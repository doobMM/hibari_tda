/* ============================================================================
 * data-loader.js — hibari_dashboard/data/ 로부터 JSON 데이터 로드
 * ============================================================================
 *
 * 외부로 노출되는 전역:
 *   window.HibariData = {
 *     manifest,                // data/manifest.json 내용
 *     overlapRef,              // { T, K, values: Int8Array[T*K] }  (이진)
 *     overlapCont,             // { T, K, values: Float32Array[T*K] } (연속)
 *     notesMeta,               // notes_metadata.json
 *     cyclesMeta,              // cycles_metadata.json
 *     loaded: true/false,
 *     error: null | string,
 *   }
 *
 *   window.HibariData.onReady(callback)  — 로드 완료 시 callback 호출
 *   window.HibariData.ref2d(t, c)        — 참조 overlap 접근 헬퍼
 *   window.HibariData.cont2d(t, c)       — 연속 overlap 접근 헬퍼
 * ========================================================================= */

(function () {
  'use strict';

  const state = {
    manifest: null,
    overlapRef: null,
    overlapCont: null,
    notesMeta: null,
    cyclesMeta: null,
    loaded: false,
    error: null,
    _readyCallbacks: [],
  };

  // ── 유틸: JSON fetch ─────────────────────────────────────────────────
  async function fetchJson(path) {
    const res = await fetch(path, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  }

  // ── 1D 리스트 → TypedArray + 메타 포장 ────────────────────────────────
  function packOverlap(payload, kind) {
    if (!payload || !Array.isArray(payload.values)) {
      throw new Error('overlap payload 형식 오류: values 배열 없음');
    }
    const T = payload.T;
    const K = payload.K;
    if (T * K !== payload.values.length) {
      throw new Error(
        `overlap 크기 불일치: T*K=${T * K}, values=${payload.values.length}`
      );
    }
    const TypedArrayCtor = (kind === 'binary') ? Int8Array : Float32Array;
    return {
      T, K,
      values: new TypedArrayCtor(payload.values),
      density: payload.density ?? null,
      min: payload.min ?? null,
      max: payload.max ?? null,
      mean: payload.mean ?? null,
      best_taus: payload.best_taus ?? null,
      exp_config: payload.exp_config ?? null,
      description: payload.description ?? '',
    };
  }

  // ── 메인 로더 ────────────────────────────────────────────────────────
  async function loadAll() {
    try {
      // data/ 는 public/ 상위 디렉토리에 있음 → 상대 경로 '../data/'
      // 배포 시에는 ?path= 쿼리로 override 가능
      const base = (new URLSearchParams(window.location.search).get('data') || '../data') + '/';
      // manifest 먼저 로드
      const manifest = await fetchJson(base + 'manifest.json');
      state.manifest = manifest;

      // 병렬 fetch
      const [refRaw, contRaw, notesRaw, cyclesRaw] = await Promise.all([
        fetchJson(base + 'overlap_matrix_reference.json'),
        fetchJson(base + 'overlap_matrix_continuous.json'),
        fetchJson(base + 'notes_metadata.json'),
        fetchJson(base + 'cycles_metadata.json'),
      ]);

      state.overlapRef = packOverlap(refRaw, 'binary');
      state.overlapCont = packOverlap(contRaw, 'continuous');
      state.notesMeta = notesRaw;
      state.cyclesMeta = cyclesRaw;
      state.loaded = true;

      // 접근자 헬퍼
      state.ref2d = (t, c) => state.overlapRef.values[t * state.overlapRef.K + c];
      state.cont2d = (t, c) => state.overlapCont.values[t * state.overlapCont.K + c];

      // ready callback 일괄 실행
      state._readyCallbacks.forEach((cb) => {
        try { cb(state); } catch (e) { console.error('onReady cb error:', e); }
      });
      state._readyCallbacks = [];

      console.info(
        `[HibariData] 로드 완료: T=${state.overlapRef.T}, K=${state.overlapRef.K}, ` +
        `N=${state.notesMeta.num_notes}, cycles=${state.cyclesMeta.num_cycles}`
      );
    } catch (err) {
      state.error = err.message || String(err);
      state.loaded = false;
      console.error('[HibariData] 로드 실패:', err);
    }
  }

  // ── 공개 API ─────────────────────────────────────────────────────────
  state.onReady = function (cb) {
    if (state.loaded) cb(state);
    else if (state.error) console.warn('[HibariData] 이미 실패 상태, cb 무시');
    else state._readyCallbacks.push(cb);
  };

  window.HibariData = state;
  // DOM 준비와 독립적으로 즉시 시작
  loadAll();
})();
