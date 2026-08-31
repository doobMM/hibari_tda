"""run_dynamism_metrics.py — 사전등록한 역동성 지표 4종을 구현하고 상한을 확인한다

사전등록: `docs/step3_data/PREREG_dynamism_2026-08-31.md` (커밋 47e10a7, 계산 이전)

이 스크립트가 하는 일은 **두 가지뿐**이다.
  1단계  M1~M4 를 구현하고, 사전등록이 요구한 **대조군 상한**을 재 둔다.
         "이 지표들은 원곡을 참조하지 않으므로 높다고 좋은 음악이라는 보장이 없다.
          극단적으로는 무작위 잡음이 모든 지표에서 최고값을 받는다.
          → `OM 전부 비움`과 `백색잡음` 대조군을 함께 돌려 그 상한을 명시한다."
  2단계  기존 19쌍에 걸어 **방향만** 본다. ⚠ 확증이 아니다 — 가설이 이 쌍들의
         코멘트에서 나왔으므로 순환이다. 사전등록이 그렇게 규정했다.

지표는 전부 **한 곡 안에서만** 계산한다. 원곡을 인자로 받지 않는다 — 그것이
거리 계열과의 결정적 차이이고, 함수 시그니처로 강제한다.

실행:  python experiments/run_dynamism_metrics.py [--n-seeds 20]
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
from scipy import stats

import generation as G
import run_dft_gap0_suite as suite
from run_metric_protocol import ROUNDS, TOL, load_notes
from run_topo_diffusion import (CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU,
                                STEP3_DIR, load_continuous_om)

WIN = 8          # M2 창 길이 (8분음표 8칸 = 한 마디)
CLIP = 24        # M1 음정 클립 (±2옥타브)
KEYS = ["interval_entropy", "onset_density_cv", "duration_entropy", "harmonic_change"]
LABEL = {"interval_entropy": "M1 음정엔트로피", "onset_density_cv": "M2 타건밀도CV",
         "duration_entropy": "M3 길이엔트로피", "harmonic_change": "M4 화성변화"}


def _entropy(counts):
    """Shannon 엔트로피 (bit). 빈 입력은 0."""
    c = np.asarray(counts, float)
    if c.sum() == 0:
        return 0.0
    p = c[c > 0] / c.sum()
    return float(-(p * np.log2(p)).sum())


# ── 사전등록 지표 4종 — 인자는 notes 하나뿐이다 (원곡 참조 불가) ──────────────
def interval_entropy(notes):
    """M1 — 연속 음정(다음음-현재음, ±24 클립) 분포의 엔트로피."""
    s = [p for _, p, _ in sorted(notes, key=lambda n: (n[0], n[1]))]
    h = np.zeros(2 * CLIP + 1)
    for a, b in zip(s, s[1:]):
        h[int(np.clip(b - a, -CLIP, CLIP)) + CLIP] += 1
    return _entropy(h)


def onset_density_cv(notes):
    """M2 — 8스텝 창별 타건 수의 변동계수(std/mean)."""
    if not notes:
        return 0.0
    T = int(max(n[0] for n in notes)) + 1
    c = np.zeros((T + WIN - 1) // WIN)
    for n in notes:
        c[int(n[0]) // WIN] += 1
    return float(c.std() / c.mean()) if c.mean() > 0 else 0.0


def duration_entropy(notes):
    """M3 — 음 길이 분포의 엔트로피."""
    d = {}
    for s, _, e in notes:
        k = max(1, int(e) - int(s))
        d[k] = d.get(k, 0) + 1
    return _entropy(list(d.values()))


def harmonic_change(notes):
    """M4 — 인접 시점의 울리는 pitch-class 집합 간 Jaccard 거리의 평균.

    ponytail: 두 시점이 **모두 비어** 있으면 '화성 변화' 자체가 정의되지 않으므로
    분모에서 뺀다. 한쪽만 비면 거리 1 이다(무음↔울림도 변화다).
    """
    if not notes:
        return 0.0
    T = int(max(e for _, _, e in notes)) + 1
    act = [set() for _ in range(T + 1)]
    for s, p, e in notes:
        for t in range(int(s), min(int(e), T) + 1):
            act[t].add(p % 12)
    ds = []
    for a, b in zip(act, act[1:]):
        if not a and not b:
            continue
        ds.append(1.0 - len(a & b) / len(a | b))
    return float(np.mean(ds)) if ds else 0.0


def dynamism(notes):
    return {"interval_entropy": interval_entropy(notes),
            "onset_density_cv": onset_density_cv(notes),
            "duration_entropy": duration_entropy(notes),
            "harmonic_change": harmonic_change(notes)}


def white_noise(template, rng):
    """백색잡음 대조군 — 음 수·시간 범위·음역만 맞추고 나머지는 전부 무작위."""
    ps = sorted({p for _, p, _ in template})
    T = int(max(e for _, _, e in template))
    out = []
    for _ in range(len(template)):
        s = rng.randrange(T)
        out.append((s, rng.choice(ps), s + rng.randrange(1, 9)))
    return sorted(out)


def holm(pvals):
    """Holm-Bonferroni 보정된 p 값."""
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(pvals) - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# ── 1단계 — 대조군 상한 ────────────────────────────────────────────────────
def stage1(args, data, orig):
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    om = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    T = om.shape[0]
    inst = (MODULES * (T // len(MODULES) + 2))[:T]
    seeds = [4000 + 29 * i for i in range(args.n_seeds)]

    def gen(o, seed):
        suite.set_all_seeds(seed)
        p = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        return G.algorithm1_optimized(p, list(inst), o, G.CycleSetManager(cyc),
                                      max_resample=50, verbose=False, min_onset_gap=0)

    arms = {"원곡 자신": [dynamism(orig)],
            "정본 (a=0.25, tau=0.5)": [dynamism(gen(om, s)) for s in seeds],
            "OM 전부 비움 (자유샘플링 100%)":
                [dynamism(gen(np.zeros_like(om), s)) for s in seeds],
            "백색잡음": [dynamism(white_noise(orig, random.Random(s))) for s in seeds]}

    print("\n" + "=" * 104)
    print("1단계 — 대조군 상한.  사전등록 §7: '무작위 잡음이 모든 지표에서 최고값을 받는다'")
    print("=" * 104)
    print(f"{'팔':30} " + " ".join(f"{LABEL[k]:>16}" for k in KEYS))
    means = {}
    for name, rows in arms.items():
        m = {k: float(np.mean([r[k] for r in rows])) for k in KEYS}
        sd = {k: float(np.std([r[k] for r in rows], ddof=1)) if len(rows) > 1 else 0.0
              for k in KEYS}
        means[name] = {"mean": m, "std": sd, "n": len(rows)}
        print(f"{name:30} " + " ".join(f"{m[k]:>10.4f}+-{sd[k]:.3f}" for k in KEYS))

    noise, best = means["백색잡음"]["mean"], {}
    print(f"\n{'-' * 104}")
    print("사전등록 예상 확인 — 잡음이 상한인가?")
    for k in KEYS:
        top = max(means, key=lambda a: means[a]["mean"][k])
        best[k] = top
        mark = ("예상대로 잡음이 최고" if top == "백색잡음"
                else f"**잡음이 최고가 아니다** -> {top}")
        print(f"  {LABEL[k]:18} 잡음 {noise[k]:.4f} · 최고 "
              f"{means[top]['mean'][k]:.4f} ({top})  {mark}")
    return means, best


# ── 2단계 — 탐색 (확증 아님) ───────────────────────────────────────────────
def stage2():
    print("\n" + "=" * 104)
    print("2단계 — 기존 19쌍 탐색.  ⚠ 확증 아님 (가설이 이 쌍들의 코멘트에서 나왔다)")
    print("=" * 104)
    rows = []
    for label, d, pre, n, ans in ROUNDS:
        for i in range(1, n + 1):
            q = f"{pre}{i}"
            if ans.get(q, "?") == "?":
                continue
            pa, pb = f"{d}/{q}A.mid", f"{d}/{q}B.mid"
            if not (os.path.exists(pa) and os.path.exists(pb)):
                continue
            A, B = load_notes(pa), load_notes(pb)
            gap = abs(len(A) - len(B)) / max(1, (len(A) + len(B)) / 2)
            rows.append({"pair": q, "round": label, "choice": ans[q],
                         "n_a": len(A), "n_b": len(B), "count_gap": float(gap),
                         "matched": bool(gap <= TOL),
                         "a": dynamism(A), "b": dynamism(B)})

    dec = [r for r in rows if r["matched"]]
    print(f"MCP 통과 {len(dec)}/{len(rows)}쌍 "
          f"(제외: {', '.join(r['pair'] for r in rows if not r['matched']) or '없음'})\n")

    print(f"{'쌍':5} {'선택':>4} " + " ".join(f"{LABEL[k]:>18}" for k in KEYS))
    for r in dec:
        cells = []
        for k in KEYS:
            hi = "A" if r["a"][k] > r["b"][k] else "B"
            cells.append(f"{r['a'][k]:6.3f}/{r['b'][k]:6.3f}"
                         f"{'O' if hi == r['choice'] else 'X'}")
        print(f"{r['pair']:5} {r['choice']:>4} " + " ".join(f"{c:>18}" for c in cells))

    print(f"\n{'-' * 104}")
    print(f"{'지표':20} {'예측방향 일치':>13} {'비율':>7} {'이항 p':>9} {'Holm p':>9} "
          f"{'r(값,음수)':>11} {'판정':>12}")
    raw, hits = [], {}
    for k in KEYS:
        h = sum(1 for r in dec if (r["a"][k] > r["b"][k]) == (r["choice"] == "A"))
        hits[k] = h
        raw.append(float(stats.binomtest(h, len(dec), 0.5).pvalue))
    adj = holm(raw)
    vals = {k: [r[s][k] for r in dec for s in ("a", "b")] for k in KEYS}
    cnts = [r[f"n_{s}"] for r in dec for s in ("a", "b")]
    corr, verdict = {}, {}
    for j, k in enumerate(KEYS):
        corr[k] = float(stats.pearsonr(vals[k], cnts)[0])
        if abs(corr[k]) > 0.4:
            v = "유보(|r|>0.4)"
        elif adj[j] < 0.05:
            v = "**유의**"
        else:
            v = "비유의"
        verdict[k] = v
        print(f"{LABEL[k]:20} {f'{hits[k]}/{len(dec)}':>13} {hits[k]/len(dec):>7.0%} "
              f"{raw[j]:>9.3f} {adj[j]:>9.3f} {corr[k]:>11.3f} {v:>12}")

    print("\n지표 간 상관 (사전등록 §7 — 넷이 서로 상관될 수 있다):")
    print(f"{'':20} " + " ".join(f"{LABEL[k][:6]:>9}" for k in KEYS))
    cm = {}
    for a in KEYS:
        cm[a] = {b: float(stats.pearsonr(vals[a], vals[b])[0]) for b in KEYS}
        print(f"{LABEL[a]:20} " + " ".join(f"{cm[a][b]:>9.3f}" for b in KEYS))
    return rows, dec, {"hits": hits, "raw_p": raw, "holm_p": adj.tolist(),
                       "corr_notes": corr, "verdict": verdict, "corr_matrix": cm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    t0 = time.time()
    print("=" * 104)
    print("사전등록 역동성 지표 M1~M4 — 1단계 대조군 상한 · 2단계 기존 19쌍 탐색")
    print("사전등록: docs/step3_data/PREREG_dynamism_2026-08-31.md (47e10a7, 계산 이전)")
    print("=" * 104)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    means, best = stage1(args, data, orig)
    rows, dec, stat = stage2()

    out = {"experiment": "dynamism_metrics",
           "prereg": "docs/step3_data/PREREG_dynamism_2026-08-31.md (commit 47e10a7)",
           "status": "탐색 전용 — 확증은 신규 회차 R4 가 담당한다",
           "metrics": {k: LABEL[k] for k in KEYS},
           "stage1_controls": means,
           "stage1_argmax": best,
           "stage2_rows": rows,
           "stage2_n_matched": len(dec),
           "stage2_stats": stat,
           "limitation": ("(1) 이 19쌍은 가설의 출처다 — 순환이므로 확증이 아니다. "
                          "(2) 청취자 1명. (3) 지표가 원곡을 참조하지 않으므로 "
                          "'높다=좋다'가 아니다(1단계 상한 참조)."),
           "n_seeds": args.n_seeds, "total_seconds": time.time() - t0}
    p = os.path.join(STEP3_DIR, "dynamism_metrics.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: {p}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
