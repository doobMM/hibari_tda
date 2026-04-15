/* ============================================================================
 * overlap-editor.js — Canvas 기반 overlap matrix 에디터
 *
 * OverlapEditor API:
 *   const ed = new OverlapEditor(canvas, { T, K, readonly, onChange })
 *   ed.setMatrix(Int8Array)    — 내부 상태 교체 (전체 재그리기)
 *   ed.getMatrix()             — 현재 Int8Array 반환 (같은 참조)
 *   ed.setReference(Int8Array) — diff 비교용 참조. 같은 T×K 크기여야 함.
 *   ed.setDiffMode(bool)
 *   ed.resetToReference()      — 참조로 복구
 *   ed.randomFill(density)     — 전체를 density 확률로 채움
 *   ed.clearAll()
 *   ed.density()               — 현재 ON 비율
 *   ed.diffCount()             — 참조와의 Hamming distance
 *
 * Zoom/Pan:
 *   - 기본 fit-to-canvas
 *   - 휠: 줌 (focal = 마우스 위치)
 *   - Shift+드래그: 팬
 *   - 더블클릭: fit 복구
 *
 * 이벤트:
 *   - 좌클릭: 셀 토글 → 'change'
 *   - 좌 드래그: 시작 셀의 반대 상태로 통일 칠하기
 *   - 우클릭: 셀 → 0 강제
 *   - 모든 변경 시 onChange 콜백 호출
 * ========================================================================= */

(function (global) {
  'use strict';

  const CELL_ON_RGB   = [74, 222, 128];     // #4ADE80
  const CELL_OFF_RGB  = [26, 26, 47];       // #1A1A2F
  const CELL_ADD_RGB  = [56, 189, 248];     // #38BDF8 — 편집에서 추가됨
  const CELL_DEL_RGB  = [244, 114, 182];    // #F472B6 — 편집에서 제거됨
  const HOVER_STROKE  = 'rgba(251, 191, 36, 0.9)';
  const GRID_STROKE   = 'rgba(67, 56, 202, 0.08)';

  class OverlapEditor {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.T = opts.T | 0;
      this.K = opts.K | 0;
      this.values = opts.values ? new Int8Array(opts.values) : new Int8Array(this.T * this.K);
      this.reference = opts.reference ? new Int8Array(opts.reference) : null;
      this.readonly = !!opts.readonly;
      this.showDiff = false;
      this.onChange = opts.onChange || (() => {});
      this.onHover = opts.onHover || (() => {});

      // 뷰 상태 (fit-to-canvas 기본)
      this.view = { scale: 1, offsetX: 0, offsetY: 0 };
      this.cellPxW = 1;   // 한 셀이 차지하는 캔버스 픽셀 너비
      this.cellPxH = 1;
      this.originX = 0;   // 셀 (0, 0) 이 캔버스에서 시작되는 좌표
      this.originY = 0;

      // 드래그 상태
      this._drag = null;   // { mode: 'paint'|'pan', paintValue, lastCell }
      this._hover = null;  // { t, c }

      // 자동 렌더링 트리거
      this._rafPending = false;

      this._bindEvents();
      this._resizeToContainer();
      this.render();
    }

    // ── 내부 인덱싱 ───────────────────────────────────────────────────
    idx(t, c) { return t * this.K + c; }

    // ── 공개 API ──────────────────────────────────────────────────────
    setMatrix(values) {
      if (values.length !== this.T * this.K) {
        throw new Error(`setMatrix 크기 불일치: ${values.length} != ${this.T * this.K}`);
      }
      this.values = new Int8Array(values);
      this.render();
      this._emitChange();
    }
    getMatrix() { return this.values; }

    setReference(ref) {
      if (ref && ref.length !== this.T * this.K) {
        throw new Error(`setReference 크기 불일치`);
      }
      this.reference = ref ? new Int8Array(ref) : null;
    }

    setDiffMode(b) {
      this.showDiff = !!b;
      this.render();
    }

    resetToReference() {
      if (!this.reference) return;
      this.values = new Int8Array(this.reference);
      this.render();
      this._emitChange();
    }

    randomFill(density = 0.3, seed) {
      const rng = seed != null ? mulberry32(seed) : Math.random;
      for (let i = 0; i < this.values.length; i++) {
        this.values[i] = (rng() < density) ? 1 : 0;
      }
      this.render();
      this._emitChange();
    }

    clearAll() {
      this.values.fill(0);
      this.render();
      this._emitChange();
    }

    density() {
      let s = 0;
      for (let i = 0; i < this.values.length; i++) s += this.values[i];
      return s / this.values.length;
    }

    diffCount() {
      if (!this.reference) return 0;
      let d = 0;
      for (let i = 0; i < this.values.length; i++) {
        if (this.values[i] !== this.reference[i]) d++;
      }
      return d;
    }

    resetView() {
      this.view = { scale: 1, offsetX: 0, offsetY: 0 };
      this._resizeToContainer();
      this.render();
    }

    // ── 이벤트 바인딩 ─────────────────────────────────────────────────
    _bindEvents() {
      const c = this.canvas;

      // 오른쪽 클릭 메뉴 억제
      c.addEventListener('contextmenu', (e) => e.preventDefault());

      c.addEventListener('mousedown', (e) => this._onMouseDown(e));
      c.addEventListener('mousemove', (e) => this._onMouseMove(e));
      c.addEventListener('mouseleave', () => {
        this._hover = null;
        this.onHover(null);
        this.render();
      });
      c.addEventListener('mouseup', (e) => this._onMouseUp(e));
      c.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
      c.addEventListener('dblclick', () => this.resetView());

      window.addEventListener('mouseup', () => { this._drag = null; });
      window.addEventListener('resize', () => {
        this._resizeToContainer();
        this.render();
      });
    }

    _onMouseDown(e) {
      if (this.readonly) return;
      const pos = this._mouseToCell(e);
      if (!pos) return;
      if (e.shiftKey || e.button === 1) {
        // 팬 모드
        this._drag = {
          mode: 'pan',
          startX: e.clientX,
          startY: e.clientY,
          baseOffsetX: this.view.offsetX,
          baseOffsetY: this.view.offsetY,
        };
      } else if (e.button === 2) {
        // 우클릭: 강제 0
        this._paintCell(pos.t, pos.c, 0);
        this._drag = { mode: 'paint', paintValue: 0, lastCell: pos };
      } else {
        // 좌클릭: 현재 값의 반대로 통일
        const cur = this.values[this.idx(pos.t, pos.c)];
        const newVal = cur ? 0 : 1;
        this._paintCell(pos.t, pos.c, newVal);
        this._drag = { mode: 'paint', paintValue: newVal, lastCell: pos };
      }
    }

    _onMouseMove(e) {
      const pos = this._mouseToCell(e);
      this._hover = pos;
      this.onHover(pos);
      if (this._drag) {
        if (this._drag.mode === 'pan') {
          const dx = e.clientX - this._drag.startX;
          const dy = e.clientY - this._drag.startY;
          this.view.offsetX = this._drag.baseOffsetX + dx;
          this.view.offsetY = this._drag.baseOffsetY + dy;
        } else if (this._drag.mode === 'paint' && pos) {
          this._paintCell(pos.t, pos.c, this._drag.paintValue);
        }
      }
      this._scheduleRender();
    }

    _onMouseUp() {
      this._drag = null;
    }

    _onWheel(e) {
      e.preventDefault();
      const zoomFactor = Math.exp(-e.deltaY * 0.0015);
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      // 줌 전 후로 마우스 포인터 고정
      const worldX = (mx - this.originX - this.view.offsetX) / this.view.scale;
      const worldY = (my - this.originY - this.view.offsetY) / this.view.scale;
      const newScale = Math.max(0.3, Math.min(12, this.view.scale * zoomFactor));
      this.view.scale = newScale;
      this.view.offsetX = mx - this.originX - worldX * newScale;
      this.view.offsetY = my - this.originY - worldY * newScale;
      this.render();
    }

    // ── 좌표 변환 ─────────────────────────────────────────────────────
    _resizeToContainer() {
      const c = this.canvas;
      const parent = c.parentElement;
      const pw = Math.max(300, parent.clientWidth - 24);
      const ph = Math.max(240, parent.clientHeight - 24 || 360);
      // 캔버스 해상도 = CSS 크기 × DPR
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      c.style.width = pw + 'px';
      c.style.height = ph + 'px';
      c.style.maxHeight = '';
      c.style.imageRendering = 'auto';
      c.width = Math.floor(pw * dpr);
      c.height = Math.floor(ph * dpr);
      // ctx scale 맞춤: 이후 모든 좌표는 CSS 픽셀 기준
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.cssW = pw;
      this.cssH = ph;

      // fit-to-canvas: 셀 크기 결정
      // 가로로 T, 세로로 K 를 채운다. 여백 10px.
      const inner_w = pw - 20;
      const inner_h = ph - 20;
      const scaleX = inner_w / this.T;
      const scaleY = inner_h / this.K;
      // 셀은 직사각형도 허용 (T 대비 K 비율이 커서)
      this.cellPxW = scaleX;
      this.cellPxH = scaleY;
      // 전체 행렬을 중앙 정렬
      this.originX = 10;
      this.originY = 10;
    }

    _mouseToCell(e) {
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const t = Math.floor((mx - this.originX - this.view.offsetX) / (this.cellPxW * this.view.scale));
      const c = Math.floor((my - this.originY - this.view.offsetY) / (this.cellPxH * this.view.scale));
      if (t < 0 || t >= this.T || c < 0 || c >= this.K) return null;
      return { t, c };
    }

    _paintCell(t, c, v) {
      const i = this.idx(t, c);
      if (this.values[i] !== v) {
        this.values[i] = v;
        this._emitChange();
      }
    }

    // ── 렌더링 ────────────────────────────────────────────────────────
    _scheduleRender() {
      if (this._rafPending) return;
      this._rafPending = true;
      requestAnimationFrame(() => {
        this._rafPending = false;
        this.render();
      });
    }

    render() {
      const { ctx, cssW, cssH } = this;
      if (!ctx) return;
      ctx.save();
      ctx.fillStyle = '#0A0A1C';
      ctx.fillRect(0, 0, cssW, cssH);

      // 화면상의 셀 크기 (scale 포함)
      const cellW = this.cellPxW * this.view.scale;
      const cellH = this.cellPxH * this.view.scale;
      const ox = this.originX + this.view.offsetX;
      const oy = this.originY + this.view.offsetY;

      // 가시 영역 판정 범위
      const tStart = Math.max(0, Math.floor((0 - ox) / cellW));
      const tEnd   = Math.min(this.T, Math.ceil((cssW - ox) / cellW));
      const cStart = Math.max(0, Math.floor((0 - oy) / cellH));
      const cEnd   = Math.min(this.K, Math.ceil((cssH - oy) / cellH));

      // ImageData 속도가 낫지만 diff 색상 적용 편의상 fillRect 사용
      for (let t = tStart; t < tEnd; t++) {
        for (let c = cStart; c < cEnd; c++) {
          const v = this.values[this.idx(t, c)];
          const refV = this.reference ? this.reference[this.idx(t, c)] : v;
          let rgb;
          if (this.showDiff && this.reference) {
            if (v === refV) {
              rgb = v ? CELL_ON_RGB : CELL_OFF_RGB;
            } else if (v && !refV) {
              rgb = CELL_ADD_RGB;
            } else {
              rgb = CELL_DEL_RGB;
            }
          } else {
            rgb = v ? CELL_ON_RGB : CELL_OFF_RGB;
          }
          ctx.fillStyle = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
          ctx.fillRect(ox + t * cellW, oy + c * cellH, Math.ceil(cellW), Math.ceil(cellH));
        }
      }

      // 셀 격자선 (scale이 충분히 큰 경우만)
      if (cellW >= 6 || cellH >= 6) {
        ctx.strokeStyle = GRID_STROKE;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let t = tStart; t <= tEnd; t++) {
          const x = ox + t * cellW + 0.5;
          ctx.moveTo(x, oy + cStart * cellH);
          ctx.lineTo(x, oy + cEnd * cellH);
        }
        for (let c = cStart; c <= cEnd; c++) {
          const y = oy + c * cellH + 0.5;
          ctx.moveTo(ox + tStart * cellW, y);
          ctx.lineTo(ox + tEnd * cellW, y);
        }
        ctx.stroke();
      }

      // hover
      if (this._hover) {
        const { t, c } = this._hover;
        ctx.strokeStyle = HOVER_STROKE;
        ctx.lineWidth = 2;
        ctx.strokeRect(ox + t * cellW + 0.5, oy + c * cellH + 0.5,
                       Math.max(2, cellW - 1), Math.max(2, cellH - 1));
      }

      ctx.restore();
    }

    _emitChange() {
      try { this.onChange(this); } catch (e) { console.error('onChange cb error:', e); }
    }
  }

  // 간단한 결정적 PRNG (seed 기반)
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  global.OverlapEditor = OverlapEditor;
})(window);
