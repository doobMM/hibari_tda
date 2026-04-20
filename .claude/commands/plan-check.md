---
description: Plan Mode 진입 후 두 번째 Claude 인스턴스(staff engineer 페르소나)로 플랜을 자체 검증. best-practice 패턴 "이중 Claude 검증".
argument-hint: <planning_topic>
---

# plan-check

되돌리기 비싼 작업(데이터 재생성·LaTeX 대규모 수정·UI 전면 개편)에 대한 **이중 검증**. 비용 2배이지만 회귀 비용보다 저렴.

## 실행 절차

1. **첫 Plan** — 너(현재 Claude)가 plan 작성
   - 파일별 수정 항목, 예상 산출, 예상 리스크 3가지
   - 산출: `.claude/plans/<timestamp>_<topic>.md`

2. **두 번째 검증** — `Agent(subagent_type="octo:personas:code-reviewer")` 에 위임
   - 입력: 첫 Plan 전문 + 관련 코드 파일 경로 목록 (내용 아님, 경로만)
   - 요청: "staff engineer 관점에서 Plan의 맹점을 지적. 구체적 파일·라인·시나리오만. 일반론 금지."
   - 산출 형식:
     ```
     ✓ 동의: 3항목
     ⚠ 의심: 2항목 (파일·근거·대안)
     ✗ 거부: 0~1항목 (치명적 결함)
     ```

3. **차이 정리** — 두 Plan의 diff만 사용자에게 제시

## 사용 기준

사용 권장:
- 데이터 재export + 모델 재학습 (R1 같은 작업)
- 코드 파일 5개 이상 동시 수정
- CLAUDE.md / academic_paper_full.md / LaTeX 대규모 갱신
- 공개 산출물(대시보드·유튜브) 최종 단계

사용 비권장:
- 실험 1회 실행 (결과 뒤집으면 그만)
- 논문 오타·수치 1건 수정
- 새 skill 초안 작성

## Gotchas

- 두 Claude가 같은 모델(opus-4-7)이면 **동일 오류 공유 가능** → code-reviewer persona는 엄격한 페르소나로 약간의 편차 유도
- 검증 subagent가 "일반론"으로 도망가면 재프롬프트하지 말고 **재호출에 파일 1~2개 내용 첨부**
