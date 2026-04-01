# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install mido
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install pretty_midi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install gudhi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install librosa
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install tqdm
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install tabulate



import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx

import numpy as np
import math
import pandas as pd

from collections import defaultdict
from collections import Counter

import itertools
import re


import gudhi
from sklearn.decomposition import PCA
from scipy.interpolate import CubicSpline
from scipy.linalg import null_space

from tqdm import tqdm


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

        return adjusted_notes

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
    pitch_length_combinations = []
    for start, pitch, end in notes:
        length = end - start
        pitch_length_combinations.append((pitch, length))
    notes_counts = Counter(pitch_length_combinations)

    # (pitch, length) 튜플을 pitch, duration 오름차순으로 정렬
    sorted_pitches = sorted(notes_counts.items(), key=lambda item: (item[0][0], item[0][1]))

    # 레이블 딕셔너리 생성
    notes_label = {}
    label = 1  # 레이블 시작 번호
    for pitch_tuple, _ in sorted_pitches:  # 빈도수는 사용하지 않으므로 _로 받음
        notes_label[pitch_tuple] = label
        label += 1

    return notes_label, notes_counts
# _, notes_freq = notes_label_n_counts(adjusted_notes_real)
# frequent_pitches = find_multilength_pitches(notes_freq)
# print("\n서로 다른 length를 갖는 조합으로 2번 이상 등장한 Pitches:")
# frequent_pitches

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
