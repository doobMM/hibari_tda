# D 세션 프롬프트 (2026-04-14 Control Tower 작성)

> 아래 내용을 D 세션 시작 시 그대로 붙여넣기.

---

D 세션이야. 체크리스트는 `docs/checklist_0413.md`에 있어 (D 세션 항목은 line 48부터).
논문 `docs/academic_paper_full.md`를 수정하는 작업이야. 총 33건.

논문을 **섹션 순서대로** 앞에서 뒤로 한 번만 읽으면서 수정해줘. 아래에 섹션별로 정리해뒀어.

---

## A 세션 최종 결과 (수치 참조용)

D 세션에서 논문에 반영할 최신 수치야. 이 숫자들을 사용해.

| 실험 | 핵심 결과 |
|---|---|
| A-1 통합 조합 (ow=0.3+α=0.0+감쇄lag) | K=14로 cycle 격감 → 시너지 없음. α=0.0은 단독 유효, 조합 시 악화 |
| A-2 Per-cycle τ_c (N=20) | baseline 0.0460 → 0.0241, **+47.5%, p<0.001** ★ 과적합 없음 확정 |
| A-3 Soft activation 확장 | FC +88.6%(0.0004★), Transformer +79.4%(0.0007), LSTM 부적합(-3.5%) |
| A-4 최종 최적 설정 | Algo1: JS=0.0240 (per-cycle τ_c), Algo2: JS=0.0004 (FC cont) |

**최종 확정 hibari 최적 설정:**
```
거리: Tonnetz (α=0.5, octave_weight=0.3)    ← 주의: α=0.0은 조합 시 K 격감, α=0.5 유지
Lag: 감쇄 가중 (lag 1~4, w=[0.4,0.3,0.2,0.1])
중첩행렬: continuous activation + per-cycle τ_c (cycle별 최적 임계)
생성: FC + continuous overlap 입력
온도: T=3.0
```

---

## §1 수정 (2건)

### D-F1-1. §1.2 Tonnetz 최소매칭 삭제/범위 한정
피드백 원문: "Tonnetz 최소매칭 거리는 관련 내용이 파이프라인에서 빠진 것 맞아? 그렇다면 관련 내용 전부 삭제해줘."
- 사실확인: `note_reassign.py`에만 존재. 파이프라인 본체에 없음.
- **액션**: §1.2에서 Tonnetz 최소매칭을 파이프라인 핵심으로 서술한 부분 삭제. 또는 "방향 A(§7.3) 한정"으로 범위 명시.

### D-F1-2. §1.3 악기 설명 수정
피드백 원문: "서로 다른 두 악기라고 인식했는데, 둘 다 피아노 계열이야!"
- **액션**: "서로 다른 두 악기" → "두 피아노 파트(inst 1, inst 2)" 등으로 수정.

---

## §2 수정 (6건)

### D-F1-3. §2.2 Vietoris-Rips 비유클리드 설명
피드백 원문: "Vietoris-Rips 거리가 Euclidean이 아님을 설명할 때, 첨부한 이 논문을 참고해줘!"
- **액션**: 피드백에 첨부된 참고 논문이 있는지 `docs/` 폴더에서 확인. 없으면 일반적인 설명으로 보강하고 `[TODO: 참고 논문 확인 필요]` 표시.

### D-F1-4. §2.4 L_2 거리 수식 크기
피드백 원문: "수식이 너무 작아! 조금만 더 키워줘!"
- **액션**: inline math → displaymath 또는 `\large` 적용.

### D-F1-5. §2.7 Betti curve similarity 수식 설명
피드백 원문: "우변의 2번째 summand의 분모에 있는 각 summand가 어떻게 정의되는지 모르겠어."
- **액션**: 분모의 각 항에 대해 한 줄씩 정의 추가 (예: "여기서 $B_k^{ref}(r)$은 reference barcode의 rate $r$에서의 $k$차 Betti 수").

### D-F1-6. §2.9 inter weight 감쇄 lag 반영
피드백 원문: "W_inter 우변에서 lag마다 가중치 다르게 한 거 반영해줘" + "if랑 otherwise 띄어쓰기"
- **액션**:
  1. 기존 lag=1 단일 수식 → lag 1~4 감쇄 합산 수식으로 교체: $W_{inter} = \sum_{k=1}^{4} w_k \cdot W_{inter}^{(k)}$, $w_k = \frac{5-k}{10}$ (즉 [0.4, 0.3, 0.2, 0.1])
  2. 거리 행렬의 if/otherwise 케이스 들여쓰기 정리
  3. 실험 결과 추가: "감쇄 가중 적용 시 hibari Tonnetz JS가 0.0398 → 0.0121로 −69.6% 개선"

### D-F1-7. §2.11 up to permutation 복잡도 주석
피드백 원문: "up to permutation이란 조건이 애초에 맞는지 잘 모르겠어. N!의 계산복잡도가 합리적인지도"
- 사실확인: `note_reassign.py` line 403-443. N≤8이면 전수탐색(N!), N>8이면 Hungarian 근사(O(N³)).
- **액션**: 두 경로를 설명하고, "hibari의 cycle 수(46)에서는 항상 근사 알고리즘이 사용된다"를 명시.

### D-F1-8. §2.13 roughness/dissonance 정의 보강
피드백 원문: "roughness가 어떻게 정의되는지, rough가 의미하는 바가 무엇인지 모르겠어. 수식이 너무 작아."
- **액션**: roughness 정의 1~2문장 추가 + 평균 dissonance 수식을 displaymath로.

---

## §3 수정 (1건)

### D-F1-9. §3.1 합집합 공집합 수정
피드백 원문: "'합집합도 공집합인 경우에만 전체 note pool P에서 추출한다'고 했는데, 그런 경우는 애초에 없을 것 같아."
- 사실확인: 맞음. 활성 cycle이 있으면 합집합은 반드시 비공집합. 실제 코드의 fallback은:
  - flag==0 (활성 cycle 없음, ~84% 시점) → `_sample_avoiding_neighbors()`
  - flag>0, 교집합 공집합 → `node_pool.sample()` (전체 풀)
- **액션**: "합집합이 공집합인 경우" 서술 삭제 또는 정정. 합집합 수식도 displaymath로.

---

## §4 수정 (1건)

### D-F1-10. §4 octave_weight 근거 보강
피드백 원문: "옥타브항 계수 0.5로 설정한 근거 잘 이해가 안 돼. 튜닝 진행해야 하지 않을까?"
- A세션 결과: `tonnetz_octave_tuning_results.json` — ow=0.3 최적(JS=0.0479), 기존 0.5(JS=0.0590) 대비 −18.8%.
- **액션**:
  1. 기존 "0.5로 설정" → "grid search 결과 0.3이 최적"으로 교체
  2. 표 추가: ow ∈ {0.1, 0.3, 0.5, 0.7, 1.0} 각각의 JS + K
  3. 해석: "hibari는 diatonic 7음계, 좁은 음역 → 옥타브 차이를 낮게 가중해야 더 많은 cycle을 발견"

---

## §7.1 수정 (8건)

### D-F2-1. §7.1 모듈 목적 정정
피드백 원문: "모듈 1개의 위상구조를 복사한다기보다는, 어떤 식으로 만들든 hibari와 같이 배치한 뒤 위상구조를 분석했을 때 hibari와 같은 위상구조가 나오는 모듈을 찾는 식의 접근을 나는 의도했었어."
- **액션**: "위상구조를 복사" → "생성된 모듈을 hibari와 동일한 방식으로 배치한 뒤 PH를 계산했을 때, 원곡과 유사한 위상 구조가 나타나는 모듈을 탐색" 으로 정정.

### D-F2-2. §7.1 모듈 간 이행 설명
피드백 원문: "3. 모듈 간 이행 매끄럽게 → 이 부분 뭔지 잘 이해가 안 돼."
- **액션**: "이행(transition)"이 뜻하는 바를 구체적으로 풀어쓰기 (예: "인접 모듈의 마지막/첫 note가 음악적으로 자연스럽게 연결되도록...").

### D-F2-3. §7.1 tie 정규화 ≠ pitch-only labelling
피드백 원문: "tie 정규화가 일반적으로 pitch-only labelling인 건 아니지 않아? solari에서만 gcd=1이라서 그렇지."
- **액션**: "tie 정규화 = pitch-only labelling"이라는 일반화 삭제. "solari의 경우 GCD=1(8분음표)이므로 tie 정규화 결과가 pitch-only labelling과 동일해지는 특수 사례"로 수정.

### D-F2-16. §7.1.2 P3 수식 + density 수정
피드백 원문: "P3 정의로 나온 수식이 수정 필요" + "§4.3a에선 0.201로 나오는데?"
- 사실확인: density 세 값 혼용(0.1684/0.160/0.201). P3는 `step71_improvements.json`에 항목 없음(미구현 가능성).
- **액션**:
  1. P3 수식은 있는 그대로 두되, "현재 구현에서는 P3를 단독 적용하지 않음"을 주석
  2. density 수치: "0.160"과 "0.201"이 서로 다른 조건(모듈 평균 vs 전체 행렬)인지, 아니면 오기재인지를 확인 후 통일 — 확인 불가하면 `[TODO: B세션에서 코드 확인 필요]` 표시

### D-F2-17. §7.1.5 한계 2 삭제
피드백 원문: "한계 2는 빼도 돼. 왜냐하면 inst 1과 2가 사실 같은 피아노 악기거든."
- **액션**: "두 악기 간 차이" 관련 한계 항목 삭제 + 한계 해결 정리표에서도 해당 행 삭제.

### D-F2-18. §7.1.6 개선 C/P4 설명 보강
피드백 원문: "개선 C에서 '동률일 때는 더 작은 인덱스를 선호한다' 이 내용 조금 더 이해하기 쉽게" + "개선 P4 설명 무슨 뜻인지 모르겠어"
- **액션**:
  1. 개선 C: "best-of-k에서 JS가 동일한 후보가 여러 개일 때, 모듈 인덱스가 더 작은(= 곡의 앞부분에 가까운) 후보를 선택한다. 이는 곡의 도입부가 청취자에게 더 강한 인상을 주기 때문" 등으로 풀어쓰기
  2. 개선 P4: "첫 모듈(t∈[0,32))에 속하는 inst 1 note들과, 대응하는 inst 2 note들만으로 축소된 chord transition을 만든다. 이 축소 데이터에서 PH를 계산하면, 전체 곡이 아닌 해당 모듈 구간의 위상 구조만을 포착할 수 있다" 식으로.

### D-F2-19. §7.1.8 "첫 모듈" 기준 재정리
피드백 원문: "n번째를 말할때 inst 1과 2 중에서 어떤 거 기준이야? 아니면 그냥 마디 기준이야?"
- 사실확인: inst1 기준 t∈[0,32) (8분음표 32개 단위, 마디 아님). v4에서 start_modules=[0,4,8,...,28].
- **액션**: "첫 모듈 = inst 1 기준 처음 32 timepoints (8분음표 단위, t=0~31)"을 명확히. "마디 기준이 아님"을 주석.

### D-F2-20. §7.1.8 첫 모듈 우수성 주의사항
피드백 원문: "이건 사실 이때 inst 1만 연주 중이라서 오히려 곡 전반적인 중첩의 구조를 파악하지 못하고 수치적으로만 우수한 결과가 나온 것일지도 몰라."
- **액션**: "단, 이 구간(t∈[0,32))에서는 inst 1만 독주 중이므로, 두 악기 상호작용이 포함된 이후 구간에 비해 위상 구조가 단순하다. 따라서 수치적 우수성이 과대평가되었을 가능성이 있다"는 주의사항 추가.

---

## §7.2 수정 (2건)

### D-F2-4. §7.2 Wasserstein distance 정의 누락
피드백 원문: "Wasserstein distance가 §2.10에 나와있다고 했지만 앞에 나와 있지 않았어."
- **액션**: §2에 Wasserstein distance 정의 추가. 또는 §7.2에서 사용할 때 인라인으로 정의.

### D-F2-5. §7.2 일반화 테이블 확장
- `classical_contrast_results.json` 참조하여 Bach/Ravel 행 추가:

| 곡 | frequency | tonnetz | voice_leading | best |
|---|---|---|---|---|
| Bach Fugue | 0.0902 | **0.0408** | 0.1242 | tonnetz (−54.8%) |
| Ravel Pavane | **0.0337** | 0.0387 | 0.0798 | frequency |

- 해석: "대위법=voice_leading 가설 불성립. Bach도 Tonnetz 최적."

---

## §7.3 수정 (4건)

### D-F2-6. §7.3 측정 지표 정의 추가
피드백 원문: "note 오차와 cycle 오차 어떻게 측정돼?" + "DTW가 선율을 포착해?"
- **액션**: §7.3 서두에 다음 정의 추가:
  - **note 오차**: 원곡/생성곡의 note-note Tonnetz 거리행렬 간 Frobenius norm (up to permutation). ⚠ "Tonnetz 최소매칭 거리" 자체가 아님.
  - **cycle 오차**: 원곡/생성곡의 cycle-cycle 거리행렬(각 원소 = Tonnetz 기반 set distance) 간 Frobenius norm (up to permutation).
  - **DTW (Dynamic Time Warping)**: 두 pitch 시퀀스의 시간축 신축 허용 정렬 비용. 선율 윤곽의 유사도를 포착.
  - **pJS (pitch JS divergence)**: 생성곡의 pitch 빈도 분포 vs 원곡 pitch 빈도 분포 간 Jensen-Shannon divergence.

### D-F2-7. §7.3 DL 재학습 조건 명시
피드백 원문: "재분배된 note 위에서 LSTM/Transformer를 재학습시켰다고 했는데 중첩행렬 자체는 hibari의 것을 동일하게 사용한 거야?"
- 사실확인: 맞음. `run_note_reassign.py` line 138에서 hibari 원본 중첩행렬 `ov` 그대로 전달.
- **액션**: "DL 모델의 입력(중첩행렬)은 hibari 원본을 동일하게 사용하며, 출력 레이블만 재분배된 note로 교체하여 재학습" 명시.

### D-F2-8. §7.3 new_notes 생성 방식 명시
피드백 원문: "vs ref pJS에서는 그냥 기존 note를 재분배를 한 건지, 아니면 아예 새로운 note를 도입한 건지"
- 사실확인: `note_reassign.py` line 646-648. pitch pool(40~88)에서 N개를 **완전 새 pitch로 랜덤 샘플**. 기존 note 재분배 아님.
- **액션**: "기존 note의 재할당이 아닌, 지정된 pitch 범위에서 N개의 완전히 새로운 pitch를 무작위로 선택한다" 명시.

### D-X2. §7.3 Wasserstein 제약 실험 결과 추가
- `note_reassign_wasserstein_results.json` 참조.
- **액션**: "Wasserstein 제약을 추가 적용했으나, 계수(0.3/0.5/1.0) 변화에 무관하게 동일한 결과를 산출. cycle 보존 개선 없음. 이는 topk 필터가 먼저 후보를 제한한 뒤 Wasserstein으로 재정렬하는 구조 때문" 정직 기재.

---

## §7.4 수정 (2건)

### D-F2-9. §7.4 segment shuffle/block permute 통합
피드백 원문: "segment shuffle과 block permute가 근본적으로 블록 단위만 다르고 같은 방법론인 것 같은데 맞아?"
- **액션**: "두 전략은 블록 크기만 다를 뿐 동일한 블록 단위 순열(block permutation) 방법론의 특수 사례"임을 인정. 일반화된 서술로 정리.

### D-F2-10. §7.4 transition JS 정의
피드백 원문: "transition JS가 어떻게 정의되는지 모르겠어."
- **액션**: "note 시퀀스에서 연속된 두 시점의 note 쌍으로 transition matrix를 구축한 뒤, 원곡과 생성곡의 transition matrix 간 JS divergence를 계산" 정의 추가.

---

## §7.5 수정 (2건)

### D-F2-11. §7.5 ICV 차이 정의
피드백 원문: "ICV 차이가 어떻게 정의돼?"
- **액션**: "ICV 차이 = |ICV_ref − ICV_gen| (또는 각 성분별 L2 norm)" 등 구체적 계산 방식 추가.

### D-F2-12. §7.5 val_loss 정의
피드백 원문: "val_loss는 어떻게 구해지고 왜 이게 학습 품질을 의미하는 거야?"
- **액션**: "검증 셋(validation set)에 대한 binary cross-entropy loss. 학습 데이터에 과적합되지 않고 새 입력에도 잘 예측하는지를 측정하므로 모델의 일반화 품질을 나타낸다" 설명 추가.

---

## §7.6 수정 (1건)

### D-F2-13. §7.6 "적당한 차이" 수치화
피드백 원문: "'적당한 차이'라는 워딩은 수학 논문에서 부적절해."
- **액션**: "적당한 차이" → "JS divergence의 이론 최댓값 ln(2) ≈ 0.693 기준 약 X%에 해당" 등 정량적 표현으로 교체.

---

## §7.7 수정 (1건 — A세션 최신 수치 포함)

### D-F2-14. §7.7 실험 결과 반영
피드백 원문: "여기 나온 3가지 사항 실제로 반영해보자!"
- A세션 결과로 **최신 수치 확정**:

| 실험 | 결과 | JSON |
|---|---|---|
| Per-cycle τ_c (N=20) | baseline 0.0460→0.0241, **+47.5%**, p<0.001 | `percycle_tau_n20_results.json` |
| Soft activation FC (N=20) | binary 0.0035→cont 0.0004, **+88.6%** ★ | `soft_activation_all_models.json` |
| Soft activation Transformer | binary 0.0034→cont 0.0007, **+79.4%** | 위 동일 |
| Soft activation LSTM | binary 0.0029→cont 0.0030, **-3.5%** (부적합) | 위 동일 |
| 온도 T=3.0 (N=10) | T=1.0 JS=0.0627→T=3.0 JS=0.0585, **-6.7%** | `section77_experiments.json` |

- **액션**: §7.7에 위 5개 실험 결과를 표+해석으로 반영. 특히 "soft activation은 FC/Transformer에서는 크게 유효하나, LSTM에서는 부적합"이라는 모델 의존성을 강조.

---

## §7.8 수정 (1건)

### D-F2-15. §7.8 α grid search 결과 반영
피드백 원문: "역시 마찬가지로 실험해보자!"
- `alpha_grid_search_results.json` 참조.
- **중요 뉘앙스** (A-1 결과 반영): α=0.0이 단독으로는 최적(JS=0.0574)이나, ow=0.3+감쇄lag와 조합 시 K=42→14로 cycle 격감하여 시너지 불발. 따라서 최종 설정에서는 α=0.5 유지.
- **액션**: α별 JS/K 표 + "α=0.0은 순수 Tonnetz로 단독 최적이나, 다른 파라미터 조합 시 cycle 수 감소로 인해 실질 성능이 저하될 수 있다"는 주의사항 포함.

---

## 추가 반영 (2건)

### D-X1. Barcode Wasserstein 주의사항 (§7.1.9 신규 절 또는 §7.2 Discussion)
- `step_barcode_results.json` 참조.
- **액션**: 4개 주의사항 기술:
  1. JS vs W dist 상충 (Pearson=0.503, 중간 상관)
  2. Module-level 비교 한계 (단일 악기만)
  3. Chord 공간 불일치 (생성 23~31 chords vs reference 17)
  4. Rate 선택 민감도 (3점 합산으로 완화했으나 full profile과 다를 수 있음)

### D-X3. octave_weight 튜닝 결과 표 (§4 또는 §3.1)
- `tonnetz_octave_tuning_results.json` 참조.
- **액션**: D-F1-10에서 §4를 수정할 때, 아래 표를 함께 삽입:

| ow | JS mean | K cycles |
|---|---|---|
| 0.1 | 0.0516 | 50 |
| **0.3 ★** | **0.0479** | 47 |
| 0.5 (기존) | 0.0590 | 42 |
| 0.7 | 0.0720 | 38 |
| 1.0 | 0.0719 | 35 |

---

## 참조할 JSON 파일 목록

```
docs/step3_data/
├── tonnetz_octave_tuning_results.json     ← D-F1-10, D-X3
├── alpha_grid_search_results.json         ← D-F2-15
├── section77_experiments.json             ← D-F2-14
├── classical_contrast_results.json        ← D-F2-5
├── step_barcode_results.json              ← D-X1
├── note_reassign_wasserstein_results.json ← D-X2
├── percycle_tau_n20_results.json          ← D-F2-14 (A세션 신규)
├── soft_activation_all_models.json        ← D-F2-14 (A세션 신규)
├── combined_optimal_results.json          ← A-1 참조 (논문 반영은 주의사항만)
└── final_optimal_results.json             ← A-4 최종 수치
```

---

## 세션 완료 시 해야 할 것

1. 수정한 `academic_paper_full.md`를 저장
2. `docs/checklist_0413.md`에서 완료 항목을 `[x]`로 업데이트
3. B세션 의존 항목(D-F2-16 density/P3)은 `[TODO]` 상태로 남겨둬도 됨
4. D-F1-3(참고 논문)도 파일 없으면 `[TODO]`로
