# Codex 세션 A — Task 42: T39-4/T39-5 N=5 반복 통계 재검증

## 배경

Task 39 Wave 2 실행 보고에서 사용자가 "T39-4/5를 요청 스펙대로 N=5 반복 통계 버전으로
재실행" 옵션을 제시했으며, 세션 E가 **"반복 수가 불충분할 수 있음"**을 확인 대기로
플래그함 (`memory/project_task39_wave2_findings_0417.md`).

본 Task 42는 T39-4(§6.4) / T39-5(§6.5)의 FC/LSTM JSON에 **통계적 반복 (N=5) + std 존재**
여부를 확인하고, 부족한 항목은 N=5로 재실행해 std까지 확정한다.

결론 방향은 이미 명확:
- FC 시점 독립성 (§6.4): 수학적 자명 + baseline pitch_js=0.000917 확인
- LSTM 재배치 반응 (§6.4): Task 39-4 집중(커밋 b3903ab)에서 이미 N=5 실측 확정
- FC/LSTM 화성 제약 (§6.5): Task 39 Wave 2 수행, 반복 수 미확인

따라서 **본 Task는 std 수치 확정이 목적**이며 결론 방향 변경은 예상되지 않음.

## 필수 참조 파일

### 읽을 것

- `memory/project_task39_wave2_findings_0417.md` — Wave 2 경과
- `memory/project_task39_4_lstm_findings_0417.md` — 집중 실험 (N=5 이미 확정)
- 기존 JSON 4종 (N 확인 후 부족하면 재실행):
  - `docs/step3_data/temporal_reorder_fc_dft_gap0.json`
  - `docs/step3_data/temporal_reorder_lstm_dft_gap0.json` (⚠ 두 번 덮어쓰기 이력 —
    Task 39-4 집중 vs Task 39 wave2)
  - `docs/step3_data/harmony_fc_dft_gap0.json`
  - `docs/step3_data/harmony_lstm_dft_gap0.json`

### 금지

- 논문 `academic_paper_*.md` 수정 (세션 D 영역)
- `CLAUDE.md` 수정
- 기존 신뢰 JSON 덮어쓰기 (temporal_reorder_lstm은 신규 파일명 권장)

## 사전 검사

각 JSON의 다음 구조 확인:

1. `n_repeats` 필드 존재 여부
2. 각 조건마다 `{mean, std}` 또는 `{mean, values_array}` 존재 여부
3. std가 0 또는 부재 → N=1 의심

### 결과별 분기

| JSON | N=5 + std 존재 | N<5 or std 부재 |
|---|---|---|
| `temporal_reorder_fc_dft_gap0.json` | 스킵 | 재실행 (T42-1) |
| `temporal_reorder_lstm_dft_gap0.json` | Task 39-4 집중 N=5 확인됨 → 현재 파일이 Wave 2로 덮어쓴 상태면 집중 결과 복원 or 별도 파일 | — |
| `harmony_fc_dft_gap0.json` | 스킵 | 재실행 (T42-2) |
| `harmony_lstm_dft_gap0.json` | 스킵 | 재실행 (T42-3) |

## 공통 설정

```python
distance_metric = 'dft'
alpha = 0.25
octave_weight = 0.3
duration_weight = 1.0
min_onset_gap = 0
post_bugfix = True
n_repeats = 5
```

입력 OM: DFT continuous (§6.7.2 최적).

## 실행 Task

### T42-1: §6.4 FC N=5 재실행 (필요 시)

- 조건: baseline + 3 재배치 (segment_shuffle, block_permute32, markov τ=1.0) × FC
- N=5, 각 조건 pitch_js / transition_js / DTW mean±std
- **가설**: FC 시점 독립성으로 4조건 사실상 동일 (std 작음, pitch_js 거의 불변)
- 출력: `docs/step3_data/temporal_reorder_fc_dft_gap0_n5.json`

### T42-2: §6.5 FC N=5 재실행 (필요 시)

- 조건: original / baseline / scale_major / scale_penta × FC
- N=5, 각 조건 4지표 (vs_orig pJS / vs_orig DTW / vs_ref pJS / val_loss) mean±std
- 출력: `docs/step3_data/harmony_fc_dft_gap0_n5.json`

### T42-3: §6.5 LSTM N=5 재실행 (필요 시)

- 같은 구성, LSTM
- 출력: `docs/step3_data/harmony_lstm_dft_gap0_n5.json`

### T42-4: `temporal_reorder_lstm_dft_gap0.json` 덮어쓰기 이슈 해결

- Task 39-4 집중 (b3903ab)의 LSTM 결과는 DTW ≤0.5% 검증 목적
- Task 39 Wave 2가 같은 파일에 다른 용도로 덮어썼을 가능성
- 조치:
  - 현재 파일 내용 확인
  - 필요 시 `temporal_reorder_lstm_dft_gap0_dtwverify.json` (Task 39-4 집중 복원) 과
    `temporal_reorder_lstm_dft_gap0_wave2.json` (Wave 2) 으로 분리
  - 또는 현재 파일이 Task 39-4 집중 결과이면 유지 + Wave 2 결과는 본 Task T42-5로
    별도 생성

### T42-5 (선택): §6.4 LSTM Wave 2 용 별도 재실행

- T42-4에서 분리 필요 결정 시
- 조건: baseline + 3 재배치 × LSTM × retrain X / retrain O, N=5
- 출력: `docs/step3_data/temporal_reorder_lstm_dft_gap0_wave2.json`

## 출력 메타데이터

각 JSON 최상위:

```json
{
  "metric": "dft",
  "alpha": 0.25,
  "min_onset_gap": 0,
  "octave_weight": 0.3,
  "duration_weight": 1.0,
  "n_repeats": 5,
  "date": "...",
  "script": "...",
  "post_bugfix": true,
  "purpose": "n_repeat_verification_task42"
}
```

## 실행 순서

```
사전 검사 (4 JSON의 n_repeats + std 확인)
    ↓
T42-4 LSTM 파일 덮어쓰기 이슈 해결
    ↓
T42-1 / T42-2 / T42-3 중 재실행 필요한 것만 (같은 Python 세션 직렬)
    ↓
phase3_task42_nrepeat_verify_summary.json 저장
```

Python 세션 정책: 같은 Python 세션 직렬 (Phase 1·2·3 동일).

## 예상 소요

- FC 학습 × 조건 × N=5: 약 5~10분/실험 × 2실험 ≈ 15분
- LSTM 학습 × 조건 × N=5: 약 10~20분/실험 × 1~2실험 ≈ 15~30분
- **총 30~60분** (재실행 필요 개수에 따라)

## 판정 및 보고

각 실험별로:

1. 기존 JSON의 N과 std 요약
2. 재실행 여부 판단 근거
3. 재실행 시 새 std 수치 보고
4. **결론 방향 변경 여부** — 예상: 불변 ("§6.4 FC 시점 독립, LSTM ≤0.5% 재배치 무반응,
   §6.5 scale_major 최적" 유지)

## 주의사항

1. **metric='dft', alpha=0.25, gap_min=0 명시 필수**
2. **기존 JSON 보존**: 신규 파일은 `*_n5.json` 접미사. 기존 덮어쓰기 금지.
3. **Python 세션 직렬**: `phase3_task42_summary.json`에 `same_python_session=true`,
   `status=completed` 기록.
4. **논문 수정 금지**: 세션 D가 std 수치를 최종 반영. 본 Task는 JSON 생성까지.
5. **완료 보고 형식**: Phase 1·2·3 스타일 (Task별 핵심 수치 + 결론 방향 판정).

## 세션 D 연동

Task 42 결과 수령 시 세션 D가 간단히 반영:

- §6.4 / §6.5 표의 수치 뒤에 ±std 추가 또는 확인
- std가 기존 서술 수치와 크게 다르면 재확인
- 결론 방향 불변이면 단순 수치 업데이트만

모델 권장: **GPT-5.3-Codex + reasoning 높음** (복잡도 낮음).
