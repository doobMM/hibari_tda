"""run_period32_om.py — ③ 32주기 리듬 구조를 OM 과 결합한다

배경
────
원곡 hibari 의 시점별 타건 수를 무엇이 잘 예측하는가 (후반 held-out Pearson):

    OM 활성 cycle 수          0.571
    MODULES 고정 스케줄        0.584   ← 지금 생성기가 쓰는 것
    32주기 평균 프로파일        0.693
    OM + 32주기 결합           0.779

`corr(OM, 32주기) = 0.366` 으로 낮다 — **서로 다른 정보**다.
생성기의 `inst_len[j]`(그 시점에 뽑을 음의 개수)는 지금 MODULES 만 본다.
여기에 32주기 프로파일을 얹으면 리듬이 원곡에 가까워지는가?

설계 — 세 가지 함정을 미리 막는다
─────────────────────────────────
1. **"음을 더 냈을 뿐" 아티팩트 (T4 전례).**
   `inst_len` 은 지속음 때문에 동적으로 줄어든다(MODULES 3~4 인데 실제 1.80음/스텝).
   그래서 원곡 타건 수에 직접 적합하면 총량이 흔들린다.
   → **모든 팔의 총 예산을 baseline 과 같게 스케일한다.** 팔들은 "몇 개를 내느냐"가
     아니라 **"어디에 놓느냐"만** 다르다. 아티팩트가 구조적으로 배제된다.

2. **동어반복.** 프로파일을 hibari 로 적합하고 hibari 로 평가하면 당연히 이긴다.
   → **전반부로 적합, 후반부에서만 생성·평가**한다.

3. **메커니즘 뺀 대조군 (오늘 두 번 헤드라인을 살린 교훈).**
   → `*_shuffled`: 같은 프로파일 값을 쓰되 **위상을 무작위로 섞는다.**
     숫자의 분포는 같고 32주기 정렬만 파괴된다.
     이게 baseline 수준이면 "32주기 정렬"이 진짜 원인이고,
     이게 똑같이 좋으면 프로파일의 **모양**이 아니라 값의 분산이 한 일이다.

**사전 예측 (실행 전에 적는다)**
  · 리듬 프로파일 상관: combined > phase32 > om ≈ modules, 그리고 shuffled 는 modules 수준.
  · **음고 JS 는 예측하지 않는다** — `inst_len` 은 음 선택이 아니라 시점별 개수를 바꾼다.
    방향을 모른다. 사후에 좋은 쪽을 골라 이야기를 만들지 않기 위해 미리 적어 둔다.

실행:  python experiments/run_period32_om.py [--n-seeds 20]
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

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, load_continuous_om,
)

PERIOD = 32
PREDICTION = ("리듬 프로파일 상관: combined > phase32 > om ≈ modules, shuffled 는 modules 수준. "
              "음고 JS 는 방향을 예측하지 않는다.")


def onset_counts(notes, t0, t1):
    """[t0,t1) 구간의 시점별 타건 수."""
    c = np.zeros(t1 - t0)
    for n in notes:
        s = int(n[0])
        if t0 <= s < t1:
            c[s - t0] += 1
    return c


def phase_profile(counts, offset):
    """counts[i] 가 절대시점 offset+i 일 때, 위상별 평균 타건 수."""
    p = np.zeros(PERIOD)
    idx = np.arange(len(counts)) + offset
    for r in range(PERIOD):
        sel = counts[(idx % PERIOD) == r]
        p[r] = sel.mean() if len(sel) else 0.0
    return p


def scale_to_budget(shape, budget):
    """모양은 유지하고 총합만 budget 에 맞춘 정수 벡터."""
    shape = np.clip(np.asarray(shape, dtype=float), 0.0, None)
    if shape.sum() <= 0:
        shape = np.ones_like(shape)
    v = shape * (budget / shape.sum())
    out = np.maximum(0, np.round(v)).astype(int)
    # 반올림 잔차를 큰 항부터 ±1 로 보정해 총합을 정확히 맞춘다
    diff = int(budget - out.sum())
    if diff:
        order = np.argsort(-v if diff > 0 else -out.astype(float))
        for i in range(abs(diff)):
            j = order[i % len(order)]
            out[j] += 1 if diff > 0 else (-1 if out[j] > 0 else 0)
    return out


def shrink(shape, gamma):
    """평균 쪽으로 대비를 줄인다. gamma=1 이면 그대로, 0 이면 완전 평탄."""
    s = np.asarray(shape, dtype=float)
    m = s.mean()
    return m + gamma * (s - m)


def build_shapes(om_test, prof_train, mods_test, rng, offset=None):
    """팔별 inst_len 모양. 전부 같은 예산으로 스케일된다."""
    OFFSET_ = OFFSET if offset is None else offset
    T = len(mods_test)
    om_row = om_test.sum(1)
    prof_full = prof_train[(np.arange(T) + OFFSET_) % PERIOD]

    # OM + 32주기 결합: 전반부에서 적합한 계수를 쓴다
    X = np.column_stack([om_row, prof_full, np.ones(T)])
    comb = X @ BETA

    perm = rng.permutation(PERIOD)                 # 위상만 섞는다 (값 분포는 동일)
    prof_shuf = prof_train[perm][(np.arange(T) + OFFSET_) % PERIOD]
    comb_shuf = np.column_stack([om_row, prof_shuf, np.ones(T)]) @ BETA

    return {
        "modules":           mods_test.astype(float),
        "om":                om_row.astype(float),
        "phase32":           prof_full,
        "combined":          comb,
        "phase32_shuffled":  prof_shuf,
        "combined_shuffled": comb_shuf,
    }


def main():
    global OFFSET, BETA, GAMMA
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t0 = time.time()
    print("=" * 88)
    print("③ 32주기 리듬 구조 × OM — inst_len 을 어디에 놓을 것인가")
    print(f"  사전 예측: {PREDICTION}")
    print("=" * 88)

    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]
    om = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    T = om.shape[0]

    half = (T // 2 // PERIOD) * PERIOD          # 32의 배수로 잘라 위상을 보존
    OFFSET = half
    om_test = om[half:]
    Ttest = om_test.shape[0]
    mods_full = np.array((MODULES * (T // PERIOD + 2))[:T], dtype=float)
    mods_test = mods_full[half:]

    # ── 전반부에서만 적합 ──
    cnt_train = onset_counts(orig, 0, half)
    cnt_test = onset_counts(orig, half, T)
    prof_train = phase_profile(cnt_train, 0)
    Xtr = np.column_stack([om[:half].sum(1),
                           prof_train[np.arange(half) % PERIOD],
                           np.ones(half)])
    BETA, *_ = np.linalg.lstsq(Xtr, cnt_train, rcond=None)
    print(f"\n적합 구간 [0,{half}) · 평가 구간 [{half},{T})  ({Ttest} 스텝)")
    print(f"결합 계수  om={BETA[0]:+.4f}  phase32={BETA[1]:+.4f}  절편={BETA[2]:+.4f}")

    budget = int(mods_test.sum())
    print(f"공통 예산 = {budget} (= MODULES 총합) — 모든 팔이 동일. "
          f"'음을 더 냈을 뿐' 은 구조적으로 불가능하다.")

    # ── γ 보정 ──
    # 생성기는 지시된 대비를 **증폭**한다(지시 0.14 → 실현 0.47). 증폭률이 팔마다 달라서
    # 보정 없이 비교하면 "모양이 좋은가"와 "대비가 센가"가 뒤섞인다.
    # 그래서 **모든 팔**을 전반부에서 같은 목표 대비로 맞춘다 → 팔은 **모양만** 다르다.
    # (uncal_combined 는 보정을 안 한 팔로, 증폭 문제 자체를 보여주기 위해 남긴다)
    seeds = [3000 + 41 * i for i in range(args.n_seeds)]
    seeds_cal = seeds[:5]
    om_tr, mods_tr = om[:half], mods_full[:half]
    budget_tr = int(mods_tr.sum())
    p_tr = phase_profile(cnt_train, 0)
    target = float(p_tr.std() / p_tr.mean())
    shapes_tr = build_shapes(om_tr, prof_train, mods_tr, np.random.default_rng(0), offset=0)

    def realized(shape, gam):
        sh = scale_to_budget(shrink(shape, gam), budget_tr)
        out = []
        for s in seeds_cal:
            random.seed(s); np.random.seed(s)
            p = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
            g = G.algorithm1_optimized(p, list(sh), om_tr, G.CycleSetManager(cycle_labeled),
                                       max_resample=50, verbose=False, min_onset_gap=0)
            pf = phase_profile(onset_counts(g, 0, half), 0)
            out.append(pf.std() / pf.mean() if pf.mean() else 0.0)
        return float(np.mean(out))

    GAMMA = {}
    print(f"γ 보정 (전반부에서만) — 목표 실현 대비 {target:.4f}")
    for a, sh in shapes_tr.items():
        cand = [(abs(realized(sh, g) - target), g) for g in (0.1, 0.2, 0.3, 0.5, 0.75, 1.0)]
        err, g = min(cand)
        GAMMA[a] = g
        print(f"    {a:20} γ={g:<5} (오차 {err:.4f})")
    GAMMA["uncal_combined"] = 1.0
    print()

    arms = ["modules", "om", "phase32", "combined",
            "phase32_shuffled", "combined_shuffled", "uncal_combined"]
    acc = {a: {"js": [], "cons": [], "n": [], "rho": [], "prof_js": []} for a in arms}

    for s in seeds:
        shapes = build_shapes(om_test, prof_train, mods_test, np.random.default_rng(s))
        shapes["uncal_combined"] = shapes["combined"]
        for a in arms:
            inst = scale_to_budget(shrink(shapes[a], GAMMA[a]), budget)
            random.seed(s); np.random.seed(s)
            pool = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
            gen = G.algorithm1_optimized(pool, list(inst), om_test,
                                         G.CycleSetManager(cycle_labeled),
                                         max_resample=50, verbose=False, min_onset_gap=0)
            if not gen:
                continue
            acc[a]["js"].append(pitch_distribution_similarity(gen, orig)["js_divergence"])
            acc[a]["cons"].append(consonance_score(gen))
            acc[a]["n"].append(len(gen))
            g_cnt = onset_counts(gen, 0, Ttest)
            acc[a]["rho"].append(float(np.corrcoef(g_cnt, cnt_test)[0, 1]))
            pg = phase_profile(g_cnt, OFFSET); po = phase_profile(cnt_test, OFFSET)
            pg = pg / pg.sum() if pg.sum() else pg
            po = po / po.sum() if po.sum() else po
            m = 0.5 * (pg + po)
            kl = lambda p, q: float(np.sum(np.where(p > 0, p * np.log2(p / np.where(q > 0, q, 1)), 0.0)))
            acc[a]["prof_js"].append(0.5 * kl(pg, m) + 0.5 * kl(po, m))

    print(f"{'팔':20} {'리듬상관 ρ':>14} {'위상프로파일 JS':>16} {'음고 JS':>16} {'협화도':>10} {'음':>6}")
    res = {}
    for a in arms:
        d = acc[a]
        res[a] = {k: (float(np.mean(v)), float(np.std(v, ddof=1))) for k, v in d.items()}
        print(f"{a:20} {np.mean(d['rho']):>8.4f}±{np.std(d['rho'],ddof=1):.4f} "
              f"{np.mean(d['prof_js']):>10.5f}±{np.std(d['prof_js'],ddof=1):.5f} "
              f"{np.mean(d['js']):>9.5f}±{np.std(d['js'],ddof=1):.5f} "
              f"{np.mean(d['cons']):>10.4f} {np.mean(d['n']):>6.0f}")

    # ── 판정: 메커니즘 대조군을 통과하는가 ──
    from scipy import stats
    print(f"\n{'─'*88}\n대조 (paired, N={args.n_seeds})")
    def cmp(a, b, key, label):
        x, y = acc[a][key], acc[b][key]
        p = float(stats.ttest_rel(x, y).pvalue)
        dz = (np.mean(x) - np.mean(y)) / np.std(np.array(x) - np.array(y), ddof=1)
        print(f"  {label:52} Δ={np.mean(x)-np.mean(y):+.5f}  p={p:.3e}  dz={dz:+.2f}"
              f"  {'유의' if p < 0.05 else '판별 불가'}")
        return {"delta": float(np.mean(x) - np.mean(y)), "p": p, "dz": float(dz)}

    tests = {
        "rho_om_vs_modules":         cmp("om", "modules", "rho", "리듬상관: om vs modules ★대부분의 이득이 여기?"),
        "rho_combined_vs_om":        cmp("combined", "om", "rho", "리듬상관: combined vs om ★32주기의 순수 기여"),
        "rho_combined_vs_phase32":   cmp("combined", "phase32", "rho", "리듬상관: combined vs phase32 (OM 의 기여)"),
        "rho_combined_vs_modules":   cmp("combined", "modules", "rho", "리듬상관: combined vs modules (baseline)"),
        "rho_phase32_vs_shuffled":   cmp("phase32", "phase32_shuffled", "rho", "리듬상관: phase32 vs 위상섞기 ★메커니즘"),
        "rho_combined_vs_shuffled":  cmp("combined", "combined_shuffled", "rho", "리듬상관: combined vs 위상섞기 ★메커니즘"),
        "profjs_combined_vs_modules": cmp("combined", "modules", "prof_js", "위상프로파일 JS: combined vs modules (낮을수록 좋다)"),
        "profjs_om_vs_modules":      cmp("om", "modules", "prof_js", "위상프로파일 JS: om vs modules"),
        "js_combined_vs_modules":    cmp("combined", "modules", "js", "음고 JS: combined vs modules (낮을수록 좋다)"),
        "js_phase32_vs_modules":     cmp("phase32", "modules", "js", "음고 JS: phase32 vs modules"),
        "cons_combined_vs_modules":  cmp("combined", "modules", "cons", "협화도: combined vs modules (대가 확인)"),
        "profjs_uncal_vs_combined":  cmp("uncal_combined", "combined", "prof_js", "위상프로파일 JS: 보정 안 함 vs 보정함 ★증폭"),
        "js_uncal_vs_combined":      cmp("uncal_combined", "combined", "js", "음고 JS: 보정 안 함 vs 보정함"),
    }

    # 왜 두 리듬 지표가 반대로 가는가 — 실현된 프로파일의 대비를 본다
    print(f"\n{'─'*88}\n진단: 실현된 위상 프로파일의 대비 (원곡 대비)")
    po = phase_profile(cnt_test, OFFSET)
    print(f"  {'원곡':22} std/mean = {po.std()/po.mean():.4f}")
    contrast = {}
    for a in arms:
        _sh = build_shapes(om_test, prof_train, mods_test, np.random.default_rng(seeds[0]))
        _sh["uncal_combined"] = _sh["combined"]
        inst = scale_to_budget(shrink(_sh[a], GAMMA[a]), budget)
        random.seed(seeds[0]); np.random.seed(seeds[0])
        pool = G.NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        g = G.algorithm1_optimized(pool, list(inst), om_test, G.CycleSetManager(cycle_labeled),
                                   max_resample=50, verbose=False, min_onset_gap=0)
        pg = phase_profile(onset_counts(g, 0, Ttest), OFFSET)
        pi = phase_profile(inst.astype(float), OFFSET)
        contrast[a] = {"inst_contrast": float(pi.std() / pi.mean()),
                       "realized_contrast": float(pg.std() / pg.mean())}
        print(f"  {a:22} 지시 = {pi.std()/pi.mean():.4f}  →  실현 = {pg.std()/pg.mean():.4f}"
              f"   (원곡 {po.std()/po.mean():.4f})")

    payload = {
        "experiment": "period32_x_om_inst_len",
        "prediction_registered_before_run": PREDICTION,
        "config": {"period": PERIOD, "train": [0, half], "test": [half, T],
                   "budget": budget, "n_seeds": args.n_seeds,
                   "beta_om_phase_intercept": [float(b) for b in BETA]},
        "held_out_pearson_reference": {"om": 0.5705, "modules": 0.5837,
                                       "phase32": 0.6928, "combined": 0.7788},
        "results": res, "tests": tests,
        "raw_per_seed": {a: {k: [float(x) for x in v] for k, v in acc[a].items()} for a in arms},
        "phase_contrast_diagnostic": contrast,
        "gamma_per_arm": GAMMA, "target_contrast": target,
        "original_phase_contrast": float(po.std() / po.mean()),
        "note": "모든 팔이 동일 예산이므로 음 수 차이로 인한 아티팩트는 배제된다.",
        "total_seconds": time.time() - t0,
    }
    out = os.path.join(STEP3_DIR, "period32_om_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
