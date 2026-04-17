# Codex 세션 A — Task 38a: §7 DFT 전면 재수행 (Phase 3)

## 배경

1. 논문 §7 (모듈 단위 생성) 관련 JSON 전부 **pre-bugfix** 상태 확인됨 (2026-04-10 ~
   2026-04-14):
   - `step71_startmodule_study.json` (4/10)
   - `step71_improvements.json` (4/11)
   - `step_barcode_results.json` (4/13, alpha=0.5)
   - `section77_experiments.json` (4/13)
   - `step71_module_results.json` (4/14)
   - `step71_prototype_comparison.json` (4/14)

   이들 전부 refine_connectedness + pipeline.py ow/dw 버그픽스 이전이며, 거리 함수도
   **Tonnetz α=0.5** 기반 (K=42).

2. 현재 논문 상태:
   - §4, §6: Phase 1+2+2b로 **DFT** 전면 반영 완료 (Task 32~37).
   - §7: 여전히 **Tonnetz α=0.5 cycle (K=42)** 기반. §7.1 수식이 `O_proto ∈ {0,1}^{32 × 42}`.
   - Task 37에서 §7 baseline만 "Tonnetz 0.0488 → DFT 0.0213"으로 교체했으나, 모듈 생성
     실험 자체는 미변경 → **baseline 거리와 모듈 생성 거리가 분기**.

3. 본 Task 38a는 §7.1~§7.8 전체를 **DFT α=0.25 조건**으로 전면 재수행한다. Phase 2
   A10-a에서 DFT α-hybrid 최적이 α=0.25로 확인되었으므로 이 값을 채택.

## 필수 참조 파일

### 읽을 것

- `memory/project_phase1_gap0_findings_0417.md` — Phase 1 파라미터 최적값
- `memory/project_phase2_gap0_findings_0417.md` — Phase 2 α 최적, per-cycle τ
- `memory/project_phase2b_alpha25_findings_0417.md` — complex Tonnetz 한정 확정
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 규칙
- 기존 §7 실행 스크립트 (참고용):
  - `tda_pipeline/run_module_generation.py` (§7.1 P1)
  - `tda_pipeline/run_module_generation_v3.py` (§7.1 P0/P1/P2/P3, 개선 C/D)
  - `tda_pipeline/run_module_generation_v4.py` (§7.7 startmodule study — 또는
    unified.py `--mode startmodule_study`)
  - 기타: `run_any_track.py` 패턴 참고
- 기존 §7 JSON (수치 대조·비교용, 덮어쓰기 금지):
  - `docs/step3_data/step71_module_results.json`
  - `docs/step3_data/step71_improvements.json`
  - `docs/step3_data/step71_prototype_comparison.json`
  - `docs/step3_data/step71_startmodule_study.json`
  - `docs/step3_data/step_barcode_results.json`
  - `docs/step3_data/section77_experiments.json`

### 금지

- 논문 `academic_paper_*.md` 수정 (세션 D Task 38b 영역)
- `CLAUDE.md` 수정 (세션 D Task 38b 완료 후 세션 E 갱신)
- 기존 pre-bugfix JSON 삭제·덮어쓰기

## 공통 설정 (Task 38a 전 실행)

```python
distance_metric = 'dft'
alpha = 0.25              # ★ Phase 2 A10-a 최적
octave_weight = 0.3       # Phase 1 A3 확정
duration_weight = 1.0     # Phase 1 A2 확정
min_onset_gap = 0
post_bugfix = True
```

캐시: `cache/metric_dft.pkl` 있는지 확인. α=0.25 조건은 §6.8 실험에서 빌드된
`alpha_grid_dft_gap0_results.json` 맥락과 일치. 캐시 재사용 가능하면 활용.

## 실행 방식

`run_dft_suite.py` (세션 B 파라미터화 결과) 또는 신규 `run_module_generation_dft.py`를
작성. 기존 `run_module_generation_v3.py`를 복사 후 DFT α=0.25로 설정 상수를 바꾸는 방식
추천.

**Python 세션 정책**: T38a-1 ~ T38a-6 **같은 Python 세션에서 직렬 실행** (Phase 1·2
동일). 완료 후 `phase3_task38a_dft_gap0_summary.json` 저장.

## 사전 체크

1. DFT α=0.25 조건 PH 캐시 존재 확인. 없으면 ~15분 PH 재계산 예고 후 진행.
2. T38a-1에서 **K 값을 최우선 확인**하여 보고 (Tonnetz α=0.5의 K=42 vs 신규 K).

---

## Phase 3 — §7 DFT α=0.25 재실험

### T38a-1: §7.1 prototype OM 재생성

- DFT α=0.25 cycle_labeled 기반 prototype overlap 생성.
- K (cycle 수) 확정.
- 검증: 기존 Tonnetz K=42 대비 신규 K는 17 (§4.1 DFT baseline) 또는 14 (§6.8 α=0.25) 근처
  예상. 실제 값 JSON 메타에 기록.
- **출력 메타데이터에 `K`, `cycle_count` 필수 포함**.
- 후속 T38a-2~T38a-6 모두 이 K 기반 prototype OM을 사용.

### T38a-2: §7.2 Prototype 전략 비교 (N=10)

- 전략: **P0** (첫 모듈 복제) / **P1** (union-of-active) / **P2** (exclusive-to-module) /
  **P3** (module-specific)
- 기존 `run_module_generation_v3.py` 방식 준수.
- N=10 trials, 각 전략의 mean JS ± std 산출.
- **출력**: `docs/step3_data/step71_prototype_comparison_dft_gap0.json`
- **보고**: 각 전략 JS, full-song DFT baseline 0.0213 대비 비율, 기존 Tonnetz
  대비 비교.

### T38a-3: §7.3 본 실험 (N=20)

- §7.3은 현재 논문상 "P0 전략 채택" 기록 (full.md 확인). `run_module_generation.py`
  또는 unified.py 사용.
- N=20, best/worst trial 포함.
- **출력**: `docs/step3_data/step71_module_results_dft_gap0.json`
- **보고**: mean/std JS, best trial 정보, baseline 대비 배수.

### T38a-4: §7.5 개선 C/D/P3/P3+C (N=10)

- 개선 C, D, P3, P3+C 4종 조합. `run_module_generation_v3.py` 패턴.
- N=10, best trial (seed, JS, coverage, 사용 note 수) 기록.
- **출력**: `docs/step3_data/step71_improvements_dft_gap0.json`
- **보고**: 각 조합 mean JS, P3+C best 재확인.

### T38a-5: §7.7 시작 모듈 선택 정당성 재검증

- hibari 시작 모듈 후보 전부 스위프 (inst 1 + inst 2 합쳐 총 65개 modules 기준, 또는
  기존 33 기준 — 사용자 피드백 22번 반영 필요한지 확인 후 일관 선택).
- 각 시작 모듈 위치에서 N=? (기존 방식) 생성 후 JS 분포.
- 첫 모듈 advantage 재현 여부 판정.
- **출력**: `docs/step3_data/section77_experiments_dft_gap0.json`
- **보고**: best_temperature 포함, first-module 우위 유지 여부, best global trial
  (seed, JS, coverage, module 수, 사용 note 수).

### T38a-6: §7.8 Barcode Wasserstein 재계산

- DFT α=0.25 barcode × generated module JS 간 Pearson 상관.
- 기존: W_mean=0.812, JS_mean=0.056, Pearson(W, JS)=0.503 (Tonnetz).
- 재계산 후 신규 W·JS·Pearson 제시.
- **출력**: `docs/step3_data/step_barcode_dft_gap0.json`
- **보고**: 새 Pearson 값, §7.1.9 "주의사항 4개" 변화 여부.

---

## 출력 파일 표준 메타데이터

모든 JSON 최상위에 다음 필드 필수 (세션 B Task 33 `utils/result_meta.build_result_header`
활용):

```json
{
  "metric": "dft",
  "min_onset_gap": 0,
  "alpha": 0.25,
  "octave_weight": 0.3,
  "duration_weight": 1.0,
  "n_repeats": ...,
  "K": ...,
  "date": "...",
  "script": "...",
  "post_bugfix": true,
  ...
}
```

## 전체 실행 순서

```
사전 체크 (DFT α=0.25 PH 캐시)
    ↓
T38a-1 (prototype OM, K 확정)
    ↓
T38a-2 (prototype 전략 비교 N=10)
    ↓
T38a-3 (본 실험 N=20)
    ↓
T38a-4 + T38a-5 + T38a-6 (독립 병렬 가능)
    ↓
phase3_task38a_dft_gap0_summary.json 저장
```

## 주의사항

1. **metric='dft' + alpha=0.25 명시 필수**: 모든 호출부에 명시.
2. **min_onset_gap=0**: 기본값이지만 명시.
3. **기존 JSON 보존**: Tonnetz 기반 `step71_*.json`, `section77_*.json`,
   `step_barcode_*.json` 삭제·덮어쓰기 금지. 신규는 `*_dft_gap0_*` 접미사.
4. **K 값 보고 최우선**: T38a-1에서 확정 후 이후 Task에 일관 적용.
5. **same_python_session 기록**: `phase3_task38a_dft_gap0_summary.json`에 Phase 1·2
   서밋과 동일 구조.
6. **논문 수정 금지**: academic_paper_*.md / CLAUDE.md 손대지 않는다.
7. **완료 보고 형식**: Phase 1·2 스타일로 Task별 핵심 수치 + 기존(Tonnetz) 대비 변화
   방향 + 다음 단계 제언.

## 세션 D 연동

본 Task 완료 후 세션 D가 Task 38b (§7 전면 재서술) 착수:

- §7.1 수식 `32 × 42` → `32 × K_new` 교체
- §7.2~§7.8 표·해석 전면 갱신
- short.md는 최종 수치만, full.md는 Tonnetz 기존 각주 가능
- §8 결론의 §7 인용 부분 수치 동기화

Task 38b 프롬프트는 Task 38a 결과 수령 직후 세션 E가 작성.
