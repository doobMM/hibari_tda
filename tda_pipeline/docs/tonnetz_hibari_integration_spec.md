# tonnetz_hibari_integration_spec.md

## 1) User flow (통합 후)

아래 플로우는 "다운로드 후 업로드"를 제거하고, 생성 직후 Tonnetz 확인까지 도달 실패를 줄이는 1.0 기준 동작이다. 기본 UX는 모바일 우선(탭 전환 최소, 버튼 1회)으로 설계한다.

1. 사용자가 `hibari_dashboard`에서 overlap matrix를 편집하고 `Generate`를 실행해 시퀀스를 만든다.  
   이 시점의 내부 표현(8분음표 단위 notes, bpm, ticksPerEighth)을 표준 payload로 구성한다.
2. 사용자가 `Tonnetz 에서 재생` 버튼을 누르면, `TDAState.publishSequence(payload)`를 호출해 `sessionStorage`에 저장하고 같은 페이지에 `tda:sequence` 이벤트를 발생시킨 뒤, `tonnetz_demo`로 이동한다.  
   권장 이동 방식은 `?from=hibari&intent=autoplay` 같은 의도 플래그 포함이다.
3. `tonnetz_demo`는 진입 시 payload 유효성(`notes` 존재, `version`, `ts` 신선도)을 검사한다.  
   유효하고 자동재생 의도가 명확하면 시퀀스를 자동 로드하고 즉시 재생을 시작한다(모바일 기준 첫 진입 체감 지연 최소화).
4. 사용자가 원할 때만 `MIDI 저장` 버튼으로 파일을 내려받는다.  
   즉, 다운로드는 선택 기능이며 기본 감상 플로우의 필수 단계가 아니다.
5. 사용자가 다시 `hibari_dashboard`로 돌아와 note를 수정하거나 파라미터를 바꾸는 순간, 이전에 발행된 시퀀스는 자동 소거한다.  
   정책상 "편집 상태의 데이터"는 재생 대기열로 유지하지 않으며, 재생 가능한 새 결과는 Generate 이후에만 다시 publish한다.

---

## 2) sessionStorage 스키마

키는 고정으로 `tda:pendingSequence`를 사용한다. 값은 JSON 문자열이며, 1.0 스키마는 다음과 같다.

```json
{
  "notes": [[0, 67, 2], [2, 69, 4], [4, 71, 8]],
  "bpm": 120,
  "ticksPerEighth": 240,
  "source": "hibari_dashboard",
  "version": "1.0",
  "ts": 1761465600000
}
```

필드 정의:

- `notes`: `[[startEighth:int, pitch:int, endEighth:int], ...]` 형식 배열.
- `bpm`: number. 기본값 `120` (hibari가 명시).
- `ticksPerEighth`: number. 기본값 `240`.
- `source`: 발행 주체 식별자. 예: `'hibari_dashboard' | 'mobile_tonnetz' | ...`.
- `version`: `'1.0'` 고정(향후 역호환 분기용).
- `ts`: `Date.now()` 밀리초 타임스탬프(신선도 판정용).

검증 규칙(요약):

- `notes.length > 0` 이어야 한다.
- 각 note tuple은 길이 3, 정수형, `0 <= pitch <= 127`, `startEighth < endEighth`.
- `bpm > 0`, `ticksPerEighth > 0`.
- `version`은 지원 목록(1.0)에 포함되어야 한다.

---

## 3) shared/state.js API

1.0에서는 상태 유틸 API를 최소화해 아래 두 메서드만 제공한다.

```js
// shared/state.js
const KEY = 'tda:pendingSequence';
const SUPPORTED_VERSIONS = new Set(['1.0']);

export const TDAState = {
  publishSequence(payload) {
    // 1) payload validate
    // 2) sessionStorage.setItem(KEY, JSON.stringify(payload))
    // 3) window.dispatchEvent(new CustomEvent('tda:sequence', { detail: payload }))
  },

  consumeSequence() {
    // 1) raw read (없으면 null)
    // 2) parse 실패 시 clear 후 null
    // 3) version 불일치 시 clear 후 null
    // 4) 정상 payload 반환 전에 clear (read + clear 원자적 소비)
  }
};
```

메서드 계약:

- `TDAState.publishSequence(payload)`
  - `sessionStorage`에 overwrite 저장한다(큐가 아니라 "마지막 1건" 유지).
  - 같은 페이지 문맥에서 즉시 반응이 필요할 때를 위해 `CustomEvent('tda:sequence')`를 dispatch한다.
  - 반환값은 사용하지 않으며, 실패는 콘솔 경고 + UX 토스트로 노출한다.
- `TDAState.consumeSequence()`
  - 성공 시 payload를 반환하고 저장값을 즉시 삭제한다.
  - 데이터가 없거나 손상/버전 불일치면 삭제 후 `null` 반환.
  - 이 메서드는 "재생 대기열 단건 소비" 의미를 가지므로, 재시도 시 다시 publish되어야 한다.

주의:

- `CustomEvent`는 동일 페이지 한정이다(브라우저 탭 간 실시간 동기화 아님).
- 민감정보는 payload에 넣지 않는다. 시퀀스 데이터 외 사용자 식별값 저장 금지.

---

## 4) Edge case 처리 규칙

아래 규칙은 1.0 공통 정책이며, "조용히 실패" 대신 사용자 도달 실패를 줄이는 안내를 우선한다.

1. **빈 `notes` 배열**
   - 처리: 경고 토스트 표시(`재생 가능한 노트가 없습니다`), 저장/소비 모두 수행하지 않음.
   - 이유: 빈 데이터 자동재생은 사용자가 시스템 오작동으로 오해하기 쉽다.
2. **`ts` 기준 10분 초과 stale**
   - 처리: 자동 clear 후 안내 토스트(`이전 세션이 만료되어 삭제되었습니다`).
   - 기준: `Date.now() - ts > 10 * 60 * 1000`.
3. **`version` 필드 누락 또는 미지원 버전**
   - 처리: clear + 콘솔 로그(`unsupported payload version`) + 비차단 토스트.
   - 목적: 구버전 데이터로 재생 파이프라인이 깨지는 것 방지.
4. **`tonnetz_demo` 직접 URL 진입 + pending 존재**
   - 처리: 자동재생하지 않고 상단 배너 표시(`이전 세션 시퀀스가 있습니다. 재생할까요?`).
   - 액션: `재생` 클릭 시 consume 후 로드, `무시` 클릭 시 clear.
5. **재생 중 다시 hibari에서 publish**
   - 정책: 현재 재생을 즉시 중단하고 새 시퀀스로 전환(최신 사용자 의도 우선).
   - UX: `새 시퀀스로 전환되었습니다` 토스트 1회.
6. **payload 구조 손상(JSON parse 실패/필드 타입 오류)**
   - 처리: clear + 경고 로그 + 안전 복귀(기본 화면 유지).
7. **Storage 접근 불가(사파리 프라이빗/보안 정책 등)**
   - 처리: publish 실패 시 `URL 파라미터 fallback` 또는 `파일 저장 안내`로 degrade.
   - 원칙: 통합 실패 시에도 기존 수동 플로우로 우회 가능해야 한다.

---

## 5) 테스트 시나리오 (수동 + 자동)

아래는 1.0 릴리즈 전 최소 검증 세트(9개)다. 각 항목은 준비/액션/기대 결과를 명시한다.

### 시나리오 1 — Happy path (자동 로드 + 자동 재생)
- 준비 상태: `hibari_dashboard`에서 유효 notes 생성 완료.
- 액션 순서: `Tonnetz 에서 재생` 클릭 → `tonnetz_demo` 이동.
- 기대 결과: 시퀀스 자동 로드, 재생 시작, 다운로드 없이 격자 시각화 확인.

### 시나리오 2 — Stale 상태 자동 소거
- 준비 상태: `tda:pendingSequence.ts`를 현재 시각 대비 11분 이전으로 주입.
- 액션 순서: `tonnetz_demo` 진입.
- 기대 결과: payload 자동 삭제, 자동재생 없음, 만료 안내 토스트 표시.

### 시나리오 3 — 양쪽 탭 동시 열림 시 동작 확인
- 준비 상태: 탭 A(`hibari_dashboard`), 탭 B(`tonnetz_demo`) 동시 오픈.
- 액션 순서: 탭 A에서 publish 실행 후 탭 B 관찰.
- 기대 결과: 1.0에서는 탭 간 live sync 미지원이므로 즉시 재생되지 않음(명시된 제약과 일치).

### 시나리오 4 — 직접 URL 진입 시 배너 분기
- 준비 상태: 유효 pending payload 존재, `tonnetz_demo`를 북마크/직접 URL로 진입.
- 액션 순서: 진입 후 배너에서 `재생` 또는 `무시` 선택.
- 기대 결과: 자동재생은 발생하지 않음. 선택값에 따라 consume 재생 또는 clear.

### 시나리오 5 — version mismatch
- 준비 상태: `version: "0.9"` 또는 필드 누락 payload 저장.
- 액션 순서: consume 트리거(진입 또는 버튼).
- 기대 결과: clear 후 `null` 처리, 콘솔에 버전 경고 기록.

### 시나리오 6 — 빈 notes publish 방지
- 준비 상태: notes `[]` payload 생성.
- 액션 순서: `publishSequence` 호출.
- 기대 결과: 저장되지 않음, 사용자 경고 표시, tonnetz 이동해도 재생 없음.

### 시나리오 7 — 재생 중 새 publish 도착
- 준비 상태: tonnetz에서 시퀀스 재생 중.
- 액션 순서: 새 payload publish 이벤트 발생(동일 페이지 이벤트 시뮬레이션 포함).
- 기대 결과: 기존 재생 정지 후 새 시퀀스 로드/재생, 중복 오디오 없음.

### 시나리오 8 — hibari 재편집 시 자동 소거
- 준비 상태: 기존 생성 결과가 pending 상태.
- 액션 순서: hibari에서 note 이동/삭제 등 편집 시작(Generate 전).
- 기대 결과: pending이 즉시 clear되어, 과거 결과가 tonnetz에서 재생 대기되지 않음.

### 시나리오 9 — 선택적 MIDI 저장
- 준비 상태: tonnetz 자동재생 성공 상태.
- 액션 순서: `MIDI 저장` 버튼 미사용/사용 각각 확인.
- 기대 결과: 미사용 시에도 핵심 플로우 정상 완료, 사용 시 현재 시퀀스 기준 파일 다운로드.

자동화 권장 포인트:

- 단위 테스트: `publishSequence`, `consumeSequence`의 validate/clear/버전 분기.
- E2E 테스트: 시나리오 1, 2, 4, 8 우선(모바일 viewport 포함).

---

## 6) 미구현 / 후속 과제 (1.0 범위 밖)

1. **실시간 cross-tab 동기화**
   - 현재 `sessionStorage + CustomEvent`는 탭 간 전파가 안 된다.
   - 후속 후보: `BroadcastChannel` 또는 `localStorage` event 기반 동기화.
2. **iframe 임베드형 완전 통합**
   - hibari 내부에 tonnetz를 iframe으로 붙여 무전환 재생하는 방식은 1.0 제외.
3. **MIDI 외 오디오 포맷 직접 공유**
   - WAV/OGG 스트림 전달, 렌더 캐시 재사용은 후속.
4. **시퀀스 히스토리(다건) 관리**
   - 현재는 "마지막 1건"만 유지. 버전 비교/되돌리기 UI는 추후.
5. **서명/암호화 포함 고급 무결성**
   - 1.0은 로컬 세션 범위 비민감 payload 전제. 공개 배포 전 보안 강화 별도 설계.

1.0의 핵심 성공 기준은 "웹에서 즉시 확인 가능한 자동 도달"이다. 즉, 사용자가 생성 후 버튼 1회로 Tonnetz 재생까지 도달하고, 실패 시에도 원인을 바로 이해하고 복구할 수 있어야 한다.
