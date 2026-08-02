# TDA 음악 생성 파이프라인 — 차기 알고리즘 조사 (2026-08)

작성일: 2026-08-02 | 세션: E(조사) → 배정은 표 참조
조사 방법: WebSearch/WebFetch, 2024~2026 우선. 확인 불가 항목은 "미확인"으로 명시.

## 0. 조사 전제 (필터링 기준)

- **입력**: hibari 등 원곡 1곡의 중첩행렬(OM, T×K 이진/연속 행렬. hibari 예시 T=1088×K=14, 모바일 세그먼트는 T=60).
- **제약**: (a) 브라우저 client-side 실행 (ONNX Runtime Web, 모델 수 MB 이하) (b) 데이터 극소량 — 곡 1개=시퀀스 1개 (c) 개인 연구, GPU 클러스터 없음, CPU 수 분 내 학습.
- **이미 실패/한계 확인 — 중복 제안 금지**:
  - OM 디퓨전(MLP-DDPM, cosine T=200): 밀도 3배 과밀(139→418), 시간 autocorr 붕괴(0.814→0.504). 원인 = MLP가 840차원(60×14)을 평면화해 시간축 구조를 못 배움 (`project_om_diffusion_negative_0621`, 커밋 54e7878).
  - OM VAE(840차원 MLP, z=12): 작동은 하나 prior 샘플 품질 제한적(재구성 MAE 0.033은 양호, 생성 다양성 낮음).
  - 음악이론 미적 지표(협화도+성부진행+도약) re-ranking: 합성 지표 자체가 calibration 실패(셔플이 원곡보다 점수 높음). 협화도(C) 성분만 유효, 나머지는 hibari의 2성부 음역 분리 구조를 오히려 페널티(`project_aesthetic_rerank_negative_0613`).
- 이 세 실패의 공통 원인은 **"시간축을 구조로 보존하지 못함"** + **"암묵적 지표로는 위상 구조를 못 잡음"** 두 가지로 수렴한다. 아래 후보는 이 두 축을 정면으로 다루는 것을 우선했다.

---

## 1. 위상 손실 결합 디노이저 — TopoDiffusionNet 방식 (최우선)

**① 요약**: ICLR 2025 논문. 확산 모델의 각 디노이징 스텝에서 생성 중인 이진 마스크에 직접 persistent homology를 계산해 Betti 수(0차원=객체 수, 1차원=구멍 수)를 목표값에 맞추는 손실 `L_topo`를 `L_simple`(표준 diffusion loss)과 함께 역전파한다. "확산 모델이 이렇게 기본적인 위상 제약(구멍 개수)조차 못 지킨다"는 문제의식에서 출발.

**② 접목 설계**: 이미 계획된 "1D-conv/UNet denoiser (60×14, 시간축 보존)" 후속안에 그대로 결합 가능. 입력=노이즈가 섞인 60×14 이진 그리드, 출력=디노이즈된 그리드. 손실 = `L_simple(MSE) + λ·L_topo(PH(생성 OM), 목표 Betti)`. 목표 Betti는 실제 hibari OM의 컬럼별(cycle별) 활성 구간 수 — 이는 이미 파이프라인이 계산하는 barcode/overlap 정보에서 바로 뽑을 수 있어 데이터 추가 수집이 필요 없다. 밀도 3배 폭주 문제를 구조적으로 억제할 수 있는 게 핵심 — 디노이저가 "구멍 개수"를 못 맞추면 직접 벌점을 받으므로, 시간축 붕괴(autocorr 0.50) 완화를 기대할 수 있다.
의존 라이브러리: `cripser`(Cubical Ripser), `gudhi`, `POT` — 모두 pip 설치 가능, 학습(오프라인)에만 필요하고 **브라우저 추론에는 불필요**(추론은 표준 디노이징 스텝만 실행).

**③ 난이도**: 원 논문은 256×256(65536픽셀) 이미지 대상이라 PH 계산이 무겁지만, 우리 그리드는 60×14=840셀로 78배 작다 — CPU에서 스텝당 PH 계산이 수 ms 이내일 것으로 예상(미확인, 실측 필요). 기존 공개 코드(GitHub, OpenAI improved-diffusion 포크)를 이진 그리드용으로 축소 이식하는 작업이 필요 — **중간 난이도, 예상 1~2일 구현 + CPU 수십 분 학습**.

**④ 기대효과 · 리스크**: 기대 — 디퓨전 재도전의 근본 실패 원인(시간축 구조 미학습)을 손실 함수 레벨에서 직접 겨냥하므로 이전 시도보다 성공 가능성이 구조적으로 높음. 리스크 — cubical persistence의 gradient는 "거의 어디서나 미분 가능"이지 항상 안정적이진 않음(critical point 근처에서 subgradient 불연속), 하이퍼파라미터(λ) 튜닝 필요. 확산 모델 자체가 소량 데이터에 약하다는 근본 한계는 여전(D3PM 등과 병행 검토 권장, §3).

**⑤ 출처**:
- [TopoDiffusionNet: A Topology-aware Diffusion Model (arXiv 2410.16646)](https://arxiv.org/html/2410.16646v1)
- [OpenReview — TopoDiffusionNet](https://openreview.net/forum?id=ZK1LoTo10R)
- [GitHub — Saumya-Gupta-26/TopoDiffusionNet](https://github.com/Saumya-Gupta-26/TopoDiffusionNet)

---

## 2. 이산 상태공간 디퓨전 (D3PM / absorbing-state) — OM을 연속값이 아닌 이진 토큰으로 직접 확산

**① 요약**: Structured Denoising Diffusion in Discrete State-Spaces(D3PM, NeurIPS 2021)의 흡수상태(absorbing-state) 변형은 노이즈 과정을 "연속 가우시안 → 임계값" 대신 "각 셀을 확률적으로 mask 토큰으로 흡수 → 역과정에서 복원"으로 정의한다. 이미 심볼릭 음악(피아노롤류)에 D3PM을 적용해 note-level infilling까지 지원한 선례가 있다(IJCAI 2023).

**② 접목 설계**: OM의 각 셀(0/1)을 이산 토큰(0, 1, [MASK])으로 취급. 순방향 과정에서 임의 비율의 셀을 [MASK]로 흡수시키고, 역방향에서 원래 값을 복원하도록 작은 모델(1D-conv 또는 attention, 60×14 입력)을 학습. **연속 노이즈+임계값 방식이 아니므로 "밀도 3배 폭주"가 구조적으로 발생하기 어렵다** — 흡수상태 모델은 각 위치의 최종 분포가 카테고리형이라 원래 0/1 비율(밀도)에서 크게 벗어나려면 모델이 명시적으로 그렇게 학습돼야 하기 때문. §1과 병행하거나(위상 손실 + 이산 상태공간 결합), 더 간단한 대안으로 단독 적용도 가능.

**③ 난이도**: 최소 구현체가 이미 공개돼 있음(400줄, PyTorch) — 이를 60×14 그리드에 맞게 축소 이식하는 작업. **낮은~중간 난이도, 예상 반나절~1일 구현 + CPU 수십 분 학습**. §1보다 구현이 단순하다(PH 계산 불필요).

**④ 기대효과 · 리스크**: 기대 — 이진 데이터 특성과 노이즈 프로세스가 정확히 일치해 §1보다 구현 리스크가 낮으면서도 밀도 폭주 문제를 다른 각도로 해결. 리스크 — 심볼릭 음악 논문(2305.09489)의 실제 데이터 규모·학습시간은 초록만으로 확인 불가(미확인) — 대규모 코퍼스 가정일 수 있어 극소데이터 적응이 필요할 수 있음. 이 프로젝트처럼 시퀀스 1개 학습에 D3PM을 쓴 선례는 발견하지 못함(미확인) — §4의 SinTra식 단일시퀀스 전략과 결합 검토 필요.

**⑤ 출처**:
- [Structured Denoising Diffusion Models in Discrete State-Spaces (NeurIPS 2021, D3PM 원논문)](https://papers.neurips.cc/paper/2021/file/958c530554f78bcd8e97125b70e6973d-Paper.pdf)
- [Discrete Diffusion Probabilistic Models for Symbolic Music Generation (arXiv 2305.09489)](https://arxiv.org/abs/2305.09489)
- [GitHub — cloneofsimo/d3pm (최소 PyTorch 구현, 400줄)](https://github.com/cloneofsimo/d3pm)

---

## 3. 단일 시퀀스 다중 스케일 학습 — SinTra (SinGAN 계열의 음악 버전)

**① 요약**: ISMIR 2021. SinGAN의 "이미지 1장에서 학습" 철학을 음악에 이식 — **곡 1개(멀티트랙 세그먼트 1개)만으로** Transformer-XL 피라미드를 거친-세밀 순서로 학습해 유사하되 다양한 변주를 생성한다. "데이터=시퀀스 1개"라는 이 프로젝트의 제약과 정확히 같은 문제를 다룬 몇 안 되는 선행연구.

**② 접목 설계**: hibari OM(T=1088×K=14) 하나를 다운샘플 피라미드(예: T=1088 → 272 → 68)로 분해. 각 스케일에서 작은 Transformer를 "이전 스케일 업샘플 결과 + 노이즈 → 현재 스케일 OM"으로 학습(패치 단위 판별/재구성). 최하위 스케일에서 전체 구조(저해상도 cycle 활성 패턴)를, 상위 스케일에서 디테일(정확한 on/off 타이밍)을 학습 — Algorithm 2(FC/LSTM/Transformer)를 대체하기보다 **원곡 하나로 다양한 변주를 뽑아내는 새 출구**로 포지셔닝하는 게 적합. 데이터 구성은 슬라이딩 윈도 불필요(SinGAN 계열은 애초에 patch 단위 내부 통계를 학습하므로 원본 그리드 자체가 모든 학습 데이터).

**③ 난이도**: Transformer-XL 피라미드 전체 구현은 상당한 작업량이지만, 우리 그리드가 이미지/오디오보다 훨씬 작으므로(피라미드 3~4단, 각 단 T≤300) 소형 attention 블록으로 축소 가능. **중간~높은 난이도, 예상 2~3일 구현 + CPU 학습(스케일당 수 분, 원 논문 학습시간 자체는 미확인)**.

**④ 기대효과 · 리스크**: 기대 — 극소데이터 제약을 정면으로 설계 철학에 내장한 유일한 후보. "원곡과 위상수학적으로 유사하되 다른 곡"이라는 이 연구의 최종 목표(`feedback_generation_direction`)와 방향이 일치 — 다중 스케일이 곧 "구조는 유지, 디테일은 자유"의 자연스러운 구현. 리스크 — 논문 자체가 다성부 MIDI 이벤트 시퀀스 대상이라 OM(이진 T×K 행렬)에 맞게 다운샘플 정의(풀링 방식, cycle 축은 다운샘플 대상인지 등)를 새로 설계해야 함 — 직접 이식 불가, 재설계 필요. 학습 데이터량·시간 관련 세부사항은 PDF 파싱 실패로 확인하지 못함(미확인, 원문 재확인 필요).

**⑤ 출처**:
- [SinTra: Learning an Inspiration Model from a Single Multi-track Music Segment (ISMIR 2021)](https://archives.ismir.net/ismir2021/paper/000083.pdf)
- [SinGAN: 원조 단일 이미지 학습 프레임워크 참고 (Improved Techniques for Training Single-Image GANs)](https://arxiv.org/pdf/2003.11512)

---

## 4. 경량 조건화 어댑터 — MuseControlLite 방식 (decoupled cross-attention + RoPE)

**① 요약**: ICML 2025. 텍스트-음악 생성 모델에 멜로디/리듬/다이내믹스 같은 시간에 따라 변하는 조건을 "가볍게" 주입하는 방법. 핵심 발견 — 조건이 시간의 함수일 때 회전위치임베딩(RoPE)을 디커플드 cross-attention에 추가하면 SOTA 파인튜닝 대비 파라미터 6.75배 적게 쓰고도 멜로디 제어 정확도가 56.6%→61.1%로 오름.

**② 접목 설계**: 현재 Algorithm 2(FC/Transformer)에 "더 밝게/더 성기게" 같은 사용자 의도를 넣을 방법이 없음(대시보드는 읽기전용 산출물 위주로 단순화된 상태, `feedback_dashboard_too_complex`). 기존 학습된 FC/Transformer 가중치는 고정한 채, 작은 cross-attention 어댑터(입력=사용자가 지정한 "목표 밀도/cycle 강도" 시퀀스, RoPE로 시간 위치 인코딩)만 추가 학습. 원 모델 재학습 없이 조건부 생성 인터페이스를 추가하는 구조라 브라우저 배포 시 기존 ONNX 모델에 얇은 레이어만 얹으면 됨.

**③ 난이도**: 어댑터 자체는 작은 cross-attention 블록 하나 — **낮은 난이도**. 다만 원 논문은 대형 diffusion 백본(오디오) 기준이라, 우리의 KB급 FC/Transformer에 이식하려면 "무엇을 조건으로 줄지"(밀도 스칼라 vs 시간별 강도 벡터)부터 재설계해야 함. **예상 반나절~1일 구현 + CPU 학습(원 모델보다 훨씬 작으므로 수 분 내)**.

**④ 기대효과 · 리스크**: 기대 — 사용자가 요청한 "인터랙티브·참여형" 방향(대시보드 R1~R5 트랙)과 직결되는 실질적 UX 개선. 브라우저 제약과도 궁합이 좋음(어댑터가 원 모델보다 훨씬 작음). 리스크 — 논문의 정량 효과(6.75배, 56.6→61.1%)는 오디오 diffusion 도메인 수치이므로 우리 문제(이진 행렬, KB급 모델)에 그대로 이전된다는 보장은 없음(미확인, 실험 필요).

**⑤ 출처**:
- [MuseControlLite: Multifunctional Music Generation with Lightweight Conditioners (arXiv 2506.18729)](https://arxiv.org/abs/2506.18729)
- [프로젝트 데모 페이지](https://musecontrollite.github.io/web/)

---

## 5. 잠재 스티어링 벡터 — CFG의 무학습 경량 대안

**① 요약**: LLM 활성화 조작(activation steering) 계열 기법. 모델을 재학습하지 않고, 은닉층 활성값에 "원하는 방향" 벡터(예: 밀집 샘플 평균 활성 − 희소 샘플 평균 활성)를 추론 시점에 스케일 조절해 더하는 것만으로 속성을 제어. 선형 분류기 가정 하에서는 classifier guidance가 이 방식과 수학적으로 같아짐.

**② 접목 설계**: 이미 학습된 Algorithm 2 FC/Transformer의 은닉층에서, 기존 OM 캐시(hibari/aqua/solari 등 여러 τ·α 조합 결과)로부터 "고밀도 vs 저밀도", "cycle 활성 집중 vs 분산" 같은 대비 그룹의 평균 활성 차이 벡터를 계산해 저장. 추론 시 사용자가 슬라이더로 계수 β를 조절하면 `h' = h + β·v_direction`로 은닉 활성을 이동. **학습이 전혀 필요 없다** — 기존 가중치와 캐시된 OM 결과만으로 벡터 추출 가능.

**③ 난이도**: 벡터 계산은 순전파 후 평균 차이를 구하는 것뿐 — **가장 낮은 난이도**. 기존 FC/Transformer 구조에 벡터 더하는 hook만 추가하면 되므로 **예상 수 시간, 학습 없음(CPU 불필요)**. 5개 후보 중 유일하게 "학습" 단계가 없는 후보.

**④ 기대효과 · 리스크**: 기대 — 즉시 실행 가능하면서 §4(MuseControlLite 어댑터)보다도 훨씬 저비용. 실패해도 손실이 거의 없어 첫 시도로 적합. 리스크 — 선형 방향 벡터가 이 문제(이진 위상 구조 생성)에서 얼마나 해석 가능한 축을 잡아줄지 불확실 — 이미지/텍스트 도메인 결과가 이진 행렬에도 통할지는 검증 전까지 미확인. 효과가 미미하면 §4로 승격.

**⑤ 출처**:
- [Guiding Giants: Lightweight Controllers for Weighted Activation Steering in LLMs (arXiv 2505.20309)](https://arxiv.org/html/2505.20309v3)
- [SteerVLM: Robust Model Control through Lightweight Activation Steering (arXiv 2510.26769)](https://arxiv.org/html/2510.26769v1)

---

## 6. 페르시스턴스 포인트 직접 조건화 — TopoGen 방식

**① 요약**: Computer Graphics Forum 2025(3D 형상 생성 논문). Betti 수뿐 아니라 **persistence point(생–사 좌표) 자체를 조건 벡터로 사용**해 생성 모델을 guide. persistence point를 바꾸면 생성물의 위상을 명시적으로 조정할 수 있음을 보임.

**② 접목 설계**: 이 프로젝트는 이미 hibari의 barcode(H1 cycle들의 생–사 persistence)를 계산해 두고 있고, `project_barcode_experiment`(Wasserstein 기반 모듈 선택)에서 barcode 정보를 활용한 바 있다. 지금까지는 barcode를 "모듈 선택 지표"로만 썼는데, TopoGen처럼 **barcode 좌표 자체를 생성기의 조건 입력**으로 직접 사용하는 시도는 아직 없었다. 즉 Algorithm 2 입력을 "OM만" → "OM + K개 cycle의 (birth, death) 좌표 벡터"로 확장. 이는 압축된 요약 통계를 명시적으로 노출하는 것이라 극소데이터에서 오히려 모델이 배워야 할 정보량을 줄여줄 수 있음.

**③ 난이도**: 입력 벡터 concat 수준의 변경이라 구현 자체는 쉽지만, "조건을 바꿔서 실제로 위상이 통제되는지" 검증하려면 원 논문처럼 조건-결과 간 정합성 평가 지표를 새로 설계해야 함. **중간 난이도, 예상 1일 구현 + 기존 학습 파이프라인 재사용(수 분)**.

**④ 기대효과 · 리스크**: 기대 — 이미 계산해 둔 barcode 자산을 재활용하는 저비용 확장이며, §7.1.9(barcode 모듈 선택 Pearson=0.503)의 후속 실험으로 자연스럽게 이어짐. 리스크 — 3D 형상(연속 좌표) 도메인 사례라 이산 이진 행렬로의 이전 효과는 미확인. 조건이 늘어나면 극소데이터에서 과적합 위험도 커짐.

**⑤ 출처**:
- [TopoGen: Topology-Aware 3D Generation with Persistence Points (Computer Graphics Forum, 2025, DOI 10.1111/cgf.70257)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.70257)

---

## 7. Persistence Diagram Matching(PDM) 손실 — 그래프 관점의 보조 손실 (§1의 대안/보완)

**① 요약**: NeurIPS 2025 (TAGG, Topology-aware Graph Diffusion). 그래프 확산모델에 PDM 손실(생성 그래프와 원본 그래프의 persistence diagram을 직접 비교)과 위상 인지 attention 모듈(TAM)을 추가해 위상 충실도를 높임.

**② 접목 설계**: OM을 "시간 노드 – cycle 노드 이분 그래프(bipartite graph)"로 재해석하면 §1의 이미지형 접근(cubical complex) 대신 그래프형 접근을 쓸 수 있다. §1의 손실이 이미지/그리드 관점이라면 이쪽은 그래프 관점 — 어느 쪽이 OM 데이터에 더 잘 맞을지는 실험 전까지 불확실하므로, §1을 1차로 시도하고 성능이 부족하면 이쪽을 보조/대체 손실로 검토하는 것을 권장.

**③ 난이도**: PDM 손실의 정확한 수식은 OpenReview 페이지 접근 제한(브라우저 검증 페이지만 반환)으로 **확인하지 못함(미확인)** — 실제 구현 난이도는 원문 확인 후 재평가 필요. 공개 코드 여부도 미확인.

**④ 기대효과 · 리스크**: 기대 — §1과 상호 보완적인 2차 옵션 확보. 리스크 — 핵심 손실 정의를 확인하지 못한 상태라 난이도·구현량 추정 신뢰도가 낮음. **우선순위를 낮게 두고, §1이 실패하거나 부족할 때 재조사 권장**.

**⑤ 출처**:
- [Topology-aware Graph Diffusion Model with Persistent Homology — OpenReview](https://openreview.net/forum?id=sye27MizdM)
- [NeurIPS 2025 포스터 페이지](https://neurips.cc/virtual/2025/poster/115645)

---

## 8. 이산 흐름매칭(Discrete Flow Matching) — 디퓨전의 대안 패러다임

**① 요약**: Meta의 공식 라이브러리(`facebookresearch/flow_matching`)가 연속·이산 흐름매칭을 모두 지원. 이산 상태공간에서 확률질량이 시간에 따라 연속적으로 흐르도록 학습해, 반복적 정제(iterative refinement)로 비자기회귀적(non-autoregressive) 생성을 수행. 2025년 다수 확장 연구(분자, 음성 등) 존재.

**② 접목 설계**: §2(D3PM)와 같은 문제(OM을 이산 상태공간에서 직접 생성)를 다른 수학적 틀로 접근. 이론적으로 few-step 샘플링이 가능해 브라우저 추론 속도에 유리할 수 있음.

**③ 난이도**: 공식 라이브러리가 있어 진입장벽은 낮아 보이나, 텍스트/이미지용 예제뿐이고 우리처럼 극소데이터·초소형 모델에 맞춘 사례는 찾지 못함(미확인) — 처음부터 커스텀 구현이 필요해 **중간~높은 난이도**. **주의**: 검색 결과에 따르면 이 라이브러리는 **CC BY-NC 라이선스**로 명시돼 있어(연구용 한정), 코드를 프로젝트에 그대로 통합·재배포할 때 라이선스 조건을 확인해야 함(미확인 세부조항 — 상업적 이용 제한 여부 등 원문 재확인 필요).

**④ 기대효과 · 리스크**: 기대 — §2보다 이론적으로 정교한 대안, 적은 샘플링 스텝. 리스크 — §2(D3PM, 400줄 미니멀 구현 존재)에 비해 구현 성숙도·참고자료가 부족해 개인 연구 환경에서 우선순위가 낮음. 라이선스 이슈도 확인 필요.

**⑤ 출처**:
- [GitHub — facebookresearch/flow_matching](https://github.com/facebookresearch/flow_matching)
- [Discrete Flow Matching (arXiv 2407.15595)](https://arxiv.org/pdf/2407.15595)

---

## 9. 브라우저 경량 추론 — ONNX Runtime Web WebGPU 업그레이드 경로

**① 요약**: ONNX Runtime 1.17(2024)부터 WebGPU 실행공급자(EP)가 공식 지원되며, Stable Diffusion Turbo급 모델까지 브라우저에서 구동한 사례가 보고됨. Chrome/Edge 113+(Mac/Win/ChromeOS), Android Chrome 121+에서 기본 활성화.

**② 접목 설계**: 이 프로젝트는 이미 ONNX 모델(173KB급)을 브라우저에 배포 중(CLAUDE.md 기술환경 기록). §1~§8 중 어떤 후보를 채택하든 모델이 커지면(특히 §3 SinTra 피라미드나 §1 conv denoiser) 현재 WASM 실행 경로가 병목이 될 수 있음. 대응: (a) WebGPU EP를 progressive enhancement로 추가(미지원 브라우저는 WASM로 자동 폴백), (b) int8 양자화로 §1/§3처럼 커진 모델의 첫 로드 크기를 억제, (c) `mobile.md` 규칙대로 추론은 Web Worker로 분리해 메인스레드 60fps 유지.

**③ 난이도**: ONNX Runtime Web은 EP 선택이 설정값 수준이라 **낮은 난이도** — 단, 현재 대시보드가 WASM만 쓰고 있는지 WebGPU도 이미 시도했는지는 이번 조사 범위에서 코드 확인을 하지 않아 **미확인**(별도 세션 B에서 `hibari_dashboard/` 내 onnxruntime 초기화 코드 확인 필요).

**④ 기대효과 · 리스크**: 기대 — 현재 모델(수십~수백 KB급)엔 필수는 아니지만, §1/§3 채택 시 대비용 인프라 정비. 리스크 — WebGPU 미지원 구형 브라우저·iOS Safari 일부 버전에서 폴백 필요(모바일 규칙 §"iOS Safari·Android Chrome 양쪽 최소 1회 실기기 검증" 준수 필요). 지금 당장 시급하지 않음 — §1/§3 착수 시점에 재검토.

**⑤ 출처**:
- [ONNX Runtime Web unleashes generative AI in the browser using WebGPU (Microsoft Open Source Blog, 2024)](https://opensource.microsoft.com/blog/2024/02/29/onnx-runtime-web-unleashes-generative-ai-in-the-browser-using-webgpu/)
- [Using WebGPU — onnxruntime 공식문서](https://onnxruntime.ai/docs/tutorials/web/ep-webgpu.html)

---

## 검토했으나 부적합 판정

| 후보 | 부적합 사유 | 출처 |
|---|---|---|
| **문법 제약 디코딩** (DOMINO, IterGen 등 LLM 구조화 출력 기법) | CFG/정규식 기반 토큰 검증은 텍스트·코드처럼 "이산 문법이 있는" 출력에 맞춰져 있음. OM은 이진 행렬이지 문법을 가진 토큰열이 아니라 자동자(automaton)를 새로 설계해야 하는데, 그 결과가 이미 구현된 Algorithm 1(확률적 규칙 기반 샘플러)보다 나을 근거가 없음. 철학적으로는 "생성 중 하드 제약 강제"라는 아이디어는 참고할 만하나 직접 이식 대상은 아님. | [DOMINO (arXiv 2403.06988)](https://arxiv.org/abs/2403.06988), [IterGen (arXiv 2410.07295)](https://arxiv.org/abs/2410.07295) |
| **Live Music Diffusion Models** (실시간 오디오 디퓨전, 340M 파라미터) | 원시 오디오 도메인(우리는 심볼릭 OM)이고, "겨우" 340M 파라미터라 해도 브라우저 KB~MB 제약을 수백 배 초과. 데이터효율(~12초 오디오로 파인튜닝) 아이디어 자체는 흥미롭지만 모델 스케일이 근본적으로 안 맞음. | [Live Music Diffusion Models (arXiv 2605.22717)](https://arxiv.org/html/2605.22717v1) |

---

## 우선순위 표

| 순위 | 후보 | 분류 | 권장 세션 | 핵심 근거 |
|---|---|---|---|---|
| 1 | §5 잠재 스티어링 벡터 (CFG-lite) | **즉시 실행 가능** | B | 학습 불필요, 기존 가중치+캐시만으로 수 시간 내 시도. 실패 비용 최소 |
| 2 | §2 D3PM 이산 상태공간 디퓨전 | **즉시 실행 가능** | B | 400줄 미니멀 구현 존재, 이진 데이터에 노이즈 프로세스가 정확히 부합, 밀도 폭주를 구조적으로 억제 |
| 3 | §9 ONNX WebGPU 인프라 정비 | **즉시 실행 가능** (단, §1/§3 착수 전엔 낮은 긴급도) | B | 설정 수준 변경, §1/§3 채택 대비 |
| 4 | §1 TopoDiffusionNet식 위상 손실 결합 | **중기** | B→A(평가) | 디퓨전 실패의 근본 원인(시간축 미학습)을 손실 레벨에서 정면 공략. 78배 작은 그리드라 CPU 가능성 높음(단, 실측 전 미확인) |
| 5 | §4 MuseControlLite 경량 어댑터 | **중기** | B→C(청취) | 대시보드 인터랙션 방향과 직결, 원 모델 재학습 불필요 |
| 6 | §6 Persistence Point 조건화 (TopoGen식) | **중기** | A | 기존 barcode 자산 재활용, §7.1.9 후속선상 |
| 7 | §3 SinTra 단일시퀀스 피라미드 | **중기~장기** | B | 극소데이터 철학이 가장 잘 맞지만 재설계 범위가 가장 큼 |
| 8 | §7 PDM 손실 (그래프 관점) | **장기** | B(재조사 먼저) | 핵심 수식 미확인 — §1 결과 나온 뒤 재검토 |
| 9 | §8 이산 흐름매칭 | **장기** | B | 라이선스(CC BY-NC) 확인 필요, 구현 성숙도가 §2보다 낮음 |

---

## 결론

가장 먼저 시도할 가치가 있는 것은 **§5(잠재 스티어링 벡터)**다. 학습이 전혀 필요 없고 기존 자산만으로 반나절 내 결과를 볼 수 있어, 다른 모든 후보에 앞서 "지금 있는 모델을 재학습 없이 더 쓸모 있게 만들 수 있는가"를 즉시 확인할 수 있다. 실패해도 잃을 게 거의 없다.

구조적으로 가장 중요한 것은 **§1(TopoDiffusionNet식 위상 손실)**과 **§2(D3PM)**다. 둘 다 지난 OM 디퓨전 실패의 실제 원인 — "MLP가 시간축을 평면화해 구조를 못 배움" — 을 서로 다른 방식으로 정면 공략한다. §1은 손실 함수에 위상 제약을 명시적으로 추가하고, §2는 애초에 노이즈 프로세스를 이진 데이터 특성에 맞춰 밀도 폭주가 나오기 어렵게 만든다. 이미 계획돼 있던 "1D-conv/UNet denoiser" 후속안과 결합하면 두 아이디어 모두 적용 가능하므로, **conv denoiser 구현 시 D3PM식 이산 노이즈 프로세스 + TopoDiffusionNet식 위상 손실을 함께 넣는 통합안**이 실질적으로 가장 유망한 중기 과제다.
