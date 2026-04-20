---
description: LaTeX 작업(`docs/latex/**`) 진입 시 조건부 로드.
activate_when:
  - "editing docs/latex/**"
  - "user mentions: LaTeX, xelatex, pdflatex, hibari_tda.tex, hibari_tda_ko.tex, hibari_tda_report.tex"
---

# LaTeX 규칙 (CLAUDE.md §빌드 레시피 보강)

## 엔진 선택 (파일별)

| 파일 | 엔진 | 이유 |
|---|---|---|
| `hibari_tda.tex` | xelatex 또는 pdflatex | 영문 IEEE, 폰트 자유 |
| `hibari_tda_ko.tex` | **xelatex 전용** | fontspec 한글 폰트 |
| `hibari_tda_report.tex` | **xelatex 전용** | fontspec 한글 폰트 |

pdflatex로 `_ko` · `_report` 빌드 시도는 금지 — 실패 확정 + 시간 낭비.

## 커밋 관례

- **3파일 PDF 모두 tracked** (2026-04-19 bcd35ed 이후).
- md/tex 수정 후 **3파일 동시 재빌드** 원칙. 누락 시 불일치 커밋.
- 컴파일 성공 검증 3항:
  1. 에러 0
  2. undefined reference 0
  3. citation warning 0
  위 3항 중 하나라도 실패하면 PDF 커밋 중단.

## 참조 일관성

- `\label` 변경 시 `\ref` 전수 스캔 (Grep).
- `\cite` 추가 시 `.bib` 파일에도 엔트리 확인.
- 수치 변경은 `step3_data/*.json` 원본 대조 (CLAUDE.md §논문-코드 정합성 규칙).

## 한글본 특수 주의

- `\begin{itemize}` 안에 한국어+영어 섞으면 hyphenation 깨짐 → `\hangindent` 또는 `\leavevmode` 사용.
- 표 셀 내부 한글은 `\raggedright` 고려.

## Gotchas

- `hibari_tda_report.toc` 등 aux 파일은 **gitignore 대상** (재생성 가능).
- BibTeX warning "empty journal" 등은 무시 안 됨 — citation 0 원칙.
- figure 경로는 `docs/latex/`에서 상대 경로. `../figures/xxx.png` 형태.
