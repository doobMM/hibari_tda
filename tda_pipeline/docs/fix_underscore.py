"""
academic_paper_full.md에서 \_를 수정하는 스크립트.
- 수학 블록($...$, $$...$$) 내부: 그대로 유지
- 코드 블록(```...```) 내부: 그대로 유지
- 인라인 코드(`...`) 내부: 그대로 유지
- 그 외 산문/표에서: \_ → _  (불필요한 백슬래시 제거)
"""

import re

INPUT = r"C:\WK14\tda_pipeline\docs\academic_paper_full.md"
OUTPUT = INPUT  # 덮어쓰기

with open(INPUT, encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")
result = []

in_code_fence = False      # ``` 펜스 내부
in_display_math = False    # $$ 블록 내부

for line in lines:
    # ── 1. 펜스 코드블록 추적 ──────────────────────────────────
    stripped = line.strip()
    if stripped.startswith("```"):
        in_code_fence = not in_code_fence
        result.append(line)
        continue
    if in_code_fence:
        result.append(line)
        continue

    # ── 2. $$ 디스플레이 수학 블록 추적 ──────────────────────
    # $$가 한 줄에 0개 or 짝수: 상태 변화 없거나 토글 2번 = 유지
    # $$가 한 줄에 홀수: 상태 토글
    dd_count = len(re.findall(r'\$\$', line))
    if dd_count % 2 == 1:
        # 블록 시작 혹은 끝
        if in_display_math:
            # 이 줄은 아직 수학 블록 안
            result.append(line)
            in_display_math = False
            continue
        else:
            in_display_math = True
            result.append(line)
            continue
    if in_display_math:
        result.append(line)
        continue

    # ── 3. 인라인 처리: math / code 영역 외 \_ → _ ───────────
    # 토큰 단위로 분리: 인라인 수학($...$)과 인라인 코드(`...`)를 보호
    # 패턴: $$...$$ 이미 처리됨, $...$, `...` 보호
    def fix_line(s):
        # 인라인 코드와 인라인 수학을 토큰화하여 보호
        pattern = re.compile(
            r'(`[^`]*`)'          # 인라인 코드
            r'|(\$[^$\n]+?\$)'   # 인라인 수학 $...$
        )
        parts = []
        last = 0
        for m in pattern.finditer(s):
            # 매치 전 구간: 치환 적용
            before = s[last:m.start()]
            parts.append(before.replace(r'\_', '_'))
            # 보호 구간: 그대로
            parts.append(m.group(0))
            last = m.end()
        # 나머지
        tail = s[last:]
        parts.append(tail.replace(r'\_', '_'))
        return "".join(parts)

    result.append(fix_line(line))

fixed_content = "\n".join(result)

# 변경 통계
original_count = content.count(r'\_')
fixed_count = fixed_content.count(r'\_')
print(f"원본 \\_ 개수: {original_count}")
print(f"수정 후 \\_ 개수: {fixed_count}")
print(f"제거된 \\_ 개수: {original_count - fixed_count}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(fixed_content)

print(f"\n저장 완료: {OUTPUT}")
