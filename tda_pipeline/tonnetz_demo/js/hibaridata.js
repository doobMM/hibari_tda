/**
 * hibaridata.js — TDA data loader for TonnetzViz
 *
 * Loads hibari_barcode.json + hibari_overlap.json and provides:
 *   - Rate slider → barcode chart + cycle strength overlay
 *   - Overlap matrix heatmap with playback cursor
 *
 * Public API (window.hibariData):
 *   init()
 *   applyRate(rate)               — update barcode chart + tonnetz multipliers
 *   updatePlaybackCursor(frac)    — move heatmap cursor (0..1)
 */

(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────
  var barcodeData = null;   // hibari_barcode.json
  var overlapData = null;   // hibari_overlap.json
  var currentRate = 0.5;

  // Canvas references (set when panel is visible)
  var barcodeCanvas  = null;
  var overlapCanvas  = null;

  // Cursor for overlap heatmap (0..1 fraction)
  var overlapCursorFrac = 0;

  // Normalised strength max values per cycle name
  var maxStrength = { A: 1, B: 1, C: 1, D: 1 };

  // ── Overlap-driven playback state ─────────────────────────────────
  // colToCycle[c] = 'A'/'B'/'C'/'D'/null — overlap matrix column → ABCD 매핑
  var colToCycle = [];
  // 현재 overlap row에서 각 사이클이 active한가 (lerp'd 0..1)
  var overlapSmooth = { A: 1, B: 1, C: 1, D: 1 };
  var OVERLAP_DIM    = 0.12;   // inactive 시 최소 opacity
  var OVERLAP_SMOOTH = 0.30;   // lerp factor (100ms tick 기준)

  // ── Colours matching tonnetz.js H1_CYCLES ──────────────────────────
  var CYCLE_META = [
    { name: 'A', label: 'E–G–B',   pcs: [4,7,11],     fill: 'rgba(100,220,100,', stroke: '#64dc64' },
    { name: 'B', label: 'C–E–G',   pcs: [0,4,7],      fill: 'rgba(100,150,255,', stroke: '#6496ff' },
    { name: 'C', label: 'D–F–A',   pcs: [2,5,9],      fill: 'rgba(255,165, 80,', stroke: '#ffa550' },
    { name: 'D', label: 'F–A–C–E', pcs: [0,4,5,9],    fill: 'rgba(200,100,255,', stroke: '#c864ff' },
  ];
  var FALLBACK_FILL = 'rgba(160,160,160,';  // 매칭 없는 경우

  // 주어진 pc 집합에서 A/B/C/D 중 교집합이 가장 큰 사이클 색깔 반환
  function fillForPcs (pcs) {
    var pcSet = pcs.reduce(function(s, p){ s[p] = 1; return s; }, {});
    var best = null, bestCount = 0;
    CYCLE_META.forEach(function (cm) {
      var count = cm.pcs.filter(function(p){ return pcSet[p]; }).length;
      if (count > bestCount) { bestCount = count; best = cm; }
    });
    return bestCount >= 2 ? best.fill : FALLBACK_FILL;
  }

  // ── Helpers ───────────────────────────────────────────────────────
  function normalize () {
    if (!barcodeData) return;
    maxStrength = { A: 0, B: 0, C: 0, D: 0 };
    barcodeData.rate_data.forEach(function (rd) {
      ['A','B','C','D'].forEach(function (k) {
        var v = rd.cycle_strengths[k] || 0;
        if (v > maxStrength[k]) maxStrength[k] = v;
      });
    });
  }

  // overlap matrix column → A/B/C/D 사이클 매핑 (init 시 1회 계산)
  function buildColToCycle () {
    if (!overlapData) return;
    var ids = overlapData.cycle_ids || [];
    var pcs = overlapData.cycle_pcs || {};
    colToCycle = ids.map(function (cid) {
      var pcList = pcs[String(cid)] || [];
      var pcSet  = {};
      pcList.forEach(function (p) { pcSet[p] = 1; });
      var best = null, bestN = 0;
      CYCLE_META.forEach(function (cm) {
        var n = cm.pcs.filter(function (p) { return pcSet[p]; }).length;
        if (n >= 2 && n > bestN) { bestN = n; best = cm.name; }
      });
      return best;  // 'A'/'B'/'C'/'D' or null
    });
  }

  // rate 강도 × overlap 활성화 상태를 합산하여 tonnetz에 push
  // playing=true  → overlapSmooth 반영 (재생 중 cycle 점멸)
  // playing=false → overlapSmooth 무시 (rate slider만)
  function pushCombinedMults () {
    var rd = getRateEntry(currentRate);
    if (!rd) return;

    var playing = (typeof Tone !== 'undefined' &&
                   window._midiDuration > 0 &&
                   Tone.Transport && Tone.Transport.state === 'started');

    var result = {};
    CYCLE_META.forEach(function (cm) {
      var rMult = maxStrength[cm.name] > 0
                  ? (rd.cycle_strengths[cm.name] || 0) / maxStrength[cm.name]
                  : 0;
      result[cm.name] = playing ? rMult * overlapSmooth[cm.name] : rMult;
    });

    if (window.tonnetz && window.tonnetz.setRateMultipliers) {
      window.tonnetz.setRateMultipliers(result.A, result.B, result.C, result.D);
    }

    // strength label 업데이트 (재생 중 active cycle에 ● 표시)
    var labelEl = document.getElementById('rateStrengthLabels');
    if (labelEl) {
      labelEl.innerHTML = CYCLE_META.map(function (cm) {
        var pct = Math.round((result[cm.name] || 0) * 100);
        var dot = playing && overlapSmooth[cm.name] > 0.5 ? ' ●' : '';
        return '<span style="color:' + cm.stroke + '">' +
               cm.name + ':' + pct + '%' + dot + '</span>';
      }).join(' ');
    }
  }

  function getRateEntry (rate) {
    if (!barcodeData) return null;
    var r = Math.round(rate * 10) / 10;
    for (var i = 0; i < barcodeData.rate_data.length; i++) {
      if (Math.abs(barcodeData.rate_data[i].rate - r) < 0.01) return barcodeData.rate_data[i];
    }
    return barcodeData.rate_data[0];
  }

  // ── Barcode chart ─────────────────────────────────────────────────
  function renderBarcodeChart (rateEntry) {
    barcodeCanvas = barcodeCanvas || document.getElementById('barcodeCanvas');
    if (!barcodeCanvas || !rateEntry) return;

    var W = barcodeCanvas.width  = barcodeCanvas.offsetWidth  || 400;
    var H = barcodeCanvas.height = barcodeCanvas.offsetHeight || 220;
    var ctx = barcodeCanvas.getContext('2d');

    // Background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, W, H);

    var intervals = rateEntry.all_intervals || [];
    if (intervals.length === 0) {
      ctx.fillStyle = '#888';
      ctx.font = '12px monospace';
      ctx.fillText('No H₁ cycles at rate ' + rateEntry.rate.toFixed(1), 20, H / 2);
      return;
    }

    // X range: 0 → max death
    var maxD = 0;
    intervals.forEach(function (iv) { if (iv.death > maxD) maxD = iv.death; });
    if (maxD === 0) maxD = 1;

    var PAD_L = 46, PAD_R = 12, PAD_T = 24, PAD_B = 22;
    var chartW = W - PAD_L - PAD_R;
    var chartH = H - PAD_T - PAD_B;
    var N = intervals.length;
    var rowH = Math.max(3, Math.floor(chartH / N) - 1);

    function xOf(v) { return PAD_L + v / maxD * chartW; }

    // X-axis ticks
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD_L, H - PAD_B);
    ctx.lineTo(W - PAD_R, H - PAD_B);
    ctx.stroke();

    var tickCount = 5;
    ctx.fillStyle = '#888';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    for (var t = 0; t <= tickCount; t++) {
      var val = maxD * t / tickCount;
      var x = xOf(val);
      ctx.beginPath();
      ctx.moveTo(x, H - PAD_B);
      ctx.lineTo(x, H - PAD_B + 4);
      ctx.strokeStyle = '#555';
      ctx.stroke();
      ctx.fillText(val.toFixed(2), x, H - 4);
    }

    // Rate label
    ctx.fillStyle = '#aaa';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText('rate = ' + rateEntry.rate.toFixed(1) + '  |  H₁: ' + N, PAD_L, 14);

    // Determine which intervals match the 4 demo cycles for colouring
    // (Use cycle_strengths proportional highlight — we colour top-N intervals per cycle)
    // Simple heuristic: sort by persistence desc; top intervals get demo colors
    var sorted = intervals.slice().sort(function (a, b) {
      return (b.death - b.birth) - (a.death - a.birth);
    });

    // Map cycle letter → colour for top intervals
    var cycleColors = {};
    var share = Math.ceil(N / 4);
    ['D','B','A','C'].forEach(function (k, qi) {
      var start = qi * share;
      for (var si = start; si < Math.min(start + share, sorted.length); si++) {
        var iv = sorted[si];
        var idx = intervals.indexOf(iv);
        if (!(idx in cycleColors)) cycleColors[idx] = k;
      }
    });

    // Draw bars
    intervals.forEach(function (iv, i) {
      var x0 = xOf(iv.birth);
      var x1 = xOf(iv.death);
      var y  = PAD_T + i * (rowH + 1);
      var pers = iv.death - iv.birth;

      var meta = null;
      if (i in cycleColors) {
        var letter = cycleColors[i];
        for (var m = 0; m < CYCLE_META.length; m++) {
          if (CYCLE_META[m].name === letter) { meta = CYCLE_META[m]; break; }
        }
      }

      ctx.fillStyle = meta ? meta.fill + '0.85)' : 'rgba(160,160,160,0.6)';
      ctx.fillRect(x0, y, Math.max(x1 - x0, 2), rowH);

      // Persistence label for long bars
      if (x1 - x0 > 30 && rowH >= 5) {
        ctx.fillStyle = '#fff';
        ctx.font = '9px monospace';
        ctx.textAlign = 'left';
        ctx.fillText(pers.toFixed(3), x0 + 2, y + rowH - 1);
      }
    });

    // Cycle strength legend (top-right)
    var legX = W - 110, legY = PAD_T;
    CYCLE_META.forEach(function (cm, li) {
      var norm = maxStrength[cm.name] > 0
                 ? (getRateEntry(currentRate).cycle_strengths[cm.name] || 0) / maxStrength[cm.name]
                 : 0;
      var barW = Math.round(norm * 70);
      var ly = legY + li * 16;
      ctx.fillStyle = '#222';
      ctx.fillRect(legX - 2, ly, 76, 13);
      ctx.fillStyle = cm.fill + '0.8)';
      ctx.fillRect(legX - 2, ly, barW, 13);
      ctx.fillStyle = '#ccc';
      ctx.font = '10px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(cm.name + ' ' + (norm * 100).toFixed(0) + '%', legX + 1, ly + 10);
    });
  }

  // ── Overlap heatmap ───────────────────────────────────────────────
  function renderOverlapHeatmap () {
    overlapCanvas = overlapCanvas || document.getElementById('overlapCanvas');
    if (!overlapCanvas || !overlapData) return;

    var W = overlapCanvas.width  = overlapCanvas.offsetWidth  || 300;
    var H = overlapCanvas.height = overlapCanvas.offsetHeight || 400;
    var ctx = overlapCanvas.getContext('2d');

    var mat = overlapData.matrix;           // T_down × 10
    var T   = mat.length;
    var Nc  = mat[0].length;
    var colW = Math.floor(W / Nc);
    var rowH = Math.max(1, Math.floor(H / T));

    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, W, H);

    // 각 column의 색 = 해당 cycle의 pitch class 집합과 가장 많이 겹치는 A/B/C/D 사이클 색
    var cyclePcs  = overlapData.cycle_pcs  || {};
    var cycleIds  = overlapData.cycle_ids  || [];
    var colColors = [];
    for (var c = 0; c < Nc; c++) {
      var cid  = cycleIds[c];
      var pcs  = cyclePcs[String(cid)] || [];
      colColors.push(fillForPcs(pcs));
    }

    for (var t = 0; t < T; t++) {
      for (var c = 0; c < Nc; c++) {
        if (mat[t][c]) {
          ctx.fillStyle = colColors[c] + '0.85)';
          ctx.fillRect(c * colW, t * rowH, colW, rowH);
        }
      }
    }

    // Column labels at top
    ctx.fillStyle = '#aaa';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    var cycleIds = overlapData.cycle_ids || [];
    var cyclePcs = overlapData.cycle_pcs || {};
    var PC_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
    for (var c = 0; c < Nc; c++) {
      var cid = cycleIds[c];
      var pcs = cyclePcs[String(cid)] || [];
      var label = pcs.length > 0 ? pcs.map(function(p){return PC_NAMES[p];}).join('') : String(cid);
      ctx.fillText(label.slice(0, 4), c * colW + colW / 2, 10);
    }

    // Draw cursor
    drawOverlapCursor(ctx, W, H, T, rowH);
  }

  function drawOverlapCursor (ctx, W, H, T, rowH) {
    var t = Math.round(overlapCursorFrac * (T - 1));
    var y = t * rowH;
    ctx.save();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
    ctx.restore();
  }

  // ── Generated Music Comparison chart ────────────────────────────
  function renderComparisonChart () {
    var canvas = document.getElementById('comparisonCanvas');
    if (!canvas) return;
    var cd = window.HIBARI_COMPARISON_DATA;
    if (!cd) {
      var ctx2 = canvas.getContext('2d');
      ctx2.fillStyle = '#333';
      ctx2.font = '12px monospace';
      ctx2.fillText('comparison data not loaded', 16, canvas.height / 2);
      return;
    }

    var W = canvas.width  = canvas.offsetWidth  || 420;
    var H = canvas.height = canvas.offsetHeight || 180;
    var ctx = canvas.getContext('2d');

    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, W, H);

    var PAD_L = 38, PAD_R = 10, PAD_T = 32, PAD_B = 26;
    var chartW = W - PAD_L - PAD_R;
    var chartH = H - PAD_T - PAD_B;

    var orig   = cd.original.dist;
    var gen    = cd.generated.dist;
    var maxV   = Math.max.apply(null, orig.concat(gen)) * 1.15 || 0.25;
    var nPc    = cd.pc_names.length;   // 12
    var gW     = chartW / nPc;
    var barW   = gW * 0.36;
    var gap    = gW * 0.05;

    function yOf(v) { return PAD_T + chartH * (1 - v / maxV); }

    // Gridlines + Y labels
    ctx.font = '9px monospace';
    ctx.textAlign = 'right';
    for (var t = 0; t <= 4; t++) {
      var yv = maxV * t / 4;
      var yy = yOf(yv);
      ctx.strokeStyle = (t === 0) ? '#444' : '#222';
      ctx.lineWidth = (t === 0) ? 1 : 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD_L, yy);
      ctx.lineTo(W - PAD_R, yy);
      ctx.stroke();
      ctx.fillStyle = '#555';
      ctx.fillText(Math.round(yv * 100) + '%', PAD_L - 3, yy + 3);
    }

    // Bars + X labels
    ctx.textAlign = 'center';
    for (var i = 0; i < nPc; i++) {
      var xC = PAD_L + (i + 0.5) * gW;

      // original (blue)
      var hO = chartH * (orig[i] / maxV);
      ctx.fillStyle = 'rgba(100,150,255,0.88)';
      ctx.fillRect(xC - gap / 2 - barW, yOf(orig[i]), barW, hO);

      // generated (orange)
      var hG = chartH * (gen[i] / maxV);
      ctx.fillStyle = 'rgba(255,165,80,0.88)';
      ctx.fillRect(xC + gap / 2, yOf(gen[i]), barW, hG);

      // X label — only for non-zero pitch classes
      if (orig[i] > 0 || gen[i] > 0) {
        ctx.fillStyle = '#888';
        ctx.font = '9px monospace';
        ctx.fillText(cd.pc_names[i], xC, H - PAD_B + 12);
      }
    }

    // Chart title (left)
    ctx.fillStyle = '#aaa';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Pitch Class Distribution', PAD_L + 2, PAD_T - 18);

    // JS value (right) — prominent
    ctx.fillStyle = '#6f6';
    ctx.font = 'bold 13px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('JS = ' + cd.js_note.toFixed(4) + ' \u2605', W - PAD_R, PAD_T - 18);
  }

  // ── Rate application ──────────────────────────────────────────────
  function applyRate (rate) {
    currentRate = rate;
    // rate 전용 barcode 차트 갱신
    renderBarcodeChart(getRateEntry(rate));
    // 재생 중이 아닐 때는 rate 강도만 반영; 재생 중이면 overlap도 포함
    pushCombinedMults();
  }

  // ── Playback cursor update ────────────────────────────────────────
  function updatePlaybackCursor (frac) {
    overlapCursorFrac = Math.max(0, Math.min(1, frac));

    // overlap matrix 현재 row에서 A/B/C/D 활성화 여부 계산
    if (overlapData && colToCycle.length > 0) {
      var mat = overlapData.matrix;
      var T   = mat.length;
      var t   = Math.round(overlapCursorFrac * (T - 1));
      var row = (t >= 0 && t < T) ? mat[t] : [];

      // 각 사이클이 active(1)인지 집계
      var active = { A: false, B: false, C: false, D: false };
      for (var c = 0; c < row.length; c++) {
        if (row[c] && colToCycle[c]) active[colToCycle[c]] = true;
      }

      // 부드러운 전환 (lerp): 켜짐 → 1.0, 꺼짐 → OVERLAP_DIM
      ['A','B','C','D'].forEach(function (k) {
        var target = active[k] ? 1.0 : OVERLAP_DIM;
        overlapSmooth[k] += OVERLAP_SMOOTH * (target - overlapSmooth[k]);
      });

      // Tonnetz cycle polygon 즉시 업데이트
      pushCombinedMults();
    }

    // overlap heatmap 커서 갱신
    overlapCanvas = overlapCanvas || document.getElementById('overlapCanvas');
    if (overlapCanvas && overlapData) renderOverlapHeatmap();
  }

  // ── Init ──────────────────────────────────────────────────────────
  function init () {
    // Data is inlined via <script src="js/hibari_barcode_data.js"> etc.
    // Both set window globals synchronously before DOMContentLoaded.
    barcodeData = window.HIBARI_BARCODE_DATA || null;
    overlapData = window.HIBARI_OVERLAP_DATA || null;

    if (!barcodeData || !overlapData) {
      console.warn('hibaridata: inline data not found — check script tag order in index.html');
      return;
    }

    normalize();
    buildColToCycle();   // overlap column → ABCD 매핑 사전 계산

    // 콘솔 확인용: 매핑 결과 출력
    console.log('colToCycle:', colToCycle,
                '(ids:', (overlapData.cycle_ids || []).join(','), ')');

    // Defer first render so the DOM layout is fully stable
    setTimeout(function () {
      applyRate(currentRate);
      renderOverlapHeatmap();
      renderComparisonChart();
    }, 0);
  }

  window.hibariData = {
    init: init,
    applyRate: applyRate,
    updatePlaybackCursor: updatePlaybackCursor,
    renderOverlapHeatmap: renderOverlapHeatmap,
    renderComparisonChart: renderComparisonChart,
    renderBarcodeChart: function () {
      renderBarcodeChart(getRateEntry(currentRate));
    }
  };

})();
