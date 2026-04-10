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


def restore_durations_probabilistic(
        generated_notes: List[Tuple[int, int, int]],
        original_notes: List[Tuple[int, int, int]],
        T: int,
        seed: Optional[int] = None) -> List[Tuple[int, int, int]]:
    """
    확률적 duration 복원 — 원곡의 pitch 별 duration 분포에서 샘플링.

    원리:
      1. 원곡에서 각 pitch 가 실제로 쓰인 duration 의 빈도 분포를 구함
         예: C4 → {dur=1: 10회, dur=2: 20회, dur=3: 30회, dur=4: 40회}
      2. Algorithm 1 이 (start, C4, start+1) 을 생성하면,
         위 분포에서 가중 랜덤 추출 → 40% 확률로 dur=4 선택
      3. 선택된 duration 만큼 해당 pitch 를 유지
         → 그 동안 같은 pitch 의 새 onset 은 허용하지 않음

    이 방식이 기존 median/smoothed 보다 나은 이유:
      - median 은 "평균적 길이"를 할당하지만 분포의 다양성이 사라짐
      - 확률적 샘플링은 원곡의 duration 다양성을 그대로 재현

    Args:
        generated_notes: Algorithm 1/2 가 생성한 [(start, pitch, end), ...]
        original_notes: 원곡의 [(start, pitch, end), ...]
        T: 전체 시간 길이
        seed: 재현성을 위한 random seed (None 이면 비결정적)

    Returns:
        duration 이 확률적으로 복원된 note 리스트
    """
    import random as rng
    if seed is not None:
        rng.seed(seed)

    # 1. pitch 별 duration 분포 구축
    pitch_dur_dist: dict = defaultdict(Counter)
    for s, p, e in original_notes:
        d = e - s
        if d > 0:
            pitch_dur_dist[p][d] += 1

    # 가중 랜덤 추출용 사전 계산
    pitch_dur_choices: dict = {}
    for p, counter in pitch_dur_dist.items():
        durs = list(counter.keys())
        weights = list(counter.values())
        pitch_dur_choices[p] = (durs, weights)

    # fallback: 전체 duration 분포
    all_durs_counter = Counter()
    for c in pitch_dur_dist.values():
        all_durs_counter.update(c)
    fallback_durs = list(all_durs_counter.keys())
    fallback_weights = list(all_durs_counter.values())

    # 2. 시간순 정렬 + duration 할당
    sorted_notes = sorted(generated_notes, key=lambda x: (x[0], x[1]))
    restored = []
    pitch_end: dict = {}  # pitch → 가장 빠른 허용 onset 시점

    for s, p, e in sorted_notes:
        # 같은 pitch 가 아직 울리고 있으면 건너뜀
        if p in pitch_end and s < pitch_end[p]:
            continue

        # duration 샘플링
        if p in pitch_dur_choices:
            durs, weights = pitch_dur_choices[p]
            d = rng.choices(durs, weights=weights, k=1)[0]
        else:
            d = rng.choices(fallback_durs, weights=fallback_weights, k=1)[0]

        new_end = min(s + d, T)
        if new_end <= s:
            continue

        restored.append((s, p, new_end))
        pitch_end[p] = new_end

    return restored


def restore_durations(generated_notes: List[Tuple[int, int, int]],
                       original_notes: List[Tuple[int, int, int]],
                       T: int,
                       method: str = 'probabilistic',
                       window: int = 16,
                       seed: Optional[int] = None) -> List[Tuple[int, int, int]]:
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
    # probabilistic 이 기본 (신규 추천)
    if method == 'probabilistic':
        return restore_durations_probabilistic(
            generated_notes, original_notes, T, seed=seed)

    pitch_dur = compute_pitch_duration_map(original_notes, method='median')
    smoothed_dur = compute_smoothed_duration(original_notes, T, window)

    global_median = max(1, int(np.median([e-s for s,_,e in original_notes if e > s])))

    restored = []
    sorted_notes = sorted(generated_notes, key=lambda x: (x[0], x[1]))
    pitch_end = {}

    for s, p, e in sorted_notes:
        if p in pitch_end and s < pitch_end[p]:
            continue

        if method == 'per_pitch':
            d = pitch_dur.get(p, global_median)
        elif method == 'smoothed':
            d = int(smoothed_dur[min(s, T - 1)]) if s < T else global_median
        elif method == 'hybrid':
            d_pitch = pitch_dur.get(p, global_median)
            d_smooth = int(smoothed_dur[min(s, T - 1)]) if s < T else global_median
            d = max(1, round(0.6 * d_pitch + 0.4 * d_smooth))
        else:
            d = 1

        new_end = min(s + d, T)
        if new_end <= s:
            continue

        restored.append((s, p, new_end))
        pitch_end[p] = new_end

    return restored
