"""
run_complex_n20.py — complex + per-cycle τ N=20 재검증 (절대 최저 설정 확정)
===========================================================================

실험 B 확장 (N=20): α=0.25, ow=0.0, dw=0.3, r_c=0.1
  → 기존 N=10 결과에 N=10 추가, 동일 best_taus 재사용 (greedy 생략)

실험 D (N=20): α=0.5, ow=0.3, dw=0.3, r_c=0.1  ← 실험 C N=5 재검증
  → 신규 greedy per-cycle τ + Algo1 N=20 + Algo2 FC N=3

실험 E (N=20): α=0.25, ow=0.0, dw=0.3, r_c=0.3  ← grid 실제 2위 후보
  → 신규 greedy per-cycle τ + Algo1 N=20

통계: B vs D, B vs E — Welch t-test (equal_var=False)

결과: docs/step3_data/complex_percycle_n20_results.json
"""

import os, sys, json, time, random, pickle
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from preprocessing import simul_chord_lists, simul_union_by_dict
from overlap import build_activation_matrix
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

RATE_T    = 0.3
TAU_VALS  = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]
T_TOTAL   = 1088
ALGO1_MOD = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
             4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]

# 이전 실험 B 결과 (complex_percycle_results.json)
B_PREV_JS = [0.0198,0.0175,0.0185,0.0188,0.0184,
             0.0173,0.0185,0.0171,0.0182,0.0179]   # N=10
B_BEST_TAUS = [0.3,0.1,0.5,0.6,0.5,0.4,0.1,0.4,0.35,0.6,
               0.7,0.1,0.6,0.5,0.3,0.6,0.7,0.1,0.1,0.1,
               0.1,0.5,0.3,0.1,0.1,0.7,0.6,0.6,0.4,0.1,
               0.7,0.1,0.7,0.35,0.1,0.35,0.3,0.1,0.6,0.1]


# ─── 공통 유틸 ────────────────────────────────────────────────────────────────

def build_note_time_df(p):
    adn_i      = p._cache['adn_i']
    notes_dict = p._cache['notes_dict']
    notes_label= p._cache['notes_label']
    chord_pairs= simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets  = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T_TOTAL, len(nodes_list)), dtype=int)
    for t in range(min(T_TOTAL, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


def run_algo1_once(shared, ov, cyc, seed):
    random.seed(seed); np.random.seed(seed)
    pool    = NodePool(shared['notes_label'], shared['notes_counts'], num_modules=65)
    manager = CycleSetManager(cyc)
    gen = algorithm1_optimized(pool, ALGO1_MOD*33, ov, manager,
                                max_resample=50, verbose=False)
    return evaluate_generation(gen, [shared['inst1_real'], shared['inst2_real']],
                                shared['notes_label'], name="")


def mean_js(shared, ov, cyc, n, seed_base):
    vals = [run_algo1_once(shared, ov, cyc, seed_base+i)['js_divergence']
            for i in range(n)]
    return float(np.mean(vals)), float(np.std(vals, ddof=1) if n>1 else 0.0)


def eval_n20(shared, ov, cyc, n, seed_base, label=""):
    js_vals = []; t0 = time.time()
    for i in range(n):
        r = run_algo1_once(shared, ov, cyc, seed_base+i)
        js_vals.append(r['js_divergence'])
        if i % 5 == 0 or i == n-1:
            print(f"    [{i+1:2d}/{n}] JS={js_vals[-1]:.4f}  {time.time()-t0:.1f}s")
    arr = np.array(js_vals)
    return arr, float(arr.mean()), float(arr.std(ddof=1) if n>1 else 0.0)


def greedy_percycle_tau(shared, cont_act, cyc, seed_base=5000):
    K = cont_act.shape[1]
    baseline_ov = (cont_act >= 0.35).astype(np.float32)
    base_mean, base_std = mean_js(shared, baseline_ov, cyc, 5, seed_base)
    print(f"    baseline (τ=0.35): JS = {base_mean:.4f} ± {base_std:.4f}")

    best_taus = [0.35] * K
    for c in range(K):
        best_tau_c, best_js_c = 0.35, float('inf')
        for tau in TAU_VALS:
            tt = list(best_taus); tt[c] = tau
            ov = np.zeros_like(cont_act)
            for ci, t in enumerate(tt):
                ov[:, ci] = (cont_act[:, ci] >= t).astype(float)
            js_m, _ = mean_js(shared, ov, cyc, 5, seed_base + c*100 + 1)
            if js_m < best_js_c:
                best_js_c, best_tau_c = js_m, tau
        best_taus[c] = best_tau_c
        arrow = '↓' if best_js_c < base_mean else '↑'
        print(f"    cycle {c:2d}: τ={best_tau_c:.2f}  JS={best_js_c:.4f}  {arrow}")

    final_ov = np.zeros_like(cont_act)
    for ci, t in enumerate(best_taus):
        final_ov[:, ci] = (cont_act[:, ci] >= t).astype(float)
    final_mean, final_std = mean_js(shared, final_ov, cyc, 10, seed_base+9000)
    impr = 100*(base_mean - final_mean)/base_mean
    print(f"    per-cycle τ 결과: JS = {final_mean:.4f} ± {final_std:.4f}  ({impr:+.1f}%)")
    return best_taus, base_mean, final_ov, final_mean, final_std, impr


def run_algo2_fc(shared, cont_act, n_trials=3, epochs=80):
    try:
        import torch
        from generation import (MusicGeneratorFC, prepare_training_data,
                                 train_model, generate_from_model)
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        return {'error': str(e)}
    N = len(shared['notes_label'])
    K = cont_act.shape[1]
    X, y = prepare_training_data(cont_act, [shared['inst1_real'], shared['inst2_real']],
                                  shared['notes_label'], T_TOTAL, N)
    X_tr, X_v, y_tr, y_v = train_test_split(X, y, test_size=0.2, random_state=42)
    torch.manual_seed(42)
    model = MusicGeneratorFC(num_cycles=K, num_notes=N, hidden_dim=128, dropout=0.3)
    t0 = time.time()
    hist = train_model(model, X_tr, y_tr, X_v, y_v,
                       epochs=epochs, lr=0.001, batch_size=32,
                       model_type='fc', seq_len=T_TOTAL)
    tt = time.time()-t0
    vl = hist[-1]['val_loss'] if hist else None
    print(f"  Algo2 FC 학습 완료: {tt:.1f}s  val_loss={vl:.4f}" if vl else f"  완료 {tt:.1f}s")
    js_list = []
    for i in range(n_trials):
        torch.manual_seed(i); random.seed(i); np.random.seed(i)
        gen = generate_from_model(model, cont_act, shared['notes_label'],
                                  model_type='fc', adaptive_threshold=True)
        js_list.append(1.0 if not gen else
                       evaluate_generation(gen, [shared['inst1_real'],shared['inst2_real']],
                                           shared['notes_label'], name="")['js_divergence'])
        print(f"    trial {i}: JS={js_list[-1]:.4f}")
    arr = np.array(js_list)
    print(f"  → Algo2 FC: JS = {arr.mean():.4f} ± {arr.std(ddof=1 if len(js_list)>1 else 0):.4f}")
    return {'js_mean': round(float(arr.mean()),4),
            'js_std':  round(float(arr.std(ddof=1) if len(js_list)>1 else 0.0),4),
            'all_js':  [round(float(x),4) for x in js_list],
            'train_time_s': round(tt,1), 'val_loss': round(float(vl),4) if vl else None}


def welch_ttest(arr1, arr2, label1, label2):
    t, p = stats.ttest_ind(arr1, arr2, equal_var=False)
    m1, m2 = arr1.mean(), arr2.mean()
    delta = 100*(m2-m1)/m1
    sig = "★ 유의 (p<0.05)" if p < 0.05 else "(유의하지 않음)"
    print(f"  {label1}(n={len(arr1)}) vs {label2}(n={len(arr2)}):")
    print(f"    {label1} mean={m1:.4f}  {label2} mean={m2:.4f}  Δ={delta:+.1f}%")
    print(f"    t={t:.3f}  p={p:.4f}  {sig}")
    return {'t': round(float(t),4), 'p': round(float(p),4),
            'significant': bool(p<0.05), 'delta_pct': round(delta,1),
            'mean1': round(float(m1),4), 'mean2': round(float(m2),4)}


def run_complex_experiment(label, preproc_cache, shared, alpha, ow, dw, rc,
                           n_algo1, run_algo2=False, greedy_seed_base=5000):
    """complex PH → greedy τ → Algo1 N=n_algo1 → (optional) Algo2."""
    print(f"\n{'─'*60}")
    print(f"  실험 {label}: α={alpha}, ow={ow}, dw={dw}, r_c={rc}  [N={n_algo1}]")
    print(f"{'─'*60}")

    cfg = PipelineConfig()
    cfg.metric.metric          = 'tonnetz'
    cfg.metric.alpha           = alpha
    cfg.metric.octave_weight   = ow
    cfg.metric.duration_weight = dw

    p = TDAMusicPipeline(cfg)
    p._cache.update(preproc_cache)

    t0 = time.time()
    p.run_homology_search(search_type='complex', dimension=1, rate_t=RATE_T, rate_s=rc)
    p.run_overlap_construction(persistence_key='h1_complex_lag1')
    ph_time = time.time()-t0

    cyc = p._cache['cycle_labeled']
    K   = len(cyc)
    print(f"  PH: K={K}  ({ph_time:.1f}s)")

    note_time_df = shared['note_time_df']
    cont_act = build_activation_matrix(note_time_df, cyc, continuous=True).values.astype(np.float32)

    print(f"\n  [Greedy per-cycle τ]")
    t0 = time.time()
    best_taus, base_mean, percycle_ov, pc_mean, pc_std, impr = greedy_percycle_tau(
        shared, cont_act, cyc, seed_base=greedy_seed_base)
    greedy_time = time.time()-t0
    print(f"  greedy 완료: {greedy_time:.1f}s")

    print(f"\n  [Algo1 N={n_algo1}]")
    seed_a1 = 20000 + ord(label)*100
    arr_a1, mean_a1, std_a1 = eval_n20(shared, percycle_ov, cyc, n_algo1, seed_a1)

    r_a2 = None
    if run_algo2:
        print(f"\n  [Algo2 FC N=3]")
        r_a2 = run_algo2_fc(shared, cont_act, n_trials=3, epochs=80)

    return {
        'config': {'alpha':alpha,'ow':ow,'dw':dw,'rc':rc,'rate_t':RATE_T},
        'K': K,
        'ph_time_s': round(ph_time,1),
        'greedy_time_s': round(greedy_time,1),
        'best_taus': [round(t,2) for t in best_taus],
        'tau_baseline_js': round(base_mean,4),
        'greedy_percycle': {'js_mean':round(pc_mean,4),'js_std':round(pc_std,4),
                             'improvement_pct':round(impr,1)},
        'algo1': {'js_mean':round(mean_a1,4),'js_std':round(std_a1,4),
                  'all_js':[round(float(x),4) for x in arr_a1],'n':n_algo1},
        'algo2_fc': r_a2,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 65)
    print("  complex + per-cycle τ N=20 재검증 — 절대 최저 확정")
    print("  실험 B 확장 / 실험 D (α=0.5) / 실험 E (r_c=0.3)")
    print("=" * 65)

    # ── 전처리 ─────────────────────────────────────────────────────────────────
    print("\n[전처리]")
    base_p = TDAMusicPipeline(PipelineConfig())
    base_p.run_preprocessing()
    preproc_cache = dict(base_p._cache)

    note_time_df = build_note_time_df(base_p)
    shared = {
        'notes_label':  base_p._cache['notes_label'],
        'notes_counts': base_p._cache['notes_counts'],
        'inst1_real':   base_p._cache['inst1_real'],
        'inst2_real':   base_p._cache['inst2_real'],
        'note_time_df': note_time_df,
    }
    print(f"전처리 완료: notes={len(shared['notes_label'])}종")

    all_results = {}

    # ── 실험 B 확장: 기존 best_taus + N=10 추가 ────────────────────────────────
    print("\n" + "█"*65)
    print("  실험 B 확장 (N=10 추가 → 총 N=20)")
    print("  α=0.25, ow=0.0, dw=0.3, r_c=0.1 | best_taus 재사용")
    print("█"*65)

    # complex PH 재계산 (cycle_labeled 필요)
    cfg_b = PipelineConfig()
    cfg_b.metric.metric = 'tonnetz'; cfg_b.metric.alpha = 0.25
    cfg_b.metric.octave_weight = 0.0; cfg_b.metric.duration_weight = 0.3
    pb = TDAMusicPipeline(cfg_b); pb._cache.update(preproc_cache)
    pb.run_homology_search(search_type='complex', dimension=1, rate_t=RATE_T, rate_s=0.1)
    pb.run_overlap_construction(persistence_key='h1_complex_lag1')
    cyc_b = pb._cache['cycle_labeled']
    K_b   = len(cyc_b)
    print(f"  K={K_b} (이전 실험 B K=40 확인)")

    cont_b = build_activation_matrix(note_time_df, cyc_b, continuous=True).values.astype(np.float32)

    # best_taus 적용
    best_taus_b = B_BEST_TAUS[:K_b]  # K 일치 확인
    percycle_ov_b = np.zeros_like(cont_b)
    for ci, tau in enumerate(best_taus_b):
        percycle_ov_b[:, ci] = (cont_b[:, ci] >= tau).astype(float)

    print(f"\n  [N=10 추가 평가] (seed 30000~30009)")
    arr_b_ext, mean_b_ext, std_b_ext = eval_n20(shared, percycle_ov_b, cyc_b, 10, 30000)

    # 기존 N=10 + 신규 N=10 합산
    arr_b_all  = np.array(B_PREV_JS + list(arr_b_ext))
    mean_b_all = float(arr_b_all.mean())
    std_b_all  = float(arr_b_all.std(ddof=1))
    print(f"\n  B 합산 N=20: JS = {mean_b_all:.4f} ± {std_b_all:.4f}")
    print(f"  (기존 N=10: {np.mean(B_PREV_JS):.4f}, 신규 N=10: {mean_b_ext:.4f})")

    all_results['exp_B_extended'] = {
        'config': {'alpha':0.25,'ow':0.0,'dw':0.3,'rc':0.1,'rate_t':RATE_T},
        'K': K_b,
        'best_taus_source': 'reused_from_prev_experiment',
        'best_taus': B_BEST_TAUS,
        'algo1': {
            'js_mean': round(mean_b_all,4), 'js_std': round(std_b_all,4),
            'all_js_prev_n10': B_PREV_JS,
            'all_js_new_n10':  [round(float(x),4) for x in arr_b_ext],
            'all_js_n20':      [round(float(x),4) for x in arr_b_all],
            'n': 20,
        },
    }

    # ── 실험 D ─────────────────────────────────────────────────────────────────
    print("\n" + "█"*65)
    print("  실험 D: α=0.5, ow=0.3, dw=0.3, r_c=0.1  [N=20 + Algo2]")
    print("█"*65)
    rD = run_complex_experiment(
        'D', preproc_cache, shared,
        alpha=0.5, ow=0.3, dw=0.3, rc=0.1,
        n_algo1=20, run_algo2=True, greedy_seed_base=5400
    )
    all_results['exp_D'] = rD

    # ── 실험 E ─────────────────────────────────────────────────────────────────
    print("\n" + "█"*65)
    print("  실험 E: α=0.25, ow=0.0, dw=0.3, r_c=0.3  [N=20]")
    print("  (grid search 실제 2위 후보, 실험 B와 r_c만 다름)")
    print("█"*65)
    rE = run_complex_experiment(
        'E', preproc_cache, shared,
        alpha=0.25, ow=0.0, dw=0.3, rc=0.3,
        n_algo1=20, run_algo2=False, greedy_seed_base=5800
    )
    all_results['exp_E'] = rE

    # ── 통계 비교 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  Welch t-test 비교")
    print("=" * 65)

    arr_b = arr_b_all
    arr_d = np.array(rD['algo1']['all_js'])
    arr_e = np.array(rE['algo1']['all_js'])

    stats_results = {}
    stats_results['B_vs_D'] = welch_ttest(arr_b, arr_d, 'B(N=20)', 'D(N=20)')
    stats_results['B_vs_E'] = welch_ttest(arr_b, arr_e, 'B(N=20)', 'E(N=20)')
    stats_results['D_vs_E'] = welch_ttest(arr_d, arr_e, 'D(N=20)', 'E(N=20)')

    # 원래 N=10 B vs D/E 도 추가
    arr_b10 = np.array(B_PREV_JS)
    stats_results['B10_vs_D'] = welch_ttest(arr_b10, arr_d, 'B(N=10)', 'D(N=20)')
    stats_results['B10_vs_E'] = welch_ttest(arr_b10, arr_e, 'B(N=10)', 'E(N=20)')

    # ── 저장 ──────────────────────────────────────────────────────────────────
    out_dir  = 'docs/step3_data'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'complex_percycle_n20_results.json')
    payload  = {
        'experiment': 'complex_percycle_n20_revalidation',
        'date': '2026-04-15',
        'reference': {
            'algo1_best_prev': 0.0241,
            'exp_B_prev_n10_mean': round(float(np.mean(B_PREV_JS)),4),
        },
        'results': all_results,
        'statistics': stats_results,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 최종 요약 ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  최종 요약 — 절대 최저 설정 확정")
    print("=" * 65)

    rows = [
        ('B(N=20)', '0.25/0.0/0.1', K_b,   arr_b_all),
        ('D(N=20)', '0.5/0.3/0.1',  rD['K'], arr_d),
        ('E(N=20)', '0.25/0.0/0.3', rE['K'], arr_e),
    ]
    print(f"  {'실험':10s}  {'α/ow/rc':12s}  {'K':>5s}  {'JS mean':>9s}  {'JS std':>7s}")
    print("  " + "─"*55)
    best_exp = min(rows, key=lambda r: r[3].mean())
    for tag, cfg_s, K, arr in rows:
        mark = '★' if tag == best_exp[0] else ' '
        print(f"{mark} {tag:10s}  {cfg_s:12s}  {K:5d}  {arr.mean():9.4f}  {arr.std(ddof=1):7.4f}")

    print(f"\n  ★ 최저: {best_exp[0]}  JS={best_exp[3].mean():.4f}")
    winner_cfg = next(r for t,r in [('B(N=20)',all_results['exp_B_extended']),
                                     ('D(N=20)',rD),('E(N=20)',rE)]
                      if t == best_exp[0])
    c = winner_cfg['config']
    print(f"    설정: complex, α={c['alpha']}, ow={c.get('ow',c.get('octave_weight','?'))}, "
          f"dw={c.get('dw',c.get('duration_weight','?'))}, r_c={c['rc']}")

    # Algo2 요약
    a2 = rD.get('algo2_fc')
    if a2 and 'error' not in a2:
        print(f"\n  Algo2 FC (실험 D): JS = {a2['js_mean']:.4f}"
              f"  (이전 best 0.0003 대비 {100*(a2['js_mean']-0.0003)/0.0003:+.1f}%)")

    # 통계 요약
    print(f"\n  통계 (B(N=20) vs 각 실험):")
    for key, label in [('B_vs_D','vs D'), ('B_vs_E','vs E')]:
        s = stats_results[key]
        sig_str = "유의" if s['significant'] else "비유의"
        print(f"    B {label}: p={s['p']:.4f} {sig_str}  Δ={s['delta_pct']:+.1f}%")

    # §7.9 추천
    best_tag  = best_exp[0]
    best_js   = round(float(best_exp[3].mean()), 4)
    best_std  = round(float(best_exp[3].std(ddof=1)), 4)
    winner_c  = winner_cfg['config']
    K_winner  = winner_cfg['K']
    print(f"\n  §7.9 논문용 추천:")
    print(f"    최적 설정: complex mode (α={winner_c['alpha']}, ow={winner_c.get('ow',0)}, "
          f"dw={winner_c.get('dw',0.3)}, r_c={winner_c['rc']}) + greedy per-cycle τ_c")
    print(f"    K={K_winner}  Algo1 JS={best_js}±{best_std} (N=20)")
    print(f"    기존 timeflow+per-cycle τ best(0.0241) 대비 "
          f"{100*(best_js-0.0241)/0.0241:+.1f}%")

    print("\n[완료]")


if __name__ == '__main__':
    main()
