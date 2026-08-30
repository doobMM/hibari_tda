"""run_metric_protocol.py — 음 수를 **프로토콜로 통제**하고 청취 판정으로 검증한다

배경
────
`metric_design.json`: 후보 6종 중 `interval_js` 만 G1(순서 민감)·G2(자유샘플링 벌점)·
G4(원곡 최소)를 통과했고 G3(음 수 독립)에서 떨어졌다(r=−0.50, 표본 고정 후에도 −0.50).

사용자 결정: **음 수를 지표의 성질로 없애려 하지 말고 프로토콜로 통제한다.**
근거는 단순하다 — 음 수는 *교란 공변량*이고, 교란은 지표를 바꿔서가 아니라
**비교 조건을 맞춰서** 다루는 것이 표준이다. 이미 이 프로젝트는 같은 일을 두 번 했다:
α vineyard 의 대비 정렬, A/B 의 노출도 정렬.

프로토콜 (MCP — Matched-Count Protocol)
───────────────────────────────────────
두 팔을 `interval_js` 로 비교하기 전에:
  1. 두 팔의 음 수 분포를 비교한다.
  2. |Δ평균| / 평균 이 TOL 을 넘으면 → **비교 불가로 보고한다.** 값을 내지 않는다.
  3. 통과하면 paired 비교 + 음 수를 항상 병기한다.
그리고 결과에는 **언제나 음 수 차이를 함께 싣는다** — 숨기면 같은 함정에 다시 빠진다.

검증 — 청취 판정 19쌍을 맞추는가
────────────────────────────────
지표가 옳은지는 관문만으로 알 수 없다. 관문은 "무엇을 재지 못하는가" 만 거른다.
그래서 **이미 확보한 사람의 판정**으로 검증한다:
    1차 ab_check 5쌍 · 2차 ab_p4 5쌍 · 3차 ab_r3 9쌍  = 19쌍
음고 JS 는 이 중 몇 개를 맞췄는지 이미 안다. `interval_js` 가 더 나은가?

⚠ 한계: 19쌍·한 청취자다. 이 검증은 "명백히 못 맞춘다" 를 걸러낼 수는 있어도
   "맞춘다" 를 확립하지는 못한다(80% 를 보이려면 20쌍, 61% 면 162쌍).

실행:  python experiments/run_metric_protocol.py
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
import pretty_midi
from scipy import stats

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_metric_design import _js, interval_hist
from run_topo_diffusion import STEP3_DIR, consonance_score

SEC_PER_8TH = 60 / 66 / 2
TOL = 0.10        # 음 수 평균 차이가 10% 를 넘으면 비교하지 않는다

ROUNDS = [
    ("1차 ab_check", "output/ab_check", "P", 5,
     {"P1": "B", "P2": "B", "P3": "A", "P4": "B", "P5": "A"}),
    ("2차 ab_p4", "output/ab_p4", "Q", 6,
     {"Q1": "A", "Q2": "B", "Q3": "?", "Q4": "B", "Q5": "B", "Q6": "A"}),
    ("3차 ab_r3", "output/ab_r3", "R", 15,
     {"R1": "?", "R2": "B", "R3": "B", "R4": "?", "R5": "?", "R6": "B", "R7": "?",
      "R8": "B", "R9": "?", "R10": "A", "R11": "A", "R12": "?", "R13": "B",
      "R14": "B", "R15": "A"}),
]


def load_notes(path):
    pm = pretty_midi.PrettyMIDI(path)
    ns = sorted(((n.start / SEC_PER_8TH, n.pitch, n.end / SEC_PER_8TH)
                 for i in pm.instruments for n in i.notes))
    return [(int(round(s)), int(p), int(round(e))) for s, p, e in ns]


def matched_count_compare(a_notes, b_notes, orig, tol=TOL):
    """MCP — 음 수가 맞을 때만 interval_js 로 비교한다."""
    na, nb = len(a_notes), len(b_notes)
    gap = abs(na - nb) / max(1, (na + nb) / 2)
    out = {"n_a": na, "n_b": nb, "count_gap": float(gap), "matched": bool(gap <= tol)}
    if not out["matched"]:
        out["verdict"] = "비교 불가 (음 수 차이 %.0f%% > %.0f%%)" % (gap * 100, tol * 100)
        return out
    out["interval_js_a"] = _js(interval_hist(a_notes), interval_hist(orig))
    out["interval_js_b"] = _js(interval_hist(b_notes), interval_hist(orig))
    out["winner"] = "A" if out["interval_js_a"] < out["interval_js_b"] else "B"
    return out


def main():
    os.chdir(suite.BASE_DIR)
    t0 = time.time()
    print("=" * 96)
    print("MCP — 음 수를 프로토콜로 통제한 interval_js, 청취 판정으로 검증")
    print("=" * 96)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])

    rows = []
    print(f"\n{'쌍':6} {'선택':>4} {'음 수 A/B':>12} {'차이':>7} {'interval_js A/B':>22} "
          f"{'MCP':>6} {'JS':>5}")
    for label, d, pre, n, ans in ROUNDS:
        for i in range(1, n + 1):
            q = f"{pre}{i}"
            if ans.get(q, "?") == "?":
                continue
            pa, pb = f"{d}/{q}A.mid", f"{d}/{q}B.mid"
            if not (os.path.exists(pa) and os.path.exists(pb)):
                continue
            A, B = load_notes(pa), load_notes(pb)
            r = matched_count_compare(A, B, orig)
            pjs_a = pitch_distribution_similarity(A, orig)["js_divergence"]
            pjs_b = pitch_distribution_similarity(B, orig)["js_divergence"]
            pick = ans[q]
            js_ok = (pjs_a < pjs_b) == (pick == "A")
            mcp_ok = (r["winner"] == pick) if r["matched"] else None
            rows.append({"pair": q, "round": label, "choice": pick, **r,
                         "pitch_js_a": pjs_a, "pitch_js_b": pjs_b,
                         "pitch_js_agrees": bool(js_ok), "mcp_agrees": mcp_ok})
            iv = ("%.4f/%.4f" % (r["interval_js_a"], r["interval_js_b"])
                  if r["matched"] else "—")
            cnt = "%d/%d" % (r["n_a"], r["n_b"])
            print(f"{q:6} {pick:>4} {cnt:>12} "
                  f"{r['count_gap']*100:>6.1f}% {iv:>22} "
                  f"{('○' if mcp_ok else '✗') if r['matched'] else '제외':>6} "
                  f"{'○' if js_ok else '✗':>5}")

    dec = [r for r in rows if r["mcp_agrees"] is not None]
    excl = [r for r in rows if r["mcp_agrees"] is None]
    mcp_hit = sum(1 for r in dec if r["mcp_agrees"])
    js_hit_all = sum(1 for r in rows if r["pitch_js_agrees"])
    js_hit_dec = sum(1 for r in dec if r["pitch_js_agrees"])

    print(f"\n{'─' * 96}")
    print(f"프로토콜이 제외한 쌍: {len(excl)}/{len(rows)}  "
          f"({', '.join(r['pair'] for r in excl) if excl else '없음'})")
    print(f"\n{'지표':28} {'일치':>10} {'비율':>7} {'이항 p':>9}")
    for nm, k, n_ in (("음고 JS (전체 19쌍)", js_hit_all, len(rows)),
                      ("음고 JS (MCP 통과쌍만)", js_hit_dec, len(dec)),
                      ("interval_js + MCP", mcp_hit, len(dec))):
        p = float(stats.binomtest(k, n_, 0.5).pvalue) if n_ else float("nan")
        print(f"{nm:28} {f'{k}/{n_}':>10} {k/n_ if n_ else 0:>7.0%} {p:>9.3f}")

    if len(dec):
        both = [(r["pitch_js_agrees"], r["mcp_agrees"]) for r in dec]
        b01 = sum(1 for a, b in both if not a and b)
        b10 = sum(1 for a, b in both if a and not b)
        pm = float(stats.binomtest(b01, b01 + b10, 0.5).pvalue) if (b01 + b10) else 1.0
        print(f"\nMcNemar (같은 쌍에서 한쪽만 맞춘 경우): "
              f"interval_js 만 맞춤 {b01} · 음고 JS 만 맞춤 {b10} · p={pm:.3f}")

    payload = {"experiment": "matched_count_protocol",
               "protocol": {"name": "MCP", "tolerance": TOL,
                            "rule": "음 수 평균 차이가 10% 를 넘으면 비교하지 않고 '비교 불가' 로 보고한다"},
               "rows": rows,
               "summary": {"n_pairs": len(rows), "n_excluded": len(excl),
                           "pitch_js_all": [js_hit_all, len(rows)],
                           "pitch_js_matched_only": [js_hit_dec, len(dec)],
                           "interval_js_mcp": [mcp_hit, len(dec)]},
               "limitation": ("19쌍·청취자 1명. '명백히 못 맞춘다' 는 거를 수 있어도 "
                              "'맞춘다' 를 확립하지는 못한다."),
               "total_seconds": time.time() - t0}
    json.dump(payload, open(os.path.join(STEP3_DIR, "metric_protocol.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: metric_protocol.json  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
