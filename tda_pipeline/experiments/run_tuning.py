"""
run_tuning.py — DL 하이퍼파라미터 튜닝
========================================

3가지 모델(FC, LSTM, Transformer)에 대해
핵심 하이퍼파라미터를 grid search하고
eval_metrics으로 종합 평가합니다.

탐색 대상:
  - hidden_dim: 64, 128, 256
  - learning_rate: 0.0005, 0.001, 0.003
  - epochs: 100, 200
  - dropout: 0.1, 0.3
  - augmentation: 5x, 10x
"""

import sys, os, time, itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build_data():
    """학습에 필요한 데이터를 모두 준비합니다."""
    import pandas as pd
# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences
    )
    from overlap import (
        label_cycles_from_persistence, build_activation_matrix,
        build_overlap_matrix
    )
    from preprocessing import simul_chord_lists, simul_union_by_dict

    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

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

    pkl_path = os.path.join(os.path.dirname(__file__),
                            "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    df = pd.read_pickle(pkl_path)
    persistence = {}
    for _, row in df.iterrows():
        persistence.setdefault(row['cycle'], []).append(
            (row['rate'], row['birth'], row['death']))
    cycle_labeled = label_cycles_from_persistence(persistence)

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
    import pandas as pd
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled, threshold=0.35, total_length=T)

    return {
        'overlap': overlap.values.astype(np.float32),
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'cycle_labeled': cycle_labeled,
        'T': T, 'C': overlap.shape[1], 'N': len(notes_label),
    }


def run_single_experiment(data, model_type, hidden_dim, lr, epochs, dropout,
                          aug_k_values, aug_n_shifts):
    """단일 하이퍼파라미터 조합으로 학습 + 평가를 수행합니다."""
    import torch
    from generation import (
        prepare_training_data, augment_training_data,
        MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from eval_metrics import evaluate_generation

    overlap = data['overlap']
    T, C, N = data['T'], data['C'], data['N']

    # 데이터 준비
    X, y = prepare_training_data(
        overlap, [data['inst1_real'], data['inst2_real']],
        data['notes_label'], T, N
    )
    X_aug, y_aug = augment_training_data(
        X, y, overlap, data['cycle_labeled'],
        k_values=aug_k_values, n_shifts=aug_n_shifts,
        noise_prob=0.03, n_noise_copies=1
    )

    # 분할
    n = len(X_aug)
    idx = np.random.permutation(n)
    split = int(n * 0.7)
    X_tr, y_tr = X_aug[idx[:split]], y_aug[idx[:split]]
    X_va, y_va = X_aug[idx[split:]], y_aug[idx[split:]]

    # 모델 생성
    if model_type == 'fc':
        model = MusicGeneratorFC(C, N, hidden_dim=hidden_dim, dropout=dropout)
    elif model_type == 'lstm':
        model = MusicGeneratorLSTM(C, N, hidden_dim=hidden_dim,
                                    num_layers=2, dropout=dropout)
    elif model_type == 'transformer':
        model = MusicGeneratorTransformer(C, N, d_model=hidden_dim,
                                           nhead=4, num_layers=2, dropout=dropout)

    # 학습 (출력 억제)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        history = train_model(
            model, X_tr, y_tr, X_va, y_va,
            epochs=epochs, lr=lr, batch_size=64,
            model_type=model_type, seq_len=T
        )

    val_loss = history[-1]['val_loss']
    train_loss = history[-1]['train_loss']
    overfit_gap = val_loss - train_loss

    # 생성
    generated = generate_from_model(model, overlap, data['notes_label'],
                                     model_type=model_type)

    # 평가
    original = [data['inst1_real'], data['inst2_real']]
    metrics = evaluate_generation(generated, original, data['notes_label'])

    return {
        'val_loss': val_loss,
        'train_loss': train_loss,
        'overfit_gap': overfit_gap,
        **metrics,
        'model': model,
        'generated': generated,
    }


if __name__ == "__main__":
    print("=" * 70)
    print("  DL 하이퍼파라미터 튜닝")
    print("=" * 70)

    print("\n데이터 준비 중...")
    data = build_data()
    print(f"  Overlap: ({data['T']}, {data['C']}), Notes: {data['N']}")

    # ── 탐색 공간 ──
    # 핵심 파라미터만 탐색 (전체 grid는 너무 큼)
    configs = []

    # FC: 가장 가벼우므로 넓게 탐색
    for hd in [64, 128, 256]:
        for lr in [0.0005, 0.001, 0.003]:
            for do in [0.1, 0.3]:
                configs.append(('fc', hd, lr, 100, do, [10, 20], 2))  # 5x aug

    # LSTM: 핵심 조합만
    for hd in [64, 128]:
        for lr in [0.001, 0.003]:
            configs.append(('lstm', hd, lr, 100, 0.2, [10, 20, 30], 3))  # 10x aug

    # Transformer: 핵심 조합만 (overfitting 방지에 집중)
    for hd in [64, 128]:
        for lr in [0.0005, 0.001]:
            for do in [0.2, 0.3]:
                configs.append(('transformer', hd, lr, 100, do, [10, 20, 30], 3))

    print(f"\n총 {len(configs)}개 조합 탐색")

    results = []
    best_by_model = {}

    for i, (mtype, hd, lr, ep, do, aug_k, aug_s) in enumerate(configs):
        label = f"{mtype}/hd{hd}/lr{lr}/do{do}"
        print(f"\n  [{i+1}/{len(configs)}] {label}", end=" ", flush=True)

        t0 = time.time()
        try:
            r = run_single_experiment(data, mtype, hd, lr, ep, do, aug_k, aug_s)
            dt = time.time() - t0
            r['config'] = label
            r['model_type'] = mtype
            r['hidden_dim'] = hd
            r['lr'] = lr
            r['dropout'] = do
            r['time'] = dt
            results.append(r)

            print(f"val={r['val_loss']:.4f} JS={r['js_divergence']:.4f}"
                  f" notes={r['n_notes']} ({dt:.0f}s)")

            # 모델별 best 추적
            key = mtype
            if key not in best_by_model or r['val_loss'] < best_by_model[key]['val_loss']:
                best_by_model[key] = r

        except Exception as e:
            print(f"실패: {e}")
            continue

    # ── 결과 요약 ──
    print(f"\n{'='*70}")
    print("  모델별 Best 결과")
    print("=" * 70)

    print(f"\n  {'Model':<12} | {'Config':<30} | {'Val':>6} | {'JS':>6}"
          f" | {'Notes':>5} | {'Cov':>4} | {'Gap':>5}")
    print(f"  {'-'*12} | {'-'*30} | {'-'*6} | {'-'*6}"
          f" | {'-'*5} | {'-'*4} | {'-'*5}")

    for mtype in ['fc', 'lstm', 'transformer']:
        if mtype in best_by_model:
            r = best_by_model[mtype]
            print(f"  {mtype:<12} | {r['config']:<30} | {r['val_loss']:>6.4f}"
                  f" | {r['js_divergence']:>6.4f} | {r['n_notes']:>5}"
                  f" | {r['note_coverage']:>3.0%} | {r['overfit_gap']:>+5.3f}")

    # ── 전체 결과 정렬 (val_loss 기준) ──
    print(f"\n{'='*70}")
    print(f"  전체 Top 10 (val_loss 기준)")
    print("=" * 70)

    results.sort(key=lambda x: x['val_loss'])
    print(f"\n  {'#':>2} | {'Config':<30} | {'Val':>6} | {'JS':>6}"
          f" | {'Notes':>5} | {'Gap':>6}")
    print(f"  {'--':>2} | {'-'*30} | {'-'*6} | {'-'*6}"
          f" | {'-'*5} | {'-'*6}")
    for i, r in enumerate(results[:10]):
        print(f"  {i+1:>2} | {r['config']:<30} | {r['val_loss']:>6.4f}"
              f" | {r['js_divergence']:>6.4f} | {r['n_notes']:>5}"
              f" | {r['overfit_gap']:>+6.3f}")

    # ── Best 모델로 MIDI 생성 ──
    print(f"\n{'='*70}")
    print("  Best 모델별 MIDI 생성")
    print("=" * 70)

    from generation import notes_to_xml
    import datetime

    for mtype in ['fc', 'lstm', 'transformer']:
        if mtype not in best_by_model:
            continue
        r = best_by_model[mtype]
        gen = r['generated']
        if not gen:
            print(f"  {mtype}: 생성된 note 없음")
            continue

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"tuned_{mtype}_{ts}"
        notes_to_xml([gen], tempo_bpm=66, file_name=fname, output_dir="./output")

        try:
            from music21 import converter
            score = converter.parse(f"./output/{fname}.musicxml")
            score.write('midi', fp=f"./output/{fname}.mid")
            print(f"  {mtype}: ./output/{fname}.mid"
                  f" (val={r['val_loss']:.4f}, JS={r['js_divergence']:.4f})")
        except Exception as e:
            print(f"  {mtype}: MIDI 변환 실패 - {e}")

    print(f"\n{'='*70}")
    print("  완료")
    print("=" * 70)
