# 세션 D — Task 38b: §7 전면 재서술 (DFT α=0.25 재수행 반영)

## 배경

Task 38a 완료 (커밋 `dafdff3`, 2026-04-17). §7 DFT α=0.25 전면 재수행 결과로 §7.1~§7.8
전체 재서술 필요. 특히 **§7.7(first-module 우위)과 §7.8(Pearson 상관)의 기존 주장이
Tonnetz distance-specific 현상으로 확정**되어 서사 반전이 불가피.

결과 요약: `memory/project_task38a_phase3_findings_0417.md` 참조.

핵심 변화:
- **K = 42 → 14** (§7.1 수식 변경)
- **Prototype 전략 서열 유지** (P3 여전히 best)
- **P3+C best JS 0.0250** (기존 P4+C 0.0258과 근접)
- **first-module 우위 미재현** (rank=5, §7.7 반전)
- **Pearson(W, JS) 0.503 → −0.054** (§7.8 반전)
- **best global JS=0.01479** (§6.7.1 0.01489와 거의 동등 — 모듈 ≒ full-song 달성)

## 필수 참조 파일

### 읽을 것

- `memory/project_task38a_phase3_findings_0417.md` — 본 Task 전체 지침 요약
- `memory/project_phase2_gap0_findings_0417.md` — Phase 2 맥락 (per-cycle τ 0.01489)
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 규칙
- `CLAUDE.md` — 논문-코드 정합성 규칙 (JSON 원본 대조 필수)
- JSON 원본 (수치 갱신 전 반드시 직접 확인):
  - `docs/step3_data/step71_prototype_om_dft_gap0.json` (K=14)
  - `docs/step3_data/step71_prototype_comparison_dft_gap0.json` (§7.2)
  - `docs/step3_data/step71_module_results_dft_gap0.json` (§7.3)
  - `docs/step3_data/step71_improvements_dft_gap0.json` (§7.5)
  - `docs/step3_data/section77_experiments_dft_gap0.json` (§7.7)
  - `docs/step3_data/step_barcode_dft_gap0.json` (§7.8)
  - `docs/step3_data/phase3_task38a_dft_gap0_summary.json` (통합)

### 수정할 것

- `tda_pipeline/docs/academic_paper_full.md`
- `tda_pipeline/docs/academic_paper_portfolio (short).md`
- (선택) PDF 재빌드

### 읽지 말 것

- 소스코드 (`*.py`)
- Tonnetz 기반 기존 JSON(덮어쓰기 금지)

## 핵심 수치 (JSON 재확인 필수 — 아래는 참고용 요약)

| 섹션 | 신규 수치 | 출처 JSON |
|---|---|---|
| §7.1 K | **K = 14** (α=0.25) | `step71_prototype_om_dft_gap0.json` |
| §7.2 P0 | 0.1040 ± 0.0219 (N=10) | `step71_prototype_comparison_dft_gap0.json` |
| §7.2 P1 | 0.0621 ± 0.0167 | 동 |
| §7.2 P2 | 0.0900 ± 0.0308 | 동 |
| §7.2 **P3 ★** | **0.0474 ± 0.0187** | 동 |
| §7.3 P0 본 실험 (N=20) | 0.1082 ± 0.0241, best seed 7105 JS=0.0701 | `step71_module_results_dft_gap0.json` |
| §7.5 **P3+C best** | **0.0440 ± 0.0158**, best trial **0.0250** | `step71_improvements_dft_gap0.json` |
| §7.7 first-module rank | **5** (기존 1에서 반전) | `section77_experiments_dft_gap0.json` |
| §7.7 best global | start=1, seed=9309, **JS=0.01479** | 동 |
| §7.8 **Pearson(W,JS)** | **−0.054** (기존 0.503에서 반전) | `step_barcode_dft_gap0.json` |

## 작업 범위 — 섹션별 체크리스트

### ① §7.1 구현 설계

- 수식 `O_proto ∈ {0,1}^{32 × 42}` → `O_proto ∈ {0,1}^{32 × 14}`로 교체.
- "K=14 (DFT α=0.25 기반 hibari cycle 수)" 명기.
- §7.1 도입부 "full-song 대비" 설명에서 baseline은 DFT 0.0213 기준 (Task 37에서 이미
  교체됨 — §7에도 일관 적용).

### ② §7.2 Prototype module overlap 전략 비교

- 표 4종 전부 DFT 수치로 교체 (P0 0.1040 / P1 0.0621 / P2 0.0900 / **P3 0.0474 ★**).
- 핵심 발견: "**P3 (module-specific)의 우위는 거리 함수에 robust**" 명시 — Tonnetz에서도
  best였고 DFT에서도 best.
- 기존 Tonnetz JS 구체 수치는 short.md에서 삭제, full.md에서는 각주로 비교 가능.

### ③ §7.3 본 실험 결과

- 사용 전략 확인 (P0 또는 P3 중 어느 쪽?). §7.3 원문에 "P0 전략 사용"이면 P0 수치
  (0.1082) 사용. P3으로 변경 제안도 고려 가능.
- best seed 7105 JS=0.0701로 교체.
- §7.3 베이스라인 비교: "full-song DFT 0.0213 대비 X.X배" 재계산.

### ④ §7.4 한계와 개선 방향

- 수치 업데이트 외에 본문 수정 크지 않음. 기존 "33× amplification" 논리 유지.
- §7.5로 자연스럽게 연결.

### ⑤ §7.5 개선 C/D/P3/P3+C

- 표 수치 교체 (P3+C best 0.0440 ± 0.0158).
- **best trial JS 0.0250** 강조 — 기존 P4+C best 0.0258과 근접.
- 해석 추가: **개선 조합 효과는 distance-invariant**로 관찰됨 (Tonnetz P4+C ≈ DFT P3+C).
- "P4 + C → P3 + C"로 명명 변경 여부 확인 (Task 38a에서 P3+C로 명명).

### ⑥ §7.6 결론과 후속 과제 — 결론 강화

- 기존 "잘 만든 모듈 1개를 33번 복제하는 것이 full-song 생성과 비교 가능"을
  **최신 수치로 재강조**:
  - T38a-5 best global trial JS = **0.01479**
  - §6.7.1 per-cycle τ full-song JS = 0.01489
  - 차이 0.00010 — 사실상 동등. 오히려 모듈 쪽이 소폭 낮음.
- "Algorithm 1 연구 전체 최저 0.01489(full-song, §6.7.1)에 모듈 단위 best trial이
  **수치적으로 도달**" 명시.

### ⑦ §7.7 시작 모듈 선택 정당성 — **서사 반전**

**기존**: "첫 모듈의 예외적 우수성" — hibari 32-timestep 모듈 구조에서 첫 모듈이
음악이론적으로 특별.

**신규 (DFT)**: **first-module rank=5** → 첫 모듈의 예외적 우수성 **미재현**.

#### short.md

- 기존 "첫 모듈의 예외적 우수성" 주장 **완전 삭제** 또는 **크게 약화**.
- 대안 서술: "best global trial이 JS 0.01479로 §6.7.1 full-song per-cycle τ와 동등한
  품질을 달성. 시작 모듈 선택에 따른 분산은 있으나 특정 모듈이 일관되게 우수하지는
  않음."
- §7.7 제목도 "시작 모듈 선택 정당성" → "시작 모듈 탐색" 같이 중립화 가능.

#### full.md

- 기존 Tonnetz 결과 "first-module rank=1 우수성"을 **조건부 유지** — "Tonnetz α=0.5
  조건에서는 관측되었으나 DFT α=0.25에서는 미재현. distance-specific 현상."
- 메타 통찰 한 문단 추가: "거리 함수 선택이 단순한 수치 차이뿐 아니라 **모듈 기반
  생성의 구조적 특성**까지 변경함."
- 33 vs 65 기준: Task 38a는 33 기준. 피드백 #22(65 제안)는 inst1+inst2 합산 기준
  언급이었으나 Task 38a는 기존 33 유지. 논문 서술 시 "시작 모듈 후보 33개 (inst1
  18개 + inst2 15개)" 같이 명확화 또는 65 재검증 여부 세션 A에 요청.

### ⑧ §7.8 Barcode Wasserstein — **Pearson 반전**

**기존 (Tonnetz)**: Pearson(W, JS) = **0.503** (중간 양의 상관). "W distance로 좋은
module 선택 가능" 주장.

**신규 (DFT)**: Pearson = **−0.054** (사실상 무상관). W는 module 품질 지표로 **부적합**.

#### §7.1.9 주의사항 4개 재작성

- 기존 4개 주의사항 중 "W-JS 상관 활용 가능" 항목 반전.
- 메타 결론: "**barcode Wasserstein distance와 생성 품질의 상관은 distance function에
  따라 크게 달라짐**. Tonnetz에서는 0.503, DFT에서는 -0.054. 따라서 W-based module
  선택은 거리 함수 선택 전제가 고정된 경우에만 유효."

#### short.md

- §7.8 축약 또는 "Tonnetz 한정 결과는 full.md 참조" 수준으로 처리.

#### full.md

- Pearson 반전 수치와 해석 모두 포함. 기존 Tonnetz 결과 히스토리로 보존.

### ⑨ §8 결론 §7 관련 수치 동기화

- §8 결론 4번 또는 관련 항에 §7 모듈 단위 생성 결과 언급이 있으면 수치 갱신.
- "모듈 단위 생성으로 JS 0.01479 달성 — full-song 최저(0.01489)와 동등" 메시지 추가
  고려.

## short.md vs full.md 작업 순서 (권장)

1. **full.md 먼저**: DFT 수치 + Tonnetz 반전 각주 동시 반영.
2. **short.md 그 다음**: full을 참조해 Tonnetz 비교·§7.7 "첫 모듈 우수성" 주장 삭제.

## JSON 원본 대조 규칙

- 모든 수치는 해당 JSON을 **직접 열어** mean/std/p-value/Pearson 확인.
- 위 "핵심 수치" 요약은 편의용. JSON과 충돌 시 **JSON이 진실**.

## 산출물

1. `tda_pipeline/docs/academic_paper_full.md` (M)
2. `tda_pipeline/docs/academic_paper_portfolio (short).md` (M)
3. (선택) PDF 재빌드

## 커밋 지침

```
docs(paper): Task 38b §7 전면 재서술 (DFT α=0.25 재수행 반영)

- §7.1 수식 32×42 → 32×14 (K=14, DFT α=0.25 cycle 수)
- §7.2 prototype 전략 DFT 수치 (P3 best 0.0474 유지 — 거리 함수 robust)
- §7.3 P0 본 실험 0.1082, best seed 7105 JS=0.0701
- §7.5 P3+C best trial 0.0250 (distance-invariant 효과 명시)
- §7.6 결론 강화: best global JS=0.01479 ≈ §6.7.1 per-cycle τ 0.01489
- §7.7 서사 반전: first-module 우위 미재현 (rank=5). Tonnetz distance-specific
- §7.8 Pearson 반전: 0.503 → -0.054. §7.1.9 주의사항 재작성
- §8 결론 수치 동기화

short.md: §7.7 "첫 모듈 우수성" 주장 삭제, §7.8 축약
full.md: Tonnetz 기존 결과 히스토리 각주 유지

참조: memory/project_task38a_phase3_findings_0417.md
```

## 검수 체크리스트 (PR 전)

- [ ] §7.1 내 `K = 42` 또는 `32 × 42` 문자열 0건
- [ ] §7.2~§7.5 모든 수치가 DFT α=0.25 JSON 원본과 일치
- [ ] §7.7 short.md에 "첫 모듈의 예외적 우수성" 또는 유사 주장 없음
- [ ] §7.8 Pearson 값이 -0.054로 일관 (논문 전체 Grep)
- [ ] §8 결론의 §7 인용부가 갱신됨
- [ ] short.md 내 Tonnetz 기반 §7 수치 0건, full.md는 각주 수준 유지

## 세션 간 병렬 안전성

- 본 Task 38b는 `academic_paper_*.md` 수정.
- 세션 A Task 39 (T39-2/3/4/5) 가 병렬 진행 중이면 파일 영역 분리 — 동시 실행 안전.
- Task 39 결과 수령 시 세션 D 후속 Task가 필요할 수 있음 (§6.1/§6.2 DFT 열 추가 등).
  Task 38b와는 섹션 다르므로 독립.
