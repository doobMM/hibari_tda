"""
run_step3_continuous.py — Continuous overlap matrix 실험.

목적:
  본 실험은 Algorithm 1을 다음 두 가지 overlap 형식으로 비교한다.
    (a) 이진 (binary) — 기존 방식, build_overlap_matrix
    (b) 연속값 (continuous) — build_activation_matrix(continuous=True)
        cycle별 vertex의 활성 비율 × 희귀도 가중치
  cycle_labeled와 distance metric은 동일 (Tonnetz 캐시 사용),
  Algorithm 1 자체는 동일. 다만 입력되는 overlap_matrix만 형태가 다르다.

각 설정 N=20회 반복 → mean ± std 보고.
결과: docs/step3_data/step3_continuous_results.json
"""
import os, sys, json, time, random, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation
from overlap import build_activation_matrix
from preprocessing import simul_chord_lists, simul_union_by_dict

N_REPEATS = 20


def setup_pipeline():
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    return p


def build_note_time_df(p):
    """원곡의 (T, N_notes) 활성 행렬을 만든다."""
    notes_label = p._cache['notes_label']
    notes_dict = p._cache['notes_dict']
    adn_i = p._cache['adn_i']

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))
    T = 1088
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


def run_algo1(p, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33

    t0 = time.time()
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False)
    elapsed = time.time() - t0

    res = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        p._cache['notes_label'], name="")
    res['elapsed_s'] = elapsed
    return res


def aggregate(trials, keys):
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


METRIC_KEYS = ['js_divergence', 'kl_divergence', 'note_coverage',
               'n_notes', 'pitch_count', 'elapsed_s']


def main():
    print("Step 3 continuous overlap 실험")
    print(f"각 설정 {N_REPEATS}회 반복")

    p = setup_pipeline()

    # Tonnetz cache의 cycle_labeled 사용
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    binary_overlap = cache['overlap'].values  # (T, K)
    print(f"\n  Tonnetz cycle_labeled: {len(cycle_labeled)} cycles")
    print(f"  Binary overlap shape: {binary_overlap.shape}")

    # 원곡 note-time 행렬을 만들고, 그것에서 binary/continuous 활성화 둘 다 계산
    note_time_df = build_note_time_df(p)
    print(f"  note_time_df shape: {note_time_df.shape}")

    activation_binary = build_activation_matrix(
        note_time_df, cycle_labeled, continuous=False)
    activation_continuous = build_activation_matrix(
        note_time_df, cycle_labeled, continuous=True)

    print(f"\n  Activation binary  range: "
          f"[{activation_binary.values.min():.3f}, {activation_binary.values.max():.3f}]")
    print(f"  Activation cont. range:  "
          f"[{activation_continuous.values.min():.3f}, {activation_continuous.values.max():.3f}]")
    print(f"  Activation binary  mean: {activation_binary.values.mean():.4f}")
    print(f"  Activation cont. mean:  {activation_continuous.values.mean():.4f}")

    # ── Setting A: 기존 binary overlap (cache에 들어있는 것) ──
    print(f"\n[A] Tonnetz binary overlap (기존 캐시, {N_REPEATS}회)")
    trials_a = []
    for i in range(N_REPEATS):
        r = run_algo1(p, binary_overlap, cycle_labeled, seed=5000 + i)
        trials_a.append(r)
        if i % 5 == 0 or i == N_REPEATS - 1:
            print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
    agg_a = aggregate(trials_a, METRIC_KEYS)
    print(f"  → JS = {agg_a['js_divergence']['mean']:.4f} "
          f"± {agg_a['js_divergence']['std']:.4f}")

    # ── Setting B: continuous activation, 직접 사용 ──
    print(f"\n[B] Tonnetz continuous overlap (활성화 직접 사용, {N_REPEATS}회)")
    cont_overlap = activation_continuous.values.astype(np.float32)
    trials_b = []
    for i in range(N_REPEATS):
        r = run_algo1(p, cont_overlap, cycle_labeled, seed=5000 + i)
        trials_b.append(r)
        if i % 5 == 0 or i == N_REPEATS - 1:
            print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
    agg_b = aggregate(trials_b, METRIC_KEYS)
    print(f"  → JS = {agg_b['js_divergence']['mean']:.4f} "
          f"± {agg_b['js_divergence']['std']:.4f}")

    # ── Setting C: continuous → binarize at threshold τ_c ──
    # 임계값 τ_c 이상이면 1
    for tau in [0.3, 0.5, 0.7]:
        print(f"\n[C@τ={tau}] Tonnetz continuous → binarize at {tau} ({N_REPEATS}회)")
        ov = (cont_overlap >= tau).astype(np.float32)
        density = ov.mean()
        print(f"  binarized density: {density:.4f}")
        trials_c = []
        for i in range(N_REPEATS):
            r = run_algo1(p, ov, cycle_labeled, seed=5000 + i)
            trials_c.append(r)
            if i % 5 == 0 or i == N_REPEATS - 1:
                print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
        agg = aggregate(trials_c, METRIC_KEYS)
        agg['density'] = float(density)
        print(f"  → JS = {agg['js_divergence']['mean']:.4f} "
              f"± {agg['js_divergence']['std']:.4f}")
        if tau == 0.3:
            agg_c03 = agg
        elif tau == 0.5:
            agg_c05 = agg
        else:
            agg_c07 = agg

    # ── 결과 저장 ──
    results = {
        'n_repeats': N_REPEATS,
        'A_binary_cached':       agg_a,
        'B_continuous_direct':   agg_b,
        'C_continuous_thr_0.3':  agg_c03,
        'C_continuous_thr_0.5':  agg_c05,
        'C_continuous_thr_0.7':  agg_c07,
    }
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'step3_continuous_results.json'),
              'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60)
    print("  요약")
    print("="*60)
    for label, agg in [
        ('A binary (cached)',         agg_a),
        ('B continuous (direct)',     agg_b),
        ('C continuous→bin τ=0.3',   agg_c03),
        ('C continuous→bin τ=0.5',   agg_c05),
        ('C continuous→bin τ=0.7',   agg_c07),
    ]:
        js = agg['js_divergence']
        print(f"  {label:30s}  JS = {js['mean']:.4f} ± {js['std']:.4f}")


if __name__ == '__main__':
    main()
