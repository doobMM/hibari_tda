# 세션 D — Task 37: §7 baseline 재설정 + §8 결론·초록 최종 통일 + CLAUDE.md 최적 설정

## 배경

Task 35 (§4, 커밋 `9873cdd`) + Task 36 (§6.7~§6.9, 커밋 `8c4e3ae`) 완료. 연구 전체 최저
수치 확정:

- Algo1 최저: **DFT + per-cycle τ (§6.7.1) JS=0.01489±0.0014** (N=20)
- Algo2 최저: **DFT + FC-cont (§6.7.2) JS=0.00035** (N=10, Welch p=1.66e-4)

본 Task 37은 **§7 baseline 교체 + §8 결론 통일 + 초록 최종 통일 + CLAUDE.md "현재 최적
설정" 블록 갱신**을 수행한다.

## 필수 참조 파일

### 읽을 것

- `CLAUDE.md` — "현재 최적 설정" 블록 (L65~L73 근처) + 세션 E 규칙
- `memory/project_phase1_gap0_findings_0417.md`
- `memory/project_phase2_gap0_findings_0417.md`
- `memory/project_phase2b_alpha25_findings_0417.md`
- `memory/project_gap0_dft_integration_0417.md` (결정 1~5)
- `memory/feedback_short_md_gap_comparison_exclude.md`
- JSON 원본 (필요 시):
  - `docs/step3_data/step3_results_gap0.json` (§4.1 DFT baseline)
  - `docs/step3_data/step3_continuous_dft_gap0_results.json` (§4.2 Binary DFT)
  - `docs/step3_data/percycle_tau_dft_gap0_results.json` (§6.7.1 Algo1 최저)
  - `docs/step3_data/soft_activation_dft_gap0_results.json` (§6.7.2 Algo2 최저)
  - `docs/step3_data/alpha_grid_dft_gap0_results.json` (§6.8)

### 수정할 것

- `tda_pipeline/docs/academic_paper_full.md`
- `tda_pipeline/docs/academic_paper_portfolio (short).md`
- `CLAUDE.md` (특별 허용: "현재 최적 설정" 블록만)
- (선택) PDF 재빌드

## 작업 범위

### ① §7 baseline 재설정

§7 전체의 "full-song Tonnetz 0.0488 baseline" 인용을 **DFT baseline**으로 교체:

- §7.2 "baseline full-song Tonnetz JS = 0.0488"
- §7.3 "Full-song Tonnetz (baseline) = 0.0488 ± 0.0040"
- §7.5 baseline full-song JS = 0.0488
- §7.7 "full-song Tonnetz baseline 0.0488"

**교체 방향 결정** (세션 D 판단):

1. **§4.1 DFT baseline 0.0213** (frequency 대비 거리 함수 효과의 baseline)
2. **§6.7.1 DFT + per-cycle τ 0.01489** (파라미터 최적화 + OM 정교화 포함된 현재 최저)

권장: **0.0213 (§4.1 DFT baseline)을 §7의 비교 기준으로**. 이유:
- §7의 목적은 "모듈 단위 생성이 full-song 대비 어떤 위치인가" 비교. full-song이 거리 함수
  효과만 반영한 상태(§4.1)가 공정한 비교.
- 0.01489는 per-cycle τ 등 추가 개선이 포함되어 §7 모듈 생성과 1:1 대비가 어려움.
- 단, 박스 참조로 "(참고: 최종 설정에서는 §6.7.1의 0.01489까지 낮출 수 있음)" 허용.

§7의 module 생성 결과 수치 자체는 **변경 불필요** (P3+C best 등은 거리 함수와 독립). baseline
대비 비율만 재계산 (예: "0.0488의 52.9%" → "0.0213의 X%").

**short.md vs full.md**:
- short: DFT baseline만 사용. Tonnetz 참고 언급 금지.
- full: Tonnetz 기존 결과를 각주로 유지 가능.

### ② §8 결론 전면 통일

기존 §8의 "핵심 경험적 결과" 5개를 최신 수치로 전면 갱신:

1. **거리 함수 선택의 효과**:
   - "DFT 거리가 frequency 대비 **38.2%**, Tonnetz 대비 **56.8%**, voice_leading 대비
     **62.4%** 낮춘다 (hibari, N=20, Phase 1 A1)"
   - 기존 솔라리·Bach Fugue·Ravel Pavane 서술은 유지 (§6.2 내용 일치)

2. **곡의 성격이 최적 모델을 결정**:
   - hibari: FC 최적, entropy 0.974 유지
   - solari: Transformer 유지
   - Phase 2 A9 통계 확정 추가: "hibari+gap=0에서 FC-cont가 Transformer 대비 Welch
     p=1.66e-4로 유의 우위"

3. **위상 보존 음악 변주**:
   - §6.4~§6.6 major_block32 결과 유지

4. **OM의 정교화** (전면 갱신):
   - **per-cycle 임계값 최적화: JS +58.7% (p=2.48e-26, N=20), DFT continuous OM 기반**
   - **continuous overlap 직접 입력: FC-cont +83.9% (p=1.50e-6, N=10)**
   - LSTM은 연속값 입력이 부적합 (유지)
   - §4.1a octave_weight: 기존 −18.8% 수치 대신 DFT 조건 수치로 재작성 (JSON 확인)

5. **미학적 타당성** (유지, QR 코드 링크)

추가 결론 6 (선택): **Complex 모드는 distance-specific** (Tonnetz 한정 유효, DFT에서
p<1e-39 유의 악화) — full.md에만, short.md 생략 가능.

### ③ 초록 최종 통일

Task 35에서 §4 수치는 이미 대부분 갱신됨. 본 Task 37에서 추가 반영:

- Algorithm 1 최종 최저: **§6.7.1 DFT + per-cycle τ JS=0.01489±0.0014** (N=20) ★
- Algorithm 2 최종 최저: **§6.7.2 DFT + FC-cont JS=0.00035** (N=10) ★
- 이론 최댓값 log(2)≈0.693 대비 비율 재계산

**원칙 재확인**:
- short: gap_min=3 문자열 0건. Transformer 조건부 언급 금지(gap=0 FC 우위 단순 서술).
- full: gap3 역사적 맥락 각주 1줄 허용.

### ④ CLAUDE.md "현재 최적 설정" 블록 갱신

현재 내용 (`CLAUDE.md` L65~L73 근처):

```
거리 함수: DFT
Lag: 감쇄 가중 (lag 1~4, w=[0.4, 0.3, 0.2, 0.1])
중첩행렬: continuous activation + per-cycle τ_c 이진화
생성 모델: FC (soft activation 입력)
온도: T=3.0 (빈도 스케일링)
```

**신규 내용으로 교체**:

```
거리 함수: DFT (w_o=0.3, w_d=1.0)
Hybrid α: 0.25 (§6.8 확정, DFT α-hybrid grid)
모드: timeflow (Complex는 Tonnetz 한정 유효 — §6.9 Task 34b 확정)
Lag: lag=1 또는 감쇄 가중 (§4.1c 결과에 따라 — JSON 재대조 후 서술 확정)
중첩행렬: continuous activation + per-cycle τ_c (DFT continuous OM 기반)
생성 모델:
  - Algorithm 1: DFT + per-cycle τ → JS=0.01489±0.0014 (N=20) ★
  - Algorithm 2: FC + continuous 입력 → JS=0.00035 (N=10, Welch p=1.66e-4) ★
gap_min: 0
온도: (JSON 확인 후 서술 — T=3.0 여부)
```

**세션 D 특별 허용 편집**: "현재 최적 설정" 블록은 원래 세션 E 영역 밖. 본 Task 37에서
세션 D가 논문 반영 최종본으로 갱신하는 것이 허용되는 **유일한** 경우.

### ⑤ 완료된 주요 실험 표 (CLAUDE.md L37~L53 근처) — 선택적 갱신

기존 §3.1 거리 함수 비교 수치가 구형. 갱신 권장:

- 기존: `§3.1 거리 함수 비교 (N=20) | DFT 0.0211★ (frequency -38.7%, Tonnetz -56.8%)`
- 신규: `§4.1 거리 함수 비교 (N=20) | DFT 0.0213 (frequency -38.2%, Tonnetz -56.8%, voice_leading -62.4%)`

기타 §3.x 섹션 명이 현재 §4.x로 매핑됐으므로 전반 정리. 단 **본 작업은 선택적** — 필수는
"현재 최적 설정" 블록만.

## 산출물 & 커밋

**커밋 분리 권장**:

**커밋 1 — 논문 최종 통일**:

```
docs(paper): Task 37 §7 baseline + §8 결론 + 초록 최종 통일

- §7 baseline: full-song Tonnetz 0.0488 → DFT 0.0213로 전면 교체
- §8 결론 전면 갱신:
  - 거리 함수 효과 38.2%/56.8%/62.4%
  - OM 정교화: per-cycle τ +58.7% (p=2.48e-26), FC-cont +83.9% (p=1.50e-6)
- 초록 최종: Algo1 최저 0.01489★, Algo2 최저 0.00035★
- short.md: gap3 잔존 0건, complex 수식 0건
- full.md: gap3/Tonnetz 각주 수준 보존
- (선택) PDF 재빌드
```

**커밋 2 — CLAUDE.md 최적 설정 갱신**:

```
chore(claude): Task 37 완료 — 현재 최적 설정 블록 갱신 + 완료 주요 실험 표 정리

- "현재 최적 설정" 블록: DFT + timeflow + per-cycle τ + FC-cont
  - Algo1 최저 0.01489★ (§6.7.1), Algo2 최저 0.00035★ (§6.7.2)
- §3.x → §4.x 매핑 정리, 완료 주요 실험 표 구형 수치 갱신
- Task 37 ✓ 완료 표시
```

## 검수 체크리스트 (PR 전)

- [ ] §7 모든 "Tonnetz 0.0488 baseline" 인용 0건 (short.md), full은 각주만
- [ ] §8 결론 다섯 항 모두 최신 수치로 갱신 + Phase 2 A8/A9 수치 명시
- [ ] 초록 Algo1/Algo2 최저값 0.01489 / 0.00035 기재
- [ ] CLAUDE.md "현재 최적 설정" 블록 신규 내용 반영
- [ ] short.md 내 `gap_min=3` / `gap3` 문자열 0건
- [ ] short.md 내 "Complex" 수식·pilot grid 세부 0건
- [ ] 모든 수치가 JSON 원본과 일치

## 세션 간 병렬 안전성

- 본 Task 37은 **academic_paper_*.md + CLAUDE.md**를 수정.
- 세션 C (최종 WAV 생성) 및 세션 B (잔여 정리) 와 **파일 영역 완전 분리** — 동시 실행 안전.
- 세션 B가 CLAUDE.md를 건드리지 않도록 해당 프롬프트에 명시됨.

## Task 37 완료 후 (세션 E 영역)

- memory에 `project_task37_final_0417.md` 간단 기록 (Task 37 완료 + 최종 최적 설정)
- `MEMORY.md` 인덱스 1줄 추가
- 전체 gap0+DFT 재서술 프로젝트 종결 선언
