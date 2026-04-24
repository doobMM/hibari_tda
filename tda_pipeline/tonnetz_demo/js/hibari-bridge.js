/**
 * hibari-bridge.js — hibari_dashboard → tonnetz_demo consumer
 *
 * Spec: docs/tonnetz_hibari_integration_spec.md
 *
 * Depends on:
 *   - window.TDAState  (shared/state.js)
 *   - window.MidiIO    (shared/midi-io.js)
 *   - window.midiPlayer.load  (tonnetz_demo/js/midifile.js)
 *   - Bootstrap 3 tabs (shown("playback"))
 *
 * Behavior:
 *   1) DOMContentLoaded 이후 ?from=hibari&intent=autoplay 이면 pending 을 consume 후 자동재생
 *   2) autoplay intent 가 아니고 pending 이 존재하면 배너 표시 (시나리오 4)
 *   3) 동일 페이지 'tda:sequence' 이벤트 수신 시 즉시 consume + 재생 (시나리오 7)
 *   4) "MIDI 저장" 버튼은 마지막 수령 payload 를 MidiIO.downloadBytes 로 다운로드
 */

(function () {
  'use strict';

  var _lastPayload = null;

  function $(id) { return document.getElementById(id); }

  function payloadToArrayBuffer(payload) {
    if (!window.MidiIO || typeof window.MidiIO.notesToMidiBytes !== 'function') {
      throw new Error('MidiIO not loaded');
    }
    var bytes = window.MidiIO.notesToMidiBytes(payload.notes, {
      bpm: payload.bpm,
      ticksPerEighth: payload.ticksPerEighth
    });
    // Uint8Array.buffer can include offset/length — slice 로 순수 ArrayBuffer 확보
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }

  function ensurePlaybackTabVisible() {
    try {
      var link = document.querySelector('a[href="#playback"]');
      if (link && window.$ && typeof window.$(link).tab === 'function') {
        window.$(link).tab('show');
      }
    } catch (e) { /* noop */ }
  }

  function playPayload(payload) {
    if (!payload || !Array.isArray(payload.notes) || payload.notes.length === 0) return false;
    if (!window.midiPlayer || typeof window.midiPlayer.load !== 'function') {
      console.warn('[hibari-bridge] midiPlayer.load unavailable — is midifile.js loaded?');
      return false;
    }
    try {
      var buf = payloadToArrayBuffer(payload);
      _lastPayload = payload;
      updateSaveButtonVisibility();
      ensurePlaybackTabVisible();
      window.midiPlayer.load(buf);
      return true;
    } catch (e) {
      console.error('[hibari-bridge] playPayload failed', e);
      return false;
    }
  }

  function updateSaveButtonVisibility() {
    var btn = $('hibariSaveMidiBtn');
    if (!btn) return;
    btn.style.display = _lastPayload ? '' : 'none';
  }

  function handleSaveClick() {
    if (!_lastPayload) return;
    try {
      var bytes = window.MidiIO.notesToMidiBytes(_lastPayload.notes, {
        bpm: _lastPayload.bpm,
        ticksPerEighth: _lastPayload.ticksPerEighth
      });
      var stamp = new Date(_lastPayload.ts || Date.now()).toISOString().replace(/[:.]/g, '-').slice(0, 19);
      var filename = 'hibari_generated_' + stamp + '.mid';
      window.MidiIO.downloadBytes(bytes, filename);
    } catch (e) {
      console.error('[hibari-bridge] save failed', e);
    }
  }

  function hideBanner() {
    var banner = $('hibariPendingBanner');
    if (banner) banner.hidden = true;
  }

  function showBanner() {
    var banner = $('hibariPendingBanner');
    if (banner) banner.hidden = false;
  }

  function handleBannerPlay() {
    var payload = window.TDAState.consumeSequence();
    hideBanner();
    if (payload) playPayload(payload);
  }

  function handleBannerDismiss() {
    // consume without using → 저장값 제거
    window.TDAState.consumeSequence();
    hideBanner();
  }

  function parseIntent() {
    var q = new URLSearchParams(window.location.search);
    return {
      from: q.get('from'),
      intent: q.get('intent')
    };
  }

  function onPublishEvent(e) {
    // 동일 페이지 이벤트 — 재생 중이면 중단 후 새 시퀀스 로드
    var payload = window.TDAState.consumeSequence();
    if (!payload) return;
    hideBanner();
    playPayload(payload);
  }

  function wireButtons() {
    var playBtn = $('hibariBannerPlayBtn');
    var dismissBtn = $('hibariBannerDismissBtn');
    var saveBtn = $('hibariSaveMidiBtn');
    if (playBtn) playBtn.addEventListener('click', handleBannerPlay);
    if (dismissBtn) dismissBtn.addEventListener('click', handleBannerDismiss);
    if (saveBtn) saveBtn.addEventListener('click', handleSaveClick);
  }

  function init() {
    if (!window.TDAState) {
      console.warn('[hibari-bridge] TDAState not loaded — skipping');
      return;
    }

    wireButtons();
    updateSaveButtonVisibility();

    window.addEventListener('tda:sequence', onPublishEvent);

    var intent = parseIntent();
    var pending = window.TDAState.peekSequence();

    if (pending && intent.from === 'hibari' && intent.intent === 'autoplay') {
      var payload = window.TDAState.consumeSequence();
      if (payload) playPayload(payload);
    } else if (pending) {
      // 직접 URL 진입 + pending 존재 → 자동재생하지 않고 배너
      showBanner();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
