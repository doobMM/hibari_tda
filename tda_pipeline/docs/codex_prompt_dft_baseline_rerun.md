# Codex 세션 A — DFT baseline 전체 재실험 프롬프트

## 배경

1. **DFT baseline 통일**: 현재 §4.1b, §4.2, §4.3, §4.3a가 Tonnetz 기반으로 실험됨. §4.1에서 DFT가 hibari 최적이므로 이후 실험을 DFT로 재실험해야 함.
2. **gap_min 통일**: 모든 실험에서 `min_onset_gap=3` (1.5박 간격 제약)을 적용. 기존 실험들(§4.1 포함)은 gap_min=0으로 수행됐으므로 전면 재실험 필요.
3. **게이트 실험 우선**: 이후 Task 26~30은 모두 "DFT가 gap_min=3에서도 여전히 hibari 최적 baseline인가?"라는 전제를 깔고 있다. 따라서 **Task 25를 가장 먼저 실행**해서 DFT 우위가 유지되는지 확인해야 한다.

- 파이프라인: `C:\WK14\tda_pipeline\`
- DFT 캐시 후보: `cache/metric_dft.pkl`
- 결과 저장: `docs/step3_data/` 아래 JSON

---

## 실행 전 체크리스트

1. `cache/metric_dft.pkl` 존재 여부를 **먼저 확인**한다.
2. 파일이 있으면 `from_cache=True`로 진행한다.
3. 파일이 없으면 PH를 DFT 기준으로 재계산해야 하며, **약 15분 소요 가능**을 먼저 보고한 뒤 진행한다.
4. **Task 25 결과를 본 뒤**에만 Task 26~30으로 넘어간다.
5. 만약 Task 25에서 DFT가 best가 아니면, 이후 DFT 전용 재실험은 보류하고 새 baseline 후보를 먼저 보고한다.

---

## 공통 설정 (모든 Task에 적용)

```python
# 모든 generate/algorithm 호출에 반드시 포함
min_onset_gap = 3      # gap_min=3 (1.5박 간격 제약)
distance_metric = 'dft'
octave_weight = 0.3    # §4.1a 최적값 (Task 27에서 DFT 조건으로 재확인)
duration_weight = 0.3  # §4.1b 최적값 (Task 26에서 DFT 조건으로 재확인)
```

---

## Task 25: §4.1 거리 함수 비교 (N=20) — gap_min=3 재실험

**목표**: frequency / Tonnetz / voice_leading / DFT 4종을 **gap_min=3** 조건에서 N=20 반복 실험.

**참조**: 기존 `run_step3_unified.py`, `step3_results.json`.

**설정**:
- algorithm1_optimized 호출 시 `min_onset_gap=3`
- N=20 반복, 각 거리 함수마다 독립 실행

**출력**: `docs/step3_data/step3_results_gap3.json`

```json
{
  "n_repeats": 20,
  "frequency": { "js_divergence": { "mean": ..., "std": ... }, "K": ..., "coverage": ... },
  "tonnetz":   { ... },
  "voice_leading": { ... },
  "dft":       { ... }
}
```

**보고**: 각 거리 함수 JS mean ± std, DFT vs frequency 개선율.

---

## Task 26: §4.1b Duration Weight (w_d) — DFT + gap_min=3 재실험

**목표**: `w_d ∈ {0.0, 0.1, 0.3, 0.5, 0.7, 1.0}` grid를 DFT + gap_min=3 조건에서 N=10.

**출력**: `docs/step3_data/dw_gridsearch_dft_results.json`

```json
{
  "0.0": { "mean": ..., "std": ..., "K": ... },
  "0.1": { ... },
  ...
}
```

**보고**: 최적 w_d와 JS, w_d=0.3 유지 여부.

---

## Task 27: §4.1a Octave Weight (w_o) — DFT + gap_min=3 재실험

**목표**: `w_o ∈ {0.1, 0.3, 0.5, 0.7, 1.0}` grid를 DFT + gap_min=3 조건에서 N=10.
Task 26 최적 w_d 사용.

**출력**: `docs/step3_data/ow_gridsearch_dft_results.json`

```json
{
  "0.1": { "mean": ..., "std": ..., "K": ... },
  ...
}
```

**보고**: 최적 w_o, w_o=0.3 유지 여부.

---

## Task 28a: §4.1c 감쇄 Lag — DFT + gap_min=3 재실험

**목표**: lag=1 단일 vs lag 1~4 감쇄합산을 DFT와 Tonnetz 두 조건으로 비교, gap_min=3.

**설정**:
- lag=1 단일: `W_inter = W_inter^(1)`
- lag 1~4 감쇄: `lambda = (0.60, 0.30, 0.08, 0.02)`
- 거리 함수: DFT, Tonnetz 각각, N=20

**출력**: `docs/step3_data/decayed_lag_gap3_results.json`

```json
{
  "DFT_lag1":     { "mean": ..., "std": ... },
  "DFT_lag1to4":  { "mean": ..., "std": ... },
  "Tonnetz_lag1": { "mean": ..., "std": ... },
  "Tonnetz_lag1to4": { "mean": ..., "std": ... }
}
```

**보고**: DFT에서 개선율(%), p값. Tonnetz에서 변화.

---

## Task 28: §4.2 Continuous OM — DFT + gap_min=3 재실험

**목표**: DFT 기반 binary OM baseline + continuous OM 5종 비교, N=20, gap_min=3.
Task 26+27 최적 w_d, w_o 사용.

**설정**: (A) Binary / (B) Continuous direct / (C) τ=0.3/0.5/0.7, 모두 DFT 거리.

**출력**: `docs/step3_data/step3_continuous_dft_gap3_results.json`

```json
{
  "n_repeats": 20,
  "A_binary":            { "js_divergence": { "mean": ..., "std": ... }, "density": ... },
  "B_continuous_direct": { ... },
  "C_tau_0.3":           { ... },
  "C_tau_0.5":           { ... },
  "C_tau_0.7":           { ... }
}
```

**보고**: 최적 τ, A→최적 개선율.

---

## Task 29: §4.3 DL 모델 비교 — DFT 이진 OM + gap_min=3

**목표**: FC / LSTM / Transformer를 DFT 기반 이진 OM 입력으로 학습+생성, N=5, gap_min=3.

**설정**:
- FC: hidden=256, lr=0.001, dropout=0.3, epochs=200
- LSTM: 2-layer, hidden=128
- Transformer: 2-layer, 4-head, d_model=128
- generate_from_model 호출 시 `min_onset_gap=3`

**출력**: `docs/step3_data/dl_comparison_dft_gap3_results.json`

```json
{
  "FC":          { "js_mean": ..., "js_std": ..., "val_loss": ... },
  "LSTM":        { ... },
  "Transformer": { ... }
}
```

---

## Task 30: §4.3a FC-cont — DFT + continuous + gap_min=3

**목표**: FC-bin vs FC-cont (DFT 기반), N=5, gap_min=3.

**설정**: FC (hidden=128, lr=0.001, dropout=0.3, epochs=200).

**출력**: `docs/step3_data/fc_cont_dft_gap3_results.json`

```json
{
  "FC_bin":  { "js_mean": ..., "js_std": ... },
  "FC_cont": { "js_mean": ..., "js_std": ... }
}
```

---

## 전체 실행 순서

```
사전 체크: cache/metric_dft.pkl 확인
    ↓
Task 25 (거리 함수 비교)  ←── 반드시 가장 먼저 실행
    ↓
DFT best 유지 시에만 아래 진행
    ↓
Task 26 (w_d grid)        ←── 독립 실행 가능
Task 27 (w_o grid)        ←── Task 26 완료 후
Task 28a (lag)            ←── 독립 실행 가능
    ↓
Task 28 (continuous OM)   ←── Task 26+27 완료 후
    ↓
Task 29 + 30 (DL)         ←── 병렬 실행 가능
```

Task 31 (D 세션): 완료된 JSON으로 논문 §4.1~§4.3a 표 전면 갱신.

---

## 주의사항

1. **gap_min=3 누락 금지**: `algorithm1_optimized(..., min_onset_gap=3)`, `generate_from_model(..., min_onset_gap=3)` 명시 필수.
2. **DFT 캐시 활용 전 확인**: `cache/metric_dft.pkl` 존재 여부를 먼저 체크하고, 있을 때만 `from_cache=True` + `metric='dft'`를 사용. 없으면 PH 재계산이 필요하며 약 15분 걸릴 수 있다.
3. **config.py 필드**: `PipelineConfig`의 `distance_metric`, `octave_weight`, `duration_weight` 사용.
4. **결과 불일치 예상**: gap_min=3 + DFT 조합은 기존 Tonnetz + gap_min=0과 수치가 크게 달라질 수 있음. D 세션에서 논문 전면 재서술 필요.
5. **Task 25가 게이트**: DFT가 여전히 최적인지 gap_min=3 조건에서 재확인 후 진행. DFT가 1위가 아니면 Task 26~30은 즉시 멈추고 새 baseline 기준으로 계획을 다시 잡는다.
