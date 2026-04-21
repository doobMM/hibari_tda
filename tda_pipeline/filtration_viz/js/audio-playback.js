/* ============================================================================
 * audio-playback.js — Web Audio 기반 피아노-스타일 플레이어 (look-ahead scheduler)
 *
 * 이전 버전은 모든 노트(3953개 × 2 오실레이터 = ~8000 노드)를 일괄 스케줄 →
 * 일부 브라우저/환경에서 audio thread 포화로 소리가 나지 않는 문제 확인됨.
 *
 * 개선: 표준 look-ahead 패턴
 *   - 노트를 startSec 오름차순 정렬
 *   - 100ms 간격으로 앞으로 1.5s 안에 시작되는 노트만 스케줄
 *   - 끝난 노드는 자동 해제 (osc.onended 에서 정리)
 *
 * 공개:
 *   window.PianoPlayer — class
 *     .play(notes, opts) — notes: [[startSec, pitch, endSec, vel?], ...]
 *     .stop()
 *     .isPlaying
 * ========================================================================= */

(function (global) {
  'use strict';

  const LOOKAHEAD_SEC = 1.5;
  const INTERVAL_MS = 100;

  class PianoPlayer {
    constructor() {
      this.ctx = null;
      this.master = null;
      this._scheduled = [];      // 아직 살아있는 { osc1, osc2, gain, g2 }
      this._intervalId = null;
      this._rafId = null;
      this._onEndUser = null;
      this._t0 = 0;
      this._dur = 0;
      this._stopped = true;
      this._notes = [];          // 정렬된 전체
      this._cursor = 0;          // 다음에 스케줄할 인덱스
      this._velScale = 0.18;
      this.isPlaying = false;
    }

    _ensureCtx() {
      if (!this.ctx) {
        const AC = global.AudioContext || global.webkitAudioContext;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = 0.8;
        this.master.connect(this.ctx.destination);
      }
      if (this.ctx.state === 'suspended') {
        this.ctx.resume().catch((e) => console.warn('[audio] resume failed', e));
      }
    }

    stop() {
      this._stopped = true;
      this.isPlaying = false;
      if (this._intervalId) clearInterval(this._intervalId);
      this._intervalId = null;
      if (this._rafId) cancelAnimationFrame(this._rafId);
      this._rafId = null;

      const now = this.ctx ? this.ctx.currentTime : 0;
      for (const node of this._scheduled) {
        try { node.gain.gain.cancelScheduledValues(now); } catch (e) {}
        try { node.gain.gain.setValueAtTime(node.gain.gain.value, now); } catch (e) {}
        try { node.gain.gain.linearRampToValueAtTime(0.0, now + 0.05); } catch (e) {}
        try { node.osc1.stop(now + 0.08); } catch (e) {}
        try { node.osc2.stop(now + 0.08); } catch (e) {}
      }
      this._scheduled = [];
    }

    _scheduleNote(note, t0) {
      const s = note[0], p = note[1], e = note[2];
      const vel = note[3] != null ? note[3] : 80;
      if (!(e > s) || p < 21 || p > 108) return null;

      const freq = 440 * Math.pow(2, (p - 69) / 12);
      const ctx = this.ctx;

      const osc1 = ctx.createOscillator();
      osc1.type = 'triangle';
      osc1.frequency.value = freq;

      const osc2 = ctx.createOscillator();
      osc2.type = 'sine';
      osc2.frequency.value = freq * 2;

      const g2 = ctx.createGain();
      g2.gain.value = 0.22;

      const gain = ctx.createGain();
      const atk = 0.008, dec = 0.12, rel = 0.25;
      const peak = Math.min(1, (vel / 127) * this._velScale * 3.5);
      const sustain = peak * 0.35;

      const onT = t0 + s;
      const offT = t0 + e;
      gain.gain.setValueAtTime(0.0, onT);
      gain.gain.linearRampToValueAtTime(peak, onT + atk);
      gain.gain.exponentialRampToValueAtTime(
        Math.max(0.0005, sustain), onT + atk + dec
      );
      gain.gain.setValueAtTime(
        Math.max(0.0005, sustain),
        Math.max(onT + atk + dec, offT)
      );
      gain.gain.exponentialRampToValueAtTime(0.0005, offT + rel);
      gain.gain.linearRampToValueAtTime(0.0, offT + rel + 0.02);

      osc2.connect(g2).connect(gain);
      osc1.connect(gain).connect(this.master);

      osc1.start(onT);
      osc2.start(onT);
      const stopT = offT + rel + 0.05;
      osc1.stop(stopT);
      osc2.stop(stopT);

      const node = { osc1, osc2, gain, g2, stopT };
      osc1.onended = () => {
        const i = this._scheduled.indexOf(node);
        if (i >= 0) this._scheduled.splice(i, 1);
        try { osc1.disconnect(); } catch (_) {}
        try { osc2.disconnect(); } catch (_) {}
        try { gain.disconnect(); } catch (_) {}
        try { g2.disconnect(); } catch (_) {}
      };
      return node;
    }

    /**
     * 재생.
     * @param {Array} notes — [[startSec, pitch, endSec, vel?], ...]
     * @param {object} [opts]
     *    opts.onEnd()
     *    opts.gain           — master gain (기본 0.8)
     *    opts.velocityScale  — default 0.18
     */
    play(notes, opts = {}) {
      this._ensureCtx();
      this.stop();
      this._stopped = false;
      this.isPlaying = true;
      if (opts.gain != null) this.master.gain.value = opts.gain;
      this._velScale = opts.velocityScale || 0.18;
      this._onEndUser = opts.onEnd;

      // 정렬된 노트 + 총 재생시간
      this._notes = notes
        .filter(n => (n[2] > n[0]) && n[1] >= 21 && n[1] <= 108)
        .slice()
        .sort((a, b) => a[0] - b[0]);
      this._cursor = 0;
      this._dur = 0;
      for (const n of this._notes) {
        if (n[2] > this._dur) this._dur = n[2];
      }

      const t0 = this.ctx.currentTime + 0.08;
      this._t0 = t0;

      let errorLogged = false;
      const scheduleAhead = () => {
        if (this._stopped) return;
        const horizon = this.ctx.currentTime - t0 + LOOKAHEAD_SEC;
        while (this._cursor < this._notes.length) {
          const n = this._notes[this._cursor];
          if (n[0] > horizon) break;
          try {
            const node = this._scheduleNote(n, t0);
            if (node) this._scheduled.push(node);
          } catch (e) {
            if (!errorLogged) {
              console.error('[audio] schedule error', e);
              errorLogged = true;
            }
          }
          this._cursor++;
        }
        // 재생 종료 판정
        const t = this.ctx.currentTime - t0;
        if (this._cursor >= this._notes.length && t >= this._dur + 0.3) {
          this._stopped = true;
          this.isPlaying = false;
          if (this._intervalId) clearInterval(this._intervalId);
          this._intervalId = null;
          if (this._onEndUser) {
            try { this._onEndUser(); } catch (e) { console.error(e); }
          }
        }
      };

      scheduleAhead();
      this._intervalId = setInterval(scheduleAhead, INTERVAL_MS);

      console.log('[audio] play start — notes:', this._notes.length,
                  'dur:', this._dur.toFixed(2) + 's',
                  'ctx:', this.ctx.state);
    }
  }

  global.PianoPlayer = PianoPlayer;
})(window);
