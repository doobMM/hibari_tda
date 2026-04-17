# Claude Handoff — `refine_connectedness` undirected semantics 재점검

작성일: 2026-04-17  
작업 위치: `C:\WK14\tda_pipeline\`

## TL;DR

현재 `refine_connectedness_fast()`의 구현은 pre-bugfix의 **하삼각 누락 버그**는 고쳤지만,  
만약 우리가 원하는 것이

> "module 기반 chord 전이 하나가 unordered note pair `{a,b}`를 만들면 그 pair에 **최대 1번만** 기여"

라는 의미의 **undirected note adjacency**였다면, 지금 구현(`E.T @ W_sym @ E`)은 여전히 **일부 note pair를 과계산**할 가능성이 큽니다.

즉:

1. `OLD = E.T @ W_upper @ E`
   - 명백한 누락 버그가 있었음
2. `CURRENT = E.T @ W_sym @ E`
   - 누락은 복원했지만, shared note / 양방향 매칭 가능한 경우 일부 pair를 2배 셈
3. 우리가 의도한 것이 unordered pair 기준 "존재 여부" 누적이라면
   - `CURRENT`도 최종 정답은 아닐 수 있음

---

## 관련 코드 위치

- 현재 구현: `weights.py`
  - `_build_expansion_matrix()`
  - `refine_connectedness_fast()`
  - `compute_distance_matrix()`
- 진단 스크립트: `diagnose_refine_bug.py`

현재 핵심 구현:

```python
W_sym = W + W.T
np.fill_diagonal(W_sym, np.diag(W))
refined = E.T @ W_sym @ E
refined = np.triu(refined)
```

---

## 배경

원래 chord-level adjacency를 먼저 구한 뒤 note-level로 펼친 이유는:

- hibari가 module 기반 구조를 강하게 가지므로
- 먼저 **module/chord 전이**를 잡고
- 그 전이를 **note pair**로 분해하는 것이 설계 의도였음

따라서 핵심 질문은:

> chord pair `(i,j)`의 weight `w`를 note pair로 펼칠 때,  
> 같은 unordered note pair `{a,b}`가 chord 양쪽에서 모두 실현 가능하면  
> `w`를 1번 넣어야 하는가, 2번 넣어야 하는가?

내 현재 판단은:

- **undirected adjacency**라면 보통 `1번`이 더 자연스럽고
- 현재 `E.T @ W_sym @ E`는 일부 경우 `2번` 넣고 있음

---

## 확정된 사실 1 — pre-bugfix 코드는 실제 누락 버그가 있었음

`diagnose_refine_bug.py` 실행 결과:

```text
OLD non-zero 연결: 220
NEW non-zero 연결: 276
복원된 누락 연결: 56
새로 사라진 연결: 0
값이 변경된 쌍: 136
OLD max: 425.4240
NEW max: 842.4480
```

즉 pre-bugfix는 실제로 일부 note pair를 누락하고 있었음.  
이건 `note_a > note_b`일 때 하삼각으로 떨어져 `np.triu()`에서 버려졌기 때문.

대표 예시:

- `note(5, 6)`: `OLD=0`, `NEW=150.82`
- `note(10, 23)`: `OLD=0`, `NEW=148.00`

이 두 예시는 **복원 자체는 맞는 수정**으로 보임.

---

## 확정된 사실 2 — 현재 구현은 "복원만" 하는 것이 아니라 일부 pair를 더 크게 만듦

추가로 ad-hoc 비교를 수행해서 아래 3개를 대조했음.

### 비교 대상

1. `OLD`
   - `np.triu(E.T @ W_upper @ E)`
2. `CURRENT`
   - `np.triu(E.T @ W_sym @ E)`
3. `DIRECT-UNDIRECTED-ONCE`
   - 각 unordered chord pair `(i,j)`의 weight `w`에 대해
   - chord `i`, `j`가 만들 수 있는 unordered note pair `{a,b}`마다
   - **중복 없이** `+w`를 1번만 더하는 참조 구현

### 결과 (rate=0.3, decayed lag 설정에서 확인)

복원 예시:

```text
note(5, 6):   OLD=0.0   CURRENT=150.82   DIRECT=150.82
note(10,23):  OLD=0.0   CURRENT=148.00   DIRECT=148.00
note(7, 9):   OLD=0.0   CURRENT=147.664  DIRECT=147.664
```

즉 이들은 `CURRENT`가 정확히 원하는 값을 복원한 경우.

하지만 과계산 예시:

```text
note(6,12): CURRENT=294.56, DIRECT=158.08
note(10,10): CURRENT=842.448, DIRECT=425.424
note(6,6): CURRENT=586.72, DIRECT=296.96
```

즉 `CURRENT > DIRECT`인 note pair가 실제로 존재함.

추가 확인:

```text
n_extra_pairs = 34
```

즉 최소 34개의 note pair가 "unordered chord pair당 최대 1회" 기준보다 크게 셈됨.

---

## 왜 과계산이 생기나

현재 수식은 본질적으로:

```text
R_current[a,b]
= w * 1[a∈C_i, b∈C_j]
+ w * 1[a∈C_j, b∈C_i]
```

를 수행함.

이때 unordered pair `{a,b}`가 chord 양쪽에서 모두 실현 가능하면 같은 chord pair `(i,j)` 하나에서 `w`가 2번 들어감.

### 대표 예시: `note(6,12)`

확인된 chord pair 중 하나:

```text
chord 8 = [6, 12, 16, 21]
chord 9 = [6, 12, 19]
W(8,9) = 65.84
```

이 chord pair 하나만 봐도 `{6,12}`는

- `6 ∈ chord8`, `12 ∈ chord9`
- `12 ∈ chord8`, `6 ∈ chord9`

가 둘 다 참.

따라서:

- `DIRECT-UNDIRECTED-ONCE` 해석: `{6,12}`에 `+65.84` 1번
- `CURRENT` 해석: `{6,12}`에 `+65.84 + 65.84 = +131.68`

즉 unordered adjacency 해석이라면 `CURRENT`는 과계산.

---

## diagonal entry가 왜 중요하냐

이건 사용자와 대화 중 핵심으로 떠오른 포인트.

### 예시

chord `A`, `B` 둘 다에 같은 note `n`이 들어 있다고 하자.

그러면 현재 구현은 같은 unordered chord pair 하나에서 diagonal `(n,n)`에 대해:

```text
n in A, n in B
n in B, n in A
```

를 모두 세므로 `2w`가 됨.

하지만 만약 우리가 말하는 undirected adjacency가

> unordered chord event 하나가 unordered note pair `{n,n}`를 만들면 1번만 반영

이었다면 `(n,n)`은 `w`가 맞고 `2w`는 과계산임.

즉 diagonal은 이 semantic mismatch가 가장 뚜렷하게 드러나는 자리.

---

## 의미론적으로 가능한 3가지 해석

### 1. 현재 `CURRENT`를 유지하는 해석

의미:

> unordered chord pair가 note pair를 만들 수 있는 **매칭 경로 수**를 모두 센다

이 경우 `E.T @ W_sym @ E`는 일관적일 수 있음.

문제:

- 사용자의 현재 직감/설계 의도와는 다소 어긋나는 듯함
- diagonal과 shared-note pair가 강하게 부풀 수 있음

### 2. 우리가 더 원했을 가능성이 높은 해석

의미:

> unordered chord pair 하나는 unordered note pair `{a,b}`에 최대 1회만 기여

이 경우 필요한 것은 `DIRECT-UNDIRECTED-ONCE` 타입 구현.

직관:

- chord event 하나를 note-level로 "펼친다"
- 같은 pair가 양쪽에서 보인다고 해서 같은 event를 두 번 세지 않음

### 3. 만약 실제로 directed note adjacency를 원했다면

의미:

> `(5,6)`과 `(6,5)`를 구분해서 센다

이 경우:

- `W_sym`를 쓰면 안 됨
- `np.triu()`도 쓰면 안 됨
- 원래의 full directed chord matrix에서 바로 directed note matrix를 만들어야 함

하지만 현재 논의는 undirected 쪽에 가까워 보임.

---

## 내가 현재 가장 의심하는 결론

사용자 의도를 기준으로 보면:

> **현재 `E.T @ W_sym @ E`는 lower-triangle 누락 버그를 해결했지만,  
> 최종 intended undirected adjacency는 아닐 가능성이 큼.**

즉 다음 형태의 함수가 더 맞을 가능성이 높음:

```text
for each unordered chord pair (i,j) with weight w:
    S = unordered note pairs realizable between chord i and chord j
    for pair in S:
        R[pair] += w
```

여기서 `S`는 set이어야 하고, 같은 chord pair 안에서 같은 unordered note pair는 한 번만 들어가야 함.

---

## Claude에게 부탁하고 싶은 다음 작업

### 우선순위 1

`refine_connectedness_fast()`의 intended semantics를 결정해줘:

- `matching multiplicity`를 세는 것이 맞는지
- 아니면 `unordered pair existence once per chord event`가 맞는지

현재 사용자 맥락상 나는 후자가 더 맞다고 보고 있음.

### 우선순위 2

후자가 맞다면 새 구현 예시:

- `refine_connectedness_undirected_once()`
- 각 nonzero chord pair마다 unordered note pair set을 구성
- set 기준으로만 `+w`
- 마지막에 upper triangular DataFrame 반환

### 우선순위 3

새 구현과 현재 구현을 hibari에서 비교해줘:

- note pair count
- diagonal inflation
- barcode / cycle count 변화
- baseline JS 변화

특히 기존 실험들이 다시 얼마나 바뀌는지 확인 필요.

---

## 참고용 ad-hoc 검증 메모

아래는 이번 세션에서 대화 중 즉석으로 확인한 포인트:

- `note(5,6)`은 `CURRENT == DIRECT`
- `note(10,23)`도 `CURRENT == DIRECT`
- `note(6,12)`는 `CURRENT > DIRECT`
- diagonal `(10,10)`, `(6,6)`도 `CURRENT > DIRECT`

즉 현재 구현은:

- "누락 복원"만 하는 쌍도 있고
- "복원 + 과계산"이 동시에 일어나는 쌍도 있음

이 둘을 분리해서 봐야 함.

---

## 한 줄 결론

**pre-bugfix는 틀렸고, current bugfix는 그 버그를 고쳤지만, 우리가 진짜 원하는 undirected note adjacency semantics까지는 아직 아닐 수 있다.**
