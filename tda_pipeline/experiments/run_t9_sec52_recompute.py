"""run_t9_sec52_recompute.py — T9 후반: §5.2 일반화 표를 NodePool 수정 후로 재산출

§4.1 재산출(`run_t9_nodepool_recompute.py`)에서 확인된 것:
**OM 의 zero-row 비율이 효과 크기를 그대로 예측한다** — 70%→−28.3%, 8%→+1.7%(비유의),
5%→−6.7%, 0%→비트 동일. 조사 메모는 solari/aqua 가 50~65% 라고 보고했으므로
§5.2 표는 크게 움직일 수 있다.

설계는 §4.1 과 같다 — **같은 시드로 두 배선을 모두 실행하는 paired 비교**.
곡별 PH 캐시가 없어 재계산이 필요하므로 오래 걸린다(Bach 는 N=61).

실행:  python experiments/run_t9_sec52_recompute.py [--n-seeds 20]
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os
import random
import time

import numpy as np
from scipy import stats

import generation as G
import run_any_track as RA
from eval_metrics import evaluate_generation
from run_t9_nodepool_recompute import OldPool

TRACKS = [
    ("solari", "ryuichi-sakamoto-solari.mid"),
    ("aqua",   "aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid"),
    ("ravel_pavane", "maurice-ravel-pavane-pour-une-infante-defunte-m-19.mid"),
    ("bach_fugue",   "bach-toccata-and-fugue-in-d-minor-piano-solo.mid"),
]
METRICS = ["frequency", "tonnetz", "voice_leading", "dft"]
# 논문 §5.2 표 (수정 전 값). 재현 검증용.
PUBLISHED = {
    "solari":       {"frequency": 0.0634, "tonnetz": 0.0632, "voice_leading": 0.0775, "dft": 0.0824},
    "ravel_pavane": {"frequency": 0.0337, "tonnetz": 0.0415, "voice_leading": 0.0798, "dft": 0.0494},
    "bach_fugue":   {"frequency": 0.0902, "tonnetz": 0.0417, "voice_leading": 0.1242, "dft": 0.0951},
}


def trials(data, ov, cl, n, pool_cls, seed_base=9700):
    hp = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
          4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    T = len(ov)
    h = (hp * (T // 32 + 1))[:T]
    js, sig = [], []
    for i in range(n):
        random.seed(seed_base + i); np.random.seed(seed_base + i)
        pool = pool_cls(data["notes_label"], data["notes_counts"], num_modules=65)
        gen = G.algorithm1_optimized(pool, h, ov, G.CycleSetManager(cl), max_resample=50)
        m = evaluate_generation(gen, [data["inst1"], data["inst2"]], data["notes_label"], name="")
        js.append(float(m["js_divergence"]))
        sig.append(hash(tuple(map(tuple, gen))))
    return np.array(js), sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    t0 = time.time()

    print("=" * 100)
    print("T9 후반 — §5.2 일반화 표 재산출 (같은 시드, paired)")
    print("=" * 100)

    out = {"experiment": "t9_nodepool_recompute_sec52", "n_seeds": args.n_seeds, "tracks": {}}
    for name, midi in TRACKS:
        if not os.path.exists(midi):
            print(f"\n[{name}] MIDI 없음: {midi} — 건너뜀")
            continue
        print(f"\n[{name}] {midi}")
        data = RA.preprocess(midi)
        print(f"  T={data['T']} N={data['N']} C={data['num_chords']}")
        out["tracks"][name] = {"T": data["T"], "N": data["N"], "metrics": {}}
        print(f"  {'metric':14} {'K':>4} {'zero-row':>13} {'수정 전':>10} {'수정 후':>10} "
              f"{'Δ%':>8} {'p':>10} {'동일':>6}")
        for metric in METRICS:
            try:
                cl, ov, n_cyc, ph_t = RA.compute_ph(data, metric)
            except Exception as e:
                print(f"  {metric:14} PH 실패: {e}")
                out["tracks"][name]["metrics"][metric] = {"error": str(e)}
                continue
            if cl is None:
                print(f"  {metric:14} cycle 없음")
                out["tracks"][name]["metrics"][metric] = {"n_cycles": 0}
                continue
            arr = np.asarray(ov)
            zr = int((arr.sum(axis=1) == 0).sum())
            T = arr.shape[0]
            b, sb = trials(data, ov, cl, args.n_seeds, OldPool)
            a, sa = trials(data, ov, cl, args.n_seeds, G.NodePool)
            same = sum(x == y for x, y in zip(sb, sa))
            dp = 100 * (a.mean() - b.mean()) / b.mean()
            p = float(stats.ttest_rel(a, b).pvalue) if same < args.n_seeds else 1.0
            pub = PUBLISHED.get(name, {}).get(metric)
            print(f"  {metric:14} {n_cyc:>4} {f'{zr}/{T} ({zr/T:.0%})':>13} "
                  f"{b.mean():>10.4f} {a.mean():>10.4f} {dp:>+7.1f}% {p:>10.2e} "
                  f"{f'{same}/{args.n_seeds}':>6}"
                  + (f"   논문 {pub:.4f}" if pub else ""))
            out["tracks"][name]["metrics"][metric] = {
                "K": n_cyc, "zero_rows": zr, "T": T, "exposure": zr / T,
                "ph_time_s": round(ph_t, 1), "published_js": pub,
                "before": {"js_mean": float(b.mean()), "js_std": float(b.std(ddof=1))},
                "after": {"js_mean": float(a.mean()), "js_std": float(a.std(ddof=1))},
                "delta_pct": float(dp), "paired_p": p, "identical_runs": int(same),
                "js_all_before": [float(x) for x in b], "js_all_after": [float(x) for x in a],
            }
        # 최적 거리 함수가 바뀌었는가
        ms = {k: v for k, v in out["tracks"][name]["metrics"].items() if "after" in v}
        if ms:
            bb = min(ms, key=lambda k: ms[k]["before"]["js_mean"])
            ba = min(ms, key=lambda k: ms[k]["after"]["js_mean"])
            out["tracks"][name]["best_before"] = bb
            out["tracks"][name]["best_after"] = ba
            print(f"  → 최적 거리: {bb} → {ba}" + ("  ★ 순위 역전" if bb != ba else "  (유지)"))

    out["total_seconds"] = time.time() - t0
    path = os.path.join("docs", "step3_data", "t9_nodepool_recompute_sec52.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
