"""
학술 논문 PDF 생성 스크립트
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.colors import HexColor, black, grey, white
from reportlab.lib import colors

OUTPUT = os.path.join(os.path.dirname(__file__), "paper.pdf")

# ── 스타일 ──
styles = getSampleStyleSheet()

s_title = ParagraphStyle('PaperTitle', parent=styles['Title'],
    fontSize=18, leading=22, spaceAfter=6, alignment=TA_CENTER)
s_subtitle = ParagraphStyle('Sub', parent=styles['Normal'],
    fontSize=10, leading=14, alignment=TA_CENTER, textColor=HexColor('#555555'))
s_author = ParagraphStyle('Author', parent=styles['Normal'],
    fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=4)
s_h1 = ParagraphStyle('H1', parent=styles['Heading1'],
    fontSize=14, leading=18, spaceBefore=18, spaceAfter=8,
    textColor=HexColor('#1a5276'))
s_h2 = ParagraphStyle('H2', parent=styles['Heading2'],
    fontSize=12, leading=15, spaceBefore=12, spaceAfter=6,
    textColor=HexColor('#2c3e50'))
s_body = ParagraphStyle('Body', parent=styles['Normal'],
    fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6)
s_caption = ParagraphStyle('Caption', parent=styles['Normal'],
    fontSize=9, leading=12, alignment=TA_CENTER, textColor=HexColor('#555555'),
    spaceBefore=4, spaceAfter=10)
s_bullet = ParagraphStyle('Bullet', parent=s_body,
    leftIndent=20, bulletIndent=10, spaceAfter=3)
s_small = ParagraphStyle('Small', parent=styles['Normal'],
    fontSize=8, leading=10, textColor=HexColor('#666666'))

def tbl(data, col_widths=None):
    """간단한 테이블 생성"""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t

def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm, leftMargin=2.5*cm, rightMargin=2.5*cm)

    story = []
    W = doc.width

    # ═══════════════════════════════════════════
    # TITLE
    # ═══════════════════════════════════════════
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "Topological Data Analysis를 활용한 음악 구조 분석 및<br/>"
        "위상 구조 보존 기반 AI 작곡 파이프라인",
        s_title))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "TDA-Based Music Structure Analysis and Topology-Preserving AI Composition Pipeline",
        s_subtitle))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("김민주", s_author))
    story.append(Paragraph(
        "지도교수: 정재훈 (KIAS)", s_subtitle))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="60%", thickness=1, color=HexColor('#cccccc')))
    story.append(Spacer(1, 6*mm))

    # ═══════════════════════════════════════════
    # ABSTRACT
    # ═══════════════════════════════════════════
    story.append(Paragraph("Abstract", s_h1))
    story.append(Paragraph(
        "본 논문에서는 사카모토 류이치의 'hibari'를 대상으로, Persistent Homology를 "
        "이용하여 음악의 위상 구조(cycle)를 추출하고, 이 구조를 보존하면서 새로운 "
        "음악을 생성하는 전체 파이프라인을 제시한다. 선행연구(정재훈 외, 2024)의 "
        "방법론을 기반으로 하되, (1) 거리 함수의 다양화(Tonnetz, Voice-leading, DFT), "
        "(2) 위상 구조 보존도 정량화, (3) 딥러닝 기반 음악 생성, (4) 인터랙티브 "
        "대시보드 구축 등을 추가로 수행하였다. 실험 결과, Tonnetz 거리와 FC 신경망의 "
        "조합이 원곡 pitch 분포와의 JS divergence 0.002를 달성하여 가장 우수한 "
        "성능을 보였다.",
        s_body))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "<b>키워드:</b> Topological Data Analysis, Persistent Homology, "
        "Vietoris-Rips Complex, Tonnetz, AI 작곡, 중첩행렬, 사카모토 류이치",
        ParagraphStyle('kw', parent=s_body, fontSize=9, textColor=HexColor('#555555'))))

    # ═══════════════════════════════════════════
    # 1. INTRODUCTION
    # ═══════════════════════════════════════════
    story.append(Paragraph("1. 서론", s_h1))
    story.append(Paragraph(
        "인공지능 음악 작곡은 대부분 대량의 음악 데이터를 학습하여 통계적으로 유사한 "
        "음악을 생성하는 블랙박스 접근법을 취한다. 이에 반해, 본 연구는 단일 곡의 "
        "수학적 구조를 분석하고, 그 구조를 명시적으로 보존하면서 새로운 음악을 "
        "생성하는 '설명 가능한' 작곡 방법론을 제시한다.",
        s_body))
    story.append(Paragraph(
        "선행연구(정재훈, 이동진, Mai Lan Tran)에서는 국악(수연장지곡)의 음악 네트워크에 "
        "Persistent Homology를 적용하여 cycle 구조를 발견하고, 이를 중첩행렬로 시각화한 후 "
        "Algorithm 1(확률적 샘플링)과 Algorithm 2(신경망)로 음악을 생성하는 프레임워크를 "
        "제안하였다. 본 연구는 이 프레임워크를 사카모토 류이치의 'hibari'에 적용하면서, "
        "다음의 추가적 기여를 수행하였다.",
        s_body))

    # ═══════════════════════════════════════════
    # 기여 분리
    # ═══════════════════════════════════════════
    story.append(Paragraph("1.1 기여 분리: 연구자 vs AI 보조", s_h2))

    story.append(Paragraph("<b>연구자(김민주)가 설정한 방법론 및 방향성:</b>", s_body))
    contribs_human = [
        "TDA 기반 음악 분석 프레임워크의 hibari 적용 설계",
        "rate 파라미터를 이용한 위상 구조 탐색 전략 수립",
        "timeflow / simul / complex 가중치 체계 설계 및 해석",
        "중첩행렬 → 음악 생성의 개념적 연결고리 정의",
        "Tonnetz/Voice-leading/DFT 등 음악적 거리 함수 도입 제안",
        "고아 note 문제의 발견 및 chord 기반 보충 아이디어",
        "모듈 단위 생성, onset 간격 제약 등 음악적 제약조건 제안",
        "발표자료(수학탐구A) 작성 및 연구 방향 수립",
    ]
    for c in contribs_human:
        story.append(Paragraph(f"- {c}", s_bullet))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("<b>AI 보조(Claude)가 구현한 영역:</b>", s_body))
    contribs_ai = [
        "0-cycle 버그 진단 및 수정 (preprocessing, weights, symmetrize)",
        "generateBarcode의 Numpy 벡터화(2.5x) 및 Ripser 통합(45x)",
        "위상 구조 보존도 지표 설계 (Jaccard + Correlation + Betti curve)",
        "Greedy Forward Selection 기반 cycle subset 선택 알고리즘",
        "Algorithm 2 데이터 정합성 수정 (L_encoded vs L_onehot)",
        "DL 모델 3종 구현 (FC, LSTM, Transformer) + Data Augmentation",
        "하이퍼파라미터 튜닝 (30개 조합 grid search)",
        "Tonnetz/Voice-leading/DFT 거리 함수 구현 + 플러그인 시스템",
        "평가 지표 모듈 (note coverage, KL/JS divergence)",
        "Streamlit 인터랙티브 대시보드 구축",
        "코드 일반화 (MIDI 자동 감지, 하드코딩 제거)",
    ]
    for c in contribs_ai:
        story.append(Paragraph(f"- {c}", s_bullet))

    # ═══════════════════════════════════════════
    # 2. METHODOLOGY
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("2. 방법론", s_h1))

    story.append(Paragraph("2.1 음악 네트워크와 거리 행렬", s_h2))
    story.append(Paragraph(
        "MIDI 파일을 8분음표 단위로 양자화한 후, 각 note를 (pitch, duration) 쌍으로 "
        "정의한다. hibari에서는 23종의 고유 note와 17종의 고유 chord가 발견된다. "
        "두 note 간의 거리는 기존 방법(빈도 역수)에 더하여 음악 이론 기반 거리를 "
        "도입하였다.",
        s_body))

    story.append(tbl([
        ['거리 함수', '원리', '수학적 정의'],
        ['빈도 역수', '연달아 등장한 횟수의 역수', 'd = 1/w(i,j)'],
        ['Tonnetz', '장3도/완전5도 격자 위 BFS 거리', 'd = BFS(pc1, pc2) on Z/12'],
        ['Voice-leading', '반음 수 차이', 'd = |p1 - p2|'],
        ['DFT', 'Fourier 계수 L2 거리', 'd = ||DFT(pc1) - DFT(pc2)||'],
    ], col_widths=[W*0.18, W*0.35, W*0.42]))
    story.append(Paragraph("Table 1. 거리 함수 비교", s_caption))

    story.append(Paragraph(
        "복합 거리는 d_hybrid = alpha * d_freq + (1-alpha) * d_musical로 정의하며, "
        "alpha=0.5를 기본으로 사용한다.",
        s_body))

    story.append(Paragraph("2.2 Persistent Homology", s_h2))
    story.append(Paragraph(
        "거리 행렬로부터 Vietoris-Rips complex를 구축하고, pHcol 알고리즘으로 "
        "persistent homology를 계산한다. rate 파라미터를 0.0에서 1.5까지 변화시키며 "
        "각 rate에서의 barcode를 수집하여, cycle의 출현/소멸 패턴을 추적한다. "
        "계산 최적화를 위해 Ripser(C++ 기반, 45배 속도 향상)를 통합하였다.",
        s_body))

    story.append(Paragraph("2.3 중첩행렬과 Cycle 선택", s_h2))
    story.append(Paragraph(
        "발견된 cycle들이 각 시점에서 활성화되는지를 나타내는 이진 행렬(T x C)을 "
        "중첩행렬이라 한다. 전체 cycle 중 최적 subset을 선택하기 위해 다음 세 가지 "
        "지표의 가중 평균(보존도)을 정의하였다: Note Pool Jaccard(50%), "
        "Overlap Correlation(30%), Betti Curve Score(20%). "
        "Greedy Forward Selection으로 보존도 90%에 도달하는 최소 K를 결정한다.",
        s_body))

    story.append(Paragraph("2.4 음악 생성", s_h2))
    story.append(Paragraph(
        "<b>Algorithm 1(확률적 샘플링):</b> 각 시점에서 활성 cycle의 note pool에서 "
        "빈도 기반으로 랜덤 샘플링한다. 고아 note(어떤 cycle에도 미포함) 보충과 "
        "onset 간격 제약(min_onset_gap)을 추가하였다.",
        s_body))
    story.append(Paragraph(
        "<b>Algorithm 2(딥러닝):</b> 중첩행렬 → 원곡 note 매핑을 신경망이 학습한다. "
        "FC(시점별 독립), LSTM(시간 패턴), Transformer(장거리 관계) 3종을 구현하였다. "
        "BCEWithLogitsLoss(다중 레이블)를 사용하고, Subset/Circular Shift/Noise "
        "Injection으로 10배 data augmentation을 수행한다.",
        s_body))

    # ═══════════════════════════════════════════
    # 3. RESULTS
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("3. 실험 결과", s_h1))

    story.append(Paragraph("3.1 거리 함수 x DL 모델 비교", s_h2))
    story.append(Paragraph(
        "4가지 거리 함수와 3가지 DL 모델의 조합(12개)에 대해 JS divergence를 "
        "측정하였다. gap=3(1.5박 onset 간격), 50 epochs, 10x augmentation 조건이다.",
        s_body))

    story.append(tbl([
        ['거리 함수', 'Cycles', '90% K', 'FC', 'LSTM', 'Transformer'],
        ['빈도 only', '43', '17', '0.014', '0.268', '0.011'],
        ['Tonnetz', '46', '15', '0.002', '0.267', '0.009'],
        ['Voice-leading', '22', '11', '0.007', '0.277', '0.016'],
        ['DFT', '20', '12', '0.012', '0.257', '0.014'],
    ], col_widths=[W*0.18, W*0.1, W*0.1, W*0.15, W*0.15, W*0.18]))
    story.append(Paragraph(
        "Table 2. 거리 함수 x DL 모델 JS divergence (낮을수록 원곡과 유사)", s_caption))

    story.append(Paragraph(
        "Tonnetz + FC 조합이 JS=0.002로 최우수 성능을 보였다. FC 모델이 전반적으로 "
        "우세한 이유는 학습 데이터가 1088 시점(10x augmentation 후 ~10,000)으로 "
        "복잡한 시퀀스 모델(LSTM, Transformer)에 비해 부족하기 때문이다. "
        "LSTM은 모든 metric에서 JS > 0.25로 사실상 학습에 실패하였다.",
        s_body))

    story.append(Paragraph("3.2 개선 이력", s_h2))
    story.append(tbl([
        ['#', '단계', '핵심 수치'],
        ['1', '0-cycle 버그 수정', '0 -> 48 cycles'],
        ['2', 'Barcode 최적화 (Ripser)', '72ms -> 1.6ms (45x)'],
        ['3', 'Cycle subset 선택', '17/48 = 90% 보존'],
        ['4', '고아 note 보충', 'KL 23% 개선'],
        ['5', 'Data augmentation (10x)', 'val_loss 0.282'],
        ['6', 'HP 튜닝 (30 조합)', 'JS 0.0015'],
        ['7', '다중 search (12 조합)', '85개 고유 cycle'],
        ['8', 'Tonnetz 거리', 'JS 0.002 (18x 개선)'],
        ['9', 'Onset 간격 제약', '선율적 생성 (gap=3)'],
    ], col_widths=[W*0.06, W*0.4, W*0.4]))
    story.append(Paragraph("Table 3. 단계별 개선 이력", s_caption))

    story.append(Paragraph("3.3 고아 Note 문제", s_h2))
    story.append(Paragraph(
        "note 5(A3, dur=6), 8(C4, dur=6), 22(G5, dur=1)는 어떤 cycle에도 속하지 않는다. "
        "이들은 거리가 먼 '색채음'으로, 빈도 역수 기반 거리에서는 다른 note와의 "
        "연결이 약하다. chord 기반 보충(해당 chord 활성 시점에 30% 확률로 주입)으로 "
        "KL divergence를 0.323에서 0.250으로 개선하였다.",
        s_body))

    # ═══════════════════════════════════════════
    # 4. DISCUSSION
    # ═══════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("4. 논의: 방법론의 한계와 비판적 검토", s_h1))

    story.append(Paragraph("4.1 거리 정의의 근본적 문제", s_h2))
    story.append(Paragraph(
        "현재 파이프라인의 기본 거리(빈도 역수)는 곡의 통계적 특성만 반영하며, "
        "음악 이론적 관계를 포착하지 못한다. Tonnetz 등의 도입으로 개선되었으나, "
        "'빈도 거리와 음악적 거리의 alpha 혼합'이 최선인지는 이론적 근거가 부족하다. "
        "특히 alpha=0.5라는 선택은 경험적이며, 곡이나 장르에 따라 최적값이 "
        "달라질 수 있다.",
        s_body))

    story.append(Paragraph("4.2 중첩행렬의 정보 손실", s_h2))
    story.append(Paragraph(
        "중첩행렬은 cycle의 활성 여부를 이진(0/1)으로 표현하므로, cycle의 "
        "'강도'나 '위상'을 잃는다. 같은 cycle이 활성화되어 있어도 birth/death "
        "시점에 따라 의미가 다를 수 있으나, 이 정보는 중첩행렬에 반영되지 않는다.",
        s_body))

    story.append(Paragraph("4.3 LSTM 학습 실패", s_h2))
    story.append(Paragraph(
        "LSTM이 전 metric에서 JS > 0.25인 것은 심각한 한계이다. 1088 시점을 "
        "하나의 시퀀스로 학습하는 현재 방식은 시퀀스 모델에 적합하지 않다. "
        "선행연구에서 제안한 '모듈(4마디) 단위 학습'이 이 문제의 해결책일 수 있다. "
        "4마디 = 32 eighth notes 단위로 시퀀스를 나누면 학습 샘플이 ~34개로 늘어나고, "
        "LSTM이 모듈 내부의 선율 패턴을 학습할 수 있다.",
        s_body))

    story.append(Paragraph("4.4 평가 지표의 한계", s_h2))
    story.append(Paragraph(
        "JS divergence는 pitch 빈도 분포의 유사도만 측정하며, 음악적 '좋음'과 "
        "직접 대응되지 않는다. JS=0.002라도 시간적 구조(프레이징, 텐션-릴리스)가 "
        "원곡과 다를 수 있다. 청취 실험(listening test)이나 음악 이론 기반 평가 "
        "(예: 화성 진행 정합성)가 필요하다.",
        s_body))

    story.append(Paragraph("4.5 단일 곡 의존성", s_h2))
    story.append(Paragraph(
        "전체 파이프라인이 hibari 한 곡에 최적화되어 있다. solo_notes=59, "
        "solo_timepoints=32 등의 파라미터는 자동 감지가 어렵고, 다른 곡에 적용할 때 "
        "수동 설정이 필요하다. 특히 8분음표 양자화가 불가능한 곡(복잡한 리듬)에 대한 "
        "일반화는 미해결 과제이다.",
        s_body))

    # ═══════════════════════════════════════════
    # 5. FUTURE WORK
    # ═══════════════════════════════════════════
    story.append(Paragraph("5. 향후 연구", s_h1))

    future_items = [
        ("<b>모듈 단위 생성:</b> 전체 시퀀스 대신 4마디 모듈을 예측하고 조합하는 방식. "
         "LSTM/Transformer의 학습 데이터 증가 및 반복 구조 학습에 유리."),
        ("<b>Digraph 도입:</b> 현재 가중치 행렬은 대칭(무방향)이나, 실제 음악에서 "
         "A→B와 B→A는 다른 의미. 방향 그래프 기반 거리 정의 검토."),
        ("<b>청취 실험:</b> JS divergence 외에 인간 평가자의 주관적 평가를 통한 "
         "음악적 품질 검증."),
        ("<b>인터랙티브 seed 편집:</b> 사용자가 중첩행렬을 직접 그려서 "
         "음악을 생성하는 UI 구현. 이미 Streamlit 대시보드의 기반이 구축됨."),
        ("<b>다른 곡 일반화:</b> hibari 외의 사카모토 곡, 또는 국악에 적용하여 "
         "방법론의 일반성 검증. 양자화 단위 자동 감지 개선 필요."),
        ("<b>H2(void) 활용:</b> 현재 H1(cycle)만 주로 사용. H2의 음악적 의미를 "
         "규명하고 생성에 활용하는 방안 탐색."),
    ]
    for item in future_items:
        story.append(Paragraph(f"- {item}", s_bullet))

    # ═══════════════════════════════════════════
    # 6. CONCLUSION
    # ═══════════════════════════════════════════
    story.append(Paragraph("6. 결론", s_h1))
    story.append(Paragraph(
        "본 연구는 Persistent Homology 기반 음악 구조 분석 프레임워크를 확장하여, "
        "음악 이론 기반 거리 함수(Tonnetz, Voice-leading, DFT), 위상 구조 보존도 "
        "정량화, 딥러닝 음악 생성, 인터랙티브 대시보드를 포함하는 종합적 파이프라인을 "
        "구축하였다. Tonnetz 거리가 hibari의 화성 구조를 가장 잘 포착하며, "
        "FC 신경망과의 조합에서 JS divergence 0.002의 최우수 결과를 달성하였다. "
        "향후 모듈 단위 생성과 다른 곡으로의 일반화를 통해 방법론의 확장성을 "
        "검증할 계획이다.",
        s_body))

    # ═══════════════════════════════════════════
    # REFERENCES
    # ═══════════════════════════════════════════
    story.append(Paragraph("참고문헌", s_h1))
    refs = [
        "[1] 이동진, Mai Lan Tran, 정재훈, '국악의 기하학적 구조와 인공지능 작곡', 2024.",
        "[2] Mai Lan Tran et al., 'Topological Data Analysis of Korean Music in Jeongganbo: A Cycle Structure', arXiv:2103.06620, 2021.",
        "[3] Mai Lan Tran et al., 'Machine Composition of Korean Music via TDA and ANN', arXiv:2211.17298, 2024.",
        "[4] Michael J. Catanzaro, 'Generalized Tonnetze', arXiv:1612.03519, 2016.",
        "[5] Dmitri Tymoczko, 'The Generalized Tonnetz', J. Music Theory 56:1, 2012.",
        "[6] Tymoczko, 'Set-Class Similarity, Voice Leading, and the Fourier Transform', J. Music Theory 52/2, 2008.",
        "[7] Louis Bigo et al., 'Computation and Visualization of Musical Structures in Chord-Based Simplicial Complexes', MCM 2013.",
        "[8] Gunnar Carlsson, 'Topology and data', Bull. AMS 46(2), 2009.",
    ]
    for r in refs:
        story.append(Paragraph(r, ParagraphStyle('ref', parent=s_body, fontSize=9, spaceAfter=3)))

    # BUILD
    doc.build(story)
    print(f"PDF 생성 완료: {OUTPUT}")

if __name__ == "__main__":
    build()
