"""
run_topo_diffusion.py — 위상 손실 결합 1D-conv 디노이저 (TopoDiffusionNet 방식 접목)

배경
────
`run_om_diffusion.py`(커밋 54e7878)의 MLP-DDPM은 negative 였다:
  · 밀도 3배 과밀 (REAL 139 → DIFF 418)
  · 시간축 autocorr 붕괴 (0.814 → 0.504)
진단된 원인 = **MLP가 840차원(60×14)을 평면화해 시간축 구조를 학습하지 못함**.

본 실험은 `docs/research_next_algorithms_2026.md` §1 (최우선 후보,
TopoDiffusionNet / ICLR 2025)을 그 진단에 정면으로 대응시킨다.

  (A) 아키텍처 — OM을 (K=14 채널) × (T=60 시간) 신호로 보고 **시간축 1D conv U-Net**
      으로 디노이즈. 평면화 제거 → 시간 국소성이 구조적으로 보존된다.

  (B) 위상 손실 — 각 디노이징 스텝에서 예측된 x̂₀ 의 persistent homology 를 계산해
      원본 x₀ 의 위상과 맞추는 L_topo 를 L_simple 과 함께 역전파.

위상 손실의 폐형식 (본 실험의 핵심 적응)
───────────────────────────────────────
원 논문은 256×256 이미지에 cubical persistence 를 매 스텝 계산해 무겁다.
그러나 우리 문제에서 음악적으로 의미 있는 위상은 **cycle(열)별 시간축 H₀**
— "이 cycle 이 몇 번, 얼마나 길게 켜지는가" — 이고, **1차원 신호의 0차원
superlevel-set persistence 는 폐형식을 갖는다**:

      Σ_i persistence(H₀ feature_i)  =  총 상승변동(total upward variation)
                                     =  Σ_t ReLU( x[t] − x[t−1] )

즉 외부 PH 라이브러리(gudhi/cripser) 없이, O(T) 로, **정확히 미분 가능하게**
persistence 총합을 얻는다. ε-게이트를 걸면 "persistence > ε 인 유의 feature 의
개수"에 해당하는 양이 되어, 원 논문의 Betti 수 제약과 같은 역할을 한다.
→ 연구문서 §1 ④ 에 적힌 "스텝당 PH 계산 비용" 리스크가 구조적으로 제거된다.

변이 (ablation) — 개선을 위상 손실에 정직하게 귀속시키기 위함
───────────────────────────────────────────────────────────
  · `mlp`        : 기존 negative 기록 (재실행 안 함, JSON 수치 인용)
  · `conv`       : 1D-conv U-Net, L_simple 만        ← 아키텍처 효과만
  · `conv_topo`  : + L_topo                          ← 위상 손실 효과
  · `full`       : + L_dens (cycle별 밀도 정합)      ← 밀도 폭주 직접 억제

MultiDiffusion 장형 샘플링
─────────────────────────
T=60(30초)은 감상하기에 짧다. 창 하나로 학습한 모델에서 긴 OM 을 얻기 위해
MultiDiffusion(ICML 2023) 방식으로 **겹치는 창들의 ε 예측을 매 스텝 가중평균**
하여 T=240(약 2분) OM 을 합성한다. 별도 학습 없이 길이만 확장된다.

실행
────
  python experiments/run_topo_diffusion.py                 # 전체 (변이 3종 + 평가)
  python experiments/run_topo_diffusion.py --variant full  # 한 변이만
  python experiments/run_topo_diffusion.py --skip-music    # 구조 지표까지만
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import math
import os
import pickle
import random
import time
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from generation import CycleSetManager, NodePool, algorithm1_optimized

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # experiments/
TDA_ROOT = os.path.dirname(BASE_DIR)                            # tda_pipeline/
# `suite.MIDI_FILE` 몽키패치 제거 (2026-08-15, T14).
# BASE_DIR 근본 수정(739c389) 으로 suite 가 이미 루트를 가리킨다.

DASH_DIR = os.path.join(TDA_ROOT, "hibari_dashboard")
DATA_DIR = os.path.join(DASH_DIR, "data")
STEP3_DIR = os.path.join(TDA_ROOT, "docs", "step3_data")
CACHE_DIR = os.path.join(TDA_ROOT, "cache")
OUT_DIR = os.path.join(TDA_ROOT, "output", "topo_diffusion")

# ── 데이터 상수 (run_om_diffusion.py 와 동일해야 비교 가능) ──
WINDOW = 60
STRIDE = 2
K = 14
DATA_SEED = 42

# ── 확산 하이퍼파라미터 ──
T_DIFFUSION = 200
TEMB_DIM = 128
CH = 48                     # 학습 데이터가 창 515개뿐 — 과대 모델은 시간만 먹는다
BATCH = 128
EPOCHS = 300
LR = 2e-3
TRAIN_SEED = 42
SAMPLE_SEED = 7
N_GROUP = 64

# ── 위상/밀도 손실 ──
LAMBDA_TOPO = 0.30
LAMBDA_DENS = 0.30
PERSIST_EPS = 0.10          # persistence 게이트 — 이보다 작은 요동은 위상 feature 로 안 침

# ── 평가 프로토콜 (기존 실험과 동일) ──
REAL_TAU = 0.5
MUSIC_OM_PER_GROUP = 8
MUSIC_SEEDS_PER_OM = 3
MIN_ONSET_GAP = 0
CACHE_NAME = "metric_dft_alpha0p25_ow0p3_dw1p0.pkl"

# ── 장형 생성 ──
LONG_T = 240                # 약 2분
LONG_STRIDE = 15

# 순서 주의: 한 프로세스 안에서 순차 학습한다(병렬 실행은 스레드 과다구독으로
# 오히려 2.6배 느렸다 — 4코어에 3프로세스×2스레드). 헤드라인인 full 을 먼저 둬서
# 체크포인트가 가장 먼저 나오게 한다.
VARIANTS = ["full", "conv_topo", "conv"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. 데이터
# ═══════════════════════════════════════════════════════════════════════════

def load_continuous_om() -> np.ndarray:
    """대시보드가 export 한 연속 OM (DFT α=0.25, w_o=0.3, w_d=1.0).

    ⚠ **이 파일은 `use_decayed=True` 산출물이다** (감쇄 lag 1~4).
      논문 헤드라인 JS=0.00902 를 만든 `run_percycle_tau_dft_alpha_grid.py:155` 는
      `use_decayed=False` 를 쓴다 — 즉 **여기서 돌아오는 OM 은 헤드라인과 다른 설정**이다.
      저장소에서 `use_decayed=True` 를 넘기는 곳은 `export_hibari_data.py` 하나뿐인데,
      그 산출물을 이 함수를 통해 실험 스크립트 10여 개가 공유하고 있다.

      두 설정은 연속값의 약 52% 가 다르지만(maxdiff 0.449, cycle 4 구성원도 다르다:
      False `[1,2,6,9]` vs True `[1,5,6,8]`), **생성 결과는 구별되지 않는다** —
      τ=0.5 이진화 후 zero-row 가 196/1088 로 같고 Algorithm 1 음고 JS 는
      0.03828 vs 0.03889 (paired p=0.315, N=20). 그래서 지금까지 아무도 눈치채지 못했다.

      → 자산을 재생성하지 않는다. 다만 **"이 OM = 헤드라인 설정" 이라고 가정하지 말 것.**
        헤드라인을 재현하려면 `suite.build_overlap_bundle(..., use_decayed=False)` 를 직접 부를 것.
    """
    with open(os.path.join(DATA_DIR, "overlap_matrix_continuous.json"), "r", encoding="utf-8") as f:
        d = json.load(f)
    T, Kk = d["T"], d["K"]
    assert Kk == K, f"K mismatch: {Kk} vs {K}"
    return np.clip(np.array(d["values"], dtype=np.float32).reshape(T, Kk), 0.0, 1.0)


def sliding_windows_ct(om: np.ndarray, w: int, stride: int) -> np.ndarray:
    """(T,K) → (N, K, w) — 채널=cycle, 길이=시간. conv 입력 레이아웃."""
    out = [om[s:s + w].T for s in range(0, om.shape[0] - w + 1, stride)]
    return np.stack(out).astype(np.float32)


def augment(X: np.ndarray, n_noise: int = 3, sigma: float = 0.04) -> np.ndarray:
    rng = np.random.default_rng(DATA_SEED)
    outs = [X]
    for _ in range(n_noise):
        outs.append(np.clip(X + rng.normal(0.0, sigma, X.shape).astype(np.float32), 0.0, 1.0))
    return np.concatenate(outs, axis=0)


# ═══════════════════════════════════════════════════════════════════════════
# 2. 위상 손실 — 1D cubical H₀ persistence 폐형식
# ═══════════════════════════════════════════════════════════════════════════

def h0_total_persistence(x01: torch.Tensor, eps: float = PERSIST_EPS) -> torch.Tensor:
    """
    x01: (B, K, T) ∈ [0,1]. cycle(채널)별 시간축 0차원 persistence 총합.

    1차원 신호의 superlevel-set H₀ 는 "임계값을 내리며 나타나는 구간"들로,
    그 persistence 총합은 총 상승변동과 정확히 같다:
        Σ_i pers_i = Σ_t ReLU(x[t] − x[t−1])   (x[−1] := 0)
    이진 신호에서는 이 값이 곧 **활성 구간의 개수**가 된다.
    eps 게이트는 persistence ≤ eps 인 미세 요동을 feature 로 세지 않게 한다.
    """
    prev = F.pad(x01, (1, 0))[..., :-1]
    rise = F.relu(x01 - prev)
    gated = F.relu(rise - eps) / max(1e-6, 1.0 - eps)
    return gated.sum(dim=-1)                     # (B, K)


def per_cycle_density(x01: torch.Tensor) -> torch.Tensor:
    """cycle별 평균 활성도 (B, K)."""
    return x01.mean(dim=-1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. 1D-conv U-Net 디노이저
# ═══════════════════════════════════════════════════════════════════════════

class SinusoidalTimeEmb(nn.Module):
    def __init__(self, dim: int = TEMB_DIM):
        super().__init__()
        self.dim = dim
        self.proj = nn.Sequential(nn.Linear(dim, dim), nn.SiLU(), nn.Linear(dim, dim))

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        half = self.dim // 2
        freqs = torch.exp(-math.log(10000) * torch.arange(half, device=t.device).float() / (half - 1))
        args = t.float()[:, None] * freqs[None, :]
        return self.proj(torch.cat([torch.sin(args), torch.cos(args)], dim=-1))


class ResBlock1D(nn.Module):
    """Conv1d ×2 + FiLM 시간조건. 시간축 국소성 보존이 이 실험의 핵심."""

    def __init__(self, c_in: int, c_out: int, temb_dim: int = TEMB_DIM, ksize: int = 5):
        super().__init__()
        pad = ksize // 2
        self.norm1 = nn.GroupNorm(8, c_in)
        self.conv1 = nn.Conv1d(c_in, c_out, ksize, padding=pad)
        self.film = nn.Linear(temb_dim, c_out * 2)
        self.norm2 = nn.GroupNorm(8, c_out)
        self.conv2 = nn.Conv1d(c_out, c_out, ksize, padding=pad)
        self.skip = nn.Conv1d(c_in, c_out, 1) if c_in != c_out else nn.Identity()

    def forward(self, x: torch.Tensor, temb: torch.Tensor) -> torch.Tensor:
        h = self.conv1(F.silu(self.norm1(x)))
        scale, shift = self.film(temb)[:, :, None].chunk(2, dim=1)
        h = h * (1 + scale) + shift
        h = self.conv2(F.silu(self.norm2(h)))
        return h + self.skip(x)


class TopoConvUNet(nn.Module):
    """
    (B, K=14, T) → (B, K=14, T) eps 예측.
    T 는 가변 (60 학습 / MultiDiffusion 시에도 창 단위 60 유지).
    """

    def __init__(self, k: int = K, ch: int = CH, temb_dim: int = TEMB_DIM):
        super().__init__()
        self.time_emb = SinusoidalTimeEmb(temb_dim)
        self.inp = nn.Conv1d(k, ch, 5, padding=2)

        self.d1 = ResBlock1D(ch, ch, temb_dim)
        self.down1 = nn.Conv1d(ch, ch * 2, 4, stride=2, padding=1)      # T → T/2
        self.d2 = ResBlock1D(ch * 2, ch * 2, temb_dim)
        self.down2 = nn.Conv1d(ch * 2, ch * 2, 4, stride=2, padding=1)  # T/2 → T/4

        self.mid1 = ResBlock1D(ch * 2, ch * 2, temb_dim)
        self.mid2 = ResBlock1D(ch * 2, ch * 2, temb_dim)

        self.up2 = nn.ConvTranspose1d(ch * 2, ch * 2, 4, stride=2, padding=1)
        self.u2 = ResBlock1D(ch * 4, ch * 2, temb_dim)
        self.up1 = nn.ConvTranspose1d(ch * 2, ch, 4, stride=2, padding=1)
        self.u1 = ResBlock1D(ch * 2, ch, temb_dim)

        self.out_norm = nn.GroupNorm(8, ch)
        self.out = nn.Conv1d(ch, k, 5, padding=2)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        temb = self.time_emb(t)
        h0 = self.inp(x)
        h1 = self.d1(h0, temb)
        h2 = self.d2(self.down1(h1), temb)
        m = self.mid2(self.mid1(self.down2(h2), temb), temb)
        u = self.u2(torch.cat([self.up2(m), h2], dim=1), temb)
        u = self.u1(torch.cat([self.up1(u), h1], dim=1), temb)
        return self.out(F.silu(self.out_norm(u)))


# ═══════════════════════════════════════════════════════════════════════════
# 4. DDPM
# ═══════════════════════════════════════════════════════════════════════════

def cosine_beta_schedule(timesteps: int, s: float = 0.008) -> torch.Tensor:
    steps = timesteps + 1
    t = torch.linspace(0, timesteps, steps, dtype=torch.float64) / timesteps
    ac = torch.cos((t + s) / (1 + s) * math.pi * 0.5) ** 2
    ac = ac / ac[0]
    return torch.clip(1 - (ac[1:] / ac[:-1]), 0.0001, 0.9999).float()


class DDPM:
    def __init__(self, timesteps: int = T_DIFFUSION):
        self.T = timesteps
        betas = cosine_beta_schedule(timesteps)
        alphas = 1.0 - betas
        ac = torch.cumprod(alphas, dim=0)
        self.betas, self.alphas, self.alphas_cumprod = betas, alphas, ac
        self.alphas_cumprod_prev = torch.cat([torch.ones(1), ac[:-1]])
        self.sqrt_ac = torch.sqrt(ac)
        self.sqrt_1mac = torch.sqrt(1.0 - ac)
        self.post_var = betas * (1.0 - self.alphas_cumprod_prev) / (1.0 - ac)
        # x̂₀ 를 [-1,1] 로 자른 뒤 쓰는 사후평균 계수 (Ho et al. 2020, eq.7).
        # 자르지 않으면 200 스텝 동안 오차가 누적돼 샘플이 0/1 로 포화된다 —
        # 실제로 그렇게 됐다 (평균 0.42 / std 0.49, 데이터는 평균 0.264).
        self.post_c0 = betas * torch.sqrt(self.alphas_cumprod_prev) / (1.0 - ac)
        self.post_ct = (1.0 - self.alphas_cumprod_prev) * torch.sqrt(alphas) / (1.0 - ac)

    def q_sample(self, x0, t, noise):
        a = self.sqrt_ac[t][:, None, None]
        b = self.sqrt_1mac[t][:, None, None]
        return a * x0 + b * noise

    def pred_x0(self, x_t, t, eps):
        a = self.sqrt_ac[t][:, None, None]
        b = self.sqrt_1mac[t][:, None, None]
        return torch.clamp((x_t - b * eps) / a, -1.0, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# 5. 학습
# ═══════════════════════════════════════════════════════════════════════════

def train(variant: str, X_aug: np.ndarray, epochs: int = EPOCHS, verbose: bool = True):
    use_topo = variant in ("conv_topo", "full")
    use_dens = variant == "full"

    torch.manual_seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)

    n = X_aug.shape[0]
    perm = np.random.default_rng(TRAIN_SEED).permutation(n)
    n_val = max(1, int(0.1 * n))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]
    Xtr = torch.from_numpy(X_aug[tr_idx] * 2.0 - 1.0)     # [-1,1]
    Xva = torch.from_numpy(X_aug[val_idx] * 2.0 - 1.0)

    model = TopoConvUNet()
    ddpm = DDPM()
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    n_params = sum(p.numel() for p in model.parameters())
    if verbose:
        print(f"    파라미터 {n_params:,} | topo={use_topo} dens={use_dens} "
              f"| train {len(tr_idx)} / val {len(val_idx)}")

    best_val, best_state, best_ep = float("inf"), None, -1
    history = []
    g = torch.Generator().manual_seed(TRAIN_SEED)

    for ep in range(epochs):
        model.train()
        idx = torch.randperm(Xtr.shape[0], generator=g)
        ep_simple = ep_topo = ep_dens = 0.0
        nb = 0
        for i in range(0, Xtr.shape[0], BATCH):
            x0 = Xtr[idx[i:i + BATCH]]
            b = x0.shape[0]
            t = torch.randint(0, ddpm.T, (b,), generator=g)
            noise = torch.randn(x0.shape, generator=g)
            x_t = ddpm.q_sample(x0, t, noise)
            eps_pred = model(x_t, t)

            loss_simple = F.mse_loss(eps_pred, noise)
            loss = loss_simple
            l_topo = l_dens = torch.zeros(())

            if use_topo or use_dens:
                x0_hat = ddpm.pred_x0(x_t, t, eps_pred)
                x0_hat01 = (x0_hat + 1.0) / 2.0
                x0_01 = (x0 + 1.0) / 2.0
                # 저노이즈 구간일수록 x̂₀ 가 의미 있으므로 ᾱ_t 로 가중
                w = ddpm.alphas_cumprod[t][:, None]
                if use_topo:
                    l_topo = (w * (h0_total_persistence(x0_hat01)
                                   - h0_total_persistence(x0_01)) ** 2).mean()
                    loss = loss + LAMBDA_TOPO * l_topo
                if use_dens:
                    l_dens = (w * (per_cycle_density(x0_hat01)
                                   - per_cycle_density(x0_01)) ** 2).mean() * 100.0
                    loss = loss + LAMBDA_DENS * l_dens

            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

            ep_simple += float(loss_simple.detach())
            ep_topo += float(l_topo.detach()) if l_topo.requires_grad else float(l_topo)
            ep_dens += float(l_dens.detach()) if l_dens.requires_grad else float(l_dens)
            nb += 1
        sched.step()

        if (ep + 1) % 10 == 0 or ep == epochs - 1:
            model.eval()
            with torch.no_grad():
                gv = torch.Generator().manual_seed(1234)
                tv = torch.randint(0, ddpm.T, (Xva.shape[0],), generator=gv)
                nv = torch.randn(Xva.shape, generator=gv)
                val = float(F.mse_loss(model(ddpm.q_sample(Xva, tv, nv), tv), nv))
            history.append({"epoch": ep + 1, "simple": ep_simple / nb,
                            "topo": ep_topo / nb, "dens": ep_dens / nb, "val": val})
            if val < best_val:
                best_val, best_ep = val, ep + 1
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            if verbose and (ep + 1) % 100 == 0:
                print(f"    ep {ep+1:4d} | simple {ep_simple/nb:.4f} "
                      f"| topo {ep_topo/nb:.4f} | dens {ep_dens/nb:.4f} | val {val:.4f}")

    if best_state is not None:
        model.load_state_dict(best_state)
    meta = {"variant": variant, "n_params": n_params, "best_epoch": best_ep,
            "best_val_mse": best_val, "epochs": epochs,
            "lambda_topo": LAMBDA_TOPO if use_topo else 0.0,
            "lambda_dens": LAMBDA_DENS if use_dens else 0.0,
            "persist_eps": PERSIST_EPS}
    return model, ddpm, history, meta


# ═══════════════════════════════════════════════════════════════════════════
# 6. 샘플링 — 표준 + MultiDiffusion 장형
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def sample(model: TopoConvUNet, ddpm: DDPM, n: int, seed: int, length: int = WINDOW) -> np.ndarray:
    """표준 ancestral 샘플링. 반환 (n, length, K) ∈ [0,1]."""
    model.eval()
    g = torch.Generator().manual_seed(seed)
    x = torch.randn((n, K, length), generator=g)
    for i in reversed(range(ddpm.T)):
        t = torch.full((n,), i, dtype=torch.long)
        x0 = ddpm.pred_x0(x, t, model(x, t))            # [-1,1] 클리핑 포함
        mean = ddpm.post_c0[i] * x0 + ddpm.post_ct[i] * x
        if i > 0:
            x = mean + torch.sqrt(ddpm.post_var[i]) * torch.randn(x.shape, generator=g)
        else:
            x = mean
    x01 = torch.clamp((x + 1.0) / 2.0, 0, 1).permute(0, 2, 1)
    return np.ascontiguousarray(x01.numpy(), dtype=np.float32)


@torch.no_grad()
def sample_multidiffusion(model: TopoConvUNet, ddpm: DDPM, total_T: int, seed: int,
                          win: int = WINDOW, stride: int = LONG_STRIDE) -> np.ndarray:
    """
    MultiDiffusion (ICML 2023): 창 하나로 학습한 모델에서 긴 시퀀스를 얻는다.
    매 디노이징 스텝마다 겹치는 창들의 ε 예측을 위치별 가중평균해 하나의 ε 로 융합.
    학습 없이 길이만 확장 — 30초 모델로 2분 곡을 만든다.
    """
    model.eval()
    g = torch.Generator().manual_seed(seed)
    x = torch.randn((1, K, total_T), generator=g)

    starts = list(range(0, total_T - win + 1, stride))
    if starts[-1] != total_T - win:
        starts.append(total_T - win)
    # 창 경계 이음매를 없애기 위한 hann 가중
    wwin = torch.hann_window(win, periodic=False).clamp_min(1e-3)[None, None, :]

    for i in reversed(range(ddpm.T)):
        # 창들을 한 배치로 묶어 한 번에 통과 (CPU에서 순차 호출보다 훨씬 빠름)
        crops = torch.cat([x[:, :, s:s + win] for s in starts], dim=0)
        t = torch.full((len(starts),), i, dtype=torch.long)
        eps_w = model(crops, t) * wwin
        eps_acc = torch.zeros_like(x)
        w_acc = torch.zeros_like(x)
        for j, s in enumerate(starts):
            eps_acc[0, :, s:s + win] += eps_w[j]
            w_acc[0, :, s:s + win] += wwin[0]
        eps = eps_acc / w_acc
        x0 = ddpm.pred_x0(x, torch.tensor([i]), eps)     # [-1,1] 클리핑 포함
        mean = ddpm.post_c0[i] * x0 + ddpm.post_ct[i] * x
        if i > 0:
            x = mean + torch.sqrt(ddpm.post_var[i]) * torch.randn(x.shape, generator=g)
        else:
            x = mean
    out = torch.clamp((x + 1.0) / 2.0, 0, 1)[0].T
    return np.ascontiguousarray(out.numpy(), dtype=np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# 7. 이진화 + 구조 지표 (run_om_diffusion.py 프로토콜 그대로)
# ═══════════════════════════════════════════════════════════════════════════

def density_match_binarize(samples: np.ndarray) -> np.ndarray:
    """
    (n,T,K) 각 샘플에서 Σp 개의 상위 셀만 ON.

    주의 — `np.zeros_like` 는 입력의 메모리 순서를 물려받는다(order='K').
    sample() 이 torch 의 permute 결과를 numpy 로 넘기면 C-연속이 아니므로
    `out[i].reshape(-1)` 이 **뷰가 아니라 복사본**이 되어 쓰기가 조용히 버려진다.
    (실제로 이 버그로 모든 변이의 density 가 0.0 으로 보고됐다.)
    그래서 C-연속 배열을 명시적으로 만들고 평평한 인덱스로 직접 쓴다.
    """
    s = np.ascontiguousarray(samples, dtype=np.float32)
    n = s.shape[0]
    flat_in = s.reshape(n, -1)
    out = np.zeros((n, flat_in.shape[1]), dtype=np.float32)
    for i in range(n):
        p = flat_in[i]
        na = int(round(float(p.sum())))
        na = max(0, min(na, p.size))
        if na == 0:
            continue
        out[i, np.argpartition(-p, na - 1)[:na]] = 1.0
    return out.reshape(s.shape)


def per_cycle_activation_profile(bs: np.ndarray) -> np.ndarray:
    return bs.mean(axis=1).mean(axis=0)                # (K,)


def js_divergence_profiles(p, q, eps=1e-10) -> float:
    p = np.asarray(p, np.float64) + eps; p /= p.sum()
    q = np.asarray(q, np.float64) + eps; q /= q.sum()
    m = 0.5 * (p + q)
    kl = lambda a, b: float(np.sum(a * np.log(a / b)))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def temporal_autocorr(bs: np.ndarray) -> float:
    return float(np.mean([(bs[i, t] == bs[i, t + 1]).mean()
                          for i in range(bs.shape[0]) for t in range(bs.shape[1] - 1)]))


def diversity_pairwise_hamming(bs: np.ndarray) -> float:
    n = bs.shape[0]
    if n < 2:
        return 0.0
    f = bs.reshape(n, -1)
    return float(np.mean([np.sum(f[i] != f[j]) for i in range(n) for j in range(i + 1, n)]))


def h0_runs_np(bs: np.ndarray) -> Tuple[float, float]:
    """이진 (n,T,K) → cycle당 평균 활성구간 수, 평균 구간 길이."""
    runs, lens = [], []
    for i in range(bs.shape[0]):
        for c in range(bs.shape[2]):
            col = bs[i, :, c]
            r = int(np.sum(np.diff(np.concatenate([[0], col])) > 0))
            runs.append(r)
            if r > 0:
                lens.append(float(col.sum()) / r)
    return float(np.mean(runs)), (float(np.mean(lens)) if lens else 0.0)


def structural_report(name: str, bs: np.ndarray, real_profile: np.ndarray) -> dict:
    counts = bs.reshape(bs.shape[0], -1).sum(axis=1)
    prof = per_cycle_activation_profile(bs)
    runs, runlen = h0_runs_np(bs)
    return {
        "density_mean": float(counts.mean()),
        "density_std": float(counts.std(ddof=1)) if len(counts) > 1 else 0.0,
        "per_cycle_profile": [float(v) for v in prof],
        "js_vs_real_profile": 0.0 if name == "REAL" else js_divergence_profiles(prof, real_profile),
        "temporal_autocorr": temporal_autocorr(bs),
        "diversity_pairwise_hamming": diversity_pairwise_hamming(bs),
        "h0_runs_per_cycle": runs,
        "mean_run_length": runlen,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 8. 음악 레벨
# ═══════════════════════════════════════════════════════════════════════════

MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
           4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]

CONSONANT_ICS = {0, 3, 4, 5}


def consonance_score(notes: List[Tuple[int, int, int]]) -> float:
    """협화도 — 미적 지표 3종 중 유일하게 calibration 을 통과한 성분
    (`project_aesthetic_rerank_negative_0613`). 그래서 이것만 랭킹에 쓴다."""
    from collections import defaultdict
    t2p = defaultdict(list)
    for start, pitch, end in notes:
        for t in range(start, end):
            t2p[t].append(pitch)
    ratios = []
    for ps in t2p.values():
        if len(ps) < 2:
            continue
        tot = con = 0
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                ic = abs(ps[i] - ps[j]) % 12
                ic = min(ic, 12 - ic)
                tot += 1
                con += (ic in CONSONANT_ICS)
        ratios.append(con / tot)
    return float(np.mean(ratios)) if ratios else 1.0


def generate_from_om(data, cycle_labeled, om_bin: np.ndarray, seed: int):
    """이진 OM (T,K) → Algorithm 1 → note 리스트."""
    T = om_bin.shape[0]
    inst_len = (MODULES * (T // len(MODULES) + 2))[:T]
    random.seed(seed)
    np.random.seed(seed)
    pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
    mgr = CycleSetManager(cycle_labeled)
    return algorithm1_optimized(pool, list(inst_len), om_bin.astype(np.float32), mgr,
                                max_resample=50, verbose=False, min_onset_gap=MIN_ONSET_GAP)


# ═══════════════════════════════════════════════════════════════════════════
# 9. 메인
# ═══════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None, choices=VARIANTS)
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--skip-music", action="store_true")
    ap.add_argument("--threads", type=int, default=0, help="0=torch 기본. 변이 병렬 실행 시 2~3 권장")
    ap.add_argument("--tag", default="", help="결과 JSON 접미사 (병렬 실행 충돌 방지)")
    args = ap.parse_args()

    if args.threads > 0:
        torch.set_num_threads(args.threads)

    os.chdir(TDA_ROOT)
    os.makedirs(STEP3_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    variants = [args.variant] if args.variant else VARIANTS
    t_total = time.time()

    print("=" * 76)
    print("위상 손실 결합 1D-conv 디노이저 (TopoDiffusionNet 방식)")
    print(f"  window={WINDOW} K={K} T_diff={T_DIFFUSION} variants={variants}")
    print("=" * 76)

    # ── 데이터 ──
    om = load_continuous_om()
    X = sliding_windows_ct(om, WINDOW, STRIDE)
    X_aug = augment(X)
    print(f"\n[데이터] OM T={om.shape[0]} K={om.shape[1]} 평균활성={om.mean():.4f}")
    print(f"         슬라이딩 창 {X.shape[0]} → 증강 후 {X_aug.shape[0]} (각 {K}×{WINDOW})")

    # REAL 기준군
    rng_real = np.random.default_rng(2026)
    real_idx = rng_real.choice(X.shape[0], size=min(N_GROUP, X.shape[0]), replace=False)
    real_samples = X[real_idx].transpose(0, 2, 1)                 # (n,T,K)
    real_bin = (real_samples >= REAL_TAU).astype(np.float32)
    real_profile = per_cycle_activation_profile(real_bin)
    rep_real = structural_report("REAL", real_bin, real_profile)
    print(f"\n[REAL] density={rep_real['density_mean']:.1f} "
          f"autocorr={rep_real['temporal_autocorr']:.4f} "
          f"H0runs/cycle={rep_real['h0_runs_per_cycle']:.2f} "
          f"runlen={rep_real['mean_run_length']:.2f}")

    results = {"REAL": {"structural": rep_real}}
    models = {}

    # ── 변이별 학습 + 샘플 + 구조 평가 ──
    for v in variants:
        print(f"\n{'─'*76}\n[{v}] 학습 중...")
        t0 = time.time()
        model, ddpm, hist, meta = train(v, X_aug, epochs=args.epochs)
        ttrain = time.time() - t0
        print(f"    학습 {ttrain:.1f}s  best_ep={meta['best_epoch']} val={meta['best_val_mse']:.4f}")

        t0 = time.time()
        s = sample(model, ddpm, N_GROUP, SAMPLE_SEED)
        tsample = time.time() - t0
        s_bin = density_match_binarize(s)
        rep = structural_report(v, s_bin, real_profile)
        rep["train_seconds"] = ttrain
        rep["sample_seconds"] = tsample
        print(f"    샘플 {N_GROUP}개 {tsample:.1f}s")
        print(f"    density={rep['density_mean']:.1f} (REAL {rep_real['density_mean']:.1f}) "
              f"autocorr={rep['temporal_autocorr']:.4f} (REAL {rep_real['temporal_autocorr']:.4f})")
        print(f"    JS_profile={rep['js_vs_real_profile']:.5f}  "
              f"H0runs={rep['h0_runs_per_cycle']:.2f} (REAL {rep_real['h0_runs_per_cycle']:.2f})  "
              f"runlen={rep['mean_run_length']:.2f} (REAL {rep_real['mean_run_length']:.2f})")

        results[v] = {"structural": rep, "train_meta": meta, "history": hist[-8:]}
        models[v] = (model, ddpm, s_bin)
        torch.save({"model_state": model.state_dict(), "meta": meta},
                   os.path.join(CACHE_DIR, f"topo_diffusion_{v}.pt"))

    # ── 음악 레벨 ──
    if not args.skip_music:
        print(f"\n{'─'*76}\n[음악 레벨] hibari 파이프라인 로드...")
        t0 = time.time()
        data = suite.setup_hibari()
        orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
        with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
            bundle = pickle.load(f)
        cycle_labeled = bundle["cycle_labeled"]
        assert len(cycle_labeled) == K
        print(f"    완료 ({time.time()-t0:.1f}s) K={len(cycle_labeled)}")

        music_seeds = [101, 202, 303]
        groups = {"REAL": real_bin}
        for v in variants:
            groups[v] = models[v][2]

        for name, bs in groups.items():
            pick = np.random.default_rng(abs(hash(name)) % (2 ** 31)).choice(
                bs.shape[0], size=MUSIC_OM_PER_GROUP, replace=False)
            js_all, cons_all = [], []
            for oi in pick:
                for sd in music_seeds:
                    gen = generate_from_om(data, cycle_labeled, bs[oi], sd)
                    js_all.append(pitch_distribution_similarity(gen, orig_flat)["js_divergence"])
                    cons_all.append(consonance_score(gen))
            entry = {"pitch_js_mean": float(np.mean(js_all)),
                     "pitch_js_std": float(np.std(js_all, ddof=1)),
                     "consonance_mean": float(np.mean(cons_all)),
                     "consonance_std": float(np.std(cons_all, ddof=1)),
                     "n_songs": len(js_all)}
            results.setdefault(name, {})["music"] = entry
            print(f"    [{name:10s}] pitch_JS={entry['pitch_js_mean']:.5f}"
                  f"±{entry['pitch_js_std']:.5f}  consonance={entry['consonance_mean']:.4f}")

    # ── 저장 ──
    payload = {
        "experiment": "topo_diffusion",
        "description": "TopoDiffusionNet 방식 위상 손실 + 1D-conv U-Net 디노이저. "
                       "1D cubical H0 persistence 폐형식(총 상승변동)으로 PH 라이브러리 없이 미분 가능.",
        "config": {"window": WINDOW, "K": K, "stride": STRIDE, "T_diffusion": T_DIFFUSION,
                   "epochs": args.epochs, "ch": CH, "lr": LR, "batch": BATCH,
                   "lambda_topo": LAMBDA_TOPO, "lambda_dens": LAMBDA_DENS,
                   "persist_eps": PERSIST_EPS, "n_group": N_GROUP},
        "baseline_mlp_ddpm_recorded": {
            "source": "docs/step3_data/om_diffusion_results.json (커밋 54e7878)",
            "note": "MLP-DDPM negative — 밀도 3배, autocorr 붕괴",
        },
        "results": results,
        "total_seconds": time.time() - t_total,
    }
    out = os.path.join(STEP3_DIR, f"topo_diffusion_results{args.tag}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*76}\n저장: {out}  (총 {time.time()-t_total:.1f}s)")


if __name__ == "__main__":
    main()
