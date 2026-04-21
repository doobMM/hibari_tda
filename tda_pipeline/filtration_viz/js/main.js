/* ============================================================================
 * main.js — filtration_viz 진입점
 *
 * 책임:
 *   1. 데이터 로드
 *   2. SimplexRenderer 구성
 *   3. PianoPlayer 재생 ↔ tick 동기화 (선형 매핑 midiDurSec → T)
 *   4. scrub / ε / 토글 UI 배선
 *   5. legend 렌더 (cycle별 활성 여부 하이라이트)
 * ========================================================================= */
(async function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const canvas = $('canvas');
  const legendEl = $('legend');

  // UI refs
  const btnPlay = $('btn-play');
  const btnStop = $('btn-stop');
  const scrub   = $('scrub');
  const outT    = $('out-t');
  const outTmax = $('out-T');
  const epsEl   = $('eps');
  const outEps  = $('out-eps');
  const togCyc  = $('toggle-cycle');
  const togTri  = $('toggle-triangles');
  const togLbl  = $('toggle-labels');
  const togFilt = $('toggle-filtration');
  const layoutSel = $('layout-sel');
  const metaA   = $('meta-active');
  const metaE   = $('meta-edges');
  const metaR   = $('meta-triangles');
  const metaC   = $('meta-cycles');

  let data, renderer, player;
  let curTick = 0;
  let playStartCtxTime = 0;
  let playing = false;
  let rafId = null;
  let tickIntervalId = null;      // RAF 스로틀(숨은 탭) 대비용 fallback

  try {
    data = await window.FiltrationData.load('data');
  } catch (e) {
    console.error(e);
    alert('데이터 로드 실패: ' + e.message);
    return;
  }
  console.log('[filtration-viz] loaded', {
    T: data.T, N: data.N, K: data.cycles.length,
    midiDurSec: data.midiDurSec.toFixed(2),
    distRange: [data.distMin, data.distMax],
  });

  // DOM 업데이트
  scrub.max = String(data.T - 1);
  outTmax.textContent = String(data.T);

  renderer = new window.SimplexRenderer(canvas, data);
  player = new window.PianoPlayer();

  // Legend 구축
  function buildLegend() {
    const parts = ['<div class="title">Cycle (K=' + data.cycles.length + ')</div>'];
    for (const c of data.cycles) {
      const color = window.CYCLE_COLORS[c.cycle_idx % window.CYCLE_COLORS.length];
      const labels = c.note_labels_1idx.join(', ');
      parts.push(
        `<div class="row" data-cycle="${c.cycle_idx}">` +
        `<span class="sw" style="background:${color}"></span>` +
        `<span>#${c.cycle_idx} · ${c.size}v · τ=${c.tau.toFixed(2)}</span>` +
        `</div>`
      );
    }
    legendEl.innerHTML = parts.join('');
  }
  buildLegend();

  function updateLegend(activeCycles) {
    const set = new Set(activeCycles);
    legendEl.querySelectorAll('.row').forEach(el => {
      const idx = parseInt(el.getAttribute('data-cycle'), 10);
      el.classList.toggle('on', set.has(idx));
    });
  }

  function currentOpts() {
    return {
      showTriangles: togTri.checked,
      showCycles: togCyc.checked,
      showLabels: togLbl.checked,
      filtrationMode: togFilt.checked,
    };
  }

  function render() {
    const eps = parseFloat(epsEl.value);
    outEps.textContent = eps.toFixed(2);
    const stats = renderer.draw({ tick: curTick, eps, opts: currentOpts() });
    outT.textContent = String(curTick);
    metaA.textContent = '활성 note: ' + stats.activeCount;
    metaE.textContent = 'edges: ' + stats.edgeCount;
    metaR.textContent = 'triangles: ' + stats.triCount;
    metaC.textContent = 'active cycles: ' + stats.activeCycles.length;
    updateLegend(stats.activeCycles);
  }

  // 초기 렌더
  render();

  // 스크럽 ↔ tick
  scrub.addEventListener('input', (e) => {
    curTick = parseInt(e.target.value, 10);
    render();
  });

  // ε / 토글
  for (const el of [epsEl, togCyc, togTri, togLbl, togFilt]) {
    el.addEventListener('input', render);
    el.addEventListener('change', render);
  }

  // 레이아웃 변경
  layoutSel.addEventListener('change', () => {
    renderer.setLayout(layoutSel.value);
    render();
  });
  renderer.setLayout(layoutSel.value);

  // 마우스/터치 드래그로 yaw/pitch 회전
  renderer.attachDrag(render);

  // Play / Stop
  btnPlay.addEventListener('click', async () => {
    if (playing) return;
    if (!data.midiNotes.length) {
      alert('MIDI notes가 비었어 — export를 다시 확인해줘.');
      return;
    }

    // AudioContext 명시적 resume (iOS/일부 브라우저는 user gesture에서 await 필요)
    try {
      player._ensureCtx();
      if (player.ctx && player.ctx.state === 'suspended') {
        await player.ctx.resume();
      }
      console.log('[filtration-viz] AudioContext state:', player.ctx && player.ctx.state,
                  'notes:', data.midiNotes.length,
                  'dur:', data.midiDurSec.toFixed(2) + 's');
    } catch (e) {
      console.error('[filtration-viz] audio ctx resume 실패', e);
      alert('오디오 컨텍스트 시작 실패: ' + e.message);
      return;
    }

    playing = true;
    btnPlay.disabled = true;
    btnStop.disabled = false;

    player.play(data.midiNotes, {
      gain: 0.75,
      velocityScale: 0.14,
      onEnd: () => {
        playing = false;
        btnPlay.disabled = false;
        btnStop.disabled = true;
        if (rafId) cancelAnimationFrame(rafId);
        if (tickIntervalId) { clearInterval(tickIntervalId); tickIntervalId = null; }
      },
    });

    // 선형 매핑: MIDI 진행시간 → tick index
    const totalSec = Math.max(data.midiDurSec, 1e-3);
    const ctx = player.ctx;
    playStartCtxTime = ctx ? ctx.currentTime : 0;

    function syncTick() {
      if (!playing) return;
      const now = ctx.currentTime - playStartCtxTime;
      const frac = Math.min(1, Math.max(0, now / totalSec));
      const t = Math.min(data.T - 1, Math.floor(frac * data.T));
      if (t !== curTick) {
        curTick = t;
        scrub.value = String(t);
        render();
      }
    }
    function tickLoop() {
      if (!playing) return;
      syncTick();
      rafId = requestAnimationFrame(tickLoop);
    }
    rafId = requestAnimationFrame(tickLoop);
    // fallback: RAF가 탭 throttle/headless 로 멈춰도 오디오-시각 동기 유지
    if (tickIntervalId) clearInterval(tickIntervalId);
    tickIntervalId = setInterval(syncTick, 150);
  });

  btnStop.addEventListener('click', () => {
    if (!playing) return;
    player.stop();
    playing = false;
    btnPlay.disabled = false;
    btnStop.disabled = true;
    if (rafId) cancelAnimationFrame(rafId);
    if (tickIntervalId) { clearInterval(tickIntervalId); tickIntervalId = null; }
  });

  // 리사이즈
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(render, 120);
  });
})();
