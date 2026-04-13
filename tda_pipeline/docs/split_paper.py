"""
split_paper.py — academic_paper_full.md를 섹션별로 분할하여 step*.md 파일 재생성.
"""
import os, re

DOCS = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(DOCS, 'academic_paper_full.md')

with open(FULL, 'r', encoding='utf-8') as f:
    lines = f.readlines()

text = ''.join(lines)

# 주요 섹션 패턴으로 분할
SECTIONS = [
    ('step0',  r'^## 초록',                  r'^## 1\.'),
    ('step1',  r'^## 1\.',                   r'^## 2\.'),
    ('step2',  r'^## 2\.',                   r'^## 3\.'),
    ('step3',  r'^## 3\.',                   r'^## 4\.'),
    ('step4',  r'^## 4\.',                   r'^## 5\.'),
    ('step5',  r'^## 5\.',                   r'^## 6\.'),
    ('step6',  r'^## 6\.',                   r'^## 7\.'),
    ('step7',  r'^## 7\.',                   r'^## 8\.'),
    ('step8',  r'^## 8\.',                   r'^## 7\.1\.1'),  # 결론 + 참고문헌
    ('step71', r'^## 7\.1\.1',               None),            # 7.1 Appendix
]

def find_pos(pattern, start=0):
    m = re.search(pattern, text[start:], re.MULTILINE)
    if m:
        return start + m.start()
    return None

results = {}
for name, start_pat, end_pat in SECTIONS:
    s = find_pos(start_pat)
    if s is None:
        print(f"  WARNING: start pattern not found for {name}: {start_pat}")
        continue
    if end_pat:
        e = find_pos(end_pat, s + 1)
    else:
        e = None

    chunk = text[s:e] if e else text[s:]
    results[name] = chunk.rstrip() + '\n'
    print(f"  {name}: chars {s}–{e or 'end'}, {len(results[name].splitlines())} lines")

# 제목 헤더는 step0에서만 전체 제목 포함 (나머지는 섹션 그대로)
# 실제로 step0에는 Abstract만 — 전체 제목+메타데이터는 별도
title_end = find_pos(r'^## 초록')
title_block = text[:title_end]

# step0 = 제목 + 메타 + 초록
results['step0'] = title_block + results.get('step0', '')

for name, content in results.items():
    out_path = os.path.join(DOCS, f'academic_paper_{name}.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved: academic_paper_{name}.md ({len(content.splitlines())} lines)")

print("\nDone. Next: run build_academic_pdf.py for each step file.")
