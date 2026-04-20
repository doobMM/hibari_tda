---
description: 모바일 웹 작업(R4/R5) 진입 시 조건부 로드. 320~768px 뷰포트 가정.
activate_when:
  - "editing `hibari_dashboard/public/**` with viewport concerns"
  - "editing `mobile_tonnetz/**` or any R5 prototype"
  - "user mentions: 모바일, 핸드폰, responsive, tilt, gyro, DeviceOrientation"
---

# 모바일 규칙

## 레이아웃

- **기본 뷰포트: 320px** (iPhone SE). 375px(표준 iPhone), 768px(태블릿) 순으로 검증.
- `<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">`
- **터치 타깃 최소 44×44px** (Apple HIG).
- 스크롤은 세로 1축만 허용. 가로 스크롤 유발 금지.
- Canvas 에디터는 **SVG로 대체 검토** — 모바일 GPU 부담 ↓, 터치 이벤트 ↑.

## 센서

- `DeviceOrientationEvent`는 **iOS 13+에서 사용자 제스처 필요** — 버튼 클릭 후 `requestPermission()` 호출.
- `DeviceMotionEvent`도 동일 권한 플로우.
- 권한 거부 시 **키보드·터치 대체 인터랙션 필수** (접근성).
- 안드로이드는 권한 불필요이지만 HTTPS 필수.

## 성능

- **메인 스레드 60fps 유지** — onnxruntime-web 추론은 Web Worker로.
- 30초 분량 생성 기준 **T=60 step** (현 대시보드 T=1088의 1/18) — seed 1개면 <200ms 안에 끝나야 함.
- Bundle size < 500KB (초기 로드). 모델 173KB는 별도 지연 로드.

## 오프라인·배포

- GitHub Pages 배포 가정 — 절대 경로 금지, `./relative/path` 사용.
- Service Worker로 static assets precache (선택).

## 테스트

- Chrome DevTools Device Mode로 1차 검증.
- **실기기 검증은 인간(사용자) 담당** — 센서는 에뮬레이터에서 부정확.
- iOS Safari · Android Chrome 양쪽 최소 1회.

## 금지

- 뷰포트 `user-scalable=no` 단독 사용 (접근성 위반). `maximum-scale=1`로 절충.
- `hover:` CSS에만 의존하는 인터랙션 (모바일에 hover 없음).
- 300ms 클릭 지연 유발하는 non-touch 이벤트.
