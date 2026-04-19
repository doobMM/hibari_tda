"""
run_wasserstein_strategy_a.py — 전략 A(tonnetz_nearest) + Wasserstein 제약 실험

run_note_reassign_unified.py의 mode_wasserstein을 기반으로,
matching_mode='tonnetz_nearest' (전략 A)를 적용한 버전.

기존 note_reassign_wasserstein_results.json (전략 B, ascending)과
1:1 비교 가능하도록 동일 config 5종 포함.
추가로 전략 A 최적 pitch 범위 wide(48-84) 실험 2종 포함.

결과 저장: docs/step3_data/note_reassign_wasserstein_strategy_a_results.json
"""
import os
import sys
import time
import json
import random
import warnings

import numpy as np

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph, run_algo1
from note_reassign import find_new_notes
from generation import algorithm1_optimized, NodePool, CycleSetManager
from sequence_metrics import evaluate_sequence_metrics

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42
N_TRIALS = 5
OUTPUT_FILE = "note_reassign_wasserstein_strategy_a_results.json"


def run_algo1_with_new_notes(data, ov, cl, new_notes_label, seed):
    """새 notes_label로 Algorithm 1 실행."""
    random.seed(seed)
    np.random.seed(seed)
    new_counts = {nt: 10 for nt in new_notes_label.keys()}
    pool = NodePool(new_notes_label, new_counts, num_modules=65)
    mgr = CycleSetManager(cl)
    T = len(ov)
    hp = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
          4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    h = (hp * (T // 32 + 1))[:T]
    return algorithm1_optimized(pool, h, ov, mgr, max_resample=50)


def main():
    print("=" * 64)
    print("  전략 A(tonnetz_nearest) + Wasserstein 제약 Note 재분배 실험")
    print("=" * 64)

    t_total = time.time()

    # ── 전처리 + PH ──────────────────────────────────────────────
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")
    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        raise RuntimeError("no cycles found")
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    original_notes = data['inst1'] + data['inst2']

    # ── Baseline ─────────────────────────────────────────────────
    print("\n[Baseline 계산]")
    bl_results = []
    for i in range(N_TRIALS):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        bl_results.append(evaluate_sequence_metrics(gen, original_notes))
    bl_avg = {k: np.mean([r[k] for r in bl_results]) for k in bl_results[0]}
    print(f"  pitch_js={bl_avg['pitch_js']:.4f}  "
          f"transition_js={bl_avg['transition_js']:.4f}  "
          f"dtw={bl_avg['dtw']:.4f}")

    results = {
        'track': TRACK_NAME,
        'metric': METRIC,
        'matching_mode': 'tonnetz_nearest',
        'n_cycles': n_cyc,
        'N': data['N'],
        'n_trials': N_TRIALS,
        'baseline': {k: round(v, 6) for k, v in bl_avg.items()},
        'experiments': {},
    }

    # ── Configs ───────────────────────────────────────────────────
    # 기존 전략 B(ascending)와 동일 5종 (pitch_range=(40,88))
    # + 전략 A 최적 wide 범위(48-84) 2종 추가
    configs = [
        # ── vwide 범위 (40,88) — 전략 B와 동일 비교 기준 ──
        ('no_wasserstein',
         {'alpha_wasserstein': 0.0,
          'n_candidates': 1000,
          'pitch_range': (40, 88)}),
        ('wasserstein_0.3',
         {'alpha_wasserstein': 0.3,
          'n_candidates': 1000,
          'n_wasserstein_topk': 30,
          'pitch_range': (40, 88)}),
        ('wasserstein_0.5',
         {'alpha_wasserstein': 0.5,
          'n_candidates': 1000,
          'n_wasserstein_topk': 30,
          'pitch_range': (40, 88)}),
        ('wasserstein_1.0',
         {'alpha_wasserstein': 1.0,
          'n_candidates': 1000,
          'n_wasserstein_topk': 30,
          'pitch_range': (40, 88)}),
        ('scale_major_wass_0.5',
         {'alpha_wasserstein': 0.5,
          'n_candidates': 1000,
          'n_wasserstein_topk': 30,
          'pitch_range': (40, 88),
          'harmony_mode': 'scale',
          'scale_type': 'major'}),
        # ── wide 범위 (48,84) — 전략 A 최적 설정 ──
        ('no_wasserstein_wide',
         {'alpha_wasserstein': 0.0,
          'n_candidates': 1000,
          'pitch_range': (48, 84)}),
        ('wasserstein_0.3_wide',
         {'alpha_wasserstein': 0.3,
          'n_candidates': 1000,
          'n_wasserstein_topk': 30,
          'pitch_range': (48, 84)}),
    ]

    # ── 실험 루프 ─────────────────────────────────────────────────
    for cfg_name, kwargs in configs:
        print(f"\n  [{cfg_name}]")
        t1 = time.time()

        try:
            result = find_new_notes(
                notes_label=data['notes_label'],
                cycle_labeled=cl,
                note_metric='tonnetz',
                seed=SEED_BASE,
                alpha_note=0.5,
                matching_mode='tonnetz_nearest',
                **kwargs)
        except Exception as e:
            print(f"  오류: {e}")
            results['experiments'][cfg_name] = {'error': str(e)}
            continue

        elapsed = time.time() - t1

        # Algorithm 1 N_TRIALS 회 실행
        trial_results = []
        for i in range(N_TRIALS):
            gen = run_algo1_with_new_notes(
                data, ov, cl, result['new_notes_label'], SEED_BASE + i)
            if gen:
                trial_results.append(
                    evaluate_sequence_metrics(gen, original_notes))

        if not trial_results:
            results['experiments'][cfg_name] = {'error': 'no generated notes'}
            continue

        avg = {k: round(float(np.mean([r[k] for r in trial_results])), 6)
               for k in trial_results[0]}

        exp_data = {
            'note_dist_error': round(float(result['note_dist_error']), 4),
            'cycle_dist_error': round(float(result.get('cycle_dist_error', 0.0)), 4),
            'wasserstein_dist': round(float(result.get('wasserstein_dist', 0.0)), 4),
            'total_cost': round(float(result['total_cost']), 4),
            'new_pitches': [int(p) for p, d in result['new_notes']],
            'avg_metrics': avg,
            'elapsed_s': round(elapsed, 1),
        }
        if 'scale_root_name' in result:
            exp_data['scale_root'] = result['scale_root_name']

        results['experiments'][cfg_name] = exp_data
        pjs = avg.get('pitch_js', float('nan'))
        wdist = result.get('wasserstein_dist', 0.0)
        print(f"  pitch_js={pjs:.4f}  wass_dist={wdist:.4f}  ({elapsed:.1f}s)")

    results['total_elapsed_s'] = round(time.time() - t_total, 1)

    # ── 저장 ─────────────────────────────────────────────────────
    out_path = os.path.join("docs", "step3_data", OUTPUT_FILE)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 요약 비교표 출력 ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  전략 A(tonnetz_nearest) vs 전략 B(ascending) — pitch_js 비교")
    print("=" * 70)
    print(f"  {'Config':<28} {'A pitch_js':>12} {'B pitch_js':>12} {'A wass':>10}")
    print("  " + "-" * 66)

    # 전략 B 기존 수치 (note_reassign_wasserstein_results.json 값)
    strategy_b = {
        'no_wasserstein':     0.607164,
        'wasserstein_0.3':    0.512626,
        'wasserstein_0.5':    0.512626,
        'wasserstein_1.0':    0.512626,
        'scale_major_wass_0.5': 0.114862,
    }

    for cfg_name, exp in results['experiments'].items():
        if 'error' in exp:
            print(f"  [{cfg_name:<26}] ERROR: {exp['error']}")
            continue
        pjs_a = exp['avg_metrics'].get('pitch_js', float('nan'))
        pjs_b = strategy_b.get(cfg_name, float('nan'))
        wdist = exp.get('wasserstein_dist', 0.0)
        b_str = f"{pjs_b:.4f}" if not np.isnan(pjs_b) else "  —   "
        print(f"  {cfg_name:<28}  {pjs_a:>10.4f}  {b_str:>12}  {wdist:>8.4f}")

    print(f"\n  총 소요: {results['total_elapsed_s']:.0f}s")


if __name__ == '__main__':
    main()
