# Codex 세션 A — Phase 2 후속: A10-b α=0.25 재실험

## 배경

Phase 2 완료 (커밋 `459eb24`) 후속 과제. Task A10-b pilot에서 α=0.5를 사용했으나,
A10-a grid에서 **최적 α=0.25**로 확인됨 (JS=0.01593±0.00181). pilot 선택과 grid 최적
사이의 불일치를 해소하고, α=0.25 조건에서 complex 모드가 timeflow(A8) 대비 개선을 주는지
최종 확인한다.

현재 잠정 최저:
- Algo1: **A8 DFT + per-cycle τ (timeflow) = 0.0149±0.0014 ★**
- Algo2: **A9 DFT + FC-cont = 0.00035 (N=10, p=1.66e-4)**

A10-b pilot α=0.5 결과:
- Algo1: 0.03365 (A8 대비 +126% 악화)
- Algo2 FC: 0.000554 (A9 대비 +58% 악화)

## 실행

### Task A10-b′ — DFT Complex × per-cycle τ, α=0.25 고정 (N=20)

**설정**:

```python
distance_metric = 'dft'
min_onset_gap = 0
alpha = 0.25              # ★ A10-a 최적값으로 고정
octave_weight = 0.3       # Phase 1 A3 확정
duration_weight = 1.0     # Phase 1 A2 확정
r_c_grid = [0.1, 0.3]     # A10-b와 동일 선택지
mode = 'complex'
post_bugfix = True
n_repeats_main = 20
```

**수행**:

- r_c ∈ {0.1, 0.3} 각각 per-cycle τ_c greedy coordinate descent 수행 후 N=20 재검증.
- Algo1 + Algo2 (FC-cont만 — A9 결과로 `fc_only` 결정 유지) 둘 다 보고.

### 출력

`docs/step3_data/complex_percycle_dft_gap0_alpha25_results.json`

**필수 메타데이터**: `metric`, `min_onset_gap`, `alpha=0.25`, `octave_weight=0.3`,
`duration_weight=1.0`, `r_c`, `n_repeats`, `date`, `script`, `post_bugfix=true`.

### 보고

1. α=0.25 기준 complex의 Algo1 JS + Algo2 FC JS (r_c별)
2. **A8 (0.0149)와의 Welch t-test p-value** — 유의 개선인지, 유의 악화인지, 비유의인지
3. **결론 판정**:
   - A8보다 유의 개선 → DFT에서도 complex 유효, §6.9 결론을 complex 최적 α=0.25로
   - A8보다 유의 악화 or 비유의 → "complex는 Tonnetz 한정 유효" 확정, §6.9는 Tonnetz
     기반 서술 유지 + DFT에서는 timeflow 선호

## 주의

- **Python 세션**: 단독 Task이므로 새 Python 세션 실행 OK. 완료 후
  `phase2b_alpha25_summary.json` 저장 (same_python_session 필드 OK).
- **기존 JSON 보존**: `complex_percycle_dft_gap0_results.json` (α=0.5 pilot) 유지. 신규는
  별도 파일명.
- **논문 수정 금지**: 세션 D 영역.
- **완료 보고 형식**: Phase 1·2와 동일 스타일 (Task별 수치 + 통계 + 결론 판정).

## 세션 D 연동

본 Task 결과에 따라 세션 D Task 36 (§6.9 재서술)의 결론 방향이 결정됨. 재실험 결과 나오기
전까지 세션 D Task 36은 대기. Task 35 (§4 재서술)는 선행 가능.
