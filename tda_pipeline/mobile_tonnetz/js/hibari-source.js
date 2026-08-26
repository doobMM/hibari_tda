// hibari-source.js — 세 모드가 공유하는 **진짜 hibari 생성기**
//
// 종전에 shake·camera 는 임의 음높이를 음계에 맞추는 mock 이었다
// (소스 주석: "Mock Algorithm 1 ... Replace with real hibari notes_metadata.json").
// 이 모듈이 그 자리를 채운다 — 실제 hibari 의 note 어휘와 위상 구조(중첩행렬)로
// Algorithm 1 을 돌린다. tilt 가 쓰는 `generator.js` 는 "녹음 → 개인화 OM" 흐름이라
// 실시간 모드에는 맞지 않아, 여기서는 미리 계산된 **참조 OM 뱅크**를 쓴다.
//
// 뱅크는 α(두 음악적 거리를 섞는 비율) 6단계다. 양 끝에서 위상이 무너져 cycle 이
// 하나만 남고 가운데에서 풍부해진다 — 그 차이가 그대로 들린다.

import { NodePool, CycleSetManager, algorithm1, makeRng, buildHibariInstLen }
  from './generation-algo1.js';

let _bank = null, _notes = null;

export async function loadHibari() {
  if (_bank) return { bank: _bank, notes: _notes };
  const [b, n] = await Promise.all([
    fetch('./data/om_bank.json').then(r => r.json()),
    fetch('./data/notes_metadata.json').then(r => r.json()),
  ]);
  _bank = b; _notes = n.labels;
  return { bank: _bank, notes: _notes };
}

export function bankSize() { return _bank ? _bank.banks.length : 0; }
export function bankAlpha(i) { return _bank ? _bank.banks[i].alpha : null; }
export function bankK(i) { return _bank ? _bank.banks[i].K : null; }

/**
 * 뱅크 하나에서 30초 분량을 생성한다.
 * @returns {{notes: Array<[startSec, midi, endSec]>, K: number, alpha: number, n: number}}
 */
export function generateFromBank(bankIdx, seed) {
  if (!_bank) throw new Error('loadHibari() 를 먼저 호출해야 한다');
  const b = _bank.banks[Math.max(0, Math.min(_bank.banks.length - 1, bankIdx | 0))];
  const { T, K } = b;
  const values = new Int8Array(T * K);
  for (let i = 0; i < values.length; i++) values[i] = b.om_bits.charCodeAt(i) === 49 ? 1 : 0;

  const rng = makeRng(seed >>> 0 || 1);
  // temperature 1.0 — 3.0 의 근거(§7.7.3)는 2026-08-15 철회됐다.
  const nodePool = new NodePool({ labels: _notes, numModules: 65, temperature: 1.0, rng });
  const cycleManager = new CycleSetManager({
    cycles: b.cycles.map((v, i) => ({ cycle_idx: i, note_labels_0idx: v })), K,
  });
  const res = algorithm1({
    nodePool, cycleManager, instLen: buildHibariInstLen(T),
    overlap: { T, K, values }, maxResample: 50, rng,
  });
  const sec = _bank.step_ms / 1000;
  return {
    notes: res.notes.map(n => [n[0] * sec, n[1], n[2] * sec]),
    K, alpha: b.alpha, n: res.notes.length,
  };
}

/** AudioEngine 으로 스케줄 재생. 이미 재생 중이면 갈아탄다. */
export function playNotes(audio, notes, { velocity = 0.5 } = {}) {
  audio.stopAll(80);
  const t0 = performance.now();
  const timers = [];
  for (const [s, midi, e] of notes) {
    const id = setTimeout(() => {
      try { audio.note(midi, { velocity, dur: Math.max(0.12, e - s) }); } catch (_) {}
    }, Math.max(0, s * 1000 - (performance.now() - t0)));
    timers.push(id);
  }
  return () => timers.forEach(clearTimeout);
}
