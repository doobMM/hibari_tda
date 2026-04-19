"""
run_dw_gridsearch.py — duration_weight (w_d) grid search (hibari, Tonnetz, N=10)

octave_weight 튜닝(§4.1a, run_tonnetz_octave_tuning.py)과 동일한 방식:
  - 거리 함수: Tonnetz
  - octave_weight=0.3 고정 (§4.1a 최적값)
  - w_d 후보: {0.0, 0.1, 0.3, 0.5, 0.7, 1.0}
  - w_d별로 PH → overlap → Algo1 N=10 실행
  - 결과: docs/step3_data/dw_gridsearch_results.json
"""
import sys, os, json, time, random, pickle
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

N_REPEATS = 10
ALPHA = 0.5          # 빈도-음악 혼합 비율 (기존 기본값, octave 튜닝과 동일)
OCTAVE_WEIGHT = 0.3  # §4.1a 최적값 고정
DW_CANDIDATES = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]


def setup_hibari():
    """run_tonnetz_octave_tuning.py와 동일한 전처리."""
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
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    return {
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'intra': intra, 'inter': inter, 'oor': oor,
        'N': N, 'T': T,
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
    }


def build_overlap(data, duration_weight):
    """특정 duration_weight로 PH → overlap 구축 (PH 전체 재실행)."""
    nl = data['notes_label']; nd = data['notes_dict']
    intra = data['intra']; inter = data['inter']; oor = data['oor']
    N = data['N']; T = data['T']; adn_i = data['adn_i']

    # Tonnetz 거리 행렬 (octave_weight=0.3 고정, duration_weight 변화)
    m_dist = compute_note_distance_matrix(
        nl, metric='tonnetz',
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=duration_weight,
    )

    # PH sweep (rate 0.0 ~ 1.5)
    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, nd, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)

    # overlap 행렬 구축
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
    result = evaluate_generation(
        generated,
        [data['inst1_real'], data['inst2_real']],
        data['notes_label'], name=""
    )
    return result


def main():
    print("=" * 60)
    print("  duration_weight (w_d) Grid Search — hibari Tonnetz N=10")
    print(f"  octave_weight={OCTAVE_WEIGHT} (고정), alpha={ALPHA}")
    print(f"  candidates={DW_CANDIDATES}")
    print("=" * 60)

    data = setup_hibari()
    print(f"\n전처리 완료: N={data['N']}, T={data['T']}, "
          f"notes={len(data['notes_label'])}종")

    results = {}

    for dw in DW_CANDIDATES:
        print(f"\n[w_d = {dw}]")
        t0 = time.time()
        overlap, cycle_labeled = build_overlap(data, dw)
        ph_time = time.time() - t0
        n_cyc = len(cycle_labeled)
        print(f"  {n_cyc} cycles, PH {ph_time:.1f}s")

        if n_cyc == 0:
            print("  → cycle 없음, skip")
            results[str(dw)] = {'dw': dw, 'n_cycles': 0, 'error': 'no cycles'}
            continue

        ov = overlap.values if hasattr(overlap, 'values') else overlap
        trials_js = []
        for i in range(N_REPEATS):
            r = run_algo1_once(data, ov, cycle_labeled, seed=100 + i)
            js = r['js_divergence']
            trials_js.append(js)
            print(f"    [{i+1:2d}] JS={js:.4f}")

        js_mean = float(np.mean(trials_js))
        js_std  = float(np.std(trials_js, ddof=1))
        results[str(dw)] = {
            'dw': dw,
            'n_cycles': n_cyc,
            'js_mean': round(js_mean, 4),
            'js_std':  round(js_std,  4),
            'all_js':  [round(v, 4) for v in trials_js],
            'n': N_REPEATS,
        }
        print(f"  JS: {js_mean:.4f} ± {js_std:.4f}")

    # 요약
    print("\n" + "=" * 60)
    print("  결과 요약")
    print(f"  {'w_d':>5}  {'K':>4}  {'JS mean':>9}  {'JS std':>8}")
    print("-" * 40)
    best_dw, best_js = None, float('inf')
    for dw in DW_CANDIDATES:
        r = results.get(str(dw), {})
        if 'error' in r:
            print(f"  {dw:>5.1f}  {'—':>4}  {'—':>9}  {'—':>8}  (skip)")
            continue
        jm = r['js_mean']; jstd = r['js_std']; K = r['n_cycles']
        marker = " ★" if jm < best_js else ""
        if jm < best_js:
            best_js = jm; best_dw = dw
        print(f"  {dw:>5.1f}  {K:>4}  {jm:>9.4f}  {jstd:>8.4f}{marker}")
    print(f"\n  최적: w_d = {best_dw}  (JS = {best_js:.4f})")

    # 저장
    out = {
        'experiment': 'dw_gridsearch_hibari_tonnetz',
        'date': '2026-04-16',
        'config': {
            'metric': 'tonnetz',
            'octave_weight': OCTAVE_WEIGHT,
            'alpha': ALPHA,
            'n_repeats': N_REPEATS,
            'candidates': DW_CANDIDATES,
        },
        'best_dw': best_dw,
        'best_js': round(best_js, 4),
        'results': results,
    }
    out_path = os.path.join("docs", "step3_data", "dw_gridsearch_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")


if __name__ == '__main__':
    main()
