# Codex 세션 C — Task 45-B: 청취 실험 D/E/F WAV 재생성

## 배경

Task 45 (커밋 `36a879b`) 에서 청취 실험 인프라 8 stimuli 중 **5개(A/B/C/G/H) 생성 완료**,
**3개(D/E/F) 누락**. D/E/F는 §6.6.1/§6.6.2 통합 실험(`major_block32`) 조건의 변주 WAV로,
`combined_AB_results.json` / `combined_AB_dft_gap0.json` 에 수치만 있고 **WAV 파일은
저장된 적 없음**.

본 Task 45-B는 D/E/F 3 조건을 재학습·재생성하고 `output/listening_test/` 에 추가한다.

## 필수 참조 파일

### 읽을 것

- `tda_pipeline/run_section66_dft_transformer.py` — Task 40 실행 스크립트 (E/F 재생성의
  구조 참고)
- `tda_pipeline/gen_final_wavs.py` — WAV 렌더링 로직 참고
- `tda_pipeline/docs/step3_data/combined_AB_results.json` — §6.6.1 Tonnetz 설정
- `tda_pipeline/docs/step3_data/combined_AB_dft_gap0.json` — §6.6.2 DFT 설정
- `tda_pipeline/listening_test/generate_test_stimuli.py` — stimuli 생성 파이프라인
  (D/E/F override 스펙 확인)
- `tda_pipeline/listening_test/stimuli_overrides.example.json` — override 포맷
- `memory/feedback_piano_rendering.md` — 렌더링 규칙

### 수정·추가할 것

- 신규 스크립트: `tda_pipeline/listening_test/regenerate_DEF_stimuli.py`
- 출력 WAV: `tda_pipeline/output/listening_test/stimulus_D_*.wav`,
  `stimulus_E_*.wav`, `stimulus_F_*.wav` (gitignored)
- `listening_test/stimuli_overrides.json` — D/E/F 경로 지정 (example 복사 후 실제 경로
  채움)

### 금지

- `academic_paper_*.md` 수정
- `CLAUDE.md` 수정
- 기존 JSON 덮어쓰기

## 3 조건 상세

공통 설정: major_block32 (scale_major 재분배 + block_permute(32) 시간 재배치 + continuous
OM + PE 유지 Transformer/FC).

### D: §6.6.1 Tonnetz-Transformer major_block32

- 거리: Tonnetz (α=0.5 기본), ow=0.3, dw=1.0
- 모드: timeflow (complex 아님)
- OM: continuous
- 모델: Transformer (PE 유지, retrain)
- 학습 N=1 (청취용 단일 trial)
- best seed 선택: `combined_AB_results.json` 의 major_block32_continuous 항목 참조
- 주의: pre-bugfix 조건을 그대로 사용 (역사적 재현성). `combined_AB_results.json` 원본
  스크립트의 bugfix 이전 동작을 재현하기 어려우면 **현재 코드로 동일 설정 재학습** 후
  "post-bugfix 재현" 라벨로 처리.

### E: §6.6.2 DFT-Transformer major_block32

- 거리: DFT α=0.25, ow=0.3, dw=1.0
- 모드: timeflow
- OM: continuous
- 모델: Transformer
- N=1 trial (best JS 선택)
- `combined_AB_dft_gap0.json` 의 `models.transformer.major_block32` 수치(ref pJS 0.080)
  에 해당하는 trial 재현

### F: §6.6.2 DFT-FC major_block32

- 거리: DFT α=0.25, ow=0.3, dw=1.0
- 모드: timeflow
- OM: continuous
- 모델: **FC** (§6.7.2 최적 모델)
- N=1 trial
- `combined_AB_dft_gap0.json` 의 `models.fc.major_block32` 수치(ref pJS 0.041) 대응

## 실행 방식

### 구조

`regenerate_DEF_stimuli.py`:

```python
def regenerate_stimulus_D():
    # Tonnetz α=0.5 pipeline, major_block32 Transformer
    # 학습 → generate → MusicXML → WAV (피아노 렌더링)
    ...

def regenerate_stimulus_E():
    # DFT α=0.25 pipeline, major_block32 Transformer
    ...

def regenerate_stimulus_F():
    # DFT α=0.25 pipeline, major_block32 FC
    ...
```

각 함수는:
1. 파이프라인 설정 (config)
2. PH cycle 로드 (캐시 활용)
3. major_block32 OM 생성 (block_permute 32 + scale_major 재분배 + continuous)
4. 모델 학습 (best seed 또는 N=1)
5. 생성 → MusicXML → WAV
6. stimuli_overrides.json 에 경로 기록

### 피아노 렌더링 설정

`gen_final_wavs.py` 의 렌더링 함수 재사용. 서스테인 페달 on + reverb medium hall +
44.1kHz 16-bit stereo.

### override 파일 업데이트

`stimuli_overrides.example.json` 복사해 `stimuli_overrides.json` 생성. D/E/F 경로 기록.

그 후 `python listening_test/generate_test_stimuli.py --overrides stimuli_overrides.json`
재실행하여 **8/8 stimuli 세트 완성** 확인.

## 공통 설정

```python
# D (Tonnetz)
distance_metric='tonnetz', alpha=0.5, octave_weight=0.3, duration_weight=1.0
mode='timeflow', overlap='continuous', model='transformer'

# E (DFT Transformer)
distance_metric='dft', alpha=0.25, octave_weight=0.3, duration_weight=1.0
mode='timeflow', overlap='continuous', model='transformer'

# F (DFT FC)
distance_metric='dft', alpha=0.25, octave_weight=0.3, duration_weight=1.0
mode='timeflow', overlap='continuous', model='fc'

# 공통
min_onset_gap=0
note_variant='scale_major'  # scale_major 재분배
time_reorder='block_permute', block_size=32
```

## 실행 및 검증

```
1. python listening_test/regenerate_DEF_stimuli.py
    → WAV 3개 + stimuli_overrides.json 업데이트
    ↓
2. python listening_test/generate_test_stimuli.py --overrides stimuli_overrides.json
    → index.html / manifest / catalog 재생성
    ↓
3. output/listening_test/index.html 열어 8/8 재생 가능 확인
```

## 예상 소요

- D (Tonnetz Transformer 재학습): ~10분
- E (DFT Transformer 재학습): ~10분
- F (DFT FC 재학습): ~5분 (FC 빠름)
- 렌더링·파일 정리: 5~10분
- **총 30~40분**

## 산출물

1. `listening_test/regenerate_DEF_stimuli.py` — 신규 스크립트
2. `listening_test/stimuli_overrides.json` — D/E/F 경로 주입
3. `output/listening_test/stimulus_D_tonnetz_transformer.wav` (gitignored)
4. `output/listening_test/stimulus_E_dft_transformer.wav` (gitignored)
5. `output/listening_test/stimulus_F_dft_fc.wav` (gitignored)
6. 갱신된 `output/listening_test/index.html` + manifest + catalog

## 커밋 지침

```
feat(listening_test): Task 45-B D/E/F major_block32 WAV 재생성

§6.6.1/§6.6.2 major_block32 3종 변주 WAV 재학습·렌더링:
- D: Tonnetz-Transformer (α=0.5)
- E: DFT-Transformer (α=0.25)
- F: DFT-FC (α=0.25, §6.7.2 최적 모델)

공통: scale_major 재분배 + block_permute(32) + continuous OM + PE 유지

산출물 (gitignored output 제외):
- listening_test/regenerate_DEF_stimuli.py
- listening_test/stimuli_overrides.json

8/8 stimuli 세트 완성. 피아노 렌더링 규칙 준수.

참조: docs/session_c_task45b_def_regenerate_prompt.md
```

## 검수 체크리스트

- [ ] D/E/F WAV 3개 생성 완료
- [ ] 각 WAV의 음악적 재생 가능 (3~4분 분량)
- [ ] 피아노 렌더링 일관 (sustain + reverb)
- [ ] stimuli_overrides.json에 3 경로 기록
- [ ] generate_test_stimuli.py 재실행 시 manifest에 8 stimuli
- [ ] index.html에서 8/8 재생 가능

## 주의사항

1. **pre-bugfix 재현 불가 시**: D (Tonnetz) 는 `combined_AB_results.json` 이 2026-04-11
   pre-bugfix 결과. 현재 코드로 재학습하면 post-bugfix 수치가 나와 약간 다를 수 있음.
   청취 실험 목적으로는 **post-bugfix 재현**으로 충분 (수치 이슈는 실험 보고서에 각주).
2. **학습 seed 공개**: 각 WAV의 seed, JS, trial 정보를 stimuli_manifest.json에 기록.
3. **모델 학습 실패 감지**: NaN/inf 발생 시 seed 변경하여 재시도.
4. **output/ gitignored**: WAV는 로컬 보관. 배포·공유는 별도 결정.

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음** (Transformer + FC 학습 + 파이프라인
재구성 필요).
