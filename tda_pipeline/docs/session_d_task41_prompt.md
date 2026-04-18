# 세션 D — Task 41: §6.1~§6.6 재서술 + §8 메타 통찰 (선택지 C)

## 배경

Wave 2(세션 D, 커밋 fcaf2af) 이후 Phase 3 세션 A가 다음 실험을 완료:

1. **Task 38a**(커밋 dafdff3): §7 DFT α=0.25 재수행
2. **Task 38b**(커밋 c548371): §7 전면 재서술
3. **Task 39 Wave 2**(커밋 5fb01b2): solari/Bach/Ravel DFT + §6.4/§6.5 FC·LSTM
4. **Task 39-4 집중**(커밋 b3903ab): §6.4 LSTM "≤0.5% DTW" 실측 검증
5. **Task 40**(커밋 a67977d): §6.3~§6.6 DFT 전환 재실험 (Transformer + FC)

**핵심 발견 (Task 40)**: DFT 전환 시 §6.6 `major_block32`가 Tonnetz 대비 **ref pJS 27배
악화**. §6.9 complex 모드 Tonnetz 한정 유효와 합쳐 "**거리 함수는 음악적 목적에 따라
최적이 다름**"이라는 메타 통찰 형성.

**사용자 결정 (2026-04-17)**: 선택지 **(C) 두 결과 병기 + 메타 통찰 강조** 채택.

본 Task 41은 §6.1~§6.6 + §8 결론을 (C) 방향으로 재서술한다.

## 필수 참조 파일

### 읽을 것

- `memory/project_task39_wave2_findings_0417.md` — §6.1/§6.2/§6.4/§6.5 FC·LSTM
- `memory/project_task39_4_lstm_findings_0417.md` — §6.4 LSTM 교체안 (실측 +0.11~+0.36%,
  retrain O -1.09%)
- `memory/project_task40_section66_findings_0417.md` — §6.3~§6.6 DFT 재실험, 메타 통찰
- `memory/project_task38a_phase3_findings_0417.md` — §7 Task 34b 연동 (§6.9 Tonnetz 한정)
- `memory/project_wave2_d_completed_0417.md` — 기존 Wave 2 반영 상태
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 규칙
- `CLAUDE.md` — 논문-코드 정합성 규칙

### JSON 원본 (수치 대조 필수)

- `docs/step3_data/solari_dft_gap0_results.json` (§6.1)
- `docs/step3_data/classical_contrast_dft_gap0_results.json` (§6.2)
- `docs/step3_data/temporal_reorder_fc_dft_gap0.json` (§6.4 FC)
- `docs/step3_data/temporal_reorder_lstm_dft_gap0.json` (§6.4 LSTM — 주의: 두 실험
  결과 덮어쓰기 가능성. `phase3_task39_4_lstm_summary.json`의 verdict와 교차 확인)
- `docs/step3_data/phase3_task39_4_lstm_summary.json` — Task 39-4 집중 LSTM 판정
- `docs/step3_data/temporal_reorder_transformer_dft_gap0.json` (§6.4 Transformer, Task 40)
- `docs/step3_data/harmony_fc_dft_gap0.json` (§6.5 FC)
- `docs/step3_data/harmony_lstm_dft_gap0.json` (§6.5 LSTM)
- `docs/step3_data/harmony_transformer_dft_gap0.json` (§6.5 Transformer, Task 40)
- `docs/step3_data/combined_AB_dft_gap0.json` (§6.6 Task 40 DFT)
- `docs/step3_data/combined_AB_results.json` (§6.6 Tonnetz 기존, 비교용)
- `docs/step3_data/phase3_task40_section66_dft_summary.json`

### 수정할 것

- `tda_pipeline/docs/academic_paper_full.md`
- `tda_pipeline/docs/academic_paper_portfolio (short).md`
- (선택) PDF 재빌드

### 금지

- `CLAUDE.md` 수정 (Task 41 ✓은 세션 E가 처리)
- 기존 JSON 덮어쓰기
- 소스코드 수정

## 설계 원칙 — (C) 메타 통찰

### 핵심 메시지

> **음악적 목적이 거리 함수의 최적을 결정한다.** 원곡 재현·PH cycle 발견·모듈 단위 생성
> 같은 **"구조 정밀도"** 목적에서는 DFT가 우수하며, scale 제약 변주·화성 공존 보강 같은
> **"화성적 정합성"** 목적에서는 Tonnetz가 우수하다. 두 현상(§6.6 Tonnetz 우위 + §6.9
> complex Tonnetz 한정)은 본 연구의 메타 기여이다.

### 서사 흐름

```
§6.1 solari       : 곡 성격 → 최적 거리 (12-PC는 Tonnetz/freq)
§6.2 classical    : 다양한 곡 → "hibari만 DFT 최적" 확정
§6.3 변주 개요    : "본 장은 Tonnetz 기반" 선언 (메타 통찰 예고)
§6.4 재배치       : FC/LSTM/Transformer 반응 (실증 보강)
§6.5 화성 제약    : scale_major 최적 (FC/LSTM 확장)
§6.6 통합 실험    : §6.6.1 Tonnetz 성공 + §6.6.2 DFT 탐색 실패 → §6.6.3 메타 통찰
§6.9 complex      : Tonnetz 한정 확정 (기존)
§8 결론           : "거리 함수 × 목적" 차원 추가
```

## 작업 범위 — 섹션별 체크리스트

### ① §6.1 solari DFT 열 추가 (T39-2)

- 기존 표: frequency 0.063 / Tonnetz 0.063 / voice_leading 0.078
- **추가**: DFT **0.0824 ± 0.0029 (K=15)**
- 해석: "12-PC 구조에서 DFT 지름 한계 (§4.5.3 연결) — frequency/Tonnetz 최적 유지"
- 기존 §6.1 "solari에서는 frequency와 Tonnetz가 거의 동일" 결론 보강
- short.md: 4거리 표 유지, 해석 1~2줄 추가
- full.md: DFT K=15가 낮은 이유 해석 더 상세

### ② §6.2 classical DFT 열 추가 + "hibari만 DFT 최적" 메타 확정 (T39-3)

- 기존 표: frequency / Tonnetz / voice_leading / 최적
- **추가**: Bach Fugue DFT **0.0951 K=30**, Ravel Pavane DFT **0.0494 K=37**
- 표 갱신 후:
  - Bach Fugue: Tonnetz 0.0408 유지 (DFT 0.0951 악화)
  - Ravel Pavane: frequency 0.0337 유지 (DFT 0.0494 악화)
- **종합 표 "거리 함수 패턴 종합"** 재확인:
  - hibari → DFT (유일)
  - solari / aqua / Bach / Ravel → 기존 최적 거리
- 결론 문장 추가: **"hibari만 DFT가 최적이며, 이는 §4.5의 고유 구조(7-PC diatonic, entropy
  0.974, deep scale)에서 유래한다. 이는 §6.3~§6.6의 Tonnetz 기반 변주 실험 설계의 근거
  중 하나이다."**

### ③ §6.3 변주 개요 — 메타 통찰 예고 신설

§6.3 첫 단락에 다음 취지의 선언 추가:

> 본 §6.3~§6.6은 위상 보존 음악 변주 실험이다. **실험은 Tonnetz 기반으로 수행한다.** 이는
> scale 제약 (§6.5) 과 화성적 이웃 구조가 Tonnetz와 자연스럽게 공명하기 때문이다. §6.6.2
> 에서 DFT 전환을 시도하여 이 판단을 실증적으로 확인한다.

DTW·평가 지표 정의는 기존 유지.

### ④ §6.4 FC / LSTM / Transformer 반응 실증 확장

기존 §6.4는 세 모델의 반응을 정성 서술. 본 Task에서 **실측 수치 추가**:

#### FC (Task 39 T39-4)

- baseline pitch_js = **0.000917** (§6.7.2 FC-cont 수준)
- 재배치 3전략 후 pitch_js 거의 동일 (±0.001 이내)
- DTW 증가는 관측되나 pitch 분포 불변 → **FC 시점 독립성 실증**

#### LSTM (Task 39-4 집중, DTW 검증)

이전 서술 "모든 전략에서 ≤ 0.5%"를 **실측 기반으로 교체**
(memory `project_task39_4_lstm_findings_0417.md` 교체안 활용):

- segment_shuffle (retrain X): +0.11%
- block_permute (retrain X): +0.12%
- markov (retrain X): +0.36%
- segment_shuffle (retrain O): **-1.09%** (초과)

#### §6.4 LSTM 교체 권장 문장 (short.md)

> LSTM: 순환 구조(recurrence)로 과거 문맥을 누적하지만 positional embedding이 없어,
> 재학습 없이 입력 순서만 바뀌는 경우 **DTW 변화가 매우 작다 (3전략 모두 ≤ 0.5%, 실측
> +0.11~+0.36%)**. 재학습을 시도해도 DTW 변화가 약 1.1% 수준에 그쳐, LSTM은 PE 없이는
> 시간 재배치로 선율을 바꾸기에 부적합하다.

#### Transformer (Task 40 T40-1)

기존 Tonnetz 결과 (pJS 0.011, DTW +21.7% 등)는 **full.md에 각주**로 보존. short.md는
**Task 40 DFT 결과로 교체**가 원칙이나, §6.3에서 "본 장은 Tonnetz 기반"을 선언했으므로
§6.4에서 **Tonnetz Transformer 유지 + DFT 수치는 §6.6.2 참조**로 안내 권장. 이 방향이
(C) 메타 통찰과 가장 정합.

### ⑤ §6.5 FC/LSTM 추가 + Transformer Tonnetz 유지 (T39-5, T40-2)

§6.5 기존 Algorithm 2 결과(Tonnetz-Transformer): original/baseline/scale_major/scale_penta
표. 보강 내용:

- **FC·LSTM 수치 추가** (T39-5):
  - FC scale_major: (JSON 확인)
  - LSTM scale_major: (JSON 확인)
- **모델 선택 근거 명시**: FC는 §6.7.2에서 최적, LSTM은 continuous 부적합 — Transformer
  기반 서술이 §6.5에서 여전히 중심이지만 실증 비교 가능
- Transformer DFT 결과(Task 40 T40-2, vs_orig pJS 0.313)는 full.md 각주로만 — §6.6.2
  에서 통합 처리됨
- scale_major 3축(17-3) 내역은 이미 Wave 2에서 반영됨 (확인 후 유지)

### ⑥ §6.6 — **두 결과 병기 + 메타 통찰 (핵심 재구조화)**

#### §6.6.1 Tonnetz 기반 통합 실험 (기존 유지)

- `combined_AB_results.json` (2026-04-11) 기반 major_block32 결과
- ref pJS **0.003**, DTW **2.36 (+31%)**, vs_orig pJS **0.097**, scale_match 1.0
- "위상 보존 + 선율 변화 + 화성 일관성" 3축 균형 = 본 연구 변주의 성공 사례
- **⚠ pre-bugfix 각주 유지**: "본 결과는 2026-04-11 bugfix 이전 Tonnetz baseline. DFT
  전환 실험은 §6.6.2 참조."

#### §6.6.2 DFT 전환 탐색 — 실패 사례 (신규)

- `combined_AB_dft_gap0.json` (Task 40) 기반
- **DFT-Transformer**: ref pJS 0.080 (27배↑), DTW 3.31, vs_orig pJS 0.354
- **DFT-FC**: ref pJS 0.041 (14배↑), DTW 3.30, vs_orig pJS 0.308 — **FC가 Transformer보다
  우수 (§6.7.2 결론 일관)**
- **공통 best setting**: `orig_continuous` (scale_major 변주 효과 소실)
- **판정**: DFT 전환이 모든 축에서 Tonnetz 대비 악화. FC로 바꿔도 Tonnetz Transformer에
  도달 못함.

#### §6.6.3 메타 통찰 — "거리 함수 × 음악적 목적" (신규)

핵심 내용:

- DFT 우위 목적: **구조 정밀도** (§4 원곡 재현, §6.7 per-cycle τ 최저, §7 모듈 단위 생성)
- Tonnetz 우위 목적: **화성적 정합성** (§6.6 scale_major 변주, §6.9 complex 모드)
- scale 제약이 Tonnetz "화성적 이웃 관계"(3도·5도 등)와 공명하기 때문 → 이를 DFT 거리로
  바꾸면 제약과 cycle 구조 사이 정합성 소실
- "단일 거리 함수로 모든 목적을 커버할 수 없다" = 본 연구의 **메타 기여**

#### short.md vs full.md 배분

- **short.md**:
  - §6.6.1 간결 (기존 major_block32 수치 + 각주 1줄 "bugfix 이전 Tonnetz")
  - §6.6.2 간결 (ref pJS 27배 악화 한 줄 + 표)
  - §6.6.3 메타 통찰 박스 (2~3문단)
- **full.md**:
  - §6.6.1 상세
  - §6.6.2 표 전체 (10 조합 × 2 모델)
  - §6.6.3 상세 해석 + §6.9 complex와의 연결

### ⑦ §8 결론 — 메타 통찰 항목 신설

기존 §8 결론에 **새 결론 항목 추가**:

> **6. 거리 함수는 음악적 목적에 따라 최적이 다르다 (메타 통찰).**
> 원곡 재현·모듈 단위 생성과 같은 구조 정밀도 목적에서는 DFT가 우수하며(§4, §6.7, §7),
> scale 제약 변주·화성 공존 보강과 같은 화성적 정합성 목적에서는 Tonnetz가 우수하다
> (§6.6, §6.9). 단일 거리 함수로 모든 음악적 목적을 커버할 수 없으며, 목적과 거리 함수의
> **정합성**이 위상 보존 음악 생성의 중요한 설계 요소이다.

§8 개요에 "거리 함수 × 목적" 짝 표 추가 권장.

## short.md vs full.md 원칙 재확인

- **short.md**: gap_min=3 / gap3 0건 (기존 규칙), Tonnetz 수치는 §6.6.1 한정, 비교는 간결
- **full.md**: 역사적 맥락·과정·각주 허용. §6.6.2 DFT 실패도 상세.
- JSON 원본 대조 필수. 기억에만 의존 금지.

## 산출물 & 커밋

**커밋 분리 권장**:

### 커밋 1 — §6.1·§6.2 DFT 열 추가 + "hibari만 DFT" 확정

```
docs(paper): Task 41-A §6.1/§6.2 DFT 열 추가 — "hibari만 DFT 최적" 확정
```

### 커밋 2 — §6.3 메타 통찰 예고 + §6.4 FC/LSTM 실증 + §6.5 FC/LSTM

```
docs(paper): Task 41-B §6.3 선언·§6.4 세 모델 실증·§6.5 FC/LSTM 확장
```

### 커밋 3 — §6.6 재구조화 (6.6.1/6.6.2/6.6.3) + §8 메타 통찰

```
docs(paper): Task 41-C §6.6 재구조화 + §8 메타 통찰 — "거리 함수 × 음악적 목적"

- §6.6.1 Tonnetz 기반 통합 실험 (기존 major_block32 성공) 유지
- §6.6.2 DFT 전환 탐색 (Task 40 a67977d) 추가 — ref pJS 27배 악화, FC로도 회복 X
- §6.6.3 메타 통찰 신설 — 거리 함수 × 음악적 목적 정합성
- §8 결론 6항 신설: "거리 함수 최적은 목적에 따라 다름" (§6.6, §6.9 vs §4, §6.7, §7)
```

단일 커밋으로 묶어도 OK.

## 검수 체크리스트 (PR 전)

- [ ] §6.1 표에 DFT 열 존재, K=15 표시
- [ ] §6.2 표에 DFT 열 존재, "hibari만 DFT 최적" 문장
- [ ] §6.3에 "본 장은 Tonnetz 기반" 선언 존재
- [ ] §6.4 LSTM 서술이 "≤ 0.5% 실측 +0.11~+0.36%"로 교체됨
- [ ] §6.5 FC/LSTM 수치 표 추가됨
- [ ] §6.6.1 / §6.6.2 / §6.6.3 세 하위 섹션 존재
- [ ] §6.6.2에 DFT-FC 우세 (§6.7.2 일관) 명시
- [ ] §6.6.3 메타 통찰에 §6.9 complex 연결 명시
- [ ] §8 결론 6항 (거리 함수 × 목적) 존재
- [ ] short.md에 `gap_min=3` / `gap3` 문자열 0건
- [ ] 모든 수치 JSON 원본과 소수점 4자리 일치

## 세션 간 병렬 안전성

- 본 Task는 **`academic_paper_*.md` 수정 전용**.
- 병렬 진행 중 세션 A 작업 없음. 완전 단독 실행 가능.
- 세션 E 커밋 분리 원칙 준수.

## 완료 후 세션 E 루틴

Task 41 완료 보고 받으면 세션 E가 처리:

1. 커밋 확인 (Task 41이 자체 커밋하거나 세션 E가 분리 커밋)
2. memory 신설: `project_task41_section6_rewrite_0417.md`
3. `MEMORY.md` 인덱스 1줄
4. `CLAUDE.md` Task 41 ✓ + 최종 상태 표 업데이트
5. **Phase 3 프로젝트 종결 선언** (Task 38a/38b/39/39-4/40/41 모두 완료)

## Task 41 이후 남은 과제

1. **T39-4/5 N=5 반복 재검증** (낮음 — memory 플래그만)
2. **§6.6 재실험 Tonnetz 유지 결정 사후 검토** — bugfix 이후 Tonnetz major_block32 재실험
   여부. (C) 채택으로 "기존 Tonnetz 결과 유지 + pre-bugfix 각주"이면 재실험 불필요.
3. 최종 PDF 빌드 + 제출 준비

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음 + 권한 전체 액세스**.
