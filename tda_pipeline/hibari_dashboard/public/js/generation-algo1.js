/* ============================================================================
 * generation-algo1.js — Algorithm 1 (확률적 샘플링) JS 포팅
 *
 * 대응 Python: tda_pipeline/generation.py (algorithm1_optimized, NodePool,
 *              CycleSetManager, _sample_note_at_time, _sample_avoiding_neighbors).
 *
 * 공개 API:
 *   const pool = new NodePool({ labels, numModules, temperature, rng })
 *   const mgr  = new CycleSetManager({ cycles, K })
 *   const res  = algorithm1({
 *     nodePool: pool,
 *     cycleManager: mgr,
 *     instLen,             // Int array[T] — 시점별 동시음 수
 *     overlap,             // { T, K, values: Int8Array[T*K] }
 *     maxResample: 50,
 *     rng,                 // () => [0,1)
 *     onProgress,          // (t, length) => void (선택)
 *   })
 *   res.notes       — [[startEighth, pitch, endEighth], ...]
 *   res.resampleFails
 *
 * 주의:
 *   - Python NodePool 은 풀에 1-indexed label 을 저장하고
 *     label_to_note_info 는 `lbl === label + 1` 로 조회한다.
 *     실질적으로 pool-sampled 경로는 "한 레이블 시프트" 된 조회가 발생하는
 *     잠재 버그가 존재하지만, 실험 결과(JS=0.0183)가 이 동작에 맞춰져
 *     보정되어 있으므로 본 포트는 이 동작을 그대로 재현한다.
 *   - cycle_labeled 는 0-indexed note 인덱스를 담으므로 intersect 경로는
 *     label_idx 와 일치한다 (정상).
 * ========================================================================= */

(function (global) {
  'use strict';

  // ── 결정적 PRNG (mulberry32) ─────────────────────────────────────────
  function makeRng(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Fisher-Yates 셔플 (rng in-place)
  function shuffle(arr, rng) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
  }

  // ── NodePool ────────────────────────────────────────────────────────
  class NodePool {
    /**
     * @param {object} opts
     * @param {Array} opts.labels  — notes_metadata.labels (각 {label, label_idx, pitch, dur, count})
     * @param {number} [opts.numModules=65]
     * @param {number} [opts.temperature=1.0]
     * @param {Function} [opts.rng]
     */
    constructor({ labels, numModules = 65, temperature = 1.0, rng = Math.random }) {
      this.labels = labels;
      this.labelToEntryPlus1 = new Map();   // label+1 key → entry (Python 버그 재현용)
      for (const e of labels) this.labelToEntryPlus1.set(e.label + 1, e);
      this.labelToEntry = new Map();        // label key → entry (정상 조회)
      for (const e of labels) this.labelToEntry.set(e.label, e);
      // label_idx → entry (cycle intersect 조회용)
      this.byIdx = new Map();
      for (const e of labels) this.byIdx.set(e.label_idx, e);

      this.numModules = numModules;
      this.temperature = temperature;
      this.rng = rng;

      // 온도 스케일링: count × num_modules → round(c ^ (1/T))
      const scaled = labels.map(n => {
        const v = n.count * numModules;
        if (Math.abs(temperature - 1.0) < 1e-9) return v;
        return Math.max(1, Math.round(Math.pow(v, 1.0 / temperature)));
      });

      const pool = [];
      labels.forEach((n, i) => {
        const c = scaled[i];
        for (let k = 0; k < c; k++) pool.push(n.label);   // 1-indexed (Python 호환)
      });
      shuffle(pool, rng);
      this.pool = pool;
      this.totalSize = pool.length;
    }

    sample() {
      return this.pool[Math.floor(this.rng() * this.pool.length)];
    }

    // Python label_to_note_info 완전 재현.
    // 호출자에 따라 input 이 0-indexed(cycle) 또는 1-indexed(pool) 로 들어오지만,
    // 둘 다 `target = input + 1` 로 조회하도록 Python 을 그대로 따른다.
    labelToNoteInfo(label) {
      const e = this.labelToEntryPlus1.get(label + 1);
      return e || null;
    }
  }

  // ── CycleSetManager ─────────────────────────────────────────────────
  class CycleSetManager {
    /**
     * @param {object} opts
     * @param {Array} opts.cycles  — cycles_metadata.cycles (각 {note_labels_0idx, ...})
     * @param {number} opts.K      — 총 cycle 수
     */
    constructor({ cycles, K }) {
      this.K = K;
      // allCycleSets[idx] = Set of note indices (0-indexed)
      this.allCycleSets = new Array(K);
      for (let i = 0; i < K; i++) this.allCycleSets[i] = new Set();
      for (const cy of cycles) {
        const idx = cy.cycle_idx;
        if (idx < 0 || idx >= K) continue;
        const notes = Array.isArray(cy.note_labels_0idx)
          ? cy.note_labels_0idx
          : (Array.isArray(cy.vertices_0idx) ? cy.vertices_0idx : []);
        for (const v of notes) this.allCycleSets[idx].add(v);
      }
      this._cacheIntersect = new Map();
      this._cacheUnion = new Map();
    }

    // mask: Int8Array 또는 유사 TypedArray (길이 K) — row of overlap
    _activeKey(mask) {
      const K = this.K;
      let key = '';
      for (let i = 0; i < K; i++) if (mask[i]) key += key ? (',' + i) : String(i);
      return key;
    }

    getIntersectNodes(mask) {
      const key = this._activeKey(mask);
      if (!key) return null;
      if (this._cacheIntersect.has(key)) return this._cacheIntersect.get(key);

      const freq = new Map();
      for (const idxStr of key.split(',')) {
        const idx = +idxStr;
        for (const v of this.allCycleSets[idx]) {
          freq.set(v, (freq.get(v) || 0) + 1);
        }
      }
      if (freq.size === 0) { this._cacheIntersect.set(key, null); return null; }
      const result = [];
      for (const [v, c] of freq) for (let k = 0; k < c; k++) result.push(v);
      this._cacheIntersect.set(key, result);
      return result;
    }

    getUnionNodes(mask) {
      const key = this._activeKey(mask);
      if (!key) return null;
      if (this._cacheUnion.has(key)) return this._cacheUnion.get(key);
      const u = new Set();
      for (const idxStr of key.split(',')) {
        const idx = +idxStr;
        for (const v of this.allCycleSets[idx]) u.add(v);
      }
      this._cacheUnion.set(key, u);
      return u;
    }
  }

  // ── 내부 헬퍼: j 시점에서 note 하나 샘플링 ───────────────────────────
  function _sampleNoteAtTime(j, length, flag, overlapRow, nodePool, cycleMgr,
                             onsetCheckerJ, maxResample, rng) {
    for (let attempt = 0; attempt < maxResample; attempt++) {
      let z;
      if (flag === 0) {
        z = _sampleAvoidingNeighbors(j, length, nodePool, cycleMgr, rng);
      } else {
        const interPool = cycleMgr.getIntersectNodes(overlapRow);
        if (interPool == null) {
          z = nodePool.sample();
        } else {
          z = interPool[Math.floor(rng() * interPool.length)];
        }
      }
      const tup = nodePool.labelToNoteInfo(z);
      if (!tup) continue;
      const pitch = tup.pitch;
      const duration = tup.dur;
      let end = j + duration;
      if (end > length) {
        if (j + 1 <= length) end = length;
        else continue;
      }
      const n2key = pitch * 10000 + (end - j);   // (pitch, dur) 고유 키
      if (onsetCheckerJ.has(n2key)) continue;
      return {
        n1: [j, pitch, end],
        n2key,
        dur: end - j,
      };
    }
    return null;
  }

  function _sampleAvoidingNeighbors(j, length, nodePool, cycleMgr, rng) {
    const K = cycleMgr.K;
    // 이전/이후 시점 mask 확보 — overlap row 는 주변에서 직접 접근
    const avoid = new Set();
    const prev = nodePool._prevRow;
    const next = nodePool._nextRow;
    if (prev && prev.flag > 0) {
      const u = cycleMgr.getUnionNodes(prev.row);
      if (u) for (const v of u) avoid.add(v);
    }
    if (next && next.flag > 0) {
      const u = cycleMgr.getUnionNodes(next.row);
      if (u) for (const v of u) avoid.add(v);
    }
    if (avoid.size === 0) return nodePool.sample();
    for (let i = 0; i < 20; i++) {
      const z = nodePool.sample();
      if (!avoid.has(z)) return z;
    }
    return nodePool.sample();
  }

  // ── 메인 Algorithm 1 ────────────────────────────────────────────────
  function algorithm1({ nodePool, cycleManager, instLen, overlap,
                        maxResample = 50, rng, onProgress }) {
    if (rng) nodePool.rng = rng;
    const effectiveRng = rng || nodePool.rng || Math.random;
    const { T, K, values } = overlap;
    const length = Math.min(T, instLen.length);

    const len = new Int32Array(instLen.slice(0, length));
    const onsetChecker = new Array(length);
    for (let i = 0; i < length; i++) onsetChecker[i] = new Set();

    const generated = [];
    let resampleFails = 0;

    for (let j = 0; j < length; j++) {
      // 현재 시점 row 및 flag
      const row = values.subarray(j * K, (j + 1) * K);
      let flag = 0;
      for (let c = 0; c < K; c++) flag += row[c];

      // 이웃 행 캐시 (sampleAvoidingNeighbors 에서 사용)
      nodePool._prevRow = null;
      nodePool._nextRow = null;
      if (j > 0) {
        const prev = values.subarray((j - 1) * K, j * K);
        let f = 0; for (let c = 0; c < K; c++) f += prev[c];
        nodePool._prevRow = { row: prev, flag: f };
      }
      if (j < length - 1) {
        const nx = values.subarray((j + 1) * K, (j + 2) * K);
        let f = 0; for (let c = 0; c < K; c++) f += nx[c];
        nodePool._nextRow = { row: nx, flag: f };
      }

      const numToSample = Math.max(0, len[j]);
      for (let s = 0; s < numToSample; s++) {
        const info = _sampleNoteAtTime(
          j, length, flag, row, nodePool, cycleManager,
          onsetChecker[j], maxResample, effectiveRng
        );
        if (!info) { resampleFails++; continue; }
        generated.push(info.n1);
        onsetChecker[j].add(info.n2key);
        const endT = Math.min(info.n1[2], length);
        for (let t = j + 1; t < endT; t++) {
          if (len[t] > 0) len[t] -= 1;
          onsetChecker[t].add(info.n2key);
        }
      }

      if (onProgress && (j & 63) === 0) onProgress(j, length);
    }
    if (onProgress) onProgress(length, length);

    return { notes: generated, resampleFails, length };
  }

  // ── hibari 고정 inst_len 패턴 (run_test.py step4_generate_music) ────
  //   modules × 33 = 1056 길이. 나머지 32 시점은 0.
  const HIBARI_MODULE_PATTERN = [
    4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3
  ];
  function buildHibariInstLen(T = 1088) {
    const out = new Int32Array(T);
    const p = HIBARI_MODULE_PATTERN;
    for (let i = 0; i < p.length * 33 && i < T; i++) {
      out[i] = p[i % p.length];
    }
    return out;
  }

  // 공개
  global.GenerationAlgo1 = {
    NodePool,
    CycleSetManager,
    algorithm1,
    makeRng,
    buildHibariInstLen,
    HIBARI_MODULE_PATTERN,
  };
})(window);
