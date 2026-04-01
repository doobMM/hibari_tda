"""
TDA Music Pipeline - Weight & Distance Computation (핵심 최적화)
================================================================
가중치 행렬 → 거리 행렬 변환을 담당합니다.

주요 최적화:
1. refine_connectedness: numpy 벡터화 연산으로 4중 루프 제거
   - 기존: O(17² × max_notes_per_chord²) Python 루프
   - 개선: 사전 계산된 매핑 행렬을 이용한 행렬 연산
2. get_UTMconnected: numpy 삼각 행렬 연산으로 대체
3. 거리 행렬 변환: numpy 마스크 연산으로 일괄 처리
"""

import numpy as np
import pandas as pd
from typing import Dict, Set, Optional, Tuple


# ─── Intra/Inter Weight 계산 ───────────────────────────────────────────────

def compute_intra_weights(chord_seq: list, num_chords: int = 17, lag: int = 1) -> pd.DataFrame:
    """
    같은 악기 내 인접 화음 전이 빈도를 계산합니다.
    
    최적화: numpy 배열 인덱싱으로 루프 최소화
    """
    weights = np.zeros((num_chords, num_chords), dtype=int)
    n = len(chord_seq)
    
    for i in range(n - lag):
        a, b = chord_seq[i], chord_seq[i + lag]
        if a is not None and b is not None and a != b:
            weights[a, b] += 1
    
    return pd.DataFrame(weights)


def compute_inter_weights(seq_a: list, seq_b: list, 
                          num_chords: int = 17, lag: int = 1) -> pd.DataFrame:
    """
    두 악기 간 시차(lag)를 둔 화음 전이 빈도를 계산합니다.
    """
    weights = np.zeros((num_chords, num_chords), dtype=int)
    n = len(seq_a) - lag
    
    for i in range(n):
        # a[i] → b[i+lag]
        if seq_b[i + lag] is None:
            # 기존 코드: b[i+lag]가 None이면 두 번째 업데이트도 건너뜀
            continue
        weights[seq_a[i], seq_b[i + lag]] += 1

        # b[i] → a[i+lag] (양방향) - b[i+lag]가 유효할 때만 실행
        if seq_b[i] is not None:
            weights[seq_b[i], seq_a[i + lag]] += 1
    
    return pd.DataFrame(weights)


# ─── 핵심 최적화: Refine Connectedness ─────────────────────────────────────

def _build_expansion_matrix(notes_dict: dict, num_notes: int) -> np.ndarray:
    """
    화음→note 매핑을 위한 확장 행렬을 사전 계산합니다.
    
    expansion[chord_label, note_label] = 1 if note_label ∈ chord
    
    이 행렬을 한 번만 계산하면 refine_connectedness를 
    행렬 연산으로 수행할 수 있습니다.
    """
    num_chords = max(k for k in notes_dict.keys() if isinstance(k, int)) + 1
    expansion = np.zeros((num_chords, num_notes), dtype=float)
    
    for chord_lbl, note_set in notes_dict.items():
        if not isinstance(chord_lbl, int):
            continue
        for note_lbl in note_set:
            expansion[chord_lbl, note_lbl - 1] = 1.0  # note labels are 1-indexed
    
    return expansion


def refine_connectedness_fast(weight_matrix: pd.DataFrame,
                              notes_dict: dict,
                              num_notes: int = 23,
                              rounding_digits: int = 4) -> pd.DataFrame:
    """
    화음 단위의 가중치를 note 단위로 분해합니다. (벡터화 버전)

    원리:
    - W[i,j] (화음 i→j 가중치)를 화음 i에 속한 모든 note와
      화음 j에 속한 모든 note 쌍에 분배
    - E = expansion matrix, W = weight matrix (상삼각)
    - refined = E^T @ W_upper @ E (상삼각 부분만 취함)

    rounding_digits: 부동소수점 오차 방지용 반올림 자릿수 (기존 코드의 round(v, -power))
    """
    W = weight_matrix.values.astype(float)

    # 상삼각으로 변환 (대각선 제외)
    W_upper = np.triu(W, k=0) + np.triu(W.T, k=1)
    np.fill_diagonal(W_upper, np.diag(W))
    # 하삼각 → 상삼각으로 옮기기
    for i in range(W.shape[0]):
        for j in range(i):
            W_upper[j, i] += W[i, j]
    W_upper = np.triu(W_upper)

    # 확장 행렬
    E = _build_expansion_matrix(notes_dict, num_notes)

    # 행렬 곱으로 refine: R = E^T @ W_upper @ E
    refined = E.T @ W_upper @ E

    # 부동소수점 오차 보정 (기존 코드와 일치)
    if rounding_digits is not None:
        refined = np.round(refined, rounding_digits)

    # 상삼각만 유지
    refined = np.triu(refined)

    # DataFrame으로 변환 (1-indexed note labels)
    idx = list(range(1, num_notes + 1))
    return pd.DataFrame(refined, index=idx, columns=idx, dtype=float)


def refine_connectedness_precise(weight_matrix: pd.DataFrame,
                                  notes_dict: dict,
                                  num_notes: int = 23,
                                  rounding_digits: int = 2) -> pd.DataFrame:
    """
    부동소수점 정밀도가 중요한 경우 사용하는 정밀 버전.
    별도의 반올림 자릿수를 지정할 수 있습니다.
    """
    result = refine_connectedness_fast(weight_matrix, notes_dict, num_notes, rounding_digits=rounding_digits)
    # 부동소수점 오차 보정 (이미 fast에서 처리됨)
    result = result.round(rounding_digits)
    return result


# ─── 거리 행렬 변환 ────────────────────────────────────────────────────────

def weight_to_distance(weight_df: pd.DataFrame, 
                       out_of_reach: float) -> pd.DataFrame:
    """
    가중치 행렬을 거리 행렬로 변환합니다. (역수 변환)
    
    최적화: numpy 마스크 연산으로 일괄 처리
    """
    W = weight_df.values.astype(float)
    D = np.full_like(W, out_of_reach, dtype=float)
    
    nonzero = W != 0
    D[nonzero] = 1.0 / W[nonzero]
    
    return pd.DataFrame(D, index=weight_df.index, columns=weight_df.columns)


def symmetrize_upper_to_full(upper_df: pd.DataFrame) -> pd.DataFrame:
    """상삼각 행렬을 대칭 행렬로 변환합니다."""
    M = upper_df.values.copy()
    # 하삼각을 0으로 만든 후 대칭화 (weight_to_distance 후 하삼각이 out_of_reach일 수 있음)
    M = np.triu(M)
    M = M + M.T - np.diag(np.diag(M))
    return pd.DataFrame(M, index=upper_df.index, columns=upper_df.columns)


def to_upper_triangular(df: pd.DataFrame) -> pd.DataFrame:
    """하삼각 요소를 상삼각으로 옮기고 하삼각을 0으로 만듭니다."""
    M = df.values.astype(float)
    result = np.triu(M) + np.triu(M.T, k=1)
    return pd.DataFrame(result, index=df.index, columns=df.columns)


# ─── 통합 거리 계산 함수 ───────────────────────────────────────────────────

def compute_distance_matrix(weight_matrix: pd.DataFrame,
                            notes_dict: dict,
                            out_of_reach: float,
                            num_notes: int = 23,
                            refine: bool = True) -> pd.DataFrame:
    """
    가중치 행렬로부터 최종 거리 행렬을 계산합니다.
    기존 is_distance_matrix_from의 최적화 + 통합 버전.
    
    파이프라인: 
    1. 상삼각 변환 
    2. note 단위 refine (선택) 
    3. 역수 변환 
    4. 대칭화
    """
    # 1. 상삼각
    W_upper = to_upper_triangular(weight_matrix)
    
    # 2. Refine
    if refine:
        W_refined = refine_connectedness_fast(W_upper, notes_dict, num_notes)
    else:
        W_refined = W_upper
    
    # 3. 역수 변환
    D_upper = weight_to_distance(W_refined, out_of_reach)
    
    # 4. 대칭화
    D_full = symmetrize_upper_to_full(D_upper)
    
    return D_full


def compute_out_of_reach(weight_df: pd.DataFrame, power: int = -2) -> float:
    """out_of_reach 값을 계산합니다."""
    step = 10 ** power
    min_nonzero = weight_df.values[weight_df.values != 0].min()
    return 1 + 2 / (min_nonzero * step)


# ─── Simul 가중치 (동시 발음) ──────────────────────────────────────────────

def compute_simul_weights(inst1_seq: list, inst2_seq: list, 
                          notes_dict: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    동시 발음 기반 intra/inter 가중치를 계산합니다.
    
    최적화: specify_chord_list를 인라인화하고 한 번의 순회로 처리
    """
    # note label 집합 추출
    all_labels = set()
    for k, v in notes_dict.items():
        if isinstance(k, int):
            all_labels |= v
    
    labels_sorted = sorted(all_labels)
    n = len(labels_sorted)
    label_to_idx = {lbl: i for i, lbl in enumerate(labels_sorted)}
    
    intra = np.zeros((n, n), dtype=int)
    inter = np.zeros((n, n), dtype=int)
    
    for t in range(len(inst1_seq)):
        c1, c2 = inst1_seq[t], inst2_seq[t]
        
        set1 = notes_dict.get(c1) if c1 is not None else None
        set2 = notes_dict.get(c2) if c2 is not None else None
        
        # Intra: 각 inst 내 조합 (union - intersection)
        for s in [s for s in (set1, set2) if s is not None]:
            sl = sorted(s)
            for i_idx in range(len(sl)):
                for j_idx in range(i_idx, len(sl)):
                    ni, nj = label_to_idx[sl[i_idx]], label_to_idx[sl[j_idx]]
                    intra[ni, nj] += 1
        
        # 교집합 보정 (중복 카운트 제거)
        if set1 is not None and set2 is not None:
            intersect = sorted(set1 & set2)
            for i_idx in range(len(intersect)):
                for j_idx in range(i_idx, len(intersect)):
                    ni, nj = label_to_idx[intersect[i_idx]], label_to_idx[intersect[j_idx]]
                    intra[ni, nj] -= 1
            
            # Inter: 차집합 간 bipartite 연결
            diff1 = set1 - set2
            diff2 = set2 - set1
            for d1 in diff1:
                for d2 in diff2:
                    ni, nj = label_to_idx[d1], label_to_idx[d2]
                    inter[ni, nj] += 1
    
    intra_df = pd.DataFrame(intra, index=labels_sorted, columns=labels_sorted)
    inter_df = pd.DataFrame(inter, index=labels_sorted, columns=labels_sorted)
    
    return intra_df, inter_df
