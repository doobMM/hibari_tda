# 코드 플로우 리뷰 문서 작성 (2026-04-26)

## 산출물

- `tda_pipeline/docs/codebase_flow_review.html`

## 배경

- 사용자가 원한 것은 Jarvis 대시보드 사용법이 아니라, 대시보드가 인간 작업자에게 보여주려던 코드 리뷰를 대신 수행한 문서였음.
- 이전 산출물 `jarvis_code_review_interface_guide.html`은 대시보드 가이드 성격이 강해 요구와 어긋남.

## 이번 문서의 초점

- 핵심 11개 모듈:
  - `config.py`, `pipeline.py`, `preprocessing.py`, `weights.py`, `musical_metrics.py`, `topology.py`, `overlap.py`, `generation.py`, `eval_metrics.py`, `cycle_selector.py`, `temporal_reorder.py`
- 인접 중요 코드:
  - `note_reassign.py`, `run_any_track.py`, `experiments/`, `hibari_dashboard/scripts/`, `filtration_viz/scripts/`, `tests/`
- 주요 내용:
  - 전체 파이프라인 구조
  - 단계 간 데이터 계약
  - 파일 위계
  - Stage 1~4 코드 흐름
  - Algorithm 1/2 요약
  - cycle selection / temporal reorder / note reassign 변형
  - 실험/웹/테스트 표면
  - 알고리즘 특이사항과 리뷰 체크리스트

## 확인

- HTML 문서 내 `<section class="page">` 15개 확인.
- 대시보드 가이드가 아니라 코드 리뷰 대체 문서임을 마지막 페이지에 명시.
- 중요한 코드 특이사항 반영:
  - 1-index/0-index 혼재
  - `solo_notes` vs `solo_timepoints`
  - `refine_connectedness_fast` post-bugfix 구조
  - `ripser` generator 대표 cycle 근사
  - continuous activation 희귀도 가중
  - Algorithm 1 sustain 차감
  - `run_any_track.py` pitch-only 경로

## 후속

- 필요하면 이전 잘못된 범위의 `jarvis_code_review_interface_guide.html`을 삭제하거나, 새 문서로 redirect하는 후속 정리 가능.
