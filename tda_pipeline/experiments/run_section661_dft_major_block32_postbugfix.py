"""
§6.6.1 DFT major_block32 post-bugfix 재실험 (세션 A)

목표:
- pre-bugfix 기준값(2026-04-11, combined_AB_results.json)과
  post-bugfix 조건에서 동일 실험(major + block_permute(32), Transformer)을 직접 비교.
- N=5 pilot 후 N=10 확장.

출력:
- docs/step3_data/post_bugfix_dft_major_block32_results.json
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import train_test_split

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

from generation import (
    MusicGeneratorTransformer,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from musical_metrics import compute_hybrid_distance, compute_note_distance_matrix
from note_reassign import SCALES, find_new_notes
from overlap import (
    build_activation_matrix,
    build_overlap_matrix,
    group_rBD_by_homology,
    label_cycles_from_persistence,
)
from preprocessing import simul_chord_lists, simul_union_by_dict
from run_any_track import preprocess
from run_note_reassign_unified import remap_music_notes
from sequence_metrics import evaluate_sequence_metrics
from temporal_reorder import reorder_overlap_matrix
from topology import generate_barcode_numpy
from weights import (
    compute_distance_matrix,
    compute_inter_weights_decayed,
    compute_intra_weights,
    compute_out_of_reach,
)


BASE = os.path.dirname(os.path.abspath(__file__))
STEP3 = os.path.join(BASE, "docs", "step3_data")
OUT_PATH = os.path.join(STEP3, "post_bugfix_dft_major_block32_results.json")
PRE_PATH = os.path.join(STEP3, "combined_AB_results.json")

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
METRIC = "dft"
ALPHA = 0.5
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
RATE_STEP = 0.05
THRESHOLD = 0.35

PITCH_RANGE = (40, 88)
N_CANDIDATES = 1000
BLOCK_SIZE = 32

EPOCHS = 50
LR = 0.001
BATCH_SIZE = 32

N_PILOT = 5
N_FINAL = 10
MAX_ATTEMPT = 40
SEED0 = 418000

PRE_BUGFIX_REFERENCE = {
    "vs_orig_pitch_js": 0.0968,
    "vs_orig_dtw": 2.3593,
    "vs_ref_pitch_js": 0.0034,
}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_continuous_overlap(data: dict[str, Any], cycle_labeled: dict[Any, Any]) -> np.ndarray:
    n_notes = len(data["notes_label"])
    total_length = int(data["T"])
    cp = simul_chord_lists(data["adn_i"][1][-1], data["adn_i"][2][-1])
    note_sets = simul_union_by_dict(cp, data["notes_dict"])
    nodes = list(range(1, n_notes + 1))
    ntd = np.zeros((total_length, n_notes), dtype=int)
    for t in range(min(total_length, len(note_sets))):
        if note_sets[t]:
            for n in note_sets[t]:
                if 1 <= n <= n_notes:
                    ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)
    act = build_activation_matrix(ntd_df, cycle_labeled, continuous=True)
    return act.values.astype(np.float32)


def compute_ph_post_bugfix(data: dict[str, Any]) -> tuple[dict[Any, Any], np.ndarray, float]:
    adn_i = data["adn_i"]
    notes_dict = data["notes_dict"]
    notes_label = data["notes_label"]
    n_notes = int(data["N"])
    total_length = int(data["T"])
    num_chords = int(data["num_chords"])

    metric_dist = compute_note_distance_matrix(
        notes_label,
        metric=METRIC,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
    )

    inter = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=num_chords)
    w1 = compute_intra_weights(adn_i[1][0], num_chords=num_chords)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=num_chords)
    intra = w1 + w2
    oor = compute_out_of_reach(inter, power=-2)

    profile = []
    rate = 0.0
    t0 = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        timeflow = intra + r * inter
        freq_dist = compute_distance_matrix(
            timeflow, notes_dict, oor, num_notes=n_notes
        ).values
        final_dist = compute_hybrid_distance(freq_dist, metric_dist, alpha=ALPHA)
        barcode = generate_barcode_numpy(
            mat=final_dist,
            listOfDimension=[1],
            exactStep=True,
            birthDeathSimplex=False,
            sortDimension=False,
        )
        profile.append((r, barcode))
        rate += RATE_STEP

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    if not cycle_labeled:
        raise RuntimeError("cycle_labeled empty")

    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(cp, notes_dict)
    nodes = list(range(1, n_notes + 1))
    ntd = np.zeros((total_length, n_notes), dtype=int)
    for t in range(min(total_length, len(note_sets))):
        if note_sets[t]:
            for n in note_sets[t]:
                if 1 <= n <= n_notes:
                    ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)
    act = build_activation_matrix(ntd_df, cycle_labeled, continuous=False)
    ov = build_overlap_matrix(act, cycle_labeled, threshold=THRESHOLD, total_length=total_length)
    return cycle_labeled, ov.values.astype(np.float32), round(time.time() - t0, 3)


def best_scale(generated: list[tuple[int, int, int]]) -> tuple[float, str]:
    pcs = {p % 12 for _, p, _ in generated}
    if not pcs:
        return 0.0, ""
    roots = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    best_score = 0.0
    best_name = ""
    for scale_name, scale_pcs in SCALES.items():
        for root in range(12):
            scale = {(pc + root) % 12 for pc in scale_pcs}
            score = len(pcs & scale) / len(pcs)
            if score > best_score:
                best_score = score
                best_name = f"{roots[root]} {scale_name}"
    return float(best_score), best_name


def run_single_trial(
    data: dict[str, Any],
    cycle_labeled: dict[Any, Any],
    trial_seed: int,
    original_notes: list[tuple[int, int, int]],
) -> dict[str, Any]:
    set_seed(trial_seed)

    # 방향 A: scale_major note reassignment
    reassign = find_new_notes(
        data["notes_label"],
        cycle_labeled,
        note_metric=METRIC,
        pitch_range=PITCH_RANGE,
        n_candidates=N_CANDIDATES,
        seed=trial_seed,
        harmony_mode="scale",
        scale_type="major",
    )
    new_notes_label = reassign["new_notes_label"]
    remapped_pair = remap_music_notes(
        [data["inst1"], data["inst2"]],
        data["notes_label"],
        new_notes_label,
    )
    remapped_flat = remapped_pair[0] + remapped_pair[1]

    # 방향 B: block_permute(32)
    ov_cont = build_continuous_overlap(data, cycle_labeled)
    ov_mb32, reorder_info = reorder_overlap_matrix(
        ov_cont,
        strategy="block_permute",
        block_size=BLOCK_SIZE,
        seed=trial_seed + 17,
    )
    ov_mb32 = ov_mb32.astype(np.float32)

    # Transformer 학습/생성
    total_length = int(data["T"])
    num_notes = len(new_notes_label)
    x, y = prepare_training_data(ov_mb32, remapped_pair, new_notes_label, total_length, num_notes)
    x_tr, x_va, y_tr, y_va = train_test_split(x, y, test_size=0.2, random_state=trial_seed + 31)

    model = MusicGeneratorTransformer(
        ov_mb32.shape[1],
        num_notes,
        d_model=128,
        nhead=4,
        num_layers=2,
        dropout=0.1,
        max_len=total_length,
    )
    history = train_model(
        model,
        x_tr,
        y_tr,
        x_va,
        y_va,
        epochs=EPOCHS,
        lr=LR,
        batch_size=BATCH_SIZE,
        model_type="transformer",
        seq_len=total_length,
    )
    val_loss = float(history[-1]["val_loss"])
    generated = generate_from_model(
        model,
        ov_mb32,
        new_notes_label,
        model_type="transformer",
        adaptive_threshold=True,
    )
    if not generated:
        raise RuntimeError("empty generation")

    m_orig = evaluate_sequence_metrics(generated, original_notes, name=f"postbugfix_orig_{trial_seed}")
    m_ref = evaluate_sequence_metrics(generated, remapped_flat, name=f"postbugfix_ref_{trial_seed}")
    scale_match, best_scale_name = best_scale(generated)

    return {
        "trial_seed": float(trial_seed),
        "n_notes": float(len(generated)),
        "val_loss": float(val_loss),
        "scale_root_name": reassign.get("scale_root_name"),
        "reorder": {
            "strategy": reorder_info.get("strategy"),
            "block_size": reorder_info.get("block_size"),
            "n_blocks": reorder_info.get("n_blocks"),
            "remainder": reorder_info.get("remainder"),
        },
        "vs_orig_pitch_js": float(m_orig["pitch_js"]),
        "vs_orig_dtw": float(m_orig["dtw"]),
        "vs_ref_pitch_js": float(m_ref["pitch_js"]),
        "scale_match": float(scale_match),
        "best_scale_name": best_scale_name,
    }


def stat(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None}
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=1) if arr.size > 1 else 0.0),
    }


def summarize_trials(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_samples": len(rows),
        "vs_orig_pitch_js": stat([float(r["vs_orig_pitch_js"]) for r in rows]),
        "vs_orig_dtw": stat([float(r["vs_orig_dtw"]) for r in rows]),
        "vs_ref_pitch_js": stat([float(r["vs_ref_pitch_js"]) for r in rows]),
        "scale_match": stat([float(r["scale_match"]) for r in rows]),
        "val_loss": stat([float(r["val_loss"]) for r in rows]),
        "n_notes": stat([float(r["n_notes"]) for r in rows]),
    }


def compare_to_pre(rows: list[dict[str, Any]], pre_vals: dict[str, float]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    metric_keys = ("vs_orig_pitch_js", "vs_orig_dtw", "vs_ref_pitch_js")
    for key in metric_keys:
        arr = np.asarray([float(r[key]) for r in rows], dtype=float)
        pre = float(pre_vals[key])
        mean = float(arr.mean())
        delta_pct = 100.0 * (mean - pre) / pre if pre != 0 else None

        t_stat = None
        p_val = None
        ci95 = [None, None]
        includes_pre = None
        if arr.size >= 2 and np.isfinite(arr).all():
            t_res = stats.ttest_1samp(arr, popmean=pre)
            t_stat = float(t_res.statistic) if np.isfinite(t_res.statistic) else None
            p_val = float(t_res.pvalue) if np.isfinite(t_res.pvalue) else None
            sem = stats.sem(arr)
            if np.isfinite(sem):
                low, high = stats.t.interval(
                    confidence=0.95,
                    df=arr.size - 1,
                    loc=mean,
                    scale=sem,
                )
                ci95 = [float(low), float(high)]
                includes_pre = bool(low <= pre <= high)

        out[key] = {
            "pre_bugfix": pre,
            "post_bugfix_mean": mean,
            "delta_pct": delta_pct,
            "one_sample_ttest": {
                "t_stat": t_stat,
                "p_value": p_val,
            },
            "mean_95ci": ci95,
            "pre_in_95ci": includes_pre,
        }
    return out


def run_trials_until(
    data: dict[str, Any],
    cycle_labeled: dict[Any, Any],
    target_n: int,
    existing_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = [] if existing_rows is None else list(existing_rows)
    tries = 0
    while len(rows) < target_n and tries < MAX_ATTEMPT:
        trial_seed = SEED0 + tries * 97
        tries += 1
        if any(int(r["trial_seed"]) == trial_seed for r in rows):
            continue
        try:
            row = run_single_trial(
                data=data,
                cycle_labeled=cycle_labeled,
                trial_seed=trial_seed,
                original_notes=data["inst1"] + data["inst2"],
            )
            rows.append(row)
            print(
                f"[OK] {len(rows)}/{target_n} seed={trial_seed} "
                f"pJS={row['vs_orig_pitch_js']:.4f} DTW={row['vs_orig_dtw']:.4f} "
                f"ref_pJS={row['vs_ref_pitch_js']:.4f} scale={row['scale_match']:.3f}"
            )
        except Exception as exc:
            print(f"[retry] seed={trial_seed} -> {exc}")
    if len(rows) < target_n:
        raise RuntimeError(f"only {len(rows)}/{target_n} trials succeeded")
    return rows


def load_pre_bugfix_from_json() -> dict[str, Any]:
    if not os.path.exists(PRE_PATH):
        return {"available": False}
    with open(PRE_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    row = (
        payload.get("experiments", {}).get("major_block32", {})
        if isinstance(payload, dict) else {}
    )
    vo = row.get("vs_original", {})
    vr = row.get("vs_ref", {})
    return {
        "available": True,
        "path": os.path.relpath(PRE_PATH, BASE),
        "raw_from_file": {
            "vs_orig_pitch_js": vo.get("pitch_js"),
            "vs_orig_dtw": vo.get("dtw"),
            "vs_ref_pitch_js": vr.get("pitch_js"),
        },
    }


def main() -> None:
    t0 = time.time()
    os.makedirs(STEP3, exist_ok=True)

    print("=" * 84)
    print("§6.6.1 DFT major_block32 post-bugfix 실험")
    print("=" * 84)
    print(
        f"config: metric={METRIC}, ow={OCTAVE_WEIGHT}, dw={DURATION_WEIGHT}, "
        f"alpha={ALPHA}, rate_step={RATE_STEP}, threshold={THRESHOLD}"
    )

    data = preprocess(MIDI_FILE)
    print(
        f"[preprocess] T={data['T']} N={data['N']} C={data['num_chords']} "
        f"inst1={len(data['inst1'])} inst2={len(data['inst2'])}"
    )

    cycle_labeled, _, ph_time = compute_ph_post_bugfix(data)
    print(f"[PH] cycles={len(cycle_labeled)} ph_time={ph_time:.1f}s")

    # 1) N=5 pilot
    print("\n[N=5 pilot]")
    pilot_rows = run_trials_until(data, cycle_labeled, N_PILOT, [])
    pilot_summary = summarize_trials(pilot_rows)
    pilot_cmp = compare_to_pre(pilot_rows, PRE_BUGFIX_REFERENCE)

    # 2) N=10 확장
    print("\n[N=10 확장]")
    final_rows = run_trials_until(data, cycle_labeled, N_FINAL, pilot_rows)
    final_summary = summarize_trials(final_rows)
    final_cmp = compare_to_pre(final_rows, PRE_BUGFIX_REFERENCE)

    within_error = all(
        bool(final_cmp[k]["pre_in_95ci"]) for k in ("vs_orig_pitch_js", "vs_orig_dtw", "vs_ref_pitch_js")
    )
    footnote_flag = "해제 후보" if within_error else "재검토 필요"

    payload = {
        "experiment": "section_6_6_1_dft_major_block32_post_bugfix",
        "script": os.path.basename(__file__),
        "date": now_iso(),
        "runtime_s": round(time.time() - t0, 2),
        "status": "completed",
        "config": {
            "midi_file": MIDI_FILE,
            "metric": METRIC,
            "octave_weight": OCTAVE_WEIGHT,
            "duration_weight": DURATION_WEIGHT,
            "alpha": ALPHA,
            "rate_step": RATE_STEP,
            "threshold": THRESHOLD,
            "reassign": {
                "harmony_mode": "scale",
                "scale_type": "major",
                "pitch_range": list(PITCH_RANGE),
                "n_candidates": N_CANDIDATES,
            },
            "reorder": {"strategy": "block_permute", "block_size": BLOCK_SIZE},
            "model": {
                "type": "transformer",
                "epochs": EPOCHS,
                "lr": LR,
                "batch_size": BATCH_SIZE,
            },
            "n_pilot": N_PILOT,
            "n_final": N_FINAL,
            "seed0": SEED0,
        },
        "diagnostics": {
            "T": int(data["T"]),
            "N": int(data["N"]),
            "num_chords": int(data["num_chords"]),
            "n_cycles": int(len(cycle_labeled)),
            "ph_time_s": ph_time,
        },
        "pre_bugfix_reference": {
            "requested_baseline": PRE_BUGFIX_REFERENCE,
            "from_combined_ab_json": load_pre_bugfix_from_json(),
        },
        "pilot_n5": {
            "summary": pilot_summary,
            "comparison_vs_pre": pilot_cmp,
            "trials": pilot_rows,
        },
        "final_n10": {
            "summary": final_summary,
            "comparison_vs_pre": final_cmp,
            "trials": final_rows,
        },
        "footnote_decision_flag": {
            "status": footnote_flag,
            "criteria": "pre-bugfix 값이 3개 핵심지표의 post-bugfix mean 95% CI 안에 모두 포함되는지",
            "all_metrics_pre_in_95ci": within_error,
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n[saved] {os.path.relpath(OUT_PATH, BASE)}")
    print(f"[flag] §6.6.1 각주 판단: {footnote_flag}")


if __name__ == "__main__":
    main()
