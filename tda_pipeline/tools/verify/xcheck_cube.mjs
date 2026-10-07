// tools/verify/xcheck_cube.mjs — 검산: 큐브 엔진 ↔ 내 독립 구현(cube_ref.mjs). 회전표 · 칸표 · 무작위 공식 뒤 박마다 두 손의 음.
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import * as REF from './xcheck_cube_ref.mjs';
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL('../..', import.meta.url)).replace(/[\/]$/, '');
const HS = require(ROOT + '/sketch/common.js');
const C = require(ROOT + '/sketch/cube-core.js');
const H = HS.derive(require(ROOT + '/lenia/tonnetz.json'));
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) process.exitCode = 1; };

// ① 회전표: 엔진 QT[f][i] = j (칸 i 의 스티커 → 칸 j) ↔ 내 MOVES[f][i]
let qtSame = 0; C.FACES.forEach(f => { if (C.QT[f].every((j, i) => j === REF.MOVES[f][i])) qtSame++; });
ok(qtSame === 6, `회전표 6면 중 ${qtSame}면이 내 기하 구현과 칸 단위로 같다`);
// 역방향도
let invSame = 0; C.FACES.forEach(f => { const st = C.turnState(C.ident(), f, 3), mine = REF.apply(REF.SOLVED, f + "'"); if (C.same(st, mine)) invSame++; });
ok(invSame === 6, `역방향(′) 6면 중 ${invSame}면 같다`);
// ② 칸표: 칸마다 제 음높이와 [박, 길이]
const E = C.create(H), T = E.table || C.table(H);
const homeE = E.home;
let homeSame = 0; for (let i = 0; i < 54; i++) if (homeE[i] === REF.HOME[i] || (homeE[i] && homeE[i].pitch === REF.HOME[i])) homeSame++;
ok(homeSame === 54, `칸 54개의 제 음높이 ${homeSame}/54 같다`);
// ③ 박마다 두 손: 엔진의 sound(g) 를 음높이·길이 다중집합으로 읽어 내 readRight/readLeft 와 대조
function engineStep(g) {
  const out = E.sound(g), R = [], L = [];
  out.forEach(n => { const rec = [n.pitch, Math.round((n.dur != null ? n.dur : n.d) / (n.dur > 20 ? 1 : 1))]; (n.hand ? L : R).push(n); });
  return { R, L };
}
const sample = E.sound(0);
console.log('엔진 sound(0) 첫 음:', JSON.stringify(sample[0]));

// ④ 무작위 공식 300개 × 한 곡(1056박): 엔진 sound(g) 의 두 손 음(음높이/길이 다중집합) ↔ 내 상태를 내 칸표로 읽은 것
let s2 = 24680; const rr = () => { s2 = (s2 * 1103515245 + 12345) >>> 0; return s2 / 4294967296; };
const NAMES = Object.keys(REF.MOVES);
let beats = 0, bad = 0, firstBad = null;
const encS = a => a.map(x => x[0] + '/' + x[1]).sort().join(' ');
for (let trial = 0; trial < 300; trial++) {
  const len = 1 + Math.floor(rr() * 25), seq = Array.from({ length: len }, () => NAMES[Math.floor(rr() * NAMES.length)]);
  let mine = REF.SOLVED; seq.forEach(m => { mine = REF.apply(mine, m); });
  E.state = C.run(C.ident(), seq);
  const R = REF.readRight(mine), L = REF.readLeft(mine);
  for (let g = 0; g < 1056; g += (trial < 5 ? 1 : 7)) {
    const out = E.sound(g), eR = out.filter(n => !n.hand).map(n => [n.pitch, n.dur]), eL = out.filter(n => n.hand).map(n => [n.pitch, n.dur]);
    const want = { R: R[g % 32], L: L[g % 33] };
    beats++;
    if (encS(eR) !== encS(want.R) || encS(eL) !== encS(want.L)) { bad++; if (!firstBad) firstBad = { trial, seq: seq.join(' '), g, eR: encS(eR), wR: encS(want.R), eL: encS(eL), wL: encS(want.L) }; }
  }
}
ok(bad === 0, `무작위 공식 300개 뒤 박 ${beats}개: 두 손 음이 다른 박 ${bad}개`);
if (firstBad) console.log(JSON.stringify(firstBad));
// ⑤ 맞춘 상태 = 원곡 (엔진으로)
E.state = C.ident(); let sameR = 0, sameL = 0;
for (let g = 0; g < 1056; g++) { const out = E.sound(g);
  if (encS(out.filter(n => !n.hand).map(n => [n.pitch, n.dur])) === encS(REF.dataRight[g % 32])) sameR++;
  if (encS(out.filter(n => n.hand).map(n => [n.pitch, n.dur])) === encS(REF.dataLeft[g % 33])) sameL++; }
ok(sameR === 1056 && sameL === 1056, `맞춘 큐브를 엔진으로 한 곡(1056박): 오른손 ${sameR}/1056 · 왼손 ${sameL}/1056 이 원곡 자료와 같다`);
// ⑥ 차수
[['R', 'U', "R'", "U'"], ['R', 'U'], ['R2', 'U2'], ['U']].forEach(f => console.log('엔진 차수', f.join(' '), C.orderOf(f), '· 내 구현', REF.order(f.flatMap(m => m.endsWith('2') ? [m[0], m[0]] : [m]))));
