import argparse
import json
import os
import pickle
import random
import time
from datetime import datetime

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
MIN_ONSET_GAP = 0
DEFAULT_ALPHA = 0.5
DEFAULT_OCTAVE_WEIGHT = 0.3
DEFAULT_DURATION_WEIGHT = 1.0
DW_CANDIDATES = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]
OW_CANDIDATES = [0.1, 0.3, 0.5, 0.7, 1.0]
TAU_CANDIDATES = [0.3, 0.5, 0.7]
OVERLAP_CACHE = {}
SCRIPT_NAME = "run_dft_gap0_suite.py"


def ensure_step3_dir():
    os.makedirs(STEP3_DIR, exist_ok=True)


def set_all_seeds(seed):
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


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


def build_overlap_bundle(data, metric, alpha=DEFAULT_ALPHA,
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
                     min_onset_gap=MIN_ONSET_GAP):
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


def task25(data):
    print("\n" + "=" * 72)
    print("Task 25 — §4.1 거리 함수 비교 (gap_min=0, N=20)")
    print("=" * 72)

    results = {
        "n_repeats": 20,
        "min_onset_gap": MIN_ONSET_GAP,
        "post_bugfix": True,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": DEFAULT_OCTAVE_WEIGHT,
        "duration_weight": DEFAULT_DURATION_WEIGHT,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }
    for idx, metric in enumerate(["frequency", "tonnetz", "voice_leading", "dft"]):
        cache = load_metric_cache(metric)
        overlap_values = cache["overlap"].values if hasattr(cache["overlap"], "values") else cache["overlap"]
        cycle_labeled = cache["cycle_labeled"]
        print(f"\n[{metric}] K={len(cycle_labeled)}")
        trials = run_algo1_trials(data, overlap_values, cycle_labeled, 20, 1000 + idx * 100)
        summary = summarize_trials(trials)
        results[metric] = {
            "js_divergence": summary["js_divergence"],
            "coverage": summary["coverage"],
            "pitch_count": summary["pitch_count"],
            "n_notes": summary["n_notes"],
            "K": len(cycle_labeled),
            "alpha": cache.get("alpha"),
        }
        print(
            f"  JS={summary['js_divergence']['mean']:.4f} ± "
            f"{summary['js_divergence']['std']:.4f}"
        )

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

    out_path = os.path.join(STEP3_DIR, "step3_results_gap0.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    print(f"최적 metric: {best_metric}")
    return results


def task26(data):
    print("\n" + "=" * 72)
    print("Task 26 — §4.1b Duration Weight (DFT + gap_min=0, N=10)")
    print("=" * 72)

    results = {
        "metric": "dft",
        "n_repeats": 10,
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": DEFAULT_OCTAVE_WEIGHT,
        "duration_weight": DEFAULT_DURATION_WEIGHT,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }
    best_dw = None
    best_js = float("inf")

    for i, dw in enumerate(DW_CANDIDATES):
        bundle = build_overlap_bundle(
            data, "dft", alpha=DEFAULT_ALPHA,
            octave_weight=DEFAULT_OCTAVE_WEIGHT,
            duration_weight=dw,
            use_decayed=False,
        )
        overlap_values = bundle["overlap_binary"].values
        trials = run_algo1_trials(data, overlap_values, bundle["cycle_labeled"], 10, 2000 + i * 100)
        js_vals = [t["js_divergence"] for t in trials]
        mean = float(np.mean(js_vals))
        std = float(np.std(js_vals, ddof=1))
        results[str(dw)] = {
            "mean": mean,
            "std": std,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[w_d={dw}] JS={mean:.4f} ± {std:.4f} (K={len(bundle['cycle_labeled'])})")
        if mean < best_js:
            best_js = mean
            best_dw = dw

    results["best_dw"] = best_dw
    results["best_js"] = best_js

    out_path = os.path.join(STEP3_DIR, "dw_gridsearch_dft_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    print(f"최적 w_d: {best_dw}")
    return results


def read_best_dw():
    path = os.path.join(STEP3_DIR, "dw_gridsearch_dft_gap0_results.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["best_dw"]


def task27(data):
    print("\n" + "=" * 72)
    print("Task 27 — §4.1a Octave Weight (DFT + gap_min=0, N=10)")
    print("=" * 72)

    best_dw = read_best_dw()
    results = {
        "metric": "dft",
        "n_repeats": 10,
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "duration_weight": best_dw,
        "octave_weight": DEFAULT_OCTAVE_WEIGHT,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }
    best_ow = None
    best_js = float("inf")

    for i, ow in enumerate(OW_CANDIDATES):
        bundle = build_overlap_bundle(
            data, "dft", alpha=DEFAULT_ALPHA,
            octave_weight=ow,
            duration_weight=best_dw,
            use_decayed=False,
        )
        overlap_values = bundle["overlap_binary"].values
        trials = run_algo1_trials(data, overlap_values, bundle["cycle_labeled"], 10, 3000 + i * 100)
        js_vals = [t["js_divergence"] for t in trials]
        mean = float(np.mean(js_vals))
        std = float(np.std(js_vals, ddof=1))
        results[str(ow)] = {
            "mean": mean,
            "std": std,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[w_o={ow}] JS={mean:.4f} ± {std:.4f} (K={len(bundle['cycle_labeled'])})")
        if mean < best_js:
            best_js = mean
            best_ow = ow

    results["best_ow"] = best_ow
    results["best_js"] = best_js
    results["octave_weight"] = best_ow

    out_path = os.path.join(STEP3_DIR, "ow_gridsearch_dft_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    print(f"최적 w_o: {best_ow}")
    return results


def read_best_ow():
    path = os.path.join(STEP3_DIR, "ow_gridsearch_dft_gap0_results.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["best_ow"]


def task28a(data):
    print("\n" + "=" * 72)
    print("Task 28a — §4.1c 감쇄 Lag (gap_min=0, N=20)")
    print("=" * 72)

    results = {
        "n_repeats": 20,
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": DEFAULT_OCTAVE_WEIGHT,
        "duration_weight": DEFAULT_DURATION_WEIGHT,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }

    configs = [
        ("DFT_lag1", "dft", False),
        ("DFT_lag1to4", "dft", True),
        ("Tonnetz_lag1", "tonnetz", False),
        ("Tonnetz_lag1to4", "tonnetz", True),
    ]

    for i, (label, metric, use_decayed) in enumerate(configs):
        bundle = build_overlap_bundle(
            data, metric, alpha=DEFAULT_ALPHA,
            octave_weight=DEFAULT_OCTAVE_WEIGHT,
            duration_weight=DEFAULT_DURATION_WEIGHT,
            use_decayed=use_decayed,
        )
        trials = run_algo1_trials(
            data, bundle["overlap_binary"].values, bundle["cycle_labeled"],
            20, 4000 + i * 100
        )
        js_vals = [t["js_divergence"] for t in trials]
        results[label] = {
            "mean": float(np.mean(js_vals)),
            "std": float(np.std(js_vals, ddof=1)),
            "n": 20,
            "K": len(bundle["cycle_labeled"]),
            "ph_time_s": bundle["ph_time_s"],
        }
        print(f"[{label}] JS={results[label]['mean']:.4f} ± {results[label]['std']:.4f}")

    out_path = os.path.join(STEP3_DIR, "decayed_lag_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    return results


def task28(data):
    print("\n" + "=" * 72)
    print("Task 28 — §4.2 Continuous OM (DFT + gap_min=0, N=20)")
    print("=" * 72)

    best_dw = read_best_dw()
    best_ow = read_best_ow()
    bundle = build_overlap_bundle(
        data, "dft", alpha=DEFAULT_ALPHA,
        octave_weight=best_ow,
        duration_weight=best_dw,
        use_decayed=False,
    )

    results = {
        "n_repeats": 20,
        "metric": "dft",
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": best_ow,
        "duration_weight": best_dw,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }

    configs = [
        ("A_binary", bundle["overlap_binary"].values),
        ("B_continuous_direct", bundle["activation_continuous"].values.astype(np.float32)),
    ]
    for name, overlap_values in configs:
        trials = run_algo1_trials(data, overlap_values, bundle["cycle_labeled"], 20, 5000 if name == "A_binary" else 5100)
        summary = summarize_trials(trials)
        results[name] = {
            "js_divergence": summary["js_divergence"],
            "density": float((overlap_values > 0).mean()),
            "K": len(bundle["cycle_labeled"]),
        }
        print(
            f"[{name}] JS={summary['js_divergence']['mean']:.4f} ± "
            f"{summary['js_divergence']['std']:.4f}"
        )

    cont_values = bundle["activation_continuous"].values.astype(np.float32)
    for i, tau in enumerate(TAU_CANDIDATES):
        binarized = (cont_values >= tau).astype(np.float32)
        trials = run_algo1_trials(data, binarized, bundle["cycle_labeled"], 20, 5200 + i * 100)
        summary = summarize_trials(trials)
        key = f"C_tau_{tau}"
        results[key] = {
            "js_divergence": summary["js_divergence"],
            "density": float(binarized.mean()),
            "K": len(bundle["cycle_labeled"]),
        }
        print(
            f"[{key}] JS={summary['js_divergence']['mean']:.4f} ± "
            f"{summary['js_divergence']['std']:.4f}"
        )

    out_path = os.path.join(STEP3_DIR, "step3_continuous_dft_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    return results


def run_model_trials(data, overlap_matrix, model_name, model_class, model_kwargs,
                     model_type, n_trials=5, epochs=200, lr=0.001,
                     batch_size=32, min_onset_gap=MIN_ONSET_GAP):
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


def task29(data):
    print("\n" + "=" * 72)
    print("Task 29 — §4.3 DL 모델 비교 (DFT binary OM + gap_min=0, N=5)")
    print("=" * 72)

    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Task 29를 실행할 수 없습니다.")

    from generation import MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer

    best_dw = read_best_dw()
    best_ow = read_best_ow()
    bundle = build_overlap_bundle(
        data, "dft", alpha=DEFAULT_ALPHA,
        octave_weight=best_ow,
        duration_weight=best_dw,
        use_decayed=False,
    )
    overlap_matrix = bundle["overlap_binary"].values.astype(np.float32)
    num_cycles = overlap_matrix.shape[1]
    num_notes = len(data["notes_label"])

    results = {
        "metric": "dft",
        "input": "binary_overlap",
        "n_repeats": 5,
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": best_ow,
        "duration_weight": best_dw,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }

    results["FC"] = run_model_trials(
        data, overlap_matrix, "FC",
        MusicGeneratorFC,
        {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 256, "dropout": 0.3},
        "fc", n_trials=5, epochs=200, lr=0.001, batch_size=32,
    )
    results["LSTM"] = run_model_trials(
        data, overlap_matrix, "LSTM",
        MusicGeneratorLSTM,
        {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 128, "num_layers": 2, "dropout": 0.3},
        "lstm", n_trials=5, epochs=200, lr=0.001, batch_size=32,
    )
    results["Transformer"] = run_model_trials(
        data, overlap_matrix, "Transformer",
        MusicGeneratorTransformer,
        {"num_cycles": num_cycles, "num_notes": num_notes, "d_model": 128, "nhead": 4, "num_layers": 2, "dropout": 0.1, "max_len": data["T"]},
        "transformer", n_trials=5, epochs=200, lr=0.001, batch_size=32,
    )

    out_path = os.path.join(STEP3_DIR, "dl_comparison_dft_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    return results


def task30(data):
    print("\n" + "=" * 72)
    print("Task 30 — §4.3a FC-bin vs FC-cont (DFT + gap_min=0, N=5)")
    print("=" * 72)

    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Task 30을 실행할 수 없습니다.")

    from generation import MusicGeneratorFC

    best_dw = read_best_dw()
    best_ow = read_best_ow()
    bundle = build_overlap_bundle(
        data, "dft", alpha=DEFAULT_ALPHA,
        octave_weight=best_ow,
        duration_weight=best_dw,
        use_decayed=False,
    )

    results = {
        "metric": "dft",
        "n_repeats": 5,
        "min_onset_gap": MIN_ONSET_GAP,
        "alpha": DEFAULT_ALPHA,
        "octave_weight": best_ow,
        "duration_weight": best_dw,
        "post_bugfix": True,
        "date": now_iso(),
        "script": SCRIPT_NAME,
    }

    binary_overlap = bundle["overlap_binary"].values.astype(np.float32)
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    num_cycles = binary_overlap.shape[1]
    num_notes = len(data["notes_label"])
    kwargs = {"num_cycles": num_cycles, "num_notes": num_notes, "hidden_dim": 128, "dropout": 0.3}

    results["FC_bin"] = run_model_trials(
        data, binary_overlap, "FC_bin",
        MusicGeneratorFC, kwargs, "fc",
        n_trials=5, epochs=200, lr=0.001, batch_size=32,
    )
    results["FC_cont"] = run_model_trials(
        data, cont_overlap, "FC_cont",
        MusicGeneratorFC, kwargs, "fc",
        n_trials=5, epochs=200, lr=0.001, batch_size=32,
    )

    out_path = os.path.join(STEP3_DIR, "fc_cont_dft_gap0_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {out_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="DFT + gap_min=0 Task 25~30 runner")
    parser.add_argument("--task", required=True, choices=["25", "26", "27", "28a", "28", "29", "30"])
    args = parser.parse_args()

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
    dispatch[args.task](data)


if __name__ == "__main__":
    main()
