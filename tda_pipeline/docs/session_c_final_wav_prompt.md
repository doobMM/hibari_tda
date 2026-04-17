# 세션 C — 최종 WAV 생성 + 청취 평가 설정 (gap0+DFT 최적)

## 배경

Phase 1 + Phase 2 + Phase 2b 완료로 hibari 최적 설정 확정 (2026-04-17):

- **Algorithm 1 최저**: DFT + gap=0 + timeflow + per-cycle τ_c (continuous OM) →
  JS=**0.01489±0.0014** (N=20, Welch p=2.48e-26)
- **Algorithm 2 최저**: DFT + FC continuous → JS=**0.00035** (N=10, Welch p=1.66e-4)

사용자 결정 맥락: `gap_min=3`을 청취 평가(부자연스러움)로 폐기하고 `gap=0`으로 롤백. 본 세션
C는 **롤백 결정의 청취적 정당성 확인** + **최적 설정 WAV의 감상 평가**가 목적.

병렬 실행 안전: 세션 D Task 37 (academic_paper_*.md + CLAUDE.md) 과 파일 영역 완전 분리
(본 세션은 `tda_pipeline/output/final/` 만 쓴다).

## 참조 규칙

- `memory/feedback_piano_rendering.md` — **서스테인 페달 + reverb 필수 적용**
- `memory/feedback_generation_direction.md` — DL 생성=원곡 복사 문제 인식
- 기존 비교 WAV 스크립트 `tda_pipeline/gen_gap3_comparison.py` (gap0 vs gap3 기존 비교)
- `tda_pipeline/gen_comparison_wavs.py` (관련 비교 도구)

## 작업

### 1. WAV 생성 5종

**설정 공통**: `min_onset_gap=0`, `distance_metric='dft'`, `w_o=0.3`, `w_d=1.0`,
`alpha=0.5` (기본) 또는 `0.25` (§6.8 최적).

1. **`hibari_dft_gap0_algo1_final.wav`** — Algorithm 1 (DFT + per-cycle τ, timeflow,
   continuous OM). 최적 τ_c 벡터 사용 (JSON: `percycle_tau_dft_gap0_results.json`
   best_taus). N=5 후 best JS trial을 MusicXML → WAV.
2. **`hibari_dft_gap0_algo2_fc_cont_final.wav`** — Algorithm 2 (FC-cont). 학습 epochs 200,
   hidden=128, dropout=0.3. inference 결과 best → MusicXML → WAV.
3. **`hibari_original.wav`** — 원곡 MIDI를 동일 피아노 렌더링으로 (비교 기준).
4. **`hibari_dft_gap3_algo1_legacy.wav`** — 레거시 gap=3 조건 Algo1 (청취 롤백 근거 확인용).
5. **`hibari_tonnetz_complex_legacy.wav`** — 레거시 Tonnetz complex (α=0.25, r_c=0.1)
   Algo1 (기존 "절대 최저" 서사가 청각적으로도 열세인지 확인).

### 2. 피아노 렌더링 설정 (필수 준수)

- `UprightPiano.sf2` 또는 프로젝트 기본 사운드폰트
- **서스테인 페달**: 전 구간 on (기본 설정 따름)
- **Reverb**: medium hall 또는 기본값
- 템포: 원곡 기준 (hibari 60 BPM 추정, MIDI 원본 확인)
- 출력: 44.1 kHz, 스테레오, WAV 16-bit

### 3. 출력 위치

`tda_pipeline/output/final/`

- 디렉토리가 없으면 생성 (`output/`는 gitignored이므로 WAV 자체는 커밋 안 됨)
- 파일 목록 `output/final/README.md`에 메타데이터로 정리:
  - 각 WAV의 설정, JS, trial seed, 생성 시각

### 4. 실행 스크립트

기존 `gen_gap3_comparison.py` 패턴을 복사해 `gen_final_wavs.py` 신규 생성 권장.
최적 설정 로드:

- `percycle_tau_dft_gap0_results.json` → best_taus, best trial 정보
- `soft_activation_dft_gap0_results.json` → FC-cont trial 정보
- `step3_results_gap0.json` → DFT baseline 재현 가능성

### 5. 사용자 귀환 후 청취 평가 체크리스트

1. **gap0 vs gap3 Algo1 비교**: gap3 부자연스러움이 실제로 gap0에서 해소되는지
2. **Algo1 vs Algo2 FC-cont**: JS 수치가 크게 다른데(0.01489 vs 0.00035) 청각적으로도
   Algo2가 원곡과 더 가깝게 들리는지
3. **Complex (Tonnetz) legacy vs DFT timeflow**: DFT timeflow가 수치만이 아니라 청각적으로도
   깔끔한지
4. **원곡과의 유사성 vs 창의성**: `feedback_generation_direction.md` 맥락 — "비슷한 느낌의
   다른 공간" 목표가 달성되는지

평가 결과는 별도 memory (`project_final_wav_eval_0417.md`) 또는 피드백 txt로 기록.

## 금지 사항

- `tda_pipeline/docs/academic_paper_*.md` 수정 금지 (세션 D 영역)
- `CLAUDE.md` 수정 금지 (Task 37에서 갱신 예정)
- 기존 JSON 덮어쓰기 금지
- `memory/` 수정 금지 (세션 E 영역)

## 산출물 & 커밋

1. `tda_pipeline/gen_final_wavs.py` (신규 스크립트)
2. `tda_pipeline/output/final/README.md` (메타데이터)
3. WAV 파일들 (gitignored)

커밋:

```
feat(wav): 최종 설정 WAV 5종 생성 스크립트 + 메타데이터

- gap0+DFT Algo1 (per-cycle τ, JS=0.01489★)
- gap0+DFT Algo2 FC-cont (JS=0.00035★)
- 원곡 vs gap3 레거시 vs Tonnetz complex 레거시 비교 쌍
- 피아노 렌더링: 서스테인 페달 + reverb 적용
- WAV 자체는 gitignore. README만 커밋.

청취 평가는 별도 세션에서 수행.
```

## 세션 C 후속 (귀환 후)

1. WAV 청취 평가 수행
2. `memory/project_final_wav_eval_0417.md` 신설
3. 평가 결과에 따라 §4·§6·§8의 미학적 서술 보강 (세션 D 영역)
