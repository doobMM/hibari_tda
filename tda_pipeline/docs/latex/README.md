# LaTeX 원고

`hibari_tda.tex` — IEEE 템플릿 기반의 학술 논문 초고.

## 컴파일

### 옵션 A — Overleaf (권장, 로컬 설치 불필요)

1. Overleaf (https://overleaf.com)에 새 프로젝트 생성
2. `hibari_tda.tex` + `docs/figures/*.png` 6개 파일 업로드
3. Compiler를 **XeLaTeX**로 설정 후 Recompile

### 옵션 B — 로컬 TeX Live / MikTeX

```bash
cd tda_pipeline/docs/latex
xelatex hibari_tda.tex
xelatex hibari_tda.tex
```

- 두 번 컴파일하는 것은 cross-reference(그림 번호, 표 번호)를 확정시키기 위함.
- `xelatex` 권장 — 한글 폰트 사용 시 `fontspec`/`xeCJK` 블록을 주석 해제하고 NanumGothic을 지정할 수 있음.
- `pdflatex`로도 영문 전용이면 컴파일 가능.

## 그림 경로

`\graphicspath{{../figures/}}`로 `docs/figures/` 아래 PNG를 참조.
figure가 없으면 `cd tda_pipeline/docs/figures && python make_fig1_pipeline.py ...`로 먼저 생성.

## 구조

- I. Introduction
- II. Mathematical Background
- III. Pipeline Overview (Figure 1)
- IV. Generation Algorithms
- V. Experiments (Tables I-III, Figures 2-6)
- VI. Discussion

분량: 약 10 페이지 (IEEE conference two-column).

## 현재 상태

- 본문 + 표 3개 + 그림 6개 + 참고문헌 12개 완료
- Abstract, keywords 작성 완료
- Author name은 placeholder (`Author Name`)로 두었음 — 제출 시 교체
