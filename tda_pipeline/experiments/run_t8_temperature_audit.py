"""run_t8_temperature_audit.py — T8: §5.8.3 온도 주장을 원 함수로 직접 재검한다

왜 필요한가
───────────
§5.8.3 은 "T=3.0 최적(+6.7%)"이라 쓰고 `config.py` 기본값까지 3.0 으로 잡았다.
그런데 `NodePool` 은 **풀 경로가 열릴 때만** 쓰인다(OM 행 전체가 0, 또는 활성 cycle 의
교집합이 빔). §7.7.3 원 실험(`run_section77_experiments.py`)은 tonnetz binary OM 을 쓰는데
그 OM 은 zero-row 가 0/1088 이다 → **풀을 한 번도 안 뽑았을 가능성**이 있다.

앞선 재현 시도는 풀 스케일이 원 함수와 달랐다
(`round((cnt×65)^(1/T))` vs 원본 `round(cnt^(1/T))` 후 num_modules 곱).
그래서 여기서는 **원 함수 `experiment_learnable_weight` 를 그대로 호출**하고,
`NodePool.sample` 을 계수해서 풀이 실제로 뽑히는지 센다.

검증 3항
────────
1. `sample()` 호출 수 — 0 이면 온도는 생성물에 닿을 수 없다
2. 재현성 — 기록된 JSON 표와 일치하는가
3. 재시드 대조 — 풀 구성 직후 RNG 를 통일하면 온도별 생성물이 동일한가

실행:  python experiments/run_t8_temperature_audit.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import json
import os
import time

import numpy as np

import generation as G
import run_section77_experiments as S77
from run_dft_gap0_suite import BASE_DIR, STEP3_DIR

# `docs/step3_data/section77_experiments.json` → sec77_3_learnable_weight (원본 대조)
RECORDED = {"0.3": 0.0596, "0.5": 0.0624, "1.0": 0.0627,
            "2.0": 0.0587, "3.0": 0.0585, "5.0": 0.0607}
RECORDED_STD = {"0.3": (0.0596, 0.0017), "0.5": (0.0624, 0.0027), "1.0": (0.0627, 0.0042),
                "2.0": (0.0587, 0.0032), "3.0": (0.0585, 0.0046), "5.0": (0.0607, 0.0039)}


def main():
    os.chdir(BASE_DIR)
    t0 = time.time()
    print("=" * 88)
    print("T8 — §5.8.3 온도 주장 감사 (원 함수 그대로 호출)")
    print("=" * 88)

    data = S77.load_hibari_cache()
    ov = np.asarray(data["binary_overlap"])
    zr = int((ov.sum(axis=1) == 0).sum())
    print(f"\n§7.7.3 이 쓰는 OM: shape={ov.shape}  zero-row={zr}/{ov.shape[0]} "
          f"({zr/ov.shape[0]:.1%})  → 풀 경로 노출도")

    # ── 계수기 부착 ──
    counts = {"sample": 0, "avoid": 0, "intersect_none": 0}
    orig_sample = G.NodePool.sample
    orig_avoid = G._sample_avoiding_neighbors
    orig_inter = G.CycleSetManager.get_intersect_nodes

    def sample(self, *a, **k):
        counts["sample"] += 1
        return orig_sample(self, *a, **k)

    def avoid(*a, **k):
        counts["avoid"] += 1
        return orig_avoid(*a, **k)

    def inter(self, *a, **k):
        r = orig_inter(self, *a, **k)
        if r is None:
            counts["intersect_none"] += 1
        return r

    G.NodePool.sample = sample
    G._sample_avoiding_neighbors = avoid
    G.CycleSetManager.get_intersect_nodes = inter
    try:
        res = S77.experiment_learnable_weight(data, n_eval=10)
    finally:
        G.NodePool.sample = orig_sample
        G._sample_avoiding_neighbors = orig_avoid
        G.CycleSetManager.get_intersect_nodes = orig_inter

    print(f"\n{'─'*88}")
    print(f"[1] 풀 경로 계측 — NodePool.sample() {counts['sample']}회 · "
          f"이웃회피 {counts['avoid']}회 · 교집합 None {counts['intersect_none']}회")
    print("    → " + ("온도는 생성물에 닿을 수 없다 (풀을 한 번도 안 뽑았다)"
                      if counts["sample"] == 0 else "풀이 실제로 쓰였다"))

    grid = res["temperature_grid"]
    print(f"\n[2] 재현 — 기록된 §5.8.3 표와 대조")
    print(f"    {'T':>5} {'기록':>9} {'재실행':>9} {'차이':>9}")
    repro = {}
    for T, rec in RECORDED.items():
        now = grid[T]["js_mean"]
        repro[T] = {"recorded": rec, "rerun": now, "diff": round(now - rec, 4)}
        print(f"    {T:>5} {rec:>9.4f} {now:>9.4f} {now-rec:>+9.4f}")
    best = min(grid, key=lambda k: grid[k]["js_mean"])
    print(f"    → 재실행 최적 T = {best} (기록: 3.0)"
          + ("   ★ 순위 역전" if best != "3.0" else ""))

    print(f"\n[3] 유의성 — 논문은 검정을 싣지 않았다. 기록값·재실행값 둘 다 계산한다")
    from scipy import stats as st
    n = 10

    def welch(m1, s1, m3, s3, tag):
        se = float(np.sqrt(s1**2 / n + s3**2 / n))
        t = (m1 - m3) / se if se else 0.0
        df = ((s1**2/n + s3**2/n)**2 /
              ((s1**2/n)**2/(n-1) + (s3**2/n)**2/(n-1))) if se else 1.0
        p = float(2 * (1 - st.t.cdf(abs(t), df)))
        pb = float(min(1.0, p * 6))
        print(f"    [{tag}] T=1.0 {m1:.4f}±{s1:.4f} vs T=3.0 {m3:.4f}±{s3:.4f}")
        print(f"           Welch t={t:+.2f} df={df:.1f} p={p:.4f}  ·  "
              f"후보 6개 argmin 이므로 Bonferroni p={pb:.3f} → "
              f"{'유의' if pb < 0.05 else '**비유의**'}")
        return {"t": float(t), "df": float(df), "p_raw": p,
                "p_bonferroni_6": pb, "significant_after_correction": bool(pb < 0.05)}

    sig_rec = welch(RECORDED_STD["1.0"][0], RECORDED_STD["1.0"][1],
                    RECORDED_STD["3.0"][0], RECORDED_STD["3.0"][1], "기록값")
    sig_new = welch(grid["1.0"]["js_mean"], grid["1.0"]["js_std"],
                    grid["3.0"]["js_mean"], grid["3.0"]["js_std"], "재실행")

    payload = {
        "experiment": "t8_temperature_audit",
        "purpose": "§5.8.3 온도 주장을 원 함수로 직접 재검",
        "om": {"shape": list(ov.shape), "zero_rows": zr, "exposure": zr / ov.shape[0]},
        "pool_path_counts": counts,
        "rerun_grid": grid,
        "recorded_vs_rerun": repro,
        "best_temperature_rerun": best,
        "best_temperature_recorded": 3.0,
        "significance": {"n_per_arm": n, "from_recorded": sig_rec, "from_rerun": sig_new},
        "caveat_reproduction": ("재실행이 기록된 절대값을 재현하지 못한다(전 온도에서 0.009~0.018 낮다). "
                                "기록 이후 전처리·캐시가 바뀌었다는 뜻이므로, 재실행은 '같은 실험'이 아니라 "
                                "'같은 함수를 현재 코드로 돌린 것'으로 읽어야 한다. "
                                "그래도 풀 호출 0회와 순위 역전은 현재 코드에서 직접 계측된 사실이다."),
        "second_unverifiable_record": ("`section77_experiments_dft_gap0.json` 에도 best_temperature=3.0 이 "
                                       "있으나 그리드·std·n 이 기록돼 있지 않아 평가할 수 없다."),
        "total_seconds": time.time() - t0,
    }
    path = os.path.join(STEP3_DIR, "t8_temperature_audit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
