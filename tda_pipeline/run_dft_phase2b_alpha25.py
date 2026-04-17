"""
run_dft_phase2b_alpha25.py
==========================

세션 A Phase 2 후속 Task A10-b′:
- DFT complex + per-cycle tau
- alpha=0.25 고정
- r_c in {0.1, 0.3}
- Algo1 N=20, Algo2 FC-cont 보고
- A8(best timeflow per-cycle) 대비 Welch t-test

출력:
- docs/step3_data/complex_percycle_dft_gap0_alpha25_results.json
- docs/step3_data/phase2b_alpha25_summary.json
"""

from __future__ import annotations

import json
import os
import time
import traceback
from typing import Dict, List

import numpy as np

from config import PipelineConfig
from pipeline import TDAMusicPipeline
from utils.result_meta import build_result_header

import run_dft_gap0_suite as suite
import run_dft_phase2_gap0_suite as p2


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")

OUTPUT_JSON = "complex_percycle_dft_gap0_alpha25_results.json"
SUMMARY_JSON = "phase2b_alpha25_summary.json"

MIN_ONSET_GAP = 0
METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
RC_GRID = [0.1, 0.3]
POST_BUGFIX = True

N_REPEATS_MAIN = 20
N_REPEATS_ALGO2 = 5
GREEDY_SEARCH_N = 5

A8_PATH = os.path.join(STEP3_DIR, "percycle_tau_dft_gap0_results.json")

TONNETZ_COMPLEX_ALGO1_BEST = 0.0183
TONNETZ_COMPLEX_ALGO2_FC_BEST = 0.0003


def save_json(payload: dict, filename: str) -> str:
    os.makedirs(STEP3_DIR, exist_ok=True)
    path = os.path.join(STEP3_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"저장: {path}")
    return path


def make_header(n_repeats: int, extra: dict | None = None) -> dict:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = ALPHA
    cfg.metric.octave_weight = OCTAVE_WEIGHT
    cfg.metric.duration_weight = DURATION_WEIGHT
    cfg.min_onset_gap = MIN_ONSET_GAP
    cfg.post_bugfix = POST_BUGFIX
    return build_result_header(cfg, script_name=__file__, n_repeats=n_repeats, extra=extra)


def classify_vs_a8(test_result: dict) -> str:
    p = test_result["p_value"]
    mean_a = test_result["mean_a"]  # A8
    mean_b = test_result["mean_b"]  # complex(rc)
    if p < 0.05 and mean_b < mean_a:
        return "significant_improvement"
    if p < 0.05 and mean_b > mean_a:
        return "significant_degradation"
    return "non_significant"


def run_for_rc(
    preproc_cache: dict,
    eval_data: dict,
    a8_js: np.ndarray,
    rc: float,
    idx: int,
) -> dict:
    print("\n" + "-" * 72)
    print(f"[A10-b′] rc={rc} 실행")
    print("-" * 72)

    bundle = p2.build_complex_bundle(
        preproc_cache,
        alpha=ALPHA,
        ow=OCTAVE_WEIGHT,
        dw=DURATION_WEIGHT,
        rc=rc,
    )
    if bundle["K"] == 0:
        return {
            "r_c": rc,
            "status": "skipped_K0",
            "K": 0,
            "ph_time_s": bundle["ph_time_s"],
        }

    best_taus, greedy_logs = p2.greedy_percycle_tau(
        eval_data,
        bundle["cont_overlap"],
        bundle["cycle_labeled"],
        tau_candidates=p2.TAU_CANDIDATES,
        n_search=GREEDY_SEARCH_N,
        seed_base=51000 + idx * 10000,
    )
    percycle_overlap = p2.build_percycle_overlap(bundle["cont_overlap"], best_taus)

    algo1_js_arr, algo1_summary = p2.run_algo1_eval(
        eval_data,
        percycle_overlap,
        bundle["cycle_labeled"],
        N_REPEATS_MAIN,
        seed_base=52000 + idx * 10000,
    )
    t_a8 = p2.welch_ttest(
        a8_js,
        algo1_js_arr,
        "A8_timeflow_percycle",
        f"A10b_alpha25_complex_rc{rc}",
    )
    t_class = classify_vs_a8(t_a8)

    if suite.torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 Algo2 FC 실행이 불가합니다.")
    from generation import MusicGeneratorFC

    algo2_fc = suite.run_model_trials(
        eval_data,
        bundle["cont_overlap"],
        f"A10b_prime_rc{rc}_FC_cont",
        MusicGeneratorFC,
        {
            "num_cycles": bundle["cont_overlap"].shape[1],
            "num_notes": len(eval_data["notes_label"]),
            "hidden_dim": 256,
            "dropout": 0.3,
        },
        "fc",
        n_trials=N_REPEATS_ALGO2,
        epochs=200,
        lr=0.001,
        batch_size=32,
        min_onset_gap=MIN_ONSET_GAP,
    )

    return {
        "r_c": rc,
        "status": "done",
        "K": int(bundle["K"]),
        "ph_time_s": float(bundle["ph_time_s"]),
        "greedy_search_n": GREEDY_SEARCH_N,
        "best_taus": [float(t) for t in best_taus],
        "greedy_logs": greedy_logs,
        "algo1_per_cycle_tau": {
            "n_repeats": N_REPEATS_MAIN,
            "js_divergence": algo1_summary["js_divergence"],
            "all_js": [float(x) for x in algo1_js_arr],
            "density": float((percycle_overlap > 0).mean()),
        },
        "a8_welch_test": {
            **t_a8,
            "classification": t_class,
        },
        "algo2_fc_cont": {
            **algo2_fc,
            "n_repeats": N_REPEATS_ALGO2,
        },
    }


def main():
    os.chdir(BASE_DIR)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    summary = {
        "task": "A10-b-prime_alpha25",
        "started_at": started_at,
        "same_python_session": True,
        "script": os.path.basename(__file__),
        "status": "running",
        "outputs": {},
    }
    summary_path = os.path.join(STEP3_DIR, SUMMARY_JSON)

    try:
        if not os.path.exists(A8_PATH):
            raise FileNotFoundError(f"A8 결과 파일 없음: {A8_PATH}")
        with open(A8_PATH, "r", encoding="utf-8") as f:
            a8 = json.load(f)
        a8_js = np.array(a8["per_cycle_tau"]["all_js"], dtype=float)
        a8_mean = float(np.mean(a8_js))
        a8_std = float(np.std(a8_js, ddof=1))
        print(f"[A8 baseline] JS={a8_mean:.4f} ± {a8_std:.4f} (N={len(a8_js)})")

        base_cfg = PipelineConfig()
        base_cfg.min_onset_gap = MIN_ONSET_GAP
        base_pipe = TDAMusicPipeline(base_cfg)
        base_pipe.run_preprocessing()
        preproc_cache = dict(base_pipe._cache)
        eval_data = p2.make_eval_data_from_preproc(preproc_cache)

        rc_results: List[dict] = []
        for idx, rc in enumerate(RC_GRID):
            rc_results.append(run_for_rc(preproc_cache, eval_data, a8_js, rc, idx))

        valid = [r for r in rc_results if r.get("status") == "done"]
        if not valid:
            conclusion = "complex_not_evaluable"
            best_rc = None
            best_algo1 = None
            best_algo2 = None
        else:
            best = min(valid, key=lambda r: r["algo1_per_cycle_tau"]["js_divergence"]["mean"])
            best_rc = best["r_c"]
            best_algo1 = best["algo1_per_cycle_tau"]["js_divergence"]["mean"]
            best_algo2 = best["algo2_fc_cont"]["js_mean"]
            cls = best["a8_welch_test"]["classification"]
            if cls == "significant_improvement":
                conclusion = "dft_complex_effective"
            elif cls == "significant_degradation":
                conclusion = "complex_tonnetz_only_effective"
            else:
                conclusion = "complex_not_better_than_timeflow_for_dft"

        header = make_header(
            n_repeats=N_REPEATS_MAIN,
            extra={
                "task": "A10-b-prime",
                "mode": "complex",
                "r_c_grid": RC_GRID,
                "n_repeats_algo2": N_REPEATS_ALGO2,
                "greedy_search_n": GREEDY_SEARCH_N,
            },
        )
        payload = {
            **header,
            "a8_reference": {
                "source_file": os.path.relpath(A8_PATH, BASE_DIR).replace("\\", "/"),
                "js_mean": a8_mean,
                "js_std": a8_std,
                "n_repeats": int(len(a8_js)),
                "all_js": [float(x) for x in a8_js],
            },
            "rc_results": rc_results,
            "best_rc_by_algo1": best_rc,
            "best_algo1_js": best_algo1,
            "best_algo2_fc_js": best_algo2,
            "comparison_to_tonnetz_complex_best": {
                "tonnetz_algo1_best_js": TONNETZ_COMPLEX_ALGO1_BEST,
                "tonnetz_algo2_fc_best_js": TONNETZ_COMPLEX_ALGO2_FC_BEST,
                "dft_best_algo1_js": best_algo1,
                "dft_best_algo2_fc_js": best_algo2,
                "delta_pct_algo1_dft_vs_tonnetz": (
                    None
                    if best_algo1 is None
                    else float(100 * (best_algo1 - TONNETZ_COMPLEX_ALGO1_BEST) / TONNETZ_COMPLEX_ALGO1_BEST)
                ),
                "delta_pct_algo2_dft_vs_tonnetz": (
                    None
                    if best_algo2 is None
                    else float(100 * (best_algo2 - TONNETZ_COMPLEX_ALGO2_FC_BEST) / TONNETZ_COMPLEX_ALGO2_FC_BEST)
                ),
            },
            "conclusion": conclusion,
        }
        out_path = save_json(payload, OUTPUT_JSON)
        summary["outputs"]["result_json"] = out_path
        summary["status"] = "completed"

    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = str(e)
        summary["traceback"] = traceback.format_exc()
        raise
    finally:
        summary["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        os.makedirs(STEP3_DIR, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Summary 저장: {summary_path}")


if __name__ == "__main__":
    main()
