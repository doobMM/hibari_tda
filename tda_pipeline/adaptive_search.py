"""
TDA Music Pipeline - Adaptive Rate Search
============================================
기존의 고정 간격(1e-4) 전수 탐색 대신,
cycle 수가 변하는 구간만 정밀 탐색하는 적응적 방법입니다.

핵심 아이디어:
  - 거친 스캔으로 "어디서 변화가 일어나는지" 먼저 파악
  - 변화 구간만 세밀하게 재탐색
  - 15,000번 → 보통 300~800번으로 줄어듦

사용법:
    python adaptive_search.py

또는 다른 코드에서:
    from adaptive_search import adaptive_homology_search
    profile = adaptive_homology_search(adn_i, notes_dict, ...)
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_distance_matrix, compute_out_of_reach
)
from overlap import group_rBD_by_homology


def _compute_barcode_at_rate(rate: float, intra, inter, notes_dict, 
                              oor, num_notes, dim, generateBarcode):
    """단일 rate에서 barcode를 계산합니다."""
    timeflow_w = intra + rate * inter
    dist = compute_distance_matrix(timeflow_w, notes_dict, oor, num_notes=num_notes)
    bd = generateBarcode(
        mat=dist.values, listOfDimension=[dim],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )
    return bd


def _count_cycles(barcode_result) -> int:
    """barcode 결과에서 cycle 수를 셉니다."""
    if barcode_result is None:
        return 0
    return len(barcode_result)


def _get_cycle_signature(barcode_result) -> frozenset:
    """
    barcode 결과의 '지문'을 만듭니다.
    cycle 수뿐 아니라 birth/death 패턴이 바뀌었는지 감지하기 위해
    각 cycle의 birth 값을 반올림하여 집합으로 만듭니다.
    """
    if barcode_result is None:
        return frozenset()
    
    sig = []
    for entry in barcode_result:
        birth = entry[1][0]
        death = entry[1][1]
        # birth를 소수점 6자리로 반올림하여 지문에 포함
        sig.append((round(float(birth), 6) if birth != 'infty' else 'inf',
                     round(float(death), 6) if death != 'infty' else 'inf'))
    return frozenset(sig)


def adaptive_homology_search(
    chord_seqs: dict,           # adn_i 형식: {1: [...], 2: [...]}
    notes_dict: dict,
    lag: int = 1,
    dimension: int = 1,
    rate_start: float = 0.0,
    rate_end: float = 1.5,
    # 적응적 탐색 파라미터
    coarse_step: float = 0.01,   # 1단계 거친 스캔 간격
    fine_step: float = 0.0001,   # 2단계 정밀 스캔 간격
    margin: float = 0.02,        # 변화 구간 양쪽에 추가할 여백
    num_notes: int = 23,
    verbose: bool = True
) -> Tuple[list, float, dict]:
    """
    적응적 rate 탐색으로 Persistent Homology를 계산합니다.
    
    단계:
    1. coarse_step 간격으로 전체 구간을 스캔하여 cycle 수의 변화 지점을 찾음
    2. 변화 지점 주변만 fine_step 간격으로 정밀 탐색
    3. 결과를 rate 순으로 정렬하여 반환
    
    Args:
        chord_seqs: {1: [seq_full, seq_lag1, ...], 2: [seq_full, seq_lag1, ...]}
        notes_dict: 화음→note 매핑 딕셔너리
        lag: inter-weight lag
        dimension: 호몰로지 차원
        rate_start, rate_end: 탐색 범위
        coarse_step: 1단계 간격 (기본 0.01 → 150 포인트)
        fine_step: 2단계 간격 (기본 0.0001)
        margin: 변화 구간 양쪽 여백 (기본 0.02)
        num_notes: 고유 note 수
        verbose: 진행 상황 출력
    
    Returns:
        (homology_profile, out_of_reach, stats)
        stats: {'total_evaluations': int, 'brute_force_would_be': int, 
                'savings_percent': float, 'transition_zones': list}
    """
    try:
        from professor import generateBarcode
    except ImportError:
        print("⚠ professor.py (generateBarcode)를 찾을 수 없습니다.")
        return [], 0, {}
    
    t_total = time.time()
    
    # ── 가중치 계산 ──
    w1 = compute_intra_weights(chord_seqs[1][0])
    w2 = compute_intra_weights(chord_seqs[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(chord_seqs[1][lag], chord_seqs[2][lag], lag=lag)
    oor = compute_out_of_reach(inter, power=int(np.log10(fine_step)))
    
    eval_count = 0  # 총 barcode 계산 횟수
    
    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: 거친 스캔 (coarse scan)
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        n_coarse = int((rate_end - rate_start) / coarse_step) + 1
        print(f"\n  Phase 1: 거친 스캔 (간격={coarse_step}, ~{n_coarse}개 포인트)")
    
    t1 = time.time()
    coarse_results = {}  # rate → (barcode, cycle_count, signature)
    
    rate = rate_start
    while rate <= rate_end + 1e-10:
        rate_rounded = round(rate, 6)
        bd = _compute_barcode_at_rate(
            rate_rounded, intra, inter, notes_dict, oor, num_notes, dimension, generateBarcode
        )
        n_cycles = _count_cycles(bd)
        sig = _get_cycle_signature(bd)
        coarse_results[rate_rounded] = (bd, n_cycles, sig)
        eval_count += 1
        rate += coarse_step
    
    coarse_rates = sorted(coarse_results.keys())
    dt1 = time.time() - t1
    
    if verbose:
        print(f"    완료: {len(coarse_rates)}개 포인트, {dt1:.1f}s")
        cycle_counts = [coarse_results[r][1] for r in coarse_rates]
        print(f"    cycle 수 범위: {min(cycle_counts)} ~ {max(cycle_counts)}")
    
    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: 변화 구간 탐지
    # ═══════════════════════════════════════════════════════════════════
    transition_zones = []  # (zone_start, zone_end) 리스트
    
    for i in range(len(coarse_rates) - 1):
        r1, r2 = coarse_rates[i], coarse_rates[i + 1]
        _, n1, sig1 = coarse_results[r1]
        _, n2, sig2 = coarse_results[r2]
        
        # cycle 수가 바뀌었거나 signature가 바뀌었으면 → 변화 구간
        if n1 != n2 or sig1 != sig2:
            zone_start = max(rate_start, r1 - margin)
            zone_end = min(rate_end, r2 + margin)
            transition_zones.append((round(zone_start, 6), round(zone_end, 6)))
    
    # 겹치는 구간 병합
    transition_zones = _merge_zones(transition_zones)
    
    if verbose:
        print(f"\n  Phase 2: {len(transition_zones)}개 변화 구간 감지")
        for zs, ze in transition_zones:
            print(f"    [{zs:.4f} ~ {ze:.4f}] (폭: {ze-zs:.4f})")
    
    # ═══════════════════════════════════════════════════════════════════
    # Phase 3: 변화 구간만 정밀 탐색 (fine scan)
    # ═══════════════════════════════════════════════════════════════════
    if verbose:
        total_fine_width = sum(ze - zs for zs, ze in transition_zones)
        n_fine_est = int(total_fine_width / fine_step)
        print(f"\n  Phase 3: 정밀 스캔 (간격={fine_step}, ~{n_fine_est}개 포인트)")
    
    t3 = time.time()
    fine_results = {}
    
    for zone_start, zone_end in transition_zones:
        rate = zone_start
        while rate <= zone_end + 1e-10:
            rate_rounded = round(rate, 6)
            
            # 이미 계산된 포인트는 건너뜀
            if rate_rounded not in coarse_results and rate_rounded not in fine_results:
                bd = _compute_barcode_at_rate(
                    rate_rounded, intra, inter, notes_dict, oor, 
                    num_notes, dimension, generateBarcode
                )
                fine_results[rate_rounded] = bd
                eval_count += 1
            
            rate += fine_step
    
    dt3 = time.time() - t3
    if verbose:
        print(f"    완료: {len(fine_results)}개 추가 포인트, {dt3:.1f}s")
    
    # ═══════════════════════════════════════════════════════════════════
    # 결과 통합
    # ═══════════════════════════════════════════════════════════════════
    all_profile = []
    
    # 거친 스캔 결과
    for rate_val in coarse_rates:
        bd, _, _ = coarse_results[rate_val]
        all_profile.append((rate_val, bd))
    
    # 정밀 스캔 결과
    for rate_val, bd in fine_results.items():
        all_profile.append((rate_val, bd))
    
    # rate 순으로 정렬
    all_profile.sort(key=lambda x: x[0])
    
    # 통계
    brute_force_would_be = int((rate_end - rate_start) / fine_step) + 1
    savings = (1 - eval_count / brute_force_would_be) * 100
    
    dt_total = time.time() - t_total
    
    stats = {
        'total_evaluations': eval_count,
        'brute_force_would_be': brute_force_would_be,
        'savings_percent': savings,
        'transition_zones': transition_zones,
        'time_seconds': dt_total,
        'coarse_points': len(coarse_rates),
        'fine_points': len(fine_results),
    }
    
    if verbose:
        print(f"\n  ── 요약 ──")
        print(f"  총 barcode 계산: {eval_count}회")
        print(f"  전수 탐색 시:    {brute_force_would_be}회")
        print(f"  절감율:          {savings:.1f}%")
        print(f"  총 소요 시간:    {dt_total:.1f}s")
        
        if brute_force_would_be > 0:
            est_brute = dt_total / eval_count * brute_force_would_be
            print(f"  전수 탐색 추정:  {est_brute:.0f}s ({est_brute/60:.1f}분)")
    
    return all_profile, oor, stats


def _merge_zones(zones: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """겹치는 구간을 병합합니다."""
    if not zones:
        return []
    
    zones.sort()
    merged = [zones[0]]
    
    for start, end in zones[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    
    return merged


# ═══════════════════════════════════════════════════════════════════════════
# 비교 실험: 전수 탐색 vs 적응적 탐색의 결과 일치 검증
# ═══════════════════════════════════════════════════════════════════════════

def verify_adaptive_vs_brute(chord_seqs, notes_dict, lag=1, dimension=1,
                              rate_start=0.0, rate_end=0.3,  # 짧은 구간으로 검증
                              num_notes=23):
    """
    짧은 구간에서 전수 탐색과 적응적 탐색의 결과가 동일한지 확인합니다.
    """
    from professor import generateBarcode
    
    print("\n  검증: 적응적 탐색 vs 전수 탐색 (rate 0.0~0.3)")
    
    # 적응적 탐색
    profile_adaptive, oor_a, stats = adaptive_homology_search(
        chord_seqs, notes_dict, lag=lag, dimension=dimension,
        rate_start=rate_start, rate_end=rate_end,
        coarse_step=0.01, fine_step=0.001,  # 검증이므로 좀 거칠게
        num_notes=num_notes, verbose=False
    )
    persistence_adaptive = group_rBD_by_homology(profile_adaptive, dim=dimension)
    
    # 전수 탐색 (0.001 간격)
    w1 = compute_intra_weights(chord_seqs[1][0])
    w2 = compute_intra_weights(chord_seqs[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(chord_seqs[1][lag], chord_seqs[2][lag], lag=lag)
    oor_b = compute_out_of_reach(inter, power=-3)
    
    profile_brute = []
    rate = rate_start
    while rate <= rate_end + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        dist = compute_distance_matrix(tw, notes_dict, oor_b, num_notes=num_notes)
        bd = generateBarcode(mat=dist.values, listOfDimension=[dimension],
                             exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile_brute.append((r, bd))
        rate += 0.001
    
    persistence_brute = group_rBD_by_homology(profile_brute, dim=dimension)
    
    # 비교
    cycles_adaptive = set(persistence_adaptive.keys())
    cycles_brute = set(persistence_brute.keys())
    
    common = cycles_adaptive & cycles_brute
    only_adaptive = cycles_adaptive - cycles_brute
    only_brute = cycles_brute - cycles_adaptive
    
    print(f"    적응적 탐색 발견: {len(cycles_adaptive)}개 사이클")
    print(f"    전수 탐색 발견:   {len(cycles_brute)}개 사이클")
    print(f"    공통:            {len(common)}개")
    
    if only_adaptive:
        print(f"    적응적에만:      {len(only_adaptive)}개 {only_adaptive}")
    if only_brute:
        print(f"    전수에만:        {len(only_brute)}개 {only_brute}")
    
    match = (cycles_adaptive == cycles_brute)
    print(f"    결과 일치: {'✓' if match else '✗'}")
    
    return match


# ═══════════════════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences
    )
    
    print("╔══════════════════════════════════════════════╗")
    print("║  적응적 Homology 탐색 테스트                   ║")
    print("╚══════════════════════════════════════════════╝")
    
    midi_file = "Ryuichi_Sakamoto_-_hibari.mid"
    if not os.path.exists(midi_file):
        print(f"⚠ '{midi_file}'을 찾을 수 없습니다.")
        sys.exit(1)
    
    # 전처리
    print("\n전처리 중...")
    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]
    
    module_notes = inst1_real[:59]
    notes_label, notes_counts = build_note_labels(module_notes)
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
    print(f"  notes: {num_notes}종")
    
    # ── 적응적 탐색 실행 ──
    print("\n" + "=" * 60)
    print("적응적 탐색 (lag=1, dim=1, rate 0.0~1.5)")
    print("=" * 60)
    
    profile, oor, stats = adaptive_homology_search(
        adn_i, notes_dict,
        lag=1, dimension=1,
        rate_start=0.0, rate_end=1.5,
        coarse_step=0.01,    # Phase 1: 150개 포인트
        fine_step=0.0001,    # Phase 3: 변화 구간만 정밀
        margin=0.02,         # 변화 구간 양쪽 2% 여백
        num_notes=num_notes,
        verbose=True
    )
    
    # 결과 확인
    persistence = group_rBD_by_homology(profile, dim=1)
    print(f"\n  발견된 사이클: {len(persistence)}개")
    
    # 기존 pickle과 비교
    pkl_path = "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl"
    if os.path.exists(pkl_path):
        import pandas as pd
        df = pd.read_pickle(pkl_path)
        old_persistence = {}
        for _, row in df.iterrows():
            old_persistence.setdefault(row['cycle'], []).append(
                (row['rate'], row['birth'], row['death'])
            )
        
        old_cycles = set(old_persistence.keys())
        new_cycles = set(persistence.keys())
        
        print(f"\n  ── 기존 결과(pkl)와 비교 ──")
        print(f"  기존 pkl:    {len(old_cycles)}개 사이클")
        print(f"  적응적 탐색: {len(new_cycles)}개 사이클")
        print(f"  공통:        {len(old_cycles & new_cycles)}개")
        
        only_old = old_cycles - new_cycles
        only_new = new_cycles - old_cycles
        if only_old:
            print(f"  pkl에만:     {len(only_old)}개")
        if only_new:
            print(f"  새로만:      {len(only_new)}개")
    
    print("\n완료!")
