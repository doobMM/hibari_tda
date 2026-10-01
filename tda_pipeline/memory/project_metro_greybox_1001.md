---
name: project-metro-greybox-1001
description: "hibari 노선도(Mini Metro 뼈대) — 규칙 한 장·장면 한 장 승인 후 소리 없는 회색 시제품 배포. 다음 = 사용자 '한 판 더?' 확인 → 소리 → 수학"
metadata:
  type: project
---

2026-10-01 판 14 뒤 [[feedback-game-rules-visual-first-1001]] 에 따라: 뼈대 셋 그림 → 사용자 "가 hibari 노선도" → 장면·규칙 승인 "응, 일단 이대로" → `sketch/metro.html` + `metro-core.js`.
- 규칙: 승객을 모양 역으로, 여섯 넘게 쌓이면 시계, 매주 열차 + 선물(노선·객차·다리), 강 = 다리, 역 이름 = hibari 모듈 화음 순서, 첫 노선 전엔 시간 정지.
- 검증 5/6 (`tools/verify_sketch_metro.mjs`): G2 실패 — 어려워짐 0.8(봇 한 판 4.6~6.8분)로 맞춘 뒤 방치 대비 2.98배(문턱 3배).
- 순서를 지킨다: 사용자가 회색 시제품을 해 보고 "한 판 더?" 를 답하기 전에는 소리(④)·수학(⑤)을 붙이지 않는다.
