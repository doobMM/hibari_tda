# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install mido
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install pretty_midi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install gudhi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install librosa
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install tqdm

import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import numpy as np
from numpy.polynomial import Polynomial
import pandas as pd

from collections import defaultdict

import itertools

from sklearn.decomposition import PCA
from scipy.interpolate import CubicSpline

from gtda.homology import VietorisRipsPersistence
from gtda.time_series import SingleTakensEmbedding
from gtda.plotting import plot_point_cloud
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

def group_pitches_with_duration(note_list : list) -> dict:
    """
    노트 리스트를 순회하며, 각 start 시간에 해당하는 (pitch, duration) 정보를 set으로 묶고,
    이전 노트의 지속 시간 내에 있는 pitch 정보도 포함합니다.

    Args:
        note_list (list): (start, pitch, end) 튜플을 요소로 갖는 리스트.

    Returns:
        dict: start 값을 키로 하고 (pitch, duration) 튜플의 set을 값으로 갖는 딕셔너리.
    """

    result = {}
    active_pitches = {}  # 현재 활성화된 pitch 정보 (pitch: end 시간)

    for start, pitch, end in note_list:
        duration = end - start

        # 현재 시간에 활성화된 pitch 추가
        if start not in result:
            result[start] = set()

        result[start].add((pitch, duration))

        # active_pitches 업데이트
        active_pitches[pitch] = end

        # 이전 노트 중 지속 시간 내에 있는 pitch 추가
        for prev_pitch, prev_end in list(active_pitches.items()):
            if prev_end > start and prev_pitch != pitch:  # 이전 노트가 아직 지속 중이고, 현재 pitch와 다른 경우
                if start not in result:
                    result[start] = set()

                result[start].add((prev_pitch, prev_end - start))  # 지속 시간 갱신

        # 현재 노트 이후에 끝나는 활성화된 pitch 정보만 남김
        active_pitches = {
            p: e for p, e in active_pitches.items() if e > start
        }

    return result

def fill_duration_indices(result : dict) -> dict:
    """
    result 딕셔너리의 비어있는 인덱스를 이전 음의 지속 시간을 기준으로 채웁니다.
    엄격한 지속 시간 제한과 디버깅 출력을 포함합니다.

    Args:
        result (dict): start 값을 키로 하고 (pitch, duration) 튜플의 set을 값으로 갖는 딕셔너리.

    Returns:
        dict: 비어있는 인덱스가 채워진 result 딕셔너리.
    """

    min_index = min(result.keys())
    max_index = max(result.keys())  # 딕셔너리에서 가장 큰 인덱스
    filled_result = result.copy()  # 원본 딕셔너리를 복사하여 수정

    last_valid_pitch_set = None
    last_valid_start_index = None  # 마지막 유효한 pitch_set이 시작된 인덱스

    for i in range(min_index, max_index + 5, 1):

        if i in filled_result:
            last_valid_pitch_set = filled_result[i]
            last_valid_start_index = i
        else:
            # print(f"인덱스: {i}")
            # print("  - 값이 없음")

            if last_valid_pitch_set is not None:
                can_copy = True  # 복사 가능 여부를 나타내는 변수
                for pitch, duration in last_valid_pitch_set:
                    if last_valid_start_index + duration <= i:  # 지속 시간이 i 이전에 끝난다면
                        can_copy = False
                        # print(f"    - 복사 불가능: 지속 시간 만료 (시작: {last_valid_start_index}, 지속: {duration}, 현재: {i})")
                        break

                if can_copy:
                    filled_result[i] = last_valid_pitch_set
                    # print(f"    - 복사: {last_valid_pitch_set}")
                # else:
                    # print("    - 복사 안 함 (지속 시간 초과)")
            # else:
                # print("    - 복사 안 함 (이전 유효한 pitch_set 없음)")

    # print("---- 종료 ----")
    return filled_result

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

def label_active_chord_by_onset(adjusted_note : list) -> list :

    # 1-1. onset이 존재하는 start 지점에서 지속되고 있는 chord 고려
    result = group_pitches_with_duration(adjusted_note)

    # 1-2. onset만을 고려하면서 누락된 부분까지 채우기 
    result_ = fill_duration_indices(result)

    # 2-1. (chord_set-label) 딕셔너리 만들기
    set_labels = {}
    label_counter = 0
    for pitch_set in result_.values():
        # frozenset을 사용하여 set을 hashable하게 만들기
        frozen_set = frozenset(pitch_set)  
        if frozen_set not in set_labels:
            set_labels[frozen_set] = label_counter
            label_counter += 1


    # 2-2. result_의 chord set들을 label에 매핑
    mapped_result = {}
    for start, pitch_set in result_.items():
        frozen_set = frozenset(pitch_set)
        mapped_result[start] = set_labels[frozen_set]


    # 2-3. onset이 없어서 비어있는 중간에 비어있는 인덱스는 None으로 채우기
    mapped_result_ = fill_missing_indices_with_none(mapped_result)

    # 3. list로 변환
    onset_chord_list = list(mapped_result_.values())

    return onset_chord_list

# none_keys = [key for key, value in mapped_result_.items() if value is None]
# for rest in none_keys :
#     print(rest%32)

def compare_lists(a : list, b : list, lag : int) -> np.ndarray :
    """
    두 리스트 a와 b를 비교하여 17x17 2차원 배열을 업데이트합니다.

    Args:
        a: 첫 번째 리스트 (adn_1_chord_).
        b: 두 번째 리스트 (adn_2_chord_). 반드시 맞춰서 넣어야 함.
        lag : 어떤 간격으로 이웃한 값끼리 값을 가중치를 구할지

    Returns:
        17x17 numpy 배열.  a[i][j]는 (i,j) 쌍의 발생 횟수를 나타냅니다.
    """

    j = lag

    # 17x17 배열 초기화 (모든 값은 0)
    result_array = np.zeros((17, 17), dtype=int)

    # i를 0부터 1022까지 반복
    for i in range(len(a) - j):  # i는 0부터 1022 - j까지 (마지막 i+j가 1022이므로)
        # None 값 확인
        if b[i+j] is None :
            continue
        else :
            val_a_i = a[i]
            val_b_i_plus_j = b[i+j]
            # 배열 업데이트 (유효한 값만 더하기)
            result_array[val_a_i][val_b_i_plus_j] += 1
        
        if b[i] is None: # None이 있으면 다음 반복으로 넘어감
            continue  
        else :
            # 값 가져오기
            val_a_i_plus_j = a[i+j]
            val_b_i = b[i]
            result_array[val_a_i_plus_j][val_b_i] += 1

    return result_array
