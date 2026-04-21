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
let triangles = []; // {i, j, k, major} — Tonnetz major/minor triad faces
let hexSide = 80;   // set by layoutNodes; used for draw() edge threshold
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

// Tonnetz 육각 격자: row 축 = 완전5도(+7), col 축 = 장3도(+4).
// 정삼각형 격자 좌표: x_step = u·√3, y_step = u·(3/2), 행마다 x_step/2 오프셋.
const SQRT_3 = Math.sqrt(3);

function layoutNodes() {
  nodes = [];
  const padX = 20;
  const padTop = 70;
  const padBot = 130;
  const usableW = W - padX * 2;
  const usableH = H - padTop - padBot;
  // Slant (parallelogram) Tonnetz lattice:
  //   x = originX + c * xStep + r * (xStep / 2)   ← each row shifts right by xStep/2
  //   y = originY + r * yStep,  yStep = xStep * (√3/2)
  // With row-step=+7 and col-step=+4, EVERY triangle has edge intervals {+3, +4, +7}
  // (the three Tonnetz intervals) → every triangle is major or minor → fully connected.
  // Grid extents: gridW = (COLS-1)*xStep + (ROWS-1)*(xStep/2)
  //               gridH = (ROWS-1)*yStep
  const sideFromW = usableW / ((COLS - 1) + (ROWS - 1) * 0.5);
  const sideFromH = usableH / ((ROWS - 1) * (SQRT_3 / 2));
  const side = Math.min(sideFromW, sideFromH, 110);
  hexSide = side;
  const xStep = side;
  const yStep = side * (SQRT_3 / 2);
  const gridW = (COLS - 1) * xStep + (ROWS - 1) * xStep * 0.5;
  const gridH = (ROWS - 1) * yStep;
  const originX = padX + (usableW - gridW) / 2;
  const originY = padTop + (usableH - gridH) / 2;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = originX + c * xStep + r * xStep * 0.5;   // slant: each row shifted right
      const y = originY + r * yStep;
      const pc = nodePC(r, c);
      const midi = 48 + pc + (ROWS - 1 - r) * 3;
      nodes.push({ x, y, pc, midi, hot: 0, r, c });
    }
  }
  // Pre-compute triangle faces (major/minor triads) — 삼각형 색칠용
  triangles = computeTriangles(xStep, yStep);
  sphere.x = W / 2;
  sphere.y = H / 2;
  sphere.vx = 0; sphere.vy = 0;
  sphere.targetX = sphere.x;
  sphere.targetY = sphere.y;
}

// 세 pc가 major({root, +4, +7}) 또는 minor({root, +3, +7}) triad 인지 판정.
// sort 기반이 아니라 "root 후보 3개" 모두 시도해 cyclic rotation까지 포착.
function triadType(pc1, pc2, pc3) {
  const set = new Set([pc1, pc2, pc3]);
  for (const r of [pc1, pc2, pc3]) {
    if (set.has((r + 4) % 12) && set.has((r + 7) % 12)) return 'major';
    if (set.has((r + 3) % 12) && set.has((r + 7) % 12)) return 'minor';
  }
  return null;
}

// 인접 3개 노드로 이루어진 삼각형 리스트(fillStyle용). xStep,yStep은 인접 판정 기준.
function computeTriangles(xStep, yStep) {
  const tri = [];
  const maxD = Math.hypot(xStep, yStep) * 1.05;  // 인접 반경
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dij = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
      if (dij > maxD) continue;
      for (let k = j + 1; k < nodes.length; k++) {
        const djk = Math.hypot(nodes[j].x - nodes[k].x, nodes[j].y - nodes[k].y);
        const dik = Math.hypot(nodes[i].x - nodes[k].x, nodes[i].y - nodes[k].y);
        if (djk > maxD || dik > maxD) continue;
        const type = triadType(nodes[i].pc, nodes[j].pc, nodes[k].pc);
        if (type) tri.push({ i, j, k, major: type === 'major' });
      }
    }
  }
  return tri;
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
  // avoid spamming the same node — require slight movement or different node
  if (best === lastTriggeredNode && bd2 > 6400) return;
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

  // ① 삼각형 면(major/minor triad) — 은은한 배경 fill
  for (const t of triangles) {
    const a = nodes[t.i], b = nodes[t.j], c = nodes[t.k];
    // hot 평균으로 면 밝기 결정
    const hot = (a.hot + b.hot + c.hot) / 3;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.lineTo(c.x, c.y);
    ctx.closePath();
    // major = 따뜻한 복숭아, minor = 차가운 청록
    const base = t.major ? [232, 143, 106] : [92, 166, 180];
    const alpha = 0.06 + hot * 0.35;
    ctx.fillStyle = `rgba(${base[0]}, ${base[1]}, ${base[2]}, ${alpha.toFixed(3)})`;
    ctx.fill();
  }

  // ② 격자 선 — 모든 인접 노드 쌍(side 거리 이내). triad 미형성 엣지도 포함.
  ctx.strokeStyle = 'rgba(200, 200, 220, 0.18)';
  ctx.lineWidth = 1;
  const maxEdge = hexSide * 1.12;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
      if (d > maxEdge) continue;
      ctx.beginPath();
      ctx.moveTo(nodes[i].x, nodes[i].y);
      ctx.lineTo(nodes[j].x, nodes[j].y);
      ctx.stroke();
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
