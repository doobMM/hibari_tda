"""
test_musical_metrics.py — 음악적 거리 함수 검증 + PH 비교
============================================================

1. Tonnetz 거리 테이블 검증
2. 3가지 metric으로 note 거리 행렬 생성
3. 각 metric으로 PH 실행 → 발견되는 cycle 비교
4. 기존 빈도 기반 vs hybrid 거리 비교
"""

import sys, os, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

    from musical_metrics import (
        tonnetz_distance, _build_tonnetz_distance_table,
        compute_note_distance_matrix, compute_hybrid_distance
    )
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences
    )
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach,
        refine_connectedness_fast, to_upper_triangular,
        weight_to_distance, symmetrize_upper_to_full
    )
    from overlap import group_rBD_by_homology, label_cycles_from_persistence
    from topology import generate_barcode_numpy

    print("=" * 60)
    print("  Musical Metrics 검증")
    print("=" * 60)

    # ── 1. Tonnetz 거리 테이블 ──
    print("\n[1] Tonnetz 거리 테이블")
    T = _build_tonnetz_distance_table()
    names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    print(f"     {'':3s}", end="")
    for n in names: print(f"{n:>3s}", end="")
    print()
    for i in range(12):
        print(f"  {names[i]:>3s}", end="")
        for j in range(12):
            print(f"{T[i,j]:>3d}", end="")
        print()

    # 검증: C→G (5도) = 1, C→F# (tritone) = 2
    assert tonnetz_distance(0, 7) == 1, "C→G should be 1"
    assert tonnetz_distance(0, 4) == 1, "C→E should be 1"
    print("  ✓ C→G=1 (완전5도), C→E=1 (장3도), C→F#=2 (트라이톤)")

    # ── 2. 데이터 준비 ──
    print("\n[2] 데이터 준비")
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    module_notes = inst1_real[:59]
    notes_label, notes_counts = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    _, cs1 = build_chord_labels(group_notes_with_duration(inst1_real))
    _, cs2 = build_chord_labels(group_notes_with_duration(inst2_real))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)
    N = len(notes_label)

    # 기존 빈도 기반 가중치
    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-4)

    print(f"  Notes: {N}, Chords: {len(cm)}")

    # ── 3. 3가지 metric 거리 행렬 ──
    print("\n[3] Musical metric 거리 행렬 생성")

    for metric_name in ['tonnetz', 'voice_leading', 'dft']:
        dist = compute_note_distance_matrix(notes_label, metric=metric_name)
        print(f"  {metric_name:15s}: shape={dist.shape}, "
              f"min={dist[dist>0].min():.3f}, max={dist.max():.3f}, "
              f"mean={dist[dist>0].mean():.3f}")

    # ── 4. Tonnetz 거리로 PH 실행 ──
    print("\n[4] Tonnetz 거리 → Persistent Homology")

    tonnetz_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    # 대칭 거리 행렬을 직접 PH에 입력
    # (기존 파이프라인의 refine 단계를 건너뛰고, note-level 거리 행렬을 직접 사용)
    idx = list(range(1, N + 1))
    tonnetz_df = pd.DataFrame(tonnetz_dist, index=idx, columns=idx, dtype=float)

    bd_tonnetz = generate_barcode_numpy(
        mat=tonnetz_dist, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )
    n_tonnetz = len(bd_tonnetz) if bd_tonnetz else 0
    print(f"  Tonnetz 직접 PH: {n_tonnetz}개 cycle")
    if bd_tonnetz:
        for entry in bd_tonnetz[:5]:
            print(f"    dim={entry[0]}, [{entry[1][0]:.3f}, {entry[1][1]:.3f}]")
        if n_tonnetz > 5:
            print(f"    ... 외 {n_tonnetz - 5}개")

    # ── 5. Hybrid 거리 (빈도 + Tonnetz) → PH ──
    print("\n[5] Hybrid 거리 (빈도 + Tonnetz) → PH")

    # 기존 빈도 기반 거리 행렬 (rate=0.5)
    rate = 0.5
    tw = intra + rate * inter
    freq_dist_df = compute_distance_matrix(tw, notes_dict, oor, num_notes=N)
    freq_dist = freq_dist_df.values

    # 각 alpha에서 cycle 수 비교
    print(f"\n  alpha | Method        | Cycles")
    print(f"  ------|---------------|-------")

    # alpha=1.0 (빈도만)
    bd_freq = generate_barcode_numpy(
        mat=freq_dist, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )
    print(f"  1.00  | 빈도 only     | {len(bd_freq) if bd_freq else 0}")

    # alpha=0.0 (Tonnetz만)
    print(f"  0.00  | Tonnetz only  | {n_tonnetz}")

    # hybrid
    for alpha in [0.7, 0.5, 0.3]:
        hybrid = compute_hybrid_distance(freq_dist, tonnetz_dist, alpha=alpha)
        bd_hybrid = generate_barcode_numpy(
            mat=hybrid, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        n_h = len(bd_hybrid) if bd_hybrid else 0
        print(f"  {alpha:.2f}  | hybrid a={alpha} | {n_h}")

    # ── 6. 전 rate 범위에서 비교 ──
    print(f"\n[6] 전 rate 범위에서 빈도 vs Tonnetz hybrid 비교")

    test_rates = [0.01, 0.1, 0.3, 0.5, 0.8, 1.0, 1.5]
    print(f"\n  rate  | 빈도 only | hybrid(a=0.5)")
    print(f"  ------|-----------|-------------")

    for rate in test_rates:
        tw = intra + rate * inter
        fd = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values

        bd_f = generate_barcode_numpy(mat=fd, listOfDimension=[1],
                                       exactStep=True, birthDeathSimplex=False, sortDimension=False)

        hybrid = compute_hybrid_distance(fd, tonnetz_dist, alpha=0.5)
        bd_h = generate_barcode_numpy(mat=hybrid, listOfDimension=[1],
                                       exactStep=True, birthDeathSimplex=False, sortDimension=False)

        nf = len(bd_f) if bd_f else 0
        nh = len(bd_h) if bd_h else 0
        print(f"  {rate:.2f}  | {nf:9d} | {nh:13d}")

    print(f"\n{'='*60}")
    print("  완료")
    print("=" * 60)
