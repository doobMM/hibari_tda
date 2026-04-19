"""
run_fc_cont_dft_alpha025.py
===========================

Task 51 — Algorithm 2 FC-cont DFT α=0.25 재실험.

배경:
- A-3에서 α=0.25 per-cycle τ가 Algo1 신기록 (0.01489 → 0.01156, -22.35%)
- 현재 Algo2 최저: FC-cont α=0.5, JS=0.000348±0.000149 (N=10, A9 기준)
- α=0.25(K=14)에서도 FC-cont 추가 개선되는지 검증

설정:
  metric=dft, alpha=0.25, ow=0.3, dw=1.0, gap_min=0
  OM: activation_continuous (K=14)
  모델: FC (hidden_dim=256, dropout=0.3)  ← A9와 동일 아키텍처
  N=10 (pilot) → Welch t-test 유의 시 N=20 확장 가능

캐시 재활용:
  cache/metric_dft_alpha0p25_ow0p3_dw1p0.pkl (K=14, shape 1088×14)

출력:
  docs/step3_data/fc_cont_dft_alpha025_results.json
"""

from __future__ import annotations

import json
import os
import pickle
import random
import time
from datetime import datetime

import numpy as np
from scipy import stats

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
MIDI_FILE = os.path.join(BASE_DIR, "Ryuichi_Sakamoto_-_hibari.mid")

ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
N_TRIALS = 10
SEED_BASE = 6000
SEED_STEP = 37

# α=0.5 A9 FC-cont baseline (soft_activation_dft_gap0_results.json)
ALPHA05_FC_CONT_MEAN = 0.00034788699141400525
ALPHA05_FC_CONT_STD = 0.00014861920005811188
ALPHA05_FC_CONT_N = 10
ALPHA05_FC_CONT_JS = [
    # extracted from soft_activation_dft_gap0_results.json FC continuous trials
]


def set_all_seeds(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def load_alpha025_cache():
    path = os.path.join(BASE_DIR, "cache", "metric_dft_alpha0p25_ow0p3_dw1p0.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def setup_hibari():
    from preprocessing import (
        build_chord_labels, build_note_labels, chord_to_note_labels,
        group_notes_with_duration, load_and_quantize, prepare_lag_sequences,
        simul_chord_lists, simul_union_by_dict, split_instruments,
    )
    from weights import compute_intra_weights

    TOTAL_LENGTH = 1088

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

    return {
        "notes_label": notes_label,
        "notes_counts": notes_counts,
        "notes_dict": notes_dict,
        "inst1_real": inst1_real,
        "inst2_real": inst2_real,
        "T": TOTAL_LENGTH,
    }


def run_fc_cont_trials(data: dict, cont_overlap: np.ndarray, cycle_labeled: dict,
                       n_trials: int, seed_base: int, seed_step: int) -> list[dict]:
    try:
        import torch
    except ImportError:
        raise RuntimeError("torch가 설치되어 있지 않습니다.")

    from generation import MusicGeneratorFC, generate_from_model, prepare_training_data, train_model
    from eval_metrics import evaluate_generation
    from sklearn.model_selection import train_test_split

    num_notes = len(data["notes_label"])
    num_cycles = cont_overlap.shape[1]

    X, y = prepare_training_data(
        cont_overlap.astype(np.float32),
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"], data["T"], num_notes
    )
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    trials = []
    for i in range(n_trials):
        seed = seed_base + i * seed_step
        set_all_seeds(seed)

        model = MusicGeneratorFC(
            num_cycles=num_cycles,
            num_notes=num_notes,
            hidden_dim=256,
            dropout=0.3,
        )
        t0 = time.time()
        history = train_model(
            model, X_train, y_train, X_val, y_val,
            epochs=200, lr=0.001, batch_size=32,
            model_type="fc", seq_len=data["T"]
        )
        generated = generate_from_model(
            model, cont_overlap, data["notes_label"],
            model_type="fc", adaptive_threshold=True,
            min_onset_gap=MIN_ONSET_GAP,
        )
        metrics = evaluate_generation(
            generated,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"],
            name="",
        )
        elapsed = time.time() - t0
        trial = {
            "seed": seed,
            "val_loss": float(history[-1]["val_loss"]),
            "js": float(metrics["js_divergence"]),
            "n_notes": int(len(generated)),
            "elapsed_s": float(elapsed),
        }
        trials.append(trial)
        print(f"[FC-cont trial {i+1}/{n_trials}] seed={seed} "
              f"val={trial['val_loss']:.4f} JS={trial['js']:.5f} notes={trial['n_notes']}")
    return trials


def welch_ttest(a_vals: list[float], b_vals: list[float],
                label_a: str, label_b: str) -> dict:
    a = np.array(a_vals, dtype=float)
    b = np.array(b_vals, dtype=float)
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    mean_a = float(a.mean())
    mean_b = float(b.mean())
    delta_pct = float(100 * (mean_b - mean_a) / mean_a) if mean_a != 0 else 0.0
    return {
        "label_a": label_a,
        "label_b": label_b,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "delta_pct_b_vs_a": delta_pct,
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "significant_p_lt_0_05": bool(p_value < 0.05),
    }


def main():
    print("=" * 72)
    print(f"Task 51 — FC-cont DFT α={ALPHA} 재실험 (N={N_TRIALS})")
    print("=" * 72)

    print("\n[1] hibari 데이터 로드...")
    data = setup_hibari()
    print(f"  notes_label: {len(data['notes_label'])}개, T={data['T']}")

    print("\n[2] α=0.25 캐시 로드...")
    cache = load_alpha025_cache()
    cont_overlap = cache["activation_continuous"].values.astype(np.float32)
    cycle_labeled = cache["cycle_labeled"]
    K = len(cycle_labeled)
    print(f"  K={K}, cont_overlap shape={cont_overlap.shape}")
    print(f"  alpha={cache['alpha']}, ow={cache['octave_weight']}, dw={cache['duration_weight']}")

    print(f"\n[3] FC-cont N={N_TRIALS} 학습...")
    t_start = time.time()
    trials = run_fc_cont_trials(
        data, cont_overlap, cycle_labeled,
        n_trials=N_TRIALS, seed_base=SEED_BASE, seed_step=SEED_STEP
    )
    total_elapsed = time.time() - t_start

    js_vals = np.array([t["js"] for t in trials], dtype=float)
    js_mean = float(js_vals.mean())
    js_std = float(js_vals.std(ddof=1)) if len(js_vals) > 1 else 0.0

    print(f"\n[4] 결과 집계")
    print(f"  α=0.25 FC-cont: JS={js_mean:.5f} ± {js_std:.5f} (N={N_TRIALS})")
    print(f"  α=0.5  FC-cont: JS={ALPHA05_FC_CONT_MEAN:.5f} ± {ALPHA05_FC_CONT_STD:.5f} (N={ALPHA05_FC_CONT_N})")

    # α=0.5 N=10 개별 JS 값 로드 (Welch t-test용)
    soft_path = os.path.join(STEP3_DIR, "soft_activation_dft_gap0_results.json")
    alpha05_js = []
    if os.path.exists(soft_path):
        with open(soft_path, "r", encoding="utf-8") as f:
            soft_data = json.load(f)
        alpha05_trials = soft_data.get("models", {}).get("FC", {}).get("continuous", {}).get("trials", [])
        alpha05_js = [t["js"] for t in alpha05_trials]

    welch = None
    if alpha05_js:
        welch = welch_ttest(alpha05_js, js_vals.tolist(), "FC_cont_alpha05", "FC_cont_alpha025")
        direction = "개선" if welch["delta_pct_b_vs_a"] < 0 else "악화"
        sig = "유의" if welch["significant_p_lt_0_05"] else "비유의"
        print(f"  Welch t-test: p={welch['p_value']:.2e} ({sig}), Δ={welch['delta_pct_b_vs_a']:+.1f}% ({direction})")

    delta_pct = 100 * (js_mean - ALPHA05_FC_CONT_MEAN) / ALPHA05_FC_CONT_MEAN
    if abs(delta_pct) < 5 or not (welch and welch["significant_p_lt_0_05"]):
        verdict = "동등"
    elif delta_pct < 0:
        verdict = "추가 개선"
    else:
        verdict = "열화"
    print(f"\n판정: {verdict} (Δ={delta_pct:+.1f}%)")

    result = {
        "task": "51",
        "metric": "dft",
        "alpha": ALPHA,
        "octave_weight": OCTAVE_WEIGHT,
        "duration_weight": DURATION_WEIGHT,
        "min_onset_gap": MIN_ONSET_GAP,
        "K": K,
        "model": "FC",
        "input": "activation_continuous",
        "hidden_dim": 256,
        "dropout": 0.3,
        "epochs": 200,
        "n_trials": N_TRIALS,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "script": os.path.basename(__file__),
        "post_bugfix": True,
        "FC_cont_alpha025": {
            "js_mean": js_mean,
            "js_std": js_std,
            "n_trials": N_TRIALS,
            "trials": trials,
            "total_elapsed_s": round(total_elapsed, 1),
        },
        "reference_alpha05": {
            "js_mean": ALPHA05_FC_CONT_MEAN,
            "js_std": ALPHA05_FC_CONT_STD,
            "n_trials": ALPHA05_FC_CONT_N,
            "source": "soft_activation_dft_gap0_results.json",
        },
        "comparison": {
            "delta_pct_alpha025_vs_alpha05": float(delta_pct),
            "verdict": verdict,
            "welch_test": welch,
        },
        "summary_table": {
            "alpha05_FC_cont": f"{ALPHA05_FC_CONT_MEAN:.5f} ± {ALPHA05_FC_CONT_STD:.5f}",
            "alpha025_FC_cont": f"{js_mean:.5f} ± {js_std:.5f}",
        },
    }

    out_path = os.path.join(STEP3_DIR, "fc_cont_dft_alpha025_results.json")
    os.makedirs(STEP3_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n저장: {out_path}")

    print("\n비교 표:")
    print(f"{'조건':<20} {'N':>4} {'JS mean±std':>22} {'vs α=0.5 p':>12} {'의미'}")
    print("-" * 70)
    print(f"{'α=0.5 FC-cont':<20} {ALPHA05_FC_CONT_N:>4} "
          f"{ALPHA05_FC_CONT_MEAN:.5f} ± {ALPHA05_FC_CONT_STD:.5f}   {'—':>12}   reference")
    p_str = f"{welch['p_value']:.2e}" if welch else "N/A"
    print(f"{'α=0.25 FC-cont':<20} {N_TRIALS:>4} {js_mean:.5f} ± {js_std:.5f}   {p_str:>12}   {verdict}")

    return result


if __name__ == "__main__":
    main()
