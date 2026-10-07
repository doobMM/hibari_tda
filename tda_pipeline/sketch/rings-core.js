/* sketch/rings-core.js — 고리판: 사용자가 보여 준 그림(루빅스 큐브의 스티커를 세 무리 동심원의 교점에 편 것)을 그대로 판으로.
 * DOM 없음, node 에서 돈다. 페이지 sketch/rings.html, 판정기 tools/verify_rings.mjs.
 *
 * 판     큐브 겉면을 공으로 보고 칸마다 공 위의 점 q 를 둔다: 면의 두 방향 좌표 = S·(−1·0·1), 법선 방향 = 나머지(공 위에 오도록).
 *        그러면 띠(축 a 의 층 L 에 있는 옆면 칸 12개)가 전부 평면 q[a] = S·L 위에 있다 = 공 위의 **진짜 원**. 원 9개 = 축 3 × 층 3.
 *        점 54 = 원과 원이 만나는 곳(점 하나에 원 둘). 보이는 모서리(+1,+1,+1) 쪽에서 보고 뒤쪽 극에서 입체 사영 → 반지름을 2·atan(r) 로 줄인다
 *        (원이 원으로 남는 사영이지만 바깥이 너무 커져 줄인다 — 줄인 뒤엔 둥근 닫힌 곡선이다). 보이는 세 면 = 가운데 육각, 숨은 세 면 = 바깥 꽃잎 셋.
 * 돌리기 원 하나를 사분 회전(90°)씩 돌린다 — 그 원 위의 점 12개만 움직인다(면은 돌지 않는다 = 헝가리 고리처럼). 점은 그 원을 따라 미끄러진다.
 * 소리   칸표는 sketch/cube-core.js 의 table(H) 그대로 — 칸 = 박과 길이, 점 = 음높이. 자리(면) 0..5 = 미 파 솔 라 시 도.
 *        여기서 면의 순서만 바꿨다: 가운데 세 면 F R U(미 파 솔) 다음 바깥 세 면 L D B(라 시 도) — 빛이 가운데를 한 바퀴, 바깥을 한 바퀴 같은 쪽으로 돈다.
 *        다 맞춘 판 = hibari 오른손 32스텝 · 왼손 33스텝 (판정기 R3). 소리·사건은 HSCube.create(H) 의 sound·mask·events 를 그대로 쓴다.
 */
(function (root) {
  'use strict';
  var HS = root.HS || (typeof require === 'function' ? require('./common.js') : null);
  var CUBE = root.HSCube || (typeof require === 'function' ? require('./cube-core.js') : null);
  var FACES = ['F', 'R', 'U', 'L', 'D', 'B'];        // 자리 0..5 = 미 파 솔 라 시 도
  var FR = CUBE.FR, S = 0.42;                        // FR[f] = [바깥 법선, 오른쪽, 위] · S = 공 위 띠의 높이
  var TAU = Math.PI * 2;
  function key(p, n) { return p.map(function (x) { return Math.round(x * 2); }).join(',') + '|' + n.join(','); }

  // ── 칸 54: 번호 = 자리·9 + 행·3 + 열 (행 0 = 위, 열 0 = 왼쪽, 4 = 가운데) — cube-core 칸표와 같은 번호 규약 ───────────
  var CELLS = [], AT = {};
  FACES.forEach(function (f, fi) { var F = FR[f], n = F[0];
    for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++) {
      var p = [0, 1, 2].map(function (k) { return n[k] * 1.5 + F[1][k] * (c - 1) + F[2][k] * (1 - r); });
      var q = [0, 1, 2].map(function (k) { return n[k] ? 0 : S * p[k]; }), ax = n.findIndex(function (x) { return x !== 0; });
      q[ax] = n[ax] * Math.sqrt(1 - q[0] * q[0] - q[1] * q[1] - q[2] * q[2]);
      AT[key(p, n)] = CELLS.length;
      CELLS.push({ id: CELLS.length, face: fi, r: r, c: c, pos: p, n: n, q: q, center: r === 1 && c === 1 }); } });

  // ── 원 9개: 축 a · 층 L. 칸 12개를 축 둘레 각(오른손 법칙)으로 늘어놓는다 ─────────────────────────────────────
  var RINGS = [];
  for (var a = 0; a < 3; a++) for (var L = -1; L <= 1; L++) {
    var k1 = (a + 1) % 3, k2 = (a + 2) % 3, cells = CELLS.filter(function (c) { return c.n[a] === 0 && c.pos[a] === L; });
    cells.forEach(function (c) { c.ang = c.ang || {}; c.ang[a] = Math.atan2(c.q[k2], c.q[k1]); });
    cells.sort(function (x, y) { return x.ang[a] - y.ang[a]; });
    RINGS.push({ id: RINGS.length, axis: a, level: L, k1: k1, k2: k2, h: S * L, rad: Math.sqrt(1 - S * S * L * L), cells: cells.map(function (c) { return c.id; }) });
  }
  // 사분 회전: 원 위 칸을 축 둘레 +90° 돌려 같은 자리의 칸을 찾는다. PERM[ring][i] = j : 칸 i 의 점이 칸 j 로 (+90° = 축 끝에서 보면 반시계)
  function rot90(v, R) { var o = v.slice(); o[R.k1] = -v[R.k2]; o[R.k2] = v[R.k1]; return o; }
  var PERM = RINGS.map(function (R) {
    var P = CELLS.map(function (c, i) { return i; });
    R.cells.forEach(function (i) { var c = CELLS[i], j = AT[key(rot90(c.pos, R), rot90(c.n, R))];
      if (j == null) throw new Error('고리 ' + R.id + ': 칸 ' + i + ' 의 갈 곳이 없다'); P[i] = j; });
    return P; });
  function ident() { var a = []; for (var i = 0; i < 54; i++) a.push(i); return a; }
  /** 상태 st[칸] = 점(= 제 칸 번호). 고리 ring 을 k 번 (+면 반시계) 돌린다 */
  function turn(st, ring, k) { k = ((k % 4) + 4) % 4; var P = PERM[ring];
    for (var m = 0; m < k; m++) { var o = st.slice(); for (var i = 0; i < 54; i++) o[P[i]] = st[i]; st = o; } return st; }

  // ── 그리기 좌표: 보이는 모서리를 눈 쪽으로 돌리고(cube-core 의 CORNER), 뒤쪽 극에서 입체 사영, 반지름 2·atan(r) (|·| < π) ──
  var M = CUBE.view(CUBE.CORNER.yaw, CUBE.CORNER.pitch);
  function flat(q) { var v = CUBE.mul(M, q), d = 1 + v[2];
    if (d < 1e-12) { var h = Math.hypot(v[0], v[1]) || 1; return [v[0] / h * Math.PI, v[1] / h * Math.PI]; }
    var X = v[0] / d, Y = v[1] / d, r = Math.hypot(X, Y), k = r > 1e-12 ? 2 * Math.atan(r) / r : 2; return [X * k, Y * k]; }   // y 위로 +
  /** 고리 R 위 각 φ 의 공 위 점 */
  function onRing(R, phi) { var q = [0, 0, 0]; q[R.axis] = R.h; q[R.k1] = R.rad * Math.cos(phi); q[R.k2] = R.rad * Math.sin(phi); return q; }
  /** 칸 c 를 고리 R 둘레로 θ 만큼 돌린 공 위 점 (끌고 있는 동안 그 고리 위 점들이 원을 따라 미끄러진다) */
  function spin(q, R, th) { var cs = Math.cos(th), sn = Math.sin(th), o = q.slice(); o[R.k1] = q[R.k1] * cs - q[R.k2] * sn; o[R.k2] = q[R.k1] * sn + q[R.k2] * cs; return o; }
  /** 고리마다 그린 곡선(표본 n 개)과, 그 고리에서 가장 바깥(판 가운데에서 먼) 곳의 각 = 바늘 */
  function curves(n) { n = n || 180;
    return RINGS.map(function (R) { var pts = [], far = 0, needle = 0;
      for (var s = 0; s < n; s++) { var phi = TAU * s / n, p = flat(onRing(R, phi)); pts.push(p); var d = Math.hypot(p[0], p[1]); if (d > far) { far = d; needle = phi; } }
      return { ring: R.id, pts: pts, needle: needle }; }); }
  /** 같은 각인가 (2π 둘레) */
  function wrap(x) { while (x > Math.PI) x -= TAU; while (x < -Math.PI) x += TAU; return x; }
  /** 끌기 판정: 점(칸 i)을 잡고 화면에서 (dx, dy)(y 위로 +) 끌었다 → 그 점을 지나는 두 고리 중 접선이 끈 방향과 더 맞는 고리.
   *  끈 방향의 부호 = 각이 늘어나는 쪽인가. 반환 {ring, sign, align} */
  function pick(i, dx, dy) { var c = CELLS[i], best = null, len = Math.hypot(dx, dy) || 1;
    RINGS.forEach(function (R) { if (R.cells.indexOf(i) < 0) return;
      var phi = c.ang[R.axis], a = flat(onRing(R, phi - 0.01)), b = flat(onRing(R, phi + 0.01)), tx = b[0] - a[0], ty = b[1] - a[1], tl = Math.hypot(tx, ty) || 1;
      var al = (tx * dx + ty * dy) / (tl * len); if (!best || Math.abs(al) > Math.abs(best.align)) best = { ring: R.id, sign: al >= 0 ? 1 : -1, align: al }; });
    return best; }
  /** 돌린 각 → 사분 회전 수 (가장 가까운 90° 배수) */
  function snap(th) { return Math.round(th / (Math.PI / 2)); }
  /** 키(→)가 쓰는 '화면에서 시계 방향' 사분의 부호 — 고리마다 그린 곡선의 넓이 부호로 (각이 늘 때 반시계(y 위로 +)면 시계 = −1) */
  var CW = curves(240).map(function (C) { var a = 0, P = C.pts;
    for (var s = 0; s < P.length; s++) { var p = P[s], q = P[(s + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a > 0 ? -1 : 1; });
  /** 키(↑↓)로 고르는 차례: 보이는 송이 미·파·솔마다 그 송이를 감싼 원 → 허리 원(베이스를 지난다) → 맞은편 꽃잎을 감싼 원 */
  var ORDER = [0, 1, 2].reduce(function (o, fi) { var n = FR[FACES[fi]][0], a = n.findIndex(function (x) { return x !== 0; });
    return o.concat(RINGS.filter(function (R) { return R.axis === a; }).sort(function (x, y) { return (y.level - x.level) * n[a]; }).map(function (R) { return R.id; })); }, []);

  // ── 엔진: cube-core 의 칸표·소리·사건을 그대로 쓰고, 상태만 고리 회전으로 바꾼다 ───────────────────────────────
  function create(H) {
    var E = CUBE.create(H), st = ident(), hist = [];
    function set(s) { st = s; E.state = s; }
    /** 고리를 k 사분 돌린다 → {ring, k, moved:[칸…], events} (사건 = 새로 돌아온 자리 · 다 맞춤) */
    function move(ring, k, auto) { k = ((k % 4) + 4) % 4; if (!k) return null; var before = E.mask();
      set(turn(st, ring, k)); hist.push({ ring: ring, k: k, auto: !!auto });
      return { ring: ring, k: k, moved: RINGS[ring].cells.slice(), events: E.events(before) }; }
    function undo() { var h = hist.pop(); if (!h) return null; var before = E.mask();
      set(turn(st, h.ring, 4 - h.k)); return { ring: h.ring, k: 4 - h.k, undo: true, moved: RINGS[h.ring].cells.slice(), events: E.events(before) }; }
    function reset() { set(ident()); hist = []; }
    return { engine: E, table: E.table, home: E.home, sound: E.sound, chordOf: E.chordOf, mask: E.mask,
             move: move, undo: undo, reset: reset, get state() { return st; }, set state(s) { set(s.slice()); }, get hist() { return hist; },
             pitchAt: function (i) { return E.home[st[i]]; } };
  }

  var API = { create: create, CELLS: CELLS, RINGS: RINGS, PERM: PERM, FACES: FACES, S: S, turn: turn, ident: ident, flat: flat, onRing: onRing,
              spin: spin, curves: curves, pick: pick, snap: snap, wrap: wrap, CW: CW, ORDER: ORDER };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSRings = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
