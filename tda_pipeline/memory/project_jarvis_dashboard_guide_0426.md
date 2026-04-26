# Jarvis 코드 점검 인터페이스 설명서 작성 (2026-04-26)

## 산출물

- `tda_pipeline/docs/jarvis_code_review_interface_guide.html`

## 내용

- `tda_pipeline/tools/gen_dashboard.py`가 `tda_pipeline/docs/pipeline_dashboard.html`을 만드는 구조를 15쪽 HTML 문서로 정리.
- 비전공자도 따라갈 수 있게 다음 흐름을 설명:
  - 생성기와 결과 HTML의 파일 위계
  - `MODULE_FILES` / AST 파싱 / git recent line detection / HTML embedding
  - 3패널 UI 구조(트리, 코드 뷰어, 함수 분석)
  - 파이프라인 단계별 모듈 역할
  - 실제 코드 리뷰 동선
  - `code_map_pipeline.html`과의 역할 차이
  - GitHub Pages 공개/민감정보 주의

## 확인

- HTML 문서 내 `<section class="page">` 15개 확인.
- 2026-04-26 로컬 기준 대시보드 대상: 11개 모듈, 4,933 lines, 110 functions/methods, 최근 수정 표시 93개.
- 현재 Pages workflow는 `tda_pipeline/docs/pipeline_dashboard.html` 또는 새 설명서를 자동 배포하지 않음. 코드 원문이 들어간 대시보드를 공개하지 않는 기본값은 유지됨.

## 후속

- 대시보드 기능 개선이 필요하면 B 세션으로 인계:
  - 모바일 탭형 레이아웃
  - docstring/파라미터까지 포함한 검색
  - 공개 전 민감정보 경고 배너
  - `pipeline_dashboard.html`에서 `code_map_pipeline.html`로 이동하는 링크
