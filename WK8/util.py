# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install mido
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install pretty_midi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install gudhi
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install librosa
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install tqdm
# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install dionysus

import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx

import numpy as np
from numpy.polynomial import Polynomial
import math
import pandas as pd

from collections import defaultdict
from collections import Counter

import itertools

import gudhi
from sklearn.decomposition import PCA
from scipy.interpolate import CubicSpline
from scipy.linalg import null_space

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

def group_pitches_with_duration_(note_list: list) -> dict:
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
    result = group_pitches_with_duration_(adjusted_note)

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

# none_keys = [key for key, value in mapped_result_.items() if value is None]
# for rest in none_keys :
#     print(rest%32)

def get_chords_inter_connected(a : list, b : list, lag : int) -> np.ndarray :
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
            # result_array[val_a_i_plus_j][val_b_i] += 1 # 250328 1627 수정
            result_array[val_b_i][val_a_i_plus_j] += 1

    result_df = pd.DataFrame(result_array)

    return result_df

def get_chords_intra_connected(a : list, lag = 1) -> np.ndarray :
    """
    리스트 a를 사용하여 17x17 2차원 배열을 업데이트합니다.
    리스트 내에서 이웃하는 두 값이 다를 때만 count합니다.

    Args:
        a: 입력 리스트.
        lag : 어떤 간격으로 이웃한 값끼리 값을 가중치를 구할지

    Returns:
        17x17 numpy 배열.  a[i][j]는 (i,j) 쌍의 발생 횟수를 나타냅니다 (단, i != j인 경우).
    """

    j = lag

    # 17x17 배열 초기화 (모든 값은 0)
    result_array = np.zeros((17, 17), dtype=int)

    # i를 0부터 len(a) - j - 1 까지 반복
    for i in range(len(a) - j):
        # None 값 확인
        if a[i] is None or a[i+j] is None:
            continue  # None이 있으면 다음 반복으로 넘어감

        # a[i]와 a[i+j]가 다를 경우에만 count
        if a[i] != a[i+j]:
            # print(a[i], a[i+j])
            result_array[a[i]][a[i+j]] += 1
            # result_array[a[i+j]][a[i]] += 1

    result_df = pd.DataFrame(result_array)

    return result_df

def get_asymmetric_indices_(df: pd.DataFrame) -> list:
    """
    비대칭 인덱스를 찾습니다 (인덱스가 연속적이지 않은 DataFrame에 적용 가능).

    Args:
        df (pd.DataFrame): 입력 DataFrame.

    Returns:
        list: 비대칭 인덱스 리스트 (df[i, j] != df[j, i]인 (i, j) 튜플).
    """

    non_symmetric_indices = []
    row_indices = df.index.tolist()  # 행 인덱스를 리스트로 변환
    col_indices = df.columns.tolist()  # 열 인덱스를 리스트로 변환

    for i in range(len(row_indices)):
        for j in range(i + 1, len(col_indices)):  # j는 i + 1부터 시작
            row_idx = row_indices[i]  # 실제 행 인덱스
            col_idx = col_indices[j]  # 실제 열 인덱스

            if df.loc[row_idx, col_idx] != df.loc[col_idx, row_idx]:
                non_symmetric_indices.append((row_idx, col_idx))

    # 결과 출력
    # print("비대칭 인덱스 (df[i, j] != df[j, i], 중복 없음):")
    return non_symmetric_indices

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

def refine_connectedness(weight_mtrx, transformed_dict):
    """
    weight_mtrx 데이터프레임을 순회하면서 transformed_dict를 이용하여
    새로운 weight_mtrx_notes 데이터프레임을 생성합니다.

    Args:
        weight_mtrx (pd.DataFrame): 원본 weight_mtrx 데이터프레임.
        transformed_dict (dict): 변환된 딕셔너리 (key는 label, value는 frozenset).

    Returns:
        pd.DataFrame: 새로운 weight_mtrx_notes 데이터프레임.
    """

    all_values = set()
    # for value in transformed_dict.values():
    #     all_values.update(value)

    for key, value in transformed_dict.items():
        if isinstance(key, int):  # 정수형 키를 가진 딕셔너리인지 확인
            all_values.update(value)  # 해당 딕셔너리의 값들만 추가
        # else:
            # print(f"Skipping non-integer key: {key}")  # 로그 출력 (선택 사항)

    # 2. all_values를 정렬된 리스트로 변환합니다. (DataFrame의 index/columns 순서 유지를 위해)
    unique_values = sorted(list(all_values))

    # 3. DataFrame을 생성합니다. index 및 columns에 고유한 값들을 설정합니다.
    weight_mtrx_refiined = pd.DataFrame(0, index=unique_values, columns=unique_values, dtype=np.float64)

    # weight_mtrx 순회
    for i in range(weight_mtrx.shape[0]):
        for j in range(weight_mtrx.shape[1]):
            weight = weight_mtrx.iloc[i, j]  # 현재 weight 값

            # transformed_dict에서 i와 j에 해당하는 frozenset 가져오기
            notes_i = transformed_dict.get(i)
            notes_j = transformed_dict.get(j)

            # notes_i와 notes_j의 모든 조합에 대해 weight 더하기
            for note_i in notes_i:
                for note_j in notes_j:
                    if note_j >= note_i: # 250328 1747 추가된 부분
                        weight_mtrx_refiined.loc[note_i, note_j] += weight  # weight_mtrx_refiined 업데이트
                        # print(f"weight_mtrx_refined[{note_i}, {note_j}] += {weight} (= weight_mtrx[{i}, {j}])") #디버깅용

    return weight_mtrx_refiined

def get_distance_matrix_from(weighted_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    가중치 행렬을 입력받아 거리 행렬을 계산합니다.
    가중치 행렬의 값이 0인 경우, 거리 행렬의 해당 값을 무한대(np.inf)로 설정합니다.
    0이 아닌 값에 대해서만 역수를 취하여 계산 효율성을 높입니다.

    Args:
        weighted_matrix: 가중치 행렬 (pandas DataFrame).

    Returns:
        거리 행렬 (pandas DataFrame).
    """

    distance_matrix = weighted_matrix.copy().astype(float)  # 원본 DataFrame 복사 및 dtype을 float으로 변환

    # 0인 값을 np.inf로 대체
    # distance_matrix[weighted_matrix == 0] = np.inf
    distance_matrix[weighted_matrix == 0] = 1

    # 0이 아닌 값에 대해서만 역수 변환
    non_zero_mask = weighted_matrix != 0  # 0이 아닌 값에 대한 boolean mask 생성
    # print(non_zero_mask)
    distance_matrix[non_zero_mask] = 1 / distance_matrix[non_zero_mask]  # 0이 아닌 값에 대해서만 역수 계산

    return distance_matrix

def get_UTMconnected(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame의 하삼각 요소를 상삼각 요소에 더하고, 하삼각 요소를 0으로 만듭니다.

    Args:
        df: 입력 DataFrame (인덱스와 컬럼명이 일치해야 함).

    Returns:
        대칭화된 DataFrame.
    """
    
    for i in df.index:
        for j in df.columns:
            if i > j:  # j가 i보다 큰 경우 (상삼각 요소)
                df.loc[j, i] += df.loc[i, j]
                df.loc[i, j] = 0

    return df

def get_LTMpart_of(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame의 상삼각 요소 값을 하삼각 요소에 대칭적으로 복사합니다.
                is_distance_matrix_from의 출력값

    Args:
        df: 입력 DataFrame (인덱스와 컬럼명이 일치해야 함).

    Returns:
        상삼각 요소 값이 하삼각 요소에 복사된 새로운 DataFrame.
    """

    # 입력 DataFrame을 복사하여 새로운 DataFrame 생성 (원본 변경 방지)
    new_df = df.copy()

    for i in new_df.index:
        for j in new_df.columns:
            if i > j:  # i가 j보다 큰 경우 (하삼각 요소)
                new_df.loc[i, j] = new_df.loc[j, i]  # 상삼각 요소 값을 하삼각 요소에 복사

    return new_df

def is_distance_matrix_from(weight_mtrx, transform_dict) : 
    """
    MIDI 파일에서 음표의 start와 end를 8분음표 단위로 조정합니다.

    Args:
        weight_mtrx (pd.DataFrame): get_chords_inter_connected의 리턴값
        transform_dict (dict) : chord_to_notes_dict | pitches_dict | pitch_classes_dict

    Return:
        transform_dict의 관점에서 도출된 거리 데이터프레임
    """
    # lower triangle에 있는 비대각원소를 UT로 옮깁니다(더한 뒤 0으로 만듭니다) 
    weight_UTM = get_UTMconnected(weight_mtrx)
    
    # 화음 단위에서 notes(pitch, length) | pitch | pitch_classes 기준으로 weight를 refine합니다
    refined_UTM = refine_connectedness(weight_UTM, transform_dict)
    
    # 역수 변환
    distance_UTM = get_distance_matrix_from(refined_UTM)

    distance_df = get_LTMpart_of(distance_UTM)

    return distance_df

def replace_with_label(data_set: list[set], distance_df: pd.DataFrame):
    indices = list(distance_df.index)
    
    new_set = set()
    for item in data_set:
        if isinstance(item, tuple):  # 튜플인 경우 (edge 정보)
            new_tuple = tuple(indices[i] if 0 <= i < len(indices) else f"Invalid({i})" for i in item)
            new_set.add(new_tuple)
        elif isinstance(item, int):  # 단일 정수인 경우 (vertex 정보)
            if 0 <= item < len(indices):
                new_set.add(indices[item])
            else:
                print(f"Warning: Index {item} is out of range.")
        else:
            print(f"Warning: Unsupported type {type(item)} in data_set.")

    return new_set

def plot_dist_distr(distance_df : pd.DataFrame, figsize : tuple = (6, 3)) :

    plt.figure(figsize=figsize)  # 그래프 크기 설정
    sns.histplot(distance_df.values.flatten(), kde=True)  # 히스토그램 그리기, kde는 밀도 추정 곡선
    plt.title("Distance Matrix Value Distribution")
    plt.xlabel("Distance Value")
    plt.ylabel("Frequency")
    plt.show()

def plot_tda_statistics(distance_df : pd.DataFrame, persistence, 
                    dist_distr : bool, barcode : bool, PD : bool) :
    
    if dist_distr :
        plot_dist_distr(distance_df)

    if barcode : # Barcode 그리기
        gudhi.plot_persistence_barcode(persistence)
        plt.title("Barcode")
        plt.xlabel("Birth-Death Time")
        plt.ylabel("Homology Dimension")
        plt.show()

    if PD : # Persistence Diagram 그리기
        gudhi.plot_persistence_diagram(persistence)
        plt.title("Persistence Diagram")
        plt.xlabel("Birth Time")
        plt.ylabel("Death Time")
        plt.show()

def find_non_triangle_inequality(distance_matrix, noneuclidean_ratio : bool = True):
    """
    Distance matrix에서 triangle inequality를 만족하지 않는 index 3쌍을 탐색하고,
    각 세변의 길이와 어디서 triangle inequality를 만족하지 못하는지 출력합니다.

    Args:
        distance_matrix (pd.DataFrame): Distance matrix (DataFrame)

    Returns:
    """

    non_triangle_inequality_triples = []
    index_list = list(distance_matrix.index)  # DataFrame의 index 리스트
    num_indices = len(index_list)

    # 모든 가능한 index 3쌍을 탐색
    for i in range(num_indices):
        for j in range(i + 1, num_indices):
            for k in range(j + 1, num_indices):
                # index 값 가져오기
                idx1 = index_list[i]
                idx2 = index_list[j]
                idx3 = index_list[k]

                # triangle inequality 확인
                d_ij = distance_matrix.loc[idx1, idx2]
                d_ik = distance_matrix.loc[idx1, idx3]
                d_jk = distance_matrix.loc[idx2, idx3]

                # # 거리 중 하나라도 np.inf면 해당 조합은 고려하지 않음
                # if np.isinf(d_ij) or np.isinf(d_ik) or np.isinf(d_jk):
                #     continue

                # triangle inequality를 만족하지 않는 경우 triple 추가
                violation_message = None
                if d_ij + d_jk < d_ik:
                    violation_message = f"{idx1}-{idx2} + {idx2}-{idx3} < {idx1}-{idx3} ({d_ij:.4f} + {d_jk:.4f} < {d_ik:.4f})"
                elif d_ij + d_ik < d_jk:
                    violation_message = f"{idx1}-{idx2} + {idx1}-{idx3} < {idx2}-{idx3} ({d_ij:.4f} + {d_ik:.4f} < {d_jk:.4f})"
                elif d_ik + d_jk < d_ij:
                    violation_message = f"{idx1}-{idx3} + {idx2}-{idx3} < {idx1}-{idx2} ({d_ik:.4f} + {d_jk:.4f} < {d_ij:.4f})"

                if violation_message:
                    non_triangle_inequality_triples.append((idx1, idx2, idx3, d_ij, d_ik, d_jk, violation_message))

                    # # num_triples이 None이 아니면, 원하는 개수만큼 찾았는지 확인
                    # if num_triples is not None and len(non_triangle_inequality_triples) >= num_triples:
                    #     return non_triangle_inequality_triples

    if noneuclidean_ratio :
        total_triples = num_indices * (num_indices - 1) * (num_indices - 2) // 6 
        return len(non_triangle_inequality_triples) / total_triples
    else :
        return non_triangle_inequality_triples

def plot_d_edge_ratio(d_edge_ratios : list, refine_dict : dict, inter_lag : int) :

    x = [point[0] for point in d_edge_ratios]
    y = [point[1] for point in d_edge_ratios]

    plt.figure()  # 새로운 Figure 생성
    plt.plot(x, y)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("d_edge (noneuclidean) ratio")
    plt.show()

def plot_cycles_profile(cycles_profile : list, refine_dict : dict, inter_lag : int, loglog : bool) :

    x = [point[0] for point in cycles_profile]
    y1 = [point[1] for point in cycles_profile]
    y2 = [point[2] for point in cycles_profile]
    y3 = [point[3] for point in cycles_profile]
    y4 = [point[4] for point in cycles_profile]
    print("from cycles profile : ")

    # Y1 plot
    plt.figure()  # 새로운 Figure 생성
    plt.plot(x, y1)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Number of Cycles")
    plt.show()

    # Y2 plot
    plt.figure()  # 새로운 Figure 생성
    if loglog :
        plt.loglog(x, y2)
    else :
        plt.plot(x, y2)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Mean of Cycle Lifespans")
    plt.show()

    # Y3 plot
    plt.figure()  # 새로운 Figure 생성
    if loglog :
        plt.loglog(x, y3)
    else :
        plt.plot(x, y3)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Std Dev of Cycle Lifespans")
    plt.show()

    # Y4 plot
    plt.figure()  # 새로운 Figure 생성
    if loglog :
        plt.loglog(x, y4)
    else :
        plt.plot(x, y4)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Longest Cycle Lifespans")
    plt.show()

def plot_higher_homol(higher_homol : list, refine_dict : dict, inter_lag : int) :

    x_ = [point[0] for point in higher_homol]
    y1_ = [np.mean(point[1]) if len(point[1]) > 0 else 0 for point in higher_homol]
    y2_ = [np.mean(point[2]) if len(point[2]) > 0 else 0 for point in higher_homol]
    print("from higher homology profile : ")

    # Y1_ plot
    plt.figure()  # 새로운 Figure 생성
    plt.plot(x_, y1_)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Mean of 2d-homology persistence")
    plt.show()

    # Y2_ plot
    plt.figure()  # 새로운 Figure 생성
    plt.plot(x_, y2_)
    plt.title(f"refined by {refine_dict['name']}, lag = {inter_lag}")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("Mean of 3d-homology persistence")
    plt.show()

def get_unique_dist_n_diff(df : pd.DataFrame) :

    # 모든 열의 고유값을 하나의 리스트로 추출
    unique_values = df.values.flatten()  # 데이터프레임을 1차원 배열로 만듦
    unique_values = pd.unique(unique_values).tolist()  # 고유값 추출 후 리스트로 변환
    unique_values.sort()

    # 2. 인접한 값들의 차이 계산
    differences = []
    for i in range(1, len(unique_values)):
        difference = unique_values[i] - unique_values[i-1]
        differences.append(difference)

    return unique_values, differences

def cycle_detection(persistence, simplex_tree, distance_matrix, 
                    # tolerance=tolerance, max_edge_length = max_edge_length_, log=log):
                    tolerance=1e-10, max_edge_length = 1, log=False):

    """
    Persistent Homology 결과를 바탕으로 Cycle을 탐색하고, Cycle 관련 정보를 추출합니다.

    Args:
        persistence (list): Persistent Homology 결과
        simplex_tree (gudhi.SimplexTree): Simplex Tree
        distance_matrix (pd.DataFrame): Distance Matrix (DataFrame)
        max_edge_length (float): Vietoris-Rips 복합체의 최대 edge 길이
        tolerance (float): Cycle 탐색 시 허용 오차 범위
        log (bool): Cycle 탐색 과정 로그 출력 여부

    Returns:
        tuple: Cycle 관련 정보 (lifespan 리스트, cycle vertex 리스트, cycle birth time 리스트, cycle edge 리스트)
    """

    lifespans = []
    cycle_birth_times = [] 
    cycle_vertices = [] 
    cycle_edges_list = []

    index_map = list(distance_matrix.index)
    def convert_simplex(simplex):
        return tuple(index_map[i] for i in simplex)

    # 1차원 homology (cycle) 확인
    for dim, (birth, death) in persistence: 
        if dim == 1:

            G = nx.Graph()

            # 모든 가능한 엣지를 확인하고, 조건을 만족하는 엣지만 추가
            for u_idx in range(len(index_map)):
                for v_idx in range(u_idx + 1, len(index_map)): # 중복 방지
                    u = index_map[u_idx]
                    v = index_map[v_idx]
                    if distance_matrix.loc[u, v] <= birth + tolerance:
                        G.add_edge(u_idx, v_idx)  # 그래프에 엣지 추가 (index 사용)
                        if log:
                            print(f"edge of Cycle candidate: {convert_simplex((u_idx, v_idx))} with distance {distance_matrix.loc[u, v]}")

            # if simplex_tree.find([birth]) : 
            simplex_1d = []
            # simplex_tree에 있는 모든 simplex를 순회하며 birth time과 같은 simplex를 찾습니다.
            for simplex, fil_val in simplex_tree.get_skeleton(1): # 1차원 simplex만 확인
                if (abs(fil_val - birth) < tolerance) and (len(simplex) != 1) :
                    G.add_edge(*simplex)  # 그래프에 엣지 추가
                    if log :
                        simplex_1d.append(simplex)
                        print(f"edge of Cycle candidate: {convert_simplex(simplex)} with birth time {fil_val}")

            if log :
                simplex_1d = []
                simplex_2d = simplex_1d
                for simplex, fil_val in simplex_tree.get_skeleton(2):
                    if (abs(fil_val - birth) < tolerance) and (simplex not in simplex_1d):
                        print(f"2-simplex: {convert_simplex(simplex)} with birth time {fil_val}")
                        simplex_2d.append(simplex)

                simplex_3d = simplex_2d
                for simplex, fil_val in simplex_tree.get_skeleton(3):
                    if (abs(fil_val - birth) < tolerance) and (simplex not in simplex_2d):
                        print(f"3-simplex: {convert_simplex(simplex)} with birth time {fil_val}")
                        simplex_3d.append(simplex)

            cycles = list(nx.cycle_basis(G))
            if cycles :
                print(f"basis of cycles in G if only 1-simplexes inserted : {convert_simplex(cycles[0])}\n")

            # 4. Cycle vertex 추출
            for cycle in cycles:
                # Cycle vertex를 정렬하여 set으로 변환 후 비교
                cycle_vertex_set = frozenset(sorted(cycle))

                if cycle_vertex_set not in cycle_vertices :
                    cycle_vertices.append(cycle_vertex_set)
                    cycle_birth_times.append(birth)
                    
                    # 무한 death 값 처리
                    life = max_edge_length - birth if death == float('inf') else death - birth
                    lifespans.append(life)

                cycle_edges = set((cycle[i], cycle[i+1]) for i in range(len(cycle)-1))
                cycle_edges.add((cycle[-1], cycle[0]))  # 마지막과 첫 번째 노드를 연결
                cycle_edges_list.append(cycle_edges)

    return lifespans, cycle_vertices, cycle_birth_times, cycle_edges_list

def get_persistence(distance_df, max_edge_length : int, max_dimension : int):
    rips_complex = gudhi.RipsComplex(distance_matrix=distance_df.values, max_edge_length=max_edge_length)
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=max_dimension)  # 1차원 homology 계산을 위해 최대 2차원 설정
    persistence = simplex_tree.persistence() # Persistent Homology 계산

    return simplex_tree, persistence

# tolerance는 거리 간의 차이 중 가장 작은 것보다 조금 더 작게?
def get_cycle_from_distance(distance_df : pd.DataFrame, 
                            dist_distr = False, barcode = False, PD = False, 
                            max_edge_length_ = 1.0, tolerance=1e-10, log = False) : 
    
    """
    Distance Matrix로부터 1차원 호몰로지 (Cycle)를 추출하고, 관련 정보를 계산합니다.

    Args:
        distance_df (pd.DataFrame): Distance Matrix (DataFrame)
        max_edge_length_ (float): Vietoris-Rips 복합체의 최대 edge 길이
        tolerance (float): Cycle 탐색 시 허용 오차 범위
        log (bool): Cycle 탐색 과정 로그 출력 여부

    Returns:
        tuple: Cycle 관련 정보 (Cycle 개수, 평균 lifespan, 표준 편차 lifespan, 최대 lifespan, Cycle vertex, Cycle birth time, Cycle edge 리스트)
    """

    simplex_tree, persistence = get_persistence(distance_df, max_edge_length = max_edge_length_, max_dimension = 4)
        
    plot_tda_statistics(distance_df, persistence, dist_distr, barcode, PD)

    lifespans_1d = []
    lifespans_2d = []
    lifespans_3d = []
    cycle_birth_times = [] 

    for dim, (birth, death) in persistence: 
        if dim == 1:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_1d.append(life)
            cycle_birth_times.append(birth)

        if dim == 2:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_2d.append(life)

        if dim == 3:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_3d.append(life)

    cycle_count = len(lifespans_1d)
    mean = np.mean(lifespans_1d)
    std_dev = np.std(lifespans_1d)
    longest = max(lifespans_1d)

    # return cycle_count, mean, std_dev, longest, cycle_vertices, cycle_birth_times, cycle_edges_list
    return cycle_count, mean, std_dev, longest, cycle_birth_times, lifespans_2d, lifespans_3d

def visualize_cycles_at_birth(cycle_birth_times: list[float], cycle_edges_list: list[set[tuple[int, int]]],):
    
    for i, (birth_time, cycle_edges) in enumerate(zip(cycle_birth_times, cycle_edges_list)):
        G = nx.Graph()
        G.add_edges_from(cycle_edges)  # 정확한 cycle edge 추가

        plt.figure(figsize=(7, 5))
        pos = nx.spring_layout(G)

        # 노드와 엣지 시각화
        nx.draw_networkx_nodes(G, pos, node_color="skyblue", node_size=300)
        nx.draw_networkx_edges(G, pos, edgelist=cycle_edges, width=2, edge_color="black")
        nx.draw_networkx_labels(G, pos, font_size=12)

        plt.title(f"Graph at Cycle {i+1} (Birth Time: {birth_time:.5f})")
        plt.show()

def is_singular_by_determinant(df, tolerance=1e-8):
  """
  Pandas DataFrame이 singular한지 행렬식(determinant)을 사용하여 판단합니다.

  Args:
    df: Pandas DataFrame (실수 값을 원소로 가져야 함)
    tolerance: 행렬식의 절대값이 이 값보다 작으면 singular로 판단

  Returns:
    True: DataFrame이 singular함
    False: DataFrame이 singular하지 않음
  """
  matrix = df.values  # DataFrame을 NumPy 행렬로 변환
  if matrix.shape[0] != matrix.shape[1]:
    return True # 정방행렬이 아니면 singular

  try:
    determinant = np.linalg.det(matrix)
    return abs(determinant) < tolerance  # 행렬식의 절대값이 tolerance보다 작으면 singular
    # 부동 소수점 오차를 고려하여 정확한 0 비교 대신 작은 값과의 비교를 사용합니다.
  except np.linalg.LinAlgError:
    return True  # 행렬식 계산 중 오류가 발생하면 singular로 간주 (예: 특이 행렬)

def is_singular_by_rank(df):
    """
    Pandas DataFrame이 singular한지 랭크(rank)를 사용하여 판단합니다.

    Args:
      df: Pandas DataFrame (실수 값을 원소로 가져야 함)

    Returns:
      True: DataFrame이 singular함
      False: DataFrame이 singular하지 않음
    """
    matrix = df.values
    if matrix.shape[0] != matrix.shape[1]:
      return True # 정방행렬이 아니면 singular

    rank = np.linalg.matrix_rank(matrix)
    return rank < min(matrix.shape)  # 랭크가 행/열의 최소값보다 작으면 singular

def get_eigenvalues(df):
  """
  Pandas DataFrame의 고윳값(eigenvalue)과 고유 벡터(eigenvector)를 반환합니다.

  Args:
    df: Pandas DataFrame (실수 값을 원소로 가져야 함, 정방 행렬이어야 함)

  Returns:
    Tuple: (eigenvalues, eigenvectors)
      eigenvalues: 고윳값을 담은 NumPy 배열
      eigenvectors: 고유 벡터를 열로 갖는 NumPy 배열
      None: 정방 행렬이 아니거나, 고윳값 계산에 실패한 경우 None 반환
  """
  matrix = df.values  # DataFrame을 NumPy 행렬로 변환

  if matrix.shape[0] != matrix.shape[1]:
    print("Error: Input DataFrame must be a square matrix.")
    return None, None  # 정방 행렬이 아니면 None 반환

  try:
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    return eigenvalues
  except np.linalg.LinAlgError:
    print("Error: Eigenvalue calculation failed.")
    return None # 고윳값 계산에 실패하면 None 반환

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
    for i in range(len(list1)):
        if list2[i] is not None:
            result.append([list1[i], list2[i]])
        else:
            result.append([list1[i]])
    return result

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

def simul_mapped_by_dict(list_of_lists, dictionary):
    """
    리스트의 각 리스트 요소에 해당하는 딕셔너리의 값들을 합집합 연산하여 새로운 리스트를 반환합니다.

    Args:
        list_of_lists: 리스트의 리스트 (예: [[0], [1, 0], [2, 1], ...]).
        dictionary: 키가 정수이고 값이 집합인 딕셔너리 (예: {0: {9, 15, 6, 1}, 1: {9, 19, 6, 1}, ...}).

    Returns:
        각 리스트 요소에 해당하는 집합들의 합집합을 담은 리스트.
    """
    result = []
    for inner_list in list_of_lists:
        combined_set = set()  # 각 inner_list에 대한 합집합을 저장할 집합
        for key in inner_list:
            # if key in dictionary:
            combined_set = combined_set.union(dictionary[key])
        result.append(combined_set)
    return result

def extract_unique_values_int_keys(dict):
    """
    딕셔너리에서 키가 정수인 항목의 값(집합)들에 들어 있는 모든 고유한 값들을 추출하여 하나의 집합으로 반환합니다.

    Args:
        dict: 딕셔너리 (키는 임의의 타입, 값은 집합).

    Returns:
        키가 정수인 딕셔너리 항목의 모든 집합 값에 포함된 고유한 값들의 집합.
    """
    unique_values = set()
    for key, value_set in dict.items():  # items()를 사용하여 키와 값을 함께 순회
        if isinstance(key, int):  # 키가 정수인지 확인
            unique_values = unique_values.union(value_set)

    return unique_values

def simul_connectedness(unique_values, simul_units, log = False):
    """
    주어진 고유 값과 simul_chords를 사용하여 데이터프레임을 생성하고 연결도를 계산하여 채웁니다.

    Args:
        unique_values: extract_unique_values_int_keys 함수의 결과로 얻은 고유 값의 집합.
        simul_chords: combine_with_dict 함수의 결과로 얻은 리스트 (각 원소는 집합).

    Returns:
        연결도가 채워진 pandas DataFrame.
    """
    import pandas as pd

    # 1. DataFrame 생성
    df = pd.DataFrame(0, index=sorted(list(unique_values)), columns=sorted(list(unique_values)))

    # 2. simul_chords의 각 원소(집합)을 순회하며 연결도 계산 및 DataFrame 업데이트
    for chord in simul_units:
        chord_list = sorted(list(chord))  # 집합을 정렬된 리스트로 변환 (인덱싱 용이)

        for i in range(len(chord_list)):
            for j in range(i, len(chord_list)):  # i <= j 조건 만족
                note_i = chord_list[i]
                note_j = chord_list[j]
                df.loc[note_i, note_j] += 1
                if log :
                    print(f"df[{note_i}, {note_j}] += 1 from {chord_list}") # 디버깅용

    return df

def get_simul_connected(adn_1_chord_ : list, adn_2_chord_ : list, transform_dict : dict) :

    simul_chords_key = simul_chord_lists(adn_1_chord_, adn_2_chord_)
    simul_units = simul_mapped_by_dict(simul_chords_key, transform_dict)
    unique_values = extract_unique_values_int_keys(transform_dict)
    print("Unique values (int keys only):", unique_values)

    df_result = simul_connectedness(unique_values, simul_units)
    
    return df_result


# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------- DFT stuffs ----------------------------------------- #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #


def FourierBars(adjusted_notes : list, distinct : bool = False) -> list:
    
    # 1. adjust_to_eighth_note 결과를 마디별로 그룹화
    len_bars = math.ceil(max(note[2] for note in adjusted_notes) / 8)
    Bars = [[] for _ in range(len_bars)] # 리스트 컴프리헨션 사용
    for start, pitch, end in adjusted_notes:
      bar_index = int(start/8)
      Bars[bar_index].append([start, pitch])

    # 2. 음높이 단위 계산
    pitches = []
    for bar in Bars:
        if bar: # bar가 비어있지 않은 경우
            pitches.extend([note[1] for note in bar])
    
    pitch_unit = min(pitches) - min(pitches) % 12

    # 3. 시간 및 음높이 정규화
    for i in range(len(Bars)):
        # 마디의 시작 시간 계산
        bar_start_time = i * 8
        for j in range(len(Bars[i])):
            # 마디 내에서의 상대적인 onset 계산
            Bars[i][j][0] = (Bars[i][j][0] - bar_start_time) % 8
            Bars[i][j][1] = (Bars[i][j][1] - pitch_unit) # 정규화된 음높이
        # Bars[i].sort() 
        # # 굳이 할 필요 없을 것 같다.

    # 4. 중복 마디 제거 : adn_1_real의 경우 활성화해야 할 수도
    if distinct :
        dist_bars = []
        for B in Bars:
            if B not in dist_bars and B != []:
                dist_bars.append(B)
        return dist_bars
    
    else :
        return Bars

# just_bars_2 = FourierBars(adn_2_real) 결과 해석 용도 
def group_indices_by_element_lists(data):
    """
    리스트를 원소로 갖는 리스트에서, 같은 원소 리스트를 갖는 애들끼리
    인덱스를 묶어서 set으로 만들어주는 함수. 키는 임의의 정수로 변경.

    Args:
        data: 리스트를 원소로 갖는 리스트.

    Returns:
        딕셔너리. 키는 임의의 정수, 값은 해당 원소 리스트를 갖는 원소들의 인덱스 set.
    """
    grouped_indices = {}
    key_counter = 0  # 새로운 키를 할당하기 위한 카운터
    element_to_key = {} # element_list와 key_counter 매핑을 저장하는 딕셔너리

    for i, element_list in enumerate(data):
        # 리스트를 문자열로 변환
        element_string = str(element_list)

        if element_string not in element_to_key:
            # 새로운 element_list인 경우, 새로운 키 할당
            element_to_key[element_string] = key_counter
            grouped_indices[key_counter] = []
            key_counter += 1

        # 해당 element_list에 해당하는 키 가져오기
        key = element_to_key[element_string]
        grouped_indices[key].append(i)

    return grouped_indices

# char function
def charFucntionBar(bar, u_time, u_pitch) :
    """
     M은 마디의 시간-음높이 표현을 나타내는 특징 행렬이 됩니다. 
     onset과 pitch의 조합이 해당 마디에 존재하는지 여부를 나타내는
     일종의 "지문" 역할을 합니다.

    """

    M = np.zeros((u_time, u_pitch ))
    for i, j in bar :
        M[i, j] = 1
    
    return M

# DFT of a musical bar
def dft(bar, u_time, u_pitch) :
    """
     마디의 시간-음높이 특징을 주파수 영역으로 변환한 스펙트럼을 반환합니다.
    """
    A = charFucntionBar(bar, u_time, u_pitch)

    if u_time == 1:
        dft = np.fft.fft(A)
    else :
        dft = np.fft.fft2(A)
    
    return dft

# DFT between two musical bars
def dftMetricBars(bar1, bar2, u_time, u_pitch) :
    """
    두 마디의 스펙트럼 차이의 총합을 반환합니다. 
    이 값은 두 마디의 시간-음높이 패턴이 
    얼마나 다른지를 나타내는 척도로 사용됩니다

    """
    A = dft(bar1, u_time, u_pitch)
    B = dft(bar2, u_time, u_pitch)
    N = np.abs(A - B)
    M = N.sum()

    return M

#the final function that provides the dict of distances
def FourierMetricNorm(Bars : list, u_time=8, u_pitch=48, fill : bool = False) -> dict:
    """
    dftMetricBars 함수 내에서 charFucntionBar 함수가 마디를 
    특징 벡터(character function)로 변환하는 방식을 고려하면, 
    onset이 같은 것들끼리 직접적으로 계산되는 것은 아닙니다. 

    오히려, 마디 내의 모든 음높이와 시간 정보를 종합적으로 고려하여 
    거리를 계산합니다.
    """

    n_bars=len(Bars)

    # 마디 간 모든 거리 수집
    dist=[]
    for i in range(n_bars):
        for j in range(i+1,n_bars):
            dist.append([dftMetricBars(Bars[i], Bars[j], u_time, u_pitch)])
    
    epsilon=[e[0] for e in dist]
    M=max(epsilon)
    prec=(M/100) # precision, 거리를 0~100으로 정규화하는 효과.
    dist_prec=dict() # 거리에 따라 마디 쌍을 그룹화하는 데 사용

    # initialization :
    # 거리가 0인 경우 모든 마디가 동일한 그룹에 속한다
    dist_prec[0]=[(i+1)for i in range(n_bars)] 
    
    for i in range(n_bars):
        for j in range(i+1, n_bars):
            
            d = dftMetricBars(Bars[i], Bars[j], u_time, u_pitch)
            k = int(d/prec) # k*prec <= 거리 < (k+1)*prec인 구간을 나타낸다.
            
            if k not in dist_prec:
                dist_prec[k]=[(i+1,j+1)]
            
            elif k in dist_prec:
                dist_prec[k].append((i+1,j+1))

    # fill in
    if fill :
        for k in range(1,101):
            if k not in dist_prec:
                dist_prec[k]=dist_prec[k-1]
            
    #sorting the dictionary
    dist_prec_sort=dict()
    L=list(dist_prec.keys())
    L.sort()
    for k in L:
        dist_prec_sort[k]=dist_prec[k]

    return dist_prec_sort
