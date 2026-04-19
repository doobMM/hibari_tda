"""
Task 40 — §6.3~§6.6 DFT 전환 전면 재실험 (세션 A)
"""

from __future__ import annotations

import json
import os
import pickle
import random
import time
import traceback
from typing import Any, Callable

import numpy as np
from sklearn.model_selection import train_test_split

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from config import PipelineConfig
from generation import (
    MusicGeneratorFC,
    MusicGeneratorTransformer,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from note_reassign import SCALES, find_new_notes
from run_note_reassign_unified import analyze_harmony, remap_music_notes
from sequence_metrics import evaluate_sequence_metrics
from temporal_reorder import reorder_overlap_matrix
from utils.result_meta import build_result_header

import run_dft_gap0_suite as suite


BASE = os.path.dirname(os.path.abspath(__file__))
STEP3 = os.path.join(BASE, "docs", "step3_data")
SCRIPT = os.path.basename(__file__)

OUT1 = os.path.join(STEP3, "temporal_reorder_transformer_dft_gap0.json")
OUT2 = os.path.join(STEP3, "harmony_transformer_dft_gap0.json")
OUT3 = os.path.join(STEP3, "combined_AB_dft_gap0.json")
OUTS = os.path.join(STEP3, "phase3_task40_section66_dft_summary.json")

REF_T40_1 = os.path.join(STEP3, "temporal_reorder_dl_v2_results.json")
REF_T40_2 = os.path.join(STEP3, "note_reassign_harmony_dl_results.json")
REF_T40_3 = os.path.join(STEP3, "combined_AB_results.json")

CACHE = os.path.join(BASE, "cache", "metric_dft_alpha0p25_ow0p3_dw1p0.pkl")

METRIC = "dft"
ALPHA = 0.25
OW = 0.3
DW = 1.0
MIN_GAP = 0
POST_BUGFIX = True
THRESHOLD = 0.35

N = 5
MAX_ATTEMPT = 20
SEED0 = 404000

TR_EPOCHS = 50
TR_LR = 0.001
TR_BATCH = 32
TR_DROPOUT = 0.3

FC_EPOCHS = 200
FC_LR = 0.001
FC_BATCH = 32
FC_HIDDEN = 128
FC_DROPOUT = 0.3


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    os.makedirs(STEP3, exist_ok=True)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def save_json(path: str, payload: dict[str, Any]) -> str:
    ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[saved] {path}")
    return path


def load_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def stat(v: list[float]) -> dict[str, float | None]:
    if not v:
        return {"mean": None, "std": None}
    arr = np.asarray(v, dtype=float)
    return {
        "mean": round(float(arr.mean()), 6),
        "std": round(float(arr.std(ddof=1) if arr.size > 1 else 0.0), 6),
    }


def hdr(model: str, n_rep: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = float(ALPHA)
    cfg.metric.octave_weight = float(OW)
    cfg.metric.duration_weight = float(DW)
    cfg.min_onset_gap = int(MIN_GAP)
    cfg.post_bugfix = bool(POST_BUGFIX)
    x = {"model": model}
    if extra:
        x.update(extra)
    return build_result_header(cfg, script_name=SCRIPT, n_repeats=n_rep, extra=x)


def compact_info(info: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    keep = [
        "strategy",
        "block_size",
        "n_blocks",
        "remainder",
        "n_segments",
        "avg_segment_len",
        "temperature",
        "n_unique_patterns",
    ]
    return {k: info[k] for k in keep if k in info}


def build_ctx() -> dict[str, Any]:
    data = suite.setup_hibari()
    bundle = None
    cache_meta: dict[str, Any] = {"path": CACHE, "used_cache": False}

    if os.path.exists(CACHE):
        try:
            with open(CACHE, "rb") as f:
                c = pickle.load(f)
            if all(k in c for k in ("cycle_labeled", "overlap_binary", "activation_continuous")):
                bundle = c
                cache_meta["used_cache"] = True
                cache_meta["alpha_in_cache"] = float(c.get("alpha", np.nan))
        except Exception as exc:
            cache_meta["cache_error"] = str(exc)

    if bundle is None:
        b = suite.build_overlap_bundle(
            data,
            METRIC,
            alpha=ALPHA,
            octave_weight=OW,
            duration_weight=DW,
            use_decayed=False,
            threshold=THRESHOLD,
        )
        bundle = {
            "cycle_labeled": b["cycle_labeled"],
            "overlap_binary": b["overlap_binary"],
            "activation_continuous": b["activation_continuous"],
            "alpha": float(b["alpha"]),
        }
        try:
            with open(CACHE, "wb") as f:
                pickle.dump(bundle, f)
        except Exception as exc:
            cache_meta["cache_write_error"] = str(exc)

    ov_bin = bundle["overlap_binary"]
    ov_bin = ov_bin.values.astype(np.float32) if hasattr(ov_bin, "values") else np.asarray(ov_bin, dtype=np.float32)
    ov_cont = bundle["activation_continuous"]
    ov_cont = ov_cont.values.astype(np.float32) if hasattr(ov_cont, "values") else np.asarray(ov_cont, dtype=np.float32)

    notes_label = data["notes_label"]
    original_pair = [data["inst1_real"], data["inst2_real"]]
    original_notes = data["inst1_real"] + data["inst2_real"]
    T = int(data["T"])
    n_notes = len(notes_label)
    _, y_orig = prepare_training_data(ov_cont, original_pair, notes_label, T, n_notes)

    return {
        "data": data,
        "cache_meta": cache_meta,
        "cycle_labeled": bundle["cycle_labeled"],
        "ov_bin": ov_bin,
        "ov_cont": ov_cont,
        "notes_label": notes_label,
        "original_pair": original_pair,
        "original_notes": original_notes,
        "T": T,
        "n_notes": n_notes,
        "n_cycles": len(bundle["cycle_labeled"]),
        "y_orig": y_orig,
    }


def fit(
    model_type: str,
    x: np.ndarray,
    y: np.ndarray,
    n_notes: int,
    T: int,
    seed: int,
    use_pos_emb: bool = True,
) -> tuple[Any, float, int]:
    if torch is None:
        raise RuntimeError("torch 없음")
    last_exc: Exception | None = None
    for r in range(3):
        s = seed + r * 10000
        try:
            set_seed(s)
            xtr, xva, ytr, yva = train_test_split(x, y, test_size=0.2, random_state=s)
            if model_type == "transformer":
                model = MusicGeneratorTransformer(
                    num_cycles=x.shape[1],
                    num_notes=n_notes,
                    d_model=128,
                    nhead=4,
                    num_layers=2,
                    dropout=TR_DROPOUT,
                    max_len=T,
                    use_pos_emb=use_pos_emb,
                )
                hist = train_model(
                    model, xtr, ytr, xva, yva,
                    epochs=TR_EPOCHS, lr=TR_LR, batch_size=TR_BATCH,
                    model_type="transformer", seq_len=T
                )
            elif model_type == "fc":
                model = MusicGeneratorFC(
                    num_cycles=x.shape[1],
                    num_notes=n_notes,
                    hidden_dim=FC_HIDDEN,
                    dropout=FC_DROPOUT,
                )
                hist = train_model(
                    model, xtr, ytr, xva, yva,
                    epochs=FC_EPOCHS, lr=FC_LR, batch_size=FC_BATCH,
                    model_type="fc", seq_len=T
                )
            else:
                raise ValueError(model_type)
            vloss = float(hist[-1]["val_loss"])
            if not np.isfinite(vloss):
                raise RuntimeError(f"val_loss not finite: {vloss}")
            return model, vloss, s
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"fit 실패 {model_type}: {last_exc}")


def best_scale(generated: list[tuple[int, int, int]]) -> tuple[float, str]:
    pcs = {p % 12 for _, p, _ in generated}
    if not pcs:
        return 0.0, ""
    roots = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    best_score, best_name = 0.0, ""
    for sname, spc in SCALES.items():
        for r in range(12):
            scale = {(pc + r) % 12 for pc in spc}
            score = len(pcs & scale) / len(pcs)
            if score > best_score:
                best_score = score
                best_name = f"{roots[r]} {sname}"
    return float(best_score), best_name


def eval_one(model: Any, model_type: str, ov: np.ndarray, notes_label: dict[tuple[int, int], int],
             original: list[tuple[int, int, int]], name: str) -> dict[str, Any]:
    gen = generate_from_model(
        model, ov, notes_label, model_type=model_type,
        adaptive_threshold=True, min_onset_gap=MIN_GAP
    )
    if not gen:
        raise RuntimeError(f"{name}: empty generation")
    m = evaluate_sequence_metrics(gen, original, name=name)
    sm, sn = best_scale(gen)
    return {
        "pitch_js": float(m["pitch_js"]),
        "transition_js": float(m["transition_js"]),
        "dtw": float(m["dtw"]),
        "n_notes": float(len(gen)),
        "scale_match": sm,
        "best_scale_name": sn,
    }


def eval_two(model: Any, model_type: str, ov: np.ndarray, notes_label: dict[tuple[int, int], int],
             original: list[tuple[int, int, int]], ref: list[tuple[int, int, int]], name: str) -> dict[str, Any]:
    gen = generate_from_model(
        model, ov, notes_label, model_type=model_type,
        adaptive_threshold=True, min_onset_gap=MIN_GAP
    )
    if not gen:
        raise RuntimeError(f"{name}: empty generation")
    mo = evaluate_sequence_metrics(gen, original, name=f"{name}_orig")
    mr = evaluate_sequence_metrics(gen, ref, name=f"{name}_ref")
    sm, sn = best_scale(gen)
    return {
        "vs_orig_pitch_js": float(mo["pitch_js"]),
        "vs_orig_transition_js": float(mo["transition_js"]),
        "vs_orig_dtw": float(mo["dtw"]),
        "vs_ref_pitch_js": float(mr["pitch_js"]),
        "vs_ref_transition_js": float(mr["transition_js"]),
        "vs_ref_dtw": float(mr["dtw"]),
        "n_notes": float(len(gen)),
        "scale_match": sm,
        "best_scale_name": sn,
    }


def repeat(label: str, seed_offset: int, runner: Callable[[int], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tries = 0
    while len(rows) < N and tries < MAX_ATTEMPT:
        seed = SEED0 + seed_offset + tries * 97
        tries += 1
        try:
            row = runner(seed)
            row["trial_seed"] = float(seed)
            rows.append(row)
            print(f"  [OK] {label} {len(rows)}/{N} seed={seed}")
        except Exception as exc:
            print(f"  [retry] {label} seed={seed} -> {exc}")
    if len(rows) < N:
        raise RuntimeError(f"{label}: {len(rows)}/{N} only")
    return rows


# --- TASKS ---
def sum_flat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pitch_js": stat([float(r["pitch_js"]) for r in rows]),
        "transition_js": stat([float(r["transition_js"]) for r in rows]),
        "dtw": stat([float(r["dtw"]) for r in rows]),
        "val_loss": stat([float(r["val_loss"]) for r in rows]),
        "n_notes": stat([float(r["n_notes"]) for r in rows]),
        "scale_match": stat([float(r.get("scale_match", 0.0)) for r in rows]),
        "n_samples": len(rows),
    }


def sum_nested(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "vs_orig_pitch_js": stat([float(r["vs_orig_pitch_js"]) for r in rows]),
        "vs_orig_transition_js": stat([float(r["vs_orig_transition_js"]) for r in rows]),
        "vs_orig_dtw": stat([float(r["vs_orig_dtw"]) for r in rows]),
        "vs_ref_pitch_js": stat([float(r["vs_ref_pitch_js"]) for r in rows]),
        "vs_ref_transition_js": stat([float(r["vs_ref_transition_js"]) for r in rows]),
        "vs_ref_dtw": stat([float(r["vs_ref_dtw"]) for r in rows]),
        "val_loss": stat([float(r["val_loss"]) for r in rows]),
        "n_notes": stat([float(r["n_notes"]) for r in rows]),
        "scale_match": stat([float(r.get("scale_match", 0.0)) for r in rows]),
        "n_samples": len(rows),
    }


def make_harmony_configs(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    notes_label = ctx["notes_label"]
    cycle_labeled = ctx["cycle_labeled"]
    original_pair = ctx["original_pair"]
    original_notes = ctx["original_notes"]

    out: dict[str, dict[str, Any]] = {
        "original": {
            "notes_label": notes_label,
            "inst_pair": original_pair,
            "ref_notes": original_notes,
            "reassign": None,
        }
    }
    cases = [
        ("baseline", {"harmony_mode": None, "pitch_range": (40, 88)}),
        ("scale_major", {"harmony_mode": "scale", "scale_type": "major", "pitch_range": (40, 88)}),
        ("scale_penta", {"harmony_mode": "scale", "scale_type": "pentatonic", "pitch_range": (21, 108)}),
    ]
    for i, (name, kwargs) in enumerate(cases):
        r = find_new_notes(
            notes_label, cycle_labeled, note_metric=METRIC,
            pitch_range=kwargs["pitch_range"],
            n_candidates=1000,
            seed=SEED0 + 700 + i,
            harmony_mode=kwargs.get("harmony_mode"),
            scale_type=kwargs.get("scale_type", "major"),
        )
        new_label = r["new_notes_label"]
        remapped = remap_music_notes(original_pair, notes_label, new_label)
        remapped_flat = remapped[0] + remapped[1]
        h = analyze_harmony(notes_label, cycle_labeled, new_label, r["new_notes"])
        out[name] = {
            "notes_label": new_label,
            "inst_pair": remapped,
            "ref_notes": remapped_flat,
            "reassign": {
                "note_dist_error": float(r["note_dist_error"]),
                "cycle_dist_error": (
                    float(r["cycle_dist_error"])
                    if r.get("cycle_dist_error") is not None
                    else None
                ),
                "n_pitch_classes": int(h["n_pitch_classes"]),
                "best_scale_match": h["best_scale_name"],
                "harmony_mode": kwargs.get("harmony_mode"),
                "scale_type": kwargs.get("scale_type"),
                "pitch_range": kwargs.get("pitch_range"),
            },
        }
    return out


def task1(ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 84)
    print("T40-1 | Temporal Reorder Transformer DFT N=5")
    print("=" * 84)

    ov = ctx["ov_cont"]
    y_orig = ctx["y_orig"]
    notes_label = ctx["notes_label"]
    original = ctx["original_notes"]
    T = ctx["T"]
    n_notes = ctx["n_notes"]

    trials = {
        "noPE_baseline": [],
        "noPE_segment_shuffle": [],
        "noPE_markov_tau1.0": [],
        "noPE_retrain_segment_shuffle": [],
        "noPE_retrain_markov_tau1.0": [],
        "PE_baseline": [],
    }
    reorder_meta: dict[str, Any] = {}

    success = 0
    attempt = 0
    while success < N and attempt < MAX_ATTEMPT:
        s = SEED0 + 10000 + attempt * 131
        attempt += 1
        try:
            seg, seg_i = reorder_overlap_matrix(ov, strategy="segment_shuffle", seed=s + 11)
            mkv, mkv_i = reorder_overlap_matrix(ov, strategy="markov_resample", seed=s + 23, temperature=1.0)
            seg = seg.astype(np.float32)
            mkv = mkv.astype(np.float32)
            if "segment_shuffle" not in reorder_meta:
                reorder_meta["segment_shuffle"] = compact_info(seg_i)
            if "markov_tau1.0" not in reorder_meta:
                reorder_meta["markov_tau1.0"] = compact_info(mkv_i)

            m0, v0, ts0 = fit("transformer", ov, y_orig, n_notes, T, s + 101, use_pos_emb=False)
            for k, x in (
                ("noPE_baseline", ov),
                ("noPE_segment_shuffle", seg),
                ("noPE_markov_tau1.0", mkv),
            ):
                r = eval_one(m0, "transformer", x, notes_label, original, f"{k}_{success+1}")
                r["val_loss"] = float(v0)
                r["train_seed"] = float(ts0)
                trials[k].append(r)

            ms, vs, tss = fit("transformer", seg, y_orig, n_notes, T, s + 201, use_pos_emb=False)
            rs = eval_one(ms, "transformer", seg, notes_label, original, f"noPE_retrain_seg_{success+1}")
            rs["val_loss"] = float(vs)
            rs["train_seed"] = float(tss)
            trials["noPE_retrain_segment_shuffle"].append(rs)

            mm, vm, tsm = fit("transformer", mkv, y_orig, n_notes, T, s + 301, use_pos_emb=False)
            rm = eval_one(mm, "transformer", mkv, notes_label, original, f"noPE_retrain_mkv_{success+1}")
            rm["val_loss"] = float(vm)
            rm["train_seed"] = float(tsm)
            trials["noPE_retrain_markov_tau1.0"].append(rm)

            mp, vp, tsp = fit("transformer", ov, y_orig, n_notes, T, s + 401, use_pos_emb=True)
            rp = eval_one(mp, "transformer", ov, notes_label, original, f"PE_baseline_{success+1}")
            rp["val_loss"] = float(vp)
            rp["train_seed"] = float(tsp)
            trials["PE_baseline"].append(rp)
            success += 1
        except Exception as exc:
            print(f"  [T40-1 retry] {exc}")

    if success < N:
        raise RuntimeError(f"T40-1 success {success}/{N}")

    cond = {k: sum_flat(v) for k, v in trials.items()}
    baseline_p = cond["noPE_baseline"]["pitch_js"]["mean"]
    baseline_d = cond["noPE_baseline"]["dtw"]["mean"]
    seg_p = cond["noPE_retrain_segment_shuffle"]["pitch_js"]["mean"]
    seg_d = cond["noPE_retrain_segment_shuffle"]["dtw"]["mean"]
    mk_p = cond["noPE_retrain_markov_tau1.0"]["pitch_js"]["mean"]
    mk_d = cond["noPE_retrain_markov_tau1.0"]["dtw"]["mean"]
    dilemma = bool(seg_p > baseline_p and seg_d > baseline_d and mk_p > baseline_p and mk_d > baseline_d)

    cmp_rows: dict[str, Any] = {}
    ref = load_json(REF_T40_1)
    if ref and "experiments" in ref:
        m = {
            "noPE_baseline": "noPE_baseline",
            "noPE_segment_shuffle": "noPE_segment_shuffle",
            "noPE_markov_tau1.0": "noPE_markov_resample_temperature1.0",
            "noPE_retrain_segment_shuffle": "noPE_retrain_segment_shuffle",
            "noPE_retrain_markov_tau1.0": "noPE_retrain_markov_resample_temperature1.0",
            "PE_baseline": "baseline",
        }
        for nk, ok in m.items():
            old = ref["experiments"].get(ok)
            if not old:
                continue
            old_p = float(old.get("pitch_js", np.nan))
            old_d = float(old.get("dtw", np.nan))
            new_p = cond[nk]["pitch_js"]["mean"]
            new_d = cond[nk]["dtw"]["mean"]
            cmp_rows[nk] = {
                "tonnetz_pitch_js": old_p,
                "tonnetz_dtw": old_d,
                "dft_pitch_js": new_p,
                "dft_dtw": new_d,
                "delta_pitch_js_pct": round(100.0 * (new_p - old_p) / old_p, 4) if old_p > 0 else None,
                "delta_dtw_pct": round(100.0 * (new_d - old_d) / old_d, 4) if old_d > 0 else None,
            }

    payload = {
        **hdr("transformer", N, {"task": "T40-1", "track": "hibari", "overlap_type": "continuous"}),
        "track": "hibari",
        "n_cycles": int(ctx["n_cycles"]),
        "T": int(T),
        "N": int(n_notes),
        "epochs": TR_EPOCHS,
        "lr": TR_LR,
        "dropout": TR_DROPOUT,
        "conditions": cond,
        "trials": trials,
        "reorder_examples": reorder_meta,
        "tonnetz_reference_comparison": {
            "source": os.path.relpath(REF_T40_1, BASE),
            "rows": cmp_rows,
        },
        "verdict": {
            "dilemma_reproduced": dilemma,
            "section_64_narrative": "유지" if dilemma else "부분 수정 권장",
        },
    }
    return save_json(OUT1, payload), {
        "dilemma_reproduced": dilemma,
        "segment_retrain_dtw_mean": cond["noPE_retrain_segment_shuffle"]["dtw"]["mean"],
    }


def task2(ctx: dict[str, Any], hcfg: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 84)
    print("T40-2 | Harmony Transformer DFT N=5")
    print("=" * 84)

    ov = ctx["ov_cont"]
    T = ctx["T"]
    original = ctx["original_notes"]

    trials: dict[str, list[dict[str, Any]]] = {k: [] for k in hcfg.keys()}
    for i, (name, cfg) in enumerate(hcfg.items()):
        notes_label = cfg["notes_label"]
        inst_pair = cfg["inst_pair"]
        ref_notes = cfg["ref_notes"]
        n_notes = len(notes_label)
        _, y = prepare_training_data(ov, inst_pair, notes_label, T, n_notes)

        def _runner(seed: int) -> dict[str, Any]:
            m, v, ts = fit("transformer", ov, y, n_notes, T, seed, use_pos_emb=True)
            r = eval_two(m, "transformer", ov, notes_label, original, ref_notes, f"{name}_{seed}")
            r["val_loss"] = float(v)
            r["train_seed"] = float(ts)
            return r

        trials[name] = repeat(f"T40-2:{name}", 20000 + i * 1000, _runner)

    cond = {k: sum_nested(v) for k, v in trials.items()}
    major = cond["scale_major"]["vs_ref_pitch_js"]["mean"]
    penta = cond["scale_penta"]["vs_ref_pitch_js"]["mean"]
    major_o = cond["scale_major"]["vs_orig_pitch_js"]["mean"]
    penta_o = cond["scale_penta"]["vs_orig_pitch_js"]["mean"]
    major_best = bool(major <= penta and major_o <= penta_o)

    cmp_rows: dict[str, Any] = {}
    ref = load_json(REF_T40_2)
    if ref and "experiments" in ref:
        mm = {
            "original": "original_transformer",
            "baseline": "baseline_transformer",
            "scale_major": "scale_major_transformer",
            "scale_penta": "scale_penta_transformer",
        }
        for nk, ok in mm.items():
            row = ref["experiments"].get(ok)
            if not row:
                continue
            if nk == "original":
                op = float(row.get("pitch_js", np.nan))
                od = float(row.get("dtw", np.nan))
                rp = float(row.get("pitch_js", np.nan))
            else:
                vo = row.get("vs_original", {})
                vr = row.get("vs_remapped", {})
                op = float(vo.get("pitch_js", np.nan))
                od = float(vo.get("dtw", np.nan))
                rp = float(vr.get("pitch_js", np.nan))
            npjs = cond[nk]["vs_orig_pitch_js"]["mean"]
            ndtw = cond[nk]["vs_orig_dtw"]["mean"]
            nrp = cond[nk]["vs_ref_pitch_js"]["mean"]
            cmp_rows[nk] = {
                "tonnetz_vs_orig_pjs": op,
                "tonnetz_vs_orig_dtw": od,
                "tonnetz_vs_ref_pjs": rp,
                "dft_vs_orig_pjs": npjs,
                "dft_vs_orig_dtw": ndtw,
                "dft_vs_ref_pjs": nrp,
                "delta_vs_orig_pjs_pct": round(100.0 * (npjs - op) / op, 4) if op > 0 else None,
                "delta_vs_orig_dtw_pct": round(100.0 * (ndtw - od) / od, 4) if od > 0 else None,
                "delta_vs_ref_pjs_pct": round(100.0 * (nrp - rp) / rp, 4) if rp > 0 else None,
            }

    payload = {
        **hdr("transformer", N, {"task": "T40-2", "track": "hibari", "overlap_type": "continuous"}),
        "track": "hibari",
        "n_cycles": int(ctx["n_cycles"]),
        "T": int(T),
        "N": int(ctx["n_notes"]),
        "epochs": TR_EPOCHS,
        "lr": TR_LR,
        "dropout": TR_DROPOUT,
        "conditions": cond,
        "trials": trials,
        "note_configs": {
            k: {"n_notes": len(v["notes_label"]), "reassign": v["reassign"]}
            for k, v in hcfg.items()
        },
        "tonnetz_reference_comparison": {
            "source": os.path.relpath(REF_T40_2, BASE),
            "rows": cmp_rows,
        },
        "verdict": {
            "scale_major_best_kept": major_best,
            "section_65_narrative": "유지" if major_best else "재검토 필요",
        },
    }
    return save_json(OUT2, payload), {
        "scale_major_best_kept": major_best,
        "scale_major_vs_ref_pjs": cond["scale_major"]["vs_ref_pitch_js"]["mean"],
    }


def task3(ctx: dict[str, Any], hcfg: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 84)
    print("T40-3 | Combined AB DFT (Transformer + FC) N=5")
    print("=" * 84)

    ov_bin = ctx["ov_bin"]
    ov_cont = ctx["ov_cont"]
    T = ctx["T"]
    original = ctx["original_notes"]
    note_map = {"orig": "original", "major": "scale_major"}
    cond_def = [
        ("orig_none", "orig", "binary", {"strategy": "none"}),
        ("orig_segment_shuffle", "orig", "binary", {"strategy": "segment_shuffle"}),
        ("orig_block32", "orig", "binary", {"strategy": "block_permute", "block_size": 32}),
        ("major_none", "major", "binary", {"strategy": "none"}),
        ("major_segment_shuffle", "major", "binary", {"strategy": "segment_shuffle"}),
        ("major_block32", "major", "binary", {"strategy": "block_permute", "block_size": 32}),
        ("major_markov", "major", "binary", {"strategy": "markov_resample", "temperature": 1.0}),
        ("orig_continuous", "orig", "continuous", {"strategy": "none"}),
        ("major_continuous", "major", "continuous", {"strategy": "none"}),
        ("major_block32_continuous", "major", "continuous", {"strategy": "block_permute", "block_size": 32}),
    ]

    y_target: dict[str, np.ndarray] = {}
    for key in ("original", "scale_major"):
        cfg = hcfg[key]
        _, y = prepare_training_data(ov_cont, cfg["inst_pair"], cfg["notes_label"], T, len(cfg["notes_label"]))
        y_target[key] = y

    def _ov(base_name: str, reorder: dict[str, Any], seed: int) -> tuple[np.ndarray, dict[str, Any]]:
        base = ov_bin if base_name == "binary" else ov_cont
        if reorder["strategy"] == "none":
            return base.astype(np.float32), {"strategy": "none"}
        kwargs = dict(reorder)
        strat = kwargs.pop("strategy")
        o, i = reorder_overlap_matrix(base, strategy=strat, seed=seed + 17, **kwargs)
        return o.astype(np.float32), compact_info(i)

    trials = {"transformer": {}, "fc": {}}
    summary = {"transformer": {}, "fc": {}}
    reorder_examples: dict[str, Any] = {}

    for model in ("transformer", "fc"):
        for i, (name, note_key, ov_type, reorder) in enumerate(cond_def):
            src_key = note_map[note_key]
            cfg = hcfg[src_key]
            n_notes = len(cfg["notes_label"])
            notes_label = cfg["notes_label"]
            ref_notes = cfg["ref_notes"]
            y = y_target[src_key]

            def _runner(seed: int) -> dict[str, Any]:
                x, info = _ov(ov_type, reorder, seed)
                if name not in reorder_examples:
                    reorder_examples[name] = info
                if model == "transformer":
                    m, v, ts = fit("transformer", x, y, n_notes, T, seed, use_pos_emb=True)
                    r = eval_two(m, "transformer", x, notes_label, original, ref_notes, f"{model}_{name}_{seed}")
                else:
                    m, v, ts = fit("fc", x, y, n_notes, T, seed, use_pos_emb=True)
                    r = eval_two(m, "fc", x, notes_label, original, ref_notes, f"{model}_{name}_{seed}")
                r["val_loss"] = float(v)
                r["train_seed"] = float(ts)
                return r

            rows = repeat(f"T40-3:{model}:{name}", 30000 + (0 if model == "transformer" else 100000) + i * 200, _runner)
            trials[model][name] = rows
            summary[model][name] = sum_nested(rows)

    def _best(ms: dict[str, Any]) -> dict[str, Any]:
        best_name, best_val = None, float("inf")
        for k, row in ms.items():
            v = row["vs_ref_pitch_js"]["mean"]
            if v is not None and v < best_val:
                best_name, best_val = k, float(v)
        if best_name is None:
            return {"setting": None}
        return {
            "setting": best_name,
            "vs_ref_pjs": ms[best_name]["vs_ref_pitch_js"]["mean"],
            "vs_orig_dtw": ms[best_name]["vs_orig_dtw"]["mean"],
            "vs_orig_pjs": ms[best_name]["vs_orig_pitch_js"]["mean"],
            "scale_match": ms[best_name]["scale_match"]["mean"],
        }

    best_t = _best(summary["transformer"])
    best_f = _best(summary["fc"])

    ref = load_json(REF_T40_3)
    ton_mb32 = None
    if ref and "experiments" in ref and "major_block32" in ref["experiments"]:
        row = ref["experiments"]["major_block32"]
        vo = row.get("vs_original", {})
        vr = row.get("vs_ref", {})
        ton_mb32 = {
            "vs_orig_pjs": float(vo.get("pitch_js", np.nan)),
            "vs_orig_dtw": float(vo.get("dtw", np.nan)),
            "vs_ref_pjs": float(vr.get("pitch_js", np.nan)),
        }

    t_mb32 = summary["transformer"]["major_block32"]
    f_mb32 = summary["fc"]["major_block32"]
    rec = "FC 우세"
    if t_mb32["vs_ref_pitch_js"]["mean"] < f_mb32["vs_ref_pitch_js"]["mean"]:
        rec = "Transformer 우세"

    payload = {
        **hdr("transformer+fc", N, {"task": "T40-3", "track": "hibari"}),
        "track": "hibari",
        "n_cycles": int(ctx["n_cycles"]),
        "T": int(T),
        "N": int(ctx["n_notes"]),
        "models_config": {
            "transformer": {
                "epochs": TR_EPOCHS, "lr": TR_LR, "dropout": TR_DROPOUT,
                "d_model": 128, "nhead": 4, "num_layers": 2,
            },
            "fc": {
                "epochs": FC_EPOCHS, "lr": FC_LR, "dropout": FC_DROPOUT,
                "hidden_dim": FC_HIDDEN,
            },
        },
        "conditions": {
            k: {
                "note_set": note_map[nk],
                "overlap_type": ot,
                "reorder": ro,
            }
            for (k, nk, ot, ro) in cond_def
        },
        "models": summary,
        "trials": trials,
        "reorder_examples": reorder_examples,
        "comparison": {
            "best_transformer": best_t,
            "best_fc": best_f,
            "major_block32_recompute": {
                "tonnetz_transformer": ton_mb32,
                "dft_transformer": {
                    "vs_orig_pjs": t_mb32["vs_orig_pitch_js"]["mean"],
                    "vs_orig_dtw": t_mb32["vs_orig_dtw"]["mean"],
                    "vs_ref_pjs": t_mb32["vs_ref_pitch_js"]["mean"],
                    "scale_match": t_mb32["scale_match"]["mean"],
                },
                "dft_fc": {
                    "vs_orig_pjs": f_mb32["vs_orig_pitch_js"]["mean"],
                    "vs_orig_dtw": f_mb32["vs_orig_dtw"]["mean"],
                    "vs_ref_pjs": f_mb32["vs_ref_pitch_js"]["mean"],
                    "scale_match": f_mb32["scale_match"]["mean"],
                },
            },
            "recommendation": rec,
        },
    }
    return save_json(OUT3, payload), {
        "recommendation": rec,
        "best_transformer": best_t.get("setting"),
        "best_fc": best_f.get("setting"),
    }


def main() -> None:
    ensure_dirs()
    t0 = time.time()
    summary: dict[str, Any] = {
        "script": SCRIPT,
        "date_start": now(),
        "same_python_session": True,
        "status": "running",
        "config": {
            "metric": METRIC,
            "alpha": ALPHA,
            "octave_weight": OW,
            "duration_weight": DW,
            "min_onset_gap": MIN_GAP,
            "post_bugfix": POST_BUGFIX,
        },
        "outputs": {},
        "tasks": {},
        "missing_requested_reference_files": [],
    }

    for p in (
        os.path.join(BASE, "memory", "project_phase2_gap0_findings_0417.md"),
        os.path.join(BASE, "memory", "project_wave2_d_completed_0417.md"),
    ):
        if not os.path.exists(p):
            summary["missing_requested_reference_files"].append(os.path.relpath(p, BASE))

    try:
        print("=" * 84)
        print("Task 40 start")
        print("=" * 84)
        ctx = build_ctx()
        summary["context"] = {
            "n_cycles": int(ctx["n_cycles"]),
            "T": int(ctx["T"]),
            "N": int(ctx["n_notes"]),
            "cache_meta": ctx["cache_meta"],
        }

        hcfg = make_harmony_configs(ctx)

        o1, i1 = task1(ctx)
        summary["outputs"]["T40-1"] = os.path.relpath(o1, BASE)
        summary["tasks"]["T40-1"] = i1

        o2, i2 = task2(ctx, hcfg)
        summary["outputs"]["T40-2"] = os.path.relpath(o2, BASE)
        summary["tasks"]["T40-2"] = i2

        o3, i3 = task3(ctx, hcfg)
        summary["outputs"]["T40-3"] = os.path.relpath(o3, BASE)
        summary["tasks"]["T40-3"] = i3

        summary["status"] = "completed"
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        print("[ERROR]", exc)
        print(traceback.format_exc())
    finally:
        summary["date_end"] = now()
        summary["elapsed_s"] = round(time.time() - t0, 2)
        save_json(OUTS, summary)
        print("=" * 84)
        print(f"Task 40 done | status={summary['status']} | elapsed={summary['elapsed_s']}s")
        print(f"summary: {OUTS}")
        print("=" * 84)


if __name__ == "__main__":
    main()
