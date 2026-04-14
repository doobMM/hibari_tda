"""
run_triad_sharing_experiment.py — Triad Sharing Distance N=20 비교 실험
=======================================================================

Tonnetz vs Triad Sharing Distance를 동일한 조건(alpha=0.5, lag=1)에서 비교한다.
- Tonnetz  : 기존 metric_tonnetz.pkl 캐시 사용  (§3.1 베이스라인과 동일 조건)
- Triad Sharing: 캐시 없으면 PH 재계산 후 저장

결과 저장: docs/step3_data/triad_sharing_results.json
"""

import os, sys, json, time, random, pickle
import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation


# ═══════════════════════════════════════════════════════════════════════════
# 0. Triad Sharing 공유 수 표 출력 (hibari 7 PC)
# ═══════════════════════════════════════════════════════════════════════════

def print_shared_triad_table():
    """hibari 7 pitch class 간 공유 triad 수 표를 출력한다."""
    from musical_metrics import _build_triad_sharing_table

    dist_table = _build_triad_sharing_table()
    # shared_count = 1 / dist (dist > 0인 경우)
    shared = np.zeros((12, 12), dtype=float)
    for i in range(12):
        for j in range(12):
            if i == j:
                shared[i, j] = 6   # 자기 자신은 6개 triad에 속함
            elif dist_table[i, j] > 0:
                shared[i, j] = round(1.0 / dist_table[i, j])

    # hibari pitch classes: C(0), D(2), E(4), F(5), G(7), A(9), B(11)
    hibari_pcs = [0, 2, 4, 5, 7, 9, 11]
    pc_names   = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

    print("\n" + "=" * 60)
    print("  Triad Sharing Count 표 — hibari 7 PC")
    print("=" * 60)
    print("  (자음 음정=2, 불협음 음정=0, 동일 PC=6)")
    print()

    # 헤더
    header = "    " + "".join(f"  {n}" for n in pc_names)
    print(header)
    print("    " + "─" * (len(pc_names) * 3))

    consonant_pairs, dissonant_pairs = [], []
    for i, (pc1, n1) in enumerate(zip(hibari_pcs, pc_names)):
        row = f"  {n1} |"
        for j, (pc2, n2) in enumerate(zip(hibari_pcs, pc_names)):
            cnt = int(shared[pc1, pc2])
            row += f"  {cnt}"
            if i < j:
                if cnt == 2:
                    consonant_pairs.append(f"{n1}-{n2}")
                elif cnt == 0:
                    dissonant_pairs.append(f"{n1}-{n2}")
        print(row)

    print()
    print(f"  자음 쌍 ({len(consonant_pairs)}개): {', '.join(consonant_pairs)}")
    print(f"  불협 쌍 ({len(dissonant_pairs)}개): {', '.join(dissonant_pairs)}")
    print()
    print("  [거리 해석]")
    print("  - 자음(공유=2) → distance ≈ 0.500   (Tonnetz 최대 4 대비 연속값)")
    print("  - 불협(공유=0) → distance ≈ 1,000,000 (정규화 후 1.0)")
    print("  → compute_hybrid_distance(alpha=0.5) 정규화 시:")
    print("    자음 쌍 ≈ 0.0,  불협 쌍 ≈ 1.0  (이진 효과)")
    print("=" * 60)

    return shared, consonant_pairs, dissonant_pairs


# ═══════════════════════════════════════════════════════════════════════════
# 1. Triad Sharing PH 캐시 구축 (metric_tonnetz.pkl과 동일 조건: lag=1, alpha=0.5)
# ═══════════════════════════════════════════════════════════════════════════

CACHE_DIR  = os.path.join(os.path.dirname(__file__), "cache")
TS_PKL     = os.path.join(CACHE_DIR, "metric_triad_sharing.pkl")
TON_PKL    = os.path.join(CACHE_DIR, "metric_tonnetz.pkl")
ALPHA      = 0.5   # metric_tonnetz.pkl 빌드와 동일


def build_triad_sharing_cache():
    """
    precompute_metrics.py의 build_overlap_for_metric()과 동일한 방식으로
    triad_sharing 캐시를 생성한다.

    조건: lag=1 단일 lag, alpha=0.5  ← metric_tonnetz.pkl 빌드와 동일
    """
    print("\n[캐시 빌드] metric_triad_sharing.pkl 생성 시작...")

    from preprocessing import (
        load_and_quantize, split_instruments, build_note_labels,
        group_notes_with_duration, build_chord_labels, chord_to_note_labels,
        prepare_lag_sequences, simul_chord_lists, simul_union_by_dict
    )
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach
    )
    from overlap import (
        group_rBD_by_homology, label_cycles_from_persistence,
        build_activation_matrix, build_overlap_matrix
    )
    from musical_metrics import (
        compute_note_distance_matrix, compute_hybrid_distance
    )

    # barcode 함수 선택
    from topology import _check_ripser
    if _check_ripser():
        from topology import generate_barcode_ripser as generateBarcode
        print("  barcode: ripser (고속)")
    else:
        from topology import generate_barcode_numpy as generateBarcode
        print("  barcode: numpy (표준, 시간 소요)")

    import pandas as pd

    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

    notes_label, notes_counts = build_note_labels(inst1_real[:59])
    ma = group_notes_with_duration(inst1_real[:59])
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    _, cs1 = build_chord_labels(group_notes_with_duration(inst1_real))
    _, cs2 = build_chord_labels(group_notes_with_duration(inst2_real))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    N = len(notes_label)
    T = 1088

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor   = compute_out_of_reach(inter, power=-2)

    # triad_sharing 거리 사전 계산
    m_dist = compute_note_distance_matrix(notes_label, metric='triad_sharing')
    print(f"  triad_sharing 거리 행렬: shape={m_dist.shape}, "
          f"min={m_dist.min():.4f}, max={m_dist.max():.2f}")

    # PH 탐색 (rate 0.00 → 1.50)
    t0 = time.time()
    profile = []
    rate = 0.0
    n_steps = 0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)

        bd = generateBarcode(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01
        n_steps += 1
        if n_steps % 30 == 0:
            elapsed = time.time() - t0
            print(f"  rate={r:.2f}  ({n_steps}/151 steps, {elapsed:.1f}s elapsed)")

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    print(f"  → {len(cycle_labeled)} cycles 발견  ({time.time()-t0:.1f}s)")

    # Overlap matrix
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets   = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list  = list(range(1, N + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation   = build_activation_matrix(note_time_df, cycle_labeled)
    overlap      = build_overlap_matrix(activation, cycle_labeled,
                                        threshold=0.35, total_length=T)

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(TS_PKL, 'wb') as f:
        pickle.dump({
            'overlap': overlap,
            'cycle_labeled': cycle_labeled,
            'metric': 'triad_sharing',
            'alpha': ALPHA,
        }, f)
    print(f"  저장 완료: {TS_PKL}")
    print(f"  overlap shape: {overlap.shape}, "
          f"ON ratio: {overlap.values.mean():.4f}")
    return overlap, cycle_labeled


# ═══════════════════════════════════════════════════════════════════════════
# 2. Algorithm 1 헬퍼
# ═══════════════════════════════════════════════════════════════════════════

METRIC_KEYS = ['js_divergence', 'kl_divergence', 'note_coverage',
               'n_notes', 'pitch_count', 'elapsed_s']


def setup_pipeline():
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    return p


def run_algo1_once(p, overlap_values, cycle_labeled, seed):
    random.seed(seed)
    np.random.seed(seed)

    notes_label  = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']

    pool    = NodePool(notes_label, notes_counts, num_modules=65)
    manager = CycleSetManager(cycle_labeled)

    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33

    t0 = time.time()
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False)
    elapsed = time.time() - t0

    result = evaluate_generation(
        generated,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        notes_label, name="")
    result['elapsed_s'] = elapsed
    return result


def aggregate(trials, keys):
    out = {}
    for k in keys:
        vals = [t[k] for t in trials]
        out[k] = {
            'mean': float(np.mean(vals)),
            'std':  float(np.std(vals, ddof=1) if len(vals) > 1 else 0.0),
            'runs': [float(v) for v in vals],
        }
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 3. 메인 실험
# ═══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-repeats', dest='n_repeats', type=int, default=20)
    parser.add_argument('--rebuild-cache', action='store_true',
                        help='기존 triad_sharing 캐시 무시하고 재빌드')
    args = parser.parse_args()

    # ── 0. Shared triad 수 표 출력 ──
    shared_table, cons_pairs, diss_pairs = print_shared_triad_table()

    # ── 1. Triad Sharing 캐시 준비 ──
    if args.rebuild_cache or not os.path.exists(TS_PKL):
        build_triad_sharing_cache()

    # ── 2. 캐시 로드 ──
    with open(TON_PKL, 'rb') as f:
        ton_cache = pickle.load(f)
    with open(TS_PKL, 'rb') as f:
        ts_cache = pickle.load(f)

    ton_overlap  = ton_cache['overlap']
    ton_cycles   = ton_cache['cycle_labeled']
    ts_overlap   = ts_cache['overlap']
    ts_cycles    = ts_cache['cycle_labeled']

    print(f"\n[로드 완료]")
    print(f"  tonnetz      : K={len(ton_cycles)} cycles, "
          f"overlap {ton_overlap.shape}, "
          f"ON={ton_overlap.values.mean():.4f}")
    print(f"  triad_sharing: K={len(ts_cycles)} cycles, "
          f"overlap {ts_overlap.shape}, "
          f"ON={ts_overlap.values.mean():.4f}")

    # ── 3. 전처리 ──
    p = setup_pipeline()
    print(f"  전처리 완료: notes_label={len(p._cache['notes_label'])}")

    # ── 4. N=20 실험 ──
    results_raw = {}
    for label, overlap_df, cycles in [
        ('tonnetz',       ton_overlap, ton_cycles),
        ('triad_sharing', ts_overlap,  ts_cycles),
    ]:
        ov = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df
        print(f"\n  → {label} ({args.n_repeats}회)")
        trials = []
        for i in range(args.n_repeats):
            r = run_algo1_once(p, ov, cycles, seed=1000 + i)
            trials.append(r)
            print(f"    [{i+1:2d}] JS={r['js_divergence']:.4f}  "
                  f"notes={r['n_notes']}  pitches={r['pitch_count']}  "
                  f"cov={r['note_coverage']:.2f}")
        agg = aggregate(trials, METRIC_KEYS)
        agg['n_cycles'] = len(cycles)
        results_raw[label] = agg
        print(f"    → JS mean={agg['js_divergence']['mean']:.4f} "
              f"± {agg['js_divergence']['std']:.4f}")

    # ── 5. t-test ──
    ton_js = results_raw['tonnetz']['js_divergence']['runs']
    ts_js  = results_raw['triad_sharing']['js_divergence']['runs']
    t_stat, p_value = stats.ttest_ind(ts_js, ton_js)
    significant = bool(p_value < 0.05)

    ton_mean = results_raw['tonnetz']['js_divergence']['mean']
    ts_mean  = results_raw['triad_sharing']['js_divergence']['mean']
    delta_pct = (ton_mean - ts_mean) / ton_mean * 100  # 양수 = triad_sharing 개선

    # ── 6. 결과 저장 ──
    out = {
        'triad_sharing': {
            'mean': ts_mean,
            'std':  results_raw['triad_sharing']['js_divergence']['std'],
            'runs': ts_js,
            'n_cycles': results_raw['triad_sharing']['n_cycles'],
        },
        'tonnetz': {
            'mean': ton_mean,
            'std':  results_raw['tonnetz']['js_divergence']['std'],
            'runs': ton_js,
            'n_cycles': results_raw['tonnetz']['n_cycles'],
        },
        't_test': {
            't_stat': float(t_stat),
            'p_value': float(p_value),
            'significant': significant,
        },
        'delta_pct': float(delta_pct),
        'n_repeats': args.n_repeats,
        'alpha': ALPHA,
        'condition': 'lag=1, alpha=0.5 (metric_tonnetz.pkl 빌드와 동일)',
        'shared_triad_table': {
            'consonant_pairs': cons_pairs,
            'dissonant_pairs': diss_pairs,
            'all_shared_values': [2, 0],
            'note': '자음 음정 쌍=2개 공유, 불협 음정 쌍=0개 공유 (이진 구조)',
        },
    }

    out_dir = os.path.join("docs", "step3_data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "triad_sharing_results.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 7. 최종 요약 ──
    print("\n" + "=" * 60)
    print("  최종 결과 요약")
    print("=" * 60)
    print(f"  tonnetz      : JS = {ton_mean:.4f} ± "
          f"{results_raw['tonnetz']['js_divergence']['std']:.4f}  "
          f"(K={results_raw['tonnetz']['n_cycles']})")
    print(f"  triad_sharing: JS = {ts_mean:.4f} ± "
          f"{results_raw['triad_sharing']['js_divergence']['std']:.4f}  "
          f"(K={results_raw['triad_sharing']['n_cycles']})")
    print(f"\n  delta_pct : {delta_pct:+.1f}%  "
          f"({'triad_sharing 개선' if delta_pct > 0 else 'triad_sharing 악화'})")
    print(f"  t-test    : t={t_stat:.3f}, p={p_value:.4f}  "
          f"({'유의 (p<0.05)' if significant else '비유의'})")
    print()
    print("  [공유 triad 구조]")
    print(f"   자음 쌍({len(cons_pairs)}개): {', '.join(cons_pairs)}")
    print(f"   불협 쌍({len(diss_pairs)}개): {', '.join(diss_pairs)}")
    print(f"   → 모든 자음 쌍이 공유 수=2로 동일 (Tonnetz보다 단조로운 거리 분포)")
    print("=" * 60)


if __name__ == '__main__':
    main()
