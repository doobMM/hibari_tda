"""
build_academic_pdf.py — academic_paper_step*.md → PDF 변환

Markdown + LaTeX 수식을 reportlab으로 직접 렌더링.
복잡한 수식은 텍스트 블록으로 표시 (한글 폰트 사용).
"""
import os, re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak,
    KeepTogether, Preformatted
)
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBd', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))

# 스타일
s_title = ParagraphStyle('T', fontName='MalgunBd', fontSize=15, leading=20,
    spaceAfter=10, alignment=TA_CENTER)
s_meta = ParagraphStyle('M', fontName='Malgun', fontSize=9.5, leading=12,
    alignment=TA_CENTER, textColor=HexColor('#555'))
s_h1 = ParagraphStyle('H1', fontName='MalgunBd', fontSize=13, leading=17,
    spaceBefore=14, spaceAfter=7, textColor=HexColor('#1a5276'))
s_h2 = ParagraphStyle('H2', fontName='MalgunBd', fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=5, textColor=HexColor('#2c3e50'))
s_h3 = ParagraphStyle('H3', fontName='MalgunBd', fontSize=10, leading=13,
    spaceBefore=8, spaceAfter=4, textColor=HexColor('#5d6d7e'))
s_body = ParagraphStyle('B', fontName='Malgun', fontSize=9.5, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=5)
s_bold_inline = ParagraphStyle('BI', fontName='MalgunBd', fontSize=9.5, leading=14)
s_math = ParagraphStyle('Math', fontName='Consolas', fontSize=9.5, leading=14,
    alignment=TA_CENTER, spaceBefore=4, spaceAfter=4,
    textColor=HexColor('#000088'), backColor=HexColor('#f5f5f5'),
    leftIndent=20, rightIndent=20, borderPadding=6)
s_inline_math = ParagraphStyle('IM', fontName='Consolas', fontSize=9.5, leading=14)
s_code = ParagraphStyle('C', fontName='Consolas', fontSize=8.5, leading=11,
    leftIndent=15, backColor=HexColor('#f0f0f0'), borderPadding=4,
    spaceBefore=4, spaceAfter=4)
s_bullet = ParagraphStyle('BL', fontName='Malgun', fontSize=9.5, leading=13.5,
    leftIndent=18, bulletIndent=6, spaceAfter=3, alignment=TA_JUSTIFY)
s_quote = ParagraphStyle('Q', fontName='Malgun', fontSize=9, leading=12,
    leftIndent=20, rightIndent=20, textColor=HexColor('#555'),
    spaceBefore=4, spaceAfter=4)


def latex_to_text(latex_str):
    """LaTeX 수식을 가독성 있는 plain text로 변환 (간단한 케이스)"""
    s = latex_str.strip()

    # 자주 쓰는 LaTeX 명령어 → unicode
    replacements = [
        (r'\\text\{([^}]*)\}', r'\1'),
        (r'\\mathbb\{R\}', 'R'),
        (r'\\mathbb\{Z\}', 'Z'),
        (r'\\mathcal\{L\}', 'L'),
        (r'\\varepsilon', 'ε'),
        (r'\\epsilon', 'ε'),
        (r'\\alpha', 'α'),
        (r'\\beta', 'β'),
        (r'\\sigma', 'σ'),
        (r'\\Sigma', 'Σ'),
        (r'\\partial', '∂'),
        (r'\\subseteq', '⊆'),
        (r'\\subset', '⊂'),
        (r'\\in\b', '∈'),
        (r'\\forall', '∀'),
        (r'\\exists', '∃'),
        (r'\\rightarrow', '→'),
        (r'\\to\b', '→'),
        (r'\\leftarrow', '←'),
        (r'\\Rightarrow', '⇒'),
        (r'\\le\b', '≤'),
        (r'\\ge\b', '≥'),
        (r'\\ne\b', '≠'),
        (r'\\approx', '≈'),
        (r'\\sum', 'Σ'),
        (r'\\prod', 'Π'),
        (r'\\infty', '∞'),
        (r'\\hat\{([^}]*)\}', r'\1̂'),
        (r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)'),
        (r'\\sqrt\{([^}]*)\}', r'√(\1)'),
        (r'\\cdot', '·'),
        (r'\\times', '×'),
        (r'\\quad', '  '),
        (r'\\,', ' '),
        (r'\\;', ' '),
        (r'\\!', ''),
        (r'\\left', ''),
        (r'\\right', ''),
        (r'\\big', ''),
        (r'\\Big', ''),
        (r'\\,\\middle\\\|', ' | '),
        (r'\\middle\|', ' | '),
        (r'\\\|', '||'),
        (r'\\langle', '⟨'),
        (r'\\rangle', '⟩'),
        (r'\\emptyset', '∅'),
        (r'\\cup', '∪'),
        (r'\\cap', '∩'),
        (r'\\setminus', '\\\\'),
        (r'\\circ', '∘'),
        (r'\\ker', 'ker'),
        (r'\\text\{im\}', 'im'),
        (r'\\text\{rank\}', 'rank'),
        (r'\\binom\{([^}]*)\}\{([^}]*)\}', r'C(\1,\2)'),
        (r'\\mathbb\{1\}', '𝟙'),
        (r'\\quantile', 'quantile'),
        (r'\\theta', 'θ'),
        (r'\\Delta', 'Δ'),
        (r'\\delta', 'δ'),
        (r'\\lambda', 'λ'),
        (r'\\ell\b', 'ℓ'),
        (r'\\min\b', 'min'),
        (r'\\max\b', 'max'),
        (r'\\argmax', 'argmax'),
        (r'\\log\b', 'log'),
        (r'_\{([^}]*)\}', r'_\1'),  # subscript: x_{abc} → x_abc
        (r'\^\{([^}]*)\}', r'^\1'),
        (r'\{|\}', ''),
        (r'\\\\', '\n'),
    ]
    for pat, rep in replacements:
        s = re.sub(pat, rep, s)
    return s


def parse_inline(text):
    """**bold**, $math$, `code` 등 인라인 마크업 처리"""
    # $...$ 인라인 수식
    text = re.sub(r'\$([^$]+)\$', lambda m: f'<font name="Consolas" color="#000088">{latex_to_text(m.group(1))}</font>', text)
    # **bold**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # *italic*
    text = re.sub(r'(?<![*])\*([^*]+)\*(?![*])', r'<i>\1</i>', text)
    # `code`
    text = re.sub(r'`([^`]+)`', r'<font name="Consolas" color="#aa0000">\1</font>', text)
    return text


def md_to_pdf(md_path, pdf_path):
    """Markdown 파일을 PDF로 변환"""
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2.2*cm, rightMargin=2.2*cm)
    story = []

    i = 0
    in_math_block = False
    math_buf = []
    in_code_block = False
    code_buf = []

    while i < len(lines):
        line = lines[i].rstrip()

        # 수식 블록 ($$...$$)
        if line.strip().startswith('$$'):
            if in_math_block:
                # 종료
                math_text = '\n'.join(math_buf)
                story.append(Paragraph(latex_to_text(math_text), s_math))
                math_buf = []
                in_math_block = False
            else:
                in_math_block = True
                # 같은 줄에 끝나는 경우
                content = line.strip().strip('$')
                if content and line.count('$$') >= 2:
                    story.append(Paragraph(latex_to_text(content), s_math))
                    in_math_block = False
            i += 1
            continue

        if in_math_block:
            math_buf.append(line)
            i += 1
            continue

        # 코드 블록
        if line.strip().startswith('```'):
            if in_code_block:
                code_text = '\n'.join(code_buf)
                story.append(Preformatted(code_text, s_code))
                code_buf = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buf.append(line)
            i += 1
            continue

        # 빈 줄
        if not line.strip():
            i += 1
            continue

        # 구분선
        if line.strip() == '---':
            story.append(Spacer(1, 3*mm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#ccc')))
            story.append(Spacer(1, 3*mm))
            i += 1
            continue

        # 헤더
        if line.startswith('# '):
            story.append(Paragraph(parse_inline(line[2:]), s_title))
        elif line.startswith('## '):
            story.append(Paragraph(parse_inline(line[3:]), s_h1))
        elif line.startswith('### '):
            story.append(Paragraph(parse_inline(line[4:]), s_h2))
        elif line.startswith('#### '):
            story.append(Paragraph(parse_inline(line[5:]), s_h3))
        # 메타 정보 (**저자:** 등)
        elif line.startswith('**저자:**') or line.startswith('**지도:**') or line.startswith('**작성일:**'):
            story.append(Paragraph(parse_inline(line), s_meta))
        # 불릿
        elif line.startswith('- '):
            story.append(Paragraph('• ' + parse_inline(line[2:]), s_bullet))
        elif re.match(r'^\d+\.\s', line):
            story.append(Paragraph(parse_inline(line), s_bullet))
        # 본문
        else:
            story.append(Paragraph(parse_inline(line), s_body))

        i += 1

    doc.build(story)
    print(f"PDF: {pdf_path}")


if __name__ == "__main__":
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        md_files = [sys.argv[1]]
    else:
        # 모든 academic_paper_step*.md 변환
        import glob
        md_files = sorted(glob.glob(os.path.join(docs_dir, 'academic_paper_step*.md')))

    for md in md_files:
        pdf = md.replace('.md', '.pdf')
        md_to_pdf(md, pdf)
