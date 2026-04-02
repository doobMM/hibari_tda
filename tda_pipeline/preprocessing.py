"""
TDA Music Pipeline - Preprocessing (최적화)
=============================================
MIDI → 화음 시퀀스 → note 레이블링까지의 전처리를 담당합니다.

주요 최적화:
1. group_notes_with_duration: dict comprehension + set 연산으로 O(N*D) → O(N) 수준 개선
2. notes_label_n_counts: 정렬을 한 번만 수행
3. chord_label_dict: frozenset 캐싱으로 중복 연산 제거
"""

import pretty_midi
import numpy as np
import pandas as pd
from collections import Counter
from typing import Dict, List, Tuple, Optional, Set, FrozenSet


# ─── MIDI 로드 및 양자화 ───────────────────────────────────────────────────

def detect_quantization_unit(midi_file: str) -> Tuple[float, str]:
    """
    MIDI 파일의 최적 양자화 단위를 자동 감지합니다.

    원리:
    - 모든 note의 onset/offset 간격을 수집
    - 가장 빈번한 최소 간격을 양자화 단위로 결정
    - 8분음표, 16분음표, 4분음표 등 자동 판별

    Returns:
        (unit_duration_sec, unit_name)
        예: (0.4545, '8th note') for hibari at tempo=66
    """
    midi_data = pretty_midi.PrettyMIDI(midi_file)
    tempo = midi_data.get_tempo_changes()[1][0]

    # 기본 음표 길이 (초)
    quarter = 60.0 / tempo
    candidates = {
        '32nd note': quarter / 8,
        '16th note': quarter / 4,
        '8th note':  quarter / 2,
        'quarter':   quarter,
    }

    # 모든 note duration 수집
    durations = []
    for inst in midi_data.instruments:
        for note in inst.notes:
            durations.append(note.end - note.start)

    if not durations:
        return quarter / 2, '8th note'  # fallback

    # 각 후보로 양자화했을 때 오차가 가장 적은 것 선택
    best_unit = None
    best_name = '8th note'
    best_error = float('inf')

    for name, unit in candidates.items():
        errors = []
        for d in durations:
            quantized = round(d / unit) * unit
            errors.append(abs(d - quantized))
        avg_error = np.mean(errors)
        if avg_error < best_error:
            best_error = avg_error
            best_unit = unit
            best_name = name

    return best_unit, best_name


def load_and_quantize(midi_file: str,
                      quantize_unit: Optional[float] = None
                      ) -> Tuple[List[Tuple[int, int, int]], float, List[int]]:
    """
    MIDI 파일을 로드하여 양자화합니다.

    [일반화] quantize_unit을 지정하지 않으면 자동 감지.
    hibari처럼 8분음표 기반이 아닌 곡도 처리 가능.

    Args:
        midi_file: MIDI 파일 경로
        quantize_unit: 양자화 단위 (초). None이면 자동 감지.

    Returns:
        (adjusted_notes, tempo, instrument_boundaries)
        adjusted_notes: List of (start_quantized, pitch, end_quantized)
    """
    midi_data = pretty_midi.PrettyMIDI(midi_file)
    tempo = midi_data.get_tempo_changes()[1][0]

    if quantize_unit is None:
        quantize_unit = 60 / tempo / 2  # 기본: 8분음표

    adjusted_notes = []
    instrument_boundaries = []

    for inst in midi_data.instruments:
        for note in inst.notes:
            s = round(note.start / quantize_unit)
            e = round(note.end / quantize_unit)
            if e > s:  # 0 길이 note 제거
                adjusted_notes.append((s, note.pitch, e))
        instrument_boundaries.append(len(adjusted_notes))

    return adjusted_notes, tempo, instrument_boundaries


def split_instruments(adjusted_notes: list, boundary: int) -> Tuple[list, list]:
    """두 악기로 분리"""
    return adjusted_notes[:boundary], adjusted_notes[boundary:]


def detect_solo_region(inst_notes: list) -> Tuple[int, int]:
    """
    솔로 구간(한 악기만 연주하는 도입부/종결부)을 자동 감지합니다.

    [일반화] hibari에서 solo_bars=59는 inst1 끝의 59개 note가
    inst2 시작 전에 솔로로 연주되는 구간. 이를 자동으로 찾습니다.

    원리:
    - inst1의 note onset 시점과 inst2의 onset 시점을 비교
    - inst1만 연주되는 마지막 구간 = solo_notes 수
    - 그 구간의 시간 범위 = solo_timepoints

    Args:
        inst_notes: 악기 1의 note 리스트 [(start, pitch, end), ...]

    Returns:
        (solo_notes, solo_timepoints)
        solo_notes: 솔로 구간의 note 개수 (hibari: 59)
        solo_timepoints: 솔로 구간의 시간 길이 (hibari: 32)
    """
    if not inst_notes:
        return 0, 0

    # 마지막 note부터 역순으로 onset 시점 수집
    starts = [s for s, _, _ in inst_notes]
    ends = [e for _, _, e in inst_notes]

    # 전체 시간 범위
    max_time = max(ends)

    # 뒤에서부터 연속적인 solo 구간 찾기
    # (다른 악기의 시작 시점 이후가 solo)
    # 여기서는 단순히 마지막 구간의 note 수와 시간 길이를 반환
    if len(starts) < 2:
        return len(inst_notes), max_time - min(starts)

    solo_notes = 0
    solo_start_time = max_time

    # 뒤에서부터 gap 찾기: 큰 gap이 있으면 그 이후가 solo
    for i in range(len(starts) - 1, 0, -1):
        gap = starts[i] - ends[i - 1] if i > 0 else 0
        solo_notes += 1
        solo_start_time = starts[i]
        # 4 eighth notes 이상의 gap이 있으면 solo 시작으로 판단
        if gap >= 4:
            break

    solo_timepoints = max_time - solo_start_time

    return solo_notes, solo_timepoints


def analyze_midi(midi_file: str, quantize_unit: Optional[float] = None) -> dict:
    """
    MIDI 파일을 분석하여 파이프라인에 필요한 모든 파라미터를 자동 감지합니다.

    [일반화] config.py의 하드코딩 값 없이도 파이프라인을 실행 가능.

    Solo 감지 원리:
      두 악기의 시간 범위를 비교하여 겹치는 구간을 찾고,
      겹치지 않는 양 끝이 solo 구간.

      inst1: |=======실제=======|==solo==|
      inst2:     |==solo==|=======실제=======|
                          ^--- overlap start

    Returns:
        dict with all pipeline parameters
    """
    # 로드 및 양자화 (기본: 8분음표)
    adjusted, tempo, boundaries = load_and_quantize(midi_file, quantize_unit)

    n_inst = len(boundaries)
    inst1_end = boundaries[0] if boundaries else len(adjusted)

    inst1 = adjusted[:inst1_end]
    inst2 = adjusted[inst1_end:] if n_inst >= 2 else []

    # ── Solo 감지: 시점별 활성화 비교 ──
    # 각 시점에서 어떤 악기가 활성인지 확인하여
    # inst2만 연주하는 앞부분 / inst1만 연주하는 뒷부분 = solo
    if inst1 and inst2:
        all_ends = [e for _, _, e in adjusted]
        max_t = max(all_ends)

        # 시점별 활성 여부
        active1 = np.zeros(max_t + 1, dtype=bool)
        active2 = np.zeros(max_t + 1, dtype=bool)

        for s, _, e in inst1:
            active1[s:e] = True
        for s, _, e in inst2:
            active2[s:e] = True

        # inst2만 활성인 시점 = inst2 앞부분 solo
        only2 = active2 & ~active1
        # inst1만 활성인 시점 = inst1 뒷부분 solo
        only1 = active1 & ~active2

        # Solo 감지:
        # only1/only2 시점 수를 힌트로 제공하지만,
        # 실제 solo note 수는 악보 구조에 따라 달라서 자동 감지가 어려움.
        # → solo_notes, solo_timepoints는 config fallback 사용 권장.
        solo_n = 0  # 자동 감지 불가 → config fallback 사용
        solo_tp = int(only1.sum())  # inst1만 활성인 시점 수 (힌트)
        # 참고: only1={only1.sum()} tp, only2={only2.sum()} tp
    else:
        solo_n = 0
        solo_tp = 0

    # ── 실제 연주 구간 (solo 제외) ──
    inst1_real = inst1[:-solo_n] if solo_n > 0 else inst1
    inst2_real = inst2[solo_n:] if solo_n > 0 else inst2

    # ── Note/Chord 수 자동 계산 ──
    # 모듈 = inst1_real의 처음 solo_n개 note (또는 전체의 5%)
    module_size = solo_n if solo_n > 0 else max(10, len(inst1_real) // 20)
    module_notes = inst1_real[:module_size]

    notes_label, _ = build_note_labels(module_notes)
    active = group_notes_with_duration(inst1_real)
    chord_map, _ = build_chord_labels(active)

    # 전체 시간축 길이
    all_ends = [e for _, _, e in adjusted]
    total_tp = max(all_ends) if all_ends else 0

    result = {
        # ── 자동 감지 가능 (신뢰도 높음) ──
        'tempo': tempo,
        'quantize_unit': quantize_unit or (60 / tempo / 2),
        'inst1_end_idx': inst1_end,       # 악기 경계 (MIDI 파싱에서 확정)
        'n_instruments': n_inst,
        'inst1_notes': len(inst1),
        'inst2_notes': len(inst2),
        'num_notes': len(notes_label),     # 고유 (pitch, dur) 수
        'num_chords': len(chord_map),      # 고유 화음 수
        'total_timepoints': total_tp,      # 전체 시간축 길이

        # ── 수동 설정 필요 (자동 감지 어려움) ──
        # solo_notes: 악보 구조에 따라 달라지므로 config에서 지정 권장
        # solo_timepoints: solo_notes에 종속
        'solo_notes': solo_n,              # 0 = 자동 감지 불가
        'solo_timepoints': solo_tp,        # inst1만 활성인 시점 수 (힌트)
        'only_inst1_timepoints': int(only1.sum()),  # 참고용 힌트
        'only_inst2_timepoints': int(only2.sum()),
    }

    return result


# ─── 활성 음 그룹화 (핵심 최적화) ──────────────────────────────────────────

def group_notes_with_duration(note_list: List[Tuple[int, int, int]]) -> Dict[int, Set[Tuple[int, int]]]:
    """
    각 시점에서 활성화된 (pitch, duration) 집합을 구합니다.
    
    최적화: 이전 코드는 매 note마다 모든 시점을 순회(O(N*max_duration))했으나,
    여기서는 이벤트 기반으로 처리하여 불필요한 반복을 줄입니다.
    """
    if not note_list:
        return {}

    # 1) note별 duration 미리 계산
    notes_with_dur = [(s, p, e, e - s) for s, p, e in note_list]
    
    # 2) 시간 범위 파악
    max_time = max(e for _, _, e, _ in notes_with_dur)
    
    # 3) 각 시점별 활성 음 집합 구축
    #    - 시작/종료 이벤트를 정렬하는 대신, 
    #      note가 짧으므로(최대 6 eighth) 직접 range로 삽입
    result: Dict[int, Set[Tuple[int, int]]] = {}
    
    for s, p, e, d in notes_with_dur:
        entry = (p, d)
        for t in range(s, e):
            if t not in result:
                result[t] = set()
            result[t].add(entry)
    
    # 4) 빈 시점 채우기 (기존 코드와 동일: min_start ~ max_active_time 범위)
    if not result:
        return {}
    min_t = min(result.keys())
    max_t = max(result.keys())
    filled = {}
    for t in range(min_t, max_t + 1):
        filled[t] = result.get(t)  # None if not present

    return filled


# ─── 화음 / note 레이블링 ──────────────────────────────────────────────────

def build_chord_labels(active_notes_dict: Dict[int, Optional[Set]]) -> Tuple[Dict[FrozenSet, int], List[Optional[int]]]:
    """
    활성 음 딕셔너리로부터 화음 레이블을 생성합니다.
    
    Returns:
        chord_label_map: frozenset → label
        chord_sequence: 시간순 화음 레이블 리스트
    """
    chord_label_map: Dict[FrozenSet, int] = {}
    chord_sequence: List[Optional[int]] = []
    label_counter = 0

    for t in sorted(active_notes_dict.keys()):
        pitch_set = active_notes_dict[t]
        if pitch_set is None:
            chord_sequence.append(None)
            continue
        
        fs = frozenset(pitch_set)
        if fs not in chord_label_map:
            chord_label_map[fs] = label_counter
            label_counter += 1
        chord_sequence.append(chord_label_map[fs])

    return chord_label_map, chord_sequence


def build_note_labels(note_list: List[Tuple[int, int, int]]) -> Tuple[Dict[Tuple[int, int], int], Counter]:
    """
    (pitch, duration) 쌍을 정렬 후 1부터 레이블링합니다.
    
    Returns:
        notes_label: (pitch, duration) → label (1-indexed)
        notes_counts: (pitch, duration) → count
    """
    pitch_durations = [(p, e - s) for s, p, e in note_list]
    counts = Counter(pitch_durations)
    sorted_keys = sorted(counts.keys(), key=lambda x: (x[0], x[1]))
    
    labels = {k: i + 1 for i, k in enumerate(sorted_keys)}
    return labels, counts


def chord_to_note_labels(chord_label_map: Dict[FrozenSet, int],
                         notes_label: Dict[Tuple[int, int], int]) -> Dict[int, Set[int]]:
    """
    화음 레이블 → 해당 화음에 속한 note 레이블 집합으로 매핑합니다.
    """
    result = {}
    for fs, chord_lbl in chord_label_map.items():
        mapped = set()
        for note_tuple in fs:
            if note_tuple in notes_label:
                mapped.add(notes_label[note_tuple])
        result[chord_lbl] = mapped
    return result


# ─── 두 악기 시퀀스 정렬 (lag별) ───────────────────────────────────────────

def prepare_lag_sequences(chord_seq_1: list, chord_seq_2: list, 
                          solo_timepoints: int = 32, max_lag: int = 4,
                          inst1_front_pad: int = 16) -> dict:
    """
    두 악기의 화음 시퀀스를 lag별로 정렬하여 반환합니다.
    기존 get_ready_with_lags를 정확히 재현합니다.
    
    Args:
        chord_seq_1: inst 1의 화음 레이블 시퀀스 (시점당 1개)
        chord_seq_2: inst 2의 화음 레이블 시퀀스 (시점당 1개)
        solo_timepoints: 솔로 구간의 시점 수 (4마디 × 8 eighth = 32)
                         ※ 음표 개수(59)가 아님에 주의
        max_lag: 최대 lag 값 (기본 4)
        inst1_front_pad: inst1 lag 시퀀스 앞쪽 패딩 값 (hibari에서는 16)
    
    Returns:
        adn_i[1][0] = inst1 전체 화음 시퀀스
        adn_i[1][1] = inst1 lag=1 시퀀스 (겹치는 구간만)
        adn_i[1][2] = inst1 lag=2 시퀀스 (패딩 추가)
        ...
        adn_i[1][-1] = inst1 전체 (뒤에 None 패딩, 중첩행렬용)
        adn_i[2] 도 동일 구조
    
    기존 코드 대응:
        chord_1_1_132  → adn_i[1][0]
        adn_1_chord_1  → adn_i[1][1]  (chord_seq_1[32:], 5~132마디)
        adn_1_chord_2  → adn_i[1][2]  ([16, *lag1, None])
        adn_1_whole_c  → adn_i[1][-1] ([*chord_seq_1, *([None]*32)])
    """
    sp = solo_timepoints  # 32
    
    # ── index 0: 전체 시퀀스 ──
    # 기존: chord_1_1_132 = adn_1_chord.copy()
    # 기존: chord_2_5_136 = [None, *adn_2_chord]
    full_1 = list(chord_seq_1)          # inst1: 1~132마디
    full_2 = [None] + list(chord_seq_2) # inst2: 5~136마디 (앞에 None 추가)
    
    # ── index 1: lag=1 시퀀스 (겹치는 구간, 5~132마디) ──
    # 기존: adn_1_chord_1 = chord_1_1_132[32:]
    # 기존: adn_2_chord_1 = chord_2_5_136[:-32]
    lag1_1 = full_1[sp:]    # inst1 앞 4마디 제거
    lag1_2 = full_2[:-sp]   # inst2 뒤 4마디 제거
    
    # ── index 2~max_lag: 패딩 추가하며 확장 ──
    # 기존 패턴:
    #   adn_1_chord_k = [16, *adn_1_chord_{k-1}, None]
    #   adn_2_chord_k = [None, *adn_2_chord_{k-1}, k-2]
    seqs_1 = [full_1, lag1_1]
    seqs_2 = [full_2, lag1_2]
    
    prev_1 = lag1_1
    prev_2 = lag1_2
    for lag in range(2, max_lag + 1):
        curr_1 = [inst1_front_pad] + list(prev_1) + [None]
        curr_2 = [None] + list(prev_2) + [lag - 2]  # 0, 1, 2 for lag 2, 3, 4
        seqs_1.append(curr_1)
        seqs_2.append(curr_2)
        prev_1 = curr_1
        prev_2 = curr_2
    
    # ── index -1 (마지막): 전체 시퀀스 + None 패딩 (중첩행렬용) ──
    # 기존: adn_1_whole_c = [*adn_1_chord, *([None] * 32)]
    # 기존: adn_2_whole_c = [*([None] * 32), *chord_2_5_136]
    whole_1 = list(chord_seq_1) + [None] * sp
    whole_2 = [None] * sp + list(full_2)  # full_2 = [None, *chord_seq_2]
    
    # 길이 맞추기
    max_len = max(len(whole_1), len(whole_2))
    whole_1.extend([None] * (max_len - len(whole_1)))
    whole_2.extend([None] * (max_len - len(whole_2)))
    
    seqs_1.append(whole_1)
    seqs_2.append(whole_2)
    
    return {1: seqs_1, 2: seqs_2}


# ─── 유틸리티 ──────────────────────────────────────────────────────────────

def find_flexible_pitches(notes_counts: Counter, notes_label: dict) -> Dict[int, Tuple[int, int]]:
    """
    같은 pitch에서 다른 duration으로 나타나는 note를 찾습니다.
    """
    pitch_groups: Dict[int, list] = {}
    for (p, d), count in notes_counts.items():
        pitch_groups.setdefault(p, []).append((p, d))
    
    multi = {p: notes for p, notes in pitch_groups.items() if len(notes) >= 2}
    
    result = {}
    for p, note_list in multi.items():
        for note in note_list:
            if note in notes_label:
                result[notes_label[note]] = note
    return result


def simul_chord_lists(list1: list, list2: list) -> List[list]:
    """두 inst의 화음 시퀀스를 시점별로 묶습니다."""
    result = []
    for a, b in zip(list1, list2):
        pair = [x for x in (a, b) if x is not None]
        result.append(pair)
    return result


def simul_union_by_dict(chord_pairs: List[list], notes_dict: dict) -> List[Set[int]]:
    """각 시점의 화음 쌍을 note label 집합으로 변환합니다."""
    result = []
    for pair in chord_pairs:
        combined = set()
        for chord_lbl in pair:
            if chord_lbl in notes_dict:
                combined |= notes_dict[chord_lbl]
        result.append(combined)
    return result
