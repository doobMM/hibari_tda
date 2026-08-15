"""run_period32_contrast_matched.py — ③ 후속: 대비를 맞춰야 모양을 비교할 수 있다

왜 필요한가
───────────
`run_period32_om.py` 1차 결론은 "combined 가 modules 대비 ρ +81%" 였다.
그런데 생성기는 지시된 대비를 **증폭**하고 증폭률이 모양마다 달라서,
그 비교는 "모양이 좋은가"가 아니라 "대비가 센가"를 재고 있었다.

**결정적 대조**: MODULES 의 *모양은 그대로* 두고 대비만 키우면(γ=3.5)
ρ 이 0.4023 → 0.6345 로 오른다(p=1.1e-18). 즉 +81%(Δ=+0.327) 중
**+0.232(71%)는 순수 대비**이고 모양의 몫은 +0.095(29%)다.
→ 대비를 맞추는 것은 정당하다.

그런데 2차 결론("combined 가 om 보다 나쁘다")도 성급했다.
**모양마다 도달 가능한 대비 범위가 다르므로**, 한 지점에서만 맞춰 비교하면
그 지점이 어느 모양에 유리한지에 따라 순위가 바뀐다. 그래서 **두 지점**에서 잰다.

한계 (먼저 적는다)
──────────────────
· MODULES 는 값이 3/4 뿐이라 정수 반올림 때문에 실현 대비 0.6 에 도달하지 못한다.
· om 은 γ=8 에서도 0.99 에 도달하지 못한다.
  → 대비 정렬은 **근사**이며, 각 비교에서 실현 대비를 함께 보고한다.

실행:  python experiments/run_period32_contrast_matched.py [--n-seeds 20]
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
import run_period32_om as P
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, load_continuous_om,
)

SHAPES = ["modules", "om", "phase32", "combined"]
TARGETS = [0.99, 0.60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()
    os.chdir(TDA_ROOT)
    t0 = time.time()

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    om = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    T = om.shape[0]
    half = (T // 2 // P.PERIOD) * P.PERIOD
    P.OFFSET = half
    om_te, Tte = om[half:], T - half
    mods_full = np.array((MODULES * (T // P.PERIOD + 2))[:T], float)
    mods_te = mods_full[half:]
    cnt_tr = P.onset_counts(orig, 0, half)
    cnt_te = P.onset_counts(orig, half, T)
    prof_tr = P.phase_profile(cnt_tr, 0)
    Xtr = np.column_stack([om[:half].sum(1), prof_tr[np.arange(half) % P.PERIOD], np.ones(half)])
    P.BETA, *_ = np.linalg.lstsq(Xtr, cnt_tr, rcond=None)
    budget = int(mods_te.sum())
    po = P.phase_profile(cnt_te, P.OFFSET)
    orig_contrast = float(po.std() / po.mean())

    seeds = [3000 + 41 * i for i in range(args.n_seeds)]
    shapes = P.build_shapes(om_te, prof_tr, mods_te, np.random.default_rng(seeds[0]))

    def run(shape, gam, ss):
        inst = P.scale_to_budget(P.shrink(shape, gam), budget)
        rho, js, con, rc = [], [], [], []
        for s in ss:
            random.seed(s); np.random.seed(s)
            pool = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
            g = G.algorithm1_optimized(pool, list(inst), om_te, G.CycleSetManager(cyc),
                                       max_resample=50, verbose=False, min_onset_gap=0)
            c = P.onset_counts(g, 0, Tte)
            rho.append(float(np.corrcoef(c, cnt_te)[0, 1]))
            js.append(pitch_distribution_similarity(g, orig)["js_divergence"])
            con.append(consonance_score(g))
            pf = P.phase_profile(c, P.OFFSET)
            rc.append(pf.std() / pf.mean())
        return np.array(rho), np.array(js), np.array(con), float(np.mean(rc))

    def find_gamma(shape, target):
        lo, hi = 0.05, 8.0
        for _ in range(18):
            mid = 0.5 * (lo + hi)
            if run(shape, mid, seeds[:5])[3] < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    print("=" * 88)
    print("③ 후속 — 실현 대비를 맞춰 '모양'만 비교한다")
    print(f"원곡 실현 대비 = {orig_contrast:.4f}")
    print("=" * 88)

    # ── 대조 A: 모양 고정, 대비만 키우기 ──
    r0, _, _, c0 = run(shapes["modules"], 1.0, seeds)
    r1, _, _, c1 = run(shapes["modules"], 3.5, seeds)
    p_amp = float(stats.ttest_rel(r1, r0).pvalue)
    print(f"\n[대조 A] MODULES 모양 그대로 대비만 ↑ : ρ {r0.mean():.4f}(대비 {c0:.3f}) "
          f"→ {r1.mean():.4f}(대비 {c1:.3f})  Δ={r1.mean()-r0.mean():+.4f} p={p_amp:.2e}")
    print("         → 대비만으로 ρ 가 오른다. 대비를 맞추지 않은 비교는 무효다.")

    out = {"experiment": "period32_contrast_matched",
           "original_contrast": orig_contrast,
           "contrast_only_control": {"rho_gamma1": float(r0.mean()), "rho_gamma3p5": float(r1.mean()),
                                     "contrast_gamma1": c0, "contrast_gamma3p5": c1, "p": p_amp},
           "levels": {}}

    for tgt in TARGETS:
        print(f"\n[목표 실현 대비 {tgt}]")
        print(f"  {'모양':10} {'γ':>7} {'실현대비':>8} {'리듬상관 ρ':>17} {'음고 JS':>17} {'협화도':>9}")
        store, lvl = {}, {}
        for name in SHAPES:
            g = find_gamma(shapes[name], tgt)
            r, j, cs, rc = run(shapes[name], g, seeds)
            store[name] = r
            lvl[name] = {"gamma": float(g), "realized_contrast": rc,
                         "rho": [float(r.mean()), float(r.std(ddof=1))],
                         "pitch_js": [float(j.mean()), float(j.std(ddof=1))],
                         "consonance": [float(cs.mean()), float(cs.std(ddof=1))],
                         "rho_all": [float(x) for x in r]}
            print(f"  {name:10} {g:>7.3f} {rc:>8.4f} {r.mean():>10.4f}±{r.std(ddof=1):.4f} "
                  f"{j.mean():>10.5f}±{j.std(ddof=1):.5f} {cs.mean():>9.4f}")
        tests = {}
        for a, b in (("combined", "om"), ("combined", "modules"),
                     ("om", "modules"), ("combined", "phase32"), ("phase32", "modules")):
            p = float(stats.ttest_rel(store[a], store[b]).pvalue)
            d = float(store[a].mean() - store[b].mean())
            tests[f"{a}_vs_{b}"] = {"delta": d, "p": p}
            print(f"     {a:9} vs {b:9} Δ={d:+.4f} p={p:.2e} {'유의' if p < 0.05 else '판별 불가'}")
        out["levels"][str(tgt)] = {"arms": lvl, "tests": tests}

    # ── 두 지점에서 부호가 일치하는가 = 견고한가 ──
    print(f"\n{'─'*88}\n견고성 — 두 대비 지점에서 부호가 같은가")
    for k in out["levels"][str(TARGETS[0])]["tests"]:
        a = out["levels"][str(TARGETS[0])]["tests"][k]
        b = out["levels"][str(TARGETS[1])]["tests"][k]
        same = (a["delta"] > 0) == (b["delta"] > 0)
        print(f"  {k:26} {a['delta']:+.4f} / {b['delta']:+.4f}   "
              f"{'견고' if same else '★ 부호 뒤집힘 — 판별 불가'}")
        out["levels"].setdefault("robustness", {})[k] = {
            "delta_hi": a["delta"], "delta_lo": b["delta"], "sign_consistent": bool(same)}

    out["total_seconds"] = time.time() - t0
    path = os.path.join(STEP3_DIR, "period32_contrast_matched.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
