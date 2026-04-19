"""
DFT + gap-min 파라미터화 Task 25~30 runner.

`run_dft_gap3_suite.py`의 리팩토링 버전 (세션 B, 2026-04-17).
기존의 `MIN_ONSET_GAP=3` 및 파일명의 `_gap3_` 하드코딩을 전부 argparse로 교체.

사용 예:

    # DFT baseline + gap_min=0 + N=20 (기본)
    python run_dft_suite.py --task 25

    # 기존 gap3 재현용
    python run_dft_suite.py --task 25 --gap-min 3

    # 한 번에 모든 task
    python run_dft_suite.py --task all --gap-min 0 --n-repeats 20

    # 다른 metric 실험
    python run_dft_suite.py --task 25 --metric tonnetz --alpha 0.0

옵션
  --task            실행할 task (25|26|27|28|28a|29|30|all)
  --gap-min N       Algorithm 1/2 min_onset_gap (기본 0)
  --n-repeats N     반복 수 (task25/28/28a 기준, 기본 20; 26/27은 10, 29/30은 5 고정)
  --metric M        거리 함수 (기본 'dft'; 현재 task25는 4개 metric 비교 고정)
  --alpha X         hybrid alpha (기본 0.5)
  --out-suffix STR  출력 파일 접미사 (기본 'gap{N}')

출력 JSON은 `docs/step3_data/*_{suffix}_results.json` 형식. `--out-suffix gap3`으로 실행하면
기존 gap3 결과와 같은 파일명으로 덮어쓰기 — 회귀 검증 용도.

**주의**: `run_dft_gap0_suite.py`(세션 A가 복사한 별도 스크립트)와는 무관.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from eval_metrics import evaluate_generation
from generation import (
    CycleSetManager,
    NodePool,
    algorithm1_optimized,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from musical_metrics import compute_hybrid_distance, compute_note_distance_matrix
from overlap import (
    build_activation_matrix,
    build_overlap_matrix,
    group_rBD_by_homology,
    label_cycles_from_persistence,
)
from preprocessing import (
    build_chord_labels,
    build_note_labels,
    chord_to_note_labels,
    group_notes_with_duration,
    load_and_quantize,
    prepare_lag_sequences,
    simul_chord_lists,
    simul_union_by_dict,
    split_instruments,
)
from topology import generate_barcode_numpy
from utils.result_meta import build_result_header
from weights import (
    compute_distance_matrix,
    compute_inter_weights,
    compute_inter_weights_decayed,
    compute_intra_weights,
    compute_out_of_reach,
)

try:
    import torch
except ImportError:
    torch = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
MIDI_FILE = os.path.join(BASE_DIR, "Ryuichi_Sakamoto_-_hibari.mid")
TOTAL_LENGTH = 1088
MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
           4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
INST_CHORD_HEIGHTS = MODULES * 33
DEFAULT_OCTAVE_WEIGHT = 0.3
DEFAULT_DURATION_WEIGHT = 0.3
DW_CANDIDATES = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]
OW_CANDIDATES = [0.1, 0.3, 0.5, 0.7, 1.0]
TAU_CANDIDATES = [0.3, 0.5, 0.7]
OVERLAP_CACHE: dict = {}


def ensure_step3_dir():
    os.makedirs(STEP3_DIR, exist_ok=True)


def set_all_seeds(seed):
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def setup_hibari():
    adjusted, _, boundaries = load_and_quantize(MIDI_FILE)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

    notes_label, notes_counts = build_note_labels(inst1_real[:59])
    module_active = group_notes_with_duration(inst1_real[:59])
    chord_map_module, _ = build_chord_labels(module_active)
    notes_dict = chord_to_note_labels(chord_map_module, notes_label)
    notes_dict["name"] = "notes"

    _, chord_seq1 = build_chord_labels(group_notes_with_duration(inst1_real))
    _, chord_seq2 = build_chord_labels(group_notes_with_duration(inst2_real))
    adn_i = prepare_lag_sequences(chord_seq1, chord_seq2, solo_timepoints=32, max_lag=4)

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])

    note_time_df = build_note_time_df(notes_dict, adn_i, len(notes_label), TOTAL_LENGTH)

    return {
        "notes_label": notes_label,
        "notes_counts": notes_counts,
        "notes_dict": notes_dict,
        "adn_i": adn_i,
        "intra": w1 + w2,
        "num_notes": len(notes_label),
        "num_chords": len(chord_map_module),
        "inst1_real": inst1_real,
        "inst2_real": inst2_real,
        "note_time_df": note_time_df,
        "T": TOTAL_LENGTH,
    }


def build_note_time_df(notes_dict, adn_i, num_notes, total_length):
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, num_notes + 1))
    node_to_idx = {node: idx for idx, node in enumerate(nodes_list)}
    note_time = np.zeros((total_length, len(nodes_list)), dtype=int)

    for t in range(min(total_length, len(note_sets))):
        if note_sets[t] is None:
            continue
        for node in note_sets[t]:
            idx = node_to_idx.get(node)
            if idx is not None:
                note_time[t, idx] = 1

    return pd.DataFrame(note_time, columns=nodes_list)


def load_metric_cache(metric):
    path = os.path.join(BASE_DIR, "cache", f"metric_{metric}.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def metric_distance_matrix(notes_label, metric, octave_weight, duration_weight):
    if metric == "frequency":
        return None
    kwargs = {}
    if metric in ("tonnetz", "dft"):
        kwargs["octave_weight"] = octave_weight
        kwargs["duration_weight"] = duration_weight
    elif metric == "voice_leading":
        kwargs["duration_weight"] = duration_weight
    return compute_note_distance_matrix(notes_label, metric=metric, **kwargs)


def build_overlap_bundle(data, metric, alpha,
                         octave_weight=DEFAULT_OCTAVE_WEIGHT,
                         duration_weight=DEFAULT_DURATION_WEIGHT,
                         use_decayed=False, threshold=0.35):
    key = (metric, alpha, octave_weight, duration_weight, use_decayed, threshold)
    if key in OVERLAP_CACHE:
        return OVERLAP_CACHE[key]

    if use_decayed:
        inter = compute_inter_weights_decayed(
            data["adn_i"], max_lag=4, num_chords=data["num_chords"]
        )
    else:
        inter = compute_inter_weights(
            data["adn_i"][1][1], data["adn_i"][2][1],
            num_chords=data["num_chords"], lag=1
        )

    oor = compute_out_of_reach(inter, power=-2)
    musical_dist = metric_distance_matrix(
        data["notes_label"], metric, octave_weight, duration_weight
    )

    profile = []
    rate = 0.0
    t0 = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        timeflow_w = data["intra"] + r * inter
        freq_dist = compute_distance_matrix(
            timeflow_w, data["notes_dict"], oor, num_notes=data["num_notes"]
        ).values
        if musical_dist is None:
            final_dist = freq_dist
        else:
            final_dist = compute_hybrid_distance(freq_dist, musical_dist, alpha=alpha)
        bd = generate_barcode_numpy(
            mat=final_dist, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    activation_binary = build_activation_matrix(
        data["note_time_df"], cycle_labeled, continuous=False
    )
    activation_continuous = build_activation_matrix(
        data["note_time_df"], cycle_labeled, continuous=True
    )
    overlap_binary = build_overlap_matrix(
        activation_binary, cycle_labeled, threshold=threshold,
        total_length=data["T"]
    )

    bundle = {
        "metric": metric,
        "alpha": alpha,
        "octave_weight": octave_weight,
        "duration_weight": duration_weight,
        "use_decayed": use_decayed,
        "cycle_labeled": cycle_labeled,
        "activation_binary": activation_binary,
        "activation_continuous": activation_continuous,
        "overlap_binary": overlap_binary,
        "ph_time_s": round(time.time() - t0, 1),
    }
    OVERLAP_CACHE[key] = bundle
    return bundle


def run_algo1_trials(data, overlap_values, cycle_labeled, n_repeats, seed_base,
                     min_onset_gap):
    trials = []
    for i in range(n_repeats):
        set_all_seeds(seed_base + i)
        pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        manager = CycleSetManager(cycle_labeled)
        generated = algorithm1_optimized(
            pool, INST_CHORD_HEIGHTS, overlap_values, manager,
            max_resample=50, verbose=False, min_onset_gap=min_onset_gap
        )
        metrics = evaluate_generation(
            generated,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"],
            name="",
        )
        trials.append(metrics)
    return trials


def summarize_trials(trials):
    js_vals = [t["js_divergence"] for t in trials]
    cov_vals = [t["note_coverage"] for t in trials]
    pitch_vals = [t["pitch_count"] for t in trials]
    note_vals = [t["n_notes"] for t in trials]
    return {
        "js_divergence": {
            "mean": float(np.mean(js_vals)),
            "std": float(np.std(js_vals, ddof=1) if len(js_vals) > 1 else 0.0),
        },
        "coverage": {
            "mean": float(np.mean(cov_vals)),
            "std": float(np.std(cov_vals, ddof=1) if len(cov_vals) > 1 else 0.0),
        },
        "pitch_count": {
            "mean": float(np.mean(pitch_vals)),
            "std": float(np.std(pitch_vals, ddof=1) if len(pitch_vals) > 1 else 0.0),
        },
        "n_notes": {
            "mean": float(np.mean(note_vals)),
            "std": float(np.std(note_vals, ddof=1) if len(note_vals) > 1 else 0.0),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Task 함수들 (gap_min·suffix·n_repeats 파라미터화)
# ═══════════════════════════════════════════════════════════════════════════

def task25(data, opts):
    suffix = opts.out_suffix
    n = opts.n_repeats
    print(f"\n{'=' * 72}\nTask 25 — §4.1 거리 함수 비교 (gap_min={opts.gap_min}, N={n})\n{'=' * 72}")

    header = _header(opts, n_repeats=n, extra={"task": 25})
    results = dict(header)
    for idx, metric in enumerate(["frequency", "tonnetz", "voice_leading", "dft"]):
        cache = load_metric_cache(metric)
        overlap_values = cache["overlap"].values if hasattr(cache["overlap"], "values") else cache["overlap"]
        cycle_labeled = cache["cycle_labeled"]
        print(f"\n[{metric}] K={len(cycle_labeled)}")
        trials = run_algo1_trials(
            data, overlap_values, cycle_labeled, n,
            1000 + idx * 100, min_onset_gap=opts.gap_min,
        )
        summary = summarize_trials(trials)
        results[metric] = {
            "js_divergence": summary["js_divergence"],
            "coverage": summary["coverage"],
            "pitch_count": summary["pitch_count"],
            "n_notes": summary["n_notes"],
            "K": len(cycle_labeled),
            "alpha": cache.get("alpha"),
        }
        print(f"  JS={summary['js_divergence']['mean']:.4f} ± {summary['js_divergence']['std']:.4f}")

    freq_mean = results["frequency"]["js_divergence"]["mean"]
    for metric in ["tonnetz", "voice_leading", "dft"]:
        mean = results[metric]["js_divergence"]["mean"]
        results[metric]["improvement_vs_frequency_pct"] = float(100 * (freq_mean - mean) / freq_mean)

    best_metric = min(
        ["frequency", "tonnetz", "voice_leading", "dft"],
        key=lambda name: results[name]["js_divergence"]["mean"]
    )
    results["best_metric"] = best_metric
    results["gate_passed"] = best_metric == "dft"

    out_path = os.path.join(STEP3_DIR, f"step3_results_{suffix}.json")
    _save(results, out_path)
    print(f"최적 metric: {best_metric}")
    return results


def task26(data, opts):
    suffix = opts.out_suffix
    print(f"\n{'=' * 72}\nTask 26 — §4.1b Duration Weight (DFT + gap_min={opts.gap_min}, N=10)\n{'=' * 72}")

    header = _header(opts, n_repeats=10, extra={"task": 26})
    results = dict(header)
    best_dw = None
    best_js = float("inf")

    for i, dw in enumerate(DW_CANDIDATES):
        bundle = build_overlap_bundle(
            data, "dft", alpha=opts.alpha,
            octave_weight=DEFAULT_OCTAVE_WEIGHT,
            duration_weight=dw, use_decayed=False,
        )
        overlap_values = bundle["overlap_binary"].values
        trials = run_algo1_trials(
            data, overlap_values, bundle["cycle_labeled"], 10,
            2000 + i * 100, min_onset_gap=opts.gap_min,
        )
        js_vals = [t["js_divergence"] for t in trials]
        mean = float(np.mean(js_vals))
        std = float(np.std(js_vals, ddof=1))
        results[str(dw)] = {
            "mean": mean, "std": std,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[w_d={dw}] JS={mean:.4f} ± {std:.4f} (K={len(bundle['cycle_labeled'])})")
        if mean < best_js:
            best_js = mean
            best_dw = dw

    results["best_dw"] = best_dw
    results["best_js"] = best_js

    out_path = os.path.join(STEP3_DIR, f"dw_gridsearch_dft_{suffix}_results.json")
    _save(results, out_path)
    print(f"최적 w_d: {best_dw}")
    return results


def read_best_dw(suffix):
    # 새 이름 우선, 없으면 legacy 이름으로 fallback (gap3일 때)
    candidates = [
        f"dw_gridsearch_dft_{suffix}_results.json",
        "dw_gridsearch_dft_results.json",
    ]
    for fname in candidates:
        path = os.path.join(STEP3_DIR, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["best_dw"]
    raise FileNotFoundError(f"dw gridsearch 결과 없음. 후보: {candidates}")


def read_best_ow(suffix):
    candidates = [
        f"ow_gridsearch_dft_{suffix}_results.json",
        "ow_gridsearch_dft_results.json",
    ]
    for fname in candidates:
        path = os.path.join(STEP3_DIR, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["best_ow"]
    raise FileNotFoundError(f"ow gridsearch 결과 없음. 후보: {candidates}")


def task27(data, opts):
    suffix = opts.out_suffix
    print(f"\n{'=' * 72}\nTask 27 — §4.1a Octave Weight (DFT + gap_min={opts.gap_min}, N=10)\n{'=' * 72}")

    best_dw = read_best_dw(suffix)
    header = _header(opts, n_repeats=10, extra={"task": 27, "duration_weight": best_dw})
    # duration_weight override (header의 기본값 덮어쓰기)
    header["duration_weight"] = best_dw
    results = dict(header)
    best_ow = None
    best_js = float("inf")

    for i, ow in enumerate(OW_CANDIDATES):
        bundle = build_overlap_bundle(
            data, "dft", alpha=opts.alpha,
            octave_weight=ow, duration_weight=best_dw, use_decayed=False,
        )
        overlap_values = bundle["overlap_binary"].values
        trials = run_algo1_trials(
            data, overlap_values, bundle["cycle_labeled"], 10,
            3000 + i * 100, min_onset_gap=opts.gap_min,
        )
        js_vals = [t["js_divergence"] for t in trials]
        mean = float(np.mean(js_vals))
        std = float(np.std(js_vals, ddof=1))
        results[str(ow)] = {
            "mean": mean, "std": std,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[w_o={ow}] JS={mean:.4f} ± {std:.4f} (K={len(bundle['cycle_labeled'])})")
        if mean < best_js:
            best_js = mean
            best_ow = ow

    results["best_ow"] = best_ow
    results["best_js"] = best_js

    out_path = os.path.join(STEP3_DIR, f"ow_gridsearch_dft_{suffix}_results.json")
    _save(results, out_path)
    print(f"최적 w_o: {best_ow}")
    return results


def task28a(data, opts):
    suffix = opts.out_suffix
    n = opts.n_repeats
    print(f"\n{'=' * 72}\nTask 28a — §4.1c 감쇄 Lag (gap_min={opts.gap_min}, N={n})\n{'=' * 72}")

    header = _header(opts, n_repeats=n, extra={"task": "28a"})
    results = dict(header)

    configs = [
        ("DFT_lag1", "dft", False),
        ("DFT_lag1to4", "dft", True),
        ("Tonnetz_lag1", "tonnetz", False),
        ("Tonnetz_lag1to4", "tonnetz", True),
    ]

    for i, (label, metric, use_decayed) in enumerate(configs):
        bundle = build_overlap_bundle(
            data, metric, alpha=opts.alpha,
            octave_weight=DEFAULT_OCTAVE_WEIGHT,
            duration_weight=DEFAULT_DURATION_WEIGHT,
            use_decayed=use_decayed,
        )
        trials = run_algo1_trials(
            data, bundle["overlap_binary"].values, bundle["cycle_labeled"],
            n, 4000 + i * 100, min_onset_gap=opts.gap_min,
        )
        js_vals = [t["js_divergence"] for t in trials]
        results[label] = {
            "mean": float(np.mean(js_vals)),
            "std": float(np.std(js_vals, ddof=1)),
            "n": n,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[{label}] JS={results[label]['mean']:.4f} ± {results[label]['std']:.4f}")

    out_path = os.path.join(STEP3_DIR, f"decayed_lag_{suffix}_results.json")
    _save(results, out_path)
    return results


def task28(data, opts):
    suffix = opts.out_suffix
    n = opts.n_repeats
    print(f"\n{'=' * 72}\nTask 28 — §4.2 Continuous OM (DFT + gap_min={opts.gap_min}, N={n})\n{'=' * 72}")

    best_dw = read_best_dw(suffix)
    best_ow = read_best_ow(suffix)
    bundle = build_overlap_bundle(
        data, "dft", alpha=opts.alpha,
        octave_weight=best_ow, duration_weight=best_dw, use_decayed=False,
    )

    header = _header(opts, n_repeats=n, extra={"task": 28})
    header["octave_weight"] = best_ow
    header["duration_weight"] = best_dw
    results = dict(header)

    configs = [
        ("A_binary", bundle["overlap_binary"].values),
        ("B_continuous_direct", bundle["activation_continuous"].values.astype(np.float32)),
    ]
    for name, overlap_values in configs:
        trials = run_algo1_trials(
            data, overlap_values, bundle["cycle_labeled"],
            n, 5000 if name == "A_binary" else 5100,
            min_onset_gap=opts.gap_min,
        )
        summary = summarize_trials(trials)
        results[name] = {
            "js_divergence": summary["js_divergence"],
            "density": float((overlap_values > 0).mean()),
            "K": len(bundle["cycle_labeled"]),
        }
        print(f"[{name}] JS={summary['js_divergence']['mean']:.4f} ± {summary['js_divergence']['std']:.4f}")

    cont_values = bundle["activation_continuous"].values.astype(np.float32)
    for i, tau in enumerate(TAU_CANDIDATES):
        binarized = (cont_values >= tau).astype(np.float32)
        trials = run_algo1_trials(
            data, binarized, bundle["cycle_labeled"], n,
            5200 + i * 100, min_onset_gap=opts.gap_min,
        )
        summary = summarize_trials(trials)
        key = f"C_tau_{tau}"
        results[key] = {
            "js_divergence": summary["js_divergence"],
            "density": float(binarized.mean()),
            "K": len(bundle["cycle_labeled"]),
        }
        print(f"[{key}] JS={summary['js_divergence']['mean']:.4f} ± {summary['js_divergence']['std']:.4f}")

    out_path = os.path.join(STEP3_DIR, f"step3_continuous_dft_{suffix}_results.json")
    _save(results, out_path)
    return results


def run_model_trials(data, overlap_matrix, model_name, model_class, model_kwargs,
                     model_type, n_trials, epochs, lr, batch_size, min_onset_gap):
    from sklearn.model_selection import train_test_split

    num_notes = len(data["notes_label"])
    num_cycles = overlap_matrix.shape[1]
    X, y = prepare_training_data(
        overlap_matrix.astype(np.float32),
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"], data["T"], num_notes
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    trials = []
    for i in range(n_trials):
        seed = 6000 + i * 37
        set_all_seeds(seed)
        model = model_class(**model_kwargs)
        t0 = time.time()
        history = train_model(
            model, X_train, y_train, X_val, y_val,
            epochs=epochs, lr=lr, batch_size=batch_size,
            model_type=model_type, seq_len=data["T"]
        )
        generated = generate_from_model(
            model, overlap_matrix, data["notes_label"],
            model_type=model_type, adaptive_threshold=True,
            min_onset_gap=min_onset_gap,
        )
        metrics = evaluate_generation(
            generated,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"],
            name="",
        )
        trials.append({
            "seed": seed,
            "val_loss": float(history[-1]["val_loss"]),
            "js": float(metrics["js_divergence"]),
            "n_notes": int(len(generated)),
            "elapsed_s": float(time.time() - t0),
        })
        print(
            f"[{model_name} trial {i + 1}] val={trials[-1]['val_loss']:.4f} "
            f"JS={trials[-1]['js']:.4f} notes={trials[-1]['n_notes']}"
        )

    js_vals = np.array([t["js"] for t in trials], dtype=float)
    val_vals = np.array([t["val_loss"] for t in trials], dtype=float)
    return {
        "js_mean": float(js_vals.mean()),
        "js_std": float(js_vals.std(ddof=1) if len(js_vals) > 1 else 0.0),
        "val_loss_mean": float(val_vals.mean()),
        "val_loss_std": float(val_vals.std(ddof=1) if len(val_vals) > 1 else 0.0),
        "n_trials": n_trials,
        "trials": trials,
    }


def task29(data, opts):
    suffix = opts.out_suffix
    print(f"\n{'=' * 72}\nTask 29 — §4.3 DL 모델 비교 (DFT binary OM + gap_min={opts.gap_min}, N=5)\n{'=' * 72}")

    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Task 29를 실행할 수 없습니다.")

    from generation import MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer

    best_dw = read_best_dw(suffix)
    best_ow = read_best_ow(suffix)
    bundle = build_overlap_bundle(
        data, "dft", alpha=opts.alpha,
        octave_weight=best_ow, duration_weight=best_dw, use_decayed=False,
    )
    overlap_matrix = bundle["overlap_binary"].values.astype(np.float32)
    num_cycles = overlap_matrix.shape[1]
    num_notes = len(data["notes_label"])

    header = _header(opts, n_repeats=5, extra={"task": 29, "input": "binary_overlap"})
    header["octave_weight"] = best_ow
    header["duration_weight"] = best_dw
    results = dict(header)

    results["FC"] = run_model_trials(
        data, overlap_matrix, "FC", MusicGeneratorFC,
        {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 256, "dropout": 0.3},
        "fc", n_trials=5, epochs=200, lr=0.001, batch_size=32,
        min_onset_gap=opts.gap_min,
    )
    results["LSTM"] = run_model_trials(
        data, overlap_matrix, "LSTM", MusicGeneratorLSTM,
        {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 128, "num_layers": 2, "dropout": 0.3},
        "lstm", n_trials=5, epochs=200, lr=0.001, batch_size=32,
        min_onset_gap=opts.gap_min,
    )
    results["Transformer"] = run_model_trials(
        data, overlap_matrix, "Transformer", MusicGeneratorTransformer,
        {"num_cycles": num_cycles, "num_notes": num_notes, "d_model": 128, "nhead": 4, "num_layers": 2, "dropout": 0.1, "max_len": data["T"]},
        "transformer", n_trials=5, epochs=200, lr=0.001, batch_size=32,
        min_onset_gap=opts.gap_min,
    )

    out_path = os.path.join(STEP3_DIR, f"dl_comparison_dft_{suffix}_results.json")
    _save(results, out_path)
    return results


def task30(data, opts):
    suffix = opts.out_suffix
    print(f"\n{'=' * 72}\nTask 30 — §4.3a FC-bin vs FC-cont (DFT + gap_min={opts.gap_min}, N=5)\n{'=' * 72}")

    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Task 30을 실행할 수 없습니다.")

    from generation import MusicGeneratorFC

    best_dw = read_best_dw(suffix)
    best_ow = read_best_ow(suffix)
    bundle = build_overlap_bundle(
        data, "dft", alpha=opts.alpha,
        octave_weight=best_ow, duration_weight=best_dw, use_decayed=False,
    )

    header = _header(opts, n_repeats=5, extra={"task": 30})
    header["octave_weight"] = best_ow
    header["duration_weight"] = best_dw
    results = dict(header)

    binary_overlap = bundle["overlap_binary"].values.astype(np.float32)
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    num_cycles = binary_overlap.shape[1]
    num_notes = len(data["notes_label"])
    kwargs = {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 128, "dropout": 0.3}

    results["FC_bin"] = run_model_trials(
        data, binary_overlap, "FC_bin", MusicGeneratorFC, kwargs, "fc",
        n_trials=5, epochs=200, lr=0.001, batch_size=32,
        min_onset_gap=opts.gap_min,
    )
    results["FC_cont"] = run_model_trials(
        data, cont_overlap, "FC_cont", MusicGeneratorFC, kwargs, "fc",
        n_trials=5, epochs=200, lr=0.001, batch_size=32,
        min_onset_gap=opts.gap_min,
    )

    out_path = os.path.join(STEP3_DIR, f"fc_cont_dft_{suffix}_results.json")
    _save(results, out_path)
    return results


# ═══════════════════════════════════════════════════════════════════════════
# 헬퍼
# ═══════════════════════════════════════════════════════════════════════════

def _header(opts, n_repeats, extra=None):
    """build_result_header 래퍼 — CLI 옵션 기반 즉석 PipelineConfig 조립."""
    from config import PipelineConfig
    cfg = PipelineConfig()
    cfg.metric.metric = opts.metric
    cfg.metric.alpha = opts.alpha
    cfg.metric.octave_weight = DEFAULT_OCTAVE_WEIGHT
    cfg.metric.duration_weight = DEFAULT_DURATION_WEIGHT
    cfg.min_onset_gap = opts.gap_min
    return build_result_header(
        cfg, script_name=__file__, n_repeats=n_repeats, extra=extra,
    )


def _save(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"저장: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True,
                        choices=["25", "26", "27", "28a", "28", "29", "30", "all"])
    parser.add_argument("--gap-min", type=int, default=0,
                        help="Algorithm 1/2 min_onset_gap (기본 0)")
    parser.add_argument("--n-repeats", type=int, default=20,
                        help="task25/28/28a 반복 수 (기본 20). task26/27/29/30은 내부 고정값")
    parser.add_argument("--metric", type=str, default="dft",
                        help="거리 함수 (기본 dft; task25는 4종 비교 고정)")
    parser.add_argument("--alpha", type=float, default=0.5, help="hybrid alpha")
    parser.add_argument("--out-suffix", type=str, default=None,
                        help="출력 suffix (기본 'gap{gap_min}')")
    args = parser.parse_args()

    if args.out_suffix is None:
        args.out_suffix = f"gap{args.gap_min}"

    ensure_step3_dir()
    data = setup_hibari()

    dispatch = {
        "25": task25,
        "26": task26,
        "27": task27,
        "28a": task28a,
        "28": task28,
        "29": task29,
        "30": task30,
    }

    if args.task == "all":
        for t in ["25", "26", "27", "28a", "28", "29", "30"]:
            try:
                dispatch[t](data, args)
            except Exception as e:
                print(f"[WARN] task {t} 실패: {e}")
    else:
        dispatch[args.task](data, args)


if __name__ == "__main__":
    main()
