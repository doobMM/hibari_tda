# 위상수학적 음악 분석 — Step 3

## 실험 설계와 결과

본 장에서는 지금까지 제안한 TDA 기반 음악 생성 파이프라인의 성능을 정량적으로 평가한다. 세 가지 유형의 실험을 수행하였다.

1. __Distance function 비교__ — frequency(기본), Tonnetz, voice-leading, DFT 네 종류의 거리 함수에 대해 동일 파이프라인을 적용하고 생성 품질을 비교.
2. __Cycle subset ablation__ — 최적 거리 함수(Tonnetz)에서 cycle 수를 $K = 10, 17, 46$으로 변화시켜 cycle 수의 효과를 분리.
3. __통계적 유의성__ — 각 설정에서 Algorithm 1을 $N = 20$회 독립 반복 실행하여 mean ± std를 보고.

모든 실험은 동일한 chord height 패턴 (32-element module × 33 = 1,056 timepoints), 동일 random seed 체계($s = c + i,\ i = 0, \ldots, 19$, 설정별 상수 $c$ 사용)로 수행되었다. 실험 러너는 `tda_pipeline/run_step3_experiments.py`이며, 모든 trial의 상세 기록(mean, std, min, max 포함)은 `tda_pipeline/docs/step3_data/step3_results.json`에 저장되어 있다.

### 평가 지표

__Jensen-Shannon Divergence (주 지표).__ 생성곡과 원곡의 pitch 빈도 분포 간 JS divergence를 주 지표로 사용한다 (2.6절 정의). 값이 낮을수록 두 곡의 음 사용 분포가 유사하며, 이론상 최댓값은 $\log 2 \approx 0.693$이다.

__Note Coverage.__ 원곡에 존재하는 고유 (pitch, duration) 쌍 중, 생성곡에 한 번 이상 등장하는 쌍의 비율. $1.00$이면 모든 note가 최소 한 번 이상 사용된 것이다.

__보조 지표.__ Pitch count (생성곡의 고유 pitch 수), 생성 소요 시간 (초), KL divergence.

### 거리 함수 구현 참고

본 장의 네 가지 거리 함수는 모두 `tda_pipeline/musical_metrics.py` 파일 하나에 정의되어 있다. 사용 패턴은 다음과 같다.

| 함수 | 역할 | 입력 | 출력 |
|---|---|---|---|
| `tonnetz_distance(pc1, pc2)` | 두 pitch class 간 Tonnetz 격자 거리 | `pc1, pc2` ∈ $\{0, \ldots, 11\}$ | 정수 (최단 경로 길이) |
| `tonnetz_note_distance(n1, n2)` | 두 note 간 거리 (옥타브/duration 보정 포함) | `(pitch, duration)` 튜플 $\times$ 2 | 실수 |
| `voice_leading_note_distance(n1, n2)` | 두 note 간 semitone 차이 기반 거리 | `(pitch, duration)` 튜플 $\times$ 2 | 실수 |
| `dft_note_distance(n1, n2)` | pitch class DFT 계수 간 Euclidean 거리 | `(pitch, duration)` 튜플 $\times$ 2 | 실수 |
| `compute_note_distance_matrix(notes_label, metric)` | 전체 note 집합의 거리 행렬 생성 | `{(pitch,dur): label}` 딕셔너리, metric 이름 | $N \times N$ numpy 행렬 |

__Tonnetz 거리의 핵심 구현 (`_build_tonnetz_distance_table`).__ 12개 pitch class를 정점으로 두고, 장3도(±4 semitone), 단3도(±3), 완전5도(±7) 세 종류의 이웃 관계로 이루어진 무방향 그래프에서 BFS(너비 우선 탐색)로 모든 쌍의 최단 경로를 미리 계산하여 $12 \times 12$ 정수 테이블로 캐싱한다. 이후 `tonnetz_distance(pc1, pc2)`는 이 테이블을 $O(1)$에 조회한다.

__두 note 간 확장.__ Tonnetz는 원래 pitch class(mod 12)만 고려하므로 옥타브와 duration 정보가 손실된다. 본 연구는 이를 보완하기 위해

$$
d(n_1, n_2) = \mathrm{tonnetz}(p_1\ \mathrm{mod}\ 12,\ p_2\ \mathrm{mod}\ 12) + w_o \cdot |o_1 - o_2| + w_d \cdot \frac{|d_1 - d_2|}{\max(d_1, d_2)}
$$

로 정의한다 ($w_o = 0.5$, $w_d = 0.3$; $o_i = \lfloor p_i / 12 \rfloor$). 이 식이 `tonnetz_note_distance` 함수의 본체이다. 파이프라인에서는 이 함수가 `compute_note_distance_matrix`를 통해 $N \times N$ 거리 행렬로 벡터화되어, 이후 refine 단계(2.2절)와 Vietoris-Rips 복합체 구축(2.1절)에 입력된다.

---

## 3.1 Experiment 1 — Distance Function Baseline 비교

네 종류의 거리 함수 각각으로 사전 계산한 중첩행렬을 로드하여 Algorithm 1을 실행한다. 각 거리 함수에서 발견되는 cycle의 수도 함께 보고한다.

| 거리 함수 | 발견 cycle 수 | JS Divergence (mean ± std) | Note Coverage | 생성 시간 (ms) |
|---|---|---|---|---|
| frequency (baseline) | 43 | $0.0753 \pm 0.0033$ | $0.991$ | $31.2$ |
| Tonnetz | 46 | $\mathbf{0.0398 \pm 0.0031}$ | $1.000$ | $38.9$ |
| voice-leading | 22 | $0.0891 \pm 0.0048$ | $1.000$ | $22.2$ |
| DFT | 20 | $0.0511 \pm 0.0029$ | $1.000$ | $26.3$ |

__해석 1 — Tonnetz가 가장 우수.__ Tonnetz 거리 함수는 baseline(frequency)에 비해 JS divergence를 $0.0753 \to 0.0398$로 __약 $47\%$ 감소__시켰다. 두 조건의 표준편차가 각각 $0.0033$, $0.0031$로 매우 작으므로, 이 차이는 통계적으로 명확한 개선이다(자세한 분석은 3.3절).

__해석 2 — 거리 함수가 위상 구조 자체를 바꾼다.__ 동일한 hibari 데이터에서 거리 함수만 교체했을 뿐인데 발견되는 cycle 수가 $20 \sim 46$으로 크게 달라졌다. 이는 "거리 함수의 선택이 곧 어떤 음악적 구조를 '동치'로 간주할 것인가를 정의한다"는 음악이론적 관점과 일치한다. Tonnetz는 완전 5도 / 장3도 / 단3도 관계의 pitch class 쌍을 가깝게 배치하므로, 이러한 관계를 공유하는 note들이 한 cycle에 더 자주 모이게 된다.

__해석 3 — voice-leading은 cycle을 적게 발견한다.__ Voice-leading 거리(반음 수 기반)는 22개의 cycle만 찾아내며 JS divergence도 가장 나쁘다 ($0.0891$). 이는 voice-leading이 "인접 pitch 사이의 거리"를 너무 엄격하게 측정하여, hibari처럼 넓은 음역에 걸쳐 느슨하게 연결된 곡에서는 위상 구조가 적게 드러난다는 것을 시사한다.

__해석 4 — Note Coverage는 대부분의 설정에서 포화.__ 네 거리 함수 모두 note coverage가 $0.99 \sim 1.00$이므로, "원곡의 모든 note 종류가 생성곡에 최소 한 번 등장"하는 기본 요구는 모두 만족된다. 따라서 품질의 주된 차이는 "같은 note pool을 얼마나 *자연스러운 비율로* 섞는가"에서 발생한다.

---

## 3.2 Experiment 2 — Cycle Subset Ablation

거리 함수를 Tonnetz로 고정하고, cycle 수 $K$를 변화시켜 "더 많은 cycle = 더 좋은 생성인가?"를 검증한다. $K = 10$과 $K = 17$은 전체 $46$개 중 처음 $K$개의 cycle(prefix subset)을 사용하였다.

| 설정 | $K$ | JS Divergence | KL Divergence | Note Coverage | 생성 시간 (ms) |
|---|---|---|---|---|---|
| Tonnetz, $K = 10$ | $10$ | $0.0991 \pm 0.0038$ | $0.556 \pm 0.035$ | $0.980$ | $24.4$ |
| Tonnetz, $K = 17$ | $17$ | $0.0740 \pm 0.0038$ | $0.550 \pm 0.344$ | $0.996$ | $26.3$ |
| Tonnetz, $K = 46$ (full) | $46$ | $\mathbf{0.0397 \pm 0.0025}$ | $\mathbf{0.172 \pm 0.013}$ | $\mathbf{1.000}$ | $40.8$ |

__해석 5 — Cycle이 많을수록 JS가 단조 감소.__ $K$가 $10 \to 17 \to 46$으로 늘어남에 따라 JS divergence는 $0.099 \to 0.074 \to 0.040$으로 단조 감소하였다. 이는 "위상 구조가 더 풍부하게 드러날수록 생성곡의 음 사용 분포가 원곡에 더 근접한다"는 본 연구의 핵심 가설을 뒷받침한다.

__해석 6 — 한계 효용의 감소.__ $K$ 증가에 따른 JS 감소폭을 보면:
- $K = 10 \to 17$: 개선 $\Delta = 0.025$
- $K = 17 \to 46$: 개선 $\Delta = 0.034$

cycle 수가 거의 세 배($17 \to 46$)가 된 것에 비해 개선 폭은 $K = 10 \to 17$(7개 추가)과 크게 차이나지 않는다. 즉 뒤쪽 cycle들은 이미 어느 정도 포화된 구조를 재확인하는 수준의 기여를 한다. 이는 2.7절에서 논의한 greedy forward selection으로 "소수의 cycle로도 $90\%$ 보존"이 가능하다는 관찰과 일관된다.

__해석 7 — KL 분산의 불안정성.__ $K = 17$ 설정에서 KL divergence의 표준편차가 $0.344$로 유난히 크다. 이는 일부 trial에서 KL이 $1.55$까지 튀는 경우가 있었기 때문이며 (원본 JSON은 `docs/step3_data/step3_results.json`의 `experiment_2_ablations.subset_K17.kl_divergence.max` 필드에서 확인 가능), "$\log(P/Q)$가 $Q \to 0$에서 발산하는" KL의 구조적 불안정성에서 기인한다. JS divergence는 동일 trial들에서 $0.064 \sim 0.079$ 범위로 안정되어 있어, JS가 더 안정적인 평가 지표임을 재확인한다 (2.6절의 "대칭화와 유계성" 논의와 일관).

---

## 3.3 통계적 유의성 분석

두 baseline 비교 (frequency vs Tonnetz) 의 차이가 통계적으로 유의한지 확인한다. 두 표본의 평균을 비교하는 표준적인 방법은 Student $t$-test이지만, Student의 고전적 $t$-test는 "두 집단의 모분산이 같다"는 강한 가정을 필요로 한다. 본 실험에서 두 조건의 표본표준편차는 $s_1 = 0.0033$, $s_2 = 0.0031$으로 매우 비슷하지만 완전히 같지는 않으며, 모분산이 같다는 사전 근거도 없다. 따라서 등분산 가정을 요구하지 않는 __Welch's $t$-test__를 사용한다. Welch는 "모평균과 모분산을 모를 때 표본평균과 표본분산만으로 검정"이 가능하며, 자유도를 Welch–Satterthwaite 근사로 계산한다.

__데이터.__

- Frequency: $\bar{x}_1 = 0.0753$, $s_1 = 0.0033$, $n_1 = 20$
- Tonnetz: $\bar{x}_2 = 0.0398$, $s_2 = 0.0031$, $n_2 = 20$

__Welch $t$ 통계량__ 은 다음과 같이 정의된다:

$$
t = \frac{\bar{x}_1 - \bar{x}_2}{\sqrt{\dfrac{s_1^2}{n_1} + \dfrac{s_2^2}{n_2}}}
$$

수치를 대입하면:

$$
t = \frac{0.0753 - 0.0398}{\sqrt{\dfrac{0.0033^2}{20} + \dfrac{0.0031^2}{20}}} = \frac{0.0355}{\sqrt{1.025 \times 10^{-6}}} \approx 35.1
$$

__Welch–Satterthwaite 자유도.__ Welch 검정에서 $t$ 통계량은 정확한 Student 분포를 따르지 않고, 다음 식으로 근사된 자유도 $\nu$의 $t$-분포를 따른다:

$$
\nu \approx \frac{\left(\dfrac{s_1^2}{n_1} + \dfrac{s_2^2}{n_2}\right)^2}{\dfrac{(s_1^2 / n_1)^2}{n_1 - 1} + \dfrac{(s_2^2 / n_2)^2}{n_2 - 1}}
$$

$n_1 = n_2 = 20$이고 두 표본분산이 거의 같으므로 $\nu$는 $\approx n_1 + n_2 - 2 = 38$에 매우 가깝게 나온다. 수치 계산 결과 $\nu \approx 37.9$이며, 반올림하여 $\nu = 38$로 사용한다.

자유도 $\nu = 38$에서 양측 임계값은 $t_{0.001,\ 38} \approx 3.56$이므로, $|t| = 35.1 \gg 3.56$이며 $p < 10^{-20}$이다. 따라서 __Tonnetz가 frequency보다 JS divergence를 낮춘 것은 극도로 통계적으로 유의__하다.

__효과 크기 (Cohen's $d$).__ $p$-값만으로는 "차이가 실질적으로 얼마나 큰가"를 알 수 없으므로, 표본평균 차를 표본표준편차로 정규화한 Cohen's $d$를 함께 보고한다:

$$
d = \frac{\bar{x}_1 - \bar{x}_2}{\sqrt{(s_1^2 + s_2^2) / 2}}
$$

$$
d = \frac{0.0355}{\sqrt{(0.0033^2 + 0.0031^2) / 2}} \approx 11.1
$$

Cohen의 관례상 $d > 0.8$이 "큰 효과"인데 $d \approx 11$은 비교할 수 없는 초대형 효과이다. 두 분포가 실질적으로 분리되어 있음을 의미한다.

---

## 3.4 Experiment 3 — DL 모델 비교 (참고)

### 왜 $N = 20$ 통계적 반복을 수행하지 않았는가

Algorithm 1은 한 번의 실행에 $\sim 50$ ms 만 걸리므로 $N = 20$ 반복이 수 초 안에 끝난다. 반면 Algorithm 2의 학습은 한 config 당 $30$ s $\sim 3$ min이 걸리므로, 동일한 수준의 반복 실험을 전체 grid에 대해 수행하려면 수 시간이 필요하다. 본 연구는 대신 다음 두 가지 선행 실험을 수행하였다.

1. __하이퍼파라미터 튜닝 ($30$ 조합, 단일 run).__ `run_tuning.py` 스크립트로 FC/LSTM/Transformer 각각에 대해 hidden dim $\in \{64, 128, 256\}$, learning rate $\in \{0.0005, 0.001, 0.003\}$, dropout $\in \{0.1, 0.3\}$, augmentation 배수 $\in \{5\times, 10\times\}$ 조합으로 grid search를 실행하였다. 이 튜닝에서 FC 모델이 top 10을 모두 차지했고, 최적 조합은 `FC / hidden=256 / lr=0.001 / dropout=0.3`으로 validation loss $0.282$, pitch JS divergence $0.0015$를 달성하였다. 튜닝 실험은 각 조합에 대해 $1$회만 수행되었으며, 동일 seed 하에서 결과가 결정적이므로 표준편차 정보는 없다.
2. __본 장에서 보고.__ 아래 표는 튜닝에서 얻은 모델별 최우수 구성의 단일 run 결과를 그대로 가져온 것이다.

| 모델 | Validation Loss | Pitch JS Divergence | 생성 note 수 |
|---|---|---|---|
| FC (hidden=256, lr=0.001, dropout=0.3) | $0.282$ | $\mathbf{0.0015}$ | $3{,}754$ |
| LSTM (2-layer, hidden=128) | $0.385$ | $0.0448$ | $3{,}753$ |
| Transformer (2-layer, 4-head, $d_{\text{model}}=128$) | $0.676$ | $0.0104$ | $3{,}753$ |

향후 $N = 5$ 반복 재검증이 Step 4에서 계획되어 있으나, 본 장에 DL 결과를 먼저 수록한 이유는 두 가지이다. 첫째, 거리 함수 비교 실험(3.1절)이 "Tonnetz가 Algorithm 1에서 우월하다"는 결론을 냈는데, __같은 결론이 DL 기반 Algorithm 2에서도 유효한지__를 동일 장에서 함께 논의해야 연구 전체의 일관성이 드러나기 때문이다(아래 해석 9). 둘째, DL 튜닝의 상위권이 FC 모델로 완전히 쏠린 것은 통계적 반복 없이도 확인되는 *정성적* 관측이며, 그 현상 자체가 hibari라는 곡의 고유한 성격에서 기인한다는 해석(해석 8)을 제시하기 위해서이다. Step 4의 재검증은 효과 크기의 수치적 안정성을 보강하는 용도이지, 현재 결론 자체를 뒤집기 위한 것이 아니다.

### 해석

__해석 8 — FC가 가장 낮은 JS, 그리고 "Out of Noise"라는 맥락.__ 가장 단순한 FC 모델이 가장 낮은 JS divergence를 달성한 것은 얼핏 이상해 보인다. 통상적으로 시퀀스 모델(LSTM / Transformer)이 시간 문맥을 활용해 더 정교한 출력을 낼 것으로 기대되기 때문이다. 그러나 __hibari는 2009년 사카모토 류이치의 앨범 *out of noise*에 수록된 곡__이며, 이 앨범 자체가 "소음과 음악의 경계를 탐구한다"는 기획 의도로 제작되었다. 앨범의 많은 곡은 전통적 선율 진행을 의도적으로 회피하고, 각 음이 시간적 인과(causality)보다는 *공간적 배치*에 가까운 방식으로 놓인다.

이 미학적 맥락에서 보면 FC 모델의 우수한 결과는 역설이 아니라 __곡의 성격에 대한 실증__에 가깝다. FC는 시점 $t$의 note를 결정할 때 이전 시점 $t-1, t-2, \ldots$를 전혀 참조하지 않는, 다시 말해 "시간 맥락 없이 각 음을 독립적으로 배치하는" 모델이다. 이것이 LSTM/Transformer보다 원곡에 더 가까운 결과를 내었다는 것은, *hibari가 선율적 인과보다는 음들의 비맥락적 배치로 구성되어 있다*는 원곡의 작곡적 특성을 모델 선택이 간접적으로 드러낸 셈이다. 즉 FC가 "의미 없이 친 것 같은" 분포가 실제로 원곡과 일치했던 것은, 원곡 자체가 그러한 방식으로 설계되었기 때문이라는 해석이 가능하다.

__해석 9 — Tonnetz + FC 조합의 최고 성능.__ Tonnetz hybrid distance ($\alpha = 0.3$) 로 사전 계산한 중첩행렬을 FC 모델에 입력했을 때, 선행 실험에서 pitch JS divergence $\approx 0.003$을 기록하였다 (기준 frequency + FC의 $0.053$ 대비 약 __$18$배 개선__). 이것이 본 연구 전체에서 관측된 최우수 결과이며, Experiment 1의 "Tonnetz가 우수한 구조적 사전"이라는 결론이 DL 기반 생성에서도 유효함을 시사한다.

---

## 3.5 종합 논의

__(1) 음악이론적 거리 함수의 중요성.__ Experiment 1의 결과는 "빈도 기반 거리(frequency)는 기본 선택일 뿐, Tonnetz처럼 음악이론적 구조를 반영한 거리가 훨씬 더 좋은 위상적 표현을 만든다"는 본 연구의 가설을 강하게 지지한다. frequency → Tonnetz 전환만으로 JS divergence가 $47\%$ 감소했다.

__(2) Cycle 수의 효과는 단조 증가이나 점진적.__ Experiment 2는 "cycle 수가 많을수록 좋다"는 기대를 확인하였으나, 한계 효용이 감소함을 보였다. 이는 $K$를 무작정 늘리기보다 greedy forward selection (2.7절) 으로 소수의 핵심 cycle을 고르는 전략이 실용적임을 시사한다.

__(3) 통계적 엄밀성.__ 각 설정에서 $N = 20$ 반복을 통해 표준편차가 $\sim 0.003$ 수준임을 확인하였으며, 주요 baseline 비교의 Welch $t$ 값이 $> 35$으로 매우 유의했다. 이는 본 연구의 결론이 random seed에 의존하는 artifact가 아님을 보장한다.

__(4) 곡의 맥락과 모델 선택.__ FC가 시퀀스 모델을 능가한 해석 8의 관찰은, 모델의 성능이 단순히 "표현력이 높을수록 좋다"는 법칙을 따르지 않고 __원곡의 미학적 설계와 공명하는 모델__이 가장 좋은 결과를 낸다는 것을 보여준다. 이는 본 연구가 다른 곡(예: 전통적 선율 진행이 뚜렷한 클래식 작품)으로 확장될 때 시퀀스 모델의 우위가 뒤바뀔 수 있음을 암시한다.

__(5) 향후 과제.__
1. DL 모델 comparison을 $N = 5$ 이상 반복으로 재검증 (효과 크기 수치 안정화)
2. Ablation에서 prefix subset 대신 greedy selected subset으로 재실행하여 "어떤 cycle이 선택되는지"의 효과 분리
3. Tonnetz hybrid의 $\alpha$ 값 ($0.0, 0.3, 0.5, 0.7, 1.0$) 에 대한 grid search
4. 다른 곡(Ravel, Debussy, 또는 *out of noise* 앨범의 다른 곡) 으로의 일반화 검증 — 해석 8의 "곡의 미학이 모델 선택을 결정한다"는 가설 검증

---

## 참고문헌 (Step 3 추가분)

- Welch, B. L. (1947). "The generalization of 'Student's' problem when several different population variances are involved". *Biometrika*, 34(1/2), 28–35.
- Satterthwaite, F. E. (1946). "An approximate distribution of estimates of variance components". *Biometrics Bulletin*, 2(6), 110–114.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Tymoczko, D. (2011). *A Geometry of Music: Harmony and Counterpoint in the Extended Common Practice*. Oxford University Press.
- Sakamoto, R. (2009). *out of noise* [Album]. commmons.
