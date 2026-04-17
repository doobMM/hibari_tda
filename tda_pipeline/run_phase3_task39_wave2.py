"""
Phase 3 Task 39 (Wave 2) runner
================================

Runs T39-2 ~ T39-5 in one Python session with:
  - metric='dft'
  - alpha=0.25
  - octave_weight=0.3
  - duration_weight=1.0
  - min_onset_gap=0
  - post_bugfix=True

Outputs:
  - docs/step3_data/solari_dft_gap0_results.json
  - docs/step3_data/classical_contrast_dft_gap0_results.json
  - docs/step3_data/temporal_reorder_fc_dft_gap0.json
  - docs/step3_data/temporal_reorder_lstm_dft_gap0.json
  - docs/step3_data/harmony_fc_dft_gap0.json
  - docs/step3_data/harmony_lstm_dft_gap0.json
  - docs/step3_data/phase3_task39_wave2_summary.json
"""

from __future__ import annotations

import json
import os
import random
import time
import traceback
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

try:
    import torch
except Exception:  # pragma: no cover - optional dependency guard
    torch = None

from config import PipelineConfig
from eval_metrics import evaluate_generation
from generation import (
    MusicGeneratorFC,
    MusicGeneratorLSTM,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from musical_metrics import compute_hybrid_distance, compute_note_distance_matrix
from note_reassign import find_new_notes
from overlap import (
    build_activation_matrix,
    build_overlap_matrix,
    group_rBD_by_homology,
    label_cycles_from_persistence,
)
from preprocessing import simul_chord_lists, simul_union_by_dict
from run_any_track import preprocess as preprocess_any
from run_any_track import run_algo1 as run_algo1_generic
from run_note_reassign_unified import analyze_harmony, remap_music_notes
from run_solari import preprocess as preprocess_solari
from sequence_metrics import evaluate_sequence_metrics
from temporal_reorder import reorder_overlap_matrix
from topology import generate_barcode_numpy
from utils.result_meta import build_result_header
from weights import (
    compute_distance_matrix,
    compute_inter_weights,
    compute_inter_weights_decayed,
    compute_intra_weights,
    compute_out_of_reach,
)

import run_dft_gap0_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
SCRIPT_NAME = os.path.basename(__file__)

METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
POST_BUGFIX = True
RATE_STEP = 0.05
PH_THRESHOLD = 0.35

T39_2_N = 10
T39_3_N = 10
DL_EPOCHS = 50
DL_LR = 0.001
DL_BATCH = 32
SEED_BASE = 42


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)


def save_json(payload: dict[str, Any], filename: str) -> str:
    ensure_dirs()
    out_path = os.path.join(STEP3_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[saved] {out_path}")
    return out_path


def make_header(
    *,
    n_repeats: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = float(ALPHA)
    cfg.metric.octave_weight = float(OCTAVE_WEIGHT)
    cfg.metric.duration_weight = float(DURATION_WEIGHT)
    cfg.min_onset_gap = int(MIN_ONSET_GAP)
    cfg.post_bugfix = bool(POST_BUGFIX)
    return build_result_header(cfg, script_name=SCRIPT_NAME, n_repeats=n_repeats, extra=extra)


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def metric_distance_matrix(notes_label: dict, metric: str) -> np.ndarray | None:
    if metric == "frequency":
        return None
    kwargs: dict[str, float] = {}
    if metric in ("tonnetz", "dft"):
        kwargs["octave_weight"] = OCTAVE_WEIGHT
        kwargs["duration_weight"] = DURATION_WEIGHT
    elif metric == "voice_leading":
        kwargs["duration_weight"] = DURATION_WEIGHT
    return compute_note_distance_matrix(notes_label, metric=metric, **kwargs)


def compute_ph_generic(
    data: dict[str, Any],
    *,
    metric: str = METRIC,
    use_decayed: bool = False,
    rate_step: float = RATE_STEP,
    threshold: float = PH_THRESHOLD,
) -> dict[str, Any]:
    adn_i = data["adn_i"]
    notes_dict = data["notes_dict"]
    notes_label = data["notes_label"]
    n_notes = int(data["N"])
    total_length = int(data["T"])
    num_chords = int(data["num_chords"])

    musical_dist = metric_distance_matrix(notes_label, metric)

    if use_decayed:
        inter = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=num_chords)
    else:
        inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], num_chords=num_chords, lag=1)

    w1 = compute_intra_weights(adn_i[1][0], num_chords=num_chords)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=num_chords)
    intra = w1 + w2
    oor = compute_out_of_reach(inter, power=-2)

    profile: list[tuple[float, Any]] = []
    t0 = time.time()
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(
            tw, notes_dict, oor, num_notes=n_notes
        ).values
        final_dist = (
            compute_hybrid_distance(freq_dist, musical_dist, alpha=ALPHA)
            if musical_dist is not None
            else freq_dist
        )
        bd = generate_barcode_numpy(
            mat=final_dist,
            listOfDimension=[1],
            exactStep=True,
            birthDeathSimplex=False,
            sortDimension=False,
        )
        profile.append((r, bd))
        rate += rate_step

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    if not cycle_labeled:
        return {
            "cycle_labeled": None,
            "overlap_binary": None,
            "activation_continuous": None,
            "ph_time_s": float(time.time() - t0),
            "n_cycles": 0,
        }

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes = list(range(1, n_notes + 1))
    note_time = np.zeros((total_length, n_notes), dtype=int)
    for t in range(min(total_length, len(note_sets))):
        if note_sets[t] is None:
            continue
        for n in note_sets[t]:
            if 1 <= n <= n_notes:
                note_time[t, n - 1] = 1
    note_time_df = pd.DataFrame(note_time, columns=nodes)

    act_binary = build_activation_matrix(note_time_df, cycle_labeled, continuous=False)
    act_cont = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)
    overlap_binary = build_overlap_matrix(
        act_binary, cycle_labeled, threshold=threshold, total_length=total_length
    )

    return {
        "cycle_labeled": cycle_labeled,
        "overlap_binary": overlap_binary.values.astype(np.float32),
        "activation_continuous": act_cont.values.astype(np.float32),
        "ph_time_s": float(time.time() - t0),
        "n_cycles": int(len(cycle_labeled)),
    }


def run_algo1_trials(
    data: dict[str, Any],
    overlap_values: np.ndarray,
    cycle_labeled: dict[Any, Any],
    *,
    n_repeats: int,
    seed_base: int,
) -> list[dict[str, float]]:
    trials: list[dict[str, float]] = []
    for i in range(n_repeats):
        seed = seed_base + i
        gen = run_algo1_generic(data, overlap_values, cycle_labeled, seed=seed)
        metrics = evaluate_generation(
            gen,
            [data["inst1"], data["inst2"]],
            data["notes_label"],
            name="",
        )
        trials.append(
            {
                "seed": float(seed),
                "js": float(metrics["js_divergence"]),
                "cov": float(metrics["note_coverage"]),
            }
        )
    return trials


def summarize_algo1(
    trials: list[dict[str, float]],
    *,
    overlap_values: np.ndarray,
    n_cycles: int,
    ph_time_s: float,
) -> dict[str, float]:
    js = np.array([t["js"] for t in trials], dtype=float)
    cov = np.array([t["cov"] for t in trials], dtype=float)
    return {
        "n_cycles": int(n_cycles),
        "ph_time_s": round(float(ph_time_s), 2),
        "density": float((overlap_values > 0).mean()),
        "js_mean": float(js.mean()),
        "js_std": float(js.std(ddof=1) if len(js) > 1 else 0.0),
        "js_min": float(js.min()),
        "cov_mean": float(cov.mean()),
    }


def make_reorder_label(strategy_name: str, kwargs: dict[str, Any]) -> str:
    if not kwargs:
        return strategy_name
    suffix = "_".join(f"{k}{v}" for k, v in kwargs.items())
    return f"{strategy_name}_{suffix}"


def build_reorder_variants(base_overlap: np.ndarray) -> dict[str, dict[str, Any]]:
    variants: dict[str, dict[str, Any]] = {
        "baseline": {
            "overlap": base_overlap.astype(np.float32),
            "reorder_info": {"strategy": "baseline"},
        }
    }
    strategies = [
        ("segment_shuffle", {}),
        ("block_permute", {"block_size": 32}),
        ("markov_resample", {"temperature": 1.0}),
    ]
    for idx, (name, kwargs) in enumerate(strategies):
        label = make_reorder_label(name, kwargs)
        reordered, info = reorder_overlap_matrix(
            base_overlap, strategy=name, seed=SEED_BASE + idx * 17, **kwargs
        )
        variants[label] = {
            "overlap": reordered.astype(np.float32),
            "reorder_info": info,
        }
    return variants


def build_model(model_type: str, num_cycles: int, num_notes: int):
    if model_type == "fc":
        return MusicGeneratorFC(num_cycles, num_notes, hidden_dim=256, dropout=0.3)
    if model_type == "lstm":
        return MusicGeneratorLSTM(num_cycles, num_notes, hidden_dim=128, num_layers=2, dropout=0.3)
    raise ValueError(f"Unsupported model_type: {model_type}")


def fit_model(
    *,
    model_type: str,
    x_input: np.ndarray,
    y_target: np.ndarray,
    num_notes: int,
    seq_len: int,
    seed: int,
) -> tuple[Any, float]:
    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않습니다.")

    set_all_seeds(seed)
    x_train, x_valid, y_train, y_valid = train_test_split(
        x_input, y_target, test_size=0.2, random_state=seed
    )
    model = build_model(model_type, x_input.shape[1], num_notes)
    history = train_model(
        model,
        x_train,
        y_train,
        x_valid,
        y_valid,
        epochs=DL_EPOCHS,
        lr=DL_LR,
        batch_size=DL_BATCH,
        model_type=model_type,
        seq_len=seq_len,
    )
    val_loss = float(history[-1]["val_loss"])
    return model, val_loss


def eval_model_vs_original(
    *,
    model: Any,
    model_type: str,
    overlap_values: np.ndarray,
    notes_label: dict[tuple[int, int], int],
    original_notes: list[tuple[int, int, int]],
    name: str,
) -> dict[str, Any]:
    gen = generate_from_model(
        model,
        overlap_values,
        notes_label,
        model_type=model_type,
        adaptive_threshold=True,
        min_onset_gap=MIN_ONSET_GAP,
    )
    if not gen:
        return {"error": "no notes generated"}
    seq = evaluate_sequence_metrics(gen, original_notes, name=name)
    return {
        "n_notes": int(len(gen)),
        "pitch_js": float(seq["pitch_js"]),
        "transition_js": float(seq["transition_js"]),
        "dtw": float(seq["dtw"]),
        "ncd": float(seq["ncd"]),
    }


def eval_model_harmony(
    *,
    model: Any,
    model_type: str,
    overlap_values: np.ndarray,
    notes_label: dict[tuple[int, int], int],
    original_notes: list[tuple[int, int, int]],
    ref_notes: list[tuple[int, int, int]],
    name: str,
) -> dict[str, Any]:
    gen = generate_from_model(
        model,
        overlap_values,
        notes_label,
        model_type=model_type,
        adaptive_threshold=True,
        min_onset_gap=MIN_ONSET_GAP,
    )
    if not gen:
        return {"error": "no notes generated"}
    seq_orig = evaluate_sequence_metrics(gen, original_notes, name=f"{name}_vs_orig")
    seq_ref = evaluate_sequence_metrics(gen, ref_notes, name=f"{name}_vs_ref")
    return {
        "n_notes": int(len(gen)),
        "vs_original": {
            "pitch_js": float(seq_orig["pitch_js"]),
            "transition_js": float(seq_orig["transition_js"]),
            "dtw": float(seq_orig["dtw"]),
            "ncd": float(seq_orig["ncd"]),
        },
        "vs_ref": {
            "pitch_js": float(seq_ref["pitch_js"]),
            "transition_js": float(seq_ref["transition_js"]),
            "dtw": float(seq_ref["dtw"]),
            "ncd": float(seq_ref["ncd"]),
        },
    }


def task_t39_2_solari() -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print("T39-2 | solari DFT gap0 (Algorithm 1, N=10)")
    print("=" * 80)

    data = preprocess_solari()
    ph = compute_ph_generic(data, metric=METRIC, use_decayed=False)
    if ph["cycle_labeled"] is None:
        raise RuntimeError("solari DFT에서 cycle이 검출되지 않았습니다.")

    trials = run_algo1_trials(
        data,
        ph["overlap_binary"],
        ph["cycle_labeled"],
        n_repeats=T39_2_N,
        seed_base=9700,
    )
    a1_dft = summarize_algo1(
        trials,
        overlap_values=ph["overlap_binary"],
        n_cycles=ph["n_cycles"],
        ph_time_s=ph["ph_time_s"],
    )

    payload = {
        **make_header(n_repeats=T39_2_N, extra={"task": "T39-2", "song": "solari"}),
        "song": "solari",
        "N": int(data["N"]),
        "T": int(data["T"]),
        "num_chords": int(data["num_chords"]),
        "tempo": float(data["tempo"]),
        "a1_dft": a1_dft,
    }
    out = save_json(payload, "solari_dft_gap0_results.json")
    return out, {
        "js_mean": a1_dft["js_mean"],
        "js_std": a1_dft["js_std"],
        "K": a1_dft["n_cycles"],
    }


def run_track_dft_algo1(
    track_name: str,
    midi_file: str,
    *,
    n_repeats: int,
    use_decayed: bool,
) -> dict[str, Any]:
    data = preprocess_any(midi_file)
    ph = compute_ph_generic(data, metric=METRIC, use_decayed=use_decayed)
    if ph["cycle_labeled"] is None:
        raise RuntimeError(f"{track_name}: DFT에서 cycle이 검출되지 않았습니다.")

    trials = run_algo1_trials(
        data,
        ph["overlap_binary"],
        ph["cycle_labeled"],
        n_repeats=n_repeats,
        seed_base=9800,
    )
    summary = summarize_algo1(
        trials,
        overlap_values=ph["overlap_binary"],
        n_cycles=ph["n_cycles"],
        ph_time_s=ph["ph_time_s"],
    )
    summary["N"] = int(data["N"])
    summary["T"] = int(data["T"])
    summary["num_chords"] = int(data["num_chords"])
    return summary


def task_t39_3_classical() -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print("T39-3 | Bach + Ravel DFT gap0 (Algorithm 1, N=10)")
    print("=" * 80)

    # 기존 classical_contrast 패턴과 비교를 위해 run_any_track 스타일 전처리 사용
    use_decayed = True
    tracks = {
        "bach_fugue": "bach-toccata-and-fugue-in-d-minor-piano-solo.mid",
        "ravel_pavane": "maurice-ravel-pavane-pour-une-infante-defunte-m-19.mid",
    }

    results: dict[str, Any] = {}
    for name, midi in tracks.items():
        print(f"  - {name}: {midi}")
        results[name] = run_track_dft_algo1(
            name, midi, n_repeats=T39_3_N, use_decayed=use_decayed
        )
        print(
            f"    JS={results[name]['js_mean']:.4f} ± {results[name]['js_std']:.4f} "
            f"(K={results[name]['n_cycles']})"
        )

    payload = {
        **make_header(
            n_repeats=T39_3_N,
            extra={
                "task": "T39-3",
                "song": "bach_fugue+ravel_pavane",
                "use_decayed_inter": use_decayed,
            },
        ),
        "song": "bach_fugue+ravel_pavane",
        "bach_fugue": {
            "js_mean": results["bach_fugue"]["js_mean"],
            "js_std": results["bach_fugue"]["js_std"],
            "js_min": results["bach_fugue"]["js_min"],
            "cov_mean": results["bach_fugue"]["cov_mean"],
            "K": results["bach_fugue"]["n_cycles"],
            "ph_time_s": results["bach_fugue"]["ph_time_s"],
            "N": results["bach_fugue"]["N"],
            "T": results["bach_fugue"]["T"],
            "num_chords": results["bach_fugue"]["num_chords"],
        },
        "ravel_pavane": {
            "js_mean": results["ravel_pavane"]["js_mean"],
            "js_std": results["ravel_pavane"]["js_std"],
            "js_min": results["ravel_pavane"]["js_min"],
            "cov_mean": results["ravel_pavane"]["cov_mean"],
            "K": results["ravel_pavane"]["n_cycles"],
            "ph_time_s": results["ravel_pavane"]["ph_time_s"],
            "N": results["ravel_pavane"]["N"],
            "T": results["ravel_pavane"]["T"],
            "num_chords": results["ravel_pavane"]["num_chords"],
        },
    }
    out = save_json(payload, "classical_contrast_dft_gap0_results.json")
    return out, {
        "bach_js_mean": results["bach_fugue"]["js_mean"],
        "ravel_js_mean": results["ravel_pavane"]["js_mean"],
    }


def build_hibari_context() -> dict[str, Any]:
    data = suite.setup_hibari()
    bundle = suite.build_overlap_bundle(
        data,
        METRIC,
        alpha=ALPHA,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=PH_THRESHOLD,
    )
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    notes_label = data["notes_label"]
    n_notes = len(notes_label)
    total_length = int(data["T"])
    _, y_original = prepare_training_data(
        cont_overlap,
        [data["inst1_real"], data["inst2_real"]],
        notes_label,
        total_length,
        n_notes,
    )
    return {
        "data": data,
        "bundle": bundle,
        "cont_overlap": cont_overlap,
        "notes_label": notes_label,
        "y_original": y_original,
        "total_length": total_length,
        "n_notes": n_notes,
        "n_cycles": int(len(bundle["cycle_labeled"])),
        "original_notes": data["inst1_real"] + data["inst2_real"],
    }


def task_t39_4_temporal(context: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print("T39-4 | Temporal reorder (FC/LSTM) on DFT continuous OM")
    print("=" * 80)

    cont_overlap = context["cont_overlap"]
    y_original = context["y_original"]
    notes_label = context["notes_label"]
    original_notes = context["original_notes"]
    total_length = context["total_length"]
    n_notes = context["n_notes"]
    n_cycles = context["n_cycles"]

    variants = build_reorder_variants(cont_overlap)

    # FC: retrain X only
    fc_model, fc_val_loss = fit_model(
        model_type="fc",
        x_input=cont_overlap,
        y_target=y_original,
        num_notes=n_notes,
        seq_len=total_length,
        seed=SEED_BASE,
    )
    fc_experiments: dict[str, Any] = {}
    for label, item in variants.items():
        ev = eval_model_vs_original(
            model=fc_model,
            model_type="fc",
            overlap_values=item["overlap"],
            notes_label=notes_label,
            original_notes=original_notes,
            name=f"fc_{label}",
        )
        if "error" in ev:
            fc_experiments[label] = {"error": ev["error"], "val_loss": round(fc_val_loss, 4)}
            continue
        fc_experiments[label] = {
            "val_loss": round(fc_val_loss, 4),
            "n_notes": ev["n_notes"],
            "pitch_js": round(ev["pitch_js"], 6),
            "transition_js": round(ev["transition_js"], 6),
            "dtw": round(ev["dtw"], 6),
            "ncd": round(ev["ncd"], 6),
            "reorder_info": item["reorder_info"],
        }

    fc_payload = {
        **make_header(
            n_repeats=1,
            extra={"task": "T39-4", "model": "fc", "overlap_type": "continuous"},
        ),
        "track": "hibari",
        "metric": METRIC,
        "n_cycles": n_cycles,
        "T": total_length,
        "N": n_notes,
        "epochs": DL_EPOCHS,
        "experiments": fc_experiments,
    }
    out_fc = save_json(fc_payload, "temporal_reorder_fc_dft_gap0.json")

    # LSTM: retrain X / retrain O
    lstm_experiments: dict[str, Any] = {}

    # retrain X: baseline overlap으로 1회 학습 후 모든 재배치로 생성
    lstm_model_x, lstm_val_x = fit_model(
        model_type="lstm",
        x_input=cont_overlap,
        y_target=y_original,
        num_notes=n_notes,
        seq_len=total_length,
        seed=SEED_BASE + 100,
    )
    for label, item in variants.items():
        ev = eval_model_vs_original(
            model=lstm_model_x,
            model_type="lstm",
            overlap_values=item["overlap"],
            notes_label=notes_label,
            original_notes=original_notes,
            name=f"lstm_retrainX_{label}",
        )
        key = f"retrainX_{label}"
        if "error" in ev:
            lstm_experiments[key] = {"error": ev["error"], "val_loss": round(lstm_val_x, 4)}
            continue
        lstm_experiments[key] = {
            "val_loss": round(lstm_val_x, 4),
            "n_notes": ev["n_notes"],
            "pitch_js": round(ev["pitch_js"], 6),
            "transition_js": round(ev["transition_js"], 6),
            "dtw": round(ev["dtw"], 6),
            "ncd": round(ev["ncd"], 6),
            "reorder_info": item["reorder_info"],
        }

    # retrain O: 각 재배치 overlap 자체로 학습 + 생성
    for idx, (label, item) in enumerate(variants.items()):
        model_rt, val_rt = fit_model(
            model_type="lstm",
            x_input=item["overlap"],
            y_target=y_original,
            num_notes=n_notes,
            seq_len=total_length,
            seed=SEED_BASE + 200 + idx,
        )
        ev = eval_model_vs_original(
            model=model_rt,
            model_type="lstm",
            overlap_values=item["overlap"],
            notes_label=notes_label,
            original_notes=original_notes,
            name=f"lstm_retrainO_{label}",
        )
        key = f"retrainO_{label}"
        if "error" in ev:
            lstm_experiments[key] = {"error": ev["error"], "val_loss": round(val_rt, 4)}
            continue
        lstm_experiments[key] = {
            "val_loss": round(val_rt, 4),
            "n_notes": ev["n_notes"],
            "pitch_js": round(ev["pitch_js"], 6),
            "transition_js": round(ev["transition_js"], 6),
            "dtw": round(ev["dtw"], 6),
            "ncd": round(ev["ncd"], 6),
            "reorder_info": item["reorder_info"],
        }

    lstm_payload = {
        **make_header(
            n_repeats=1,
            extra={"task": "T39-4", "model": "lstm", "overlap_type": "continuous"},
        ),
        "track": "hibari",
        "metric": METRIC,
        "n_cycles": n_cycles,
        "T": total_length,
        "N": n_notes,
        "epochs": DL_EPOCHS,
        "experiments": lstm_experiments,
    }
    out_lstm = save_json(lstm_payload, "temporal_reorder_lstm_dft_gap0.json")

    return out_fc, out_lstm, {
        "fc_conditions": len(fc_experiments),
        "lstm_conditions": len(lstm_experiments),
        "n_cycles": n_cycles,
    }


def run_harmony_for_model(
    *,
    context: dict[str, Any],
    model_type: str,
) -> tuple[str, dict[str, Any]]:
    data = context["data"]
    cont_overlap = context["cont_overlap"]
    notes_label = context["notes_label"]
    y_original = context["y_original"]
    original_notes = context["original_notes"]
    total_length = context["total_length"]
    n_notes = context["n_notes"]
    cycle_labeled = context["bundle"]["cycle_labeled"]

    experiments: dict[str, Any] = {}

    # original
    model_orig, val_orig = fit_model(
        model_type=model_type,
        x_input=cont_overlap,
        y_target=y_original,
        num_notes=n_notes,
        seq_len=total_length,
        seed=SEED_BASE + (0 if model_type == "fc" else 1000),
    )
    ev_orig = eval_model_harmony(
        model=model_orig,
        model_type=model_type,
        overlap_values=cont_overlap,
        notes_label=notes_label,
        original_notes=original_notes,
        ref_notes=original_notes,
        name=f"{model_type}_original",
    )
    if "error" in ev_orig:
        experiments["original"] = {"error": ev_orig["error"], "val_loss": round(val_orig, 4)}
    else:
        experiments["original"] = {
            "val_loss": round(val_orig, 4),
            "n_notes": ev_orig["n_notes"],
            "vs_original": {k: round(v, 6) for k, v in ev_orig["vs_original"].items()},
            "vs_ref": {k: round(v, 6) for k, v in ev_orig["vs_ref"].items()},
        }

    harmony_cfgs = [
        ("baseline", {"harmony_mode": None}),
        ("scale_major", {"harmony_mode": "scale", "scale_type": "major"}),
        ("scale_penta", {"harmony_mode": "scale", "scale_type": "pentatonic"}),
    ]

    for idx, (name, kwargs) in enumerate(harmony_cfgs):
        print(f"  - {model_type}::{name}")
        pitch_range = (40, 88)
        try:
            reassign = find_new_notes(
                notes_label,
                cycle_labeled,
                seed=SEED_BASE,
                note_metric="tonnetz",
                pitch_range=pitch_range,
                n_candidates=1000,
                **kwargs,
            )
        except RuntimeError as e:
            # pentatonic 등에서 음역이 좁아 후보 수가 부족하면 범위를 확장해 재시도
            msg = str(e).lower()
            if "has only" not in msg and "too narrow" not in msg:
                raise
            pitch_range = (24, 108)
            reassign = find_new_notes(
                notes_label,
                cycle_labeled,
                seed=SEED_BASE,
                note_metric="tonnetz",
                pitch_range=pitch_range,
                n_candidates=1000,
                **kwargs,
            )
        new_notes_label = reassign["new_notes_label"]
        remapped = remap_music_notes(
            [data["inst1_real"], data["inst2_real"]],
            notes_label,
            new_notes_label,
        )
        remapped_flat = remapped[0] + remapped[1]
        n_new = len(new_notes_label)
        x_new, y_new = prepare_training_data(
            cont_overlap, remapped, new_notes_label, total_length, n_new
        )

        model_new, val_new = fit_model(
            model_type=model_type,
            x_input=x_new,
            y_target=y_new,
            num_notes=n_new,
            seq_len=total_length,
            seed=SEED_BASE + 10 + idx + (0 if model_type == "fc" else 1000),
        )
        ev = eval_model_harmony(
            model=model_new,
            model_type=model_type,
            overlap_values=cont_overlap,
            notes_label=new_notes_label,
            original_notes=original_notes,
            ref_notes=remapped_flat,
            name=f"{model_type}_{name}",
        )
        if "error" in ev:
            experiments[name] = {"error": ev["error"], "val_loss": round(val_new, 4)}
            continue

        harmony = analyze_harmony(notes_label, cycle_labeled, new_notes_label, reassign["new_notes"])
        cycle_dist_error = reassign.get("cycle_dist_error")
        experiments[name] = {
            "val_loss": round(val_new, 4),
            "n_notes": ev["n_notes"],
            "vs_original": {k: round(v, 6) for k, v in ev["vs_original"].items()},
            "vs_ref": {k: round(v, 6) for k, v in ev["vs_ref"].items()},
            "note_dist_error": round(float(reassign["note_dist_error"]), 4),
            "cycle_dist_error": (
                round(float(cycle_dist_error), 4) if cycle_dist_error is not None else None
            ),
            "pitch_range_used": list(pitch_range),
            "n_pitch_classes": int(harmony["n_pitch_classes"]),
            "best_scale_match": harmony["best_scale_name"],
        }

    payload = {
        **make_header(
            n_repeats=1,
            extra={
                "task": "T39-5",
                "model": model_type,
                "overlap_type": "continuous",
            },
        ),
        "track": "hibari",
        "metric": METRIC,
        "n_cycles": int(context["n_cycles"]),
        "T": int(total_length),
        "N": int(n_notes),
        "epochs": DL_EPOCHS,
        "experiments": experiments,
    }
    filename = f"harmony_{model_type}_dft_gap0.json"
    out = save_json(payload, filename)
    return out, {"conditions": len(experiments)}


def task_t39_5_harmony(context: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print("T39-5 | Harmony constraints (FC/LSTM) on DFT continuous OM")
    print("=" * 80)

    out_fc, info_fc = run_harmony_for_model(context=context, model_type="fc")
    out_lstm, info_lstm = run_harmony_for_model(context=context, model_type="lstm")
    return out_fc, out_lstm, {
        "fc_conditions": info_fc["conditions"],
        "lstm_conditions": info_lstm["conditions"],
    }


def main() -> None:
    ensure_dirs()
    t0 = time.time()
    summary: dict[str, Any] = {
        "script": SCRIPT_NAME,
        "date_start": now_iso(),
        "same_python_session": True,
        "status": "running",
        "config": {
            "metric": METRIC,
            "alpha": ALPHA,
            "octave_weight": OCTAVE_WEIGHT,
            "duration_weight": DURATION_WEIGHT,
            "min_onset_gap": MIN_ONSET_GAP,
            "post_bugfix": POST_BUGFIX,
        },
        "tasks": {},
        "outputs": {},
    }

    try:
        print("=" * 80)
        print("Task 39 Wave 2 start")
        print("=" * 80)

        out_t39_2, info_t39_2 = task_t39_2_solari()
        summary["outputs"]["T39-2"] = out_t39_2
        summary["tasks"]["T39-2"] = info_t39_2

        out_t39_3, info_t39_3 = task_t39_3_classical()
        summary["outputs"]["T39-3"] = out_t39_3
        summary["tasks"]["T39-3"] = info_t39_3

        hibari_ctx = build_hibari_context()
        summary["hibari_context"] = {
            "n_cycles": int(hibari_ctx["n_cycles"]),
            "T": int(hibari_ctx["total_length"]),
            "N": int(hibari_ctx["n_notes"]),
            "ph_time_s": float(hibari_ctx["bundle"]["ph_time_s"]),
        }

        out_t39_4_fc, out_t39_4_lstm, info_t39_4 = task_t39_4_temporal(hibari_ctx)
        summary["outputs"]["T39-4_fc"] = out_t39_4_fc
        summary["outputs"]["T39-4_lstm"] = out_t39_4_lstm
        summary["tasks"]["T39-4"] = info_t39_4

        out_t39_5_fc, out_t39_5_lstm, info_t39_5 = task_t39_5_harmony(hibari_ctx)
        summary["outputs"]["T39-5_fc"] = out_t39_5_fc
        summary["outputs"]["T39-5_lstm"] = out_t39_5_lstm
        summary["tasks"]["T39-5"] = info_t39_5

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
        summary["date_end"] = now_iso()
        summary["elapsed_s"] = round(time.time() - t0, 2)
        out_summary = save_json(summary, "phase3_task39_wave2_summary.json")
        print("=" * 80)
        print(f"Task39 Wave2 done. status={summary['status']}, elapsed={summary['elapsed_s']}s")
        print(f"summary: {out_summary}")
        print("=" * 80)


if __name__ == "__main__":
    main()
