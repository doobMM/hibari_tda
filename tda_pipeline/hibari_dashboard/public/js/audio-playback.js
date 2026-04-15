/* ============================================================================
 * audio-playback.js — Web Audio 기반 피아노-스타일 플레이어
 *
 * 공개:
 *   window.PianoPlayer — class
 *     .play(notes, opts) — notes: [[startSec, pitch, endSec, vel=optional], ...]
 *     .stop()
 *     .isPlaying
 *
 * 설계:
 *   - Triangle 오실레이터 2개 (기본 + 1 octave) 합성으로 피아노 비슷한 harmonic
 *   - ADSR envelope: attack 0.008s, decay 0.12s, sustain 0.35×vel, release 0.25s
 *   - 예약 시간에 정확히 예약 (scheduledAhead 방식 아님, 전체 일괄 schedule)
 *   - 진행률 업데이트는 RAF 로 현재 ctx 시간과 startTime 차이로 계산
 *   - AudioContext 는 첫 재생 시 lazy 생성. 사용자 제스처 필요시 ctx.resume()
 * ========================================================================= */

(function (global) {
  'use strict';

  class PianoPlayer {
    constructor() {
      this.ctx = null;
      this.master = null;
      this._nodes = [];        // [{osc, gain}]
      this._stopTimers = [];
      this._rafId = null;
      this._onEndUser = null;
      this._t0 = 0;
      this._dur = 0;
      this._stopped = true;
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
        this.ctx.resume().catch(() => {});
      }
    }

    stop() {
      this._stopped = true;
      this.isPlaying = false;
      const now = this.ctx ? this.ctx.currentTime : 0;
      for (const { osc, gain } of this._nodes) {
        try { gain.gain.cancelScheduledValues(now); } catch (e) {}
        try { gain.gain.setValueAtTime(gain.gain.value, now); } catch (e) {}
        try { gain.gain.linearRampToValueAtTime(0.0, now + 0.05); } catch (e) {}
        try { osc.stop(now + 0.08); } catch (e) {}
      }
      this._nodes = [];
      for (const id of this._stopTimers) clearTimeout(id);
      this._stopTimers = [];
      if (this._rafId) cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }

    /**
     * 재생.
     * @param {Array} notes — [[startSec, pitch, endSec, vel?], ...]  (vel ∈ [1, 127])
     * @param {object} [opts]
     *    opts.onProgress(t, totalSec)
     *    opts.onEnd()
     *    opts.gain  — master gain (기본 0.8)
     *    opts.velocityScale  — default 0.18 (softer for many concurrent notes)
     */
    play(notes, opts = {}) {
      this._ensureCtx();
      this.stop();  // 기존 스케줄 리셋
      this._stopped = false;
      this.isPlaying = true;
      if (opts.gain != null) this.master.gain.value = opts.gain;

      const velScale = opts.velocityScale || 0.18;
      const t0 = this.ctx.currentTime + 0.08;
      this._t0 = t0;

      let maxEnd = 0;
      for (const n of notes) {
        const s = n[0], p = n[1], e = n[2];
        const vel = n[3] != null ? n[3] : 80;
        if (!(e > s) || p < 21 || p > 108) continue;
        if (e > maxEnd) maxEnd = e;

        const freq = 440 * Math.pow(2, (p - 69) / 12);
        // 두 오실레이터 가법 합성: 기본(1x) + 약한 2nd harmonic
        const osc1 = this.ctx.createOscillator();
        osc1.type = 'triangle';
        osc1.frequency.value = freq;
        const osc2 = this.ctx.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.value = freq * 2;
        const g2 = this.ctx.createGain();
        g2.gain.value = 0.22;

        const gain = this.ctx.createGain();
        const atk = 0.008;
        const dec = 0.12;
        const peak = Math.min(1, (vel / 127) * velScale * 3.5);
        const sustain = peak * 0.35;
        const rel = 0.25;

        const onT = t0 + s;
        const offT = t0 + e;
        gain.gain.setValueAtTime(0.0, onT);
        gain.gain.linearRampToValueAtTime(peak, onT + atk);
        gain.gain.exponentialRampToValueAtTime(
          Math.max(0.0005, sustain), onT + atk + dec
        );
        gain.gain.setValueAtTime(Math.max(0.0005, sustain), Math.max(onT + atk + dec, offT));
        gain.gain.exponentialRampToValueAtTime(0.0005, offT + rel);
        gain.gain.linearRampToValueAtTime(0.0, offT + rel + 0.02);

        osc2.connect(g2).connect(gain);
        osc1.connect(gain).connect(this.master);

        osc1.start(onT);
        osc2.start(onT);
        osc1.stop(offT + rel + 0.05);
        osc2.stop(offT + rel + 0.05);

        this._nodes.push({ osc: osc1, gain });
        this._nodes.push({ osc: osc2, gain: g2 });
      }

      this._dur = maxEnd;
      this._onEndUser = opts.onEnd;

      const tick = () => {
        if (this._stopped) return;
        const t = this.ctx.currentTime - t0;
        if (opts.onProgress) {
          opts.onProgress(Math.max(0, t), this._dur);
        }
        if (t >= this._dur + 0.3) {
          this.isPlaying = false;
          if (this._onEndUser) try { this._onEndUser(); } catch (e) { console.error(e); }
          this._rafId = null;
          return;
        }
        this._rafId = requestAnimationFrame(tick);
      };
      this._rafId = requestAnimationFrame(tick);
    }
  }

  global.PianoPlayer = PianoPlayer;
})(window);
