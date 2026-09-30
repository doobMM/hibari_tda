/* sketch/common.js — 세 스케치(흐름 그물 flow · 두 바퀴 wheels · 고리 합주 loops)가 같이 쓰는 바닥
 * 명세: docs/sketch_spec.md.  자료: lenia/tonnetz.json (정본 경로에서 뽑은 음·고리·가중치·두 손의 모듈).
 *
 * 판 11 의 교훈을 여기서 한 번에 막는다:
 *   · 키는 **ev.code** 로 읽는다 (ev.key 는 한글 입력 상태에서 글자 키가 전부 무시됐다)
 *   · 소리는 누른 그 호출 안에서 5 ms 뒤로 예약한다 (다음 박을 기다리지 않는다)
 *   · 밝은 바탕, 음 이름(계이름+옥타브)
 *   · 시계는 hibari 의 8분음표(60/66/2 초)
 * DOM 이 없는 곳(node 검증)에서도 derive·rng·shuffled 는 돈다.
 */
(function (root) {
  'use strict';
  var SEC = 60 / 66 / 2;
  var SOL = ['도', '도#', '레', '레#', '미', '파', '파#', '솔', '솔#', '라', '라#', '시'];
  var DEG = { 0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6 };                 // 음이름 → 계단 번호(도=0 … 시=6). hibari 는 흰 건반 7음뿐이다
  function noteName(p) { return SOL[p % 12] + (Math.floor(p / 12) - 1); }  // 60 → 도4
  function rng(seed) { var a = (seed >>> 0) || 1; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  /** tonnetz.json → 스케치가 쓰는 모양.
   *  notes[li] = {li, pitch, dur, pc, deg, name, count}           23음 (음높이 17가지 — 같은 높이에 길이가 다른 음이 있다)
   *  mod[h]    = {period, ring, steps}  h=0 오른손(32) · 1 왼손(33).  steps[t] = 그 스텝에 시작하는 음의 li 배열 (쉼이면 [])
   *              한 모듈 = 두 구절. 구절마다 12스텝 울리고 4스텝 쉰다. 베이스가 미→파→솔→라→시→도 로 한 계단씩 오르며 화음(4음) 다음에 단음(1음)이 온다.
   *              왼손은 같은 무늬에 쉼이 한 칸 더 있어 33 — 모듈마다 1/32 씩 어긋난다. 원곡은 이 모듈이 34번 100% 같게 돈다.
   *  intra[h][v][u], inter[v][u]   음 v 다음에 음 u 가 오는 정도 (한 손 안 / 두 손 사이, 최댓값 1) — 사용자의 설계 intra + rate × inter
   *  cycles[k] = li 배열(집합), order[k] = 고리를 도는 순서, alive(k, rate) = 그 rate 에 그 고리가 살아 있나 (rate 0~1.5) */
  function derive(D) {
    var notes = D.labels.map(function (l) { return { li: l.li, pitch: l.pitch, dur: l.dur, pc: l.pc, deg: DEG[l.pc], name: noteName(l.pitch), count: l.count }; });
    // 같은 높이에 길이가 다른 음이 있다: 보통은 가장 짧은 것, 구절 끝 화음은 가장 긴 것(6), 구절 끝 단음은 5 이하에서 가장 긴 것
    function labelFor(pitch, cap) { var best = -1; notes.forEach(function (n) { if (n.pitch !== pitch || (cap && n.dur > cap)) return;
      if (best < 0 || (cap ? n.dur > notes[best].dur : n.dur < notes[best].dur)) best = n.li; }); return best; }
    function mod(key) { var h = D.hands[key], P = h.period, ring = h.ring, steps = []; for (var t = 0; t < P; t++) steps.push([]);
      h.early.forEach(function (e) { var t = e[0]; if (t >= P) return;
        var endSingle = ring[t] === 1 && ring[(t + 1) % P] === 0, endChord = ring[t] > 1 && ring[(t + 1) % P] === 1 && ring[(t + 2) % P] === 0;   // 구절 끝의 긴 음
        steps[t] = e[1].map(function (p) { return labelFor(p, endChord ? 99 : endSingle ? 5 : 0); }); });
      return { period: P, ring: ring, steps: steps }; }
    var alive = D.vines.map(function (v) { var a = new Uint8Array(151);
      v.rates.forEach(function (iv) { for (var r = Math.round(iv[0] * 100); r <= Math.round(iv[1] * 100); r++) a[r] = 1; }); return a; });
    return { raw: D, notes: notes, NL: notes.length, mod: [mod('lark'), mod('octopus')],
             intra: [D.note_weights.intra_right, D.note_weights.intra_left], inter: D.note_weights.inter,
             cycles: D.cycles, order: D.loops.map(function (l) { return l.order; }), K: D.cycles.length,
             alive: function (k, rate) { return !!alive[k][Math.max(0, Math.min(150, Math.round(rate * 100)))]; },
             labelFor: labelFor };
  }
  /** 대조군: 음 번호를 섞은 자료 (가중치·고리의 **구조**만 부순다). "연구 자료를 난수로 바꿔도 같은가" 검사용. */
  function shuffled(D, seed) {
    var r = rng(seed || 777), n = D.labels.length, p = []; for (var i = 0; i < n; i++) p.push(i);
    for (i = n - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), t = p[i]; p[i] = p[j]; p[j] = t; }
    var sh = function (M) { return M.map(function (row, a) { return row.map(function (_, b) { return M[p[a]][p[b]]; }); }); };
    var C = JSON.parse(JSON.stringify(D));
    C.note_weights = { intra_right: sh(D.note_weights.intra_right), intra_left: sh(D.note_weights.intra_left), inter: sh(D.note_weights.inter) };
    C.cycles = D.cycles.map(function (c) { return c.map(function (v) { return p[v]; }).sort(function (a, b) { return a - b; }); });
    C.loops = D.loops.map(function (l) { var o = {}; for (var k in l) o[k] = l[k]; o.order = l.order.map(function (v) { return p[v]; }); return o; });
    return C;
  }

  var HS = { SEC: SEC, noteName: noteName, DEG: DEG, rng: rng, derive: derive, shuffled: shuffled,
    // 세 줄 = 세 옥타브대, 일곱 키 = 도레미파솔라시 (ev.code)
    ROWS: [['KeyZ', 'KeyX', 'KeyC', 'KeyV', 'KeyB', 'KeyN', 'KeyM'], ['KeyA', 'KeyS', 'KeyD', 'KeyF', 'KeyG', 'KeyH', 'KeyJ'], ['KeyQ', 'KeyW', 'KeyE', 'KeyR', 'KeyT', 'KeyY', 'KeyU']],
    theme: { bg: '#f3f0e6', paper: '#fbf9f2', ink: '#22302a', dim: '#7d877f', line: '#d6d2c2', lark: '#c98a12', octo: '#d2556f', green: '#2f6b4f', warn: '#b4532a' },
    hue: function (pc) { return [48, 0, 22, 0, 142, 172, 0, 204, 0, 262, 0, 330][pc]; }      // 도레미파솔라시 일곱 빛 (검은 건반은 쓰지 않는다)
  };

  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    var SILENT = /[?&]silent/.test(location.search);
    // ── 소리 ─────────────────────────────────────────────────────────────
    var ac = null, bus = null, live = 0, virt = 0, calls = [];
    function wake() {
      if (SILENT) return; if (ac) { if (ac.state === 'suspended') ac.resume(); return; }
      var AC = window.AudioContext || window.webkitAudioContext; ac = new AC();
      var comp = ac.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 3.5; comp.connect(ac.destination);
      var lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 6200; lp.connect(comp);
      bus = ac.createGain(); bus.gain.value = 0.6; bus.connect(lp);
      var conv = ac.createConvolver(), n = Math.floor(ac.sampleRate * 2.2), b = ac.createBuffer(2, n, ac.sampleRate);
      for (var ch = 0; ch < 2; ch++) { var d = b.getChannelData(ch), prev = 0;
        for (var i = 0; i < n; i++) { var x = (Math.random() * 2 - 1) * Math.exp(-i / (ac.sampleRate * 0.6)) * (1 - i / n); prev = prev * 0.6 + x * 0.4; d[i] = prev; } }
      conv.buffer = b; var wet = ac.createGain(); wet.gain.value = 0.2; bus.connect(conv); conv.connect(wet); wet.connect(comp);   // 잔향은 옅게 — 짙으면 졸리다(판 11)
    }
    function now() { return ac ? ac.currentTime : performance.now() / 1000 + virt; }
    /** 피아노 비슷한 한 음. when 을 안 주면 **지금(5 ms 뒤)** — 누른 그 호출 안에서 부른다. dur 은 초. */
    function voice(pitch, when, dur, vel) {
      var t0 = now(); when = when == null ? t0 + 0.005 : when; dur = dur || 0.4; vel = vel == null ? 0.3 : vel;
      calls.push({ pitch: pitch, delay: when - t0, vel: vel, at: t0 }); if (calls.length > 4000) calls.splice(0, 2000);
      if (!ac || live > 48) return; live++;
      var f = 440 * Math.pow(2, (pitch - 69) / 12), out = ac.createGain(); out.connect(bus);
      var tau = Math.max(0.5, Math.min(2.4, 2.4 - (pitch - 40) * 0.04)), end = when + Math.max(0.12, dur);
      out.gain.setValueAtTime(0, when); out.gain.linearRampToValueAtTime(vel, when + 0.004);
      out.gain.setTargetAtTime(vel * 0.0005, when + 0.004, tau / 4); out.gain.setTargetAtTime(0, end, 0.12);
      [[1, 0.8, 'triangle'], [2.0008, 0.3, 'sine'], [3.0027, 0.1, 'sine']].forEach(function (pt, k) {
        var o = ac.createOscillator(), g = ac.createGain(); o.type = pt[2]; o.frequency.value = f * pt[0]; g.gain.value = pt[1];
        o.connect(g); g.connect(out); o.start(when); o.stop(end + 0.8); if (!k) o.onended = function () { live--; }; });
    }
    HS.audio = { wake: wake, now: now, voice: voice, calls: calls, get silent() { return SILENT; }, get on() { return !!ac; } };

    // ── 시계: 8분음표마다 onStep(t, when). when = 그 스텝이 울릴 소리 시각(조금 앞서 부른다) ─────────
    HS.clock = function (onStep) {
      var t = 0, next = 0, running = false, C = { speed: 1 };
      function pump() { if (!running) return; var n = now(); if (next < n - 1) next = n + 0.03;
        while (next < n + 0.1) { onStep(t++, next); next += SEC / C.speed; } }
      setInterval(pump, 25);
      document.addEventListener('visibilitychange', function () { if (document.hidden) running = false; });
      C.start = function () { if (!running) { running = true; next = now() + 0.03; } };
      C.stop = function () { running = false; };
      C.advance = function (n) { for (var i = 0; i < n; i++) { virt += SEC / C.speed; onStep(t++, now()); } };   // 검증·무음 모드: n 스텝을 곧바로
      Object.defineProperty(C, 'step', { get: function () { return t; } });
      Object.defineProperty(C, 'running', { get: function () { return running; } });
      return C;
    };

    // ── 키: ev.code (한글 입력 상태에서도 같다). 자동 반복은 버린다. 창이 초점을 잃으면 전부 뗀다 ─────────
    HS.keys = function (down, up) {
      var held = {};
      addEventListener('keydown', function (ev) { if (ev.ctrlKey || ev.metaKey || ev.altKey || !ev.code) return;
        if (/^(Arrow|Space|Backspace)/.test(ev.code)) ev.preventDefault();
        if (held[ev.code]) return; held[ev.code] = true; down(ev.code, ev); });
      addEventListener('keyup', function (ev) { if (!held[ev.code]) return; delete held[ev.code]; if (up) up(ev.code, ev); });
      addEventListener('blur', function () { Object.keys(held).forEach(function (c) { delete held[c]; if (up) up(c, null); }); });
      return held;
    };
    HS.load = function () { return fetch('../lenia/tonnetz.json').then(function (r) { return r.json(); }); };
    HS.hook = function (o) { window.__sk = o; return o; };               // 검증이 쓰는 문: { press(code), release(code), advance(n), probe() }
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = HS;
  root.HS = HS;
})(typeof globalThis !== 'undefined' ? globalThis : this);
