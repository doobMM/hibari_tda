# Task24 — §6.6.1 Tonnetz major_block32 post-bugfix 재실험 (2026-04-18)

## 목적
- §6.6.1 Tonnetz baseline이 pre-bugfix 수치(`combined_AB_results.json`)만 있는 상태를 해소.
- `pipeline.py` ow/dw 전달 버그 수정(`080b9fe`, 2026-04-15) 이후 조건으로 재실험하여 각주 해제 가능 여부 판단.

## 실행 전 확인
- 기존 생성 스크립트 추적: `run_combined_AB.py` → `docs/step3_data/combined_AB_results.json` 생성 이력 확인.
- 버그 수정 커밋 확인:
  - `pipeline.py`에서 tonnetz/dft/vl metric에 `octave_weight`, `duration_weight` 전달 누락 수정.
  - `config.py`에 `duration_weight` 필드 추가.
- 지침 확인: `diagnose.py` 실행 완료.
  - `notes_label`, `notes_dict`, lag/intra/inter는 일치.
  - refine/distance 단계는 기존 코드와 차이 존재(기존 진단 스크립트에서도 보고되는 known divergence 구간).

## 실험 설정
- 스크립트: `run_section661_tonnetz_major_block32_postbugfix.py` (신규)
- 전처리: `run_any_track.py` 패턴 유지 (pitch-only, tie 정규화 흐름 유지)
- PH:
  - metric: tonnetz
  - `octave_weight=0.3`, `duration_weight=0.3`
  - `alpha=0.5`, `rate=0~1.5`, `step=0.05`
- 생성 조건:
  - note 재분배: `scale_major`
  - 시간 재배치: `block_permute(32)`
  - 모델: Transformer (`epochs=50`)
- 반복:
  - pilot N=5 후
  - 확장 N=10

## 산출물
- 결과 JSON: `docs/step3_data/post_bugfix_tonnetz_major_block32_results.json`

## 핵심 결과

### pre-bugfix 기준값 (비교 기준)
- vs orig pJS: **0.0968**
- vs orig DTW: **2.3593**
- vs ref pJS: **0.0034**

### pilot N=5
- vs orig pJS: **0.2694 ± 0.1579**  (Δ **+178.27%**)
- vs orig DTW: **3.7521 ± 1.1573**  (Δ **+59.03%**)
- vs ref pJS: **0.00636 ± 0.00151** (Δ **+86.97%**)
- scale match: **1.000 ± 0.000**

### final N=10
- vs orig pJS: **0.2696 ± 0.1106**  (Δ **+178.55%**)
- vs orig DTW: **3.6201 ± 0.8181**  (Δ **+53.44%**)
- vs ref pJS: **0.00710 ± 0.00308** (Δ **+108.97%**)
- scale match: **1.000 ± 0.000**

## 통계/판정
- one-sample t-test(기준=pre-bugfix 값, N=10):
  - vs orig pJS: p=0.0008
  - vs orig DTW: p=0.0009
  - vs ref pJS: p=0.0042
- 3개 핵심 지표 모두 pre-bugfix 값이 post-bugfix 평균 95% CI 밖.
- **결론: §6.6.1 각주 해제 보류(재검토 필요).**

## 메타 해석(초안)
- post-bugfix(ow/dw 반영) + 동일 실험 조건에서 major_block32 결과가 pre-bugfix 대비 크게 악화.
- §6.6.1/§6.6.3의 “Tonnetz major_block32 해석”은 pre-bugfix 수치 의존도가 높아 보이며, 본문/각주 정책 재결정 필요.

