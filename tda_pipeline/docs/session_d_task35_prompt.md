# 세션 D — Task 35: §4 gap0+DFT 재서술

## 배경

1. Phase 1 완료 (커밋 `bb4ab4d`): §4 DFT+gap0 Task A1~A7 실험 완료.
2. Phase 2 완료 (커밋 `459eb24`): §6.7~§6.9 DFT 재탐색 + §4.3 후속 FC-cont N=10 확정.
3. 사용자 결정: gap_min=3 청취 평가 폐기, §4 전면 `gap_min=0` + DFT baseline으로 재서술.
4. **핵심 제약**: gap3↔gap0 **비교 서술은 full.md에만**, short.md는 **최종 결과만**
   (`memory/feedback_short_md_gap_comparison_exclude.md`).

본 Task 35는 **§4 전면 재서술 + 연쇄 일관성 갱신(§3.2 / 초록 §4 부분 / §5.1 / §6.1 / §6.2의
hibari DFT 수치)**만 수행한다. §6.7~§6.9는 Task 36, §7·§8·초록 전체 마무리는 Task 37로
분리.

## 필수 참조 파일

### 읽을 것

- `memory/project_phase1_gap0_findings_0417.md` — Task A1~A7 수치 요약
- `memory/project_phase2_gap0_findings_0417.md` — Task A8~A10 (§4.3a에 A9만 사용)
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 분리 규칙
- `CLAUDE.md` — 논문-코드 정합성 규칙 (JSON 원본 대조 필수)
- JSON 원본 — **수치 갱신 전 반드시 직접 읽어 대조** (기억 의존 금지):
  - `docs/step3_data/step3_results_gap0.json` (§4.1)
  - `docs/step3_data/dw_gridsearch_dft_gap0_results.json` (§4.1b)
  - `docs/step3_data/ow_gridsearch_dft_gap0_results.json` (§4.1a)
  - `docs/step3_data/decayed_lag_dft_results.json` (§4.1c — 기존 재사용)
  - `docs/step3_data/step3_continuous_dft_gap0_results.json` (§4.2)
  - `docs/step3_data/dl_comparison_dft_gap0_results.json` (§4.3, Phase 1 N=5)
  - `docs/step3_data/soft_activation_dft_gap0_results.json` (§4.3, Phase 2 N=10 **최종**)
  - `docs/step3_data/fc_cont_dft_gap0_results.json` (§4.3a, Phase 1 N=5)

### 수정할 것

- `tda_pipeline/docs/academic_paper_full.md`
- `tda_pipeline/docs/academic_paper_portfolio (short).md`
- (선택) PDF 재빌드: `docs/build_academic_pdf.py`

### 읽지 말 것

- 소스코드 (`*.py`)
- 세션 A/B 상세 로그

## 핵심 수치 (사전 요약 — 반드시 JSON 재확인)

| 섹션 | 핵심 수치 | 출처 JSON |
|---|---|---|
| §4.1 | DFT JS=**0.0213±0.0021** (N=20), freq 대비 −38.2%, Tonnetz 대비 −56.8% | `step3_results_gap0.json` |
| §4.1a | w_o=**0.3** 최적 | `ow_gridsearch_dft_gap0_results.json` |
| §4.1b | w_d=**1.0** 최적 | `dw_gridsearch_dft_gap0_results.json` |
| §4.1c | DFT+decayed JS=**0.0196±0.0022** (−7.1% ★) | `decayed_lag_dft_results.json` |
| §4.2 | Binary 최적 JS=**0.0157±0.0018** | `step3_continuous_dft_gap0_results.json` |
| §4.3 | **FC-cont 0.00035** vs Transformer-cont 0.00082 (N=10, Welch p=1.66e-4) | `soft_activation_dft_gap0_results.json` |
| §4.3a | FC-cont 0.00035 vs FC-bin (JSON 확인) | `soft_activation_dft_gap0_results.json` |

## 작업 범위 — 섹션별 체크리스트

### ① 초록 (§4 관련 수치 부분만)

- gap_min=3 관련 모든 서술 **제거** (full에도 "초록에는 gap3 언급 금지" — 서사상 부적절).
- DFT baseline 수치, Algo1 Binary OM 최적, Algorithm 2 FC-cont 최적으로 교체.
- 초록은 short/full 동일 내용 유지 (초록은 최종 결과 요약).

### ② §3.2 5단계 onset gap 후처리

- short.md L437 근처 "본 연구의 모든 실험에서는 `gap_min = 3`" → **제거** (또는
  `gap_min = 0`으로 정정).
- `gap_min` 파라미터 정의 문장 자체는 유지 가능.
- full.md는 선택적으로 "초기에는 gap=3 조건이었으나 청취 평가 결과 gap=0으로 롤백" 각주
  1줄 허용. short.md는 각주도 금지.

### ③ §4.1 거리 함수 비교 (N=20)

- 표 수치 전면 교체 (`step3_results_gap0.json` 4종 전부).
- 해석 1: "DFT가 frequency 대비 −38.2%, Tonnetz 대비 −56.8%..." (Phase 1 A1 기준).
- "gap_min=3 (1.5박 간격 제약) 조건" 문구 **제거**.

### ④ §4.1a Octave Weight 튜닝

- 표 수치 갱신 (`ow_gridsearch_dft_gap0_results.json`). 최적 w_o=0.3.
- **"Tonnetz 조건에서도 동일하게 w_o=0.3"·"Tonnetz 조건과 동일하게" 언급 전부 삭제**
  (사용자 지시).
- `w_d = 1.0` (§4.1b 최적) 고정 표기.
- gap 조건 명시 제거.

### ⑤ §4.1b Duration Weight 튜닝

- 표 수치 갱신 (`dw_gridsearch_dft_gap0_results.json`). 최적 w_d=1.0.
- **"Tonnetz 조건의 최적값(w_d=0.3)과 달리" 등 Tonnetz 비교 언급 삭제**.
- gap 조건 명시 제거.

### ⑥ §4.1c 감쇄 Lag

- 기존 `decayed_lag_dft_results.json` 재사용 (DFT+decayed −7.1% ★ 유지).
- gap 조건 명시 제거. 표는 DFT/Tonnetz 그대로 두되 gap 라벨만 정리.

### ⑦ §4.2 Continuous Overlap Matrix

- 표 수치 갱신 (`step3_continuous_dft_gap0_results.json`). Binary 최적 0.0157±0.0018
  강조.
- 해석 5a/5b/5c의 수치 + 논리 갱신.
- gap 조건 명시 제거.

### ⑧ §4.3 DL 모델 비교

- **N을 5 → 10으로 갱신** (Phase 2 A9 기준, `soft_activation_dft_gap0_results.json`).
- 표 수치: FC-cont 0.00035 ★, Transformer-cont 0.00082, LSTM (JSON 확인).
- **해석 6~8 전면 재작성**:
  - **short.md**: "현 hibari 설정에서는 FC-cont가 최우수 (p=1.66e-4, N=10)"로 간결
    서술. gap/Tonnetz 조건 비교 금지.
  - **full.md**: "gap=3+DFT 조합에서만 Transformer가 우위였고(별도 실험),
    gap=0+DFT 및 gap=0+Tonnetz 조건에서는 FC가 우위"로 조건부 명시. 각주로 Phase 1 A6
    N=5 결과 + Phase 2 A9 N=10 확정 경과 언급 가능.

### ⑨ §4.3a FC-bin vs FC-cont

- 표 수치 갱신 (Phase 2 A9 N=10 최종값 사용): FC-cont 0.00035.
- **해석 9 반전**: 기존 "DFT 조건에서 FC-cont 이점 없음" → "DFT 조건에서도 FC에 continuous
  입력이 큰 개선(...배)을 준다. §4.2의 Algo1 Binary 우위와 대비되는 결과로, OM 표현의
  최적은 downstream 모델에 따라 다르다"로 재작성.
- 해석 10 (validation loss 역설)은 유지 가능.
- **short.md**: 간결 서술. **full.md**: gap3에서 왜 재현 안 됐는지 각주 허용.

### ⑩ §4.3a 통합 비교표

- 전면 갱신:
  - §4.1 DFT baseline 0.0213
  - §4.2 Binary DFT (최적 파라미터) 0.0157±0.0018
  - §4.3 FC-cont 0.00035★
  - 이론 최댓값 log(2)≈0.693 대비 비율 재계산
- "§4.3 Transformer (DFT binary)는 ... 관측된 최저" 문장 **삭제** — 현재는 FC-cont 최저.

### ⑪ §4.4 종합 논의

- (1) 수치 갱신 (−38.2% / −56.8%).
- (2) "DFT 조건에서 Binary Algo1 우위 / continuous Algo2 우위" 조합 interaction 서술.
- (3) 모델 선택: short.md는 "FC 우위"로 단순 서술. full.md는 gap·거리 조건부 서술.
- gap_min 언급 전면 재정리.

### ⑫ 연쇄 일관성 (short.md + full.md 공통)

hibari DFT JS 수치가 여러 곳에서 재인용됨. 모두 **0.0213** (또는 JSON 재확인 값)으로
통일:

- §5.1 해석 2 (A): "DFT가 frequency 대비 −38.2%, Tonnetz 대비 −56.8%, voice_leading
  대비 X%"로 갱신 (X는 JSON 재계산).
- §6.1 hibari 최우수 표기: 0.0213.
- §6.2 표 hibari 행: DFT 수치 0.0213.
- **§6.1/§6.2/§5.1의 다른 수치·해석(solari/Bach/Ravel 등)은 본 Task 35 범위 밖** —
  Task 36/37에서 처리.

## short.md vs full.md 작업 순서 (권장)

1. **full.md 먼저**: gap0 수치 + gap3 히스토리 각주(필요 시) 동시 반영.
2. **short.md 그 다음**: full.md 버전을 참조해 **gap3 흔적 완전 제거**한 최종본으로.

## JSON 원본 대조 규칙

- 본 Task에서 인용하는 모든 수치는 해당 JSON을 **직접 열어서** mean/std 값을 확인한다.
- 위 "핵심 수치" 요약은 편의 목적이며, JSON과 충돌 시 **JSON이 진실**.
- Task 내부에서 사용한 값은 세션 보고에 JSON 경로와 함께 요약.

## 산출물

1. `tda_pipeline/docs/academic_paper_full.md` (M)
2. `tda_pipeline/docs/academic_paper_portfolio (short).md` (M)
3. (선택) `tda_pipeline/docs/academic_paper_full.pdf` / `academic_paper_portfolio (short).pdf` 재빌드

## 커밋 지침

두 md(+선택 PDF)를 하나의 커밋으로:

```
docs(paper): §4 gap0+DFT 재서술 (Task 35, Phase 1+2 반영)

- §4.1~§4.4 수치 Phase 1 (bb4ab4d) + Phase 2 A9 (459eb24) 로 갱신
- §3.2 "모든 실험 gap_min=3" 선언 제거
- §4.3 Algo2: FC-cont 0.00035 (N=10, Welch p=1.66e-4) 최우수
- §4.3a 해석 9 반전: DFT+continuous FC 이점 통계 확정
- §4.1a/b의 "Tonnetz 조건 최적값" 언급 삭제 (사용자 지시)
- §5.1·§6.1·§6.2의 hibari DFT 수치 0.0211 → 0.0213 일관성 갱신
- short.md: gap3↔gap0 비교 서술 완전 제거
- full.md: gap3 히스토리 각주 수준 보존

참조: memory/project_phase1_gap0_findings_0417.md,
      memory/project_phase2_gap0_findings_0417.md,
      memory/feedback_short_md_gap_comparison_exclude.md
```

## 후속 Task 안내 (세션 D 작업 순서)

- **Task 36 (§6.7~§6.9 재서술)**: Task 34b (A10-b α=0.25 재실험, 세션 A 진행 중) 완료
  대기. §6.9 "절대 최저" 결론 방향은 재실험 결과가 결정.
- **Task 37 (§7 baseline 재설정 + §8 결론·초록 최종 통일)**: Task 35, 36 완료 후. "현재
  최적 설정" 블록 갱신도 이 때 수행 (CLAUDE.md의 세션 D 규칙).

## 검수 체크리스트 (PR 전 자체 점검)

- [ ] short.md에 `gap_min=3` / `gap3` / `gap=3` / "1.5박 간격 제약" 문자열 0건
- [ ] short.md·full.md 모두 hibari DFT JS 수치 단일 값으로 통일
- [ ] §4.3 해석이 short.md는 단순 서술 / full.md는 조건부 서술
- [ ] §4.1a/b에 Tonnetz 조건 언급 0건
- [ ] §4.3a 통합 비교표의 "최저" 주장이 FC-cont 0.00035로 교체됨
- [ ] 모든 수치가 JSON 원본과 일치 (소수점 4자리까지)
