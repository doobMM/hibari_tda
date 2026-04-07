# TDA Music Pipeline

사카모토 류이치의 **hibari**를 Topological Data Analysis(Persistent Homology)로 분석하여, 원곡의 위상 구조를 보존하는 새로운 음악을 생성하는 연구 파이프라인.

선행연구(정재훈 외, 2024)의 음악 네트워크 기반 TDA 프레임워크를 계승하되, **intra/inter 가중치 분리, 음악 이론 기반 거리 함수(Tonnetz/Voice-leading/DFT), 위상 구조 보존도 정량화, 모듈 단위 딥러닝 생성**을 추가하였습니다.

---

## 핵심 결과

| 단계 | 성과 |
|------|------|
| 0-cycle 버그 수정 | 0개 → **48개** cycle 발견 |
| Barcode 최적화 (Ripser) | 72ms → **1.6ms** (45배) |
| Tonnetz 거리 도입 | JS divergence **18배** 개선 |
| 모듈 단위 LSTM | JS divergence **42배** 개선 (0.267 → 0.006) |
| **최고 조합** | **Tonnetz + FC + α=0.3 → JS=0.002** |

---

## 빠른 시작

```bash
# 인터랙티브 대시보드 (사전학습 모델, ~1초 생성)
streamlit run dashboard_interactive.py

# 전체 파이프라인 실행
python run_test.py

# 거리 함수별 비교
python test_musical_metrics.py

# 모듈 단위 학습 (LSTM/Transformer)
python module_generation.py
```

---

## 파일 구조

```
tda_pipeline/
├── 핵심 파이프라인
│   ├── config.py                  # MetricConfig 포함 전체 설정
│   ├── preprocessing.py           # MIDI → 화음/note (자동 감지 포함)
│   ├── weights.py                 # 가중치/거리 행렬
│   ├── overlap.py                 # 중첩행렬 (이진/연속값)
│   ├── generation.py              # Algo1 + DL 모델 3종
│   ├── pipeline.py                # 전체 흐름 (Ripser 자동 사용)
│   └── run_test.py                # 통합 테스트
│
├── 최적화/확장 모듈
│   ├── topology.py                # Numpy(2.5x) + Ripser(45x) barcode
│   ├── cycle_selector.py          # Greedy subset 선택 + 보존도
│   ├── musical_metrics.py         # Tonnetz, Voice-leading, DFT
│   ├── eval_metrics.py            # JS, KL, transition matrix
│   ├── module_generation.py       # 4마디 모듈 단위 학습/생성
│   └── precompute_metrics.py      # metric별 캐시 사전 계산
│
├── 대시보드 / 시각화
│   ├── dashboard.py               # 기본 Streamlit 대시보드
│   ├── dashboard_interactive.py   # 중첩행렬 편집 + 즉시 생성
│   └── visualize.py               # Piano roll 시각화
│
├── 실험/비교 스크립트
│   ├── run_comparison.py          # K별 음악 생성 비교
│   ├── run_multi_search.py        # 다중 search 조합
│   ├── run_tuning.py              # 30개 HP grid search
│   ├── test_topology.py           # barcode 검증
│   ├── test_cycle_selector.py     # 보존도 검증
│   ├── test_musical_metrics.py    # 거리 함수 비교
│   └── test_dl_generation.py      # DL 모델 비교
│
├── docs/
│   ├── index.html                 # 비전공자용 보고서
│   ├── paper.pdf                  # 학술 논문 (한글)
│   └── build_paper.py             # 논문 PDF 생성기
│
├── cache/
│   ├── metric_*.pkl               # metric별 PH 결과
│   └── models/                    # 사전학습 가중치
│       ├── fc_best.pt
│       ├── lstm_best.pt
│       └── overlap_*.npy
│
└── output/                        # 생성된 MIDI/WAV/MusicXML
```

---

## 주요 기능

### 거리 함수 플러그인 시스템

```python
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance

# 4가지 거리 중 선택
tonnetz = compute_note_distance_matrix(notes_label, metric='tonnetz')
hybrid = compute_hybrid_distance(freq_dist, tonnetz, alpha=0.3)
```

| 거리 | 원리 | hibari 결과 (JS) |
|------|------|----------------|
| 빈도 (기존) | 1/연달아 등장 횟수 | 0.014 |
| **Tonnetz** | 장3도/완전5도 격자 BFS | **0.002** |
| Voice-leading | 반음 차이 | 0.007 |
| DFT | Fourier 공간 L2 | 0.012 |

### 사용 가능한 모델

| 모델 | 전체 시퀀스 JS | 모듈 단위 JS |
|------|---------------|------------|
| **FC** | **0.002** | 0.003 |
| LSTM | 0.267 (실패) | **0.006** (42x 개선) |
| Transformer | 0.009 | 0.004 |

---

## 인터랙티브 대시보드

`dashboard_interactive.py`는 사전학습된 모델을 로드하여 사용자가 중첩행렬을 직접 편집하고 즉시 음악을 생성할 수 있습니다.

- **모듈 ON/OFF**: 4마디 단위 토글
- **Cycle ON/OFF**: 특정 cycle 전체 토글
- **랜덤 변형**: N% 확률로 bit flip
- **생성 시간**: ~1초 (학습 없음)

---

## 인용

선행연구를 기반으로 합니다:

- 이동진, Mai Lan Tran, 정재훈, "국악의 기하학적 구조와 인공지능 작곡", 2024
- Mai Lan Tran et al., "TDA of Korean Music in Jeongganbo: A Cycle Structure", arXiv:2103.06620, 2021
- Catanzaro, "Generalized Tonnetze", arXiv:1612.03519, 2016
- Tymoczko, "The Generalized Tonnetz", J. Music Theory 56:1, 2012

---

## 라이선스

연구용 코드입니다. hibari MIDI 파일은 저작권자에게 권리가 있습니다.
