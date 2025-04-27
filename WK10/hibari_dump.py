


#%%
###
# 박자가 이상하게 올라가긴 했지만
# anyway, it worked
###

from music21 import stream, note, chord, metadata, tempo, key

def create_musicxml_with_chords(data, title="Untitled", composer="Unknown", tempo_value=120, key_signature='C'):
    """튜플 리스트로부터 MusicXML 파일을 생성하고, 동시에 시작하는 음표들을 화음으로 처리합니다."""

    s = stream.Score()

    # Metadata 설정
    md = metadata.Metadata()
    md.title = title
    md.composer = composer
    s.insert(0, md)

    # Tempo 설정
    mm = tempo.MetronomeMark(number=tempo_value)
    s.insert(0, mm)

    # Key Signature 설정
    ks = key.Key(key_signature)
    s.insert(0, ks)

    # Part 생성
    part = stream.Part()
    part.id = 'P1'
    s.append(part)

    # 음표들을 offset별로 그룹화
    notes_by_offset = defaultdict(list)
    for start, pitch, end in data:
        duration = (end - start) * 0.5
        n = note.Note(pitch)
        n.quarterLength = duration
        n.offset = start * 0.5
        notes_by_offset[n.offset].append(n)

    # 화음 또는 단일 음표 추가
    for offset in sorted(notes_by_offset.keys()):
        notes = notes_by_offset[offset]
        if len(notes) > 1:  # 여러 음표가 동시에 시작하는 경우 화음으로 처리
            c = chord.Chord(notes)
            part.append(c)
        else:  # 단일 음표인 경우
            part.append(notes[0])

    return s

# 예시 데이터
data = [(0, 67, 1), (0, 52, 2), (0, 59, 2), (0, 62, 2), (1, 72, 2)]

# MusicXML 생성
musicxml_score = create_musicxml_with_chords(data, title="My Composition", composer="Me", tempo_value=120, key_signature='C')

# 파일로 저장
musicxml_score.write('musicxml', 'my_composition_with_chords2.musicxml')
print("MusicXML file created: my_composition_with_chords.musicxml")

#%%

# %%
from music21 import stream, note, chord, metadata, tempo, key
from collections import defaultdict

def create_musicxml_with_tempo(data, tempo_value=120, title="Untitled", composer="Unknown", key_signature='C'):
    """튜플 리스트로부터 MusicXML 파일을 생성하고, 템포 정보를 반영하여 동시에 시작하는 음표들을 화음으로 처리합니다."""

    s = stream.Score()

    # Metadata 설정
    md = metadata.Metadata()
    md.title = title
    md.composer = composer
    s.insert(0, md)

    # Tempo 설정
    mm = tempo.MetronomeMark(number=tempo_value)
    s.insert(0, mm)

    # Key Signature 설정
    ks = key.Key(key_signature)
    s.insert(0, ks)

    # Part 생성
    part = stream.Part()
    part.id = 'P1'
    s.append(part)

    # 음표들을 offset별로 그룹화
    notes_by_offset = defaultdict(list)
    for start, pitch, end in data:
        duration = (end - start) * (60 / tempo_value)  # 8분음표 기준이므로 (60 / tempo_value) 곱하기
        n = note.Note(pitch)
        n.quarterLength = duration
        n.offset = start * (60 / tempo_value)  # offset도 8분음표 기준으로 계산
        notes_by_offset[n.offset].append(n)

    # 화음 또는 단일 음표 추가
    for offset in sorted(notes_by_offset.keys()):
        notes = notes_by_offset[offset]
        if len(notes) > 1:  # 여러 음표가 동시에 시작하는 경우 화음으로 처리
            c = chord.Chord(notes)
            part.append(c)
        else:  # 단일 음표인 경우
            part.append(notes[0])

    return s

# 예시 데이터
data = [(0, 67, 1), (0, 52, 2), (0, 59, 2), (0, 62, 2), (1, 72, 2)]
tempo_value = 65.99999340000066

# MusicXML 생성 (템포 값 전달)
musicxml_score = create_musicxml_with_tempo(data, tempo_value=tempo_value, title="My Composition", composer="Me", key_signature='C')

# 파일로 저장
musicxml_score.write('musicxml', 'my_composition_with_chords_and_tempo.musicxml')
print("MusicXML file created: my_composition_with_chords_and_tempo.musicxml")

# %%
from music21 import converter

try:
    score = converter.parse('my_composition.musicxml')
    print("MusicXML file is valid.")
except Exception as e:
    print(f"MusicXML file is invalid: {e}")








    #############################################
### adjacent matrix를 만들기 위한 시도 #######
### bipartite 가중치 ########################
#############################################
### 가설 : module 자체에 내제된 빈도수만큼으로 환원될 것이다.
################## 250316 ##################

def label_chord_by_onset(adjusted_note : list) -> list :
    """
    MIDI 데이터를 처리하여 각 onset에 해당하는 화음 레이블을 생성합니다.

    Args:
        note_list (list): (start, pitch, end) 튜플을 요소로 갖는 리스트.
                          'adjust_to_eighth_note' 함수에서 출력된 형태를 가정합니다.

    Returns:
        list: onset(start)을 기준으로 그룹화된 화음에 대해, 등장 순서대로 
              0, 1, 2, ... 로 레이블링했을 때, 입력된 'note_list'의 모든 start 인덱스에 대해 
              해당 화음의 레이블을 갖는 리스트.

    Raises:
        TypeError: `note_list`가 리스트가 아닌 경우.
        ValueError: `note_list`의 요소가 튜플이 아니거나, 튜플의 길이가 3이 아닌 경우.

    """

    # 입력 타입 검사
    if not isinstance(adjusted_note, list):
        raise TypeError("Input 'note_list' must be a list.")
    
        # 입력 데이터 구조 검사 (선택 사항 - 필요한 경우 활성화)
    for note in adjusted_note:
        if not isinstance(note, tuple):
            raise ValueError("Elements of 'note_list' must be tuples.")
        if len(note) != 3:
            raise ValueError("Tuples in 'note_list' must have length 3 (start, pitch, end).")

    # 1. start 값에 따라 pitch를 set으로 묶기
    result = {}
    for start, pitch, _ in adjusted_note:
        if start not in result:
            result[start] = set()
        result[start].add(pitch)

    # 2. set에 대한 labeling 딕셔너리 만들기
    set_labels = {}
    label_counter = 0

    for pitch_set in result.values():
        # frozenset을 사용하여 set을 hashable하게 만들기
        frozen_set = frozenset(pitch_set)  
        if frozen_set not in set_labels:
            set_labels[frozen_set] = label_counter
            label_counter += 1

    # 3. result의 value (set)들을 set_labels에 mapping하기
    mapped_result = {}
    for start, pitch_set in result.items():
        frozen_set = frozenset(pitch_set)
        mapped_result[start] = set_labels[frozen_set]

    # 4. list로 변환
    chord_labeled_at_onset = list(mapped_result.values())

    return chord_labeled_at_onset

inst_1_chord = label_chord_by_onset(adn_1_real)
inst_2_chord = label_chord_by_onset(adn_2_real)

# list에 모든 박자가 고려되지 않았다...




#%%
#######################################
########### 250322 Saturday ###########
#######################################


def EstBarsTrackMido(filename, track_number, meter):
    try:
        midi = MidiFile(filename)
    except FileNotFoundError:
        print(f"Error: MIDI file '{filename}' not found.")
        return []  # or handle the error as needed

    try:
        track = midi.tracks[track_number]
    except IndexError:
        print(f"Error: Track {track_number} not found in the MIDI file.")
        return []

    m = meter[0]  # nbr of beats per bar
    n = meter[1]  # time unit (1= whole, 2= half, 4= quarter, 8= quaver)
    ticks_per_beat = midi.ticks_per_beat
    u = ticks_per_beat * (4 / n)  # time unit in midi ticks (assuming 4/4 time signature)
    d = m * u  # length of a bar in midi ticks

    notes = []
    time = 0
    for msg in track:
        time += msg.time  # Absolute time

        if msg.type == 'note_on' and msg.velocity > 0:
            start_time = time
            pitch = msg.note

            # Find the corresponding note_off message
            for later_msg in track:
                if later_msg.time > 0:
                    time += later_msg.time # update the time
                if later_msg.type == 'note_off' or (later_msg.type == 'note_on' and later_msg.velocity == 0):
                    if later_msg.note == pitch :
                        end_time = time
                        notes.append([start_time, end_time, pitch]) # 리스트로 변경
                        break # Found matching note_off, move to next note_on

    # Create bars_list
    if not notes:
        bars_list = []
    else:
        nbr_bars = math.floor(notes[-1][1] / int(d)) + 1
        bars_list = [[] for _ in range(nbr_bars)]  # Correct initialization

    # Placing each note in the corresponding bar
    for start, end, pitch in notes:
        i = int(end / d)
        bars_list[i].append([start, pitch]) # 리스트로 변경

    return bars_list

def FourierBars(filename, track_list, meter):
    m = meter[0]
    n = meter[1]
    u = 1920/n
    d = m*u
    onsets = []
    pitches = []
    len_t = []
    bars_lists_from_EstBarsTrackMido = [] # EstBarsTrackMido 결과 저장
    for t in track_list:
        bars_list_t = EstBarsTrackMido(filename, t, meter)
        bars_lists_from_EstBarsTrackMido.append(bars_list_t)
        len_t.append(len(bars_list_t))
        for bar in bars_list_t:
            if bar:  # bar 리스트가 비어있지 않은지 확인
                pitches.append(bar[0][1])
                for i in range(1, len(bar)):
                    pitches.append(bar[i][1])
                    ons = bar[i][0] - bar[i-1][0]
                    if ons != 0:
                        onsets.append(ons)
    if onsets == []:
        time_unit = 0
    else:
        m = min(onsets)
        T = [0, 30, 60, 96, 120, 160, 240, 480, 960, 1920]
        for k in range(len(T)):
            if T[k] < m <= T[k+1]:
                p = T[k+1]
                time_unit = 1920/p
                onset = 1920/time_unit
                pitch_unit = min(pitches) - min(pitches) % 12
                len_bars = max(len_t)

    Bars = [[] for i in range(len_bars)]
    for idx, t in enumerate(track_list):
        #bars_list_t = EstBarsTrackMido(filename, t, meter) # 다시 호출하지 않고 저장된 값 사용
        bars_list_t = bars_lists_from_EstBarsTrackMido[idx]
        if bars_list_t == []:
            bars_list_t = [[] for i in range(len_bars)]
        else: # len(bars_list_t)가 len_bars보다 작으면, 빈 리스트로 채워 길이를 맞춤
            while len(bars_list_t) < len_bars:
                bars_list_t.append([])

        for i in range(len(Bars)):
            Bars[i] = Bars[i] + bars_list_t[i]

    for i in range(len(Bars)):
        for j in range(len(Bars[i])):
            Bars[i][j][0] = ((Bars[i][j][0] - d*i) / onset) % time_unit
            Bars[i][j][1] = ((Bars[i][j][1] - pitch_unit))
        Bars[i].sort()

    dist_bars = []
    for B in Bars:
        if B not in dist_bars and B != []:
            dist_bars.append(B)
    return dist_bars

file_name = "Ryuichi_Sakamoto_-_hibari.mid"
dist_bars = FourierBars(file_name, [0, 1], (4, 4))
dist_bars





#######################################
########### 250325 Week 6 ###########
#######################################

# onset이 존재하는 start 지점에서 지속되고 있는 chord 고려
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

# label_active_chord_by_onset 내에서 위의 함수가 group_pitches_with_duration_로 대체되며
# 필요없어진.
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

# notes_2_label은 그냥 다 매핑하고 있고,
# frozenset_labeled_to_note_label는 딱 frozenset(chord)_label dictionary에만 작용하고 있다.
# 그래서 없앰.
def notes_2_label(dict1, dict2):
    """
    dict1의 value에 있는 tuple들을 dict2를 사용하여 해당하는 value로 매핑합니다.

    Args:
        dict1 (dict): group_pitches_with_duration_의 리턴값
        dict2 (dict): notes_label_n_counts의 리턴값

    Returns:
        dict: dict1의 key를 유지하고, tuple set이 dict2의 value로 매핑된 딕셔너리.
    """

    mapped_dict = {}
    for key, tuple_set in dict1.items():
        mapped_values = set()
        for tup in tuple_set:
            if tup in dict2:
                mapped_values.add(dict2[tup])
        mapped_dict[key] = mapped_values
    return mapped_dict

def remove_zero_rows_cols(df):
    """
    모든 원소가 0인 행과 열을 DataFrame에서 제거합니다.

    Args:
        df (pd.DataFrame): 입력 DataFrame.

    Returns:
        pd.DataFrame: 0인 행과 열이 제거된 DataFrame.
    """

    # 0인 행과 열을 찾습니다.
    zero_rows = df.index[df.apply(lambda row: row.abs().sum() == 0, axis=1)]
    zero_cols = df.columns[df.apply(lambda col: col.abs().sum() == 0, axis=0)]

    # 0인 행과 열을 제거합니다.
    df_cleaned = df.drop(index=zero_rows, columns=zero_cols)

    return df_cleaned

# get_chords_inter_connected 250328에 수정하면서 필요없어지게 됨
def symmetrize_df_by_average(df):
  """
  데이터프레임 형태의 비대칭 행렬을 평균을 이용하여 대칭 행렬로 만듭니다.

  Args:
    df (pd.DataFrame): 비대칭 행렬을 나타내는 pandas DataFrame.

  Returns:
    pd.DataFrame: 대칭 행렬 DataFrame.
  """

  # 전치 행렬 계산
  df_transposed = df.transpose()

  # 평균 계산
  df_symmetric = (df + df_transposed) / 2

  return df_symmetric


#%%
# import csv

# filename = "adjusted_notes.csv"
# with open(filename, "w", newline="") as csvfile:
#     csvwriter = csv.writer(csvfile)

#     # 헤더를 쓰고 싶다면:
#     header = ["onset", "pitch", "end"]
#     csvwriter.writerow(header)

#     # 데이터를 한 줄씩 쓰기
#     for row in adjusted_notes:
#         csvwriter.writerow(row)

# print(f"CSV 파일 '{filename}'이 생성되었습니다.")




#%%

##########################################
########### 0325 ~ 7 Trippin ################
#########################################
import gudhi as gd
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx

# NetworkX 그래프 생성
G = nx.from_pandas_adjacency(pitchwise_dist)

# 그래프 레이아웃 설정 (선택 사항)
pos = nx.spring_layout(G, k=0.5)  # k 값 조절로 그래프 간격 조정

# 노드 및 엣지 그리기
nx.draw(G, pos, with_labels=True, node_color='skyblue', edge_color='gray', width=0.5)

# 엣지 가중치 표시 (선택 사항)
edge_labels = {(u, v): f"{G[u][v]['weight']:.2f}" for u, v in G.edges()}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

# 그래프 출력
plt.title("Graph Visualization")
plt.show()


#%%
# Persistence homology 계산 및 시각화 부분은 제거하거나 주석 처리
# triangles만 확인하고 싶다면 아래 부분은 필요 없습니다.
# 필요하다면 사용하되, cycle 관련 분석은 하지 않도록 수정했습니다.

# 3. Persistence homology 계산
persistence = simplex_tree.compute_persistence()

# Persistence가 None인지 확인
if persistence is None:
    print("Persistence calculation failed. Check Simplex Tree and parameters.")
else:
    # 4. Persistence diagram 시각화
    gd.plot_persistence_diagram(persistence, alpha=0.8)
    plt.title("Persistence Diagram (1-cycles)")
    plt.xlabel("Birth")
    plt.ylabel("Death")
    plt.show()

    # 5. life_threshold 최적화 (Persistence Diagram 기반)
    life_threshold = 0.01  # 적절한 임계값 설정 (Persistence Diagram 보고 결정)

    # 6. Cycle 추출 및 분석 (제거 또는 주석 처리)
    persistence_intervals = simplex_tree.persistence_intervals_in_dimension(1)
    significant_cycles = []
    for interval in persistence_intervals:
        birth, death = interval
        life = death - birth
        if life > life_threshold and death != np.inf:
            significant_cycles.append(interval)

    print("Significant cycles (birth, death):", significant_cycles)


# 5. 1-skeleton 추출 및 NetworkX 그래프 생성
skeleton = simplex_tree.get_skeleton(1)
G = nx.Graph()

for simplex, filtration_value in skeleton:
    if len(simplex) == 1:
        G.add_node(simplex[0])
    elif len(simplex) == 2:
        G.add_edge(simplex[0], simplex[1], weight=filtration_value)

# 6. 그래프 시각화
pos = nx.spring_layout(G)

# 새로운 figure와 axes 생성
fig, ax = plt.subplots()

# 노드 그리기
nx.draw_networkx_nodes(G, pos, node_size=50, node_color='blue', ax=ax)

# 엣지 그리기 (가중치에 따라 색상 변경)
edges = G.edges()
weights = [G[u][v]['weight'] for u, v in edges]
nx.draw_networkx_edges(G, pos, edgelist=edges, width=1, edge_color=weights, edge_cmap=plt.cm.viridis, ax=ax)

# 레이블 제거
ax.xaxis.set_major_locator(plt.NullLocator())
ax.yaxis.set_major_locator(plt.NullLocator())

# 색상 막대 추가
sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, norm=plt.Normalize(vmin=min(weights), vmax=max(weights)))
fig.colorbar(sm, ax=ax, label="Filtration Value (Edge Weight)")  # ax 인자 추가

# 그래프 제목 설정
ax.set_title("1-Skeleton of Rips Complex")

# 그래프 보여주기
plt.show()



#%%
###################################
###################################
############ 250329 ###############
###################################
###################################

"""
inter, intra distance를 따로 구해서 더하는 방식은 
weight를 더해서 구한 distance와 달랐다.
그럼에도 inter와 intra의 반영비율을 다르게 할 수 있을지도 모르기 때문에
아래 코드를 keep해둔다. 
"""


from util import is_distance_matrix_from

weight_mtrx = get_chords_inter_connected(adn_1_chord_, adn_2_chord_, lag=1)
inter_distance = is_distance_matrix_from(weight_mtrx, pitches_dict)

weight_mtrx_1 = get_chords_intra_connected(adn_1_chord_, lag=1)
intra_distance_1 = is_distance_matrix_from(weight_mtrx_1, pitches_dict)

weight_mtrx_2 = get_chords_intra_connected(adn_2_chord_, lag=1)
intra_distance_2 = is_distance_matrix_from(weight_mtrx_2, pitches_dict)

# UTM에서 inter에서 없었던 inf가 너무 많아진다.
timeflow_distance = inter_distance + intra_distance_1 + intra_distance_2
timeflow_distance

import numpy as np

# np.inf를 NaN으로 대체
df1_replaced = inter_distance.replace([np.inf, -np.inf], np.nan)
df2_replaced = intra_distance_1.replace([np.inf, -np.inf], np.nan)
df3_replaced = intra_distance_2.replace([np.inf, -np.inf], np.nan)


# 데이터프레임을 리스트로 묶어 합계를 계산
dataframes = [df1_replaced, df2_replaced, df3_replaced]
result_df = pd.concat(dataframes).groupby(level=0).sum()
result_df = result_df.replace(0, np.inf)

# 결과 출력
result_df




# %%
###################################
###################################
############ 250402 ###############
###################################
###################################

true_indices = [index for index, (flag, arr) in enumerate(linalg_profile_n1) if flag]

def check_consecutive(indices):
    """인덱스 리스트가 연속적인지 확인합니다."""
    if not indices:  # 리스트가 비어있으면 연속으로 간주합니다. (논리적으로 맞지 않을 수 있지만, 상황에 따라 처리 방법을 변경하세요)
        return True

    # 인덱스 리스트를 정렬합니다 (만약 정렬되어 있지 않다면).
    indices = sorted(indices)

    # 첫 번째 인덱스와 이후 인덱스 간의 차이가 1씩 증가하는지 확인합니다.
    for i in range(1, len(indices)):
        if indices[i] - indices[i-1] != 1:
            return False  # 연속적이지 않음

    return True  # 연속적임

if check_consecutive(true_indices):
    print("True 인덱스들은 연속적입니다.")
else:
    print("True 인덱스들은 연속적이지 않습니다.")

# rate = 0.38 (76/300) 까지는 timeflow distance가 non-singular(invertible)하다가
# 그 이후로 singular해짐.
# eigenvalue의 개수

def calculate_false_tuple_products(data):
    """False 튜플의 array 요소 값들을 각각 곱한 결과를 리스트로 반환합니다."""
    products = []
    for flag, arr in data:
        if not flag:  # flag가 False인 경우
            products.append(np.prod(arr))  # array 안의 모든 요소 곱한 결과를 products 리스트에 추가
    return products

products = calculate_false_tuple_products(linalg_profile_n1)
products[:10]

import matplotlib.pyplot as plt

# 방법 1: 폰트 이름 직접 지정 (가장 일반적인 방법)
plt.rcParams['font.family'] = 'Malgun Gothic'  # Windows

# 값 필터링 (NumPy array로 변환 후 필터링)
data_np = np.array(products)  # 먼저 NumPy array로 변환
filtered_data = data_np[(data_np >= -10) & (data_np <= 0.01)]

# 그래프 그리기 (필터링된 데이터 사용)
plt.plot(filtered_data, marker='o', linestyle='-')
plt.xlabel("Index")
plt.ylabel("Value")
plt.title("꺾은선 그래프 (필터링됨)")
plt.grid(True)

# y축 스케일 조정 (선택 사항)
# plt.yscale('log') #로그 스케일은 음수 값을 처리할 수 없으므로, 필터링 후에 사용하는 것이 좋습니다.

plt.show()



#%%
###################################
###################################
######### 250403 (GPT+) ########### # before & after 혼재되어 있음.
###################################
###################################


def get_cycle_from_distance(distance_df : pd.DataFrame, 
                            dist_dist = False, barcode = False, PD = False, 
                            prev_ver = False,
                            max_edge_length_ = 1.0) : 

    distance_matrix = distance_df.copy()

    # Vietoris-Rips 복합체 생성
    rips_complex = gudhi.RipsComplex(distance_matrix=distance_matrix.values, max_edge_length=max_edge_length_)
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=2) # 최대 차원 설정 (1차원 homology를 보려면 최소 2로 설정)

    # Persistent Homology 계산
    persistence = simplex_tree.persistence()

    # print(persistence)

    if dist_dist :
        # 1. distance_df 값 분포 시각화 (히스토그램)
        plt.figure(figsize=(6, 3))  # 그래프 크기 설정
        sns.histplot(distance_df.values.flatten(), kde=True)  # 히스토그램 그리기, kde는 밀도 추정 곡선
        plt.title("Distance Matrix Value Distribution")
        plt.xlabel("Distance Value")
        plt.ylabel("Frequency")
        plt.show()

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

    cycle_count = 0 # cycle 개수를 저장할 변수 초기화
    lifespans = []
    cycle_vertices = [] # cycle을 이루는 vertex를 저장할 리스트 추가
    cycle_birth_times = [] # cycle의 birth time을 저장하는 리스트


    tolerance = 1e-10

    for dim, (birth, death) in persistence: 
        if dim == 1:

            G = nx.Graph()  # 네트워크 그래프 생성

            # Check if the simplex exists in the simplex tree
            simplex_exists = simplex_tree.find([birth])
            
            if simplex_exists:
                # Extract vertices from the cycle
                vertices = set() # cycle vertex를 얻는 로직이 필요합니다.

                # simplex_tree에 있는 모든 simplex를 순회하며 birth time과 같은 simplex를 찾습니다.
                for simplex, fil_val in simplex_tree.get_skeleton(1): # 1차원 simplex만 확인
                    if abs(fil_val - birth) < tolerance :
                        G.add_edge(*simplex)  # 그래프에 엣지 추가
                        print(f"Cycle candidate: {simplex} with birth time {fil_val}")
                        for vertex in simplex: # simplex를 구성하는 vertex들을 set에 추가
                            vertices.add(vertex)

                for simplex, fil_val in simplex_tree.get_skeleton(2): # 2차원 simplex까지 확인
                    if abs(fil_val - birth) < tolerance:
                        print(f"Cycle candidate (2-simplex): {simplex} with birth time {fil_val}")

                try:
                    cycle = nx.find_cycle(G)
                    print(f"🔥 Cycle detected at birth time {birth}: {cycle}")
                except nx.exception.NetworkXNoCycle:
                    print(f"❌ No cycle found at birth time {birth}")

                # cycle_vertices.append(vertices)
                if vertices not in cycle_vertices:
                    cycle_vertices.append(vertices)
                    cycle_birth_times.append(birth)

            # zero division 방지 (2번) 및 값 확인
            if death == float('inf'):
                life = 1.0 - birth # 또는 다른 적절한 값으로 대체
            else:
                life = death - birth

            lifespans.append(life)
            cycle_count += 1 # cycle 개수 증가

    cycle_vertices = [replace_with_label(s, distance_matrix) for s in cycle_vertices]
    cycle_edges_list = []

    mean = np.mean(lifespans)
    std_dev = np.std(lifespans)
    longest = max(lifespans)

    return cycle_count, mean, std_dev, longest, cycle_vertices, cycle_birth_times, cycle_edges_list

# temp = set(frozenset(s) for s in cycle_vertices)
# unique_cycle_vertices = [set(s) for s in temp]

# print(cycle_vertices)
# print(unique_cycle_vertices)

def replace_with_label(data_set : list[set[int]], distance_df : pd.DataFrame):

  indices = [index for index in distance_df.index]
  
  new_set = set()
  for index in data_set:
    if 0 <= index < len(indices): # index가 유효한 범위 내에 있는지 확인
      new_set.add(indices[index])
    else:
      print(f"Warning: Index {index} is out of range.") # 유효하지 않은 index 경고
  
  return new_set


#%%

###################################
###################################
######### 250404 (GPT+) ########### # before & after 혼재되어 있음.
###################################
###################################


# c:\Users\82104\Developments\.venv\Scripts\python.exe -m pip install ripser persim scikit-tda
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from ripser import ripser
from persim import plot_diagrams

# 1. 점 생성 (예: 원형 구조)
theta = np.linspace(0, 2 * np.pi, 8, endpoint=False)
points = np.stack([np.cos(theta), np.sin(theta)], axis=1)

# 2. persistent homology + cocycles 계산
result = ripser(points, maxdim=2, do_cocycles=True)
diagrams = result['dgms']
cocycles = result['cocycles']

# 3. 다이어그램 그리기
plot_diagrams(diagrams, show=True)

# 4. 첫 번째 1-dimensional loop 추출
H1_diagram = diagrams[1]
H1_cocycles = cocycles[1]

if len(H1_diagram) > 0:
    birth, death = H1_diagram[0]
    cocycle = H1_cocycles[0]
    print(f"1-cycle birth: {birth:.3f}, death: {death:.3f}")

    # 5. loop를 형성하는 가장 유의미한 edge 추출
    print("Representative cocycle:")
    for edge in cocycle:
        i, j, val = edge
        print(f"  Edge {i}-{j} with weight {val}")

G = nx.Graph()
for i, j, val in cocycle:
    G.add_edge(i, j)

pos = {idx: coord for idx, coord in enumerate(points)}
plt.figure(figsize=(4, 4))
nx.draw(G, pos, with_labels=True, node_color='lightcoral', edge_color='black', node_size=600)
plt.title("Representative 1-Cycle")
plt.axis("equal")
plt.show()



# ------------------------------------------------------------------------------------------------

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from ripser import ripser
from persim import plot_diagrams

# 1️⃣ Distance Matrix 정의 (예제)
data = np.array([
    [0.0, 0.3, 0.7, 0.9, 1.2, 1.5, 0.6],
    [0.3, 0.0, 0.5, 0.8, 1.1, 1.4, 0.7],
    [0.7, 0.5, 0.0, 0.3, 0.6, 1.2, 0.9],
    [0.9, 0.8, 0.3, 0.0, 0.5, 1.1, 0.4],
    [1.2, 1.1, 0.6, 0.5, 0.0, 0.8, 0.3],
    [1.5, 1.4, 1.2, 1.1, 0.8, 0.0, 1.0],
    [0.6, 0.7, 0.9, 0.4, 0.3, 1.0, 0.0]
])


distance_df = pd.DataFrame(data)

# 2️⃣ Ripser 실행 (distance matrix 사용)
result = ripser(distance_df.values, distance_matrix=True, maxdim=2, do_cocycles=True)
diagrams = result['dgms']
cocycles = result['cocycles']

# 3️⃣ Persistence Diagram 출력
plot_diagrams(diagrams, show=True)

# 4️⃣ 가장 persistence가 높은 1-cycle 찾기
H1_diagram = diagrams[1]  # H1 (1차 persistent homology)
H1_cocycles = cocycles[1]  # 1-cycle 정보

if len(H1_diagram) > 0:
    # 가장 오래 지속된 cycle 찾기 (death - birth 차이가 가장 큰 것)
    idx = np.argmax(H1_diagram[:, 1] - H1_diagram[:, 0])
    birth, death = H1_diagram[idx]
    cocycle = H1_cocycles[idx]

    print(f"✔️ 선택된 1-cycle: birth={birth:.3f}, death={death:.3f}")

    # 5️⃣ 가장 중요한 edge 선택 (Thresholding)
    threshold = 0.000002  # 너무 큰 값을 주면 중요한 edge가 사라짐
    strong_edges = [(i, j) for i, j, val in cocycle if abs(val) > threshold]

    print("Selected edges for cycle visualization:")
    for i, j in strong_edges:
        print(f"Edge: ({i}, {j})")

    # 6️⃣ NetworkX를 사용해 loop를 시각화
    G = nx.Graph()
    G.add_edges_from(strong_edges)

    # 노드 위치 (랜덤이 아니라 거리 행렬을 기반으로 배치)
    pos = {i: (np.cos(2 * np.pi * i / len(data)), np.sin(2 * np.pi * i / len(data))) for i in range(len(data))}
    pos = nx.circular_layout(G)  # 원형 배치로 loop 강조
    nx.draw_networkx(G, pos, with_labels=True, node_color="red", edge_color="black")

    plt.figure(figsize=(5, 5))
    nx.draw(G, pos, with_labels=True, node_color='lightcoral', edge_color='black', node_size=600)
    plt.title("Filtered 1-Cycle (Loop)")
    plt.axis("equal")
    plt.show()




#%%

###################################
###################################
########### 250405  ############### 
###################################
###################################

import pandas as pd
import numpy as np
import ripser
import matplotlib.pyplot as plt

distance_matrix = timeflow_distance.copy()

# ripser 객체 생성
rips = ripser.Rips(maxdim = 3)

# Persistent Diagram 계산
diagrams_ripser = rips.fit_transform(distance_matrix.values, distance_matrix=True)

# Persistent Diagram 시각화
rips.plot(diagrams_ripser)
plt.title("Persistence Diagram")
plt.show()

# 결과 해석: diagrams_ripser 배열에 persistence diagram 정보가 담겨 있습니다.
# 각 feature는 (birth time, death time)으로 구성됩니다.
diagrams_ripser

persistence = [(3, (0.013888888888888888, 0.015625)), (2, (0.006944444444444444, 0.007352941176470588)), (1, (0.007246376811594203, 0.023809523809523808)), (1, (0.007246376811594203, 0.017857142857142856)), (1, (0.006493506493506494, 0.010309278350515464)), (1, (0.005376344086021506, 0.007352941176470588)), (1, (0.005434782608695652, 0.007352941176470588)), (1, (0.0045871559633027525, 0.006493506493506494)), (1, (0.005952380952380952, 0.007352941176470588)), (1, (0.005494505494505495, 0.006666666666666667)), (1, (0.005376344086021506, 0.006493506493506494)), (1, (0.005376344086021506, 0.006493506493506494)), (1, (0.0056179775280898875, 0.006493506493506494)), (1, (0.006578947368421052, 0.007352941176470588)), (1, (0.0058823529411764705, 0.006493506493506494)), (1, (0.0070921985815602835, 0.007352941176470588)), (1, (0.006369426751592357, 0.006493506493506494)), (0, (0.0, np.inf)), (0, (0.0, 0.00819672131147541)), (0, (0.0, 0.00684931506849315)), (0, (0.0, 0.006493506493506494)), (0, (0.0, 0.0058823529411764705)), (0, (0.0, 0.0055248618784530384)), (0, (0.0, 0.005494505494505495)), (0, (0.0, 0.005376344086021506)), (0, (0.0, 0.00510204081632653)), (0, (0.0, 0.005050505050505051)), (0, (0.0, 0.004761904761904762)), (0, (0.0, 0.0045871559633027525)), (0, (0.0, 0.0045045045045045045)), (0, (0.0, 0.004132231404958678)), (0, (0.0, 0.004)), (0, (0.0, 0.004)), (0, (0.0, 0.0037593984962406013)), (0, (0.0, 0.0037593984962406013)), (0, (0.0, 0.0036363636363636364)), (0, (0.0, 0.0031645569620253164)), (0, (0.0, 0.003067484662576687)), (0, (0.0, 0.0029411764705882353)), (0, (0.0, 0.002824858757062147))]

def compare_diagrams(gudhi_diagram, ripser_diagram, tolerance=1e-5):
    """
    gudhi와 ripser에서 얻은 Persistent Diagram을 비교합니다.
    순서에 상관없이 birth time과 death time이 유사한 값들이 있는지 확인합니다.

    Args:
        gudhi_diagram (list): gudhi에서 얻은 Persistent Diagram (리스트 형태)
        ripser_diagram (numpy.ndarray): ripser에서 얻은 Persistent Diagram (numpy 배열 형태)
        tolerance (float): 허용 오차 범위

    Returns:
        bool: 두 결과가 유사하면 True, 그렇지 않으면 False
    """

    # 차원별로 분리
    gudhi_h0 = [x[1] for x in gudhi_diagram if x[0] == 0]
    gudhi_h1 = [x[1] for x in gudhi_diagram if x[0] == 1]
    gudhi_h2 = [x[1] for x in gudhi_diagram if x[0] == 2]
    gudhi_h3 = [x[1] for x in gudhi_diagram if x[0] == 3]

    ripser_h0 = ripser_diagram[0]
    ripser_h1 = ripser_diagram[1]
    ripser_h2 = ripser_diagram[2] if len(ripser_diagram) > 2 else np.array([])
    ripser_h3 = ripser_diagram[3] if len(ripser_diagram) > 3 else np.array([])

    def compare_homology(gudhi_homology, ripser_homology, tolerance):
        """
        두 homology 그룹을 비교합니다.
        순서에 상관없이 gudhi의 각 점에 대해 ripser에서 유사한 점을 찾습니다.
        """
        if len(gudhi_homology) != len(ripser_homology):
            print(f"Warning: Number of features differs: gudhi={len(gudhi_homology)}, ripser={len(ripser_homology)}")
           # return False  # Feature 개수가 다르면 다르다고 판단 -> 개수가 달라도 유사한 점이 있다면 True를 반환하도록 수정

        matched = [False] * len(ripser_homology)  # ripser의 각 점이 매칭되었는지 추적

        for birth_g, death_g in gudhi_homology:
            found_match = False
            for j, (birth_r, death_r) in enumerate(ripser_homology):
                if matched[j]:
                    continue  # 이미 매칭된 점은 건너뜀
                if np.isclose(birth_g, birth_r, atol=tolerance) and np.isclose(death_g, death_r, atol=tolerance):
                    matched[j] = True
                    found_match = True
                    break
            if not found_match:
                print(f"No match found for gudhi point: ({birth_g}, {death_g})")
                return False  # gudhi의 점에 대해 매칭되는 ripser 점이 없으면 False
        return True  # 모든 gudhi 점에 대해 매칭되는 ripser 점이 있으면 True

    # 무한대 값을 비교하기 위해 ripser의 inf 값을 큰 숫자로 대체
    ripser_h0[ripser_h0 == np.inf] = max([d[1] for d in gudhi_h0 if d[1] != np.inf]) if [d[1] for d in gudhi_h0 if d[1] != np.inf] else 1.0

    # 0차원 비교
    print("Comparing H0...")
    h0_similar = compare_homology(gudhi_h0, ripser_h0, tolerance)
    print(f"H0 is similar: {h0_similar}")

    # 1차원 비교
    print("Comparing H1...")
    h1_similar = compare_homology(gudhi_h1, ripser_h1, tolerance)
    print(f"H1 is similar: {h1_similar}")

    # 2차원 비교
    print("Comparing H2...")
    h2_similar = compare_homology(gudhi_h2, ripser_h2, tolerance)
    print(f"H2 is similar: {h2_similar}")

     # 3차원 비교
    print("Comparing H3...")
    h3_similar = compare_homology(gudhi_h3, ripser_h3, tolerance)
    print(f"H3 is similar: {h3_similar}")


    return h0_similar and h1_similar and h2_similar and h3_similar  # 모든 차원에서 유사해야 True

# 예시: gudhi와 ripser 결과 비교
is_similar = compare_diagrams(persistence, diagrams_ripser)
print(f"Diagrams are similar: {is_similar}")

#%%
import pandas as pd
import numpy as np
from scipy.spatial.distance import pdist, squareform

def create_hexagon_distance_dataframe():
    """
    한 변의 길이가 1인 정육각형의 꼭짓점 좌표를 사용하여 distance dataframe을 생성합니다.

    Returns:
        pandas.DataFrame: 꼭짓점 간 거리를 나타내는 distance dataframe.
    """

    # 1. 정육각형 꼭짓점 좌표 정의 (원점 중심, 한 변의 길이 1)
    #   - 시계 방향으로 꼭짓점 번호를 매깁니다 (0, 1, 2, 3, 4, 5)
    #   - 좌표는 라디안을 사용하여 계산합니다.
    vertices = []
    for i in range(6):
        angle = 2 * np.pi / 6 * i  # 각도를 라디안으로 계산
        x = np.cos(angle)
        y = np.sin(angle)
        vertices.append([x, y])

    # 중심을 (0,0)으로 옮기는 것이 아닌, 첫번째 꼭지점을 (0,0)으로 옮기려면
    # vertices[0] = [0, 0]
    # vertices[1] = [1, 0]
    # vertices[2] = [1 + 0.5, np.sqrt(3)/2]
    # vertices[3] = [1, np.sqrt(3)]
    # vertices[4] = [0, np.sqrt(3)]
    # vertices[5] = [-0.5, np.sqrt(3)/2]
    # 로 좌표를 재정의 할 수 있습니다.  아래의 vertices 배열을 위의 내용으로 대체하면 됩니다.

    vertices = np.array(vertices)


    # 2. 좌표 간 거리 계산 (유클리드 거리)
    distances = pdist(vertices)  # pairwise distances 계산
    distance_matrix = squareform(distances)  # distance matrix 형태로 변환

    # 3. DataFrame 생성
    df = pd.DataFrame(distance_matrix,
                      index=['0', '1', '2', '3', '4', '5'],
                      columns=['0', '1', '2', '3', '4', '5'])

    return df

# 실행 예시
distance_df = create_hexagon_distance_dataframe()
distance_df


#%%
import gudhi
import numpy as np
import pandas as pd
from scipy.linalg import null_space
from collections import defaultdict

def get_1d_homology(simplex_tree):
    """
    Simplex Tree로부터 1차원 호몰로지 그룹을 계산합니다 (F2 위에서).

    Args: simplex_tree (gudhi.SimplexTree): Simplex Tree

    Returns: list: 1차원 호몰로지 그룹의 cycle (vertex index 리스트)
    """

    # 1. Simplex 정보 추출
    vertices = []
    edges = []
    triangles = []
    for simplex, fil_val in simplex_tree.get_skeleton(2) :
        if len(simplex) == 1 :
            vertices.append((simplex, fil_val)) # 0-simplex (vertex)
        elif len(simplex) == 2 :
            edges.append((simplex, fil_val)) # 1-simplex (edge)
        else :
            triangles.append((simplex, fil_val)) # 2-simplex (triangle)

    # 2. Vertex index 매핑
    num_vertices = len(vertices)
    num_edges = len(edges)
    num_triangles = len(triangles)

    # 3. Boundary Matrix 생성 (F2 위에서)
    #   - d1: edges -> vertices
    d1 = np.zeros((num_vertices, num_edges), dtype=int)
    for j, (edge, _) in enumerate(edges):
        u, v = sorted(tuple(edge))  # edge가 항상 list이므로 tuple로 변환 후 정렬
        d1[u, j] = 1  
        d1[v, j] = 1  

    #   - d2: triangles -> edges
    edge_to_index = {}
    for i, (edge, _) in enumerate(edges):
        edge_to_index[tuple(edge)] = i  # edge가 항상 list이므로 tuple로 변환

    d2 = np.zeros((num_edges, num_triangles), dtype=int)
    for k, (triangle, _) in enumerate(triangles):
        u, v, w = sorted(tuple(triangle))
        edge_uv = tuple(sorted((u, v)))
        edge_vw = tuple(sorted((v, w)))
        edge_wu = tuple(sorted((w, u)))

        d2[edge_to_index[edge_uv], k] = 1
        d2[edge_to_index[edge_vw], k] = 1
        d2[edge_to_index[edge_wu], k] = 1

    # 4. Kernel 및 Image 계산 (F2 위에서)
    # 1차원 boundary map의 kernel 계산
    kernel_d1 = null_space(d1, rcond=None)

    # 2차원 boundary map의 image 계산
    image_d2 = d2 # d2의 각 열은 해당 triangle의 boundary를 나타내며, F2 field에서의 연산은 "경계의 합"을 계산하는 데 사용됩니다.
    basis_image_d2 = []
    for i in range(image_d2.shape[1]):
        if np.any(image_d2[:, i]):
            basis_image_d2.append(image_d2[:, i])

    # 5. Quotient Group 계산 (H1 = Ker(d1) / Im(d2))
    #   - Kernel basis vector들을 edge index로 변환

    # 어려움: null_space()는 실수 field에서 커널을 계산하므로, F2 field에서 직접적인 뺄셈 연산을 수행할 수 없습니다. 
    # 또한, null_space()는 특정 basis를 반환하며, 이 basis가 이미지에 주어진 basis와 다를 수 있습니다.

    # 해결 전략: kernel_cycles 리스트를 생성하여 kernel_d1의 각 basis 벡터를 edge index의 리스트로 변환합니다. 
    # image_boundaries 리스트를 생성하여 basis_image_d2의 각 벡터를 edge index의 리스트로 변환합니다. 
    # 마지막으로, find_representative_cycles 함수를 사용하여 kernel_cycles 중에서 image_boundaries에 포함되지 않는 cycle들을 찾습니다.

    kernel_cycles = []
    for i in range(kernel_d1.shape[1]):
        cycle_edges = []
        for j in range(num_edges):
            if abs(kernel_d1[j, i]) > 1e-6:  # F2이므로 값이 0에 가까운지 확인, 만약 j번째 edge의 가중치가 0이 아니라면, 해당 edge는 현재 basis 벡터에 해당하는 cycle에 포함됩니다.
                if isinstance(edges[j][0], tuple):
                    cycle_edges.append(edges[j][0])
                elif isinstance(edges[j][0], list):
                    cycle_edges.append(tuple(edges[j][0]))
                else:
                    cycle_edges.append(edges[j][0])
        kernel_cycles.append(cycle_edges)

    #   - Image basis vector들을 edge index로 변환
    image_boundaries = []
    for edge in basis_image_d2:
        edge_indices = np.where(edge != 0)[0]
        edge_coords = []
        for i in edge_indices:
            if isinstance(edges[i][0], tuple):
                 edge_coords.append(edges[i][0])
            elif isinstance(edges[i][0], list):
                edge_coords.append(tuple(edges[i][0]))
            else:
                edge_coords.append(edges[i][0])
        image_boundaries.append(edge_coords)

    #  - 대표적인 cycle들을 선택 (Ker(d1) / Im(d2))
    representative_cycles = find_representative_cycles(kernel_cycles, image_boundaries)

    return representative_cycles

def find_representative_cycles(kernel_cycles, image_boundaries):
    """
    Kernel cycle들 중에서 image boundary와 독립적인 representative cycle들을 찾습니다.

    Args:
        kernel_cycles (list): Kernel cycle들의 리스트
        image_boundaries (list): Image boundary들의 리스트

    Returns:
        list: Representative cycle들의 리스트
    """
    representative_cycles = []
    for cycle in kernel_cycles:
        is_independent = True
        for boundary in image_boundaries:
            if is_cycle_in_boundary(cycle, boundary):
                is_independent = False
                break
        if is_independent:
            representative_cycles.append(cycle)
    return representative_cycles

def is_cycle_in_boundary(cycle, boundary):
    """
    주어진 cycle이 boundary에 포함되는지 확인합니다.

    Args:
        cycle (list): 확인할 cycle
        boundary (list): 확인할 boundary

    Returns:
        bool: cycle이 boundary에 포함되면 True, 아니면 False
    """
    cycle_set = set(cycle)
    boundary_set = set(boundary)
    return cycle_set.issubset(boundary_set)




#%%
import pandas as pd

def create_cycle_df(df, cycle):
    """
    DataFrame에서 특정 사이클에 해당하는 컬럼만 추출하고,
    각 행에서 1로 표시된 컬럼들을 값으로 갖는 cycle_df를 생성합니다.

    Args:
        df: 원본 DataFrame.
        cycle: 추출할 컬럼에 해당하는 사이클 (tuple).

    Returns:
        cycle_df: 추출된 컬럼을 기반으로 생성된 pandas DataFrame.
    """

    # 사이클에 해당하는 컬럼명 추출
    cycle_columns = [col + 1 for col in cycle]  # 컬럼명 리스트 생성

    # sub_df 생성 (cycle에 해당하는 컬럼만 추출)
    sub_df = df[cycle_columns]

    # cycle_df 생성 (각 행에서 1로 표시된 컬럼들을 set으로 저장)
    cycle_df = pd.DataFrame(sub_df.apply(lambda row: 1 if row.sum() > 0 else 0, axis=1), columns=[cycle])

    return cycle_df

for key in cycle_labeled.keys() : 
    cycle_df = create_cycle_df(hibari_notes, cycle_labeled[key])
    agreement = sum(cycles_df[key] == cycle_df[cycle_labeled[key]])
    comparison = agreement != 1088
    if comparison :
        print("ohoh")



#%%
###################################
###################################
########### 250427  ############### 
###################################
###################################


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

def get_simul_intra_connected(unique_values, paired_units, log=False):
    """
    주어진 고유 값과 paired_units (각 인덱스에 최대 2개의 set을 가짐)를 사용하여
    데이터프레임을 생성하고 연결도를 계산하여 채웁니다.

    Args:
        unique_values: extract_unique_values_int_keys 함수의 결과로 얻은 고유 값의 집합.
        paired_units: hibari_notes_list와 같은 리스트 (각 원소는 (set, set) 또는 (set, None)).

    Returns:
        연결도가 채워진 pandas DataFrame.
    """

    # 1. DataFrame 생성
    df = pd.DataFrame(0, index=sorted(list(unique_values)), columns=sorted(list(unique_values)))

    # 2. paired_units의 각 원소를 순회하며 연결도 계산 및 DataFrame 업데이트
    for pair in paired_units:
        # 각 튜플의 첫 번째와 두 번째 set을 처리
        for chord in pair:
            if chord is not None:  # None인 경우 넘어감
                chord_list = sorted(list(chord))  # 집합을 정렬된 리스트로 변환 (인덱싱 용이)

                for i in range(len(chord_list)):
                    for j in range(i, len(chord_list)):  # i <= j 조건 만족
                        note_i = chord_list[i]
                        note_j = chord_list[j]
                        df.loc[note_i, note_j] += 1
                        if log:
                            print(f"df[{note_i}, {note_j}] += 1 from {chord_list}")  # 디버깅용

    return df

def get_simul_inter_connected(unique_values, paired_units, log=False):
    """
    주어진 고유 값과 paired_units를 사용하여 데이터프레임을 생성하고,
    교집합 원소는 simul_connectedness 방식으로, 차집합 원소는 bipartite graph 방식으로
    연결도를 계산하여 채웁니다.

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

        # 3. 교집합과 차집합 계산
        intersection = set1.intersection(set2)
        difference1 = set1.difference(set2)
        difference2 = set2.difference(set1)

        # 4. 교집합 원소에 대한 연결도 계산 (simul_connectedness 방식)
        if intersection:
            intersection_list = sorted(list(intersection))
            for i in range(len(intersection_list)):
                for j in range(i+1, len(intersection_list)):
                    note_i = intersection_list[i]
                    note_j = intersection_list[j]
                    df.loc[note_i, note_j] -= 1
                    if log:
                        print(f"df[{note_i}, {note_j}] -= 1 (Intersection)")

        # 5. 차집합 원소에 대한 연결도 계산 (bipartite graph 방식)
        if difference1 and difference2:
            for note_i in difference1:
                for note_j in difference2:
                    # 대소 비교 후 작은 값을 행, 큰 값을 열로 사용
                    row = min(note_i, note_j)
                    col = max(note_i, note_j)
                    df.loc[row, col] += 1
                    if log:
                        print(f"df[{row}, {col}] += 1 (Bipartite)")

    return df

def get_persistence(distance_df, max_edge_length : int, max_dimension : int):
    rips_complex = gudhi.RipsComplex(distance_matrix=distance_df.values, max_edge_length=max_edge_length)
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=max_dimension)  # 1차원 homology 계산을 위해 최대 2차원 설정
    persistence = simplex_tree.persistence() # Persistent Homology 계산

    return simplex_tree, persistence

def get_higher_homol(distance_df : pd.DataFrame, 
                    dist_distr = False, barcode = False, PD = False, 
                    max_edge_length_ = 1.0) : 
    
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

    for dim, (birth, death) in persistence: 
        if dim == 1:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_1d.append(life)

        if dim == 2:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_2d.append(life)

        if dim == 3:
            life = max_edge_length_ - birth if death == float('inf') else death - birth
            lifespans_3d.append(life)

    # return cycle_count, mean, std_dev, longest, cycle_vertices, cycle_birth_times, cycle_edges_list
    return lifespans_2d, lifespans_3d

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

def draw_combined_cycle_persistence(cycle_persistence: dict, cycles_per_plot: int = 10):
    """
    cycle_persistence 딕셔너리를 입력받아 여러 cycle의 persistence diagram을 cycles_per_plot 개수만큼 묶어
    여러 개의 plot으로 시각화합니다.

    Args:
        cycle_persistence: create_cycle_data 함수의 결과 딕셔너리.
        cycles_per_plot: 하나의 plot에 그릴 cycle의 최대 개수.
    """

    num_cycles = len(cycle_persistence)
    num_plots = (num_cycles + cycles_per_plot - 1) // cycles_per_plot  # 필요한 plot의 개수

    # 색상 팔레트 정의 (DeprecationWarning 해결)
    colors = plt.colormaps['tab10']  # or plt.cm.get_cmap('tab10')

    # cycle 데이터를 묶어서 처리하기 위한 리스트
    cycle_groups = []
    cycle_group = {}
    count = 0
    for cycle, data_list in cycle_persistence.items():
        cycle_group[cycle] = data_list
        count += 1
        if count == cycles_per_plot or cycle == list(cycle_persistence.keys())[-1]: # 마지막 cycle인 경우
            cycle_groups.append(cycle_group)
            cycle_group = {}
            count = 0

    # plot 생성
    for plot_index, cycle_group in enumerate(cycle_groups):
        fig, ax = plt.subplots(figsize=(11, 8))  # 더 큰 figsize 설정
        fig.tight_layout(pad=3.0)

        for i, (cycle, data_list) in enumerate(cycle_group.items()):
            # 데이터 추출
            rates = np.array([data[0] for data in data_list])
            births = np.array([data[1] for data in data_list])
            deaths = np.array([data[2] for data in data_list])

            # 색상 선택
            color = colors(i % 10)  # tab10은 10가지 색상을 제공하므로, 10으로 나눈 나머지를 사용

            # Birth 시각화
            ax.plot(rates, births, marker='o', linestyle='-', color=color, label=f"Cycle {cycle} (Birth)")

            # Death 시각화
            ax.plot(rates, deaths, marker='x', linestyle='-', color=color, label=f"Cycle {cycle} (Death)")

            # 그래프 제목 및 축 레이블 설정
            start_cycle = plot_index * cycles_per_plot + 1
            end_cycle = min((plot_index + 1) * cycles_per_plot, num_cycles)
            ax.set_title(f"Persistence Diagram (Cycles {start_cycle}-{end_cycle})")
            ax.set_xlabel("Rate")
            ax.set_ylabel("Time")

            # 그리드 추가
            ax.grid(True)

        # 범례 표시 (전체 cycle에 대한 범례를 표시)
        ax.legend(loc='best')  # 최적의 위치에 범례 표시

        # 그래프 출력
        plt.show()

def find_non_continuous_cycles(cycle_persistence: dict, step: float = 0.01) -> dict:
    """
    cycle_persistence 딕셔너리에서 특정 step을 기준으로 value-list 내의 tuple의 첫 번째 값들이
    연속적이지 않은 cycle들을 찾아 딕셔너리로 반환합니다.

    Args:
        cycle_persistence: cycle 데이터를 담고 있는 딕셔너리.
        step: 연속성을 판단하는 기준이 되는 값 (default: 0.01).

    Returns:
        연속적이지 않은 cycle 데이터만 담고 있는 딕셔너리.
    """

    non_continuous_cycles = {}

    for cycle, data_list in cycle_persistence.items():
        is_continuous = True
        for i in range(len(data_list) - 1):
            diff = round(data_list[i + 1][0] - data_list[i][0], 6)  # 소수점 6자리까지 반올림하여 비교
            if abs(diff - step) > 1e-6:  # 부동 소수점 오차 고려
                is_continuous = False
                break
        if not is_continuous:
            non_continuous_cycles[cycle] = data_list

    return non_continuous_cycles

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