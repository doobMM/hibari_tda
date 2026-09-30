// verify_shape_core.mjs — shape/shape-core.js (점 → 몸) 가 맞게 도는지. 로직이 깨지면 FAIL 하는 가장 작은 확인.
//   node tools/verify_shape_core.mjs
import { createRequire } from 'node:module';
const SC = createRequire(import.meta.url)('../shape/shape-core.js');
let bad = 0;
const ok = (name, cond, note) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}  ${note}`); if (!cond) bad++; };
const white = n => new Float32Array(n * 3).fill(1);
const ring = (R, n, cx = 0) => { const P = []; for (let i = 0; i < n; i++) P.push(cx + R * Math.cos(2 * Math.PI * i / n), R * Math.sin(2 * Math.PI * i / n), 0); return P; };
const S = 0.45, r0 = S * Math.sqrt(2 * Math.log(2));

{ // 1. 점 하나 = 공
  const m = SC.build(new Float32Array([0, 0, 0]), white(1), { sigma: S, iso: 0.5, voxel: 0.06 }), t = SC.topology(m), g = SC.measure(m);
  let lo = 9, hi = 0; for (let i = 0; i < m.positions.length; i += 3) { const r = Math.hypot(m.positions[i], m.positions[i + 1], m.positions[i + 2]); lo = Math.min(lo, r); hi = Math.max(hi, r); }
  ok('점 하나 → 공 하나', t.components === 1 && t.chi === 2 && t.boundaryEdges === 0 && t.nonManifoldEdges === 0, `조각 ${t.components} chi ${t.chi} 열린 변 ${t.boundaryEdges}`);
  ok('공의 반지름', lo > r0 * 0.94 && hi < r0 * 1.06, `${lo.toFixed(3)}~${hi.toFixed(3)} (이론 ${r0.toFixed(3)})`);
  ok('넓이·부피(바깥을 보게 감김)', Math.abs(g.area / (4 * Math.PI * r0 * r0) - 1) < 0.05 && Math.abs(g.volume / (4 / 3 * Math.PI * r0 ** 3) - 1) < 0.08, `넓이 비 ${(g.area / (4 * Math.PI * r0 * r0)).toFixed(3)} 부피 비 ${(g.volume / (4 / 3 * Math.PI * r0 ** 3)).toFixed(3)}`);
}
{ // 2. 고리 = 구멍 하나
  const P = new Float32Array(ring(5, 64)), t = SC.topology(SC.build(P, white(64), { sigma: S }));
  ok('고리 → 구멍 1', t.components === 1 && t.chi === 0 && t.genus === 1 && t.boundaryEdges === 0 && t.nonManifoldEdges === 0, `chi ${t.chi} 구멍 ${t.genus}`);
}
{ // 3. 떨어진 두 점 = 두 조각, 색이 섞이지 않는다
  const m = SC.build(new Float32Array([0, 0, 0, 10, 0, 0]), new Float32Array([1, 0, 0, 0, 0, 1]), { sigma: S }), t = SC.topology(m); let mix = 0;
  for (let i = 0; i < m.positions.length; i += 3) { const red = m.positions[i] < 5; if (red ? !(m.colors[i] > 0.95 && m.colors[i + 2] < 0.05) : !(m.colors[i + 2] > 0.95 && m.colors[i] < 0.05)) mix++; }
  ok('두 점 → 두 조각', t.components === 2 && t.chi === 4, `조각 ${t.components} chi ${t.chi}`); ok('색이 제 조각에만', mix === 0, `섞인 꼭짓점 ${mix}`);
}
{ // 4. 맞닿은 두 고리 = 구멍 둘
  const P = new Float32Array(ring(5, 64, -5).concat(ring(5, 64, 5))), t = SC.topology(SC.build(P, white(128), { sigma: S }));
  ok('8자 → 구멍 2', t.components === 1 && t.genus === 2, `조각 ${t.components} chi ${t.chi} 구멍 ${t.genus} 셋 이상 만나는 변 ${t.nonManifoldEdges}`);
}
{ // 5. 결정적 · 빠르기 (선형 합동 난수로 만든 걸음)
  let s = 12345; const rnd = () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;
  const walk = (n, R) => { const P = new Float32Array(n * 3); let x = 0, y = 0, z = 0;
    for (let i = 0; i < n; i++) { const a = rnd() * 6.283, c = rnd() * 2 - 1, q = Math.sqrt(1 - c * c); x += 0.5 * q * Math.cos(a); y += 0.5 * q * Math.sin(a); z += 0.5 * c;
      const r = Math.hypot(x, y, z); if (r > R) { x *= R / r; y *= R / r; z *= R / r; } P[i * 3] = x; P[i * 3 + 1] = y; P[i * 3 + 2] = z; } return P; };
  const A = walk(1089, 4), a1 = SC.build(A, white(1089), { sigma: S }), a2 = SC.build(A, white(1089), { sigma: S });
  ok('같은 입력 = 같은 그물', a1.positions.length === a2.positions.length && a1.positions.every((v, i) => v === a2.positions[i]) && a1.indices.every((v, i) => v === a2.indices[i]), `V ${a1.stats.V} F ${a1.stats.F}`);
  ok('1,089점 빠르기', a1.stats.ms <= 300, `${a1.stats.ms} ms (목표 150, 실패 기준 300)`);
  const B = walk(8196, 20), b = SC.build(B, white(8196), { sigma: S, maxGrid: 144 }), tb = SC.topology(b);
  ok('8,196점 빠르기', b.stats.ms <= 1800, `${b.stats.ms} ms (목표 900, 실패 기준 1800) V ${b.stats.V} F ${b.stats.F} 셋 이상 만나는 변 ${tb.nonManifoldEdges} 열린 변 ${tb.boundaryEdges}`);
  let out = 0; const p = b.positions, I = b.indices, nn = b.normals;
  for (let i = 0; i < I.length; i += 3) { const [u, v, w] = [I[i] * 3, I[i + 1] * 3, I[i + 2] * 3];
    const ax = p[v] - p[u], ay = p[v + 1] - p[u + 1], az = p[v + 2] - p[u + 2], bx = p[w] - p[u], by = p[w + 1] - p[u + 1], bz = p[w + 2] - p[u + 2];
    const gx = ay * bz - az * by, gy = az * bx - ax * bz, gz = ax * by - ay * bx;
    if (gx * (nn[u] + nn[v] + nn[w]) + gy * (nn[u + 1] + nn[v + 1] + nn[w + 1]) + gz * (nn[u + 2] + nn[v + 2] + nn[w + 2]) > 0) out++; }
  ok('삼각형이 바깥을 본다', out / (I.length / 3) >= 0.995, `${(100 * out / (I.length / 3)).toFixed(2)}%`);
}
{ // 6. 고르기 · 두루마리
  const P = new Float32Array([0, 0, 0, 0, 0, -3, 2, 0, 0]), I4 = new Float32Array([0.1, 0, 0, 0, 0, 0.1, 0, 0, 0, 0, -0.1, 0, 0, 0, 0, 1]);   // 직교: z 가 클수록(−0.1·z 작을수록) 가깝다
  ok('고르기: 앞에 있는 노드', SC.pick(P, 3, I4, 50, 50, 100, 100, 4) === 0 && SC.pick(P, 3, I4, 60, 50, 100, 100, 4) === 2 && SC.pick(P, 3, I4, 10, 10, 100, 100, 4) === -1, '겹치면 가까운 쪽, 없으면 −1');
  const Sc = SC.scroll(500, 1); let worst = 0, near = 9;
  for (let i = 5; i < 499; i++) worst = Math.max(worst, Math.abs(Math.hypot(Sc[i * 3 + 3] - Sc[i * 3], Sc[i * 3 + 4] - Sc[i * 3 + 1]) - 1));
  for (let i = 0; i < 500; i++) for (let j = i + 2; j < 500; j++) near = Math.min(near, Math.hypot(Sc[j * 3] - Sc[i * 3], Sc[j * 3 + 1] - Sc[i * 3 + 1]));
  ok('두루마리: 간격 1, 겹치지 않는다', worst < 0.03 && near > 1.5, `간격 오차 ${worst.toFixed(4)} 가장 가까운 남남 ${near.toFixed(2)}`);
}
console.log(bad ? `\n${bad}개 실패` : '\n전부 통과'); process.exit(bad ? 1 : 0);
