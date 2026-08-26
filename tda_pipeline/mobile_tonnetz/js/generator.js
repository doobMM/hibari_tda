// generator.js — Phase 3: OM → Algorithm 1 → 피아노 재생.
//
// 실행 흐름
//   1. notes_metadata / cycles_metadata JSON 로드 (최초 1회, 모듈 캐시)
//   2. buildPersonalOM() 으로 T×K overlap 생성
//   3. NodePool + CycleSetManager 구성
//   4. algorithm1() 실행 → notes: [[startEighth, pitch, endEighth], ...]
//   5. AudioEngine 로 실시간 스케줄 재생
//
// 외부 API
//   await loadMetadata()          — idempotent
//   runGeneration(recording, audio, opts) → Promise<{notes, meta, stop}>

import {
  NodePool, CycleSetManager, algorithm1, makeRng, buildHibariInstLen,
} from './generation-algo1.js';
import { buildPersonalOM } from './recording-to-om.js';

let _notesCache = null;
let _cyclesCache = null;

export async function loadMetadata() {
  if (_notesCache && _cyclesCache) {
    return { notes: _notesCache, cycles: _cyclesCache };
  }
  const [notesRes, cyclesRes] = await Promise.all([
    fetch('./data/notes_metadata.json'),
    fetch('./data/cycles_metadata.json'),
  ]);
  if (!notesRes.ok) throw new Error('notes_metadata.json 로드 실패: ' + notesRes.status);
  if (!cyclesRes.ok) throw new Error('cycles_metadata.json 로드 실패: ' + cyclesRes.status);
  const notesJson  = await notesRes.json();
  const cyclesJson = await cyclesRes.json();
  _notesCache  = notesJson.labels;
  _cyclesCache = cyclesJson.cycles;
  return { notes: _notesCache, cycles: _cyclesCache };
}

// ── 생성 실행 ─────────────────────────────────────────────────────────────
export async function runGeneration(recording, audio, {
  T = 120,
  K = 14,
  stepMs = 250,
  temperature = 1.0,   // 2026-08-15: 3.0 의 근거(§7.7.3)는 철회됨
  seed = Math.floor(Math.random() * 2 ** 30),
  windowSize = 4,
  onProgress = null,
} = {}) {
  const { notes, cycles } = await loadMetadata();

  // Phase 2 — 개인화 OM
  const { overlap, meta: omMeta } = buildPersonalOM(
    recording, notes, cycles, { T, K, window: windowSize }
  );

  // instLen — hibari 32-패턴 rolling
  const instLen = buildHibariInstLen(T);

  // Algo1 — NodePool/CycleSetManager
  const rng = makeRng(seed);
  const nodePool = new NodePool({
    labels: notes,
    numModules: 65,
    temperature,
    rng,
  });
  const cycleManager = new CycleSetManager({ cycles, K });

  const t0 = performance.now();
  const result = algorithm1({
    nodePool, cycleManager, instLen, overlap,
    maxResample: 50, rng, onProgress,
  });
  const elapsedMs = performance.now() - t0;

  const meta = {
    ...omMeta,
    seed,
    temperature,
    genElapsedMs: elapsedMs,
    numNotes: result.notes.length,
    resampleFails: result.resampleFails,
  };

  // Phase 3 — 재생 스케줄 (audio unlocked 상태 가정)
  const playback = schedulePlayback(result.notes, audio, { stepMs, T });

  return { notes: result.notes, meta, playback };
}

// notes : [[startEighth, pitch, endEighth], ...]
// 각 step = stepMs real time. 시간은 절대 시점 기준으로 한 번에 예약.
function schedulePlayback(notes, audio, { stepMs = 250, T = 120 } = {}) {
  const startMs = performance.now();
  const timers = [];

  for (const [s, pitch, e] of notes) {
    const delay   = s * stepMs;
    const durSec  = Math.max(0.15, (e - s) * stepMs / 1000 + 0.4);
    const handle  = setTimeout(() => {
      audio.note(pitch, { velocity: 0.55, dur: durSec });
    }, delay);
    timers.push(handle);
  }

  // 전체 구간이 끝나면 자동 해제
  const totalMs = T * stepMs + 1500;
  const endTimer = setTimeout(() => {}, totalMs);
  timers.push(endTimer);

  return {
    startMs,
    totalMs,
    stop() {
      for (const h of timers) clearTimeout(h);
      audio.stopAll(120);
    },
  };
}
