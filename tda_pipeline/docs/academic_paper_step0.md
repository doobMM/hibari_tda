# TDA를 활용한 류이치 사카모토의 〈hibari〉 구조 분석 및 위상구조 기반 AI 작곡 파이프라인 제시

**저자:** 김민주
**지도:** 정재훈 (KIAS 초학제 독립연구단), Claude
**작성일:** 2026.04.20

**키워드:** Topological Data Analysis, Persistent Homology, Tonnetz, DFT, Overlap Matrix, Vietoris-Rips Complex, Music Information Retrieval

---

## 초록 (Abstract)

본 연구는 사카모토 류이치의 2009년 앨범 *out of noise* 수록곡 "hibari"를 대상으로, 음악의 구조를 **위상수학적으로 분석**하고 그 위상구조를 **보존하면서 새로운 음악을 생성**하는 파이프라인을 제안한다. 전체 과정은 네 단계로 구성된다. (1) MIDI 전처리: 두 악기를 분리하고 8분음표 단위로 양자화. (2) Persistent Homology: 네 가지 거리 함수(frequency, Tonnetz, voice leading, DFT)로 note 간 거리 행렬을 구성한 뒤 $H_1$ cycle을 추출. (3) 중첩행렬 구축: cycle의 시간별 활성화를 이진 또는 연속값 행렬로 기록. (4) 음악 생성: 중첩행렬을 seed로 하여 확률적 샘플링 기반의 Algorithm 1과 FC / LSTM / Transformer 신경망 기반의 Algorithm 2 두 방식으로 음악 생성.

$N = 20$회 통계적 반복을 통한 정량 검증에서, **Algorithm 1**(확률적 샘플링) 기반으로 DFT 거리 함수가 네 거리 함수 중 최우수로 확인되었다 — frequency 대비 pitch JS divergence를 $0.0344 \pm 0.0023$에서 $0.0213 \pm 0.0021$로 **약 $38.2\%$ 감소**시켰다 ($p < 10^{-20}$). 이후 DFT 기반 연속값 OM에서 $\alpha = 0.25$ ($K = 14$) 조건의 per-cycle $\tau_c$ 재탐색을 통해 Algorithm 1 신규 최저 $\mathbf{0.00902 \pm 0.00170}$ ($N=20$)를 달성했다. 이는 $\alpha = 0.5$ 조건의 per-cycle $\tau_c$ 결과 ($0.01489$) 대비 $-39.4\%$ 개선이며 ($p = 1.44 \times 10^{-15}$), $\alpha = 0.25$가 §5.7 이진 OM과 per-cycle $\tau_c$ 양쪽 모두에서 최적임이 이중으로 확인되었다. **Algorithm 2**에서는 연속값 중첩행렬 입력의 FC가 $\mathbf{0.00035 \pm 0.00015}$ ($N=10$, $\alpha=0.5$)로 최우수였고, Transformer 대비 Welch $p = 1.66 \times 10^{-4}$로 유의한 우위를 보였다. 두 최저값은 이론 최댓값 $\log 2 \approx 0.693$의 각각 약 $1.30\%$ (Algo1)와 $0.05\%$ (Algo2)다.

본 연구의 intra / inter / simul 세 갈래 가중치 분리 설계는 hibari의 두 악기 구조 — inst 1은 쉼 없이 연속 연주, inst 2는 모듈마다 규칙적 쉼을 두며 겹쳐 배치 — 를 수학적 구조에 반영한 것이며, 두 악기의 활성/쉼 패턴 관측 (inst 1 쉼 $0$개, inst 2 쉼 $64$개) 이 이 설계를 경험적으로 정당화한다.

---
