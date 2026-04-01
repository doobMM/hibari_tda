

import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import seaborn as sns

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

def get_distance_matrix_from(weighted_matrix: pd.DataFrame, out_of_reach = 1) -> pd.DataFrame:
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
    distance_matrix[weighted_matrix == 0] = out_of_reach

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

def is_distance_matrix_from(weight_mtrx, transform_dict, out_of_reach, refine = True) : 
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
    if refine :
        weight_UTM = refine_connectedness(weight_UTM, transform_dict)
    
    # 역수 변환
    distance_UTM = get_distance_matrix_from(weight_UTM, out_of_reach)

    distance_df = get_LTMpart_of(distance_UTM)

    return distance_df

def search_timeflow_cycles(adn_1_chord_ : list, adn_2_chord_ : list, 
                           inter_lag : int, refine_dict : dict,
                            rate_start = 0.00, rate_end = 1.5, step = 0.01,
                            loglog : bool = True) :
    """  
    Args :
    adn_1_chord_, adn_2_chord_ : 두 inst가 동시에 연주되는 범위에서의 화음 labelling list
      """
    
    weight_mtrx_1 = get_chords_intra_connected(adn_1_chord_, lag=1)
    weight_mtrx_2 = get_chords_intra_connected(adn_2_chord_, lag=1)
    intra_weights = weight_mtrx_1 + weight_mtrx_2
    inter_weight = get_chords_inter_connected(adn_1_chord_, adn_2_chord_, lag=inter_lag)
    
    outta_reach_t = 1 + 2 * 1 / (inter_weight[inter_weight!=0].min().min() * step)
    start = round(rate_start / step)
    end = round(rate_end / step)

    cycles_profile = []

    for a in range(start, end, 1) :

        rate = round(a * step, 4)
        if a % 10 == 0 :
            print(f"on rate {rate}...")

        timeflow_weight = intra_weights + rate * inter_weight 
        timeflow_distance = is_distance_matrix_from(timeflow_weight, refine_dict, out_of_reach = outta_reach_t)

        birthDeath = generateBarcode(mat = timeflow_distance.values, exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result_1 = (rate, birthDeath)
        cycles_profile.append(result_1)

    cycles_info = analyze_lifespans(cycles_profile, out_of_reach=outta_reach_t)

    plot_lifespan_results(cycles_info, refine_dict = refine_dict, inter_lag = inter_lag, loglog=loglog)

    return cycles_profile, outta_reach_t

def search_simul_cycles(adn_1_whole_c : list[int], adn_2_whole_c : list[int], refine_dict : dict,
                        rate_start = 0.00, rate_end = 1.5, step = 0.01,
                        loglog : bool = False) :
    
    """ 
     Args :
    adn_1_chord_, adn_2_chord_ : 같은 길이의 두 inst 전체 화음 labelling list 
       """

    simul_intra, simul_inter = get_simul_connected(adn_1_whole_c, adn_2_whole_c, refine_dict)
    start = round(rate_start / step)
    end = round(rate_end / step)

    cycles_profile = []

    temp = step * simul_inter
    outta_reach_s = 1 + 2 * 1 / temp[temp!=0].min().min()

    for a in range(start, end, 1) :

        rate = round(a * step, 4)
        if a % 10 == 0 :
            print(f"on rate {rate}...")

        # weight 구하는 부분
        simul_weight = simul_intra + rate * simul_inter
        
        # 거리 구하는 부분 
        simul_distance = is_distance_matrix_from(simul_weight, transform_dict = None, out_of_reach = outta_reach_s, refine = False)

        birthDeath = generateBarcode(mat = simul_distance.values, exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result = (rate, birthDeath)
        cycles_profile.append(result)

    cycles_info = analyze_lifespans(cycles_profile, outta_reach_s)

    plot_lifespan_results(cycles_info, refine_dict = refine_dict, inter_lag = None, loglog=loglog)

    return cycles_profile, outta_reach_s

def get_correct_df(transform_dict : dict, simul_musical_units : list):
    """
    딕셔너리의 값들을 합집합하여 컬럼명으로 사용하고, 리스트의 각 요소를 기준으로 DataFrame을 생성합니다.

    Args:
        dict_values: 딕셔너리의 값 (set)을 포함하는 dict_values 객체.
        simul_musical_units: set을 요소로 가지는 리스트.

    Returns:
        생성된 pandas DataFrame.
    """

    # 컬럼명 생성 (딕셔너리 값들의 합집합)
    all_notes = set()
    dict_values = transform_dict.values()
    for notes_set in dict_values:
        if type(notes_set) == set :
            all_notes.update(notes_set)  # 합집합 연산

    columns = sorted(list(all_notes))  # 정렬된 컬럼명 리스트

    # DataFrame 생성
    data = []
    for notes_set in simul_musical_units:
        row = [1 if col in notes_set else 0 for col in columns]  # 각 컬럼에 대해 1 또는 0 설정
        data.append(row)

    df = pd.DataFrame(data, columns=columns)  # DataFrame 생성

    return df

def get_cycles_scattered_df(df : pd.DataFrame, cycle_labeled : dict, weak : bool = True):
    """
    DataFrame에서 특정 사이클들에 해당하는 컬럼만 추출하고,
    각 행에서 1로 표시된 컬럼들을 값으로 갖는 cycle_df를 생성합니다.

    Args:
        df: 원본 DataFrame.
        cycle_labeled: 추출할 컬럼에 해당하는 사이클 (tuple)들을 값으로 가지는 딕셔너리.

    Returns:
        cycle_df: 추출된 컬럼을 기반으로 생성된 pandas DataFrame.
    """

    # 결과를 저장할 딕셔너리 초기화
    cycle_dfs = {}

    # 각 사이클에 대해 반복
    if weak :
        for label, cycle in cycle_labeled.items():
            # 사이클에 해당하는 컬럼명 추출
            cycle_columns = [col + 1 for col in cycle]  # 컬럼명 리스트 생성

            # sub_df 생성 (cycle에 해당하는 컬럼만 추출)
            sub_df = df[cycle_columns]

            # cycle_df 생성 (각 행에서 1로 표시된 컬럼들을 set으로 저장)
            cycle_dfs[label] = sub_df.apply(lambda row: 1 if row.sum() > 0 else 0, axis=1)
    else :
        for label, cycle in cycle_labeled.items():
            cycle_columns = [col + 1 for col in cycle]
            sub_df = df[cycle_columns]

            cycle_dfs[label] = sub_df.apply(lambda row: set(row[row == 1].index), axis=1)

    # 모든 cycle_df를 병합
    cycle_df = pd.DataFrame(cycle_dfs)

    return cycle_df

def notes_label_counts(notes_label, notes_counts) :
    """ 
    Args :
    notes_label_n_counts의 출력값인 notes_label, notes_counts
    """

    # Counter 객체의 key를 dictionary의 value로 매핑
    notes_freq_in_a_module = {}
    for key, count in notes_counts.items():
        if key in notes_label:
            notes_freq_in_a_module[notes_label[key]] = count

    return notes_freq_in_a_module

def check_ratio_of_on(binary_df : pd.DataFrame, column_idx : int) :

    indices_of_ones = binary_df[binary_df[column_idx] == 1].index

    return len(indices_of_ones) / binary_df.shape[0]

def standardize(data):
  mean_val = sum(data) / len(data)
  std_dev = (sum([(x - mean_val)**2 for x in data]) / len(data))**0.5
  return [(x - mean_val) / std_dev for x in data]

def analyze_cycles_scattered(binary_df : pd.DataFrame, cycle_labeled : dict, notes_freq : dict, scale : bool) :

    """ 
     Args :
     binary_df : get_cycles_scattered_df(df, cycle_labeled, weak = True)의 리턴값으로 기대된다
     notes_freq : notes_label_counts의 리턴값으로 기대된다.
       """

    plausible = []
    for column_idx in binary_df.columns:

        cycle_to_see = [vertex_label + 1 for vertex_label in cycle_labeled[column_idx]]
        cycle_length = len(cycle_to_see)

        values_sum = 0
        valid_count = 0
        for key in cycle_to_see:
            if key in notes_freq:
                values_sum += notes_freq[key]
                valid_count += 1
            else :
                print(f"you need to check compatibility for {key}!")

        # 딕셔너리에 존재하는 key가 하나도 없는 경우 예외 처리
        if valid_count == 0:
            average_freq = 0  # 또는 None 등으로 처리
        else:
            average_freq = values_sum / valid_count

        ratio = check_ratio_of_on(binary_df, column_idx)

        plausible.append((column_idx, ratio, cycle_length, average_freq))

    x_values = [t[0] for t in plausible]
    y1_values = [t[1] for t in plausible]
    y2_values = [t[2] for t in plausible]
    y3_values = [t[3] for t in plausible]

    if scale :
        # Scale the Y values (using normalization in this example)
        y1_values = standardize(y1_values)
        y2_values = standardize(y2_values)
        y3_values = standardize(y3_values)

    # Calculate correlations using NumPy
    correlation_1_2 = np.corrcoef(y1_values, y2_values)[0, 1]
    correlation_1_3 = np.corrcoef(y1_values, y3_values)[0, 1]
    correlation_2_3 = np.corrcoef(y2_values, y3_values)[0, 1]

    print(f"Correlation between plausible ratio and cycle length: {correlation_1_2}")
    print(f"Correlation between plausible ratio and mean of vertex freq: {correlation_1_3}")
    print(f"Correlation between cycle length and mean of vertex freq: {correlation_2_3}")

    # 플롯 생성
    plt.figure(figsize=(8, 5))  # 그래프 크기 설정 (선택 사항)
    plt.plot(x_values, y1_values, label="plausible ratio", marker='o')  # 첫 번째 y축 데이터
    plt.plot(x_values, y2_values, label="cycle length", marker='x')  # 두 번째 y축 데이터
    plt.plot(x_values, y3_values, label="mean of vertex freq", marker='s')  # 세 번째 y축 데이터

    # 레이블 및 제목 추가
    plt.xlabel("X-axis")

    if not scale :
        plt.ylabel("Y-axis")
    else : 
        plt.ylabel("Scaled Y-axis")

    plt.title("Multiple Y-axes Plot")
    plt.grid(True)
    plt.legend()
    plt.show()

    return plausible

def check_cycle_if_plausible(cycles_df_strong : pd.DataFrame, column_idx : int, 
                            cycle_labeled : dict, notes_counts, notes_label : dict) :

    cycle_to_see = [vertex_label + 1 for vertex_label in cycle_labeled[column_idx]]

    notes_freq_in_a_module = notes_label_counts(notes_label, notes_counts)

    filtered_dict = {key: notes_freq_in_a_module[key] for key in cycle_to_see if key in notes_freq_in_a_module}
    filtered_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1], reverse=True))

    for label, count in filtered_dict.items():
        print(f"label: {label}, 등장횟수: {count}")

    indices_of_ones = cycles_df_strong[cycles_df_strong[column_idx] != set()].index
    rows_where_ith_cycle_found = cycles_df_strong.loc[indices_of_ones, column_idx].to_frame()
    rows_where_ith_cycle_found.rename(columns={column_idx: str(cycle_to_see)}, inplace=True)

    return rows_where_ith_cycle_found, str(cycle_to_see)

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

def analyze_lifespans(cycles_profile : list, out_of_reach : int):
  """
  cycles_profile_n1 리스트를 분석하여 각 rate에 대한 lifespans의 평균, 표준편차, 최대값을 계산합니다.

  Args:
    cycles_profile_n1: (rate, length of list, list) 형태의 리스트.
                       각 리스트는 (rate, 리스트 길이, 주기 리스트)로 구성됩니다.
                       주기 리스트는 [1, [시작 시간, 종료 시간], '설명'] 형태의 리스트를 담고 있습니다.

  Returns:
    dict: 각 rate를 키로, (평균, 표준편차, 최대값) 튜플을 값으로 가지는 딕셔너리.
         만약 특정 rate에 대한 lifespan이 없으면 (평균, 표준편차, 최대값)은 (None, None, None)입니다.
  """

  results = {}

  for rate_data in cycles_profile:
    rate = rate_data[0]
    cycles_list = rate_data[1]

    lifespans = []
    for cycle in cycles_list:
      start_time, end_time = cycle[1] # unpack start, end

      life = out_of_reach - float(start_time) if end_time == 'infty' else end_time - start_time
      lifespans.append(life)

    if lifespans:  # lifespan이 존재하는 경우
      lifespans_array = np.array(lifespans) # converted to numpy array
      mean = np.mean(lifespans_array)
      std = np.std(lifespans_array)
      max_life = np.max(lifespans_array)
      count = len(cycles_list)
      results[rate] = (count, mean, std, max_life)
    else:  # lifespan이 존재하지 않는 경우
      results[rate] = (None, None, None, None)

  return results

def plot_lifespan_results(lifespan_results, refine_dict : dict, inter_lag : int, loglog=True, figsize_ = (6,4)):
  """
  각 rate에 대한 lifespan 결과 (평균, 표준편차, 최대값)를 plot합니다.

  Args:
    lifespan_results: {rate: (평균, 표준편차, 최대값)} 형태의 딕셔너리.
    title_prefix: 그래프 제목에 추가할 접두사 (선택 사항).
    loglog: True인 경우 loglog plot을 사용하고, False인 경우 일반 plot을 사용합니다 (선택 사항).
  """

  if inter_lag is not None :
    title_prefix = f"({refine_dict['name']}, {inter_lag})"
  else :
    title_prefix = f"({refine_dict['name']})"

  rates = list(lifespan_results.keys()) # rate 추출
  counts = [lifespan_results[rate][0] for rate in rates] # 갯수 추출
  means = [lifespan_results[rate][1] for rate in rates] # 평균 추출
  stds = [lifespan_results[rate][2] for rate in rates]  # 표준 편차 추출
  max_lifes = [lifespan_results[rate][3] for rate in rates] # 최대값 추출

  # Counts plot
  plt.figure(figsize = figsize_)  # 새로운 Figure 생성
  plt.plot(rates, counts) 
  plt.title(f"{title_prefix} count of 1-simplex")
  plt.xlabel("inter_weight / intra_weights")
  plt.ylabel("#cycles")
  plt.grid(True)  # Added grid for better readability
  plt.show()


  # Mean plot
  plt.figure(figsize = figsize_)  # 새로운 Figure 생성
  if loglog:  
    plt.loglog(rates, means)
  else:
    plt.plot(rates, means)  
  plt.title(f"{title_prefix} Mean Lifespan")
  plt.xlabel("inter_weight / intra_weights")
  plt.ylabel("Mean Lifespan")
  plt.grid(True)  # Added grid for better readability
  plt.show()

  # Std Dev plot
  plt.figure(figsize = figsize_)  # 새로운 Figure 생성
  if loglog:
    plt.loglog(rates, stds)
  else:
    plt.plot(rates, stds)
  plt.title(f"{title_prefix} Standard Deviation of Lifespans")
  plt.xlabel("inter_weight / intra_weights")
  plt.ylabel("Standard Deviation of Lifespan")
  plt.grid(True)  # Added grid for better readability
  plt.show()

  # Max Lifespan plot
  plt.figure(figsize = figsize_)  # 새로운 Figure 생성
  if loglog:
    plt.loglog(rates, max_lifes)
  else:
    plt.plot(rates, max_lifes)
  plt.title(f"{title_prefix} Max Lifespan")
  plt.xlabel("inter_weight / intra_weights")
  plt.ylabel("Max Lifespan")
  plt.grid(True)  # Added grid for better readability
  plt.show()

def count_cycle_lengths(cycle_labeled : dict):
    """
    cycle_labeled 딕셔너리의 value로 있는 cycle들의 길이에 따라 몇 개씩 있는지 확인합니다.

    Args:
        cycle_labeled: cycle들을 값으로 가지는 딕셔너리.

    Returns:
        각 cycle 길이별 개수를 담은 Counter 객체.
    """

    cycle_lengths = [len(cycle) for cycle in cycle_labeled.values()]  # cycle 길이를 리스트로 추출
    length_counts = Counter(cycle_lengths)  # 길이별 개수 계산

    return length_counts.most_common() 

def count_vertices_by_num_cycles_contained(cycle_labeled : dict):
    """
    cycle_labeled 딕셔너리에 있는 모든 note에 대해 각 note가 포함된 사이클의 개수를 세는 함수.

    Args:
        cycle_labeled: cycle들을 값으로 가지는 딕셔너리.

    Returns:
        각 note별로 포함된 사이클 개수를 담은 Counter 객체.
    """

    counts = Counter()

    # 모든 사이클을 순회하며 각 note의 등장 횟수를 카운트
    for cycle in cycle_labeled.values():
        counts.update(cycle)

    return counts.most_common() 

def label_cycle(cycle_persistence : dict, transform_dict : dict,
                info = True, log = False) :

    cycle_labeled = {i: cycle for i, cycle in enumerate(cycle_persistence.keys())}

    if info :

        length_counts = count_cycle_lengths(cycle_labeled)
        component_counts = count_vertices_by_num_cycles_contained(cycle_labeled)

        all_component = set()
        dict_values = transform_dict.values()
        for notes_set in dict_values:
            if type(notes_set) == set :
                all_component.update(notes_set)  # 합집합 연산

        in_cycle_component = set(x[0] for x in component_counts)
        
        not_in_cycle_component = all_component - in_cycle_component

        if log :
            print("Cycle 길이별 개수:")
            for length, count in length_counts:
                print(f"Length {length}: {count}개")

            print("\nComponent별 포함된 사이클 개수:")
            for note, count in component_counts:
                print(f"Note {note}: {count}개")

            print(f"\ncomponent label not in any cycle : {not_in_cycle_component}")
            print(f"where there are {len(all_component)} components (notes_dict의 경우 인덱스가 1부터 시작합니다)")


    else :
        length_counts = []
        component_counts = []

    return cycle_labeled, length_counts, component_counts

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

def get_rBD_groupedBy_cycle(cycles_profile: list) -> dict:
    """
    cycles_profile 리스트를 순회하면서 사이클 별로 (rate, birth, death) 정보를 담는 딕셔너리를 생성합니다.
    """
    cycle_persistence = {}

    for rate_data in cycles_profile:
        rate = rate_data[0]
        cycles_list = rate_data[1]

        for cycle in cycles_list:
            birth = cycle[1][0]
            death = cycle[1][1]
            edges_str = cycle[2].strip()

            # 0. 맨 앞에 부호가 없다면 '+' 추가
            if not re.match(r'^[+-]', edges_str):
                edges_str = '+ ' + edges_str

            # 1. 사이클 추출 및 변환
            edges = re.findall(r'([+-])\s*\(\s*(\d+)\s*,\s*(\d+)\)', edges_str)

            if not edges:
                print(f"경고: edge 정보가 없습니다. edges_str: {edges_str}")
                continue

            edge_list = []
            for sign, v1, v2 in edges:
                if sign == '-':
                    edge_list.append((int(v2), int(v1)))
                else:
                    edge_list.append((int(v1), int(v2)))
            # print(edge_list)

            # 2. Cycle 구성
            cycle_representation = []
            if edge_list:
                # 첫 번째 튜플 찾기 (첫 번째 원소가 가장 작은 것)
                start_tuple = min(edge_list)
                cycle_representation.append(start_tuple[0])
                cycle_representation.append(start_tuple[1])
                edge_list.remove(start_tuple)

                # 나머지 튜플 연결
                while edge_list:
                    # print(edge_list)
                    last_vertex = cycle_representation[-1]
                    found_next = False
                    for next_tuple in edge_list:
                        if next_tuple[0] == last_vertex:
                            # 이미 cycle에 있는 vertex는 추가하지 않음
                            if next_tuple[1] not in cycle_representation:
                                cycle_representation.append(next_tuple[1])
                            edge_list.remove(next_tuple)
                            found_next = True
                            break
                    if not found_next:
                        break  # 더 이상 연결할 수 없을 때

             # Cycle 길이 및 유효성 검사
            if len(cycle_representation) >= 4:
              if cycle_representation[0] == cycle_representation[-1]:
                cycle_representation.pop()  # 마지막 원소 제거

              cycle_key = tuple(cycle_representation) # 튜플로 변환
              if cycle_key not in cycle_persistence:
                cycle_persistence[cycle_key] = []
              cycle_persistence[cycle_key].append((rate, birth, death))
            else :
                print("cycle of length shorter than 4 detected?!")                

    return cycle_persistence

def check_rearranged_cycles(cycle_persistence: dict) -> dict:
    """
    cycle_persistence 딕셔너리에서 동일한 vertex label로 구성되었지만 순서가 다른 cycle들을 찾습니다.
    2개 이상의 Cycle을 가지는 Cycle만 반환합니다. 각 Cycle이 어떤 rate에 대해서 나타나는지 정보를 포함합니다.

    Args:
      cycle_persistence: create_cycle_data 함수의 결과 딕셔너리.

    Returns:
      dict: 동일한 vertex label로 구성된 cycle들을 묶어서 딕셔너리로 반환합니다.
            키는 정렬된 vertex label의 튜플이고, 값은 (cycle, rate 리스트) 튜플의 리스트입니다.
            2개 이상의 Cycle을 가지는 Cycle만 포함합니다.
    """

    same_cycles = {} 
    """
    중간 결과를 저장하는 데 사용됩니다.
    키: frozenset(cycle) - Cycle을 구성하는 vertex label의 집합 (순서 무시)
    값: (cycle, rates) - Cycle의 원래 형태와 해당 Cycle이 나타나는 rate 리스트의 튜플
       """
    
    for cycle, data_list in cycle_persistence.items():
        # Cycle을 set으로 변환하여 vertex label만 남기고 순서를 제거합니다.
        cycle_set = frozenset(cycle)  # set은 hashable하지 않으므로 frozenset 사용
        rates = [data[0] for data in data_list] # 현재 cycle의 모든 rate 저장

        # 현재 cycle이 이미 same_cycles에 존재하는지 여부를 나타내는 플래그를 초기화합니다.
        found = False 
        for key, cycle_data in same_cycles.items(): # cycles -> cycle_data 로 변경
            if cycle_set == frozenset(key):  # set 비교
                same_cycles[key].append((cycle, rates))  # (cycle, rate 리스트) 튜플 추가
                found = True
                break

        # same_cycles에 존재하지 않는 cycle이면 새로 추가합니다.
        if not found:
            same_cycles[cycle] = [(cycle, rates)]  # (cycle, rate 리스트) 튜플 추가

    # 결과를 정렬된 vertex label 튜플을 키로 사용하도록 변환
    result = {}
    for key, cycles in same_cycles.items():
        sorted_key = tuple(sorted(list(key)))
        if len(cycles) > 1:  # Value가 2개 이상인 Cycle만 포함
            result[sorted_key] = cycles
    
    # 결과 출력
    for key, cycles in result.items():
        print(f"Vertex label: {key}")
        for cycle, rate in cycles:
            print(f"  Cycle: {cycle}, Rate: {rate}")

    return result

def split_cycles_by_consecutive(cycle_persistence: dict, out_of_reach : float, step: float = 0.01) -> dict:
    """
    Args:
        cycle_persistence: cycle 데이터를 담고 있는 딕셔너리.
        step: 연속성을 판단하는 기준이 되는 값 (default: 0.01).

    Returns:
        
    """

    non_consecutive_cycles = {}
    for cycle, rBD_list in cycle_persistence.items():
        is_consecutive = True
        for i in range(len(rBD_list) - 1):
            diff = round(rBD_list[i + 1][0] - rBD_list[i][0], 6)  # 소수점 6자리까지 반올림하여 비교
            if abs(diff - step) > 1e-6:  # 부동 소수점 오차 고려
                is_consecutive = False
                break
        if not is_consecutive:
            new_rBD_list = []
            non_consecutive_cycles[cycle] = rBD_list
            for rate, birth, death in rBD_list:
                if death == 'infty' :
                    new_death = out_of_reach
                else :
                    new_death = death
                new_rBD_list.append((rate, birth, new_death))
            non_consecutive_cycles[cycle] = tuple(new_rBD_list)

    consecutive_cycles = dict()
    for cycle, rBD_list in cycle_persistence.items() :
        new_rBD_list = []
        if cycle not in non_consecutive_cycles.keys() :
            for rate, birth, death in rBD_list:
                if death == 'infty' :
                    new_death = out_of_reach
                    # print(cycle, rate)
                else :
                    new_death = death
                new_rBD_list.append((rate, birth, new_death))
            consecutive_cycles[cycle] = tuple(new_rBD_list)  # 튜플로 변환

    return non_consecutive_cycles, consecutive_cycles

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

def simul_union_by_dict(list_of_lists, dictionary):
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

def chord_specified_into_set(chord_list : list[int], specify_dict : dict) -> list[set[int]]:

    module_notes = []
    for chord_label in chord_list:
        if chord_label in specify_dict:
            module_notes.append(specify_dict[chord_label])
        else:
            module_notes.append(None)  # 키가 딕셔너리에 없으면 None을 사용

    return module_notes

def get_simul_intra_connected2(unique_values, paired_units, exclude=True, log=False):
    """
    주어진 고유 값과 paired_units를 사용하여 데이터프레임을 생성하고 연결도를 계산하여 채웁니다.
    교집합 원소에 대해서는 exclude이 True일 경우 1씩 빼줍니다.

    Args:
        unique_values: extract_unique_values_int_keys 함수의 결과로 얻은 고유 값의 집합.
        paired_units: hibari_notes_list와 같은 리스트 (각 원소는 (set, set) 또는 (set, None)).
        exclude: True일 경우 교집합 원소에 대해 1씩 빼줍니다.

    Returns:
        연결도가 채워진 pandas DataFrame.
    """

    # 1. DataFrame 생성
    df = pd.DataFrame(0, index=sorted(list(unique_values)), columns=sorted(list(unique_values)))

    if log:
        # 2. paired_units의 각 원소를 순회하며 연결도 계산 및 DataFrame 업데이트
        for pair in paired_units:
            # 각 튜플의 첫 번째와 두 번째 set을 처리
            sets = [s for s in pair if s is not None] # None 제거

            # sets에 2개의 set이 있을 경우, 교집합 계산
            intersection = set()
            if len(sets) == 2:
                intersection = sets[0].intersection(sets[1])

            for chord in sets:
                chord_list = sorted(list(chord))  # 집합을 정렬된 리스트로 변환 (인덱싱 용이)

                for i in range(len(chord_list)):
                    for j in range(i, len(chord_list)):  # i <= j 조건 만족
                        note_i = chord_list[i]
                        note_j = chord_list[j]
                        df.loc[note_i, note_j] += 1
                        print(f"df[{note_i}, {note_j}] += 1 from {chord_list}")  # 디버깅용
                        # logging.info(f"df[{note_i}, {note_j}] += 1 {chord_list}") # logging 사용 예시


            # exclude이 True이고 교집합이 존재할 경우, 교집합 원소에 대해 1씩 빼줍니다.
            if exclude and intersection:
                intersection_list = sorted(list(intersection))
                for i in range(len(intersection_list)):
                    for j in range(i, len(intersection_list)):
                        note_i = intersection_list[i]
                        note_j = intersection_list[j]
                        df.loc[note_i, note_j] -= 1
                        print(f"df[{note_i}, {note_j}] -= 1 (Intersection)")

    else :
        # 2. paired_units의 각 원소를 순회하며 연결도 계산 및 DataFrame 업데이트
        for pair in paired_units:
            # 각 튜플의 첫 번째와 두 번째 set을 처리
            sets = [s for s in pair if s is not None] # None 제거

            # sets에 2개의 set이 있을 경우, 교집합 계산
            intersection = set()
            if len(sets) == 2:
                intersection = sets[0].intersection(sets[1])

            for chord in sets:
                chord_list = sorted(list(chord))  # 집합을 정렬된 리스트로 변환 (인덱싱 용이)

                for i in range(len(chord_list)):
                    for j in range(i, len(chord_list)):  # i <= j 조건 만족
                        note_i = chord_list[i]
                        note_j = chord_list[j]
                        df.loc[note_i, note_j] += 1
                        # print(f"df[{note_i}, {note_j}] += 1 from {chord_list}")  # 디버깅용

            # exclude이 True이고 교집합이 존재할 경우, 교집합 원소에 대해 1씩 빼줍니다.
            if exclude and intersection:
                intersection_list = sorted(list(intersection))
                for i in range(len(intersection_list)):
                    for j in range(i, len(intersection_list)):
                        note_i = intersection_list[i]
                        note_j = intersection_list[j]
                        df.loc[note_i, note_j] -= 1
                        # print(f"df[{note_i}, {note_j}] -= 1 (Intersection)")

    return df

def get_simul_inter_connected2(unique_values, paired_units, log=False):
    """
    주어진 고유 값과 paired_units를 사용하여 데이터프레임을 생성하고,
    차집합 원소는 bipartite graph 방식으로 연결도를 계산하여 채웁니다.

    Args:
        unique_values: 고유 값의 집합.
        paired_units: 각 인덱스에 최대 2개의 set을 가지는 리스트.

    Returns:
        연결도가 채워진 pandas DataFrame.
    """

    # 1. DataFrame 생성
    df = pd.DataFrame(0, index=sorted(list(unique_values)), columns=sorted(list(unique_values)))

    # 2. paired_units의 각 원소를 순회하며 연결도 계산 및 DataFrame 업데이트
    for pair in paired_units:
        set1, set2 = pair  # 각 튜플의 두 set을 언패킹

        if set1 is None or set2 is None: # 하나라도 None이면 skip
            continue

        # 3. 차집합 계산
        difference1 = set1.difference(set2)
        difference2 = set2.difference(set1)

        # 4. 차집합 원소에 대한 연결도 계산 (bipartite graph 방식)
        if difference1 and difference2:
            if log:
                for note_i in difference1:
                    for note_j in difference2:
                        print(f"df[{note_i}, {note_j}] += 1 (Bipartite)")
                        df.loc[note_i, note_j] += 1
            else :
                for note_i in difference1:
                    for note_j in difference2:
                        # print(f"df[{note_i}, {note_j}] += 1 (Bipartite)")
                        df.loc[note_i, note_j] += 1


    return df

def get_simul_connected(inst1_whole_chord : list[int], inst2_whole_chord : list[int], specify_dict : dict, log = False):

    inst1_specified = chord_specified_into_set(inst1_whole_chord, specify_dict)
    inst2_specified = chord_specified_into_set(inst2_whole_chord, specify_dict)
    song_specified = list(zip(inst1_specified, inst2_specified)) # 해당 노래는 inst 2개로 이뤄져있어야 함.

    unique_values = extract_unique_values_int_keys(specify_dict)

    simul_intra = get_simul_intra_connected2(unique_values, song_specified, exclude=True, log = log)
    simul_inter = get_simul_inter_connected2(unique_values, song_specified, log = log)

    # simul_intra = get_simul_intra_connected(unique_values, song_specified)
    # simul_inter = get_simul_inter_connected2(unique_values, song_specified)

    return simul_intra, simul_inter

def plot_cycle_BirthDeath_over_rate(cycle_persistence: dict, subplot_in_a_row : int = 3):
    """
    cycle_persistence 딕셔너리를 입력받아 각 사이클의 persistence diagram을 시각화합니다.

    Args:
      cycle_persistence: create_cycle_data 함수의 결과 딕셔너리.
    """

    num_cycles = len(cycle_persistence)
    num_cols = min(subplot_in_a_row, num_cycles)  # 한 줄에 최대 3개
    num_rows = (num_cycles + num_cols - 1) // num_cols  # 필요한 줄 수

    fig, axes = plt.subplots(num_rows, num_cols, figsize=(8 * num_cols, 6 * num_rows))
    fig.tight_layout(pad=3.0)  # 그래프 간 간격 조정

    # axes가 1차원 배열인 경우 2차원 배열로 변환
    if num_cycles > 1 and num_cols == 1:
        axes = axes.reshape(-1, 1)
    elif num_cycles == 1:
        # axes = [axes] # 1개인 경우에도 list로 처리
        axes = np.array([axes])  # 1개인 경우에도 numpy array로 처리  <-- 수정됨


    for i, (cycle, data_list) in enumerate(cycle_persistence.items()):
        row = i // num_cols
        col = i % num_cols

        # 데이터 추출
        rates = np.array([data[0] for data in data_list])
        births = np.array([data[1] for data in data_list])
        deaths = np.array([data[2] for data in data_list])

        # 그래프 생성
        # ax = axes[row][col]  # 올바른 subplot 선택
        if num_rows == 1 and num_cols == 1:  # subplot이 하나인 경우
            ax = axes[0]  # axes는 1차원 배열, 첫 번째 요소 사용  <-- 수정됨
        elif num_rows == 1: # axes가 1차원 배열인 경우
            ax = axes[col] # <--- 수정됨
        else:
            ax = axes[row, col]  # 올바른 subplot 선택

        # Birth 시각화
        for j in range(len(rates) - 1):
            if round(rates[j+1] - rates[j], 2) == 0.01:
                ax.plot(rates[j:j+2], births[j:j+2], marker='o', linestyle='-', color='blue')
            else:
                ax.plot(rates[j], births[j], marker='o', color='blue')
        if rates.size > 0:
            ax.plot(rates[-1], births[-1], marker='o', color = 'blue') # 마지막 점

        # Death 시각화
        for j in range(len(rates) - 1):
            if round(rates[j+1] - rates[j], 2) == 0.01:
                ax.plot(rates[j:j+2], deaths[j:j+2], marker='x', linestyle='-', color='orange')
            else:
                ax.plot(rates[j], deaths[j], marker='x',  color='orange')
        if rates.size > 0:
            ax.plot(rates[-1], deaths[-1], marker='x', color = 'orange') # 마지막 점

        # 그래프 제목 및 축 레이블 설정
        ax.set_title(f"Cycle {cycle}")
        ax.set_xlabel("Rate")
        ax.set_ylabel("Time")

        # 범례 표시
        # ax.legend(['Birth', 'Death'])

        # 그리드 추가
        ax.grid(True)

    # 남은 subplot 숨기기 (cycle이 부족한 경우)
    for i in range(num_cycles, num_rows * num_cols):
        row = i // num_cols
        col = i % num_cols

        if num_rows == 1 and num_cols == 1: # subplot이 하나인 경우 skip
            continue
        elif isinstance(axes, np.ndarray):
            if axes.ndim == 2:
                ax = axes[row, col]
            else:
                ax = axes[i]
            fig.delaxes(ax)
        else:
            fig.delaxes(axes[i]) #1개인 경우

        # if isinstance(axes, np.ndarray):
        #   ax = axes[row, col]
        #   fig.delaxes(ax)
        # else:
        #   fig.delaxes(axes[i]) #1개인 경우

    # 그래프 출력
    plt.show()


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







# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------- 250414 교수님 barcoe 함수---------------------------- #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #


# 이 부분은 지속성 호몰로지를 계산하는 함수로 오론쯕 행렬의 각 행이 선형 독립이 되게 하고 
# 각 행의 마지막 열이 0이 안 될 때까지 계산을 지속합니다. 
# 이 알고리즘은 매우 technical 하기 때문에 이해할 필요는 없습니다. 계산을 위해 사용하고 
# 음악 분석을 위해서 cycle과 barcode를 계산하기 위한 알고리즘이라고 생각하면 되겠습니다. 
# from pHcol import *
import numpy as np
import itertools as it
import time

def generateBarcode(mat, listOfDimension = [1], numOfDivision = 1000, start = 0, end = 3, exactStep = False, truncate = True, increment = 1e-05, division = True, annotate = True, onlyFiniteInterval = False, checkExistInfty = True, birthDeathSimplex = True, sortDimension = False):
    stime = time.time()
    [boundaryMatrix, columnLabelOfSimplex] = generateBoundaryMatrix(listOfSimplexWithStep, dim =  dimensionsOfSimplex)
#     print('gettingBoundaryMatrixElements',time.time() - stime,'seconds')
    stime = time.time()
    birthDeath = pHcolGenerateRVmatrix(boundaryMatrix, columnLabelOfSimplex, listOfDimensionInput = listOfDimensionInput, annotate = annotate, onlyFiniteInterval = onlyFiniteInterval, birthDeathSimplex = birthDeathSimplex, sortDimension = sortDimension)
#     print('phColOperationTotal',time.time() - stime,'seconds')
#     print('wholeRunningTime',time.time() - otime,'seconds')
    return birthDeath

