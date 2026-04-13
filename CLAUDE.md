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

## 현재 상태 (2026-04-13 기준)

### 완료된 주요 실험

| 실험 | 핵심 결과 |
|---|---|
| §3.1 거리 함수 비교 (N=20) | Tonnetz가 frequency 대비 JS -47% (hibari) |
| §3.3a Continuous overlap (N=20) | τ=0.5 이진화가 추가 -11% |
| §3.4a 개선 F (N=5) | Continuous + FC → JS 0.0004 ★ 본 연구 최저 |
| §3.6 곡 고유 구조 | deep scale, entropy 0.974, phase shifting |
| §7.1 모듈 단위 생성 | P4+C best JS 0.0258, 첫 모듈 정당성 |
| §7.2 aqua/solari/Bach/Ravel 일반화 | 곡 성격이 최적 도구 결정 |
| §7.7 Continuous 정교화 3종 | per-cycle τ +48.6%, soft Algo2 +64.3% |
| §7.8 α grid search (N=20) | α=0.0(순수 Tonnetz) 최적 |
| octave_weight 튜닝 (N=10) | ow=0.3 최적, JS -18.8% |
| 감쇄 lag 가중치 (lag 1~4) | hibari Tonnetz JS -70% |
| 방향 A: note 재분배 | Tonnetz 매칭, DTW +61.4% |
| 방향 B: 시간 재배치 | pitch↔선율 딜레마, 단독 한계 |
| Barcode Wasserstein 모듈 선택 | Pearson(W,JS)=0.503 |
| Wasserstein 제약 note 재분배 | 계수 무관, 효과 제한적 |

### 핵심 발견 — 곡의 성격이 최적 도구를 결정한다

| 곡 | PC 수 | 최적 거리 | 최적 모델 | 해석 |
|---|---|---|---|---|
| hibari | 7 (diatonic) | Tonnetz | FC | 공간적 배치, entropy 0.974 |
| solari | 12 (chromatic) | voice_leading | Transformer | 선율적 진행 |
| aqua | 12 (chromatic) | Tonnetz | (미실행) | Tonnetz +26.3% |
| Bach Fugue | 12 (chromatic) | Tonnetz | — | 대위법인데 Tonnetz 최적 (-54.8%) |
| Ravel Pavane | 12 (N=49) | frequency | FC | 풍부한 분포 → 빈도 가중 유리 |

### hibari 현재 최적 설정

```
거리 함수: Tonnetz (α=0.0, octave_weight=0.3)
Lag: 감쇄 가중 (lag 1~4, w=[0.4, 0.3, 0.2, 0.1])
중첩행렬: continuous activation + per-cycle τ_c 이진화
생성 모델: FC (soft activation 입력)
온도: T=3.0 (빈도 스케일링)
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
    ├── run_any_track.py          ← 임의 MIDI에 파이프라인 적용 (일반화)
    ├── run_aqua.py               ← aqua 전용 실험
    ├── run_solari.py             ← solari 전용 실험 (Algo1 + Algo2)
    ├── run_improvement_F.py      ← 개선 F (continuous + DL)
    ├── run_module_generation.py  ← §7.1 모듈 단위 생성 (P1)
    ├── run_module_generation_v3.py ← §7.1 개선 C/D/P4
    ├── run_module_generation_v4.py ← §7.1 시작 모듈 정당성 검증
    ├── run_step3_experiments.py   ← §3.1 통계 실험 (N=20)
    ├── run_step3_continuous.py    ← §3.3a continuous overlap
    │
    ├── docs/
    │   ├── academic_paper_full.md  ← 학술 원고 통합본 (1630 lines)
    │   ├── academic_paper_general.md ← 비전공자용 요약 (15페이지)
    │   ├── academic_paper_step1~4.md ← 섹션별 개별 빌드
    │   ├── academic_paper_step71.md  ← §7.1 구현 보고
    │   ├── build_academic_pdf.py     ← md→PDF 변환
    │   ├── build_full_paper.py       ← 전체 합치기
    │   ├── latex/hibari_tda.tex      ← IEEE LaTeX 원고
    │   ├── figures/                  ← Figure 1-8 PNG + 생성 스크립트
    │   └── step3_data/               ← 실험 결과 JSON
    │
    ├── cache/                    ← metric별 PH 결과 캐시 (pkl)
    ├── output/                   ← 생성된 MusicXML/MIDI/WAV (gitignored)
    └── *.mid                     ← 원곡 MIDI 파일들 (gitignored)
```

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

### 테스트 방법

```bash
# 임의 곡에 파이프라인 적용
python run_any_track.py <midi_file>
python run_any_track.py --all

# hibari 전체 파이프라인 (pkl 기반, 빠름)
python run_test.py

# 논문 PDF 빌드
cd docs && python build_academic_pdf.py academic_paper_full.md
```

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

### Skills (자동 로드)
- `/run-experiment` — MIDI 파이프라인 실행 (세션 A)
- `/compare` — 실험 결과 JSON 2개 비교 + t-test 유의성 (세션 A)
- `/piano-wav` — MusicXML/MIDI → Piano WAV 변환 (세션 C)
- `/explain-research` — 비전공자용 연구 설명 (세션 D)
- `/update-paper` — JSON 최신 수치 → 논문 표 자동 반영 (세션 D)
- `/research-next` — 선행연구 + 다음 방향 제안 (세션 A/D)

## 다음 우선 작업 (2026-04-13 기준)

### 높은 우선순위 (연구 결과에 직접 영향)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 1 | **A** | `ow=0.3 + α=0.0 + 감쇄lag` 통합 조합 실험 (N=20) | 없음 | 3개 독립 개선이 시너지 내는지 검증 — 현재 최고 우선 |
| 2 | **A** | Per-cycle τ_c N=20 재검증 | 없음 | 현재 N=5 greedy, +48.6%를 통계적으로 확인 |
| 3 | **A** | Soft activation → Transformer/LSTM 확장 | 없음 | FC에서 +64.3% 확인, 다른 아키텍처에서도? |
| 4 | **D** | 피드백(1) 반영: §1~§4 수식 크기, 정의 보완, Tonnetz 범위 한정 | B-①②③ | 사실관계 확인 완료 후 수정 |
| 5 | **D** | 피드백(2) 반영: §7 전체 지적사항 18건 | B-①②③ | §7.1 목적 정정, §7.3 정의 추가 등 |

### 중간 우선순위 (결과 보강)

| # | 세션 | 작업 | 의존성 | 비고 |
|---|------|------|--------|------|
| 6 | **D** | §2.9 감쇄 lag 가중치 수식·결과 반영 | 없음 | memory에 기록만 됨, 논문 미반영 |
| 7 | **D** | §7.2 일반화 테이블 확장 (Bach/Ravel 추가) | 없음 | JSON 있음 |
| 8 | **D** | §7.7/§7.8 실험 결과 논문 반영 | 없음 | JSON 있음, per-cycle τ/soft/온도/α |
| 9 | **D** | §7.1.9 Barcode Wasserstein 주의사항 4개 | 없음 | memory에 기록 완료 |
| 10 | **B** | density 수치 통일 (0.1684/0.160/0.201 혼용) | 없음 | 코드 확인 → 정확한 값 확정 |
| 11 | **B** | §2.11 N! vs Hungarian 근사 — 논문 주석 추가 필요 여부 | 없음 | hibari는 항상 근사 경로 |
| 12 | **B** | P3 수식 구현 확인 (v3 미구현 가능성) | 없음 | step71_improvements.json에 P3 없음 |

### 낮은 우선순위 (향후 과제)

| # | 세션 | 작업 | 비고 |
|---|------|------|------|
| 13 | **C** | 방향 A vwide WAV 청각 평가 | 아직 미실시 |
| 14 | **C** | 최적 설정(ow=0.3, α=0.0) WAV 생성 + 감상 | A-① 이후 |
| 15 | **A** | 나머지 곡 실험 (`run_any_track.py --all`) | 파라미터 확정 이후 |
| 16 | **B** | Wasserstein 제약 재설계 (topk 이전 적용) | 현재 구현 효과 없음 |
| 17 | **D** | LaTeX 원고 최종 업데이트 | 모든 반영 완료 후 |

## 기술 환경

- Windows, Python 3.10, VS Code
- 주요 패키지: `pretty_midi`, `numpy`, `pandas`, `music21`, `matplotlib`, `torch`
- 작업 디렉토리: `C:\WK14\tda_pipeline\`
- 사용 언어: 한국어 (코드 주석, 문서, 대화 모두)
