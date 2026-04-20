# pip install mido pretty_midi librosa tqdm tabulate entropy


import librosa
import mido
from mido import MidiFile
import pretty_midi

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from collections import Counter

import itertools
import re
import os
from music21 import stream, note, tempo, chord, clef, meter, instrument # environment, duration, midi, 

# from util import specify_chord_list
# 순환 호출 이슈로 util에 있는 specify_chord_list를 가져왔다.


def specify_chord_list2(chord_list : list[int], specify_dict : dict) -> list[set[int]]:

    module_notes = []
    for chord_label in chord_list:
        if chord_label in specify_dict:
            module_notes.append(specify_dict[chord_label])
        else:
            module_notes.append(None)  # 키가 딕셔너리에 없으면 None을 사용

    return module_notes

def adjust_to_eighth_note(midi_file):
    """
    MIDI 파일에서 음표의 start와 end를 8분음표 단위로 조정합니다.

    Args:
        midi_file (str): MIDI 파일 경로.
    """
    try:
        midi_data = pretty_midi.PrettyMIDI(midi_file)
        tempo = midi_data.get_tempo_changes()[1][0]  # 첫 번째 템포 값 가져오기 (bpm)
        eighth_note_duration = 60 / tempo / 2  # 8분음표 길이 (초)

        adjusted_notes = []
        i = 0
        j = 0
        for instrument in midi_data.instruments:
            for note in instrument.notes:
                # start와 end를 가장 가까운 8분음표 단위로 반올림
                start_eighth = round(note.start / eighth_note_duration)
                end_eighth = round(note.end / eighth_note_duration)

                # start와 end를 8분음표 단위로 변환
                adjusted_start = start_eighth #* eighth_note_duration
                adjusted_end = end_eighth #* eighth_note_duration

                adjusted_notes.append((adjusted_start, note.pitch, adjusted_end))
                j += 1
            print(f"{i+1}th instrument ending : index {j}")
            i += 1

        return adjusted_notes, tempo

    except FileNotFoundError:
        print("MIDI 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"오류 발생: {e}")
        return None
    
def notes_freq_gcd_checker(adjusted_notes : list) :
    # NumPy 배열로 변환
    notes_array = np.array(adjusted_notes)

    # 음높이 열만 추출하고 DataFrame으로 변환
    notes_df = pd.DataFrame(notes_array[:, 1], columns=['Pitch'])  

    notes = notes_df.value_counts().to_frame()
    notes.reset_index(inplace=True)

    gcd = np.gcd.reduce(notes['count'].unique())
    print(f"{gcd} is a greatest common divisor for ")
    print("counts for which each notes appearing in hibari")

def midi_to_note(midi_note):
    """
    MIDI 노트 번호를 피아노 건반 이름으로 변환합니다.
    """
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note - 12) // 12
    note_name = notes[(midi_note - 12) % 12]
    return f"{note_name}{octave}"

def midi_to_frequency(midi_note):
    """
    MIDI 노트 번호를 주파수(Hz)로 변환합니다.
    """
    return 440 * 2**((midi_note - 69) / 12)

def notes_analyzer(adjusted_notes : list, give_dict : bool = True) :
    """
    adjusted_notes : adjust_to_eighth_note 함수가 뱉은 (start, pitch, end)로 이뤄진 list

    return : 해당 list에 있는 pitch에 대해 (pitch, count, Note Name, Frequency) 컬럼을 가진 df와
                        그 pitch들에 대한 dictionary 2개
    """

    # NumPy 배열로 변환
    notes_array = np.array(adjusted_notes)

    # 음높이 열만 추출하고 DataFrame으로 변환
    notes_df = pd.DataFrame(notes_array[:, 1], columns=['Pitch'])  

    notes = notes_df.value_counts().to_frame()
    notes.reset_index(inplace=True)

    # value_counts 데이터
    pitch_df = notes['Pitch'].to_frame()

    # 각 숫자를 피아노 건반 이름으로 변환하여 새로운 열 추가
    notes['Note Name'] = pitch_df['Pitch'].apply(midi_to_note)

    # 각 숫자를 주파수로 변환하여 새로운 열 추가
    notes['Frequency'] = pitch_df['Pitch'].apply(midi_to_frequency)

    if give_dict :
        pitch_to_note = dict(zip(notes['Pitch'], notes['Note Name']))   
        pitch_to_freq = dict(zip(notes['Pitch'], notes['Frequency']))
        return notes, pitch_to_note, pitch_to_freq
    
    else :
        return notes

def group_pitches(data : list, pithces_only : bool = False):
    """
    (start, pitch, end) 튜플 리스트에서 (start, end)가 같은 튜플들을 그룹화하고,
    pitch를 리스트로 묶습니다.

    Args:
        data (list): (start, pitch, end) 튜플 리스트.

    Returns:
        list: (start, pitches, end) 튜플 리스트 (pitches는 리스트).
    """
    # (start, end)를 기준으로 정렬
    data.sort(key=lambda x: (x[0], x[2]))

    # (start, end)가 같은 튜플들을 그룹화
    grouped_data = []

    if pithces_only :    
        for (start, end), group in itertools.groupby(data, key=lambda x: (x[0], x[2])):
            pitches = set(item[1] for item in group)  # 그룹 내의 pitch들을 set으로 묶음
            grouped_data.append(pitches)  # 새로운 튜플 생성
    else :
        for (start, end), group in itertools.groupby(data, key=lambda x: (x[0], x[2])):
            pitches = set(item[1] for item in group)  # 그룹 내의 pitch들을 set으로 묶음
            grouped_data.append((start, pitches, end))  # 새로운 튜플 생성

    return grouped_data

def reduce_notes(note_name):
  """
  옥타브를 제거한 계이름을 기준으로 그룹을 반환하는 함수.
  """
  base_name = note_name[0]  # 계이름 (C, D, E, F, G, A, B)만 추출
  return base_name

def group_notes_with_duration_(note_list: list) -> dict:
    """
    노트 리스트를 순회하며, 각 start 시간에 해당하는 (pitch, duration) 정보를 set으로 묶고,
    이전 노트의 지속 시간 내에 있는 pitch 정보도 포함합니다.
    각 pitch의 원래 지속 시간을 유지합니다.

    Args:
        note_list (list): (start, pitch, end) 튜플을 요소로 갖는 리스트.

    Returns:
        dict: start 값을 키로 하고 (pitch, duration) 튜플의 set을 값으로 갖는 딕셔너리.
    """

    result = {}
    active_pitches = {}  # 현재 활성화된 pitch 정보 (pitch: (end 시간, duration))

    for start, pitch, end in note_list:
        duration = end - start

        # 현재 시간에 활성화된 pitch 추가
        active_pitches[pitch] = (end, duration)

        # 현재 시간을 기준으로 활성화된 모든 pitch 정보 추가
        for time in range(start, end):  # start부터 end-1까지 순회
            if time not in result:
                result[time] = set()

            for active_pitch, (active_end, active_duration) in active_pitches.items():
                if active_end > time:
                    result[time].add((active_pitch, active_duration))  # 원래 지속 시간 사용

        # 현재 노트 이후에 끝나는 활성화된 pitch 정보만 남김
        active_pitches = {
            p: (e, d) for p, (e, d) in active_pitches.items() if e > start
        }

    return result

def fill_missing_indices_with_none(mapped_result : dict) -> dict :
    """
    mapped_result 딕셔너리의 비어있는 인덱스에 None 값을 채워넣고,
    키 값을 기준으로 정렬된 새로운 딕셔너리를 반환합니다.

    Args:
        mapped_result (dict): 정수 키와 임의의 값을 갖는 딕셔너리.

    Returns:
        dict: 비어있는 인덱스가 None으로 채워지고, 키 값을 기준으로 정렬된 딕셔너리.
    """

    min_index = min(mapped_result.keys())
    max_index = max(mapped_result.keys())

    filled_result = {}
    for i in range(min_index, max_index + 1):
        if i in mapped_result:
            filled_result[i] = mapped_result[i]
        else:
            filled_result[i] = None

    return filled_result

def chord_label_dict(chord_dict = dict) -> dict :
    
    chord_label = {}
    label_counter = 0

    for pitch_set in chord_dict.values():
        # frozenset을 사용하여 set을 hashable하게 만들기
        frozen_set = frozenset(pitch_set)  
        if frozen_set not in chord_label:
            chord_label[frozen_set] = label_counter
            label_counter += 1

    return chord_label

def chord_label_to_note_labels(dict1, dict2):
    """
    dict1의 key인 frozenset에 있는 tuple들을 dict2를 사용하여 해당하는 value로 매핑합니다.

    Args:
        dict1 (dict): chord_frozenset_label가 리턴하는 딕셔너리.
        dict2 (dict): notes_label_n_counts가 리턴하는 딕셔너리.

    Returns:
        dict: dict2의 value를 값으로 하는 딕셔너리 (dict3).  key는 dict1의 value에서 가져옴.
    """

    dict3 = {}
    for frozenset, label in dict1.items():
        mapped_values = set()
        for note in frozenset:  # key는 frozenset(tuple)
            if note in dict2:
                mapped_values.add(dict2[note]) # note_label 추가
        dict3[label] = mapped_values
    return dict3

def label_active_chord_by_onset(adjusted_note : list) -> list :

    # 1-1. onset이 존재하는 start 지점에서 지속되고 있는 chord 고려
    result = group_notes_with_duration_(adjusted_note)

    # 1-2. onset만을 고려하면서 누락된 부분까지 채우기 
    # result_ = fill_duration_indices(result)

    # 2-1. (chord_set-label) 딕셔너리 만들기
    chord_frozenset_label = chord_label_dict(result)

    # 2-2. result의 chord set들을 label에 매핑
    mapped_result = {}
    for start, pitch_set in result.items():
        frozen_set = frozenset(pitch_set)
        mapped_result[start] = chord_frozenset_label[frozen_set]

    # 2-3. onset이 없어서 비어있는 중간에 비어있는 인덱스는 None으로 채우기
    mapped_result_ = fill_missing_indices_with_none(mapped_result)

    # 3. list로 변환
    onset_chord_list = list(mapped_result_.values())

    return onset_chord_list

def get_ready_with_lags(adn_1_chord, adn_2_chord) : 
    """ 
     chord_1_1_132, chord_2_5_136은 intra_weights를 구하는 데 사용됩니다.
     
     adn_i_chord_j는 inst i에 대해 inter_weight를 lag = j에서 구하기 위한 리스트로
     adn_i[i][j]로 접근할 수 있습니다.

     adn_i_whole_c는 중첩행렬을 구하는 등에 사용됩니다.
       """

    chord_1_1_132 = adn_1_chord.copy()  # 1 ~ 132마디
    chord_2_5_136 = [None, *adn_2_chord] # 5 ~ 136마디

    adn_1_chord_1 = chord_1_1_132[32:] # 5 ~ 132마디
    adn_2_chord_1 = chord_2_5_136[:-32] # 5 ~ 132마디

    adn_1_chord_2 = [16, *adn_1_chord_1, None]
    adn_2_chord_2 = [None, *adn_2_chord_1, 0]

    adn_1_chord_3 = [16, *adn_1_chord_2, None]
    adn_2_chord_3 = [None, *adn_2_chord_2, 1]

    adn_1_chord_4 = [16, *adn_1_chord_3, None]
    adn_2_chord_4 = [None, *adn_2_chord_3, 2]

    adn_1_whole_c = [*adn_1_chord, *([None] * 32)]
    adn_2_whole_c = [*([None] * 32), *chord_2_5_136]

    adn_i = dict()
    adn_i[1] = [chord_1_1_132, adn_1_chord_1, adn_1_chord_2, adn_1_chord_3, adn_1_chord_4, adn_1_whole_c]
    adn_i[2] = [chord_2_5_136, adn_2_chord_1, adn_2_chord_2, adn_2_chord_3, adn_2_chord_4, adn_2_whole_c]

    return adn_i

def notes_label_n_counts(notes: list) -> dict:
    """
    note 리스트를 입력받아 (pitch, length) 튜플을 pitch, length 오름차순으로 정렬한 후,
    각 튜플의 빈도수를 세어 오름차순으로 레이블링하는 함수입니다.

    Args:
        notes (list): (start, pitch, end) 튜플을 요소로 갖는 리스트

    Returns:
        dict: (pitch, length) 튜플을 키로 하고, 오름차순으로 부여된 레이블을 값으로 하는 딕셔너리.
    """

    # (pitch, length) 조합을 만들고, 빈도수를 계산합니다.
    pitch_length = []
    for start, pitch, end in notes:
        length = end - start
        pitch_length.append((pitch, length))
    notes_counts = Counter(pitch_length)

    # (pitch, length) 튜플을 pitch, duration 오름차순으로 정렬
    sorted_pitches = sorted(notes_counts.items(), key=lambda item: (item[0][0], item[0][1]))

    # 레이블 딕셔너리 생성
    notes_label = {}
    label = 1  # 레이블 시작 번호
    for pitch_tuple, _ in sorted_pitches:  # 빈도수는 사용하지 않으므로 _로 받음
        notes_label[pitch_tuple] = label
        label += 1

    return notes_label, notes_counts

def find_multilength_pitches(combination_counts):
  """
  (pitch, length) 튜플을 키로 하고 등장 횟수를 값으로 갖는 Counter 객체를 받아
  서로 다른 length를 갖는 조합으로 2번 이상 등장한 pitch를 찾습니다.

  Args:
    combination_counts: (pitch, length) 튜플을 키로 하고 등장 횟수를 값으로 갖는 Counter 객체입니다.

  Returns:
    서로 다른 length를 갖는 조합으로 2번 이상 등장한 pitch를 키로 하고, 해당 pitch가 등장한 총 횟수를 값으로 갖는 딕셔너리입니다.
  """

  # pitch만 추출하여 각 pitch의 등장 횟수를 계산합니다.
  pitches = [pitch for (pitch, length), count in combination_counts.items()]
  pitch_counts = Counter(pitches)

  # 2번 이상 등장한 pitch만 필터링합니다.
  frequent_pitches = {
      pitch: count for pitch, count in pitch_counts.items() if count >= 2
  }

  return frequent_pitches

def get_flexible_pitches(notes_counts, notes_label, log : bool = True) :

    frequent_pitches = find_multilength_pitches(notes_counts)

    frequent_labels = []
    for note in notes_label.keys():
        pitch, length = note
        if pitch in frequent_pitches.keys() :
            frequent_labels.append(notes_label[note])
    if log :
        print(f"multilength pitch : its cardinality -> {frequent_pitches}")
        print(f"labels of notes whose pitch is of multilength : {frequent_labels}")

    frequent_notes = dict()
    for key, value in notes_label.items():
      for frequent_label in frequent_labels :
        if value == frequent_label :
        #   print(f"{key} : {frequent_label}")
          frequent_notes[frequent_label] = key

    return frequent_notes

def transform_dict(original_dict, project : bool = False):
    new_dict = {}
    if project :
        for key, value in original_dict.items():
            # pitch를 pitch-class로 환원
            pitch_classes = set()
            for pitch, _ in key:
                pitch_class = pitch % 12
                pitch_classes.add(pitch_class)

            # pitch_classes를 frozenset으로 만들어서 key로 사용
            new_key = set(pitch_classes)
            new_dict[value] = new_key

    else :
        for key, value in original_dict.items():
            # pitch를 pitch-class로 환원
            pitches = set()
            for pitch, _ in key:
                pitches.add(pitch)

            new_key = set(pitches)
            new_dict[value] = new_key

    return new_dict

def simul_chord_lists(list1, list2):
    """
    두 리스트를 받아 None 값을 제외하고 같은 인덱스의 요소들을 묶어 리스트를 반환합니다.

    Args:
        list1: 첫 번째 리스트 (None 값이 없음).
        list2: 두 번째 리스트 (None 값을 포함할 수 있음).

    Returns:
        None 값을 제외하고 같은 인덱스의 요소들을 묶은 리스트.
    """
    result = []
    # empty_1 = []
    # empty_2 = []
    for i in range(len(list1)):
        if (list1[i] is not None) and (list2[i] is not None):
            result.append([list1[i], list2[i]])
        elif list1[i] is None:
            # empty_1.append(i)
            result.append([list2[i]])
        elif list2[i] is None:
            # empty_2.append(i)
            result.append([list1[i]])
        else :
            print("really??")
    return result #, empty_1, empty_2

def label_simul_chords_combi(input_list):
    """
    입력 리스트의 각 요소를 set으로 변환하고, 처음 등장하는 순서대로 라벨링하는 함수입니다.

    Args:
        input_list: 라벨링할 리스트.

    Returns:
        dict: set을 키로, 라벨을 값으로 가지는 딕셔너리.
    """

    label_dict = {}  # 라벨을 저장할 딕셔너리
    label_counter = 0  # 라벨 카운터

    for item in input_list:
        # 리스트의 각 요소를 set으로 변환
        item_set = frozenset(item)  # set은 mutable이므로 frozenset 사용

        # set이 딕셔너리에 없는 경우, 라벨을 할당
        if item_set not in label_dict:
            label_dict[item_set] = label_counter
            label_counter += 1

    return label_dict

def create_instrument_part(instrument_notes, instrument_number, tempo_bpm, start_offset):
    """정제된 음표 리스트를 music21 Stream으로 변환하여 악기별 파트를 생성합니다."""

    # Stream 객체 생성
    p = stream.Part()
    p.id = f"Instrument {instrument_number}"
    p.insert(0, instrument.Instrument(instrumentNumber=instrument_number))  # 악기 정보 설정
    p.insert(0, meter.TimeSignature('4/4'))  # 4/4 박자
    p.insert(0, clef.TrebleClef())

    # 템포 설정 (MetronomeMark 객체 사용)
    mm = tempo.MetronomeMark(number=tempo_bpm)
    p.insert(0, mm)

    # 음표들을 시작 시간을 기준으로 그룹화하여 화음 처리
    notes_by_start_time = {}
    for start_eighth, pitch, end_eighth in instrument_notes:  # notes는 리스트, 각 요소는 튜플
        if start_eighth not in notes_by_start_time:
            notes_by_start_time[start_eighth] = []
        notes_by_start_time[start_eighth].append((pitch, end_eighth))

    # 모든 가능한 시작 시간 생성 (0부터 가장 늦은 end_eighth - 1까지)
    max_end_eighth = max(end_eighth for _, _, end_eighth in instrument_notes)
    all_possible_start_times = list(range(max_end_eighth))
    # print(max_end_eighth)
    # print(all_possible_start_times)

    # 활성화된 음을 추적하기 위한 set
    # active_notes = set()

    # 쉼표와 음표를 Stream에 추가
    for start_eighth in all_possible_start_times:
        # 현재 시간에 활성화된 음이 있는지 확인
        is_active = False
        for start, pitch, end in instrument_notes:
            if start <= start_eighth < end:
                is_active = True
                break

        # 활성화된 음이 없으면 쉼표 추가
        if not is_active:
            # print(f"    Instrument {instrument_number}: Adding rest at start_eighth: {start_eighth}")
            r = note.Rest()
            r.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
            r.quarterLength = 0.5  # 8분음표 길이
            p.append(r)
        else:
            # 해당 시작 시간에 음표가 있는지 확인
            if start_eighth in notes_by_start_time:
                note_info_list = notes_by_start_time[start_eighth]
                if len(note_info_list) > 1:  # 화음인 경우
                    # 화음 구성 음표들을 생성
                    chord_notes = []
                    for pitch, end_eighth in note_info_list:
                        n = note.Note()  # 노트 객체 먼저 생성
                        n.pitch.midi = pitch  # pitch 값 설정
                        duration_eighth = (end_eighth - start_eighth) / 2
                        # 최소 지속 시간 제한 (1/128분음표)
                        # if duration_eighth < 1/128:
                            # duration_eighth = 1/128
                        n.quarterLength = float(duration_eighth)  # quarterLength 값 명시적 타입 변환
                        chord_notes.append(n)

                    # 화음 생성 및 위치 설정
                    c = chord.Chord(chord_notes)
                    c.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
                    p.append(c)
                    # print(f"    Instrument {instrument_number}: Adding chord at start_eighth: {start_eighth}")
                else:  # 단일 음표인 경우
                    pitch, end_eighth = note_info_list[0]
                    n = note.Note()  # 노트 객체 먼저 생성
                    n.pitch.midi = pitch  # pitch 값 설정
                    duration_eighth = (end_eighth - start_eighth) / 2
                    # 최소 지속 시간 제한 (1/128분음표)
                    # if duration_eighth < 1/128:
                        # duration_eighth = 1/128
                    n.quarterLength = float(duration_eighth)  # quarterLength 값 명시적 타입 변환
                    n.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
                    p.append(n)
                    # print(f"    Instrument {instrument_number}: Adding note at start_eighth: {start_eighth}")
            else:
                # 해당 시작 시간에 음표가 없지만 활성화된 음이 있는 경우 (지속되는 음)
                pass  # 아무것도 하지 않음 (이미 이전 음표에 의해 처리됨)

    return p

def notes_to_score_xml(notes, tempo_bpm=66, file_name="temp_score", output_dir = "./"):
    """정제된 음표 리스트를 music21 Stream으로 변환하고 MusicXML 파일로 저장합니다."""

    # 전체 Stream 객체 생성
    s = stream.Score()

    # 악기별 Stream 객체 생성 및 전체 Stream에 추가
    instrument_streams = []
    for i, instrument_notes in enumerate(notes):  # instruments 개수만큼 반복
        p = create_instrument_part(instrument_notes, i + 1, tempo_bpm, start_offset = notes[0][0][0])
        instrument_streams.append(p)
        s.append(p)

    # MusicXML 파일로 저장
    musicxml_file = os.path.join(output_dir, f'{file_name}.musicxml')    # 디렉토리 경로와 파일 이름을 결합하여 전체 파일 경로 생성

    # 디렉토리가 존재하지 않으면 생성
    os.makedirs(output_dir, exist_ok=True)  # exist_ok=True: 이미 존재하면 에러 발생 X

    s.write('musicxml', fp=musicxml_file)
    print(f"MusicXML 파일이 저장되었습니다: {musicxml_file}")

    return s

def cycle_scattered_after_scaled(for_score, hibari_lists : list[list[tuple]], notes_label, frequent_notes):
    """
    특정 사이클에 해당하는 음표 데이터를 추출합니다.
    frequent_notes 정보를 활용하여 음표의 길이까지 고려합니다.

    Args:
        for_score (tuple) : search_optimal_threshold 3번째 리턴값 : (cycle, con_indices, scale)
        # adn_1_real (list): 음표 정보가 담긴 리스트 (튜플의 리스트).
        hibari_lists : [adn_1_real, adn_2_real]
        notes_label (dict): 음표 레이블 정보가 담긴 딕셔너리,  notes_label_n_counts 리턴값
        frequent_notes (dict): 빈번하게 나타나는 음표의 길이 정보 (딕셔너리).
        # cycle_idx (int): 추출할 사이클의 인덱스 .

        수정)
        for_scores 전체를 입력받는 것에서 특정 사이클에 대한 것만 각각 입력받는 걸로 : 반복문 간단화를 위해

    Returns:
        list: 추출된 음표 데이터 리스트. 각 요소는 (start, pitch, end) 튜플입니다.
    """

    try:
        # 1. 사이클에 해당하는 음표 레이블 찾기
        cycle_labels = for_score[0]  # 사이클에 속하는 레이블 (예: [1, 2, 3, 19, 6])

        # 2. 음표 종류별로 분리 (multilength vs singlelength)
        cycle_notes_multilength = set()
        cycle_pitches_singlelength = set()

        for key, value in notes_label.items():
            if value in cycle_labels:
                if key in frequent_notes.values():  # 튜플 전체를 비교
                    cycle_notes_multilength.add(key)
                else:
                    cycle_pitches_singlelength.add(key[0])

        # if cycle_notes_multilength :
        #     print(f"multilength notes in the cycle {cycle_notes_multilength}")

        # 3. 모든 occurrence에 대해 사이클이 나타나는 인덱스 범위
        all_con_indices = for_score[1]  # 모든 occurrence 고려

        # 4. adn_i_real (i= 1, 2) 에서 해당 음표 및 인덱스 범위에 해당하는 데이터 추출
        scaled_cycle = []
        for adn_i_real in hibari_lists :
            scaled_cycle_i = []
            for start, pitch, end in adn_i_real:
                duration = end - start

                # Multilength 음표 처리
                if (pitch, duration) in cycle_notes_multilength:
                    for con_indices in all_con_indices:
                        if start in con_indices:
                            scaled_cycle_i.append((start, pitch, end))
                            break  # 해당 occurrence에서 찾았으면 다음 음표로 넘어감

                # Singlelength 음표 처리
                elif pitch in cycle_pitches_singlelength:
                    for con_indices in all_con_indices:
                        if start in con_indices:
                            scaled_cycle_i.append((start, pitch, end))
                            break  # 해당 occurrence에서 찾았으면 다음 음표로 넘어감

            scaled_cycle.append(scaled_cycle_i)

        return scaled_cycle

    # except KeyError as e:
    #     print(f"Error: cycle_idx {cycle_idx} not found in for_scores. {e}")
    #     return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

def get_hibari_notes(adn_1_whole_c, adn_2_whole_c, notes_dict) :

    inst1_notes = specify_chord_list2(adn_1_whole_c, notes_dict)
    inst2_notes = specify_chord_list2(adn_2_whole_c, notes_dict)
    hibari_notes = list(zip(inst1_notes, inst2_notes)) 

    return hibari_notes

def analyze_scale_reduction(cycles_weak, overlapped_cycles, goal) :

    before_on = cycles_weak.sum().sum() / (46*1088)
    after_on = overlapped_cycles.sum().sum() / (46*1088)
    print(f"for hibari scores, ON ratio was originally {round( 100 * before_on, 2)}%")
    print(f"which decreased to {round(100 * after_on, 2)}% after applying cyclewise scale\n")

    actual_on = after_on / before_on
    print(f"it amounts to {round(100 * (1 - actual_on), 2)}% reduction")
    print(f"while it was {round(100 * (1 - goal), 2)}% that i tried")

    return actual_on

def verify_cycles_scaled_by_scores(hibari_lists : list[list], cycle_labeled : dict, for_scores : dict, indices_2_check : list[int] | None,
                                    notes_label : dict, flexible_pitches : dict,
                                    output_dir : str = "./test_xml", type : str = 't') :

    """ 
     hibari_lists = [adn_1_real, adn_2_real]
     cycle_labeled : label_cycle 첫번째 리턴값
     for_scores : evaluate_threshold 두번째 리턴값
     notes_label : notes_label_n_counts 첫번째 리턴값
     flexible_pitches : get_flexible_pitches 리턴값
        """

    # musicxml_files = []
    cycles_scaled = []
    if not indices_2_check :
        for cycle_idx in cycle_labeled.keys():
            print(f"{cycle_idx+1} / {len(cycle_labeled)}")
            for_score = for_scores[cycle_idx]
            cycle_scaled = cycle_scattered_after_scaled(for_score, hibari_lists, notes_label, flexible_pitches)
            musicxml_file = notes_to_score_xml(cycle_scaled, 
                                            file_name=f"{type}{cycle_idx}. {for_score[0]} on scale {for_score[2]}",
                                            output_dir = output_dir)

            # musicxml_files.append(musicxml_file)
            cycles_scaled.append(cycle_scaled)

    else :
        for cycle_idx in indices_2_check:
            print(f"cycle of index {cycle_idx} :")
            for_score = for_scores[cycle_idx]
            cycle_scaled = cycle_scattered_after_scaled(for_score, hibari_lists, notes_label, flexible_pitches)
            musicxml_file = notes_to_score_xml(cycle_scaled, 
                                            file_name=f"{type}{cycle_idx}. {for_score[0]} on scale {for_score[2]}",
                                            output_dir = output_dir)

            # musicxml_files.append(musicxml_file)
            cycles_scaled.append(cycle_scaled)

    return cycles_scaled



