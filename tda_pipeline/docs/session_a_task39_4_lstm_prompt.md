# Codex 세션 A — Task 39-4 집중: §6.4 LSTM 시간 재배치 실측

## 배경

§6.4 short.md/full.md 현재 서술에 다음 한 줄이 포함되어 있다:

> LSTM: 순환 구조(recurrence)로 과거 문맥을 누적하지만 positional embedding이 없어,
> 입력 순서가 바뀌어도 **DTW 변화가 매우 작다 (모든 전략에서 ≤ 0.5%)**.

**문제**: 이 "≤ 0.5%" 수치의 **실측 근거 JSON이 부재**. 기존 실험
(`temporal_reorder_dl_v2_results.json`)에는 Transformer 결과만 있고 LSTM 데이터 없음.
Codex 세션 D가 이론 예측으로 수치를 추정해 서술한 것으로 보이며, 논문 신뢰성 측면에서
**실측 검증 필요**.

본 Task는 LSTM의 시간 재배치 반응을 실제로 측정하여 "≤ 0.5% DTW 변화" 주장이 재현되는지
검증하고, 결과에 따라 §6.4 서술을 확정한다.

## 필수 참조 파일

### 읽을 것

- `tda_pipeline/run_temporal_reorder_unified.py` — §6.4 기존 재배치 전략 구현
- `tda_pipeline/docs/step3_data/temporal_reorder_dl_v2_results.json` — Transformer 결과
  형식 참고 (평가 지표 구조)
- `memory/project_phase2_gap0_findings_0417.md` — 파라미터 확정값 (α=0.25, w_o=0.3,
  w_d=1.0, gap_min=0)
- `memory/project_wave2_additions_0417.md` — §6.4 서술 보강 맥락

### 수정할 것 (허용)

- 신규 스크립트 `tda_pipeline/run_temporal_reorder_lstm_dft.py` (또는 유사 이름)

### 금지

- `tda_pipeline/docs/academic_paper_*.md` 수정 (세션 D 영역)
- `CLAUDE.md` 수정
- 기존 JSON 덮어쓰기

## 실험 설계

### 공통 설정

```python
distance_metric = 'dft'
alpha = 0.25
octave_weight = 0.3
duration_weight = 1.0
min_onset_gap = 0
post_bugfix = True
```

### LSTM 실험 (메인)

- **모델**: LSTM 2-layer, hidden=128 (§4.3의 §6.7.2 조건과 동일)
- **입력 OM**: DFT continuous activation (§6.7.2 최적 입력)
- **조건 5종** (기존 Transformer 실험과 동일 조건 맞춤):
  1. `baseline` (재배치 없음)
  2. `segment_shuffle` (retrain X)
  3. `block_permute(32)` (retrain X)
  4. `markov(τ=1.0)` (retrain X)
  5. `segment_shuffle + retrain` (retrain O)
- **반복**: N=5 (기존 `temporal_reorder_dl_v2`와 일치)
- **평가 지표**: 각 조건마다 `pitch_js`, `transition_js`, `dtw`, `val_loss` (mean ± std)
- **DTW 변화 계산**: 각 조건의 `dtw` vs `baseline`의 `dtw`를 백분율 변화로 산출.

### FC 실증 (보조, 선택적)

- FC는 시점 독립 모델이므로 수학적으로 재배치 무관성이 자명하지만, 서술 보강을 위해
  1회 N=5 실측 권장 (10분 내외).
- 같은 5종 조건 × FC, 가설: 4개 재배치 조건 모두 baseline과 pitch JS·DTW 사실상 동일.
- **출력 선택**: 시간 여유 있으면 수행. 본 Task 핵심은 LSTM.

## 판정 기준 (보고 필수)

### (1) "≤ 0.5% DTW 변화" 재현 여부

- 각 재배치 조건의 DTW 변화율(`|dtw_new - dtw_baseline| / dtw_baseline × 100%`)을
  표로 제시.
- **재현**: 세 전략 모두 ≤ 0.5% → 현재 §6.4 서술 유지 가능.
- **부분 재현**: 일부만 ≤ 0.5% → 서술 수정 필요 (실측값 범위로 교체).
- **미재현**: DTW 변화가 유의미 (>1%) → 서술 전면 재작성 필요.

### (2) pitch JS 변화

- "LSTM의 재배치 반응이 작다" 주장은 DTW 뿐 아니라 pitch JS·transition JS에서도 일관
  되어야 함. 세 지표 모두 보고.

### (3) retrain 효과

- `segment_shuffle + retrain` 조건에서 baseline 대비 변화가 어떻게 나타나는지.
- Transformer의 `noPE + retrain` 경우 DTW +21.7% / pitch JS 붕괴였음. LSTM은?
- LSTM도 pitch 붕괴 나타나는지, 혹은 학습 실패로 무변화인지 관찰.

## 출력

### 메인

`docs/step3_data/temporal_reorder_lstm_dft_gap0.json`

구조 (`temporal_reorder_dl_v2_results.json` 형식 준수):

```json
{
  "metric": "dft",
  "alpha": 0.25,
  "min_onset_gap": 0,
  "octave_weight": 0.3,
  "duration_weight": 1.0,
  "model": "lstm",
  "n_repeats": 5,
  "date": "...",
  "script": "run_temporal_reorder_lstm_dft.py",
  "post_bugfix": true,
  "conditions": {
    "baseline":                          { "pitch_js": ..., "transition_js": ..., "dtw": ..., "val_loss": ... },
    "segment_shuffle_retrain_x":         { ... },
    "block_permute32_retrain_x":         { ... },
    "markov_tau1_retrain_x":             { ... },
    "segment_shuffle_retrain_o":         { ... }
  },
  "dtw_change_pct": {
    "segment_shuffle_retrain_x":   ...,
    "block_permute32_retrain_x":   ...,
    "markov_tau1_retrain_x":       ...,
    "segment_shuffle_retrain_o":   ...
  },
  "verdict": {
    "threshold_0_5_pct_reproduced": true | false,
    "max_dtw_change_pct": ...,
    "recommendation": "서술 유지 | 수치 교체 | 전면 재작성"
  }
}
```

### 보조 (선택적, FC 수행 시)

`docs/step3_data/temporal_reorder_fc_dft_gap0.json` — 같은 구조, `model="fc"`.

## 실행 방식

- 기존 `run_temporal_reorder_unified.py`를 복사해 LSTM 전용으로 수정 권장.
- 또는 `session_a_task39_prompt.md`의 T39-4 섹션을 참고하여 독립 스크립트 작성.
- `utils/result_meta.build_result_header` 활용으로 메타 자동 주입.

## 주의사항

1. **min_onset_gap=0 명시 필수**
2. **metric='dft', alpha=0.25 명시**
3. **Python 세션**: 단독 Task이므로 새 세션 OK. 완료 후
   `phase3_task39_4_lstm_summary.json` (선택) 저장.
4. **기존 Transformer JSON 보존**: `temporal_reorder_dl_v2_results.json` 덮어쓰지 않음.
5. **논문 수정 금지**: §6.4 서술은 세션 D가 실측 결과 받은 뒤 판단·반영.
6. **N=5 충분 여부**: 기존 `temporal_reorder_dl_v2`가 N=5였으므로 일관. 결과가 경계
   근처(예: 평균 0.4% 근처 std 0.3%)면 N=10 재실험 제안 보고.

## 세션 D 연동

Task 39-4 완료 보고 시 다음 3가지 경로로 세션 D가 §6.4 서술 확정:

1. **재현 (all ≤ 0.5%)**: 현재 서술 유지. 각주로 "실측 검증 `temporal_reorder_lstm_dft_gap0.json`
   참조" 추가 권장.
2. **부분 재현**: "≤ 0.5%" 표현을 실측 범위로 수정 (예: "≤ X%"). 각주로 JSON 경로
   표시.
3. **미재현**: §6.4 LSTM 서술 전면 재작성. "LSTM도 재배치에 미세하게 반응" 혹은 "LSTM의
   시간 재배치 반응은 DTW X% 수준" 같이 실측 기반 서술.

본 Task 완료 보고 받으면 세션 E가 커밋 + 세션 D 서술 수정 프롬프트 작성.

## 완료 보고 형식

Phase 1·2 스타일로:
- 5개 조건의 DTW 변화율 표
- pitch JS / transition JS 변화 요약
- retrain 효과 분석
- 판정: "≤ 0.5% 재현" 여부 + §6.4 서술 추천 조치

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음**.
