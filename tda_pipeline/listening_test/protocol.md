# Listening Test Protocol (Task 45)

## 1) 한 줄 요약
원곡 `hibari`와 생성곡(A~H)을 블라인드로 들려주고, "비슷함/자연스러움/선호"를 정량화해 Q3(미학적 타당성)를 검증한다.

## 2) 연구 질문
1. 수치-청각 정합성: JS가 낮은 조건(C)이 실제 청취에서도 더 유사하게 들리는가?
2. gap=0 롤백 타당성: G(gap=3)보다 B/C(gap=0)가 더 자연스러운가?
3. 위상 보존 변주의 미학: D가 "같은 느낌의 다른 곡"으로 평가되는가?
4. Tonnetz vs DFT 차이: D와 E/F의 체감 차이가 통계적으로 드러나는가?

## 3) 자극(Stimuli) 구성
- 필수 8종: A~H
- 권장 길이: 45초 클립(기본), 필요 시 전체 길이 보조 청취
- 라벨만 노출: 파일명에 모델/거리함수 노출 금지

자극 라벨 의미:
- A: 원곡 hibari
- B: Algo1 최적 (DFT + per-cycle tau)
- C: Algo2 최적 (DFT + FC-cont)
- D: major_block32 Tonnetz-Transformer
- E: major_block32 DFT-Transformer
- F: major_block32 DFT-FC
- G: 레거시 gap=3
- H: 레거시 Tonnetz complex

## 4) 평가 절차
### 단계 1 - 단일 자극 MOS (필수)
각 자극 청취 후 1~5점 척도:
- Similarity: 원곡과 얼마나 비슷한가
- Naturalness: 음악으로 얼마나 자연스러운가
- Preference: 다시 듣고 싶은가

반복 청취 규칙:
- 자극당 최대 3회 재생 허용
- 헤드폰 권장
- 모바일/데스크톱 모두 가능(모바일 우선 UI)

### 단계 2 - A/B 선호 비교 (필수)
핵심 쌍:
- B vs C (Algo1 vs Algo2)
- D vs E (Tonnetz vs DFT-Transformer)
- B vs G (gap=0 vs gap=3)

응답:
- "왼쪽이 더 적합" / "오른쪽이 더 적합" 중 1개 선택

## 5) 피험자 구성
- 전문가 그룹: 작곡/연주/음악 전공 또는 실무 경험자, 목표 N >= 8
- 일반 그룹: 비전공 청취자, 목표 N >= 15
- 최소 파일럿: N >= 10

## 6) 블라인드 및 순서 제어
- 조건명 비공개 (A~H만 사용)
- 순서 무작위 또는 Latin square
- 한 세션 30분 이내
- 자극 순서/반복 횟수 로그 저장

## 7) 수집 채널 (웹 우선)
기본 권장:
1. 파일럿: Google Forms + `output/listening_test/index.html` 플레이어 병행
2. 본실험: Streamlit/Flask 웹 폼 (모바일 우선)

웹 폼 필수 항목:
- 동의 여부
- 그룹(expert/general)
- 기기 종류(mobile/desktop/tablet)
- 자극별 MOS 3항목
- A/B 쌍 선택

## 8) 데이터/보안 원칙
- 기본값: 익명 수집(이름/이메일 미수집)
- `participant_id`만 사용 (예: `P001`)
- 원본 응답 JSON은 비공개 저장소/로컬만 보관
- 공개 전에는 집계 통계만 공유

## 9) 윤리/저작권 체크
- 연구 목적 비공개 청취 전제
- 공개 배포 전 저작권 검토 필요
- 철회권/보관기간/연락처 포함 동의서 사용
- IRB 필요 여부는 제출 기관 정책에 맞춰 사전 확인

## 10) 분석 계획 (요약)
- MOS 평균/표준편차 (자극별, 그룹별)
- Spearman rho: JS vs Similarity MOS
- Mann-Whitney U: 전문가 vs 일반 그룹 차이
- Wilcoxon signed-rank: A/B 쌍 비교

## 11) 실행 체크리스트
- [ ] `python listening_test/generate_test_stimuli.py` 실행
- [ ] `output/listening_test/index.html` 모바일 재생 확인
- [ ] 필수 8종(A~H) 준비 확인
- [ ] 동의서/응답 스키마 반영한 설문 링크 생성
- [ ] 파일럿 10명 수집 후 분석 템플릿 dry run
