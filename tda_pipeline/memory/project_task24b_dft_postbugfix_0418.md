# Task24b — §6.6.1 DFT major_block32 post-bugfix 재실험 (2026-04-18)

## 목적
- Task24(Tonnetz post-bugfix)로 §6.6 메타 통찰(“Tonnetz ≫ DFT, ref_pJS 약 27배”)의 근거가 흔들렸는지 검증.
- 동일 조건에서 DFT 대응값을 post-bugfix로 재측정.

## 실행
- 스크립트: `run_section661_dft_major_block32_postbugfix.py` (신규)
- 설정:
  - metric=`dft`
  - `ow=0.3`, `dw=1.0` (Task27 최적값)
  - `alpha=0.5`, rate sweep(0~1.5, step 0.05), gap_min=0
  - `scale_major + block_permute(32)`, Transformer epochs=50
  - seed: Task24(Tonnetz)와 동일 (`SEED0=418000`, N=10)
- 결과 JSON: `docs/step3_data/post_bugfix_dft_major_block32_results.json`

## 3열 비교 (핵심 지표)

| 지표 | pre-bugfix Tonnetz | post-bugfix Tonnetz (N=10) | post-bugfix DFT (N=10) |
|---|---:|---:|---:|
| vs orig pJS | 0.096786 | 0.269633 | 0.268937 |
| vs orig DTW | 2.35925 | 3.62013 | 3.10525 |
| vs ref pJS | 0.003446 | 0.007105 | 0.016219 |

## 비율(메타 통찰 검증)
- 요청 비율: `Tonnetz_post / DFT_post = 0.4381`
- 해석용 역비율: `DFT_post / Tonnetz_post = 2.2828x`
- 기존 서술(약 27x) 대비 현재 강도: `2.2828 / 27 ≈ 0.0845` → 과거 대비 약 **8.45% 수준**.

## 판정 (1문장)
- **Tonnetz의 화성적 우위(ref_pJS)는 방향성은 유지되지만 27배급 격차는 재현되지 않아 메타 통찰은 “약화”로 판정.**

