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
  const STORAGE_KEY = 'hibari_dashboard_edit_v1';
  const STORAGE_VERSION = 1;

  // 외부에서 참조할 수 있도록 전역 핸들
  const UI = {
    refEditor: null,
    editEditor: null,
    data: null,
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

    $('btnRandom').addEventListener('click', () => {
      if (!UI.editEditor) return;
      const seed = parseInt($('sliderSeed').value, 10) || 0;
      // 현재 참조 density 와 같은 수준으로
      const d = UI.data?.overlapRef?.density ?? 0.3;
      UI.editEditor.randomFill(d, seed);
      log(`랜덤 채움: density≈${(d*100).toFixed(1)}%, seed=${seed}`);
    });

    $('btnClear').addEventListener('click', () => {
      if (!UI.editEditor) return;
      UI.editEditor.clearAll();
      log('편집 matrix 를 모두 0 으로 비웠습니다.');
    });

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

    // Phase 4 생성·재생 버튼
    $('btnGenerate').addEventListener('click', onClickGenerate);
    $('btnStop').addEventListener('click', onClickStop);
    $('btnDownloadMidi').addEventListener('click', onClickDownloadMidi);
    $('btnPlayOriginal').addEventListener('click', onClickPlayOriginal);
    $('btnStopOriginal').addEventListener('click', onClickStopOriginal);
  }

  // ── Phase 4: 생성·재생 로직 ─────────────────────────────────────────
  const playState = {
    lastGenerated: null,      // { notes: [[startEighth, pitch, endEighth]], meta: {...} }
    lastOriginalNotes: null,  // [[startSec, pitch, endSec, vel], ...]
    genPlayer: null,
    origPlayer: null,
    bpm: 60,                  // 생성 MIDI 기본 tempo
  };

  function ensurePlayer(kind) {
    const k = kind === 'orig' ? 'origPlayer' : 'genPlayer';
    if (!playState[k]) playState[k] = new window.PianoPlayer();
    return playState[k];
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

  // 생성 버튼
  function onClickGenerate() {
    if (!UI.editEditor || !UI.data) { log('데이터 미로드', 'ERR'); return; }
    if (!window.GenerationAlgo1) { log('GenerationAlgo1 모듈 미로드', 'ERR'); return; }

    const algo = document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
    const temperature = parseFloat($('sliderTemp').value) || 3.0;
    const seed = parseInt($('sliderSeed').value, 10) || 0;

    if (algo === 'algo2') {
      runAlgo2(temperature, seed);
      return;
    }

    const t0 = performance.now();
    log(`Algorithm 1 생성 시작 (T=${UI.editEditor.T}, temp=${temperature.toFixed(1)}, seed=${seed})`);

    try {
      const { NodePool, CycleSetManager, algorithm1, makeRng, buildHibariInstLen } =
        window.GenerationAlgo1;

      const rng = makeRng(seed);
      const pool = new NodePool({
        labels: UI.data.notesMeta.labels,
        numModules: UI.data.notesMeta.num_modules_reference,
        temperature,
        rng,
      });
      const cycleMgr = new CycleSetManager({
        cycles: UI.data.cyclesMeta.cycles,
        K: UI.editEditor.K,
      });
      const instLen = buildHibariInstLen(UI.editEditor.T);
      const overlap = {
        T: UI.editEditor.T,
        K: UI.editEditor.K,
        values: UI.editEditor.getMatrix(),
      };

      const res = algorithm1({
        nodePool: pool,
        cycleManager: cycleMgr,
        instLen,
        overlap,
        maxResample: 50,
        rng,
      });

      const dt = performance.now() - t0;
      log(`생성 완료: ${res.notes.length} notes, resample fail=${res.resampleFails}, ${dt.toFixed(0)}ms`, 'OK');

      playState.lastGenerated = res;
      $('btnStop').disabled = false;
      $('btnDownloadMidi').disabled = false;

      // 재생용 초 단위 note 리스트로 변환
      const bpm = playState.bpm;
      const sec = res.notes.map(([s, p, e]) => [
        eighthsToSec(s, bpm),
        p,
        eighthsToSec(e, bpm),
        70,
      ]);

      const player = ensurePlayer('gen');
      player.play(sec, {
        onProgress: (t, total) => setProgress(total > 0 ? t / total : 0,
          `재생중 · ${t.toFixed(1)}s / ${total.toFixed(1)}s · ${res.notes.length} notes`),
        onEnd: () => {
          setProgress(1, `완료 · ${res.notes.length} notes`);
          $('btnStop').disabled = true;
          log('재생 종료');
        },
      });
    } catch (e) {
      log(`생성 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  // Algorithm 2 (FC model) 실행
  async function runAlgo2(temperature, seed) {
    if (!window.FCGenerator) {
      log('FCGenerator 모듈 미로드', 'ERR');
      return;
    }
    if (!playState.fcGen) playState.fcGen = new window.FCGenerator();
    try {
      if (!playState.fcGen.session) {
        log('FC 모델 로드 중… (ONNX runtime + 모델 다운로드)');
      }
      await playState.fcGen.load();
      if (playState.fcLoaded !== true) {
        const m = playState.fcGen.meta;
        log(`FC 모델 로드 완료 (${m.architecture})`, 'OK');
        playState.fcLoaded = true;
      }

      const overlap = {
        T: UI.editEditor.T,
        K: UI.editEditor.K,
        values: UI.editEditor.getMatrix(),
      };
      // temperature 는 FC 에서는 threshold 조절용으로 사용:
      //   higher temp → lower threshold → 더 많은 activation
      const targetOnRatio = Math.max(0.05, Math.min(0.35, 0.05 * temperature));
      log(`Algorithm 2 (FC) 추론 시작 (targetOnRatio=${targetOnRatio.toFixed(2)}, seed=${seed})`);

      const res = await playState.fcGen.generate({
        overlap, adaptive: true, targetOnRatio, minOnsetGap: 0,
      });

      log(`추론 완료: ${res.notes.length} notes, threshold=${res.threshold.toFixed(4)}, ${res.inferenceMs.toFixed(0)}ms`, 'OK');

      playState.lastGenerated = res;
      $('btnStop').disabled = false;
      $('btnDownloadMidi').disabled = false;

      // 8 분음표 → 초 변환 후 재생
      const bpm = playState.bpm;
      const sec = res.notes.map(([s, p, e]) => [
        eighthsToSec(s, bpm), p, eighthsToSec(e, bpm), 70,
      ]);

      const player = ensurePlayer('gen');
      player.play(sec, {
        onProgress: (t, total) => setProgress(total > 0 ? t / total : 0,
          `FC 재생중 · ${t.toFixed(1)}s / ${total.toFixed(1)}s · ${res.notes.length} notes`),
        onEnd: () => {
          setProgress(1, `완료 · ${res.notes.length} notes`);
          $('btnStop').disabled = true;
          log('FC 재생 종료');
        },
      });
    } catch (e) {
      log(`FC 생성 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  function onClickStop() {
    if (playState.genPlayer) playState.genPlayer.stop();
    setProgress(0, '중지');
    $('btnStop').disabled = true;
  }

  function onClickDownloadMidi() {
    if (!playState.lastGenerated) {
      log('다운로드할 생성 결과가 없습니다 (먼저 Generate)', 'ERR');
      return;
    }
    try {
      const { notes } = playState.lastGenerated;
      const bytes = window.MidiIO.notesToMidiBytes(notes, {
        bpm: playState.bpm,
        ticksPerEighth: 240,
        velocity: 80,
      });
      const seed = parseInt($('sliderSeed').value, 10) || 0;
      const fname = `hibari_dash_seed${seed}.mid`;
      window.MidiIO.downloadBytes(bytes, fname);
      log(`MIDI 다운로드: ${fname} (${(bytes.length / 1024).toFixed(1)} KB)`, 'OK');
    } catch (e) {
      log(`MIDI 저장 실패: ${e.message}`, 'ERR');
    }
  }

  // 원곡 재생
  async function onClickPlayOriginal() {
    if (!window.MidiIO || !window.PianoPlayer) {
      log('MIDI/오디오 모듈 미로드', 'ERR'); return;
    }
    try {
      if (!playState.lastOriginalNotes) {
        const base = (new URLSearchParams(window.location.search).get('data') || '../data') + '/';
        const url = base + 'original_hibari.mid';
        log(`원곡 MIDI 로드 중: ${url}`);
        const res = await fetch(url, { cache: 'no-cache' });
        if (!res.ok) throw new Error(`원곡 MIDI 로드 실패: ${res.status}`);
        const buf = await res.arrayBuffer();
        const parsed = window.MidiIO.readMidiNotes(new Uint8Array(buf));
        playState.lastOriginalNotes = parsed.notes;
        log(`원곡 파싱 완료: ${parsed.notes.length} notes, ${parsed.bpm.toFixed(1)} BPM`, 'OK');
      }
      const player = ensurePlayer('orig');
      $('btnStopOriginal').disabled = false;
      player.play(playState.lastOriginalNotes, {
        gain: 0.6,
        velocityScale: 0.14,
        onProgress: (t, total) => setProgress(total > 0 ? t / total : 0,
          `원곡 재생중 · ${t.toFixed(1)}s / ${total.toFixed(1)}s`),
        onEnd: () => {
          setProgress(1, '원곡 재생 완료');
          $('btnStopOriginal').disabled = true;
          log('원곡 재생 종료');
        },
      });
    } catch (e) {
      log(`원곡 재생 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  function onClickStopOriginal() {
    if (playState.origPlayer) playState.origPlayer.stop();
    $('btnStopOriginal').disabled = true;
    setProgress(0, '원곡 정지');
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
          saveEditState(ed);
        },
      });
      updateEditMeta(UI.editEditor);

      // hover tooltip
      const tt = $('hoverTooltip');
      const wrap = $('editCanvas').parentElement;
      attachHoverTooltip(UI.editEditor, tt, wrap, data);

      // 최초 로드 상태 메시지
      setStatus(
        `T=${T} · K=${K} · N=${data.notesMeta.num_notes} · exp B`,
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
      window.HibariUI = UI;
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
