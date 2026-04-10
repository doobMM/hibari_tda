"""
sequence_metrics.py — JS 를 넘어서는 선율/구조 유사도 지표

기존 eval_metrics.py 의 pitch JS divergence 는 pitch 빈도 분포만 비교하므로
"어떤 음이 어떤 음 다음에 오는가" (선율 흐름) 를 포착하지 못한다.
본 모듈은 이를 보완하는 세 가지 sequence-aware 지표를 제공한다.

  1. Transition JS     — bigram (음 쌍) 분포의 JS divergence
  2. DTW distance      — Dynamic Time Warping 으로 pitch 시퀀스 정렬 후 거리
  3. NCD               — Normalized Compression Distance (gzip 기반)
"""
import numpy as np
from collections import Counter
from typing import List, Tuple


# ── 1. Transition JS Divergence ──────────────────────────────────────

def _pitch_sequence(notes: List[Tuple[int, int, int]]) -> List[int]:
    """note 리스트를 시간 순서의 pitch 시퀀스로 변환."""
    return [p for _, p, _ in sorted(notes, key=lambda x: (x[0], x[1]))]


def _bigram_distribution(pitch_seq: List[int]) -> dict:
    """pitch 시퀀스에서 (p_i, p_{i+1}) bigram 빈도 분포."""
    if len(pitch_seq) < 2:
        return {}
    bigrams = Counter()
    for i in range(len(pitch_seq) - 1):
        bigrams[(pitch_seq[i], pitch_seq[i + 1])] += 1
    total = sum(bigrams.values())
    return {k: v / total for k, v in bigrams.items()}


def transition_js_divergence(generated: List[Tuple[int, int, int]],
                              original: List[Tuple[int, int, int]]) -> float:
    """
    Transition JS Divergence — 두 곡의 pitch bigram 분포 간 JS divergence.

    pitch JS 가 "어떤 음이 얼마나 자주 나오는가" 를 측정한다면,
    transition JS 는 "어떤 음 다음에 어떤 음이 오는가" 를 측정한다.

    Returns: 0.0 (동일) ~ log(2) ≈ 0.693 (완전 분리)
    """
    gen_seq = _pitch_sequence(generated)
    orig_seq = _pitch_sequence(original)

    gen_dist = _bigram_distribution(gen_seq)
    orig_dist = _bigram_distribution(orig_seq)

    # 공통 key 집합
    all_keys = set(gen_dist.keys()) | set(orig_dist.keys())
    if not all_keys:
        return 0.0

    # numpy 로 JS 계산
    P = np.array([orig_dist.get(k, 0) for k in all_keys])
    Q = np.array([gen_dist.get(k, 0) for k in all_keys])

    # smoothing (0 방지)
    eps = 1e-12
    P = P + eps; P = P / P.sum()
    Q = Q + eps; Q = Q / Q.sum()

    M = 0.5 * (P + Q)
    kl_pm = np.sum(P * np.log(P / M))
    kl_qm = np.sum(Q * np.log(Q / M))
    return float(0.5 * kl_pm + 0.5 * kl_qm)


# ── 2. DTW (Dynamic Time Warping) ───────────────────────────────────

def dtw_pitch_distance(generated: List[Tuple[int, int, int]],
                        original: List[Tuple[int, int, int]],
                        max_len: int = 2000) -> float:
    """
    DTW distance — 두 pitch 시퀀스를 시간축으로 유연하게 정렬한 뒤 거리.

    선율의 "윤곽(contour)" 이 얼마나 닮았는지를 측정. 템포 차이를 흡수.

    Args:
        max_len: 시퀀스가 이보다 길면 균등 다운샘플링 (O(N²) 제한)

    Returns: 정규화된 DTW 거리 (0 에 가까울수록 유사)
    """
    gen_seq = np.array(_pitch_sequence(generated), dtype=float)
    orig_seq = np.array(_pitch_sequence(original), dtype=float)

    # 다운샘플링 (너무 길면 O(N²) 폭발 방지)
    if len(gen_seq) > max_len:
        idx = np.linspace(0, len(gen_seq) - 1, max_len, dtype=int)
        gen_seq = gen_seq[idx]
    if len(orig_seq) > max_len:
        idx = np.linspace(0, len(orig_seq) - 1, max_len, dtype=int)
        orig_seq = orig_seq[idx]

    n, m = len(gen_seq), len(orig_seq)
    if n == 0 or m == 0:
        return float('inf')

    # DTW 행렬 (Sakoe-Chiba band 없이 full matrix)
    dtw = np.full((n + 1, m + 1), np.inf)
    dtw[0, 0] = 0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(gen_seq[i - 1] - orig_seq[j - 1])
            dtw[i, j] = cost + min(dtw[i - 1, j],      # insertion
                                    dtw[i, j - 1],      # deletion
                                    dtw[i - 1, j - 1])  # match

    # 정규화: 경로 길이 (n + m) 으로 나눔
    return float(dtw[n, m] / (n + m))


# ── 3. NCD (Normalized Compression Distance) ────────────────────────

def ncd_pitch(generated: List[Tuple[int, int, int]],
              original: List[Tuple[int, int, int]]) -> float:
    """
    NCD — Normalized Compression Distance (gzip 기반).

    두 pitch 시퀀스를 bytes 로 변환한 뒤 gzip 압축.
    "함께 압축하면 얼마나 줄어드는가" 로 유사도 측정.

    파라미터 없이 작동하며, 전체 구조적 닮음을 포착.

    Returns: 0.0 (동일) ~ 1.0+ (완전 분리)
    """
    import gzip

    gen_seq = _pitch_sequence(generated)
    orig_seq = _pitch_sequence(original)

    # pitch 를 bytes 로 변환 (각 pitch 를 1 byte 로)
    x = bytes(gen_seq)
    y = bytes(orig_seq)
    xy = x + y

    cx = len(gzip.compress(x))
    cy = len(gzip.compress(y))
    cxy = len(gzip.compress(xy))

    return float((cxy - min(cx, cy)) / max(cx, cy))


# ── 통합 평가 함수 ──────────────────────────────────────────────────

def evaluate_sequence_metrics(generated: List[Tuple[int, int, int]],
                               original: List[Tuple[int, int, int]],
                               name: str = "") -> dict:
    """
    JS (pitch) + Transition JS + DTW + NCD 를 한 번에 계산.

    기존 eval_metrics.evaluate_generation 을 보완하는 함수.
    """
    from eval_metrics import pitch_distribution_similarity

    orig_flat = original if not isinstance(original[0], list) else \
        [n for inst in original for n in inst]

    pitch_sim = pitch_distribution_similarity(generated, orig_flat)

    result = {
        'pitch_js': float(pitch_sim['js_divergence']),
        'transition_js': transition_js_divergence(generated, orig_flat),
        'dtw': dtw_pitch_distance(generated, orig_flat),
        'ncd': ncd_pitch(generated, orig_flat),
    }

    if name:
        print(f"\n  [{name}]")
        print(f"    pitch JS:      {result['pitch_js']:.4f}")
        print(f"    transition JS: {result['transition_js']:.4f}")
        print(f"    DTW:           {result['dtw']:.4f}")
        print(f"    NCD:           {result['ncd']:.4f}")

    return result
