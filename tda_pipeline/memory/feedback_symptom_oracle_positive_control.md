---
name: feedback-symptom-oracle-positive-control
description: "2026-10-28 toss harness 분석에서 옮긴 검증 규칙 두 개 — 최종 산출물에서 결과 재기, 일부러 망가뜨린 판으로 검증기 살아 있음 확인"
metadata:
  node_type: memory
  type: feedback
  originSessionId: fd94ced9-59f4-460a-a6bc-cca587246f8e
  modified: 2026-10-28T13:02:50.231Z
---

상호작용 판·시연 영상을 검증할 때 두 가지를 지킨다 (사용자: "그 정도로 우리 작업에 옮기자", 2026-10-28).

1. **증상 오라클**: 원인 규칙과 별도로, 손짓 → 그림 변화 → 소리 변화를 최종 산출물(페이지·영상·오디오)에서 직접 잰다. 중간 계산 수치가 맞아도 화면·소리에서 안 보이면 실패.
2. **양성 대조**: 새 판정기는 하나만 망가뜨린 판(손짓 무시·소리 끔·지연)을 넣어 FAIL 이 나는지부터 보고, 그 판을 판정기 옆에 남긴다.

**Why:** toss/apps-in-toss-harness 는 skill 본문이 3주간 안 들어갔는데 모든 검사가 "호출됐나" 만 재서 통과했다. 우리 판 12~14 도 반응만 재고 읽힘을 재지 않았다.
**How to apply:** 상호작용 판·영상을 내기 전 이 두 검사를 돌린다. CLAUDE.md 「검증기를 짓는 두 규칙」 참고. [[feedback-reference-protocol]]
