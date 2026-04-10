---
name: research-next
description: TDA 음악 분석 관련 선행연구 및 유사 시도를 조사하고, 현재 연구 상태를 기반으로 다음 연구 방향을 제안. "다음에 뭘 해야 할까", "관련 연구 찾아줘", "연구 방향 제시해줘" 등의 요청에 자동 로드.
allowed-tools: WebSearch WebFetch Read Grep
---

## 선행연구 기반 다음 스텝 결정

### 현재 연구 상태 확인
1. `tda_pipeline/docs/academic_paper_full.md` 읽어서 현재까지 수행된 실험 파악
2. `tda_pipeline/docs/step3_data/*.json` 에서 최신 정량 결과 확인
3. CLAUDE.md 에서 프로젝트 개요 + 중장기 목표 확인

### 선행연구 검색 방향

**TDA + Music 분야:**
- "persistent homology music analysis" (핵심 키워드)
- "topological data analysis music generation"
- Tran, Park, Jung (2021) — 국악 정간보 TDA (본 연구의 직접 선행)
- Bergomi, Baratè, Di Fabio — "TDA for music signals"
- Tymoczko — "geometry of music" (Tonnetz, voice-leading 이론적 기반)

**Music Generation 분야:**
- "structure-preserving music generation"
- "topology-aware generative model"
- MusicVAE, Music Transformer 대비 본 연구의 차별점 정리

**수학적 불변량 분야:**
- "deep scale property" + "diatonic" (Gamer, Wilson)
- "Euclidean rhythm" (Bjorklund, Toussaint) — §3.6.4 phase shifting 관련
- "maximal evenness" (Clough, Douthett)

### 보고 형식
1. **검색된 관련 연구 3~5편** 각각에 대해:
   - 핵심 방법론 1줄
   - 본 연구와의 관계 (확장 가능 / 대안 방법 / 비교 대상)
2. **추천 다음 스텝** (우선순위 + 근거):
   - 기존 실험에서 아직 검증되지 않은 가설
   - 선행연구에서 시도했지만 본 연구에 적용하지 않은 방법
   - 논문 심사에서 요구될 가능성이 높은 실험
3. **구체적 실행 계획** (코드 수정 / 실험 설계 / 소요 시간 추정)
