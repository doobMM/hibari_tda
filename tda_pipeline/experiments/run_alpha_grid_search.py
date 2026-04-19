"""
run_alpha_grid_search.py — §7.8 Tonnetz Hybrid α grid search
==============================================================

§7.8에서 제안된 실험:
  α in [0.0, 0.1, 0.3, 0.5, 0.7, 1.0] 각각 N=20 반복 → JS mean ± std
  α=0.0: 순수 Tonnetz / α=1.0: 순수 frequency
  "빈도 거리와 음악이론적 거리의 최적 혼합 비율"을 정량적으로 제시.

힌트(memory): 단일 run에서 α=0.3이 가장 좋았음 → 통계적 확인.

결과: docs/step3_data/alpha_grid_search_results.json
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
ALPHA_VALUES = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]
OCTAVE_WEIGHT = 0.5   # 기본값 고정


# ─── hibari 전처리 ───────────────────────────────────────────────────────────
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

    # Tonnetz 거리 행렬 사전 계산 (모든 α에서 공유)
    m_dist_tonnetz = compute_note_distance_matrix(
        notes_label, metric='tonnetz', octave_weight=OCTAVE_WEIGHT
    )

    return {
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'intra': intra, 'inter': inter, 'oor': oor,
        'N': N, 'T': T,
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
        'm_dist_tonnetz': m_dist_tonnetz,
    }


# ─── 특정 α로 PH → overlap 구축 ─────────────────────────────────────────────
def build_overlap_for_alpha(data, alpha):
    nd = data['notes_dict']; nl = data['notes_label']
    intra = data['intra']; inter = data['inter']; oor = data['oor']
    N = data['N']; T = data['T']; adn_i = data['adn_i']
    m_dist = data['m_dist_tonnetz']

    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, nd, oor, num_notes=N).values

        if alpha >= 1.0 - 1e-9:
            final = freq_dist          # 순수 frequency
        elif alpha <= 1e-9:
            # 순수 tonnetz: normalize only tonnetz
            from musical_metrics import compute_hybrid_distance as _chd
            final = _chd(freq_dist, m_dist, alpha=0.0)
        else:
            final = compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)

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
    return evaluate_generation(
        generated,
        [data['inst1_real'], data['inst2_real']],
        data['notes_label'], name=""
    )


def main():
    print("=" * 60)
    print("  §7.8 Tonnetz Hybrid α grid search")
    print(f"  N={N_REPEATS}, α values={ALPHA_VALUES}")
    print("=" * 60)

    data = setup_hibari()
    print(f"\n전처리 완료: N={data['N']}, T={data['T']}")
    print(f"Tonnetz 거리 행렬 계산 완료 (octave_weight={OCTAVE_WEIGHT})")

    results = {
        'n_repeats': N_REPEATS,
        'octave_weight': OCTAVE_WEIGHT,
        'alpha_values': ALPHA_VALUES,
        'experiments': {},
        'interpretation': {
            'alpha=1.0': 'pure frequency (baseline)',
            'alpha=0.0': 'pure tonnetz',
            'alpha=0.5': 'current paper default',
        }
    }

    for alpha in ALPHA_VALUES:
        print(f"\n[α = {alpha}]")
        t0 = time.time()
        try:
            overlap, cycle_labeled = build_overlap_for_alpha(data, alpha)
        except Exception as e:
            print(f"  PH 실패: {e}")
            results['experiments'][str(alpha)] = {'alpha': alpha, 'error': str(e)}
            continue
        ph_time = time.time() - t0
        n_cyc = len(cycle_labeled)
        print(f"  {n_cyc} cycles, PH {ph_time:.1f}s")

        if n_cyc == 0:
            print("  → cycle 없음, skip")
            results['experiments'][str(alpha)] = {
                'alpha': alpha, 'n_cycles': 0, 'error': 'no cycles'
            }
            continue

        ov = overlap.values
        trials_js = []
        for i in range(N_REPEATS):
            r = run_algo1_once(data, ov, cycle_labeled, seed=6000 + i)
            js = r['js_divergence']
            trials_js.append(js)
            if i % 5 == 0 or i == N_REPEATS - 1:
                print(f"  [{i+1:2d}] JS={js:.4f}  notes={r['n_notes']}")

        js_arr = np.array(trials_js)
        results['experiments'][str(alpha)] = {
            'alpha': alpha,
            'n_cycles': n_cyc,
            'ph_time_s': round(ph_time, 1),
            'js_mean': round(float(js_arr.mean()), 4),
            'js_std':  round(float(js_arr.std(ddof=1)), 4),
            'js_min':  round(float(js_arr.min()), 4),
            'js_max':  round(float(js_arr.max()), 4),
        }
        print(f"  → JS = {js_arr.mean():.4f} ± {js_arr.std(ddof=1):.4f}")

    # 최적 α
    best_alpha = min(
        (k for k, v in results['experiments'].items() if 'js_mean' in v),
        key=lambda k: results['experiments'][k]['js_mean'],
        default=None
    )
    results['best_alpha'] = float(best_alpha) if best_alpha else None

    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/alpha_grid_search_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")

    print("\n[요약]")
    print(f"  {'alpha':>6s}  {'JS mean':>10s}  {'JS std':>8s}  {'K':>4s}")
    print("  " + "─" * 36)
    for alpha_str, r in results['experiments'].items():
        if 'js_mean' not in r:
            continue
        mark = " ★" if str(r['alpha']) == str(best_alpha) else ""
        print(f"  {r['alpha']:>6.1f}  {r['js_mean']:>10.4f}  "
              f"{r['js_std']:>8.4f}  {r['n_cycles']:>4d}{mark}")

    if best_alpha:
        print(f"\n최적 α = {best_alpha}")
        if best_alpha == '0.5':
            print("→ 현재 기본값(0.5)이 최적. 논문 설정 정당화.")
        elif best_alpha == '0.3':
            print("→ α=0.3이 최적. memory의 단일 run 힌트 통계적 확인!")
        else:
            print(f"→ α={best_alpha}이 새로운 최적. 논문 업데이트 필요.")


if __name__ == "__main__":
    main()
