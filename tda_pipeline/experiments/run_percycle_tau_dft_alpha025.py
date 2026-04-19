"""
run_percycle_tau_dft_alpha025.py
================================

목표:
  - DFT hybrid alpha=0.25 (ow=0.3, dw=1.0, gap_min=0) 조건에서
    per-cycle tau_c를 1-pass greedy coordinate descent로 재탐색
  - 같은 조건의 대조군 2개와 N=20으로 비교
    (A) Binary OM, (B) tau=0.3 단일 이진화, (C) per-cycle tau_c
  - Welch t-test: (C) vs (A), (C) vs (B)

출력:
  docs/step3_data/percycle_tau_dft_alpha025_results.json
"""

from __future__ import annotations

import json
import os
import pickle
import time
from typing import Any

import numpy as np
from scipy import stats

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import run_dft_gap0_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0

N_REPEATS = 20
GREEDY_SEARCH_N = 5
TAU_CANDIDATES = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]

# seed 분리: 조건 간 독립 샘플 유지
SEED_BASE_BINARY = 51000
SEED_BASE_TAU03 = 52000
SEED_BASE_PERCYCLE = 53000
SEED_BASE_GREEDY = 54000

CACHE_NAME = "metric_dft_alpha0p25_ow0p3_dw1p0.pkl"
OUT_NAME = "percycle_tau_dft_alpha025_results.json"


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


def build_percycle_overlap(cont_overlap: np.ndarray, taus: list[float]) -> np.ndarray:
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus):
        out[:, ci] = (cont_overlap[:, ci] >= tau).astype(np.float32)
    return out


def run_algo1_eval(
    data: dict[str, Any],
    overlap_values: np.ndarray,
    cycle_labeled: dict[str, Any],
    n_repeats: int,
    seed_base: int,
) -> tuple[np.ndarray, float, float]:
    trials = suite.run_algo1_trials(
        data,
        overlap_values,
        cycle_labeled,
        n_repeats=n_repeats,
        seed_base=seed_base,
        min_onset_gap=MIN_ONSET_GAP,
    )
    js = np.array([t["js_divergence"] for t in trials], dtype=float)
    return js, float(js.mean()), float(js.std(ddof=1))


def bundle_is_valid(bundle: dict[str, Any]) -> bool:
    required = {"cycle_labeled", "overlap_binary", "activation_continuous"}
    if not required.issubset(bundle.keys()):
        return False
    k = len(bundle["cycle_labeled"])
    if k <= 0:
        return False
    ov = bundle["overlap_binary"]
    ac = bundle["activation_continuous"]
    try:
        ov_shape = ov.shape
        ac_shape = ac.shape
    except Exception:
        return False
    if len(ov_shape) != 2 or len(ac_shape) != 2:
        return False
    if ov_shape[1] != k or ac_shape[1] != k:
        return False
    return True


def load_or_build_alpha025_bundle(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cache_path = os.path.join(CACHE_DIR, CACHE_NAME)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        if bundle_is_valid(cached):
            meta = {
                "used_cache": True,
                "cache_path": cache_path,
                "cache_K": int(len(cached["cycle_labeled"])),
            }
            return cached, meta
        print(f"[warn] cache invalid: {cache_path} -> rebuilding")

    print("[info] alpha=0.25 cache not found/invalid. Building PH bundle...")
    t0 = time.time()
    fresh = suite.build_overlap_bundle(
        data,
        METRIC,
        alpha=ALPHA,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=0.35,
    )
    bundle = {
        "metric": fresh["metric"],
        "alpha": float(fresh["alpha"]),
        "octave_weight": float(fresh["octave_weight"]),
        "duration_weight": float(fresh["duration_weight"]),
        "cycle_labeled": fresh["cycle_labeled"],
        "overlap_binary": fresh["overlap_binary"],
        "activation_continuous": fresh["activation_continuous"],
        "ph_time_s": float(fresh["ph_time_s"]),
    }
    with open(cache_path, "wb") as f:
        pickle.dump(bundle, f)
    meta = {
        "used_cache": False,
        "cache_path": cache_path,
        "build_elapsed_s": round(time.time() - t0, 2),
        "cache_K": int(len(bundle["cycle_labeled"])),
    }
    return bundle, meta


def greedy_percycle_tau(
    data: dict[str, Any],
    cont_overlap: np.ndarray,
    cycle_labeled: dict[str, Any],
) -> tuple[list[float], list[dict[str, Any]]]:
    k = cont_overlap.shape[1]
    taus = [0.35] * k
    logs: list[dict[str, Any]] = []

    # 1-pass coordinate descent: cycle 0 -> cycle K-1
    for ci in range(k):
        best_tau = taus[ci]
        best_mean = float("inf")
        for tj, tau in enumerate(TAU_CANDIDATES):
            cand = list(taus)
            cand[ci] = tau
            ov = build_percycle_overlap(cont_overlap, cand)
            js, _, _ = run_algo1_eval(
                data,
                ov,
                cycle_labeled,
                n_repeats=GREEDY_SEARCH_N,
                seed_base=SEED_BASE_GREEDY + ci * 1000 + tj * 100,
            )
            m = float(js.mean())
            if m < best_mean:
                best_mean = m
                best_tau = float(tau)

        taus[ci] = best_tau
        logs.append({"cycle_index": ci, "best_tau": best_tau, "search_js_mean": best_mean})
        print(f"  [greedy] cycle {ci+1:02d}/{k}: tau={best_tau:.2f}, mean={best_mean:.5f}")

    return taus, logs


def welch(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return {"t": float(t), "p": float(p)}


def main() -> None:
    os.chdir(BASE_DIR)
    ensure_dirs()

    print("=" * 72)
    print("Per-cycle tau @ DFT alpha=0.25 (N=20)")
    print("=" * 72)
    print(f"config: metric={METRIC}, alpha={ALPHA}, ow={OCTAVE_WEIGHT}, dw={DURATION_WEIGHT}, gap=0")
    print(f"tau candidates: {TAU_CANDIDATES}")

    data = suite.setup_hibari()
    bundle, cache_meta = load_or_build_alpha025_bundle(data)

    cycle_labeled = bundle["cycle_labeled"]
    binary_overlap = bundle["overlap_binary"].values.astype(np.float32)
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    k = int(len(cycle_labeled))
    print(f"K={k} cycles (cache_used={cache_meta['used_cache']})")

    # Baseline A: Binary OM (section 4.2 optimal baseline)
    js_bin, mean_bin, std_bin = run_algo1_eval(
        data, binary_overlap, cycle_labeled, n_repeats=N_REPEATS, seed_base=SEED_BASE_BINARY
    )
    print(f"[A] binary      : {mean_bin:.5f} ± {std_bin:.5f}")

    # Baseline B: uniform tau = 0.3
    tau03_overlap = (cont_overlap >= 0.3).astype(np.float32)
    js_tau03, mean_tau03, std_tau03 = run_algo1_eval(
        data, tau03_overlap, cycle_labeled, n_repeats=N_REPEATS, seed_base=SEED_BASE_TAU03
    )
    print(f"[B] tau=0.3     : {mean_tau03:.5f} ± {std_tau03:.5f}")

    # C: per-cycle tau (1-pass greedy)
    t0 = time.time()
    tau_profile, greedy_logs = greedy_percycle_tau(data, cont_overlap, cycle_labeled)
    greedy_s = round(time.time() - t0, 2)
    percycle_overlap = build_percycle_overlap(cont_overlap, tau_profile)
    js_pc, mean_pc, std_pc = run_algo1_eval(
        data, percycle_overlap, cycle_labeled, n_repeats=N_REPEATS, seed_base=SEED_BASE_PERCYCLE
    )
    print(f"[C] per-cycle    : {mean_pc:.5f} ± {std_pc:.5f}")

    tests = {
        "vs_binary": welch(js_pc, js_bin),
        "vs_tau03": welch(js_pc, js_tau03),
    }

    out = {
        "alpha": ALPHA,
        "K": k,
        "baselines": {
            "binary": {"js_mean": mean_bin, "js_std": std_bin, "N": N_REPEATS},
            "tau_0.3": {"js_mean": mean_tau03, "js_std": std_tau03, "N": N_REPEATS},
        },
        "percycle": {
            "js_mean": mean_pc,
            "js_std": std_pc,
            "N": N_REPEATS,
            "tau_profile": [float(t) for t in tau_profile],
        },
        "welch_tests": tests,
    }

    # 상세 메타/로그는 memory 문서에 기록하고 JSON은 요청 스키마를 유지한다.

    out_path = os.path.join(STEP3_DIR, OUT_NAME)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
