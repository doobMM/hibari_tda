import json
import os
import random
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from eval_metrics import evaluate_generation
from generation import NodePool, CycleSetManager, algorithm1_optimized
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
from overlap import (
    build_activation_matrix,
    build_overlap_matrix,
    group_rBD_by_homology,
    label_cycles_from_persistence,
)
from preprocessing import (
    build_chord_labels,
    build_note_labels,
    chord_to_note_labels,
    group_notes_with_duration,
    load_and_quantize,
    prepare_lag_sequences,
    simul_chord_lists,
    simul_union_by_dict,
    split_instruments,
)
from topology import generate_barcode_numpy
from weights import (
    compute_distance_matrix,
    compute_inter_weights,
    compute_inter_weights_decayed,
    compute_intra_weights,
    compute_out_of_reach,
)


SEEDS = list(range(1000, 1020))  # N=20
MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
           4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
TOTAL_LENGTH = 1088
ALPHA_BY_METRIC = {"dft": 0.5, "tonnetz": 0.5}


def setup_hibari():
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adjusted, _, boundaries = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

    notes_label, notes_counts = build_note_labels(inst1_real[:59])
    module_active = group_notes_with_duration(inst1_real[:59])
    chord_map_module, _ = build_chord_labels(module_active)
    notes_dict = chord_to_note_labels(chord_map_module, notes_label)
    notes_dict["name"] = "notes"

    _, chord_seq1 = build_chord_labels(group_notes_with_duration(inst1_real))
    _, chord_seq2 = build_chord_labels(group_notes_with_duration(inst2_real))
    adn_i = prepare_lag_sequences(chord_seq1, chord_seq2, solo_timepoints=32, max_lag=4)

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])

    return {
        "notes_label": notes_label,
        "notes_counts": notes_counts,
        "notes_dict": notes_dict,
        "adn_i": adn_i,
        "intra": w1 + w2,
        "num_notes": len(notes_label),
        "num_chords": len(chord_map_module),
        "inst1_real": inst1_real,
        "inst2_real": inst2_real,
    }


def build_overlap_for_condition(data, metric, use_decayed):
    if use_decayed:
        inter = compute_inter_weights_decayed(
            data["adn_i"], max_lag=4, num_chords=data["num_chords"]
        )
    else:
        inter = compute_inter_weights(
            data["adn_i"][1][1], data["adn_i"][2][1],
            num_chords=data["num_chords"], lag=1
        )

    oor = compute_out_of_reach(inter, power=-2)
    musical_dist = compute_note_distance_matrix(data["notes_label"], metric=metric)
    alpha = ALPHA_BY_METRIC[metric]

    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        timeflow_w = data["intra"] + r * inter
        freq_dist = compute_distance_matrix(
            timeflow_w, data["notes_dict"], oor, num_notes=data["num_notes"]
        ).values
        final_dist = compute_hybrid_distance(freq_dist, musical_dist, alpha=alpha)
        bd = generate_barcode_numpy(
            mat=final_dist, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)

    chord_pairs = simul_chord_lists(data["adn_i"][1][-1], data["adn_i"][2][-1])
    note_sets = simul_union_by_dict(chord_pairs, data["notes_dict"])
    nodes_list = list(range(1, data["num_notes"] + 1))
    node_to_idx = {node: idx for idx, node in enumerate(nodes_list)}
    note_time = np.zeros((TOTAL_LENGTH, len(nodes_list)), dtype=int)

    for t in range(min(TOTAL_LENGTH, len(note_sets))):
        if note_sets[t] is None:
            continue
        for node in note_sets[t]:
            idx = node_to_idx.get(node)
            if idx is not None:
                note_time[t, idx] = 1

    note_time_df = pd.DataFrame(note_time, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(
        activation, cycle_labeled, threshold=0.35, total_length=TOTAL_LENGTH
    )
    return overlap, cycle_labeled


def run_once(data, overlap_values, cycle_labeled, seed):
    random.seed(seed)
    np.random.seed(seed)

    pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    generated = algorithm1_optimized(
        pool, MODULES * 33, overlap_values, manager, max_resample=50, verbose=False
    )
    result = evaluate_generation(
        generated,
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"],
        name="",
    )
    return result["js_divergence"]


def main():
    t0 = time.time()
    data = setup_hibari()
    results = {}

    for metric in ["dft", "tonnetz"]:
        for label, decayed in [("lag1_only", False), ("lag1to4_decayed", True)]:
            key = f"{metric}_{label}"
            print(f"  실행 중: {key} ...", flush=True)
            overlap, cycle_labeled = build_overlap_for_condition(data, metric, decayed)
            overlap_values = overlap.values if hasattr(overlap, "values") else overlap
            vals = [run_once(data, overlap_values, cycle_labeled, seed) for seed in SEEDS]
            results[key] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=1)),
                "n": len(vals),
                "n_cycles": len(cycle_labeled),
            }
            print(
                f"    JS = {results[key]['mean']:.4f} ± {results[key]['std']:.4f}"
                f"  (K={results[key]['n_cycles']})"
            )

    with open("docs/step3_data/decayed_lag_dft_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("완료: docs/step3_data/decayed_lag_dft_results.json")
    print(f"총 소요 시간: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
