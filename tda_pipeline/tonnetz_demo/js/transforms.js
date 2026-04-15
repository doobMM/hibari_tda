/**
 * transforms.js — Real-time pitch transforms for TonnetzViz
 *
 * Three operation groups applied during MIDI playback:
 *   1. P / L / R / N / S / H  Neo-Riemannian triadic transforms
 *   2. T_n  Transpositions  (continuous semitone offset)
 *   3. I_n  Inversions      (pitch-class reflection around an axis)
 *
 * Public API
 *   transforms.apply(midiPitch) → midiPitch
 *       Applied to every incoming noteOn/noteOff in midifile.js.
 *   transforms.applyPLR(op)
 *       One-shot: fires on currently lit tonnetz pitch-classes.
 *   transforms.setTranspose(n)
 *   transforms.setInvert(enabled [, axis])
 *   transforms.reset()
 */

var transforms = (function () {
  'use strict';

  var module = {};

  // ── dedicated channel for PLR output (must be within CHANNELS=17) ──
  var PLR_CH = 15;

  // ── State ──────────────────────────────────────────────────────────
  module.offset     = 0;       // continuous transpose (semitones, any integer)
  module.invEnabled = false;
  module.invAxis    = 0;       // 0-11

  // ── apply: map a raw MIDI pitch to a transformed MIDI pitch ────────
  module.apply = function (pitch) {
    var p = pitch | 0;

    if (module.invEnabled) {
      var pc     = ((p % 12) + 12) % 12;
      var octave = Math.floor(p / 12);
      pc = ((2 * module.invAxis - pc) % 12 + 12) % 12;
      p  = octave * 12 + pc;
    }

    p += module.offset;

    // Keep in MIDI range [0, 127] by octave-clamping
    while (p < 0)   p += 12;
    while (p > 127) p -= 12;

    return p;
  };

  // ── setTranspose ───────────────────────────────────────────────────
  module.setTranspose = function (n) {
    module.offset = n | 0;
    updateUI();
  };

  // ── setInvert ─────────────────────────────────────────────────────
  module.setInvert = function (enabled, axis) {
    module.invEnabled = !!enabled;
    if (axis !== undefined) module.invAxis = ((axis | 0) % 12 + 12) % 12;
    updateUI();
  };

  // ── reset ──────────────────────────────────────────────────────────
  module.reset = function () {
    module.offset     = 0;
    module.invEnabled = false;
    module.invAxis    = 0;
    if (window.tonnetz) window.tonnetz.allNotesOff(PLR_CH);
    updateUI();
  };


  // ════════════════════════════════════════════════════════════════════
  //  Neo-Riemannian helpers
  // ════════════════════════════════════════════════════════════════════

  // triad → 3-element pitch-class array
  function triadPCs(t) {
    var r = t.root;
    return t.q === 'M'
      ? [r, (r + 4) % 12, (r + 7) % 12]
      : [r, (r + 3) % 12, (r + 7) % 12];
  }

  // Given a set of pitch classes, find the best-matching major/minor triad.
  // Returns {root, q} or null.
  function identifyTriad(pcs) {
    var set = {};
    pcs.forEach(function (p) { set[((p % 12) + 12) % 12] = true; });

    var best = null, bestScore = 0;
    for (var r = 0; r < 12; r++) {
      var mScore = (set[r] ? 1 : 0) + (set[(r + 4) % 12] ? 1 : 0) + (set[(r + 7) % 12] ? 1 : 0);
      var nScore = (set[r] ? 1 : 0) + (set[(r + 3) % 12] ? 1 : 0) + (set[(r + 7) % 12] ? 1 : 0);
      if (mScore > bestScore) { bestScore = mScore; best = { root: r, q: 'M' }; }
      if (nScore > bestScore) { bestScore = nScore; best = { root: r, q: 'm' }; }
    }
    return bestScore >= 2 ? best : null;
  }

  // Apply one Neo-Riemannian op to a triad descriptor
  function applyOp(op, t) {
    var r = t.root, q = t.q;
    switch (op) {
      case 'P': return { root: r,           q: q === 'M' ? 'm' : 'M' };
      case 'L': return q === 'M' ? { root: (r + 4)  % 12, q: 'm' }
                                 : { root: (r + 8)  % 12, q: 'M' };
      case 'R': return q === 'M' ? { root: (r + 9)  % 12, q: 'm' }
                                 : { root: (r + 3)  % 12, q: 'M' };
      case 'N': return applyOp('P', applyOp('L', applyOp('R', t)));  // Nebenverwandt
      case 'S': return applyOp('L', applyOp('P', applyOp('R', t)));  // Slide
      case 'H': return applyOp('L', applyOp('P', applyOp('L', t)));  // Hexatonic pole
      default:  return t;
    }
  }

  // ── applyPLR: acts on currently lit pitch classes ──────────────────
  var plrTimeout = null;

  module.applyPLR = function (op) {
    if (!window.tonnetz) return;

    var activePCs = window.tonnetz.getActivePC();
    if (activePCs.length < 2) return;

    var triad = identifyTriad(activePCs);
    if (!triad) return;

    var newTriad = applyOp(op, triad);
    var newPCs   = triadPCs(newTriad);
    var oldPCs   = triadPCs(triad);

    // Clear previous PLR channel notes
    window.tonnetz.allNotesOff(PLR_CH);
    if (plrTimeout) clearTimeout(plrTimeout);

    // Fire new triad on PLR channel (octave 4: MIDI 60-71)
    newPCs.forEach(function (pc) {
      window.tonnetz.noteOn(PLR_CH, 60 + pc);
    });

    // Flash the button name briefly
    flashPLRLabel(op, newTriad);

    // Auto-release after 2.5 s so MIDI playback can reassert
    plrTimeout = setTimeout(function () {
      window.tonnetz.allNotesOff(PLR_CH);
      plrTimeout = null;
    }, 2500);
  };


  // ════════════════════════════════════════════════════════════════════
  //  UI helpers
  // ════════════════════════════════════════════════════════════════════

  var NOTE_NAMES = ['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'];

  function flashPLRLabel(op, newTriad) {
    var el = document.getElementById('plrResult');
    if (!el) return;
    var name = NOTE_NAMES[newTriad.root] + (newTriad.q === 'M' ? ' maj' : ' min');
    el.textContent = op + ' → ' + name;
    el.style.opacity = '1';
    setTimeout(function () { el.style.opacity = '0'; }, 2000);
  }

  function updateUI() {
    var el;

    // Transpose display
    el = document.getElementById('txOffset');
    if (el) el.textContent = (module.offset >= 0 ? '+' : '') + module.offset;

    // Invert toggle button
    el = document.getElementById('txInvToggle');
    if (el) {
      if (module.invEnabled) {
        el.textContent = 'ON';
        el.className   = el.className.replace('btn-default', 'btn-info');
        if (el.className.indexOf('btn-info') === -1) el.className += ' btn-info';
      } else {
        el.textContent = 'OFF';
        el.className   = el.className.replace('btn-info', 'btn-default');
      }
    }

    // Axis buttons
    for (var i = 0; i < 12; i++) {
      var btn = document.getElementById('txAxis' + i);
      if (!btn) continue;
      if (i === module.invAxis && module.invEnabled) {
        btn.className = btn.className.replace('btn-default', 'btn-primary');
        if (btn.className.indexOf('btn-primary') === -1) btn.className += ' btn-primary';
      } else {
        btn.className = btn.className.replace('btn-primary', 'btn-default');
      }
    }
  }

  // Expose globally
  window.transforms = module;
  return module;
})();
