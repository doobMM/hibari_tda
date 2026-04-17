# 세션 B — 전반적 디버깅 + 리팩토링

## 배경

1. 최근 버그픽스 2건(refine_connectedness, pipeline.py ow/dw 전파)으로 이전 JSON이
   대량 무효화되었고, 이를 체계적으로 관리할 기반이 없다. **JSON 메타데이터 표준 부재**가
   논문 검수에서 "이 수치가 어떤 조건에서 나왔나?"를 매번 코드 역추적하게 만든다.

2. `min_onset_gap` 파라미터가 `PipelineConfig`에 공식 필드로 없고, 각 함수 호출부마다
   명시 전달되는 구조. 전역 변경(3→0)이 빈번해질 것이 확인됨.

3. `run_dft_gap3_suite.py`가 `MIN_ONSET_GAP=3` + 결과 파일명 `*_gap3_*`를 상수로
   고정. 재사용 어려움.

4. Task 23 (`pipeline.py` ow/dw 버그 수정) 이 **미커밋 상태**로 다른 변경과 섞여 있음
   (`git status` 확인 요망).

5. 세션 A(Codex)가 병렬로 `run_dft_gap3_suite.py`를 **통째 복사**해서 gap0 재실험
   중이다. 본 세션은 원본 파일을 리팩토링하되 A의 복사본은 건드리지 않는다.

## 작업 1 — 디버깅

### 1-1. Task 23 커밋 분리

- `git status` / `git diff config.py pipeline.py` 확인. ow/dw 버그 수정분이 섞여
  있다면 **별도 커밋**으로 분리.
- 커밋 메시지 예: `fix(pipeline): config.duration_weight 필드 + _apply_metric 경유 전달`.
- 기존 커밋 `080b9fe`와 중복·연관 여부 확인.

### 1-2. `min_onset_gap` 전파 경로 감사

- `Grep min_onset_gap` 전체 → 호출부 리스트업:
  - `generation.py` (L209, 243, 769, 813)
  - `dashboard.py` (L331, 387)
  - `module_generation.py` (L203, 222, 254, 365, 373)
  - `run_dft_gap3_suite.py` (여러 곳, MIN_ONSET_GAP 상수)
  - `run_temporal_reorder_unified.py` (L309, hardcoded 0)
  - `gen_gap3_comparison.py` (L111, 138, 182, ...)
- 각 호출부가 **명시 전달**인지 **기본값 의존**인지 태그. 기본값 의존 위치를 `report.md`에
  정리.
- `module_generation.py:365, 373`에 `min_onset_gap=3` 하드코딩 확인. 해당 파일은
  제3자 리팩토링 대상.

### 1-3. 거리 함수·OM 조건 명시 여부 점검

- 모든 `run_*.py`에서 생성하는 JSON을 검사하여, `metric` / `alpha` / `octave_weight` /
  `duration_weight` / `min_onset_gap` 중 **누락 필드가 있는 JSON 목록** 작성.
- 특히 `soft_activation_all_models.json`, `complex_percycle_n20_results.json`,
  `percycle_tau_n20_results.json`, `step3_continuous_results.json`, `final_optimal_results.json`,
  `step_improvementF_results.json` 확인 (4/11~4/15 생성, 메타데이터 누락 확인됨).

### 1-4. 파이프라인 파라미터 전파 회귀 테스트

- `diagnose_param_propagation.py` 작성: 동일 seed·N=3으로 Algorithm 1을 두 번 실행하되
  `min_onset_gap=0`과 `min_onset_gap=3`만 다르게 해서, 차이가 **onset 필터링 결과에만**
  국한되는지 증명. 출력: 각 실행의 K, cycle ids, activation mask hash, seed log.
- 같은 구조로 `octave_weight=0.3` vs `octave_weight=0.5` 대비 테스트 — 거리 행렬·K 변화만
  발생하고 downstream은 결정적인지 확인.

## 작업 2 — 리팩토링

### 2-1. `PipelineConfig` 확장

- `config.py`에 필드 추가:
  - `min_onset_gap: int = 0` (새 기본값)
  - `post_bugfix: bool = True` (스냅샷 태그)
- `pipeline.py`가 두 필드를 읽어 하위 호출(Algorithm 1/2)에 자동 전달. 기존 호출부
  시그니처는 유지하되 `None`이면 config 값을 사용하는 방향.

### 2-2. `run_dft_gap3_suite.py` 파라미터화

- 파일을 **`run_dft_suite.py`로 `git mv`**, argparse 추가:
  - `--gap-min N` (기본 0)
  - `--n-repeats N` (기본 20)
  - `--metric dft|tonnetz|...` (기본 dft)
  - `--alpha X` (기본 0.5)
  - `--out-suffix STR` (기본 `gap{N}`)
- 결과 JSON 경로는 suffix 기반 동적 생성: `*_gap{N}_results.json`.
- 기존 하드코딩 `MIN_ONSET_GAP = 3` 및 `_gap3_` 문자열 **전부 제거**.
- 파일 상단 docstring에 사용 예 추가:

  ```
  python run_dft_suite.py --gap-min 0 --n-repeats 20
  python run_dft_suite.py --gap-min 3 --n-repeats 20   # 비교 재현용
  ```

- **주의**: 세션 A는 이 파일을 통째 복사해서 별도 스크립트로 실행 중이므로, 본 리팩토링이
  A의 작업에 영향을 주지 않는다. 하지만 `git mv` 전에 `git status`로 A의 미커밋 복사
  스크립트가 어느 이름인지 확인.

### 2-3. JSON 메타데이터 표준화

- 유틸 함수 `utils/result_meta.py::build_result_header(config, script_name, n_repeats, extra=None)`
  추가. 반환값은 dict:

  ```
  {metric, min_onset_gap, alpha, octave_weight, duration_weight, n_repeats,
   date (ISO 8601), script, post_bugfix, commit_sha}
  ```

- 모든 `run_*.py` (최소: `run_dft_suite.py` + Task A8~A10에서 작성될 세션 A 스크립트들)에
  이 헤더를 결과 JSON 최상위에 주입.
- 기존 JSON에는 **소급 적용 금지**. 본 PR 이후 생성분부터 표준 적용.

### 2-4. `module_generation.py` 등 하드코딩 제거

- L365, L373의 `min_onset_gap=3` → config에서 읽도록 수정.
- `run_temporal_reorder_unified.py:309` `min_onset_gap=0` 하드코딩도 config 경유로 정리
  (현재 의도된 0인지 확인 후).

## 작업 3 — 회귀 검증

### 3-1. 리팩토링 후 gap3 결과 재현

`run_dft_suite.py --gap-min 3 --n-repeats 20` 실행 → 기존 `step3_results_gap3.json`
등과 mean/std가 소수점 4자리까지 일치하는지 확인 (동일 시드·N 조건). 불일치 시 원인 로그.

### 3-2. `PipelineConfig.min_onset_gap` 기본 0으로 변경 후 회귀

기본값이 바뀐 이후에도 기존 JSON(gap0 기반)이 재현되는지 샘플 검증. 기존 Tonnetz 기반 gap0
JSON (`percycle_tau_n20_results.json`, `soft_activation_all_models.json`) 중 1~2개를
다시 돌려 수치 일치 확인.

## 호환성 제약

- 기존 `*_gap3_*.json` 및 post-bugfix JSON 삭제 금지 (비교·감사용).
- 외부 `run_*.py` 스크립트 시그니처 변경 최소화. 기본값 변경(gap 3→0) 영향 반드시 테스트.
- 논문 `short.md` / `full.md` 수정 금지 — 세션 D 담당.
- 세션 A(Codex)가 돌리고 있는 `run_dft_gap0_suite.py` (복사본)은 건드리지 않는다.

## 산출물

1. 커밋 1 — `fix(pipeline): ow/dw 전파 버그 수정 (Task 23)` — 미커밋이라면 별도 분리.
2. 커밋 2 — `feat(config): min_onset_gap 필드 + 전파 경로 단일화 + 파라미터 감사 로그`.
3. 커밋 3 — `refactor: run_dft_gap3_suite.py → run_dft_suite.py (argparse 파라미터화)`.
4. 커밋 4 — `feat(utils): build_result_header 유틸 + 주요 run 스크립트 적용`.
5. `diagnose_param_propagation.py` (debug 스크립트).
6. `report.md` — 메타데이터 누락 JSON 목록 + 하드코딩된 gap 위치 목록.
7. 회귀 검증 결과 1~2줄 요약 (memory에 반영).

## 우선순위

1-1 (커밋 분리) → 1-2~1-4 (감사, 병렬 가능) → 2-1, 2-3 (config·메타 표준) → 2-2, 2-4
(스크립트 리팩토링) → 3-1, 3-2 (회귀).
