/* ============================================================================
 * measure_temp_direction.mjs — 온도가 **방향 있는 변화**를 만드는가, 난수만 미는가
 *
 * 앞선 실측(`measure_temp_liveness.mjs`)에서 이상한 것이 나왔다.
 * 정본 per-cycle τ 에서 **풀 호출이 0 회**인데 T=1 과 T=3 의 출력이 다르다(음 4.2%).
 * 풀을 한 번도 안 뽑는데 출력이 바뀔 수 있는 경로는 하나뿐이다 —
 *
 *     NodePool 생성자의 `shuffle(pool, rng)`.
 *     풀 길이가 온도에 따라 달라지므로 **셔플이 소비하는 난수 개수가 달라지고**,
 *     그 뒤의 모든 난수가 밀린다. 즉 씨앗을 바꾼 것과 같다.
 *
 * 그렇다면 사용자가 보는 "변화"는 **의미도 방향도 없는 재추첨**이다.
 * 죽은 손잡이보다 나쁘다 — 반응하는 것처럼 보여서 틀린 모형을 학습시킨다.
 *
 * 귀무 개입 대조군 (이 프로젝트에서 반복해서 헤드라인을 살린 그 패턴)
 * ────────────────────────────────────────────────────────────────
 *   `numModules` 를 65 → 64 로 바꾼다. 풀 길이는 달라지지만 **상대 빈도는 그대로**다.
 *   온도가 하는 일이 난수 밀기뿐이라면, T=1↔T=3 의 차이가
 *   numModules 65↔64 의 차이와 **구별되지 않아야** 한다.
 *
 * 실행:  node tools/measure_temp_direction.mjs
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DATA = path.join(ROOT, 'hibari_dashboard', 'data');
const rd = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const meta = rd(path.join(DATA, 'notes_metadata.json'));
const cycMeta = rd(path.join(DATA, 'cycles_metadata.json'));
const contOM = rd(path.join(DATA, 'overlap_matrix_continuous.json'));
const T = contOM.T, K = contOM.K;

globalThis.window = {};
(0, eval)(fs.readFileSync(path.join(ROOT, 'hibari_dashboard', 'public', 'js',
                                    'generation-algo1.js'), 'utf8'));
const G = globalThis.window.GenerationAlgo1;

const taus = cycMeta.cycles.map(c => Number(c.tau));
const SEG = 60;
const mk = fn => {
  const v = new Int8Array(SEG * K);
  for (let t = 0; t < SEG; t++)
    for (let k = 0; k < K; k++) v[t * K + k] = fn(contOM.values[t * K + k], k);
  return v;
};
const SCEN = [
  ['정본 per-cycle τ (풀 0%)', mk((x, k) => x >= taus[k] ? 1 : 0)],
  ['이진 τ=0.7 (풀 96%)',      mk(x => x >= 0.7 ? 1 : 0)],
];

const SEEDS = Array.from({ length: 40 }, (_, i) => 3000 + 17 * i);
const instLen = G.buildHibariInstLen(T).slice(0, SEG);

function stats(values, { temperature = 1.0, numModules = 65 }, seed) {
  const rng = G.makeRng(seed);
  const pool = new G.NodePool({ labels: meta.labels, numModules, temperature, rng });
  const mgr = new G.CycleSetManager({ cycles: cycMeta.cycles, K });
  const ns = G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen,
                            overlap: { T: SEG, K, values }, maxResample: 50, rng }).notes;
  // 온도가 "노린" 방향: 높을수록 빈도 분포가 평평해진다 → 드문 음이 더 나와야 한다.
  // 그것을 직접 재는 두 지표.
  const cnt = new Map();
  for (const n of ns) cnt.set(n[1], (cnt.get(n[1]) || 0) + 1);   // note = [start, pitch, end]
  const tot = ns.length || 1;
  let H = 0;
  for (const c of cnt.values()) { const p = c / tot; H -= p * Math.log2(p); }
  return { n: ns.length, pitchEntropy: H, distinctPitch: cnt.size };
}

const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
const sd = a => Math.sqrt(a.reduce((s, x) => s + (x - mean(a)) ** 2, 0) / (a.length - 1));
// paired t (같은 시드끼리)
function paired(a, b) {
  const d = a.map((x, i) => x - b[i]);
  const t = mean(d) / (sd(d) / Math.sqrt(d.length));
  return { delta: mean(d), t };
}

const KEYS = ['pitchEntropy', 'distinctPitch', 'n'];
const NAME = { pitchEntropy: '음고 엔트로피', distinctPitch: '고유 음고 수', n: '음 수' };
const out = [];

for (const [scen, values] of SCEN) {
  console.log('\n' + '='.repeat(94));
  console.log(scen + '   (40시드 paired)');
  console.log('='.repeat(94));
  const base = SEEDS.map(s => stats(values, {}, s));
  const hot  = SEEDS.map(s => stats(values, { temperature: 3.0 }, s));
  const nullArm = SEEDS.map(s => stats(values, { numModules: 64 }, s));   // 귀무 개입

  console.log(`${'지표'.padEnd(16)} ${'T=1.0'.padStart(16)} ${'T=3.0 (개입)'.padStart(18)} ` +
              `${'|t|'.padStart(7)}   ${'numModules 64 (귀무)'.padStart(20)} ${'|t|'.padStart(7)}`);
  for (const k of KEYS) {
    const A = base.map(x => x[k]), B = hot.map(x => x[k]), C = nullArm.map(x => x[k]);
    const pB = paired(B, A), pC = paired(C, A);
    console.log(`${NAME[k].padEnd(16)} ${mean(A).toFixed(3).padStart(16)} ` +
                `${(mean(B).toFixed(3) + ` (${pB.delta >= 0 ? '+' : ''}${pB.delta.toFixed(3)})`).padStart(18)} ` +
                `${Math.abs(pB.t).toFixed(2).padStart(7)}   ` +
                `${(mean(C).toFixed(3) + ` (${pC.delta >= 0 ? '+' : ''}${pC.delta.toFixed(3)})`).padStart(20)} ` +
                `${Math.abs(pC.t).toFixed(2).padStart(7)}`);
    out.push({ scenario: scen, metric: k, base: mean(A),
               temp3_delta: pB.delta, temp3_t: pB.t,
               null_delta: pC.delta, null_t: pC.t });
  }
  console.log('  → 개입(T=3.0)의 |t| 가 귀무(numModules 64)의 |t| 와 비슷하면, ' +
              '온도는 **난수를 밀 뿐** 방향을 만들지 않는다.');
}

fs.writeFileSync(path.join(ROOT, 'docs', 'step3_data', 'temp_slider_direction.json'),
  JSON.stringify({ experiment: 'temp_slider_direction',
                   question: '온도가 방향 있는 변화를 만드는가, 난수 스트림만 미는가',
                   mechanism: 'NodePool 생성자의 shuffle(pool, rng) 이 풀 길이만큼 난수를 소비한다',
                   null_intervention: 'numModules 65→64 — 풀 길이는 바뀌고 상대 빈도는 불변',
                   n_seeds: SEEDS.length, segment_T: SEG, rows: out }, null, 2), 'utf8');
console.log('\n저장: docs/step3_data/temp_slider_direction.json');
