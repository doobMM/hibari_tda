# CLAUDE.md — TDA Music Pipeline

## 프로젝트 개요

사카모토 류이치의 "hibari"를 **Topological Data Analysis(Persistent Homology)**로 분석하여, 원곡과 **위상수학적으로 유사한 구조**를 가진 음악을 생성하는 연구 파이프라인.

### 핵심 개념

- **note** = `(pitch, duration)` 쌍. 총 23개 고유 note.
- **chord** = 한 시점에서 동시에 활성화된 note들의 집합. 총 17개 고유 chord.
- **rate** 파라미터: `timeflow_weight = intra_weights + rate × inter_weight`. rate를 0→1.5로 변화시키며 위상 구조(cycle/void)의 출현/소멸을 추적.
- **중첩행렬(Overlap Matrix)**: 발견된 cycle들이 각 시점에서 활성화되는지를 나타내는 이진 행렬 (T × C). 이것이 음악 생성의 seed.

### 4단계 파이프라인

```
1. 전처리 (preprocessing.py)
   MIDI → 8분음표 양자화 → 두 악기 분리 → 화음/note 레이블링
   
2. Persistent Homology 탐색 (weights.py + professor.py)
   가중치 행렬 → refine → 거리 행렬 → generateBarcode(Vietoris-Rips)
   
3. 중첩행렬 구축 (overlap.py)
   cycle별 활성화 판단 → scale 조정 → 이진 중첩행렬
   
4. 음악 생성 (generation.py)
   Algorithm 1: 확률적 샘플링 (현재 작동)
   Algorithm 2: 신경망 (데이터 정합성 이슈 있음)
```

## 폴더 구조

```
C:\WK14\                          ← 프로젝트 루트
├── process.py                    ← 기존 코드 (diagnose.py 비교 대상)
├── util.py                       ← 기존 코드
├── professor.py                  ← 교수님 코드 (generateBarcode 등)
├── Ryuichi_Sakamoto_-_hibari.mid
├── pickle/                       ← 기존 분석 결과
│   └── h1_rBD_t_notes1_1e-4_0.0~1.5.pkl
│
└── tda_pipeline/                 ← 리팩토링된 파이프라인 (주 작업 폴더)
    ├── config.py                 ← 모든 설정 중앙 관리 (dataclass)
    ├── preprocessing.py          ← MIDI→화음/note 레이블링
    ├── weights.py                ← 가중치/거리 행렬 (refine_connectedness_fast)
    ├── overlap.py                ← 사이클 관리 + 중첩행렬
    ├── generation.py             ← Algorithm 1 & 2
    ├── pipeline.py               ← 전체 흐름 조율 + 캐싱
    ├── run_test.py               ← 즉시 실행 테스트
    ├── adaptive_search.py        ← 적응적 rate 탐색
    ├── diagnose.py               ← 기존↔새 코드 중간결과 비교
    ├── benchmark.py              ← 성능 벤치마크
    ├── professor.py              ← 교수님 코드 복사본
    ├── pickle/                   ← 기존 pkl 복사본
    └── Ryuichi_Sakamoto_-_hibari.mid
```

## 현재 상태와 즉시 해야 할 작업

### [CRITICAL] 0-cycle 버그 해결

리팩토링된 파이프라인에서 **모든 rate에서 cycle이 0개** 감지됨. 기존 pkl에는 48개 존재.

**원인 추정**: 새 코드의 `group_notes_with_duration`(preprocessing.py)과 기존 `group_notes_with_duration_`(process.py)이 다른 화음 레이블을 생성하여, 가중치 행렬 전체가 달라짐.

**진단 방법**: `diagnose.py`를 실행하면 8단계 중간결과를 비교하여 정확히 어느 단계에서 값이 갈라지는지 찾을 수 있음.

```bash
cd tda_pipeline
python diagnose.py
```

**이전에 수정된 버그** (0-cycle과는 별개):
- `prepare_lag_sequences`의 IndexError: `solo_bars=59`(음표 수)와 `solo_timepoints=32`(시점 수)를 혼용 → 분리 완료

### 진단 후 다음 단계

1. `diagnose.py` 결과에서 첫 불일치 지점 확인
2. 해당 함수 수정 (대부분 `group_notes_with_duration` 관련으로 예상)
3. `adaptive_search.py` 재실행하여 cycle 발견 확인
4. `run_test.py`로 음악 생성 검증

## 중장기 목표

### 1. Deep Learning / ML 기반 음악 생성

현재 Algorithm 1(확률적 샘플링)은 중첩행렬의 ON/OFF 패턴만 참조하여 단순 샘플링. 더 정교한 생성을 위해:

- **중첩행렬 → 음악 시퀀스**를 학습하는 모델 구축
- 입력: 중첩행렬 (T × C) + 원곡의 note 시퀀스
- 출력: 위상 구조를 보존하면서 음악적으로 자연스러운 note 시퀀스
- 후보 아키텍처: Transformer, VAE, Diffusion 기반 시퀀스 모델
- Algorithm 2(기존 FC 신경망)의 데이터 정합성 문제도 해결 필요:
  - `L_encoded` 길이(7670) vs `L_onehot` 길이(1088) 불일치
  - 두 악기의 시간축 정렬 방식 재설계

### 2. 교수님 선형대수 코드 개선 (professor.py)

`generateBarcode`는 순수 Python으로 구현된 Persistent Homology 계산기:
- Vietoris-Rips 복합체 구축 + pHcol 알고리즘 (boundary matrix reduction)
- **현재 가장 큰 계산 병목** (전수탐색 시 15,000회 호출, 각 ~5ms)
- 개선 방향:
  - `giotto-tda` 또는 `ripser` (C++ 기반) 라이브러리로 대체 검토
  - 대체 시 기존과 동일한 barcode 결과를 내는지 검증 필수
  - 교수님 코드의 알고리즘 자체를 numpy 벡터화로 최적화하는 것도 가능

### 3. 다른 곡으로 일반화

현재는 "hibari" 전용 하드코딩이 많음 (inst1_end_idx=2006, solo_bars=59 등). 다른 MIDI 파일에도 적용 가능하도록 자동 감지 로직 추가.

## 코드 컨벤션 및 주의사항

### 데이터 흐름의 핵심 변수들

| 변수 | 형태 | 설명 |
|------|------|------|
| `notes_label` | `{(pitch, dur): int}` | note → 1-indexed 정수 레이블 |
| `notes_dict` | `{chord_idx: [note_labels]}` | 화음 → 구성 note 매핑. `notes_dict['name'] = 'notes'` 필수 |
| `adn_i` | `{1: {0: full_seq, 1: lag1_seq, ...}, 2: {...}}` | 악기별 lag 시퀀스 |
| `cycle_labeled` | `{label: [note_indices]}` | 각 cycle의 구성 note 인덱스 |
| `overlap_matrix` | DataFrame (T × C) | 이진 중첩행렬 |

### 수정 시 절대 지켜야 할 것

1. **기존 코드와의 중간결과 일치 확인**: 어떤 함수든 수정 후 반드시 `diagnose.py`로 기존 코드와 비교. 표면적 버그 수정이 깊은 파이프라인 발산을 야기할 수 있음.
2. **notes_dict 구조 유지**: `notes_dict['name'] = 'notes'`를 포함해야 하며, 정수 키가 chord 인덱스, 값이 note 레이블 리스트.
3. **1-indexed vs 0-indexed 주의**: `notes_label`은 1-indexed, numpy 배열 접근은 0-indexed.
4. **professor.py는 직접 수정하지 않기**: 교수님 코드이므로, 개선 시 별도 모듈(`topology.py` 등)에 래핑하거나 대체 라이브러리 사용.

### 테스트 방법

```bash
# 전체 파이프라인 테스트 (pkl 기반, 빠름)
python run_test.py

# 적응적 탐색 (새로 cycle 찾기)
python adaptive_search.py

# 기존 코드 대비 성능 비교
python benchmark.py

# 기존↔새 코드 중간결과 비교
python diagnose.py
```

### 벤치마크 결과 (이미 확인됨)

| 단계 | 기존 | 새 코드 | 배율 |
|------|------|---------|------|
| 전처리 | 105ms | 133ms | 0.8x |
| refine_connectedness | 192ms | 0.27ms | **703x** |
| 활성화 행렬 | 875ms | 1.2ms | **713x** |
| 중첩행렬 전체 | 5.5s | 109ms | **51x** |

## 기술 환경

- Windows, Python 3.10, VS Code
- 주요 패키지: `pretty_midi`, `numpy`, `pandas`, `music21`, `matplotlib`, `torch`(선택)
- 작업 디렉토리: `C:\WK14\tda_pipeline\`
- 사용 언어: 한국어 (코드 주석, 문서, 대화 모두)
