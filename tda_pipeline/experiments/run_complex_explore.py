"""
run_complex_explore.py — Complex mode α=0.0 탐색 + global best 갱신 가능성 검토
==============================================================================
Phase 1: α=0.0, r_c grid [0.1, 0.3, 0.6, 1.0], N=10, Algo1 binary overlap
Phase 2: best r_c + continuous → binary τ=0.5, N=10, Algo1
Phase 3: best r_c + per-cycle τ_c (median 휴리스틱), N=10, Algo1
Phase 4: best r_c + Algo2 (FC, continuous input), N=3  ← global best 도전

참조:
  - 현재 global best: JS=0.0004 (Algo2 FC + continuous, §3.4a)
  - 현재 Algo1 best: JS=0.0241 (per-cycle τ N=20, §7.7.1)
  - timeflow α=0.0 baseline: JS≈0.0398
"""

import os
import sys
import json
import time
import random
import argparse

import numpy as np
import pandas as pd

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

GLOBAL_BEST_ALGO2 = 0.0004   # §3.4a FC+continuous
ALGO1_BEST        = 0.0241   # §7.7.1 per-cycle τ N=20
TF_BASELINE_A0    = 0.0398   # timeflow α=0.0 기존 baseline


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def make_pipeline(alpha: float = 0.0) -> TDAMusicPipeline:
    cfg = PipelineConfig()
    cfg.metric.metric = 'tonnetz'
    cfg.metric.alpha = alpha
    cfg.metric.octave_weight = 0.3
    return TDAMusicPipeline(cfg)


def run_algo1_once(p, overlap_values, cycle_labeled, seed: int) -> dict:
    random.seed(seed); np.random.seed(seed)
    notes_label  = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']
    pool    = NodePool(notes_label, notes_counts, num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33
    t0 = time.time()
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False)
    elapsed = time.time() - t0
    result  = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        notes_label, name="")
    result['elapsed_s'] = elapsed
    return result


def run_n_trials(p, overlap_values, cycle_labeled, n: int, seed_offset: int,
                 label: str = "") -> dict:
    trials = []
    for i in range(n):
        r = run_algo1_once(p, overlap_values, cycle_labeled, seed=seed_offset + i)
        trials.append(r)
        print(f"  [{i+1:2d}/{n}] JS={r['js_divergence']:.4f}  "
              f"notes={r['n_notes']}  cov={r['note_coverage']:.2f}")
    vals = [t['js_divergence'] for t in trials]
    agg = {k: {} for k in METRIC_KEYS}
    for k in METRIC_KEYS:
        v = [t[k] for t in trials]
        agg[k] = {'mean': float(np.mean(v)),
                  'std':  float(np.std(v, ddof=1) if n > 1 else 0.0),
                  'min':  float(np.min(v)),
                  'max':  float(np.max(v))}
    return agg


def compute_percycle_tau_median(cont_activation: pd.DataFrame) -> list:
    """각 cycle의 continuous activation 중앙값을 τ_c로 사용."""
    vals = cont_activation.values.astype(np.float32)
    return [float(np.median(vals[:, c])) for c in range(vals.shape[1])]


def divider(title: str):
    print(f"\n{'─' * 65}")
    print(f"  {title}")
    print(f"{'─' * 65}")


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=10, help='Algo1 반복 횟수 (기본 10)')
    parser.add_argument('--n-algo2', dest='n_algo2', type=int, default=3,
                        help='Phase 4 Algo2 시도 횟수 (기본 3)')
    parser.add_argument('--skip-algo2', dest='skip_algo2', action='store_true',
                        help='Phase 4 (Algo2) 생략')
    args = parser.parse_args()

    RC_GRID = [0.1, 0.3, 0.6, 1.0]
    RATE_T  = 0.3
    ALPHA   = 0.0
    N       = args.n

    print("=" * 65)
    print("  Complex mode α=0.0 탐색 + global best 갱신 가능성 검토")
    print(f"  metric=tonnetz (순수), ow=0.3, rate_t={RATE_T}")
    print(f"  현재 global best (Algo2): JS={GLOBAL_BEST_ALGO2}")
    print(f"  현재 Algo1 best (per-cycle τ): JS={ALGO1_BEST}")
    print("=" * 65)

    # ── 전처리 (1회) ──────────────────────────────────────────────────────────
    p = make_pipeline(alpha=ALPHA)
    p.run_preprocessing()
    print(f"전처리 완료: notes={len(p._cache['notes_label'])}종")

    all_results = {
        'config': {'alpha': ALPHA, 'rate_t': RATE_T, 'rc_grid': RC_GRID, 'n': N},
        'reference': {
            'global_best_algo2': GLOBAL_BEST_ALGO2,
            'algo1_best_percycle': ALGO1_BEST,
            'timeflow_alpha0_baseline': TF_BASELINE_A0,
        },
        'phase1_complex_grid': {},
        'phase2_cont_tau05': {},
        'phase3_percycle_median': {},
        'phase4_algo2': {},
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: α=0.0, complex r_c grid, binary overlap
    # ═══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 65}")
    print("  PHASE 1 — α=0.0, complex r_c grid, binary overlap")
    print(f"{'═' * 65}")

    phase1 = {}
    for rc in RC_GRID:
        divider(f"complex r_c={rc} (α=0.0, binary)")
        p.run_homology_search(search_type='complex', dimension=1,
                              rate_t=RATE_T, rate_s=rc)
        p.run_overlap_construction(persistence_key='h1_complex_lag1')

        ov  = p._cache['overlap_matrix'].values
        cyc = p._cache['cycle_labeled']
        K   = len(cyc)
        print(f"  K={K}, overlap shape={ov.shape}")

        agg = run_n_trials(p, ov, cyc, N, seed_offset=9000)
        agg['n_cycles'] = K
        agg['rate_s'] = rc
        phase1[f'rc{rc}'] = agg

        js = agg['js_divergence']['mean']
        delta = (js - TF_BASELINE_A0) / TF_BASELINE_A0 * 100
        sign = '+' if delta >= 0 else ''
        print(f"  → JS={js:.4f} ± {agg['js_divergence']['std']:.4f}  "
              f"K={K}  Δ(vs TF-α0)={sign}{delta:.1f}%")

    all_results['phase1_complex_grid'] = phase1

    # 최적 r_c 선택
    best_rc = min(RC_GRID, key=lambda rc: phase1[f'rc{rc}']['js_divergence']['mean'])
    best_js_p1 = phase1[f'rc{best_rc}']['js_divergence']['mean']
    best_K     = phase1[f'rc{best_rc}']['n_cycles']
    print(f"\n  ★ Phase 1 최적 r_c={best_rc}  JS={best_js_p1:.4f}  K={best_K}")

    # 최적 r_c로 pipeline 재설정 (Phase 2~4 공통 base)
    p.run_homology_search(search_type='complex', dimension=1,
                          rate_t=RATE_T, rate_s=best_rc)
    p.run_overlap_construction(persistence_key='h1_complex_lag1')
    # activation_continuous는 이미 cache에 저장됨
    cont_act    = p._cache['activation_continuous']   # (T, K) DataFrame
    best_cyc    = p._cache['cycle_labeled']
    best_K_real = len(best_cyc)

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: best r_c + continuous → binary τ=0.5
    # ═══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 65}")
    print(f"  PHASE 2 — r_c={best_rc}, continuous → binary τ=0.5, Algo1")
    print(f"{'═' * 65}")

    tau05_ov = (cont_act.values.astype(np.float32) >= 0.5).astype(np.float32)
    density  = float(tau05_ov.mean())
    print(f"  ON density (τ=0.5): {density:.4f}")

    agg_p2 = run_n_trials(p, tau05_ov, best_cyc, N, seed_offset=9200)
    agg_p2['n_cycles'] = best_K_real
    agg_p2['tau'] = 0.5
    all_results['phase2_cont_tau05'] = agg_p2

    js_p2 = agg_p2['js_divergence']['mean']
    print(f"  → JS={js_p2:.4f} ± {agg_p2['js_divergence']['std']:.4f}  "
          f"Δ(vs Phase1)={(js_p2 - best_js_p1)/best_js_p1*100:+.1f}%")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: best r_c + per-cycle τ_c (median 휴리스틱)
    # ═══════════════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 65}")
    print(f"  PHASE 3 — r_c={best_rc}, per-cycle τ_c=median(activation_c), Algo1")
    print(f"{'═' * 65}")

    tau_medians = compute_percycle_tau_median(cont_act)
    print(f"  τ_c 벡터 (K={best_K_real}): "
          f"min={min(tau_medians):.3f}  max={max(tau_medians):.3f}  "
          f"mean={np.mean(tau_medians):.3f}")
    print(f"  τ_c = {[round(t,3) for t in tau_medians]}")

    # per-cycle τ 적용 → 새 overlap 생성
    p.run_overlap_construction(persistence_key='h1_complex_lag1',
                               per_cycle_tau=tau_medians)
    ov_p3 = p._cache['overlap_matrix'].values
    cyc_p3 = p._cache['cycle_labeled']
    density_p3 = float(ov_p3.mean())
    print(f"  ON density (per-cycle τ_c): {density_p3:.4f}")

    agg_p3 = run_n_trials(p, ov_p3, cyc_p3, N, seed_offset=9400)
    agg_p3['n_cycles'] = len(cyc_p3)
    agg_p3['tau_medians'] = tau_medians
    all_results['phase3_percycle_median'] = agg_p3

    js_p3 = agg_p3['js_divergence']['mean']
    print(f"  → JS={js_p3:.4f} ± {agg_p3['js_divergence']['std']:.4f}  "
          f"Δ(vs Phase1)={(js_p3 - best_js_p1)/best_js_p1*100:+.1f}%  "
          f"vs Algo1-best={(js_p3 - ALGO1_BEST)/ALGO1_BEST*100:+.1f}%")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 4: Algo2 (FC, continuous) — global best 도전
    # ═══════════════════════════════════════════════════════════════════════════
    if args.skip_algo2:
        print("\n[Phase 4 생략 (--skip-algo2)]")
        all_results['phase4_algo2'] = {'skipped': True}
    else:
        print(f"\n{'═' * 65}")
        print(f"  PHASE 4 — r_c={best_rc}, Algo2 FC (continuous input)")
        print(f"  현재 global best: JS={GLOBAL_BEST_ALGO2}  (§3.4a)")
        print(f"{'═' * 65}")

        # Phase 3의 per-cycle overlap을 cache에 복원한 뒤 Algo2 실행
        # continuous activation을 Algo2 input으로 (use_continuous_overlap=True)
        p._cache['overlap_matrix'] = pd.DataFrame(
            ov_p3, columns=list(range(ov_p3.shape[1]))
        )
        p._cache['cycle_labeled'] = cyc_p3
        p.config.generation.use_continuous_overlap = True

        try:
            algo2_js_list = []
            for trial in range(args.n_algo2):
                print(f"\n  [Algo2 trial {trial+1}/{args.n_algo2}]")
                p.config.generation.random_state = trial
                model = p.run_generation_algo2()
                if model is None:
                    print("  Algo2 실패 (라이브러리 없음)")
                    break

                # 모델 추론 → JS 평가
                from generation import generate_from_model
                notes_label = p._cache['notes_label']
                n_notes = p.config.midi.num_notes
                seq_len = p.config.overlap.total_length

                cont_input = p._cache['activation_continuous']
                X_input = cont_input.values.astype(np.float32)

                # generate_from_model이 없으면 training loss proxy
                # (Algo2는 자체 평가 루틴 미포함 — JS는 별도 계산 필요)
                # 여기서는 학습 곡선의 최저 val_loss를 기록
                history = p._cache.get('training_history', [])
                if history:
                    min_val = min(h.get('val_loss', 9999) for h in history)
                    print(f"    val_loss 최저: {min_val:.6f}")
                    algo2_js_list.append({'trial': trial, 'val_loss': float(min_val)})

            all_results['phase4_algo2'] = {
                'note': 'JS는 Algo2 내부 추론 루틴 필요 — val_loss로 대리 기록',
                'trials': algo2_js_list,
                'global_best_reference': GLOBAL_BEST_ALGO2,
            }
        except Exception as e:
            print(f"  Phase 4 실패: {e}")
            all_results['phase4_algo2'] = {'error': str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # 저장 + 종합 요약
    # ═══════════════════════════════════════════════════════════════════════════
    out_dir  = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'complex_explore_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 종합 요약 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  종합 요약 (Algo1 JS divergence)")
    print("=" * 65)
    print(f"  {'기준선':<38}  {'JS':>8}")
    print(f"  {'─'*38}  {'─'*8}")
    print(f"  {'timeflow α=0.0 (기존 baseline)':<38}  {TF_BASELINE_A0:.4f}")
    print(f"  {'Algo1 best (per-cycle τ, §7.7.1)':<38}  {ALGO1_BEST:.4f}")
    print(f"  {'global best (Algo2 FC, §3.4a)':<38}  {GLOBAL_BEST_ALGO2:.4f}")
    print()
    print(f"  {'설정':<38}  {'JS (mean)':>9}  {'Δ Algo1-best':>12}")
    print(f"  {'─'*38}  {'─'*9}  {'─'*12}")

    p1_best_js = phase1[f'rc{best_rc}']['js_divergence']['mean']
    for label, js_val in [
        (f"Phase 1: complex r_c={best_rc} (binary)", p1_best_js),
        (f"Phase 2: + cont→binary τ=0.5",             js_p2),
        (f"Phase 3: + per-cycle τ_c (median)",         js_p3),
    ]:
        delta_algo1 = (js_val - ALGO1_BEST) / ALGO1_BEST * 100
        sign = '+' if delta_algo1 >= 0 else ''
        print(f"  {label:<38}  {js_val:9.4f}  {sign}{delta_algo1:.1f}%")

    # 최종 verdict
    best_phase_js = min(p1_best_js, js_p2, js_p3)
    print(f"\n  ─ Algo1 최저 달성: JS={best_phase_js:.4f}")
    if best_phase_js < ALGO1_BEST:
        impr = (ALGO1_BEST - best_phase_js) / ALGO1_BEST * 100
        print(f"  ★ Algo1 최고 기록 갱신! +{impr:.1f}% 개선")
    else:
        print(f"  → Algo1 best({ALGO1_BEST}) 미갱신")

    print(f"\n  ─ Global best (Algo2 JS=0.0004) 갱신 여부:")
    print(f"    Algo1 최저({best_phase_js:.4f}) vs Algo2 best({GLOBAL_BEST_ALGO2})")
    ratio = best_phase_js / GLOBAL_BEST_ALGO2
    print(f"    차이 ×{ratio:.0f} — Algo1으로 Algo2 수준 달성은 구조적으로 어려움")
    print(f"    → complex overlap을 Algo2 입력으로 쓸 경우 Phase 4 결과 확인 필요")


if __name__ == '__main__':
    main()
