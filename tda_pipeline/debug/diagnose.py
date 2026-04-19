"""
TDA Music Pipeline - 진단 스크립트
====================================
기존 코드(WK14)와 새 코드의 중간 결과를 단계별로 비교하여
0 cycle 문제의 원인을 찾습니다.

사용법:
    python diagnose.py

필요: 같은 디렉토리에 professor.py, process.py(또는 상위 폴더에), 
      Ryuichi_Sakamoto_-_hibari.mid, pickle/ 폴더
"""

import sys, os
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# 기존 코드 경로
OLD_DIR = None
for candidate in [PARENT_DIR, os.path.join(PARENT_DIR, 'WK14'), SCRIPT_DIR]:
    if os.path.exists(os.path.join(candidate, 'process.py')):
        OLD_DIR = candidate
        break


def compare_arrays(name, old_val, new_val, tolerance=1e-6):
    """두 값을 비교하고 차이를 출력합니다."""
    if isinstance(old_val, pd.DataFrame):
        old_val = old_val.values
    if isinstance(new_val, pd.DataFrame):
        new_val = new_val.values
    
    if isinstance(old_val, np.ndarray) and isinstance(new_val, np.ndarray):
        if old_val.shape != new_val.shape:
            print(f"  ✗ {name}: 크기 다름! old={old_val.shape}, new={new_val.shape}")
            return False
        
        diff = np.abs(old_val.astype(float) - new_val.astype(float))
        max_diff = diff.max()
        n_diff = (diff > tolerance).sum()
        
        if max_diff <= tolerance:
            print(f"  ✓ {name}: 동일 (max diff={max_diff:.2e})")
            return True
        else:
            print(f"  ✗ {name}: 다름! max_diff={max_diff:.4f}, 다른 원소 수={n_diff}/{diff.size}")
            # 가장 큰 차이가 나는 위치 출력
            idx = np.unravel_index(diff.argmax(), diff.shape)
            print(f"    최대 차이 위치: {idx}, old={old_val[idx]:.4f}, new={new_val[idx]:.4f}")
            return False
    
    elif isinstance(old_val, list) and isinstance(new_val, list):
        if len(old_val) != len(new_val):
            print(f"  ✗ {name}: 길이 다름! old={len(old_val)}, new={len(new_val)}")
            # 처음 다른 위치 찾기
            for i in range(min(len(old_val), len(new_val))):
                if old_val[i] != new_val[i]:
                    print(f"    처음 다른 위치: index {i}, old={old_val[i]}, new={new_val[i]}")
                    break
            return False
        
        mismatches = [(i, old_val[i], new_val[i]) for i in range(len(old_val)) if old_val[i] != new_val[i]]
        if not mismatches:
            print(f"  ✓ {name}: 동일 (길이={len(old_val)})")
            return True
        else:
            print(f"  ✗ {name}: {len(mismatches)}개 차이 (총 {len(old_val)}개)")
            for i, ov, nv in mismatches[:5]:
                print(f"    index {i}: old={ov}, new={nv}")
            if len(mismatches) > 5:
                print(f"    ... 외 {len(mismatches)-5}개")
            return False
    else:
        match = (old_val == new_val)
        sym = "✓" if match else "✗"
        print(f"  {sym} {name}: old={old_val}, new={new_val}")
        return match


def run_diagnosis():
    midi_file = os.path.join(SCRIPT_DIR, "Ryuichi_Sakamoto_-_hibari.mid")
    if not os.path.exists(midi_file):
        print("⚠ MIDI 파일을 찾을 수 없습니다.")
        return
    
    if not OLD_DIR:
        print("⚠ 기존 코드(process.py)를 찾을 수 없습니다.")
        print(f"  탐색 경로: {PARENT_DIR}, {SCRIPT_DIR}")
        return
    
    print(f"기존 코드 위치: {OLD_DIR}")
    print()
    
    # ═════════════════════════════════════════════════════════
    # 1. 기존 코드 실행
    # ═════════════════════════════════════════════════════════
    print("=" * 60)
    print("STEP A: 기존 코드(WK14) 중간 결과 수집")
    print("=" * 60)
    
    sys.path.insert(0, OLD_DIR)
    from process import (adjust_to_eighth_note, label_active_chord_by_onset,
                         get_ready_with_lags, group_notes_with_duration_,
                         notes_label_n_counts, chord_label_dict,
                         chord_label_to_note_labels)
    from util import (get_chords_intra_connected, get_chords_inter_connected,
                      is_distance_matrix_from, get_outta_reach,
                      refine_connectedness, get_UTMconnected)
    
    # 전처리
    old_adjusted, old_tempo = adjust_to_eighth_note(midi_file)
    adn_1 = old_adjusted[:2006]
    adn_2 = old_adjusted[2006:]
    adn_1_real = adn_1[:-59]
    adn_2_real = adn_2[59:]
    
    adn_1_chord = label_active_chord_by_onset(adn_1_real)
    adn_2_chord = label_active_chord_by_onset(adn_2_real)
    adn_i_old = get_ready_with_lags(adn_1_chord, adn_2_chord)
    
    module_notes_old = adn_1_real[:59]
    active_module_old = group_notes_with_duration_(module_notes_old)
    notes_label_old, notes_counts_old = notes_label_n_counts(module_notes_old)
    chord_label_old = chord_label_dict(active_module_old)
    notes_dict_old = chord_label_to_note_labels(chord_label_old, notes_label_old)
    notes_dict_old['name'] = 'notes'
    
    # 가중치 행렬
    old_w1 = get_chords_intra_connected(adn_i_old[1][0])
    old_w2 = get_chords_intra_connected(adn_i_old[2][0])
    old_intra = old_w1 + old_w2
    old_inter = get_chords_inter_connected(adn_i_old[1][1], adn_i_old[2][1], lag=1)
    old_oor = get_outta_reach(old_inter, power=-4)
    
    # rate=0.0001에서의 거리 행렬
    old_timeflow = old_intra + 0.0001 * old_inter
    old_dist = is_distance_matrix_from(old_timeflow, notes_dict_old, out_of_reach=old_oor, power=-4)
    
    print(f"\n  화음 시퀀스 길이: inst1={len(adn_i_old[1][0])}, inst2={len(adn_i_old[2][0])}")
    print(f"  고유 화음 수: {len(chord_label_old)}")
    print(f"  notes_label 수: {len(notes_label_old)}")
    print(f"  out_of_reach: {old_oor:.4f}")
    print(f"  intra 합계: {old_intra.values.sum()}")
    print(f"  inter 합계: {old_inter.values.sum()}")
    print(f"  거리 행렬 크기: {old_dist.shape}")
    print(f"  거리 행렬 min(non-diag): {old_dist.values[~np.eye(old_dist.shape[0], dtype=bool)].min():.6f}")
    print(f"  거리 행렬 max: {old_dist.values.max():.6f}")
    
    # notes_dict 내용 출력
    print(f"\n  notes_dict 키(정수만):")
    for k in sorted(k for k in notes_dict_old.keys() if isinstance(k, int)):
        print(f"    chord {k} → notes {notes_dict_old[k]}")
    
    sys.path.remove(OLD_DIR)
    
    # ═════════════════════════════════════════════════════════
    # 2. 새 코드 실행
    # ═════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP B: 새 코드 중간 결과 수집")
    print("=" * 60)
    
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
    
    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]
    
    # 화음 시퀀스
    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    cm1, cs1 = build_chord_labels(active1)
    cm2, cs2 = build_chord_labels(active2)
    
    # note 레이블
    module_notes = inst1_real[:59]
    notes_label_new, notes_counts_new = build_note_labels(module_notes)
    active_module = group_notes_with_duration(module_notes)
    cm_module, _ = build_chord_labels(active_module)
    notes_dict_new = chord_to_note_labels(cm_module, notes_label_new)
    notes_dict_new['name'] = 'notes'
    
    # lag 시퀀스
    adn_i_new = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)
    
    # 가중치 행렬
    new_w1 = compute_intra_weights(adn_i_new[1][0])
    new_w2 = compute_intra_weights(adn_i_new[2][0])
    new_intra = new_w1 + new_w2
    new_inter = compute_inter_weights(adn_i_new[1][1], adn_i_new[2][1], lag=1)
    new_oor = compute_out_of_reach(new_inter, power=-4)
    
    # rate=0.0001에서의 거리 행렬
    new_timeflow = new_intra + 0.0001 * new_inter
    new_dist = compute_distance_matrix(new_timeflow, notes_dict_new, new_oor, num_notes=23)
    
    print(f"\n  화음 시퀀스 길이: inst1={len(adn_i_new[1][0])}, inst2={len(adn_i_new[2][0])}")
    print(f"  고유 화음(모듈): {len(cm_module)}, 고유 화음(inst1 전체): {len(cm1)}, 고유 화음(inst2 전체): {len(cm2)}")
    print(f"  notes_label 수: {len(notes_label_new)}")
    print(f"  out_of_reach: {new_oor:.4f}")
    print(f"  intra 합계: {new_intra.values.sum()}")
    print(f"  inter 합계: {new_inter.values.sum()}")
    print(f"  거리 행렬 크기: {new_dist.shape}")
    print(f"  거리 행렬 min(non-diag): {new_dist.values[~np.eye(new_dist.shape[0], dtype=bool)].min():.6f}")
    print(f"  거리 행렬 max: {new_dist.values.max():.6f}")
    
    print(f"\n  notes_dict 키(정수만):")
    for k in sorted(k for k in notes_dict_new.keys() if isinstance(k, int)):
        print(f"    chord {k} → notes {notes_dict_new[k]}")
    
    # ═════════════════════════════════════════════════════════
    # 3. 단계별 비교
    # ═════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP C: 단계별 비교")
    print("=" * 60)
    
    # 3-1. notes_label 비교
    print("\n[1] notes_label 비교:")
    compare_arrays("notes_label", 
                   sorted(notes_label_old.items()), 
                   sorted(notes_label_new.items()))
    
    # 3-2. notes_dict 비교 (정수 키만)
    print("\n[2] notes_dict 비교:")
    old_int_keys = sorted(k for k in notes_dict_old if isinstance(k, int))
    new_int_keys = sorted(k for k in notes_dict_new if isinstance(k, int))
    compare_arrays("정수 키", old_int_keys, new_int_keys)
    
    all_match = True
    for k in old_int_keys:
        if k in notes_dict_new:
            if notes_dict_old[k] != notes_dict_new[k]:
                print(f"  ✗ chord {k}: old={notes_dict_old[k]}, new={notes_dict_new[k]}")
                all_match = False
        else:
            print(f"  ✗ chord {k}: 새 코드에 없음")
            all_match = False
    if all_match:
        print(f"  ✓ 모든 chord→notes 매핑 일치")
    
    # 3-3. 화음 시퀀스 비교
    print("\n[3] 화음 시퀀스 비교:")
    old_cs1 = adn_i_old[1][0]  # inst1 full
    old_cs2 = adn_i_old[2][0]  # inst2 full (with None prepended)
    new_cs1 = adn_i_new[1][0]
    new_cs2 = adn_i_new[2][0]
    compare_arrays("inst1 full chord seq", old_cs1, new_cs1)
    compare_arrays("inst2 full chord seq", old_cs2, new_cs2)
    
    # 3-3b. lag=1 시퀀스 비교
    print("\n[3b] lag=1 시퀀스 비교:")
    compare_arrays("inst1 lag1", adn_i_old[1][1], adn_i_new[1][1])
    compare_arrays("inst2 lag1", adn_i_old[2][1], adn_i_new[2][1])
    
    # 3-4. 가중치 행렬 비교
    print("\n[4] 가중치 행렬 비교:")
    compare_arrays("intra_weights (w1)", old_w1, new_w1)
    compare_arrays("intra_weights (w2)", old_w2, new_w2)
    compare_arrays("intra_weights (합)", old_intra, new_intra)
    compare_arrays("inter_weights", old_inter, new_inter)
    compare_arrays("out_of_reach", old_oor, new_oor)
    
    # 3-5. timeflow weight 비교
    print("\n[5] timeflow weight (rate=0.0001) 비교:")
    compare_arrays("timeflow_weight", old_timeflow, new_timeflow)
    
    # 3-6. refine 후 비교 (수동으로 단계별)
    print("\n[6] refine 단계별 비교:")
    
    # 기존: UTM → refine → distance → symmetrize
    old_utm = get_UTMconnected(old_timeflow.copy())
    print(f"  old UTM shape: {old_utm.shape}, sum: {old_utm.values.sum():.2f}")
    
    new_utm = to_upper_triangular(new_timeflow.copy())
    print(f"  new UTM shape: {new_utm.shape}, sum: {new_utm.values.sum():.2f}")
    
    compare_arrays("upper triangular", old_utm, new_utm)
    
    # refine 비교
    old_refined = refine_connectedness(old_utm.copy(), notes_dict_old, power=-4)
    new_refined = refine_connectedness_fast(new_utm.copy(), notes_dict_new, num_notes=23)
    
    print(f"\n  old refined shape: {old_refined.shape}, sum: {old_refined.values.sum():.2f}")
    print(f"  new refined shape: {new_refined.shape}, sum: {new_refined.values.sum():.2f}")
    print(f"  old refined nonzero: {(old_refined.values != 0).sum()}")
    print(f"  new refined nonzero: {(new_refined.values != 0).sum()}")
    
    # 인덱스 체계가 다를 수 있으므로 값만 비교
    if old_refined.shape == new_refined.shape:
        compare_arrays("refined matrix (값)", old_refined.values, new_refined.values)
    else:
        print(f"  ✗ refined 크기 다름: old={old_refined.shape}, new={new_refined.shape}")
    
    # 3-7. 최종 거리 행렬 비교
    print("\n[7] 최종 거리 행렬 비교:")
    if old_dist.shape == new_dist.shape:
        compare_arrays("distance matrix", old_dist.values, new_dist.values)
    else:
        print(f"  ✗ 거리 행렬 크기 다름: old={old_dist.shape}, new={new_dist.shape}")
    
    # 3-8. generateBarcode 비교
    print("\n[8] generateBarcode 비교 (rate=0.0001):")
    try:
        from professor import generateBarcode
        
        old_bd = generateBarcode(mat=old_dist.values, listOfDimension=[1],
                                  exactStep=True, birthDeathSimplex=False, sortDimension=False)
        new_bd = generateBarcode(mat=new_dist.values, listOfDimension=[1],
                                  exactStep=True, birthDeathSimplex=False, sortDimension=False)
        
        print(f"  기존 거리 행렬 → {len(old_bd) if old_bd else 0}개 cycle")
        print(f"  새 거리 행렬  → {len(new_bd) if new_bd else 0}개 cycle")
        
        # 기존 거리 행렬에 새 코드의 generateBarcode를 적용
        cross_bd = generateBarcode(mat=old_dist.values, listOfDimension=[1],
                                    exactStep=True, birthDeathSimplex=False, sortDimension=False)
        print(f"  (검증) 기존 거리에 generateBarcode → {len(cross_bd) if cross_bd else 0}개 cycle")
        
    except Exception as e:
        print(f"  generateBarcode 실행 실패: {e}")
    
    print("\n" + "=" * 60)
    print("진단 완료")
    print("=" * 60)


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════╗")
    print("║  TDA Music Pipeline - 진단                    ║")
    print("║  기존 vs 새 코드 중간 결과 단계별 비교          ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    run_diagnosis()
