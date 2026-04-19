# 2026-04-19 세션 B 피드백 코드 조사 (8건)

## 4) 4.1 거리함수별 cycle 평균 크기(포함 note 수)
- 근거: `cache/metric_{frequency,tonnetz,voice_leading,dft}.pkl`의 `cycle_labeled` 길이 직접 집계.
- frequency: K=1, 평균 4.000 (min=4, max=4)
- tonnetz: K=47, 평균 6.277 (min=4, max=15)
- voice_leading: K=19, 평균 4.632 (min=4, max=9), dft: K=17, 평균 4.824 (min=4, max=7)

## 12) "hibari도 tie 정규화" 문장 사실관계
- §4.x 재현 스크립트 `run_dft_gap0_suite.py`의 `setup_hibari()`는 pitch-only/tie 정규화 없이 진행 (`build_note_labels(inst1_real[:59])`).
- 해당 경로 hibari note label은 N=23, duration set={1,2,5,6}로 유지됨(정규화 안 됨).
- 반면 `run_any_track.py` 경로는 `pitch_only_notes()`로 duration을 1로 고정(hibari N=17, dur={1}).
- 결론: "hibari도 정규화"는 실험 경로별로 다름(§4.x 기준으로는 불일치).

## 16) OM 구조 설명과 note 재분배 시 cycle note 개수
- 방향 A 실행은 `run_direction_a_ablation.py`에서 기존 `ov`/`cl`(OM, cycle_labeled)을 그대로 사용.
- `find_new_notes()`는 note를 1:1 재매핑하고(`note_reassign.py`), `note_mapping`도 원 인덱스 유지.
- 즉 cycle의 구성 cardinality(몇 개 note로 이루어졌는지)는 보존되고, 실제 바뀌는 것은 각 label의 pitch/duration 값.
- 해석: "OM 구조 동일, note만 교체" 서술은 구현과 합치.

## 18-4) 5.5 Algorithm 1/2 baseline 재분배 방식과 range
- Algo1 baseline은 `run_baseline()`에서 원 notes_label 그대로 실행(재분배 없음, pitch range 파라미터 미적용).
- Algo1 비교 실험의 재분배는 wide 고정(`PITCH_RANGE=(48,84)`) + matching mode(ascending/tonnetz_nearest) 비교.
- Algo2 baseline(`note_reassign_dl_results.json`)도 원곡 학습(`baseline_lstm/transformer`)으로 재분배 없음.
- Algo2 재분배 실험은 wide(48–84)와 vwide(40–88) 둘 다 존재하나, 본문 표 값은 wide 행을 사용한 구성.

## 21) 5.8.0 diatonic 지속 활성 해석이 frequency 기반인지
- per-cycle τ 실험 코드(`run_dft_phase2_gap0_suite.py`, `run_percycle_tau_dft_alpha025.py`)는 metric을 DFT로 고정.
- 결과 JSON은 τ profile/JS 통계만 저장하며 "diatonic 핵심음 cycle" 자동 라벨링 로직은 없음.
- 따라서 해당 문장은 frequency 거리 기반 정량 확인이라기보다, DFT-cont activation을 보고 붙인 정성 해석에 가깝다.
- 별도 검증하려면 cycle별 note 집합→PC 해석 스크립트를 추가해야 함.

## 22-1) greedy per-cycle τ에서 나머지 τ 고정 방식
- 구현은 `taus=[0.35]*K`로 시작 후, cycle 0→K-1 순서 1-pass coordinate descent.
- cycle c 탐색 시 나머지는 "현재까지 확정된 taus 벡터"로 고정(후속 cycle은 아직 0.35).
- 즉 질문처럼 순서/초기값 의존성이 존재하며, 초기 고정값은 0.35.
- 재현성은 seed 규칙으로 고정되지만, global optimum 보장은 없음.

## 26) 6.1 모듈 note 수(45~60) vs chord-height 합(109)
- 32-step chord-height 패턴 합은 109가 맞음.
- 하지만 `algorithm1_optimized()`는 note duration만큼 미래 `inst_len[t]`를 감소시켜(onset 슬롯 차감) 실제 onset 수를 줄임.
- 그래서 모듈 note 수는 109보다 작아지며, 실측 JSON에서 `mod_n_notes`가 주로 45~60 범위.
- 동일 문서의 "100여 개" 서술은 sustain 차감 로직과 충돌 소지 있음.

## 18-7) fig_ref_pjs_diagram DL 박스 FC 추가
- 수정: `docs/figures/make_ref_pjs_diagram.py`의 라벨을 `(FC / LSTM / Transformer)`로 변경.
- 재빌드: `python docs/figures/make_ref_pjs_diagram.py` 실행 완료.
- 산출물: `docs/figures/fig_ref_pjs_diagram.png` 갱신(2026-04-19 18:39 KST).
- md/tex 본문 파일은 수정하지 않음.
