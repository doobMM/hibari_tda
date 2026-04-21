/* ============================================================================
 * midi-io.js — 브라우저용 최소 MIDI 리더 + 라이터
 *
 * 공개:
 *   window.MidiIO = {
 *     notesToMidiBytes(notes, opts)  — Uint8Array MIDI bytes
 *     readMidiNotes(uint8)           — { bpm, notes: [[startSec, pitch, endSec, vel], ...] }
 *     downloadBytes(uint8, filename) — 브라우저 다운로드 트리거
 *   }
 *
 * 지원 범위:
 *   - Format 0 / 1 읽기
 *   - 한 트랙 쓰기 (tempo + note events)
 *   - velocity 고정 80 쓰기, 읽기는 실제 velocity 반영
 *   - Running status 지원
 *   - SMPTE division 은 480 ticks/quarter 로 강제 폴백
 * ========================================================================= */

(function (global) {
  'use strict';

  // ── 가변 길이 quantity 직렬화 ────────────────────────────────────────
  function writeVarLen(n) {
    if (n < 0) n = 0;
    const stack = [n & 0x7F];
    n >>= 7;
    while (n > 0) {
      stack.push((n & 0x7F) | 0x80);
      n >>= 7;
    }
    return stack.reverse();
  }

  // ── Writer ──────────────────────────────────────────────────────────
  /**
   * notes: [[startEighth, pitch, endEighth], ...]
   * opts.bpm (기본 60), opts.ticksPerEighth (기본 240)
   * → MIDI bytes (Uint8Array)
   */
  function notesToMidiBytes(notes, opts = {}) {
    const bpm = opts.bpm || 60;
    const ticksPerEighth = opts.ticksPerEighth || 240;
    const ticksPerQuarter = ticksPerEighth * 2;
    const velocity = opts.velocity || 80;

    // 이벤트 리스트 구성 (on/off)
    const events = [];
    for (const n of notes) {
      const start = n[0] | 0;
      const pitch = n[1] | 0;
      const end = n[2] | 0;
      if (end <= start) continue;
      if (pitch < 0 || pitch > 127) continue;
      events.push({ t: start * ticksPerEighth, order: 1, type: 'on', pitch, vel: velocity });
      events.push({ t: end * ticksPerEighth, order: 0, type: 'off', pitch });
    }
    // 같은 시점에서 off 가 먼저 (order=0)
    events.sort((a, b) => a.t - b.t || a.order - b.order);

    // 트랙 데이터 구성
    const track = [];
    // 1) tempo meta (delta 0)
    const microsPerQuarter = Math.round(60000000 / bpm);
    track.push(0x00, 0xFF, 0x51, 0x03,
      (microsPerQuarter >> 16) & 0xFF,
      (microsPerQuarter >> 8) & 0xFF,
      microsPerQuarter & 0xFF);

    // 2) 이벤트
    let lastT = 0;
    for (const ev of events) {
      const dt = Math.max(0, ev.t - lastT);
      lastT = ev.t;
      const vl = writeVarLen(dt);
      for (const b of vl) track.push(b);
      if (ev.type === 'on') {
        track.push(0x90, ev.pitch & 0x7F, ev.vel & 0x7F);
      } else {
        track.push(0x80, ev.pitch & 0x7F, 0x00);
      }
    }

    // 3) End of track
    track.push(0x00, 0xFF, 0x2F, 0x00);

    const trkLen = track.length;
    const out = new Uint8Array(14 + 8 + trkLen);
    let p = 0;
    // MThd
    out[p++] = 0x4D; out[p++] = 0x54; out[p++] = 0x68; out[p++] = 0x64;
    out[p++] = 0x00; out[p++] = 0x00; out[p++] = 0x00; out[p++] = 0x06;
    out[p++] = 0x00; out[p++] = 0x00;   // format 0
    out[p++] = 0x00; out[p++] = 0x01;   // 1 track
    out[p++] = (ticksPerQuarter >> 8) & 0xFF;
    out[p++] = ticksPerQuarter & 0xFF;
    // MTrk
    out[p++] = 0x4D; out[p++] = 0x54; out[p++] = 0x72; out[p++] = 0x6B;
    out[p++] = (trkLen >>> 24) & 0xFF;
    out[p++] = (trkLen >>> 16) & 0xFF;
    out[p++] = (trkLen >>> 8) & 0xFF;
    out[p++] = trkLen & 0xFF;
    for (let i = 0; i < trkLen; i++) out[p++] = track[i];
    return out;
  }

  // ── Reader ──────────────────────────────────────────────────────────
  class _Reader {
    constructor(bytes) {
      this.b = bytes;
      this.p = 0;
    }
    byte() { return this.b[this.p++]; }
    bytes(n) { const s = this.p; this.p += n; return this.b.subarray(s, s + n); }
    uint16() { return ((this.byte() << 8) | this.byte()) >>> 0; }
    uint32() {
      const a = this.byte(), b = this.byte(), c = this.byte(), d = this.byte();
      return (a * 0x1000000 + (b << 16) + (c << 8) + d) >>> 0;
    }
    varlen() {
      let v = 0;
      for (let i = 0; i < 4; i++) {
        const b = this.byte();
        v = (v << 7) | (b & 0x7F);
        if ((b & 0x80) === 0) return v;
      }
      return v;
    }
  }

  /**
   * MIDI 바이트에서 note 를 추출.
   * 반환: { bpm, ticksPerQuarter, notes: [[startSec, pitch, endSec, vel], ...] }
   */
  function readMidiNotes(bytes) {
    const r = new _Reader(bytes);
    const mag = r.bytes(4);
    if (mag[0] !== 0x4D || mag[1] !== 0x54 || mag[2] !== 0x68 || mag[3] !== 0x64) {
      throw new Error('Not a MIDI file (missing MThd)');
    }
    const hlen = r.uint32();
    /* const format = */ r.uint16();
    const numTracks = r.uint16();
    const division = r.uint16();
    r.p += Math.max(0, hlen - 6);

    // division 처리
    let ticksPerQuarter = division;
    if ((division & 0x8000) !== 0) {
      // SMPTE — 안전하게 폴백
      ticksPerQuarter = 480;
    }

    const tempoChanges = [];  // {tick, us}
    const allEvents = [];     // {tick, type, pitch, vel}

    for (let tr = 0; tr < numTracks; tr++) {
      const m = r.bytes(4);
      if (m[0] !== 0x4D || m[1] !== 0x54 || m[2] !== 0x72 || m[3] !== 0x6B) {
        throw new Error(`Track ${tr} 없음 (MTrk 누락)`);
      }
      const tlen = r.uint32();
      const end = r.p + tlen;
      let absTick = 0;
      let runningStatus = 0;

      while (r.p < end) {
        const dt = r.varlen();
        absTick += dt;
        let status = r.byte();
        if ((status & 0x80) === 0) {
          // running status
          r.p--;
          status = runningStatus;
        } else {
          if (status < 0xF0) runningStatus = status;
        }
        if (status === 0xFF) {
          const metaType = r.byte();
          const len = r.varlen();
          const data = r.bytes(len);
          if (metaType === 0x51 && len === 3) {
            const us = (data[0] << 16) | (data[1] << 8) | data[2];
            tempoChanges.push({ tick: absTick, us });
          }
        } else if (status === 0xF0 || status === 0xF7) {
          const len = r.varlen();
          r.bytes(len);
        } else {
          const hi = status & 0xF0;
          if (hi === 0x90) {
            const pitch = r.byte();
            const vel = r.byte();
            if (vel > 0) allEvents.push({ tick: absTick, type: 'on', pitch, vel });
            else allEvents.push({ tick: absTick, type: 'off', pitch, vel: 0 });
          } else if (hi === 0x80) {
            const pitch = r.byte();
            const vel = r.byte();
            allEvents.push({ tick: absTick, type: 'off', pitch, vel });
          } else if (hi === 0xA0 || hi === 0xB0 || hi === 0xE0) {
            r.byte(); r.byte();
          } else if (hi === 0xC0 || hi === 0xD0) {
            r.byte();
          }
        }
      }
      r.p = end;
    }

    // tick → seconds 변환을 위한 tempo 적용
    // 기본 tempo 500000 us/quarter (120 BPM)
    if (tempoChanges.length === 0) tempoChanges.push({ tick: 0, us: 500000 });
    tempoChanges.sort((a, b) => a.tick - b.tick);

    function tickToSec(tick) {
      let acc = 0;
      let prevTick = 0;
      let prevUs = tempoChanges[0].us;
      for (let i = 0; i < tempoChanges.length; i++) {
        const cur = tempoChanges[i];
        if (cur.tick >= tick) break;
        acc += ((cur.tick - prevTick) * prevUs) / ticksPerQuarter / 1e6;
        prevTick = cur.tick;
        prevUs = cur.us;
      }
      acc += ((tick - prevTick) * prevUs) / ticksPerQuarter / 1e6;
      return acc;
    }

    // 이벤트 정렬 후 note pair 생성
    allEvents.sort((a, b) => a.tick - b.tick || (a.type === 'off' ? -1 : 1));
    const active = new Map();  // pitch → { tick, vel }
    const notes = [];
    for (const ev of allEvents) {
      if (ev.type === 'on') {
        if (active.has(ev.pitch)) {
          // same pitch: close previous
          const prev = active.get(ev.pitch);
          notes.push([tickToSec(prev.tick), ev.pitch, tickToSec(ev.tick), prev.vel]);
        }
        active.set(ev.pitch, { tick: ev.tick, vel: ev.vel });
      } else {
        if (active.has(ev.pitch)) {
          const prev = active.get(ev.pitch);
          notes.push([tickToSec(prev.tick), ev.pitch, tickToSec(ev.tick), prev.vel]);
          active.delete(ev.pitch);
        }
      }
    }
    // 남은 active (off 없이 끝난) 는 1 sec 유지로 종결
    for (const [pitch, prev] of active) {
      notes.push([tickToSec(prev.tick), pitch, tickToSec(prev.tick) + 1.0, prev.vel]);
    }
    notes.sort((a, b) => a[0] - b[0] || a[1] - b[1]);

    const bpm = 60e6 / tempoChanges[0].us;
    return { bpm, ticksPerQuarter, notes };
  }

  // ── 다운로드 헬퍼 ───────────────────────────────────────────────────
  function downloadBytes(uint8, filename) {
    const blob = new Blob([uint8], { type: 'audio/midi' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  }

  global.MidiIO = { notesToMidiBytes, readMidiNotes, downloadBytes };
})(window);
