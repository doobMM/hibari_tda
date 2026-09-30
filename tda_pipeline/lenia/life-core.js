/* life-core.js — 종달새와 문어 3판: 살아 있는 격자 (docs/tonnetz_lenia_spec.md §10)
 * 페이지(life.html)와 검증(tools/verify_life.mjs)이 **같은 이 파일**을 돌린다.
 *
 * ── 상태 ────────────────────────────────────────────────────────────────
 *   고운 격자 256 × 128 (Tonnetz 토러스 288칸 20.78 × 12 를 촘촘히 표본). 칸마다
 *     A_c ∈ [0,1]  손 c 의 생명 (c = 0 종달새·오른손, 1 문어·왼손)
 *     F_c ∈ [0,1]  손 c 의 자리 피로 (발자국 — 약하다)
 *     age_c ≥ 0    손 c 의 몸의 피로 = 나이 (몸이 지고 다닌다 — 세다)
 *   고운 칸마다 그 자리의 Tonnetz 칸 → 그 칸의 hibari 음(음역 지형). 검은 건반 칸은 음이 없다.
 * ── 갱신 규칙 (이웃만 본다 — mathematical idea stays local) ─────────────────
 *   U_c = K ∗ A_c                              Lenia 고리 커널 (반지름 13칸) — 이웃과의 관계가 모양을 만든다
 *   A_c ← clip(A_c + (G(U_c) + b·비옥도_c + 먹이_c + 끌기_c − κ·F_c − κ'·age_c) / T, 0, 1)
 *   F_c ← F_c + up·A_c·(1 − F_c) − down·F_c   산 자리에 쌓이고 천천히 풀린다
 *   age_c ← (3×3 이웃 중 몸 속(A ≥ 0.3)의 나이 평균) + AGE,  먹이·끌기가 닿은 칸은 ×(1 − YOUNG),  생명이 떠난 칸은 ×0.9
 *                                              균형 회로: 방치하면 늙어 사그라지고(≈2~3분), 돌보면(몰기·부르기·먹이) 젊어진다
 *   G = 2·exp(−(U−μ)²/2σ²) − 1                 Lenia 종 모양 (도넛: 너무 적거나 많으면 준다)
 * ── 비옥도 = 사용자의 설계 intra + rate × inter — **기본 끔 (FERT 0, v3.2)** ─────────────────────
 *   ⚠ 켜면 돌봄을 벌했다(몸 속까지 채워 과성장으로 무너진다 — 명세 §10.11). 아래 식은 이웃 합이지만 격자 전체 최댓값으로 나눠
 *   **엄밀히 국소가 아니다**(먼 손의 위치·rate 가 정규화로 들어온다). 사용자의 intra·inter 는 지금 rate → 바코드 → 소리 통로로 닿는다.
 *   Tonnetz 칸 i 의 비옥도_c = Σ_{j ∈ i 의 6-이웃} M_c(j)·intra_c(음 j → 음 i) + rate · M_c'(j)·inter(음 j → 음 i)
 *   M_c(j) = 손 c 가 이웃 칸 j 에 가진 생명의 양. intra_c = 그 손 안에서 음 j 다음에 음 i 가 오는 정도,
 *   inter = 두 손 사이(lag 1)에서 그렇게 오는 정도 — 정본 경로의 가중치(tonnetz.json note_weights). 자기 칸은 뺀다
 *   (intra 는 같은 음 반복이 가장 커서, 넣으면 제자리를 가장 비옥하게 한다 — 1회차 전역식이 움직임을 못 바꾼 이유).
 *   → 의도: 생명체가 **이웃 칸 중 hibari 에서 지금 음 다음에 오던 음** 쪽으로 자란다 (2회차 X3b — 부호만 맞고 판별 불가).
 * ── 소리 = 우리 메커니즘 ─────────────────────────────────────────────────
 *   손마다 제 리듬(오른손 32 · 왼손 33 고리)으로 운다. 그 손이 지금 덮은 음 → 고리 활성도(그 순간) → τ →
 *   그 rate 에 살아 있는 고리 → 한 행 → Algorithm 1.   켜진 고리는 바코드의 지금 rate 칸을 채운다.
 * ── 몰기 ────────────────────────────────────────────────────────────────
 *   원하는 방향이 있으면 머리 옆(목표 쪽)에 **끌기**(성장 가산 원반)를 둔다 → 그쪽으로 돈다. 질량을 더하면 오히려 밀어낸다(명세 §10.6).
 *   누르고 있으면 0.15 에서 약 7초에 걸쳐 0.30 으로 세지고, 질량이 48~90 밖이면 쉰다. 0.35 는 속까지 채워 과식으로 무너뜨렸다(§10.7 X4).
 *   태어난 뒤 12박은 몰지 않는다.
 *   음 부르기(Z~M): 그 음이름 칸 중 가까운 곳에 약한 끌기(0.15). 문어는 몰지 않으면 약하게 한쪽으로 돈다 — 왼손의 어긋남을 길의 휘어짐으로.
 */
(function (root) {
  'use strict';
  var NX = 256, NY = 128, S3 = Math.sqrt(3) / 2, W = 24 * S3, H = 12, DX = W / NX, DY = H / NY;
  var DIRS = [[1, 0, 7], [-1, 0, 5], [0, 1, 4], [0, -1, 8], [1, -1, 3], [-1, 1, 9]];

  // ── FFT (radix-2, 제자리, 미리 계산한 회전 인자) ─────────────────────────
  function plan(n) {
    var rev = new Uint32Array(n), bits = Math.round(Math.log2(n));
    for (var i = 0; i < n; i++) { var r = 0; for (var b = 0; b < bits; b++) r |= ((i >> b) & 1) << (bits - 1 - b); rev[i] = r; }
    var cs = new Float64Array(n / 2), sn = new Float64Array(n / 2);
    for (i = 0; i < n / 2; i++) { cs[i] = Math.cos(2 * Math.PI * i / n); sn[i] = Math.sin(2 * Math.PI * i / n); }
    return { n: n, rev: rev, cs: cs, sn: sn };
  }
  var PX = plan(NX), PY = plan(NY);
  function fft1(re, im, off, stride, p, inv) {
    var n = p.n, i, j, t;
    for (i = 0; i < n; i++) { j = p.rev[i]; if (i < j) { var a = off + i * stride, b = off + j * stride;
      t = re[a]; re[a] = re[b]; re[b] = t; t = im[a]; im[a] = im[b]; im[b] = t; } }
    for (var len = 2; len <= n; len <<= 1) {
      var half = len >> 1, step = n / len;
      for (i = 0; i < n; i += len) for (var k = 0; k < half; k++) {
        var wr = p.cs[k * step], wi = inv ? p.sn[k * step] : -p.sn[k * step];
        var ia = off + (i + k) * stride, ib = off + (i + k + half) * stride;
        var tr = re[ib] * wr - im[ib] * wi, ti = re[ib] * wi + im[ib] * wr;
        re[ib] = re[ia] - tr; im[ib] = im[ia] - ti; re[ia] += tr; im[ia] += ti;
      }
    }
  }
  function fft2(re, im, inv) {
    for (var y = 0; y < NY; y++) fft1(re, im, y * NX, 1, PX, inv);
    for (var x = 0; x < NX; x++) fft1(re, im, x, NX, PY, inv);
    if (inv) { var s = 1 / (NX * NY); for (var i = 0; i < re.length; i++) { re[i] *= s; im[i] *= s; } }
  }
  function kernel(Rcells) {                       // 세계 좌표에서 원이 되는 Lenia 고리 커널의 FFT
    var Rw = Rcells * DX, re = new Float64Array(NX * NY), im = new Float64Array(NX * NY), s = 0;
    for (var y = 0; y < NY; y++) for (var x = 0; x < NX; x++) {
      var X = (x < NX / 2 ? x : x - NX) * DX, Y = (y < NY / 2 ? y : y - NY) * DY, r = Math.sqrt(X * X + Y * Y) / Rw;
      var k = r > 0 && r < 1 ? Math.exp(4 - 1 / (r * (1 - r))) : 0; re[y * NX + x] = k; s += k;
    }
    for (var i = 0; i < re.length; i++) re[i] /= s;
    fft2(re, im, false); return { re: re, im: im };
  }
  var ORBIUM = [[0,0,0,0,0,0,0.1,0.14,0.1,0,0,0.03,0.03,0,0,0.3,0,0,0,0],[0,0,0,0,0,0.08,0.24,0.3,0.3,0.18,0.14,0.15,0.16,0.15,0.09,0.2,0,0,0,0],[0,0,0,0,0,0.15,0.34,0.44,0.46,0.38,0.18,0.14,0.11,0.13,0.19,0.18,0.45,0,0,0],[0,0,0,0,0.06,0.13,0.39,0.5,0.5,0.37,0.06,0,0,0,0.02,0.16,0.68,0,0,0],[0,0,0,0.11,0.17,0.17,0.33,0.4,0.38,0.28,0.14,0,0,0,0,0,0.18,0.42,0,0],[0,0,0.09,0.18,0.13,0.06,0.08,0.26,0.32,0.32,0.27,0,0,0,0,0,0,0.82,0,0],[0.27,0,0.16,0.12,0,0,0,0.25,0.38,0.44,0.45,0.34,0,0,0,0,0,0.22,0.17,0],[0,0.07,0.2,0.02,0,0,0,0.31,0.48,0.57,0.6,0.57,0,0,0,0,0,0,0.49,0],[0,0.59,0.19,0,0,0,0,0.2,0.57,0.69,0.76,0.76,0.49,0,0,0,0,0,0.36,0],[0,0.58,0.19,0,0,0,0,0,0.67,0.83,0.9,0.92,0.87,0.12,0,0,0,0,0.22,0.07],[0,0,0.46,0,0,0,0,0,0.7,0.93,1,1,1,0.61,0,0,0,0,0.18,0.11],[0,0,0.82,0,0,0,0,0,0.47,1,1,0.98,1,0.96,0.27,0,0,0,0.19,0.1],[0,0,0.46,0,0,0,0,0,0.25,1,1,0.84,0.92,0.97,0.54,0.14,0.04,0.1,0.21,0.05],[0,0,0,0.4,0,0,0,0,0.09,0.8,1,0.82,0.8,0.85,0.63,0.31,0.18,0.19,0.2,0.01],[0,0,0,0.36,0.1,0,0,0,0.05,0.54,0.86,0.79,0.74,0.72,0.6,0.39,0.28,0.24,0.13,0],[0,0,0,0.01,0.3,0.07,0,0,0.08,0.36,0.64,0.7,0.64,0.6,0.51,0.39,0.29,0.19,0.04,0],[0,0,0,0,0.1,0.24,0.14,0.1,0.15,0.29,0.45,0.53,0.52,0.46,0.4,0.31,0.21,0.08,0,0],[0,0,0,0,0,0.08,0.21,0.21,0.22,0.29,0.36,0.39,0.37,0.33,0.26,0.18,0.09,0,0,0],[0,0,0,0,0,0,0.03,0.13,0.19,0.22,0.24,0.24,0.23,0.18,0.13,0.05,0,0,0,0],[0,0,0,0,0,0,0,0,0.02,0.06,0.08,0.09,0.07,0.05,0.01,0,0,0,0,0]];

  // ── Tonnetz 지도 (2판 waves-core.js 와 같은 토러스) ──────────────────────
  function buildGeo() {
    var C = 24, Rr = 12, nodes = [], idx = {};
    var red = function (c, r) { var b = Math.floor(c / C); c -= C * b; r += 12 * b; r = ((r % Rr) + Rr) % Rr; return [c, r]; };
    for (var c = 0; c < C; c++) for (var r = 0; r < Rr; r++) { idx[c * Rr + r] = nodes.length;
      nodes.push({ c: c, r: r, pc: (7 * c + 4 * r) % 12, x: S3 * c, y: (((0.5 * c + r) % H) + H) % H, nb: [] }); }
    nodes.forEach(function (n) { n.nb = DIRS.map(function (d) { var q = red(n.c + d[0], n.r + d[1]); return idx[q[0] * Rr + q[1]]; }); });
    return { nodes: nodes, W: W, H: H };
  }
  function wrap(v, P) { return v - P * Math.round(v / P); }

  var DEF = {
    R: 13, MU: 0.15, SIG: 0.015, T: 10,             // 오비움 (Chan 2019)
    KAP: 0.12, UP: 0.008, DOWN: 0.0008,             // 자리의 피로(발자국) — 약하게. 몸을 죽일 만큼 세면 몰기가 생명체를 죽인다(§10.6). 센 피로는 몸이 진다(AGE)
    HUNGER: 0, EAT: 0.02, REGEN: 0.0005,            // 양분 N: 먹으면 줄고 천천히 찬다. 모자라면 굶는다(−HUNGER·(1−N)). 끌기 먹이가 채운다
    AGE: 0.00019, KAGE: 0.5, YOUNG: 0.03,           // 몸의 피로(나이): 몸 안 이웃의 나이를 물려받고 조금씩 늘어난다. −KAGE·나이.
                                                    //   먹이·부르기·몰기가 닿은 칸은 YOUNG 만큼 젊어진다. 방치하면 약 1.5~3.5분 뒤 사그라진다(탐색 3시드, §10.6)
    FERT: 0,                                        // 비옥도 가산 — **끔 (v3.2)**. 1회차 전역 0.06 은 움직임을 못 바꿨고(§10.7 X3), 2회차 국소 0.1 은
                                                    //   돌봄을 벌했다(과성장 죽음, 같은 시드에서 0 이면 5/5 산다 — §10.11). 다시 열려면 국소 정규화·과성장 방지 먼저
    FERT_ZM: false,                                 // true: 몸 위 평균을 뺀다(기울기만 남긴다 — 전체 성장을 더하지 않아 세게 걸 수 있다). 탐색에서 기각 (§10.9)
    EDGE: false,                                    // true: 비옥도·끌기 가산에 (1 − A) 를 곱한다. 탐색에서 기각 (§10.9)
    SATG: 0,                                        // >0: 생명이 이 값 이상인 칸에는 끌기를 더하지 않는다. 탐색에서 기각 (§10.9)
    FLOCAL: true,                                   // 비옥도를 Tonnetz 6-이웃에서만 받는다(자기 칸 제외). false = 1회차 전역식 (§10.9)
    SWELL: 0,                                       // >0: 손의 질량이 지난 박 덩어리 질량보다 이만큼(비율) 넘으면 그 스텝은 끌지 않는다. 탐색에서 기각 (§10.9)
    STEER: 0.28, CURL: 0.035, SETTLE: 12,           // 몰기 먹이 · 문어의 제 휘어짐 · 태어난 뒤 몰기를 받지 않는 박
    PUSH: 0, PUSH_D: 0.8,                           // 뒤에서 밀기(0 이면 옆구리 몰기)
    LURE: 0.30, LURE_MIN: 0.15, LURE_RAMP: 60,      // 끌어당김(성장 가산) 몰기: 누르면 0.15 에서 60스텝(≈7초)에 걸쳐 0.30 으로 (0.35 는 과식 죽음 — §10.7 X4, §10.9)
    LURE_D: 1.0, LURE_R: 0.7, GUARD_LO: 48, GUARD_HI: 90,   // 질량이 이 밖이면 몰기를 쉰다
    CALL: 0.15,                                     // 음 부르기의 끌어당김
    TAU: 0.35, SOUND_M: 0.6,                        // 음이 "울린다" 로 치는 생명의 양 (그 Tonnetz 칸 안의 합)
    RATE: 0.0,                                      // intra ↔ inter (사용자가 Q/E 로 바꾼다)
    CAP: 6,
    coupled: false, shuffleWeights: false
  };

  function create(data, opts) {
    opts = opts || {};
    var P = {}; for (var k in DEF) P[k] = (k in opts) ? opts[k] : DEF[k];
    var G = opts.algo1 || root.GenerationAlgo1;
    var rng = G.makeRng(opts.seed == null ? 1 : opts.seed);
    var geo = buildGeo(), NT = geo.nodes.length, LAB = data.labels, NL = LAB.length;
    var KF = kernel(P.R);

    // 고운 칸 → Tonnetz 칸 (육각 보로노이, 토러스)
    var cell = new Int16Array(NX * NY);
    for (var y = 0; y < NY; y++) for (var x = 0; x < NX; x++) {
      var X = (x + 0.5) * DX, Y = (y + 0.5) * DY, best = 0, bd = 1e9;
      for (var i = 0; i < NT; i++) { var n = geo.nodes[i], dx = wrap(n.x - X, W), dy = wrap(n.y - Y, H), d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; } }
      cell[y * NX + x] = best;
    }
    // Tonnetz 칸 → 음 (음역 지형, 2판과 같다)
    var cycles = data.cycles, K = cycles.length, cnt = {};
    cycles.forEach(function (c) { c.forEach(function (u) { cnt[u] = (cnt[u] || 0) + 1; }); });
    var lo = 1e9, hi = -1e9; LAB.forEach(function (l) { lo = Math.min(lo, l.pitch); hi = Math.max(hi, l.pitch); });
    var note = new Int16Array(NT), terrain = new Float32Array(NT);
    for (i = 0; i < NT; i++) {
      var nd = geo.nodes[i], target = lo + (hi - lo) * (1 - Math.cos(2 * Math.PI * nd.y / H)) / 2, bn = -1, bdd = 1e9;
      terrain[i] = target;
      for (var j = 0; j < NL; j++) { if (LAB[j].pc !== nd.pc || !cnt[j]) continue;
        var dd = Math.abs(LAB[j].pitch - target) + (LAB[j].dur === 2 ? 0 : 0.2); if (dd < bdd) { bdd = dd; bn = j; } }
      note[i] = bn;
    }
    // 가중치 (사용자의 설계). V 대조군이면 음 쌍을 섞는다
    var NW = data.note_weights, WI = [NW.intra_right, NW.intra_left], WX = NW.inter;
    if (P.shuffleWeights) {
      var rs = G.makeRng(777 + (opts.seed || 0)), perm = []; for (i = 0; i < NL; i++) perm.push(i);
      for (i = NL - 1; i > 0; i--) { var q = Math.floor(rs() * (i + 1)); var t0 = perm[i]; perm[i] = perm[q]; perm[q] = t0; }
      var sh = function (M) { return M.map(function (row, a) { return row.map(function (_, b) { return M[perm[a]][perm[b]]; }); }); };
      WI = WI.map(sh); WX = sh(WX);
    }
    var RAR = []; for (i = 0; i < NL; i++) RAR.push(cnt[i] ? 1 / cnt[i] : 0);
    var WSUM = cycles.map(function (c) { return c.reduce(function (a, v) { return a + RAR[v]; }, 0); });
    var alive = data.vines.map(function (v) { var a = new Uint8Array(151);
      v.rates.forEach(function (iv) { for (var r = Math.round(iv[0] * 100); r <= Math.round(iv[1] * 100); r++) a[r] = 1; }); return a; });
    var pool = new G.NodePool({ labels: LAB.map(function (l) { return { label: l.li + 1, label_idx: l.li, pitch: l.pitch, dur: l.dur, count: l.count }; }), rng: rng });
    var mgr = new G.CycleSetManager({ cycles: cycles.map(function (c, i3) { return { cycle_idx: i3, note_labels_0idx: c }; }), K: K });
    var HANDS = [data.hands.lark, data.hands.octopus];

    var S = { t: 0, beat: 0, A: [new Float32Array(NX * NY), new Float32Array(NX * NY)], F: [new Float32Array(NX * NY), new Float32Array(NX * NY)],
              N: new Float32Array(NX * NY).fill(1), G: [new Float32Array(NX * NY), new Float32Array(NX * NY)],
              food: new Float32Array(NX * NY), fert: [new Float32Array(NT), new Float32Array(NT)], mass: [new Float32Array(NL), new Float32Array(NL)],
              blobs: [[], []], steer: [null, null], hold: [0, 0], lureAmp: [0, 0], calls: [],
              rate: P.RATE, found: new Uint8Array(K * 151), born: [0, 0], fbar: [0, 0], P: P };
    var RE = new Float64Array(NX * NY), IM = new Float64Array(NX * NY);

    // ── 생명체 놓기: 오비움을 angle 방향으로 돌려 놓는다 ─────────────────────
    function spawn(c, wx, wy, angle) {
      if (S.blobs[c].length >= P.CAP) return false;
      var A = S.A[c], ca = Math.cos(angle || 0), sa = Math.sin(angle || 0), n = 20, ox = wx / DX, oy = wy / DY;
      for (var j2 = -16; j2 <= 16; j2++) for (var i2 = -16; i2 <= 16; i2++) {
        // 세계 좌표 (i2, j2) 를 패턴 좌표로 되돌린다 (가로 칸 크기 기준, 세로는 DX/DY 로 보정)
        var u = i2, v = j2 * DY / DX, pu = ca * u + sa * v + n / 2, pv = -sa * u + ca * v + n / 2;
        var iu = Math.floor(pu), iv = Math.floor(pv); if (iu < 0 || iv < 0 || iu >= n || iv >= n) continue;
        var val = ORBIUM[iv][iu]; if (!val) continue;
        var gx = ((Math.round(ox + i2) % NX) + NX) % NX, gy = ((Math.round(oy + j2) % NY) + NY) % NY, gi = gy * NX + gx;
        A[gi] = Math.max(A[gi], val); S.F[c][gi] = 0; S.G[c][gi] = 0;
      }
      S.born[c]++;
      if (!S.blobs[c].length) S.blobs[c] = [{ id: -1, x: ox, y: oy, m: 1, cells: 1, hx: 0, hy: 0, age: 0 }];   // 다음 박까지 FFT 를 건너뛰지 않게
      return true;
    }
    function feed(wx, wy, amt, rad) {               // 먹이 (두 손 모두) — 문지르기
      var ox = wx / DX, oy = wy / DY, r = rad || 5, a = amt == null ? 0.25 : amt;
      for (var j2 = -r * 2; j2 <= r * 2; j2++) for (var i2 = -r * 2; i2 <= r * 2; i2++) {
        var d2 = (i2 * i2 + j2 * j2 * (DY * DY) / (DX * DX)) / (r * r); if (d2 > 4) continue;
        var gx = ((Math.round(ox + i2) % NX) + NX) % NX, gy = ((Math.round(oy + j2) % NY) + NY) % NY;
        S.food[gy * NX + gx] = Math.min(0.6, S.food[gy * NX + gx] + a * Math.exp(-d2));
        S.N[gy * NX + gx] = Math.min(1, S.N[gy * NX + gx] + 2 * a * Math.exp(-d2));   // 먹이는 양분도 채운다
      }
    }
    function setSteer(c, dir) { if (!dir) S.hold[c] = 0; S.steer[c] = dir; }     // dir = [dx, dy] 단위 벡터(세계 좌표) 또는 null
    /** 음 부르기: 그 음이름의 칸 중 생명체 가까운 곳이 잠시 끌어당긴다 (steps CA 스텝 동안). */
    function call(pc, steps) { S.calls.push({ pc: pc, until: S.t + (steps || 40) }); }

    // ── 덩어리 찾기 (생명체 하나 = 이어진 덩어리) — 몰기·소리·그림이 쓴다 ─────────
    var LABEL = new Int32Array(NX * NY);
    function findBlobs(c) {
      var A = S.A[c], old = S.blobs[c], out = [], stack = [];
      LABEL.fill(0);
      var id = 0;
      for (var s0 = 0; s0 < NX * NY; s0++) {
        if (A[s0] < 0.1 || LABEL[s0]) continue;
        id++; var sx = 0, sy = 0, sw = 0, cells = 0, ref = null; stack.push(s0); LABEL[s0] = id;
        while (stack.length) {
          var q2 = stack.pop(), qx = q2 % NX, qy = (q2 / NX) | 0, a2 = A[q2];
          if (!ref) ref = [qx, qy];
          var ux = ref[0] + wrap(qx - ref[0], NX), uy = ref[1] + wrap(qy - ref[1], NY);
          sx += a2 * ux; sy += a2 * uy; sw += a2; cells++;
          var nb4 = [qy * NX + (qx + 1) % NX, qy * NX + (qx + NX - 1) % NX, ((qy + 1) % NY) * NX + qx, ((qy + NY - 1) % NY) * NX + qx];
          for (var e = 0; e < 4; e++) { var m2 = nb4[e]; if (!LABEL[m2] && A[m2] >= 0.1) { LABEL[m2] = id; stack.push(m2); } }
        }
        if (sw < 3) continue;                          // 먼지는 생명체가 아니다
        var cx = ((sx / sw) % NX + NX) % NX, cy = ((sy / sw) % NY + NY) % NY;
        // 앞선 덩어리와 이어 붙여 머리 방향을 잰다
        var prev = null, pd = 1e9;
        for (var o = 0; o < old.length; o++) { var ddx = wrap(old[o].x - cx, NX), ddy = wrap(old[o].y - cy, NY), d3 = ddx * ddx + ddy * ddy; if (d3 < pd) { pd = d3; prev = old[o]; } }
        var hx = 0, hy = 0, id2 = prev && pd < 400 ? prev.id : (S.nextBlob = (S.nextBlob || 0) + 1);
        if (prev && pd < 400) {
          var mx = wrap(cx - prev.x, NX) * DX, my = wrap(cy - prev.y, NY) * DY, L = Math.sqrt(mx * mx + my * my);
          if (L > 1e-4) { hx = 0.7 * prev.hx + 0.3 * mx / L; hy = 0.7 * prev.hy + 0.3 * my / L; var LL = Math.sqrt(hx * hx + hy * hy) || 1; hx /= LL; hy /= LL; }
          else { hx = prev.hx; hy = prev.hy; }
        }
        out.push({ id: id2, x: cx, y: cy, m: sw, cells: cells, hx: hx, hy: hy, age: prev && pd < 400 ? prev.age + 1 : 0 });
      }
      S.blobs[c] = out;
    }

    // ── 한 CA 스텝 ─────────────────────────────────────────────────────────
    function caStep() {
      var fertFine = [null, null];
      for (var cc = 0; cc < 2; cc++) {
        if (lureOn[cc]) { LURE[cc].fill(0); lureOn[cc] = false; }
        if (S.steer[cc]) S.hold[cc]++;
        S.lureAmp[cc] = P.LURE_MIN + (P.LURE - P.LURE_MIN) * Math.min(1, S.hold[cc] / P.LURE_RAMP);
      }
      // 음 부르기 — 덩어리마다 가장 가까운 그 음이름 칸(격자 3 안)에 약한 끌어당김
      S.calls = S.calls.filter(function (q) { return q.until > S.t; });
      for (var qc = 0; qc < S.calls.length; qc++) for (var c9 = 0; c9 < 2; c9++) S.blobs[c9].forEach(function (B) {
        var bx = B.x * DX, by = B.y * DY, best = -1, bd = 9;
        for (var n9 = 0; n9 < NT; n9++) { var nd9 = geo.nodes[n9]; if (nd9.pc !== S.calls[qc].pc) continue;
          var ddx = wrap(nd9.x - bx, W), ddy = wrap(nd9.y - by, H), d9 = ddx * ddx + ddy * ddy; if (d9 < bd && d9 > 0.2) { bd = d9; best = n9; } }
        if (best >= 0) { var nb9 = geo.nodes[best], L9 = Math.sqrt(bd), ux = wrap(nb9.x - bx, W) / L9, uy = wrap(nb9.y - by, H) / L9;
          lureDisk(c9, bx + Math.min(1.0, L9) * ux, by + Math.min(1.0, L9) * uy, P.CALL); }
      });
      for (var c = 0; c < 2; c++) {
        // 몰기 먹이 · 문어의 제 휘어짐 — 덩어리마다 머리 옆에
        var bl = S.blobs[c], sd = S.steer[c];
        if (sd && P.SWELL) {                              // 팽창 가드: 지난 박보다 SWELL 넘게 부풀었으면 이 스텝은 끌지 않는다 (과식 죽음, §10.7)
          var bm0 = 0, ms = 0, Ac4 = S.A[c]; for (var q4 = 0; q4 < bl.length; q4++) bm0 += bl[q4].m;
          for (var i12 = 0; i12 < Ac4.length; i12++) ms += Ac4[i12];
          if (bm0 > 0 && ms > bm0 * (1 + P.SWELL)) continue; }       // (문어의 제 휘어짐도 이 스텝은 쉰다)
        for (var b = 0; b < bl.length; b++) {
          var B = bl[b]; if (!B.hx && !B.hy) continue;
          if (B.age < P.SETTLE) continue;                 // 막 태어나 모양을 잡는 동안 한쪽을 밀면 무너진다 (§10.6)
          if (sd && P.LURE) {                               // 끌어당김: **성장 가산** 원반 (질량을 더하면 오히려 밀어낸다)
            if (B.m < P.GUARD_LO || B.m > P.GUARD_HI) continue;   // 약해지면(질량이 줄면) 잠시 멈춘다 — 세게 돌리면 무너진다(§10.6)
            var cr0 = B.hx * sd[1] - B.hy * sd[0], dt0 = B.hx * sd[0] + B.hy * sd[1];
            if (dt0 >= 0.9) lureDisk(c, B.x * DX + P.LURE_D * B.hx, B.y * DY + P.LURE_D * B.hy);          // 맞았으면 앞으로
            else { var sg = cr0 >= 0 ? 1 : -1;                                                             // 머리 옆, 목표 쪽
              lureDisk(c, B.x * DX + 0.45 * B.hx - 0.75 * B.hy * sg, B.y * DY + 0.45 * B.hy + 0.75 * B.hx * sg); }
            continue;
          }
          if (sd && P.PUSH) {                               // 뒤에서 밀기(시험용 — 효과 없음, §10.6)
            pulse(S.A[c], B.x * DX - P.PUSH_D * sd[0], B.y * DY - P.PUSH_D * sd[1], P.PUSH); continue;
          }
          var side = 0, amt = 0;
          if (sd) { var cr = B.hx * sd[1] - B.hy * sd[0], dot = B.hx * sd[0] + B.hy * sd[1];
            // 먹이를 둔 쪽의 **반대**로 돈다(steer 검증: 머리 기준 (−hy, hx) 쪽 먹이 → 각도가 준다). 그래서 부호를 뒤집는다
            // 어긋난 만큼만 민다 (정반대면 STEER, 거의 맞으면 0) — 세게 계속 밀면 무너진다
            if (dot < 0.97) { side = cr >= 0 ? -1 : 1; amt = P.STEER * Math.min(1, 0.35 + 0.65 * (1 - dot) / 2 * 2); } }
          else if (c === 1) { side = 1; amt = P.CURL; }
          if (!amt) continue;
          var px = -B.hy * side, py = B.hx * side, fx = B.x * DX + 0.5 * B.hx + 0.65 * px, fy = B.y * DY + 0.5 * B.hy + 0.65 * py;
          pulse(S.A[c], fx, fy, amt);
        }
      }
      for (c = 0; c < 2; c++) {
        var A = S.A[c], F = S.F[c], fe = S.fert[c];
        if (!S.blobs[c].length && S.t % 16 !== 0) {    // 이 손에 생명체가 없으면 FFT 를 건너뛴다(피로만 푼다) — 16스텝마다 한 번은 확인
          for (var z = 0; z < A.length; z++) { if (A[z]) A[z] *= 0.9; F[z] -= P.DOWN * F[z]; }
          continue;
        }
        for (var i4 = 0; i4 < RE.length; i4++) { RE[i4] = A[i4]; IM[i4] = 0; }
        fft2(RE, IM, false);
        for (i4 = 0; i4 < RE.length; i4++) { var ar = RE[i4], ai = IM[i4]; RE[i4] = ar * KF.re[i4] - ai * KF.im[i4]; IM[i4] = ar * KF.im[i4] + ai * KF.re[i4]; }
        fft2(RE, IM, true);
        var inv2 = 1 / (2 * P.SIG * P.SIG);
        for (i4 = 0; i4 < A.length; i4++) {
          var u2 = RE[i4] - P.MU, g = 2 * Math.exp(-u2 * u2 * inv2) - 1;
          var fb = P.FERT_ZM ? (A[i4] > 0.01 ? P.FERT * (fe[cell[i4]] - S.fbar[c]) : 0)
                             : (A[i4] > 0.01 || S.food[i4] > 0 ? P.FERT * fe[cell[i4]] : 0);
          var lb = lureOn[c] && A[i4] > 0.01 ? LURE[c][i4] : 0;
          if (P.EDGE) { var eg = 1 - A[i4]; fb *= eg; lb *= eg; }   // 가산은 가장자리에서만 — 속까지 더하면 포화(A=1)돼 퍼텐셜이 성장 창을 넘고 한꺼번에 무너진다(§10.7)
          if (P.SATG && A[i4] >= P.SATG) lb = 0;                     // 포화 가드: 거의 찬 칸에는 끌기를 더하지 않는다
          var a3 = A[i4] + (g + fb + lb + S.food[i4] - P.KAP * F[i4] - P.HUNGER * (1 - S.N[i4]) - P.KAGE * S.G[c][i4]) / P.T;
          A[i4] = a3 < 0 ? 0 : (a3 > 1 ? 1 : a3);
          F[i4] += P.UP * A[i4] * (1 - F[i4]) - P.DOWN * F[i4];
        }
      }
      if (P.AGE) for (var ca = 0; ca < 2; ca++) {
        var Ac = S.A[ca], Gc = S.G[ca], Gn = AGEBUF, Lc = LURE[ca], lo2 = lureOn[ca];
        for (var yy = 0; yy < NY; yy++) for (var xx = 0; xx < NX; xx++) {
          var id0 = yy * NX + xx, a0 = Ac[id0];
          if (a0 < 0.02) { Gn[id0] = Gc[id0] * 0.9; continue; }         // 몸이 떠난 자리는 나이를 잊는다
          // 몸의 **속**(생명 ≥ 0.3)끼리만 나이를 물려준다 — 가장자리(나이 낮음)가 섞이면 나이가 새어 나간다(평형 ≈ 0.005 에서 멈췄다)
          var sw2 = 0, sg2 = 0;
          for (var dy2 = -1; dy2 <= 1; dy2++) { var yr = ((yy + dy2) % NY + NY) % NY;
            for (var dx2 = -1; dx2 <= 1; dx2++) { var ii = yr * NX + ((xx + dx2) % NX + NX) % NX, w3 = Ac[ii]; if (w3 < 0.3) continue; sw2 += w3; sg2 += w3 * Gc[ii]; } }
          var gv = (sw2 > 0 ? sg2 / sw2 : Gc[id0]) + P.AGE;
          if (S.food[id0] > 0.02 || (lo2 && Lc[id0] > 0)) gv *= 1 - P.YOUNG;   // 먹이·부르기·몰기가 닿으면 젊어진다
          Gn[id0] = gv;
        }
        Gc.set(Gn);
      }
      for (var i5 = 0; i5 < S.food.length; i5++) {
        S.food[i5] *= 0.97;                                           // 먹이는 사라진다
        if (P.HUNGER) { var nn = S.N[i5] + P.REGEN * (1 - S.N[i5]) - P.EAT * (S.A[0][i5] + S.A[1][i5]); S.N[i5] = nn < 0 ? 0 : nn; }
      }
      S.t++;
    }
    var LURE = [new Float32Array(NX * NY), new Float32Array(NX * NY)], lureOn = [false, false], AGEBUF = new Float32Array(NX * NY);
    function lureDisk(c, wx, wy, amp) {
      var ox = wx / DX, oy = wy / DY, rr = P.LURE_R / DX, L2 = LURE[c], A0 = amp == null ? S.lureAmp[c] : amp; lureOn[c] = true;
      for (var j2 = -Math.ceil(rr * DX / DY); j2 <= Math.ceil(rr * DX / DY); j2++) for (var i2 = -Math.ceil(rr); i2 <= Math.ceil(rr); i2++) {
        var d2 = (i2 * i2 + (j2 * DY / DX) * (j2 * DY / DX)) / (rr * rr); if (d2 > 1) continue;
        var gx = ((Math.round(ox) + i2) % NX + NX) % NX, gy = ((Math.round(oy) + j2) % NY + NY) % NY;
        L2[gy * NX + gx] = Math.max(L2[gy * NX + gx], A0 * (1 - d2));
      }
    }
    function pulse(A, wx, wy, amt) {                  // 몰기 먹이: 작은 가우스 한 점 (steer 검증과 같은 모양)
      var ox = wx / DX, oy = wy / DY;
      for (var j2 = -6; j2 <= 6; j2++) for (var i2 = -6; i2 <= 6; i2++) { var r2 = (i2 * i2 + j2 * j2) / 16; if (r2 > 2.5) continue;
        var gx = ((Math.round(ox) + i2) % NX + NX) % NX, gy = ((Math.round(oy) + j2) % NY + NY) % NY, gi = gy * NX + gx;
        A[gi] = Math.min(1, A[gi] + amt * Math.exp(-r2) / P.T); }
    }

    // ── 음악 한 박: 덮은 음 → 비옥도 갱신 → 고리 → Algorithm 1 ──────────────────
    var ROW = new Int8Array(K), MCELL = [new Float32Array(NT), new Float32Array(NT)];
    function beat() {
      var ri = Math.round(S.rate * 100), out = { t: S.beat, voices: [], found: [] };
      for (var c = 0; c < 2; c++) {
        findBlobs(c);
        var m = S.mass[c]; m.fill(0);
        var A = S.A[c];
        for (var i6 = 0; i6 < A.length; i6++) if (A[i6] > 0.02) { var nt = note[cell[i6]]; if (nt >= 0) m[nt] += A[i6]; }
      }
      // 비옥도 = intra_c(v→u)·m_c(v) + rate · inter(v→u)·m_c'(v)   (Tonnetz 칸 단위, 최댓값 1)
      if (P.FLOCAL) {                                  // 국소판: 칸 i 의 비옥도 = Σ_{j ∈ 6-이웃(i)} M_c(j)·intra_c(음 j → 음 i) + rate·M_c'(j)·inter(음 j → 음 i)
        for (c = 0; c < 2; c++) { var Mc = MCELL[c], Ac3 = S.A[c]; Mc.fill(0);          //   자기 칸은 뺀다 — intra 는 같은 음 반복이 가장 커서(대각 0.20 vs 0.09) 넣으면 제자리를 가장 비옥하게 한다
          for (var i10 = 0; i10 < Ac3.length; i10++) if (Ac3[i10] > 0.02) Mc[cell[i10]] += Ac3[i10]; }
        for (c = 0; c < 2; c++) { var fe3 = S.fert[c], Ms = MCELL[c], Mo = MCELL[1 - c], mx3 = 0;
          for (var i11 = 0; i11 < NT; i11++) { var ui = note[i11], s3 = 0; fe3[i11] = 0; if (ui < 0) continue;
            var nbs = geo.nodes[i11].nb;
            for (var e3 = 0; e3 < 6; e3++) { var j3 = nbs[e3], vj = note[j3]; if (vj < 0) continue;
              s3 += Ms[j3] * WI[c][vj][ui] + S.rate * Mo[j3] * WX[vj][ui]; }
            fe3[i11] = s3; if (s3 > mx3) mx3 = s3; }
          if (mx3 > 0) for (i11 = 0; i11 < NT; i11++) fe3[i11] /= mx3; }
      } else
      for (c = 0; c < 2; c++) {
        var fu = new Float32Array(NL), mc = S.mass[c], mo = S.mass[1 - c], mx = 0;
        for (var u = 0; u < NL; u++) { var s = 0;
          for (var v = 0; v < NL; v++) s += mc[v] * WI[c][v][u] + S.rate * mo[v] * WX[v][u];
          fu[u] = s; if (s > mx) mx = s; }
        var fe = S.fert[c];
        for (var i7 = 0; i7 < NT; i7++) fe[i7] = note[i7] >= 0 && mx > 0 ? fu[note[i7]] / mx : 0;
        if (P.FERT_ZM) { var sa = 0, sf = 0, Ac2 = S.A[c];          // 몸 위(생명 가중) 비옥도 평균
          for (var i9 = 0; i9 < Ac2.length; i9++) if (Ac2[i9] > 0.01) { sa += Ac2[i9]; sf += Ac2[i9] * fe[cell[i9]]; }
          S.fbar[c] = sa > 0 ? sf / sa : 0; }
      }
      // 소리 — 손마다 제 리듬
      for (c = 0; c < 2; c++) {
        var h = HANDS[c], ph = S.beat % h.period, cnt2 = h.ring[ph] || 0;
        var mc2 = S.mass[c], snd = {}, any = 0;
        for (var v2 = 0; v2 < NL; v2++) if (mc2[v2] >= P.SOUND_M) { snd[v2] = 1; any = 1; }
        var f = 0;
        for (var k2 = 0; k2 < K; k2++) { var on = 0;
          if (any && alive[k2][ri]) { var acc = 0, cs = cycles[k2]; for (var q3 = 0; q3 < cs.length; q3++) if (snd[cs[q3]]) acc += RAR[cs[q3]];
            on = WSUM[k2] > 0 && acc / WSUM[k2] >= P.TAU ? 1 : 0; }
          ROW[k2] = on; f += on;
          if (on && !S.found[k2 * 151 + ri]) { S.found[k2 * 151 + ri] = 1; out.found.push([k2, ri]); } }
        if (!cnt2 || !f) continue;
        var vv = new Int8Array(8 * K); for (k2 = 0; k2 < K; k2++) vv[k2] = ROW[k2]; for (var w2 = 1; w2 < 8; w2++) vv.copyWithin(w2 * K, 0, K);
        var il = new Int32Array(8); il[0] = cnt2;
        var res = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen: il, overlap: { T: 8, K: K, values: vv }, rng: rng });
        out.voices.push({ hand: c, rows: f, notes: res.notes.map(function (x) { return [x[1], x[2] - x[0], where(c, x[1])]; }) });
      }
      S.beat++;
      return out;
    }
    function where(c, pitch) {                       // 그 음이 울릴 Tonnetz 칸: 그 손의 생명이 가장 많이 덮은, 같은 음(없으면 같은 음이름) 칸
      var best = -1, bm = -1, A = S.A[c], acc = new Float32Array(NT);
      for (var i8 = 0; i8 < A.length; i8 += 3) if (A[i8] > 0.05) acc[cell[i8]] += A[i8];
      for (var n2 = 0; n2 < NT; n2++) { if (!acc[n2]) continue;
        var ok = note[n2] >= 0 && LAB[note[n2]].pitch === pitch ? 2 : (geo.nodes[n2].pc === pitch % 12 ? 1 : 0);
        var sc = ok * 1000 + acc[n2]; if (ok && sc > bm) { bm = sc; best = n2; } }
      return best;
    }

    return { state: S, geo: geo, cell: cell, note: note, terrain: terrain, labels: LAB, K: K, vines: data.vines, alive: alive,
             NX: NX, NY: NY, DX: DX, DY: DY, W: W, H: H,
             spawn: spawn, feed: feed, setSteer: setSteer, call: call, caStep: caStep, beat: beat,
             setRate: function (r) { S.rate = Math.max(0, Math.min(1.5, Math.round(r * 100) / 100)); },
             mass: function (c) { var s = 0, A = S.A[c]; for (var i = 0; i < A.length; i++) s += A[i]; return s; } };
  }

  var API = { create: create, buildGeo: buildGeo, NX: NX, NY: NY, W: W, H: H, DEF: DEF };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.TonnetzLife = root.TonnetzLife3 = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
