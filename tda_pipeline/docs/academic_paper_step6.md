## 6. 블록 단위 생성 + 구조적 재배치

본 장은 hibari의 32-timestep 모듈 기반 배치 구조를 직접 활용하여, *한 마디(32 timestep)만 생성한 뒤 hibari의 구조에 따라 배치*하는 접근의 구현과 결과를 보고한다. hibari에서 연구자가 정의한 모듈이란 **A-B-A'-C로 이루어진 반복 선율 단위**(32 timestep = 음악적 4마디)로서 inst 1에서 33회, inst 2에서 32회 반복된다. 

---

### 6.1 구현 설계

### 설계 목표

기존 Algorithm 1은 전체 $T = 1{,}088$ timesteps을 한 번에 생성한다. 본 §6은 이를 **$T = 32$ (한 마디) 생성 + $65$회 복제**로 바꾸어, 다음 세 가지 목적을 달성하려 한다.

1. __계산 효율__ — 생성 시간을 대폭 단축 ($\sim 40$ ms $\to$ $\sim 1$ ms per module)
2. __구조적 충실도__ — *복제*로 hibari의 모듈 정체성(그림 2.9)을 보존
3. __변주 가능성__ — 단일 모듈의 seed만 바꾸면 곡 전체 변주가 자동으로 만들어짐

### 3단계 프로세스

__Step 1 — Prototype module OM 구축.__ Algorithm 1이 모듈 1개를 생성하려면 32개 시점 각각에서 "지금 어떤 cycle이 활성인가"라는 정보가 필요하다. 이 정보를 담는 32행 짜리 prototype OM $O_{\text{proto}} \in \{0,1\}^{32 \times 14}$를 만드는 것이 본 단계의 핵심이다 ($K = 14$, DFT $\alpha = 0.25$ 기반 hibari cycle 수). §6.2에서 4가지 전략을 비교 검증한 뒤 최적안을 채택한다.

__Step 2 — Algorithm 1로 모듈 생성.__ 위에서 만든 $O_{\text{proto}}$ 와 전체 cycle 집합 $\{V(c)\}_{c=1}^{14}$을 입력으로 받아, 길이 $32$ 인 chord-height 패턴 $[4,4,4,3,4,3,\ldots,3]$을 따라 Algorithm 1을 실행한다. 결과는 $32$ timesteps 안의 note 리스트 $G_{\text{mod}} = [(s, p, e)_k]$이다. hibari의 경우 모듈당 약 $45 \sim 60$개 note가 생성되며, 소요 시간은 $\sim 1{-}2$ ms이다.

__Step 3 — 구조적 재배치.__ $G_{\text{mod}}$를 그림 2.9에서 시각적으로 검증된 hibari의 모듈 기반 배치 구조에 그대로 맞춰 배치한다.

---

### 6.2 Prototype module OM 전략 비교

위 Step 1에서 가장 중요한 결정은 "어떤 방식으로 32-row 짜리 prototype OM을 만들 것인가" 이다. 본 절은 네 가지 후보 전략을 정의하고 동일한 $N = 10$ 반복 조건에서 비교한다.

### 네 가지 후보 전략

원본 OM $O_{\text{full}} \in \{0,1\}^{1088 \times 14}$의 전체 $1088$행을 $34 \times 32$로 reshape한 텐서 $\tilde{O} \in \{0,1\}^{34 \times 32 \times 14}$ 위에서 다음 네 가지 prototype을 정의한다. (여기서 **블록**은 음악적 마디 8-step의 4배 단위다.)

**각 전략의 상세 설명:**

P0 (first_block_copy, density ≈ 0.018). 대표 샘플로 시작 시점 $t_{\text{start}}=0$의 32-step 구간($t \in [0,32)$) OM을 prototype으로 사용한다. 가장 단순한 전략으로, inst 1 중심의 초기 구간 활성 패턴을 직접 사용한다.

P1 (OR over 34 blocks, density = 1.0). 34개 블록 중 어느 블록에서라도 한 번이라도 활성이었던 (time, cycle) 셀 전체를 1로 설정한다.

P2 (AND over 34 blocks, density ≈ 0.000). 모든 블록에서 동시에 활성인 셀만 1로 두는 AND 전략. 실측상 원곡 overlap에서 전 블록 공통 활성 셀은 거의 없으므로 density가 실질적으로 0에 가깝다.

__P3 (block OM, density ≈ 0.299).__ 시작 마디 $m$에서 **두 악기 모두 $[32(m+1), 32(m+2))$ 동일 창**을 잘라 block-local PH를 계산한다. $K=14$의 전역 사이클 대신 이 구간에서 재추출한 local cycle (11개 내외)을 사용한다.

### 결과 ($N = 10$ trials)

각 전략 내부의 mean ± std는 prototype 고정, Algorithm 1 seed $N = 10$ 반복 결과이며, P3의 start marker $m$은 본 절에서는 $m=0$으로 고정하고 $m$ 변동 효과는 **§6.5**에서 따로 다룬다.

| 전략 | Density | JS Divergence (mean ± std) | Best trial | Note coverage |
|---|---|---|---|---|
| P0 — first_block_copy | $0.018$ | $0.1040 \pm 0.0219$ | $0.0698$ | $0.809$ |
| P1 — OR | $1.000$ | $0.0621 \pm 0.0167$ | $0.0422$ | $0.800$ |
| P2 — AND | $0.000$ | $0.0900 \pm 0.0308$ | $0.0515$ | $0.809$ |
| P3 — block OM | $\mathbf{0.299}$ | $\mathbf{0.0474 \pm 0.0187}$ | $\mathbf{0.0226}$ | $\mathbf{0.817}$ |

---

### 6.3 한계와 개선 방향

### 한계 — Module-level randomness의 33× amplification

단일 모듈 생성은 32-step chord-height 합산 시 명목상 $\sim 109$개 note slot이 있으나 한 번 타건된 지속 음이 이후 시점의 slot을 점유하여 새 onset 발생을 물리적으로 제한한다. 그러나 시점 $j$에 타건된 duration $d$ 음이 이후 시점 $j+1, \ldots, \min(j+d, T)$ 구간의 slot을 한 개씩 소모하여 해당 시점들의 새 onset 가능 수를 차감한다. 각 choice의 결과가 이후 $33$번 (inst 1) + $32$번 (inst 2) 반복되므로 **한 번의 random choice가 곡 전체에서 65번 반복된다**. 예컨대 만약 특정 희귀 note (label 5, "A6 dur=6" 같은) 가 한 모듈 생성 과정에서 한 번도 선택되지 않으면, 곡 전체에서 그 note가 영구적으로 누락된다.

### 개선 방향

__모듈 수준 best-$k$ selection.__ $k$개의 후보 모듈을 생성한 뒤 각 후보의 **note coverage** (모듈이 포함한 고유 $(\text{pitch}, \text{duration})$ 레이블 개수, hibari 기준 최대 23) 를 평가하여 가장 높은 후보를 선택한다. JS divergence는 선택 이후 곡 전체 replicate 시퀀스에 대해 한 번 계산되며, best-$k$ 루프 내부에서는 사용하지 않는다. $k = 10$ 으로 두면 $\sim 20$ ms 추가 비용으로 분산을 크게 낮출 수 있다. 이는 한계(randomness amplification)에 대한 가장 직접적 대응이다. 추후 연구에서 선택 기준을 *모듈 수준 JS divergence* (예: 후보 모듈과 원곡 해당 마디의 pitch 분포 간 비교) 로 대체하거나 coverage 와 결합하는 방향으로 확장할 수 있다.

---

### 6.4 한계 해결 — P3 / best-10 / 결합 구현 및 평가

§6.3 에서 정의한 개선 방향 중 **best-10, P3** 를 구현하고, 결합 전략 **P3 + best-10**을 포함해 P0 baseline 과 동일 조건 ($N = 10$ 반복, seed $7300 \sim 7309$) 에서 평가하였다.

### 구현 세부

__local OM + best-$k$ selection.__ block-local OM 위에서 best-$k$ selection 을 동시에 적용. P3 은 *"cycle set을 어떻게 만드는가"* 단계(Stage 2-3: topology → prototype OM), best-10는 *"seed를 어떻게 고르는가"* 단계(Stage 4: 생성 후 선택).

### 결과 ($N = 10$, baseline full-song JS $= 0.00902 \pm 0.00170$)

| 전략 | JS Divergence (mean ± std) | best | coverage | per-trial 시간 |
|---|---|---|---|---|
| Baseline P0 ($N=20$) | $0.1082 \pm 0.0241$ | $0.0701$ | $0.787$ | $\sim 2$ ms |
| P3: block OM | $0.0636 \pm 0.0207$ | $0.0335$ | $0.791$ | $\sim 3$ ms |
| __P3 + best-10 ★__ | $\mathbf{0.0417 \pm 0.0145}$ | $\mathbf{0.0167}$ | $0.900$ | $\sim 25$ ms |

__핵심 발견.__

1. __P3 + best-10 가 최우수__: 평균 $0.0417 \pm 0.0145$ 로, P0 baseline ($0.1082$) 대비 $61\%$ 감소. 표준편차도 $0.0241 \to 0.0145$ 로 $40\%$ 감소. Best trial $\mathbf{0.0167}$은 full-song DFT binary OM baseline ($0.0213$, 약 $0.78$배)를 하회하나, §5.8.1 Phase 1 per-cycle τ ($0.01489$) · Phase 2 신기록 ($0.00902$) 대비로는 각각 $+12\%$ · $+85\%$ 열세이다.
2. __개선 조합 효과는 distance-independent__: Tonnetz 조건 P3 + best-10 best $\approx 0.0348$, DFT 조건 $\mathbf{0.0167}$ — 절대값은 달라도 "P3 + best-10이 최적"이라는 서열은 두 거리 함수에서 동일하다.


---

### 6.5 P3의 기준 블록 탐색 — 32개 후보 비교 (DFT)

§6.4의 P3은 대표 시작점 **start marker $m=0$** (분석 구간 $t \in [32, 64)$)의 데이터로 block-local PH를 계산했다. 이 선택의 자의성을 검증하기 위해, DFT $\alpha=0.25$에서 **32개 기준 블록** (start = 0~31, 분석 구간 $[32(m+1), 32(m+2))$) 전체에서 동일한 P3 + best-$k$ 실험을 수행하였다. 각 block의 local PH는 **두 악기 모두 동일 구간**에서 계산된다. 여기서 $k$는 각 seed 내부의 best-$k$ 후보 수($k=10$), $N$은 기준 블록당 독립 반복 횟수($N=10$ seeds)다.

**블록 번호 정의**: $m=0$일 때 분석 구간은 $[32, 64)$로 **원곡 첫 블록 $[0, 32)$와 마지막 블록 $[1056, 1088)$는 본 §6.5 탐색 대상에서 제외**했다. inst 1 혹은 inst 2만 연주되어 추출되는 cycle이 충분하지 않기 때문이다.

### 결과 요약

| start marker $m$ | JS (mean) | best trial |
|---|---|---|
| $13$ | $0.0306 \pm 0.0065$ | $0.01980$ |
| $31$ | $0.0324 \pm 0.0136$ | $0.01531$ |
| $15$ | $0.0363 \pm 0.0105$ | $0.01853$ |
| $0$ | $0.0473 \pm 0.0183$ | $\mathbf{0.01479}$ (seed 9309) ★ |

### 핵심 발견

1. __Best global trial JS = 0.01479 — §5.8.1 Phase 1 기준 동등.__ $m=0$ · seed=9309 조합이 JS $\mathbf{0.01479}$를 달성하였다. §5.8.1 Phase 1 DFT per-cycle τ ($\alpha=0.5$) full-song JS $0.01489$와의 차이 $\mathbf{0.00010}$ — Phase 1 기준 실질 동등. $\alpha=0.25$ 조건의 블록 재탐색은 이미 수행되어 best global JS $= 0.01479$를 달성하였으나, Phase 2 신기록 (JS $0.00902$, $\alpha=0.25$) 대비 $+64.0\%$ 열세이다.

2. __최저 평균 JS($m=13$)와 전역 최저 단일 trial($m=0$)의 불일치.__ $m=13$은 평균이 가장 좋지만 best trial은 0.01980. 반면 $m=0$은 평균이 16위임에도 seed 9309에서 best trial $0.01479$를 기록 — 평균 rank와 별개의 극값(variability)으로 해석된다.

### Best global trial 정보

본 §6.5 전수 탐색에서 **가장 낮은 JS divergence** 는 다음과 같다.

- __설정__: P3 + best-k ($k=10$), start marker $m = \mathbf{0}$, seed $= \mathbf{9309}$, best_j $= 1$
- __블록 내부__: $21$개 unique note 사용 (coverage $21/23 = 91.3\%$), $3{,}575$개 note
- __JS divergence__: $\mathbf{0.01479}$ (§5.8.1 Phase 1 $\alpha=0.5$ per-cycle τ $0.01489$와 차이 $\mathbf{0.00010}$; Phase 2 신기록 $\alpha=0.25$ $0.00902$)
- __의의__: 한 블록을 65회 복제하는 방식이 Algorithm 1의 full-song Phase 1 최고 품질과 **수치적으로 동등**에 도달함을 실증.

---

### 6.6 결론과 후속 과제

본 §6 구현 + 한계 해결 (§6.4) + 기준 블록 탐색 (§6.5) 의 결과로 다음을 주장할 수 있게 되었다.

__블록 단위 생성 + 구조적 재배치는 단순한 효율 트릭이 아니라, 적절한 후처리와 기준 블록 탐색을 결합하면 full-song Algorithm 1 Phase 1 수준과 수치적으로 동등한 품질에 도달한다.__ §6.4 P3 + best-10 평균 JS $0.0417$ (full-song DFT 이진 OM baseline $0.0213$의 $1.96$배), 그리고 §6.5 기준 블록 탐색 전역 최적 trial JS $\mathbf{0.01479}$ — §5.8.1 Phase 1 DFT per-cycle τ ($\alpha=0.5$) 최저 $0.01489$와 차이 $0.00010$으로 Phase 1 기준 동등한 위상구조 충실도를 33배 빠른 생성으로 달성한다. 

__본 연구 전체에 미치는 함의.__ §6 은 본 연구의 "topological seed (Stage 2-3)" 와 "음악적 구조 배치 (Stage 4 arrangement)" 가 서로 직교하는 두 축임을 실증한 첫 사례이다. 단 $3{-}35$ ms 의 블록 생성 속도는 __실시간 인터랙티브 작곡 도구의 가능성__을 열어두며, __한 곡의 topology 를 다른 곡의 arrangement 에 이식하는 topology transplant__같은 새로운 응용을 가능하게 한다.

---
