# 세션별 작업 체크리스트 (2026-04-13 기준)

> Control Tower가 관리. 각 세션 완료 시 `[x]`로 표시 + 결과 파일명 기입.
> 세션 시작 시 이 파일을 읽고, 완료 시 업데이트할 것.

---

## A 세션 (실험)

### A-1. 통합 조합 실험 ★★★ 최고 우선
- [x] `ow=0.3 + α=0.0 + 감쇄lag(1~4)` 통합 설정으로 N=20 Algo1 실행
- [x] 기존 개별 결과(ow=0.3 단독, α=0.0 단독, 감쇄lag 단독)와 비교하여 시너지 확인
- [x] 결과 JSON → `step3_data/combined_optimal_results.json`
- [x] 캐시 재계산 필요 여부 확인 (ow/α 변경 시 distance matrix 변경 → pkl 무효)
  - **결과**: K=14 (α=0.0 적용 시 cycle 수 42→14로 감소), JS=0.0569
  - **핵심 발견**: α=0.0이 cycle 수를 크게 줄여 시너지 없음. 개별 최적보다 오히려 악화.
  - **스크립트**: `run_combined_optimal.py` (generate_barcode_numpy 사용, 기존 실험들과 일관성)

### A-2. Per-cycle τ_c 재검증
- [x] N=20으로 per-cycle τ_c 실험 재실행 (현재 N=5 greedy)
- [x] baseline(전체 τ=0.35) 대비 개선율 통계 확인 (p-value)
- [x] 결과 JSON → `step3_data/percycle_tau_n20_results.json`
  - **결과**: baseline JS=0.0460, per-cycle τ_c JS=0.0241, 개선 +47.5%, p<0.001 ★
  - **과적합 없음**: N=5(0.0238) vs N=20(0.0241) 거의 동일 → 통계적으로 확정
  - **스크립트**: `run_percycle_tau_n20.py`

### A-3. Soft activation 아키텍처 확장
- [x] continuous overlap → Transformer 학습 (binary 대비 JS/val_loss 비교)
- [x] continuous overlap → LSTM 학습 (binary 대비 JS/val_loss 비교)
- [x] FC 결과(+64.3%)와 비교 표 작성
- [x] 결과 JSON → `step3_data/soft_activation_all_models.json`
  - **결과**: FC +88.6%(0.0035→0.0004★), Transformer +79.4%(0.0034→0.0007), LSTM -3.5%(부적합)
  - **최적**: FC continuous가 최고 (JS=0.0004, 현재 최고 기록 유지)
  - **스크립트**: `run_soft_activation_all_models.py`

### A-4. 최종 최적 설정 확정 실험
- [x] A-1 + A-2 + A-3 결과를 종합한 "최종 최적 설정" 결정
- [x] 최종 설정으로 Algo1 + Algo2(FC) N=20 실행
- [x] 기존 최고 기록(JS 0.0004, 개선 F) 대비 개선 여부 확인
- [x] 결과 JSON → `step3_data/final_optimal_results.json`
  - **최종 설정**: Overlap=per-cycle τ_c(K=42, α=0.5 캐시), Algo2=FC+continuous
  - **Algo1 최적**: JS=0.0240±0.0028 (per-cycle τ_c, +48.0%, p<0.001)
  - **Algo2 최적**: JS=0.0004±0.0000 (FC continuous, N=20, 현재 최고 기록 재확인)
  - **스크립트**: `run_final_optimal.py`

---

## D 세션 (보고서)

### 피드백 (1) — §1~§4 반영

#### D-F1-1. §1.2 Tonnetz 최소매칭 범위 한정
- [ ] "파이프라인 핵심"처럼 기술된 부분 → "방향 A(§7.3) 한정"으로 범위 명시
- [ ] 또는 해당 내용 삭제 (피드백 원문: "관련 내용 전부 삭제해줘")

#### D-F1-2. §1.3 악기 설명 수정
- [ ] "서로 다른 두 악기" → "둘 다 피아노 계열" 수정

#### D-F1-3. §2.2 Vietoris-Rips 비유클리드 설명
- [ ] 피드백에서 첨부한 참고 논문 반영 (논문 파일 확인 필요)

#### D-F1-4. §2.4 L_2 거리 수식 크기
- [ ] 수식 크기 키우기 (displaymath 또는 큰 분수 사용)

#### D-F1-5. §2.7 Betti curve similarity 수식 설명
- [ ] 우변 2번째 summand 분모의 각 항 정의 추가

#### D-F1-6. §2.9 inter weight 감쇄 lag 반영
- [ ] W_inter 우변에 lag별 가중치(0.4/0.3/0.2/0.1) 반영한 수식으로 교체
- [ ] 거리 행렬 정의의 if/otherwise 들여쓰기 수정
- [ ] 감쇄 lag 실험 결과(hibari Tonnetz -70%) 수치 추가

#### D-F1-7. §2.11 up to permutation 복잡도 주석
- [ ] N≤8: 전수탐색(N!), N>8: Hungarian 근사(O(N³)) 두 경로 설명
- [ ] hibari(46 cycles)는 항상 근사 경로임을 명시

#### D-F1-8. §2.13 roughness/dissonance 정의 보강
- [ ] roughness 정의 + "rough"의 의미 설명
- [ ] 평균 dissonance 수식 크기 키우기

#### D-F1-9. §3.1 합집합 공집합 수정
- [ ] "합집합도 공집합인 경우에만 전체 pool에서 추출" → 삭제 또는 수정
  - 사실: 활성 cycle이 있으면 합집합은 반드시 비공집합
  - 실제 fallback: flag==0(활성 cycle 없음) → `_sample_avoiding_neighbors()`
- [ ] 합집합 수식 크기 키우기

#### D-F1-10. §4 octave_weight 근거 보강
- [ ] 기존 0.5 설정 → 0.3 최적 튜닝 결과 반영 (A세션 결과 참조)
- [ ] hibari diatonic 7음계 → 옥타브 차이 가중 낮춰야 하는 이유 설명

### 피드백 (2) — §7 반영

#### D-F2-1. §7.1 모듈 목적 정정
- [ ] "위상구조를 복사" → "배치 후 PH 분석했을 때 같은 위상구조가 나오는 모듈 탐색"

#### D-F2-2. §7.1 모듈 간 이행 설명
- [ ] "모듈 간 이행 매끄럽게" 부분 설명 보강 (이해하기 쉽게)

#### D-F2-3. §7.1 tie 정규화 ≠ pitch-only labelling
- [ ] "tie 정규화가 일반적으로 pitch-only labelling"이라는 서술 수정
- [ ] solari에서만 GCD=1이라서 그런 것임을 명시

#### D-F2-4. §7.2 Wasserstein distance 정의 누락
- [ ] §2.10에 Wasserstein distance 나온다고 했는데 실제로 없음 → 정의 추가

#### D-F2-5. §7.2 일반화 테이블 확장
- [ ] Bach Fugue 결과 추가 (tonnetz -54.8%)
- [ ] Ravel Pavane 결과 추가 (frequency 최적)
- [ ] `classical_contrast_results.json` 참조

#### D-F2-6. §7.3 측정 지표 정의 추가
- [ ] note 오차: Tonnetz 거리행렬 간 Frobenius norm (up to perm)
- [ ] cycle 오차: cycle-cycle 거리행렬 간 Frobenius norm (up to perm)
  - ⚠ "Tonnetz 최소매칭 거리"가 아님을 명시
- [ ] DTW 정의 + "선율 유사도를 포착하는 이유" 설명
- [ ] pJS(pitch JS): 새 note pool의 pitch 분포 vs 원곡 pitch 분포

#### D-F2-7. §7.3 DL 재학습 조건 명시
- [ ] "재분배된 note 위에서 DL 재학습" = hibari 원본 중첩행렬 동일 사용 명시

#### D-F2-8. §7.3 new_notes 생성 방식 명시
- [ ] 기존 note 재분배가 아닌, pitch pool에서 N개 **완전 새 pitch 랜덤 샘플**임을 명시

#### D-F2-9. §7.4 segment shuffle/block permute 통합
- [ ] 두 방법이 블록 크기만 다르고 본질적으로 같음을 인정
- [ ] block permute로 일반화하는 서술 검토

#### D-F2-10. §7.4 transition JS 정의
- [ ] transition matrix 구하는 법 + 각 cell 기반 JS 계산 방식 설명

#### D-F2-11. §7.5 ICV 차이 정의
- [ ] ICV 자체는 §2에서 정의됨 → 두 ICV 간 차이를 어떻게 구하는지 추가

#### D-F2-12. §7.5 val_loss 정의
- [ ] val_loss 계산 방식 (cross-entropy 등) + 학습 품질 의미 설명

#### D-F2-13. §7.6 "적당한 차이" 수치화
- [ ] "적당한 차이" → JS의 이론 최댓값(log 2 ≈ 0.693) 기준 몇 %인지로 교체

#### D-F2-14. §7.7 실험 결과 반영
- [ ] per-cycle τ_c 결과 (+48.6%) 반영
- [ ] soft activation → FC 결과 (+64.3%, val_loss 10배↓) 반영
- [ ] 온도 스케일링 T=3.0 결과 (-6.7%) 반영
- [ ] `section77_experiments.json` 참조

#### D-F2-15. §7.8 α grid search 결과 반영
- [ ] α=0.0 최적, α=0.3 최악, α=1.0 degenerate(K=1)
- [ ] `alpha_grid_search_results.json` 참조

#### D-F2-16. §7.1.2 P3 수식 + density 수정
- [ ] P3 수식 수정 (현재 argmedian 전략이나 구현 미확인)
- [ ] density 수치 통일: 0.1684 / 0.160 / 0.201 세 값 중 정확한 값 확인 후 통일
  - ⚠ B세션에서 먼저 코드 확인 필요할 수 있음

#### D-F2-17. §7.1.5 한계 2 삭제
- [ ] "두 악기 간 차이" 관련 한계 삭제 (inst 1/2 모두 피아노)
- [ ] 한계 해결 정리표에서도 해당 항목 삭제

#### D-F2-18. §7.1.6 개선 C/P4 설명 보강
- [ ] 개선 C "동률 시 더 작은 인덱스 선호" → 이해하기 쉽게 풀어쓰기
- [ ] 개선 P4 모듈 PH 계산 설명 → 비전공자도 이해할 수 있게 재작성

#### D-F2-19. §7.1.8 "첫 모듈" 기준 재정리
- [ ] "첫 모듈" = inst1 기준 t∈[0,32) (8분음표 32개, 마디 아님)
- [ ] v4에서는 start_modules=[0,4,8,...,28] 다양한 시작점 테스트
- [ ] inst 기준인지 마디 기준인지 명확히

#### D-F2-20. §7.1.8 첫 모듈 우수성 주의사항
- [ ] inst1만 독주하는 구간이라 단순할 수 있음 → 해석 주의 추가

### 추가 반영 사항 (피드백 외)

#### D-X1. Barcode Wasserstein 주의사항 (§7.1.9 또는 §7.2 Discussion)
- [ ] JS vs W dist 상충 가능성
- [ ] Module-level comparison 한계 (단일 악기)
- [ ] chord 공간 불일치 가능성
- [ ] rate 선택 민감도
- [ ] `step_barcode_results.json` 참조

#### D-X2. Wasserstein 제약 note 재분배 결과 (§7.3)
- [ ] 계수(0.3/0.5/1.0) 무관, cycle 보존 개선 없음 정직 기재
- [ ] scale_major 조합 pJS 0.115★
- [ ] `note_reassign_wasserstein_results.json` 참조

#### D-X3. octave_weight 튜닝 결과 (§4 또는 §3.1)
- [ ] ow=0.3 최적 결과 표 + 해석
- [ ] `tonnetz_octave_tuning_results.json` 참조

---

## 완료 확인 기준

### A 세션 완료 조건
```
모든 A-* 항목이 [x] + 결과 JSON이 step3_data/에 존재
→ Control Tower가 JSON 파일 존재 + git status로 확인
```

### D 세션 완료 조건
```
모든 D-* 항목이 [x] + academic_paper_full.md에 반영
→ Control Tower가 키워드 grep으로 반영 여부 확인
예: "방향 A 한정" grep → D-F1-1 확인
    "Hungarian" grep → D-F1-7 확인
    "per-cycle" grep → D-F2-14 확인
```

---

## 세션 간 의존성

```
A-1 완료 → D-F1-10 (octave_weight 근거)
A-2 완료 → D-F2-14 (per-cycle τ 수치 확정)
A-3 완료 → D-F2-14 (soft activation 수치 확정)
A-4 완료 → D 전체 수치 최종 확정

B세션 density 확인 → D-F2-16 (density 통일)
B세션 P3 구현 확인 → D-F2-16 (P3 수식)
```

---

*마지막 업데이트: 2026-04-14 by A 세션*
