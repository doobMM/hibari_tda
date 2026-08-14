/* ============================================================================
 * verify_js_algo1.mjs — 배포 JS 포트(Algorithm 1)의 인덱스 규약 회귀 테스트
 *
 * 왜 필요한가
 * ───────────
 * `motif-diffusion.js` 는 `docs/js_sampler_parity.md` 로 대조돼 있었지만
 * `generation-algo1.js` 에는 대조가 없었다. 그 공백에서 2026-08-14 까지
 * **인덱스 규약 버그**가 살아남았다 — 풀에 1-indexed `label` 을 넣고
 * `labelToEntryPlus1.get(z+1)`(= 항등 조회)로 디코딩해서, 0-indexed 입력이
 * 들어오는 **intersect 경로**가 한 칸 낮은 음으로 디코딩되고 z=0 은 항상 폐기됐다.
 * 정본 OM(per-cycle τ)은 zero-row 가 0 이라 draw 의 100% 가 intersect 경로다.
 *
 * `debug/diagnose.py` 는 generation 을 import 하지 않아 이 계열을 잡지 못한다.
 * 그래서 **실제 배포 JS 를 그대로 실행**하는 이 하네스를 둔다.
 *
 * 실행:
 *   node tools/verify_js_algo1.mjs            # 현재 코드만
 *   node tools/verify_js_algo1.mjs --with-old # 수정 전 규약도 함께 산출(대조군)
 *   python tools/verify/score_js_algo1.py     # ↑ 산출물을 파이썬 지표로 채점
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');                       // tda_pipeline/
const OUT = path.join(ROOT, 'tools', 'verify');
const SRC = path.join(ROOT, 'hibari_dashboard', 'public', 'js', 'generation-algo1.js');
const withOld = process.argv.includes('--with-old');

const rd = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const DATA = path.join(ROOT, 'hibari_dashboard', 'data');
const meta = rd(path.join(DATA, 'notes_metadata.json'));
const cycMeta = rd(path.join(DATA, 'cycles_metadata.json'));
const contOM = rd(path.join(DATA, 'overlap_matrix_continuous.json'));

// ── 정본 OM: cycle 별 τ 로 이진화 (per-cycle τ) ─────────────────────────────
const T = contOM.T, K = contOM.K;
const taus = cycMeta.cycles.map(c => Number(c.tau));
const values = new Int8Array(T * K);
for (let t = 0; t < T; t++)
  for (let k = 0; k < K; k++)
    values[t * K + k] = contOM.values[t * K + k] >= taus[k] ? 1 : 0;

let zeroRows = 0;
for (let t = 0; t < T; t++) {
  let s = 0;
  for (let k = 0; k < K; k++) s += values[t * K + k];
  if (s === 0) zeroRows++;
}

// ── 규약 검사 ①: 디코딩이 전단사인가 ────────────────────────────────────────
// 0..N-1 이 서로 다른 note 로, 빠짐없이 디코딩돼야 한다.
function decodeContract(G) {
  const pool = new G.NodePool({ labels: meta.labels, numModules: 1, temperature: 1.0,
                                rng: () => 0 });
  const seen = new Map();
  let nulls = 0;
  for (let z = 0; z < meta.labels.length; z++) {
    const e = pool.labelToNoteInfo(z);
    if (!e) { nulls++; continue; }
    seen.set(z, `${e.pitch}/${e.dur}`);
  }
  const distinct = new Set(seen.values()).size;
  // 풀에 들어가는 값도 같은 규약이어야 한다
  const poolRange = [Math.min(...pool.pool), Math.max(...pool.pool)];
  return { nulls, decoded: seen.size, distinct, poolRange };
}

const src = fs.readFileSync(SRC, 'utf8');
const OLD_SRC = src
  .replace('pool.push(n.label_idx);', 'pool.push(n.label);')
  .replace('return this.byIdx.get(label) || null;',
           'for (const e of this.labels) if (e.label === label) return e; return null;');

function load(code) {
  globalThis.window = {};
  // eslint-disable-next-line no-eval
  (0, eval)(code);
  return globalThis.window.GenerationAlgo1;
}

const SEEDS = Array.from({ length: 20 }, (_, i) => 1000 + 37 * i);
const variants = withOld ? [['after', src], ['before', OLD_SRC]] : [['after', src]];
if (withOld && OLD_SRC === src) {
  console.error('대조군 생성 실패 — 소스 문자열이 바뀌었다. 이 스크립트를 갱신할 것.');
  process.exit(1);
}

fs.mkdirSync(OUT, { recursive: true });
console.log(`정본 OM(per-cycle τ): T=${T} K=${K} zero-row=${zeroRows}/${T}` +
            `  → 풀 경로 노출 ${(100 * zeroRows / T).toFixed(2)}%`);

let failed = false;
for (const [tag, code] of variants) {
  const G = load(code);
  const c = decodeContract(G);
  const ok = c.nulls === 0 && c.decoded === meta.labels.length &&
             c.distinct === meta.labels.length &&
             c.poolRange[0] === 0 && c.poolRange[1] === meta.labels.length - 1;
  console.log(`[${tag}] 디코딩 계약: null=${c.nulls} 해독=${c.decoded}/${meta.labels.length} ` +
              `고유=${c.distinct} 풀범위=[${c.poolRange}]  → ${ok ? 'PASS' : 'FAIL'}`);
  if (tag === 'after' && !ok) failed = true;

  const instLen = G.buildHibariInstLen(T);
  const runs = [];
  for (const s of SEEDS) {
    const rng = G.makeRng(s);
    const pool = new G.NodePool({ labels: meta.labels, numModules: 65, temperature: 1.0, rng });
    const mgr = new G.CycleSetManager({ cycles: cycMeta.cycles, K });
    runs.push(G.algorithm1({ nodePool: pool, cycleManager: mgr, instLen,
                             overlap: { T, K, values }, maxResample: 50, rng }).notes);
  }
  fs.writeFileSync(path.join(OUT, `js_algo1_notes_${tag}.json`), JSON.stringify(runs));
  console.log(`         ${runs.length}시드 · 평균 음 수 ` +
              `${(runs.reduce((a, r) => a + r.length, 0) / runs.length).toFixed(0)}` +
              ` → tools/verify/js_algo1_notes_${tag}.json`);
}

console.log('\n다음: python tools/verify/score_js_algo1.py');
process.exit(failed ? 1 : 0);
