/* sketch/flight-core.js — 날갯짓: 유리 큐브 안을 나비처럼 나는 빛 한 점 (2026-10-07). 엔진 — DOM 없음, node 에서 돈다.
 * 페이지 sketch/flight.html · 판정기 tools/verify_flight.mjs · VR H₁ 대조 tools/verify/flight_ripser_check.py (ripser 0.6.14)
 *
 * 사용자: "생명체가 없어도 돼 … 사용자가 조작함으로써 자신이 원하는 음악 … ryuichi sakamoto 스타일이자 TDA 에 기반 … 사건은 있었으면" ·
 *         "나비나 벌이 … 3차원 공간 상에서 그 움직임을 구현 … 생명체 자체를 베끼는 게 아니라 그 움직임을".
 *         그래서 몸은 그리지 않는다 — 빛 한 점, 지나간 길, 고리뿐이다.
 *
 * 공간   큐브 [−1,1]³, y 가 위. 높이를 여섯 칸으로 나눈다(아래부터 자리 0..5 — hibari 베이스가 한 계단씩 오르는 그 여섯 자리).
 * 날기   누르고 있으면 날갯짓. 한 번 = 2박(내리치기 → 올리기). 내리칠 때 튀어 오르고(CLIMB+BOB) 올릴 때 조금 가라앉아(BOB)
 *        날갯짓 한 번에 한 칸씩 오른다. 바닥에서 뜰 때만 반 칸을 더 뛴다(HOP) — 그래야 바닥에서 누르고 있을 때 여섯 번의
 *        내리치기가 칸 0..5 의 **한가운데**에 떨어진다(경계에 떨어지면 부동소수 하나에 칸이 바뀐다).
 *        떼면 활공: 소리 없이 y = y₀ − ½·G·τ² 로 떨어지며 점점 빨라진다(짧게 떼면 조금, 오래 떼면 뚝).
 *        G 는 "맨 위(올리기 끝)에서 4박 떼면 칸 0 한가운데" 가 되도록 정했다 → 여섯 번 날갯짓하며 오르고 4박 떨어지면 hibari 한 구절의 톱니.
 *        바닥에 닿으면 앉는다. 높이는 해석식이라 박의 자리에서 정확하다(물리 걸음 DT 와 무관).
 *        방향은 누름과 상관없이 목표점(포인터)으로 돈다: 앞으로 V, 도는 빠르기 최대 W. 목표를 가만히 두면 목표를 가운데 둔
 *        반지름 RO = V·16박/2π ≈ 0.46 의 원으로 맴돈다(맴돌기 벡터장 — desire 주석) → 맴도는 한 바퀴가 16박 = hibari 한 구절(12박 울림 + 4박 쉼).
 *        벽 가까이선 가운데 쪽을 섞고 더 세게 돈다.
 * 소리   칸은 내리치는 순간에 정한다. 내리치기 = 그 자리의 hibari 화음, 올리기 = **같은 자리의** 단음(화음–단음 짝), 활공 = 쉼.
 *        활공이 2박 이상이었으면 다시 날기 시작할 때 1구절 ↔ 2구절(A A′). 음은 H.mod[0] 에서 읽는다(구절·자리를 거기서 찾는다).
 *        누르는 그 호출 안에서 곧바로 내리치기(press 가 음을 돌려준다). 그 뒤 날갯짓은 박자 격자에 — 다음 박까지 DEFER 초 미만이면
 *        그 박의 올리기를 한 박 미룬다. 기록은 올리기 바로 앞 박(대개 가장 가까운 박 — 아래 press 주석).
 *        세기: 화음 베이스 0.2 · 위 음 0.14 · 단음 0.32, 구절 첫 화음(자리 0) ×1.25. 고리 소리 ×RINGV. (카메라 거리 ±20% 는 페이지가 곱한다.)
 * 고리   박마다 빛의 자리와 그 박에 낸 음(쉼이면 [])을 표본으로 남긴다. 박 t 에 s ∈ [t−LMAX, t−LMIN] 중 가장 이른 s
 *        (그리고 s ≥ 바로 앞에서 받아들인 t)로 |p_t − p_s| < EPS 인 것을 찾고, 표본 s..t 의 Vietoris–Rips H₁ 지속 막대를 직접 계산한다
 *        (Z₂ 경계행렬 열 축소, vrH1). 가장 긴 막대의 지속 ≥ THETA 면 고리가 생긴다. 같은 길을 오고 가면 가까워지지만 H₁ 이 없다 —
 *        '가까워짐' 만으로 세지 않는 이유(판정기 V8).
 *        고리 = {구간 [s,t], L = t−s, 구절 = 그 L박의 음(쉼 포함), 주기 P = L+1, 점들, 지속, 수명, 시작 박 = t+1}.
 *        고리는 닫힌 다음 박부터 [쉼, 구절[0], …, 구절[L−1]] 을 주기 L+1 로 되풀이한다 — hibari 왼손이 앞에 쉼 한 칸을 둔 33박인 것처럼.
 *        그래서 같은 길을 계속 돌면 나는 L박마다, 고리는 L+1박마다 → 한 바퀴에 한 박씩 어긋난다(hibari 의 위상 어긋남).
 *        이미 있는 고리와 거의 같으면(무게중심 < SAMEC, 길이 차 ≤ SAMEL) **다시 그린 것**: 수명을 되살리고 구절·점을 이번 바퀴 것으로,
 *        시작 박은 그대로(어긋남이 이어진다). 수명: 되풀이 LIFE 바퀴면 사그라진다. 고리가 감싼 면을 가로질러 날면(Newell 평면,
 *        평면에 투영한 다각형 안 — 가장자리에서 MARGIN 이상 안쪽) 고리가 울리고 수명 +PASS. 고리는 많아야 MAXR 개(넘치면 가장 오래된 것이 사라진다).
 * 사건   born(생김: 고리의 음을 아래에서 위로 여린 펼침화음) · pass(지남: 여린 화음) · redraw(다시 그림) · fade(사라짐: 가장 낮은 음 하나) ·
 *        mesh(맞물림: 두 고리의 되풀이 첫 박이 같은 박).
 * 예시   demo(true): 한 바퀴 32박짜리 원(반지름 DEMO_R)을 돌며 날갯짓 6번 → 4박 떨어짐 → 6번 → 4박 (1구절·2구절).
 *        그러면 첫 바퀴 = hibari 오른손 32스텝, t=32 에 고리 L=32·P=33 = hibari 왼손, 그 뒤 나와 고리가 한 바퀴에 한 박씩 벌어진다.
 *        128박(4바퀴) 뒤 목표를 가만히 둘 때와 같은 원(반지름 RO, 16박 = 한 구절)을 4바퀴 — 큰 원 안쪽으로 맞닿아 자리·방향이 이어진다.
 *        여기서 둘째 고리(L=16, P=17)가 생기고, 맴도는 원이 큰 고리 안을 오르내리며 큰 고리를 지난다. 192박마다 처음으로.
 *        ⚠ 처음엔 반지름이 절반(0.34)인 원을 같은 빠르기로 돌렸다 — 톱니(4박에 1.73 떨어짐)가 좁은 원에선 H₁ 지속 0.151 이라 고리가 되지 못했다.
 *          맴돌기 반지름 0.463 에선 0.38 (2026-10-07 측정).
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var SEC = HS.SEC, TAU = Math.PI * 2, BH = 2 / 6;             // BH = 칸 하나의 높이 (큐브 높이 2 를 여섯으로)
  var DEF = {
    DT: 1 / 120,            // 물리 한 걸음(초)
    FLOOR: -1, CEIL: 0.96,  // 바닥 · 빛이 오를 수 있는 끝 (큐브 천장은 1)
    CLIMB: 1 / 3,           // 날갯짓 한 번에 오르는 높이 = 한 칸
    HOP: 1 / 2,             // 바닥에서 뜰 때 첫 날갯짓 (반 칸 더)
    BOB: 0.06,              // 내리칠 때 더 튀었다가 올릴 때 가라앉는 몫 — 통통 튀는 길
    FALL: 4,                // 맨 위에서 이만큼(박) 떼면 칸 0 한가운데에 닿도록 G 를 정한다
    V: 0.40,                // 앞으로 가는 빠르기 (/초)
    W: 1.0,                 // 도는 빠르기 최대 (rad/초)
    ORBIT: 16,              // 목표를 가만히 두면 맴도는 한 바퀴(박) = hibari 한 구절 → 반지름 V·ORBIT·SEC/2π ≈ 0.46 (W 의 86% 로 돈다 — 남는 몫으로 흐트러짐을 바로잡는다)
    KORB: 2,                // 맴돌기 길잡이(벡터장)의 끌림: 반지름에서 벗어난 만큼 안·밖으로 꺾는다
    GAIN: 3,                // 방향 오차 1 rad 당 도는 빠르기 (W 에서 잘린다)
    WALL0: 0.6, WALL1: 0.95,// 벽: |x|·|z| 가 이 사이면 가운데 쪽을 0→1 로 섞고 더 세게 돈다
    CLIP: 0.9, HARD: 0.97,  // 목표점을 자르는 곳 · 빛이 넘지 못하는 곳
    EPS: 0.3,               // 되돌아옴 — |p_t − p_s| 가 이보다 작으면 후보
    THETA: 0.3,             // 고리 — 가장 긴 H₁ 막대의 지속이 이 이상
    LMIN: 6, LMAX: 40,      // 고리 길이(박)
    SAMEC: 0.25, SAMEL: 3,  // 다시 그림 — 무게중심 거리 · 길이 차
    LIFE: 8, PASS: 4, MAXR: 3, MARGIN: 0.1,
    HYS: 0.1,               // 지남: 고리 면의 한쪽에서 HYS 넘게 떨어졌다가 반대쪽으로 HYS 넘게 — 면을 스치며 통통 튀는 것(BOB)은 지남이 아니다
    DEFER: 0.15,            // 누른 때가 다음 박까지 이보다 가까우면(초) 그 박의 올리기를 한 박 미룬다
    TOGGLE: 2,              // 활공이 이만큼(박) 이상이면 다음 날기에서 구절을 바꾼다
    RINGV: 0.7,             // 고리 소리 세기
    DEMO_R: 0.68, DEMO_A: Math.PI / 2   // 예시 원의 반지름 · 출발 각(앞쪽 가운데)
  };

  // ── 작은 셈 ─────────────────────────────────────────────────────────────
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function wrap(a) { while (a > Math.PI) a -= TAU; while (a < -Math.PI) a += TAU; return a; }
  function smooth01(u) { u = clamp(u, 0, 1); return u * u * (3 - 2 * u); }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function norm(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function d3(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  function centroid(P) { var c = [0, 0, 0]; P.forEach(function (p) { c[0] += p[0]; c[1] += p[1]; c[2] += p[2]; }); return [c[0] / P.length, c[1] / P.length, c[2] / P.length]; }
  function diam(P) { var m = 0; for (var i = 0; i < P.length; i++) for (var j = i + 1; j < P.length; j++) { var d = d3(P[i], P[j]); if (d > m) m = d; } return m; }

  /** Vietoris–Rips H₁ 지속 막대 — Z₂ 경계행렬 열 축소. P = [[x,y,z]…] (점 41개면 10660 삼각형).
   *  거리는 Math.fround — ripser 가 거리를 float32 로 다루므로 같은 값으로 잰다(판정기 V1 이 막대를 1e-9 로 대조한다).
   *  변 전부와 삼각형 전부를 넣으므로 H₁ 은 모두 죽는다 → 양의 변(m − n + 1 개)이 다 짝을 찾으면 멈춘다.
   *  돌려주는 것 = [[탄생, 죽음]…] (지속 > 0 만, 긴 것부터). */
  function vrH1(P) {
    var n = P.length, i, j, k, r, z; if (n < 3) return [];
    var m = n * (n - 1) / 2, el = new Float64Array(m), ea = new Int32Array(m), eb = new Int32Array(m), ord = new Int32Array(m), e = 0;
    for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) { var dx = P[i][0] - P[j][0], dy = P[i][1] - P[j][1], dz = P[i][2] - P[j][2];
      el[e] = Math.fround(Math.sqrt(dx * dx + dy * dy + dz * dz)); ea[e] = i; eb[e] = j; ord[e] = e; e++; }
    ord.sort(function (a, b) { return el[a] - el[b] || a - b; });
    var R = new Int32Array(n * n), len = new Float64Array(m);
    for (r = 0; r < m; r++) { e = ord[r]; len[r] = el[e]; R[ea[e] * n + eb[e]] = r; R[eb[e] * n + ea[e]] = r; }
    // 삼각형을 가장 긴 변의 순번으로 묶는다 (= 지름 순서; 같은 지름은 변의 순서로) — 셈 정렬
    var NT = n * (n - 1) * (n - 2) / 6, HI = new Int32Array(NT), TA = new Int32Array(NT), TB = new Int32Array(NT), TC = new Int32Array(NT), cnt = new Int32Array(m + 1), q = 0;
    for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) { var rij = R[i * n + j];
      for (k = j + 1; k < n; k++) { var a = rij, b = R[i * n + k], c = R[j * n + k], h = a > b ? (a > c ? a : c) : (b > c ? b : c);
        TA[q] = a; TB[q] = b; TC[q] = c; HI[q] = h; cnt[h + 1]++; q++; } }
    for (r = 0; r < m; r++) cnt[r + 1] += cnt[r];
    var fill = cnt.slice(0, m), T3 = new Int32Array(NT * 3);
    for (q = 0; q < NT; q++) { z = fill[HI[q]]++; T3[z * 3] = TA[q]; T3[z * 3 + 1] = TB[q]; T3[z * 3 + 2] = TC[q]; }
    // 열 축소: 열 = 삼각형의 경계(변 셋). low = 가장 늦은 변. 같은 low 의 열이 이미 있으면 더한다(XOR).
    var Wd = (m + 31) >>> 5, piv = new Array(m), col = new Uint32Array(Wd), out = [], need = m - n + 1, got = 0, w, pc, l;
    for (var hh = 0; hh < m && got < need; hh++) for (z = cnt[hh]; z < cnt[hh + 1]; z++) {
      col.fill(0);
      for (k = 0; k < 3; k++) { e = T3[z * 3 + k]; col[e >>> 5] ^= 1 << (e & 31); }
      l = hh;
      while (l >= 0 && piv[l]) { pc = piv[l]; for (w = 0; w < pc.length; w++) col[w] ^= pc[w];
        l = -1; for (w = pc.length - 1; w >= 0; w--) if (col[w]) { l = (w << 5) + 31 - Math.clz32(col[w]); break; } }
      if (l >= 0) { piv[l] = col.slice(0, (l >>> 5) + 1); got++; if (len[hh] > len[l]) out.push([len[l], len[hh]]); }
    }
    return out.sort(function (x, y) { return (y[1] - y[0]) - (x[1] - x[0]); });
  }

  /** 닫힌 꺾은선의 평면 (Newell 법) — 법선 n, 무게중심 c, 평면 안 축 u·v, 평면에 투영한 다각형 poly. 넓이가 거의 0 이면 null. */
  function plane(pts) {
    var n = pts.length, N3 = [0, 0, 0], c = centroid(pts);
    for (var i = 0; i < n; i++) { var a = pts[i], b = pts[(i + 1) % n];
      N3[0] += (a[1] - b[1]) * (a[2] + b[2]); N3[1] += (a[2] - b[2]) * (a[0] + b[0]); N3[2] += (a[0] - b[0]) * (a[1] + b[1]); }
    var nl = Math.hypot(N3[0], N3[1], N3[2]); if (nl < 1e-6) return null;
    var nn = [N3[0] / nl, N3[1] / nl, N3[2] / nl], ax = Math.abs(nn[0]) < 0.6 ? [1, 0, 0] : [0, 1, 0], u = norm(cross(nn, ax)), v = cross(nn, u);
    return { c: c, n: nn, u: u, v: v, area: nl / 2, poly: pts.map(function (p) { var d = sub(p, c); return [dot(d, u), dot(d, v)]; }) };
  }
  function inside(q, poly) { var c = false;   // 짝홀 규칙
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) { var a = poly[i], b = poly[j];
      if ((a[1] > q[1]) !== (b[1] > q[1]) && q[0] < (b[0] - a[0]) * (q[1] - a[1]) / (b[1] - a[1]) + a[0]) c = !c; }
    return c; }
  function edgeDist(q, poly) { var best = Infinity;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) { var a = poly[j], b = poly[i], dx = b[0] - a[0], dy = b[1] - a[1],
      u = clamp(((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / (dx * dx + dy * dy || 1), 0, 1); best = Math.min(best, Math.hypot(a[0] + u * dx - q[0], a[1] + u * dy - q[1])); }
    return best; }

  /** H.mod[0](오른손 모듈)에서 두 구절 × 자리 여섯의 화음–단음 짝을 찾는다. 구절 = 쉼 없이 이어진 스텝 묶음, 그 안에서 화음 다음 단음. */
  function phrases(H) {
    var st = H.mod[0].steps, out = [], cur = null;
    for (var t = 0; t < st.length; t++) {
      if (!st[t].length) { cur = null; continue; }
      if (!cur) { cur = { at: t, chord: [], single: [] }; out.push(cur); }
      var off = t - cur.at;
      if (off % 2 === 0) { if (st[t].length < 2) throw new Error('구절 ' + out.length + ' 의 스텝 ' + t + ' 가 화음이 아니다'); cur.chord.push(st[t].slice()); }
      else { if (st[t].length !== 1) throw new Error('스텝 ' + t + ' 가 단음이 아니다'); cur.single.push(st[t].slice()); }
    }
    if (out.length !== 2 || out.some(function (f) { return f.chord.length !== 6 || f.single.length !== 6; })) throw new Error('hibari 오른손이 두 구절 × 자리 여섯이 아니다');
    return out;
  }

  function create(H, opts) {
    opts = opts || {};
    var C = {}, key; for (key in DEF) C[key] = key in opts ? opts[key] : DEF[key];
    var N = H.notes, PH = phrases(H), SM = new Array(128);
    function mid(k) { return C.FLOOR + (k + 0.5) * BH; }
    function band(y) { var k = Math.floor((y - C.FLOOR) / BH); return k < 0 ? 0 : k > 5 ? 5 : k; }
    var G = 2 * (C.CEIL - C.BOB - mid(0)) / Math.pow(C.FALL * SEC, 2);   // 올리기 끝(맨 위)에서 FALL 박 = 칸 0 한가운데
    var RO = C.V * C.ORBIT * SEC / TAU;                                  // 맴도는 반지름 (≈ 0.463)
    var S = { time: 0, beat: 0, x: 0, y: C.FLOOR, z: 0.5, head: -Math.PI / 2, mode: 'sit', hold: false, tRel: -1e9, yRel: C.FLOOR,
              st: null, next: null, ph: -1, k: 0, pend: null, tx: 0, tz: 0, lam: 0, om: 0, rings: [], lastAcc: -1e9, close: null, cand: 0, lastCand: null,
              out: [], ev: [], pilot: null, demo: null, id: 0, first: 0, flaps: 0 };
    function get(b) { var s = SM[((b % 128) + 128) % 128]; return s && s.t === b ? s : null; }
    function put(s) { SM[((s.t % 128) + 128) % 128] = s; }

    // ── 높이 (해석식) ───────────────────────────────────────────────────
    function yAt(t) {
      if (S.mode === 'sit') return C.FLOOR;
      if (S.mode === 'glide') { var u = t - S.tRel, y = S.yRel - 0.5 * G * u * u; return y < C.FLOOR ? C.FLOOR : y; }
      var s = S.st, f = clamp((t - s.t0) / (s.t1 - s.t0 || 1), 0, 1), g = s.down ? 1 - (1 - f) * (1 - f) : f * f * (3 - 2 * f);
      return s.y0 + (s.y1 - s.y0) * g;   // 내리치기: 처음에 빨리 튀어 오른다 · 올리기: 부드럽게 가라앉는다
    }
    function stroke(down, t0, t1, hop) {
      var y0 = S.y, y1 = down ? Math.min(C.CEIL, y0 + (hop ? C.HOP : C.CLIMB) + C.BOB) : Math.max(C.FLOOR, y0 - C.BOB);
      S.st = { down: down, t0: t0, t1: t1, y0: y0, y1: y1 };
    }
    // ── 음 ──────────────────────────────────────────────────────────────
    function chordNotes(ph, k) { var ls = PH[ph].chord[k], lo = Math.min.apply(null, ls.map(function (li) { return N[li].pitch; })), acc = k === 0 ? 1.25 : 1;
      return ls.map(function (li) { return { li: li, v: (N[li].pitch === lo ? 0.2 : 0.14) * acc }; }); }
    function singleNotes(ph, k) { return PH[ph].single[k].map(function (li) { return { li: li, v: 0.32 }; }); }
    function note(q, at, off, src, pos, ring, now, vk) { var nt = N[q.li];
      return { pitch: nt.pitch, li: q.li, name: nt.name, pc: nt.pc, dur: q.d || nt.dur * SEC, vel: q.v * (vk || 1), at: at, off: off || 0, src: src, pos: pos, ring: ring || 0, now: !!now }; }
    function emit(ns, at, src, pos, ring, vk) { ns.forEach(function (q, i) { S.out.push(note(q, at, ns.length > 1 ? i * 0.012 : 0, src, pos, ring, false, vk)); }); }
    function pitchesOf(R) { var seen = {}, ps = []; R.phrase.forEach(function (ns) { ns.forEach(function (q) { var p = N[q.li].pitch; if (!seen[p]) { seen[p] = 1; ps.push(q.li); } }); });
      return ps.sort(function (a, b) { return N[a].pitch - N[b].pitch; }); }

    // ── 누르기 · 떼기 ───────────────────────────────────────────────────
    /** 누른 그 호출에서 내리치기 음을 돌려준다(페이지가 when 없이 곧바로 울린다).
     *  올리기 = 다음 박, 다음 박까지 DEFER 초 미만이면 그다음 박. 내리치기의 기록 = **올리기 바로 앞 박** —
     *  누른 때가 박 안 0~0.5 면 지난 박(= 가장 가까운 박), 0.67~1 이면 다음 박(= 가장 가까운 박),
     *  0.5~0.67 이면 가장 가까운 박은 다음 박이지만 그 박에 올리기가 오므로 지난 박에 넣는다(한 박에 화음과 단음이 겹치지 않게). */
    function doPress() {
      if (S.hold) return [];
      var t = S.time, n = S.beat, fromFloor = S.mode === 'sit', glide = (t - S.tRel) / SEC;
      S.hold = true;
      if (S.ph < 0) S.ph = 0; else if (S.mode !== 'flap' && glide >= C.TOGGLE - 1e-9) S.ph = 1 - S.ph;
      S.y = yAt(t); var k = band(S.y), up = n + 1;
      if ((n + 1) * SEC - t < C.DEFER) up = n + 2;
      var r = up - 1, has = get(r);
      if (has && has.notes.length) { r++; up++; }               // 그 박에 이미 음(방금 낸 올리기)이 있으면 한 박 뒤로
      S.k = k; S.mode = 'flap'; S.flaps++; stroke(true, t, up * SEC, fromFloor); S.next = { beat: up, down: false };
      var ns = chordNotes(S.ph, k), pos = [S.x, S.y, S.z];
      if (r <= n && get(r)) get(r).notes = ns; else S.pend = { beat: r, notes: ns };
      S.lastDown = { at: t, k: k, ph: S.ph };
      return ns.map(function (q, i) { return note(q, t, i * 0.012, 'me', pos, 0, true); });
    }
    function release() {
      if (!S.hold) return;
      S.y = yAt(S.time); S.hold = false; S.next = null; S.st = null; S.tRel = S.time; S.yRel = S.y;
      S.mode = S.y <= C.FLOOR + 1e-9 ? 'sit' : 'glide';
    }

    // ── 수평: 목표점으로 돈다 ───────────────────────────────────────────
    /** 가고 싶은 방향. 멀면 목표 쪽으로, 가까우면 목표를 가운데 둔 반지름 RO 의 원으로 — 맴돌기 벡터장
     *  χ = γ + λ(π/2 + atan(KORB·(d − RO)/RO)) (γ = 목표에서 본 빛의 방향, λ = 도는 쪽). 처음엔 '향하기 + 도는 빠르기 상한' 만 썼더니
     *  맴도는 원의 가운데가 목표 둘레를 천천히 돌아(세차) 바퀴마다 무게중심이 0.25~0.3 씩 옮겨 가 같은 고리가 매번 새 고리가 됐다(2026-10-07 측정). */
    function desire() {
      var dx = S.x - S.tx, dz = S.z - S.tz, d = Math.hypot(dx, dz);
      if (d < 1e-6) return S.head;
      if (S.lam === 0 || d > 2.5 * RO) S.lam = dx * Math.sin(S.head) - dz * Math.cos(S.head) >= 0 ? 1 : -1;   // 지금 도는 쪽을 따른다(가까이선 바꾸지 않는다)
      return Math.atan2(dz, dx) + S.lam * (Math.PI / 2 + Math.atan(C.KORB * (d - RO) / RO));
    }
    function turnRate() {
      var want = desire(), wx = Math.cos(want), wz = Math.sin(want);
      var m = Math.max(Math.abs(S.x), Math.abs(S.z)), w = smooth01((m - C.WALL0) / (C.WALL1 - C.WALL0));
      if (w > 0) { var cl = Math.hypot(S.x, S.z) || 1; wx = wx * (1 - w) - 2 * w * S.x / cl; wz = wz * (1 - w) - 2 * w * S.z / cl; }   // 벽 가까이선 가운데 쪽을 섞는다
      // 앞먹임 = 목표에서 본 빛의 방향이 도는 빠르기(γ̇). 이것 없이 비례 조향만 쓰면 원 위에서도 0.29 rad 를 늘 뒤처져
      // 맴도는 반지름이 0.52(한 바퀴 18박)로 부풀었다(2026-10-07 측정).
      var dx = S.x - S.tx, dz = S.z - S.tz, d = Math.max(Math.hypot(dx, dz), RO / 2), ff = C.V * Math.sin(S.head - Math.atan2(dz, dx)) / d;
      var lim = C.W * (1 + 2 * w);
      return clamp(ff * (1 - w) + C.GAIN * wrap(Math.atan2(wz, wx) - S.head), -lim, lim);
    }
    function steer(h) {
      if (S.mode === 'sit') { S.head = wrap(S.head + clamp(C.GAIN * wrap(Math.atan2(S.tz - S.z, S.tx - S.x) - S.head), -C.W, C.W) * h); return; }   // 앉아서는 제자리에서 목표 쪽으로 몸만 돌린다
      S.om = turnRate(); S.head = wrap(S.head + S.om * h);
      S.x = clamp(S.x + C.V * Math.cos(S.head) * h, -C.HARD, C.HARD); S.z = clamp(S.z + C.V * Math.sin(S.head) * h, -C.HARD, C.HARD);
    }
    /** 지금 그대로 둔다면 다음 박의 자리 — 고리가 닫히는 박을 '가장 가까이 돌아온 박' 으로 고르는 데 쓴다 */
    function predict(t) {
      var y = yAt(t + SEC);
      if (S.pilot) { var q = S.pilot(t + SEC); return [q.x, y, q.z]; }
      if (S.mode === 'sit') return [S.x, y, S.z];
      var hm = S.head + (S.om || 0) * SEC / 2, l = C.V * SEC;
      return [S.x + l * Math.cos(hm), y, S.z + l * Math.sin(hm)];
    }
    function integrate(h) {
      var t1 = S.time + h, p0 = [S.x, S.y, S.z];
      S.y = yAt(t1); if (S.mode === 'glide' && S.y <= C.FLOOR) { S.y = C.FLOOR; S.mode = 'sit'; }
      if (S.pilot) { var q = S.pilot(t1); S.x = q.x; S.z = q.z; S.head = q.head; } else steer(h);
      S.time = t1;
      passCheck(p0, [S.x, S.y, S.z]);
    }
    function advance(sec) {
      var end = S.time + sec;
      while (S.time < end - 1e-12) {
        var nb = (S.beat + 1) * SEC, h = Math.min(C.DT, end - S.time, nb - S.time);
        if (h > 0) integrate(h);
        if (S.time >= nb - 1e-12) { S.time = nb; beat(S.beat + 1); }
      }
    }

    // ── 박 ──────────────────────────────────────────────────────────────
    function beat(b) {
      S.beat = b; var t = b * SEC, notes = null;
      if (S.demo) demoBeat(b);
      if (S.mode === 'flap' && S.next && S.next.beat === b) {
        S.y = yAt(t);
        if (S.next.down) { S.k = band(S.y); notes = chordNotes(S.ph, S.k); S.lastDown = { at: t, k: S.k, ph: S.ph }; } else notes = singleNotes(S.ph, S.k);
        stroke(S.next.down, t, t + SEC); S.next = { beat: b + 1, down: !S.next.down };
        emit(notes, t, 'me', [S.x, S.y, S.z]);
      }
      if (S.pend && S.pend.beat === b) { if (!notes) notes = S.pend.notes; S.pend = null; }
      put({ t: b, p: [S.x, S.y, S.z], notes: notes || [] });
      playRings(b);
      detect(b);
    }
    function playRings(b) {
      var heads = [];
      S.rings = S.rings.filter(function (R) {
        if (b < R.start) return true;
        var k = (b - R.start) % R.P; R.k = k;
        if (k === 0) { if (b > R.start) { R.lap++; R.life--; if (R.life <= 0) { fade(R); return false; } } heads.push(R.id); }
        else if (R.phrase[k - 1].length) emit(R.phrase[k - 1], b * SEC, 'ring', R.pts[k - 1], R.id, C.RINGV);
        return true;
      });
      if (heads.length > 1) S.ev.push({ type: 'mesh', at: b * SEC, rings: heads });
    }
    /** 되돌아옴 찾기. 박 b 에 s ∈ [b−LMAX, b−LMIN] (s ≥ 바로 앞에서 받아들인 t) 중 가장 이른 s 로 |p_b − p_s| < EPS 이면 후보.
     *  닫히는 박 = **가장 가까이 돌아온 박**: 다음 박이 더 가까울 것 같으면(predict) 한 박 기다리고, 실제로 멀어졌으면 지난 박으로 닫는다.
     *  (EPS 0.3 > 한 박 걸음 0.18 이라 '처음 가까워진 박' 으로 닫으면 16박 바퀴가 늘 15박 고리가 됐다 — 2026-10-07 측정.)
     *  늦게 닫혀도(t = b−1) 고리는 t+1 = b 부터 [쉼 …] 이라 b 의 쉼 자리에서 시작한다 — 놓치는 소리가 없다. */
    function detect(b) {
      var cur = get(b), P0 = S.close, t, sp;
      if (P0) {
        S.close = null; sp = get(P0.s); if (!sp) return;
        var dd = d3(cur.p, sp.p);
        if (dd < P0.d && b - P0.s <= C.LMAX) {
          if (d3(predict(b * SEC), sp.p) < dd - 0.02 && b + 1 - P0.s <= C.LMAX) { S.close = { s: P0.s, t: b, d: dd }; return; }
          return tryRing(P0.s, b);
        }
        return tryRing(P0.s, P0.t);                                    // 멀어졌다 — 지난 박이 가장 가까웠다
      }
      var lo = Math.max(b - C.LMAX, S.lastAcc, S.first), s = -1;
      for (t = lo; t <= b - C.LMIN; t++) { var sm = get(t); if (sm && d3(sm.p, cur.p) < C.EPS) { s = t; break; } }
      if (s < 0) return;
      var d0 = d3(cur.p, get(s).p);
      if (d3(predict(b * SEC), get(s).p) < d0 - 0.02 && b + 1 - s <= C.LMAX) { S.close = { s: s, t: b, d: d0 }; return; }
      tryRing(s, b);
    }
    function tryRing(s, b) {
      var pts = [], t; for (t = s; t <= b; t++) { var sm = get(t); if (!sm) return; pts.push(sm.p); }
      S.cand++;
      var pers = 0; if (diam(pts) >= C.THETA) { var bars = vrH1(pts); if (bars.length) pers = bars[0][1] - bars[0][0]; }   // 지름 < θ 면 지속도 < θ
      S.lastCand = { s: s, t: b, pers: pers, at: S.beat };
      if (pers < C.THETA) return;
      S.lastAcc = b;
      var L = b - s, phrase = [], body = pts.slice(0, L), c = centroid(body);
      for (t = s; t < b; t++) phrase.push(get(t).notes);
      var same = null; S.rings.forEach(function (R) { if (!same && d3(R.c, c) < C.SAMEC && Math.abs(R.L - L) <= C.SAMEL) same = R; });
      if (same) { same.s = s; same.t = b; same.L = L; same.P = L + 1; same.phrase = phrase; same.pts = pts; same.c = c; same.pers = pers;   // 시작 박은 그대로
        same.life = C.LIFE; same.plane = plane(body); same.side = 0; same.redrawn++; same.tRedraw = S.time;
        S.ev.push({ type: 'redraw', at: S.time, ring: same.id, P: same.P }); return; }
      var R = { id: ++S.id, born: b, seen: S.beat, s: s, t: b, L: L, P: L + 1, start: b + 1, phrase: phrase, pts: pts, c: c, pers: pers, life: C.LIFE, lap: 0, k: 0,
                side: 0, crossIn: false, redrawn: 0, passes: 0, plane: plane(body), tBorn: S.time, tRedraw: -1e9, tPass: -1e9 };
      S.rings.push(R);
      if (S.rings.length > C.MAXR) fade(S.rings.shift());
      var ps = pitchesOf(R);                                          // 생김: 고리의 음을 아래에서 위로 여린 펼침화음
      ps.forEach(function (li, i) { S.out.push(note({ li: li, v: 0.075, d: 1.6 }, S.time, 0.05 + i * 0.055, 'event', R.c, R.id)); });
      S.ev.push({ type: 'born', at: S.time, ring: R.id, P: R.P, L: R.L, pers: pers });
    }
    function fade(R) {
      var ps = pitchesOf(R); if (ps.length) S.out.push(note({ li: ps[0], v: 0.13, d: 1.8 }, S.time, 0.02, 'event', R.c, R.id));
      S.ev.push({ type: 'fade', at: S.time, ring: R.id, pts: R.pts.slice(0, R.L) });
    }
    function clearRings() { var rs = S.rings; S.rings = []; rs.forEach(fade); }
    /** 지남 = 고리 면의 한쪽(HYS 넘게)에서 반대쪽(HYS 넘게)으로 건너갔고, 그 사이 면을 뚫은 자리가 다각형 안(가장자리에서 MARGIN 넘게)이었다.
     *  면을 스치며 통통 튀는 것(맨 위에서 납작한 고리를 맴돌 때 BOB 0.06)은 HYS 를 못 넘는다. 제 고리를 다시 날 때 면을 뚫는 자리는 가장자리라 MARGIN 에 걸린다. */
    function passCheck(p0, p1) {
      S.rings.forEach(function (R) {
        var Q = R.plane; if (!Q) return;
        var d0 = dot(sub(p0, Q.c), Q.n), d1 = dot(sub(p1, Q.c), Q.n);
        if ((d0 > 0) !== (d1 > 0) && d0 !== d1) {                       // 면을 뚫었다 — 그 자리가 안쪽인가
          var f = d0 / (d0 - d1), qd = sub([p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f, p0[2] + (p1[2] - p0[2]) * f], Q.c), q2 = [dot(qd, Q.u), dot(qd, Q.v)];
          R.crossIn = inside(q2, Q.poly) && edgeDist(q2, Q.poly) >= C.MARGIN;
        }
        if (Math.abs(d1) < C.HYS) return;
        var side = d1 > 0 ? 1 : -1, was = R.side; R.side = side;
        if (!was || was === side || !R.crossIn) return;
        R.crossIn = false;
        R.life = Math.min(R.life + C.PASS, 2 * C.LIFE); R.passes++; R.tPass = S.time;
        var ps = pitchesOf(R), pick = []; for (var i = 0; i < Math.min(6, ps.length); i++) pick.push(ps[Math.round(i * (ps.length - 1) / Math.max(1, Math.min(6, ps.length) - 1))]);
        pick.forEach(function (li, i) { S.out.push(note({ li: li, v: 0.09, d: 1.1 }, S.time, i * 0.016, 'event', R.c, R.id)); });
        S.ev.push({ type: 'pass', at: S.time, ring: R.id });
      });
    }

    // ── 예시: 32박 원 4바퀴 → 맴도는 원(반지름 RO, 16박 = 한 구절) 4바퀴 → 처음으로 (192박) ──────────
    function demoPilot(t) {
      var q = t / SEC - S.demo.start, r = C.DEMO_R, a0 = C.DEMO_A;
      if (q < 128) { var a = a0 + TAU * q / 32; return { x: r * Math.cos(a), z: r * Math.sin(a), head: wrap(a + Math.PI / 2) }; }
      var bb = a0 + TAU * (q - 128) / C.ORBIT;                         // 큰 원 안쪽으로 맞닿은 원 — 맞닿는 곳에서 자리·방향이 같다(빠르기만 V 로 오른다)
      return { x: (r - RO) * Math.cos(a0) + RO * Math.cos(bb), z: (r - RO) * Math.sin(a0) + RO * Math.sin(bb), head: wrap(bb + Math.PI / 2) };
    }
    function demoBeat(b) {
      var D = S.demo, q = b - D.start;
      if (q >= 192) { D.start = b; q = 0; clearRings(); S.lastAcc = b; }
      var w = q < 128 ? q % 16 : (q - 128) % 16, outN;
      if (w === 0) { outN = doPress(); outN.forEach(function (x) { x.now = false; S.out.push(x); }); }   // 예시는 박에 맞춰 예약한다
      else if (w === 12) release();
    }
    function demo(on) {
      if (!on) { if (S.demo && S.hold) release(); S.demo = null; S.pilot = null; S.lastAcc = S.beat; return; }   // 자동 조종이 누르고 있던 것을 놓는다 · 고리는 손으로 난 길에서만 (예시 길과 이어 닫히지 않게)
      var b1 = S.beat + 1; S.demo = { start: b1 }; S.pilot = demoPilot;
      clearRings(); S.lastAcc = b1; S.ph = -1; S.hold = false; S.next = null; S.st = null; S.pend = null;
      S.mode = 'glide'; S.tRel = (b1 - C.FALL) * SEC; S.yRel = C.CEIL - C.BOB; S.y = yAt(S.time);   // 4박 전에 맨 위에서 뗀 것처럼 떨어지는 중
      var p = demoPilot(S.time); S.x = p.x; S.z = p.z; S.head = p.head;
    }

    function place(o) {   // 검증·처음 자리: 빛을 옮긴다 (y 가 바닥이면 앉고, 아니면 그 자리에서 활공을 시작한다)
      if (S.hold) release();
      if (o.x != null) S.x = o.x; if (o.z != null) S.z = o.z; if (o.head != null) S.head = o.head;
      if (o.y != null) { S.y = o.y; S.st = null; S.next = null; S.tRel = S.time; S.yRel = o.y; S.mode = o.y <= C.FLOOR + 1e-9 ? 'sit' : 'glide'; }
    }
    function probe() {
      return { time: S.time, beat: S.beat, mode: S.mode, hold: S.hold, pos: [S.x, S.y, S.z], head: S.head, band: band(S.y), phrase: S.ph, demo: !!S.demo,
        target: [S.tx, S.tz], cand: S.cand, lastCand: S.lastCand, flaps: S.flaps,
        rings: S.rings.map(function (R) { return { id: R.id, L: R.L, P: R.P, start: R.start, born: R.born, life: R.life, lap: R.lap, pers: R.pers, k: R.k, redrawn: R.redrawn, passes: R.passes, c: R.c }; }) };
    }

    put({ t: 0, p: [S.x, S.y, S.z], notes: [] });
    return {
      press: doPress, release: release, advance: advance, demo: demo, place: place, probe: probe, clearRings: clearRings,
      target: function (x, z) { S.tx = clamp(x, -C.CLIP, C.CLIP); S.tz = clamp(z, -C.CLIP, C.CLIP); },
      pilot: function (f) { S.pilot = f || null; },
      drain: function () { var o = { notes: S.out, events: S.ev }; S.out = []; S.ev = []; return o; },
      sample: get, rings: function () { return S.rings; }, band: band, mid: mid, G: G, RO: RO, C: C, PH: PH, state: S
    };
  }

  var API = { create: create, vrH1: vrH1, plane: plane, inside: inside, edgeDist: edgeDist, phrases: phrases, DEF: DEF, SEC: SEC };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSFlight = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
