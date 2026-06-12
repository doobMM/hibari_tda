/* ============================================================================
 * vae-explorer.js — OM VAE latent 공간 탐험 (구조 탐험 패널)
 *
 * 모델: scripts/train_om_vae_and_export.py 산출물
 *   - om_vae_encoder.onnx : 'om' [B, 840] → 'mu','logvar' [B, 12]
 *   - om_vae_decoder.onnx : 'z' [B, 12] → 'om_recon' [B, 840] (sigmoid, [0,1])
 *   - om_vae_meta.json    : window=60, K=14, z_ref_blocks (m=0..17 참조 latent)
 *
 * 공개 API:
 *   const vae = new VAEExplorer();
 *   await vae.load();
 *   vae.meta                            — 메타 (window, K, latent_dim, z_ref_blocks)
 *   const mu = await vae.encode(seg);   — Float32Array(840) → Float32Array(12)
 *   const om = await vae.decode(z);     — Float32Array(12) → Float32Array(840) [0,1]
 *   VAEExplorer.lerp(a, b, t)           — latent 선형 보간
 *   VAEExplorer.randn(dim, rng)         — 표준정규 샘플 (Box-Muller)
 *
 * 주의: onnxruntime-web 로더는 generation-algo2.js 와 동일 CDN. window.ort 재사용.
 * ========================================================================= */

(function (global) {
  'use strict';

  const ORT_CDN_URL =
    'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/ort.min.js';

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

  function resolveBase() {
    const p = new URLSearchParams(location.search).get('data');
    if (p) return p.replace(/\/data\/?$/, '') + '/models/';
    return './models/';
  }

  class VAEExplorer {
    constructor() {
      this.enc = null;
      this.dec = null;
      this.meta = null;
      this._loading = null;
    }

    async load() {
      if (this.enc && this.dec && this.meta) return;
      if (this._loading) return this._loading;
      this._loading = (async () => {
        await loadScriptOnce(ORT_CDN_URL);
        if (!global.ort) throw new Error('window.ort 누락');
        global.ort.env.wasm.wasmPaths =
          'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/';
        const base = resolveBase();
        const metaRes = await fetch(base + 'om_vae_meta.json', { cache: 'no-cache' });
        if (!metaRes.ok) throw new Error(`vae meta 로드 실패: ${metaRes.status}`);
        this.meta = await metaRes.json();
        const [encBytes, decBytes] = await Promise.all([
          fetch(base + 'om_vae_encoder.onnx', { cache: 'no-cache' }).then(r => {
            if (!r.ok) throw new Error(`encoder 로드 실패: ${r.status}`);
            return r.arrayBuffer();
          }),
          fetch(base + 'om_vae_decoder.onnx', { cache: 'no-cache' }).then(r => {
            if (!r.ok) throw new Error(`decoder 로드 실패: ${r.status}`);
            return r.arrayBuffer();
          }),
        ]);
        this.enc = await global.ort.InferenceSession.create(
          encBytes, { executionProviders: ['wasm'] });
        this.dec = await global.ort.InferenceSession.create(
          decBytes, { executionProviders: ['wasm'] });
      })();
      try {
        await this._loading;
      } finally {
        this._loading = null;
      }
    }

    get dim() { return this.meta.window * this.meta.K; }

    /** 연속 OM 세그먼트 (Float32Array(840), [0,1]) → latent μ (Float32Array(12)) */
    async encode(segValues) {
      if (!this.enc) throw new Error('VAEExplorer 미로드');
      const dim = this.dim;
      const input = new Float32Array(dim);
      for (let i = 0; i < dim; i++) {
        const v = +segValues[i];
        input[i] = v > 1 ? 1 : (v > 0 ? v : 0);
      }
      const out = await this.enc.run({
        om: new global.ort.Tensor('float32', input, [1, dim]),
      });
      return new Float32Array(out.mu.data);
    }

    /** latent z (length 12) → 연속 OM 세그먼트 Float32Array(840) [0,1] */
    async decode(z) {
      if (!this.dec) throw new Error('VAEExplorer 미로드');
      const L = this.meta.latent_dim;
      const input = new Float32Array(L);
      for (let i = 0; i < L; i++) input[i] = +z[i] || 0;
      const out = await this.dec.run({
        z: new global.ort.Tensor('float32', input, [1, L]),
      });
      return new Float32Array(out.om_recon.data);
    }

    /** 블록 m 의 참조 latent (학습 시 사전계산) */
    zRef(m) {
      const refs = this.meta.z_ref_blocks || [];
      const row = refs[Math.max(0, Math.min(refs.length - 1, m | 0))];
      return row ? new Float32Array(row) : null;
    }

    static lerp(a, b, t) {
      const out = new Float32Array(a.length);
      for (let i = 0; i < a.length; i++) out[i] = a[i] * (1 - t) + b[i] * t;
      return out;
    }

    /** 표준정규 샘플 (Box-Muller, rng: () => [0,1)) */
    static randn(dim, rng) {
      const r = rng || Math.random;
      const out = new Float32Array(dim);
      for (let i = 0; i < dim; i += 2) {
        const u1 = Math.max(1e-12, r());
        const u2 = r();
        const m = Math.sqrt(-2 * Math.log(u1));
        out[i] = m * Math.cos(2 * Math.PI * u2);
        if (i + 1 < dim) out[i + 1] = m * Math.sin(2 * Math.PI * u2);
      }
      return out;
    }
  }

  global.VAEExplorer = VAEExplorer;
})(window);
