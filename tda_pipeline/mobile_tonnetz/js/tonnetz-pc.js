// Tonnetz pitch-class helpers.
// Neo-Riemannian Tonnetz: row-step = perfect fifth (+7), col-step = major third (+4).
// Each node = a pitch class (0..11). Triangles between neighbors form major/minor triads.
//
// Grid layout chosen for mobile: 4 rows × 6 cols = 24 nodes (with wrap in pitch-class space).
// Node (row r, col c) → pc = (row0 + r*7 + c*4) mod 12.

export const ROW0_PC = 0; // C anchor at top-left
export const ROWS = 4;
export const COLS = 6;

export function nodePC(r, c) {
  return ((ROW0_PC + r * 7 + c * 4) % 12 + 12) % 12;
}

// Map pc + scale context → actual MIDI pitch (octave picked by row for voice leading).
export function nodeMidi(r, c, baseOctave = 4) {
  const pc = nodePC(r, c);
  // Higher rows → higher octave (sphere "falling" down triggers lower pitches).
  const octave = baseOctave + (ROWS - 1 - r) * 0;  // keep flat octave; tweak per mode
  return 12 * (octave + 1) + pc;  // MIDI: C-1 = 0
}

// Short pitch-class names (Korean 고정도 solfège mixed with letters for compact UI).
export const PC_NAME = ['C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B'];

// Scale masks in pc space (1 = in-scale, 0 = out). Used by camera mode.
export const SCALES = {
  major:    [1,0,1,0,1,1,0,1,0,1,0,1],
  minor:    [1,0,1,1,0,1,0,1,1,0,1,0],  // natural minor
  phrygian: [1,1,0,1,0,1,0,1,1,0,1,0],
  hibari:   [1,0,1,0,1,1,0,1,0,1,0,1],  // placeholder = C major; real 저전 scale later
};

export function inScale(pc, scaleName, rootPc = 0) {
  const mask = SCALES[scaleName] || SCALES.major;
  return mask[((pc - rootPc) % 12 + 12) % 12] === 1;
}

// Resolve a node to nearest in-scale pitch (±1 semitone fallback).
export function resolveToScale(midi, scaleName, rootPc = 0) {
  const pc = ((midi % 12) + 12) % 12;
  if (inScale(pc, scaleName, rootPc)) return midi;
  // try +1 then -1
  for (const d of [-1, 1, -2, 2]) {
    const npc = ((pc + d) % 12 + 12) % 12;
    if (inScale(npc, scaleName, rootPc)) return midi + d;
  }
  return midi;
}
