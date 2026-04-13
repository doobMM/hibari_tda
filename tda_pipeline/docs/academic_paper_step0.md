# Topological Data Analysis를 활용한 음악 구조 분석 및 위상 구조 보존 기반 AI 작곡 파이프라인

**저자:** 김민주
**지도:** 정재훈 (KIAS 초학제 독립연구단)
**작성일:** 2026
**키워드:** Topological Data Analysis, Persistent Homology, Tonnetz, Music Generation, Vietoris-Rips Complex, Jensen-Shannon Divergence

---

## 초록 (Abstract)

본 연구는 사카모토 류이치의 2009년 앨범 *out of noise* 수록곡 "hibari"를 대상으로, 음악의 구조를 **위상수학적으로 분석**하고 그 위상 구조를 **보존하면서 새로운 음악을 생성**하는 파이프라인을 제안한다. 전체 과정은 네 단계로 구성된다. (1) MIDI 전처리: 두 악기를 분리하고 8분음표 단위로 양자화. (2) Persistent Homology: 네 가지 거리 함수(frequency, Tonnetz, voice-leading, DFT)로 note 간 거리 행렬을 구성한 뒤 Vietoris-Rips 복합체의 $H_1$ cycle을 추출. (3) 중첩행렬 구축: cycle의 시간별 활성화를 이진 또는 연속값 행렬로 기록. (4) 음악 생성: (3)에서 구한 중첩행렬을 seed로 사용하여 확률적 샘플링 기반의 Algorithm 1과 FC / LSTM / Transformer 신경망 기반의 Algorithm 2 두 방식을 제공.

$N = 20$회 통계적 반복을 통한 정량 검증에서 Tonnetz 거리 함수가 frequency 거리 함수 대비 pitch Jensen-Shannon divergence를 $0.0753 \pm 0.0033$에서 $0.0398 \pm 0.0031$로 **약 $47\%$ 감소**시켰으며, 이는 Welch's $t = 35.1$, Cohen's $d = 11.1$, $p < 10^{-20}$로 극도로 유의한 개선이다. 연속값 중첩행렬을 임계값 $\tau = 0.5$로 이진화한 변형은 기존 이진 중첩행렬 대비 추가로 JS divergence를 $11.4\%$ 개선했으며 ($0.0387 \to 0.0343$, Welch $t = 5.16$), 이 역시 통계적으로 유의했다. 가장 단순한 FC 신경망이 LSTM / Transformer보다 낮은 JS divergence($0.0015$)를 기록한 것은, hibari가 수록된 *out of noise* 앨범의 미학적 성격 — 전통적 선율 인과보다 음들의 공간적 배치에 의존 — 과 정확히 공명하는 관찰이다.

본 연구의 intra / inter / simul 세 갈래 가중치 분리 설계는 hibari의 두 악기 구조 — inst 1은 쉼 없이 연속 연주, inst 2는 모듈마다 규칙적 쉼을 두며 겹쳐 배치 — 를 수학적 구조에 반영한 것이며, 두 악기의 활성/쉼 패턴 관측 (inst 1 쉼 $0$개, inst 2 쉼 $64$개) 이 이 설계를 경험적으로 정당화한다. 본 논문은 수학적 정의부터 통계 실험, 시각자료, 향후 연구 방향까지를 하나의 일관된 흐름으로 정리한다.

---
