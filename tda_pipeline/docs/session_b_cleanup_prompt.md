# 세션 B — 잔여 미커밋 파일 정리 (Task 37과 병렬 실행 가능)

## 배경

Phase 1+2 실험 + §4·§6 재서술 완료 후 대량의 미커밋 파일이 누적되어 있다. 주제별로
분리 커밋해 git log 흐름을 깔끔히 한다.

**병렬 안전성**: 세션 D Task 37 (academic_paper_*.md + CLAUDE.md) 및 세션 C
(output/final/) 과 파일 영역 완전 분리. 동시 실행 OK.

## 금지 파일 (절대 건드리지 말 것)

- `tda_pipeline/docs/academic_paper_*.md` — 세션 D Task 37 영역
- `tda_pipeline/docs/academic_paper_*.pdf` — 세션 D Task 37 영역
- `CLAUDE.md` — 세션 D Task 37 특별 편집 예정
- `tda_pipeline/docs/step3_data/*_gap0_*.json` — 실험 결과, 수정 금지
- `tda_pipeline/output/` — 세션 C 영역 (gitignored)
- `~/.claude/projects/.../memory/` — 세션 E 시스템 영역

## 커밋 분할 (6개 권장)

### 커밋 B1: Figures 신규 묶음

파일:
- `tda_pipeline/docs/figures/fig_algo1_sampling.png` + `gen_fig_algo1.py`
- `tda_pipeline/docs/figures/fig_algo2_neural.png` + `gen_fig_algo2.py`
- `tda_pipeline/docs/figures/fig_overlap_compare.png` + `gen_fig_overlap_compare.py`
- `tda_pipeline/docs/figures/fig_persistent_homology.png` + `gen_fig_persistent_homology.py`
- `tda_pipeline/docs/figures/fig_simplicial_homology.png` + `gen_fig_simplicial_homology.py`
- `tda_pipeline/docs/figures/fig_vr_complex.png` + `fig_vr_complex_v2.png` + gen 스크립트 2개
- `tda_pipeline/docs/figures/fig_ref_pjs_diagram.png` + `make_ref_pjs_diagram.py`
- `tda_pipeline/docs/figures/pf{1..6}_*.png` 6장
- `tda_pipeline/docs/figures/qr_hibari_original.png`, `qr_generated_placeholder.png`
- `tda_pipeline/docs/VR.webp`, `persistence.png`, `tonnetz_lattice_수정.png`,
  `mobile_UI.png`
- `M fig7_inst2_modules.png` + `M make_fig7_inst2_modules.py`
- `tda_pipeline/docs/make_portfolio_figures.py`

커밋 메시지:

```
feat(figures): 논문용 figure 일괄 생성 스크립트 + 렌더링 결과

- §2 개념 figure (VR complex, simplicial/persistent homology, overlap compare)
- §3 알고리즘 figure (Algorithm 1 sampling, Algorithm 2 neural)
- §7 figure (fig7_inst2_modules 갱신)
- pf1~pf6 포트폴리오용 figure
- QR 코드 placeholder, Tonnetz lattice 다이어그램 등
```

### 커밋 B2: LaTeX 컴파일 결과

파일:
- `tda_pipeline/docs/latex/hibari_tda.aux`, `.out`, `.pdf` (영문 IEEE)
- `tda_pipeline/docs/latex/hibari_tda_ko.aux`, `.out`, `.pdf`, `.tex` (한글)
- `tda_pipeline/docs/latex/hibari_tda_report.tex` (report 스타일)

**주의**: `.aux`와 `.out`은 일반적으로 `.gitignore` 대상. 커밋 전 판단:

- 옵션 A: `.aux`/`.out` 모두 커밋 (재현성)
- 옵션 B: `.tex`와 `.pdf`만 커밋 + `.gitignore`에 `*.aux`/`*.out` 추가

권장: **옵션 B** (산출물 재빌드 가능). `.gitignore` 수정을 본 커밋에 포함.

커밋 메시지:

```
docs(latex): hibari_tda 한글 버전 + report 스타일 추가 + gitignore 정리

- hibari_tda_ko.tex (한글 IEEE 스타일) 신규
- hibari_tda_report.tex (report 스타일) 신규
- 컴파일 산출물 .aux/.out은 gitignore 추가
```

### 커밋 B3: 보조 문서/스크립트

파일:
- `tda_pipeline/docs/portfolio_report.md`
- `tda_pipeline/docs/portfolio_report.pdf`
- `tda_pipeline/docs/md_to_pdf.py`
- `tda_pipeline/docs/fix_underscore.py`
- `tda_pipeline/docs/pdf build.txt`

**주의**: `portfolio_report.md`가 `academic_paper_portfolio (short).md`와 내용이 중복/파생인지
먼저 확인. 중복이면 커밋 전 삭제 고려.

커밋 메시지:

```
docs(aux): 포트폴리오 보조 문서 + PDF 빌드 스크립트

- portfolio_report.md/pdf (요약본)
- md_to_pdf.py (pandoc 래퍼)
- fix_underscore.py (LaTeX underscore 전처리)
- pdf build.txt (빌드 로그 메모)
```

### 커밋 B4: step3_data 잔여 JSON

파일:
- `tda_pipeline/docs/step3_data/note_reassign_wasserstein_strategy_a_results.json`
- `tda_pipeline/docs/step3_data/step_improvementF_tau_results.json`
- `tda_pipeline/docs/step3_data/step3_results_regression_gap3.json` (세션 B 회귀 검증 산출)
- `tda_pipeline/docs/step3_data/temporal_reorder_dl_results_c42.json`
- `tda_pipeline/docs/step3_data/temporal_reorder_dl_v2_results_c42.json`

커밋 메시지:

```
feat(experiment): 이전 세션 A/B 실험 JSON 정리 (wasserstein, improvementF, 회귀)

- note_reassign_wasserstein_strategy_a (방향 A 재분배 최종)
- step_improvementF_tau (개선 F per-cycle τ 변형)
- step3_results_regression_gap3 (세션 B Task 3-1 gap=3 비트 재현 테스트)
- temporal_reorder_dl_c42 / v2_c42 (방향 B PE 제거 재학습 추가 시드)
```

### 커밋 B5: 잔여 Python 스크립트

파일:
- `tda_pipeline/gen_hibari_viz_dft.py` (DFT 기반 시각화)
- `tda_pipeline/run_improvement_F_tau.py`
- `tda_pipeline/run_wasserstein_strategy_a.py`
- `tda_pipeline/utils/__init__.py` (신규, B4 리팩토링 시점)

커밋 메시지:

```
feat(scripts): 잔여 실험 러너 + 시각화 스크립트 정리

- gen_hibari_viz_dft.py (DFT barcode/overlap 시각화 생성)
- run_improvement_F_tau.py (개선 F per-cycle τ 변형 실행)
- run_wasserstein_strategy_a.py (방향 A Wasserstein 제약)
- utils/__init__.py (패키지 초기화)
```

### 커밋 B6: tonnetz_demo 대시보드 갱신

파일:
- `M tda_pipeline/tonnetz_demo/index.html`
- `M tda_pipeline/tonnetz_demo/js/hibaridata.js`
- `tda_pipeline/tonnetz_demo/design-preview.html`
- `tda_pipeline/tonnetz_demo/js/hibari_barcode_dft_data.js`
- `tda_pipeline/tonnetz_demo/js/hibari_overlap_dft_data.js`

커밋 메시지:

```
feat(dashboard): Tonnetz 데모 DFT 데이터 포트 + 디자인 프리뷰 추가

- hibari_barcode_dft_data.js / hibari_overlap_dft_data.js 신규
- index.html·hibaridata.js DFT 데이터 연동 업데이트
- design-preview.html (스타일 프리뷰 페이지)
```

## 사용자 결정 보류 항목 (커밋 안 함)

아래는 성격상 사용자 판단이 필요 — 본 세션에서는 건드리지 않고 `report.md`에 목록만 정리:

- **피드백 txt 6개** (`260414/260415/260417 *피드백*.txt`) — 커밋할지, `.gitignore`할지
- `tda_pipeline/docs/academic_paper_portfolio (上).pdf` — 용도 불명
- `tda_pipeline/docs/proofs/` 디렉토리 — 내용 확인 필요
- `tda_pipeline/memory/` (세션 B 리팩토링 중 생긴 디렉토리) — 로컬 memory인지 공유용인지
  확인 후 `.gitignore` 또는 커밋

## 산출물

- 커밋 B1~B6 (6개)
- `tda_pipeline/docs/session_b_cleanup_report.md` — 정리 내역 요약 + 사용자 결정 보류 항목
  목록

## 검수 (PR 전)

- [ ] `git status --short` 에 아래만 남아야:
  - 피드백 txt 6개
  - `academic_paper_portfolio (上).pdf`
  - `docs/proofs/` (처리 결정 전)
  - `tda_pipeline/memory/` (처리 결정 전)
  - 세션 D/C 산출물 (Task 37, WAV, memory 등)
- [ ] 금지 파일 중 수정된 것 0건
- [ ] `.gitignore`에 `*.aux`, `*.out` 추가됨 (B2 옵션 B 채택 시)

## 세션 E 후속 (귀환 후)

1. 사용자 결정 보류 항목에 대한 지시 대기
2. `memory/project_cleanup_0417.md` 간단 기록 (몇 커밋, 무엇 정리됐는지)
