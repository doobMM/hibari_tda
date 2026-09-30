---
name: project-sketches-1001
description: "살리기 세 스케치 A 흐름 그물 · B 두 바퀴 · C 고리 합주 — 지어서 배포(4ad3d29), 사용자 판정 대기. 정본 intra 는 순서를 담지 않아 방향을 모듈에서 가져왔다"
metadata:
  type: project
---

2026-10-01 커밋 4ad3d29 로 배포: `tda_pipeline/sketch/index.html` → flow.html(A) · wheels.html(B) · loops.html(C). 명세·수치 `docs/sketch_spec.md` §7.
검증 `node tools/verify_sketch_{flow,wheels,loops}.mjs` 전부 통과 — 단 엔진 상수는 그 수치를 보며 골랐다(확증 아님). 사람 손·귀로는 아직 안 만졌다.

- A: 부은 음에서 곡이 이어진다(그 손의 모듈이 그 음 자리로). 계단 0.804, 그러나 "물길 같게" 대조가 0.687 — 계단의 대부분은 모듈 음높이 끌림에서 온다.
  **정본 intra 는 대칭이라 순서를 담지 않는다**(다음 묶음으로 가는 무게 3~10%) → 방향은 모듈의 다음 묶음에서. HS.shuffled 로 섞어도 0.803 = 정본 가중치는 A 에서 하중 없음.
- B: 톱니 자리 수 = 모듈(리듬은 hibari 로 남고 박힌 음이 내 음이 된다). 닳기는 배고픔(마지막 손길 뒤 16스텝)에 비례. 고리 보호는 효과 있으나 고리 정체는 무관(섞음과 같다).
- C: 워크플로 검토의 치명 2(포크가 고침)·중요 4(원본이 고침). 실패할 수 없는 판정기 재설계는 남음.
- 워크플로의 A·B 제작 에이전트는 사용량 한도로 죽었다 → 원본 세션이 직접 지었다. [[feedback-fork-sessions-and-usage]] [[feedback-life-v3-verdict-0930]]

**Why:** 사용자가 "시안 3개 다 좋아… 살리기는 뭘지 궁금해" 라고 한 뒤 만져 볼 수 있게 지었다.
**How to apply:** 다음은 사용자가 10초씩 만져 보고 고르는 것. 판정이 오면 CLAUDE.md 거절 이력에 12판으로 적는다.
