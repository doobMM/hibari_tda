---
name: feedback-shortest-path-math
description: 수학 계산은 무작정(brute force) 돌리지 말고 먼저 GitHub·논문(arXiv 등)·작업 폴더에 사용자가 받아 둔 PDF 에서 최신 방법을 찾아 최단거리로 — 2026-10-07 사용자 지시
metadata:
  node_type: memory
  type: feedback
  originSessionId: fd94ced9-59f4-460a-a6bc-cca587246f8e
  modified: 2026-10-07T13:14:38.299Z
---

사용자(2026-10-07, 고리판 H₁ 탐침을 정본 번들로 판 73개 돌리는 도중): "수학적인 계산을 수행할 때 brute force로 임하지 말고 github이나 논문 개제 사이트에서 최신 연구결과를 참고해서 항상 최단거리를 추구하는 버릇을 들이도록 해."

**Why:** 정본 번들(build_overlap_bundle)을 판마다 통째로 돌려 일곱 프로세스로 561초를 썼다. 병목은 topology.generate_barcode_numpy(pHcol, rate 151번 ≈ 5.4초/판)였고 거리 계산은 0.18초뿐이었다.
같은 행렬에서 ripser 는 151번 0.08초에 같은 막대를 낸다(float32 반올림 1e-6 차이). 저장소에 generate_barcode_ripser 가 이미 있었고(대표는 BFS 근사),
사용자는 바로 이 문제의 논문을 tda_pipeline/ 에 받아 두었다 — Vines and Vineyards(1137856.1137877.pdf) · Move schedules(s41468-023-00156-3.pdf) · Through the Grapevine: vineyard distance(2510.24472v2.pdf).
그 틀(정본 rate 쓸기 = vineyard, 비교 = 바코드 Wasserstein)로 다시 하니 한 프로세스 71초에 끝났고, 고리 대표 맞대기로는 안 보이던 것(원마다 모양을 흔드는 정도가 다르다)이 보였다.

**How to apply:**
- 계산을 짜기 전에 ① `tda_pipeline/` 의 PDF 목록(사용자가 받아 둔 논문) ② 저장소에 이미 있는 빠른 함수 ③ WebSearch(arXiv·GitHub) 순으로 "이미 풀린 문제인가" 를 본다.
- 1분 넘게 걸릴 계산은 돌리기 전에 병목을 한 번 재고(어디서 시간이 드나), 알려진 알고리즘·라이브러리로 줄일 수 있는지 먼저 확인한다.
- 정확한 동치가 필요하면 빠른 방법을 정본과 대조한다(이번: 다 맞춘 판 151 rate 막대 대조). 근사(대표의 BFS 등)는 근사라고 적는다.
- 쓸 수 있는 도구: ripser 0.6.14 · persim 0.3.8 설치됨. 대표가 필요하면 involuted PH(Čufar·Virk 2023, Ripserer.jl), 매개변수 족이면 vineyard·move schedules, 2-매개변수면 multipers.

[[project-rings-board-1007]] [[feedback-adversarial-advisor]]
