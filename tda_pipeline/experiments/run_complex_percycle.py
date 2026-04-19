"""
run_complex_percycle.py — Complex PH + per-cycle τ_c + Algo2(FC) 통합 실험
==========================================================================

실험 0: ow 재검증 (N=5, timeflow, 버그수정 후 ow 실제 반영 확인)
실험 A: 기준선 재확인 (N=10, pkl 캐시 기반 per-cycle τ, Algo1+Algo2)
실험 B: 핵심 — complex 최적 + per-cycle τ_c 신규 greedy 최적화 + Algo2
실험 C: 추가 탐색 — complex 2위 + per-cycle τ_c (N=5, Algo1)

비교 기준선:
  Algo1 best (timeflow + per-cycle τ, N=20): JS = 0.0241 ± 0.0023
  Algo2 best (FC continuous, N=5):           JS = 0.0004

결과: docs/step3_data/complex_percycle_results.json
"""

import os, sys, json, time, random, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from pipeline import TDAMusicPipeline, PipelineConfig
from preprocessing import simul_chord_lists, simul_union_by_dict
from overlap import build_activation_matrix, build_overlap_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

# ─── 기준 수치 ───────────────────────────────────────────────────────────────
ALGO1_BEST = 0.0241   # timeflow + per-cycle τ N=20
ALGO2_BEST = 0.0004   # FC continuous

RATE_T  = 0.3         # complex 모드 timeflow 비율 고정값
TAU_VALS = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]
ALGO1_MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                 4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
T_TOTAL = 1088


# ═══════════════════════════════════════════════════════════════════════════════
# 공통 유틸
# ═══════════════════════════════════════════════════════════════════════════════

def build_note_time_df(p):
    """파이프라인 캐시에서 note-time 행렬 DataFrame 구축."""
    adn_i       = p._cache['adn_i']
    notes_dict  = p._cache['notes_dict']
    notes_label = p._cache['notes_label']

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets   = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list  = list(range(1, len(notes_label) + 1))

    ntd = np.zeros((T_TOTAL, len(nodes_list)), dtype=int)
    for t in range(min(T_TOTAL, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


def run_algo1_once(shared, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool    = NodePool(shared['notes_label'], shared['notes_counts'], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    generated = algorithm1_optimized(
        pool, ALGO1_MODULES * 33, overlap_values, manager,
        max_resample=50, verbose=False
    )
    return evaluate_generation(
        generated,
        [shared['inst1_real'], shared['inst2_real']],
        shared['notes_label'], name=""
    )


def mean_js(shared, overlap_values, cycle_labeled, n, seed_base):
    vals = [run_algo1_once(shared, overlap_values, cycle_labeled, seed_base + i)['js_divergence']
            for i in range(n)]
    return float(np.mean(vals)), float(np.std(vals, ddof=1) if n > 1 else 0.0)


def eval_n(shared, overlap_values, cycle_labeled, n, seed_base, label=""):
    """N회 Algo1 평가, 진행 상황 출력."""
    js_vals = []
    t0 = time.time()
    for i in range(n):
        r = run_algo1_once(shared, overlap_values, cycle_labeled, seed_base + i)
        js_vals.append(r['js_divergence'])
        if i % 5 == 0 or i == n - 1:
            print(f"    [{i+1:2d}/{n}] JS={js_vals[-1]:.4f}  {time.time()-t0:.1f}s")
    arr = np.array(js_vals)
    return arr, float(arr.mean()), float(arr.std(ddof=1) if n > 1 else 0.0)


def greedy_percycle_tau(shared, cont_act, cycle_labeled,
                        tau_vals=TAU_VALS, n_eval=5, seed_base=5000):
    """
    Greedy coordinate descent — 각 cycle c에 독립 τ_c 탐색.
    baseline: 전체 τ=0.35
    반환: (best_taus, base_mean, final_mean)
    """
    K = cont_act.shape[1]
    baseline_ov = (cont_act >= 0.35).astype(np.float32)
    base_mean, base_std = mean_js(shared, baseline_ov, cycle_labeled, n_eval, seed_base)
    print(f"    baseline (τ=0.35): JS = {base_mean:.4f} ± {base_std:.4f}")

    best_taus = [0.35] * K

    for c in range(K):
        best_tau_c = 0.35
        best_js_c  = float('inf')
        for tau in tau_vals:
            test_taus = list(best_taus)
            test_taus[c] = tau
            ov = np.zeros_like(cont_act)
            for ci, t in enumerate(test_taus):
                ov[:, ci] = (cont_act[:, ci] >= t).astype(float)
            js_m, _ = mean_js(shared, ov, cycle_labeled, n_eval, seed_base + c * 100 + 1)
            if js_m < best_js_c:
                best_js_c  = js_m
                best_tau_c = tau
        best_taus[c] = best_tau_c
        arrow = '↓' if best_js_c < base_mean else '↑'
        print(f"    cycle {c:2d}: τ={best_tau_c:.2f}  JS={best_js_c:.4f}  {arrow}")

    # 최종 평가
    final_ov = np.zeros_like(cont_act)
    for ci, t in enumerate(best_taus):
        final_ov[:, ci] = (cont_act[:, ci] >= t).astype(float)
    final_mean, final_std = mean_js(shared, final_ov, cycle_labeled, n_eval * 2, seed_base + 9000)
    impr = 100 * (base_mean - final_mean) / base_mean
    print(f"    per-cycle τ: JS = {final_mean:.4f} ± {final_std:.4f}  (개선 {impr:+.1f}%)")

    return best_taus, base_mean, final_ov, final_mean, final_std, impr


def run_algo2_fc(shared, cont_act, n_trials=3, epochs=80):
    """FC 모델을 continuous overlap으로 학습 + 생성 평가."""
    try:
        import torch
        from generation import (MusicGeneratorFC, prepare_training_data,
                                 train_model, generate_from_model)
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        return {'error': str(e)}

    notes_label = shared['notes_label']
    inst1_real  = shared['inst1_real']
    inst2_real  = shared['inst2_real']
    N = len(notes_label)
    K = cont_act.shape[1]

    print(f"  [Algo2 FC] K={K} cycles, N={N} notes, epochs={epochs}")
    print(f"  continuous range: [{cont_act.min():.3f}, {cont_act.max():.3f}]")

    X, y = prepare_training_data(cont_act, [inst1_real, inst2_real], notes_label, T_TOTAL, N)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    torch.manual_seed(42)
    model = MusicGeneratorFC(num_cycles=K, num_notes=N, hidden_dim=128, dropout=0.3)

    t0 = time.time()
    history = train_model(model, X_train, y_train, X_val, y_val,
                          epochs=epochs, lr=0.001, batch_size=32,
                          model_type='fc', seq_len=T_TOTAL)
    train_time = time.time() - t0
    final_val_loss = history[-1]['val_loss'] if history else None
    print(f"  학습 완료: {train_time:.1f}s  val_loss={final_val_loss:.4f}" if final_val_loss else
          f"  학습 완료: {train_time:.1f}s")

    js_trials = []
    for i in range(n_trials):
        torch.manual_seed(i); random.seed(i); np.random.seed(i)
        gen = generate_from_model(model, cont_act, notes_label,
                                  model_type='fc', adaptive_threshold=True)
        if not gen:
            js_trials.append(1.0); continue
        m = evaluate_generation(gen, [inst1_real, inst2_real], notes_label, name="")
        js_trials.append(m['js_divergence'])
        print(f"    trial {i}: JS={js_trials[-1]:.4f}")

    js_arr = np.array(js_trials)
    js_mean = float(js_arr.mean())
    js_std  = float(js_arr.std(ddof=1) if len(js_trials) > 1 else 0.0)
    print(f"  → Algo2 FC: JS = {js_mean:.4f} ± {js_std:.4f}")

    return {
        'js_mean':      round(js_mean, 4),
        'js_std':       round(js_std, 4),
        'train_time_s': round(train_time, 1),
        'val_loss':     round(float(final_val_loss), 4) if final_val_loss else None,
        'all_js':       [round(float(x), 4) for x in js_trials],
        'n_trials':     n_trials,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 실험 0: ow 재검증
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_0_ow_revalidation(preproc_cache, shared):
    """
    버그수정(080b9fe) 이후 ow가 실제로 PH에 반영되는지 확인.
    search_type='timeflow', metric='tonnetz', α=0.5
    ow ∈ {0.0, 0.3, 0.6}, dw=0.3, τ=0.5 이진화, N=5
    """
    print("\n" + "=" * 65)
    print("  실험 0: ow 재검증 (timeflow + τ=0.5 이진화, N=5)")
    print("=" * 65)

    OW_LIST = [0.0, 0.3, 0.6]
    DW = 0.3
    ALPHA = 0.5
    TAU_FIXED = 0.5
    N = 5

    results_0 = {}

    for ow in OW_LIST:
        print(f"\n  [ow={ow}]")
        cfg = PipelineConfig()
        cfg.metric.metric          = 'tonnetz'
        cfg.metric.alpha           = ALPHA
        cfg.metric.octave_weight   = ow
        cfg.metric.duration_weight = DW
        cfg.overlap.threshold      = TAU_FIXED

        p = TDAMusicPipeline(cfg)
        p._cache.update(preproc_cache)

        t0 = time.time()
        p.run_homology_search(search_type='timeflow', dimension=1)
        p.run_overlap_construction(persistence_key='h1_timeflow_lag1')

        cycle_labeled = p._cache['cycle_labeled']
        ov = p._cache['overlap_matrix'].values
        K = len(cycle_labeled)
        elapsed = time.time() - t0

        _, js_mean, js_std = eval_n(shared, ov, cycle_labeled, N, 4000 + int(ow*10), f"ow={ow}")
        print(f"  → K={K}  JS={js_mean:.4f} ± {js_std:.4f}  ({elapsed:.1f}s)")

        results_0[f'ow{ow}'] = {
            'ow': ow, 'K': K,
            'js_mean': round(js_mean, 4),
            'js_std':  round(js_std, 4),
        }

    # ow에 따라 K 또는 JS가 달라지는지 확인
    ow_vals = [results_0[k]['ow'] for k in results_0]
    js_vals = [results_0[k]['js_mean'] for k in results_0]
    K_vals  = [results_0[k]['K'] for k in results_0]
    ow_varies = (len(set(js_vals)) > 1) or (len(set(K_vals)) > 1)

    print(f"\n  결과 요약:")
    print(f"  {'ow':>5}  {'K':>5}  {'JS':>8}")
    for ow in OW_LIST:
        r = results_0[f'ow{ow}']
        print(f"  {ow:>5.1f}  {r['K']:>5d}  {r['js_mean']:>8.4f}")
    verdict = "✓ ow가 PH에 실제 반영됨 (K 또는 JS 변화)" if ow_varies else \
              "△ K/JS 변화 없음 — ow 영향 미미 또는 α=0.5 하에서 ow 차이 상쇄"
    print(f"\n  판정: {verdict}")

    results_0['verdict'] = verdict
    return results_0


# ═══════════════════════════════════════════════════════════════════════════════
# 실험 A: 기준선 재확인 (pkl 캐시 + 기존 per-cycle τ)
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_A_baseline(shared, percycle_path):
    """
    pkl 캐시 기반 K=42 사이클 + 기존 greedy per-cycle τ 재확인.
    Algo1 N=10, Algo2 FC continuous N=3.
    """
    print("\n" + "=" * 65)
    print("  실험 A: 기준선 재확인 (pkl 캐시 + 기존 per-cycle τ, N=10)")
    print("=" * 65)

    # ── 기존 per-cycle τ 로드 ───────────────────────────────────────────────
    with open(percycle_path) as f:
        prev = json.load(f)
    best_taus = prev['per_cycle_tau']['best_taus']
    K_expected = prev['n_cycles']
    prev_mean  = prev['per_cycle_tau']['js_mean']
    print(f"  기존 per-cycle τ: K={K_expected}, JS(N=20)={prev_mean:.4f}")
    print(f"  τ 벡터 앞 10개: {best_taus[:10]}")

    # ── pkl 캐시에서 사이클 로드 ─────────────────────────────────────────────
    cache_pkl = 'cache/metric_tonnetz.pkl'
    if not os.path.exists(cache_pkl):
        print(f"  [경고] {cache_pkl} 없음 — 실험 A 건너뜀")
        return {'error': f'{cache_pkl} not found'}

    with open(cache_pkl, 'rb') as f:
        pkl = pickle.load(f)
    cycle_labeled = pkl['cycle_labeled']
    K_actual = len(cycle_labeled)
    print(f"  pkl 캐시 K={K_actual}")

    if K_actual != K_expected:
        print(f"  [경고] K 불일치: best_taus({K_expected}) vs pkl({K_actual})")
        if K_actual < K_expected:
            best_taus = best_taus[:K_actual]
        else:
            best_taus = best_taus + [0.35] * (K_actual - K_expected)

    # continuous activation 계산 (note_time_df는 preprocessing 기반)
    note_time_df = shared['note_time_df']
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True).values.astype(np.float32)

    # per-cycle τ 적용 overlap
    percycle_ov = np.zeros_like(cont_act)
    for ci, tau in enumerate(best_taus):
        percycle_ov[:, ci] = (cont_act[:, ci] >= tau).astype(float)

    # ── Algo1 N=10 ───────────────────────────────────────────────────────────
    print(f"\n  [Algo1 N=10]")
    arr_a1, mean_a1, std_a1 = eval_n(shared, percycle_ov, cycle_labeled, 10, 6000)
    print(f"  → Algo1: JS = {mean_a1:.4f} ± {std_a1:.4f}")
    vs_prev = 100 * (mean_a1 - prev_mean) / prev_mean
    print(f"    (기존 N=20 대비 {vs_prev:+.1f}%)")

    # ── Algo2 FC N=3 ─────────────────────────────────────────────────────────
    print(f"\n  [Algo2 FC N=3]")
    r_a2 = run_algo2_fc(shared, cont_act, n_trials=3, epochs=80)

    return {
        'K': K_actual,
        'best_taus': best_taus,
        'algo1': {
            'js_mean': round(mean_a1, 4),
            'js_std':  round(std_a1, 4),
            'all_js':  [round(float(x), 4) for x in arr_a1],
            'vs_prev_n20_pct': round(vs_prev, 1),
        },
        'algo2_fc': r_a2,
        'source': 'pkl_cache',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 실험 B/C: complex + greedy per-cycle τ
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_complex_percycle(label, preproc_cache, shared,
                                alpha, ow, dw, rc, n_algo1, run_algo2=True):
    """
    Complex PH 신규 계산 → greedy per-cycle τ → Algo1 + (optionally) Algo2.
    label: 'B' or 'C'
    """
    print("\n" + "=" * 65)
    print(f"  실험 {label}: complex + per-cycle τ_c")
    print(f"  α={alpha}, ow={ow}, dw={dw}, r_c={rc}")
    print(f"  Algo1 N={n_algo1}" + (" + Algo2 FC N=3" if run_algo2 else ""))
    print("=" * 65)

    # ── PH 계산 ──────────────────────────────────────────────────────────────
    cfg = PipelineConfig()
    cfg.metric.metric          = 'tonnetz'
    cfg.metric.alpha           = alpha
    cfg.metric.octave_weight   = ow
    cfg.metric.duration_weight = dw

    p = TDAMusicPipeline(cfg)
    p._cache.update(preproc_cache)

    t0 = time.time()
    p.run_homology_search(search_type='complex', dimension=1,
                          rate_t=RATE_T, rate_s=rc)
    p.run_overlap_construction(persistence_key='h1_complex_lag1')
    ph_time = time.time() - t0

    cycle_labeled = p._cache['cycle_labeled']
    K = len(cycle_labeled)
    print(f"\n  PH 완료: K={K} cycles  ({ph_time:.1f}s)")

    # ── continuous activation 구축 ───────────────────────────────────────────
    note_time_df = shared['note_time_df']
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True).values.astype(np.float32)
    print(f"  cont_act range: [{cont_act.min():.3f}, {cont_act.max():.3f}]")

    # ── greedy per-cycle τ 최적화 ────────────────────────────────────────────
    print(f"\n  [Greedy per-cycle τ 탐색 (τ ∈ {TAU_VALS})]")
    t0 = time.time()
    best_taus, base_mean, percycle_ov, pc_mean, pc_std, impr = greedy_percycle_tau(
        shared, cont_act, cycle_labeled,
        tau_vals=TAU_VALS, n_eval=5, seed_base=5000 + ord(label) * 100
    )
    greedy_time = time.time() - t0
    print(f"  greedy 완료: {greedy_time:.1f}s")

    # ── Algo1 N ──────────────────────────────────────────────────────────────
    print(f"\n  [Algo1 N={n_algo1}]")
    arr_a1, mean_a1, std_a1 = eval_n(shared, percycle_ov, cycle_labeled,
                                      n_algo1, 6000 + ord(label) * 100)
    vs_algo1_best = 100 * (mean_a1 - ALGO1_BEST) / ALGO1_BEST
    print(f"  → Algo1: JS = {mean_a1:.4f} ± {std_a1:.4f}")
    sign = '+' if vs_algo1_best >= 0 else ''
    print(f"    (Algo1 best {ALGO1_BEST} 대비 {sign}{vs_algo1_best:.1f}%)")

    # ── Algo2 FC ─────────────────────────────────────────────────────────────
    r_a2 = None
    if run_algo2:
        print(f"\n  [Algo2 FC N=3]")
        r_a2 = run_algo2_fc(shared, cont_act, n_trials=3, epochs=80)
        if 'error' not in r_a2:
            vs_algo2_best = 100 * (r_a2['js_mean'] - ALGO2_BEST) / ALGO2_BEST if ALGO2_BEST > 0 else 0
            print(f"    (Algo2 best {ALGO2_BEST} 대비 {vs_algo2_best:+.1f}%)")

    return {
        'config': {'alpha': alpha, 'ow': ow, 'dw': dw, 'rc': rc, 'rate_t': RATE_T},
        'K': K,
        'ph_time_s': round(ph_time, 1),
        'greedy_time_s': round(greedy_time, 1),
        'best_taus': [round(t, 2) for t in best_taus],
        'tau_baseline_js': round(base_mean, 4),
        'greedy_percycle': {
            'js_mean': round(pc_mean, 4),
            'js_std':  round(pc_std, 4),
            'improvement_pct': round(impr, 1),
        },
        'algo1': {
            'js_mean': round(mean_a1, 4),
            'js_std':  round(std_a1, 4),
            'all_js':  [round(float(x), 4) for x in arr_a1],
            'n': n_algo1,
            'vs_algo1_best_pct': round(vs_algo1_best, 1),
        },
        'algo2_fc': r_a2,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 65)
    print("  Complex PH + per-cycle τ_c + Algo2(FC) 통합 실험")
    print(f"  Algo1 best: {ALGO1_BEST}  Algo2 best: {ALGO2_BEST}")
    print("=" * 65)

    # ── 전처리 1회 (모든 실험 공유) ────────────────────────────────────────────
    print("\n[전처리]")
    base_p = TDAMusicPipeline(PipelineConfig())
    base_p.run_preprocessing()
    preproc_cache = dict(base_p._cache)

    # note_time_df: 전처리 기반, PH와 무관하게 공통
    note_time_df = build_note_time_df(base_p)

    shared = {
        'notes_label':  base_p._cache['notes_label'],
        'notes_counts': base_p._cache['notes_counts'],
        'inst1_real':   base_p._cache['inst1_real'],
        'inst2_real':   base_p._cache['inst2_real'],
        'note_time_df': note_time_df,
        'T': T_TOTAL,
    }
    print(f"전처리 완료: notes={len(shared['notes_label'])}종")

    all_results = {}

    # ── 실험 0 ─────────────────────────────────────────────────────────────────
    print("\n\n" + "█" * 65)
    print("  실험 0: ow 재검증")
    print("█" * 65)
    r0 = experiment_0_ow_revalidation(preproc_cache, shared)
    all_results['exp0_ow_revalidation'] = r0

    # ── 실험 A ─────────────────────────────────────────────────────────────────
    print("\n\n" + "█" * 65)
    print("  실험 A: 기준선 재확인 (pkl 캐시 + 기존 per-cycle τ)")
    print("█" * 65)
    percycle_path = 'docs/step3_data/percycle_tau_n20_results.json'
    rA = experiment_A_baseline(shared, percycle_path)
    all_results['exp_A_baseline'] = rA

    # ── 실험 B ─────────────────────────────────────────────────────────────────
    print("\n\n" + "█" * 65)
    print("  실험 B: complex 최적 (α=0.25 ow=0.0 dw=0.3 r_c=0.1) + per-cycle τ")
    print("█" * 65)
    rB = experiment_complex_percycle(
        label='B', preproc_cache=preproc_cache, shared=shared,
        alpha=0.25, ow=0.0, dw=0.3, rc=0.1,
        n_algo1=10, run_algo2=True
    )
    all_results['exp_B_complex_optimal'] = rB

    # ── 실험 C ─────────────────────────────────────────────────────────────────
    print("\n\n" + "█" * 65)
    print("  실험 C: complex 2위 (α=0.5 ow=0.3 dw=0.3 r_c=0.1) + per-cycle τ")
    print("█" * 65)
    rC = experiment_complex_percycle(
        label='C', preproc_cache=preproc_cache, shared=shared,
        alpha=0.5, ow=0.3, dw=0.3, rc=0.1,
        n_algo1=5, run_algo2=False
    )
    all_results['exp_C_complex_2nd'] = rC

    # ── 저장 ──────────────────────────────────────────────────────────────────
    out_dir  = 'docs/step3_data'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'complex_percycle_results.json')

    payload = {
        'experiment':  'complex_PH_percycle_tau_integration',
        'date':        '2026-04-15',
        'reference': {
            'algo1_best_timeflow_percycle_n20': ALGO1_BEST,
            'algo2_best_fc_continuous':         ALGO2_BEST,
        },
        'results': all_results,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 최종 요약 ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  최종 요약")
    print("=" * 65)
    print(f"  {'실험':6s}  {'설정':30s}  {'Algo1 JS':>10s}  {'K':>5s}  {'vs best':>8s}")
    print("  " + "─" * 65)

    def _row(tag, cfg_str, r):
        if 'error' in r: return
        a1 = r.get('algo1', {})
        js = a1.get('js_mean', float('nan'))
        K  = r.get('K', '?')
        vs = 100 * (js - ALGO1_BEST) / ALGO1_BEST
        sign = '+' if vs >= 0 else ''
        mark = '★' if js < ALGO1_BEST else ' '
        print(f"{mark} {tag:6s}  {cfg_str:30s}  {js:>10.4f}  {K:>5}  {sign}{vs:.1f}%")

    _row('A', 'timeflow+per-cycle τ(기존)', rA)
    _row('B', 'complex(α=0.25,ow=0.0,rc=0.1)', rB)
    _row('C', 'complex(α=0.5,ow=0.3,rc=0.1)', rC)

    print(f"\n  기준: Algo1 best = {ALGO1_BEST}  Algo2 best = {ALGO2_BEST}")

    # Algo2 결과
    for exp_tag, r in [('A', rA), ('B', rB)]:
        a2 = r.get('algo2_fc')
        if a2 and 'error' not in a2:
            vs = 100 * (a2['js_mean'] - ALGO2_BEST) / ALGO2_BEST if ALGO2_BEST > 0 else 0
            sign = '+' if vs >= 0 else ''
            mark = '★' if a2['js_mean'] < ALGO2_BEST else ' '
            print(f"  {mark} Algo2 {exp_tag}: FC cont JS={a2['js_mean']:.4f}  (Algo2 best 대비 {sign}{vs:.1f}%)")

    print("\n[완료]")


if __name__ == '__main__':
    main()
