# A 세션 프롬프트 (2026-04-13 Control Tower 작성)

> 아래 내용을 A 세션 시작 시 그대로 붙여넣기.

---

A 세션이야. 체크리스트는 `docs/checklist_0413.md`에 있어.
오늘 할 실험은 A-1 ~ A-4까지 4건이야. 순서대로 진행해줘.

## A-1. 통합 조합 실험 (★★★ 최고 우선)

지금까지 hibari에서 **독립적으로** 발견된 3개 최적 파라미터를 **동시에** 적용하여 시너지를 검증해야 해.

**적용할 설정:**
- `octave_weight = 0.3` (기존 0.5 → JS -18.8%, `run_tonnetz_octave_tuning.py` 결과)
- `α = 0.0` (순수 Tonnetz, 기존 0.5 → JS -3.4%, `run_alpha_grid_search.py` 결과)
- 감쇄 lag 가중치 (lag 1~4, w=[0.4, 0.3, 0.2, 0.1]) — 이건 이미 `pipeline.py`에 반영됨

**주의:** ow와 α를 바꾸면 distance matrix가 달라지므로 **캐시(pkl) 재계산이 필수**야. 기존 `cache/metric_tonnetz.pkl`은 ow=0.3, α=0.0 기준이 아닐 수 있어.

**참고 스크립트:** `run_alpha_grid_search.py`가 α를 바꾸면서 PH를 처음부터 재계산하는 패턴을 갖고 있어. 이 구조를 베이스로 하되:
- α를 0.0 고정
- octave_weight를 0.3 고정
- 감쇄 lag는 pipeline.py의 `compute_inter_weights_decayed()` 사용 확인
- N=20 반복, Algo1 JS 측정

**비교 기준 (개별 실험 결과):**
| 설정 | JS mean | 출처 |
|---|---|---|
| ow=0.5, α=0.5, lag=1 (구 기본) | 0.0590 | §3.1 baseline |
| ow=0.3, α=0.5, lag=1 | 0.0479 | tonnetz_octave_tuning |
| ow=0.5, α=0.0, lag=1 | 0.0574 | alpha_grid_search |
| ow=0.5, α=0.5, lag 1~4 감쇄 | 0.0121 | decayed_lag (memory) |
| **ow=0.3, α=0.0, lag 1~4 감쇄** | **???** | **이번 실험** |

**결과 저장:** `docs/step3_data/combined_optimal_results.json`
**스크립트:** `run_combined_optimal.py` 신규 작성 또는 기존 스크립트 활용

---

## A-2. Per-cycle τ_c N=20 재검증

`run_section77_experiments.py`의 `experiment_percycle_tau()` 함수가 N=5 greedy로 per-cycle τ_c를 탐색했어. 결과: JS 0.0464 → 0.0238 (+48.6%). 이걸 N=20으로 올려서 통계적 신뢰를 확보해야 해.

**방법:**
1. `experiment_percycle_tau(data, n_eval=5)` → `n_eval=20`으로 변경하거나 별도 호출
2. 기존 greedy로 찾은 최적 τ_c 벡터를 고정한 채 N=20 평가만 반복하는 것이 더 적절할 수 있어 (greedy 탐색 자체를 20번 반복하면 시간이 너무 오래 걸림)
3. baseline(전체 τ=0.35)도 N=20으로 같이 돌려서 p-value 계산

**핵심:** greedy 탐색으로 찾은 τ_c 벡터가 **과적합이 아닌지** 확인하는 것이 목표.

**결과 저장:** `docs/step3_data/percycle_tau_n20_results.json`
**출력 포함:** js_mean, js_std, baseline과의 t-test p-value, 최적 τ_c 벡터

---

## A-3. Soft activation 아키텍처 확장

`run_section77_experiments.py`의 `experiment_soft_activation_algo2()` 함수가 **FC만** 테스트했어. 결과: binary→continuous 입력으로 바꿨더니 JS +64.3%, val_loss 10배 감소.

이걸 **Transformer와 LSTM에도** 적용해봐야 해.

**방법:**
- `experiment_soft_activation_algo2()` 함수를 확장하거나 별도 함수 작성
- 기존 함수(line 204~313)에서 `MusicGeneratorFC` 부분을 `MusicGeneratorLSTM`, `MusicGeneratorTransformer`로 교체
- Transformer의 경우 `use_pos_emb=True/False` 두 가지도 비교하면 좋지만, 기본은 True로 시작
- 각 모델별 binary vs continuous 비교

**기대 출력 형태:**
```json
{
  "FC": {"binary": {"js_mean": ..., "val_loss": ...}, "continuous": {...}, "improvement_pct": ...},
  "LSTM": {"binary": {...}, "continuous": {...}, "improvement_pct": ...},
  "Transformer": {"binary": {...}, "continuous": {...}, "improvement_pct": ...}
}
```

**참고:** `generation.py`에 `MusicGeneratorFC`(line 549), `MusicGeneratorLSTM`(line 576), `MusicGeneratorTransformer`(line 605) 세 클래스가 이미 있어.

**결과 저장:** `docs/step3_data/soft_activation_all_models.json`

---

## A-4. 최종 최적 설정 확정

A-1~3 결과를 종합해서 **hibari 최종 최적 설정**을 확정하고, 그 설정으로 Algo1 + Algo2(최적 모델) N=20을 돌려.

**의사결정 흐름:**
1. A-1에서 통합 조합의 JS 확인
2. A-2에서 per-cycle τ가 유효하면 → A-1 설정에 per-cycle τ 추가
3. A-3에서 FC 외에 더 좋은 모델이 나오면 → 해당 모델 사용
4. 최종 설정으로 Algo1 N=20 + Algo2 N=20 실행

**비교 대상:** 현재 최고 기록 = 개선 F (Continuous + FC), JS 0.0004

**결과 저장:** `docs/step3_data/final_optimal_results.json`

---

## 세션 완료 시 해야 할 것

1. 모든 결과 JSON이 `docs/step3_data/`에 저장되었는지 확인
2. `docs/checklist_0413.md`에서 완료 항목을 `[x]`로 업데이트
3. 핵심 수치 요약을 간단히 출력 (Control Tower가 확인용)
