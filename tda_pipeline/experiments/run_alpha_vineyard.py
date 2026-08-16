"""run_alpha_vineyard.py — B1 1단계: α 를 쓸어 cycle 의 탄생·소멸을 잇는다

동기 (문헌)
───────────
지금 툴은 **위상이 얼어 있다.** K=14 cycle 을 미리 계산해 두고 사용자는 활성화만 토글한다.
α(하이브리드 계수)를 바꾸면 위상 자체가 바뀌지만 PH 재계산이 ~19초라 실시간이 불가능하다.

Vineyard(Cohen-Steiner–Edelsbrunner–Morozov 2006)는 필트레이션이 변할 때 persistence 를
transposition 단위로 갱신한다. 그런데 Piekenbrock–Perea(2024, `s41468-023-00156-3.pdf`)는
**"vineyards 는 1-파라미터 족이 성길 때 특히 비효율적"** 이고 moves 조차 재계산 대비 3배
수준이라고 보고한다. Lesnick–Wright 인용도 같은 취지다 —
*"transposition 이 많으면 그냥 다시 계산하는 편이 훨씬 빠를 때가 있다."*

우리 슬라이더는 **성긴 족**이다(이산 정지점 수십 개). 따라서 동적 갱신 엔진을 만들 이유가 없다.
→ **오프라인에서 α 를 쓸어 미리 계산하고, 브라우저는 색인만 한다.**
   (Ponytail 사다리: "애초에 만들어야 하나" 에서 멈춘다)

이 스크립트가 만드는 것
───────────────────────
1. α 격자마다 PH 를 돌려 `cycle_labeled`(각 cycle 의 note 인덱스)와 OM 밀도를 저장
2. 인접 α 사이 cycle 을 **Jaccard 최대 매칭**으로 이어 vine 을 만든다
   → "이 cycle 은 α=0.35 에서 태어나 α=0.62 에서 죽는다" 를 UI 가 그릴 수 있다
3. 브라우저용 JSON 하나

⚠ 한계: 이것은 진짜 vineyard(연속 추적)가 아니라 **격자 표본 + 사후 매칭**이다.
   격자 사이에서 일어나는 교환은 보이지 않는다. 정지점 수를 늘리면 촘촘해질 뿐이다.
   진짜 연속 추적이 필요해지면 그때 vineyard 를 구현한다.

실행:  python experiments/run_alpha_vineyard.py [--step 0.05] [--metric dft]
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

import run_dft_gap0_suite as suite


def jaccard(a: set, b: set) -> float:
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--metric", default="dft")
    ap.add_argument("--match-threshold", type=float, default=0.5,
                    help="인접 α 사이 cycle 을 같은 vine 으로 볼 최소 Jaccard")
    args = ap.parse_args()
    os.chdir(suite.BASE_DIR)
    t0 = time.time()

    alphas = [round(a, 4) for a in np.arange(0.0, 1.0 + 1e-9, args.step)]
    print("=" * 88)
    print(f"B1 1단계 — α vineyard ({args.metric}, {len(alphas)}점, step={args.step})")
    print("=" * 88)

    data = suite.setup_hibari()
    frames = []
    for i, a in enumerate(alphas):
        b = suite.build_overlap_bundle(data, args.metric, alpha=a)
        cyc = b["cycle_labeled"]
        cont = np.asarray(b["activation_continuous"])
        ob = np.asarray(b["overlap_binary"])
        frames.append({
            "alpha": a, "K": len(cyc),
            "cycles": {str(k): sorted(int(x) for x in v) for k, v in cyc.items()},
            "om_density": float(ob.mean()),
            "zero_rows": int((ob.sum(1) == 0).sum()),
            "T": int(ob.shape[0]),
            "ph_time_s": b.get("ph_time_s"),
        })
        print(f"  α={a:<5} K={len(cyc):>3}  OM 밀도={ob.mean():.4f}  "
              f"zero-row={int((ob.sum(1)==0).sum()):>4}/{ob.shape[0]}  ({b.get('ph_time_s')}s)")

    # ── 인접 α 사이 매칭 → vine ──
    print(f"\n{'─'*88}\nvine 구성 (Jaccard ≥ {args.match_threshold})")
    vines, active = [], {}          # active: 현 프레임 cycle key → vine id
    for i, f in enumerate(frames):
        cur = {k: set(v) for k, v in f["cycles"].items()}
        nxt = {}
        if i == 0:
            for k in cur:
                vines.append({"vine": len(vines), "birth_alpha": f["alpha"],
                              "death_alpha": None, "members": [sorted(cur[k])]})
                nxt[k] = len(vines) - 1
        else:
            prev = {k: set(v) for k, v in frames[i - 1]["cycles"].items()}
            used = set()
            # 탐욕 최대 Jaccard 매칭
            pairs = sorted(((jaccard(cur[c], prev[p]), c, p) for c in cur for p in prev),
                           reverse=True)
            for s, c, p in pairs:
                if s < args.match_threshold or c in nxt or p in used:
                    continue
                nxt[c] = active[p]; used.add(p)
                vines[active[p]]["members"].append(sorted(cur[c]))
            for k in cur:                       # 매칭 실패 = 새로 태어남
                if k not in nxt:
                    vines.append({"vine": len(vines), "birth_alpha": f["alpha"],
                                  "death_alpha": None, "members": [sorted(cur[k])]})
                    nxt[k] = len(vines) - 1
            for p, vid in active.items():       # 이어지지 않음 = 죽음
                if p not in used and vines[vid]["death_alpha"] is None:
                    vines[vid]["death_alpha"] = f["alpha"]
        active = nxt

    born = sum(1 for v in vines if v["birth_alpha"] > alphas[0])
    died = sum(1 for v in vines if v["death_alpha"] is not None)
    survived = sum(1 for v in vines if v["death_alpha"] is None)
    print(f"  vine {len(vines)}개 · 도중 탄생 {born} · 소멸 {died} · 끝까지 생존 {survived}")
    longest = max(vines, key=lambda v: len(v["members"]))
    print(f"  가장 긴 vine: #{longest['vine']} — α={longest['birth_alpha']} 부터 "
          f"{len(longest['members'])}프레임 지속, note {longest['members'][0]}")

    out = {
        "experiment": "alpha_vineyard",
        "method": ("α 격자마다 PH 를 다시 돌리고 인접 격자 사이 cycle 을 Jaccard 최대 매칭으로 잇는다. "
                   "진짜 연속 vineyard 가 아니라 격자 표본 + 사후 매칭이다 — "
                   "격자 사이의 교환은 보이지 않는다."),
        "literature": {
            "why_not_dynamic": ("Piekenbrock & Perea (2024) — vineyards 는 1-파라미터 족이 성길 때 "
                                "특히 비효율적이고 moves 도 재계산 대비 3배 수준. "
                                "우리 슬라이더는 성긴 족이므로 오프라인 사전계산이 맞다."),
            "refs": ["s41468-023-00156-3.pdf", "1137856.1137877.pdf", "2510.24472v2.pdf"],
        },
        "config": {"metric": args.metric, "step": args.step, "alphas": alphas,
                   "match_threshold": args.match_threshold},
        "frames": frames,
        "vines": vines,
        "summary": {"n_vines": len(vines), "born_midway": born,
                    "died": died, "survived": survived},
        "total_seconds": time.time() - t0,
    }
    path = os.path.join(suite.STEP3_DIR, "alpha_vineyard.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
