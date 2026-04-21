/* ============================================================================
 * data-loader.js — filtration_viz 데이터 로더
 *
 * 공개:
 *   window.FiltrationData.load(base='data') → Promise<{
 *     T, N,
 *     points,          // Float32Array(N*2) — [x0,y0, x1,y1, ...] ([-1,1])
 *     points3,         // Float32Array(N*3) — [x0,y0,z0, ...] ([-1,1]³)
 *     dist,            // Float32Array(N*N) — row-major
 *     distMin, distMax,
 *     active,          // Uint8Array(T*N) — values[t*N + i]
 *     notes,           // [{label, label_idx, pitch, dur, pc}, ...]
 *     cycles,          // [{cycle_idx, vertices_0idx, edges:[[i,j],...], ...}]
 *     midiBytes,       // Uint8Array
 *     midiNotes,       // [[startSec, pitch, endSec, vel], ...]
 *     midiDurSec,      // total duration (sec)
 *     manifest
 *   }>
 * ========================================================================= */

(function (global) {
  'use strict';

  async function fetchJson(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
    return r.json();
  }
  async function fetchBytes(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
    const b = await r.arrayBuffer();
    return new Uint8Array(b);
  }

  async function load(base) {
    base = base || 'data';
    const [manifest, distJ, pointsJ, activeJ, notesJ, cyclesJ, midiBytes,
           overlapRefJ, overlapContJ] =
      await Promise.all([
        fetchJson(`${base}/manifest.json`),
        fetchJson(`${base}/distance_hybrid_a025.json`),
        fetchJson(`${base}/points_2d.json`),
        fetchJson(`${base}/notes_active.json`),
        fetchJson(`${base}/notes_metadata.json`),
        fetchJson(`${base}/cycles_simplicial.json`),
        fetchBytes(`${base}/original_hibari.mid`),
        fetchJson(`${base}/overlap_matrix_reference.json`).catch(() => null),
        fetchJson(`${base}/overlap_matrix_continuous.json`).catch(() => null),
      ]);

    const N = distJ.N;
    const T = activeJ.T;

    // overlap matrix (T × K) — 있으면 렌더러가 per-cycle 활성 판정에 사용
    let overlapBin = null, overlapCont = null, K = 0;
    if (overlapRefJ && overlapRefJ.values) {
      K = overlapRefJ.K;
      overlapBin = Uint8Array.from(overlapRefJ.values);
    }
    if (overlapContJ && overlapContJ.values) {
      overlapCont = Float32Array.from(overlapContJ.values);
    }

    // distance
    const dist = new Float32Array(distJ.values);

    // points (flatten) — 새 스키마 coords_2d/coords_3d, 구 스키마 coords 폴백
    const coords2d = pointsJ.coords_2d || pointsJ.coords;
    const coords3d = pointsJ.coords_3d;
    const points = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) {
      points[i * 2]     = coords2d[i][0];
      points[i * 2 + 1] = coords2d[i][1];
    }
    let points3 = null;
    if (coords3d && coords3d.length === N) {
      points3 = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        points3[i * 3]     = coords3d[i][0];
        points3[i * 3 + 1] = coords3d[i][1];
        points3[i * 3 + 2] = coords3d[i][2];
      }
    }

    // active matrix
    const active = Uint8Array.from(activeJ.values);

    // MIDI parse
    let midiNotes = [], midiDurSec = 0;
    try {
      const parsed = global.MidiIO.readMidiNotes(midiBytes);
      midiNotes = parsed.notes || [];
      for (const n of midiNotes) {
        if (n[2] > midiDurSec) midiDurSec = n[2];
      }
    } catch (e) {
      console.warn('[filtration-viz] MIDI parse failed:', e);
    }

    return {
      T, N, K,
      points,
      points3,
      dist,
      distMin: distJ.min,
      distMax: distJ.max,
      active,
      overlapBin,     // Uint8Array(T*K) — values[t*K + c]
      overlapCont,    // Float32Array(T*K) — [0, 1]
      notes: notesJ.labels,
      cycles: cyclesJ.cycles,
      midiBytes,
      midiNotes,
      midiDurSec,
      manifest,
    };
  }

  global.FiltrationData = { load };
})(window);
