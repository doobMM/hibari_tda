"""run_metric_design.py — 순서·구조를 보는 지표를 설계하고 **검증 관문**에 통과시킨다

왜 필요한가
───────────
음고 JS 는 두 가지 이유로 목표가 될 수 없음이 밝혀졌다 (2026-08-31, `2e42c32`):
  · **순서를 안 본다** — 주변 분포 통계라 시간 순서를 섞어도 값이 변하지 않는다
  · **위상을 안 쓸수록 좋아진다** — 노드 풀이 곧 원곡의 음고 분포라서,
    OM 을 전부 비운 생성(0.00087)이 헤드라인(0.00902)을 10배 이긴다
협화도도 청취에서 갈렸다(R3 C족 2:2). 둘 다 목표로 쓸 수 없다.

설계 원칙 — 먼저 **관문**을 정하고 그다음에 후보를 만든다
────────────────────────────────────────────────────────
지표를 제안하는 것은 쉽다. 오늘 배운 것은 **제안한 지표가 무엇을 재는지 검증하지 않으면
엉뚱한 것을 최적화하게 된다**는 것이다. 그래서 통과해야 할 4관문을 먼저 못박는다.

  G1 순서 민감  — 생성물의 시간 순서를 섞으면 점수가 **나빠져야** 한다.
                  (음고 JS 는 정확히 0 만큼 변한다 → 탈락 예정)
  G2 자유샘플링 벌점 — OM 을 비운 생성이 정본보다 **나빠야** 한다.
                  (음고 JS 는 반대로 10배 좋아진다 → 탈락 예정)
  G3 음 수 독립 — 음 수와의 |상관| < 0.4. 강하면 "음을 충분히 냈나" 를 재는 것이다.
                  (음고 JS 는 r=−0.65 → 탈락 예정)
  G4 원곡 최소  — 원곡 자신을 넣으면 0 에 가까워야 한다. 아니면 정의가 틀린 것이다.

후보
────
  [순서] interval_js   — 연속 음정(다음음−현재음) 분포의 JS. 이조 불변이고 순서 의존.
  [순서] transition_js — pitch class 이항(bigram) 분포의 JS. 어떤 음 뒤에 어떤 음이 오나.
  [순서] onset_acf     — 타건 시계열 자기상관(lag 1..16) 프로파일의 L1 거리.
  [구조] cooc_dist     — 동시발생 행렬 거리. 어떤 음들이 **함께 울리는가** —
                         PH 가 올라타는 바로 그 substrate 다. 자유샘플링은 이것을 파괴한다.
  [구조] cycle_hit     — 활성 cycle 교집합 안에서 나온 음의 비율(↑ 좋음).
  [대조] pitch_js      — 기존 지표. 관문에서 탈락하는 것을 보이려고 함께 돌린다.

실행:  python experiments/run_metric_design.py [--n-seeds 20]
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
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU,
                                STEP3_DIR, consonance_score, load_continuous_om)

LAGS = 16
KEYS = ["pitch_js", "interval_js", "transition_js", "onset_acf", "cooc_dist", "cycle_hit"]
HIGHER_BETTER = {"cycle_hit"}
RHYTHM_METRICS = {"onset_acf"}   # 이 지표는 음고가 아니라 시점을 본다


def _js(p, q):
    p = np.asarray(p, float)
    q = np.asarray(q, float)
    if p.sum() == 0 or q.sum() == 0:
        return 1.0
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(a, b):
        return float(np.sum(np.where(a > 0, a * np.log2(a / np.where(b > 0, b, 1)), 0.0)))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def _seq(notes):
    """시작시각 순으로 정렬한 음고열."""
    return [p for _, p, _ in sorted(notes, key=lambda n: (n[0], n[1]))]


def interval_hist(notes, lo=-24, hi=24):
    s = _seq(notes)
    h = np.zeros(hi - lo + 1)
    for a, b in zip(s, s[1:]):
        h[int(np.clip(b - a, lo, hi)) - lo] += 1
    return h


def transition_hist(notes):
    s = [p % 12 for p in _seq(notes)]
    h = np.zeros(144)
    for a, b in zip(s, s[1:]):
        h[a * 12 + b] += 1
    return h


def onset_series(notes, T):
    c = np.zeros(T)
    for n in notes:
        t = int(n[0])
        if 0 <= t < T:
            c[t] += 1
    return c


def acf(x, lags=LAGS):
    x = np.asarray(x, float) - np.mean(x)
    d = float(np.dot(x, x))
    if d == 0:
        return np.zeros(lags)
    return np.array([float(np.dot(x[:-k], x[k:])) / d for k in range(1, lags + 1)])


def cooc(notes):
    """동시발생 행렬 — 두 음이 같은 시점에 함께 울린 횟수."""
    ps = sorted({p for _, p, _ in notes})
    idx = {p: i for i, p in enumerate(ps)}
    T = int(max((e for _, _, e in notes), default=1))
    active = [[] for _ in range(T + 2)]
    for s, p, e in notes:
        for t in range(int(s), min(int(e), T) + 1):
            active[t].append(idx[p])
    M = np.zeros((len(ps), len(ps)))
    for a in active:
        for i in a:
            for j in a:
                if i != j:
                    M[i, j] += 1
    return ps, M


def cooc_dist(gen, orig):
    """두 동시발생 행렬을 공통 음고 축에 올려 정규화한 뒤 총변동 거리."""
    pg, Mg = cooc(gen)
    po, Mo = cooc(orig)
    ps = sorted(set(pg) | set(po))
    pos = {p: i for i, p in enumerate(ps)}
    n = len(ps)
    A = np.zeros((n, n))
    B = np.zeros((n, n))
    for i, p in enumerate(pg):
        for j, q in enumerate(pg):
            A[pos[p], pos[q]] = Mg[i, j]
    for i, p in enumerate(po):
        for j, q in enumerate(po):
            B[pos[p], pos[q]] = Mo[i, j]
    if A.sum():
        A /= A.sum()
    if B.sum():
        B /= B.sum()
    return float(np.abs(A - B).sum() / 2)


def cycle_hit(notes, om, cycle_labeled, notes_label):
    """활성 cycle 의 교집합 안에서 나온 음의 비율. 자유 샘플링 구간은 분모에서 뺀다."""
    lab = {}
    for note, l in notes_label.items():
        lab.setdefault(note[0], set()).add(l - 1)
    sets = [set(v) for v in cycle_labeled.values()]
    hit = tot = 0
    for s, p, _ in notes:
        t = int(s)
        if t >= om.shape[0]:
            continue
        act = [sets[k] for k in range(om.shape[1]) if om[t, k] > 0]
        if not act:
            continue
        inter = set.intersection(*act) if len(act) > 1 else act[0]
        if not inter:
            continue
        tot += 1
        if lab.get(p, set()) & inter:
            hit += 1
    return hit / tot if tot else float("nan")


def evaluate(notes, orig, om, cyc, notes_label, T):
    return {
        "pitch_js": pitch_distribution_similarity(notes, orig)["js_divergence"],
        "interval_js": _js(interval_hist(notes), interval_hist(orig)),
        "transition_js": _js(transition_hist(notes), transition_hist(orig)),
        "onset_acf": float(np.abs(acf(onset_series(notes, T)) - acf(onset_series(orig, T))).mean()),
        "cooc_dist": cooc_dist(notes, orig),
        "cycle_hit": cycle_hit(notes, om, cyc, notes_label),
        "n_notes": len(notes),
        "consonance": consonance_score(notes),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    t0 = time.time()

    print("=" * 104)
    print("순서·구조 지표 설계 — 관문 4개 통과 검증")
    print("=" * 104)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
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

    arms = {}
    for name, o in (("정본", om), ("OM 전부 비움", np.zeros_like(om))):
        arms[name] = [evaluate(gen(o, s), orig, om, cyc, data["notes_label"], T) for s in seeds]

    # 시간 셔플 — onset/duration 은 그대로 두고 음고열만 재배열한다.
    # 주변 분포는 정확히 보존되므로 순서를 보는 지표만 나빠져야 한다.
    shuf = []
    for s in seeds:
        g = gen(om, s)
        ps = [p for _, p, _ in g]
        random.Random(s).shuffle(ps)
        shuf.append(evaluate([(a, ps[i], c) for i, (a, _, c) in enumerate(g)],
                             orig, om, cyc, data["notes_label"], T))
    arms["정본 + 음고 셔플"] = shuf

    # 리듬 셔플 — 음고는 제자리, **onset 만** 재배열한다.
    # 음고 셔플만으로는 리듬 지표(onset_acf)를 검사할 수 없다 — 그건 내 테스트 결함이었다.
    rshuf = []
    for s in seeds:
        g = gen(om, s)
        starts = [a for a, _, _ in g]
        random.Random(s + 1).shuffle(starts)
        rshuf.append(evaluate([(starts[i], p_, starts[i] + max(1, c - a))
                               for i, (a, p_, c) in enumerate(g)],
                              orig, om, cyc, data["notes_label"], T))
    arms["정본 + 리듬 셔플"] = rshuf
    arms["원곡 자신"] = [evaluate(orig, orig, om, cyc, data["notes_label"], T)]

    print(f"\n{'팔':20} " + " ".join(f"{k:>14}" for k in KEYS) + f" {'음':>6}")
    mean = {}
    for name, rows in arms.items():
        mean[name] = {k: float(np.nanmean([r[k] for r in rows])) for k in KEYS + ["n_notes"]}
        print(f"{name:20} " + " ".join(f"{mean[name][k]:>14.5f}" for k in KEYS)
              + f" {mean[name]['n_notes']:>6.0f}")

    print(f"\n{'─' * 104}")
    print("관문 판정   (cycle_hit 만 ↑ 좋음, 나머지는 ↓ 좋음)")
    print(f"{'지표':15} {'G1 순서민감':>12} {'G2 자유샘플링':>14} {'G3 음수독립':>18} {'G4 원곡최소':>18}  판정")
    verdict, passed = {}, []
    for k in KEYS:
        hb = k in HIGHER_BETTER
        b = mean["정본"][k]
        f_ = mean["OM 전부 비움"][k]
        # 리듬 지표는 리듬 셔플로, 음고 지표는 음고 셔플로 검사한다.
        sh_key = "정본 + 리듬 셔플" if k in RHYTHM_METRICS else "정본 + 음고 셔플"
        sh = mean[sh_key][k]
        ori = mean["원곡 자신"][k]
        g1 = (sh < b) if hb else (sh > b)
        g2 = (f_ < b) if hb else (f_ > b)
        vals = np.array([r[k] for r in arms["정본"]])
        ns = np.array([r["n_notes"] for r in arms["정본"]])
        r_n = float(stats.pearsonr(vals, ns)[0]) if vals.std() > 0 and ns.std() > 0 else 0.0
        g3 = abs(r_n) < 0.4
        g4 = (ori > 0.95) if hb else (ori < 0.02)
        ok = bool(g1 and g2 and g3 and g4)
        if ok:
            passed.append(k)
        verdict[k] = {"G1_order": bool(g1), "G2_free_penalty": bool(g2),
                      "G3_note_independent": bool(g3), "G4_original_min": bool(g4),
                      "r_with_notes": r_n, "pass": ok, "higher_better": hb,
                      "canonical": b, "free_sampling": f_, "shuffled": sh,
                      "shuffle_kind": sh_key, "original": ori}
        m = lambda x: "○" if x else "✗"
        print(f"{k:15} {m(g1):>12} {m(g2):>14} "
              f"{m(g3) + ' (r=%+.2f)' % r_n:>18} {m(g4) + ' (%.4f)' % ori:>18}  "
              f"{'**통과**' if ok else '탈락'}")

    print(f"\n통과한 지표: {', '.join(passed) if passed else '없음'}")
    json.dump({"experiment": "metric_design_gauntlet",
               "gates": {"G1": "시간 셔플 시 나빠져야 한다",
                         "G2": "OM 을 비운 생성이 정본보다 나빠야 한다",
                         "G3": "음 수와의 |r| < 0.4",
                         "G4": "원곡 자신이 최적값에 근접"},
               "n_seeds": args.n_seeds, "arm_means": mean,
               "verdict": verdict, "passed": passed,
               "limitation": ("관문은 '무엇을 재지 못하는가' 만 거른다. 통과한 지표가 "
                              "청취 선호를 예측하는지는 별도 청취 검증이 필요하다."),
               "total_seconds": time.time() - t0},
              open(os.path.join(STEP3_DIR, "metric_design.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"저장: metric_design.json  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
