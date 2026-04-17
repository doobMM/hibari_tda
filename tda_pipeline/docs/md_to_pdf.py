"""
portfolio_report.md -> portfolio_report.pdf
한국어 지원 (맑은 고딕) + 이미지 삽입 + 작성자 영역 박스
"""

import re
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, PageBreak, Image, KeepTogether, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 등록 ────────────────────────────────────────────────
FONT_DIR = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("Malgun",  f"{FONT_DIR}/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunB", f"{FONT_DIR}/malgunbd.ttf"))
pdfmetrics.registerFont(TTFont("MalgunL", f"{FONT_DIR}/malgunsl.ttf"))
pdfmetrics.registerFontFamily("Malgun", normal="Malgun", bold="MalgunB",
                              italic="MalgunL", boldItalic="MalgunB")

# ── 페이지 설정 ───────────────────────────────────────────────
W, H = A4
MARGIN_L, MARGIN_R = 22*mm, 22*mm
MARGIN_T, MARGIN_B = 24*mm, 22*mm
BODY_W = W - MARGIN_L - MARGIN_R

FIGURES_DIR = Path(r"C:\WK14\tda_pipeline\docs\figures")


# ── 커스텀 Flowable: 둥근 모서리 색 박스 ─────────────────────
class ColorBox(Flowable):
    """텍스트를 배경색 박스 안에 표시"""
    def __init__(self, text, width, bg_color, border_color, font="Malgun",
                 font_size=10, leading=16, padding=10):
        super().__init__()
        self.text = text
        self.box_width = width
        self.bg = bg_color
        self.border = border_color
        self.font = font
        self.font_size = font_size
        self.leading = leading
        self.pad = padding
        # 높이 계산
        lines = text.split("\n")
        self.height = len(lines) * leading + 2 * padding
        self.width = width

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.border)
        c.setFillColor(self.bg)
        c.setLineWidth(1.2)
        c.roundRect(0, 0, self.box_width, self.height, 6, fill=1, stroke=1)
        # 텍스트
        c.setFillColor(colors.HexColor("#444444"))
        c.setFont(self.font, self.font_size)
        y = self.height - self.pad - self.font_size
        for line in self.text.split("\n"):
            c.drawString(self.pad, y, line)
            y -= self.leading


# ── 스타일 정의 ───────────────────────────────────────────────
def ps(name, **kw):
    defaults = dict(fontName="Malgun", fontSize=10, leading=16,
                    textColor=colors.HexColor("#1a1a1a"), spaceAfter=4)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

S = {
    "title": ps("title", fontName="MalgunB", fontSize=22, leading=30,
                textColor=colors.HexColor("#0d1b2a"), alignment=TA_CENTER, spaceAfter=6),
    "subtitle": ps("subtitle", fontName="Malgun", fontSize=13, leading=20,
                   textColor=colors.HexColor("#3d5a80"), alignment=TA_CENTER, spaceAfter=4),
    "meta": ps("meta", fontSize=9.5, leading=15,
               textColor=colors.HexColor("#666666"), alignment=TA_CENTER, spaceAfter=2),
    "h2": ps("h2", fontName="MalgunB", fontSize=14.5, leading=22,
             textColor=colors.HexColor("#0d1b2a"), spaceBefore=12, spaceAfter=4),
    "h3": ps("h3", fontName="MalgunB", fontSize=11.5, leading=18,
             textColor=colors.HexColor("#1d3557"), spaceBefore=8, spaceAfter=3),
    "body": ps("body", fontSize=10, leading=17, alignment=TA_JUSTIFY, spaceAfter=6),
    "quote": ps("quote", fontName="MalgunL", fontSize=9.5, leading=16,
                textColor=colors.HexColor("#444444"), leftIndent=14, rightIndent=14,
                backColor=colors.HexColor("#f5f5f5"), borderPadding=8, spaceAfter=8),
    "bullet": ps("bullet", fontSize=10, leading=16, leftIndent=16, bulletIndent=4, spaceAfter=3),
    "caption": ps("caption", fontName="MalgunL", fontSize=8.5, leading=13,
                  textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
                  spaceBefore=2, spaceAfter=10),
    "toc": ps("toc", fontSize=10, leading=18, leftIndent=8, spaceAfter=1),
}


# ── 인라인 마크다운 → XML ─────────────────────────────────────
def inl(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'<u>\1</u>', text)
    return text


# ── 표 파싱 ───────────────────────────────────────────────────
def make_table(lines: list[str]) -> Table | None:
    rows = []
    for line in lines:
        if re.match(r'^\|[-:| ]+\|$', line.strip()):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cols)
    if not rows:
        return None

    n_cols = max(len(r) for r in rows)
    data = []
    for ri, r in enumerate(rows):
        while len(r) < n_cols:
            r.append("")
        style = S["body"] if ri > 0 else ps("th", fontName="MalgunB", fontSize=9.5,
                                              leading=14, textColor=colors.HexColor("#0d1b2a"))
        data.append([Paragraph(inl(c), style) for c in r])

    col_w = BODY_W / n_cols
    t = Table(data, colWidths=[col_w]*n_cols, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),  colors.HexColor("#e8f0fe")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9fafc")]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 6),
        ("RIGHTPADDING",   (0,0), (-1,-1), 6),
    ]))
    return t


# ── 이미지 삽입 ───────────────────────────────────────────────
def make_image(img_path: str) -> Image | None:
    # ![alt](path) 에서 추출된 path
    full = FIGURES_DIR / Path(img_path).name
    if not full.exists():
        # figures/ 접두사가 이미 포함된 경우
        full = Path(r"C:\WK14\tda_pipeline\docs") / img_path
    if not full.exists():
        return None
    # 이미지 크기 조정: 본문 폭에 맞춤
    img = Image(str(full))
    iw, ih = img.imageWidth, img.imageHeight
    scale = min(BODY_W / iw, 140*mm / ih)  # 최대 높이 140mm
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    img.hAlign = "CENTER"
    return img


# ── 마크다운 → Flowable 리스트 ────────────────────────────────
def parse_md(text: str) -> list:
    lines = text.splitlines()
    story = []
    i = 0
    table_buf = []
    in_author = False
    author_lines = []
    title_done = False

    def flush_table():
        if table_buf:
            t = make_table(table_buf)
            if t:
                story.append(Spacer(1, 4))
                story.append(t)
                story.append(Spacer(1, 8))
            table_buf.clear()

    while i < len(lines):
        line = lines[i]

        # ── QR 코드 섹션 ──────────────────────────────────────
        if line.strip().startswith("@@QR_SECTION@@"):
            flush_table()
            # QR 섹션 내의 이미지와 텍스트를 파싱
            i += 1
            qr_items = []  # (img_path, label_lines)
            current_label = []
            current_img = None
            while i < len(lines) and not lines[i].strip().startswith("@@END_QR_SECTION@@"):
                qline = lines[i].strip()
                m_qimg = re.match(r'^!\[(.+?)\]\((.+?)\)', qline)
                if m_qimg:
                    if current_img:
                        qr_items.append((current_img, current_label))
                    current_img = m_qimg.group(2)
                    current_label = []
                elif qline:
                    current_label.append(qline)
                i += 1
            if current_img:
                qr_items.append((current_img, current_label))
            i += 1  # skip @@END_QR_SECTION@@

            # 두 QR을 나란히 배치하는 테이블
            qr_cells = []
            for img_path, labels in qr_items:
                cell_content = []
                img = make_image(img_path)
                if img:
                    img.drawWidth = 38*mm
                    img.drawHeight = 38*mm
                    cell_content.append(img)
                for lb in labels:
                    txt = inl(lb)
                    cell_content.append(Paragraph(txt, ps("qrlabel",
                        fontName="Malgun", fontSize=8.5, leading=13,
                        textColor=colors.HexColor("#333333"),
                        alignment=TA_CENTER, spaceAfter=1)))
                qr_cells.append(cell_content)

            if len(qr_cells) == 2:
                qr_table = Table([[qr_cells[0], qr_cells[1]]],
                    colWidths=[BODY_W/2, BODY_W/2])
                qr_table.setStyle(TableStyle([
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("LEFTPADDING", (0,0), (-1,-1), 10),
                    ("RIGHTPADDING", (0,0), (-1,-1), 10),
                ]))
                story.append(Spacer(1, 8))
                story.append(qr_table)
                story.append(Spacer(1, 8))
            continue

        # ── 작성자 영역 시작 ───────────────────────────────────
        if line.strip().startswith("@@AUTHOR_SECTION@@"):
            flush_table()
            in_author = True
            author_lines = []
            i += 1
            continue

        if line.strip().startswith("@@END_AUTHOR_SECTION@@"):
            in_author = False
            content = "\n".join(author_lines)
            box = ColorBox(content, BODY_W,
                           bg_color=colors.HexColor("#fff8e1"),
                           border_color=colors.HexColor("#f9a825"),
                           font="Malgun", font_size=10, leading=16, padding=12)
            story.append(Spacer(1, 6))
            story.append(box)
            story.append(Spacer(1, 8))
            i += 1
            continue

        if in_author:
            author_lines.append(line)
            i += 1
            continue

        # ── 코드 블록 (```...```) — 비전공자 보고서라 최소화 ──
        if line.strip().startswith("```"):
            # 코드 블록은 이 보고서에 없으므로 그냥 건너뜀
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue

        # ── 표 행 ─────────────────────────────────────────────
        if line.strip().startswith("|"):
            table_buf.append(line)
            i += 1
            continue
        else:
            flush_table()

        # ── 이미지 ─────────────────────────────────────────────
        m_img = re.match(r'^!\[(.+?)\]\((.+?)\)', line.strip())
        if m_img:
            alt, path = m_img.group(1), m_img.group(2)
            img = make_image(path)
            if img:
                story.append(Spacer(1, 6))
                story.append(img)
            i += 1
            continue

        # ── 이미지 캡션 (*그림 X. ...*)
        if line.strip().startswith("*그림") and line.strip().endswith("*"):
            text = inl(line.strip().strip("*"))
            story.append(Paragraph(text, S["caption"]))
            i += 1
            continue

        # ── 수평선 ─────────────────────────────────────────────
        if re.match(r'^---+$', line.strip()):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=colors.HexColor("#dddddd")))
            story.append(Spacer(1, 4))
            i += 1
            continue

        # ── H1 ────────────────────────────────────────────────
        if line.startswith("# ") and not line.startswith("## "):
            flush_table()
            text = inl(line[2:].strip())
            if not title_done:
                story.append(Spacer(1, 30))
                story.append(Paragraph(text, S["title"]))
                title_done = True
            else:
                story.append(PageBreak())
                story.append(Paragraph(text, S["title"]))
            i += 1
            continue

        # ── H2 ────────────────────────────────────────────────
        if line.startswith("## ") and not line.startswith("### "):
            flush_table()
            text = inl(line[3:].strip())
            story.append(Spacer(1, 6))
            story.append(Paragraph(text, S["h2"]))
            story.append(HRFlowable(width="100%", thickness=1.0,
                                    color=colors.HexColor("#3d5a80")))
            story.append(Spacer(1, 3))
            i += 1
            continue

        # ── H3 ────────────────────────────────────────────────
        if line.startswith("### "):
            flush_table()
            text = inl(line[4:].strip())
            story.append(Paragraph(text, S["h3"]))
            i += 1
            continue

        # ── 인용문 ─────────────────────────────────────────────
        if line.startswith("> "):
            flush_table()
            text = inl(line[2:].strip())
            story.append(Paragraph(text, S["quote"]))
            i += 1
            continue

        # ── 불릿 ──────────────────────────────────────────────
        if re.match(r'^[-*]\s+', line):
            flush_table()
            text = inl(re.sub(r'^[-*]\s+', '', line))
            story.append(Paragraph(f"\u2022  {text}", S["bullet"]))
            i += 1
            continue

        # ── 번호 목록 ─────────────────────────────────────────
        m = re.match(r'^(\d+)\.\s+(.+)', line)
        if m:
            flush_table()
            num, text = m.group(1), inl(m.group(2))
            story.append(Paragraph(f"{num}.  {text}", S["bullet"]))
            i += 1
            continue

        # ── 빈 줄 ─────────────────────────────────────────────
        if not line.strip():
            story.append(Spacer(1, 4))
            i += 1
            continue

        # ── 일반 문단 ─────────────────────────────────────────
        text = inl(line.strip())
        if text:
            story.append(Paragraph(text, S["body"]))
        i += 1

    flush_table()
    return story


# ── 페이지 장식 ───────────────────────────────────────────────
def page_template(canvas, doc):
    canvas.saveState()
    pn = canvas.getPageNumber()

    # 하단 페이지 번호
    canvas.setFont("Malgun", 8)
    canvas.setFillColor(colors.HexColor("#999999"))
    canvas.drawCentredString(W/2, 12*mm, f"- {pn} -")

    # 상단 헤더 (2페이지부터)
    if pn > 1:
        canvas.setFont("MalgunL", 7.5)
        canvas.setFillColor(colors.HexColor("#bbbbbb"))
        canvas.drawString(MARGIN_L, H - 16*mm,
                          "한 곡의 수학적 지문을 복원한다는 것")
        canvas.drawRightString(W - MARGIN_R, H - 16*mm,
                               "김민주 | KIAS 초학제 독립연구단")
        # 헤더 하단 가는 선
        canvas.setStrokeColor(colors.HexColor("#dddddd"))
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_L, H - 17.5*mm, W - MARGIN_R, H - 17.5*mm)

    canvas.restoreState()


# ── 메인 ─────────────────────────────────────────────────────
def build_pdf():
    md_path  = r"C:\WK14\tda_pipeline\docs\portfolio_report.md"
    pdf_path = r"C:\WK14\tda_pipeline\docs\portfolio_report.pdf"

    md_text = Path(md_path).read_text(encoding="utf-8")

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="한 곡의 수학적 지문을 복원한다는 것",
        author="김민주",
        subject="TDA Music Analysis — Portfolio Report",
    )

    story = parse_md(md_text)
    doc.build(story, onFirstPage=page_template, onLaterPages=page_template)
    print(f"PDF 생성 완료: {pdf_path}")

    # 파일 크기 출력
    size_kb = os.path.getsize(pdf_path) // 1024
    print(f"파일 크기: {size_kb} KB")


if __name__ == "__main__":
    build_pdf()
