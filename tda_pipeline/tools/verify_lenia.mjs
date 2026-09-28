/* ============================================================================
 * verify_lenia.mjs — Lenia 상호작용 페이지의 규칙·회로·입자 검증 (docs/lenia_spec.md §5)
 *
 * 페이지가 쓰는 **바로 그 파일**(lenia/lenia-core.js + generation-algo1.js)을 Node 에서 돌린다.
 * 조건(arm) 정의도 lenia-core.js 의 LeniaCore.arm() 하나를 페이지와 함께 쓴다.
 *
 * ① JS 규칙 == 파이썬 규칙        tools/verify/lenia_fixture.json (run_lenia_rule.py 가 만든다)
 * ② 하네스 자체 검증              echo 조건 == echo.html → 2026-09-08 세션 기록(시드 11)을 그대로 재현
 * ③ 사전 예측 G1·G2·G3 (+ G1′)     조건 여섯 — 바뀐 것을 하나씩 떼어 본다 (lenia-core.js arm() 주석)
 * ④ 입자                          켜진 고리 쪽으로 끌려도 집에서 15% 넘게 벗어나지 않는가
 *
 * ── 사전 예측과 판정 규칙 — 이 판(2회차)을 돌리기 전에 적었다 ─────────────────────
 * 1회차에서 배운 것 (그대로 남긴다)
 *   · 명세의 사전등록 설정 `lenia`(τ_c · T=25 · uMax 0.688)는 **점 2·4개로는 완전 침묵**이었다.
 *     τ_c(헤드라인, 최대 0.7)와 T=25(원곡 최소 지속 길이)는 **원곡의 조밀한 결**에 맞춘 값인데,
 *     상호작용의 입력은 **성긴 점**이다. 적합과 적용을 다른 자로 쟀다 (CLAUDE.md 교훈 3).
 *     특히 점은 한 주기에 SUS=12 스텝 울리는데 T=25 에서 켜지려면 12.5 스텝이 든다(12×1/25=0.48).
 *   · 추가 예측 L0("T=25 면 점만으로는 영원히 안 켜진다")은 **절반만 맞았다** — 점 2·4 는 침묵,
 *     점 8 은 켜졌다(시차 0·6·12·18 을 둔 점 여럿이 지지를 이어 붙인다).
 *   · 측정 결함 3건: 반올림된 희귀도(점 8개 재현 실패의 원인 → lenia-core.js 수정),
 *     G3 가 침묵한 영역을 "잘 갈렸다"로 셌다(빈 집합 Jaccard=0), G1′ 가 최소 lag 최대값을
 *     진동으로 읽었다(지속성일 뿐). 아래에서 고쳤다.
 *
 * 예측 (조건마다 같은 기준)
 *   G1  점 8개: 마지막 30초 구간 증가율의 절댓값이 echo 보다 작다 (echo 는 계속 자란다)
 *   G2  점 2개: **살아났다가** 사그라진다 — 첫 구간 > 0.5 이고 마지막 구간 < 첫 구간
 *   G3  놓는 자리가 결과를 정한다 — ① 침묵한 영역 수 ≤ echo 의 것, ② 소리 난 영역끼리의
 *       평균 Jaccard ≤ echo + 0.1 (소리 난 영역이 2개 미만이면 실패)
 *   G1′ (보고만) 점 8개 켜진 고리 수의 주기성 — 자기상관이 처음 골을 지난 뒤의 첫 봉우리를
 *       시간 셔플 대조군의 같은 통계와 비교한다
 *
 * 배포 설정 판정 규칙 (결과를 보기 전에 정한다)
 *   `lenia` 가 G1·G2·G3 를 모두 통과하면 `lenia`.
 *   아니면 아래 순서에서 **처음으로 셋을 다 통과하는** 조건:
 *     echo_over → tauc_over → lenia_noover → tauc
 *   순서의 근거: 사용자가 승인한 유일한 상호작용(echo.html)에서 가장 적게 벗어나면서
 *   Lenia 의 성장 창(과소·과밀 양쪽에서 줄어든다)을 넣는 것이 먼저다. 관성(T>1)은 원곡 검증
 *   (run_lenia_rule.py R1 실패, R2 JS +479%)에서 뒷받침이 없었으므로 뒤로 간다.
 *   전부 실패하면 `echo`(검증된 기준선)를 쓰고 그렇게 보고한다.
 *
 * ── 3회차 — 2회차 결과를 **본 뒤에** 추가했다. 숨기지 않는다 ────────────────────
 *   2회차 판정: 여섯 조건 중 G1·G2·G3 를 모두 통과한 것이 없어 규칙대로면 `echo`.
 *   그런데 G1 은 **시드 하나(N=1)** 로 쟀다. 20 시드로 다시 재니(⑤) G1 은 어느 조건도 가려내지 못했다 —
 *   모든 조건의 점 8개 증가율 10~90% 구간이 겹치고 0 을 포함한다. N=1 의 "lenia 0.0% 통과 ·
 *   echo_over 20% 실패" 는 잡음이었다. 반면 G2 는 시드와 무관하게 갈렸다(20/20 vs 0/20).
 *   → 판별력이 없는 G1 을 빼고 **G2(20시드) · G3** 로 같은 순서를 다시 적용한다.
 *     두 판정을 모두 JSON 에 남긴다. 이것은 사전 규칙의 문자 그대로가 아니라 검정력 보정이다
 *     (memory: 역동성 사전등록 — "검정력 계산 누락이 설계 결함" 과 같은 병).
 *   ⚠ 같은 이유로 2026-09-08 세션 기록·CLAUDE.md 의 "점 8개는 자란다(4.5→5.9)" 는 N=1 궤적이다.
 *
 * 실행: node tools/verify_lenia.mjs     산출: docs/step3_data/lenia_generation_results.json
 * ========================================================================= */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = {};
(0, eval)(fs.readFileSync(path.join(ROOT, 'hibari_dashboard/public/js/generation-algo1.js'), 'utf8'));
(0, eval)(fs.readFileSync(path.join(ROOT, 'lenia/lenia-core.js'), 'utf8'));
const G = window.GenerationAlgo1, L = window.LeniaCore;
const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, 'lenia/hibari.json'), 'utf8'));
const K = DATA.K;
const out = { script: 'tools/verify_lenia.mjs', run: 2, run_at: new Date().toISOString(), rule: DATA.rule,
              page_arm_in_code: L.PAGE_ARM };
let fail = 0;
const ok = (c, msg) => { console.log(`${c ? '  PASS' : '  FAIL'}  ${msg}`); if (!c) fail++; return c; };

// ── ① JS 규칙 == 파이썬 규칙 ─────────────────────────────────────────
console.log('① JS 규칙 == 파이썬 규칙 (고정 입력)');
const FX = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools/verify/lenia_fixture.json'), 'utf8'));
out.fixture = [];
for (const cs of FX.cases) {
  const A = new Float64Array(K), om = new Int8Array(K), g = new Int8Array(K);
  let bits = '';
  for (const row of FX.U) { L.leniaStep(A, row, FX.tau, cs.T, cs.u_max, om, g); for (const b of om) bits += b; }
  let same = 0; for (let i = 0; i < bits.length; i++) same += bits[i] === cs.om_bits[i];
  out.fixture.push({ T: cs.T, u_max: cs.u_max, agreement: same / bits.length });
  ok(same === bits.length, `T=${cs.T} u_max=${cs.u_max} : ${same}/${bits.length} 비트 일치`);
}

// ── 공통 — 480스텝 규약 (echo.html 세션과 같다) ─────────────────────────
const ARMS = ['echo', 'tauc', 'lenia_noover', 'lenia', 'tauc_over', 'echo_over'];
function run(arm, drops, { steps = 480, seed = 11 } = {}) {
  const a = L.arm(arm, DATA);
  const e = new L.Engine({ data: DATA, G, tau: a.tau, T: a.T, uMax: a.uMax, rng: G.makeRng(seed) });
  for (const [li, at] of drops) e.addDrop(li, at);
  const f = [];
  const notes = e.advance(steps, (t, ff) => f.push(ff));
  return { e, f, notes };
}
const seg = f => [0, 120, 240, 360].map(a => +(f.slice(a, a + 120).reduce((x, y) => x + y, 0) / 120).toFixed(1));
const summary = r => ({ segments: seg(r.f), silence: r.f.filter(x => !x).length, saturation: r.f.filter(x => x >= 12).length,
                        notes: r.notes.length, pitches: [...new Set(r.notes.map(n => n[1]))].sort((a, b) => a - b) });
const d = (li, at) => [li, at];
const SETS = { '점 1': [d(0, 0)], '점 2': [d(0, 0), d(1, 0)] };
SETS['점 4'] = [...SETS['점 2'], d(2, 6), d(5, 6)];
SETS['점 8'] = [...SETS['점 4'], d(14, 12), d(18, 12), d(20, 18), d(9, 18)];

// ── ② 하네스 자체 검증 ────────────────────────────────────────────────
console.log('\n② 하네스 검증 — echo 조건 == 2026-09-08 세션 기록 (시드 11)');
const RECORD = { '점 1': [0, 0, 0, 0], '점 2': [1.9, 1.8, 1.3, 0.3], '점 4': [4.0, 3.3, 1.7, 2.1], '점 8': [4.5, 4.9, 5.3, 5.9] };
out.harness = {};
for (const [nm, dr] of Object.entries(SETS)) {
  const s = seg(run('echo', dr).f);
  out.harness[nm] = { reproduced: s, recorded: RECORD[nm] };
  ok(JSON.stringify(s) === JSON.stringify(RECORD[nm]), `${nm}  재현 ${s.join(' → ')}   기록 ${RECORD[nm].join(' → ')}`);
}

// ── ③ 조건별 궤적 ────────────────────────────────────────────────────
console.log('\n③ 조건별 켜진 고리 수 (30초 구간 평균, 480스텝 = 2분)');
out.arms = {};
console.log(`  ${'조건'.padEnd(14)} ${'점'.padEnd(5)} ${'고리 궤적'.padEnd(26)} 침묵   포화  음`);
for (const arm of ARMS) {
  out.arms[arm] = {};
  for (const [nm, dr] of Object.entries(SETS)) {
    const s = summary(run(arm, dr)); out.arms[arm][nm] = s;
    console.log(`  ${arm.padEnd(14)} ${nm.padEnd(5)} ${s.segments.join(' → ').padEnd(26)} ${String(s.silence).padStart(3)}  ${String(s.saturation).padStart(4)}  ${String(s.notes).padStart(4)}`);
  }
}

// ── G3 영역 ─────────────────────────────────────────────────────────
const XY = DATA.layout.coords, iso = new Set(DATA.isolated_notes);
const idx = XY.map((_, i) => i).filter(i => !iso.has(i));
const cx = idx.reduce((a, i) => a + XY[i][0], 0) / idx.length, cy = idx.reduce((a, i) => a + XY[i][1], 0) / idx.length;
const sector = i => Math.floor(((Math.atan2(XY[i][1] - cy, XY[i][0] - cx) + Math.PI) / (2 * Math.PI)) * 4) % 4;
const REG = {};
for (let q = 0; q < 4; q++) {
  const mem = idx.filter(i => sector(i) === q);
  const mx = mem.reduce((a, i) => a + XY[i][0], 0) / mem.length, my = mem.reduce((a, i) => a + XY[i][1], 0) / mem.length;
  REG[`영역${q}`] = mem.sort((a, b) => Math.hypot(XY[a][0] - mx, XY[a][1] - my) - Math.hypot(XY[b][0] - mx, XY[b][1] - my)).slice(0, 4);
}
const jac = (a, b) => { const A = new Set(a), B = new Set(b); const i = [...A].filter(x => B.has(x)).length; return i / (A.size + B.size - i || 1); };
function g3(arm) {
  const P = {};
  for (const [nm, lis] of Object.entries(REG)) P[nm] = summary(run(arm, lis.map((li, k) => d(li, k < 2 ? 0 : 6)))).pitches;
  const sounding = Object.keys(P).filter(k => P[k].length), js = [];
  for (let a = 0; a < sounding.length; a++) for (let b = a + 1; b < sounding.length; b++) js.push(jac(P[sounding[a]], P[sounding[b]]));
  return { pitches: P, silent_regions: 4 - sounding.length,
           mean_jaccard_sounding: js.length ? +(js.reduce((x, y) => x + y, 0) / js.length).toFixed(3) : null };
}

// ── 판정 ────────────────────────────────────────────────────────────
const growth = s => (s.segments[3] - s.segments[2]) / Math.max(s.segments[2], 1e-9);
const G3 = Object.fromEntries(ARMS.map(a => [a, g3(a)]));
const gEcho = growth(out.arms.echo['점 8']);
out.verdict = {};
console.log('\n③ 사전 예측 판정 (조건마다)');
console.log(`  ${'조건'.padEnd(14)} ${'G1 점8 증가율'.padEnd(16)} ${'G2 점2 궤적'.padEnd(24)} G3 침묵영역·Jaccard`);
for (const a of ARMS) {
  const g1v = growth(out.arms[a]['점 8']), s2 = out.arms[a]['점 2'].segments, r3 = G3[a];
  const G1ok = a === 'echo' ? null : Math.abs(g1v) < Math.abs(gEcho);
  const G2ok = s2[0] > 0.5 && s2[3] < s2[0];
  const G3ok = r3.mean_jaccard_sounding != null && r3.silent_regions <= G3.echo.silent_regions
               && r3.mean_jaccard_sounding <= G3.echo.mean_jaccard_sounding + 0.1;
  out.verdict[a] = { G1: G1ok, G2: G2ok, G3: G3ok, growth_8: +g1v.toFixed(3), G3_detail: r3 };
  const m = v => v === null ? '  —' : (v ? 'PASS' : 'FAIL');
  console.log(`  ${a.padEnd(14)} ${m(G1ok)} ${((g1v * 100).toFixed(1) + '%').padStart(7)}     ${m(G2ok)} ${s2.join('→').padEnd(18)} ${m(G3ok)} ${r3.silent_regions}개·${r3.mean_jaccard_sounding}`);
}
const passes = a => out.verdict[a].G1 && out.verdict[a].G2 && out.verdict[a].G3;
const ORDER = ['echo_over', 'tauc_over', 'lenia_noover', 'tauc'];
const ruleN1 = passes('lenia') ? 'lenia' : (ORDER.find(passes) || 'echo');
console.log(`\n  ▶ 사전 규칙 그대로 (N=1): ${ruleN1}${passes('lenia') ? '' : '   — 사전등록 설정 lenia 는 통과하지 못했다'}`);

// ── ⑤ 견고성 — 20 시드. G1·G2 가 시드에 따라 흔들리는가 ─────────────────
console.log('\n⑤ 견고성 — 시드 20개 (1000~1019)');
const SEEDS = Array.from({ length: 20 }, (_, i) => 1000 + i);
const qt = (arr, p) => { const s = arr.slice().sort((a, b) => a - b); return s[Math.floor(p * (s.length - 1))]; };
out.robust = {};
for (const a of ARMS) {
  let g2 = 0; const g8 = [], lv8 = [];
  for (const sd of SEEDS) {
    const s2 = seg(run(a, SETS['점 2'], { seed: sd }).f); if (s2[0] > 0.5 && s2[3] < s2[0]) g2++;
    const s8 = seg(run(a, SETS['점 8'], { seed: sd }).f); g8.push(growth({ segments: s8 })); lv8.push(s8[3]);
  }
  out.robust[a] = { G2_pass: g2, n: SEEDS.length, g8_median: +qt(g8, .5).toFixed(3), g8_p10: +qt(g8, .1).toFixed(3),
                    g8_p90: +qt(g8, .9).toFixed(3), level8_median: +qt(lv8, .5).toFixed(2) };
  const r = out.robust[a];
  console.log(`  ${a.padEnd(14)} G2 ${String(g2).padStart(2)}/20   점8 증가율 중앙 ${(r.g8_median * 100).toFixed(1).padStart(5)}% ` +
              `[${(r.g8_p10 * 100).toFixed(0)}%, ${(r.g8_p90 * 100).toFixed(0)}%]   점8 마지막 수준 ${r.level8_median}`);
}
const g1Separates = ARMS.some(a => a !== 'echo' && (out.robust[a].g8_p90 < out.robust.echo.g8_p10 || out.robust[a].g8_p10 > out.robust.echo.g8_p90));
console.log(`  G1 이 20시드에서 어느 조건이든 echo 와 갈리나: ${g1Separates ? '예' : '아니다 — 판별력 없음'}`);
const passesRobust = a => out.robust[a].G2_pass >= 19 && out.verdict[a].G3;
const chosen = passesRobust('lenia') ? 'lenia' : (ORDER.find(passesRobust) || 'echo');
const ca = L.arm(chosen, DATA);
out.page_arm_decision = {
  rule_as_registered_N1: ruleN1, chosen_power_corrected: chosen, g1_discriminates_at_20_seeds: g1Separates,
  rule: 'lenia 가 통과면 lenia, 아니면 ' + ORDER.join(' → ') + ' 중 처음 통과, 전부 실패면 echo',
  correction: 'G1 은 N=1 이라 판별력이 없음을 20시드로 확인 → G2(20시드 중 19 이상) · G3 로 판정',
  user_decision: '처음부터 생성에도 참여 (2026-09-28)',
  chosen_uses_lenia_growth_window: ca.uMax < 1 || ca.T > 1 };
console.log(`\n  ▶ 배포 설정 (검정력 보정): ${chosen}   Lenia 성장 창 사용: ${out.page_arm_decision.chosen_uses_lenia_growth_window ? '예' : '아니오'}`);
ok(L.PAGE_ARM === chosen, `lenia-core.js 의 PAGE_ARM (${L.PAGE_ARM}) == 판정 (${chosen})`);

// ── G1′ 주기성 (보고만) ─────────────────────────────────────────────
function acf(x, lag) {
  const n = x.length, m = x.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) den += (x[i] - m) ** 2;
  for (let i = 0; i + lag < n; i++) num += (x[i] - m) * (x[i + lag] - m);
  return den > 0 ? num / den : 0;
}
function firstPeakAfterTrough(x, maxLag = 200) {
  const a = []; for (let l = 1; l <= maxLag; l++) a.push(acf(x, l));
  let i = 1; while (i < a.length - 1 && !(a[i] < a[i - 1] && a[i] <= a[i + 1])) i++;      // 첫 골
  let best = -1, bl = null;
  for (let j = i + 1; j < a.length - 1; j++) if (a[j] > a[j - 1] && a[j] >= a[j + 1] && a[j] > best) { best = a[j]; bl = j + 1; break; }
  return { lag: bl, value: bl ? +best.toFixed(3) : null };
}
const f8 = run(chosen, SETS['점 8'], { steps: 1920 }).f.slice(240);
const pk = firstPeakAfterTrough(f8);
const rng = G.makeRng(7), nul = [];
for (let k = 0; k < 200; k++) {
  const sh = f8.slice(); for (let i = sh.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [sh[i], sh[j]] = [sh[j], sh[i]]; }
  const p = firstPeakAfterTrough(sh); nul.push(p.value == null ? 0 : p.value);
}
nul.sort((a, b) => a - b);
out.G1prime = { arm: chosen, first_peak_after_trough: pk, shuffle_q95: +nul[189].toFixed(3),
                periodic: pk.value != null && pk.value > nul[189] };
console.log(`\n  G1′ ${chosen} 점 8개 (8분): 첫 골 뒤 첫 봉우리 lag ${pk.lag ?? '—'} = ${pk.lag ? (pk.lag * 0.25).toFixed(1) + '초' : '—'}, ` +
            `${pk.value ?? '—'} (셔플 95% ${nul[189].toFixed(3)}) → ${out.G1prime.periodic ? '주기성 있음' : '주기성 없음'}`);

// ── ④ 입자 — 지도가 무너지지 않는가 (배포 설정) ─────────────────────────
console.log(`\n④ 입자 변위 (점 8개, ${chosen}, 2분, 스텝당 15프레임)`);
const r8 = run(chosen, SETS['점 8']);
const P = { x: Float64Array.from(XY.map(p => p[0])), y: Float64Array.from(XY.map(p => p[1])),
            hx: Float64Array.from(XY.map(p => p[0])), hy: Float64Array.from(XY.map(p => p[1])),
            vx: new Float64Array(XY.length), vy: new Float64Array(XY.length) };
let maxDisp = 0, sumDisp = 0, cnt = 0;
for (let t = 0; t < 480; t++) {
  const A = r8.e.snap[t].A;
  for (let fr = 0; fr < 15; fr++) {
    L.physicsStep(P, A, DATA.cycles, L.PHYS, 1 / 60);
    for (let i = 0; i < XY.length; i++) {
      const dd = Math.hypot(P.x[i] - P.hx[i], P.y[i] - P.hy[i]); maxDisp = Math.max(maxDisp, dd); sumDisp += dd; cnt++;
    }
  }
}
out.particles = { arm: chosen, params: L.PHYS, max_displacement: +maxDisp.toFixed(4), mean_displacement: +(sumDisp / cnt).toFixed(4), bound: 0.15 };
ok(maxDisp <= 0.15, `최대 변위 ${maxDisp.toFixed(3)} ≤ 0.15 (평균 ${(sumDisp / cnt).toFixed(3)}) — 정규화 좌표 기준`);

fs.writeFileSync(path.join(ROOT, 'docs/step3_data/lenia_generation_results.json'), JSON.stringify(out, null, 1));
console.log(`\n${fail ? `✗ 실패 ${fail}건` : '✓ 전부 통과'} — docs/step3_data/lenia_generation_results.json`);
process.exit(fail ? 1 : 0);
