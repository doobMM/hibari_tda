/**
 * touch.js — Touch & mouse click support for Tonnetz canvas
 *
 * Allows users to play notes by:
 *   - Tapping / dragging on the canvas (mobile touch)
 *   - Clicking / dragging on the canvas (desktop mouse)
 *
 * Finds the nearest Tonnetz node to the pointer position via
 * tonnetz.pitchFromXY(x, y), then calls noteOn/noteOff.
 *
 * Multi-touch: each touch identifier tracks its own held pitch,
 * so sliding a finger glides to the nearest new note.
 */
(function () {
  'use strict';

  var TOUCH_CH  = 16;   // same channel as computer keyboard
  var BASE_NOTE = 60;   // middle C — all tap notes are in octave 4/5

  // id (touch identifier or 'mouse') → currently held MIDI pitch
  var held = {};

  function press(id, x, y) {
    if (!window.tonnetz) return;
    var pc = tonnetz.pitchFromXY(x, y);
    if (pc < 0) return;
    var pitch = BASE_NOTE + pc;
    if (held[id] !== undefined) {
      if (held[id] === pitch) return;           // same node — no change
      tonnetz.noteOff(TOUCH_CH, held[id]);      // glide: release old note
    }
    held[id] = pitch;
    tonnetz.noteOn(TOUCH_CH, pitch);
  }

  function release(id) {
    if (held[id] !== undefined) {
      tonnetz.noteOff(TOUCH_CH, held[id]);
      delete held[id];
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var tz = document.getElementById('tonnetz');
    if (!tz) return;

    // ── Touch events (mobile) ──────────────────────────────────────
    tz.addEventListener('touchstart', function (e) {
      e.preventDefault();
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        press(t.identifier, t.clientX, t.clientY);
      }
    }, { passive: false });

    tz.addEventListener('touchmove', function (e) {
      e.preventDefault();
      for (var i = 0; i < e.changedTouches.length; i++) {
        var t = e.changedTouches[i];
        press(t.identifier, t.clientX, t.clientY);
      }
    }, { passive: false });

    tz.addEventListener('touchend', function (e) {
      e.preventDefault();
      for (var i = 0; i < e.changedTouches.length; i++) {
        release(e.changedTouches[i].identifier);
      }
    }, { passive: false });

    tz.addEventListener('touchcancel', function (e) {
      for (var i = 0; i < e.changedTouches.length; i++) {
        release(e.changedTouches[i].identifier);
      }
    });

    // ── Mouse click / drag (desktop) ──────────────────────────────
    var dragging = false;

    tz.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      dragging = true;
      press('mouse', e.clientX, e.clientY);
    });

    tz.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      press('mouse', e.clientX, e.clientY);
    });

    // Release on mouseup anywhere on document (handles drag-out-of-canvas)
    document.addEventListener('mouseup', function () {
      if (dragging) { release('mouse'); dragging = false; }
    });
  });
})();
