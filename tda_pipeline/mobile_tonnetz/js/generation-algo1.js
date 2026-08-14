// Algorithm 1 (확률적 샘플링) — ES module 포팅.
// 원본: tda_pipeline/hibari_dashboard/public/js/generation-algo1.js
// (window.GenerationAlgo1 IIFE 버전)
//
// 공개 API:
//   const pool = new NodePool({ labels, numModules, temperature, rng })
//   const mgr  = new CycleSetManager({ cycles, K })
//   const res  = algorithm1({ nodePool: pool, cycleManager: mgr,
//                              instLen, overlap, maxResample, rng, onProgress })
//
// 인덱스 규약: **전부 0-indexed(`label_idx`)** (2026-08-14 정정, Python fcf929f 와 동일).
// ⚠ 이전 버전은 풀에 1-indexed `label` 을 넣고 항등 조회를 해서 intersect 경로
//   (cycle_labeled = 0-indexed) 가 한 칸 낮은 음으로 디코딩됐다. z=0 은 항상 버려졌다.

// ── 결정적 PRNG (mulberry32) ───────────────────────────────────────────────
export function makeRng(seed) {
  let a = (seed >>> 0) || 1;
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Fisher-Yates 셔플
function shuffle(arr, rng) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
  }
  return arr;
}

// ── NodePool ──────────────────────────────────────────────────────────────
export class NodePool {
  constructor({ labels, numModules = 65, temperature = 1.0, rng = Math.random }) {
    this.labels = labels;
    // label_idx(0-indexed) → entry. 유일한 디코딩 경로.
    this.byIdx = new Map();
    for (const e of labels) this.byIdx.set(e.label_idx, e);

    this.numModules = numModules;
    this.temperature = temperature;
    this.rng = rng;

    const scaled = labels.map(n => {
      const v = n.count * numModules;
      if (Math.abs(temperature - 1.0) < 1e-9) return v;
      return Math.max(1, Math.round(Math.pow(v, 1.0 / temperature)));
    });

    const pool = [];
    labels.forEach((n, i) => {
      const c = scaled[i];
      for (let k = 0; k < c; k++) pool.push(n.label_idx); // 0-indexed
    });
    shuffle(pool, rng);
    this.pool = pool;
    this.totalSize = pool.length;
  }

  sample() {
    return this.pool[Math.floor(this.rng() * this.pool.length)];
  }

  // 입력은 항상 0-indexed (풀 = label_idx, intersect = cycle_labeled note 인덱스).
  labelToNoteInfo(label) {
    return this.byIdx.get(label) || null;
  }
}

// ── CycleSetManager ───────────────────────────────────────────────────────
export class CycleSetManager {
  constructor({ cycles, K }) {
    this.K = K;
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

// ── 샘플링 헬퍼 ─────────────────────────────────────────────────────────
function _sampleAvoidingNeighbors(j, length, nodePool, cycleMgr, rng) {
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
    const n2key = pitch * 10000 + (end - j);
    if (onsetCheckerJ.has(n2key)) continue;
    return { n1: [j, pitch, end], n2key, dur: end - j };
  }
  return null;
}

// ── 메인 Algorithm 1 ─────────────────────────────────────────────────────
export function algorithm1({ nodePool, cycleManager, instLen, overlap,
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
    const row = values.subarray(j * K, (j + 1) * K);
    let flag = 0;
    for (let c = 0; c < K; c++) flag += row[c];

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

// ── hibari instLen 패턴 (run_test.py step4_generate_music 기준) ──────────
export const HIBARI_MODULE_PATTERN = [
  4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
  4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3
];
export function buildHibariInstLen(T = 1088) {
  const out = new Int32Array(T);
  const p = HIBARI_MODULE_PATTERN;
  for (let i = 0; i < T; i++) out[i] = p[i % p.length];
  return out;
}
