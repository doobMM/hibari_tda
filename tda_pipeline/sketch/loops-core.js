/* sketch/loops-core.js — 고리 합주 (시안 C) 엔진. DOM 없음. 명세: docs/sketch_spec.md §5 C
 *
 * 상태   고리마다 기운 life(0 = 꺼짐) · 켜질 때의 세기 amp · 지침 tired.  음마다 heat(지금 울리는 중, 남은 스텝) · hamp(그 소리의 세기).
 *        rate(구간 15개 — 구간마다 살아 있는 고리가 다르다) · slot[15](살아 있는 고리 ↔ 키) · ph(모듈 안의 자리).
 * 소리   스텝마다 켜진 고리들 = OM 한 줄 → Algorithm 1 이 겹침에서 음을 뽑는다(여러 고리에 든 음이 그만큼 자주 뽑힌다).
 *        몇 음인지는 모듈의 리듬(오른손 32, 기운이 넉넉하면 왼손 33 도)이 정하고, 뽑힌 후보 중 모듈의 그 스텝 음높이에 가까운 것을 고른다(계단).
 * 연쇄   지금 울리는 음들이 꺼진 고리의 음을 τ=0.35(희귀도 가중) 이상 덮은 스텝이 HOLD(3)번 쌓이면 그 고리가 저절로 켜진다(스텝에 하나, 가장 많이 덮인 것).
 *        세기는 덮은 소리 세기의 GAIN(0.55)배 — 기운은 옮겨질 때마다 준다.
 * 살리기 켜진 고리는 스텝마다 1/LIFE(44) 씩 기운이 빠져 꺼진다. 기운을 넣는 것은 내 손뿐이다 → 방치하면 멎는다(세기 1 → 0.55 → 0.30 세 대까지).
 *        켜져 있는 동안 지치고(tired) 쉬면 돌아온다. 지친 고리는 연쇄로 안 켜지고, 눌러 켜면 약하게(그래도 절반은) 켜진다 — 누르는 것이 죽이지 않는다.
 * 키     고리 키(숫자 줄 + QWERT): 꺼져 있거나 흐린 고리 → 환하게 켠다(그 고리의 음들이 곧바로 울린다) · 환한 고리 → 끈다.
 *        일곱 건반(Z~M, A~J, Pad0~6) = 그 음이름을 울려, 그 음으로 τ 이상 덮인 고리 둘까지 깨운다 · ←/→ = rate 구간 · 그 밖의 키 = 쉬고 있는 고리 하나를 켠다.
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var LOOP_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9', 'Digit0', 'KeyQ', 'KeyW', 'KeyE', 'KeyR', 'KeyT'];
  var DEF = {
    TAU: 0.35,        // 고리가 켜지는 덮임 (원래 OM 의 활성 문턱 그대로)
    LIFE: 44,         // 세기 1 로 켠 고리가 도는 스텝 수 (20초)
    GAIN: 0.55,       // 연쇄로 켜진 고리의 세기 = 덮은 소리 세기 × GAIN  (<1 — 기운은 옮겨질 때마다 준다)
    AMP_MIN: 0.2,     // 이보다 약한 연쇄는 일어나지 않는다
    HOLD: 3,          // τ 이상 덮인 스텝이 이만큼 쌓여야 저절로 켜진다 (한 번 스친 것으로는 안 켜진다)
    REST: 48,         // 다 지친 고리가 다 쉬는 데 걸리는 스텝
    DIM: 0.6,         // 기운이 (누르면 얻을 세기 × DIM) 아래면 '흐리다' — 누르면 끄지 않고 다시 환하게 켠다
    MUTE: 16,         // 내가 끈 고리는 이만큼은 연쇄로 다시 켜지지 않는다
    OVER: 2,          // Algorithm 1 에서 필요한 음의 몇 배를 뽑아 그중 모듈 음높이에 가까운 것을 고르나
    RICH: 2.5,        // 기운 합이 이만큼이면 왼손(33)이 들어온다
    CALL: 2,          // 건반 한 번에 깨어나는 고리 수 (가장 많이 덮인 것부터)
    GHOST: 1.5,       // rate 를 옮겨 사라진 고리는 이 배로 빨리 꺼진다
    START: 0.5,       // 처음 rate
    CHAIN: true, STAIR: true   // 대조군용: 연쇄 끄기 · 계단(모듈 음높이 따라가기) 끄기
  };

  function create(H, opts) {
    opts = opts || {};
    var P = {}, q; for (q in DEF) P[q] = (q in opts) ? opts[q] : DEF[q];
    var G = opts.algo1 || root.GenerationAlgo1, rng = HS.rng(opts.seed == null ? 1 : opts.seed);
    var K = H.K, NL = H.NL, N = H.notes, cyc = H.cycles, NS = LOOP_KEYS.length, i, k;

    var cnt = []; for (i = 0; i < NL; i++) cnt.push(0);
    cyc.forEach(function (c) { c.forEach(function (u) { cnt[u]++; }); });
    var rar = cnt.map(function (c) { return c ? 1 / c : 0; });                                   // 희귀도: 적은 고리에만 든 음일수록 무겁다
    var wsum = cyc.map(function (c) { return c.reduce(function (a, u) { return a + rar[u]; }, 0); });
    var pool = new G.NodePool({ labels: N.map(function (n) { return { label: n.li + 1, label_idx: n.li, pitch: n.pitch, dur: n.dur, count: n.count }; }), rng: rng });
    var mgr = new G.CycleSetManager({ cycles: cyc.map(function (c, j) { return { cycle_idx: j, note_labels_0idx: c }; }), K: K });
    var liOf = {}; N.forEach(function (n) { liOf[n.pitch * 10 + n.dur] = n.li; });
    var byDeg = [[], [], [], [], [], [], []]; N.forEach(function (n) { byDeg[n.deg].push(n.li); });   // 음이름(도~시)마다 그 음들

    // rate 구간: 살아 있는 고리 집합이 같은 rate 끼리 묶는다 (15개)
    var regs = [], prev = null;
    for (var r = 0; r <= 150; r++) { var set = []; for (k = 0; k < K; k++) if (H.alive(k, r / 100)) set.push(k);
      if (set.join() !== prev) { regs.push({ r0: r, r1: r, set: set }); prev = set.join(); } else regs[regs.length - 1].r1 = r; }

    function zeros(n) { var a = []; for (var j = 0; j < n; j++) a.push(0); return a; }
    var S = { t: 0, ph: 0, reg: 0, rate: 0, slot: zeros(NS).map(function () { return -1; }), life: zeros(K), amp: zeros(K), tired: zeros(K), mute: zeros(K),
              res: zeros(K), chain: zeros(K), heat: zeros(NL), hamp: zeros(NL), mult: zeros(NL), eng: zeros(NL), lamp: zeros(NL), nOn: 0, body: 0, P: P };
    var ROW = new Int8Array(K), VV = new Int8Array(8 * K), IL = new Int32Array(8);

    function recount() {                                   // 켜진 고리 수 · 기운 합 · 음마다 겹침 수(mult)와 그 음을 가진 고리의 가장 큰 기운/세기
      S.nOn = 0; S.body = 0;
      for (var li = 0; li < NL; li++) { S.mult[li] = 0; S.eng[li] = 0; S.lamp[li] = 0; }
      for (var k2 = 0; k2 < K; k2++) { var on = S.life[k2] > 0; ROW[k2] = on ? 1 : 0; if (!on) continue;
        S.nOn++; S.body += S.life[k2];
        cyc[k2].forEach(function (u) { S.mult[u]++; if (S.life[k2] > S.eng[u]) S.eng[u] = S.life[k2]; if (S.amp[k2] > S.lamp[u]) S.lamp[u] = S.amp[k2]; }); }
    }
    function setReg(j) {                                   // 자리(키)는 남는 고리가 그대로 지킨다. 새 고리는 빈 자리에 든다
      var inSet = {}, came = [], went = [];
      regs[j].set.forEach(function (k2) { inSet[k2] = 1; });
      S.slot.forEach(function (k2, s) { if (k2 >= 0 && !inSet[k2]) { S.slot[s] = -1; went.push(k2); } });
      regs[j].set.forEach(function (k2) { if (S.slot.indexOf(k2) < 0) { S.slot[S.slot.indexOf(-1)] = k2; came.push(k2); } });
      S.reg = j; S.rate = Math.round((regs[j].r0 + regs[j].r1) / 2) / 100;
      return { came: came, went: went };
    }
    function ring(li, dur, amp) { if (dur > S.heat[li]) S.heat[li] = dur; S.hamp[li] = amp; }     // 그 음이 지금부터 dur 스텝 울린다
    function cover(k2) {                                   // 지금 울리는 음이 고리 k 를 얼마나 덮나 (희귀도 가중) · 덮은 소리의 세기
      var a = 0, w = 0; cyc[k2].forEach(function (u) { if (S.heat[u] > 0) { a += rar[u]; w += rar[u] * S.hamp[u]; } });
      return { cov: a / wsum[k2], amp: a ? w / a : 0 };
    }
    function turnOn(k2, amp) { if (!S.nOn) S.ph = -1; S.amp[k2] = S.life[k2] = amp; S.mute[k2] = 0; S.chain[k2] = 0; recount(); }   // 멎었다가 다시 켜면 한 스텝 쉬고(누른 소리가 첫 박) 모듈의 처음부터
    function chordOf(k2, vel, dur) {                       // 고리의 음들(같은 높이는 한 번) — 고리를 도는 순서대로
      var seen = {}, out = [];
      H.order[k2].forEach(function (u) { var n = N[u]; if (seen[n.pitch]) return; seen[n.pitch] = 1; out.push({ pitch: n.pitch, dur: dur, vel: vel, li: u }); });
      return out;
    }
    function edge(k2, hi) { var best = cyc[k2][0]; cyc[k2].forEach(function (u) { if (hi ? N[u].pitch > N[best].pitch : N[u].pitch < N[best].pitch) best = u; }); return best; }

    // ── 누르기: 돌려주는 음은 곧바로 울린다 ─────────────────────────────────────────
    function toggle(s) {
      var k2 = S.slot[s], out, amp = 1 - 0.5 * S.tired[k2];   // 지친 고리는 약하게 — 그래도 절반은 켜진다
      if (S.life[k2] >= P.DIM && S.nOn > 1) {              // 환하게 켜져 있으면 끈다 — 단 마지막 하나는 끄지 않고, 문턱은 절댓값(검토 지적: 다시 눌러 살리려다 꺼졌다)
        S.life[k2] = 0; S.mute[k2] = P.MUTE; S.res[k2] = 0; recount(); var lo = edge(k2, false);
        return { kind: 'off', k: k2, slot: s, notes: [{ pitch: N[lo].pitch, dur: 1, vel: 0.12, li: lo }], woke: [] };
      }
      turnOn(k2, amp);                                     // 꺼져 있거나 흐려진(저절로 켜졌거나 다 돌아가는) 고리는 다시 환하게
      out = chordOf(k2, Math.max(0.13, Math.min(0.26, 0.5 / Math.sqrt(cyc[k2].length))) * (0.6 + 0.4 * amp), 2);
      out.reduce(function (a, n) { return n.pitch > a.pitch ? n : a; }).vel *= 1.3;          // 맨 윗음은 또렷이
      return { kind: 'on', k: k2, slot: s, notes: out, woke: [] };
    }
    function note(deg) {                                   // 일곱 건반: 그 음이름의 음들이 (옥타브로) 울리고, 덮인 고리가 깨어난다
      var seen = {}, out = [], woke = [];
      byDeg[deg].forEach(function (u) { ring(u, 2, 1); if (seen[N[u].pitch]) return; seen[N[u].pitch] = 1; out.push({ pitch: N[u].pitch, dur: 2, vel: out.length ? 0.3 : 0.22, li: u }); });
      var hit = [];
      S.slot.forEach(function (k2) { if (k2 < 0 || S.life[k2] > 0) return; var c = cover(k2); if (c.cov >= P.TAU) hit.push({ k: k2, cov: c.cov, amp: c.amp }); });
      hit.sort(function (a, b) { return b.cov - a.cov; }).slice(0, P.CALL).forEach(function (x) { turnOn(x.k, 0.85 * x.amp * (1 - 0.5 * S.tired[x.k])); woke.push(x.k); });   // 가장 많이 덮인 고리부터
      return { kind: 'note', deg: deg, notes: out, woke: woke };
    }
    function shift(d) {                                    // rate 구간을 옮긴다. 사라진 고리는 자리를 내주고 흐려지며 꺼진다(GHOST)
      var j = S.reg + d;
      if (j < 0 || j >= regs.length) return { kind: 'edge', notes: [{ pitch: N[0].pitch, dur: 1, vel: 0.1, li: 0 }], woke: [] };
      var ch = setReg(j); recount();
      var src = ch.came.length ? ch.came : ch.went, out = src.slice(0, 3).map(function (k2) { var u = edge(k2, d > 0); return { pitch: N[u].pitch, dur: 1, vel: ch.came.length ? 0.24 : 0.12, li: u }; });
      var woke = [];
      if (ch.came.length) { var kc = ch.came[0]; turnOn(kc, 0.7 * (1 - 0.5 * S.tired[kc])); woke.push(kc);        // 새로 온 고리 하나가 곧바로 켜진다 — 누르면 소리가 바뀌고, 멎은 뒤에도 다시 시작된다
        out = chordOf(kc, 0.16, 2).slice(0, 4); }
      return { kind: 'rate', came: ch.came, went: ch.went, notes: out, woke: woke };
    }
    function any() {                                       // 그 밖의 키: 쉬고 있는 고리 중 가장 덜 지친 것을 켠다 (같으면 제비)
      var best = -1, bt = 9;
      S.slot.forEach(function (k2, s) { if (k2 < 0 || S.life[k2] > 0) return; var v = S.tired[k2] + rng() * 0.05; if (v < bt) { bt = v; best = s; } });
      if (best < 0) S.slot.forEach(function (k2, s) { if (k2 >= 0 && S.life[k2] < P.DIM * (1 - 0.5 * S.tired[k2]) && S.life[k2] < bt) { bt = S.life[k2]; best = s; } });   // 다 켜져 있으면 가장 흐린 것을 다시 환하게
      if (best >= 0) return toggle(best);
      var top = 0; for (var u = 1; u < NL; u++) if (S.mult[u] > S.mult[top]) top = u;             // 전부 켜져 있으면 가장 많이 겹친 음 하나
      return { kind: 'none', notes: [{ pitch: N[top].pitch, dur: 1, vel: 0.3, li: top }], woke: [] };
    }
    function press(code) {
      var s = LOOP_KEYS.indexOf(code), d;
      if (s >= 0 && S.slot[s] >= 0) return toggle(s);
      if (/^Pad[0-6]$/.test(code)) return note(+code.charAt(3));
      if ((d = HS.ROWS[0].indexOf(code)) >= 0 || (d = HS.ROWS[1].indexOf(code)) >= 0) return note(d);
      if (code === 'ArrowLeft' || code === 'ArrowRight') return shift(code === 'ArrowLeft' ? -1 : 1);
      return any();
    }

    // ── 한 스텝 ───────────────────────────────────────────────────────────
    function pick(h, tg, n) {                              // 손 h 가 이 스텝에 n 음: Algorithm 1 이 겹침에서 후보를 뽑고, 모듈의 음높이에 가까운 것을 고른다
      var want = tg.map(function (u) { return N[u]; }).sort(function (a, b) { return a.pitch - b.pitch; });
      var ord = [0, want.length - 1, 1, 2].filter(function (v, j, a) { return v < want.length && a.indexOf(v) === j; }).slice(0, n);   // 베이스 · 맨 위 · 그 사이
      var uni = mgr.getUnionNodes(ROW).size, chord = tg.length >= 3, out = [];
      IL.fill(0); IL[0] = Math.min(uni, P.STAIR ? P.OVER * n : n);
      for (var w = 0; w < 8; w++) VV.set(ROW, w * K);
      var cand = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen: IL, overlap: { T: 8, K: K, values: VV }, rng: rng }).notes
        .filter(function (x) { return x[0] === 0; }).map(function (x) { return liOf[x[1] * 10 + (x[2] - x[0])]; });
      if (P.STAIR && chord && ord.length) {                  // 베이스는 켜진 고리들의 음 전체에서 모듈 베이스에 가장 가까운 음 (검토: 후보 안에서만 고르면 계단이 43% 만 맞았다)
        var tb = want[ord[0]], bb = -1; for (var z = 0; z < NL; z++) if (S.mult[z] > 0 && (bb < 0 || Math.abs(N[z].pitch - tb.pitch) < Math.abs(N[bb].pitch - tb.pitch) || (N[z].pitch === N[bb].pitch && S.mult[z] > S.mult[bb]))) bb = z;
        if (bb >= 0) { var ci = cand.indexOf(bb); if (ci >= 0) cand.splice(ci, 1); cand.unshift(bb); } }
      ord.forEach(function (wi, j) {
        if (!cand.length) return;
        var tgt = want[wi], bi = 0;
        if (P.STAIR && !(chord && j === 0)) cand.forEach(function (u, c) { if (Math.abs(N[u].pitch - tgt.pitch) < Math.abs(N[cand[bi]].pitch - tgt.pitch)) bi = c; });
        var u = cand.splice(bi, 1)[0], e = 0.55 + 0.45 * Math.min(1, S.eng[u]);
        var vel = (chord ? (j === 0 ? 0.2 : 0.14) : 0.32) * e * (h ? 0.7 : 1) * (S.mult[u] >= 2 ? 1.12 : 1);   // 화음은 여리게(베이스만 조금 또렷이), 단음은 또렷이, 겹친 음은 조금 더
        out.push({ pitch: N[u].pitch, dur: tgt.dur, vel: vel, li: u, hand: h, ov: S.mult[u] });
      });
      return out;
    }
    function step() {
      var out = { t: S.t++, ph: -1, notes: [], woke: [], slept: [] }, k2;
      if (S.nOn) {
        var ph = out.ph = S.ph++;
        for (var h = 0; h < 2 && ph >= 0; h++) {
          if (h === 1 && S.body < P.RICH) continue;                                       // 왼손은 합주가 넉넉할 때만 들어온다
          var m = H.mod[h], p = ph % m.period, tg = m.steps[p]; if (!tg.length) continue;
          var n = tg.length < 3 ? tg.length : Math.max(2, Math.min(tg.length, Math.round(1.5 + 1.5 * S.body)));   // 기운이 줄면 화음이 가늘어진다 (4 → 3 → 2)
          if (h === 1) n = Math.min(n, 2);
          var acc = (h === 0 && p % 16 === 0) ? 1.25 : 1;                                   // 구절 첫 화음은 세게
          pick(h, tg, n).forEach(function (x) { x.vel *= acc; ring(x.li, x.dur, S.lamp[x.li]); out.notes.push(x); });
        }
      }
      var bk = -1, bc = 0, ba = 0;                                                          // 연쇄: τ 이상 덮인 스텝이 HOLD 번 쌓인 고리가 저절로 켜진다 (쉰 고리만, 스텝에 하나)
      if (P.CHAIN) S.slot.forEach(function (k3) {
        if (k3 < 0 || S.life[k3] > 0 || S.mute[k3] > 0 || S.tired[k3] >= 0.5) { if (k3 >= 0) S.res[k3] = 0; return; }
        var c = cover(k3), amp = P.GAIN * c.amp;
        S.res[k3] = c.cov >= P.TAU && amp >= P.AMP_MIN ? S.res[k3] + 1 : Math.max(0, S.res[k3] - 1);   // 울림이 쌓인다 (덮이지 않으면 빠진다)
        if (S.res[k3] >= P.HOLD && c.cov > bc) { bk = k3; bc = c.cov; ba = amp; } });
      if (bk >= 0) { S.amp[bk] = S.life[bk] = ba; S.res[bk] = 0; S.chain[bk] = 1; out.woke.push(bk); }
      for (k2 = 0; k2 < K; k2++) {
        if (S.life[k2] > 0 && out.woke.indexOf(k2) < 0) {                                  // 돌면 기운이 빠지고 지친다
          S.life[k2] -= (S.slot.indexOf(k2) < 0 ? P.GHOST : 1) / P.LIFE; if (!S.chain[k2]) S.tired[k2] = Math.min(1, S.tired[k2] + 1 / P.LIFE);   // 연쇄로 켜진 고리는 지치지 않는다(검토: 드문 돌봄을 연쇄가 죽였다)
          if (S.life[k2] < 1e-6) { S.life[k2] = 0; out.slept.push(k2); }
        } else if (S.life[k2] <= 0) { S.tired[k2] = Math.max(0, S.tired[k2] - 1 / P.REST); if (S.mute[k2] > 0) S.mute[k2]--; }   // 쉬면 돌아온다
      }
      for (var u = 0; u < NL; u++) if (S.heat[u] > 0) S.heat[u]--;
      recount(); out.alive = S.nOn > 0;
      return out;
    }
    function probe() {
      var on = []; for (var k2 = 0; k2 < K; k2++) if (S.life[k2] > 0) on.push(k2);
      return { alive: S.nOn > 0, on: on, nOn: S.nOn, body: S.body, t: S.t, ph: S.ph, rate: S.rate, reg: S.reg, slots: S.slot.slice() };
    }

    for (i = 0; i < regs.length; i++) if (regs[i].r0 <= P.START * 100 && P.START * 100 <= regs[i].r1) setReg(i);
    recount();
    return { press: press, release: function () { return null; }, step: step, probe: probe, state: S, regs: regs, keys: LOOP_KEYS, cover: cover, rar: rar };
  }

  var API = { create: create, DEF: DEF, KEYS: LOOP_KEYS };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSLoops = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
