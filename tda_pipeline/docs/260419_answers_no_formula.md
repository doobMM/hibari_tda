# 260419 피드백 — 해석·서술 질문 답변 (수식 미포함)

**작성일:** 2026-04-20
**대상:** 260419 피드백 (1).txt 의 해석·서술 질문 26개 중 수식이 거의 없는 항목
**관련 파일:** short.md / full.md (LaTeX 제외)

---

## 2. 키워드 검토

현재: `Topological Data Analysis, Persistent Homology, Tonnetz, Discrete Fourier Transform, Music Generation, Vietoris-Rips Complex, Jensen-Shannon Divergence`

**추가 권장** (본 연구의 구별 포인트를 키워드에서 드러낼 수 있는 후보):

- **Overlap Matrix** — 본 연구의 고유 구성물
- **Ryuichi Sakamoto / hibari** — 대상곡·작곡가 (인덱싱·검색 접근성)
- **Music Information Retrieval (MIR)** — 분야 위치 명시
- **Symbolic Music Generation** — Suno/audio 생성과 대비되는 위치 (§7.1 Suno 비교와 정합)
- **Cycle Representative** — PH의 음악적 해석 단위
- **Algorithmic Composition** — 전통 분야명

7개가 많지 않으면 **"Overlap Matrix, Ryuichi Sakamoto, Symbolic Music Generation"** 3개 추가를 최우선 권장.

---

## 5. 후속 과제 추가 — transposition-invariance 증명 + void 의미

두 항목 모두 §8 결론부 "후속 과제" 단락(또는 §4.7 / §4.5.4 인접 각주)에 추가 권장.

1. **Transposition-invariance 증명의 확장.** 2026-04-16 증명(T/I 변환 하 M(f(S)) = M(S)·Π 열 permutation 관계, ω_o = 0 또는 f = T_{12m} 조건) — ExperimentB의 이론적 정당성을 확보. 후속 과제: (a) PLR(parallel/leading-tone/relative neo-Riemannian) 변환 불변성 확장, (b) octave-aware 확장.

2. **Void(H_2 구멍, 3-simplex)의 음악적 의미 해석.** 본 연구는 H_1 중심이나, PH는 H_2(2차원 void, 3-simplex의 경계로 둘러싸인 공동)를 원리적으로 제공한다. 음악 네트워크 위에서 H_2가 어떤 구조(예: 세 cycle이 공유 vertex 없이 얽혀 void를 이루는 상황)를 포착하는지, 그리고 그 구조가 생성 seed로 유용한지 — 후속 과제.

---

## 8. Adaptive threshold

### Part 1 — §2.8 Adaptive threshold는 "사용되지 않는다"?

**실제로는 사용됨.** §2.8의 Adaptive threshold는 **Algorithm 2 inference의 §3.2 Step 3**에 적용되며, 대상 행렬은 T × N (note dimension)의 **sigmoid 출력 행렬 P**다. 사용자 질문의 "continuous OM의 각 cell 값에 대해 threshold를 적용해서 이진화한 경우"(대상: T × K OM)는 **§4.2의 별개 실험**이며 τ ∈ {0.3, 0.5, 0.7} 단일 고정값(adaptive 아님).

두 threshold는 대상·목적이 다른 독립 개념:

| 위치 | 대상 | 값 결정 | 쓰이는가 |
|---|---|---|---|
| §2.8 Adaptive threshold | Algo2 sigmoid 출력 P ∈ R^(T×N) | 원곡 ON ratio (15%) 기준 top-k 동적 | **예** (§3.2 Step 3) |
| §4.2 OM τ | 연속값 OM O_cont ∈ [0,1]^(T×K) | τ ∈ {0.3, 0.5, 0.7} 고정 비교 실험 | 실험으로만 (최종 미채택) |

**권장:** §2.8은 **유지**. 다만 혼동을 줄이기 위해 §2.8 본문 첫 문장을 "추론 시 Algorithm 2의 sigmoid 출력 행렬(T × N)에 대해 고정 임계값 0.5 대신…"으로 대상 행렬을 명시하도록 소폭 수정 권장(이미 본문 후반에 "P ∈ R^(T×N)"로 명시되어 있어 필수는 아님).

### Part 2 — §3.2 Step 3 이름 교체?

"adaptive threshold 결정" → "threshold 결정"으로 바꾸면 **§2.8과 이름이 달라져 혼동**. 오히려 §2.8을 참조하는 교차 참조가 약해짐. **"§2.8 adaptive threshold 적용"** 같은 명시적 참조로 바꾸는 게 더 낫다고 봄. 현재는 그대로 두기 권장.

---

## 10. §3.3 Algorithm 2 "보지 못한 cycle subset도 생성" 뾰족화

현재 문구가 모호한 이유: 무엇을 "못 봤는지"가 막연함.

**제안 대안** (우선순위 순):

1. **"학습 중 접하지 않은 cycle subset 크기(예: 학습 K ∈ {10, 15, 20} → 추론 K = 12)에 대해서도 복원"** — 가장 구체적·검증 가능.
2. **"OM에 subset drop / threshold 변동 augmentation을 적용한 새 입력에도 동일 원곡을 복원"** — 실제 학습 설계를 반영.
3. **"같은 cycle set 위에서의 변형(subset 선택, threshold, 시간 재배치)에 대한 일반화"** — 현재 §3.2 후반 "이 일반화는 ~한정된다" 단서와 정합.

**권장 채택:** 1번. 표의 셀이 짧아야 하므로 **"변형된 subset/threshold OM에도 일반화"** 정도가 적절.

---

## 11. Algorithm 2도 N=5?

**§4.3 실험은 N=10 반복.** short.md line 605: "N = 10 반복", full.md §4.5 동일. §4에서 "§4.3의 평가 지표"는 N=10으로 진행되었고, §4 서두의 "4. 통계적 유의성 — 각 설정에서 Algorithm 1을 N = 20회"는 Algorithm 1 대상 진술. **Algorithm 2는 N=10**.

단, §5.5 Algorithm 2 보강 실험(DFT scale_major)은 **N=5** (short.md line 919). 이건 별도 실험.

**권장 반영:** §4 서두 "4. 통계적 유의성" 단락에 **"Algorithm 2는 학습 시간 고려로 N = 10"** 명시 추가. 본 패치는 MD sweep 대상.

---

## 13. 해석 4 "먼 lag의 시간 상호작용 정보를 흡수" 후속 과제

§4.1c 해석 4의 "이론적 설명은 후속 과제로 남긴다" 부분을 §8 후속 과제 리스트에 통합:

**제안 후속과제 문구:**

> "DFT 거리에서 inter 감쇄 lag 합산이 Tonnetz와 반대 방향(개선)으로 작동하는 이유 — DFT의 pitch class 스펙트럼 표현과 시간 스케일별 상호작용 정보의 정합성에 대한 이론적 설명은 후속 과제로 남긴다."

---

## 17-1. §5.4 LSTM 수치가 DTW?

**맞습니다, DTW입니다.** §5.4 FC 문단이 "pitch JS가 모두 0.000373으로 동일" + "DTW는 baseline 대비 segment +47.8%…"로 pitch JS와 DTW를 분리 서술한 맥락이며, 이어지는 LSTM 문단도 동일 구조의 DTW 변화량. Task 39-4 memory/project_task39_4_lstm_findings_0417.md / Task 42 project_task42_nrepeat_verify_findings_0417.md도 **"LSTM retrain X 세 전략 DTW 변화 ≤ 0.5%"** 로 기록.

**서술 자체는 정확**. 혼동 방지 차원에서 "**DTW 변화가 모두 ≤ 0.5%**"의 "DTW"를 **"(DTW 기준)"**으로 한 번 더 명시하는 소폭 개선 가능.

---

## 17-2. Transition JS의 "note-to-note 전이 분포"는 adjacency matrix에서?

**부분적으로 맞지만 정확한 대응은 아님.**

- **§2.9 W_intra (frequency weight)의 adjacency**: 원곡 안에서 **동일 악기 내 연속 note** 간 전이 횟수 행렬. PH 입력용. **거리 행렬 구축 단계**에서 사용.
- **Transition JS의 "전이 분포"**: **평가 단계**에서 사용. 생성곡 G와 원곡 y 각각에서 **시점별 연속 note 쌍** (n_t, n_{t+1})의 count를 N × N 전이 빈도 행렬로 구성 → 정규화 → JS divergence 계산.

**차이:**

| 구분 | Frequency adjacency (W_intra) | Transition JS |
|---|---|---|
| 대상 | 원곡(PH 입력용) | 원곡 + 생성곡 둘 다 (평가용) |
| 계산 단위 | 악기별 분리 (intra) | 전체 note 시퀀스 |
| lag | inter는 lag 1~4 감쇄, intra는 lag 1 | lag 1 고정 |
| 목적 | 거리 행렬 구성 | 분포 비교 (JS) |

**즉 개념적으로 같은 "전이" 행렬 구조지만 실제 계산은 별도.** 전이 분포를 adjacency matrix "에서 구한다"라기보다 **같은 정의(연속 note 쌍 횟수)를 원곡/생성곡 양쪽에 독립 적용**이 정확.

---

## 17-3. §5.4 "pitch JS가 0.007 → 0.173" — 0.007? 0.011?

**사용자 지적이 맞습니다.** §5.4 맥락은 **§5.4 표의 noPE_baseline pitch JS = 0.011**에서 retrain 후 0.173으로 붕괴했다는 비교가 자연스러움. 0.007은 §5.5 Algorithm 2 baseline의 **vs ref pJS**(재분배된 note를 얼마나 잘 학습했는지) 컬럼으로, 비교 대상이 다름(원곡 기준 vs 재분배 기준).

**권장 수정:** "pitch JS가 0.011 → 0.173" (§5.4 표 noPE_baseline pitch JS 기준). MD sweep 대상.

---

## 18-1. α_note = 0.5, β_diss = 0.3 근거

**결론: 휴리스틱 기본값** (grid search 미수행).

- dist_err 와 diss 는 **단위가 다름**(Tonnetz hop 수 vs [0,1] roughness): 두 항이 비슷한 스케일로 기여하도록 α = 0.5 (주), β = 0.3 (보조) 정도로 설정된 것.
- §5.5 "핵심 발견 3"에서 "consonance 단독은 무효과 — dissonance penalty가 거리 보존 제약에 비해 너무 약한 것으로 추정"이라고 적혀 있어, **β 값의 약함이 실험적으로 관찰**되었음을 인정. 즉 grid search를 안 한 것이 실험의 한계로 암시됨.

**제안 보강:** §5.5 끝에 각주 한 줄 — **"(α_note, β_diss) = (0.5, 0.3)은 두 항의 스케일 균형을 위해 설정한 휴리스틱 기본값이며, grid search는 후속 과제"**. MD sweep 대상.

---

## 18-2. Tonnetz "hop" 정의

**hop = 격자 위 한 단위 edge 이동.** Tonnetz 격자에서 인접 두 pitch class 사이의 edge(단3도 ±3, 장3도 ±4, 완전5도 ±5) 중 하나를 따라 **한 번 이동**하는 것이 1 hop. 격자 거리 d_T는 **최소 hop 수**.

- 예: C → G (완전5도 edge 1개) = 1 hop.
- C → D (완전5도 2번 = C→G→D) = 2 hop. "edge" 개수와 동일하지만 "격자 구조 위에서 방향 제약(±3, ±4, ±5)이 있는 edge"를 강조하기 위해 "hop"으로 부름.

**왜 그냥 "edge"가 아닌가:** 일반 그래프 거리에서 edge는 임의 pair 간 직결이지만, Tonnetz에서는 **±3, ±4, ±5 세 방향만 허용**되는 격자 구조이므로 "hop"이 이 방향 제약을 암시. 사용자가 정확히 구분해준 지점 그대로 — edge보다 더 구조적 함의가 있는 용어.

**제안 각주:** §5.5 dist_err 단위 언급 위치에 "hop = Tonnetz 격자의 (±3, ±4, ±5) 인접 관계 하나를 따라 한 번 이동"을 한 문장 추가. MD sweep 대상.

---

## 18-3. Interval class가 transposition-invariant 재분배 때문?

**네, 정확합니다.** Interval class vector(ICV)는 pitch set의 **모든 pair interval의 multiset**이며, **transposition 하에서 불변**. 즉 같은 pitch 집합을 k 반음 이동(T_k)해도 ICV는 같다.

이 덕분에 "C major {0, 2, 4, 5, 7, 9, 11}"와 "D major {2, 4, 6, 7, 9, 11, 1}"이 같은 interval 구조로 인식됨. Pitch class 자체를 비교하면 두 집합이 달라 보이지만, **ICV로 비교하면 동일**.

**§5.5 interval 제약의 설계 목적:** "원곡과 동일 화성 '모양'을 유지하되, **조성은 자유롭게 이동** 가능"한 재분배를 허용. Transposition-invariance 증명(2026-04-16 Experiment B) 맥락과 정합.

**제안 보강** (§5.5 interval structure 보존 직후 1줄 각주):

> "ICV는 transposition(T_k) 하에서 불변이므로, 이 제약은 조성 이동은 허용하되 화성 구조 자체는 보존하는 재분배를 선호하게 한다."

---

## 20-1. §5.6.3 "cycle 분리"

§5.6.3 서술 "위상 구조 재현(원곡 재현·cycle 분리·모듈 탐색) 목적에서는 DFT가 강점"에서 **"cycle 분리"는 "서로 다른 H_1 cycle을 구조적으로 구별해내는 능력"**을 의미. 구체적으로:

- Tonnetz: 12-PC에서 cycle들이 밀집·겹쳐 자주 구별되지 않음 (§4.5.3 Tonnetz 지름 한계와 연결).
- DFT: k=5 계수의 spectral signature를 통해 서로 다른 pitch class 집합을 **다른 magnitude 벡터로 사상**하므로 cycle 간 구조적 차별화가 강함.

**원곡 재현·모듈 탐색**과 병렬로 "cycle 분리"를 나열한 이유: 이 세 목적 모두 "**다른 구조를 다른 것으로 식별**"하는 능력이 필요하며, DFT가 이 식별력에서 우수하다는 공통점을 강조하려는 것.

**권장 보강** (§5.6.3 첫 줄 인라인 각주):

> "여기서 **cycle 분리**는 서로 다른 H_1 cycle이 거리 공간에서 뚜렷이 구별되어 PH가 별개의 generator로 포착하는 능력을 의미한다 (§4.5.3 Tonnetz 지름 한계 참조)."

MD sweep 대상.

---

## 23-1. §5.8.2의 §4.3 참조 — α = ?

**§4.3 = DFT baseline, α = 0.5** (§5.7이 α grid를 아직 안 돌렸을 때의 기본값).

증거:

- short.md §4.3 line 605의 실험 설정이 "DFT 기반 OM 입력 (w_o = 0.3, w_d = 1.0)"에서 α를 명시하지 않음 → 당시 베이스라인은 α = 0.5 (DFT hybrid의 디폴트).
- §5.7에서 α grid search를 통해 최적 α = 0.25를 **§5.8.1 per-cycle τ 재탐색부터** 적용하였음을 명시 — 이는 §5.8.2 §4.3 실험이 α = 0.5 조건임을 역으로 확인.
- Memory project_phase2_gap0_findings_0417.md 와 Task 51 project_task51_fc_cont_alpha025_0418.md: Task 51은 **"§4.3 FC-cont는 α = 0.5였으므로 α = 0.25로 재실험"** 목적으로 설계됨. → 재확인.

**결론 및 제안.** §5.8.2 표의 "DFT baseline" 레이블은 **α = 0.5** 조건임을 명시해야 함. 비고(Task 51) 각주와도 정합 (Task 51이 α = 0.25 재실험).

**권장 반영:** §5.8.2 첫 문장 / 표 제목 옆에 **"DFT baseline (α = 0.5)"** 명시 추가. MD sweep 대상.

**동일 수정 필요:** §4.3 표 캡션 / §5.8.1 Phase 1 레이블도 "α = 0.5" 명시 강화.

### 연쇄로 — §5.8.1과 §5.8.2의 연속성 확장 가능?

네, **가능하며 이미 Task 51이 그 시도**였음:

- §5.8.1 (Phase 2): Algo1 α = 0.25 per-cycle τ JS = 0.01156 ★
- §5.8.2: Algo2 FC-cont α = 0.25 재실험 JS = 0.00057 (N=10), α = 0.5 0.00035 대비 Welch p = 0.168 (비유의) → **Algo2는 α = 0.5 유지**.

즉 Algo1 Phase 2 (α = 0.25)와 Algo2 최저 (α = 0.5)가 **다른 hyperparameter에서 최적**임이 확인됨. §5.8.1과 §5.8.2가 연속되려면 "**Algo1/Algo2가 다른 α에서 최적인 이유는 K 감소(19→14)에 따라 FC 학습 신호가 줄어들기 때문**"이라는 해석이 필요하며, 이 문장이 §5.8.2 비고(Task 51) 각주에 이미 적혀 있음.

---

## 23-2. Welch p = 0.168 = "α=0.25가 안 좋은 게 비유의"?

**엄밀히는 "α=0.25와 α=0.5의 차이 자체가 통계적으로 유의하지 않다"** 의미:

- 관측: α=0.25에서 JS = 0.00057 ± 0.00046, α=0.5에서 JS = 0.00035 ± 0.00015.
- 수치상 α=0.5가 더 낮음 (개선).
- p = 0.168 > 0.05 → 이 차이가 **통계적으로 유의하지 않음** (random variation으로 설명 가능).
- 결론: α=0.25 FC-cont가 α=0.5 대비 **유의하게 나쁘지도, 유의하게 좋지도 않음**. 따라서 "신기록" 주장 불가.

사용자의 "결과가 좋지 않다는 게 비유의하다는 뜻"은 절반만 맞음 — 더 정확히는 "**α=0.25가 α=0.5 대비 개선을 보이지 않았고, 관측된 수치적 열세도 유의하지 않다**". 그래서 "Algo2 최저는 α=0.5 유지" 결정.

---

## 24. §5.9 표의 complex (DFT) 2~4행 α 값 + Tonnetz r_c 최적

**§5.9 표 현재 세 complex 행 모두 α = 0.25** (Phase 2b 재실험 기반).

근거:

- CLAUDE.md Task 34b project_phase2b_alpha25_findings_0417.md: "α=0.25, r_c ∈ {0.1, 0.3} 모두 A8 대비 p<1e-39로 유의 악화. complex_tonnetz_only_effective 판정 확정"
- §5.8.1 Phase 2 기준 (α = 0.25, JS 0.01156)과 동일 α에서 complex를 추가했을 때의 변화를 측정하는 실험 설계.
- Tonnetz 행(0.0183)도 α = 0.25 (Task 24 project_complex_n20_0415.md B 확정).

**Tonnetz r_c 최적: r_c = 0.1 확정 (N=20).**

- Task 24: B(α = 0.25, ω_o = 0.0, r_c = 0.1) JS = 0.0183 ± 0.0009 ★.
- D(α = 0.5) = 0.0218, E(r_c = 0.3) = 0.0214.
- B vs D/E 모두 p<0.001 유의.

즉 **Tonnetz에서는 α = 0.25 + r_c = 0.1 + ω_o = 0.0이 최적**.

**권장 반영:** §5.9 표 제목 / 첫 줄에 **"모든 complex 행 α = 0.25, Tonnetz 행은 추가로 ω_o = 0.0"** 명시. MD sweep 대상.

---

## 29. §6.4 "개선 P3 — Bar-local PH" 중복 제거

**네, 중복됩니다.** §6.2의 P3 설명과 §6.4 개선 P3 설명이 거의 동일:

- §6.2 P3: "두 악기 모두 [32(m+1), 32(m+2)) 동일 창을 잘라 block-local PH를 계산… 전역 K=14 대신 이 구간에서 재추출한 local cycle (11개 내외)을 사용"
- §6.4 개선 P3: "대상 마디의 데이터로 새로 persistent homology를 계산하는 접근… 전체 K=14 cycle 대신 해당 구간에서 계산한 11개 내외의 local cycle을 사용"

**§6.5 구현 세부의 "개선 P3 — Bar-local persistent homology"도 §6.2와 중복.**

**권장 수정:**

1. §6.4의 "개선 P3 — Bar-local PH" 한 단락 **삭제** (개선 C 단락만 남김).
2. §6.5 구현 세부에서 "개선 P3 — Bar-local persistent homology" 단락은 **§6.2에서 이미 정의됨을 참조**하는 1문장으로 축약 (예: "§6.2에서 정의된 P3 전략을 본 §6.5 한계 해결 프레임에 통합하여 평가한다.").

§6.4 "한계 해결" 맥락에서 개선안의 나열 중 일부로 다시 등장한 것으로 보이나, §6.2에 이미 상세 정의가 있으므로 요점만 남기면 충분. MD sweep 대상.

---

## 33. §8 결론 "핵심 경험적 결과" 최신화 (α=0.5 잔재 제거)

**현 문구 문제:** 항목 4에 "per-cycle 임계값 최적화(§5.8.1, α = 0.5)로 JS +58.7% 개선 후, α = 0.25 재탐색에서…" — α=0.5를 거치는 중간 단계가 길게 남아있어 결과 중심이 아님.

**제안 재작성 (짧고 최종 결과 중심):**

> **핵심 경험적 결과:**
>
> 1. **거리 함수 선택의 효과.** hibari Algorithm 1에서 DFT는 frequency 대비 JS −38.2% (N=20). 곡에 따라 최적 거리 함수는 다름 — aqua·Bach (Tonnetz), Ravel (frequency), solari (Tonnetz≈frequency).
>
> 2. **곡의 성격이 최적 모델을 결정한다.** hibari(diatonic, entropy 0.974) → FC, solari(chromatic) → Transformer.
>
> 3. **본 연구 최저 수치.** Algorithm 1: DFT α = 0.25 per-cycle τ_c 로 **JS = 0.01156 ± 0.00147** (N=20, log 2의 약 1.67%). Algorithm 2: DFT α = 0.5 FC-continuous 로 **JS = 0.00035 ± 0.00015** (N=10, log 2의 약 0.05%). Task 51에서 Algo2의 α = 0.25 재실험은 유의 개선 없음 확인.
>
> 4. **위상 보존 음악 변주.** 화성 제약 + 시간 재배치 + continuous OM 결합으로 원곡과 위상적 유사·선율적으로 다른 변주 생성 (§5.4~§5.6).
>
> 5. **거리 함수 × 음악적 목적의 정합성.** 위상 구조 재현 목적에서는 DFT, scale 제약 변주·화성 일관성 목적에서는 Tonnetz가 유리 (§5.6.1 vs §5.6.2, ref pJS 약 2.28배 차이).
>
> 6. **마디 단위 생성.** §6 P3+C로 한 마디 생성 + 65회 복제 방식이 full-song Algorithm 1 Phase 1 수준(JS 0.01479, §5.8.1 0.01489)과 수치적 동등. 단 Phase 2(0.01156) 미달.
>
> 7. **청각적 타당성 (Q4).** 체계적 청취 실험은 후속 과제로 남김 — QR코드로 데모 제공.

MD sweep 대상.

---

## 요약

본 파일에 포함된 18개 항목 — 짧거나 수식을 거의 쓰지 않는 해석/서술 답변. 별도 파일(260419_answers_with_formula.md)에 수식이 본격적으로 포함된 8개 항목(3, 7, 14, 18-5, 19-1, DFT 3문항) 분리.
