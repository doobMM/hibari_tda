/* ============================================================================
 * make_arena_seeds.mjs — 파종장(arena)의 **씨앗 풀**을 만들고, 동시에
 * "무작위 조각들이 서로 충분히 다른가"를 계측한다.
 *
 * 왜 계측이 먼저인가
 * ─────────────────
 * 겨루기(A/B 선호 투표)가 성립하려면 두 조각이 **구별 가능해야** 한다.
 * 구별이 안 되면 투표는 동전던지기가 되고 Elo 는 잡음으로 수렴한다.
 * 게임을 세 번 접은 자리가 전부 "다 만들고 나서 안 된다는 걸 알았다" 였으므로,
 * 이번에는 **만들기 전에** 공간이 살아 있는지 잰다.
 *
 * 판정 기준 (실행 전에 적는다)
 *   · 무작위 두 조각의 특징 차이가 **같은 설정에서 시드만 바꿨을 때의 차이(잡음 바닥)**
 *     보다 뚜렷해야 한다. 그렇지 않으면 사람은 설정이 아니라 시드를 듣는 것이다.
 *   · 축별로 잡음 대비 배수를 낸다. 2배 미만이면 그 축은 겨루기에서 쓸모가 없다.
 *
 * 유전자(genome) = duet.html 의 SHARE 해시와 **같은 형식**이다. 새 규약을 만들지 않는다.
 *   p{pitch} d{density} t{tempo} g{length} a{material} s{seed}
 *
 * 실행:  node tools/make_arena_seeds.mjs
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rd = p => JSON.parse(fs.readFileSync(p, 'utf8'));

const bank = rd(path.join(ROOT, 'mobile_tonnetz', 'data', 'om_bank.json'));
const meta = rd(path.join(ROOT, 'hibari_dashboard', 'data', 'notes_metadata.json'));

globalThis.window = {};
(0, eval)(fs.readFileSync(path.join(ROOT, 'hibari_dashboard', 'public', 'js',
                                    'generation-algo1.js'), 'utf8'));
const G = globalThis.window.GenerationAlgo1;

const bits = (s, n) => {
  const v = new Int8Array(n);
  for (let i = 0; i < n; i++) v[i] = s.charCodeAt(i) === 49 ? 1 : 0;
  return v;
};

/** duet.html build() 과 동일한 순서. 딴 경로를 만들지 않는다. */
function render(g) {
  const b = bank.banks[g.a], T = b.T;
  const cyc = b.cycles.map((c, i) => ({ cycle_idx: i, note_labels_0idx: c }));
  const base = G.buildHibariInstLen(T), len = new Int32Array(T);
  for (let i = 0; i < T; i++) len[i] = Math.max(0, Math.round(base[i] * g.d));
  const rng = G.makeRng(g.s);
  const r = G.algorithm1({
    nodePool: new G.NodePool({ labels: meta.labels, numModules: 65, temperature: 1.0, rng }),
    cycleManager: new G.CycleSetManager({ cycles: cyc, K: b.K }),
    instLen: len, overlap: { T, K: b.K, values: bits(b.om_bits, T * b.K) },
    maxResample: 50, rng,
  });
  return r.notes.map(n => {
    const d = Math.max(1, Math.round((n[2] - n[0]) * g.g));
    return [n[0], n[1] + g.p, Math.min(T, n[0] + d)];
  });
}

/** 사람이 듣고 구별할 만한 특징만 고른다. 계산 가능한 것 전부가 아니다. */
function feat(ns, g) {
  if (!ns.length) return { n: 0, pitch: 0, len: 0, span: 0, loopSec: 0 };
  const ps = ns.map(x => x[1]);
  return {
    n: ns.length,
    pitch: ps.reduce((a, b) => a + b, 0) / ns.length,
    len: ns.reduce((s, x) => s + (x[2] - x[0]), 0) / ns.length,
    span: Math.max(...ps) - Math.min(...ps),
    loopSec: +(bank.banks[g.a].T * (0.25 / g.t)).toFixed(2),
  };
}

// ── 축 범위는 duet.html 의 노브 그대로 ──────────────────────────────────
const AX = { p: [-12, 12], d: [0.4, 2.2], t: [0.5, 2.0], g: [0.4, 3.0] };
const MATERIALS = [1, 2, 3, 4, 5];   // α=0 은 K=1(구조 붕괴)이라 씨앗에서 뺀다
let rs = 20260907;
const rnd = () => (rs = (rs * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const pick = ([lo, hi]) => lo + rnd() * (hi - lo);

const N = 48;
const seeds = [];
for (let i = 0; i < N; i++) {
  const g = {
    p: Math.round(pick(AX.p)), d: +pick(AX.d).toFixed(2), t: +pick(AX.t).toFixed(2),
    g: +pick(AX.g).toFixed(2), a: MATERIALS[Math.floor(rnd() * MATERIALS.length)],
    s: 1000 + Math.floor(rnd() * 899000),
  };
  seeds.push({ ...g, feat: feat(render(g), g) });
}

// ── 잡음 바닥 — 설정을 고정하고 시드만 바꾼다 ────────────────────────────
const fixed = { p: 0, d: 1.0, t: 1.0, g: 1.0, a: 2 };
const noise = [];
for (let i = 0; i < 40; i++) noise.push(feat(render({ ...fixed, s: 7000 + 13 * i }), fixed));

const sd = (a, k) => {
  const m = a.reduce((s, x) => s + x[k], 0) / a.length;
  return Math.sqrt(a.reduce((s, x) => s + (x[k] - m) ** 2, 0) / a.length);
};
const KEYS = ['n', 'pitch', 'len', 'span', 'loopSec'];
const LABEL = { n: '음 수', pitch: '평균 음고', len: '평균 길이', span: '음역폭', loopSec: '루프 길이' };

console.log('='.repeat(78));
console.log('파종장 씨앗 풀 — 겨루기가 성립하는가 (구별 가능성 계측)');
console.log('='.repeat(78));
console.log(`씨앗 ${N}개 · 잡음 바닥 = 같은 설정 시드만 40회 재추첨\n`);
console.log('특징'.padEnd(12) + '무작위 σ'.padStart(11) + '잡음 σ'.padStart(11)
          + '배수'.padStart(9) + '   판정');
console.log('-'.repeat(78));
const ratios = {};
for (const k of KEYS) {
  const a = sd(seeds.map(x => x.feat), k), b = sd(noise, k);
  const r = b > 1e-9 ? a / b : Infinity;
  ratios[k] = { random_sd: a, noise_sd: b, ratio: r };
  console.log(LABEL[k].padEnd(12) + a.toFixed(2).padStart(11) + b.toFixed(2).padStart(11)
            + (isFinite(r) ? r.toFixed(1) + 'x' : 'inf').padStart(9) + '   '
            + (r >= 2 ? '겨루기에 쓸 수 있다' : '** 잡음에 묻힌다 **'));
}

const out = {
  experiment: 'arena_seed_pool',
  generated_at: new Date().toISOString(),
  note: '유전자 형식은 duet.html SHARE 해시와 동일하다. genome = {p,d,t,g,a,s}',
  axes: AX, materials: MATERIALS,
  material_meta: bank.banks.map((b, i) => ({ idx: i, alpha: b.alpha, K: b.K, zero_rows: b.zero_rows })),
  n_seeds: N, discriminability: ratios,
  noise_floor_design: '설정 고정(p0 d1 t1 g1 a2) · 시드만 40회 재추첨',
  limitation: ('여기서 잰 것은 **계산 가능한 특징의 분산**이지 "다르게 들린다"가 아니다. '
             + '지표가 선호를 예측하지 못한다는 것은 이미 세 계열에서 확인됐다. '
             + '이 계측은 필요조건(공간이 죽어 있지 않다)만 확인한다 — 사람이 듣고 '
             + '구별하는지는 겨루기 데이터가 쌓여야 답할 수 있다.'),
  seeds,
};
const dst = path.join(ROOT, 'arena', 'data', 'seeds.json');
fs.mkdirSync(path.dirname(dst), { recursive: true });
fs.writeFileSync(dst, JSON.stringify(out, null, 1));
console.log(`\n저장: ${dst}`);
