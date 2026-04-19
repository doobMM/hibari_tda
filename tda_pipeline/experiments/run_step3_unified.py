"""
run_step3_unified.py — Step 3 통합 실험 러너

기존 2개 파일을 통합:
  run_step3_experiments.py → --mode baselines, --mode ablations
  run_step3_continuous.py  → --mode continuous

사용법:
  python run_step3_unified.py --mode baselines
  python run_step3_unified.py --mode ablations
  python run_step3_unified.py --mode continuous
  python run_step3_unified.py --mode all          # 3개 모두 실행
"""
import os, sys, json, time, random, pickle, argparse
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


# ═══════════════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════════════

METRIC_KEYS = ['js_divergence', 'kl_divergence', 'note_coverage',
               'n_notes', 'pitch_count', 'elapsed_s']


def setup_pipeline():
    """TDAMusicPipeline을 전처리만 수행한 상태로 준비."""
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    return p


def load_metric_cache(metric: str):
    path = os.path.join("cache", f"metric_{metric}.pkl")
    with open(path, 'rb') as f:
        return pickle.load(f)


def run_algo1_once(p, overlap_values, cycle_labeled, seed):
    """Algorithm 1을 한 번 실행하고 평가 지표를 반환."""
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
        max_resample=50, verbose=False)
    elapsed = time.time() - t0

    result = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        notes_label, name="")
    result['elapsed_s'] = elapsed
    return result


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


# ═══════════════════════════════════════════════════════════════════════
# Mode: baselines — 거리 함수 비교 (N=20)
# ═══════════════════════════════════════════════════════════════════════

def mode_baselines(args):
    """4가지 거리 함수(frequency/tonnetz/voice_leading/dft) 비교."""
    print("\n" + "=" * 60)
    print("  실험 1: Distance function baseline 비교")
    print("=" * 60)

    p = setup_pipeline()
    print(f"전처리 완료: notes_label={len(p._cache['notes_label'])}")

    results = {}
    metrics_to_test = ['frequency', 'tonnetz', 'voice_leading', 'dft']

    for metric in metrics_to_test:
        print(f"\n  → {metric} ({args.n_repeats}회 반복)")
        try:
            cache = load_metric_cache(metric)
        except FileNotFoundError:
            print(f"    (캐시 없음, skip)")
            continue
        overlap_df = cache['overlap']
        cycle_labeled = cache['cycle_labeled']
        overlap_values = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df

        trials = []
        for i in range(args.n_repeats):
            r = run_algo1_once(p, overlap_values, cycle_labeled, seed=1000 + i)
            trials.append(r)
            print(f"    [{i+1:2d}] JS={r['js_divergence']:.4f}  "
                  f"notes={r['n_notes']}  pitches={r['pitch_count']}  "
                  f"cov={r['note_coverage']:.2f}")

        agg = aggregate(trials, METRIC_KEYS)
        agg['n_cycles'] = len(cycle_labeled)
        agg['n_repeats'] = args.n_repeats
        results[metric] = agg
        print(f"    JS: {agg['js_divergence']['mean']:.4f} "
              f"± {agg['js_divergence']['std']:.4f}")

    # 결과 저장
    out = {'n_repeats': args.n_repeats, 'experiment_1_baselines': results}
    out_path = os.path.join("output", "step3_results_baselines.json")
    os.makedirs("output", exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # 요약
    print("\n[요약] Distance baselines")
    for metric, agg in results.items():
        js = agg['js_divergence']
        print(f"  {metric:15s}: JS = {js['mean']:.4f} ± {js['std']:.4f}  "
              f"(K={agg.get('n_cycles','?')})")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Mode: ablations — Cycle subset ablation
# ═══════════════════════════════════════════════════════════════════════

def mode_ablations(args):
    """Tonnetz full vs K=10, K=17 cycle subset ablation."""
    print("\n" + "=" * 60)
    print("  실험 2: Ablation study")
    print("=" * 60)

    p = setup_pipeline()
    print(f"전처리 완료: notes_label={len(p._cache['notes_label'])}")

    cache = load_metric_cache('tonnetz')
    overlap_df = cache['overlap']
    cycle_labeled = cache['cycle_labeled']
    overlap_full = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df
    n_cycles = len(cycle_labeled)
    results = {}

    # Full tonnetz
    print(f"\n  (a) Full cycle set (K={n_cycles}, Tonnetz)")
    trials = []
    for i in range(args.n_repeats):
        r = run_algo1_once(p, overlap_full, cycle_labeled, seed=2000 + i)
        trials.append(r)
    results['full_tonnetz'] = aggregate(trials, METRIC_KEYS)
    results['full_tonnetz']['config'] = f'K={n_cycles}, Tonnetz, full'
    results['full_tonnetz']['n_cycles'] = n_cycles
    print(f"    JS: {results['full_tonnetz']['js_divergence']['mean']:.4f} "
          f"± {results['full_tonnetz']['js_divergence']['std']:.4f}")

    # Subsets
    for k_sub in [10, 17]:
        if k_sub >= n_cycles:
            continue
        print(f"\n  (b) Cycle subset K={k_sub} (first {k_sub} cycles)")
        cycle_list = list(cycle_labeled.items())[:k_sub]
        cycle_sub = dict(cycle_list)
        overlap_sub = overlap_full[:, :k_sub]
        trials = []
        for i in range(args.n_repeats):
            r = run_algo1_once(p, overlap_sub, cycle_sub, seed=3000 + i)
            trials.append(r)
        key = f'subset_K{k_sub}'
        results[key] = aggregate(trials, METRIC_KEYS)
        results[key]['config'] = f'K={k_sub}, Tonnetz, prefix subset'
        results[key]['n_cycles'] = k_sub
        print(f"    JS: {results[key]['js_divergence']['mean']:.4f} "
              f"± {results[key]['js_divergence']['std']:.4f}")

    # 결과 저장
    out = {'n_repeats': args.n_repeats, 'experiment_2_ablations': results}
    out_path = os.path.join("output", "step3_results_ablations.json")
    os.makedirs("output", exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # 요약
    print("\n[요약] Ablation")
    for key, agg in results.items():
        js = agg['js_divergence']
        print(f"  {key:18s}: JS = {js['mean']:.4f} ± {js['std']:.4f}  "
              f"({agg.get('config','')})")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Mode: continuous — Binary vs Continuous overlap 비교
# ═══════════════════════════════════════════════════════════════════════

def mode_continuous(args):
    """Binary / Continuous / Binarized-continuous overlap 비교."""
    from overlap import build_activation_matrix
    from preprocessing import simul_chord_lists, simul_union_by_dict

    print("Step 3 continuous overlap 실험")
    print(f"각 설정 {args.n_repeats}회 반복")

    p = setup_pipeline()

    # Tonnetz cache
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    binary_overlap = cache['overlap'].values
    print(f"\n  Tonnetz cycle_labeled: {len(cycle_labeled)} cycles")
    print(f"  Binary overlap shape: {binary_overlap.shape}")

    # 원곡 note-time 행렬
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
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
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

    results = {'n_repeats': args.n_repeats}

    # ── Setting A: 기존 binary overlap (cache) ──
    print(f"\n[A] Tonnetz binary overlap (기존 캐시, {args.n_repeats}회)")
    trials_a = []
    for i in range(args.n_repeats):
        r = run_algo1_once(p, binary_overlap, cycle_labeled, seed=5000 + i)
        trials_a.append(r)
        if i % 5 == 0 or i == args.n_repeats - 1:
            print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
    agg_a = aggregate(trials_a, METRIC_KEYS)
    results['A_binary_cached'] = agg_a
    print(f"  → JS = {agg_a['js_divergence']['mean']:.4f} "
          f"± {agg_a['js_divergence']['std']:.4f}")

    # ── Setting B: continuous 직접 사용 ──
    print(f"\n[B] Tonnetz continuous overlap (활성화 직접 사용, {args.n_repeats}회)")
    cont_overlap = activation_continuous.values.astype(np.float32)
    trials_b = []
    for i in range(args.n_repeats):
        r = run_algo1_once(p, cont_overlap, cycle_labeled, seed=5000 + i)
        trials_b.append(r)
        if i % 5 == 0 or i == args.n_repeats - 1:
            print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
    agg_b = aggregate(trials_b, METRIC_KEYS)
    results['B_continuous_direct'] = agg_b
    print(f"  → JS = {agg_b['js_divergence']['mean']:.4f} "
          f"± {agg_b['js_divergence']['std']:.4f}")

    # ── Setting C: continuous → binarize at τ ──
    tau_aggs = {}
    for tau in [0.3, 0.5, 0.7]:
        print(f"\n[C@τ={tau}] Tonnetz continuous → binarize at {tau} ({args.n_repeats}회)")
        ov = (cont_overlap >= tau).astype(np.float32)
        density = ov.mean()
        print(f"  binarized density: {density:.4f}")
        trials_c = []
        for i in range(args.n_repeats):
            r = run_algo1_once(p, ov, cycle_labeled, seed=5000 + i)
            trials_c.append(r)
            if i % 5 == 0 or i == args.n_repeats - 1:
                print(f"  [{i+1:2d}] JS={r['js_divergence']:.4f}  notes={r['n_notes']}")
        agg = aggregate(trials_c, METRIC_KEYS)
        agg['density'] = float(density)
        tau_aggs[tau] = agg
        results[f'C_continuous_thr_{tau}'] = agg
        print(f"  → JS = {agg['js_divergence']['mean']:.4f} "
              f"± {agg['js_divergence']['std']:.4f}")

    # ── 결과 저장 ──
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'step3_continuous_results.json'),
              'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 요약
    print("\n" + "=" * 60)
    print("  요약")
    print("=" * 60)
    for label, agg in [
        ('A binary (cached)',         agg_a),
        ('B continuous (direct)',     agg_b),
        ('C continuous→bin τ=0.3',   tau_aggs[0.3]),
        ('C continuous→bin τ=0.5',   tau_aggs[0.5]),
        ('C continuous→bin τ=0.7',   tau_aggs[0.7]),
    ]:
        js = agg['js_divergence']
        print(f"  {label:30s}  JS = {js['mean']:.4f} ± {js['std']:.4f}")


# ═══════════════════════════════════════════════════════════════════════
# Mode: all — baselines + ablations + continuous 순차 실행
# ═══════════════════════════════════════════════════════════════════════

def mode_all(args):
    """3개 모드 모두 순차 실행 (원본 step3_results.json 호환 출력)."""
    os.makedirs("output", exist_ok=True)

    p = setup_pipeline()
    print(f"전처리 완료: notes_label={len(p._cache['notes_label'])}")

    # baselines
    baselines_result = mode_baselines(args)
    # ablations
    ablations_result = mode_ablations(args)

    # 통합 JSON (원본 step3_results.json 호환)
    combined = {
        'n_repeats': args.n_repeats,
        'experiment_1_baselines': baselines_result or {},
        'experiment_2_ablations': ablations_result or {},
    }
    out_path = os.path.join("output", "step3_results.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\n통합 결과 저장: {out_path}")

    # continuous
    mode_continuous(args)

    print("\n모든 실험 완료!")


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Step 3 통합 실험 러너")
    parser.add_argument('--mode', required=True,
                        choices=['baselines', 'ablations', 'continuous', 'all'])
    parser.add_argument('--n-repeats', dest='n_repeats', type=int, default=20,
                        help="각 설정 반복 횟수 (기본 20)")

    args = parser.parse_args()

    dispatch = {
        'baselines': mode_baselines,
        'ablations': mode_ablations,
        'continuous': mode_continuous,
        'all': mode_all,
    }
    dispatch[args.mode](args)


if __name__ == '__main__':
    main()
