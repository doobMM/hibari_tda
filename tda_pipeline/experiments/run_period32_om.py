"""run_period32_om.py — ③ 32주기 리듬 구조를 OM 과 결합한다

배경
────
원곡 hibari 의 시점별 타건 수를 무엇이 잘 예측하는가 (후반 held-out Pearson):

    OM 활성 cycle 수          0.571
    MODULES 고정 스케줄        0.584   ← 지금 생성기가 쓰는 것
    32주기 평균 프로파일        0.693
    OM + 32주기 결합           0.779

`corr(OM, 32주기) = 0.366` 으로 낮다 — 서로 다른 정보다.
생성기의 `inst_len[j]`(그 시점에 뽑을 음의 개수)는 지금 MODULES 만 본다. 여기에 얹으면 좋아지는가?

설계 — 네 가지 함정을 미리 막는다
─────────────────────────────────
1. **"음을 더 냈을 뿐" 아티팩트 (T4 전례).**
   `inst_len` 은 지속음 때문에 동적으로 줄어든다(MODULES 3~4 인데 실제 1.80음/스텝).
   → **모든 팔의 총 예산을 동일**하게 스케일한다. 팔은 "몇 개"가 아니라 **"어디에"**만 다르다.

2. **동어반복.** → 전반부 [0,544) 로 적합, 후반부 [544,1088) 에서만 생성·평가.

3. **메커니즘 뺀 대조군.** → `*_shuffled`: 프로파일 값 분포는 그대로, **위상만 무작위**.

4. **대비 증폭 (이 실험에서 실제로 헤드라인을 무너뜨린 것).**
   생성기는 지시된 대비를 증폭한다 — 지시 0.144 → 실현 0.468(원곡 0.457),
   지시 0.448 → 실현 1.001. 증폭률이 모양마다 달라서, 보정 없는 비교는
   **"모양이 좋은가"가 아니라 "대비가 센가"** 를 잰다.
   **결정적 대조**: MODULES 의 *모양은 그대로* 두고 대비만 키우면(γ=3.5) ρ 0.402 → 0.635.
   1차 헤드라인 +81% 중 **71% 가 순수 대비**였다.
   → 그래서 대비를 맞춰야 한다. 그런데 **한 지점을 맞추는 방법은 두 번 실패했다**:
     ① 한 지점에서만 맞추니 그 지점이 어느 모양에 유리한지에 따라 순위가 바뀌었다
     ② γ 를 전반부에서 고르면 후반부로 전이되지 않는다 (실현 0.99 → 0.473).
        `realized(γ)` 가 계단 함수(MODULES 는 값이 3/4 뿐)라 이분 탐색이 경계에 수렴한다.
     → **곡선 방법**으로 바꿨다. γ 를 쓸어 (실현 대비 → ρ) 곡선을 얻고
       **겹치는 대비 구간에서만** 비교한다. 실현 대비를 평가 구간에서 직접 재므로 전이가 없고,
       결과가 아니라 공변량으로 맞추므로 누출이 아니다. 안 겹치면 "비교 불가"라고 말한다.

**사전 예측 (1차 실행 전에 기록했다)**
  · 리듬 프로파일 상관: combined > phase32 > om ≈ modules, shuffled 는 modules 수준.
  · 음고 JS 는 방향을 예측하지 않는다 — `inst_len` 은 음 선택이 아니라 시점별 개수를 바꾼다.
  **결과: 반증됐다.** om 이 phase32 를 이겼고, combined vs om 은 대비 지점에 따라 부호가 뒤집힌다.

한계
────
모양마다 **도달 가능한 대비 범위가 다르다** — modules [0.473,1.335] · om [0.267,0.892] ·
phase32 [0.600,1.313] · combined [0.534,1.344]. 그래서 모든 쌍을 전 구간에서 비교할 수 없다.
겹치는 구간만 쓰고, 겹치지 않으면 비교 불가로 보고한다.

⚠ **원곡의 리듬 대비 0.457 은 modules·phase32·combined 의 도달 범위 아래**다.
고정 예산에서 생성기는 원곡만큼 평탄한 리듬을 만들지 못한다 (om 만 0.267 까지 내려간다).

산출:  docs/step3_data/period32_om_results.json       (팔 비교, 팔별 γ 보정 — 기술적)
       docs/step3_data/period32_contrast_curve.json   (대비-ρ 곡선 + 겹침 구간 비교 — 추론적)

실행:  python experiments/run_period32_om.py [--n-seeds 20] [--skip-contrast]
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
from types import SimpleNamespace

import numpy as np
from scipy import stats

import generation as G
import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, load_continuous_om,
)

PERIOD = 32
ARMS = ["modules", "om", "phase32", "combined", "phase32_shuffled", "combined_shuffled"]
SHAPES_MATCHED = ["modules", "om", "phase32", "combined"]
GAMMA_GRID = [0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.25, 3.5, 5.0, 8.0]
CONTRAST_TOL = 0.10          # 실현 대비 차이가 이보다 크면 "정렬됐다"고 할 수 없다
PREDICTION = ("리듬 프로파일 상관: combined > phase32 > om ≈ modules, shuffled 는 modules 수준. "
              "음고 JS 는 방향을 예측하지 않는다.")


# ── 순수 함수 ────────────────────────────────────────────────────────────────

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
    idx = np.arange(len(counts)) + offset
    return np.array([counts[(idx % PERIOD) == r].mean() if np.any((idx % PERIOD) == r) else 0.0
                     for r in range(PERIOD)])


def contrast(v):
    """대비 = std/mean. 0 나눗셈은 0 으로."""
    v = np.asarray(v, dtype=float)
    return float(v.std() / v.mean()) if v.mean() else 0.0


def shrink(shape, gamma):
    """평균 쪽으로 대비를 줄인다. gamma=1 그대로, 0 완전 평탄, >1 증폭."""
    s = np.asarray(shape, dtype=float)
    return s.mean() + gamma * (s - s.mean())


def scale_to_budget(shape, budget):
    """모양은 유지하고 총합만 budget 에 맞춘 정수 벡터."""
    shape = np.clip(np.asarray(shape, dtype=float), 0.0, None)
    if shape.sum() <= 0:
        shape = np.ones_like(shape)
    v = shape * (budget / shape.sum())
    out = np.maximum(0, np.round(v)).astype(int)
    diff = int(budget - out.sum())          # 반올림 잔차를 큰 항부터 ±1 로 보정
    if diff:
        order = np.argsort(-v if diff > 0 else -out.astype(float))
        for i in range(abs(diff)):
            j = order[i % len(order)]
            out[j] += 1 if diff > 0 else (-1 if out[j] > 0 else 0)
    return out


def js_divergence(p, q):
    p, q = np.asarray(p, float), np.asarray(q, float)
    p = p / p.sum() if p.sum() else p
    q = q / q.sum() if q.sum() else q
    m = 0.5 * (p + q)
    kl = lambda a, b: float(np.sum(np.where(a > 0, a * np.log2(a / np.where(b > 0, b, 1)), 0.0)))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def build_shapes(ctx, om_r, mods_r, offset, rng):
    """팔별 inst_len 모양 (스케일 전)."""
    n = len(mods_r)
    om_row = om_r.sum(1)
    prof = ctx.prof_train[(np.arange(n) + offset) % PERIOD]
    X = lambda pr: np.column_stack([om_row, pr, np.ones(n)]) @ ctx.beta
    prof_shuf = ctx.prof_train[rng.permutation(PERIOD)][(np.arange(n) + offset) % PERIOD]
    return {
        "modules":           mods_r.astype(float),
        "om":                om_row.astype(float),
        "phase32":           prof,
        "combined":          X(prof),
        "phase32_shuffled":  prof_shuf,
        "combined_shuffled": X(prof_shuf),
    }


# ── 생성 + 측정: 이 실험에서 음악을 만드는 **유일한** 경로 ──────────────────────

def evaluate(ctx, shape, gamma, seeds, *, region="test"):
    """shape 를 γ 로 눌러 예산에 맞춘 뒤 seeds 만큼 생성하고 지표를 잰다."""
    om_r, budget, cnt_ref, offset = (
        (ctx.om_test, ctx.budget, ctx.cnt_test, ctx.half) if region == "test"
        else (ctx.om_train, ctx.budget_train, ctx.cnt_train, 0))
    inst = scale_to_budget(shrink(shape, gamma), budget)
    ref_prof = phase_profile(cnt_ref, offset)
    out = {k: [] for k in ("rho", "js", "cons", "prof_js", "n", "realized_contrast")}
    for s in seeds:
        random.seed(s); np.random.seed(s)
        pool = G.NodePool(ctx.data["notes_label"], ctx.data["notes_counts"], num_modules=65)
        gen = G.algorithm1_optimized(pool, list(inst), om_r, G.CycleSetManager(ctx.cycle_labeled),
                                     max_resample=50, verbose=False, min_onset_gap=0)
        if not gen:
            continue
        cnt = onset_counts(gen, 0, len(inst))
        out["rho"].append(float(np.corrcoef(cnt, cnt_ref)[0, 1]))
        out["js"].append(pitch_distribution_similarity(gen, ctx.orig)["js_divergence"])
        out["cons"].append(consonance_score(gen))
        out["prof_js"].append(js_divergence(phase_profile(cnt, offset), ref_prof))
        out["n"].append(len(gen))
        out["realized_contrast"].append(contrast(phase_profile(cnt, offset)))
    res = {k: np.array(v) for k, v in out.items()}
    res["inst_contrast"] = contrast(phase_profile(inst.astype(float), offset))
    return res


# ── 준비 ─────────────────────────────────────────────────────────────────────

def prepare():
    data = suite.setup_hibari()
    orig = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]
    om = (load_continuous_om() >= REAL_TAU).astype(np.float32)
    T = om.shape[0]
    half = (T // 2 // PERIOD) * PERIOD          # 32의 배수로 잘라 위상을 보존
    mods = np.array((MODULES * (T // PERIOD + 2))[:T], dtype=float)

    cnt_train = onset_counts(orig, 0, half)
    cnt_test = onset_counts(orig, half, T)
    prof_train = phase_profile(cnt_train, 0)
    X = np.column_stack([om[:half].sum(1), prof_train[np.arange(half) % PERIOD], np.ones(half)])
    beta, *_ = np.linalg.lstsq(X, cnt_train, rcond=None)

    return SimpleNamespace(
        data=data, orig=orig, cycle_labeled=cycle_labeled, T=T, half=half,
        om_train=om[:half], om_test=om[half:],
        mods_train=mods[:half], mods_test=mods[half:],
        cnt_train=cnt_train, cnt_test=cnt_test, prof_train=prof_train, beta=beta,
        budget=int(mods[half:].sum()), budget_train=int(mods[:half].sum()),
        target=contrast(prof_train), orig_contrast=contrast(phase_profile(cnt_test, half)))


# ── 분석 A: 팔별 γ 보정 후 비교 ───────────────────────────────────────────────

def analysis_arms(ctx, seeds, t0):
    shapes_tr = build_shapes(ctx, ctx.om_train, ctx.mods_train, 0, np.random.default_rng(0))
    gamma = {}
    print(f"γ 보정 (전반부에서만) — 목표 실현 대비 {ctx.target:.4f}")
    for a, sh in shapes_tr.items():
        err, g = min((abs(evaluate(ctx, sh, g, seeds[:5], region="train")
                          ["realized_contrast"].mean() - ctx.target), g)
                     for g in (0.1, 0.2, 0.3, 0.5, 0.75, 1.0))
        gamma[a] = g
        print(f"    {a:20} γ={g:<5} (오차 {err:.4f})")
    gamma["uncal_combined"] = 1.0
    arms = ARMS + ["uncal_combined"]

    acc = {a: {k: [] for k in ("rho", "js", "cons", "prof_js", "n")} for a in arms}
    diag = {}
    for s in seeds:
        sh = build_shapes(ctx, ctx.om_test, ctx.mods_test, ctx.half, np.random.default_rng(s))
        sh["uncal_combined"] = sh["combined"]
        for a in arms:
            r = evaluate(ctx, sh[a], gamma[a], [s])
            for k in acc[a]:
                acc[a][k].extend(r[k].tolist())
            if s == seeds[0]:
                diag[a] = {"inst_contrast": r["inst_contrast"],
                           "realized_contrast": float(r["realized_contrast"].mean())}

    print(f"\n{'팔':20} {'리듬상관 ρ':>14} {'위상프로파일 JS':>16} {'음고 JS':>16} {'협화도':>10} {'음':>6}")
    res = {}
    for a in arms:
        d = {k: np.array(v) for k, v in acc[a].items()}
        res[a] = {k: [float(v.mean()), float(v.std(ddof=1))] for k, v in d.items()}
        print(f"{a:20} {d['rho'].mean():>8.4f}±{d['rho'].std(ddof=1):.4f} "
              f"{d['prof_js'].mean():>10.5f}±{d['prof_js'].std(ddof=1):.5f} "
              f"{d['js'].mean():>9.5f}±{d['js'].std(ddof=1):.5f} "
              f"{d['cons'].mean():>10.4f} {d['n'].mean():>6.0f}")

    print(f"\n{'─'*88}\n대조 (paired, N={len(seeds)})")

    def cmp(a, b, key, label):
        x, y = np.array(acc[a][key]), np.array(acc[b][key])
        p = float(stats.ttest_rel(x, y).pvalue)
        dz = float((x.mean() - y.mean()) / (x - y).std(ddof=1))
        print(f"  {label:52} Δ={x.mean()-y.mean():+.5f}  p={p:.3e}  dz={dz:+.2f}"
              f"  {'유의' if p < 0.05 else '판별 불가'}")
        return {"delta": float(x.mean() - y.mean()), "p": p, "dz": dz}

    tests = {
        "rho_om_vs_modules":          cmp("om", "modules", "rho", "리듬상관: om vs modules"),
        "rho_combined_vs_om":         cmp("combined", "om", "rho", "리듬상관: combined vs om (32주기의 몫)"),
        "rho_combined_vs_phase32":    cmp("combined", "phase32", "rho", "리듬상관: combined vs phase32 (OM 의 몫)"),
        "rho_combined_vs_modules":    cmp("combined", "modules", "rho", "리듬상관: combined vs modules (baseline)"),
        "rho_phase32_vs_shuffled":    cmp("phase32", "phase32_shuffled", "rho", "리듬상관: phase32 vs 위상섞기 ★메커니즘"),
        "rho_combined_vs_shuffled":   cmp("combined", "combined_shuffled", "rho", "리듬상관: combined vs 위상섞기 ★메커니즘"),
        "profjs_combined_vs_modules": cmp("combined", "modules", "prof_js", "위상프로파일 JS: combined vs modules"),
        "profjs_om_vs_modules":       cmp("om", "modules", "prof_js", "위상프로파일 JS: om vs modules"),
        "js_combined_vs_modules":     cmp("combined", "modules", "js", "음고 JS: combined vs modules"),
        "js_phase32_vs_modules":      cmp("phase32", "modules", "js", "음고 JS: phase32 vs modules"),
        "cons_combined_vs_modules":   cmp("combined", "modules", "cons", "협화도: combined vs modules"),
        "profjs_uncal_vs_combined":   cmp("uncal_combined", "combined", "prof_js", "위상프로파일 JS: 보정 안 함 vs 함 ★증폭"),
        "js_uncal_vs_combined":       cmp("uncal_combined", "combined", "js", "음고 JS: 보정 안 함 vs 함"),
    }

    print(f"\n{'─'*88}\n진단: 지시 대비 → 실현 대비 (원곡 {ctx.orig_contrast:.4f})")
    for a in arms:
        print(f"  {a:22} 지시 = {diag[a]['inst_contrast']:.4f}  →  실현 = {diag[a]['realized_contrast']:.4f}")

    return {
        "experiment": "period32_x_om_inst_len",
        "prediction_registered_before_run": PREDICTION,
        "prediction_outcome": "반증 — om 이 phase32 를 이겼고, combined vs om 은 대비 지점에 따라 뒤집힌다",
        "config": {"period": PERIOD, "train": [0, ctx.half], "test": [ctx.half, ctx.T],
                   "budget": ctx.budget, "n_seeds": len(seeds),
                   "beta_om_phase_intercept": [float(b) for b in ctx.beta]},
        "held_out_pearson_reference": {"om": 0.5705, "modules": 0.5837,
                                       "phase32": 0.6928, "combined": 0.7788},
        "results": res, "tests": tests,
        "raw_per_seed": {a: {k: [float(x) for x in v] for k, v in acc[a].items()} for a in arms},
        "phase_contrast_diagnostic": diag,
        "gamma_per_arm": gamma, "target_contrast": ctx.target,
        "original_phase_contrast": ctx.orig_contrast,
        "note": "모든 팔이 동일 예산이므로 음 수 차이로 인한 아티팩트는 배제된다.",
        "total_seconds": time.time() - t0,
    }


# ── 분석 B: 대비-ρ **곡선**을 그려 겹치는 구간에서만 비교 ─────────────────────
#
# 왜 곡선인가 — 한 지점을 맞추려던 이전 방법이 두 이유로 깨졌다:
#   (a) `realized(γ)` 가 계단 함수다 (MODULES 는 값이 3/4 뿐) → 이분 탐색이 경계에 수렴
#   (b) 전반부에서 고른 γ 가 후반부로 전이되지 않는다 (실현 0.99 → 0.473)
# 곡선은 둘 다 피한다. γ 를 쓸어 (실현 대비 → ρ) 곡선을 얻고 **겹치는 대비 구간에서만**
# 비교한다. 실현 대비를 평가 구간에서 **직접 측정**하므로 전이 문제가 없고,
# 결과(ρ)가 아니라 **공변량(대비)** 으로 맞추는 것이라 누출도 아니다.
# 겹치지 않으면 "비교 불가"라고 말한다 — 외삽하지 않는다.


def analysis_contrast_curve(ctx, seeds, t0):
    shapes = build_shapes(ctx, ctx.om_test, ctx.mods_test, ctx.half,
                          np.random.default_rng(seeds[0]))

    # 대조 A — 모양을 고정하고 대비만 키워도 ρ 가 오르는가 (이 실험의 출발점)
    r0 = evaluate(ctx, shapes["modules"], 1.0, seeds)
    r1 = evaluate(ctx, shapes["modules"], 3.5, seeds)
    p_amp = float(stats.ttest_rel(r1["rho"], r0["rho"]).pvalue)
    print("\n[대조 A] MODULES **모양 그대로** 대비만 키움 : "
          f"ρ {r0['rho'].mean():.4f}(대비 {r0['realized_contrast'].mean():.3f}) → "
          f"{r1['rho'].mean():.4f}(대비 {r1['realized_contrast'].mean():.3f})  "
          f"Δ={r1['rho'].mean() - r0['rho'].mean():+.4f} p={p_amp:.2e}")
    print("         → 모양을 안 바꿔도 대비만으로 ρ 가 오른다. 대비를 맞추지 않은 비교는 무효다.")

    # ── 곡선 쓸기 ──
    print(f"\n[곡선] γ {len(GAMMA_GRID)}점 × 모양 {len(SHAPES_MATCHED)}개 × 시드 {len(seeds)}")
    curves = {}
    for name in SHAPES_MATCHED:
        pts = []
        for g in GAMMA_GRID:
            r = evaluate(ctx, shapes[name], g, seeds)
            pts.append({"gamma": float(g),
                        "contrast": float(r["realized_contrast"].mean()),
                        "rho": float(r["rho"].mean()), "rho_all": r["rho"],
                        "pitch_js": float(r["js"].mean()),
                        "consonance": float(r["cons"].mean())})
        pts.sort(key=lambda d: d["contrast"])
        curves[name] = pts
        print(f"  {name:10} 도달 대비 [{pts[0]['contrast']:.3f}, {pts[-1]['contrast']:.3f}]  "
              f"ρ [{min(q['rho'] for q in pts):.3f}, {max(q['rho'] for q in pts):.3f}]")

    print(f"\n  원곡 대비 {ctx.orig_contrast:.3f} 에서의 값 (선형보간):")
    at_orig = {}
    for name in SHAPES_MATCHED:
        pts = curves[name]
        xs = [q["contrast"] for q in pts]
        if xs[0] <= ctx.orig_contrast <= xs[-1]:
            y = float(np.interp(ctx.orig_contrast, xs, [q["rho"] for q in pts]))
            j = float(np.interp(ctx.orig_contrast, xs, [q["pitch_js"] for q in pts]))
            at_orig[name] = {"rho": y, "pitch_js": j}
            print(f"    {name:10} ρ≈{y:.4f}   음고 JS≈{j:.5f}")
        else:
            at_orig[name] = None
            print(f"    {name:10} 도달 범위 밖 — 보간 불가")

    # ── 겹치는 구간에서만 쌍 비교 ──
    print(f"\n{'-' * 88}")
    print(f"겹치는 대비 구간에서 쌍 비교 (지점마다 paired t-test, 대비 차이 ≤ {CONTRAST_TOL})")
    pairs = {}
    for a, b in (("combined", "om"), ("combined", "modules"), ("om", "modules"),
                 ("combined", "phase32"), ("phase32", "modules"), ("om", "phase32")):
        ca, cb = curves[a], curves[b]
        lo = max(ca[0]["contrast"], cb[0]["contrast"])
        hi = min(ca[-1]["contrast"], cb[-1]["contrast"])
        if hi <= lo:
            print(f"  {a:9} vs {b:9}  겹치는 구간 없음 → 비교 불가")
            pairs[f"{a}_vs_{b}"] = {"overlap": None, "verdict": "비교 불가 (구간 미겹침)"}
            continue
        rows, wins = [], []
        for c in np.linspace(lo, hi, 5):
            pa = min(ca, key=lambda q: abs(q["contrast"] - c))
            pb = min(cb, key=lambda q: abs(q["contrast"] - c))
            gap = abs(pa["contrast"] - pb["contrast"])
            if gap > CONTRAST_TOL:
                continue
            d = float(pa["rho"] - pb["rho"])
            pv = float(stats.ttest_rel(pa["rho_all"], pb["rho_all"]).pvalue)
            rows.append({"target": float(c), "contrast_a": pa["contrast"],
                         "contrast_b": pb["contrast"], "gap": float(gap),
                         "delta": d, "p": pv})
            wins.append(1 if d > 0 else -1)
        if not rows:
            verdict = "비교 불가 (정렬 지점 없음)"
        elif all(w > 0 for w in wins):
            verdict = f"{a} 우세 (정렬 {len(rows)}지점 전부)"
        elif all(w < 0 for w in wins):
            verdict = f"{b} 우세 (정렬 {len(rows)}지점 전부)"
        else:
            verdict = f"판별 불가 (부호 갈림 {sum(w > 0 for w in wins)}/{len(rows)})"
        ds = " ".join(f"{r['delta']:+.3f}" for r in rows)
        print(f"  {a:9} vs {b:9}  겹침 [{lo:.3f},{hi:.3f}]  Δ = {ds or '-'}   → {verdict}")
        pairs[f"{a}_vs_{b}"] = {"overlap": [float(lo), float(hi)],
                                "points": rows, "verdict": verdict}

    return {
        "experiment": "period32_contrast_curve",
        "method": ("γ 를 쓸어 (실현 대비 → ρ) 곡선을 얻고 겹치는 구간에서만 비교한다. "
                   "실현 대비를 평가 구간에서 직접 측정하므로 train→test 전이 문제가 없고, "
                   "결과가 아니라 공변량으로 맞추므로 누출이 아니다. "
                   "겹치지 않으면 비교 불가로 보고하고 외삽하지 않는다."),
        "original_contrast": ctx.orig_contrast,
        "gamma_grid": GAMMA_GRID, "contrast_tolerance": CONTRAST_TOL,
        "contrast_only_control": {"rho_gamma1": float(r0["rho"].mean()),
                                  "rho_gamma3p5": float(r1["rho"].mean()),
                                  "contrast_gamma1": float(r0["realized_contrast"].mean()),
                                  "contrast_gamma3p5": float(r1["realized_contrast"].mean()),
                                  "p": p_amp},
        "curves": {k: [{kk: vv for kk, vv in q.items() if kk != "rho_all"} for q in v]
                   for k, v in curves.items()},
        "at_original_contrast": at_orig,
        "pair_comparisons": pairs,
        "total_seconds": time.time() - t0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    ap.add_argument("--skip-contrast", action="store_true", help="분석 B(대비 정렬) 생략")
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t0 = time.time()
    print("=" * 88)
    print("③ 32주기 리듬 구조 × OM — inst_len 을 어디에 놓을 것인가")
    print(f"  사전 예측: {PREDICTION}")
    print("=" * 88)

    ctx = prepare()
    seeds = [3000 + 41 * i for i in range(args.n_seeds)]
    print(f"\n적합 [0,{ctx.half}) · 평가 [{ctx.half},{ctx.T})  ·  "
          f"결합 계수 om={ctx.beta[0]:+.4f} phase32={ctx.beta[1]:+.4f} 절편={ctx.beta[2]:+.4f}")
    print(f"공통 예산 = {ctx.budget} (= MODULES 총합) — 전 팔 동일, "
          f"'음을 더 냈을 뿐' 은 구조적으로 불가능하다.\n")

    for name, payload in (("period32_om_results.json", analysis_arms(ctx, seeds, t0)),
                          *(() if args.skip_contrast else
                            (("period32_contrast_curve.json",
                              analysis_contrast_curve(ctx, seeds, t0)),))):
        path = os.path.join(STEP3_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n저장: {path}")
    print(f"({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
