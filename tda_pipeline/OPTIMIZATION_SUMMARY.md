# TDA Music Pipeline - 리팩토링 요약

## 아키텍처 변경

### 기존 구조 (5파일, 순환 의존성 있음)
```
process.py ─────┐
util.py ────────┼── 순환 호출 이슈 (specify_chord_list2 등 복사)
professor.py ───┘
WK13_analysis.ipynb
WK13_model.ipynb
```

### 새로운 구조 (6파일, 단방향 의존성)
```
config.py            ← 모든 설정 중앙 관리
    ↓
preprocessing.py     ← MIDI → 화음/note 레이블링
    ↓
weights.py           ← 가중치/거리 행렬 계산 (핵심 최적화)
    ↓
overlap.py           ← 사이클 관리 + 중첩행렬
    ↓
generation.py        ← Algorithm 1 & 2
    ↓
pipeline.py          ← 전체 흐름 조율 + 캐싱
```

---

## 핵심 최적화 상세

### 1. `refine_connectedness` → `refine_connectedness_fast` (weights.py)

**문제**: 기존 코드는 4중 중첩 Python 루프로 O(17² × max_notes²) 반복
```python
# 기존 (process.py / util.py)
for i in range(weight_mtrx.shape[0]):        # 17
    for j in range(weight_mtrx.shape[1]):    # 17
        for note_i in notes_i:               # ~3-4
            for note_j in notes_j:           # ~3-4
                weight_mtrx_refined.loc[note_i, note_j] += weight
```

**해결**: 확장 행렬(expansion matrix)을 사전 계산하여 행렬 곱으로 대체
```python
# 새 코드 (weights.py)
E = _build_expansion_matrix(notes_dict, num_notes)  # (17, 23) 행렬, 1회 계산
refined = E.T @ W_upper @ E                          # numpy 행렬 곱 1회
```
- **예상 속도 향상**: ~10-50x (화음/note 수에 따라)
- **부동소수점 정밀도**: `refine_connectedness_precise` 함수에서 반올림 보정

### 2. `build_activation_matrix` (overlap.py)

**문제**: 기존 `get_scattered_cycles_df`는 각 행마다 lambda 함수 호출
```python
# 기존
cycle_dfs[label] = sub_df.apply(lambda row: 1 if row.sum() > 0 else 0, axis=1)
```

**해결**: numpy boolean 배열로 일괄 처리
```python
# 새 코드
sub = df_values[:, note_indices]
activation[:, c_idx] = np.any(sub > 0, axis=1).astype(int)
```
- **예상 속도 향상**: ~5-10x

### 3. `find_consecutive_runs` (overlap.py)

**문제**: 기존 `filter_consecutive_indices`는 인덱스를 하나씩 비교
```python
# 기존
for i in range(1, len(index)):
    if index[i] == index[i-1] + 1:
        current_group.append(index[i])
    else: ...
```

**해결**: numpy diff로 연속 구간의 시작/끝을 한 번에 찾음
```python
# 새 코드
padded = np.concatenate(([0], binary_series, [0]))
diff = np.diff(padded)
starts = np.where(diff == 1)[0]
ends = np.where(diff == -1)[0]
```

### 4. Algorithm 1 최적화 (generation.py)

**버그 수정**:
- `for num_nodes in range(inst_len[j])`: range는 루프 시작 시 고정되므로
  중간에 `inst_len[j] -= 1`이 반영되지 않음 → 음수 문제 발생
- 수정: 루프 시작 전에 `num_to_sample = max(0, inst_len[j])`로 고정

**성능 개선**:
- `onset_checker`를 `list` → `set`으로 변경: 멤버십 검사 O(n) → O(1)
- `CycleSetManager`: 교집합/합집합 연산을 캐싱하여 동일 mask 재계산 방지
- `max_resample_attempts` 도입: 무한 루프 방지 (기존에는 영원히 재샘플링)
- `NodePool`: numpy 배열 기반 샘플링 (Python list보다 ~2x 빠름)

### 5. Algorithm 2 최적화 (generation.py)

**문제**: 기존 코드는 전체 X_train을 한 번에 forward pass → OOM 위험
```python
# 기존
y_pred = model(torch.from_numpy(X_train))  # X_train 전체!
```

**해결**: 미니배치 학습 도입
```python
# 새 코드
for start in range(0, n_train, batch_size):
    X_batch = torch.from_numpy(X_train[batch_idx])
    y_pred = model(X_batch)
    loss.backward()
    optimizer.step()
```

**데이터 정합성 수정**:
- 기존: `L_encoded`가 두 악기 concat으로 길이 7670, `L_onehot`은 시간 기준 1088 → 불일치
- 수정: `prepare_training_data`에서 두 악기 모두 시간축 기준 one-hot으로 통합

---

## 캐싱 전략 (pipeline.py)

`TDAMusicPipeline._cache` 딕셔너리로 중간 결과를 메모리에 유지:

| 캐시 키 | 내용 | 용도 |
|---------|------|------|
| `inst1_real`, `inst2_real` | 전처리된 음표 리스트 | Stage 3, 4 |
| `notes_label`, `notes_dict` | note/화음 레이블 | 전체 |
| `adn_i` | lag별 시퀀스 | Stage 2 |
| `h1_timeflow_lag1` | persistence 데이터 | Stage 3 |
| `cycle_labeled` | 사이클 레이블 | Stage 3, 4 |
| `overlap_matrix` | 중첩행렬 | Stage 4 |
| `model` | 학습된 신경망 | 생성 |

`save_cache()` / `load_cache()`로 디스크 영속화 가능.
전처리만 바꾸고 homology는 재사용하는 등의 부분 재실행이 가능합니다.

---

## 사용 예시

```python
from config import PipelineConfig
from pipeline import TDAMusicPipeline

config = PipelineConfig()
config.overlap.threshold = 0.35
config.homology.power = -4  # 더 정밀한 탐색

pipeline = TDAMusicPipeline(config)
pipeline.run_preprocessing("Ryuichi_Sakamoto_-_hibari.mid")
pipeline.run_homology_search(search_type='timeflow', lag=1, dimension=1)
pipeline.run_overlap_construction(persistence_key='h1_timeflow_lag1')

# 또는 기존 pickle에서 로드
# pipeline.run_overlap_construction(from_pickle='h1_rBD_t_notes1_1e-4_0.0~1.5.pkl')

generated = pipeline.run_generation_algo1(verbose=True)
pipeline.save_cache()  # 중간 결과 저장
```

## 남은 과제

1. **generateBarcode 최적화**: 가장 큰 병목이지만 교수님 코드이므로 수정 범위에서 제외함.
   대안: giotto-tda, ripser 같은 C++ 기반 라이브러리 사용 검토
2. **Algorithm 2 데이터 정합성**: 두 악기의 시간축 정렬 방식에 대한 추가 검토 필요
3. **inst_len 계산 로직**: 원곡의 화음 높이 시퀀스를 자동으로 추출하는 함수 추가
