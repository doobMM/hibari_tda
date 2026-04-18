# 세션 D — Task 44: §6.4 FC 서술 교체 + §6.5 ±std + §6.6.3 메타 보강

## 배경

Task 42 (커밋 `901eab0`) N=5 재검증에서 §6.4 FC 시간 재배치의 **의외 발견**:

- pitch_js: 재배치 전·후 거의 동일 (≈ 0.0009) → 시점 독립성 유지 ✓
- **DTW: 재배치 조건에서 +30~48% 증가** (매우 큼)

현재 Task 41까지의 §6.4 FC 서술은 **"시간 재배치로 선율을 바꾸는 것이 구조적으로
불가능하다"** 로 쓰여 있음. 이는 **pitch 분포 기준**일 때만 참이며, **DTW 기준으로는
선율(pitch 순서)이 크게 바뀜**. 실제로는 **"pitch 분포 유지 + 선율 순서 변화"**의
이상적 변주 특성. 서술 교체 필요.

## 필수 참조 파일

### 읽을 것

- `memory/project_task42_nrepeat_verify_findings_0417.md` — Task 42 결과 + 교체안
- JSON:
  - `docs/step3_data/temporal_reorder_fc_dft_gap0_n5.json` — T42-1 FC 재배치 N=5
  - `docs/step3_data/harmony_fc_dft_gap0_n5.json` — T42-2 FC 화성 제약 N=5
  - `docs/step3_data/harmony_lstm_dft_gap0_n5.json` — T42-3 LSTM 화성 제약 N=5
- 현재 md:
  - `docs/academic_paper_portfolio (short).md` §6.4 / §6.5 / §6.6.3
  - `docs/academic_paper_full.md` 동일

### 수정 대상

- `academic_paper_full.md`
- `academic_paper_portfolio (short).md`

### 금지

- `CLAUDE.md` 수정
- 기존 JSON 덮어쓰기

## 작업 범위 (3개 항목)

### ① §6.4 FC 서술 교체 — **필수**

현재 (short.md / full.md):

> FC: 각 시점 $t$의 cycle 활성 벡터를 독립 처리하므로, OM 행 순서가 바뀌어도 각 시점의
> 출력 분포는 불변이다. pitch JS는 전략에 무관하게 일정하여 시간 재배치로 선율을
> 바꾸는 것이 **구조적으로 불가능**하다.

### 권장 교체안 (short.md)

> FC: 각 시점 $t$의 cycle 활성 벡터를 독립 처리하므로, OM 행 순서가 바뀌어도 **pitch
> 분포는 불변**이다 (pitch JS ≈ $0.0009$, 재배치 전략에 무관). 그러나 pitch 시퀀스의
> 순서는 OM 재배치에 직접 대응하므로 **DTW는 재배치 조건에서 $+30 \sim +48\%$ 증가**
> 한다 (실측, N=5). 즉 FC는 "**같은 pitch 분포를 유지한 채 선율의 시간 순서만 바꾸는**"
> 변주 생성에 구조적으로 적합하며, 이는 §6.6의 모델 선택 시 재고할 만한 특성이다.

### 권장 교체안 (full.md, 수치 더 상세)

Short 교체안 + 각주/실측 표:

| 전략 | pitch JS | DTW Δ (vs baseline) |
|---|---|---|
| baseline | 0.00091 | — |
| segment_shuffle | ≈ 0.00091 | +30~48% |
| block_permute(32) | ≈ 0.00091 | +30~48% |
| markov (τ=1.0) | 소폭 상승 | +30~48% |

(출처: `temporal_reorder_fc_dft_gap0_n5.json`, N=5. 정확한 값은 JSON 재확인 후 기재.)

그리고 각주로: "이 발견은 §6.6.2에서 DFT-FC가 Transformer보다 ref pJS 낮은 이유 중
하나를 구성한다 — FC의 pitch 분포 보존 특성이 변주 품질에 기여."

### ② §6.5 표 ±std 추가 — **선택**

§6.5 Algorithm 2 결과 표(Transformer + FC + LSTM × original/baseline/scale_major/scale_penta)의
수치에 **Task 42 N=5 기반 ±std 추가**. short.md는 간결하게 주요 값만, full.md는 전체.

### 출처 JSON

- `harmony_fc_dft_gap0_n5.json` (FC)
- `harmony_lstm_dft_gap0_n5.json` (LSTM)
- Transformer 값은 기존 (Task 40 T40-2 또는 Tonnetz 기존 — §6.3 "본 장은 Tonnetz 기반"
  선언에 맞춰 Tonnetz 결과 유지 우선).

### 원칙

- 표의 "vs_orig pJS" / "vs_orig DTW" / "vs_ref pJS" / "val_loss" 열에 ±std 추가.
- scale_major 최적 결론은 변경 없음 (Task 42 재검증).

### ③ §6.6.3 메타 통찰 — FC 특성 보강 — **선택**

§6.6.3 메타 통찰(Task 41에서 신설)에 다음 취지 **한 단락 추가**:

> **FC의 pitch 분포 유지 특성 — §6.4 재발견.** §6.4 재검증에서 FC는 OM 재배치 하에
> pitch 분포가 불변이면서 DTW가 크게 변하는, "pitch 유지 + 선율 순서 변화"의 변주
> 생성에 이상적인 구조적 특성을 가진다. 이는 §6.6.2에서 DFT-FC가 DFT-Transformer보다
> `ref pJS`가 낮은 이유를 부분 설명한다. 그럼에도 §6.6 전체에서 Tonnetz-Transformer가
> 여전히 최적인 이유는, scale 제약 기반 재분배의 효과가 **OM 재배치가 아닌 note 선택
> 단계에서** 주로 발현되기 때문이다 — 이는 scale과 Tonnetz의 화성적 공명 때문으로,
> §6.6.3의 "거리 함수 × 목적 정합성" 논지를 강화한다.

## 실행 순서 권장

```
① §6.4 FC 서술 교체 (short + full)
    ↓
② §6.5 표 ±std (short 간결, full 상세)
    ↓
③ §6.6.3 메타 보강 (short 간결, full 상세)
    ↓
컴파일/검수
```

## JSON 원본 대조 규칙

- FC DTW 증가율 구체 수치는 `temporal_reorder_fc_dft_gap0_n5.json` 직접 대조.
- §6.5 표 수치는 3개 JSON 각각에서 확인.

## 커밋 지침

단일 커밋 권장:

```
docs(paper): Task 44 §6.4 FC 서술 교체 + §6.5 ±std + §6.6.3 메타 보강

Task 42 N=5 재검증의 FC 의외 발견 반영:
- §6.4 FC: "구조적으로 불가능" → "pitch 분포 유지 + DTW +30~48% 실측"으로 교체
  FC가 "같은 pitch 분포 + 다른 선율 순서" 변주에 이상적 특성을 가짐 명시
- §6.5 표: Task 42 N=5 기반 ±std 추가 (FC/LSTM)
- §6.6.3 메타 통찰: FC 특성 한 단락 추가 — §6.6.2 DFT-FC 우수성 해석 연결

참조: memory/project_task42_nrepeat_verify_findings_0417.md
      docs/step3_data/temporal_reorder_fc_dft_gap0_n5.json
      docs/step3_data/harmony_fc_dft_gap0_n5.json
      docs/step3_data/harmony_lstm_dft_gap0_n5.json

short.md / full.md 양쪽 반영.
```

## 검수 체크리스트

- [ ] short.md §6.4 "구조적으로 불가능" 문자열 0건
- [ ] short.md / full.md §6.4 DTW +30~48% 실측 수치 존재
- [ ] §6.5 표에 ±std 존재 (최소 scale_major 행)
- [ ] §6.6.3에 FC 특성 보강 단락 존재 (선택 항목이면 스킵 가능)
- [ ] JSON 원본과 수치 일치

## 예상 소요

- ① §6.4: 30분 (두 md 교체)
- ② §6.5: 30분
- ③ §6.6.3: 15분
- **총 1시간 내외**. 단독 Task 41 대비 작음.

## 세션 간 병렬 안전성

- 본 Task는 `academic_paper_*.md` 전용.
- 세션 A Task 43 LaTeX 동기화와 **순서 의존** — 본 Task 44 완료 후 Task 43 착수 권장 (최신 md를 기준으로 LaTeX 작업).
- 단 Task 43을 이미 시작했다면 §6.4 FC 부분만 LaTeX에서도 별도 패치.

## Task 44 완료 후 세션 E 루틴

1. 커밋 확인
2. memory 신설 또는 Task 42 memory에 반영 결과 추가
3. `CLAUDE.md` Task 44 ✓
4. **Task 43 LaTeX 동기화 착수 권장** (이제 md 최종 확정 상태)

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음** (서술 교체 + 수치 정합 필요).
