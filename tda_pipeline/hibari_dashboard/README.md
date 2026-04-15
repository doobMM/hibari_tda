# Hibari Overlap Matrix Dashboard

hibari TDA 연구의 웹 대시보드. 사용자가 브라우저에서 overlap matrix를
직접 편집하고 → Algorithm 1/2 로 음악을 생성·재생할 수 있다.

## 디렉토리

```
hibari_dashboard/
├── data/        # Python 에서 export 한 JSON + MIDI (정적)
├── public/      # 정적 웹 자산 (HTML/JS/CSS)
├── scripts/     # 데이터 export·모델 변환 스크립트
└── README.md
```

## 데이터 재생성

실험 B 최적 설정(complex α=0.25, ow=0.0, dw=0.3, r_c=0.1 + per-cycle τ)으로
overlap matrix / notes meta / cycles meta 를 재계산:

```bash
cd C:/WK14/tda_pipeline
python hibari_dashboard/scripts/export_hibari_data.py
```

출력:
- `data/overlap_matrix_reference.json`   — 이진 overlap (T=1088, K=40)
- `data/overlap_matrix_continuous.json`  — 연속 activation (soft Algo2 입력)
- `data/notes_metadata.json`             — 23종 note 메타데이터
- `data/cycles_metadata.json`            — 40개 cycle 구성·persistence
- `data/original_hibari.mid`             — 원곡 복사
- `data/manifest.json`                   — 버전·경로 manifest

## 로컬 실행

데이터(`data/`)가 `public/`과 같은 레벨에 있으므로 서버는
`hibari_dashboard/` 에서 띄운다:

```bash
cd C:/WK14/tda_pipeline/hibari_dashboard
python -m http.server 8000
# 브라우저: http://localhost:8000/public/index.html
```

배포 시 `public/` 만 올려야 한다면 `public/` 안에 `data/` 를 복사하고
`index.html` 에 `?data=data` 쿼리를 붙여 접근.

## Phase 진행 상태

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | 데이터 export (Python) | ✓ |
| 2 | 정적 웹 scaffold | 진행 중 |
| 3 | Overlap Matrix 에디터 UI | 대기 |
| 4 | Algorithm 1 JS 포팅 + 재생 | 대기 |
| 5 | FC 모델 ONNX export + 브라우저 추론 | 대기 |
| 6 | OOD 경고 + 마무리 | 대기 |

## 제약 사항

- 기존 `tda_pipeline/` 파일은 **읽기 전용**. 본 대시보드는
  `hibari_dashboard/` 하위에만 새 코드를 둔다.
- 데이터는 실험 B (N=20 재검증) 기준. 다른 설정으로 바꾸려면
  `scripts/export_hibari_data.py` 의 `EXP_B_CONFIG` 수정.
