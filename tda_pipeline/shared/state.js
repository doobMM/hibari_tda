/* ============================================================================
 * state.js — 공유 상태 publish/subscribe 모듈
 *
 * hibari_dashboard (Producer) 와 tonnetz_demo (Consumer) 간에
 * sessionStorage 를 통해 생성된 note sequence 를 전달한다.
 *
 * 공개:
 *   window.TDAState = {
 *     publishSequence(payload)  — producer 측에서 호출
 *     consumeSequence()         — consumer 측 1회성 수령 (읽고 clear)
 *     peekSequence()            — UI 배너 등에서 clear 없이 조회
 *   }
 *
 * payload 계약:
 *   {
 *     notes: [[startEighth, pitch, endEighth], ...],
 *     bpm: number,
 *     ticksPerEighth: number,
 *     source: string
 *   }
 *
 * 저장 포맷 (sessionStorage):
 *   { ...payload, version: '1.0', ts: <epoch ms> }
 *
 * 이벤트:
 *   publishSequence 성공 시 window.dispatchEvent('tda:sequence', {detail: stored})
 *
 * 유효성:
 *   - version 불일치 → clear + null
 *   - ts 로부터 10분 초과 → clear + null (stale)
 *   - notes 비어있음 → clear + null
 * ========================================================================= */

(function (global) {
  'use strict';

  const KEY = 'tda:pendingSequence';
  const VERSION = '1.0';
  const STALE_MS = 10 * 60 * 1000;

  function _readStored() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function _clear() {
    try {
      sessionStorage.removeItem(KEY);
    } catch (e) { /* noop */ }
  }

  function _validate(stored) {
    if (!stored || typeof stored !== 'object') return null;
    if (stored.version !== VERSION) return { invalid: true, reason: 'version' };
    if (typeof stored.ts !== 'number' || Date.now() - stored.ts > STALE_MS) {
      return { invalid: true, reason: 'stale' };
    }
    if (!Array.isArray(stored.notes) || stored.notes.length === 0) {
      return { invalid: true, reason: 'empty' };
    }
    return { invalid: false };
  }

  function publishSequence(payload) {
    if (!payload || !Array.isArray(payload.notes) || payload.notes.length === 0) {
      console.warn('[TDAState] publishSequence: notes is empty, skipping');
      return;
    }
    const stored = {
      notes: payload.notes,
      bpm: payload.bpm,
      ticksPerEighth: payload.ticksPerEighth,
      source: payload.source,
      version: VERSION,
      ts: Date.now()
    };
    try {
      sessionStorage.setItem(KEY, JSON.stringify(stored));
    } catch (e) {
      console.warn('[TDAState] publishSequence: sessionStorage write failed', e);
      return;
    }
    try {
      window.dispatchEvent(new CustomEvent('tda:sequence', { detail: stored }));
    } catch (e) { /* noop */ }
  }

  function consumeSequence() {
    const stored = _readStored();
    const v = _validate(stored);
    if (!v || v.invalid) {
      if (stored) _clear();
      return null;
    }
    _clear();
    return stored;
  }

  function peekSequence() {
    const stored = _readStored();
    const v = _validate(stored);
    if (!v || v.invalid) {
      if (stored) _clear();
      return null;
    }
    return stored;
  }

  global.TDAState = { publishSequence, consumeSequence, peekSequence };
})(window);
