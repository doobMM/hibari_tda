"""
run_note_reassign_harmony_dl.py — 화성 제약 + Algorithm 2 (DL) 비교

scale_penta, scale_major, baseline(chromatic)을 Transformer로 학습/생성하여
화성 제약이 DL 생성에도 효과적인지 검증.

사용법:
  python run_note_reassign_harmony_dl.py
"""
import os, sys, time, json, datetime, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from run_note_reassign_dl import remap_music_notes
from note_reassign import find_new_notes
from sequence_metrics import evaluate_sequence_metrics
from run_note_reassign_harmony import analyze_harmony
from generation import notes_to_xml

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED = 42
EPOCHS = 50
LR = 0.001
BATCH_SIZE = 32
N_CANDIDATES = 1000
PITCH_RANGE = (40, 88)

# 화성 제약 설정들
HARMONY_CONFIGS = [
    ('baseline',    {'harmony_mode': None}),
    ('scale_major', {'harmony_mode': 'scale', 'scale_type': 'major'}),
    ('scale_penta', {'harmony_mode': 'scale', 'scale_type': 'pentatonic'}),
    ('all_penta',   {'harmony_mode': 'all',   'scale_type': 'pentatonic',
                     'alpha_consonance': 0.3, 'alpha_interval': 0.3}),
]


def run():
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model,
    )
    from sklearn.model_selection import train_test_split

    print("=" * 70)
    print("  화성 제약 + Algorithm 2 (Transformer) 비교")
    print("=" * 70)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    T = data['T']
    N = len(data['notes_label'])
    C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': EPOCHS, 'experiments': {},
    }

    # ── Baseline: 원곡 note + Transformer ──
    print(f"\n{'='*70}")
    print(f"  [original] 원곡 note → Transformer")
    print(f"{'='*70}")

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N
    )
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_orig, y_orig, test_size=0.2, random_state=SEED
    )

    model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                       num_layers=2, dropout=0.1, max_len=T)
    history = train_model(model, X_tr, y_tr, X_va, y_va,
                          epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
                          model_type='transformer', seq_len=T)
    val_loss = history[-1]['val_loss']

    gen = generate_from_model(model, ov, data['notes_label'],
                              model_type='transformer', adaptive_threshold=True)
    if gen:
        seq_m = evaluate_sequence_metrics(gen, original_notes, name="original_transformer")
        all_results['experiments']['original_transformer'] = {
            'val_loss': round(val_loss, 4), 'n_notes': len(gen),
            **{k: round(v, 6) for k, v in seq_m.items()},
        }

    # ── 각 화성 제약 × Transformer ──
    for config_name, extra_kwargs in HARMONY_CONFIGS:
        print(f"\n{'='*70}")
        print(f"  [{config_name}] 새 note 탐색...")
        print(f"{'='*70}")

        t1 = time.time()
        reassign = find_new_notes(
            data['notes_label'], cl, seed=SEED,
            note_metric='tonnetz', cycle_metric='tonnetz',
            pitch_range=PITCH_RANGE, n_candidates=N_CANDIDATES,
            **extra_kwargs,
        )
        new_notes_label = reassign['new_notes_label']
        new_pitches = [n[0] for n in reassign['new_notes']]

        print(f"  note 오차: {reassign['note_dist_error']:.4f}")
        print(f"  cycle 오차: {reassign['cycle_dist_error']:.4f}")
        print(f"  consonance: {reassign['consonance_score']:.4f}")
        print(f"  새 pitch: {new_pitches}")

        # 원곡 음표를 새 note로 치환
        remapped = remap_music_notes(
            [data['inst1'], data['inst2']],
            data['notes_label'], new_notes_label
        )
        remapped_flat = remapped[0] + remapped[1]
        print(f"  치환: inst1={len(remapped[0])}, inst2={len(remapped[1])}")

        # 새 note로 학습 데이터 구성
        N_new = len(new_notes_label)
        X_new, y_new = prepare_training_data(
            ov, remapped, new_notes_label, T, N_new
        )
        X_tr_n, X_va_n, y_tr_n, y_va_n = train_test_split(
            X_new, y_new, test_size=0.2, random_state=SEED
        )

        label = f"{config_name}_transformer"
        print(f"\n  [{label}] 학습...")

        model = MusicGeneratorTransformer(C, N_new, d_model=128, nhead=4,
                                           num_layers=2, dropout=0.1, max_len=T)
        history = train_model(model, X_tr_n, y_tr_n, X_va_n, y_va_n,
                              epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
                              model_type='transformer', seq_len=T)
        val_loss = history[-1]['val_loss']

        gen = generate_from_model(model, ov, new_notes_label,
                                  model_type='transformer', adaptive_threshold=True)
        if not gen:
            print(f"  생성 실패")
            all_results['experiments'][label] = {'error': 'no notes'}
            continue

        print(f"  생성: {len(gen)}개 음표")

        # MusicXML + WAV용 출력
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        notes_to_xml([gen], tempo_bpm=66,
                     file_name=f"harmony_dl_{config_name}_{ts}",
                     output_dir="./output")

        # 평가: vs 원곡 + vs 치환 원곡
        seq_orig = evaluate_sequence_metrics(gen, original_notes, name=f"{label}_vs_orig")
        seq_remap = evaluate_sequence_metrics(gen, remapped_flat, name=f"{label}_vs_remap")

        # 화성 분석 (analyze_harmony 재활용)
        harmony = analyze_harmony(
            data['notes_label'], cl,
            new_notes_label, reassign['new_notes']
        )

        all_results['experiments'][label] = {
            'val_loss': round(val_loss, 4),
            'n_notes': len(gen),
            'vs_original': {k: round(v, 6) for k, v in seq_orig.items()},
            'vs_remapped': {k: round(v, 6) for k, v in seq_remap.items()},
            'note_dist_error': round(reassign['note_dist_error'], 4),
            'cycle_dist_error': round(reassign['cycle_dist_error'], 4),
            'consonance_score': round(reassign['consonance_score'], 4),
            'interval_error': round(reassign['interval_error'], 4),
            'new_pitches': new_pitches,
            'n_pitch_classes': harmony['n_pitch_classes'],
            'best_scale_match': harmony['best_scale_name'],
            'harmony_mode': extra_kwargs.get('harmony_mode'),
        }

        elapsed = time.time() - t1
        print(f"  소요: {elapsed:.1f}s")

    # ── 요약 ──
    elapsed_total = time.time() - t0

    print(f"\n{'='*100}")
    print(f"  요약")
    print(f"{'='*100}")
    print(f"  {'실험':<30} {'vloss':>6} {'notes':>6} {'pJS(orig)':>10} {'DTW(orig)':>10} {'pJS(remap)':>10} {'DTW(remap)':>10} {'#PC':>4}")
    print(f"  {'─'*30} {'─'*6} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*4}")

    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<30} ERROR")
            continue
        if 'vs_original' in r:
            vo = r['vs_original']
            vr = r['vs_remapped']
            print(f"  {name:<30} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
                  f"{vo['pitch_js']:>10.4f} {vo['dtw']:>10.4f} "
                  f"{vr['pitch_js']:>10.4f} {vr['dtw']:>10.4f} "
                  f"{r.get('n_pitch_classes',''):>4}")
        else:
            print(f"  {name:<30} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
                  f"{r.get('pitch_js',0):>10.4f} {r.get('dtw',0):>10.4f}")

    # JSON 저장
    out_path = os.path.join("docs", "step3_data", "note_reassign_harmony_dl_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
    print(f"총 소요: {elapsed_total:.1f}s")


if __name__ == '__main__':
    run()
