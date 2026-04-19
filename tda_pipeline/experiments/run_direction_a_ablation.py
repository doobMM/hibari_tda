"""
run_direction_a_ablation.py — 방향 A Ablation: matching_mode × alpha_cycle

목적:
  §7.3 방향 A(거리 보존 note 재분배)에서 두 개의 구조적 선택을 ablate한다.
    1) matching_mode: 원곡 pitch ↔ 새 pitch 매칭 규칙
         - 'ascending'      : 오름차순 정렬 (기존 방식)
         - 'tonnetz_nearest': Tonnetz 공간 최근접 Hungarian 매칭 (신규)
    2) alpha_cycle:    cycle 거리 보존 가중치
         - 0.5 (기존)       : note_err + cycle_err
         - 0.0 (ablation)   : note_err only (cycle_err는 계산만, 선택엔 무기여)

  2×2 factorial design. 각 조건에서 Algorithm 1으로 n_trials회 생성 후
  sequence_metrics(pitch_js, transition_js, dtw, ncd) 평균 집계.

사용법:
  python run_direction_a_ablation.py                    # 기본 n_trials=5
  python run_direction_a_ablation.py --n_trials 20      # 본 실험
  python run_direction_a_ablation.py --include_dl       # DL 확장 (현재 stub)

주의:
  - 이 스크립트는 세션 B에서 "실행 없이" 작성된 러너이다.
  - 실행은 세션 A에서 진행한다.
  - DL 확장(--include_dl)은 현재 stub. Algorithm 1만 완전 구현됨.
"""
import os, sys, time, json, warnings, argparse
import numpy as np
import random
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from run_any_track import preprocess, compute_ph, run_algo1
from note_reassign import find_new_notes
from generation import algorithm1_optimized, NodePool, CycleSetManager
from sequence_metrics import evaluate_sequence_metrics

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42
PITCH_RANGE = (48, 84)   # wide
N_CANDIDATES = 1000


def run_algo1_with_new_notes(data, ov, cl, new_notes_label, seed):
    """새 notes_label로 Algorithm 1 실행 (run_note_reassign_unified와 동일 패턴)."""
    random.seed(seed); np.random.seed(seed)
    new_counts = {nt: 10 for nt in new_notes_label.keys()}
    pool = NodePool(new_notes_label, new_counts, num_modules=65)
    mgr = CycleSetManager(cl)
    T = len(ov)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
          4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    h = (hp * (T // 32 + 1))[:T]
    return algorithm1_optimized(pool, h, ov, mgr, max_resample=50)


def setup():
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")
    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        raise RuntimeError("no cycles found")
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")
    return data, cl, ov, n_cyc


def avg_metrics(results):
    if not results:
        return None
    return {k: float(np.mean([r[k] for r in results])) for k in results[0]}


def run_condition(data, cl, ov, original_notes, *,
                  matching_mode, n_trials, seed_base=SEED_BASE):
    """
    한 조건(matching_mode)에서 note 재분배 → Algorithm 1 × n_trials → 평균.
    cycle_error는 제거됨. note_error만으로 최적 후보 선택.
    """
    print(f"\n  --- condition: matching={matching_mode}")

    t0 = time.time()
    reassign = find_new_notes(
        data['notes_label'], cl,
        note_metric='tonnetz',
        pitch_range=PITCH_RANGE,
        n_candidates=N_CANDIDATES,
        alpha_note=0.5,
        matching_mode=matching_mode,
        seed=seed_base,
    )
    find_elapsed = time.time() - t0
    print(f"    find_new_notes: {find_elapsed:.1f}s  "
          f"note_err={reassign['note_dist_error']:.4f}")

    trial_results = []
    for i in range(n_trials):
        gen = run_algo1_with_new_notes(
            data, ov, cl, reassign['new_notes_label'], seed=seed_base + i)
        if gen:
            trial_results.append(evaluate_sequence_metrics(gen, original_notes))

    avg = avg_metrics(trial_results)
    return {
        'matching_mode': matching_mode,
        'note_dist_error': round(reassign['note_dist_error'], 4),
        'find_elapsed_s': round(find_elapsed, 1),
        'n_trials_completed': len(trial_results),
        'avg_metrics': {k: round(v, 6) for k, v in avg.items()} if avg else None,
    }


def run_baseline(data, cl, ov, original_notes, n_trials, seed_base=SEED_BASE):
    print("\n  --- baseline (original notes_label, 원곡 직접 사용)")
    bl = []
    for i in range(n_trials):
        gen = run_algo1(data, ov, cl, seed=seed_base + i)
        if gen:
            bl.append(evaluate_sequence_metrics(gen, original_notes))
    avg = avg_metrics(bl)
    return {'n_trials_completed': len(bl),
            'avg_metrics': {k: round(v, 6) for k, v in avg.items()} if avg else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_trials', type=int, default=5,
                        help='Algorithm 1 생성 횟수 (기본 5; 본 실험은 20 권장)')
    parser.add_argument('--include_dl', action='store_true',
                        help='LSTM/Transformer ablation 추가 (현재 stub, 미구현)')
    parser.add_argument('--out', type=str,
                        default='docs/step3_data/direction_a_ablation_results.json')
    args = parser.parse_args()

    print("=" * 64)
    print(f"  방향 A Ablation: matching_mode × alpha_cycle — {TRACK_NAME}")
    print(f"  n_trials = {args.n_trials}")
    print("=" * 64)

    t_total = time.time()
    data, cl, ov, n_cyc = setup()
    original_notes = data['inst1'] + data['inst2']

    all_results = {
        'track': TRACK_NAME,
        'metric': METRIC,
        'pitch_range': list(PITCH_RANGE),
        'n_candidates': N_CANDIDATES,
        'n_cycles': n_cyc,
        'N': data['N'],
        'T': data['T'],
        'n_trials': args.n_trials,
        'seed_base': SEED_BASE,
        'baseline': run_baseline(data, cl, ov, original_notes, args.n_trials),
        'ablation_2x2': {},
    }

    # matching_mode ablation (cycle_error 제거 후 단일 축)
    conditions = [
        ('ascending',       'ascending'),
        ('tonnetz_nearest', 'tonnetz_nearest'),
    ]

    for label, mm in conditions:
        all_results['ablation_2x2'][label] = run_condition(
            data, cl, ov, original_notes,
            matching_mode=mm, n_trials=args.n_trials,
        )

    # DL stub
    if args.include_dl:
        print("\n[--include_dl] DL ablation은 아직 stub입니다.")
        print("  세션 A에서 LSTM/Transformer 확장을 추가할 예정.")
        all_results['dl_ablation'] = {'status': 'not_implemented'}

    all_results['elapsed_s'] = round(time.time() - t_total, 1)

    # 결과 저장
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {args.out}")
    print(f"총 소요: {all_results['elapsed_s']}s")

    # 요약 출력
    print("\n" + "=" * 64)
    print("  요약 (pitch_js, 낮을수록 원곡과 유사)")
    print("=" * 64)
    bl_pjs = all_results['baseline']['avg_metrics']
    if bl_pjs:
        print(f"  baseline                      pitch_js={bl_pjs['pitch_js']:.4f}  "
              f"dtw={bl_pjs['dtw']:.4f}")
    for label, r in all_results['ablation_2x2'].items():
        if r['avg_metrics']:
            m = r['avg_metrics']
            print(f"  {label:<30} pitch_js={m['pitch_js']:.4f}  "
                  f"dtw={m['dtw']:.4f}  "
                  f"note_err={r['note_dist_error']:.4f}")


if __name__ == '__main__':
    main()
