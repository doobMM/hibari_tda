import { AudioEngine } from './audio-engine.js';
import { ROWS, COLS, nodePC, nodeMidi, PC_NAME } from './tonnetz-pc.js';
import { requestSensorPermission } from './sensor-permission.js';

const SESSION_SEC = 30;
const BPM = 120;
const STEPS_PER_BEAT = 2; // 8th notes
const STEP_MS = (60 / BPM / STEPS_PER_BEAT) * 1000; // 250ms
const TOTAL_STEPS = 60; // 30 sec at 8th notes = 60 steps

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const hudTime = document.getElementById('hudTime');
const btnStart = document.getElementById('btnStart');
const btnReseed = document.getElementById('btnReseed');
const btnPerm = document.getElementById('btnPerm');
const overlay = document.getElementById('perm');

let dpr = Math.max(1, window.devicePixelRatio || 1);
let W = 0, H = 0;

const audio = new AudioEngine();

// Sphere physics (accel-based)
const sphere = {
  x: 0, y: 0, vx: 0, vy: 0, r: 22,
  targetX: 0, targetY: 0,
};
const friction = 0.92;
const gain = 0.6; // tilt → accel gain

// Nodes laid out in grid. Hot-activation fades over time.
let nodes = []; // {x, y, pc, midi, hot}
let running = false;
let startT = 0;
let stepCount = 0;
let lastStep = -1;
let lastTriggeredNode = -1;

function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  layoutNodes();
}
window.addEventListener('resize', resize);

function layoutNodes() {
  nodes = [];
  const padX = 24;
  const padTop = 80;
  const padBot = 140;
  const usableW = W - padX * 2;
  const usableH = H - padTop - padBot;
  const stepX = usableW / (COLS - 1);
  const stepY = usableH / (ROWS - 1);
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const offsetX = (r % 2) * stepX * 0.5; // diamond offset → Tonnetz-like triangles
      const x = padX + c * stepX + offsetX * (c < COLS - 1 ? 1 : 0);
      const y = padTop + r * stepY;
      const pc = nodePC(r, c);
      const midi = 48 + pc + (ROWS - 1 - r) * 12 * 0 + (r < 2 ? 12 : 0);
      nodes.push({ x, y, pc, midi, hot: 0, r, c });
    }
  }
  sphere.x = W / 2;
  sphere.y = H / 2;
  sphere.vx = 0; sphere.vy = 0;
  sphere.targetX = sphere.x;
  sphere.targetY = sphere.y;
}

// Device orientation → target accel
let tiltX = 0, tiltY = 0;
function onOrient(e) {
  // gamma: left-right [-90,90], beta: front-back [-180,180]
  let g = e.gamma || 0;
  let b = e.beta || 0;
  // Clamp to a comfortable range
  g = Math.max(-45, Math.min(45, g));
  b = Math.max(-45, Math.min(45, b - 20)); // assume phone tilted ~20° toward user at rest
  tiltX = g / 45; // -1..1
  tiltY = b / 45;
}

function step(now) {
  const dt = 1 / 60;
  // accelerate sphere by tilt
  sphere.vx += tiltX * gain;
  sphere.vy += tiltY * gain;
  sphere.vx *= friction;
  sphere.vy *= friction;
  sphere.x += sphere.vx;
  sphere.y += sphere.vy;
  // walls bounce
  if (sphere.x < sphere.r) { sphere.x = sphere.r; sphere.vx *= -0.5; }
  if (sphere.x > W - sphere.r) { sphere.x = W - sphere.r; sphere.vx *= -0.5; }
  if (sphere.y < 60) { sphere.y = 60; sphere.vy *= -0.5; }
  if (sphere.y > H - 120) { sphere.y = H - 120; sphere.vy *= -0.5; }

  if (running) {
    const elapsed = (now - startT) / 1000;
    const left = Math.max(0, SESSION_SEC - elapsed);
    hudTime.textContent = left.toFixed(1) + 's';
    const curStep = Math.floor(elapsed * 1000 / STEP_MS);
    if (curStep !== lastStep && curStep < TOTAL_STEPS) {
      lastStep = curStep;
      triggerNearestNode();
    }
    if (elapsed >= SESSION_SEC) stop();
  } else {
    hudTime.textContent = SESSION_SEC.toFixed(1) + 's';
  }

  draw();
  requestAnimationFrame(step);
}

function triggerNearestNode() {
  let best = -1, bd2 = Infinity;
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const dx = n.x - sphere.x, dy = n.y - sphere.y;
    const d2 = dx * dx + dy * dy;
    if (d2 < bd2) { bd2 = d2; best = i; }
  }
  if (best < 0) return;
  // avoid spamming the same node — skip while sphere stays within 80px of the
  // last-triggered node (hysteresis: must drift away and return).
  if (best === lastTriggeredNode && bd2 < 6400) return;
  lastTriggeredNode = best;
  const n = nodes[best];
  n.hot = 1.0;
  const midi = 48 + n.pc + (ROWS - 1 - n.r) * 3;
  const vel = Math.min(1.0, 0.4 + Math.hypot(sphere.vx, sphere.vy) * 0.04);
  audio.note(midi, { velocity: vel, dur: 0.5 });
}

function draw() {
  ctx.fillStyle = '#0a0a12';
  ctx.fillRect(0, 0, W, H);
  // edges — connect neighbors
  ctx.strokeStyle = '#1e1e34';
  ctx.lineWidth = 1;
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d < 120) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
  }
  // nodes
  for (const n of nodes) {
    n.hot = Math.max(0, n.hot - 0.02);
    const rad = 14 + n.hot * 14;
    ctx.beginPath();
    ctx.arc(n.x, n.y, rad, 0, Math.PI * 2);
    const hot = n.hot;
    ctx.fillStyle = hot > 0.02
      ? `rgba(255,${154 + hot * 80},${122 - hot * 40},${0.3 + hot * 0.6})`
      : '#2a2a4a';
    ctx.fill();
    ctx.fillStyle = hot > 0.3 ? '#1a1000' : '#888';
    ctx.font = '11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(PC_NAME[n.pc], n.x, n.y);
  }
  // sphere
  const grad = ctx.createRadialGradient(sphere.x - 6, sphere.y - 6, 2, sphere.x, sphere.y, sphere.r);
  grad.addColorStop(0, '#fff6c8');
  grad.addColorStop(1, '#c28a2a');
  ctx.beginPath();
  ctx.arc(sphere.x, sphere.y, sphere.r, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.2)';
  ctx.stroke();
}

async function start() {
  await audio.unlock();
  running = true;
  startT = performance.now();
  stepCount = 0; lastStep = -1;
  btnStart.textContent = 'running…';
  btnStart.disabled = true;
}
function stop() {
  running = false;
  btnStart.textContent = 'start (30s)';
  btnStart.disabled = false;
  audio.stopAll(200);
}

async function onPermClick() {
  const r = await requestSensorPermission();
  if (r.orientation === 'granted' || r.orientation === 'unknown') {
    window.addEventListener('deviceorientation', onOrient);
  }
  await audio.unlock();
  overlay.classList.add('hidden');
  // Dev fallback for desktop: mouse position → fake tilt
  if (r.orientation !== 'granted') {
    window.addEventListener('mousemove', (ev) => {
      tiltX = (ev.clientX / W - 0.5) * 2;
      tiltY = (ev.clientY / H - 0.5) * 2;
    });
  }
}

btnPerm.addEventListener('click', onPermClick);
btnStart.addEventListener('click', start);
btnReseed.addEventListener('click', () => {
  sphere.x = Math.random() * (W - 100) + 50;
  sphere.y = Math.random() * (H - 200) + 100;
  sphere.vx = (Math.random() - 0.5) * 10;
  sphere.vy = (Math.random() - 0.5) * 10;
});

resize();
requestAnimationFrame(step);
