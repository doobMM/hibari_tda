"""
test_cycle_selector.py — cycle_selector 검증
===============================================

실제 48-cycle 데이터로 greedy selection을 실행하고:
1. Preservation curve (K vs score)
2. 고정 크기 K=5,10,15,20 결과
3. 임계값 기반 자동 선택
4. 개별 cycle 순위
"""

import sys, os, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build_overlap_from_pipeline():
    """파이프라인을 실행하여 overlap matrix + cycle_labeled를 구합니다."""
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences
    )
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach
    )
    from overlap import (
        label_cycles_from_persistence, group_rBD_by_homology,
        build_activation_matrix, build_overlap_matrix
    )
    from preprocessing import simul_chord_lists, simul_union_by_dict
    from topology import generate_barcode_ripser, _check_ripser

    midi_file = os.path.join(os.path.dirname(__file__),
                             "Ryuichi_Sakamoto_-_hibari.mid")

    # 전처리
    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    module_notes = inst1_real[:59]
    notes_label, _ = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, cs1 = build_chord_labels(active1)
    _, cs2 = build_chord_labels(active2)
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    num_notes = len(notes_label)

    # 가중치
    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-4)

    # ripser로 전 rate 범위 탐색 (coarse)
    barcode_fn = None
    if _check_ripser():
        from topology import generate_barcode_ripser as barcode_fn_r
        barcode_fn = barcode_fn_r
        print("  ripser 사용")
    else:
        from professor import generateBarcode
        barcode_fn = lambda mat, **kw: generateBarcode(
            mat=mat, listOfDimension=kw.get('listOfDimension', [1]),
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        print("  professor.py 사용 (ripser 미설치)")

    # 전 rate 탐색 (pkl에서 로드 가능하면 사용)
    pkl_path = os.path.join(os.path.dirname(__file__),
                            "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    if os.path.exists(pkl_path):
        print("  pkl에서 persistence 로드")
        import re
        df = pd.read_pickle(pkl_path)
        persistence = {}
        for _, row in df.iterrows():
            cycle_key = row['cycle']
            persistence.setdefault(cycle_key, []).append(
                (row['rate'], row['birth'], row['death'])
            )
    else:
        print("  rate 탐색 중 (시간 소요)...")
        profile = []
        step = 10 ** -4
        rate = 0.0
        while rate <= 1.5 + 1e-10:
            r = round(rate, 4)
            tw = intra + r * inter
            dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=num_notes)
            bd = barcode_fn(mat=dist.values, listOfDimension=[1],
                            annotate=True, birthDeathSimplex=False, sortDimension=False)
            profile.append((r, bd))
            rate += step
        persistence = group_rBD_by_homology(profile, dim=1)

    cycle_labeled = label_cycles_from_persistence(persistence)

    # Note-time 행렬
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    nodes_list = list(range(1, num_notes + 1))
    T = 1088
    note_time_data = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    col_idx = nodes_list.index(n)
                    note_time_data[t, col_idx] = 1
    note_time_df = pd.DataFrame(note_time_data, columns=nodes_list)

    # Activation + Overlap
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled,
                                   threshold=0.35, total_length=T)

    return overlap, cycle_labeled, notes_dict


if __name__ == "__main__":
    print("=" * 60)
    print("  Cycle Subset Selector 검증")
    print("=" * 60)

    print("\n전처리 중...")
    t0 = time.time()
    overlap_df, cycle_labeled, notes_dict = build_overlap_from_pipeline()
    print(f"  완료 ({time.time()-t0:.1f}s)")
    print(f"  Overlap matrix: {overlap_df.shape} (T={overlap_df.shape[0]}, C={overlap_df.shape[1]})")

    overlap_mat = overlap_df.values

    from cycle_selector import CycleSubsetSelector

    selector = CycleSubsetSelector(overlap_mat, cycle_labeled)

    # ── 1. 개별 cycle 순위 ──
    print("\n" + "=" * 60)
    print("개별 Cycle 순위 (단독 보존도)")
    print("=" * 60)
    ranks = selector.rank_cycles()
    for rank, (c_idx, score) in enumerate(ranks[:10]):
        cycle = list(cycle_labeled.items())[c_idx][1]
        print(f"  {rank+1:2d}. cycle {c_idx:2d} {str(cycle):30s} score={score:.4f}")
    print(f"  ... (하위 {len(ranks)-10}개 생략)")

    # ── 2. 고정 크기 K ──
    for k in [5, 10, 15, 20]:
        print(f"\n{'='*60}")
        print(f"Greedy Selection: K={k}")
        print("=" * 60)
        result = selector.select_fixed_size(k, verbose=True)
        print(f"\n  최종 score: {result.final_score:.4f}")
        print(f"  선택된 cycle: {result.selected_indices}")

    # ── 3. 임계값 기반 ──
    print(f"\n{'='*60}")
    print(f"임계값 기반 선택 (target=0.90)")
    print("=" * 60)
    result_t = selector.select_by_threshold(target=0.90, verbose=True)
    print(f"\n  필요 cycle 수: {len(result_t.selected_indices)}")
    print(f"  최종 score: {result_t.final_score:.4f}")

    # ── 4. Preservation Curve (전체 48 cycle) ──
    print(f"\n{'='*60}")
    print(f"전체 Preservation Curve (48 cycles)")
    print("=" * 60)
    result_full = selector.select_fixed_size(len(cycle_labeled), verbose=False)

    print(f"\n  K | Composite | Jaccard | Corr   | Betti")
    print(f"  --|-----------|---------|--------|------")
    milestones = [1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 35, 40, 45, 48]
    for k in milestones:
        if k <= len(result_full.preservation_curve):
            idx = k - 1
            j = result_full.component_curves['jaccard'][idx]
            c = result_full.component_curves['correlation'][idx]
            b = result_full.component_curves['betti'][idx]
            s = result_full.preservation_curve[idx]
            print(f"  {k:2d} | {s:.4f}    | {j:.4f}  | {c:.4f} | {b:.4f}")

    # 90% 도달 지점 찾기
    for i, s in enumerate(result_full.preservation_curve):
        if s >= 0.90:
            print(f"\n  90% 보존도 도달: K={i+1} (score={s:.4f})")
            break

    print(f"\n{'='*60}")
    print("완료")
    print("=" * 60)
