# topo_diffusion — 위상 손실 디퓨전이 만든 들판과 그 소리

**연구 문서:** `docs/topo_diffusion_report.md` (디퓨전 본체) · `docs/motif_control_design.md` (모티브 통제)
**원곡:** Ryuichi Sakamoto — *hibari* (*out of noise*, 2009)
**중첩행렬 규격:** K=14 cycle × T=60(약 27초) 또는 T=240(약 1분 50초), 이진화 τ=0.5
**렌더링:** UprightPianoKW SF2 · 44.1 kHz · 16-bit · Stereo · 서스테인 페달 + Reverb + Chorus · 66 BPM (8분음표 = 0.4545초)

이 폴더에는 **중첩행렬(OM)을 먼저 만들고, 그것을 Algorithm 1로 통과시켜 얻은 음악**이 들어간다.
OM 자체는 음악이 아니므로 `.mid` / `.wav` / `.ogg` 는 전부 "그 들판이 낸 소리"다.

---

## 1. 산출물 계열

| 계열 | 만드는 스크립트 | 무엇인가 |
|---|---|---|
| **디퓨전 비교 트랙** | `experiments/make_topo_music.py` | 원곡 OM / 아키텍처만 / 위상 손실 / 장형 합성을 같은 조건에서 나란히 들려주는 대조군 세트 |
| **모티브 통제 트랙** | `experiments/motif_control.py` | 중심 모티브를 조건으로 준 RePaint 생성물. 같은 모티브에서 나온 변주들 |
| **비교 페이지** | `tools/build_topo_listening_page.py` | 들판 그림 + 재생 버튼을 묶은 `listen.html`, 그리고 WAV→OGG 압축본 |

---

## 2. 파일명 규칙

### 2.1 디퓨전 비교 트랙

```
topo_{track}.{mid,wav,ogg}
```

`{track}` 은 `make_topo_music.py` 의 OM 소스 이름을 소문자로 쓴 것이다.

| 파일 stem | OM 소스 | 성격 |
|---|---|---|
| `topo_real_30` | 원곡 OM 창 (T=60) | 기준선 |
| `topo_conv_30` | `conv` 변이 샘플 | 아키텍처 교체 효과만 |
| `topo_full_30` | `full` 변이 샘플 | 위상 손실 + 밀도 손실 |
| `topo_full_long` | `full` + MultiDiffusion (T=240) | ★ 본편 |
| `topo_real_long` | 원곡 OM (T=240) | 본편의 기준선 |

### 2.2 모티브 통제 트랙

```
topo_motif{A|B|C|D}_{skeleton|v1|v2}.{mid,wav,ogg}
```

**모티브 슬롯** — `motif_control.py` 가 자동으로 정하며, 알파벳 순서는 추출 순서다.

| 슬롯 | 출처 |
|---|---|
| `A`, `B`, `C` | hibari OM 에서 재현 횟수 상위로 뽑힌 중심 모티브 (서로 충분히 다른 것만) |
| `D` | 원곡이 거의 쓰지 않는 cycle 조합으로 만든 **합성 모티브**(대조군, 점멸 패턴) |

**역할 접미사** — 같은 모티브가 세 가지 방식으로 들린다.

| 접미사 | 내용 | 듣는 목적 |
|---|---|---|
| `skeleton` | 마스크 영역만 남기고 자유영역을 0으로 비운 뼈대 | "이것이 그 모티브다"를 귀로 확정 |
| `v1` | 조건부 샘플링 변주 1 | 모티브는 같고 사이가 다르다 |
| `v2` | 조건부 샘플링 변주 2 | 같은 모티브의 또 다른 사이 |

> 슬롯 수는 `N_MOTIFS`(hibari 유래) + 1(합성)이고 역할 수는 `N_VARIATIONS` 중 앞 2개 + skeleton 이다.
> 상수를 바꾸면 파일 개수도 따라 바뀐다 — 이 표는 기본 설정 기준.

### 2.3 확장자

| 확장자 | 설명 | 만드는 시점 |
|---|---|---|
| `.mid` | Standard MIDI. 음고·리듬은 Algorithm 1 결과 그대로, 세기(velocity)만 연주 레이어로 손댄 것 | 음악 생성 단계 |
| `.wav` | 최종 오디오 (Stereo, 44.1 kHz, 16-bit PCM) | 음악 생성 단계, `--no-wav` 면 생략 |
| `.ogg` | Vorbis q4 압축본. 페이지 재생용 | 페이지 빌드 단계, ffmpeg 있을 때만 |
| `listen.html` | 들판 그림 + 재생 버튼 비교 페이지 (단일 파일, 오디오는 같은 폴더 상대 참조) | 페이지 빌드 단계 |

---

## 3. 재현

### 3.1 전제

| 필요한 것 | 위치 · 확인법 |
|---|---|
| 학습된 디노이저 | `cache/topo_diffusion_{full,conv_topo,conv}.pt` |
| PH 캐시 (cycle 라벨) | `cache/metric_dft_alpha0p25_ow0p3_dw1p0.pkl` |
| 사운드폰트 | `C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2` |
| ffmpeg | OGG 압축용. 없으면 페이지가 WAV 를 그대로 참조한다 |

### 3.2 순서

```bash
cd C:/WK14/tda_pipeline

# (0) 디노이저 학습 — 이미 .pt 가 있으면 건너뛴다 (4코어 기준 변이당 약 21분, 순차)
python experiments/run_topo_diffusion.py --threads 4

# (1) 디퓨전 비교 트랙: OM 샘플링 → Algorithm 1 → MIDI → WAV
python experiments/make_topo_music.py

# (2) 모티브 통제 트랙: 모티브 추출 → RePaint 조건부 샘플링 → 검증 → MIDI → WAV
python experiments/motif_control.py --variant full --threads 4

# (3) WAV→OGG + listen.html
python tools/build_topo_listening_page.py
```

WAV 렌더링을 빼고 지표만 보고 싶으면 `--no-wav` 를 붙인다.

```bash
python experiments/make_topo_music.py --no-wav
python experiments/motif_control.py --no-wav
```

### 3.3 단계별 부산물

| 단계 | 이 폴더 밖에 남는 것 |
|---|---|
| (0) | `cache/topo_diffusion_{variant}.pt`, `docs/step3_data/topo_diffusion_results.json` |
| (1) | `docs/step3_data/topo_music_manifest.json` |
| (2) | `docs/step3_data/motif_control_results.json` |
| (3) | — (`listen.html` 만 이 폴더에) |

---

## 4. 지표는 여기 적지 않는다

트랙별 음고 JS·협화도·밀도·시간 연속성, 모티브 보존율·변주간 차이는
전부 위 JSON 에 기록되고 `listen.html` 카드에 표시된다.
이 README 는 **무엇이 어떤 이름으로 나오고 어떻게 다시 만드는가**만 다룬다.

---

## 5. 주의

- **`output/` 은 gitignore 대상**이다(`.gitignore:31`). 이 README 를 포함해 폴더 내용은 tracked 되지 않는다.
  공유가 필요하면 `listen.html` + `.ogg` 만 따로 복사한다.
- `listen.html` 은 현재 `topo_music_manifest.json`(§2.1 트랙)만 읽는다.
  모티브 트랙(§2.2)은 `motif_control_results.json` 에 기록되며, 페이지 편입은 별도 작업이다.
- `.mid` 의 velocity 조형은 **연주 레이어이지 알고리즘의 일부가 아니다**.
  연구 주장과 무관한 렌더링 선택이므로 지표 해석에 섞지 않는다.
- 학습·샘플링을 여러 프로세스로 병렬 실행하면 스레드 경합으로 오히려 느려진다.
  한 프로세스에서 `--threads 4` 로 순차 실행할 것.

---

*OM → 음악: `generation.py` Algorithm 1 · 렌더러: `tools/wav_renderer.py`*
