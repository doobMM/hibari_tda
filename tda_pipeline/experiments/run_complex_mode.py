"""
run_complex_mode.py — Complex weight 모드 실험
=============================================
W_complex(r) = W_timeflow_refined + r · W_simul
  W_timeflow = intra + rate_t · inter  (rate_t=0.3, 감쇄 lag 1~4)
  W_simul    = simul_intra + rate_s · simul_inter  (rate_s = r_c 고정)
  r          : 0.0 → 1.5 sweep (기존 timeflow rate와 동일 역할)

실험 목표:
  rate_s(r_c) ∈ [0.1, 0.3, 0.6, 1.0], rate_t=0.3 고정, N=10
  → K(cycle 수), Algo1 JS 측정
  baseline: 동일 metric으로 timeflow 모드 신규 실행

사용법:
  python run_complex_mode.py
  python run_complex_mode.py --n-repeats 20
  python run_complex_mode.py --alpha 0.0       # α=0.0: 순수 Tonnetz
"""

import os
import sys
import json
import time
import random
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

METRIC_KEYS = ['js_divergence', 'kl_divergence', 'note_coverage',
               'n_notes', 'pitch_count', 'elapsed_s']


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def make_config(alpha: float = 0.5) -> PipelineConfig:
    """Tonnetz α=alpha, ow=0.3 설정 반환."""
    cfg = PipelineConfig()
    cfg.metric.metric = 'tonnetz'
    cfg.metric.alpha = alpha
    cfg.metric.octave_weight = 0.3
    return cfg


def run_algo1_once(p, overlap_values, cycle_labeled, seed: int) -> dict:
    """Algorithm 1을 한 번 실행하고 평가 결과를 반환."""
    random.seed(seed)
    np.random.seed(seed)

    notes_label = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']

    pool = NodePool(notes_label, notes_counts, num_modules=65)
    manager = CycleSetManager(cycle_labeled)

    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33

    t0 = time.time()
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False
    )
    elapsed = time.time() - t0

    result = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        notes_label, name=""
    )
    result['elapsed_s'] = elapsed
    return result


def aggregate(trials: list, keys: list) -> dict:
    out = {}
    for k in keys:
        vals = [t[k] for t in trials]
        out[k] = {
            'mean': float(np.mean(vals)),
            'std':  float(np.std(vals, ddof=1) if len(vals) > 1 else 0.0),
            'min':  float(np.min(vals)),
            'max':  float(np.max(vals)),
        }
    return out


def run_n_trials(p, overlap_values, cycle_labeled, n: int, seed_offset: int) -> dict:
    """N회 Algo1 실행 후 집계."""
    trials = []
    for i in range(n):
        r = run_algo1_once(p, overlap_values, cycle_labeled, seed=seed_offset + i)
        trials.append(r)
        print(f"  [{i+1:2d}/{n}] JS={r['js_divergence']:.4f}  "
              f"notes={r['n_notes']}  cov={r['note_coverage']:.2f}")
    return aggregate(trials, METRIC_KEYS)


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Complex weight 모드 실험 (r_c grid × N 반복)")
    parser.add_argument('--n-repeats', dest='n_repeats', type=int, default=10,
                        help="각 설정 반복 횟수 (기본 10)")
    parser.add_argument('--alpha', type=float, default=0.5,
                        help="tonnetz/frequency blend. α=0.0: 순수 Tonnetz, "
                             "α=1.0: 순수 frequency (기본 0.5)")
    args = parser.parse_args()

    RC_GRID = [0.1, 0.3, 0.6, 1.0]
    RATE_T = 0.3
    ALPHA = args.alpha
    N = args.n_repeats

    print("=" * 65)
    print("  Complex weight 모드 실험")
    print(f"  metric=tonnetz, α={ALPHA}, ow=0.3")
    print(f"  rate_t={RATE_T} (fixed), r_c grid={RC_GRID}")
    print(f"  N={N} 반복 / 설정")
    print("=" * 65)

    # ── 전처리 (1회) ──────────────────────────────────────────────────────────
    cfg = make_config(alpha=ALPHA)
    p = TDAMusicPipeline(cfg)
    p.run_preprocessing()
    print(f"\n전처리 완료: notes={len(p._cache['notes_label'])}종")

    results = {}

    # ── Timeflow baseline (동일 α, 캐시 미사용) ───────────────────────────────
    print(f"\n{'─' * 65}")
    print(f"[Baseline] Timeflow  (rate_t={RATE_T}, α={ALPHA})")
    print(f"{'─' * 65}")

    p.run_homology_search(search_type='timeflow', dimension=1)
    p.run_overlap_construction(persistence_key='h1_timeflow_lag1')

    overlap_tf = p._cache['overlap_matrix'].values
    cycle_labeled_tf = p._cache['cycle_labeled']
    K_tf = len(cycle_labeled_tf)
    print(f"  K={K_tf} cycles, overlap shape={overlap_tf.shape}")

    agg_tf = run_n_trials(p, overlap_tf, cycle_labeled_tf, N, seed_offset=7000)
    agg_tf['n_cycles'] = K_tf
    agg_tf['search_type'] = 'timeflow'
    agg_tf['rate_t'] = RATE_T
    agg_tf['rate_s'] = None
    results['timeflow_baseline'] = agg_tf
    js_tf = agg_tf['js_divergence']['mean']
    print(f"  → JS={js_tf:.4f} ± {agg_tf['js_divergence']['std']:.4f}")

    # ── Complex mode grid ─────────────────────────────────────────────────────
    for rc in RC_GRID:
        print(f"\n{'─' * 65}")
        print(f"[Complex] rate_s(r_c)={rc}, rate_t={RATE_T}")
        print(f"{'─' * 65}")

        p.run_homology_search(
            search_type='complex', dimension=1,
            rate_t=RATE_T, rate_s=rc
        )
        p.run_overlap_construction(persistence_key='h1_complex_lag1')

        overlap_cx = p._cache['overlap_matrix'].values
        cycle_labeled_cx = p._cache['cycle_labeled']
        K_cx = len(cycle_labeled_cx)
        print(f"  K={K_cx} cycles, overlap shape={overlap_cx.shape}")

        agg = run_n_trials(p, overlap_cx, cycle_labeled_cx, N, seed_offset=8000)
        agg['n_cycles'] = K_cx
        agg['search_type'] = 'complex'
        agg['rate_t'] = RATE_T
        agg['rate_s'] = rc
        results[f'complex_rc{rc}'] = agg

        js = agg['js_divergence']['mean']
        delta = (js - js_tf) / js_tf * 100 if js_tf > 0 else 0.0
        sign = '+' if delta >= 0 else ''
        print(f"  → JS={js:.4f} ± {agg['js_divergence']['std']:.4f}  "
              f"K={K_cx}  Δ(vs baseline)={sign}{delta:.1f}%")

    # ── 저장 ─────────────────────────────────────────────────────────────────
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    out = {
        'experiment': 'complex_mode',
        'description': 'W_complex = W_timeflow_refined + r * W_simul, r_c grid',
        'alpha': ALPHA,
        'octave_weight': 0.3,
        'rate_t': RATE_T,
        'rc_grid': RC_GRID,
        'n_repeats': N,
        'results': results,
    }
    out_path = os.path.join(out_dir, 'complex_mode_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 요약 표 ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  요약 (Algo1 JS divergence, N=%d)" % N)
    print("=" * 65)
    print(f"  {'설정':<30}  {'JS (mean±std)':<18}  {'K':>4}  {'Δ baseline':>10}")
    print(f"  {'─'*30}  {'─'*18}  {'─'*4}  {'─'*10}")

    baseline_js = results['timeflow_baseline']['js_divergence']['mean']
    baseline_std = results['timeflow_baseline']['js_divergence']['std']
    print(f"  {'timeflow (baseline)':<30}  "
          f"{baseline_js:.4f} ± {baseline_std:.4f}   "
          f"  {results['timeflow_baseline']['n_cycles']:>4}  {'—':>10}")

    best_key, best_js = None, float('inf')
    for rc in RC_GRID:
        key = f'complex_rc{rc}'
        agg = results[key]
        js = agg['js_divergence']['mean']
        std = agg['js_divergence']['std']
        K = agg['n_cycles']
        delta = (js - baseline_js) / baseline_js * 100 if baseline_js > 0 else 0.0
        sign = '+' if delta >= 0 else ''
        label = f"complex r_c={rc}"
        print(f"  {label:<30}  {js:.4f} ± {std:.4f}   {K:>4}  {sign}{delta:.1f}%")
        if js < best_js:
            best_js, best_key = js, key

    if best_key:
        best_rc = results[best_key]['rate_s']
        print(f"\n  ★ 최적 r_c = {best_rc}  JS={best_js:.4f}")
        if best_js < baseline_js:
            impr = (baseline_js - best_js) / baseline_js * 100
            print(f"    → timeflow 대비 {impr:.1f}% 개선")
        else:
            impr = (best_js - baseline_js) / baseline_js * 100
            print(f"    → timeflow 대비 {impr:.1f}% 악화 (complex 효과 없음)")


if __name__ == '__main__':
    main()
