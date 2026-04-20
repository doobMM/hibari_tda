"""
train_fc_and_export.py — FC 모델 학습 + ONNX export
=======================================================

대시보드 Algorithm 2 (FC) 용 경량 모델을 학습하고 ONNX 로 저장한다.

데이터 흐름:
  1. Phase 1 export 산출물(`data/overlap_matrix_reference.json` — 이진 T×K) 로드
  2. `preprocessing.run_preprocess` 호출하여 원곡 `music_notes` + `notes_label` 획득
  3. (T, N) multi-hot 타깃 행렬 y 구성
  4. MusicGeneratorFC 아키텍처(K → 128 → 256 → N) 로 학습
     - 현재 최적 설정: K=14, N=23 (reference matrix 로드 후 런타임 결정)
     - circular shift + noise injection 증강
     - BCEWithLogitsLoss, Adam
  5. torch.onnx.export 로 ONNX 저장 → `public/models/fc_model.onnx`
  6. label_to_note 매핑 + 메타데이터 → `public/models/fc_model_meta.json`

주의:
- 기존 `tda_pipeline/` 코드는 import 만 한다. 수정 금지.
- 현재 연구 최저 FC 기록(JS≈0.00035, α=0.5 FC-cont)은 continuous 입력 + subset aug
  기준. 대시보드 사용자는 이진 edit matrix 를 생성 입력으로 쓰므로 이진 학습으로 구성.
- hidden_dim=128, dropout=0.3, 300 epochs. 학습시간 ~30 초 (CPU).
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn


# ──────────────────────────────────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
DASH_ROOT = HERE.parent
DATA_DIR = DASH_ROOT / 'data'
MODELS_DIR = DASH_ROOT / 'public' / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TDA_ROOT = DASH_ROOT.parent   # tda_pipeline/
sys.path.insert(0, str(TDA_ROOT))

from pipeline import TDAMusicPipeline
from config import PipelineConfig
from preprocessing import simul_chord_lists, simul_union_by_dict


T_TOTAL = 1088


# ──────────────────────────────────────────────────────────────────────────
# FC 모델 (generation.py MusicGeneratorFC 와 동일 구조)
# ──────────────────────────────────────────────────────────────────────────
class FCModel(nn.Module):
    def __init__(self, num_cycles: int, num_notes: int,
                 hidden_dim: int = 128, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(num_cycles, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, num_notes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)   # raw logits


# ──────────────────────────────────────────────────────────────────────────
# 데이터 구성
# ──────────────────────────────────────────────────────────────────────────
def load_binary_overlap() -> np.ndarray:
    """Phase 1 에서 저장된 이진 overlap 로드."""
    with open(DATA_DIR / 'overlap_matrix_reference.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
    T, K = d['T'], d['K']
    vals = np.array(d['values'], dtype=np.float32).reshape(T, K)
    return vals


def build_music_notes(pipeline) -> List[List[Tuple[int, int, int]]]:
    """파이프라인 캐시에서 두 악기별 (start, pitch, end) 리스트 구축."""
    adn_i = pipeline._cache['adn_i']
    notes_dict = pipeline._cache['notes_dict']
    notes_label = pipeline._cache['notes_label']

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    # 역매핑: label → (pitch, dur)
    label_to_pd = {v: k for k, v in notes_label.items()}

    # 각 (t, label) 에서 새로운 onset 만 추출하여 (start, pitch, end) 구성
    # 동일 label 이 연속 시점에 있으면 앞쪽만 onset 으로 간주
    prev_active = set()
    notes_list: List[Tuple[int, int, int]] = []

    for t in range(min(T_TOTAL, len(note_sets))):
        curr = set(note_sets[t]) if note_sets[t] is not None else set()
        new_onsets = curr - prev_active
        for lbl in new_onsets:
            if lbl not in label_to_pd:
                continue
            pitch, dur = label_to_pd[lbl]
            end = min(T_TOTAL, t + dur)
            notes_list.append((t, int(pitch), int(end)))
        prev_active = curr

    return [notes_list, []]   # 두 악기 이미 union 된 상태 → 한 리스트에만


def build_onehot_y(music_notes: List[List[Tuple[int, int, int]]],
                   notes_label: dict,
                   T: int, N: int) -> np.ndarray:
    """(T, N) multi-hot onset 행렬."""
    onehot = np.zeros((T, N), dtype=np.float32)
    for inst in music_notes:
        for (start, pitch, end) in inst:
            dur = end - start
            key = (pitch, dur)
            if key in notes_label:
                label_idx = notes_label[key] - 1
                if 0 <= start < T and 0 <= label_idx < N:
                    onehot[start, label_idx] = 1.0
    return onehot


def augment(X: np.ndarray, y: np.ndarray,
            n_shifts: int = 4, noise_prob: float = 0.03,
            n_noise: int = 3, rng: np.random.Generator = None) -> Tuple[np.ndarray, np.ndarray]:
    """circular shift + noise injection (subset aug 생략 — cycle_labeled 의존)."""
    if rng is None:
        rng = np.random.default_rng(0)
    T = X.shape[0]
    all_X = [X]
    all_y = [y]

    for _ in range(n_shifts):
        s = int(rng.integers(1, T))
        all_X.append(np.roll(X, s, axis=0))
        all_y.append(np.roll(y, s, axis=0))

    for _ in range(n_noise):
        mask = rng.random(X.shape) < noise_prob
        Xn = X.copy()
        Xn[mask] = 1.0 - Xn[mask]
        all_X.append(Xn.astype(np.float32))
        all_y.append(y.copy())

    return np.concatenate(all_X, axis=0), np.concatenate(all_y, axis=0)


# ──────────────────────────────────────────────────────────────────────────
# 학습 + export
# ──────────────────────────────────────────────────────────────────────────
def train(X: np.ndarray, y: np.ndarray,
          num_cycles: int, num_notes: int,
          epochs: int = 300, lr: float = 1e-3, batch_size: int = 64,
          seed: int = 42) -> Tuple[FCModel, List[dict]]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = FCModel(num_cycles, num_notes, hidden_dim=128, dropout=0.3)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    # 8:2 split (시점 순서 유지, 증강 후 shuffle)
    N_total = X.shape[0]
    perm = np.random.RandomState(seed).permutation(N_total)
    Xp = X[perm]
    yp = y[perm]
    sp = int(N_total * 0.85)
    X_tr = torch.from_numpy(Xp[:sp])
    y_tr = torch.from_numpy(yp[:sp])
    X_va = torch.from_numpy(Xp[sp:])
    y_va = torch.from_numpy(yp[sp:])

    history = []
    for ep in range(epochs):
        model.train()
        idx = torch.randperm(X_tr.shape[0])
        total, nb = 0.0, 0
        for s in range(0, X_tr.shape[0], batch_size):
            e = min(s + batch_size, X_tr.shape[0])
            b = idx[s:e]
            pred = model(X_tr[b])
            loss = loss_fn(pred, y_tr[b])
            opt.zero_grad(); loss.backward(); opt.step()
            total += loss.item(); nb += 1
        tr_loss = total / max(nb, 1)

        model.eval()
        with torch.no_grad():
            va_loss = loss_fn(model(X_va), y_va).item()
        history.append({'epoch': ep, 'train_loss': tr_loss, 'val_loss': va_loss})
        if ep % 30 == 0 or ep == epochs - 1:
            print(f"  [Epoch {ep:3d}] train={tr_loss:.5f}  val={va_loss:.5f}")

    return model, history


def export_onnx(model: FCModel, num_cycles: int, num_notes: int,
                out_path: Path):
    model.eval()
    # (batch, C) → (batch, N). batch 축 동적.
    dummy = torch.randn(1, num_cycles)
    # torch ≥ 2.6 기본 dynamo exporter 는 onnxscript 요구 → 레거시(TorchScript) 경로 강제
    try:
        torch.onnx.export(
            model, dummy, str(out_path),
            input_names=['overlap'],
            output_names=['logits'],
            dynamic_axes={'overlap': {0: 'T'}, 'logits': {0: 'T'}},
            opset_version=17,
            dynamo=False,
        )
    except TypeError:
        # 아주 오래된 torch 에서는 dynamo 파라미터 자체가 없음
        torch.onnx.export(
            model, dummy, str(out_path),
            input_names=['overlap'],
            output_names=['logits'],
            dynamic_axes={'overlap': {0: 'T'}, 'logits': {0: 'T'}},
            opset_version=17,
        )
    print(f"[onnx] 저장: {out_path} ({out_path.stat().st_size/1024:.1f} KB)")


def save_meta(num_cycles: int, num_notes: int,
              notes_label: dict, history: List[dict],
              out_path: Path):
    # label → (pitch, dur) 역매핑 (1-indexed label → 0-indexed label_idx → pitch/dur)
    label_to_pd = {v - 1: k for k, v in notes_label.items()}
    labels_sorted = []
    for li in sorted(label_to_pd.keys()):
        pitch, dur = label_to_pd[li]
        labels_sorted.append({
            'label_idx': li,
            'label': li + 1,
            'pitch': int(pitch),
            'dur': int(dur),
        })

    meta = {
        'version': '2.0',
        'architecture': f'MusicGeneratorFC ({num_cycles} → 128 → 256 → {num_notes})',
        'num_cycles': num_cycles,
        'num_notes': num_notes,
        'input': {
            'shape': [None, num_cycles],
            'dtype': 'float32',
            'description': 'Binary overlap row [0/1]. (T, C) 배치도 가능 (C=num_cycles).',
        },
        'output': {
            'shape': [None, num_notes],
            'dtype': 'float32',
            'description': 'Raw logits. sigmoid(logits) → multi-label 확률.',
        },
        'label_to_note': labels_sorted,
        'threshold': {
            'default': 0.5,
            'adaptive_target_on_ratio': 0.15,
            'min_threshold': 0.1,
            'description': 'adaptive=true 시 전체 확률의 top 15% 를 임계값으로.',
        },
        'training': {
            'epochs': len(history),
            'final_train_loss': round(history[-1]['train_loss'], 5) if history else None,
            'final_val_loss': round(history[-1]['val_loss'], 5) if history else None,
            'augmentation': 'circular shift × 4 + noise(p=0.03) × 3',
            'loss': 'BCEWithLogitsLoss',
            'optimizer': 'Adam (lr=1e-3)',
        },
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[meta] 저장: {out_path}")


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────
def main():
    import os
    os.chdir(TDA_ROOT)

    print("=" * 70)
    print("  FC Model 학습 + ONNX Export")
    print("=" * 70)

    # 1) 파이프라인 전처리 (preprocessing 만 — PH 불필요)
    print("\n[1] 전처리 시작")
    cfg = PipelineConfig()
    cfg.midi.auto_detect = True
    pipeline = TDAMusicPipeline(cfg)
    pipeline.run_preprocessing()

    notes_label = pipeline._cache['notes_label']
    N = len(notes_label)
    print(f"  N = {N} notes")

    # 2) X, y 구성
    print("\n[2] 학습 데이터 구성")
    X_raw = load_binary_overlap()          # (T, K) float32
    T, K = X_raw.shape
    music_notes = build_music_notes(pipeline)
    y_raw = build_onehot_y(music_notes, notes_label, T, N)
    total_onsets = int(y_raw.sum())
    print(f"  X: {X_raw.shape}, density={X_raw.mean():.4f}")
    print(f"  y: {y_raw.shape}, 총 onset 수={total_onsets}")

    # 3) 증강
    rng = np.random.default_rng(42)
    X_aug, y_aug = augment(X_raw, y_raw, rng=rng)
    print(f"  증강 후: X={X_aug.shape}, y={y_aug.shape}")

    # 4) 학습
    print("\n[3] FC 학습")
    model, history = train(X_aug, y_aug, num_cycles=K, num_notes=N,
                           epochs=300, lr=1e-3, batch_size=64)

    # 5) ONNX export
    print("\n[4] ONNX Export")
    onnx_path = MODELS_DIR / 'fc_model.onnx'
    export_onnx(model, K, N, onnx_path)

    # 6) meta 저장
    print("\n[5] 메타데이터 저장")
    meta_path = MODELS_DIR / 'fc_model_meta.json'
    save_meta(K, N, notes_label, history, meta_path)

    # 7) 간단한 자체 검증 (PyTorch vs onnxruntime)
    print("\n[6] ONNX 추론 검증")
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(onnx_path))
        torch_out = model.eval()(torch.from_numpy(X_raw)).detach().numpy()
        ort_out = sess.run(['logits'], {'overlap': X_raw})[0]
        err = float(np.abs(torch_out - ort_out).max())
        print(f"  torch vs ort 최대 오차: {err:.6e}")
        if err > 1e-4:
            print("  [경고] 오차가 큼 — ONNX 입력/출력 확인 필요")
        # 간단한 statistics
        probs = 1.0 / (1.0 + np.exp(-ort_out))
        top15 = np.quantile(probs.flatten(), 0.85)
        print(f"  probs range: [{probs.min():.4f}, {probs.max():.4f}], "
              f"top15 ≈ {top15:.4f}")
    except ImportError:
        print("  onnxruntime 미설치 — 검증 생략 (pip install onnxruntime)")

    print("\n" + "=" * 70)
    print("  완료")
    print("=" * 70)


if __name__ == '__main__':
    main()
