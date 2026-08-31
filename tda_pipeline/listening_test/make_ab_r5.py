"""make_ab_r5.py — R5 판별 회차. 손잡이가 **들리는가**를 묻는다

목표가 바뀌었다 (2026-08-31, 사용자)
────────────────────────────────
    "상호작용과, 쉽게 음악을 내 의도대로 만들 수 있다는 감각만 주어지면 충분하다."

그러면 성공 기준이 "원곡에 가까운가"가 아니라 **"내 조작이 들리고 의도한 방향으로
가는가"** 다. 그리고 그 질문은 선호가 아니라 **판별**로 물어야 한다.

    선호("어느 쪽이 좋나")  — 정답 없음. 참 일치율 61% 기준 **74쌍** 필요
    판별("어느 쪽이 촘촘한가") — **정답 있음**. 정답률 80% 면 **9쌍**이면 끝

12쌍 = 밀도 3 + 음역 3 + 온도 3 + 귀무 3
  · 세기 3단계(약·중·강)로 **역치**를 본다. 슬라이더 눈금이 그 결과다.
  · 귀무 3쌍은 시드만 다르고 지표 차이가 **정확히 0** 이다. 여기서 맞힌다고 답하면
    그 질문이 무의미하거나 응답자가 추측하고 있다는 뜻이다.

자극은 `tools/make_r5_notes.mjs` 가 **배포 JS 를 그대로 돌려** 만든다 —
시험 대상이 파이썬 정본이 아니라 사용자가 실제로 만지는 코드이기 때문이다.

실행:  node tools/make_r5_notes.mjs  &&  python listening_test/make_ab_r5.py
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_ROOT = _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__)))
_rp_sys.path.insert(0, _ROOT)
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "experiments"))
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "tools"))
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.abspath(__file__)))
# --- end path_bootstrap ---

import json
import os

from run_topo_diffusion import TDA_ROOT
from make_topo_music import SEC_PER_8TH, render_wav, write_midi
from make_ab_check import to_ogg
from make_ab_p4 import PAGE

SRC = os.path.join(TDA_ROOT, "tools", "verify", "r5_notes.json")
OUT = os.path.join(TDA_ROOT, "output", "ab_r5")
FAM = {"density": "밀도", "register": "음역", "temperature": "온도", "null": "귀무"}


def main():
    os.makedirs(OUT, exist_ok=True)
    src = json.load(open(SRC, encoding="utf-8"))
    pairs = src["pairs"]

    print("=" * 96)
    print("R5 판별 회차 — 손잡이가 들리는가 (자극은 배포 JS 산출)")
    print("=" * 96)
    print(f"{'쌍':5} {'축':6} {'세기':20} {'지표차':>9} {'잡음σ배':>8} {'음 A/B':>10}  정답")

    blocks, key = [], {}
    for p in pairs:
        pid = p["id"]
        for side in ("A", "B"):
            stem = f"{pid}{side}"
            mid = os.path.join(OUT, stem + ".mid")
            wav = os.path.join(OUT, stem + ".wav")
            write_midi([tuple(n) for n in p[f"notes{side}"]], mid)
            render_wav(mid, wav)
            to_ogg(wav, os.path.join(OUT, stem + ".ogg"))
            os.remove(wav)
        key[pid] = {k: p[k] for k in
                    ("family", "question", "strength", "window", "metric",
                     "valueA", "valueB", "delta", "noise_sigma",
                     "effect_in_sigma", "truth", "seedA", "seedB", "nA", "nB")}
        nn = "%d/%d" % (p["nA"], p["nB"])
        print(f"{pid:5} {FAM[p['family']]:6} {p['strength']:20} "
              f"{p['delta']:>9.2f} {(p['effect_in_sigma'] or 0):>8.1f} {nn:>10}  "
              f"{p['truth'] or '— (정답 없음)'}")

        blocks.append(
            f'<div class="pair"><div class="pn">{pid} / {len(pairs)}</div>'
            f'<div class="pt">{p["question"]}</div>'
            f'<div class="side"><label>A</label>'
            f'<audio controls preload="none" src="{pid}A.ogg"></audio></div>'
            f'<div class="side"><label>B</label>'
            f'<audio controls preload="none" src="{pid}B.ogg"></audio></div>'
            f'<div class="choices">'
            f'<button data-pair="{pid}" data-val="A">A</button>'
            f'<button data-pair="{pid}" data-val="B">B</button>'
            f'<button data-pair="{pid}" data-val="?">구별 안 됨</button></div>'
            f'<textarea data-pair="{pid}" placeholder="이유 한 줄 (선택)"></textarea></div>')

    page = (PAGE.replace("__PAIRS__", "\n".join(blocks))
                .replace("__N__", str(len(pairs)))
                .replace("AB-P4 ", "AB-R5 ")
                .replace("각 약 15초 · <b>5분이면 끝납니다</b>",
                         "각 약 15초 · <b>8분쯤 걸립니다</b>. "
                         "이번에는 <b>취향이 아니라 사실</b>을 묻습니다 — "
                         "정답이 있는 문제이고, 정답이 없는 문제도 섞여 있습니다"))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)

    json.dump({"experiment": "R5 — 손잡이 판별 회차",
               "goal": ("사용자 목표 재정의(2026-08-31): '내 의도대로 만들 수 있다는 감각'. "
                        "따라서 선호가 아니라 판별을 묻는다."),
               "generator": src["generator"],
               "tilt_calibration_semitones": src["tilt_calibration_semitones"],
               "noise_floor_sd": src["noise_floor_sd"],
               "analysis_plan_fixed_before_listening": {
                   "primary": "축마다 3쌍의 정답률. 귀무 3쌍은 정답이 없으므로 "
                              "'구별 안 됨' 이 아닌 응답을 **거짓 양성**으로 센다",
                   "threshold": "약/중/강 중 어디서부터 맞히는지가 슬라이더 눈금 근거다",
                   "invalidation": "귀무 3쌍에서 2개 이상 확신 응답이 나오면 "
                                   "그 회차의 판별 결과를 신뢰하지 않는다",
                   "note": "12쌍·청취자 1명. 축 하나당 3쌍이라 통계가 아니라 **신호 유무** 를 본다"},
               "n_pairs": len(pairs), "seconds_each": round(60 * SEC_PER_8TH, 1),
               "key": key,
               "note": "이 파일을 먼저 열지 마세요 — 정답이 들어 있습니다."},
              open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n페이지: {os.path.join(OUT, 'index.html')}")


if __name__ == "__main__":
    main()
