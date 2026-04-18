# Task 30 — §7.2 34×32 블록 Prototype 재실험 (2026-04-18)

## 목적
- 기존 reshape `33×32=1056`(앞 1056행 사용) 대신,
- **전체 OM 1088행**을 `34×32` 블록으로 reshape하여 prototype(P0/P1/P2/P3_local) 재비교.
- 용어는 "마디" 대신 **32시점 블록(block)** 사용.

## 실행 조건
- 스크립트: `run_section72_34blocks_prototype.py` (신규)
- metric: DFT
- alpha: 0.25
- octave_weight: 0.3
- duration_weight: 1.0
- min_onset_gap: 0
- global cycle count: K=14
- 반복: 각 prototype N=10
- full-song 재구성: 생성 블록 1개를 **34회 복제**
- 출력: `docs/step3_data/section72_34blocks_prototype_results.json`

## reshape 및 prototype 정의
- `O_full ∈ {0,1}^{1088×14}`
- `O_tilde ∈ {0,1}^{34×32×14}`
- P0: `O_tilde[0]` (첫 블록)
- P1: 34개 블록 시점별 OR
- P2: 34개 블록 시점별 majority vote (strict majority)
- P3_local: 블록 구간(두 악기) local PH 재실행 후 새 cycle set 사용

## 34×32 결과 (N=10)

| Prototype | JS mean ± std | Best JS (seed) | Coverage mean |
|---|---:|---:|---:|
| P0_first_block | 0.0957 ± 0.0136 | 0.0678 (8202) | 0.817 |
| P1_or_over_34blocks | 0.0586 ± 0.0187 | 0.0367 (8309) | 0.822 |
| P2_majority_vote_over_34blocks | 0.0692 ± 0.0112 | 0.0543 (8400) | 0.796 |
| P3_local_recomputed_ph | **0.0575 ± 0.0141** | **0.0360 (8506)** | **0.839** |

요약:
- mean JS 기준 최고: **P3_local (0.0575)**
- best trial JS 기준 최고: **P3_local (0.0360)**
- coverage 기준도 P3_local이 가장 높음(0.839)

## 기존 33×32 결과와 비교

비교 기준 파일:
- `docs/step3_data/step71_prototype_comparison_dft_gap0.json` (33×32, N=10)

| Prototype | 34×32 JS mean | 33×32 JS mean | Δ% (34 vs 33) | 메모 |
|---|---:|---:|---:|---|
| P0_first_block | 0.0957 | 0.1040 | -8.0% | 정의 직접 비교 가능 |
| P1_or_over_34blocks | 0.0586 | 0.0621 | -5.6% | 정의 직접 비교 가능 |
| P2_majority_vote_over_34blocks | 0.0692 | 0.0900 | -23.0% | 정의 변경(구 P2는 exclusive/sparse) |
| P3_local_recomputed_ph | 0.0575 | 0.0474 | +21.4% | 정의 변경(구 P3는 module-specific pick) |

## 기록 유지 (pre-수정 비교용)
- 사용자 지정 기록값 유지: **P0 (N=20) = 0.1082**
- JSON 원본 확인: `step71_module_results_dft_gap0.json`
  - mean JS = 0.108162...
  - best JS = 0.070083...

## 산출물
- `docs/step3_data/section72_34blocks_prototype_results.json`
- `memory/project_task30_section72_34blocks_0418.md` (본 문서)
- `memory/MEMORY.md` 인덱스 업데이트
