"""run_r4_analysis.py — R4 확증 회차 채점기. **답이 오기 전에** 작성·커밋한다

사전등록: `docs/step3_data/PREREG_dynamism_2026-08-31.md` (커밋 47e10a7)
자극 설계: `output/ab_r4/answer_key.json` (커밋 시점에 분석 계획까지 고정돼 있다)

이 파일이 답보다 먼저 커밋돼 있어야 "결과를 보고 검정을 골랐다"는 의심이 성립하지 않는다.
그래서 채점 규칙은 전부 하드코딩이고, 인자로 받는 것은 **답 문자열 하나뿐**이다.

분석 (사전등록 §5 + answer_key 의 analysis_plan_fixed_before_listening 그대로)
  · 지표마다 **12쌍 전부**에서 "선택된 쪽의 값이 더 큰가" 이항검정(양측, H0=0.5)
  · Holm 보정 (지표 4종)
  · r(지표값, 음 수) 병기 — |r|>0.4 면 그 지표 유보
  · 성공 = 최소 하나가 Holm 후 p<0.05 이고 **선택된 쪽이 높다**
  · 실패 = 넷 다 비유의거나 방향 반대 → 다른 지표를 찾아 붙이지 않는다

실행:  python experiments/run_r4_analysis.py --answers "S1:A ; S2:B ; S3:? ; ..."
       (모르겠다 = '?' 는 제외한다. 이유 코멘트는 --notes 로 따로 넘긴다.)
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os

import numpy as np
from scipy import stats

import run_dft_gap0_suite as suite
from run_dynamism_metrics import KEYS, LABEL, holm
from run_topo_diffusion import STEP3_DIR

PREDICTION = {k: "선택된 쪽이 높다" for k in KEYS}     # 사전등록 §4 — 넷 다 같은 방향
TARGET_RATE = {"interval_entropy": 0.65, "onset_density_cv": 0.70,
               "duration_entropy": 0.65, "harmonic_change": 0.70}


def parse(s):
    out = {}
    for tok in s.replace(",", ";").split(";"):
        if ":" not in tok:
            continue
        k, v = tok.split(":", 1)
        out[k.strip().upper()] = v.strip().split("|")[0].strip().upper()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)

    key = json.load(open("output/ab_r4/answer_key.json", encoding="utf-8"))
    K = key["key"]
    ans = parse(args.answers)
    dec = [(p, ans[p]) for p in K if ans.get(p, "?") in ("A", "B")]

    print("=" * 104)
    print("R4 확증 회차 — 사전등록 역동성 가설")
    print("=" * 104)
    print(f"응답 {len(dec)}/{len(K)}쌍 (모르겠다 제외: "
          f"{', '.join(p for p in K if ans.get(p, '?') not in ('A', 'B')) or '없음'})\n")

    print(f"{'쌍':5} {'목표':16} {'선택':>4} {'역할':>6} " +
          " ".join(f"{LABEL[k]:>17}" for k in KEYS))
    for p, c in dec:
        e = K[p]
        cells = []
        for k in KEYS:
            hi = "A" if e["A"]["metrics"][k] > e["B"]["metrics"][k] else "B"
            cells.append(f"{e['A']['metrics'][k]:6.3f}/{e['B']['metrics'][k]:6.3f}"
                         f"{'O' if hi == c else 'X'}")
        print(f"{p:5} {LABEL[e['target']]:16} {c:>4} {e[c]['role']:>6} " +
              " ".join(f"{x:>17}" for x in cells))

    # ── 주 검정 ──
    raw, hits = [], {}
    for k in KEYS:
        h = sum(1 for p, c in dec
                if (K[p]["A"]["metrics"][k] > K[p]["B"]["metrics"][k]) == (c == "A"))
        hits[k] = h
        raw.append(float(stats.binomtest(h, len(dec), 0.5).pvalue))
    adj = holm(raw)

    vals = {k: [K[p][s]["metrics"][k] for p, _ in dec for s in ("A", "B")] for k in KEYS}
    cnts = [K[p][s]["n"] for p, _ in dec for s in ("A", "B")]

    print(f"\n{'-' * 104}")
    print(f"{'지표':20} {'일치':>8} {'비율':>7} {'예측':>7} {'이항 p':>9} {'Holm p':>9} "
          f"{'r(값,음수)':>11} {'판정':>14}")
    res,supported = {}, False
    for j, k in enumerate(KEYS):
        r = float(stats.pearsonr(vals[k], cnts)[0])
        rate = hits[k] / len(dec)
        if abs(r) > 0.4:
            v = "유보(|r|>0.4)"
        elif adj[j] < 0.05 and rate > 0.5:
            v = "**유의·예측대로**"
            supported = True
        elif adj[j] < 0.05:
            v = "**유의·방향반대**"
        else:
            v = "비유의"
        res[k] = {"hits": hits[k], "n": len(dec), "rate": rate, "p_raw": raw[j],
                  "p_holm": float(adj[j]), "r_with_notes": r,
                  "predicted_rate": TARGET_RATE[k], "prediction": PREDICTION[k],
                  "verdict": v}
        print(f"{LABEL[k]:20} {f'{hits[k]}/{len(dec)}':>8} {rate:>7.0%} "
              f"{TARGET_RATE[k]:>7.0%} {raw[j]:>9.3f} {adj[j]:>9.3f} {r:>11.3f} {v:>14}")

    print(f"\n{'=' * 104}")
    print("사전등록 판정:  " + ("**H1 지지** — 최소 한 지표가 Holm 후 유의하고 예측 방향이다."
                            if supported else
                            "**H1 기각** — 어떤 지표도 Holm 보정을 통과하지 못했다. "
                            "사전등록대로 다른 지표를 찾아 붙이지 않는다."))
    print("=" * 104)

    out = {"experiment": "r4_dynamism_confirmatory",
           "prereg": "docs/step3_data/PREREG_dynamism_2026-08-31.md (commit 47e10a7)",
           "analysis_committed_before_data": True,
           "answers": ans, "n_decided": len(dec),
           "per_metric": res, "supported": supported,
           "notes": args.notes,
           "limitation": ("청취자 1명 · 12쌍. 쌍 안의 차이는 시드 하나뿐이므로 "
                          "위상·α 와 교란되지 않지만, 그만큼 '역동성' 외의 우연한 "
                          "차이도 함께 들어간다."),
           "caveat_M3": key.get("caveat_M3")}
    p = os.path.join(STEP3_DIR, "r4_dynamism_result.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: {p}")


if __name__ == "__main__":
    main()
