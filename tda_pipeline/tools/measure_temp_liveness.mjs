/* ============================================================================
 * measure_temp_liveness.mjs — 대시보드 온도 슬라이더가 실제로 살아 있는가
 *
 * 왜
 * ──
 * 목표가 "더 좋은 음악"에서 **"내 조작이 들리는가"** 로 바뀌었다(2026-08-31).
 * 그 프레임에서 가장 먼저 걸린 것은 `ui-bootstrap.js:2365` 의 온도 슬라이더다.
 *   · 온도는 `NodePool` 의 빈도 분포만 재구성한다(`generation-algo1.js:84`).
 *   · 풀은 **OM 행이 전부 0(flag==0)** 이거나 **활성 cycle 교집합이 빌 때**만 쓰인다.
 *   · 그런데 OM 은 사용자가 그린 행렬이다 → 촘촘하면 풀을 안 쓰고, 지우면 쓴다.
 * 즉 **같은 슬라이더가 어떨 때는 반응하고 어떨 때는 안 한다.** 죽은 손잡이보다 나쁘다.
 *
 * 이 스크립트는 그 주장을 배포 JS 를 직접 실행해 수치로 확정한다.
 *   ① 시나리오별 풀 경로 호출 횟수 (sample() 을 감싸서 실측)
 *   ② 온도만 바꿨을 때 실제로 달라지는 음의 비율
 * 측정 없이 고치면 또 엉뚱한 것을 고치게 된다.
 *
 * 실행:  node tools/measure_temp_liveness.mjs
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const SRC = path.join(ROOT, 'hibari_dashboard', 'public', 'js', 'generation-algo1.js');
const DATA = path.join(ROOT, 'hibari_dashboard', 'data');
const rd = p => JSON.parse(fs.readFileSync(p, 'utf8'));

const meta = rd(path.join(DATA, 'notes_metadata.json'));
const cycMeta = rd(path.join(DATA, 'cycles_metadata.json'));
const contOM = rd(path.join(DATA, 'overlap_matrix_continuous.json'));
const T = contOM.T, K = contOM.K;

globalThis.window = {};
(0, eval)(fs.readFileSync(SRC, 'utf8'));
const G = globalThis.window.GenerationAlgo1;

const taus = cycMeta.cycles.map(c => Number(c.tau));
const bin = (fn) => {
  const v = new Int8Array(T * K);
  for (let t = 0; t < T; t++)
    for (let k = 0; k < K; k++) v[t * K + k] = fn(contOM.values[t * K + k], k, t);
  return v;
};

// 대시보드가 실제로 보여 주는 것: 기본은 30초 세그먼트(T=60).
const SEG = 60, OFF = 0;
const slice = (v) => v.slice(OFF * K, (OFF + SEG) * K);

const SCEN = [
  ['정본 per-cycle τ (기본 로드)', slice(bin((x, k) => x >= taus[k] ? 1 : 0))],
  ['이진 τ=0.5',                  slice(bin(x => x >= 0.5 ? 1 : 0))],
  ['이진 τ=0.7 (희소하게 편집)',   slice(bin(x => x >= 0.7 ? 1 : 0))],
  ['모두 지우기 (btnClear)',       new Int8Array(SEG * K)],
];

const TEMPS = [1.0, 3.0, 5.0];      // 3.0 이 UI 기본값이다
const SEEDS = Array.from({ length: 12 }, (_, i) => 1000 + 37 * i);
const instLen = G.buildHibariInstLen(T).slice(OFF, OFF + SEG);

function run(values, temperature, seed) {
  const rng = G.makeRng(seed);
  const pool = new G.NodePool({ labels: meta.labels, numModules: 65, temperature, rng });
  let poolDraws = 0;
  const orig = pool.sample.bind(pool);
  pool.sample = () => { poolDraws++; return orig(); };
  const mgr = new G.CycleSetManager({ cycles: cycMeta.cycles, K });
  const out = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen,
                             overlap: { T: SEG, K, values }, maxResample: 50, rng });
  return { notes: out.notes, poolDraws };
}

const sig = ns => ns.map(n => n.join(',')).join('|');   // note = [start, pitch, end]

console.log('='.repeat(96));
console.log('온도 슬라이더 실측 — 배포 JS 직접 실행 (30초 세그먼트 T=60, 12시드)');
console.log('='.repeat(96));
console.log(`${'시나리오'.padEnd(28)} ${'빈 행'.padStart(7)} ${'풀 호출'.padStart(9)} ` +
            `${'전체 draw'.padStart(10)} ${'풀 비율'.padStart(8)}   T=3.0 이 T=1.0 과 다른 정도`);

const rows = [];
for (const [name, values] of SCEN) {
  let zero = 0;
  for (let t = 0; t < SEG; t++) {
    let s = 0;
    for (let k = 0; k < K; k++) s += values[t * K + k];
    if (s === 0) zero++;
  }
  let draws = 0, notes = 0, diff = 0, same = 0;
  for (const s of SEEDS) {
    const a = run(values, 1.0, s), b = run(values, 3.0, s);
    draws += a.poolDraws; notes += a.notes.length;
    if (sig(a.notes) === sig(b.notes)) same++;
    else {
      const A = sig(a.notes).split('|'), B = sig(b.notes).split('|');
      let d = 0;
      for (let i = 0; i < Math.max(A.length, B.length); i++) if (A[i] !== B[i]) d++;
      diff += d / Math.max(A.length, B.length);
    }
  }
  const changed = SEEDS.length - same;
  const pct = changed ? (100 * diff / changed) : 0;
  const verdict = same === SEEDS.length
    ? '**완전히 동일 — 슬라이더가 죽었다**'
    : `${changed}/${SEEDS.length} 시드에서 변화, 바뀐 음 평균 ${pct.toFixed(1)}%`;
  console.log(`${name.padEnd(28)} ${String(zero + '/' + SEG).padStart(7)} ` +
              `${String(draws).padStart(9)} ${String(notes).padStart(10)} ` +
              `${(100 * draws / Math.max(1, notes)).toFixed(1).padStart(7)}%   ${verdict}`);
  rows.push({ scenario: name, zero_rows: zero, T: SEG, pool_draws: draws,
              total_notes: notes, pool_ratio: draws / Math.max(1, notes),
              seeds_changed: changed, n_seeds: SEEDS.length, mean_note_diff_pct: pct });
}

// 온도 3단계가 서로 구분되는가 (정본 시나리오에서)
console.log('\n' + '-'.repeat(96));
console.log('온도 3단계 상호 비교 — 정본 per-cycle τ 에서');
const base = SCEN[0][1];
for (let i = 0; i < TEMPS.length; i++)
  for (let j = i + 1; j < TEMPS.length; j++) {
    let same = 0;
    for (const s of SEEDS)
      if (sig(run(base, TEMPS[i], s).notes) === sig(run(base, TEMPS[j], s).notes)) same++;
    console.log(`  T=${TEMPS[i]} vs T=${TEMPS[j]}: ${same}/${SEEDS.length} 시드에서 ` +
                `**비트 단위 동일**`);
  }

fs.writeFileSync(path.join(ROOT, 'docs', 'step3_data', 'temp_slider_liveness.json'),
  JSON.stringify({ experiment: 'temp_slider_liveness',
                   question: '대시보드 온도 슬라이더가 사용자의 조작에 반응하는가',
                   source: 'hibari_dashboard/public/js/generation-algo1.js (배포본 직접 실행)',
                   segment_T: SEG, n_seeds: SEEDS.length, ui_default_temperature: 3.0,
                   scenarios: rows }, null, 2), 'utf8');
console.log('\n저장: docs/step3_data/temp_slider_liveness.json');
