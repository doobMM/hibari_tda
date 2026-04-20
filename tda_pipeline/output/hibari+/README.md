# hibari TDA Pipeline — 음악 생성 파일 목록

**프로젝트:** 위상수학적 데이터 분석(TDA) 기반 사카모토 류이치 hibari 음악 생성 연구  
**원곡:** Ryuichi Sakamoto — *hibari* (*out of noise*, 2009)  
**렌더링:** UprightPiano KW SF2 · 44.1 kHz · 16-bit · Stereo · 서스테인 페달 + Reverb + Chorus  
**생성일:** 2026-04-20

---

## 파일 목록 및 스펙

| ID | 파일명 (WAV) | 길이 | 크기 | 설정 요약 | JS↓ | 비고 |
|:--:|:-----------|-----:|-----:|:---------|----:|:-----|
| **v0** | v0_hibari_original.wav | 8'16" | 83 MB | 원곡 MIDI 직접 렌더링 | — | 비교 기준 |
| **v1** | v1_algo1_frequency_binary.wav | 13'08" | 133 MB | Algo 1 · frequency 거리 · Binary OM | 0.0335 | §4.1 baseline |
| **v2** | v2_algo1_dft_binary.wav | 12'33" | 127 MB | Algo 1 · DFT 거리 · Binary OM | 0.0144 | §4.1 DFT 효과 |
| **v3** | v3_algo1_dft_percycle_tau_alpha05.wav | 12'23" | 125 MB | Algo 1 · DFT · per-cycle τ · α=0.5 | 0.0144 | §5.7 |
| **v4** | v4_algo1_dft_percycle_alpha025.wav | 12'22" | 125 MB | Algo 1 · DFT · per-cycle τ · α=0.25 | 0.0107 | §5.8.1 Algo 1 최저 |
| **v5** | v5_algo2_fc_cont_dft_alpha05.wav | 8'17" | 84 MB | Algo 2 FC-cont · DFT · α=0.5 | 0.00022 | §5.8.2 수치 절대 최저 ★ |
| **v6** | v6_block_p3_bestof10_m0.wav | 8'17" | 84 MB | §6 Block P3 · DFT · α=0.25 · m=0 | 0.0148 | §6.6 블록 단위 best |
| **vD** | vD_tonnetz_transformer.wav | 8'14" | 83 MB | Tonnetz · Transformer · scale_major · block_permute(32) | 0.334* | §5.6 위상 보존 변주 ★ |
| **vH** | vH_tonnetz_complex_legacy.wav | 14'09" | 143 MB | Tonnetz · Complex(rc=0.1) · per-cycle τ · α=0.25 | 0.0177 | §5.6.3 Complex 레거시 |

> **JS** = JS Divergence (원곡 pitch 분포 대비, 낮을수록 원곡에 가까움)  
> **\*** vD의 JS 0.334는 vs 원곡 pitch JS — note 재분배로 의도적으로 다른 음역 사용. vs ref pitch JS = 0.014

---

## 포함 파일 형식

| 확장자 | 설명 | 해당 ID |
|:------:|:-----|:--------|
| `.wav` | 최종 오디오 (Stereo, 44.1 kHz, 16-bit PCM) | 전체 (v0–vH) |
| `.mid` | MIDI (Standard MIDI Format 1) | v1–v4, v6, vD, vH |
| `.musicxml` | MusicXML 악보 | v1–v4, vH |

---

## 실험 파라미터 상세

| ID | metric | α | ow | dw | overlap | model | gap |
|:--:|:------:|:-:|:--:|:--:|:-------:|:-----:|:---:|
| v1 | frequency | 0.5 | 0.3 | 1.0 | binary | Algo 1 | 0 |
| v2 | DFT | 0.5 | 0.3 | 1.0 | binary | Algo 1 | 0 |
| v3 | DFT | 0.5 | 0.3 | 1.0 | continuous → per-cycle τ | Algo 1 | 0 |
| v4 | DFT | 0.25 | 0.3 | 1.0 | continuous → per-cycle τ | Algo 1 | 0 |
| v5 | DFT | 0.5 | 0.3 | 1.0 | continuous | Algo 2 (FC) | 0 |
| v6 | DFT | 0.25 | 0.3 | 1.0 | continuous → per-cycle τ | Algo 1 (block) | 0 |
| vD | Tonnetz | 0.5 | 0.3 | 1.0 | binary | Algo 2 (Transformer) | 0 |
| vH | Tonnetz | 0.25 | 0.0 | 0.3 | continuous → per-cycle τ | Algo 1 (Complex) | 0 |

> **α** = Hybrid timeflow 가중치 (낮을수록 DFT/Tonnetz 거리 순수 반영)  
> **ow** = octave_weight · **dw** = duration_weight

---

## 들어볼 순서 (권장)

1. **v0** — 원곡 기준
2. **v1 → v2 → v3 → v4** — 파이프라인 단계별 개선 (JS 0.034 → 0.011)
3. **v5** — 수치 절대 최저 (원곡 거의 모사)
4. **vD** — 위상 보존 + 의도적 변주 (다른 느낌의 음악)
5. **vH** — Tonnetz + Complex 레거시 (14분)
6. **v6** — 블록 단위 생성

---

*생성 파이프라인: `tda_pipeline/tools/gen_pipeline_progression_wavs.py`*  
*렌더러: `tda_pipeline/tools/wav_renderer.py` (UprightPianoKW-SF2-20220221)*
