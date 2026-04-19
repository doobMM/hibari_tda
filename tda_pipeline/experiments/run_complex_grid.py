"""
run_complex_grid.py — Complex simul weight 효과 × 4차원 grid search
====================================================================
캐시 미사용. PH 신규 계산.

Grid:
  alpha          : [0.25, 0.5]          — frequency↔musical 혼합 비율
  octave_weight  : [0.0,  0.3, 0.6]     — 옥타브 항 가중치
  duration_weight: [0.0,  0.3, 0.6]     — duration 항 가중치
  rate_s (r_c)   : [0.1,  0.3, 0.6]     — simul 성분 강도 (complex 전용)

  각 metric combo (alpha, ow, dw)마다:
    - timeflow baseline 1회
    - complex 3 r_c값

  rate_t = 0.3 고정, N = 5 / 설정

총 2×3×3 = 18 metric combos × (1 tf + 3 cx) = 72 PH runs
결과: docs/step3_data/complex_grid_results.json
"""

import os, sys, json, time, random, itertools, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

METRIC_KEYS = ['js_divergence', 'note_coverage', 'n_notes', 'pitch_count']
RATE_T      = 0.3
RC_GRID     = [0.1, 0.3, 0.6]
ALGO1_BEST  = 0.0241   # §7.7.1 per-cycle τ N=20 기준


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def make_pipeline(alpha, octave_weight, duration_weight) -> TDAMusicPipeline:
    cfg = PipelineConfig()
    cfg.metric.metric          = 'tonnetz'
    cfg.metric.alpha           = alpha
    cfg.metric.octave_weight   = octave_weight
    cfg.metric.duration_weight = duration_weight
    return TDAMusicPipeline(cfg)


def run_algo1_once(p, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    notes_label  = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']
    pool    = NodePool(notes_label, notes_counts, num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    generated = algorithm1_optimized(
        pool, modules * 33, overlap_values, manager,
        max_resample=50, verbose=False)
    result = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        notes_label, name="")
    return result


def run_n(p, overlap_values, cycle_labeled, n, seed_offset):
    trials = [run_algo1_once(p, overlap_values, cycle_labeled, seed_offset + i)
              for i in range(n)]
    agg = {}
    for k in METRIC_KEYS:
        v = [t[k] for t in trials]
        agg[k] = {'mean': float(np.mean(v)),
                  'std':  float(np.std(v, ddof=1) if n > 1 else 0.0)}
    return agg


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=5, help='Algo1 반복 횟수 (기본 5)')
    parser.add_argument('--alpha-grid', nargs='+', type=float,
                        default=[0.25, 0.5],
                        help='alpha 값 목록 (기본 0.25 0.5)')
    parser.add_argument('--ow-grid', nargs='+', type=float,
                        default=[0.0, 0.3, 0.6],
                        help='octave_weight 값 목록')
    parser.add_argument('--dw-grid', nargs='+', type=float,
                        default=[0.0, 0.3, 0.6],
                        help='duration_weight 값 목록')
    parser.add_argument('--rc-grid', nargs='+', type=float,
                        default=[0.1, 0.3, 0.6],
                        help='rate_s(r_c) 값 목록 (complex 전용)')
    args = parser.parse_args()

    ALPHA_GRID = args.alpha_grid
    OW_GRID    = args.ow_grid
    DW_GRID    = args.dw_grid
    RC_GRID_   = args.rc_grid
    N          = args.n

    metric_combos = list(itertools.product(ALPHA_GRID, OW_GRID, DW_GRID))
    n_total = len(metric_combos) * (1 + len(RC_GRID_))

    print("=" * 70)
    print("  Complex grid search — 캐시 미사용, PH 신규 계산")
    print(f"  alpha={ALPHA_GRID}  ow={OW_GRID}  dw={DW_GRID}  r_c={RC_GRID_}")
    print(f"  {len(metric_combos)} metric combos × (1 tf + {len(RC_GRID_)} cx)"
          f" = {n_total} PH runs  /  N={N}")
    print("=" * 70)

    # ── 전처리 1회 ────────────────────────────────────────────────────────────
    # 전처리는 metric 설정과 무관하므로 1회만 실행 후 캐시 공유
    base_p = TDAMusicPipeline(PipelineConfig())
    base_p.run_preprocessing()
    preproc_cache = {k: v for k, v in base_p._cache.items()}
    print(f"전처리 완료: notes={len(preproc_cache['notes_label'])}종\n")

    all_results = {}    # key: "α{a}_ow{o}_dw{d}_{tf|cx_rc{r}}"
    summary_rows = []   # 최종 표용

    seed_counter = [10000]

    def next_seed():
        s = seed_counter[0]; seed_counter[0] += 1; return s

    combo_idx = 0
    for alpha, ow, dw in metric_combos:
        combo_idx += 1
        combo_tag = f"α{alpha}_ow{ow}_dw{dw}"
        print(f"\n[{combo_idx}/{len(metric_combos)}] {combo_tag}")
        print(f"  {'─'*60}")

        # 파이프라인 재구성 (metric만 변경, 전처리 캐시 재주입)
        p = make_pipeline(alpha, ow, dw)
        p._cache.update(preproc_cache)   # 전처리 결과 재사용

        # ── Timeflow baseline ──────────────────────────────────────────────
        t0 = time.time()
        p.run_homology_search(search_type='timeflow', dimension=1)
        p.run_overlap_construction(persistence_key='h1_timeflow_lag1')
        ov_tf  = p._cache['overlap_matrix'].values
        cyc_tf = p._cache['cycle_labeled']
        K_tf   = len(cyc_tf)

        seed = next_seed()
        agg_tf = run_n(p, ov_tf, cyc_tf, N, seed)
        js_tf  = agg_tf['js_divergence']['mean']
        elapsed = time.time() - t0

        key_tf = f"{combo_tag}_timeflow"
        all_results[key_tf] = {**agg_tf, 'K': K_tf, 'search': 'timeflow',
                                'alpha': alpha, 'ow': ow, 'dw': dw, 'rc': None}
        summary_rows.append({'tag': key_tf, 'alpha': alpha, 'ow': ow, 'dw': dw,
                              'rc': None, 'search': 'timeflow',
                              'K': K_tf, 'js': js_tf,
                              'js_std': agg_tf['js_divergence']['std']})
        print(f"  [TF] K={K_tf:3d}  JS={js_tf:.4f} ± {agg_tf['js_divergence']['std']:.4f}"
              f"  ({elapsed:.1f}s)")

        # ── Complex r_c grid ───────────────────────────────────────────────
        for rc in RC_GRID_:
            t0 = time.time()
            p.run_homology_search(search_type='complex', dimension=1,
                                  rate_t=RATE_T, rate_s=rc)
            p.run_overlap_construction(persistence_key='h1_complex_lag1')
            ov_cx  = p._cache['overlap_matrix'].values
            cyc_cx = p._cache['cycle_labeled']
            K_cx   = len(cyc_cx)

            seed = next_seed()
            agg_cx = run_n(p, ov_cx, cyc_cx, N, seed)
            js_cx  = agg_cx['js_divergence']['mean']
            elapsed = time.time() - t0

            delta = (js_cx - js_tf) / js_tf * 100 if js_tf > 0 else 0
            sign  = '+' if delta >= 0 else ''

            key_cx = f"{combo_tag}_cx_rc{rc}"
            all_results[key_cx] = {**agg_cx, 'K': K_cx, 'search': 'complex',
                                    'alpha': alpha, 'ow': ow, 'dw': dw, 'rc': rc}
            summary_rows.append({'tag': key_cx, 'alpha': alpha, 'ow': ow, 'dw': dw,
                                  'rc': rc, 'search': 'complex',
                                  'K': K_cx, 'js': js_cx,
                                  'js_std': agg_cx['js_divergence']['std']})
            print(f"  [CX r_c={rc}] K={K_cx:3d}  JS={js_cx:.4f} ± {agg_cx['js_divergence']['std']:.4f}"
                  f"  Δtf={sign}{delta:.1f}%  ({elapsed:.1f}s)")

    # ── 저장 ─────────────────────────────────────────────────────────────────
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    payload = {
        'experiment': 'complex_grid_search',
        'config': {
            'alpha_grid': ALPHA_GRID, 'ow_grid': OW_GRID,
            'dw_grid': DW_GRID, 'rc_grid': RC_GRID_,
            'rate_t': RATE_T, 'n_repeats': N,
        },
        'reference': {'algo1_best_percycle': ALGO1_BEST},
        'results': all_results,
        'summary': summary_rows,
    }
    out_path = os.path.join(out_dir, 'complex_grid_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 요약 표 ───────────────────────────────────────────────────────────────
    summary_rows.sort(key=lambda r: r['js'])

    print("\n" + "=" * 70)
    print(f"  전체 순위 (상위 15개, N={N})")
    print("=" * 70)
    print(f"  {'설정':<42}  {'JS':>7}  {'±':>6}  {'K':>4}  {'Δ Algo1-best':>12}")
    print(f"  {'─'*42}  {'─'*7}  {'─'*6}  {'─'*4}  {'─'*12}")

    for row in summary_rows[:15]:
        tag   = row['tag'].replace('α', 'a').replace('_', ' ')
        js    = row['js']
        std   = row['js_std']
        K     = row['K']
        delta = (js - ALGO1_BEST) / ALGO1_BEST * 100
        sign  = '+' if delta >= 0 else ''
        mark  = '★' if js < ALGO1_BEST else ' '
        print(f"{mark} {tag:<42}  {js:7.4f}  {std:6.4f}  {K:4d}  {sign}{delta:.1f}%")

    # simul 효과 요약
    print(f"\n{'─'*70}")
    print("  Simul 효과 요약 (같은 metric combo 내 complex vs timeflow)")
    print(f"{'─'*70}")
    tf_map = {(r['alpha'], r['ow'], r['dw']): r['js']
              for r in summary_rows if r['search'] == 'timeflow'}
    improvements = []
    for row in summary_rows:
        if row['search'] != 'complex': continue
        key = (row['alpha'], row['ow'], row['dw'])
        if key not in tf_map: continue
        js_tf_ = tf_map[key]
        delta = (row['js'] - js_tf_) / js_tf_ * 100
        improvements.append({'combo': key, 'rc': row['rc'], 'delta': delta,
                              'js': row['js'], 'js_tf': js_tf_})

    improvements.sort(key=lambda x: x['delta'])
    print(f"  {'α / ow / dw / r_c':<32}  {'js_tf':>6}  {'js_cx':>6}  {'Δ':>8}")
    print(f"  {'─'*32}  {'─'*6}  {'─'*6}  {'─'*8}")
    for imp in improvements[:10]:
        a, o, d = imp['combo']
        print(f"  α={a} ow={o} dw={d} rc={imp['rc']:<5}  "
              f"{imp['js_tf']:6.4f}  {imp['js']:6.4f}  {imp['delta']:+7.1f}%")

    best = summary_rows[0]
    print(f"\n  ★ 전체 최적: {best['tag']}")
    print(f"    JS={best['js']:.4f}  K={best['K']}")
    rc_str = 'timeflow' if best['rc'] is None else f"complex r_c={best['rc']}"
    print(f"    (α={best['alpha']}, ow={best['ow']}, dw={best['dw']}, {rc_str})")
    if best['js'] < ALGO1_BEST:
        print(f"    → Algo1 best ({ALGO1_BEST}) 갱신! "
              f"{(ALGO1_BEST - best['js'])/ALGO1_BEST*100:.1f}% 개선")
    else:
        print(f"    → Algo1 best ({ALGO1_BEST}) 미갱신")


if __name__ == '__main__':
    main()
