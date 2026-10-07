// tools/verify_cube.mjs — 큐브 판정기 (sketch/cube-core.js · sketch/cube.html).  node tools/verify_cube.mjs
/* 예측 — 돌리기 전에 적었다 (2026-10-07). 결과를 보고 고치지 않는다.
 * ⚠ 정직하게: 엔진을 쓴 직후 node 한 줄로 칸표(54칸 · 사건 59), 움직임마다 20칸, 차수 6·105·6·4, 움직임 방향(R·U·F·D·L·B 표준)을
 *   이미 봤다. 그래서 C1 의 칸 수 · C2 의 20칸 · C3 은 예측이 아니라 확인이다. 나머지는 아직 돌려 보지 않았다.
 *
 * C1  칸표: 54칸 · 소리 사건 59 · 맞춘 큐브 → 오른손 32/32 · 왼손 33/33 (왼손 쉼 칸 = 0) ............................ PASS
 * C2  12가지 움직임: 각 20칸 · 가운데 6칸 고정 · X⁴ = 항등 · X·X′ = 항등 .............................................. PASS
 * C3  차수: R U R′ U′ = 6 · R U = 105 · R2 U2 = 6 · U = 4 ............................................................ PASS
 * C4  U 한 번 → 바뀐 오른손 스텝 = {0,2,4,6,8,9,24,25} 여덟 개 전부 (U 면 스티커가 서로 다른 음이라 다 바뀐다)
 *     D 한 번 → {10,11,16,18,20,22,26} 일곱 개 — 27 은 그대로일 것 (칸 1 의 파4 가 칸 5 로 가는데 칸 5 도 파4) ........ PASS
 * C5  면 판정: 맞춤 6/6 · U 뒤 1/6 (D) · U⁴ 뒤 6/6 ................................................................... PASS
 * C6  무작위 200수 → 거꾸로 되돌리면 맞춤 · undo 200번도 맞춤 ......................................................... PASS
 * C7  move() 가 곧바로 음을 돌려준다 (4음 · at 없음 · 세기 0.22) ...................................................... PASS
 * C8  되풀이: 공식 U 는 4번째에만 '제자리' · R U R′ U′ 는 6번째에만 .................................................... PASS
 * C9  흐트린 상태에서 1056박 동안 박마다 왼손 = 오른손 스텝 (g mod 33)−1 의 음 (세기 ×0.78) ............................. PASS
 * C10 끌기: 앞면 오른쪽 열을 위로 → R · 앞면 윗줄을 오른쪽으로 → U′ · 가운데 층 → 보기 돌리기 (정면 · 기본 보기 둘 다) .... PASS
 * C10b (덧붙임) 보이는 칸 × 8방향 × 보기 3: 고른 층이 조금 돌 때 그 스티커가 화면에서 끈 쪽으로 가나.
 *     사양대로(접선 축을 투영해 고르기)면 대각선으로 애매하게 끈 경우(정렬 ≤ 0.6)에서 거꾸로 가는 쌍이 생길 것 — 통과율 ≥ 90% ... 아슬
 * C11 펴기: 54점이 서로 다르다(최소 거리 > 1e-3) · 띠 9개 × 12장이 그 띠 곡선 위(< 1e-6) · 모서리 보기에서 120° 대칭 ........ PASS
 * C12 cube.html 스크립트 문법 · HS.audio.wake 는 제스처 처리기 안에서만 불린다 .......................................... PASS
 * C13 (덧붙임) 가짜 DOM 에서 페이지가 돈다: 불러오기 → 예시(무음) 30초에 공식 U 가 쉼마다 4번 → 제자리 → R U R′ U′ 로 ·
 *     키 U(곧바로 4음) · Shift+U(다시 hibari) · 스티커 끌기 = R · 처음으로 · 되풀이(곧바로 1/6, 쉼 다섯 번 뒤 제자리) · 펴기 · 되돌리기 ... PASS
 */
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import vm from 'vm'; import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const HS = require('../sketch/common.js'); const D = require('../lenia/tonnetz.json'); const H = HS.derive(D);
const C = require('../sketch/cube-core.js');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) { fails++; process.exitCode = 1; } };
const ms = a => a.map(n => n.pitch + '/' + n.dur).sort().join(' ');                      // 음높이·길이 다중집합
const modSig = (h, t) => H.mod[h].steps[t].map(li => H.notes[li].pitch + '/' + H.notes[li].dur).sort().join(' ');
const ALL = []; C.FACES.forEach(f => ALL.push(f, f + "'"));
const rng = HS.rng(20261007);

// ── C1 칸표 ───────────────────────────────────────────────────────────────────────────────
{ const E = C.create(H), T = E.table;
  const nEv = T.cell.reduce((s, c) => s + c.ev.length, 0), twice = T.cell.filter(c => c.ev.length === 2).length;
  ok(T.cell.length === 54 && nEv === 59 && twice === 5 && T.cell.every((c, i) => c.ev.length === (C.CELLS[i].center && C.CELLS[i].face < 5 ? 2 : 1)),
    `C1 칸 ${T.cell.length} · 소리 사건 ${nEv} = 54 + ${twice} (두 번 우는 칸 = 자리 0–4 의 가운데)`);
  let r = 0; for (let t = 0; t < 32; t++) if (ms(E.stepNotes(t, 0)) === modSig(0, t)) r++;
  let l = 0; for (let g = 0; g < 33; g++) if (ms(E.sound(g).filter(n => n.hand === 1)) === modSig(1, g)) l++;
  ok(r === 32 && l === 33 && T.gap === 0, `C1 맞춘 큐브 = hibari: 오른손 ${r}/32 · 왼손 ${l}/33 (왼손 쉼 칸 ${T.gap})`);
  ok(T.seat.join('') === '미파솔라시도' && T.rest.join() === '12,28' && T.first.join() === '0,16', `C1 자리 이름 ${T.seat.join('')} · 쉼 시작 ${T.rest} · 구절 첫 화음 ${T.first}`); }

// ── C2 움직임 ─────────────────────────────────────────────────────────────────────────────
{ const id = C.ident(); let moved = [], fixed = true, four = true, back = true;
  for (const f of C.FACES) { moved.push(C.QT[f].filter((j, i) => j !== i).length);
    C.CELLS.forEach((c, i) => { if (c.center && C.QT[f][i] !== i) fixed = false; });
    if (!C.same(C.run(id, [f, f, f, f]), id)) four = false;
    if (!C.same(C.run(id, [f, f + "'"]), id) || !C.same(C.run(id, [f + "'", f]), id)) back = false; }
  const primeMoved = C.FACES.map(f => C.run(C.ident(), [f + "'"]).filter((s, i) => s !== i).length);
  ok(moved.every(n => n === 20) && primeMoved.every(n => n === 20), `C2 12가지 움직임이 옮기는 칸: ${moved.concat(primeMoved).join(',')}`);
  ok(fixed && four && back, `C2 가운데 6칸 고정 ${fixed} · X⁴ = 항등 ${four} · X·X′ = 항등 ${back}`); }

// ── C3 차수 ───────────────────────────────────────────────────────────────────────────────
{ const want = [["R U R' U'", 6], ['R U', 105], ['R2 U2', 6], ['U', 4]];
  const got = want.map(([s]) => C.orderOf(s.split(' ')));
  ok(got.every((o, i) => o === want[i][1]), `C3 차수 ${want.map(([s], i) => C.show(s) + ' = ' + got[i]).join(' · ')}`); }

// ── C4 음악의 뜻 ──────────────────────────────────────────────────────────────────────────
function changedSteps(moves) { const E = C.create(H), before = []; for (let t = 0; t < 32; t++) before.push(ms(E.stepNotes(t, 0)));
  moves.forEach(m => E.move(m)); const out = []; for (let t = 0; t < 32; t++) if (ms(E.stepNotes(t, 0)) !== before[t]) out.push(t); return out; }
{ const u = changedSteps(['U']), allowU = [0, 2, 4, 6, 8, 9, 24, 25], keepU = [1, 3, 5, 7, 16, 17, 18, 19, 20, 21, 22, 23];
  ok(u.every(t => allowU.includes(t)) && [0, 2, 4, 6].every(t => u.includes(t)) && keepU.every(t => !u.includes(t)), `C4 U 한 번 → 바뀐 오른손 스텝 [${u}] (예측 [${allowU}])`);
  const E = C.create(H); E.move('U'); const bass = [0, 2, 4, 6].map(t => E.stepNotes(t, 0).reduce((a, n) => Math.min(a, n.pitch), 99));
  ok(bass.join() === '52,53,55,57', `C4 U 뒤에도 베이스 그대로: ${bass.map(HS.noteName).join(' ')}`);
  const d = changedSteps(['D']), allowD = [10, 11, 16, 18, 20, 22, 26, 27];
  ok(d.every(t => allowD.includes(t)) && [16, 18, 20, 22].every(t => d.includes(t)), `C4 D 한 번 → 바뀐 오른손 스텝 [${d}] (예측 [10,11,16,18,20,22,26])`); }

// ── C5 면 판정 ────────────────────────────────────────────────────────────────────────────
{ const E = C.create(H), a = E.probe().solvedFaces; E.move('U'); const p = E.probe(); E.move('U'); E.move('U'); E.move('U'); const c = E.probe().solvedFaces;
  ok(a === 6 && p.solvedFaces === 1 && p.faces.join() === '5' && c === 6, `C5 맞춤 ${a}/6 · U 뒤 ${p.solvedFaces}/6 (${p.faces.map(f => C.FACES[f])}) · U⁴ 뒤 ${c}/6`);
  const E2 = C.create(H); E2.move('R'); const x = E2.move("R'");
  ok(x.events.all && x.events.faces.length === 5 && E2.move('U').events.faces.length === 0, `C5 사건: R R′ → 다 맞춤 (새로 돌아온 면 ${x.events.faces.length}개 — 돌리지 않은 L 은 처음부터 맞아 있었다) · 그다음 U → 사건 없음`); }

// ── C6 되돌리기 ───────────────────────────────────────────────────────────────────────────
{ const E = C.create(H), seq = []; for (let i = 0; i < 200; i++) { const m = ALL[Math.floor(rng() * 12)]; seq.push(m); E.move(m); }
  const scr = 54 - E.state.filter((s, i) => s === i).length;
  for (let i = seq.length - 1; i >= 0; i--) E.move(C.inv(seq[i]));
  const E2 = C.create(H); seq.forEach(m => E2.move(m)); let n = 0; while (E2.undo()) n++;
  ok(E.probe().solved && E2.probe().solved && n === 200 && scr > 30, `C6 무작위 200수(제자리 아닌 칸 ${scr}) → 거꾸로 = 맞춤 ${E.probe().solved} · undo ${n}번 = 맞춤 ${E2.probe().solved}`); }

// ── C7 곧바로 소리 ────────────────────────────────────────────────────────────────────────
{ const E = C.create(H), res = ALL.map(m => E.move(m));
  ok(res.every(x => x.notes.length >= 3 && x.notes.every(n => n.at == null && n.vel === 0.22 && n.pitch > 0)),
    `C7 돌리는 호출이 곧바로 음을 돌려준다: ${res.map(x => C.show(x.name) + ':' + x.notes.length).join(' ')} (D 는 윗줄 3음)`); }

// ── C8 되풀이 ─────────────────────────────────────────────────────────────────────────────
function homes(formula) { const E = C.create(H); E.move('F'); E.move('R');               // 맞춘 상태가 아닌 곳에서 시작해도 제자리로 와야 한다
  E.setRepeat(true, formula); const hits = []; let n = 0;
  for (let g = 0; g < 32 * 8 && n < 8; g++) { const o = E.beat(); if (o.rep) { n++; if (o.rep.home) hits.push(n); } } return hits; }
{ const u = homes(['U']), x = homes(['R', 'U', "R'", "U'"]);
  ok(u[0] === 4 && x[0] === 6 && u.join() === '4,8' && x.join() === '6', `C8 제자리가 난 회차: U [${u}] · R U R′ U′ [${x}] (8회 중)`);
  const E = C.create(H); E.move('R'); E.move('U'); const info = E.setRepeat(true);
  ok(info.formula === 'R U' && info.order === 105 && E.probe().rec.length === 0, `C8 공식 = 내가 돌린 것: ${info.formula} · 차수 ${info.order}`);
  E.move('F'); ok(E.rep === null, 'C8 손으로 돌리면 되풀이가 꺼진다');
  const E3 = C.create(H); ['U', 'U', "U'", 'R', 'R', 'R', 'R', 'F'].forEach(m => E3.move(m));
  ok(E3.setRepeat(true).formula === 'U F', `C8 이어진 같은 면은 합친다: U U U′ R R R R F → ${E3.rep.formula}`); }

// ── C9 두 손 ──────────────────────────────────────────────────────────────────────────────
{ const E = C.create(H); for (let i = 0; i < 40; i++) E.move(ALL[Math.floor(rng() * 12)]);
  let bad = 0, n = 0;
  for (let g = 0; g < 1056; g++) { const L = E.sound(g).filter(x => x.hand === 1), l = g % 33;
    const want = l >= 1 ? E.stepNotes(l - 1, 0) : [];
    const same = ms(L) === ms(want) && L.every((x, i) => Math.abs(x.vel - want[i].vel * 0.78) < 1e-12);
    if (!same) bad++; if (L.length) n++; }
  ok(bad === 0 && n > 600, `C9 1056박: 왼손이 오른손 스텝 (g mod 33)−1 과 다른 박 ${bad} · 왼손이 운 박 ${n}`); }

// ── C10 끌기 → 움직임 ─────────────────────────────────────────────────────────────────────
const VIEWS = { 정면: [0, 0], 기본: [-0.62, 0.5], 모서리: [C.CORNER.yaw, C.CORNER.pitch] };
const pj = ([y, p]) => C.projector(C.view(y, p), 10, 80, 200, 200);
const cell = (f, r, c) => C.FACES.indexOf(f) * 9 + r * 3 + c;
for (const nm of ['정면', '기본']) { const P = pj(VIEWS[nm]);
  const R = [0, 1, 2].map(r => C.dragMove(cell('F', r, 2), 0, -40, P).move), Up = [0, 1, 2].map(c => C.dragMove(cell('F', 0, c), 40, 0, P).move);
  const mid = [C.dragMove(cell('F', 1, 1), 0, -40, P), C.dragMove(cell('F', 1, 0), 40, 0, P), C.dragMove(cell('F', 0, 1), 0, -40, P)];
  ok(R.every(m => m === 'R') && Up.every(m => m === "U'"), `C10 ${nm} 보기: 앞면 오른쪽 열 위로 → ${R.map(C.show)} · 앞면 윗줄 오른쪽으로 → ${Up.map(C.show)}`);
  ok(mid.every(x => x && x.view && x.move === null), `C10 ${nm} 보기: 가운데 층(가운데 열 위로 · 가운데 줄 옆으로 · 윗줄 가운데 위로) → 보기 돌리기`); }
{ let tot = 0, good = 0, worst = []; const bandA = { lo: 0, hi: 0 };
  for (const nm of Object.keys(VIEWS)) { const M = C.view(...VIEWS[nm]), P = C.projector(M, 10, 80, 200, 200);
    for (const c of C.CELLS) { const nv = C.mul(M, c.n), cv = C.mul(M, c.pos), facing = (nv[0] * -cv[0] + nv[1] * -cv[1] + nv[2] * (10 - cv[2])) / Math.hypot(-cv[0], -cv[1], 10 - cv[2]);
      if (facing < 0.25) continue;
      for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4, dx = Math.cos(a) * 40, dy = Math.sin(a) * 40, r = C.dragMove(c.id, dx, dy, P); if (!r || !r.move) continue;
        const m = C.parse(r.move), n = C.FR[m.f][0], th = C.angleOf(r.move) * 0.06, p0 = P(c.pos), p1 = P(C.rot(c.pos, n, th));
        const along = (p1[0] - p0[0]) * dx + (p1[1] - p0[1]) * dy; tot++; if (along > 0) good++; else worst.push(`${nm} ${C.FACES[c.face]}(${c.r},${c.c}) ${k * 45}° → ${C.show(r.move)} 정렬 ${r.align.toFixed(2)}`);
        if (along > 0) bandA.hi = Math.max(bandA.hi, 0); } } }
  ok(good / tot >= 0.9, `C10b 고른 층이 끈 쪽으로 돈다 ${good}/${tot} (${(100 * good / tot).toFixed(1)}%)` + (worst.length ? ` · 거꾸로 ${worst.length}: ${worst.slice(0, 4).join(' | ')}${worst.length > 4 ? ' …' : ''}` : '')); }
// C10c — C10b 를 돌려 본 뒤 덧붙임 (2026-10-07). C10b 의 예측("거꾸로는 정렬 ≤ 0.6 인 애매한 대각선에서만")은 틀렸다:
//   거꾸로 28쌍은 정렬 0.85 까지 있고, 전부 층의 가운데 줄이 아닌 스티커(모서리를 감아 돌며 처음 화면 움직임이 꺾인다)였다. 정면 보기에선 0.
//   층이 끈 쪽으로 도는지는 그 층·그 면의 가운데 줄 스티커(감아 도는 성분이 없다)로 잰다. 예측(덧붙이며 적음): 100%.
{ let tot = 0, good = 0;
  for (const nm of Object.keys(VIEWS)) { const M = C.view(...VIEWS[nm]), P = C.projector(M, 10, 80, 200, 200);
    for (const c of C.CELLS) { const nv = C.mul(M, c.n), cv = C.mul(M, c.pos), facing = (nv[0] * -cv[0] + nv[1] * -cv[1] + nv[2] * (10 - cv[2])) / Math.hypot(-cv[0], -cv[1], 10 - cv[2]);
      if (facing < 0.25) continue;
      for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4, dx = Math.cos(a) * 40, dy = Math.sin(a) * 40, r = C.dragMove(c.id, dx, dy, P); if (!r || !r.move) continue;
        const m = C.parse(r.move), n = C.FR[m.f][0], th = C.angleOf(r.move) * 0.06, mov = [0, 1, 2].filter(i => n[i] === 0 && c.n[i] === 0)[0], mid = c.pos.slice(); mid[mov] = 0;
        const q0 = P(mid), q1 = P(C.rot(mid, n, th)); tot++; if ((q1[0] - q0[0]) * dx + (q1[1] - q0[1]) * dy > 0) good++; } } }
  ok(good === tot, `C10c (덧붙임) 돈 층의 가운데 줄은 끈 쪽으로 간다 ${good}/${tot}`); }

// ── C11 펴기 ──────────────────────────────────────────────────────────────────────────────
{ const M = C.view(C.CORNER.yaw, C.CORNER.pitch), F = C.CELLS.map(c => C.flat(c.pos, M));
  let dmin = Infinity; for (let i = 0; i < 54; i++) for (let j = i + 1; j < 54; j++) dmin = Math.min(dmin, Math.hypot(F[i][0] - F[j][0], F[i][1] - F[j][1]));
  ok(dmin > 1e-3, `C11 54개 스티커 → 서로 다른 점 (가장 가까운 두 점 ${dmin.toFixed(4)})`);
  const B = C.bands(); let worst = 0, cnt = 0;
  const segD = (p, a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1], u = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1))); return Math.hypot(a[0] + u * dx - p[0], a[1] + u * dy - p[1]); };
  B.forEach(b => { const Q = b.path.map(p => C.flat(p, M)); b.cells.forEach(i => { let d = Infinity; for (let k = 0; k < Q.length; k++) d = Math.min(d, segD(F[i], Q[k], Q[(k + 1) % Q.length])); worst = Math.max(worst, d); cnt++; }); });
  ok(B.length === 9 && B.every(b => b.cells.length === 12) && cnt === 108 && worst < 1e-6, `C11 띠 ${B.length}개 × ${B[0].cells.length}장 (${cnt}) 이 그 띠 곡선 위 — 가장 먼 것 ${worst.toExponential(1)}`);
  const cyc = p => [p[2], p[0], p[1]];                                                     // (x,y,z) → (z,x,y): 모서리 축 둘레 120°
  const idx = {}; C.CELLS.forEach(c => idx[c.pos.join()] = c.id); const pi = C.CELLS.map(c => idx[cyc(c.pos).join()]);
  let ang = null, mis = 0; C.CELLS.forEach((c, i) => { const a = F[i], b = F[pi[i]], r = Math.hypot(a[0], a[1]);
    if (r > 1e-6) { const th = Math.atan2(b[1], b[0]) - Math.atan2(a[1], a[0]); const t = ((th % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI); if (ang == null) ang = t; }
    const c2 = Math.cos(ang), s2 = Math.sin(ang); mis = Math.max(mis, Math.hypot(a[0] * c2 - a[1] * s2 - b[0], a[0] * s2 + a[1] * c2 - b[1])); });
  ok(mis < 1e-9 && Math.abs(Math.min(ang, 2 * Math.PI - ang) - 2 * Math.PI / 3) < 1e-9, `C11 모서리 보기에서 3겹 대칭: 스티커를 (x,y,z)→(z,x,y) 로 옮기면 평면 점이 ${(ang * 180 / Math.PI).toFixed(1)}° 돈 자리 (어긋남 ${mis.toExponential(1)})`);
  const R = F.map(p => Math.hypot(p[0], p[1])); ok(Math.max(...R) < C.FLATMAX, `C11 펼친 반지름 ${Math.min(...R).toFixed(3)} … ${Math.max(...R).toFixed(3)} (< ${C.FLATMAX.toFixed(3)})`); }

// ── C12 페이지 스크립트 ───────────────────────────────────────────────────────────────────
const HTML = fs.readFileSync(path.join(ROOT, 'sketch/cube.html'), 'utf8');
const INLINE = [...HTML.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
{ let syn = true, err = ''; INLINE.forEach(s => { try { new Function(s); } catch (e) { syn = false; err = e.message; } });
  ok(INLINE.length === 1 && syn, `C12 인라인 스크립트 ${INLINE.length}개 문법 ${syn ? '맞음' : '틀림: ' + err}`);
  const srcs = [...HTML.matchAll(/<script src="([^"]+)"/g)].map(m => m[1].split('?')[0]);
  ok(srcs.join() === './common.js,./cube-core.js' && srcs.every(s => fs.existsSync(path.join(ROOT, 'sketch', s))), `C12 바깥 스크립트 = 이 저장소 파일뿐: ${srcs}`); }
/** 제스처 검사: 주석·문자열 속을 지운 뒤 함수 범위를 괄호 짝으로 찾는다. wake 를 부르는 곳의 가장 안쪽 함수가
 *  (가) 제스처 이벤트에 바로 넘긴 이름 없는 함수이거나 (나) 그런 곳에서만 불리는 이름 있는 함수여야 한다. */
function gestureCheck(code) {
  let clean = ''; for (let i = 0; i < code.length;) { const c = code[i], d = code[i + 1];
    if (c === '/' && d === '/') { while (i < code.length && code[i] !== '\n') { clean += ' '; i++; } continue; }
    if (c === '/' && d === '*') { while (i < code.length && !(code[i] === '*' && code[i + 1] === '/')) { clean += code[i] === '\n' ? '\n' : ' '; i++; } clean += '  '; i += 2; continue; }
    if (c === "'" || c === '"') { clean += c; i++; while (i < code.length && code[i] !== c) { if (code[i] === '\\') { clean += 'x'; i++; } clean += 'x'; i++; } clean += c; i++; continue; }
    clean += c; i++; }
  const fns = [], re = /function\s*([A-Za-z_$][\w$]*)?\s*\(/g; let m;
  while ((m = re.exec(clean))) { let i = m.index + m[0].length, dep = 1; while (dep && i < clean.length) { if (clean[i] === '(') dep++; else if (clean[i] === ')') dep--; i++; }
    while (clean[i] !== '{') i++; const b = i; dep = 0; do { if (clean[i] === '{') dep++; else if (clean[i] === '}') dep--; i++; } while (dep && i < clean.length);
    fns.push({ name: m[1] || null, start: m.index, b: b, e: i }); }
  const GEST = /(?:addEventListener\(\s*'(?:pointerdown|pointerup|click|keydown|touchend)'\s*,\s*|HS\.keys\(\s*)$/;
  const inner = pos => fns.filter(f => f.b < pos && pos < f.e).sort((a, b) => (a.e - a.b) - (b.e - b.b))[0] || null;
  const isGestureCb = f => !f.name && GEST.test(code.slice(Math.max(0, f.start - 80), f.start));
  let G = new Set(fns.filter(f => f.name).map(f => f.name)), changed = true;
  const okAt = (pos, G) => { const f = inner(pos); return !!f && (isGestureCb(f) || (f.name && G.has(f.name))); };
  while (changed) { changed = false;
    for (const name of [...G]) { const rr = new RegExp('(^|[^\\w$.])' + name.replace('$', '\\$') + '(?![\\w$])', 'g'); let q;
      while ((q = rr.exec(clean))) { const at = q.index + q[1].length; if (/function\s*$/.test(clean.slice(Math.max(0, at - 12), at))) continue;   // 정의
        const after = clean.slice(at + name.length).match(/^\s*(\(|\))/), before = code.slice(Math.max(0, at - 60), at);
        const asListener = after && after[1] === ')' && /addEventListener\(\s*'(?:pointerdown|pointerup|click|keydown|touchend)'\s*,\s*$/.test(before);
        const asCall = after && after[1] === '(' && okAt(at, G);
        if (!asListener && !asCall) { G.delete(name); changed = true; break; } } } }
  const wakes = [...clean.matchAll(/audio\s*\.\s*wake/g)].map(w => w.index);
  const bad = wakes.filter(p => !/^\s*\(/.test(clean.slice(p + clean.slice(p).indexOf('wake') + 4)) || !okAt(p, G));
  return { wakes: wakes.length, bad: bad.length, where: bad.map(p => code.slice(p - 40, p + 20).replace(/\s+/g, ' ')) };
}
{ const g = gestureCheck(INLINE[0] || '');
  ok(g.wakes >= 1 && g.bad === 0, `C12 HS.audio.wake ${g.wakes}곳 — 제스처 처리기 밖 ${g.bad}` + (g.bad ? ': ' + g.where.join(' | ') : ''));
  const neg = gestureCheck("function unlock(){HS.audio.wake();} el.addEventListener('click', function(){ unlock(); }); HS.hook({ go: function(){ unlock(); } });");
  const pos = gestureCheck("function unlock(){HS.audio.wake();} el.addEventListener('click', function(){ unlock(); }); HS.keys(function(c){ unlock(); });");
  ok(neg.bad === 1 && pos.bad === 0, `C12 제스처 검사기 자체: 훅에서 부르면 잡는다(${neg.bad}) · 제스처에서만이면 통과(${pos.bad})`);
  ok(!/\bev\.key\b|\be\.key\b/.test(INLINE[0] || '') && /\.code\b|HS\.keys/.test(INLINE[0] || ''), 'C12 키는 ev.code 로만 읽는다 (ev.key 없음)'); }

// ── C13 가짜 DOM 에서 페이지 ──────────────────────────────────────────────────────────────
async function pageSmoke() {
  const els = {}, winL = {}, raf = [], logs = [];
  function stub(id) { const L = {}, cls = new Set();
    return { id, L, style: {}, dataset: {}, hidden: false, disabled: false, textContent: '', innerHTML: '', clientWidth: 0, clientHeight: 0, width: 0, height: 0,
      classList: { add: (...c) => c.forEach(x => cls.add(x)), remove: (...c) => c.forEach(x => cls.delete(x)), contains: c => cls.has(c),
        toggle: (c, on) => { if (on === undefined ? !cls.has(c) : on) cls.add(c); else cls.delete(c); return cls.has(c); } },
      setAttribute(k, v) { this['@' + k] = String(v); }, getAttribute(k) { return this['@' + k]; }, addEventListener(t, f) { (L[t] = L[t] || []).push(f); },
      getBoundingClientRect() { return { left: 0, top: 0, width: this.clientWidth, height: this.clientHeight, right: this.clientWidth, bottom: this.clientHeight }; },
      setPointerCapture() {}, releasePointerCapture() {}, hasPointerCapture() { return false; }, focus() {}, blur() {}, appendChild(c) { return c; },
      getContext() { const store = {}; const f = function () { return p; }; const p = new Proxy(f, { get: (t, k) => k === 'measureText' ? () => ({ width: 10 }) : (k in store ? store[k] : f), set: (t, k, v) => { store[k] = v; return true; }, apply: () => p }); return p; } }; }
  const $ = s => els[s] || (els[s] = stub(s)); const $$ = s => els['all:' + s] || (els['all:' + s] = [0, 1, 2, 3, 4, 5].map(i => stub(s + i)));
  $('#cv').clientWidth = 375; $('#cv').clientHeight = 520;
  const sb = { console: { log: (...a) => logs.push(a.join(' ')), warn: () => {}, error: (...a) => logs.push('ERR ' + a.join(' ')) },
    location: { search: '?silent' }, performance: { now: () => clockMs }, devicePixelRatio: 2, innerWidth: 375, innerHeight: 760,
    document: { hidden: false, querySelector: $, querySelectorAll: $$, getElementById: id => $('#' + id), addEventListener: () => {}, createElement: () => stub('new') },
    addEventListener: (t, f) => { (winL[t] = winL[t] || []).push(f); }, removeEventListener: () => {},
    requestAnimationFrame: f => { raf.push(f); return raf.length; }, setInterval: () => 0, clearInterval: () => {}, setTimeout: () => 0, clearTimeout: () => {},
    fetch: () => Promise.resolve({ json: () => Promise.resolve(JSON.parse(JSON.stringify(D))) }), matchMedia: () => ({ matches: false }),
    Math, JSON, Promise, Object, Array, Number, String, Set, Map, Float32Array, Int16Array, Int32Array, Uint8Array, Date, Error, RegExp, isFinite, parseFloat, parseInt };
  let clockMs = 1000; sb.window = sb; sb.globalThis = sb; vm.createContext(sb);
  for (const f of ['sketch/common.js', 'sketch/cube-core.js']) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), sb, { filename: f });
  vm.runInContext(INLINE[0], sb, { filename: 'cube.html' });
  for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r));
  const K = sb.__sk; if (!K) return { err: '훅이 없다 (불러오기 실패?) ' + logs.join(' / ') };
  const frames = n => { for (let i = 0; i < n; i++) { clockMs += 16.7; const q = raf.splice(0); q.forEach(f => f(clockMs)); } };
  const key = (code, shift) => (winL.keydown || []).forEach(f => f({ code, shiftKey: !!shift, ctrlKey: false, metaKey: false, altKey: false, preventDefault() {} }));
  const keyup = code => (winL.keyup || []).forEach(f => f({ code, preventDefault() {} }));
  const click = id => ($(id).L.click || []).forEach(f => f({ preventDefault() {} }));
  const ptr = (type, x, y) => ($('#cv').L[type] || []).forEach(f => f({ clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, preventDefault() {} }));
  const R = { logs };
  frames(3); R.p0 = K.probe();
  K.advance(30); frames(20); R.p30 = K.probe();
  key('KeyU'); keyup('KeyU'); R.c1 = sb.HS.audio.calls.slice(); R.pU = K.probe(); frames(5);
  key('KeyU', true); keyup('KeyU'); R.pUi = K.probe(); R.msgU = $('#msg').textContent; frames(15);
  K.view(-0.62, 0.5); const at = K.at(C.FACES.indexOf('F') * 9 + 1 * 3 + 2); R.at = at;   // 예시 30초 동안 저절로 돌아 앞면이 뒤로 갔다 — 기본 보기로                     // 앞면 오른쪽 열 가운데 칸
  ptr('pointerdown', at[0], at[1]); for (let k = 1; k <= 6; k++) ptr('pointermove', at[0] + 0.3 * k, at[1] - 8 * k); ptr('pointerup', at[0] + 2, at[1] - 48); R.pDrag = K.probe(); frames(15);
  ptr('pointerdown', 4, 4); for (let k = 1; k <= 5; k++) ptr('pointermove', 4 + 12 * k, 4); ptr('pointerup', 64, 4); R.pView = K.probe(); frames(5);
  click('#reset'); R.pReset = K.probe(); click('#rep'); R.pRep = K.probe(); R.tagRep = $('#info').textContent;
  K.advance(16 * HS.SEC * 5 + 0.1); frames(30); R.pRep5 = K.probe(); R.msgRep = $('#msg').textContent;
  click('#unfold'); frames(90); R.pUnf = K.probe(); click('#unfold'); frames(90);
  click('#undo'); R.pUndo = K.probe();
  click('#listen'); frames(3); R.pDemo = K.probe();
  return R;
}
try { const R = await pageSmoke();
  if (R.err) ok(false, 'C13 ' + R.err);
  else { const errs = R.logs.filter(l => /^ERR/.test(l));
    ok(R.p0.mode === 'demo' && !R.p0.sound && R.p0.solved && R.p0.calls === 0, `C13 들어오면 예시 · 소리 꺼짐 · 맞춘 큐브 · 소리 호출 ${R.p0.calls}`);
    ok(R.p30.solved && R.p30.moves === 4 && R.p30.formula === 'R U R′ U′' && R.p30.calls === 0, `C13 예시 30초: 쉼마다 U 4번(움직임 ${R.p30.moves}) → 제자리(맞춤 ${R.p30.solved}) → 다음 공식 ${R.p30.formula} · 소리 호출 ${R.p30.calls}`);
    const turn = R.c1.slice(-4);
    ok(R.pU.mode === 'play' && R.pU.sound && R.pU.solvedFaces === 1 && turn.length === 4 && turn.every(c => c.delay > 0 && c.delay < 0.01), `C13 키 U: 직접 하기 · 소리 켜짐 · 면 ${R.pU.solvedFaces}/6 · 곧바로 ${turn.length}음 (지연 ${turn.map(c => (c.delay * 1000).toFixed(0) + 'ms').join(',')})`);
    ok(R.pUi.solved && /hibari/.test(R.msgU), `C13 Shift+U: 맞춤 ${R.pUi.solved} · 글 "${R.msgU}"`);
    ok(R.pDrag.moves === R.pUi.moves + 1 && R.pDrag.last === 'R', `C13 앞면 오른쪽 열을 위로 끌기 (${R.at.map(v => v.toFixed(0))}) → ${R.pDrag.last} (움직임 ${R.pUi.moves}→${R.pDrag.moves})`);
    ok(R.pView.moves === R.pDrag.moves && Math.abs(R.pView.yaw - R.pDrag.yaw) > 0.1, `C13 큐브 밖 끌기 = 보기만 돈다 (yaw ${R.pDrag.yaw.toFixed(2)}→${R.pView.yaw.toFixed(2)}, 움직임 그대로)`);
    ok(R.pReset.solved && R.pReset.moves === 0 && R.pReset.step === 0, `C13 처음으로: 맞춤 · 기록 0 · 박 ${R.pReset.step}`);
    ok(R.pRep.formula && R.pRep.order >= 1 && R.pRep.count === 1, `C13 되풀이: 곧바로 한 번 (${R.pRep.formula} · ${R.pRep.count}/${R.pRep.order}) · "${R.tagRep}"`);
    ok(R.pRep5.count === 0 && /제자리/.test(R.msgRep) && R.pRep5.solved, `C13 쉼 다섯 번 뒤 제자리: "${R.msgRep}" · 맞춤 ${R.pRep5.solved}`);
    ok(R.pUnf.unfold === 1 && R.pUndo.moves === R.pRep5.moves - 1, `C13 펴기 켬 ${R.pUnf.unfold} · 되돌리기 ${R.pRep5.moves}→${R.pUndo.moves}`);
    ok(R.pDemo.mode === 'demo' && R.pDemo.solved && R.pDemo.sound, `C13 ▶ 예시 듣기: 예시 다시 · 맞춤 · 소리 켬`);
    ok(errs.length === 0, `C13 콘솔 오류 ${errs.length}` + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : '')); } }
catch (e) { ok(false, 'C13 페이지가 가짜 DOM 에서 멈췄다: ' + (e && e.stack || e).toString().split('\n').slice(0, 4).join(' / ')); }

console.log(fails ? `\n${fails}개 FAIL` : '\n전부 PASS');
