# 260419 피드백 — 해석·서술 질문 답변 (수식 포함)

**작성일:** 2026-04-20
**대상:** 260419 피드백 (1).txt 의 해석·서술 질문 26개 중 수식 기반 항목
**관련 파일:** short.md / full.md (LaTeX 제외)

---

## 3. §2.2 — $H_n(K)$가 "개수"인데 왜 아벨 군?

**오해 지점 분리.** "개수"는 $\beta_n = \text{rank}(H_n(K))$이지 $H_n(K)$ 그 자체가 아니다.

- $H_n(K) = \ker(\partial_n) / \text{im}(\partial_{n+1})$은 **chain(선형 결합) 집합의 몫군**. 원소는 "cycle의 동치류"이며, 연산은 **cycle들의 $\mathbb{F}_2$-선형 합**(대칭차).
- $\mathbb{F}_2$ 계수에서 $H_1(K) \cong \mathbb{F}_2^{\beta_1}$이며, $\beta_1$은 이 벡터공간의 차원 = 독립적 cycle의 개수.
- 예: §2.2 예시에서 $\beta_1 = 1$이면 $H_1(K) \cong \mathbb{F}_2$ (원소 2개: trivial class와 nontrivial cycle class), 군 연산은 "두 cycle을 더하면 boundary를 모듈로 하여 같은지 다른지를 판정".

**제안 문구** (§2.2 "$H_n(K)$는 아벨 군이며" 바로 뒤에 한 문장 삽입):

> "엄밀히 말하면 $H_n(K)$의 원소는 개별 구멍이 아니라 $n$-cycle들의 **동치류**(boundary로 차이나는 두 cycle을 같다고 보는 관계)이며, 연산은 cycle의 chain 합이다. 이때 $\text{rank}(H_n(K)) = \beta_n$이 '독립적인 구멍의 개수'를 정의한다."

---

## 7. §2.4 주석 — stability 정리 + path-representable / cost-dominated

Heo–Choi–Jung (2025) "Persistent Homology with Path-Representable Distances on Graph Data" (arXiv:2501.03553) 내용을 확인한 뒤의 정리.

### (a) Stability 정리 (Cohen-Steiner–Edelsbrunner–Harer 2007)

**명제.** 두 filtration을 유도하는 함수 $f, g: K \to \mathbb{R}$에 대해

$$d_B(\text{bcd}(f),\ \text{bcd}(g)) \le \|f - g\|_\infty$$

여기서 $d_B$는 **bottleneck distance**(두 barcode의 최적 매칭 비용).

**음악 맥락 해석.** 거리 행렬을 조금 흔들어도 (예: $w_d$ 미세 조정, noise) barcode는 bottleneck 거리 상 선형 이상 변동하지 않는다. 즉 본 연구의 barcode 기반 비교(§6.8 등)가 소량의 거리 perturbation에 **구조적으로 안정**함을 보장하는 정리.

### (b) Path-representable distance (Heo et al. Def 3.1)

연결 가중 그래프 $G = (V, E, W_E)$에서 "path choice function" $g: V \times V \to \mathcal{P}$를 선택하고, 거리를

$$d(v, w) = \sum_{e \in g(v, w)} W_E(e)$$

로 정의하면 $d$는 **path-representable distance**. $g$의 **consistency**(optimal substructure: $a, b \in g(v, w)$일 때 $g(a, b) \subseteq g(v, w)$ 성립)가 자연스러운 조건.

**대표 예시:** $d_{\text{weight}}$ (최단가중경로), $d_{\text{edge}}$ (최소 edge 수 경로). 본 연구의 완전 그래프 $K_n$ 위 거리 행렬은 **edge direct path** ($g(v, w) = \{(v, w)\}$)로 자명하게 path-representable 처리 가능.

### (c) Cost-dominated 조건 (Heo et al. Def 3.2)

$g$가 **locally cost-dominated by edge $e = (v, w)$**: 모든 대안 경로의 가중치 합이 단일 edge $e$ 이하일 때, 즉

$$W_E(e) \ge \sum_{e' \in g(v, w)} W_E(e').$$

$g(v, w) \ne e$인 모든 edge에서 성립하면 **cost-dominated**.

**해석.** "직접 edge를 쓰는 대신 우회 경로를 선택했다면, 그 우회 경로의 총 가중치가 직접 edge보다 작아야 한다"는 최단경로 직관의 일반화.

### (d) Main theorem (Heo et al. Thm 3.4)

$d_i, d_j$가 **cost-dominated path-representable**이고 $d_i \le d_j$이면, 1-dim barcode 사이에 **순서 보존 단사**

$$\varphi_{i, j}: \text{bcd}_1(d_i) \to \text{bcd}_1(d_j), \quad \varphi([a, b]) = [a, c] \text{ with } b \le c$$

가 존재. (2+ 차원에서는 반례 존재.)

### (e) 본 연구에서의 적용

본 연구의 네 거리는 **완전그래프** $K_n$ 위 edge weight로 주어진다. Path choice function을 "direct single edge"로 고정하면 **$g(v, w) = \{(v, w)\}$이 자명하게 cost-dominated**. 따라서 frequency(metric 공리 위반) 및 dft(identity 위반)도 **1-cycle barcode 비교**에 대해 Thm 3.4가 적용 가능 → **order-preserving injection이 이론적으로 보장**됨. 단 $k \ge 2$ persistence는 정리가 보장하지 않으므로 별도 검증 필요.

이 내용은 §2.4 주석에 이미 반영되어 있으며 (line 176), 현재 서술이 요지를 정확히 담고 있음. PDF 읽기 결과 추가할 부분은 **"1-dim에 한정된 이론이며 $k \ge 2$ persistence는 보장 범위 밖"**라는 점을 명시한 것 정도. 이미 "($k \geq 2$ persistence는 별도 검증 필요)"로 서술 완료.

---

## 14. 정규화 entropy 정의

**Shannon entropy를 이론적 최댓값으로 나눈 값.** §4.5.2 표의 "정규화 pitch entropy"는:

$$H_{\text{norm}}(X) = \frac{H(X)}{\log_2 |X|} = \frac{-\sum_i p_i \log_2 p_i}{\log_2 K}$$

여기서 $K$는 사용된 고유 pitch 수(hibari 17, solari 34, aqua 51), $p_i$는 각 pitch의 곡 내 빈도(전체 note 등장 수로 정규화). $H_{\text{norm}} \in [0, 1]$이며, 1이면 모든 pitch가 균등 빈도로 등장, 0이면 한 pitch만 쓰임.

**hibari 0.974 해석:** 17개 pitch가 거의 균등 빈도 분포를 이루어, 통계적 특이값(자주 쓰이는 한두 음)이 없는 "평탄한 분포". §4.3 FC 우위의 음악적 근거 중 하나.

---

## 18-5. `consonance score` 컬럼 vs `consonance 단독` 행 — 왜 행마다 값 다름?

**현재 서술의 혼동 원인:** "평균 dissonance 지표"라고 할 때 "평균"이 무엇에 대한 평균인지 불명확.

**정확한 정의 (제안 수식):**

- **`consonance score` 컬럼** = 해당 설정으로 생성된 곡 $G$의 **시점별 dissonance의 시간 평균**:

$$\text{cons\_score}(G) = \frac{1}{T} \sum_{t=1}^{T} \text{diss}(\text{chord}_t(G))$$

여기서 $\text{diss}(\cdot)$은 동시 타건 note 쌍의 roughness 평균 (§2.10). 이 값은 **각 설정(scale_major, scale_minor, …)에서 서로 다른 곡이 생성**되므로 행마다 값이 다름.

- **`consonance 단독` 행** = **최적화 목적함수에 $\beta_{\text{diss}} \cdot \text{diss}$만 추가**하고 scale / interval 제약은 없는 특정 설정의 **이름**. 이 행의 `consonance score` 컬럼 값(0.412)은 그 설정으로 생성된 곡에서 사후 측정한 값.

**제안 수정 (§5.5 "핵심 발견 4" 대체):**

> "**`consonance score` vs `consonance 단독`** — 컬럼 `consonance score`는 **생성된 곡의 시점별 평균 dissonance** $\frac{1}{T} \sum_t \text{diss}(\text{chord}_t(G))$로, 각 설정이 만든 다른 곡에서 개별 측정되므로 행마다 값이 다르다. 행 이름 `consonance 단독`은 '최적화 비용에 $\beta_{\text{diss}} \cdot \text{diss}$만 추가(scale / interval 없음)'한 설정 이름으로, 이 설정에서도 note 오차는 $\alpha_{\text{note}}$ 항으로 비용함수에 포함된다."

MD sweep 대상.

---

## 19-1. §5.6.1 "각주 해제 보류 — pre/post-bugfix 간 ref pJS 95% CI 불일치"

**의미 풀이.** 이 각주는 "pre-bugfix 수치(0.0034)와 post-bugfix 수치(0.00710)가 **같은 현상을 측정하는 두 시점인지, 아니면 유의하게 다른 현상인지**"를 판별하기 위한 문구. "각주 해제"는 "pre-bugfix 수치를 참조할 필요가 없다(버그가 무의미했다)"고 선언하는 것. "보류"는 그 선언을 하지 못함을 뜻함.

**95% CI 계산 (post-bugfix, N=10):**

- mean = 0.00710, std = 0.00308
- SE = $0.00308 / \sqrt{10} \approx 0.000974$
- 95% CI $\approx 0.00710 \pm 1.96 \times 0.000974 = [0.00519, 0.00901]$
- Pre-bugfix 0.0034는 이 CI 바깥(아래)에 위치 → **불일치 확정**.

**t-test 직접 수행 결과 추정.** (pre-bugfix 단일 수치 혹은 별도 std가 없어 정확한 t-test 수행 불가) 단, 대표 값 0.0034를 mean, post-bugfix와 비교한 **one-sample t-test**:

$$t = \frac{0.00710 - 0.0034}{0.000974} \approx 3.80 \quad \Rightarrow \quad p \approx 0.004$$

**유의 차이** (p < 0.01).

**결론:** Pre/post-bugfix ref pJS는 통계적으로 유의하게 다르며, bug fix 효과가 실재. 따라서 **"pre-bugfix 수치도 그대로 쓸 수 있다"는 각주 해제는 불가**. 이 각주는 유지되어야 함 (현 서술 그대로).

---

## DFT (1) — "k=5 계수의 magnitude" 정확한 정의

**$|F_5| = |\hat{\chi}_S(5)|$ 맞다.** 엄밀한 정의:

Pitch class 집합 $S \subseteq \mathbb{Z}/12$의 **indicator vector** $\chi_S \in \{0, 1\}^{12}$:

$$\chi_S[p] = \begin{cases} 1 & p \in S \\ 0 & p \notin S \end{cases}$$

이 벡터의 **이산 Fourier 변환(DFT)**:

$$\hat{\chi}_S(k) = \sum_{p=0}^{11} \chi_S[p] \cdot e^{-2\pi i k p / 12}, \quad k = 0, 1, \ldots, 11$$

$k$번째 **DFT magnitude** $|\hat{\chi}_S(k)| = |F_k|$는 복소수 $\hat{\chi}_S(k)$의 절댓값.

- $k = 5$는 $\gcd(5, 12) = 1$이므로 $e^{-2\pi i \cdot 5p / 12}$가 pitch class들을 **완전5도 순환 순서**로 재배열하는 효과. $|F_5|$는 "이 재배열 위에서 집합 $S$가 얼마나 연속 클러스터를 형성하는가"의 척도.

---

## DFT (2) — §4.1b Fourier 계수 구체 예시

**구체 예시.** $S = \{0, 2, 4, 5, 7, 9, 11\}$ (C major diatonic, hibari의 PC 집합):

$$\chi_S = (1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1)$$

$\hat{\chi}_S(k) = \sum_{p \in S} e^{-2\pi i k p / 12}$를 각 $k$에 대해 계산:

- $|F_0| = |S| = 7$ (집합 크기)
- $|F_1| \approx 0.267$
- $|F_2| \approx 1.414$
- $|F_3| \approx 1.0$
- $|F_4| \approx 1.414$
- $|F_5| \approx \mathbf{2.732}$ ← 최대 (5도 순환 연속성)
- $|F_6| = 1$

**대조 예시.** $S' = \{0, 1, 2, 3, 4, 5, 6\}$ (chromatic 연속 7개): $|F_5|$는 훨씬 작은 값. Diatonic이 **5도 순환에서 뭉친 구조**이므로 $|F_5|$가 크게 튄다.

**해석.** DFT 계수는 12개 pitch class 각각에 "단위원 위 $e^{-2\pi i k p / 12}$ 지점에 대응하는 복소수 벡터"를 부여하고, 집합 $S$에 속하는 점들의 벡터 합을 측정. 벡터들이 **서로 정렬**되어 있으면 큰 magnitude, **서로 상쇄**되면 작은 magnitude.

**제안 §4.1b 보강** (현 서술 뒤에 예시 단락 1개):

> "예: C major diatonic $S = \{0, 2, 4, 5, 7, 9, 11\}$의 DFT magnitude는 $(|F_0|, \ldots, |F_6|) \approx (7, 0.27, 1.41, 1.0, 1.41, \mathbf{2.73}, 1)$로, $|F_5|$가 다른 성분 대비 압도적으로 크다. 이는 diatonic이 완전5도 순환 $\{C, G, D, A, E, B, F\}$ 상에서 연속 7개 위치를 차지하기 때문이며, chromatic cluster $S' = \{0, 1, 2, 3, 4, 5, 6\}$에서는 반대로 $|F_1|$이 커진다."

MD sweep 대상 (§4.1b 보강).

---

## DFT (3) — §5.1 "12-PC 전체에서 $|\hat{\chi}(k)| = 0$" 쉽게 바꾸기

**현 문구의 어려움.** "indicator vector가 $(1, 1, \ldots, 1)$에 가까워져"부터 "구조 구별력이 떨어진다"까지 수식 함축이 많음.

**제안 재작성:**

> "pitch class 12개를 모두 사용하는 곡(solari, aqua)에서는 indicator vector가 $(1, 1, \ldots, 1)$이 되어, DFT 계산 시 $k \ne 0$인 모든 계수가 이론적으로 0 — 즉 12개 단위원 벡터의 합이 상쇄되어 사라진다. **모든 PC subset이 거의 같은 DFT magnitude 벡터를 가지게 되므로 '서로 다른 집합을 DFT 거리로 구별할 여지가 사라짐'**이 된다. Hibari처럼 7개 PC만 쓰는 경우에만 indicator vector가 sparse하여 DFT magnitude 차이가 선명히 유지된다."

MD sweep 대상.

---

## 요약

본 파일에 포함된 8개 항목 — 수식이 본격적으로 등장하는 해석/서술 답변.

- 3 (몫군·chain)
- 7 (stability + path-representable + cost-dominated, Heo et al. Thm 3.4)
- 14 (정규화 entropy)
- 18-5 (consonance score 평균 수식)
- 19-1 (95% CI / t-test)
- DFT (1), (2), (3) — Fourier 계수 정의·예시·극한

별도 파일(260419_answers_no_formula.md)에 수식이 거의 없는 18개 항목.
