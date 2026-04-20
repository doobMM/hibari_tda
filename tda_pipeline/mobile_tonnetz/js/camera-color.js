import { AudioEngine } from './audio-engine.js';
import { resolveToScale, PC_NAME } from './tonnetz-pc.js';

const SESSION_SEC = 30;
const BPM = 120;
const STEP_MS = (60 / BPM / 2) * 1000;
const TOTAL_STEPS = 60;

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const hudTime = document.getElementById('hudTime');
const btnStart = document.getElementById('btnStart');
const btnFlip = document.getElementById('btnFlip');
const btnPerm = document.getElementById('btnPerm');
const overlay = document.getElementById('perm');

const audio = new AudioEngine();

let dpr = Math.max(1, window.devicePixelRatio || 1);
let W = 0, H = 0;
let running = false;
let startT = 0;
let lastStep = -1;
let facing = 'environment';
let stream = null;

// Offscreen sampler for webcam frames
const samplerSize = 32;
const sampler = document.createElement('canvas');
sampler.width = samplerSize; sampler.height = samplerSize;
const sctx = sampler.getContext('2d', { willReadFrequently: true });

let currentScale = 'major';
let currentRootPc = 0;
let lastHue = 0, lastSat = 0, lastLight = 0;

function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener('resize', resize);

async function startCamera() {
  try {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facing, width: { ideal: 320 }, height: { ideal: 240 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
  } catch (e) {
    console.warn('camera error', e);
  }
}

function sampleColor() {
  if (!video.videoWidth) return null;
  // Sample center 60% region
  const sw = video.videoWidth * 0.6;
  const sh = video.videoHeight * 0.6;
  const sx = (video.videoWidth - sw) / 2;
  const sy = (video.videoHeight - sh) / 2;
  sctx.drawImage(video, sx, sy, sw, sh, 0, 0, samplerSize, samplerSize);
  const d = sctx.getImageData(0, 0, samplerSize, samplerSize).data;
  let r = 0, g = 0, b = 0;
  const n = samplerSize * samplerSize;
  for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i+1]; b += d[i+2]; }
  r /= n; g /= n; b /= n;
  return rgbToHsl(r, g, b);
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h *= 60;
  }
  return {h, s, l};
}

function hslToScale(hsl) {
  if (!hsl) return { scale: 'major', rootPc: 0 };
  const {h, s} = hsl;
  // Saturation too low → default hibari-ish major
  if (s < 0.12) return { scale: 'major', rootPc: 0 };
  let scale;
  if (h < 40 || h >= 320) scale = 'phrygian';  // red
  else if (h < 80) scale = 'major';              // yellow-green
  else if (h < 180) scale = 'major';             // green-cyan
  else if (h < 260) scale = 'minor';             // blue
  else scale = 'phrygian';                       // magenta
  // Hue → root pc (0..11)
  const rootPc = Math.floor(((h / 360) * 12)) % 12;
  return { scale, rootPc };
}

function step(now) {
  const hsl = sampleColor();
  if (hsl) {
    lastHue = hsl.h; lastSat = hsl.s; lastLight = hsl.l;
    const s = hslToScale(hsl);
    currentScale = s.scale;
    currentRootPc = s.rootPc;
  }
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
  // ascending arpeggio biased by brightness
  const octShift = Math.floor(lastLight * 2) - 1; // -1..1
  const base = 60 + octShift * 12;
  const offset = Math.floor(Math.random() * 14);
  const midi = resolveToScale(base + offset, currentScale, currentRootPc);
  audio.note(midi, { velocity: 0.55, dur: 0.4 });
}

function draw() {
  ctx.fillStyle = 'rgba(10,10,18,0.35)';
  ctx.fillRect(0, 0, W, H);
  // Center reticle
  const cx = W / 2, cy = H / 2;
  const size = Math.min(W, H) * 0.5;
  ctx.strokeStyle = 'rgba(255,255,255,0.35)';
  ctx.lineWidth = 2;
  ctx.strokeRect(cx - size/2, cy - size/2, size, size);
  // Color chip + scale label
  const chipR = 42;
  ctx.beginPath();
  ctx.arc(cx, cy + size/2 + 50, chipR, 0, Math.PI * 2);
  ctx.fillStyle = `hsl(${lastHue}, ${lastSat * 100}%, ${Math.min(60, lastLight * 100)}%)`;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.3)';
  ctx.stroke();
  ctx.fillStyle = '#fff';
  ctx.font = '600 14px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`${currentScale} · ${PC_NAME[currentRootPc]}`, cx, cy + size/2 + 112);
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

btnPerm.addEventListener('click', async () => {
  await startCamera();
  await audio.unlock();
  overlay.classList.add('hidden');
});
btnStart.addEventListener('click', start);
btnFlip.addEventListener('click', async () => {
  facing = facing === 'environment' ? 'user' : 'environment';
  await startCamera();
});

resize();
requestAnimationFrame(step);
