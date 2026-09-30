// verify_sketch_flow.mjs — 흐름 그물(시안 A, sketch/flow-core.js) 이 명세 docs/sketch_spec.md §3 의 P1·P5·P6·P7·P8 을 넘는지.
//   node tools/verify_sketch_flow.mjs          (시드 1~10. 실패가 있으면 종료 코드 1)
//
// 문턱은 수치를 보기 **전에** 적었다(2026-09-30). 엔진 상수(EVAP·MOVE·FITS·TAU …)는 이 검증의 수치를 보며 골랐다 → P6 은 조정한 자료로 잰 것이다(확증 아님).
// 돌봄 정책(P5·P6b·P7 공통): 8스텝마다 건반 하나 — 금빛·산호빛을 번갈아, 음이름은 제비.
// 판정기를 믿기 전에 **그 성질이 없어야 할 팔**에도 돌린다(loops 검토의 교훈): 물길을 전부 같게(NET 끔) · 모듈 음높이 끌림 끔(FIT 끔) · 자료 섞기(HS.shuffled).
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const HS = require('../sketch/common.js'), FL = require('../sketch/flow-core.js');
const D = JSON.parse(readFileSync(new URL('../lenia/tonnetz.json', import.meta.url), 'utf8')), H = HS.derive(D);
const SEEDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], KEYS = [...HS.ROWS[0], ...HS.ROWS[1], ...HS.ROWS[2]];
let bad = 0;
const line = (ok, name, msg) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${name}  ${msg}`); if (!ok) bad++; };
const mean = a => a.reduce((x, y) => x + y, 0) / Math.max(1, a.length), med = a => [...a].sort((x, y) => x - y)[a.length >> 1];
const corr = (a, b) => { const ma = mean(a), mb = mean(b); let n = 0, da = 0, db = 0; a.forEach((x, i) => { n += (x - ma) * (b[i] - mb); da += (x - ma) ** 2; db += (b[i] - mb) ** 2; }); return n / Math.sqrt(da * db || 1); };
const bassOf = h => H.mod[h].steps.map(s => s.length >= 3 ? Math.min(...s.map(u => H.notes[u].pitch)) : null);

/** 돌봄: every 스텝마다 건반 하나. 돌려주는 것 = 스텝별 기록 */
function run(HH, seed, steps, every, opt = {}) {
  const E = FL.create(HH, { seed, ...opt }), r = HS.rng(seed * 7919 + 13), log = []; let dead = -1, k = 0;
  for (let t = 0; t < steps; t++) {
    if (every && t % every === 0) E.press((k++ % 2 ? 'PadC' : 'PadG') + (r() * 7 | 0));
    const o = E.step(); log.push(o); if (t > 0 && !E.state.alive && dead < 0) dead = t;
  }
  return { E, log, dead };
}
/** 음악 통계: 리듬(32로 접은 음 수), 오른손 화음의 베이스가 모듈과 같은 비율, 구절 안에서 베이스가 오른 비율, 같이 울린 음의 어울림 */
function music(log) {
  const fold = new Array(32).fill(0), cnt = new Array(32).fill(0), B = bassOf(0); let same = 0, nb = 0, up = 0, nup = 0, prev = null, cons = 0, npair = 0, chordN = 0, chordS = 0, oneN = 0, oneS = 0, restN = 0, restS = 0;
  const ring = H.mod[0].ring;
  for (const o of log) {
    const p = o.ph[0]; if (p < 0) continue; const q = p % 32, mine = o.notes.filter(n => n.hand === 0);   // 오른손 모듈이 낸 음
    fold[q] += o.notes.length; cnt[q]++;
    if (ring[q] >= 3) { chordN += mine.length; chordS++; } else if (ring[q] === 1) { oneN += mine.length; oneS++; } else { restN += o.notes.length; restS++; }
    if (q % 16 === 0) prev = null;
    if (B[q] != null && mine.length >= 2) { const b = Math.min(...mine.map(n => n.pitch)); nb++; if (b === B[q]) same++;
      if (prev != null) { nup++; if (b > prev) up++; } prev = b; }
    const ps = o.notes.map(n => n.pitch);
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) { const d = Math.abs(ps[i] - ps[j]) % 12; npair++; if ([0, 3, 4, 5, 7, 8, 9].includes(d)) cons++; }
  }
  return { r: corr(fold.map((v, i) => v / Math.max(1, cnt[i])), ring), bassSame: same / Math.max(1, nb), bassUp: up / Math.max(1, nup), cons: cons / Math.max(1, npair),
           chord: chordN / Math.max(1, chordS), one: oneN / Math.max(1, oneS), rest: restN / Math.max(1, restS), perStep: mean(log.map(o => o.notes.length)) };
}

// ── P1 즉각: 모든 키가 그 호출 안에서 음을 돌려주고 상태를 바꾼다 ─────────────────────────
{ let silent = 0, same = 0, n = 0; const codes = [...KEYS, 'PadG0', 'PadG6', 'PadC3', 'Note5', 'ArrowLeft', 'ArrowRight', 'Space', 'Enter', 'KeyP', 'Digit5'];
  for (const seed of SEEDS) for (const warm of [0, 40]) for (const code of codes) {
    const { E } = run(H, seed, warm, 8), b = JSON.stringify([E.state.w, E.state.rate]), r = E.press(code); n++;
    if (!r.notes.length || r.notes.some(x => !(x.vel > 0))) silent++;
    if (JSON.stringify([E.state.w, E.state.rate]) === b && !(r.kind === 'gate' && !r.moved)) same++; }   // 수문이 끝에 닿았을 때만 상태가 그대로다(소리는 난다)
  line(silent === 0 && same === 0, 'P1', `누름 ${n}번(키 ${codes.length}가지 × 시드 10 × 빈 상태/도는 중): 소리 없는 누름 ${silent}, 상태가 안 바뀐 누름 ${same}`); }

// ── P5 진행감 ────────────────────────────────────────────────────────
const arms = { '실제': [H, {}], '물길 같게(NET 끔)': [H, { NET: false }], '끌림 끔(FIT 끔)': [H, { FIT: false }], '방향 섞음': [H, { MIX: 901 }], '방향 섞음 + 끌림 끔': [H, { MIX: 901, FIT: false }] }, M = {};
for (const [name, [HH, opt]] of Object.entries(arms)) M[name] = SEEDS.map(s => music(run(HH, s, 660, 8, opt).log));
const real = M['실제'], avg = (arr, f) => mean(arr.map(m => m[f]));
console.log(`     스텝당 음 수 ${avg(real, 'perStep').toFixed(2)} (원곡 오른손 1.85 · 두 손 3.63) · 쉼 자리 ${avg(real, 'rest').toFixed(2)}음`);
line(Math.min(...real.map(m => m.r)) >= 0.8, 'P5a 리듬 틀', `32로 접은 스텝별 음 수 ↔ 모듈 리듬 상관 r 평균 ${avg(real, 'r').toFixed(3)} (최소 ${Math.min(...real.map(m => m.r)).toFixed(3)}, 문턱 ≥ 0.8) — 틀이 적용됐다는 확인일 뿐이다(어느 팔에서도 선다: NET 끔 ${avg(M['물길 같게(NET 끔)'], 'r').toFixed(3)})`);
line(avg(real, 'chord') / avg(real, 'one') >= 2, 'P5b 4·1 흔들림', `화음 스텝 ${avg(real, 'chord').toFixed(2)}음 / 단음 스텝 ${avg(real, 'one').toFixed(2)}음 = ${(avg(real, 'chord') / avg(real, 'one')).toFixed(2)}배 (문턱 ≥ 2)`);
line(avg(real, 'bassSame') >= 0.6 && avg(real, 'bassUp') >= 0.6, 'P5c 계단', `오른손 화음의 베이스가 모듈과 같은 비율 ${avg(real, 'bassSame').toFixed(3)} (문턱 ≥ 0.6) · 구절 안에서 오른 비율 ${avg(real, 'bassUp').toFixed(3)} (문턱 ≥ 0.6, 원곡 0.90)`);
console.log('     (대조) ' + Object.keys(arms).slice(1).map(k => `${k}: 같은 음 ${avg(M[k], 'bassSame').toFixed(3)} · 오름 ${avg(M[k], 'bassUp').toFixed(3)}`).join('   '));

// ── P6 살리기 ────────────────────────────────────────────────────────
const firstDead = (seed, presses, steps = 300, opt = {}) => { const E = FL.create(H, { seed, ...opt }); let lastPress = 0;
  for (let t = 0; t < steps; t++) { for (const [at, code] of presses) if (at === t) { E.press(code); lastPress = t; } E.step(); if (!E.state.alive && t >= lastPress) return t - lastPress; } return Infinity; };
{ const one = SEEDS.map(s => firstDead(s, [[0, 'PadG' + (s % 7)]])), five = SEEDS.map(s => firstDead(s, [0, 1, 2, 3, 4].map(i => [i, (i % 2 ? 'PadC' : 'PadG') + ((s + i * 2) % 7)])));
  const after = SEEDS.map(s => { const { E } = run(H, s, 80, 8); let t = 0; while (E.state.alive && t < 400) { E.step(); t++; } return t; });
  const all = [...one, ...five, ...after], sec = x => (x * HS.SEC).toFixed(0);
  line(Math.max(...all) <= 96, 'P6a 방치하면 멎는다', `마지막 누름부터 (문턱 ≤ 96스텝): 한 번 붓고 ${Math.min(...one)}~${Math.max(...one)}(중앙 ${med(one)}) · 다섯 번 붓고 ${Math.min(...five)}~${Math.max(...five)}(중앙 ${med(five)}) · 돌본 뒤 ${Math.min(...after)}~${Math.max(...after)}(중앙 ${med(after)}). 전체 ${sec(Math.min(...all))}~${sec(Math.max(...all))}초`); }
{ const res = SEEDS.map(s => run(H, s, 660, 8)), ok = res.filter(r => r.dead < 0).length;
  line(ok === 10, 'P6b 단순한 돌봄', `8스텝마다 건반 하나로 660스텝: ${ok}/10 시드가 한 번도 멎지 않음. 켜진 고리 평균 ${mean(res.map(r => mean(r.log.map(o => o.lit.length)))).toFixed(3)}번/스텝 새로 켜짐, 끝의 물 ${mean(res.map(r => r.E.probe().water[0] + r.E.probe().water[1])).toFixed(2)}`);
  const sparse = [16, 24, 32, 48].map(ev => `${ev}스텝마다 ${SEEDS.filter(s => run(H, s, 660, ev).dead < 0).length}/10`).join(' · ');
  console.log(`     느슨한 돌봄으로 660스텝을 산 시드: ${sparse}`); }
{ // 돌봄이 방치보다 먼저 멎는 시드가 있나 — 방치와 같은 첫 누름으로 짝지은 여러 정책
  const pol = { '같은 건반 4스텝마다': t => t % 4 === 0 ? 'PadG2' : null, '같은 건반 24스텝마다': t => t % 24 === 0 ? 'PadG2' : null, '모든 키 제비 매 스텝': (t, r) => KEYS[r() * KEYS.length | 0],
                '수문만 4스텝마다': (t, r) => t && t % 4 === 0 ? (r() < 0.5 ? 'ArrowLeft' : 'ArrowRight') : null, '그 밖의 키(Space) 8스텝마다': t => t && t % 8 === 0 ? 'Space' : null };
  const out = [];
  for (const [name, f] of Object.entries(pol)) { let early = 0, deadRuns = 0;
    for (const s of SEEDS) { const neglect = firstDead(s, [[0, 'PadG2']]), E = FL.create(H, { seed: s }), r = HS.rng(s + 99); E.press('PadG2'); let dead = Infinity;
      for (let t = 0; t < 660; t++) { const c = t ? f(t, r) : null; if (c) E.press(c); E.step(); if (!E.state.alive) { dead = t; break; } }
      if (dead < neglect) early++; if (dead < Infinity) deadRuns++; }
    out.push([name, early, deadRuns]); }
  line(out.every(o => o[1] === 0), 'P6c 돌봄이 벌받지 않는다', out.map(o => `${o[0]}: 방치보다 먼저 멎음 ${o[1]}/10 (660스텝 안에 멎음 ${o[2]}/10)`).join(' · ')); }

// ── P7 자료가 하중을 진다: ① 방향 물길(모듈에서 v 다음에 u)의 도착 음을 섞으면 계단이 무너지나 ② 정본 가중치·고리를 섞으면(HS.shuffled) 무엇이 달라지나 ──
{ const mixed = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(j => SEEDS.map(s => music(run(H, s, 660, 8, { MIX: 900 + j }).log)));
  const f = k => mixed.map(a => avg(a, k)), d = avg(real, 'bassSame') - mean(f('bassSame')), wins = f('bassSame').filter(v => v < avg(real, 'bassSame')).length;
  line(d >= 0.15 && wins >= 9, 'P7', `베이스가 모듈과 같은 비율: 실제 ${avg(real, 'bassSame').toFixed(3)} vs 방향 섞음 ${mean(f('bassSame')).toFixed(3)} [${Math.min(...f('bassSame')).toFixed(3)}~${Math.max(...f('bassSame')).toFixed(3)}] (섞는 시드 10벌, 차 ${d.toFixed(3)}, 문턱 ≥ 0.15 · 실제가 높은 벌 ${wins}/10)`);
  console.log(`     (서술) 오름 비율: 실제 ${avg(real, 'bassUp').toFixed(3)} vs 방향 섞음 ${mean(f('bassUp')).toFixed(3)} · 어울림: 실제 ${avg(real, 'cons').toFixed(3)} vs ${mean(f('cons')).toFixed(3)}`);
  const sh = [1, 2, 3, 4, 5].map(j => { const HH = HS.derive(HS.shuffled(D, 700 + j)); return SEEDS.map(s => { const r = run(HH, s, 660, 8); return { ...music(r.log), lit: mean(r.log.map(o => o.lit.length)) }; }); });
  const litReal = mean(SEEDS.map(s => mean(run(H, s, 660, 8).log.map(o => o.lit.length))));
  console.log(`     (서술) 정본 가중치·고리를 섞으면(HS.shuffled, 5벌): 베이스 같은 음 ${mean(sh.map(a => avg(a, 'bassSame'))).toFixed(3)} · 어울림 ${mean(sh.map(a => avg(a, 'cons'))).toFixed(3)} · 고리가 새로 켜진 횟수/스텝 실제 ${litReal.toFixed(3)} vs 섞음 ${mean(sh.map(a => avg(a, 'lit'))).toFixed(3)} — 정본 가중치는 스밈(SEEP)과 수문에만 들어가므로 소리는 거의 같다(하중은 방향 물길과 모듈이 진다)`); }

// ── P8 우연 ─────────────────────────────────────────────────────────
{ const sig = s => run(H, s, 330, 8).log.map(o => o.notes.map(n => n.li + ':' + n.hand).join(',')), A = SEEDS.map(sig); let sameRun = 0, eq = [];
  SEEDS.forEach((s, i) => { if (JSON.stringify(sig(s)) === JSON.stringify(A[i])) sameRun++; });
  for (let i = 0; i < 10; i++) for (let j = i + 1; j < 10; j++) eq.push(mean(A[i].map((x, t) => x && x === A[j][t] ? 1 : 0)) / Math.max(1e-9, mean(A[i].map(x => x ? 1 : 0))));
  line(sameRun === 10 && Math.max(...eq) < 0.5, 'P8', `같은 시드를 두 번: ${sameRun}/10 이 음 하나까지 같음 · 다른 시드끼리 소리 나는 스텝의 음이 똑같은 비율 평균 ${(100 * mean(eq)).toFixed(1)}% (최대 ${(100 * Math.max(...eq)).toFixed(1)}%, 문턱 < 50%)`); }

console.log(bad ? `\n${bad}개 실패` : '\n전부 통과'); process.exit(bad ? 1 : 0);
