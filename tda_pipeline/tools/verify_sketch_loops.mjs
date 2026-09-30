// verify_sketch_loops.mjs — 고리 합주(시안 C) 엔진 검증. 명세 docs/sketch_spec.md §3 의 P1·P5·P6·P7·P8.
//   node tools/verify_sketch_loops.mjs        → PASS/FAIL 줄 + 측정값. 실패가 있으면 종료 코드 1. 시드 10개(1..10).
// 페이지(sketch/loops.html)와 같은 엔진(sketch/loops-core.js)·같은 Algorithm 1(generation-algo1.js)을 돌린다.
//
// 문턱은 수치를 보기 전에 적었다(아래 TH). 엔진 상수(LIFE 44 · GAIN 0.55 · HOLD 3 · 연쇄는 스텝에 하나 · 건반은 고리 둘까지)는
// 이 파일의 P6 수치와 연쇄 횟수를 보며 골랐다 — 같은 시드 1..10 이므로 P6 은 "조정한 자료로 잰 것"이다(스케치라 확증 회차는 없다 — 명세 §6).
//
// 단순한 돌봄 정책(P6·P5·P7·P8 이 같이 쓴다): **8스텝(3.6초)마다 한 번, 꺼져 있는 고리의 키 하나를 누른다.
//   왼쪽 키부터 차례로 돌며 켜져 있는 고리는 건너뛴다.** 첫 누름은 스텝 0 의 '1'. 건반·←/→ 는 쓰지 않는다.
// 방치: 누른 뒤 아무것도 하지 않는다. 네 가지로 잰다 — 고리 하나 / 다섯 / 건반으로 깨운 뒤 / 200스텝 돌본 뒤.
// 멎음 = 켜진 고리가 하나도 없다(그 뒤로는 손대지 않으면 영영 소리가 없다 — 기운을 넣는 것은 손뿐이다).
//
// P7 은 "비트가 다르다"가 아니라 **한 스텝에 같이 울린 음들의 어울림 비율**(음정이 1도·3도·4도·5도·6도인 쌍의 비율)로 잰다.
//   까닭: 실제 고리는 Tonnetz 이웃(3도·5도)과 같은 음이름(옥타브)으로 이어진 닫힌 길이라 고리의 겹침에서 뽑은 음들이 화음이 된다.
//   HS.shuffled 는 음 번호를 섞어 그 구조만 부순다(고리 크기·겹침 수·리듬·모듈은 그대로) → 차이가 나면 고리의 **내용**이 소리를 정한 것이다.
//   원곡 음높이 분포와의 JS 는 서술로만 덧붙인다(판정에 쓰지 않는다).
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = globalThis;
require(path.join(ROOT, 'hibari_dashboard/public/js/generation-algo1.js'));
const HS = require(path.join(ROOT, 'sketch/common.js'));
const L = require(path.join(ROOT, 'sketch/loops-core.js'));
const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'lenia/tonnetz.json'), 'utf8'));
const H = HS.derive(D), SEEDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const BASE = JSON.parse(process.env.OPTS || '{}');      // 엔진 상수를 바꿔 다시 재 볼 때: OPTS='{"OVER":1}' node tools/verify_sketch_loops.mjs (P1·P6a 의 방치는 기본값으로 잰다)
const TH = { foldR: 0.8, swing: 2, stairR: 0.5, bassMove: 0.5, neglectMax: 96, careSteps: 660, consDiff: 0.05, consSeeds: 9, mashAlive: 0.95 };

let fails = 0;
const say = (ok, id, msg) => { if (!ok) fails++; console.log((ok ? 'PASS ' : 'FAIL ') + id + '  ' + msg); };
const mean = a => a.reduce((x, y) => x + y, 0) / (a.length || 1);
const med = a => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
const f = (x, n = 3) => Number(x).toFixed(n);
const pearson = (a, b) => { const ma = mean(a), mb = mean(b); let n = 0, da = 0, db = 0;
  a.forEach((x, i) => { n += (x - ma) * (b[i] - mb); da += (x - ma) ** 2; db += (b[i] - mb) ** 2; }); return da && db ? n / Math.sqrt(da * db) : 0; };

function carer(every = 8) { let ptr = 0; const fn = (E, t) => { if (t % every) return;
  for (let j = 0; j < 15; j++) { const s = (ptr + j) % 15, k = E.state.slot[s]; if (k >= 0 && !(E.state.life[k] > 0)) { ptr = s + 1; fn.n++; return E.press(L.KEYS[s]); } } }; fn.n = 0; return fn; }
/** 정책을 걸고 steps 스텝을 돌린다. 스텝마다 {ph, notes, nOn, woke} */
function run(Hx, seed, steps, policy, opts) {
  const E = L.create(Hx, { seed, ...BASE, ...(opts || {}) }), rows = [];
  for (let t = 0; t < steps; t++) { if (policy) policy(E, t); const o = E.step(); rows.push({ ph: o.ph, notes: o.notes, nOn: E.probe().nOn, woke: o.woke.length }); }
  return rows;
}
/** 누른 뒤 손을 떼고, 멎을 때까지의 스텝 수 */
function untilDead(E, cap = 400) { let t = 0; while (E.probe().alive && t < cap) { E.step(); t++; } return t; }

// ── P1 즉각: 어떤 키든 press() 가 그 호출 안에서 음을 돌려주고 상태가 바뀐다 ───────────────────
{ const codes = [...L.KEYS, 'Pad0', 'Pad1', 'Pad2', 'Pad3', 'Pad4', 'Pad5', 'Pad6', 'KeyZ', 'KeyD', 'ArrowLeft', 'ArrowRight', 'Space', 'KeyK', 'Enter'];
  let n = 0, silent = 0, frozen = 0, cnt = [];
  const snap = E => JSON.stringify([E.state.life, E.state.slot, E.state.heat, E.state.reg]);
  for (const seed of SEEDS) for (const warm of [0, 1]) for (const c of codes) {
    const E = L.create(H, { seed }); if (warm) { E.press('Digit1'); E.press('Digit3'); for (let i = 0; i < 5; i++) E.step(); }
    const before = snap(E), r = E.press(c); n++;
    if (!r || !r.notes || !r.notes.length || r.notes.some(x => !(x.pitch >= 40 && x.vel > 0 && x.dur >= 1))) silent++; else cnt.push(r.notes.length);
    if (snap(E) === before && r.kind !== 'edge' && r.kind !== 'none') frozen++;
  }
  // 멎은 상태에서도, 방금 끈 고리도, rate 끝에서도 소리가 난다
  const E = L.create(H, { seed: 1 }); let extra = 0;
  // 마지막 하나 남은 고리는 다시 눌러도 꺼지지 않는다(돌봄이 벌받지 않게 — 검토 지적). 둘이 켜져 있을 때만 끌 수 있다.
  const a = E.press('Digit1'), a2 = E.press('Digit1'), a3 = E.press('Digit2'), b = E.press('Digit1');
  if (a.kind !== 'on' || a2.kind === 'off' || !a2.notes.length || a3.kind !== 'on' || b.kind !== 'off' || !b.notes.length) extra++;
  for (let i = 0; i < 20; i++) { const r = E.press('ArrowRight'); if (!r.notes.length) extra++; }
  say(silent === 0 && frozen === 0 && extra === 0, 'P1', `누름 ${n}번(키 ${codes.length}가지 × 시드 10 × 빈 상태/도는 중): 소리 없는 누름 ${silent}, 상태가 안 바뀐 누름 ${frozen}, 끄기·rate 끝 소리 없음 ${extra}. 누름당 음 수 평균 ${f(mean(cnt), 2)} (최소 ${Math.min(...cnt)})`);
}

// ── P5 진행감: 돌봄 정책으로 320스텝 ────────────────────────────────────────────
function progress(Hx, seed, opts) {
  const rows = run(Hx, seed, 320, carer(), opts), ring = Hx.mod[0].ring, fold = new Array(32).fill(0), vis = new Array(32).fill(0), gb = [], mb = []; let moved = 0, pairs = 0, prevSet = null;
  rows.forEach(r => { if (r.ph < 0) return; const p = r.ph % 32; fold[p] += r.notes.length; vis[p]++;
    if (ring[p] >= 3) { const h0 = r.notes.filter(x => x.hand === 0).map(x => x.pitch).sort((x, y) => x - y); if (!h0.length) return;
      gb.push(h0[0]); mb.push(Math.min(...Hx.mod[0].steps[p].map(li => Hx.notes[li].pitch)));
      const key = h0.join(); if (prevSet != null) { pairs++; if (key !== prevSet) moved++; } prevSet = key; } });
  const per = fold.map((x, i) => vis[i] ? x / vis[i] : 0);
  const at = v => mean(per.filter((_, i) => v(ring[i])));
  return { r: pearson(per, ring), chord: at(x => x >= 3), single: at(x => x === 1), rest: at(x => x === 0), stair: pearson(gb, mb), moved: moved / pairs, per };
}
{ const R = SEEDS.map(s => progress(H, s)), C = SEEDS.map(s => progress(H, s, { STAIR: false }));
  const r = mean(R.map(x => x.r)), sw = mean(R.map(x => x.chord / x.single)), st = mean(R.map(x => x.stair)), mv = mean(R.map(x => x.moved));
  console.log('     접은 스텝별 음 수(시드 1): ' + R[0].per.map(x => Math.round(x)).join('') + '   ← 모듈 ' + H.mod[0].ring.join(''));
  say(Math.min(...R.map(x => x.r)) >= TH.foldR, 'P5a', `32로 접은 스텝별 음 수 ↔ 모듈 리듬 상관 r 평균 ${f(r)} (최소 ${f(Math.min(...R.map(x => x.r)))}, 문턱 ≥ ${TH.foldR})`);
  say(sw >= TH.swing, 'P5b', `4·1 흔들림: 화음 스텝 ${f(mean(R.map(x => x.chord)), 2)}음 / 단음 스텝 ${f(mean(R.map(x => x.single)), 2)}음 = ${f(sw, 2)}배 (문턱 ≥ ${TH.swing}). 쉼 스텝 ${f(mean(R.map(x => x.rest)), 2)}음(왼손이 어긋나 들어온 것)`);
  say(Math.min(...R.map(x => x.stair)) >= TH.stairR, 'P5c', `계단: 뽑힌 베이스 ↔ 모듈 베이스 상관 r 평균 ${f(st)} (최소 ${f(Math.min(...R.map(x => x.stair)))}, 문턱 ≥ ${TH.stairR}). 계단 규칙을 뺀 대조군 r ${f(mean(C.map(x => x.stair)))}`);
  say(mv >= TH.bassMove, 'P5d', `졸림 아님: 이어지는 두 화음이 서로 다른 비율 ${f(mv)} (문턱 ≥ ${TH.bassMove})`);
}

// ── P6 살리기 ─────────────────────────────────────────────────────────────
const neglect1 = {};
{ const N = { one: [], five: [], pad: [], after: [] };
  for (const s of SEEDS) {
    let E = L.create(H, { seed: s }); E.press(L.KEYS[(s * 3) % 14]); N.one.push(neglect1[s] = untilDead(E));
    E = L.create(H, { seed: s }); [0, 3, 6, 9, 11].forEach(j => E.press(L.KEYS[(j + s) % 14])); N.five.push(untilDead(E));
    E = L.create(H, { seed: s }); for (let d = 0; d < 7 && !E.probe().alive; d++) E.press('Pad' + (s + d * 2) % 7); N.pad.push(E.probe().alive ? untilDead(E) : -1);
    E = L.create(H, { seed: s }); const pol = carer(); for (let t = 0; t < 200; t++) { if (t <= 192) pol(E, t); E.step(); } N.after.push(untilDead(E) + 8);   // 마지막 누름(스텝 192)부터 — 192~199 의 여덟 스텝을 더한다
  }
  const all = [...N.one, ...N.five, ...N.pad, ...N.after], line = k => `${Math.min(...N[k])}~${Math.max(...N[k])}(중앙 ${med(N[k])})`;
  say(Math.max(...all) <= TH.neglectMax && Math.min(...all) > 0, 'P6a', `방치하면 멎는다 (마지막 누름부터 스텝 수, 문턱 ≤ ${TH.neglectMax}): 고리 하나 ${line('one')} · 다섯 ${line('five')} · 건반으로 ${line('pad')} · 돌본 뒤 ${line('after')}. 전체 ${f(Math.min(...all) * HS.SEC, 0)}~${f(Math.max(...all) * HS.SEC, 0)}초`);

  const care = SEEDS.map(s => { const pol = carer(), rows = run(H, s, TH.careSteps, pol); const dead = rows.findIndex(r => r.nOn === 0);
    return { presses: pol.n, dead: dead < 0 ? Infinity : dead, minOn: Math.min(...rows.map(r => r.nOn)), meanOn: mean(rows.map(r => r.nOn)), woke: rows.reduce((a, r) => a + r.woke, 0), notes: rows.reduce((a, r) => a + r.notes.length, 0) }; });
  const alive = care.filter(c => c.dead === Infinity).length;
  say(alive === SEEDS.length, 'P6b', `단순한 돌봄(8스텝마다 꺼진 고리 하나)으로 ${TH.careSteps}스텝: ${alive}/10 시드가 한 번도 멎지 않음. 켜진 고리 평균 ${f(mean(care.map(c => c.meanOn)), 2)}개(최소 ${Math.min(...care.map(c => c.minOn))}), 누름 평균 ${f(mean(care.map(c => c.presses)), 1)}번에 저절로 켜진 고리 평균 ${f(mean(care.map(c => c.woke)), 1)}번, 음 ${f(mean(care.map(c => c.notes)), 0)}개`);
  const worse = SEEDS.filter((s, i) => care[i].dead <= neglect1[s]).length;
  say(worse === 0, 'P6c', `돌봄이 방치보다 먼저 멎은 시드 ${worse}/10`);
  // 느슨한 돌봄 — 어디서 끊기나 (판정 없음)
  const lazy = [16, 32, 40, 48, 64].map(per => { let ok = 0; const on = []; for (const s of SEEDS) { const rows = run(H, s, 660, carer(per)); if (rows.every(r => r.nOn > 0)) ok++; on.push(mean(rows.map(r => r.nOn))); }
    return `${per}스텝마다 ${ok}/10(켜진 고리 ${f(mean(on), 1)})`; });
  console.log('     느슨한 돌봄으로 660스텝을 산 시드: ' + lazy.join(' · '));
  // 마구 누르기 — 많이 만져서 죽는 길이 있나
  const mash = (codes, every) => SEEDS.map(s => { const r = HS.rng(900 + s), rows = run(H, s, 660, (E, t) => { if (t % every === 0) E.press(codes[Math.floor(r() * codes.length)]); });
    return { alive: mean(rows.map(x => x.nOn > 0 ? 1 : 0)), first: rows.findIndex(x => x.nOn === 0), end: rows[rows.length - 1].nOn }; });
  const m1 = mash(L.KEYS.slice(0, 14), 1), m2 = mash([...L.KEYS, 'Pad0', 'Pad1', 'Pad2', 'Pad3', 'Pad4', 'Pad5', 'Pad6', 'ArrowLeft', 'ArrowRight', 'Space'], 1), m3 = mash(['Space'], 2), m4 = mash(['Digit1'], 4);
  const ml = m => `소리 나는 스텝 ${f(100 * mean(m.map(x => x.alive)), 1)}%(최소 ${f(100 * Math.min(...m.map(x => x.alive)), 1)}%)`;
  say(Math.min(...m1.map(x => x.alive), ...m2.map(x => x.alive), ...m3.map(x => x.alive)) >= TH.mashAlive, 'P6d', `마구 눌러도 죽지 않는다 (문턱 ≥ ${100 * TH.mashAlive}%): 고리 키를 매 스텝 제비로 ${ml(m1)} · 모든 키를 매 스텝 제비로 ${ml(m2)} · Space 만 2스텝마다 ${ml(m3)}`);
  console.log(`     (참고) 같은 고리 키 하나만 4스텝마다 = 켰다 껐다: ${ml(m4)} — 끄는 것은 내가 멈춘 것이다. 방치(고리 하나) ${Math.min(...N.one)}~${Math.max(...N.one)}스텝`);
}

// ── P7 연구 자료가 하중을 진다: 어울림 비율 (실제 고리 vs 음 번호를 섞은 고리) ─────────────────
const CONS = new Set([0, 3, 4, 5, 7, 8, 9]);
function consonance(rows) { let a = 0, b = 0; rows.forEach(r => { const ps = [...new Set(r.notes.map(x => x.pitch))];
  for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) { b++; if (CONS.has(Math.abs(ps[i] - ps[j]) % 12)) a++; } }); return b ? a / b : 0; }
function jsToOrig(rows) { const c = {}; let n = 0; rows.forEach(r => r.notes.forEach(x => { c[x.pitch] = (c[x.pitch] || 0) + 1; n++; }));
  const O = D.orig_pitch_counts, on = Object.values(O).reduce((x, y) => x + y, 0); let js = 0;
  Object.keys(O).forEach(p => { const P = O[p] / on, Q = (c[p] || 0) / n, M = (P + Q) / 2; if (P) js += 0.5 * P * Math.log2(P / M); if (Q) js += 0.5 * Q * Math.log2(Q / M); }); return js; }
{ const real = [], shuf = [], jr = [], js = [], wr = [], ws = [], stat = [];
  const loopCons = Hx => mean(Hx.cycles.map(c => { const ps = [...new Set(c.map(li => Hx.notes[li].pitch))]; let a = 0, b = 0;
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) { b++; if (CONS.has(Math.abs(ps[i] - ps[j]) % 12)) a++; } return b ? a / b : 1; }));
  for (const s of SEEDS) { const Hs = HS.derive(HS.shuffled(D, 777 + s)), A = run(H, s, 320, carer()), B = run(Hs, s, 320, carer());
    real.push(consonance(A)); shuf.push(consonance(B)); jr.push(jsToOrig(A)); js.push(jsToOrig(B)); stat.push(loopCons(Hs));
    wr.push(A.reduce((a, r) => a + r.woke, 0)); ws.push(B.reduce((a, r) => a + r.woke, 0)); }
  const wins = SEEDS.filter((_, i) => real[i] > shuf[i]).length, diff = mean(real) - mean(shuf);
  say(wins >= TH.consSeeds && diff >= TH.consDiff, 'P7', `같이 울린 음의 어울림 비율: 실제 ${f(mean(real))} vs 섞음 ${f(mean(shuf))} (차 ${f(diff)}, 문턱 ≥ ${TH.consDiff}; 실제가 높은 시드 ${wins}/10, 문턱 ≥ ${TH.consSeeds}). 범위 실제 ${f(Math.min(...real))}~${f(Math.max(...real))} · 섞음 ${f(Math.min(...shuf))}~${f(Math.max(...shuf))}`);
  // 고리 하나만 켰을 때(연쇄 끔, 44스텝) — 자료가 가장 무겁게 실리는 상태. 켜진 고리가 많아질수록 겹침이 거의 모든 음을 덮어 차이가 옅어진다
  const solo = Hx => mean(SEEDS.map(s => { const E = L.create(Hx, { seed: s, CHAIN: false }), rows = []; E.press(L.KEYS[s % 13]);
    for (let t = 0; t < 44; t++) rows.push({ notes: E.step().notes }); return consonance(rows); }));
  console.log(`     (고리 하나만) 어울림 비율: 실제 ${f(solo(H))} vs 섞음 ${f(mean(SEEDS.map(s => solo(HS.derive(HS.shuffled(D, 777 + s))))))}`);
  console.log(`     (자료 자체) 고리 안 음들의 어울림: 실제 ${f(loopCons(H))} vs 섞음 ${f(mean(stat))}`);
  console.log(`     (서술) 원곡 음높이 분포와의 JS: 실제 ${f(mean(jr), 4)} vs 섞음 ${f(mean(js), 4)} · 저절로 켜진 고리 수: 실제 ${f(mean(wr), 1)} vs 섞음 ${f(mean(ws), 1)}`);
}

// ── P8 우연: 같은 시드 = 같은 음악, 다른 시드 = 다른 음악 ─────────────────────────────
{ const sig = rows => rows.map(r => r.notes.map(x => x.pitch + ':' + x.dur).join(',')).join('|');
  const runs = SEEDS.map(s => run(H, s, 320, carer())), again = SEEDS.map(s => run(H, s, 320, carer()));
  const same = SEEDS.filter((_, i) => sig(runs[i]) === sig(again[i])).length;
  let diffPairs = 0, pairs = 0, agree = [];
  for (let i = 0; i < runs.length; i++) for (let j = i + 1; j < runs.length; j++) { pairs++; if (sig(runs[i]) !== sig(runs[j])) diffPairs++;
    let eq = 0, tot = 0; runs[i].forEach((r, t) => { if (!r.notes.length && !runs[j][t].notes.length) return; tot++;
      if (r.notes.map(x => x.pitch).sort().join() === runs[j][t].notes.map(x => x.pitch).sort().join()) eq++; }); agree.push(eq / tot); }
  say(same === SEEDS.length && diffPairs === pairs, 'P8', `같은 시드를 두 번: ${same}/10 이 음 하나까지 같음 · 다른 시드 쌍 ${diffPairs}/${pairs} 가 다름 (같은 누름에서 스텝의 음이 똑같은 비율 평균 ${f(100 * mean(agree), 1)}%, 범위 ${f(100 * Math.min(...agree), 1)}~${f(100 * Math.max(...agree), 1)}%)`);
}

console.log(fails ? `\n${fails}개 실패` : '\n전부 통과');
process.exit(fails ? 1 : 0);
