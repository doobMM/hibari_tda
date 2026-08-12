"""
tools/verify/gen_reference.py — JS RePaint 샘플러 검증용 파이썬 기준값 생성기

목적
────
`hibari_dashboard/public/js/motif-diffusion.js` 의 sampleWithMotif() 가
`experiments/motif_control.py` 의 sample_with_motif() 를 정확히 이식했는지
검증하기 위해, 같은 입력에 대한 "정답" 수치를 계산해 JSON 으로 남긴다.
비교(diff 계산)는 이 파일이 아니라 tools/verify_js_sampler.mjs 가 한다.

**읽기 전용 원본**: experiments/run_topo_diffusion.py, experiments/motif_control.py
는 절대 수정하지 않는다. 이 파일은 그 두 파일에서 실제 프로덕션 함수/클래스를
**import** 해서 쓰거나(스케줄·DDPM 수식), 노이즈 항만 제거하고 모델 호출만
더미로 바꾼 "검증 전용 사본"을 아래에 작성한다(원본 로직은 그대로 베낀다).

왜 노이즈를 0으로 두는가 (검증 방식 B 선택)
────────────────────────────────────────
과제가 제시한 두 방법 중 (A) "양쪽에 동일한 고정 노이즈 배열 주입"은
브라우저 측에서 불가능하다: motif-diffusion.js 의 randn 은 makeRandn(seed) 로
만든 **비공개 클로저**(mulberry32 + Box-Muller)이고, 외부에서 개별 draw 를
주입할 공개 인터페이스가 없다. 이를 가능하게 하려면 배포용 motif-diffusion.js
자체를 수정해야 하는데, 그러면 "실제 배포된 코드"가 아니라 "테스트를 위해
바뀐 코드"를 검증하게 되어 본말이 전도된다.

그래서 (B) "사후분산 항 제거"를 택한다 — 즉 모든 스텝에서 노이즈 기여를 0으로
만들어(ODE/평균-전용 경로) 완전히 결정적인 경로만 비교한다. mulberry32(JS)와
torch.Generator(Python)가 **애초에 다른 알고리즘**이므로 실제 난수 스트림이
같을 이유가 없다 — 이는 버그가 아니라 서로 다른 PRNG 를 쓴 결과이며 검증
대상이 아니다. 우리가 실제로 검증해야 하는 것은 (i) 윈도우 크롭·Hann 융합,
(ii) x̂₀ 클리핑 사후평균 계수, (iii) RePaint 마스크 블렌딩, (iv) respace
스케줄 재계산 — 이 네 가지의 **결정적 산술**이 두 언어에서 같은가이다.
노이즈를 0으로 두면 이 네 가지를 오염 없이 그대로 노출시킬 수 있다.

모델도 같은 이유로 실제 ONNX 가중치 대신 **공유 더미 함수**를 쓴다.
ONNX 모델 자체의 PyTorch-vs-ONNXRuntime 수치 일치는 이미
`tools/export_topo_onnx.py` 가 별도로 검증했다(1e-6 수준, topo_denoiser_meta.json
의 parity_max_abs_diff 참조) — 여기서 다시 검증할 필요가 없다. 대신 두 언어가
**같은 더미 함수**를 쓰면 "모델이 무엇을 예측하든 그 값을 창 경계에서 올바르게
합성/클리핑/마스킹하는가"라는, 지금까지 미검증이었던 로직만 순수하게 시험할 수
있다.

실행
────
  python tools/verify/gen_reference.py
  → tools/verify/reference.json 생성 (JS 쪽 tools/verify_js_sampler.mjs 가 읽음)
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_TOOLS_DIR = _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__)))  # tools/
_TDA_ROOT = _rp_os.path.dirname(_TOOLS_DIR)                                            # tda_pipeline/
_rp_sys.path.insert(0, _TDA_ROOT)
_rp_sys.path.insert(0, _rp_os.path.join(_TDA_ROOT, "experiments"))
# --- end path_bootstrap ---

import json
import math
import time

import numpy as np
import torch

# 읽기 전용 원본에서 실제 프로덕션 함수를 그대로 가져온다 (수정 없음).
from run_topo_diffusion import cosine_beta_schedule, DDPM, K, WINDOW, T_DIFFUSION  # noqa: E402

torch.set_num_threads(1)   # 학습 중인 다른 프로세스의 CPU 를 침범하지 않는다

OUT_DIR = _rp_os.path.dirname(_rp_os.path.abspath(__file__))
OUT_PATH = _rp_os.path.join(OUT_DIR, "reference.json")

SEED = 2026
LONG_T = 240
STRIDE = 15
TEST_I = 100          # item2/3/4 에서 쓰는 고정 스텝 (S=200 비-respace 스케줄)
RESPACE_N = 50         # item5
LOOP_STEPS = 5         # item6
JUMP_U = 4
JUMP_FROM = 0.35


# ═══════════════════════════════════════════════════════════════════════════
# 공유 더미 모델 — JS(tools/verify_js_sampler.mjs)와 완전히 같은 수식이어야 한다.
#   eps[w,c,j] = tanh(0.3*crop + 0.01*(j - win/2) - 0.002*t + 0.05*sin(0.7*c + 0.02*t))
# 실제 ONNX 가중치를 쓰지 않는 이유는 파일 상단 설명 참조.
# ═══════════════════════════════════════════════════════════════════════════

def dummy_eps_torch(crops: torch.Tensor, t: torch.Tensor, win: int) -> torch.Tensor:
    """crops: (W,K,win) float32, t: (W,) long → (W,K,win) float32."""
    Wn, Kn, _ = crops.shape
    c_idx = torch.arange(Kn, dtype=torch.float32).view(1, Kn, 1)
    j_idx = torch.arange(win, dtype=torch.float32).view(1, 1, win)
    t_f = t.float().view(Wn, 1, 1)
    return torch.tanh(0.3 * crops + 0.01 * (j_idx - win / 2.0) - 0.002 * t_f
                       + 0.05 * torch.sin(0.7 * c_idx + 0.02 * t_f))


# ═══════════════════════════════════════════════════════════════════════════
# _fused_eps 검증 사본 — experiments/motif_control.py:174-189 를 베낀 것.
# 바뀐 부분: model(crops, t) → dummy_eps_torch(crops, t, win)  (그 외 동일)
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def fused_eps_verify(x: torch.Tensor, i: int, starts, wwin: torch.Tensor, win: int) -> torch.Tensor:
    crops = torch.cat([x[:, :, s:s + win] for s in starts], dim=0)      # (W,K,win)
    t = torch.full((len(starts),), i, dtype=torch.long)
    eps_w = dummy_eps_torch(crops, t, win) * wwin                        # (W,K,win)

    eps_acc = torch.zeros_like(x)
    w_acc = torch.zeros_like(x)
    for j, s in enumerate(starts):
        eps_acc[0, :, s:s + win] += eps_w[j]
        w_acc[0, :, s:s + win] += wwin[0]
    return eps_acc / w_acc


def build_starts(total_T: int, win: int, stride: int):
    starts = list(range(0, total_T - win + 1, stride))
    if starts[-1] != total_T - win:
        starts.append(total_T - win)
    return starts


# ═══════════════════════════════════════════════════════════════════════════
# sample_with_motif 검증 사본 (노이즈=0) — experiments/motif_control.py:192-239
# 를 베낀 것. 바뀐 부분:
#   · model(...) → dummy_eps_torch(...)
#   · x_unknown 의 sqrt(post_var)*randn 항 제거 (0)
#   · x_known 의 sqrt_1mac[i-1]*randn 항 제거 (0)
#   · 되돌림(jump) 재샘플링의 sqrt(betas)*randn 항 제거 (0)
# 그 외 변수명·연산 순서·분기 조건은 원본과 동일하게 유지했다.
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def sample_step_deterministic(x: torch.Tensor, i: int, ddpm_like, starts, wwin, win: int,
                               known: torch.Tensor, m: torch.Tensor):
    """한 스텝(노이즈 0)을 적용하고 (eps_fused, x0, mean, x_after_mask) 를 모두 반환."""
    eps = fused_eps_verify(x, i, starts, wwin, win)
    x0 = ddpm_like.pred_x0(x, torch.tensor([i]), eps)          # [-1,1] 클리핑 포함
    mean = ddpm_like.post_c0[i] * x0 + ddpm_like.post_ct[i] * x
    x_unknown = mean                                            # noise=0 (i>0 이어도)

    if i > 0:
        a = ddpm_like.sqrt_ac[i - 1]
        x_known = a * known                                     # noise=0
    else:
        x_known = known
    x_new = m * x_known + (1.0 - m) * x_unknown
    return eps, x0, mean, x_new


@torch.no_grad()
def sample_with_motif_verify(ddpm_like, total_T: int, known01: np.ndarray, mask: np.ndarray,
                              win: int, stride: int, jump_u: int, jump_from: float,
                              x_init: np.ndarray) -> np.ndarray:
    """x_init: (K,T) 고정 배열을 그대로 초기 x 로 쓴다.

    원본(motif_control.py)은 초기 x 를 torch.Generator(매 언어마다 다른 PRNG
    알고리즘)로 뽑지만, 그러면 JS(mulberry32)와 애초에 값이 다른 배열에서
    출발하게 되어 "같은 입력에서 같은 산술을 하는가"를 시험할 수 없다.
    그래서 여기서는 reference.json 에 실어 보내는 고정 x_init(K,T) 을 두
    언어가 똑같이 시작점으로 쓰도록 파라미터로 받는다 — 노이즈=0 선택(옵션 B)과
    같은 이유의 결정론화다.
    """
    known = torch.from_numpy(known01.T[None].astype(np.float32)) * 2.0 - 1.0
    m = torch.from_numpy(mask.T[None].astype(np.float32))
    starts = build_starts(total_T, win, stride)
    wwin = torch.hann_window(win, periodic=False).clamp_min(1e-3)[None, None, :]

    x = torch.from_numpy(x_init[None].astype(np.float32))        # (1,K,T) 고정 시작점
    jump_start = int(ddpm_like.T * jump_from)

    for i in reversed(range(ddpm_like.T)):
        u_reps = jump_u if i < jump_start else 1
        for u in range(u_reps):
            _, _, _, x = sample_step_deterministic(x, i, ddpm_like, starts, wwin, win, known, m)
            # 되돌림 — 노이즈=0 이므로 sqrt(alphas)*x 만 남는다 (경계 조화 항은 제거)
            if u < u_reps - 1 and i > 0:
                x = torch.sqrt(ddpm_like.alphas[i]) * x

    return torch.clamp((x + 1.0) / 2.0, 0, 1)[0].T.numpy().astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# respace — 파이썬 원본이 없다 (JS 전용 최적화). motif-diffusion.js:108-122 의
# 알고리즘 설명을 바탕으로 **독립 재구현**한다 (베끼지 않고 스펙만 보고 새로
# 작성 — 같은 알고리즘을 서로 다른 코드로 짜서 교차검증하는 것이 목적).
#
# 주의: JS Math.round 는 0.5 를 항상 +Infinity 방향으로 올림한다
# (round-half-away-from-zero, 여기서는 입력이 항상 ≥0 이므로 round-half-up과
# 동일). Python 내장 round()/np.round 는 banker's rounding(round-half-to-even)
# 이라 .5 경계에서 다른 결과를 낼 수 있으므로, math.floor(x+0.5) 로 JS 의
# Math.round 를 명시적으로 재현한다.
# ═══════════════════════════════════════════════════════════════════════════

def js_math_round(x: float) -> int:
    return math.floor(x + 0.5)


def derive_from_betas(betas: np.ndarray) -> dict:
    """DDPM.__init__ (run_topo_diffusion.py:270-285) 의 수식을 그대로 옮긴 것 —
    임의 길이의 beta 배열에 적용할 수 있도록 일반화했을 뿐 계수식은 원본과 동일."""
    betas_t = torch.from_numpy(betas.astype(np.float64))
    alphas = 1.0 - betas_t
    ac = torch.cumprod(alphas, dim=0)
    ac_prev = torch.cat([torch.ones(1, dtype=torch.float64), ac[:-1]])
    sqrt_ac = torch.sqrt(ac)
    sqrt_1mac = torch.sqrt(1.0 - ac)
    post_var = betas_t * (1.0 - ac_prev) / (1.0 - ac)
    post_c0 = betas_t * torch.sqrt(ac_prev) / (1.0 - ac)
    post_ct = (1.0 - ac_prev) * torch.sqrt(alphas) / (1.0 - ac)
    return {
        "betas": betas_t.numpy(), "alphas": alphas.numpy(), "alphas_cumprod": ac.numpy(),
        "sqrt_ac": sqrt_ac.numpy(), "sqrt_1mac": sqrt_1mac.numpy(),
        "post_var": post_var.numpy(), "post_c0": post_c0.numpy(), "post_ct": post_ct.numpy(),
    }


def respace_py(base_betas: np.ndarray, n_steps: int) -> dict:
    """motif-diffusion.js 의 respace(sched, nSteps) 독립 재구현.
    base_betas: 원 스케줄(T=200)의 beta 배열."""
    T = len(base_betas)
    if not n_steps or n_steps >= T:
        return derive_from_betas(base_betas)

    base = derive_from_betas(base_betas)          # alphas_cumprod 필요
    ac_base = base["alphas_cumprod"]

    src_idx = [min(T - 1, js_math_round(s * (T - 1) / (n_steps - 1))) for s in range(n_steps)]
    betas = np.zeros(n_steps, dtype=np.float64)
    prev_ac = 1.0
    for s in range(n_steps):
        ac = ac_base[src_idx[s]]
        betas[s] = min(0.9999, max(1e-8, 1 - ac / prev_ac))
        prev_ac = ac
    return derive_from_betas(betas)


# ═══════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════

def to_list(t) -> list:
    if isinstance(t, torch.Tensor):
        t = t.numpy()
    return np.asarray(t).astype(np.float64).flatten().tolist()


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    # ── 고정 입력 데이터 (JS 쪽도 이 JSON 을 그대로 읽어 쓴다) ──
    x_init = rng.normal(0.0, 1.0, size=(K, LONG_T)).astype(np.float32)          # (K,T) — 모델 입력 레이아웃
    known01 = (rng.random((LONG_T, K)) > 0.5).astype(np.float32)                 # (T,K) ∈{0,1}
    mask = np.zeros((LONG_T, K), dtype=np.float32)
    mask[0:40, ::2] = 1.0                                                        # 앞부분 짝수 cycle 고정 (item4 테스트용)

    starts = build_starts(LONG_T, WINDOW, STRIDE)
    print(f"[설정] T={LONG_T} win={WINDOW} stride={STRIDE} 창 {len(starts)}개: {starts}")
    assert len(starts) == 13, f"창 개수가 13이 아님: {len(starts)}"

    # ── item1: Hann window (실제 프로덕션 라인과 동일한 API 호출) ──
    wwin_full = torch.hann_window(WINDOW, periodic=False).clamp_min(1e-3)
    hann60 = to_list(wwin_full)
    print(f"[item1] hann[:5]={hann60[:5]}")
    print(f"[item1] hann[-5:]={hann60[-5:]}")
    print(f"[item1] hann min={min(hann60):.6f}")

    # ── 실제 프로덕션 스케줄 (T=200, DDPM 원본 그대로) ──
    ddpm200 = DDPM(timesteps=T_DIFFUSION)
    cosine_betas_200 = cosine_beta_schedule(T_DIFFUSION)   # 실제 프로덕션 함수, 수정 없음
    print(f"[스케줄] cosine_beta_schedule(200) betas[:3]={cosine_betas_200[:3].tolist()}")

    # 배포된 meta.json 의 betas 는 export_topo_onnx.py 가 DDPM().betas 를 그대로
    # 저장한 것이므로, 위에서 재계산한 cosine_betas_200 과 같아야 한다. 이게 실제로
    # 대시보드가 fetch 해서 쓰는 배열이므로 그대로 실어 보낸다 — JS 쪽에서
    # _cosineSchedule(200) 재계산 결과와 "배포된 meta.betas" 를 모두 대조한다.
    meta_path = _rp_os.path.join(_TDA_ROOT, "hibari_dashboard", "public", "models",
                                  "topo_denoiser_meta.json")
    with open(meta_path, encoding="utf-8") as f:
        deployed_meta = json.load(f)
    deployed_betas_200 = deployed_meta["schedule"]["betas"]
    print(f"[스케줄] 배포 meta.json betas[:3]={deployed_betas_200[:3]}")

    # ── item2/3/4: 고정 스텝 i=100, T=240, dummy model, noise=0 ──
    x_t = torch.from_numpy(x_init[None])                                         # (1,K,T)
    wwin = wwin_full[None, None, :]
    known_t = torch.from_numpy(known01.T[None].astype(np.float32)) * 2.0 - 1.0
    mask_t = torch.from_numpy(mask.T[None].astype(np.float32))

    eps_fused, x0_i, mean_i, x_after_mask = sample_step_deterministic(
        x_t, TEST_I, ddpm200, starts, wwin, WINDOW, known_t, mask_t)

    print(f"[item2] fused eps shape={tuple(eps_fused.shape)} "
          f"mean={eps_fused.mean().item():.6f} max={eps_fused.abs().max().item():.6f}")
    print(f"[item3] mean(posterior) mean={mean_i.mean().item():.6f} "
          f"max|x0|={x0_i.abs().max().item():.6f} (clip 확인용, 1.0 넘으면 버그)")
    print(f"[item4] x_after_mask mean={x_after_mask.mean().item():.6f}")

    # ── item5: respace(200 → 50) 독립 재구현 ──
    resp = respace_py(cosine_betas_200.numpy(), RESPACE_N)
    print(f"[item5] respace(50) betas[:3]={resp['betas'][:3].tolist()}")
    print(f"[item5] respace(50) post_c0[:3]={resp['post_c0'][:3].tolist()}")

    # ── item6: 전체 루프 (respace 50 → S=5 로 재적용, 즉 200→5). ──
    # motif-diffusion.js 의 respace() 는 항상 "원 스케줄(T=200)" 에서 바로 nSteps
    # 로 재배치한다(50을 거치지 않음) — sampleWithMotif 안에서
    # respace(this._baseSchedule(), o.steps||50) 이 한 번만 호출되기 때문이다.
    # 따라서 item6 은 respace_py(cosine_betas_200, LOOP_STEPS) 를 직접 써야
    # JS 의 실제 호출 경로와 일치한다.
    resp5 = respace_py(cosine_betas_200.numpy(), LOOP_STEPS)

    class DDPMLike:
        """DDPM 클래스와 같은 속성 이름을 갖는 얇은 래퍼 — respace 결과를 그대로 담아
        sample_step_deterministic/sample_with_motif_verify 에 그대로 넘기기 위함."""
        def __init__(self, d: dict):
            self.T = len(d["betas"])
            self.betas = torch.from_numpy(d["betas"]).float()
            self.alphas = torch.from_numpy(d["alphas"]).float()
            self.alphas_cumprod = torch.from_numpy(d["alphas_cumprod"]).float()
            self.sqrt_ac = torch.from_numpy(d["sqrt_ac"]).float()
            self.sqrt_1mac = torch.from_numpy(d["sqrt_1mac"]).float()
            self.post_var = torch.from_numpy(d["post_var"]).float()
            self.post_c0 = torch.from_numpy(d["post_c0"]).float()
            self.post_ct = torch.from_numpy(d["post_ct"]).float()

        def pred_x0(self, x_t, t, eps):
            a = self.sqrt_ac[t][:, None, None]
            b = self.sqrt_1mac[t][:, None, None]
            return torch.clamp((x_t - b * eps) / a, -1.0, 1.0)

    ddpm5 = DDPMLike(resp5)
    x_out = sample_with_motif_verify(ddpm5, LONG_T, known01, mask, WINDOW, STRIDE, JUMP_U, JUMP_FROM,
                                      x_init)
    print(f"[item6] S={ddpm5.T} 최종 x_out shape={x_out.shape} mean={x_out.mean():.6f} "
          f"min={x_out.min():.6f} max={x_out.max():.6f}")

    # ── JSON 저장 ──
    payload = {
        "config": {"K": K, "win": WINDOW, "stride": STRIDE, "T": LONG_T, "seed": SEED,
                   "test_i": TEST_I, "respace_n": RESPACE_N, "loop_steps": LOOP_STEPS,
                   "jump_u": JUMP_U, "jump_from": JUMP_FROM, "starts": starts,
                   "t_diffusion": T_DIFFUSION},
        "inputs": {"x_init": x_init.astype(np.float64).tolist(),      # (K,T)
                   "known01": known01.astype(np.float64).tolist(),     # (T,K)
                   "mask": mask.astype(np.float64).tolist()},          # (T,K)
        "item1_hann60": hann60,
        "cosine_betas_200": to_list(cosine_betas_200),
        "deployed_meta_betas_200": deployed_betas_200,
        "ddpm200_post_c0": to_list(ddpm200.post_c0),
        "ddpm200_post_ct": to_list(ddpm200.post_ct),
        "ddpm200_post_var": to_list(ddpm200.post_var),
        "item2_fused_eps": to_list(eps_fused),      # (K,T) flattened
        "item3_x0": to_list(x0_i),
        "item3_mean": to_list(mean_i),
        "item4_x_after_mask": to_list(x_after_mask),
        "item5_respace50": {k: v.tolist() for k, v in resp.items()},
        "item5_respace_loopsteps": {k: v.tolist() for k, v in resp5.items()},
        "item6_x_out": x_out.astype(np.float64).tolist(),   # (T,K)
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    print(f"\n저장: {OUT_PATH}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
