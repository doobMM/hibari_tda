/* ============================================================================
 * ui-bootstrap.js — Phase 3: Overlap Matrix Editor UI 부트스트랩
 *
 * 책임:
 *   - HibariData 로드 대기 → 참조/편집 canvas 모두에 OverlapEditor 인스턴스 생성
 *   - 편집 상태를 localStorage (key = STORAGE_KEY) 에 자동 저장·복구
 *   - 컨트롤 버튼 (reset/random/clear) + diff 토글 배선
 *   - hover tooltip 으로 (t, cycle_id, note 구성) 표시
 *   - 편집 density / diff count 실시간 갱신
 *
 * Phase 4 에서 btnGenerate/btnStop/btnDownloadMidi 등에 생성 로직을 덧붙일 예정.
 * ========================================================================= */

(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const STORAGE_KEY = 'hibari_dashboard_edit_v2';
  const STORAGE_VERSION = 2;

  // 외부에서 참조할 수 있도록 전역 핸들
  const UI = {
    refEditor: null,
    editEditor: null,
    data: null,
    ood: null,        // OODDetector 인스턴스
  };

  // ── 로그/상태 유틸 ──────────────────────────────────────────────────
  function log(msg, kind) {
    const area = $('logArea');
    if (!area) return;
    const time = new Date().toTimeString().slice(0, 8);
    const prefix = kind ? `[${kind}] ` : '';
    area.textContent += `${time} ${prefix}${msg}\n`;
    area.scrollTop = area.scrollHeight;
  }

  function setStatus(text, kind) {
    const el = $('appStatus');
    if (!el) return;
    el.textContent = text;
    el.classList.remove('status-ok', 'status-err');
    if (kind === 'ok') el.classList.add('status-ok');
    if (kind === 'err') el.classList.add('status-err');
  }

  // ── localStorage 입출력 ──────────────────────────────────────────────
  function saveEditState(editor) {
    try {
      const v = editor.getMatrix();
      // Int8Array → 일반 배열 (JSON 직렬화용)
      const arr = Array.from(v);
      const blob = {
        version: STORAGE_VERSION,
        T: editor.T,
        K: editor.K,
        values: arr,
        savedAt: new Date().toISOString(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(blob));
    } catch (e) {
      console.warn('[saveEditState] 실패:', e);
    }
  }

  function loadEditState(expectT, expectK) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const blob = JSON.parse(raw);
      if (blob.version !== STORAGE_VERSION) return null;
      if (blob.T !== expectT || blob.K !== expectK) return null;
      if (!Array.isArray(blob.values) || blob.values.length !== expectT * expectK) return null;
      return new Int8Array(blob.values);
    } catch (e) {
      console.warn('[loadEditState] 실패:', e);
      return null;
    }
  }

  function clearEditState() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
  }

  // ── density / diff 표시 ─────────────────────────────────────────────
  function updateEditMeta(editor) {
    const pct = (editor.density() * 100).toFixed(2);
    const diff = editor.diffCount();
    const total = editor.T * editor.K;
    const diffPct = (diff / total * 100).toFixed(2);
    $('editMeta').textContent =
      `density ${pct}% · diff ${diff} (${diffPct}%)`;
  }

  function updateRefMeta(editor) {
    $('refMeta').textContent = `T=${editor.T} × K=${editor.K}`;
  }

  // ── OOD 배너 갱신 ───────────────────────────────────────────────────
  const LEVEL_LABEL = {
    stable: '안정',
    normal: '정상',
    warn: '주의',
    danger: '경고',
  };

  function updateOODBanner(editor) {
    if (!UI.ood) return;
    const banner = $('oodBanner');
    const scoreEl = $('oodScore');
    const levelEl = $('oodLevel');
    const detailEl = $('oodDetail');
    if (!banner || !scoreEl || !levelEl || !detailEl) return;

    const s = UI.ood.score(editor.getMatrix());

    banner.classList.remove('ood-hidden', 'level-warn', 'level-danger');
    // 편집이 전혀 없으면 배너 숨김 (stable + diff=0)
    if (s.diffCount === 0) {
      banner.classList.add('ood-hidden');
      return;
    }
    if (s.level === 'warn') banner.classList.add('level-warn');
    if (s.level === 'danger') banner.classList.add('level-danger');

    // 숫자는 0~1 을 %로
    scoreEl.textContent = (s.score * 100).toFixed(1) + '%';
    levelEl.textContent = LEVEL_LABEL[s.level] || s.level;
    detailEl.textContent = s.detail;
  }

  // ── Hover tooltip ───────────────────────────────────────────────────
  function formatHoverInfo(pos, data) {
    if (!pos) return '';
    const { t, c } = pos;
    const cycles = data.cyclesMeta?.cycles;
    let cycleText = `cycle ${c}`;
    if (cycles && cycles[c]) {
      const cy = cycles[c];
      const pers = cy.max_persistence != null ? cy.max_persistence.toFixed(4) : '-';
      const size = cy.size != null ? cy.size : '?';
      const tau = cy.tau != null ? cy.tau.toFixed(2) : '?';
      const notes = Array.isArray(cy.note_labels_1idx)
        ? cy.note_labels_1idx.join(',')
        : (Array.isArray(cy.note_labels_0idx) ? cy.note_labels_0idx.join(',') : '-');
      cycleText = `cycle ${c} (size=${size}) · notes=[${notes}] · τ=${tau} · pers=${pers}`;
    }
    return `t=${t}/${data.overlapRef.T}  ·  ${cycleText}`;
  }

  function attachHoverTooltip(editor, tooltipEl, wrapEl, data) {
    editor.onHover = (pos) => {
      if (!pos) {
        tooltipEl.hidden = true;
        return;
      }
      tooltipEl.hidden = false;
      tooltipEl.textContent = formatHoverInfo(pos, data);
      // wrap 내부 좌상단 기준으로 offset
      const canvas = editor.canvas;
      const cellW = editor.cellPxW * editor.view.scale;
      const cellH = editor.cellPxH * editor.view.scale;
      const x = editor.originX + editor.view.offsetX + pos.t * cellW + cellW + 6;
      const y = editor.originY + editor.view.offsetY + pos.c * cellH - 4;
      // canvas 의 offset 을 wrap 내부 기준으로 반영
      tooltipEl.style.left = (canvas.offsetLeft + x) + 'px';
      tooltipEl.style.top = (canvas.offsetTop + Math.max(0, y)) + 'px';
    };
  }

  // ── 컨트롤 버튼 배선 ─────────────────────────────────────────────────
  function wireControls() {
    $('btnReset').addEventListener('click', () => {
      if (!UI.editEditor) return;
      UI.editEditor.resetToReference();
      log('편집을 참조로 초기화했습니다.');
    });

    $('btnClear').addEventListener('click', () => {
      if (!UI.editEditor) return;
      UI.editEditor.clearAll();
      log('편집 matrix 를 모두 0 으로 비웠습니다.');
    });

    // ── 변형 컨트롤 배선 ─────────────────────────────────────────────
    const sV = $('sliderVariant');
    const sVVal = $('sliderVariantVal');
    if (sV && sVVal) {
      sV.addEventListener('input', () => {
        sVVal.textContent = parseFloat(sV.value).toFixed(2);
      });
    }
    $('variantMode').addEventListener('change', updateVariantHint);
    $('btnVariant').addEventListener('click', applyVariant);
    updateVariantHint();

    const diffToggle = $('toggleDiff');
    diffToggle.addEventListener('change', () => {
      if (!UI.editEditor) return;
      UI.editEditor.setDiffMode(diffToggle.checked);
      log(`diff 하이라이트 ${diffToggle.checked ? 'ON' : 'OFF'}`);
    });

    // seed 랜덤화
    $('btnRandomSeed').addEventListener('click', () => {
      const seed = Math.floor(Math.random() * 99999);
      $('sliderSeed').value = seed;
      log(`seed = ${seed}`);
    });

    // temperature 표시
    const sT = $('sliderTemp');
    const sTVal = $('sliderTempVal');
    if (sT && sTVal) {
      sT.addEventListener('input', () => {
        sTVal.textContent = parseFloat(sT.value).toFixed(1);
      });
    }

    // Phase 4 생성 버튼
    $('btnGenerate').addEventListener('click', onClickGenerate);
    $('btnDownloadMidi').addEventListener('click', onClickDownloadMidi);
  }

  // ── 변형 컨트롤 힌트/적용 로직 ───────────────────────────────────────
  const VARIANT_HINTS = {
    block:       '강도 t 를 올릴수록 블록 크기 증가 (bs = round(8·(1+3t))). 작을수록 국소 섞임, 클수록 구간 이동.',
    jitter:      '참조 각 ON 셀을 시간 축 ±round(24t), cycle 축 ±round(4t) 이내로 흔들기. 가까운 셀끼리 겹치면 병합되어 density 가 5~15% 감소할 수 있음.',
    shift:       '시간 축으로 round(T·t) 스텝만큼 원형 이동. density/분포 완전 동일, 시작점만 이동.',
    permuteTime: '시점(row) 순서를 완전 랜덤 permutation. cycle 별 column 분포는 완전 유지.',
    permuteCycle:'cycle(K) 번호를 permutation. 각 시점의 활성 cycle 개수는 완전 유지.',
    shuffle:     'ON 셀 개수(N_on)를 유지하면서 위치를 완전 랜덤 재배치. 공간 구조 완전 파괴, density 만 유지.',
    flood:       '2~5 개 씨앗에서 시작해 4방향으로 번지는 물자국. 강도 = 번짐 확률 (0.3~0.9).',
    bernoulli:   '각 셀을 참조 density 와 같은 확률로 독립 추출. 완전 노이즈 — 생성 음악도 거의 무작위.',
  };
  const VARIANT_LABEL = {
    block: '블록 셔플', jitter: '참조 왜곡', shift: '원형 이동',
    permuteTime: '시간축 셔플', permuteCycle: 'cycle 셔플',
    shuffle: '무작위 재분배', flood: '흐름 무늬', bernoulli: '독립 Bernoulli',
  };

  function updateVariantHint() {
    const mode = $('variantMode').value;
    $('variantHint').textContent = VARIANT_HINTS[mode] || '';
  }

  function applyVariant() {
    if (!UI.editEditor || !UI.data) { log('데이터 미로드', 'ERR'); return; }
    const ed = UI.editEditor;
    const mode = $('variantMode').value;
    const seed = parseInt($('sliderSeed').value, 10) || 0;
    const t = parseFloat($('sliderVariant').value);
    const refDens = UI.data.overlapRef.density ?? 0.3;
    const fromCurrent = $('toggleFromCurrent').checked;
    const fromRef = !fromCurrent;
    const T = ed.T;

    switch (mode) {
      case 'shuffle':
        ed.shuffleDensity(seed, fromRef);
        break;
      case 'permuteTime':
        ed.permuteTime(seed, fromRef);
        break;
      case 'permuteCycle':
        ed.permuteCycles(seed, fromRef);
        break;
      case 'block': {
        const bs = Math.max(2, Math.round(8 * (1 + t * 3)));
        ed.blockShuffle(bs, seed, fromRef);
        log(`${VARIANT_LABEL[mode]}: blockSize=${bs} (${fromRef ? '참조' : '편집본'} 기반, seed=${seed})`);
        return;
      }
      case 'shift': {
        const dt = Math.round(T * t);
        ed.circularShift(dt, 0, fromRef);
        log(`${VARIANT_LABEL[mode]}: Δt=${dt} (${fromRef ? '참조' : '편집본'} 기반, seed=${seed})`);
        return;
      }
      case 'flood': {
        const spread = 0.3 + 0.6 * t;
        ed.floodPattern(seed, refDens, spread);
        log(`${VARIANT_LABEL[mode]}: spread=${spread.toFixed(2)}, target density≈${(refDens*100).toFixed(1)}%, seed=${seed}`);
        return;
      }
      case 'jitter': {
        if (fromRef) {
          ed.jitterFromReference(Math.max(0.02, t), seed);
        } else {
          // 편집본 기반 jitter: 현재 values 를 임시 reference 로 swap
          const origRef = ed.reference;
          ed.reference = ed.values;
          ed.jitterFromReference(Math.max(0.02, t), seed);
          ed.reference = origRef;
        }
        log(`${VARIANT_LABEL[mode]}: strength=${t.toFixed(2)} (${fromRef ? '참조' : '편집본'} 기반, seed=${seed})`);
        return;
      }
      case 'bernoulli':
        ed.randomFill(refDens, seed);
        log(`${VARIANT_LABEL[mode]}: density≈${(refDens*100).toFixed(1)}%, seed=${seed}`);
        return;
    }
    // 공통 로그 (shuffle/permuteTime/permuteCycle)
    log(`${VARIANT_LABEL[mode]}: (${fromRef ? '참조' : '편집본'} 기반, seed=${seed})`);
  }

  // ── Phase 4: 생성·재생 로직 ─────────────────────────────────────────
  const BAR_STEPS = 32;         // 한 마디 = 32개 8분음표

  const playState = {
    lastGenerated: null,
    genPlayer: null,
    previewPlayer: null,    // cycle 미리듣기 전용 PianoPlayer (생성과 분리)
    previewTimer: null,
    bpm: 60,
  };

  // ── Cycle 미리듣기 ─────────────────────────────────────────────────
  const PITCH_CLASS_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  function pitchName(midi) {
    if (midi == null || !isFinite(midi)) return '?';
    const pc = ((midi % 12) + 12) % 12;
    const oct = Math.floor(midi / 12) - 1;   // MIDI 60 = C4
    return PITCH_CLASS_NAMES[pc] + oct;
  }

  function getCyclePitches(cycleIdx) {
    if (!UI.data) return [];
    const cy = UI.data.cyclesMeta?.cycles?.[cycleIdx];
    if (!cy) return [];
    const labels = UI.data.notesMeta?.labels || [];
    // cycle edge 연결 순서 (traversal_1idx) 우선, 없으면 sorted fallback
    const useTraversal = Array.isArray(cy.traversal_1idx) && cy.traversal_1idx.length > 0;
    const ids = useTraversal ? cy.traversal_1idx : (cy.note_labels_1idx || []);
    const pitches = [];
    for (const l of ids) {
      const lab = labels[l - 1];          // 1-indexed → array index
      if (lab && typeof lab.pitch === 'number') pitches.push(lab.pitch);
    }
    if (useTraversal) {
      // traversal 순서 보존. 연속 중복 pitch 만 skip (같은 pc 다른 dur 라벨이 인접한 경우).
      const out = [];
      for (const p of pitches) {
        if (out.length === 0 || out[out.length - 1] !== p) out.push(p);
      }
      return out;
    }
    // fallback: 중복 pitch 제거 + 오름차순
    return Array.from(new Set(pitches)).sort((a, b) => a - b);
  }

  // 전용 AudioContext (피아노풍 합성) — PianoPlayer 보다 풍부한 harmonic
  function ensureCyclePreviewCtx() {
    if (!playState.previewCtx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      playState.previewCtx = new AC();
    }
    if (playState.previewCtx.state === 'suspended') {
      playState.previewCtx.resume().catch(() => {});
    }
    return playState.previewCtx;
  }

  // 피아노풍 1음 스케줄링 — 다중 partial + brightness 감쇄 lowpass + 피아노식 envelope
  function schedulePianoNote(ctx, dest, freq, startT, dur, vel) {
    vel = Math.max(0.1, Math.min(1, vel));
    // Mild inharmonicity (실제 피아노는 stretched tuning — 배음이 정수배보다 살짝 높음)
    const B = 0.00035;

    // Brightness 감쇄: 타격 직후 밝고, 빠르게 어두워짐
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.Q.value = 0.6;
    filter.frequency.setValueAtTime(3400 + 2000 * vel, startT);
    filter.frequency.exponentialRampToValueAtTime(780, startT + Math.min(dur, 2.2));

    // Envelope: 매우 빠른 attack → 초기 급감 → 긴 꼬리 (피아노는 sustain 수준이 없음)
    const amp = ctx.createGain();
    const peak = 0.19 * vel;
    amp.gain.setValueAtTime(0.0001, startT);
    amp.gain.exponentialRampToValueAtTime(peak,          startT + 0.004);
    amp.gain.exponentialRampToValueAtTime(peak * 0.55,   startT + 0.10);
    amp.gain.exponentialRampToValueAtTime(peak * 0.18,   startT + Math.min(dur * 0.6, 0.9));
    amp.gain.exponentialRampToValueAtTime(0.001,         startT + dur);
    amp.gain.linearRampToValueAtTime(0,                  startT + dur + 0.06);

    filter.connect(amp).connect(dest);

    // 4 partial: fund(triangle) + 2f + 3f + 4f (모두 sine, 감쇠 gain)
    const partials = [
      { n: 1, gain: 0.85, type: 'triangle' },
      { n: 2, gain: 0.28, type: 'sine' },
      { n: 3, gain: 0.10, type: 'sine' },
      { n: 4, gain: 0.045, type: 'sine' },
    ];
    for (const p of partials) {
      const inhar = Math.sqrt(1 + B * p.n * p.n);
      const osc = ctx.createOscillator();
      osc.type = p.type;
      osc.frequency.value = freq * p.n * inhar;
      const g = ctx.createGain();
      g.gain.value = p.gain;
      osc.connect(g).connect(filter);
      osc.start(startT);
      osc.stop(startT + dur + 0.10);
    }
  }

  // 사이클은 닫힌 루프이므로 startPitch 를 첫번째로 오도록 순환 회전
  function rotateToStart(arr, startPitch) {
    if (startPitch == null) return arr;
    const i = arr.indexOf(startPitch);
    if (i <= 0) return arr;            // 없거나 이미 선두면 그대로
    return arr.slice(i).concat(arr.slice(0, i));
  }

  // 사이클 선택 (재생 없이 건반 시각화만)
  function selectCycle(cycleIdx) {
    playState.selectedCycleIdx = cycleIdx;
    const listEl = $('cycleList');
    if (listEl) {
      listEl.querySelectorAll('.cycle-item.is-selected').forEach(el => el.classList.remove('is-selected'));
      const row = listEl.querySelector(`.cycle-item[data-cycle="${cycleIdx}"]`);
      row && row.classList.add('is-selected');
    }
    renderCycleViz(cycleIdx, null);
  }

  function playCyclePreview(cycleIdx, startPitch) {
    let pitches = getCyclePitches(cycleIdx);
    if (pitches.length === 0) {
      log(`cycle ${cycleIdx}: 재생할 음이 없음`, 'ERR');
      return;
    }
    pitches = rotateToStart(pitches, startPitch);

    // 선택 상태 보장 (재생 = 선택 + 순차 하이라이트)
    selectCycle(cycleIdx);

    const ctx = ensureCyclePreviewCtx();
    const master = ctx.createGain();
    master.gain.value = 0.85;
    master.connect(ctx.destination);

    const spacing = 0.30;    // 음 간 간격 (사용자 요청: 약간 느리게)
    const hold = 0.95;       // 각 음 지속 (피아노 envelope 이 스스로 감쇄)
    const preRollSec = 0.08;
    const t0 = ctx.currentTime + preRollSec;

    pitches.forEach((midi, i) => {
      const freq = 440 * Math.pow(2, (midi - 69) / 12);
      schedulePianoNote(ctx, master, freq, t0 + i * spacing, hold, 0.85);
    });

    // 시각화: 순차 highlight (row + 건반)
    if (playState._animTimers) playState._animTimers.forEach(id => clearTimeout(id));
    playState._animTimers = [];

    const listEl = $('cycleList');
    listEl && listEl.querySelectorAll('.cycle-item.is-playing').forEach(el => el.classList.remove('is-playing'));
    const row = listEl && listEl.querySelector(`.cycle-item[data-cycle="${cycleIdx}"]`);
    row && row.classList.add('is-playing');

    const preRollMs = preRollSec * 1000;
    pitches.forEach((midi, i) => {
      const tid = setTimeout(() => {
        renderCycleViz(cycleIdx, midi);
      }, preRollMs + i * spacing * 1000);
      playState._animTimers.push(tid);
    });
    const endMs = preRollMs + ((pitches.length - 1) * spacing + hold) * 1000;
    const endTid = setTimeout(() => {
      row && row.classList.remove('is-playing');
      renderCycleViz(cycleIdx, null);
    }, endMs);
    playState._animTimers.push(endTid);
  }

  // ── 피아노 건반 시각화 ─────────────────────────────────────────────
  const VIZ_MIN_MIDI = 48;                       // C3
  const VIZ_NUM_OCT  = 3;                        // C3..B5
  const WHITE_SEMITONES = [0, 2, 4, 5, 7, 9, 11];
  const BLACK_SEMITONES = [1, 3, 6, 8, 10];
  // Octave 내 각 black key 의 white-key 단위 중심 위치 (C=0 기준)
  const BLACK_WK_OFFSET = { 1: 0.70, 3: 1.70, 6: 3.70, 8: 4.70, 10: 5.70 };

  function drawPitchKeyboard(cv, activePitches, playingPitch) {
    const wrap = cv.parentElement;
    const cssW = Math.max(200, wrap.clientWidth - 4);
    const cssH = 64;
    const dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.floor(cssW * dpr) || cv.height !== Math.floor(cssH * dpr)) {
      cv.width = Math.floor(cssW * dpr);
      cv.height = Math.floor(cssH * dpr);
      cv.style.width = cssW + 'px';
      cv.style.height = cssH + 'px';
    }
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const cs = getComputedStyle(document.documentElement);
    const read = (v, f) => (cs.getPropertyValue(v).trim() || f);
    const whiteFill  = read('--surface-overlay', '#ffffff');
    const blackFill  = read('--text-primary',    '#2f3a28');
    const borderCol  = read('--border-hairline', '#d9c5ae');
    const activeCol  = read('--accent-teal',     '#6fa66a');
    const playingCol = read('--accent-amber',    '#e88f6a');
    const textCol    = read('--text-tertiary',   '#a89b89');

    const actSet = new Set(activePitches);
    const whiteCount = 7 * VIZ_NUM_OCT;
    const wkW = cssW / whiteCount;
    const bkW = wkW * 0.62;
    const bkH = cssH * 0.62;

    // 1) White keys
    for (let oct = 0; oct < VIZ_NUM_OCT; oct++) {
      for (let i = 0; i < 7; i++) {
        const sem = WHITE_SEMITONES[i];
        const midi = VIZ_MIN_MIDI + oct * 12 + sem;
        const x = (oct * 7 + i) * wkW;
        const isPlaying = midi === playingPitch;
        const isActive  = actSet.has(midi);
        ctx.fillStyle = isPlaying ? playingCol : (isActive ? activeCol : whiteFill);
        ctx.fillRect(x, 0, wkW - 0.5, cssH);
        ctx.strokeStyle = borderCol;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, 0.5, wkW - 1, cssH - 1);
      }
    }

    // 2) Octave 라벨 (C3/C4/C5)
    ctx.fillStyle = textCol;
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.textBaseline = 'bottom';
    for (let oct = 0; oct < VIZ_NUM_OCT; oct++) {
      const x = oct * 7 * wkW + 3;
      ctx.fillText(`C${oct + 3}`, x, cssH - 2);
    }

    // 3) Black keys (overlay)
    for (let oct = 0; oct < VIZ_NUM_OCT; oct++) {
      for (const sem of BLACK_SEMITONES) {
        const midi = VIZ_MIN_MIDI + oct * 12 + sem;
        const centerX = (oct * 7 + BLACK_WK_OFFSET[sem]) * wkW;
        const x = centerX - bkW / 2;
        const isPlaying = midi === playingPitch;
        const isActive  = actSet.has(midi);
        ctx.fillStyle = isPlaying ? playingCol : (isActive ? activeCol : blackFill);
        ctx.fillRect(x, 0, bkW, bkH);
        ctx.strokeStyle = borderCol;
        ctx.lineWidth = 0.8;
        ctx.strokeRect(x + 0.4, 0.4, bkW - 0.8, bkH - 0.8);
      }
    }

    // 4) hit-test 메타 저장 — 클릭 시 (cssX, cssY) → midi pitch
    cv._layout = { cssW, cssH, wkW, bkW, bkH, activeSet: actSet };
    cv._hitTest = function (cssX, cssY) {
      // black keys 먼저 (상단 overlay)
      if (cssY <= bkH) {
        for (let oct = 0; oct < VIZ_NUM_OCT; oct++) {
          for (const sem of BLACK_SEMITONES) {
            const midi = VIZ_MIN_MIDI + oct * 12 + sem;
            const centerX = (oct * 7 + BLACK_WK_OFFSET[sem]) * wkW;
            const x = centerX - bkW / 2;
            if (cssX >= x && cssX <= x + bkW) return midi;
          }
        }
      }
      // white keys
      for (let oct = 0; oct < VIZ_NUM_OCT; oct++) {
        for (let i = 0; i < 7; i++) {
          const midi = VIZ_MIN_MIDI + oct * 12 + WHITE_SEMITONES[i];
          const x = (oct * 7 + i) * wkW;
          if (cssX >= x && cssX <= x + wkW) return midi;
        }
      }
      return null;
    };
  }

  function renderCycleViz(cycleIdx, playingPitch) {
    const cv = $('cycleVizKeys');
    const labelEl = $('cycleVizLabel');
    if (!cv || !labelEl) return;
    // 선택 없음
    if (cycleIdx == null || cycleIdx === undefined) {
      labelEl.innerHTML = '<span class="cycle-viz__hint">위 목록의 ▶ 또는 건반을 눌러 사이클을 선택하세요</span>';
      drawPitchKeyboard(cv, [], null);
      cv.style.cursor = 'default';
      return;
    }
    const pitches = getCyclePitches(cycleIdx);
    const names = pitches.map(pitchName).join(' ');
    labelEl.innerHTML =
      `<span class="cycle-viz__id">c${cycleIdx}</span>` +
      `<span class="cycle-viz__notes" title="${names}">${names || '(empty)'}</span>` +
      `<span class="cycle-viz__count" style="margin-left:auto">${pitches.length}음</span>`;
    drawPitchKeyboard(cv, pitches, playingPitch == null ? null : playingPitch);

    // 클릭 → 해당 pitch 부터 재생 (최초 1회만 wiring)
    if (!cv._wiredClick) {
      cv.addEventListener('click', (e) => {
        const idx = playState.selectedCycleIdx;
        if (idx == null) return;
        if (!cv._hitTest) return;
        const rect = cv.getBoundingClientRect();
        const cssX = e.clientX - rect.left;
        const cssY = e.clientY - rect.top;
        const midi = cv._hitTest(cssX, cssY);
        if (midi == null) return;
        const layout = cv._layout;
        if (!layout || !layout.activeSet.has(midi)) return;   // 비활성 건반은 무시
        playCyclePreview(idx, midi);
      });
      cv.addEventListener('mousemove', (e) => {
        if (!cv._hitTest || !cv._layout) { cv.style.cursor = 'default'; return; }
        const rect = cv.getBoundingClientRect();
        const midi = cv._hitTest(e.clientX - rect.left, e.clientY - rect.top);
        cv.style.cursor = (midi != null && cv._layout.activeSet.has(midi)) ? 'pointer' : 'default';
      });
      cv._wiredClick = true;
    }
  }

  function populateCycleList() {
    const container = $('cycleList');
    if (!container || !UI.data) return;
    const cycles = UI.data.cyclesMeta?.cycles || [];
    container.innerHTML = '';
    cycles.forEach((cy, idx) => {
      const pitches = getCyclePitches(idx);
      const names = pitches.map(pitchName).join(' ');
      const row = document.createElement('div');
      row.className = 'cycle-item';
      row.setAttribute('role', 'listitem');
      row.dataset.cycle = String(idx);
      row.innerHTML =
        `<button class="cycle-item__play" type="button" data-cycle="${idx}" ` +
        `title="cycle ${idx} 미리듣기 (${pitches.length}음)" ` +
        `aria-label="cycle ${idx} 미리듣기">▶</button>` +
        `<span class="cycle-item__id">c${idx}</span>` +
        `<span class="cycle-item__notes" title="${names}">${names || '(empty)'}</span>`;
      container.appendChild(row);
    });
    // 이벤트는 한 번만 (delegation)
    if (!container._wired) {
      container.addEventListener('click', (e) => {
        // ▶ 버튼: 선택 + 재생
        const btn = e.target.closest('.cycle-item__play');
        if (btn) {
          const idx = parseInt(btn.dataset.cycle, 10);
          if (!isNaN(idx)) playCyclePreview(idx);
          return;
        }
        // row 본체: 선택만 (건반 시각화)
        const row = e.target.closest('.cycle-item');
        if (row) {
          const idx = parseInt(row.dataset.cycle, 10);
          if (!isNaN(idx)) selectCycle(idx);
        }
      });
      container._wired = true;
    }
  }

  function ensurePlayer() {
    if (!playState.genPlayer) playState.genPlayer = new window.PianoPlayer();
    return playState.genPlayer;
  }

  function setProgress(frac, meta) {
    const bar = $('progressFill');
    if (!bar) return;
    const p = Math.max(0, Math.min(1, frac));
    bar.style.width = (p * 100).toFixed(2) + '%';
    if (meta != null) $('playbackMeta').textContent = meta;
  }

  // 8분음표 → seconds 변환 (bpm: quarter = 60/bpm, 8th = 30/bpm)
  function eighthsToSec(eighths, bpm) {
    return eighths * (30 / bpm);
  }

  // 알고리즘 1: overlap(이미 슬라이스된 형태 포함) 하나 생성
  function runAlgo1Once({ overlap, instLen, temperature, seed }) {
    const { NodePool, CycleSetManager, algorithm1, makeRng } = window.GenerationAlgo1;
    const rng = makeRng(seed >>> 0);
    const pool = new NodePool({
      labels: UI.data.notesMeta.labels,
      numModules: UI.data.notesMeta.num_modules_reference,
      temperature,
      rng,
    });
    const cycleMgr = new CycleSetManager({
      cycles: UI.data.cyclesMeta.cycles,
      K: overlap.K,
    });
    const t0 = performance.now();
    const res = algorithm1({
      nodePool: pool, cycleManager: cycleMgr,
      instLen, overlap, maxResample: 50, rng,
    });
    res.elapsedMs = performance.now() - t0;
    return res;
  }

  // 알고리즘 2 (FC): overlap 하나 추론
  async function runAlgo2Once({ overlap, temperature }) {
    const targetOnRatio = Math.max(0.05, Math.min(0.35, 0.05 * temperature));
    const res = await playState.fcGen.generate({
      overlap, adaptive: true, targetOnRatio, minOnsetGap: 0,
    });
    return res;
  }

  // FC 모델 지연 로드 (슬라이스 모드에서 매번 확인)
  async function ensureFcLoaded() {
    if (!window.FCGenerator) throw new Error('FCGenerator 모듈 미로드');
    if (!playState.fcGen) playState.fcGen = new window.FCGenerator();
    if (!playState.fcGen.session) log('FC 모델 로드 중… (ONNX runtime + 모델 다운로드)');
    await playState.fcGen.load();
    if (playState.fcLoaded !== true) {
      log(`FC 모델 로드 완료 (${playState.fcGen.meta.architecture})`, 'OK');
      playState.fcLoaded = true;
    }
  }

  // 생성 버튼 메인 핸들러 — 34마디 전곡 1개
  async function onClickGenerate() {
    if (!UI.editEditor || !UI.data) { log('데이터 미로드', 'ERR'); return; }
    if (!window.GenerationAlgo1) { log('GenerationAlgo1 모듈 미로드', 'ERR'); return; }

    const algo = document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
    const temperature = parseFloat($('sliderTemp').value) || 3.0;
    const seed = parseInt($('sliderSeed').value, 10) || 0;

    const { buildHibariInstLen } = window.GenerationAlgo1;
    const fullInstLen = buildHibariInstLen(UI.editEditor.T);
    const fullOverlap = {
      T: UI.editEditor.T,
      K: UI.editEditor.K,
      values: UI.editEditor.getMatrix(),
    };

    try {
      const algoLabel = algo === 'algo2' ? 'Algorithm 2 (FC)' : 'Algorithm 1';
      const bars = Math.round(fullOverlap.T / BAR_STEPS);
      log(`${algoLabel} 전곡 생성 (T=${fullOverlap.T}, ${bars}마디, seed=${seed}, temp=${temperature.toFixed(1)})`);
      if (algo === 'algo2') await ensureFcLoaded();

      const t0 = performance.now();
      let res;
      if (algo === 'algo2') {
        res = await runAlgo2Once({ overlap: fullOverlap, temperature });
      } else {
        res = runAlgo1Once({ overlap: fullOverlap, instLen: fullInstLen, temperature, seed });
      }
      res.offset = 0;
      const dt = performance.now() - t0;
      log(`생성 완료 (${dt.toFixed(0)}ms, ${res.notes.length} notes)`, 'OK');

      playState.lastGenerated = res;
      $('btnDownloadMidi').disabled = false;
      setProgress(1, `생성 완료 · ${res.notes.length} notes · MIDI 저장 버튼으로 다운로드`);
    } catch (e) {
      log(`생성 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  function onClickDownloadMidi() {
    if (!playState.lastGenerated) {
      log('다운로드할 생성 결과가 없습니다 (먼저 Generate)', 'ERR');
      return;
    }
    try {
      const cur = playState.lastGenerated;
      const bytes = window.MidiIO.notesToMidiBytes(cur.notes, {
        bpm: playState.bpm,
        ticksPerEighth: 240,
        velocity: 80,
      });
      const seed = parseInt($('sliderSeed').value, 10) || 0;
      const fname = `hibari_dash_seed${seed}_off${cur.offset|0}.mid`;
      window.MidiIO.downloadBytes(bytes, fname);
      log(`MIDI 다운로드: ${fname} (${(bytes.length / 1024).toFixed(1)} KB)`, 'OK');
    } catch (e) {
      log(`MIDI 저장 실패: ${e.message}`, 'ERR');
    }
  }

  // ── 부트스트랩 본체 ─────────────────────────────────────────────────
  function bootstrap() {
    wireControls();
    setStatus('데이터 로드 중…');

    if (!window.HibariData) {
      setStatus('data-loader 미초기화', 'err');
      log('HibariData 전역이 존재하지 않습니다', 'err');
      return;
    }
    if (!window.OverlapEditor) {
      setStatus('overlap-editor 미로드', 'err');
      log('OverlapEditor 전역이 존재하지 않습니다', 'err');
      return;
    }

    window.HibariData.onReady((data) => {
      UI.data = data;
      const { T, K, values } = data.overlapRef;

      // 참조 editor: readonly
      UI.refEditor = new window.OverlapEditor($('refCanvas'), {
        T, K,
        values: values,
        readonly: true,
      });
      updateRefMeta(UI.refEditor);

      // OOD detector: 참조 + cycle persistence 로 초기화
      if (window.OODDetector) {
        UI.ood = new window.OODDetector({
          reference: values,
          T, K,
          cycles: data.cyclesMeta.cycles,
        });
      }

      // 편집 editor: 상호작용
      const restored = loadEditState(T, K);
      const initVals = restored || values; // 복구 실패 시 참조 복사
      UI.editEditor = new window.OverlapEditor($('editCanvas'), {
        T, K,
        values: initVals,
        reference: values,
        readonly: false,
        onChange: (ed) => {
          updateEditMeta(ed);
          updateOODBanner(ed);
          saveEditState(ed);
        },
      });
      updateEditMeta(UI.editEditor);
      updateOODBanner(UI.editEditor);

      // hover tooltip
      const tt = $('hoverTooltip');
      const wrap = $('editCanvas').parentElement;
      attachHoverTooltip(UI.editEditor, tt, wrap, data);

      // 사이클 미리듣기 목록 + 시각화 초기 렌더 (c0 기본 표시)
      populateCycleList();
      playState.selectedCycleIdx = 0;
      renderCycleViz(0, null);

      // 최초 로드 상태 메시지
      setStatus(
        `T=${T} · K=${K} · N=${data.notesMeta.num_notes} · DFT α=0.25 per-cycle τ`,
        'ok'
      );
      log(`데이터 로드 완료 (manifest version ${data.manifest.version})`, 'OK');
      log(`overlap shape: T=${T}, K=${K}, density=${(data.overlapRef.density * 100).toFixed(2)}%`);
      log(`notes=${data.notesMeta.num_notes}, cycles=${data.cyclesMeta.num_cycles}`);
      if (restored) {
        log(`localStorage 에서 편집 상태 복구 완료 (diff ${UI.editEditor.diffCount()} cells)`);
      } else {
        log(`편집 matrix 를 참조로 초기화 (diff 0)`);
      }

      // 콘솔 접근 힌트
      console.log(
        '%c[Hibari Dashboard] 디버그 핸들:',
        'color:#4ADE80;font-weight:bold',
        '\nUI.refEditor / UI.editEditor',
        '\nwindow.HibariData.overlapRef / overlapCont / notesMeta / cyclesMeta'
      );
      // 테마 토글 / 리사이즈 시 재렌더를 위한 외부 핸들
      UI.renderCycleViz = () => renderCycleViz(
        playState.selectedCycleIdx != null ? playState.selectedCycleIdx : null,
        null,
      );
      window.HibariUI = UI;

      // 창 크기 변경 시 건반 캔버스 재계산
      window.addEventListener('resize', () => {
        UI.renderCycleViz && UI.renderCycleViz();
      });
    });

    // 1.5 초 후에도 로드 안 됐으면 오류 상태 갱신
    setTimeout(() => {
      if (!window.HibariData.loaded) {
        if (window.HibariData.error) {
          setStatus('데이터 로드 실패', 'err');
          log(window.HibariData.error, 'ERR');
        } else {
          log('로드 중… (느릴 수 있음)');
        }
      }
    }, 1500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
})();
