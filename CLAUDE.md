# CLAUDE.md — TDA Music Pipeline

## 프로젝트 개요

사카모토 류이치의 곡들을 **Topological Data Analysis(Persistent Homology)**로 분석하여, 원곡과 **위상수학적으로 유사한 구조**를 가진 음악을 생성하는 연구 파이프라인. 주 대상곡은 *out of noise* (2009) 수록곡 **hibari**이며, **solari**, **aqua** 등 다른 곡으로 일반화 실험을 진행 중.

### 핵심 개념

- **note** = `(pitch, duration)` 쌍. hibari는 23개, solari는 34개, aqua는 51개 고유 note (GCD 기반 pitch-only labeling 적용 후).
- **chord** = 한 시점에서 동시에 활성화된 note들의 집합.
- **rate** 파라미터: `timeflow_weight = intra_weights + rate × inter_weight`. rate를 0→1.5로 변화시키며 위상 구조(cycle/void)의 출현/소멸을 추적.
- **중첩행렬(Overlap Matrix)**: 발견된 cycle들이 각 시점에서 활성화되는지를 나타내는 행렬. 이진(0/1) 또는 연속값([0,1]) 버전. 음악 생성의 seed.
- **GCD 기반 pitch-only labeling**: 모든 note의 duration을 GCD(=1, 8분음표 단위)로 정규화. 긴 음은 짧은 음의 붙임줄(tie)로 해석. unique (pitch, dur) 수를 대폭 감소시켜 PH 계산 가속.

### 4단계 파이프라인

```
1. 전처리 (preprocessing.py)
   MIDI → 8분음표 양자화 → 두 악기 분리 → 화음/note 레이블링
   
2. Persistent Homology 탐색 (weights.py + topology.py)
   가중치 행렬 → refine → 거리 행렬 → generateBarcode(Vietoris-Rips)
   거리 함수: frequency / tonnetz / voice_leading / dft
   
3. 중첩행렬 구축 (overlap.py)
   cycle별 활성화 판단 → scale 조정 → 이진 또는 연속값 중첩행렬
   
4. 음악 생성 (generation.py)
   Algorithm 1: 확률적 샘플링 (규칙 기반, ~50ms)
   Algorithm 2: FC / LSTM / Transformer 신경망 (학습 기반, ~30s-3min)
```

## 현재 상태 (2026-04-17 기준)

### 완료된 주요 실험

| 실험 | 핵심 결과 |
|---|---|
| §4.1 거리 함수 비교 (N=20) | DFT 0.0213★ (frequency -38.2%, Tonnetz -56.8%, voice_leading -62.4%) |
| §3.3a Continuous overlap (N=20) | τ=0.7 이진화가 추가 -39.1% (0.0488→0.0297) |
| §3.4a 개선 F (N=5) | Continuous + FC → JS 0.0004 ★ 본 연구 최저 |
| §3.6 곡 고유 구조 | deep scale, entropy 0.974, phase shifting |
| §7.1 모듈 단위 생성 | P4+C best JS 0.0258, 첫 모듈 정당성 |
| §7.2 aqua/solari/Bach/Ravel 일반화 | 곡 성격이 최적 도구 결정 |
| §7.7 Continuous 정교화 3종 | per-cycle τ +48.6%, soft Algo2 +64.3% |
| §7.8 α grid search (N=20) | α=0.0(순수 Tonnetz) 최적 |
| octave_weight 튜닝 (N=10) | ow=0.3 최적, JS -18.8% |
| 감쇄 lag 가중치 (lag 1~4) | hibari Tonnetz JS -70% |
| 방향 A: note 재분배 (두 전략 비교) | 전략 A(위치 기반 tonnetz_nearest)+wide(48-84) pitch_js=0.2930 ★, 전략 B(Hungarian ascending) 0.3815. vwide·cycle_perm 폐기 |
| 방향 B: 시간 재배치 | pitch↔선율 딜레마, 단독 한계 |
| Barcode Wasserstein 모듈 선택 | Pearson(W,JS)=0.503 |
| Wasserstein 제약 note 재분배 | 계수 무관, 효과 제한적 |
| Complex weight 모드 grid search | r_c=0.1(simul 소량)이 전 조합에서 최적, timeflow 대비 −41%~−55% robust |

### 핵심 발견 — 곡의 성격이 최적 도구를 결정한다

| 곡 | PC 수 | 최적 거리 | 최적 모델 | 해석 |
|---|---|---|---|---|
| hibari | 7 (diatonic) | DFT | FC | 스펙트럼 구조 포착, entropy 0.974 |
| solari | 12 (chromatic) | voice_leading | Transformer | 선율적 진행 |
| aqua | 12 (chromatic) | Tonnetz | (미실행) | Tonnetz +26.3% |
| Bach Fugue | 12 (chromatic) | Tonnetz | — | 대위법인데 Tonnetz 최적 (-54.8%) |
| Ravel Pavane | 12 (N=49) | frequency | FC | 풍부한 분포 → 빈도 가중 유리 |

### hibari 현재 최적 설정

```
거리 함수: DFT (w_o=0.3, w_d=1.0)
Hybrid α: 0.25 (§6.8 확정, DFT α-hybrid grid)
모드: timeflow (Complex는 Tonnetz 한정 유효 — §6.9 Task 34b 확정)
Lag: lag 1~4 감쇄 가중 (DFT에서 lag=1 대비 -7.1%, `decayed_lag_dft_results.json`)
중첩행렬: continuous activation + per-cycle τ_c (DFT continuous OM 기반)
생성 모델:
  - Algorithm 1: DFT + per-cycle τ (α=0.25, K=14) → JS=0.00902±0.00170 (N=20) ★ (α-grid 재탐색, percycle_tau_dft_gap0_alpha_grid_results.json)
  - Algorithm 2: FC + continuous 입력 → JS=0.00035±0.00015 (N=10, Welch p=1.66e-4) ★
gap_min: 0
온도: T=3.0 (`section77_experiments.json` best_temperature)
```

### 다음 할 작업 (세션별)

아래 "다음 우선 작업" 섹션 참조.

## 폴더 구조

```
C:\WK14\
├── CLAUDE.md                     ← 이 파일
├── .claude/skills/               ← Claude Code skills
│   ├── run-experiment/           ← MIDI 분석 파이프라인 실행
│   ├── research-next/            ← 선행연구 기반 다음 스텝
│   └── explain-research/         ← 비전공자용 연구 설명
│
└── tda_pipeline/                 ← 주 작업 폴더
    │  ── 메인 파이프라인 (9) ──
    ├── config.py                 ← 모든 설정 (dataclass)
    ├── preprocessing.py          ← MIDI→화음/note 레이블링
    ├── weights.py                ← 가중치/거리 행렬
    ├── overlap.py                ← 사이클 관리 + 중첩행렬
    ├── generation.py             ← Algorithm 1 & 2 (FC/LSTM/Transformer)
    ├── musical_metrics.py        ← Tonnetz/voice_leading/DFT 거리 함수
    ├── eval_metrics.py           ← JS divergence, coverage 평가
    ├── pipeline.py               ← 전체 흐름 조율 + 캐싱
    ├── topology.py               ← generateBarcode numpy wrapper
    │
    │  ── 진입점 + core 도메인 ──
    ├── run_any_track.py          ← 임의 MIDI에 파이프라인 적용 (일반화)
    ├── run_aqua.py               ← aqua 전용 실험
    ├── run_solari.py             ← solari 전용 실험
    ├── run_test.py               ← hibari smoke test (pkl 기반)
    ├── note_reassign.py          ← 방향 A 재분배 core
    ├── temporal_reorder.py       ← 방향 B 재배치 core
    ├── sequence_metrics.py       ← DTW / pitch JS 평가
    ├── cycle_selector.py         ← cycle 선택 유틸
    ├── precompute_metrics.py     ← 사전계산 스크립트
    ├── professor.py              ← 교수님 원본 (수정 금지)
    │
    │  ── 재편된 서브폴더 (2026-04-19 7876d62) ──
    ├── experiments/              ← run_*.py × 49 (path_bootstrap 포함)
    ├── tests/                    ← test_*.py × 4
    ├── tools/                    ← gen_* / visualize* / wav_renderer
    ├── debug/                    ← diagnose* / benchmark / dashboard*
    ├── archive/                  ← unused (adaptive_search / module_generation / duration_restore)
    ├── utils/                    ← result_meta.py 등
    ├── listening_test/           ← 청취 실험 stimuli + 웹 플레이어
    ├── hibari_dashboard/         ← 분석 대시보드
    ├── scripts/                  ← 빌드/배포 스크립트
    │
    ├── docs/
    │   ├── academic_paper_full.md         ← 학술 원고 통합본
    │   ├── 환대_포트폴리오.md             ← 포트폴리오용 축약 (공개 1순위)
    │   ├── academic_paper_general.md      ← 비전공자용 요약
    │   ├── build_academic_pdf.py          ← md→PDF 변환
    │   ├── latex/                         ← IEEE 영문/한글본/report
    │   ├── figures/                       ← Figure PNG + 생성 스크립트
    │   └── step3_data/                    ← 실험 결과 JSON
    │
    ├── memory/                   ← 세션 간 메모 (gitignored는 아님)
    ├── cache/                    ← metric별 PH 결과 캐시 (pkl)
    ├── output/                   ← 생성된 MusicXML/MIDI/WAV (gitignored)
    └── *.mid                     ← 원곡 MIDI 파일들 (gitignored)
```

**실행 규칙 (2026-04-19 이후):**
- `experiments/`, `tests/` 내 스크립트는 첫 줄에 `path_bootstrap` 블록이 있어 **루트에서 `python experiments/run_xxx.py` 형태로 실행**하거나 **스크립트 경로 직접 호출** 모두 가능
- `tools/wav_renderer.py`를 참조하는 `listening_test/*.py`는 sys.path에 루트 + tools + experiments 3경로를 주입
- 루트에서 직접 실행하던 `run_improvement_F`, `run_module_generation*`, `run_step3_*` 등은 `experiments/` 아래로 이동됨

## 코드 컨벤션 및 주의사항

### 데이터 흐름의 핵심 변수들

| 변수 | 형태 | 설명 |
|------|------|------|
| `notes_label` | `{(pitch, dur): int}` | note → 1-indexed 정수 레이블 |
| `notes_dict` | `{chord_idx: [note_labels]}` | 화음 → 구성 note 매핑. `notes_dict['name'] = 'notes'` 필수 |
| `adn_i` | `{1: [lag0_seq, lag1_seq, ...], 2: [...]}` | 악기별 lag 시퀀스 (list of lists) |
| `cycle_labeled` | `{label: (note_indices)}` | 각 cycle의 구성 note 인덱스 (tuple) |
| `overlap_matrix` | DataFrame (T × C) | 이진 또는 연속값 중첩행렬 |

### 수정 시 절대 지켜야 할 것

1. **기존 코드와의 중간결과 일치 확인**: 어떤 함수든 수정 후 반드시 `diagnose.py`로 기존 코드와 비교.
2. **notes_dict 구조 유지**: `notes_dict['name'] = 'notes'`를 포함해야 하며, 정수 키가 chord 인덱스, 값이 note 레이블 리스트.
3. **1-indexed vs 0-indexed 주의**: `notes_label`은 1-indexed, numpy 배열 접근은 0-indexed.
4. **professor.py는 직접 수정하지 않기**: 교수님 코드이므로, 개선 시 별도 모듈(`topology.py` 등)에 래핑.
5. **다른 곡 적용 시**: `run_any_track.py` 패턴 사용. 통합 chord map + pitch-only labeling 필수. `num_chords` 동적 산출.

### 논문–코드 정합성 규칙 (D 세션 필수)

논문 서술이 코드 구현을 근거로 할 때 반드시 지켜야 할 규칙:

1. **코드 먼저 읽기**: "동등하다", "동일 구현", "별칭" 등의 표현을 쓰거나 수정하기 전에 반드시 해당 함수 구현을 직접 읽고 확인한다. 논문 서술만 믿지 않는다.
   - 위반 사례: `segment_shuffle`을 `block_permute(64)`의 별칭이라 서술했으나 실제로는 가변 길이 패턴 기반 전략으로 구현이 다름.

2. **정의 참조 변경 시 전파 확인**: `§2.X` 또는 `정의 2.X` 참조가 변경(이동·통합·삭제)되었을 때, 해당 번호를 참조하는 **모든 곳**을 Grep으로 찾아 일괄 수정한다.
   - 위반 사례: markov_resample 정의가 §2.10으로 통합됐으나 §7.4에서 구 참조 `정의 2.14`가 잔존.

3. **수치·파라미터는 JSON 원본 대조**: 논문 표의 수치를 수정하거나 설명할 때 `docs/step3_data/` JSON 파일을 직접 읽어 확인한다. 기억에만 의존하지 않는다.

### 테스트 방법

```bash
# 임의 곡에 파이프라인 적용
python run_any_track.py <midi_file>
python run_any_track.py --all

# hibari 전체 파이프라인 (pkl 기반, 빠름)
python run_test.py

# 논문 PDF 빌드 (Markdown)
cd docs && python build_academic_pdf.py academic_paper_full.md
cd docs && python build_academic_pdf.py 환대_포트폴리오.md
```

### LaTeX 빌드 레시피

```bash
cd docs/latex

# 영문 IEEE — xelatex/pdflatex 모두 가능
xelatex hibari_tda.tex

# 한글본 — XeLaTeX 전용 (fontspec이 Xe/Lua 엔진 요구)
xelatex hibari_tda_ko.tex

# 보고서 — XeLaTeX 전용 (동일 사유)
xelatex hibari_tda_report.tex
```

**중요:**
- `hibari_tda_ko.tex` / `hibari_tda_report.tex`는 **pdflatex로 컴파일 불가** (fontspec 한글 폰트 때문). 반드시 `xelatex`.
- **PDF 커밋 관례**: `hibari_tda.pdf` / `hibari_tda_ko.pdf` / `hibari_tda_report.pdf` **3파일 모두 tracked** (2026-04-19 bcd35ed 이후). 논문 수정 시 3파일 PDF 동시 재빌드 후 커밋.
- 컴파일 성공 검증 3항: 에러 0 / undefined ref 0 / citation 0.

## 세션 운용 가이드

토큰 절약을 위해 세션을 역할별로 분리. 세션 시작 시 "X 세션이야"라고 선언.

| 세션 | 역할 | 읽는 것 | 안 읽는 것 |
|------|------|---------|-----------|
| **A. 실험** | run_*.py 실행, 결과 해석 | config, pipeline, 실험 스크립트 | docs/, LaTeX |
| **B. 디버그** | 코드 수정, diagnose.py | 소스코드 전체 | docs/, 결과 해석 |
| **C. 감상** | WAV 청취 평가, 방향 논의 | output/, 생성 결과 요약 | 소스코드 내부 |
| **D. 보고서** | md/LaTeX, 도표, 수치 | docs/, step3_data/ | 소스코드 내부 |
| **E. Control Tower** | 전체 추적, 우선순위, 커밋 | memory/, CLAUDE.md, git log | 소스코드·논문 내부 |

**세션 간 인터페이스 = 파일**: A→json→D, A→wav→C, B→코드수정→A, C→방향→memory→A/B

### E. Control Tower 역할

A~D 세션의 상위 조율자. 어떤 세션에도 속하지 않으며, 세션 간 정보 흐름을 추적한다.

**주요 책임:**
1. **작업 추적** — 오늘/최근 세션에서 수행된 실험·코드수정·논문작업을 종합 파악
2. **우선순위 조정** — A~D 세션별 다음 작업을 중요도·의존성 기준으로 정렬
3. **커밋 관리** — 미커밋 작업 감지, 적절한 단위로 커밋 생성
4. **memory 갱신** — 세션 결과를 memory에 기록하여 세션 간 정보 전달
5. **흐름도 유지** — `docs/research_flow_diagram.html` 업데이트
6. **피드백 추적** — `docs/260*피드백*.txt` → 미반영 항목 식별 → 세션 배정

**사용 시점:** 세션 간 전환이 잦거나, 전체 진행 현황을 파악할 때. "control tower야"로 선언.

**읽는 것:** memory/, CLAUDE.md, git log/status, 피드백 txt, step3_data/ JSON (수치만)
**안 읽는 것:** 소스코드 내부, 논문 본문 (구조만 파악)

**실험/코드 세션 직후 정기 루틴 (A/B 세션 종료 → E 자동 호출 권장):**
1. memory/에 결과 메모 추가 (신규 파일 + `MEMORY.md` 인덱스 1줄)
2. `git status` → 이번 세션 산출물 파일만 골라 커밋 (무관 변경과 섞지 않기)
3. CLAUDE.md "다음 우선 작업" 표에 후속 작업 반영
4. 주의: "현재 최적 설정" 블록은 **세션 D가 논문에 반영한 뒤**에만 수정

### Skills (자동 로드)
- `/run-experiment` — MIDI 파이프라인 실행 (세션 A)
- `/compare` — 실험 결과 JSON 2개 비교 + t-test 유의성 (세션 A)
- `/piano-wav` — MusicXML/MIDI → Piano WAV 변환 (세션 C)
- `/explain-research` — 비전공자용 연구 설명 (세션 D)
- `/update-paper` — JSON 최신 수치 → 논문 표 자동 반영 (세션 D)
- `/research-next` — 선행연구 + 다음 방향 제안 (세션 A/D)

## 다음 우선 작업 (2026-04-20 기준)

**완료 Task 아카이브**: #1~#56 전체는 `memory/project_task_archive_0420.md` 로 이관 (Phase 1/1b/2/3/3-후속/4 전부 포함). 이 섹션은 현재 진행·대기 중인 작업만 유지.

### 논문 · 실험 펜딩 (세션 A/B/C/D)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 46 | **C** | 청취 실험 파일럿 실행 | 인간 주도 | N=10 비공식 가능. stimuli 길이 결정 (45초 vs 전체) — R1 30초 정책과 정합 필요 |
| 47 | **A** | 응답 데이터 분석 | Task 46 완료 후 | analysis_template.py — Spearman / Mann-Whitney / Wilcoxon |
| 48 | **D** | §8 또는 §9 청취 실험 결과 반영 | Task 47 완료 후 | 수치-청각 정합성, 위상 보존 변주 평가 |
| 52 | **A** | §6 블록 단위 생성 α=0.25 per-cycle τ 재탐색 | Task 56 완료 (착수 가능) | 블록 best 0.01479를 α=0.25로 초과 가능? 긴 작업. Task 51 결과상 negative 가능성 있음. Option B 창 baseline 재산정 완료 |
| 57 | **D** | LaTeX 3파일 260419 sweep + Task 61 블록 rename 동기화 | 2aac918 + Task 61 완료 | md 반영분 (Algo1 0.00902, α-grid, tie 정규화, Bach/Ravel 등) + §6 "마디→블록" → hibari_tda.tex / ko.tex / report.tex. 컴파일 에러 0 검증 |
| 60 | **D** | 논문 QR 코드 첨부 | 없음 | 코드 저장소 링크 QR 이미지 삽입 |

### 공개 · 상호작용 트랙 (2026-04-20 신설, R1~R7)

best-practice 도입 커밋 시리즈(316e125 / 9c781ff / 1ca08d4) 이후 병렬 진행.

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| R1 | 별도 | OM 대시보드 post-bugfix 업데이트 (30초 세그먼트 한정) | 진행 중 | **30초 제약** — `memory/feedback_dashboard_30sec_constraint.md` 참조. T=60 step, m=0..17 블록 선택 UI. `hibari_dashboard/` 건드리지 말 것 (타 세션 작업) |
| R2 | 별도 | 코드 위계 시각화 (사용자 병목 완화) | 진행 중 | `/map` + code-map skill 활용. depth 3, 최근 30일 수정 배지 |
| R3 | 별도 | UI 폴리싱 (데스크톱) | 진행 중 | claude design 미숙 — best-practice 컴포넌트 참조. `hibari_dashboard/` 건드리지 말 것 |
| R4 | — | 모바일 responsive 포팅 | R1 완료 후 | 320~768px 뷰포트, 터치 44×44px, WebWorker ONNX. 30초 기준 |
| **R5-a** | **E** | **Tilt Sphere (기울기 → 구 굴림 → 음악)** | **내일 기한** | DeviceOrientation(iOS 권한 플로우), 30초 세그먼트, tonnetz 격자 위 구. 신규 폴더 `tda_pipeline/mobile_tonnetz/` 권장 |
| **R5-c** | **E** | **Shake (흔들림 피크 → Algo1 re-seed)** | **내일 기한** | DeviceMotion 피크 감지, 30초 생성 |
| **R5-f** | **E** | **Camera Color (비디오 색조 → 스케일 매핑)** | **내일 기한** | video + canvas hue 추출 → scale_major / minor 매핑 |
| R5-g | stretch | Multi-phone jam (WebRTC signaling) | R5-a/c/f 중 2개 | 시간 부족 시 차기 |
| R6 | Codex 병렬 | OBS 녹화 → YouTube 업로드 스크립트·메타데이터 | 없음 | Codex에 위임: `docs/youtube_script.md` + `docs/youtube_description.md` + 썸네일 브리프 |
| R7 | Codex 병렬 | SKMT 재단 연락 — 3-language portfolio 1p + 이메일 | 없음 | Codex에 위임: `docs/outreach/skmt_portfolio_1p.md` + ko/ja/en 이메일 3개 |

### Codex 병렬 위임 후보 (사용자가 발송)

1. **R6 YouTube 스크립트** 8~12분 한국어 내레이션 → `docs/youtube_script.md`
2. **R6 YouTube 메타데이터** 제목·설명·태그·챕터 → `docs/youtube_description.md` + `docs/youtube_thumbnail_brief.md`
3. **R7 SKMT 3-language 세트** — portfolio 1p (ko/ja/en) + 이메일 (ko/ja/en) → `docs/outreach/` 하위
4. **R5-a Tilt Sphere 기술 스펙** — DeviceOrientation 권한 플로우, tonnetz 격자 좌표, 물리 시뮬 파라미터 → `docs/mobile_r5a_spec.md`

## 기술 환경

- Windows, Python 3.10, VS Code
- 주요 패키지: `pretty_midi`, `numpy`, `pandas`, `music21`, `matplotlib`, `torch`
- 작업 디렉토리: `C:\WK14\tda_pipeline\`
- 사용 언어: 한국어 (코드 주석, 문서, 대화 모두)
