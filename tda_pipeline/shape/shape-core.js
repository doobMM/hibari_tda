/* shape/shape-core.js — 점(가닥) → 몸(삼각형 그물).  페이지(shape/index.html)와 node 검증(tools/verify_shape_core.mjs)이 같이 쓴다.
 *
 * 장    F(x) = Σ_i W_i · exp(−|x − P_i|² / 2σ²)      가닥이 여러 번 지나간 자리는 장이 세다 → 굵다
 * 색    K(x) = Σ_i W_i · exp(…) · C_i / F(x)
 * 몸    F = iso 인 면. naive Surface Nets — 부호가 바뀌는 칸마다 꼭짓점 하나(모서리 교차점들의 평균),
 *       부호가 바뀌는 격자 모서리마다 네모 하나(삼각형 둘). 표는 쓰지 않는다.
 * 결정적이다(난수 없음). DOM 없이 돈다.
 */
(function (root) {
  'use strict';
  var EDGES = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];   // 꼭짓점 번호 = x + 2y + 4z
  var clock = typeof performance !== 'undefined' ? function () { return performance.now(); } : function () { return Date.now(); };

  function build(P, C, opts) {
    opts = opts || {}; var t0 = clock(), N = P.length / 3, sigma = opts.sigma || 0.45, iso = opts.iso || 0.5, W = opts.W || null, i, k;
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (i = 0; i < N; i++) for (k = 0; k < 3; k++) { var v = P[i * 3 + k]; if (v < lo[k]) lo[k] = v; if (v > hi[k]) hi[k] = v; }
    var pad = (opts.pad || 3) * sigma, side = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) + 2 * pad;
    var h = opts.voxel || Math.max(sigma / 1.6, side / (opts.maxGrid || 144));
    var o = [lo[0] - pad - h, lo[1] - pad - h, lo[2] - pad - h];
    var nx = Math.ceil((hi[0] - o[0] + pad) / h) + 2, ny = Math.ceil((hi[1] - o[1] + pad) / h) + 2, nz = Math.ceil((hi[2] - o[2] + pad) / h) + 2, nxy = nx * ny;
    var F = new Float32Array(nxy * nz), R = new Float32Array(nxy * nz), G = new Float32Array(nxy * nz), B = new Float32Array(nxy * nz);
    // ① 뿌리기: 노드마다 3σ 안의 칸에만 (축마다 1차원 가우스를 미리 구해 곱한다)
    var rad = Math.ceil(3 * sigma / h), n1 = 2 * rad + 1, wx = new Float32Array(n1), wy = new Float32Array(n1), wz = new Float32Array(n1), s2 = 1 / (2 * sigma * sigma);
    for (i = 0; i < N; i++) {
      var px = (P[i * 3] - o[0]) / h, py = (P[i * 3 + 1] - o[1]) / h, pz = (P[i * 3 + 2] - o[2]) / h, cx = Math.round(px), cy = Math.round(py), cz = Math.round(pz);
      for (k = 0; k < n1; k++) { var d = (cx - rad + k - px) * h; wx[k] = Math.exp(-d * d * s2); d = (cy - rad + k - py) * h; wy[k] = Math.exp(-d * d * s2); d = (cz - rad + k - pz) * h; wz[k] = Math.exp(-d * d * s2); }
      var w0 = W ? W[i] : 1, cr = C[i * 3], cg = C[i * 3 + 1], cb = C[i * 3 + 2];
      for (var c = 0; c < n1; c++) { var z = cz - rad + c; if (z < 0 || z >= nz) continue; var wc = w0 * wz[c];
        for (var b = 0; b < n1; b++) { var y = cy - rad + b; if (y < 0 || y >= ny) continue; var wb = wc * wy[b], base = z * nxy + y * nx + cx - rad;
          for (var a = 0; a < n1; a++) { var x = cx - rad + a; if (x < 0 || x >= nx) continue; var w = wb * wx[a], q = base + a; F[q] += w; R[q] += w * cr; G[q] += w * cg; B[q] += w * cb; } } }
    }
    // ② 면 뽑기
    var cells = new Int32Array(nxy * nz).fill(-1), pos = [], nor = [], col = [], idx = [], f8 = new Float32Array(8), off = [0, 1, nx, nx + 1, nxy, nxy + 1, nxy + nx, nxy + nx + 1], step = [1, nx, nxy];
    for (var zc = 0; zc < nz - 1; zc++) for (var yc = 0; yc < ny - 1; yc++) for (var xc = 0; xc < nx - 1; xc++) {
      var m = zc * nxy + yc * nx + xc, mask = 0;
      for (k = 0; k < 8; k++) { f8[k] = F[m + off[k]]; if (f8[k] >= iso) mask |= 1 << k; }
      if (mask === 0 || mask === 255) continue;
      var sx = 0, sy = 0, sz = 0, cnt = 0;
      for (k = 0; k < 12; k++) { var e0 = EDGES[k][0], e1 = EDGES[k][1]; if (((mask >> e0) & 1) === ((mask >> e1) & 1)) continue;
        var t = (iso - f8[e0]) / (f8[e1] - f8[e0]);
        sx += (e0 & 1) + t * ((e1 & 1) - (e0 & 1)); sy += ((e0 >> 1) & 1) + t * (((e1 >> 1) & 1) - ((e0 >> 1) & 1)); sz += ((e0 >> 2) & 1) + t * (((e1 >> 2) & 1) - ((e0 >> 2) & 1)); cnt++; }
      cells[m] = pos.length / 3;
      pos.push(o[0] + (xc + sx / cnt) * h, o[1] + (yc + sy / cnt) * h, o[2] + (zc + sz / cnt) * h);
      var gx = f8[1] + f8[3] + f8[5] + f8[7] - f8[0] - f8[2] - f8[4] - f8[6], gy = f8[2] + f8[3] + f8[6] + f8[7] - f8[0] - f8[1] - f8[4] - f8[5], gz = f8[4] + f8[5] + f8[6] + f8[7] - f8[0] - f8[1] - f8[2] - f8[3];
      var gl = Math.hypot(gx, gy, gz) || 1; nor.push(-gx / gl, -gy / gl, -gz / gl);
      var fs = 0, rs = 0, gs = 0, bs = 0; for (k = 0; k < 8; k++) { var qq = m + off[k]; fs += F[qq]; rs += R[qq]; gs += G[qq]; bs += B[qq]; }
      col.push(rs / fs, gs / fs, bs / fs);
      // 이 칸의 0번 꼭짓점에서 나가는 세 모서리: 부호가 바뀌면 그 모서리를 둘러싼 네 칸을 네모로 잇는다 (바깥을 보게 감는다)
      var in0 = mask & 1;
      for (var ax = 0; ax < 3; ax++) { if (in0 === ((mask >> (1 << ax)) & 1)) continue;
        var u = (ax + 1) % 3, vv = (ax + 2) % 3, cu = u === 0 ? xc : u === 1 ? yc : zc, cvv = vv === 0 ? xc : vv === 1 ? yc : zc; if (cu === 0 || cvv === 0) continue;
        var A = cells[m], Bv = cells[m - step[u]], Cv = cells[m - step[u] - step[vv]], Dv = cells[m - step[vv]];
        if (in0) idx.push(A, Bv, Cv, A, Cv, Dv); else idx.push(A, Dv, Cv, A, Cv, Bv); }
    }
    // ③ 그늘: 면에서 법선 쪽으로 1.6σ 나간 곳의 장이 세면(다른 살이 가까우면) 어둡다
    var V = pos.length / 3, ao = new Float32Array(V);
    for (i = 0; i < V; i++) { var ix = Math.round((pos[i * 3] + nor[i * 3] * 1.6 * sigma - o[0]) / h), iy = Math.round((pos[i * 3 + 1] + nor[i * 3 + 1] * 1.6 * sigma - o[1]) / h), iz = Math.round((pos[i * 3 + 2] + nor[i * 3 + 2] * 1.6 * sigma - o[2]) / h);
      var fv = ix < 0 || iy < 0 || iz < 0 || ix >= nx || iy >= ny || iz >= nz ? 0 : F[iz * nxy + iy * nx + ix]; ao[i] = 1 - Math.min(1, fv / iso) * 0.75; }
    return { positions: new Float32Array(pos), normals: new Float32Array(nor), colors: new Float32Array(col), ao: ao, indices: new Uint32Array(idx),
             grid: { nx: nx, ny: ny, nz: nz, h: h, origin: o }, stats: { V: V, F: idx.length / 3, ms: Math.round(clock() - t0) } };
  }

  /** 그물의 위상: chi = V − E + F, 조각 수, 열린 변·셋 이상이 만나는 변, 구멍 수(genus = 조각 − chi/2, 닫힌 면일 때만 뜻이 있다) */
  function topology(mesh) {
    var I = mesh.indices, V = mesh.positions.length / 3, Fc = I.length / 3, E = new Map(), par = new Int32Array(V), i;
    for (i = 0; i < V; i++) par[i] = i;
    function find(a) { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; }
    for (i = 0; i < I.length; i += 3) for (var k = 0; k < 3; k++) { var a = I[i + k], b = I[i + (k + 1) % 3], key = a < b ? a * V + b : b * V + a;
      E.set(key, (E.get(key) || 0) + 1); var ra = find(a), rb = find(b); if (ra !== rb) par[ra] = rb; }
    var bd = 0, nm = 0; E.forEach(function (n) { if (n === 1) bd++; else if (n > 2) nm++; });
    var comp = 0; for (i = 0; i < V; i++) if (find(i) === i) comp++;
    var chi = V - E.size + Fc; return { V: V, E: E.size, F: Fc, chi: chi, components: comp, boundaryEdges: bd, nonManifoldEdges: nm, genus: comp - chi / 2 };
  }
  function measure(mesh) { var I = mesh.indices, p = mesh.positions, area = 0, vol = 0;
    for (var i = 0; i < I.length; i += 3) { var a = I[i] * 3, b = I[i + 1] * 3, c = I[i + 2] * 3;
      var ux = p[b] - p[a], uy = p[b + 1] - p[a + 1], uz = p[b + 2] - p[a + 2], vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
      var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; area += Math.hypot(nx, ny, nz) / 2; vol += (p[a] * nx + p[a + 1] * ny + p[a + 2] * nz) / 6; }
    return { area: area, volume: vol }; }

  /** 화면의 (px, py) 에서 radiusPx 안에 비치는 노드 중 카메라에 가장 가까운 것. mvp 는 열 우선 4×4. 없으면 −1. */
  function pick(P, N, mvp, px, py, width, height, radiusPx) { var best = -1, bz = Infinity, r2 = radiusPx * radiusPx;
    for (var i = 0; i < N; i++) { var x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2], w = mvp[3] * x + mvp[7] * y + mvp[11] * z + mvp[15]; if (w <= 0) continue;
      var sx = ((mvp[0] * x + mvp[4] * y + mvp[8] * z + mvp[12]) / w * 0.5 + 0.5) * width, sy = (1 - ((mvp[1] * x + mvp[5] * y + mvp[9] * z + mvp[13]) / w * 0.5 + 0.5)) * height;
      var dx = sx - px, dy = sy - py; if (dx * dx + dy * dy > r2) continue;
      var zz = (mvp[2] * x + mvp[6] * y + mvp[10] * z + mvp[14]) / w; if (zz < bz) { bz = zz; best = i; } }
    return best; }
  function lerp(A, B, t, out) { out = out || new Float32Array(A.length); for (var i = 0; i < A.length; i++) out[i] = A[i] + (B[i] - A[i]) * t; return out; }
  /** 편 상태: z = 0 평면의 두루마리(아르키메데스 나선). 이웃 점 사이 호 길이 = spacing, 바퀴 사이 틈 2. */
  function scroll(N, spacing) { var out = new Float32Array(N * 3), g = 2 / (2 * Math.PI), th = 2 / g;
    for (var i = 0; i < N; i++) { var r = g * th; out[i * 3] = r * Math.cos(th); out[i * 3 + 1] = r * Math.sin(th); th += spacing / Math.sqrt(r * r + g * g); }
    var mx = 0, my = 0; for (i = 0; i < N; i++) { mx += out[i * 3]; my += out[i * 3 + 1]; } for (i = 0; i < N; i++) { out[i * 3] -= mx / N; out[i * 3 + 1] -= my / N; } return out; }

  var ShapeCore = { build: build, topology: topology, measure: measure, pick: pick, lerp: lerp, scroll: scroll };
  if (typeof module !== 'undefined' && module.exports) module.exports = ShapeCore;
  root.ShapeCore = ShapeCore;
})(typeof globalThis !== 'undefined' ? globalThis : this);
