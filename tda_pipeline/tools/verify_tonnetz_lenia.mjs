// verify_tonnetz_lenia.mjs — 종달새와 문어 의 검증 (docs/tonnetz_lenia_spec.md §5 V1~V6)
// 페이지와 **같은 엔진 파일**(lenia/tonnetz-core.js)과 같은 Algorithm 1 포팅을 돌린다. 소리·화면 없음.
//   node tools/verify_tonnetz_lenia.mjs            → docs/step3_data/tonnetz_lenia_verify.json
// 사전 예측은 spec §5 에 실행 전에 적었다. 이 파일은 재기만 한다.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = globalThis;
require(path.join(ROOT, 'hibari_dashboard/public/js/generation-algo1.js'));
const TL = require(path.join(ROOT, 'lenia/tonnetz-core.js'));
const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, 'lenia/tonnetz.json'), 'utf8'));
const G = globalThis.GenerationAlgo1;
const CM = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/step3_data/cycle_markov_results.json'), 'utf8'));

const N_SEEDS = 20, STEPS = 640, WIN = 32, SEED0 = 4101;
const geo = TL.buildGeo();
const DIA = new Set([0, 2, 4, 5, 7, 9, 11]);
const diaNodes = geo.nodes.map((n, i) => i).filter(i => DIA.has(geo.nodes[i].pc));

// ── 고정 입력 (모든 시드·팔이 같은 것을 쓴다) ───────────────────────────
function fixedOrder(seed, list) {
  const r = G.makeRng(seed), a = list.slice();
  for (let j = a.length - 1; j > 0; j--) { const q = Math.floor(r() * (j + 1)); [a[j], a[q]] = [a[q], a[j]]; }
  return a;
}
// 알 자리 8곳: 서로 이웃하지 않는 hibari 칸
const EGGS = [];
for (const n of fixedOrder(12345, diaNodes)) {
  if (EGGS.length === 8) break;
  if (EGGS.every(m => m !== n && !geo.nodes[m].nb.includes(n))) EGGS.push(n);
}
const CARE_SEQ = fixedOrder(777, diaNodes);            // 같은 돌봄: 8스텝마다 이 순서로 3곳씩

// ── 음높이 분포 JS — eval_metrics.pitch_distribution_similarity 와 같은 정의 ──
function jsd(a, b) {
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort((x, y) => x - y);
  const ta = keys.reduce((s, k) => s + (a[k] || 0), 0), tb = keys.reduce((s, k) => s + (b[k] || 0), 0);
  if (!ta || !tb) return null;
  let p = keys.map(k => (a[k] || 0) / ta + 1e-10), q = keys.map(k => (b[k] || 0) / tb + 1e-10);
  const sp = p.reduce((x, y) => x + y), sq = q.reduce((x, y) => x + y);
  p = p.map(x => x / sp); q = q.map(x => x / sq);
  let js = 0;
  for (let i = 0; i < keys.length; i++) { const m = (p[i] + q[i]) / 2; js += 0.5 * p[i] * Math.log(p[i] / m) + 0.5 * q[i] * Math.log(q[i] / m); }
  return js;
}
const ORIG = DATA.orig_pitch_counts;
const med = a => { const s = a.filter(x => x != null).sort((x, y) => x - y); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const q = (a, f) => { const s = a.filter(x => x != null).sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(f * s.length))] : null; };
const iqr = a => [q(a, 0.25), med(a), q(a, 0.75)];
const range = a => { const s = a.filter(x => x != null).sort((x, y) => x - y); return s.length ? [s[0], s[s.length - 1]] : null; };

// ── 한 세계 ────────────────────────────────────────────────────────────
// input: { n: 알 수, near: 음높이 근처 }  care: 'none' | 'same' | 'player'
function runWorld({ seed, input, care = 'none', steps = STEPS, opts = {} }) {
  const L = TL.create(DATA, Object.assign({ seed, algo1: G }, opts));
  for (let i = 0; i < input.n; i++) L.hatch(EGGS[i], i % 2 ? 'octopus' : 'lark', input.near);
  const perStep = [], cfg = [], alive = [], heads = {};
  let ci = 0;
  for (let t = 0; t < steps; t++) {
    if (t % 8 === 0) {
      if (care === 'same') for (let k = 0; k < 3; k++) L.feed(CARE_SEQ[(ci++) % CARE_SEQ.length], 1.0);
      if (care === 'player') L.alive().forEach(c => L.feed(c.node, 1.0));
    }
    const ev = L.step(), ps = {};
    for (const e of ev.notes) {
      for (const n of e.notes) ps[n[0]] = (ps[n[0]] || 0) + 1;
      (heads[e.id] = heads[e.id] || [])[t] = e.notes.length ? e.notes[0][0] : null;
    }
    perStep.push(ps);
    const al = L.alive();
    alive.push(al.length);
    cfg.push(new Set(al.map(c => c.node + '|' + c.species + '|' + c.li)));
  }
  return { L, perStep, cfg, alive, heads };
}
function windowDist(w, t) {
  const d = {};
  for (let u = Math.max(0, t - WIN + 1); u <= t; u++) for (const k in w.perStep[u]) d[k] = (d[k] || 0) + w.perStep[u][k];
  return d;
}
const silentAt = (w, t) => Object.keys(windowDist(w, t)).length === 0;
function symdiff(a, b) { let n = 0; for (const x of a) if (!b.has(x)) n++; for (const x of b) if (!a.has(x)) n++; return n; }
function sameSet(a, b) { return a.size === b.size && symdiff(a, b) === 0; }

// ── V5 입력 기억 시간 (결합 모드) ───────────────────────────────────────
const INPUTS = { a: [{ n: 2, near: 66 }, { n: 8, near: 66 }], b: [{ n: 4, near: 52 }, { n: 4, near: 81 }] };
function v5(care, arm) {
  const opts = Object.assign({ coupled: true }, arm === 'no_balance' ? { COST: 0 } : {});
  const out = {};
  for (const key of ['a', 'b']) {
    const [IA, IB] = INPUTS[key];
    const pairs = [], noiseA = [], noiseB = [];
    for (let s = 0; s < N_SEEDS; s++) {
      const seed = SEED0 + s;
      const A = runWorld({ seed, input: IA, care, opts }), B = runWorld({ seed, input: IB, care, opts });
      const A2 = runWorld({ seed: seed + 1000, input: IA, care, opts }), B2 = runWorld({ seed: seed + 1000, input: IB, care, opts });
      const js = [], jsA = [], jsB = [], dcfg = [], both = [];
      for (let t = WIN - 1; t < STEPS; t++) {
        js.push(jsd(windowDist(A, t), windowDist(B, t)));
        jsA.push(jsd(windowDist(A, t), windowDist(A2, t)));
        jsB.push(jsd(windowDist(B, t), windowDist(B2, t)));
        dcfg.push(symdiff(A.cfg[t], B.cfg[t]));
        both.push(silentAt(A, t) && silentAt(B, t));
      }
      pairs.push({ A, B, js, dcfg, both, same_end: sameSet(A.cfg[STEPS - 1], B.cfg[STEPS - 1]) && A.alive[STEPS - 1] > 0 });
      noiseA.push(jsA); noiseB.push(jsB);
    }
    // 잡음 바닥: 시각마다 20쌍 중앙값 (두 입력 중 큰 쪽). 정의되지 않으면 직전 값을 잇는다
    const T = STEPS - WIN + 1, floor = [];
    let last = null;
    for (let i = 0; i < T; i++) {
      const fa = noiseA.map(r => r[i]).filter(x => x != null), fb = noiseB.map(r => r[i]).filter(x => x != null);
      const va = fa.length >= 5 ? med(fa) : null, vb = fb.length >= 5 ? med(fb) : null;
      const v = va == null && vb == null ? last : Math.max(va ?? -1, vb ?? -1);
      floor.push(v); if (v != null) last = v;
    }
    const mem = [], kinds = { silence: 0, identical: 0, indistinguishable: 0, distinct: 0 };
    pairs.forEach(p => {
      let t0 = null;
      for (let i = T - 1; i >= 0; i--) {
        const ok = p.both[i] || (p.js[i] != null && floor[i] != null && p.js[i] <= floor[i]);
        if (!ok) break;
        t0 = i;
      }
      const tm = t0 == null ? null : t0 + WIN - 1;
      mem.push(tm);
      const end = T - 1;
      if (p.both[end]) kinds.silence++;
      else if (p.same_end) kinds.identical++;
      else if (tm != null) kinds.indistinguishable++;
      else kinds.distinct++;
    });
    const at = (arr, t) => arr.map(p => p[t - (WIN - 1)]);
    out[key] = {
      inputs: [IA, IB],
      memory_time_steps: { median: med(mem.map(x => x == null ? Infinity : x)), iqr: iqr(mem.map(x => x == null ? Infinity : x)),
                           censored: mem.filter(x => x == null).length, all: mem },
      merge_kinds_at_end: kinds,
      config_diff_at: { 64: iqr(at(pairs.map(p => p.dcfg), 64)), 160: iqr(at(pairs.map(p => p.dcfg), 160)),
                        320: iqr(at(pairs.map(p => p.dcfg), 320)), 639: iqr(at(pairs.map(p => p.dcfg), 639)) },
      js_ab_at: { 64: iqr(at(pairs.map(p => p.js), 64)), 160: iqr(at(pairs.map(p => p.js), 160)), 320: iqr(at(pairs.map(p => p.js), 320)) },
      floor_at: { 64: floor[64 - WIN + 1], 160: floor[160 - WIN + 1], 320: floor[320 - WIN + 1] },
      alive_A_at: { 160: iqr(pairs.map(p => p.A.alive[160])), 320: iqr(pairs.map(p => p.A.alive[320])), 639: iqr(pairs.map(p => p.A.alive[639])) },
      alive_B_at: { 160: iqr(pairs.map(p => p.B.alive[160])), 320: iqr(pairs.map(p => p.B.alive[320])), 639: iqr(pairs.map(p => p.B.alive[639])) },
      reached_cap_both: pairs.filter(p => Math.max(...p.A.alive) >= 8 && Math.max(...p.B.alive) >= 8).length,
    };
  }
  return out;
}

// ── H0 결합 모드 자기 검사: 같은 시드·같은 입력이면 비트 동일, 한 번 같아지면 계속 같다 ─────
function h0() {
  const w1 = runWorld({ seed: 99, input: { n: 4, near: 66 }, care: 'same', opts: { coupled: true } });
  const w2 = runWorld({ seed: 99, input: { n: 4, near: 66 }, care: 'same', opts: { coupled: true } });
  let same = 0; for (let t = 0; t < STEPS; t++) same += JSON.stringify(w1.perStep[t]) === JSON.stringify(w2.perStep[t]) ? 1 : 0;
  return { identical_steps: same + '/' + STEPS };
}

// ── V6 닫힌 고리가 도달하는 분포 + V1 난수 고리 ─────────────────────────
function v6() {
  const res = { real: [], random: [], real_vs_random: [], real_vs_real: [] };
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 500 + s;
    const R1 = runWorld({ seed, input: { n: 4, near: 66 }, care: 'same' });
    const R2 = runWorld({ seed: seed + 1000, input: { n: 4, near: 66 }, care: 'same' });
    const X = runWorld({ seed, input: { n: 4, near: 66 }, care: 'same', opts: { randomCycles: true } });
    const tot = w => { const d = {}; for (let t = 64; t < STEPS; t++) for (const k in w.perStep[t]) d[k] = (d[k] || 0) + w.perStep[t][k]; return d; };
    const d1 = tot(R1), d2 = tot(R2), dx = tot(X);
    res.real.push(jsd(ORIG, d1)); res.random.push(jsd(ORIG, dx));
    res.real_vs_random.push(jsd(d1, dx)); res.real_vs_real.push(jsd(d1, d2));
    res.alive_end = (res.alive_end || []).concat([R1.alive[STEPS - 1]]);
    res.notes = (res.notes || []).concat([Object.values(d1).reduce((a, b) => a + b, 0)]);
  }
  const algo1 = CM.tonnetz.summary.algo1.js;
  return {
    open_algo1_tonnetz_om: algo1,
    closed_loop_js_vs_hibari: { iqr: iqr(res.real), range: range(res.real) },
    random_cycles_js_vs_hibari: { iqr: iqr(res.random), range: range(res.random) },
    ratio_closed_over_open: med(res.real) / algo1.mean,
    V1_real_vs_random: { iqr: iqr(res.real_vs_random) }, V1_real_vs_real_seed_noise: { iqr: iqr(res.real_vs_real) },
    V1_ratio: med(res.real_vs_random) / med(res.real_vs_real),
    alive_at_end: iqr(res.alive_end), notes_after_burnin: iqr(res.notes),
    per_seed: res,
  };
}

// ── V2 돌봄 vs 방치 (플레이어처럼: 8스텝마다 생명체가 선 칸에 먹이) ─────────
function v2() {
  const care = [], none = []; let wins = 0;
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 900 + s, t3 = 396;                    // 3분 = 396스텝
    const a = runWorld({ seed, input: { n: 2, near: 66 }, care: 'player', steps: t3 + 1 });
    const b = runWorld({ seed, input: { n: 2, near: 66 }, care: 'none', steps: t3 + 1 });
    care.push(a.alive[t3]); none.push(b.alive[t3]); wins += a.alive[t3] > b.alive[t3] ? 1 : 0;
  }
  return { alive_at_3min_care: iqr(care), alive_at_3min_neglect: iqr(none), care_more_alive: wins + '/' + N_SEEDS };
}

// ── V3 발자국 따라가기 → 같은 가락을 늦게? ──────────────────────────────
function canon(w) {
  const ids = Object.keys(w.heads); if (ids.length < 2) return null;
  const a = w.heads[ids[0]], b = w.heads[ids[1]];
  let best = 0;
  for (const [x, y] of [[a, b], [b, a]]) for (let L = 8; L <= 64; L++) {
    let hit = 0, n = 0;
    for (let t = 0; t + L < STEPS; t++) if (x[t] != null && y[t + L] != null) { n++; if (x[t] === y[t + L]) hit++; }
    if (n > 50) best = Math.max(best, hit / n);
  }
  return best;
}
function v3() {
  const on = [], off = []; let wins = 0;
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 1300 + s;
    const a = canon(runWorld({ seed, input: { n: 2, near: 66 }, care: 'player' }));
    const b = canon(runWorld({ seed, input: { n: 2, near: 66 }, care: 'player', opts: { FOLLOW: 0 } }));
    on.push(a); off.push(b); if (a != null && b != null && a > b) wins++;
  }
  return { canon_follow_on: iqr(on), canon_follow_off: iqr(off), on_greater: wins + '/' + N_SEEDS };
}

// ── V4 몸 모양: 종달새는 박마다 각도가 하나, 문어는 모듈마다 +1칸 ─────────
function v4() {
  const w = runWorld({ seed: 7, input: { n: 2, near: 66 }, care: 'player' });
  const out = {};
  for (const c of w.L.state.creatures) {
    const byPh = {};
    for (const e of c.hist) {
      const ph = ((e.t - c.born) % c.period + c.period) % c.period, ang = ((e.t % 32) + 32) % 32;
      (byPh[ph] = byPh[ph] || []).push([e.t, ang]);
    }
    let single = 0, groups = 0, incs = [];
    for (const ph in byPh) {
      const g = byPh[ph].sort((x, y) => x[0] - y[0]); groups++;
      if (new Set(g.map(x => x[1])).size === 1) single++;
      for (let i = 1; i < g.length; i++) incs.push(((g[i][1] - g[i - 1][1]) % 32 + 32) % 32);
    }
    out[c.species] = { phases_with_one_angle: single + '/' + groups, median_angle_step_per_module: med(incs) };
  }
  return out;
}

// ── (선택) 두 단계 민감도 ────────────────────────────────────────────────
function sensitivity() {
  const K = DATA.cycles.length, NL = DATA.labels.length;
  const cnt = {}; DATA.cycles.forEach(c => c.forEach(u => cnt[u] = (cnt[u] || 0) + 1));
  const RAR = DATA.labels.map(l => cnt[l.li] ? 1 / cnt[l.li] : 0);
  const WS = DATA.cycles.map(c => c.reduce((a, x) => a + RAR[x], 0));
  const row = set => DATA.cycles.map((c, k) => (c.reduce((a, x) => a + (set.has(x) ? RAR[x] : 0), 0) / WS[k]) >= 0.35 ? 1 : 0);
  const poolDist = r => { const d = new Array(NL).fill(0); let t = 0; r.forEach((on, k) => { if (on) DATA.cycles[k].forEach(x => { d[x]++; t++; }); }); return t ? d.map(x => x / t) : null; };
  // 실제 생명체의 최근 음 집합을 모은다
  const sets = [];
  for (let s = 0; s < 10; s++) {
    const L = TL.create(DATA, { seed: 3000 + s, algo1: G });
    for (let i = 0; i < 4; i++) L.hatch(EGGS[i], i % 2 ? 'octopus' : 'lark', 66);
    for (let t = 0; t < 320; t++) {
      if (t % 8 === 0) L.alive().forEach(c => L.feed(c.node, 1));
      L.step();
      if (t > 32 && t % 16 === 0) L.alive().forEach(c => sets.push(new Set(c.recent.filter(r => r.to > L.state.t).map(r => r.li))));
    }
  }
  const r = G.makeRng(55);
  let h = 0, nh = 0, tv = 0, ntv = 0, act = 0;
  for (const S of sets) {
    if (!S.size) continue;
    const r0 = row(S); act += r0.reduce((a, b) => a + b, 0);
    const arr = [...S], out = arr[Math.floor(r() * arr.length)];
    let inn; do { inn = Math.floor(r() * NL); } while (S.has(inn));
    const S2 = new Set(S); S2.delete(out); S2.add(inn);
    const r1 = row(S2); h += r0.reduce((a, v, k) => a + (v !== r1[k] ? 1 : 0), 0); nh++;
    const k = Math.floor(r() * K), rf = r0.slice(); rf[k] = 1 - rf[k];
    const p0 = poolDist(r0), p1 = poolDist(rf);
    if (p0 && p1) { tv += 0.5 * p0.reduce((a, v, i) => a + Math.abs(v - p1[i]), 0); ntv++; }
  }
  const s1 = h / nh, s2 = tv / ntv;
  return { samples: nh, mean_active_cycles: act / nh, K,
           rows_changed_per_note_swap: s1, pool_tv_per_cycle_flip: s2, product: s1 * s2,
           note: '연속 공간 결과(곱 < 1 → 빨리 잊는다)를 이산 회로에 옮기지 않는다 — 적어만 둔다' };
}

// ── V5b (사후 보정, 2026-09-29): 판정기 검정 + 95% 잡음 띠 ─────────────────
// ⚠ 사전 기준의 결함: 잡음 바닥을 **중앙값**으로 잡으면, 분포가 완전히 같은 두 세계도 JS 가 바닥보다 위일 확률이 절반이라
//   "끝까지 아래에 머문다" 는 조건이 우연히만(끝 몇 스텝) 만족된다 → 기억 시간이 늘 끝 근처이거나 절단된다.
//   그래서 (1) 입력이 같은 독립 쌍에 같은 판정기를 돌려 보고(영가설 검정), (2) 바닥을 95% 띠(시각 ±16스텝을 모은 95번째 백분위)로 바꾼다.
//   추가로 (3) 칸 점유 분포의 JS — "처음 놓은 자리가 남는다" 는 설명을 직접 잰다.
function occ(w, t) {                                  // 최근 64스텝 동안 생명체가 선 칸의 분포
  const d = {};
  for (let u = Math.max(0, t - 63); u <= t; u++) for (const x of w.cfg[u]) { const n = x.split('|')[0]; d[n] = (d[n] || 0) + 1; }
  return d;
}
function v5b(care, arm) {
  const opts = Object.assign({ coupled: true }, arm === 'no_balance' ? { COST: 0 } : {});
  const res = {};
  for (const key of ['a', 'b']) {
    const [IA, IB] = INPUTS[key];
    const T = STEPS - WIN + 1, ab = [], nulls = [], noise = [], occAB = [], occNoise = [];
    for (let s = 0; s < N_SEEDS; s++) {
      const seed = SEED0 + s;
      const A = runWorld({ seed, input: IA, care, opts }), B = runWorld({ seed, input: IB, care, opts });
      const A2 = runWorld({ seed: seed + 1000, input: IA, care, opts }), A3 = runWorld({ seed: seed + 2000, input: IA, care, opts });
      const B2 = runWorld({ seed: seed + 1000, input: IB, care, opts });
      const r1 = [], r2 = [], r3 = [], r4 = [];
      for (let t = WIN - 1; t < STEPS; t++) {
        r1.push(jsd(windowDist(A, t), windowDist(B, t)));
        r2.push(jsd(windowDist(A2, t), windowDist(A3, t)));                  // 영가설 쌍 (같은 입력, 독립 시드)
        r3.push(Math.max(jsd(windowDist(A, t), windowDist(A2, t)) ?? -1, jsd(windowDist(B, t), windowDist(B2, t)) ?? -1));
      }
      for (const t of [64, 160, 320, 639]) { r4.push([t, jsd(occ(A, t), occ(B, t)), Math.max(jsd(occ(A, t), occ(A2, t)) ?? -1, jsd(occ(B, t), occ(B2, t)) ?? -1)]); }
      ab.push(r1); nulls.push(r2); noise.push(r3); occAB.push(r4);
    }
    const band = (arr, f) => { const out = []; for (let i = 0; i < T; i++) { const pool = [];
      for (let j = Math.max(0, i - 16); j <= Math.min(T - 1, i + 16); j++) arr.forEach(r => { if (r[j] != null && r[j] >= 0) pool.push(r[j]); });
      out.push(pool.length ? q(pool, f) : null); } return out; };
    const fMed = band(noise, 0.5), f95 = band(noise, 0.95);
    const memOf = (r, fl) => { let t0 = null; for (let i = T - 1; i >= 0; i--) { if (!(r[i] == null || (fl[i] != null && r[i] <= fl[i]))) break; t0 = i; }
      return t0 == null ? Infinity : t0 + WIN - 1; };
    const summ = (rows, fl) => { const m = rows.map(r => memOf(r, fl)); return { median: med(m), iqr: iqr(m), censored: m.filter(x => x === Infinity).length }; };
    const ratioAt = t => med(ab.map(r => r[t - WIN + 1]).filter(x => x != null)) / med(noise.map(r => r[t - WIN + 1]).filter(x => x != null && x >= 0));
    res[key] = {
      median_floor: { AB: summ(ab, fMed), null_pairs: summ(nulls, fMed) },
      band95_floor: { AB: summ(ab, f95), null_pairs: summ(nulls, f95) },
      js_ratio_AB_over_noise: { 64: ratioAt(64), 160: ratioAt(160), 320: ratioAt(320), 639: ratioAt(639) },
      occupancy_js: Object.fromEntries([64, 160, 320, 639].map((t, i) => [t, { AB: iqr(occAB.map(r => r[i][1])), same_input_noise: iqr(occAB.map(r => r[i][2])) }])),
    };
  }
  return res;
}

const ONLY = (process.argv.find(a => a.startsWith('--only=')) || '').slice(7);
if (ONLY === 'v5b') {
  const o = { script: 'tools/verify_tonnetz_lenia.mjs --only=v5b', n_seeds: N_SEEDS, steps: STEPS, generated_at: new Date().toISOString(), V5b: {} };
  for (const care of ['none', 'same']) for (const arm of ['balanced', 'no_balance']) {
    const k = care + ':' + arm; o.V5b[k] = v5b(care, arm);
    for (const key of ['a', 'b']) { const r = o.V5b[k][key];
      console.log('V5b', k, key, 'med-floor AB', JSON.stringify(r.median_floor.AB), 'null', JSON.stringify(r.median_floor.null_pairs),
                  '| 95band AB', JSON.stringify(r.band95_floor.AB), 'null', JSON.stringify(r.band95_floor.null_pairs),
                  '| ratio', JSON.stringify(Object.values(r.js_ratio_AB_over_noise).map(x => +x.toFixed(2))),
                  '| occ320', JSON.stringify(r.occupancy_js[320])); }
  }
  fs.writeFileSync(path.join(ROOT, 'docs/step3_data/tonnetz_lenia_verify_v5b.json'), JSON.stringify(o, (k, v) => v === Infinity ? 'inf' : v, 1));
  console.log('저장 docs/step3_data/tonnetz_lenia_verify_v5b.json'); process.exit(0);
}

const t0 = Date.now();
const out = { script: 'tools/verify_tonnetz_lenia.mjs', n_seeds: N_SEEDS, steps: STEPS, window: WIN, eggs: EGGS,
              generated_at: new Date().toISOString() };
out.H0_coupling_self_check = h0(); console.log('H0', out.H0_coupling_self_check);
out.V4_body_geometry = v4(); console.log('V4', JSON.stringify(out.V4_body_geometry));
out.V2_care_vs_neglect = v2(); console.log('V2', JSON.stringify(out.V2_care_vs_neglect));
out.V3_trail_canon = v3(); console.log('V3', JSON.stringify(out.V3_trail_canon));
out.V6_closed_loop_distribution = v6();
{ const v = out.V6_closed_loop_distribution; console.log('V6', JSON.stringify({ open: v.open_algo1_tonnetz_om.mean, closed: v.closed_loop_js_vs_hibari, random: v.random_cycles_js_vs_hibari, ratio: v.ratio_closed_over_open, V1_ratio: v.V1_ratio, alive: v.alive_at_end })); }
out.sensitivity = sensitivity(); console.log('S', JSON.stringify(out.sensitivity));
out.V5 = {};
for (const care of ['none', 'same']) for (const arm of ['balanced', 'no_balance']) {
  const k = care + ':' + arm; out.V5[k] = v5(care, arm);
  for (const key of ['a', 'b']) {
    const r = out.V5[k][key];
    console.log('V5', k, key, 'mem', r.memory_time_steps.median, JSON.stringify(r.memory_time_steps.iqr), 'cens', r.memory_time_steps.censored,
                JSON.stringify(r.merge_kinds_at_end), 'dcfg320', JSON.stringify(r.config_diff_at[320]), 'cap', r.reached_cap_both,
                'aliveA320', JSON.stringify(r.alive_A_at[320]), 'aliveB320', JSON.stringify(r.alive_B_at[320]));
  }
}
out.elapsed_s = (Date.now() - t0) / 1000;
fs.writeFileSync(path.join(ROOT, 'docs/step3_data/tonnetz_lenia_verify.json'), JSON.stringify(out, (k, v) => v === Infinity ? 'inf' : v, 1));
console.log('저장 docs/step3_data/tonnetz_lenia_verify.json', out.elapsed_s, 's');
