# Codex 세션 A — Task 39: Wave 2 누락 실험 보강 묶음

## 배경

논문 검토 중 발견된 미실험/누락 항목 5건을 하나의 세션 A 작업으로 묶어 처리.
Task 38a (§7 DFT 재수행)와 **파일 영역 분리**되어 병렬 실행 가능 (단 같은 Codex
인스턴스면 순차). 각 서브태스크 결과는 §6·§7 재서술에 반영 예정.

## 서브태스크 개요

| # | 대응 질문 | 범위 | 출력 JSON |
|---|---|---|---|
| T39-1 | 14-1 후반 / 2-1 | 원곡 MIDI duration 분포 + 16분음표 존재 여부 + GCD 판정 | `duration_distribution_analysis.json` |
| T39-2 | 13 | §6.1 solari DFT 실험 추가 | `solari_dft_gap0_results.json` |
| T39-3 | 14-2 | §6.2 Bach Fugue + Ravel Pavane DFT 실험 추가 | `classical_contrast_dft_gap0_results.json` |
| T39-4 | 16-1 | §6.4 OM 시간 재배치 — FC · LSTM 추가 | `temporal_reorder_fc_dft_gap0.json`, `temporal_reorder_lstm_dft_gap0.json` |
| T39-5 | 16-1 | §6.5 화성 제약 — FC · LSTM 추가 | `harmony_fc_dft_gap0.json`, `harmony_lstm_dft_gap0.json` |

## 필수 참조 파일

### 읽을 것

- `memory/project_phase1_gap0_findings_0417.md`, `project_phase2_gap0_findings_0417.md`
  — 파라미터 확정값 (α=0.25, w_o=0.3, w_d=1.0)
- `memory/feedback_short_md_gap_comparison_exclude.md` — short/full 규칙
- 기존 스크립트 (참고용):
  - `run_solari.py` — §6.1 solari 실험 패턴
  - `run_any_track.py` — 임의 곡 파이프라인
  - `run_temporal_reorder_unified.py` — §6.4 재배치 전략
  - (없으면) `gen_hibari_viz_dft.py` 등에서 DFT 로드 방식
- 기존 JSON (수치 대조, 덮어쓰기 금지):
  - `docs/step3_data/solari_results.json` (dft 키 부재 확정)
  - `docs/step3_data/classical_contrast_results.json` (dft 키 부재 확정)
  - `docs/step3_data/temporal_reorder_dl_v2_results.json` (Transformer 전용)
  - `docs/step3_data/harmony_continuous_results.json` (Transformer 전용)

### 금지

- 논문 `academic_paper_*.md` 수정 (세션 D 영역)
- `CLAUDE.md` 수정
- 기존 JSON 덮어쓰기 — 전부 `*_dft_gap0_*` 또는 `*_dft_*` 접미사로 신규 파일

## 공통 설정

```python
distance_metric = 'dft'
alpha = 0.25              # Phase 2 A10-a 최적 (hibari 기준, 타곡 적용은 아래 주의)
octave_weight = 0.3
duration_weight = 1.0
min_onset_gap = 0
post_bugfix = True
```

**α 적용 주의**: hibari 최적 α=0.25는 7-PC diatonic 구조 기반. solari/aqua(12-PC) 및
Bach/Ravel에서 α 최적이 다를 수 있으나 본 Task는 **hibari 확정값을 일관 적용**하고,
"곡별 α 최적은 향후 과제"로 남긴다 (세션 D가 각주 처리).

---

## T39-1: 원곡 MIDI duration 분포 분석 (Task 14-1 후반 + 2-1)

### 목적

1. **Task 14-1 후반 질문**: "16분음표 등 8분음표보다 작은 duration을 가진 note가
   있었는지, duration의 GCD가 16분음표 기준은 아닌지" 확인.
2. **Task 2-1**: aqua/solari 원곡 duration 분포가 어떻게 되는지, tie 정규화(GCD
   기반 pitch-only labeling)가 합리적인지 판단.

### 분석 대상

- `hibari.mid` (또는 `hibari_*.mid`)
- `solari.mid`
- `aqua.mid`
- `bach_fugue.mid` (파일명 확인)
- `ravel_pavane.mid` (파일명 확인)

### 산출 지표 (각 곡마다)

- 원본 MIDI의 note duration 리스트 (tick 단위 + beat 단위 둘 다)
- 분포 통계: min, max, median, p25/p75, unique value count
- GCD (tick 기준 + beat 기준)
- **16분음표(0.25 beat) 이하 duration 개수 + 비율**
- **8분음표(0.5 beat) 양자화 시 손실되는 note 개수 + 비율**
- 결론: "8분음표 양자화가 손실 없이 가능한가", "실제 GCD는 몇 beat인가"

### 출력

`docs/step3_data/duration_distribution_analysis.json`

구조 예:
```json
{
  "metric": "raw_midi_analysis",
  "date": "...",
  "songs": {
    "hibari": { "unique_durations": [...], "stats": {...}, "gcd_beat": 0.5, "below_8th_note_count": 0, ... },
    "solari": {...},
    "aqua": {...},
    "bach_fugue": {...},
    "ravel_pavane": {...}
  },
  "conclusion": {
    "hibari_gcd": 0.5,
    "16th_note_present": {"hibari": false, "solari": ...},
    "8th_quantization_safe": {"hibari": true, ...}
  }
}
```

### 보고

각 곡별 1줄 요약 + 판정: "8분음표 양자화 합리적" vs "16분음표 정보 손실 발생". 세션 D가
§3/§4.5/§6.2 서술 보강 시 참조.

---

## T39-2: §6.1 solari DFT 실험 추가 (Task 13)

### 목적

`solari_results.json`에 frequency/Tonnetz/voice_leading 3종만 존재, **DFT 미실험**. §6.1
표에 DFT 열을 추가하기 위해 Algorithm 1을 solari + DFT 조건으로 실행.

### 설정

- metric='dft', alpha=0.25, w_o=0.3, w_d=1.0, gap_min=0
- N=10 (기존 `solari_results.json`의 a1_frequency/a1_tonnetz/a1_voice_leading과 일치
  확인 후 맞춤)

### 출력

`docs/step3_data/solari_dft_gap0_results.json`

구조: 기존 `solari_results.json`과 동일한 a1_{metric} 키 구조를 사용하되 dft 한 키만.

### 보고

solari에서 DFT JS mean/std, 기존 frequency/Tonnetz(0.063)와 비교, 12-PC 구조에서 DFT가
유리/불리한지 해석. 세션 D가 §6.1·§4.5.3 참조 갱신.

---

## T39-3: §6.2 Bach Fugue + Ravel Pavane DFT 실험 (Task 14-2)

### 목적

`classical_contrast_results.json`에 frequency/Tonnetz/voice_leading 3종만 존재, **DFT
미실험**. Bach Fugue, Ravel Pavane 각각 DFT 조건 Algorithm 1 실행.

### 설정

- metric='dft', alpha=0.25, w_o=0.3, w_d=1.0, gap_min=0
- N=기존 classical_contrast와 일치 (JSON 헤더 확인)

### 출력

`docs/step3_data/classical_contrast_dft_gap0_results.json`

구조:
```json
{
  "metric": "dft",
  "alpha": 0.25, ...,
  "bach_fugue": { "js_mean": ..., "js_std": ..., "K": ... },
  "ravel_pavane": { "js_mean": ..., "js_std": ..., "K": ... }
}
```

### 보고

각 곡 DFT JS, 기존 3거리 대비 우열, "Tonnetz가 가장 광범위하게 최적" 결론이 DFT 포함 후
유지되는지 판정.

---

## T39-4: §6.4 OM 시간 재배치 — FC·LSTM 추가 (Task 16-1 상반)

### 목적

기존 §6.4는 Transformer만 사용. 이유는 "FC는 시점 독립이라 재배치 무효, LSTM은 PE 개념
없음". 사용자 요청으로 **FC·LSTM도 실증 추가** — FC의 무효성을 실험으로 확인, LSTM은
retrain 방식 가능성 검증.

### 실험 설계

#### FC

- 시점 독립 모델 → OM 행 순서 변경 시 이론상 출력 불변
- 실험: baseline (재배치 없음) + 3가지 재배치 (segment_shuffle, block_permute(32),
  markov(τ=1.0)) × FC
- **가설**: 4개 조건 모두 pitch JS/DTW가 사실상 동일
- retrain 여부: FC는 재배치 OM으로 재학습해도 결과 동일할 것 — `retrain X`만 돌려도 충분

#### LSTM

- PE 없음 (순환 구조 자체가 순서 인코딩)
- 실험: baseline + 3 재배치 × LSTM × retrain X / retrain O
- **가설**: retrain 없으면 약한 재배치, retrain 하면 pitch 붕괴 or 학습 실패

### 설정 (FC·LSTM 공통)

- metric='dft', α=0.25, w_o=0.3, w_d=1.0, gap_min=0
- 입력: DFT continuous OM (§6.7.2 최적)
- N=5 (기존 `temporal_reorder_dl_v2` 수준)

### 출력

- `docs/step3_data/temporal_reorder_fc_dft_gap0.json`
- `docs/step3_data/temporal_reorder_lstm_dft_gap0.json`

구조는 `temporal_reorder_dl_v2_results.json` 형식 준수 (pitch_js, transition_js, DTW,
val_loss 각 셀).

### 보고

- FC: 가설대로 재배치 무효인지 실험적 확인 (pitch JS 변동 < 1% 예상)
- LSTM: retrain X vs O에서 pitch 붕괴 여부
- 세션 D가 §6.4 "Transformer만 사용" 근거 서술을 **실증 자료로 보강** 가능.

---

## T39-5: §6.5 화성 제약 — FC·LSTM 추가 (Task 16-1 하반)

### 목적

§6.5 Algorithm 2 실험도 Transformer만. scale_major 재분배 note 입력을 FC·LSTM에
줬을 때 결과 비교.

### 실험 설계

- 조건: original / baseline / scale_major / scale_penta × {FC, LSTM}
- 입력: 재분배 note + DFT continuous OM (§6.6 설정 통일)
- N=5
- **§6.5 Algorithm 2 평가 지표 그대로 사용**: vs 원곡 pJS, vs 원곡 DTW, vs ref pJS,
  val_loss

### 설정

공통 설정과 동일.

### 출력

- `docs/step3_data/harmony_fc_dft_gap0.json`
- `docs/step3_data/harmony_lstm_dft_gap0.json`

### 보고

- FC: scale_major 재분배 분포를 학습할 때 Transformer 대비 성능
- LSTM: 동일
- §6.7.2에서 FC-cont 최적 확정된 것과 §6.5 결과가 일관되는지 교차 검증

---

## 출력 파일 표준 메타데이터

모든 JSON 최상위에 필수:

```json
{
  "metric": "dft",
  "min_onset_gap": 0,
  "alpha": 0.25,
  "octave_weight": 0.3,
  "duration_weight": 1.0,
  "n_repeats": ...,
  "date": "...",
  "script": "...",
  "post_bugfix": true,
  "song": "..." (T39-1~3만 해당)
}
```

`utils/result_meta.build_result_header` (세션 B Task 33 산출물) 활용 권장.

## 실행 순서

```
T39-1 (duration 분석, 독립)
    ↓
T39-2 (solari DFT)
    ↓
T39-3 (classical DFT, Bach+Ravel)
    ↓
T39-4 (§6.4 FC, §6.4 LSTM 직렬)
    ↓
T39-5 (§6.5 FC, §6.5 LSTM 직렬)
    ↓
phase3_task39_wave2_summary.json 저장
```

Python 세션 정책: **같은 Python 세션에서 직렬 실행** (Phase 1·2 동일). 완료 후
`phase3_task39_wave2_summary.json`에 `same_python_session: true`, `status: completed`
기록.

## 주의사항

1. **Task 38a와 독립**: §7 실험(`step71_*_dft_gap0_*.json`)과 파일 영역이 겹치지 않으므로
   동시 실행 안전. 단 같은 Codex 인스턴스면 순차.
2. **α=0.25 일관 적용**: 타곡(solari, aqua, Bach, Ravel)의 최적 α는 재탐색하지 않음.
   논문 각주 처리는 세션 D 담당.
3. **FC 시점 독립성 실증**: T39-4 FC 결과가 "baseline과 거의 동일"로 나오면 예상대로임.
   그 자체가 §6.4 서술의 실증 근거.
4. **기존 JSON 보존**: 전부 신규 파일명 (`*_dft_gap0*` 접미사). `solari_results.json` 등
   기존 파일에 DFT 키를 덮어쓰지 말 것.
5. **논문 수정 금지**: academic_paper_*.md / CLAUDE.md 손대지 않는다.

## 세션 D 연동 (Task 38b·후속)

Task 39 완료 후 세션 D가 반영할 섹션:

- §3 또는 §4.5: T39-1 duration 분포 결과 요약 (필요 시)
- §6.1: T39-2 solari DFT 열 추가
- §6.2: T39-3 Bach/Ravel DFT 열 추가 + 종합 표 "최적 거리" 재판정
- §6.4: T39-4 FC/LSTM 결과로 "Transformer 선택" 근거 실증 보강
- §6.5: T39-5 FC/LSTM 결과 표 추가

Task 39 보고 받으면 세션 E가 Task 39 커밋 + 세션 D 보강 프롬프트 작성 예정.
