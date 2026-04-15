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

  // ── Sigmoid 벡터화 ──────────────────────────────────────────────────
  function sigmoidInPlace(arr) {
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      arr[i] = 1.0 / (1.0 + Math.exp(-v));
    }
    return arr;
  }

  // ── Top-k 기반 threshold 계산 (partial sort) ────────────────────────
  function topKThreshold(flat, ratio) {
    const k = Math.max(1, Math.floor(flat.length * ratio));
    // quickselect 으로 k 번째 최대값 탐색. n ≈ 25000, 1회 호출이므로 정렬도 감당 가능.
    // 메모리 copy 최소화 위해 Float64Array 복사본 정렬.
    const copy = Array.from(flat);
    copy.sort((a, b) => b - a);     // 내림차순
    return copy[k - 1];
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
     * 생성.
     * @param {object} args
     * @param {{T:number,K:number,values:(Int8Array|Float32Array)}} args.overlap
     * @param {number} [args.threshold] — null 이면 adaptive
     * @param {boolean} [args.adaptive=true]
     * @param {number} [args.minOnsetGap=0]
     * @param {number} [args.targetOnRatio=0.15]
     * @returns {Promise<{notes:Array, numActivations:number, threshold:number, inferenceMs:number}>}
     */
    async generate(args) {
      if (!this.session) throw new Error('FCGenerator 미로드 — load() 먼저 호출');
      const { overlap } = args;
      const adaptive = args.adaptive !== false;
      const minOnsetGap = args.minOnsetGap | 0;
      const targetOnRatio = args.targetOnRatio || 0.15;

      const T = overlap.T, K = overlap.K;
      const numCycles = this.meta.num_cycles;
      const numNotes = this.meta.num_notes;
      if (K !== numCycles) {
        throw new Error(`overlap K(${K}) != model num_cycles(${numCycles})`);
      }

      // Int8Array → Float32Array cast
      const input = new Float32Array(T * K);
      const src = overlap.values;
      for (let i = 0; i < T * K; i++) input[i] = src[i] ? 1.0 : 0.0;

      // ONNX 추론 (T, C) 배치
      const t0 = performance.now();
      const feeds = {
        overlap: new global.ort.Tensor('float32', input, [T, K]),
      };
      const out = await this.session.run(feeds);
      const logits = out.logits.data;   // Float32Array (T * N)
      const probs = sigmoidInPlace(logits.slice());
      const inferenceMs = performance.now() - t0;

      // threshold 결정
      let thr;
      if (adaptive || args.threshold == null) {
        thr = topKThreshold(probs, targetOnRatio);
        thr = Math.max(thr, this.meta.threshold?.min_threshold ?? 0.1);
      } else {
        thr = args.threshold;
      }

      // label_idx → {pitch, dur} 매핑
      const L2PD = new Map();
      for (const row of this.meta.label_to_note) {
        L2PD.set(row.label_idx, { pitch: row.pitch, dur: row.dur });
      }

      // 시점별 sampling
      const notes = [];
      let lastOnset = -minOnsetGap;
      let numActivations = 0;
      for (let t = 0; t < T; t++) {
        if (minOnsetGap > 0 && (t - lastOnset) < minOnsetGap) continue;
        let onsetAtT = false;
        for (let n = 0; n < numNotes; n++) {
          const p = probs[t * numNotes + n];
          if (p >= thr) {
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

      return { notes, numActivations, threshold: thr, inferenceMs };
    }
  }

  global.FCGenerator = FCGenerator;
})(window);
