"""
run_combined_optimal.py — A-1 통합 조합 실험
=============================================

hibari에서 독립적으로 발견된 3개 최적 파라미터를 동시에 적용하여 시너지 검증.

  - octave_weight = 0.3  (기본 0.5 → JS -18.8%)
  - α = 0.0              (순수 Tonnetz, 기본 0.5 → JS -3.4%)
  - 감쇄 lag 가중치      (lag 1~4, DECAY_WEIGHTS=[0.60,0.30,0.08,0.02])

주의: ow와 α가 바뀌면 distance matrix가 달라지므로 캐시 우회 후 PH 재계산.

결과: docs/step3_data/combined_optimal_results.json
"""

import sys, os, json, time, random
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict
)
from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_inter_weights_decayed,
    compute_distance_matrix, compute_out_of_reach
)
from overlap import (
    group_rBD_by_homology, label_cycles_from_persistence,
    build_activation_matrix, build_overlap_matrix
)
from topology import generate_barcode_numpy
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

N_REPEATS = 20
OCTAVE_WEIGHT = 0.3   # ★ 최적: 기본 0.5 → -18.8%
ALPHA = 0.0           # ★ 최적: 순수 Tonnetz (α=0.0)
# 감쇄 lag 가중치는 compute_inter_weights_decayed()에서 [0.60,0.30,0.08,0.02] 적용


# ─── 비교 기준 ────────────────────────────────────────────────────────────────
BASELINES = {
    '구 기본 (ow=0.5, α=0.5, lag=1)':      0.0590,
    'ow=0.3 (α=0.5, lag=1)':               0.0479,
    'α=0.0 (ow=0.5, lag=1)':               0.0574,
    '감쇄 lag (ow=0.5, α=0.5, lag 1~4)':   0.0121,
}


# ─── hibari 전처리 ────────────────────────────────────────────────────────────
def setup_hibari():
    midi = "Ryuichi_Sakamoto_-_hibari.mid"
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

    # ★ 감쇄 lag: 단순 lag=1 대신 lag 1~4 감쇄 합산
    inter_decayed = compute_inter_weights_decayed(adn_i, max_lag=4)

    oor = compute_out_of_reach(inter_decayed, power=-2)

    # ★ Tonnetz 거리 행렬: octave_weight=0.3
    m_dist_tonnetz = compute_note_distance_matrix(
        notes_label, metric='tonnetz', octave_weight=OCTAVE_WEIGHT
    )

    return {
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'intra': intra, 'inter_decayed': inter_decayed, 'oor': oor,
        'N': N, 'T': T,
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
        'm_dist_tonnetz': m_dist_tonnetz,
    }


# ─── PH → overlap 구축 (ow=0.3, α=0.0, 감쇄 lag) ─────────────────────────────
def build_combined_overlap(data):
    nd = data['notes_dict']; nl = data['notes_label']
    intra = data['intra']; inter = data['inter_decayed']; oor = data['oor']
    N = data['N']; T = data['T']; adn_i = data['adn_i']
    m_dist = data['m_dist_tonnetz']  # ow=0.3

    # 기존 실험들과 동일하게 generate_barcode_numpy 사용 (일관성)
    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        # ★ 감쇄 inter 사용
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, nd, oor, num_notes=N).values

        # ★ α=0.0: 순수 Tonnetz
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=0.0)

        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, nd)
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(
        activation, cycle_labeled, threshold=0.35, total_length=T
    )
    return overlap, cycle_labeled


# ─── Algo1 단일 실행 ────────────────────────────────────────────────────────────
def run_algo1_once(data, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False
    )
    return evaluate_generation(
        generated,
        [data['inst1_real'], data['inst2_real']],
        data['notes_label'], name=""
    )


def main():
    print("=" * 65)
    print("  A-1 통합 조합 실험")
    print(f"  설정: octave_weight={OCTAVE_WEIGHT}, α={ALPHA}, 감쇄 lag(1~4)")
    print(f"  N={N_REPEATS} 반복, Algo1 JS 측정")
    print("=" * 65)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("\n[전처리 + 거리 행렬 계산]")
    t0 = time.time()
    data = setup_hibari()
    print(f"  완료: N={data['N']}, T={data['T']}  ({time.time()-t0:.1f}s)")
    print(f"  inter_decayed shape: {data['inter_decayed'].shape}")
    print(f"  Tonnetz 거리 (ow={OCTAVE_WEIGHT}) 계산 완료")

    print("\n[PH 계산 및 overlap 구축]")
    t0 = time.time()
    overlap, cycle_labeled = build_combined_overlap(data)
    ph_time = time.time() - t0
    K = len(cycle_labeled)
    print(f"  cycle 수: K={K}  PH 시간: {ph_time:.1f}s")

    if K == 0:
        print("  [오류] cycle이 없음. 파이프라인 설정 확인 필요.")
        return

    ov = overlap.values
    print(f"\n[Algo1 N={N_REPEATS} 실행]")
    trials_js = []
    t0 = time.time()
    for i in range(N_REPEATS):
        r = run_algo1_once(data, ov, cycle_labeled, seed=9000 + i)
        js = r['js_divergence']
        trials_js.append(js)
        if i % 5 == 0 or i == N_REPEATS - 1:
            elapsed = time.time() - t0
            print(f"  [{i+1:2d}/{N_REPEATS}] JS={js:.4f}  "
                  f"notes={r['n_notes']}  {elapsed:.1f}s")

    js_arr = np.array(trials_js)
    js_mean = float(js_arr.mean())
    js_std  = float(js_arr.std(ddof=1))

    # 비교
    print("\n[비교]")
    print(f"  {'설정':45s}  {'JS mean':>10s}")
    print("  " + "─" * 58)
    for label, val in BASELINES.items():
        tag = " ← 비교 기준" if '구 기본' in label else ""
        print(f"  {label:45s}  {val:.4f}{tag}")
    print(f"  {'★ 통합 조합 (ow=0.3, α=0.0, 감쇄 lag)':45s}  {js_mean:.4f} ± {js_std:.4f}")

    # 기준 대비 개선율
    baseline_old = BASELINES['구 기본 (ow=0.5, α=0.5, lag=1)']
    baseline_lag = BASELINES['감쇄 lag (ow=0.5, α=0.5, lag 1~4)']
    improvement_vs_old = 100 * (baseline_old - js_mean) / baseline_old
    improvement_vs_lag = 100 * (baseline_lag - js_mean) / baseline_lag

    print(f"\n  구 기본 대비 개선: {improvement_vs_old:+.1f}%")
    print(f"  감쇄 lag 단독 대비: {improvement_vs_lag:+.1f}%")

    results = {
        'experiment': 'A-1 통합 조합',
        'settings': {
            'octave_weight': OCTAVE_WEIGHT,
            'alpha': ALPHA,
            'lag': 'decayed (lag 1~4, w=[0.60,0.30,0.08,0.02])',
            'n_repeats': N_REPEATS,
            'n_cycles': K,
            'ph_time_s': round(ph_time, 1),
        },
        'result': {
            'js_mean': round(js_mean, 4),
            'js_std':  round(js_std, 4),
            'js_min':  round(float(js_arr.min()), 4),
            'js_max':  round(float(js_arr.max()), 4),
            'all_js':  [round(float(x), 4) for x in trials_js],
        },
        'baselines': BASELINES,
        'improvement': {
            'vs_old_baseline_pct':       round(improvement_vs_old, 1),
            'vs_decayed_lag_only_pct':   round(improvement_vs_lag, 1),
        },
    }

    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/combined_optimal_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")
    print("\n[완료]")


if __name__ == "__main__":
    main()
