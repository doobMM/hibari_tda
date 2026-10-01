// verify_sketch_relay.mjs — 잇기(모듈 시계, sketch/relay-core.js + data/relay_clock.json) 가 판 12 규칙(CLAUDE.md)과 구멍 규칙을 지키는지.
//   node tools/verify_sketch_relay.mjs        (실패가 있으면 종료 코드 1)
// 문턱은 이 검증을 돌리기 전에 적었다(2026-10-01, 시계 판). 시계 판으로는 아직 탐색 시뮬레이션을 돌리지 않았다.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const HS = require('../sketch/common.js'), RL = require('../sketch/relay-core.js');
const D = JSON.parse(readFileSync(new URL('../sketch/data/relay_clock.json', import.meta.url), 'utf8'));
const B = RL.clockBoard(D), N = B.N, S = D.sectors, id = (s, r) => r * S + s, live = [...Array(N).keys()].filter(p => !B.gone[p]);
const SEEDS = [...Array(20)].map((_, i) => i + 1);
let bad = 0;
const line = (ok, n, m) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${n}  ${m}`); if (!ok) bad++; };
const med = a => [...a].sort((x, y) => x - y)[a.length >> 1], snap = E => JSON.stringify([E.state.path, E.state.by, E.state.rings]);
const loop = ps => ps.concat([ps[0]]);

// 정책: greedy = 금빛(울림) 칸이 보이면 그리로, 아니면 'go' 중 제비 · random = 'go' 중 제비 · cw = 늘 시계 방향(→ 만 누르는 사람)
function move(E, r, policy) { const o = E.options(), P = E.state.path; if (!o.length) return live[r() * live.length | 0];
  if (policy === 'cw') { const c = o.filter(q => B.dir(P[P.length - 1], q) === 'cw'); if (c.length) return c[0]; }
  const g = o.filter(q => E.preview(q) === 'ring'); if (policy === 'greedy' && g.length) return g[0];
  const go = o.filter(q => E.preview(q) === 'go'), c = go.length ? go : o; return c[r() * c.length | 0]; }
function warm(seed, k, policy = 'greedy') { const E = RL.create(B, { seed }), r = HS.rng(seed * 31 + 7), log = [];
  for (let t = 0; t < k; t++) { log.push(E.press(move(E, r, policy))); E.step(); } return { E, r, log }; }

// ── Q1 즉각: 어느 칸을 눌러도 소리가 나고 상태가 바뀐다 ──────────────────────
{ let silent = 0, same = 0, n = 0;
  for (const s of SEEDS.slice(0, 5)) for (const k of [0, 12]) for (const p of live) {
    const { E } = warm(s, k), b = snap(E), res = E.press(p); n++;
    if (!D.tiles[p].notes.length || (res.answer >= 0 && !D.tiles[res.answer].notes.length)) silent++;
    if (snap(E) === b) same++; }
  line(silent === 0 && same === 0, 'Q1 즉각', `누름 ${n}번(칸 ${live.length} × 시드 5 × 처음/12수 뒤): 소리 없는 누름(내 칸·대답) ${silent} · 상태가 안 바뀐 누름 ${same}`); }

// ── Q2 누른 판 / 안 누른 판: 두 마디(칸 4개) 뒤 달라진 것이 누른 그 하나뿐인가 ──────────
{ let trials = 0, extra = 0, ringDiff = 0, added = 0;
  for (const s of SEEDS) for (const k of [6, 20, 40]) {
    const A = warm(s, k), Bq = warm(s, k); trials++;
    const r = A.E.press(move(A.E, A.r, 'greedy')), nNew = r.events.filter(e => e.kind === 'ring').length;
    const ra = A.E.state.rings, rb = Bq.E.state.rings;
    if (ra.length - rb.length !== nNew || nNew > 2) ringDiff++;
    if (JSON.stringify(ra.slice(0, rb.length)) !== JSON.stringify(rb)) extra++;
    added += nNew;
    for (let t = 0; t < 4; t++) { const oa = A.E.step(), ob = Bq.E.step(); if (JSON.stringify(oa.slice(0, ob.length)) !== JSON.stringify(ob)) { extra++; break; } } }
  line(extra === 0 && ringDiff === 0, 'Q2 한 수 = 한 가지', `${trials}쌍(시드 20 × 6·20·40수 뒤): 누르지 않은 쪽과 비교해 줄 말고 달라진 것 — 기존 울림 고리 ${extra}쌍, 새 고리 수가 이벤트와 다른 쌍 ${ringDiff} · 새로 생긴 고리 평균 ${(added / trials).toFixed(2)}개`); }

// ── Q3 손을 떼면 그대로 ─────────────────────────────────────────────────
{ let moved = 0, aper = 0, withRings = 0;
  for (const s of SEEDS) { const { E } = warm(s, 30), b = snap(E), outs = []; if (E.state.rings.length) withRings++;
    for (let t = 0; t < 96; t++) outs.push(E.step());
    if (snap(E) !== b) moved++;
    E.state.rings.forEach((rg, k) => { const L = rg.places.length; for (let t = 0; t + L < 96; t++) if (outs[t][k].place !== outs[t + L][k].place) { aper++; break; } }); }
  line(moved === 0 && aper === 0 && withRings >= 15, 'Q3 손을 떼면 그대로', `시드 20(울림 고리가 있는 판 ${withRings}): 96칸 동안 줄·고리가 바뀐 판 ${moved} · 제 길이로 되풀이되지 않은 고리 ${aper}`); }

// ── Q4 되돌리기 ─────────────────────────────────────────────────────────
{ let off = 0, n = 0;
  for (const s of SEEDS) { const { E, r } = warm(s, 15); for (let i = 0; i < 10; i++) { const b = snap(E); E.press(move(E, r, 'random')); E.undo(); n++; if (snap(E) !== b) off++; } }
  line(off === 0, 'Q4 되돌리기', `${n}번: 되돌린 뒤 줄·고리가 누르기 전과 다른 경우 ${off}`); }

// ── Q5 구멍 = 판의 H1: 우는 고리는 보이는 구멍을 감은 것뿐 ──────────────────────
{ const ringLoop = r => [...Array(S)].map((_, s) => id(s, r));
  const full = [1, 3].map(r => B.wind(loop(ringLoop(r))));
  const wins = D.silent.filter(k => Math.floor(k / S) > 0 && Math.floor(k / S) < D.rings - 1);
  const around = wins.map(k => { const s = k % S, r = Math.floor(k / S), m = (a, b) => id((s + a + S) % S, r + b);
    return B.wind(loop([m(-1, -1), m(0, -1), m(1, -1), m(1, 0), m(1, 1), m(0, 1), m(-1, 1), m(-1, 0)])); });
  let blocks = 0, blockRing = 0;
  for (let r = 0; r + 1 < D.rings; r++) for (let s = 0; s < S; s++) { const q = [id(s, r), id((s + 1) % S, r), id((s + 1) % S, r + 1), id(s, r + 1)];
    if (q.some(p => B.gone[p])) continue; blocks++; if (B.wind(loop(q)).length) blockRing++; }
  const twice = B.wind(loop(ringLoop(1).concat(ringLoop(1))));                          // 두 바퀴 감아도 운다(감김수 2)
  const ok = JSON.stringify(full) === JSON.stringify([[0], [0, 1, 2]]) && around.every((h, i) => JSON.stringify(h) === JSON.stringify([i + 1])) && blockRing === 0 && B.holes.length === 1 + wins.length && twice.length === 1;
  line(ok, 'Q5 구멍 = H1', `구멍 ${B.holes.length}개(가운데 + 빈 칸 ${wins.length}) · 띠 1 한 바퀴 → ${JSON.stringify(full[0])}, 띠 3 → ${JSON.stringify(full[1])} · 빈 칸 둘레 → ${JSON.stringify(around)} · 2×2 막 ${blocks}개 중 우는 것 ${blockRing} · 두 바퀴 → ${JSON.stringify(twice)}`); }

// ── Q6 짧은 주고받기 · Q7 고르는 수가 결과를 바꾼다 ─────────────────────────────
{ const run = (s, pol) => { const E = RL.create(B, { seed: s }), r = HS.rng(s * 31 + 7); let first = -1, rings = 0, gold = 0;
    for (let t = 0; t < 60; t++) { if (E.options().some(q => E.preview(q) === 'ring')) gold++;
      const res = E.press(move(E, r, pol)); E.step(); const k = res.events.filter(e => e.kind === 'ring').length; rings += k; if (k && first < 0) first = t + 1; }
    return { first: first < 0 ? 99 : first, rings, gold }; };
  const C = SEEDS.map(s => run(s, 'cw')), G = SEEDS.map(s => run(s, 'greedy')), R = SEEDS.map(s => run(s, 'random'));
  line(med(C.map(x => x.first)) <= 6 && med(G.map(x => x.first)) <= 8, 'Q6 짧은 주고받기',
    `→ 만 누르면 첫 울림까지 누름 중앙 ${med(C.map(x => x.first))} (문턱 ≤ 6) · 금빛을 챙기면 ${med(G.map(x => x.first))} (범위 ${Math.min(...G.map(x => x.first))}~${Math.max(...G.map(x => x.first))}, 문턱 ≤ 8) · 아무렇게나 ${med(R.map(x => x.first))}`);
  const win = SEEDS.filter((s, i) => G[i].rings > R[i].rings).length;
  line(med(G.map(x => x.rings)) > med(R.map(x => x.rings)) && win >= 14, 'Q7 고르는 수가 결과를 바꾼다',
    `60번 누름의 울림 고리: 금빛을 챙김 중앙 ${med(G.map(x => x.rings))} · → 만 ${med(C.map(x => x.rings))} · 아무렇게나 ${med(R.map(x => x.rings))} · 같은 시드에서 챙긴 쪽이 아무렇게나보다 많은 시드 ${win}/20 (문턱 ≥ 14)`); }

// ── Q8 hibari 의 대답은 곡을 따른다 · 고리는 새 순서를 만든다 (대조군 = 곡의 흐름을 뺀 hibari) ────
{ const flat = { ...B, w: () => 1 };
  const share = BB => { let cw = 0, n = 0; for (const s of SEEDS) { const E = RL.create(BB, { seed: s }), r = HS.rng(s);
      for (let t = 0; t < 60; t++) { const P0 = E.state.path, res = E.press(move(E, r, 'random')); const ev = res.events.find(e => e.who === 'hibari'); if (!ev) continue;
        const P = E.state.path, from = ev.kind === 'go' ? P[P.length - 2] : null; if (from == null) continue; n++; if (B.dir(from, ev.place) === 'cw') cw++; void P0; } }
    return cw / Math.max(1, n); };
  const real = share(B), ctrl = share(flat);
  let rings = 0, mixed = 0; for (const s of SEEDS) { const { E } = warm(s, 60, 'greedy'); E.state.rings.forEach(rg => { rings++; if (new Set(rg.places.map(p => Math.floor(p / S))).size > 1) mixed++; }); }
  line(real > 0.6 && real - ctrl > 0.25, 'Q8 대답은 곡을 따른다',
    `hibari 가 곡이 흐르는 쪽(시계 방향)으로 대답한 몫 ${real.toFixed(3)} vs 곡의 흐름을 뺀 hibari ${ctrl.toFixed(3)} (문턱: 0.6 넘고 차 0.25 넘게) · 서술: 울림 고리 ${rings}개 중 띠를 넘나든(원곡에 없는 순서) 고리 ${mixed}개`); }

// ── Q9 같은 시드 = 같은 판, 다른 시드 = 다른 대답 ─────────────────────────────────
{ const sig = s => JSON.stringify(warm(s, 30, 'random').log.map(r => [r.mine, r.answer]));
  const same = SEEDS.filter(s => sig(s) === sig(s)).length;
  const E1 = RL.create(B, { seed: 1 }), E2 = RL.create(B, { seed: 2 }); let diff = 0;
  for (let t = 0; t < 30; t++) { const p = live[(t * 7) % live.length]; E1.state.path = [p]; E1.state.by = ['me']; E2.state.path = [p]; E2.state.by = ['me']; if (E1.press(p).answer !== E2.press(p).answer) diff++; }
  line(same === 20 && diff >= 3, 'Q9 우연', `같은 시드 두 번: ${same}/20 이 같은 판 · 같은 칸을 눌렀을 때 시드 1·2 의 대답이 다른 경우 ${diff}/30 (문턱 ≥ 3 — 대답이 곡을 따르니 대부분 같은 게 정상이다)`); }

console.log(bad ? `\n${bad}개 실패` : '\n전부 통과'); process.exit(bad ? 1 : 0);
