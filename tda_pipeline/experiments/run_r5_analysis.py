"""run_r5_analysis.py — R5 판별 회차 채점기. **답이 오기 전에** 커밋한다

자극·분석계획: `output/ab_r5/answer_key.json` (커밋 234d818, 청취 이전)

이번 회차가 묻는 것은 선호가 아니라 **판별**이다 — 정답이 있다.
그래서 채점은 단순하고, 중요한 것은 **무엇을 결론으로 삼을지 미리 정해 두는 것**이다.

  · 축(밀도·음역·온도)마다 3쌍의 정답률. 약/중/강 중 **어디서부터 맞히는지**가
    슬라이더 눈금의 근거가 된다.
  · 귀무 3쌍은 지표 차가 정확히 0 이다. 여기서 '구별 안 됨' 이 아닌 응답은
    **거짓 양성**이다.
  · 무효화 규칙: 귀무에서 확신 응답이 **2개 이상**이면 그 회차의 판별 결과를
    신뢰하지 않는다 (응답자가 추측하고 있다는 뜻).
  · 12쌍·1인이므로 통계가 아니라 **신호 유무**를 본다. 이항검정은 참고로만 낸다.

실행:  python experiments/run_r5_analysis.py --answers "D1:A ; D2:B ; D3:? ; ..."
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os

from scipy import stats

import run_dft_gap0_suite as suite
from run_topo_diffusion import STEP3_DIR

FAM = {"density": "밀도", "register": "음역", "temperature": "온도", "null": "귀무"}
ORDER = ["density", "register", "temperature"]


def parse(s):
    out = {}
    for tok in s.replace(",", ";").split(";"):
        if ":" in tok:
            k, v = tok.split(":", 1)
            out[k.strip().upper()] = v.strip().split("|")[0].strip().upper()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)

    K = json.load(open("output/ab_r5/answer_key.json", encoding="utf-8"))["key"]
    ans = parse(args.answers)

    print("=" * 100)
    print("R5 판별 회차 — 손잡이가 들리는가")
    print("=" * 100)
    print(f"{'쌍':5} {'축':6} {'세기':20} {'효과':>8} {'응답':>6} {'정답':>6}  판정")
    rows = []
    for pid, e in K.items():
        a = ans.get(pid, "?")
        sig = e["effect_in_sigma"] or 0.0
        if e["truth"] is None:
            ok = None
            v = "거짓 양성" if a in ("A", "B") else "정상 (구별 안 됨)"
        else:
            ok = (a == e["truth"]) if a in ("A", "B") else None
            v = "맞음" if ok else ("모름" if ok is None else "틀림")
        print(f"{pid:5} {FAM[e['family']]:6} {e['strength']:20} {sig:>7.1f}σ "
              f"{a:>6} {str(e['truth'] or '—'):>6}  {v}")
        rows.append({"pair": pid, "family": e["family"], "strength": e["strength"],
                     "effect_in_sigma": sig, "answer": a, "truth": e["truth"],
                     "correct": ok, "verdict": v})

    # ── 무효화 규칙을 **먼저** 적용한다 ──
    fp = [r for r in rows if r["truth"] is None and r["answer"] in ("A", "B")]
    print(f"\n{'-' * 100}")
    print(f"귀무 대조 — 거짓 양성 {len(fp)}/3"
          f"{' (' + ', '.join(r['pair'] for r in fp) + ')' if fp else ''}")
    invalid = len(fp) >= 2
    if invalid:
        print("  ⚠ **사전 규칙 발동: 거짓 양성 2개 이상 → 이 회차의 판별 결과를 신뢰하지 않는다.**")
    else:
        print("  → 판별 결과를 읽어도 된다.")

    print(f"\n{'축':8} {'정답':>8} {'비율':>7} {'이항 p':>9}   세기별 (약→강)")
    per = {}
    for f in ORDER:
        rs = [r for r in rows if r["family"] == f]
        dec = [r for r in rs if r["correct"] is not None]
        hit = sum(1 for r in dec if r["correct"])
        p = float(stats.binomtest(hit, len(dec), 0.5).pvalue) if dec else float("nan")
        seq = " → ".join(f"{r['effect_in_sigma']:.1f}σ:"
                         f"{'O' if r['correct'] else ('?' if r['correct'] is None else 'X')}"
                         for r in rs)
        per[f] = {"hits": hit, "n_decided": len(dec), "p": p,
                  "detail": [{k: r[k] for k in ("pair", "strength", "effect_in_sigma",
                                                "answer", "correct")} for r in rs]}
        print(f"{FAM[f]:8} {f'{hit}/{len(dec)}':>8} "
              f"{(hit / len(dec) if dec else 0):>7.0%} {p:>9.3f}   {seq}")

    # 역치 — 맞히기 시작한 가장 약한 세기
    print(f"\n역치 (맞힌 것 중 가장 약한 효과 = 슬라이더 최소 눈금 후보)")
    thr = {}
    for f in ORDER:
        ok = [r for r in per[f]["detail"] if r["correct"]]
        thr[f] = min((r["effect_in_sigma"] for r in ok), default=None)
        print(f"  {FAM[f]:8} " + (f"{thr[f]:.1f}σ 부터 판별됨 "
                                  f"({min(ok, key=lambda r: r['effect_in_sigma'])['strength']})"
                                  if ok else "**어떤 세기에서도 판별되지 않음**"))

    out = {"experiment": "r5_knob_discrimination",
           "analysis_committed_before_data": True,
           "answers": ans, "rows": rows,
           "false_positives": len(fp), "round_invalidated": invalid,
           "per_axis": per, "threshold_sigma": thr, "notes": args.notes,
           "limitation": ("12쌍·청취자 1명·축당 3쌍. 통계가 아니라 신호 유무를 본다. "
                          "음역 쌍은 음 수가 함께 움직여 완전히 독립적이지 않다.")}
    p = os.path.join(STEP3_DIR, "r5_knob_discrimination.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n저장: {p}")


if __name__ == "__main__":
    main()
