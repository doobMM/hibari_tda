"""run_js_consonance_conflict.py — 음고 JS 를 목표로 삼는 것이 옳은가

동기
────
이 프로젝트는 거의 모든 판단을 **음고 Jensen-Shannon divergence** 로 내려 왔다.
그런데 오늘(2026-08-15) 같은 일이 반복해서 일어났다:

  · T12 12 모티브 트랙 재생성 — JS 평균 −44.5%, **12트랙 전부 협화도 하락**
  · NodePool 인덱스 수정      — JS −4.3%(p=0.008), 협화도 −1.22%(p=0.013)
  · T5 곡빈도 교집합 추출     — JS −6.2%(p=0.046), 협화도 −0.011(p=0.024)
                                → 블라인드 A/B 에서 **귀가 baseline 을 선택**
  · 2026-08-15 블라인드 A/B   — 지표 예측이 맞은 것은 **4쌍 중 1쌍**

즉 "JS 를 낮췄다"가 "더 나아졌다"를 뜻하지 않을 수 있다.
여기서 묻는 것은 하나다 — **JS 와 협화도는 체계적으로 충돌하는가?**

설계
────
같은 OM 안에서 seed 만 바꿔 후보를 여러 개 만들고, 후보들의 (JS, 협화도) 상관을 본다.
**OM 별로 따로 상관을 재고 그다음에 요약한다** — 전부 풀링하면 OM 정체성이 교란하고
유사반복(pseudoreplication)이 된다(이 프로젝트의 기존 교훈).

여러 OM 을 쓴다: 정본(per-cycle τ) · 이진 τ=0.5 · 모티브 OM 몇 개.
풀 경로 노출도(zero-row)가 서로 달라 일반화 범위가 넓어진다.

⚠ 한계를 먼저 적는다
  협화도 역시 **대리 지표**다. 이 실험이 답하는 것은 "두 대리 지표가 충돌하는가"이지
  "귀가 어느 쪽을 따르는가"가 아니다. 후자는 청취 실험만 답할 수 있다.
  다만 둘이 체계적으로 충돌한다면 **"JS 를 최적화한다"는 중립적 선택이 아니라
  협화도를 내주는 선택**이라는 뜻이고, 그 사실 자체가 결정에 필요하다.

실행:  python experiments/run_js_consonance_conflict.py [--n-seeds 40]
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

import numpy as np
from scipy import stats

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, consonance_score, load_continuous_om,
)


def candidates(data, om, cyc, orig, seeds):
    """같은 OM 에서 seed 만 바꿔 (JS, 협화도, 음 수) 를 모은다."""
    T = om.shape[0]
    inst = (MODULES * (T // len(MODULES) + 2))[:T]
    js, cons, n = [], [], []
    for s in seeds:
        suite.set_all_seeds(s)
        pool = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        g = G.algorithm1_optimized(pool, list(inst), om, G.CycleSetManager(cyc),
                                   max_resample=50, verbose=False, min_onset_gap=0)
        if not g:
            continue
        js.append(pitch_distribution_similarity(g, orig)["js_divergence"])
        cons.append(consonance_score(g))
        n.append(len(g))
    return np.array(js), np.array(cons), np.array(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=40)
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    t0 = time.time()

    print("=" * 92)
    print("음고 JS 를 목표로 삼는 것이 옳은가 — JS 와 협화도는 체계적으로 충돌하는가")
    print("=" * 92)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    cont = load_continuous_om()

    # 정본 per-cycle τ
    J = json.load(open(os.path.join(STEP3_DIR,
                  "percycle_tau_dft_gap0_alpha_grid_results.json"), encoding="utf-8"))
    tau = np.array([x for x in J["results"] if abs(x["alpha"] - 0.25) < 1e-9][0]["tau_profile"],
                   dtype=np.float32)

    oms = {"정본 per-cycle τ": (cont >= tau[None, :]).astype(np.float32),
           "이진 τ=0.5":       (cont >= REAL_TAU).astype(np.float32),
           "이진 τ=0.3":       (cont >= 0.3).astype(np.float32),
           "이진 τ=0.7":       (cont >= 0.7).astype(np.float32)}

    # 모티브 OM 도 섞는다 — 노출도가 훨씬 높다
    mp = os.path.join(STEP3_DIR, "motif_control_results.json")
    if os.path.exists(mp):
        tr = json.load(open(mp, encoding="utf-8"))["tracks"]
        for e in tr[:3]:
            T, Kk = int(e["om_T"]), int(e["om_K"])
            ob = (np.frombuffer(e["om_bits"].encode("ascii"), dtype=np.uint8) == ord("1")
                  ).reshape(T, Kk).astype(np.float32)
            oms[f"모티브 {e['track']}"] = ob

    seeds = [7000 + 13 * i for i in range(args.n_seeds)]
    print(f"\n{'OM':26} {'zero-row':>11} {'JS':>18} {'협화도':>18} {'r(JS,협화)':>11} {'p':>9}")
    rows, rs = [], []
    for name, om in oms.items():
        js, cons, n = candidates(data, om, cyc, orig, seeds)
        if len(js) < 5 or js.std() == 0 or cons.std() == 0:
            print(f"{name:26} 표본 부족 — 건너뜀"); continue
        r, p = stats.pearsonr(js, cons)
        zr = int((om.sum(1) == 0).sum())
        print(f"{name:26} {f'{zr}/{om.shape[0]}':>11} {js.mean():>10.5f}±{js.std(ddof=1):.5f} "
              f"{cons.mean():>10.4f}±{cons.std(ddof=1):.4f} {r:>11.3f} {p:>9.2e}")
        rows.append({"om": name, "zero_rows": zr, "T": int(om.shape[0]),
                     "js_mean": float(js.mean()), "js_std": float(js.std(ddof=1)),
                     "cons_mean": float(cons.mean()), "cons_std": float(cons.std(ddof=1)),
                     "pearson_r": float(r), "p": float(p), "n": int(len(js)),
                     "corr_js_notes": float(stats.pearsonr(js, n)[0]),
                     "corr_cons_notes": float(stats.pearsonr(cons, n)[0])})
        rs.append(r)

    print(f"\n{'─'*92}")
    rs = np.array(rs)
    neg = int((rs < 0).sum())
    # OM 별 상관을 표본으로 보는 1-표본 검정 (풀링하지 않는다)
    tt = stats.ttest_1samp(rs, 0.0)
    print(f"OM {len(rs)}개의 r: 평균 {rs.mean():+.3f} (범위 {rs.min():+.3f}~{rs.max():+.3f}) · "
          f"음수 {neg}/{len(rs)}")
    print(f"H0: 평균 r = 0  →  t={tt.statistic:+.2f} p={tt.pvalue:.4f}  "
          f"{'**체계적 충돌**' if tt.pvalue < 0.05 and rs.mean() < 0 else '판별 불가'}")

    print(f"\n※ 교란 확인 — 음 수가 두 지표를 동시에 움직이는가")
    for r_ in rows:
        print(f"  {r_['om']:26} r(JS,음수)={r_['corr_js_notes']:+.3f}  "
              f"r(협화,음수)={r_['corr_cons_notes']:+.3f}")

    out = {"experiment": "js_consonance_conflict",
           "question": "음고 JS 와 협화도는 체계적으로 충돌하는가",
           "design": ("같은 OM 안에서 seed 만 바꿔 후보를 만들고 OM 별로 상관을 잰 뒤 요약한다. "
                      "전부 풀링하면 OM 정체성 교란 + 유사반복이 된다."),
           "limitation": ("협화도도 대리 지표다. 이 결과는 '두 대리 지표가 충돌하는가' 에만 답하며 "
                          "'귀가 어느 쪽을 따르는가' 는 청취 실험만 답할 수 있다."),
           "n_seeds": args.n_seeds, "per_om": rows,
           "summary": {"mean_r": float(rs.mean()), "n_negative": neg, "n_om": len(rs),
                       "t": float(tt.statistic), "p": float(tt.pvalue)},
           "total_seconds": time.time() - t0}
    path = os.path.join(STEP3_DIR, "js_consonance_conflict.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
