# listening_test (Task 45)

체계적 청취 실험을 바로 실행할 수 있도록, 자극 생성/프로토콜/분석 템플릿을 모은 폴더입니다.

## 구성 파일
- `generate_test_stimuli.py`: A~H(옵션 I~L) 자극 WAV 세트 생성
- `protocol.md`: 실험 진행 프로토콜
- `analysis_template.py`: 응답 통계 분석 템플릿
- `consent_form.md`: 참여 동의서 초안
- `response_schema.json`: 응답 JSON 스키마

## 빠른 시작
1. 자극 생성
```bash
cd C:\WK14\tda_pipeline
python listening_test\generate_test_stimuli.py
```

2. HTML 플레이어 확인 (모바일 우선)
- 생성 위치: `output/listening_test/index.html`
- 스마트폰 브라우저로 열어서 재생/볼륨/길이 확인

3. 응답 분석 (수집 후)
```bash
python listening_test\analysis_template.py --input <response_bundle.json>
```

## 출력 위치
- 오디오: `output/listening_test/stimuli/*.wav`
- 메타:
  - `output/listening_test/stimuli_manifest.json`
  - `output/listening_test/stimuli_catalog.csv`
  - `output/listening_test/index.html`

## D/E/F 소스가 없을 때
`major_block32` 계열 파일이 없으면 manifest에 `missing`으로 표시됩니다.

수동 지정 방법:
1. `listening_test/stimuli_overrides.example.json`을 복사해 `listening_test/stimuli_overrides.json` 생성
2. 아래 형식으로 경로 입력

```json
{
  "D": "output/section66/major_block32_tonnetz_transformer.mid",
  "E": "output/section66/major_block32_dft_transformer.mid",
  "F": "output/section66/major_block32_dft_fc.mid"
}
```

3. 다시 실행
```bash
python listening_test\generate_test_stimuli.py --overrides listening_test\stimuli_overrides.json
```

## 운영 팁
- 파일럿(N=10): 웹 폼 + `index.html` 병행
- 본실험(N>=23): 동일 스키마 유지(재분석 자동화)
- 기본값은 익명 수집(`participant_id`)만 사용

## 체크리스트
- [ ] A~H 준비 완료(누락 0)
- [ ] 모바일 재생/볼륨 정상
- [ ] 동의서/응답 폼 항목 동기화
- [ ] response_schema.json 기준 검증 통과
