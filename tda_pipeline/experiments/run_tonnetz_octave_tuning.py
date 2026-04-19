"""
run_tonnetz_octave_tuning.py — Tonnetz octave_weight 계수 튜닝 실험
====================================================================

실험 1: hibari Algo1 JS를 N=10으로 측정하며
  octave_weight in [0.1, 0.3, 0.5, 0.7, 1.0] 비교.
  현재 기본값 0.5가 최적인지 확인.

결과: docs/step3_data/tonnetz_octave_tuning_results.json
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
ALPHA = 0.5   # 빈도-음악 혼합 비율 (기존 기본값)
OCTAVE_WEIGHTS = [0.1, 0.3, 0.5, 0.7, 1.0]


# ─── hibari 전처리 (precompute_metrics.py 동일 방식) ─────────────────────────
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
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    return {
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'intra': intra, 'inter': inter, 'oor': oor,
        'N': N, 'T': T,
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
    }


# ─── 특정 octave_weight로 PH → overlap 구축 ──────────────────────────────────
def build_overlap(data, octave_weight):
    nl = data['notes_label']; nd = data['notes_dict']
    intra = data['intra']; inter = data['inter']; oor = data['oor']
    N = data['N']; T = data['T']; adn_i = data['adn_i']

    # tonnetz 거리 행렬 (해당 octave_weight 적용)
    m_dist = compute_note_distance_matrix(
        nl, metric='tonnetz', octave_weight=octave_weight
    )

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


# ─── Algo1 단일 실행 ──────────────────────────────────────────────────────────
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
    print("  Tonnetz octave_weight 튜닝 실험")
    print(f"  N={N_REPEATS}, alpha={ALPHA}")
    print(f"  octave_weights={OCTAVE_WEIGHTS}")
    print("=" * 60)

    data = setup_hibari()
    print(f"\n전처리 완료: N={data['N']}, T={data['T']}, notes={len(data['notes_label'])}")

    results = {
        'n_repeats': N_REPEATS,
        'alpha': ALPHA,
        'experiments': {},
        'baseline_ref': {
            'octave_weight': 0.5,
            'js_mean_from_paper': 0.0398,
            'source': '§3.1 N=20 기준 (캐시, single-lag)'
        }
    }

    for ow in OCTAVE_WEIGHTS:
        print(f"\n[octave_weight = {ow}]")
        t0 = time.time()
        overlap, cycle_labeled = build_overlap(data, ow)
        ph_time = time.time() - t0
        n_cyc = len(cycle_labeled)
        print(f"  {n_cyc} cycles, PH {ph_time:.1f}s")

        if n_cyc == 0:
            print("  → cycle 없음, skip")
            results['experiments'][str(ow)] = {
                'octave_weight': ow, 'n_cycles': 0, 'error': 'no cycles'
            }
            continue

        ov = overlap.values
        trials_js = []
        for i in range(N_REPEATS):
            r = run_algo1_once(data, ov, cycle_labeled, seed=5000 + i)
            js = r['js_divergence']
            trials_js.append(js)
            print(f"  [{i+1:2d}] JS={js:.4f}  notes={r['n_notes']}")

        js_arr = np.array(trials_js)
        results['experiments'][str(ow)] = {
            'octave_weight': ow,
            'n_cycles': n_cyc,
            'ph_time_s': round(ph_time, 1),
            'js_mean': round(float(js_arr.mean()), 4),
            'js_std':  round(float(js_arr.std(ddof=1)), 4),
            'js_min':  round(float(js_arr.min()), 4),
            'js_max':  round(float(js_arr.max()), 4),
        }
        print(f"  → JS = {js_arr.mean():.4f} ± {js_arr.std(ddof=1):.4f}")

    # 최적 octave_weight
    best_ow = min(
        (k for k, v in results['experiments'].items() if 'js_mean' in v),
        key=lambda k: results['experiments'][k]['js_mean'],
        default=None
    )
    results['best_octave_weight'] = float(best_ow) if best_ow else None

    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/tonnetz_octave_tuning_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")

    print("\n[요약]")
    print(f"  {'ow':>6s}  {'JS mean':>10s}  {'JS std':>8s}  {'K':>4s}")
    print("  " + "─" * 34)
    for ow_str, r in results['experiments'].items():
        if 'js_mean' not in r:
            continue
        mark = " ★" if str(r['octave_weight']) == str(best_ow) else ""
        print(f"  {r['octave_weight']:>6.1f}  {r['js_mean']:>10.4f}  "
              f"{r['js_std']:>8.4f}  {r['n_cycles']:>4d}{mark}")


if __name__ == "__main__":
    main()
