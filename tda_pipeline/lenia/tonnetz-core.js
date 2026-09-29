/* tonnetz-core.js — 종달새와 문어 의 엔진 (docs/tonnetz_lenia_spec.md). 화면·소리와 분리돼 있다.
 * 페이지(tonnetz.html)와 검증(tools/verify_tonnetz_lenia.mjs)이 **같은 이 파일**을 돌린다.
 *
 * 세계 — Tonnetz 삼각격자를 주기 (0,6)·(12,−6) 으로 감은 토러스. 72칸, 음이름마다 6칸.
 *   skew 좌표 (c = 5도 축, r = 장3도 축), 음이름 = 7c + 4r mod 12.
 *   30° 돌린 화면 좌표: x = 0.866c, y = 0.5c + r  (W = 10.392, H = 6 로 감긴다).
 * 생명체 — 머리(지금 부르는 음 = 격자 한 칸 + 높이) · 리듬 고리(hibari 한 손의 모듈) · 기운 · 노래의 역사.
 *   종달새 = 오른손(32스텝), 문어 = 왼손(33스텝). 몸 그림은 역사를 박자틀 32 로 접은 것 (페이지가 그린다).
 * 한 스텝 = 8분음표. 리듬 고리가 켜진 박에 운다:
 *   머리 = 고리-Markov 한 걸음 (상태 = 음 × 지금 탄 고리, 갈림길에서만 바꿔 탄다) — 격자 위를 기어간다
 *   음   = 전부 Algorithm 1 (generation-algo1.js) — 최근 부른 음 → 고리 활성도 → τ → 한 행(+ 지금 탄 고리)
 *          → 풀(공유 가중 합집합) 추출. Markov 는 음이 아니라 '어느 고리 위에 있나' 를 정한다 (spec §8)
 * 되먹임 — 강화: 고리를 한 바퀴 돌면 기운 +, 기운이 차면 다른 손의 알 · 균형: 우는 음마다 기운 −, 먹이 감쇠.
 */
(function (root) {
  'use strict';
  var S3 = Math.sqrt(3) / 2;
  var W = 12 * S3, H = 6;                        // 10.392 × 6
  var DIRS = [[1, 0, 7], [-1, 0, 5], [0, 1, 4], [0, -1, 8], [1, -1, 3], [-1, 1, 9]];   // [dc, dr, 음이름 차]

  function reduce(c, r) {                        // (c, r) → 기본 상자 0≤c<12, 0≤r<6
    var b = Math.floor(c / 12); c -= 12 * b; r += 6 * b;
    r = ((r % 6) + 6) % 6; return [c, r];
  }
  function buildGeo() {
    var nodes = [], idx = {};
    for (var c = 0; c < 12; c++) for (var r = 0; r < 6; r++) {
      idx[c * 6 + r] = nodes.length;
      nodes.push({ c: c, r: r, pc: (7 * c + 4 * r) % 12, x: S3 * c, y: ((0.5 * c + r) % H + H) % H, nb: [] });
    }
    nodes.forEach(function (n) {
      n.nb = DIRS.map(function (d) { var q = reduce(n.c + d[0], n.r + d[1]); return idx[q[0] * 6 + q[1]]; });
    });
    return { W: W, H: H, nodes: nodes, DIRS: DIRS };
  }

  var DEF = {
    TAU: 0.35,        // 고리 활성 이진화 (build_overlap_bundle 의 threshold)
    WIN: 8,           // 활성도를 재는 최근 스텝 창
    GEN_W: 8,         // algorithm1 호출 창 (음 길이가 잘리지 않게, echo.html 과 같다)
    RHO: 0.8,         // 지금 탄 고리를 계속 탈 확률
    E0: 0.6, MEAL: 0.12, COST: 0.004, EGG: 1.0,
    FOOD_D: 0.18, FOOD_DECAY: 0.012, EAT: 0.06, FOOD_GAIN: 1.0, FOOD_PULL: 4.0,
    TRAIL: 1.0, TRAIL_DECAY: 0.035, FOLLOW: 1.5,
    CAP: 8, MEMORY: 8,   // 알에서 깰 때 기억하는 모듈 수
    randomCycles: false, // 검증 V1: 같은 크기의 난수 고리
    coupled: false       // 검증 V5: 난수를 (seed, 시각, 칸) 으로 새로 시드하고 칸 번호 순으로 처리한다
  };

  function create(data, opts) {
    opts = opts || {};
    var P = {}; for (var k in DEF) P[k] = (k in opts) ? opts[k] : DEF[k];
    var G = opts.algo1 || root.GenerationAlgo1;
    var SEED = opts.seed == null ? 1 : opts.seed;
    var rng = G.makeRng(SEED), R = rng;          // R = 지금 결정에 쓰는 난수 (결합 모드에서 바뀐다)
    function rngAt(t, node) {                    // 결합 모드: 같은 (seed, 시각, 칸) → 같은 난수열
      var h = (SEED ^ Math.imul(t + 1, 0x9E3779B1) ^ Math.imul(node + 1, 0x85EBCA77)) >>> 0;
      h = Math.imul(h ^ (h >>> 16), 0x7FEB352D) >>> 0; h = Math.imul(h ^ (h >>> 15), 0x846CA68B) >>> 0;
      return G.makeRng((h ^ (h >>> 16)) >>> 0 || 1);
    }
    var geo = buildGeo(), NN = geo.nodes.length;
    var LAB = data.labels, NL = LAB.length;

    // ── 고리 (V1 대조군이면 같은 크기의 난수 집합과 난수 순서) ─────────────
    var cycles = data.cycles.map(function (c) { return c.slice(); });
    var loops = data.loops.map(function (l) { return l.order ? l.order.slice() : null; });
    var wts = data.loops.map(function (l) { return l.w; });
    if (P.randomCycles) {
      var rr = G.makeRng(9973 + (opts.seed || 0));
      cycles = cycles.map(function (c) {
        var all = []; for (var i = 0; i < NL; i++) all.push(i);
        for (var j = all.length - 1; j > 0; j--) { var q = Math.floor(rr() * (j + 1)); var t = all[j]; all[j] = all[q]; all[q] = t; }
        return all.slice(0, c.length).sort(function (a, b) { return a - b; });
      });
      loops = cycles.map(function (c) { return c.slice(); });
    }
    var K = cycles.length;
    var succ = loops.map(function (o) {
      var d = {}; if (o) for (var i = 0; i < o.length; i++) d[o[i]] = o[(i + 1) % o.length]; return d;
    });
    var cyclesOf = []; for (var v = 0; v < NL; v++) cyclesOf.push([]);
    for (var ci = 0; ci < K; ci++) if (loops[ci]) loops[ci].forEach(function (u) { cyclesOf[u].push(ci); });
    var cnt = {}; cycles.forEach(function (c) { c.forEach(function (u) { cnt[u] = (cnt[u] || 0) + 1; }); });
    var RAR = []; for (var u = 0; u < NL; u++) RAR.push(cnt[u] ? 1 / cnt[u] : 0);
    var WSUM = cycles.map(function (c) { return c.reduce(function (a, x) { return a + RAR[x]; }, 0); });
    var pool = new G.NodePool({ labels: LAB.map(function (l) {
      return { label: l.li + 1, label_idx: l.li, pitch: l.pitch, dur: l.dur, count: l.count };
    }), rng: rng });
    var mgr = new G.CycleSetManager({ cycles: cycles.map(function (c, i) { return { cycle_idx: i, note_labels_0idx: c }; }), K: K });
    var PD2L = {}; LAB.forEach(function (l) { PD2L[l.pitch * 100 + l.dur] = l.li; });
    var HANDS = data.hands;

    // ── 상태 ──────────────────────────────────────────────────────────
    var S = { t: 0, creatures: [], food: new Float32Array(NN), trail: [new Float32Array(NN), new Float32Array(NN)],
              nextId: 1, P: P, geo: geo };

    function other(sp) { return sp === 'lark' ? 'octopus' : 'lark'; }
    function occupied(n, except) {
      for (var i = 0; i < S.creatures.length; i++) {
        var c = S.creatures[i]; if (c !== except && !c.dead && c.node === n) return true;
      } return false;
    }
    function step1(n, fromLi, toLi) {             // 음 fromLi → toLi 일 때 머리가 갈 칸
      var d = ((LAB[toLi].pitch - LAB[fromLi].pitch) % 12 + 12) % 12;
      if (d === 0) return n;
      for (var i = 0; i < 6; i++) if (DIRS[i][2] === d) return geo.nodes[n].nb[i];
      return nearNode(n, LAB[toLi].pc);            // 격자 이웃이 아니다 — V1 난수 고리에서만 생긴다(건너뛴다)
    }
    function noteAt(n, nearPitch) {                // 칸 n 의 음이름을 가진 hibari 음 중 nearPitch 에 가장 가까운 것
      var pc = geo.nodes[n].pc, best = -1, bd = 1e9;
      for (var i = 0; i < NL; i++) {
        if (LAB[i].pc !== pc || !cyclesOf[i].length) continue;
        var dd = Math.abs(LAB[i].pitch - nearPitch) + (LAB[i].dur === 2 ? 0 : 0.1);
        if (dd < bd) { bd = dd; best = i; }
      } return best;
    }
    function board(cr) {                           // 머리 음을 품은 고리 중 가장 무거운 것에 올라탄다
      var cs = cyclesOf[cr.li], best = -1, bw = -1;
      for (var i = 0; i < cs.length; i++) if (wts[cs[i]] > bw) { bw = wts[cs[i]]; best = cs[i]; }
      cr.cyc = best; cr.boardLi = cr.li; cr.ride = 0;
    }

    /** 알. 칸 n 이 hibari 음이름이고 비어 있어야 한다. */
    function hatch(n, species, nearPitch, energy) {
      var alive = S.creatures.filter(function (c) { return !c.dead; }).length;
      if (alive >= P.CAP || occupied(n)) return null;
      var sp = species || (S.nextId % 2 ? 'lark' : 'octopus');
      var li = noteAt(n, nearPitch == null ? 66 : nearPitch);
      if (li < 0) return null;
      var hd = HANDS[sp], per = hd.period;
      var cr = { id: S.nextId++, species: sp, period: per, ring: hd.ring.slice(), born: S.t, node: n, li: li,
                 z: LAB[li].pitch, cyc: -1, boardLi: li, ride: 0, energy: energy == null ? P.E0 : energy,
                 hist: [], recent: [], meals: 0, eggs: 0, dead: false, deadAt: -1 };
      // 한 손의 기억 — hibari 그 손의 처음 MEMORY 모듈 리듬을 과거로 놓는다 (몸이 처음부터 보이게)
      var M = P.MEMORY;
      hd.early.forEach(function (e) {
        if (e[0] < M * per) cr.hist.push({ t: S.t - M * per + e[0], n: e[1].length, pcs: e[1].map(function (p) { return p % 12; }),
                                          head: e[1][e[1].length - 1] % 12, mem: true });
      });
      board(cr);
      S.creatures.push(cr);
      return cr;
    }

    function feed(n, amt) { S.food[n] = Math.min(4, S.food[n] + (amt == null ? 1 : amt)); }

    /** 끌어다 놓기: 칸 n 의 음이름을 가진 hibari 음 중 지금 높이에 가장 가까운 음으로 이어 걷는다. */
    function move(cr, n) {
      if (occupied(n, cr)) return false;
      var li = noteAt(n, cr.z); if (li < 0) return false;
      cr.node = n; cr.li = li; cr.z = LAB[li].pitch; board(cr); return true;
    }

    function activeRow(cr, out) {
      var s = {};
      for (var i = 0; i < cr.recent.length; i++) if (cr.recent[i].to > S.t) s[cr.recent[i].li] = 1;
      var f = 0;
      for (var c = 0; c < K; c++) {
        var acc = 0, cs = cycles[c];
        for (var j = 0; j < cs.length; j++) if (s[cs[j]]) acc += RAR[cs[j]];
        var on = WSUM[c] > 0 && acc / WSUM[c] >= P.TAU ? 1 : 0;
        out[c] = on; f += on;
      } return f;
    }

    function headStep(cr) {
      var li = cr.li, sp = cr.species === 'lark' ? 1 : 0;   // 따라갈 발자국 = 다른 종의 것
      if (cr.cyc >= 0 && succ[cr.cyc][li] != null && R() < P.RHO) {
        var nx = succ[cr.cyc][li], nn = step1(cr.node, li, nx);
        if (nn >= 0 && !occupied(nn, cr)) return go(cr, cr.cyc, nx, nn, false);
      }
      var cs = cyclesOf[li], opt = [], tot = 0;
      for (var i = 0; i < cs.length; i++) {
        var k2 = cs[i], v2 = succ[k2][li], n2 = step1(cr.node, li, v2);
        if (n2 < 0 || occupied(n2, cr)) continue;
        var w = wts[k2] * (1 + P.FOOD_PULL * S.food[n2] + P.FOLLOW * S.trail[sp][n2]);
        opt.push([k2, v2, n2, w]); tot += w;
      }
      if (!opt.length) return false;                // 막혔다 — 제자리에서 같은 음
      var x = R() * tot;
      for (var j = 0; j < opt.length; j++) { x -= opt[j][3]; if (x <= 0) break; }
      var o = opt[Math.min(j, opt.length - 1)];
      return go(cr, o[0], o[1], o[2], o[0] !== cr.cyc);
    }
    function go(cr, k, nx, nn, switched) {
      if (switched) { cr.cyc = k; cr.boardLi = cr.li; cr.ride = 0; }
      cr.li = nx; cr.node = nn; cr.z = LAB[nx].pitch; cr.ride++;
      if (cr.li === cr.boardLi && cr.ride >= cycles[k].length - 1) {   // 고리 한 바퀴 = 한 끼
        cr.energy += P.MEAL; cr.meals++; cr.ride = 0; cr.lastMeal = S.t;
      }
      return true;
    }

    var ROW = new Int8Array(K);
    /* 한 박에 count 음. **음은 전부 Algorithm 1 이 고른다.** 고리-Markov 는 머리를 옮기고, 지금 탄 고리를
     * 활성 행에 늘 켜 둔다 — 즉 Markov 는 "다음 음" 이 아니라 **"지금 어느 고리 위에 있나"** 를 정한다.
     * 근거: run_cycle_markov.py — 고리의 순회 순서로 음을 고르면 hibari 와 덜 닮고(음높이 JS +11~13%),
     * 같은 고리 안에서 순서를 섞어도 같거나 낫다. 순회 순서는 선율 정보가 아니었다 (spec §8). */
    function sing(cr, count, ev) {
      headStep(cr);
      activeRow(cr, ROW);
      if (cr.cyc >= 0) ROW[cr.cyc] = 1;
      var v = new Int8Array(P.GEN_W * K);
      for (var c = 0; c < K; c++) v[c] = ROW[c];
      for (var w = 1; w < P.GEN_W; w++) v.copyWithin(w * K, 0, K);
      var il = new Int32Array(P.GEN_W); il[0] = count;
      var res = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen: il,
                               overlap: { T: P.GEN_W, K: K, values: v }, rng: R });
      var notes = [], zs = 0;
      for (var i = 0; i < res.notes.length; i++) {
        var x = res.notes[i], d = x[2] - x[0], li2 = PD2L[x[1] * 100 + d];
        notes.push([x[1], d, nearNode(cr.node, x[1] % 12), i === 0 ? 1 : 0]);
        zs += x[1];
        if (li2 != null) cr.recent.push({ li: li2, to: S.t + Math.max(d, P.WIN) });
      }
      cr.recent = cr.recent.filter(function (r) { return r.to > S.t; });
      if (notes.length) cr.z = zs / notes.length;   // 높이 = 지금 부르는 음들의 평균 음높이
      cr.energy -= P.COST * notes.length;
      var sp = cr.species === 'lark' ? 0 : 1;
      S.trail[sp][cr.node] += P.TRAIL;
      var eat = Math.min(S.food[cr.node], P.EAT); S.food[cr.node] -= eat; cr.energy += eat * P.FOOD_GAIN;
      cr.hist.push({ t: S.t, n: notes.length, pcs: notes.map(function (q) { return q[0] % 12; }),
                     head: notes.length ? notes[0][0] % 12 : LAB[cr.li].pc, rows: sumRow() });
      if (cr.hist.length > 400) cr.hist.splice(0, cr.hist.length - 400);
      ev.notes.push({ id: cr.id, species: cr.species, notes: notes, z: cr.z, node: cr.node, rows: sumRow() });
    }
    function sumRow() { var f = 0; for (var c = 0; c < K; c++) f += ROW[c]; return f; }
    function nearNode(n, pc) {                      // 칸 n 에서 음이름 pc 인 가장 가까운 칸 (너비 우선)
      var seen = {}, q = [n]; seen[n] = 1;
      for (var h = 0; h < q.length; h++) {
        var a = q[h]; if (geo.nodes[a].pc === pc) return a;
        var nb = geo.nodes[a].nb;
        for (var i = 0; i < 6; i++) if (!seen[nb[i]]) { seen[nb[i]] = 1; q.push(nb[i]); }
      }
      return n;
    }

    function fieldStep() {
      var F = S.food, nf = new Float32Array(NN);
      for (var i = 0; i < NN; i++) {
        var nb = geo.nodes[i].nb, a = 0; for (var j = 0; j < 6; j++) a += F[nb[j]];
        nf[i] = (F[i] + P.FOOD_D * (a / 6 - F[i])) * (1 - P.FOOD_DECAY);
      }
      S.food = nf;
      for (var s = 0; s < 2; s++) for (i = 0; i < NN; i++) S.trail[s][i] *= (1 - P.TRAIL_DECAY);
    }

    /** 한 스텝. 반환: { t, notes:[{id, species, notes:[[pitch,dur,node,isHead]], z, node}], born:[], died:[], meals:[] } */
    function step() {
      var ev = { t: S.t, notes: [], born: [], died: [], meals: [] };
      var list = S.creatures.slice();
      if (P.coupled) list.sort(function (a, b) { return a.node - b.node; });
      for (var i = 0; i < list.length; i++) {
        var cr = list[i]; if (cr.dead || cr.held) continue;   // 손에 들린 생명체는 멈춘다
        R = P.coupled ? rngAt(S.t, cr.node) : rng;
        var ph = ((S.t - cr.born) % cr.period + cr.period) % cr.period, c = cr.ring[ph];
        var m0 = cr.meals;
        if (c > 0) sing(cr, c, ev);
        if (cr.meals > m0) ev.meals.push(cr.id);
        if (cr.energy >= P.EGG) {                  // 천장 — 알을 낳고 안쪽으로 돌아온다
          var nb = geo.nodes[cr.node].nb, placed = null;
          for (var j = 0; j < 6 && !placed; j++) placed = hatch(nb[(j + S.t) % 6], other(cr.species), cr.z, 0.5);
          if (placed) { cr.energy -= 0.5; cr.eggs++; ev.born.push(placed.id); }
          else cr.energy = P.EGG;
        }
        if (cr.energy <= 0) { cr.dead = true; cr.deadAt = S.t; ev.died.push(cr.id); }   // 바닥
      }
      fieldStep();
      S.creatures = S.creatures.filter(function (c) { return !c.dead || S.t - c.deadAt < 16; });
      S.t++;
      return ev;
    }

    return { state: S, geo: geo, labels: LAB, cycles: cycles, loops: loops, K: K,
             hatch: hatch, feed: feed, move: move, step: step, noteAt: noteAt,
             alive: function () { return S.creatures.filter(function (c) { return !c.dead; }); } };
  }

  var API = { create: create, buildGeo: buildGeo, W: W, H: H, S3: S3, DEF: DEF };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.TonnetzLife = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
