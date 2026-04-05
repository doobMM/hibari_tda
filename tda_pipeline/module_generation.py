"""
module_generation.py — 모듈 단위 음악 생성
==============================================

전체 시퀀스(1088 시점) 대신 4마디 모듈(32 eighth notes) 단위로
학습하고 생성합니다.

장점:
  - 학습 데이터: 1개 시퀀스 → 33개 시퀀스 (33x 증가)
  - LSTM/Transformer가 모듈 내부 선율 패턴을 학습 가능
  - 모듈을 hibari와 동일 순서로 배치하여 곡 구조 보존

파이프라인:
  1. 원곡을 33개 모듈로 분할
  2. 각 모듈의 overlap(32, C)와 note(32, N)를 학습 데이터로 구성
  3. DL 모델이 "모듈의 overlap 패턴 → 모듈의 note 시퀀스" 학습
  4. 생성 시: 중첩행렬을 모듈 단위로 잘라 모델에 입력 → 33개 모듈 생성
  5. 33개 모듈을 순서대로 이어붙여 전체 곡 완성
"""

import numpy as np
import os, sys, time
from typing import List, Tuple, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODULE_SIZE = 32  # 4마디 x 8 eighth notes


def split_into_modules(notes: List[Tuple[int, int, int]],
                       total_time: int,
                       module_size: int = MODULE_SIZE
                       ) -> List[List[Tuple[int, int, int]]]:
    """
    note 리스트를 모듈 단위로 분할합니다.

    각 모듈의 note는 시작 시점이 모듈 내부로 오프셋됩니다.
    예: module 3의 note (start=100, pitch, end=102)
        → (100-96=4, pitch, min(102-96, 32)=6)

    Args:
        notes: [(start, pitch, end), ...] 전체 곡 note
        total_time: 전체 시간축 길이
        module_size: 모듈 길이 (기본 32)

    Returns:
        [module_0_notes, module_1_notes, ...] 각 모듈의 note 리스트
    """
    n_modules = total_time // module_size
    modules = [[] for _ in range(n_modules)]

    for s, p, e in notes:
        m_idx = s // module_size
        if m_idx >= n_modules:
            continue
        # 모듈 내부 오프셋으로 변환
        m_start = s - m_idx * module_size
        m_end = min(e - m_idx * module_size, module_size)
        if m_end > m_start:
            modules[m_idx].append((m_start, p, m_end))

    return modules


def build_module_training_data(overlap_matrix: np.ndarray,
                                music_notes: List[List[Tuple[int, int, int]]],
                                notes_label: dict,
                                total_time: int,
                                num_notes: int = 23,
                                module_size: int = MODULE_SIZE
                                ) -> Tuple[np.ndarray, np.ndarray]:
    """
    모듈 단위 학습 데이터를 구성합니다.

    X: (n_modules, module_size, C) — 각 모듈의 overlap 시퀀스
    y: (n_modules, module_size, N) — 각 모듈의 note multi-hot 시퀀스

    33개 모듈 = 33개 독립 학습 샘플 (기존: 1개 시퀀스)
    """
    from generation import build_onehot_matrix

    n_modules = total_time // module_size
    C = overlap_matrix.shape[1]

    # 전체 onehot 행렬
    onehot = build_onehot_matrix(music_notes, notes_label, total_time, num_notes)

    # overlap도 total_time 길이로 자르기
    T = min(overlap_matrix.shape[0], total_time)
    overlap = overlap_matrix[:T]

    # 모듈 단위로 분할
    X_modules = []
    y_modules = []

    for m in range(n_modules):
        t_start = m * module_size
        t_end = t_start + module_size

        if t_end <= T:
            X_modules.append(overlap[t_start:t_end])
            y_modules.append(onehot[t_start:t_end])

    X = np.array(X_modules, dtype=np.float32)  # (n_modules, 32, C)
    y = np.array(y_modules, dtype=np.float32)   # (n_modules, 32, N)

    return X, y


def augment_module_data(X: np.ndarray, y: np.ndarray,
                        n_noise: int = 3,
                        noise_prob: float = 0.03) -> Tuple[np.ndarray, np.ndarray]:
    """
    모듈 단위 data augmentation.

    - Noise injection: overlap에 bit flip
    - Shuffle: 모듈 순서 섞기 (모듈 내부는 유지)

    모듈 자체가 33개이므로 circular shift 대신 noise에 집중.
    """
    all_X = [X]
    all_y = [y]

    for _ in range(n_noise):
        mask = np.random.random(X.shape) < noise_prob
        X_noisy = X.copy()
        X_noisy[mask] = 1.0 - X_noisy[mask]
        all_X.append(X_noisy.astype(np.float32))
        all_y.append(y.copy())

    X_aug = np.concatenate(all_X, axis=0)
    y_aug = np.concatenate(all_y, axis=0)

    # 셔플
    idx = np.random.permutation(len(X_aug))
    return X_aug[idx], y_aug[idx]


def train_module_model(model, X_train, y_train, X_valid, y_valid,
                       epochs=100, lr=0.001, model_type='lstm',
                       epoch_callback=None):
    """
    모듈 단위 학습.

    X: (n_modules, 32, C), y: (n_modules, 32, N)
    시퀀스 모델(LSTM/Transformer)에 자연스럽게 맞는 형태.
    """
    import torch
    import torch.nn as nn

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    X_tr = torch.from_numpy(X_train)
    y_tr = torch.from_numpy(y_train)
    X_va = torch.from_numpy(X_valid)
    y_va = torch.from_numpy(y_valid)

    history = []
    batch_size = 8  # 모듈 단위 배치

    for epoch in range(epochs):
        model.train()
        n = len(X_tr)
        indices = torch.randperm(n)
        total_loss = 0.0
        n_batches = 0

        for s in range(0, n, batch_size):
            e = min(s + batch_size, n)
            idx = indices[s:e]
            pred = model(X_tr[idx])           # (batch, 32, N)
            loss = criterion(pred, y_tr[idx]) # (batch, 32, N)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)

        model.eval()
        with torch.no_grad():
            val_pred = model(X_va)
            val_loss = criterion(val_pred, y_va).item()

        history.append({'epoch': epoch, 'train_loss': avg_loss, 'val_loss': val_loss})

        if epoch % 20 == 0 or epoch == epochs - 1:
            print(f"  [Epoch {epoch:3d}] train={avg_loss:.5f}  val={val_loss:.5f}")

        if epoch_callback:
            epoch_callback(epoch, epochs, avg_loss, val_loss)

    return history


def generate_modules(model, overlap_matrix: np.ndarray,
                     notes_label: dict, model_type: str = 'lstm',
                     module_size: int = MODULE_SIZE,
                     threshold: float = 0.5,
                     adaptive: bool = True,
                     min_onset_gap: int = 0
                     ) -> List[Tuple[int, int, int]]:
    """
    학습된 모델로 모듈 단위 음악을 생성하고 전체로 이어붙입니다.

    1. overlap을 모듈 단위로 분할
    2. 각 모듈을 모델에 입력 → note 예측
    3. 모듈 내부 시점을 전체 시점으로 복원
    4. 33개 모듈 결합 → 전체 곡
    """
    import torch

    model.eval()
    label_to_note = {v - 1: k for k, v in notes_label.items()}

    T = overlap_matrix.shape[0]
    n_modules = T // module_size

    all_notes = []
    last_onset = -min_onset_gap

    for m in range(n_modules):
        t_start = m * module_size
        t_end = t_start + module_size

        if t_end > T:
            break

        # 모듈의 overlap 추출
        mod_overlap = overlap_matrix[t_start:t_end]  # (32, C)
        X = torch.from_numpy(mod_overlap.astype(np.float32)).unsqueeze(0)  # (1, 32, C)

        with torch.no_grad():
            logits = model(X).squeeze(0)  # (32, N)
            probs = torch.sigmoid(logits)

        M, N = probs.shape

        # Adaptive threshold
        if adaptive:
            target_on = 0.15
            k = max(1, int(M * N * target_on))
            flat = probs.flatten()
            topk_val = torch.topk(flat, k).values[-1].item()
            th = max(topk_val, 0.1)
        else:
            th = threshold

        # 모듈 내 note 생성
        for t in range(M):
            global_t = t_start + t
            if min_onset_gap > 0 and (global_t - last_onset) < min_onset_gap:
                continue

            onset_here = False
            for n in range(N):
                if probs[t, n] >= th:
                    if n in label_to_note:
                        pitch, dur = label_to_note[n]
                        all_notes.append((global_t, pitch, global_t + dur))
                        onset_here = True

            if onset_here:
                last_onset = global_t

    return all_notes


# ═══════════════════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pickle
    import pandas as pd
    from generation import (
        MusicGeneratorLSTM, MusicGeneratorTransformer, MusicGeneratorFC,
        notes_to_xml
    )
    from eval_metrics import evaluate_generation
    from preprocessing import (
        load_and_quantize, split_instruments, build_note_labels,
        group_notes_with_duration, build_chord_labels, chord_to_note_labels
    )

    print("=" * 60)
    print("  모듈 단위 음악 생성")
    print("=" * 60)

    # 데이터
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]
    notes_label, notes_counts = build_note_labels(inst1_real[:59])
    N = len(notes_label)

    # Tonnetz 캐시에서 overlap 로드
    cache_path = os.path.join(os.path.dirname(__file__), "cache", "metric_tonnetz.pkl")
    with open(cache_path, 'rb') as f:
        cached = pickle.load(f)
    overlap = cached['overlap'].values.astype(np.float32)
    cycle_labeled = cached['cycle_labeled']
    C = overlap.shape[1]

    # 모듈 데이터 구축
    print(f"\n  Overlap: ({overlap.shape[0]}, {C})")
    total_time = 1056  # 33 modules x 32
    X, y = build_module_training_data(
        overlap, [inst1_real, inst2_real], notes_label, total_time, N
    )
    print(f"  모듈 데이터: X={X.shape}, y={y.shape}")
    print(f"  = {X.shape[0]}개 모듈, 각 {X.shape[1]} 시점")

    # Augmentation (4x = 원본 + noise 3개)
    X_aug, y_aug = augment_module_data(X, y, n_noise=3)
    print(f"  증강 후: {X_aug.shape[0]}개 모듈 ({X_aug.shape[0] / X.shape[0]:.0f}x)")

    # Train/Valid 분할
    n = len(X_aug)
    split = int(n * 0.75)
    X_tr, y_tr = X_aug[:split], y_aug[:split]
    X_va, y_va = X_aug[split:], y_aug[split:]
    print(f"  Train: {len(X_tr)}, Valid: {len(X_va)}")

    # 3개 모델 학습 + 생성
    original = [inst1_real, inst2_real]
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    models = [
        ("FC", "fc", MusicGeneratorFC(C, N, hidden_dim=256, dropout=0.3)),
        ("LSTM", "lstm", MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.2)),
        ("Transformer", "transformer", MusicGeneratorTransformer(C, N, d_model=128, nhead=4, num_layers=2, dropout=0.1)),
    ]

    results = []

    for name, mtype, model in models:
        print(f"\n{'='*60}")
        print(f"  {name} (모듈 단위)")
        print("=" * 60)

        n_params = sum(p.numel() for p in model.parameters())
        print(f"  Parameters: {n_params:,}")

        t0 = time.time()
        if mtype == 'fc':
            # FC는 시점별 독립 → 모듈을 풀어서 (n*32, C) 형태로
            X_tr_flat = X_tr.reshape(-1, C)
            y_tr_flat = y_tr.reshape(-1, N)
            X_va_flat = X_va.reshape(-1, C)
            y_va_flat = y_va.reshape(-1, N)

            import torch, torch.nn as nn, io, contextlib
            from generation import train_model
            with contextlib.redirect_stdout(io.StringIO()):
                train_model(model, X_tr_flat, y_tr_flat, X_va_flat, y_va_flat,
                            epochs=100, lr=0.001, batch_size=64, model_type='fc')
            # FC 생성은 기존 방식
            from generation import generate_from_model
            gen = generate_from_model(model, overlap[:total_time], notes_label,
                                       model_type='fc', min_onset_gap=3)
        else:
            history = train_module_model(
                model, X_tr, y_tr, X_va, y_va,
                epochs=100, lr=0.001, model_type=mtype
            )
            gen = generate_modules(
                model, overlap[:total_time], notes_label,
                model_type=mtype, min_onset_gap=3
            )

        dt = time.time() - t0

        # 평가
        metrics = evaluate_generation(gen, original, notes_label, name=f"{name} (module)")

        # MIDI 출력
        if gen:
            fname = f"module_{name}_{ts}"
            notes_to_xml([gen], tempo_bpm=66, file_name=fname, output_dir="./output")
            try:
                from music21 import converter
                converter.parse(f"./output/{fname}.musicxml").write('midi', fp=f"./output/{fname}.mid")
                print(f"  -> output/{fname}.mid")
            except Exception as e:
                print(f"  MIDI 변환 실패: {e}")

        results.append({
            'name': name, 'notes': len(gen), 'js': metrics['js_divergence'],
            'coverage': metrics['note_coverage'], 'time': dt
        })

    # 요약
    print(f"\n{'='*60}")
    print("  요약 (모듈 단위 vs 전체 시퀀스)")
    print("=" * 60)
    print(f"\n  {'Model':<12s} | {'Notes':>6s} | {'JS Div':>8s} | {'Coverage':>8s} | {'Time':>5s}")
    print(f"  {'-'*12} | {'-'*6} | {'-'*8} | {'-'*8} | {'-'*5}")
    for r in results:
        print(f"  {r['name']:<12s} | {r['notes']:>6d} | {r['js']:>8.4f} | {r['coverage']:>7.0%} | {r['time']:>4.0f}s")

    print(f"\n  참고: 전체 시퀀스 Tonnetz 결과")
    print(f"  FC: JS=0.002, LSTM: JS=0.267, Transformer: JS=0.009")
    print(f"\n{'='*60}")
    print("  완료")
    print("=" * 60)
