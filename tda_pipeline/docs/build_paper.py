"""
학술 논문 PDF 생성 (한글 폰트 적용)
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUTPUT = os.path.join(os.path.dirname(__file__), "paper.pdf")

# ── 한글 폰트 등록 ──
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBd', 'C:/Windows/Fonts/malgunbd.ttf'))

# ── 스타일 ──
s_title = ParagraphStyle('T', fontName='MalgunBd', fontSize=17, leading=22,
    spaceAfter=6, alignment=TA_CENTER)
s_eng = ParagraphStyle('E', fontName='Malgun', fontSize=10, leading=13,
    alignment=TA_CENTER, textColor=HexColor('#555555'))
s_author = ParagraphStyle('A', fontName='Malgun', fontSize=11, leading=14,
    alignment=TA_CENTER, spaceAfter=4)
s_h1 = ParagraphStyle('H1', fontName='MalgunBd', fontSize=13, leading=17,
    spaceBefore=16, spaceAfter=8, textColor=HexColor('#1a5276'))
s_h2 = ParagraphStyle('H2', fontName='MalgunBd', fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=5, textColor=HexColor('#2c3e50'))
s_body = ParagraphStyle('B', fontName='Malgun', fontSize=9.5, leading=14,
    alignment=TA_JUSTIFY, spaceAfter=5)
s_bullet = ParagraphStyle('BL', fontName='Malgun', fontSize=9.5, leading=14,
    leftIndent=18, bulletIndent=8, spaceAfter=3, alignment=TA_JUSTIFY)
s_cap = ParagraphStyle('C', fontName='Malgun', fontSize=8.5, leading=11,
    alignment=TA_CENTER, textColor=HexColor('#555555'), spaceBefore=3, spaceAfter=8)
s_ref = ParagraphStyle('R', fontName='Malgun', fontSize=8.5, leading=11, spaceAfter=2)
s_kw = ParagraphStyle('KW', fontName='Malgun', fontSize=9, leading=12,
    textColor=HexColor('#555555'))

def tbl(data, cw=None):
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,-1), 'Malgun'),
        ('FONTNAME', (0,0), (-1,0), 'MalgunBd'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor('#f5f5f5')]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    return t

def P(text): return Paragraph(text, s_body)
def B(text): return Paragraph(f"- {text}", s_bullet)
def S(h=3): return Spacer(1, h*mm)

def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm, leftMargin=2.5*cm, rightMargin=2.5*cm)
    story = []
    W = doc.width

    # ═══ TITLE ═══
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(
        "Topological Data Analysis를 활용한<br/>음악 구조 분석 및 위상 구조 보존 기반 AI 작곡 파이프라인", s_title))
    story.append(S(3))
    story.append(Paragraph(
        "TDA-Based Music Structure Analysis and Topology-Preserving AI Composition Pipeline", s_eng))
    story.append(S(6))
    story.append(Paragraph("김민주", s_author))
    story.append(Paragraph("지도교수: 정재훈 (KIAS 초학제 독립연구단)", s_eng))
    story.append(S(5))
    story.append(HRFlowable(width="50%", thickness=0.8, color=HexColor('#cccccc')))
    story.append(S(5))

    # ═══ ABSTRACT ═══
    story.append(Paragraph("초록", s_h1))
    story.append(P(
        "본 논문에서는 사카모토 류이치의 'hibari'를 대상으로, Persistent Homology를 이용하여 "
        "음악의 위상 구조(cycle)를 추출하고, 이 구조를 보존하면서 새로운 음악을 생성하는 전체 "
        "파이프라인을 제시한다. 선행연구(정재훈 외, 2024)에서 제안한 음악 네트워크 기반 "
        "TDA 프레임워크를 계승하되, intra/inter 가중치 분리 설계, 다양한 거리 함수(Tonnetz, "
        "Voice-leading, DFT) 도입, 위상 구조 보존도 정량화, 딥러닝 기반 음악 생성 등을 수행하였다. "
        "실험 결과, Tonnetz 거리와 FC 신경망의 조합이 원곡 pitch 분포와의 JS divergence 0.002를 "
        "달성하여 가장 우수한 성능을 보였다."))
    story.append(S(2))
    story.append(Paragraph(
        "<b>키워드:</b> Topological Data Analysis, Persistent Homology, Vietoris-Rips Complex, "
        "Tonnetz, 음악 네트워크, 중첩행렬, intra/inter 가중치, AI 작곡", s_kw))

    # ═══ 1. 서론 ═══
    story.append(Paragraph("1. 서론", s_h1))
    story.append(P(
        "인공지능 음악 작곡 연구의 주류는 대량의 음악 데이터를 인공신경망에 학습시켜 "
        "유사한 음악을 생성하는 블랙박스 최적화 방식이다. 이에 반해, 본 연구는 단일 곡의 "
        "수학적 구조를 분석하고 그 구조를 명시적으로 보존하면서 새로운 음악을 생성하는 "
        "'설명 가능한' 작곡 방법론을 추구한다."))
    story.append(P(
        "선행연구(정재훈, 이동진, Mai Lan Tran)에서는 국악(수연장지곡)의 음악 네트워크에 "
        "Persistent Homology를 적용하여 cycle 구조를 발견하고, 이를 중첩행렬로 시각화한 후 "
        "Algorithm 1(확률적 샘플링)과 Algorithm 2(신경망)로 음악을 생성하는 프레임워크를 "
        "제안하였다. 본 연구는 이 프레임워크를 사카모토 류이치의 미니멀 음악 'hibari'에 "
        "적용하면서, 방법론적 확장과 기술적 개선을 수행하였다."))

    # ═══ 1.1 기여 분리 ═══
    story.append(Paragraph("1.1 연구자의 방법론적 기여", s_h2))
    story.append(P("<b>가중치 체계 설계 (intra/inter 분리):</b>"))
    story.append(B(
        "<b>Intra weight:</b> 같은 악기 내에서 인접 화음 간 전이 빈도. 한 악기의 선율적 "
        "흐름을 포착한다. 두 악기의 intra weight를 합산하여 '선율 구조'를 반영."))
    story.append(B(
        "<b>Inter weight:</b> 두 악기 간 시차(lag)를 둔 화음 전이 빈도. lag=1~4로 변화시키며 "
        "악기 간 상호작용의 다양한 시간 스케일을 탐색. 이 설계를 통해 '모듈 위주의 인식'(낮은 rate)부터 "
        "'두 악기가 휘몰아칠 때의 인식'(높은 rate)까지의 스펙트럼을 탐색할 수 있다."))
    story.append(B(
        "<b>Timeflow weight</b> = intra + rate x inter. rate를 0.0~1.5로 변화시키며 "
        "위상 구조의 출현/소멸을 추적하는 것이 핵심 탐색 전략."))

    story.append(S(2))
    story.append(P("<b>탐색 전략 설계:</b>"))
    story.append(B(
        "<b>Timeflow 탐색:</b> 선율 중심. intra(같은 악기 내 흐름) + rate x inter(악기 간 시차)."))
    story.append(B(
        "<b>Simul 탐색:</b> 화음 중심. 동시 발음(simultaneous) 기반 가중치. "
        "순간순간의 화음 관점에서 두 악기를 함께 들으려 할수록 노이즈로 인식되는 현상을 포착."))
    story.append(B(
        "<b>Complex 탐색:</b> timeflow + simul의 결합. "
        "rate_t, rate_s 비율로 선율과 화음의 기여도를 조절. "
        "'음악은 시간 예술이므로 화음보다 선율에 집중'이라는 해석(rate_c < 1)을 반영."))

    story.append(S(2))
    story.append(P("<b>기타 방법론적 기여:</b>"))
    story.append(B("중첩행렬(overlap matrix) → 음악 생성의 개념적 연결고리 정의"))
    story.append(B("Tonnetz, Voice-leading, DFT 등 음악적 거리 함수 도입 제안 및 실험 방향 설계"))
    story.append(B("고아 note(어떤 cycle에도 미포함) 문제의 발견 및 chord 기반 보충 아이디어"))
    story.append(B("onset 간격 제약, 모듈 단위 생성 등 음악적 제약조건 제안"))
    story.append(B("dim=2(void) 탐색, digraph 도입 가능성 등 확장 방향 제시"))

    story.append(Paragraph("1.2 AI 보조(Claude)의 구현 기여", s_h2))
    story.append(B("0-cycle 버그 진단 및 수정 (preprocessing, weights, symmetrize 3개 함수)"))
    story.append(B("generateBarcode의 Numpy 벡터화(2.5x) 및 Ripser C++ 통합(45x)"))
    story.append(B("위상 구조 보존도 지표 설계 (Jaccard + Correlation + Betti curve 복합 점수)"))
    story.append(B("Greedy Forward Selection 기반 cycle subset 선택 알고리즘"))
    story.append(B("Algorithm 2 데이터 정합성 수정 (L_encoded 7670 vs L_onehot 1088 불일치)"))
    story.append(B("DL 모델 3종 구현 (FC, LSTM, Transformer) + Data Augmentation 10x"))
    story.append(B("하이퍼파라미터 튜닝 (30개 조합 grid search)"))
    story.append(B("Tonnetz/Voice-leading/DFT 거리 함수 구현 + 플러그인 시스템"))
    story.append(B("평가 지표 모듈 (note coverage, KL/JS divergence, duration diversity)"))
    story.append(B("Streamlit 인터랙티브 대시보드 구축"))
    story.append(B("코드 일반화 (MIDI 자동 감지, 하드코딩 제거)"))

    # ═══ 2. 방법론 ═══
    story.append(PageBreak())
    story.append(Paragraph("2. 방법론", s_h1))

    story.append(Paragraph("2.1 음악 네트워크 구축", s_h2))
    story.append(P(
        "MIDI 파일을 8분음표 단위로 양자화한 후, 각 note를 (pitch, duration) 순서쌍으로 정의한다. "
        "hibari에서는 23종의 고유 note와 17종의 고유 chord가 발견된다. 두 악기를 분리하고, "
        "솔로 구간(inst1 끝 59개 note, inst2 앞 59개 note)을 제거하여 겹치는 연주 구간만 추출한다."))

    story.append(Paragraph("2.2 가중치 행렬: intra/inter 분리", s_h2))
    story.append(P(
        "<b>Intra weight(W_intra):</b> 같은 악기 내에서 시점 t의 화음과 시점 t+1의 화음이 "
        "연달아 나타나는 빈도를 17x17 행렬로 기록한다. 두 악기의 intra weight를 합산하여 "
        "W_intra = W_intra_1 + W_intra_2로 정의한다. 이는 개별 악기의 선율적 흐름을 포착한다."))
    story.append(P(
        "<b>Inter weight(W_inter):</b> 악기 1의 시점 t 화음과 악기 2의 시점 t+lag 화음의 "
        "동시 출현 빈도를 기록한다. lag=1~4로 변화시키며 다양한 시간 스케일의 악기 간 "
        "상호작용을 탐색한다. 이 설계가 본 연구의 핵심 아이디어 중 하나이다."))
    story.append(P(
        "<b>Timeflow weight:</b> W_timeflow = W_intra + rate x W_inter. "
        "rate를 0.0에서 1.5까지 변화시키면서 Persistent Homology를 반복 계산한다. "
        "rate가 낮을 때는 intra(선율) 위주의 구조가, 높을 때는 inter(악기 간 상호작용) "
        "위주의 구조가 지배적으로 나타난다."))

    story.append(Paragraph("2.3 음악적 거리 함수", s_h2))
    story.append(P(
        "기존 방법의 거리(빈도 역수)는 순수 통계적이어서 화성/선율 관계를 반영하지 못한다. "
        "이를 보완하기 위해 3가지 음악 이론 기반 거리를 추가로 도입하였다."))
    story.append(tbl([
        ['거리 함수', '원리', '특성'],
        ['빈도 역수', 'd = 1/w(i,j)', '통계적 — 자주 연달아 나온 음이 가까움'],
        ['Tonnetz', 'BFS on Z/12 격자', '화성적 — 장3도/완전5도 관계가 가까움'],
        ['Voice-leading', '|pitch1 - pitch2|', '선율적 — 반음 수 차이가 작은 음이 가까움'],
        ['DFT', '||DFT(pc1)-DFT(pc2)||', '음향적 — Fourier 계수 유사도'],
    ], cw=[W*0.16, W*0.30, W*0.48]))
    story.append(Paragraph("표 1. 거리 함수 비교", s_cap))
    story.append(P(
        "복합 거리: d_hybrid = alpha x d_freq + (1-alpha) x d_musical. alpha=0.5를 기본으로 사용한다."))

    story.append(Paragraph("2.4 Persistent Homology와 중첩행렬", s_h2))
    story.append(P(
        "거리 행렬로부터 Vietoris-Rips complex를 구축하고, pHcol 알고리즘(또는 Ripser)으로 "
        "persistent homology를 계산한다. 각 rate에서의 barcode를 수집하여 cycle의 출현/소멸 "
        "패턴을 추적한다. 발견된 cycle들이 각 시점에서 활성화되는지를 나타내는 이진 행렬 "
        "(T x C)이 중첩행렬이며, 이것이 음악 생성의 seed가 된다."))

    story.append(Paragraph("2.5 위상 구조 보존도와 Cycle 선택", s_h2))
    story.append(P(
        "전체 cycle 중 최적 subset을 선택하기 위해 3가지 지표의 가중 평균으로 보존도를 정의하였다: "
        "Note Pool Jaccard(50%) — 각 시점의 연주 가능 음 집합 유사도, "
        "Overlap Correlation(30%) — 시간적 활성 패턴 상관, "
        "Betti Curve Score(20%) — 위상적 복잡도 변화의 형태 유사도. "
        "Greedy Forward Selection으로 보존도 90%에 도달하는 최소 K를 결정한다."))

    story.append(Paragraph("2.6 음악 생성", s_h2))
    story.append(P(
        "<b>Algorithm 1(확률적 샘플링):</b> 각 시점에서 활성 cycle의 note pool에서 "
        "빈도 기반으로 랜덤 샘플링한다. 고아 note 보충(chord 활성 시점에 30% 확률로 주입)과 "
        "onset 간격 제약(min_onset_gap)을 추가하였다."))
    story.append(P(
        "<b>Algorithm 2(딥러닝):</b> 중첩행렬(overlap[t]) → 원곡 note(onehot[t]) 매핑을 "
        "신경망이 학습한다. FC(시점별 독립), LSTM(시간 패턴), Transformer(장거리 관계) 3종을 "
        "구현하였다. BCEWithLogitsLoss(다중 레이블)를 사용하고, Subset/Circular Shift/Noise "
        "Injection으로 10배 data augmentation을 수행한다."))

    # ═══ 3. 실험 결과 ═══
    story.append(PageBreak())
    story.append(Paragraph("3. 실험 결과", s_h1))

    story.append(Paragraph("3.1 거리 함수 x DL 모델 비교", s_h2))
    story.append(P(
        "4가지 거리 함수와 3가지 DL 모델의 12개 조합에 대해 JS divergence를 측정하였다. "
        "gap=3(1.5박 onset 간격), 50 epochs, 10x augmentation 조건이다."))
    story.append(tbl([
        ['거리 함수', 'Cycles', '90% K', 'FC (JS)', 'LSTM (JS)', 'Transformer (JS)'],
        ['빈도 only', '43', '17', '0.014', '0.268', '0.011'],
        ['Tonnetz (a=0.5)', '46', '15', '0.002', '0.267', '0.009'],
        ['Voice-leading', '22', '11', '0.007', '0.277', '0.016'],
        ['DFT', '20', '12', '0.012', '0.257', '0.014'],
    ], cw=[W*0.17, W*0.09, W*0.09, W*0.15, W*0.15, W*0.20]))
    story.append(Paragraph("표 2. 거리 함수 x DL 모델 JS divergence (낮을수록 원곡과 유사)", s_cap))

    story.append(P(
        "Tonnetz + FC 조합이 JS=0.002로 최우수. Tonnetz가 hibari의 C major/A minor 화성 구조를 "
        "가장 잘 포착한다. LSTM은 모든 metric에서 JS > 0.25로 학습 실패 — 1088 시점이 시퀀스 "
        "모델에 부족하기 때문이다."))

    story.append(Paragraph("3.2 단계별 개선 이력", s_h2))
    story.append(tbl([
        ['단계', '내용', '핵심 수치'],
        ['1', '0-cycle 버그 수정', '0 -> 48 cycles'],
        ['2', 'Barcode 최적화 (Ripser)', '72ms -> 1.6ms (45x)'],
        ['3', 'Cycle subset 선택', '17/48 = 90% 보존'],
        ['4', '고아 note 보충', 'KL 0.323 -> 0.250 (23%)'],
        ['5', 'Data augmentation 10x', 'val_loss 0.282'],
        ['6', 'HP 튜닝 30 조합', 'JS 0.0015 (FC best)'],
        ['7', '다중 search 12 조합', '85개 고유 cycle'],
        ['8', 'Tonnetz 거리 도입', 'JS 0.002 (18x 개선)'],
        ['9', 'Onset 간격 제약', '선율적 생성 (gap=3)'],
    ], cw=[W*0.07, W*0.42, W*0.38]))
    story.append(Paragraph("표 3. 단계별 개선 이력", s_cap))

    story.append(Paragraph("3.3 고아 Note 문제", s_h2))
    story.append(P(
        "note 5(A3 dur=6), 8(C4 dur=6), 22(G5 dur=1)는 어떤 cycle에도 속하지 않는다. "
        "이들은 화음의 일부이나 다른 note와의 거리가 상대적으로 멀어 cycle에 포함되지 못하는 "
        "'색채음'이다. chord 기반 보충으로 KL divergence를 23% 개선하였다."))

    # ═══ 4. 논의 ═══
    story.append(Paragraph("4. 논의: 방법론의 한계와 비판적 검토", s_h1))

    story.append(Paragraph("4.1 거리 정의의 근본적 문제", s_h2))
    story.append(P(
        "빈도 역수 거리는 곡의 통계적 특성만 반영하며 음악 이론적 관계를 포착하지 못한다. "
        "Tonnetz 도입으로 개선되었으나, alpha=0.5라는 혼합 비율은 경험적이며 곡/장르에 따라 "
        "최적값이 달라질 수 있다. 또한 duration 정보의 반영 방식(0.3 가중)도 이론적 근거가 부족하다."))

    story.append(Paragraph("4.2 중첩행렬의 정보 손실", s_h2))
    story.append(P(
        "cycle 활성을 0/1 이진화하여 cycle의 '강도'나 birth/death 시점 정보를 잃는다. "
        "같은 cycle이 활성화되어도 rate에 따라 의미가 다를 수 있으나 이 정보는 반영되지 않는다."))

    story.append(Paragraph("4.3 LSTM 학습 실패와 시퀀스 길이 문제", s_h2))
    story.append(P(
        "LSTM이 전 metric에서 JS > 0.25인 것은 심각한 한계이다. 1088 시점을 하나의 시퀀스로 "
        "학습하는 현재 방식은 시퀀스 모델에 적합하지 않다. 모듈(4마디=32 eighth notes) 단위 "
        "학습이 해결책이 될 수 있다 — 학습 샘플이 ~34개로 늘어나고 모듈 내부의 선율 패턴 "
        "학습이 가능해진다."))

    story.append(Paragraph("4.4 평가 지표의 한계", s_h2))
    story.append(P(
        "JS divergence는 pitch 빈도 분포만 측정하며 음악적 '좋음'과 직접 대응되지 않는다. "
        "시간적 구조(프레이징, 텐션-릴리스)의 평가를 위해 청취 실험이나 음악 이론 기반 "
        "평가(화성 진행 정합성 등)가 필요하다."))

    story.append(Paragraph("4.5 단일 곡 의존성", s_h2))
    story.append(P(
        "solo_notes=59 등의 파라미터는 자동 감지가 어렵고 다른 곡에 적용할 때 수동 설정이 "
        "필요하다. 특히 8분음표 양자화가 불가능한 복잡한 리듬의 곡에 대한 일반화는 미해결이다."))

    # ═══ 5. 향후 연구 ═══
    story.append(Paragraph("5. 향후 연구", s_h1))
    story.append(B(
        "<b>모듈 단위 생성:</b> 전체 시퀀스 대신 4마디 모듈을 예측하고 hibari와 동일하게 "
        "배치하는 방식. LSTM/Transformer의 학습 데이터 증가 및 반복 구조 학습에 유리."))
    story.append(B(
        "<b>Digraph 도입:</b> 현재 가중치 행렬은 대칭(무방향)이나 A->B와 B->A는 "
        "음악적으로 다른 의미. 방향 그래프 기반 거리 정의 검토."))
    story.append(B(
        "<b>청취 실험:</b> JS divergence 외에 인간 평가자의 주관적 평가를 통한 음악적 품질 검증."))
    story.append(B(
        "<b>인터랙티브 seed 편집:</b> 사용자가 중첩행렬을 직접 그려서 음악을 생성하는 UI."))
    story.append(B(
        "<b>다른 곡 일반화:</b> 사카모토의 다른 미니멀 곡이나 국악에 적용하여 일반성 검증."))
    story.append(B(
        "<b>H2(void) 활용:</b> 현재 H1(cycle)만 주로 사용. H2의 음악적 의미 규명."))

    # ═══ 6. 결론 ═══
    story.append(Paragraph("6. 결론", s_h1))
    story.append(P(
        "본 연구는 선행연구의 Persistent Homology 기반 음악 구조 분석 프레임워크를 확장하여, "
        "intra/inter 가중치 분리, 음악 이론 기반 거리 함수(Tonnetz 등), 위상 구조 보존도 "
        "정량화, 딥러닝 음악 생성, 인터랙티브 대시보드를 포함하는 종합적 파이프라인을 구축하였다. "
        "Tonnetz 거리가 hibari의 화성 구조를 가장 잘 포착하며(JS=0.002), 향후 모듈 단위 생성과 "
        "다른 곡으로의 일반화를 통해 방법론의 확장성을 검증할 계획이다."))

    # ═══ 참고문헌 ═══
    story.append(Paragraph("참고문헌", s_h1))
    for r in [
        "[1] 이동진, Mai Lan Tran, 정재훈, '국악의 기하학적 구조와 인공지능 작곡', 2024.",
        "[2] Mai Lan Tran et al., 'TDA of Korean Music in Jeongganbo: A Cycle Structure', arXiv:2103.06620, 2021.",
        "[3] Mai Lan Tran et al., 'Machine Composition of Korean Music via TDA and ANN', arXiv:2211.17298, 2024.",
        "[4] M. J. Catanzaro, 'Generalized Tonnetze', arXiv:1612.03519, 2016.",
        "[5] D. Tymoczko, 'The Generalized Tonnetz', J. Music Theory 56:1, 2012.",
        "[6] D. Tymoczko, 'Set-Class Similarity, Voice Leading, and the Fourier Transform', J. Music Theory 52/2, 2008.",
        "[7] L. Bigo et al., 'Computation and Visualization of Musical Structures in Chord-Based Simplicial Complexes', MCM 2013.",
        "[8] G. Carlsson, 'Topology and data', Bull. AMS 46(2), 2009.",
    ]:
        story.append(Paragraph(r, s_ref))

    doc.build(story)
    print(f"PDF 생성 완료: {OUTPUT}")

if __name__ == "__main__":
    build()
