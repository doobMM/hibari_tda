def visualize_midi_notes(midi_file):
    """
    MIDI 파일에서 음표 데이터를 추출하여 음의 높이에 따른 그래프로 시각화합니다.

    Args:
        midi_file (str): MIDI 파일의 경로.
    """
    try:
        # MIDI 파일 로드
        midi_data = pretty_midi.PrettyMIDI(midi_file)

        # 모든 악기 트랙의 음표를 하나의 목록으로 합치기
        notes = []
        for instrument in midi_data.instruments:
            for note in instrument.notes:
                notes.append((note.start, note.pitch, note.end))

        # 음표 데이터를 NumPy 배열로 변환 (시각화 용이성)
        notes_array = np.array(notes)

        # 시각화
        plt.figure(figsize=(12, 6))  # 그래프 크기 설정

        # 음표의 시작 시간을 x축, 음의 높이를 y축으로 설정하여 산점도 그래프 그리기
        plt.scatter(notes_array[:, 0], notes_array[:, 1], s=5)  # s는 점의 크기

        plt.xlabel("Time (seconds)")
        plt.ylabel("Pitch (MIDI Note Number)")
        plt.title("MIDI Note Visualization")
        plt.grid(True)  # 격자 추가
        plt.show()

    except FileNotFoundError:
        print("MIDI 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")



#%%
import pretty_midi
import numpy as np

def create_midi_from_notes(notes, output_file, tempo=120):
    """
    (start, pitch, end) 튜플 리스트를 MIDI 파일로 출력합니다.

    Args:
        notes (list): (start, pitch, end) 튜플 리스트.
        output_file (str): 출력 MIDI 파일 경로.
        tempo (int): 템포 (기본값: 120 BPM).
    """
    # PrettyMIDI 객체 생성
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # 악기 객체 생성 (피아노)
    instrument = pretty_midi.Instrument(program=0)  # 0은 피아노를 의미

    # 음표 객체 생성 및 악기에 추가
    for start, pitch, end in notes:
        note = pretty_midi.Note(velocity=100, pitch=int(pitch), start=start, end=end)
        instrument.notes.append(note)

    # PrettyMIDI 객체에 악기 추가
    midi.instruments.append(instrument)

    # MIDI 파일로 저장
    midi.write(output_file)

# 예시 데이터
notes = [
    (0.0, 60, 1.0),  # C4
    (1.0, 64, 2.0),  # E4
    (2.0, 67, 3.0),  # G4
    (3.0, 72, 4.0)   # C5
]

# MIDI 파일로 출력
output_file = "output.mid"
create_midi_from_notes(notes, output_file)



#%%

data = adn_1_real
data = [(item[0], pitch_to_freq[item[1]], item[2]) for item in data]

# 샘플링 레이트 및 전체 재생 시간 설정
sampling_rate = 44100  # 샘플링 레이트 (일반적인 오디오 CD 품질)
duration = data[-1][2]  # 마지막 음표의 끝나는 시간을 총 재생 시간으로 설정

# 시간 축 생성
time = np.linspace(0, duration, int(sampling_rate * duration), endpoint=False)

# 파형 데이터 생성 (초기화)
waveform = np.zeros(len(time))

#%%

# 각 음표에 대한 파형 생성 및 덮어쓰기
for start_time, freq, end_time in data[:10]:

    amplitude = 0.8  # 음표의 강도는 0.8로 고정 (필요에 따라 조정)

    # 해당 음표의 시작 및 끝 인덱스 계산
    start_index = int(start_time * sampling_rate)
    end_index = int(end_time * sampling_rate)

    # np.sin 함수를 사용하여 사인파 생성
    t = time[start_index:end_index] - start_time
    wave = amplitude * np.sin(2 * np.pi * freq * t)

    # 전체 파형에 해당 음표의 파형 덮어쓰기 (+= 대신 =)
    waveform[start_index:end_index] = wave

# 파형 데이터 그래프로 표시
plt.plot(time, waveform)
plt.xlabel("Time (seconds)")
plt.ylabel("Amplitude")
plt.title("Waveform")
plt.show()



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

def get_skeleton_in_VRsense(distance_df : pd.DataFrame, max_edge_length : float,
                            dimensions : int | list[int] ) :
    """
    DataFrame 기반 거리 행렬에서 Rips 복합체를 생성하고 지정된 차원의 심플렉스 정보를 출력합니다.

    Args:
        distance_df: 거리 정보를 담은 pandas DataFrame.
        max_edge_length: Rips 복합체 생성 시 최대 엣지 길이.
        dimensions: 정보를 보고자 하는 심플렉스의 차원(정수 또는 정수 리스트).

    Returns:
        None. 결과를 출력합니다.
    """

    # 데이터에 NaN 값이 있는지 확인하고 처리
    if distance_df.isnull().values.any():
        print("NaN values found in DataFrame. Replacing with 0.")
        distance_df = distance_df.fillna(0)

    # DataFrame의 인덱스를 저장합니다.
    original_indices = distance_df.index.tolist()

    # DataFrame을 NumPy 배열로 변환합니다.
    distance_matrix = distance_df.values

    # 1. max_edge_length 최적화
    # max_edge_length = 1.5  # 조정된 임계값

    # 2. Rips 복합체 생성
    max_dim = max(dimensions) if isinstance(dimensions, list) else dimensions  # 최대 차원 설정
    rips_complex = gd.RipsComplex(distance_matrix=distance_matrix, max_edge_length=max_edge_length)
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=max_dim)

    # Simplex Tree 정보 확인
    print(f"Number of vertices: {simplex_tree.num_vertices()}")
    print(f"Number of simplices: {simplex_tree.num_simplices()}")

    # dimensions가 list가 아닌 정수일 경우 list로 감싸서 처리
    if not isinstance(dimensions, list):
        dimensions = [dimensions]

    # 결과 저장용 딕셔너리
    result_dict = {}

    for dim in dimensions:
        simplices = []
        for simplex, _ in simplex_tree.get_skeleton(dim):
            if len(simplex) == dim + 1:  # dim차원 심플렉스는 (dim+1)개의 정점을 가짐
                # 심플렉스의 정점 인덱스를 원래 DataFrame의 인덱스로 변환
                original_indices_for_simplex = [original_indices[i] for i in simplex]
                simplices.append(set(original_indices_for_simplex))

        print('\n')
        print(f"Number of {dim}-simplices: {len(simplices)}")
        print(f"{dim}-simplices:", simplices)

        # 중복 제거 (set으로 변환)
        unique_simplices = set() # set으로 초기화
        for simplex in simplices:
            unique_simplices.add(tuple(sorted(simplex))) # 정렬된 튜플을 set에 추가

        unique_simplices = [set(s) for s in unique_simplices] # 튜플을 다시 set으로 변환

        result_dict[dim] = unique_simplices

    return simplex_tree, result_dict


simplex_tree, result_dict = get_skeleton_in_VRsense(distance_df = pitchwise_dist, 
                                    max_edge_length = 1.75, 
                                    dimensions=[1, 2, 3, 4, 5, 6])
result_dict[2]

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





#%%

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

finite_distance = timeflow_distance[timeflow_distance != np.inf]
print(finite_distance.max().max())


df = finite_distance

# 데이터프레임을 Series로 변환
series = df.stack()
series_nonzeros = series[series != 0]

# 히스토그램
plt.figure() # 새로운 Figure 객체 생성
series_nonzeros.hist(bins=20)
plt.title('Histogram of Values')
plt.xlabel('Values')
plt.ylabel('Frequency')
plt.show()

# 값의 빈도 계산
value_counts = series_nonzeros.value_counts()
value_counts