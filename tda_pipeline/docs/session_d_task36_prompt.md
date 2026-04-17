# 세션 D — Task 36: §6.7~§6.9 재서술 (DFT 기반)

## 배경

1. Phase 2 완료 (커밋 `459eb24`): §6.7~§6.9 대응 실험 Task A8~A10 완료.
2. Phase 2b 완료 (커밋 `d83efc5`): Task 34b α=0.25 재실험 결과 **complex는 Tonnetz 한정
   유효** 확정.
3. 기존 §6.7~§6.9는 **Tonnetz α-hybrid 기반**이었음. 본 Task 36에서 **DFT 기반으로
   전면 교체**.
4. 사용자 제약 재확인:
   - **short.md**: gap3↔gap0 비교 서술 금지, 최종 결과만 (깔끔 유지).
   - **full.md**: gap3 및 Tonnetz 기반 기존 실험을 히스토리·각주로 허용.
   - (근거: `memory/feedback_short_md_gap_comparison_exclude.md`)

본 Task 36은 **§6.7~§6.9만** 담당. §4는 Task 35, §7·§8·초록 최종 통일은 Task 37.

## 필수 참조 파일

### 읽을 것

- `memory/project_phase2_gap0_findings_0417.md` — Task A8~A10 수치 요약
- `memory/project_phase2b_alpha25_findings_0417.md` — Task 34b 결과 + 최종 판정
- `memory/project_gap0_dft_integration_0417.md` 결정 5 — Complex 확정 사실
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 분리 규칙
- `CLAUDE.md` 논문-코드 정합성 규칙 (JSON 원본 대조 필수)
- JSON 원본 (수치 갱신 전 **반드시 직접 읽기**):
  - `docs/step3_data/percycle_tau_dft_gap0_results.json` (§6.7.1 = A8)
  - `docs/step3_data/soft_activation_dft_gap0_results.json` (§6.7.2 = A9, N=10 ★)
  - `docs/step3_data/alpha_grid_dft_gap0_results.json` (§6.8 = A10-a)
  - `docs/step3_data/complex_percycle_dft_gap0_results.json` (§6.9 = A10-b pilot α=0.5)
  - `docs/step3_data/complex_percycle_dft_gap0_alpha25_results.json` (§6.9 = Task 34b)

### 수정할 것

- `tda_pipeline/docs/academic_paper_full.md`
- `tda_pipeline/docs/academic_paper_portfolio (short).md`
- (선택) PDF 재빌드

### 읽지 말 것

- 소스코드 (`*.py`)
- 세션 A 상세 로그

## 핵심 수치 (JSON 재확인 필수 — 아래는 참고용 요약)

| 섹션 | 신규 수치 | 출처 JSON |
|---|---|---|
| §6.7.1 baseline (uniform τ=0.35) | JSON 확인 (A8 기반) | `percycle_tau_dft_gap0_results.json` |
| §6.7.1 per-cycle τ_c | **0.0149±0.0014** (N=20, +58.7%, Welch p=2.48e-26) | A8 |
| §6.7.2 FC-bin / FC-cont | FC-cont **0.00035** ★ (N=10) | A9 |
| §6.7.2 Transformer-cont | 0.00082 (FC-cont 대비 p=1.66e-4) | A9 |
| §6.7.2 LSTM | JSON 확인 (열화 예상) | A9 |
| §6.8 DFT α-hybrid 최적 | **α=0.25** (JS=0.01593±0.00181, N=20) | A10-a |
| §6.9 A10-b pilot α=0.5, r_c=0.1 | Algo1 0.03365, Algo2 FC-cont 0.000554 | A10-b pilot |
| §6.9 Task 34b α=0.25, r_c=0.1 | Algo1 **0.0440±0.0010**, Algo2 FC-cont 0.000623 | Task 34b |
| §6.9 Task 34b α=0.25, r_c=0.3 | Algo1 0.0657±0.0015, Algo2 FC-cont 0.000977 | Task 34b |
| §6.9 A8 대비 Welch p | p=4.74e-39 (r_c=0.1), p=1.12e-48 (r_c=0.3) | 둘 다 유의 악화 |

## 작업 범위 — 섹션별 체크리스트

### ① §6.7.0 Cycle별 활성화 프로파일의 다양성

- **직관적 설명은 유지**.
- 단, 예시 cycle 번호가 기존 Tonnetz K=42 기준(cycle 0–5, 30–38)으로 서술되어 있다면
  DFT 기반 K 값에 맞춰 수정 (A8 JSON 확인). cycle 번호는 설명의 편의상 "예: cycle 0–X"
  수준으로 일반화 가능.
- full.md: 개념 설명을 더 풍부하게 유지. short.md: 필요한 핵심만.

### ② §6.7.1 Per-cycle 임계값 최적화

**DFT 기반으로 전면 교체**:

- 기존 Tonnetz α=0.5 baseline (0.0460 → 0.0241, +47.5%) 전부 교체.
- 신규: DFT continuous OM 기반 per-cycle τ_c.
  - baseline uniform τ=0.35: JSON 확인
  - per-cycle τ_c: **0.0149±0.0014** (N=20)
  - 개선율: **+58.7%**, Welch **p=2.48e-26**
- 최적 τ_c 분포: JSON `best_taus` 확인 후 통계 서술 (중앙값, 주된 τ 분포).
- **Algo1 연구 전체 최저 기록 달성** 명시 (기존 Tonnetz complex 0.0183을 능가).

### ③ §6.7.2 Continuous overlap을 직접 받는 Algorithm 2

**DFT 기반 + N=10으로 재서술** (Phase 2 A9 기준):

- 표 수치 갱신 (`soft_activation_dft_gap0_results.json`):
  - FC / LSTM / Transformer × binary / continuous, N=10
  - JS + val_loss
- **핵심 결과**:
  - FC-cont **0.00035** (최우수, 연구 전체 Algo2 최저)
  - Transformer-cont 0.00082 (FC-cont 대비 **p=1.66e-4**로 FC 유의 우위)
  - LSTM: JSON 확인 (기존대로 열화일 것)
- **해석**:
  - short.md: "FC + continuous가 최적. Transformer보다 유의하게 우위 (p=1.66e-4, N=10)"
  - full.md: gap3+DFT 조건에서는 Transformer가 우위였음을 각주로 언급 가능
    (`memory/project_phase2_gap0_findings_0417.md` A9 참조). 단 본문은 DFT+gap0
    맥락 유지.

### ④ §6.8 α grid search — Tonnetz → **DFT hybrid**로 교체

**전면 재작성**:

- 제목 변경: "§6.8 DFT Hybrid의 $\alpha$ grid search — 실험 결과"
- hybrid 거리식도 DFT로: $d_\text{hybrid} = \alpha \cdot d_\text{freq} + (1-\alpha) \cdot d_\text{DFT}$
- 표 수치 갱신 (`alpha_grid_dft_gap0_results.json`): α ∈ {0.0, 0.1, 0.25, 0.3, 0.5, 0.7, 1.0},
  K와 JS.
- 최적 **α=0.25** (JS=0.01593±0.00181).
- **기존 "α=0.5 유지" 권고는 Tonnetz 기반 결론이었으므로 삭제**. DFT에서는 α=0.25 채택.
- α=0.0 / α=1.0 degenerate case 서술은 DFT JSON 결과로 갱신 (K 붕괴 여부 확인).
- 기존 "§6.8 α=0.0 PH 붕괴 주의 박스" (task #22)는 Tonnetz α 전제였음. DFT hybrid에서
  어떤지 A10-a JSON으로 확인 후 재작성 또는 제거.
- short.md / full.md 공통: α=0.25 최종.

### ⑤ §6.9 Complex 가중치 모드 — **절대 최저 서사 전면 반전**

**기존**: "Complex (α=0.25, ow=0.0, rc=0.1) Algo1 0.0183 ★ — 절대 최저 확정".
**신규**: "Complex 모드는 **Tonnetz 한정 유효**. DFT에서는 A8 timeflow 대비 유의 악화."

#### short.md (간결)

- §6.9 제목·내용 대폭 축소: "§6.9 Complex 가중치 모드 — Tonnetz 한정 유효"
- 본문: "Complex 모드는 timeflow와 simul을 결합하는 가중치 구성이다. DFT 거리에서는
  complex가 timeflow 단독(§6.7의 per-cycle τ, JS 0.0149)보다 유의하게 나쁘다
  (JS 0.0440, p<1e-39). 따라서 현재 hibari 최적 설정에서는 timeflow를 사용한다. complex
  모드의 구체적 수식과 Tonnetz 기반 결과는 full.md 참조."
- **"절대 최저 확정" 서술 완전 제거**. 현재 연구 전체 최저는 §6.7.1의 per-cycle τ로 이동.
- gap·α·r_c 등 세부 수치 비교는 금지.

#### full.md (상세)

- Complex 모드 수식·공식은 유지.
- **결과 섹션 전면 재작성**:
  - pilot α=0.5 결과 (A10-b, 0.03365) + Task 34b α=0.25 재실험 결과 (r_c=0.1: 0.0440,
    r_c=0.3: 0.0657)
  - Welch t-test 결과 (p=4.74e-39, p=1.12e-48)
  - 판정: `complex_tonnetz_only_effective` — DFT complex 모드는 α·r_c 선택과 무관하게
    timeflow 대비 유의 악화
- **해석**:
  - DFT는 스펙트럼 구조를 이미 정밀 포착 → simul 혼합이 cycle 활성 신호를 오히려 흐림.
  - Tonnetz에서 complex가 유효했던 이유(화성적 공존 보완)가 DFT에서는 불필요.
  - 기존 Tonnetz complex 최저 0.0183은 distance-specific 현상이었음.
- **연구 전체 최저 갱신 주석**:
  - Algo1 최저 = §6.7.1 DFT + per-cycle τ = **0.0149** (§6.9에서 이를 참조)
  - Algo2 최저 = §6.7.2 DFT + FC-cont = **0.00035**
- 기존 "절대 최저 확정 박스"는 제거 또는 "Tonnetz 한정" 조건부로 전환.

### ⑥ §6 종합 (full.md에서 상단 개요나 §6.4 종합 논의에 가능)

선택적: §6 개요에 "§6.7~§6.9 모두 DFT 기반으로 재탐색됨"을 명시하는 한 줄 추가.
강제 사항 아님.

## short.md vs full.md 작업 순서 (권장)

1. **full.md 먼저**: DFT 수치 반영 + Complex 판정 확정 + Tonnetz 기존 결과는 각주·"이전
   실험" 수준으로 배치.
2. **short.md 그 다음**: full을 참고해 최종 결과만 남기고 Tonnetz 비교·Complex 상세 삭제.

## JSON 원본 대조 규칙

- 모든 수치는 해당 JSON을 **직접 열어** mean/std/p-value 값을 확인.
- 위 핵심 수치 표는 편의용. JSON과 충돌 시 **JSON이 진실**.
- 특히 §6.7.1 baseline uniform τ=0.35 값, §6.7.2 Transformer/LSTM 상세, §6.8 α grid
  각 값은 JSON으로 직접 채울 것.

## 산출물

1. `tda_pipeline/docs/academic_paper_full.md` (M)
2. `tda_pipeline/docs/academic_paper_portfolio (short).md` (M)
3. (선택) PDF 재빌드 (`academic_paper_full.pdf`, `academic_paper_portfolio (short).pdf`)

## 커밋 지침

Task 35 커밋과 별개로 분리:

```
docs(paper): §6.7~§6.9 DFT 기반 재서술 (Task 36, Phase 2+2b 반영)

- §6.7.1 per-cycle τ: DFT continuous 기반으로 교체, +58.7% p=2.48e-26 (N=20)
- §6.7.2 DL: N=10 재검증, FC-cont 0.00035 ★ (Transformer-cont 대비 p=1.66e-4)
- §6.8 α grid: Tonnetz → DFT hybrid 교체, 최적 α=0.25 (JS=0.01593±0.00181)
- §6.9 Complex: 서사 전면 반전 — "Tonnetz 한정 유효" 확정 (Task 34b p<1e-39)
  - 기존 "Complex 절대 최저" 제거, 연구 전체 최저는 §6.7.1 per-cycle τ 0.0149로 이동
- short.md: Complex 상세·Tonnetz 비교 완전 제거
- full.md: gap3·Tonnetz 기존 결과는 히스토리·각주 수준 보존

참조: memory/project_phase2_gap0_findings_0417.md,
      memory/project_phase2b_alpha25_findings_0417.md,
      memory/feedback_short_md_gap_comparison_exclude.md
```

## 후속 Task 안내 (세션 D 작업 순서)

**Task 37 (§7 baseline 재설정 + §8 결론·초록 최종 통일)**: Task 35 + Task 36 완료 후 착수.

- §7의 full-song Tonnetz 0.0488 baseline을 DFT baseline으로 교체 (실험 재실행 불필요 —
  baseline 값만 교체). 대체 값은 §4.1 DFT (0.0213) 또는 §4.2 Binary DFT (0.0157) 중
  세션 D 판단.
- §8 결론 수치 전면 통일 (§4/§6 갱신 반영).
- 초록 최종 통일.
- **CLAUDE.md "현재 최적 설정" 블록 갱신** (세션 D 전용 허용 편집):
  - 거리: DFT, w_o=0.3, w_d=1.0
  - 모드: timeflow (complex 아님)
  - OM: continuous + per-cycle τ_c
  - 모델: FC-cont
  - gap_min=0

## 검수 체크리스트 (PR 전 자체 점검)

- [ ] §6.7.1 Tonnetz baseline(0.0460/0.0241) 흔적 0건 (short.md), 각주로만 (full.md)
- [ ] §6.7.2 FC-cont 0.00035 + Transformer-cont p=1.66e-4 통계 명시
- [ ] §6.8 α grid 표가 DFT hybrid로 교체됨, α=0.25 최적
- [ ] §6.9 "절대 최저" 주장 완전 삭제, "Tonnetz 한정 유효" 결론
- [ ] short.md 내 complex 수식·pilot grid 0건
- [ ] 모든 수치가 JSON 원본과 일치
- [ ] §6 어디에도 gap_min=3 / gap3 문자열 0건 (short.md)
