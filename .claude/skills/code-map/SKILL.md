---
name: code-map
description: >
  선택한 진입점 모듈(pipeline / generation / overlap)의 함수 호출 계층을 Mermaid flowchart
  HTML로 시각화. 최근 30일 수정 빨간 뱃지·hover 툴팁·외부 라이브러리 회색 박스 포함.
  "코드 맵 만들어줘", "pipeline 시각화", "generation 함수 계층 보여줘" 요청에 로드.
allowed-tools: Bash(python *) Bash(git *) Read Glob Agent
argument-hint: pipeline | generation | overlap
---

## code-map — 함수 호출 계층 HTML 생성

### 빠른 실행 (권장)

```bash
# C:\WK14 루트에서 실행
python tda_pipeline/tools/gen_code_map.py pipeline
python tda_pipeline/tools/gen_code_map.py generation
python tda_pipeline/tools/gen_code_map.py overlap
```

출력: `tda_pipeline/docs/code_map_<module>.html`

---

### 스킬 내 심층 분석 (subagent 위임 방식)

대상 모듈의 코드가 최근 크게 변경되어 `PIPELINE_EDGES` 수동 정의가 outdated일 때,
또는 generation/overlap 등 다른 모듈에서 depth-3 호출 체인이 필요할 때 사용.

#### Step 1 — Explore 서브에이전트로 파일 탐색

```
Explore 서브에이전트 프롬프트 (예시):

  tda_pipeline/<module>.py 를 읽고 다음 JSON을 반환하라:
  {
    "functions": [
      {"name": "func_name", "qual": "Class.func_name", "doc": "docstring 첫 줄", "lineno": 42}
    ],
    "edges": [
      {"from": "caller_qual", "to_module": "weights", "to_func": "compute_intra_weights", "depth": 1}
    ]
  }
  - depth 1: 대상 파일 내 함수가 직접 호출하는 함수
  - depth 2: 호출된 외부 모듈 함수가 다시 호출하는 함수 (해당 .py 파일도 읽어야 함)
  - depth 3: depth-2 함수의 호출 (필요 시만)
  - 외부 라이브러리(numpy/pandas/torch/music21/sklearn)는 module="external"로 표기
```

서브에이전트가 반환한 JSON을 부모 세션이 받아 HTML 생성.

#### Step 2 — edges JSON → HTML 생성

서브에이전트 결과를 `tda_pipeline/docs/edges_<module>.json`으로 저장 후:
```bash
python tda_pipeline/tools/gen_code_map.py <module>  # 자동으로 JSON 참조 (향후 지원)
```

또는 Claude가 직접 HTML 생성:
```python
import json, sys
sys.path.insert(0, "tda_pipeline/tools")
from gen_code_map import render_html, build_mermaid_generic
# ... edges JSON → Mermaid → HTML
```

---

### 출력 스펙

| 항목 | 내용 |
|------|------|
| 파일 | `tda_pipeline/docs/code_map_<module>.html` |
| 다이어그램 | Mermaid `flowchart LR` (또는 `TD`) |
| 깊이 | 최대 depth 3 (진입점 메서드 → 외부 함수 → 내부 호출) |
| 최근 수정 | 빨간 배경 (🔴) — `git log --since=30 days ago` |
| hover 툴팁 | 함수명 + docstring 첫 줄 (JavaScript post-render) |
| 외부 라이브러리 | 회색 박스 (numpy·pandas·torch·music21 등) |
| 모듈 색상 | preprocessing=파랑, weights=초록, overlap=보라, generation=주황, topology=노랑 |

---

### 주간 재생성 (loop skill 연동)

```bash
# 매주 월요일 코드 맵 갱신 — /loop 스킬과 연동
/loop 7d python tda_pipeline/tools/gen_code_map.py pipeline
```

또는 `/schedule` 스킬로 cron 등록:
```
0 9 * * 1  python tda_pipeline/tools/gen_code_map.py pipeline
```

---

### gen_code_map.py 커스터마이징

`tda_pipeline/tools/gen_code_map.py`의 `PIPELINE_EDGES` 딕셔너리를 수정하여
pipeline.py에 새 외부 함수 호출이 추가됐을 때 다이어그램을 갱신한다.

```python
# PIPELINE_EDGES 예시 추가
"run_new_stage": [
    ("new_module", ["func_a", "func_b"]),
],
```

## Gotchas (누적 실패점)

- **`professor.py`를 진입점으로 삼지 말 것** — 교수님 원본, 수정 금지 규약.
- `experiments/` / `tests/` / `tools/` / `debug/` 재편(2026-04-19) 이후 일부 import 경로가 `path_bootstrap` 의존 — depth 추적 시 루트 + 서브폴더 2경로 모두 포함.
- Mermaid LR 모드는 depth 3 이상에서 가독성 ↓ — depth≥3은 TD로 전환 권장.
- `git log --since=30 days ago`는 **로컬 타임존** 기준. CI 환경에서 다를 수 있음.
- 외부 라이브러리 목록은 수동 블랙리스트 — `music21.stream.Part.insert` 같은 메서드는 안 잡힐 수 있음. `external_prefixes` 확장 검토.
- HTML 출력은 정적 — 재생성 시 **이전 파일 덮어쓰기** 확인. 버전 관리는 git 사용.
