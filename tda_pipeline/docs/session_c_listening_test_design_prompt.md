# 세션 C — Task 45: 체계적 청취 실험(Listening Test) 설계

## 배경

본 연구 §8 결론 5항에 "체계적인 청취 실험은 향후 연구 과제로 남긴다" 명시. 지금까지의
청취 평가는 사용자 비공식 감상 (`memory/project_complex_wav_eval_0416.md`,
`project_final_wav_eval_0417.md`) 만 수행됨.

본 Task 45는 **체계적 청취 실험 프로토콜 + 평가 WAV 세트 + 분석 스크립트 템플릿**을
설계·준비한다. 실제 피험자 모집·실행은 범위 밖 (별도 Task).

## 연구 질문

논문에서 제기된 3대 질문 중 Q3 (미학적 타당성) 을 정량화:

1. **수치-청각 정합성**: JS divergence 최저 설정(Algo2 FC-cont 0.00035)이 청각적으로도
   "원곡과 유사"로 평가되는가? 수치 순위와 MOS 순위의 상관?
2. **gap=0 롤백 타당성**: gap=3 폐기 결정이 전문가 청취로도 지지되는가?
3. **위상 보존 변주의 미학적 성공**: §6.6 major_block32("pitch 보존 + 선율 변화")가
   "원곡과 같은 느낌이면서 다른 곡"으로 들리는가?
4. **Tonnetz vs DFT 청각 차이**: §6.6.2 DFT 전환 악화가 청각으로도 감지되는가?

## 필수 참조 파일

### 읽을 것

- `memory/project_complex_wav_eval_0416.md` — 기존 비공식 청취 평가
- `memory/project_final_wav_eval_0417.md` — gap0 최종 청취 평가
- `memory/feedback_generation_direction.md` — "비슷한 느낌의 다른 공간" 연구 목표
- `memory/feedback_piano_rendering.md` — 피아노 렌더링 설정 (서스테인 페달 + reverb)
- `tda_pipeline/gen_final_wavs.py` — 기존 WAV 생성 스크립트 (기반으로 확장)
- `tda_pipeline/docs/academic_paper_portfolio (short).md` §8 — 논문의 향후 과제 서술
- CLAUDE.md — 세션 운용 가이드

### 수정·추가할 것

- 신규 `tda_pipeline/listening_test/` 디렉토리 생성
  - `generate_test_stimuli.py` — 평가 WAV 세트 생성
  - `protocol.md` — 실험 설계 프로토콜 문서
  - `analysis_template.py` — 응답 수집 후 통계 분석 템플릿
  - `consent_form.md` — 피험자 동의서 초안
  - `response_schema.json` — 응답 데이터 구조
- `docs/step3_data/` 또는 `output/listening_test/` — 생성 WAV 저장

### 금지

- `academic_paper_*.md` 수정 (결과 도착 후 세션 D 영역)
- `CLAUDE.md` 수정

## 작업 범위

### ① 평가 WAV 세트 설계 (8~12 stimuli)

`gen_final_wavs.py` 확장. 각 WAV는 30~60초 발췌 또는 전체 재생 (hibari ≈ 3~4분).

**권장 8 stimuli 세트**:

| # | 조건 | 설정 | 목적 |
|---|---|---|---|
| A | **원곡 hibari** | 원본 MIDI | 기준 |
| B | Algo1 최적 | DFT + per-cycle τ, JS=0.01489★ | 연구 최저 Algo1 |
| C | Algo2 FC-cont 최적 | DFT + FC-cont, JS=0.00035★ | 연구 최저 Algo2 |
| D | §6.6.1 Tonnetz 성공 사례 | major_block32 Tonnetz-Transformer | 위상 보존 변주 성공 |
| E | §6.6.2 DFT 전환 실패 | major_block32 DFT-Transformer | 수치 악화 청각 검증 |
| F | §6.6.2 DFT-FC | major_block32 DFT-FC | FC 변주 후보 검증 |
| G | 레거시 gap=3 | gap_min=3 Algo1 | 롤백 결정 재검증 |
| H | 레거시 Tonnetz complex | §6.9 실험 B | 폐기 결정 재검증 |

(선택) 12 stimuli로 확장 시:
- I: Algo1 baseline (DFT 단독, per-cycle τ 없음)
- J: FC-bin (continuous 없음)
- K: frequency 거리 (기준선)
- L: §4.2 Continuous direct

**렌더링 설정 (`feedback_piano_rendering.md` 준수)**:

- UprightPiano SF2, 44.1kHz, 16-bit stereo
- **서스테인 페달 on (전 구간)** + reverb (medium hall)
- 템포: 원곡 기준 (약 60 BPM)

### ② 실험 프로토콜 설계 (`protocol.md`)

#### 평가 방식 (2단계)

**1단계 — 단일 자극 평가 (MOS)**: 각 stimulus를 개별 청취 후 5점 척도 평가
- 유사도 (원곡과 비슷한 정도)
- 자연스러움 (음악으로 자연스러운 정도)
- 선호도 (얼마나 다시 듣고 싶은가)
- (선택) 자유 서술 코멘트

**2단계 — A/B 선호도 비교**: 주요 쌍 비교
- B vs C (Algo1 vs Algo2) — 수치-청각 정합성
- D vs E (Tonnetz vs DFT 변주) — 메타 통찰 검증
- B vs G (gap=0 vs gap=3) — 롤백 근거

#### 피험자 (2 그룹)

- **전문가 그룹**: 음악 전공자·작곡가·연주자, N ≥ 8
- **일반 청취자 그룹**: 음악 교육 비전공, N ≥ 15
- 총 N ≥ 23 (파일럿은 N ≥ 10)

#### 블라인드·순서

- 파일명 숨김 (A~H 라벨만)
- Latin square 또는 무작위 순서
- 반복 청취 허용 (최대 3회)
- 피험자 내 세션 길이 30분 이내 (피로 방지)

### ③ 분석 계획 (`analysis_template.py`)

- MOS 평균 ± std per stimulus / per group
- 수치-청각 상관: Spearman ρ (JS vs MOS-유사도)
- 그룹 간 비교: Mann-Whitney U test (전문가 vs 일반)
- 쌍 비교: Wilcoxon signed-rank test
- 자유 서술 thematic coding (선택)

예상 가설:
- JS vs MOS-유사도 상관: 강한 음의 상관 (낮은 JS → 높은 유사도)
- B(Algo1) vs C(Algo2): 수치상 C가 원곡 가까움 → MOS-유사도에서도 C > B 예상
- D > E: Tonnetz 변주가 DFT 변주보다 청각적 자연스러움
- G(gap=3) MOS-자연스러움 < 다른 조건 (롤백 근거)

### ④ 응답 수집 인프라

3개 옵션 중 선택:

| 옵션 | 장점 | 단점 |
|---|---|---|
| **Google Forms** | 빠름, 무료, 반응 수집 자동 | WAV 재생 UX 단순 |
| **자체 웹 (Streamlit/Flask)** | WAV 플레이어 커스터마이즈, 로그 상세 | 구현 시간 1~3일 |
| **오프라인 (대면)** | 통제 환경, 고품질 헤드폰 | 피험자 모집 제약 |

**권장**: 파일럿 (N=10) 은 Google Forms, 본 실험 (N≥23) 은 자체 Streamlit 웹. 또는 전체
Google Forms로 가볍게 시작.

### ⑤ 윤리·저작권 체크

- **저작권**: 사카모토 류이치 "hibari" — 학술 연구 fair use 범위 확인. 비공개 or 접근
  제한 실험으로 유지. 결과 논문에도 30초 이하 발췌 권장.
- **피험자 동의서 (`consent_form.md`)**: 목적·방법·데이터 보관·철회 권리 명시.
- **IRB**: 학술지 제출 시 기관 IRB 또는 학과 윤리심사. 초안 체크리스트 포함.
- **데이터 보관**: 피험자 ID 익명화, raw response JSON 별도 보관.

## 산출물

1. `tda_pipeline/listening_test/generate_test_stimuli.py` — 8~12 WAV 생성 (gen_final_wavs.py 확장)
2. `tda_pipeline/listening_test/protocol.md` — 실험 프로토콜 문서
3. `tda_pipeline/listening_test/analysis_template.py` — 통계 분석 템플릿 (응답 JSON 받으면 즉시 실행 가능)
4. `tda_pipeline/listening_test/consent_form.md` — 피험자 동의서 초안
5. `tda_pipeline/listening_test/response_schema.json` — 응답 데이터 구조
6. `tda_pipeline/listening_test/README.md` — 전체 운영 가이드
7. WAV 세트 (gitignored `output/listening_test/`)

## 커밋 지침

```
feat(listening_test): Task 45 체계적 청취 실험 설계 + 인프라

- 8 stimuli WAV 세트 (원곡 / Algo1 / Algo2 / major_block32 4종 / 레거시 2종)
- protocol.md: 2단계 평가 (MOS + A/B), 전문가 N≥8 + 일반 N≥15, 블라인드
- analysis_template.py: MOS, Spearman ρ, Mann-Whitney U, Wilcoxon
- consent_form.md: 피험자 동의서 초안
- response_schema.json: 응답 JSON 구조
- README.md: 운영 가이드

실행 (피험자 모집·응답 수집) 은 별도 과제.
```

## 검수 체크리스트

- [ ] WAV 8종 생성 스크립트 + 출력 경로
- [ ] protocol.md 내 5개 필수 항목 (평가 방식 / 피험자 / 순서 / 척도 / 반복)
- [ ] analysis_template.py에 Spearman / Mann-Whitney / Wilcoxon 최소 3개 통계 함수
- [ ] consent_form.md 필수 항목 (목적/방법/철회권/보관기간)
- [ ] response_schema.json 스키마 유효성
- [ ] 저작권·IRB 체크 섹션 포함

## 예상 소요

- WAV 생성 스크립트 확장: 1~2시간
- protocol.md 작성: 2~3시간
- analysis_template.py: 1~2시간
- consent / schema / README: 1시간
- **총 5~8시간** (설계만, 실제 실행 제외)

## 세션 구분

- **세션 C (본 Task)**: 설계 + 인프라
- **세션 C 후속 (Task 46, 별도)**: 파일럿 실행 + 응답 수집 (인간 활동, 자동화 불가)
- **세션 A 후속 (Task 47, 별도)**: 응답 데이터 분석 (analysis_template.py 실행)
- **세션 D 후속 (Task 48, 별도)**: 결과를 §8 또는 §9 신설로 논문 반영

## 세션 간 안전성

- 본 Task는 `tda_pipeline/listening_test/` 신규 디렉토리 전용.
- 다른 Task와 파일 영역 완전 분리.
- `academic_paper_*.md` / `CLAUDE.md` 건드리지 않음.

## 완료 후 세션 E 루틴

1. `listening_test/` 디렉토리 커밋
2. memory: `project_task45_listening_design_0417.md` 신설
3. CLAUDE.md "후속 과제" 섹션에 Task 45 ✓ + Task 46/47/48 대기 표시
4. 파일럿 실행 계획 사용자 협의

모델 권장: **GPT-5.3-Codex + reasoning 매우 높음 + 권한 전체 액세스**. 연구 방법론 설계
+ 통계·윤리 섬세함 필요.

## 실행 주의

- 저작권 이슈: 생성 WAV는 학술 연구 목적 비공개 배포 전제. 공개 플랫폼 업로드 시 재고.
- 피험자 윤리: IRB 미승인 상태에서는 파일럿 10인 이하 비공식 실행만 권장.
- 시간: 체계적 실험은 최소 2~4주 (모집 + 응답 + 분석). 논문 제출 일정과 조율.
