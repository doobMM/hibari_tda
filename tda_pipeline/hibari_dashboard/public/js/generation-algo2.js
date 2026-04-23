/* ============================================================================
 * generation-algo2.js — Algorithm 2 (FC model) ONNX 추론
 *
 * 대응 Python: generation.py (MusicGeneratorFC, generate_from_model)
 *
 * 외부 의존:
 *   - onnxruntime-web (CDN 또는 로컬) — window.ort
 *   - fc_model.onnx      : public/models/fc_model.onnx
 *   - fc_model_meta.json : public/models/fc_model_meta.json
 *
 * 공개 API:
 *   const fc = new FCGenerator();
 *   await fc.load();                   // CDN 에서 ORT 로드 + 모델/메타 로드
 *   const res = await fc.generate({
 *     overlap,              // { T, K, values: Int8Array|Float32Array (T*K) }
 *     threshold,            // number | null (null → adaptive)
 *     adaptive: true,       // true 면 meta.threshold 기준 상위 15% 임계값 자동
 *     minOnsetGap: 0,       // 이전 onset 과 최소 간격 (시점 단위)
 *     targetOnRatio: 0.15,  // adaptive 시 목표 activation 비율
 *   });
 *   res.notes           — [[startEighth, pitch, endEighth], ...]
 *   res.numActivations
 *   res.threshold
 *   res.inferenceMs
 *
 * 주의:
 *   - 입력은 Float32Array 또는 Int8Array 모두 허용 (내부에서 float32 cast).
 *   - ONNX 모델은 (T, C) batch 입력을 받도록 dynamic axis 로 export 됨.
 *   - 모델 로드 실패 시 error 표시 후 throw. 호출자가 try/catch.
 * ========================================================================= */

(function (global) {
  'use strict';

  const ORT_CDN_URL =
    'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/ort.min.js';

  // 결정적 PRNG (mulberry32) — Algo1 과 동일 구현
  function makeRng(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // meta + model 상대경로 — URL 파라미터 ?data 와 동일 규칙 적용
  function resolveBase() {
    const p = new URLSearchParams(location.search).get('data');
    if (p) {
      // data 가 지정되면 models 도 동일 베이스 기준으로 상위 폴더에서 찾음
      // 일반적으로 data/ 와 models/ 는 동일 depth 에 있음.
      return p.replace(/\/data\/?$/, '') + '/models/';
    }
    return './models/';
  }

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
      s.src = url;
      s.async = true;
      s.dataset.ortSrc = url;
      s.addEventListener('load', resolve, { once: true });
      s.addEventListener('error',
        () => reject(new Error('onnxruntime-web 로드 실패 (CDN 접근 불가)')),
        { once: true });
      document.head.appendChild(s);
    });
  }

  // ── Sigmoid + temperature scaling (stochastic sampling 용) ─────────
  //   probs[i] = sigmoid(logits[i] / T)
  //   T→0  ⇒ 확률이 0/1 로 극단화 (거의 deterministic)
  //   T=1  ⇒ 모델 native 확률
  //   T>1  ⇒ 확률이 0.5 쪽으로 완화 (다양한 변주)
  function sigmoidTempered(logits, temperature) {
    const invT = 1.0 / Math.max(0.1, temperature);
    const out = new Float32Array(logits.length);
    for (let i = 0; i < logits.length; i++) {
      out[i] = 1.0 / (1.0 + Math.exp(-logits[i] * invT));
    }
    return out;
  }

  class FCGenerator {
    constructor() {
      this.session = null;
      this.meta = null;
      this._loading = null;
    }

    async load() {
      if (this.session && this.meta) return;
      if (this._loading) return this._loading;
      this._loading = (async () => {
        // 1) onnxruntime-web 스크립트
        await loadScriptOnce(ORT_CDN_URL);
        if (!global.ort) throw new Error('window.ort 누락 — CDN 로드 확인');
        // WebAssembly 백엔드 경로 (CDN 에 해당 .wasm 이 함께 배포되어 있음)
        global.ort.env.wasm.wasmPaths =
          'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/';

        const base = resolveBase();
        // 2) 메타 로드
        const metaRes = await fetch(base + 'fc_model_meta.json', { cache: 'no-cache' });
        if (!metaRes.ok) throw new Error(`meta 로드 실패: ${metaRes.status}`);
        this.meta = await metaRes.json();

        // 3) ONNX 로드
        const modelRes = await fetch(base + 'fc_model.onnx', { cache: 'no-cache' });
        if (!modelRes.ok) throw new Error(`onnx 로드 실패: ${modelRes.status}`);
        const bytes = await modelRes.arrayBuffer();
        this.session = await global.ort.InferenceSession.create(
          bytes, { executionProviders: ['wasm'] }
        );
      })();
      try {
        await this._loading;
      } finally {
        this._loading = null;
      }
    }

    /**
     * 생성 — stochastic Bernoulli sampling.
     *   1. ONNX logits 에 temperature scaling 적용 → sigmoid → 확률 p.
     *   2. 각 (t, note) 셀마다 Bernoulli(p) 샘플링: rng() < p → 활성.
     *   같은 OM + 같은 seed + 같은 temperature ⇒ 항상 같은 결과 (재현성).
     *   seed 변경 ⇒ 확률이 애매한 셀들이 출현/누락 → 변주.
     *   temperature 변경 ⇒ 분포 sharpness (낮을수록 원곡 충실, 높을수록 다양).
     *
     * @param {object} args
     * @param {{T:number,K:number,values:(Int8Array|Float32Array)}} args.overlap
     * @param {number} [args.seed=1]
     * @param {number} [args.temperature=1.0]
     * @param {number} [args.minOnsetGap=0]
     * @returns {Promise<{notes:Array, numActivations:number, meanProb:number, inferenceMs:number}>}
     */
    async generate(args) {
      if (!this.session) throw new Error('FCGenerator 미로드 — load() 먼저 호출');
      const { overlap } = args;
      const seed = (args.seed | 0) >>> 0 || 1;
      const temperature = args.temperature > 0 ? args.temperature : 1.0;
      const minOnsetGap = args.minOnsetGap | 0;

      const T = overlap.T, K = overlap.K;
      const numCycles = this.meta.num_cycles;
      const numNotes = this.meta.num_notes;
      if (K !== numCycles) {
        throw new Error(`overlap K(${K}) != model num_cycles(${numCycles})`);
      }

      // Int8Array/Float32Array → Float32Array cast ([0,1] 연속값 유지 지원)
      const input = new Float32Array(T * K);
      const src = overlap.values;
      for (let i = 0; i < T * K; i++) {
        const v = +src[i];
        input[i] = v > 0 ? v : 0;
      }

      // ONNX 추론 (T, C) 배치
      const t0 = performance.now();
      const feeds = {
        overlap: new global.ort.Tensor('float32', input, [T, K]),
      };
      const out = await this.session.run(feeds);
      const logits = out.logits.data;   // Float32Array (T * N)
      const probs = sigmoidTempered(logits, temperature);
      const inferenceMs = performance.now() - t0;

      // 확률 평균 (UI 표시용 — density hint)
      let probSum = 0;
      for (let i = 0; i < probs.length; i++) probSum += probs[i];
      const meanProb = probSum / probs.length;

      // label_idx → {pitch, dur} 매핑
      const L2PD = new Map();
      for (const row of this.meta.label_to_note) {
        L2PD.set(row.label_idx, { pitch: row.pitch, dur: row.dur });
      }

      // Bernoulli 샘플링 — seed 로 결정적 PRNG 구동
      const rng = makeRng(seed);
      const notes = [];
      let lastOnset = -minOnsetGap;
      let numActivations = 0;
      for (let t = 0; t < T; t++) {
        if (minOnsetGap > 0 && (t - lastOnset) < minOnsetGap) continue;
        let onsetAtT = false;
        for (let n = 0; n < numNotes; n++) {
          const p = probs[t * numNotes + n];
          if (rng() < p) {
            const pd = L2PD.get(n);
            if (!pd) continue;
            const end = Math.min(T, t + pd.dur);
            notes.push([t, pd.pitch, end]);
            onsetAtT = true;
            numActivations++;
          }
        }
        if (onsetAtT) lastOnset = t;
      }

      return { notes, numActivations, meanProb, inferenceMs };
    }
  }

  global.FCGenerator = FCGenerator;
})(window);
