// sketch/lifeloop-core.js 판정기 — 답이 알려진 경우부터. node tools/verify_lifeloop.mjs
import { createRequire } from 'module'; const require = createRequire(import.meta.url);
const L = require('../sketch/lifeloop-core.js');
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) process.exitCode = 1; };
const N = 64;
// ① 구멍 판정기: 0 바탕 위 고리 하나 → 구멍 1개(깊이 1) · 꽉 찬 원판 → 0개
{ const A = new Float32Array(N * N); for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { const d = Math.hypot(x - 32, y - 32); if (d >= 6 && d <= 9) A[y * N + x] = 1; }
  const h = L.holes(A, N, 0.12, 3); ok(h.length === 1 && Math.abs(h[0].d - 1) < 1e-6, `고리 → 구멍 ${h.length}개 깊이 ${h[0] && h[0].d}`); }
{ const A = new Float32Array(N * N); for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (Math.hypot(x - 32, y - 32) <= 9) A[y * N + x] = 1;
  ok(L.holes(A, N, 0.12, 3).length === 0, '꽉 찬 원판 → 구멍 0개'); }
// ② 생명체: 네 방향 모두 300스텝 산다 · 나란한 두 마리 600스텝 산다
for (let r = 0; r < 4; r++) { const W = L.World(); W.stamp(20, 20, r); for (let s = 0; s < 300; s++) W.step(); ok(W.mass > 28 && W.mass < 40, `방향 ${r}: 300스텝 질량 ${W.mass.toFixed(1)}`); }
{ const W = L.World(); W.stamp(16, 18, 0); W.stamp(44, 44, 0); let holesSeen = 0; for (let s = 0; s < 600; s++) { W.step(); if (s % 30 === 0) holesSeen += L.holes(W.A, N, 0.12, 3).length; }
  ok(W.mass > 60 && W.mass < 76, `나란한 두 마리: 600스텝 질량 ${W.mass.toFixed(1)} · 30스텝마다 센 구멍 합 ${holesSeen}`); }
// ③ 어느 고리가 켜지나 · 무엇을 연주하나
const towns = [[0, 0], [10, 0], [10, 10], [0, 10], [5, 5], [20, 5], [15, 0], [15, 10]].map(([x, y], k) => ({ x, y, p: 60 + k }));
const loops = [[0, 1, 2, 3], [4, 6, 5, 7, 2]];       // hibari 고리 둘(겹침): 큰 사각형 · 오른쪽에 걸친 다각형(점 2 공유)
{ const r = L.which(2, 2, towns, loops); ok(r.on === 'h0' && r.loop.join() === '0,1,2,3', `고리 0 안 → [${r.on}] 고리 순서 그대로 [${r.loop}]`); }
{ const A0 = L.area(loops[0].map(k => [towns[k].x, towns[k].y])), A1 = L.area(loops[1].map(k => [towns[k].x, towns[k].y])), small = A0 < A1 ? 0 : 1;
  const r = L.which(9, 6, towns, loops); ok(r.on === 'h' + small, `두 고리 안 → 안쪽(작은) 고리 [${r.on}] (넓이 ${A0}·${A1})`); }
{ const r = L.which(9, 6, towns, loops, [[0, 1, 2, 3]]); ok(r.on === 'm0' && r.loop.join() === '0,1,2,3', `내가 그은 고리가 먼저 [${r.on}]`); }
{ const r = L.which(8, 3, towns, loops, [[0, 1, 2, 3], [4, 2, 1]]); ok(r.on === 'm1' && r.loop.join() === '4,2,1', `둘 다 감싸면 나중에 그은 고리 [${r.on}] 그은 순서 [${r.loop}]`); }
{ const r = L.which(30, 30, towns, loops); ok(r.on === null && r.loop.length === 1, `고리 밖 → 가장 가까운 음 하나 [${r.loop}]`); }
{ const lp = [3, 1, 4, 1, 5].filter((k, i, a) => a.indexOf(k) === i);   // [3,1,4,5]
  const seq = [0, 1, 2, 3, 4, 5, 6, 7].map(t => L.play(lp, t).join('.'));
  ok(seq[0] === '3.1.4.5' && seq[1] === '3' && seq[3] === '1' && seq[5] === '4' && seq[7] === '5' && seq[2] === '1.4.5.3', `연주: 짝수 박 화음·홀수 박 한 음씩 고리를 돈다 ${seq.join(' | ')}`);
  ok(L.play([7, 8, 9, 10, 11, 12], 0).length === 4 && L.play([2], 4).join() === '2', '화음은 넷까지 · 음 하나면 그 음'); }
ok(L.vel(0.05) < L.vel(0.2) && L.vel(0.2) < L.vel(0.35) && L.vel(1) === L.vel(0.35), `세기 = 깊이: ${[0.05, 0.2, 0.35, 1].map(d => L.vel(d).toFixed(2))}`);
