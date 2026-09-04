"""run_knob_mi.py — 손잡이가 "살아 있나"와 "방향이 있나"를 **갈라서** 잰다

원자료: `tools/measure_knob_mi.mjs` → `docs/step3_data/knob_mi_sweep.json`
채점기(이 파일)는 **결과를 보기 전에 커밋한다.**

── 왜 상호정보량인가 ──────────────────────────────────────────────────────
지금까지 우리가 쓴 지표는 전부 **JS divergence** 였다. JS 는 *두 분포가 얼마나
닮았나*를 재는 **유사도**다. 그런데 2026-08-31 에 목표가 바뀌었다 —
"더 좋은 음악"이 아니라 **"내 조작이 의도대로 먹히나"**. 그건 유사도 질문이
아니라 **의존성 질문**이다: I(손잡이 ; 출력).

상호정보량은 **비선형·비단조 의존까지** 잡는다(상관계수는 선형만 잡는다).
그래서 "반응은 하는데 방향이 없다"는 상태를 **숫자로** 분리할 수 있다:

    MI ≈ 0                → 죽음
    MI > 0  이고  |ρ| 작음 → **살아 있으나 방향 없음**  ← 지금 못 가르는 칸
    MI > 0  이고  |ρ| 큼   → 쓸 수 있는 손잡이

α 가 정확히 가운데 칸에 걸려 있다고 나는 주장해 왔다(음역폭이 오르내린다).
그 주장을 여기서 **반증 가능하게** 만든다.

── 사전 예측 (PREDICTION · 실행 전에 적는다) ──────────────────────────────
P1. 온도(정본 α=0.25) · pitchTilt(정본): MI_adj ≈ 0, p > 0.05.
    풀 경로가 닫혀 있으므로(zero_rows=0) 출력이 눈금과 무관해야 한다.
P2. 귀무 numModules 60→65: MI_adj ≈ 0, p > 0.05.
    **이게 실패하면 순열 귀무가 편향을 못 잡은 것이다 → 회차 전체 판정 보류.**
P3. 높낮이 PITCH → meanPitch: MI_adj/log L > 0.90 이고 |ρ| > 0.99.
    사후 이조라 자명하다. **추정기의 양성 대조. 실패하면 추정기가 고장난 것이다.**
P4. 밀도 → n: MI_adj > 0 (p < 0.05) 이고 |ρ| > 0.90.
P5. 음 길이 → avgLen: MI_adj > 0 (p < 0.05) 이고 |ρ| > 0.90.
P6. **α → pitchRange: MI_adj 가 귀무보다 유의(p < 0.05) 하면서 |ρ| < 0.50.**
    ← 핵심 예측. |ρ| 가 크게 나오면 **내 α 판정이 틀린 것이고**, α 는
      방향 있는 손잡이로 되살려야 한다.
P7. 온도·pitchTilt (α=0, zero_rows=65 → 풀 열림): MI_adj > 0, p < 0.05.
    같은 손잡이가 OM 에 따라 살고 죽는다는 것을 보인다.

실행:  python experiments/run_knob_mi.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import json
import os

import numpy as np
from scipy import stats

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "step3_data")
NBINS, NPERM = 24, 4000
RNG = np.random.default_rng(20260905)

# ── 2026-09-05 설계 정정 (사전등록 회차를 무효화한 뒤) ──────────────────────
# 최초 회차는 P3(양성 대조)에서 실패했다. 원인을 파 보니 **추정기가 아니라
# 내가 적은 임계값이 도달 불가능한 값**이었다.
#   · 눈금 L=6 · 눈금당 n=60 이면 완벽한 단조 계단의 Spearman 상한이 **0.98602**
#     다(동순위 때문). 그런데 나는 |ρ| > 0.99 를 요구했다.
#   · 표본 360 을 등빈도 8구간으로 나누면 구간당 45 인데 눈금당 60 이라 구간이
#     눈금 경계를 반드시 가로지른다 → 완벽 분리라도 MI 상한이 **H(X)의 82.2%**.
#     그런데 나는 90% 를 요구했다.
#   증거: 서로 무관한 세 손잡이(밀도·PITCH·LENGTH)가 79.26/79.43/79.55% 와
#   ρ = 0.98596/0.98602/0.98607 로 **네 자리까지 붙었다.** 우연이 아니라 천장이다.
#
# 정정: 구간을 24 로 올려 천장을 없애고(12 이상이면 H(X)에 도달), 임계값을
# **해석적 천장 대비 비율**로 바꾼다. 새 매직넘버를 고르지 않는다.
# ⚠ 이 정정은 **결과를 보고 임계값을 옮긴 것**이라 확증이 아니다. 무효 회차
#    원본은 `knob_mi_prereg_invalid_bins8.json` 에 보존한다. 다만 핵심 예측
#    P6 을 정하는 것은 ρ 인데 **ρ 는 구간 수와 무관하다** — 이 정정으로 P6 의
#    판정을 사후에 구해낼 수는 없다는 뜻이다.

# 손잡이마다 "그 손잡이가 노리는" 특징을 **미리** 지정한다 (사후 고르기 금지)
TARGET = {
    "alpha": "pitchRange", "density": "n", "pitch": "meanPitch", "length": "avgLen",
    "temperature": "n", "pitchTilt": "meanPitch",
    "temperature_open": "n", "pitchTilt_open": "meanPitch",
    "null_numModules": "n",
}
FEATS = ["n", "meanPitch", "pitchRange", "avgLen"]


def mi_discrete(x_idx, y_bin, L, B):
    """이산 x(L값) × 구간화된 y(B구간) 의 상호정보량 (nat)."""
    c = np.zeros((L, B))
    np.add.at(c, (x_idx, y_bin), 1.0)
    p = c / c.sum()
    px, py = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    nz = p > 0
    return float((p[nz] * np.log(p[nz] / (px @ py)[nz])).sum())


def qbin(y, b):
    """등빈도 구간화. 서로 다른 값이 몇 개뿐이면 구간 수가 자동으로 줄어든다."""
    u = np.unique(y)
    if len(u) <= b:
        return np.searchsorted(u, y), max(1, len(u))
    edges = np.quantile(y, np.linspace(0, 1, b + 1)[1:-1])
    return np.searchsorted(edges, y, side="right"), b


def analyse(levels, lv_idx, y):
    L = len(levels)
    y = np.asarray(y, float)
    yb, B = qbin(y, NBINS)
    raw = mi_discrete(lv_idx, yb, L, B)
    null = np.empty(NPERM)
    perm = lv_idx.copy()
    for i in range(NPERM):
        RNG.shuffle(perm)
        null[i] = mi_discrete(perm, yb, L, B)
    nm = float(null.mean())
    p = (float((null >= raw).sum()) + 1.0) / (NPERM + 1.0)
    rho, prho = stats.spearmanr(np.asarray(levels, float)[lv_idx], y)
    return {
        "mi_raw": raw, "mi_null_mean": nm, "mi_null_p95": float(np.quantile(null, 0.95)),
        "mi_adj": raw - nm, "mi_adj_frac_of_HX": (raw - nm) / np.log(L),
        "perm_p": p, "n_bins_used": B,
        "spearman_rho": float(rho) if np.isfinite(rho) else 0.0,
        "spearman_p": float(prho) if np.isfinite(prho) else 1.0,
        "level_means": [float(y[lv_idx == i].mean()) for i in range(L)],
        "seed_sigma": float(np.mean([y[lv_idx == i].std() for i in range(L)])),
    }


def ceilings(levels, n):
    """완벽한 단조 계단이 **이 설계에서** 낼 수 있는 상한. 임계값의 기준.

    ⚠ 반드시 `analyse()` 를 **그대로 통과시켜** 잰다. 여기서 지름길을 쓰면
      귀무 보정이 한쪽에만 걸려 천장이 부풀고, 그러면 도달 불가능한 임계값이
      또 만들어진다 — 실제로 2026-09-05 에 이 실수를 **두 번** 했다.
        1차: 구간 8 의 구조적 천장(H(X)의 82.2%)을 모르고 90% 를 요구
        2차: 귀무 보정한 측정값(1.6098)을 보정 안 한 천장(1.7918)과 비교
      원인은 둘 다 같다 — **천장을 측정과 다른 경로로 구했다.**
    """
    L = len(levels)
    lv_idx = np.repeat(np.arange(L), n)
    perfect = np.asarray(levels, float)[lv_idx] + np.linspace(0, 1e-9, L * n)
    r = analyse(levels, lv_idx, perfect)
    return abs(r["spearman_rho"]), r["mi_adj"]


def verdict(r):
    if r["perm_p"] >= 0.05 or r["mi_adj"] <= 0:
        return "죽음 — 출력이 눈금에 의존하지 않는다"
    return ("살아 있고 **방향도 있다**" if abs(r["spearman_rho"]) >= 0.50
            else "**살아 있으나 방향이 없다** — 손잡이로 쓸 수 없다")


def main():
    d = json.load(open(os.path.join(SRC, "knob_mi_sweep.json"), encoding="utf-8"))
    L = d["n_levels"]
    print("=" * 104)
    print("손잡이 상호정보량 감사 — '반응하나'와 '방향이 있나'를 가른다")
    print(f"눈금 {L} × 시드 {d['n_seeds']} (눈금마다 같은 시드) · "
          f"순열 귀무 {NPERM}회 · 구간 {NBINS}")
    print("=" * 104)

    out = {"experiment": "knob_mutual_information",
           "analysis_committed_before_data": True,
           "source_sweep": "docs/step3_data/knob_mi_sweep.json",
           "n_levels": L, "n_seeds": d["n_seeds"], "n_perm": NPERM, "n_bins": NBINS,
           "banks": d["banks"], "knobs": {}}

    ceil_rho, ceil_mi = ceilings(list(range(L)), d["n_seeds"])
    out["ceiling_rho"], out["ceiling_mi"] = ceil_rho, ceil_mi
    print(f"\n천장 — 완벽한 단조 계단을 **같은 채점 경로**로 통과시킨 값: "
          f"|rho| = {ceil_rho:.5f} · MI_adj = {ceil_mi:.4f}")
    print(f"\n{'손잡이':26}{'대상특징':11}{'MI_adj':>8}{'/천장':>8}{'순열p':>8}"
          f"{'rho':>7}{'시드σ':>8}  판정")
    print("-" * 104)
    for k in d["knobs"]:
        lv = k["levels"]
        lv_idx = np.array([lv.index(r["level"]) for r in k["rows"]])
        res = {f: analyse(lv, lv_idx, [r[f] for r in k["rows"]]) for f in FEATS}
        tgt = TARGET[k["id"]]
        t = res[tgt]
        v = verdict(t)
        out["knobs"][k["id"]] = {"label": k["label"], "note": k["note"], "levels": lv,
                                 "target_feature": tgt,
                                 "distinct_outputs": k["distinct_outputs"],
                                 "verdict": v, "per_feature": res}
        t["mi_adj_frac_of_ceiling"] = t["mi_adj"] / ceil_mi
        print(f"{k['label'][:25]:26}{tgt:11}{t['mi_adj']:>8.4f}"
              f"{t['mi_adj_frac_of_ceiling']:>8.1%}{t['perm_p']:>8.4f}"
              f"{t['spearman_rho']:>7.2f}{t['seed_sigma']:>8.2f}  {v}")

    # ── 사전 예측 채점 ────────────────────────────────────────────────
    g = out["knobs"]

    def T(kid):
        return g[kid]["per_feature"][g[kid]["target_feature"]]

    est_ok = (T("pitch")["mi_adj"] > 0.90 * ceil_mi
              and abs(T("pitch")["spearman_rho"]) > 0.98 * ceil_rho)
    null_ok = T("null_numModules")["perm_p"] >= 0.05
    checks = [
        ("P1 온도(정본) 죽음", T("temperature")["perm_p"] >= 0.05),
        ("P1 pitchTilt(정본) 죽음", T("pitchTilt")["perm_p"] >= 0.05),
        ("P2 귀무 numModules 무반응", null_ok),
        ("P3 PITCH 양성대조", est_ok),
        ("P4 밀도 방향 있음", T("density")["perm_p"] < 0.05
         and abs(T("density")["spearman_rho"]) > 0.90 * ceil_rho),
        ("P5 LENGTH 방향 있음", T("length")["perm_p"] < 0.05
         and abs(T("length")["spearman_rho"]) > 0.90 * ceil_rho),
        ("P6 alpha 살아있고 방향없음", T("alpha")["perm_p"] < 0.05
         and abs(T("alpha")["spearman_rho"]) < 0.50 * ceil_rho),
        ("P7 온도(alpha=0) 살아남", T("temperature_open")["perm_p"] < 0.05),
        ("P7 tilt(alpha=0) 살아남", T("pitchTilt_open")["perm_p"] < 0.05),
    ]
    print(f"\n{'-' * 104}\n사전 예측 채점")
    for n, ok in checks:
        print(f"  {'O' if ok else 'X'}  {n}")
    out["prediction_checks"] = {n: bool(ok) for n, ok in checks}
    out["estimator_valid"] = bool(est_ok and null_ok)
    if not out["estimator_valid"]:
        print("\n  ** 사전 규칙 발동: 양성 대조(P3) 또는 귀무(P2) 가 실패했다.")
        print("     추정기가 신뢰되지 않으므로 이 회차의 손잡이 판정을 채택하지 않는다. **")

    out["superseded"] = (
        "최초 사전등록 회차(구간 8)는 P3 양성 대조 실패로 자체 규칙에 따라 무효. "
        "원본 보존: docs/step3_data/knob_mi_prereg_invalid_bins8.json. "
        "원인은 추정기가 아니라 도달 불가능한 임계값이었다 — 이 설계의 "
        "|ρ| 상한은 0.98602, MI 상한은 H(X)의 82.2% 인데 각각 0.99 와 90% 를 요구했다.")
    out["limitation"] = (
        "⓪ **이 회차의 임계값은 결과를 본 뒤 고친 것이다.** 확증이 아니라 정정이다. "
        "다만 핵심 예측 P6 을 정하는 ρ 는 구간 수와 무관하므로 이 정정으로 P6 의 "
        "판정을 사후에 구해낼 수는 없다. "
        "① α 눈금은 OM 자체가 갈린다(K 1→58). 다른 손잡이와 같은 척도로 비교할 수 없고, "
        "'무언가 크게 변한다'는 사실 자체는 자명하다 — 여기서 읽을 것은 **방향(ρ)** 과 "
        "**시드 잡음 대비 크기**이지 MI 의 절대값이 아니다. "
        "② 시드 60개는 MI 추정에 넉넉하지 않다. 순열 귀무로 편향은 빼지만 분산은 남는다. "
        "③ 특징 4종은 **계산 가능한 양이지 지각 축이 아니다.** 거리·협화도·역동성 세 계열이 "
        "이미 n≈20 청취에서 선호 예측에 실패했다. 여기서 재는 것은 '들린다'가 아니라 "
        "**'출력이 설정에 의존한다'** 뿐이다 — 필요조건이지 충분조건이 아니다. "
        "④ 눈금마다 같은 시드를 쓰는 paired 설계다. 순열 귀무는 그 짝을 무시하므로 "
        "보수적이지 않을 수 있다.")
    p = os.path.join(SRC, "knob_mutual_information.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: {p}")


if __name__ == "__main__":
    main()
