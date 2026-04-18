# 세션 D — Task 43-B: LaTeX 한글본 동기화 + 3파일 컴파일 검증

## 배경

Task 43-A (커밋 `fe85f53`, 2026-04-17) 에서 세션 D가 Task 44 중 LaTeX 일부 선행:

- `hibari_tda.tex` (영문 IEEE) — Phase 3 반영 완료
- `hibari_tda_report.tex` (report 장문) — full.md 기반 동기화
- `hibari_tda.pdf` — 재컴파일

**미완**:
- `hibari_tda_ko.tex` (한글 IEEE) — 동기화 필요
- **3파일 최종 컴파일 검증** — undefined ref / 표 참조 / 수식 레이블 정합성

본 Task 43-B는 한글본을 최신 영문본과 동기화하고, 3파일 모두 컴파일 에러 없이 PDF
생성되는지 검증한다.

## 필수 참조 파일

### 읽을 것

- `tda_pipeline/docs/latex/hibari_tda.tex` — 영문 IEEE 최신 (Task 43-A 결과)
- `tda_pipeline/docs/latex/hibari_tda_ko.tex` — 한글 IEEE (동기화 대상)
- `tda_pipeline/docs/latex/hibari_tda_report.tex` — report 장문 (Task 43-A 결과)
- `tda_pipeline/docs/academic_paper_portfolio (short).md` — short.md (한글본의 소스)
- `tda_pipeline/docs/academic_paper_full.md` — full.md (report의 소스)
- `docs/session_d_task43_latex_sync_prompt.md` — 원본 Task 43 체크리스트

### 수정할 것

- `tda_pipeline/docs/latex/hibari_tda_ko.tex`
- 3파일 컴파일 산출물: `.aux`, `.out`, `.pdf` (단 `.aux`/`.out`은 `.gitignore` 대상이면 커밋 제외)

### 금지

- `.md` 원고 수정 (Task 41/44에서 최종 확정)
- `CLAUDE.md` 수정

## 작업 범위

### ① hibari_tda_ko.tex 한글 동기화 — 1순위

`hibari_tda.tex` (영문 IEEE, Task 43-A 완료) 의 구조·수치를 한글본에 반영:

1. 초록 Algo1 0.01489 / Algo2 0.00035
2. §4 gap0+DFT 수치 (DFT 38.2% / Tonnetz 56.8% / VL 62.4%)
3. §6.1·§6.2 DFT 열 추가 (solari 0.0824 / Bach 0.0951 / Ravel 0.0494)
4. §6.3 "본 장은 Tonnetz 기반" 선언
5. §6.4 세 모델 서술 (FC pitch JS 0.0009 + DTW +30~48%, LSTM ≤0.5% 실측, Transformer
   PE 핵심)
6. §6.5 FC/LSTM 표 ±std
7. §6.6 3분할 (6.6.1/6.6.2/6.6.3)
8. §6.7 per-cycle τ +58.7% + FC-cont 0.000348
9. §6.8 DFT α-hybrid α=0.25
10. §6.9 Tonnetz 한정 유효
11. §7 K=14, P3+C best 0.0250, §7.7 서사 반전, §7.8 Pearson −0.054
12. §8 결론 6항 "거리 함수 × 목적"

**접근**: 기존 한글본 문장 스타일·용어 유지하면서 영문본의 **수치·섹션 구조만** 일치시킴.

### ② 3파일 컴파일 검증 — 2순위

각 `.tex` 파일 컴파일:

```bash
cd tda_pipeline/docs/latex
pdflatex hibari_tda.tex            # 영문 IEEE
pdflatex hibari_tda.tex            # 2회 (ref 해결)
pdflatex hibari_tda.tex            # 3회

pdflatex hibari_tda_ko.tex         # 한글
pdflatex hibari_tda_ko.tex
pdflatex hibari_tda_ko.tex

pdflatex hibari_tda_report.tex     # report
pdflatex hibari_tda_report.tex
pdflatex hibari_tda_report.tex
```

bibtex 필요 시 중간에 수행. 3회 컴파일은 cross-reference 안정화용.

### 검증 체크

각 파일별 `.log` 확인:

- `! LaTeX Error` / `! Undefined control sequence` → 에러
- `LaTeX Warning: Reference \`...' on page ... undefined` → ref 누락
- `LaTeX Warning: Citation \`...' undefined` → bib 누락

보고 형식:

| 파일 | 컴파일 에러 | undefined refs | citations 누락 |
|---|---|---|---|
| hibari_tda.tex | 0 / X건 | 0 / X건 | 0 / X건 |
| hibari_tda_ko.tex | | | |
| hibari_tda_report.tex | | | |

에러 0 / ref 0 / citation 0 이면 통과.

### ③ (선택) 한글 폰트·레이아웃 최종 확인

- `kotex` 또는 `xelatex` 사용 여부 확인
- 한글 폰트 embed 확인
- 표·수식 overflow 점검

## 금지 사항

- `.md` 원고 수정
- 기존 `.bib` 파일 재편집 (필요 시 `\bibitem` 추가만 OK)
- `CLAUDE.md` 수정

## 산출물

1. `hibari_tda_ko.tex` (M)
2. 3파일 PDF 컴파일 결과 (`hibari_tda.pdf`, `hibari_tda_ko.pdf`, `hibari_tda_report.pdf`)
3. `.aux`/`.out`은 `.gitignore`에 이미 있으므로 커밋 제외 (세션 B 리팩토링 결과)

## 커밋 지침

```
docs(latex): Task 43-B 한글본 동기화 + 3파일 최종 컴파일 검증

- hibari_tda_ko.tex: Phase 3 반영 (영문본 hibari_tda.tex 구조·수치 일치)
  · 초록·§4~§8 전체 수치 갱신
  · §6.6 3분할 구조
  · §8 6항 메타 통찰

- 3파일 pdflatex 컴파일 검증:
  · hibari_tda.pdf: 에러 0, undefined ref 0, citation 0
  · hibari_tda_ko.pdf: 에러 0, undefined ref 0, citation 0
  · hibari_tda_report.pdf: 에러 0, undefined ref 0, citation 0

Phase 3 LaTeX 동기화 완결.

참조: docs/session_d_task43_latex_sync_prompt.md (원본)
      docs/session_d_task43b_latex_finalize_prompt.md (본 Task)
```

## 검수 체크리스트

### hibari_tda_ko.tex

- [ ] 초록 Algo1 0.01489, Algo2 0.00035 수치 존재
- [ ] §6.6.1 / §6.6.2 / §6.6.3 (또는 상응 subsection) 존재
- [ ] §7.1 K=14 언급 존재
- [ ] §7.7 first-module rank=5 언급
- [ ] §7.8 Pearson −0.054 존재
- [ ] §8 결론 6항 "거리 함수 × 목적" 존재
- [ ] 한글 폰트 정상 렌더링 (외국어 기호 포함)

### 3파일 공통

- [ ] 컴파일 에러 0
- [ ] Undefined references 0
- [ ] Undefined citations 0
- [ ] 표·그림 번호 일관성 (cross-reference 정상)

## 예상 소요

- 한글 동기화 (ko.tex): 1~2시간 (영문본 복사 + 한글 용어 유지)
- 3파일 컴파일 검증 + 오류 수정: 30분~1시간
- **총 1.5~3시간**

## 세션 간 병렬 안전성

- 본 Task는 `docs/latex/*.tex` + `*.pdf`만.
- 다른 세션 작업 없음. 단독 실행.

## 완료 후 세션 E 루틴

1. 3 tex + 3 pdf 커밋
2. memory: `project_task43_latex_complete_0417.md` 신설 (또는 기존 Task 44 memory 확장)
3. `CLAUDE.md` Task 43 ✓
4. **gap0+DFT 통합 재서술 + Phase 3 + LaTeX 동기화 전체 프로젝트 종결 선언**

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음 + 권한 전체 액세스**. 한글 타이포·LaTeX
오류 진단 필요하므로 "매우 높음" 유지.
