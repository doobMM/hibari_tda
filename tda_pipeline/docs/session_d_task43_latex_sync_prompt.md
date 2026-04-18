# 세션 D — Task 43: LaTeX 한·영 버전 최종 동기화 (Phase 3 반영)

## 배경

md 원고는 Phase 3 (Task 38a/38b/39/39-4/40/41) 및 Wave 2 (27개 질문)를 거치며 Phase 3
종결 상태로 반영됨. 그러나 LaTeX 파일들은 마지막 동기화(커밋 `8477dc5`, 2026-04-15
"hibari_tda 한글 버전 + report 스타일 추가") 이후 **주요 변경사항이 미반영**.

대상 파일:
- `tda_pipeline/docs/latex/hibari_tda.tex` (영문 IEEE, 제출용 1순위)
- `tda_pipeline/docs/latex/hibari_tda_ko.tex` (한글 IEEE)
- `tda_pipeline/docs/latex/hibari_tda_report.tex` (report 스타일, 장문)

## 미반영 변경사항 (md 최신 vs LaTeX 마지막 동기화)

### Phase 2/2b 이후 (Task 36 이후)

- §4 gap0+DFT 전면 재서술 (Task 35, 9873cdd)
- §6.7.1 per-cycle τ +58.7% p=2.48e-26, JS=0.01489 (Task 36, 8c4e3ae)
- §6.7.2 FC-cont 0.000348 (Welch p=1.66e-4) (Task 36)
- §6.8 DFT α-hybrid α=0.25 (Task 36)
- §6.9 complex Tonnetz 한정 유효 서사 반전 (Task 36)
- §7 baseline DFT 0.0213 교체 (Task 37)
- §8 결론 수치 통일 (Task 37)
- 초록 Algo1 0.01489 / Algo2 0.00035 (Task 37)

### Phase 3 이후 (Task 38a/38b)

- §7.1 K=14 (32×42 → 32×14)
- §7.2 P0~P3 DFT 전략
- §7.5 P3+C best 0.0250
- §7.6 best global JS=0.01479 ≈ full-song
- §7.7 first-module 우위 미재현 (Tonnetz-specific)
- §7.8 Pearson 0.503 → −0.054

### Wave 2 + Task 41 이후

- §6.1 solari DFT 열 (0.0824 K=15)
- §6.2 Bach DFT (0.0951) / Ravel DFT (0.0494) + "hibari만 DFT 최적" 확정
- §6.3 "본 장은 Tonnetz 기반" 선언
- §6.4 세 모델 실증 (FC 시점 독립, LSTM "≤0.5% 실측", Transformer)
- §6.5 FC/LSTM 확장
- §6.6 3분할 (6.6.1 Tonnetz 성공 / 6.6.2 DFT 실패 / 6.6.3 메타)
- §8 결론 6항 신설: "거리 함수 × 음악적 목적 정합성"

## 파일별 소스 매핑

| LaTeX 파일 | 소스 md | 분량 | 역할 |
|---|---|---|---|
| `hibari_tda.tex` | `academic_paper_portfolio (short).md` | 축약 (IEEE) | 제출용 1순위 |
| `hibari_tda_ko.tex` | `academic_paper_portfolio (short).md` | 축약 (한글 IEEE) | 한국어 제출 |
| `hibari_tda_report.tex` | `academic_paper_full.md` | 장문 (report) | 완전 보고서 |

## 필수 참조 파일

### 읽을 것

- 최신 md:
  - `tda_pipeline/docs/academic_paper_portfolio (short).md`
  - `tda_pipeline/docs/academic_paper_full.md`
- 현재 LaTeX:
  - `tda_pipeline/docs/latex/hibari_tda.tex`
  - `tda_pipeline/docs/latex/hibari_tda_ko.tex`
  - `tda_pipeline/docs/latex/hibari_tda_report.tex`
- memory:
  - `project_task41_section6_rewrite_0417.md` — Task 41 반영 내용
  - `project_task38b_section7_rewrite_0417.md` — Task 38b 반영 내용
  - `feedback_short_md_gap_comparison_exclude.md` — short/full 규칙 (LaTeX 영문·한글
    short도 동일 원칙)
- `CLAUDE.md` — 논문-코드 정합성 규칙

### 수정할 것

- `tda_pipeline/docs/latex/hibari_tda.tex`
- `tda_pipeline/docs/latex/hibari_tda_ko.tex`
- `tda_pipeline/docs/latex/hibari_tda_report.tex`
- 컴파일 산출물 (`.aux`, `.out`, `.pdf`)은 컴파일 결과만. `.gitignore` 정책 유지
  (aux/out 제외).

### 금지

- 최신 md 원고 수정 (이미 확정됨)
- `CLAUDE.md` 수정

## 작업 범위 — 3개 파일 분할

### ① `hibari_tda.tex` (영문 IEEE) — 1순위

**범위**: short.md 기반. 아래 구성으로 동기화.

1. 초록 수치 동기화 (Algo1 0.01489 / Algo2 0.00035 등)
2. §4 표 갱신 (gap0+DFT 수치, DFT 38.2%/Tonnetz 56.8%/VL 62.4%)
3. §6.1/§6.2 DFT 열 추가 + "hibari만 DFT 최적"
4. §6.3 Tonnetz 기반 선언
5. §6.4 세 모델 서술 (FC/LSTM/Transformer 행동)
6. §6.6 3분할 (Tonnetz 성공 / DFT 실패 / 메타 통찰)
7. §6.7 per-cycle τ +58.7% + FC-cont 0.000348
8. §6.8 DFT α-hybrid α=0.25
9. §6.9 Tonnetz 한정 유효
10. §7 K=14, P3+C best 0.0250, best global 0.01479, §7.7 서사 반전, §7.8 Pearson 반전
11. §8 결론 6항 (메타 통찰) 추가

**LaTeX 특수 주의**:
- 수식 레이블 `\label{eq:...}` 참조 변경 시 `\ref{}` 일괄 수정
- 표 `\begin{table}` 내 수치 정합
- 인용 `\cite{}` 기존 bib 항목 재사용
- `\section{}` · `\subsection{}` 번호 체계 유지 (§6.6.1/§6.6.2/§6.6.3 신설)

### ② `hibari_tda_ko.tex` (한글 IEEE)

`hibari_tda.tex`와 동일 구성 + 한글 번역. 한국어 학회 제출 계획이 있으면 작업. 없으면 보류
가능 (사용자 판단).

**권장 접근**: `hibari_tda.tex` 먼저 완성 → 그 구조 복제 후 한글 번역. 기존 한글본
문장을 유지하면서 새 수치·섹션만 업데이트.

### ③ `hibari_tda_report.tex` (report 장문)

**범위**: full.md 기반. 짧은 IEEE 버전보다 역사적 맥락·각주 풍부.

- full.md에 있는 Tonnetz 역사적 각주 유지 (§6.6.1 pre-bugfix 각주 등)
- Phase 3 이전 서술도 일부 보존 가능 (비교 맥락)
- §6.6.3 메타 통찰 + §6.9 complex Tonnetz 한정 두 사례를 연결하는 장문 해석

**우선순위**: IEEE 버전 완성 후 착수. 단독 제출 계획 없으면 후순위.

## 작업 순서 (권장)

```
1. hibari_tda.tex (영문 IEEE) 전면 동기화 + 컴파일 테스트
    ↓
2. hibari_tda_ko.tex — 한글 번역 반영 + 컴파일 테스트
    ↓
3. hibari_tda_report.tex — full.md 기반 + 장문 해석
    ↓
4. 세 파일 PDF 컴파일 + cross-reference 검증
```

## 컴파일 검증

각 `.tex` 파일에 대해:

```bash
cd tda_pipeline/docs/latex
pdflatex hibari_tda.tex     # 1회
bibtex hibari_tda           # bib 처리
pdflatex hibari_tda.tex     # 2회 (ref 해결)
pdflatex hibari_tda.tex     # 3회
```

검증 항목:
- 컴파일 에러 0건
- `undefined references` 0건
- 모든 `\ref{}` 정상 해결
- 표·그림 번호 일관성

## 산출물

1. `hibari_tda.tex` (M)
2. `hibari_tda_ko.tex` (M) (필요 시)
3. `hibari_tda_report.tex` (M) (필요 시)
4. 컴파일 결과 PDF 3종 (선택)

## 커밋 지침

3파일 동시 또는 파일별 분리:

### 파일별 분리 (권장)

```
docs(latex): Task 43-A hibari_tda.tex 영문 IEEE Phase 3 반영

- 초록 Algo1 0.01489 / Algo2 0.00035
- §4 gap0+DFT + §6.6 3분할 + §7 K=14 + §8 6항 메타 통찰
- 컴파일 성공, undefined ref 0
```

```
docs(latex): Task 43-B hibari_tda_ko.tex 한글 버전 동기화
```

```
docs(latex): Task 43-C hibari_tda_report.tex report 장문 동기화
```

## 검수 체크리스트 (PR 전)

### 각 LaTeX 파일별 공통

- [ ] Algo1 최저 수치 0.01489 존재
- [ ] Algo2 최저 수치 0.00035 존재
- [ ] §6.6.1/§6.6.2/§6.6.3 (또는 equivalent LaTeX `\subsection{}`) 존재
- [ ] §8 결론 6항 "거리 함수 × 목적" 존재
- [ ] §7.1 K=14 (또는 14-cycle 표기) 존재
- [ ] §7.7 first-module rank=5 언급 존재
- [ ] §7.8 Pearson −0.054 존재
- [ ] DFT 38.2% / Tonnetz 56.8% 수치 존재 (§4.1)
- [ ] 컴파일 에러 0

### 영문/한글 IEEE 버전

- [ ] gap_min=3 문자열 0건
- [ ] Tonnetz 기존 §7 수치 (0.503 등) 0건 — full.md 각주 레벨만 허용

### report 버전

- [ ] Tonnetz 역사적 각주 유지
- [ ] 메타 통찰 장문 해석 포함

## 세션 간 병렬 안전성

- 본 Task는 `docs/latex/*.tex` 수정 전용.
- 세션 A Task 42 (std 재검증)와 **파일 영역 완전 분리** — 동시 실행 OK.
- `.md` 원고는 수정하지 않음.

## 세션 D 연동

Task 43 완료 후 세션 E 루틴:

1. 3 tex 파일 커밋 (분리 또는 통합)
2. memory: `project_task43_latex_sync_0417.md` 신설
3. CLAUDE.md Task 19(기존 LaTeX 업데이트) + Task 43 ✓ 표시
4. 제출 준비 마무리 단계 돌입

## 예상 소요

- hibari_tda.tex 동기화: 2~3시간 (md 구조 복잡, 수식·표 다수)
- hibari_tda_ko.tex 한글 번역 반영: 1~2시간
- hibari_tda_report.tex 장문 동기화: 2~4시간
- **총 5~9시간** (세 파일 모두). IEEE 버전만 하면 2~3시간.

## 우선순위

- **1순위 (필수)**: hibari_tda.tex (영문 IEEE) — 제출용
- **2순위 (권장)**: hibari_tda_ko.tex — 한국어 학회 제출 계획 있으면
- **3순위 (선택)**: hibari_tda_report.tex — 별도 보고서 필요 시

사용자가 1순위만 먼저 지시하고 2·3순위는 제출 계획 확정 후 진행 가능.

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음 + 권한 전체 액세스**. LaTeX 수식·구조
섬세함 때문에 "매우 높음" 필수.
