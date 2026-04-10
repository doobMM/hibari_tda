"""
run_temporal_reorder_dl_v2.py — 방향 B 확장 실험

실험 1: Positional encoding 제거 (use_pos_emb=False)
  → 위치 정보 없이 순수 attention만으로 학습
  → 재배치 시 위치 임베딩이 "원래 자리"를 기억하는 문제 해결

실험 2: 재배치된 overlap으로 재학습
  → 학습 자체를 재배치 데이터로 수행
  → 모델이 "재배치된 시간 구조"를 직접 학습

사용법:
  python run_temporal_reorder_dl_v2.py
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from temporal_reorder import reorder_overlap_matrix
from sequence_metrics import evaluate_sequence_metrics

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42
EPOCHS = 50
BATCH_SIZE = 32
LR = 0.001

# segment_shuffle이 가장 유망했으므로 집중 + 나머지도 포함
STRATEGIES = [
    ('segment_shuffle',  {}),
    ('block_permute',    {'block_size': 32}),
    ('markov_resample',  {'temperature': 1.0}),
]


def train_and_generate(model, model_type, X_train, y_train, X_valid, y_valid,
                       gen_overlap, notes_label, original_notes, T, label):
    """모델 학습 → 생성 → 평가를 수행하는 헬퍼."""
    from generation import train_model, generate_from_model

    history = train_model(
        model, X_train, y_train, X_valid, y_valid,
        epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
        model_type=model_type, seq_len=T
    )
    val_loss = history[-1]['val_loss']

    gen = generate_from_model(
        model, gen_overlap, notes_label,
        model_type=model_type, adaptive_threshold=True
    )
    if not gen:
        return {'error': 'no notes', 'val_loss': round(val_loss, 4)}

    seq_m = evaluate_sequence_metrics(gen, original_notes, name=label)
    return {
        'val_loss': round(val_loss, 4),
        'n_notes': len(gen),
        'pitch_js': round(seq_m['pitch_js'], 6),
        'transition_js': round(seq_m['transition_js'], 6),
        'dtw': round(seq_m['dtw'], 6),
        'ncd': round(seq_m['ncd'], 6),
    }


def run_experiment():
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from sklearn.model_selection import train_test_split

    print("=" * 64)
    print(f"  방향 B 확장: PE 제거 + 재배치 학습 — {TRACK_NAME}")
    print("=" * 64)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    T = data['T']; N = len(data['notes_label']); C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N
    )

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N, 'epochs': EPOCHS,
        'experiments': {},
    }

    # ═══════════════════════════════════════════════════════════════════
    # 실험 0: Baseline (PE 있음, 원본 학습, 원본 생성) — 이전 결과 재현
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*64}")
    print(f"  [실험 0] Baseline: PE 있음 + 원본 학습 + 원본 생성")
    print(f"{'='*64}")

    X_tr, X_va, y_tr, y_va = train_test_split(X_orig, y_orig, test_size=0.2, random_state=SEED_BASE)

    model_bl = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                         num_layers=2, dropout=0.1, max_len=T,
                                         use_pos_emb=True)
    bl_result = train_and_generate(
        model_bl, 'transformer', X_tr, y_tr, X_va, y_va,
        ov, data['notes_label'], original_notes, T, "baseline"
    )
    all_results['experiments']['baseline'] = bl_result
    print(f"  val_loss={bl_result['val_loss']}, pitch_js={bl_result.get('pitch_js','?')}, dtw={bl_result.get('dtw','?')}")

    # ═══════════════════════════════════════════════════════════════════
    # 실험 1: PE 제거 + 원본 학습 + 재배치 생성
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*64}")
    print(f"  [실험 1] PE 제거: 원본 학습 → 재배치 생성")
    print(f"{'='*64}")

    model_nope = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                           num_layers=2, dropout=0.1, max_len=T,
                                           use_pos_emb=False)
    # 원본으로 학습
    print("  학습 (PE 제거)...")
    history_nope = train_model(
        model_nope, X_tr, y_tr, X_va, y_va,
        epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
        model_type='transformer', seq_len=T
    )
    nope_val = history_nope[-1]['val_loss']
    print(f"  val_loss: {nope_val:.4f}")

    # baseline 생성 (PE 제거, 원본 overlap)
    gen_bl = generate_from_model(
        model_nope, ov, data['notes_label'],
        model_type='transformer', adaptive_threshold=True
    )
    if gen_bl:
        seq_bl = evaluate_sequence_metrics(gen_bl, original_notes, name="noPE_baseline")
        all_results['experiments']['noPE_baseline'] = {
            'val_loss': round(nope_val, 4), 'n_notes': len(gen_bl),
            'pitch_js': round(seq_bl['pitch_js'], 6),
            'transition_js': round(seq_bl['transition_js'], 6),
            'dtw': round(seq_bl['dtw'], 6),
            'ncd': round(seq_bl['ncd'], 6),
        }

    # 각 전략으로 재배치 생성
    for strategy_name, kwargs in STRATEGIES:
        label = f"noPE_{strategy_name}"
        if kwargs:
            label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())

        reordered, _ = reorder_overlap_matrix(ov, strategy=strategy_name, seed=SEED_BASE, **kwargs)
        gen = generate_from_model(
            model_nope, reordered, data['notes_label'],
            model_type='transformer', adaptive_threshold=True
        )
        if not gen:
            all_results['experiments'][label] = {'error': 'no notes'}
            continue

        seq_m = evaluate_sequence_metrics(gen, original_notes, name=label)
        all_results['experiments'][label] = {
            'n_notes': len(gen),
            'pitch_js': round(seq_m['pitch_js'], 6),
            'transition_js': round(seq_m['transition_js'], 6),
            'dtw': round(seq_m['dtw'], 6),
            'ncd': round(seq_m['ncd'], 6),
        }

    # ═══════════════════════════════════════════════════════════════════
    # 실험 2: PE 있음 + 재배치 overlap으로 재학습 + 재배치 생성
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*64}")
    print(f"  [실험 2] 재배치 학습: 재배치 overlap으로 학습+생성")
    print(f"{'='*64}")

    for strategy_name, kwargs in STRATEGIES:
        label = f"retrain_{strategy_name}"
        if kwargs:
            label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())

        print(f"\n  [{label}]")
        reordered, _ = reorder_overlap_matrix(ov, strategy=strategy_name, seed=SEED_BASE, **kwargs)

        # 재배치된 X로 학습 데이터 재구성 (y는 원본 유지)
        X_reord = reordered.astype(np.float32)
        X_r_tr, X_r_va, y_r_tr, y_r_va = train_test_split(
            X_reord, y_orig, test_size=0.2, random_state=SEED_BASE
        )

        model_rt = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                             num_layers=2, dropout=0.1, max_len=T,
                                             use_pos_emb=True)
        result = train_and_generate(
            model_rt, 'transformer', X_r_tr, y_r_tr, X_r_va, y_r_va,
            reordered, data['notes_label'], original_notes, T, label
        )
        all_results['experiments'][label] = result
        print(f"  val_loss={result['val_loss']}, pitch_js={result.get('pitch_js','?')}, dtw={result.get('dtw','?')}")

    # ═══════════════════════════════════════════════════════════════════
    # 실험 3: PE 제거 + 재배치 학습 + 재배치 생성 (조합)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*64}")
    print(f"  [실험 3] PE 제거 + 재배치 학습 (조합)")
    print(f"{'='*64}")

    for strategy_name, kwargs in STRATEGIES:
        label = f"noPE_retrain_{strategy_name}"
        if kwargs:
            label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())

        print(f"\n  [{label}]")
        reordered, _ = reorder_overlap_matrix(ov, strategy=strategy_name, seed=SEED_BASE, **kwargs)

        X_reord = reordered.astype(np.float32)
        X_r_tr, X_r_va, y_r_tr, y_r_va = train_test_split(
            X_reord, y_orig, test_size=0.2, random_state=SEED_BASE
        )

        model_combo = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                                num_layers=2, dropout=0.1, max_len=T,
                                                use_pos_emb=False)
        result = train_and_generate(
            model_combo, 'transformer', X_r_tr, y_r_tr, X_r_va, y_r_va,
            reordered, data['notes_label'], original_notes, T, label
        )
        all_results['experiments'][label] = result
        print(f"  val_loss={result['val_loss']}, pitch_js={result.get('pitch_js','?')}, dtw={result.get('dtw','?')}")

    # ═══════════════════════════════════════════════════════════════════
    # 요약
    # ═══════════════════════════════════════════════════════════════════
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "temporal_reorder_dl_v2_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # baseline 기준으로 delta 계산
    bl = all_results['experiments'].get('baseline', {})

    print(f"\n{'='*64}")
    print(f"  전체 요약 — Transformer (baseline: pitch_js={bl.get('pitch_js','?')}, dtw={bl.get('dtw','?')})")
    print(f"{'='*64}")
    print(f"  {'실험':<45} {'vloss':>6} {'pJS':>8} {'DTW':>8} {'tJS':>8} {'NCD':>8} {'ΔDTW%':>8}")
    print(f"  {'─'*45} {'─'*6} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    bl_dtw = bl.get('dtw', 0)
    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<45} ERROR")
            continue
        dtw_delta = (100 * (r['dtw'] - bl_dtw) / bl_dtw) if bl_dtw > 0 else 0
        print(f"  {name:<45} {r['val_loss']:>6.3f} {r['pitch_js']:>8.4f} {r['dtw']:>8.4f} "
              f"{r['transition_js']:>8.4f} {r['ncd']:>8.4f} {dtw_delta:>+7.1f}%")

    print(f"\n총 소요: {elapsed:.1f}s")


if __name__ == '__main__':
    run_experiment()
