# Task 26 — per-cycle tau (alpha=0.25) 재실험 결과 (2026-04-18)

## 목적
- §6.7.1 per-cycle tau 실험을 기존 `alpha=0.5, K=19`에서
  §6.8 최적 설정인 `alpha=0.25, K=14`로 재수행.
- 같은 조건(`alpha=0.25, K=14`)에서 대조군 2개와 공정 비교:
  1) Binary OM, 2) 단일 `tau=0.3`, 3) per-cycle `tau_c`.

## 실행 조건
- metric: `dft`
- hybrid: `alpha=0.25`
- `octave_weight=0.3`, `duration_weight=1.0`
- `min_onset_gap=0`
- tau 후보: `{0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7}`
- per-cycle 탐색: greedy coordinate descent 1-pass (`K=14` 순회)
- 평가: 각 조건 N=20, Welch t-test

## 결과 요약
- 산출 `K`: **14**
- Binary OM: `JS = 0.01586 ± 0.00152` (N=20)
- tau=0.3: `JS = 0.04300 ± 0.00247` (N=20)
- per-cycle tau_c: `JS = 0.01156 ± 0.00147` (N=20)

### 유의성 (Welch t-test)
- per-cycle vs Binary: `t=-9.0628`, `p=4.94e-11` (**p<0.001**)
- per-cycle vs tau=0.3: `t=-48.8333`, `p=7.02e-31` (**p<0.001**)

## 이전 조건(alpha=0.5) 비교
- 이전 A8 (2026-04-17): `alpha=0.5, K=19, per-cycle JS=0.01489 ± 0.00143`
- 이번 Task 26: `alpha=0.25, K=14, per-cycle JS=0.01156 ± 0.00147`
- 변화: **약 -22.35% 개선** (`(0.014891 - 0.011563) / 0.014891`)

## tau_c 프로파일 (Task A-4 재사용용)
- `tau_profile` (cycle 1~14):
  `[0.7, 0.6, 0.5, 0.7, 0.7, 0.3, 0.1, 0.3, 0.3, 0.1, 0.4, 0.3, 0.2, 0.3]`
- 분포:
  - `0.1`: 2개
  - `0.2`: 1개
  - `0.3`: 5개
  - `0.4`: 1개
  - `0.5`: 1개
  - `0.6`: 1개
  - `0.7`: 3개

## 산출물
- 결과 JSON:
  `docs/step3_data/percycle_tau_dft_alpha025_results.json`
- 실행 스크립트:
  `run_percycle_tau_dft_alpha025.py`
- 캐시 확인:
  `cache/metric_dft_alpha0p25_ow0p3_dw1p0.pkl` 사용(`K=14`, 무결성 통과)

## 결론
- `alpha=0.25` 조건에서도 per-cycle `tau_c`가 두 baseline(Binary, tau=0.3) 대비 모두 유의하게 우수(p<0.001).
- 따라서 **Algo1 최적 overlap 전략으로 per-cycle tau_c 유지 가능**.
