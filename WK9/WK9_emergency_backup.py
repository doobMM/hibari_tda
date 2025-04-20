# %% [markdown]
# ### 1-1. midi 파일 전처리

# %%
from util import adjust_to_eighth_note

file_name = "Ryuichi_Sakamoto_-_hibari.mid"
adjusted_notes = adjust_to_eighth_note(file_name)

adn_1 = adjusted_notes[:2006]
adn_2 = adjusted_notes[2006:]

adn_1_real = adn_1[:-59]
adn_2_real = adn_2[59:]

adjusted_notes_real = adn_1_real + adn_2_real
adjusted_notes_real

# %% [markdown]
# * adn_i_chord_(i = 1, 2)는 두 list에서 동시에 연주되는 범위(5~132마디)에 해당됩니다.

# %%
from util import label_active_chord_by_onset

adn_1_chord = label_active_chord_by_onset(adn_1_real)
adn_2_chord = label_active_chord_by_onset(adn_2_real)

adn_1_chord_ = adn_1_chord[33:] 
adn_2_chord_ = adn_2_chord[:-32]

chord_1_132 = adn_1_chord.copy()
chord_2_132 = [None, *adn_2_chord]
# each of which is of length 1056 (132 bars)

# chord_1_132는 규칙적으로 반복되므로 굳이 solo 파트를 뒤로 붙이지 않아도
# chord_2_132와 원형적 alignness를 보고자 할 때 가능하다.

adn_1_chord_ = chord_1_132[:-32]
adn_2_chord_ = chord_2_132[:-32]
adn_2_chord_

# %%
# module_chord_label = pd.DataFrame(adn_1_chord[:32])
# module_chord_label.value_counts().to_frame()

# %% [markdown]
# * 곡에서 반복되는 단위를 추출하고(module_notes), 각 시점에서 활성화된 음들을 모아(active_module) 화음 단위로 정제합니다.
# * 화음에 대해 3가지 방식으로 딕셔너리를 만듭니다.

# %%
from util import (group_notes_with_duration_, notes_label_n_counts, 
                  chord_label_to_note_labels, transform_dict, chord_label_dict)

module_notes = adn_1_real[:59]
active_module = group_notes_with_duration_(module_notes)

notes_label, notes_counts = notes_label_n_counts(module_notes)
chord_label = chord_label_dict(active_module)

# notes = (pitch, duration)
notes_dict = chord_label_to_note_labels(chord_label, notes_label)
pitches_dict = transform_dict(chord_label)
pitch_classes_dict = transform_dict(chord_label, project=True)

# %%
notes_label

# %%
notes_dict

# %% [markdown]
# * 시간축에 대해서는 t_i, t_j (i != j) 간에 weight를 준다면 동시에 타건 혹은 같은 시점에 활성화되어있는 소리의 단위끼리도 weight를 주어봅니다.

# %%
# simul 거리공간 정의 및 cycle 탐지 및 대조 용도
from util import get_simul_connected, get_distance_matrix_from, get_LTMpart_of

simul_notes_weight = get_simul_connected(adn_1_chord_, adn_2_chord_, notes_dict)
simul_notes_dist = get_distance_matrix_from(simul_notes_weight)
simul_dist_n = get_LTMpart_of(simul_notes_dist)

# simul_pitches = get_simul_connected(adn_1_chord_, adn_2_chord_, pitches_dict)
# simul_pitch_classes = get_simul_connected(adn_1_chord_, adn_2_chord_, pitch_classes_dict)

# %% [markdown]
# * 총 17개의 화음이 등장하고, 각 instrumental의 솔로 구간이 있어 17 choose 2 + 17 = 153개의 조합이 등장할 거란 예상처럼 0 ~ 152까지의 value가 발견됩니다.

# %%
from util import simul_chord_lists, label_simul_chords_combi

simul_chords_key = simul_chord_lists(adn_1_chord_, adn_2_chord_)
simul_chord_comb_dict = label_simul_chords_combi(simul_chords_key)

for item_set, label in simul_chord_comb_dict.items():
    print(f"{set(item_set)}: {label}")

# %% [markdown]
# * 밑에 있는 search_optimal_rate_n_dict 함수에 쓰일 intra_weights와 inter_weight를 구하고, plot에 쓰기 위해 각 딕셔너리의 이름을 추가합니다.

# %%
from util import get_chords_intra_connected, get_chords_inter_connected

weight_mtrx_1 = get_chords_intra_connected(adn_1_chord_, lag=1)
weight_mtrx_2 = get_chords_intra_connected(adn_2_chord_, lag=1)
weight_mtrx = get_chords_inter_connected(adn_1_chord_, adn_2_chord_, lag=1)

intra_weights = weight_mtrx_1 + weight_mtrx_2
inter_weight = weight_mtrx

notes_dict['name'] = 'notes_dict'
pitches_dict['name'] = 'pitches_dict'
pitch_classes_dict['name'] = 'pitch_classes_dict'

# %% [markdown]
# * 밑에 search_optimal_rate_n_dict에서 rate_end를 1.5로 설정한 것이 임의가 아님에 대한 설명 요망
# * 1(np.inf 대신 넣어놓은)보다 작은 distance 값이 0.5인데, 애초에 1을 np.inf 대신 넣어놓은 만큼
# * rate가 변함에 따라 해당 edge를 포함한 삼각형 이상의 simplex가 나오지 않도록 설정해야 함.

# %%
import numpy as np
from util import is_distance_matrix_from, plot_dist_distr, get_unique_dist_n_diff

timeflow_weight = inter_weight + intra_weights
timeflow_distance = is_distance_matrix_from(timeflow_weight, notes_dict)

plot_dist_distr(timeflow_distance)

unique_distance, differences = get_unique_dist_n_diff(timeflow_distance)

print(min(differences))
print(np.mean(differences))
print(np.std(differences))

# %%
unique_distance.sort()
unique_distance

# %%
timeflow_weight

# %%
"""
listofDimension
[1, 2, 3] : 33.2s
[1] : 0.1s
[2] : 2.2s /   '(5, 18, 19) - (9, 18, 19) + (3, 5, 19) - (3, 9, 19) + (5, 11, 18) - (9, 11, 18) - (3, 5, 11) + (3, 9, 11)']]
[3] : 36.7s /   '-(0, 5, 9, 13) + (3, 5, 9, 13) + (2, 3, 9, 13) + (0, 5, 7, 13) - (3, 5, 7, 13) - (2, 3, 7, 13) + (0, 5, 9, 10) - (3, 5, 9, 10) - (2, 3, 9, 10) - (0, 5, 7, 10) + (3, 5, 7, 10) + (2, 3, 7, 10) + (0, 1, 9, 13) + (1, 2, 9, 13) - (0, 1, 9, 10) - (1, 2, 9, 10) - (0, 1, 7, 13) - (1, 2, 7, 13) + (0, 1, 7, 10) + (1, 2, 7, 10)']]
[1, 2] : 2.1s
[2, 3] : 33.6s
"""

print("generateBarcode 실행결과")

# %% [markdown]
# ### 1-2. 거리행렬 기반 사이클 분석

# %%
# from util import find_non_triangle_inequality, plot_d_edge_ratio, plot_higher_homol
import matplotlib.pyplot as plt
from util import is_distance_matrix_from, generateBarcode, analyze_lifespans, plot_lifespan_results

def search_optimal_rate_n_dict(intra_weights, inter_lag : int = 1, refine_dict : dict = notes_dict,
                                rate_start = 0.00, rate_end = 1.5, step = 0.01,
                                loglog : bool = True) :
    
    inter_weight = get_chords_inter_connected(adn_1_chord_, adn_2_chord_, lag=inter_lag)
    
    start = round(rate_start / step)
    end = round(rate_end / step)

    cycles_profile = []
    cycles_births = []
    higher_homol = []
    d_edge_ratios = []

    for a in range(start, end, 1) :
        rate = round(a * step, 4)
        print(f"on rate {rate}...")

        timeflow_weight = intra_weights + rate * inter_weight 
        timeflow_distance = is_distance_matrix_from(timeflow_weight, refine_dict)

        birthDeath = generateBarcode(mat = timeflow_distance.values, exactStep = True, birthDeathSimplex=False, sortDimension=False)
        result_1 = (rate, birthDeath)
        cycles_profile.append(result_1)

    cycles_info = analyze_lifespans(cycles_profile)

    plot_lifespan_results(cycles_info, refine_dict = refine_dict, inter_lag = inter_lag, loglog=loglog)

    return d_edge_ratios, cycles_profile, cycles_births, higher_homol

# (cycles_info_n1, cycles_vertices_n1, cycles_births_n1, cycles_edges_n1) = 
(d_edge_ratio_n1, cycles_profile_n1, 
 cycles_births_n1, higher_homol_n1) = search_optimal_rate_n_dict(intra_weights)

# %% [markdown]
# * cycle_profile에 저장되어있는 정보를 딕셔너리로 정제합니다.
# * key : 사이클을 구성하는 vertex들을 가장 작은 정수로 레이블링된 것부터 연결된 순서대로 나열
# * value : 해당 사이클이 발견된 시점에 대해 (rate, birth, death) tuple를 담은 리스트

# %%
from util import get_rBD_groupedBy_cycle

cycle_persistence = get_rBD_groupedBy_cycle(cycles_profile_n1)
cycle_persistence

# %% [markdown]
# * 같은 vertex로 구성되어 있지만 inter_weight와 intra_weight의 비율이 변함에 따라 연결 순서가 달라지는 경우가 5건 관찰됩니다.
# * generateBarcode 함수에서 DeathSimplex를 분석하는 기능을 이용해 어떻게 이럴 수 있는지 확인할 예정입니다.
# * 2, 3번째 경우는 중간에 해당 Vertices 조합으로 사이클이 나타나지 않는 구간이 있는 반면 1, 4, 5번째 경우는 연속적이어서 DeathSimplex가 동일하지 않을까 예상됩니다.

# %%
from util import check_rearranged_cycles

# 동일 Cycle 확인 함수 호출
rearranged_cycles = check_rearranged_cycles(cycle_persistence)

# %% [markdown]
# * 사이클 갯수에 대한 위의 plot은 대강 0.03, 0.5, 0.65, 0.95를 기점으로 계단이 나뉘고 진동을 하고 있었다.
# * (불연속, 4 / 48)
# * 1. (0, 6, 21, 1)이 사이클 갯수 진동에 전체적으로 책임이 있는 것으로 보이며, life가 정말 짧아 노이즈가 아닌가 싶다.
# * 2. (5, 6, 9, 18, 8, 15), (5, 10, 9, 18, 8, 15) 역시 사이클이 존재하는 구간이 연속적이지 않고 약간 띄엄띄엄한데 흥미롭다.
# * 3. (0, 19, 22, 1)은 0.01에서만 불연속한다.

# %%
from util import find_non_continuous_cycles

non_continuous_cycles = find_non_continuous_cycles(cycle_persistence, step = 0.01)
for cycle in non_continuous_cycles.keys() :
    print(cycle)

    for rate, birth, death in cycle_persistence[cycle][:5] :
        print(rate)
        
    # print("\n")

# %%
for i in range(len(non_continuous_cycles[(0, 19, 22, 1)]) - 1):
    rate_diff = round(non_continuous_cycles[(0, 19, 22, 1)][i+1][0] - non_continuous_cycles[(0, 19, 22, 1)][i][0], 2)
    if rate_diff != 0.01 :
        print(non_continuous_cycles[(0, 19, 22, 1)][i], non_continuous_cycles[(0, 19, 22, 1)][i+1])

# %%
from util import plot_cycle_BirthDeath_over_rate

plot_cycle_BirthDeath_over_rate(non_continuous_cycles, subplot_in_a_row = 3)

# %% [markdown]
# * (연속, 44/48)
# * 4. (0, 1, 2, 18), (0, 15, 22, 1), (1, 2, 3, 19, 22), (0, 13, 9, 14, 18, 5, 16)의 4개는 0.0에서만 등장하는 intra_weight에 기인할 것으로 예상된다.
# * 5. rate가 커짐에 따라 life가 길어지는 사이클의 경우엔 inter_weight에 기인할 것으로 예상된다. 
# * 6. rate = 0.0에선 등장하지 않다가 y = 1/x 꼴로 death가 birth에 점근적으로 가까워지는 사이클들도 몇 있다.

# %%
continuous_cycles = dict()
for cycle in cycle_persistence.keys() :
    if cycle not in non_continuous_cycles.keys():
        continuous_cycles[cycle] = cycle_persistence[cycle]

# %%
plot_cycle_BirthDeath_over_rate(continuous_cycles, subplot_in_a_row = 4)

# %% [markdown]
# * 아주 잠깐씩 나타나던 (0, 6, 21, 1)은 rate에 따라 BirthDeath가 달라지는데
# * 확인해보면 life 길이의 고윳값(eigenvalue X unique() O)이 2개뿐이어서
# * 왜 이런지 이해가 필요하다, getBarcode에서 exactStep = True 옵션으로 했는데...

# %%
for rBD in cycle_persistence[(0, 6, 21, 1)][:5] :
    print(rBD)

# %%
lifes = set()
for i in range(len(cycle_persistence[(0, 6, 21, 1)])) :
    # 각 rate에서 death - birth를 계산하는 것
    life = cycle_persistence[(0, 6, 21, 1)][i][2] - cycle_persistence[(0, 6, 21, 1)][i][1]
    lifes.add(life)
    print(life)

print("\n")
print(f"cycle (0, 6, 21, 1) could persist for {len(lifes)} options in terms of its life, ")
print(f"each of which is {lifes}")


# %% [markdown]
# *  사이클의 리스트는 중첩행렬을 만드는 함수(get_overlapped)에 입력값으로 쓰입니다.

# %%
cycles = []
for cycle in cycle_persistence.keys() :
    cycles.append(cycle)
    
print(cycles[:5])
print("Total number of cycles: ", len(cycles))

# %% [markdown]
# * 악보 전체 범위에 대한 Chord labelled list (simul_whole_c)를 만들고, notes_dict를 이용해 note labelling을 해줍니다.
# * inst 1은 마지막 4마디에 쉬고, inst 2는 처음 4마디를 쉽니다. 

# %%
from util import simul_chord_lists, simul_mapped_by_dict

adn_1_whole_c = [*adn_1_chord, *([None] * 32)]
adn_2_whole_c = [*([None] * 32), *chord_2_132]

simul_whole_c = simul_chord_lists(adn_1_whole_c, adn_2_whole_c)
simul_notes = simul_mapped_by_dict(simul_whole_c, notes_dict)

print("At First bar, inst 1 playes solo", simul_notes[0:5])
print("At Fifth bar, inst 1 & 2 play   ", simul_notes[32:37])

# print(simul_notes[:32] == simul_notes[-32:]) # True (firth 4 and last 4 bars are played solo)
# print(simul_notes[:33] == simul_notes[-33:]) # False

# %% [markdown]
# * notes_dict에 들어있는 note의 label 역시 리스트로 담아줍니다.

# %%
notelist = []
for note in notes_label.values() :
    notelist.append(note)

# %% [markdown]
# ### 2. Zipf's Law

# %% [markdown]
# ### 3. DFT (Discrete Fourier Transform)


