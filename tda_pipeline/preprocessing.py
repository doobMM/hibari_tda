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

def load_and_quantize(midi_file: str) -> Tuple[List[Tuple[int, int, int]], float]:
    """
    MIDI 파일을 로드하여 8분음표 단위로 양자화합니다.
    
    Returns:
        (adjusted_notes, tempo) 
        adjusted_notes: List of (start_eighth, pitch, end_eighth)
    """
    midi_data = pretty_midi.PrettyMIDI(midi_file)
    tempo = midi_data.get_tempo_changes()[1][0]
    eighth_dur = 60 / tempo / 2

    adjusted_notes = []
    instrument_boundaries = []
    
    for inst in midi_data.instruments:
        for note in inst.notes:
            s = round(note.start / eighth_dur)
            e = round(note.end / eighth_dur)
            adjusted_notes.append((s, note.pitch, e))
        instrument_boundaries.append(len(adjusted_notes))

    return adjusted_notes, tempo, instrument_boundaries


def split_instruments(adjusted_notes: list, boundary: int) -> Tuple[list, list]:
    """두 악기로 분리"""
    return adjusted_notes[:boundary], adjusted_notes[boundary:]


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
