---
description: code-map skill의 얇은 alias. `/map pipeline.py` 형태로 호출. 구현은 code-map skill에 위임.
argument-hint: <entry_module>
---

# /map — code-map skill alias

`/code-map` skill을 짧게 부를 때 사용. 의미·동작은 code-map skill과 동일.

실행:
```
Skill(skill="code-map", args="<entry_module>")
```

## 사용 예

```
/map pipeline.py
/map generation.py
/map overlap.py
```

## Gotchas

- skill이 이미 실행 중이면 재호출 금지 (CLAUDE.md Skill 규약)
- `professor.py`는 진입점으로 삼지 말 것 — 교수님 원본, 위계 파악 목적 벗어남
