# Topological Data Analysis를 활용한 음악 구조 분석 및 위상 구조 보존 기반 AI 작곡 파이프라인

**저자:** 김민주
**지도:** 정재훈 (KIAS 초학제 독립연구단)
**작성일:** 2026

---

## 2. 수학적 배경

본 절에서는 본 연구의 파이프라인을 이해하기 위해 필요한 수학적 도구들을 정의하고, 각 도구가 음악 구조 분석에서 어떻게 사용되는지를 서술한다.

---

### 2.1 Vietoris-Rips Complex

**정의 2.1.** 거리 공간 $(X, d)$와 양의 실수 $\varepsilon > 0$이 주어졌을 때, **Vietoris-Rips complex** $\text{VR}_\varepsilon(X)$는 다음과 같이 정의되는 복합체(simplicial complex)이다:

$$
\text{VR}_\varepsilon(X) = \left\{ \sigma \subseteq X \,\middle|\, \forall x_i, x_j \in \sigma,\ d(x_i, x_j) \le \varepsilon \right\}
$$

즉, **점 집합 $X$의 부분집합 $\sigma$**에 속한 모든 점 쌍 사이의 거리가 $\varepsilon$ 이하이면 $\sigma$를 심플렉스(simplex)로 포함시킨다.

**구성 요소:**
- 0-simplex (vertex): 각 점 $x_i \in X$. 단일 점은 거리 조건이 없으므로 어떤 $\varepsilon$에서도 포함된다.
- 1-simplex (edge): $d(x_i, x_j) \le \varepsilon$인 두 점의 쌍 $\{x_i, x_j\}$
- 2-simplex (triangle): 세 점이 서로 모두 $\varepsilon$ 이내인 부분집합
- $k$-simplex: $k+1$개의 점이 서로 모두 $\varepsilon$ 이내인 부분집합

**Filtration 구조와 nested 성질의 직관.** $\varepsilon$ 값을 0부터 연속적으로 키우면, 점 집합 $X$ 자체는 변하지 않은 채 **새로운 심플렉스만 점차 추가된다**. 점 자체는 $\varepsilon = 0$부터 이미 0-simplex로 존재하므로 사라지지 않으며, 어떤 두 점 사이 거리가 $\varepsilon$ 임계를 처음 넘는 순간에 그 두 점을 잇는 1-simplex가 추가된다. 마찬가지로 세 점이 모두 $\varepsilon$ 이내가 되는 순간 2-simplex(삼각형)가 추가된다. 즉, $\varepsilon_1 < \varepsilon_2$이면 $\text{VR}_{\varepsilon_1}(X)$의 모든 심플렉스가 $\text{VR}_{\varepsilon_2}(X)$에도 그대로 들어 있으며, 새 심플렉스가 추가될 뿐이다. 따라서 다음의 포함관계는 항상 성립한다:

$$
\emptyset \subseteq \text{VR}_{\varepsilon_0}(X) \subseteq \text{VR}_{\varepsilon_1}(X) \subseteq \text{VR}_{\varepsilon_2}(X) \subseteq \cdots \subseteq \text{VR}_{\varepsilon_n}(X)
$$

여기서 $\varepsilon_0 < \varepsilon_1 < \varepsilon_2 < \cdots$는 새로운 심플렉스가 추가되어 복합체의 **연결 구조 또는 구멍 구조**(이를 위상이라 부른다)가 변하는 임계값들이다. 즉, 점이 추가되거나 사라지는 것이 아니라, 같은 점들 사이에 새로운 연결(edge, 삼각형 등)이 생기면서 cycle이나 void가 형성되거나 채워지는 변화이다.

표기 편의를 위해 $K_{\varepsilon_i} := \text{VR}_{\varepsilon_i}(X)$로 두면:

$$
\emptyset \subseteq K_{\varepsilon_0} \subseteq K_{\varepsilon_1} \subseteq K_{\varepsilon_2} \subseteq \cdots \subseteq K_{\varepsilon_n}
$$

이를 **filtration**이라 부르며, 변화가 일어나는 미지수 $\varepsilon_i$들이 곧 위상 구조의 birth/death 시점이 된다.

**본 연구에서의 사용:** $X = \{n_1, n_2, \ldots, n_{23}\}$은 hibari에 등장하는 23개의 고유 note이며, $d(n_i, n_j)$는 두 note 간 거리이다. $\varepsilon$를 점진적으로 증가시키며 simplex complex의 변화를 추적하여, 어떤 거리 척도에서 어떤 cycle이 출현·소멸하는지를 분석한다.

---

### 2.2 Simplicial Homology

**정의 2.2.** Simplex complex $K$에 대해 $n$차 호몰로지 군(homology group) $H_n(K)$는 $K$ 안에 존재하는 $n$차원 "구멍"의 대수적 표현이다. 직관적으로:

- $H_0(K)$: 연결 성분(connected components)의 개수
- $H_1(K)$: cycle의 개수 (1차원 구멍, 즉 닫힌 고리 모양으로 둘러싸인 영역)
- $H_2(K)$: 2차원 빈 공간(void)의 개수 (3차원 공동을 둘러싼 표면)

**구멍을 만들기 위해 필요한 최소 점의 개수.**
- 1차원 cycle (1차원 구멍): 최소 3개의 점이 필요하다. 세 점을 잇는 1-simplex 3개가 삼각형 모양의 폐곡선을 만들되, 그 내부를 채우는 2-simplex(삼각형)가 없을 때 cycle로 인식된다. 본 연구의 알고리즘에서는 4개 이상의 점으로 구성된 cycle을 주로 다룬다 (3점 cycle은 즉시 삼각형으로 채워질 가능성이 높기 때문).
- 2차원 void (2차원 구멍): 최소 4개의 점이 필요하다. 4개의 점이 사면체(tetrahedron)의 boundary를 이루되, 사면체 내부를 채우는 3-simplex가 없을 때 void가 인식된다.
- $n$차원 구멍: 최소 $n+2$개의 점이 필요하다.

**Betti number** $\beta_n = \text{rank}(H_n(K))$는 $n$차원 위상 특징의 개수를 나타낸다. 예컨대 $\beta_1 = 3$이면 이 simplex complex 안에 서로 독립적인 cycle이 3개 있다는 뜻이다.

![Simplicial homology의 직관: cycle과 void](simplicial_homology.png)

*그림 2.2. (좌) 1차원 cycle: 4개 점이 만드는 사각형의 boundary. 내부 2-simplex가 없으므로 $H_1$의 generator 1개. (우) 2차원 void: 4개 점이 만드는 tetrahedron의 boundary (4개 삼각형 면). 내부 3-simplex가 없으므로 $H_2$의 generator 1개.*

**본 연구에서의 사용:** 본 연구는 주로 $H_1$ (1차 호몰로지)을 다룬다. 이는 음악 네트워크에서 서로 가까운 note들이 만드는 닫힌 cycle, 즉 순환적으로 연결된 note 그룹을 포착한다. 발견된 각 cycle은 곡의 구조적 반복 단위로 해석된다.

---

### 2.3 Persistent Homology

Filtration $K_{\varepsilon_0} \subseteq K_{\varepsilon_1} \subseteq \cdots \subseteq K_{\varepsilon_n}$에서, 각 단계마다 $H_1$의 cycle 구조가 달라진다. **Persistent homology**는 이 과정에서 각 cycle이 어느 $\varepsilon_i$에서 처음 나타나고(**birth**) 어느 $\varepsilon_j$에서 사라지는지(**death**)를 추적한다.

**Birth와 death의 음악적 의미:**
- **Birth** $b$: 거리 임계값 $\varepsilon$가 충분히 커져서 새로운 cycle이 형성되는 순간. 음악적으로는 "이 거리 척도에서 처음으로 닫힌 반복 구조가 발견되는 시점".
- **Death** $d$: 더 큰 $\varepsilon$에서 그 cycle 내부가 더 작은 simplex들로 채워져 cycle이 더 이상 독립적이지 않게 되는 순간. 음악적으로는 "거리 척도가 너무 느슨해져서 이 cycle이 다른 구조에 흡수되는 시점".

각 cycle은 $(b, d)$ 쌍으로 기록되며, 본 연구에서는 이 쌍의 모음을 곡의 **위상적 지문(topological signature)**으로 사용한다.

**Persistence:** $\text{pers}(\text{cycle}) = d - b$. (death가 birth보다 항상 크므로 양수.) 큰 persistence를 갖는 cycle은 다양한 거리 척도에서 살아남으므로 **위상적으로 안정한 구조**이며, 작은 persistence는 일시적이거나 노이즈에 가까운 구조이다.

**알고리즘적 측면:** 본 연구에서는 persistent homology 계산에 두 가지 구현을 사용하였다.

1. **pHcol algorithm** (정재훈 외, 2024): 순수 Python 구현. 알고리즘 검증과 디버깅에 활용.
2. **Ripser** (Bauer, 2021): C++ 기반 최적화 구현. 동일한 결과를 약 45배 빠르게 계산하므로 본격 실험에 사용.

**본 연구에서의 사용:** 거리 행렬 $D \in \mathbb{R}^{23 \times 23}$로부터 Vietoris-Rips filtration을 구성하고, 각 rate parameter $r$ (가중치 비율, 후술)에서의 $H_1$ persistence를 계산한다. 발견된 모든 $(b, d)$ 쌍이 cycle 집합을 정의하며, 이 cycle들이 다음 절의 중첩행렬 구축에 사용된다.

---

### 2.4 Tonnetz와 음악적 거리 함수

**정의 2.4.** Tonnetz(또는 tone-network)는 pitch class 집합 $\mathbb{Z}/12\mathbb{Z}$를 평면 격자에 배치한 구조이다. 여기서 **pitch class**는 옥타브 차이를 무시한 음의 동치류로, 예컨대 C4 (가운데 도), C5 (한 옥타브 위 도), C3 등은 모두 같은 pitch class "C"에 속한다. 12음 평균율(12-TET)에서는 한 옥타브 안에 12개의 pitch class가 있으며, 이를 정수 $\{0, 1, 2, \ldots, 11\}$에 대응시켜 $\mathbb{Z}/12\mathbb{Z}$로 표기한다 (0=C, 1=C♯, 2=D, ..., 11=B). 두 pitch class가 격자 위에서 가까운 것은 음악 이론적으로 어울리는 음(consonant)임을 의미한다.

**Tonnetz의 격자 구조.** pitch class $p \in \mathbb{Z}/12$를 좌표 $(x, y)$에 배치하되, 다음 관계를 만족시킨다:
- 가로 이동 (+1 in $x$): 완전5도 (perfect fifth, +7 semitones)
- 대각선 이동 (+1 in $y$): 장3도 (major third, +4 semitones)

이렇게 배치하면 자연스럽게 단3도(+3 semitones) 관계도 다른 대각선 방향으로 형성되어 삼각형 격자가 만들어진다. 그림 2.1은 hibari의 C장조 음역에 해당하는 일부분을 보여준다.

![Tonnetz 격자 다이어그램](tonnetz_lattice.png)

*그림 2.1. Tonnetz 격자 구조. 가로 방향은 완전5도(C→G→D→A→E…), 대각선 방향은 장3도(C→E→G♯…)와 단3도(C→A→F♯…)로 이동한다. 삼각형 하나는 하나의 장3화음(major triad) 또는 단3화음(minor triad)에 대응된다.*

**Tonnetz 거리.** 두 pitch class $p_1, p_2$ 사이의 Tonnetz 거리 $d_T(p_1, p_2)$는 격자 위 최단 경로 길이(즉, edge 수)로 정의된다:

$$
d_T(p_1, p_2) = \min \left\{ |x_1 - x_2| + |y_1 - y_2| \,\middle|\, (x_i, y_i)\ \mathrm{represents}\ p_i \right\}
$$

격자의 모든 edge가 단위 길이 1로 동등하게 가중되므로, 출발 노드에서 시작해 인접한 노드를 한 층씩 확장해 나가는 **너비 우선 탐색(BFS)**이 정확한 최단 경로를 보장한다 (Dijkstra 같은 가중치 그래프 알고리즘은 불필요). 본 연구에서는 12개 pitch class 모두에 대해 BFS로 사전 계산된 $12 \times 12$ 거리 테이블을 사용한다.

**빈도 기반 거리 $d_{\text{freq}}$.** 본 연구의 기준 거리는 두 note의 인접도(adjacency)의 역수로 정의된다. 인접도 $w(n_i, n_j)$는 곡 안에서 note $n_i$와 $n_j$가 시간적으로 연달아 등장한 횟수이다:

$$
w(n_i, n_j) = \#\!\left\{\,t : n_i\ \mathrm{at\ time}\ t\ \mathrm{and}\ n_j\ \mathrm{at\ time}\ t+1\,\right\}
$$

거리는 $d_{\text{freq}}(n_i, n_j) = 1 / w(n_i, n_j)$로 정의되며 (인접도가 0인 경우는 도달 불가능한 큰 값으로 처리), 자주 연달아 등장하는 음일수록 가까워진다. 이는 곡의 통계적 흐름만 반영하며 화성 관계는 직접 포착하지 못한다는 한계가 있다.

**그 외의 음악적 거리 함수.**

**(1) Voice-leading distance** (Tymoczko, 2008): 두 pitch 사이의 절대 차이로 정의된다.

$$
d_V(p_1, p_2) = |p_1 - p_2|
$$

이 정의가 "두 음의 반음 차이"가 되는 이유는 12음 평균율에서 인접한 두 음(예: C와 C♯, 또는 E와 F)의 pitch 정수 표현이 정확히 1만큼 차이나며, 그 음정 차이가 1 반음(semitone)이기 때문이다. 즉, $|p_1 - p_2|$는 두 음 사이를 이동하기 위해 거쳐야 하는 반음의 개수와 같다. 음악 이론에서 voice-leading은 한 화음에서 다른 화음으로 옮겨갈 때 각 성부가 가능한 한 적은 음정으로 이동하는 것을 미덕으로 삼으며, 이 거리는 그러한 "최소 이동" 원리를 직접 수치화한 것이다.

**(2) DFT distance** (Tymoczko, 2008): pitch class 집합을 12차원 indicator vector로 표현한 후 이산 푸리에 변환(Discrete Fourier Transform)을 적용하여 푸리에 공간(Fourier space)으로 옮긴 뒤, 그 공간에서의 $L_2$ 거리를 측정한다.

$$
d_F(p_1, p_2) = \left\| \hat{f}(p_1) - \hat{f}(p_2) \right\|_2
$$

여기서 $\hat{f}(p) \in \mathbb{C}^{12}$는 pitch class $p$의 indicator vector $e_p \in \mathbb{R}^{12}$ ($e_p$는 $p$번째 성분만 1이고 나머지가 0)에 12점 DFT를 적용한 결과이며, 그 $k$번째 성분 $\hat{f}_k$를 $k$번째 **푸리에 계수**라 부른다.

**왜 DFT를 사용하는가.** 12음 평균율은 한 옥타브를 12등분한 주기 구조를 가지므로, pitch class 집합은 본질적으로 $\mathbb{Z}/12$ 위의 함수로 볼 수 있다. 이러한 주기 함수는 시간 영역에서 비교하기 어렵지만(인접 비교만으로는 화성적 의미를 포착하기 힘들다), 푸리에 공간으로 옮기면 각 계수가 특정 음악적 속성에 직접 대응된다. 예를 들어 $|\hat{f}_3|$은 옥타브를 4등분하는 단3도 대칭성(증3화음 등), $|\hat{f}_5|$는 옥타브를 5도권으로 도는 온음계성(diatonicity)과 연관된다 (Tymoczko, 2008). 따라서 푸리에 공간의 $L_2$ 거리는 두 음의 화성적 성격이 얼마나 닮았는지를 측정한다.

**복합 거리(Hybrid distance).** 본 연구는 빈도 기반 거리 $d_{\text{freq}}$와 음악적 거리 $d_{\text{music}}$ (Tonnetz, Voice-leading, DFT 중 하나)을 선형 결합한다:

$$
d_{\text{hybrid}}(n_i, n_j) = \alpha \cdot d_{\text{freq}}(n_i, n_j) + (1 - \alpha) \cdot d_{\text{music}}(n_i, n_j)
$$

여기서 $\alpha \in [0, 1]$은 두 거리의 비중을 조절하는 파라미터이다. Grid search 결과, hibari에 대해서는 $\alpha = 0.3$ (음악적 거리 70% + 빈도 거리 30%)이 최적임을 확인하였다 (구체적 수치는 추후 작성될 실험 결과 절에 정리).

**본 연구에서의 사용:** 거리 함수의 선택은 발견되는 cycle 구조에 직접적으로 영향을 미친다. 빈도 기반 거리만 사용하면 곡의 통계적 특성만 반영되어 화성적·선율적 의미가 있는 구조를 포착하지 못한다. Tonnetz 거리를 도입함으로써 hibari의 C장조/A단조 화성 구조와 정합적인 cycle을 발견할 수 있었다.

---

### 2.5 활성화 행렬과 중첩행렬

본 연구에서는 곡의 시간축 위에서 cycle 구조가 어떻게 전개되는지를 두 단계의 행렬로 표현한다. 첫 단계는 **활성화 행렬(activation matrix)**, 두 번째 단계는 그것을 가공한 **중첩행렬(overlap matrix)**이다.

**정의 2.5 (활성화 행렬).** 음악의 시간축 길이를 $T$, 발견된 cycle의 수를 $C$라 하자. 활성화 행렬 $A \in \{0, 1\}^{T \times C}$는 raw 활성 정보를 담는다:

시점 $t$에서 cycle $c$를 구성하는 note 중 **적어도 하나가 원곡에서 연주되고 있으면** $A[t, c] = 1$, 아니면 $A[t, c] = 0$이다. 형식적으로:

$$
A[t, c] = \mathbb{1}\!\left[\,\exists\ n \in V(c)\ \mathrm{such\ that}\ n\ \mathrm{is\ played\ at\ time}\ t\,\right]
$$

여기서 $V(c)$는 cycle $c$의 vertex(=note) 집합이며, $\mathbb{1}[\cdot]$은 indicator function이다. 활성화 행렬은 산발적인 단일 시점 활성화까지 모두 포함하므로 노이즈가 많다.

**정의 2.6 (중첩행렬).** 중첩행렬 $O \in \{0, 1\}^{T \times C}$는 활성화 행렬에서 **연속적이고 충분히 긴 활성 구간만 남긴 것**이다.

$$
O[t, c] = \mathbb{1}\!\left[\,t \in R(c)\,\right], \qquad R(c) = \bigcup_{i} [s_i,\ s_i + L_i]
$$

여기서 $R(c)$는 cycle $c$의 "지속 활성 구간(sustained intervals)"의 합집합이며, 각 구간 $[s_i, s_i + L_i]$는 활성화 행렬 $A[\cdot, c]$에서 길이가 임계값 $\mathrm{scale}(c)$ 이상인 연속 1의 구간이다. 즉, 중첩행렬은 활성화 행렬을 시간 방향 morphological filtering한 결과이다.

**활성화 행렬과 중첩행렬의 차이.**
- $A[t, c]$: 시점 $t$에 cycle $c$의 note가 단 한 번이라도 울리면 1. **순간적 활성을 모두 잡음.**
- $O[t, c]$: cycle $c$의 활성이 일정 시간 이상 **지속되는 구간**에서만 1. 산발적 노이즈 제거됨.

본 연구에서 중첩행렬을 음악 생성의 seed로 사용하는 이유는, 잠시 스쳐가는 활성보다 일정 시간 유지되는 cycle만이 곡의 구조적 단위로 의미 있다고 보기 때문이다.

**구축 과정:**

1. **활성화 행렬 계산**: 위 정의 2.5에 따라 $A \in \{0,1\}^{T \times C}$를 구한다.

2. **연속 활성 구간 추출**: 각 cycle $c$에 대해 길이 $\ge \text{scale}(c)$인 연속 1 구간을 모두 찾는다.

3. **Scale 동적 조정**: cycle마다 ON 비율 $\rho(c) = |R(c)|/T$가 목표치 $\rho^* = 0.35$에 근접하도록 $\text{scale}(c)$를 조정한다 (구간이 너무 많으면 scale을 키우고, 너무 적으면 줄인다).

**목표 ON 비율 $\rho^* = 0.35$의 근거.** 이 값은 본 연구에서 새로 결정한 것이 아니라 선행연구(정재훈 외, 2024)에서 사용된 휴리스틱 값을 계승한 것이다. 직관적으로 한 cycle이 곡 전체의 약 1/3 정도 활성화되면 "그 cycle이 곡의 구조적 모티프로서 충분히 자주 등장하면서도, 모든 시점을 점유하지 않아 다른 cycle과 구분된다"는 균형을 만든다. 이 값의 최적성은 본 연구에서 정량적으로 검증하지 않았으며, 향후 다른 곡으로 확장할 때 재검토되어야 할 파라미터이다.

**연속값 확장.** 본 연구에서는 이진 중첩행렬 외에, cycle의 활성 정도를 [0,1] 사이의 실수값으로 표현하는 연속값 버전도 도입하였다:

$$
O_{\text{cont}}[t, c] = \frac{\sum_{n \in V(c)} w(n) \cdot \mathbb{1}\!\left[\,n\ \mathrm{is\ played\ at\ time}\ t\,\right]}{\sum_{n \in V(c)} w(n)}
$$

여기서 $V(c)$는 cycle $c$의 vertex 집합, $w(n) = 1 / N_{\text{cyc}}(n)$은 note $n$의 **희귀도 가중치**이며 $N_{\text{cyc}}(n)$은 note $n$이 등장하는 cycle의 개수이다. 적은 cycle에만 등장하는 희귀한 note가 활성화되면 더 큰 가중치를 받는다.

**음악적 의미:** 중첩행렬은 곡의 **위상적 뼈대(topological skeleton)**를 시각화한 것이다. 시간이 흐름에 따라 어떤 반복 구조가 켜지고 꺼지는지를 나타내며, 이것이 음악 생성의 seed 역할을 한다.

---

### 2.6 Kullback-Leibler Divergence와 Jensen-Shannon Divergence

**정의 2.7 (KL Divergence).** 두 이산 확률 분포 $P$와 $Q$에 대해, **Kullback-Leibler divergence**는 다음과 같이 정의된다:

$$
D_{\text{KL}}(P \,\|\, Q) = \sum_{i} P(i) \log \frac{P(i)}{Q(i)}
$$

직관적으로 $D_{\text{KL}}(P \,\|\, Q)$는 "참 분포가 $P$인데 우리가 $Q$로 잘못 알고 있을 때 발생하는 정보 손실(information loss)"의 평균으로 해석된다. 두 분포가 똑같으면 손실이 없으므로 $D_{\text{KL}} = 0$이고, 분포의 차이가 클수록 값이 커진다. 항상 $D_{\text{KL}}(P \,\|\, Q) \ge 0$이며, 등호는 $P = Q$일 때만 성립한다 (Gibbs' inequality).

**비대칭성:** $D_{\text{KL}}(P \,\|\, Q) \ne D_{\text{KL}}(Q \,\|\, P)$. 예를 들어, $P$에는 자주 나오는 사건이 $Q$에는 거의 없으면 $D_{\text{KL}}(P \,\|\, Q)$는 매우 크지만 그 반대는 작을 수 있다. 이 비대칭성 때문에 두 곡을 "공정하게" 비교하기 위해서는 대칭화된 지표가 필요하다.

**정의 2.8 (Jensen-Shannon Divergence).** KL을 대칭화한 지표로, **JS divergence**는 다음과 같이 정의된다:

$$
D_{\text{JS}}(P \,\|\, Q) = \frac{1}{2} D_{\text{KL}}(P \,\|\, M) + \frac{1}{2} D_{\text{KL}}(Q \,\|\, M)
$$

여기서 $M = \frac{1}{2}(P + Q)$는 두 분포의 평균이다.

**핵심 성질:**
- 대칭성: $D_{\text{JS}}(P \,\|\, Q) = D_{\text{JS}}(Q \,\|\, P)$
- 유계성: $0 \le D_{\text{JS}}(P \,\|\, Q) \le \log 2$ ($\log_2$ 사용 시 최대값 1)
- $D_{\text{JS}}$ 자체는 metric은 아니지만, $\sqrt{D_{\text{JS}}}$는 삼각 부등식까지 만족하는 metric이다 (Endres & Schindelin, 2003)

**본 연구에서의 사용:** 생성된 음악과 원곡의 유사도를 평가하는 주요 지표로 사용한다. 두 가지 분포를 비교한다.

**(1) Pitch 빈도 분포.** 곡에 등장하는 모든 note에 대해, 그 pitch 값의 출현 횟수를 세어 정규화한 확률 분포이다. 곡의 모든 note 집합을 $\mathcal{N} = \{(s_k, p_k, e_k)\}_{k=1}^{K}$ ($s_k$=시작, $p_k$=pitch, $e_k$=종료)라 하면:

$$
P_{\text{pitch}}(p) = \frac{|\{k : p_k = p\}|}{K}
$$

원곡과 생성곡 각각에서 이 분포를 계산하고 둘 사이의 JS divergence를 측정한다. 값이 0에 가까울수록 두 곡의 pitch 사용 비율이 일치한다.

**(2) Transition 빈도 분포.** 시간 순서대로 인접한 두 note 쌍 $(p_k, p_{k+1})$의 출현 횟수를 세어 정규화한 분포이다. note들을 시작 시점 $s_k$ 순으로 정렬하여 pitch 시퀀스 $(p_1, p_2, \ldots, p_K)$를 만들고:

$$
P_{\text{trans}}(a, b) = \frac{|\{k : p_k = a,\ p_{k+1} = b\}|}{K - 1}
$$

이는 $|P| \times |P|$ 크기의 transition matrix를 정규화한 것과 동일하다. 원곡과 생성곡의 transition 분포 간 JS divergence는 "어떤 음 다음에 어떤 음이 오는가"의 패턴이 얼마나 유사한지를 측정한다.

**두 지표의 차이.**
- $D_{\text{JS}}(P_{\text{pitch}}^{\text{orig}} \,\|\, P_{\text{pitch}}^{\text{gen}})$: 음의 사용 비율 (시간 순서 무시)
- $D_{\text{JS}}(P_{\text{trans}}^{\text{orig}} \,\|\, P_{\text{trans}}^{\text{gen}})$: 음의 진행 패턴 (시간 순서 반영)

본 연구의 최우수 조합(Tonnetz hybrid + FC, $\alpha = 0.3$)에서 pitch JS divergence는 $D_{\text{JS}} \approx 0.002$를 달성하였다. 이는 가능한 최댓값 $\log 2 \approx 0.693$ (자연로그 기준)의 약 $0.3\%$에 해당하는 값이다.

---

### 2.7 Greedy Forward Selection과 Submodularity

**정의 2.9.** 유한 집합 $V$에 대한 함수 $f : 2^V \to \mathbb{R}$이 **submodular**라 함은, 모든 $A \subseteq B \subseteq V$와 $x \in V \setminus B$에 대해 다음이 성립한다는 것이다:

$$
f(A \cup \{x\}) - f(A) \ge f(B \cup \{x\}) - f(B)
$$

이는 "한계 효용 체감(diminishing returns)" 성질로, 큰 집합에 원소를 추가할 때의 이득이 작은 집합에 같은 원소를 추가할 때의 이득보다 작거나 같다는 것을 의미한다.

**정리 (Nemhauser et al., 1978).** $f$가 submodular이고 monotone이며 $f(\emptyset) = 0$일 때, $|S| \le k$를 만족시키면서 $f(S)$를 최대화하는 문제에 대해 **greedy forward selection** 알고리즘은 $(1 - 1/e) \approx 0.632$ 근사 보장을 갖는다:

$$
f(S_{\text{greedy}}) \ge \left(1 - \frac{1}{e}\right) f(S^*)
$$

여기서 $S^*$는 최적해이다.

**Greedy forward selection 알고리즘:**

```
S ← ∅
while |S| < k:
    x* ← argmax_{x ∈ V\S}  f(S ∪ {x}) - f(S)
    S ← S ∪ {x*}
return S
```

**본 연구에서의 사용:** 발견된 모든 cycle 중에서 위상 구조 보존도가 가장 높은 부분집합을 선택하는 데 사용한다. 보존도 함수 $f$는 다음과 같이 정의된다:

$$
f(S) = w_J \cdot J(S) + w_C \cdot C(S) + w_B \cdot B(S)
$$

여기서:
- $J(S)$: Note Pool Jaccard similarity (가중치 $w_J = 0.5$)
- $C(S)$: Overlap pattern correlation (가중치 $w_C = 0.3$)
- $B(S)$: Betti curve similarity (가중치 $w_B = 0.2$)

**참고:** 본 연구의 보존도 함수는 엄밀히 submodular임이 증명되지는 않았으나, 실험적으로 greedy 방법이 90% 보존도를 작은 $k$로 달성하는 것을 확인하였다 (예: 46개 cycle 중 15개로 90% 보존).

---

### 2.8 Multi-label Binary Cross-Entropy Loss

**정의 2.10.** Multi-label classification 문제에서, 각 예측 단위마다 여러 클래스가 동시에 정답일 수 있다. 모델 출력 $\hat{y} \in \mathbb{R}^N$을 sigmoid 함수로 [0, 1] 범위로 변환한 후, 각 클래스마다 독립적인 binary cross-entropy를 계산한다:

$$
\sigma(z) = \frac{1}{1 + e^{-z}}
$$

$$
\mathcal{L}_{\text{BCE}}(y, \hat{y}) = -\frac{1}{N} \sum_{i=1}^{N} \left[ y_i \log \sigma(\hat{y}_i) + (1 - y_i) \log (1 - \sigma(\hat{y}_i)) \right]
$$

여기서 $y \in \{0, 1\}^N$은 정답 multi-hot vector이고, $\hat{y} \in \mathbb{R}^N$은 모델의 logit 출력이다.

**본 연구에서의 사용:** 각 시점 $t$에서 동시에 여러 note가 활성화될 수 있으므로, 단일 클래스 예측인 categorical cross-entropy 대신 multi-label BCE를 사용한다. 모델 입력은 중첩행렬의 한 행 $O[t, :] \in \mathbb{R}^C$이고, 출력은 23차원 multi-hot vector $y_t \in \{0, 1\}^{23}$이다 (해당 시점의 활성 note 표시).

**Adaptive threshold:** 학습된 모델이 음악을 생성할 때, sigmoid 출력 $\sigma(\hat{y})$가 일정 임계값 이상인 클래스를 활성으로 판정한다. 본 연구에서는 원곡의 ON 비율(약 15%)에 맞춰 threshold를 동적으로 결정한다:

$$
\theta_t = \text{quantile}\left( \sigma(\hat{Y}),\ 1 - 0.15 \right)
$$

이를 통해 LSTM처럼 sigmoid 출력이 전체적으로 낮은 모델에서도 적절한 수의 음표를 생성할 수 있다.

---

### 2.9 음악 네트워크 구축과 가중치 분리

**정의 2.11.** 음악 네트워크 $G = (V, E)$는 다음과 같이 정의된다:
- **Vertex set** $V$: 곡에 등장하는 모든 고유 (pitch, duration) 쌍. hibari의 경우 $|V| = 23$.
- **Edge set** $E$: 두 vertex가 곡에서 인접하여 등장한 경우 연결.
- **Weight function** $w : E \to \mathbb{R}_{\ge 0}$: 인접 등장 빈도.

**가중치 행렬의 분리 (본 연구의 핵심 설계):** 본 연구는 가중치를 다음과 같이 세 가지로 분리한다:

1. **Intra weight** $W_{\text{intra}}$: 같은 악기 내에서 연속한 두 화음 간 전이 빈도. 두 악기의 intra weight를 합산한다:
$$W_{\text{intra}} = W_{\text{intra}}^{(1)} + W_{\text{intra}}^{(2)}$$
이는 각 악기의 **선율적 흐름**을 포착한다.

2. **Inter weight** $W_{\text{inter}}^{(\ell)}$: 시차(lag) $\ell$을 두고 악기 1의 화음과 악기 2의 화음이 동시에 출현하는 빈도. $\ell \in \{1, 2, 3, 4\}$로 변화시키며 다양한 시간 스케일의 **악기 간 상호작용**을 탐색한다.

3. **Simul weight** $W_{\text{simul}}$: 같은 시점에서 두 악기가 동시에 발음하는 note 조합의 빈도. **순간적 화음 구조**를 포착한다.

**Timeflow weight (선율 중심 탐색):**
$$W_{\text{timeflow}}(r_t) = W_{\text{intra}} + r_t \cdot W_{\text{inter}}$$

$r_t \in [0, 1.5]$를 변화시키며 위상 구조의 출현·소멸을 추적한다.

**Complex weight (선율-화음 결합):**
$$W_{\text{complex}}(r_c) = W_{\text{timeflow,refined}} + r_c \cdot W_{\text{simul}}$$

$r_c \in [0, 0.5]$로 제한하여 "음악은 시간 예술이므로 화음보다 선율에 더 큰 비중을 둔다"는 음악적 해석을 반영한다.

**거리 행렬:** 가중치 $w(n_i, n_j) > 0$에 대해 거리는 역수로 정의된다:
$$
d(n_i, n_j) = \begin{cases} 1 / w(n_i, n_j) & \text{if } w > 0 \\ d_\infty & \text{otherwise} \end{cases}
$$

여기서 $d_\infty$는 "도달 불가능한 큰 값"으로, $d_\infty = 1 + 2 / (\min_{w > 0} w \cdot \text{step})$로 계산된다.

---

## 참고문헌

- Carlsson, G. (2009). "Topology and data". *Bulletin of the AMS*, 46(2), 255–308.
- Edelsbrunner, H., & Harer, J. (2010). *Computational Topology: An Introduction*. AMS.
- Catanzaro, M. J. (2016). "Generalized Tonnetze". arXiv:1612.03519.
- Tymoczko, D. (2012). "The Generalized Tonnetz". *Journal of Music Theory*, 56(1).
- Tymoczko, D. (2008). "Set-Class Similarity, Voice Leading, and the Fourier Transform". *Journal of Music Theory*, 52(2).
- Bauer, U. (2021). "Ripser: efficient computation of Vietoris–Rips persistence barcodes". *Journal of Applied and Computational Topology*, 5, 391–423.
- Nemhauser, G. L., Wolsey, L. A., & Fisher, M. L. (1978). "An analysis of approximations for maximizing submodular set functions". *Mathematical Programming*, 14(1), 265–294.
- Nielsen, F. (2019). "On the Jensen–Shannon symmetrization of distances". *Entropy*, 21(5), 485.
- Endres, D. M., & Schindelin, J. E. (2003). "A new metric for probability distributions". *IEEE Transactions on Information Theory*, 49(7), 1858–1860.
- Tran, M. L., Park, C., & Jung, J.-H. (2021). "Topological Data Analysis of Korean Music in Jeongganbo". arXiv:2103.06620.
- 이동진, Tran, M. L., 정재훈 (2024). "국악의 기하학적 구조와 인공지능 작곡".
