"""
refair_mlp_baseline.py — 기존 MLP-DDPM 을 **같은 자로** 다시 재보기

왜 필요한가
──────────
`run_topo_diffusion.py` 의 샘플러에서 x̂₀ 클리핑 누락 버그를 잡았더니
결과가 완전히 달라졌다 (density 364→132, 원곡 139). 그런데 2026-06-21 의
MLP-DDPM negative 기록도 **같은 버그가 있는 샘플러**로 만들어졌다.

그렇다면 "MLP 는 시간축을 못 배운다"는 진단이 사실은 샘플러 버그였을 수도 있다.
아키텍처 교체의 공을 주장하려면 **MLP 를 고친 샘플러로 다시 재봐야** 한다.
학습은 다시 하지 않는다 — 저장된 가중치(`cache/om_diffusion.pt`)를 그대로 쓰고
샘플링만 바꾼다. 학습에는 버그가 없었기 때문이다.

세 가지를 비교한다:
  MLP_old   기록된 수치 (버그 있는 샘플러)
  MLP_fixed 같은 가중치 + 고친 샘플러          ← 공정한 비교 대상
  conv/full 새 아키텍처 + 고친 샘플러

실행:  python experiments/refair_mlp_baseline.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import json
import os

import numpy as np
import torch

from run_topo_diffusion import (
    CACHE_DIR, K, REAL_TAU, STEP3_DIR, TDA_ROOT, WINDOW, DDPM,
    density_match_binarize, load_continuous_om, per_cycle_activation_profile,
    sliding_windows_ct, structural_report,
)
from run_om_diffusion import DIM, DenoiserMLP

N_GROUP = 64
SAMPLE_SEED = 7

RECORDED = {   # docs/step3_data/om_diffusion_results.json (커밋 54e7878)
    "density_mean": 418.22, "temporal_autocorr": 0.5038,
    "js_vs_real_profile": 0.03037, "diversity_pairwise_hamming": 420.00,
}


@torch.no_grad()
def sample_mlp_fixed(model: DenoiserMLP, ddpm: DDPM, n: int, seed: int) -> np.ndarray:
    """MLP 디노이저를 **x̂₀ 클리핑 사후평균**으로 샘플링. 반환 (n,T,K) ∈[0,1]."""
    model.eval()
    g = torch.Generator().manual_seed(seed)
    x = torch.randn((n, DIM), generator=g)
    for i in reversed(range(ddpm.T)):
        t = torch.full((n,), i, dtype=torch.long)
        eps = model(x, t)
        x0 = torch.clamp((x - ddpm.sqrt_1mac[i] * eps) / ddpm.sqrt_ac[i], -1.0, 1.0)
        mean = ddpm.post_c0[i] * x0 + ddpm.post_ct[i] * x
        x = (mean + torch.sqrt(ddpm.post_var[i]) * torch.randn(x.shape, generator=g)
             if i > 0 else mean)
    x01 = torch.clamp((x + 1.0) / 2.0, 0, 1).reshape(n, WINDOW, K)
    return np.ascontiguousarray(x01.numpy(), dtype=np.float32)


@torch.no_grad()
def sample_mlp_buggy(model: DenoiserMLP, ddpm: DDPM, n: int, seed: int) -> np.ndarray:
    """기록을 만든 원래 샘플러 (클리핑 없음) — 재현 확인용."""
    model.eval()
    g = torch.Generator().manual_seed(seed)
    x = torch.randn((n, DIM), generator=g)
    for i in reversed(range(ddpm.T)):
        t = torch.full((n,), i, dtype=torch.long)
        eps = model(x, t)
        mean = (x - ddpm.betas[i] / ddpm.sqrt_1mac[i] * eps) / torch.sqrt(ddpm.alphas[i])
        x = (mean + torch.sqrt(ddpm.post_var[i]) * torch.randn(x.shape, generator=g)
             if i > 0 else mean)
    x01 = torch.clamp((x + 1.0) / 2.0, 0, 1).reshape(n, WINDOW, K)
    return np.ascontiguousarray(x01.numpy(), dtype=np.float32)


def main():
    os.chdir(TDA_ROOT)
    torch.set_num_threads(2)

    om = load_continuous_om()
    X = sliding_windows_ct(om, WINDOW, 2).transpose(0, 2, 1)
    real = X[np.random.default_rng(2026).choice(X.shape[0], N_GROUP, replace=False)]
    real_bin = (real >= REAL_TAU).astype(np.float32)
    real_prof = per_cycle_activation_profile(real_bin)
    rep_real = structural_report("REAL", real_bin, real_prof)

    ck = torch.load(os.path.join(CACHE_DIR, "om_diffusion.pt"),
                    map_location="cpu", weights_only=False)
    model = DenoiserMLP()
    model.load_state_dict(ck["model_state"])
    ddpm = DDPM()

    print("=" * 84)
    print("MLP-DDPM 재평가 — 학습 재실행 없음, 샘플링만 고친 자로")
    print("=" * 84)
    print(f"  가중치: cache/om_diffusion.pt (best_ep="
          f"{ck.get('train_meta', {}).get('best_epoch')})")

    out = {"REAL": rep_real, "MLP_recorded": RECORDED}
    rows = [("REAL", rep_real)]

    for label, fn in (("MLP_buggy", sample_mlp_buggy), ("MLP_fixed", sample_mlp_fixed)):
        s = fn(model, ddpm, N_GROUP, SAMPLE_SEED)
        for proto, b in (("tau05", (s >= REAL_TAU).astype(np.float32)),
                         ("densmatch", density_match_binarize(s))):
            rep = structural_report(label, b, real_prof)
            rep["raw_mean"] = float(s.mean())
            rep["raw_std"] = float(s.std())
            out[f"{label}_{proto}"] = rep
            rows.append((f"{label}/{proto}", rep))

    print(f"\n  {'group':<22} {'density':>8} {'autocorr':>9} {'JSprof':>9} "
          f"{'H0runs':>7} {'runlen':>7} {'raw평균':>8}")
    for name, r in rows:
        print(f"  {name:<22} {r['density_mean']:>8.1f} {r['temporal_autocorr']:>9.4f} "
              f"{r['js_vs_real_profile']:>9.5f} {r['h0_runs_per_cycle']:>7.2f} "
              f"{r['mean_run_length']:>7.2f} {r.get('raw_mean', float('nan')):>8.4f}")
    print(f"  {'MLP 기록(2026-06)':<22} {RECORDED['density_mean']:>8.1f} "
          f"{RECORDED['temporal_autocorr']:>9.4f} {RECORDED['js_vs_real_profile']:>9.5f}")

    p = os.path.join(STEP3_DIR, "mlp_baseline_refair.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"experiment": "mlp_baseline_refair",
                   "purpose": "샘플러 x̂₀ 클리핑 버그 수정이 기존 MLP negative 결론을 바꾸는지 확인",
                   "results": out}, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {p}")


if __name__ == "__main__":
    main()
