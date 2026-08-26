import { AudioEngine } from './audio-engine.js';
import { nodePC, PC_NAME } from './tonnetz-pc.js';
import { requestSensorPermission } from './sensor-permission.js';
import { runGeneration } from './generator.js';

// ── Constants ──────────────────────────────────────────────────────────────
const SESSION_SEC    = 30;
const STEP_MS        = 250;      // 8th note at 120 BPM — rhythmic grid
const MAX_REC_STEPS  = SESSION_SEC * 1000 / STEP_MS;  // 120 steps
const SQRT_3         = Math.sqrt(3);

// ── DOM ────────────────────────────────────────────────────────────────────
const canvas    = document.getElementById('canvas');
const ctx       = canvas.getContext('2d');
const hudTime   = document.getElementById('hudTime');
const btnStart  = document.getElementById('btnStart');
const btnReseed = document.getElementById('btnReseed');
const btnPerm   = document.getElementById('btnPerm');
const overlay   = document.getElementById('perm');

let dpr = Math.max(1, window.devicePixelRatio || 1);
let W = 0, H = 0;

const audio = new AudioEngine();

// ── Grid geometry ──────────────────────────────────────────────────────────
// Slant (parallelogram) Tonnetz: x = W/2 + c·xStep + r·(xStep/2) − panX
//                                y = H/2 + r·yStep               − panY
// Row step = +7 (P5), col step = +4 (M3) → all adjacent triangles are triads.
let xStep = 80;
let yStep = xStep * SQRT_3 / 2;

// ── Pan physics ────────────────────────────────────────────────────────────
let panX = 0, panY = 0;
let pvx  = 0, pvy  = 0;
const friction = 0.92;
const gain     = 0.9;   // 실기기 피드백 반영 (0.6 → 0.9). 굴림이 굼떴다.

// ── Hot-node map ───────────────────────────────────────────────────────────
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

// ── App state machine ──────────────────────────────────────────────────────
// 'idle'      → ready, audio permission not yet granted
// 'explore'   → audio unlocked; notes play freely; no recording
// 'recording' → 30 s recording phase; notes play + path captured
// 'done'      → recording saved; "Generate" button shown
let appState = 'idle';

// ── Note-step counter (always ticking, independent of session) ────────────
// Notes fire on every STEP_MS interval regardless of appState.
// This decouples sound from session management.
let lastNoteStep     = -1;
let lastTriggeredKey = '';

// ── Recording buffer ───────────────────────────────────────────────────────
// Each entry: { step, pc, r, c }  (120 entries over 30 s)
let recording     = [];     // filled during 'recording' state
let recordStartT  = 0;

// ── Generation playback handle ────────────────────────────────────────────
let activePlayback = null;

// ── Resize / layout ────────────────────────────────────────────────────────
function resize() {
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width  = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  xStep = Math.min((W - 40) / 4.5, 100);
  yStep = xStep * SQRT_3 / 2;
}
window.addEventListener('resize', resize);

// ── Grid helpers ───────────────────────────────────────────────────────────
function nodePos(r, c) {
  return {
    x: W / 2 + c * xStep + r * xStep * 0.5 - panX,
    y: H / 2 + r * yStep                   - panY,
  };
}
function centreGrid() {
  const rF = panY / yStep;
  const cF = (panX - rF * xStep * 0.5) / xStep;
  return { rF, cF };
}
function visibleRange() {
  const { rF, cF } = centreGrid();
  const rHalf = Math.ceil(H / yStep / 2) + 2;
  const cHalf = Math.ceil(W / xStep)     + 3;
  return {
    rMin: Math.floor(rF - rHalf), rMax: Math.ceil(rF + rHalf),
    cMin: Math.floor(cF - cHalf), cMax: Math.ceil(cF + cHalf),
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

// ── Sensor / keyboard ──────────────────────────────────────────────────────
let tiltX = 0, tiltY = 0;
// 실기기 피드백: 민감도가 낮다. 종전에는 ±45° 를 다 기울여야 최대 편향이었는데
// 손에 든 상태에서 45° 는 과하다. ±26° 로 좁혀 같은 동작에 약 1.7배 반응한다.
// TILT_RANGE 를 키우면 둔해지고 줄이면 예민해진다.
const TILT_RANGE = 26;
const TILT_REST  = 20;   // 손에 들었을 때의 기본 beta (화면을 눕히지 않는 자세)
function onOrient(e) {
  let g = e.gamma || 0, b = e.beta || 0;
  g = Math.max(-TILT_RANGE, Math.min(TILT_RANGE, g));
  b = Math.max(-TILT_RANGE, Math.min(TILT_RANGE, b - TILT_REST));
  tiltX = g / TILT_RANGE;
  tiltY = b / TILT_RANGE;
}

const keysDown = new Set();
window.addEventListener('keydown', (e) => {
  if (e.key.startsWith('Arrow')) { e.preventDefault(); keysDown.add(e.key); }
});
window.addEventListener('keyup', (e) => { keysDown.delete(e.key); });

// ── Note trigger (always runs — not gated by appState) ────────────────────
function triggerNearestNode(stepIdx) {
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
  // Skip repeat triggers unless sphere has moved noticeably
  if (key === lastTriggeredKey && bestD2 > 6400) return;
  lastTriggeredKey = key;

  setHot(best.r, best.c);
  const pc  = nodePC(best.r, best.c);
  const rowOct = ((best.r % 4) + 4) % 4;
  const midi   = 48 + pc + (3 - rowOct) * 3;
  const vel    = Math.min(1.0, 0.4 + Math.hypot(pvx, pvy) * 0.04);
  audio.note(midi, { velocity: vel, dur: 1.8 });

  // ── Record step if in recording phase ────────────────────────────────
  if (appState === 'recording') {
    recording.push({ step: stepIdx, pc, r: best.r, c: best.c, midi });
  }
}

// ── Main loop ──────────────────────────────────────────────────────────────
function step(now) {
  // Pan physics
  const kx = (keysDown.has('ArrowRight') ? 1 : 0) - (keysDown.has('ArrowLeft') ? 1 : 0);
  const ky = (keysDown.has('ArrowDown')  ? 1 : 0) - (keysDown.has('ArrowUp')   ? 1 : 0);
  pvx += (tiltX + kx) * gain;
  pvy += (tiltY + ky) * gain;
  pvx *= friction;
  pvy *= friction;
  panX += pvx;
  panY += pvy;

  // ── Note step: always fires, not gated by session ─────────────────────
  if (appState !== 'idle') {
    const curStep = Math.floor(now / STEP_MS);
    if (curStep !== lastNoteStep) {
      lastNoteStep = curStep;
      triggerNearestNode(curStep);
    }
  }

  // ── Recording timer ────────────────────────────────────────────────────
  if (appState === 'recording') {
    const elapsed = (now - recordStartT) / 1000;
    const left = Math.max(0, SESSION_SEC - elapsed);
    hudTime.textContent = '⏺ ' + left.toFixed(1) + 's';
    if (elapsed >= SESSION_SEC) finishRecording();
  } else if (appState === 'explore') {
    hudTime.textContent = '▶ ' + SESSION_SEC + 's';
  } else if (appState === 'done') {
    hudTime.textContent = '✓ recorded';
  } else {
    hudTime.textContent = SESSION_SEC + 's';
  }

  draw();
  requestAnimationFrame(step);
}

// ── Session controls ───────────────────────────────────────────────────────
async function startRecording() {
  await audio.unlock();
  // 새 녹음 시작 시 이전 생성 결과 정리
  if (activePlayback) { activePlayback.stop(); activePlayback = null; }
  hideGenerateButton();

  appState    = 'recording';
  recording   = [];
  recordStartT = performance.now();
  btnStart.textContent = '⏹ 녹음 중지';
  btnStart.disabled    = false;
  btnStart.onclick     = stopRecordingEarly;
}

function stopRecordingEarly() {
  finishRecording();
}

function finishRecording() {
  appState = 'done';
  // Persist for later generation (Phase 2)
  window.__tonnetzRecording = recording.slice();
  btnStart.textContent = '▶ 다시 녹음';
  btnStart.disabled    = false;
  btnStart.onclick     = restartRecording;
  // Show generate placeholder (Phase 2 will wire this up)
  showGenerateButton();
}

function restartRecording() {
  btnStart.onclick = restartRecording; // keep
  startRecording();
}

function showGenerateButton() {
  let btn = document.getElementById('btnGenerate');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'btnGenerate';
    btn.style.cssText =
      'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
      'padding:12px 28px;border-radius:24px;border:none;background:#6fa66a;' +
      'color:#fff;font-size:1rem;font-weight:600;cursor:pointer;z-index:50;' +
      'box-shadow:0 4px 16px rgba(0,0,0,0.35);white-space:nowrap;';
    document.body.appendChild(btn);
  }
  btn.textContent = '🎵 생성하기 (' + recording.length + ' steps)';
  btn.disabled = false;
  btn.onclick = onGenerateClick;
}

function hideGenerateButton() {
  const btn = document.getElementById('btnGenerate');
  if (btn) btn.remove();
}

async function onGenerateClick() {
  const btn = document.getElementById('btnGenerate');
  if (!btn) return;

  // 재생 중이면 중단
  if (activePlayback) {
    activePlayback.stop();
    activePlayback = null;
    btn.textContent = '🎵 생성하기 (' + recording.length + ' steps)';
    btn.style.background = '#6fa66a';
    return;
  }

  if (recording.length === 0) {
    btn.textContent = '⚠ 녹음이 비어있음';
    btn.disabled = true;
    return;
  }

  btn.disabled = true;
  btn.textContent = '🔄 생성 중…';

  try {
    await audio.unlock();
    const res = await runGeneration(recording, audio, {
      T: 120,            // 30s × (1000/250ms)
      K: 14,
      stepMs: 250,
      // ⚠ 3.0 은 §7.7.3 근거로 쓰였으나 그 주장은 철회됐다(2026-08-15,
      //   `t8_temperature_audit.json`). 개인화 OM 은 zero-row 가 많아 노드 풀이
      //   실제로 열리는데, 그런 설정에서는 T=1.0 이 단조 우세하다(paired p=6.1e-08).
      temperature: 1.0,
      windowSize: 4,
    });
    activePlayback = res.playback;

    const m = res.meta;
    console.log('[gen] seed=' + m.seed + ' notes=' + m.numNotes +
      ' density=' + (m.density * 100).toFixed(1) + '% fails=' + m.resampleFails +
      ' elapsed=' + m.genElapsedMs.toFixed(0) + 'ms');

    btn.textContent = '⏹ 중지 (seed ' + m.seed + ' · ' + m.numNotes + ' notes)';
    btn.style.background = '#b05a5a';
    btn.disabled = false;

    // 재생 끝나면 원래 상태로
    setTimeout(() => {
      if (activePlayback === res.playback) {
        activePlayback = null;
        btn.textContent = '🎵 다시 생성 (seed 변경)';
        btn.style.background = '#6fa66a';
        btn.disabled = false;
      }
    }, res.playback.totalMs);
  } catch (err) {
    console.error('[gen] 실패', err);
    btn.textContent = '⚠ 실패: ' + (err.message || err);
    btn.disabled = false;
    setTimeout(() => {
      btn.textContent = '🎵 다시 시도';
      btn.style.background = '#6fa66a';
    }, 2500);
  }
}

// ── Permission ─────────────────────────────────────────────────────────────
async function onPermClick() {
  const r = await requestSensorPermission();
  if (r.orientation === 'granted' || r.orientation === 'unknown') {
    window.addEventListener('deviceorientation', onOrient);
  }
  await audio.unlock();
  overlay.classList.add('hidden');
  appState = 'explore';   // notes now play freely; Start begins recording
  btnStart.textContent = '⏺ 녹음 시작 (30s)';
  btnStart.onclick = startRecording;
}

// ── Draw ───────────────────────────────────────────────────────────────────
function draw() {
  ctx.fillStyle = '#0a0a12';
  ctx.fillRect(0, 0, W, H);
  decayHot();

  const { rMin, rMax, cMin, cMax } = visibleRange();

  // ① Triangles
  for (let r = rMin; r < rMax; r++) {
    for (let c = cMin; c < cMax; c++) {
      const pa = nodePos(r, c),   pb = nodePos(r, c+1);
      const pd = nodePos(r+1, c), pe = nodePos(r+1, c+1);
      if (onScreen(pa) || onScreen(pb) || onScreen(pd)) {
        const t = triadType(nodePC(r,c), nodePC(r,c+1), nodePC(r+1,c));
        if (t) fillTri(pa, pb, pd, t,
          (nodeHot(r,c)+nodeHot(r,c+1)+nodeHot(r+1,c))/3);
      }
      if (onScreen(pb) || onScreen(pd) || onScreen(pe)) {
        const t = triadType(nodePC(r,c+1), nodePC(r+1,c), nodePC(r+1,c+1));
        if (t) fillTri(pb, pd, pe, t,
          (nodeHot(r,c+1)+nodeHot(r+1,c)+nodeHot(r+1,c+1))/3);
      }
    }
  }

  // ② Edges (batched)
  ctx.strokeStyle = 'rgba(200,200,220,0.18)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let r = rMin; r <= rMax; r++) {
    for (let c = cMin; c <= cMax; c++) {
      const p  = nodePos(r, c);
      if (!onScreen(p)) continue;
      const pr = nodePos(r, c+1), pd = nodePos(r+1, c), pl = nodePos(r+1, c-1);
      ctx.moveTo(p.x, p.y); ctx.lineTo(pr.x, pr.y);
      ctx.moveTo(p.x, p.y); ctx.lineTo(pd.x, pd.y);
      ctx.moveTo(p.x, p.y); ctx.lineTo(pl.x, pl.y);
    }
  }
  ctx.stroke();

  // ③ Nodes
  ctx.font = '11px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (let r = rMin; r <= rMax; r++) {
    for (let c = cMin; c <= cMax; c++) {
      const p = nodePos(r, c);
      if (!onScreen(p)) continue;
      const hot = nodeHot(r, c);
      const rad = 14 + hot * 14;
      ctx.beginPath();
      ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
      ctx.fillStyle = hot > 0.02
        ? `rgba(255,${Math.round(154+hot*80)},${Math.round(122-hot*40)},${(0.3+hot*0.6).toFixed(2)})`
        : '#2a2a4a';
      ctx.fill();
      ctx.fillStyle = hot > 0.3 ? '#1a1000' : '#888';
      ctx.fillText(PC_NAME[nodePC(r, c)], p.x, p.y);
    }
  }

  // ④ Sphere (fixed at centre)
  const sx = W/2, sy = H/2, sr = 22;
  // Recording pulse ring
  if (appState === 'recording') {
    const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 200);
    ctx.beginPath();
    ctx.arc(sx, sy, sr + 8 + pulse * 6, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255,80,80,${(0.4 + pulse * 0.4).toFixed(2)})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  const grad = ctx.createRadialGradient(sx-6, sy-6, 2, sx, sy, sr);
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
  const base  = type === 'major' ? [232,143,106] : [92,166,180];
  ctx.beginPath();
  ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c.x, c.y);
  ctx.closePath();
  ctx.fillStyle = `rgba(${base[0]},${base[1]},${base[2]},${(0.06+hot*0.35).toFixed(3)})`;
  ctx.fill();
}

// ── Init ───────────────────────────────────────────────────────────────────
btnPerm.addEventListener('click', onPermClick);
btnStart.addEventListener('click', () => { /* overridden per-state */ });
btnReseed.addEventListener('click', () => {
  pvx = (Math.random() - 0.5) * 14;
  pvy = (Math.random() - 0.5) * 14;
});

resize();
requestAnimationFrame(step);
