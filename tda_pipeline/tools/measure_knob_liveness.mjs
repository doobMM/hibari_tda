/* ============================================================================
 * measure_knob_liveness.mjs — 대시보드의 **모든 손잡이**가 살아 있는가
 *
 * 온도 하나를 고치고 나니 같은 질문이 남는다. 온도는 `NodePool` 안에서만 작동해서
 * 정본 OM 에서는 죽어 있었다. **`pitchTilt` 도 같은 곳에 있다**(생성자의 `scaled`).
 * 그렇다면 "음역" 슬라이더도 기본 상태에서 죽어 있어야 한다 — 확인해야 한다.
 * `densityFactor` 는 `instLen` 에 붙으므로 풀과 무관하게 살아 있어야 한다.
 *
 * 설계 — 손잡이마다 **귀무 개입 대조군**을 붙인다
 * ───────────────────────────────────────────
 *   개입: 손잡이를 실제로 움직인다
 *   귀무: `numModules` 65→64 — 풀 길이는 바뀌지만 상대 빈도·의미는 불변
 *   개입의 |t| 가 귀무와 비슷하면 그 손잡이는 **의미 없는 흔들림**이다.
 *
 * 이것이 ① 청취 회차에 넣을 축을 정한다. 지표가 아니라 **들리는 축**만 넣는다.
 *
 * 실행:  node tools/measure_knob_liveness.mjs
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rd = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const D = path.join(ROOT, 'hibari_dashboard', 'data');
const meta = rd(path.join(D, 'notes_metadata.json'));
const cycMeta = rd(path.join(D, 'cycles_metadata.json'));
const cont = rd(path.join(D, 'overlap_matrix_continuous.json'));
const K = cont.K;

globalThis.window = {};
(0, eval)(fs.readFileSync(path.join(ROOT, 'hibari_dashboard', 'public', 'js',
                                    'generation-algo1.js'), 'utf8'));
const G = globalThis.window.GenerationAlgo1;

const SEG = 60, taus = cycMeta.cycles.map(c => Number(c.tau));
const mk = f => {
  const v = new Int8Array(SEG * K);
  for (let t = 0; t < SEG; t++)
    for (let k = 0; k < K; k++) v[t * K + k] = f(cont.values[t * K + k], k);
  return v;
};
const SCEN = [
  ['정본 per-cycle τ (기본 로드)', mk((x, k) => x >= taus[k] ? 1 : 0)],
  ['이진 τ=0.7 (많이 지운 상태)',  mk(x => x >= 0.7 ? 1 : 0)],
];
const SEEDS = Array.from({ length: 40 }, (_, i) => 3000 + 17 * i);
const BASE_LEN = G.buildHibariInstLen(1088).slice(0, SEG);

// UI 와 동일한 밀도 적용 (ui-bootstrap.js applyDensity)
const applyDensity = (len, f) => {
  if (Math.abs(f - 1) < 1e-6) return len;
  const o = new Int32Array(len.length);
  for (let i = 0; i < len.length; i++) o[i] = Math.max(0, Math.round(len[i] * f));
  return o;
};

function gen(values, { temperature = 1, pitchTilt = 0, density = 1, numModules = 65 }, seed) {
  const rng = G.makeRng(seed);
  const pool = new G.NodePool({ labels: meta.labels, numModules, temperature, pitchTilt, rng });
  const ns = G.algorithm1({
    nodePool: pool, cycleManager: new G.CycleSetManager({ cycles: cycMeta.cycles, K }),
    instLen: applyDensity(BASE_LEN, density),
    overlap: { T: SEG, K, values }, maxResample: 50, rng }).notes;
  const meanPitch = ns.length ? ns.reduce((a, n) => a + n[1], 0) / ns.length : 0;
  return { n: ns.length, meanPitch, sig: ns.map(x => x.join(',')).join('|') };
}

const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)); };
const paired = (a, b) => {
  const d = a.map((x, i) => x - b[i]);
  const s = sd(d);
  return { delta: mean(d), t: s === 0 ? 0 : mean(d) / (s / Math.sqrt(d.length)) };
};

// UI 슬라이더 양 끝값 (index.html 의 min/max 를 그대로 쓴다)
const KNOBS = [
  ['Temperature 1.0→5.0', { temperature: 5.0 }, 'n'],
  ['음역 pitchTilt 0→+2.0 (슬라이더 우측 끝)', { pitchTilt: 2.0 }, 'meanPitch'],
  ['밀도 factor 1.0→2.0 (슬라이더 우측 끝)', { density: 2.0 }, 'n'],
];
const NULLARM = { numModules: 64 };
const LABEL = { n: '음 수', meanPitch: '평균 음고' };

const out = [];
for (const [scen, values] of SCEN) {
  console.log('\n' + '='.repeat(100));
  console.log(`${scen}   풀 노출 ${JSON.stringify(G.poolExposure({
    cycleManager: new G.CycleSetManager({ cycles: cycMeta.cycles, K }),
    overlap: { T: SEG, K, values } }).rows)}/${SEG}   (40시드 paired)`);
  console.log('='.repeat(100));
  const base = SEEDS.map(s => gen(values, {}, s));
  const nul = SEEDS.map(s => gen(values, NULLARM, s));
  console.log(`${'손잡이'.padEnd(40)} ${'지표'.padStart(9)} ${'변화량'.padStart(11)} ` +
              `${'|t|'.padStart(7)} ${'귀무 |t|'.padStart(8)} ${'비트동일'.padStart(9)}  판정`);
  for (const [name, opt, key] of KNOBS) {
    const arm = SEEDS.map(s => gen(values, opt, s));
    const pI = paired(arm.map(x => x[key]), base.map(x => x[key]));
    const pN = paired(nul.map(x => x[key]), base.map(x => x[key]));
    const identical = SEEDS.filter((_, i) => arm[i].sig === base[i].sig).length;
    const verdict = identical === SEEDS.length ? '**완전히 죽음 (출력 비트 동일)**'
      : Math.abs(pI.t) <= Math.abs(pN.t) + 1 ? '**의미 없는 흔들림 (귀무와 구별 불가)**'
      : '살아 있음';
    console.log(`${name.padEnd(40)} ${LABEL[key].padStart(9)} ` +
                `${(pI.delta >= 0 ? '+' : '') + pI.delta.toFixed(2)}`.padStart(12) +
                ` ${Math.abs(pI.t).toFixed(2).padStart(7)} ${Math.abs(pN.t).toFixed(2).padStart(8)} ` +
                `${(identical + '/' + SEEDS.length).padStart(9)}  ${verdict}`);
    out.push({ scenario: scen, knob: name, metric: key, delta: pI.delta, t: pI.t,
               null_t: pN.t, identical, n_seeds: SEEDS.length, verdict });
  }
}

fs.writeFileSync(path.join(ROOT, 'docs', 'step3_data', 'knob_liveness.json'),
  JSON.stringify({ experiment: 'knob_liveness',
    question: '대시보드의 각 손잡이가 사용자의 조작에 의미 있게 반응하는가',
    null_intervention: 'numModules 65→64 (풀 길이만 변경, 의미 불변)',
    note: '온도·음역은 NodePool 안에서만 작동하므로 풀 경로가 닫힌 OM 에서는 무력하다',
    n_seeds: SEEDS.length, segment_T: SEG, rows: out }, null, 2), 'utf8');
console.log('\n저장: docs/step3_data/knob_liveness.json');
