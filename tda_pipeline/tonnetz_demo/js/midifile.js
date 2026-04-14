/**
 * midifile.js — MIDI file playback for TonnetzViz
 *
 * Depends on:
 *   - Tone.js  (global: Tone)
 *   - @tonejs/midi  (global: Midi)
 *   - window.tonnetz  (set in main.js)
 *
 * Public API:
 *   loadAndPlayMidi(file)  — load a File object and start playback
 *   pauseMidi()            — toggle pause/resume
 *   stopMidi()             — stop and reset
 */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────
  var midiDuration = 0;   // total duration in seconds
  var timerID      = null;
  var MIDI_CHANNEL = 0;   // channel index passed to tonnetz.noteOn/Off

  // ── Recording state ─────────────────────────────────────────────
  var recorder       = null;
  var recordedChunks = [];
  var isRecording    = false;

  // ── UI element references (available after DOMContentLoaded) ───────
  function ui(id) { return document.getElementById(id); }

  function setStatus(text, cls) {
    var el = ui('playStatus');
    el.textContent = text;
    el.className = 'label label-' + (cls || 'default');
  }

  function formatTime(sec) {
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function startTimer() {
    stopTimer();
    timerID = setInterval(function () {
      if (Tone.Transport.state === 'started') {
        var pos = Tone.Transport.seconds;
        ui('playTime').textContent = formatTime(pos) + ' / ' + formatTime(midiDuration);
      }
    }, 250);
  }

  function stopTimer() {
    if (timerID !== null) {
      clearInterval(timerID);
      timerID = null;
    }
    ui('playTime').textContent = '0:00 / ' + formatTime(midiDuration);
  }

  // ── Core: load + schedule ──────────────────────────────────────────
  async function loadAndPlayMidi(file) {
    if (!file) return;

    try {
      setStatus('Loading…', 'info');

      var buffer = await file.arrayBuffer();
      var midi   = new Midi(buffer);

      // Compute total duration
      midiDuration = midi.duration;

      // Resume AudioContext (required after user gesture)
      await Tone.start();

      // Cancel previous playback completely
      stopMidi();

      // Schedule all note on/off events
      midi.tracks.forEach(function (track) {
        track.notes.forEach(function (note) {
          Tone.Transport.schedule(function () {
            if (window.tonnetz) window.tonnetz.noteOn(MIDI_CHANNEL, note.midi);
          }, note.time);

          Tone.Transport.schedule(function () {
            if (window.tonnetz) window.tonnetz.noteOff(MIDI_CHANNEL, note.midi);
          }, note.time + note.duration);
        });
      });

      // Auto-stop at end of file
      Tone.Transport.schedule(function () {
        stopMidi();
        setStatus('Finished', 'success');
        ui('playTime').textContent = formatTime(midiDuration) + ' / ' + formatTime(midiDuration);
      }, midiDuration + 0.1);

      window._midiDuration = midiDuration;  // expose for cursor update
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
      // Silence any held notes on the tonnetz
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
    if (window.tonnetz) window.tonnetz.allNotesOff(MIDI_CHANNEL);
    stopTimer();
    setStatus('Stopped', 'default');
  }

  // ── Wire up buttons after DOM is ready ────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    ui('playBtn').addEventListener('click', function () {
      var file = ui('midiFileInput').files[0];
      if (!file) {
        setStatus('No file selected', 'danger');
        return;
      }
      loadAndPlayMidi(file);
    });

    ui('pauseBtn').addEventListener('click', function () {
      pauseMidi();
    });

    ui('stopBtn').addEventListener('click', function () {
      stopMidi();
    });

    ui('recordBtn').addEventListener('click', function () {
      toggleRecording();
    });

    // Allow re-selecting a file while paused/playing
    ui('midiFileInput').addEventListener('change', function () {
      stopMidi();
      midiDuration = 0;
      ui('playTime').textContent = '0:00 / 0:00';
    });
  });

  // ── Recording ────────────────────────────────────────────────────
  function toggleRecording() {
    if (!isRecording) {
      startRecording();
    } else {
      stopRecording();
    }
  }

  function startRecording() {
    var canvas = document.getElementById('canvas');
    if (!canvas) { alert('Canvas not found'); return; }

    recordedChunks = [];
    var tracks = [];

    // 1) 캔버스 비디오 스트림 (30 fps)
    var videoStream = canvas.captureStream(30);
    videoStream.getTracks().forEach(function(t) { tracks.push(t); });

    // 2) Tone.js 오디오 스트림 (Web Audio → MediaStream)
    try {
      var rawCtx = Tone.getContext().rawContext;
      var audioDest = rawCtx.createMediaStreamDestination();
      // Tone.js master output → audioDest
      Tone.getDestination().connect(audioDest);
      audioDest.stream.getTracks().forEach(function(t) { tracks.push(t); });
    } catch(e) {
      console.warn('Audio capture unavailable:', e);
    }

    var combined = new MediaStream(tracks);

    // 지원 코덱 선택 (webm/vp9 우선, 없으면 기본)
    var mimeType = '';
    ['video/webm;codecs=vp9,opus',
     'video/webm;codecs=vp8,opus',
     'video/webm'].forEach(function(m) {
      if (!mimeType && MediaRecorder.isTypeSupported(m)) mimeType = m;
    });

    recorder = new MediaRecorder(combined, mimeType ? { mimeType: mimeType } : {});
    recorder.ondataavailable = function(e) {
      if (e.data && e.data.size > 0) recordedChunks.push(e.data);
    };
    recorder.onstop = function() {
      var blob = new Blob(recordedChunks, { type: 'video/webm' });
      var url  = URL.createObjectURL(blob);
      var a    = document.createElement('a');
      a.href     = url;
      a.download = 'tonnetz_hibari_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.webm';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function() { URL.revokeObjectURL(url); }, 5000);
    };

    recorder.start(200);  // 200ms 단위로 chunk
    isRecording = true;

    var btn = ui('recordBtn');
    btn.classList.add('btn-danger');
    btn.classList.remove('btn-default');
    btn.innerHTML = '<i class="fa fa-stop-circle"></i> STOP REC';
    ui('recStatus').style.display = 'inline';
  }

  function stopRecording() {
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    isRecording = false;

    var btn = ui('recordBtn');
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-default');
    btn.innerHTML = '<i class="fa fa-circle" style="color:#c00"></i> REC';
    ui('recStatus').style.display = 'none';
  }

  // ── Expose for console debugging ──────────────────────────────────
  window.midiPlayer = { load: loadAndPlayMidi, pause: pauseMidi, stop: stopMidi,
                        startRec: startRecording, stopRec: stopRecording };

})();
