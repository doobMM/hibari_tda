// verify_sketch_wheels.mjs — 두 바퀴(시안 B, sketch/wheels-core.js) 가 명세 docs/sketch_spec.md §3 의 P1·P5·P6·P7·P8 을 넘는지.
//   node tools/verify_sketch_wheels.mjs          (시드 1~10. 실패가 있으면 종료 코드 1)
// 문턱은 수치를 보기 전에 적었다(2026-10-01). 엔진은 이 검증을 보며 세 번 고쳤다 — WEAR 0.34→0.42→0.55→0.6, 배고픔 닳기(32→16스텝), 쉼에는 심지 않기(P5b 0.798 을 본 뒤), 톱니 자리 수를 모듈 그대로 두기(P5b 0.649 를 본 뒤).
// → P5b·P6a 는 조정한 자료로 잰 것이다(확증 아님).
// 돌봄 정책(P5·P6b·P7): 8스텝마다 건반 하나 — 오른손·왼손 번갈아, 음이름은 제비.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const HS = require('../sketch/common.js'), WH = require('../sketch/wheels-core.js');
const D = JSON.parse(readFileSync(new URL('../lenia/tonnetz.json', import.meta.url), 'utf8')), H = HS.derive(D);
const SEEDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], KEYS = [...HS.ROWS[0], ...HS.ROWS[1], ...HS.ROWS[2]];
let bad = 0;
const line = (ok, n, m) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${n}  ${m}`); if (!ok) bad++; };
const mean = a => a.reduce((x, y) => x + y, 0) / Math.max(1, a.length), med = a => [...a].sort((x, y) => x - y)[a.length >> 1];
const corr = (a, b) => { const ma = mean(a), mb = mean(b); let n = 0, da = 0, db = 0; a.forEach((x, i) => { n += (x - ma) * (b[i] - mb); da += (x - ma) ** 2; db += (b[i] - mb) ** 2; }); return n / Math.sqrt(da * db || 1); };
const B = H.mod[0].steps.map(s => s.length >= 3 ? Math.min(...s.map(u => H.notes[u].pitch)) : null);

function run(HH, seed, steps, every, opt = {}, first = 'PadR2') {
  const E = WH.create(HH, { seed, ...opt }), r = HS.rng(seed * 7919 + 13), log = []; let dead = -1, k = 0; E.press(first);
  for (let t = 0; t < steps; t++) {
    if (every && t && t % every === 0) E.press((k++ % 2 ? 'PadL' : 'PadR') + (r() * 7 | 0));
    const o = E.step(); log.push(o); if (!E.state.alive && dead < 0) dead = t;
  }
  return { E, log, dead };
}
function music(log) {
  const fold = new Array(32).fill(0), c = new Array(32).fill(0), ring = H.mod[0].ring; let same = 0, nb = 0, cons = 0, np = 0, mine = 0, all = 0;
  for (const o of log) {
    const q = o.pos[0] % 32, R = o.notes.filter(n => n.hand === 0); fold[q] += R.length; c[q]++;
    if (B[q] != null && R.length >= 2) { nb++; if (Math.min(...R.map(n => n.pitch)) === B[q]) same++; }
    const ps = o.notes.map(n => n.pitch);
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) { np++; if ([0, 3, 4, 5, 7, 8, 9].includes(Math.abs(ps[i] - ps[j]) % 12)) cons++; }
    o.notes.forEach(n => { all++; if (n.mine) mine++; });
  }
  return { r: corr(fold.map((v, i) => v / Math.max(1, c[i])), ring), bass: same / Math.max(1, nb), cons: cons / Math.max(1, np), mineShare: mine / Math.max(1, all), perStep: mean(log.map(o => o.notes.length)) };
}

// ── P1 즉각 ────────────────────────────────────────────────────────
{ let silent = 0, same = 0, n = 0; const codes = [...KEYS, 'PadR0', 'PadL6', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space', 'KeyP', 'Digit3'];
  for (const s of SEEDS) for (const warm of [0, 40]) for (const code of codes) {
    const { E } = run(H, s, warm, 8), b = JSON.stringify([E.state.wheel, E.state.pos]), r = E.press(code); n++;
    if (!r.notes.length || r.notes.some(x => !(x.vel > 0))) silent++;
    if (JSON.stringify([E.state.wheel, E.state.pos]) === b && !(r.kind === 'teeth' && (r.n === 31 || r.n === 35))) same++; }
  line(silent === 0 && same === 0, 'P1', `누름 ${n}번(키 ${codes.length}가지 × 시드 10 × 처음/도는 중): 소리 없는 누름 ${silent}, 상태가 안 바뀐 누름 ${same} (톱니 수가 끝(31·35)에 닿은 경우만 그대로)`); }

// ── P5 진행감 ────────────────────────────────────────────────────────
{ const first = SEEDS.map(s => music(run(H, s, 32, 0).log)), care = SEEDS.map(s => music(run(H, s, 660, 8).log));
  line(Math.min(...first.map(m => m.bass)) === 1, 'P5a 처음은 원곡', `손대지 않은 첫 바퀴: 오른손 화음의 베이스가 모듈과 같은 비율 ${mean(first.map(m => m.bass)).toFixed(3)} (문턱 = 1)`);
  line(Math.min(...care.map(m => m.r)) >= 0.8, 'P5b 리듬 틀', `8스텝마다 돌본 660스텝: 32로 접은 음 수 ↔ 모듈 리듬 r 평균 ${mean(care.map(m => m.r)).toFixed(3)} (최소 ${Math.min(...care.map(m => m.r)).toFixed(3)}, 문턱 ≥ 0.8) — 톱니가 곧 모듈이라 틀이 남는다는 확인일 뿐이다`);
  console.log(`     돌본 5분 동안: 울린 음 중 내가 심은 음 ${(100 * mean(care.map(m => m.mineShare))).toFixed(1)}% · 오른손 화음 베이스가 모듈과 같은 비율 ${mean(care.map(m => m.bass)).toFixed(3)} · 스텝당 음 수 ${mean(care.map(m => m.perStep)).toFixed(2)} (원곡 두 손 3.63)`); }

// ── P6 살리기 ────────────────────────────────────────────────────────
{ const neg = SEEDS.map(s => run(H, s, 400, 0).dead), after = SEEDS.map(s => { const { E } = run(H, s, 80, 8); let t = 0; while (E.state.alive && t < 400) { E.step(); t++; } return t; });
  line(Math.max(...neg, ...after) <= 96, 'P6a 방치하면 멎는다', `첫 누름 뒤 손을 떼면 ${Math.min(...neg)}~${Math.max(...neg)}스텝(중앙 ${med(neg)}) · 80스텝 돌본 뒤 떼면 ${Math.min(...after)}~${Math.max(...after)}(중앙 ${med(after)}) (문턱 ≤ 96)`);
  const care = SEEDS.map(s => run(H, s, 660, 8)), ok = care.filter(r => r.dead < 0).length;
  line(ok === 10, 'P6b 단순한 돌봄', `8스텝마다 건반 하나로 660스텝: ${ok}/10 이 한 번도 멎지 않음 · 끝에 남은 심은 음 ${mean(care.map(r => r.E.probe().mine)).toFixed(1)}개 · 원곡 음 ${mean(care.map(r => r.E.probe().orig)).toFixed(1)}개`);
  console.log('     느슨한 돌봄으로 660스텝을 산 시드: ' + [16, 24, 32, 48].map(ev => `${ev}스텝마다 ${SEEDS.filter(s => run(H, s, 660, ev).dead < 0).length}/10`).join(' · '));
  const ALL = [...KEYS, 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'], ARR = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];
  const pol = { '같은 건반 4스텝마다': t => t % 4 === 0 ? 'PadR2' : null, '모든 키 제비 매 스텝': (t, r) => ALL[r() * ALL.length | 0],
                '밀기·톱니만 2스텝마다': (t, r) => t % 2 === 0 ? ARR[r() * 4 | 0] : null, 'Space 8스텝마다': t => t % 8 === 0 ? 'Space' : null };
  const res = Object.entries(pol).map(([name, f]) => { let early = 0;
    for (const s of SEEDS) { const nd = run(H, s, 400, 0).dead, E = WH.create(H, { seed: s }), r = HS.rng(s + 99); E.press('PadR2'); let dead = Infinity;
      for (let t = 0; t < 400; t++) { const c = t ? f(t, r) : null; if (c) E.press(c); E.step(); if (!E.state.alive) { dead = t; break; } }
      if (dead < nd) early++; }
    return `${name}: 방치보다 먼저 멎음 ${early}/10`; });
  line(res.every(x => x.endsWith(' 0/10')), 'P6c 돌봄이 벌받지 않는다', res.join(' · ')); }

// ── P7 고리 보호가 하중을 지나: 보호를 끄면 · 고리를 섞으면(HS.shuffled) 심은 음의 삶이 달라지나 ──────────
{ const life = (HH, opt) => SEEDS.map(s => { const { E, log } = run(HH, s, 660, 8, opt); return { grew: mean(log.map(o => o.grew)), mine: E.probe().mine, cons: music(log.slice(-240)).cons }; });
  const real = life(H, {}), off = life(H, { GUARD: false }), sh = [1, 2, 3, 4, 5].map(j => life(HS.derive(HS.shuffled(D, 700 + j)), {}));
  const f = (A, k) => mean(A.map(x => x[k])), fs = k => mean(sh.map(A => f(A, k)));
  line(f(real, 'mine') - f(off, 'mine') >= 1 && f(real, 'grew') > 0, 'P7', `660스텝 뒤 살아 있는 심은 음: 실제 ${f(real, 'mine').toFixed(1)}개 vs 고리 보호 끔 ${f(off, 'mine').toFixed(1)}개 (차 ≥ 1 이 문턱) · 고리 덕에 안 닳은 횟수 ${f(real, "grew").toFixed(3)}번/스텝`);
  console.log(`     (서술) 고리를 섞으면(HS.shuffled, 5벌): 살아 있는 심은 음 ${fs('mine').toFixed(1)}개 · 자람 ${fs('grew').toFixed(3)}번/스텝 · 마지막 2분 어울림 실제 ${f(real, 'cons').toFixed(3)} vs 섞음 ${fs('cons').toFixed(3)} vs 보호 끔 ${f(off, 'cons').toFixed(3)}`); }

// ── P8 우연 ─────────────────────────────────────────────────────────
{ const sig = s => run(H, s, 330, 8).log.map(o => o.notes.map(n => n.li + ':' + n.hand).join(',')), A = SEEDS.map(sig); let same = 0; const eq = [];
  SEEDS.forEach((s, i) => { if (JSON.stringify(sig(s)) === JSON.stringify(A[i])) same++; });
  for (let i = 0; i < 10; i++) for (let j = i + 1; j < 10; j++) eq.push(mean(A[i].map((x, t) => x && x === A[j][t] ? 1 : 0)) / Math.max(1e-9, mean(A[i].map(x => x ? 1 : 0))));
  line(same === 10 && Math.max(...eq) < 0.9, 'P8', `같은 시드 두 번: ${same}/10 이 음 하나까지 같음 · 다른 시드끼리 소리 나는 스텝이 똑같은 비율 평균 ${(100 * mean(eq)).toFixed(1)}% (최대 ${(100 * Math.max(...eq)).toFixed(1)}%, 문턱 < 90% — 원곡이 밑에 깔려 있어 비슷한 게 정상이다)`); }

console.log(bad ? `\n${bad}개 실패` : '\n전부 통과'); process.exit(bad ? 1 : 0);
