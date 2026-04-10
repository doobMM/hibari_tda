# DEBUG LOG — refine_connectedness upper-triangular 누락 버그

## 발견일: 2026-04-10

## 증상
- hibari 에서 chord+refine 경로와 direct note 전이 경로의 nonzero cell 수가 불일치
- 수정 전: chord+refine 120쌍 vs direct 136쌍 (16쌍 누락 = 12%)
- 누락된 쌍은 모두 **두 악기에 걸친 pitch 쌍** (예: pitch 55 inst2 — pitch 81 inst1)

## 원인

### 위치
- 원본: `WK14/util.py:142` (사용자가 2025-03-28 추가한 코드)
- 리팩토링: `tda_pipeline/weights.py:refine_connectedness_fast` (동일 로직의 행렬 버전)

### 원본 코드
```python
# util.py:142
if note_j >= note_i:  # 250328 1747 추가된 부분
    weight_mtrx_refined.loc[note_i, note_j] += weight
```

### 문제
`refine_connectedness` 는 chord-level weight matrix 를 note-level 로 확장하는 함수.
chord i 에 속한 note_a 와 chord j 에 속한 note_b 를 연결해야 하는데,
`if note_j >= note_i` 조건이 upper triangular 만 채우도록 제한.

**chord 번호 i < j 이지만 note 번호 note_a > note_b 인 경우**:
- chord i→j 전이는 upper tri 에 있음 (i < j)
- 하지만 refine 에서 note_a→note_b 를 기록할 때 note_a > note_b 이면 스킵됨
- 반대 방향 (chord j→i → note_b→note_a) 은 chord weight matrix 에서 이미 upper tri 변환 때 합산되어 chord j→i 전이 기록이 사라짐

**결과**: chord 번호 순서와 note 번호 순서가 역전되는 쌍이 누락.

### 리팩토링 버전에서도 동일
```python
# weights.py (수정 전)
W_upper = np.triu(W_upper)      # chord 를 먼저 upper tri 로
refined = E.T @ W_upper @ E     # refine
refined = np.triu(refined)      # note 도 upper tri 로
```
E^T @ W_upper @ E 연산에서 동일한 누락 발생 (행렬 곱의 특성상 자동으로 재현).

## 수정

### weights.py (수정 후)
```python
# chord weight 를 대칭 행렬로 만든 뒤 refine, 마지막에만 upper tri 추출
W_sym = W + W.T
np.fill_diagonal(W_sym, np.diag(W))
refined = E.T @ W_sym @ E       # 전체 행렬에서 연산
refined = np.triu(refined)      # 마지막에만 upper tri
```

### 검증
- hibari 수정 전: chord 120 vs direct 136 (16쌍 누락)
- hibari 수정 후: chord **136** vs direct **136** (누락 0)
- merry christmas 수정 전: chord 88 nonzero
- merry christmas 수정 후: chord **976** nonzero (11배 증가)

## 영향 범위
- `tda_pipeline/weights.py:refine_connectedness_fast` — 수정 완료
- `WK14/util.py:refine_connectedness` — 원본, 미수정 (참조용 보존)
- **이 버그에 영향을 받은 모든 실험 결과를 재실행해야 함**:
  - hibari 의 모든 metric cache (cache/metric_*.pkl)
  - 모든 JS divergence 수치
  - 모든 overlap matrix
  - §3.1, §3.3a, §3.4, §3.4a, §3.6, §7.1 결과 전부

## 비고
- 이 버그는 보고서(논문)에는 기재하지 않음 (내부 디버깅 기록)
- hibari 처럼 chord 수가 적은 곡 (14개) 에서는 영향이 12% 수준으로 제한적
- merry christmas 처럼 chord 수가 많은 곡에서는 영향이 더 심각했을 가능성
