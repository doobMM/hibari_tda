"""
2.1 Vietoris-Rips Complex 절을 5가지 한글 폰트로 렌더링한 PDF를 생성.
사용자가 선택할 수 있도록 비교 자료를 제공.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_academic_pdf import md_to_pdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import build_academic_pdf as bap
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# 폰트 후보
FONT_CANDIDATES = [
    {
        'name': 'Malgun',
        'label': '맑은고딕 (Malgun Gothic)',
        'regular': 'C:/Windows/Fonts/malgun.ttf',
        'bold': 'C:/Windows/Fonts/malgunbd.ttf',
    },
    {
        'name': 'NanumGothic',
        'label': '나눔고딕 (Nanum Gothic)',
        'regular': 'C:/Users/82104/AppData/Local/Microsoft/Windows/Fonts/NanumGothic.ttf',
        'bold': 'C:/Users/82104/AppData/Local/Microsoft/Windows/Fonts/NanumGothic.ttf',
    },
    {
        'name': 'NanumSquare',
        'label': '나눔스퀘어 (Nanum Square)',
        'regular': 'C:/Users/82104/AppData/Local/Microsoft/Windows/Fonts/NanumSquare.ttf',
        'bold': 'C:/Users/82104/AppData/Local/Microsoft/Windows/Fonts/NanumSquare.ttf',
    },
    {
        'name': 'HANBatang',
        'label': '한컴바탕 (HANBatang) — 명조체',
        'regular': 'C:/Windows/Fonts/HANBatang.ttf',
        'bold': 'C:/Windows/Fonts/HANBatangB.ttf',
    },
    {
        'name': 'HANDotum',
        'label': '한컴돋움 (HANDotum)',
        'regular': 'C:/Windows/Fonts/HANDotum.ttf',
        'bold': 'C:/Windows/Fonts/HANDotumB.ttf',
    },
]

# 2.1만 추출한 임시 md
SECTION_MD = """# 한글 폰트 비교: {label}

본 문서는 학술논문의 2.1절(Vietoris-Rips Complex)을 위 폰트로 렌더링한 결과입니다. 본문, 헤더, 영문, 인라인 수식의 가독성을 확인해주세요.

---

### 2.1 Vietoris-Rips Complex

**정의 2.1.** 거리 공간 $(X, d)$와 양의 실수 $\\varepsilon > 0$이 주어졌을 때, **Vietoris-Rips complex** $\\text{VR}_\\varepsilon(X)$는 다음과 같이 정의되는 복합체(simplicial complex)이다:

$$
\\text{VR}_\\varepsilon(X) = \\left\\{ \\sigma \\subseteq X \\,\\middle|\\, \\forall x_i, x_j \\in \\sigma,\\ d(x_i, x_j) \\le \\varepsilon \\right\\}
$$

즉, 부분집합 $\\sigma$에 속한 모든 점 쌍 사이의 거리가 $\\varepsilon$ 이하이면 $\\sigma$를 심플렉스(simplex)로 포함시킨다.

**구성 요소:**
- 0-simplex (vertex): 각 점 $x_i \\in X$
- 1-simplex (edge): $d(x_i, x_j) \\le \\varepsilon$인 쌍 $\\{x_i, x_j\\}$
- 2-simplex (triangle): 세 점이 모두 $\\varepsilon$ 이내인 삼각형
- $k$-simplex: $k+1$개의 점이 모두 $\\varepsilon$ 이내인 부분집합

**Filtration 구조:** $\\varepsilon$ 값을 0부터 연속적으로 키우면, 어떤 임계값들을 지날 때마다 새로운 심플렉스가 추가되어 복합체의 위상이 변한다. 이 변화 임계값들을 $\\varepsilon_0 < \\varepsilon_1 < \\varepsilon_2 < \\cdots$로 두면, 다음의 nested sequence가 만들어진다:

$$
\\emptyset \\subseteq \\text{VR}_{\\varepsilon_0}(X) \\subseteq \\text{VR}_{\\varepsilon_1}(X) \\subseteq \\text{VR}_{\\varepsilon_2}(X) \\subseteq \\cdots \\subseteq \\text{VR}_{\\varepsilon_n}(X)
$$

표기 편의를 위해 $K_{\\varepsilon_i} := \\text{VR}_{\\varepsilon_i}(X)$로 두면 nested sequence를 단순하게 표현할 수 있으며, 변화가 일어나는 미지수 $\\varepsilon_i$들이 곧 위상 구조의 birth/death 시점이 된다.

**본 연구에서의 사용:** $X = \\{n_1, n_2, \\ldots, n_{23}\\}$은 hibari에 등장하는 23개의 고유 note이며, $d(n_i, n_j)$는 두 note 간 거리이다. $\\varepsilon$를 점진적으로 증가시키며 simplex complex의 변화를 추적하여, 어떤 거리 척도에서 어떤 위상 구조가 출현·소멸하는지를 분석한다.
"""


def build_one(font_cfg):
    name = font_cfg['name']
    # 폰트 등록 (이미 등록된 경우 건너뛰기)
    try:
        pdfmetrics.registerFont(TTFont(name, font_cfg['regular']))
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont(name + 'Bd', font_cfg['bold']))
    except Exception:
        pass

    # 스타일을 임시로 교체
    bap.s_title.fontName = name + 'Bd'
    bap.s_meta.fontName = name
    bap.s_h1.fontName = name + 'Bd'
    bap.s_h2.fontName = name + 'Bd'
    bap.s_h3.fontName = name + 'Bd'
    bap.s_body.fontName = name
    bap.s_bullet.fontName = name

    # 임시 md 작성
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(docs_dir, f'_font_preview_{name}.md')
    pdf_path = os.path.join(docs_dir, f'font_preview_{name}.pdf')

    with open(md_path, 'w', encoding='utf-8') as f:
        # .format() 대신 단순 치환 (수식의 {} 충돌 방지)
        f.write(SECTION_MD.replace('{label}', font_cfg['label']))

    md_to_pdf(md_path, pdf_path)
    os.remove(md_path)
    print(f"  -> {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    print("폰트 비교 PDF 생성 중...")
    for cfg in FONT_CANDIDATES:
        if not os.path.exists(cfg['regular']):
            print(f"  스킵: {cfg['name']} (파일 없음)")
            continue
        build_one(cfg)
    print("\n완료. docs/font_preview_*.pdf 파일들을 비교해보세요.")
