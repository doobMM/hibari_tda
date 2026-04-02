"""
eval_metrics.py — 생성 음악 평가 지표
=======================================

val_loss만으로는 음악적 품질을 판단할 수 없으므로,
다양한 관점에서 생성 결과를 평가합니다.

지표:
1. Note Coverage: 원곡의 23개 note 중 생성 곡에 등장하는 비율
2. Pitch 분포 유사도: KL-divergence로 원곡과 생성곡의 pitch 빈도 비교
3. Duration 다양성: 사용된 duration 종류 수
4. Overlap 충실도: 생성 곡의 활성 패턴이 원래 overlap과 일치하는 정도
"""

import numpy as np
from collections import Counter
from typing import List, Tuple, Dict, Optional


def note_coverage(generated: List[Tuple[int, int, int]],
                  notes_label: dict) -> Dict[str, float]:
    """
    생성된 음악이 원곡의 note 종류를 얼마나 커버하는지 측정.

    Args:
        generated: [(start, pitch, end), ...] 생성된 note 리스트
        notes_label: (pitch, dur) -> label 매핑 (원곡의 전체 note 종류)

    Returns:
        {'coverage': 0~1, 'n_used': int, 'n_total': int, 'missing': set}
    """
    total_notes = set(notes_label.values())  # 1-indexed labels
    used_pitches = set()

    for start, pitch, end in generated:
        dur = end - start
        key = (pitch, dur)
        if key in notes_label:
            used_pitches.add(notes_label[key])

    coverage = len(used_pitches) / len(total_notes) if total_notes else 1.0
    missing = total_notes - used_pitches

    return {
        'coverage': coverage,
        'n_used': len(used_pitches),
        'n_total': len(total_notes),
        'missing_labels': missing
    }


def pitch_distribution_similarity(generated: List[Tuple[int, int, int]],
                                   original: List[Tuple[int, int, int]],
                                   ) -> Dict[str, float]:
    """
    원곡과 생성곡의 pitch 빈도 분포를 비교합니다.
    KL-divergence가 낮을수록 유사합니다.

    Returns:
        {'kl_divergence': float, 'js_divergence': float,
         'common_pitches': int, 'gen_unique_pitches': int}
    """
    orig_pitches = Counter(p for _, p, _ in original)
    gen_pitches = Counter(p for _, p, _ in generated)

    all_pitches = set(orig_pitches.keys()) | set(gen_pitches.keys())
    if not all_pitches:
        return {'kl_divergence': 0.0, 'js_divergence': 0.0,
                'common_pitches': 0, 'gen_unique_pitches': 0}

    # 정규화된 분포
    orig_total = sum(orig_pitches.values())
    gen_total = sum(gen_pitches.values())

    eps = 1e-10  # smoothing
    p = np.array([orig_pitches.get(k, 0) / orig_total + eps for k in sorted(all_pitches)])
    q = np.array([gen_pitches.get(k, 0) / gen_total + eps for k in sorted(all_pitches)])
    p /= p.sum()
    q /= q.sum()

    # KL divergence: D(P || Q)
    kl = np.sum(p * np.log(p / q))

    # Jensen-Shannon divergence (대칭)
    m = 0.5 * (p + q)
    js = 0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m))

    common = len(set(orig_pitches.keys()) & set(gen_pitches.keys()))

    return {
        'kl_divergence': float(kl),
        'js_divergence': float(js),
        'common_pitches': common,
        'gen_unique_pitches': len(gen_pitches)
    }


def duration_diversity(generated: List[Tuple[int, int, int]],
                       original: List[Tuple[int, int, int]]) -> Dict[str, float]:
    """
    사용된 duration 종류와 분포를 비교합니다.

    Returns:
        {'gen_durations': int, 'orig_durations': int,
         'duration_coverage': float}
    """
    orig_durs = set(e - s for s, _, e in original)
    gen_durs = set(e - s for s, _, e in generated)

    coverage = len(gen_durs & orig_durs) / len(orig_durs) if orig_durs else 1.0

    return {
        'gen_durations': len(gen_durs),
        'orig_durations': len(orig_durs),
        'duration_coverage': coverage
    }


def evaluate_generation(generated: List[Tuple[int, int, int]],
                        original_notes: List[List[Tuple[int, int, int]]],
                        notes_label: dict,
                        name: str = "") -> dict:
    """
    생성 결과를 종합 평가합니다.

    Args:
        generated: 생성된 note 리스트
        original_notes: [inst1_notes, inst2_notes] 원곡
        notes_label: (pitch, dur) -> label
        name: 모델/설정 이름 (출력용)
    """
    # 원곡 통합
    orig_flat = []
    for inst in original_notes:
        orig_flat.extend(inst)

    cov = note_coverage(generated, notes_label)
    pitch = pitch_distribution_similarity(generated, orig_flat)
    dur = duration_diversity(generated, orig_flat)

    result = {
        'name': name,
        'n_notes': len(generated),
        'note_coverage': cov['coverage'],
        'missing_notes': len(cov['missing_labels']),
        'kl_divergence': pitch['kl_divergence'],
        'js_divergence': pitch['js_divergence'],
        'pitch_count': pitch['gen_unique_pitches'],
        'duration_coverage': dur['duration_coverage'],
        'duration_count': dur['gen_durations'],
    }

    if name:
        print(f"\n  [{name}] 평가 결과:")
        print(f"    Notes: {result['n_notes']}")
        print(f"    Note coverage: {cov['n_used']}/{cov['n_total']}"
              f" ({cov['coverage']:.1%})"
              f"{' missing: ' + str(sorted(cov['missing_labels'])) if cov['missing_labels'] else ''}")
        print(f"    Pitch distribution: KL={pitch['kl_divergence']:.4f},"
              f" JS={pitch['js_divergence']:.4f}")
        print(f"    Duration: {dur['gen_durations']}/{dur['orig_durations']} types"
              f" ({dur['duration_coverage']:.1%})")

    return result
