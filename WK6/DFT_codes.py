#%%
import numpy as np
import pandas as pd
import gudhi as gd
import networkx as nx
from collections import Counter
import matplotlib.pyplot as plt

from scipy.optimize import curve_fit
from scipy.stats import linregress

from util import adjust_to_eighth_note


#%%
file_name = "Ryuichi_Sakamoto_-_hibari.mid"
adjusted_notes = adjust_to_eighth_note(file_name)

adn_1 = adjusted_notes[:2006]
adn_2 = adjusted_notes[2006:]

adn_1_real = adn_1[:-59]
adn_2_real = adn_2[59:]

adjusted_notes_real = adn_1_real + adn_2_real



#%%
#######################################
########### 250324~ Week6 #############
#######################################

import util
import importlib
importlib.reload(util)
from util import notes_label_n_counts, find_multilength_pitches


#%%
notes_label, notes_counts = notes_label_n_counts(adjusted_notes_real)

# 결과 출력 (전체 결과 출력)
for note, label in notes_label.items():
    print(f"{note}: {label}")

frequent_pitches = find_multilength_pitches(notes_counts)
print("\n서로 다른 length를 갖는 조합으로 2번 이상 등장한 Notes:")
frequent_pitches


#%%
# Counter 객체를 리스트로 변환
data = list(notes_counts.items())
combination_counts_df = pd.DataFrame(data, columns=['Combination', 'Count'])
combination_counts_df

#%%
# 각 조합의 등장 횟수를 계산 (논문에서 말하는 frequency에 해당)
frequency_counts = combination_counts_df.copy()
frequency_counts.columns = ['Combination', 'Frequency']

# 빈도수를 기준으로 내림차순 정렬
frequency_counts = frequency_counts.sort_values(by='Frequency', ascending=False)

# rank 부여
frequency_counts['Rank'] = range(1, len(frequency_counts) + 1)
frequency_counts

# 플롯 생성 (선택 사항)
plt.figure(figsize=(10, 6))
plt.loglog(frequency_counts['Rank'], frequency_counts['Frequency'], marker='o', linestyle='-')
plt.xlabel("Rank (Log Scale)")
plt.ylabel("Frequency (Log Scale)")
plt.title("Frequency vs. Rank (Log-Log Scale)")
plt.grid(True, which="both", ls="-")
plt.show()


#%%

def simons_model(r, a, b, z):
    return 1 / (a + b * r)**z


frequency = frequency_counts['Frequency']
frequency = np.array(frequency)

rank = frequency_counts['Rank']
rank = np.array(rank)


# 초기 추정
initial_guess = [1, 1, 1]  # a, b, z에 대한 초기값

# curve_fit 실행
popt, pcov = curve_fit(simons_model, rank, frequency, p0=initial_guess)

# 결과 출력
a_opt, b_opt, z_opt = popt
print(f"최적화된 파라미터: a={a_opt:.3f}, b={b_opt:.3f}, z={z_opt:.3f}")

# fitting된 곡선 생성
rank_fit = np.linspace(min(rank), max(rank), 100)
frequency_fit = simons_model(rank_fit, a_opt, b_opt, z_opt)

# 플롯
plt.figure(figsize=(12, 8))
plt.loglog(rank, frequency, 'o', label="Data")
plt.loglog(rank_fit, frequency_fit, '-', label="Simon's Model Fit")

plt.xlabel("Rank (Log Scale)")
plt.ylabel("Frequency (Log Scale)")
plt.title("Frequency vs. Rank with Simon's Model Fit")
plt.grid(True, which="both", ls="-")
plt.legend()
plt.show()





#%%
# 꺾이는 점을 시각적으로 추정 (예시: 순위 8 근처)
break_point = 10

# 첫 번째 구간
rank_1 = np.log(rank[:break_point])
frequency_1 = np.log(frequency[:break_point])
slope_1, intercept_1, r_value_1, p_value_1, std_err_1 = linregress(rank_1, frequency_1)
print(f"첫 번째 구간 기울기: {slope_1:.3f}, R-squared: {r_value_1**2:.3f}")

# 두 번째 구간
rank_2 = np.log(rank[break_point:])
frequency_2 = np.log(frequency[break_point:])
slope_2, intercept_2, r_value_2, p_value_2, std_err_2 = linregress(rank_2, frequency_2)
print(f"두 번째 구간 기울기: {slope_2:.3f}, R-squared: {r_value_2**2:.3f}")

# 플롯
plt.figure(figsize=(12, 8))
plt.loglog(rank, frequency, 'o', label="Data")

# Power-law 1
rank_fit_1 = np.linspace(min(rank), rank[break_point-1], 50)
frequency_fit_1 = np.exp(intercept_1 + slope_1 * np.log(rank_fit_1))
plt.loglog(rank_fit_1, frequency_fit_1, '--', label=f"Power-law 1 (Slope: {slope_1:.3f})")

# Power-law 2
rank_fit_2 = np.linspace(rank[break_point], max(rank), 50)
frequency_fit_2 = np.exp(intercept_2 + slope_2 * np.log(rank_fit_2))
plt.loglog(rank_fit_2, frequency_fit_2, '--', label=f"Power-law 2 (Slope: {slope_2:.3f})")

plt.xlabel("Rank (Log Scale)")
plt.ylabel("Frequency (Log Scale)")
plt.title("Frequency vs. Rank with Power-Law Approximations")
plt.grid(True, which="both", ls="-")
plt.legend()
plt.show()




#%%
from piecewise import PiecewiseLinFit

# Piecewise Linear Fit 모델 생성
pwlf = PiecewiseLinFit(rank, frequency)

# 최적의 breakpoint 개수 찾기 (AIC 사용)
res = pwlf.fit_with_breaks([4, 10])  # 초기 breakpoint 추정값
print(f"최적의 breakpoint 위치: {pwlf.fit_breaks}")

# 결과 시각화
plt.figure(figsize=(10, 6))
plt.plot(rank, frequency, 'o', label='Data')
plt.plot(rank, pwlf.predict(rank), '-', label='Piecewise Linear Fit')
plt.legend()
plt.show()


#%%
#######################################
########### 250322 Saturday ###########
#######################################

from util import FourierBars, group_indices_by_element_lists, FourierMetricNorm

#%%

# just_bars_1 = FourierBars(adn_1_real, distinct=False)
just_bars_2 = FourierBars(adn_2_real, distinct=False)
# len(just_bars_1), len(just_bars_2) # (132, 136)

# inst1 기준으로 2가 다시 맞춰지는 데에는 130마디 가량 소요되지만
# (모듈의 길이가 4마디고, ABA'C 구조이므로) 마디 단위로 봤을 때 
# inst 2 자체에서 반복되는 고윳값은 29개에 불과하다. 
grouped_indices = group_indices_by_element_lists(just_bars_2)
grouped_indices 
# adn_2_real이 (33, _, _)부터라 처음 4개 list가 비어있다.

# 그래도 내가 하려는 것
# 똑같은 길이의 list 2개를 전달하면 bipartite distance 구해서 순환성, 연속성 보는데에
# 29개의 조합만 나오지는 않겠지...?ㄴㄴ

#%%
# unique_bars_1 = FourierBars(adn_1_real, distinct=True)
unique_bars_2 = FourierBars(adn_2_real, distinct=True)
# len(unique_bars_1), len(unique_bars_2) # (4, 29)

distance_bars = FourierMetricNorm(unique_bars_2, fill = False)

for i in distance_bars.keys() :
    print(f"{i} / 100 : {distance_bars[i]}")

# 새로 추가된 것만 보이고 마디 index가 1~29까지 있는데
# grouped_indices에서 보는 것과 대응되는지 모르겠다.
# 악보 확인해보면 얼추 맞는 것 같기도 하고...
# 의외로 마지막 100에 추가되는 (11, 28)에 대해 grouped_indices_2에서 확인해보면
# ---- 11: [17, 50, 83, 116], 28: [35, 68, 101, 134] ---- 
# (18, 36)마디인데, 비교해보면 5~12박(A 후반 4박 + B 전반 4박)과 17~24(A')이다. 


#%%
#######################################
########### 250325 Tuesday ############
#######################################


def rips_filtration(bars_list, dft_dict):
    
    bars = bars_list  # list of distinct musical bars, modulo t and p
    dist = dft_dict  # dictionary of DFT-distances with pair of bars
    nbr_bars = len(bars)
    vertices = [i + 1 for i in range(nbr_bars)]  # a vertex = a musical bar

    epsilon = [e for e in dist]  # scaling parameters
    epsilon.remove(0)
    epsilon.sort()

    # initialisation = complex at time 0 with only vertices
    graph_0 = nx.Graph()
    graph_0.add_nodes_from(vertices)

    filt_graph = [graph_0]  # list of graphs
    filt_complex = dict()  # list of complexes
    filt_complex[0] = {'vertices': vertices, 'edges': [], 'triangles': []}

    for i, e in enumerate(epsilon, start=1):
        
        # for each scale e put the corresponding edges to the ith graph
        graph_i = filt_graph[i - 1].copy()
        
        if isinstance(dist[e][0], int):
            graph_i.add_nodes_from(dist[e])
            print("can't be here")

        else:
            graph_i.add_edges_from(dist[e])
            # print("can be here")
        
        filt_graph.append(graph_i)
        
        # for each parameter "e" we create the corresponding ith complex
        edges_e = []  # edges list for the ith complex at scale e
        E = list(graph_i.edges())
        # print(E)
        for k in range(len(E)):
            edges_e.append(list(E[k])) # tuple을 list로 바꿔서 

        triangles_e = []  # triangles list for the ith complex at a scale e
        triangles = set()
        S = list(graph_i.nodes()) # [1, 2, ... , 136]
        gr = graph_i.copy()
        for s in S:
            Ls = list(gr.neighbors(s))
            Gs = gr.subgraph(Ls)
            Es = list(Gs.edges())
            triangles = triangles.union({frozenset([s, edge[0], edge[1]]) for edge in Es})
            gr.remove_node(s)
        for t in list(triangles):
            triangles_e.append(list(t))

        filt_complex[e] = {'vertices': vertices, 'edges': edges_e, 'triangles': triangles_e}

    return filt_complex
# 중요한 점은 함수 내에서 bars_list의 내용 자체는 사용되지 않고, 
# 단지 len(bars_list)를 통해 마디의 개수만 사용된다.

def find_keys_with_triangles(filt_complex):
    """
    filt_complex 딕셔너리에서 triangles 리스트가 비어 있지 않은 key 값들을 찾아서 반환합니다.
    """
    keys_with_triangles = []
    for key, value in filt_complex.items():
        if 'triangles' in value and value['triangles']:  # 'triangles' 키가 존재하고, 리스트가 비어 있지 않으면
            keys_with_triangles.append(key)
    return keys_with_triangles

def rips_intervals(filtration, degree):
    """
    주어진 filtration으로부터 Rips 복합체를 생성하고, 특정 차원의 persistent homology intervals을 계산합니다.

    Args:
        filtration (dict): filtration 값 (시간)을 담고 있는 딕셔너리.
                         각 filtration 값은 해당 시간에 나타나는 simplex들의 정보를 담고 있습니다.
                         예: {0: {'vertices': [...], 'edges': [...], 'triangles': [...]},
                             19: {'vertices': [...], 'edges': [...], 'triangles': [...]}, ...}
        degree (int): 계산할 homology의 차원.

    Returns:
        list: persistent intervals (birth, death) 리스트.
    """

    F = filtration
    N = len(F)  # number of complexes

    list_simplex_degree = []  # list of pairs (simplex, apparition time)

    # vertices 추가 (시간 0에만 나타나는 vertices)
    if 0 in F:
        sommets = F[0]['vertices']
        for v in sommets:
            list_simplex_degree.append(([v], 0))

    # edges, triangles 추가
    for t in F:
        if t != 0:
            if 'edges' in F[t]:
                E_t = F[t]['edges']
                for edge in E_t:
                    list_simplex_degree.append((edge, t))  # edges
            if 'triangles' in F[t]:
                T_t = F[t]['triangles']
                for triangle in T_t:
                    list_simplex_degree.append((triangle, t))  # triangles

    # filtration 값들을 이용하여 simplex tree 구성
    st = gd.SimplexTree()
    for simplex, value in list_simplex_degree:
        st.insert(simplex, filtration=value)

    st.make_filtration_non_decreasing()

    # Persistent homology 계산
    persistence = st.persistence()

    # 지정된 차수의 intervals만 추출
    intervals = []
    for dim, (birth, death) in persistence:
        if dim == degree:
            intervals.append((birth, death))

    return intervals

def rips_graphs(filtration):
    """List of associated graphs for a filtration."""
    list_graph = []
    # nbr_complexes = len(filtration)
    for t in filtration.keys() :
        C = filtration[t]
        G = nx.Graph()
        G.add_nodes_from(C['vertices'])
        G.add_edges_from(C['edges'])
        list_graph.append(G)
    return list_graph


#%%
filt_complex = rips_filtration(just_bars_2, distance_bars)
keys_with_triangles = find_keys_with_triangles(filt_complex)
for key in keys_with_triangles[:4] :
    print(key, filt_complex[key]['triangles'])

# 마디 고유값 labeling이라 실제 마디 번호랑 mapping해야 함.


#%%

intervals = rips_intervals(filt_complex, 1)
intervals

list_graph = rips_graphs(filt_complex)
list_graph

#%%

def music_graph(bars_list, dft_dict):
    """The graph-type for a midi file."""
    
    # dist = fourier_metric_norm(bars_list, u_time, u_pitch)  # Not used
    filtration = rips_filtration(bars_list, dft_dict)
    graphs = rips_graphs(filtration)
    
    inter_1 = rips_intervals(filtration, 1)
    inter_0 = rips_intervals(filtration, 0)

    inter_0e = [inter_0[i][1] for i in range(len(inter_0))]  # end of each bar in degree 0
    inter_1s = [inter_1[i][0] for i in range(len(inter_1))]  # start of each bar in degree 1

    # longest bar for H0
    m0 = {}
    for i in range(1, len(inter_0e)):
        time = inter_0e[i] - inter_0e[i - 1]
        if time not in m0:
            m0[time] = [inter_0e[i - 1]]
        else:
            m0[time].append(inter_0e[i - 1])
            
    if not m0:
        t0 = 0  # m0가 비어있을 경우 t0를 0으로 초기화
    else:
        m00 = max(list(m0.keys()))
        if np.isinf(m00):
            t0 = 0
        else:
            t0 = int(m0[m00][0]) # int로 변경

    # truncation of H1 from t0
    L = [i for i in range(101)]
    L0 = L[t0:]
    m = []
    for i in L0:
        if i in inter_1s:
            m.append(i)

    s = inter_1s.index(min(m))
    inter_1s = inter_1s[s:]

    # longest bar for H1
    m1 = {}
    for i in range(1, len(inter_1s)):
        time = inter_1s[i] - inter_1s[i - 1]
        if time not in m1:
            m1[time] = [inter_1s[i - 1]]
        else:
            m1[time].append(inter_1s[i - 1])

    m11 = max(list(m1.keys()))
    t1 = m1[m11][0]

    if t1 == 100:
        t1 = t0

    # final graph-type
    print('Error margin t0 (%) :', t0)
    print('Error margin t1 (%) :', t1)
    return graphs[t1]

graphs = music_graph(just_bars_2, distance_bars)
graphs
# %%
