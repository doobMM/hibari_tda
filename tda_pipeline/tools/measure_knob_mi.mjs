/* ============================================================================
 * measure_knob_mi.mjs — 손잡이마다 **설정을 여러 눈금으로 쓸어** 원자료를 남긴다
 *
 * 왜 새로 만드나. `measure_knob_liveness.mjs` 는 손잡이의 **양 끝 두 점**만 비교한다.
 * 그래서 "반응했다 / 안 했다"는 갈라도 **"반응에 방향이 있나"**는 못 가른다.
 * α 가 정확히 그 칸에 걸려 있다 — 음역폭이 12.75→14.10→12.65→13.10→11.92→13.45 로
 * 오르내린다. 두 점만 보면 "거의 안 변함"으로 읽히고, 여섯 점을 보면 "많이 변하는데
 * 방향이 없음"으로 읽힌다. **다른 판정이다.**
 *
 * 이 스크립트는 채점하지 않는다. 눈금 × 시드 격자를 돌려 **특징만 덤프**한다.
 * 상호정보량·순열 귀무·Spearman 은 `experiments/run_knob_mi.py` 가 계산한다.
 * (지표를 계산하는 쪽과 생성하는 쪽을 분리해야 지표를 바꿔도 재생성이 필요 없다)
 *
 * 생성 경로는 **배포된 duet.html 과 동일**하다 — 같은 om_bank, 같은 numModules=65,
 * 같은 buildHibariInstLen, 같은 사후 이조·길이 배율. 딴 데서 잰 숫자를 쓰지 않는다.
 *
 * 실행:  node tools/measure_knob_mi.mjs
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

/** duet.html build() 과 같은 순서로 한 조각을 만든다. */
function gen({ a = 2, shift = 0, density = 1, glue = 1,
               temperature = 1, pitchTilt = 0, numModules = 65 }, seed) {
  const b = bank.banks[a], T = b.T;
  const cyc = b.cycles.map((c, i) => ({ cycle_idx: i, note_labels_0idx: c }));
  const base = G.buildHibariInstLen(T), len = new Int32Array(T);
  for (let i = 0; i < T; i++) len[i] = Math.max(0, Math.round(base[i] * density));
  const rng = G.makeRng(seed);
  const r = G.algorithm1({
    nodePool: new G.NodePool({ labels: meta.labels, numModules, temperature, pitchTilt, rng }),
    cycleManager: new G.CycleSetManager({ cycles: cyc, K: b.K }),
    instLen: len, overlap: { T, K: b.K, values: bits(b.om_bits, T * b.K) },
    maxResample: 50, rng,
  });
  const ns = r.notes.map(n => {
    const d = Math.max(1, Math.round((n[2] - n[0]) * glue));
    return [n[0], n[1] + shift, Math.min(T, n[0] + d)];
  });
  if (!ns.length) return { n: 0, meanPitch: 0, pitchRange: 0, avgLen: 0 };
  const ps = ns.map(x => x[1]);
  return {
    n: ns.length,
    meanPitch: ps.reduce((x, y) => x + y, 0) / ns.length,
    pitchRange: Math.max(...ps) - Math.min(...ps),
    avgLen: ns.reduce((s, x) => s + (x[2] - x[0]), 0) / ns.length,
  };
}

const lin = (lo, hi, L) => Array.from({ length: L }, (_, i) => lo + (hi - lo) * i / (L - 1));
const A_CANON = 2;   // α=0.25 — 정본, zero_rows=0 (풀 경로 닫힘)
const A_OPEN  = 0;   // α=0.0  — zero_rows=65/120 (풀 경로 열림)

/* 눈금은 duet.html 의 실제 슬라이더 범위를 쓴다. 임의로 넓히지 않는다. */
const KNOBS = [
  { id: 'alpha',        label: 'α (MATERIAL)',        levels: [0, 1, 2, 3, 4, 5],
    note: 'om_bank 6단. 눈금은 α=0/0.1/0.25/0.5/0.75/0.95',
    make: v => ({ a: v }) },
  { id: 'density',      label: '밀도 DENSITY',         levels: lin(0.4, 2.2, 6),
    note: 'duet.html AX[1] 범위', make: v => ({ a: A_CANON, density: v }) },
  { id: 'pitch',        label: '높낮이 PITCH (사후 이조)', levels: lin(-12, 12, 6),
    note: '자명하게 단조여야 한다 — MI 추정기의 양성 대조',
    make: v => ({ a: A_CANON, shift: Math.round(v) }) },
  { id: 'length',       label: '음 길이 LENGTH',        levels: lin(0.4, 3.0, 6),
    note: 'duet.html AX[3] 범위', make: v => ({ a: A_CANON, glue: v }) },
  { id: 'temperature',  label: '온도 (정본 α=0.25)',    levels: lin(1, 5, 6),
    note: 'zero_rows=0 → 풀 경로가 닫혀 있다', make: v => ({ a: A_CANON, temperature: v }) },
  { id: 'pitchTilt',    label: '음역 pitchTilt (정본)',  levels: lin(0, 2, 6),
    note: 'zero_rows=0 → 풀 경로가 닫혀 있다', make: v => ({ a: A_CANON, pitchTilt: v }) },
  { id: 'temperature_open', label: '온도 (α=0, 풀 열림)', levels: lin(1, 5, 6),
    note: 'zero_rows=65/120 → 여기서는 살아 있어야 한다 (양성 대조)',
    make: v => ({ a: A_OPEN, temperature: v }) },
  { id: 'pitchTilt_open',   label: '음역 pitchTilt (α=0, 풀 열림)', levels: lin(0, 2, 6),
    note: 'zero_rows=65/120 → 여기서는 살아 있어야 한다 (양성 대조)',
    make: v => ({ a: A_OPEN, pitchTilt: v }) },
  /* 귀무 개입 — 의미는 안 바뀌고 난수 소비만 바뀐다. MI 추정 편향의 바닥. */
  { id: 'null_numModules', label: '귀무: numModules 60→65', levels: [60, 61, 62, 63, 64, 65],
    note: '풀 길이만 변한다. 상대 빈도·의미 불변 → MI 는 0 이어야 한다',
    make: v => ({ a: A_CANON, numModules: v }) },
];

const NSEED = 60;
const SEEDS = Array.from({ length: NSEED }, (_, i) => 3000 + 17 * i);  // 눈금마다 같은 시드(paired)

const t0 = Date.now();
const out = {
  experiment: 'knob_mi_sweep',
  generated_at: new Date().toISOString(),
  source: 'tools/measure_knob_mi.mjs — 배포된 generation-algo1.js 를 node 에서 그대로 실행',
  bank_source: bank.source, step_ms: bank.step_ms,
  banks: bank.banks.map(b => ({ alpha: b.alpha, K: b.K, T: b.T, zero_rows: b.zero_rows })),
  n_seeds: NSEED, n_levels: 6, seeds: SEEDS,
  features: ['n', 'meanPitch', 'pitchRange', 'avgLen'],
  knobs: [],
};

for (const k of KNOBS) {
  const rows = [];
  for (const v of k.levels)
    for (const s of SEEDS) rows.push({ level: v, seed: s, ...gen(k.make(v), s) });
  const sigs = new Set(rows.map(r => `${r.n}|${r.meanPitch}|${r.pitchRange}|${r.avgLen}`));
  out.knobs.push({ id: k.id, label: k.label, note: k.note, levels: k.levels,
                   distinct_outputs: sigs.size, n_rows: rows.length, rows });
  console.log(`${k.id.padEnd(20)} ${rows.length}행  서로 다른 출력 ${sigs.size}`);
}

const dst = path.join(ROOT, 'docs', 'step3_data', 'knob_mi_sweep.json');
fs.writeFileSync(dst, JSON.stringify(out));
console.log(`\n${((Date.now() - t0) / 1000).toFixed(1)}s · 저장: ${dst}`);
