# Codex 세션 A — Phase 2 진입 (Task A8~A10, DFT-hybrid 재탐색)

## Phase 1 결과 요약 (2026-04-17 완료, 커밋 bb4ab4d)

- Task A1 ★ DFT JS=0.0213±0.0021 (N=20), frequency 대비 −38.2%, Tonnetz 대비 −56.8%
- Task A2: **w_d = 1.0** 최적 (gap3와 동일)
- Task A3: **w_o = 0.3** 최적 (gap3와 동일)
- Task A4: 기존 `decayed_lag_dft_results.json` 재사용 (DFT+decayed −7.1% ★ 유지)
- Task A5: Binary OM 최적 JS=0.0157±0.0018 (N=20)
- **Task A6 중요 발견 — 이전 가설 부분 기각**:
  - gap0+DFT에서 FC 0.0021 ≈ Transformer 0.0024 (FC 근소 우위, N=5)
  - gap3에서는 Transformer 0.00276 우위였음. gap_min이 최적 모델 선택에 영향
- **Task A7 중요 발견**: FC_cont 0.00032 vs FC_bin 0.00378 → FC_cont 압도적 우위.
  연구 전체 잠정 최저 (Tonnetz+FC_cont 0.0004, complex B 0.0003과 동등~갱신)

## Phase 2 진입 지시

`codex_prompt_dft_gap0_rerun.md`의 Phase 2 섹션을 기준으로 하되, 아래 사항을 반영해
수정·진행한다.

### 공통 설정 (Phase 1 확정값 고정)

```python
min_onset_gap = 0
distance_metric = 'dft'
octave_weight = 0.3       # Task A3 확정
duration_weight = 1.0     # Task A2 확정
post_bugfix = True
```

### Task A8 — Per-cycle τ × DFT continuous OM (N=20)

원 프롬프트대로 진행. 추가 참고:

- Phase 1 Task A5에서 **DFT Binary가 Continuous direct를 이긴 것**을 주목
  (gap3와 동일 방향: §4.2 binary 우위).
- 그럼에도 per-cycle τ는 continuous activation을 기반으로 하는 방법이므로 유효
  (§6.7.1과 동일 로직). Binary·Continuous 양쪽 baseline을 모두 보고.
- **출력**: `docs/step3_data/percycle_tau_dft_gap0_results.json`

### Task A9 — Soft activation × DL 아키텍처 **(N=10으로 증가 + 통계 검증)**

원 프롬프트(N=5)에서 **N=10으로 증가**. 이유: Phase 1 Task A6에서 FC/Transformer 차이
(0.0021 vs 0.0024)가 표준편차 내에 있어 통계적 확정이 어려움.

- FC / LSTM / Transformer × binary / continuous, **N=10**
- **Welch t-test** 수행: FC-cont vs Transformer-cont, FC-cont vs FC-bin, Transformer-cont
  vs Transformer-bin 세 쌍 최소.
- **출력**: `docs/step3_data/soft_activation_dft_gap0_results.json`
- **보고**: DFT+gap0 조건에서
  1. continuous 입력이 binary를 이기는지 (각 아키텍처별)
  2. FC-cont와 Transformer-cont의 우열 (p-value 포함)
  3. A7의 FC_cont 0.00032가 N=10에서 재현되는지

### Task A10 — DFT α-hybrid grid + Complex 통합 (A10-a, A10-b)

**(A10-a) DFT α-hybrid grid (N=20)**: 원 프롬프트대로. 출력은
`alpha_grid_dft_gap0_results.json`.

**(A10-b) Complex × DFT-hybrid × per-cycle τ (N=20)**:

- A10-a 최적 α 중심 grid + r_c ∈ {0.1, 0.3}.
- **Algo2 모델은 Task A9 결과에 따라 결정**:
  - Task A9에서 FC-cont가 Transformer-cont보다 유의하게 우위면 → FC만 돌려도 됨
  - 유의차 없으면 → FC와 Transformer 둘 다 보고
  - Transformer 우위면 → Transformer 기본 + FC 병기
- **출력**: `docs/step3_data/complex_percycle_dft_gap0_results.json`
- **보고**: DFT-complex 최저 JS와 Tonnetz-complex 기존 최저 (Algo1 0.0183, Algo2
  FC 0.0003) 비교. "절대 최저" 전환 여부 확정.

## 인프라

세션 B가 `run_dft_suite.py`로 파라미터화 완료. Phase 2 신규 스크립트도 가능하면
`utils/result_meta.py::build_result_header`를 사용해 JSON 메타 표준 준수.

## 주의

1. **Python 세션 정책**: A8~A10도 **같은 Python 세션에서 직렬 실행** 권장 (Phase 1과 동일).
   완료 후 `phase2_a8_a10_gap0_serial_summary.json` 저장.
2. **메타 표준 필수**: `metric`, `min_onset_gap`, `alpha`, `octave_weight`,
   `duration_weight`, `n_repeats`, `date`, `script`, `post_bugfix` 전부 포함.
3. **기존 JSON 보존**: gap3 / Tonnetz 기반 JSON 삭제 금지. 신규는 `*_dft_gap0_*`로.
4. **논문 수정 금지**: 세션 D 영역.
5. **완료 보고 형식**: Phase 1과 동일 스타일로 Task별 핵심 수치 + 통계 유의성 + 다음
   단계 제언.
