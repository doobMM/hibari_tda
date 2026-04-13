"""
run_note_reassign_wasserstein.py — Wasserstein distance 제약 적용 note 재분배

기존 Tonnetz matching 제약에 PD 간 Wasserstein distance를 추가로 적용.
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph, run_algo1
from note_reassign import find_new_notes
from generation import algorithm1_optimized, NodePool, CycleSetManager
from sequence_metrics import evaluate_sequence_metrics
import random

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
N_TRIALS = 5
SEED_BASE = 42


def run_algo1_with_new_notes(data, ov, cl, new_notes_label, seed):
    random.seed(seed); np.random.seed(seed)
    new_counts = {note_tuple: 10 for note_tuple in new_notes_label.keys()}
    pool = NodePool(new_notes_label, new_counts, num_modules=65)
    mgr = CycleSetManager(cl)
    T = len(ov)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    h = (hp * (T//32+1))[:T]
    return algorithm1_optimized(pool, h, ov, mgr, max_resample=50)


def run_experiment():
    print("=" * 64)
    print("  Wasserstein Distance 제약 Note 재분배 실험")
    print("=" * 64)

    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    original_notes = data['inst1'] + data['inst2']

    # Baseline
    baseline_results = []
    for i in range(N_TRIALS):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        baseline_results.append(evaluate_sequence_metrics(gen, original_notes))
    bl_avg = {k: np.mean([r[k] for r in baseline_results]) for k in baseline_results[0]}
    print(f"\n[Baseline] pitch JS: {bl_avg['pitch_js']:.4f}, DTW: {bl_avg['dtw']:.4f}")

    results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'N': data['N'],
        'baseline': {k: round(v, 6) for k, v in bl_avg.items()},
        'experiments': {},
    }

    configs = [
        ('no_wasserstein', {'alpha_wasserstein': 0.0, 'n_candidates': 1000}),
        ('wasserstein_0.3', {'alpha_wasserstein': 0.3, 'n_candidates': 1000, 'n_wasserstein_topk': 30}),
        ('wasserstein_0.5', {'alpha_wasserstein': 0.5, 'n_candidates': 1000, 'n_wasserstein_topk': 30}),
        ('wasserstein_1.0', {'alpha_wasserstein': 1.0, 'n_candidates': 1000, 'n_wasserstein_topk': 30}),
        ('scale_major_wass_0.5', {
            'alpha_wasserstein': 0.5, 'n_candidates': 1000, 'n_wasserstein_topk': 30,
            'harmony_mode': 'scale', 'scale_type': 'major',
        }),
    ]

    for config_name, kwargs in configs:
        print(f"\n{'─'*50}")
        print(f"  [{config_name}]")
        t0 = time.time()

        result = find_new_notes(
            notes_label=data['notes_label'],
            cycle_labeled=cl,
            note_metric='tonnetz', cycle_metric='tonnetz',
            pitch_range=(40, 88), seed=42,
            alpha_note=0.5, alpha_cycle=0.5,
            **kwargs,
        )
        elapsed = time.time() - t0

        new_pitches = [p for p, d in result['new_notes']]
        print(f"  new pitches: {new_pitches}")
        print(f"  note_err={result['note_dist_error']:.4f}  cycle_err={result['cycle_dist_error']:.4f}  "
              f"wass={result.get('wasserstein_dist', 0):.4f}  cost={result['total_cost']:.4f}")

        # Algo1로 평가
        trial_results = []
        for i in range(N_TRIALS):
            gen = run_algo1_with_new_notes(data, ov, cl, result['new_notes_label'], SEED_BASE+i)
            trial_results.append(evaluate_sequence_metrics(gen, original_notes))
        avg = {k: round(np.mean([r[k] for r in trial_results]), 6) for k in trial_results[0]}

        entry = {
            'note_dist_error': round(result['note_dist_error'], 4),
            'cycle_dist_error': round(result['cycle_dist_error'], 4),
            'wasserstein_dist': round(result.get('wasserstein_dist', 0.0), 4),
            'total_cost': round(result['total_cost'], 4),
            'new_pitches': new_pitches,
            'avg_metrics': avg,
            'elapsed_s': round(elapsed, 1),
        }
        if kwargs.get('harmony_mode') == 'scale':
            entry['scale_root'] = result.get('scale_root_name', '')
        results['experiments'][config_name] = entry
        print(f"  pJS={avg.get('pitch_js', '?')}  DTW={avg.get('dtw', '?')}  ({elapsed:.1f}s)")

    # 저장
    out_path = os.path.join(os.path.dirname(__file__), 'docs', 'step3_data',
                            'note_reassign_wasserstein_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n결과: {out_path}")


if __name__ == '__main__':
    run_experiment()
