/* sketch/relay-core.js — 잇기 (③ 주고받기 · 모듈 시계 판) 규칙. DOM 없음. 페이지 relay.html 과 검증 tools/verify_sketch_relay.mjs 가 같이 쓴다.
 *
 * 판     data/relay_clock.json (experiments/export_relay_clock.py). 칸 = 모듈 자리 8(2박씩) × 곡의 띠 4(안쪽 = 곡의 처음 … 바깥 = 끝).
 *        소리 없는 칸(두 손이 함께 쉬는 곳)은 빠져 있다. 이웃 = 맞닿은 칸(시계 방향 · 반대 · 바깥 · 안).
 *        구멍 = 가운데(모듈 한 바퀴) + 안쪽의 빈 칸. 맨 안 띠의 빈 칸은 가운데 구멍에 붙고, 맨 바깥 띠의 빈 칸은 가장자리의 홈이다.
 * 한 수  내가 칸 하나를 누른다 → 곧바로 운다. hibari 가 이어진 칸 하나로 대답한다(페이지가 한 박 뒤에 울린다).
 *        대답은 곡이 흐르는 쪽으로 기운다: 무게 = 곡에서 그 칸 다음으로 넘어간 몫(가장 많은 쪽 = 1) + 바닥 FLOOR.
 *        hibari 는 내가 방금 떠난 칸으로 되돌아가지 않는다(다른 길이 있으면) — 한 수가 아무것도 바꾸지 않는 일이 없게(검증 Q1, 2026-10-01).
 *        이어지지 않은 칸을 누르면 거기서 새 줄이 시작된다.
 * 닫힘   줄이 앞의 칸으로 돌아오면 고리가 닫힌다. 고리가 구멍을 감으면(감김수 ≠ 0) 울림 고리가 되어 되풀이되고, 아니면 스러진다(줄이 고리가 시작된 칸으로 줄어든다).
 *        한 걸음 되돌아가기(A→B→A)도 줄이 줄어드는 것이다.
 * 판 12  한 번 누름 = 한 번의 주고받기. 손을 떼면 울림 고리가 도는 것 말고 바뀌는 것이 없다. 되돌리기는 한 수 전 그대로.
 *        누르기 전에 보인다: preview(칸) = 'ring' | 'fade' | 'back' | 'go' | 'new'.
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var FLOOR = 0.12;

  /** 시계 판 → { N, nb, w(p,q), wind(loop), pos, holes, dir(p,q) }. 칸 번호 = 띠 × 자리수 + 자리. */
  function clockBoard(D) {
    var S = D.sectors, R = D.rings, N = S * R, gone = {}, nb = [], pos = [], holes = [[0, 0]], W = {}, i;
    D.silent.forEach(function (k) { gone[k] = 1; });
    for (i = 0; i < N; i++) { var th = -Math.PI / 2 + (i % S + 0.5) * 2 * Math.PI / S, rad = 1 + Math.floor(i / S); pos.push([rad * Math.cos(th), rad * Math.sin(th)]); }
    D.silent.forEach(function (k) { var r = Math.floor(k / S); if (r > 0 && r < R - 1) holes.push(pos[k]); });   // 안쪽 빈 칸만 따로 센다
    for (i = 0; i < N; i++) { var s = i % S, r = Math.floor(i / S), c = [];
      if (!gone[i]) [[(s + 1) % S, r], [(s + S - 1) % S, r], [s, r + 1], [s, r - 1]].forEach(function (q) { if (q[1] >= 0 && q[1] < R && !gone[q[1] * S + q[0]]) c.push(q[1] * S + q[0]); });
      nb.push(c); }
    var sc = {}; D.succ.forEach(function (e) { sc[e[0] * N + e[1]] = e[2]; });
    nb.forEach(function (c, p) { var m = 0; c.forEach(function (q) { m = Math.max(m, sc[p * N + q] || 0); });
      c.forEach(function (q) { W[p * N + q] = (m ? (sc[p * N + q] || 0) / m : 0) + FLOOR; }); });
    function wind(loop) { var hit = [];
      holes.forEach(function (h, k) { var a = 0;
        for (var j = 0; j + 1 < loop.length; j++) { var u = pos[loop[j]], v = pos[loop[j + 1]], ux = u[0] - h[0], uy = u[1] - h[1], vx = v[0] - h[0], vy = v[1] - h[1];
          a += Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy); }
        if (Math.round(a / (2 * Math.PI))) hit.push(k); });
      return hit; }
    function dir(p, q) { var sp = p % S, sq = q % S, rp = Math.floor(p / S), rq = Math.floor(q / S);   // 'cw' 시계 방향 · 'ccw' · 'out' 바깥 · 'in' 안
      return rp === rq ? (sq === (sp + 1) % S ? 'cw' : 'ccw') : (rq > rp ? 'out' : 'in'); }
    return { N: N, nb: nb, w: function (p, q) { return W[p * N + q] || FLOOR; }, wind: wind, pos: pos, holes: holes, dir: dir, gone: gone, S: S, R: R };
  }

  function create(B, opt) {
    opt = opt || {};
    var rng = HS.rng(opt.seed || 1), S = { path: [], by: [], rings: [], t: 0, hist: [] };
    function linked(a, b) { return B.nb[a].indexOf(b) >= 0; }
    function judge(path, p) {                   // p 를 줄 끝에 이으면 무슨 일이 나나
      if (!path.length || !linked(path[path.length - 1], p)) return { kind: 'new' };
      var j = path.lastIndexOf(p);
      if (j < 0) return { kind: 'go' };
      if (j === path.length - 2) return { kind: 'back', j: j };
      var loop = path.slice(j).concat([p]), hit = B.wind(loop);
      return { kind: hit.length ? 'ring' : 'fade', j: j, loop: loop.slice(0, -1), holes: hit };
    }
    function apply(p, who, ev) {
      var r = judge(S.path, p); r.who = who; r.place = p;
      if (r.kind === 'new') { S.path = [p]; S.by = [who]; }
      else if (r.kind === 'go') { S.path.push(p); S.by.push(who); }
      else if (r.kind === 'back' || r.kind === 'fade') { S.path = S.path.slice(0, r.j + 1); S.by = S.by.slice(0, r.j + 1); }
      else { S.rings.push({ places: r.loop, by: S.by.slice(r.j).concat([who]).slice(0, r.loop.length), holes: r.holes, t0: S.t }); S.path = [p]; S.by = [who]; }
      ev.push(r); return r;
    }
    function answer(left) {                     // hibari: 줄 끝의 이웃 하나 — 곡이 흐르는 쪽으로 기운 제비. 방금 온 칸·내가 떠난 칸은 피한다
      var e = S.path[S.path.length - 1], prev = S.path.length > 1 ? S.path[S.path.length - 2] : -1;
      var cand = B.nb[e].filter(function (q) { return q !== prev && q !== left; }); if (!cand.length) cand = B.nb[e].slice(); if (!cand.length) return -1;
      var w = cand.map(function (q) { return B.w(e, q); }), s = w.reduce(function (a, b) { return a + b; }, 0), x = rng() * s;
      for (var k = 0; k < cand.length; k++) { x -= w[k]; if (x <= 0) return cand[k]; }
      return cand[cand.length - 1];
    }
    function keep() { S.hist.push(JSON.stringify([S.path, S.by, S.rings])); if (S.hist.length > 200) S.hist.shift(); }

    /** 한 수: 내 칸 p → { mine, answer, events[] }. events 의 kind 는 new · go · back · fade · ring */
    function press(p) {
      if (!(p >= 0 && p < B.N) || B.gone[p]) return null;
      keep(); var left = S.path.length ? S.path[S.path.length - 1] : -1, ev = [];
      apply(p, 'me', ev);
      var q = answer(left); if (q >= 0) apply(q, 'hibari', ev);
      return { mine: p, answer: q, events: ev };
    }
    function undo() { var h = S.hist.pop(); if (!h) return false; h = JSON.parse(h); S.path = h[0]; S.by = h[1]; S.rings = h[2]; return true; }
    function unring(k) { if (!(k >= 0 && k < S.rings.length)) return false; keep(); S.rings.splice(k, 1); return true; }
    /** 칸 하나만큼(2박) 시간이 간다: 울림 고리마다 제 칸 하나씩 → [{ring, place}] */
    function step() { var out = S.rings.map(function (r, k) { return { ring: k, place: r.places[(S.t - r.t0) % r.places.length] }; }); S.t++; return out; }
    function options() { return S.path.length ? B.nb[S.path[S.path.length - 1]].slice() : []; }
    return { press: press, undo: undo, unring: unring, step: step, options: options, preview: function (p) { return judge(S.path, p).kind; }, state: S, board: B };
  }

  var API = { create: create, clockBoard: clockBoard };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSRelay = API;
})(typeof window !== 'undefined' ? window : globalThis);
