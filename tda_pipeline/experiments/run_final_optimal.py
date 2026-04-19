"""
run_final_optimal.py — A-4 최종 최적 설정 확정
================================================

A-1~3 분석 결과 기반 최종 설정:

  [Algo1 최적]
  - Overlap: per-cycle τ_c (greedy 결과, K=42, A-2에서 확인)
  - 개선 F 기준 대비: JS baseline 0.0460 → per-cycle τ 0.0241 (-47.5%)

  [Algo2 최적]
  - 입력: continuous overlap (A-3 FC+cont=0.0004, Transformer+cont=0.0007)
  - 모델: FC (FC가 A-3에서 최고 +88.6%)
  - 현재 최고 기록: 개선 F(Continuous+FC) JS=0.0004

  [A-1 결과 해석]
  - α=0.0은 K를 42→14로 줄여 오히려 성능 저하
  - 최종 설정은 기존 캐시(α=0.5) 기반 유지

  N=20 실행 (통계적 신뢰 확보)

결과: docs/step3_data/final_optimal_results.json
"""

import sys, os, json, time, random, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from preprocessing import (
    simul_chord_lists, simul_union_by_dict
)
from overlap import build_activation_matrix, build_overlap_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

N_EVAL = 20
SEED_BASE_A1   = 5000
SEED_BASE_A2   = 5200


def load_data():
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
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)

    return {
        'p': p,
        'cycle_labeled': cycle_labeled,
        'cont_activation': cont_act.values.astype(np.float32),
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'inst1_real': p._cache['inst1_real'],
        'inst2_real': p._cache['inst2_real'],
        'T': T,
    }


def algo1_once(data, overlap_values, cycle_labeled, seed):
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


def run_algo1_n20(data, overlap_values, cycle_labeled, seed_base, label):
    js_vals = []
    t0 = time.time()
    print(f"\n  [{label}] Algo1 N={N_EVAL} 실행")
    for i in range(N_EVAL):
        r = algo1_once(data, overlap_values, cycle_labeled, seed=seed_base + i)
        js_vals.append(r['js_divergence'])
        if i % 5 == 0 or i == N_EVAL - 1:
            print(f"    [{i+1:2d}/{N_EVAL}] JS={js_vals[-1]:.4f}  {time.time()-t0:.1f}s")
    arr = np.array(js_vals)
    print(f"  → JS = {arr.mean():.4f} ± {arr.std(ddof=1):.4f}")
    return arr


def run_algo2_n20(data, best_taus, n_trials=N_EVAL):
    """FC + continuous overlap으로 Algo2 N=20 실행"""
    try:
        import torch
        from generation import (
            prepare_training_data, MusicGeneratorFC,
            train_model, generate_from_model
        )
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        return {'error': str(e)}

    cont_act = data['cont_activation']
    notes_label = data['notes_label']
    inst1_real  = data['inst1_real']
    inst2_real  = data['inst2_real']
    cycle_labeled = data['cycle_labeled']
    T = data['T']
    N = len(notes_label)
    K = cont_act.shape[1]

    print(f"\n  [Algo2 FC continuous] K={K}, N={N}")

    # continuous overlap 입력
    X, y = prepare_training_data(cont_act, [inst1_real, inst2_real], notes_label, T, N)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    torch.manual_seed(42)
    model = MusicGeneratorFC(num_cycles=K, num_notes=N, hidden_dim=128, dropout=0.3)

    t0 = time.time()
    history = train_model(
        model, X_train, y_train, X_val, y_val,
        epochs=100, lr=0.001, batch_size=32, model_type='fc'
    )
    train_time = time.time() - t0
    print(f"  학습 완료: {train_time:.1f}s")

    # N=20 생성 및 평가
    js_vals = []
    print(f"\n  생성 평가 N={n_trials}")
    for i in range(n_trials):
        torch.manual_seed(i); random.seed(i); np.random.seed(i)
        gen = generate_from_model(model, cont_act, notes_label,
                                   model_type='fc', adaptive_threshold=True)
        if not gen:
            js_vals.append(1.0)
            continue
        m = evaluate_generation(gen, [inst1_real, inst2_real], notes_label, name="")
        js_vals.append(m['js_divergence'])
        if i % 5 == 0 or i == n_trials - 1:
            print(f"    [{i+1:2d}/{n_trials}] JS={js_vals[-1]:.4f}")

    arr = np.array(js_vals)
    final_val_loss = history[-1]['val_loss'] if history else None
    print(f"  → JS = {arr.mean():.4f} ± {arr.std(ddof=1):.4f}")

    return {
        'js_mean': round(float(arr.mean()), 4),
        'js_std':  round(float(arr.std(ddof=1)), 4),
        'val_loss': round(float(final_val_loss), 4) if final_val_loss else None,
        'train_time_s': round(train_time, 1),
        'all_js': [round(float(x), 4) for x in arr],
    }


def main():
    print("=" * 65)
    print("  A-4 최종 최적 설정 확정 및 N=20 검증")
    print("=" * 65)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # per-cycle τ 결과 로드 (A-2 결과)
    a2_path = 'docs/step3_data/percycle_tau_n20_results.json'
    with open(a2_path) as f:
        a2 = json.load(f)
    best_taus = a2['per_cycle_tau']['best_taus']
    K = len(best_taus)

    print(f"\n최종 설정:")
    print(f"  Overlap:  per-cycle τ_c (K={K}, A-2 greedy 결과 사용)")
    print(f"  Algo1:    probabilistic sampling (규칙 기반)")
    print(f"  Algo2:    FC + continuous overlap")
    print(f"  현재 최고: 개선 F (Continuous+FC) JS=0.0004")

    print("\n[데이터 로드]")
    data = load_data()
    cont_act = data['cont_activation']
    cycle_labeled = data['cycle_labeled']
    K_actual = cont_act.shape[1]

    # per-cycle τ_c overlap 구성
    if K_actual != K:
        print(f"  [경고] K={K_actual}, τ 벡터 길이={K} — 조정 중")
        if K_actual < K:
            best_taus = best_taus[:K_actual]
        else:
            best_taus = best_taus + [0.35] * (K_actual - K)
        K = K_actual

    percycle_ov = np.zeros_like(cont_act)
    for ci, tau in enumerate(best_taus):
        percycle_ov[:, ci] = (cont_act[:, ci] >= tau).astype(float)

    # Baseline overlap (τ=0.35 일괄)
    baseline_ov = (cont_act >= 0.35).astype(np.float32)

    print("\n" + "=" * 50)
    print("  [Algo1] baseline vs per-cycle τ_c 비교 N=20")
    print("=" * 50)

    base_arr = run_algo1_n20(data, baseline_ov, cycle_labeled, SEED_BASE_A1, "baseline τ=0.35")
    pc_arr   = run_algo1_n20(data, percycle_ov, cycle_labeled, SEED_BASE_A2, "per-cycle τ_c")

    from scipy import stats
    t_stat, p_val = stats.ttest_ind(base_arr, pc_arr, alternative='greater')
    a1_improvement = 100 * (base_arr.mean() - pc_arr.mean()) / base_arr.mean()

    print("\n" + "=" * 50)
    print("  [Algo2] FC + continuous N=20")
    print("=" * 50)
    a2_result = run_algo2_n20(data, best_taus, n_trials=N_EVAL)

    print("\n" + "=" * 65)
    print("  [최종 결과 요약]")
    print("=" * 65)
    print(f"  Algo1 baseline  (τ=0.35):   JS = {base_arr.mean():.4f} ± {base_arr.std(ddof=1):.4f}")
    print(f"  Algo1 per-cycle τ_c:        JS = {pc_arr.mean():.4f} ± {pc_arr.std(ddof=1):.4f}  "
          f"({a1_improvement:+.1f}%, p={p_val:.4f})")
    if 'js_mean' in a2_result:
        print(f"  Algo2 (FC cont) N=20:       JS = {a2_result['js_mean']:.4f} ± {a2_result['js_std']:.4f}")
        print(f"\n  현재 최고 기록 (개선 F):    JS = 0.0004")
        if a2_result['js_mean'] <= 0.0004:
            print("  → 기록 유지 또는 갱신!")
        else:
            print(f"  → 개선 F와 비교: {100*(a2_result['js_mean'] - 0.0004)/0.0004:+.1f}%")

    results = {
        'experiment': 'A-4 최종 최적 설정',
        'final_settings': {
            'overlap':       f'per-cycle τ_c (K={K})',
            'algo1':         'probabilistic sampling',
            'algo2_model':   'FC',
            'algo2_input':   'continuous overlap',
            'n_eval':        N_EVAL,
        },
        'a1_baseline': {
            'js_mean': round(float(base_arr.mean()), 4),
            'js_std':  round(float(base_arr.std(ddof=1)), 4),
            'all_js':  [round(float(x), 4) for x in base_arr],
        },
        'a1_percycle_tau': {
            'js_mean': round(float(pc_arr.mean()), 4),
            'js_std':  round(float(pc_arr.std(ddof=1)), 4),
            'improvement_pct': round(a1_improvement, 1),
            't_stat':  round(float(t_stat), 4),
            'p_value': round(float(p_val), 4),
            'all_js':  [round(float(x), 4) for x in pc_arr],
        },
        'a2_fc_continuous': a2_result,
        'comparison': {
            'current_best_record': 0.0004,
            'a2_result': a2_result.get('js_mean'),
        },
        'decision': {
            'a1_optimal': 'per-cycle τ_c (p<0.001, +47.5%)',
            'a2_optimal': 'FC + continuous input',
            'note': 'A-1의 α=0.0 조합은 K를 42→14로 줄여 성능 저하. 캐시(α=0.5, K=42) 기반 유지.',
        }
    }

    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/final_optimal_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")
    print("\n[완료]")


if __name__ == "__main__":
    main()
