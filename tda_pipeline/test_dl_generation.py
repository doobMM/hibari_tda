"""
test_dl_generation.py — Deep Learning 음악 생성 모델 검증
==========================================================

3가지 모델(FC, LSTM, Transformer)을 학습하고 음악을 생성합니다.

1. 데이터 정합성 확인: X(T,C)와 y(T,N)의 시간축 일치 검증
2. 3개 모델 학습 (각 50 epochs)
3. 생성된 음악을 MusicXML/MIDI로 출력
4. 모델별 성능 비교
"""

import sys, os, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build_data():
    """파이프라인에서 학습 데이터를 구성합니다."""
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences,
        simul_chord_lists, simul_union_by_dict
    )
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach
    )
    from overlap import (
        label_cycles_from_persistence, build_activation_matrix,
        build_overlap_matrix
    )
    import pandas as pd

    midi_file = os.path.join(os.path.dirname(__file__),
                             "Ryuichi_Sakamoto_-_hibari.mid")

    # 전처리
    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    module_notes = inst1_real[:59]
    notes_label, notes_counts = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, cs1 = build_chord_labels(active1)
    _, cs2 = build_chord_labels(active2)
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    num_notes = len(notes_label)

    # Persistence (pkl에서 로드)
    pkl_path = os.path.join(os.path.dirname(__file__),
                            "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    df = pd.read_pickle(pkl_path)
    persistence = {}
    for _, row in df.iterrows():
        persistence.setdefault(row['cycle'], []).append(
            (row['rate'], row['birth'], row['death'])
        )

    cycle_labeled = label_cycles_from_persistence(persistence)

    # Note-time 행렬
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    nodes_list = list(range(1, num_notes + 1))
    T = 1088
    note_time_data = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    note_time_data[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(note_time_data, columns=nodes_list)

    # Overlap matrix
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled,
                                   threshold=0.35, total_length=T)

    return {
        'overlap': overlap.values.astype(np.float32),
        'inst1_real': inst1_real,
        'inst2_real': inst2_real,
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'cycle_labeled': cycle_labeled,
        'num_notes': num_notes,
        'T': T,
        'tempo': tempo,
    }


if __name__ == "__main__":
    import torch
    from generation import (
        prepare_training_data, build_onehot_matrix,
        MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer,
        train_model, generate_from_model, notes_to_xml
    )

    print("=" * 60)
    print("  Deep Learning 음악 생성 모델 검증")
    print("=" * 60)

    # ── 데이터 준비 ──
    print("\n데이터 준비 중...")
    data = build_data()

    overlap = data['overlap']       # (T=1088, C=48)
    music_notes = [data['inst1_real'], data['inst2_real']]
    notes_label = data['notes_label']
    T, C = overlap.shape
    N = data['num_notes']

    print(f"  Overlap: ({T}, {C})")
    print(f"  Notes: {N}종")

    # ── 데이터 정합성 검증 ──
    print(f"\n{'='*60}")
    print("  데이터 정합성 검증")
    print("=" * 60)

    X, y = prepare_training_data(overlap, music_notes, notes_label, T, N)

    print(f"  X shape: {X.shape}  (expected: ({T}, {C}))")
    print(f"  y shape: {y.shape}  (expected: ({T}, {N}))")

    assert X.shape == (T, C), f"X shape 불일치: {X.shape} != ({T}, {C})"
    assert y.shape == (T, N), f"y shape 불일치: {y.shape} != ({T}, {N})"
    print(f"  ✓ X와 y가 동일한 시간축 T={T} 공유")

    # 활성 비율 확인
    x_on = (X > 0).sum() / X.size
    y_on = (y > 0).sum() / y.size
    print(f"  X ON ratio: {x_on:.4f}")
    print(f"  y ON ratio: {y_on:.4f}")

    # ── Train/Valid 분할 ──
    split = int(T * 0.7)
    X_train, X_valid = X[:split], X[split:]
    y_train, y_valid = y[:split], y[split:]
    print(f"  Train: {split} steps, Valid: {T - split} steps")

    # ── 3개 모델 학습 + 생성 ──
    models_config = [
        ('FC', 'fc', MusicGeneratorFC(C, N, hidden_dim=128, dropout=0.3)),
        ('LSTM', 'lstm', MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)),
        ('Transformer', 'transformer', MusicGeneratorTransformer(C, N, d_model=128, nhead=4, num_layers=2)),
    ]

    results = []

    for name, mtype, model in models_config:
        print(f"\n{'='*60}")
        print(f"  Model: {name}")
        print("=" * 60)

        n_params = sum(p.numel() for p in model.parameters())
        print(f"  Parameters: {n_params:,}")

        t0 = time.time()
        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=50, lr=0.001, batch_size=64,
            model_type=mtype
        )
        train_time = time.time() - t0
        final_val = history[-1]['val_loss']
        print(f"  학습 완료 ({train_time:.1f}s), final val_loss: {final_val:.5f}")

        # 생성
        generated = generate_from_model(
            model, overlap, notes_label,
            model_type=mtype, threshold=0.5
        )

        pitches = set(p for _, p, _ in generated)
        print(f"  생성: {len(generated)} notes, {len(pitches)} unique pitches")

        # MusicXML 출력
        if generated:
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"algo2_{name}_{ts}"
            try:
                notes_to_xml(
                    [generated], tempo_bpm=66,
                    file_name=fname, output_dir="./output"
                )
            except Exception as e:
                print(f"  XML 출력 실패: {e}")

        results.append({
            'name': name,
            'params': n_params,
            'val_loss': final_val,
            'n_notes': len(generated),
            'n_pitches': len(pitches),
            'time': train_time,
        })

    # ── 요약 ──
    print(f"\n{'='*60}")
    print("  요약")
    print("=" * 60)
    print(f"\n  {'Model':<12s} | {'Params':>8s} | {'Val Loss':>8s} | {'Notes':>6s} | {'Pitches':>7s} | {'Time':>5s}")
    print(f"  {'-'*12} | {'-'*8} | {'-'*8} | {'-'*6} | {'-'*7} | {'-'*5}")
    for r in results:
        print(f"  {r['name']:<12s} | {r['params']:>8,} | {r['val_loss']:>8.5f} | "
              f"{r['n_notes']:>6} | {r['n_pitches']:>7} | {r['time']:>4.0f}s")

    # MIDI 변환
    print(f"\n  MIDI 변환 중...")
    try:
        from music21 import converter
        import glob
        for f in glob.glob('output/algo2_*_*.musicxml'):
            score = converter.parse(f)
            midi_path = f.replace('.musicxml', '.mid')
            score.write('midi', fp=midi_path)
            print(f"    {os.path.basename(f)} → .mid")
    except Exception as e:
        print(f"    변환 실패: {e}")

    print(f"\n{'='*60}")
    print("  완료")
    print("=" * 60)
