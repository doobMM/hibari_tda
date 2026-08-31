"""make_ab_r4.py — 확증 회차. 사전등록한 역동성 가설을 **독립변수를 흔들어** 시험한다

왜 새 회차가 필요한가
─────────────────────
사전등록(`docs/step3_data/PREREG_dynamism_2026-08-31.md`, 커밋 47e10a7)은 기존 19쌍을
**탐색 전용**으로 못박았다 — 가설이 그 쌍들의 코멘트에서 나왔으므로 순환이다.
실제로 탐색에서 넷 다 실패했다(`dynamism_metrics.json`, 커밋 115e502).

다만 그 표본은 **역동성을 조작한 적이 없다.** NodePool 수정·OM 출처·α 를 흔들었을 뿐이라
쌍 안의 역동성 차이가 작았다(예: P1 M4 0.307 vs 0.282, +9%). 검정력이 낮다.

R4 설계 — 오직 시드만 다르다
────────────────────────────
창(32스텝)·OM·설정·온도를 **완전히 고정**하고 **시드만** 바꿔 60개 후보를 만든 뒤,
목표 지표의 격차가 가장 큰 쌍을 고른다. 단 **음 수는 10% 이내**로 맞춘다(MCP).

  → 두 팔의 차이는 난수 하나뿐이다. 위상·α·버그수정 상태와 교란되지 않는다.
  → 탐침 결과 달성 가능한 격차: M1 +14~20% · M2 +120~194% · M3 +33~53% · M4 +25~42%
     (탐색 표본의 ~9% 보다 훨씬 크다)

창 3개 × 목표지표 4종 = 12쌍. 창은 노출도(zero-row)가 서로 달라 일반화 폭이 넓다.

**분석 계획은 청취 전에 고정한다** (사전등록 §5 그대로):
  · 지표마다 12쌍 전부에서 "선택된 쪽의 값이 더 큰가" 이항검정(양측)
    — 자기 목표 쌍 3개만 보지 않는다. 그러면 조작으로 만든 방향을 자기가 채점하게 된다.
  · Holm 보정 4종 · r(지표값, 음 수) 병기, |r|>0.4 면 유보
  · 성공 = 최소 하나가 Holm 후 유의 + 예측 방향(선택된 쪽이 **높다**)

⚠ 사전 경고 — M3 은 이미 실격 후보다. 1단계 대조군에서 백색잡음이 2.999 로
   2위(1.447)의 두 배를 받았다. R4 에서 M3 이 이겨도 "잡음스러움"을 잰 것일 수 있다.

실행:  python listening_test/make_ab_r4.py [--shuffle-seed N]
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

import argparse, json, os, pickle, random
import numpy as np

import run_dft_gap0_suite as suite
from run_topo_diffusion import CACHE_DIR, CACHE_NAME, REAL_TAU, TDA_ROOT, load_continuous_om
from run_dynamism_metrics import KEYS, LABEL, dynamism
from make_topo_music import SEC_PER_8TH, render_wav, write_midi
from make_ab_check import gen, to_ogg
from make_ab_p4 import PAGE

OUT = os.path.join(TDA_ROOT, "output", "ab_r4")
T = 32                      # 32스텝 ≈ 14.5초 — R3 와 동일
TEMPERATURE = 1.0           # 정본 경로와 동일 (T=3.0 주장은 철회됐다)
WINDOWS = [0, 192, 384]     # zero-row 16/32 · 6/32 · 1/32 — 노출도가 다르다
SEEDS = list(range(9000, 9060))
TOL = 0.10                  # MCP — 음 수 평균 차이 허용치


def pick(cands, key, used):
    """음 수 10% 이내로 맞춘 쌍 중 `key` 격차가 최대인 (높은쪽, 낮은쪽)."""
    best = (0.0, None, None)
    for i, ci in enumerate(cands):
        for j, cj in enumerate(cands):
            if i == j or ci["seed"] in used or cj["seed"] in used:
                continue
            gap = abs(ci["n"] - cj["n"]) / max(1, (ci["n"] + cj["n"]) / 2)
            d = ci["m"][key] - cj["m"][key]
            if gap <= TOL and d > best[0]:
                best = (d, i, j)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffle-seed", type=int, default=20260901)
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    os.makedirs(OUT, exist_ok=True)

    data = suite.setup_hibari()
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    full = load_continuous_om()

    print("=" * 100)
    print("R4 — 확증 회차. 창·OM·설정 고정, **시드만** 다른 쌍으로 역동성을 조작한다")
    print("=" * 100)

    pairs = []
    for off in WINDOWS:
        om = (full[off:off + T] >= REAL_TAU).astype(np.float32)
        zr = int((om.sum(1) == 0).sum())
        cands = []
        for s in SEEDS:
            g = gen(data, cyc, om, s, temperature=TEMPERATURE)
            cands.append({"seed": s, "notes": g, "n": len(g), "m": dynamism(g)})
        used = set()
        print(f"\n창 off={off}  zero-row={zr}/{T}")
        for k in KEYS:
            d, i, j = pick(cands, k, used)
            if i is None:
                print(f"  {LABEL[k]:16} 조건을 만족하는 쌍 없음 — 건너뜀")
                continue
            hi, lo = cands[i], cands[j]
            used |= {hi["seed"], lo["seed"]}
            pairs.append({"window": off, "zero_rows": zr, "target": k,
                          "high": hi, "low": lo})
            print(f"  {LABEL[k]:16} 격차 {d:+.3f} ({d / max(1e-9, lo['m'][k]):+.0%}) "
                  f"시드 {hi['seed']}(높음)/{lo['seed']}(낮음) "
                  f"음 {hi['n']}/{lo['n']} (차이 "
                  f"{abs(hi['n'] - lo['n']) / ((hi['n'] + lo['n']) / 2):.1%})")

    # ── 블라인드 배치 ──
    # 단순 무작위로 섞으면 **지표 방향이 한쪽으로 쏠린다**. 실제로 첫 시도에서
    # M4 가 12쌍 중 10쌍에서 "A 가 높음" 이 됐다 — 청취자에게 A 선호가 조금만 있어도
    # 그 지표가 공짜로 점수를 얻는다. 그래서 네 지표 **모두** 6/6 에 가깝도록
    # 뒤집기 패턴을 고른다. 청취 전에 정하는 설계 결정이고, 정답은 여전히 가려져 있다.
    def imbalance(flip):
        worst = 0
        for k in KEYS:
            a = 0
            for p, f in zip(pairs, flip):
                arms = [p["low"], p["high"]] if f else [p["high"], p["low"]]
                a += arms[0]["m"][k] > arms[1]["m"][k]
            worst = max(worst, abs(a - len(pairs) / 2))
        return worst

    rng = random.Random(args.shuffle_seed)
    flips = [rng.random() < 0.5 for _ in pairs]
    for _ in range(4000):
        c = [rng.random() < 0.5 for _ in pairs]
        if imbalance(c) < imbalance(flips):
            flips = c
        if imbalance(flips) == 0:
            break
    print(f"\n배치 균형: 네 지표의 'A 가 높음' 쏠림 최대 {imbalance(flips):.0f}쌍 "
          f"(6/6 이 완전균형)")

    key, blocks = {}, []
    print(f"\n{'-' * 100}\n{'쌍':5} {'목표':16} {'창':>5} {'A 정체':>8} {'음 A/B':>10}")
    for idx, (p, flip) in enumerate(zip(pairs, flips), 1):
        pid = f"S{idx}"
        arms = [("높음", p["high"]), ("낮음", p["low"])]
        if flip:
            arms.reverse()
        key[pid] = {"target": p["target"], "window": p["window"],
                    "zero_rows": p["zero_rows"],
                    "A": {"role": arms[0][0], "seed": arms[0][1]["seed"],
                          "n": arms[0][1]["n"], "metrics": arms[0][1]["m"]},
                    "B": {"role": arms[1][0], "seed": arms[1][1]["seed"],
                          "n": arms[1][1]["n"], "metrics": arms[1][1]["m"]}}
        for L, (_, c) in zip("AB", arms):
            stem = f"{pid}{L}"
            mid = os.path.join(OUT, stem + ".mid")
            wav = os.path.join(OUT, stem + ".wav")
            write_midi(c["notes"], mid)
            render_wav(mid, wav)
            to_ogg(wav, os.path.join(OUT, stem + ".ogg"))
            os.remove(wav)
        nn = "%d/%d" % (arms[0][1]["n"], arms[1][1]["n"])
        print(f"{pid:5} {LABEL[p['target']]:16} {p['window']:>5} {arms[0][0]:>8} {nn:>10}")
        blocks.append(
            f'<div class="pair"><div class="pn">{pid} / {len(pairs)}</div>'
            f'<div class="pt">어느 쪽이 더 마음에 드나요?</div>'
            f'<div class="side"><label>A</label><audio controls preload="none" src="{pid}A.ogg"></audio></div>'
            f'<div class="side"><label>B</label><audio controls preload="none" src="{pid}B.ogg"></audio></div>'
            f'<div class="choices">'
            f'<button data-pair="{pid}" data-val="A">A</button>'
            f'<button data-pair="{pid}" data-val="B">B</button>'
            f'<button data-pair="{pid}" data-val="?">모르겠다</button></div>'
            f'<textarea data-pair="{pid}" placeholder="이유 한 줄 (선택)"></textarea></div>')

    page = (PAGE.replace("__PAIRS__", "\n".join(blocks))
                .replace("__N__", str(len(pairs)))
                .replace("AB-P4 ", "AB-R4 ")
                .replace("각 약 15초 · <b>5분이면 끝납니다</b>",
                         "각 약 15초 · <b>8분쯤 걸립니다</b>"))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)

    json.dump({"experiment": "R4 — 사전등록 역동성 가설 확증 회차",
               "prereg": "docs/step3_data/PREREG_dynamism_2026-08-31.md (commit 47e10a7)",
               "design": ("창·OM·설정·온도를 고정하고 시드만 바꾼 60후보 중 "
                          "목표 지표 격차가 최대인 쌍을 고른다. 음 수는 10% 이내(MCP). "
                          "두 팔의 차이는 난수 하나뿐이다."),
               "analysis_plan_fixed_before_listening": {
                   "test": "지표마다 12쌍 **전부**에서 '선택된 쪽의 값이 더 큰가' 이항검정(양측, H0=0.5)",
                   "why_all_pairs": "자기 목표 쌍 3개만 채점하면 조작으로 만든 방향을 자기가 채점한다",
                   "correction": "Holm (지표 4종)",
                   "withhold_rule": "r(지표값, 음 수) 의 |r|>0.4 면 그 지표 결과 유보",
                   "success": "최소 하나가 Holm 후 p<0.05 이고 예측 방향(선택된 쪽이 높다)",
                   "failure": "넷 다 비유의거나 방향이 반대 — 다른 지표를 찾아 붙이지 않는다"},
               "n_pairs": len(pairs), "T_steps": T,
               "seconds_each": round(T * SEC_PER_8TH, 1),
               "temperature": TEMPERATURE, "windows": WINDOWS,
               "shuffle_seed": args.shuffle_seed, "mcp_tolerance": TOL,
               "caveat_M3": ("1단계 대조군에서 백색잡음이 M3 최고값(2.999, 2위의 2배)을 받았다. "
                             "M3 이 이겨도 '잡음스러움'을 잰 것일 수 있다."),
               "key": key,
               "note": "이 파일을 먼저 열지 마세요 — 블라인드가 깨집니다."},
              open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n페이지: {os.path.join(OUT, 'index.html')}")


if __name__ == "__main__":
    main()
