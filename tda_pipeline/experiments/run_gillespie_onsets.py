"""
run_gillespie_onsets.py — 스텝별 음 개수를 OM 이 정하게 한다 (τ-leaping)

무엇을 고치는가
──────────────
지금 Algorithm 1 은 스텝 j 에서 뽑을 음의 개수를 `MODULES` 고정 스케줄에서 가져온다.
이 스케줄은 중첩행렬(OM)과 **무관**하다. 그래서 모티브를 바꿔도 음악 표면의 밀도가
거의 안 바뀐다 — 모티브 창 안/밖 밀도비가 1.10~1.18 에 그쳤다
(`docs/motif_music_analysis.md`). "OM 은 어떤 음을 뽑을지만 정하고 몇 개 뽑을지는
정하지 않는다"는 한계가 여기서 나온다.

근거 — 원곡을 재보면 이 설계가 정보를 버리고 있다
────────────────────────────────────────────────
hibari 원곡에서 스텝별 onset 수를 세어 상관을 재면:

  OM 연속 활성합 vs onset      Pearson +0.663   Spearman +0.700
  OM **이진** 활성수 vs onset  Pearson +0.571   Spearman +0.587   ← 실제로 쓰는 자
  MODULES 스케줄 vs onset      Pearson +0.587   Spearman +0.571
  원곡 32주기 평균 프로파일     Pearson +0.695                     ← 셋 다 이긴다

⚠ **이 동기 근거는 무너졌다** (적대적 감사 2026-08-13). 세 가지 이유다.
  1. `fit_propensity` 는 `binarized=True` 가 기본이라 **이진 활성수**를 쓴다.
     그 자로 재면 Pearson 기준 **MODULES(+0.587)가 OM(+0.571)보다 낫다.**
     연속값 r=0.663 은 연속/이진 불일치 버그를 고치면서 무효가 된 수치인데
     갱신하지 않았다 — MEMORY.md 유형 B 의 재발이다.
  2. 자유도가 다르다. OM 은 1088스텝 신호, MODULES 는 사실상 2값(3/4) 상수 템플릿이다.
     같은 계열의 **최선** baseline(원곡 32주기 평균 프로파일)은 +0.695 로 OM 을 이긴다.
     밀도 정보는 **32주기 구조**에 있고 MODULES 가 그 구조의 나쁜 판본이었을 뿐이다.
  3. 결정적으로, 메커니즘을 뺀 대조군이 τ-leaping 을 이긴다 (아래).

**대조군 실측** (같은 8케이스 × 6시드, onset_hist_JS):

  modules_fixed        0.22555   —        음 361.5
  tau_leaping_matched  0.17008   −24.6%   음 423.8
  poisson_const        0.17558   −22.2%   음 398.1   ← OM 미사용
  modules_×1.2         0.15322   −32.1%   음 462.6   ← OM·확률성 둘 다 미사용
  modules_×1.6         0.13710   −39.2%   음 566.5

τ-leaping vs OM-free `poisson_const` 케이스수준 paired **p = 0.106 — 판별 불가**.
모드 간 corr(음 수, JS) = **−0.869**. 이 지표는 사실상 "음을 충분히 냈나"를 잰다.

**따라서 "OM 이 리듬 밀도를 잡는다"고 주장할 수 없다.** 남는 정직한 진술은
"고정 스케줄을 확률화하면 리듬분포 JS 가 −22~32% 개선되나 대부분 음 수 증가 효과이며,
OM 활성도 자체의 기여는 판별되지 않았다" 이다.

방법 — Gillespie τ-leaping
─────────────────────────
음의 발생을 반응 사건으로 본다. 스텝 j 의 propensity 를 OM 활성도의 함수로 두고,
한 스텝(τ=1) 동안의 사건 수를 Poisson 으로 뽑는다:

    λ_j = max(0, a + b · activity_j)          (원곡에서 최소제곱으로 적합)
    n_j ~ Poisson(λ_j),  0 ≤ n_j ≤ n_max

정확 Gillespie(사건마다 지수분포 대기시간)를 쓰지 않고 τ-leaping 을 쓰는 이유는
우리 시간축이 이미 8분음표 격자로 이산화돼 있어 τ=1 스텝이 자연스럽고,
스텝 안에서 propensity 가 상수라 leap 조건이 정확히 성립하기 때문이다.
(수업 자료 `수리생물학/hw3` Exercise 3.6 의 tau_leaping 과 같은 구조.)

`generation.py` 는 수정하지 않는다 — `inst_len` 인자만 갈아끼운다.

실행:  python experiments/run_gillespie_onsets.py [--n-seeds 20]
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
import random
import time
from typing import Dict, List, Tuple

import numpy as np

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from generation import CycleSetManager, NodePool, algorithm1_optimized

from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, js_divergence_profiles, load_continuous_om,
)

N_MAX = 8            # 원곡 최대 onset 수
MOTIF_RESULTS = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")


# ═══════════════════════════════════════════════════════════════════════════
# 1. 원곡에서 propensity 적합
# ═══════════════════════════════════════════════════════════════════════════

def fit_propensity(data: dict, om: np.ndarray, binarized: bool = True) -> Tuple[float, float, dict]:
    """
    원곡의 (OM 활성도 → onset 수) 관계를 최소제곱 직선으로 적합.

    **적합과 적용은 반드시 같은 자를 써야 한다.** 처음엔 연속 OM 활성합(평균 3.69)으로
    적합해 놓고 이진 활성수(평균 2.21, 모티브 OM 은 1.30)에 적용해 λ 가 3.53 대신
    0.87 이 됐다 — 음이 41% 사라졌다. 적용 대상이 이진이므로 적합도 이진으로 한다.
    """
    T = om.shape[0]
    on = np.zeros(T)
    for s, _p, _e in list(data["inst1_real"]) + list(data["inst2_real"]):
        if 0 <= s < T:
            on[s] += 1
    act = (om >= REAL_TAU).sum(axis=1).astype(float) if binarized else om.sum(axis=1)
    b, a = np.polyfit(act, on, 1)               # on ≈ a + b·act
    pred = np.clip(a + b * act, 0, N_MAX)
    ss_res = float(((on - pred) ** 2).sum())
    ss_tot = float(((on - on.mean()) ** 2).sum())
    meta = {
        "intercept_a": float(a), "slope_b": float(b),
        "r2": 1.0 - ss_res / ss_tot,
        "onset_mean_real": float(on.mean()),
        "lambda_mean_fit": float(pred.mean()),
        "modules_mean": float(np.mean(MODULES)),
    }
    return float(a), float(b), meta


def tau_leap_inst_len(om_bin: np.ndarray, a: float, b: float,
                      rng: np.random.Generator, n_max: int = N_MAX,
                      match_total: float = None) -> List[int]:
    """
    τ-leaping — 스텝별 propensity λ_j 로 Poisson 추출.

    match_total 을 주면 Σλ 를 그 값에 맞춰 재정규화한다.

    ⚠ **이것은 총량을 보증하지 않는다.** 예전 주석은 "총 음 수를 고정 스케줄과 같게 두므로
    총량 오염 없이 밀도 모양만 잰다"고 적었으나 **거짓이다.** 뒤이어 clip(0, n_max) 와
    Algorithm 1 의 slot 차감이 걸리므로 산출 총량은 안 맞는다 — 실측 361.5 → 424.6 (+17.2%)
    로 세 팔 중 오염이 가장 심하다. 그리고 이 지표는 총량과 corr = −0.869 로 강상관이라
    그 오염이 곧 개선폭의 실체다. (적대적 감사 2026-08-13)
    """
    act = om_bin.sum(axis=1).astype(float)
    lam = np.clip(a + b * act, 0.0, float(n_max))
    if match_total is not None and lam.sum() > 1e-9:
        lam = np.clip(lam * (match_total / lam.sum()), 0.0, float(n_max))
    n = rng.poisson(lam)
    return [int(min(n_max, v)) for v in n]


# ═══════════════════════════════════════════════════════════════════════════
# 2. 평가 지표
# ═══════════════════════════════════════════════════════════════════════════

def onset_counts(notes, T: int) -> np.ndarray:
    c = np.zeros(T)
    for s, _p, _e in notes:
        if 0 <= s < T:
            c[s] += 1
    return c


def count_hist_js(gen_counts: np.ndarray, real_counts: np.ndarray, n_max: int = N_MAX) -> float:
    """스텝당 onset 개수 **분포**가 원곡과 얼마나 닮았는가."""
    hg = np.bincount(gen_counts.astype(int).clip(0, n_max), minlength=n_max + 1).astype(float)
    hr = np.bincount(real_counts.astype(int).clip(0, n_max), minlength=n_max + 1).astype(float)
    return js_divergence_profiles(hg, hr)


def motif_density_ratio(counts: np.ndarray, mask: np.ndarray) -> float:
    """모티브 창 **안** 밀도 ÷ **밖** 밀도. 1.0 이면 모티브가 표면 밀도를 못 잡는다는 뜻."""
    inside = mask.any(axis=1)
    if inside.sum() == 0 or (~inside).sum() == 0:
        return float("nan")
    out = counts[~inside].mean()
    return float(counts[inside].mean() / out) if out > 0 else float("nan")


# ═══════════════════════════════════════════════════════════════════════════
# 3. 메인
# ═══════════════════════════════════════════════════════════════════════════

def bits(s: str, T: int, K: int) -> np.ndarray:
    return (np.frombuffer(s.encode("ascii"), dtype=np.uint8) == ord("1")).reshape(T, K)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    ap.add_argument("--temperature", type=float, default=3.0)
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t0 = time.time()
    print("=" * 80)
    print("스텝별 음 개수를 OM 이 정하게 — Gillespie τ-leaping vs 고정 스케줄")
    print("=" * 80)

    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]
    om_full = load_continuous_om()

    a, b, fit = fit_propensity(data, om_full)
    print(f"\n[적합] λ = {a:.3f} + {b:.3f}·활성합    R² = {fit['r2']:.4f}")
    print(f"       원곡 onset 평균 {fit['onset_mean_real']:.2f} · "
          f"적합 λ 평균 {fit['lambda_mean_fit']:.2f} · MODULES 평균 {fit['modules_mean']:.2f}")

    real_counts = onset_counts(orig_flat, om_full.shape[0])

    # 모티브 조건부 OM 재사용 (v1/v2 트랙)
    with open(MOTIF_RESULTS, encoding="utf-8") as f:
        mres = json.load(f)
    cases = [t for t in mres["tracks"] if t.get("role") in ("v1", "v2")]
    print(f"\n[대상] 모티브 조건부 OM {len(cases)}개 (T=240) × seed {args.n_seeds}개")

    results: Dict[str, dict] = {}
    for mode in ("modules_fixed", "tau_leaping", "tau_leaping_matched"):
        js_l, cons_l, cnt_js_l, ratio_l, n_l = [], [], [], [], []
        for tr in cases:
            T, K = tr["om_T"], tr["om_K"]
            om_b = bits(tr["om_bits"], T, K).astype(np.float32)
            mask = bits(tr["mask_bits"], T, K)
            for i in range(args.n_seeds):
                sd = 3000 + i * 13
                random.seed(sd); np.random.seed(sd)
                rng = np.random.default_rng(sd)
                base = (MODULES * (T // len(MODULES) + 2))[:T]
                if mode == "modules_fixed":
                    inst_len = base
                elif mode == "tau_leaping":
                    inst_len = tau_leap_inst_len(om_b, a, b, rng)
                else:   # tau_leaping_matched — 총량 고정, 모양만 OM 이 정함
                    inst_len = tau_leap_inst_len(om_b, a, b, rng,
                                                 match_total=float(sum(base)))
                pool = NodePool(data["notes_label"], data["notes_counts"],
                                num_modules=65, temperature=args.temperature)
                gen = algorithm1_optimized(pool, list(inst_len), om_b,
                                           CycleSetManager(cycle_labeled),
                                           max_resample=50, verbose=False, min_onset_gap=0)
                if not gen:
                    continue
                c = onset_counts(gen, T)
                js_l.append(pitch_distribution_similarity(gen, orig_flat)["js_divergence"])
                cons_l.append(consonance_score(gen))
                cnt_js_l.append(count_hist_js(c, real_counts))
                ratio_l.append(motif_density_ratio(c, mask))
                n_l.append(len(gen))
        results[mode] = {
            "pitch_js_mean": float(np.mean(js_l)), "pitch_js_std": float(np.std(js_l, ddof=1)),
            "consonance_mean": float(np.mean(cons_l)),
            "onset_hist_js_mean": float(np.mean(cnt_js_l)),
            "onset_hist_js_std": float(np.std(cnt_js_l, ddof=1)),
            "motif_density_ratio_mean": float(np.nanmean(ratio_l)),
            "motif_density_ratio_std": float(np.nanstd(ratio_l, ddof=1)),
            "n_notes_mean": float(np.mean(n_l)), "n": len(js_l),
            "_js": [float(v) for v in js_l], "_ratio": [float(v) for v in ratio_l],
            "_cnt": [float(v) for v in cnt_js_l],
        }
        r = results[mode]
        print(f"\n[{mode}]  n={r['n']}")
        print(f"   모티브 밀도비   {r['motif_density_ratio_mean']:.3f} ± "
              f"{r['motif_density_ratio_std']:.3f}   ← 1.0 이면 통제 실패")
        print(f"   onset 분포 JS   {r['onset_hist_js_mean']:.5f} ± {r['onset_hist_js_std']:.5f}"
              f"   ← 원곡 리듬 밀도 분포와의 거리")
        print(f"   음고 JS         {r['pitch_js_mean']:.5f} ± {r['pitch_js_std']:.5f}")
        print(f"   협화도          {r['consonance_mean']:.4f}   음 {r['n_notes_mean']:.0f}개")

    # ── 판정 ──
    m, g = results["modules_fixed"], results["tau_leaping_matched"]
    print(f"\n{'─'*80}")
    try:
        from scipy import stats
        def cmp(key, hi_is_good=False):
            p = stats.ttest_ind(m["_" + key], g["_" + key], equal_var=False).pvalue
            return p
        p_ratio = cmp("ratio"); p_cnt = cmp("cnt"); p_js = cmp("js")
    except Exception as e:
        p_ratio = p_cnt = p_js = float("nan")

    print(f"{'지표':<20}{'고정 스케줄':>14}{'τ-leaping':>14}{'변화':>12}{'Welch p':>11}")
    print(f"{'모티브 밀도비':<20}{m['motif_density_ratio_mean']:>14.3f}"
          f"{g['motif_density_ratio_mean']:>14.3f}"
          f"{(g['motif_density_ratio_mean']/m['motif_density_ratio_mean']-1)*100:>+11.1f}%"
          f"{p_ratio:>11.2e}")
    print(f"{'onset 분포 JS':<20}{m['onset_hist_js_mean']:>14.5f}{g['onset_hist_js_mean']:>14.5f}"
          f"{(g['onset_hist_js_mean']/m['onset_hist_js_mean']-1)*100:>+11.1f}%{p_cnt:>11.2e}")
    print(f"{'음고 JS':<20}{m['pitch_js_mean']:>14.5f}{g['pitch_js_mean']:>14.5f}"
          f"{(g['pitch_js_mean']/m['pitch_js_mean']-1)*100:>+11.1f}%{p_js:>11.2e}")
    print(f"{'협화도':<20}{m['consonance_mean']:>14.4f}{g['consonance_mean']:>14.4f}")

    # 원자료를 **버리지 않는다.** 예전엔 여기서 _js/_ratio/_cnt 를 pop 했는데,
    # 그 결과 보고된 p 값을 커밋된 아티팩트만으로 재검증할 수 없었다
    # (MEMORY.md 유형 H). 검정에 쓴 두 팔의 표본을 모두 남긴다.
    for k in list(results):
        for key in ("_js", "_ratio", "_cnt"):
            if key in results[k]:
                results[k][key.lstrip("_") + "_all"] = results[k].pop(key)
    payload = {"experiment": "gillespie_tau_leaping_onsets",
               "source_idea": "수리생물학/hw3 Exercise 3.6 (tau-leaping)",
               "propensity_fit": fit, "n_max": N_MAX,
               "config": {"n_seeds": args.n_seeds, "temperature": args.temperature,
                          "n_cases": len(cases)},
               "results": results,
               "p_values": {"motif_density_ratio": p_ratio, "onset_hist_js": p_cnt,
                            "pitch_js": p_js}}
    out = os.path.join(STEP3_DIR, "gillespie_onsets_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
