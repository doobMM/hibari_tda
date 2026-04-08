---

## 6. 차별화 포인트 — 기존 연구와의 비교

본 연구의 위치를 명확히 하기 위해, 두 가지 관련 연구 흐름과 비교한다. 하나는 **일반적인 AI 음악 생성 연구** 이며, 다른 하나는 **TDA를 음악에 적용한 선행 연구**들이다.

### 6.1 일반 AI 음악 생성 연구와의 차별점

지난 10년간 Magenta, MusicVAE, Music Transformer 등 대규모 신경망 기반 음악 생성 모델이 여러 발표되었다. 이들은 공통적으로 다음 구조를 따른다:

$$
\text{\{수만 곡의 MIDI 코퍼스\}} \;\to\; \text{신경망 학습} \;\to\; \text{샘플링 생성}
$$

본 연구는 이와 다음 네 가지 지점에서 근본적으로 다르다.

__(1) 코퍼스 규모 vs 단일곡 심층 분석.__ 일반적인 AI 음악 생성은 "많은 곡을 보고 평균적인 음악 규칙을 배우는 것"을 목표로 한다. 본 연구는 반대로 **단 한 곡(hibari)의 구조를 가능한 한 깊이 해석한 뒤 그 구조를 재생성**하는 것을 목표로 한다. 음악 학자가 한 곡의 악보를 정밀하게 분석하는 작업에 가깝다.

__(2) Blackbox 학습 vs 구조화된 seed.__ 일반 신경망 모델은 학습이 끝난 후 "왜 이 음이 나왔는가"를 설명하기 어렵다. 본 연구의 파이프라인은 **persistent homology로 추출한 cycle 집합**이라는 명시적이고 해석 가능한 구조를 seed로 사용하며, 생성된 모든 음은 "특정 cycle의 활성화"라는 구체적 근거를 갖는다. 즉 생성 결과가 *역추적 가능*하다.

__(3) 시간 모델링의 역설.__ 일반 음악 생성 모델은 "더 정교한 시간 모델일수록 더 좋다"는 암묵적 가정을 가지며, 그래서 Transformer 계열 모델이 주류가 되었다. 본 연구의 §3.4에서 관찰된 "가장 단순한 FC가 가장 좋은 결과를 낸다"는 결과는, 이러한 일반적 가정이 **곡의 미학적 성격에 따라 뒤집힐 수 있다**는 증거이다. hibari처럼 시간 인과보다 공간적 배치를 중시하는 곡에서는 *시간 문맥을 무시하는 모델*이 오히려 곡의 성격에 더 맞다.

__(4) 작곡가의 작업 방식 반영.__ 본 연구의 가중치 분리 (intra / inter / simul) 는 사카모토 본인이 인터뷰에서 밝힌 작곡 방식 — "한 악기를 시간 방향으로 충분히 채운 뒤 다른 악기를 그 위에 겹쳐 배치" — 을 수학적 구조에 직접 반영한 것이다 (§2.9). 일반적인 AI 음악 생성에서는 모델의 architectural choice가 "학습 효율"에 따라 결정되지만, 본 연구에서는 **작곡가의 실제 작업 방식**이 설계의 출발점이다.

### 6.2 기존 TDA-Music 연구와의 차별점

TDA를 음악에 적용한 선행 연구는 몇 편이 있으며, 본 연구와 가장 가까운 것은 다음 두 편이다.

- **Tran, Park, & Jung (2021)** — 국악 정간보(Jeongganbo)에 TDA를 적용하여 전통 한국 음악의 위상적 구조를 분석. 초기적 탐구 연구이며, 본 연구가 사용하는 파이프라인의 공통 조상.
- **이동진, Tran, 정재훈 (2024)** — 국악의 기하학적 구조와 AI 작곡. 본 연구의 지도교수 연구실의 직전 연구이며, 본 연구가 계승한 pHcol 알고리즘 구현과 $\rho^* = 0.35$ 휴리스틱의 출처.

본 연구가 이들 대비 새로 기여하는 지점은 다음 다섯 가지이다.

__(A) 네 가지 거리 함수의 체계적 비교.__ 선행 연구들은 frequency 기반 거리만을 사용했으나, 본 연구는 frequency, Tonnetz, voice-leading, DFT 네 가지를 동일한 파이프라인 위에서 $N = 20$회 반복 실험으로 정량 비교하였다 (§3.1). 이를 통해 "Tonnetz가 frequency 대비 JS divergence를 47% 낮춘다"는 음악이론적 정당성을 실증적으로 제공한다.

__(B) Continuous overlap matrix의 도입과 검증.__ 선행 연구들은 이진 overlap matrix만을 사용했다. 본 연구는 희귀도 가중치를 적용한 continuous 활성도 개념을 새로 도입했으며 (§2.5), $\tau = 0.5$ 임계값 이진화가 추가로 $11.4\%$ 개선을 주는 것을 통계 실험으로 검증하였다 (§3.3a).

__(C) 통계적 엄밀성.__ 선행 연구들은 단일 run 결과만 보고했지만, 본 연구는 모든 baseline에서 $N = 20$회 반복 실행하여 mean ± std, Welch $t$-test, Cohen's $d$를 보고한다. 이는 TDA-music 분야에서 "효과가 실재하는가"를 통계적으로 검증한 최초의 사례 중 하나이다.

__(D) 서양 현대음악으로의 확장.__ 기존 연구가 국악을 대상으로 했다면, 본 연구는 서양의 minimalism / ambient 계열 현대음악 (사카모토 *out of noise*) 으로 적용 범위를 확장했다. 이를 통해 TDA 기반 분석이 **장르 특이적이지 않음**을 보였다.

__(E) 곡의 미학적 맥락과 모델 선택의 연결.__ 본 연구의 §3.4 해석 — FC 모델 우위를 *out of noise* 앨범의 작곡 철학으로 설명 — 은 기존 TDA-music 연구에 없던 관점이다. "어떤 곡에는 어떤 모델이 맞는가"가 단순히 성능 최적화 문제가 아니라 **미학적 정합성 문제**임을 제시한다.

### 6.3 세 줄 요약

1. 본 연구는 단일곡의 위상 구조를 가능한 한 깊이 이해하고 그 구조를 보존한 채 재생성하는 *심층 분석 — 재생성* 파이프라인이다.
2. 네 가지 거리 함수, 두 가지 overlap 형식, 세 가지 신경망 모델, 통계적 반복이라는 네 축의 체계적 비교가 본 연구의 경험적 기여이다.
3. 작곡가의 작업 방식 (§2.9) 과 곡의 미학적 맥락 (§3.4) 을 수학적 설계에 직접 반영한 것이 본 연구의 해석적 기여이다.

---

## 7. 향후 연구 방향

본 연구는 여러 확장 가능성을 열어두고 있다. 우선순위와 연결되는 함의 순으로 정리한다.

### 7.1 모듈 단위 생성 + 구조적 재배치 (Most Immediate)

본 연구는 지금까지 "전체 $T = 1{,}088$ timesteps에 해당하는 음악을 한 번에 생성"하는 방식을 사용했다. 그러나 §5 Figure 7에서 드러났듯이, hibari의 실제 구조는 **32-timestep 모듈이 33회 반복**되는 형태이며, 두 악기는 inst 1 = 연속적 기저 흐름, inst 2 = 모듈마다 쉼을 두는 얹힘 구조라는 상보적 역할을 가진다.

이 관찰을 반영한 새로운 생성 전략이 가능하다:

1. __한 모듈만 생성__ — persistent homology로 얻은 cycle 집합 중 모듈 1개(32 timesteps)의 위상 구조를 보존하는 최소 단위의 생성을 먼저 수행한다. 이는 기존 파이프라인을 $T = 32$로 줄여 그대로 실행한 뒤, 중첩행렬의 한 모듈 폭 만큼만 seed로 사용하면 된다.
2. __hibari 구조에 따라 배치__ — 생성된 모듈을 $33$회 반복하되:
   - inst 1 자리에는 동일한 모듈을 쉼 없이 이어 붙임
   - inst 2 자리에는 같은 모듈을 각 반복마다 inst 1 대비 shift (Figure 7 관찰에 맞게) + 모듈마다 지정된 위치에 쉼을 삽입
3. __모듈 간 이행 매끄럽게__ — 단순 복제가 아니라 모듈 경계에서 자연스러운 이행이 이루어지도록 ±2 timesteps 정도의 "이음새" 영역을 가변 cycle로 재샘플링.

이 접근의 이점은 다음과 같다.
- __계산 효율__: $T = 1{,}088$ 대신 $T = 32$로 persistent homology를 계산하므로 수 배 빠르다.
- __구조적 충실도__: hibari의 고유 모듈 구조를 재샘플링이 아닌 *복제*로 보존하므로 곡의 정체성이 유지된다.
- __변주 가능성__: 한 모듈의 cycle seed만 바꾸면 전체 곡 수준의 변주가 자동으로 만들어진다.

### 7.2 다른 곡으로의 일반화 — *out of noise* 앨범 전곡

본 연구의 §3.4 해석 8("hibari의 FC 우위는 곡의 미학적 성격에서 기인")은 가설 수준이다. 이를 검증하려면 *out of noise* 앨범의 다른 곡들 — `hwit`, `still life`, `in the red`, `tama` 등 — 이나 Sakamoto 의 다른 시기 작품 (예: 1998년 *BTTB* 의 `aqua`) 에 같은 파이프라인을 적용하여 **FC가 계속 우위를 보이는지**를 확인해야 한다. 만약 앨범 전체에서 FC 우위 패턴이 반복된다면, "작곡 철학이 모델 선택을 결정한다"는 주장이 통계적으로 뒷받침된다.

대조군으로 **전통적 선율 인과가 강한 곡** (Ravel "Pavane pour une infante défunte", Debussy "Clair de lune", 바흐 평균율 클라비어 중 fugue 등)에 같은 파이프라인을 적용하여 LSTM / Transformer가 우위로 뒤집히는지도 검증해야 한다. 이 두 그룹의 대비가 명확히 드러나면, 본 연구의 "곡의 미학과 모델 구조의 정합성" 가설이 *genre-dependent music modeling*이라는 더 일반적인 framework로 확장될 수 있다.

__현 단계 상태__: 본 연구는 현재 `Ryuichi_Sakamoto_-_hibari.mid` 외에 다른 원곡 MIDI 를 확보하지 못했다. 따라서 §7.2 는 *구체적 추가 실험은 미수행*한 채 향후 과제로만 명시해 둔다. 후속 작업에서 MIDI 확보가 이루어지는 대로 본 §7.2 의 `aqua` / `hwit` / `Pavane` 중 선택하여 즉시 실행 가능하도록, 본 연구의 모든 파이프라인 스크립트는 MIDI 파일 경로를 `config.py` 에서 한 줄 변경하는 것만으로 재사용할 수 있게 설계되어 있다.

### 7.3 Continuous overlap의 정교화

§3.3a에서 continuous overlap $\to$ $\tau = 0.5$ 이진화가 $11.4\%$ 개선을 주었지만, 이는 *단일 고정 임계값*만을 탐색한 것이다. 더 정교한 방향:

1. __Per-cycle 임계값.__ 모든 cycle에 동일한 $\tau$를 쓰지 않고, cycle 별로 고유 $\tau_c$를 학습 가능 파라미터로 두어 $\{\tau_c\}_{c=1}^{K}$를 end-to-end optimization으로 결정한다.
2. __Soft activation을 받아들이는 Algorithm 2 변형.__ 현재 Algorithm 2는 $O[t, c]$를 이진 입력으로 가정하는데, continuous $O_{\text{cont}}[t, c] \in [0, 1]$을 그대로 받아들이는 입력 레이어로 교체한다. 이 경우 모델은 "어느 cycle이 얼마나 강하게 활성인가"라는 더 풍부한 정보를 학습에 쓸 수 있다.
3. __가중치 함수 학습.__ 현재 희귀도 가중치 $w(n) = 1 / N_{\text{cyc}}(n)$은 고정된 휴리스틱인데, 이를 학습 가능 함수로 대체하여 *어떤 가중치가 JS divergence 최소화에 가장 도움이 되는지*를 직접 추정한다.

### 7.4 Tonnetz Hybrid의 $\alpha$ grid search

본 연구는 Tonnetz hybrid의 $\alpha$를 $0.5$ 고정으로 실험했다. 다른 $\alpha$ 값 ($0.0, 0.1, 0.3, 0.5, 0.7, 1.0$) 에 대해 동일 $N = 20$ 반복 실험을 수행하면, "빈도 거리와 음악이론적 거리의 최적 혼합 비율"을 정량적으로 제시할 수 있다. 메모리에 있는 과거 단일 run 실험에서 $\alpha = 0.3$이 가장 좋았다는 힌트가 있으나, 통계적 확인이 필요하다.

### 7.5 Interactive 작곡 도구

현재 파이프라인의 모든 단계는 batch 처리 방식이다. 실시간/상호작용 버전은 다음과 같이 설계할 수 있다:

- 사용자가 GUI에서 **drag-and-drop으로 중첩행렬을 직접 그리면**, 그 중첩행렬로부터 Algorithm 1 또는 2가 즉시 음악을 생성하여 재생
- 사용자가 특정 cycle을 강조/억제하는 슬라이더를 조작하면 생성 결과가 실시간으로 바뀜
- Figure 2의 interactive HTML을 기반으로 확장하여, cycle을 클릭하면 그 cycle만 활성화된 "단색" 생성을 들을 수 있는 모드 추가

이 방향은 본 연구의 결과를 **작곡 보조 도구**로 활용하게 만든다. 전통적으로 TDA는 분석 도구로만 쓰여왔지만, 본 연구의 파이프라인은 "위상 구조를 직접 조작하여 음악을 만드는" 생성 도구로도 기능할 수 있음을 보였다.

### 7.6 위상 구조 보존의 수학적 엄밀화

본 연구의 "보존도 함수" $f(S) = 0.5 J + 0.3 C + 0.2 B$ (§2.7) 는 경험적 선택이다. 향후 과제로는 다음이 있다:

1. __Submodularity 증명 시도.__ 보존도 함수가 submodular라면 Nemhauser 정리에 의해 greedy 근사가 $0.632$-optimal임이 보장된다. 세 구성 요소 중 어떤 것이 submodular인지 분석하고, 비-submodular 요소가 있다면 그것을 대체하거나 penalty로 처리한다.
2. __Bottleneck/Wasserstein distance.__ 보존도의 수학적 자연스러운 정의는 두 persistence diagram 사이의 bottleneck 또는 Wasserstein distance이다. 본 연구의 Jaccard/Correlation/Betti 조합을 이러한 이론적 기반과 연결하는 것이 과제다.

### 7.7 우선순위 정리

| 과제 | 난이도 | 기대 효과 | 우선순위 |
|---|---|---|---|
| 7.1 모듈 단위 생성 + 구조적 재배치 | 중 | 곡의 정체성 보존 + 계산 효율 | __최우선__ |
| 7.2 *out of noise* 앨범 전곡 검증 | 중 | §3.4 가설의 통계적 확증 | 높음 |
| 7.3 Continuous overlap 정교화 | 중 | 추가 $\sim 10\%$ 개선 예상 | 높음 |
| 7.4 Tonnetz $\alpha$ grid search | 낮 | 기존 결과의 robustness 확인 | 중 |
| 7.5 Interactive 작곡 도구 | 중 | 연구 성과의 응용 확장 | 중 |
| 7.6 보존도 함수의 이론적 정당화 | 높 | 이론적 기여 | 장기 |

---

## 8. 결론

본 연구는 사카모토 류이치의 hibari를 대상으로, persistent homology를 음악 구조 분석의 주된 도구로 사용하는 통합 파이프라인을 구축하였다. 수학적 배경 (§2), 두 가지 생성 알고리즘 (§3), 네 거리 함수 및 continuous overlap의 통계적 비교 (§4), 6종의 시각자료 (§5)를 일관된 흐름으로 제시하였다. 핵심 경험적 결과는 Tonnetz 거리가 frequency 대비 pitch JS divergence를 $47\%$ 낮춘다는 것 ($p < 10^{-20}$) 이며, 핵심 해석적 기여는 FC 모델의 우위를 *out of noise* 앨범의 작곡 철학과 연결한 것이다. 가중치 행렬의 intra / inter / simul 분리 설계가 작곡가 본인의 작업 방식에서 유도된 결정이라는 점, 그리고 그 설계가 Figure 7의 관측 (inst 1 쉼 0개 vs inst 2 쉼 64개) 로 경험적으로 정당화된다는 점이 본 연구의 특징적 해석 구조이다.

향후 연구 방향으로는 모듈 단위 생성 + 구조적 재배치 (§7.1) 이 가장 자연스럽고 즉각적인 확장이며, *out of noise* 앨범 전곡으로의 일반화 (§7.2) 가 본 연구의 핵심 가설을 검증할 수 있는 가장 강력한 후속 작업이다.

---

## 감사의 글

본 연구는 KIAS 초학제 독립연구단 정재훈 교수님의 지도 아래 진행되었다. pHcol 알고리즘 구현 및 선행 파이프라인의 많은 부분을 계승하였음을 밝힌다. Ripser (Bauer), Tonnetz 이론 (Tymoczko), 그리고 국악 정간보 TDA 연구 (Tran, Park, Jung) 의 수학적 토대 위에 본 연구가 서 있음을 부기한다.

## 참고문헌

- Bauer, U. (2021). "Ripser: efficient computation of Vietoris–Rips persistence barcodes". *Journal of Applied and Computational Topology*, 5, 391–423.
- Carlsson, G. (2009). "Topology and data". *Bulletin of the American Mathematical Society*, 46(2), 255–308.
- Catanzaro, M. J. (2016). "Generalized Tonnetze". *arXiv preprint arXiv:1612.03519*.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Edelsbrunner, H., & Harer, J. (2010). *Computational Topology: An Introduction*. AMS.
- Endres, D. M., & Schindelin, J. E. (2003). "A new metric for probability distributions". *IEEE Transactions on Information Theory*, 49(7), 1858–1860.
- Hochreiter, S., & Schmidhuber, J. (1997). "Long Short-Term Memory". *Neural Computation*, 9(8), 1735–1780.
- Kingma, D. P., & Ba, J. (2015). "Adam: A method for stochastic optimization". *ICLR*.
- Nemhauser, G. L., Wolsey, L. A., & Fisher, M. L. (1978). "An analysis of approximations for maximizing submodular set functions". *Mathematical Programming*, 14(1), 265–294.
- Nielsen, F. (2019). "On the Jensen–Shannon symmetrization of distances". *Entropy*, 21(5), 485.
- Sakamoto, R. (2009). *out of noise* [Album]. commmons.
- Satterthwaite, F. E. (1946). "An approximate distribution of estimates of variance components". *Biometrics Bulletin*, 2(6), 110–114.
- Tran, M. L., Park, C., & Jung, J.-H. (2021). "Topological Data Analysis of Korean Music in Jeongganbo". *arXiv:2103.06620*.
- Tymoczko, D. (2008). "Set-Class Similarity, Voice Leading, and the Fourier Transform". *Journal of Music Theory*, 52(2).
- Tymoczko, D. (2011). *A Geometry of Music: Harmony and Counterpoint in the Extended Common Practice*. Oxford University Press.
- Tymoczko, D. (2012). "The Generalized Tonnetz". *Journal of Music Theory*, 56(1).
- Vaswani, A., et al. (2017). "Attention is all you need". *NeurIPS*.
- Welch, B. L. (1947). "The generalization of 'Student's' problem when several different population variances are involved". *Biometrika*, 34(1/2), 28–35.
- 이동진, Tran, M. L., 정재훈 (2024). "국악의 기하학적 구조와 인공지능 작곡".
