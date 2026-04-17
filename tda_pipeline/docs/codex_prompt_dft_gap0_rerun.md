# Codex 세션 A — gap_min=0 + DFT baseline 통합 재실험

## 배경

1. 기존에 `min_onset_gap=3` (1.5박 제약) 조건으로 §4 전체를 재실험했으나
   (`docs/codex_prompt_dft_baseline_rerun.md`, 2026-04-17 완료),
   청취 평가 결과 onset 간격이 부자연스럽다는 판단으로 **`min_onset_gap=0` 롤백 결정**.

2. 동시에 **bugfix 이후(refine_connectedness 수정, `pipeline.py` ow/dw 전파 버그
   수정)에 생긴 "DFT가 hibari 최적"이라는 결론을 §4 밖으로도 통합**해야 한다.
   현재 §6.7~§6.9는 여전히 **Tonnetz α-hybrid** 기반이고, §7은 **Tonnetz 0.0488
   baseline**을 쓴다. 사용자 결정: §6~§7도 **DFT 기반 hybrid로 재탐색**한다.

3. **`min_onset_gap`은 `generation.py`의 onset 후처리 전용 파라미터**로 PH/OM/거리행렬
   계산과 독립된 레이어임을 확인했다 (`generation.py:209, 243, 769, 813`). 따라서
   DFT × gap0 조합은 이론상 안전하되, **bugfix 이전에 생성된 JSON은 재활용 불가**이다
   (`step3_results.json`은 2026-04-08로 pre-bugfix).

4. 본 프롬프트는 DFT × gap_min=0 × post-bugfix 조건의 전면 재실험을 지시한다.
   기존 gap3 JSON은 비교용으로 유지(삭제 금지), 신규는 `*_gap0_*` 접미사로 저장.

- 파이프라인: `C:\WK14\tda_pipeline\`
- DFT 캐시: `cache/metric_dft.pkl` (존재 확인 후 `from_cache=True` 사용, 없으면 ~15분 PH 재계산)
- 결과 저장: `docs/step3_data/` 하위 JSON

## 실행 방식

`run_dft_gap3_suite.py`를 **`run_dft_gap0_suite.py`로 통째 복사** 후,
`MIN_ONSET_GAP = 0`으로 상수 교체 + 모든 결과 JSON 경로를 `_gap3_` → `_gap0_`로 일괄
치환. 기존 파일은 손대지 않는다. (세션 B가 원본 스크립트를 병렬로 argparse 파라미터화
리팩토링 중이므로, 원본 건드리면 충돌한다.)

## 공통 설정 — Phase 1 (§4 DFT 재실험용)

```python
min_onset_gap = 0         # ★ 롤백
distance_metric = 'dft'
alpha = 0.5               # Tonnetz hybrid α 기본값 (§6.8에서 별도 탐색)
octave_weight = 0.3       # Task A3에서 재확인
duration_weight = 1.0     # Task A2에서 재확인 (DFT 조건 gap3 최적값)
```

## 사전 체크 (필수)

1. `cache/metric_dft.pkl` 존재 여부. 없으면 PH 재계산 ~15분 예고 후 진행.
2. `docs/step3_data/decayed_lag_dft_results.json` 존재 여부. 있다면 Task A4는
   "재실행 불필요"로 보고하고 기존 수치(DFT+decayed −7.1% ★) 재사용.

---

## Phase 1 — §4 DFT + gap0 재실험

### Task A1: §4.1 거리 함수 비교 (N=20)

- frequency / Tonnetz / voice_leading / DFT 4종, 각각 `min_onset_gap=0`, N=20.
- **출력**: `docs/step3_data/step3_results_gap0.json`
- **필수 메타데이터**: `min_onset_gap: 0`, `n_repeats: 20`, `post_bugfix: true`,
  `alpha: 0.5`, `octave_weight: 0.3`, `duration_weight: 1.0`, `date: <iso>`,
  `script: run_dft_gap0_suite.py`.
- **게이트**: DFT가 best인지 확인. best가 아니면 Phase 1·2 중단, 새 baseline 후보 보고.
- **보고**: 각 거리 함수 JS mean±std, DFT vs freq / vs Tonnetz 개선율.

### Task A2: §4.1b Duration Weight (w_d) — DFT + gap0

- `w_d ∈ {0.0, 0.1, 0.3, 0.5, 0.7, 1.0}`, N=10, DFT 고정, `w_o=0.3`.
- **출력**: `docs/step3_data/dw_gridsearch_dft_gap0_results.json`
- **보고**: 최적 w_d, gap3 최적(1.0)과 비교.

### Task A3: §4.1a Octave Weight (w_o) — DFT + gap0

- `w_o ∈ {0.1, 0.3, 0.5, 0.7, 1.0}`, N=10, DFT 고정, Task A2 최적 w_d 사용.
- **출력**: `docs/step3_data/ow_gridsearch_dft_gap0_results.json`
- **보고**: 최적 w_o, gap3 최적(0.3)과 비교.

### Task A4: §4.1c 감쇄 Lag — DFT + Tonnetz × gap0

- 사전 체크에서 기존 JSON 있으면 재실행 불필요.
- 없다면: lag=1 단일 vs lag 1~4 감쇄합산 (λ=0.60, 0.30, 0.08, 0.02),
  DFT·Tonnetz 각각, N=20.
- **출력**: `docs/step3_data/decayed_lag_gap0_results.json` (또는 기존 유지)

### Task A5: §4.2 Continuous OM — DFT + gap0

- (A) Binary / (B) Continuous direct / (C) τ=0.3/0.5/0.7, 모두 DFT, N=20,
  Task A2+A3 최적 (w_d, w_o) 사용.
- **출력**: `docs/step3_data/step3_continuous_dft_gap0_results.json`
- **보고**: 최적 설정, density, gap3(Binary 최적 0.0185)와 비교.

### Task A6: §4.3 DL 모델 — DFT 이진 OM + gap0

- FC(hidden=256, lr=0.001, dropout=0.3, epochs=200), LSTM(2L, h=128),
  Transformer(2L, 4-head, d_model=128). `generate_from_model(..., min_onset_gap=0)`.
  N=5.
- **출력**: `docs/step3_data/dl_comparison_dft_gap0_results.json`
- **보고**: DFT+gap0에서 Transformer 우위가 유지되는지 (gap3에서 0.00276 ★).

### Task A7: §4.3a FC-cont — DFT + gap0

- FC-bin vs FC-cont (hidden=128, lr=0.001, dropout=0.3, epochs=200), N=5.
- **출력**: `docs/step3_data/fc_cont_dft_gap0_results.json`

---

## Phase 2 — §6.7~§6.9 DFT-hybrid 재탐색

Phase 1 완료 후 Task A2·A3의 최적 (w_d, w_o)를 고정해서 진행.

### Task A8: §6.7.1 Per-cycle τ — DFT 기반 재실험 (N=20)

- 기존 `percycle_tau_n20_results.json`은 Tonnetz α=0.5 기반 → 재실험 필수.
- 균일 τ=0.35 baseline vs greedy per-cycle τ_c (coordinate descent,
  τ ∈ {0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7}), **DFT continuous OM 기준**, N=20.
- **출력**: `docs/step3_data/percycle_tau_dft_gap0_results.json`
- **보고**: baseline·percycle JS, 개선율, Welch t-test. gap3 Binary DFT 0.0185와
  비교.

### Task A9: §6.7.2 Soft activation × DL 아키텍처 — DFT 기반 (N=5)

- FC / LSTM / Transformer 각 모델에 binary vs continuous 입력 비교, DFT 기준, N=5.
- **출력**: `docs/step3_data/soft_activation_dft_gap0_results.json`
- **보고**: DFT 조건에서 "Transformer vs FC 최우수" 가설 재검증. Tonnetz(FC 우위) 대비
  DFT(Transformer 우위)가 continuous 입력에서도 유지되는지.

### Task A10: §6.8 + §6.9 — DFT-hybrid α grid + Complex 통합 재탐색

두 단계로 수행:

**(A10-a) DFT α-hybrid grid (N=20)**

- hybrid 거리: $d_\text{hybrid} = \alpha \cdot d_\text{freq} + (1-\alpha) \cdot d_\text{DFT}$
  (§6.8는 Tonnetz hybrid였음. DFT로 치환).
- α ∈ {0.0, 0.1, 0.25, 0.3, 0.5, 0.7, 1.0}, N=20, timeflow 모드, 다른 파라미터는 Phase 1
  최적값 고정.
- **출력**: `docs/step3_data/alpha_grid_dft_gap0_results.json`
- **보고**: α별 K, JS, 최적 α (gap3 Tonnetz grid의 α=0.25와 비교).

**(A10-b) Complex 모드 × DFT-hybrid × per-cycle τ (N=20)**

- A10-a 최적 α를 중심으로 grid: α ∈ {best-0.25, best, best+0.25},
  w_o ∈ {0.0, Phase1_best}, dw ∈ {Phase1_best}, r_c ∈ {0.1, 0.3}, N=5 먼저.
  최우수 조합을 N=20 재검증.
- per-cycle τ_c는 greedy coordinate descent.
- Algo1·Algo2(FC / Transformer 둘 다) 모두 보고.
- **출력**: `docs/step3_data/complex_percycle_dft_gap0_results.json`
- **보고**: DFT-complex 최저 JS와 기존 Tonnetz-complex (실험 B JS=0.0183 / Algo2
  FC=0.0003)와 비교. "절대 최저"가 DFT로 전환되는지 확정.

---

## Phase 3 — §7 DFT baseline 재설정

### Task A11: §7 full-song Tonnetz baseline → DFT baseline 교체

- §7의 모든 비교 기준을 Phase 1·2 결과로 갱신: 새 `full-song DFT` baseline JS 값
  (Task A1 DFT 또는 Task A5 Binary DFT 최적) 을 §7 모듈 생성의 비교축으로 설정.
- **실험 자체 재실행은 불필요** (§7의 module 생성 결과는 거리 함수와 독립). baseline 표
  갱신 정보만 정리해서 보고.
- **출력**: JSON 없음. 보고서 한 블록. (세션 D가 §7 서술 수정 시 참조.)

---

## 전체 실행 순서

```
사전 체크 (캐시, 기존 JSON)
    ↓
Task A1 (게이트)
    ↓  DFT best 유지 시
Task A2 → Task A3 (파라미터 grid, 직렬)
Task A4 (lag, 독립)
    ↓
Task A5 (continuous OM)
    ↓
Task A6 + Task A7 (DL, 병렬)
    ↓
Phase 2: Task A8 → Task A9 → Task A10
    ↓
Phase 3: Task A11 (정리)
```

## 주의사항

1. **`min_onset_gap=0` 명시 필수**: 모든 `algorithm1_optimized`·`generate_from_model`
   호출. 기본값 의존 금지.
2. **metric 통일**: 모든 호출에서 `distance_metric='dft'` 명시.
3. **기존 JSON 보존**: `*_gap3_*.json`, Tonnetz 기반 기존 JSON 모두 유지.
4. **메타데이터 표준**: 생성하는 모든 JSON 최상위에 `metric`, `min_onset_gap`,
   `n_repeats`, `alpha`, `octave_weight`, `duration_weight`, `date`, `script`,
   `post_bugfix: true` 필드 포함.
5. **Task A1 게이트**: DFT가 best 아니면 즉시 중단, 새 baseline 후보 보고.
6. **Phase 2 Task A9 게이트**: DFT 조건에서 Transformer가 FC보다 우위인지 확인 후
   Task A10 Algo2 모델 선택.
7. **논문 수정 금지**: short.md / full.md는 세션 D 담당. JSON 생성·보고까지만.
