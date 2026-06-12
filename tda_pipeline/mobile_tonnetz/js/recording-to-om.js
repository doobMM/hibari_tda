// recording-to-om.js — Phase 2: 사용자 녹음 경로 → 개인화 OM (T × K=14).
//
// 입력
//   recording : [{step, pc, r, c, midi}, ...]  — 사용자가 30초 동안 방문한 노드
//   notes     : notes_metadata.labels          — 23개 note (pc/pitch/dur)
//   cycles    : cycles_metadata.cycles         — 14개 cycle (note_labels_0idx)
//   T         : 전체 타임스텝 수 (기본 120, 8분음표 × 30s)
//   window    : 각 t 에서 "활성"으로 간주할 rolling window 크기 (8분음표 단위)
//
// 출력
//   { T, K, values } — values: Int8Array(T*K)  — Algorithm 1 overlap 포맷
//   meta            — 활성 통계 (UI 표시용)
//
// 설계
//   1. 녹음된 PC 를 stepToPCs : step → Set<pc> 로 인덱싱.
//   2. 각 cycle 에 대해, 그 cycle 이 포함하는 note 들의 PC 집합을 미리 구축.
//   3. 각 t 에서 [t-window+1, t] 구간에 사용자가 친 PC 들의 집합을 만들고,
//      각 cycle 의 PC 집합과 교집합이 있으면 그 cycle 은 t 시점에서 활성 (=1).
//
//   이 방식은 user path 를 "최근에 친 음들과 topologically 가까운 cycle 들"
//   을 활성화하는 개인화 OM 으로 변환한다. 원 hibari OM 과 정확히 같지 않지만,
//   사용자의 움직임을 반영해 Algo1 샘플러에 서로 다른 cycle context 를 공급한다.

export function buildPersonalOM(recording, notes, cycles, {
  T = 120, K = 14, window = 4,
} = {}) {
  const values = new Int8Array(T * K);

  // note label_idx → pc lookup
  const idxToPc = new Map();
  for (const n of notes) idxToPc.set(n.label_idx, n.pc);

  // cycle k → Set<pc>
  const cyclePCs = new Array(K);
  for (let k = 0; k < K; k++) cyclePCs[k] = new Set();
  for (const cy of cycles) {
    const kIdx = cy.cycle_idx;
    if (kIdx < 0 || kIdx >= K) continue;
    const noteIdxList = Array.isArray(cy.note_labels_0idx)
      ? cy.note_labels_0idx
      : (Array.isArray(cy.vertices_0idx) ? cy.vertices_0idx : []);
    for (const idx of noteIdxList) {
      const pc = idxToPc.get(idx);
      if (pc !== undefined) cyclePCs[kIdx].add(pc);
    }
  }

  // step → Set<pc>
  const stepToPCs = new Map();
  for (const rec of recording) {
    const s = rec.step | 0;
    if (s < 0 || s >= T) continue;
    let set = stepToPCs.get(s);
    if (!set) { set = new Set(); stepToPCs.set(s, set); }
    set.add(rec.pc);
  }

  let activeCellCount = 0;
  let activeStepCount = 0;

  // 각 t 에서 window 내 PC 집합 만들고 cycle 활성 판정
  for (let t = 0; t < T; t++) {
    const windowPCs = new Set();
    for (let dt = -window + 1; dt <= 0; dt++) {
      const s = t + dt;
      if (s < 0) continue;
      const set = stepToPCs.get(s);
      if (set) for (const pc of set) windowPCs.add(pc);
    }
    if (windowPCs.size === 0) continue;

    let anyActive = false;
    for (let k = 0; k < K; k++) {
      const cyc = cyclePCs[k];
      let hit = false;
      for (const pc of cyc) {
        if (windowPCs.has(pc)) { hit = true; break; }
      }
      if (hit) {
        values[t * K + k] = 1;
        activeCellCount++;
        anyActive = true;
      }
    }
    if (anyActive) activeStepCount++;
  }

  return {
    overlap: { T, K, values },
    meta: {
      T, K,
      recordingSteps: recording.length,
      uniqueStepsCovered: stepToPCs.size,
      activeSteps: activeStepCount,
      activeCells: activeCellCount,
      density: activeCellCount / (T * K),
    },
  };
}
