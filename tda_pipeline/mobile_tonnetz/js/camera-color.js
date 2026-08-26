import { AudioEngine } from './audio-engine.js';
import { loadHibari, generateFromBank, playNotes, bankAlpha, bankK } from './hibari-source.js';

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
let bankIdx = 2, curAlpha = null, curK = null, curN = 0;
let ready = false, cancelPlayback = null;
let lastStep = -1;
let facing = 'environment';
let stream = null;

// Offscreen sampler for webcam frames
const samplerSize = 32;
const sampler = document.createElement('canvas');
sampler.width = samplerSize; sampler.height = samplerSize;
const sctx = sampler.getContext('2d', { willReadFrequently: true });

let lastHue = 0, lastSat = 0, lastLight = 0;

function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener('resize', resize);

// 실패를 삼키지 않는다. 종전에는 catch 에서 console.warn 만 하고 호출부가 오버레이를
// 닫아버려, 사용자에게는 "허용했는데 아무 일도 안 일어남" 으로 보였다(실기기 피드백).
function cameraError(e) {
  const m = {
    NotAllowedError: '카메라 권한이 거부되었습니다. 브라우저 설정에서 허용해 주세요.',
    NotFoundError: '카메라를 찾을 수 없습니다.',
    NotReadableError: '다른 앱이 카메라를 쓰고 있습니다. 그 앱을 닫고 다시 시도해 주세요.',
    OverconstrainedError: '요청한 카메라 설정을 지원하지 않습니다.',
    SecurityError: 'HTTPS 에서만 카메라를 쓸 수 있습니다.',
  }[e && e.name] || ('카메라를 열지 못했습니다: ' + (e && e.name ? e.name : e));
  return m;
}

async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    return { ok: false, msg: '이 브라우저는 카메라를 지원하지 않습니다.' };
  }
  if (!window.isSecureContext) {
    return { ok: false, msg: 'HTTPS(또는 localhost) 에서만 카메라를 쓸 수 있습니다.' };
  }
  if (stream) stream.getTracks().forEach(t => t.stop());
  // 후면 카메라가 없는 기기가 있다 — 실패하면 제약 없이 한 번 더 시도한다.
  for (const c of [{ facingMode: facing, width: { ideal: 320 }, height: { ideal: 240 } }, true]) {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: c, audio: false });
      video.srcObject = stream;
      await video.play();
      return { ok: true };
    } catch (e) {
      var last = e;
    }
  }
  return { ok: false, msg: cameraError(last) };
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

// 색조 → α (두 음악적 거리를 섞는 비율). 종전에는 임의 음높이를 음계에 맞추는 mock 이었다.
// 이제 색이 **위상 구조 자체**를 고른다 — 따뜻한 색일수록 구조가 성기고(cycle 적고),
// 차가운 색일수록 촘촘하다(cycle 많다). 채도가 낮으면 정본 α=0.25 로 둔다.
const N_BANK = 6;
function hslToBank(hsl) {
  if (!hsl || hsl.s < 0.12) return 2;            // 무채색 → 정본
  return Math.min(N_BANK - 1, Math.floor((hsl.h / 360) * N_BANK));
}

function step(now) {
  const hsl = sampleColor();
  if (hsl) {
    lastHue = hsl.h; lastSat = hsl.s; lastLight = hsl.l;
    const b = hslToBank(hsl);
    // 뱅크가 바뀌면 즉시 다시 생성한다 — 색을 바꾸면 음악이 바뀌는 것이 이 모드의 전부다.
    if (b !== bankIdx) { bankIdx = b; if (running) regenerate(); }
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

// 음은 regenerate() 가 30초치를 한 번에 스케줄한다.
function tick() {}

function regenerate() {
  if (!ready) return;
  try {
    const g = generateFromBank(bankIdx, Math.floor(Math.random() * 1e6));
    curAlpha = g.alpha; curK = g.K; curN = g.n;
    if (cancelPlayback) cancelPlayback();
    cancelPlayback = playNotes(audio, g.notes, { velocity: 0.5 });
  } catch (e) { console.error('regenerate failed', e); }
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
  ctx.fillText(ready ? `hibari · α=${curAlpha} · cycle ${curK}개 · ${curN}음`
                     : 'hibari 데이터 불러오는 중…', cx, cy + size/2 + 112);
}

async function start() {
  await audio.unlock();
  if (!ready) { try { await loadHibari(); ready = true; } catch (e) {
      console.error('hibari load failed', e); return; } }
  running = true;
  startT = performance.now();
  regenerate();
  lastStep = -1;
  btnStart.textContent = 'running…';
  btnStart.disabled = true;
}
function stop() {
  if (cancelPlayback) { cancelPlayback(); cancelPlayback = null; }
  running = false;
  btnStart.textContent = 'start (30s)';
  btnStart.disabled = false;
  audio.stopAll(200);
}

btnPerm.addEventListener('click', async () => {
  const r = await startCamera();
  if (!r.ok) {                       // 실패하면 오버레이를 닫지 않고 이유를 보여준다
    let el = document.getElementById('camErr');
    if (!el) {
      el = document.createElement('p');
      el.id = 'camErr';
      el.style.cssText = 'color:#ff9c8f;font-size:13px;margin-top:10px;line-height:1.5';
      btnPerm.parentNode.appendChild(el);
    }
    el.textContent = r.msg;
    return;
  }
  await audio.unlock();
  try { await loadHibari(); ready = true; } catch (e) { console.error('hibari load failed', e); }
  overlay.classList.add('hidden');
});
btnStart.addEventListener('click', start);
btnFlip.addEventListener('click', async () => {
  facing = facing === 'environment' ? 'user' : 'environment';
  const r = await startCamera();
  if (!r.ok) console.warn(r.msg);
});

resize();
requestAnimationFrame(step);
