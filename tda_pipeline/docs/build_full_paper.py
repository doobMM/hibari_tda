"""
build_full_paper.py — 전체 논문 md 합치기

step1/2/3/4 + _front + _back을 단일 academic_paper_full.md로 결합.
각 step 파일에서 title line과 references block을 제거하고,
section 번호를 일관되게 재지정한다.

최종 섹션 구조:
  §1  서론 (from _front)
  §2  수학적 배경 (from step1)
  §3  두 가지 음악 생성 알고리즘 (from step2, §2.10~2.12 → §3.1~3.3)
  §4  실험 (from step3, §3.1~3.5 → §4.1~4.5, §3.3a → §4.3a)
  §5  시각자료 (from step4, Figure 1~7)
  §6~ 차별화 + 향후 + 결론 + 참고문헌 (from _back)
"""
import os, re

DOCS = os.path.dirname(os.path.abspath(__file__))

def read(name):
    with open(os.path.join(DOCS, name), 'r', encoding='utf-8') as f:
        return f.read()

def strip_title(txt):
    """첫 # 타이틀 줄과 이어지는 metadata를 제거."""
    lines = txt.split('\n')
    # 첫 # 라인부터, 비어있지 않은 다음 ## 라인 직전까지 제거
    out = []
    skipping_header = True
    for i, line in enumerate(lines):
        if skipping_header:
            if line.startswith('## '):
                skipping_header = False
                out.append(line)
            continue
        out.append(line)
    return '\n'.join(out)

def strip_references(txt):
    """## 참고문헌 이후 전체 제거."""
    m = re.search(r'^## 참고문헌', txt, flags=re.M)
    if m:
        return txt[:m.start()].rstrip() + '\n'
    return txt

def renumber_sections_step2(txt):
    """step2의 §2.10/2.11/2.12 → §3.1/3.2/3.3
    그리고 ## 알고리즘 의사코드... → ## 3. 두 가지 음악 생성 알고리즘"""
    txt = txt.replace('## 두 가지 음악 생성 알고리즘',
                      '## 3. 두 가지 음악 생성 알고리즘')
    txt = txt.replace('## 2.10 Algorithm 1', '## 3.1 Algorithm 1')
    txt = txt.replace('## 2.11 Algorithm 2', '## 3.2 Algorithm 2')
    txt = txt.replace('## 2.12 두 알고리즘의 비교 요약',
                      '## 3.3 두 알고리즘의 비교 요약')
    return txt

def renumber_sections_step3(txt):
    """step3의 §3.x → §4.x, 메인 타이틀 재설정"""
    txt = txt.replace('## 실험 설계와 결과',
                      '## 4. 실험 설계와 결과')
    txt = txt.replace('## 3.1 Experiment 1', '## 4.1 Experiment 1')
    txt = txt.replace('## 3.2 Experiment 2', '## 4.2 Experiment 2')
    txt = txt.replace('## 3.3 통계적 유의성', '## 4.3 통계적 유의성')
    txt = txt.replace('## 3.3a Experiment 2.5', '## 4.3a Experiment 2.5')
    txt = txt.replace('## 3.4 Experiment 3', '## 4.4 Experiment 3')
    txt = txt.replace('## 3.5 종합 논의', '## 4.5 종합 논의')
    return txt

def renumber_sections_step4(txt):
    """step4의 메인 타이틀 → §5 시각자료"""
    txt = txt.replace('## 시각자료 (Figures)',
                      '## 5. 시각자료 (Figures)')
    return txt

def main():
    front = read('_paper_front.md')
    s1 = strip_references(strip_title(read('academic_paper_step1.md')))
    s2 = strip_references(strip_title(read('academic_paper_step2.md')))
    s3 = strip_references(strip_title(read('academic_paper_step3.md')))
    s4 = strip_references(strip_title(read('academic_paper_step4.md')))
    back = read('_paper_back.md')

    # Step1 메인 섹션은 이미 ## 2. 수학적 배경
    # Step2 renumber
    s2 = renumber_sections_step2(s2)
    s3 = renumber_sections_step3(s3)
    s4 = renumber_sections_step4(s4)

    parts = [front, s1, s2, s3, s4, back]
    merged = '\n\n'.join(p.rstrip() for p in parts) + '\n'

    out_path = os.path.join(DOCS, 'academic_paper_full.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(merged)
    print(f"Saved: {out_path}")
    print(f"Length: {len(merged.splitlines())} lines, {len(merged)} chars")

if __name__ == '__main__':
    main()
