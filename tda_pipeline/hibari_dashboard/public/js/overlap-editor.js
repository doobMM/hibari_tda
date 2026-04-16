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
 *   ed.randomFill(density)     — 각 셀 독립 Bernoulli (공간 구조 無)
 *   ed.clearAll()
 *   ed.density()               — 현재 ON 비율
 *   ed.diffCount()             — 참조와의 Hamming distance
 *
 *   ── density 보존 변형 (기본은 참조 기반) ──
 *   ed.shuffleDensity(seed, fromRef)        — ON 셀 수 유지, 위치 완전 랜덤
 *   ed.permuteTime(seed, fromRef)           — T 축 순서 permutation
 *   ed.permuteCycles(seed, fromRef)         — K 축 순서 permutation
 *   ed.blockShuffle(blockSize, seed, fromRef) — 시간 블록 단위 셔플
 *   ed.circularShift(dt, dc, fromRef)       — 원형 이동
 *   ed.floodPattern(seed, density, spread)  — 물 번짐 flood fill
 *   ed.jitterFromReference(strength, seed)  — 참조 각 ON 셀을 local jitter
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
      const rng = this._rng(seed);
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

    // ── density 보존 변형 ────────────────────────────────────────────
    // source: fromRef=true 이면 this.reference 기반, false 이면 현재 편집본 기반.

    /**
     * density 유지 재분배 — ON 셀 개수(N_on)는 그대로, 위치만 완전 랜덤.
     * 공간/시간 구조 완전 파괴, 통계(density)만 유지.
     */
    shuffleDensity(seed, fromRef = false) {
      const rng = this._rng(seed);
      const src = this._srcArray(fromRef);
      const N = src.length;
      let nOn = 0;
      for (let i = 0; i < N; i++) if (src[i]) nOn++;
      // 인덱스 배열을 shuffle 해서 앞 nOn 개만 ON 으로 선택
      const idx = new Int32Array(N);
      for (let i = 0; i < N; i++) idx[i] = i;
      for (let i = 0; i < nOn; i++) {
        const j = i + Math.floor(rng() * (N - i));
        const tmp = idx[i]; idx[i] = idx[j]; idx[j] = tmp;
      }
      const out = new Int8Array(N);
      for (let i = 0; i < nOn; i++) out[idx[i]] = 1;
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * T 축 permutation — 각 시점(row) 순서를 섞음.
     * cycle별 column 분포 완전 유지, 시간 구조만 파괴.
     */
    permuteTime(seed, fromRef = false) {
      const rng = this._rng(seed);
      const src = this._srcArray(fromRef);
      const T = this.T, K = this.K;
      const perm = new Int32Array(T);
      for (let t = 0; t < T; t++) perm[t] = t;
      for (let i = T - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        const tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
      }
      const out = new Int8Array(T * K);
      for (let t = 0; t < T; t++) {
        const s = perm[t];
        for (let c = 0; c < K; c++) out[t * K + c] = src[s * K + c];
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * K 축 permutation — cycle 번호 순서를 섞음.
     * 시점별 활성 cycle 개수 완전 유지, 어떤 cycle인지만 재배치.
     */
    permuteCycles(seed, fromRef = false) {
      const rng = this._rng(seed);
      const src = this._srcArray(fromRef);
      const T = this.T, K = this.K;
      const perm = new Int32Array(K);
      for (let c = 0; c < K; c++) perm[c] = c;
      for (let i = K - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        const tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
      }
      const out = new Int8Array(T * K);
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) out[t * K + c] = src[t * K + perm[c]];
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * 시간 블록 단위 셔플 — blockSize 스텝을 하나의 블록으로 묶어 permutation.
     * 블록 내부 구조는 보존, 블록 간 순서만 섞음.
     */
    blockShuffle(blockSize = 8, seed, fromRef = false) {
      const rng = this._rng(seed);
      const src = this._srcArray(fromRef);
      const T = this.T, K = this.K;
      const bs = Math.max(1, blockSize | 0);
      const nb = Math.floor(T / bs);
      const perm = new Int32Array(nb);
      for (let b = 0; b < nb; b++) perm[b] = b;
      for (let i = nb - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        const tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
      }
      const out = new Int8Array(T * K);
      for (let b = 0; b < nb; b++) {
        const s = perm[b];
        for (let dt = 0; dt < bs; dt++) {
          for (let c = 0; c < K; c++) {
            out[(b * bs + dt) * K + c] = src[(s * bs + dt) * K + c];
          }
        }
      }
      // 꼬리(T 가 bs 로 나누어 떨어지지 않을 때)는 그대로 복사
      for (let t = nb * bs; t < T; t++) {
        for (let c = 0; c < K; c++) out[t * K + c] = src[t * K + c];
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * 원형 이동 — 시간 축으로 dt, cycle 축으로 dc 만큼 circular shift.
     * density/row/col 분포 완전 동일, 시작 위상만 다름.
     */
    circularShift(dt = 0, dc = 0, fromRef = false) {
      const src = this._srcArray(fromRef);
      const T = this.T, K = this.K;
      dt = (((dt | 0) % T) + T) % T;
      dc = (((dc | 0) % K) + K) % K;
      const out = new Int8Array(T * K);
      for (let t = 0; t < T; t++) {
        const st = (t - dt + T) % T;
        for (let c = 0; c < K; c++) {
          const sc = (c - dc + K) % K;
          out[t * K + c] = src[st * K + sc];
        }
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * 물 번짐 flood fill — 2~5 개 씨앗에서 spread 확률로 4방향 전파.
     * 참조와 무관한 공간 연속성 패턴. target density 근사.
     */
    floodPattern(seed, density = 0.3, spread = 0.6) {
      const rng = this._rng(seed);
      const T = this.T, K = this.K;
      const N = T * K;
      const target = Math.max(1, Math.round(N * density));
      const out = new Int8Array(N);
      const frontier = [];
      const numSources = 2 + Math.floor(rng() * 4);  // 2..5
      for (let s = 0; s < numSources; s++) {
        const t = Math.floor(rng() * T);
        const c = Math.floor(rng() * K);
        const i = t * K + c;
        if (!out[i]) { out[i] = 1; frontier.push(i); }
      }
      let count = frontier.length;
      // 안전장치: 최악의 경우 무한루프 방지
      let safety = N * 4;
      while (count < target && frontier.length > 0 && safety-- > 0) {
        const pickIdx = Math.floor(rng() * frontier.length);
        const si = frontier[pickIdx];
        const st = (si / K) | 0;
        const sc = si - st * K;
        const neigh = [
          [st - 1, sc], [st + 1, sc],
          [st, sc - 1], [st, sc + 1],
        ];
        let grew = false;
        for (let n = 0; n < 4; n++) {
          const nt = neigh[n][0], nc = neigh[n][1];
          if (nt < 0 || nt >= T || nc < 0 || nc >= K) continue;
          const ni = nt * K + nc;
          if (out[ni]) continue;
          if (rng() < spread) {
            out[ni] = 1;
            frontier.push(ni);
            count++;
            grew = true;
            if (count >= target) break;
          }
        }
        if (!grew) {
          // 이 씨앗은 더 이상 확장 불가 — frontier 에서 제거 (O(1) swap-pop)
          frontier[pickIdx] = frontier[frontier.length - 1];
          frontier.pop();
        }
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    /**
     * 참조 왜곡 — 참조의 각 ON 셀을 local random offset 으로 이동.
     * strength ∈ [0,1] → 시간축 최대 24 step, cycle 축 최대 4.
     * 지각적으로 참조와 가장 비슷한 "흔들린 그림".
     */
    jitterFromReference(strength = 0.2, seed) {
      if (!this.reference) return;
      const rng = this._rng(seed);
      const T = this.T, K = this.K;
      const out = new Int8Array(T * K);
      const maxT = Math.max(1, Math.round(strength * 24));
      const maxC = Math.max(1, Math.round(strength * 4));
      for (let t = 0; t < T; t++) {
        for (let c = 0; c < K; c++) {
          if (!this.reference[t * K + c]) continue;
          const ot = Math.floor(rng() * (2 * maxT + 1)) - maxT;
          const oc = Math.floor(rng() * (2 * maxC + 1)) - maxC;
          let nt = t + ot, nc = c + oc;
          // 시간은 clamp (wrap 하면 음악 끝과 처음이 섞여 부자연스러움)
          if (nt < 0) nt = 0; else if (nt >= T) nt = T - 1;
          if (nc < 0) nc = 0; else if (nc >= K) nc = K - 1;
          out[nt * K + nc] = 1;  // 겹치면 자연스럽게 하나로 병합 → density 약간 감소
        }
      }
      this.values = out;
      this.render();
      this._emitChange();
    }

    // ── 내부 helper ──────────────────────────────────────────────────
    _rng(seed) {
      return seed != null ? mulberry32(seed) : Math.random;
    }
    _srcArray(fromRef) {
      if (fromRef) {
        if (!this.reference) throw new Error('참조(reference) 가 설정되지 않음');
        return this.reference;
      }
      return this.values;
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

      // Pointer 이벤트로 통일 (마우스/터치/펜 모두 처리). 모바일에서 단일 터치
      // 드래그는 paint, 두 손가락은 pinch-zoom 으로 처리.
      this._activePointers = new Map();   // pointerId → {x, y}
      this._pinchStart = null;            // { dist, scale, cx, cy, offX, offY }

      c.addEventListener('pointerdown', (e) => this._onPointerDown(e));
      c.addEventListener('pointermove', (e) => this._onPointerMove(e));
      c.addEventListener('pointerup', (e) => this._onPointerUp(e));
      c.addEventListener('pointercancel', (e) => this._onPointerUp(e));
      c.addEventListener('pointerleave', (e) => {
        if (this._activePointers.size === 0) {
          this._hover = null;
          this.onHover(null);
          this.render();
        }
      });
      c.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
      c.addEventListener('dblclick', () => this.resetView());

      window.addEventListener('pointerup', () => {
        this._drag = null;
        this._activePointers.clear();
        this._pinchStart = null;
      });
      window.addEventListener('resize', () => {
        this._resizeToContainer();
        this.render();
      });
    }

    _onPointerDown(e) {
      if (this.readonly) return;
      // 터치 캡처: pointermove 가 canvas 밖으로 나가도 추적되게
      try { this.canvas.setPointerCapture(e.pointerId); } catch (_) {}
      this._activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

      // 두 손가락 이상 → pinch/pan 모드로 전환, 이전 drag 취소
      if (this._activePointers.size >= 2) {
        const pts = Array.from(this._activePointers.values());
        const dx = pts[1].x - pts[0].x;
        const dy = pts[1].y - pts[0].y;
        this._pinchStart = {
          dist: Math.hypot(dx, dy) || 1,
          scale: this.view.scale,
          cx: (pts[0].x + pts[1].x) / 2,
          cy: (pts[0].y + pts[1].y) / 2,
          offX: this.view.offsetX,
          offY: this.view.offsetY,
        };
        this._drag = { mode: 'multi' };
        return;
      }

      const pos = this._mouseToCell(e);
      if (!pos) return;
      if (e.shiftKey || e.button === 1 || e.pointerType === 'touch' && e.altKey) {
        // Shift+드래그(데스크톱) 팬 모드
        this._drag = {
          mode: 'pan',
          startX: e.clientX,
          startY: e.clientY,
          baseOffsetX: this.view.offsetX,
          baseOffsetY: this.view.offsetY,
        };
      } else if (e.button === 2) {
        this._paintCell(pos.t, pos.c, 0);
        this._drag = { mode: 'paint', paintValue: 0, lastCell: pos };
      } else {
        const cur = this.values[this.idx(pos.t, pos.c)];
        const newVal = cur ? 0 : 1;
        this._paintCell(pos.t, pos.c, newVal);
        this._drag = { mode: 'paint', paintValue: newVal, lastCell: pos };
      }
    }

    _onPointerMove(e) {
      if (this._activePointers.has(e.pointerId)) {
        this._activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      }

      // 멀티터치 pinch-zoom + 2-finger pan
      if (this._activePointers.size >= 2 && this._pinchStart) {
        const pts = Array.from(this._activePointers.values());
        const dx = pts[1].x - pts[0].x;
        const dy = pts[1].y - pts[0].y;
        const dist = Math.hypot(dx, dy) || 1;
        const newCx = (pts[0].x + pts[1].x) / 2;
        const newCy = (pts[0].y + pts[1].y) / 2;
        const rect = this.canvas.getBoundingClientRect();
        const pinch = this._pinchStart;
        const zoomFactor = dist / pinch.dist;
        const newScale = Math.max(0.3, Math.min(12, pinch.scale * zoomFactor));

        // 시작 시점의 두 손가락 중점이 고정되게, 그리고 중점 평행이동을 pan 으로 반영
        const mx = pinch.cx - rect.left;
        const my = pinch.cy - rect.top;
        const worldX = (mx - this.originX - pinch.offX) / pinch.scale;
        const worldY = (my - this.originY - pinch.offY) / pinch.scale;
        const panDx = newCx - pinch.cx;
        const panDy = newCy - pinch.cy;
        this.view.scale = newScale;
        this.view.offsetX = mx - this.originX - worldX * newScale + panDx;
        this.view.offsetY = my - this.originY - worldY * newScale + panDy;
        this._scheduleRender();
        return;
      }

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

    _onPointerUp(e) {
      this._activePointers.delete(e.pointerId);
      try { this.canvas.releasePointerCapture(e.pointerId); } catch (_) {}
      // 손가락 1개 이하가 되면 pinch 종료
      if (this._activePointers.size < 2) {
        this._pinchStart = null;
        if (this._drag && this._drag.mode === 'multi') this._drag = null;
      }
      if (this._activePointers.size === 0) {
        this._drag = null;
      }
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
