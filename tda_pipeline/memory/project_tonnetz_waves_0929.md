# 시안 C — 종달새와 문어 (2026-09-29)

명세·결과 전부: `docs/tonnetz_lenia_spec.md` (§8 1판 결과, §9 2판 설계, §9.8 2판 결과).

## 페이지
- 1판 `lenia/tonnetz.html` — 종달새(오른손 32)·문어(왼손 33)가 격자 위를 기어가는 행위자. 몸 = 부른 음의 역사를 박자틀 32 로 접은 그림
  (오른손 곧은 날개, 왼손 말린 팔 — V4 로 확인, 그린 것이 아님). 사용자: "느낌 나쁘지 않다. automata 형태 … 반영되진 않았지만".
- 2판 `lenia/waves.html` — 칸이 흥분성 매질(확률 GH, 288칸). 전도 = 정본 경로의 rate 별 음 거리(intra + rate·inter). rate = 두 손 거리.
  바코드 띠(고리 41개의 vine)를 손으로 채운다. 누르기 = 종달새(동심 파문), 긋기 = 문어(회전 원천, 말린 팔), 원천 끌기 = rate 바꾸기.

## 데이터 (lenia/tonnetz.json, experiments/export_tonnetz_lenia_data.py)
- Tonnetz α=0.5 정본 경로(use_decayed=False) K=41 — 캐시 metric_tonnetz.pkl(K=47)은 다른 설정이라 안 쓴다.
- vines: 13개 rate 0 전용, 8개 전 구간, 20개 결합 구간. dist_grid: rate 0.0~1.5(0.1) 23×23 거리.

## 검증 (재현)
- `python experiments/run_cycle_markov.py` → cycle_markov_results.json (고리 순회 순서 ≠ 선율 정보)
- `node tools/verify_tonnetz_lenia.mjs` (+ `--only=v5b`) → tonnetz_lenia_verify*.json (1판 V1~V6)
- `node tools/verify_waves.mjs` → waves_verify.json (2판 W2~W7; 1차 waves_verify_run1.json)

## 남은 것
- 2판 사용자 판정. W4(전도가 소리에 닿지 않음)·W7(매질이 수축하지 않음) 설계 결정.
