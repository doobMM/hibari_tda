# Topological Data Analysis를 활용한 음악 구조 분석 및 위상 구조 보존 기반 AI 작곡 파이프라인

**저자:** 김민주
**지도:** 정재훈 (KIAS 초학제 독립연구단)
**작성일:** 2026

---

## 2. 수학적 배경

본 절에서는 본 연구의 파이프라인을 이해하기 위해 필요한 수학적 도구들을 정의하고, 각 도구가 음악 구조 분석에서 어떻게 사용되는지를 서술한다.

---

### 2.1 Vietoris-Rips Complex

**정의 2.1.** 거리 공간 $(X, d)$와 양의 실수 $\varepsilon > 0$이 주어졌을 때, **Vietoris-Rips complex** $\text{VR}_\varepsilon(X)$는 다음과 같이 정의되는 추상 단체 복합체(abstract simplicial complex)이다:

$$
\text{VR}_\varepsilon(X) = \left\{ \sigma \subseteq X \,\middle|\, \forall x_i, x_j \in \sigma,\ d(x_i, x_j) \le \varepsilon \right\}
$$

즉, 부분집합 $\sigma$에 속한 모든 점 쌍 사이의 거리가 $\varepsilon$ 이하이면 $\sigma$를 단체(simplex)로 포함시킨다.

**구성 요소:**
- 0-단체(vertex): 각 점 $x_i \in X$
- 1-단체(edge): $d(x_i, x_j) \le \varepsilon$인 쌍 $\{x_i, x_j\}$
- 2-단체(triangle): 세 점이 모두 $\varepsilon$ 이내인 삼각형
- $k$-단체: $k+1$개의 점이 모두 $\varepsilon$ 이내인 부분집합

**Filtration 구조:** $\varepsilon_1 < \varepsilon_2$이면 $\text{VR}_{\varepsilon_1}(X) \subseteq \text{VR}_{\varepsilon_2}(X)$이므로, $\varepsilon$를 0부터 점진적으로 키우면 단체 복합체의 nested sequence가 만들어진다:

$$
\emptyset = K_0 \subseteq K_1 \subseteq K_2 \subseteq \cdots \subseteq K_n = \text{VR}_\infty(X)
$$

이를 **filtration**이라 부른다.

**본 연구에서의 사용:** $X = \{n_1, n_2, \ldots, n_{23}\}$은 hibari에 등장하는 23개의 고유 note이며, $d(n_i, n_j)$는 두 note 간 거리이다. $\varepsilon$를 점진적으로 증가시키며 단체 복합체의 변화를 추적하여, 어떤 거리 척도에서 어떤 위상 구조가 출현·소멸하는지를 분석한다.

---

### 2.2 Simplicial Homology

**정의 2.2.** 단체 복합체 $K$에 대해, 차원 $n$의 **chain group** $C_n(K)$는 $K$의 모든 $n$-단체들이 생성하는 자유 abelian group이다 (계수는 $\mathbb{Z}$ 또는 $\mathbb{Z}/2$):

$$
C_n(K) = \mathbb{Z}\langle \sigma_1^{(n)}, \sigma_2^{(n)}, \ldots \rangle
$$

**경계 연산자(boundary operator)** $\partial_n : C_n(K) \to C_{n-1}(K)$는 $n$-단체 $\sigma = [v_0, v_1, \ldots, v_n]$에 대해 다음과 같이 정의된다:

$$
\partial_n \sigma = \sum_{i=0}^{n} (-1)^i [v_0, \ldots, \hat{v_i}, \ldots, v_n]
$$

여기서 $\hat{v_i}$는 해당 꼭짓점을 제외함을 의미한다. 핵심 성질은 $\partial_{n-1} \circ \partial_n = 0$이다.

**$n$차 호몰로지 군(homology group):**

$$
H_n(K) = \frac{\ker \partial_n}{\text{im } \partial_{n+1}} = \frac{Z_n(K)}{B_n(K)}
$$

여기서 $Z_n = \ker \partial_n$은 **cycle**의 집합, $B_n = \text{im } \partial_{n+1}$은 **boundary**의 집합이다. 직관적으로:

- $H_0(K)$: 연결 성분(connected components)의 개수
- $H_1(K)$: 1차원 구멍(loop, cycle)의 개수
- $H_2(K)$: 2차원 빈 공간(void)의 개수

**Betti number** $\beta_n = \text{rank}(H_n(K))$는 $n$차원 위상 특징의 개수를 나타낸다.

**본 연구에서의 사용:** 본 연구는 주로 $H_1$(1차 호몰로지)을 다룬다. 이는 음악 네트워크에서 **순환적으로 연결된 note 그룹**, 즉 서로 가까운 note들이 만드는 닫힌 고리(cycle)를 포착한다.

---

### 2.3 Persistent Homology

**정의 2.3.** Filtration $K_0 \subseteq K_1 \subseteq \cdots \subseteq K_n$에 대해, 각 단계의 호몰로지 군들은 포함 함수에 의해 induced된 사상을 통해 연결된다:

$$
H_p(K_0) \to H_p(K_1) \to H_p(K_2) \to \cdots \to H_p(K_n)
$$

**Persistent homology**는 이 sequence에서 각 위상 특징이 **언제 태어나고(birth) 언제 죽는지(death)**를 추적하는 이론이다.

구체적으로, 어떤 호몰로지 클래스 $[\alpha] \in H_p(K_i)$가 처음 등장하면 그 단계 $i$가 **birth time**이고, 더 큰 단계 $j$에서 다른 클래스에 흡수되거나 boundary가 되어 사라지면 $j$가 **death time**이다. 각 특징은 $(\text{birth}, \text{death})$ 쌍으로 표현되며, 이를 모은 것을 **persistence diagram** 또는 **barcode**라 한다.

**Persistence:** $\text{pers}(\alpha) = \text{death}(\alpha) - \text{birth}(\alpha)$. 큰 persistence를 갖는 특징은 다양한 스케일에서 살아남으므로 **위상적으로 안정한 구조**로 간주된다.

**알고리즘적 측면:** Persistent homology는 boundary matrix $D$를 구성하고 column reduction을 수행하여 계산한다. 본 연구에서는 두 가지 구현을 사용하였다:

1. **pHcol algorithm** (정재훈 외, 2024): 순수 Python 구현
2. **Ripser** (Bauer, 2021): C++ 기반 최적화 구현, 약 45배 빠름

**본 연구에서의 사용:** 거리 행렬 $D \in \mathbb{R}^{23 \times 23}$로부터 Vietoris-Rips filtration을 구성하고, 각 rate parameter $r$ (가중치 비율, 후술)에서의 H₁ persistence를 계산한다. 발견된 모든 (birth, death) 쌍을 모아 곡의 **위상적 지문(topological signature)**으로 사용한다.

---

### 2.4 Barcode Diagram

**정의 2.4.** Persistent homology의 결과를 시각화하는 두 가지 동등한 표현이 있다:

1. **Persistence diagram**: 평면 $\mathbb{R}^2$ 위의 점들로 표현. 각 점 $(b_i, d_i)$는 한 특징의 birth-death 쌍이다. $d_i > b_i$이므로 모든 점은 대각선 위에 위치한다.

2. **Barcode**: 각 특징을 구간 $[b_i, d_i]$로 표현한 수평 막대들의 집합. 막대 길이가 길수록 위상적으로 안정한 특징이다.

**음악적 해석:** 본 연구에서 hibari의 H₁ barcode는 곡 안에서 발견되는 반복 구조의 "수명"을 나타낸다. 짧은 막대는 특정 거리 임계값 근처에서만 일시적으로 나타나는 패턴이고, 긴 막대는 광범위한 임계값에서 일관되게 존재하는 핵심 구조이다.

**본 연구에서의 사용:** 각 cycle의 (birth, death)를 추출하여, **중첩행렬(overlap matrix)** 구축의 기본 자료로 사용한다 (2.6절).

---

### 2.5 Tonnetz와 음악적 거리 함수

**정의 2.5.** **Tonnetz** (또는 tone-network)는 12음 평균율(12-TET)의 pitch class 집합 $\mathbb{Z}/12\mathbb{Z}$를 평면 격자에 배치한 구조이다. 두 pitch class가 가까운 것은 음악 이론적으로 어울리는 음(consonant)임을 의미한다.

**Tonnetz의 격자 구조:** 한 가지 표준 정의에서, pitch class $p \in \mathbb{Z}/12$를 좌표 $(x, y)$에 배치하되 다음 관계를 만족시킨다:
- 가로 이동 (+1 in $x$): 완전5도 (perfect fifth, +7 semitones)
- 세로 이동 (+1 in $y$): 장3도 (major third, +4 semitones)

이 격자에서 두 pitch class $p_1, p_2$ 사이의 **Tonnetz 거리** $d_T(p_1, p_2)$는 격자 위 최단 경로 길이로 정의된다:

$$
d_T(p_1, p_2) = \min \left\{ |x_1 - x_2| + |y_1 - y_2| \,\middle|\, (x_i, y_i) \text{ represents } p_i \right\}
$$

본 연구에서는 BFS(너비 우선 탐색)로 이 거리를 계산한다. 12개 pitch class 모두에 대해 사전 계산된 $12 \times 12$ 거리 테이블을 사용한다.

**기타 음악적 거리 함수:**

1. **Voice-leading distance** (Tymoczko, 2008):
$$d_V(p_1, p_2) = |p_1 - p_2|$$
즉, 두 음의 반음 차이. 피아노 건반에서 가까운 음일수록 거리가 짧다.

2. **DFT distance** (Tymoczko, 2008):
$$d_F(p_1, p_2) = \left\| \hat{f}(p_1) - \hat{f}(p_2) \right\|_2$$
여기서 $\hat{f}(p)$는 pitch class indicator vector를 12차원 DFT 변환한 결과이다. 각 Fourier 계수는 음악적 속성(반음계성, 온음계성 등)에 대응된다.

**복합 거리(Hybrid distance):** 본 연구는 빈도 기반 거리 $d_{\text{freq}}$와 음악적 거리 $d_{\text{music}}$를 선형 결합한다:

$$
d_{\text{hybrid}}(n_i, n_j) = \alpha \cdot d_{\text{freq}}(n_i, n_j) + (1 - \alpha) \cdot d_{\text{music}}(n_i, n_j)
$$

여기서 $\alpha \in [0, 1]$은 두 거리의 비중을 조절하는 파라미터이다. Grid search 결과, hibari에 대해서는 $\alpha = 0.3$ (Tonnetz 거리 70% + 빈도 거리 30%)이 최적임을 확인하였다 (실험 결과 표 X 참조).

**본 연구에서의 사용:** 거리 함수의 선택은 발견되는 cycle 구조에 직접적으로 영향을 미친다. 빈도 기반 거리만 사용하면 곡의 통계적 특성만 반영되어 화성적·선율적 의미가 있는 구조를 포착하지 못한다. Tonnetz 거리를 도입함으로써 hibari의 C장조/A단조 화성 구조와 정합적인 cycle을 발견할 수 있었다.

---

### 2.6 중첩행렬(Overlap Matrix)

**정의 2.6.** 음악의 시간축 길이를 $T$, 발견된 cycle의 수를 $C$라 하자. **중첩행렬** $O \in \{0, 1\}^{T \times C}$는 다음과 같이 정의된다:

$$
O[t, c] = \begin{cases} 1 & \text{if cycle } c \text{ is active at time } t \\ 0 & \text{otherwise} \end{cases}
$$

여기서 "cycle $c$가 시점 $t$에서 활성화되어 있다"는 의미는, **cycle $c$를 구성하는 note 중 적어도 하나가 시점 $t$에 원곡에서 연주되고 있다**는 것이다.

**구축 과정:**

1. **활성화 행렬(activation matrix)** 계산: 각 cycle의 vertex 집합에 속한 note가 원곡의 어느 시점에서 연주되는지 확인하여 이진 행렬을 만든다.

2. **연속 활성 구간 추출**: 산발적인 단일 시점 활성화는 의미가 약하므로, 연속적으로 활성화된 길이가 임계값(scale) 이상인 구간만 남긴다.

3. **Scale 동적 조정**: 각 cycle마다 scale을 조정하여 ON 비율(전체 시점 중 활성 시점의 비율)이 목표치(35%)에 가까워지도록 한다.

**연속값 확장:** 본 연구에서는 이진 중첩행렬 외에 연속값 버전도 도입하였다:

$$
O_{\text{cont}}[t, c] = \frac{\sum_{n \in V(c)} w(n) \cdot \mathbb{1}[n \text{ active at } t]}{\sum_{n \in V(c)} w(n)}
$$

여기서 $V(c)$는 cycle $c$의 vertex 집합, $w(n) = 1 / N_{\text{cyc}}(n)$은 note $n$의 **희귀도 가중치**이며 $N_{\text{cyc}}(n)$은 note $n$이 등장하는 cycle의 개수이다. 적은 cycle에만 등장하는 희귀한 note가 활성화되면 더 큰 가중치를 받는다.

**음악적 의미:** 중첩행렬은 곡의 **위상적 뼈대(topological skeleton)**를 시각화한 것이다. 시간이 흐름에 따라 어떤 반복 구조가 켜지고 꺼지는지를 나타내며, 이것이 음악 생성의 seed 역할을 한다.

---

### 2.7 Kullback-Leibler Divergence와 Jensen-Shannon Divergence

**정의 2.7 (KL Divergence).** 두 이산 확률 분포 $P$와 $Q$에 대해, **Kullback-Leibler divergence**는 다음과 같이 정의된다:

$$
D_{\text{KL}}(P \,\|\, Q) = \sum_{i} P(i) \log \frac{P(i)}{Q(i)}
$$

이는 분포 $Q$를 사용하여 분포 $P$를 부호화할 때 발생하는 **추가 정보량(extra bits)**으로 해석된다. 항상 $D_{\text{KL}}(P \,\|\, Q) \ge 0$이며, 등호는 $P = Q$일 때만 성립한다 (Gibbs' inequality).

**비대칭성:** $D_{\text{KL}}(P \,\|\, Q) \ne D_{\text{KL}}(Q \,\|\, P)$. 예를 들어, $P$에는 자주 나오는 사건이 $Q$에는 거의 없으면 $D_{\text{KL}}(P \,\|\, Q)$는 매우 크지만 그 반대는 작을 수 있다.

**정의 2.8 (Jensen-Shannon Divergence).** KL의 대칭화 버전으로, **JS divergence**는 다음과 같이 정의된다:

$$
D_{\text{JS}}(P \,\|\, Q) = \frac{1}{2} D_{\text{KL}}(P \,\|\, M) + \frac{1}{2} D_{\text{KL}}(Q \,\|\, M)
$$

여기서 $M = \frac{1}{2}(P + Q)$는 두 분포의 평균이다.

**핵심 성질:**
- 대칭성: $D_{\text{JS}}(P \,\|\, Q) = D_{\text{JS}}(Q \,\|\, P)$
- 유계성: $0 \le D_{\text{JS}}(P \,\|\, Q) \le \log 2$ ($\log_2$ 사용 시 최대값 1)
- 평방근 $\sqrt{D_{\text{JS}}}$는 metric (삼각 부등식 성립)

**본 연구에서의 사용:** 생성된 음악과 원곡의 유사도를 평가하는 주요 지표로 사용한다. 구체적으로:

1. **Pitch distribution JS divergence**: 원곡과 생성곡 각각에서 등장하는 pitch의 빈도 분포를 계산하고 그 사이의 JS divergence를 측정한다. 값이 낮을수록 두 곡의 음 사용이 유사하다.

2. **Transition matrix JS divergence** (확장 지표): note $A$ 다음에 어떤 note가 오는지의 transition 빈도 분포를 비교한다. pitch JS가 "어떤 음이 자주 나왔는가"라면, transition JS는 "어떤 순서로 나왔는가"를 측정한다.

수치적으로, 본 연구의 최우수 결과는 JS divergence $\approx 0.002$이다. 이는 원곡과 생성곡의 pitch 분포가 거의 동일함을 의미한다 (최대값 1의 0.2% 수준).

---

### 2.8 Greedy Forward Selection과 Submodularity

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

### 2.9 Multi-label Binary Cross-Entropy Loss

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

### 2.10 음악 네트워크 구축과 가중치 분리

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
- Tran, M. L., Park, C., & Jung, J.-H. (2021). "Topological Data Analysis of Korean Music in Jeongganbo". arXiv:2103.06620.
- 이동진, Tran, M. L., 정재훈 (2024). "국악의 기하학적 구조와 인공지능 작곡".
