"""
musical_metrics.py — 음악적 거리 함수 플러그인 시스템
=====================================================

기존 파이프라인의 빈도 역수 거리 외에
음악 이론 기반 거리를 플러그인 방식으로 제공합니다.

사용 가능한 거리:
  1. 'frequency'  — 기존 (빈도 역수, 1/weight)
  2. 'tonnetz'    — Tonnetz 격자 위 최단 경로 거리
  3. 'voice_leading' — 두 note 간 최소 음 이동량
  4. 'dft'        — Discrete Fourier Transform 거리

사용법:
  from musical_metrics import get_metric, compute_note_distance_matrix
  dist = compute_note_distance_matrix(notes_label, metric='tonnetz')
"""

import numpy as np
from typing import Dict, Tuple, Optional


# ═══════════════════════════════════════════════════════════════════════════
# 1. Tonnetz 거리
# ═══════════════════════════════════════════════════════════════════════════
#
# Tonnetz는 pitch class를 장3도(+4)와 완전5도(+7) 관계로 배열한 2D 격자.
# 두 pitch class 사이의 Tonnetz 거리 = 격자 위 최단 경로 길이.
#
# 좌표 체계:
#   pitch class p를 Tonnetz 좌표 (x, y)로 변환:
#     x축 = 장3도 이동 (4 semitones)
#     y축 = 완전5도 이동 (7 semitones)
#     p ≡ 4x + 7y (mod 12)
#
#   이 좌표에서의 거리 = |Δx| + |Δy| (Manhattan distance on Tonnetz)

# 미리 계산된 12개 pitch class 간 Tonnetz 거리 (BFS로 계산)
_TONNETZ_DIST = None


def _build_tonnetz_distance_table() -> np.ndarray:
    """
    12개 pitch class 간의 Tonnetz 최단 거리 테이블을 BFS로 구축합니다.

    Tonnetz 이웃 관계:
      - 장3도: ±4 semitones
      - 단3도: ±3 semitones (장3도의 보완)
      - 완전5도: ±7 semitones

    이 3가지 이동으로 연결된 격자에서 BFS → 최단 거리.
    """
    from collections import deque

    # Tonnetz 이웃: 장3도(±4), 단3도(±3), 완전5도(±7)
    neighbors = [3, -3, 4, -4, 7, -7]

    dist = np.full((12, 12), 99, dtype=int)
    np.fill_diagonal(dist, 0)

    for src in range(12):
        visited = {src}
        queue = deque([(src, 0)])
        while queue:
            node, d = queue.popleft()
            for step in neighbors:
                nxt = (node + step) % 12
                if nxt not in visited:
                    visited.add(nxt)
                    dist[src, nxt] = d + 1
                    queue.append((nxt, d + 1))

    return dist


def tonnetz_distance(pc1: int, pc2: int) -> int:
    """두 pitch class (0~11) 간의 Tonnetz 거리."""
    global _TONNETZ_DIST
    if _TONNETZ_DIST is None:
        _TONNETZ_DIST = _build_tonnetz_distance_table()
    return int(_TONNETZ_DIST[pc1 % 12, pc2 % 12])


def tonnetz_note_distance(note1: Tuple[int, int], note2: Tuple[int, int],
                          octave_weight: float = 0.5,
                          duration_weight: float = 0.3) -> float:
    """
    두 note = (pitch, duration) 간의 Tonnetz 기반 거리.

    Tonnetz는 pitch class(mod 12)만 고려하므로,
    옥타브 차이와 duration 차이를 추가 항으로 반영합니다.

    d(n1, n2) = tonnetz(pc1, pc2)
              + octave_weight * |octave1 - octave2|
              + duration_weight * |dur1 - dur2| / max_dur

    Args:
        note1, note2: (pitch, duration) 튜플
        octave_weight: 옥타브 차이 가중치
        duration_weight: duration 차이 가중치
    """
    p1, d1 = note1
    p2, d2 = note2

    # Tonnetz 거리 (pitch class)
    t_dist = tonnetz_distance(p1 % 12, p2 % 12)

    # 옥타브 차이
    oct_diff = abs(p1 // 12 - p2 // 12)

    # Duration 차이 (정규화)
    max_dur = max(d1, d2, 1)
    dur_diff = abs(d1 - d2) / max_dur

    return t_dist + octave_weight * oct_diff + duration_weight * dur_diff


# ═══════════════════════════════════════════════════════════════════════════
# 2. Voice-leading 거리
# ═══════════════════════════════════════════════════════════════════════════

def voice_leading_note_distance(note1: Tuple[int, int], note2: Tuple[int, int],
                                duration_weight: float = 0.3) -> float:
    """
    두 note 간의 voice-leading 거리.

    단일 음에 대해서는 pitch 차이(semitones)가 voice-leading 거리.
    duration 차이도 가중하여 반영.

    d(n1, n2) = |pitch1 - pitch2| + duration_weight * |dur1 - dur2| / max_dur
    """
    p1, d1 = note1
    p2, d2 = note2

    pitch_dist = abs(p1 - p2)
    max_dur = max(d1, d2, 1)
    dur_diff = abs(d1 - d2) / max_dur

    return pitch_dist + duration_weight * dur_diff


# ═══════════════════════════════════════════════════════════════════════════
# 3. DFT (Discrete Fourier Transform) 거리
# ═══════════════════════════════════════════════════════════════════════════

def pitch_class_dft(pc: int) -> np.ndarray:
    """
    단일 pitch class를 12차원 indicator로 변환 후 DFT.

    Returns:
        6개의 Fourier 계수 크기 (|f̂(1)|, ..., |f̂(6)|)
    """
    indicator = np.zeros(12)
    indicator[pc % 12] = 1.0
    fft = np.fft.fft(indicator)
    # 대칭이므로 1~6번 계수만 (0번은 총합 = 1)
    return np.abs(fft[1:7])


def dft_note_distance(note1: Tuple[int, int], note2: Tuple[int, int],
                      octave_weight: float = 0.5,
                      duration_weight: float = 0.3) -> float:
    """
    두 note 간의 DFT 거리.

    각 note의 pitch class를 Fourier 공간으로 변환하여
    L2 거리를 계산합니다.

    d(n1, n2) = ||DFT(pc1) - DFT(pc2)||₂
              + octave_weight * |oct1 - oct2|
              + duration_weight * |dur1 - dur2| / max_dur
    """
    p1, d1 = note1
    p2, d2 = note2

    # DFT 거리
    f1 = pitch_class_dft(p1)
    f2 = pitch_class_dft(p2)
    dft_dist = np.linalg.norm(f1 - f2)

    # 옥타브 + duration
    oct_diff = abs(p1 // 12 - p2 // 12)
    max_dur = max(d1, d2, 1)
    dur_diff = abs(d1 - d2) / max_dur

    return dft_dist + octave_weight * oct_diff + duration_weight * dur_diff


# ═══════════════════════════════════════════════════════════════════════════
# 플러그인 인터페이스
# ═══════════════════════════════════════════════════════════════════════════

METRICS = {
    'tonnetz': tonnetz_note_distance,
    'voice_leading': voice_leading_note_distance,
    'dft': dft_note_distance,
}


def get_metric(name: str):
    """이름으로 거리 함수를 가져옵니다."""
    if name not in METRICS:
        raise ValueError(f"Unknown metric '{name}'. Available: {list(METRICS.keys())}")
    return METRICS[name]


def compute_note_distance_matrix(notes_label: dict,
                                 metric: str = 'tonnetz',
                                 **kwargs) -> np.ndarray:
    """
    notes_label의 모든 note 쌍에 대해 musical metric 거리 행렬을 계산합니다.

    기존 파이프라인의 빈도 기반 거리를 대체하거나 결합할 수 있습니다.

    Args:
        notes_label: {(pitch, dur): label} 매핑 (1-indexed)
        metric: 'tonnetz' | 'voice_leading' | 'dft'

    Returns:
        (N, N) 대칭 거리 행렬 (1-indexed label 순서)
    """
    dist_fn = get_metric(metric)

    # label 순서대로 note 목록 구성
    sorted_items = sorted(notes_label.items(), key=lambda x: x[1])
    notes = [note_tuple for note_tuple, label in sorted_items]
    N = len(notes)

    dist = np.zeros((N, N), dtype=float)
    for i in range(N):
        for j in range(i + 1, N):
            d = dist_fn(notes[i], notes[j], **kwargs)
            dist[i, j] = d
            dist[j, i] = d

    return dist


def compute_hybrid_distance(freq_distance: np.ndarray,
                            musical_distance: np.ndarray,
                            alpha: float = 0.5) -> np.ndarray:
    """
    빈도 기반 거리와 음악적 거리를 결합합니다.

    d_hybrid = alpha * d_freq_normalized + (1 - alpha) * d_musical_normalized

    Args:
        freq_distance: 기존 빈도 역수 거리 행렬 (N, N)
        musical_distance: 음악적 거리 행렬 (N, N)
        alpha: 빈도 거리 가중치 (0=음악적만, 1=빈도만, 0.5=반반)
    """
    # 각 행렬을 [0, 1]로 정규화
    def normalize(m):
        mask = m > 0
        if not mask.any():
            return m
        min_val = m[mask].min()
        max_val = m[mask].max()
        if max_val == min_val:
            return np.where(mask, 0.5, 0)
        result = np.zeros_like(m)
        result[mask] = (m[mask] - min_val) / (max_val - min_val)
        return result

    f_norm = normalize(freq_distance)
    m_norm = normalize(musical_distance)

    return alpha * f_norm + (1 - alpha) * m_norm
