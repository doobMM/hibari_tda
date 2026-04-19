"""
run_dft_phase2_gap0_suite.py
============================

세션 A Phase 2 (Task A8~A10) 전용 러너.
- min_onset_gap=0
- metric=dft
- octave_weight=0.3
- duration_weight=1.0
- post_bugfix=True

요구사항:
- A8~A10을 같은 Python 세션에서 직렬 수행
- 결과 JSON 메타 표준 준수
- phase2_a8_a10_gap0_serial_summary.json 저장
"""

from __future__ import annotations

import json
import os
import time
import traceback
from dataclasses import dataclass
from itertools import product
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from config import PipelineConfig
from pipeline import TDAMusicPipeline
from utils.result_meta import build_result_header

import run_dft_gap0_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
SCRIPT_NAME = os.path.basename(__file__)

MIN_ONSET_GAP = 0
DISTANCE_METRIC = "dft"
DEFAULT_ALPHA = 0.5
BEST_OW = 0.3
BEST_DW = 1.0
RATE_T = 0.3

A8_N_REPEATS = 20
A8_GREEDY_SEARCH_N = 5
A9_N_REPEATS = 10
A10A_N_REPEATS = 20
A10B_PILOT_N = 5
A10B_FINAL_N = 20
A10B_PILOT_GREEDY_SEARCH_N = 1
A10B_FINAL_GREEDY_SEARCH_N = 5

TAU_CANDIDATES = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]
ALPHA_GRID = [0.0, 0.1, 0.25, 0.3, 0.5, 0.7, 1.0]

TONNETZ_COMPLEX_ALGO1_BEST = 0.0183
TONNETZ_COMPLEX_ALGO2_FC_BEST = 0.0003


@dataclass
class TaskArtifacts:
    cycle_labeled: Dict
    binary_overlap: np.ndarray
    cont_overlap: np.ndarray


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def save_json(payload: dict, filename: str) -> str:
    os.makedirs(STEP3_DIR, exist_ok=True)
    out_path = os.path.join(STEP3_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"저장: {out_path}")
    return out_path


def make_header(
    *,
    alpha: float,
    n_repeats: int,
    extra: dict | None = None,
    metric: str = DISTANCE_METRIC,
    octave_weight: float = BEST_OW,
    duration_weight: float = BEST_DW,
) -> dict:
    cfg = PipelineConfig()
    cfg.metric.metric = metric
    cfg.metric.alpha = float(alpha)
    cfg.metric.octave_weight = float(octave_weight)
    cfg.metric.duration_weight = float(duration_weight)
    cfg.min_onset_gap = int(MIN_ONSET_GAP)
    cfg.post_bugfix = True
    return build_result_header(cfg, script_name=SCRIPT_NAME, n_repeats=n_repeats, extra=extra)


def overlap_density(overlap_values: np.ndarray) -> float:
    return float((overlap_values > 0).mean())


def run_algo1_eval(
    data: dict,
    overlap_values: np.ndarray,
    cycle_labeled: Dict,
    n_repeats: int,
    seed_base: int,
) -> Tuple[np.ndarray, dict]:
    trials = suite.run_algo1_trials(
        data,
        overlap_values,
        cycle_labeled,
        n_repeats,
        seed_base,
        min_onset_gap=MIN_ONSET_GAP,
    )
    summary = suite.summarize_trials(trials)
    js = np.array([t["js_divergence"] for t in trials], dtype=float)
    return js, summary


def build_percycle_overlap(cont_overlap: np.ndarray, taus: List[float]) -> np.ndarray:
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus):
        out[:, ci] = (cont_overlap[:, ci] >= tau).astype(np.float32)
    return out


def welch_ttest(a: np.ndarray, b: np.ndarray, label_a: str, label_b: str) -> dict:
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
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


def greedy_percycle_tau(
    data: dict,
    cont_overlap: np.ndarray,
    cycle_labeled: Dict,
    *,
    tau_candidates: List[float],
    n_search: int,
    seed_base: int,
) -> Tuple[List[float], List[dict]]:
    k = cont_overlap.shape[1]
    taus = [0.35] * k
    logs = []
    for ci in range(k):
        best_tau = taus[ci]
        best_js = float("inf")
        for tj, tau in enumerate(tau_candidates):
            candidate = list(taus)
            candidate[ci] = tau
            ov = build_percycle_overlap(cont_overlap, candidate)
            js_arr, _ = run_algo1_eval(
                data,
                ov,
                cycle_labeled,
                n_repeats=n_search,
                seed_base=seed_base + ci * 1000 + tj * 50,
            )
            js_mean = float(np.mean(js_arr))
            if js_mean < best_js:
                best_js = js_mean
                best_tau = tau
        taus[ci] = best_tau
        logs.append(
            {
                "cycle_index": ci,
                "best_tau": float(best_tau),
                "best_search_js": float(best_js),
            }
        )
        print(f"  [greedy] cycle {ci:02d}: tau={best_tau:.2f}, search_js={best_js:.4f}")
    return taus, logs


def task_a8(data: dict) -> Tuple[dict, TaskArtifacts, str]:
    print("\n" + "=" * 72)
    print("Task A8 — Per-cycle τ × DFT continuous OM (N=20)")
    print("=" * 72)

    bundle = suite.build_overlap_bundle(
        data,
        DISTANCE_METRIC,
        alpha=DEFAULT_ALPHA,
        octave_weight=BEST_OW,
        duration_weight=BEST_DW,
        use_decayed=False,
    )
    cycle_labeled = bundle["cycle_labeled"]
    binary_overlap = bundle["overlap_binary"].values.astype(np.float32)
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    uniform_tau_overlap = (cont_overlap >= 0.35).astype(np.float32)

    js_bin, sum_bin = run_algo1_eval(data, binary_overlap, cycle_labeled, A8_N_REPEATS, 11000)
    js_cont, sum_cont = run_algo1_eval(data, cont_overlap, cycle_labeled, A8_N_REPEATS, 12000)
    js_uni, sum_uni = run_algo1_eval(data, uniform_tau_overlap, cycle_labeled, A8_N_REPEATS, 13000)

    t0 = time.time()
    best_taus, search_logs = greedy_percycle_tau(
        data,
        cont_overlap,
        cycle_labeled,
        tau_candidates=TAU_CANDIDATES,
        n_search=A8_GREEDY_SEARCH_N,
        seed_base=14000,
    )
    greedy_elapsed = time.time() - t0

    percycle_overlap = build_percycle_overlap(cont_overlap, best_taus)
    js_pc, sum_pc = run_algo1_eval(data, percycle_overlap, cycle_labeled, A8_N_REPEATS, 15000)

    t_uni_vs_pc = welch_ttest(js_uni, js_pc, "uniform_tau_0.35", "percycle_tau")
    t_bin_vs_pc = welch_ttest(js_bin, js_pc, "binary_baseline", "percycle_tau")

    improvement_vs_uniform = float(100 * (np.mean(js_uni) - np.mean(js_pc)) / np.mean(js_uni))
    improvement_vs_binary = float(100 * (np.mean(js_bin) - np.mean(js_pc)) / np.mean(js_bin))

    header = make_header(
        alpha=DEFAULT_ALPHA,
        n_repeats=A8_N_REPEATS,
        extra={
            "task": "A8",
            "search_type": "timeflow",
            "tau_candidates": TAU_CANDIDATES,
            "greedy_search_n": A8_GREEDY_SEARCH_N,
        },
    )
    result = {
        **header,
        "K": int(len(cycle_labeled)),
        "ph_time_s": float(bundle["ph_time_s"]),
        "baseline_binary": {
            "js_divergence": sum_bin["js_divergence"],
            "density": overlap_density(binary_overlap),
            "all_js": [float(x) for x in js_bin],
        },
        "baseline_continuous_direct": {
            "js_divergence": sum_cont["js_divergence"],
            "density": overlap_density(cont_overlap),
            "all_js": [float(x) for x in js_cont],
        },
        "baseline_uniform_tau_0_35": {
            "js_divergence": sum_uni["js_divergence"],
            "density": overlap_density(uniform_tau_overlap),
            "all_js": [float(x) for x in js_uni],
        },
        "per_cycle_tau": {
            "best_taus": [float(t) for t in best_taus],
            "js_divergence": sum_pc["js_divergence"],
            "density": overlap_density(percycle_overlap),
            "all_js": [float(x) for x in js_pc],
            "improvement_vs_uniform_tau_pct": improvement_vs_uniform,
            "improvement_vs_binary_pct": improvement_vs_binary,
        },
        "welch_tests": {
            "uniform_tau_vs_percycle": t_uni_vs_pc,
            "binary_vs_percycle": t_bin_vs_pc,
        },
        "greedy": {
            "elapsed_s": round(float(greedy_elapsed), 2),
            "logs": search_logs,
        },
    }

    out = save_json(result, "percycle_tau_dft_gap0_results.json")
    artifacts = TaskArtifacts(cycle_labeled=cycle_labeled, binary_overlap=binary_overlap, cont_overlap=cont_overlap)
    return result, artifacts, out


def task_a9(data: dict, artifacts: TaskArtifacts) -> Tuple[dict, str]:
    print("\n" + "=" * 72)
    print("Task A9 — Soft activation × DL 아키텍처 (N=10 + Welch t-test)")
    print("=" * 72)

    if suite.torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Task A9를 실행할 수 없습니다.")

    from generation import MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer

    binary_overlap = artifacts.binary_overlap
    cont_overlap = artifacts.cont_overlap

    model_defs = {
        "FC": {
            "cls": MusicGeneratorFC,
            "kwargs": {
                "num_cycles": binary_overlap.shape[1],
                "num_notes": len(data["notes_label"]),
                "hidden_dim": 256,
                "dropout": 0.3,
            },
            "model_type": "fc",
        },
        "LSTM": {
            "cls": MusicGeneratorLSTM,
            "kwargs": {
                "num_cycles": binary_overlap.shape[1],
                "num_notes": len(data["notes_label"]),
                "hidden_dim": 128,
                "num_layers": 2,
                "dropout": 0.3,
            },
            "model_type": "lstm",
        },
        "Transformer": {
            "cls": MusicGeneratorTransformer,
            "kwargs": {
                "num_cycles": binary_overlap.shape[1],
                "num_notes": len(data["notes_label"]),
                "d_model": 128,
                "nhead": 4,
                "num_layers": 2,
                "dropout": 0.1,
                "max_len": data["T"],
            },
            "model_type": "transformer",
        },
    }

    results_models = {}
    js_arrays = {}
    for i, (name, spec) in enumerate(model_defs.items()):
        print(f"\n[{name}] binary")
        r_bin = suite.run_model_trials(
            data,
            binary_overlap,
            f"{name}_bin",
            spec["cls"],
            spec["kwargs"],
            spec["model_type"],
            n_trials=A9_N_REPEATS,
            epochs=200,
            lr=0.001,
            batch_size=32,
            min_onset_gap=MIN_ONSET_GAP,
        )
        print(f"\n[{name}] continuous")
        r_cont = suite.run_model_trials(
            data,
            cont_overlap,
            f"{name}_cont",
            spec["cls"],
            spec["kwargs"],
            spec["model_type"],
            n_trials=A9_N_REPEATS,
            epochs=200,
            lr=0.001,
            batch_size=32,
            min_onset_gap=MIN_ONSET_GAP,
        )
        js_bin = np.array([t["js"] for t in r_bin["trials"]], dtype=float)
        js_cont = np.array([t["js"] for t in r_cont["trials"]], dtype=float)
        improvement = float(100 * (js_bin.mean() - js_cont.mean()) / js_bin.mean())
        results_models[name] = {
            "binary": r_bin,
            "continuous": r_cont,
            "improvement_pct_binary_to_cont": improvement,
        }
        js_arrays[f"{name}_bin"] = js_bin
        js_arrays[f"{name}_cont"] = js_cont
        print(
            f"[{name}] binary={js_bin.mean():.4f}, cont={js_cont.mean():.4f}, "
            f"improvement={improvement:+.1f}%"
        )

    tests = {
        "FC_cont_vs_Transformer_cont": welch_ttest(
            js_arrays["FC_cont"], js_arrays["Transformer_cont"], "FC_cont", "Transformer_cont"
        ),
        "FC_cont_vs_FC_bin": welch_ttest(
            js_arrays["FC_bin"], js_arrays["FC_cont"], "FC_bin", "FC_cont"
        ),
        "Transformer_cont_vs_Transformer_bin": welch_ttest(
            js_arrays["Transformer_bin"], js_arrays["Transformer_cont"], "Transformer_bin", "Transformer_cont"
        ),
        "LSTM_cont_vs_LSTM_bin": welch_ttest(
            js_arrays["LSTM_bin"], js_arrays["LSTM_cont"], "LSTM_bin", "LSTM_cont"
        ),
    }

    fc_cont_mean = float(js_arrays["FC_cont"].mean())
    tr_cont_mean = float(js_arrays["Transformer_cont"].mean())
    fc_vs_tr = tests["FC_cont_vs_Transformer_cont"]
    if fc_vs_tr["significant_p_lt_0_05"] and fc_cont_mean < tr_cont_mean:
        algo2_plan = "fc_only"
    elif fc_vs_tr["significant_p_lt_0_05"] and tr_cont_mean < fc_cont_mean:
        algo2_plan = "transformer_primary_with_fc"
    else:
        algo2_plan = "fc_and_transformer"

    header = make_header(
        alpha=DEFAULT_ALPHA,
        n_repeats=A9_N_REPEATS,
        extra={
            "task": "A9",
            "input_modes": ["binary", "continuous"],
            "test_type": "Welch_t_test_equal_var_false",
            "algo2_plan_for_a10b": algo2_plan,
        },
    )
    result = {
        **header,
        "models": results_models,
        "welch_tests": tests,
        "a10b_algo2_plan": algo2_plan,
        "checks": {
            "continuous_beats_binary_by_model": {
                name: bool(results_models[name]["continuous"]["js_mean"] < results_models[name]["binary"]["js_mean"])
                for name in ["FC", "LSTM", "Transformer"]
            },
            "fc_cont_js_mean": fc_cont_mean,
            "transformer_cont_js_mean": tr_cont_mean,
        },
    }
    out = save_json(result, "soft_activation_dft_gap0_results.json")
    return result, out


def task_a10a(data: dict) -> Tuple[dict, str]:
    print("\n" + "=" * 72)
    print("Task A10-a — DFT α-hybrid grid (N=20)")
    print("=" * 72)

    rows = []
    for i, alpha in enumerate(ALPHA_GRID):
        print(f"[alpha={alpha}]")
        bundle = suite.build_overlap_bundle(
            data,
            DISTANCE_METRIC,
            alpha=alpha,
            octave_weight=BEST_OW,
            duration_weight=BEST_DW,
            use_decayed=False,
        )
        js_arr, summary = run_algo1_eval(
            data,
            bundle["overlap_binary"].values.astype(np.float32),
            bundle["cycle_labeled"],
            A10A_N_REPEATS,
            seed_base=21000 + i * 200,
        )
        row = {
            "alpha": float(alpha),
            "K": int(len(bundle["cycle_labeled"])),
            "ph_time_s": float(bundle["ph_time_s"]),
            "js_divergence": summary["js_divergence"],
            "density": overlap_density(bundle["overlap_binary"].values.astype(np.float32)),
            "all_js": [float(x) for x in js_arr],
        }
        rows.append(row)
        print(f"  JS={row['js_divergence']['mean']:.4f} ± {row['js_divergence']['std']:.4f}, K={row['K']}")

    best = min(rows, key=lambda r: r["js_divergence"]["mean"])
    header = make_header(
        alpha=float(best["alpha"]),
        n_repeats=A10A_N_REPEATS,
        extra={
            "task": "A10-a",
            "search_type": "timeflow",
            "alpha_grid": ALPHA_GRID,
        },
    )
    result = {
        **header,
        "grid_results": rows,
        "best_alpha": float(best["alpha"]),
        "best_js_mean": float(best["js_divergence"]["mean"]),
        "best_js_std": float(best["js_divergence"]["std"]),
        "best_K": int(best["K"]),
    }
    out = save_json(result, "alpha_grid_dft_gap0_results.json")
    return result, out


def build_complex_bundle(preproc_cache: dict, alpha: float, ow: float, dw: float, rc: float) -> dict:
    cfg = PipelineConfig()
    cfg.metric.metric = DISTANCE_METRIC
    cfg.metric.alpha = float(alpha)
    cfg.metric.octave_weight = float(ow)
    cfg.metric.duration_weight = float(dw)
    cfg.min_onset_gap = MIN_ONSET_GAP
    cfg.post_bugfix = True
    cfg.overlap.threshold = 0.35
    p = TDAMusicPipeline(cfg)
    p._cache.update(preproc_cache)
    t0 = time.time()
    p.run_homology_search(search_type="complex", lag=1, dimension=1, rate_t=RATE_T, rate_s=rc)
    p.run_overlap_construction(persistence_key="h1_complex_lag1")
    ph_elapsed = time.time() - t0
    cycle_labeled = p._cache["cycle_labeled"]
    cont_overlap = p._cache["activation_continuous"].values.astype(np.float32)
    return {
        "cycle_labeled": cycle_labeled,
        "cont_overlap": cont_overlap,
        "binary_overlap": p._cache["overlap_matrix"].values.astype(np.float32),
        "K": len(cycle_labeled),
        "ph_time_s": float(ph_elapsed),
    }


def make_eval_data_from_preproc(cache: dict) -> dict:
    return {
        "notes_label": cache["notes_label"],
        "notes_counts": cache["notes_counts"],
        "inst1_real": cache["inst1_real"],
        "inst2_real": cache["inst2_real"],
        "T": 1088,
    }


def task_a10b(best_alpha: float, a9_algo2_plan: str) -> Tuple[dict, str]:
    print("\n" + "=" * 72)
    print("Task A10-b — Complex × DFT-hybrid × per-cycle τ")
    print("=" * 72)

    base_cfg = PipelineConfig()
    base_cfg.min_onset_gap = MIN_ONSET_GAP
    base_pipe = TDAMusicPipeline(base_cfg)
    base_pipe.run_preprocessing()
    preproc_cache = dict(base_pipe._cache)
    eval_data = make_eval_data_from_preproc(preproc_cache)

    alpha_candidates = sorted(
        {
            round(max(0.0, min(1.0, best_alpha - 0.25)), 2),
            round(max(0.0, min(1.0, best_alpha)), 2),
            round(max(0.0, min(1.0, best_alpha + 0.25)), 2),
        }
    )
    ow_candidates = [0.0, BEST_OW]
    rc_candidates = [0.1, 0.3]

    pilot_rows = []
    bundle_cache = {}
    for idx, (alpha, ow, rc) in enumerate(product(alpha_candidates, ow_candidates, rc_candidates)):
        print(f"\n[pilot] alpha={alpha}, ow={ow}, dw={BEST_DW}, rc={rc}")
        b = build_complex_bundle(preproc_cache, alpha=alpha, ow=ow, dw=BEST_DW, rc=rc)
        if b["K"] == 0:
            print("  K=0 이라 스킵")
            continue
        key = (alpha, ow, rc)
        bundle_cache[key] = b
        best_taus, _ = greedy_percycle_tau(
            eval_data,
            b["cont_overlap"],
            b["cycle_labeled"],
            tau_candidates=TAU_CANDIDATES,
            n_search=A10B_PILOT_GREEDY_SEARCH_N,
            seed_base=31000 + idx * 5000,
        )
        ov_pc = build_percycle_overlap(b["cont_overlap"], best_taus)
        js_arr, summary = run_algo1_eval(
            eval_data,
            ov_pc,
            b["cycle_labeled"],
            A10B_PILOT_N,
            seed_base=32000 + idx * 200,
        )
        pilot_rows.append(
            {
                "alpha": float(alpha),
                "ow": float(ow),
                "dw": float(BEST_DW),
                "rc": float(rc),
                "K": int(b["K"]),
                "ph_time_s": float(b["ph_time_s"]),
                "greedy_search_n": A10B_PILOT_GREEDY_SEARCH_N,
                "algo1_n": A10B_PILOT_N,
                "algo1_js_mean": float(summary["js_divergence"]["mean"]),
                "algo1_js_std": float(summary["js_divergence"]["std"]),
                "algo1_all_js": [float(x) for x in js_arr],
                "best_taus": [float(t) for t in best_taus],
            }
        )
        print(
            f"  pilot Algo1 JS={summary['js_divergence']['mean']:.4f} ± "
            f"{summary['js_divergence']['std']:.4f}, K={b['K']}"
        )

    if not pilot_rows:
        raise RuntimeError("A10-b pilot 결과가 비어 있습니다.")

    best_pilot = min(pilot_rows, key=lambda r: r["algo1_js_mean"])
    selected_key = (best_pilot["alpha"], best_pilot["ow"], best_pilot["rc"])
    print(
        f"\n[A10-b 선택] alpha={best_pilot['alpha']}, ow={best_pilot['ow']}, "
        f"rc={best_pilot['rc']} (pilot mean={best_pilot['algo1_js_mean']:.4f})"
    )

    final_bundle = bundle_cache[selected_key]
    final_taus, final_greedy_logs = greedy_percycle_tau(
        eval_data,
        final_bundle["cont_overlap"],
        final_bundle["cycle_labeled"],
        tau_candidates=TAU_CANDIDATES,
        n_search=A10B_FINAL_GREEDY_SEARCH_N,
        seed_base=41000,
    )
    ov_uniform = (final_bundle["cont_overlap"] >= 0.35).astype(np.float32)
    ov_percycle = build_percycle_overlap(final_bundle["cont_overlap"], final_taus)

    js_uni, sum_uni = run_algo1_eval(
        eval_data, ov_uniform, final_bundle["cycle_labeled"], A10B_FINAL_N, seed_base=42000
    )
    js_pc, sum_pc = run_algo1_eval(
        eval_data, ov_percycle, final_bundle["cycle_labeled"], A10B_FINAL_N, seed_base=43000
    )
    t_uni_pc = welch_ttest(js_uni, js_pc, "uniform_tau_0.35", "percycle_tau")

    from generation import MusicGeneratorFC, MusicGeneratorTransformer

    algo2_models = []
    if a9_algo2_plan == "fc_only":
        algo2_models = ["FC"]
    elif a9_algo2_plan == "transformer_primary_with_fc":
        algo2_models = ["Transformer", "FC"]
    else:
        algo2_models = ["FC", "Transformer"]

    algo2_results = {}
    model_specs = {
        "FC": (
            MusicGeneratorFC,
            {
                "num_cycles": final_bundle["cont_overlap"].shape[1],
                "num_notes": len(eval_data["notes_label"]),
                "hidden_dim": 256,
                "dropout": 0.3,
            },
            "fc",
        ),
        "Transformer": (
            MusicGeneratorTransformer,
            {
                "num_cycles": final_bundle["cont_overlap"].shape[1],
                "num_notes": len(eval_data["notes_label"]),
                "d_model": 128,
                "nhead": 4,
                "num_layers": 2,
                "dropout": 0.1,
                "max_len": eval_data["T"],
            },
            "transformer",
        ),
    }

    for model_name in algo2_models:
        cls, kwargs, model_type = model_specs[model_name]
        print(f"\n[A10-b Algo2] {model_name} (continuous input)")
        algo2_results[model_name] = suite.run_model_trials(
            eval_data,
            final_bundle["cont_overlap"],
            f"A10b_{model_name}_cont",
            cls,
            kwargs,
            model_type,
            n_trials=5,
            epochs=200,
            lr=0.001,
            batch_size=32,
            min_onset_gap=MIN_ONSET_GAP,
        )

    best_algo2_js = None
    best_algo2_model = None
    for name, rr in algo2_results.items():
        if best_algo2_js is None or rr["js_mean"] < best_algo2_js:
            best_algo2_js = rr["js_mean"]
            best_algo2_model = name

    algo1_final_mean = float(sum_pc["js_divergence"]["mean"])
    delta_algo1_vs_tonnetz = float(
        100 * (algo1_final_mean - TONNETZ_COMPLEX_ALGO1_BEST) / TONNETZ_COMPLEX_ALGO1_BEST
    )

    delta_algo2_vs_tonnetz = None
    if best_algo2_js is not None:
        delta_algo2_vs_tonnetz = float(
            100 * (best_algo2_js - TONNETZ_COMPLEX_ALGO2_FC_BEST) / TONNETZ_COMPLEX_ALGO2_FC_BEST
        )

    header = make_header(
        alpha=float(best_pilot["alpha"]),
        n_repeats=A10B_FINAL_N,
        extra={
            "task": "A10-b",
            "search_type": "complex",
            "rate_t": RATE_T,
            "alpha_candidates": alpha_candidates,
            "ow_candidates": ow_candidates,
            "rc_candidates": rc_candidates,
            "algo2_plan_from_a9": a9_algo2_plan,
        },
        octave_weight=float(best_pilot["ow"]),
        duration_weight=BEST_DW,
    )
    result = {
        **header,
        "pilot_grid": {
            "algo1_n": A10B_PILOT_N,
            "rows": pilot_rows,
            "selected": best_pilot,
        },
        "final_revalidation": {
            "algo1_n": A10B_FINAL_N,
            "K": int(final_bundle["K"]),
            "uniform_tau_0_35": {
                "js_divergence": sum_uni["js_divergence"],
                "density": overlap_density(ov_uniform),
                "all_js": [float(x) for x in js_uni],
            },
            "per_cycle_tau": {
                "best_taus": [float(t) for t in final_taus],
                "js_divergence": sum_pc["js_divergence"],
                "density": overlap_density(ov_percycle),
                "all_js": [float(x) for x in js_pc],
                "improvement_vs_uniform_tau_pct": float(
                    100 * (np.mean(js_uni) - np.mean(js_pc)) / np.mean(js_uni)
                ),
            },
            "welch_uniform_vs_percycle": t_uni_pc,
            "greedy_search_n": A10B_FINAL_GREEDY_SEARCH_N,
            "greedy_logs": final_greedy_logs,
        },
        "algo2": {
            "executed_models": algo2_models,
            "results": algo2_results,
            "best_model": best_algo2_model,
            "best_js_mean": best_algo2_js,
        },
        "comparison_to_tonnetz_complex_best": {
            "tonnetz_algo1_best_js": TONNETZ_COMPLEX_ALGO1_BEST,
            "dft_algo1_best_js": algo1_final_mean,
            "delta_pct_dft_vs_tonnetz_algo1": delta_algo1_vs_tonnetz,
            "tonnetz_algo2_fc_best_js": TONNETZ_COMPLEX_ALGO2_FC_BEST,
            "dft_algo2_best_model": best_algo2_model,
            "dft_algo2_best_js": best_algo2_js,
            "delta_pct_dft_vs_tonnetz_algo2": delta_algo2_vs_tonnetz,
        },
    }
    out = save_json(result, "complex_percycle_dft_gap0_results.json")
    return result, out


def run_all_phase2() -> dict:
    os.chdir(BASE_DIR)
    os.makedirs(STEP3_DIR, exist_ok=True)

    summary = {
        "phase": "Phase 2",
        "tasks_requested": ["A8", "A9", "A10-a", "A10-b"],
        "started_at": now_iso(),
        "same_python_session": True,
        "script": SCRIPT_NAME,
        "status": "running",
        "tasks": {},
        "outputs": {},
    }
    summary_path = os.path.join(STEP3_DIR, "phase2_a8_a10_gap0_serial_summary.json")

    try:
        data = suite.setup_hibari()
        summary["notes_n"] = int(len(data["notes_label"]))

        t0 = time.time()
        a8, a8_artifacts, a8_out = task_a8(data)
        summary["tasks"]["A8"] = {"status": "done", "elapsed_s": round(time.time() - t0, 2)}
        summary["outputs"]["A8"] = a8_out

        t0 = time.time()
        a9, a9_out = task_a9(data, a8_artifacts)
        summary["tasks"]["A9"] = {"status": "done", "elapsed_s": round(time.time() - t0, 2)}
        summary["outputs"]["A9"] = a9_out
        summary["a10b_algo2_plan"] = a9["a10b_algo2_plan"]

        t0 = time.time()
        a10a, a10a_out = task_a10a(data)
        summary["tasks"]["A10-a"] = {"status": "done", "elapsed_s": round(time.time() - t0, 2)}
        summary["outputs"]["A10-a"] = a10a_out
        summary["a10a_best_alpha"] = a10a["best_alpha"]

        t0 = time.time()
        a10b, a10b_out = task_a10b(a10a["best_alpha"], a9["a10b_algo2_plan"])
        summary["tasks"]["A10-b"] = {"status": "done", "elapsed_s": round(time.time() - t0, 2)}
        summary["outputs"]["A10-b"] = a10b_out
        summary["a10b_selected"] = a10b["pilot_grid"]["selected"]
        summary["a10b_best_algo2_model"] = a10b["algo2"]["best_model"]
        summary["a10b_best_algo2_js"] = a10b["algo2"]["best_js_mean"]

        summary["status"] = "completed"
    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = str(e)
        summary["traceback"] = traceback.format_exc()
        raise
    finally:
        summary["completed_at"] = now_iso()
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Summary 저장: {summary_path}")

    return summary


if __name__ == "__main__":
    run_all_phase2()
