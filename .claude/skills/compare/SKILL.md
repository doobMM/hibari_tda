---
name: compare
description: step3_data의 실험 결과 JSON 파일 2개를 비교하여 delta%, 통계 유의성(t-test), 승패 요약을 자동 생성. "비교해줘", "차이 분석", "이번 결과 vs baseline" 등의 요청에 자동 로드.
allowed-tools: Read Glob Bash(python *)
argument-hint: <file_a.json> <file_b.json>  또는  "최신 결과 vs baseline"
---

## 실험 결과 비교 스킬

### 사용 예시
```
/compare step3_results.json step3_continuous_results.json
/compare harmony_continuous_results.json combined_AB_results.json
/compare "최신 결과" "baseline"    ← 자연어도 가능 (파일 자동 매칭)
```

### 비교 절차

1. **파일 로드**: `tda_pipeline/docs/step3_data/` 에서 두 JSON 읽기
2. **공통 메트릭 추출**: js_mean, js_std, js_min, kl_mean, n_cycles, coverage 등
3. **Delta 계산**: `(B - A) / A × 100%` (음수 = B가 더 좋음)
4. **통계 검정**: mean ± std가 있으면 Welch t-test (scipy.stats.ttest_ind_from_stats)

### 비교 스크립트 (인라인 실행)

```python
import json, sys
from scipy.stats import ttest_ind_from_stats
import math

def load_json(path):
    with open(path) as f:
        return json.load(f)

def welch_t(m1, s1, n1, m2, s2, n2):
    """Welch t-test from summary stats. Returns (t, p)."""
    try:
        t, p = ttest_ind_from_stats(m1, s1, n1, m2, s2, n2, equal_var=False)
        return t, p
    except:
        return float('nan'), float('nan')

def compare_metric(name, a_mean, a_std, b_mean, b_std, n_a=20, n_b=20):
    """단일 메트릭 비교 결과 dict 반환"""
    if a_mean is None or b_mean is None:
        return None
    delta = b_mean - a_mean
    delta_pct = (delta / a_mean * 100) if a_mean != 0 else float('inf')
    
    result = {
        'metric': name,
        'A': f"{a_mean:.6f}",
        'B': f"{b_mean:.6f}",
        'delta': f"{delta:+.6f}",
        'delta_pct': f"{delta_pct:+.1f}%",
    }
    
    if a_std is not None and b_std is not None:
        t, p = welch_t(a_mean, a_std, n_a, b_mean, b_std, n_b)
        result['p_value'] = f"{p:.4f}" if not math.isnan(p) else "N/A"
        result['significant'] = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
    
    # 방향 판단 (JS/KL은 낮을수록 좋고, coverage는 높을수록 좋음)
    lower_is_better = any(k in name.lower() for k in ['js', 'kl', 'loss', 'error', 'cost', 'dtw'])
    if lower_is_better:
        result['winner'] = 'B' if delta < 0 else 'A' if delta > 0 else 'tie'
    else:
        result['winner'] = 'B' if delta > 0 else 'A' if delta < 0 else 'tie'
    
    return result
```

### 출력 형식 (마크다운 테이블)

```
## A vs B 비교 결과

| 메트릭 | A | B | Δ | Δ% | p-value | 유의성 | 승자 |
|--------|---|---|---|-----|---------|--------|------|
| js_mean | 0.0398 | 0.0280 | -0.0118 | -29.6% | 0.0001 | *** | B |
| ...

### 요약
- B가 A 대비 js_mean -29.6% 개선 (p < 0.001, 매우 유의)
- coverage는 동일 (1.0 vs 1.0)
- 종합: B 우세 (2승 0패 1무)
```

### JSON 구조 패턴별 처리

파일마다 구조가 다르므로 재귀적으로 js_mean, js_std 등의 키를 탐색:

| 패턴 | 예시 파일 | 추출법 |
|------|----------|--------|
| `{metric: {js_mean, js_std}}` | step3_results, aqua_results | 직접 접근 |
| `{experiment: {js_mean, js_std}}` | step3_continuous | 실험명 매칭 |
| `{experiments: {name: {vs_original: {pitch_js}}}}` | combined_AB | nested 접근 |
| `{strategy: {avg: {pitch_js}}}` | temporal_reorder | avg/std 분리 |

### 주의사항
- N(반복 횟수)이 다르면 명시: "A: N=20, B: N=5"
- p-value는 N≥5일 때만 의미 있음
- 같은 곡, 같은 metric 기반 실험끼리만 직접 비교 유효

## Gotchas (누적 실패점)

- **gap 다른 JSON 섞어 비교 금지**. gap=3 (pre-bugfix) ↔ gap=0 (post-bugfix) 결과는 **정량 비교 불가** — 전처리 자체가 다름. 파일명·manifest에 gap 표기 확인 후 진행.
- **N=1 결과는 평균으로 취급 금지** — `js_mean` 키만 있고 `js_std`가 없으면 반복 없음. Welch t-test 시 p값 폭주.
- Welch vs Student t-test: 기본은 Welch (등분산 가정 안 함). 보고 시 명시.
- 음수 delta = B 개선이라는 **우리 연구 관례**는 `lower_is_better` metric에 한정. `coverage`/`accuracy`는 반대.
- **JSON 키 구조가 실험마다 다름** — 새 실험 추가 시 위 표에 패턴 등록 권장.
- 같은 파일에 여러 metric이 섞여 있으면 metric별로 분리 비교 (합산 평균 금지).
