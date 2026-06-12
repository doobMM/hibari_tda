"""
train_om_vae_and_export.py — OM VAE 학습 + ONNX export (구조 탐험 패널용)
==========================================================================

목적: 대시보드 "구조 탐험 (AI)" 패널의 latent 슬라이더.
  - 사용자가 그린 30초 세그먼트 OM 과 hibari 참조 OM 을 latent 공간에서 보간
    ("hibari다움 0~100%")
  - z ~ N(0, I) 샘플로 "hibari 문법 안의 새 구조" 생성
  - encode→decode 재구성으로 손그림 OM 을 학습된 매니폴드로 사영 (OOD 완화)

데이터:
  data/overlap_matrix_continuous.json (T=1088 × K=14, 연속 [0,1])
  → 슬라이딩 윈도 (W=60, stride=2) ≈ 515 샘플, 각 840차원 (t-major flatten)
  → 가우시안 노이즈 증강 ×3

모델: VAE 840 → 256 → (μ, logσ²) z=12 → 256 → 840 (sigmoid)
손실: BCE 재구성 + β·KL (β=1.0, 50 epoch warmup)

산출:
  public/models/om_vae_encoder.onnx   ('om' [None,840] → 'mu','logvar' [None,12])
  public/models/om_vae_decoder.onnx   ('z' [None,12] → 'om_recon' [None,840])
  public/models/om_vae_meta.json      (z_ref: 블록 m=0..17 참조 latent 포함)

규칙: train_fc_and_export.py 와 동일 컨벤션. 기존 파이프라인 코드 수정 없음.
"""

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn

HERE = Path(__file__).resolve().parent
DASH_ROOT = HERE.parent
DATA_DIR = DASH_ROOT / 'data'
MODELS_DIR = DASH_ROOT / 'public' / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)

WINDOW = 60          # 30초 세그먼트 (8분음표 60개)
STRIDE = 2
LATENT = 12
HIDDEN = 256
EPOCHS = 500
# 손실 스케일: 재구성은 840차원 합, KL은 12차원 합 (표준 VAE).
# mean-mean 조합은 KL 압력이 상대적으로 과대 → posterior collapse 유발 (1차 시도에서 확인).
BETA = 1.0
WARMUP = 100         # KL warmup epochs
SEED = 42


# ──────────────────────────────────────────────────────────────────────────
# 모델
# ──────────────────────────────────────────────────────────────────────────
class Encoder(nn.Module):
    def __init__(self, dim_in: int, hidden: int, latent: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(dim_in, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.mu = nn.Linear(hidden, latent)
        self.logvar = nn.Linear(hidden, latent)

    def forward(self, x):
        h = self.body(x)
        return self.mu(h), self.logvar(h)


class Decoder(nn.Module):
    def __init__(self, latent: int, hidden: int, dim_out: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(latent, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, dim_out), nn.Sigmoid(),
        )

    def forward(self, z):
        return self.body(z)


# ──────────────────────────────────────────────────────────────────────────
# 데이터
# ──────────────────────────────────────────────────────────────────────────
def load_continuous_om() -> Tuple[np.ndarray, int, int]:
    with open(DATA_DIR / 'overlap_matrix_continuous.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
    T, K = d['T'], d['K']
    vals = np.array(d['values'], dtype=np.float32).reshape(T, K)
    vals = np.clip(vals, 0.0, 1.0)
    return vals, T, K


def sliding_windows(om: np.ndarray, w: int, stride: int) -> np.ndarray:
    T = om.shape[0]
    out = []
    for s in range(0, T - w + 1, stride):
        out.append(om[s:s + w].reshape(-1))   # t-major flatten (행=시간)
    return np.stack(out).astype(np.float32)


def augment(X: np.ndarray, n_noise: int = 3, sigma: float = 0.04,
            rng: np.random.Generator = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(SEED)
    outs = [X]
    for _ in range(n_noise):
        noisy = X + rng.normal(0.0, sigma, X.shape).astype(np.float32)
        outs.append(np.clip(noisy, 0.0, 1.0))
    return np.concatenate(outs, axis=0)


# ──────────────────────────────────────────────────────────────────────────
# 학습
# ──────────────────────────────────────────────────────────────────────────
def train(X: np.ndarray, dim: int) -> Tuple[Encoder, Decoder, List[dict]]:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    enc = Encoder(dim, HIDDEN, LATENT)
    dec = Decoder(LATENT, HIDDEN, dim)
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=1e-3)
    # 재구성: 차원 합 → 배치 평균 (sum-BCE). KL 도 차원 합 → 배치 평균.
    bce_sum = nn.BCELoss(reduction='none')

    def recon_loss(xr, x):
        return bce_sum(xr, x).sum(dim=1).mean()

    perm = np.random.RandomState(SEED).permutation(X.shape[0])
    Xp = X[perm]
    sp = int(X.shape[0] * 0.9)
    X_tr = torch.from_numpy(Xp[:sp])
    X_va = torch.from_numpy(Xp[sp:])

    history = []
    batch = 64
    for ep in range(EPOCHS):
        beta = BETA * min(1.0, (ep + 1) / WARMUP)
        enc.train(); dec.train()
        idx = torch.randperm(X_tr.shape[0])
        tot_r, tot_k, nb = 0.0, 0.0, 0
        for s in range(0, X_tr.shape[0], batch):
            b = idx[s:s + batch]
            x = X_tr[b]
            mu, logvar = enc(x)
            std = torch.exp(0.5 * logvar)
            z = mu + std * torch.randn_like(std)
            xr = dec(z)
            recon = recon_loss(xr, x)
            kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1).mean()
            loss = recon + beta * kl
            opt.zero_grad(); loss.backward(); opt.step()
            tot_r += recon.item(); tot_k += kl.item(); nb += 1

        enc.eval(); dec.eval()
        with torch.no_grad():
            mu, logvar = enc(X_va)
            xr = dec(mu)
            va_recon = recon_loss(xr, X_va).item()
        history.append({'epoch': ep, 'train_recon': tot_r / nb,
                        'train_kl': tot_k / nb, 'val_recon': va_recon})
        if ep % 50 == 0 or ep == EPOCHS - 1:
            print(f"  [Epoch {ep:3d}] recon={tot_r/nb:.5f}  kl={tot_k/nb:.4f}  "
                  f"val_recon={va_recon:.5f}  beta={beta:.2f}")
    return enc, dec, history


# ──────────────────────────────────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────────────────────────────────
def export_onnx(enc: Encoder, dec: Decoder, dim: int):
    enc.eval(); dec.eval()
    enc_path = MODELS_DIR / 'om_vae_encoder.onnx'
    dec_path = MODELS_DIR / 'om_vae_decoder.onnx'
    kw = dict(opset_version=17, dynamo=False)
    try:
        torch.onnx.export(enc, torch.randn(1, dim), str(enc_path),
                          input_names=['om'], output_names=['mu', 'logvar'],
                          dynamic_axes={'om': {0: 'B'}, 'mu': {0: 'B'}, 'logvar': {0: 'B'}},
                          **kw)
        torch.onnx.export(dec, torch.randn(1, LATENT), str(dec_path),
                          input_names=['z'], output_names=['om_recon'],
                          dynamic_axes={'z': {0: 'B'}, 'om_recon': {0: 'B'}},
                          **kw)
    except TypeError:
        kw.pop('dynamo')
        torch.onnx.export(enc, torch.randn(1, dim), str(enc_path),
                          input_names=['om'], output_names=['mu', 'logvar'],
                          dynamic_axes={'om': {0: 'B'}, 'mu': {0: 'B'}, 'logvar': {0: 'B'}},
                          **kw)
        torch.onnx.export(dec, torch.randn(1, LATENT), str(dec_path),
                          input_names=['z'], output_names=['om_recon'],
                          dynamic_axes={'z': {0: 'B'}, 'om_recon': {0: 'B'}},
                          **kw)
    print(f"[onnx] encoder: {enc_path.stat().st_size/1024:.1f} KB, "
          f"decoder: {dec_path.stat().st_size/1024:.1f} KB")
    return enc_path, dec_path


def main():
    print("=" * 70)
    print("  OM VAE 학습 + ONNX Export (구조 탐험 패널)")
    print("=" * 70)

    om, T, K = load_continuous_om()
    dim = WINDOW * K
    print(f"\n[1] 연속 OM 로드: T={T}, K={K}, 평균 활성도={om.mean():.4f}")

    X = sliding_windows(om, WINDOW, STRIDE)
    print(f"[2] 슬라이딩 윈도: {X.shape[0]} 샘플 × {X.shape[1]} 차원")
    X_aug = augment(X)
    print(f"    증강 후: {X_aug.shape[0]} 샘플")

    print("\n[3] VAE 학습")
    enc, dec, history = train(X_aug, dim)

    print("\n[4] ONNX Export")
    enc_path, dec_path = export_onnx(enc, dec, dim)

    # 참조 블록 latent 사전계산 (m=0..17, 슬라이더의 'hibari다움' 끝점)
    print("\n[5] 참조 블록 latent (z_ref) 계산")
    n_blocks = T // WINDOW
    z_refs = []
    with torch.no_grad():
        for m in range(n_blocks):
            seg = om[m * WINDOW:(m + 1) * WINDOW].reshape(1, -1)
            mu, _ = enc(torch.from_numpy(seg))
            z_refs.append([round(float(v), 5) for v in mu[0]])
    print(f"    {n_blocks}개 블록 latent 저장")

    # 검증: torch vs ort + 재구성/샘플 통계
    print("\n[6] 검증")
    import onnxruntime as ort
    es = ort.InferenceSession(str(enc_path))
    ds = ort.InferenceSession(str(dec_path))
    seg0 = om[:WINDOW].reshape(1, -1)
    with torch.no_grad():
        t_mu, _ = enc(torch.from_numpy(seg0))
        t_rec = dec(t_mu).numpy()
    o_mu = es.run(['mu'], {'om': seg0})[0]
    o_rec = ds.run(['om_recon'], {'z': o_mu})[0]
    err = float(np.abs(t_rec - o_rec).max())
    print(f"  torch vs ort 최대 오차: {err:.6e}")
    rec_mae = float(np.abs(o_rec - seg0).mean())
    print(f"  블록0 재구성 MAE: {rec_mae:.4f} (입력 평균 {seg0.mean():.4f}, 출력 평균 {o_rec.mean():.4f})")
    rng = np.random.default_rng(7)
    z_rand = rng.normal(0, 1, (8, LATENT)).astype(np.float32)
    samples = ds.run(['om_recon'], {'z': z_rand})[0]
    print(f"  prior 샘플 8개 평균 활성도: {samples.mean():.4f} (참조 {om.mean():.4f})")

    meta = {
        'version': '1.0',
        'architecture': f'VAE {dim} → {HIDDEN} → z={LATENT} → {HIDDEN} → {dim}',
        'window': WINDOW,
        'K': K,
        'latent_dim': LATENT,
        'layout': 't-major flatten (행=시간 60, 열=cycle 14)',
        'input': {'name': 'om', 'shape': [None, dim], 'dtype': 'float32',
                  'description': '연속 OM 세그먼트 [0,1] flatten'},
        'encoder_outputs': ['mu', 'logvar'],
        'decoder_input': {'name': 'z', 'shape': [None, LATENT]},
        'decoder_output': {'name': 'om_recon', 'shape': [None, dim],
                           'description': 'sigmoid — 연속 OM [0,1]'},
        'z_ref_blocks': z_refs,
        'training': {
            'samples': int(X_aug.shape[0]),
            'epochs': EPOCHS,
            'beta': BETA,
            'final_val_recon_bce': round(history[-1]['val_recon'], 5),
            'block0_recon_mae': round(rec_mae, 5),
            'prior_sample_density': round(float(samples.mean()), 5),
            'reference_density': round(float(om.mean()), 5),
            'augmentation': f'sliding window stride={STRIDE} + gaussian noise σ=0.04 ×3',
        },
    }
    with open(MODELS_DIR / 'om_vae_meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[meta] 저장: {MODELS_DIR / 'om_vae_meta.json'}")

    print("\n" + "=" * 70)
    print("  완료")
    print("=" * 70)


if __name__ == '__main__':
    main()
