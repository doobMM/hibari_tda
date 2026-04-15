/**
 * midifile.js — MIDI file playback for TonnetzViz
 *
 * Depends on:
 *   - Tone.js          (global: Tone)
 *   - @tonejs/midi     (global: Midi)
 *   - window.tonnetz   (set in main.js)
 *   - window.transforms (from transforms.js — optional, graceful fallback)
 *   - window.PRELOADED_MIDI  (from preloaded_midi.js — optional auto-load)
 *
 * Public API:
 *   loadAndPlayMidi(arrayBuffer | File)
 *   pauseMidi()
 *   stopMidi()
 */

(function () {
  "use strict";

  var MIDI_CHANNEL = 0;

  // noteMap: tracks originalPitch+startTime → transformedPitch
  // so noteOff always matches the transformed pitch used at noteOn time.
  var noteMap = {};

  var midiDuration = 0;
  var timerID      = null;

  // ── Recording state ──────────────────────────────────────────────
  var recorder       = null;
  var recordedChunks = [];
  var isRecording    = false;

  // ── UI helpers ────────────────────────────────────────────────────
  function ui(id) { return document.getElementById(id); }

  function setStatus(text, cls) {
    var el = ui('playStatus');
    if (!el) return;
    el.textContent = text;
    el.className   = 'label label-' + (cls || 'default');
  }

  function formatTime(sec) {
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function setProgress(frac) {
    var fill = ui('midiProgressFill');
    if (fill) fill.style.width = Math.min(1, Math.max(0, frac)) * 100 + '%';
  }

  function startTimer() {
    stopTimer();
    timerID = setInterval(function () {
      if (Tone.Transport.state === 'started') {
        var pos = Tone.Transport.seconds;
        ui('playTime').textContent = formatTime(pos) + ' / ' + formatTime(midiDuration);
        if (midiDuration > 0) setProgress(pos / midiDuration);
      }
    }, 250);
  }

  function stopTimer() {
    if (timerID !== null) { clearInterval(timerID); timerID = null; }
    var el = ui('playTime');
    if (el) el.textContent = '0:00 / ' + formatTime(midiDuration);
  }

  // ── Core schedule ─────────────────────────────────────────────────
  function scheduleBuffer(buffer) {
    var midi = new Midi(buffer);
    midiDuration = midi.duration;
    noteMap = {};

    midi.tracks.forEach(function (track) {
      track.notes.forEach(function (note) {
        var origPitch  = note.midi;
        var startTime  = note.time;
        var mapKey     = origPitch + ':' + startTime.toFixed(4);

        Tone.Transport.schedule(function () {
          var tp = window.transforms ? window.transforms.apply(origPitch) : origPitch;
          noteMap[mapKey] = tp;
          if (window.tonnetz) window.tonnetz.noteOn(MIDI_CHANNEL, tp);
        }, startTime);

        Tone.Transport.schedule(function () {
          var tp = (noteMap[mapKey] !== undefined)
                    ? noteMap[mapKey]
                    : (window.transforms ? window.transforms.apply(origPitch) : origPitch);
          delete noteMap[mapKey];
          if (window.tonnetz) window.tonnetz.noteOff(MIDI_CHANNEL, tp);
        }, startTime + note.duration);
      });
    });

    // Auto-stop sentinel
    Tone.Transport.schedule(function () {
      stopMidi();
      setStatus('Finished', 'success');
      var el = ui('playTime');
      if (el) el.textContent = formatTime(midiDuration) + ' / ' + formatTime(midiDuration);
    }, midiDuration + 0.1);

    window._midiDuration = midiDuration;
  }

  // ── loadAndPlayMidi: accepts ArrayBuffer or File ──────────────────
  async function loadAndPlayMidi(source) {
    if (!source) return;

    try {
      setStatus('Loading…', 'info');

      var buffer = (source instanceof ArrayBuffer) ? source : await source.arrayBuffer();

      await Tone.start();
      stopMidi();
      scheduleBuffer(buffer);

      Tone.Transport.start();
      setStatus('Playing', 'success');
      startTimer();

    } catch (err) {
      console.error('midifile.js:', err);
      setStatus('Error: ' + err.message, 'danger');
    }
  }

  function pauseMidi() {
    if (Tone.Transport.state === 'started') {
      Tone.Transport.pause();
      if (window.tonnetz) window.tonnetz.allNotesOff(MIDI_CHANNEL);
      setStatus('Paused', 'warning');
      stopTimer();
    } else if (Tone.Transport.state === 'paused') {
      Tone.Transport.start();
      setStatus('Playing', 'success');
      startTimer();
    }
  }

  function stopMidi() {
    Tone.Transport.stop();
    Tone.Transport.cancel();
    noteMap = {};
    if (window.tonnetz) window.tonnetz.allNotesOff(MIDI_CHANNEL);
    stopTimer();
    setProgress(0);
    setStatus('Stopped', 'default');
  }

  // ── Preloaded songs — decode all PRELOADED_MIDI entries ───────────
  function loadAllPreloaded() {
    if (typeof PRELOADED_MIDI === 'undefined') return;
    window._preloadedBuffers = {};
    Object.keys(PRELOADED_MIDI).forEach(function (key) {
      try {
        var raw   = atob(PRELOADED_MIDI[key].b64);
        var bytes = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
        window._preloadedBuffers[key] = bytes.buffer;
        if (key === 'hibari') window._hibariBuffer = bytes.buffer; // backward compat
      } catch (e) {
        console.warn('preload failed:', key, e);
      }
    });
    setStatus('songs ready ▶', 'info');
  }

  // ── Recording ─────────────────────────────────────────────────────
  function toggleRecording() {
    if (!isRecording) startRecording(); else stopRecording();
  }

  function startRecording() {
    var canvas = document.getElementById('canvas');
    if (!canvas) { alert('Canvas not found'); return; }

    recordedChunks = [];
    var tracks = [];

    var videoStream = canvas.captureStream(30);
    videoStream.getTracks().forEach(function (t) { tracks.push(t); });

    try {
      var rawCtx    = Tone.getContext().rawContext;
      var audioDest = rawCtx.createMediaStreamDestination();
      Tone.getDestination().connect(audioDest);
      audioDest.stream.getTracks().forEach(function (t) { tracks.push(t); });
    } catch (e) { console.warn('Audio capture unavailable:', e); }

    var combined = new MediaStream(tracks);
    var mimeType = '';
    ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
      .forEach(function (m) { if (!mimeType && MediaRecorder.isTypeSupported(m)) mimeType = m; });

    recorder = new MediaRecorder(combined, mimeType ? { mimeType: mimeType } : {});
    recorder.ondataavailable = function (e) { if (e.data && e.data.size > 0) recordedChunks.push(e.data); };
    recorder.onstop = function () {
      var blob = new Blob(recordedChunks, { type: 'video/webm' });
      var url  = URL.createObjectURL(blob);
      var a    = document.createElement('a');
      a.href = url; a.download = 'tonnetz_' + new Date().toISOString().slice(0, 19).replace(/:/g, '-') + '.webm';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
    };

    recorder.start(200);
    isRecording = true;

    var btn = ui('recordBtn');
    btn.classList.add('btn-danger'); btn.classList.remove('btn-default');
    btn.innerHTML = '<i class="fa fa-stop-circle"></i> STOP REC';
    var rs = ui('recStatus'); if (rs) rs.style.display = 'inline';
  }

  function stopRecording() {
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    isRecording = false;

    var btn = ui('recordBtn');
    btn.classList.remove('btn-danger'); btn.classList.add('btn-default');
    btn.innerHTML = '<i class="fa fa-circle" style="color:#c00"></i> REC';
    var rs = ui('recStatus'); if (rs) rs.style.display = 'none';
  }

  // ── Wire up after DOM ready ───────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {

    // Decode all preloaded songs
    loadAllPreloaded();

    // Preloaded song buttons (event delegation on #preloadedSongs)
    var songsContainer = ui('preloadedSongs');
    if (songsContainer) {
      songsContainer.addEventListener('click', function (e) {
        var btn = e.target.closest ? e.target.closest('.preload-btn') : null;
        if (!btn) return;
        var key = btn.getAttribute('data-key');
        if (!window._preloadedBuffers || !window._preloadedBuffers[key]) {
          setStatus(key + ' not loaded', 'danger');
          return;
        }
        // Highlight active button
        songsContainer.querySelectorAll('.preload-btn').forEach(function (b) {
          b.classList.remove('btn-success');
          b.classList.add('btn-default');
        });
        btn.classList.remove('btn-default');
        btn.classList.add('btn-success');
        loadAndPlayMidi(window._preloadedBuffers[key].slice(0));
      });
    }

    // Play custom file button
    ui('playBtn').addEventListener('click', function () {
      var file = ui('midiFileInput').files[0];
      if (!file) {
        // Fall back to first available preloaded song
        var buf = window._preloadedBuffers;
        var fallbackKey = buf && (buf['bach'] || buf['ravel'] || buf['clair']);
        if (fallbackKey) {
          var key = buf['bach'] ? 'bach' : (buf['ravel'] ? 'ravel' : 'clair');
          loadAndPlayMidi(buf[key].slice(0));
        } else {
          setStatus('No file selected', 'danger');
        }
        return;
      }
      loadAndPlayMidi(file);
    });

    ui('pauseBtn').addEventListener('click', pauseMidi);
    ui('stopBtn').addEventListener('click', stopMidi);
    ui('recordBtn').addEventListener('click', toggleRecording);

    // Progress bar — click to seek
    var progressBar = ui('midiProgress');
    if (progressBar) {
      progressBar.addEventListener('click', function (e) {
        if (!midiDuration || Tone.Transport.state === 'stopped') return;
        var rect = progressBar.getBoundingClientRect();
        var frac = (e.clientX - rect.left) / rect.width;
        var seekTime = Math.max(0, Math.min(midiDuration, frac * midiDuration));
        Tone.Transport.seconds = seekTime;
        setProgress(frac);
      });
    }

    ui('midiFileInput').addEventListener('change', function () {
      stopMidi();
      midiDuration = 0;
      var el = ui('playTime'); if (el) el.textContent = '0:00 / 0:00';
    });
  });

  window.midiPlayer = { load: loadAndPlayMidi, pause: pauseMidi, stop: stopMidi };
})();
