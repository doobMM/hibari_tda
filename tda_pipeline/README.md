# TDA Music Pipeline

류이치 사카모토의 **hibari**를 대상으로 Topological Data Analysis(Persistent Homology)를 적용하여, 원곡과 **위상수학적으로 유사한 구조**를 가진 음악을 생성하는 파이프라인입니다.

---

## 파일 구조

```
tda_music_pipeline/
├── config.py              # 모든 설정 중앙 관리
├── preprocessing.py       # MIDI → 화음/note 레이블링
├── weights.py             # 가중치/거리 행렬 계산 (핵심 최적화)
├── overlap.py             # 사이클 관리 + 중첩행렬
├── generation.py          # Algorithm 1 (확률적) & Algorithm 2 (신경망)
├── pipeline.py            # 전체 흐름 조율 + 캐싱
├── run_test.py            # 즉시 실행 가능한 테스트 스크립트
├── OPTIMIZATION_SUMMARY.md
└── README.md
```

---

## 빠른 시작

### 1. 환경 설정

```bash
# Python 3.10+ 권장
pip install pretty_midi numpy pandas matplotlib seaborn music21 scikit-learn tqdm

# (선택) Algorithm 2 사용 시
pip install torch
```

### 2. 파일 배치

아래 파일들을 **같은 디렉토리**에 배치합니다:

```
작업_디렉토리/
├── (이 저장소의 .py 파일들)
├── Ryuichi_Sakamoto_-_hibari.mid    ← MIDI 파일
├── professor.py                      ← 기존 WK14/professor.py (generateBarcode 함수)
└── pickle/                           ← (선택) 기존 분석 결과
    └── h1_rBD_t_notes1_1e-4_0.0~1.5.pkl
```

### 3. 실행

```bash
python run_test.py
```

### 4. 결과 확인

```
generated_output/
├── hibari_tda_20250329_xxxxxx.musicxml   ← MuseScore로 열기
├── hibari_tda_20250329_xxxxxx.mid        ← 미디 재생
└── overlap_matrix.png                     ← 중첩행렬 시각화
```

> **MusicXML/MIDI 재생**: [MuseScore](https://musescore.org/ko) (무료) 설치 후 파일을 열면 악보를 보면서 재생할 수 있습니다.

---

## 단계별 설명

| 단계 | 파일 | 하는 일 |
|------|------|---------|
| **1. 전처리** | `preprocessing.py` | MIDI를 8분음표 단위로 양자화, 두 악기 분리, 화음/note 레이블링 |
| **2. 호몰로지 탐색** | `weights.py` + `professor.py` | 가중치→거리 행렬 변환 후 Persistent Homology 계산 |
| **3. 중첩행렬** | `overlap.py` | 사이클의 시점별 활성화를 스케일 조정하여 이진 행렬 생성 |
| **4. 음악 생성** | `generation.py` | 중첩행렬 기반 확률적 샘플링 (Algo 1) 또는 신경망 (Algo 2) |

---

## 기존 코드(WK14)와의 호환성

- `professor.py`의 `generateBarcode` 함수를 **그대로 사용**합니다
- 기존 `pickle/` 폴더의 `.pkl` 파일을 로드할 수 있습니다
- `notes_dict`, `notes_label` 등의 자료구조 형식을 유지합니다
