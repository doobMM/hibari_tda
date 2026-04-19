"""
run_percycle_tau_dft_alpha_grid.py
==================================

목표:
  - DFT + gap=0 + (ow,dw)=(0.3,1.0) 고정 조건에서
    alpha grid 전체에 대해 per-cycle tau_c를 독립 탐색
  - alpha별 최적 per-cycle 성능(JS)을 N=20으로 비교
  - 5.8.1의 "alpha=0.25 최적" 주장 강화용 실험 산출물 생성

출력:
  docs/step3_data/percycle_tau_dft_gap0_alpha_grid_results.json
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
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

METRIC = "dft"
ALPHA_GRID = [0.0, 0.1, 0.25, 0.3, 0.5, 0.7, 1.0]
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0

N_REPEATS = 20
GREEDY_SEARCH_N = 5
TAU_CANDIDATES = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]

OUT_NAME = "percycle_tau_dft_gap0_alpha_grid_results.json"


@dataclass
class AlphaRun:
    alpha: float
    K: int
    ph_time_s: float
    tau_profile: list[float]
    js_trials: np.ndarray
    js_mean: float
    js_std: float
    density: float
    greedy_elapsed_s: float
    greedy_logs: list[dict[str, Any]]


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)


def build_percycle_overlap(cont_overlap: np.ndarray, taus: list[float]) -> np.ndarray:
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus):
        out[:, ci] = (cont_overlap[:, ci] >= tau).astype(np.float32)
    return out


def run_algo1_eval(
    data: dict[str, Any],
    overlap_values: np.ndarray,
    cycle_labeled: dict[Any, Any],
    *,
    n_repeats: int,
    seed_base: int,
) -> np.ndarray:
    trials = suite.run_algo1_trials(
        data,
        overlap_values,
        cycle_labeled,
        n_repeats=n_repeats,
        seed_base=seed_base,
        min_onset_gap=MIN_ONSET_GAP,
    )
    return np.array([t["js_divergence"] for t in trials], dtype=float)


def greedy_percycle_tau(
    data: dict[str, Any],
    cont_overlap: np.ndarray,
    cycle_labeled: dict[Any, Any],
    *,
    alpha: float,
    seed_base: int,
) -> tuple[list[float], list[dict[str, Any]], float]:
    k = cont_overlap.shape[1]
    taus = [0.35] * k
    logs: list[dict[str, Any]] = []
    t0 = time.time()

    for ci in range(k):
        best_tau = taus[ci]
        best_mean = float("inf")
        for tj, tau in enumerate(TAU_CANDIDATES):
            cand = list(taus)
            cand[ci] = tau
            ov = build_percycle_overlap(cont_overlap, cand)
            js = run_algo1_eval(
                data,
                ov,
                cycle_labeled,
                n_repeats=GREEDY_SEARCH_N,
                seed_base=seed_base + ci * 1000 + tj * 100,
            )
            m = float(js.mean())
            if m < best_mean:
                best_mean = m
                best_tau = float(tau)

        taus[ci] = best_tau
        logs.append(
            {
                "cycle_index": int(ci),
                "best_tau": float(best_tau),
                "search_js_mean": float(best_mean),
            }
        )
        print(
            f"    [alpha={alpha:>4.2f}] cycle {ci+1:02d}/{k:02d} -> "
            f"tau={best_tau:.2f}, search_js={best_mean:.5f}"
        )

    return taus, logs, round(time.time() - t0, 2)


def run_alpha(
    data: dict[str, Any],
    alpha: float,
    alpha_idx: int,
) -> AlphaRun:
    print("\n" + "-" * 72)
    print(f"[alpha={alpha}] bundle build")
    bundle = suite.build_overlap_bundle(
        data,
        METRIC,
        alpha=alpha,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=0.35,
    )

    cycle_labeled = bundle["cycle_labeled"]
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    k = int(len(cycle_labeled))
    print(f"  K={k}, ph_time={bundle['ph_time_s']}s")

    seed_offset = 100000 + alpha_idx * 10000
    taus, logs, greedy_elapsed = greedy_percycle_tau(
        data,
        cont_overlap,
        cycle_labeled,
        alpha=alpha,
        seed_base=seed_offset,
    )

    final_overlap = build_percycle_overlap(cont_overlap, taus)
    js = run_algo1_eval(
        data,
        final_overlap,
        cycle_labeled,
        n_repeats=N_REPEATS,
        seed_base=seed_offset + 5000,
    )
    js_mean = float(js.mean())
    js_std = float(js.std(ddof=1)) if len(js) > 1 else 0.0
    density = float((final_overlap > 0).mean())
    print(f"  -> per-cycle JS={js_mean:.5f} ± {js_std:.5f} (N={N_REPEATS})")

    return AlphaRun(
        alpha=float(alpha),
        K=k,
        ph_time_s=float(bundle["ph_time_s"]),
        tau_profile=[float(t) for t in taus],
        js_trials=js,
        js_mean=js_mean,
        js_std=js_std,
        density=density,
        greedy_elapsed_s=float(greedy_elapsed),
        greedy_logs=logs,
    )


def welch(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    mean_a = float(a.mean())
    mean_b = float(b.mean())
    delta_pct = float((mean_b - mean_a) / mean_a * 100.0) if mean_a != 0 else 0.0
    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "delta_pct_b_vs_a": delta_pct,
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "significant_p_lt_0_05": bool(p_value < 0.05),
    }


def main() -> None:
    os.chdir(BASE_DIR)
    ensure_dirs()

    print("=" * 72)
    print("Per-cycle tau alpha-grid experiment (DFT, gap=0)")
    print("=" * 72)
    print(
        f"config: metric={METRIC}, alpha_grid={ALPHA_GRID}, "
        f"ow={OCTAVE_WEIGHT}, dw={DURATION_WEIGHT}, gap={MIN_ONSET_GAP}"
    )
    print(
        f"N={N_REPEATS}, greedy_search_n={GREEDY_SEARCH_N}, "
        f"tau_candidates={TAU_CANDIDATES}"
    )

    data = suite.setup_hibari()
    runs: list[AlphaRun] = []
    t0 = time.time()

    for i, alpha in enumerate(ALPHA_GRID):
        runs.append(run_alpha(data, alpha, i))

    elapsed = round(time.time() - t0, 2)
    runs_sorted = sorted(runs, key=lambda r: r.js_mean)
    best = runs_sorted[0]

    by_alpha = {str(r.alpha): r for r in runs}
    alpha025 = by_alpha.get("0.25")
    alpha05 = by_alpha.get("0.5")

    pairwise_vs_best: dict[str, Any] = {}
    for r in runs:
        if r.alpha == best.alpha:
            continue
        pairwise_vs_best[str(r.alpha)] = welch(best.js_trials, r.js_trials)

    extra_tests: dict[str, Any] = {}
    if alpha025 is not None and alpha05 is not None:
        extra_tests["alpha_0.25_vs_0.5"] = welch(alpha025.js_trials, alpha05.js_trials)

    payload = {
        "script": os.path.basename(__file__),
        "date_start": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - elapsed)),
        "status": "completed",
        "config": {
            "metric": METRIC,
            "alpha_grid": ALPHA_GRID,
            "octave_weight": OCTAVE_WEIGHT,
            "duration_weight": DURATION_WEIGHT,
            "min_onset_gap": MIN_ONSET_GAP,
            "N_repeats": N_REPEATS,
            "greedy_search_n": GREEDY_SEARCH_N,
            "tau_candidates": TAU_CANDIDATES,
        },
        "results": [
            {
                "alpha": r.alpha,
                "K": r.K,
                "ph_time_s": r.ph_time_s,
                "greedy_elapsed_s": r.greedy_elapsed_s,
                "tau_profile": r.tau_profile,
                "js_mean": r.js_mean,
                "js_std": r.js_std,
                "density": r.density,
                "all_js": [float(x) for x in r.js_trials],
                "greedy_logs": r.greedy_logs,
            }
            for r in sorted(runs, key=lambda x: x.alpha)
        ],
        "ranking_by_js_mean": [
            {"rank": i + 1, "alpha": r.alpha, "js_mean": r.js_mean, "js_std": r.js_std, "K": r.K}
            for i, r in enumerate(runs_sorted)
        ],
        "best_alpha": best.alpha,
        "best_js_mean": best.js_mean,
        "best_js_std": best.js_std,
        "best_K": best.K,
        "pairwise_welch_vs_best": pairwise_vs_best,
        "extra_tests": extra_tests,
        "date_end": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": elapsed,
    }

    out_path = os.path.join(STEP3_DIR, OUT_NAME)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 72)
    print("Summary")
    print("=" * 72)
    for i, r in enumerate(runs_sorted, start=1):
        mark = "★" if r.alpha == best.alpha else " "
        print(f"{i:2d}. {mark} alpha={r.alpha:>4.2f} | JS={r.js_mean:.5f} ± {r.js_std:.5f} | K={r.K}")
    print(f"\nSaved: {out_path}")
    print(f"Elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
