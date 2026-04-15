/* ============================================================================
 * ood-detector.js — Out-of-Distribution 경고 계산
 *
 * 목적:
 *   사용자가 편집한 overlap matrix 가 학습 분포(참조)에서 얼마나 벗어났는지
 *   간단한 지표로 추정. 생성 품질 저하 가능성을 경고 배너로 표시.
 *
 * 핵심 지표:
 *   1. Hamming ratio          = (# differing cells) / (T × K)
 *   2. Density gap            = |density(E) - density(R)|
 *   3. Persistence-weighted   = Σ_c w_c · |colSum(E,c) - colSum(R,c)| / T  (w_c = maxPers_c / Σ maxPers)
 *   4. Overall OOD score      = 0.5 * ham + 0.2 * density + 0.3 * pers  ∈ [0,1]
 *
 * Level 매핑:
 *   < 0.05 : stable  (녹색, 배너 숨김)
 *   < 0.12 : normal  (녹색, 표시만)
 *   < 0.25 : warn    (황색)
 *   ≥ 0.25 : danger  (적색)
 *
 * 공개:
 *   const ood = new OODDetector({ reference, cycles });
 *   const s = ood.score(editValues);
 *   s = { score, hamming, densityGap, persistenceWeighted, level, detail }
 * ========================================================================= */

(function (global) {
  'use strict';

  class OODDetector {
    /**
     * @param {object} opts
     * @param {Int8Array|Int32Array|Array} opts.reference  (length = T*K)
     * @param {number} opts.T
     * @param {number} opts.K
     * @param {Array} opts.cycles  — cyclesMeta.cycles ({max_persistence, ...})
     */
    constructor({ reference, T, K, cycles }) {
      this.T = T;
      this.K = K;
      this.ref = new Int8Array(T * K);
      for (let i = 0; i < T * K; i++) this.ref[i] = reference[i] ? 1 : 0;

      // 사전 계산: 참조 column sums + density
      let refOn = 0;
      const colSumR = new Int32Array(K);
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) {
          const v = this.ref[t * K + c];
          refOn += v;
          colSumR[c] += v;
        }
      }
      this.refOn = refOn;
      this.refDensity = refOn / (T * K);
      this.colSumR = colSumR;

      // cycle 가중치 (max_persistence 기반 정규화)
      const weights = new Float32Array(K);
      let wSum = 0;
      for (let c = 0; c < K; c++) {
        const m = (cycles && cycles[c]) ? (cycles[c].max_persistence || 0) : 0;
        weights[c] = m;
        wSum += m;
      }
      if (wSum > 0) {
        for (let c = 0; c < K; c++) weights[c] /= wSum;
      } else {
        for (let c = 0; c < K; c++) weights[c] = 1.0 / K;
      }
      this.weights = weights;
    }

    score(editValues) {
      const T = this.T, K = this.K;
      let diffCount = 0;
      let editOn = 0;
      const colSumE = new Int32Array(K);

      for (let t = 0; t < T; t++) {
        const base = t * K;
        for (let c = 0; c < K; c++) {
          const ev = editValues[base + c] ? 1 : 0;
          editOn += ev;
          colSumE[c] += ev;
          if (ev !== this.ref[base + c]) diffCount++;
        }
      }

      const hamming = diffCount / (T * K);
      const editDensity = editOn / (T * K);
      const densityGap = Math.abs(editDensity - this.refDensity);

      let pers = 0;
      for (let c = 0; c < K; c++) {
        const dC = Math.abs(colSumE[c] - this.colSumR[c]) / T;
        pers += this.weights[c] * dC;
      }

      // 가중 결합. 모든 항이 [0,1] 이므로 합 ∈ [0,1].
      const sc = 0.5 * hamming + 0.2 * densityGap + 0.3 * pers;

      let level;
      if (sc < 0.05) level = 'stable';
      else if (sc < 0.12) level = 'normal';
      else if (sc < 0.25) level = 'warn';
      else level = 'danger';

      const detail =
        `Hamming ${(hamming * 100).toFixed(1)}% · ` +
        `Δdensity ${(densityGap * 100).toFixed(1)}pp · ` +
        `pers-weighted ${(pers * 100).toFixed(1)}%`;

      return {
        score: sc,
        hamming,
        densityGap,
        persistenceWeighted: pers,
        editDensity,
        diffCount,
        level,
        detail,
      };
    }
  }

  global.OODDetector = OODDetector;
})(window);
