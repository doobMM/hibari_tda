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
    │   ├── academic_paper_portfolio (short).md ← 포트폴리오용 축약
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
cd docs && python build_academic_pdf.py "academic_paper_portfolio (short).md"
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

## 다음 우선 작업 (2026-04-17 기준)

### 높은 우선순위 (연구 결과에 직접 영향)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 1 | **A+D** | 방향 A vwide 재검증 + §7.3 논문 반영 ✓ | 완료 | vwide 열세 확정. wide+tonnetz_nearest+no_cycle (pitch_js=0.2930). §7.3 2×2 ablation 표 반영. DTW+61.4% 제거. |
| 2 | **A** | `ow=0.3 + α=0.0 + 감쇄lag` 통합 조합 실험 ✓ | 완료 | α=0.0 시 K 감소로 시너지 없음 확정 (2026-04-14) |
| 3 | **A** | Per-cycle τ_c N=20 재검증 ✓ | 없음 | +47.5% p<0.001 확정 (2026-04-14 완료) |
| 4 | **A** | Soft activation → Transformer/LSTM 확장 ✓ | 없음 | FC=0.0004★, Transformer=0.0007 확인 (2026-04-14 완료) |
| 5 | **D** | 피드백 19항 전체 반영 (md) ✓ | 완료 | §1~§7 정의·수식·표기 일괄 수정 (2026-04-15). 13/19 반영, 6개는 기완료 또는 미해당 |
| 6 | **B+A** | `note_perm` Hungarian 진단 + 수정 + 재검증 ✓ | 완료 | 원인: tonnetz_nearest의 positional semantics를 후속 perm이 덮어씀. 수정: tonnetz_nearest 분기 perm skip. 재실험 결과: tonnetz_nearest 0.3843→**0.2930** 복원 성공. ascending 0.3815 유지. |

### 중간 우선순위 (결과 보강)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 7 | **D** | §4.1c 감쇄 lag 표 post-bugfix 재작성 ✓ | 완료 | DFT 중심으로 교체. Tonnetz −69.6%→+4.8%, DFT −7.1% ★. 초록·§2.9도 수정 (2026-04-17) |
| 8 | **D** | §7.2 일반화 표 aqua/Bach 추가 ✓ | 완료 | 피드백 #18로 반영 (2026-04-15) |
| 9 | **D** | §7.1.9 Barcode Wasserstein 주의사항 ✓ | 완료 | 피드백 #19로 반영 (2026-04-15) |
| 10 | **D** | §7.7/§7.8 실험 결과 논문 반영 ✓ | 완료 | 이전 세션에 이미 완료됨을 JSON 전수 대조로 확인 (2026-04-15). per-cycle τ/soft/온도/α 모두 일치 |
| 11 | **B** | density 수치 통일 ✓ | 완료 | 0.1684(전체 overlap) / 0.160(P1 prototype, 첫 모듈) 정상 구분. 0.201은 이미 정정됨. 수정 불필요 (2026-04-15) |
| 12 | **B+D** | §7.3 ascending Hungarian 근사 경로 주석 ✓ | 완료 | §2.11과 무관, §7.3 line 1221에 N=17 / N!=3.56×10¹⁴ 1문장 삽입 (2026-04-15) |
| 13 | **B+D** | P3 수식 구현 확인 + 파일명 수정 ✓ | 완료 | P3는 unified.py에 구현·결과 기재 정상. run_module_generation_v2/v3 언급 4곳 → unified로 교체 (2026-04-15) |
| 14 | **D** | §7.3 두 전략 비교 서술로 재구성 ✓ | 완료 | 2×2 → 1×2 교체. 전략 A(tonnetz_nearest)/B(ascending) 수식 추가. 피드백 #16 박스 재작성. 잔류 참조 스캔 clean. (2026-04-15) |
| 20 | **B+D** | line 1787 `run_module_generation_v4.py` 참조 교체 ✓ | 완료 | v4 기능은 unified.py `--mode startmodule_study`로 완전 통합됨 확인 후 교체 (2026-04-15) |

### 새 실험 우선 작업 (2026-04-15 추가)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 21 | **A** | Complex PH + per-cycle τ + Algo2(FC) 통합 파이프라인 실험 ✓ | 완료 | **Algo1: 0.0182★ (−24.5%)**, **Algo2: 0.0003★ (−25.0%)** (complex α=0.25 ow=0.0 rc=0.1 + greedy τ). 실험C(α=0.5,ow=0.3) N=5: 0.0172 (추가 검증 필요). complex_percycle_results.json (2026-04-15) |
| 22 | **D** | §6.8 α=0.0 표기 보완 ✓ | 완료 | α grid=생성 단계만 적용, PH 캐시=α=0.5 고정, K=3 붕괴 사실 명기. short.md 삽입 (2026-04-17) |
| 23 | **B** | pipeline.py ow/dw 버그 수정 커밋 | 완료(코드 수정됨) | config.py duration_weight 추가 + _apply_metric ow/dw 전달 수정 — 미커밋 상태 |
| 24 | **A** | 실험 C/D/E N=20 재검증 + 절대 최저 확정 ✓ | 완료 | **B(α=0.25,ow=0.0,rc=0.1) JS=0.0183±0.0009 N=20 ★확정**. D(α=0.5)=0.0218, E(rc=0.3)=0.0214. B vs D/E 모두 p<0.001 유의. Algo2 D=0.0005(B=0.0003 유지). complex_percycle_n20_results.json (2026-04-15) |
| 25 | **D** | §6.9 신설 — complex+per-cycle τ 통합 실험 결과 논문 반영 ✓ | 완료 | §6.9 in full.md. Algo1: 0.0183±0.0009 N=20 (−24.1% vs timeflow). Algo2: 0.0003. B vs D p<0.001 (2026-04-15) |

### DFT baseline 재실험 과제 (2026-04-17 추가)

§4.1b Duration Weight 튜닝이 Tonnetz 조건으로 수행됨. §4.1에서 DFT가 hibari 최적이므로 이후 실험들의 baseline을 DFT로 통일해야 함. 영향 범위:

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 26 | **A** | §4.1b w_d grid search — DFT 조건으로 재실험 (N=10) ✓ | 완료 | **w_d=1.0 최적** (JS=0.0199). Tonnetz 최적(0.3)과 다름. dw_gridsearch_dft_results.json (2026-04-17) |
| 27 | **A** | §4.1a w_o grid search — DFT 조건으로 재실험 (N=10) ✓ | 완료 | **w_o=0.3 유지** (JS=0.0184). ow_gridsearch_dft_results.json (2026-04-17) |
| 28 | **A** | §4.2 Continuous OM 실험 — DFT 조건으로 재실험 (N=20) ✓ | 완료 | **Binary 최적** (JS=0.0185). Continuous는 열세. step3_continuous_dft_gap3_results.json (2026-04-17) |
| 29 | **A** | §4.3 DL 모델 비교 — DFT 기반 OM으로 재실험 ✓ | 완료 | **Transformer=0.00276★**, FC=0.00354, LSTM=0.240(열화). dl_comparison_dft_gap3_results.json (2026-04-17) |
| 30 | **A** | §4.3a FC-cont — DFT 기반으로 재실험 ✓ | 완료 | **FC-cont 이점 없음** (0.00383 vs 0.00363). fc_cont_dft_gap3_results.json (2026-04-17) |
| 31 | **D** | 재실험 결과 논문 §4.1a~§4.3a 표 갱신 ✓ | 완료 | Task 25 포함 전체 재서술. short.md 전면 업데이트 (2026-04-17). ⚠ gap_min=0 롤백 결정으로 Task 35에서 gap0+DFT 수치로 재서술 예정 |

### gap_min=0 롤백 + §6~§7 DFT-hybrid 통합 과제 (2026-04-17 추가)

gap_min=3 청취 평가 폐기 결정에 따른 §4 gap=0 롤백 + bugfix 이후 DFT baseline을 §6~§7까지 통합하는 과제. 배경 · Phase 1 결과는 `memory/project_gap0_dft_integration_0417.md` · `memory/project_phase1_gap0_findings_0417.md` 참조.

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 32 | **A** | gap_min=0 롤백 Phase 1 (§4 DFT 재실험 Task A1~A7) ✓ | 완료 | 커밋 bb4ab4d. DFT 0.0213★, w_d=1.0 / w_o=0.3 확정. **A6: FC≈Transformer (가설 수정)**, **A7: FC_cont 0.00032 잠정 최저** |
| 33 | **B** | min_onset_gap 필드화 + run_dft_suite 파라미터화 + 메타표준 ✓ | 완료 | 커밋 71d2f2b. config.min_onset_gap, rename(R061), utils/result_meta, scripts 2개 |
| 34 | **A** | Phase 2 (Task A8~A10) — DFT-hybrid 재탐색 ✓ | 완료 | 커밋 459eb24. **A8: DFT+per-cycle τ 0.0149★ Algo1 신기록** (p=2.48e-26), A9: FC-cont 유의 우위 p=1.66e-4, A10-a α=0.25 최적, A10-b pilot(α=0.5) 열세 → Task 34b로 α=0.25 재실험 |
| 34b | **A** | A10-b α=0.25 재실험 (Phase 2 후속) ✓ | 완료 | 커밋 d83efc5. α=0.25, r_c ∈ {0.1, 0.3} 모두 A8 대비 p<1e-39로 유의 악화. **complex_tonnetz_only_effective 판정 확정** — DFT에서는 timeflow + per-cycle τ (A8 0.0149★) 선호. Algo2도 A9 0.00035 최저 유지 |
| 35 | **D** | §4 gap0+DFT 재서술 ✓ | 완료 | 커밋 9873cdd (+ 8c4e3ae 연쇄 일관성). §4.1 38.2%/56.8%/62.4%, §4.2 Binary 0.0157, §4.3a FC-cont 0.00035 +83.9% p=1.50e-6. §3.2 gap_min=3 선언 제거. §4.1a/b "Tonnetz 조건 최적값" 언급 삭제. §3.x→§4.x 교차참조 일치 |
| 36 | **D** | §6.7~§6.9 재서술 ✓ | 완료 | 커밋 8c4e3ae. §6.7.1 DFT per-cycle τ +58.7% (p=2.48e-26, JS=0.01489★), §6.7.2 FC-cont 0.000348★ (Transformer 대비 p=1.66e-4), §6.8 DFT hybrid α=0.25, §6.9 "Tonnetz 한정 유효" 서사 반전 + Task 34b 검증절 신설 |
| 37 | **D** | §7 baseline 재설정 + §8 결론·초록 통일 ✓ | 완료 | §7 baseline Tonnetz 0.0488 → DFT 0.0213±0.0021 교체. §8 결론 수치 통일 (38.2%/56.8%/62.4%, per-cycle τ +58.7%, FC-cont +83.9%). 초록 Algo1 0.01489±0.00143★, Algo2 0.00035±0.00015★ (log2 대비 2.15% / 0.05%). CLAUDE.md 현재 최적 설정 블록 갱신 완료. **gap0+DFT 통합 재서술 프로젝트 종결** |

### Phase 3 — §7 DFT 재수행 + Wave 2 보강 (2026-04-17 추가)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 38a | **A** | §7 DFT α=0.25 전면 재수행 ✓ | 완료 | 커밋 dafdff3. **K=42→14**, P3 best 유지, P3+C best 0.0250. **§7.7 first-module 우위 미재현 (rank=5)**, **§7.8 Pearson 0.503→-0.054 — 반전**. best global JS=0.01479 (§6.7.1 0.01489와 동등 ★). `memory/project_task38a_phase3_findings_0417.md` |
| 38b | **D** | §7 전면 재서술 ✓ | 완료 | 커밋 c548371. 수식 32×42→32×14, §7.2 P0~P3 DFT 전략 교체, §7.5 P3+C best 0.0250, §7.6 **best global JS=0.01479 ≈ full-song**, §7.7 first-module rank=5 (Tonnetz-specific), §7.8 Pearson 0.503→-0.054. `memory/project_task38b_section7_rewrite_0417.md` |
| 39 | **A** | Wave 2 누락 실험 (T39-2/3/4/5) ✓ | 완료 (N=5 반복 재검증 과제) | 커밋 5fb01b2. hibari만 DFT 최적, 타곡(solari/Bach/Ravel) 기존 거리 유지 확정 |
| 40 | **A** | §6.3~§6.6 DFT 전환 재실험 (Transformer + FC) ✓ | 완료 | 커밋 a67977d. §6.4 딜레마 재현 ✓, §6.5 scale_major 최적 유지 ✓. **§6.6 Tonnetz가 DFT 대비 ref pJS 27배 우수** — 메타 통찰 "거리 함수는 목적에 따라 최적 다름". 세션 D Task 41에서 (A/B/C) 선택. `memory/project_task40_section66_findings_0417.md` |
| 41 | **D** | §6.1~§6.6 재서술 + §8 메타 통찰 ✓ | 완료 | 커밋 b2f9b51. (C) 채택 — §6.1/§6.2 DFT 열 추가, §6.3 "Tonnetz 기반" 선언, §6.4 세 모델 실증, §6.5 FC/LSTM 확장, §6.6 3분할 (Tonnetz 성공 / DFT 실패 / 메타 통찰), §8 6항 "거리 함수 × 음악적 목적". **Phase 3 종결** |
| 42 | **A** | T39-4/5 N=5 std 재검증 ✓ | 완료 | 커밋 901eab0. 사전검사 전원 n=1 → N=5 전체 재실행. LSTM dtwverify 1.09% 재현 (Task 39-4 결과 일관). **FC 재배치에서 DTW +30~48% 발견** → §6.4 FC 서술 "구조적 불가능" 과장 수정 필요 (Task 44 신설). scale_major 최적 유지 |
| 43-A | **D** | LaTeX 영문 IEEE + report 동기화 ✓ | 완료 | 커밋 fe85f53. hibari_tda.tex + hibari_tda_report.tex + hibari_tda.pdf — Phase 3 최신 반영. Task 44 중 선행 처리됨 |
| 43-B | **D** | LaTeX 한글본 동기화 + 3파일 컴파일 검증 ✓ | 완료 | 커밋 d8f3f00. hibari_tda_ko.tex Phase 3 반영. 3파일 모두 컴파일 에러 0, undefined ref 0, citation 0. **전체 프로젝트 종결** |
| 45 | **C** | 체계적 청취 실험 설계 + 인프라 ✓ (부분) | 완료 (D/E/F WAV 누락) | 커밋 36a879b. 8 stimuli 중 5개(A/B/C/G/H) 생성, 3개(D/E/F, §6.6 major_block32 변주) 누락. 웹 플레이어·프로토콜·분석 스크립트 완성 |
| 45-B | **C** | D/E/F WAV 재생성 ✓ | 완료 | 커밋 fb095e7. D seed 7401 (pJS 0.013816), E seed 7501 (pJS 0.030679), F seed 7601 (pJS 0.013049). **8/8 stimuli 완비**. `memory/project_task45_listening_test_design_0417.md` |
| 46 | **C** | 청취 실험 파일럿 실행 | Task 45-B 완료 (인간 주도) | 피험자 모집 + 응답 수집. 파일럿 N=10 비공식 가능. stimuli 길이 (45초 vs 전체) 결정 필요 |
| 47 | **A** | 응답 데이터 분석 | Task 46 완료 후 | analysis_template.py 실행 — Spearman / Mann-Whitney / Wilcoxon |
| 48 | **D** | §8 또는 §9 청취 실험 결과 반영 | Task 47 완료 후 | 수치-청각 정합성, gap=0 근거, 위상 보존 변주 청각 평가 |
| 49 | **D** | §2.4/§2.5 methodological note (metric 공리 + Heo et al. 2025) ✓ | 완료 | full.md §2.4 #### 주석(표+3단락), short.md 1단락, LaTeX 3파일 \paragraph{Remark} 삽입. Cohen-Steiner et al. (2007) 참고문헌 전 파일 추가. 컴파일 에러 0/undefined 0/citation 0. short.md PDF 재빌드 성공 |
| 50 | **D** | §6.7.1 / §6.8 / §8 / 초록 수치 전면 갱신 — α=0.25 per-cycle τ, JS=0.01156 ✓ | 완료 | 커밋 2125055 → 06c852d → **8a14d80** (2026-04-19). full.md 구조 재편(§5↔§7 스왑) + short.md + LaTeX 3파일 + PDF 2종. 초록/§5.7/§5.8.1/§6.7/§8 전부 갱신. LaTeX xelatex/pdflatex 에러 0/undef 0/cit 0 검증. `memory/project_a3_new_record_0418.md` |
| 51 | **A** | Algo2 FC-cont α=0.25 재실험 ✓ | 완료 | **α=0.25 FC-cont JS=0.00057±0.00046 (N=10) vs α=0.5 0.00035±0.00015, Welch p=0.168 비유의** — **Algo2 최저 α=0.5 유지**. K=14로 감소 영향. `run_fc_cont_dft_alpha025.py` + `fc_cont_dft_alpha025_results.json` (커밋 8a14d80). `memory/project_task51_fc_cont_alpha025_0418.md` |
| 51-b | **D** | Task 51 결과 논문 반영 (짧은 각주) ✓ | 완료 | 커밋 bcd35ed. full.md §5.8.2 Remark 2단락 + short.md 1문장 + LaTeX 3파일 \\paragraph{비고} + PDF 3종 재빌드. 컴파일 에러 0/undef 0/cit 0 |
| 52 | **A** | §6 블록 단위 생성 α=0.25 per-cycle τ 재탐색 | Task 56 완료 (착수 가능) | 블록 best global 0.01479 기록을 α=0.25로 초과 가능? 긴 작업. **주의**: Task 51에서 Algo2는 α=0.25 비유의였으므로, 블록 Algo1도 negative 가능성 있음. Option B 창 baseline 재산정 완료 (best 0.01479 @ m=0,seed=9309) |
| 53 | **E** | CLAUDE.md "현재 최적 설정" 블록 Algo1 수치 갱신 ✓ | 완료 | 8a14d80에서 D가 직접 갱신 (규칙 예외). `Algorithm 1: DFT + per-cycle τ (α=0.25, K=14) → JS=0.01156±0.00147`. Algo2는 α=0.5 유지 명시 (Task 51 정합) |
| 56 | **B+D** | §6 P3_local window 재설계 (Option B) — `[32(m+1), 32(m+2))` both instruments ✓ | 완료 | 커밋 148b16d (B 코드) + 101ffa7 (B JSON) + **6c83ddc (D 재서술)**. §6.2 P3 mean `0.0474±0.0187`, §6.5 P3+C best **`0.0167`** (seed 7300, baseline 하회), §6.7 32개 시작 블록 (best global JS=0.01479 유지, Phase1 동등 / Phase2 0.01156 미달 +28%), **§6.8 Pearson −0.054 → +0.2457 반전 ★** (설계 의도 부합 검증). 용어 "모듈→마디" rename + 비대칭 창 한계 서술 제거 + history footnote. PDF 4종 재빌드 + 3항 검증 통과. `memory/project_task56_b_execution_0419.md` + `project_task56_d_revision_checklist_0419.md` |
| 44 | **D** | §6.4 FC 서술 교체 + §6.5 ±std + §6.6.3 메타 보강 ✓ | 완료 | 커밋 19df059. §6.4 "구조적 불가능" → "pitch 분포 유지 + DTW +30~48% 실측". §6.5 ±std (FC/LSTM). §6.6.3 FC 특성 단락 추가 (DFT-FC 우수성 해석 + note 선택 논지 강화) | T39-2 solari DFT 0.0824 K=15 / T39-3 Bach 0.0951 K=30, Ravel 0.0494 K=37 (타곡 모두 기존 최적 거리 유지 — hibari만 DFT 최적). T39-4 FC 시점 독립성 실증, LSTM pitch_js 0.26~0.28. T39-5 FC/LSTM 화성 제약. ⚠ T39-4/5는 N=5 반복 재실행 검토 여지 있음 |

### 260419 피드백 후속 과제 (2026-04-19 신설)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 57 | **D** | LaTeX 3파일 260419 sweep + Task 61 블록 rename 동기화 | 260419 sweep 완료 (커밋 2aac918) + Task 61 완료 | md에 반영된 사항(Algo1 0.00902, α-grid 표, tie 정규화, §6.3~§6.4 DFT 관련, Bach/Ravel 수치 등) + §6 "마디→블록" rename → hibari_tda.tex / ko.tex / report.tex 적용. 컴파일 에러 0 검증 필수 |
| 60 | **D** | QR 코드 첨부 | 없음 | 논문 내 관련 링크(코드 저장소 등) QR 이미지 삽입. 별도 Task |

### 낮은 우선순위 (향후 과제)

| # | 세션 | 작업 | 비고 |
|---|------|------|------|
| 15 | **C** | 방향 A wide(48-84) WAV 청각 평가 | vwide 폐기, wide 기준으로 재설정 |
| 16 | **C** | 최적 설정 WAV 생성 + 감상 | complex(α=0.25,ow=0.0,rc=0.1)+per-cycle τ 확정됨 → 실행 가능 |
| 17 | **A** | 나머지 곡 실험 (`run_any_track.py --all`) | 파라미터 확정 이후 |
| 18 | **B** | Wasserstein 제약 재설계 (topk 이전 적용) | 현재 구현 효과 없음 |
| 19 | **D** | LaTeX 원고 최종 업데이트 ✓ | 완료 | hibari_tda.tex(영문 IEEE) §7.3 1×2 표 + 전략 A/B 수식 + N!=3.56e14 주석 동기화. §4.1b/§7.2/§7.1.9는 이미 반영. 컴파일 성공, undefined ref 0. ko/report 버전은 제출 계획 따라 차후 (2026-04-15) |

## 기술 환경

- Windows, Python 3.10, VS Code
- 주요 패키지: `pretty_midi`, `numpy`, `pandas`, `music21`, `matplotlib`, `torch`
- 작업 디렉토리: `C:\WK14\tda_pipeline\`
- 사용 언어: 한국어 (코드 주석, 문서, 대화 모두)
