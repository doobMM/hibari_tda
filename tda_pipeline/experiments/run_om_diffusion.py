"""
run_om_diffusion.py
====================

OM(중첩행렬) 디퓨전 모델 실험.

연구 질문:
  hibari의 30초 구조(OM 세그먼트, W=60 × K=14) 생성에서,
  DDPM 디퓨전이 기존 VAE prior 샘플보다
  (a) 더 사실적이고(구조 충실) (b) 더 다양한 구조를 만드는가?

데이터 파이프라인은 train_om_vae_and_export.py 를 그대로 재사용:
  load_continuous_om() → sliding_windows(W=60, stride=2) → augment(×3 gaussian)

VAE baseline: hibari_dashboard/public/models/om_vae_decoder.onnx
  (z~N(0,I) 64개 → decoder → 64 샘플)

DDPM 스펙 (지시대로 그대로 구현):
  - x0 ∈ [0,1]^840 → [-1,1] 스케일
  - cosine noise schedule (Nichol & Dhariwal), T=200
  - denoiser: MLP, concat(x_t, temb) → 512 SiLU → 512 SiLU → 840 (ε 예측)
    temb: 128-dim sinusoidal(timestep) → Linear 128→128 SiLU
  - 학습: MSE(ε), Adam 1e-3, batch 128, epochs 800, seed 42
    val 10% split, best-checkpoint(val MSE 최저) 사용
  - 샘플링: ancestral DDPM, 64개, seed 7, [-1,1]→[0,1] 클램프

평가 (3원 비교: REAL 64 / VAE 64 / DIFF 64):
  같은 밀도 일치 이진화(기대 활성수 N=round(Σp)만큼 상위 셀 ON) 적용.
  REAL은 이미 이진에 가까움 → τ=0.5.
  1. 구조 사실성: density 분포, per-cycle 활성비율 JS divergence, 시간 자기상관(해밍 유사도)
  2. 다양성: 그룹 내 평균 pairwise 해밍 거리
  3. 음악 레벨: 그룹당 OM 8개 × Algo1 seed 3개 = 24곡, pitch JS vs 원곡

실행:
    python experiments/run_om_diffusion.py       (루트에서)
    python run_om_diffusion.py                   (experiments/ 안에서)

출력:
    docs/step3_data/om_diffusion_results.json
    cache/om_diffusion.pt   (디퓨전 가중치 — ONNX export는 하지 않음)

주의: Python만. 웹/UI 수정 없음. 커밋 없음. 결과는 있는 그대로 보고(negative 허용).
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List, Tuple

import numpy as np

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import torch
import torch.nn as nn

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from generation import CycleSetManager, NodePool, algorithm1_optimized

# `suite.MIDI_FILE` 몽키패치 제거 (2026-08-15, T14).
# BASE_DIR 근본 수정(739c389) 으로 suite 가 이미 루트를 가리킨다.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))            # experiments/
TDA_ROOT = os.path.dirname(BASE_DIR)                              # tda_pipeline/
DASH_DIR = os.path.join(TDA_ROOT, "hibari_dashboard")
DATA_DIR = os.path.join(DASH_DIR, "data")
MODELS_DIR = os.path.join(DASH_DIR, "public", "models")
STEP3_DIR = os.path.join(TDA_ROOT, "docs", "step3_data")
CACHE_DIR = os.path.join(TDA_ROOT, "cache")

# ─────────────────────────────────────────────
# 데이터 파이프라인 상수 (train_om_vae_and_export.py 동일)
# ─────────────────────────────────────────────
WINDOW = 60
STRIDE = 2
K = 14
DIM = WINDOW * K  # 840
DATA_SEED = 42

# ─────────────────────────────────────────────
# DDPM 하이퍼파라미터 (지시 스펙 그대로)
# ─────────────────────────────────────────────
T_DIFFUSION = 200
TEMB_DIM = 128
HIDDEN = 512
BATCH = 128
EPOCHS = 800
LR = 1e-3
TRAIN_SEED = 42
SAMPLE_SEED = 7
N_SAMPLE = 64

# ─────────────────────────────────────────────
# 평가 프로토콜 상수
# ─────────────────────────────────────────────
REAL_TAU = 0.5          # REAL 이진화 threshold (이미 이진에 가까움)
N_GROUP = 64             # 그룹당 샘플 수 (구조 평가용)
MUSIC_OM_PER_GROUP = 8   # 음악 레벨: 그룹당 OM 개수
MUSIC_SEEDS_PER_OM = 3   # OM 당 Algo1 seed 수
MIN_ONSET_GAP = 0
CACHE_NAME = "metric_dft_alpha0p25_ow0p3_dw1p0.pkl"  # aesthetic_rerank 재사용 캐시


# ═══════════════════════════════════════════════════════════════════════════
# 1. 데이터 파이프라인 (train_om_vae_and_export.py 재사용)
# ═══════════════════════════════════════════════════════════════════════════

def load_continuous_om() -> Tuple[np.ndarray, int, int]:
    with open(os.path.join(DATA_DIR, "overlap_matrix_continuous.json"), "r", encoding="utf-8") as f:
        d = json.load(f)
    T, Kk = d["T"], d["K"]
    vals = np.array(d["values"], dtype=np.float32).reshape(T, Kk)
    vals = np.clip(vals, 0.0, 1.0)
    return vals, T, Kk


def sliding_windows(om: np.ndarray, w: int, stride: int) -> np.ndarray:
    T = om.shape[0]
    out = []
    for s in range(0, T - w + 1, stride):
        out.append(om[s:s + w].reshape(-1))  # t-major flatten
    return np.stack(out).astype(np.float32)


def augment(X: np.ndarray, n_noise: int = 3, sigma: float = 0.04,
            rng: np.random.Generator = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng(DATA_SEED)
    outs = [X]
    for _ in range(n_noise):
        noisy = X + rng.normal(0.0, sigma, X.shape).astype(np.float32)
        outs.append(np.clip(noisy, 0.0, 1.0))
    return np.concatenate(outs, axis=0)


# ═══════════════════════════════════════════════════════════════════════════
# 2. DDPM: cosine schedule + denoiser MLP
# ═══════════════════════════════════════════════════════════════════════════

def cosine_beta_schedule(timesteps: int, s: float = 0.008) -> torch.Tensor:
    """Nichol & Dhariwal (2021) cosine schedule."""
    steps = timesteps + 1
    t = torch.linspace(0, timesteps, steps, dtype=torch.float64) / timesteps
    alphas_cumprod = torch.cos((t + s) / (1 + s) * math.pi * 0.5) ** 2
    alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
    betas = 1 - (alphas_cumprod[1:] / alphas_cumprod[:-1])
    return torch.clip(betas, 0.0001, 0.9999).float()


class SinusoidalTimeEmb(nn.Module):
    """128-dim sinusoidal timestep embedding → Linear 128→128 SiLU."""

    def __init__(self, dim: int = 128):
        super().__init__()
        self.dim = dim
        self.proj = nn.Sequential(nn.Linear(dim, dim), nn.SiLU())

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        half = self.dim // 2
        freqs = torch.exp(
            -math.log(10000) * torch.arange(half, device=t.device).float() / (half - 1)
        )
        args = t.float()[:, None] * freqs[None, :]
        emb = torch.cat([torch.sin(args), torch.cos(args)], dim=-1)
        if self.dim % 2 == 1:
            emb = torch.cat([emb, torch.zeros_like(emb[:, :1])], dim=-1)
        return self.proj(emb)


class DenoiserMLP(nn.Module):
    """concat(x_t, temb) → Linear(840+128→512) SiLU → 512→512 SiLU → 512→840 (eps 예측)."""

    def __init__(self, dim: int = DIM, temb_dim: int = TEMB_DIM, hidden: int = HIDDEN):
        super().__init__()
        self.time_emb = SinusoidalTimeEmb(temb_dim)
        self.net = nn.Sequential(
            nn.Linear(dim + temb_dim, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden), nn.SiLU(),
            nn.Linear(hidden, dim),
        )

    def forward(self, x_t: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        temb = self.time_emb(t)
        h = torch.cat([x_t, temb], dim=-1)
        return self.net(h)


class DDPM:
    """cosine schedule 기반 DDPM 학습·샘플링 유틸."""

    def __init__(self, timesteps: int = T_DIFFUSION, device: str = "cpu"):
        self.T = timesteps
        self.device = device
        betas = cosine_beta_schedule(timesteps).to(device)
        alphas = 1.0 - betas
        alphas_cumprod = torch.cumprod(alphas, dim=0)
        alphas_cumprod_prev = torch.cat([torch.ones(1, device=device), alphas_cumprod[:-1]])

        self.betas = betas
        self.alphas = alphas
        self.alphas_cumprod = alphas_cumprod
        self.alphas_cumprod_prev = alphas_cumprod_prev
        self.sqrt_alphas_cumprod = torch.sqrt(alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - alphas_cumprod)
        # posterior variance: beta_t * (1-acp_prev)/(1-acp_t)
        self.posterior_variance = betas * (1.0 - alphas_cumprod_prev) / (1.0 - alphas_cumprod)

    def q_sample(self, x0: torch.Tensor, t: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
        sqrt_acp = self.sqrt_alphas_cumprod[t][:, None]
        sqrt_1m_acp = self.sqrt_one_minus_alphas_cumprod[t][:, None]
        return sqrt_acp * x0 + sqrt_1m_acp * noise

    @torch.no_grad()
    def p_sample_loop(self, model: nn.Module, n: int, dim: int, generator: torch.Generator) -> torch.Tensor:
        x = torch.randn(n, dim, generator=generator, device=self.device)
        for step in reversed(range(self.T)):
            t = torch.full((n,), step, dtype=torch.long, device=self.device)
            eps_pred = model(x, t)
            alpha_t = self.alphas[step]
            alpha_cp_t = self.alphas_cumprod[step]
            beta_t = self.betas[step]

            mean = (1.0 / torch.sqrt(alpha_t)) * (
                x - (beta_t / torch.sqrt(1.0 - alpha_cp_t)) * eps_pred
            )
            if step > 0:
                noise = torch.randn(x.shape, generator=generator, device=self.device)
                sigma = torch.sqrt(self.posterior_variance[step])
                x = mean + sigma * noise
            else:
                x = mean
        return x


def train_ddpm(X: np.ndarray) -> Tuple[DenoiserMLP, DDPM, List[dict], dict]:
    """DDPM 학습. val 10% split, best-checkpoint(val MSE 최저) 사용."""
    torch.manual_seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)

    device = "cpu"
    ddpm = DDPM(T_DIFFUSION, device=device)
    model = DenoiserMLP().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)

    # x0 ∈ [0,1] → [-1,1]
    X_scaled = X * 2.0 - 1.0
    perm = np.random.RandomState(TRAIN_SEED).permutation(X_scaled.shape[0])
    Xp = X_scaled[perm]
    sp = int(X_scaled.shape[0] * 0.9)
    X_tr = torch.from_numpy(Xp[:sp]).to(device)
    X_va = torch.from_numpy(Xp[sp:]).to(device)

    history = []
    best_val = float("inf")
    best_state = None
    best_epoch = -1

    g = torch.Generator(device=device)
    g.manual_seed(TRAIN_SEED)

    for ep in range(EPOCHS):
        model.train()
        idx = torch.randperm(X_tr.shape[0], generator=g)
        tot_loss, nb = 0.0, 0
        for s in range(0, X_tr.shape[0], BATCH):
            b = idx[s:s + BATCH]
            x0 = X_tr[b]
            n = x0.shape[0]
            t = torch.randint(0, T_DIFFUSION, (n,), generator=g, device=device)
            noise = torch.randn(x0.shape, generator=g, device=device)
            x_t = ddpm.q_sample(x0, t, noise)
            eps_pred = model(x_t, t)
            loss = nn.functional.mse_loss(eps_pred, noise)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot_loss += loss.item()
            nb += 1
        sched.step()

        # val MSE: 고정 seed로 매 epoch 동일 (t, noise) 샘플 사용 → 노이즈에 의한 val 변동 최소화
        model.eval()
        with torch.no_grad():
            gv = torch.Generator(device=device)
            gv.manual_seed(12345)  # val 평가는 항상 동일 노이즈
            n_va = X_va.shape[0]
            t_va = torch.randint(0, T_DIFFUSION, (n_va,), generator=gv, device=device)
            noise_va = torch.randn(X_va.shape, generator=gv, device=device)
            x_t_va = ddpm.q_sample(X_va, t_va, noise_va)
            eps_pred_va = model(x_t_va, t_va)
            val_loss = nn.functional.mse_loss(eps_pred_va, noise_va).item()

        train_mse = tot_loss / nb
        history.append({"epoch": ep, "train_mse": train_mse, "val_mse": val_loss})

        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = ep

        if ep % 100 == 0 or ep == EPOCHS - 1:
            print(f"  [Epoch {ep:3d}] train_mse={train_mse:.5f}  val_mse={val_loss:.5f}  "
                  f"best_val={best_val:.5f}@{best_epoch}")

    model.load_state_dict(best_state)
    meta = {"best_epoch": best_epoch, "best_val_mse": best_val,
            "final_train_mse": history[-1]["train_mse"],
            "final_val_mse": history[-1]["val_mse"],
            "n_train": int(X_tr.shape[0]), "n_val": int(X_va.shape[0])}
    return model, ddpm, history, meta


def sample_ddpm(model: DenoiserMLP, ddpm: DDPM, n: int, seed: int) -> np.ndarray:
    model.eval()
    g = torch.Generator(device="cpu")
    g.manual_seed(seed)
    x = ddpm.p_sample_loop(model, n, DIM, g)
    x01 = torch.clamp((x + 1.0) / 2.0, 0.0, 1.0)
    return x01.numpy().astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# 3. VAE baseline 샘플링 (기존 decoder onnx)
# ═══════════════════════════════════════════════════════════════════════════

def sample_vae(n: int, seed: int) -> np.ndarray:
    import onnxruntime as ort
    dec_path = os.path.join(MODELS_DIR, "om_vae_decoder.onnx")
    ds = ort.InferenceSession(dec_path)
    latent_dim = ds.get_inputs()[0].shape[1]
    rng = np.random.default_rng(seed)
    z = rng.normal(0.0, 1.0, (n, latent_dim)).astype(np.float32)
    out = ds.run(["om_recon"], {"z": z})[0]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# 4. 밀도 일치 이진화 (대시보드 방식) + 구조 평가 지표
# ═══════════════════════════════════════════════════════════════════════════

def density_match_binarize(samples: np.ndarray, window: int = WINDOW, k: int = K) -> np.ndarray:
    """
    각 샘플(840-dim, t-major flatten)에 대해:
    기대 활성수 N = round(Σp) 만큼, 확률값이 높은 상위 N개 셀만 ON.
    """
    out = np.zeros_like(samples, dtype=np.float32)
    for i in range(samples.shape[0]):
        p = samples[i]
        n_active = int(round(float(p.sum())))
        n_active = max(0, min(n_active, p.shape[0]))
        if n_active == 0:
            continue
        top_idx = np.argpartition(-p, n_active - 1)[:n_active]
        out[i, top_idx] = 1.0
    return out


def binarize_threshold(samples: np.ndarray, tau: float) -> np.ndarray:
    return (samples >= tau).astype(np.float32)


def per_cycle_activation_profile(bin_samples: np.ndarray, window: int = WINDOW, k: int = K) -> np.ndarray:
    """
    각 샘플을 (window, k)로 reshape 후 cycle(열)별 평균 활성비율.
    그룹 전체 평균 K-dim 프로파일 반환.
    """
    n = bin_samples.shape[0]
    reshaped = bin_samples.reshape(n, window, k)
    per_sample_profile = reshaped.mean(axis=1)  # (n, k) — 샘플별 cycle 활성비율
    return per_sample_profile.mean(axis=0)  # (k,) 그룹 평균


def js_divergence_profiles(p: np.ndarray, q: np.ndarray, eps: float = 1e-10) -> float:
    """두 K-dim 활성비율 프로파일 간 Jensen-Shannon divergence (정규화 분포로 취급)."""
    p = np.asarray(p, dtype=np.float64) + eps
    q = np.asarray(q, dtype=np.float64) + eps
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(a, b):
        return float(np.sum(a * np.log(a / b)))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def temporal_autocorr(bin_samples: np.ndarray, window: int = WINDOW, k: int = K) -> float:
    """
    각 샘플의 인접 스텝(t, t+1) 해밍 유사도(같은 셀 비율) 평균.
    구조 연속성 지표 — 그룹 평균 반환.
    """
    n = bin_samples.shape[0]
    reshaped = bin_samples.reshape(n, window, k)
    sims = []
    for i in range(n):
        seg = reshaped[i]
        for t in range(window - 1):
            same = (seg[t] == seg[t + 1]).mean()
            sims.append(same)
    return float(np.mean(sims))


def diversity_pairwise_hamming(bin_samples: np.ndarray) -> float:
    """그룹 내 평균 pairwise 해밍 거리 (840셀 기준, 서로 다른 셀 수)."""
    n = bin_samples.shape[0]
    if n < 2:
        return 0.0
    dists = []
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.sum(bin_samples[i] != bin_samples[j]))
            dists.append(d)
    return float(np.mean(dists))


def density_stats(bin_samples: np.ndarray) -> Tuple[float, float]:
    counts = bin_samples.sum(axis=1)
    return float(counts.mean()), float(counts.std(ddof=1)) if len(counts) > 1 else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 5. 음악 레벨 평가 (Algo1 pitch JS)
# ═══════════════════════════════════════════════════════════════════════════

def om_to_overlap_matrix(flat_bin: np.ndarray, window: int = WINDOW, k: int = K) -> np.ndarray:
    """840-dim 이진 벡터 → (window, k) overlap_matrix (Algo1 입력 포맷)."""
    return flat_bin.reshape(window, k).astype(np.float32)


def generate_music_js(
    data: dict,
    cycle_labeled: dict,
    overlap_matrix: np.ndarray,
    inst_len_60: List[int],
    orig_flat: List[Tuple[int, int, int]],
    seeds: List[int],
) -> List[float]:
    """overlap_matrix(60×14) 한 개에 대해 seed별 Algo1 생성 → pitch JS 리스트."""
    js_list = []
    for seed in seeds:
        import random as _random
        _random.seed(seed)
        np.random.seed(seed)
        pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        mgr = CycleSetManager(cycle_labeled)
        gen = algorithm1_optimized(
            pool, list(inst_len_60), overlap_matrix, mgr,
            max_resample=50, verbose=False, min_onset_gap=MIN_ONSET_GAP,
        )
        js = pitch_distribution_similarity(gen, orig_flat)["js_divergence"]
        js_list.append(js)
    return js_list


# ═══════════════════════════════════════════════════════════════════════════
# 6. 메인
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    os.chdir(TDA_ROOT)
    os.makedirs(STEP3_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    t_total0 = time.time()
    print("=" * 72)
    print("OM 디퓨전 모델 실험 (DDPM vs VAE baseline)")
    print(f"  window={WINDOW} K={K} dim={DIM} T_diffusion={T_DIFFUSION}")
    print("=" * 72)

    # ── [1] 데이터 로드 ──
    print("\n[1/6] 연속 OM 로드 + 슬라이딩 윈도 + 증강...")
    om, T_om, K_om = load_continuous_om()
    assert K_om == K, f"K mismatch: json K={K_om} vs 상수 K={K}"
    X = sliding_windows(om, WINDOW, STRIDE)
    print(f"  연속 OM: T={T_om}, K={K_om}, 평균 활성도={om.mean():.4f}")
    print(f"  슬라이딩 윈도: {X.shape[0]} 샘플 × {X.shape[1]} 차원")
    X_aug = augment(X)
    print(f"  증강 후: {X_aug.shape[0]} 샘플")

    # ── [2] DDPM 학습 ──
    print("\n[2/6] DDPM 학습 (epochs=800, batch=128, cosine schedule T=200)...")
    t0 = time.time()
    model, ddpm, history, train_meta = train_ddpm(X_aug)
    train_time = time.time() - t0
    print(f"  학습 완료 ({train_time:.1f}s). best_epoch={train_meta['best_epoch']} "
          f"best_val_mse={train_meta['best_val_mse']:.5f}")

    torch.save({"model_state": model.state_dict(), "train_meta": train_meta,
                "config": {"T_diffusion": T_DIFFUSION, "temb_dim": TEMB_DIM,
                           "hidden": HIDDEN, "dim": DIM, "window": WINDOW, "K": K}},
               os.path.join(CACHE_DIR, "om_diffusion.pt"))
    print(f"  가중치 저장: {os.path.join(CACHE_DIR, 'om_diffusion.pt')}")

    # ── [3] 3원 샘플 생성 ──
    print(f"\n[3/6] 3원 샘플 생성 (REAL/VAE/DIFF 각 {N_GROUP}개)...")

    # REAL: 원본 슬라이딩 윈도 중 무작위 64개 (증강 전, seed 고정)
    rng_real = np.random.default_rng(2026)
    real_idx = rng_real.choice(X.shape[0], size=min(N_GROUP, X.shape[0]), replace=False)
    real_samples = X[real_idx]  # 연속값, 이미 이진에 가까움

    vae_samples = sample_vae(N_GROUP, seed=SAMPLE_SEED)

    t0 = time.time()
    diff_samples = sample_ddpm(model, ddpm, N_GROUP, seed=SAMPLE_SEED)
    sample_time = time.time() - t0
    print(f"  DDPM ancestral 샘플링 {N_GROUP}개: {sample_time:.1f}s")

    # ── [4] 밀도 일치 이진화 ──
    print("\n[4/6] 밀도 일치 이진화...")
    real_bin = binarize_threshold(real_samples, REAL_TAU)
    vae_bin = density_match_binarize(vae_samples)
    diff_bin = density_match_binarize(diff_samples)

    groups_bin = {"REAL": real_bin, "VAE": vae_bin, "DIFF": diff_bin}
    groups_raw = {"REAL": real_samples, "VAE": vae_samples, "DIFF": diff_samples}

    # ── [5] 구조 사실성 + 다양성 지표 ──
    print("\n[5/6] 구조 사실성 + 다양성 지표 계산...")
    real_profile = per_cycle_activation_profile(real_bin)

    structural_metrics = {}
    for name, bin_s in groups_bin.items():
        dens_mean, dens_std = density_stats(bin_s)
        profile = per_cycle_activation_profile(bin_s)
        js_vs_real = js_divergence_profiles(profile, real_profile) if name != "REAL" else 0.0
        autocorr = temporal_autocorr(bin_s)
        diversity = diversity_pairwise_hamming(bin_s)
        structural_metrics[name] = {
            "density_mean": dens_mean,
            "density_std": dens_std,
            "per_cycle_profile": [float(v) for v in profile],
            "js_vs_real_profile": js_vs_real,
            "temporal_autocorr": autocorr,
            "diversity_pairwise_hamming": diversity,
        }
        print(f"  [{name}] density={dens_mean:.2f}±{dens_std:.2f}  "
              f"JS_vs_real={js_vs_real:.5f}  autocorr={autocorr:.4f}  "
              f"diversity={diversity:.2f}")

    # ── [6] 음악 레벨 평가 ──
    print(f"\n[6/6] 음악 레벨 평가 (그룹당 OM {MUSIC_OM_PER_GROUP}개 × seed {MUSIC_SEEDS_PER_OM}개 = "
          f"{MUSIC_OM_PER_GROUP * MUSIC_SEEDS_PER_OM}곡)...")

    print("  hibari 데이터 + PH bundle 로드...")
    t0 = time.time()
    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    print(f"  완료 ({time.time()-t0:.1f}s)")

    import pickle
    cache_path = os.path.join(CACHE_DIR, CACHE_NAME)
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"PH bundle 캐시 없음: {cache_path}. "
            "run_aesthetic_rerank.py 를 먼저 1회 실행해 캐시를 생성해야 합니다."
        )
    with open(cache_path, "rb") as f:
        bundle = pickle.load(f)
    cycle_labeled = bundle["cycle_labeled"]
    K_bundle = len(cycle_labeled)
    print(f"  PH bundle 로드: K={K_bundle} cycles (cache={CACHE_NAME})")
    assert K_bundle == K, f"cycle 수 불일치: bundle K={K_bundle} vs OM K={K}"

    # hibari 패턴 앞 60 스텝 (MODULES 기반 INST_CHORD_HEIGHTS 앞부분)
    MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights_full = MODULES * 33
    inst_len_60 = inst_chord_heights_full[:WINDOW]

    music_seeds = [101, 202, 303]
    assert len(music_seeds) == MUSIC_SEEDS_PER_OM

    music_results = {}
    t_music0 = time.time()
    for name, bin_s in groups_bin.items():
        rng_pick = np.random.default_rng(hash(name) % (2**31))
        pick_idx = rng_pick.choice(bin_s.shape[0], size=MUSIC_OM_PER_GROUP, replace=False)
        js_all = []
        for oi in pick_idx:
            ov = om_to_overlap_matrix(bin_s[oi])
            js_list = generate_music_js(data, cycle_labeled, ov, inst_len_60, orig_flat, music_seeds)
            js_all.extend(js_list)
        music_results[name] = {
            "pitch_js_mean": float(np.mean(js_all)),
            "pitch_js_std": float(np.std(js_all, ddof=1)),
            "n_songs": len(js_all),
            "om_indices": [int(i) for i in pick_idx],
        }
        print(f"  [{name}] pitch_js={music_results[name]['pitch_js_mean']:.5f}"
              f"±{music_results[name]['pitch_js_std']:.5f}  (n={len(js_all)})")
    music_time = time.time() - t_music0
    print(f"  음악 레벨 평가 완료: {music_time:.1f}s")

    # ── 종합 판정 ──
    print("\n" + "=" * 72)
    print("종합 판정")
    print("=" * 72)

    js_vae = structural_metrics["VAE"]["js_vs_real_profile"]
    js_diff = structural_metrics["DIFF"]["js_vs_real_profile"]
    div_vae = structural_metrics["VAE"]["diversity_pairwise_hamming"]
    div_diff = structural_metrics["DIFF"]["diversity_pairwise_hamming"]
    music_vae = music_results["VAE"]["pitch_js_mean"]
    music_diff = music_results["DIFF"]["pitch_js_mean"]

    cond_i = js_diff < js_vae              # per-cycle JS 낮음 (구조 충실)
    cond_ii = div_diff > div_vae            # 다양성 높음
    music_ratio = (music_diff - music_vae) / music_vae if music_vae > 0 else float("inf")
    cond_iii = abs(music_ratio) <= 0.10     # 음악 JS 동급 (±10%)

    n_pass = sum([cond_i, cond_ii, cond_iii])
    if n_pass == 3:
        verdict = "디퓨전 우위"
    elif n_pass == 0:
        verdict = "디퓨전 열세"
    else:
        verdict = "trade-off"

    print(f"  (i)   per-cycle JS:  VAE={js_vae:.5f}  DIFF={js_diff:.5f}  → "
          f"{'DIFF 우위' if cond_i else 'VAE 우위/동급'}")
    print(f"  (ii)  다양성:        VAE={div_vae:.2f}  DIFF={div_diff:.2f}  → "
          f"{'DIFF 우위' if cond_ii else 'VAE 우위/동급'}")
    print(f"  (iii) 음악 JS 동급:  VAE={music_vae:.5f}  DIFF={music_diff:.5f}  "
          f"비율차={music_ratio*100:+.1f}%  → {'동급(±10%)' if cond_iii else '동급 아님'}")
    print(f"\n  판정: {verdict} ({n_pass}/3 조건 충족)")

    total_time = time.time() - t_total0
    print(f"\n총 실행 시간: {total_time:.1f}s ({total_time/60:.1f}분)")

    # ── JSON 저장 ──
    out = {
        "config": {
            "window": WINDOW,
            "stride": STRIDE,
            "K": K,
            "dim": DIM,
            "T_diffusion": T_DIFFUSION,
            "temb_dim": TEMB_DIM,
            "hidden": HIDDEN,
            "batch": BATCH,
            "epochs": EPOCHS,
            "lr": LR,
            "train_seed": TRAIN_SEED,
            "sample_seed": SAMPLE_SEED,
            "n_sample_group": N_GROUP,
            "real_binarize_tau": REAL_TAU,
            "music_om_per_group": MUSIC_OM_PER_GROUP,
            "music_seeds_per_om": MUSIC_SEEDS_PER_OM,
            "music_seeds": music_seeds,
            "n_train_windows_before_aug": int(X.shape[0]),
            "n_train_samples_after_aug": int(X_aug.shape[0]),
        },
        "training": {
            "history_curve": [
                h for i, h in enumerate(history)
                if i in (0, len(history) // 4, len(history) // 2, 3 * len(history) // 4, len(history) - 1)
            ],
            "meta": train_meta,
            "train_time_s": train_time,
            "sample_time_s": sample_time,
        },
        "structural_metrics": structural_metrics,
        "music_level": music_results,
        "verdict": {
            "cond_i_lower_js": bool(cond_i),
            "cond_ii_higher_diversity": bool(cond_ii),
            "cond_iii_music_js_parity": bool(cond_iii),
            "music_js_ratio_diff_vs_vae": float(music_ratio),
            "n_conditions_passed": n_pass,
            "verdict": verdict,
        },
        "timing": {
            "train_time_s": train_time,
            "sample_time_s": sample_time,
            "music_eval_time_s": music_time,
            "total_time_s": total_time,
        },
    }

    out_path = os.path.join(STEP3_DIR, "om_diffusion_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n저장됨: {out_path}")


if __name__ == "__main__":
    main()
