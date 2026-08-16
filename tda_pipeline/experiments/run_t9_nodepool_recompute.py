"""run_t9_nodepool_recompute.py — T9: NodePool 수정이 §4.1 · §5.2 를 바꾸는가

배경
────
`fcf929f` 가 `NodePool` 인덱스 규약을 1-indexed → 0-indexed 로 고쳤다.
이 버그는 **풀 경로가 열리는 설정에서만** 영향을 준다 —
풀은 OM 행이 전부 0(`flag==0`)이거나 활성 cycle 의 교집합이 빌 때만 쓰인다.
따라서 **OM 의 zero-row 수 = 노출도**다.

정본(per-cycle τ, zero-row 0/1088)과 Algorithm 2 는 무영향이라 이미 확인됐다.
남은 것이 §4.1(거리 함수 비교)과 §5.2(일반화)다 — frequency 는 K=1 이라 zero-row 가 많고,
solari/aqua 도 50~65% 로 알려져 있다.

설계 — 왜 paired 인가
─────────────────────
조사 메모는 "DFT 쪽 변화량은 시드 스트림마다 부호가 흔들려 **판별 불가**가 정확"이라고
경고했다. 수정 전 결과(2026-04-17)와 수정 후를 **다른 실행끼리** 비교하면
버그 효과와 시드 노이즈가 섞이기 때문이다.

→ 여기서는 **같은 시드로 두 배선을 모두 돌린다**(`OldPool` 은 풀을 1-indexed 로 되돌린 서브클래스).
  paired 차이는 오직 배선 차이다. 노출도가 0 인 metric 은 **비트 단위로 동일**해야 하고,
  그 자체가 이 하네스의 검증이 된다.

실행:  python experiments/run_t9_nodepool_recompute.py [--n-seeds 20]
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os
import time

import numpy as np
from scipy import stats

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import evaluate_generation

METRICS = ["frequency", "tonnetz", "voice_leading", "dft"]
PUBLISHED = {"frequency": 0.0344, "tonnetz": 0.0493, "voice_leading": 0.0566, "dft": 0.0213}


class OldPool(G.NodePool):
    """수정 전 배선 — 풀을 1-indexed 로 되돌린다."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pool = self.pool + 1


def trials(data, overlap, cycle_labeled, n, seed_base, pool_cls):
    js, cov, nn, miss, sig = [], [], [], [], []
    for i in range(n):
        suite.set_all_seeds(seed_base + i)
        pool = pool_cls(data["notes_label"], data["notes_counts"], num_modules=65)
        gen = G.algorithm1_optimized(pool, suite.INST_CHORD_HEIGHTS, overlap,
                                     G.CycleSetManager(cycle_labeled),
                                     max_resample=50, verbose=False,
                                     min_onset_gap=suite.MIN_ONSET_GAP)
        m = evaluate_generation(gen, [data["inst1_real"], data["inst2_real"]],
                                data["notes_label"], name="")
        js.append(m["js_divergence"]); cov.append(m["note_coverage"]); nn.append(len(gen))
        miss.append(getattr(pool, "decode_misses", 0))
        sig.append(hash(tuple(map(tuple, gen))))
    return {"js": np.array(js), "cov": np.array(cov), "n": np.array(nn),
            "misses": np.array(miss), "sig": sig}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    t0 = time.time()

    print("=" * 92)
    print("T9 — NodePool 인덱스 수정이 §4.1 을 바꾸는가 (같은 시드, paired)")
    print("=" * 92)
    data = suite.setup_hibari()

    out = {"experiment": "t9_nodepool_recompute_sec41",
           "design": ("같은 시드로 수정 전(1-indexed) / 후(0-indexed) 두 배선을 모두 실행한 paired 비교. "
                      "노출도(zero-row)가 0 인 metric 은 비트 단위로 동일해야 하며 그것이 하네스 검증이다."),
           "n_seeds": args.n_seeds, "metrics": {}}

    print(f"\n{'metric':14} {'K':>4} {'zero-row':>12} {'수정 전 JS':>18} {'수정 후 JS':>18} "
          f"{'Δ%':>8} {'p':>10} {'동일':>6}")
    for idx, metric in enumerate(METRICS):
        cache = suite.load_metric_cache(metric)
        ov = cache["overlap"]
        overlap = ov.values if hasattr(ov, "values") else ov
        cyc = cache["cycle_labeled"]
        zr = int((np.asarray(overlap).sum(axis=1) == 0).sum())
        T = overlap.shape[0]

        before = trials(data, overlap, cyc, args.n_seeds, 1000 + idx * 100, OldPool)
        after = trials(data, overlap, cyc, args.n_seeds, 1000 + idx * 100, G.NodePool)
        same = sum(a == b for a, b in zip(before["sig"], after["sig"]))
        d_pct = 100 * (after["js"].mean() - before["js"].mean()) / before["js"].mean()
        p = float(stats.ttest_rel(after["js"], before["js"]).pvalue) if same < args.n_seeds else 1.0

        print(f"{metric:14} {len(cyc):>4} {f'{zr}/{T} ({zr/T:.0%})':>12} "
              f"{before['js'].mean():>10.5f}±{before['js'].std(ddof=1):.5f} "
              f"{after['js'].mean():>10.5f}±{after['js'].std(ddof=1):.5f} "
              f"{d_pct:>+7.1f}% {p:>10.2e} {f'{same}/{args.n_seeds}':>6}")

        out["metrics"][metric] = {
            "K": len(cyc), "zero_rows": zr, "T": T, "exposure": zr / T,
            "published_js": PUBLISHED[metric],
            "before": {"js_mean": float(before["js"].mean()), "js_std": float(before["js"].std(ddof=1)),
                       "coverage": float(before["cov"].mean()), "n_notes": float(before["n"].mean()),
                       "decode_misses": float(before["misses"].mean())},
            "after": {"js_mean": float(after["js"].mean()), "js_std": float(after["js"].std(ddof=1)),
                      "coverage": float(after["cov"].mean()), "n_notes": float(after["n"].mean()),
                      "decode_misses": float(after["misses"].mean())},
            "delta_pct": float(d_pct), "paired_p": p,
            "identical_runs": int(same),
            "js_all_before": [float(x) for x in before["js"]],
            "js_all_after": [float(x) for x in after["js"]],
        }

    # ── 하네스 검증 ──
    print(f"\n{'─'*92}\n검증")
    for m, r in out["metrics"].items():
        pub, rep = r["published_js"], r["before"]["js_mean"]
        ok = abs(rep - pub) < 0.0005
        print(f"  {m:14} 논문값 {pub:.4f} vs 수정 전 재현 {rep:.5f}  "
              f"{'일치' if ok else '★ 불일치 — 조건이 다르다'}")
        r["reproduces_published"] = bool(ok)
        if r["exposure"] == 0 and r["identical_runs"] != args.n_seeds:
            print(f"  ⚠ {m}: 노출도 0 인데 생성물이 다르다 — 하네스 오류")

    # ── 논문 표 갱신용 요약 ──
    print(f"\n{'─'*92}\n§4.1 표 갱신 (수정 후)")
    freq = out["metrics"]["frequency"]["after"]["js_mean"]
    for m in METRICS:
        a = out["metrics"][m]["after"]
        imp = 100 * (freq - a["js_mean"]) / freq
        print(f"  {m:14} JS {a['js_mean']:.4f} ± {out['metrics'][m]['after']['js_std']:.4f}  "
              f"coverage {a['coverage']:.3f}  vs frequency {imp:+.1f}%")
        out["metrics"][m]["improvement_vs_frequency_pct_after"] = float(imp)

    out["total_seconds"] = time.time() - t0
    path = os.path.join(suite.STEP3_DIR, "t9_nodepool_recompute_sec41.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
