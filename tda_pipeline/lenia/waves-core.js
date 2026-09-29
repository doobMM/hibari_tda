/* waves-core.js — 종달새와 문어 2판: 칸이 생명을 담는 오토마타 (docs/tonnetz_lenia_spec.md §9)
 * 페이지(waves.html)와 검증(tools/verify_waves.mjs)이 **같은 이 파일**을 돌린다.
 *
 * 앞으로와 거꾸로가 같은 식을 쓴다 — 사용자의 설계  timeflow = intra + rate × inter  (한 손 안 + rate × 두 손 사이, lag 1)
 *   · 칸 사이 전도  = 그 rate 에서 PH 가 보는 두 음의 거리(dist_grid)를 뒤집은 것   ← 앞으로: 이론이 파도를 움직인다
 *   · rate          = 종달새(오른손)와 문어(왼손) 사이의 거리                         ← 거꾸로: 손으로 rate 를 쓴다
 *   · 발견          = 목소리의 행에서 켜진 고리 → 바코드(vine)의 지금 rate 칸을 채운다
 * 세계 — Tonnetz 삼각격자를 주기 (0,12)·(24,−12) 로 감은 토러스. 288칸(음이름마다 24칸), 20.78 × 12.
 *   칸의 음 = 그 음이름의 hibari 음 중 음역 지형(y: 낮음→높음→낮음)에 가장 가까운 것. 검은 건반 칸은 소리가 없다.
 * 칸의 상태 — 확률 Greenberg–Hastings: φ 0 쉼 · 1 켜짐 · 2..R 불응. 켜질 확률 = σ(STEEP·(입력 − θ − 피로)).
 *   전체가 확률 셀룰러 오토마타 = 배치 위의 Markov 연쇄. 결합 모드면 칸마다 (seed, t, 칸) 로 시드한 균등 난수.
 * 생명체 — 파도의 원천 = 두 손
 *   종달새(오른손): 제 모듈 32 안에서 8스텝마다 제 칸 + 이웃 6칸을 켠다 → 동심 파문
 *   문어  (왼손): 제 모듈 33 안에서 8스텝마다 **한 방향**으로 3칸을 켜고 방향을 돌린다 → 한쪽이 열린 파도가 말려 나선 팔
 *   목소리: 제 손의 리듬 고리(onset 수)로 운다. 음 = 주변 4걸음 안 **그 순간 전도로 건너와** 켜진 음 → 고리 활성도 → τ →
 *           그 rate 에 살아 있는 고리만 → 한 행 → Algorithm 1 (1판 V6: 8스텝 창은 고리를 과하게 켜 소속 분포로 쏠렸다)
 * 되먹임 — 강화: 켜진 음 → 켜진 고리 → 그 고리 변의 전도 가산 · 균형: 불응기 + 피로 + 원천의 수명
 */
(function (root) {
  'use strict';
  var S3 = Math.sqrt(3) / 2;
  var DIRS = [[1, 0, 7], [-1, 0, 5], [0, 1, 4], [0, -1, 8], [1, -1, 3], [-1, 1, 9]];
  var PA = 2, PB = 2;                              // 주기 (0,12)·(24,−12) — 288칸, 20.78 × 12
  var W = 12 * PB * S3, H = 6 * PA;

  function reduce(c, r) {
    var C = 12 * PB, Rr = 6 * PA, b = Math.floor(c / C); c -= C * b; r += 6 * PB * b;
    r = ((r % Rr) + Rr) % Rr; return [c, r];
  }
  function buildGeo() {
    var nodes = [], idx = {}, C = 12 * PB, Rr = 6 * PA;
    for (var c = 0; c < C; c++) for (var r = 0; r < Rr; r++) {
      idx[c * Rr + r] = nodes.length;
      nodes.push({ c: c, r: r, pc: (7 * c + 4 * r) % 12, x: S3 * c, y: (((0.5 * c + r) % H) + H) % H, nb: [] });
    }
    nodes.forEach(function (n) {
      n.nb = DIRS.map(function (d) { var q = reduce(n.c + d[0], n.r + d[1]); return idx[q[0] * Rr + q[1]]; });
    });
    return { W: W, H: H, nodes: nodes, DIRS: DIRS };
  }
  function wrap(v, P) { return v - P * Math.round(v / P); }

  var DEF = {
    R: 7,                                  // 켜짐 1 + 불응 6 → 8스텝 = 한 마디에 한 번
    C_LO: 0.8, C_HI: 1.6,                  // 전도 = C_LO + (C_HI − C_LO) · (1 − 거리/그 rate 의 최대 거리) — 이웃 하나로도 대개 건너간다
    C_BLACK: 0.85, BONUS: 0.45, THETA: 1.0, STEEP: 14,
    FAT_MAX: 10, FAT_DECAY: 0.04, FATIGUE: 0.07,
    TAU: 0.35, HEAR: 4,                    // 목소리가 듣는 반경 (격자 걸음) — 원천이 직접 켠 칸은 듣지 않는다(전도로 건너온 파도만)
    LIFE: 24,                              // 원천의 수명(모듈). 누르면 다시 찬다
    D0: 8.0,                               // 두 손 거리 D0 이상이면 rate 0, 붙으면 1.5
    CAP: 6,
    coupled: false, shuffleDist: false, fixedRate: null
  };

  function create(data, opts) {
    opts = opts || {};
    var P = {}; for (var k in DEF) P[k] = (k in opts) ? opts[k] : DEF[k];
    var G = opts.algo1 || root.GenerationAlgo1;
    var SEED = opts.seed == null ? 1 : opts.seed;
    var rng = G.makeRng(SEED);
    function uAt(t, i, salt) {                   // 결합 모드: (seed, t, 칸, 용도) → 균등 난수 하나
      var h = (SEED ^ Math.imul(t + 1, 0x9E3779B1) ^ Math.imul(i + 1, 0x85EBCA77) ^ Math.imul(salt + 1, 0xC2B2AE3D)) >>> 0;
      h = Math.imul(h ^ (h >>> 16), 0x7FEB352D) >>> 0; h = Math.imul(h ^ (h >>> 15), 0x846CA68B) >>> 0;
      return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    }
    var geo = buildGeo(), NN = geo.nodes.length, LAB = data.labels, NL = LAB.length;
    var cycles = data.cycles, K = cycles.length, loops = data.loops.map(function (l) { return l.order; });
    var cnt = {}; cycles.forEach(function (c) { c.forEach(function (u) { cnt[u] = (cnt[u] || 0) + 1; }); });
    var RAR = []; for (var u = 0; u < NL; u++) RAR.push(cnt[u] ? 1 / cnt[u] : 0);
    var WSUM = cycles.map(function (c) { return c.reduce(function (a, x) { return a + RAR[x]; }, 0); });

    // ── vine: 고리 k 가 rate r 에 살아 있나 (0.01 격자) ──────────────────────
    var alive = [];                                   // alive[k][ri], ri = round(r*100)
    data.vines.forEach(function (v) {
      var a = new Uint8Array(151);
      v.rates.forEach(function (iv) { for (var x = Math.round(iv[0] * 100); x <= Math.round(iv[1] * 100); x++) a[x] = 1; });
      alive.push(a);
    });
    // ── 거리 격자 (rate 0.0~1.5, 0.1 간격) — V4 대조군이면 음 쌍을 섞는다 ─────────
    var GR = []; for (var gi = 0; gi <= 15; gi++) GR.push(data.dist_grid[(gi / 10).toFixed(1)]);
    if (P.shuffleDist) {
      var rs = G.makeRng(4242 + SEED), perm = []; for (var i0 = 0; i0 < NL; i0++) perm.push(i0);
      for (var j0 = NL - 1; j0 > 0; j0--) { var q0 = Math.floor(rs() * (j0 + 1)); var t0 = perm[j0]; perm[j0] = perm[q0]; perm[q0] = t0; }
      GR = GR.map(function (M) { return M.map(function (row, a) { return row.map(function (_, b) { return M[perm[a]][perm[b]]; }); }); });
    }
    var GMAX = GR.map(function (M) { var m = 0; M.forEach(function (row) { row.forEach(function (x) { if (x > m) m = x; }); }); return m; });

    // ── 칸의 음 (음역 지형) ─────────────────────────────────────────────
    var lo = 1e9, hi = -1e9; LAB.forEach(function (l) { lo = Math.min(lo, l.pitch); hi = Math.max(hi, l.pitch); });
    var note = new Int16Array(NN), terrain = new Float32Array(NN);
    for (var n = 0; n < NN; n++) {
      var nd = geo.nodes[n], target = lo + (hi - lo) * (1 - Math.cos(2 * Math.PI * nd.y / H)) / 2, best = -1, bd = 1e9;
      terrain[n] = target;
      for (var i2 = 0; i2 < NL; i2++) {
        if (LAB[i2].pc !== nd.pc || !cnt[i2]) continue;
        var dd = Math.abs(LAB[i2].pitch - target) + (LAB[i2].dur === 2 ? 0 : 0.2);
        if (dd < bd) { bd = dd; best = i2; }
      }
      note[n] = best;
    }
    // 격자 변 (칸 n, 방향 d) 을 품은 고리들 — 순회에서 이웃한 두 음이 이웃 칸에 놓인 곳
    var pairCyc = {}, edgeCyc = [];
    loops.forEach(function (o, k2) {
      if (!o) return;
      for (var a = 0; a < o.length; a++) {
        var x = o[a], y = o[(a + 1) % o.length];
        (pairCyc[x * 64 + y] = pairCyc[x * 64 + y] || []).push(k2); (pairCyc[y * 64 + x] = pairCyc[y * 64 + x] || []).push(k2);
      }
    });
    for (n = 0; n < NN; n++) for (var d = 0; d < 6; d++) {
      var m = geo.nodes[n].nb[d];
      edgeCyc.push(note[n] >= 0 && note[m] >= 0 ? (pairCyc[note[n] * 64 + note[m]] || []) : []);
    }
    // 격자 걸음 거리 (목소리가 듣는 반경용) — 칸마다 HEAR 걸음 안의 칸 목록
    var near = [];
    for (n = 0; n < NN; n++) {
      var seen = {}, fr = [n], out = [n]; seen[n] = 1;
      for (var s = 0; s < P.HEAR; s++) {
        var nx = [];
        fr.forEach(function (a) { geo.nodes[a].nb.forEach(function (b) { if (!seen[b]) { seen[b] = 1; nx.push(b); out.push(b); } }); });
        fr = nx;
      }
      near.push(out);
    }

    var pool = new G.NodePool({ labels: LAB.map(function (l) {
      return { label: l.li + 1, label_idx: l.li, pitch: l.pitch, dur: l.dur, count: l.count };
    }), rng: rng });
    var mgr = new G.CycleSetManager({ cycles: cycles.map(function (c, i3) { return { cycle_idx: i3, note_labels_0idx: c }; }), K: K });
    var HANDS = data.hands;

    // ── 상태 ────────────────────────────────────────────────────────────
    var S = { t: 0, phi: new Uint8Array(NN), fat: new Uint8Array(NN), stim: new Float32Array(NN), bonus: new Uint8Array(NN * 6),
              org: new Uint8Array(NN), stimOrg: new Uint8Array(NN),     // 어느 손의 파도인가 (1 오른손, 2 왼손) — 그림용
              stimmed: new Uint8Array(NN),                               // 이 스텝에 원천이 직접 켠 칸
              srcs: [], nextId: 1, rate: 0, found: new Uint8Array(K * 151), P: P, geo: geo, note: note, terrain: terrain };

    function rateNow() {
      if (P.fixedRate != null) return P.fixedRate;
      var best = Infinity;
      S.srcs.forEach(function (a) { if (a.hand !== 1) return;
        S.srcs.forEach(function (b) { if (b.hand !== 2) return;
          var A = geo.nodes[a.node], B = geo.nodes[b.node], dx = wrap(A.x - B.x, W), dy = wrap(A.y - B.y, H);
          best = Math.min(best, Math.sqrt(dx * dx + dy * dy)); }); });
      return best === Infinity ? 0 : 1.5 * Math.max(0, 1 - best / P.D0);
    }
    function condAt(a, b, r) {                   // 두 음 사이 전도 — 거리 격자를 rate 로 선형 보간
      if (a < 0 || b < 0) return P.C_BLACK;
      var x = Math.min(15, Math.max(0, r * 10)), i = Math.floor(x), f = x - i, j = Math.min(15, i + 1);
      var dd = GR[i][a][b] * (1 - f) + GR[j][a][b] * f, mx = GMAX[i] * (1 - f) + GMAX[j] * f;
      return P.C_LO + (P.C_HI - P.C_LO) * Math.max(0, 1 - dd / mx);
    }
    var COND = new Float32Array(NN * 6), condRate = -1;
    function refreshCond(r) {
      if (Math.abs(r - condRate) < 0.005) return;
      condRate = r;
      for (var n2 = 0; n2 < NN; n2++) for (var d2 = 0; d2 < 6; d2++) COND[n2 * 6 + d2] = condAt(note[n2], note[geo.nodes[n2].nb[d2]], r);
    }

    /** 원천. hand 1 = 종달새(32, 동심), 2 = 문어(33, 회전). */
    function source(n, hand, dir) {
      for (var i = 0; i < S.srcs.length; i++) if (S.srcs[i].node === n) { S.srcs[i].life = P.LIFE; return S.srcs[i]; }
      if (S.srcs.length >= P.CAP) return null;
      var h = HANDS[hand === 1 ? 'lark' : 'octopus'];
      var src = { id: S.nextId++, hand: hand, per: h.period, ring: h.ring, node: n, born: S.t, life: P.LIFE, dir: dir || 0,
                  hist: [], row: new Int8Array(K) };
      S.srcs.push(src); return src;
    }
    function moveSource(src, n) { src.node = n; }
    function removeSource(src) { var i = S.srcs.indexOf(src); if (i >= 0) S.srcs.splice(i, 1); }
    function poke(n, amt) { S.stim[n] += amt == null ? 2 : amt; }

    function voiceRow(src, out) {                // 제 주변 HEAR 걸음 안 그 순간 켜진 음 → 그 rate 에 살아 있는 고리의 행
      var s = {}, nn = near[src.node], ri = Math.round(S.rate * 100);
      for (var i = 0; i < nn.length; i++) if (S.phi[nn[i]] === 1 && !S.stimmed[nn[i]] && note[nn[i]] >= 0) s[note[nn[i]]] = 1;
      var f = 0;
      for (var c = 0; c < K; c++) {
        var on = 0;
        if (alive[c][ri]) {
          var acc = 0, cs = cycles[c];
          for (var j = 0; j < cs.length; j++) if (s[cs[j]]) acc += RAR[cs[j]];
          on = WSUM[c] > 0 && acc / WSUM[c] >= P.TAU ? 1 : 0;
        }
        out[c] = on; f += on;
      }
      return f;
    }

    /** 한 스텝. 반환 { t, rate, fired:[칸], voices:[{id, hand, notes:[[pitch,dur,칸]], rows}], found:[[k, ri]] } */
    function step() {
      var t = S.t, phi = S.phi, next = new Uint8Array(NN), fired = [], ev = { t: t, voices: [], found: [], fired: fired };
      S.rate = rateNow(); ev.rate = S.rate; refreshCond(S.rate); S.stimmed.fill(0);
      // 원천의 자극
      for (var i = S.srcs.length - 1; i >= 0; i--) {
        var src = S.srcs[i], ph = (t - src.born) % src.per;
        if (ph === 0 && t > src.born) { src.life--; if (src.life <= 0) { S.srcs.splice(i, 1); continue; } }
        if (ph < 32 && ph % 8 === 0) {
          var nb = geo.nodes[src.node].nb;
          if (src.hand === 1) { S.stim[src.node] += 3; S.stimOrg[src.node] = 1;
            nb.forEach(function (m2) { S.stim[m2] += 3; S.stimOrg[m2] = 1; }); }
          else {                                  // 한 방향으로 3칸 — 한쪽이 열린 파도
            var d0 = src.dir % 6, m3 = nb[d0], m4 = geo.nodes[m3].nb[d0];
            S.stim[src.node] += 3; S.stim[m3] += 3; S.stim[m4] += 3; S.stimOrg[src.node] = S.stimOrg[m3] = S.stimOrg[m4] = 2;
            S.stim[nb[(d0 + 3) % 6]] = -9;        // 뒤쪽은 막는다
            src.dir = (src.dir + 1) % 6;
          }
        }
      }
      // 칸 갱신
      for (var n2 = 0; n2 < NN; n2++) {
        var p = phi[n2];
        if (p >= 1) { next[n2] = p >= P.R ? 0 : p + 1; continue; }
        var E = S.stim[n2], og = S.stimOrg[n2], ogw = S.stim[n2] > 0 ? 99 : 0;
        for (var d3 = 0; d3 < 6; d3++) {
          var mm = geo.nodes[n2].nb[d3]; if (phi[mm] !== 1) continue;
          var cc = COND[n2 * 6 + d3] + (S.bonus[n2 * 6 + d3] ? P.BONUS : 0);
          E += cc; if (cc > ogw) { ogw = cc; og = S.org[mm]; }
        }
        if (E <= 0) continue;
        var pr = 1 / (1 + Math.exp(-P.STEEP * (E - P.THETA - P.FATIGUE * S.fat[n2])));
        if ((P.coupled ? uAt(t, n2, 0) : rng()) < pr) { next[n2] = 1; fired.push(n2); S.org[n2] = og; }
      }
      for (n2 = 0; n2 < NN; n2++) {
        if (next[n2] === 1) S.fat[n2] = Math.min(P.FAT_MAX, S.fat[n2] + 1);
        else if (S.fat[n2] > 0 && (P.coupled ? uAt(t, n2, 1) : rng()) < P.FAT_DECAY) S.fat[n2]--;
        if (S.stim[n2] > 0 && next[n2] === 1) S.stimmed[n2] = 1;
        S.stim[n2] = 0; S.stimOrg[n2] = 0;
      }
      S.phi = next;
      // 목소리 — 제 손의 리듬으로, Algorithm 1
      S.bonus.fill(0);
      var ri = Math.round(S.rate * 100);
      var order = S.srcs.slice().sort(function (a, b) { return a.node - b.node; });
      for (i = 0; i < order.length; i++) {
        var sv = order[i], phs = (t - sv.born) % sv.per, c = sv.ring[phs] || 0;
        var rows = voiceRow(sv, sv.row);
        for (var kk = 0; kk < K; kk++) if (sv.row[kk] && !S.found[kk * 151 + ri]) { S.found[kk * 151 + ri] = 1; ev.found.push([kk, ri]); }
        markBonus(sv.row);
        if (!c || !rows) continue;
        var v = new Int8Array(8 * K);
        for (var c2 = 0; c2 < K; c2++) v[c2] = sv.row[c2];
        for (var w2 = 1; w2 < 8; w2++) v.copyWithin(w2 * K, 0, K);
        var il = new Int32Array(8); il[0] = c;
        var R = P.coupled ? G.makeRng((Math.floor(uAt(t, sv.node, 2) * 4294967296) >>> 0) || 1) : rng;
        var res = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen: il, overlap: { T: 8, K: K, values: v }, rng: R });
        var notes = res.notes.map(function (x) { return [x[1], x[2] - x[0], litCell(sv.node, x[1])]; });
        sv.hist.push({ t: t, n: notes.length }); if (sv.hist.length > 300) sv.hist.shift();
        ev.voices.push({ id: sv.id, hand: sv.hand, notes: notes, rows: rows });
      }
      S.t++;
      return ev;
    }
    function markBonus(row) {                    // 켜진 고리의 변 → 다음 스텝 전도 가산 (강화 회로)
      for (var e = 0; e < edgeCyc.length; e++) {
        var ec = edgeCyc[e];
        for (var q = 0; q < ec.length; q++) if (row[ec[q]]) { S.bonus[e] = 1; break; }
      }
    }
    function litCell(n0, pitch) {                // 그 음이 울릴 칸 — 제 주변에서 같은 음, 없으면 같은 음이름
      var nn = near[n0], pcHit = -1;
      for (var i = 0; i < nn.length; i++) {
        var a = nn[i]; if (note[a] >= 0 && LAB[note[a]].pitch === pitch) return a;
        if (pcHit < 0 && geo.nodes[a].pc === pitch % 12) pcHit = a;
      }
      return pcHit >= 0 ? pcHit : n0;
    }

    return { state: S, geo: geo, labels: LAB, cycles: cycles, K: K, note: note, terrain: terrain, vines: data.vines,
             alive: alive, source: source, moveSource: moveSource, removeSource: removeSource, poke: poke, step: step,
             rateNow: rateNow, lit: function () { var a = 0; for (var i = 0; i < NN; i++) if (S.phi[i] === 1) a++; return a; } };
  }

  var API = { create: create, buildGeo: buildGeo, W: W, H: H, S3: S3, DEF: DEF };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.TonnetzWaves = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
