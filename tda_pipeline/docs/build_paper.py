"""
학술 논문 PDF 생성 (v3 — 전면 수정)
수정사항:
  - rate_t, rate_s 명확히 서술
  - 중첩행렬 상세 설명
  - 거리함수별 특징 상세
  - 색채음 정의
  - onset 간격 제약 도입 맥락
  - 기여도 분리 → 맨 끝으로 이동
  - 모듈 단위 생성 결과 추가
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
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBd', 'C:/Windows/Fonts/malgunbd.ttf'))

s_title = ParagraphStyle('T', fontName='MalgunBd', fontSize=16, leading=21, spaceAfter=5, alignment=TA_CENTER)
s_eng = ParagraphStyle('E', fontName='Malgun', fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=HexColor('#555'))
s_author = ParagraphStyle('A', fontName='Malgun', fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=3)
s_h1 = ParagraphStyle('H1', fontName='MalgunBd', fontSize=13, leading=17, spaceBefore=14, spaceAfter=7, textColor=HexColor('#1a5276'))
s_h2 = ParagraphStyle('H2', fontName='MalgunBd', fontSize=11, leading=14, spaceBefore=10, spaceAfter=5, textColor=HexColor('#2c3e50'))
s_body = ParagraphStyle('B', fontName='Malgun', fontSize=9.3, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=4)
s_bl = ParagraphStyle('BL', fontName='Malgun', fontSize=9.3, leading=13.5, leftIndent=16, bulletIndent=6, spaceAfter=2, alignment=TA_JUSTIFY)
s_cap = ParagraphStyle('C', fontName='Malgun', fontSize=8.3, leading=11, alignment=TA_CENTER, textColor=HexColor('#555'), spaceBefore=2, spaceAfter=7)
s_ref = ParagraphStyle('R', fontName='Malgun', fontSize=8.3, leading=10.5, spaceAfter=2)
s_kw = ParagraphStyle('KW', fontName='Malgun', fontSize=8.5, leading=11.5, textColor=HexColor('#555'))

def tbl(data, cw=None):
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),HexColor('#2c3e50')),('TEXTCOLOR',(0,0),(-1,0),white),
        ('FONTNAME',(0,0),(-1,-1),'Malgun'),('FONTNAME',(0,0),(-1,0),'MalgunBd'),
        ('FONTSIZE',(0,0),(-1,-1),8.3),('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('GRID',(0,0),(-1,-1),0.5,HexColor('#ccc')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#f5f5f5')]),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
    ]))
    return t
def P(t): return Paragraph(t, s_body)
def B(t): return Paragraph(f"- {t}", s_bl)
def S(h=3): return Spacer(1, h*mm)

def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2.5*cm, rightMargin=2.5*cm)
    story = []
    W = doc.width

    # TITLE
    story.append(S(6))
    story.append(Paragraph("Topological Data Analysis를 활용한<br/>음악 구조 분석 및 위상 구조 보존 기반 AI 작곡 파이프라인", s_title))
    story.append(S(2))
    story.append(Paragraph("TDA-Based Music Structure Analysis and Topology-Preserving AI Composition Pipeline", s_eng))
    story.append(S(6))
    story.append(Paragraph("김민주", s_author))
    story.append(Paragraph("지도교수: 정재훈 (KIAS 초학제 독립연구단)", s_eng))
    story.append(S(4))
    story.append(HRFlowable(width="50%", thickness=0.7, color=HexColor('#ccc')))
    story.append(S(4))

    # ABSTRACT
    story.append(Paragraph("초록", s_h1))
    story.append(P(
        "본 논문에서는 사카모토 류이치의 'hibari'를 대상으로, Persistent Homology를 이용하여 "
        "음악의 위상 구조(cycle)를 추출하고, 이 구조를 보존하면서 새로운 음악을 생성하는 전체 "
        "파이프라인을 제시한다. 선행연구의 프레임워크를 계승하되, intra/inter 가중치 분리를 통한 "
        "선율-화음 스펙트럼 탐색, 음악 이론 기반 거리 함수(Tonnetz, Voice-leading, DFT) 도입, "
        "위상 구조 보존도 정량화, 모듈 단위 딥러닝 음악 생성 등을 수행하였다. 실험 결과, "
        "Tonnetz 거리와 모듈 단위 학습의 조합에서 LSTM의 JS divergence가 0.267에서 0.006으로 "
        "42배 개선되었으며, 전 모델이 JS < 0.01을 달성하였다."))
    story.append(S(1))
    story.append(Paragraph("<b>키워드:</b> Topological Data Analysis, Persistent Homology, Tonnetz, "
        "중첩행렬, intra/inter 가중치, 모듈 단위 생성, AI 작곡", s_kw))

    # 1. 서론
    story.append(Paragraph("1. 서론", s_h1))
    story.append(P(
        "인공지능 음악 작곡의 주류는 대량의 데이터를 학습하여 통계적으로 유사한 음악을 생성하는 "
        "블랙박스 접근법이다. 이에 반해, 본 연구는 단일 곡의 수학적 구조를 분석하고, 그 구조를 "
        "명시적으로 보존하면서 새로운 음악을 생성하는 '설명 가능한' 작곡 방법론을 추구한다."))
    story.append(P(
        "선행연구(정재훈, 이동진, Mai Lan Tran)에서는 국악(수연장지곡)의 음악 네트워크에 "
        "Persistent Homology를 적용하여 cycle 구조를 발견하고, 이를 중첩행렬로 시각화한 후 "
        "음악을 생성하는 프레임워크를 제안하였다. 본 연구는 이 프레임워크를 사카모토 류이치의 "
        "미니멀 음악 'hibari'에 적용하면서 방법론적 확장을 수행하였다."))

    # 2. 방법론
    story.append(Paragraph("2. 방법론", s_h1))

    story.append(Paragraph("2.1 음악 네트워크 구축", s_h2))
    story.append(P(
        "MIDI 파일을 8분음표 단위로 양자화한 후, 각 note를 (pitch, duration) 순서쌍으로 정의한다. "
        "hibari에서는 23종의 고유 note와 17종의 고유 chord가 발견된다. 두 악기(inst1, inst2)를 "
        "분리하고, 솔로 구간(inst1 끝 59개 note, inst2 앞 59개 note)을 제거하여 두 악기가 "
        "동시에 연주하는 구간(1056 시점 = 132마디)만 추출한다."))

    story.append(Paragraph("2.2 가중치 행렬: intra/inter/simul 분리", s_h2))
    story.append(P(
        "본 연구의 핵심 설계는 가중치를 성격에 따라 분리한 것이다. 이를 통해 '선율 중심의 인식'부터 "
        "'화음 중심의 인식'까지의 연속적 스펙트럼을 탐색할 수 있다."))
    story.append(P(
        "<b>Intra weight (W_intra):</b> 같은 악기 내에서 시점 t의 화음과 시점 t+1의 화음이 "
        "연달아 나타나는 빈도를 17x17 행렬로 기록한다. 두 악기의 intra를 합산: "
        "W_intra = W_intra_1 + W_intra_2. 이는 개별 악기의 <b>선율적 흐름</b>을 포착한다."))
    story.append(P(
        "<b>Inter weight (W_inter):</b> 악기 1의 시점 t 화음과 악기 2의 시점 t+lag 화음의 "
        "동시 출현 빈도를 기록한다. lag=1~4로 변화시키며 다양한 시간 스케일의 <b>악기 간 상호작용</b>을 "
        "탐색한다."))
    story.append(P(
        "<b>Simul weight:</b> 같은 시점에서 두 악기가 동시에 발음하는 note 조합의 빈도. "
        "순간적인 <b>화음 구조</b>를 포착한다."))
    story.append(S(2))
    story.append(P("<b>세 가지 탐색 전략:</b>"))
    story.append(B(
        "<b>Timeflow 탐색:</b> W_timeflow = W_intra + rate_t x W_inter. "
        "rate_t를 0.0~1.5로 변화시키며 선율(intra) 위주 → 상호작용(inter) 위주의 스펙트럼을 탐색. "
        "rate_t가 낮으면 처음/후반의 모듈 위주로, 높으면 3/8~5/8 지점에서 두 악기가 휘몰아칠 때의 "
        "구조가 발견된다."))
    story.append(B(
        "<b>Simul 탐색:</b> W_simul = W_simul_intra + rate_s x W_simul_inter. "
        "rate_s를 0.0~1.0로 변화. 순간순간의 화음 관점에서 두 악기를 동시에 들으려 할수록 "
        "노이즈로 인식되는 현상(정렬도 하락)을 포착한다."))
    story.append(B(
        "<b>Complex 탐색:</b> W_complex = W_timeflow_refined + rate_c x W_simul. "
        "rate_c < 1로 제한 — '음악은 시간 예술이므로 화음보다 선율에 더 큰 비중을 둔다'는 "
        "해석을 반영한다."))

    story.append(Paragraph("2.3 음악적 거리 함수", s_h2))
    story.append(P(
        "기존 방법의 거리 d = 1/w(i,j)는 '곡에서 연달아 자주 나온 음일수록 가깝다'는 순수 통계적 "
        "정의이다. 같은 화음에 속하더라도 등장 빈도가 낮은 음은 멀리 배치되어 cycle에서 배제될 수 "
        "있다. 이를 보완하기 위해 음악 이론에 기반한 3가지 거리를 추가 도입하였다."))
    story.append(tbl([
        ['거리 함수', '원리', '특징'],
        ['빈도 역수', '연달아 등장 횟수의 역수', '곡의 통계에만 의존. 화성/선율 관계 무시'],
        ['Tonnetz\n(어울림)', '장3도(+4)/완전5도(+7)\n격자 위 BFS 거리',
         '도-미, 도-솔처럼 함께 울리면 어울리는 음이 가까움.\n화성 구조를 반영. hibari의 C장조 구조에 적합'],
        ['Voice-leading\n(높낮이)', '|pitch1 - pitch2|\n(반음 수 차이)',
         '피아노 건반에서 가까운 음이 가까움.\n손가락 이동이 적은 자연스러운 진행을 반영'],
        ['DFT\n(파동)', '||DFT(pc1)-DFT(pc2)||\nFourier 계수 L2 거리',
         'pitch class를 주파수 공간으로 변환.\n각 계수가 반음계성/온음계성 등에 대응'],
    ], cw=[W*0.14, W*0.28, W*0.52]))
    story.append(Paragraph("표 1. 거리 함수 비교", s_cap))
    story.append(P(
        "복합 거리: d_hybrid = alpha x d_freq + (1-alpha) x d_musical. alpha=0.5를 기본으로 사용한다."))

    story.append(Paragraph("2.4 Persistent Homology", s_h2))
    story.append(P(
        "거리 행렬로부터 Vietoris-Rips complex를 구축하고, pHcol 알고리즘(또는 Ripser C++)으로 "
        "persistent homology를 계산한다. 각 rate_t 값에서의 barcode를 수집하여 cycle의 출현(birth)/"
        "소멸(death) 패턴을 추적한다. 계산 최적화를 위해 Ripser를 통합하여 기존 대비 45배 속도 "
        "향상을 달성하였다."))

    story.append(Paragraph("2.5 중첩행렬 (Overlap Matrix)", s_h2))
    story.append(P(
        "중첩행렬은 '시간이 흐르면서 어떤 위상적 반복 패턴이 활성화되어 있는가'를 나타내는 "
        "이진 행렬이다. 크기는 T x C (T=1088 시점, C=cycle 수)이며, overlap[t, c] = 1이면 "
        "'시점 t에서 cycle c에 속한 note들이 원곡에서 연주되고 있다'는 의미이다."))
    story.append(P(
        "구축 과정: (1) 각 cycle의 구성 note가 원곡의 어느 시점에서 활성화되는지 확인 "
        "(activation matrix). (2) 연속적으로 활성화된 구간 중 일정 길이(scale) 이상인 것만 "
        "남겨서 산발적 활성화를 제거. (3) ON 비율이 목표치(35%)에 가까워지도록 scale을 "
        "동적 조정. 이 행렬이 음악 생성의 <b>seed(씨앗)</b>이 된다."))

    story.append(Paragraph("2.6 위상 구조 보존도와 Cycle 선택", s_h2))
    story.append(P(
        "발견된 전체 cycle을 사용할 필요 없이, 원곡의 구조를 90% 이상 보존하는 최소 subset을 "
        "선택한다. Greedy Forward Selection으로 매 단계 보존도가 가장 높아지는 cycle을 추가하며, "
        "보존도 = Note Pool Jaccard(50%) + Overlap Correlation(30%) + Betti Curve Score(20%)의 "
        "가중 평균으로 정의한다."))

    story.append(Paragraph("2.7 고아 Note와 색채음 문제", s_h2))
    story.append(P(
        "분석 결과, note 5(A3 dur=6), 8(C4 dur=6), 22(G5 dur=1)는 어떤 cycle에도 속하지 않는다. "
        "이들은 음악에서 '색채음(color tone)'이라 불리는 역할을 한다 — 화음의 핵심 구성음은 "
        "아니지만, 곡에 독특한 음색이나 긴장감을 부여하는 음이다. 빈도 기반 거리에서는 다른 음과의 "
        "연결이 약하여 cycle 구조에서 배제되지만, 실제 연주에서는 화음의 일부로 등장한다."))
    story.append(P(
        "해결: 고아 note가 속한 chord가 활성화되는 시점에, 30% 확률로 해당 note를 sampling pool에 "
        "주입한다. 이를 통해 pitch 분포의 KL divergence가 0.323에서 0.250으로 23% 개선되었다."))

    story.append(Paragraph("2.8 음악 생성", s_h2))
    story.append(P(
        "<b>Algorithm 1(확률적 샘플링):</b> 각 시점에서 활성 cycle의 note pool에서 빈도 기반으로 "
        "랜덤 샘플링한다."))
    story.append(P(
        "<b>Algorithm 2(딥러닝):</b> 중첩행렬의 overlap[t] → 원곡의 onehot[t] 매핑을 신경망이 "
        "학습한다. FC(시점별 독립), LSTM(시간 패턴 기억), Transformer(장거리 관계) 3종을 구현. "
        "BCEWithLogitsLoss(다중 레이블)를 사용하고, Subset/Circular Shift/Noise Injection으로 "
        "10배 data augmentation을 수행한다."))

    story.append(Paragraph("2.9 Onset 간격 제약", s_h2))
    story.append(P(
        "생성된 음악을 청취한 결과, 원곡 hibari와 달리 '화음 타건 연타'처럼 들리는 문제가 발견되었다. "
        "원곡의 동시 발음 수를 분석하면, 1개(선율)와 4개(화음)로 뚜렷하게 이분되는 반면 "
        "생성곡은 2~3개가 과다하게 분포하였다. 이를 해결하기 위해 min_onset_gap 파라미터를 도입: "
        "새 음이 시작된 후 최소 N개의 eighth note가 지나야 다음 음을 배치할 수 있도록 제약한다. "
        "gap=3(1.5박)으로 설정하면 선율적 흐름이 살아나는 효과가 있다."))

    story.append(Paragraph("2.10 모듈 단위 생성", s_h2))
    story.append(P(
        "hibari는 4마디(32 eighth notes) 단위의 규칙적 모듈 구조를 가진다 — 정확히 33개 모듈, "
        "각 모듈에 59개 note. 전체 시퀀스(1088 시점)를 하나로 학습하는 대신, 33개 모듈을 독립적인 "
        "학습 샘플로 구성하면 LSTM/Transformer의 학습 데이터가 1개 → 33개(+ augmentation)로 "
        "대폭 증가한다. 32 시점 길이의 짧은 시퀀스에서 LSTM의 vanishing gradient 문제도 해소된다."))

    # 3. 실험 결과
    story.append(PageBreak())
    story.append(Paragraph("3. 실험 결과", s_h1))

    story.append(Paragraph("3.1 거리 함수 x 모델 비교 (전체 시퀀스)", s_h2))
    story.append(tbl([
        ['거리 함수', 'Cycles', '90% K', 'FC (JS)', 'LSTM (JS)', 'Transformer (JS)'],
        ['빈도 only', '43', '17', '0.014', '0.268', '0.011'],
        ['Tonnetz (a=0.5)', '46', '15', '0.002', '0.267', '0.009'],
        ['Voice-leading', '22', '11', '0.007', '0.277', '0.016'],
        ['DFT', '20', '12', '0.012', '0.257', '0.014'],
    ], cw=[W*0.17, W*0.09, W*0.09, W*0.15, W*0.15, W*0.20]))
    story.append(Paragraph("표 2. 전체 시퀀스 학습: JS divergence (낮을수록 원곡과 유사)", s_cap))
    story.append(P(
        "Tonnetz + FC가 JS=0.002로 최우수. LSTM은 모든 metric에서 JS > 0.25로 학습 실패 — "
        "1088 시점 시퀀스가 LSTM에 너무 길어 vanishing gradient 발생."))

    story.append(Paragraph("3.2 모듈 단위 학습 결과", s_h2))
    story.append(tbl([
        ['Model', '전체 시퀀스 JS', '모듈 단위 JS', '개선 배율'],
        ['FC', '0.002', '0.003', '동등'],
        ['LSTM', '0.267', '0.006', '42x 개선'],
        ['Transformer', '0.009', '0.004', '2.5x 개선'],
    ], cw=[W*0.20, W*0.22, W*0.22, W*0.22]))
    story.append(Paragraph("표 3. Tonnetz 거리 기준: 전체 시퀀스 vs 모듈 단위", s_cap))
    story.append(P(
        "모듈 단위 학습에서 LSTM의 JS가 0.267 → 0.006으로 <b>42배 개선</b>되었다. "
        "32 시점 시퀀스 33개를 독립 학습하여 vanishing gradient가 해소되고, "
        "모듈 내부의 선율 패턴을 제대로 학습한 결과이다. val_loss도 0.39 → 0.05로 수렴."))

    story.append(Paragraph("3.3 단계별 개선 이력", s_h2))
    story.append(tbl([
        ['단계', '내용', '핵심 수치'],
        ['1', '0-cycle 버그 수정', '0 -> 48 cycles'],
        ['2', 'Barcode 최적화 (Ripser)', '72ms -> 1.6ms (45x)'],
        ['3', 'Cycle subset 선택', '17/48 = 90% 보존'],
        ['4', '고아 note(색채음) 보충', 'KL 23% 개선'],
        ['5', 'Data augmentation 10x', 'val_loss 0.282'],
        ['6', 'HP 튜닝 30 조합', 'JS 0.0015 (FC best)'],
        ['7', '다중 search 12 조합', '85개 고유 cycle'],
        ['8', 'Tonnetz 거리 도입', 'JS 0.002 (18x 개선)'],
        ['9', 'Onset 간격 제약', '선율적 생성 (gap=3)'],
        ['10', '모듈 단위 생성', 'LSTM JS 42x 개선'],
    ], cw=[W*0.06, W*0.40, W*0.40]))
    story.append(Paragraph("표 4. 단계별 개선 이력", s_cap))

    # 4. 논의
    story.append(Paragraph("4. 논의", s_h1))

    story.append(Paragraph("4.1 거리 정의의 근본적 문제", s_h2))
    story.append(P(
        "alpha=0.5라는 빈도-음악적 거리 혼합 비율은 경험적이며, 곡/장르에 따라 최적값이 다를 수 있다. "
        "Tonnetz가 hibari(C장조)에서 우수한 이유는 장3도/완전5도 관계가 이 조성에 자연스럽게 맞기 "
        "때문이며, 무조성 음악이나 미분음 음악에서는 다른 결과가 나올 수 있다."))

    story.append(Paragraph("4.2 중첩행렬의 정보 손실", s_h2))
    story.append(P(
        "cycle 활성을 0/1 이진화하여 '어느 정도 강하게 활성화되는가'의 정보를 잃는다. "
        "실수값 중첩행렬(0~1 사이의 활성 확률)로 확장하면 더 세밀한 정보를 보존할 수 있다."))

    story.append(Paragraph("4.3 평가 지표의 한계", s_h2))
    story.append(P(
        "JS divergence는 pitch 빈도 분포만 측정하며 시간적 구조(프레이징, 텐션-릴리스)를 반영하지 "
        "않는다. 청취 실험이나 음악 이론 기반 평가(화성 진행 정합성)가 필요하다."))

    story.append(Paragraph("4.4 단일 곡 의존성", s_h2))
    story.append(P(
        "solo_notes=59, 8분음표 양자화 등이 hibari 전용이다. 복잡한 리듬의 곡에 대한 일반화는 "
        "미해결 과제이며, 양자화 단위 자동 감지 기능을 구현하였으나 완전하지 않다."))

    # 5. 향후 연구
    story.append(Paragraph("5. 향후 연구", s_h1))
    story.append(B("<b>Digraph 도입:</b> A->B와 B->A의 음악적 의미 차이를 반영하는 방향 그래프 기반 거리."))
    story.append(B("<b>청취 실험:</b> 인간 평가자의 주관적 품질 평가."))
    story.append(B("<b>인터랙티브 seed 편집:</b> 사용자가 중첩행렬을 직접 그려서 음악을 생성하는 UI."))
    story.append(B("<b>다른 곡 일반화:</b> 사카모토의 다른 곡이나 국악에 적용."))
    story.append(B("<b>H2(void) 활용:</b> 2차원 호몰로지의 음악적 의미 규명."))
    story.append(B("<b>실감 음원:</b> SoundFont 기반 피아노 렌더링으로 청취 품질 향상."))

    # 6. 결론
    story.append(Paragraph("6. 결론", s_h1))
    story.append(P(
        "본 연구는 Persistent Homology 기반 음악 구조 분석 프레임워크를 확장하여, intra/inter/simul "
        "가중치 분리, Tonnetz 등 음악 이론 기반 거리, 모듈 단위 딥러닝 생성을 포함하는 종합적 "
        "파이프라인을 구축하였다. 모듈 단위 학습에서 LSTM의 JS divergence가 42배 개선(0.267 → 0.006) "
        "되어, 시퀀스 모델도 적절한 데이터 구성으로 효과적임을 확인하였다."))

    # 부록: 기여 분리
    story.append(PageBreak())
    story.append(Paragraph("부록: 연구 기여 분리", s_h1))
    story.append(P(
        "본 연구는 인간 연구자(김민주)의 방법론적 설계와 AI 보조(Claude)의 기술적 구현이 "
        "협업한 결과이다. 아래에 각각의 기여를 명시한다."))

    story.append(Paragraph("A.1 인간 연구자(김민주)의 기여", s_h2))
    story.append(B("TDA 기반 음악 분석 프레임워크의 hibari 적용 설계"))
    story.append(B("intra/inter/simul 가중치 분리 체계 설계 및 음악적 해석"))
    story.append(B("rate_t, rate_s, rate_c의 의미론적 해석 (선율 vs 화음 스펙트럼)"))
    story.append(B("timeflow/simul/complex 3가지 탐색 전략 수립"))
    story.append(B("Tonnetz, Voice-leading, DFT 거리 함수 도입 제안"))
    story.append(B("고아 note(색채음) 문제의 발견 및 chord 기반 보충 아이디어"))
    story.append(B("onset 간격 제약, 모듈 단위 생성 등 음악적 제약조건 제안"))
    story.append(B("dim=2(void) 탐색, digraph 도입 등 확장 방향 제시"))
    story.append(B("발표자료 작성 및 전체 연구 방향 수립"))

    story.append(Paragraph("A.2 AI 보조(Claude)의 기여", s_h2))
    story.append(B("0-cycle 버그 진단/수정, Ripser 통합(45x), Numpy 벡터화(2.5x)"))
    story.append(B("보존도 지표 설계 (Jaccard + Correlation + Betti) + Greedy Selection"))
    story.append(B("Algorithm 2 데이터 정합성 수정 (L_encoded/L_onehot 불일치)"))
    story.append(B("DL 모델 3종 구현, Data Augmentation 10x, HP 튜닝 30조합"))
    story.append(B("Tonnetz/VL/DFT 거리 함수 구현 + 플러그인 시스템"))
    story.append(B("평가 지표 모듈, Streamlit 대시보드, 코드 일반화"))
    story.append(B("모듈 단위 학습/생성 코드 구현"))

    # 참고문헌
    story.append(Paragraph("참고문헌", s_h1))
    for r in [
        "[1] 이동진, Mai Lan Tran, 정재훈, '국악의 기하학적 구조와 인공지능 작곡', 2024.",
        "[2] Mai Lan Tran et al., 'TDA of Korean Music: A Cycle Structure', arXiv:2103.06620, 2021.",
        "[3] Mai Lan Tran et al., 'Machine Composition via TDA and ANN', arXiv:2211.17298, 2024.",
        "[4] M. J. Catanzaro, 'Generalized Tonnetze', arXiv:1612.03519, 2016.",
        "[5] D. Tymoczko, 'The Generalized Tonnetz', J. Music Theory 56:1, 2012.",
        "[6] D. Tymoczko, 'Set-Class Similarity and the Fourier Transform', J. Music Theory 52/2, 2008.",
        "[7] L. Bigo et al., 'Musical Structures in Chord-Based Simplicial Complexes', MCM 2013.",
        "[8] G. Carlsson, 'Topology and data', Bull. AMS 46(2), 2009.",
    ]:
        story.append(Paragraph(r, s_ref))

    doc.build(story)
    print(f"PDF: {OUTPUT}")

if __name__ == "__main__":
    build()
