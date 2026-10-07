// tools/verify/xcheck_cube_ref.mjs — 검산용 독립 구현 — 에이전트 코드를 보지 않고 사양만으로 다시 짠 큐브.
// 면 좌표 · 칸표 · 움직임(기하) · 모듈 읽기. 에이전트 엔진과 박마다 대조한다.
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL('../..', import.meta.url)).replace(/[\/]$/, '');
const HS = require(ROOT + '/sketch/common.js');
const D = require(ROOT + '/lenia/tonnetz.json');
const H = HS.derive(D);

// 면 순서 = 자리 0..5 : F R B L U D
const FACES = [
  { name: 'F', n: [0, 0, 1], up: [0, 1, 0], right: [1, 0, 0] },
  { name: 'R', n: [1, 0, 0], up: [0, 1, 0], right: [0, 0, -1] },
  { name: 'B', n: [0, 0, -1], up: [0, 1, 0], right: [-1, 0, 0] },
  { name: 'L', n: [-1, 0, 0], up: [0, 1, 0], right: [0, 0, 1] },
  { name: 'U', n: [0, 1, 0], up: [0, 0, -1], right: [1, 0, 0] },
  { name: 'D', n: [0, -1, 0], up: [0, 0, 1], right: [1, 0, 0] },
];
const add = (a, b, s = 1) => a.map((v, i) => v + s * b[i]);
const key = (p, n) => p.map(v => Math.round(v * 2)).join(',') + '|' + n.map(v => Math.round(v)).join(',');
const SLOTS = []; const IDX = {};
FACES.forEach((f, fi) => { for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
  const p = add(add(f.n.map(v => v * 1.5), f.right, c - 1), f.up, 1 - r);
  const i = fi * 9 + r * 3 + c; SLOTS.push({ face: fi, r, c, p, n: f.n }); IDX[key(p, f.n)] = i; } });

function rot(v, axis, q) {             // q = +1 → +90° (반시계, 축 끝에서 볼 때), −1 → −90°
  const [x, y, z] = v, s = q, c = 0;    // sin = q, cos = 0
  if (axis === 0) return [x, y * c - z * s, y * s + z * c];
  if (axis === 1) return [x * c + z * s, y, -x * s + z * c];
  return [x * c - y * s, x * s + y * c, z];
}
// 바깥에서 볼 때 시계 방향 = 법선 축으로 −90°
function movePerm(fi, prime) {
  const f = FACES[fi], axis = f.n.findIndex(v => v !== 0), sign = f.n[axis];
  const q = (prime ? 1 : -1) * sign;   // 축이 −방향이면 같은 회전이 축 +방향에선 반대
  const perm = SLOTS.map((_, i) => i); // perm[src] = dest
  SLOTS.forEach((s, i) => {
    if (s.p[axis] * sign < 0.5) return;  // 그 층만 (면 위 1.5 · 옆면 1)
    const p2 = rot(s.p, axis, q), n2 = rot(s.n, axis, q), j = IDX[key(p2, n2)];
    if (j === undefined) throw new Error('rot miss ' + i);
    perm[i] = j;
  });
  return perm;
}
const MOVES = {};
FACES.forEach((f, fi) => { MOVES[f.name] = movePerm(fi, false); MOVES[f.name + "'"] = movePerm(fi, true); });
function apply(state, m) { const P = MOVES[m], out = state.slice(); for (let i = 0; i < 54; i++) out[P[i]] = state[i]; return out; }
const SOLVED = SLOTS.map((_, i) => i);
const same = (a, b) => a.every((v, i) => v === b[i]);
function order(seq) { let s = SOLVED, k = 0; do { seq.forEach(m => { s = apply(s, m); }); k++; } while (!same(s, SOLVED) && k < 5000); return k; }

// ── 칸표 (자료에서) ──
const R = H.mod[0].steps, LH = H.mod[1].steps, NT = H.notes;
const sorted = t => R[t].map(li => NT[li]).slice().sort((a, b) => a.pitch - b.pitch || a.dur - b.dur);
const ROLE = SLOTS.map(() => []);     // ROLE[slot] = [{step, dur}]
const HOME = new Array(54);          // HOME[slot] = 맞춘 상태의 음높이
function put(slot, note, step) { if (HOME[slot] === undefined) HOME[slot] = note.pitch; else if (HOME[slot] !== note.pitch) throw new Error('center mismatch ' + slot); ROLE[slot].push({ step, dur: note.dur }); }
for (let k = 0; k < 6; k++) {
  const b = k * 9, c1 = sorted(2 * k), c2 = sorted(16 + 2 * k), s1 = sorted(2 * k + 1), s2 = sorted(17 + 2 * k);
  if (k < 5) { put(b + 4, c1[0], 2 * k); put(b + 4, c2[0], 16 + 2 * k); [1, 2, 3].forEach((j, x) => put(b + x, c1[j], 2 * k)); [1, 2, 3].forEach((j, x) => put(b + 6 + x, c2[j], 16 + 2 * k)); }
  else { c1.forEach((n, x) => put(b + x, n, 2 * k)); put(b + 4, c2[0], 16 + 2 * k); [1, 2, 3].forEach((j, x) => put(b + 6 + x, c2[j], 16 + 2 * k)); }
  put(b + 3, s1[0], 2 * k + 1); put(b + 5, s2[0], 17 + 2 * k);
}
const events = ROLE.reduce((a, r) => a + r.length, 0);
// 상태 → 오른손 32스텝 [ [pitch,dur]... ]
function readRight(state) { const out = []; for (let t = 0; t < 32; t++) out.push([]);
  for (let j = 0; j < 54; j++) ROLE[j].forEach(r => out[r.step].push([HOME[state[j]], r.dur]));
  return out.map(a => a.sort((x, y) => x[0] - y[0] || x[1] - y[1])); }
function readLeft(state) { const r = readRight(state); return [[]].concat(r); }   // 33: 앞에 쉼 한 칸
const enc = m => m.map(a => a.map(x => x.join('/')).join(' ')).join(' | ');
const dataRight = R.map(a => a.map(li => [NT[li].pitch, NT[li].dur]).sort((x, y) => x[0] - y[0] || x[1] - y[1]));
const dataLeft = LH.map(a => a.map(li => [NT[li].pitch, NT[li].dur]).sort((x, y) => x[0] - y[0] || x[1] - y[1]));

export { FACES, SLOTS, MOVES, apply, SOLVED, order, ROLE, HOME, readRight, readLeft, enc, dataRight, dataLeft, events, same };

if (process.argv[1] && process.argv[1].endsWith('cube_ref.mjs')) {
  const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
  ok(HOME.every(v => v !== undefined) && events === 59, `칸 54 다 찼다 · 소리 사건 ${events} (= 54 + 5)`);
  const rr = readRight(SOLVED), ll = readLeft(SOLVED);
  ok(enc(rr) === enc(dataRight), `맞춘 큐브 = 오른손 ${rr.filter((s, t) => enc([s]) === enc([dataRight[t]])).length}/32`);
  ok(enc(ll) === enc(dataLeft), `맞춘 큐브 = 왼손 ${ll.filter((s, t) => enc([s]) === enc([dataLeft[t]])).length}/33`);
  Object.keys(MOVES).forEach(m => { const P = MOVES[m], moved = P.filter((d, i) => d !== i).length;
    let s = SOLVED; for (let k = 0; k < 4; k++) s = apply(s, m);
    ok(moved === 20 && same(s, SOLVED) && [4, 13, 22, 31, 40, 49].every(c => P[c] === c), `${m}: 옮김 ${moved} · ⁴=항등 · 가운데 고정`); });
  [['R', 'U', "R'", "U'"], ['R', 'U'], ['R', 'R', 'U', 'U'], ['U']].forEach(seq => console.log('차수', seq.join(' '), order(seq)));
  // 표준 방향: R 은 앞 오른쪽 열을 위로, U 는 앞 윗줄을 왼쪽으로
  const fr = [2, 5, 8], up = SLOTS.map((s, i) => i).filter(i => SLOTS[i].face === 4);
  ok(fr.every(i => SLOTS[MOVES.R[i]].face === 4), 'R: 앞 오른쪽 열 → 위(U)');
  ok([0, 1, 2].every(i => SLOTS[MOVES.U[i]].face === 3), 'U: 앞 윗줄 → 왼쪽(L)');
  Object.keys(MOVES).forEach(m => { const a = readRight(apply(SOLVED, m)), ch = [];
    a.forEach((s, t) => { if (enc([s]) !== enc([rr[t]])) ch.push(t); }); console.log('바뀌는 오른손 스텝', m.padEnd(2), ch.join(',')); });
}
