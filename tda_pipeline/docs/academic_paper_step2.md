## 2. 수학적 배경

본 절에서는 본 연구의 파이프라인을 이해하기 위해 필요한 수학적 도구들을 정의하고, 각 도구가 음악 구조 분석에서 어떻게 사용되는지를 서술한다. TDA의 기본 개념에 대한 상호작용적 입문 자료로는 POSTECH MINDS 그룹의 튜토리얼(https://github.com/postech-minds/postech-minds/blob/main/tutorials/%5BGTDA_TUTO%5D01-Introduction_to_TDA.ipynb)을 참고할 수 있다.

---

### 2.1 Vietoris-Rips Complex

**정의 2.1.** 거리 공간 $(X, d)$와 양의 실수 $\varepsilon > 0$이 주어졌을 때, **Vietoris-Rips complex** $\text{VR}_\varepsilon(X)$는 다음과 같이 정의되는 복합체(simplicial complex)이다:

$$
\text{VR}_\varepsilon(X) = \left\{ \sigma \subseteq X \,\middle|\, \forall x_i, x_j \in \sigma,\ d(x_i, x_j) \le \varepsilon \right\}
$$

즉, 점 집합 $X$의 부분집합 $\sigma$에 속한 **모든 점 쌍 사이의 거리가 $\varepsilon$ 이하**이면 $\sigma$를 심플렉스(simplex)로 포함시킨다.

**구성 요소:**
- 0-simplex (vertex): 각 점 $x_i \in X$. 단일 점은 거리 조건이 없으므로 어떤 $\varepsilon$에서도 포함된다.
- 1-simplex (edge): $d(x_i, x_j) \le \varepsilon$인 두 점의 쌍 $\{x_i, x_j\}$
- 2-simplex (triangle): 세 점이 서로 모두 $\varepsilon$ 이내인 부분집합
- $k$-simplex: $k+1$개의 점이 서로 모두 $\varepsilon$ 이내인 부분집합

**Filtration 구조와 포함관계(nested sequence).** $\varepsilon$ 값을 0부터 연속적으로 키우면, 점 집합 $X$ 자체는 변하지 않은 채 **새로운 심플렉스만 점차 추가된다**. $\varepsilon = 0$일 때 $\text{VR}_0(X)$는 각 점만을 0-simplex로 포함하는 이산적인 점 집합(discrete set)이다 — 아직 어떤 edge도 없으므로 이것은 $X$ 그 자체와 같다. $\varepsilon$이 커지면서 두 점 사이 거리가 $\varepsilon$ 임계를 처음 넘는 순간에 1-simplex(edge)가 추가되고, 세 점이 모두 $\varepsilon$ 이내가 되면 2-simplex(삼각형)가 추가된다. 즉 $\varepsilon_1 < \varepsilon_2$이면 $\text{VR}_{\varepsilon_1}(X)$의 모든 심플렉스가 $\text{VR}_{\varepsilon_2}(X)$에도 그대로 들어 있으며, 새 심플렉스가 추가될 뿐이다. 따라서 다음의 포함관계는 항상 성립한다:

$$
\text{VR}_0(X) \subseteq \text{VR}_{\varepsilon_1}(X) \subseteq \text{VR}_{\varepsilon_2}(X) \subseteq \cdots \subseteq \text{VR}_{\varepsilon_n}(X)
$$

여기서 $0 < \varepsilon_1 < \varepsilon_2 < \cdots$는 새로운 심플렉스가 추가되어 복합체의 **위상 구조**가 변하는 임계값들이다. 점이 추가되거나 사라지는 것이 아니라, 같은 점들 사이에 새로운 연결(edge, 삼각형 등)이 생기면서 cycle이나 void가 형성되거나 채워지는 변화이다.

표기 편의를 위해 $K_i := \text{VR}_{\varepsilon_i}(X)$로 두면:

$$
K_0 \subseteq K_1 \subseteq K_2 \subseteq \cdots \subseteq K_n
$$

이를 **filtration**이라 부르며, 변화가 일어나는 임계값 $\varepsilon_i$들이 곧 위상의 birth/death 시점이 된다.

**본 연구에서의 사용:** $X = \{n_1, n_2, \ldots, n_{23}\}$은 hibari에 등장하는 23개의 고유 note이며, $d(n_i, n_j)$는 두 note 간 거리이다. 

---

### 2.2 Simplicial Homology

**정의 2.2.** Simplex complex $K$에 대해 $n$차 호몰로지 군(homology group) $H_n(K)$는 $K$ 안에 존재하는 $n$차원 "구멍"의 대수적 표현이다. 직관적으로:

- $H_0(K)$: 연결 성분(connected components)의 수
- $H_1(K)$: 1차원 cycle의 수 (닫힌 고리 모양으로 둘러싸인 영역)
- $H_2(K)$: 2차원 빈 공간(void)의 수 (3차원 공동을 둘러싼 표면)

**$H_n(K)$는 "함수"가 아니라 "군(group)"이다.** 정확히 말하면 아벨 군(abelian group)이며, 계수(coefficient)를 체(field) $\mathbb{F}$ 위에서 취하면 벡터 공간이 된다. $\text{rank}(H_n(K))$는 이 벡터 공간의 **차원** — 즉 서로 독립적인 $n$차원 구멍의 개수 — 을 뜻한다.

**구멍을 만들기 위해 필요한 최소 점의 개수.**
- 1차원 cycle ($H_1$): 최소 **3개**의 점이 필요하다. 세 점을 잇는 edge 3개가 삼각형 모양의 폐곡선을 만들되, 그 내부를 채우는 2-simplex(면)가 없어야 cycle로 인식된다.
- 2차원 void ($H_2$): 최소 **4개**의 점이 필요하다. 4개의 점이 사면체의 경계면(4개의 삼각형)을 이루되, 내부를 채우는 3-simplex가 없어야 한다.
- 일반적으로 $n$차원 구멍: 최소 $n+2$개의 점이 필요하다. 이는 $n$차원 구멍의 경계를 이루는 최소 구조가 $(n+1)$-simplex의 boundary이고, $(n+1)$-simplex는 $n+2$개의 vertex를 갖기 때문이다.

**주의: Vietoris-Rips 거리는 유클리드 거리가 아니다.** 본 연구에서 "두 note의 거리"는 물리적 공간에서의 거리가 아니라, 음악적 관계(인접 빈도, Tonnetz 격자 위치 등)에서 정의된 추상적 거리이다. 따라서 삼각형 모양의 cycle이라고 해서 2차원 평면 위의 삼각형을 떠올릴 필요는 없다. 중요한 것은 edge의 연결 관계이지 기하학적 배치가 아니다. 예를 들어, note A, B, C 사이의 거리가 각각 $d(A,B) = 2$, $d(B,C) = 3$, $d(A,C) = 5$일 때, $\varepsilon = 3$에서 A-B와 B-C edge가 존재하고 A-C edge는 없으면, 경로 A→B→C는 존재하지만 A→C 직접 edge는 없다. 이런 "경로는 있지만 직접 연결은 없는" 상태가 1차원 cycle의 후보가 된다. $\varepsilon = 5$에서 A-C edge까지 추가되면 삼각형 내부가 채워져(2-simplex) cycle이 소멸한다.

**Betti number.** $\beta_n = \text{rank}(H_n(K))$는 $n$차원 위상 특징의 개수를 나타낸다. 예컨대 $\beta_1 = 3$이면 이 복합체 안에 서로 독립적인 1차원 cycle이 3개 있다는 뜻이다.

**Boundary 연산자와 호몰로지 — 선형대수적 계산 예시.** $H_n$이 어떻게 계산되는지를 간단한 예시로 보인다. 점 4개 $\{a, b, c, d\}$와 edge $\{ab, bc, cd, da, ac\}$, 삼각형 $\{abc\}$로 이루어진 복합체 $K$를 생각하자.

boundary 연산자 $\partial_1$ (edge → vertex)과 $\partial_2$ (삼각형 → edge)를 $\mathbb{F}_2$ (mod 2) 위에서 행렬로 표현하면:

```
  ∂₁ (edge → vertex):         ∂₂ (triangle → edge):
       ab bc cd da ac               abc
  a [  1  0  0  1  1 ]         ab [  1 ]
  b [  1  1  0  0  1 ]         bc [  1 ]
  c [  0  1  1  0  0 ]         cd [  0 ]
  d [  0  0  1  1  0 ]         da [  0 ]
                                ac [  1 ]
```

$H_1(K) = \ker(\partial_1) / \text{im}(\partial_2)$이다. $\ker(\partial_1)$은 "닫힌 edge 체인들"의 공간이고, $\text{im}(\partial_2)$는 "삼각형의 경계인 edge 체인들"의 공간이다. 이 예시에서 $\ker(\partial_1)$의 차원은 2 (두 개의 독립적인 닫힌 고리: $ab+bc+ca$와 $ac+cd+da$), $\text{im}(\partial_2)$의 차원은 1 ($abc$의 경계 $= ab+bc+ca$). 따라서 $\beta_1 = 2 - 1 = 1$, 즉 독립적인 cycle이 1개이다. 직관적으로, 삼각형 $abc$가 한 cycle을 "채워서" 없앴고, 남은 사각형 $a-c-d-a$에 해당하는 cycle 1개가 살아남는다.

![Simplicial homology의 직관: cycle과 void](simplicial_homology.png)

**본 연구에서의 사용:** 본 연구는 주로 $H_1$ (1차 호몰로지)을 다룬다. 이는 음악 네트워크에서 서로 가까운 note들이 만드는 닫힌 cycle, 즉 순환적으로 연결된 note 그룹을 포착한다. 발견된 각 cycle은 곡의 구조적 반복 단위로 해석된다.

---

### 2.3 Persistent Homology

Filtration $K_0 \subseteq K_1 \subseteq \cdots \subseteq K_n$에서, 각 단계마다 $H_1$의 cycle 구성이 달라진다. **Persistent homology**는 이 과정에서 각 cycle이 어느 $\varepsilon_i$에서 처음 나타나고(**birth**) 어느 $\varepsilon_j$에서 사라지는지(**death**)를 추적한다.

**Birth와 death의 음악적 의미:**
- **Birth** $b$: 거리 임계값 $\varepsilon$가 충분히 커져서 새로운 cycle이 형성되는 순간. 음악적으로는 "이 거리 척도에서 처음으로 닫힌 반복 구조가 발견되는 시점".
- **Death** $d$: 더 큰 $\varepsilon$에서 그 cycle이 다른 cycle들의 합(정확히는 boundary)으로 표현될 수 있게 되어, 호몰로지 군 안에서 더 이상 독립적인 generator가 아니게 되는 순간. 음악적으로는 "거리 척도가 너무 느슨해져서 이 반복 구조가 다른 구조에 흡수되는 시점".

각 cycle은 $(b, d)$ 쌍과, 그 cycle을 구성하는 vertex/edge 집합인 **cycle representative**가 함께 기록된다. 본 연구에서는 birth-death 쌍은 cycle의 "수명"을 측정하는 데, cycle representative는 어떤 note들이 그 cycle을 이루는지 식별하는 데 사용한다. 이 정보를 모은 것이 곡의 **위상적 지문(topological signature)**이다.

**Persistence:** $\text{pers}(\text{cycle}) = d - b$. (death가 birth보다 항상 크므로 양수.) 큰 persistence를 갖는 cycle은 다양한 거리 척도에서 살아남으므로 **위상적으로 안정한 구조**이며, 작은 persistence는 일시적이거나 노이즈에 가까운 구조이다.

**알고리즘적 측면:** 본 연구의 대부분의 실험에서는 선행연구(정재훈 외, 2024)의 **pHcol algorithm** 순수 Python 구현을 사용하였다. 이 구현은 cycle representative까지 함께 추출해주므로 본 연구의 후속 단계(중첩행렬 구축)에 그대로 활용할 수 있다. 별도로 계산 속도가 중요한 일부 단계에서는 C++ 기반 **Ripser** (Bauer, 2021) 구현을 보조적으로 활용하였으며, 두 구현이 동일한 birth-death 결과를 내는지 검증하였다.

**본 연구에서의 사용:** 거리 행렬 $D \in \mathbb{R}^{23 \times 23}$로부터 Vietoris-Rips filtration을 구성하고, 각 rate parameter $r$ (가중치 비율, 후술)에서의 $H_1$ persistence를 계산한다. 발견된 모든 $(b, d)$ 쌍과 cycle representative가 함께 cycle 집합을 정의하며, 이 cycle들이 다음 절의 중첩행렬 구축에 사용된다.

---

### 2.4 Tonnetz와 음악적 거리 함수

**정의 2.4.** Tonnetz(또는 tone-network)는 pitch class 집합 $\mathbb{Z}/12\mathbb{Z}$를 평면 격자에 배치한 구조이다. 여기서 **pitch class**는 옥타브 차이를 무시한 음의 동치류(equivalence class)로, 예컨대 C4 (가운데 도), C5 (한 옥타브 위 도), C3 등은 모두 같은 pitch class "C"에 속한다. 12음 평균율(12-TET)에서는 한 옥타브 안에 12개의 pitch class가 있으며, 이를 정수 $\{0, 1, 2, \ldots, 11\}$에 대응시켜 $\mathbb{Z}/12\mathbb{Z}$로 표기한다 (0=C, 1=C♯, 2=D, ..., 11=B). 두 pitch class가 격자 위에서 가까운 것은 음악 이론적으로 어울리는 음(consonant)임을 의미한다.

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

본 연구에서는 12개 pitch class 모두에 대해 사전 계산된 $12 \times 12$ 거리 테이블을 사용한다. 이 테이블에서 **최솟값은 $0$** (같은 pitch class), **최댓값은 $4$** (예: F와 B, 또는 C와 F♯처럼 Tonnetz 격자에서 가장 먼 쌍)이다.

**빈도 기반 거리.** 본 연구의 기준 거리 $d_{\text{freq}}$는 두 note의 인접도(adjacency)의 역수로 정의된다. 인접도 $w(n_i, n_j)$는 곡 안에서 note $n_i$와 $n_j$가 시간적으로 연달아 등장한 횟수이다:

$$
w(n_i, n_j) = \#\!\left\{\,t : n_i\ \mathrm{at\ time}\ t\ \mathrm{and}\ n_j\ \mathrm{at\ time}\ t+1\,\right\}
$$

거리는 $d_{\text{freq}}(n_i, n_j) = 1 / w(n_i, n_j)$로 정의되며 (인접도가 0인 경우는 도달 불가능한 큰 값으로 처리), 자주 연달아 등장하는 음일수록 가까워진다. 이는 곡의 통계적 흐름만 반영하며 화성 관계는 직접 포착하지 못한다는 한계가 있다.

**그 외의 음악적 거리 함수.**

**(1) Voice-leading distance** (Tymoczko, 2008): 두 pitch class 사이를 이동하기 위해 거쳐야 하는 반음의 개수와 같다.

$$
d_V(p_1, p_2) = |p_1 - p_2|
$$

이 정의가 "두 pitch class의 반음 차이"가 되는 이유는 12음 평균율에서 인접한 두 pitch class(예: C와 C♯, 또는 E와 F)의 정수 표현이 정확히 1만큼 차이나며, 그 음정 차이가 1 반음(semitone)이기 때문이다. 음악 이론에서 voice-leading은 한 화음에서 다른 화음으로 옮겨갈 때 각 성부가 가능한 한 적은 음정으로 이동하는 것을 미덕으로 삼으며, 이 거리는 그러한 "최소 이동" 원리를 직접 수치화한 것이다.

**(2) DFT distance** (Tymoczko, 2008): 각 pitch class를 12차원 벡터로 표현한 뒤, 이산 푸리에 변환(DFT)으로 다른 공간으로 옮겨서 비교한다.

**pitch class를 "함수"로 보는 이유.** 12음 평균율에서 한 옥타브는 12개의 동일 간격 칸으로 나뉜다. pitch class $p$를 "12칸짜리 원형 자(ruler) 위에서 $p$번째 칸이 켜져 있고 나머지는 꺼져 있는 상태"로 생각하면, 이것은 $\{0, 1, \ldots, 11\} \to \{0, 1\}$인 함수이다. 이 함수를 **indicator vector** $e_p \in \mathbb{R}^{12}$ ($p$번째 성분만 1, 나머지 0)로 표현한다.

**$L_2$ 거리란.** 두 벡터 $u, v \in \mathbb{R}^n$ 사이의 $L_2$ 거리(유클리드 거리)는 성분별 차이의 제곱합에 루트를 씌운 것으로, 일상적인 "두 점 사이의 직선 거리"와 같다:

$$
\|u - v\|_2 = \sqrt{\sum_{i=1}^{n} (u_i - v_i)^2}
$$

**푸리에 공간(Fourier space)이란.** 원래 공간에서 indicator vector를 비교하면 "이 음과 저 음이 같은지 다른지"만 알 수 있다. DFT는 이 벡터를 **주기성 성분별로 분해**하여 새로운 좌표계 — 이것을 푸리에 공간이라 부른다 — 로 옮긴다. 각 좌표축(=**푸리에 계수** $\hat{f}_k$)은 특정 주기의 패턴에 대한 반응 강도를 나타낸다. 예를 들어 $k=3$번 계수는 "옥타브를 4등분하는 단3도 간격에 대한 반응" (증3화음과 관련), $k=5$번 계수는 "5도권을 따른 반응" (온음계적 구조와 관련)이다.

$$
d_F(p_1, p_2) = \left\| \hat{f}(p_1) - \hat{f}(p_2) \right\|_2
$$

여기서 $\hat{f}(p) \in \mathbb{C}^{12}$는 indicator vector $e_p$에 12점 DFT를 적용한 결과이다. 따라서 DFT 거리는 "두 pitch class가 화성적 성격(온음계성, 증3화음 대칭성 등)에서 얼마나 다른가"를 측정한다.

**복합 거리(Hybrid distance).** 본 연구는 빈도 기반 거리 $d_{\text{freq}}$와 음악적 거리 $d_{\text{music}}$ (Tonnetz, Voice-leading, DFT 중 하나)을 선형 결합한다:

$$
d_{\text{hybrid}}(n_i, n_j) = \alpha \cdot d_{\text{freq}}(n_i, n_j) + (1 - \alpha) \cdot d_{\text{music}}(n_i, n_j)
$$

여기서 $\alpha \in [0, 1]$은 두 거리의 비중을 조절하는 파라미터이다. 본 연구의 기본 실험에서는 $\alpha = 0.5$ (빈도 거리와 음악적 거리를 동등하게 결합)로 고정하였다. 과거 단일 run 탐색에서 $\alpha = 0.3$이 약간 더 좋다는 힌트가 있었으나, 통계적 반복 실험은 §7.8에서 향후 과제로 남아 있다.

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

여기서 $R(c)$는 cycle $c$의 "지속 활성 구간(sustained intervals)"의 합집합이며, 각 구간 $[s_i, s_i + L_i]$는 활성화 행렬 $A[\cdot, c]$에서 길이가 임계값 $\mathrm{scale}_c$ 이상인 연속 1의 구간이다.

**활성화 행렬과 중첩행렬의 차이.**
- $A[t, c]$: 시점 $t$에 cycle $c$의 note가 단 한 번이라도 울리면 1. **순간적 활성을 모두 잡음.**
- $O[t, c]$: cycle $c$의 활성이 일정 시간 이상 **지속되는 구간**에서만 1. 산발적 노이즈 제거됨.

예를 들어 $\mathrm{scale}_c = 3$일 때 (3 시점 이상 지속된 활성만 인정), 다음과 같은 cycle $c$의 한 행을 생각해보자.

```
시점:  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
A[·,c]: 0  1  1  0  1  1  1  1  0  0  1  0  1  1  1
O[·,c]: 0  0  0  0  1  1  1  1  0  0  0  0  1  1  1
```

활성화 행렬 $A$는 시점 2~3, 5~8, 11, 13~15에서 모두 활성화되어 있다. 중첩행렬 $O$는 그중 길이가 $\mathrm{scale}_c = 3$ 이상인 두 구간(시점 5~8과 13~15)만 1로 남기고, 길이가 짧은 시점 2~3과 단발성 시점 11은 0으로 처리한다. 본 연구에서 중첩행렬을 음악 생성의 seed로 사용하는 이유는, 잠시 스쳐가는 활성보다 일정 시간 유지되는 cycle만이 곡의 구조적 단위로 의미 있다고 보기 때문이다.

**구축 과정**:

1. **활성화 행렬 계산**: 위 정의 2.5에 따라 $A \in \{0,1\}^{T \times C}$를 구한다.

2. **연속 활성 구간 추출**: 각 cycle $c$에 대해 길이가 $\mathrm{scale}_c$ 이상인 연속 1 구간을 모두 찾는다.

3. **Scale 동적 조정**: cycle마다 ON 비율 $\rho(c) = |R(c)|/T$가 목표치 $\rho^* = 0.35$에 근접하도록 $\mathrm{scale}_c$를 조정한다 (구간이 너무 많으면 scale을 키우고, 너무 적으면 줄인다).

__목표 ON 비율의 근거.__ $\rho^* = 0.35$는 본 연구에서 새로 결정한 것이 아니라 선행연구(정재훈 외, 2024)에서 사용된 휴리스틱 값을 계승한 것이다. 직관적으로 한 cycle이 곡 전체의 약 1/3 정도 활성화되면 "그 cycle이 곡의 구조적 모티프로서 충분히 자주 등장하면서도, 모든 시점을 점유하지 않아 다른 cycle과 구분된다"는 균형을 만든다. 이 값의 최적성은 본 연구에서 정량적으로 검증하지 않았으며, 향후 곡 또는 데이터에 따라 적응적으로 조정 가능한 파라미터로 일반화할 예정이다 (예: ON 비율 자체를 최적화 대상으로 설정).

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

**왜 $D_{\text{KL}} \ge 0$인가 — 예시.** $P = (0.5, 0.5)$, $Q = (0.9, 0.1)$인 이진 분포를 생각하자. $D_{\text{KL}}(P\|Q) = 0.5 \log(0.5/0.9) + 0.5 \log(0.5/0.1) = 0.5 \times (-0.588) + 0.5 \times 1.609 = 0.510 > 0$이다. 직관적으로, $P$가 균등한데 $Q$가 한쪽에 치우쳐 있으면, "$Q$로 $P$를 설명하려 할 때 정보 손실이 생긴다"는 뜻이다. $P = Q$일 때만 $\log(P/Q) = \log 1 = 0$이 되어 손실이 사라진다.

**비대칭성:** $D_{\text{KL}}(P \,\|\, Q) \ne D_{\text{KL}}(Q \,\|\, P)$. 예를 들어, $P$에는 자주 나오는 사건이 $Q$에는 거의 없으면 $D_{\text{KL}}(P \,\|\, Q)$는 매우 크지만 그 반대는 작을 수 있다. 이 비대칭성 때문에 두 곡을 "공정하게" 비교하기 위해서는 대칭화된 지표가 필요하다.

**정의 2.8 (Jensen-Shannon Divergence).** KL을 대칭화한 지표로, **JS divergence**는 다음과 같이 정의된다:

$$
D_{\text{JS}}(P \,\|\, Q) = \frac{1}{2} D_{\text{KL}}(P \,\|\, M) + \frac{1}{2} D_{\text{KL}}(Q \,\|\, M)
$$

여기서 $M = \frac{1}{2}(P + Q)$는 두 분포의 평균이다.

**핵심 성질:**
- 대칭성: $D_{\text{JS}}(P \,\|\, Q) = D_{\text{JS}}(Q \,\|\, P)$
- 유계성: $0 \le D_{\text{JS}}(P \,\|\, Q) \le \log 2$ ($\log_2$ 사용 시 최대값 1)

**본 연구에서의 사용:** 생성된 음악과 원곡의 유사도를 평가하는 주요 지표로 사용한다. 두 가지 분포를 비교한다.

**(1) Pitch 빈도 분포.** 곡에 등장하는 모든 note에 대해, 그 pitch 값의 출현 횟수를 세어 정규화한 확률 분포이다. 곡의 모든 note 집합을 $\mathcal{N} = \{(s_k, p_k, e_k)\}_{k=1}^{K}$ ($s_k$=시작, $p_k$=pitch, $e_k$=종료)라 하자. 여기서 $K = |\mathcal{N}|$은 곡 전체의 총 note 개수(중복 포함)이다. 즉 같은 pitch라도 곡 안에서 두 번 연주되면 두 번 세어진다. 이 때 pitch 빈도 분포는 다음과 같이 정의된다:

$$
P_{\text{pitch}}(p) = \frac{|\{k : p_k = p\}|}{K}
$$

원곡과 생성곡 각각에서 이 분포를 계산하고 둘 사이의 JS divergence를 측정한다. 값이 0에 가까울수록 두 곡의 pitch 사용 비율이 일치한다.

**(2) Transition 빈도 분포.** 시간 순서대로 인접한 두 note 쌍 $(p_k, p_{k+1})$의 출현 횟수를 세어 정규화한 분포이다. 순서를 고려하므로 $(a, b)$와 $(b, a)$는 다른 transition으로 센다. note들을 시작 시점 $s_k$ 순으로 정렬하여 pitch 시퀀스 $(p_1, p_2, \ldots, p_K)$를 만들고:

$$
P_{\text{trans}}(a, b) = \frac{|\{k : p_k = a,\ p_{k+1} = b\}|}{K - 1}
$$

이는 $|P| \times |P|$ 크기의 transition matrix를 정규화한 것과 동일하다. 원곡과 생성곡의 transition 분포 간 JS divergence는 "어떤 음 다음에 어떤 음이 오는가"의 패턴이 얼마나 유사한지를 측정한다.

**두 지표의 차이.** Pitch 분포는 "어떤 음들이 얼마나 자주 쓰였는가"라는 빈도 정보만 담는 반면, transition 분포는 "어떤 음 다음에 어떤 음이 오는가"라는 시간적 진행 정보까지 담는다. 두 지표는 다음과 같은 차이를 가진다.

- 음의 사용 비율 (시간 순서 무시):
$$
D_{\text{JS}}\!\left(P_{\text{pitch}}^{\text{orig}} \,\|\, P_{\text{pitch}}^{\text{gen}}\right)
$$

- 음의 진행 패턴 (시간 순서 반영):
$$
D_{\text{JS}}\!\left(P_{\text{trans}}^{\text{orig}} \,\|\, P_{\text{trans}}^{\text{gen}}\right)
$$

따라서 전자는 작더라도 후자는 클 수 있으며, 두 지표를 함께 사용함으로써 "음을 비슷하게 쓰는가"와 "비슷한 순서로 쓰는가"를 별도로 측정할 수 있다.

**최댓값이 $\log 2$인 이유.** JS divergence는 두 분포 $P, Q$의 평균 $M = (P+Q)/2$에 대해 $D_{\text{JS}}(P\|Q) = \frac{1}{2}D_{\text{KL}}(P\|M) + \frac{1}{2}D_{\text{KL}}(Q\|M)$로 정의된다. 두 분포가 서로 완전히 분리된 경우(즉, $P$의 support와 $Q$의 support가 겹치지 않는 경우), $P$의 영역에서는 $M = P/2$이므로 $\log(P/M) = \log 2$가 되고, 마찬가지로 $Q$의 영역에서도 $\log 2$가 된다. 따라서 $D_{\text{KL}}(P\|M) = D_{\text{KL}}(Q\|M) = \log 2$가 되어 $D_{\text{JS}} = \log 2 \approx 0.693$이 최댓값이 된다.

본 연구의 최우수 full-song 조합(Tonnetz hybrid + FC, continuous overlap, $\alpha = 0.5$)에서 pitch JS divergence는 $D_{\text{JS}} \approx 0.0006$을 달성하였다 (§3.4a). 이는 가능한 최댓값 $\log 2 \approx 0.693$의 약 $0.09\%$에 해당하는 값이다.

---

### 2.7 Greedy Forward Selection과 Submodularity

**정의 2.9.** 유한 집합 $V$에 대한 함수 $f : 2^V \to \mathbb{R}$이 **submodular**라 함은, 모든 $A \subseteq B \subseteq V$와 $x \in V \setminus B$에 대해 다음이 성립한다는 것이다:

$$
f(A \cup \{x\}) - f(A) \ge f(B \cup \{x\}) - f(B)
$$

이는 "한계 효용 체감(diminishing returns)" 성질로, 큰 집합 B에 원소를 추가할 때의 이득이 작은 집합 A에 같은 원소를 추가할 때의 이득보다 작거나 같다는 것을 의미한다.

**정리 (Nemhauser et al., 1978).** $f$가 submodular이고 단조 증가(monotone non-decreasing)이며 $f(\emptyset) = 0$일 때, $|S| \le k$를 만족시키면서 $f(S)$를 최대화하는 문제에 대해 **greedy forward selection** 알고리즘은 $(1 - 1/e) \approx 0.632$ 근사 보장을 갖는다:

$$
f(S_{\text{greedy}}) \ge \left(1 - \frac{1}{e}\right) f(S^*)
$$

여기서 $S^*$는 최적해이다.

**본 연구에서의 사용:** 발견된 전체 cycle 집합 $\mathcal{C}$에서, 원곡의 위상 구조를 가장 잘 보존하는 부분집합 $S \subseteq \mathcal{C}$를 선택하는 데 사용한다. 보존도 함수 $f(S)$는 세 가지 지표의 가중합으로 정의된다:

$$
f(S) = w_J \cdot J(S) + w_C \cdot C(S) + w_B \cdot B(S)
$$

여기서 각 지표는 다음과 같이 정의된다.

**(1) Note Pool Jaccard similarity** $J(S)$. 전체 cycle이 사용하는 모든 note의 집합을 $\mathcal{N}_{\text{full}}$, 부분집합 $S$가 사용하는 note 집합을 $\mathcal{N}_S$라 하자:

$$
\mathcal{N}_{\text{full}} = \bigcup_{c \in \mathcal{C}} V(c), \quad \mathcal{N}_S = \bigcup_{c \in S} V(c)
$$

$S \subseteq \mathcal{C}$이므로 $\mathcal{N}_S \subseteq \mathcal{N}_{\text{full}}$이 항상 성립한다. 따라서 Jaccard similarity는 단순한 커버리지 비율로 귀결된다:

$$
J(S) = \frac{|\mathcal{N}_S|}{|\mathcal{N}_{\text{full}}|}
$$

예를 들어 전체 cycle이 사용하는 고유 note가 23개이고, $S$에 속한 cycle들이 그중 20개를 커버하면 $J(S) = 20/23 \approx 0.87$이다.

**(2) Overlap pattern correlation** $C(S)$. 각 시점 $t$에서 전체 cycle의 활성 수 $a_t = \sum_{c \in \mathcal{C}} O[t, c]$와 $S$만의 활성 수 $a_t^S = \sum_{c \in S} O[t, c]$를 계산한 뒤, 두 시계열의 **Pearson 상관계수**로 정의한다:

$$
C(S) = \frac{\sum_t (a_t - \bar{a})(a_t^S - \bar{a}^S)}{\sqrt{\sum_t (a_t - \bar{a})^2 \sum_t (a_t^S - \bar{a}^S)^2}}
$$

여기서 $\bar{a}, \bar{a}^S$는 각각의 평균이다. Pearson 상관계수는 두 시계열의 선형적 동조(co-movement) 정도를 $[-1, 1]$ 범위로 측정하며, $1$에 가까울수록 두 시계열이 같은 방향으로 움직인다. 예: 원본에서 시점 5에 활성 cycle이 많으면 $S$에서도 시점 5에 많아야 $C(S)$가 높다.

**(3) Betti curve similarity** $B(S)$. 각 rate $r$에 대해 살아있는 cycle 수를 세는 함수 $\beta_1^{\mathcal{C}}(r)$, $\beta_1^S(r)$을 정의하고 두 곡선의 정규화된 $L^2$ 유사도로 계산한다:

$$
B(S) = 1 - \frac{\|\beta_1^{\mathcal{C}} - \beta_1^S\|_2}{\|\beta_1^{\mathcal{C}}\|_2 + \|\beta_1^S\|_2}
$$

여기서 $\beta_1^{\mathcal{C}}$와 $\beta_1^S$는 이산화된 rate 값 $r_1, r_2, \ldots, r_M$ 위에서 평가된 Betti number 시계열, 즉 $\beta_1^{\mathcal{C}} = (\beta_1^{\mathcal{C}}(r_1), \ldots, \beta_1^{\mathcal{C}}(r_M)) \in \mathbb{R}^M$으로 본다. $\|\beta_1^{\mathcal{C}}\|_2 = \sqrt{\sum_{j=1}^M (\beta_1^{\mathcal{C}}(r_j))^2}$는 이 벡터의 $L^2$ 노름이며, $\|\beta_1^S\|_2$도 동일하게 정의된다. 분모에 두 노름의 합을 두는 이유는 $B(S) \in [0, 1]$로 정규화하기 위함이다.

이는 "rate 변화에 따른 위상 구조의 전체 골격(총 cycle 수의 변화 곡선)이 얼마나 유사한가"를 측정한다. 개별 cycle의 정체(identity)는 비교하지 않고 총량만 비교하는 한계가 있으나, 전체 Betti 곡선의 형태가 보존되면 위상 구조의 거시적 복잡도가 보존된다고 볼 수 있다.

**가중치 설정 ($w_J = 0.5,\ w_C = 0.3,\ w_B = 0.2$).** 세 지표 중 Note Pool Jaccard에 가장 큰 비중을 둔 이유는 음악 생성의 직접적 입력이 cycle 구성 note들이기 때문이다(음 자체가 보존되지 않으면 위상 구조의 의미가 사라진다). Overlap pattern correlation은 시간적 음악 흐름을 반영하므로 두 번째로 큰 비중을 두었고, Betti curve similarity는 보다 거시적인 위상 통계량이므로 보조 지표로 두었다. 이 가중치는 실험적으로 결정된 heuristic이며, 후속 연구에서 정량적 grid search로 재조정될 여지가 있다.

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

**예시.** 정답 $y = (1, 0, 1, 0)$ (note 1, 3이 활성), sigmoid 출력 $(0.88, 0.27, 0.62, 0.05)$일 때: note 1의 기여 $= -\log(0.88) \approx 0.13$, note 2: $-\log(0.73) \approx 0.31$, note 3: $-\log(0.62) \approx 0.48$, note 4: $-\log(0.95) \approx 0.05$. 평균 $\mathcal{L} \approx 0.24$. 정답 note의 확률이 높고 비정답 note의 확률이 낮을수록 손실이 줄어든다.

**학습은 gradient descent로 수행한다.** 각 step에서 (1) 입력을 모델에 통과시켜 $\hat{y}$를 계산, (2) $\mathcal{L}_{\text{BCE}}$를 구함, (3) 손실에 대한 모델 파라미터의 기울기(gradient) $\nabla_\theta \mathcal{L}$를 역전파(backpropagation)로 계산, (4) $\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$로 파라미터 업데이트 ($\eta$는 학습률). 수천 번 반복하여 모델이 정답에 가까운 출력을 내도록 한다.

**본 연구에서의 사용:** 각 시점 $t$에서 동시에 여러 note가 활성화될 수 있으므로, 단일 클래스 예측인 categorical cross-entropy 대신 multi-label BCE를 사용한다. 모델 입력은 중첩행렬의 한 행 $O[t, :] \in \mathbb{R}^C$이고, 출력은 23차원 multi-hot vector $y_t \in \{0, 1\}^{23}$이다 (해당 시점의 활성 note 표시).

**Adaptive threshold (추론 단계의 후처리).** 학습 후 음악을 생성할 때, sigmoid 출력 중 어느 음을 활성으로 볼 것인지 결정해야 한다. 고정 임계값 0.5를 쓰면, LSTM/Transformer처럼 출력이 전체적으로 낮은 모델에서는 음표가 거의 생성되지 않는 문제가 발생한다.

이를 해결하기 위해, 본 연구에서는 원곡의 평균 ON 비율(약 15% — 한 시점당 23개 note 중 약 3~4개가 활성)에 맞춰 임계값을 **데이터 기반으로 동적 결정**한다. 즉 모델이 어떤 절대적 확률 수준을 출력하든, 상위 15%에 해당하는 점수를 가진 음들만 활성으로 채택한다:

$$
\theta = \mathrm{quantile}\!\left(\,\sigma(\hat{Y}),\ 1 - 0.15\,\right)
$$


---

### 2.9 음악 네트워크 구축과 가중치 분리

**정의 2.11.** 음악 네트워크 $G = (V, E)$는 다음과 같이 정의된다:
- **Vertex set** $V$: 곡에 등장하는 모든 고유 (pitch, duration) 쌍. hibari의 경우 $|V| = 23$.
- **Edge set** $E$: 두 vertex가 곡에서 인접하여 등장한 경우 연결.
- **Weight function** $w : E \to \mathbb{R}_{\ge 0}$: 인접 등장 빈도.

**가중치 행렬의 분리 — hibari의 악기 배치 구조에 근거.** 본 연구가 가중치를 intra / inter / simul 세 가지로 분리한 것은 hibari의 실제 구조에서 비롯된다. hibari에서 inst 1은 처음부터 끝까지 쉬지 않고 연주하는 반면, inst 2는 모듈마다 규칙적인 쉼을 두며 얹히는 방식으로 배치된다 (§5 Figure 7에서 시각적으로 확인). 즉 두 악기는 (1) 각각 독립적인 시간적 흐름을 갖고, (2) 서로 다른 시간 위상(phase)에서 상호작용한다. 본 연구는 이 구조를 수학적 가중치에 반영하여, intra weight는 "한 악기 내부의 시간 방향 흐름", inter weight는 "악기 1의 어떤 타건 다음 lag $\ell$만큼 후에 악기 2의 어떤 타건이 오는가", simul weight는 "같은 시점에서의 즉시적 화음 결합"을 각각 독립적으로 표현한다.

**rate parameter $r_t$의 의미.** $r_t$는 timeflow weight에서 intra와 inter의 비중을 조절한다.
- $r_t = 0$: $W = W_{\text{intra}}$만 사용. 각 악기의 선율적 흐름만 반영.
- $r_t = 1$: intra와 inter를 동등하게 결합. 선율과 상호작용을 균형 있게 반영.
- $r_t > 1$: inter의 비중이 intra보다 커짐. 악기 간 상호작용이 지배적인 구조를 탐색.

**가중치 행렬의 분리 (본 연구의 핵심 설계):** 본 연구는 가중치를 다음과 같이 세 가지로 분리한다:

1. **Intra weight** $W_{\text{intra}}$: 같은 악기 내에서 연속한 두 화음 간 전이 빈도. 두 악기의 intra weight를 합산한다:
$$W_{\text{intra}} = W_{\text{intra}}^{(1)} + W_{\text{intra}}^{(2)}$$
이는 각 악기의 **선율적 흐름**을 포착한다.

2. **Inter weight** $W_{\text{inter}}^{(\ell)}$: 시차(lag) $\ell$을 두고 악기 1의 화음과 악기 2의 화음이 동시에 출현하는 빈도이다. $\ell \in \{1, 2, 3, 4\}$로 변화시키며 다양한 시간 스케일의 **악기 간 상호작용**을 탐색한다. 가까운 시차에 더 큰 비중을 두는 **감쇄 가중치** $\lambda_\ell$을 사용하여 합산한다:
$$W_{\text{inter}} = \sum_{\ell = 1}^{4} \lambda_\ell \cdot W_{\text{inter}}^{(\ell)}, \qquad (\lambda_1, \lambda_2, \lambda_3, \lambda_4) = (0.60,\ 0.30,\ 0.08,\ 0.02), \quad \sum_\ell \lambda_\ell = 1$$
직관적으로 lag 1 (바로 다음 시점의 상호작용)에 $60\%$를 집중하고, lag가 늘어날수록 급격히 줄인다. 이는 "먼 시차의 우연한 동시 등장보다 가까운 시차의 인과적 상호작용이 음악적으로 의미 있다"는 가정을 반영한다.

3. **Simul weight** $W_{\text{simul}}$: 같은 시점에서 두 악기가 동시에 타건하는 note 조합의 빈도. **순간적 화음 구조**를 포착한다.

**Timeflow weight (선율 중심 탐색):**
$$W_{\text{timeflow}}(r_t) = W_{\text{intra}} + r_t \cdot W_{\text{inter}}$$

$r_t \in [0, 1.5]$를 변화시키며 위상 구조의 출현·소멸을 추적한다.

**Complex weight (선율-화음 결합):**
$$W_{\text{complex}}(r_c) = W_{\text{timeflow,refined}} + r_c \cdot W_{\text{simul}}$$

$r_c \in [0, 0.5]$로 제한하여 "음악은 시간 예술이므로 화음보다 선율에 더 큰 비중을 둔다"는 음악적 해석을 반영한다.

**거리 행렬:** 가중치 $w(n_i, n_j) > 0$에 대해 거리는 역수로 정의된다:
$$
d(n_i, n_j) = \begin{cases} 1\,/\,w(n_i, n_j) & \quad \mathrm{if}\ \ w(n_i, n_j) > 0 \\ d_\infty & \quad \mathrm{otherwise} \end{cases}
$$

여기서 $d_\infty$는 "도달 불가능한 큰 값"이다. 구체적으로 $d_\infty = 1 + 2 / (\min_{w > 0} w \cdot \text{step})$으로 계산되며, $\text{step} = 10^{\text{power}}$ ($\text{power} = -2$이므로 $\text{step} = 0.01$)은 persistent homology 계산 시 거리행렬의 이산화 단위이다. 이 값은 "가중치가 0인 note 쌍(=곡에서 한 번도 연달아 등장하지 않은 쌍)에게 매우 큰 거리를 부여하여, filtration의 후반부에서야 비로소 연결되게 한다"는 역할을 한다.

---

### 2.10 확장 수학적 도구 — 거리 보존 재분배와 화성 제약

본 절은 §7.3–§7.6 의 확장 실험에서 사용되는 수학적 도구를 정의한다.

**정의 2.10 (Tonnetz 최소매칭 거리).** 두 cycle $c_1, c_2$가 각각 $V(c_1) = \{n_1, \ldots, n_k\}$, $V(c_2) = \{m_1, \ldots, m_k\}$ (같은 크기 $k$) 를 가질 때, 두 cycle 간 **Tonnetz 최소매칭 거리**는 다음과 같이 정의된다:

$$
d_{\text{match}}(c_1, c_2) = \min_{\pi \in S_k} \frac{1}{k} \sum_{i=1}^{k} d_T(\text{pc}(n_i),\ \text{pc}(m_{\pi(i)}))
$$

여기서 $\pi$는 $\{1, \ldots, k\}$의 순열, $\text{pc}(\cdot)$는 MIDI pitch를 pitch class ($\mathrm{mod}\ 12$) 로 변환하는 함수, $d_T$는 Tonnetz 격자 거리 (§2.4) 이다. 이 최적 순열은 **Hungarian algorithm** (Kuhn, 1955)으로 $O(k^3)$에 정확히 계산된다. 두 cycle의 크기가 다를 때는 작은 쪽에 dummy vertex (거리 $= \infty$)를 추가하여 정방 비용행렬을 만든다.

**음악적 의미:** 이 거리는 "두 cycle을 구성하는 note들을 *최선의 1:1 대응*으로 짝지었을 때의 평균 Tonnetz 거리"를 측정한다. 예컨대 C major triad $\{C, E, G\}$와 F major triad $\{F, A, C\}$는 $d_{\text{match}} = (d_T(C,F) + d_T(E,A) + d_T(G,C))/3$ 으로 비교된다.

**정의 2.10b (Persistence Diagram과 Wasserstein Distance).** Persistent homology의 결과는 $(b_i, d_i)$ 쌍들의 집합인 **persistence diagram** $\mathrm{PD}$로 표현된다. 두 persistence diagram $\mathrm{PD}_1$, $\mathrm{PD}_2$ 간의 **$p$-Wasserstein distance** (여기서 $p = 2$)는 다음과 같이 정의된다:

$$
W_p(\mathrm{PD}_1, \mathrm{PD}_2) = \left(\inf_{\gamma} \sum_{x \in \mathrm{PD}_1} \|x - \gamma(x)\|_\infty^p \right)^{1/p}
$$

여기서 $\gamma : \mathrm{PD}_1 \to \mathrm{PD}_2 \cup \Delta$는 $\mathrm{PD}_1$의 각 점을 $\mathrm{PD}_2$의 점 또는 대각선 $\Delta = \{(a,a) : a \in \mathbb{R}\}$ (persistence = 0인 trivial point를 대표) 에 대응시키는 전단사 함수이며, $\|\cdot\|_\infty$는 $L^\infty$ 노름이다. 직관적으로, 두 PD의 점들을 최적 대응으로 짝지었을 때의 이동 비용의 합을 최소화한 값이다. 값이 작을수록 두 PD가 유사한 birth-death 구조를 가진다. 본 연구에서는 Python 라이브라리 `persim`의 `wasserstein` 함수를 사용하여 계산한다.

**정의 2.11 (Cycle-cycle 거리행렬의 Up to permutation 오차).** 원곡의 cycle 집합 $\{V_1, \ldots, V_K\}$와 새 note 집합으로 재구성된 cycle 집합 $\{V'_1, \ldots, V'_K\}$에 대해, 각각의 cycle-cycle Tonnetz 최소매칭 거리행렬을 $C, C' \in \mathbb{R}^{K \times K}$이라 하자 (정의 2.10). 두 행렬을 레이블 순열에 무관하게 비교한 **Frobenius 오차**는 다음과 같다:

$$
\text{err}_{\text{cycle}}(C, C') = \min_{\pi \in S_K} \left\| \tilde{C} - \tilde{C}'_\pi \right\|_F = \min_{\pi \in S_K} \sqrt{\sum_{i,j} \left(\tilde{C}[i,j] - \tilde{C}'[\pi(i), \pi(j)]\right)^2}
$$

여기서 $\tilde{C}$는 $C$를 $[0,1]$로 정규화한 행렬이다.

**"Up to permutation"의 필요성.** 새 note 집합을 랜덤하게 생성할 때, cycle에 배정되는 note 순서에 정해진 기준이 없다. 따라서 cycle 레이블 순열 $\pi$에 의한 재배열을 고려해야만, 두 cycle 집합 간 구조적으로 가장 유사한 대응을 찾을 수 있다.

**Note-note 거리 오차.** 반면 개별 note의 Tonnetz 거리행렬 $D, D' \in \mathbb{R}^{N \times N}$에 대한 오차는 순열 없이 pitch 오름차순으로 정렬한 뒤 직접 Frobenius 거리로 측정한다:

$$
\text{err}_{\text{note}}(D, D') = \left\| \tilde{D} - \tilde{D}' \right\|_F
$$

**$S_K$ 탐색 근사.** hibari의 cycle 수 $K = 46$의 경우 $46!$의 전수 탐색은 불가능하다. 본 연구에서는 $K \le 8$이면 전수 탐색, $K > 8$이면 각 행의 정렬된 거리 프로파일(sorted row profile)을 특성 벡터로 삼아 행 간 Hungarian 매칭으로 최적 순열을 근사한다. 이때 새 note 집합 후보 1,000개를 랜덤 샘플링하여 $\alpha \cdot \text{err}_{\text{note}} + (1-\alpha) \cdot \text{err}_{\text{cycle}}$ (기본 $\alpha = 0.5$)이 최소인 후보를 선택한다.

**정의 2.12 (Interval Class Vector, ICV).** pitch class 집합 $S \subseteq \mathbb{Z}/12\mathbb{Z}$의 **interval class vector** $\text{ICV}(S) \in \mathbb{Z}_{\ge 0}^{6}$는 다음과 같이 정의된다:

$$
\text{ICV}(S)[k] = \left|\left\{(p, q) \in S^2 : p < q,\ \min(|p-q|,\ 12-|p-q|) = k\right\}\right|, \quad k = 1, \ldots, 6
$$

여기서 $\min(|p-q|, 12-|p-q|)$는 두 pitch class 사이의 **interval class** — 옥타브 대칭을 고려한 최소 반음 거리 — 이다. 예를 들어 C major scale의 ICV는 $[2, 5, 4, 3, 6, 1]$이다.

**정의 2.13 (Consonance score).** **roughness**는 두 pitch class 사이의 음정(interval)이 청취자에게 얼마나 긴장감 있게(거칠게) 들리는지를 나타내는 지표이다. 음악이론에서 두 음이 어울리는 정도(consonance/dissonance)는 그 음정의 주파수 비율로 결정된다. 완전1도·완전8도처럼 비율이 단순할수록 잘 어울리고(roughness $= 0$), 장2도·단2도처럼 비율이 복잡할수록 거칠게 들린다(roughness $= 1$). 본 연구에서는 interval class $k \in \{1, \ldots, 6\}$에 따른 roughness 가중치를 다음 표와 같이 설정하였다:

| Interval class | 음정 이름 | roughness |
|---|---|---|
| 0 | 완전1도 / 완전8도 | $0.0$ |
| 1 | 단2도 / 장7도 | $1.0$ |
| 2 | 장2도 / 단7도 | $0.8$ |
| 3 | 단3도 / 장6도 | $0.3$ |
| 4 | 장3도 / 단6도 | $0.2$ |
| 5 | 완전4도 / 완전5도 | $0.1$ |
| 6 | 증4도 / 감5도 (tritone) | $0.7$ |

시점 $t$에서 동시에 타건되는 pitch class 집합 $S_t$의 **dissonance**는 모든 pitch class 쌍의 roughness 평균으로 정의된다:

$$
\text{diss}(S_t) = \frac{1}{\binom{|S_t|}{2}} \sum_{\{p,q\} \subset S_t} \text{roughness}(\min(|p-q|, 12-|p-q|))
$$

여기서 $\min(|p-q|, 12-|p-q|)$는 두 pitch class 간의 interval class이다. 쌍의 개수가 $\binom{|S_t|}{2} = |S_t|(|S_t|-1)/2$이므로 평균을 취한다. 곡 전체의 **평균 dissonance**는 다음과 같이 정의된다:

$$
\bar{d} \;=\; \frac{1}{T}\sum_{t=1}^{T} \text{diss}(S_t)
$$

**정의 2.14 (Markov chain 시간 재배치).** 원본 overlap matrix $O \in \{0,1\}^{T \times C}$의 행 시퀀스로부터 1차 Markov chain의 전이행렬을 추정한다. 시점 $t$에서의 상태 $s_t$는 $O[t, :] \in \{0,1\}^C$ (길이-$C$ 이진 벡터) 이며:

$$
P(s_{t+1} = j \mid s_t = i) = \frac{\#\{t : s_t = i,\ s_{t+1} = j\}}{\#\{t : s_t = i\}}
$$

이 전이확률을 사용하여 초기 상태 $s_0$부터 새로운 상태 시퀀스를 **재샘플링**한다. 온도 파라미터 $\tau > 0$로 전이확률을 조절한다: $P_\tau(j|i) \propto P(j|i)^{1/\tau}$. $\tau = 1$이면 원본과 동일한 전이 통계, $\tau > 1$이면 더 무작위적, $\tau < 1$이면 더 결정적이다.

---
