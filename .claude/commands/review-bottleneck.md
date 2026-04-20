---
description: 변경된 파일만 subagent로 탐색하여 "3줄 요약 + 위험 플래그"만 반환. 인간(사용자)이 코드 리뷰 병목이라는 가정 하에 설계.
argument-hint: [base_ref=HEAD~1]
---

# review-bottleneck

사용자는 **본인이 코드 리뷰 병목**임을 인지하고 있다. 이 커맨드는 전체 diff를 네게(사용자에게) 읽히는 대신, **subagent에 탐색을 위임**하고 **요약만** 돌려준다.

## 실행 절차

1. **변경 파일 식별**
   ```bash
   git diff --name-only ${1:-HEAD~1}..HEAD
   git diff --stat ${1:-HEAD~1}..HEAD | tail -1
   ```

2. **subagent에 위임** (`Agent(subagent_type="general-purpose", ...)`)
   - 프롬프트에 변경 파일 목록 + 각 파일 diff 전달
   - 각 파일당 요구 산출:
     - **변경 의도** (1줄)
     - **작동 영향** (1줄 — 어떤 함수·파이프라인 단계가 달라지는지)
     - **위험 플래그** (있을 때만 1줄: 성능·정합성·테스트 미존재·회귀 가능성)

3. **집계 후 부모 컨텍스트에는 표만 제시**
   ```
   | 파일 | 의도 | 영향 | 🚩 |
   |---|---|---|---|
   | pipeline.py | overlap 계산 | Algo1 경로 분기 추가 | — |
   | weights.py | rate 기본값 변경 0.3→0.5 | PH 전 단계 재계산 필요 | 🚩 캐시 무효 |
   ```

4. **마지막 줄**: 🚩 개수 + 추천 다음 행동 (1줄)

## 제약

- 파일 5개 초과 시 **persistence · semantic · test · docs** 4분류로 묶어 요약
- 생성된 바이너리(`*.png`, `*.pdf`, `*.pkl`, `*.onnx`, `*.mid`, `*.wav`)는 파일명만 언급, diff 안 읽음
- diff 1000줄 초과 파일은 "대규모 변경" 표시 후 상위 20줄/하위 20줄만 본다
- 보안·secret 패턴(`api_key`, `token`, `.env`) 발견 시 즉시 최상단에 🔐 경고

## Gotchas

- `git diff HEAD~1` 가 merge commit을 포함하면 정보량 폭증 → `--first-parent` 추가 고려
- `professor.py` 수정은 **항상 위험** — CLAUDE.md 규약상 직접 수정 금지
- `hibari_dashboard/` vs `tda_pipeline/` 동시 수정 시 세션 충돌 가능 (R1/R3 세션과 겹치는지 플래그)
