"""
run_step3_experiments.py — Step 3 통계 실험 러너
==================================================

목적:
 1) 비교 baseline: frequency / tonnetz / voice_leading / dft
 2) 각 설정당 N=20회 반복 → mean ± std
 3) Ablation: full vs subset (K=10, K=17)

모든 결과는 output/step3_results.json 에 저장됨.
"""
import sys, os, json, time, random, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

N_REPEATS = 20
OUTPUT_JSON = os.path.join("output", "step3_results.json")


def setup_base():
    """TDAMusicPipeline을 전처리만 수행한 상태로 준비."""
    config = PipelineConfig()
    p = TDAMusicPipeline(config)
    p.run_preprocessing()
    return p


def load_metric_cache(metric: str):
    path = os.path.join("cache", f"metric_{metric}.pkl")
    with open(path, 'rb') as f:
        return pickle.load(f)


def run_algo1_once(base_pipeline, overlap_values, cycle_labeled, seed):
    """Algorithm 1을 한 번 실행하고 평가 지표를 반환."""
    random.seed(seed)
    np.random.seed(seed)

    notes_label = base_pipeline._cache['notes_label']
    notes_counts = base_pipeline._cache['notes_counts']

    pool = NodePool(notes_label, notes_counts, num_modules=65)
    manager = CycleSetManager(cycle_labeled)

    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33

    t0 = time.time()
    generated = algorithm1_optimized(
        pool, inst_chord_heights,
        overlap_values,
        manager,
        max_resample=50,
        verbose=False,
    )
    elapsed = time.time() - t0

    result = evaluate_generation(
        generated,
        [base_pipeline._cache['inst1_real'], base_pipeline._cache['inst2_real']],
        notes_label,
        name=""
    )
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


METRIC_KEYS = ['js_divergence', 'kl_divergence', 'note_coverage',
               'n_notes', 'pitch_count', 'elapsed_s']


def experiment_baselines(base):
    print("\n" + "="*60)
    print("  실험 1: Distance function baseline 비교")
    print("="*60)
    results = {}
    metrics_to_test = ['frequency', 'tonnetz', 'voice_leading', 'dft']

    for metric in metrics_to_test:
        print(f"\n  → {metric} ({N_REPEATS}회 반복)")
        try:
            cache = load_metric_cache(metric)
        except FileNotFoundError:
            print(f"    (캐시 없음, skip)")
            continue
        overlap_df = cache['overlap']
        cycle_labeled = cache['cycle_labeled']
        overlap_values = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df

        trials = []
        for i in range(N_REPEATS):
            r = run_algo1_once(base, overlap_values, cycle_labeled, seed=1000 + i)
            trials.append(r)
            print(f"    [{i+1:2d}] JS={r['js_divergence']:.4f}  "
                  f"notes={r['n_notes']}  pitches={r['pitch_count']}  "
                  f"cov={r['note_coverage']:.2f}")

        agg = aggregate(trials, METRIC_KEYS)
        agg['n_cycles'] = len(cycle_labeled)
        agg['n_repeats'] = N_REPEATS
        results[metric] = agg
        print(f"    JS: {agg['js_divergence']['mean']:.4f} "
              f"± {agg['js_divergence']['std']:.4f}")

    return results


def experiment_ablations(base):
    print("\n" + "="*60)
    print("  실험 2: Ablation study")
    print("="*60)
    results = {}

    # Tonnetz를 base로 사용
    cache = load_metric_cache('tonnetz')
    overlap_df = cache['overlap']
    cycle_labeled = cache['cycle_labeled']
    overlap_full = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df
    n_cycles = len(cycle_labeled)

    # (a) Full (tonnetz)
    print(f"\n  (a) Full cycle set (K={n_cycles}, Tonnetz)")
    trials = []
    for i in range(N_REPEATS):
        r = run_algo1_once(base, overlap_full, cycle_labeled, seed=2000 + i)
        trials.append(r)
    results['full_tonnetz'] = aggregate(trials, METRIC_KEYS)
    results['full_tonnetz']['config'] = f'K={n_cycles}, Tonnetz, full'
    results['full_tonnetz']['n_cycles'] = n_cycles
    print(f"    JS: {results['full_tonnetz']['js_divergence']['mean']:.4f} "
          f"± {results['full_tonnetz']['js_divergence']['std']:.4f}")

    # (b) Subset K=10, K=17 (prefix subset — 간단한 ablation)
    for k_sub in [10, 17]:
        if k_sub >= n_cycles:
            continue
        print(f"\n  (b) Cycle subset K={k_sub} (first {k_sub} cycles)")
        cycle_list = list(cycle_labeled.items())[:k_sub]
        cycle_sub = dict(cycle_list)
        sub_idx = list(range(k_sub))
        overlap_sub = overlap_full[:, sub_idx]
        trials = []
        for i in range(N_REPEATS):
            r = run_algo1_once(base, overlap_sub, cycle_sub, seed=3000 + i)
            trials.append(r)
        key = f'subset_K{k_sub}'
        results[key] = aggregate(trials, METRIC_KEYS)
        results[key]['config'] = f'K={k_sub}, Tonnetz, prefix subset'
        results[key]['n_cycles'] = k_sub
        print(f"    JS: {results[key]['js_divergence']['mean']:.4f} "
              f"± {results[key]['js_divergence']['std']:.4f}")

    return results


def main():
    os.makedirs("output", exist_ok=True)
    print("Step 3 통계 실험 시작")
    print(f"각 설정당 {N_REPEATS}회 반복")

    base = setup_base()
    print(f"전처리 완료: notes_label={len(base._cache['notes_label'])}")

    all_results = {
        'n_repeats': N_REPEATS,
        'experiment_1_baselines': experiment_baselines(base),
        'experiment_2_ablations': experiment_ablations(base),
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60)
    print(f"  결과 저장: {OUTPUT_JSON}")
    print("="*60)

    # 요약 출력
    print("\n[요약] Experiment 1 — Distance baselines")
    for metric, agg in all_results['experiment_1_baselines'].items():
        js = agg['js_divergence']
        print(f"  {metric:15s}: JS = {js['mean']:.4f} ± {js['std']:.4f}  "
              f"(K={agg.get('n_cycles','?')})")

    print("\n[요약] Experiment 2 — Ablation")
    for key, agg in all_results['experiment_2_ablations'].items():
        js = agg['js_divergence']
        print(f"  {key:18s}: JS = {js['mean']:.4f} ± {js['std']:.4f}  "
              f"({agg.get('config','')})")


if __name__ == "__main__":
    main()
