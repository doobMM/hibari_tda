/* =========================================================================
 * motif-diffusion.js — 모티브를 남기고 나머지를 디퓨전이 채운다 (브라우저)
 *
 * 사용자가 중첩행렬에 그린 셀을 **모티브(고정)** 로 삼고, 나머지를 학습된
 * 위상 손실 디노이저가 채운다. 파이썬 구현 experiments/motif_control.py 의
 * sample_with_motif() 를 그대로 이식한 것이다.
 *
 *   RePaint (Lugmayr et al., CVPR 2022)
 *     x_{i-1} = mask ⊙ (√ᾱ_{i-1}·known + √(1-ᾱ_{i-1})·ε)  +  (1-mask) ⊙ p_θ(x_i)
 *   MultiDiffusion (Bar-Tal et al., ICML 2023)
 *     T > 학습창(60) 일 때 겹치는 창들의 ε 예측을 Hann 가중 평균해 하나로 융합
 *
 * 스레드 정책 — Web Worker 를 쓰지 않고 **스텝 사이에 이벤트 루프로 양보**한다.
 *   이유: (1) onnxruntime-web 세션을 워커로 옮기면 wasm 경로·전송 비용이 늘고
 *   기존 vae-explorer.js / generation-algo2.js 의 window.ort 재사용 구조가 깨진다.
 *   (2) 대시보드 기본 단위인 T=60 은 창 하나라 스텝당 모델 호출이 1회뿐이고,
 *   respacing(기본 50스텝)까지 쓰면 전체가 1초 안쪽이라 워커의 이득이 없다.
 *   T=240 처럼 긴 경우에만 창 13개가 한 배치로 들어가 수 초가 걸리는데,
 *   그때도 onProgress 로 진행률을 보이고 양보하므로 UI 가 멈추지 않는다.
 *
 * 모델이 없으면 조용히 실패한다(콘솔 에러 없음) — available() 로 먼저 확인하라.
 * ========================================================================= */

(function (global) {
  'use strict';

  const ORT_CDN_URL =
    'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/ort.min.js';
  const ORT_WASM_BASE =
    'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/';

  // ── 시드 고정 난수 (재현 가능) ──
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeRandn(seed) {
    const u = mulberry32(seed >>> 0);
    let spare = null;
    return function randn() {
      if (spare !== null) { const s = spare; spare = null; return s; }
      let a = u(); if (a < 1e-12) a = 1e-12;
      const b = u();
      const r = Math.sqrt(-2 * Math.log(a));
      spare = r * Math.sin(2 * Math.PI * b);
      return r * Math.cos(2 * Math.PI * b);
    };
  }

  function fillRandn(arr, randn) {
    for (let i = 0; i < arr.length; i++) arr[i] = randn();
    return arr;
  }

  // ── cosine schedule (파이썬 cosine_beta_schedule 과 동일) ──
  function cosineSchedule(T, s) {
    s = s === undefined ? 0.008 : s;
    const ac = new Float64Array(T + 1);
    const f0 = Math.pow(Math.cos((0 / T + s) / (1 + s) * Math.PI * 0.5), 2);
    for (let i = 0; i <= T; i++) {
      ac[i] = Math.pow(Math.cos((i / T + s) / (1 + s) * Math.PI * 0.5), 2) / f0;
    }
    const betas = new Float64Array(T);
    for (let i = 0; i < T; i++) {
      betas[i] = Math.min(0.9999, Math.max(0.0001, 1 - ac[i + 1] / ac[i]));
    }
    return derive(betas);
  }

  function derive(betas) {
    const T = betas.length;
    const alphas = new Float64Array(T);
    const acum = new Float64Array(T);
    let run = 1;
    for (let i = 0; i < T; i++) {
      alphas[i] = 1 - betas[i];
      run *= alphas[i];
      acum[i] = run;
    }
    const acPrev = new Float64Array(T);
    for (let i = 0; i < T; i++) acPrev[i] = i === 0 ? 1 : acum[i - 1];
    const sqrtAc = new Float64Array(T);
    const sqrt1mAc = new Float64Array(T);
    const postVar = new Float64Array(T);
    const postC0 = new Float64Array(T);
    const postCt = new Float64Array(T);
    for (let i = 0; i < T; i++) {
      sqrtAc[i] = Math.sqrt(acum[i]);
      sqrt1mAc[i] = Math.sqrt(1 - acum[i]);
      postVar[i] = betas[i] * (1 - acPrev[i]) / (1 - acum[i]);
      postC0[i] = betas[i] * Math.sqrt(acPrev[i]) / (1 - acum[i]);
      postCt[i] = (1 - acPrev[i]) * Math.sqrt(alphas[i]) / (1 - acum[i]);
    }
    return { T, betas, alphas, alphasCumprod: acum, alphasCumprodPrev: acPrev,
             sqrtAc, sqrt1mAc, postVar, postC0, postCt };
  }

  /**
   * 스텝 수를 줄인 재배치 스케줄 (respacing).
   * 원래 200 스텝을 그대로 돌면 브라우저에서 느리므로, ᾱ 를 부분수열로 뽑아
   * 그에 맞는 β' 를 다시 계산한다. 표본 품질은 거의 유지하면서 4배 빨라진다.
   */
  function respace(sched, nSteps) {
    if (!nSteps || nSteps >= sched.T) return { sched, srcIdx: null };
    const srcIdx = [];
    for (let s = 0; s < nSteps; s++) {
      srcIdx.push(Math.min(sched.T - 1, Math.round(s * (sched.T - 1) / (nSteps - 1))));
    }
    const betas = new Float64Array(nSteps);
    let prevAc = 1;
    for (let s = 0; s < nSteps; s++) {
      const ac = sched.alphasCumprod[srcIdx[s]];
      betas[s] = Math.min(0.9999, Math.max(1e-8, 1 - ac / prevAc));
      prevAc = ac;
    }
    return { sched: derive(betas), srcIdx };
  }

  // ── ort 로더 (vae-explorer.js 와 동일 CDN·전역 재사용) ──
  function loadScriptOnce(url) {
    return new Promise((resolve, reject) => {
      if (global.ort) return resolve();
      const existing = document.querySelector(`script[data-ort-src="${url}"]`);
      if (existing) {
        existing.addEventListener('load', resolve, { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }
      const s = document.createElement('script');
      s.src = url; s.async = true; s.dataset.ortSrc = url;
      s.addEventListener('load', resolve, { once: true });
      s.addEventListener('error',
        () => reject(new Error('onnxruntime-web 로드 실패')), { once: true });
      document.head.appendChild(s);
    });
  }

  function resolveBase() {
    const p = new URLSearchParams(location.search).get('data');
    if (p) return p.replace(/\/data\/?$/, '') + '/models/';
    return './models/';
  }

  const yieldToUI = () => new Promise(r => setTimeout(r, 0));

  class MotifDiffusion {
    constructor() {
      this.session = null;
      this.meta = null;
      this.base = null;
      this._loading = null;
      this._probe = null;
    }

    /** 모델 파일이 실제로 있는지 (버튼 노출 판단용). 실패해도 예외를 던지지 않는다. */
    async available() {
      if (this._probe !== null) return this._probe;
      try {
        const r = await fetch(resolveBase() + 'topo_denoiser_meta.json',
                              { method: 'GET', cache: 'no-cache' });
        this._probe = r.ok;
      } catch (e) {
        this._probe = false;
      }
      return this._probe;
    }

    async load() {
      if (this.session && this.meta) return;
      if (this._loading) return this._loading;
      this._loading = (async () => {
        await loadScriptOnce(ORT_CDN_URL);
        if (!global.ort) throw new Error('window.ort 누락');
        global.ort.env.wasm.wasmPaths = ORT_WASM_BASE;
        const base = resolveBase();
        const mr = await fetch(base + 'topo_denoiser_meta.json', { cache: 'no-cache' });
        if (!mr.ok) throw new Error(`denoiser meta 로드 실패: ${mr.status}`);
        this.meta = await mr.json();
        const buf = await fetch(base + 'topo_denoiser.onnx', { cache: 'no-cache' })
          .then(r => { if (!r.ok) throw new Error(`denoiser 로드 실패: ${r.status}`);
                       return r.arrayBuffer(); });
        this.session = await global.ort.InferenceSession.create(
          buf, { executionProviders: ['wasm'] });
        this.base = base;
      })();
      try { await this._loading; } finally { this._loading = null; }
    }

    /** 파이썬이 내보낸 스케줄을 우선 쓰고, 없으면 JS 에서 재계산한다. */
    _baseSchedule() {
      const m = this.meta && this.meta.schedule;
      if (m && Array.isArray(m.betas) && m.betas.length) {
        return derive(Float64Array.from(m.betas));
      }
      return cosineSchedule((this.meta && this.meta.T_diffusion) || 200);
    }

    /**
     * @param {Object} o
     * @param {Float32Array} o.known  길이 T*K, t-major, [0,1] — 사용자가 준 중첩행렬
     * @param {Float32Array} o.mask   길이 T*K, 1=고정 / 0=모델이 채움
     * @param {number} o.T  @param {number} [o.K=14]  @param {number} [o.seed=1]
     * @param {number} [o.steps=50]  재배치 스텝 수 (원본 200 을 줄임)
     * @param {function} [o.onProgress] (done, total)
     * @returns {Promise<Float32Array>} 길이 T*K, t-major, [0,1]
     */
    async sampleWithMotif(o) {
      await this.load();
      const K = o.K || (this.meta && this.meta.K) || 14;
      const T = o.T;
      const seed = (o.seed == null ? 1 : o.seed) | 0;
      const randn = makeRandn(seed);
      const onProgress = o.onProgress || function () {};

      // 재배치 스케줄과 **원본 타임스텝 인덱스**를 함께 받는다.
      // 계수(β·ᾱ·사후평균)는 재배치본 sched 로 계산하지만, 모델에 넣는 t 는
      // 반드시 **학습 때 쓰인 원본 인덱스**(0..199)여야 한다. 재배치 인덱스(0..49)를
      // 그대로 넣으면 디노이저가 노이즈 수준을 완전히 잘못 읽는다.
      const { sched, srcIdx } = respace(this._baseSchedule(), o.steps || 50);
      const S = sched.T;
      const modelT = i => (srcIdx ? srcIdx[i] : i);

      const md = (this.meta && this.meta.multidiffusion) || { win: 60, stride: 15 };
      const win = Math.min(md.win || 60, T);
      const stride = md.stride || 15;
      const rp = (this.meta && this.meta.repaint) || { jump_u: 4, jump_from: 0.35 };

      // 창 시작점
      const starts = [];
      for (let s = 0; s + win <= T; s += stride) starts.push(s);
      if (starts.length === 0) starts.push(0);
      if (starts[starts.length - 1] !== T - win) starts.push(T - win);

      // Hann 가중 (periodic=false)
      const hann = new Float32Array(win);
      for (let i = 0; i < win; i++) {
        hann[i] = Math.max(1e-3, 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (win - 1)));
      }

      // 채널-우선 (K,T) 로 다룬다 — 모델 입력 레이아웃
      const N = K * T;
      const idxCT = (c, t) => c * T + t;
      const known = new Float32Array(N);
      const mask = new Float32Array(N);
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) {
          known[idxCT(c, t)] = o.known[t * K + c] * 2 - 1;   // [-1,1]
          mask[idxCT(c, t)] = o.mask[t * K + c] > 0.5 ? 1 : 0;
        }
      }

      let x = fillRandn(new Float32Array(N), randn);
      const epsAcc = new Float32Array(N);
      const wAcc = new Float32Array(N);
      const noise = new Float32Array(N);

      const jumpStart = Math.floor(S * (rp.jump_from == null ? 0.35 : rp.jump_from));
      const jumpU = rp.jump_u || 4;
      let totalWork = 0;
      for (let i = S - 1; i >= 0; i--) totalWork += (i < jumpStart ? jumpU : 1);
      let done = 0;

      const crop = new Float32Array(starts.length * K * win);
      const tArr = new BigInt64Array(starts.length);

      for (let i = S - 1; i >= 0; i--) {
        const reps = i < jumpStart ? jumpU : 1;
        for (let u = 0; u < reps; u++) {
          // ── 겹치는 창을 한 배치로 묶어 ε 예측 ──
          for (let w = 0; w < starts.length; w++) {
            const s0 = starts[w];
            for (let c = 0; c < K; c++) {
              const src = idxCT(c, 0) + s0;
              crop.set(x.subarray(src, src + win), (w * K + c) * win);
            }
            tArr[w] = BigInt(modelT(i));
          }
          const feeds = {
            x: new global.ort.Tensor('float32', crop, [starts.length, K, win]),
            t: new global.ort.Tensor('int64', tArr, [starts.length]),
          };
          const out = await this.session.run(feeds);
          const eps = out.eps.data;

          epsAcc.fill(0); wAcc.fill(0);
          for (let w = 0; w < starts.length; w++) {
            const s0 = starts[w];
            for (let c = 0; c < K; c++) {
              const dst = idxCT(c, 0) + s0;
              const src = (w * K + c) * win;
              for (let j = 0; j < win; j++) {
                epsAcc[dst + j] += eps[src + j] * hann[j];
                wAcc[dst + j] += hann[j];
              }
            }
          }

          // ── x̂₀ 클리핑 사후평균 ──
          const sAc = sched.sqrtAc[i], s1 = sched.sqrt1mAc[i];
          const c0 = sched.postC0[i], ct = sched.postCt[i];
          const sig = i > 0 ? Math.sqrt(sched.postVar[i]) : 0;
          const kAc = i > 0 ? sched.sqrtAc[i - 1] : 1;
          const k1m = i > 0 ? sched.sqrt1mAc[i - 1] : 0;
          if (sig > 0) fillRandn(noise, randn);

          for (let p = 0; p < N; p++) {
            const e = epsAcc[p] / wAcc[p];
            let x0 = (x[p] - s1 * e) / sAc;
            if (x0 > 1) x0 = 1; else if (x0 < -1) x0 = -1;
            let v = c0 * x0 + ct * x[p];
            if (sig > 0) v += sig * noise[p];
            if (mask[p] === 1) {
              v = i > 0 ? kAc * known[p] + k1m * randn() : known[p];
            }
            x[p] = v;
          }

          // ── 되돌림 (경계 조화) ──
          if (u < reps - 1 && i > 0) {
            const sa = Math.sqrt(sched.alphas[i]), sb = Math.sqrt(sched.betas[i]);
            for (let p = 0; p < N; p++) x[p] = sa * x[p] + sb * randn();
          }

          done++;
          if ((done & 3) === 0 || done === totalWork) {
            onProgress(done, totalWork);
            await yieldToUI();
          }
        }
      }

      // (K,T) [-1,1] → t-major [0,1]
      const res = new Float32Array(N);
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) {
          let v = (x[idxCT(c, t)] + 1) / 2;
          res[t * K + c] = v < 0 ? 0 : (v > 1 ? 1 : v);
        }
      }
      return res;
    }

    /** 편의 — 켜져 있는 셀을 모티브로 삼아 채운 뒤 τ 로 이진화해 돌려준다. */
    async completeFromOn(matrix, T, K, opts) {
      opts = opts || {};
      const known = new Float32Array(T * K);
      const mask = new Float32Array(T * K);
      for (let i = 0; i < T * K; i++) {
        const on = matrix[i] > 0.5 ? 1 : 0;
        known[i] = on; mask[i] = on;          // 켜진 셀만 고정, 나머지는 자유
      }
      const raw = await this.sampleWithMotif(Object.assign({ known, mask, T, K }, opts));
      const tau = (this.meta && this.meta.tau) || 0.5;
      const out = new Float32Array(T * K);
      for (let i = 0; i < T * K; i++) out[i] = raw[i] >= tau ? 1 : 0;
      return { binary: out, raw };
    }
  }

  global.MotifDiffusion = MotifDiffusion;
  global.motifDiffusion = new MotifDiffusion();
  // 스케줄 계산부는 파이썬 대조 검증용으로 노출한다
  global.MotifDiffusion._cosineSchedule = cosineSchedule;
  global.MotifDiffusion._respace = respace;
})(window);
