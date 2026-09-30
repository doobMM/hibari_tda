/* sketch/flow-core.js — 흐름 그물 (시안 A) 엔진. DOM 없음. 명세: docs/sketch_spec.md §5 A
 *
 * 상태   웅덩이마다 물 w[손][음] (금빛 = 오른손, 산호빛 = 왼손) · 젖은 자국 wet[손][음] (물이 지나간 흔적 — 천천히 마른다)
 *        물길의 넓이 wide[손][음→음] (쓰면 넓어지고 안 쓰면 좁아진다) · rate(수문, 0~1.5) · ph[손](모듈 안의 자리, 32 와 33) · 고리마다 켜짐 lit · 지침 tired.
 * 흐름   스텝마다 손마다: 모듈의 리듬이 이 스텝에 몇 음인지 정한다(화음 4 · 단음 1 · 쉼 0 — 물이 적으면 화음이 가늘어진다).
 *        울 웅덩이 u 를 **제비뽑기**로 고른다:  무게 = Σ_v (v 의 물) × 물길(v→u) × (1 + 넓이) × 모듈의 그 자리 음높이에 가까운 정도
 *          물길(v→u) = 같은 손: 모듈에서 v 다음에 u 가 오는 횟수(방향이 있다) + SEEP × intra[손][v][u] (정본 가중치 — 곁에 있는 음으로 스민다)
 *                     두 손 사이: rate × GATE × inter[v][u] (수문)
 *        뽑힌 웅덩이로 물길이 닿는 **모든** 물이 흘러든다(넷으로 갈라졌다 하나로 모인다). **닿은 웅덩이가 운다**(세기 = 닿은 양). 두 손 사이 물길로 온 몫은 물빛이 바뀐다.
 *        닿을 물길이 없는 물은 그 자리에서 기다린다. → 다음 음은 "방금 울린 음 다음에 오는 음" 이다.
 *        ⚠ 정본 intra 는 대칭이고 "곁에 있는 음" 을 말할 뿐 순서를 담지 않는다(실측: 다음 묶음으로 가는 무게가 3~10%) — 그래서 방향은 모듈에서 가져온다.
 * 붓기   그 음이 곧바로 울고, **그 손의 모듈이 그 음이 나오는 자리로 옮겨 간다**(앞으로 가장 가까운 곳). 부은 음에서 곡이 이어진다 — 두 손의 어긋남을 내가 정한다.
 *        마른 손으로 물이 건너오면 그 손도 건너온 음의 자리에서 시작한다(돌림노래가 저절로 생긴다).
 * 고리   그 rate 에 살아 있는 고리의 음이 (희귀도 가중) TAU 이상 젖어 있으면 켜진다. 켜진 고리 위의 물은 KEEP 배로만 마른다(스스로 돈다).
 *        켜져 있는 동안 지치고(LIFE 스텝이면 꺼진다) 쉬어야 다시 켜진다 — 영원하지 않다.
 * 살리기 물은 스텝마다 EVAP 몫이 마른다. 남은 물 전체가 DEAD 아래면 멎는다. 물을 넣는 것은 내 손뿐이다 → 방치하면 멎는다.
 *        붓기·수문·넘침은 물을 더하거나 옮길 뿐 줄이지 않는다 — 많이 눌러서 멎는 길은 없다. 웅덩이가 넘치면(CAP) 다음 음들로 흩어지고, 전체가 FULL 을 넘으면 넘친 만큼만 빠진다.
 * 키     가운데 줄 A~J · 윗줄 Q~U = 금빛 물을 도~시에(가운데 · 높은 옥타브대)   아랫줄 Z~M = 산호빛 물을 도~시에(낮은 옥타브대)
 *        ←/→ = 수문(두 물이 서로 넘어가는 정도)   그 밖의 키 = 어딘가에 붓는다(덜 찬 물빛으로)
 *        화면: PadG0~6 금빛 건반 · PadC0~6 산호빛 건반 · Note<음 번호> 그 웅덩이에 금빛
 */
(function (root) {
  'use strict';
  var HS = root.HS || require('./common.js');
  var DEF = {
    POUR: 1.0,      // 한 번 붓는 양
    CAP: 2.0,       // 웅덩이 하나가 담는 양
    FULL: 4.0,      // 물 전체의 한도
    EVAP: 0.055,    // 스텝마다 마르는 몫
    DEAD: 0.1,      // 남은 물 전체가 이보다 적으면 멎는다
    SEEP: 0.05,     // 정본 intra(곁에 있는 음)로 스미는 정도 — 모듈의 방향 물길 1 에 대해
    FITS: 1.0,      // 모듈 음높이에 끌리는 너비(반음). 작을수록 모듈을 그대로 따른다
    GATE: 0.2,      // rate 1 일 때 두 손 사이 물길의 무게
    RICH: 0.5,      // 한 손의 물이 이만큼이면 화음이 다 찬다(4음)
    GROW: 0.5, FADE: 0.04, WMAX: 3,   // 물길: 쓰면 넓어지고(+GROW) 스텝마다 FADE 몫이 줄어든다
    TRACE: 0.12,    // 젖은 자국이 스텝마다 마르는 몫
    TAU: 1.0,       // 고리가 켜지는 젖은 몫
    WET: 0.3,       // 고리가 '젖었다' 고 치는 자국
    KEEP: 0.6,      // 켜진 고리 위의 물은 이 배로만 마른다
    LIFE: 24,       // 켜진 고리가 버티는 스텝
    REST: 64,       // 다 지친 고리가 다 쉬는 스텝
    SPLASH: 0.15,   // 수문을 움직이면 튀는 물 (만지는 것이 물을 줄이지 않게)
    RATE0: 0.5, RSTEP: 0.25, RMAX: 1.5,
    FIT: true, NET: true, MIX: 0   // 대조군용: 모듈 음높이 끌림 끄기 · 물길을 전부 같게 · 방향 물길의 도착 음을 섞기(시드)
  };
  var BANDS = [55, 65, 77];       // 아랫줄 · 가운데 줄 · 윗줄이 붓는 옥타브대의 가운데 음높이

  function create(H, opts) {
    opts = opts || {};
    var P = {}, q; for (q in DEF) P[q] = (q in opts) ? opts[q] : DEF[q];
    var rng = HS.rng(opts.seed == null ? 1 : opts.seed), N = H.notes, NL = H.NL, K = H.K, cyc = H.cycles;
    function zeros(n) { var a = []; for (var j = 0; j < n; j++) a.push(0); return a; }
    var cnt = zeros(NL); cyc.forEach(function (c) { c.forEach(function (u) { cnt[u]++; }); });
    var rar = cnt.map(function (c) { return c ? 1 / c : 0; }), wsum = cyc.map(function (c) { return c.reduce(function (a, u) { return a + rar[u]; }, 0); });
    var IN = [H.intra[0], H.intra[1]], X = H.inter;
    var SUCC = [0, 1].map(function (h) {                   // 모듈에서 v 다음(다음 onset 묶음)에 u 가 오는 횟수 — 방향이 있는 물길. 최댓값 1
      var M = [], st = H.mod[h].steps, on = [], mx = 0, a, b; for (a = 0; a < NL; a++) M.push(zeros(NL));
      st.forEach(function (g, p) { if (g.length) on.push(p); });
      on.forEach(function (p, i) { st[p].forEach(function (v) { st[on[(i + 1) % on.length]].forEach(function (u) { M[v][u]++; if (M[v][u] > mx) mx = M[v][u]; }); }); });
      if (P.MIX) { var r2 = HS.rng(P.MIX), perm = []; for (a = 0; a < NL; a++) perm.push(a);             // 대조군: 도착 음의 번호를 섞는다(구조는 같고 어느 음인지만 다르다)
        for (a = NL - 1; a > 0; a--) { b = Math.floor(r2() * (a + 1)); var t = perm[a]; perm[a] = perm[b]; perm[b] = t; }
        M = M.map(function (row) { var o = zeros(NL); row.forEach(function (x, u) { o[perm[u]] = x; }); return o; }); }
      return M.map(function (row) { return row.map(function (x) { return x / mx; }); });
    });
    var entry = BANDS.map(function (c) { var row = []; for (var d = 0; d < 7; d++) { var best = -1;      // 옥타브대 × 음이름 → 가장 가까운 음(짧은 것)
      N.forEach(function (n) { if (n.deg !== d) return; if (best < 0 || Math.abs(n.pitch - c) < Math.abs(N[best].pitch - c) || (n.pitch === N[best].pitch && n.dur < N[best].dur)) best = n.li; });
      row.push(best); } return row; });
    var S = { t: 0, ph: [0, 0], rate: P.RATE0, w: [zeros(NL), zeros(NL)], wet: [zeros(NL), zeros(NL)], wide: [new Float32Array(NL * NL), new Float32Array(NL * NL)],
              lit: zeros(K), tired: zeros(K), alive: false, nLit: 0, P: P };
    function total(h) { var s = 0; for (var u = 0; u < NL; u++) s += S.w[h][u]; return s; }
    function chan(h, v, u) { return P.NET ? SUCC[h][v][u] + P.SEEP * IN[h][v][u] : (v === u ? 0 : 0.3); }   // 같은 손 물길: 방향(모듈) + 스밈(정본 intra)
    function cross(v, u) { return S.rate * P.GATE * (P.NET ? X[v][u] : (v === u ? 0 : 0.3)); }              // 두 손 사이 물길(수문)
    function seat(h, li) {                                 // 그 음높이가 그 손의 모듈에서 다음에 나오는 자리 (지금 자리에서 앞으로 가장 가까운 곳)
      var st = H.mod[h].steps, per = H.mod[h].period, p0 = ((S.ph[h] % per) + per) % per, d, p;
      for (d = 0; d < per; d++) { p = (p0 + d) % per; if (st[p].some(function (u) { return N[u].pitch === N[li].pitch; })) return p; }
      return p0;
    }
    function land(h, u, amt, first) {                      // 물이 손 h 의 웅덩이 u 에 닿는다. first: 마른 손으로 건너온 첫 물 — 그 손도 그 음의 자리에서 시작한다
      if (first) S.ph[h] = seat(h, u) + 1;
      S.w[h][u] += amt; S.wet[h][u] = Math.max(S.wet[h][u], Math.min(1, 0.3 + amt * 2));
    }

    // ── 붓기: 돌려주는 음은 곧바로 울린다 ─────────────────────────────────────────
    function spill(h, v, notes) {                          // 넘친 물은 물길을 따라 이웃 둘로 흩어진다
      var ex = S.w[h][v] - P.CAP; if (ex <= 0) return; S.w[h][v] = P.CAP;
      for (var j = 0; j < 2; j++) { var tot = 0, u, r; for (u = 0; u < NL; u++) tot += chan(h, v, u);
        if (tot <= 0) { S.w[h][v] += ex / 2; continue; } r = rng() * tot; for (u = 0; u < NL - 1; u++) { r -= chan(h, v, u); if (r <= 0) break; }
        S.w[h][u] += ex / 2; S.wet[h][u] = 1; if (notes) notes.push({ pitch: N[u].pitch, dur: 1, vel: 0.12, li: u, hand: h, from: v }); }
    }
    function pour(h, li) {
      var was = S.alive;
      S.ph[h] = seat(h, li) + 1;                             // **부은 음이 곡을 그 자리로 데려간다**: 다음 스텝은 모듈에서 그 음 다음에 오는 것
      if (!was) { S.alive = true; S.ph[1 - h] = seat(1 - h, li) + 1; }   // 멎었다가 다시 부으면 두 손이 같은 자리에서 나란히 시작한다(원곡처럼). 그 뒤로 32 와 33 이 어긋난다
      S.w[h][li] += P.POUR; S.wet[h][li] = 1; var notes = [{ pitch: N[li].pitch, dur: 2, vel: 0.34, li: li, hand: h }];
      spill(h, li, notes);
      return { kind: 'pour', hand: h, li: li, notes: notes };
    }
    function gate(d) {                                     // 수문: 열면 가장 찬 웅덩이의 물이 곧바로 건너가며 운다
      var r0 = S.rate, notes = [], h, v, u; S.rate = Math.max(0, Math.min(P.RMAX, Math.round((S.rate + d * P.RSTEP) * 100) / 100));
      for (h = 0; h < 2 && d > 0 && S.rate > r0; h++) { var bv = -1; for (v = 0; v < NL; v++) if (S.w[h][v] > 0.02 && (bv < 0 || S.w[h][v] > S.w[h][bv])) bv = v;
        if (bv < 0) continue; var bu = -1; for (u = 0; u < NL; u++) if (X[bv][u] > 0 && (bu < 0 || X[bv][u] > X[bv][bu])) bu = u;
        if (bu < 0) continue; var amt = 0.35 * S.w[h][bv]; S.w[h][bv] -= amt; land(1 - h, bu, amt, total(1 - h) < 0.05);
        notes.push({ pitch: N[bu].pitch, dur: 1, vel: 0.22, li: bu, hand: 1 - h, from: bv, cross: true }); }
      if (!notes.length) { var top = 0; for (u = 1; u < NL; u++) if (S.w[0][u] + S.w[1][u] > S.w[0][top] + S.w[1][top]) top = u;     // 닫을 때·끝에서도 소리는 난다(가장 찬 웅덩이, 여리게)
        notes.push({ pitch: N[top].pitch, dur: 1, vel: S.rate === r0 ? 0.08 : 0.13, li: top, hand: S.w[1][top] > S.w[0][top] ? 1 : 0 }); }
      if (S.alive) { S.w[notes[0].hand][notes[0].li] += P.SPLASH; S.wet[notes[0].hand][notes[0].li] = 1; }   // 수문을 움직이면 물이 조금 튄다
      return { kind: 'gate', rate: S.rate, moved: S.rate !== r0, notes: notes };
    }
    function press(code) {
      var d, m;
      if ((d = HS.ROWS[1].indexOf(code)) >= 0) return pour(0, entry[1][d]);
      if ((d = HS.ROWS[2].indexOf(code)) >= 0) return pour(0, entry[2][d]);
      if ((d = HS.ROWS[0].indexOf(code)) >= 0) return pour(1, entry[0][d]);
      if ((m = /^Pad([GC])([0-6])$/.exec(code))) return m[1] === 'G' ? pour(0, entry[1][+m[2]]) : pour(1, entry[0][+m[2]]);
      if ((m = /^Note(\d+)$/.exec(code)) && +m[1] < NL) return pour(0, +m[1]);
      if (code === 'ArrowLeft' || code === 'ArrowRight') return gate(code === 'ArrowLeft' ? -1 : 1);
      var h = total(0) <= total(1) ? 0 : 1, r = rng() * 7 | 0;                                         // 그 밖의 키: 덜 찬 물빛으로 어딘가에
      return pour(h, entry[h ? 0 : 1 + (rng() < 0.35 ? 1 : 0)][r]);
    }

    // ── 한 스텝 ───────────────────────────────────────────────────────────
    function flow(h, out, later) {
      var m = H.mod[h], tg = m.steps[S.ph[h] % m.period], tot = total(h); if (!tg.length || tot < 0.01) return;
      var want = tg.map(function (u) { return N[u]; }).sort(function (a, b) { return a.pitch - b.pitch; });
      var n = want.length < 3 ? want.length : Math.max(2, Math.min(want.length, Math.round(1 + 3 * Math.min(1, tot / P.RICH))));   // 물이 줄면 화음이 가늘어진다 (4 → 3 → 2)
      var ord = [0, want.length - 1, 1, 2].filter(function (v, j, a) { return v < want.length && a.indexOf(v) === j; }).slice(0, n);      // 베이스 · 맨 위 · 그 사이
      var used = {}, picks = [], src = S.w[h], chord = want.length >= 3, v, u;
      function link(v2, u2) { var a = chan(h, v2, u2), b = cross(v2, u2); return a + b <= 0 ? 0 : (a + b) * (1 + S.wide[h][v2 * NL + u2]); }
      ord.forEach(function (wi, j) {                                                          // 울 웅덩이를 하나씩 뽑는다
        var tgt = want[wi], T = zeros(NL), totW = 0, r;
        for (u = 0; u < NL; u++) { if (used[u]) continue; var g = 0; for (v = 0; v < NL; v++) if (src[v] > 0 && v !== u) g += src[v] * link(v, u);
          T[u] = g * (P.FIT ? Math.exp(-Math.abs(N[u].pitch - tgt.pitch) / P.FITS) : 1); totW += T[u]; }
        if (totW <= 0) return; r = rng() * totW;
        for (u = 0; u < NL - 1; u++) { r -= T[u]; if (r <= 0 && T[u] > 0) break; }
        if (!(T[u] > 0)) return; used[u] = 1; picks.push({ u: u, tgt: tgt, j: j });
      });
      if (!picks.length) return;
      var arrive = [zeros(NL), zeros(NL)], from = picks.map(function () { return []; });
      for (v = 0; v < NL; v++) { if (src[v] <= 0) continue;                                    // 뽑힌 웅덩이로 닿는 물길이 있는 모든 물이 흘러든다
        var gs = picks.map(function (pk) { return pk.u === v ? 0 : link(v, pk.u); }), gt = gs.reduce(function (x, y) { return x + y; }, 0); if (gt <= 0) continue;
        var amt = src[v]; src[v] = 0;
        picks.forEach(function (pk, i) { if (gs[i] <= 0) return; var part = amt * gs[i] / gt, b = cross(v, pk.u), xs = b / (chan(h, v, pk.u) + b);
          arrive[h][pk.u] += part * (1 - xs); arrive[1 - h][pk.u] += part * xs; from[i].push({ v: v, amt: part });
          S.wide[h][v * NL + pk.u] = Math.min(P.WMAX, S.wide[h][v * NL + pk.u] + P.GROW * Math.min(1, part / 0.2)); });
      }
      picks.forEach(function (pk, i) {
        var got = arrive[0][pk.u] + arrive[1][pk.u], e = 0.5 + 0.5 * Math.min(1, got / 0.4);
        from[i].sort(function (x, y) { return y.amt - x.amt; });
        out.notes.push({ pitch: N[pk.u].pitch, dur: pk.tgt.dur, vel: (chord ? (pk.j === 0 ? 0.2 : 0.14) : 0.32) * e * (h ? 0.78 : 1) * (S.ph[h] % 16 === 0 ? 1.25 : 1),
                         li: pk.u, hand: h, from: from[i].length ? from[i][0].v : -1, flows: from[i].slice(0, 4), crossed: arrive[1 - h][pk.u] > arrive[h][pk.u], amt: got });
      });
      for (u = 0; u < NL; u++) { if (arrive[h][u] > 0) later.push([h, u, arrive[h][u], false]); if (arrive[1 - h][u] > 0) later.push([1 - h, u, arrive[1 - h][u], true]); }
    }
    function step() {
      var out = { t: S.t++, ph: S.ph.slice(), notes: [], lit: [], dark: [] }, h, u, k, f, later = [];
      if (!S.alive) return out;
      var dry = [total(0) < 0.05, total(1) < 0.05];
      for (h = 0; h < 2; h++) if (S.ph[h] >= 0) flow(h, out, later);
      S.ph[0]++; S.ph[1]++;
      later.sort(function (a, b) { return b[2] - a[2]; }).forEach(function (a) {             // 닿은 물은 두 손이 다 흐른 뒤에 내려앉는다(한 스텝에 두 번 흐르지 않게)
        var first = a[3] && dry[a[0]]; if (first) dry[a[0]] = false; land(a[0], a[1], a[2], first); });
      var keep = zeros(NL); S.nLit = 0;                                                     // 고리: 젖어 있으면 켜지고, 켜져 있으면 덜 마른다
      for (k = 0; k < K; k++) {
        var a = 0; cyc[k].forEach(function (x) { if (Math.max(S.wet[0][x], S.wet[1][x]) >= P.WET) a += rar[x]; }); var cov = H.alive(k, S.rate) ? a / wsum[k] : 0;
        if (S.lit[k]) { S.tired[k] += 1 / P.LIFE; if (cov < P.TAU * 0.8 || S.tired[k] >= 1) { S.lit[k] = 0; out.dark.push(k); } }
        else { S.tired[k] = Math.max(0, S.tired[k] - 1 / P.REST); if (cov >= P.TAU && S.tired[k] < 0.5) { S.lit[k] = 1; out.lit.push(k); } }
        if (S.lit[k]) { S.nLit++; cyc[k].forEach(function (x) { keep[x] = 1; }); }
      }
      var left = 0;
      for (h = 0; h < 2; h++) { for (u = 0; u < NL; u++) { spill(h, u, null); S.w[h][u] *= 1 - P.EVAP * (keep[u] ? P.KEEP : 1); left += S.w[h][u]; S.wet[h][u] *= 1 - P.TRACE * (keep[u] ? P.KEEP : 1); }
        for (u = 0; u < NL * NL; u++) if (S.wide[h][u]) S.wide[h][u] = S.wide[h][u] < 0.02 ? 0 : S.wide[h][u] * (1 - P.FADE); }
      if (left > P.FULL) { f = P.FULL / left; for (h = 0; h < 2; h++) for (u = 0; u < NL; u++) S.w[h][u] *= f; left = P.FULL; }   // 전체가 넘치면 넘친 만큼만 빠진다
      if (left < P.DEAD) { left = 0; for (h = 0; h < 2; h++) for (u = 0; u < NL; u++) S.w[h][u] = 0; }
      S.alive = left > 0; out.alive = S.alive; out.water = left;
      if (!S.alive) for (k = 0; k < K; k++) S.lit[k] = 0;
      return out;
    }
    function probe() { var lit = []; for (var k = 0; k < K; k++) if (S.lit[k]) lit.push(k);
      var wet = 0; for (var u = 0; u < NL; u++) if (Math.max(S.wet[0][u], S.wet[1][u]) >= P.WET) wet++;
      return { alive: S.alive, water: [total(0), total(1)], wet: wet, lit: lit, rate: S.rate, t: S.t, ph: S.ph.slice() }; }
    return { press: press, release: function () { return null; }, step: step, probe: probe, state: S, entry: entry, rar: rar, succ: SUCC };
  }

  var API = { create: create, DEF: DEF, BANDS: BANDS };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HSFlow = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
