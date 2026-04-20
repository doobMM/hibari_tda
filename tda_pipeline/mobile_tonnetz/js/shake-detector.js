import { AudioEngine } from './audio-engine.js';
import { PC_NAME, resolveToScale } from './tonnetz-pc.js';
import { requestSensorPermission } from './sensor-permission.js';

const SESSION_SEC = 30;
const BPM = 120;
const STEP_MS = (60 / BPM / 2) * 1000; // 8th
const TOTAL_STEPS = 60;

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const hudTime = document.getElementById('hudTime');
const btnStart = document.getElementById('btnStart');
const btnShake = document.getElementById('btnShake');
const btnPerm = document.getElementById('btnPerm');
const overlay = document.getElementById('perm');

const audio = new AudioEngine();

let dpr = Math.max(1, window.devicePixelRatio || 1);
let W = 0, H = 0;
let running = false;
let startT = 0;
let lastStep = -1;

// Mock Algorithm 1 state — maintained pitch pool + transition matrix.
// Replace with real hibari notes_metadata.json when integrating with R1.
const SCALES = ['major', 'minor', 'phrygian'];
let state = freshSeed();

function freshSeed() {
  const seed = Math.floor(Math.random() * 1e6);
  const r = seededRng(seed);
  return {
    seed,
    scaleIdx: Math.floor(r() * SCALES.length),
    rootPc: Math.floor(r() * 12),
    pitches: Array.from({length: 8}, () => 48 + Math.floor(r() * 24)),
    rng: r,
    createdAt: performance.now(),
  };
}

function seededRng(seed) {
  let s = seed | 0;
  return function() {
    s = (s * 1664525 + 1013904223) | 0;
    return ((s >>> 0) % 1_000_000) / 1_000_000;
  };
}

// Shake detection via DeviceMotion
let accelHistory = [];
let lastShakeT = 0;
function onMotion(e) {
  const a = e.accelerationIncludingGravity || e.acceleration;
  if (!a) return;
  const mag = Math.hypot(a.x || 0, a.y || 0, a.z || 0);
  const now = performance.now();
  accelHistory.push({t: now, m: mag});
  accelHistory = accelHistory.filter(h => now - h.t < 600);
  // Detect sudden spike: high max - min in last window
  if (accelHistory.length >= 4) {
    const ms = accelHistory.map(h => h.m);
    const max = Math.max(...ms), min = Math.min(...ms);
    if (max - min > 22 && now - lastShakeT > 800) {
      lastShakeT = now;
      triggerShake();
    }
  }
}

function triggerShake() {
  state = freshSeed();
  // visual pulse
  shakePulse = 1.0;
}

function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener('resize', resize);

let shakePulse = 0;

function step(now) {
  if (running) {
    const elapsed = (now - startT) / 1000;
    const left = Math.max(0, SESSION_SEC - elapsed);
    hudTime.textContent = left.toFixed(1) + 's';
    const cur = Math.floor(elapsed * 1000 / STEP_MS);
    if (cur !== lastStep && cur < TOTAL_STEPS) {
      lastStep = cur;
      tick();
    }
    if (elapsed >= SESSION_SEC) stop();
  } else {
    hudTime.textContent = SESSION_SEC.toFixed(1) + 's';
  }
  draw();
  requestAnimationFrame(step);
}

function tick() {
  const r = state.rng;
  // Pick from the pool, mutate towards scale.
  const pick = state.pitches[Math.floor(r() * state.pitches.length)];
  const scaleName = SCALES[state.scaleIdx];
  const midi = resolveToScale(pick, scaleName, state.rootPc);
  audio.note(midi, {velocity: 0.55, dur: 0.35});
}

function draw() {
  ctx.fillStyle = '#0a0a12';
  ctx.fillRect(0, 0, W, H);
  shakePulse = Math.max(0, shakePulse - 0.02);
  // Big seed chip
  const cx = W / 2, cy = H / 2 - 20;
  const rad = 70 + shakePulse * 30;
  const g = ctx.createRadialGradient(cx, cy, 10, cx, cy, rad);
  g.addColorStop(0, `rgba(255,180,120,${0.8 + shakePulse * 0.2})`);
  g.addColorStop(1, 'rgba(255,111,97,0.05)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(cx, cy, rad, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.font = '600 14px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`seed ${state.seed}`, cx, cy - 6);
  ctx.fillStyle = '#e8e8f0';
  ctx.font = '12px -apple-system, sans-serif';
  ctx.fillText(`${SCALES[state.scaleIdx]} · root ${PC_NAME[state.rootPc]}`, cx, cy + 14);
  // hint
  ctx.fillStyle = '#8888a0';
  ctx.font = '13px -apple-system, sans-serif';
  ctx.fillText('핸드폰을 흔들어 새 seed', cx, cy + 90);
}

async function start() {
  await audio.unlock();
  running = true;
  startT = performance.now();
  lastStep = -1;
  btnStart.textContent = 'running…';
  btnStart.disabled = true;
}
function stop() {
  running = false;
  btnStart.textContent = 'start (30s)';
  btnStart.disabled = false;
  audio.stopAll(200);
}

async function onPerm() {
  const r = await requestSensorPermission();
  if (r.motion === 'granted' || r.motion === 'unknown') {
    window.addEventListener('devicemotion', onMotion);
  }
  await audio.unlock();
  overlay.classList.add('hidden');
}

btnPerm.addEventListener('click', onPerm);
btnStart.addEventListener('click', start);
btnShake.addEventListener('click', triggerShake);

resize();
requestAnimationFrame(step);
