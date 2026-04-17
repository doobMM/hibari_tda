# 세션 B 리포트 — 디버깅·리팩토링 결과

2026-04-17, 세션 B.

## 요약

| 항목 | 상태 |
|---|---|
| Task 1-1 (Task 23 커밋 분리) | ✓ 완료 — `080b9fe`로 기커밋 확인 |
| Task 1-2 (min_onset_gap 감사) | ✓ 완료 — 아래 표 |
| Task 1-3 (JSON 메타 누락) | ✓ 완료 — `scripts/audit_json_meta.py` |
| Task 1-4 (파라미터 전파 회귀) | ✓ 완료 — `diagnose_param_propagation.py` |
| Task 2-1 (PipelineConfig) | 완료 — 아래 변경 |
| Task 2-3 (result_meta) | 완료 — `utils/result_meta.py` |
| Task 2-2 (run_dft_suite) | 완료 — `git mv`+argparse |
| Task 2-4 (하드코딩 제거) | 완료 — module_generation.py / run_temporal_reorder_unified.py |
| Task 3-1 (gap3 재현) | 완료 |
| Task 3-2 (gap0 회귀) | 완료 |

## 1-1. Task 23 커밋 분리

`config.py`의 `MetricConfig.duration_weight` 필드 추가 + `pipeline.py`의
`_apply_metric` ow/dw 전달 수정은 **이미 `080b9fe` 커밋에 반영**되어 있음.
`git diff HEAD -- tda_pipeline/config.py tda_pipeline/pipeline.py`는 빈 결과.
별도 분리 불필요.

## 1-2. `min_onset_gap` 전파 경로 감사

| 위치 | 값 | 구분 |
|---|---|---|
| `generation.py:209` | default `0` | 함수 시그니처 |
| `generation.py:769` | default `0` | 함수 시그니처 |
| `pipeline.py:603-662` `run_generation_algo1` | 호출 없음 → 기본 `0` | **기본값 의존** |
| `pipeline.py:664-735` `run_generation_algo2` | Algo2 생성은 학습까지만, 생성 호출은 외부에서 → 적용 안됨 | — |
| `module_generation.py:203` | default `0` | 함수 시그니처 |
| `module_generation.py:365` | **`3` 하드코딩** | 버그 흔적 |
| `module_generation.py:373` | **`3` 하드코딩** | 버그 흔적 |
| `run_temporal_reorder_unified.py:309` | `0` 하드코딩 (명시적) | 의도된 0 |
| `dashboard.py:331, 387` | `min_gap` 외부 입력 | 정상 |
| `run_dft_gap3_suite.py` | 모듈 상수 `MIN_ONSET_GAP=3` | Task 2-2 대상 |
| `run_dft_gap0_suite.py` | 모듈 상수 `MIN_ONSET_GAP=0` | 세션 A 소유, 건드리지 않음 |
| `gen_gap3_comparison.py` | 함수 인자로 명시 전달 (0 혹은 3) | 정상 |

**기본값 의존으로 "의도되지 않은 0이 들어가는" 위치**: `pipeline.py`의 Algo1 (수정됨: 2-1).

## 1-3. JSON 메타데이터 누락 감사

`scripts/audit_json_meta.py`로 `docs/step3_data/*.json` 53개 전수조사.

요구 필드: `metric, alpha, octave_weight, duration_weight, min_onset_gap` 5종.

### 결과

- 모두 갖춘 JSON: **3개**
  - `dl_comparison_dft_gap3_results.json`
  - `fc_cont_dft_gap3_results.json`
  - `step3_continuous_dft_gap3_results.json`
- 누락 JSON: **50개**

세션 B 이후 생성분부터 `utils.result_meta.build_result_header`로 표준 헤더를
자동 주입 (Task 2-3). **기존 JSON에는 소급 적용 금지.**

### 특별히 주의 필요 (4/11~4/15 생성, 메타 누락 확인됨)

`soft_activation_all_models.json`, `complex_percycle_n20_results.json`,
`percycle_tau_n20_results.json`, `step3_continuous_results.json`,
`final_optimal_results.json`, `step_improvementF_results.json` — 모두 요구 필드
5종 전부 누락. 논문 수치로 이미 소비되었으므로 코드 역추적 및 memory 기반으로
논문 본문에 조건 명시 완료된 것들만 해당 JSON을 그대로 유지.

## 1-4. 회귀 테스트

`diagnose_param_propagation.py`가 동일 seed로 `min_onset_gap=0`/`3` 두 번 실행,
차이가 onset 필터링 결과에만 국한되는지 증명. 기대 로그:

- K (total cycles), cycle ids: 동일
- activation mask hash: 동일 (binary overlap 기준)
- 생성 결과: `gap=0` 쪽이 노트 수 더 많음

## 2-1. PipelineConfig 확장

- `PipelineConfig`에 `min_onset_gap: int = 0`, `post_bugfix: bool = True` 추가.
- `pipeline.py::run_generation_algo1`가 `config.min_onset_gap`을 읽어
  `algorithm1_optimized`에 전달.

## 2-2. run_dft_suite.py

`run_dft_gap3_suite.py` → `run_dft_suite.py`로 git mv.
argparse: `--gap-min`, `--n-repeats`, `--metric`, `--alpha`, `--out-suffix`.
하드코딩 `MIN_ONSET_GAP=3` 및 `_gap3_` 문자열 전부 제거.

**주의**: 세션 A의 `run_dft_gap0_suite.py`는 건드리지 않음 (세션 A 병렬 실행 중).

## 2-3. JSON 메타 표준

`utils/result_meta.py::build_result_header(config, script_name, n_repeats, extra)`.
반환: `{metric, min_onset_gap, alpha, octave_weight, duration_weight,
n_repeats, date(ISO 8601), script, post_bugfix, commit_sha}`.

## 2-4. 하드코딩 제거

- `module_generation.py:365, 373`: `min_onset_gap=3` → argparse `--gap-min`
  (미지정 시 `PipelineConfig().min_onset_gap` 기본 0) 사용.
- `run_temporal_reorder_unified.py:309`: `0` 명시적 의도 유지하되 주석으로 이유 기록.

## 3-1. gap3 재현 회귀 검증

```
python run_dft_suite.py --task 25 --gap-min 3 --out-suffix regression_gap3
```

결과 `step3_results_regression_gap3.json`을 기존 `step3_results_gap3.json`과 비교:

| metric | 기존 JS mean | 기존 JS std | 신규 JS mean | 신규 JS std | 차이 |
|---|---|---|---|---|---|
| frequency | 0.0319 | 0.00270 | 0.0319 | 0.00270 | 비트 단위 동일 |
| tonnetz | 0.0554 | 0.00550 | 0.0554 | 0.00550 | 비트 단위 동일 |
| voice_leading | 0.0619 | 0.00335 | 0.0619 | 0.00335 | 비트 단위 동일 |
| dft ★ | 0.0289 | 0.00379 | 0.0289 | 0.00379 | 비트 단위 동일 |

**리팩토링이 수치를 바꾸지 않음 확인.**

## 3-2. gap0 기본값 회귀 검증

```
python run_dft_suite.py --task 25 --gap-min 0 --out-suffix regression_gap0
```

| metric | JS mean | JS std |
|---|---|---|
| frequency | 0.0344 | 0.0023 |
| tonnetz | 0.0493 | 0.0038 |
| voice_leading | 0.0566 | 0.0027 |
| dft ★ | **0.0213** | 0.0021 |

CLAUDE.md "§3.1 DFT 0.0211★" 수치와 0.0002 이내 일치 (seed_base 차이 수준).
**기본값이 gap=0으로 바뀐 후에도 post-bugfix 수치가 안정적으로 재현됨.**

## 3-3. 파라미터 전파 회귀 (diagnose)

```
python scripts/diagnose_param_propagation.py --gap-a 0 --gap-b 3 --seed 42 --skip-ow
```

- K (homology 수): **3** 동일
- cycle_ids: `[0, 1, 2]` 동일
- overlap_hash: `3f888ecb2d08` 동일
- 생성 노트 수: gap=0이 1615개, gap=3이 936개 (onset 필터링 효과)

**`min_onset_gap`은 PH/overlap을 건드리지 않고 onset 필터링에만 영향** — 보장 확인.
