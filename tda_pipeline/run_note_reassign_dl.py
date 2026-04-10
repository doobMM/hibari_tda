"""
run_note_reassign_dl.py — 방향 A + Algorithm 2: 거리 보존 note 재분배 + DL 생성

1. Tonnetz 기반으로 새 note 집합 탐색 (거리 구조 보존)
2. 원곡의 onset 패턴을 새 note로 치환한 학습 데이터 구성
3. LSTM / Transformer로 학습 → 생성
4. wav 출력 + 평가

사용법:
  python run_note_reassign_dl.py
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from note_reassign import find_new_notes
from sequence_metrics import evaluate_sequence_metrics
from generation import notes_to_xml

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42
EPOCHS = 50
LR = 0.001
BATCH_SIZE = 32

# note 재분배 설정
REASSIGN_CONFIGS = [
    ('tonnetz_wide',  {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                       'pitch_range': (48, 84), 'n_candidates': 1000}),
    ('tonnetz_vwide', {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                       'pitch_range': (40, 88), 'n_candidates': 1000}),
]

MODEL_TYPES = ['lstm', 'transformer']


def remap_music_notes(music_notes_list, orig_notes_label, new_notes_label):
    """
    원곡의 음표를 새 note로 치환.

    orig label i → new label i (같은 인덱스) → 새 (pitch, dur)
    """
    # orig label → new (pitch, dur)
    orig_sorted = sorted(orig_notes_label.items(), key=lambda x: x[1])
    new_sorted = sorted(new_notes_label.items(), key=lambda x: x[1])

    # label(1-indexed) → new (pitch, dur)
    label_to_new = {}
    for (orig_note, label), (new_note, _) in zip(orig_sorted, new_sorted):
        label_to_new[label] = new_note

    # pitch → orig label 역매핑 (duration 포함)
    remapped_list = []
    for inst_notes in music_notes_list:
        remapped = []
        for start, pitch, end in inst_notes:
            duration = end - start
            key = (pitch, duration)
            if key in orig_notes_label:
                label = orig_notes_label[key]
                if label in label_to_new:
                    new_pitch, new_dur = label_to_new[label]
                    remapped.append((start, new_pitch, start + new_dur))
        remapped_list.append(remapped)
    return remapped_list


def run_experiment():
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorLSTM, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from sklearn.model_selection import train_test_split

    print("=" * 64)
    print(f"  방향 A + DL: 거리 보존 note 재분배 + LSTM/Transformer")
    print("=" * 64)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

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

    # ── Baseline: 원곡 note + DL ──
    print(f"\n{'='*64}")
    print(f"  [Baseline] 원곡 note → DL 학습/생성")
    print(f"{'='*64}")

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N
    )
    X_tr, X_va, y_tr, y_va = train_test_split(X_orig, y_orig, test_size=0.2, random_state=SEED_BASE)

    for model_type in MODEL_TYPES:
        print(f"\n  [{model_type}] 학습...")
        if model_type == 'lstm':
            model = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
        else:
            model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                              num_layers=2, dropout=0.1, max_len=T)
        history = train_model(model, X_tr, y_tr, X_va, y_va,
                              epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
                              model_type=model_type, seq_len=T)
        val_loss = history[-1]['val_loss']

        gen = generate_from_model(model, ov, data['notes_label'],
                                  model_type=model_type, adaptive_threshold=True)
        if gen:
            seq_m = evaluate_sequence_metrics(gen, original_notes, name=f"baseline_{model_type}")
            all_results['experiments'][f'baseline_{model_type}'] = {
                'val_loss': round(val_loss, 4), 'n_notes': len(gen),
                **{k: round(v, 6) for k, v in seq_m.items()},
            }

    # ── 각 reassign 설정 × 각 모델 ──
    for config_name, config_kwargs in REASSIGN_CONFIGS:
        print(f"\n{'='*64}")
        print(f"  [{config_name}] 새 note 탐색...")
        print(f"{'='*64}")

        reassign = find_new_notes(data['notes_label'], cl, seed=SEED_BASE, **config_kwargs)
        new_notes_label = reassign['new_notes_label']

        print(f"  note 거리 오차: {reassign['note_dist_error']:.4f}")
        print(f"  cycle 거리 오차: {reassign['cycle_dist_error']:.4f}")

        # 원곡 음표를 새 note로 치환
        remapped = remap_music_notes(
            [data['inst1'], data['inst2']],
            data['notes_label'], new_notes_label
        )
        remapped_flat = remapped[0] + remapped[1]

        print(f"  치환된 음표: inst1={len(remapped[0])}, inst2={len(remapped[1])}")

        # 새 note로 학습 데이터 구성
        N_new = len(new_notes_label)
        X_new, y_new = prepare_training_data(
            ov, remapped, new_notes_label, T, N_new
        )
        X_tr_n, X_va_n, y_tr_n, y_va_n = train_test_split(
            X_new, y_new, test_size=0.2, random_state=SEED_BASE
        )

        for model_type in MODEL_TYPES:
            label = f"{config_name}_{model_type}"
            print(f"\n  [{label}] 학습...")

            if model_type == 'lstm':
                model = MusicGeneratorLSTM(C, N_new, hidden_dim=128, num_layers=2, dropout=0.3)
            else:
                model = MusicGeneratorTransformer(C, N_new, d_model=128, nhead=4,
                                                  num_layers=2, dropout=0.1, max_len=T)

            history = train_model(model, X_tr_n, y_tr_n, X_va_n, y_va_n,
                                  epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
                                  model_type=model_type, seq_len=T)
            val_loss = history[-1]['val_loss']

            gen = generate_from_model(model, ov, new_notes_label,
                                      model_type=model_type, adaptive_threshold=True)
            if not gen:
                print(f"    ⚠ 생성 실패")
                all_results['experiments'][label] = {'error': 'no notes'}
                continue

            print(f"    생성: {len(gen)}개 음표")

            # XML + MIDI 출력
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            notes_to_xml([gen], tempo_bpm=66,
                         file_name=f"reassign_{label}_{ts}",
                         output_dir="./output")

            # 원곡 대비 평가
            seq_m = evaluate_sequence_metrics(gen, original_notes, name=label)

            # 치환된 원곡 대비 평가 (더 의미 있는 비교)
            seq_m2 = evaluate_sequence_metrics(gen, remapped_flat, name=f"{label}_vs_remapped")

            all_results['experiments'][label] = {
                'val_loss': round(val_loss, 4),
                'n_notes': len(gen),
                'vs_original': {k: round(v, 6) for k, v in seq_m.items()},
                'vs_remapped': {k: round(v, 6) for k, v in seq_m2.items()},
                'note_dist_error': round(reassign['note_dist_error'], 4),
                'cycle_dist_error': round(reassign['cycle_dist_error'], 4),
                'new_pitches': [n[0] for n in reassign['new_notes']],
            }

    # ── 요약 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "note_reassign_dl_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    print(f"\n{'='*64}")
    print(f"  요약")
    print(f"{'='*64}")
    print(f"  {'실험':<35} {'vloss':>6} {'notes':>6} {'pJS(orig)':>10} {'DTW(orig)':>10} {'pJS(remap)':>10} {'DTW(remap)':>10}")
    print(f"  {'─'*35} {'─'*6} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<35} ERROR")
            continue
        if 'vs_original' in r:
            vo = r['vs_original']
            vr = r['vs_remapped']
            print(f"  {name:<35} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
                  f"{vo['pitch_js']:>10.4f} {vo['dtw']:>10.4f} "
                  f"{vr['pitch_js']:>10.4f} {vr['dtw']:>10.4f}")
        else:
            print(f"  {name:<35} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
                  f"{r['pitch_js']:>10.4f} {r['dtw']:>10.4f}")

    print(f"\n총 소요: {elapsed:.1f}s")


if __name__ == '__main__':
    run_experiment()
