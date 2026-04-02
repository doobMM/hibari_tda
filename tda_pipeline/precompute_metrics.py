"""
precompute_metrics.py — 4개 metric별 PH 결과를 사전 계산하여 pkl로 저장
===========================================================================

대시보드에서 metric 변경 시 즉시 사용할 수 있도록 캐싱합니다.
한 번만 실행하면 됩니다.
"""

import sys, os, time, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
from musical_metrics import (
    compute_note_distance_matrix, compute_hybrid_distance
)


def build_overlap_for_metric(metric_name, alpha, intra, inter, oor,
                              notes_dict, notes_label, adn_i, N, T):
    """단일 metric으로 PH → overlap matrix를 구축합니다."""

    if metric_name == 'frequency':
        m_dist = None
    else:
        m_dist = compute_note_distance_matrix(notes_label, metric=metric_name)

    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values

        if m_dist is not None:
            final = compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)
        else:
            final = freq_dist

        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)

    # Overlap matrix
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled, threshold=0.35, total_length=T)

    return overlap, cycle_labeled


if __name__ == "__main__":
    print("=" * 60)
    print("  Metric별 PH 사전 계산")
    print("=" * 60)

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
    oor = compute_out_of_reach(inter, power=-2)

    metrics = [
        ('frequency', 1.0),
        ('tonnetz', 0.5),
        ('voice_leading', 0.5),
        ('dft', 0.5),
    ]

    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    os.makedirs(cache_dir, exist_ok=True)

    for name, alpha in metrics:
        print(f"\n  [{name}] (alpha={alpha}) ...", end=" ", flush=True)
        t0 = time.time()

        overlap, cycle_labeled = build_overlap_for_metric(
            name, alpha, intra, inter, oor,
            notes_dict, notes_label, adn_i, N, T
        )

        dt = time.time() - t0
        pkl_path = os.path.join(cache_dir, f"metric_{name}.pkl")
        with open(pkl_path, 'wb') as f:
            pickle.dump({
                'overlap': overlap,
                'cycle_labeled': cycle_labeled,
                'metric': name,
                'alpha': alpha,
            }, f)

        print(f"{len(cycle_labeled)} cycles, {overlap.shape}, {dt:.1f}s → {pkl_path}")

    print(f"\n완료! cache/ 폴더에 4개 pkl 저장됨.")
