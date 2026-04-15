/* ============================================================================
 * ui-bootstrap.js — Phase 2 scaffold 수준의 최소 UI 초기화
 *
 * 목적:
 *   - 데이터 로드 상태를 헤더에 표시
 *   - 참조 canvas에 overlap matrix를 단순 시각화 (Phase 3에서 풍부해질 예정)
 *   - 컨트롤 버튼은 placeholder로만 동작
 *
 * Phase 3부터 overlap-editor.js 가 canvas 상호작용을 인계받는다.
 * ========================================================================= */

(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const appStatus = () => $('appStatus');

  function log(msg, kind) {
    const area = $('logArea');
    if (!area) return;
    const time = new Date().toTimeString().slice(0, 8);
    const prefix = kind ? `[${kind}] ` : '';
    area.textContent += `${time} ${prefix}${msg}\n`;
    area.scrollTop = area.scrollHeight;
  }

  function setStatus(text, kind) {
    const el = appStatus();
    if (!el) return;
    el.textContent = text;
    el.classList.remove('status-ok', 'status-err');
    if (kind === 'ok') el.classList.add('status-ok');
    if (kind === 'err') el.classList.add('status-err');
  }

  // ── 간단한 overlap → canvas 렌더 (Phase 3에서 재작성 예정) ────────────
  function renderOverlapSimple(canvas, overlap, highlightDiff) {
    const ctx = canvas.getContext('2d');
    const { T, K, values } = overlap;

    // 캔버스 내부 해상도 = T × K (픽셀 1개 = 셀 1개)
    canvas.width = T;
    canvas.height = K;

    // 배경
    ctx.fillStyle = '#0A0A1C';
    ctx.fillRect(0, 0, T, K);

    // ImageData로 고속 픽셀 채우기
    const img = ctx.createImageData(T, K);
    for (let t = 0; t < T; t++) {
      for (let c = 0; c < K; c++) {
        const on = values[t * K + c] > 0.5;
        // 시각적으로 cycle 0이 위쪽, cycle K-1이 아래쪽
        const px = c * T + t;
        const base = px * 4;
        if (on) {
          // cell-on (#4ADE80) with slight variance per cycle
          img.data[base] = 70;         // R
          img.data[base + 1] = 222;    // G
          img.data[base + 2] = 128;    // B
          img.data[base + 3] = 255;    // A
        } else {
          // cell-off (#1A1A2F)
          img.data[base] = 26;
          img.data[base + 1] = 26;
          img.data[base + 2] = 47;
          img.data[base + 3] = 255;
        }
      }
    }
    ctx.putImageData(img, 0, 0);

    // CSS로 2-dimensional 스케일 (크게)
    canvas.style.width = '100%';
    canvas.style.height = 'auto';
    canvas.style.maxHeight = '360px';
  }

  function updateMeta(overlapRef) {
    const { T, K, density } = overlapRef;
    $('refMeta').textContent = `T=${T} × K=${K}`;
    const pct = (density * 100).toFixed(2);
    $('editMeta').textContent = `density ${pct}%`;
  }

  // ── 버튼 placeholder ─────────────────────────────────────────────────
  function wirePlaceholders() {
    const handlers = [
      ['btnReset', () => log('[Phase 3] 초기화 — 아직 미구현')],
      ['btnRandom', () => log('[Phase 3] 랜덤 채움 — 아직 미구현')],
      ['btnClear', () => log('[Phase 3] 모두 지우기 — 아직 미구현')],
      ['btnGenerate', () => log('[Phase 4] 생성·재생 — 아직 미구현')],
      ['btnStop', () => log('정지 (대기 중)')],
      ['btnDownloadMidi', () => log('[Phase 4] MIDI 저장 — 아직 미구현')],
      ['btnPlayOriginal', () => log('[Phase 4] 원곡 재생 — 아직 미구현')],
      ['btnStopOriginal', () => log('정지 (대기 중)')],
      ['btnRandomSeed', () => {
        const seed = Math.floor(Math.random() * 99999);
        $('sliderSeed').value = seed;
        log(`seed = ${seed}`);
      }],
    ];
    for (const [id, fn] of handlers) {
      const el = $(id);
      if (el) el.addEventListener('click', fn);
    }

    // temperature slider 값 표시
    const sT = $('sliderTemp');
    const sTVal = $('sliderTempVal');
    if (sT && sTVal) {
      sT.addEventListener('input', () => {
        sTVal.textContent = parseFloat(sT.value).toFixed(1);
      });
    }

    // diff 토글 placeholder
    const diffToggle = $('toggleDiff');
    if (diffToggle) {
      diffToggle.addEventListener('change', () => {
        log(`diff 하이라이트 ${diffToggle.checked ? 'ON' : 'OFF'} (Phase 3)`);
      });
    }
  }

  // ── 부트스트랩 ───────────────────────────────────────────────────────
  function bootstrap() {
    wirePlaceholders();
    setStatus('데이터 로드 중…');

    if (!window.HibariData) {
      setStatus('data-loader 미초기화', 'err');
      log('HibariData 전역이 존재하지 않습니다', 'err');
      return;
    }

    window.HibariData.onReady((data) => {
      updateMeta(data.overlapRef);
      renderOverlapSimple($('refCanvas'), data.overlapRef);
      renderOverlapSimple($('editCanvas'), data.overlapRef);  // 초기값=참조 복사
      setStatus(
        `T=${data.overlapRef.T} · K=${data.overlapRef.K} · N=${data.notesMeta.num_notes} · ` +
        `exp B`,
        'ok'
      );
      log(`데이터 로드 완료 (manifest version ${data.manifest.version})`, 'OK');
      log(`overlap shape: T=${data.overlapRef.T}, K=${data.overlapRef.K}, density=${(data.overlapRef.density * 100).toFixed(2)}%`);
      log(`notes=${data.notesMeta.num_notes}, cycles=${data.cyclesMeta.num_cycles}`);

      // 콘솔 접근 힌트
      console.log(
        '%c[Hibari Dashboard] 데이터 접근:',
        'color:#4ADE80;font-weight:bold',
        '\nwindow.HibariData.overlapRef',
        '\nwindow.HibariData.overlapCont',
        '\nwindow.HibariData.notesMeta',
        '\nwindow.HibariData.cyclesMeta',
        '\nwindow.HibariData.ref2d(t, c)  / cont2d(t, c)'
      );
    });

    // 1.5초 후에도 로드 안 됐으면 오류 상태 갱신
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
