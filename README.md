# hibari-TDA

사카모토 류이치의 **hibari** (out of noise, 2009)를 **Topological Data Analysis (Persistent Homology)** 로 분석하여, 원곡과 위상수학적으로 유사한 구조를 가진 음악을 생성하는 연구 파이프라인.

---

## 🖥️ 파이프라인 대시보드 (코드 탐색기)

연구 코드의 전체 구조를 **JARVIS 스타일 3-패널 인터페이스**로 탐색할 수 있습니다.

> **🔗 라이브**: [pipeline_dashboard.html](https://doobmm.github.io/hibari_tda/tda_pipeline/docs/pipeline_dashboard.html)

| 패널 | 내용 |
|---|---|
| **왼쪽** | 스테이지별 모듈 트리 (Stage 1 전처리 → Stage 4 생성) · 함수 목록 · 검색 |
| **가운데** | 선택 모듈의 소스코드 (Python 신택스 하이라이팅, 함수 클릭 시 자동 스크롤) |
| **오른쪽** | 함수 시그니처 · 파라미터 표(Name/Type/Default/설명) · 반환값 |

🔴 빨간 배지 = 최근 30일 이내 수정된 함수. 로컬 재생성: `python tda_pipeline/tools/gen_dashboard.py`

---

## 배경

본 저장소는 2025년 1학기 **수학탐구 A** 수강 중 시작된 연구 과제를 담고 있습니다. 저장소 루트 디렉토리명 `WK14`는 수업 일정상 **WK14 (2025년 5월 19~25일)** 즈음 초기 수업 과제가 마무리된 시점을 의미합니다. 이후 약 10개월의 공백을 거쳐 **2026년 4월 2일부터 4월 20일까지** 연구를 재개·확장하여 현재의 실험·파이프라인으로 정리하였습니다.

- **저자**: 김민주
- **GitHub**: [doobMM/hibari_tda](https://github.com/doobMM/hibari_tda)
- **주 연구 코드**: [`tda_pipeline/`](./tda_pipeline/) (자체 README 별도 존재)

---

## 📄 먼저 읽을 문서 — 포트폴리오용 축약 논문

연구 내용을 가장 빠르게 파악하려면 **포트폴리오용 축약본 논문**을 먼저 읽어주세요.

> 📘 **[`환대_포트폴리오.md`](./tda_pipeline/docs/%ED%99%98%EB%8C%80_%ED%8F%AC%ED%8A%B8%ED%8F%B4%EB%A6%AC%EC%98%A4.md)** — Markdown
> 📕 **[`환대_포트폴리오.pdf`](./tda_pipeline/docs/%ED%99%98%EB%8C%80_%ED%8F%AC%ED%8A%B8%ED%8F%B4%EB%A6%AC%EC%98%A4.pdf)** — PDF 빌드본

이 문서는 본 연구의 방법론·핵심 결과·결론을 간략히 정리합니다.

---

## 연구 요약

- **대상곡**: hibari (주력), solari, aqua, Bach Fugue, Ravel Pavane (일반화 실험)
- **핵심 개념**
  - note = `(pitch, duration)` 쌍
  - chord = 한 시점에서 동시 활성화된 note 집합
  - **중첩행렬(Overlap Matrix, OM)**: persistent cycle의 시점별 활성화 패턴
  - **GCD 기반 pitch-only labeling**: duration 정규화로 PH 계산 가속
- **4단계 파이프라인**
  1. **전처리** — MIDI → 8분음표 양자화 → 두 악기 분리 → 화음/note 레이블링
  2. **Persistent Homology 탐색** — 가중치 행렬 → 거리 행렬 → barcode (Vietoris-Rips)
  3. **중첩행렬 구축** — cycle별 활성화 판단 (이진 / 연속값)
  4. **음악 생성** — Algorithm 1 (확률 샘플링) / Algorithm 2 (FC·LSTM·Transformer)

## 핵심 결과 (2026-04-20 기준)

| 항목 | 수치 |
|---|---|
| **최적 거리 함수 (hibari)** | DFT — Tonnetz 대비 −56.8% JS |
| **Algorithm 1 최저 JS** | **0.00902 ± 0.00170** (N=20, DFT, α=0.25, per-cycle τ, K=14) |
| **Algorithm 2 최저 JS** | **0.00035 ± 0.00015** (N=10, FC-cont, DFT, α=0.5) |
| **일반화 최적 거리** | 곡에 따라 다름 — aqua/solari: voice_leading 또는 Tonnetz / Bach: Tonnetz / Ravel: frequency |

연구 전체 내용은 포트폴리오용 축약본 `환대_포트폴리오.md` / `환대_포트폴리오.pdf`에서 확인할 수 있습니다.

---

## 🎧 생성 음악 들어보기

원곡(v0) 대비 파이프라인 단계별 개선 흐름을 9개 버전으로 수록했습니다. **OGG**는 브라우저에서 바로 재생·다운로드 가능하고, **MIDI**는 악보·편집용입니다. 렌더링: UprightPiano KW SF2 · 44.1 kHz · 스테레오 · 서스테인 페달 + Reverb.

| ID | 설명 | 길이 | JS ↓ | OGG | MIDI |
|:--:|:-----|:----:|:----:|:---:|:----:|
| **v0** | 원곡 MIDI 직접 렌더링 (기준) | 8'16" | — | [🎵](./tda_pipeline/output/hibari%2B/v0_hibari_original.ogg) | — |
| **v1** | Algo 1 · frequency 거리 (§4.1 baseline) | 13'08" | 0.0335 | [🎵](./tda_pipeline/output/hibari%2B/v1_algo1_frequency_binary.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v1_algo1_frequency_binary.mid) |
| **v2** | Algo 1 · DFT 거리 · Binary OM | 12'33" | 0.0144 | [🎵](./tda_pipeline/output/hibari%2B/v2_algo1_dft_binary.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v2_algo1_dft_binary.mid) |
| **v3** | Algo 1 · DFT · per-cycle τ · α=0.5 | 12'23" | 0.0144 | [🎵](./tda_pipeline/output/hibari%2B/v3_algo1_dft_percycle_tau_alpha05.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v3_algo1_dft_percycle_tau_alpha05.mid) |
| **v4** | Algo 1 · DFT · per-cycle τ · α=0.25 (**최저**) | 12'22" | **0.0107** | [🎵](./tda_pipeline/output/hibari%2B/v4_algo1_dft_percycle_alpha025.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v4_algo1_dft_percycle_alpha025.mid) |
| **v5** | Algo 2 FC-cont · DFT (**수치 절대 최저 ★**) | 8'17" | **0.00022** | [🎵](./tda_pipeline/output/hibari%2B/v5_algo2_fc_cont_dft_alpha05.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v5_algo2_fc_cont_dft_alpha05.mid) |
| **v6** | §6 블록 단위 P3 · DFT · α=0.25 | 8'17" | 0.0148 | [🎵](./tda_pipeline/output/hibari%2B/v6_block_p3_bestof10_m0.ogg) | [🎼](./tda_pipeline/output/hibari%2B/v6_block_p3_bestof10_m0.mid) |
| **vD** | Tonnetz · Transformer · 위상 보존 변주 | 8'14" | 0.014* | [🎵](./tda_pipeline/output/hibari%2B/vD_tonnetz_transformer.ogg) | [🎼](./tda_pipeline/output/hibari%2B/vD_tonnetz_transformer.mid) |
| **vH** | Tonnetz · Complex · per-cycle τ (legacy) | 14'09" | 0.0177 | [🎵](./tda_pipeline/output/hibari%2B/vH_tonnetz_complex_legacy.ogg) | [🎼](./tda_pipeline/output/hibari%2B/vH_tonnetz_complex_legacy.mid) |

> **권장 청취 순서**: v0 → v1 → v2 → v3 → v4 (단계별 개선) → v5 (원곡 거의 모사) → vD (위상 보존 변주) → vH → v6
>
> **\*** vD 의 JS는 ref pitch 기준(vs 원곡은 0.334로 의도적 변주).
> 상세 파라미터 표·MusicXML 악보는 [`tda_pipeline/output/hibari+/README.md`](./tda_pipeline/output/hibari+/README.md) 참조.

> **저장 용량 주의**: 원본 WAV 파일(개당 87–150 MB, 총 ~1 GB)은 GitHub 용량 제한으로 저장소에 포함하지 않았습니다. 위 OGG Vorbis(개당 6–12 MB, 총 ~80 MB)는 원본 WAV 대비 약 8% 용량으로 사실상 동일한 청취 품질입니다.

---

## 🕹️ 인터랙티브 데모

### 🌐 라이브 (GitHub Pages)

설치 없이 브라우저에서 바로 접속할 수 있습니다.

- **허브**: <https://doobmm.github.io/hibari_tda/>
- **Tonnetz 시각화**: <https://doobmm.github.io/hibari_tda/tda_pipeline/tonnetz_demo/>

<p align="center">
  <img src="./tda_pipeline/docs/qr_live_demo.png" alt="Live demo QR code" width="180">
  <br>
  <sub>📱 QR → <code>doobmm.github.io/hibari_tda</code> 허브</sub>
</p>

> 최초 배포 시 GitHub Pages 활성화가 필요합니다 (저장소 **Settings → Pages → Source: `main` / root** → Save, 1~2분 후 활성). 활성 후 push 할 때마다 자동 재배포됩니다.

### 데모 내용

- **Tonnetz 시각화** — [`tda_pipeline/tonnetz_demo/`](./tda_pipeline/tonnetz_demo/)
  hibari 의 원곡 연주와 **Tonnetz 격자 위 H1 cycle overlay**를 동기 재생. Playback / Controls / Appearance / Sound / TDA 5탭으로 배색·오디오·사이클 강조 방식을 조정할 수 있습니다. Bootstrap + Tone.js 기반 정적 HTML.
  **파이프라인 7단계 MIDI(v0 원곡 + v1~v6 생성본)가 페이지에 직접 인라인되어 있어 다운로드·추가 설정 없이 버튼 한 번으로 즉시 재생** 가능합니다 (embed 도구: [`tda_pipeline/tools/embed_hibari_midis.py`](./tda_pipeline/tools/embed_hibari_midis.py)).

### 로컬 실행 (오프라인 또는 수정 중일 때)

```bash
# 저장소 루트에서 한 번만 서버 띄우면 허브·Tonnetz 데모 모두 접근 가능
python -m http.server 8000
# → http://localhost:8000/                                              (허브)
# → http://localhost:8000/tda_pipeline/tonnetz_demo/                    (시각화)
```

---

## 디렉토리 구조 (루트)

```
WK14/
├── README.md                   ← 이 파일 (저장소 대문)
├── .gitignore
├── process.py                  ← 초기 MIDI 탐색 스크립트 (WK14 과제 당시 원본)
├── WK14/                       ← WK12~14 과제 노트북 아카이브
│   ├── WK12_floatingpt_error.ipynb
│   ├── WK13_analysis.ipynb
│   └── WK13_model.ipynb
├── tda_pipeline/               ← 주 연구 코드 (자체 README 존재)
│   ├── config.py
│   ├── preprocessing.py
│   ├── weights.py
│   ├── overlap.py
│   ├── generation.py
│   ├── musical_metrics.py
│   ├── eval_metrics.py
│   ├── pipeline.py
│   ├── topology.py
│   ├── run_any_track.py        ← 임의 MIDI 파이프라인 진입점
│   ├── run_test.py             ← hibari 빠른 smoke test
│   ├── experiments/            ← 누적 실험 스크립트 (49개)
│   ├── tests/                  ← 단위 테스트
│   ├── tools/                  ← 보조 도구 (WAV 렌더링 등)
│   ├── debug/                  ← 진단 스크립트
│   ├── docs/                   ← 논문·Figure·실험 결과 JSON
│   ├── listening_test/         ← 청취 실험 웹 플레이어 + stimuli
│   ├── hibari_dashboard/       ← (archived: 2026-04-16 pre-Phase2 snapshot)
│   └── tonnetz_demo/           ← Tonnetz 격자 + H1 cycle overlay 재생 (7단계 MIDI 인라인)
└── index.html                  ← 루트 랜딩 허브 (GitHub Pages 대문)
```

---

## 설치

### 요구 환경
- **OS**: Windows 10/11 (개발 환경), Linux도 대부분 동작
- **Python**: 3.10
- **시스템 의존**: `xelatex` (한글 논문 PDF 빌드 시)

### 의존 패키지

```bash
pip install numpy pandas matplotlib pretty_midi music21 torch ripser
# 선택: librosa, mido, tqdm, tabulate
```

주요 패키지:
- `pretty_midi`, `music21` — MIDI I/O
- `numpy`, `pandas` — 수치 연산
- `torch` — FC/LSTM/Transformer 모델
- `ripser` — Vietoris-Rips 복합체 barcode 계산 (교수님 원본 numpy 구현 백업 있음)
- `matplotlib` — 시각화

```bash
cd tda_pipeline
python run_test.py    # hibari 스모크 테스트. 캐시 있으면 수 초 내 완료
```

---

## 빠른 시작

### 임의 MIDI 파일에 파이프라인 적용
```bash
cd tda_pipeline
python run_any_track.py path/to/song.mid
python run_any_track.py --all          # 지원되는 모든 곡 일괄
```

### hibari 전체 파이프라인 (캐시 기반, 빠름)
```bash
cd tda_pipeline
python run_test.py
```

### 특정 곡 전용 진입점
```bash
python run_aqua.py
python run_solari.py
```

---

## 사용법 — 파라미터로 파이프라인 제어

세 가지 주요 축에서 코드 내 인자를 바꿔 실험할 수 있습니다.

### 1) 거리 함수 선택

`tda_pipeline/musical_metrics.py` + `config.py`에서 제어.

```python
from config import MetricConfig

# 단일 metric
cfg = MetricConfig(metric='dft', octave_weight=0.3, duration_weight=1.0)
# metric ∈ {'frequency', 'tonnetz', 'voice_leading', 'dft'}

# hybrid (두 metric 선형 결합)
cfg = MetricConfig(
    metric='hybrid',
    base_metric='dft',
    hybrid_alpha=0.25,     # α=0.25 → 0.25·base + 0.75·tonnetz
)
```

| metric | 의미 | hibari 최적 시 JS |
|---|---|---|
| `frequency` | 공동 등장 빈도 역수 | 0.0345 |
| `tonnetz` | 장3도/완전5도 격자 BFS | 0.0274 |
| `voice_leading` | 반음 차이 | 0.0346 |
| `dft` | Fourier 공간 L2 | **0.0213 ★** |

### 2) 중첩행렬 생성 모드

`tda_pipeline/overlap.py` + `config.py`.

```python
from config import OverlapConfig

# 이진 중첩행렬 (기본)
cfg = OverlapConfig(mode='binary', gap_min=0)

# 연속값 중첩행렬 — 글로벌 threshold
cfg = OverlapConfig(mode='continuous', tau=0.7)

# 연속값 + per-cycle τ_c (Algorithm 1 최적)
cfg = OverlapConfig(mode='continuous', per_cycle_tau=True)
```

`gap_min`: cycle 활성화 판단 시 허용 gap. hibari에서는 `0` 권장 (청취 평가 기반).

### 3) 음악 생성

`tda_pipeline/generation.py`.

```python
from generation import algorithm1_optimized, train_and_generate

# Algorithm 1: 확률 샘플링 (빠름, ~50ms)
seq, stats = algorithm1_optimized(
    overlap_matrix=om,
    cycle_labeled=cycles,
    notes_dict=nd,
    notes_label=nl,
    temperature=3.0,
    seed=7309,
)

# Algorithm 2: FC 모델 (정확, ~30초)
seq, stats = train_and_generate(
    model='fc',           # 'fc' | 'lstm' | 'transformer'
    overlap_matrix=om,
    epochs=500,
)
```

주요 파라미터:
- `temperature`: 샘플링 온도 (hibari 최적 T=3.0)
- `seed`: 재현용 seed
- `model`: 신경망 아키텍처
- `epochs`: 학습 횟수 (FC는 500 권장)

### 4) 전체 파이프라인을 한 번에

```python
from pipeline import run_full_pipeline
from config import MetricConfig, OverlapConfig

result = run_full_pipeline(
    midi_path='hibari.mid',
    metric_cfg=MetricConfig(metric='dft', octave_weight=0.3),
    overlap_cfg=OverlapConfig(mode='continuous', per_cycle_tau=True),
    gen_method='algorithm1',   # 또는 'fc' / 'lstm' / 'transformer'
    n_repeats=10,              # seed 반복 횟수
    seed_base=7300,
)
print(result['js_mean'], '±', result['js_std'])
```

---

## 자주 쓰는 실험 스크립트

전부 `tda_pipeline/experiments/` 아래.

| 스크립트 | 목적 |
|---|---|
| `run_phase3_task38a_dft_gap0.py` | §6 Prototype OM 비교 (P0~P3) + best-of-10 |
| `run_dft_suite.py` | §4.1 거리 함수 grid |
| `run_percycle_tau_dft.py` | per-cycle τ_c Algorithm 1 실험 |
| `run_fc_cont_dft.py` | Algorithm 2 FC + continuous OM |
| `run_alpha_grid_dft.py` | α-hybrid grid search |

루트에서 직접 실행 가능 (`path_bootstrap` 헤더가 sys.path를 조정).

---

## 포트폴리오 PDF 빌드

```bash
cd tda_pipeline/docs
python build_academic_pdf.py 환대_포트폴리오.md
```

---

## 기여 / 연구 협업

- 논문 초안 리뷰, 실험 재현, 새 곡 적용 등의 기여 환영
- 현재 스크립트 동작은 Windows 기준으로 테스트됨. Linux/macOS 호환 이슈 발견 시 Issue 제보 부탁드립니다.
- 청취 실험 피험자 모집 중 (2026년 봄): `tda_pipeline/listening_test/` 참조

---

## 인용

선행·관련 연구:
- 이동진, Mai Lan Tran, 정재훈, "국악의 기하학적 구조와 인공지능 작곡", 2022
- Mai Lan Tran et al., "TDA of Korean Music in Jeongganbo: A Cycle Structure", arXiv:2103.06620, 2021
- Cohen-Steiner, Edelsbrunner, Harer, "Stability of Persistence Diagrams", Discrete Comput. Geom. 37, 2007
- Catanzaro, "Generalized Tonnetze", arXiv:1612.03519, 2016
- Tymoczko, "The Generalized Tonnetz", J. Music Theory 56:1, 2012

본 연구를 인용하려면:
```
김민주, "TDA를 활용한 류이치 사카모토의 〈hibari〉 구조 분석 및 위상구조 기반 AI 작곡 파이프라인 제시",
2026. https://github.com/doobMM/hibari_tda
```

---

## 라이선스

본 저장소는 **Open Use License (Attribution + Share-Alike)** 로 공개됩니다. 자세한 조건은 루트의 [`LICENSE`](./LICENSE) 파일을 참고하세요.

요약:
- ✅ 학술·연구·상업적 목적의 열람·복제·수정·재배포·판매 허용
- ✅ 저작자 표시(Attribution) 필수
- ✅ 파생 저작물은 본 라이선스 또는 CC BY-SA 4.0 등 동등 개방형 라이선스로 공개

음악 저작권: hibari 등 원곡 MIDI 파일은 원저작자(사카모토 류이치·레코드사)에게 권리가 있으며 `.gitignore`로 제외되어 저장소에 포함되지 않습니다. 상업적 활용 시 음원 저작권은 이용자가 별도로 확보해야 합니다.
