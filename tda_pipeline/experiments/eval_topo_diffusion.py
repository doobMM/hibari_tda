"""
eval_topo_diffusion.py — 세 변이를 한 표에 놓고 비교 (이진화 프로토콜 2종 병기)

왜 별도 스크립트인가 — 이진화 프로토콜의 공정성 문제
────────────────────────────────────────────────────
기존 `run_om_diffusion.py` 는 REAL 은 **τ=0.5 임계값**으로, 생성물은 **밀도 일치
(Σp 개의 상위 셀만 ON)** 로 이진화했다. 그런데 연속 OM 의 평균 활성도는 0.2637
이므로 밀도 일치는 840×0.2637 ≈ 222 셀을 켜는 반면, τ=0.5 는 139 셀만 켠다.
**연속 분포를 완벽히 재현한 모델조차 밀도 일치 하에서는 REAL(139)에 도달할 수
없다.** 즉 두 군을 서로 다른 자로 잰 셈이다.

여기서는 두 프로토콜을 모두 보고한다:
  · tau05      — 학습 데이터와 **동일한** 자. 본 실험의 1차 판정 기준.
  · densmatch  — 기존 negative 기록(커밋 54e7878)과 **직접 비교**하기 위한 자.

MLP-DDPM 은 출력이 거의 균일 0.5 였으므로 두 자 모두에서 실패한다
(τ=0.5 로 잘라도 절반이 켜진다) — 따라서 기존 negative 결론 자체는 바뀌지 않는다.

실행:  python experiments/eval_topo_diffusion.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os
import pickle
import time
from typing import Dict, List

import numpy as np
import torch

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity

from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, K, LONG_T, N_GROUP, REAL_TAU, SAMPLE_SEED, STEP3_DIR,
    TDA_ROOT, VARIANTS, WINDOW, DDPM, TopoConvUNet, consonance_score,
    density_match_binarize, generate_from_om, h0_runs_np, js_divergence_profiles,
    load_continuous_om, per_cycle_activation_profile, sample,
    sample_multidiffusion, sliding_windows_ct, structural_report,
)

MUSIC_OM_PER_GROUP = 8
MUSIC_SEEDS = [101, 202, 303]

# 기존 negative 기록 (docs/step3_data/om_diffusion_results.json, 커밋 54e7878)
BASELINE = {
    "REAL": {"density_mean": 139.0, "temporal_autocorr": 0.8135,
             "js_vs_real_profile": 0.0, "diversity": 222.07, "music_js": 0.06144},
    "VAE": {"density_mean": 218.23, "temporal_autocorr": 0.7450,
            "js_vs_real_profile": 0.01011, "diversity": 304.60, "music_js": 0.08022},
    "MLP_DDPM": {"density_mean": 418.22, "temporal_autocorr": 0.5038,
                 "js_vs_real_profile": 0.03037, "diversity": 420.00, "music_js": 0.04628},
}


def load_model(variant: str):
    path = os.path.join(CACHE_DIR, f"topo_diffusion_{variant}.pt")
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    m = TopoConvUNet()
    m.load_state_dict(ckpt["model_state"])
    m.eval()
    return m, DDPM(), ckpt.get("meta", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true")
    ap.add_argument("--skip-long", action="store_true")
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t_total = time.time()
    print("=" * 84)
    print("위상 손실 디퓨전 — 변이 비교 (이진화 프로토콜 2종)")
    print("=" * 84)

    om = load_continuous_om()
    X = sliding_windows_ct(om, WINDOW, 2).transpose(0, 2, 1)     # (n,T,K)
    rng = np.random.default_rng(2026)
    real_raw = X[rng.choice(X.shape[0], size=N_GROUP, replace=False)]

    # REAL 은 두 자 모두로 만들어 둔다
    real_bins = {"tau05": (real_raw >= REAL_TAU).astype(np.float32),
                 "densmatch": density_match_binarize(real_raw)}
    real_profiles = {k: per_cycle_activation_profile(v) for k, v in real_bins.items()}

    raw_samples: Dict[str, np.ndarray] = {}
    metas: Dict[str, dict] = {}
    for v in VARIANTS:
        m, ddpm, meta = load_model(v)
        t0 = time.time()
        raw_samples[v] = sample(m, ddpm, N_GROUP, SAMPLE_SEED)
        metas[v] = meta
        print(f"  [{v}] 샘플 {N_GROUP}개 {time.time()-t0:.1f}s "
              f"(best_ep={meta.get('best_epoch')} val={meta.get('best_val_mse',0):.4f}) "
              f"평균값={raw_samples[v].mean():.4f}")
    print(f"  [REAL] 연속 평균값={real_raw.mean():.4f}")

    results: Dict[str, dict] = {"baseline_recorded": BASELINE, "protocols": {}}

    for proto in ("tau05", "densmatch"):
        binf = ((lambda s: (s >= REAL_TAU).astype(np.float32)) if proto == "tau05"
                else density_match_binarize)
        real_bin = real_bins[proto]
        real_prof = real_profiles[proto]
        rep_real = structural_report("REAL", real_bin, real_prof)

        print(f"\n{'─'*84}\n[프로토콜 {proto}]  "
              f"({'학습 데이터와 동일한 자 — 1차 판정' if proto=='tau05' else '기존 기록과 직접 비교용'})")
        print(f"  {'group':<12} {'density':>8} {'autocorr':>9} {'JSprof':>9} "
              f"{'H0runs':>7} {'runlen':>7} {'diversity':>10}")
        print(f"  {'REAL':<12} {rep_real['density_mean']:>8.1f} "
              f"{rep_real['temporal_autocorr']:>9.4f} {'—':>9} "
              f"{rep_real['h0_runs_per_cycle']:>7.2f} {rep_real['mean_run_length']:>7.2f} "
              f"{rep_real['diversity_pairwise_hamming']:>10.1f}")

        proto_res = {"REAL": rep_real}
        bins_for_music = {"REAL": real_bin}
        for v in VARIANTS:
            bs = binf(raw_samples[v])
            rep = structural_report(v, bs, real_prof)
            proto_res[v] = rep
            bins_for_music[v] = bs
            print(f"  {v:<12} {rep['density_mean']:>8.1f} {rep['temporal_autocorr']:>9.4f} "
                  f"{rep['js_vs_real_profile']:>9.5f} {rep['h0_runs_per_cycle']:>7.2f} "
                  f"{rep['mean_run_length']:>7.2f} {rep['diversity_pairwise_hamming']:>10.1f}")

        results["protocols"][proto] = {"structural": proto_res}
        if proto == "tau05":
            music_bins = bins_for_music

    # ── 장형 (MultiDiffusion) 구조 검사 ──
    if not args.skip_long:
        print(f"\n{'─'*84}\n[MultiDiffusion 장형 T={LONG_T}]")
        m, ddpm, _ = load_model("full")
        longs = []
        for i in range(4):
            t0 = time.time()
            longs.append(sample_multidiffusion(m, ddpm, LONG_T, SAMPLE_SEED + i * 17))
            print(f"  {i+1}/4 ({time.time()-t0:.1f}s)")
        L = np.stack(longs)
        Lb = (L >= REAL_TAU).astype(np.float32)
        starts = rng.choice(om.shape[0] - LONG_T, size=4, replace=False)
        Rb = np.stack([(om[s:s + LONG_T] >= REAL_TAU).astype(np.float32) for s in starts])
        rp = per_cycle_activation_profile(Rb)
        for nm, arr in (("REAL_LONG", Rb), ("FULL_LONG", Lb)):
            rep = structural_report(nm if nm == "REAL_LONG" else "x", arr, rp)
            rep["density_per_step"] = rep["density_mean"] / LONG_T
            results.setdefault("long_form", {})[nm] = rep
            print(f"  {nm:<11} density/step={rep['density_per_step']:.2f} "
                  f"autocorr={rep['temporal_autocorr']:.4f} "
                  f"H0runs={rep['h0_runs_per_cycle']:.2f} runlen={rep['mean_run_length']:.2f} "
                  f"JSprof={rep['js_vs_real_profile']:.5f}")

    # ── 음악 레벨 (tau05 기준) ──
    if not args.skip_music:
        print(f"\n{'─'*84}\n[음악 레벨] hibari 파이프라인 로드...")
        t0 = time.time()
        data = suite.setup_hibari()
        orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
        with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
            cycle_labeled = pickle.load(f)["cycle_labeled"]
        print(f"  완료 ({time.time()-t0:.1f}s)")
        print(f"  {'group':<12} {'pitch_JS':>18} {'consonance':>18} {'notes':>7}")
        for name, bs in music_bins.items():
            pick = np.random.default_rng(abs(hash(name)) % (2**31)).choice(
                bs.shape[0], size=MUSIC_OM_PER_GROUP, replace=False)
            js, cons, nn = [], [], []
            for oi in pick:
                for sd in MUSIC_SEEDS:
                    gen = generate_from_om(data, cycle_labeled, bs[oi], sd)
                    if not gen:
                        continue
                    js.append(pitch_distribution_similarity(gen, orig_flat)["js_divergence"])
                    cons.append(consonance_score(gen))
                    nn.append(len(gen))
            entry = {"pitch_js_mean": float(np.mean(js)), "pitch_js_std": float(np.std(js, ddof=1)),
                     "consonance_mean": float(np.mean(cons)),
                     "consonance_std": float(np.std(cons, ddof=1)),
                     "n_notes_mean": float(np.mean(nn)), "n_songs": len(js)}
            results["protocols"]["tau05"].setdefault("music", {})[name] = entry
            print(f"  {name:<12} {entry['pitch_js_mean']:>10.5f}±{entry['pitch_js_std']:.5f} "
                  f"{entry['consonance_mean']:>10.4f}±{entry['consonance_std']:.4f} "
                  f"{entry['n_notes_mean']:>7.0f}")

    results["variant_meta"] = metas
    out = os.path.join(STEP3_DIR, "topo_diffusion_compare.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*84}\n저장: {out}  ({time.time()-t_total:.1f}s)")


if __name__ == "__main__":
    main()
