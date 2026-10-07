// tools/verify_rings.mjs — 고리판(sketch/rings-core.js · sketch/rings.html) 판정기.   node tools/verify_rings.mjs
// 예측 (돌리기 전에 적음, 2026-10-07):
//  R1 판: 칸 54 가 모두 단위 공 위 · 원 9 × 칸 12 · 칸마다 원 둘 · 원마다 칸 12 의 축 좌표가 같다(공 위의 진짜 원)
//  R2 돌리기: 원마다 사분 회전이 정확히 12칸을 옮기고 ⁴ = 항등, k 뒤 −k = 항등. 가운데(베이스) 6칸은 가운데 층 원(L=0)에서만 움직인다
//  R3 소리: 다 맞춘 판 = hibari 오른손 32/32 · 왼손 33/33 (정답은 xcheck_cube_ref 가 자료에서 따로 뽑은 것)
//  R4 그림: 사영한 54점이 서로 다르고 (가장 가까운 두 점) / (가장 먼 반지름) ≥ 0.1 · 칸마다 제 원의 그 각 위에 있다(오차 < 1e-12)
//  R5 끌기: 칸마다 제 원 둘 각각의 접선 쪽으로 끌면 그 원 · 부호 +1, 반대로 끌면 −1 (108 경우 모두)
//  R6 놓기: 80°→1 · −100°→−1 · 130°→1 · 140°→2 · 10°→0 사분
//  R7 사건: 맞춘 판에서 원 하나를 돌리면 그 원이 지나는 네 송이만 깨지고, 되돌리면 그 네 송이가 '돌아옴' + '다 맞춤'
//  R8 되돌리기: 무작위 300수 뒤 되돌리기 300번 = 맞춤
//  R9 들림: 원 9개 모두 사분 회전 한 번이 오른손 스텝 하나 이상의 음을 바꾼다
//  R10 페이지: 인라인 스크립트 문법 · HS.audio.wake 는 unlock 안에서만 · unlock 은 제스처 처리기(pointerdown·click·keys)에서만 · 키는 ev.code
import { createRequire } from 'module';
import { readFileSync } from 'fs';
import { dataRight, dataLeft } from './verify/xcheck_cube_ref.mjs';
const require = createRequire(import.meta.url);
const HS = require('../sketch/common.js');
globalThis.HS = HS; globalThis.HSCube = require('../sketch/cube-core.js');
const RG = require('../sketch/rings-core.js');
const H = HS.derive(require('../lenia/tonnetz.json'));
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) { fails++; process.exitCode = 1; } };

// R1
const onSphere = RG.CELLS.every(c => Math.abs(Math.hypot(...c.q) - 1) < 1e-12);
const inc = new Array(54).fill(0); RG.RINGS.forEach(R => R.cells.forEach(i => inc[i]++));
const planar = RG.RINGS.every(R => R.cells.every(i => Math.abs(RG.CELLS[i].q[R.axis] - R.h) < 1e-12));
ok(RG.CELLS.length === 54 && onSphere && RG.RINGS.length === 9 && RG.RINGS.every(R => R.cells.length === 12) && inc.every(x => x === 2) && planar,
  `R1 칸 54 공 위 · 원 9 × 12 · 칸마다 원 2 · 원은 평면 단면(진짜 원)`);
// R2
let r2 = true, centerOnlyMiddle = true;
RG.RINGS.forEach((R, k) => { const P = RG.PERM[k], moved = P.filter((d, i) => d !== i).length; let s = RG.ident(); for (let m = 0; m < 4; m++) s = RG.turn(s, k, 1);
  const back = RG.turn(RG.turn(RG.ident(), k, 1), k, -1); if (moved !== 12 || !s.every((v, i) => v === i) || !back.every((v, i) => v === i)) r2 = false;
  const movesCenter = RG.CELLS.some(c => c.center && P[c.id] !== c.id); if (movesCenter !== (R.level === 0)) centerOnlyMiddle = false; });
ok(r2 && centerOnlyMiddle, `R2 사분 회전: 원마다 12칸 · ⁴=항등 · k·(−k)=항등 · 베이스는 가운데 층 원에서만 움직인다`);
// R3
const E = RG.create(H);
const enc = a => a.map(x => x[0] + '/' + x[1]).sort().join(' ');
let sr = 0, sl = 0;
for (let g = 0; g < 1056; g++) { const out = E.sound(g);
  if (enc(out.filter(n => !n.hand).map(n => [n.pitch, n.dur])) === enc(dataRight[g % 32])) sr++;
  if (enc(out.filter(n => n.hand).map(n => [n.pitch, n.dur])) === enc(dataLeft[g % 33])) sl++; }
ok(sr === 1056 && sl === 1056, `R3 다 맞춘 판 한 곡(1056박) = hibari: 오른손 ${sr}/1056 · 왼손 ${sl}/1056`);
// R4
const P2 = RG.CELLS.map(c => RG.flat(c.q)); let md = 1e9; for (let i = 0; i < 54; i++) for (let j = i + 1; j < 54; j++) md = Math.min(md, Math.hypot(P2[i][0] - P2[j][0], P2[i][1] - P2[j][1]));
const span = Math.max(...P2.map(p => Math.hypot(p[0], p[1])));
let onCurve = 0; RG.RINGS.forEach(R => R.cells.forEach(i => { const q = RG.onRing(R, RG.CELLS[i].ang[R.axis]); if (Math.hypot(...q.map((v, k) => v - RG.CELLS[i].q[k])) < 1e-12) onCurve++; }));
ok(md / span >= 0.1 && onCurve === 108, `R4 그림: 가장 가까운 두 점 / 반지름 = ${(md / span).toFixed(3)} · 칸이 제 원의 그 각 위 ${onCurve}/108`);
// R5
let r5 = 0, r5n = 0;
RG.RINGS.forEach(R => R.cells.forEach(i => { const phi = RG.CELLS[i].ang[R.axis], a = RG.flat(RG.onRing(R, phi - 1e-3)), b = RG.flat(RG.onRing(R, phi + 1e-3)), tx = b[0] - a[0], ty = b[1] - a[1];
  const f = RG.pick(i, tx, ty), r = RG.pick(i, -tx, -ty); r5n++; if (f && f.ring === R.id && f.sign === 1 && r && r.ring === R.id && r.sign === -1) r5++; }));
ok(r5 === r5n, `R5 끌기: 제 원의 접선 쪽 → 그 원·+1, 반대 → 그 원·−1 ${r5}/${r5n}`);
// R6
const deg = d => d * Math.PI / 180;
ok(RG.snap(deg(80)) === 1 && RG.snap(deg(-100)) === -1 && RG.snap(deg(130)) === 1 && RG.snap(deg(140)) === 2 && RG.snap(deg(10)) === 0, 'R6 놓기: 80°→1 · −100°→−1 · 130°→1 · 140°→2 · 10°→0');
// R7
let r7 = 0;
RG.RINGS.forEach(R => { E.reset(); const touched = [...new Set(R.cells.map(i => RG.CELLS[i].face))].sort();
  const x = E.move(R.id, 1); const broken = [0, 1, 2, 3, 4, 5].filter(f => !(E.mask() & 1 << f));
  const y = E.undo(); const back = (y.events.faces || []).slice().sort();
  if (touched.length === 4 && broken.join() === touched.join() && back.join() === touched.join() && y.events.all) r7++; });
ok(r7 === 9, `R7 사건: 원을 돌리면 그 원이 지나는 네 송이만 깨지고 되돌리면 네 송이 돌아옴 + 다 맞춤 ${r7}/9`);
// R8
E.reset(); let s8 = 24680; const rnd = () => { s8 = (s8 * 1103515245 + 12345) >>> 0; return s8 / 4294967296; };
for (let m = 0; m < 300; m++) E.move(Math.floor(rnd() * 9), 1 + Math.floor(rnd() * 3));
const scrambled = E.state.filter((v, i) => v !== i).length; for (let m = 0; m < 300; m++) E.undo();
ok(E.state.every((v, i) => v === i) && scrambled > 30, `R8 무작위 300수(제자리 아닌 칸 ${scrambled}) 뒤 되돌리기 300번 = 맞춤`);
// R9
const solvedR = E.sound; E.reset(); const base = []; for (let t = 0; t < 32; t++) base.push(enc(E.sound(t).filter(n => !n.hand).map(n => [n.pitch, n.dur])));
const changed = RG.RINGS.map(R => { E.reset(); E.move(R.id, 1); let c = 0; for (let t = 0; t < 32; t++) if (enc(E.sound(t).filter(n => !n.hand).map(n => [n.pitch, n.dur])) !== base[t]) c++; return c; });
ok(changed.every(c => c > 0), `R9 원마다 사분 회전 한 번이 바꾸는 오른손 스텝 수: ${changed.join(' · ')}`);
// R10
const html = readFileSync(new URL('../sketch/rings.html', import.meta.url), 'utf8');
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
let syntax = true; try { new Function(inline); } catch (e) { syntax = false; console.log(e.message); }
const wakeCalls = (inline.match(/HS\.audio\.wake\(/g) || []).length, wakeInUnlock = /function unlock\(\) \{ if \(!sound\) \{ HS\.audio\.wake\(\)/.test(inline);
const unlockSites = [...inline.matchAll(/unlock\(\)/g)].length, keysByCode = !/\bev\.key\b/.test(inline);
ok(syntax && wakeCalls === 1 && wakeInUnlock && keysByCode, `R10 페이지: 문법 · wake 1곳(unlock 안) · unlock 호출 ${unlockSites - 1}곳 · ev.key 없음`);
console.log(fails ? `FAIL ${fails}개` : '전부 PASS');
