"""
run_note_reassign.py — 방향 A: 거리 보존 note 재분배 실험

중첩행렬은 그대로 두고, cycle에 새 note를 분배.
새 note 집합은 원곡의 note-note / cycle-cycle 거리를 보존.

사용법:
  python run_note_reassign.py
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph, run_algo1
from note_reassign import find_new_notes, compute_cycle_distance_matrix
from musical_metrics import compute_note_distance_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from sequence_metrics import evaluate_sequence_metrics
import random

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
N_TRIALS = 5
SEED_BASE = 42


def run_algo1_with_new_notes(data, ov, cl, new_notes_label, seed):
    """새 notes_label로 Algorithm 1 실행."""
    random.seed(seed); np.random.seed(seed)

    # new_notes_label의 key = (pitch, dur) 튜플
    # NodePool은 notes_counts의 key가 notes_label에 있는지 확인
    # → counts의 key도 새 (pitch, dur)여야 함
    new_counts = {note_tuple: 10 for note_tuple in new_notes_label.keys()}

    pool = NodePool(new_notes_label, new_counts, num_modules=65)
    mgr = CycleSetManager(cl)
    T = len(ov)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    h = (hp * (T//32+1))[:T]
    gen = algorithm1_optimized(pool, h, ov, mgr, max_resample=50)
    return gen


def print_note_comparison(orig_notes, new_notes):
    """원곡 vs 새 note 비교 출력."""
    print(f"\n  {'idx':>4} {'원곡 pitch':>10} {'새 pitch':>10} {'차이':>6}")
    print(f"  {'─'*4} {'─'*10} {'─'*10} {'─'*6}")
    for i, (on, nn) in enumerate(zip(orig_notes, new_notes)):
        diff = nn[0] - on[0]
        print(f"  {i+1:>4} {on[0]:>10} {nn[0]:>10} {diff:>+6}")


def run_experiment():
    print("=" * 64)
    print(f"  방향 A: 거리 보존 note 재분배 — {TRACK_NAME}")
    print("=" * 64)

    t0 = time.time()

    # ── 1. 전처리 + PH ──
    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    original_notes = data['inst1'] + data['inst2']

    # ── 2. 원곡 거리행렬 출력 ──
    D_orig = compute_note_distance_matrix(data['notes_label'], metric='voice_leading')
    C_orig = compute_cycle_distance_matrix(cl, data['notes_label'], metric='voice_leading')
    print(f"\n[원곡] note-note 거리행렬: {D_orig.shape}, cycle-cycle 거리행렬: {C_orig.shape}")
    print(f"  D_orig 통계: mean={D_orig[D_orig>0].mean():.2f}, max={D_orig.max():.2f}")
    print(f"  C_orig 통계: mean={C_orig[C_orig>0].mean():.2f}, max={C_orig.max():.2f}")

    # ── 3. Baseline (원곡 notes) ──
    print(f"\n{'─'*64}")
    print(f"  [Baseline] 원곡 notes → Algo1 × {N_TRIALS}")
    print(f"{'─'*64}")

    baseline_results = []
    for i in range(N_TRIALS):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        seq_m = evaluate_sequence_metrics(gen, original_notes)
        baseline_results.append(seq_m)

    bl_avg = {k: np.mean([r[k] for r in baseline_results]) for k in baseline_results[0]}
    print(f"  pitch JS:      {bl_avg['pitch_js']:.4f}")
    print(f"  transition JS: {bl_avg['transition_js']:.4f}")
    print(f"  DTW:           {bl_avg['dtw']:.4f}")
    print(f"  NCD:           {bl_avg['ncd']:.4f}")

    # ── 4. 새 note 탐색 (여러 seed) ──
    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'N': data['N'],
        'baseline': {k: round(v, 6) for k, v in bl_avg.items()},
        'reassignments': {},
    }

    configs = [
        ('tonnetz_narrow', {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (55, 79), 'n_candidates': 1000}),
        ('tonnetz_wide',   {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (48, 84), 'n_candidates': 1000}),
        ('tonnetz_vwide',  {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (40, 88), 'n_candidates': 1000}),
    ]

    for config_name, config_kwargs in configs:
        print(f"\n{'─'*64}")
        print(f"  [{config_name}] 새 note 탐색 (candidates={config_kwargs['n_candidates']})")
        print(f"{'─'*64}")

        result = find_new_notes(
            data['notes_label'], cl,
            seed=SEED_BASE,
            **config_kwargs
        )

        print(f"  note 거리 오차:  {result['note_dist_error']:.4f}")
        print(f"  cycle 거리 오차: {result['cycle_dist_error']:.4f}")
        print(f"  총 비용:         {result['total_cost']:.4f}")

        print_note_comparison(result['orig_notes'], result['new_notes'])

        # 생성 실험
        print(f"\n  → Algo1 × {N_TRIALS} 생성...")
        reassign_results = []
        for i in range(N_TRIALS):
            gen = run_algo1_with_new_notes(
                data, ov, cl, result['new_notes_label'], seed=SEED_BASE + i
            )
            if not gen:
                print(f"    trial {i}: no notes generated")
                continue
            seq_m = evaluate_sequence_metrics(gen, original_notes)
            reassign_results.append(seq_m)

        if reassign_results:
            avg = {k: np.mean([r[k] for r in reassign_results]) for k in reassign_results[0]}

            # DTW가 높으면 "다른 선율", pitch JS도 높으면 "다른 음" — 둘 다 예상됨
            print(f"\n  pitch JS:      {avg['pitch_js']:.4f}  (Δ {100*(avg['pitch_js']-bl_avg['pitch_js'])/max(bl_avg['pitch_js'],1e-6):+.1f}%)")
            print(f"  transition JS: {avg['transition_js']:.4f}")
            print(f"  DTW:           {avg['dtw']:.4f}  (Δ {100*(avg['dtw']-bl_avg['dtw'])/bl_avg['dtw']:+.1f}%)")
            print(f"  NCD:           {avg['ncd']:.4f}")

            all_results['reassignments'][config_name] = {
                'note_dist_error': round(result['note_dist_error'], 4),
                'cycle_dist_error': round(result['cycle_dist_error'], 4),
                'total_cost': round(result['total_cost'], 4),
                'orig_pitches': [n[0] for n in result['orig_notes']],
                'new_pitches': [n[0] for n in result['new_notes']],
                'avg_metrics': {k: round(v, 6) for k, v in avg.items()},
            }

    # ── 5. 저장 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "note_reassign_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
    print(f"총 소요: {elapsed:.1f}s")


if __name__ == '__main__':
    run_experiment()
