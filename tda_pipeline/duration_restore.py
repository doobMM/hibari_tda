"""
duration_restore.py — 생성된 note 의 duration 을 원곡 패턴으로 복원

문제: pitch-only labeling (GCD tie 해석) 으로 PH 를 계산하면 모든 note 가
dur=1 로 생성되어 WAV 가 불완전하게 들림.

해결: 원곡의 duration 통계를 사용하여 생성된 note 에 현실적인 duration 부여.

두 가지 전략:
  A. per_pitch_restore: 각 pitch 의 원곡 median duration 을 적용
  B. smoothed_restore: 시점별 이동평균 duration 을 적용

두 전략 모두 onset overlap 방지 로직 포함.
"""
import numpy as np
from collections import defaultdict, Counter
from typing import List, Tuple, Optional


def compute_pitch_duration_map(original_notes: List[Tuple[int, int, int]],
                                method: str = 'median') -> dict:
    """원곡에서 pitch 별 대표 duration 계산.

    Args:
        original_notes: [(start, pitch, end), ...]
        method: 'median' | 'mode' | 'mean'

    Returns:
        {pitch: representative_duration}
    """
    pitch_durs = defaultdict(list)
    for s, p, e in original_notes:
        d = e - s
        if d > 0:
            pitch_durs[p].append(d)

    result = {}
    for p, ds in pitch_durs.items():
        if method == 'median':
            result[p] = max(1, int(np.median(ds)))
        elif method == 'mode':
            result[p] = Counter(ds).most_common(1)[0][0]
        elif method == 'mean':
            result[p] = max(1, round(np.mean(ds)))
    return result


def compute_smoothed_duration(original_notes: List[Tuple[int, int, int]],
                               T: int,
                               window: int = 16) -> np.ndarray:
    """시점별 이동평균 duration 계산.

    Returns:
        length-T array, smoothed_dur[t] = 해당 시점에서의 기대 duration (정수)
    """
    dur_sum = np.zeros(T + 1)
    dur_count = np.zeros(T + 1)
    for s, p, e in original_notes:
        d = e - s
        if 0 <= s <= T and d > 0:
            dur_sum[s] += d
            dur_count[s] += 1

    avg = np.where(dur_count > 0, dur_sum / dur_count, 1.0)

    # 이동평균
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(avg[:T], size=window)
    return np.clip(np.round(smoothed).astype(int), 1, 20)


def restore_durations(generated_notes: List[Tuple[int, int, int]],
                       original_notes: List[Tuple[int, int, int]],
                       T: int,
                       method: str = 'hybrid',
                       window: int = 16) -> List[Tuple[int, int, int]]:
    """생성된 note 의 duration 을 원곡 패턴으로 복원.

    Args:
        generated_notes: Algorithm 1/2 가 생성한 [(start, pitch, end), ...]
                         대부분 end = start + 1 (pitch-only labeling 결과)
        original_notes: 원곡의 [(start, pitch, end), ...]
        T: 전체 시간 길이
        method:
            'per_pitch' — pitch 별 median duration
            'smoothed'  — 시점별 이동평균 duration
            'hybrid'    — per_pitch 를 기본, smoothed 로 보정
        window: smoothed 이동평균 윈도우 크기

    Returns:
        duration 이 복원된 note 리스트 (onset overlap 방지 적용)
    """
    pitch_dur = compute_pitch_duration_map(original_notes, method='median')
    smoothed_dur = compute_smoothed_duration(original_notes, T, window)

    # pitch 별 duration 이 없는 경우의 fallback
    global_median = max(1, int(np.median([e-s for s,_,e in original_notes if e > s])))

    restored = []
    # onset 별로 정렬
    sorted_notes = sorted(generated_notes, key=lambda x: (x[0], x[1]))

    # pitch 별 마지막 onset + duration 추적 (같은 pitch 겹침 방지)
    pitch_end = {}  # pitch → earliest allowed next onset

    for s, p, e in sorted_notes:
        # 이미 이 pitch 가 울리고 있으면 건너뜀
        if p in pitch_end and s < pitch_end[p]:
            continue

        # duration 결정
        if method == 'per_pitch':
            d = pitch_dur.get(p, global_median)
        elif method == 'smoothed':
            d = int(smoothed_dur[min(s, T - 1)]) if s < T else global_median
        elif method == 'hybrid':
            d_pitch = pitch_dur.get(p, global_median)
            d_smooth = int(smoothed_dur[min(s, T - 1)]) if s < T else global_median
            # pitch 고유 duration 과 시점 duration 의 가중 평균
            d = max(1, round(0.6 * d_pitch + 0.4 * d_smooth))
        else:
            d = 1

        new_end = min(s + d, T)
        if new_end <= s:
            continue

        restored.append((s, p, new_end))
        pitch_end[p] = new_end

    return restored
