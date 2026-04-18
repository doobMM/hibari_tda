# Metric Axiom Numeric Verification (hibari, 2026-04-18)

## 목적
- §2.4의 네 거리 함수 `frequency / tonnetz / voice_leading / dft`가
  metric axiom(비음수, 동일성, 대칭성, 삼각부등식)을 만족하는지 hibari 23-note 공간에서 수치 검증.

## 실행 정보
- 스크립트: `scripts/verify_metric_axioms.py`
- 입력 곡: `Ryuichi_Sakamoto_-_hibari.mid`
- note space: 23개 (`notes_label`)
- tolerance: 절대오차 `1e-9`
- 결과 JSON: `docs/step3_data/metric_axiom_verification.json`

## 결과 요약
- `frequency`
  - 비음수: PASS
  - 동일성: **FAIL (23)**
  - 대칭성: PASS
  - 삼각부등식: **FAIL (1327)**
- `tonnetz`
  - 4개 공리 모두 PASS
- `voice_leading`
  - 4개 공리 모두 PASS
- `dft`
  - 비음수: PASS
  - 동일성: **FAIL (66)**
  - 대칭성: PASS
  - 삼각부등식: PASS

## 주요 위반 샘플
- frequency 동일성 위반(대각 비영):
  - label 13, note `(65, 5)`, `d(i,i)=7.25`
- frequency 삼각부등식 위반(최대):
  - `(i,j,k)=(21,10,21)`, `d(i,k)=7.25`, `d(i,j)+d(j,k)=0.005128...`, excess `7.244871...`
- dft 동일성 위반(비대각 0):
  - `(i,j)=(1,2)`, notes `(52,2)` vs `(53,2)`, `d(i,j)=0.0`

## 해석 메모
- `tonnetz`, `voice_leading`은 수치적으로 metric 조건을 충족.
- `frequency`는 현재 파이프라인 거리행렬(인접도 역수 refine) 기준에서 metric이 아님.
- `dft` 구현은 단일 pitch-class indicator의 DFT magnitude를 사용하므로, 같은 octave/duration의 서로 다른 pitch class 쌍에서 0거리가 발생해 동일성이 깨짐.
