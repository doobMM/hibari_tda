# TDA Music Pipeline

사카모토 류이치의 **hibari** (out of noise, 2009)를 **Topological Data Analysis (Persistent Homology)** 로 분석하여, 원곡과 위상수학적으로 유사한 구조를 가진 음악을 생성하는 연구 파이프라인.

> **📘 먼저 읽을 문서**: [`docs/환대_포트폴리오.md`](./docs/%ED%99%98%EB%8C%80_%ED%8F%AC%ED%8A%B8%ED%8F%B4%EB%A6%AC%EC%98%A4.md) — 연구 전체를 빠르게 파악할 수 있는 포트폴리오용 축약본

저장소 전체 개요는 [상위 README](../README.md) 참조. 본 README는 `tda_pipeline/` 내부 코드 · 스크립트 · 실험 흐름에 집중합니다.

---

## 연구 배경

- **대상곡**: hibari (주력), solari, aqua, Bach Fugue, Ravel Pavane (일반화 실험)
- **핵심 아이디어**: 음악의 화음·note 구조를 그래프로 모델링 → Vietoris-Rips 복합체의 Persistent Homology 계산 → 발견된 cycle을 시드로 재생성
- **선행연구 대비 공헌**:
  - intra / inter 가중치 분리 설계
  - 음악 이론 기반 거리 함수 4종 (`frequency` / `tonnetz` / `voice_leading` / `dft`)
  - 연속값 중첩행렬 + per-cycle threshold τ_c
  - FC / LSTM / Transformer 기반 Algorithm 2 도입

---

## 핵심 결과 (2026-04-20 기준, N=10~20)

| 지표 | 수치 | 조건 |
|------|------|------|
| **Algorithm 1 (확률 샘플링) 최저 JS** | **0.00902 ± 0.00170** | DFT + hybrid α=0.25 + per-cycle τ + K=14 |
| **Algorithm 2 (FC-cont) 최저 JS** | **0.00035 ± 0.00015** | DFT + continuous OM + FC + α=0.5 |
| **최적 거리 함수 (hibari)** | **DFT** | Tonnetz 대비 −56.8%, voice_leading 대비 −62.4% |
| **첫 블록 vs 전체 곡** | 블록 0.01479 ≒ full-song Phase 1 | Task 56 Option B 창 통일 후 |
| **거리 함수-목적 정합성** | 곡마다 다름 | hibari: DFT / solari: voice_leading / Bach: Tonnetz / Ravel: frequency |

---

## 빠른 시작

```bash
cd tda_pipeline

# 가장 빠른 smoke test (캐시 기반, 수 초)
python run_test.py

# 임의 MIDI 파일 처리
python run_any_track.py path/to/song.mid
python run_any_track.py --all      # 지원 곡 일괄

# 곡별 전용 진입점
python run_aqua.py
python run_solari.py
```

---

## 파일 구조 (2026-04-19 재편 이후)

```
tda_pipeline/
│
├── 메인 파이프라인 (9 모듈)
│   ├── config.py                 # MetricConfig / OverlapConfig / 전역 설정
│   ├── preprocessing.py          # MIDI → 8분음표 양자화 → 화음/note 레이블링
│   ├── weights.py                # intra/inter 가중치 + 거리 행렬
│   ├── overlap.py                # 중첩행렬 (binary / continuous / per-cycle τ)
│   ├── generation.py             # Algorithm 1 (샘플링) + Algorithm 2 (FC/LSTM/Transformer)
│   ├── musical_metrics.py        # Tonnetz / voice_leading / DFT 거리
│   ├── eval_metrics.py           # JS divergence / coverage / transition matrix
│   ├── pipeline.py               # 전체 흐름 오케스트레이션 + 캐싱
│   └── topology.py               # Ripser 래퍼 (교수님 원본 numpy 백업 함께)
│
├── 진입점 + core 도메인
│   ├── run_any_track.py          # 임의 MIDI에 파이프라인 적용 (일반화)
│   ├── run_test.py               # hibari 스모크 테스트 (pkl 기반, 빠름)
│   ├── run_aqua.py / run_solari.py
│   ├── note_reassign.py          # "방향 A" 거리 보존 note 재분배
│   ├── temporal_reorder.py       # "방향 B" 시간 재배치
│   ├── sequence_metrics.py       # DTW / pitch JS 평가
│   ├── cycle_selector.py         # cycle 선택 유틸
│   ├── precompute_metrics.py     # metric별 캐시 사전계산
│   └── professor.py              # 원본 참조 (수정 금지)
│
├── 재편된 서브폴더
│   ├── experiments/              # 누적 실험 스크립트 49개 (path_bootstrap 포함)
│   ├── tests/                    # 단위 테스트 4개
│   ├── tools/                    # gen_*, visualize*, wav_renderer 등
│   ├── debug/                    # 진단 스크립트 5개
│   ├── archive/                  # 아카이브된 모듈 3개 (adaptive_search 등)
│   └── utils/                    # result_meta.py 등
│
├── docs/                         # 포트폴리오 + Figure + 실험 결과 JSON
│   ├── 환대_포트폴리오.md                     # 포트폴리오 축약본 ★먼저 읽기
│   ├── 환대_포트폴리오.pdf
│   ├── build_academic_pdf.py                  # md → PDF 변환
│   ├── figures/                               # Figure PNG + 생성 스크립트
│   └── step3_data/                            # 실험 결과 JSON
│
├── listening_test/               # 청취 실험 stimuli + 웹 플레이어
├── hibari_dashboard/             # 분석 대시보드
│
├── cache/                        # metric별 PH 결과 캐시 (pkl, gitignored)
├── output/                       # 생성된 MIDI / WAV / MusicXML (gitignored)
└── *.mid                         # 원곡 MIDI 파일 (gitignored)
```

실행 규칙: `experiments/` · `tests/` 내 스크립트는 첫 줄에 `path_bootstrap` 블록이 있어 **루트에서 `python experiments/run_xxx.py`** 또는 **경로 직접 호출** 모두 가능.

---

## 사용법 — 파라미터로 제어하기

### 1) 거리 함수 선택

```python
from config import MetricConfig

# 단일 metric
cfg = MetricConfig(
    metric='dft',               # 'frequency' | 'tonnetz' | 'voice_leading' | 'dft'
    octave_weight=0.3,          # hibari 최적
    duration_weight=1.0,        # hibari 최적 (DFT 조건)
)

# hybrid — base + tonnetz 선형 결합
cfg = MetricConfig(
    metric='hybrid',
    base_metric='dft',
    hybrid_alpha=0.25,          # 0.25 · base + 0.75 · tonnetz
)
```

| metric | 원리 | hibari 단일 최적 JS |
|---|---|---|
| `frequency` | 공동 등장 빈도 역수 | 0.0345 |
| `tonnetz` | 장3도/완전5도 격자 BFS | 0.0274 |
| `voice_leading` | 반음 차이 | 0.0346 |
| `dft` | Fourier 공간 L2 | **0.0213 ★** |
| `hybrid(dft, α=0.25)` + per-cycle τ | 최종 Algorithm 1 최적 | **0.00902 ★★** |

### 2) 중첩행렬 생성

```python
from config import OverlapConfig

# 이진 중첩행렬 (기본)
cfg = OverlapConfig(mode='binary', gap_min=0)

# 연속값 — 글로벌 threshold
cfg = OverlapConfig(mode='continuous', tau=0.7)

# 연속값 + per-cycle τ_c (Algorithm 1 최저)
cfg = OverlapConfig(mode='continuous', per_cycle_tau=True)
```

- `gap_min=0`: cycle 활성화 판단에서 허용 gap. hibari는 청취 평가 결과 0으로 확정.
- `per_cycle_tau=True`: 각 cycle별 개별 threshold로 Algorithm 1 JS −58.7% (p=2.48e-26).

### 3) 음악 생성

```python
from generation import algorithm1_optimized, train_and_generate

# Algorithm 1 — 확률 샘플링 (~50ms)
seq, stats = algorithm1_optimized(
    overlap_matrix=om,
    cycle_labeled=cycles,
    notes_dict=nd,
    notes_label=nl,
    temperature=3.0,            # hibari 최적
    seed=7309,
)

# Algorithm 2 — 신경망 기반 (~30초)
seq, stats = train_and_generate(
    model='fc',                 # 'fc' | 'lstm' | 'transformer'
    overlap_matrix=om,
    epochs=500,
    continuous_input=True,      # FC-cont 권장
)
```

| 모델 | Algorithm 2 JS | 특성 |
|---|---|---|
| FC (continuous) | **0.00035 ★** | Algorithm 2 최저 |
| Transformer | 0.00276 | scale 제약과 좋은 상호작용 |
| LSTM | 0.240 (hibari) | 시간 의존성이 음악 구조와 불일치 |

### 4) 전체 파이프라인 한 번에

```python
from pipeline import run_full_pipeline
from config import MetricConfig, OverlapConfig

result = run_full_pipeline(
    midi_path='hibari.mid',
    metric_cfg=MetricConfig(metric='dft', octave_weight=0.3),
    overlap_cfg=OverlapConfig(mode='continuous', per_cycle_tau=True),
    gen_method='algorithm1',    # 또는 'fc' / 'lstm' / 'transformer'
    n_repeats=10,
    seed_base=7300,
)
print(result['js_mean'], '±', result['js_std'])
```

---

## 자주 쓰는 실험 스크립트

모두 `experiments/` 아래. 논문 §번호와 대응.

| 스크립트 | 대응 논문 절 | 목적 |
|---|---|---|
| `run_dft_suite.py` | §4.1 | 거리 함수 grid (frequency/tonnetz/vl/dft) |
| `run_ow_gridsearch_dft.py` | §4.1a | octave_weight 튜닝 |
| `run_dw_gridsearch_dft.py` | §4.1b | duration_weight 튜닝 |
| `run_step3_continuous_dft_gap0.py` | §4.2 | Binary vs Continuous OM |
| `run_fc_cont_dft.py` | §4.3a | Algorithm 2 FC + continuous |
| `run_percycle_tau_dft.py` | §4.3 / §5.8.1 | per-cycle τ 검증 |
| `run_alpha_grid_dft.py` | §5.7 / §5.8.1 | α-hybrid grid search |
| `run_phase3_task38a_dft_gap0.py` | §6 | Prototype OM 전략 P0~P3 + best-of-10 |

N=10, N=20 반복으로 JS mean ± std + Welch t-test 기반 통계적 유의성 보고.

---

## 포트폴리오 PDF 빌드

```bash
cd docs

# Markdown → PDF (한글 폰트 자동 탐색, ~/AppData/... Nanum 폴백 포함)
python build_academic_pdf.py 환대_포트폴리오.md
```

---

## 환경 설정 비고

### 폰트 재생성 시 (docs/figures/)

`docs/figures/gen_fig_*.py`는 Claude `canvas-design` 스킬 폰트를 사용합니다. 외부 환경에서 figure 재생성 시:

```bash
# 옵션 A: 환경변수로 폰트 경로 주입
export CANVAS_FONTS_DIR=/path/to/canvas-fonts   # Linux/macOS
set CANVAS_FONTS_DIR=C:\path\to\canvas-fonts    # Windows cmd

python docs/figures/gen_fig_vr_complex.py
```

폰트 경로가 없으면 Windows 시스템 폰트(`SYSF`)로 폴백됩니다 (일부 스크립트만).

### 한글 폰트 (docs/build_academic_pdf.py)

`~/AppData/Local/Microsoft/Windows/Fonts/`의 **NanumSquare_ac** 또는 **NanumGothic**을 탐색 → 없으면 시스템 폰트로 폴백. 한글 PDF 렌더링이 깨지면 NanumGothic을 사용자 폰트 폴더에 설치하세요.

---

## 연구 맥락 및 인용

본 연구는 2025년 1학기 수학탐구 A 수강 중 시작된 초기 과제(`WK14/`)에 기반하며, 약 10개월의 공백 이후 2026년 4월 2일부터 4월 20일까지 재개·확장되었다.

선행·관련 연구:
- 이동진, Mai Lan Tran, 정재훈, "국악의 기하학적 구조와 인공지능 작곡", 2022
- Mai Lan Tran et al., "TDA of Korean Music in Jeongganbo: A Cycle Structure", arXiv:2103.06620, 2021
- Cohen-Steiner, Edelsbrunner, Harer, "Stability of Persistence Diagrams", Discrete Comput. Geom. 37, 2007
- Heo, Choi, Jung, 2025 (path-representable pseudo-metrics)
- Catanzaro, "Generalized Tonnetze", arXiv:1612.03519, 2016
- Tymoczko, "The Generalized Tonnetz", J. Music Theory 56:1, 2012

인용 형식:
```
김민주, "TDA를 활용한 류이치 사카모토의 〈hibari〉 구조 분석 및 위상구조 기반 AI 작곡 파이프라인 제시",
2026. https://github.com/doobMM/hibari_tda
```

---

## 라이선스

저장소 루트의 [`LICENSE`](../LICENSE) 참조 — **Open Use License (Attribution + Share-Alike)**.

- ✅ 학술·연구·상업적 목적 사용·수정·재배포·판매 (저작자 표시 필수)
- ✅ 파생 저작물은 동일 조건(또는 CC BY-SA 4.0 등 동등 개방형) 라이선스로 공개
- MIDI 음원 저작권은 원저작자에게 귀속 — `.mid` 파일은 `.gitignore`로 제외, 상업 활용 시 이용자가 별도 확보
