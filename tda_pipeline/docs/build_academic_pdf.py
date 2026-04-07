"""
build_academic_pdf.py — academic_paper_step*.md → PDF 변환

LaTeX 수식을 matplotlib mathtext로 PNG 렌더링하여 PDF에 이미지로 삽입.
한글 본문은 맑은고딕, 수식은 실제 수학 표기로 표시.
"""
import os, re, sys, hashlib, io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak,
    Image, Preformatted, KeepTogether
)
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 폰트
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBd', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))

# matplotlib mathtext 설정 (Computer Modern 비슷하게)
rcParams['mathtext.fontset'] = 'cm'
rcParams['font.family'] = 'serif'

# 수식 캐시 디렉토리
EQ_CACHE_DIR = os.path.join(os.path.dirname(__file__), '_eq_cache')
os.makedirs(EQ_CACHE_DIR, exist_ok=True)


def render_equation(latex_str, display=True, fontsize=14):
    """LaTeX 수식을 PNG로 렌더링하여 파일 경로 반환.

    display=True: 블록 수식 (큰 크기, 가운데)
    display=False: 인라인 수식 (작은 크기)
    """
    # 캐시 키
    key = hashlib.md5(f"{latex_str}|{display}|{fontsize}".encode()).hexdigest()
    cache_path = os.path.join(EQ_CACHE_DIR, f"eq_{key}.png")

    if os.path.exists(cache_path):
        return cache_path

    # matplotlib mathtext 렌더링
    fig = plt.figure(figsize=(0.01, 0.01), dpi=200)
    fig.patch.set_alpha(0)
    try:
        # mathtext에 호환되는 형태로 변환
        tex = clean_latex_for_mathtext(latex_str)
        text = fig.text(0, 0, f'${tex}$', fontsize=fontsize,
                        color='black', ha='left', va='bottom')

        # 텍스트 크기 측정
        fig.canvas.draw()
        bbox = text.get_window_extent()
        w_in = bbox.width / 200 + 0.1
        h_in = bbox.height / 200 + 0.1
        fig.set_size_inches(w_in, h_in)

        plt.savefig(cache_path, dpi=200, bbox_inches='tight',
                    transparent=True, pad_inches=0.05)
    except Exception as e:
        # mathtext 렌더링 실패 시 plain text fallback
        print(f"  수식 렌더링 실패: {latex_str[:50]}... ({e})")
        plt.close(fig)
        return None
    plt.close(fig)
    return cache_path


def clean_latex_for_mathtext(s):
    """matplotlib mathtext가 지원하는 형식으로 LaTeX 정리.

    mathtext가 지원하지 않는 것들을 unicode 또는 호환 명령어로 변환.
    """
    # \begin{cases}...\end{cases} → 단순한 표현으로
    s = re.sub(
        r'\\begin\{cases\}(.+?)\\end\{cases\}',
        lambda m: m.group(1).replace('\\\\', ', ').replace('&', ' '),
        s, flags=re.DOTALL
    )

    replacements = [
        # \text → \mathrm
        (r'\\text\{([^}]*)\}', r'\\mathrm{\1}'),
        # 부등호: mathtext가 \le, \ge 미지원 → unicode
        (r'\\le\b', r'\\leq'),
        (r'\\ge\b', r'\\geq'),
        (r'\\ne\b', r'\\neq'),
        # 공백
        (r'\\quad', r'\\ \\ '),
        (r'\\;', r'\\,'),
        (r'\\!', ''),
        # |, ||
        (r'\\middle\\\|', '|'),
        (r'\\middle\|', '|'),
        (r'\\big\\\|', r'\\|'),
        (r'\\Big\\\|', r'\\|'),
        (r'\\big\|', '|'),
        (r'\\Big\|', '|'),
        # \left, \right
        (r'\\left', ''),
        (r'\\right', ''),
        # 기타
        (r'\\hat\{([^}]*)\}', r'\\hat{\1}'),
        (r'\\widehat\{([^}]*)\}', r'\\hat{\1}'),
        (r'\\bar\{([^}]*)\}', r'\\bar{\1}'),
    ]
    for pat, rep in replacements:
        s = re.sub(pat, rep, s)
    return s


# ── 스타일 ──
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
s_code = ParagraphStyle('C', fontName='Consolas', fontSize=8.5, leading=11,
    leftIndent=15, backColor=HexColor('#f0f0f0'), borderPadding=4,
    spaceBefore=4, spaceAfter=4)
s_bullet = ParagraphStyle('BL', fontName='Malgun', fontSize=9.5, leading=13.5,
    leftIndent=18, bulletIndent=6, spaceAfter=3, alignment=TA_JUSTIFY)


def parse_inline_with_math(text):
    """
    인라인 수식 ($...$)을 추출하여 텍스트 + Image의 sequence로 변환.
    bold/italic/code 마크업도 처리.

    Returns: list of (type, content) where type ∈ ('text', 'inline_eq')
    """
    parts = []
    pos = 0
    # $...$ 패턴 찾기 (단, $$는 제외)
    pattern = re.compile(r'(?<!\$)\$([^$]+)\$(?!\$)')

    for m in pattern.finditer(text):
        if m.start() > pos:
            parts.append(('text', text[pos:m.start()]))
        parts.append(('inline_eq', m.group(1)))
        pos = m.end()
    if pos < len(text):
        parts.append(('text', text[pos:]))

    return parts


def parse_inline_markup(text):
    """**bold**, *italic*, `code` → reportlab markup"""
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<![*])\*([^*]+)\*(?![*])', r'<i>\1</i>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Consolas" color="#aa0000">\1</font>', text)
    return text


def make_paragraph_with_inline_math(text, style):
    """
    인라인 수식이 포함된 텍스트를 Paragraph로 만든다.
    수식 부분은 작은 이미지를 inline으로 삽입.

    reportlab의 Paragraph는 <img/> 태그로 인라인 이미지를 지원한다.
    """
    parts = parse_inline_with_math(text)
    result = ''
    for ptype, content in parts:
        if ptype == 'text':
            result += parse_inline_markup(content)
        else:
            # 인라인 수식 → 작은 PNG → <img/> 태그
            img_path = render_equation(content, display=False, fontsize=11)
            if img_path:
                # reportlab Paragraph inline image
                result += f'<img src="{img_path}" valign="-3"/>'
            else:
                result += f'<font name="Consolas" color="#000088">{content}</font>'
    return Paragraph(result, style)


def make_block_equation(latex_str):
    """블록 수식 → 큰 PNG → 가운데 정렬 Image"""
    img_path = render_equation(latex_str, display=True, fontsize=15)
    if img_path is None:
        return Paragraph(f'<font name="Consolas">{latex_str}</font>', s_body)

    # 이미지 크기 측정
    from PIL import Image as PILImage
    pil = PILImage.open(img_path)
    w_px, h_px = pil.size
    # 200 DPI로 저장했으므로 inch로 변환
    w_in = w_px / 200
    h_in = h_px / 200
    # 최대 너비 제한
    max_w = 14 * cm / inch
    if w_in > max_w:
        scale = max_w / w_in
        w_in *= scale
        h_in *= scale

    img = Image(img_path, width=w_in*inch, height=h_in*inch)
    img.hAlign = 'CENTER'
    return img


def md_to_pdf(md_path, pdf_path):
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

        # 블록 수식 ($$...$$)
        if line.strip().startswith('$$'):
            content_after = line.strip()[2:]
            if content_after.endswith('$$'):
                # 한 줄 블록 수식
                story.append(Spacer(1, 2*mm))
                story.append(make_block_equation(content_after[:-2]))
                story.append(Spacer(1, 2*mm))
                i += 1
                continue
            if in_math_block:
                math_text = '\n'.join(math_buf)
                story.append(Spacer(1, 2*mm))
                story.append(make_block_equation(math_text))
                story.append(Spacer(1, 2*mm))
                math_buf = []
                in_math_block = False
            else:
                in_math_block = True
                if content_after:
                    math_buf.append(content_after)
            i += 1
            continue

        if in_math_block:
            if line.strip().endswith('$$'):
                math_buf.append(line.strip()[:-2])
                math_text = '\n'.join(math_buf)
                story.append(Spacer(1, 2*mm))
                story.append(make_block_equation(math_text))
                story.append(Spacer(1, 2*mm))
                math_buf = []
                in_math_block = False
            else:
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
            story.append(make_paragraph_with_inline_math(line[2:], s_title))
        elif line.startswith('## '):
            story.append(make_paragraph_with_inline_math(line[3:], s_h1))
        elif line.startswith('### '):
            story.append(make_paragraph_with_inline_math(line[4:], s_h2))
        elif line.startswith('#### '):
            story.append(make_paragraph_with_inline_math(line[5:], s_h3))
        elif line.startswith('**저자:**') or line.startswith('**지도:**') or line.startswith('**작성일:**'):
            story.append(make_paragraph_with_inline_math(line, s_meta))
        elif line.startswith('- '):
            story.append(make_paragraph_with_inline_math('• ' + line[2:], s_bullet))
        elif re.match(r'^\d+\.\s', line):
            story.append(make_paragraph_with_inline_math(line, s_bullet))
        else:
            story.append(make_paragraph_with_inline_math(line, s_body))

        i += 1

    doc.build(story)
    print(f"PDF: {pdf_path}")


if __name__ == "__main__":
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        md_files = [sys.argv[1]]
    else:
        import glob
        md_files = sorted(glob.glob(os.path.join(docs_dir, 'academic_paper_step*.md')))

    for md in md_files:
        pdf = md.replace('.md', '.pdf')
        md_to_pdf(md, pdf)
