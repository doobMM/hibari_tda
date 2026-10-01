/* sketch/lifeloop-core.js — 살아 있는 고리: Lenia 생명체의 구멍(H₁)이 hibari 지도의 고리를 켠다
 * 페이지(sketch/lifeloop.html)와 판정기(tools/verify_lifeloop.mjs)가 같은 파일을 돈다. DOM 없음.
 *
 *  세계  64×64 토러스 Lenia. 생명체 = Chan(2019) 오비움을 0.7배로 줄인 모양(R=9) — 줄인 칸을 먼저 만들고 90°씩 돌린다
 *        (원본을 돌리며 줄이면 180° 쪽 표본이 달라져 바로 죽었다 — 2026-10-01 측정).
 *  구멍  높은 값 집합의 구멍 = 낮은 값부터 채우는 합집합-찾기에서 '가장 큰 빈 땅'(같은 바닥이면 큰 쪽이 형)에 합쳐지기 전의 성분.
 *        깊이 = 테두리 고개 − 바닥 (지속). 판 위 생명체 모양의 위상이다 — 음과 무관하게 생긴다.
 *  소리  구멍을 감싼 고리(지도 위 닫힌 다각형) 하나가 켜지고 **그 고리를 연주한다** — 짝수 박 = 고리의 음 넷까지 화음,
 *        홀수 박 = 고리를 따라 한 음씩(아르페지오, 자리 = 박 번호라 상태가 없다). 고르는 순서: **내가 그은 고리가 먼저**(가장 최근 것),
 *        없으면 hibari 고리 가운데 **가장 안쪽(넓이가 가장 작은) 고리**. 고리 밖이면 가장 가까운 음 하나(작게). 세기 = 구멍 깊이.
 *        ⚠ 처음엔 Algorithm 1 처럼 겹친 고리들의 공통 음(교집합)을 골랐다 — 그러자 이용자가 hibari 고리 위에 그은 고리가
 *        공통 음을 바꾸지 못해 소리가 그대로였다(같은 판 두 갈래, 120박 중 달라진 박 0, 2026-10-01). 안쪽 고리 규칙으로 바꿔도 크게 그은
 *        고리는 더 작은 hibari 고리에 져서 구멍이 7박 들어가는 동안 1박만 달라졌다 → 내가 그은 고리를 먼저 부른다. 그래도 0박이었다 —
 *        고리 안에서 '구멍에 가까운 음'을 고르면 가까운 음으로 그은 고리는 원래 고리와 같은 음을 낸다(소리를 정한 건 고리가 아니라 자리).
 *        그래서 고리 자체를 연주한다.
 */
(function (root) {
  'use strict';
  var ORB = [[0,0,0,0,0,0,0.1,0.14,0.1,0,0,0.03,0.03,0,0,0.3,0,0,0,0],[0,0,0,0,0,0.08,0.24,0.3,0.3,0.18,0.14,0.15,0.16,0.15,0.09,0.2,0,0,0,0],[0,0,0,0,0,0.15,0.34,0.44,0.46,0.38,0.18,0.14,0.11,0.13,0.19,0.18,0.45,0,0,0],[0,0,0,0,0.06,0.13,0.39,0.5,0.5,0.37,0.06,0,0,0,0.02,0.16,0.68,0,0,0],[0,0,0,0.11,0.17,0.17,0.33,0.4,0.38,0.28,0.14,0,0,0,0,0,0.18,0.42,0,0],[0,0,0.09,0.18,0.13,0.06,0.08,0.26,0.32,0.32,0.27,0,0,0,0,0,0,0.82,0,0],[0.27,0,0.16,0.12,0,0,0,0.25,0.38,0.44,0.45,0.34,0,0,0,0,0,0.22,0.17,0],[0,0.07,0.2,0.02,0,0,0,0.31,0.48,0.57,0.6,0.57,0,0,0,0,0,0,0.49,0],[0,0.59,0.19,0,0,0,0,0.2,0.57,0.69,0.76,0.76,0.49,0,0,0,0,0,0.36,0],[0,0.58,0.19,0,0,0,0,0,0.67,0.83,0.9,0.92,0.87,0.12,0,0,0,0,0.22,0.07],[0,0,0.46,0,0,0,0,0,0.7,0.93,1,1,1,0.61,0,0,0,0,0.18,0.11],[0,0,0.82,0,0,0,0,0,0.47,1,1,0.98,1,0.96,0.27,0,0,0,0.19,0.1],[0,0,0.46,0,0,0,0,0,0.25,1,1,0.84,0.92,0.97,0.54,0.14,0.04,0.1,0.21,0.05],[0,0,0,0.4,0,0,0,0,0.09,0.8,1,0.82,0.8,0.85,0.63,0.31,0.18,0.19,0.2,0.01],[0,0,0,0.36,0.1,0,0,0,0.05,0.54,0.86,0.79,0.74,0.72,0.6,0.39,0.28,0.24,0.13,0],[0,0,0,0.01,0.3,0.07,0,0,0.08,0.36,0.64,0.7,0.64,0.6,0.51,0.39,0.29,0.19,0.04,0],[0,0,0,0,0.1,0.24,0.14,0.1,0.15,0.29,0.45,0.53,0.52,0.46,0.4,0.31,0.21,0.08,0,0],[0,0,0,0,0,0.08,0.21,0.21,0.22,0.29,0.36,0.39,0.37,0.33,0.26,0.18,0.09,0,0,0],[0,0,0,0,0,0,0.03,0.13,0.19,0.22,0.24,0.24,0.23,0.18,0.13,0.05,0,0,0,0],[0,0,0,0,0,0,0,0,0.02,0.06,0.08,0.09,0.07,0.05,0.01,0,0,0,0,0]];

  function World(N, R, SC) {
    N = N || 64; R = R || 9; SC = SC || 0.7;
    var A = new Float32Array(N * N), B = new Float32Array(N * N), K = [], s = 0, dx, dy;
    for (dy = -R; dy <= R; dy++) for (dx = -R; dx <= R; dx++) { var r = Math.sqrt(dx * dx + dy * dy) / R; if (r <= 0 || r >= 1) continue;
      var w = Math.exp(4 - 1 / (r * (1 - r))); K.push(dx, dy, w); s += w; }
    for (var i = 2; i < K.length; i += 3) K[i] /= s;
    var n = Math.round(20 * SC), SM = [];
    for (var y = 0; y < n; y++) { SM.push([]); for (var x = 0; x < n; x++) SM[y].push(ORB[Math.min(19, Math.floor(y / SC))][Math.min(19, Math.floor(x / SC))]); }
    function wr(v) { return ((v % N) + N) % N; }
    var W = { N: N, mass: 0, get A() { return A; } };
    W.stamp = function (cx, cy, rot) { for (var y = 0; y < n; y++) for (var x = 0; x < n; x++) { var a = x, b = y;
      if (rot === 1) { a = n - 1 - y; b = x; } else if (rot === 2) { a = n - 1 - x; b = n - 1 - y; } else if (rot === 3) { a = y; b = n - 1 - x; }
      A[wr(cy - (n >> 1) + y) * N + wr(cx - (n >> 1) + x)] = SM[b][a]; } };
    W.clear = function () { A.fill(0); };
    W.step = function () { var m = 0;
      for (var y = 0; y < N; y++) for (var x = 0; x < N; x++) { var u = 0;
        for (var k = 0; k < K.length; k += 3) u += K[k + 2] * A[wr(y + K[k + 1]) * N + wr(x + K[k])];
        var g = 2 * Math.exp(-(u - 0.15) * (u - 0.15) / (2 * 0.015 * 0.015)) - 1, v = A[y * N + x] + g / 10;
        v = v < 0 ? 0 : v > 1 ? 1 : v; B[y * N + x] = v; m += v; }
      var t = A; A = B; B = t; W.mass = m; };
    W.set = function (arr) { A.set(arr); };
    return W;
  }

  // 구멍(H₁): 토러스 위 높은 값 집합의 구멍. minD = 최소 깊이, minS = 최소 넓이(칸)
  function holes(A, N, minD, minS) {
    var M = N * N, par = new Int32Array(M), mn = new Float32Array(M), fl = new Int32Array(M), sz = new Int32Array(M), done = new Uint8Array(M), idx = new Array(M), out = [];
    for (var i = 0; i < M; i++) idx[i] = i;
    idx.sort(function (a, b) { return A[a] - A[b]; });
    function find(a) { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; }
    function unite(a, b, f) { a = find(a); b = find(b); if (a === b) return;
      var y = (mn[a] > mn[b] || (mn[a] === mn[b] && sz[a] < sz[b])) ? a : b, o = y === a ? b : a;
      if (f - mn[y] > minD && sz[y] >= minS) out.push({ x: fl[y] % N, y: (fl[y] / N) | 0, d: f - mn[y], s: sz[y] });
      par[y] = o; sz[o] += sz[y]; }
    for (var q = 0; q < M; q++) { var p = idx[q], x = p % N, y = (p / N) | 0, f = A[p]; par[p] = p; mn[p] = f; fl[p] = p; sz[p] = 1; done[p] = 1;
      var nb = [y * N + (x + N - 1) % N, y * N + (x + 1) % N, ((y + N - 1) % N) * N + x, ((y + 1) % N) * N + x];
      for (var j = 0; j < 4; j++) if (done[nb[j]]) unite(p, nb[j], f); }
    return out.sort(function (a, b) { return b.d - a.d; });
  }

  // 원이 깜박이지 않게 — 가까운 구멍끼리 이어 붙이고 부드럽게 따라간다(토러스 거리)
  function Tracker(N) {
    var tr = [], id = 0;
    function td(a, b) { var dx = Math.abs(a.x - b.x), dy = Math.abs(a.y - b.y); dx = Math.min(dx, N - dx); dy = Math.min(dy, N - dy); return Math.hypot(dx, dy); }
    function wrap(d) { return d > N / 2 ? d - N : d < -N / 2 ? d + N : d; }
    return { list: function () { return tr; }, update: function (hs) {
      tr.forEach(function (t) { t.hit = false; });
      hs.forEach(function (h) { var best = null, bd = 6; tr.forEach(function (t) { var d = td(t, h); if (!t.hit && d < bd) { bd = d; best = t; } });
        if (best) { best.x = ((best.x + wrap(h.x - best.x) * 0.35) % N + N) % N; best.y = ((best.y + wrap(h.y - best.y) * 0.35) % N + N) % N;
          best.s += (h.s - best.s) * 0.25; best.d += (h.d - best.d) * 0.25; best.hit = true; }
        else tr.push({ id: ++id, x: h.x, y: h.y, s: h.s, d: h.d, a: 0, hit: true }); });
      tr.forEach(function (t) { t.a += t.hit ? (1 - t.a) * 0.15 : -0.06; });
      tr = tr.filter(function (t) { return t.a > 0.02; }); return tr; } };
  }

  // 점이 다각형 안에 있나 (짝홀 규칙)
  function inside(px, py, poly) { var c = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) { var a = poly[i], b = poly[j];
      if ((a[1] > py) !== (b[1] > py) && px < (b[0] - a[0]) * (py - a[1]) / (b[1] - a[1]) + a[0]) c = !c; }
    return c; }
  function area(poly) { var s = 0; for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) s += (poly[j][0] + poly[i][0]) * (poly[j][1] - poly[i][1]); return Math.abs(s / 2); }

  /** 구멍 하나 → 켜진 고리와 그 음들. towns[k] = {x, y, p}, loops/mine = [[town 번호…]…] (그 순서로 닫힌 다각형, mine 은 나중 것이 뒤)
   *  반환 { on: 'm'+번호 | 'h'+번호 | null, loop: [town 번호…, 고리 순서] } — 고리 밖이면 loop = [가장 가까운 음] */
  function which(hx, hy, towns, loops, mine) {
    var poly = function (l) { return l.map(function (k) { return [towns[k].x, towns[k].y]; }); };
    var uniq = function (l) { var seen = {}; return l.filter(function (k) { if (seen[k]) return false; seen[k] = 1; return true; }); };
    mine = mine || [];
    for (var i = mine.length - 1; i >= 0; i--) if (mine[i].length >= 3 && inside(hx, hy, poly(mine[i]))) return { on: 'm' + i, loop: uniq(mine[i]) };
    var on = []; loops.forEach(function (l, j) { if (l.length >= 3) { var P = poly(l); if (inside(hx, hy, P)) on.push([area(P), j]); } });
    if (on.length) { on.sort(function (a, b) { return a[0] - b[0] || b[1] - a[1]; }); return { on: 'h' + on[0][1], loop: uniq(loops[on[0][1]]) }; }
    var best = 0, bd = Infinity; towns.forEach(function (t, k) { var d = Math.hypot(t.x - hx, t.y - hy); if (d < bd) { bd = d; best = k; } });
    return { on: null, loop: [best] };
  }
  /** 박 t 에 고리가 낼 음: 짝수 박 = 넷까지(자리 t/2 에서 시작해 고리 순서로), 홀수 박 = 고리 순서의 (t>>1) 번째 하나 */
  function play(loop, t) { var n = loop.length, s = (t >> 1) % n;
    if (t % 2 === 1 || n === 1) return [loop[s]];
    var out = []; for (var i = 0; i < Math.min(4, n); i++) out.push(loop[(s + i) % n]); return out; }
  function vel(depth) { return 0.06 + 0.44 * Math.min(1, depth / 0.35); }   // 세기 = 구멍 깊이

  var API = { World: World, holes: holes, Tracker: Tracker, inside: inside, area: area, which: which, play: play, vel: vel };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.LifeLoop = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
