"""score_js_algo1.py — verify_js_algo1.mjs 산출물을 **파이썬 지표로** 채점한다.

왜 파이썬으로 채점하는가
────────────────────────
JS 쪽에서 지표까지 다시 구현하면 "두 구현이 같은 실수를 한" 경우를 못 잡는다.
실제로 2026-08-14 인덱스 버그가 오래 살아남은 이유가 그것이다 —
기존 대조는 파이썬 기준값을 JS 동작에 맞춰 만들었다.
여기서는 `eval_metrics.pitch_distribution_similarity` 원본을 그대로 쓴다.

판정: 수정된 JS 포트의 음고 JS 가 파이썬 정본(0.00902 ± 0.00170)의 3σ 안에 있어야 한다.
      RNG 가 다르므로(mulberry32 vs Mersenne Twister) 비트 일치는 기대하지 않는다.

실행:  node tools/verify_js_algo1.mjs --with-old  &&  python tools/verify/score_js_algo1.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.dirname(
    _rp_os.path.abspath(__file__)))))
_rp_sys.path.insert(0, _rp_os.path.join(_rp_sys.path[0], "experiments"))
# --- end path_bootstrap ---

import json
import os

import numpy as np

import run_topo_diffusion as _TD          # noqa: F401  (suite.MIDI_FILE 몽키패치 목적)
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity

HERE = os.path.dirname(os.path.abspath(__file__))
CANONICAL_MEAN, CANONICAL_STD = 0.00902, 0.00170


def main() -> int:
    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])

    scores = {}
    for tag in ("after", "before"):
        p = os.path.join(HERE, f"js_algo1_notes_{tag}.json")
        if not os.path.exists(p):
            continue
        runs = json.load(open(p, encoding="utf-8"))
        scores[tag] = [pitch_distribution_similarity([tuple(n) for n in r], orig)["js_divergence"]
                       for r in runs]
        print(f"JS 포트 {tag:6}: 음고 JS = {np.mean(scores[tag]):.5f} "
              f"± {np.std(scores[tag], ddof=1):.5f}  (N={len(runs)})")

    print(f"파이썬 정본        : 음고 JS = {CANONICAL_MEAN:.5f} ± {CANONICAL_STD:.5f}")

    if "before" in scores and "after" in scores:
        from scipy import stats
        p = stats.ttest_rel(scores["before"], scores["after"]).pvalue
        ratio = np.mean(scores["before"]) / np.mean(scores["after"])
        print(f"대조군 대비        : {ratio:.2f}배 악화, paired p={p:.2e}")

    if "after" not in scores:
        print("FAIL — after 산출물이 없다. 먼저 node tools/verify_js_algo1.mjs 를 돌릴 것.")
        return 1

    dev = abs(float(np.mean(scores["after"])) - CANONICAL_MEAN)
    ok = dev < 3 * CANONICAL_STD
    print(f"\n판정: 편차 {dev:.5f} {'<' if ok else '>='} 3σ({3*CANONICAL_STD:.5f})  "
          f"→ {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
