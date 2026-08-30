"""run_collapse_confound.py — 위상이 무너진 곳에서 협화도가 높은 이유는 무엇인가

관찰 (미해결로 남아 있던 것)
────────────────────────────
α 스윕에서 협화도가 가장 높은 지점은 **위상이 붕괴한 양 끝**이었다:
    α=0.00 (K=1)  협화도 0.7360     α=1.00 (K=1)  0.7152
    가운데 K=13~58                   0.656 ~ 0.693

두 설명이 구별되지 않는다:
  (가) **위상 부재** — cycle 구조가 협화도를 내주고 있다
  (나) **자유 샘플링** — K=1 이면 zero-row 가 718/1088 이라 시간의 66% 가
       OM 이 아니라 노드 풀에서 뽑힌다. 풀 추출이 협화한 것뿐일 수 있다.

분리 설계 — 메커니즘만 제거한 대조군
────────────────────────────────────
정본 α=0.25 OM(zero-row 161/1088)에서 **행을 무작위로 비워** zero-row 비율을
α=0 수준(718)까지 올린다. cycle 구조는 그대로 두고 **자유 샘플링 비율만** α=0 과 맞춘다.

  · 협화도가 α=0 수준까지 오르면  → (나) 자유 샘플링이 원인. 위상은 무죄.
  · 오르지 않으면                → (가) 위상 자체가 협화도를 내주고 있다.

blanking 은 어느 행을 비우느냐에 따라 흔들리므로 **비우는 시드를 여러 개** 돌린다.

⚠ 한계: "협화도"는 대리 지표다. 이 실험은 그 지표의 원인을 가르는 것이지
   "어느 쪽이 더 좋게 들리나"에 답하지 않는다. 그것은 R3 C족(청취)이 묻는다.

실행:  python experiments/run_collapse_confound.py [--n-seeds 24]
"""
from __future__ import annotations
# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---
import argparse, json, os, pickle, time
import numpy as np
from scipy import stats

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU,
                                STEP3_DIR, consonance_score, load_continuous_om)


def run(data, om, cyc, orig, seeds):
    T = om.shape[0]
    inst = (MODULES * (T // len(MODULES) + 2))[:T]
    js, cs, nn = [], [], []
    for s in seeds:
        suite.set_all_seeds(s)
        pool = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        g = G.algorithm1_optimized(pool, list(inst), om, G.CycleSetManager(cyc),
                                   max_resample=50, verbose=False, min_onset_gap=0)
        if not g:
            continue
        js.append(pitch_distribution_similarity(g, orig)["js_divergence"])
        cs.append(consonance_score(g)); nn.append(len(g))
    return np.array(js), np.array(cs), np.array(nn)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n-seeds", type=int, default=24)
    args = ap.parse_args(); os.chdir(suite.BASE_DIR); t0 = time.time()
    print("=" * 92)
    print("위상 붕괴 지점의 높은 협화도 — 위상 부재인가, 자유 샘플링인가")
    print("=" * 92)

    data = suite.setup_hibari(); orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc25 = pickle.load(f)["cycle_labeled"]
    V = json.load(open(os.path.join(STEP3_DIR, "alpha_vineyard.json"), encoding="utf-8"))
    fr = {round(f["alpha"], 2): f for f in V["frames"]}

    def vine(a):
        f = fr[a]
        om = (np.frombuffer(f["om_bits"].encode("ascii"), dtype=np.uint8) == ord("1")
              ).reshape(f["T"], f["K"]).astype(np.float32)
        return om, {i: tuple(v) for i, v in enumerate(f["cycles"].values())}

    om0, cyc0 = vine(0.0)
    om25 = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    zr0 = int((om0.sum(1) == 0).sum()); zr25 = int((om25.sum(1) == 0).sum())
    seeds = [8000 + 31 * i for i in range(args.n_seeds)]
    print(f"\nα=0.00  K={om0.shape[1]:>2}  zero-row {zr0}/{om0.shape[0]} ({zr0/om0.shape[0]:.0%})")
    print(f"α=0.25  K={om25.shape[1]:>2}  zero-row {zr25}/{om25.shape[0]} ({zr25/om25.shape[0]:.0%})")

    print(f"\n{'조건':34} {'zero-row':>12} {'협화도':>18} {'음고 JS':>18} {'음':>7}")
    res = {}
    for name, om, cy in (("α=0.00 (위상 붕괴)", om0, cyc0), ("α=0.25 (정본)", om25, cyc25)):
        js, cs, nn = run(data, om, cy, orig, seeds)
        res[name] = (js, cs, nn)
        z = int((om.sum(1) == 0).sum())
        print(f"{name:34} {f'{z}/{om.shape[0]}':>12} {cs.mean():>11.4f}±{cs.std(ddof=1):.4f} "
              f"{js.mean():>11.5f}±{js.std(ddof=1):.5f} {nn.mean():>7.0f}")

    # ── 대조군: 정본 구조 + α=0 의 자유샘플링 비율 ──
    print(f"\n{'─'*92}\n대조군 — 정본 cycle 구조는 그대로 두고 zero-row 만 {zr0} 로 올린다")
    blanked = []
    for bs in range(5):
        rng = np.random.default_rng(500 + bs)
        om_b = om25.copy()
        cand = np.where(om_b.sum(1) > 0)[0]
        pick = rng.choice(cand, size=min(zr0 - zr25, len(cand)), replace=False)
        om_b[pick] = 0.0
        js, cs, nn = run(data, om_b, cyc25, orig, seeds)
        blanked.append((js, cs, nn))
        z = int((om_b.sum(1) == 0).sum())
        print(f"{'  비우기 시드 ' + str(bs):34} {f'{z}/{om_b.shape[0]}':>12} "
              f"{cs.mean():>11.4f}±{cs.std(ddof=1):.4f} {js.mean():>11.5f}±{js.std(ddof=1):.5f} {nn.mean():>7.0f}")

    bc = np.concatenate([b[1] for b in blanked])
    c0, c25 = res["α=0.00 (위상 붕괴)"][1], res["α=0.25 (정본)"][1]
    print(f"\n{'─'*92}\n판정")
    print(f"  α=0.25 원본        협화도 {c25.mean():.4f}")
    print(f"  α=0.25 + 행 비우기  협화도 {bc.mean():.4f}   (Δ {bc.mean()-c25.mean():+.4f})")
    print(f"  α=0.00 위상 붕괴    협화도 {c0.mean():.4f}   (Δ {c0.mean()-c25.mean():+.4f})")
    recov = (bc.mean() - c25.mean()) / (c0.mean() - c25.mean()) if c0.mean() != c25.mean() else float("nan")
    p_b = float(stats.ttest_ind(bc, c25, equal_var=False).pvalue)
    p_r = float(stats.ttest_ind(bc, c0, equal_var=False).pvalue)
    print(f"\n  자유샘플링만으로 회복된 비율 = **{recov:.0%}**")
    print(f"    비우기 vs 정본 : p={p_b:.2e} {'유의' if p_b<0.05 else '판별 불가'}")
    print(f"    비우기 vs α=0  : p={p_r:.2e} {'유의(아직 차이 남)' if p_r<0.05 else '구별 불가(=자유샘플링으로 설명됨)'}")
    verdict = ("자유 샘플링이 대부분을 설명한다 — 위상 부재 탓이 아니다" if recov > 0.7
               else ("절반 정도만 설명된다 — 두 요인이 섞여 있다" if recov > 0.3
                     else "자유 샘플링으로 설명되지 않는다 — 위상 자체가 협화도를 내준다"))
    print(f"  → {verdict}")

    json.dump({"experiment": "collapse_confound",
               "question": "위상 붕괴 지점의 높은 협화도가 위상 부재 때문인가 자유샘플링 때문인가",
               "design": "정본 OM 의 cycle 구조는 두고 zero-row 만 α=0 수준으로 올린 대조군",
               "n_seeds": args.n_seeds, "zero_rows": {"alpha0": zr0, "alpha25": zr25},
               "consonance": {"alpha25": float(c25.mean()), "alpha25_blanked": float(bc.mean()),
                              "alpha0": float(c0.mean())},
               "recovered_fraction": float(recov),
               "p_blanked_vs_canonical": p_b, "p_blanked_vs_alpha0": p_r,
               "verdict": verdict,
               "limitation": "협화도는 대리 지표다. '어느 쪽이 더 좋게 들리나' 는 R3 C족(청취)이 묻는다.",
               "total_seconds": time.time() - t0},
              open(os.path.join(STEP3_DIR, "collapse_confound.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n저장: collapse_confound.json  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
