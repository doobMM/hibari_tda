"""
run_section77_experiments.py — §7.7 Continuous overlap 정교화 세 가지 실험
============================================================================

§7.7에서 제안된 세 가지 향후 과제를 실제로 실험:

1. §7.7.1 Per-cycle 임계값 τ_c 최적화
   - 현재: 모든 cycle에 동일 τ=0.35
   - 새: 각 cycle c에 독립적으로 최적 τ_c 탐색 (greedy coordinate descent)
   - 탐색 범위: τ ∈ {0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7}
   - N=5 trials per evaluation (속도 우선)

2. §7.7.2 Soft activation을 받아들이는 Algorithm 2 변형
   - 현재: binary overlap → Algo2 FC 학습
   - 새: continuous overlap (0~1) → Algo2 FC 학습
   - 비교: binary vs continuous input JS

3. §7.7.3 가중치 함수 w(n) 학습 — 온도 스케일링
   - 현재: w(n) = freq(n) (원곡 빈도 그대로)
   - 새: w(n) = freq(n)^(1/T)  (온도 T로 분포 smooth/sharp 조절)
   - T ∈ {0.3, 0.5, 1.0, 2.0, 3.0, 5.0} 그리드 탐색, N=10

결과: docs/step3_data/section77_experiments.json
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
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict
)
from overlap import build_activation_matrix, build_overlap_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation


# ─── 공통 setup ───────────────────────────────────────────────────────────────
def load_hibari_cache():
    """Tonnetz 캐시 + 전처리 공통 데이터를 반환."""
    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    binary_overlap = cache['overlap'].values   # (T, K) binary

    # note-time 행렬
    notes_label = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']
    notes_dict = p._cache['notes_dict']
    adn_i = p._cache['adn_i']
    T = 1088

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)

    # continuous activation
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)

    return {
        'p': p,
        'cycle_labeled': cycle_labeled,
        'binary_overlap': binary_overlap,
        'cont_activation': cont_act.values.astype(np.float32),
        'note_time_df': note_time_df,
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'inst1_real': p._cache['inst1_real'],
        'inst2_real': p._cache['inst2_real'],
        'T': T,
    }


def run_algo1_once(data, overlap_values, cycle_labeled, seed,
                   notes_counts_override=None):
    random.seed(seed); np.random.seed(seed)
    nc = notes_counts_override if notes_counts_override else data['notes_counts']
    pool = NodePool(data['notes_label'], nc, num_modules=65)
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


def mean_js(data, overlap_values, cycle_labeled, n, seed_base, nc=None):
    js_vals = [
        run_algo1_once(data, overlap_values, cycle_labeled,
                       seed=seed_base + i, notes_counts_override=nc)['js_divergence']
        for i in range(n)
    ]
    return float(np.mean(js_vals)), float(np.std(js_vals, ddof=1) if n > 1 else 0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# §7.7.1 Per-cycle τ_c 최적화
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_percycle_tau(data, n_eval=5):
    """
    각 cycle c에 대해 독립적으로 최적 τ_c를 탐색.
    전략: 다른 cycle은 τ=0.35 고정, cycle c만 변경하며 JS 최소화.
    """
    print("\n" + "=" * 60)
    print("  §7.7.1 Per-cycle τ_c 최적화")
    print(f"  탐색: τ ∈ 각 cycle별로, N={n_eval}회 평가")
    print("=" * 60)

    cycle_labeled = data['cycle_labeled']
    cont_act = data['cont_activation']  # (T, K) continuous
    K = cont_act.shape[1]
    T = data['T']

    TAU_VALS = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]

    # 기준: 모든 cycle τ=0.35 (현재 기본값)
    baseline_ov = (cont_act >= 0.35).astype(np.float32)
    base_mean, base_std = mean_js(data, baseline_ov, cycle_labeled, n_eval, 7000)
    print(f"\n  Baseline (all τ=0.35): JS = {base_mean:.4f} ± {base_std:.4f}")

    # 각 cycle에 대해 최적 τ 탐색
    best_taus = [0.35] * K
    tau_search_results = {}

    for c in range(K):
        best_tau = 0.35
        best_js = float('inf')

        for tau in TAU_VALS:
            # cycle c만 tau로 변경, 나머지는 현재 best_taus
            test_taus = list(best_taus)
            test_taus[c] = tau
            ov = np.zeros_like(cont_act)
            for ci, t in enumerate(test_taus):
                ov[:, ci] = (cont_act[:, ci] >= t).astype(float)

            js_m, _ = mean_js(data, ov, cycle_labeled, n_eval, 7000 + c * 100)
            if js_m < best_js:
                best_js = js_m
                best_tau = tau

        best_taus[c] = best_tau
        tau_search_results[int(c)] = {
            'best_tau': best_tau,
            'best_js_vs_baseline': round(best_js - base_mean, 4),
        }
        print(f"  Cycle {c:2d}: best τ={best_tau:.2f}  JS={best_js:.4f} "
              f"({'↓' if best_js < base_mean else '↑'}"
              f"{abs(best_js-base_mean):.4f})")

    # 최적 τ_c 조합으로 최종 평가 (N=10)
    final_ov = np.zeros_like(cont_act)
    for ci, t in enumerate(best_taus):
        final_ov[:, ci] = (cont_act[:, ci] >= t).astype(float)
    final_mean, final_std = mean_js(data, final_ov, cycle_labeled, 10, 7100)

    improvement = 100 * (base_mean - final_mean) / base_mean
    print(f"\n  최종 (per-cycle τ_c): JS = {final_mean:.4f} ± {final_std:.4f}")
    print(f"  개선율: {improvement:.1f}%")
    print(f"  최적 τ 분포: {[round(t, 2) for t in best_taus]}")

    return {
        'baseline': {'js_mean': base_mean, 'js_std': base_std, 'tau': 0.35},
        'per_cycle_tau': {
            'best_taus': [round(t, 2) for t in best_taus],
            'js_mean': round(final_mean, 4),
            'js_std': round(final_std, 4),
            'improvement_pct': round(improvement, 1),
        },
        'per_cycle_search': tau_search_results,
        'tau_distribution': {
            str(tau): best_taus.count(tau) for tau in TAU_VALS
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# §7.7.2 Soft activation을 받아들이는 Algorithm 2 변형
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_soft_activation_algo2(data):
    """
    Algo2 (FC)를 binary overlap vs continuous overlap input으로 비교.
    """
    print("\n" + "=" * 60)
    print("  §7.7.2 Soft activation → Algorithm 2 (FC)")
    print("=" * 60)

    try:
        import torch
        from generation import (
            prepare_training_data, MusicGeneratorFC,
            train_model, build_onehot_matrix
        )
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        print(f"  torch/sklearn 없음: {e}")
        return {'error': str(e)}

    p = data['p']
    cycle_labeled = data['cycle_labeled']
    binary_ov = data['binary_overlap']        # (T, K) binary
    cont_ov   = data['cont_activation']       # (T, K) continuous

    notes_label = data['notes_label']
    inst1_real  = data['inst1_real']
    inst2_real  = data['inst2_real']
    T = data['T']
    N = len(notes_label)
    K = binary_ov.shape[1]

    results = {}

    for mode, overlap_for_train in [('binary', binary_ov), ('continuous', cont_ov)]:
        print(f"\n  [{mode}] overlap → Algo2 FC 학습")
        print(f"    X range: [{overlap_for_train.min():.3f}, {overlap_for_train.max():.3f}]")

        X, y = prepare_training_data(
            overlap_for_train,
            [inst1_real, inst2_real],
            notes_label, T, N
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = MusicGeneratorFC(num_cycles=K, num_notes=N,
                                 hidden_dim=128, dropout=0.3)

        t0 = time.time()
        history = train_model(
            model, X_train, y_train, X_val, y_val,
            epochs=80, lr=0.001, batch_size=32, model_type='fc'
        )
        train_time = time.time() - t0
        print(f"    학습 완료: {train_time:.1f}s")

        # 생성 및 평가 (N=5)
        model.eval()
        import torch

        def generate_from_dl(model, overlap_inp):
            """DL 모델로 note 시퀀스를 생성하여 (start, pitch, end) 리스트로 반환."""
            with torch.no_grad():
                x = torch.FloatTensor(overlap_inp)      # (T, K)
                logits = model(x)                        # (T, N)
                probs = torch.sigmoid(logits).numpy()    # (T, N) in [0,1]

            gen = []
            for t in range(T):
                for n_idx in range(N):
                    if probs[t, n_idx] > 0.5:
                        # 1-indexed note lookup
                        for note, lbl in notes_label.items():
                            if lbl - 1 == n_idx:
                                pitch, dur = note
                                gen.append((t, pitch, t + dur))
                                break
            return gen

        js_trials = []
        for i in range(5):
            gen = generate_from_dl(model, overlap_for_train)
            if not gen:
                js_trials.append(1.0)
                continue
            m = evaluate_generation(gen, [inst1_real, inst2_real], notes_label, name="")
            js_trials.append(m['js_divergence'])

        js_arr = np.array(js_trials)
        final_val_loss = history[-1]['val_loss'] if history else None

        results[mode] = {
            'js_mean': round(float(js_arr.mean()), 4),
            'js_std':  round(float(js_arr.std(ddof=1) if len(js_trials)>1 else 0.0), 4),
            'train_time_s': round(train_time, 1),
            'final_val_loss': round(float(final_val_loss), 4) if final_val_loss else None,
            'n_trials': len(js_trials),
        }
        print(f"    JS = {js_arr.mean():.4f} ± {js_arr.std(ddof=1):.4f}")

    if 'binary' in results and 'continuous' in results:
        b = results['binary']['js_mean']
        c = results['continuous']['js_mean']
        improvement = 100 * (b - c) / b if b > 0 else 0
        results['improvement_pct'] = round(improvement, 1)
        print(f"\n  binary→continuous 개선: {improvement:+.1f}%")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# §7.7.3 가중치 함수 w(n) 학습 — 온도 스케일링
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_learnable_weight(data, n_eval=10):
    """
    w(n) = freq(n)^(1/T) 온도 스케일링으로 샘플링 분포 조절.
    T < 1: 고빈도 note에 집중 (sharp)
    T = 1: 원래 빈도 (current)
    T > 1: 균등화 (smooth)
    T → ∞: 균등 분포
    """
    print("\n" + "=" * 60)
    print("  §7.7.3 가중치 함수 w(n) 학습 — 온도 스케일링")
    print(f"  N={n_eval}회 평가")
    print("=" * 60)

    from collections import Counter
    cycle_labeled = data['cycle_labeled']
    binary_ov = data['binary_overlap']
    notes_label = data['notes_label']
    notes_counts = data['notes_counts']

    TEMPERATURES = [0.3, 0.5, 1.0, 2.0, 3.0, 5.0]

    # 기준: T=1.0 (현재 기본값)
    base_mean, base_std = mean_js(data, binary_ov, cycle_labeled, n_eval, 8000)
    print(f"\n  Baseline (T=1.0): JS = {base_mean:.4f} ± {base_std:.4f}")

    results_t = {}
    for T in TEMPERATURES:
        # 온도 스케일링된 notes_counts 생성
        scaled_counts = Counter()
        for note, cnt in notes_counts.items():
            # freq^(1/T)에 비례하도록 count 조정
            # 정수가 필요하므로 max(1, round(cnt^(1/T))) 사용
            new_cnt = max(1, round(cnt ** (1.0 / T)))
            scaled_counts[note] = new_cnt

        js_m, js_s = mean_js(
            data, binary_ov, cycle_labeled, n_eval, 8000,
            nc=scaled_counts
        )
        improvement = 100 * (base_mean - js_m) / base_mean
        results_t[str(T)] = {
            'temperature': T,
            'js_mean': round(js_m, 4),
            'js_std':  round(js_s, 4),
            'improvement_pct': round(improvement, 1),
        }
        mark = "★" if js_m < base_mean else " "
        print(f"  T={T:>4.1f}: JS = {js_m:.4f} ± {js_s:.4f}  "
              f"({'↓' if js_m < base_mean else '↑'}{abs(improvement):.1f}%)  {mark}")

    best_T = min(results_t.items(), key=lambda x: x[1]['js_mean'])[0]
    print(f"\n  최적 T = {best_T}")

    return {
        'baseline': {'temperature': 1.0, 'js_mean': round(base_mean, 4),
                     'js_std': round(base_std, 4)},
        'temperature_grid': results_t,
        'best_temperature': float(best_T),
        'interpretation': {
            'T<1': '고빈도 note 집중 (sharp sampling)',
            'T=1': '원래 빈도 (current default)',
            'T>1': '균등화 (uniform-like sampling)',
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  §7.7 Continuous overlap 정교화 — 세 가지 실험")
    print("=" * 70)

    print("\n[공통 데이터 로드]")
    data = load_hibari_cache()
    K = data['binary_overlap'].shape[1]
    print(f"  cycle 수: K={K}, T={data['T']}")
    print(f"  continuous activation range: "
          f"[{data['cont_activation'].min():.3f}, {data['cont_activation'].max():.3f}]")

    all_results = {}

    # §7.7.1 Per-cycle τ 최적화
    print("\n\n" + "=" * 70)
    r1 = experiment_percycle_tau(data, n_eval=5)
    all_results['sec77_1_percycle_tau'] = r1

    # §7.7.2 Soft activation Algo2
    print("\n\n" + "=" * 70)
    r2 = experiment_soft_activation_algo2(data)
    all_results['sec77_2_soft_activation_algo2'] = r2

    # §7.7.3 Learnable weight (temperature)
    print("\n\n" + "=" * 70)
    r3 = experiment_learnable_weight(data, n_eval=10)
    all_results['sec77_3_learnable_weight'] = r3

    # 결과 저장
    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/section77_experiments.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n\nJSON 저장: {out}")

    # 요약
    print("\n" + "=" * 60)
    print("  §7.7 실험 요약")
    print("=" * 60)

    print("\n  §7.7.1 Per-cycle τ:")
    r = all_results['sec77_1_percycle_tau']
    print(f"    Baseline τ=0.35: JS = {r['baseline']['js_mean']:.4f}")
    print(f"    Per-cycle τ_c:   JS = {r['per_cycle_tau']['js_mean']:.4f} "
          f"({r['per_cycle_tau']['improvement_pct']:+.1f}%)")

    print("\n  §7.7.2 Soft activation (Algo2 FC):")
    r = all_results['sec77_2_soft_activation_algo2']
    if 'error' not in r:
        for mode in ['binary', 'continuous']:
            if mode in r:
                print(f"    {mode:12s}: JS = {r[mode]['js_mean']:.4f}")
        if 'improvement_pct' in r:
            print(f"    개선: {r['improvement_pct']:+.1f}%")

    print("\n  §7.7.3 Learnable weight (temperature):")
    r = all_results['sec77_3_learnable_weight']
    print(f"    Baseline (T=1.0): JS = {r['baseline']['js_mean']:.4f}")
    print(f"    Best T={r['best_temperature']}: "
          f"JS = {r['temperature_grid'][str(r['best_temperature'])]['js_mean']:.4f}")


if __name__ == "__main__":
    main()
