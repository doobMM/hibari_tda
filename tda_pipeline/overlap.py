"""
TDA Music Pipeline - Overlap Matrix (최적화)
=============================================
사이클 레이블링, 스케일 조정, 중첩행렬 구축을 담당합니다.

주요 최적화:
1. get_scattered_cycles_df: numpy boolean 연산으로 DataFrame 순회 제거
2. filter_consecutive_indices: numpy diff 기반 O(N) 처리
3. construct_overlap_df: numpy 배열 직접 조작 (DataFrame 루프 제거)
"""

import numpy as np
import pandas as pd
from collections import Counter
from typing import Dict, List, Tuple, Optional, Set, Union
import re


# ─── 사이클 레이블링 ───────────────────────────────────────────────────────

def label_cycles_from_persistence(cycle_persistence: dict) -> dict:
    """
    persistence 데이터에서 사이클을 정렬하여 레이블링합니다.
    기존 get_cycle_labeled_asc + label_cycle의 통합 버전.
    dim=1(tuple)과 dim=2(frozenset) 키가 혼재할 수 있으므로
    문자열 변환 후 정렬합니다.
    """
    sorted_keys = sorted(cycle_persistence.keys(), key=lambda c: str(c))
    return {i: cycle for i, cycle in enumerate(sorted_keys)}


def get_cycle_stats(cycle_labeled: dict, notes_dict: dict) -> Tuple[list, list, set]:
    """사이클 통계를 한 번의 순회로 계산합니다."""
    length_counter = Counter()
    vertex_counter = Counter()
    
    for cycle in cycle_labeled.values():
        length_counter[len(cycle)] += 1
        vertex_counter.update(cycle)
    
    # 어떤 사이클에도 포함되지 않은 note 찾기
    all_notes = set()
    for k, v in notes_dict.items():
        if isinstance(k, int):
            all_notes |= v
    
    in_cycle = {v + 1 for v in vertex_counter.keys()}  # 0-indexed → 1-indexed
    not_in_cycle = all_notes - in_cycle
    
    return (length_counter.most_common(), 
            [(k + 1, c) for k, c in vertex_counter.most_common()],
            not_in_cycle)


# ─── 중첩행렬 구축 (핵심 최적화) ──────────────────────────────────────────

def build_activation_matrix(df: pd.DataFrame,
                            cycle_labeled: Union[dict, list],
                            continuous: bool = False) -> pd.DataFrame:
    """
    원곡의 note-time 행렬에서 각 사이클의 시점별 활성화를 계산합니다.

    continuous=False (기존): 이진 0/1. 하나라도 활성화되면 1.
    continuous=True (신규): 연속값 0~1.
      활성 note 비율에 희귀도 가중치를 적용:
      - 많은 cycle에 등장하는 흔한 note → 낮은 가중치
      - 적은 cycle에만 등장하는 희귀 note → 높은 가중치
      효과: 색채음 같은 희귀 note가 활성화되면 overlap 값이 더 높아짐
    """
    df_values = df.values  # (T, N_notes) numpy array
    columns = list(df.columns)

    if isinstance(cycle_labeled, dict):
        items = list(cycle_labeled.items())
    else:
        items = list(enumerate(cycle_labeled))

    n_cycles = len(items)
    n_times = df_values.shape[0]
    dtype = float if continuous else int
    activation = np.zeros((n_times, n_cycles), dtype=dtype)

    col_to_idx = {col: i for i, col in enumerate(columns)}

    # 희귀도 계산: note_rarity[col_idx] = 1 / (해당 note가 등장하는 cycle 수)
    note_rarity = {}
    if continuous:
        from collections import Counter
        note_cycle_count = Counter()
        for _, (label, cycle) in enumerate(items):
            verts = set()
            if isinstance(cycle, frozenset):
                for s in cycle:
                    verts.update(s) if isinstance(s, tuple) else verts.add(s)
            else:
                verts = set(cycle)
            for v in verts:
                if (v + 1) in col_to_idx:
                    note_cycle_count[col_to_idx[v + 1]] += 1
        # rarity = 1/count (등장 cycle이 적을수록 높은 가중치)
        for col_idx, count in note_cycle_count.items():
            note_rarity[col_idx] = 1.0 / count
    
    for c_idx, (label, cycle) in enumerate(items):
        # cycle의 vertex 추출 (dim=1: tuple of ints, dim=2: frozenset of tuples)
        if isinstance(cycle, frozenset):
            # dim=2: frozenset of (v1, v2, v3) → 모든 vertex 합집합
            vertices = set()
            for simplex in cycle:
                if isinstance(simplex, tuple):
                    vertices.update(simplex)
                else:
                    vertices.add(simplex)
        else:
            vertices = cycle
        note_indices = [col_to_idx[v + 1] for v in vertices if (v + 1) in col_to_idx]
        
        if note_indices:
            sub = df_values[:, note_indices]
            if continuous:
                # 연속값 모드: 활성 note 비율 + 희귀 note 가중치
                # note_rarity[n] = 1 / (해당 note가 등장하는 cycle 수)
                # 희귀 note가 활성화되면 기여도가 높음
                weights = np.array([note_rarity.get(ni, 1.0)
                                    for ni in note_indices])
                weighted_active = (sub > 0).astype(float) * weights[np.newaxis, :]
                activation[:, c_idx] = weighted_active.sum(axis=1) / weights.sum()
            else:
                # 이진 모드 (기존): 하나라도 활성화되면 1
                activation[:, c_idx] = np.any(sub > 0, axis=1).astype(int)

    result = pd.DataFrame(activation, columns=[item[0] for item in items])
    return result


# ─── 스케일 조정 (최적화) ──────────────────────────────────────────────────

def find_consecutive_runs(binary_series: np.ndarray, 
                          min_length: int) -> List[List[int]]:
    """
    이진 배열에서 min_length 이상 연속된 1의 구간을 찾습니다.
    
    최적화: numpy diff 기반 O(N) 처리
    - 기존: 인덱스를 하나씩 비교하며 순회
    - 개선: diff로 연속 구간의 시작/끝을 한 번에 찾음
    """
    if binary_series.sum() == 0:
        return []
    
    # 패딩 추가하여 경계 처리
    padded = np.concatenate(([0], binary_series, [0]))
    diff = np.diff(padded)
    
    starts = np.where(diff == 1)[0]   # 1이 시작되는 위치
    ends = np.where(diff == -1)[0]    # 1이 끝나는 위치
    
    runs = []
    for s, e in zip(starts, ends):
        length = e - s
        if length >= min_length:
            runs.append(list(range(s, e)))
    
    return runs


def compute_scale_for_cycle(activation_col: np.ndarray,
                            initial_scale: int,
                            threshold: float,
                            lower_bound: float) -> Tuple[List[list], int, float]:
    """
    단일 사이클에 대해 최적 scale을 탐색합니다.
    기존 get_cycle_scaled의 최적화 버전.
    """
    total = len(activation_col)
    # activation이 1인 인덱스만 추출
    ones_idx = np.where(activation_col == 1)[0]
    
    if len(ones_idx) == 0:
        return [], initial_scale, 0.0
    
    scale = initial_scale
    
    while True:
        runs = find_consecutive_runs(activation_col, scale)
        on_length = sum(len(r) for r in runs)
        reduction = on_length / total
        
        if reduction <= lower_bound:
            # scale을 하나 줄여서 재계산
            scale = max(scale - 1, 1)
            runs = find_consecutive_runs(activation_col, scale)
            on_length = sum(len(r) for r in runs)
            reduction = on_length / total
            break
        elif reduction <= threshold:
            break
        
        scale += 1
    
    return runs, scale, reduction


def build_overlap_matrix(activation_df: pd.DataFrame,
                         cycle_labeled: Union[dict, list],
                         threshold: float,
                         lower_bound: Optional[float] = None,
                         total_length: int = 1088) -> pd.DataFrame:
    """
    활성화 행렬에서 스케일 조정을 적용하여 중첩행렬을 구축합니다.
    기존 evaluate_threshold + construct_overlap_df의 통합 최적화 버전.
    
    최적화: numpy 배열 직접 조작 (DataFrame 순회 제거)
    """
    if lower_bound is None:
        lower_bound = max(0.0, threshold - 0.1)
    
    if isinstance(cycle_labeled, dict):
        items = list(cycle_labeled.items())
    else:
        items = list(enumerate(cycle_labeled))
    
    n_cycles = len(items)
    overlap = np.zeros((total_length, n_cycles), dtype=int)
    
    for c_idx, (label, cycle) in enumerate(items):
        col = activation_df[label].values
        initial_scale = len(cycle)
        
        runs, _, _ = compute_scale_for_cycle(
            col, initial_scale, threshold, lower_bound
        )
        
        for run in runs:
            indices = np.array(run)
            indices = indices[indices < total_length]
            overlap[indices, c_idx] = 1
    
    columns = [item[0] for item in items]
    return pd.DataFrame(overlap, columns=columns)


# ─── rBD 그룹화 (최적화) ──────────────────────────────────────────────────

def group_rBD_by_homology(homology_profile: list, dim: int = 1) -> dict:
    """
    호몰로지 프로필을 사이클/void별로 그룹화합니다.
    기존 get_rBD_groupedBy_homol의 정리 버전.
    """
    persistence = {}
    
    for rate_data in homology_profile:
        rate = rate_data[0]
        cycles_list = rate_data[1]
        
        for cycle_info in cycles_list:
            birth = cycle_info[1][0]
            death = cycle_info[1][1]
            
            if len(cycle_info) < 3:
                continue
            edges_str = cycle_info[2].strip()
            
            # 부호 정규화
            if not re.match(r'^[+-]', edges_str):
                edges_str = '+ ' + edges_str
            
            if dim == 1:
                key = _parse_cycle_1d(edges_str)
            elif dim == 2:
                key = _parse_cycle_2d(edges_str)
            else:
                continue
            
            if key is not None:
                persistence.setdefault(key, []).append((rate, birth, death))
    
    return persistence


def _parse_cycle_1d(edges_str: str) -> Optional[tuple]:
    """1차 호몰로지 (cycle) 파싱.

    numpy 버전: " - (5, 19) + (9, 18) + ..." (부호 + edge)
    ripser 버전: "(5, 9) + (5, 16) + ..." (부호 없을 수 있음, 중복 가능)
    둘 다 처리합니다.
    """
    edges = re.findall(r'([+-])?\s*\(\s*(\d+)\s*,\s*(\d+)\)', edges_str)
    if not edges:
        return None

    edge_list = []
    for sign, v1, v2 in edges:
        a, b = int(v1), int(v2)
        if sign == '-':
            edge_list.append((b, a))
        else:
            edge_list.append((a, b))

    # 중복 edge 제거 (ripser BFS에서 발생 가능)
    seen = set()
    unique_edges = []
    for e in edge_list:
        normalized = (min(e), max(e))
        if normalized not in seen:
            seen.add(normalized)
            unique_edges.append(e)
    edge_list = unique_edges

    if not edge_list:
        return None

    # edge가 1개뿐이면 cycle이 아님 → vertex set으로 fallback
    if len(edge_list) == 1:
        return tuple(sorted(set(edge_list[0])))

    # 연결 순서대로 vertex 나열
    cycle_repr = []
    start_tuple = min(edge_list)
    cycle_repr.append(start_tuple[0])
    cycle_repr.append(start_tuple[1])
    remaining = [e for e in edge_list if e != start_tuple]

    while remaining:
        last = cycle_repr[-1]
        found = False
        for e in remaining:
            # 양방향 연결 허용 (ripser BFS는 방향이 다를 수 있음)
            if e[0] == last and e[1] not in cycle_repr:
                cycle_repr.append(e[1])
                remaining.remove(e)
                found = True
                break
            elif e[1] == last and e[0] not in cycle_repr:
                cycle_repr.append(e[0])
                remaining.remove(e)
                found = True
                break
        if not found:
            # 연결이 안 되면 vertex set으로 fallback
            all_verts = set()
            for e in edge_list:
                all_verts.update(e)
            return tuple(sorted(all_verts))

    if cycle_repr and cycle_repr[0] == cycle_repr[-1]:
        cycle_repr.pop()

    return tuple(cycle_repr)


def _parse_cycle_2d(edges_str: str) -> Optional[frozenset]:
    """2차 호몰로지 (void) 파싱"""
    edges = re.findall(r'([+-])\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', edges_str)
    if not edges:
        return None
    
    simplices = set()
    for sign, v1, v2, v3 in edges:
        v1, v2, v3 = int(v1), int(v2), int(v3)
        if sign == '+':
            simplices.add((v1, v2, v3))
        else:
            simplices.add((v3, v2, v1))
    
    return frozenset(simplices)


# ─── 교집합 분석 ───────────────────────────────────────────────────────────

def find_common_across_lags(persistence_by_lag: Dict[int, dict], dim: int = 1):
    """
    lag 1~4에서 공통으로 발견되는 호몰로지를 찾습니다.
    기존 catch_intersection의 간결화 버전.
    """
    sets = {lag: set(p.keys()) for lag, p in persistence_by_lag.items()}
    lags = sorted(sets.keys())
    
    # 모든 lag의 교집합
    common = sets[lags[0]]
    for lag in lags[1:]:
        common &= sets[lag]
    
    # 모든 lag의 합집합
    union = set()
    for s in sets.values():
        union |= s
    
    return {
        'common': common,
        'union': union,
        'per_lag': sets,
        'counts': {lag: len(s) for lag, s in sets.items()}
    }
