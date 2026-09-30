/* sketch/wheels-core.js — 두 바퀴 (시안 B) 엔진. DOM 없음. 명세: docs/sketch_spec.md §5 B
 *
 * 상태   바퀴 둘: 오른손 32톱니 · 왼손 33톱니(↑/↓ 로 31~35). 톱니 하나 = 모듈의 한 스텝 = 음들의 목록 {li, life(0~1), mine(내가 심었나)}.
 *        톱니마다 **자리 수**는 모듈 그대로(화음 4 · 단음 1 · 쉼 0) — 톱니의 모양(리듬)은 hibari 로 남고, 거기 박힌 음이 점점 내 음이 된다.
 *        바늘 자리 pos[손]. 처음 톱니는 hibari 모듈 그대로다 → 손대지 않은 첫 몇 초는 원곡(계단 상승 · 4·1 흔들림 · 32 대 33 어긋남).
 * 갱신   스텝마다 두 바퀴가 한 톱니씩 돈다. 바늘을 지나는 톱니의 음이 운다(세기 = 그 음의 life).
 *        운 음은 닳는다: life −WEAR × 배고픔 × 제비 0.8~1.2. 배고픔 = 마지막으로 손댄 뒤 지난 스텝 / 16 (최대 1) — 돌보는 동안엔 천천히, 손을 떼면 빨리 닳는다.
 *        다 닳으면 빠진다 — 톱니가 비면 쉼이 된다.
 *        그 스텝에 두 바퀴가 함께 낸 음들이 (그 rate 에 살아 있는) 고리를 TAU 이상 덮으면(희귀도 가중), 그 고리에 든 **내가 심은 음**은 돌보는 동안 닳지 않는다.
 * 살리기 손을 떼면 원곡의 톱니도 내가 심은 음도 세 바퀴(96스텝) 안에 닳아 사라진다 — 방치하면 멎는다.
 *        돌보는 동안엔 원곡이 천천히 닳고, 고리를 이루는 내 음은 남고, 아닌 음은 닳는다 — 곡이 천천히 hibari 에서 내 곡으로 바뀐다.
 *        심기·밀기·톱니 수 바꾸기는 음을 빼지 않는다 — 많이 만져서 멎는 길은 없다.
 * 키     가운데 줄 A~J · 윗줄 Q~U = 그 음을 곧바로 울리고 **오른손 바퀴**의 방금 지난 톱니에 심는다(한 바퀴 뒤에 돌아온다)
 *        아랫줄 Z~M = 같은 일을 **왼손 바퀴**에   ←/→ = 왼손 바퀴를 한 톱니 당기기/밀기   ↑/↓ = 왼손 바퀴의 톱니 수 +1/−1 (31~35)
 *        그 밖의 키 = 가장 닳은 바퀴에 제비로 하나 심는다.  화면: PadR0~6 · PadL0~6 건반 · ArrowX 단추
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var DEF = {
    WEAR: 0.6,      // 배고플 때 한 번 울면 닳는 양 (1 → 두 번 울면 거의 사라진다)
    TAU: 0.35,      // 고리를 덮었다고 치는 몫 (원래 OM 의 활성 문턱)
    MINE: 0.9,      // 심은 음의 첫 life
    MAXN: 5,        // 톱니 하나에 들어가는 음 수
    RATE: 0.5,      // 살아 있는 고리를 고르는 rate (고정)
    GUARD: true     // 대조군용: 고리 보호 끄기
  };
  var BANDS = [55, 65, 77];

  function create(H, opts) {
    opts = opts || {};
    var P = {}, q; for (q in DEF) P[q] = (q in opts) ? opts[q] : DEF[q];
    var rng = HS.rng(opts.seed == null ? 1 : opts.seed), N = H.notes, NL = H.NL, K = H.K, cyc = H.cycles;
    function zeros(n) { var a = []; for (var j = 0; j < n; j++) a.push(0); return a; }
    var cnt = zeros(NL); cyc.forEach(function (c) { c.forEach(function (u) { cnt[u]++; }); });
    var rar = cnt.map(function (c) { return c ? 1 / c : 0; }), wsum = cyc.map(function (c) { return c.reduce(function (a, u) { return a + rar[u]; }, 0); });
    var live = []; for (var k = 0; k < K; k++) if (H.alive(k, P.RATE)) live.push(k);
    var entry = BANDS.map(function (c) { var row = []; for (var d = 0; d < 7; d++) { var best = -1;
      N.forEach(function (n) { if (n.deg !== d) return; if (best < 0 || Math.abs(n.pitch - c) < Math.abs(N[best].pitch - c) || (n.pitch === N[best].pitch && n.dur < N[best].dur)) best = n.li; });
      row.push(best); } return row; });
    var S = { t: 0, pos: [0, 0], wheel: [0, 1].map(function (h) { return H.mod[h].steps.map(function (g) { return g.map(function (li) { return { li: li, life: 1, mine: false }; }); }); }),
              cap: [0, 1].map(function (h) { return H.mod[h].steps.map(function (g) { return g.length; }); }), alive: true, started: false, hunger: 32, P: P, lastCover: [] };
    function teeth(h) { return S.wheel[h].length; }
    function count() { var n = 0; S.wheel.forEach(function (w) { w.forEach(function (tt) { n += tt.length; }); }); return n; }

    // ── 누르기 ────────────────────────────────────────────────────────────
    function plant(h, li) {                                 // 방금 울린 톱니에 심는다(쉼은 비워 둔다 — 넷까지 거슬러 올라간다) — 한 바퀴 뒤에 돌아온다
      var w = S.wheel[h], n0 = teeth(h), p = (S.pos[h] - 1 + n0) % n0, b;
      for (b = 1; b <= 6; b++) { var q2 = (S.pos[h] - b + n0) % n0; if (S.cap[h][q2] > 0) { p = q2; break; } }
      var tt = w[p], had = null, cp = Math.max(1, S.cap[h][p]);
      tt.forEach(function (x) { if (x.li === li) had = x; });
      if (had) { had.life = Math.min(1, Math.max(had.life, P.MINE) + 0.1); had.mine = true; }
      else { if (tt.length >= cp) { var lo = 0; tt.forEach(function (x, i) { if (x.life < tt[lo].life) lo = i; }); tt.splice(lo, 1); }   // 자리가 차 있으면 가장 닳은 음의 자리를 잇는다
        tt.push({ li: li, life: P.MINE, mine: true }); }
      S.alive = true; S.started = true; S.hunger = 0;
      return { kind: 'plant', hand: h, tooth: p, li: li, notes: [{ pitch: N[li].pitch, dur: 2, vel: 0.34, li: li, hand: h }] };
    }
    function nudge(d) {                                     // 왼손 바퀴를 한 톱니 민다(→) · 당긴다(←)
      S.pos[1] = (S.pos[1] + d + teeth(1)) % teeth(1); S.started = true; S.hunger = 0;
      var tt = S.wheel[1][S.pos[1]], u = tt.length ? tt[0].li : 0;
      return { kind: 'nudge', d: d, notes: [{ pitch: N[u].pitch, dur: 1, vel: tt.length ? 0.2 : 0.08, li: u, hand: 1 }] };
    }
    function resize(d) {                                    // 왼손 바퀴의 톱니 수 (31~35): 늘리면 빈 톱니가 바늘 뒤에 끼고, 줄이면 가장 빈 톱니가 빠진다(음은 옆 톱니로 옮긴다)
      var w = S.wheel[1], n = w.length, p; S.hunger = 0;
      if (d > 0 && n < 35) { p = (S.pos[1] - 1 + n) % n; w.splice(p + 1, 0, []); S.cap[1].splice(p + 1, 0, 1); if (S.pos[1] > p) S.pos[1]++; }   // 새 톱니는 한 자리
      else if (d < 0 && n > 31) { var e = 0; w.forEach(function (tt, i) { if (tt.length < w[e].length) e = i; }); var mv = w[e]; w.splice(e, 1); var ce = S.cap[1].splice(e, 1)[0];
        if (S.pos[1] > e) S.pos[1]--; S.pos[1] %= w.length; var ne = e % w.length, nb = w[ne]; S.cap[1][ne] += ce; mv.forEach(function (x) { nb.push(x); }); }   // 음은 빼지 않는다(자리째 옆 톱니로)
      var u = entry[1][(w.length - 31) % 7];
      return { kind: 'teeth', n: w.length, notes: [{ pitch: N[u].pitch, dur: 1, vel: 0.12, li: u, hand: 1 }] };
    }
    function press(code) {
      var d, m;
      if ((d = HS.ROWS[1].indexOf(code)) >= 0) return plant(0, entry[1][d]);
      if ((d = HS.ROWS[2].indexOf(code)) >= 0) return plant(0, entry[2][d]);
      if ((d = HS.ROWS[0].indexOf(code)) >= 0) return plant(1, entry[0][d]);
      if ((m = /^Pad([RL])([0-6])$/.exec(code))) return m[1] === 'R' ? plant(0, entry[1][+m[2]]) : plant(1, entry[0][+m[2]]);
      if (code === 'ArrowLeft' || code === 'ArrowRight') return nudge(code === 'ArrowLeft' ? -1 : 1);
      if (code === 'ArrowUp' || code === 'ArrowDown') return resize(code === 'ArrowUp' ? 1 : -1);
      var lifeOf = [0, 1].map(function (h) { var s = 0; S.wheel[h].forEach(function (tt) { tt.forEach(function (x) { s += x.life; }); }); return s; });
      var h = lifeOf[0] <= lifeOf[1] ? 0 : 1; return plant(h, entry[h ? 0 : 1][rng() * 7 | 0]);             // 그 밖의 키: 더 닳은 바퀴에 하나
    }

    // ── 한 스텝 ───────────────────────────────────────────────────────────
    function step() {
      var out = { t: S.t++, pos: S.pos.slice(), notes: [], worn: 0, grew: 0, cover: [] }, h;
      if (!S.alive) return out;
      var sound = [];
      for (h = 0; h < 2; h++) { var tt = S.wheel[h][S.pos[h]], ring = H.mod[h].ring, chord = tt.length >= 3;
        tt.slice().sort(function (a, b) { return N[a.li].pitch - N[b.li].pitch; }).forEach(function (x, j) {
          var vel = (chord ? (j === 0 ? 0.2 : 0.14) : 0.3) * (0.35 + 0.65 * x.life) * (h ? 0.8 : 1) * (x.mine ? 1.15 : 1);
          out.notes.push({ pitch: N[x.li].pitch, dur: x.mine ? 2 : N[x.li].dur, vel: vel, li: x.li, hand: h, mine: x.mine, life: x.life, tooth: S.pos[h] });
          sound.push(x.li); }); }
      var hit = {}, heard = {}; sound.forEach(function (u) { heard[u] = 1; });
      if (P.GUARD) live.forEach(function (k2) { var a = 0; cyc[k2].forEach(function (u) { if (heard[u]) a += rar[u]; }); if (a / wsum[k2] >= P.TAU) { out.cover.push(k2); cyc[k2].forEach(function (u) { hit[u] = 1; }); } });
      S.lastCover = out.cover;
      for (h = 0; h < 2; h++) { var t2 = S.wheel[h][S.pos[h]];
        for (var i = t2.length - 1; i >= 0; i--) { var x = t2[i];
          if (x.mine && hit[x.li] && S.hunger < 32) { out.grew++; continue; }                  // 고리를 이룬 심은 음은 돌보는 동안 닳지 않는다
          x.life -= P.WEAR * Math.min(1, S.hunger / 16) * (0.8 + 0.4 * rng()); if (x.life <= 0) { t2.splice(i, 1); out.worn++; } }
        S.pos[h] = (S.pos[h] + 1) % teeth(h); }
      S.hunger++; S.alive = count() > 0; out.alive = S.alive;
      return out;
    }
    function probe() { var mine = 0, orig = 0; S.wheel.forEach(function (w) { w.forEach(function (tt) { tt.forEach(function (x) { if (x.mine) mine++; else orig++; }); }); });
      return { alive: S.alive, mine: mine, orig: orig, teeth: [teeth(0), teeth(1)], pos: S.pos.slice(), t: S.t, cover: S.lastCover.slice() }; }
    return { press: press, release: function () { return null; }, step: step, probe: probe, state: S, entry: entry, live: live };
  }

  var API = { create: create, DEF: DEF };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSWheels = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
