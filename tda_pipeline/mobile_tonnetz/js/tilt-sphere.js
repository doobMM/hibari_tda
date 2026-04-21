import { AudioEngine } from './audio-engine.js';
import { nodePC, PC_NAME } from './tonnetz-pc.js';
import { requestSensorPermission } from './sensor-permission.js';

const SESSION_SEC  = 30;
const BPM          = 120;
const STEPS_PER_BEAT = 2;            // 8th notes
const STEP_MS      = (60 / BPM / STEPS_PER_BEAT) * 1000;  // 250 ms
const TOTAL_STEPS  = 60;
const SQRT_3       = Math.sqrt(3);

const canvas   = document.getElementById('canvas');
const ctx      = canvas.getContext('2d');
const hudTime  = document.getElementById('hudTime');
const btnStart = document.getElementById('btnStart');
const btnReseed= document.getElementById('btnReseed');
const btnPerm  = document.getElementById('btnPerm');
const overlay  = document.getElementById('perm');

let dpr = Math.max(1, window.devicePixelRatio || 1);
let W = 0, H = 0;

const audio = new AudioEngine();

// ── Grid geometry ─────────────────────────────────────────────────────────
// Slant (parallelogram) Tonnetz layout:
//   screenX(r,c) = W/2 + c·xStep + r·(xStep/2) − panX
//   screenY(r,c) = H/2 + r·yStep               − panY
// Row axis = perfect 5th (+7 semitones), col axis = major 3rd (+4).
// Every adjacent triangle has edge intervals {+3,+4,+7} → always a triad.

let xStep = 80;          // node spacing (set by resize)
let yStep = xStep * SQRT_3 / 2;

// ── Pan physics (tilt moves the grid; sphere stays centred) ───────────────
let panX = 0, panY = 0;  // grid pan offset  (px)
let pvx  = 0, pvy  = 0;  // pan velocity
const friction = 0.92;
const gain     = 0.6;

// ── Hot-node map  {`r,c` → 0..1} ─────────────────────────────────────────
const hotMap = new Map();
const hotKey = (r, c) => `${r},${c}`;
function nodeHot(r, c)  { return hotMap.get(hotKey(r, c)) || 0; }
function setHot(r, c)   { hotMap.set(hotKey(r, c), 1.0); }
function decayHot() {
  for (const [k, v] of hotMap) {
    const nv = v - 0.02;
    if (nv <= 0) hotMap.delete(k); else hotMap.set(k, nv);
  }
}

// ── Session state ──────────────────────────────────────────────────────────
let running  = false;
let startT   = 0;
let lastStep = -1;
let lastTriggeredKey = '';

// ── Resize / layout ───────────────────────────────────────────────────────
function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width  = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // Target ~5 visible columns; cap at 100 px
  xStep = Math.min((W - 40) / 4.5, 100);
  yStep = xStep * SQRT_3 / 2;
}
window.addEventListener('resize', resize);

// ── Grid helpers ──────────────────────────────────────────────────────────
function nodePos(r, c) {
  return {
    x: W / 2 + c * xStep + r * xStep * 0.5 - panX,
    y: H / 2 + r * yStep                   - panY,
  };
}

// Fractional (r,c) of the grid point currently under the sphere (screen centre).
function centreGrid() {
  const rF = panY / yStep;
  const cF = (panX - rF * xStep * 0.5) / xStep;
  return { rF, cF };
}

// Visible node row/col range with generous margin.
function visibleRange() {
  const { rF, cF } = centreGrid();
  const rHalf = Math.ceil(H / yStep / 2) + 2;
  const cHalf = Math.ceil(W / xStep)     + 3;
  return {
    rMin: Math.floor(rF - rHalf),
    rMax: Math.ceil (rF + rHalf),
    cMin: Math.floor(cF - cHalf),
    cMax: Math.ceil (cF + cHalf),
  };
}

function onScreen({ x, y }, m = 80) {
  return x > -m && x < W + m && y > -m && y < H + m;
}

// ── Triad detection ────────────────────────────────────────────────────────
function triadType(pc1, pc2, pc3) {
  const s = new Set([pc1, pc2, pc3]);
  for (const r of [pc1, pc2, pc3]) {
    if (s.has((r + 4) % 12) && s.has((r + 7) % 12)) return 'major';
    if (s.has((r + 3) % 12) && s.has((r + 7) % 12)) return 'minor';
  }
  return null;
}

// ── Sensor / input ─────────────────────────────────────────────────────────
let tiltX = 0, tiltY = 0;

function onOrient(e) {
  let g = e.gamma || 0;
  let b = e.beta  || 0;
  g = Math.max(-45, Math.min(45, g));
  b = Math.max(-45, Math.min(45, b - 20));  // rest angle ~20°
  tiltX = g / 45;   // −1 … +1
  tiltY = b / 45;
}

// ── Main loop ──────────────────────────────────────────────────────────────
function step(now) {
  // Pan physics — tilt accelerates the grid
  pvx += tiltX * gain;
  pvy += tiltY * gain;
  pvx *= friction;
  pvy *= friction;
  panX += pvx;
  panY += pvy;

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

// ── Note trigger ──────────────────────────────────────────────────────────
function triggerNearestNode() {
  const { rF, cF } = centreGrid();
  let best = null, bestD2 = Infinity;

  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      const r = Math.round(rF) + dr;
      const c = Math.round(cF) + dc;
      const p = nodePos(r, c);
      const dx = p.x - W / 2, dy = p.y - H / 2;
      const d2 = dx * dx + dy * dy;
      if (d2 < bestD2) { bestD2 = d2; best = { r, c }; }
    }
  }
  if (!best) return;

  const key = hotKey(best.r, best.c);
  if (key === lastTriggeredKey && bestD2 > 6400) return;
  lastTriggeredKey = key;

  setHot(best.r, best.c);

  const pc = nodePC(best.r, best.c);
  // Octave = row position mod 4, higher rows → lower pitch
  const rowOct = ((best.r % 4) + 4) % 4;
  const midi   = 48 + pc + (3 - rowOct) * 3;   // MIDI 48–59 range
  const vel    = Math.min(1.0, 0.4 + Math.hypot(pvx, pvy) * 0.04);
  audio.note(midi, { velocity: vel, dur: 0.5 });
}

// ── Draw ───────────────────────────────────────────────────────────────────
function draw() {
  ctx.fillStyle = '#0a0a12';
  ctx.fillRect(0, 0, W, H);

  decayHot();

  const { rMin, rMax, cMin, cMax } = visibleRange();

  // ① Triangle faces (major = peach, minor = teal)
  for (let r = rMin; r < rMax; r++) {
    for (let c = cMin; c < cMax; c++) {
      const pa = nodePos(r,   c);
      const pb = nodePos(r,   c + 1);
      const pd = nodePos(r + 1, c);
      const pe = nodePos(r + 1, c + 1);

      // Upper: {(r,c), (r,c+1), (r+1,c)}
      if (onScreen(pa) || onScreen(pb) || onScreen(pd)) {
        const t = triadType(nodePC(r, c), nodePC(r, c + 1), nodePC(r + 1, c));
        if (t) {
          const hot = (nodeHot(r, c) + nodeHot(r, c + 1) + nodeHot(r + 1, c)) / 3;
          fillTri(pa, pb, pd, t, hot);
        }
      }
      // Lower: {(r,c+1), (r+1,c), (r+1,c+1)}
      if (onScreen(pb) || onScreen(pd) || onScreen(pe)) {
        const t = triadType(nodePC(r, c + 1), nodePC(r + 1, c), nodePC(r + 1, c + 1));
        if (t) {
          const hot = (nodeHot(r, c + 1) + nodeHot(r + 1, c) + nodeHot(r + 1, c + 1)) / 3;
          fillTri(pb, pd, pe, t, hot);
        }
      }
    }
  }

  // ② Edges — batched into one path for performance
  // Three edge directions per node: right (+4), down-right (+7), down-left (+3)
  ctx.strokeStyle = 'rgba(200,200,220,0.18)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let r = rMin; r <= rMax; r++) {
    for (let c = cMin; c <= cMax; c++) {
      const p  = nodePos(r, c);
      const pr = nodePos(r,     c + 1);  // right      (+4)
      const pd = nodePos(r + 1, c);      // down-right (+7)
      const pl = nodePos(r + 1, c - 1); // down-left  (+3)
      if (onScreen(p) || onScreen(pr))  { ctx.moveTo(p.x, p.y); ctx.lineTo(pr.x, pr.y); }
      if (onScreen(p) || onScreen(pd))  { ctx.moveTo(p.x, p.y); ctx.lineTo(pd.x, pd.y); }
      if (onScreen(p) || onScreen(pl))  { ctx.moveTo(p.x, p.y); ctx.lineTo(pl.x, pl.y); }
    }
  }
  ctx.stroke();

  // ③ Node circles + labels
  for (let r = rMin; r <= rMax; r++) {
    for (let c = cMin; c <= cMax; c++) {
      const p = nodePos(r, c);
      if (!onScreen(p)) continue;
      const hot = nodeHot(r, c);
      const rad = 14 + hot * 14;
      ctx.beginPath();
      ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
      ctx.fillStyle = hot > 0.02
        ? `rgba(255,${Math.round(154 + hot * 80)},${Math.round(122 - hot * 40)},${(0.3 + hot * 0.6).toFixed(2)})`
        : '#2a2a4a';
      ctx.fill();
      ctx.fillStyle = hot > 0.3 ? '#1a1000' : '#888';
      ctx.font = '11px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(PC_NAME[nodePC(r, c)], p.x, p.y);
    }
  }

  // ④ Sphere — fixed at screen centre
  const sx = W / 2, sy = H / 2, sr = 22;
  const grad = ctx.createRadialGradient(sx - 6, sy - 6, 2, sx, sy, sr);
  grad.addColorStop(0, '#fff6c8');
  grad.addColorStop(1, '#c28a2a');
  ctx.beginPath();
  ctx.arc(sx, sy, sr, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.2)';
  ctx.lineWidth = 1;
  ctx.stroke();
}

function fillTri(a, b, c, type, hot) {
  const base  = type === 'major' ? [232, 143, 106] : [92, 166, 180];
  const alpha = (0.06 + hot * 0.35).toFixed(3);
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.lineTo(c.x, c.y);
  ctx.closePath();
  ctx.fillStyle = `rgba(${base[0]},${base[1]},${base[2]},${alpha})`;
  ctx.fill();
}

// ── Session controls ───────────────────────────────────────────────────────
async function start() {
  await audio.unlock();
  running = true;
  startT  = performance.now();
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

// ── Permission + desktop fallback ──────────────────────────────────────────
async function onPermClick() {
  const r = await requestSensorPermission();
  if (r.orientation === 'granted' || r.orientation === 'unknown') {
    window.addEventListener('deviceorientation', onOrient);
  }
  await audio.unlock();
  overlay.classList.add('hidden');
  // Desktop: mouse position → fake tilt
  if (r.orientation !== 'granted') {
    window.addEventListener('mousemove', (ev) => {
      tiltX = (ev.clientX / W - 0.5) * 2;
      tiltY = (ev.clientY / H - 0.5) * 2;
    });
  }
}

btnPerm.addEventListener('click', onPermClick);
btnStart.addEventListener('click', start);
// Reseed = give the grid a random kick to explore new territory
btnReseed.addEventListener('click', () => {
  pvx = (Math.random() - 0.5) * 14;
  pvy = (Math.random() - 0.5) * 14;
});

resize();
requestAnimationFrame(step);
