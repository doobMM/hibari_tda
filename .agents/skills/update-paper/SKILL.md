---
name: update-paper
description: step3_data/*.json의 최신 실험 수치를 academic_paper_full.md 논문 표에 자동 반영. "논문 수치 업데이트", "표 갱신해줘", "최신 결과로 반영" 등의 요청에 자동 로드.
allowed-tools: Read Glob Edit Bash(python *)
argument-hint: [specific_section]  예: "§4.1만" 또는 "전체"
---

## 논문 수치 자동 업데이트 스킬

### 대상 파일
- **논문**: `tda_pipeline/docs/academic_paper_full.md`
- **데이터**: `tda_pipeline/docs/step3_data/*.json`

### 업데이트 절차

1. **JSON 로드**: step3_data/ 에서 해당 섹션의 결과 파일 읽기
2. **논문 표 탐색**: academic_paper_full.md 에서 갱신 대상 표 위치 찾기
3. **수치 매칭**: JSON 키 → 표 셀 매핑 (아래 매핑 테이블 참조)
4. **Edit 도구로 교체**: 기존 수치를 새 수치로 정밀 교체
5. **변경 사항 보고**: 어떤 수치가 바뀌었는지 diff 형태로 표시

### JSON → 논문 표 매핑

| 논문 섹션 | JSON 파일 | 표 위치 (line ~) | 핵심 필드 |
|-----------|----------|-----------------|----------|
| §4.1 거리함수 비교 | `step3_results.json` → experiment_1_baselines | ~769 | js_mean±std, coverage, n_cycles |
| §4.2 ablation | `step3_results.json` → experiment_2_ablations | ~788 | js_mean±std, kl_mean±std |
| §4.3a continuous | `step3_continuous_results.json` | ~878 | density, js_mean±std |
| §4.4 Algo2 DL | `step3_results.json` (해당 섹션) | ~920 | val_loss, js_mean, n_notes |
| §4.5 개선F | `step_improvementF_results.json` | ~955 | js_mean±std, js_min, val_mean, cov |
| §4.6 누적 비교 | 위 전체 종합 | ~976 | js 대표값 |
| §5 곡 고유 구조 | (수동) | ~1030 | entropy, PC count |
| §7.1 모듈 생성 | `step71_improvements.json` | (별도) | js_mean, cov_mean |
| §7.2a solari | `solari_results.json` | ~1306 | js_mean±std per metric |
| §7.2b aqua | `aqua_results.json` | (별도) | js_mean±std per metric |
| §8 일반화 | `all_tracks_results.json` | (별도) | 6곡 best_js, best_metric |

### 수치 형식 규칙
- JS divergence: `$0.0398 \pm 0.0031$` (소수점 4자리 ± 4자리)
- coverage: `$1.000$` (소수점 3자리)
- val_loss: `$0.282$` (소수점 3자리)
- n_cycles: 정수
- 최적값 볼드: `$\mathbf{0.0006 \pm 0.0005}$`
- 행 전체 최적: `__행 내용__` (마크다운 볼드)

### 안전 규칙
- **수치만 교체**, 표 구조/설명문은 건드리지 않기
- 교체 전 반드시 기존값과 새 값을 나란히 보여주고 확인 받기
- 소수점 자릿수를 기존과 동일하게 유지
- `\mathbf` 볼드 처리는 최솟값이 변경된 경우에만 이동

### 사용 예시

```
/update-paper §4.1
→ step3_results.json 읽기
→ line 769~772 의 frequency/Tonnetz/VL/DFT 행 수치 비교
→ 변경 없으면 "모든 수치 일치" 보고
→ 변경 있으면 diff 표시 후 Edit 적용

/update-paper 전체
→ 모든 섹션 순회, 변경 필요한 곳만 리포트
```
