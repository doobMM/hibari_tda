/* sketch/metro-core.js — hibari 노선도 (Mini Metro 뼈대) 규칙. DOM 없음. 페이지 metro.html · 검증 tools/verify_sketch_metro.mjs 가 같이 쓴다.
 *
 * 규칙 한 장(2026-10-01 사용자 승인 "일단 이대로"):
 *   승객을 자기 모양(○ △ □ ☆)의 역으로 나른다. 점수 = 나른 승객 수. 한 역에 승객이 CROWD 넘게 쌓이면 그 역의 시계가 돌고, 다 돌면 끝(태워 가면 되감긴다).
 *   역은 시간이 지나며 생긴다 — 이름(음)은 hibari 모듈의 화음 순서 미 파 솔 라 시 도 | 미 파 솔 라 시 라. 승객도 점점 빨리 생긴다.
 *   노선은 끌어서 긋고 늘리고 끼워 넣는다. 끝을 첫 역에 이으면 고리 노선. 강을 건너려면 다리가 든다. 매주 열차 하나 + 선물 하나(노선·객차·다리 중).
 *   첫 노선을 긋기 전에는 시간이 흐르지 않는다(자동 재생 없음).
 * 회색 시제품(③): 소리 없음. 박에 맞춘 열차와 소리는 ④ 에서 붙인다.
 * 어려워짐 harder = 0.8: 단순한 봇의 한 판이 0.9 에서 6.8~12.5분(중앙 10.1)이라 규칙의 3~6분에 맞춰 0.8 로 낮췄다(봇 4.6~6.8분, 중앙 5.7) — 봇에 맞춘 값이다.
 * 길찾기: 모양마다 그 모양 역까지의 홉 수(여러 출발 너비 우선). 승객은 열차의 다음 역이 목적지에 더 가까우면 타고,
 *         내리는 건 목적지 모양 역에 닿거나 계속 타도 가까워지지 않을 때(갈아타기).
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var NOTES = ['미', '파', '솔', '라', '시', '도', '미', '파', '솔', '라', '시', '라'];
  var DEF = { W: 1000, H: 640, margin: 56, gap: 92, riverGap: 34, spawn0: 15, spawnMin: 6, pax0: 2.6, paxMin: 0.6, harder: 0.8,
    cap: 6, crowd: 6, fill: 30, rewind: 14, speed: 70, dwell: 0.25, per: 0.08, week: 60, lines0: 3, maxLines: 6, bridges0: 2 };
  function hyp(p, q) { return Math.hypot(q[0] - p[0], q[1] - p[1]); }
  function cross(a, b, c, d) {                              // 선분 ab 와 cd 가 엇갈리나
    function o(p, q, r) { return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]); }
    return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0; }

  function create(opt) {
    opt = opt || {}; var P = {}, k; for (k in DEF) P[k] = opt[k] != null ? opt[k] : DEF[k];
    var rng = HS.rng(opt.seed || 1), nid = 0;
    var S = { t: 0, score: 0, spawned: 0, started: false, over: false, gift: null, week: 0, stations: [], lines: [], river: [], dist: [[], [], [], []],
      spare: { lines: P.lines0, trains: 0, cars: 0, bridges: P.bridges0 }, nextStation: P.spawn0, nextPax: P.pax0, spawnEvery: P.spawn0, paxEvery: P.pax0 };
    (function river() { var a = 0.56 + 0.1 * rng(), b = rng() * 6.28;
      for (var i = 0; i <= 40; i++) { var v = i / 40; S.river.push([P.W * (a + 0.06 * Math.sin(v * 5 + b)), -30 + v * (P.H + 60)]); } })();
    function riverDist(x, y) { var m = 1e9; for (var i = 0; i + 1 < S.river.length; i++) { var p = S.river[i], q = S.river[i + 1], dx = q[0] - p[0], dy = q[1] - p[1], u = Math.max(0, Math.min(1, ((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy)));
      m = Math.min(m, Math.hypot(x - p[0] - u * dx, y - p[1] - u * dy)); } return m; }

    // ── 노선 모양: 대각선 먼저, 그다음 곧게 (45°·90° 만) ────────────────────
    function seg(a, b) { var A = S.stations[a], B = S.stations[b], dx = B.x - A.x, dy = B.y - A.y, m = Math.min(Math.abs(dx), Math.abs(dy));
      return [[A.x, A.y], [A.x + Math.sign(dx) * m, A.y + Math.sign(dy) * m], [B.x, B.y]]; }
    function segLen(p) { return hyp(p[0], p[1]) + hyp(p[1], p[2]); }
    function crossings(a, b) { var p = seg(a, b), n = 0;
      for (var i = 0; i + 1 < S.river.length; i++) if (cross(p[0], p[1], S.river[i], S.river[i + 1]) || cross(p[1], p[2], S.river[i], S.river[i + 1])) { n++; break; }
      return n; }
    function pairs(L) { var st = L.stations, out = []; for (var i = 0; i + 1 < st.length; i++) out.push([st[i], st[i + 1]]); if (L.loop && st.length > 2) out.push([st[st.length - 1], st[0]]); return out; }
    function cost(L) { return pairs(L).reduce(function (s, p) { return s + crossings(p[0], p[1]); }, 0); }

    // ── 길찾기 ──────────────────────────────────────────────────────────
    function rebuild() {
      var n = S.stations.length, adj = [], i;
      for (i = 0; i < n; i++) adj.push([]);
      S.lines.forEach(function (L) { pairs(L).forEach(function (p) { if (adj[p[0]].indexOf(p[1]) < 0) adj[p[0]].push(p[1]); if (adj[p[1]].indexOf(p[0]) < 0) adj[p[1]].push(p[0]); }); });
      for (var T = 0; T < 4; T++) { var d = [], q = [];
        for (i = 0; i < n; i++) { d.push(S.stations[i].type === T ? 0 : Infinity); if (!d[i]) q.push(i); }
        for (var h = 0; h < q.length; h++) adj[q[h]].forEach(function (v) { if (d[v] === Infinity) { d[v] = d[q[h]] + 1; q.push(v); } });
        S.dist[T] = d; }
    }

    // ── 열차 ───────────────────────────────────────────────────────────
    function next(L, i, dir) { var n = L.stations.length; if (L.loop && n > 2) return { j: ((i + dir) % n + n) % n, dir: dir };
      var j = i + dir; if (j < 0 || j >= n) { dir = -dir; j = i + dir; } return { j: j, dir: dir }; }
    function train(L, i) { var nx = next(L, i || 0, 1); return { line: L, i: i || 0, j: nx.j, dir: nx.dir, d: 0, wait: 0, pax: [], cap: P.cap }; }
    function arrive(tr) {
      var L = tr.line, si = L.stations[tr.i], st = S.stations[si], nx = next(L, tr.i, tr.dir), moved = 0;
      tr.dir = nx.dir; tr.j = nx.j; var ni = L.stations[tr.j];
      tr.pax = tr.pax.filter(function (p) {
        if (st.type === p.dest) { S.score++; moved++; return false; }
        var h = S.dist[p.dest][si], n2 = S.dist[p.dest][ni];
        if (h < Infinity && !(n2 < h)) { st.q.push(p); moved++; return false; }
        return true; });
      st.q = st.q.filter(function (p) { if (tr.pax.length >= tr.cap || !(S.dist[p.dest][ni] < S.dist[p.dest][si])) return true; tr.pax.push(p); moved++; return false; });
      tr.wait = P.dwell + P.per * moved; tr.arrived = S.t;
    }
    function move(tr, dt) {
      var L = tr.line; if (L.stations.length < 2) return;
      if (tr.wait > 0) { tr.wait -= dt; return; }
      tr.d += P.speed * dt; var len = segLen(seg(L.stations[tr.i], L.stations[tr.j]));
      if (tr.d >= len) { tr.i = tr.j; tr.d = 0; arrive(tr); }
    }
    function remap(L, before) {                             // 노선을 고친 뒤 열차를 새 번호에 맞춘다(구간이 사라졌으면 역에 세운다)
      var n = L.stations.length;
      L.trains.forEach(function (tr) { var i = L.stations.indexOf(before[tr.i]), j = L.stations.indexOf(before[tr.j]);
        var adj = i >= 0 && j >= 0 && (Math.abs(i - j) === 1 || (L.loop && n > 2 && Math.abs(i - j) === n - 1));
        if (adj) { tr.i = i; tr.j = j; tr.dir = L.loop && n > 2 ? ((j - i + n) % n === 1 ? 1 : -1) : Math.sign(j - i); }
        else { tr.i = Math.max(0, i); tr.d = 0; var nx = next(L, tr.i, tr.dir); tr.j = nx.j; tr.dir = nx.dir; } });
    }

    // ── 생기기 ──────────────────────────────────────────────────────────
    function spawnStation() {
      var n = S.stations.length, edge = n < 3 ? Math.min(P.W, P.H) * 0.28 : P.margin;
      for (var tries = 0; tries < 400; tries++) {
        var x = edge + rng() * (P.W - 2 * edge), y = edge + rng() * (P.H - 2 * edge);
        if (S.stations.some(function (s) { return Math.hypot(s.x - x, s.y - y) < P.gap; }) || riverDist(x, y) < P.riverGap) continue;
        var r = rng(), type = n < 3 ? n : S.week >= 2 && r < 0.06 ? 3 : r < 0.53 ? 0 : r < 0.83 ? 1 : 2;
        S.stations.push({ id: n, x: x, y: y, type: type, q: [], crowd: 0, note: n % NOTES.length, name: NOTES[n % NOTES.length], born: S.t });
        rebuild(); return true; }
      return false;
    }
    function spawnPax() {
      var n = S.stations.length; if (!n) return; var s = S.stations[rng() * n | 0], types = [];
      S.stations.forEach(function (st) { if (st.type !== s.type && types.indexOf(st.type) < 0) types.push(st.type); });
      if (types.length) { s.q.push({ dest: types[rng() * types.length | 0], t: S.t }); S.spawned++; }
    }
    for (k = 0; k < 3; k++) spawnStation();

    function tick(dt) {
      S.t += dt;
      if ((S.nextStation -= dt) <= 0) { spawnStation(); S.nextStation = S.spawnEvery * (0.8 + 0.4 * rng()); }
      S.nextPax -= dt; while (S.nextPax <= 0) { spawnPax(); S.nextPax += S.paxEvery * (0.6 + 0.8 * rng()); }
      S.lines.forEach(function (L) { L.trains.forEach(function (tr) { move(tr, dt); }); });
      S.stations.forEach(function (st) { st.crowd = st.q.length > P.crowd ? Math.min(1, st.crowd + dt / P.fill) : Math.max(0, st.crowd - dt / P.rewind); if (st.crowd >= 1) S.over = true; });
      var wk = Math.floor(S.t / P.week);
      if (wk > S.week) { S.week = wk; S.spare.trains++; S.spawnEvery = Math.max(P.spawnMin, S.spawnEvery * P.harder); S.paxEvery = Math.max(P.paxMin, S.paxEvery * P.harder);
        var pool = ['car', 'bridge']; if (S.lines.length + S.spare.lines < P.maxLines) pool.push('line');
        var a = pool.splice(rng() * pool.length | 0, 1)[0], b = pool[rng() * pool.length | 0]; S.gift = { options: [a, b] }; }
    }
    function step(dt) { if (!S.started || S.over || S.gift) return; var h = Math.min(dt, 0.25);
      while (h > 1e-9 && !S.over && !S.gift) { var d = Math.min(h, 0.05); h -= d; tick(d); } }

    // ── 하는 것 ─────────────────────────────────────────────────────────
    function slot() { for (var c = 0; c < P.maxLines; c++) if (!S.lines.some(function (L) { return L.color === c; })) return c; return -1; }
    /** 새 노선: 역 번호 목록(2개 이상, 서로 다름). 다리가 모자라면 false */
    function newLine(ids) {
      if (S.spare.lines < 1 || !ids || ids.length < 2 || new Set(ids).size !== ids.length) return false;
      var L = { color: slot(), stations: ids.slice(), loop: false, trains: [] }, c = cost(L); if (c > S.spare.bridges) return false;
      S.spare.lines--; S.spare.bridges -= c; L.bridges = c; L.trains.push(train(L, 0)); S.lines.push(L); S.started = true; rebuild(); return L;
    }
    /** 늘리기: end = 'tail'(끝에서) | 'head'(처음에서), ids = 끌며 지난 역들(끝 역에서 가까운 차례). 다른 끝 역에 닿으면 고리 */
    function extend(L, end, ids) {
      if (!L || L.loop || !ids || !ids.length) return false;
      var before = L.stations.slice(), st = before.slice(), other = end === 'tail' ? st[0] : st[st.length - 1], loop = false, add = [];
      for (var i = 0; i < ids.length; i++) { if (ids[i] === other && st.length + add.length >= 3) { loop = true; break; } if (st.indexOf(ids[i]) >= 0 || add.indexOf(ids[i]) >= 0) return false; add.push(ids[i]); }
      st = end === 'tail' ? st.concat(add) : add.slice().reverse().concat(st);
      var T = { stations: st, loop: loop }, c = cost(T) - L.bridges; if (c > S.spare.bridges) return false;
      L.stations = st; L.loop = loop; S.spare.bridges -= c; L.bridges += c; remap(L, before); rebuild(); return true;
    }
    /** 끼워 넣기: 노선 L 의 k 번째 구간(역 k → k+1, 고리면 마지막 → 처음)에 역 id 를 넣는다 */
    function insert(L, k, id) {
      if (!L || L.stations.indexOf(id) >= 0) return false;
      var before = L.stations.slice(), st = before.slice(); st.splice(k + 1, 0, id);
      var T = { stations: st, loop: L.loop }, c = cost(T) - L.bridges; if (c > S.spare.bridges) return false;
      L.stations = st; S.spare.bridges -= c; L.bridges += c; remap(L, before); rebuild(); return true;
    }
    function removeLine(L) {
      var i = S.lines.indexOf(L); if (i < 0) return false;
      L.trains.forEach(function (tr, k) { var st = S.stations[L.stations[tr.i]]; tr.pax.forEach(function (p) { if (st.type === p.dest) S.score++; else st.q.push(p); });
        if (k > 0) S.spare.trains++; S.spare.cars += Math.round((tr.cap - P.cap) / P.cap); });
      S.lines.splice(i, 1); S.spare.lines++; S.spare.bridges += L.bridges; rebuild(); return true;
    }
    function addTrain(L) { if (!L || S.spare.trains < 1 || L.stations.length < 2) return false; S.spare.trains--; L.trains.push(train(L, Math.floor(L.stations.length / 2))); return true; }
    function addCar(L) { if (!L || S.spare.cars < 1 || !L.trains.length) return false; S.spare.cars--;
      L.trains.reduce(function (a, b) { return b.cap < a.cap ? b : a; }).cap += P.cap; return true; }
    function chooseGift(k) { if (!S.gift) return false; var g = S.gift.options[k]; if (!g) return false;
      if (g === 'line') S.spare.lines++; else if (g === 'car') S.spare.cars++; else S.spare.bridges++; S.gift = null; return g; }
    function trainPos(tr) {
      var L = tr.line, p = seg(L.stations[tr.i], L.stations[tr.j]), l1 = hyp(p[0], p[1]), d = Math.min(tr.d, segLen(p)), a, b, u;
      if (d <= l1) { a = p[0]; b = p[1]; u = l1 ? d / l1 : 0; } else { a = p[1]; b = p[2]; var l2 = hyp(a, b); u = l2 ? (d - l1) / l2 : 0; }
      if (a[0] === b[0] && a[1] === b[1]) { a = p[1]; b = p[2]; }
      return { x: a[0] + (b[0] - a[0]) * u, y: a[1] + (b[1] - a[1]) * u, a: Math.atan2(b[1] - a[1], b[0] - a[0]) };
    }
    return { state: S, P: P, step: step, newLine: newLine, extend: extend, insert: insert, removeLine: removeLine, addTrain: addTrain, addCar: addCar,
      chooseGift: chooseGift, seg: seg, pairs: pairs, trainPos: trainPos, crossings: crossings };
  }

  var API = { create: create, DEF: DEF, NOTES: NOTES };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSMetro = API;
})(typeof window !== 'undefined' ? window : globalThis);
