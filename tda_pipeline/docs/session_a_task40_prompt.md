# Codex 세션 A — Task 40: §6.3~§6.6 DFT 전환 전면 재실험

## 배경

§6.6 결합 실험(`combined_AB_results.json`, 2026-04-11)이 pre-bugfix 상태 + Tonnetz
baseline. 사용자 결정으로 **옵션 (B) DFT 전환 재실험**을 진행한다.

관련 bugfix:
- `refine_connectedness` 대칭화 (2026-04-17 확정)
- `pipeline.py` ow/dw 전파 (커밋 `080b9fe`, 2026-04-15)

영향 범위가 §6.4·§6.5·§6.6 전체에 걸치므로 Transformer를 써야 하는 §6 섹션을 일괄
DFT α=0.25 조건으로 재실험한다. FC/LSTM 부분은 Task 39 / Task 39-4 집중에서 처리되므로
본 Task 40은 **Transformer 전용**.

**충돌 안전**: Task 39 (FC/LSTM), Task 39-4 LSTM, Task 38b (논문 md) 와 파일 영역 분리.
밤새 돌려도 안전. 예상 소요 3~4시간.

## 필수 참조 파일

### 읽을 것

- `tda_pipeline/run_temporal_reorder_unified.py` — §6.4 재배치 구현
- `tda_pipeline/docs/step3_data/temporal_reorder_dl_v2_results.json` — 기존 Tonnetz
  Transformer 결과 (형식 참고)
- `tda_pipeline/docs/step3_data/harmony_continuous_results.json` — 기존 §6.5 Tonnetz
  결과 (형식 참고)
- `tda_pipeline/docs/step3_data/combined_AB_results.json` — 기존 §6.6 Tonnetz 결과
  (구성 조합 확인)
- `memory/project_phase2_gap0_findings_0417.md` — DFT α=0.25 확정
- `memory/project_wave2_d_completed_0417.md` — §6.6 각주·미재실험 경과

### 수정 가능

- 신규 스크립트 `tda_pipeline/run_section66_dft_transformer.py` (또는 분할 3개)

### 금지

- `tda_pipeline/docs/academic_paper_*.md` 수정 (세션 D 영역)
- `CLAUDE.md` 수정
- 기존 Tonnetz JSON 덮어쓰기 (`combined_AB_results.json` 등)

## 공통 설정

```python
distance_metric = 'dft'
alpha = 0.25
octave_weight = 0.3
duration_weight = 1.0
min_onset_gap = 0
post_bugfix = True
```

모델 공통:
- **Transformer 2-layer, 4-head, d_model=128** (§4.3 / §6.7.2 동일 설정)
- lr=0.001, dropout=0.3, epochs=기존 Transformer 실험과 일치
- 입력: DFT continuous OM (§6.7.2 최적 입력 기준)

---

## T40-1: §6.4 Transformer × 시간 재배치 DFT (N=5)

### 실험 조건

기존 Tonnetz의 `temporal_reorder_dl_v2_results.json` 구조 유지:

1. **noPE_baseline** (PE 제거, 재배치 없음, retrain X) — 기존 noPE_baseline 대응
2. **noPE_segment_shuffle (retrain X)**
3. **noPE_markov (retrain X, τ=1.0)**
4. **noPE+retrain segment_shuffle** — 강한 재배치 1
5. **noPE+retrain markov (τ=1.0)** — 강한 재배치 2
6. **PE 있음 + baseline** (표준, 참고용) — 필요 시 추가

지표: pitch_js, transition_js, dtw, val_loss. 각각 mean ± std.

### 출력

`docs/step3_data/temporal_reorder_transformer_dft_gap0.json`

구조는 `temporal_reorder_dl_v2_results.json` 형식 준수.

### 보고

- 기존 Tonnetz DTW +21.7% (noPE+retrain segment_shuffle) vs DFT 신규 수치
- "딜레마" (강한 재배치 → pitch 붕괴) 재현 여부
- §6.4 서사 유지 여부 판정

### 예상 소요

Transformer 학습 × 5~6 조건 × N=5 = 25~30 학습 × 학습시간 ≈ 40~60분.

---

## T40-2: §6.5 Transformer × 화성 제약 DFT (N=5)

### 실험 조건

기존 `harmony_continuous_results.json` 구조 유지:

1. **original** (원곡 note 사용, 참고 기준)
2. **baseline** (제약 없음, 재분배 note)
3. **scale_major** — 메인 조건 ★
4. **scale_penta**

지표: vs 원곡 pJS, vs 원곡 DTW, vs ref pJS, val_loss.

### 출력

`docs/step3_data/harmony_transformer_dft_gap0.json`

### 보고

- scale_major + Transformer 조합의 3축 (위상 보존·정량화 가능 차이·화성 일관성)
  수치 재측정
- 기존 Tonnetz 값 (pJS=0.097, DTW=2.35, ref pJS=0.003) vs DFT 신규 수치
- "scale_major 최적" 결론 유지 여부

### 예상 소요

Transformer × 4 조건 × N=5 = 20 학습 ≈ 30~45분.

---

## T40-3: §6.6 통합 실험 DFT (N=5)

### 실험 조건

기존 `combined_AB_results.json` 구성 매핑:

| # | note | reorder | overlap | 비고 |
|---|---|---|---|---|
| 1 | orig | none | binary | orig_none |
| 2 | orig | segment_shuffle | binary | orig_segment_shuffle |
| 3 | orig | block_permute(32) | binary | orig_block32 |
| 4 | major | none | binary | major_none |
| 5 | major | segment_shuffle | binary | major_segment_shuffle |
| 6 | **major** | **block_permute(32)** | **binary** | **major_block32** ★ |
| 7 | major | markov (τ=1.0) | binary | major_markov |
| 8 | orig | none | continuous | orig_continuous |
| 9 | major | none | continuous | major_continuous |
| 10 | major | block_permute(32) | continuous | major_block32_continuous |

(기존 `combined_AB_results.json` 조합 확인 후 맞춤)

모델: Transformer (PE 유지 + retrain). 입력: DFT continuous OM.

지표: vs 원곡 pJS, vs 원곡 DTW, vs ref pJS, val_loss.

### 출력

`docs/step3_data/combined_AB_dft_gap0.json`

기존 `combined_AB_results.json` 구조 준수 (조합 리스트 + 각 조합의 4지표).

### 보고

- 각 조합 4지표 mean ± std
- major_block32 최종 종합 표 재산출:
  - ref pJS ("학습 정확도", 낮을수록 좋음)
  - vs 원곡 DTW ("선율 차이", 높을수록 좋음)
  - vs 원곡 pJS ("pitch 차이", 최댓값 10~30% 수준)
  - scale match ("1.0이 C major 완전 일치")
- 기존 Tonnetz 결과 (ref pJS=0.002, DTW=2.37/+31%, pJS=0.100) vs DFT 신규 비교
- "위상 보존 + 선율 변화 + 화성 일관성" 균형 유지 여부

### 예상 소요

Transformer × 8~10 조합 × N=5 = 40~50 학습 ≈ 80~120분.

---

## 출력 파일 표준 메타데이터

모든 JSON 최상위에 필수:

```json
{
  "metric": "dft",
  "alpha": 0.25,
  "min_onset_gap": 0,
  "octave_weight": 0.3,
  "duration_weight": 1.0,
  "model": "transformer",
  "n_repeats": 5,
  "date": "...",
  "script": "...",
  "post_bugfix": true
}
```

`utils/result_meta.build_result_header` 활용 권장.

## 실행 순서

```
T40-1 (§6.4 Transformer, ~40-60분)
    ↓
T40-2 (§6.5 Transformer, ~30-45분)
    ↓
T40-3 (§6.6 통합 실험, ~80-120분)
    ↓
phase3_task40_section66_dft_summary.json 저장
```

Python 세션 정책: **같은 Python 세션에서 직렬 실행** (Phase 1·2·2b·38a 동일).
`same_python_session: true`, `status: completed` 기록.

## 예상 총 소요

**3~4시간**. 밤새 실행 OK.

## 주의사항

1. **min_onset_gap=0 / metric='dft' / alpha=0.25 명시 필수** — 모든 학습/inference 호출
   부에 명시.
2. **입력 OM**: §6.7.2 FC-cont 최적이 continuous OM임을 확인했으나, §6.4/§6.5/§6.6 맥락에서는
   기존 실험이 binary/continuous 혼용. **각 실험의 기존 조건 그대로 유지** (T40-1 continuous,
   T40-2/T40-3은 combined_AB 참조).
3. **Task 39 / 39-4 / 38b와 독립**: 파일 영역 분리. 동시 실행 안전. Codex 인스턴스가
   별개면 완전 병렬.
4. **기존 JSON 보존**: `temporal_reorder_dl_v2_results.json`,
   `harmony_continuous_results.json`, `combined_AB_results.json` 덮어쓰기 금지.
   신규는 `*_dft_gap0*.json`.
5. **논문 수정 금지**: 세션 D Task 41(신설 예정)에서 §6.3~§6.6 재서술.
6. **학습 실패 감지**: Transformer 학습 중 NaN/inf 발생하거나 수렴 안 되는 경우 해당
   trial은 skip + 재시도. 전체 N=5 유지.
7. **완료 보고 형식**: Phase 1·2·2b·38a 스타일. Task별 핵심 수치 + 기존 Tonnetz 대비
   변화 방향 + 다음 단계 제언.

## 세션 D 연동 (Task 41 신설 예정)

Task 40 완료 후 세션 D가 §6.3~§6.6 재서술:

- **§6.3 개요**: DFT 기반 위상 보존 변주 맥락 재조정
- **§6.4**: T40-1 Transformer DFT 결과로 표·해석 교체 (기존 Tonnetz → DFT)
  - FC/LSTM 부분은 Task 39 T39-4 결과로 보강 (별도)
- **§6.5**: T40-2 Transformer DFT + T39-5 FC/LSTM DFT 통합 표
- **§6.6**: T40-3 major_block32 수치 전면 교체. 기존 Tonnetz 각주는 "bugfix 이전 참고"로
  유지 또는 제거
- **short.md/full.md 규칙**: gap3 비교 금지, distance-specific 비교는 full.md 한정

Task 40 보고 받으면 세션 E가 커밋 + Task 41 프롬프트 작성.

## 완료 보고 형식

Phase 1·2 스타일:

1. T40-1: 5~6 조건 pitch_js/DTW/val_loss 표 + "딜레마" 재현 여부
2. T40-2: 4 조건 4지표 표 + scale_major 최적 유지 여부
3. T40-3: 8~10 조합 4지표 표 + major_block32 3축 요약
4. 판정: "§6.3~§6.6 서사 유지 / 수치 변동 / 결론 반전" 중 어디에 해당

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음 + 권한 전체 액세스**.
