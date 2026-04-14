"""
run_temporal_reorder_dl.py — 방향 B + Algorithm 2: DL 모델에 시간 재배치 적용

Algorithm 1은 시점별 독립 샘플링이라 재배치 효과가 없었음.
LSTM/Transformer는 시퀀스 맥락을 학습하므로,
재배치된 중첩행렬 → 다른 맥락 → 다른 선율이 기대됨.

실험 설계:
  1. 원본 overlap으로 모델 학습 (baseline)
  2. 재배치된 overlap을 생성 시 입력으로 사용 (학습은 원본)
  3. pitch JS(유지) + DTW(변화) + NCD(구조) 비교

사용법:
  python run_temporal_reorder_dl.py
"""
import os, sys, time, json, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from temporal_reorder import reorder_overlap_matrix
from sequence_metrics import evaluate_sequence_metrics

# ── 설정 ────────────────────────────────────────────────────────────────

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42

# DL 모델 설정
MODEL_TYPES = ['lstm', 'transformer']  # FC는 시점 독립이므로 제외
EPOCHS = 50
BATCH_SIZE = 32
LR = 0.001

STRATEGIES = [
    ('baseline',         {}),
    ('segment_shuffle',  {}),
    ('block_permute',    {'block_size': 32}),
    ('block_permute',    {'block_size': 64}),
    ('markov_resample',  {'temperature': 1.0}),
    ('markov_resample',  {'temperature': 1.5}),
]


def run_experiment():
    print("=" * 64)
    print(f"  방향 B + DL: 시간 재배치 × LSTM/Transformer — {TRACK_NAME}")
    print("=" * 64)

    # lazy import (torch는 무거움)
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorLSTM, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from sklearn.model_selection import train_test_split

    # ── 1. 전처리 + PH ──
    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles found"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    T = data['T']
    N = len(data['notes_label'])
    C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    # ── 2. 학습 데이터 준비 (원본 overlap) ──
    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']],
        data['notes_label'], T, N
    )
    print(f"[학습 데이터] X: {X_orig.shape}, y: {y_orig.shape}")

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': EPOCHS, 'models': {},
    }

    # ── 3. 각 모델 × 각 전략 ──
    for model_type in MODEL_TYPES:
        print(f"\n{'='*64}")
        print(f"  모델: {model_type.upper()}")
        print(f"{'='*64}")

        # 모델 학습 (원본 overlap으로 1회만)
        print(f"\n  [학습] 원본 overlap으로 {model_type} 학습 ({EPOCHS} epochs)...")
        X_train, X_valid, y_train, y_valid = train_test_split(
            X_orig, y_orig, test_size=0.2, random_state=SEED_BASE
        )

        if model_type == 'lstm':
            model = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
        else:
            model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                              num_layers=2, dropout=0.1, max_len=T)

        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
            model_type=model_type, seq_len=T
        )
        val_loss = history[-1]['val_loss']
        print(f"  최종 val_loss: {val_loss:.4f}")

        model_results = {'val_loss': round(val_loss, 4), 'strategies': {}}

        for strategy_name, kwargs in STRATEGIES:
            if strategy_name == 'baseline':
                label = 'baseline'
                gen_overlap = ov
                print(f"\n  {'─'*56}")
                print(f"  [baseline] 원본 overlap → {model_type} 생성")
                print(f"  {'─'*56}")
            else:
                label = strategy_name
                if kwargs:
                    label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())

                reordered, info = reorder_overlap_matrix(
                    ov, strategy=strategy_name, seed=SEED_BASE, **kwargs
                )
                gen_overlap = reordered
                print(f"\n  {'─'*56}")
                print(f"  [{label}] 재배치 overlap → {model_type} 생성")
                print(f"  {'─'*56}")

            # 재배치된 overlap으로 생성
            gen = generate_from_model(
                model, gen_overlap, data['notes_label'],
                model_type=model_type, adaptive_threshold=True,
                min_onset_gap=0
            )

            if not gen:
                print(f"    ⚠ 생성된 음표 없음")
                model_results['strategies'][label] = {'error': 'no notes generated'}
                continue

            # 평가
            seq_m = evaluate_sequence_metrics(gen, original_notes, name=f"{model_type}_{label}")

            model_results['strategies'][label] = {
                'n_notes': len(gen),
                'pitch_js': round(seq_m['pitch_js'], 6),
                'transition_js': round(seq_m['transition_js'], 6),
                'dtw': round(seq_m['dtw'], 6),
                'ncd': round(seq_m['ncd'], 6),
            }

        # baseline 대비 변화율 계산
        bl = model_results['strategies'].get('baseline', {})
        if bl and 'error' not in bl:
            for label, r in model_results['strategies'].items():
                if label == 'baseline' or 'error' in r:
                    continue
                delta = {}
                for k in ['pitch_js', 'transition_js', 'dtw', 'ncd']:
                    if bl[k] > 0:
                        delta[k] = round(100 * (r[k] - bl[k]) / bl[k], 1)
                    else:
                        delta[k] = 0.0
                r['delta_pct'] = delta

                pitch_ok = delta['pitch_js'] < 20
                dtw_diff = delta['dtw'] > 10
                r['verdict'] = ("★ 유망" if (pitch_ok and dtw_diff)
                                else "△ 보통" if pitch_ok
                                else "✗ 분포 붕괴")

        all_results['models'][model_type] = model_results

    # ── 4. 요약 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "temporal_reorder_dl_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # 요약 테이블
    for model_type in MODEL_TYPES:
        mr = all_results['models'][model_type]
        print(f"\n{'='*64}")
        print(f"  {model_type.upper()} 요약 (val_loss: {mr['val_loss']:.4f})")
        print(f"{'='*64}")
        print(f"  {'전략':<35} {'notes':>6} {'pitch JS':>10} {'DTW':>10} {'trans JS':>10} {'NCD':>10} {'판정':>8}")
        print(f"  {'─'*35} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")

        for label, r in mr['strategies'].items():
            if 'error' in r:
                print(f"  {label:<35} {'ERROR':>6}")
                continue
            d = r.get('delta_pct', {})
            delta_str = lambda k: f"{d[k]:+.1f}%" if d else "  (기준)"
            print(f"  {label:<35} {r['n_notes']:>6} {r['pitch_js']:>10.4f} {r['dtw']:>10.4f} "
                  f"{r['transition_js']:>10.4f} {r['ncd']:>10.4f} {r.get('verdict', '(기준)'):>8}")

    print(f"\n총 소요: {elapsed:.1f}s")


if __name__ == '__main__':
    run_experiment()
