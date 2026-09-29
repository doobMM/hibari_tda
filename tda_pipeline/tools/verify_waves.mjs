// verify_waves.mjs — 두 손의 파도(2판) 검증 (docs/tonnetz_lenia_spec.md §9.7 W2~W7, 실행 전에 적은 예측)
// 페이지와 같은 엔진 파일(lenia/waves-core.js)과 같은 Algorithm 1 포팅을 돌린다. 소리·화면 없음.
//   node tools/verify_waves.mjs   → docs/step3_data/waves_verify.json
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = globalThis;
require(path.join(ROOT, 'hibari_dashboard/public/js/generation-algo1.js'));
const TW = require(path.join(ROOT, 'lenia/waves-core.js'));
const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'lenia/tonnetz.json'), 'utf8'));
const G = globalThis.GenerationAlgo1;
const N_SEEDS = 20, SEED0 = 7300, STEPS = 660;           // 660스텝 = 5분
const geo = TW.buildGeo();
const DIA = new Set([0, 2, 4, 5, 7, 9, 11]);
const dia = geo.nodes.map((n, i) => i).filter(i => DIA.has(geo.nodes[i].pc));
const wr = (v, P) => v - P * Math.round(v / P);
const dist = (i, j) => { const a = geo.nodes[i], b = geo.nodes[j]; return Math.hypot(wr(a.x - b.x, TW.W), wr(a.y - b.y, TW.H)); };
const at = (fx, fy) => dia.reduce((b, i) => { const n = geo.nodes[i], m = geo.nodes[b];
  return Math.hypot(n.x - TW.W * fx, n.y - TW.H * fy) < Math.hypot(m.x - TW.W * fx, m.y - TW.H * fy) ? i : b; }, dia[0]);
const LARK = at(0.3, 0.5), OCT_FAR = at(0.8, 0.0);       // 고정 자리 — 모든 시드·팔이 같다
const med = a => { const s = a.filter(x => x != null && !Number.isNaN(x)).sort((x, y) => x - y); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const qt = (a, f) => { const s = a.filter(x => x != null).sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(f * s.length))] : null; };
const iqr = a => [qt(a, 0.25), med(a), qt(a, 0.75)];
const jac = (A, B) => { const u = new Set([...A, ...B]); if (!u.size) return 1; let n = 0; for (const x of A) if (B.has(x)) n++; return n / u.size; };
function jsd(a, b) {
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  const ta = keys.reduce((s, k) => s + (a[k] || 0), 0), tb = keys.reduce((s, k) => s + (b[k] || 0), 0);
  if (!ta || !tb) return null;
  let p = keys.map(k => (a[k] || 0) / ta + 1e-10), q = keys.map(k => (b[k] || 0) / tb + 1e-10);
  const sp = p.reduce((x, y) => x + y), sq = q.reduce((x, y) => x + y); p = p.map(x => x / sp); q = q.map(x => x / sq);
  let js = 0; for (let i = 0; i < keys.length; i++) { const m = (p[i] + q[i]) / 2; js += 0.5 * p[i] * Math.log(p[i] / m) + 0.5 * q[i] * Math.log(q[i] / m); }
  return js;
}
// 문어를 lark 에 가깝게 두는 칸: 거리 ≈ d
function octAt(d) { return dia.reduce((b, i) => Math.abs(dist(LARK, i) - d) < Math.abs(dist(LARK, b) - d) && i !== LARK ? i : b, OCT_FAR); }

function world(seed, opts = {}) { return TW.create(D, Object.assign({ seed, algo1: G }, opts)); }
function run(W, steps, script) {
  const pitch = {}, foundK = new Set(), rates = []; let notes = 0, lit = 0;
  for (let t = 0; t < steps; t++) {
    if (script) script(W, t);
    const ev = W.step();
    rates.push(ev.rate); lit += ev.fired.length;
    ev.found.forEach(([k]) => foundK.add(k));
    if (t >= 64) ev.voices.forEach(v => v.notes.forEach(q => { pitch[q[0]] = (pitch[q[0]] || 0) + 1; notes++; }));
  }
  return { pitch, foundK, rates, notes, lit: lit / steps, silentEnd: W.lit() === 0 };
}
const out = { script: 'tools/verify_waves.mjs', n_seeds: N_SEEDS, steps: STEPS, lark: LARK, generated_at: new Date().toISOString() };

// H0 결합 모드 자기 검사
{ const a = world(1, { coupled: true }), b = world(1, { coupled: true });
  [a, b].forEach(w => { w.source(LARK, 1); w.source(octAt(3), 2, 1); });
  let same = 0; for (let t = 0; t < 300; t++) { a.step(); b.step(); same += a.state.phi.every((x, i) => x === b.state.phi[i]) ? 1 : 0; }
  out.H0_coupled_identical_steps = same + '/300'; console.log('H0', out.H0_coupled_identical_steps); }

// W1 (단위 검사) 두 손의 박이 모듈마다 한 칸씩 어긋난다
{ const w = world(2); const a = w.source(LARK, 1), b = w.source(octAt(9), 2, 0); const d = [];
  for (let m = 0; m < 8; m++) { const t = m * 32 * 33; d.push(((t - b.born) % 33) - ((t - a.born) % 32)); }
  out.W1_phase = '32·33 주기 — 원천의 박 위상은 정의상 모듈마다 1 스텝 어긋난다 (결정적)'; }

// W2 rate 가 찾는 고리를 바꾼다
{ const J01 = [], J00 = [], J11 = [], n0 = [], n1 = [];
  for (let s = 0; s < N_SEEDS; s++) {
    const setup = w => { w.source(LARK, 1); w.source(octAt(3), 2, 1); };
    const mk = (seed, r) => { const w = world(seed, { fixedRate: r }); setup(w); return run(w, STEPS).foundK; };
    const a0 = mk(SEED0 + s, 0), a1 = mk(SEED0 + s, 1.2), b0 = mk(SEED0 + s + 1000, 0), b1 = mk(SEED0 + s + 1000, 1.2);
    J01.push(jac(a0, a1)); J00.push(jac(a0, b0)); J11.push(jac(a1, b1)); n0.push(a0.size); n1.push(a1.size);
  }
  out.W2 = { jaccard_rate0_vs_rate1_2: iqr(J01), same_rate_seed_jaccard_r0: iqr(J00), same_rate_seed_jaccard_r1_2: iqr(J11),
             found_count_r0: iqr(n0), found_count_r1_2: iqr(n1),
             prediction: 'J(0 vs 1.2) ≤ 0.3, 같은 rate 시드 간 ≥ 0.6' };
  console.log('W2', JSON.stringify(out.W2)); }

// W3 옮기면 더 많이 찾는다 — 문어를 멀리 → 가까이 → 멀리 (rate 0 → 1.5 → 0)
{ const sweep = [], stat = { 0: [], 0.4: [], 0.8: [], 1.2: [], 1.5: [] }, bestStatic = [], rateCover = [], posOnly = [], rateOnly = [];
  const path = []; for (let i = 0; i <= 10; i++) path.push(octAt(9 - 8.5 * Math.sin(Math.PI * i / 10)));
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 200 + s;
    const w = world(seed); w.source(LARK, 1); const o = w.source(path[0], 2, 1);
    const r = run(w, STEPS, (W2, t) => { const k = Math.min(10, Math.floor(t / STEPS * 11)); W2.moveSource(o, path[k]); });
    sweep.push(r.foundK.size); rateCover.push([Math.min(...r.rates), Math.max(...r.rates)]);
    let best = 0;
    for (const rr of Object.keys(stat)) { const w2 = world(seed, { fixedRate: +rr }); w2.source(LARK, 1); w2.source(octAt(3), 2, 1);
      const n = run(w2, STEPS).foundK.size; stat[rr].push(n); best = Math.max(best, n); }
    bestStatic.push(best);
    // ⚠ 사후 대조군 (1차 결과를 본 뒤 추가): 옮김은 **자리**와 **rate** 를 함께 바꾼다. 둘을 떼어 본다.
    //   posOnly  = 같은 경로로 옮기되 rate 는 sweep 의 평균에 고정 · rateOnly = 자리는 그대로, rate 만 0→1.5→0
    const meanR = r.rates.reduce((x, y) => x + y) / r.rates.length;
    const wp = world(seed, { fixedRate: Math.round(meanR * 100) / 100 }); wp.source(LARK, 1); const op = wp.source(path[0], 2, 1);
    posOnly.push(run(wp, STEPS, (W2, t) => { W2.moveSource(op, path[Math.min(10, Math.floor(t / STEPS * 11))]); }).foundK.size);
    const wq = world(seed); wq.source(LARK, 1); wq.source(octAt(3), 2, 1);
    rateOnly.push(run(wq, STEPS, (W2, t) => { W2.state.P.fixedRate = Math.round(150 * Math.sin(Math.PI * Math.min(10, Math.floor(t / STEPS * 11)) / 10)) / 100; }).foundK.size);
  }
  out.W3 = { sweep_found: iqr(sweep), best_static_found: iqr(bestStatic),
             static_found_by_rate: Object.fromEntries(Object.entries(stat).map(([k, v]) => [k, iqr(v)])),
             ratio_median: med(sweep) / med(bestStatic), sweep_rate_range_example: rateCover[0],
             sweep_beats_best_static: sweep.filter((x, i) => x > bestStatic[i]).length + '/' + N_SEEDS,
             posthoc_position_only_fixed_rate: iqr(posOnly), posthoc_rate_only_fixed_position: iqr(rateOnly),
             prediction: 'sweep 중앙값 ≥ 1.5 × 가장 좋은 고정 rate' };
  console.log('W3', JSON.stringify(out.W3)); }

// W4 메커니즘 (거리 행렬 섞기) + W5 닫힌 고리의 분포
{ const real = [], shuf = [], noise = [], toHib = [], toHibShuf = [], corr = [];
  const mem = {}; D.labels.forEach(l => { mem[l.pitch] = (mem[l.pitch] || 0) + D.cycles.filter(c => c.includes(l.li)).length; });
  const O = D.orig_pitch_counts;
  const pear = (a, b) => { const n = a.length, ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n; let s1 = 0, s2 = 0, s3 = 0;
    for (let i = 0; i < n; i++) { s1 += (a[i] - ma) * (b[i] - mb); s2 += (a[i] - ma) ** 2; s3 += (b[i] - mb) ** 2; } return s1 / Math.sqrt(s2 * s3); };
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 400 + s, setup = w => { w.source(LARK, 1); w.source(octAt(3.5), 2, 1); };
    const a = world(seed); setup(a); const ra = run(a, STEPS);
    const b = world(seed + 1000); setup(b); const rb = run(b, STEPS);
    const c = world(seed, { shuffleDist: true }); setup(c); const rc = run(c, STEPS);
    real.push(ra); noise.push(jsd(ra.pitch, rb.pitch)); shuf.push(jsd(ra.pitch, rc.pitch));
    toHib.push(jsd(O, ra.pitch)); toHibShuf.push(jsd(O, rc.pitch));
    const tot = Object.values(ra.pitch).reduce((x, y) => x + y, 0), ps = Object.keys(O).map(Number);
    corr.push(pear(ps.map(p => (ra.pitch[p] || 0) / tot), ps.map(p => mem[p] || 0)));
  }
  out.W4 = { js_real_vs_shuffled: iqr(shuf), js_real_vs_real_seed_noise: iqr(noise), ratio: med(shuf) / med(noise),
             prediction: '비 ≥ 3' };
  out.W5 = { js_vs_hibari: iqr(toHib), js_vs_hibari_shuffled: iqr(toHibShuf), open_algo1_tonnetz: 0.0440, v1_closed: 0.132,
             corr_pitch_share_vs_cycle_membership: iqr(corr), notes_per_run: iqr(real.map(r => r.notes)), mean_rate: med(real.map(r => r.rates.reduce((x, y) => x + y) / r.rates.length)),
             prediction: 'JS 중앙값 0.05~0.10, 상관 < 0.9' };
  console.log('W4', JSON.stringify(out.W4)); console.log('W5', JSON.stringify(out.W5)); }

// W6 균형 — 누르지 않으면 원천 수명 + 2모듈 안에 침묵, 60초마다 눌러 주면 계속 운다
{ const quiet = [], alive = [], silentAt = [];
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 600 + s, L0 = TW.DEF.LIFE, T = (L0 + 2) * 33 + 40;
    const a = world(seed); a.source(LARK, 1); a.source(octAt(3.5), 2, 1);
    let firstSilent = null;
    for (let t = 0; t < T; t++) { a.step(); if (firstSilent == null && a.state.srcs.length === 0 && a.lit() === 0) firstSilent = t; }
    quiet.push(a.lit() === 0 && a.state.srcs.length === 0); silentAt.push(firstSilent);
    const b = world(seed); const l = b.source(LARK, 1), o = b.source(octAt(3.5), 2, 1);
    for (let t = 0; t < T; t++) { if (t % 132 === 0) { b.source(LARK, 1); b.source(o.node, 2); } b.step(); }
    alive.push(b.state.srcs.length > 0 && b.lit() > 0);
  }
  out.W6 = { silent_without_care: quiet.filter(Boolean).length + '/' + N_SEEDS, first_silent_step: iqr(silentAt),
             active_with_care_60s: alive.filter(Boolean).length + '/' + N_SEEDS, life_modules: TW.DEF.LIFE,
             prediction: '방치 20/20 침묵 (수명+2모듈 안), 돌봄 20/20 계속' };
  console.log('W6', JSON.stringify(out.W6)); }

// W7 결합 (③) — 종달새만 vs 종달새+문어, 문어를 100스텝에 치운다 → 배치(φ·피로)까지 정확히 같아지는 시각
{ const tc = [];
  for (let s = 0; s < N_SEEDS; s++) {
    const seed = SEED0 + 800 + s;
    const A = world(seed, { coupled: true }), B = world(seed, { coupled: true });
    A.source(LARK, 1); B.source(LARK, 1); const o = B.source(octAt(3.5), 2, 1);
    let merged = null;
    for (let t = 0; t < 100 + 640; t++) {
      if (t === 100) B.removeSource(o);
      A.step(); B.step();
      if (t >= 100) {
        const same = A.state.phi.every((x, i) => x === B.state.phi[i]) && A.state.fat.every((x, i) => x === B.state.fat[i]);
        if (same && merged == null) merged = t - 100; else if (!same) merged = null;
      }
    }
    tc.push(merged);
  }
  out.W7 = { steps_to_identical_after_removal: iqr(tc.map(x => x == null ? Infinity : x)),
             merged_within_320: tc.filter(x => x != null && x <= 320).length + '/' + N_SEEDS,
             never: tc.filter(x => x == null).length, all: tc, prediction: '320스텝 안 ≥ 15/20' };
  console.log('W7', JSON.stringify(out.W7)); }

fs.writeFileSync(path.join(ROOT, 'docs/step3_data/waves_verify.json'), JSON.stringify(out, (k, v) => v === Infinity ? 'inf' : v, 1));
console.log('저장 docs/step3_data/waves_verify.json');
