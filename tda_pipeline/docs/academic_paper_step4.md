## 4. 실험 설계와 결과

본 장에서는 지금까지 제안한 TDA 기반 음악 생성 파이프라인의 성능을 **정량적으로** 평가한다. 

1. __거리 함수 비교__ — frequency(기본), Tonnetz, voice leading, DFT 네 종류의 거리 함수에 대해 동일 파이프라인을 적용하고 생성 품질을 비교 (§4.1).
2. __연속값 OM 효과 검증__ — 이진 OM 대비 연속값 OM의 효과를 Algorithm 1 및 Algorithm 2 (FC/LSTM/Transformer)에서 검증 (§4.2, §4.3).
3. __DL 모델 비교__ — FC / LSTM / Transformer 세 아키텍처를 동일 조건에서 비교하고, 연속값 OM을 직접 입력으로 활용하는 효과를 검증 (§4.3).
4. __통계적 유의성__ — 각 설정에서 Algorithm 1을 $N = 20$회 독립 반복 실행하여 mean ± std를 보고한다. Algorithm 2는 학습 시간을 고려해 $N = 10$회로 수행한다.

### 평가 지표

__Jensen-Shannon Divergence.__ 생성곡과 원곡의 pitch 빈도 분포 간 JS divergence를 주 지표로 사용한다 (§2.6).

__Note Coverage.__ 원곡에 존재하는 고유 (pitch, duration) 쌍 중, 생성곡에 한 번 이상 등장하는 쌍의 비율. $1.00$이면 모든 note가 최소 한 번 이상 사용된 것이다.

### 거리 함수 구현

__두 note 간 확장 — 옥타브와 duration 보정.__ §2.4의 음악적 거리 함수들은 원래 pitch class만 고려하므로 옥타브와 duration 정보가 손실된다. 본 연구에서 note는 (pitch, duration) 쌍으로 정의되므로, 세 거리 함수 모두에 다음 두 항을 추가한다.

$$
d(n_1, n_2) = d_{\text{base}}(p_1, p_2) + w_o \cdot |o_1 - o_2| + w_d \cdot \frac{|d_1 - d_2|}{\max(d_1, d_2)}
$$

여기서 $d_{\text{base}}$는 Tonnetz / voice leading / DFT 중 하나, $o_i = \lfloor p_i / 12 \rfloor$는 옥타브 번호, $d_i$는 duration이다.

**각 항의 설계 근거:**
- **옥타브 항** $w_o |o_1 - o_2|$: 같은 pitch class라도 옥타브가 다르면 음악적으로 다른 역할을 한다(예: C4와 C5). 
- **Duration 항** $w_d |d_1 - d_2| / \max(d_1, d_2)$: 분자를 $\max$로 정규화하여 $[0, 1]$ 범위로 만든다. 
- **계수 최적화:** $w_o = 0.3$(§4.1a)과 $w_d = 1.0$(§4.1b)은 hibari DFT 조건 N=10 grid search로 최적화되었다.

> **한계 및 후속 과제 — duration tie 정규화로 인한 $w_d$ 해석의 제약.** 본 연구는 hibari를 제외한 모든 곡에서 note를 최소 duration으로 정규화했다. 이 과정에서 긴 음은 붙임줄(tie)로 연결된 여러 짧은 음들로 환원되므로 원 악보의 duration 다양성이 축소된다. §4 이후 일반화 실험(§5.1~§5.2)을 제외하고는 정규화가 적용되지 않는다. aqua·solari에서는 note 수를 줄이기 위해 tie 정규화를 적용하여 모든 duration이 GCD 단위(=1)로 수렴하므로 $|d_1-d_2|=0$이 되어 duration 항이 비활성화된다. 결과적으로 원곡의 리듬·지속 구조를 재현하는 음악을 생성할 수 없으며, **원 duration을 보존하면서도 계산 복잡도를 낮게 유지하는 파이프라인 설계는 후속 과제**로 남긴다.

---

## 4.1 Experiment 1 — 거리 함수 비교 ($N = 20$)

네 종류의 거리 함수 각각으로 사전 계산한 OM을 로드하여, Algorithm 1을 $N = 20$회 독립 반복 실행하고 JS divergence의 mean ± std를 측정한다.

| 거리 함수 | 발견 cycle 수 | 평균 cycle 크기 | JS Divergence (mean ± std) | Note Coverage |
|---|---|---|---|---|
| frequency (baseline) | 1 | 4.0 | $0.0344 \pm 0.0023$ | $0.957$ |
| Tonnetz | 47 | 6.3 | $0.0493 \pm 0.0038$ | $1.000$ |
| voice leading | 19 | 4.6 | $0.0566 \pm 0.0027$ | $0.989$ |
| DFT | 17 | 4.8 | $\mathbf{0.0213 \pm 0.0021}$ | $1.000$ |


__해석 1 — DFT가 가장 우수.__ DFT 거리 함수는 frequency 대비 JS를 $0.0344 \to 0.0213$으로 낮추어 약 $38.2\%$ 낮은 JS를 달성하였다. DFT 거리는 각 note의 pitch class를 $\mathbb{Z}/12\mathbb{Z}$ 위의 12차원 이진 벡터로 표현한 후 이산 푸리에 변환(DFT)을 적용하고, 복소수 계수의 **magnitude(크기)만** 거리 계산에 사용한다. 이조(transposition)는 DFT 계수의 **phase(위상)**만 바꿀 뿐 magnitude에는 영향을 주지 않는다. 이렇게 phase 정보를 버리고 magnitude만 고려함으로써 이조에 불변인 **화성 구조의 지문**을 추출하게 된다.

특히 $k=5$ 푸리에 계수가 diatonic scale과 강하게 반응하는 이유는 다음과 같다. 12개 pitch class를 **완전5도 순환(circle of fifths)** 순서 $\{C, G, D, A, E, B, F{\sharp}, C{\sharp}, G{\sharp}, D{\sharp}, A{\sharp}, F\}$로 재배열하면, diatonic scale에 속하는 7개 pitch class는 이 순환 상의 **연속된 7개 위치**를 차지한다. DFT의 $k=5$ 계수의 magnitude는 정확히 이 "5도 순환 상의 연속성"을 수치로 측정하는 양이며, $\binom{12}{7} = 792$개의 7-note subset 중 diatonic scale 류가 $|F_5|$를 최대화한다 (§4.5.1 maximal evenness). hibari의 7개 PC 집합 $\{0, 2, 4, 5, 7, 9, 11\}$ (C major / A natural minor) 역시 이 최대화 subset 중 하나이므로, DFT magnitude 공간에서 hibari의 note들은 frequency 거리에서는 포착되지 않던 **음계적 동질성**에 의해 서로 가깝게 군집된다.

__해석 2 — 거리 함수가 위상구조 자체를 바꾼다.__ 거리 함수의 선택이 곧 어떤 음악적 구조를 동치로 간주할 것인가를 정의한다. 

__해석 3 — Note Coverage는 대부분의 설정에서 포화.__ 원곡의 모든 note 종류가 생성곡에 최소 한 번 등장해야 한다는 기본 요구는 모두 만족된다. 따라서 품질의 주된 차이는 같은 note pool을 얼마나 *자연스러운 비율로* 섞는가에서 발생한다.

## 4.1a Octave Weight 튜닝 — DFT + N=10 Grid Search

DFT 거리 함수의 옥타브 가중치 $w_o$를 $\{0.1, 0.3, 0.5, 0.7, 1.0\}$에 대해 hibari Algo1 JS로 $N=10$ 반복 실험하였다. $w_d = 1.0$ (§4.1b 최적값) 고정.

| $w_o$ | K (cycle 수) | JS (mean ± std) |
|---|---|---|
| 0.1 | 14 | $0.0380 \pm 0.0026$ |
| **0.3** | **19** | $\mathbf{0.0163 \pm 0.0014}$ |
| 0.5 | 16 | $0.0183 \pm 0.0020$ |
| 0.7 | 16 | $0.0231 \pm 0.0019$ |
| 1.0 | 16 | $0.0204 \pm 0.0020$ |

**결론:** $w_o = 0.3$이 최적이다 (JS = 0.0163). 옥타브 패널티를 줄이면 pitch class 유사성이 거리 행렬을 더 강하게 지배하며, 이는 hibari의 좁은 옥타브 범위(52–81, 최대 2 옥타브)에서 옥타브 구분이 상대적으로 덜 중요하다는 음악적 직관과 일치한다.

---

## 4.1b Duration Weight 튜닝 — DFT + N=10 Grid Search

DFT 거리 함수의 duration 가중치 $w_d$를 $\{0.0, 0.1, 0.3, 0.5, 0.7, 1.0\}$에 대해 hibari Algo1 JS로 $N=10$ 반복 실험하였다. $w_o = 0.3$ (§4.1a 최적값) 고정.

| $w_d$ | K (cycle 수) | JS (mean ± std) |
|---|---|---|
| $0.0$ | $10$ | $0.0503 \pm 0.0042$ |
| $0.1$ | $25$ | $0.0311 \pm 0.0021$ |
| $0.3$ | $16$ | $0.0221 \pm 0.0017$ |
| $0.5$ | $17$ | $0.0215 \pm 0.0024$ |
| $0.7$ | $17$ | $0.0211 \pm 0.0016$ |
| **$1.0$** ★ | **$19$** | $\mathbf{0.0156 \pm 0.0012}$ |

**결론:** $w_d = 1.0$이 최적이다 (JS = $0.0156$). duration 가중치를 최대화할 때 성능이 가장 좋다. DFT는 pitch class 집합의 스펙트럼 구조(indicator vector $\chi_S \in \{0,1\}^{12}$의 이산 Fourier 계수 $|\hat{\chi}_S(k)|$가 나타내는 대칭성 패턴)를 정밀하게 포착하므로 $w_d$가 높아도 pitch 정보가 충분히 보존되며, 오히려 duration이 거리 행렬에 많이 기여할수록 cycle 수와 생성 품질이 향상되는 경향이 나타난다. 또한 $w_d = 0.0$ (duration 항 완전 제거)일 때 cycle 수가 $10$으로 급감하고 JS가 $0.0503$으로 크게 악화되어, duration 정보가 거리 행렬의 질에 유의미하게 기여함을 확인하였다.

**DFT 계수 예시.** hibari의 PC 집합 $S = \{0, 2, 4, 5, 7, 9, 11\}$의 indicator vector $\chi_S = (1,0,1,0,1,1,0,1,0,1,0,1)$에 대해 DFT magnitude $(|F_0|, \ldots, |F_6|) \approx (7, 0.27, 1.41, 1.0, 1.41, \mathbf{2.73}, 1)$으로 $|F_5|$가 다른 성분 대비 압도적으로 크다. 이는 diatonic이 완전5도 순환 $\{C, G, D, A, E, B, F\}$ 상에서 연속 7개 위치를 차지하기 때문이다. 반대로 chromatic cluster $S' = \{0,1,2,3,4,5,6\}$에서는 $|F_1|$이 커지고 $|F_5|$가 작아진다.

---

## 4.1c 감쇄 Lag 가중치 실험

§2.9에서 언급한 감쇄 합산 inter weight의 실험적 근거를 제시한다. lag 1 단일 옵션과 lag 1~4 감쇄 합산 옵션 두 설정을 비교하되, 거리 함수는 DFT와 Tonnetz 두 가지를 대조하여 거리 함수의 특성에 따라 효과가 달라짐을 확인한다.

**실험 설정:**
- lag 1 단일 : $W_{\text{inter}} = W_{\text{inter}}^{(1)}$
- lag 1~4 감쇄 합산 :

$$W_{\text{inter}} = \sum_{\ell=1}^{4} \lambda_\ell \cdot W_{\text{inter}}^{(\ell)}, \qquad (\lambda_1,\lambda_2,\lambda_3,\lambda_4) = (0.60,\ 0.30,\ 0.08,\ 0.02)$$

- 고정 조건: hibari, Algorithm 1, N=20

$N = 20$ 반복.

| 곡 | 거리 함수 | lag 1 단일 (JS mean ± std) | lag 1~4 감쇄 합산 (JS mean ± std) | 변화 |
|---|---|---|---|---|
| hibari | DFT | $0.0211 \pm 0.0021$ | $\mathbf{0.0196 \pm 0.0022}$ | $\mathbf{-7.1\%}$ ★ |
| hibari | Tonnetz | $0.0488 \pm 0.0040$ | $0.0511 \pm 0.0039$ | $+4.8\%$ |

__해석 4 — DFT에서 개선, Tonnetz에서는 악화.__ DFT 거리에서는 감쇄 lag가 JS를 7.1% 개선한다. 반면 Tonnetz에서는 오히려 4.8% 악화한다. 경험적으로 DFT 조건에서만 감쇄 lag 합산이 유효하며, Tonnetz에서는 역효과였다. DFT의 pitch class 스펙트럼 표현이 먼 lag의 시간 상호작용 정보를 흡수하는 데 더 적합하다는 경험적 관찰이며, 이론적 설명은 후속 과제로 남긴다.

> **Tonnetz 결과 병기 이유.** §4.1에서 DFT를 본 연구의 baseline로 결정했지만, §5.6.1 Tonnetz 기반 통합 실험의 수치적 기반을 제공하고, §5.6.3 메타 통찰 시 참고하기 위해 두 거리 함수를 대조한다.

> **Algorithm 2 미실험 이유.** 감쇄 lag는 OM 생성 *이전* 단계인 가중치 행렬 $W_{\text{inter}}$에 적용된다. Algorithm 2는 이미 완성된 OM을 입력으로 받으므로, §4.3 DFT baseline 실험의 입력 OM에 감쇄 lag를 묵시적으로 반영하였다. 독립 ablation은 별도로 수행하지 않았다.

> **향후 과제 — inter 감쇄 계수 재탐색.** 본 실험에선 임의로 $\lambda_1 = 0.60$으로 설정하였는데, intra weight에서 lag=1 계수를 $1.0$으로 두는 것과의 비대칭이 존재한다. inter lag 감쇄 계수 $(\lambda_1, \lambda_2, \lambda_3, \lambda_4)$는 휴리스틱으로 설정된 것이므로, 향후 $\lambda_1 = 1.0$을 포함한 grid search 및 uniform/exponential decay 비교 실험이 가능하다.

---

## 4.2 연속값 OM 실험

![Figure C/D — Binary vs 연속값 OM Matrix](figures/fig_overlap_compare.png){width=85%}

본 절은 §2.5에서 정의한 연속값 OM $O_{\text{cont}} \in [0,1]^{T \times K}$가 이진 OM $O \in \{0,1\}^{T \times K}$ 대비 어떤 영향을 주는지를 정량적으로 검증한다. 거리 함수는 모든 설정에서 **DFT**로 고정한다. 본 실험은 Algorithm 1에 대해서만 수행하였다. Algorithm 2에서 이진/연속값 입력의 효과는 §4.3에서 세 모델(FC/LSTM/Transformer) 비교 실험의 일부로 다룬다.

### 실험 설계

cycle별 시점 활성도 $a_{c,t}$는 두 가지 방식으로 계산할 수 있다.

__이진 (binary)__: 단순 OR 연산이다. $V(c)$에 속하는 note가 시점 $t$에 하나라도 활성이면 $a_{c,t} = 1$, 그렇지 않으면 $0$이다.

__연속값 (continuous)__: cycle을 구성하는 note들이 *얼마나 많은 비율로* 활성화되어 있는지를 $[0,1]$ 실수로 표현한다 :

$$
a_{c,t} \;=\; \left(\;\sum_{n \in V(c)} w(n)\cdot\mathbb{1}[n \in A_t]\;\right)\;/\;\left(\;\sum_{n \in V(c)} w(n)\;\right)
$$

여기서 $A_t$는 시점 $t$에 활성인 note들의 집합, $w(n) = 1/N_{\text{cyc}}(n)$은 note $n$의 **희귀도 가중치**이며 $N_{\text{cyc}}(n)$은 note $n$이 등장하는 cycle의 개수이다.

연속값 활성도가 만들어진 후, 최종 OM을 만드는 방식에 따라 다시 두 가지 변형이 가능하다.

- __직접 사용 (direct)__: $O[t, c] = a_{c,t} \in [0, 1]$
- __임계값 이진화 (threshold $\tau$)__: $O[t, c] = \mathbb{1}[\,a_{c,t} \ge \tau\,]$, $\tau \in \{0.3, 0.5, 0.7\}$

### 결과

DFT 조건, $w_o = 0.3$, $w_d = 1.0$, $N = 20$ 반복.

| 설정 | Density | JS Divergence (mean ± std) |
|---|---|---|
| __(A) Binary__ | $\mathbf{0.313}$ | $\mathbf{0.0157 \pm 0.0018}$ ★ |
| (B) Continuous direct | $0.728$ | $0.0186 \pm 0.0015$ |
| (C) Continuous → bin $\tau = 0.3$ | $0.367$ | $0.0360 \pm 0.0029$ |
| (C) Continuous → bin $\tau = 0.5$ | $0.199$ | $0.0507 \pm 0.0027$ |
| (C) Continuous → bin $\tau = 0.7$ | $0.060$ | $0.0449 \pm 0.0024$ |

여기서 "Density"는 **OM (1,088 timestep × $K$ cycle) 기준** 활성 셀의 평균 비율 ($\bar{O}$)이다. §3.2의 ON ratio는 **원곡 multi-hot 행렬 $y \in \{0,1\}^{T \times N}$ 기준**으로 대상 행렬이 다르다.

### 해석

__해석 5a — Binary가 최우수.__ DFT 거리는 스펙트럼 구조를 정밀하게 포착하므로 이진 표현만으로도 cycle 활성 신호가 충분히 구별된다. DFT 이진 OM의 density $0.313$은 **선택적 sparsity** — 즉 의미 있는 시점에만 해당 cycle이 활성화되는 상태 — 를 자체적으로 달성한다는 뜻이다. Algorithm 1의 교집합 sampling은 density가 너무 낮으면 활성 cycle이 부족해 note 선택의 다양성이 떨어지고, 너무 높으면 cycle 간 교집합이 비어 fallback(전체 pool 균등 추출)된다. 

__해석 5b — Continuous direct는 오히려 열세.__ (B) continuous direct ($\bar{O} = 0.728$)는 이진보다 훨씬 dense하여, Algorithm 1의 교집합 sampling이 과도하게 자주 호출되어 Binary 대비 $18.5\%$ 악화한다.

__해석 5c — 임계값 이진화는 모두 열세.__ DFT 이진 OM이 이미 cycle 활성의 핵심 구간만을 선별하므로 추가적인 임계값 필터링($\tau = 0.3 \sim 0.7$)은 과도한 sparsity를 만들어 성능을 저하시킨다.

---

## 4.3 Experiment 3 — Algorithm 2 DL 모델 비교

DFT 기반 OM 입력 ($\alpha = 0.5$, $w_o = 0.3$, $w_d = 1.0$)에서 세 모델을 비교한다. 각 모델을 이진 OM $O \in \{0,1\}^{T \times K}$과 연속값 OM $O_{\text{cont}} \in [0,1]^{T \times K}$의 두 입력에서 모두 학습하였다. $N = 10$ 반복. ($\alpha$ grid search 결과는 §5.7에서 별도 탐색하며, Algo2 조건의 $\alpha = 0.25$ 재실험은 §5.8.2 참조.)

### 모델 아키텍처

- **FC** (Fully Connected, 2-layer, $H=128$, dropout$=0.3$): 각 시점 $t$의 cycle 활성 벡터 $O[t, :] \in \{0,1\}^K$ 또는 $O_{\text{cont}}[t, :] \in [0,1]^K$를 입력으로 받아 동시점의 note label 분포를 출력. **시점 간 독립 매핑**이므로 시간 문맥 없음.
- **LSTM** (2-layer, $H=128$): cycle 활성 벡터 시퀀스 $\{O[t, :]\}_{t=1}^{T}$를 순차 입력. 순차 구조 $h_t = f(x_t, h_{t-1})$로 과거 문맥을 hidden state에 누적.
- **Transformer** (2-layer, 4-head self-attention, $d_{\text{model}} = 128$): positional embedding으로 시간 위치를 인코딩하고 self-attention으로 **전 시점 동시 참조**가 가능.

세 모델 모두 동일한 학습 조건에서 multi-label BCE loss (§2.8)로 학습한다. 각 시점에서 예측된 note 확률로부터 샘플링하여 생성곡을 얻는다. **validation loss**는 학습 시점 validation set에서 측정한 BCE loss의 평균이다.

| 모델 | 입력 | Pitch JS (mean ± std) | validation loss (mean) |
|---|---|---|---|
| FC | binary | $0.00217 \pm 0.00056$ | $0.339$ |
| FC | __continuous__ | $\mathbf{0.00035 \pm 0.00015}$ ★ | $\mathbf{0.023}$ |
| LSTM | binary | $0.233 \pm 0.029$ | $0.408$ |
| LSTM | continuous | $0.170 \pm 0.027$ | $0.395$ |
| Transformer | binary | $0.00251 \pm 0.00057$ | $0.836$ |
| Transformer | continuous | $0.00082 \pm 0.00026$ | $0.152$ |

### 해석

__해석 6 — FC + continuous 입력이 최우수.__ FC가 연속값 입력에서 JS $0.00035$로 가장 낮은 값을 달성하였다. 동일한 FC의 이진 입력 ($0.00217$) 대비 $83.9\%$ 개선된 수치이며, Welch's $t$-test $p = 1.50 \times 10^{-6}$로 통계적으로 유의하다. Transformer continuous와의 비교에서도 FC continuous가 유의하게 우수하다 (Welch $p = 1.66 \times 10^{-4}$). FC의 cell-wise 표현력이 DFT continuous OM의 cycle 활성 강도 차이를 세밀하게 반영한다.

__해석 7 — LSTM의 심각한 열화.__ LSTM은 이진 입력 $0.233$, 연속값 입력 $0.170$으로 다른 두 모델과 비교할 수 없는 수준으로 열화하였다. LSTM의 **순차 구조(recurrent structure)** 란 시점 $t$의 hidden state $h_t$가 직전 시점 $h_{t-1}$로부터 $h_t = f(x_t, h_{t-1})$로 갱신되는 순차적 정보 전파 메커니즘을 의미하며, 이 구조는 시점이 연속적으로 이어지는 부드러운 시계열(예: 자연어, 음향 파형)에 적합하다. 그러나 OM은 본질적으로 시점별 이산 on/off 활성 패턴이며, 특히 hibari의 cycle 활성 위치는 모듈 기반 phase shifting 구조(§4.5.4)를 따라 모듈 단위로 평행 이동하므로 직전 시점의 hidden state가 현재 시점 예측에 기여하는 바가 작다.

__해석 8 — 연속값 입력의 보편적 이점.__ 세 모델 모두 연속값 입력이 이진 입력보다 유의하게 우수하다 (모두 Welch $p < 10^{-4}$). 그러나 그 개선율은 모델별로 다르다: FC($-83.9\%$), Transformer($-67.4\%$), LSTM($-27.3\%$). 

__해석 9 — Validation loss와 JS의 동시 감소.__ FC-continuous는 validation loss ($0.023$)가 FC-binary ($0.339$)의 약 $7\%$ 수준이며 JS도 동시에 크게 감소한다. 연속값 입력이 모델의 학습 signal을 더 부드럽게 만들어, 과적합 없이 일반화된 분포를 학습하게 한다.

### 통합 비교 (§4.1 ~ §4.3)

| 실험 | 설정 | JS divergence | 출처 |
|---|---|---|---|
| §4.1 Algo 1 | frequency baseline | $0.0344$ | §4.1 |
| §4.1 Algo 1 | DFT (최적) | $0.0213$ | §4.1 |
| §4.2 Algo 1 | DFT binary (최적 파라미터) | $\mathbf{0.0157 \pm 0.0018}$ ★ | §4.2 |
| §4.3 Algo 2 FC | DFT continuous | $\mathbf{0.00035 \pm 0.00015}$ ★ | §4.3 |

**§4.3 FC (DFT continuous)**는 DFT 기반 실험 내에서 관측된 최저 JS divergence이다. 이론적 최댓값 $\log 2 \approx 0.693$의 약 $0.05\%$에 해당한다.

---

## 4.4 종합 논의

__(1) 음악이론적 거리 함수의 중요성.__ §4.1. Experiment 1 결과는 "DFT처럼 음악이론적 구조를 반영한 거리가 더 좋은 위상적 표현을 만들 수 있다"는 가설을 지지한다. 

__(2) Algorithm 1의 이진 OM, Algorithm 2의 연속값 OM.__ 거리 함수 baseline으로 DFT를 채택했을 때 Algorithm 1에서는 이진 OM이 연속값 OM보다 우수한 반면 (§4.2), Algorithm 2의 FC에서는 연속값 OM이 큰 폭으로 우수하다 (§4.3, $-83.9\%$). 규칙 기반 Algorithm 1은 sparse한 이진 활성 패턴을 직접 샘플링에 사용하므로 이진 OM이 적합하지만, DL 기반 Algorithm 2의 FC는 continuous activation의 강도 정보를 학습 signal로 활용하여 cell-wise 표현력이 극대화된다.

__(3) FC + continuous 입력의 결정적 우위.__ DL 모델 비교 (§4.3)에서 FC-cont가 JS $0.00035$로 Transformer-cont ($0.00082$) 대비 유의하게 우수하다.

---

## 4.5 곡 고유 구조 분석 — hibari 의 수학적 불변량

본 절은 hibari 가 가지는 수학적 고유 성질을 분석하고, 이 성질들이 본 연구의 실험 결과와 어떻게 연결되는지를 서술한다. 비교 대상으로 사카모토의 다른 곡인 solari 와 aqua 를 함께 분석한다.

### 4.5.1 Deep Scale Property — hibari 의 pitch class 집합이 갖는 대수적 고유성

hibari 가 사용하는 7개 pitch class 는 $\{0, 2, 4, 5, 7, 9, 11\} \subset \mathbb{Z}/12\mathbb{Z}$이다. 이 집합의 **interval vector**는 $[2, 5, 4, 3, 6, 1]$로 여기서 $k$번째 성분은 "집합 안에서 interval class $k$에 해당하는 쌍의 수"이다. 옥타브 대칭에 의해 $k$는 $12 - k$와 동치이므로 interval class는 $1 \sim 6$까지만 존재한다.

이 벡터의 6개 성분은 __모두 다른 수__($\{1, 2, 3, 4, 5, 6\}$의 순열)로 이것을 **deep scale property** 라 한다 (Gamer & Wilson, 2003). 이 성질을 갖는 7-note subset 은 $\binom{12}{7} = 792$개 중 __diatonic scale 류 뿐__이다. 

또한 7개 PC 사이의 간격 패턴은 $[2, 2, 1, 2, 2, 2, 1]$로, 오직 $\{1, 2\}$ 두 종류의 간격만으로 구성된다. 이것은 __maximal evenness__ — 12개 칸 위에 7개 점을 가능한 한 균등하게 배치한 상태 — 를 의미한다 (Clough & Douthett, 1991). deep scale property와 maximal evenness 는 모두 diatonic scale 의 고유 성질이다.

solari 와 aqua 는 12개 PC 모두를 사용하므로 이 성질을 갖지 않는다.

### 4.5.2 근균등 Pitch 분포 — Pitch Entropy

| 곡 | 사용 pitch 수 | 정규화 pitch entropy | 해석 |
|---|---|---|---|
| __hibari__ | $17$ | $\mathbf{0.974}$ | 거의 완전 균등 |
| solari | $34$ | $0.905$ | 덜 균등 |
| aqua | $51$ | $0.891$ | 가장 치우침 |

pitch entropy는 곡 안에서 사용된 모든 pitch의 빈도 분포에 대한 Shannon entropy를 이론적 최댓값으로 나눈 **정규화 Shannon entropy**이다. hibari 의 $0.974$ 는 __"모든 pitch 를 거의 같은 빈도로 사용"__한다는 뜻이며, §4.3 의 "FC 모델 우위"를 뒷받침한다.

### 4.5.3 Tonnetz 구별력과 Pitch Class 수의 관계

hibari 의 7개 PC 는 Tonnetz 위에서 __하나의 연결 성분__을 이루며, 평균 degree 가 $3.71/6 = 62\%$이다. Tonnetz 이웃 관계는 $\pm 3$ (단3도), $\pm 4$ (장3도), $\pm 5$ (완전5도) 의 세 가지 방향이며, 각 방향이 양쪽으로 작용하므로 최대 $6$개의 이웃이 가능하다.

예를 들어 C(0) 의 Tonnetz 이웃은 $\{E, F, G, A\}$의 __4개__ 이다:

| 관계 | $+$ 방향 | $-$ 방향 | hibari 에 있는가 |
|---|---|---|---|
| 단3도 ($\pm 3$) | D#(3) | A(9) | A 있음 |
| 장3도 ($\pm 4$) | E(4) | G#(8) | E 있음 |
| 완전5도 ($\pm 5$) | G(7) | F(5) | G, F 있음 |

__Tonnetz 그래프의 지름(diameter).__

12개 PC를 전부 사용하는 곡 (solari, aqua) 에서는 어떤 두 PC 든 Tonnetz 거리가 $\leq 2$이다. 이는 __"가까운 음"과 "먼 음"을 구별할 여지가 거의 없다__는 뜻이다. 반면 hibari에서는 Tonnetz 거리가 $1 \sim 4$ 범위로 분포하여, 가까운 쌍 (예: C-G, 거리 $1$) 과 먼 쌍 (예: F-B, 거리 $3$ 이상) 이 명확히 구별된다.

단, 이는 **Tonnetz 거리 함수가 빈도 기반(frequency)보다 유리할 구조적 정황**일 뿐, hibari의 최적 거리 함수가 Tonnetz임을 의미하지는 않는다. §4.1의 hibari 실험에서는 **DFT가 Tonnetz 대비 $-56.8\%$로 유의하게 우수**하였고 §5.1의 solari 실험에서는 "12-PC에서는 Tonnetz 구별력이 소실되어 frequency와 Tonnetz가 동등해진다"는 결과가 나왔다.

### 4.5.4 Phase Shifting — inst 1 과 inst 2 의 서로소 주기 구조

그림 2.9 에서 관찰한 패턴을 더 정밀하게 분석하면, 마디 내 쉼의 상대위치가 모듈마다 정확히 1칸씩 이동한다는 것이 발견된다. inst 2 의 모듈별 쉼 위치를 조사하면 __대각선 패턴__이 나타난다. :

```
module  1: rest at position  0
module  2: rest at position  1
module  3: rest at position  2
module  4: rest at position  3
  ...
module  k: rest at position  k-1
```

32-timestep의 마디 안에서 쉼의 위치가 매 모듈마다 정확히 1칸씩 오른쪽으로 밀린다. 32개 모듈을 거치면 쉼이 마디 내 모든 상대위치 ($0, 1, 2, \ldots, 31$) 를 정확히 한 번씩 방문한다. 이 구조는 미니멀리즘 작곡가 Steve Reich 가 *Piano Phase* (1967) 에서 사용한 __phase shifting__ 기법과 수학적으로 동일하다. 같은 패턴을 연주하는 두 악기 중 하나가 아주 조금 느리게 진행하여, 같은 패턴이 점점 어긋나다가 한참 뒤에야 정렬되는 것이다. hibari 에서 이 phase shifting 은 다음과 같이 수치화된다.

| | inst 1 | inst 2 |
|---|---|---|
| 모듈 주기 | $M = 32$ (쉼 없음) | $M + 1 = 33$ (32 음 + 1 쉼) |
| 반복 횟수 | $33$ 회 | $32$ 회 |
| 총 길이 | $33 \times 32 = 1{,}056$ | $32 \times 33 = 1{,}056$ |

두 주기가 $32$ 와 $33$ 으로 __서로소__이다. 이 관계 때문에 두 악기의 위상(phase)이 곡 전체에서 한 번도 __모듈 단위로__ 동기화되지 않는다. 이때, 모듈 자체가 A-B-A'-C 구조로 구성되어 국소적으로는 같은 위상(phase)이 반복되는 시점이 있다.

이 구조는 수학적으로 __Euclidean rhythm__ (Bjorklund, 2003; Toussaint, 2005) 과도 연결된다. Euclidean rhythm 은 "$n$ 비트 중 $k$ 개를 가능한 한 균등하게 배치" 하는 알고리즘으로, 아프리카 전통 음악과 전자 음악에서 널리 사용된다. hibari 의 경우 "$33$ 칸 중 $1$ 칸을 비운다" 를 $32$번 반복하면서 매번 1칸씩 이동하는 것이 Euclidean rhythm 의 가장 단순한 형태이다.

---
