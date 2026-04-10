"""
temporal_reorder.py — 중첩행렬 시간 재배치 (방향 B)

cycle(열)은 고정하고 시간(행)을 재배치하여,
같은 위상 구조에서 다른 선율 경로를 생성한다.

3가지 전략:
  1. segment_shuffle  — 동일 활성 패턴 연속 구간을 셔플
  2. block_permute    — 고정 길이 블록 단위 셔플
  3. markov_resample  — 행 전이확률 학습 → 새 시퀀스 리샘플링
"""
import numpy as np
from typing import Tuple, Dict, Any, Optional


def reorder_overlap_matrix(overlap: np.ndarray,
                           strategy: str = 'segment_shuffle',
                           seed: int = 42,
                           **kwargs) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    중첩행렬의 시간축을 재배치한다.

    Args:
        overlap: (T, C) numpy 배열 (이진 또는 연속값)
        strategy: 'segment_shuffle' | 'block_permute' | 'markov_resample'
        seed: 랜덤 시드
        **kwargs: 전략별 추가 파라미터

    Returns:
        reordered: (T, C) 재배치된 행렬
        info: 전략 정보 및 통계
    """
    rng = np.random.RandomState(seed)

    if strategy == 'segment_shuffle':
        return _segment_shuffle(overlap, rng, **kwargs)
    elif strategy == 'block_permute':
        return _block_permute(overlap, rng, **kwargs)
    elif strategy == 'markov_resample':
        return _markov_resample(overlap, rng, **kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# ── 1. Segment Shuffle ─────────────────────────────────────────────────

def _segment_shuffle(overlap: np.ndarray, rng: np.random.RandomState,
                     min_segment_len: int = 1
                     ) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    동일한 활성화 패턴이 연속되는 구간(segment)을 식별하고,
    segment 단위로 순서를 셔플한다.

    예: [A,A,A,B,B,C,C,C,C] → [C,C,C,C,A,A,A,B,B]
    각 segment 내부 순서는 보존되므로 국소적 연결성 유지.
    """
    T, C = overlap.shape

    # 각 행을 tuple로 변환하여 패턴 비교
    segments = []  # [(start, end, pattern_tuple), ...]
    current_pattern = tuple(overlap[0])
    seg_start = 0

    for t in range(1, T):
        pattern = tuple(overlap[t])
        if pattern != current_pattern:
            segments.append((seg_start, t, current_pattern))
            current_pattern = pattern
            seg_start = t
    segments.append((seg_start, T, current_pattern))

    # 최소 길이 필터
    small = []
    if min_segment_len > 1:
        filtered = [s for s in segments if (s[1] - s[0]) >= min_segment_len]
        small = [s for s in segments if (s[1] - s[0]) < min_segment_len]
        # 짧은 segment는 가장 가까운 filtered segment에 병합
        segments = filtered if filtered else segments

    # 셔플
    order = list(range(len(segments)))
    rng.shuffle(order)

    # 재조립
    reordered = np.empty_like(overlap)
    pos = 0
    mapping = {}  # new_t → old_t

    for new_idx in order:
        start, end, _ = segments[new_idx]
        seg_len = end - start
        reordered[pos:pos + seg_len] = overlap[start:end]
        for offset in range(seg_len):
            mapping[pos + offset] = start + offset
        pos += seg_len

    # pos < T인 경우 (small segments 제외 시) 나머지 채움
    if pos < T:
        for s_start, s_end, _ in small:
            seg_len = s_end - s_start
            reordered[pos:pos + seg_len] = overlap[s_start:s_end]
            for offset in range(seg_len):
                mapping[pos + offset] = s_start + offset
            pos += seg_len

    info = {
        'strategy': 'segment_shuffle',
        'n_segments': len(segments),
        'avg_segment_len': np.mean([s[1] - s[0] for s in segments]),
        'shuffle_order': order,
    }
    return reordered, info


# ── 2. Block Permute ───────────────────────────────────────────────────

def _block_permute(overlap: np.ndarray, rng: np.random.RandomState,
                   block_size: int = 32
                   ) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    고정 길이 블록(예: 32 timestep = 4마디) 단위로 셔플.
    블록 내부 순서는 보존.

    block_size=32 → 8분음표 기준 4마디 (32 × 0.5beat = 16beat = 4bar)
    """
    T, C = overlap.shape
    n_blocks = T // block_size
    remainder = T % block_size

    # 블록 인덱스 셔플
    order = list(range(n_blocks))
    rng.shuffle(order)

    reordered = np.empty_like(overlap)
    pos = 0

    for new_idx in order:
        start = new_idx * block_size
        reordered[pos:pos + block_size] = overlap[start:start + block_size]
        pos += block_size

    # 나머지 (마지막 불완전 블록) 그대로 붙임
    if remainder > 0:
        reordered[pos:] = overlap[n_blocks * block_size:]

    info = {
        'strategy': 'block_permute',
        'block_size': block_size,
        'n_blocks': n_blocks,
        'remainder': remainder,
        'shuffle_order': order,
    }
    return reordered, info


# ── 3. Markov Resample ─────────────────────────────────────────────────

def _markov_resample(overlap: np.ndarray, rng: np.random.RandomState,
                     temperature: float = 1.0
                     ) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    원본 중첩행렬의 행 전이확률(1차 Markov)을 학습한 뒤,
    같은 길이의 새로운 시퀀스를 리샘플링한다.

    temperature: 1.0 = 원본 전이확률 그대로
                 >1.0 = 더 랜덤 (탐험적)
                 <1.0 = 더 결정론적 (원본에 가까움)
    """
    T, C = overlap.shape

    # 각 행을 고유 패턴으로 인코딩
    row_tuples = [tuple(overlap[t]) for t in range(T)]
    unique_patterns = list(set(row_tuples))
    pattern_to_idx = {p: i for i, p in enumerate(unique_patterns)}
    n_states = len(unique_patterns)

    # 상태 시퀀스
    state_seq = [pattern_to_idx[p] for p in row_tuples]

    # 전이 행렬 구축
    trans = np.zeros((n_states, n_states))
    for t in range(T - 1):
        trans[state_seq[t], state_seq[t + 1]] += 1

    # 정규화 (smoothing)
    trans += 1e-6
    row_sums = trans.sum(axis=1, keepdims=True)
    trans = trans / row_sums

    # temperature 적용
    if temperature != 1.0:
        log_trans = np.log(trans + 1e-12) / temperature
        log_trans -= log_trans.max(axis=1, keepdims=True)
        trans = np.exp(log_trans)
        trans = trans / trans.sum(axis=1, keepdims=True)

    # 리샘플링 — 시작 상태는 원본과 동일
    new_state_seq = [state_seq[0]]
    for t in range(1, T):
        current = new_state_seq[-1]
        probs = trans[current]
        next_state = rng.choice(n_states, p=probs)
        new_state_seq.append(next_state)

    # 상태 → 행 복원
    reordered = np.array([unique_patterns[s] for s in new_state_seq])

    # 통계: 원본과 리샘플의 상태 분포 비교
    from collections import Counter
    orig_dist = Counter(state_seq)
    new_dist = Counter(new_state_seq)

    info = {
        'strategy': 'markov_resample',
        'n_unique_patterns': n_states,
        'temperature': temperature,
        'orig_state_dist': dict(orig_dist),
        'new_state_dist': dict(new_dist),
    }
    return reordered, info
