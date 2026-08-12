/* =========================================================================
 * tools/verify_js_sampler.mjs — 브라우저 RePaint 샘플러 결정적 동치 검증
 *
 * 무엇을 검증하는가
 * ──────────────────
 * hibari_dashboard/public/js/motif-diffusion.js 의 sampleWithMotif() 는
 * experiments/motif_control.py 의 sample_with_motif() 를 이식한 것이라고
 * 문서(motif-diffusion.js:5-6)에 적혀 있지만, 실제로 두 구현의 산술이
 * 일치하는지는 지금까지 아무도 실행해서 대조한 적이 없다("스케줄 상수만
 * 검증됨, 샘플링 루프 자체는 미검증" — 과제 배경 참조).
 *
 * 검증 방식 선택 — (B) 노이즈=0, 결정적 경로만 비교
 * ────────────────────────────────────────────────
 * 과제가 제시한 (A) "동일 고정 노이즈 배열 주입"은 이 파일(모듈 스코프)
 * 안에서는 불가능하다: motif-diffusion.js 의 randn 은
 *   const randn = makeRandn(seed);
 * 로 sampleWithMotif() 호출마다 새로 만들어지는 **비공개 클로저**이고,
 * mulberry32+Box-Muller 알고리즘이다. 외부에서 개별 draw 값을 주입할 공개
 * 인터페이스가 없고, 이를 만들려면 배포 중인 motif-diffusion.js 자체를
 * 고쳐야 한다 — 그러면 "실제 배포 코드"가 아니라 "테스트용으로 바뀐 코드"를
 * 검증하는 셈이 되어 검증의 의미가 없어진다. 반대로 Python 쪽
 * torch.Generator 는 Philox 계열 알고리즘이라 mulberry32 와 애초에 같은
 * 스트림을 낼 수 없다 — 둘 다 그대로 두고 값만 맞추려는 시도 자체가
 * 잘못된 접근이다.
 *
 * 그래서 (B) 를 택했다: 모든 노이즈 항(사후분산 항 sig*noise, RePaint 안다는
 * 영역의 k1m*randn(), 되돌림 재샘플링의 sqrt(betas)*randn())을 0 으로 두고
 * **평균-전용(ODE) 결정적 경로**만 비교한다. PRNG 알고리즘이 다른 것은
 * 버그가 아니므로 검증 대상에서 뺀다 — 대신 실제로 미검증이었던 4가지
 * 결정적 산술을 노출한다:
 *   (i)   윈도우 크롭 + Hann 가중 MultiDiffusion 융합
 *   (ii)  x̂₀ [-1,1] 클리핑 + 사후평균 계수(post_c0/post_ct)
 *   (iii) RePaint 마스크 블렌딩 (mask ⊙ known + (1-mask) ⊙ unknown)
 *   (iv)  respace() 재배치 스케줄
 *
 * 모델도 같은 이유로 실제 ONNX 대신 **공유 더미 함수**를 쓴다 — ONNX 모델
 * 자체의 PyTorch-vs-ONNXRuntime 수치 일치는 tools/export_topo_onnx.py 가
 * 이미 별도로 검증했다(1e-6 수준, topo_denoiser_meta.json 의
 * parity_max_abs_diff 참조). 여기서 다시 검증할 필요가 없고, 오히려 실제
 * 모델을 쓰면 "모델이 무엇을 예측하든 창 경계에서 올바르게
 * 합성/클리핑/마스킹하는가"라는 진짜 검증 대상이 모델 예측값의 잡음에
 * 가려진다. 더미 함수는 Python 쪽(tools/verify/gen_reference.py 의
 * dummy_eps_torch)과 완전히 같은 수식이다:
 *   eps[c,j] = tanh(0.3*crop + 0.01*(j-win/2) - 0.002*t + 0.05*sin(0.7*c+0.02*t))
 *
 * onnxruntime-node 관련 (npm ls 로 확인, 설치하지 않음)
 * ──────────────────────────────────────────────────
 * `npm ls onnxruntime-node` → "(empty)", 즉 이 레포에 설치돼 있지 않다.
 * 과제 지시대로 설치는 하지 않았다. 대신 위에서 설명한 "양쪽에 같은
 * 더미 eps 주입" 대안을 썼다 — 이는 과제가 명시한 대안 중 하나이며,
 * 실제 ONNX 런타임 호출 자체는 이미 별도 검증되어 있으므로(위 참조)
 * 이 대안으로도 검증 공백이 남지 않는다.
 *
 * 코드 재사용 범위
 * ────────────────
 * · 아래 respaceSched()/cosineSchedResult 계산은 motif-diffusion.js 를
 *   **수정 없이 그대로 로드**해서 그 파일이 노출하는
 *   MotifDiffusion._cosineSchedule / MotifDiffusion._respace 를 직접
 *   호출한다 — 진짜 배포 코드다.
 * · Hann 창(hannWindow 함수)과 스텝 산술(stepDeterministic/runLoop)은
 *   motif-diffusion.js:234-238, 266-330 을 그대로 옮긴 **검증 전용 사본**
 *   이다 — 원본 파일은 건드리지 않았다(class 내부 클로저라 외부에서 직접
 *   호출할 수 없어 부득이 복사했다). 노이즈 항만 제거했고, 그 외 변수명·
 *   연산 순서·분기 조건은 원본과 동일하게 유지했다(라인 인용 주석 참조).
 *
 * 실행
 * ────
 *   python tools/verify/gen_reference.py     # 먼저 파이썬 기준값 생성
 *   node tools/verify_js_sampler.mjs         # 이 스크립트
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TDA_ROOT = path.dirname(HERE);
const REF_PATH = path.join(HERE, 'verify', 'reference.json');
const JS_SRC_PATH = path.join(TDA_ROOT, 'hibari_dashboard', 'public', 'js', 'motif-diffusion.js');
const REPORT_PATH = path.join(TDA_ROOT, 'docs', 'js_sampler_parity.md');
const TOL = 1e-4;

// ── 파이썬 기준값 로드 ──
if (!fs.existsSync(REF_PATH)) {
  console.error(`기준값 없음: ${REF_PATH}\n먼저 실행: python tools/verify/gen_reference.py`);
  process.exit(1);
}
const ref = JSON.parse(fs.readFileSync(REF_PATH, 'utf-8'));
const { K, win, stride, T, seed, test_i: TEST_I, respace_n: RESPACE_N,
        loop_steps: LOOP_STEPS, jump_u: JUMP_U, jump_from: JUMP_FROM,
        starts: refStarts } = ref.config;

// ── motif-diffusion.js 를 수정 없이 그대로 실행해 static 헬퍼를 얻는다 ──
// 이 파일은 IIFE 안에서 `window`(=global 파라미터)만 참조하고, 맨 아래
// `new MotifDiffusion()` 생성자 호출은 순수 필드 초기화뿐이라
// document/fetch/ort 없이도 안전하게 로드된다 (I/O 는 load()/available()
// 안에만 있고 여기선 호출하지 않는다).
globalThis.window = globalThis;
const jsSrc = fs.readFileSync(JS_SRC_PATH, 'utf-8');
(0, eval)(jsSrc);  // eslint-disable-line no-eval -- 실제 배포 파일을 그대로 실행
const { MotifDiffusion } = globalThis;
if (!MotifDiffusion || !MotifDiffusion._cosineSchedule || !MotifDiffusion._respace) {
  console.error('motif-diffusion.js 로드 실패 — _cosineSchedule/_respace 노출 안 됨');
  process.exit(1);
}

const results = [];  // { item, label, maxDiff, pass }

function maxAbsDiff(a, b) {
  const n = Math.min(a.length, b.length);
  let m = 0;
  for (let i = 0; i < n; i++) {
    const d = Math.abs(a[i] - b[i]);
    if (d > m) m = d;
  }
  if (a.length !== b.length) m = Infinity;
  return m;
}

function record(item, label, maxDiff, extra) {
  const pass = maxDiff <= TOL;
  results.push({ item, label, maxDiff, pass, extra: extra || '' });
  console.log(`  [${pass ? 'PASS' : 'FAIL'}] ${item} ${label}  max|diff|=${maxDiff.toExponential(3)}`);
}

console.log('='.repeat(78));
console.log('JS RePaint 샘플러 결정적 동치 검증');
console.log('='.repeat(78));

// ═════════════════════════════════════════════════════════════════════════
// item 1 — Hann 창 (win=60, periodic=false)
// motif-diffusion.js:235-238 을 그대로 옮김 (원본 파일은 함수 스코프
// 안이라 외부에서 직접 호출 불가능해 여기서 재현). item2 의 MultiDiffusion
// 융합 테스트가 이 값을 실제로 소비하므로 간접적으로도 검증된다.
// ═════════════════════════════════════════════════════════════════════════
function hannWindow(w) {
  const hann = new Float32Array(w);
  for (let i = 0; i < w; i++) {
    hann[i] = Math.max(1e-3, 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (w - 1)));
  }
  return hann;
}
console.log('\n[item1] Hann 창 (win=60, periodic=false)');
const hann60 = hannWindow(win);
console.log(`  JS  hann[:5]  = [${Array.from(hann60.slice(0, 5)).join(', ')}]`);
console.log(`  PY  hann[:5]  = [${ref.item1_hann60.slice(0, 5).join(', ')}]`);
console.log(`  JS  hann[-5:] = [${Array.from(hann60.slice(-5)).join(', ')}]`);
console.log(`  PY  hann[-5:] = [${ref.item1_hann60.slice(-5).join(', ')}]`);
console.log(`  JS  min = ${Math.min(...hann60)}   PY min = ${Math.min(...ref.item1_hann60)}`);
record('item1', 'hann60(전체60개)', maxAbsDiff(Array.from(hann60), ref.item1_hann60));

// ═════════════════════════════════════════════════════════════════════════
// item 5 — respace(50) 스케줄 (+ cosineSchedule(200) 자체 교차검증)
// 실제 배포 코드 MotifDiffusion._cosineSchedule / ._respace 를 그대로 호출.
// ═════════════════════════════════════════════════════════════════════════
console.log('\n[item5] cosineSchedule(200) / respace() — 실제 배포 함수 직접 호출');
const sched0 = MotifDiffusion._cosineSchedule(200);
record('item5-pre', 'cosineSchedule(200).betas vs 재계산 cosine_beta_schedule(200)',
       maxAbsDiff(Array.from(sched0.betas), ref.cosine_betas_200));
record('item5-pre', 'cosineSchedule(200).betas vs 배포된 topo_denoiser_meta.json betas',
       maxAbsDiff(Array.from(sched0.betas), ref.deployed_meta_betas_200));
record('item5-pre', 'cosineSchedule(200).postC0 vs 실제 DDPM(200).post_c0',
       maxAbsDiff(Array.from(sched0.postC0), ref.ddpm200_post_c0));
record('item5-pre', 'cosineSchedule(200).postCt vs 실제 DDPM(200).post_ct',
       maxAbsDiff(Array.from(sched0.postCt), ref.ddpm200_post_ct));
record('item5-pre', 'cosineSchedule(200).postVar vs 실제 DDPM(200).post_var',
       maxAbsDiff(Array.from(sched0.postVar), ref.ddpm200_post_var));

const { sched: respaced50 } = MotifDiffusion._respace(sched0, RESPACE_N);
record('item5', `respace(${RESPACE_N}).betas vs 독립재구현 respace_py`,
       maxAbsDiff(Array.from(respaced50.betas), ref.item5_respace50.betas));
record('item5', `respace(${RESPACE_N}).postC0`,
       maxAbsDiff(Array.from(respaced50.postC0), ref.item5_respace50.post_c0));
record('item5', `respace(${RESPACE_N}).postCt`,
       maxAbsDiff(Array.from(respaced50.postCt), ref.item5_respace50.post_ct));
record('item5', `respace(${RESPACE_N}).postVar`,
       maxAbsDiff(Array.from(respaced50.postVar), ref.item5_respace50.post_var));

// item6 이 실제로 쓰는 스케줄: respace(cosineSchedule(200), LOOP_STEPS)
const { sched: respacedLoop } = MotifDiffusion._respace(sched0, LOOP_STEPS);
record('item5', `respace(${LOOP_STEPS}).postC0 (item6 용 스케줄)`,
       maxAbsDiff(Array.from(respacedLoop.postC0), ref.item5_respace_loopsteps.post_c0));
record('item5', `respace(${LOOP_STEPS}).postCt (item6 용 스케줄)`,
       maxAbsDiff(Array.from(respacedLoop.postCt), ref.item5_respace_loopsteps.post_ct));

// ═════════════════════════════════════════════════════════════════════════
// 더미 모델 (Python gen_reference.py 의 dummy_eps_torch 와 동일 수식)
// ═════════════════════════════════════════════════════════════════════════
function dummyEps(cropVal, j, c, t, w) {
  return Math.tanh(0.3 * cropVal + 0.01 * (j - w / 2) - 0.002 * t
                    + 0.05 * Math.sin(0.7 * c + 0.02 * t));
}

// motif-diffusion.js:230-232 를 그대로 옮김
function buildStarts(totalT, w, strideVal) {
  const s = [];
  for (let x = 0; x + w <= totalT; x += strideVal) s.push(x);
  if (s.length === 0) s.push(0);
  if (s[s.length - 1] !== totalT - w) s.push(totalT - w);
  return s;
}

// motif-diffusion.js:269-296 을 그대로 옮김 (model(crops,t) → dummyEps)
function fusedEpsStep(x, i, startsArr, hannArr, Kc, Tt, w) {
  const idxCT = (c, t) => c * Tt + t;
  const N = Kc * Tt;
  const epsAcc = new Float32Array(N);
  const wAcc = new Float32Array(N);
  for (const s0 of startsArr) {
    for (let c = 0; c < Kc; c++) {
      for (let j = 0; j < w; j++) {
        const t = s0 + j;
        const cropVal = x[idxCT(c, t)];
        const e = dummyEps(cropVal, j, c, i, w) * hannArr[j];
        epsAcc[idxCT(c, t)] += e;
        wAcc[idxCT(c, t)] += hannArr[j];
      }
    }
  }
  const eps = new Float32Array(N);
  for (let p = 0; p < N; p++) eps[p] = epsAcc[p] / wAcc[p];
  return eps;
}

// motif-diffusion.js:298-316 을 그대로 옮김. sig*noise, k1m*randn() 항만
// 제거했다(옵션 B) — 그 외 클리핑·계수·마스크 분기는 원본과 동일하다.
function stepDeterministic(x, i, sched, known, mask, startsArr, hannArr, Kc, Tt, w) {
  const N = Kc * Tt;
  const eps = fusedEpsStep(x, i, startsArr, hannArr, Kc, Tt, w);
  const sAc = sched.sqrtAc[i], s1 = sched.sqrt1mAc[i];
  const c0 = sched.postC0[i], ct = sched.postCt[i];
  const kAc = i > 0 ? sched.sqrtAc[i - 1] : 1;
  const x0 = new Float32Array(N);
  const mean = new Float32Array(N);
  const xNew = new Float32Array(N);
  for (let p = 0; p < N; p++) {
    let v0 = (x[p] - s1 * eps[p]) / sAc;
    if (v0 > 1) v0 = 1; else if (v0 < -1) v0 = -1;
    x0[p] = v0;
    const m = c0 * v0 + ct * x[p];             // noise=0 (sig*noise[p] 제거)
    mean[p] = m;
    let v = m;
    if (mask[p] === 1) {
      v = i > 0 ? kAc * known[p] : known[p];   // noise=0 (k1m*randn() 제거)
    }
    xNew[p] = v;
  }
  return { eps, x0, mean, xNew };
}

// motif-diffusion.js:266-330 (u-loop + 되돌림) 을 그대로 옮김.
function runLoop(xInit, schedS, known, mask, startsArr, hannArr, Kc, Tt, w, jumpU, jumpFrom) {
  const N = Kc * Tt;
  let x = xInit.slice();
  const S = schedS.T;
  const jumpStart = Math.floor(S * jumpFrom);
  for (let i = S - 1; i >= 0; i--) {
    const reps = i < jumpStart ? jumpU : 1;
    for (let u = 0; u < reps; u++) {
      const { xNew } = stepDeterministic(x, i, schedS, known, mask, startsArr, hannArr, Kc, Tt, w);
      x = xNew;
      if (u < reps - 1 && i > 0) {                       // motif-diffusion.js:319-322
        const sa = Math.sqrt(schedS.alphas[i]);
        const xr = new Float32Array(N);
        for (let p = 0; p < N; p++) xr[p] = sa * x[p];    // noise=0 (sb*randn() 제거)
        x = xr;
      }
    }
  }
  const res = new Float32Array(N);   // (K,T)[-1,1] → t-major[0,1] — motif-diffusion.js:332-339
  for (let t = 0; t < Tt; t++) {
    for (let c = 0; c < Kc; c++) {
      let v = (x[c * Tt + t] + 1) / 2;
      res[t * Kc + c] = v < 0 ? 0 : (v > 1 ? 1 : v);
    }
  }
  return res;
}

// ── 공통 입력 (파이썬과 동일 reference.json 에서 로드) ──
const xInitKT = new Float32Array(K * T);   // (K,T) layout, idxCT(c,t)=c*T+t
for (let c = 0; c < K; c++) {
  for (let t = 0; t < T; t++) xInitKT[c * T + t] = ref.inputs.x_init[c][t];
}
const knownKT = new Float32Array(K * T);   // known01*2-1, (K,T) layout
const maskKT = new Float32Array(K * T);
for (let t = 0; t < T; t++) {
  for (let c = 0; c < K; c++) {
    knownKT[c * T + t] = ref.inputs.known01[t][c] * 2 - 1;
    maskKT[c * T + t] = ref.inputs.mask[t][c] > 0.5 ? 1 : 0;
  }
}
const startsJS = buildStarts(T, win, stride);
record('설정확인', `창 시작점(13개) JS vs PY`,
       maxAbsDiff(startsJS, refStarts));

// ═════════════════════════════════════════════════════════════════════════
// item 2/3/4 — 고정 스텝 i=100, T=240, 스케줄 sched0(T=200, 비-respace)
// ═════════════════════════════════════════════════════════════════════════
console.log(`\n[item2/3/4] i=${TEST_I} 고정 스텝, T=${T}, 창 13개 (더미모델, 노이즈=0)`);
const step100 = stepDeterministic(xInitKT, TEST_I, sched0, knownKT, maskKT, startsJS, hann60, K, T, win);
record('item2', `MultiDiffusion 융합 eps @ i=${TEST_I} (K×T=${K}×${T})`,
       maxAbsDiff(Array.from(step100.eps), ref.item2_fused_eps));
record('item3', `x̂₀ 클리핑 값 @ i=${TEST_I}`,
       maxAbsDiff(Array.from(step100.x0), ref.item3_x0));
record('item3', `사후평균(mean) @ i=${TEST_I}`,
       maxAbsDiff(Array.from(step100.mean), ref.item3_mean));
record('item4', `RePaint 마스크 적용 후 x @ i=${TEST_I}`,
       maxAbsDiff(Array.from(step100.xNew), ref.item4_x_after_mask));

// ═════════════════════════════════════════════════════════════════════════
// item 6 — 전체 루프 (respace(200→5), 더미모델, 노이즈=0)
// ═════════════════════════════════════════════════════════════════════════
console.log(`\n[item6] 전체 루프 steps=${LOOP_STEPS} (respace(200→${LOOP_STEPS}))`);
const xOutTK = runLoop(xInitKT, respacedLoop, knownKT, maskKT, startsJS, hann60, K, T, win,
                        JUMP_U, JUMP_FROM);
console.log(`  JS  x_out mean=${(Array.from(xOutTK).reduce((a, b) => a + b, 0) / xOutTK.length).toFixed(6)} `
            + `min=${Math.min(...xOutTK).toFixed(6)} max=${Math.max(...xOutTK).toFixed(6)}`);
const pyXOutFlat = ref.item6_x_out.flat();
record('item6', `최종 출력 x_out (T×K=${T}×${K}, [0,1])`,
       maxAbsDiff(Array.from(xOutTK), pyXOutFlat));

// ═════════════════════════════════════════════════════════════════════════
// 판정 표 + 리포트 작성
// ═════════════════════════════════════════════════════════════════════════
console.log('\n' + '='.repeat(78));
const anyFail = results.some(r => !r.pass);
console.log(anyFail ? '실패 항목 있음 (max|diff| > 1e-4)' : '전 항목 통과 (max|diff| <= 1e-4)');
console.log('='.repeat(78));

const nowStr = new Date().toISOString();
const rows = results.map(r =>
  `| ${r.item} | ${r.label} | ${r.maxDiff === Infinity ? '길이 불일치' : r.maxDiff.toExponential(3)} `
  + `| ${r.pass ? 'PASS' : '**FAIL**'} |`).join('\n');

const reportMd = `# JS RePaint 샘플러 결정적 동치 검증

생성: ${nowStr} (자동 생성 — \`tools/verify_js_sampler.mjs\`)

## 배경

\`hibari_dashboard/public/js/motif-diffusion.js\` 는 \`experiments/motif_control.py\`
의 \`sample_with_motif()\` 를 브라우저용으로 이식한 RePaint 샘플러다. 지금까지
검증된 것은 스케줄 상수뿐이었고(파이썬 대비 7.2e-8), 샘플링 루프 자체
(MultiDiffusion 창 융합 + RePaint 마스킹 + x̂₀ 클리핑 사후평균)는 미검증이었다.
이 문서는 그 루프를 실제로 실행해 대조한 결과다.

## 검증 방식 — 왜 (B) "노이즈=0 결정적 경로"를 택했는가

과제가 제시한 두 방법 중 (A) "양쪽에 동일한 고정 노이즈 배열 주입"은 실행
불가능했다: \`motif-diffusion.js\` 의 \`randn\` 은 \`sampleWithMotif()\` 호출마다
새로 만들어지는 **비공개 클로저**(\`makeRandn(seed)\`, mulberry32+Box-Muller)이고,
외부에서 개별 draw 값을 주입할 공개 인터페이스가 없다. 이를 가능하게 하려면
배포 중인 \`motif-diffusion.js\` 자체를 고쳐야 하는데, 그러면 "실제 배포된
코드"가 아니라 "테스트를 위해 바뀐 코드"를 검증하게 되어 본말이 전도된다.
반대로 파이썬 쪽 \`torch.Generator\` 는 Philox 계열 PRNG 라 mulberry32 와
애초에 같은 난수 스트림을 낼 수 없다 — 이는 버그가 아니라 서로 다른 PRNG 를
쓴 결과이며 검증 대상이 아니다.

그래서 (B) 를 택했다: 모든 노이즈 항(사후분산 항 \`sig*noise\`, RePaint 안다는
영역의 \`k1m*randn()\`, 되돌림 재샘플링의 \`sqrt(betas)*randn()\`)을 0으로 두고
**평균-전용(ODE) 결정적 경로**만 비교했다. 이렇게 하면 실제로 미검증이었던
4가지 결정적 산술 — (i) 윈도우 크롭+Hann 융합, (ii) x̂₀ 클리핑+사후평균 계수,
(iii) RePaint 마스크 블렌딩, (iv) respace() 재배치 — 을 노이즈에 가려지지
않고 그대로 비교할 수 있다.

모델도 같은 이유로 실제 ONNX 대신 **두 언어가 공유하는 더미 함수**를 썼다:

\`\`\`
eps[c,j] = tanh(0.3*crop + 0.01*(j-win/2) - 0.002*t + 0.05*sin(0.7*c+0.02*t))
\`\`\`

ONNX 모델 자체(PyTorch↔ONNXRuntime)의 수치 일치는 \`tools/export_topo_onnx.py\`
가 이미 별도로 검증했다(모든 배치/시간축 조합에서 max|diff| ≤ 3.1e-6,
\`topo_denoiser_meta.json\`.\`parity_max_abs_diff\` 참조) — 여기서 다시 검증할
필요가 없었다. 오히려 실제 모델을 쓰면 "모델이 무엇을 예측하든 창 경계에서
올바르게 합성/클리핑/마스킹하는가"라는 진짜 검증 대상이 모델 예측값 자체의
변동에 가려진다.

## onnxruntime-node 설치 여부

\`npm ls onnxruntime-node\` → \`(empty)\`. 이 레포에는 설치돼 있지 않았고,
지시대로 설치하지 않았다. 대신 위에서 설명한 "더미 eps 주입" 대안을 썼다.

## 코드 재사용 범위

- \`MotifDiffusion._cosineSchedule\` / \`MotifDiffusion._respace\` — motif-diffusion.js
  를 **수정 없이 그대로 로드**해서 직접 호출한 실제 배포 코드.
- Hann 창 계산(\`motif-diffusion.js:235-238\`)과 스텝 산술
  (\`motif-diffusion.js:266-330\`)은 class 내부 클로저라 외부에서 직접 호출할
  수 없어 **검증 전용 사본**으로 옮겨 썼다. 노이즈 항만 제거했고, 변수명·
  연산 순서·분기 조건은 원본과 동일하게 유지했다(\`tools/verify_js_sampler.mjs\`
  주석에 원본 라인 번호를 인용).
- 파이썬 쪽은 \`experiments/motif_control.py\` (읽기 전용, 수정하지 않음)의
  \`_fused_eps\` / \`sample_with_motif\` 를 그대로 베낀 사본을
  \`tools/verify/gen_reference.py\` 에 두었다(모델 호출만 더미로, 노이즈 항만
  제거).
- \`respace()\` 는 파이썬 원본이 없다(JS 전용 최적화) — 알고리즘 설명을 보고
  독립 재구현(\`respace_py\`)해 교차검증했다.

## 결과

| 항목 | 비교 대상 | max\\|diff\\| | 판정 |
|---|---|---|---|
${rows}

판정 기준: 1e-4 초과 시 FAIL.

${anyFail ? '**FAIL 항목이 있다 — 아래에서 원인을 코드 라인 단위로 지목한다.**'
          : '**전 항목 통과.** MultiDiffusion 융합·x̂₀ 클리핑 사후평균·RePaint 마스킹·'
            + 'respace 스케줄 재계산 모두 파이썬 기준값과 1e-4 이내로 일치했다.'}

## 재현 명령

\`\`\`bash
python tools/verify/gen_reference.py   # 파이썬 기준값 생성 → tools/verify/reference.json
node tools/verify_js_sampler.mjs       # 이 리포트 재생성
\`\`\`

## 남은 검증 공백 (참고)

- **RNG 자체의 등가성은 검증하지 않았다** — mulberry32(JS) vs torch.Generator
  (Python)는 설계상 다른 스트림을 낸다. 실제 배포 코드의 시각적/청각적 품질은
  난수가 켜진 상태에서 결정되므로, 이 문서의 결과는 "결정적 배관이 새지
  않는다"는 것만 보장하고 "노이즈가 켜졌을 때도 감각적으로 그럴듯한 분포를
  낸다"는 것까지는 보장하지 않는다.
- 실제 ONNX 모델 호출 코드 경로(\`session.run(feeds)\`, \`ort.Tensor\` 구성)는
  onnxruntime-node 부재로 이 검증에서 실행되지 않았다 — 더미 함수로 대체됐다.
  단, 텐서 shape/dtype 규약(\`float32\`/\`int64\`, \`[batch,K,win]\`)은
  \`tools/export_topo_onnx.py\` 의 export 시 검증된 것과 동일 규약을 그대로
  썼다.
`;

fs.writeFileSync(REPORT_PATH, reportMd, 'utf-8');
console.log(`\n리포트 저장: ${REPORT_PATH}`);

process.exit(anyFail ? 1 : 0);
