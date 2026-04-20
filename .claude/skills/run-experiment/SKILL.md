---
name: run-experiment
description: 임의의 MIDI 파일에 TDA 음악 분석 파이프라인을 적용하여 frequency / tonnetz / voice_leading 거리 함수 비교 실험을 수행. "이 곡 분석해줘", "MIDI 실험 돌려줘", "파이프라인 적용해줘" 등의 요청에 자동 로드.
allowed-tools: Bash(python *) Read Glob Grep
argument-hint: <midi_file.mid>
---

## TDA Music Pipeline 실험 실행

### 사전 조건
- 작업 디렉토리: `C:\WK14\tda_pipeline`
- MIDI 파일이 해당 디렉토리에 있어야 함
- 필요 패키지: pretty_midi, numpy, pandas, music21

### 실행 절차

1. **MIDI 파일 확인**
   ```bash
   ls tda_pipeline/*.mid
   ```

2. **단일 곡 실험** (frequency / tonnetz / voice_leading × N=10 trials)
   ```bash
   cd tda_pipeline && python -u run_any_track.py <midi_file>
   ```

3. **전체 곡 일괄 실험** (ALL_TRACKS 리스트의 모든 곡)
   ```bash
   cd tda_pipeline && python -u run_any_track.py --all
   ```

### 핵심 처리 단계
- Pitch-only labeling (GCD 기반 tie 해석: duration 무시, pitch 만으로 note identity)
- 통합 chord label 체계 (두 악기의 chord 를 하나의 label map 으로)
- PH rate sweep: 0 ~ 1.5, step 0.05
- Algorithm 1: 3 metrics × N=10 seeds

### 결과 해석 기준 (hibari baseline 참조)
| 곡 | 최적 거리 | JS | 특성 |
|---|---|---|---|
| hibari | tonnetz | 0.0398 | 7 PC, diatonic, entropy 0.974 |
| aqua | tonnetz | 0.0920 | 12 PC, +26.3% 개선 |
| solari | voice_leading | 0.0631 | 12 PC, Transformer 최적 |

### 보고 형식
실험 완료 후 다음을 보고:
1. 전처리 결과 (T, N, num_chords)
2. 각 metric 별 cycle 수 + JS (mean ± std)
3. 최적 metric 및 hibari/solari 대비 패턴 해석
4. (선택) 최우수 trial 의 piano WAV 생성 여부 확인

## Gotchas (누적 실패점)

- 표의 hibari baseline 0.0398은 **구버전(gap=3, Tonnetz)**. **현재 최적은 gap=0, DFT, α=0.25 per-cycle τ → JS=0.00902**. 해석 시 반드시 CLAUDE.md §현재 최적 설정 대조.
- `run_any_track.py`는 2026-04-19 이후 `experiments/` 로 이동됨. 루트에서 호출 시 `path_bootstrap` 덕분에 동작하지만, 직접 import는 실패.
- `K` 값이 곡별로 다름 (hibari=14, solari=15, aqua 미실행, Bach=30, Ravel=37). 하드코딩 금지.
- cache/*.pkl 은 **bugfix 이전 데이터** 가능 — metric 실험 시 `rm -f cache/*.pkl` 후 재실행 권장.
- N=10이 기본이지만 통계 유의성은 N≥20 권장 (Welch t-test).
- Windows bash에서 `cd tda_pipeline && python`은 동작하지만 `python tda_pipeline/run_any_track.py`는 path_bootstrap 실패 가능. **반드시 cd 후 실행**.
