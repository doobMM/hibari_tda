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

# 폰트 — 나눔고딕 사용
from reportlab.pdfbase.pdfmetrics import registerFontFamily

NANUM_REGULAR = 'C:/Users/82104/AppData/Local/Microsoft/Windows/Fonts/NanumGothic.ttf'
# Bold는 docs/ 폴더에 다운로드된 Google Fonts 버전 사용
_BOLD_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NanumGothic-Bold.ttf')
NANUM_BOLD = _BOLD_LOCAL if os.path.exists(_BOLD_LOCAL) else NANUM_REGULAR

pdfmetrics.registerFont(TTFont('Nanum', NANUM_REGULAR))
pdfmetrics.registerFont(TTFont('NanumBd', NANUM_BOLD))

# <b>...</b> 태그가 자동으로 NanumBd를 쓰도록 family 등록
registerFontFamily('Nanum', normal='Nanum', bold='NanumBd', italic='Nanum', boldItalic='NanumBd')

# 호환을 위해 Malgun이라는 이름으로도 등록 (기존 코드 호환)
pdfmetrics.registerFont(TTFont('Malgun', NANUM_REGULAR))
pdfmetrics.registerFont(TTFont('MalgunBd', NANUM_BOLD))
registerFontFamily('Malgun', normal='Malgun', bold='MalgunBd', italic='Malgun', boldItalic='MalgunBd')

pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))

# matplotlib mathtext 설정 (Computer Modern 비슷하게)
rcParams['mathtext.fontset'] = 'cm'
rcParams['font.family'] = 'serif'

# 수식 캐시 디렉토리
EQ_CACHE_DIR = os.path.join(os.path.dirname(__file__), '_eq_cache')
os.makedirs(EQ_CACHE_DIR, exist_ok=True)


def render_equation(latex_str, display=True, fontsize=14):
    """LaTeX 수식을 PNG로 렌더링하여 (경로, width_pt, height_pt) 반환.

    display=True: 블록 수식 (큰 크기, 가운데)
    display=False: 인라인 수식 (작은 크기)

    width/height는 PDF의 point 단위로 반환되어, reportlab img 태그에서 직접 사용 가능.
    """
    DPI = 200
    key = hashlib.md5(f"{latex_str}|{display}|{fontsize}".encode()).hexdigest()
    cache_path = os.path.join(EQ_CACHE_DIR, f"eq_{key}.png")
    meta_path = cache_path + '.meta'

    if os.path.exists(cache_path) and os.path.exists(meta_path):
        with open(meta_path) as f:
            w_pt, h_pt = map(float, f.read().split(','))
        return cache_path, w_pt, h_pt

    fig = plt.figure(figsize=(0.01, 0.01), dpi=DPI)
    fig.patch.set_alpha(0)
    try:
        tex = clean_latex_for_mathtext(latex_str)
        text = fig.text(0, 0, f'${tex}$', fontsize=fontsize,
                        color='black', ha='left', va='bottom')

        fig.canvas.draw()
        bbox = text.get_window_extent()
        w_px = bbox.width + 8
        h_px = bbox.height + 8
        w_in = w_px / DPI
        h_in = h_px / DPI
        fig.set_size_inches(w_in, h_in)

        plt.savefig(cache_path, dpi=DPI, bbox_inches='tight',
                    transparent=True, pad_inches=0.02)
    except Exception as e:
        print(f"  수식 렌더링 실패: {latex_str[:50]}... ({e})")
        plt.close(fig)
        return None, 0, 0
    plt.close(fig)

    # 저장된 PNG의 실제 크기로 PDF point 환산 (1 inch = 72 pt)
    from PIL import Image as PILImage
    pil = PILImage.open(cache_path)
    actual_w, actual_h = pil.size
    w_pt = actual_w / DPI * 72
    h_pt = actual_h / DPI * 72

    with open(meta_path, 'w') as f:
        f.write(f"{w_pt},{h_pt}")

    return cache_path, w_pt, h_pt


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
s_title = ParagraphStyle('T', fontName='NanumBd', fontSize=15, leading=20,
    spaceAfter=10, alignment=TA_CENTER)
s_meta = ParagraphStyle('M', fontName='Nanum', fontSize=9.5, leading=12,
    alignment=TA_CENTER, textColor=HexColor('#555'))
s_h1 = ParagraphStyle('H1', fontName='NanumBd', fontSize=13, leading=17,
    spaceBefore=14, spaceAfter=7, textColor=HexColor('#1a5276'))
s_h2 = ParagraphStyle('H2', fontName='NanumBd', fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=5, textColor=HexColor('#2c3e50'))
s_h3 = ParagraphStyle('H3', fontName='NanumBd', fontSize=10, leading=13,
    spaceBefore=8, spaceAfter=4, textColor=HexColor('#5d6d7e'))
s_body = ParagraphStyle('B', fontName='Nanum', fontSize=9.5, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=5)
s_code = ParagraphStyle('C', fontName='Consolas', fontSize=8.5, leading=11,
    leftIndent=15, backColor=HexColor('#f0f0f0'), borderPadding=4,
    spaceBefore=4, spaceAfter=4)
s_bullet = ParagraphStyle('BL', fontName='Nanum', fontSize=9.5, leading=13.5,
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
    수식 부분은 PDF point 단위로 명시적 width/height를 지정한 이미지로 삽입.

    인라인 수식의 fontsize는 본문 폰트와 균형을 맞춤.
    """
    # 본문 스타일의 폰트 크기에 맞춰 인라인 수식 크기 결정
    body_size = style.fontSize  # pt
    # mathtext의 fontsize=10이 대략 본문 9.5pt와 균형
    inline_fontsize = body_size + 0.5

    parts = parse_inline_with_math(text)
    result = ''
    for ptype, content in parts:
        if ptype == 'text':
            result += parse_inline_markup(content)
        else:
            res = render_equation(content, display=False, fontsize=inline_fontsize)
            if res and res[0]:
                img_path, w_pt, h_pt = res
                # 인라인 수식의 표시 높이를 본문 줄높이에 맞게 제한
                target_h = body_size * 1.4  # 본문 폰트의 약 1.4배 높이로 제한
                if h_pt > target_h:
                    scale = target_h / h_pt
                    w_pt *= scale
                    h_pt *= scale
                # reportlab img 태그에 width/height 명시 (pt 단위)
                # valign으로 baseline 조정
                vshift = -h_pt * 0.20
                result += (f'<img src="{img_path}" '
                           f'width="{w_pt:.1f}" height="{h_pt:.1f}" '
                           f'valign="{vshift:.1f}"/>')
            else:
                result += f'<font name="Consolas" color="#000088">{content}</font>'
    return Paragraph(result, style)


def make_block_equation(latex_str):
    """블록 수식 → 큰 PNG → 가운데 정렬 Image"""
    res = render_equation(latex_str, display=True, fontsize=14)
    if res is None or res[0] is None:
        return Paragraph(f'<font name="Consolas">{latex_str}</font>', s_body)
    img_path, w_pt, h_pt = res

    # 최대 너비 제한 (페이지 본문 폭의 약 90%)
    max_w_pt = 14 * cm / inch * 72  # cm → pt
    if w_pt > max_w_pt:
        scale = max_w_pt / w_pt
        w_pt *= scale
        h_pt *= scale

    img = Image(img_path, width=w_pt, height=h_pt)
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

        # 마크다운 이미지 ![alt](path)
        img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
        if img_match:
            alt = img_match.group(1)
            img_path = img_match.group(2)
            # 상대 경로면 md 파일과 같은 폴더 기준
            if not os.path.isabs(img_path):
                img_path = os.path.join(os.path.dirname(md_path), img_path)
            if os.path.exists(img_path):
                from PIL import Image as PILImage
                pil = PILImage.open(img_path)
                w_px, h_px = pil.size
                # 페이지 폭의 80%를 최대로
                max_w_pt = doc.width * 0.85
                aspect = h_px / w_px
                w_pt = min(max_w_pt, w_px * 72 / 200)
                h_pt = w_pt * aspect
                img_obj = Image(img_path, width=w_pt, height=h_pt)
                img_obj.hAlign = 'CENTER'
                story.append(Spacer(1, 3*mm))
                story.append(img_obj)
                story.append(Spacer(1, 1*mm))
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
