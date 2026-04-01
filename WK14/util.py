

import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import seaborn as sns

import numpy as np
import math
import pandas as pd

from collections import Counter

import re
import os
import datetime
from tqdm import tqdm

from professor import generateBarcode
from process import group_notes_with_duration_

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

    for i in range(len(a) - j): # 1 : 0 ~ 1022 = (1024 - 1) - 1 / 2 : 0 ~ 1024 = (1026 - 1) - 1 / 3 : 0 ~ 1026 = (1028 - 1) - 1
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

def refine_connectedness(weight_mtrx, transformed_dict, power):
    """
    weight_mtrx 데이터프레임을 순회하면서 transformed_dict를 이용하여
    새로운 weight_mtrx_notes 데이터프레임을 생성합니다.

    Args:
        weight_mtrx (pd.DataFrame): 원본 weight_mtrx 데이터프레임.
        transformed_dict (dict): 변환된 딕셔너리 (key는 label, value는 frozenset).
        power : 본 함수를 is_distance_matrix_from을 통해 호출하지 않는 경우에는 0으로 두어도 무방합니다. 부동소수점 이슈 방지용

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
    weight_mtrx_refined = pd.DataFrame(0, index=unique_values, columns=unique_values, dtype=np.float64)

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
                        # weight_mtrx_refined.loc[note_i, note_j] += weight  # 부동소수점 오류 이슈로 인한 사이클 오인(...), 250511 1737
                        weight_mtrx_refined.loc[note_i, note_j] = round(weight_mtrx_refined.loc[note_i, note_j] + weight, -power)  # weight_mtrx_refined 업데이트
                        # if (note_i in focus_n) and (note_j in focus_n) and (note_i != note_j) :
                        #     print(f"weight_mtrx_refined[{note_i}, {note_j}] += {weight} (= weight_mtrx[{i}, {j}])") #디버깅용

    return weight_mtrx_refined

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

def is_distance_matrix_from(weight_mtrx, transform_dict, out_of_reach, power : int | None, refine = True) : 
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
        weight_UTM = refine_connectedness(weight_UTM, transform_dict, power = power)
    
    # 역수 변환
    distance_UTM = get_distance_matrix_from(weight_UTM, out_of_reach)

    distance_df = get_LTMpart_of(distance_UTM)

    return distance_df

def is_refined_from(timeflow_weight : pd.DataFrame, transform_dict : dict, power : int = 0) :
    """ 
     complex_distance(simul+timeflow)를 구하기 위해 timeflow weight만 refine할 때

     Args :
     timeflow_weight : intra_weights + rate * inter_weight
     transform_dict : 보통은 notes_dict
     power : 0을 디폴트로 한 이유는 refine 함수가 rate * inter_weight를 입력값으로 받을 때 부동소수점 이슈를 막으려고 넣어놓았던 거라서
       """


    timeflow_UTM = get_UTMconnected(timeflow_weight)
    timeflow_UTM = refine_connectedness(timeflow_UTM, transform_dict, 0)
    timeflow_weight_ = get_LTMpart_of(timeflow_UTM)

    return timeflow_weight_

def get_outta_reach(weight_df, power) :

    step = 10**power
    outta_reach = 1 + 2 * 1 / (weight_df[weight_df!=0].min().min() * step)

    return outta_reach

def search_timeflow_homology(adn_i : list[list], inter_lag : int, refine_dict : dict, 
                           dimension : int = 1, rate_start = 0.00, rate_end = 1.5, power = -2,
                           loglog : bool = True, output_dir = './power_search') :
    """  
    Args :
    adn_1_chord_i, adn_2_chord_i : 두 inst가 동시에 연주되는 범위에서의 화음 labelling list
      """
    
    weight_mtrx_1 = get_chords_intra_connected(adn_i[1][0])
    weight_mtrx_2 = get_chords_intra_connected(adn_i[2][0])
    intra_weights = weight_mtrx_1 + weight_mtrx_2

    inter_weight = get_chords_inter_connected(adn_i[1][inter_lag], adn_i[2][inter_lag], lag=inter_lag)
    outta_reach_t = get_outta_reach(inter_weight, power = power)
    
    step = 10**power
    start = round(rate_start / step)
    end = round(rate_end / step)

    homology_profile = []

    for a in range(start, end, 1) :

        rate = round(a * step, -power)
        if a % 10 == 0 :
            print(f"on rate {rate}...")

        timeflow_weight = intra_weights + rate * inter_weight 
        timeflow_distance = is_distance_matrix_from(timeflow_weight, refine_dict, out_of_reach = outta_reach_t, power = power)

        birthDeath = generateBarcode(mat = timeflow_distance.values, listOfDimension = [dimension], 
                                     exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result_1 = (rate, birthDeath)
        homology_profile.append(result_1)

    homol_info = analyze_lifespans(homology_profile, out_of_reach=outta_reach_t)

    plot_lifespan_results(homol_info, refine_dict = refine_dict, inter_lag = inter_lag, power = power, 
                          dim = dimension, rate_start = rate_start, rate_end = rate_end, 
                          loglog=loglog, type = 't', output_dir = output_dir)

    return homology_profile, outta_reach_t

def search_simul_cycles(adn_i : list[list], refine_dict : dict,
                        dimension : int = 1, rate_start = 0.00, rate_end = 1.5, power = -2,
                        loglog : bool = False, output_dir = './power_search') :
    
    """ 
     Args :
    adn_1_chord_, adn_2_chord_ : 같은 길이의 두 inst 전체 화음 labelling list 
       """

    simul_intra, simul_inter = get_simul_connected(adn_i[1][-1], adn_i[2][-1], refine_dict)
    step = 10**power
    start = round(rate_start / step)
    end = round(rate_end / step)

    homology_profile = []

    temp = step * simul_inter
    outta_reach_s = 1 + 2 * 1 / temp[temp!=0].min().min()

    for a in range(start, end, 1) :

        rate = round(a * step, 4)
        if a % 10 == 0 :
            print(f"on rate {rate}...")

        # weight 구하는 부분
        simul_weight = simul_intra + rate * simul_inter
        
        # 거리 구하는 부분 
        simul_distance = is_distance_matrix_from(simul_weight, transform_dict = None, out_of_reach = outta_reach_s, power = None, refine = False)

        birthDeath = generateBarcode(mat = simul_distance.values, listOfDimension = [dimension],
                                     exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result = (rate, birthDeath)
        homology_profile.append(result)

    homol_info = analyze_lifespans(homology_profile, outta_reach_s)

    plot_lifespan_results(homol_info, refine_dict = refine_dict, inter_lag = None, power = power, 
                          dim = dimension, rate_start = rate_start, rate_end = rate_end, 
                          loglog=loglog, type = 's', output_dir = output_dir)


    return homology_profile, outta_reach_s

def search_complex_homology(adn_i : list[list], inter_lag_t : int, refine_dict : dict,
                          rate_t : float, rate_s : float, dimension = 1,
                          rate_start_c = 0.0, rate_end_c = 0.5, rate_power_c : int = -2,
                          loglog = True, output_dir = './power_search') :

    # timeflow (intra)
    weight_mtrx_1 = get_chords_intra_connected(adn_i[1][0])
    weight_mtrx_2 = get_chords_intra_connected(adn_i[2][0])
    intra_weights = weight_mtrx_1 + weight_mtrx_2

    # timeflow (inter)
    inter_lag_t = 1
    inter_weight = get_chords_inter_connected(adn_i[1][inter_lag_t], adn_i[2][inter_lag_t], lag=inter_lag_t)

    # simul (intra & inter)
    simul_intra, simul_inter = get_simul_connected(adn_i[1][-1], adn_i[2][-1], refine_dict)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

    timeflow_weight = intra_weights + rate_t * inter_weight 
    timeflow_weight_ = is_refined_from(timeflow_weight, refine_dict)

    simul_weight_ = simul_intra + rate_s * simul_inter

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

    outta_reach = get_outta_reach(simul_weight_, power = rate_power_c)

    step = 10**rate_power_c
    start = round(rate_start_c / step)
    end = round(rate_end_c / step)

    homol_profile = []

    for a in range(start, end, 1) :

        rate = round(a * step, -rate_power_c)
        if a % 10 == 0 :
            print(f"on rate {rate}...")

        complex_weight = timeflow_weight_ + rate * simul_weight_ 
        complex_distance = get_distance_matrix_from(complex_weight, outta_reach)

        birthDeath = generateBarcode(mat = complex_distance.values, listOfDimension = [dimension],
                                     exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result = (rate, birthDeath)
        homol_profile.append(result)

    homol_info = analyze_lifespans(homol_profile, out_of_reach=outta_reach)

    plot_lifespan_results(homol_info, refine_dict = refine_dict, inter_lag = inter_lag_t, power = rate_power_c, 
                          dim = dimension, rate_start = rate_start_c, rate_end = rate_end_c, 
                          loglog=loglog, type = 'c', output_dir = output_dir, rate_t = rate_t, rate_s = rate_s)


    return homol_profile, outta_reach

def catch_intersection(homol_persistence_1, homol_persistence_2, homol_persistence_3, homol_persistence_4, dim : int) :
    
    """  
   Args 
   : lag 1~4에 해당하는 특정 차원(dim)의 호몰로지 rBD pkl파일을 'homol_rBD_from_pkl' 함수를 통해 읽어온 것.
    lag 1~4에 해당하는 것이 있으려면 type = t(timeflow) | c(complex = timeflow + simul)이여야 한다. 
    
      """

    if dim == 1:
        name = 'cycle'

        homol_1 = []
        for homol in homol_persistence_1.keys():
            homol_1.append(homol)
        homol_1 = set(homol_1)

        homol_2 = []
        for homol in homol_persistence_2.keys():
            homol_2.append(homol)
        homol_2 = set(homol_2)

        homol_3 = []
        for homol in homol_persistence_3.keys():
            homol_3.append(homol)
        homol_3 = set(homol_3)

        homol_4 = []
        for homol in homol_persistence_4.keys():
            homol_4.append(homol)
        homol_4 = set(homol_4)

    elif dim == 2 :
        name = 'void'

        homol_1 = []
        for homol in homol_persistence_1.keys():
            homol_1.append(homol)
        homol_1 = set(homol_1)

        homol_2 = []
        for homol in homol_persistence_2.keys():
            homol_2.append(homol)
        homol_2 = set(homol_2)

        homol_3 = []
        for homol in homol_persistence_3.keys():
            homol_3.append(homol)
        homol_3 = set(homol_3)

        homol_4 = []
        for homol in homol_persistence_4.keys():
            homol_4.append(homol)
        homol_4 = set(homol_4)

    homol_12 = homol_1.intersection(homol_2)
    homol_13 = homol_1.intersection(homol_3)
    homol_14 = homol_1.intersection(homol_4)
    homol_23 = homol_2.intersection(homol_3)
    homol_24 = homol_2.intersection(homol_4)
    homol_34 = homol_3.intersection(homol_4)

    homol_123 = homol_12.intersection(homol_3)
    homol_124 = homol_12.intersection(homol_4)
    homol_134 = homol_13.intersection(homol_4)
    homol_234 = homol_23.intersection(homol_4)

    homol_1234 = homol_12.intersection(homol_34)

    print(f"Lag 1, 2, 3, 4 모두에서 발견되는 {name} : {homol_1234}")

    print(f"the number of {name}s in each lags are", len(homol_1), len(homol_2), len(homol_3), len(homol_4), "\n")

    if homol_1 - homol_12 - homol_13 - homol_14 :
        print(f"Lag 1에서만 발견되는 {name} : {homol_1 - homol_12 - homol_13 - homol_14}")
    if homol_2 - homol_12 - homol_23 - homol_24 :
        print(f"Lag 2에서만 발견되는 {name} : {homol_2 - homol_12 - homol_23 - homol_24}")
    if homol_3 - homol_13 - homol_23 - homol_34 :
        print(f"Lag 3에서만 발견되는 {name} : {homol_3 - homol_13 - homol_23 - homol_34}")
    if homol_4 - homol_14 - homol_24 - homol_34 :
        print(f"Lag 4에서만 발견되는 {name} : {homol_4 - homol_14 - homol_24 - homol_34}")
        print("\n")
    
    if homol_12 - homol_123 - homol_124 :
        print(f"Lag 1, 2에서 발견되고 3, 4에서 발견되지 않는 {name} : {homol_12 - homol_123 - homol_124}")
    if homol_13 - homol_123 - homol_134 :
        print(f"Lag 1, 3에서 발견되고 2, 4에서 발견되지 않는 {name} : {homol_13 - homol_123 - homol_134}")
    if homol_14 - homol_124 - homol_134 :
        print(f"Lag 1, 4에서 발견되고 2, 3에서 발견되지 않는 {name} : {homol_14 - homol_124 - homol_134}")
    if homol_23 - homol_123 - homol_234 :
        print(f"Lag 2, 3에서 발견되고 1, 4에서 발견되지 않는 {name} : {homol_23 - homol_123 - homol_234}")
    if homol_24 - homol_124 - homol_234 :
        print(f"Lag 2, 4에서 발견되고 1, 3에서 발견되지 않는 {name} : {homol_24 - homol_124 - homol_234}")
    if homol_34 - homol_134 - homol_234 :
        print(f"Lag 3, 4에서 발견되고 1, 2에서 발견되지 않는 {name} : {homol_34 - homol_134 - homol_234}")
        print("\n")
    
    if homol_123 - homol_1234 :
        print(f"Lag 1, 2, 3에서 발견되고 4에서 발견되지 않는 {name} : {homol_123 - homol_1234}")
    if homol_124 - homol_1234 :
        print(f"Lag 1, 2, 4에서 발견되고 3에서 발견되지 않는 {name} : {homol_124 - homol_1234}")
    if homol_134 - homol_1234 :
        print(f"Lag 1, 3, 4에서 발견되고 2에서 발견되지 않는 {name} : {homol_134 - homol_1234}")
    if homol_234 - homol_1234 :
        print(f"Lag 2, 3, 4에서 발견되고 1에서 발견되지 않는 {name} : {homol_234 - homol_1234}")
        print("\n")
    
    print(f"Lag 1, 2, 3, 4 모두에서 발견되는 {len(homol_1234)}개의 {name} : {homol_1234}")

    homol_12_u = homol_1.union(homol_2)
    homol_34_u = homol_3.union(homol_4)
    homol_1234_u = homol_12_u.union(homol_34_u)

    return homol_1, homol_2, homol_3, homol_4, homol_1234, homol_1234_u


def get_correct_df(nodes_list : list, simul_musical_units : list):
    """
    딕셔너리의 값들을 합집합하여 컬럼명으로 사용하고, 리스트의 각 요소를 기준으로 DataFrame을 생성합니다.

    Args:
        dict_values: 딕셔너리의 값 (set)을 포함하는 dict_values 객체.
        simul_musical_units: set을 요소로 가지는 리스트.

    Returns:
        생성된 pandas DataFrame.
    """

    # # # 컬럼명 생성 (딕셔너리 값들의 합집합)
    # # all_notes = set()
    # # dict_values = transform_dict.values()
    # # for notes_set in dict_values:
    # #     if type(notes_set) == set :
    # #         all_notes.update(notes_set)  # 합집합 연산

    # # columns = sorted(list(all_notes))  # 정렬된 컬럼명 리스트
    

    # 원래는 transform_dict를 입력받다가 
    # Music Class에서 Overlap_mtrx 짤 때 dependency가 너무 많아지는 것 같아서
    # pitches_dict이나 pitch_classes_dict는 잘 안 사용할 것 같으니까.
    columns = nodes_list 

    # DataFrame 생성
    data = []
    for notes_set in simul_musical_units:
        row = [1 if col in notes_set else 0 for col in columns]  # 각 컬럼에 대해 1 또는 0 설정
        data.append(row)

    df = pd.DataFrame(data, columns=columns)  # DataFrame 생성

    return df

def get_scattered_cycles_df(df : pd.DataFrame, cycle_labeled : dict | list, binary : bool = True):
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

    if type(cycle_labeled) == dict :
        if binary :
            for label, cycle in cycle_labeled.items():
                # 사이클에 해당하는 컬럼명 추출
                cycle_node_indices = [col + 1 for col in cycle]  # 컬럼명 리스트 생성

                # sub_df 생성 (cycle에 해당하는 컬럼만 추출)
                sub_df = df[cycle_node_indices]

                # cycle_df 생성 (각 행에서 1로 표시된 컬럼들을 set으로 저장)
                cycle_dfs[label] = sub_df.apply(lambda row: 1 if row.sum() > 0 else 0, axis=1)
        else :
            for label, cycle in cycle_labeled.items():
                cycle_node_indices = [col + 1 for col in cycle]
                sub_df = df[cycle_node_indices]

                cycle_dfs[label] = sub_df.apply(lambda row: set(row[row == 1].index), axis=1)

    elif type(cycle_labeled) == list : 
        if binary :
            for label in range(len(cycle_labeled)):

                cycle = cycle_labeled[label]
                cycle_node_indices = [col + 1 for col in cycle]
                sub_df = df[cycle_node_indices]
                cycle_dfs[label] = sub_df.apply(lambda row: 1 if row.sum() > 0 else 0, axis=1)
        
        else :
            for label in range(len(cycle_labeled)):

                cycle = cycle_labeled[label]
                cycle_node_indices = [col + 1 for col in cycle]
                sub_df = df[cycle_node_indices]
                cycle_dfs[label] = sub_df.apply(lambda row: set(row[row == 1].index), axis=1)

    else : 
        raise TypeError("2nd argmuent should be list or dict containing cycles")

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

def merge_sequential_homol_rBD(dict1, dict2):
    """
    두 딕셔너리를 합쳐서 새로운 딕셔너리를 반환합니다.
    각 키에 대한 값은 (a, b, c) 형태의 튜플로 구성된 리스트이고, a 값을 기준으로 정렬되어 있습니다.
    겹치는 키에 대해서는 dict2의 첫 번째 튜플의 a 값이 dict1의 마지막 튜플의 a 값보다 크다는 조건을 만족합니다.
    """
    merged_dict = dict1.copy()  # dict1을 복사하여 merged_dict를 만듭니다.

    for key, value2 in dict2.items():
        if key in merged_dict:
            # 겹치는 키인 경우, dict1의 값(value1)과 dict2의 값(value2)을 합칩니다.
            value1 = merged_dict[key]
            merged_dict[key] = value1 + value2  # 두 리스트를 연결합니다.
        else:
            # 겹치지 않는 키인 경우, dict2의 키와 값을 merged_dict에 추가합니다.
            merged_dict[key] = value2

    return merged_dict

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

def check_cycle_if_plausible(cycles_df : pd.DataFrame, column_idx : int, 
                            cycle_labeled : dict | list, binary : bool = False) :
                            # cycle_labeled : dict, notes_counts, notes_label : dict) :

    cycle_to_see = [vertex_label + 1 for vertex_label in cycle_labeled[column_idx]]

    # notes_freq_in_a_module = notes_label_counts(notes_label, notes_counts)

    # filtered_dict = {key: notes_freq_in_a_module[key] for key in cycle_to_see if key in notes_freq_in_a_module}
    # filtered_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1], reverse=True))

    # for label, count in filtered_dict.items():
    #     print(f"label: {label}, 등장횟수: {count}")
    
    if not binary :
        indices_of_ones = cycles_df[cycles_df[column_idx] != set()].index
    else :
        indices_of_ones = cycles_df[cycles_df[column_idx] != 0].index

    rows_where_ith_cycle_found = cycles_df.loc[indices_of_ones, column_idx].to_frame()
    rows_where_ith_cycle_found.rename(columns={column_idx: str(cycle_to_see)}, inplace=True)

    return rows_where_ith_cycle_found

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

def plot_lifespan_results(lifespan_results, refine_dict : dict, inter_lag : int, power : int,
                          dim : int, rate_start : float = 0.0, rate_end : float = 1.5,
                          loglog=True, figsize_ = (6,4), type = 't', output_dir : str | None = "./power_search",
                          rate_t = None, rate_s = None):
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

    date = get_now("%Y%m%d")
    if type == 'c' :  
        title_string = f'{date}_h{dim}_{type}_{title_prefix}_1e{power}_{rate_start}_{rate_end}_t{rate_t}_s{rate_s}_'
    else :
        title_string = f'{date}_h{dim}_{type}_{title_prefix}_1e{power}_{rate_start}_{rate_end}_'

    if output_dir is not None :
        os.makedirs(output_dir, exist_ok=True)  # 디렉토리가 없으면 생성

    # Counts plot
    plt.figure(figsize = figsize_)  # 새로운 Figure 생성
    plt.plot(rates, counts) 
    plt.title(f"{title_prefix} count of {dim}D homology")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel(f"# {dim}D homology")
    plt.grid(True)  # Added grid for better readability
    if output_dir is not None :
        filename_1 = title_string + 'num.png'
        filepath_1 = os.path.join(output_dir, filename_1)
        plt.savefig(filepath_1)
    plt.show()

    # Mean plot
    plt.figure(figsize = figsize_)  # 새로운 Figure 생성
    if loglog:  
        plt.loglog(rates, means)
    else:
        plt.plot(rates, means)  
    plt.title(f"{title_prefix} Mean Lifespan")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("filtration value")
    plt.grid(True)  
    if output_dir is not None :
        filename_2 = title_string + 'mean.png'
        filepath_2 = os.path.join(output_dir, filename_2)
        plt.savefig(filepath_2)
    plt.show()

    # Std Dev plot
    plt.figure(figsize = figsize_)  # 새로운 Figure 생성
    if loglog:
        plt.loglog(rates, stds)
    else:
        plt.plot(rates, stds)
    plt.title(f"{title_prefix} Std of Lifespans")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("filtration value")
    plt.grid(True)  
    if output_dir is not None :
        filename_3 = title_string + 'std.png'
        filepath_3 = os.path.join(output_dir, filename_3)
        plt.savefig(filepath_3)
    plt.show()

    # Max Lifespan plot
    plt.figure(figsize = figsize_)  # 새로운 Figure 생성
    if loglog:
        plt.loglog(rates, max_lifes)
    else:
        plt.plot(rates, max_lifes)
    plt.title(f"{title_prefix} Max Lifespan")
    plt.xlabel("inter_weight / intra_weights")
    plt.ylabel("filtration value")
    plt.grid(True)  
    if output_dir is not None :
        filename_4 = title_string + 'max.png'
        filepath_4 = os.path.join(output_dir, filename_4)
        plt.savefig(filepath_4)
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

    return [(key + 1, count) for key, count in counts.most_common()] # counts.most_common() 

def get_cycles_scaled(cycles_weak : pd.DataFrame, cycle_labeled : dict | list, goal : float, lower_bound : float | None) :

    for_overlap = []

    if lower_bound is None :
        lower_bound = np.max([0.0, goal - 0.1])

    elif lower_bound > goal :
        raise ValueError("Lower bound must be smaller than threshold")

    if type(cycle_labeled) == dict :
        for cycle_idx in cycle_labeled.keys():
            cons_indicies, scale, scale_reduction = get_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, goal, lower_bound)
            for_overlap.append((cycle_idx, cons_indicies))
    
    elif type(cycle_labeled) == list :
        for cycle_idx in range(len(cycle_labeled)):
            cons_indicies, scale, scale_reduction = get_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, goal, lower_bound)
            for_overlap.append((cycle_idx, cons_indicies))
    
    else :
        raise TypeError("2nd argmuent should be of list or dict type containing cycles")


    return for_overlap

def get_score_for_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, threshold, lower_bound) :

    cons_indicies, scale, _ = get_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, threshold, lower_bound)

    # Series를 DataFrame으로 변환
    cycle_to_see = [vertex_label + 1 for vertex_label in cycle_labeled[cycle_idx]]
    # print(f"Working on {cycle_idx+1}th / {len(cycle_labeled)} cycle : {cycle_to_see}")
    for_score = (cycle_to_see, cons_indicies, scale)

    return for_score

def get_scores_for_cycle_scaled(cycles_weak : pd.DataFrame, cycle_labeled : dict, goal : float, lower_bound : float | None, 
                                indices_2_check : list[int] | None) :

    for_scores = dict()

    if lower_bound is None :
        lower_bound = np.max([0.0, goal - 0.1])

    if not indices_2_check :
        for cycle_idx in cycle_labeled.keys():
            for_score = get_score_for_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, goal, lower_bound)
            for_scores[cycle_idx] = for_score
    else :
        for cycle_idx in indices_2_check:
            for_score = get_score_for_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, goal, lower_bound)
            for_scores[cycle_idx] = for_score

    return for_scores

def get_cycle_labeled_asc(cycle_persistence : dict) :

    def custom_sort_key(cycle):
        return (cycle[0], cycle[1], cycle[2], cycle[3])  # 1 ~ 3번째 사이클의 Vertex label 요소를 기준으로 정렬

    cycle_keys = sorted(cycle_persistence.keys(), key=custom_sort_key)
    # cycle_keys = sorted(cycle_persistence.keys(), key=lambda x: x[0])
    # cycle_labeled = {i: cycle for i, cycle in enumerate(cycle_persistence.keys())}
    cycle_labeled = {i: cycle for i, cycle in enumerate(cycle_keys)}

    return cycle_labeled

def label_cycle(cycle_persistence : dict, transform_dict : dict,
                info = True, log = False) :

    cycle_labeled = get_cycle_labeled_asc(cycle_persistence)

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

def construct_overlap_df(overlap_data, length = 1088):
    """
    overlap_data 리스트로부터 데이터프레임을 생성합니다.

    Args:
        overlap_data (list): (컬럼 인덱스, 1로 설정해야 하는 인덱스 리스트) 튜플의 리스트.
        length (int): 데이터프레임의 전체 행 길이.

    Returns:
        pandas.DataFrame: 생성된 데이터프레임.
    """

    # 데이터 초기화 (모든 값이 0인 데이터프레임 생성)
    df = pd.DataFrame(0, index=range(length), columns=[item[0] for item in overlap_data])

    # 각 overlap 데이터에 대해 컬럼을 채우기
    for column_index, indices_list in overlap_data:
        # 1로 설정해야 하는 인덱스들을 데이터프레임에 반영
        for indices in indices_list:
            df.loc[indices, column_index] = 1

    return df

def construct_OM_at_once(s1 : list[list[tuple[int]]], notes_label : dict, node_indices : list[int], cycle_labeled_ : dict | list, threshold : float) :

    """  
     Args 
       """

    active_notes_by_onset_1 = group_notes_with_duration_(s1[0])
    active_notes_by_onset_2 = group_notes_with_duration_(s1[1])
    active_notes_by_onset = union_values_for_common_keys(active_notes_by_onset_1, active_notes_by_onset_2)
    simul_notes = get_simul_notes(active_notes_by_onset, notes_label)
    generated_df = get_correct_df(node_indices, simul_notes) # 노드 관점에서 모델 학습 중 마지막에 대조하는 데 쓰이는 정답지

    cycles_binary = get_scattered_cycles_df(df = generated_df, cycle_labeled = cycle_labeled_, binary = True)

    for_overlap = get_cycles_scaled(cycles_binary, cycle_labeled_, threshold, None)

    last_ts1 = [s1[0][i][2] for i in range(-5, 0, 1)]
    last_ts2 = [s1[1][i][2] for i in range(-5, 0, 1)]
    last_ts = [*last_ts1, *last_ts2]

    overlapped_cycles = construct_overlap_df(for_overlap, length = np.max(last_ts))
    # overlap_matrix_ = overlapped_cycles_.to_numpy() 

    return overlapped_cycles

def get_rBD_groupedBy_homol(homology_profile: list, dim : int = 1) -> dict:
    """
    homology_profile 리스트를 순회하면서 사이클 별로 (rate, birth, death) 정보를 담는 딕셔너리를 생성합니다.
    """
    homology_persistence = {}

    for rate_data in homology_profile:
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
            if dim == 1 :
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
                # if len(cycle_representation) >= 4:
                if cycle_representation[0] == cycle_representation[-1]:
                    cycle_representation.pop()  # 마지막 원소 제거

                cycle_key = tuple(cycle_representation) # 튜플로 변환
                if cycle_key not in homology_persistence:
                    homology_persistence[cycle_key] = []
                homology_persistence[cycle_key].append((rate, birth, death))
                # else :
                #     print("cycle of length shorter than 4 detected?!")                

            elif dim == 2:
                edges = re.findall(r'([+-])\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', edges_str)

                # # 숫자들을 추출하여 집합을 만듭니다.
                # nodes = set()
                # for sign, v1, v2, v3 in edges:
                #     nodes.add(int(v1))
                #     nodes.add(int(v2))
                #     nodes.add(int(v3))

                    # 숫자들을 추출하여 순서를 고려한 튜플의 집합을 만듭니다.
                simp = set()
                for sign, v1, v2, v3 in edges:
                    v1, v2, v3 = int(v1), int(v2), int(v3)  # 문자열을 정수로 변환
                    if sign == '+':
                        simp.add((v1, v2, v3))
                    else:
                        simp.add((v3, v2, v1))

                h2_key = frozenset(simp)  # frozenset으로 변환
                # h2_key = tuple(nodes) # 튜플로 변환

                if h2_key not in homology_persistence:
                    homology_persistence[h2_key] = []
                homology_persistence[h2_key].append((rate, birth, death))

    return homology_persistence

def homol_rBD_to_pkl(homol_persistence : dict, refine_dict : dict, inter_lag_t : int | None,
                     dim : int, rate_start : float, rate_end : float, power : int,
                     type : str, output_dir : str = "./pickle", rate_t = None, rate_s = None):
    """
    딕셔너리 형태의 데이터를 Pandas dictFrame으로 변환합니다.

    Args:
    homol_persistence: homology(e.g. cycle, void)를 구성하는 vertex label들을 key로, 
            rate, birth, death 튜플의 리스트를 value로 가지는 딕셔너리.
            get_rBD_groupedBy_homol의 리턴값

    Returns:
    Pandas dataFrame.
    """

    rows = []
    for cycle, rBD_list in homol_persistence.items():
        for rate, birth, death in rBD_list:
            rows.append({'cycle': cycle, 'rate': float(rate), 'birth': float(birth), 'death': float(death)})

    df = pd.DataFrame(rows)

    name = refine_dict['name']

    if type == 't' :
        if inter_lag_t is None :
            raise ValueError("to save timeflow homology rBD, inter lag should be specified.")
        else :
            if (rate_start is None) or (rate_end is None) : 
                raise ValueError("to save timeflow homology rBD, rate range should be specified by rate_start and rate_end.")

            else :
                filename = f'h{dim}_rBD_{type}_{name}{inter_lag_t}_1e{power}_{rate_start}~{rate_end}.pkl'
                filepath = os.path.join(output_dir, filename)  # 폴더 경로와 파일 이름 결합
                df.to_pickle(filepath)  # pickle로 저장
                print(f"Pickle 파일 '{filename}'가 성공적으로 생성되었습니다.")


    elif type == 's' :
        filename = f'h{dim}_rBD_{type}_{name}_1e{power}.pkl'
        filepath = os.path.join(output_dir, filename)  # 폴더 경로와 파일 이름 결합
        df.to_pickle(filepath)  # pickle로 저장
        print(f"Pickle 파일 {filename}가 성공적으로 생성되었습니다.")


    elif type == 'c' :
        if (rate_t is None) or (rate_s is None) :
            raise ValueError("to save complex homology rBD, ratio of inter weight to intra weights should be specified in both sense of timeflow and simul.")
        else :
            filename = f'h{dim}_rBD_{type}_{name}{inter_lag_t}_1e{power}_{rate_start}~{rate_end}_t{rate_t}_s{rate_s}.pkl'
            filepath = os.path.join(output_dir, filename)  # 폴더 경로와 파일 이름 결합
            df.to_pickle(filepath)  # pickle로 저장
            print(f"Pickle 파일 '{filename}'가 성공적으로 생성되었습니다.")


    return df

def homol_rBD_from_pkl(pkl_file, dir="./pickle"):
    """
    Pickle 파일을 읽어 딕셔너리 형태로 변환합니다.

    Args:
        pkl_file: Pickle 파일 경로.

    Returns:
        cycle을 구성하는 vertex label들을 key로, 
        rate, birth, death 튜플의 리스트를 value로 가지는 딕셔너리.
    """

    filepath = os.path.join(dir, pkl_file)  # 폴더 경로와 파일 이름 결합
    df = pd.read_pickle(filepath)
    dict_rBD = {}

    for index, row in df.iterrows():
        vertex_labels = row['cycle']  # 이미 튜플 형태일 것이므로 변환 불필요
        rate = row['rate']
        birth = row['birth']
        death = row['death']

        # 딕셔너리에 데이터 추가
        if vertex_labels not in dict_rBD:
            dict_rBD[vertex_labels] = []
        dict_rBD[vertex_labels].append((rate, birth, death))

    return dict_rBD

def find_cycles_with_simul_intersection(cycles, notes_dict):
    """
    cycles 딕셔너리에서 notes_dict의 어떤 value와도 교집합 크기가 2 이상인 cycle을 찾고,
    해당 cycle에 대해 notes_dict에서 몇 번 key와 교집합이 크게 나타나는지 출력합니다.

    Args:
        cycles: cycle을 나타내는 튜플의 집합입니다.
        notes_dict: 각 key에 대한 음표(노트) 집합을 나타내는 딕셔너리입니다.

    Returns:
        notes_dict의 어떤 value와도 교집합 크기가 2 이상인 cycle의 리스트,
        그리고 각 cycle에 대해 교집합이 크게 나타나는 key 번호의 리스트를 담은 튜플입니다.
    """
    significant_cycles = []
    intersection_keys = []

    for cycle in cycles:
        chord_keys = []  # 현재 cycle에 대한 key 번호 리스트

        for chord_key, note_set in notes_dict.items():
            intersection = set(cycle).intersection(note_set)  # cycle과 note_set의 교집합 계산

            if len(intersection) >= 2:  # 교집합 크기가 2 이상이면
                chord_keys.append(chord_key)  # 해당 key 번호를 리스트에 추가

        if chord_keys:  # cycle에 대해 교집합 크기가 2 이상인 key가 하나라도 있으면
            significant_cycles.append(cycle)  # 결과 리스트에 추가
            intersection_keys.append(chord_keys)  # key 번호 리스트를 결과 리스트에 추가

    return significant_cycles, intersection_keys

def find_differences(dict1, dict2):
    """
    두 딕셔너리의 값을 비교하여 다른 부분을 찾아 출력합니다.

    Args:
        dict1: 첫 번째 딕셔너리
        dict2: 두 번째 딕셔너리
    """

    # 키가 다른 경우
    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())
    if keys1 != keys2:
        print("키가 다릅니다!")
        print("dict1에만 있는 키:", keys1 - keys2)
        print("dict2에만 있는 키:", keys2 - keys1)
        return  # 키가 다르면 값 비교는 의미가 없으므로 종료

    # 키가 같은 경우 값 비교
    for key in dict1:
        value1 = dict1[key]
        value2 = dict2[key]

        if value1 != value2:
            print(f"키 '{key}'에 대한 값이 다릅니다.")

            # 값의 타입 확인
            print(f"dict1['{key}']의 타입: {type(value1)}")
            print(f"dict2['{key}']의 타입: {type(value2)}")

            # 값의 길이 확인 (리스트인 경우)
            if isinstance(value1, list) and isinstance(value2, list):
                if len(value1) != len(value2):
                    print(f"길이가 다릅니다. dict1: {len(value1)}, dict2: {len(value2)}")
                else:
                    # 리스트의 각 요소 비교
                    for i in range(len(value1)):
                        if value1[i] != value2[i]:
                            print(f"인덱스 {i}에서 값이 다릅니다.")
                            print(f"dict1: {value1[i]} (타입: {type(value1[i])})")
                            print(f"dict2: {value2[i]} (타입: {type(value2[i])})")
            else:
                print(f"dict1: {value1}")
                print(f"dict2: {value2}")

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

def split_cycles_by_consecutive(cycle_persistence: dict, out_of_reach: float | None, power: int = -2) -> dict:
    """
    Args:
        cycle_persistence: cycle 데이터를 담고 있는 딕셔너리.
        out_of_reach: 'infty' 값을 대체할 값, pickle 파일에서 읽어온 경우 이미 처리되어 있으므로 None을 택한다.
        power: 연속성을 판단하는 기준이 되는 step 값의 지수 (default: -2, step=0.01).

    Returns:
        non_consecutive_cycles: 불연속적인 cycle 데이터를 담은 딕셔너리.
        consecutive_cycles: 연속적인 cycle 데이터를 담은 딕셔너리.
    """
    step = 10**power
    non_consecutive_cycles = {}
    consecutive_cycles = {}

    for cycle, rBD_list in cycle_persistence.items():
        # is_cycle_consecutive = True # cycle이 연속적인지 여부를 나타내는 변수
        new_rBD_list = []
        is_non_consecutive = False
        # print(f"cycle {cycle}")
        for i in range(len(rBD_list) - 1):
            diff = round(rBD_list[i + 1][0] - rBD_list[i][0], -power + 4)  # 소수점 6자리까지 반올림하여 비교
            if abs(diff - step) > 10**(power-4):  # 부동 소수점 오차 고려
                # print(f"rate differs for {diff} ({rBD_list[i][0]} ~ {rBD_list[i+1][0]})")
                is_non_consecutive = True # 불연속적인 구간이 있음을 표시
                # is_cycle_consecutive = False # cycle이 불연속적임을 표시

            rate, birth, death = rBD_list[i]
            if death == 'infty':
                new_death = out_of_reach
            else:
                new_death = death
            new_rBD_list.append((rate, birth, new_death))

        # 마지막 rBD 값 처리
        rate, birth, death = rBD_list[-1]
        if death == 'infty':
            new_death = out_of_reach
        else:
            new_death = death
        new_rBD_list.append((rate, birth, new_death))

        if is_non_consecutive:
            non_consecutive_cycles[cycle] = tuple(new_rBD_list)
        else:
             consecutive_cycles[cycle] = tuple(new_rBD_list)

    # 연속적인 cycle을 찾기 위해 non_consecutive_cycles에 없는 cycle을 찾아서 추가하는 로직은 제거됨.
    # 이미 위 반복문에서 cycle이 연속적인지 불연속적인지 판단하여 각각의 딕셔너리에 저장했기 때문.

    return non_consecutive_cycles, consecutive_cycles

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

def specify_chord_list(chord_list : list[int], specify_dict : dict) -> list[set[int]]:

    module_notes = []
    for chord_label in chord_list:
        if chord_label in specify_dict:
            module_notes.append(specify_dict[chord_label])
        else:
            module_notes.append(None)  # 키가 딕셔너리에 없으면 None을 사용

    return module_notes

def get_simul_connected(inst1_whole_chord : list[int], inst2_whole_chord : list[int], specify_dict : dict, log = False):

    inst1_specified = specify_chord_list(inst1_whole_chord, specify_dict)
    inst2_specified = specify_chord_list(inst2_whole_chord, specify_dict)
    song_of_two_inst_specified = list(zip(inst1_specified, inst2_specified)) # 해당 노래는 inst 2개로 이뤄져있어야 함.

    unique_values = extract_unique_values_int_keys(specify_dict)

    simul_intra = get_simul_intra_connected2(unique_values, song_of_two_inst_specified, exclude=True, log = log)
    simul_inter = get_simul_inter_connected2(unique_values, song_of_two_inst_specified, log = log)

    # simul_intra = get_simul_intra_connected(unique_values, song_of_two_inst_specified)
    # simul_inter = get_simul_inter_connected2(unique_values, song_of_two_inst_specified)

    return simul_intra, simul_inter

def plot_homol_BirthDeath_over_rate(cycle_persistence: dict, subplot_in_a_row : int = 3, power = -2):
    """
    cycle_persistence 딕셔너리를 입력받아 각 사이클의 persistence diagram을 시각화합니다.

    Args:
      cycle_persistence: create_cycle_data 함수의 결과 딕셔너리.
    """

    rate = 10**power
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
            if round(rates[j+1] - rates[j], -power) == rate:
                ax.plot(rates[j:j+2], births[j:j+2], marker='o', linestyle='-', color='blue')
            else:
                ax.plot(rates[j], births[j], marker='o', color='blue')
        if rates.size > 0:
            ax.plot(rates[-1], births[-1], marker='o', color = 'blue') # 마지막 점

        # Death 시각화
        for j in range(len(rates) - 1):
            if round(rates[j+1] - rates[j], -power) == rate:
                ax.plot(rates[j:j+2], deaths[j:j+2], marker='x', linestyle='-', color='orange')
            else:
                ax.plot(rates[j], deaths[j], marker='x',  color='orange')
        if rates.size > 0:
            ax.plot(rates[-1], deaths[-1], marker='x', color = 'orange') # 마지막 점

        # 그래프 제목 및 축 레이블 설정
        if type(cycle) == frozenset :
            ax.set_title(f"Voids {set(cycle)}")
        else :
            ax.set_title(f"Cycle {cycle}")
        ax.set_xlabel("Rate")
        ax.set_ylabel("Filtration Value")

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

def check_commutivity(inter_weight, intra_weights, refine_dict, outta_reach_t, distance_df) :

    ### inter_weight, intra_weights 각각 refine하고 더해서 거리 구하는 버전

    inter_UTM = get_UTMconnected(inter_weight)
    inter_UTM_ = refine_connectedness(inter_UTM, refine_dict)

    intra_UTM = get_UTMconnected(intra_weights)
    intra_UTM_ = refine_connectedness(intra_UTM, refine_dict)

    weight_UTM_ = intra_UTM_ + inter_UTM_

    distance_UTM_ = get_distance_matrix_from(weight_UTM_, outta_reach_t)
    distance_df_ = get_LTMpart_of(distance_UTM_)

    print("inter_weight, intra_weights 각각 refine하고 그것을 더해서 구한 거리는 기존 방식으로 구한 거리와 같다 :")
    print((distance_df_ == distance_df).sum().sum() == distance_df.shape[0] * distance_df.shape[1])

    ### inter_weight, intra_weights 각각 refine하고 거리까지 구해서 더하는 버전

    inter_UTM = get_UTMconnected(inter_weight)
    inter_UTM_ = refine_connectedness(inter_UTM, refine_dict)
    distance_UTM_inter = get_distance_matrix_from(inter_UTM_, outta_reach_t)

    intra_UTM = get_UTMconnected(intra_weights)
    intra_UTM_ = refine_connectedness(intra_UTM, refine_dict)
    distance_UTM_intra = get_distance_matrix_from(intra_UTM_, outta_reach_t)

    distance_UTM_ = distance_UTM_inter + distance_UTM_intra
    distance_df__ = get_LTMpart_of(distance_UTM_)

    print("inter_weight, intra_weights 각각을 refine하고 거리까지 구해서 더해서 얻어진 거리는 기존 방식으로 구한 거리와 같다 :")
    print((distance_df__ == distance_df).sum().sum() == distance_df.shape[0] * distance_df.shape[1])

def get_degree_sequence(data):
  """
  set[tuple]에서 각 숫자가 등장한 횟수를 세는 함수

  Args:
    data: set[tuple] 형태의 데이터

  Returns:
    dict: 각 숫자가 등장한 횟수를 저장한 딕셔너리
  """

  counts = {}  # 각 숫자의 등장 횟수를 저장할 딕셔너리
  for tup in data:
    for num in tup:
      if num in counts:
        counts[num] += 1
      else:
        counts[num] = 1
  return counts



# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# --------------------- Modelling ---------------------------------------- #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #

def filter_consecutive_indices(df : pd.DataFrame, scale):
    """
    주어진 pandas Index에서 scale 이상 연속하는 indices를 찾아서 반환합니다.

    Args:
        index (pd.Index): 대상 pandas Index (dtype은 int64라고 가정).
        scale (int): 연속성을 판단하는 기준이 되는 최소 연속 개수.

    Returns:
        list: scale 이상 연속하는 indices의 리스트.
              각 요소는 연속된 indices를 담은 리스트입니다.
              (예: [[0, 1, 2, 3], [5, 6], [1078, 1079, 1080, 1081, 1082]])
    """

    index = df.index
    consecutive_groups = []
    current_group = []

    if not isinstance(index, pd.Index):
        raise TypeError("index must be a pandas Index object.")

    if index.dtype != 'int64':
        raise ValueError("Index dtype must be int64")

    if not all(isinstance(s, int) for s in index):
        raise ValueError("Index elements must be integers")

    if not isinstance(scale, int) or scale <= 0:
        raise ValueError("scale must be a positive integer")

    # index가 비어있으면 빈 리스트를 반환
    if len(index) == 0:
        return []

    # 첫 번째 index를 current_group에 추가
    current_group.append(index[0])

    # index를 순회하며 연속성을 확인
    for i in range(1, len(index)):
        if index[i] == index[i-1] + 1:  # 연속하는 경우
            current_group.append(index[i])
        else:  # 연속이 끊기는 경우
            if len(current_group) >= scale:
                consecutive_groups.append(current_group)
            current_group = [index[i]]  # 새로운 그룹 시작

    # 마지막 그룹 처리 (index 순회가 끝난 후)
    if len(current_group) >= scale:
        consecutive_groups.append(current_group)

    return consecutive_groups

def access_by_consecutive_indices(df, consecutive_row_indices, column_idx : int):
    """
    주어진 DataFrame에서 consecutive_row_indices에 해당하는 행에 접근합니다.

    Args:
        df (pd.DataFrame): 대상 DataFrame.
        consecutive_row_indices (list): 연속된 indices를 담은 리스트.
                                    각 요소는 연속된 indices를 담은 리스트입니다.
                                    (예: [[0, 1, 2, 3], [5, 6], [1078, 1079, 1080, 1081, 1082]])

    Returns:
        pd.DataFrame: 모든 연속된 index 그룹에 해당하는 행들을 포함하는 DataFrame.
                      빈 DataFrame이 반환될 수 있습니다.
    """

    all_indices = []
    for group in consecutive_row_indices:
        all_indices.extend(group)  # 모든 index를 하나의 리스트로 합침

    result_df = df.loc[all_indices, column_idx]  # loc를 사용하여 모든 index에 해당하는 행 접근

    return result_df

def label_which_inst(temp : pd.Series, notes : list[tuple[set]], exact : bool = False):
    """
    temp Series를 순회하면서 notes 리스트의 해당 인덱스에 있는 튜플의 set을 기반으로 레이블을 생성합니다.

    Args:
        temp (pd.Series): pandas Series, 각 요소는 set.
        notes (list): 튜플의 리스트, 각 튜플은 두 개의 set을 포함합니다.

    Returns:
        pandas.Series: temp와 동일한 인덱스를 가지며, 0, 1, -1 값을 갖는 pandas Series.
    """

    labels = []

    if not exact :
        for index, s in temp.items():
            # print(f"index: {index}, set: {s}")

            s = set(s) if type(s) == str else s
            inst_1 = notes[index][0]
            inst_2 = notes[index][1]

            # print(f"  inst 1: {inst_1}, inst 2: {inst_2}")

            if inst_1 is None :
                label = -1
                # print(f"  -1 (inst 2에만 존재)")
            elif inst_2 is None :
                label = 1
                # print(f"  1 (inst 1에만 존재)")
            else :
                intersection_1 = s.intersection(inst_1)
                intersection_2 = s.intersection(inst_2)

                if intersection_1 and not intersection_2:
                    label = 1
                    # print(f"  1 (inst 1에만 존재)")
                elif intersection_2 and not intersection_1:
                    label = -1
                    # print(f"  -1 (inst 2에만 존재)")
                else:
                    label = 0 #(len(intersection_1) - len(intersection_2)) / len(s)
                    # print(f"  0 (두 inst에 걸쳐있음)")

            labels.append(label)

    else :
        for index, s in temp.items():
            # print(f"index: {index}, set: {s}")

            s = set(s) if type(s) == str else s
            inst_1 = notes[index][0]
            inst_2 = notes[index][1]

            if inst_1 is None :
                label = (0, len(s))
            elif inst_2 is None :
                label = (len(s), 0)
            else :
                intersection_1 = s.intersection(inst_1)
                intersection_2 = s.intersection(inst_2)

                if intersection_1 and not intersection_2:
                    label = (len(s), 0)
                elif intersection_2 and not intersection_1:
                    label = (0, len(s))
                else:
                    label = (len(intersection_1), len(intersection_2))

            labels.append(label)

    return pd.Series(labels, index=temp.index)

def plot_onoff_distr_of_cycle(cons_indicies : list, cycle_idx, cycle_to_see, scale, threshold, scale_reduction, 
                              show : bool = False, output_dir = 'scale_evaluation') :

    
    cons_ends = [(sublist[0], sublist[-1], len(sublist)) for sublist in cons_indicies]

    # 1. 길이(length)의 평균 및 표준 편차 계산
    lengths = [tup[2] for tup in cons_ends]
    on_mean = round(np.mean(lengths), 2)
    on_std = round(np.std(lengths), 2)

    # print(f"연속존재 구간 mean: {on_mean}") # 사이클 노드 
    # print(f"연속존재 구간 std: {on_std}") # 사이클 노드

    # 2. start와 end 차이 계산
    differences = []
    diff_4_plot = []
    if len(cons_ends) != 1 :
        for i in range(len(cons_ends) - 1):  # 마지막 튜플은 제외
            start_next = cons_ends[i+1][0]
            end_current = cons_ends[i][1]
            # print(start_next, end_current)
            difference = start_next - end_current
            differences.append(difference)
            diff_4_plot.append((cons_ends[i][1]+1, difference))
    else :
        differences = [cons_ends[0][0], 1087 - cons_ends[0][1]]
        diff_4_plot.append((0, cons_ends[0][0]))
        diff_4_plot.append((cons_ends[0][1], 1087 - cons_ends[0][1]))

    # 차이가 없는 경우를 처리
    if not differences:
        print("start와 end의 차이를 계산할 수 있는 쌍이 없습니다.")
        # print(cons_ends, cons_indicies )
    else:
        off_mean = round(np.mean(differences), 2)
        off_std = round(np.std(differences), 2)

        # print(f"부재 구간 mean: {off_mean}")
        # print(f"부재 구간 std: {off_std}")


    x1 = [tup[0] for tup in cons_ends]
    cons_len = [tup[2] for tup in cons_ends]

    x2 = [tup[0] for tup in diff_4_plot]
    nonexist_len = [tup[1] for tup in diff_4_plot]

    # Figure와 Axes 생성 (명시적으로 Figure 객체 생성)
    fig, ax = plt.subplots(figsize=(10, 6))

    # 첫 번째 데이터셋을 파란색으로 플롯
    ax.scatter(x1, cons_len, color='blue', label='on')
    ax.scatter(x2, nonexist_len, color='red', label='off')

    title_string = f'{cycle_idx+1}. {cycle_to_see} at {scale}-scale for {threshold}'
    ax.set_title(title_string)

    # x축 레이블 추가
    ax.set_xlabel('time with quaver as a unit')
    ax.set_ylabel('length of period')

    ax.grid(True)
    ax.legend(loc='upper left')  # 오른쪽 상단에 범례 표시

        # 텍스트 추가
    textstr = '\n'.join((
        f'On Mean: {on_mean:.2f}',
        f'On Std: {on_std:.2f}',
        f'Off Mean: {off_mean:.2f}',
        f'Off Std: {off_std:.2f}',
        f'Scale-Reduction: {(1-scale_reduction):.2f}'
    ))

    temp = dict()
    temp[cycle_idx] = (cycle_to_see, scale, on_mean, on_std, off_mean, off_std, 100 - round(scale_reduction*100, 2))

    # 텍스트 박스 속성
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

    # 텍스트 박스 추가 (플롯의 오른쪽 상단)
    ax.text(0.80, 0.95, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # 파일 저장 경로 설정
    # output_dir = 'scale_evaluation'  # 저장할 디렉토리 이름
    os.makedirs(output_dir, exist_ok=True)  # 디렉토리가 없으면 생성

    # 파일 이름 설정
    filename = title_string + '.png'
    filepath = os.path.join(output_dir, filename)

    # 레이아웃 조정 (저장 전에 호출)
    plt.tight_layout()

    # 플롯 저장 (show() 호출 전에 저장)
    plt.savefig(filepath)

    if show :
        # 플롯 보여주기 (저장 후에 호출)
        plt.show()
    
    # 메모리 관리를 위해 figure를 닫음
    plt.close(fig)

    return temp

# cycles_strong = get_scattered_cycles_df(df = hibari_notes_df, cycle_labeled = cycle_labeled, binary = False)

def brute_force_check_assistant(hibari_notes, cons_scattered, cycle_to_see) :

    in_which_inst = label_which_inst(cons_scattered, hibari_notes, exact = True)
    df1 = cons_scattered.to_frame(name=f'{cycle_to_see}')
    df2 = in_which_inst.to_frame(name='inst_distr')

    # concat() 함수를 사용하여 연결
    about_cycle = pd.concat([df1, df2], axis=1)  # axis=1은 열 방향으로 연결을 의미
    about_cycle.reset_index(inplace=True)
    about_cycle['bar'] = about_cycle['index'].apply(lambda x: ((x // 8)+1, (x % 8)+1))
    about_cycle.drop(columns=['index'], inplace=True)

    return about_cycle

def length_of_consecutive_indices(cons_indicies : list[list]) :

    length = 0
    for i in range(len(cons_indicies)):
        length += len(cons_indicies[i])
    
    return length

def union_values_for_common_keys(dict1, dict2):
  """
  두 딕셔너리의 공통된 key에 대해 value set을 합집합합니다.

  Args:
    dict1: 첫 번째 딕셔너리.
    dict2: 두 번째 딕셔너리.

  Returns:
    공통된 key에 대해 value set이 합쳐진 새로운 딕셔너리.
  """

  result_dict = {}

  # dict1의 모든 키에 대해 반복
  for key, value1 in dict1.items():
    # dict2에도 동일한 키가 있는지 확인
    if key in dict2:
      value2 = dict2[key]
      # 두 value set을 합집합
      united_value = value1.union(value2)
      result_dict[key] = united_value
    else:
      # dict2에 없는 키는 dict1의 값을 그대로 사용
      result_dict[key] = value1

  # dict1에 없는 키들을 dict2에서 가져옴
  for key, value2 in dict2.items():
    if key not in dict1:
      result_dict[key] = value2

  return result_dict

def get_simul_notes(active_notes_by_onset, notes_label):
  """
  두 개의 딕셔너리를 사용하여 특정 형식의 리스트를 생성합니다.

  Args:
    active_notes_by_onset: 첫 번째 딕셔너리 (int: set(tuple)).
    notes_label: 두 번째 딕셔너리 (tuple: int).

  Returns:
    리스트[dict[int]] 형태의 리스트.
  """

  result = []
  for key in active_notes_by_onset:
    new_set = set()
    for tup in active_notes_by_onset[key]:
      if tup in notes_label:
        new_set.add(notes_label[tup])
    result.append(new_set)
  return result

def get_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled : dict | list, threshold : float, min_reduction) :

    cycle_scattered = check_cycle_if_plausible(cycles_weak, column_idx = cycle_idx, cycle_labeled = cycle_labeled, binary = True)
    initial_scale = len(cycle_labeled[cycle_idx])

    scale = initial_scale
    
    while True:
        cons_indicies = filter_consecutive_indices(cycle_scattered, scale=scale)
        on_length = length_of_consecutive_indices(cons_indicies)
        scale_reduction = on_length / len(cycle_scattered)

        if scale_reduction <= min_reduction:
            
            scale = scale - 1
            cons_indicies = filter_consecutive_indices(cycle_scattered, scale=scale)
            on_length = length_of_consecutive_indices(cons_indicies)
            scale_reduction = on_length / len(cycle_scattered)
            break

        elif scale_reduction <= threshold:
            break  

        scale += 1  # scale 증가

    return cons_indicies, scale, scale_reduction

def search_scale_for_threshold(cycles_weak, cycle_idx, cycle_labeled, threshold : float = 0.8, 
                             get_plot : bool = True, brute_force : bool = False, output_dir = 'scale_evaluation', min_reduction = 0.5) :


    cons_indicies, scale, scale_reduction = get_cycle_scaled(cycles_weak, cycle_idx, cycle_labeled, threshold, min_reduction)

    # Series를 DataFrame으로 변환
    cycle_to_see = [vertex_label + 1 for vertex_label in cycle_labeled[cycle_idx]]
    print(f"Working on {cycle_idx+1}th / {len(cycle_labeled)} cycle : {cycle_to_see}")
    for_score = (cycle_to_see, cons_indicies, scale)

    cycle_onoff = dict()
    # about_cycle = pd.DataFrame()

    if get_plot :
        cycle_onoff = plot_onoff_distr_of_cycle(cons_indicies, cycle_idx, cycle_to_see, scale, threshold, scale_reduction, output_dir = output_dir)
        
    # if brute_force :
    #     about_cycle = brute_force_check_assistant(hibari_notes, cons_scattered, cycle_to_see)

    return cons_indicies, cycle_onoff, for_score

def evaluate_threshold(cycles_weak : pd.DataFrame, cycle_labeled : dict, threshold : float, lower_bound : float | None, output_dir : str) :

    for_overlap = []
    for_scores = dict()
    cycles_onoff = dict()

    if lower_bound is None :
        lower_bound = np.max([0.0, threshold - 0.1])

    for cycle_idx in cycle_labeled.keys():
        
        cons_indicies, cycle_onoff, for_score = search_scale_for_threshold(cycles_weak = cycles_weak, 
                                                                        cycle_idx = cycle_idx, cycle_labeled = cycle_labeled, 
                                                                        threshold = threshold, output_dir = output_dir, min_reduction = lower_bound)
        
        cycles_onoff = {**cycles_onoff, **cycle_onoff}
        for_scores[cycle_idx] = for_score
        for_overlap.append((cycle_idx, cons_indicies))

    column_names = ['cycle', 'scale', 'mean(on)', 'std(on)', 'mean(off)', 'std(off)', 'scale reduction(%)']  # 원하는 컬럼 이름 리스트
    cycles_scaled_stat = pd.DataFrame.from_dict(cycles_onoff, orient='index', columns = column_names)

    return for_overlap, for_scores, cycles_scaled_stat

def get_now(format : str = "%Y%m%d_%H%M%S"):

    timestamp = datetime.datetime.now().strftime(format) 
    
    return timestamp

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







