/* ============================================================================
 * generation-algo-transformer.js — Algorithm 2 (Transformer) ONNX 추론
 *
 * 대응 Python: generation.py (DynTransformerModel)
 * 곡: solari (K=25, N=34, T 동적)
 *
 * 외부 의존:
 *   - onnxruntime-web (CDN) — window.ort (generation-algo2.js 가 먼저 로드하면 공유)
 *   - transformer_solari.onnx      : public/models/transformer_solari.onnx
 *   - transformer_solari_meta.json : public/models/transformer_solari_meta.json
 *
 * 공개 API:
 *   const tg = new TransformerGenerator();
 *   await tg.load();
 *   const res = await tg.generate({
 *     overlap,        // { T, K, values: Int8Array|Float32Array (T*K) }
 *     seed,           // number
 *     temperature,    // number
 *     minOnsetGap,    // number
 *   });
 *   res.notes           — [[startEighth, pitch, endEighth], ...]
 *   res.numActivations
 *   res.meanProb
 *   res.inferenceMs
 *
 * 모델 base 경로: 항상 './models/' 고정.
 *   (FCGenerator 의 resolveBase()는 ?data= 파라미터 기반이라
 *    ?data=../data_solari 환경에서 모델 경로가 깨지므로 사용하지 않음.)
 * ========================================================================= */

(function (global) {
  'use strict';

  const ORT_CDN_URL =
    'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/ort.min.js';
  // 모델 경로는 public/ 기준 상대 경로로 고정
  const MODEL_BASE = './models/';

  // 결정적 PRNG (mulberry32) — FCGenerator, Algo1 과 동일 구현
  function makeRng(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ORT 스크립트 단 1회 로드 (FCGenerator 가 이미 로드했으면 재사용)
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

  // Sigmoid + temperature scaling — FCGenerator 와 동일
  function sigmoidTempered(logits, temperature) {
    const invT = 1.0 / Math.max(0.1, temperature);
    const out = new Float32Array(logits.length);
    for (let i = 0; i < logits.length; i++) {
      out[i] = 1.0 / (1.0 + Math.exp(-logits[i] * invT));
    }
    return out;
  }

  class TransformerGenerator {
    constructor() {
      this.session = null;
      this.meta = null;
      this._loading = null;
    }

    async load() {
      if (this.session && this.meta) return;
      if (this._loading) return this._loading;
      this._loading = (async () => {
        // 1) onnxruntime-web 스크립트 (이미 로드됐으면 no-op)
        await loadScriptOnce(ORT_CDN_URL);
        if (!global.ort) throw new Error('window.ort 누락 — CDN 로드 확인');
        // wasm 경로 (이미 설정됐을 수 있지만 덮어써도 무방)
        global.ort.env.wasm.wasmPaths =
          'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/';

        // 2) 메타 로드 (경로 고정: ./models/)
        const metaRes = await fetch(MODEL_BASE + 'transformer_solari_meta.json', { cache: 'no-cache' });
        if (!metaRes.ok) throw new Error(`Transformer meta 로드 실패: ${metaRes.status}`);
        this.meta = await metaRes.json();

        // 3) ONNX 로드
        const modelRes = await fetch(MODEL_BASE + 'transformer_solari.onnx', { cache: 'no-cache' });
        if (!modelRes.ok) throw new Error(`Transformer onnx 로드 실패: ${modelRes.status}`);
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
     * 생성 — stochastic Bernoulli sampling (FCGenerator 와 동일 방식).
     *
     * 입력 텐서 형상: [1, T, K] (Transformer 는 3D 배치 시퀀스)
     * 출력 logits: [1, T, N] flat → probs[t*N+n] (row-major)
     *
     * @param {object} args
     * @param {{T:number,K:number,values:(Int8Array|Float32Array)}} args.overlap
     * @param {number} [args.seed=1]
     * @param {number} [args.temperature=1.0]
     * @param {number} [args.minOnsetGap=0]
     * @returns {Promise<{notes:Array, numActivations:number, meanProb:number, inferenceMs:number}>}
     */
    async generate(args) {
      if (!this.session) throw new Error('TransformerGenerator 미로드 — load() 먼저 호출');
      const { overlap } = args;
      const seed = (args.seed | 0) >>> 0 || 1;
      const temperature = args.temperature > 0 ? args.temperature : 1.0;
      const minOnsetGap = args.minOnsetGap | 0;

      const T = overlap.T, K = overlap.K;
      const numCycles = this.meta.num_cycles;   // 25
      const numNotes  = this.meta.num_notes;    // 34
      if (K !== numCycles) {
        throw new Error(`overlap K(${K}) != model num_cycles(${numCycles})`);
      }

      // Int8Array/Float32Array → Float32Array (음수 → 0 클리핑)
      const input = new Float32Array(T * K);
      const src = overlap.values;
      for (let i = 0; i < T * K; i++) {
        const v = +src[i];
        input[i] = v > 0 ? v : 0;
      }

      // ONNX 추론 — Transformer 는 [B=1, T, K] 3D 텐서
      const t0 = performance.now();
      const feeds = {
        overlap: new global.ort.Tensor('float32', input, [1, T, K]),
      };
      const out = await this.session.run(feeds);
      // logits 출력 shape: [1, T, N] → data 는 flat Float32Array(T*N)
      const logits = out.logits.data;
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

      // Bernoulli 샘플링 — FCGenerator 와 동일 로직
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

  global.TransformerGenerator = TransformerGenerator;
})(window);
