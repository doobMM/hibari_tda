var tonnetz = (function() {
  "use strict";

  var module = {};

  var TONE_NAMES = ['C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'];
  var STATE_OFF = 0,
      STATE_GHOST = 1,
      STATE_SUST = 2,
      STATE_ON = 3;
  var STATE_NAMES = ['OFF', 'GHOST', 'SUSTAIN', 'ON'];
  var LAYOUT_RIEMANN = 'riemann',
      LAYOUT_SONOME = 'sonome';

  var W,  // width
      H,  // height
      u;  // unit distance (distance between neighbors)

  module.density = 22;
  module.ghostDuration = 500;
  module.layout = LAYOUT_RIEMANN;
  module.unitCellVisible = false;

  // ── (a, b, c) interval parameters ────────────────────────────────
  // 6 directions of the hex grid: a, b, c=a+b and their complements.
  // Default: (3, 4, 7) = minor third / major third / perfect fifth.
  var iA = 3, iB = 4, iC = 7;

  var toneGrid = [];
  var tones;
  var channels;

  var sustainEnabled = true,
      sustain = false;

  var SQRT_3 = Math.sqrt(3);
  var CHANNELS = 17;  // the 17th channel is for the computer keyboard


  module.init = function() {
    tones = $.map(Array(12), function(_, i) {
      return {
        'pitch': i,
        'name': TONE_NAMES[i],
        'state': STATE_OFF,
        'byChannel': {},     // counts of this tone in each channel
        'channelsSust': {},  // channels where the tone is sustained
        'released': null,    // the last time the note was on
        'cache': {}          // temporary data
      };
    });

    channels = $.map(Array(CHANNELS), function(_, i) {
      return {
        'number': i,
        'pitches': {},
        'sustTones': {},
        'sustain': false
      };
    });

    this.rebuild();
    window.onresize = function() { module.rebuild(); };
  };


  module.noteOn = function(c, pitch) {
    audio.noteOn(c, pitch);

    if (!(pitch in channels[c].pitches)) {
      var i = pitch%12;
      tones[i].state = STATE_ON;

      if (!tones[i].byChannel[c])
        tones[i].byChannel[c] = 1;
      else
        tones[i].byChannel[c]++;

      channels[c].pitches[pitch] = 1;

      // Remove sustain
      delete tones[i].channelsSust[c];
      delete channels[c].sustTones[i];
    }
    this.draw();
  };

  module.noteOff = function(c, pitch) {
    audio.noteOff(c, pitch);

    if (pitch in channels[c].pitches) {
      var i = pitch%12;
      delete channels[c].pitches[pitch];
      tones[i].byChannel[c]--;

      // Check if this was the last instance of the tone in this channel
      if (tones[i].byChannel[c] === 0) {
        delete tones[i].byChannel[c];

        // Check if this was the last channel with this tone
        if ($.isEmptyObject(tones[i].byChannel)) {
          if (sustainEnabled && channels[c].sustain) {
            tones[i].state = STATE_SUST;
            channels[c].sustTones[i] = 1;
          } else {
            // change state to STATE_GHOST or STATE_OFF
            // depending on setting
            releaseTone(tones[i]);
          }
        }
      }

      this.draw();
    }
  };

  module.allNotesOff = function(c) {
    audio.allNotesOff(c);

    for (var i=0; i<12; i++) {
      delete tones[i].byChannel[c];
      delete tones[i].channelsSust[c];

      // Check if this tone is turned off in all channels
      if ($.isEmptyObject(tones[i].byChannel)) {
        tones[i].state = STATE_OFF;
      }
    }

    channels[c].pitches = {};
    channels[c].sustTones = {};

    this.draw();
  };

  module.sustainOn = function(c) {
    channels[c].sustain = true;
  };

  module.sustainOff = function(c) {
    channels[c].sustain = false;
    channels[c].sustTones = {};

    for (var i=0; i<12; i++) {
      delete tones[i].channelsSust[c];

      if (tones[i].state == STATE_SUST &&
          $.isEmptyObject(tones[i].channelsSust)) {
        releaseTone(tones[i]);
      }
    }

    this.draw();
  };

  module.panic = function() {
    for (var i=0; i<CHANNELS; i++) {
      this.sustainOff(i);
      this.allNotesOff(i);
    }
  };


  module.toggleSustainEnabled = function() {
    sustainEnabled = !sustainEnabled;
  };

  // Returns array of pitch classes (0-11) currently ON or SUSTAINED.
  // Used by transforms.js for Neo-Riemannian operations.
  module.getActivePC = function() {
    var pcs = [];
    for (var i = 0; i < 12; i++) {
      if (tones[i].state === STATE_ON || tones[i].state === STATE_SUST) {
        pcs.push(i);
      }
    }
    return pcs;
  };

  module.setDensity = function(density) {
    if (isFinite(density) && density >= 5 && density <= 50) {
      this.density = density;
      this.rebuild();
    }
  };

  module.setGhostDuration = function(duration) {
    if (isFinite(duration) && duration !== null && duration !== '') {
      duration = Number(duration);
      if (duration >= 0) {
        if (duration != this.ghostDuration) {
          this.ghostDuration = duration;
          this.draw();
        }
        return true;
      }
    }

    return false;
  };

  module.setLayout = function(layout) {
    this.layout = layout;
    this.rebuild();
  };

  module.setIntervals = function(a, b) {
    iA = ((a % 12) + 12) % 12;
    iB = ((b % 12) + 12) % 12;
    iC = (iA + iB) % 12;
    this.rebuild();
  };

  module.toggleUnitCell = function() {
    this.unitCellVisible = !this.unitCellVisible;
    this.draw();
  };


  var releaseTone = function(tone) {
    tone.release = new Date();
    if (module.ghostDuration > 0) {
      tone.state = STATE_GHOST;
      ghosts();
    } else {
      tone.state = STATE_OFF;
    }
  };


  var ghostsInterval = null;

  /**
   * Check for dead ghost tones and turn them off. Keep
   * checking using setInterval as long as there are
   * any ghost tones left.
   */
  var ghosts = function() {
    if (ghostsInterval === null) {
      ghostsInterval = setInterval(function() {
        var numAlive = 0, numDead = 0;
        var now = new Date();

        for (var i=0; i<12; i++) {
          if (tones[i].state == STATE_GHOST) {
            if (now - tones[i].release >= module.ghostDuration) {
              tones[i].state = STATE_OFF;
              numDead++;
            } else {
              numAlive++;
            }
          }
        }

        if (numAlive == 0) {
          clearInterval(ghostsInterval);
          ghostsInterval = null;
        }

        if (numDead>0)
          module.draw();
      }, Math.min(module.ghostDuration, 30));
    }
  };


  var drawTimeout = null;

  /**
   * Request a redraw. If true is passed as a parameter, redraw immediately.
   * Otherwise, draw at most once every 30 ms.
   */
  module.draw = function(immediately) {
    if (immediately) {
      if (drawTimeout !== null) {
        clearTimeout(drawTimeout);
      }
      drawNow();
    } else if (drawTimeout === null) {
      drawTimeout = setTimeout(drawNow, 30);
    }
  };

  // ── H1 cycle overlay ──────────────────────────────────────────────
  // hibari H1 cycles (pitch-class level).
  // Each cycle is defined by its root pitch class and a sequence of
  // interval steps (in semitones) that trace the polygon edges.
  // Edge directions follow the Tonnetz interval lattice:
  //   3 = minor 3rd (left-up),  4 = major 3rd (right-up),
  //   7 = perfect 5th (right),  and their inverses (9, 8, 5).
  module.cyclesVisible = true;

  // Rate-based multipliers (0..1) set by hibaridata.js.
  // When 0, a cycle is barely visible; at 1, full opacity.
  var rateMultipliers = [1, 1, 1, 1]; // index matches H1_CYCLES order

  module.setRateMultipliers = function (a, b, c, d) {
    rateMultipliers = [a, b, c, d];
    this.draw();
  };

  var H1_CYCLES = [
    // A: E–G–B  (E minor triad)
    { root: 4,  steps: [3, 4],    color: 'rgba(100,220,100,{a})', pitches: [4, 7, 11] },
    // B: C–E–G  (C major triad)
    { root: 0,  steps: [4, 3],    color: 'rgba(100,150,255,{a})', pitches: [0, 4,  7] },
    // C: D–F–A  (D minor triad)
    { root: 2,  steps: [3, 4],    color: 'rgba(255,165, 80,{a})', pitches: [2, 5,  9] },
    // D: F–A–E–C  (parallelogram: two stacked triangles)
    { root: 5,  steps: [4, 7, 8], color: 'rgba(200,100,255,{a})', pitches: [5, 9,  4, 0] }
  ];

  // Compute the (dx, dy) offset for a single Tonnetz interval step,
  // respecting the current layout (Riemann vs Sonome).
  // Maps a semitone interval to a hex-grid XY offset.
  // The 6 directions correspond to (iA, iB, iC) and their complements.
  var cycleStepOffset = function(diff) {
    var r;
    var d = ((diff % 12) + 12) % 12;
    if      (d === iA)          r = {x: -0.5*SQRT_3*u, y: -0.5*u};
    else if (d === iB)          r = {x:  0.5*SQRT_3*u, y: -0.5*u};
    else if (d === iC)          r = {x:  0,            y: -1.0*u};
    else if (d === (12-iA)%12)  r = {x:  0.5*SQRT_3*u, y:  0.5*u};
    else if (d === (12-iB)%12)  r = {x: -0.5*SQRT_3*u, y:  0.5*u};
    else if (d === (12-iC)%12)  r = {x:  0,            y:  1.0*u};
    else                        r = {x: 0, y: 0};
    if (module.layout === LAYOUT_RIEMANN) {
      r = {x: -r.y, y: r.x};
    }
    return r;
  };

  // Build polygon vertex offsets (relative to root node) from step list.
  var buildCycleOffsets = function(steps) {
    var pts = [{x: 0, y: 0}];
    for (var k = 0; k < steps.length; k++) {
      var off = cycleStepOffset(steps[k]);
      pts.push({x: pts[k].x + off.x, y: pts[k].y + off.y});
    }
    return pts;
  };

  // Compute activation fraction for a cycle (0..1) based on currently active tones.
  var cycleActivation = function(pitches) {
    var on = 0;
    pitches.forEach(function(p) {
      if (tones[p].state === STATE_ON || tones[p].state === STATE_SUST) on++;
    });
    return on / pitches.length;
  };

  // Draw all H1 cycle polygons onto ctx.
  // Alpha scales with activation: idle → dim, partial → medium, all-on → full glow.
  var drawCycleOverlays = function() {
    if (!module.cyclesVisible) return;
    // H1 cycles are defined for standard (3,4,7) intervals only.
    if (iA !== 3 || iB !== 4) return;

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    H1_CYCLES.forEach(function(cyc, cycIdx) {
      var pts  = buildCycleOffsets(cyc.steps);
      var frac = cycleActivation(cyc.pitches);   // 0..1

      // Rate multiplier (0..1): scales idle and active alpha proportionally.
      // A multiplier of 0 makes the cycle nearly invisible.
      var rm = Math.max(0.05, rateMultipliers[cycIdx] !== undefined ? rateMultipliers[cycIdx] : 1);

      // fill alpha:   0.08 (idle) → 0.55 (fully on), scaled by rate multiplier
      // stroke alpha: 0.30 (idle) → 1.00 (fully on), scaled by rate multiplier
      var fillA   = ((0.08 + frac * 0.47) * rm).toFixed(3);
      var strokeA = ((0.30 + frac * 0.70) * rm).toFixed(3);

      toneGrid[cyc.root].forEach(function(node) {
        var drawPath = function() {
          ctx.beginPath();
          ctx.moveTo(node.x + pts[0].x, node.y + pts[0].y);
          for (var k = 1; k < pts.length; k++) {
            ctx.lineTo(node.x + pts[k].x, node.y + pts[k].y);
          }
          ctx.closePath();
        };

        // Glow halo when fully active
        if (frac >= 1.0) {
          drawPath();
          ctx.shadowBlur   = 18;
          ctx.shadowColor  = cyc.color.replace('{a}', '1');
          ctx.strokeStyle  = cyc.color.replace('{a}', '0.55');
          ctx.lineWidth    = 9;
          ctx.stroke();
          ctx.shadowBlur   = 0;
          ctx.lineWidth    = 2;
        }

        // Normal fill + stroke
        drawPath();
        ctx.fillStyle   = cyc.color.replace('{a}', fillA);
        ctx.fill();
        ctx.strokeStyle = cyc.color.replace('{a}', strokeA);
        ctx.lineWidth   = frac >= 1.0 ? 2.5 : 2;
        ctx.stroke();
      });
    });

    ctx.restore();
  };
  // ── end H1 cycle overlay ──────────────────────────────────────────




  var drawNow = function() {
    drawTimeout = null;

    colorscheme.update();

    var xUnit = u*SQRT_3/2;
    var uW = Math.ceil(Math.ceil(W/xUnit*2)/2);
    var uH = Math.ceil(H/u);

    var now = new Date();

    ctx.clearRect(0, 0, W, H);

    // Fill faces. Each vertex takes care of the two faces above it.
    for (var tone=0; tone<12; tone++) {
      var c = tones[tone].cache;

      var leftNeighbor = (tone+iA)%12;
      var rightNeighbor = (tone+iB)%12;
      var topNeighbor = (tone+iC)%12;

      c.leftPos = getNeighborXYDiff(tone, leftNeighbor);
      c.rightPos = getNeighborXYDiff(tone, rightNeighbor);
      c.topPos = getNeighborXYDiff(tone, topNeighbor);

      c.leftState = tones[leftNeighbor].state;
      c.rightState = tones[rightNeighbor].state;
      c.topState = tones[topNeighbor].state;

      var thisOn = (tones[tone].state != STATE_OFF);
      var leftOn = (c.leftState != STATE_OFF);
      var rightOn = (c.rightState != STATE_OFF);
      var topOn = (c.topState != STATE_OFF);

      // Fill faces
      for (var i=0; i<toneGrid[tone].length; i++) {
        setTranslate(ctx, toneGrid[tone][i].x, toneGrid[tone][i].y);

        var minorOn = false, majorOn = false;
        if (thisOn && topOn) {
          if (leftOn) { // left face (minor triad)
            minorOn = true;
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(c.topPos.x, c.topPos.y);
            ctx.lineTo(c.leftPos.x, c.leftPos.y);
            ctx.closePath();
            ctx.fillStyle = colorscheme.minorFill;
            ctx.fill();
          }
          if (rightOn) { // right face (major triad)
            majorOn = true;
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(c.topPos.x, c.topPos.y);
            ctx.lineTo(c.rightPos.x, c.rightPos.y);
            ctx.closePath();
            ctx.fillStyle = colorscheme.majorFill;
            ctx.fill();
          }
        }

        var $minorTriadLabel = $(toneGrid[tone][i].minorTriadLabel);
        var $majorTriadLabel = $(toneGrid[tone][i].majorTriadLabel);

        if (minorOn) {
          $minorTriadLabel.addClass('state-ON');
        } else {
          $minorTriadLabel.removeClass('state-ON');
        }

        if (majorOn) {
          $majorTriadLabel.addClass('state-ON');
        } else {
          $majorTriadLabel.removeClass('state-ON');
        }
      }
    }

    if (module.unitCellVisible){
      drawUnitCell(ctx);
    };

    // H1 cycle polygon overlays (drawn above face fills, below edges/vertices)
    drawCycleOverlays();

    // Draw edges. Each vertex takes care of the three upward edges.
    for (var tone=0; tone<12; tone++) {
      var c = tones[tone].cache;
      var state = tones[tone].state;

      for (var i=0; i<toneGrid[tone].length; i++) {
        setTranslate(ctx, toneGrid[tone][i].x, toneGrid[tone][i].y);

        drawEdge(ctx, c.topPos, state, c.topState);
        drawEdge(ctx, c.leftPos, state, c.leftState);
        drawEdge(ctx, c.rightPos, state, c.rightState);
      }
    }

    setTranslate(ctx, 0, 0);

    // Draw vertices.
    for (var tone=0; tone<12; tone++) {
      for (var i=0; i<toneGrid[tone].length; i++) {
        var x = toneGrid[tone][i].x, y = toneGrid[tone][i].y;
        var state = tones[tone].state;

        // ── 강도(weight) 계산: 같은 pitch class가 옥타브/채널에 걸쳐
        //   동시에 활성화된 총 음 수 (e.g. inst1 E3 + inst2 E4 → weight=2)
        var weight = 0;
        for (var ch in tones[tone].byChannel) {
          weight += tones[tone].byChannel[ch];
        }
        if (weight === 0 && state === STATE_ON) weight = 1; // 방어 코드

        // weight > 1 일 때: 뒤에 배치되는 글로우 헤일로 (동심원)
        if (state === STATE_ON && weight >= 2) {
          var rings = Math.min(weight - 1, 3);  // 최대 3링
          for (var r = rings; r >= 1; r--) {
            ctx.beginPath();
            ctx.arc(x, y, u/5 * (1 + 0.55 * r), 0, Math.PI * 2, false);
            ctx.closePath();
            ctx.strokeStyle = colorscheme.stroke[STATE_ON];
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.55 / r;
            ctx.stroke();
          }
          ctx.globalAlpha = 1.0;
        }

        // 기본 노드 (radius: weight=1 → u/5, weight≥2 → 살짝 크게)
        var baseRadius = (state === STATE_ON && weight >= 2)
                         ? u/5 * (1 + 0.12 * Math.min(weight - 1, 3))
                         : u/5;

        ctx.beginPath();
        ctx.arc(x, y, baseRadius, 0, Math.PI * 2, false);
        ctx.closePath();

        ctx.fillStyle = colorscheme.fill[state];
        ctx.strokeStyle = colorscheme.stroke[state];
        toneGrid[tone][i].label.className = 'state-' + STATE_NAMES[state];

        ctx.lineWidth = (state === STATE_OFF) ? 1 : 2;
        ctx.fill();
        ctx.stroke();
      }
    }

  };

  var setTranslate = function(ctx, x, y) {
    ctx.setTransform(1, 0, 0, 1, x, y);
  };

  var drawEdge = function(ctx, endpoint, state1, state2) {
    var state = Math.min(state1, state2);

    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(endpoint.x, endpoint.y);
    ctx.strokeStyle = colorscheme.stroke[state];
    ctx.lineWidth = (state != STATE_OFF) ? 1.5 : 1;
    ctx.stroke();
  };

  // Reuses cycleStepOffset — same logic, just computed from two pitch classes.
  var getNeighborXYDiff = function(t1, t2) {
    return cycleStepOffset((t2 - t1 + 12) % 12);
  };

  var createLabel = function(text, x, y) {
    var label = document.createElement('div');
    var inner = document.createElement('div');
    inner.appendChild(document.createTextNode(text));
    label.appendChild(inner);
    label.style.left = x + 'px';
    label.style.top = y + 'px';
    return label;
  };

  var addNode = function(tone, x, y) {
    if (x < -u || y < -u || x > W+u || y > H+u) {
      return;
    }

    var name = tones[tone].name;
    var node = {'x': x, 'y': y};

    // Create the note label.
    node.label = createLabel(name, x, y);
    noteLabels.appendChild(node.label);

    // Create labels for the two triads above this node.
    if (module.layout == LAYOUT_RIEMANN) {
      var yUnit = u * SQRT_3;
      node.majorTriadLabel = createLabel(name.toUpperCase(), x + u/2, y + yUnit/6);
      node.minorTriadLabel = createLabel(name.toLowerCase(), x + u/2, y - yUnit/6);
    } else if (module.layout == LAYOUT_SONOME) {
      var xUnit = u * SQRT_3;
      node.majorTriadLabel = createLabel(name.toUpperCase(), x + xUnit/6, y - u/2);
      node.minorTriadLabel = createLabel(name.toLowerCase(), x - xUnit/6, y - u/2);
    }
    node.majorTriadLabel.className = 'major';
    node.minorTriadLabel.className = 'minor';
    triadLabels.appendChild(node.majorTriadLabel);
    triadLabels.appendChild(node.minorTriadLabel);

    // Add the node to the grid.
    toneGrid[tone].push(node);
  };

  var drawUnitCell = function(ctx) {
    // Unit cell geometry is only valid for standard (3,4,7) intervals.
    if (iA !== 3 || iB !== 4) return;
    var closest = getNeighborXYDiff(0,3);
    setTranslate(ctx, W/2-closest.x, H/2-closest.y);

    ctx.beginPath();
    ctx.moveTo(0, 0);
    if (module.layout == LAYOUT_RIEMANN) {
      ctx.lineTo(1.5*u, 3*SQRT_3*u/2);
      ctx.lineTo(3.5*u, -1*SQRT_3*u/2);
      ctx.lineTo(2*u, -4*SQRT_3*u/2);
    } else if (module.layout == LAYOUT_SONOME) {
      ctx.lineTo(-2*SQRT_3*u, -2*u);
      ctx.lineTo(-3.5*SQRT_3*u, -0.5*u);
      ctx.lineTo(-1.5*SQRT_3*u, 1.5*u);
    }
    ctx.lineTo(0, 0);
    ctx.strokeStyle = colorscheme.stroke[0];
    ctx.lineWidth = 4;
    ctx.stroke();
  };

  module.rebuild = function() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    u = (W+H)/this.density;

    for (var i=0; i<12; i++) {
      toneGrid[i] = [];
    }

    $(noteLabels).empty();
    $(triadLabels).empty();

    $(noteLabels).css('font-size', u * 0.17 + 'px');
    $(triadLabels).css('font-size', u * 0.17 + 'px');

    if (this.layout == LAYOUT_RIEMANN) {
      var yUnit = u * SQRT_3;
      var uW = Math.ceil(W/u);
      var uH = Math.ceil(H/yUnit);
      for(var j=-Math.floor(uW/2+1); j<=Math.floor(uW/2+1); j++){
        for(var i=-Math.floor(uH/2+1); i<=Math.floor(uH/2+1); i++){
          addNode(((i-iC*j)%12 + 12)%12,
                  W/2 - j*u,
                  H/2 + i*yUnit);

          addNode(((i-iC*j)%12 + 12 + iB)%12,
                  W/2 - (j - 0.5)*u,
                  H/2 + (i + 0.5)*yUnit);
        }
      }
    } else if (this.layout == LAYOUT_SONOME) {
      var xUnit = u * SQRT_3;
      var uW = Math.ceil(W/xUnit);
      var uH = Math.ceil(H/u);

      for (var j=-Math.floor(uH/2+1); j<=Math.floor(uH/2+1); j++) {
        for (var i=-Math.floor(uW/2+1); i<=Math.floor(uW/2+1); i++) {
          addNode(((i-iC*j)%12 + 12)%12,
                  W/2 + i*xUnit,
                  H/2 + j*u);

          addNode(((i-iC*j)%12 + 12 + iB)%12,
                  W/2 + (i + 0.5)*xUnit,
                  H/2 + (j - 0.5)*u);
        }
      }
    }

    this.draw(true);
  };

  return module;
})();
