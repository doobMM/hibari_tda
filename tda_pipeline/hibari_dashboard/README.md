# Hibari Overlap Matrix Dashboard

hibari TDA 연구의 웹 대시보드. 사용자가 브라우저에서 overlap matrix를
직접 편집하고 → Algorithm 1/2 로 음악을 생성·재생할 수 있다.

## 디렉토리

```
hibari_dashboard/
├── data/                 # Python 에서 export 한 JSON + MIDI (정적)
│   ├── overlap_matrix_reference.json
│   ├── overlap_matrix_continuous.json
│   ├── notes_metadata.json
│   ├── cycles_metadata.json
│   ├── original_hibari.mid
│   └── manifest.json
├── public/               # 정적 웹 자산
│   ├── index.html
│   ├── css/style.css
│   ├── js/
│   │   ├── data-loader.js          # JSON 로드 + Float32Array 변환
│   │   ├── overlap-editor.js       # Canvas 에디터 (zoom/pan/DPR)
│   │   ├── generation-algo1.js     # Python 포팅 (NodePool + CycleSetManager)
│   │   ├── generation-algo2.js     # FCGenerator (onnxruntime-web)
│   │   ├── midi-io.js              # SMF format 0/1 reader/writer
│   │   ├── audio-playback.js       # Web Audio 피아노 synth
│   │   ├── ood-detector.js         # Hamming + density + persistence-weighted
│   │   └── ui-bootstrap.js         # DOM 배선
│   └── models/
│       ├── fc_model.onnx           # 173 KB, 40→128→256→23
│       └── fc_model_meta.json      # label → (pitch, dur) 매핑
├── scripts/
│   ├── export_hibari_data.py       # Phase 1 데이터 export
│   └── train_fc_and_export.py      # Phase 5 FC 학습 + ONNX 저장
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

## FC 모델 재생성

FC 모델 체크포인트와 ONNX 파일을 다시 만들려면:

```bash
cd C:/WK14/tda_pipeline
python hibari_dashboard/scripts/train_fc_and_export.py
```

- 전처리 → multi-hot y 구성 → 300 epochs FC 학습 → ONNX export
- 산출: `public/models/fc_model.onnx` (~173 KB) + `fc_model_meta.json`
- 학습 시간: CPU 30 초 정도. `onnxscript` / `onnx` 패키지 필요:
  `pip install onnx onnxscript` (torch ≥ 2.6 기본 dynamo 백엔드용)

## Phase 진행 상태

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | 데이터 export (Python) | ✓ |
| 2 | 정적 웹 scaffold | ✓ |
| 3 | Overlap Matrix 에디터 UI | ✓ |
| 4 | Algorithm 1 JS 포팅 + 재생 | ✓ |
| 5 | FC 모델 ONNX export + 브라우저 추론 | ✓ |
| 6 | OOD 경고 + 마무리 | ✓ |

## 기능 요약

- **에디터** (편집 matrix): 좌클릭 토글, 우클릭 지움, Shift+드래그 팬, 휠 줌, 더블클릭 리셋
- **참조 matrix**: 읽기 전용. 실험 B 최적 설정의 이진 overlap.
- **diff 하이라이트**: 토글 시 참조 대비 추가/삭제 셀을 청록/핑크로 표시
- **Algorithm 1**: 확률적 샘플링 (mulberry32 seed, temperature로 분포 스케일). 20 ms 내외
- **Algorithm 2 (FC)**: ONNX 추론 (CDN 로드). temperature 는 adaptive threshold 의 targetOnRatio 로 사용
- **원곡 재생**: `original_hibari.mid` 를 JS 로 파싱 후 Web Audio synth 로 재생
- **MIDI 저장**: 생성된 notes 를 SMF format 0 로 직렬화 후 브라우저 다운로드
- **OOD 배너**: 편집이 참조에서 얼마나 벗어났는지 실시간 계산. `<5%` 안정, `<12%` 정상, `<25%` 주의, `≥25%` 경고
- **localStorage 자동 저장**: 편집 상태 유지, 새로고침해도 복구

## 제약 사항

- 기존 `tda_pipeline/` 파일은 **읽기 전용**. 본 대시보드는
  `hibari_dashboard/` 하위에만 새 코드를 둔다.
- 데이터는 실험 B (N=20 재검증) 기준. 다른 설정으로 바꾸려면
  `scripts/export_hibari_data.py` 의 `EXP_B_CONFIG` 수정 후
  `train_fc_and_export.py` 를 재실행하여 FC 모델도 함께 갱신.
- 외부 의존: onnxruntime-web 은 jsdelivr CDN 에서 지연 로드
  (Algorithm 2 첫 실행 시). 오프라인 배포 시 `public/vendor/` 에
  ort.min.js + .wasm 사본을 두고 `generation-algo2.js` 의
  `ORT_CDN_URL` 을 로컬 경로로 교체.
