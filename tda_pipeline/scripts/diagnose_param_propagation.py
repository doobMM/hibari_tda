"""
파이프라인 파라미터 전파 회귀 테스트 (Task 1-4).

같은 seed, 같은 cache로 Algorithm 1을 두 번 실행하되,
`min_onset_gap`만 0/3 (또는 인자로 지정한 값)으로 다르게 넘겨
onset 필터링 외에는 결정적으로 같은지 검증.

추가: `octave_weight=0.3` vs `0.5` 대비 — 거리 행렬·K 변화만 발생,
downstream이 결정적인지 확인.

요구 실행 환경:
  - `tda_pipeline/` 루트에서 `python scripts/diagnose_param_propagation.py`
  - `output/pipeline_cache.pkl`이 있거나, `--fresh`로 매 번 새로 전처리
"""
from __future__ import annotations

import argparse
import hashlib
import os
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def set_all_seeds(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


def hash_array(a: np.ndarray) -> str:
    return hashlib.sha1(a.tobytes()).hexdigest()[:12]


def run_algo1_with_gap(pipeline, *, seed: int, gap: int) -> dict[str, Any]:
    """동일 캐시 기반으로 Algo1을 한 번 실행, 결과 요약 반환."""
    from generation import NodePool, CycleSetManager, algorithm1_optimized

    set_all_seeds(seed)

    notes_label = pipeline._cache['notes_label']
    notes_counts = pipeline._cache['notes_counts']
    cycle_labeled = pipeline._cache['cycle_labeled']
    overlap = pipeline._cache['overlap_matrix']

    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33

    pool = NodePool(
        notes_label, notes_counts,
        num_modules=pipeline.config.generation.num_modules,
        temperature=pipeline.config.generation.temperature,
    )
    manager = CycleSetManager(cycle_labeled)

    generated = algorithm1_optimized(
        pool, inst_chord_heights,
        overlap.values,
        manager,
        max_resample=pipeline.config.generation.max_resample_attempts,
        verbose=False,
        min_onset_gap=gap,
    )

    return {
        'K': len(cycle_labeled),
        'cycle_ids': sorted(cycle_labeled.keys()),
        'overlap_hash': hash_array(overlap.values.astype(np.int8)),
        'n_notes_generated': len(generated),
        'seed': seed,
        'gap': gap,
    }


def run_metric_diff(pipeline_factory, *, ow_values: list[float]):
    """octave_weight만 바꿔 가며 Stage 2/3까지 수행, 거리행렬·K 변화만 있는지 확인."""
    from config import PipelineConfig

    results = []
    for ow in ow_values:
        cfg = PipelineConfig()
        cfg.metric.metric = 'tonnetz'
        cfg.metric.alpha = 0.5
        cfg.metric.octave_weight = ow

        pipe = pipeline_factory(cfg)
        pipe.run_preprocessing()
        pipe.run_homology_search(search_type='timeflow', lag=1, dimension=1)
        pipe.run_overlap_construction(persistence_key='h1_timeflow_lag1')

        K = len(pipe._cache['cycle_labeled'])
        overlap_hash = hash_array(
            pipe._cache['overlap_matrix'].values.astype(np.int8)
        )
        results.append({'ow': ow, 'K': K, 'overlap_hash': overlap_hash})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--gap-a', type=int, default=0)
    parser.add_argument('--gap-b', type=int, default=3)
    parser.add_argument('--skip-ow', action='store_true', help='octave_weight 비교 스킵 (시간 절약)')
    parser.add_argument('--cache', type=str, default='output/pipeline_cache.pkl',
                        help='파이프라인 캐시 경로 (없으면 새로 전처리)')
    args = parser.parse_args()

    os.chdir(ROOT)

    from config import PipelineConfig
    from pipeline import TDAMusicPipeline

    # === Part 1: min_onset_gap 전파 검증 ===
    print("=" * 72)
    print(f"Part 1: min_onset_gap {args.gap_a} vs {args.gap_b} (seed={args.seed})")
    print("=" * 72)

    cfg = PipelineConfig()
    pipeline = TDAMusicPipeline(cfg)

    if Path(args.cache).exists():
        print(f"[load] cache: {args.cache}")
        pipeline.load_cache(Path(args.cache).name)
    else:
        print("[fresh] no cache — running preprocessing + homology + overlap")
        pipeline.run_preprocessing()
        pipeline.run_homology_search(search_type='timeflow', lag=1, dimension=1)
        pipeline.run_overlap_construction(persistence_key='h1_timeflow_lag1')

    res_a = run_algo1_with_gap(pipeline, seed=args.seed, gap=args.gap_a)
    res_b = run_algo1_with_gap(pipeline, seed=args.seed, gap=args.gap_b)

    print()
    print(f"[{args.gap_a}] K={res_a['K']}, cycle_ids={res_a['cycle_ids'][:6]}..., "
          f"overlap_hash={res_a['overlap_hash']}, n_notes={res_a['n_notes_generated']}")
    print(f"[{args.gap_b}] K={res_b['K']}, cycle_ids={res_b['cycle_ids'][:6]}..., "
          f"overlap_hash={res_b['overlap_hash']}, n_notes={res_b['n_notes_generated']}")

    assert res_a['K'] == res_b['K'], "K 불일치 — gap이 PH에 영향을 줌 (예상 밖 동작)"
    assert res_a['cycle_ids'] == res_b['cycle_ids'], "cycle_ids 불일치"
    assert res_a['overlap_hash'] == res_b['overlap_hash'], "overlap_hash 불일치"
    print("  ✓ K / cycle_ids / overlap_hash 모두 동일 — min_onset_gap이 PH를 건드리지 않음")
    if res_a['n_notes_generated'] != res_b['n_notes_generated']:
        print(f"  ✓ 노트 수 차이 {res_a['n_notes_generated']} vs {res_b['n_notes_generated']} "
              "— onset 필터링에만 영향 (예상대로)")

    # === Part 2: octave_weight 대비 (옵션) ===
    if not args.skip_ow:
        print()
        print("=" * 72)
        print("Part 2: octave_weight=0.3 vs 0.5 (tonnetz, alpha=0.5)")
        print("=" * 72)

        def factory(cfg):
            return TDAMusicPipeline(cfg)

        ow_rows = run_metric_diff(factory, ow_values=[0.3, 0.5])
        for r in ow_rows:
            print(f"  ow={r['ow']}: K={r['K']}, overlap_hash={r['overlap_hash']}")
        if ow_rows[0]['overlap_hash'] == ow_rows[1]['overlap_hash']:
            print("  ⚠ 두 ow에서 overlap_hash 동일 — 거리 행렬에 octave_weight가 반영되지 않았을 가능성")
        else:
            print("  ✓ overlap_hash 다름 — octave_weight가 거리 행렬 경유로 반영됨")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
