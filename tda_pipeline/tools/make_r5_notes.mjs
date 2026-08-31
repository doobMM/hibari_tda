/* ============================================================================
 * make_r5_notes.mjs — R5 판별 회차 자극 생성. **배포 JS 를 그대로 돌린다**
 *
 * 왜 JS 인가
 * ─────────
 * 이번 회차가 묻는 것은 "지표가 옳은가"가 아니라 **"내가 만진 손잡이가 들리는가"** 다.
 * 그러면 시험 대상은 파이썬 정본이 아니라 **사용자가 실제로 만지는 배포 코드**다.
 * `pitchTilt` 는 애초에 JS 에만 있다. 그래서 음은 여기서 만들고 렌더만 파이썬이 한다.
 *
 * 설계 — 선호가 아니라 **정답이 있는 판별**을 묻는다
 * ────────────────────────────────────────────
 * 선호("어느 쪽이 좋나")는 정답이 없어 61% 참 일치율 기준 74쌍이 필요하다.
 * 판별("어느 쪽이 더 촘촘한가")은 **정답이 있어** 80% 면 9쌍으로 끝난다.
 * 그리고 판별이야말로 "의도대로 만드는 감각"의 정의다.
 *
 * 12쌍 = 밀도 3 + 음역 3 + 온도 3 + **귀무 3**
 *   · 세기를 3단계로 벌려 **어디서부터 들리는지(역치)** 를 본다. 슬라이더 눈금이 그 결과다.
 *   · 귀무 3쌍은 **시드만 다르고 설정이 같다.** 여기서도 맞힌다고 답하면
 *     그 질문 자체가 무의미하다는 뜻이다 — 청취 실험 안에 넣는 대조군이다.
 *
 * 온도·음역은 풀 경로가 열려야 작동하므로(`knob_liveness.json`) 그 팔만
 * **τ=0.7 로 성글게 만든 OM** 을 쓴다. 사용자가 셀을 지웠을 때의 실제 상태다.
 *
 * 실행:  node tools/make_r5_notes.mjs   → tools/verify/r5_notes.json
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
const om = (f, off) => {
  const v = new Int8Array(SEG * K);
  for (let t = 0; t < SEG; t++)
    for (let k = 0; k < K; k++) v[t * K + k] = f(cont.values[(off + t) * K + k], k);
  return v;
};
const DENSE = off => om((x, k) => x >= taus[k] ? 1 : 0, off);   // 정본 — 밀도만 작동
const SPARSE = off => om(x => x >= 0.7 ? 1 : 0, off);           // 성글게 — 셋 다 작동

const BASE_LEN = G.buildHibariInstLen(1088);
const applyDensity = (len, f) => {
  if (Math.abs(f - 1) < 1e-6) return len;
  const o = new Int32Array(len.length);
  for (let i = 0; i < len.length; i++) o[i] = Math.max(0, Math.round(len[i] * f));
  return o;
};

function gen(values, off, { temperature = 1, pitchTilt = 0, density = 1 }, seed) {
  const rng = G.makeRng(seed);
  const pool = new G.NodePool({ labels: meta.labels, numModules: 65,
                                temperature, pitchTilt, rng });
  const notes = G.algorithm1({
    nodePool: pool,
    cycleManager: new G.CycleSetManager({ cycles: cycMeta.cycles, K }),
    instLen: applyDensity(BASE_LEN.slice(off, off + SEG), density),
    overlap: { T: SEG, K, values }, maxResample: 50, rng }).notes;
  const mp = notes.length ? notes.reduce((a, n) => a + n[1], 0) / notes.length : 0;
  return { notes, n: notes.length, meanPitch: mp };
}

// ── pitchTilt 를 반음 단위로 보정한다 (슬라이더 눈금을 정하려면 물리량이 필요하다) ──
const CAL_SEEDS = Array.from({ length: 24 }, (_, i) => 8000 + 31 * i);
function tiltToSemitones(tilt, off) {
  const v = SPARSE(off);
  const a = CAL_SEEDS.map(s => gen(v, off, {}, s).meanPitch);
  const b = CAL_SEEDS.map(s => gen(v, off, { pitchTilt: tilt }, s).meanPitch);
  return b.reduce((x, y) => x + y, 0) / b.length - a.reduce((x, y) => x + y, 0) / a.length;
}
console.log('■ pitchTilt 보정 (창 off=0, 24시드 평균 음고 차, 반음)');
const TILT_CAL = {};
for (const t of [0.25, 0.5, 1.0, 1.5, 2.0]) {
  TILT_CAL[t] = tiltToSemitones(t, 0);
  console.log(`   tilt ${t.toFixed(2)} → ${TILT_CAL[t] >= 0 ? '+' : ''}${TILT_CAL[t].toFixed(2)} 반음`);
}

// ── 12쌍 ────────────────────────────────────────────────────────────────
// 세기 3단계: 약 / 중 / 강. 역치가 그 사이 어디인지 본다.
const PAIRS = [
  // 밀도 — 정본 OM 에서도 항상 작동하는 유일한 축
  ['density', '어느 쪽이 음이 더 많고 촘촘한가요?', DENSE,   0, { density: 1.0 }, { density: 1.15 }, '약 (×1.15)'],
  ['density', '어느 쪽이 음이 더 많고 촘촘한가요?', DENSE, 192, { density: 1.0 }, { density: 1.4 },  '중 (×1.4)'],
  ['density', '어느 쪽이 음이 더 많고 촘촘한가요?', DENSE, 384, { density: 1.0 }, { density: 2.0 },  '강 (×2.0)'],
  // 음역 — 풀이 열려야 작동한다
  ['register', '어느 쪽이 더 높게 들리나요?', SPARSE,   0, { pitchTilt: 0 }, { pitchTilt: 0.25 }, '약'],
  ['register', '어느 쪽이 더 높게 들리나요?', SPARSE, 192, { pitchTilt: 0 }, { pitchTilt: 1.0 },  '중'],
  ['register', '어느 쪽이 더 높게 들리나요?', SPARSE, 384, { pitchTilt: 0 }, { pitchTilt: 2.0 },  '강'],
  // 온도 — 실측상 하는 일은 '음 줄이기'다. 이름이 약속하는 다양성이 아니다.
  ['temperature', '두 개가 서로 다르게 들리나요? 다르다면 어느 쪽이 더 성긴가요?', SPARSE,   0, { temperature: 1 }, { temperature: 2 }, '약 (T=2)'],
  ['temperature', '두 개가 서로 다르게 들리나요? 다르다면 어느 쪽이 더 성긴가요?', SPARSE, 192, { temperature: 1 }, { temperature: 3 }, '중 (T=3)'],
  ['temperature', '두 개가 서로 다르게 들리나요? 다르다면 어느 쪽이 더 성긴가요?', SPARSE, 384, { temperature: 1 }, { temperature: 5 }, '강 (T=5)'],
  // 귀무 — 시드만 다르다. 여기서 맞히면 질문이 무의미하다는 신호다.
  ['null', '어느 쪽이 음이 더 많고 촘촘한가요?', DENSE,   0, { density: 1.0 }, { density: 1.0 }, '귀무 (시드만 다름)'],
  ['null', '어느 쪽이 더 높게 들리나요?', SPARSE, 192, { pitchTilt: 0 }, { pitchTilt: 0 }, '귀무 (시드만 다름)'],
  ['null', '두 개가 서로 다르게 들리나요? 다르다면 어느 쪽이 더 성긴가요?', SPARSE, 384, { temperature: 1 }, { temperature: 1 }, '귀무 (시드만 다름)'],
];

// ── 시드만 재추첨했을 때의 폭 — 이것이 **잡음 바닥**이다 ─────────────────
// 손잡이의 효과가 이 폭보다 작으면 그것은 조작이 아니라 잡음이다.
// (첫 시도에서 실제로 걸렸다: 귀무 쌍의 음 수 차 −19 가 온도 개입 −20 과 맞먹었다.)
const NOISE_SEEDS = Array.from({ length: 60 }, (_, i) => 21000 + 7 * i);
const sdev = a => {
  const m = a.reduce((x, y) => x + y, 0) / a.length;
  return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1));
};
console.log('\n■ 잡음 바닥 — 시드만 바꿨을 때의 표준편차 (60시드)');
const NOISE = {};
for (const [nm, omf] of [['정본', DENSE], ['성긴 τ=0.7', SPARSE]]) {
  for (const off of [0, 192, 384]) {
    const v = omf(off);
    const r = NOISE_SEEDS.map(s2 => gen(v, off, {}, s2));
    NOISE[`${nm}|${off}`] = { n: sdev(r.map(x => x.n)),
                              meanPitch: sdev(r.map(x => x.meanPitch)) };
    console.log(`   ${nm.padEnd(10)} off=${String(off).padStart(3)}  ` +
                `음 수 σ=${NOISE[`${nm}|${off}`].n.toFixed(1).padStart(5)}  ` +
                `평균음고 σ=${NOISE[`${nm}|${off}`].meanPitch.toFixed(2)}`);
  }
}

// ── 귀무 쌍은 **차이가 0 에 가까운** 시드 짝을 골라야 한다 ─────────────────
function pickNullPair(values, off, key) {
  let best = null;
  for (let i = 0; i < NOISE_SEEDS.length; i++)
    for (let j = i + 1; j < NOISE_SEEDS.length; j++) {
      const a = gen(values, off, {}, NOISE_SEEDS[i]);
      const b = gen(values, off, {}, NOISE_SEEDS[j]);
      const d = Math.abs(b[key] - a[key]);
      if (!best || d < best.d) best = { d, sa: NOISE_SEEDS[i], sb: NOISE_SEEDS[j] };
      if (best.d === 0) return best;
    }
  return best;
}

const SEED_A = 5100, SEED_B = 5200;
const truthKey = { density: 'n', register: 'meanPitch', temperature: 'n', null: 'n' };
const higherIsTarget = { density: true, register: true, temperature: false, null: null };
const nullKey = ['n', 'meanPitch', 'n'];   // D10 밀도 · D11 음역 · D12 온도 질문에 맞춘 지표

// A/B 배치를 뒤집어 **정답이 한쪽으로 쏠리지 않게** 한다.
// 첫 시도에서 12쌍 전부 정답이 B 였다 — 늘 B 만 눌러도 만점이었다.
const FLIP = [false, true, false, true, true, false, true, false, true, false, true, false];

const out = [];
let nullIdx = 0;
console.log('\n■ 12쌍 생성');
console.log(`${'쌍'.padEnd(5)} ${'축'.padEnd(12)} ${'세기'.padEnd(20)} ${'창'.padStart(4)} ` +
            `${'A'.padStart(8)} ${'B'.padStart(8)} ${'차이'.padStart(8)} ${'잡음σ배'.padStart(8)}  정답`);
PAIRS.forEach((p, i) => {
  const [fam, question, omf, off, optA, optB, strength] = p;
  const values = omf(off);
  const key = fam === 'null' ? nullKey[nullIdx] : truthKey[fam];
  const scenName = omf === DENSE ? '정본' : '성긴 τ=0.7';
  const sigma = NOISE[`${scenName}|${off}`][key];

  let lo, hi, seedLo, seedHi;
  if (fam === 'null') {
    const pick = pickNullPair(values, off, key);
    nullIdx++;
    seedLo = pick.sa; seedHi = pick.sb;
    lo = gen(values, off, optA, seedLo);
    hi = gen(values, off, optB, seedHi);
  } else {
    seedLo = SEED_A + i; seedHi = SEED_B + i;
    lo = gen(values, off, optA, seedLo);
    hi = gen(values, off, optB, seedHi);
  }

  // 개입 팔(hi)이 정답인 방향을 먼저 정하고, 그다음 A/B 를 뒤집는다
  const truth = fam === 'null' ? null
    : (higherIsTarget[fam] ? (hi[key] > lo[key] ? 'hi' : 'lo')
                           : (hi[key] < lo[key] ? 'hi' : 'lo'));
  const flip = FLIP[i];
  const A = flip ? hi : lo, B = flip ? lo : hi;
  const sA = flip ? seedHi : seedLo, sB = flip ? seedLo : seedHi;
  const truthAB = truth === null ? null
    : ((truth === 'hi') === !flip ? 'B' : 'A');
  const d = B[key] - A[key];

  out.push({ id: `D${i + 1}`, family: fam, question, strength, window: off,
             optA: flip ? optB : optA, optB: flip ? optA : optB,
             seedA: sA, seedB: sB, metric: key,
             valueA: A[key], valueB: B[key], delta: d,
             noise_sigma: sigma, effect_in_sigma: sigma ? Math.abs(d) / sigma : null,
             truth: truthAB, notesA: A.notes, notesB: B.notes, nA: A.n, nB: B.n });
  console.log(`${('D' + (i + 1)).padEnd(5)} ${fam.padEnd(12)} ${strength.padEnd(20)} ` +
              `${String(off).padStart(4)} ${A[key].toFixed(2).padStart(8)} ` +
              `${B[key].toFixed(2).padStart(8)} ${((d >= 0 ? '+' : '') + d.toFixed(2)).padStart(8)} ` +
              `${(sigma ? (Math.abs(d) / sigma).toFixed(1) : '—').padStart(8)}  ` +
              `${truthAB || '— (정답 없음)'}`);
});

console.log(`\n정답 분포: A ${out.filter(o => o.truth === 'A').length} · ` +
            `B ${out.filter(o => o.truth === 'B').length} · 정답없음 ` +
            `${out.filter(o => o.truth === null).length}`);

fs.mkdirSync(path.join(ROOT, 'tools', 'verify'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'tools', 'verify', 'r5_notes.json'),
  JSON.stringify({ generator: 'hibari_dashboard/public/js/generation-algo1.js (배포본)',
                   segment_T: SEG, tilt_calibration_semitones: TILT_CAL,
                   noise_floor_sd: NOISE, pairs: out }, null, 1), 'utf8');
console.log('\n저장: tools/verify/r5_notes.json  →  다음: python listening_test/make_ab_r5.py');
