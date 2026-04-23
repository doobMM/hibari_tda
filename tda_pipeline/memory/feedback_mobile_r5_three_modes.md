# R5 3개 모드 사용자 피드백 (2026-04-21)

사용자 실기기 테스트 피드백. 작업 착수 전 기록만. 다음 세션 E/B 에서 우선순위 배정.

## 공통 — 착수 전 요청

1. **화면 회전 잠금 요청 플로우** — Tilt / Shake 모두 해당. 권한 모달(`perm` overlay)에서 "시작" 버튼을 누르기 전에 **"화면 회전을 잠가주세요"** 안내 문구 추가 권장.
   - iOS Safari 는 웹에서 direct lock 불가 (제어판에서 사용자가 수동으로).
   - `screen.orientation.lock()` 은 전체화면 진입 후에만 동작 — PWA 설치 or `requestFullscreen()` 필요.
   - 실용안: 모달에 **"Portrait 잠금 권장"** 텍스트 + 시각적 아이콘만.

## Tilt (`tilt.html`)

- **버그**: 녹음 후 버튼이 여전히 "구현 예정 …" 으로 표시됨 (보고 시점).
  - 원인 분석: 본 세션에서 Phase 2+3 구현 커밋. 해당 문자열은 현재 코드에서 제거됨 (grep 0). 사용자 환경의 **브라우저 캐시** 이슈로 추정.
  - 검증 방법: Ctrl+Shift+R 후 재시도. 새 버튼은 `🎵 생성하기 (N steps)` 로 표시되며 클릭 시 실제 30초 재생됨.
  - 캐시 대책 (추후 작업): `<script type="module" src="js/tilt-sphere.js?v=20260421">` 같이 쿼리 스트링 버전 부여.

- **개선 요청**: **기울이기 민감도 상향**.
  - 현 파라미터 (`js/tilt-sphere.js`):
    - `onOrient()`: `g = clamp(gamma, -45..45)`, `b = clamp(beta - 20, -45..45)`, `tiltX = g/45`, `tiltY = b/45` → [-1, 1]
    - `step()`: `pvx += (tiltX + kx) * gain`  with `gain = 0.6`
    - `friction = 0.92`
  - 튜닝 후보:
    - (a) clamp 범위 축소 (-30..30) → 작은 기울임도 ±1.0 포화
    - (b) `gain` 상향 (0.6 → 1.2)
    - (c) tilt 제곱 대신 선형 유지 + 낮은 dead-zone (예 |tilt| < 0.05 → 0)
  - 권장: (a)+(b) 조합 시작, 실기기에서 (b) 만 먼저 튜닝.

## Shake (`shake.html`)

- **버그**: 음악이 재생되다가 **중간에 끊김**.
  - 원인 후보 (코드 미확인, 추정):
    1. Algo1 생성 길이와 `setTimeout` 스케줄 불일치 — notes 마지막이 T 를 넘지만 `totalMs` 가 부족해 조기 종료.
    2. AudioContext auto-suspend (iOS 모바일에서 30초 idle 시 suspend 되는 경우 있음).
    3. shake 재감지가 기존 재생 `stopAll()` 을 호출.
    4. oscillator `stop(now + dur)` 이후 새 노트 스케줄되지 않음 (one-shot 방식인 경우).
  - 작업 시: `js/shake-detector.js` + AudioEngine 상호작용 로그 확인 필요.

## Camera (`camera.html`)

- **버그**: 권한 승인 UI 는 나오지만 **승인 후 작동 안 함**.
  - 원인 후보 (코드 미확인):
    1. `getUserMedia({ video: true })` 후 `<video>` 엘리먼트 attach 누락.
    2. canvas hue 추출 loop 가 시작되지 않음 (requestAnimationFrame 미호출).
    3. hue → scale 매핑 결과가 audio 파이프라인에 연결되지 않음.
    4. iOS Safari 에서 `playsinline` 속성 없으면 전체화면 비디오로 전환 후 blank.
  - 작업 시: `js/camera-color.js` 검토 + Safari/Chrome 콘솔 에러 확인.

## 다음 액션 (세션 E 배정 대기)

| 항목 | 세션 | 우선순위 |
|---|---|---|
| Tilt 민감도 튜닝 | B | 높음 (작은 변경) |
| 회전 잠금 안내 문구 | B | 높음 (문자열만) |
| Tilt 캐시 bust (?v=…) | B | 중 |
| Shake 중단 디버깅 | B/A | 중 (재현 필요) |
| Camera 미작동 디버깅 | B | 중-높음 (완전 불동작) |

사용자 지시: **이 세션에서 수정 착수 금지** — 기록만.
