#%%
import sys
lib_dir = r'C:\Users\82104\AppData\Local\Programs\Python\Python310\Lib\site-packages'
sys.path.append(lib_dir)

import librosa
import mido
from mido import MidiFile
import pretty_midi

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from collections import defaultdict


from util import (adjust_to_eighth_note, notes_freq_gcd_checker, 
        midi_to_note, midi_to_frequency, notes_analyzer,
        group_pitches, reduce_notes)


#%%
file_name = "Ryuichi_Sakamoto_-_hibari.mid"
midi_file_path = file_name  # 여기에 MIDI 파일 경로를 입력하세요.
adjusted_notes = adjust_to_eighth_note(midi_file_path)


#%%
# instrument 단위로 자른 list
adn_1 = adjusted_notes[:2006]
adn_2 = adjusted_notes[2006:]


# module of melody keeps being repeated
limit = min(len(adn_1), len(adn_2))

pitch_1 = []
for start, pitch, end in adn_1[:limit] :
    pitch_1.append(pitch)

pitch_2 = []
for start, pitch, end in adn_2[:limit] :
    pitch_2.append(pitch)

if not pitch_1 == pitch_2 :
    print("inconsistent notes proceeding detected")


# while when to start is differ by 'instrument' 
limit_ = min(len(adn_1), len(adn_2))
for i in range(0, limit_) :
    limit = i

    start_1 = []
    for start, pitch, end in adn_1[:limit] :
        start_1.append(start)

    start_2 = []
    for start, pitch, end in adn_2[:limit] :
        start_2.append(start)

    if not start_1 == start_2 :
        print("inconsistent onsets period detected at index")
        print(i)
        break



#%%
adn_1_real = adn_1[:-59]
adn_2_real = adn_2[59:]

adjusted_notes_real = adn_1_real + adn_2_real

num_repeat_1 = len(adn_1_real) / 59
num_repeat_2 = len(adn_2_real) / 59

print(f'the number of time for each part to iterate module is repectively, {num_repeat_1, num_repeat_2}')
print("\n")

notes_freq_gcd_checker(adjusted_notes_real)


#%%
# 편의상 똑같이 자른다. 길이는 다르지만 시작과 마지막 부분은 같다.
adn_1_ = adn_1[59:-59]
adn_2_ = adn_2[59:-59]

# adn_1_은 주기적으로 전개되는 것을 확인할 수 있다.
# 1888 = len(adn_1) - 118
for i in range(0, 1888, 59) :
    print(adn_1_[i], adn_1_[i][0]/32)


# adn_2_는 조금씩 밀려나는 것을 확인할 수 있다.
# 1829 = len(adn_2)-118
j = 0
misfitness = []
for i in range(0, len(adn_2)-118, 59) :
    misfit_i = adn_2_[i][0]/32 - (j+1)
    misfitness.append(misfit_i)
    print(adn_2_[i], misfit_i)
    j += 1

# len(misfitness) = 31
misfit_diff = set()
for i in range(30) :
    diff = misfitness[i+1] - misfitness[i]
    misfit_diff.add(diff)

misfit_diff # 0.03125 = 1 / 32 = 1 / (8*4). 즉 정확히 8분음표씩 밀려났음을 함의



#%%

adjusted_notes_ = adn_1_ + adn_2_
notes, pitch_to_note, pitch_to_freq = notes_analyzer(adjusted_notes_,
                                                     give_dict = True)

notes['Notes'] = notes['Note Name'].apply(reduce_notes)

notes_cnts = notes.groupby('Notes')['count'].sum().reset_index()

# print(np.gcd.reduce(notes_cnts['count'].unique()))
notes_cnts

# 한 모듈 당 각각 계이름이 등장하는 횟수
# adjusted_notes_에서 모듈은 inst 1에서 32, inst 2에서 31번 반복된다. 
notes_cnts['count'] / 63




#%%
step = 59
list_to_see = adn_1_real
len_list = len(list_to_see)
iteration = round(len_list/step)

modules_analyzed = []
for i in range(0, iteration) :
    module_pitch = list_to_see[step*i : step*(i+1)] 
    module_note = [(x, pitch_to_note.get(y, y), z) for x, y, z in module_pitch]

    # 그룹화된 데이터 얻기
    module_gp = group_pitches(module_note, pithces_only=True)
    modules_analyzed.append(module_gp)

modules_analyzed

#%%
parts_to_check = []
for i in range(iteration-1): # len(modules_analyzed) = 33 = 1947 / 59
    for j in range(35) : # len(modules_analyzed[i]) for any i
        if not modules_analyzed[i][j] == modules_analyzed[i+1][j] :
            parts_to_check.append((i, j))
    print(i)

# pitch가 전개되는 것만 비교하면 같다.
parts_to_check

# %%
# 결과 출력
for item in module_gp:
    print(item)




#%%
## module extraction
# length : 59 tuple, 4 bars, 32 quiver notes
# pitch : 17
# chord : 16

module_pitch = adn_1_real[:59]
module_note = [(x, pitch_to_note.get(y, y), z) for x, y, z in module_pitch]
module_dict = defaultdict(set)

for start, pitch, end in module_note:
    for i in range(start, end):
        module_dict[i].add(pitch)

unique_sets = set()

# result 딕셔너리의 values를 순회하며 고유한 set을 찾음
for value_set in module_dict.values():
    unique_sets.add(frozenset(value_set)) # set은 hashable하지 않아서 frozenset으로 바꿔줘야 한다.

# 결과 출력 (frozenset은 set으로 다시 변환하여 출력)
for unique_set in unique_sets:
    print(set(unique_set))
    # print(unique_set)




#%%
########################################################
############## STILL WORKING ON IT #####################
########################################################
########################################################

# 전반부

# 각 unique_set의 유지 기간을 저장할 딕셔너리
persistence = {}

# unique_sets 순회
for s in unique_sets:
    persistence[frozenset(s)] = 0  # 초기화
    start_index = -1
    end_index = -1

    # module_dict 순회하며 해당 set이 나타나는 구간 찾기
    for i in range(16):
        if module_dict[i] == s:
            if start_index == -1:
                start_index = i
            end_index = i

    # 유지 기간 계산
    if start_index != -1:
        persistence[frozenset(s)] = end_index - start_index + 1

# 결과 출력
for s, duration in persistence.items():
    print(f"{set(s)}: {duration}")







#%%
## 모델 학습 시 엔트로피 함수 적용할 버전 1
# all_pitches = list(notes['Note Name'].unique())
all_pitches = ['C5','E4', 'D5', 'G4', 'A4', 'F4', 'B3', 'E5', 'A3', 
               'C4', 'B4', 'G5', 'E3', 'F3', 'D4', 'G3', 'A5']

# DataFrame 생성을 위한 데이터 준비
df_data = {}
for pitch in all_pitches:
    df_data[pitch] = [1 if pitch in module_dict[i] else 0 for i in range(len(module_dict))]

# DataFrame 생성
df = pd.DataFrame(df_data)
df




#%%
## 모델 학습 시 엔트로피 함수 적용할 버전 2
notes_group = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

# DataFrame 생성을 위한 데이터 준비
df_data = {}
for note in notes_group:
    df_data[note] = [0] * len(module_dict)  # 초기값을 0으로 설정

    for i in range(len(module_dict)):
        count = 0
        for pitch in module_dict[i]:
            if pitch.startswith(note):
                count += 1
        df_data[note][i] = count  # 해당 group으로 시작하는 pitch 개수를 저장

# DataFrame 생성
df_ = pd.DataFrame(df_data)
df_





# %%

# 각 인덱스가 나타내는 화음 구성이 무엇인지와
# 한 모듈 안에서 각 화음이 몇 번씩 등장하는지.

#############################################
### adjacent matrix를 만들기 위한 시도 #######
### bipartite 가중치 ########################
#############################################
### 가설 : module 자체에 내제된 빈도수만큼으로 환원될 것이다.
################## 250317 ##################

from util import label_active_chord_by_onset

adn_1_chord = label_active_chord_by_onset(adn_1_real)
adn_2_chord = label_active_chord_by_onset(adn_2_real)

print(len(adn_1_real) / 59, len(adn_2_real) / 59)
print(len(adn_1_chord) / 32, (len(adn_2_chord) + 1) / (32 + 1))

## 32개의 모듈 사이에 있는 31개의 쉼표가 있는데
## 첫번째 모듈 앞에도 8분쉼표를 하나 더해놓고 33으로 나눠야 모듈 횟수가 나온다.
# empty_indices = [i for i, x in enumerate(adn_2_chord) if x is None]
# for idx in empty_indices :
#     print(idx%32)
  

#%%
# (length of adn_i_chord) = (# module repeated) * (length of each period)
# 1056 = 33 * 32
# 1 + 1055 = 32 * 33 
# 임을 고려할 때

# 아래와 같이 처리해야 인덱스별로 동기화된 가중치 계산이 가능하다.
# 둘 다 길이가 1023이 되었다.
adn_1_chord_ = adn_1_chord[33:] # 5마디 2박자 ~ 132마디
adn_2_chord_ = adn_2_chord[:-32] # 5마디 2박자 ~ 132마디


#%%

from util import compare_lists

lag = 1
weight_mtrx = compare_lists(adn_1_chord_, adn_2_chord_, lag)
weight_mtrx = pd.DataFrame(weight_mtrx)
weight_mtrx

# %%
module_chord_label = pd.DataFrame(adn_1_chord[:32])
module_chord_label.value_counts()

