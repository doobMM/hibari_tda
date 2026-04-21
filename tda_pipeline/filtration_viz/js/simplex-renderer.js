/* ============================================================================
 * simplex-renderer.js — 활성 note 기반 simplicial complex 렌더러 (3D 회전)
 *
 * 공개:
 *   const r = new SimplexRenderer(canvas, data);
 *   r.setLayout(name);                 // 'pc_helix' | 'mds_3d'
 *   r.setRotation(yaw, pitch);         // 라디안
 *   r.attachDrag();                    // 마우스/터치 드래그로 회전
 *   r.draw({ tick, eps, opts });
 *
 * 3D 좌표계:
 *   points3[i] ∈ [−1, 1]³ 중심원점.
 *   회전 적용 → 정사영(orthographic)으로 2D 투영.
 *   z-order로 vertex 앞뒤 감각을 살리기 위해 z_screen에 따라 크기/알파 조정.
 *
 * 활성 / cycle 로직은 이전과 동일.
 * ========================================================================= */
(function (global) {
  'use strict';

  const CYCLE_COLORS = [
    '#ffcd60', '#7ea5ff', '#ff6b8a', '#6bd4a5', '#d48aff',
    '#ffb36b', '#67d8e8', '#f07070', '#9de86b', '#c97bff',
    '#ff8cbe', '#70e0c5', '#ffd87e', '#8a9eff',
  ];

  class SimplexRenderer {
    constructor(canvas, data) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.data = data;
      this.dpr = Math.min(window.devicePixelRatio || 1, 2);

      this._normDist = this._computeNormalizedDist();
      this.layouts = {
        pc_helix: this._computePcHelixLayout(),
        mds_3d:   this._loadMds3dLayout(),
      };
      this.currentLayout = 'pc_helix';

      // 회전 상태 (라디안)
      this.yaw = 0.6;
      this.pitch = -0.25;

      this.lastStats = { activeCount: 0, edgeCount: 0, triCount: 0, activeCycles: [] };
      this.lastProjected = null;
      this._resize();
    }

    setLayout(name) {
      if (this.layouts[name]) this.currentLayout = name;
    }
    setRotation(yaw, pitch) {
      this.yaw = yaw;
      this.pitch = Math.max(-Math.PI / 2 + 0.1, Math.min(Math.PI / 2 - 0.1, pitch));
    }

    _computeNormalizedDist() {
      const { N, dist, distMin, distMax } = this.data;
      const range = Math.max(1e-9, distMax - distMin);
      const nd = new Float32Array(N * N);
      for (let i = 0; i < N * N; i++) {
        nd[i] = (dist[i] - distMin) / range;
      }
      return nd;
    }

    _loadMds3dLayout() {
      // data-loader가 points3를 채워두면 그걸 쓴다. 없으면 z=0.
      const { N, points3 } = this.data;
      if (points3 && points3.length === N * 3) {
        return Float32Array.from(points3);
      }
      const { points } = this.data;
      const out = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        out[i * 3]     = (points[i * 2]     - 0.5) * 2;
        out[i * 3 + 1] = (points[i * 2 + 1] - 0.5) * 2;
        out[i * 3 + 2] = 0;
      }
      return out;
    }

    _computePcHelixLayout() {
      // 원기둥 나선:
      //   x = cos(pc 각도 in circle of fifths)
      //   z = sin(pc 각도)
      //   y = pitch (octave 기반, [-1,1])
      const { N, notes } = this.data;
      const COF = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5];
      const pcToAngle = new Array(12);
      for (let i = 0; i < 12; i++) {
        pcToAngle[COF[i]] = (2 * Math.PI * i / 12);
      }
      let minP = Infinity, maxP = -Infinity;
      for (const n of notes) {
        if (n.pitch < minP) minP = n.pitch;
        if (n.pitch > maxP) maxP = n.pitch;
      }
      const pRange = Math.max(1, maxP - minP);

      const out = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        const p = notes[i];
        const ang = pcToAngle[p.pc];
        const r = 0.85;
        const yNorm = -1 + 2 * ((p.pitch - minP) / pRange);      // 낮은 음 아래
        out[i * 3]     = r * Math.cos(ang);
        out[i * 3 + 1] = yNorm * 0.9;
        out[i * 3 + 2] = r * Math.sin(ang);
      }
      return out;
    }

    _resize() {
      const c = this.canvas;
      const rect = c.getBoundingClientRect();
      const w = Math.max(320, Math.floor(rect.width));
      const h = Math.max(320, Math.floor(rect.height || rect.width * 0.72));
      c.width = Math.floor(w * this.dpr);
      c.height = Math.floor(h * this.dpr);
      this.cw = w;
      this.ch = h;
    }

    _project() {
      // 현재 layout + 회전으로 3D→2D 정사영
      const pts = this.layouts[this.currentLayout];
      const N = this.data.N;
      const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw);
      const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
      const pad = 44;
      const halfW = (this.cw - 2 * pad) / 2;
      const halfH = (this.ch - 2 * pad) / 2;
      const cx = this.cw / 2, cc = this.ch / 2;
      const scale = Math.min(halfW, halfH);

      const out = new Float32Array(N * 3);   // [sx, sy, sz(depth)]
      for (let i = 0; i < N; i++) {
        const x = pts[i * 3], y = pts[i * 3 + 1], z = pts[i * 3 + 2];
        // Yaw (y-axis) 회전
        const x1 = cy * x + sy * z;
        const z1 = -sy * x + cy * z;
        // Pitch (x-axis) 회전
        const y2 = cp * y - sp * z1;
        const z2 = sp * y + cp * z1;
        // 정사영
        out[i * 3]     = (cx + x1 * scale) * this.dpr;
        out[i * 3 + 1] = (cc - y2 * scale) * this.dpr;   // y 위로
        out[i * 3 + 2] = z2;                                // depth ∈ [−1, 1]
      }
      this.lastProjected = out;
      return out;
    }

    _depthAlpha(z) {
      // z ∈ [−1, 1]. 뒤쪽(+z일수록 멀다, 이때 +) 어둡게.
      // 회전 후 z1 = sp*y + cp*z1 — 부호는 바라보는 방향에 따라 다름.
      // 우리 규약: z가 클수록 뒤 (0.45) / z가 작을수록 앞 (1.0)
      return 0.45 + 0.55 * (1 - (z + 1) / 2);
    }

    _clear() {
      this.ctx.fillStyle = '#0a0b10';
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    draw({ tick, eps, opts }) {
      this._resize();
      const ctx = this.ctx;
      const { N, active, cycles } = this.data;
      const nd = this._normDist;
      const options = Object.assign({
        showTriangles: true,
        showCycles: true,
        showLabels: true,
        filtrationMode: false,
      }, opts || {});

      this._clear();
      const proj = this._project();

      // 활성 집합
      let activeSet;
      if (options.filtrationMode) {
        activeSet = new Uint8Array(N).fill(1);
      } else {
        const row = tick * N;
        activeSet = new Uint8Array(N);
        for (let i = 0; i < N; i++) activeSet[i] = active[row + i];
      }

      // Edge / triangle
      const edges = [];
      for (let i = 0; i < N; i++) {
        if (!activeSet[i]) continue;
        for (let j = i + 1; j < N; j++) {
          if (!activeSet[j]) continue;
          if (nd[i * N + j] <= eps) edges.push([i, j]);
        }
      }
      const triangles = [];
      if (options.showTriangles) {
        for (let a = 0; a < edges.length; a++) {
          const [i, j] = edges[a];
          for (let k = j + 1; k < N; k++) {
            if (!activeSet[k]) continue;
            if (nd[i * N + k] <= eps && nd[j * N + k] <= eps) {
              triangles.push([i, j, k]);
            }
          }
        }
      }

      const xy = (i) => [proj[i * 3], proj[i * 3 + 1]];
      const depthMean = (...idxs) => {
        let s = 0;
        for (const i of idxs) s += proj[i * 3 + 2];
        return s / idxs.length;
      };

      // ── 1. Triangle 채움 (depth-sort)
      if (options.showTriangles) {
        const sorted = triangles.slice().sort(
          (a, b) => depthMean(...b) - depthMean(...a)
        );
        for (const [i, j, k] of sorted) {
          const zm = depthMean(i, j, k);
          ctx.fillStyle = `rgba(126, 165, 255, ${0.08 + 0.14 * (1 - (zm + 1) / 2)})`;
          const [x1, y1] = xy(i), [x2, y2] = xy(j), [x3, y3] = xy(k);
          ctx.beginPath();
          ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.lineTo(x3, y3);
          ctx.closePath();
          ctx.fill();
        }
      }

      // ── 2. Edge
      ctx.lineWidth = 1.2 * this.dpr;
      for (const [i, j] of edges) {
        const zm = (proj[i * 3 + 2] + proj[j * 3 + 2]) / 2;
        const a = 0.35 + 0.55 * (1 - (zm + 1) / 2);
        ctx.strokeStyle = `rgba(180, 200, 240, ${a.toFixed(3)})`;
        const [x1, y1] = xy(i), [x2, y2] = xy(j);
        ctx.beginPath();
        ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
        ctx.stroke();
      }

      // ── 3. Cycle overlay
      //   판정: 연속 중첩행렬 overlapCont[t*K + c] ∈ [0, 1] 을 alpha 강도로 직접 사용.
      //   (Algo2 FC-cont JS=0.00035 절대 최저 기록의 입력 OM과 동일.)
      //   MIN_VIS 미만은 렌더 생략 (잡음 방지).
      //   폴백: overlapCont 미제공 → "모든 vertex 동시 활성" 판정 (이전 방식).
      //   filtrationMode 시 모든 cycle overlay 표시 (ε sweep 맥락).
      const activeCycles = [];
      const { overlapCont, K: Kfull } = this.data;
      const useOverlap = !options.filtrationMode && overlapCont && Kfull > 0;
      const MIN_VIS = 0.05;
      if (options.showCycles) {
        for (const c of cycles) {
          const verts = c.vertices_0idx;
          let intensity = 1.0;
          if (useOverlap) {
            const v = overlapCont[tick * Kfull + c.cycle_idx];
            if (!(v > MIN_VIS)) continue;
            intensity = Math.max(0, Math.min(1, v));
          } else {
            let allActive = true;
            for (const v of verts) {
              if (!activeSet[v]) { allActive = false; break; }
            }
            if (!allActive) continue;
          }
          activeCycles.push(c.cycle_idx);
          const color = CYCLE_COLORS[c.cycle_idx % CYCLE_COLORS.length];
          ctx.strokeStyle = color;
          ctx.globalAlpha = 0.25 + 0.75 * intensity;
          ctx.lineWidth = (1.2 + 1.6 * intensity) * this.dpr;
          ctx.shadowColor = color;
          ctx.shadowBlur = (2 + 6 * intensity) * this.dpr;
          const pts = verts.map(v => xy(v));
          const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
          const cyc = pts.reduce((s, p) => s + p[1], 0) / pts.length;
          const sorted = pts.slice().sort((a, b) =>
            Math.atan2(a[1] - cyc, a[0] - cx) - Math.atan2(b[1] - cyc, b[0] - cx)
          );
          ctx.beginPath();
          ctx.moveTo(sorted[0][0], sorted[0][1]);
          for (let i = 1; i < sorted.length; i++) {
            ctx.lineTo(sorted[i][0], sorted[i][1]);
          }
          ctx.closePath();
          ctx.stroke();
          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1;
        }
      }

      // ── 4. Vertex (depth-sort back to front)
      const order = [];
      for (let i = 0; i < N; i++) order.push(i);
      order.sort((a, b) => proj[b * 3 + 2] - proj[a * 3 + 2]);  // 큰 z가 뒤

      for (const i of order) {
        const [x, y] = xy(i);
        const z = proj[i * 3 + 2];
        const front = (1 - (z + 1) / 2);       // 앞=1, 뒤=0
        const on = activeSet[i];
        const r = (on ? 5.5 + 2 * front : 3 + 1.5 * front) * this.dpr;
        ctx.fillStyle = on
          ? `rgba(255, 255, 255, ${0.6 + 0.4 * front})`
          : `rgba(80, 90, 110, ${0.45 + 0.45 * front})`;
        ctx.strokeStyle = on ? 'rgba(255,255,255,0.9)' : 'rgba(80,90,110,0.8)';
        ctx.lineWidth = (on ? 1.5 : 1) * this.dpr;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        if (on) ctx.stroke();
      }

      // ── 5. Label
      if (options.showLabels) {
        ctx.font = `${11 * this.dpr}px 'Fira Code', monospace`;
        ctx.textBaseline = 'middle';
        const notes = this.data.notes;
        for (let i = 0; i < N; i++) {
          const [x, y] = xy(i);
          const z = proj[i * 3 + 2];
          const front = (1 - (z + 1) / 2);
          const on = activeSet[i];
          const p = notes[i];
          const text = p ? pitchName(p.pitch) : String(i + 1);
          ctx.globalAlpha = (on ? 1.0 : 0.4) * (0.5 + 0.5 * front);
          ctx.fillStyle = '#c9cdd7';
          ctx.fillText(text, x + 8 * this.dpr, y - 8 * this.dpr);
        }
        ctx.globalAlpha = 1;
      }

      let activeCount = 0;
      for (let i = 0; i < N; i++) if (activeSet[i]) activeCount++;

      this.lastStats = {
        activeCount,
        edgeCount: edges.length,
        triCount: triangles.length,
        activeCycles,
      };
      return this.lastStats;
    }

    attachDrag(onChange) {
      const c = this.canvas;
      let dragging = false;
      let lastX = 0, lastY = 0;
      const onDown = (ev) => {
        dragging = true;
        const pt = ev.touches ? ev.touches[0] : ev;
        lastX = pt.clientX;
        lastY = pt.clientY;
        ev.preventDefault();
      };
      const onMove = (ev) => {
        if (!dragging) return;
        const pt = ev.touches ? ev.touches[0] : ev;
        const dx = pt.clientX - lastX;
        const dy = pt.clientY - lastY;
        lastX = pt.clientX;
        lastY = pt.clientY;
        const scale = 0.01;
        this.setRotation(this.yaw + dx * scale, this.pitch - dy * scale);
        if (onChange) onChange();
        ev.preventDefault();
      };
      const onUp = () => { dragging = false; };

      c.addEventListener('mousedown', onDown);
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      c.addEventListener('touchstart', onDown, { passive: false });
      c.addEventListener('touchmove', onMove,  { passive: false });
      c.addEventListener('touchend', onUp);
    }
  }

  const PC_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  function pitchName(midi) {
    const pc = ((midi % 12) + 12) % 12;
    const oct = Math.floor(midi / 12) - 1;
    return `${PC_NAMES[pc]}${oct}`;
  }

  global.SimplexRenderer = SimplexRenderer;
  global.CYCLE_COLORS = CYCLE_COLORS;
})(window);
