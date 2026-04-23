/* ============================================================================
 * ood-detector.js — Out-of-Distribution 경고 (JSD per-cycle persistence-weighted)
 *
 * 목적:
 *   사용자가 편집한 overlap matrix 가 학습 분포(참조)에서 얼마나 벗어났는지를
 *   논문에서 사용한 동일 지표(Jensen–Shannon divergence)로 측정.
 *
 * 정의:
 *   각 cycle c 에 대해 column 벡터를 시간축 확률 분포로 정규화 (ε regularization):
 *     p_c[t] = (M_ref[t,c] + ε) / Σ_t (M_ref[t,c] + ε)
 *     q_c[t] = (M_edit[t,c] + ε) / Σ_t (M_edit[t,c] + ε)
 *
 *   JSD_c = 0.5·KL(p_c || m_c) + 0.5·KL(q_c || m_c),  m_c = (p_c + q_c) / 2
 *   (log2 base → JSD ∈ [0, 1])
 *
 *   Overall = Σ_c w_c · JSD_c,  w_c = max_persistence_c / Σ_c max_persistence_c
 *
 * 부가 지표:
 *   meanGap = mean_{t,c} |edit[t,c] - ref[t,c]|   (이진/연속 모두 의미)
 *   density = mean(edit)                          (이진=ON 비율, 연속=평균 활성도)
 *
 * Level 매핑 (JSD 기준):
 *   < 0.05 : stable
 *   < 0.12 : normal
 *   < 0.25 : warn
 *   ≥ 0.25 : danger
 *
 * 공개:
 *   const ood = new OODDetector({ reference, T, K, cycles });
 *   const s = ood.score(editValues);  // editValues: Int8Array OR Float32Array
 *   s = { score, jsdPerCycle, meanGap, editDensity, refDensity, level, detail }
 *
 * 비고:
 *   T×K = 15,232 셀, K=14 cycle 기준 한 번 score() 호출은 < 5ms 수준.
 * ========================================================================= */

(function (global) {
  'use strict';

  const EPS = 1e-6;
  const LOG2 = Math.log(2);

  function _safeLog2(x) { return Math.log(x) / LOG2; }

  class OODDetector {
    /**
     * @param {object} opts
     * @param {Int8Array|Float32Array|Array} opts.reference  (length = T*K)
     * @param {number} opts.T
     * @param {number} opts.K
     * @param {Array}  opts.cycles  — cyclesMeta.cycles ({max_persistence, ...})
     */
    constructor({ reference, T, K, cycles }) {
      this.T = T;
      this.K = K;

      // 참조는 Float32 로 저장 (이진/연속 통합 처리)
      const N = T * K;
      this.ref = new Float32Array(N);
      for (let i = 0; i < N; i++) this.ref[i] = reference[i] || 0;

      // 사전계산: cycle 별 column sum (정규화 분모, ε 더한 값)
      const colSumR = new Float64Array(K);
      let refSum = 0;
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) {
          const v = this.ref[t * K + c];
          colSumR[c] += v;
          refSum += v;
        }
      }
      // ε regularization 적용한 분모: Σ + T·ε
      this.colSumR_eps = new Float64Array(K);
      for (let c = 0; c < K; c++) this.colSumR_eps[c] = colSumR[c] + T * EPS;
      this.refDensity = refSum / N;

      // cycle 가중치 (max_persistence 정규화)
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

    /**
     * @param {Int8Array|Float32Array} editValues
     * @returns {{score, jsdPerCycle, meanGap, editDensity, refDensity, level, detail}}
     */
    score(editValues) {
      const T = this.T, K = this.K;
      const N = T * K;

      // edit column sum + 부가 지표 (mean gap, density)
      const colSumE = new Float64Array(K);
      let editSum = 0;
      let absGap = 0;
      for (let t = 0; t < T; t++) {
        const base = t * K;
        for (let c = 0; c < K; c++) {
          const v = editValues[base + c] || 0;
          colSumE[c] += v;
          editSum += v;
          absGap += Math.abs(v - this.ref[base + c]);
        }
      }
      const editDensity = editSum / N;
      const meanGap = absGap / N;
      const colSumE_eps = new Float64Array(K);
      for (let c = 0; c < K; c++) colSumE_eps[c] = colSumE[c] + T * EPS;

      // per-cycle JSD (log2 base → ∈ [0,1])
      const jsdPerCycle = new Float32Array(K);
      let overall = 0;
      for (let c = 0; c < K; c++) {
        const denomP = this.colSumR_eps[c];
        const denomQ = colSumE_eps[c];
        let kl_pm = 0;   // Σ p log(p/m)
        let kl_qm = 0;   // Σ q log(q/m)
        for (let t = 0; t < T; t++) {
          const idx = t * K + c;
          const p = (this.ref[idx] + EPS) / denomP;
          const q = (editValues[idx] + EPS) / denomQ;
          const m = (p + q) * 0.5;
          if (p > 0 && m > 0) kl_pm += p * _safeLog2(p / m);
          if (q > 0 && m > 0) kl_qm += q * _safeLog2(q / m);
        }
        let jsd = 0.5 * (kl_pm + kl_qm);
        if (jsd < 0) jsd = 0;
        if (jsd > 1) jsd = 1;
        jsdPerCycle[c] = jsd;
        overall += this.weights[c] * jsd;
      }

      let level;
      if (overall < 0.05) level = 'stable';
      else if (overall < 0.12) level = 'normal';
      else if (overall < 0.25) level = 'warn';
      else level = 'danger';

      const detail =
        `JSD ${overall.toFixed(4)} (= OOD ${(overall * 100).toFixed(1)}%) · ` +
        `Δdensity ${(Math.abs(editDensity - this.refDensity) * 100).toFixed(1)}pp · ` +
        `평균 셀 차 ${(meanGap * 100).toFixed(1)}%`;

      return {
        score: overall,
        jsdPerCycle,
        meanGap,
        editDensity,
        refDensity: this.refDensity,
        level,
        detail,
      };
    }
  }

  global.OODDetector = OODDetector;
})(window);
