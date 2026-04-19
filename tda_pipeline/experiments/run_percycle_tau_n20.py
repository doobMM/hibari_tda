"""
run_percycle_tau_n20.py — A-2 Per-cycle τ_c N=20 재검증
=========================================================

section77_experiments.json에서 greedy(N=5)로 찾은 최적 τ_c 벡터를
N=20 평가로 통계적 신뢰성을 확보.

목표:
  - baseline (전체 τ=0.35) N=20 평가
  - per-cycle τ_c (greedy 결과 고정) N=20 평가
  - t-test p-value로 유의성 확인
  - 과적합 여부 검증 (N=5 greedy 결과가 N=20에서도 유지되는지)

결과: docs/step3_data/percycle_tau_n20_results.json
"""

import sys, os, json, time, random
import numpy as np
import pandas as pd
import pickle
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict
)
from overlap import build_activation_matrix, build_overlap_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

N_EVAL = 20
SEED_BASE_BASELINE = 7000
SEED_BASE_PERCYCLE = 7200  # baseline과 다른 seed 사용 (독립 샘플)


# ─── 공통 setup (section77와 동일) ─────────────────────────────────────────────
def load_hibari_cache():
    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']

    notes_label  = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']
    adn_i        = p._cache['adn_i']
    T = 1088

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, p._cache['notes_dict'])
    nodes_list = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)

    # continuous activation 필요 (threshold 적용해서 binary로 변환)
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)

    return {
        'cycle_labeled': cycle_labeled,
        'cont_activation': cont_act.values.astype(np.float32),
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'inst1_real': p._cache['inst1_real'],
        'inst2_real': p._cache['inst2_real'],
        'T': T,
    }


def run_algo1_once(data, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False
    )
    return evaluate_generation(
        generated,
        [data['inst1_real'], data['inst2_real']],
        data['notes_label'], name=""
    )


def evaluate_n20(data, overlap_values, cycle_labeled, n, seed_base, label=""):
    js_vals = []
    t0 = time.time()
    for i in range(n):
        r = run_algo1_once(data, overlap_values, cycle_labeled, seed=seed_base + i)
        js_vals.append(r['js_divergence'])
        if i % 5 == 0 or i == n - 1:
            print(f"    [{i+1:2d}/{n}] JS={js_vals[-1]:.4f}  {time.time()-t0:.1f}s")
    arr = np.array(js_vals)
    return arr, float(arr.mean()), float(arr.std(ddof=1))


def main():
    print("=" * 65)
    print("  A-2 Per-cycle τ_c N=20 재검증")
    print(f"  N={N_EVAL} 평가 (greedy 결과 고정 → 통계적 신뢰 확보)")
    print("=" * 65)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 이전 greedy 결과 로드
    prev_path = 'docs/step3_data/section77_experiments.json'
    if not os.path.exists(prev_path):
        print(f"  [오류] {prev_path} 없음. run_section77_experiments.py 먼저 실행.")
        return

    with open(prev_path) as f:
        prev = json.load(f)
    r77 = prev.get('sec77_1_percycle_tau', {})
    best_taus = r77.get('per_cycle_tau', {}).get('best_taus')

    if best_taus is None:
        print("  [오류] best_taus 없음. section77 실험 결과 확인.")
        return

    K = len(best_taus)
    prev_js_n5 = r77.get('per_cycle_tau', {}).get('js_mean')
    prev_base  = r77.get('baseline', {}).get('js_mean')
    print(f"\n  이전 greedy(N=5) 결과:")
    print(f"    K={K} cycles")
    print(f"    baseline(τ=0.35): JS = {prev_base:.4f}")
    print(f"    per-cycle τ_c:    JS = {prev_js_n5:.4f}")
    print(f"    best_taus: {best_taus}")

    print("\n[공통 데이터 로드]")
    data = load_hibari_cache()
    cont_act = data['cont_activation']
    cycle_labeled = data['cycle_labeled']

    K_actual = cont_act.shape[1]
    if K_actual != K:
        print(f"  [경고] cycle 수 불일치: best_taus K={K}, 현재 K={K_actual}")
        print(f"  τ 벡터를 현재 K={K_actual}에 맞게 조정...")
        if K_actual < K:
            best_taus = best_taus[:K_actual]
        else:
            # 부족한 부분은 0.35로 채우기
            best_taus = best_taus + [0.35] * (K_actual - K)
        K = K_actual

    # ─ Baseline: 전체 τ=0.35, N=20 ─────────────────────────────────────────
    print(f"\n[Baseline (τ=0.35 일괄) N={N_EVAL} 평가]")
    baseline_ov = (cont_act >= 0.35).astype(np.float32)
    base_arr, base_mean, base_std = evaluate_n20(
        data, baseline_ov, cycle_labeled, N_EVAL, SEED_BASE_BASELINE, "baseline"
    )
    print(f"  → JS = {base_mean:.4f} ± {base_std:.4f}")

    # ─ Per-cycle τ_c: N=20 ──────────────────────────────────────────────────
    print(f"\n[Per-cycle τ_c (greedy 결과 고정) N={N_EVAL} 평가]")
    percycle_ov = np.zeros_like(cont_act)
    for ci, tau in enumerate(best_taus):
        percycle_ov[:, ci] = (cont_act[:, ci] >= tau).astype(float)

    pc_arr, pc_mean, pc_std = evaluate_n20(
        data, percycle_ov, cycle_labeled, N_EVAL, SEED_BASE_PERCYCLE, "per-cycle"
    )
    print(f"  → JS = {pc_mean:.4f} ± {pc_std:.4f}")

    # ─ t-test ───────────────────────────────────────────────────────────────
    t_stat, p_value = stats.ttest_ind(base_arr, pc_arr, alternative='greater')
    improvement = 100 * (base_mean - pc_mean) / base_mean

    print(f"\n[통계 검정]")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value:     {p_value:.4f}  {'★ 유의 (p<0.05)' if p_value < 0.05 else '(유의하지 않음)'}")
    print(f"  개선율:      {improvement:+.1f}%")

    # 과적합 여부 판단
    if pc_mean < base_mean:
        overfitting = "개선 유지 (과적합 아님)"
    else:
        overfitting = "역전 (과적합 의심)"
    print(f"  N=5→N=20:   {overfitting}")
    print(f"  (N=5 결과: JS={prev_js_n5:.4f}, N=20 결과: JS={pc_mean:.4f})")

    results = {
        'experiment': 'A-2 Per-cycle τ_c N=20 재검증',
        'n_eval': N_EVAL,
        'n_cycles': K,
        'best_taus_from_greedy': best_taus,
        'baseline': {
            'tau': 0.35,
            'js_mean': round(base_mean, 4),
            'js_std':  round(base_std, 4),
            'all_js':  [round(float(x), 4) for x in base_arr],
        },
        'per_cycle_tau': {
            'best_taus': best_taus,
            'js_mean': round(pc_mean, 4),
            'js_std':  round(pc_std, 4),
            'improvement_pct': round(improvement, 1),
            'all_js': [round(float(x), 4) for x in pc_arr],
        },
        'statistical_test': {
            't_statistic': round(float(t_stat), 4),
            'p_value':     round(float(p_value), 4),
            'significant': bool(p_value < 0.05),
            'hypothesis':  'baseline > per_cycle (단측)',
        },
        'comparison_n5_vs_n20': {
            'n5_js_mean': prev_js_n5,
            'n20_js_mean': round(pc_mean, 4),
            'overfitting_verdict': overfitting,
        },
    }

    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/percycle_tau_n20_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")
    print("\n[완료]")


if __name__ == "__main__":
    main()
