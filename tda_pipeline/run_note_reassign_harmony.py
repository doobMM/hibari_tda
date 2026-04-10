"""
run_note_reassign_harmony.py — 방향 A 화성 제약 비교 실험

3가지 화성 제약 방식을 비교:
  1. scale:      후보 pitch를 특정 음계로 제한
  2. consonance: cycle 내 불협화도 패널티
  3. interval:   원곡 cycle interval structure 보존
  + all: 세 가지 동시 적용
  + baseline: 제약 없음 (기존 방식)

사용법:
  python run_note_reassign_harmony.py
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from note_reassign import find_new_notes, SCALES
from generation import notes_to_xml, algorithm1_optimized, NodePool, CycleSetManager

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED = 42
N_CANDIDATES = 1000
PITCH_RANGE = (40, 88)  # vwide (가장 자유도 높은 설정)

# ── 실험 설정 ──
EXPERIMENTS = [
    # (이름, harmony_mode, 추가 kwargs)
    ('baseline',    None,          {}),
    ('scale_major', 'scale',       {'scale_type': 'major'}),
    ('scale_minor', 'scale',       {'scale_type': 'minor'}),
    ('scale_penta', 'scale',       {'scale_type': 'pentatonic'}),
    ('consonance',  'consonance',  {'alpha_consonance': 0.3}),
    ('interval',    'interval',    {'alpha_interval': 0.3}),
    ('all_major',   'all',         {'scale_type': 'major',
                                    'alpha_consonance': 0.3,
                                    'alpha_interval': 0.3}),
    ('all_penta',   'all',         {'scale_type': 'pentatonic',
                                    'alpha_consonance': 0.3,
                                    'alpha_interval': 0.3}),
]


def analyze_harmony(notes_label, cycle_labeled, new_notes_label, new_notes):
    """새 note set의 화성 분석 (음계 적합도)."""
    new_pitches = [n[0] for n in new_notes]

    # 음계 적합도: 가장 잘 맞는 음계 찾기
    best_scale_match = 0.0
    best_scale_name = ""
    pcs = set(p % 12 for p in new_pitches)
    for sname, spc in SCALES.items():
        for root in range(12):
            scale_pcs = set((pc + root) % 12 for pc in spc)
            match = len(pcs & scale_pcs) / len(pcs) if pcs else 0
            if match > best_scale_match:
                best_scale_match = match
                root_name = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][root]
                best_scale_name = f"{root_name} {sname}"

    return {
        'best_scale_match': best_scale_match,
        'best_scale_name': best_scale_name,
        'pitch_classes_used': sorted(list(pcs)),
        'n_pitch_classes': len(pcs),
    }


def run():
    print("=" * 70)
    print("  방향 A: 화성 제약 비교 실험")
    print("=" * 70)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    # 원곡 pitch class 분석
    orig_sorted = sorted(data['notes_label'].items(), key=lambda x: x[1])
    orig_pitches = [n[0][0] for n in orig_sorted]
    orig_pcs = set(p % 12 for p in orig_pitches)
    print(f"\n원곡 pitch classes: {sorted(list(orig_pcs))} ({len(orig_pcs)}개)")

    all_results = {
        'track': TRACK_NAME,
        'metric': METRIC,
        'n_cycles': n_cyc,
        'pitch_range': list(PITCH_RANGE),
        'n_candidates': N_CANDIDATES,
        'orig_n_pitch_classes': len(orig_pcs),
        'experiments': {},
    }

    # ── 각 실험 실행 ──
    for exp_name, harmony_mode, extra_kwargs in EXPERIMENTS:
        print(f"\n{'─'*60}")
        print(f"  [{exp_name}] harmony_mode={harmony_mode}")
        print(f"{'─'*60}")

        t1 = time.time()
        try:
            result = find_new_notes(
                data['notes_label'], cl, seed=SEED,
                note_metric='tonnetz', cycle_metric='tonnetz',
                pitch_range=PITCH_RANGE, n_candidates=N_CANDIDATES,
                harmony_mode=harmony_mode,
                **extra_kwargs,
            )
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            all_results['experiments'][exp_name] = {'error': str(e)}
            continue

        elapsed = time.time() - t1
        new_pitches = [n[0] for n in result['new_notes']]

        # 화성 분석
        harmony = analyze_harmony(
            data['notes_label'], cl,
            result['new_notes_label'], result['new_notes']
        )

        print(f"  소요: {elapsed:.1f}s")
        print(f"  note 거리 오차:  {result['note_dist_error']:.4f}")
        print(f"  cycle 거리 오차: {result['cycle_dist_error']:.4f}")
        print(f"  consonance:     {result['consonance_score']:.4f}")
        print(f"  interval 오차:  {result['interval_error']:.4f}")
        print(f"  최적 음계 매칭:  {harmony['best_scale_name']} ({harmony['best_scale_match']*100:.0f}%)")
        print(f"  사용 PC 수:     {harmony['n_pitch_classes']}개 → {harmony['pitch_classes_used']}")
        print(f"  새 pitch:       {new_pitches}")

        if 'scale_root_name' in result:
            print(f"  선택된 scale:   {result['scale_root_name']} {extra_kwargs.get('scale_type', '')}")

        # MusicXML 출력 (Algorithm 1으로 빠르게 청각 확인용)
        new_counts = {nt: 10 for nt in result['new_notes_label'].keys()}
        pool = NodePool(result['new_notes_label'], new_counts, num_modules=65)
        mgr = CycleSetManager(cl)
        T = len(ov)
        hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
        h = (hp * (T//32+1))[:T]
        import random
        random.seed(SEED); np.random.seed(SEED)
        gen = algorithm1_optimized(pool, h, ov, mgr, max_resample=50)
        n_gen = len(gen) if gen else 0

        if gen:
            notes_to_xml([gen], tempo_bpm=66,
                         file_name=f"harmony_{exp_name}",
                         output_dir="./output")
            print(f"  생성: {n_gen}개 음표 → output/harmony_{exp_name}.musicxml")

        all_results['experiments'][exp_name] = {
            'harmony_mode': harmony_mode,
            'note_dist_error': round(result['note_dist_error'], 4),
            'cycle_dist_error': round(result['cycle_dist_error'], 4),
            'consonance_score': round(result['consonance_score'], 4),
            'interval_error': round(result['interval_error'], 4),
            'total_cost': round(result['total_cost'], 4),
            'elapsed_s': round(elapsed, 1),
            'n_generated': n_gen,
            'new_pitches': new_pitches,
            **{f'harmony_{k}': v for k, v in harmony.items()},
            **({
                'scale_type': extra_kwargs.get('scale_type', ''),
                'scale_root': result.get('scale_root_name', ''),
                'pool_size': result.get('pool_size', 0),
            } if 'scale_root_name' in result else {}),
        }

    # ── 요약 테이블 ──
    elapsed_total = time.time() - t0

    print(f"\n{'='*100}")
    print(f"  요약")
    print(f"{'='*100}")
    print(f"  {'실험':<20} {'note_err':>9} {'cycle_err':>10} {'intv_err':>9} {'scale_match':>12} {'#PC':>4} {'notes':>6}")
    print(f"  {'─'*20} {'─'*9} {'─'*10} {'─'*9} {'─'*12} {'─'*4} {'─'*6}")

    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<20} ERROR: {r['error']}")
            continue
        print(f"  {name:<20} "
              f"{r['note_dist_error']:>9.4f} "
              f"{r['cycle_dist_error']:>10.4f} "
              f"{r['interval_error']:>9.4f} "
              f"{r.get('harmony_best_scale_name', 'N/A'):>12s} "
              f"{r['harmony_n_pitch_classes']:>4d} "
              f"{r['n_generated']:>6d}")

    # JSON 저장
    out_path = os.path.join("docs", "step3_data", "note_reassign_harmony_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
    print(f"총 소요: {elapsed_total:.1f}s")


if __name__ == '__main__':
    run()
