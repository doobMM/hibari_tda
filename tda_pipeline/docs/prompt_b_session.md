# B 세션 프롬프트 (2026-04-14 Control Tower 작성)

> 아래 내용을 B 세션 시작 시 그대로 붙여넣기.

---

B 세션이야. 코드 확인 + 수정 작업 2건이야.
이 2건이 끝나면 D 세션 체크리스트의 마지막 블로킹 항목(D-F2-16)이 해제돼.

체크리스트는 `docs/checklist_0413.md` line 149~153.

---

## B-1. density 수치 통일 ★★ (D-F2-16 블로킹)

### 문제

논문에서 동일한 "density" 개념에 대해 세 가지 다른 수치가 혼용 중:

| 출처 | 값 | 맥락 |
|---|---|---|
| `step3_continuous_results.json` key `C_continuous_thr_0.5` → `density` | **0.1684** | 전체 overlap matrix τ=0.5 이진화 후 ON 비율 |
| 논문 §7.1.2 "P1 prototype density" | **0.160** | `run_module_generation_v3.py` line 327: `(proto_P1 > 0).mean()` |
| 논문 §4.3a "τ=0.5에서의 density" | **0.201** | 출처 불명 — 이전 실험 또는 오기재 |

### 해야 할 것

1. **0.1684 확인**: `step3_continuous_results.json`의 `C_continuous_thr_0.5` density가 어떻게 계산되는지 추적.
   - `run_step3_continuous.py`에서 이 JSON을 생성하는 코드를 찾아줘.
   - density = overlap matrix 전체의 `(matrix > 0).mean()` 인지, 아니면 다른 계산인지.

2. **0.160 확인**: `run_module_generation_v3.py` line 327에서 `(proto_P1 > 0).mean()`.
   - `proto_P1`은 `make_P1(overlap_full)` (line 325)의 결과.
   - `make_P1`이 뭘 하는지 확인. 아마 32×K 모듈 프로토타입을 만드는 것 같은데, 전체 행렬과 범위가 다르면 density가 다를 수 있어.
   - 0.160 = **모듈(32 timepoints) 기준 density**이고, 0.1684 = **전체(1088 timepoints) 기준 density**일 수 있어.

3. **0.201 추적**: 논문 §4.3a에서 "τ=0.5에서 density=0.201"이라고 기재된 곳을 `academic_paper_full.md`에서 찾아줘. 그게 어디서 온 값인지:
   - 혹시 τ=0.5가 아니라 다른 τ에서의 값인지 (JSON에서 `C_continuous` 즉 τ 미적용 density는 0.4119)
   - 혹시 이전 버전 실험(refine 버그 수정 전)의 값인지
   - 확인 불가하면 "0.201은 출처 미확인, 현재 코드 기준 0.1684(전체) / 0.160(모듈)"으로 결론.

4. **결론 문서화**: 확인 결과를 `checklist_0413.md` D-F2-16 항목에 기록. 예:
   ```
   - 0.1684 = 전체 overlap matrix(1088×K) τ=0.5 이진화 후 ON 비율
   - 0.160 = P1 모듈 프로토타입(32×K) 기준 density
   - 0.201 = [확인 결과 기입]
   → 논문에서 각각의 맥락을 명시하면 세 값 모두 정당하게 공존 가능.
     또는 0.201이 오류라면 삭제.
   ```

### 참조 파일

- `overlap.py` line 57~86: `build_activation_matrix()` — density의 원천
- `overlap.py` line 203~239: `build_overlap_matrix()` — 이진화 로직
- `run_step3_continuous.py`: JSON 생성 스크립트
- `run_module_generation_v3.py` line 315~327: P1 prototype density 계산
- `docs/step3_data/step3_continuous_results.json` line 155: density=0.1684

---

## B-2. P3 수식 구현 확인 ★★ (D-F2-16 블로킹)

### 문제

논문에 P3(argmedian 전략)이 정의되어 있는데, `step71_improvements.json`에 P3 결과가 없음. `run_module_generation_v3.py`에서도 P1, C, D, C+D, P4, P4+C만 실행하고 **P3는 호출하지 않음** (line 324~389 확인 완료).

### 해야 할 것

1. **P3 구현 여부 확인**: 코드베이스 전체에서 `P3`, `argmedian`, `median_prototype` 같은 키워드를 검색.
   - 구현이 있으면: 왜 v3에서 호출하지 않았는지 확인
   - 구현이 없으면: 논문 정의만 존재하고 실험은 미실시

2. **결론 문서화**: `checklist_0413.md` D-F2-16 항목에 기록. 예:
   ```
   P3 구현 상태: [구현됨/미구현]
   → 논문에 "[P3는 정의만 제시하고 실험은 미실시]" 주석 추가 필요 여부: [예/아니오]
   ```

### 참조 파일

- `run_module_generation_v3.py` line 324~389: 실행되는 전략 목록 (P3 없음)
- `docs/step3_data/step71_improvements.json`: 결과에 P3 키 없음
- `academic_paper_full.md`: P3 정의 위치 확인 필요

---

## 세션 완료 시 해야 할 것

1. `docs/checklist_0413.md`의 D-F2-16 항목을 업데이트:
   - `[TODO]` → `[x]` + 확인 결과 기입
   - 또는 D 세션에 전달할 구체적 지시사항 기입
2. D 세션에서 논문을 최종 수정할 수 있도록 **정확한 수치와 권고사항**을 남겨줘.
