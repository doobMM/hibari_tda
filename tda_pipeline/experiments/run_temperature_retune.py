"""
run_temperature_retune.py — NodePool 인덱스 수정 후 온도를 다시 튜닝한다

왜 재튜닝이 필연인가
────────────────────
`temperature` 는 노드 풀의 **빈도 가중을 재조형**하는 파라미터다
(count → round(count^(1/T)), T 가 클수록 균등화).

그런데 그 빈도 가중이 바로 어긋나 있던 부분이다 — 2026-08-13 수정 전까지
풀은 1-indexed 인데 디코더는 0-indexed 여서, **음 X 의 등장빈도가 음 X+1 에 붙어**
있었다. §7.7.3 의 T=3.0 은 그 상태에서 정해진 값이다.

**사전 예측 (이 파일을 커밋한 시점에 기록한다)**
  T=3.0 은 강한 균등화다(빈도 차이를 뭉갠다). 가중이 엉뚱한 음에 붙어 있으면
  그 가중을 뭉개는 편이 유리하다. 따라서 T=3.0 은 오배선을 **보정하고 있었을** 가능성이
  크고, 제대로 배선되면 **최적 온도가 1.0 쪽으로 내려가야 한다.**
  → 맞으면 "왜 하필 3.0인가"가 설명된다. 틀리면 이 인과 해석이 틀린 것이다.
  어느 쪽이든 사후에 말을 바꾸지 않기 위해 예측을 먼저 적는다 (MEMORY.md 유형 D).

설계
────
  · 수정 전(1-indexed) / 후(0-indexed) **두 배선 모두**에서 같은 온도 그리드를 돈다.
    한쪽만 돌리면 "최적이 움직였다"를 말할 수 없다 (유형 L — 비교 대상이 있어야 한다).
  · 반복 단위는 **seed** 이고 모든 온도가 같은 seed 리스트를 공유하므로 **paired** 로 본다.
  · 지표는 음고 JS(주) + 협화도(부). 둘이 반대로 움직이는 것이 이 연구의 상수이므로
    둘 다 보고한다.

실행:  python experiments/run_temperature_retune.py [--n-seeds 20]
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

import numpy as np

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, load_continuous_om,
)

GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
PREDICTION = ("수정 후 최적 온도가 3.0 보다 낮아진다 (1.0 쪽으로 이동). "
              "T=3.0 이 인덱스 오배선을 보정하고 있었다는 가설.")


class OldPool(G.NodePool):
    """수정 전 배선 재현 — 풀을 1-indexed 로 되돌린다."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pool = self.pool + 1


def run(data, cycle_labeled, om, inst_len, seed, temperature, pool_cls):
    random.seed(seed)
    np.random.seed(seed)
    pool = pool_cls(data["notes_label"], data["notes_counts"],
                    num_modules=65, temperature=temperature)
    gen = G.algorithm1_optimized(pool, list(inst_len), om,
                                 G.CycleSetManager(cycle_labeled),
                                 max_resample=50, verbose=False, min_onset_gap=0)
    return gen, pool.decode_misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t0 = time.time()
    print("=" * 84)
    print("온도 재튜닝 — NodePool 인덱스 수정이 최적값을 옮겼는가")
    print(f"  사전 예측: {PREDICTION}")
    print("=" * 84)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]

    om = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    T = om.shape[0]
    inst_len = (MODULES * (T // len(MODULES) + 2))[:T]
    seeds = [1000 + 37 * i for i in range(args.n_seeds)]

    results = {}
    for wiring, cls in (("before_1indexed", OldPool), ("after_0indexed", G.NodePool)):
        print(f"\n[{wiring}]")
        print(f"  {'T':>5} {'음고 JS':>20} {'협화도':>18} {'음':>7} {'폐기':>6}")
        rows = {}
        for temp in GRID:
            js, cons, nn, miss = [], [], [], []
            for s in seeds:
                g, m = run(data, cycle_labeled, om, inst_len, s, temp, cls)
                if not g:
                    continue
                js.append(pitch_distribution_similarity(g, orig)["js_divergence"])
                cons.append(consonance_score(g))
                nn.append(len(g))
                miss.append(m)
            rows[temp] = {
                "js_mean": float(np.mean(js)), "js_std": float(np.std(js, ddof=1)),
                "consonance_mean": float(np.mean(cons)),
                "consonance_std": float(np.std(cons, ddof=1)),
                "n_notes_mean": float(np.mean(nn)),
                "decode_misses_mean": float(np.mean(miss)),
                "js_all": [float(v) for v in js],
            }
            r = rows[temp]
            print(f"  {temp:>5.1f} {r['js_mean']:>11.5f}±{r['js_std']:.5f} "
                  f"{r['consonance_mean']:>11.4f}±{r['consonance_std']:.4f} "
                  f"{r['n_notes_mean']:>7.0f} {r['decode_misses_mean']:>6.0f}")
        best = min(rows, key=lambda t: rows[t]["js_mean"])
        results[wiring] = {"grid": rows, "best_temperature": best,
                           "best_js": rows[best]["js_mean"]}
        print(f"  → 최적 T = {best}  (JS {rows[best]['js_mean']:.5f})")

    # ── 판정 ──
    b_before = results["before_1indexed"]["best_temperature"]
    b_after = results["after_0indexed"]["best_temperature"]
    print(f"\n{'─'*84}")
    print(f"최적 온도  수정 전 {b_before}  →  수정 후 {b_after}")
    moved_down = b_after < b_before
    print(f"예측('3.0 보다 낮아진다') 적중: {'예' if b_after < 3.0 else '아니오'}"
          f"   ·  이동 방향: {'하향' if moved_down else ('불변' if b_after == b_before else '상향')}")

    # 수정 후 배선에서 T=3.0 vs 새 최적이 실제로 다른가 (paired)
    try:
        from scipy import stats
        a = results["after_0indexed"]["grid"][3.0]["js_all"]
        b = results["after_0indexed"]["grid"][b_after]["js_all"]
        if b_after != 3.0:
            p = float(stats.ttest_rel(a, b).pvalue)
            print(f"수정 후 배선에서 T=3.0 vs T={b_after}: paired p = {p:.4f}"
                  f"  ({'유의' if p < 0.05 else '판별 불가'})")
            results["retune_significance"] = {"vs_T3_paired_p": p}
        else:
            print("수정 후에도 T=3.0 이 최적 — 재튜닝 불필요")
    except Exception as e:
        print(f"(검정 생략: {e})")

    payload = {
        "experiment": "temperature_retune_after_nodepool_fix",
        "prediction_registered_before_run": PREDICTION,
        "grid": GRID, "n_seeds": args.n_seeds,
        "config": {"T_steps": T, "om": "binary tau=0.5 full song", "min_onset_gap": 0},
        "results": results,
        "total_seconds": time.time() - t0,
    }
    out = os.path.join(STEP3_DIR, "temperature_retune_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
