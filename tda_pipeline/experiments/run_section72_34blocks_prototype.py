"""
Section 7.2 prototype 재실험 (34x32 블록 reshape)
=================================================

요구사항:
- O_full: (1088, K=14) 전체 이진 overlap 사용
- reshape: (34, 32, 14)
- Prototype:
  P0: 첫 블록
  P1: 34개 블록 시점별 OR
  P2: 34개 블록 시점별 majority vote
  P3_local: 블록 구간(두 악기) local PH 재계산
- 각 prototype N=10 반복
- 생성 모듈을 34회 복제로 full-song 재구성 후 JS 평가
- 출력: docs/step3_data/section72_34blocks_prototype_results.json
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import numpy as np

from config import PipelineConfig
from eval_metrics import evaluate_generation
from utils.result_meta import build_result_header

import run_phase3_task38a_dft_gap0 as phase38


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
OUT_PATH = os.path.join(STEP3_DIR, "section72_34blocks_prototype_results.json")

BLOCK_LEN = 32
FULL_T = 1088
N_BLOCKS = 34
N_REPEATS = 10
EXPECTED_K = 14


def make_header(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = "dft"
    cfg.metric.alpha = 0.25
    cfg.metric.octave_weight = 0.3
    cfg.metric.duration_weight = 1.0
    cfg.min_onset_gap = 0
    cfg.post_bugfix = True
    return build_result_header(
        cfg,
        script_name=os.path.basename(__file__),
        n_repeats=N_REPEATS,
        extra=extra,
    )


def reshape_full_to_blocks(overlap_full: np.ndarray) -> np.ndarray:
    if overlap_full.shape[0] != FULL_T:
        raise ValueError(f"expected overlap rows {FULL_T}, got {overlap_full.shape[0]}")
    if overlap_full.shape[0] % BLOCK_LEN != 0:
        raise ValueError(
            f"overlap rows {overlap_full.shape[0]} is not divisible by block_len {BLOCK_LEN}"
        )
    n_blocks = overlap_full.shape[0] // BLOCK_LEN
    if n_blocks != N_BLOCKS:
        raise ValueError(f"expected {N_BLOCKS} blocks, got {n_blocks}")
    return overlap_full.reshape(n_blocks, BLOCK_LEN, overlap_full.shape[1]).astype(np.float32)


def replicate_34_blocks(module_notes: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for b in range(N_BLOCKS):
        offset = b * BLOCK_LEN
        block_end = offset + BLOCK_LEN
        for s, p, e in module_notes:
            ns = s + offset
            ne = min(e + offset, block_end)
            if ns < block_end and ne > ns:
                out.append((int(ns), int(p), int(ne)))
    return out


def summarize_trials(trials: list[dict[str, Any]], density: float, cycle_count: int) -> dict[str, Any]:
    js_vals = np.asarray([t["js"] for t in trials], dtype=float)
    cov_vals = np.asarray([t["coverage"] for t in trials], dtype=float)
    time_vals = np.asarray([t["trial_time_s"] for t in trials], dtype=float)
    best = min(trials, key=lambda x: x["js"])
    return {
        "js_mean": float(js_vals.mean()),
        "js_std": float(js_vals.std(ddof=1) if len(js_vals) > 1 else 0.0),
        "best": {
            "seed": int(best["seed"]),
            "js": float(best["js"]),
            "coverage": float(best["coverage"]),
            "n_notes": int(best["n_notes"]),
            "module_coverage": int(best["module_coverage"]),
        },
        "coverage": float(cov_vals.mean()),
        "per_trial_time": float(time_vals.mean()),
        "density": float(density),
        "cycle_count": int(cycle_count),
        "trials": trials,
    }


def run_trials(
    data: dict[str, Any],
    proto_name: str,
    proto: np.ndarray,
    cycle_labeled: dict[Any, Any],
    seed_base: int,
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    density = float((proto > 0).mean())
    print(f"[run] {proto_name}: density={density:.4f}, cycles={len(cycle_labeled)}")
    for i in range(N_REPEATS):
        seed = seed_base + i
        t0 = time.perf_counter()
        mod = phase38.run_algo1_module(data, proto, cycle_labeled, seed=seed)
        full_gen = replicate_34_blocks(mod)
        metrics = evaluate_generation(
            full_gen,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"],
            name="",
        )
        elapsed = time.perf_counter() - t0
        trials.append(
            {
                "seed": int(seed),
                "js": float(metrics["js_divergence"]),
                "coverage": float(metrics["note_coverage"]),
                "n_notes": int(len(full_gen)),
                "mod_n_notes": int(len(mod)),
                "module_coverage": int(phase38.module_coverage(mod, data["notes_label"])),
                "trial_time_s": float(elapsed),
            }
        )
        print(
            f"  - seed={seed} | js={trials[-1]['js']:.4f} "
            f"| cov={trials[-1]['coverage']:.3f}"
        )

    return summarize_trials(trials, density=density, cycle_count=len(cycle_labeled))


def load_json_if_exists(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_33x32_mean(old_data: dict[str, Any], key: str) -> float | None:
    if old_data is None:
        return None

    # DFT gap0 결과 포맷 (run_phase3_task38a_dft_gap0.py)
    if isinstance(old_data.get("results"), dict):
        mapping = {
            "P0_first_block": "P0_first_module_copy",
            "P1_or_over_34blocks": "P1_union_of_active",
            "P2_majority_vote_over_34blocks": "P2_exclusive_to_module",
            "P3_local_recomputed_ph": "P3_module_specific",
        }
        row = old_data["results"].get(mapping[key], {})
        if isinstance(row, dict) and "js_mean" in row:
            return float(row["js_mean"])

    # 구형 포맷 (step71_prototype_comparison.json)
    mapping_legacy = {
        "P0_first_block": "P0 — OR over 33",
        "P1_or_over_34blocks": "P0 — OR over 33",
        "P2_majority_vote_over_34blocks": "P1 — mean → τ=0.5",
        "P3_local_recomputed_ph": "P3 — median module",
    }
    legacy_row = old_data.get(mapping_legacy[key], {})
    if isinstance(legacy_row, dict) and "js_mean" in legacy_row:
        return float(legacy_row["js_mean"])
    return None


def build_comparison_table(
    results_34: dict[str, Any],
    old_data: dict[str, Any] | None,
    old_path: str | None,
) -> list[dict[str, Any]]:
    notes = {
        "P0_first_block": "direct",
        "P1_or_over_34blocks": "direct",
        "P2_majority_vote_over_34blocks": "definition_changed (old P2 was exclusive/sparse)",
        "P3_local_recomputed_ph": "definition_changed (old P3 was module-specific pick)",
    }
    rows: list[dict[str, Any]] = []
    for proto in [
        "P0_first_block",
        "P1_or_over_34blocks",
        "P2_majority_vote_over_34blocks",
        "P3_local_recomputed_ph",
    ]:
        new_js = float(results_34[proto]["js_mean"])
        old_js = extract_33x32_mean(old_data, proto) if old_data is not None else None
        delta_pct = None
        if old_js is not None and old_js > 0:
            delta_pct = float(100.0 * (new_js - old_js) / old_js)
        rows.append(
            {
                "prototype": proto,
                "js_mean_34x32": new_js,
                "js_mean_33x32": old_js,
                "delta_pct_vs_33x32": delta_pct,
                "note": notes[proto],
                "source_33x32": old_path,
            }
        )
    return rows


def load_legacy_p0_n20_record() -> dict[str, Any]:
    path = os.path.join(STEP3_DIR, "step71_module_results_dft_gap0.json")
    data = load_json_if_exists(path)
    if data is None:
        return {
            "source": path,
            "available": False,
            "reported_user_record_js": 0.1082,
        }
    summary = data.get("summary", {}).get("js_divergence", {})
    return {
        "source": path,
        "available": True,
        "reported_user_record_js": 0.1082,
        "json_mean_js": float(summary.get("mean", np.nan)),
        "json_best_js": float(summary.get("min", np.nan)),
        "n_repeats": int(data.get("summary", {}).get("n_repeats", 0)),
    }


def main() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)

    data = phase38.setup_data()
    bundle, cache_meta = phase38.load_or_build_alpha_bundle(data)
    overlap_full = phase38.to_np(bundle["overlap_binary"])
    cycle_labeled = bundle["cycle_labeled"]
    k_global = len(cycle_labeled)
    if k_global != EXPECTED_K:
        print(f"[warn] expected K={EXPECTED_K}, got K={k_global}")

    blocks = reshape_full_to_blocks(overlap_full)
    print(f"[info] overlap_full={overlap_full.shape} -> blocks={blocks.shape}")
    print(f"[info] cache_used={cache_meta.get('used_cache', False)}")

    p0 = blocks[0].astype(np.float32)
    p1 = blocks.max(axis=0).astype(np.float32)
    p2 = (blocks.sum(axis=0) > (blocks.shape[0] / 2.0)).astype(np.float32)

    local_cycles, p3_local, p3_count = phase38.compute_module_local_ph(data, start_module=0)
    if local_cycles is None or p3_local is None:
        raise RuntimeError("P3_local PH computation returned empty result")
    print(f"[info] P3_local cycles={p3_count}, shape={p3_local.shape}")

    results_34 = {
        "P0_first_block": run_trials(data, "P0_first_block", p0, cycle_labeled, seed_base=8200),
        "P1_or_over_34blocks": run_trials(
            data, "P1_or_over_34blocks", p1, cycle_labeled, seed_base=8300
        ),
        "P2_majority_vote_over_34blocks": run_trials(
            data, "P2_majority_vote_over_34blocks", p2, cycle_labeled, seed_base=8400
        ),
        "P3_local_recomputed_ph": run_trials(
            data, "P3_local_recomputed_ph", p3_local, local_cycles, seed_base=8500
        ),
    }

    old_candidates = [
        os.path.join(STEP3_DIR, "prototype_comparison_results.json"),
        os.path.join(STEP3_DIR, "step71_prototype_comparison_dft_gap0.json"),
        os.path.join(STEP3_DIR, "step71_prototype_comparison.json"),
    ]
    old_data = None
    old_path = None
    for c in old_candidates:
        old_data = load_json_if_exists(c)
        if old_data is not None:
            old_path = c
            break

    comparison = build_comparison_table(results_34, old_data, old_path)
    legacy_p0_n20 = load_legacy_p0_n20_record()

    payload = {
        **make_header(
            extra={
                "task": "section72_34blocks_prototype_comparison",
                "reshape": {
                    "full_shape": [FULL_T, int(k_global)],
                    "block_shape": [N_BLOCKS, BLOCK_LEN, int(k_global)],
                    "block_term": "32-step block",
                },
                "cache_meta": cache_meta,
                "global_cycle_count": int(k_global),
                "local_cycle_count_p3": int(p3_count),
            }
        ),
        "P0_first_block": results_34["P0_first_block"],
        "P1_or_over_34blocks": results_34["P1_or_over_34blocks"],
        "P2_majority_vote_over_34blocks": results_34["P2_majority_vote_over_34blocks"],
        "P3_local_recomputed_ph": results_34["P3_local_recomputed_ph"],
        "_comparison_33x32": comparison,
        "_legacy_p0_n20_record": legacy_p0_n20,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n=== 34x32 Prototype Summary (N=10) ===")
    for name in [
        "P0_first_block",
        "P1_or_over_34blocks",
        "P2_majority_vote_over_34blocks",
        "P3_local_recomputed_ph",
    ]:
        row = payload[name]
        print(
            f"{name:34s} | JS={row['js_mean']:.4f}±{row['js_std']:.4f} "
            f"| best={row['best']['js']:.4f} | cov={row['coverage']:.3f}"
        )
    print(f"\n[saved] {OUT_PATH}")


if __name__ == "__main__":
    main()
