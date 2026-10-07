/* sketch/cube-core.js — 큐브: hibari 오른손 한 모듈이 루빅스 큐브 하나에 꼭 맞는다. DOM 없음, node 에서 돈다.
 * 페이지 sketch/cube.html 과 판정기 tools/verify_cube.mjs 가 같은 파일을 돈다.
 *
 * 칸표   면 = 화음 자리(F 미 · R 파 · B 솔 · L 라 · U 시 · D 도/라), 스티커 = 음, 칸 = 그 음이 울리는 때.
 *        H.mod[0](오른손 32스텝)에서 만든다 — 쉼 다음 첫 소리 = 구절의 시작, 구절마다 (화음, 단음) 여섯 쌍 = 자리 0..5.
 *        자리 0–4  가운데 = 두 구절이 같이 쓰는 베이스(두 화음 스텝에서 다 운다) · 윗줄 = 1구절 화음의 나머지 셋(낮은 음부터 왼→오른)
 *                  · 아랫줄 = 2구절 화음의 나머지 셋 · 칸 3 = 1구절 단음 · 칸 5 = 2구절 단음
 *        자리 5    1구절 화음에 낮은 베이스가 없다 → 윗줄 = 1구절 화음 셋 전부 · 가운데 = 2구절 베이스 · 아랫줄 = 2구절 나머지 셋
 *        → 칸 54 = 음 59 − (두 번 우는 가운데 다섯). 칸마다 박(스텝)과 길이가 붙어 있고 스티커는 음높이만 나른다(리듬은 시간 구조라 칸에 남는다).
 * 움직임 바깥 층만 돈다 — 가운데 칸(베이스)은 움직이지 않으니 어떻게 돌려도 오르는 베이스(미→도)는 지켜진다.
 *        표로 적지 않고 기하로 만든다: 칸마다 3차원 자리(면 위 ±1.5, 나머지 ∈ {−1,0,1})를 두고 그 층을 90° 돌려 같은 자리의 칸을 찾는다.
 *        바깥에서 그 면을 볼 때 시계 방향 = 기본(= 바깥 법선 둘레 −90°). R 은 앞면 오른쪽 열을 위로, U 는 앞면 윗줄을 왼쪽으로 보낸다.
 * 소리   박 g 마다 오른손 = 스텝 g mod 32 의 칸들, 왼손 = g mod 33 (왼손 모듈 = 오른손 + 쉼 한 칸 — 그 칸을 자료에서 찾는다).
 *        그 칸에 지금 있는 스티커의 음높이를 그 칸의 길이로. 세기: 화음 맨 아래 0.2 · 위 음 0.14 · 단음 0.32 · 왼손 ×0.78 · 구절 첫 화음 ×1.25.
 * 사건   면이 돌아옴(9칸이 모두 제 스티커 — 음높이가 같은 다른 스티커는 아니다) · 다 맞춤 · 되풀이가 시작 상태로 돌아옴(제자리).
 * 되풀이 공식(많아야 6수)을 쉼(오른손 12·28 = 쉼이 시작하는 스텝)마다 한 번. 차수 = 공식 순열의 고리 길이들의 최소공배수.
 * 펴기   스티커 중심을 공으로 부풀리고(정규화) 화면 뒤쪽 극에서 입체 사영 → 반지름을 2·atan(r) 로 줄인다(flat 머리말). 층의 띠는 같은 사상으로 옮긴 닫힌 곡선.
 */
(function (root) {
  'use strict';
  var HS = root.HS || (typeof require === 'function' ? require('./common.js') : null);
  var FACES = ['F', 'R', 'B', 'L', 'U', 'D'];
  var FR = {                                         // 면 → [바깥 법선, 바깥에서 본 오른쪽, 위]
    F: [[0, 0, 1], [1, 0, 0], [0, 1, 0]],   R: [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
    B: [[0, 0, -1], [-1, 0, 0], [0, 1, 0]], L: [[-1, 0, 0], [0, 0, 1], [0, 1, 0]],
    U: [[0, 1, 0], [1, 0, 0], [0, 0, -1]],  D: [[0, -1, 0], [1, 0, 0], [0, 0, 1]] };
  var DEFAULT_F = ['R', 'U', "R'", "U'"], DEMO = [['U'], ['R', 'U', "R'", "U'"]], FLATMAX = Math.PI, HIST = 4000;

  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function axpy(a, b, k) { return [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k]; }
  /** v 를 단위 축 a 둘레로 th 만큼 돌린다 (오른손 법칙 — 축 끝에서 보면 반시계가 +) */
  function rot(v, a, th) { var c = Math.cos(th), s = Math.sin(th), k = dot(a, v) * (1 - c), x = cross(a, v);
    return [v[0] * c + x[0] * s + a[0] * k, v[1] * c + x[1] * s + a[1] * k, v[2] * c + x[2] * s + a[2] * k]; }
  function key(p) { return Math.round(p[0] * 2) + ',' + Math.round(p[1] * 2) + ',' + Math.round(p[2] * 2); }

  // ── 칸 54개: 면 fi 의 (행 r, 열 c) → 번호 fi·9 + r·3 + c, 자리 = 법선·1.5 + 오른쪽·(c−1) + 위·(1−r) ─────────────
  var CELLS = [], AT = {};
  FACES.forEach(function (f, fi) { var F = FR[f];
    for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++) {
      var p = axpy(axpy([F[0][0] * 1.5, F[0][1] * 1.5, F[0][2] * 1.5], F[1], c - 1), F[2], 1 - r);
      AT[key(p)] = CELLS.length;
      CELLS.push({ id: CELLS.length, face: fi, r: r, c: c, pos: p, n: F[0], right: F[1], up: F[2], center: r === 1 && c === 1 }); } });
  // ── 사분 회전: 그 층(법선 방향 좌표 ≥ 1)을 법선 둘레 −90° 돌려 같은 자리의 칸을 찾는다. QT[f][i] = j : 칸 i 의 스티커가 칸 j 로 ──
  var QT = {};
  FACES.forEach(function (f) { var n = FR[f][0];
    QT[f] = CELLS.map(function (c, i) { if (dot(c.pos, n) < 0.5) return i; var j = AT[key(rot(c.pos, n, -Math.PI / 2))];
      if (j == null) throw new Error('움직임 ' + f + ': 칸 ' + i + ' 의 갈 곳이 없다'); return j; }); });

  function parse(name) { var m = /^([FRBLUD])(2|'|′)?$/.exec(String(name).trim()); if (!m) return null;
    return { f: m[1], fi: FACES.indexOf(m[1]), q: m[2] === '2' ? 2 : m[2] ? 3 : 1 }; }   // q = 시계 방향 사분 회전 수
  function nameOf(f, q) { return f + (q === 2 ? '2' : q === 3 ? "'" : ''); }
  function inv(name) { var m = parse(name); return nameOf(m.f, 4 - m.q); }
  function show(name) { return String(name).replace(/'/g, '′'); }                  // 화면용: R′
  function ident() { var a = []; for (var i = 0; i < 54; i++) a.push(i); return a; }
  function turnState(st, f, q) { var P = QT[f]; for (var k = 0; k < q; k++) { var o = new Array(54); for (var i = 0; i < 54; i++) o[P[i]] = st[i]; st = o; } return st; }
  function run(st, formula) { formula.forEach(function (nm) { var m = parse(nm); st = turnState(st, m.f, m.q); }); return st; }
  function same(a, b) { for (var i = 0; i < 54; i++) if (a[i] !== b[i]) return false; return true; }
  function gcd(a, b) { while (b) { var t = a % b; a = b; b = t; } return a; }
  /** 공식의 차수: 맞춘 상태에 한 번 돌린 순열의 고리 길이들의 최소공배수 (그만큼 되풀이하면 어디서 시작했든 제자리) */
  function orderOf(formula) { var st = run(ident(), formula), seen = [], o = 1;
    for (var i = 0; i < 54; i++) { if (seen[i]) continue; var n = 0, j = i; while (!seen[j]) { seen[j] = 1; j = st[j]; n++; } o = o / gcd(o, n) * n; }
    return o; }
  /** 이어진 같은 면 돌리기를 합친다 (U U′ → 없음, R R → R2) */
  function reduce(moves) { var out = [];
    moves.forEach(function (nm) { var m = parse(nm); if (!m) return; var top = out[out.length - 1];
      if (top && top.f === m.f) { top.q = (top.q + m.q) % 4; if (!top.q) out.pop(); } else out.push({ f: m.f, q: m.q }); });
    return out.map(function (m) { return nameOf(m.f, m.q); }); }
  function faceOf(n) { for (var i = 0; i < 6; i++) { var a = FR[FACES[i]][0]; if (a[0] === n[0] && a[1] === n[1] && a[2] === n[2]) return FACES[i]; } return null; }
  /** 이름 → 그 층을 법선 둘레로 돌리는 각 (그림용): 시계 = −90° */
  function angleOf(name) { var m = parse(name); return m.q === 3 ? Math.PI / 2 : -Math.PI / 2 * m.q; }

  // ── 칸표: 오른손 모듈 → 칸마다 제 음높이와 소리 사건 [{step, dur}] ────────────────────────────────────────
  function table(H) {
    var A = H.mod[0], P = A.period, st = A.steps, N = H.notes, t, u, k;
    function nt(li) { return { pitch: N[li].pitch, dur: N[li].dur }; }
    function byP(a, b) { return a.pitch - b.pitch || a.dur - b.dur; }
    var starts = [], rest = [];
    for (t = 0; t < P; t++) { var on = st[t].length > 0, prev = st[(t + P - 1) % P].length > 0; if (on && !prev) starts.push(t); if (!on && prev) rest.push(t); }
    var ph = starts.map(function (s) { var o = []; for (u = s; u < s + P && st[u % P].length; u++) o.push(u % P); return o; });
    if (ph.length !== 2 || ph[0].length !== 12 || ph[1].length !== 12) throw new Error('칸표: 오른손 모듈이 두 구절 × 12소리가 아니다');
    var cell = CELLS.map(function () { return { pitch: null, ev: [] }; }), ch1 = [], single1 = [];
    function put(i, n, step) { if (cell[i].pitch != null && cell[i].pitch !== n.pitch) throw new Error('칸표: 칸 ' + i + ' 에 다른 두 음');
      cell[i].pitch = n.pitch; cell[i].ev.push({ step: step, dur: n.dur }); }
    for (k = 0; k < 6; k++) {
      var a = ph[0][2 * k], b = ph[1][2 * k], s1 = ph[0][2 * k + 1], s2 = ph[1][2 * k + 1], o = k * 9;
      var c1 = st[a].map(nt).sort(byP), c2 = st[b].map(nt).sort(byP);
      if (st[s1].length !== 1 || st[s2].length !== 1 || c2.length !== 4) throw new Error('칸표: 자리 ' + k + ' 의 모양이 다르다');
      if (c1.length === 4 && c1[0].pitch === c2[0].pitch) { put(o + 4, c1[0], a); put(o + 4, c2[0], b); for (u = 0; u < 3; u++) put(o + u, c1[u + 1], a); }
      else if (c1.length === 3) { for (u = 0; u < 3; u++) put(o + u, c1[u], a); put(o + 4, c2[0], b); }
      else throw new Error('칸표: 자리 ' + k + ' 의 1구절 화음이 3음도 4음도 아니다');
      for (u = 0; u < 3; u++) put(o + 6 + u, c2[u + 1], b);
      put(o + 3, nt(st[s1][0]), s1); put(o + 5, nt(st[s2][0]), s2);
      ch1.push(a); single1.push(s1);
    }
    var by = []; for (t = 0; t < P; t++) by.push([]);
    cell.forEach(function (c, i) { c.ev.forEach(function (e) { by[e.step].push({ cell: i, dur: e.dur }); }); });
    // 왼손 = 오른손 모듈에 쉼 한 칸을 끼운 것 — 그 칸(gap)을 찾는다. 왼손 스텝 l → 오른손 스텝 lmap[l] (gap 이면 −1)
    var B = H.mod[1], Q = B.period, sig = function (s) { return s.map(function (li) { return N[li].pitch + '/' + N[li].dur; }).sort().join(' '); };
    var RS = st.map(sig), LS = B.steps.map(sig), gap = -1, p;
    for (p = 0; p < Q && gap < 0 && Q === P + 1; p++) { if (LS[p]) continue;
      for (t = 0, u = 0; t < Q; t++) { if (t === p) continue; if (LS[t] !== RS[u++]) break; } if (t === Q) gap = p; }
    if (gap < 0) throw new Error('칸표: 왼손이 오른손 + 쉼 한 칸이 아니다');
    var lmap = []; for (t = 0; t < Q; t++) lmap.push(t < gap ? t : t === gap ? -1 : t - 1);
    var seat = ch1.map(function (s) { var lo = Math.min.apply(null, by[s].map(function (e) { return cell[e.cell].pitch; }));
      return HS ? HS.noteName(lo).replace(/-?\d+$/, '') : String(lo); });
    return { cell: cell, by: by, ch1: ch1, single1: single1, first: [ph[0][0], ph[1][0]], rest: rest, P: P, Q: Q, lmap: lmap, gap: gap, seat: seat };
  }

  // ── 끌기 → 움직임 (순수 함수): 면의 두 접선 축을 화면에 투영해 끈 방향과 더 맞는 축 m 을 고르고, 회전축 = 법선 × m,
  //    층 = 스티커의 그 축 좌표. 가운데 층(0)이면 움직임 없음 = 보기 돌리기. proj(p) → [화면 x, 화면 y(아래로 +)] ─────────────
  function dragMove(cell, dx, dy, proj) {
    var c = CELLS[cell], len = Math.hypot(dx, dy); if (!c || !(len > 0)) return null;
    var o = proj(c.pos), best = null;
    [c.right, c.up].forEach(function (t) { var q = proj(axpy(c.pos, t, 0.5)), sx = q[0] - o[0], sy = q[1] - o[1], sl = Math.hypot(sx, sy) || 1;
      var a = (sx * dx + sy * dy) / (sl * len); if (!best || Math.abs(a) > Math.abs(best.a)) best = { t: t, a: a }; });
    var m = best.t.map(function (x) { return best.a < 0 ? -x : x; }), axis = cross(c.n, m), layer = Math.round(dot(c.pos, axis));
    if (!layer) return { view: true, move: null, align: Math.abs(best.a) };
    // 축 둘레 +90° (점이 m 쪽으로 간다) = 층 쪽 면 법선 nf = axis·layer 둘레로는 layer>0 이면 +90°(반시계 = ′), layer<0 이면 −90°(시계)
    var f = faceOf(axis.map(function (x) { return x * layer || 0; }));
    return { view: false, move: layer > 0 ? f + "'" : f, align: Math.abs(best.a) };
  }

  // ── 보기·투영 ────────────────────────────────────────────────────────────────────────────────
  /** 보기 행렬 M = Rx(pitch)·Ry(yaw) (행 우선 9개). 화면: x 오른쪽, y 위, z 화면 밖(눈 쪽) */
  function view(yaw, pitch) { var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    return [cy, 0, sy, sp * sy, cp, -sp * cy, -cp * sy, sp, cp * cy]; }
  function mul(M, v) { return [M[0] * v[0] + M[1] * v[1] + M[2] * v[2], M[3] * v[0] + M[4] * v[1] + M[5] * v[2], M[6] * v[0] + M[7] * v[1] + M[8] * v[2]]; }
  /** 원근 투영: 눈은 (0,0,D). S = 깊이 0 에서 한 칸의 화면 길이 */
  function projector(M, D, S, cx, cy) { return function (p) { var v = mul(M, p), k = S * D / (D - v[2]); return [cx + v[0] * k, cy - v[1] * k, v[2]]; }; }
  var CORNER = { yaw: -Math.PI / 4, pitch: Math.atan(Math.SQRT1_2) };                  // 앞·오른쪽·위 모서리(+1,+1,+1)가 눈 쪽: 3겹 대칭
  /** 펴기: 공으로 부풀린 점을 보기 공간에서 뒤쪽 극 (0,0,−1) 으로부터 입체 사영(r = tan(θ/2)) → 바깥이 커지니 반지름을 부드럽게 줄인다.
   *  줄이는 함수 = 2·atan(r) (= 앞쪽 극에서 잰 각 θ, 끝 = π). 방향은 입체 사영 그대로다.
   *  ponytail: 예시였던 r/(1+0.25r) 는 폰 폭(375px)에서 앞 세 면의 점 간격이 10px(이름을 못 쓴다), 뒤는 96px — 간격 비 9.2.
   *  2·atan(r) 은 21px … 45px, 비 2.2 (2026-10-07 측정). 반환 [x, y] (y 위로 +), |·| < FLATMAX */
  function flat(p, M) {
    var l = Math.hypot(p[0], p[1], p[2]), v = mul(M, [p[0] / l, p[1] / l, p[2] / l]), d = 1 + v[2];
    if (d < 1e-12) { var h = Math.hypot(v[0], v[1]) || 1; return [v[0] / h * Math.PI, v[1] / h * Math.PI]; }
    var X = v[0] / d, Y = v[1] / d, r = Math.hypot(X, Y), k = r > 1e-12 ? 2 * Math.atan(r) / r : 2; return [X * k, Y * k]; }
  /** 층의 띠 9개 (축 3 × 층 −1·0·1): 그 층이 큐브 겉면을 두르는 네모 고리를 1/16 간격으로 표본(스티커 중심이 표본에 든다) + 띠 위 스티커 12장 */
  function bands() { var out = [], C4 = [[1.5, 1.5], [-1.5, 1.5], [-1.5, -1.5], [1.5, -1.5]];
    for (var ax = 0; ax < 3; ax++) for (var v = -1; v <= 1; v++) {
      var j = (ax + 1) % 3, k = (ax + 2) % 3, path = [];
      for (var e = 0; e < 4; e++) { var A = C4[e], B = C4[(e + 1) % 4];
        for (var s = 0; s < 48; s++) { var t = s / 48, p = [0, 0, 0]; p[ax] = v; p[j] = A[0] + (B[0] - A[0]) * t; p[k] = A[1] + (B[1] - A[1]) * t; path.push(p); } }
      out.push({ axis: ax, v: v, path: path, cells: CELLS.filter(function (c) { return c.n[ax] === 0 && c.pos[ax] === v; }).map(function (c) { return c.id; }) });
    } return out; }

  // ── 엔진 ─────────────────────────────────────────────────────────────────────────────────
  function create(H) {
    var T = table(H), HOME = T.cell.map(function (c) { return c.pitch; });
    var S = { st: ident(), g: 0, hist: [], rec: [], rep: null, demo: false, demoK: 0, lastF: null };
    function pitchAt(i) { return HOME[S.st[i]]; }
    function mask() { var m = 0; for (var f = 0; f < 6; f++) { var ok = true; for (var i = f * 9; i < f * 9 + 9; i++) if (S.st[i] !== i) { ok = false; break; } if (ok) m |= 1 << f; } return m; }
    function faces(m) { var o = []; for (var f = 0; f < 6; f++) if (m & 1 << f) o.push(f); return o; }
    /** 오른손 스텝 t 의 칸들이 지금 내는 음 (hand 1 = 왼손 세기) */
    function stepNotes(t, hand) { var evs = T.by[t]; if (!evs || !evs.length) return [];
      var out = evs.map(function (e) { return { pitch: pitchAt(e.cell), dur: e.dur, hand: hand, cell: e.cell, sticker: S.st[e.cell], step: t }; });
      var lo = 0; out.forEach(function (o, i) { if (o.pitch < out[lo].pitch) lo = i; });
      var boost = (T.first.indexOf(t) >= 0 ? 1.25 : 1) * (hand ? 0.78 : 1);
      out.forEach(function (o, i) { o.vel = (out.length > 1 ? (i === lo ? 0.2 : 0.14) : 0.32) * boost; });
      return out; }
    function sound(g) { var r = g % T.P, l = g % T.Q, out = stepNotes(r, 0); return T.lmap[l] >= 0 ? out.concat(stepNotes(T.lmap[l], 1)) : out; }
    function chordOf(fi, vel) { return T.by[T.ch1[fi]].map(function (e) { return { pitch: pitchAt(e.cell), dur: e.dur, vel: vel, cell: e.cell, sticker: S.st[e.cell] }; }); }
    function turn(name, auto) { var m = parse(name); if (!m) return null; var before = S.st.slice();
      S.st = turnState(S.st, m.f, m.q);
      return { name: nameOf(m.f, m.q), f: m.f, fi: m.fi, q: m.q, before: before, after: S.st.slice(), notes: chordOf(m.fi, auto ? 0.12 : 0.22), auto: !!auto }; }
    function push(name, auto) { S.hist.push({ name: name, auto: auto }); if (S.hist.length > HIST) S.hist.splice(0, S.hist.length - HIST); }
    /** 사건: 이번에 새로 돌아온 면 · 다 맞춤. 소리 = 돌아온 면의 원래 1구절 화음(여리게) / 다 맞춤이면 hibari 첫 화음을 펼쳐서 */
    function events(before) { var now = mask(), fresh = faces(now & ~before), all = now === 63 && before !== 63, notes = [];
      if (all) { var arp = T.by[T.first[0]].map(function (e) { return { pitch: HOME[e.cell], cell: e.cell }; }).sort(function (a, b) { return a.pitch - b.pitch; })
          .concat(T.by[T.single1[0]].map(function (e) { return { pitch: HOME[e.cell], cell: e.cell }; }));
        arp.forEach(function (n, i) { notes.push({ pitch: n.pitch, dur: 3, vel: 0.12, at: 0.2 + 0.09 * i, cell: n.cell, sticker: n.cell }); }); }
      else fresh.forEach(function (f, j) { T.by[T.ch1[f]].forEach(function (e) { notes.push({ pitch: HOME[e.cell], dur: e.dur, vel: 0.1, at: 0.24 + 0.16 * j, cell: e.cell, sticker: e.cell }); }); });
      return { faces: fresh, all: all, mask: now, names: fresh.map(function (f) { return T.seat[f]; }), notes: notes }; }
    function stopRep() { S.rep = null; S.demo = false; }
    function startRep(f) { S.lastF = f.slice(); S.rep = { formula: f.slice(), order: orderOf(f), count: 0, start: S.st.slice() }; return info(); }
    function info() { var R = S.rep; return R ? { formula: R.formula.map(show).join(' '), moves: R.formula.slice(), order: R.order, count: R.count } : null; }

    /** 손으로 돌리기 — 되풀이가 꺼진다. 돌린 면의 새 1구절 화음이 곧바로(notes, 지연 없음) */
    function move(name) { var m = parse(name); if (!m) return null; stopRep();
      var before = mask(), x = turn(name, false); push(x.name, false); S.rec.push(x.name); x.events = events(before); return x; }
    function undo() { var h = S.hist.pop(); if (!h) return null; stopRep(); if (!h.auto) S.rec.pop();
      var before = mask(), x = turn(inv(h.name), false); x.undo = true; x.events = events(before); return x; }
    function reset(restart) { S.st = ident(); S.hist = []; S.rec = []; stopRep(); if (restart) S.g = 0; }
    /** 되풀이 켜기: 공식 = 처음으로/지난번 켠 뒤 손으로 돌린 것(합친 뒤 마지막 6수). 없으면 지난 공식, 그것도 없으면 R U R′ U′.
     *  시작 상태 = 켠 순간의 상태. 차수만큼 되풀이하면 반드시 여기로 돌아온다. */
    function setRepeat(on, formula) { if (!on) { stopRep(); return null; }
      var f = formula ? formula.map(function (x) { var m = parse(x); return nameOf(m.f, m.q); }) : reduce(S.rec).slice(-6);
      if (!f.length) f = (S.lastF || DEFAULT_F).slice();
      S.rec = []; S.demo = false; return startRep(f); }
    /** 공식을 한 번 — 저절로 돈 움직임은 되돌리기 기록에 들어가고 공식 기록(rec)에는 들어가지 않는다 */
    function repeatOnce() { var R = S.rep; if (!R) return null; var before = mask();
      var moves = R.formula.map(function (nm) { var x = turn(nm, true); push(x.name, true); return x; });
      R.count++; var home = same(S.st, R.start), out = { auto: moves, count: R.count, order: R.order, formula: R.formula.map(show).join(' '), home: home, events: events(before) };
      if (home) { if (S.demo) { S.demoK = (S.demoK + 1) % DEMO.length; startRep(DEMO[S.demoK]); S.demo = true; } else R.count = 0; }
      return out; }
    function setDemo(on) { if (!on) { if (S.demo) stopRep(); return; } S.demoK = 0; startRep(DEMO[0]); S.demo = true; }
    /** 한 박: 지금 상태로 두 손의 음을 내고, 쉼이 시작하는 박이면 되풀이를 한 번 (소리를 먼저 정하고 나서 돌린다) */
    function beat() { var g = S.g, r = g % T.P, out = { g: g, r: r, l: g % T.Q, notes: sound(g), rep: null };
      if (S.rep && T.rest.indexOf(r) >= 0) out.rep = repeatOnce();
      S.g++; return out; }
    function probe() { var m = mask(), R = info(); return { g: S.g, r: S.g % T.P, solvedFaces: faces(m).length, faces: faces(m), solved: m === 63,
      formula: R && R.formula, order: R && R.order, count: R && R.count, moves: S.hist.length, demo: S.demo, rec: S.rec.slice() }; }

    return { table: T, home: HOME, cells: CELLS, get state() { return S.st; }, set state(a) { S.st = a.slice(); }, get g() { return S.g; }, set g(v) { S.g = v; },
             pitchAt: pitchAt, mask: mask, stepNotes: stepNotes, sound: sound, chordOf: chordOf, move: move, undo: undo, reset: reset,
             setRepeat: setRepeat, repeatOnce: repeatOnce, setDemo: setDemo, beat: beat, probe: probe, info: info, events: events,
             get rep() { return info(); }, get demo() { return S.demo; } };
  }

  var API = { create: create, table: table, CELLS: CELLS, FACES: FACES, FR: FR, QT: QT, parse: parse, inv: inv, show: show, nameOf: nameOf, reduce: reduce,
              orderOf: orderOf, run: run, ident: ident, same: same, turnState: turnState, angleOf: angleOf, rot: rot, dot: dot, cross: cross, axpy: axpy,
              dragMove: dragMove, view: view, mul: mul, projector: projector, CORNER: CORNER, flat: flat, bands: bands, FLATMAX: FLATMAX, DEMO: DEMO, DEFAULT_F: DEFAULT_F };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSCube = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
