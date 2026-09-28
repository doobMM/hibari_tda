/* ============================================================================
 * lenia-core.js — 되먹임 회로 + Lenia 성장 규칙 + 제자리에 묶인 입자
 *
 * 페이지(lenia/index.html)와 검증 하네스(tools/verify_lenia.mjs)가 **같은 이 파일**을 쓴다.
 * 그래야 하네스의 측정이 배포되는 코드를 잰 것이 된다 (T10 의 교훈).
 *
 * 명세: docs/lenia_spec.md §4-1 (규칙) · §4-3 (입자)
 *
 * 신호 흐름 — echo.html 의 되먹임 회로를 그대로 두고 **중첩행렬을 만드는 규칙만** 바꿨다
 *   울리는 음 S   = 사용자 점(자기 주기로 SUS 스텝) + 생성음의 잔향(세대마다 짧아짐)
 *   퍼텐셜 U_c    = Σ_{n∈c} rar(n)·S_n / Σ_{n∈c} rar(n)        ← overlap.py 연속 활성도
 *   성장 G_c      = +1  if τ_c ≤ U_c ≤ uMax   else −1          ← Lenia 사각형 성장
 *   상태 A_c     ← clip(A_c + G_c / T, 0, 1)                    ← Lenia 갱신식
 *   중첩행렬 OM_c = [A_c ≥ ½]  →  Algorithm 1 (generation-algo1.js, T10 검증본)
 *   난 음         → 다시 S                                       ← 되먹임
 *
 * 정확한 특수 경우: T=1, uMax=1 이면 OM = [U ≥ τ_c].
 *   τ_c = 헤드라인 tau_profile 이면 헤드라인 OM, τ = 0.35 평탄이면 echo.html 과 같다.
 *   그래서 echo.html 은 이 엔진의 한 설정으로 재현된다 (하네스가 확인한다).
 * ========================================================================= */
(function (global) {
  'use strict';

  /** Lenia 사각형 성장 한 스텝. A 를 제자리에서 갱신하고 om·g 를 채운다. 켜진 고리 수를 돌려준다.
   *  ⚠ 연산 순서를 파이썬(run_lenia_rule.py)과 똑같이 둔다: min(1, max(0, A + g/T)) */
  function leniaStep(A, U, tau, T, uMax, om, g) {
    var f = 0;
    for (var c = 0; c < A.length; c++) {
      var gg = (U[c] >= tau[c] && U[c] <= uMax) ? 1 : -1;
      A[c] = Math.min(1, Math.max(0, A[c] + gg / T));
      g[c] = gg;
      om[c] = A[c] >= 0.5 ? 1 : 0;
      f += om[c];
    }
    return f;
  }

  /**
   * 되먹임 엔진.
   * @param {object} o
   *   data   lenia/hibari.json (cycles · rarity · labels)
   *   G      window.GenerationAlgo1
   *   tau    길이 K 배열 (헤드라인 τ_c, 또는 대조군용 평탄 0.35)
   *   T, uMax  Lenia 상수
   *   rng    () => [0,1)  (시험용 결정적 난수. 기본 Math.random)
   *   이하 echo.html 과 같은 기본값: SUS 12 · RING 10 · DECAY 0.55 · VOICES 2 · HANDS [32,33] · GEN_W 8
   */
  function Engine(o) {
    var d = o.data;
    this.G = o.G;
    this.K = d.cycles.length;
    this.CSET = d.cycles.map(function (c) { return c.filter(function (v, i) { return c.indexOf(v) === i; }); });
    /* 희귀도는 고리에서 **정확히** 다시 계산한다 — rar(n) = 1 / (n 을 품은 고리 수).
     * ⚠ hibari.json 의 `rarity` 는 소수 6자리로 반올림돼 있다. 그걸 쓰면 U 가 τ 에 아주 가까운
     *   스텝에서 켜짐/꺼짐이 뒤집히고 거기서부터 난수 소비가 갈라진다 — 하네스가 점 8개에서 잡았다
     *   (재현 4.5→5→4.8→5.8 vs 세션 기록 4.5→4.9→5.3→5.9, 점 1·2·4 는 일치). */
    this.RAR = {};
    this.CSET.forEach(function (c) { c.forEach(function (v) { this.RAR[v] = (this.RAR[v] || 0) + 1; }, this); }, this);
    for (var k in this.RAR) this.RAR[k] = 1 / this.RAR[k];
    this.WSUM = this.CSET.map(function (c) {
      var s = 0; for (var i = 0; i < c.length; i++) s += (this.RAR[c[i]] || 1); return s;
    }, this);
    this.PD2L = {};                                   // (pitch,dur) → label_idx — 되먹임의 역방향
    for (var i = 0; i < d.labels.length; i++) {
      var e = d.labels[i]; this.PD2L[e.pitch * 100 + e.dur] = e.label_idx;
    }
    this.PITCH = d.labels.map(function (e) { return e.pitch; });
    this.tau = o.tau; this.T = o.T; this.uMax = o.uMax;
    this.rng = o.rng || Math.random;
    this.SUS = o.SUS || 12; this.RING = o.RING || 10; this.DECAY = o.DECAY || 0.55;
    this.VOICES = o.VOICES || 2; this.HANDS = o.HANDS || [32, 33]; this.GEN_W = o.GEN_W || 8;
    this.LIFE = o.LIFE || 24; this.ECHO_LEN = o.ECHO_LEN || 8.8;
    this.mgr = new this.G.CycleSetManager({
      cycles: d.cycles.map(function (c, i) { return { cycle_idx: i, note_labels_0idx: c }; }), K: this.K });
    this.pool = new this.G.NodePool({ labels: d.labels, numModules: 65, temperature: 1.0, rng: this.rng });
    this.clear(0);
  }

  Engine.prototype.clear = function (t) {
    this.drops = []; this.ring = []; this.simT = t || 0;
    this.A = new Float64Array(this.K);
    this.snap = {};                                    // 스텝 → 화면용 상태 (A · G 부호 · 울림)
  };

  /** 점 하나. 놓는 순서대로 두 손(32·33)에 번갈아 배정한다 — hibari 의 modular operation. */
  Engine.prototype.addDrop = function (li, at) {
    var d = { li: li, pitch: this.PITCH[li], per: this.HANDS[this.drops.length % 2], at: at, life: this.LIFE };
    this.drops.push(d);
    if (this.drops.length > 40) this.drops.shift();
    return d;
  };

  /** 스텝 t 에 울리는 label_idx 집합. withRing 이면 생성음 잔향(되먹임)까지. */
  Engine.prototype.sounding = function (t, withRing) {
    var s = {};
    for (var i = 0; i < this.drops.length; i++) {
      var d = this.drops[i];
      if ((t - d.at) / d.per > d.life) continue;
      var ph = (t - d.at) % d.per; if (ph < 0) ph += d.per;
      if (ph < this.SUS) s[d.li] = 1;
    }
    if (withRing) for (var j = 0; j < this.ring.length; j++) if (this.ring[j].to > t) s[this.ring[j].li] = 1;
    return s;
  };

  Engine.prototype.potential = function (s, U) {
    for (var c = 0; c < this.K; c++) {
      var acc = 0, cs = this.CSET[c];
      for (var j = 0; j < cs.length; j++) if (s[cs[j]]) acc += this.RAR[cs[j]];
      U[c] = acc / this.WSUM[c];
    }
    return U;
  };

  /**
   * simT 부터 `to` 까지 **한 스텝씩** 나아간다. 한 스텝의 결과가 다음 스텝의 입력이 되므로
   * 통째로 계산할 수 없다. 난 음을 [시작스텝, 음높이, 끝스텝, 세기, 세대] 로 돌려준다.
   * ⚠ algorithm1 을 T=1 로 부르면 `end > length` 가림에 걸려 음 길이가 전부 1 로 잘린다 → 창 GEN_W.
   */
  Engine.prototype.advance = function (to, onStep) {
    var out = [], K = this.K, W = this.GEN_W;
    var U = new Float64Array(K), om = new Int8Array(K), g = new Int8Array(K);
    for (; this.simT < to; this.simT++) {
      var t = this.simT, keep = [];
      for (var i = 0; i < this.ring.length; i++) if (this.ring[i].to > t) keep.push(this.ring[i]);
      this.ring = keep;

      var s = this.sounding(t, true);
      this.potential(s, U);
      var f = leniaStep(this.A, U, this.tau, this.T, this.uMax, om, g);
      this.snap[t] = { A: Float32Array.from(this.A), g: Int8Array.from(g), s: s, f: f };
      if (onStep) onStep(t, f, U, om);
      if (!f) continue;

      var v = new Int8Array(W * K);
      for (var c = 0; c < K; c++) v[c] = om[c];
      for (var w = 1; w < W; w++) v.copyWithin(w * K, 0, K);
      var il = new Int32Array(W);
      il[0] = Math.min(this.VOICES, this.G.HIBARI_MODULE_PATTERN[((t % 32) + 32) % 32]);

      var gen = 1;                                    // 지금 울리는 잔향의 다음 세대
      for (var r = 0; r < this.ring.length; r++) if (this.ring[r].g + 1 > gen) gen = this.ring[r].g + 1;
      var life = this.RING * Math.pow(this.DECAY, gen - 1);           // ← 세대 감쇠 (echo.html 과 같다)

      var res = this.G.algorithm1({ nodePool: this.pool, cycleManager: this.mgr, instLen: il,
                                    overlap: { T: W, K: K, values: v }, rng: this.rng });
      for (var n = 0; n < res.notes.length; n++) {
        var x = res.notes[n], dur = x[2] - x[0];
        var li = this.PD2L[x[1] * 100 + dur];                           // (pitch,dur) 로 되찾는다 — 손실 없음
        out.push([t + x[0], x[1], t + x[2], 84, gen, li]);
        if (li != null && life >= 1) this.ring.push({ li: li, to: t + dur + Math.round(life), g: gen });
      }
    }
    return out;
  };

  /** 사용자 점이 자기 주기로 되돌아오는 소리 [시작, 음높이, 끝, 세기] — 회로의 씨앗 */
  Engine.prototype.echoes = function (a, b) {
    var out = [];
    for (var i = 0; i < this.drops.length; i++) {
      var d = this.drops[i];
      for (var k = Math.max(1, Math.ceil((a - d.at) / d.per)); d.at + k * d.per < b; k++) {
        if (k > d.life) break;
        var s0 = d.at + k * d.per;
        out.push([s0, d.pitch, s0 + this.ECHO_LEN, Math.round(96 * Math.pow(1 - k / d.life, 0.6))]);
      }
    }
    return out;
  };

  Engine.prototype.prune = function (before) {
    for (var k in this.snap) if (+k < before) delete this.snap[k];
  };

  /**
   * 입자 한 스텝 — 제자리에 묶인 입자 (명세 §4-3).
   * Particle Lenia 에서 영감을 받았을 뿐 그 에너지 정식화(E = R − G)는 아니다.
   *   F_i = −kHome·(x_i − x_i⁰)                          집으로 (지도를 지킨다)
   *       + kBind·Σ_c A_c·[i∈c]·(x̄_c − x_i)              켜진 고리의 무게중심 쪽으로 (별자리가 조여진다)
   *       − kRep·Σ_{|x_j−x_i|<r0} (x_j − x_i)/|x_j − x_i|³  겹침 방지
   * 좌표는 0~1 정규화 공간. 소리에 영향이 없는 표시 매개변수다.
   */
  function physicsStep(P, A, cycles, prm, dt) {
    var n = P.x.length, i, c, j, fx = new Float64Array(n), fy = new Float64Array(n);
    for (i = 0; i < n; i++) {
      fx[i] = -prm.kHome * (P.x[i] - P.hx[i]);
      fy[i] = -prm.kHome * (P.y[i] - P.hy[i]);
    }
    for (c = 0; c < cycles.length; c++) {
      if (A[c] <= 0) continue;
      var cy = cycles[c], mx = 0, my = 0;
      for (j = 0; j < cy.length; j++) { mx += P.x[cy[j]]; my += P.y[cy[j]]; }
      mx /= cy.length; my /= cy.length;
      for (j = 0; j < cy.length; j++) {
        fx[cy[j]] += prm.kBind * A[c] * (mx - P.x[cy[j]]);
        fy[cy[j]] += prm.kBind * A[c] * (my - P.y[cy[j]]);
      }
    }
    for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) {
      var dx = P.x[j] - P.x[i], dy = P.y[j] - P.y[i], r2 = dx * dx + dy * dy;
      if (r2 >= prm.r0 * prm.r0 || r2 < 1e-12) continue;
      var inv = prm.kRep / (r2 * Math.sqrt(r2));
      fx[i] -= dx * inv; fy[i] -= dy * inv; fx[j] += dx * inv; fy[j] += dy * inv;
    }
    for (i = 0; i < n; i++) {
      P.vx[i] = prm.gamma * P.vx[i] + fx[i] * dt; P.vy[i] = prm.gamma * P.vy[i] + fy[i] * dt;
      P.x[i] += P.vx[i] * dt; P.y[i] += P.vy[i] * dt;
    }
  }
  /* 표시 매개변수 (소리와 무관). kBind/(kHome+kBind) 가 켜진 고리 쪽 평형 변위의 몫이다.
   * 첫 값 9.0(몫 0.60) 은 지도를 제대로 펼친 뒤 최대 변위 0.199 로 한도 0.15 를 넘었다 →
   * 몫을 0.60×0.12/0.199 ≈ 0.37 로 낮췄더니(kBind 3.5) 0.144 — 여러 고리가 한 입자를 함께 끌어 예측보다 컸다.
   * 최악(연결 음 21개 전부에 점)도 0.145 로 거의 같아 **변위는 점 개수가 아니라 지도 모양이 정한다**.
   * 여유가 0.005 뿐이라 kBind 3.0(최악 0.136) 으로 둔다. 하네스 ④ 가 한도를 잰다. */
  var PHYS = { kHome: 6.0, kBind: 3.0, kRep: 2e-5, r0: 0.05, gamma: 0.86 };

  /**
   * 규칙 설정 — 페이지와 하네스가 **같은 정의**를 쓴다 (둘이 어긋나지 않게).
   *   echo          τ=0.35 평탄 · T=1   · 과밀 없음   = echo.html
   *   tauc          τ_c        · T=1   · 과밀 없음   τ 만 헤드라인으로
   *   lenia_noover  τ_c        · T=25  · 과밀 없음   + 관성
   *   lenia         τ_c        · T=25  · uMax 0.688  + 과밀      ← 명세가 사전등록한 설정
   *   tauc_over     τ_c        · T=1   · uMax 0.688  과밀만
   *   echo_over     τ=0.35 평탄 · T=1   · uMax 0.688  echo.html + 과밀 창
   */
  function arm(name, d) {
    var K = d.cycles.length, flat = [], i;
    for (i = 0; i < K; i++) flat.push(0.35);
    var u = d.rule.u_max_generation, T = d.rule.T;
    return {
      echo:         { tau: flat,  T: 1, uMax: 1 },
      tauc:         { tau: d.tau, T: 1, uMax: 1 },
      lenia_noover: { tau: d.tau, T: T, uMax: 1 },
      lenia:        { tau: d.tau, T: T, uMax: u },
      tauc_over:    { tau: d.tau, T: 1, uMax: u },
      echo_over:    { tau: flat,  T: 1, uMax: u },
    }[name];
  }
  /* 배포 설정 — tools/verify_lenia.mjs 가 정한다 (그 파일 헤더의 1~3회차 기록 참조).
   *   명세가 사전등록한 `lenia`(τ_c · T=25) 는 점 2·4개로 고리가 켜지지 않는다 — 20시드 중 0.
   *   `echo_over` = echo.html 의 규칙 + Lenia 성장 창(과밀이면 줄어든다). 점 2개에 20/20 반응하고,
   *   점 8개에서 켜진 고리 수준을 낮춘다. 다른 설정은 URL ?rule=이름 으로 들어 본다. */
  var PAGE_ARM = 'echo_over';

  global.LeniaCore = { leniaStep: leniaStep, Engine: Engine, physicsStep: physicsStep, PHYS: PHYS,
                       arm: arm, PAGE_ARM: PAGE_ARM };
})(typeof window !== 'undefined' ? window : globalThis);
