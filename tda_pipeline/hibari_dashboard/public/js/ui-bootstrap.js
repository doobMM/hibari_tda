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
  const STORAGE_VERSION = 2;

  // ── 곡 식별 (URL ?data 파라미터 기반) ────────────────────────────────
  // data-loader.js 가 HibariData.manifest.song 을 채우기 전이라도
  // URL 파라미터로 곡을 미리 판단해 localStorage 키를 분리한다.
  function currentSongFromUrl() {
    const p = new URLSearchParams(location.search).get('data') || '';
    return p.includes('solari') ? 'solari' : 'hibari';
  }

  // 로드 후 manifest.song 이 있으면 그쪽 우선 (혹시 URL 과 다를 때)
  function currentSong() {
    if (UI.data && UI.data.manifest && UI.data.manifest.song) {
      return UI.data.manifest.song;
    }
    return currentSongFromUrl();
  }

  // 곡별 localStorage 키 — T/K 불일치 깨짐 방지
  function makeStorageKey(base) {
    return `${base}_${currentSongFromUrl()}`;
  }

  const STORAGE_KEY = makeStorageKey('hibari_dashboard_edit_v2');

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
    const isCont = editor.displayMode === 'continuous';
    if (editor.displayMode === 'continuous') {
      $('editMeta').textContent =
        `평균 활성도 ${pct}% · 변경 ${diff}셀 (>5%p, ${diffPct}%)`;
    } else {
      $('editMeta').textContent =
        `density ${pct}% · diff ${diff} (${diffPct}%)`;
    }
    setText('metricMode', isCont ? '연속 OM' : '이진 OM');
    setText('metricDensity', isCont ? `평균 활성도 ${pct}%` : `density ${pct}%`);
    setText('metricDiff', diff > 0 ? `참조와 ${diff}셀 다름 (${diffPct}%)` : '참조와 동일');
    setText('workflowStatus', diff > 0 ? `편집됨 · ${diff}셀 변경` : '참조와 같은 상태입니다');
    setText('actionSummary', diff > 0 ? '변경된 OM으로 생성할 수 있습니다' : 'OM을 편집하거나 바로 생성하세요');
    const diffPill = $('metricDiff');
    if (diffPill) diffPill.classList.toggle('status-pill--changed', diff > 0);
  }

  function updateRefMeta(editor) {
    $('refMeta').textContent = `T=${editor.T} × K=${editor.K}`;
  }

  function setText(id, text) {
    const el = $(id);
    if (el) el.textContent = text;
  }

  function setWorkflowStage(stage) {
    const current = Math.max(1, Math.min(3, stage | 0));
    document.querySelectorAll('.workflow-step[data-stage]').forEach((el) => {
      const n = parseInt(el.dataset.stage, 10);
      el.classList.toggle('is-active', n === current);
      el.classList.toggle('is-complete', n < current);
    });
  }

  function syncActionButtons() {
    const hasGenerated = !!(typeof playState !== 'undefined' && playState.lastGenerated);
    const tonnetz = $('actionTonnetz');
    const download = $('actionDownload');
    if (tonnetz) tonnetz.disabled = !hasGenerated;
    if (download) download.disabled = !hasGenerated;
    if (hasGenerated) {
      setWorkflowStage(2);
      setText('workflowStatus', '음악 생성 완료 · Tonnetz 확인 가능');
      setText('actionSummary', '생성 완료 · Tonnetz에서 확인하세요');
    }
  }

  function invalidateGeneratedOnEdit() {
    if (typeof playState === 'undefined' || !playState.lastGenerated) return;
    playState.lastGenerated = null;
    const mainTonnetz = $('btnPlayInTonnetz');
    const mainDownload = $('btnDownloadMidi');
    const mainPlay = $('btnPlayLocal');
    if (mainTonnetz) mainTonnetz.disabled = true;
    if (mainDownload) mainDownload.disabled = true;
    if (mainPlay) mainPlay.disabled = true;
    syncActionButtons();
    setWorkflowStage(1);
    setText('actionSummary', 'OM이 바뀌었습니다 · 다시 생성하세요');
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
    // 편집이 전혀 없으면 배너 숨김 (참조와 같음)
    if (editor.diffCount() === 0 && s.score < 1e-4) {
      banner.classList.add('ood-hidden');
      return;
    }
    if (s.level === 'warn') banner.classList.add('level-warn');
    if (s.level === 'danger') banner.classList.add('level-danger');

    // JSD ∈ [0,1] (log2 base 정의상 최댓값 1) → score × 100 = OOD %.
    // 직관성 우선 — 사람들이 "분포 차이 12%" 같은 표현을 더 쉽게 받아들임.
    scoreEl.textContent = `OOD ${(s.score * 100).toFixed(1)}%`;
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

  // ── 사진 → 연속 OM (아이디어 B) ───────────────────────────────────────
  // photoState 는 세션 간 유지되지 않음 (localStorage 미사용 의도).
  // 사용자가 새로고침하면 hibari 원본으로 복귀.
  const photoState = {
    name: null,           // 파일명
    thumbDataUrl: null,   // 재적용 시 썸네일 재표시용
    baseOM: null,         // Float32Array(K*T) — γ=1.0 기준 (정규화+반전 끝난 상태)
    hibariBackup: null,   // {T, K, values, mean, ...} — 첫 활성화 시 원본 백업
    T: 0, K: 0,
    lastGamma: 1.0,
    targetMean: 0,        // hibari 연속 OM 평균 (자동 γ 탐색 목표)
    active: false,        // 현재 사진 OM 적용 중인지 (false=hibari 원본)
  };

  function updatePhotoButtonStates() {
    const btn = $('btnPhotoToggle');
    if (!btn) return;
    const hasPhoto = !!photoState.baseOM;
    btn.hidden = !hasPhoto;
    if (photoState.active) {
      btn.textContent = 'hibari 로 되돌리기';
      btn.dataset.state = 'active';
    } else {
      btn.textContent = '사진 다시 적용';
      btn.dataset.state = 'reverted';
    }
  }

  // 이미지 → grayscale luminance Float32Array(h*w), 값 [0,1]
  // bilinear resize 는 canvas drawImage 로 수행 (고해상도 원본 → (T, K))
  async function imageToLuminance(file, T, K) {
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.decoding = 'async';
      await new Promise((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => {
          const isHeic = /\.(heic|heif)$/i.test(file.name || '') ||
                         /heic|heif/i.test(file.type || '');
          reject(new Error(
            isHeic
              ? 'HEIC/HEIF 포맷은 현재 브라우저(Chrome/Firefox)에서 디코딩 불가. JPG/PNG/WEBP 로 변환해 주세요. (Safari 는 지원)'
              : '이미지 디코딩 실패 — 손상되었거나 지원되지 않는 포맷입니다.'
          ));
        };
        img.src = url;
      });
      // (T, K) 해상도로 캔버스 리샘플 — 브라우저 기본 bilinear
      const c = document.createElement('canvas');
      c.width = T; c.height = K;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, 0, 0, T, K);
      const imgData = ctx.getImageData(0, 0, T, K);
      const px = imgData.data;
      const lum = new Float32Array(T * K);
      // row-major (y, x) → flat
      for (let i = 0; i < T * K; i++) {
        const r = px[4*i], g = px[4*i+1], b = px[4*i+2];
        // Rec. 601 luminance
        lum[i] = (0.299*r + 0.587*g + 0.114*b) / 255.0;
      }
      // 원본 비율 유지 썸네일 — 가로 480 기준으로 축소 (OM 과 시각 비교용)
      const thumbW = Math.min(480, img.naturalWidth || img.width || 480);
      const thumbH = Math.round(
        thumbW * (img.naturalHeight || img.height || 1) /
                 (img.naturalWidth  || img.width  || 1)
      );
      const tc = document.createElement('canvas');
      tc.width = thumbW; tc.height = thumbH;
      const tctx = tc.getContext('2d');
      tctx.imageSmoothingEnabled = true;
      tctx.imageSmoothingQuality = 'high';
      tctx.drawImage(img, 0, 0, thumbW, thumbH);
      return { lum, thumbDataUrl: tc.toDataURL('image/jpeg', 0.85) };
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  // percentile 기반 stretch → 반전 → [0,1] continuous OM (γ=1.0 기준)
  // input lum 레이아웃: (K rows, T cols) flat row-major
  // 출력은 원 데이터 레이아웃(T*K, t-major)과 일치시킴: values[t*K + c]
  function buildBaseOM(lum, T, K) {
    // percentile 5, 95 — 약간의 대비 확장
    const sorted = Float32Array.from(lum).sort();
    const lo = sorted[Math.floor(0.05 * sorted.length)];
    const hi = sorted[Math.floor(0.95 * sorted.length)];
    const denom = Math.max(1e-6, hi - lo);
    // (K, T) row-major → (T, K) — canvas 는 (row=K, col=T) 라 루프 재배열
    const out = new Float32Array(T * K);
    for (let k = 0; k < K; k++) {
      for (let t = 0; t < T; t++) {
        const v = (lum[k * T + t] - lo) / denom;
        const clamped = v < 0 ? 0 : (v > 1 ? 1 : v);
        // 반전: 어두운 픽셀 → 높은 활성도
        out[t * K + k] = 1.0 - clamped;
      }
    }
    return out;
  }

  function meanOf(arr) {
    let s = 0;
    for (let i = 0; i < arr.length; i++) s += arr[i];
    return s / arr.length;
  }

  // γ 적용: out[i] = base[i]^γ (0<γ<∞). γ=1 이면 identity.
  function applyGammaArray(base, gamma) {
    const out = new Float32Array(base.length);
    const g = Math.max(0.05, gamma);
    for (let i = 0; i < base.length; i++) {
      out[i] = Math.pow(base[i], g);
    }
    return out;
  }

  // baseOM 에 대해 mean(baseOM^γ) ≈ target 이 되는 γ 를 이분탐색
  function findGammaForMean(base, target) {
    if (!base || !base.length) return 1.0;
    const curMean = meanOf(base);
    // target 보다 이미 낮으면 γ<1 로 밝게. 둘이 거의 같으면 1.
    if (Math.abs(curMean - target) < 1e-4) return 1.0;
    let lo = 0.1, hi = 10.0;
    for (let i = 0; i < 40; i++) {
      const mid = 0.5 * (lo + hi);
      const m = meanOf(applyGammaArray(base, mid));
      if (m > target) lo = mid; else hi = mid;
    }
    return +(0.5 * (lo + hi)).toFixed(3);
  }

  function updatePhotoStatsUi() {
    const st = $('photoStats');
    if (!st) return;
    const baseMean = photoState.baseOM ? meanOf(photoState.baseOM) : 0;
    const finalArr = photoState.baseOM ? applyGammaArray(photoState.baseOM, photoState.lastGamma) : null;
    const finalMean = finalArr ? meanOf(finalArr) : 0;
    const hibariMean = photoState.targetMean || 0;
    st.textContent =
      `원 사진 평균 ${baseMean.toFixed(3)} · γ 적용 후 ${finalMean.toFixed(3)}` +
      (hibariMean ? ` · hibari ${hibariMean.toFixed(3)}` : '');
  }

  // UI.data.overlapCont 를 교체하고 스택을 재적용
  function injectPhotoAsContinuousOM() {
    if (!photoState.baseOM || !UI.data) return;
    const gamma = photoState.lastGamma;
    const values = applyGammaArray(photoState.baseOM, gamma);
    UI.data.overlapCont = {
      T: photoState.T,
      K: photoState.K,
      values,
      description: 'photo-derived continuous OM',
      mean: meanOf(values),
      density: null, min: 0, max: 1,
      best_taus: null, exp_config: null,
    };
    // 연속 모드 강제 + Algo2 전환
    if (UI.stackMode !== 'continuous') {
      setStackMode && setStackMode('continuous');
    } else {
      // 동일 모드여도 값이 바뀌었으므로 재계산
      if (typeof recomputeStackToEditor === 'function') recomputeStackToEditor();
    }
    // 참조 표시도 연속으로
    if (UI.refViewMode !== 'continuous' && typeof setRefViewMode === 'function') {
      setRefViewMode('continuous');
    } else {
      rerenderReferenceContinuous();
    }
    // 알고리즘 자동 전환
    const algo2Radio = document.querySelector('input[name="algo"][value="algo2"]');
    if (algo2Radio && !algo2Radio.checked) {
      algo2Radio.checked = true;
      algo2Radio.dispatchEvent(new Event('change', { bubbles: true }));
    }
    photoState.active = true;
    // 참조 OM 위 사진 배너 — viewport 와 상관없이 OM 과 동일 폭으로 stretch
    const bannerImg = $('refPhotoBannerImg');
    const banner = $('refPhotoBanner');
    if (bannerImg && banner && photoState.thumbDataUrl) {
      bannerImg.src = photoState.thumbDataUrl;
      banner.hidden = false;
    }
    updatePhotoStatsUi();
    updatePhotoButtonStates();
  }

  // 참조 캔버스의 연속 뷰 재렌더 (overlapCont 값 교체 후 반영)
  function rerenderReferenceContinuous() {
    if (!UI.refEditor || !UI.data || !UI.data.overlapCont) return;
    try {
      UI.refEditor.setDisplayMode && UI.refEditor.setDisplayMode('continuous', {
        reference: UI.data.overlapCont.values,
        values: UI.data.overlapCont.values,
      });
    } catch (e) { /* no-op */ }
    if (typeof recomputeStackToEditor === 'function') recomputeStackToEditor();
  }

  async function onPhotoPicked(file) {
    if (!file || !UI.data) return;
    try {
      if (!photoState.hibariBackup) {
        // 첫 업로드 시 원본 백업 (얕은 복사로 충분 — values 는 공유 읽기 전용)
        photoState.hibariBackup = Object.assign({}, UI.data.overlapCont);
        photoState.targetMean = (UI.data.overlapCont && UI.data.overlapCont.mean)
          ? UI.data.overlapCont.mean
          : meanOf(UI.data.overlapCont.values);
      }
      const T = UI.data.overlapCont.T;
      const K = UI.data.overlapCont.K;
      photoState.T = T; photoState.K = K;
      photoState.name = file.name || '사진';

      log(`사진 디코딩 중 (${file.name}, ${(file.size/1024).toFixed(1)} KB)…`);
      const { lum, thumbDataUrl } = await imageToLuminance(file, T, K);
      photoState.baseOM = buildBaseOM(lum, T, K);
      photoState.thumbDataUrl = thumbDataUrl;

      // 자동 γ 추천
      const autoGamma = findGammaForMean(photoState.baseOM, photoState.targetMean);
      photoState.lastGamma = autoGamma;

      // UI 반영
      $('photoPanel').hidden = false;
      $('photoThumb').src = thumbDataUrl;
      $('photoName').textContent = file.name;
      const gs = $('sliderGamma');
      const gv = $('sliderGammaVal');
      gs.value = String(autoGamma);
      gv.textContent = autoGamma.toFixed(2);

      injectPhotoAsContinuousOM();
      log(`사진 → 연속 OM 변환 완료 (${T}×${K}, 자동 γ=${autoGamma.toFixed(2)})`, 'OK');
    } catch (e) {
      log(`사진 변환 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  function revertPhoto() {
    if (!photoState.hibariBackup || !UI.data) return;
    UI.data.overlapCont = photoState.hibariBackup;
    photoState.active = false;
    // 패널은 유지 — baseOM 메모리에 있으므로 "사진 다시 적용" 로 복귀 가능
    const banner = $('refPhotoBanner');
    if (banner) banner.hidden = true;
    rerenderReferenceContinuous();
    if (typeof recomputeStackToEditor === 'function') recomputeStackToEditor();
    updatePhotoStatsUi();
    updatePhotoButtonStates();
    log('hibari 원본 연속 OM 으로 복귀했습니다. (사진은 메모리에 남아 있음 — "사진 다시 적용" 가능)');
  }

  function reapplyPhoto() {
    if (!photoState.baseOM) {
      log('재적용할 사진이 없습니다. 먼저 사진을 선택하세요.', 'WARN');
      return;
    }
    injectPhotoAsContinuousOM();
    log(`사진 OM 재적용 (γ=${photoState.lastGamma.toFixed(2)})`, 'OK');
  }

  function wirePhotoControls() {
    const btnPick = $('btnPhotoPick');
    const fileInput = $('photoInput');
    if (!btnPick || !fileInput) return;
    btnPick.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      const f = e.target.files && e.target.files[0];
      if (f) onPhotoPicked(f);
      fileInput.value = ''; // 같은 파일 재선택 허용
    });

    const gs = $('sliderGamma');
    const gv = $('sliderGammaVal');
    if (gs && gv) {
      gs.addEventListener('input', () => {
        const g = parseFloat(gs.value);
        gv.textContent = g.toFixed(2);
        photoState.lastGamma = g;
        if (photoState.baseOM) injectPhotoAsContinuousOM();
      });
    }

    const btnAuto = $('btnPhotoAutoGamma');
    if (btnAuto) {
      btnAuto.addEventListener('click', () => {
        if (!photoState.baseOM) return;
        const g = findGammaForMean(photoState.baseOM, photoState.targetMean);
        photoState.lastGamma = g;
        gs.value = String(g);
        gv.textContent = g.toFixed(2);
        injectPhotoAsContinuousOM();
        log(`자동 γ=${g.toFixed(2)} 재적용 (hibari 평균 ${photoState.targetMean.toFixed(3)} 기준)`);
      });
    }

    const btnToggle = $('btnPhotoToggle');
    if (btnToggle) {
      btnToggle.addEventListener('click', () => {
        if (photoState.active) revertPhoto();
        else reapplyPhoto();
      });
    }

    // 참조 canvas 의 rendered 높이를 배너에 동기화 — OM 과 동일 폭·높이로 stretch 되어 육안 비교 가능
    wirePhotoBannerHeightSync();
  }

  function wirePhotoBannerHeightSync() {
    const banner = $('refPhotoBanner');
    const wrap = $('refCanvasWrap');
    if (!banner || !wrap) return;
    const getActiveCanvas = () => {
      const cont = document.getElementById('refCanvasCont');
      const bin  = document.getElementById('refCanvas');
      if (cont && !cont.hidden) return cont;
      return bin;
    };
    const sync = () => {
      const c = getActiveCanvas();
      if (!c) return;
      const h = c.clientHeight;
      if (h > 0) banner.style.setProperty('--photo-banner-h', h + 'px');
    };
    sync();
    // canvas 크기 변화 추적
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(sync);
      const cont = document.getElementById('refCanvasCont');
      const bin  = document.getElementById('refCanvas');
      if (cont) ro.observe(cont);
      if (bin)  ro.observe(bin);
    }
    window.addEventListener('resize', sync);
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

    // ── 변형 스택 컨트롤 배선 (Q1) ────────────────────────────────────
    wireStackControls();
    wireRefViewModeControls();
    wireAlgoRouting();
    wireHelpModal();
    wirePhotoControls();

    function setDiffVisible(visible) {
      if (!UI.editEditor) return;
      UI.editEditor.setDiffMode(visible);
      const quick = $('btnQuickDiff');
      if (quick) {
        quick.setAttribute('aria-pressed', visible ? 'true' : 'false');
        quick.textContent = visible ? 'diff 끄기' : 'diff 보기';
      }
      log(`diff 하이라이트 ${visible ? 'ON' : 'OFF'}`);
    }

    const quickDiff = $('btnQuickDiff');
    if (quickDiff) {
      quickDiff.addEventListener('click', () => {
        const next = quickDiff.getAttribute('aria-pressed') !== 'true';
        setDiffVisible(next);
      });
    }

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
    const btnPlayTonnetz = $('btnPlayInTonnetz');
    if (btnPlayTonnetz) btnPlayTonnetz.addEventListener('click', onClickPlayInTonnetz);

    // 30초 세그먼트 + 인페이지 재생 + 라이브 모드 + 품질 맵 + 구조 탐험
    wireSegmentControls();
    wireLiveMode();
    wireQualityMap();
    wireVaePanel();
    const btnPlayLocal = $('btnPlayLocal');
    if (btnPlayLocal) btnPlayLocal.addEventListener('click', playLastGenerated);
    const btnStopLocal = $('btnStopLocal');
    if (btnStopLocal) btnStopLocal.addEventListener('click', stopLocalPlayback);

    const actionGenerate = $('actionGenerate');
    if (actionGenerate) actionGenerate.addEventListener('click', onClickGenerate);
    const actionTonnetz = $('actionTonnetz');
    if (actionTonnetz) actionTonnetz.addEventListener('click', onClickPlayInTonnetz);
    const actionDownload = $('actionDownload');
    if (actionDownload) actionDownload.addEventListener('click', onClickDownloadMidi);
    syncActionButtons();
  }

  // ── 변형 스택 (Q1) ────────────────────────────────────────────
  // 스택 상태: [{id, kind, params, enabled}, ...]
  // 첫 변형은 reference 입력 → 출력. 다음 변형은 이전 출력 → 다시 출력.
  // localStorage 에 stack 자체를 저장 (참조와 함께 deterministic 재생성 가능).

  // 곡 전환 시 T/K 불일치 방지: 스택도 곡별 키 사용
  const STACK_STORAGE_KEY = makeStorageKey('hibari_dashboard_stack_v1');

  UI.stack = [];
  UI.stackNextId = 1;
  UI.refViewMode = 'binary';   // binary | continuous
  UI.stackMode  = 'binary';    // binary | continuous — 알고리즘 라디오와 동기화 (algo1=binary, algo2=continuous)

  function saveStackState() {
    try {
      const blob = { v: 1, stack: UI.stack, savedAt: new Date().toISOString() };
      localStorage.setItem(STACK_STORAGE_KEY, JSON.stringify(blob));
    } catch (e) { console.warn('[saveStackState] 실패', e); }
  }
  function loadStackState() {
    try {
      const raw = localStorage.getItem(STACK_STORAGE_KEY);
      if (!raw) return null;
      const blob = JSON.parse(raw);
      if (!Array.isArray(blob.stack)) return null;
      return blob.stack;
    } catch (e) { return null; }
  }
  function clearStackState() {
    try { localStorage.removeItem(STACK_STORAGE_KEY); } catch (e) {}
  }

  function nextStepId() {
    const id = `s${UI.stackNextId++}`;
    return id;
  }

  function addStackStep(kind) {
    const T = window.OverlapTransforms;
    if (!T || !T.SCHEMA[kind]) return;
    const params = T.defaultParams(kind);
    // boost: 현재 선택된 cycle 을 default 로 사용 (사용자 의도 추정)
    if (kind === 'boost' && playState.selectedCycleIdx != null) {
      params.cycleIdx = playState.selectedCycleIdx;
    }
    const step = {
      id: nextStepId(),
      kind,
      params,
      enabled: true,
    };
    UI.stack.push(step);
    onStackChanged(`+ ${T.KINDS[kind]} 추가`);
  }
  function removeStackStep(id) {
    const i = UI.stack.findIndex(s => s.id === id);
    if (i < 0) return;
    const removed = UI.stack.splice(i, 1)[0];
    onStackChanged(`− ${window.OverlapTransforms.KINDS[removed.kind]} 제거`);
  }
  function moveStackStep(id, dir) {
    const i = UI.stack.findIndex(s => s.id === id);
    if (i < 0) return;
    const j = i + dir;
    if (j < 0 || j >= UI.stack.length) return;
    const [s] = UI.stack.splice(i, 1);
    UI.stack.splice(j, 0, s);
    onStackChanged(`${dir > 0 ? '↓' : '↑'} 순서 변경`);
  }
  function toggleStackStep(id) {
    const s = UI.stack.find(s => s.id === id);
    if (!s) return;
    s.enabled = !s.enabled;
    onStackChanged(`${s.enabled ? '◉' : '◯'} ${window.OverlapTransforms.KINDS[s.kind]}`);
  }
  // 설명 토글: UI 상태 (recompute 불필요, 변형 결과 불변).
  function toggleStackInfo(id) {
    const s = UI.stack.find(s => s.id === id);
    if (!s) return;
    s.uiOpen = !s.uiOpen;
    renderStackList();
  }
  function updateStackParam(id, key, value) {
    const s = UI.stack.find(s => s.id === id);
    if (!s) return;
    s.params[key] = value;
    onStackChanged(null, /*silent=*/true);
  }
  function clearStack() {
    if (UI.stack.length === 0) return;
    UI.stack = [];
    onStackChanged('스택 비움 (참조로 복귀)');
  }

  function onStackChanged(logMsg, silent) {
    saveStackState();
    renderStackList();
    recomputeStackToEditor();
    if (logMsg && !silent) log(logMsg);
  }

  function recomputeStackToEditor() {
    if (!UI.editEditor || !UI.data) return;
    const mode = UI.stackMode;
    const refSrc = mode === 'continuous' ? UI.data.overlapCont : UI.data.overlapRef;
    if (!refSrc || !refSrc.values) {
      log(`연속 OM 데이터 없음 — 이진으로 폴백`, 'WARN');
      UI.stackMode = 'binary';
      const ref = UI.data.overlapRef.values;
      const T = UI.editEditor.T, K = UI.editEditor.K;
      UI.editEditor.setDisplayMode('binary', {
        reference: ref,
        values: window.OverlapTransforms.apply(UI.stack, ref, T, K, 'binary'),
      });
      return;
    }
    const ref = refSrc.values;
    const T = UI.editEditor.T, K = UI.editEditor.K;
    const out = window.OverlapTransforms.apply(UI.stack, ref, T, K, mode);
    // displayMode 가 다르면 reference + values 교체, 같으면 setMatrix 만
    if (UI.editEditor.displayMode !== mode) {
      UI.editEditor.setDisplayMode(mode, { reference: ref, values: out });
    } else {
      UI.editEditor.setReference(ref);
      UI.editEditor.setMatrix(out);
    }
  }

  // ── 스택 카드 DOM 렌더 ───────────────────────────────────────
  function renderStackList() {
    const list = $('stackList');
    if (!list) return;
    const T = window.OverlapTransforms;
    list.innerHTML = '';
    if (UI.stack.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'stack-empty hint';
      empty.textContent = '스택이 비어 있습니다 — 편집 OM = 참조 OM. 아래에서 변형을 추가하세요.';
      list.appendChild(empty);
      return;
    }
    UI.stack.forEach((step, idx) => {
      const card = document.createElement('div');
      card.className = `stack-card${step.enabled ? '' : ' is-disabled'}`;
      card.dataset.id = step.id;

      // header
      const head = document.createElement('div');
      head.className = 'stack-card__head';
      const isOpen = !!step.uiOpen;
      head.innerHTML = `
        <span class="stack-card__order">${idx + 1}</span>
        <span class="stack-card__name">${T.KINDS[step.kind] || step.kind}</span>
        <button class="stack-card__btn stack-card__btn--info${isOpen ? ' is-active' : ''}" data-act="info" title="${isOpen ? '설명 접기' : '설명 펼치기'}" aria-expanded="${isOpen ? 'true' : 'false'}" aria-label="설명 토글">?</button>
        <button class="stack-card__btn" data-act="up"     title="위로 이동" aria-label="위로 이동">▲</button>
        <button class="stack-card__btn" data-act="down"   title="아래로 이동" aria-label="아래로 이동">▼</button>
        <button class="stack-card__btn" data-act="toggle" title="${step.enabled ? '끄기' : '켜기'}" aria-label="활성/비활성">${step.enabled ? '◉' : '◯'}</button>
        <button class="stack-card__btn stack-card__btn--del" data-act="del" title="제거" aria-label="제거">×</button>
      `;
      card.appendChild(head);

      // description (접힘 가능 — 기본 접힘)
      if (isOpen) {
        const desc = document.createElement('p');
        desc.className = 'stack-card__desc hint';
        desc.textContent = T.DESCRIPTIONS[step.kind] || '';
        card.appendChild(desc);
      }

      // params
      const schema = T.SCHEMA[step.kind] || [];
      schema.forEach(p => {
        const row = document.createElement('div');
        row.className = 'stack-card__param';
        const label = document.createElement('label');
        label.className = 'stack-card__param-label';
        label.textContent = p.label;
        row.appendChild(label);

        if (p.kind === 'slider' || p.kind === 'sliderAuto') {
          const isAuto = p.kind === 'sliderAuto' && step.params[p.key] === 'auto';
          const wrap = document.createElement('div');
          wrap.className = 'stack-card__param-input';
          // 직접 입력 number 필드 (슬라이더 제거 — 정밀 입력 우선)
          const num = document.createElement('input');
          num.type = 'number';
          num.className = 'stack-card__param-num';
          num.min = p.min; num.max = p.max; num.step = p.step;
          const fallback = (p.default === 'auto')
            ? (UI.data?.overlapRef.density ?? 0.3)
            : p.default;
          const initVal = isAuto ? fallback : (step.params[p.key] ?? fallback);
          num.value = isAuto ? '' : Number(initVal).toFixed(2);
          num.placeholder = isAuto ? 'auto' : '';
          num.disabled = isAuto;
          // number 직접 입력 → clamp + 저장
          const commitNum = () => {
            let v = parseFloat(num.value);
            if (Number.isNaN(v)) return;
            if (v < +p.min) v = +p.min;
            else if (v > +p.max) v = +p.max;
            num.value = v.toFixed(2);
            updateStackParam(step.id, p.key, v);
          };
          num.addEventListener('change', commitNum);
          num.addEventListener('blur', commitNum);
          wrap.appendChild(num);
          if (p.kind === 'sliderAuto') {
            const autoBtn = document.createElement('button');
            autoBtn.type = 'button';
            autoBtn.className = `stack-card__auto-btn${isAuto ? ' is-active' : ''}`;
            autoBtn.textContent = 'auto';
            autoBtn.addEventListener('click', () => {
              const cur = step.params[p.key];
              const goAuto = cur !== 'auto';
              const numVal = parseFloat(num.value);
              const restoreVal = Number.isFinite(numVal) ? numVal : (p.default === 'auto' ? 0.3 : p.default);
              updateStackParam(step.id, p.key, goAuto ? 'auto' : restoreVal);
              renderStackList();
            });
            wrap.appendChild(autoBtn);
          }
          row.appendChild(wrap);
        } else if (p.kind === 'int') {
          const num = document.createElement('input');
          num.type = 'number';
          num.min = p.min; num.max = p.max; num.step = p.step;
          num.value = step.params[p.key];
          num.className = 'stack-card__num';
          num.addEventListener('input', () => {
            const v = parseInt(num.value, 10) || 0;
            updateStackParam(step.id, p.key, v);
          });
          row.appendChild(num);
        } else if (p.kind === 'seed') {
          const wrap = document.createElement('div');
          wrap.className = 'stack-card__param-input';
          const num = document.createElement('input');
          num.type = 'number';
          num.min = 0; num.max = 99999; num.step = 1;
          num.value = step.params[p.key];
          num.className = 'stack-card__num';
          num.addEventListener('input', () => {
            const v = parseInt(num.value, 10) || 0;
            updateStackParam(step.id, p.key, v);
          });
          const dice = document.createElement('button');
          dice.type = 'button';
          dice.className = 'stack-card__btn';
          dice.title = '무작위 seed';
          dice.textContent = '🎲';
          dice.addEventListener('click', () => {
            const v = Math.floor(Math.random() * 99999);
            num.value = v;
            updateStackParam(step.id, p.key, v);
          });
          wrap.appendChild(num);
          wrap.appendChild(dice);
          row.appendChild(wrap);
        }
        card.appendChild(row);
      });

      // 위임 핸들러: head 의 버튼들
      head.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const act = btn.dataset.act;
        if (act === 'up') moveStackStep(step.id, -1);
        else if (act === 'down') moveStackStep(step.id, +1);
        else if (act === 'toggle') toggleStackStep(step.id);
        else if (act === 'del') removeStackStep(step.id);
        else if (act === 'info') toggleStackInfo(step.id);
      });

      list.appendChild(card);
    });
  }

  function wireStackControls() {
    $('btnStackAdd').addEventListener('click', () => {
      const kind = $('stackAddKind').value;
      addStackStep(kind);
    });
    $('btnStackClear').addEventListener('click', () => {
      clearStack();
    });
  }

  // ── 참조 표시 모드 (binary / continuous) ──────────────────────
  // 알고리즘과 불일치하는 모드 버튼은 비활성화.
  //   algo1 → binary 입력 → continuous 버튼 disabled
  //   algo2 → binary/continuous 양쪽 허용
  function wireRefViewModeControls() {
    const btns = document.querySelectorAll('.matrix-card__viewmode-btn');
    btns.forEach(b => {
      b.addEventListener('click', () => {
        if (b.disabled) return;
        const mode = b.dataset.refmode;
        if (mode) setRefViewMode(mode);
      });
    });
  }
  function setRefViewMode(mode) {
    if (mode !== 'binary' && mode !== 'continuous') return;
    UI.refViewMode = mode;
    document.querySelectorAll('.matrix-card__viewmode-btn').forEach(b => {
      const active = b.dataset.refmode === mode;
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    const wrap = $('refCanvasWrap');
    if (wrap) wrap.dataset.mode = mode;
    const refC = $('refCanvas');
    const contC = $('refCanvasCont');
    const contLegend = $('contLegend');
    if (refC && contC) {
      refC.hidden = (mode === 'continuous');
      contC.hidden = (mode === 'binary');
      if (mode === 'continuous') renderContinuousReference();
    }
    if (contLegend) contLegend.hidden = (mode === 'binary');
    if (UI.refEditor) UI.refEditor.render();
    // stackMode 동기화 (same-mode early return)
    setStackMode(mode);
  }

  function _currentAlgo() {
    return document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
  }
  function applyViewModeButtonDisabled() {
    // Algo1 은 이진 입력만 받으므로 'continuous' 버튼 disable.
    // Algo2 는 binary/continuous 모두 허용 (재현성 위해 — 기존 mid 파일 재생성 가능).
    const algo = _currentAlgo();
    document.querySelectorAll('.matrix-card__viewmode-btn').forEach(b => {
      const m = b.dataset.refmode;
      const disabled = (algo === 'algo1' && m === 'continuous');
      b.disabled = disabled;
      b.classList.toggle('is-disabled', disabled);
      if (disabled) {
        b.title = 'Algorithm 1 은 이진 OM 만 입력으로 받습니다';
      } else {
        b.removeAttribute('title');
      }
    });
  }

  // ── 알고리즘 ↔ 모드 자동 라우팅 ────────────────────────────────
  // Algorithm 1 → 이진 입력 (편집 OM = binary, ref 표시 = binary)
  // Algorithm 2 → 연속 입력 (편집 OM = continuous, ref 표시 = continuous)
  function wireAlgoRouting() {
    document.querySelectorAll('input[name="algo"]').forEach(r => {
      r.addEventListener('change', () => {
        const algo = document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
        const newMode = algo === 'algo2' ? 'continuous' : 'binary';
        setStackMode(newMode);
      });
    });
  }
  function setStackMode(mode) {
    if (mode !== 'binary' && mode !== 'continuous') return;
    if (UI.stackMode === mode) return;
    UI.stackMode = mode;
    applyViewModeButtonDisabled();
    if (UI.refViewMode !== mode) setRefViewMode(mode);
    updateModeBadge();
    // OOD detector 를 새 모드 참조로 재초기화 (JSD 는 reference 분포가 바뀌면 재계산 필요)
    if (window.OODDetector && UI.data) {
      const refSrc = mode === 'continuous' ? UI.data.overlapCont : UI.data.overlapRef;
      if (refSrc && refSrc.values) {
        UI.ood = new window.OODDetector({
          reference: refSrc.values,
          T: refSrc.T, K: refSrc.K,
          cycles: UI.data.cyclesMeta.cycles,
        });
      }
    }
    recomputeStackToEditor();
    log(`입력 모드: ${mode === 'binary' ? '이진 OM' : '연속 OM'}`);
  }

  function updateModeBadge() {
    const badge = $('stackModeBadge');
    if (!badge) return;
    badge.textContent = UI.stackMode === 'continuous' ? '연속 OM 입력' : '이진 OM 입력';
    badge.dataset.mode = UI.stackMode;
    const algoHint = $('algoInputHint');
    if (algoHint) {
      algoHint.textContent = UI.stackMode === 'continuous'
        ? '입력: 연속 OM (학습 분포)'
        : '입력: 이진 OM (τ=0.7)';
    }
  }

  function renderContinuousReference() {
    if (!UI.data) return;
    const cont = UI.data.overlapCont;
    if (!cont || !cont.values) return;
    const canvas = $('refCanvasCont');
    if (!canvas) return;
    const T = cont.T, K = cont.K;
    // 캔버스 사이즈 = 형제 binary canvas 와 동일하게 맞춤
    const sibling = $('refCanvas');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cssW = sibling ? parseFloat(sibling.style.width) || sibling.clientWidth || 700 : 700;
    const cssH = sibling ? parseFloat(sibling.style.height) || sibling.clientHeight || 360 : 360;
    canvas.style.width = cssW + 'px';
    canvas.style.height = cssH + 'px';
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // 배경
    const bgVar = getComputedStyle(document.documentElement).getPropertyValue('--surface-canvas').trim() || '#0A0A1C';
    ctx.fillStyle = bgVar;
    ctx.fillRect(0, 0, cssW, cssH);
    // 셀 크기 — Editor 와 동일 패딩 10
    const inner_w = cssW - 20;
    const inner_h = cssH - 20;
    const cellW = inner_w / T;
    const cellH = inner_h / K;
    const ox = 10, oy = 10;
    // 색조: 다크 테마면 지속도 → 초록 가까움, 라이트는 청록. 단순화: HSL hue=160 채도 80%, lightness=20→70% 로 매핑
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const baseL = isDark ? 12 : 95;
    const peakL = isDark ? 60 : 35;
    for (let t = 0; t < T; t++) {
      for (let c = 0; c < K; c++) {
        const v = cont.values[t * K + c];
        const clamped = Math.max(0, Math.min(1, v));
        const L = baseL + (peakL - baseL) * clamped;
        // hue 약간 이동: 작은 값 → 푸르스름, 큰 값 → 초록
        const H = 200 - 40 * clamped;
        ctx.fillStyle = `hsl(${H}, 70%, ${L}%)`;
        ctx.fillRect(ox + t * cellW, oy + c * cellH, Math.ceil(cellW), Math.ceil(cellH));
      }
    }
  }

  // ── 도움말 모달 (Q2-b) ────────────────────────────────────────
  function wireHelpModal() {
    const open = $('btnStackHelp');
    const close = $('btnHelpClose');
    const modal = $('helpModal');
    if (!open || !modal) return;
    open.addEventListener('click', () => { modal.hidden = false; });
    if (close) close.addEventListener('click', () => { modal.hidden = true; });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.hidden = true;
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modal.hidden) modal.hidden = true;
    });
  }

  // ── Phase 4: 생성·재생 로직 ─────────────────────────────────────────
  const BAR_STEPS = 32;         // 한 마디 = 32개 8분음표

  const playState = {
    lastGenerated: null,
    genPlayer: null,
    previewPlayer: null,    // cycle 미리듣기 전용 PianoPlayer (생성과 분리)
    previewTimer: null,
    bpm: 60,
    fcGen: null,            // FCGenerator 인스턴스 (hibari)
    fcLoaded: false,
    transGen: null,         // TransformerGenerator 인스턴스 (solari)
    transLoaded: false,
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

  // note → cycle 역방향 조회 패널
  function populateNoteLookup() {
    const sel = $('noteLookupInput');
    const result = $('noteLookupResult');
    const pitchEl = $('noteLookupPitch');
    if (!sel || !result || !UI.data) return;
    const labels = UI.data.notesMeta?.labels || [];
    sel.innerHTML = '';
    labels.forEach(l => {
      const opt = document.createElement('option');
      opt.value = String(l.label);
      opt.textContent = `#${l.label} · ${pitchName(l.pitch)} (dur ${l.dur})`;
      sel.appendChild(opt);
    });
    const render = () => {
      const lab = parseInt(sel.value, 10);
      const meta = labels.find(l => l.label === lab);
      pitchEl.textContent = meta ? `pitch ${pitchName(meta.pitch)} · ${meta.count}회` : '';
      const cycles = UI.data.cyclesMeta?.cycles || [];
      const hits = [];
      cycles.forEach((cy, idx) => {
        const arr = cy.note_labels_1idx || [];
        if (arr.includes(lab)) hits.push(idx);
      });
      result.innerHTML = '';
      if (hits.length === 0) {
        const empty = document.createElement('span');
        empty.className = 'note-lookup__empty';
        empty.textContent = '(이 note 를 포함한 cycle 없음)';
        result.appendChild(empty);
        return;
      }
      const head = document.createElement('span');
      head.className = 'note-lookup__count';
      head.textContent = `${hits.length}개 cycle:`;
      result.appendChild(head);
      hits.forEach(i => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'note-lookup__chip';
        chip.dataset.cycle = String(i);
        chip.textContent = `c${i}`;
        chip.title = `cycle ${i} 선택 (건반 시각화)`;
        chip.addEventListener('click', () => selectCycle(i));
        result.appendChild(chip);
      });
    };
    if (!sel._wired) {
      sel.addEventListener('change', render);
      sel._wired = true;
    }
    if (labels.length > 0) {
      sel.value = String(labels[0].label);
      render();
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

  // ── 30초 세그먼트 (T=60 ≈ 30초 @ bpm 60) ──────────────────────────
  const SEGMENT_STEPS = 60;
  const SEGMENT_KEY = makeStorageKey('hibari_dashboard_segment_v1');
  const segState = { mode: 'segment', m: 0 };   // mode: 'segment' | 'full'

  function segmentCount(T) { return Math.max(1, Math.floor(T / SEGMENT_STEPS)); }

  function fmtStepTime(step) {
    const sec = Math.round(step * 0.5);   // bpm 60 → 8분음표 1개 = 0.5초
    const m = Math.floor(sec / 60), s = sec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function getSegment() {
    if (!UI.editEditor || segState.mode === 'full') return null;
    const n = segmentCount(UI.editEditor.T);
    const m = Math.max(0, Math.min(n - 1, segState.m | 0));
    return { m, start: m * SEGMENT_STEPS, len: SEGMENT_STEPS };
  }

  function saveSegmentState() {
    try { localStorage.setItem(SEGMENT_KEY, JSON.stringify(segState)); } catch (e) {}
  }
  function loadSegmentState() {
    try {
      const b = JSON.parse(localStorage.getItem(SEGMENT_KEY));
      if (b && (b.mode === 'full' || b.mode === 'segment')) {
        segState.mode = b.mode;
        segState.m = b.m | 0;
      }
    } catch (e) {}
  }

  function applySegmentToEditors() {
    const seg = getSegment();
    [UI.refEditor, UI.editEditor].forEach((ed) => {
      if (!ed || typeof ed.setSegment !== 'function') return;
      if (seg) ed.setSegment(seg.start, seg.len);
      else ed.setSegment(null, null);
    });
  }

  function updateSegmentHint() {
    const hint = $('segmentHint');
    if (!hint) return;
    const seg = getSegment();
    hint.textContent = seg
      ? `30초 세그먼트 · step ${seg.start}–${seg.start + seg.len} (${fmtStepTime(seg.start)}–${fmtStepTime(seg.start + seg.len)}) · 캔버스의 밝은 구간만 생성`
      : '전곡 모드 (약 9분) — 데모는 30초 블록을 권장합니다';
  }

  function populateSegmentSelect() {
    const sel = $('segmentSelect');
    if (!sel || !UI.editEditor) return;
    const T = UI.editEditor.T;
    const n = segmentCount(T);
    sel.innerHTML = '';
    for (let m = 0; m < n; m++) {
      const opt = document.createElement('option');
      opt.value = String(m);
      opt.textContent = `블록 ${m} · ${fmtStepTime(m * SEGMENT_STEPS)}–${fmtStepTime((m + 1) * SEGMENT_STEPS)}`;
      sel.appendChild(opt);
    }
    const full = document.createElement('option');
    full.value = 'full';
    full.textContent = `전곡 (${fmtStepTime(T)} · 연구용)`;
    sel.appendChild(full);
    segState.m = Math.max(0, Math.min(n - 1, segState.m | 0));
    sel.value = segState.mode === 'full' ? 'full' : String(segState.m);
    updateSegmentHint();
  }

  function onSegmentChanged() {
    saveSegmentState();
    applySegmentToEditors();
    updateSegmentHint();
    stopLocalPlayback();
    invalidateGeneratedOnEdit();   // 이전 생성물은 다른 구간 결과
    vaeResetBase();                // 다른 블록 = 다른 latent 끝점
    liveMaybeRegenerate();
  }

  function wireSegmentControls() {
    const sel = $('segmentSelect');
    if (!sel) return;
    sel.addEventListener('change', () => {
      if (sel.value === 'full') {
        segState.mode = 'full';
      } else {
        segState.mode = 'segment';
        segState.m = parseInt(sel.value, 10) || 0;
      }
      onSegmentChanged();
      log(segState.mode === 'full' ? '구간: 전곡' : `구간: 블록 ${segState.m}`);
    });
    const stepBlock = (d) => {
      const n = segmentCount(UI.editEditor ? UI.editEditor.T : SEGMENT_STEPS);
      if (segState.mode === 'full') segState.mode = 'segment';
      segState.m = ((segState.m + d) % n + n) % n;
      sel.value = String(segState.m);
      onSegmentChanged();
      log(`구간: 블록 ${segState.m}`);
    };
    const prev = $('btnSegPrev');
    const next = $('btnSegNext');
    if (prev) prev.addEventListener('click', () => stepBlock(-1));
    if (next) next.addEventListener('click', () => stepBlock(1));
  }

  // ── 인페이지 재생 (생성 결과 ♪ 듣기) ────────────────────────────────
  function playLastGenerated() {
    if (!playState.lastGenerated) {
      log('재생할 생성 결과가 없습니다 (먼저 생성)', 'ERR');
      return;
    }
    const player = ensurePlayer();
    const bpm = playState.bpm;
    const notesSec = playState.lastGenerated.notes.map(
      (n) => [eighthsToSec(n[0], bpm), n[1], eighthsToSec(n[2], bpm)]
    );
    const btnStop = $('btnStopLocal');
    if (btnStop) btnStop.disabled = false;
    player.play(notesSec, {
      onProgress: (t, total) => {
        setProgress(total > 0 ? t / total : 0,
          `재생 중 ${t.toFixed(1)}s / ${total.toFixed(1)}s`);
      },
      onEnd: () => {
        setProgress(1, '재생 완료');
        if (btnStop) btnStop.disabled = true;
      },
    });
  }

  function stopLocalPlayback() {
    if (playState.genPlayer && playState.genPlayer.isPlaying) {
      playState.genPlayer.stop();
      setProgress(0, '정지');
    }
    const btnStop = $('btnStopLocal');
    if (btnStop) btnStop.disabled = true;
  }

  // ── 라이브 모드 — 편집하면 debounce 후 자동 재생성 + 재생 ──────────
  const LIVE_DEBOUNCE_MS = 500;
  let liveTimer = null;

  function liveMaybeRegenerate() {
    const chk = $('chkLive');
    if (!chk || !chk.checked) return;
    if (liveTimer) clearTimeout(liveTimer);
    liveTimer = setTimeout(async () => {
      liveTimer = null;
      const res = await generateNow({ quiet: true });
      if (res) playLastGenerated();
    }, LIVE_DEBOUNCE_MS);
  }

  function wireLiveMode() {
    const chk = $('chkLive');
    if (!chk) return;
    chk.addEventListener('change', () => {
      if (chk.checked) {
        log('라이브 모드 ON — OM을 편집하면 자동으로 생성·재생합니다', 'OK');
        liveMaybeRegenerate();
      } else {
        if (liveTimer) { clearTimeout(liveTimer); liveTimer = null; }
        stopLocalPlayback();
        log('라이브 모드 OFF');
      }
    });
  }

  // ── 품질 맵 — 구조 보존 × 신선함 산점도 ────────────────────────────
  // x = 위상 구조 보존: 편집 OM(세그먼트)의 cycle별 활성 분포 vs 참조 동일 구간 (1 − JS)
  // y = 신선함: 생성 (pitch, dur) 분포 vs 원곡 분포의 JS divergence (논문 평가 지표와 동일 계열)
  const qualityState = { points: [], cap: 60 };

  function jsDivergence(p, q) {
    // p, q: 정규화된 분포 (합 1). log2 기준 → [0, 1].
    const eps = 1e-12;
    let js = 0;
    for (let i = 0; i < p.length; i++) {
      const pi = p[i] + eps, qi = q[i] + eps, mi = 0.5 * (pi + qi);
      js += 0.5 * pi * Math.log2(pi / mi) + 0.5 * qi * Math.log2(qi / mi);
    }
    return Math.max(0, Math.min(1, js));
  }

  function normalizeDist(arr) {
    let s = 0;
    for (const v of arr) s += v;
    if (s <= 0) return arr.map(() => 1 / arr.length);
    return arr.map((v) => v / s);
  }

  function computeStructureScore(seg) {
    const ed = UI.editEditor;
    const K = ed.K;
    const vals = ed.getMatrix();
    const ref = ed.reference;
    if (!ref) return 1;
    const start = seg ? seg.start : 0;
    const len = seg ? seg.len : ed.T;
    const e = new Array(K).fill(0);
    const r = new Array(K).fill(0);
    for (let t = start; t < start + len; t++) {
      for (let c = 0; c < K; c++) {
        const i = t * K + c;
        e[c] += Math.max(0, vals[i]);
        r[c] += Math.max(0, ref[i]);
      }
    }
    return 1 - jsDivergence(normalizeDist(e), normalizeDist(r));
  }

  function computeFreshnessScore(notes) {
    // (pitch, dur) note 단위 분포 — 논문 JS 평가와 동일한 단위
    const gen = new Map();
    for (const n of notes) {
      const key = n[1] * 1000 + Math.max(1, (n[2] - n[0]) | 0);
      gen.set(key, (gen.get(key) || 0) + 1);
    }
    const orig = new Map();
    for (const l of UI.data.notesMeta.labels) {
      const key = l.pitch * 1000 + Math.max(1, l.dur | 0);
      orig.set(key, (orig.get(key) || 0) + (l.count || 1));
    }
    const keys = Array.from(new Set([...gen.keys(), ...orig.keys()])).sort((a, b) => a - b);
    const p = keys.map((k) => gen.get(k) || 0);
    const q = keys.map((k) => orig.get(k) || 0);
    return jsDivergence(normalizeDist(p), normalizeDist(q));
  }

  // 협화도 — 각 시점 동시발음의 협화 interval class {0,3,4,5} 비율.
  // 실험(experiments/run_aesthetic_rerank.py)에서 calibration 유효 확인된 유일한 미적 성분.
  // (성부진행·도약은 hibari 2성부 음역분리를 페널티해 무효 → 표시하지 않음)
  function consonanceScore(notes) {
    const CONSONANT = new Set([0, 3, 4, 5]);
    const timeToPitches = new Map();
    for (const n of notes) {
      const s = n[0] | 0, p = n[1] | 0, e = n[2] | 0;
      for (let t = s; t < e; t++) {
        if (!timeToPitches.has(t)) timeToPitches.set(t, []);
        timeToPitches.get(t).push(p);
      }
    }
    let ratioSum = 0, chordCount = 0;
    for (const pitches of timeToPitches.values()) {
      if (pitches.length < 2) continue;
      let total = 0, cons = 0;
      for (let i = 0; i < pitches.length; i++) {
        for (let j = i + 1; j < pitches.length; j++) {
          let ic = Math.abs(pitches[i] - pitches[j]) % 12;
          ic = Math.min(ic, 12 - ic);
          total++;
          if (CONSONANT.has(ic)) cons++;
        }
      }
      if (total > 0) { ratioSum += cons / total; chordCount++; }
    }
    return chordCount > 0 ? ratioSum / chordCount : 1;
  }

  function updateQualityMap(res, seg, info) {
    const S = computeStructureScore(seg);
    const F = computeFreshnessScore(res.notes);
    const Cons = consonanceScore(res.notes);
    qualityState.points.push({
      S, F,
      algo: info.algo,
      seed: info.seed,
      seg: seg ? seg.m : 'full',
      ts: Date.now(),
    });
    if (qualityState.points.length > qualityState.cap) {
      qualityState.points.splice(0, qualityState.points.length - qualityState.cap);
    }
    const meta = $('qualityMapMeta');
    if (meta) {
      meta.textContent =
        `구조 보존 ${(S * 100).toFixed(0)}% · 신선함 JS=${F.toFixed(3)} · 협화도 ${(Cons * 100).toFixed(0)}% · ${info.algoLabel} seed ${info.seed}`;
    }
    renderQualityMap();
  }

  function renderQualityMap() {
    const cv = $('qualityMapCanvas');
    if (!cv) return;
    const ctx = cv.getContext('2d');
    const W = cv.width, H = cv.height;
    const css = getComputedStyle(document.documentElement);
    const colCanvas = css.getPropertyValue('--surface-canvas').trim() || '#101322';
    const colGrid = css.getPropertyValue('--grid-line').trim() || 'rgba(255,255,255,0.08)';
    const colText = css.getPropertyValue('--text-dim').trim() ||
                    css.getPropertyValue('--text-secondary').trim() || '#888';
    const colA1 = css.getPropertyValue('--accent-teal').trim() || '#34d399';
    const colA2 = css.getPropertyValue('--accent-amber').trim() || '#fbbf24';

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = colCanvas;
    ctx.fillRect(0, 0, W, H);

    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r;
    const plotH = H - pad.t - pad.b;

    // sqrt 스케일 — JS 가 작은 영역(좋은 생성)을 넓게 펼침
    const xOf = (S) => pad.l + plotW * (1 - Math.sqrt(Math.max(0, Math.min(1, 1 - S))));
    const yOf = (F) => pad.t + plotH * (1 - Math.sqrt(Math.max(0, Math.min(1, F))));

    // 격자 + 축
    ctx.strokeStyle = colGrid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const fr of [0.25, 0.5, 0.75]) {
      ctx.moveTo(pad.l + plotW * fr, pad.t); ctx.lineTo(pad.l + plotW * fr, pad.t + plotH);
      ctx.moveTo(pad.l, pad.t + plotH * fr); ctx.lineTo(pad.l + plotW, pad.t + plotH * fr);
    }
    ctx.rect(pad.l, pad.t, plotW, plotH);
    ctx.stroke();

    // 목표 사분면 힌트 (오른쪽 위)
    ctx.fillStyle = 'rgba(52, 211, 153, 0.07)';
    ctx.fillRect(pad.l + plotW * 0.55, pad.t, plotW * 0.45, plotH * 0.45);

    ctx.fillStyle = colText;
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.fillText('신선함 ↑', pad.l + 2, pad.t + 10);
    ctx.textAlign = 'right';
    ctx.fillText('구조 보존 →', W - pad.r, H - 8);
    ctx.textAlign = 'left';

    // 점들 — 과거는 흐리게, 최신은 크게 + 링
    const pts = qualityState.points;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      const isLast = i === pts.length - 1;
      const x = xOf(p.S), y = yOf(p.F);
      const col = p.algo === 'algo2' ? colA2 : colA1;
      ctx.globalAlpha = isLast ? 1 : Math.max(0.15, 0.65 * (i + 1) / pts.length);
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(x, y, isLast ? 5 : 3, 0, Math.PI * 2);
      ctx.fill();
      if (isLast) {
        ctx.globalAlpha = 0.9;
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  function wireQualityMap() {
    const btn = $('btnQualityClear');
    if (btn) {
      btn.addEventListener('click', () => {
        qualityState.points = [];
        const meta = $('qualityMapMeta');
        if (meta) meta.textContent = '생성할 때마다 점이 찍힙니다';
        renderQualityMap();
      });
    }
    // 테마 전환 시 재렌더 (토큰 색이 바뀌므로)
    try {
      new MutationObserver(() => renderQualityMap())
        .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    } catch (e) {}
    renderQualityMap();
  }

  // ── 구조 탐험 (VAE) — latent 슬라이더 · 새 구조 · 매니폴드 보정 ──────
  // 학습: scripts/train_om_vae_and_export.py (window=60 = 30초 세그먼트와 동일)
  const vaeState = {
    vae: null,
    base: null,        // { m, z } — 슬라이더 0% 끝점 (사용자가 그린 상태의 latent)
    applying: false,   // VAE 가 setMatrix 하는 동안 base 무효화 방지
    token: 0,          // 슬라이더 연타 시 stale decode 폐기
  };

  function setVaeStatus(msg) {
    const el = $('vaeStatus');
    if (el) el.textContent = msg;
  }

  async function ensureVaeLoaded() {
    if (!window.VAEExplorer) throw new Error('VAEExplorer 모듈 미로드');
    if (!vaeState.vae) vaeState.vae = new window.VAEExplorer();
    if (!vaeState.vae.dec) {
      setVaeStatus('VAE 모델 로드 중… (~2MB)');
      await vaeState.vae.load();
      setVaeStatus('준비 완료 — 슬라이더로 hibari다움을 조절하세요');
      log(`VAE 로드 완료 (${vaeState.vae.meta.architecture})`, 'OK');
    }
  }

  // 세그먼트 필수 — 전곡 모드면 안내 후 null
  function getVaeSegment() {
    const seg = getSegment();
    if (!seg) setVaeStatus('전곡 모드에서는 사용할 수 없습니다 — 30초 블록을 선택하세요');
    return seg;
  }

  // 현재 편집 OM 의 세그먼트를 [0,1] 연속 Float32Array(window*K) 로 읽기
  function readSegmentContinuous(seg) {
    const ed = UI.editEditor;
    const K = ed.K;
    const vals = ed.getMatrix();
    const out = new Float32Array(seg.len * K);
    for (let i = 0; i < seg.len * K; i++) {
      const v = +vals[seg.start * K + i];
      out[i] = v > 1 ? 1 : (v > 0 ? v : 0);
    }
    return out;
  }

  // decode 결과를 편집 OM 의 세그먼트 창에 기록.
  // 이진 모드: 고정 τ 대신 밀도 일치 이진화 — 디코더 출력은 확률이라
  // 기대 활성 수 N = Σp 만큼 상위 셀을 켠다 (τ=0.7 은 과소 활성 유발).
  function applyVaeSegment(decoded, seg) {
    const ed = UI.editEditor;
    const K = ed.K;
    const isBinary = ed.displayMode !== 'continuous';
    const Alloc = isBinary ? Int8Array : Float32Array;
    const full = new Alloc(ed.getMatrix());
    const n = seg.len * K;
    if (isBinary) {
      let sum = 0;
      for (let i = 0; i < n; i++) sum += decoded[i];
      const target = Math.max(0, Math.min(n, Math.round(sum)));
      const order = Array.from({ length: n }, (_, i) => i)
        .sort((a, b) => decoded[b] - decoded[a]);
      const on = new Uint8Array(n);
      for (let k = 0; k < target; k++) on[order[k]] = 1;
      for (let i = 0; i < n; i++) full[seg.start * K + i] = on[i];
    } else {
      for (let i = 0; i < n; i++) {
        const v = decoded[i];
        full[seg.start * K + i] = v > 1 ? 1 : (v > 0 ? v : 0);
      }
    }
    vaeState.applying = true;
    try { ed.setMatrix(full); } finally { vaeState.applying = false; }
  }

  async function vaeCaptureBase(seg) {
    const z = await vaeState.vae.encode(readSegmentContinuous(seg));
    vaeState.base = { m: seg.m, z };
  }

  // 수동 편집·세그먼트 이동 시 base 무효화 + 슬라이더 0 복귀 (표시만)
  function vaeResetBase() {
    if (vaeState.applying) return;
    vaeState.base = null;
    const s = $('sliderVaeMix');
    if (s && s.value !== '0') {
      s.value = '0';
      const v = $('sliderVaeMixVal');
      if (v) v.textContent = '0%';
    }
  }

  async function onVaeMixInput() {
    const slider = $('sliderVaeMix');
    const t = (+slider.value) / 100;
    const valEl = $('sliderVaeMixVal');
    if (valEl) valEl.textContent = Math.round(t * 100) + '%';
    const myToken = ++vaeState.token;
    try {
      await ensureVaeLoaded();
      const seg = getVaeSegment();
      if (!seg) return;
      if (!vaeState.base || vaeState.base.m !== seg.m) await vaeCaptureBase(seg);
      const zRef = vaeState.vae.zRef(seg.m);
      if (!zRef) { setVaeStatus('참조 latent 없음 (meta 확인)'); return; }
      const z = window.VAEExplorer.lerp(vaeState.base.z, zRef, t);
      const decoded = await vaeState.vae.decode(z);
      if (myToken !== vaeState.token) return;   // 슬라이더가 더 움직임 — stale 폐기
      applyVaeSegment(decoded, seg);
      setVaeStatus(`보간 ${Math.round(t * 100)}% 적용 (블록 ${seg.m})`);
    } catch (e) {
      setVaeStatus('오류: ' + e.message);
      console.error(e);
    }
  }

  // 🎲 새 구조: z ~ N(0, I) — hibari 문법 안의 무작위 구조
  async function onVaeDice() {
    try {
      await ensureVaeLoaded();
      const seg = getVaeSegment();
      if (!seg) return;
      const seedInput = $('sliderSeed');
      const seed = (parseInt(seedInput && seedInput.value, 10) || 0) + Date.now() % 9973;
      const rng = window.GenerationAlgo1
        ? window.GenerationAlgo1.makeRng(seed >>> 0)
        : Math.random;
      const z = window.VAEExplorer.randn(vaeState.vae.meta.latent_dim, rng);
      const decoded = await vaeState.vae.decode(z);
      applyVaeSegment(decoded, seg);
      // 새 구조가 슬라이더 0% 끝점이 되도록 base 갱신
      vaeState.applying = true;
      vaeState.base = { m: seg.m, z };
      vaeState.applying = false;
      const s = $('sliderVaeMix');
      if (s) { s.value = '0'; const v = $('sliderVaeMixVal'); if (v) v.textContent = '0%'; }
      setVaeStatus(`새 구조 적용 (블록 ${seg.m}) — 슬라이더로 hibari 쪽으로 끌어보세요`);
      log(`VAE 새 구조 샘플 (블록 ${seg.m})`);
    } catch (e) {
      setVaeStatus('오류: ' + e.message);
      console.error(e);
    }
  }

  // 🌿 부드럽게 보정: encode→decode 재구성 = 학습 매니폴드로 사영 (OOD 완화)
  async function onVaeSmooth() {
    try {
      await ensureVaeLoaded();
      const seg = getVaeSegment();
      if (!seg) return;
      const z = await vaeState.vae.encode(readSegmentContinuous(seg));
      const decoded = await vaeState.vae.decode(z);
      applyVaeSegment(decoded, seg);
      vaeState.base = { m: seg.m, z };
      const s = $('sliderVaeMix');
      if (s) { s.value = '0'; const v = $('sliderVaeMixVal'); if (v) v.textContent = '0%'; }
      setVaeStatus(`부드럽게 보정 완료 (블록 ${seg.m}) — 손그림이 hibari 구조 문법으로 정돈됨`);
      log(`VAE 매니폴드 보정 (블록 ${seg.m})`);
    } catch (e) {
      setVaeStatus('오류: ' + e.message);
      console.error(e);
    }
  }

  function wireVaePanel() {
    const slider = $('sliderVaeMix');
    if (slider) slider.addEventListener('input', onVaeMixInput);
    const dice = $('btnVaeDice');
    if (dice) dice.addEventListener('click', onVaeDice);
    const smooth = $('btnVaeSmooth');
    if (smooth) smooth.addEventListener('click', onVaeSmooth);
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

  // 알고리즘 2 — 곡에 따라 FC(hibari) 또는 Transformer(solari) 분기
  async function runAlgo2Once({ overlap, temperature, seed }) {
    const song = currentSong();
    if (song === 'solari') {
      const res = await playState.transGen.generate({
        overlap, seed, temperature, minOnsetGap: 0,
      });
      return res;
    }
    // 기본(hibari): FC
    const res = await playState.fcGen.generate({
      overlap, seed, temperature, minOnsetGap: 0,
    });
    return res;
  }

  // FC 모델 지연 로드 (hibari 전용)
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

  // Transformer 모델 지연 로드 (solari 전용)
  async function ensureTransformerLoaded() {
    if (!window.TransformerGenerator) throw new Error('TransformerGenerator 모듈 미로드');
    if (!playState.transGen) playState.transGen = new window.TransformerGenerator();
    if (!playState.transGen.session) log('Transformer 모델 로드 중… (ONNX runtime + solari 모델 다운로드)');
    await playState.transGen.load();
    if (playState.transLoaded !== true) {
      log(`Transformer 모델 로드 완료 (${playState.transGen.meta.architecture})`, 'OK');
      playState.transLoaded = true;
    }
  }

  // 곡에 따른 Algorithm 2 로드 헬퍼 선택
  async function ensureAlgo2Loaded() {
    if (currentSong() === 'solari') {
      return ensureTransformerLoaded();
    }
    return ensureFcLoaded();
  }

  // 생성 메인 — 기본은 30초 세그먼트(T=60), '전곡' 선택 시 전체.
  // opts.quiet — 라이브 모드 재생성 시 로그 최소화.
  // genToken: 라이브 모드에서 async 추론 중 재편집 시 늦게 도착한
  // stale 결과가 최신 결과를 덮어쓰지 않도록 세대 가드.
  let genToken = 0;
  async function generateNow(opts = {}) {
    if (!UI.editEditor || !UI.data) { log('데이터 미로드', 'ERR'); return; }
    if (!window.GenerationAlgo1) { log('GenerationAlgo1 모듈 미로드', 'ERR'); return; }

    const algo = document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
    const temperature = parseFloat($('sliderTemp').value) || 3.0;
    const seed = parseInt($('sliderSeed').value, 10) || 0;
    const song = currentSong();

    const { buildHibariInstLen } = window.GenerationAlgo1;
    const K = UI.editEditor.K;
    const fullT = UI.editEditor.T;
    // instLen 패턴: hibari 전용. solari 는 데이터 기반 T 에 맞춘 단순 fill=4
    const fullInstLen = buildHibariInstLen(fullT);
    const fullValues = UI.editEditor.getMatrix();

    // 세그먼트 슬라이스 — 선택 구간만 생성 (메모: T=60 ≈ 30초)
    const seg = getSegment();
    let overlap, instLen, offset;
    if (seg) {
      overlap = {
        T: seg.len, K,
        values: fullValues.slice(seg.start * K, (seg.start + seg.len) * K),
      };
      instLen = fullInstLen.slice(seg.start, seg.start + seg.len);
      offset = seg.start;
    } else {
      overlap = { T: fullT, K, values: fullValues };
      instLen = fullInstLen;
      offset = 0;
    }

    try {
      // Algorithm 2 라벨 동적화: solari → Transformer
      const algo2Label = song === 'solari' ? 'Algorithm 2 (Transformer)' : 'Algorithm 2 (FC)';
      const algoLabel = algo === 'algo2' ? algo2Label : 'Algorithm 1';
      if (!opts.quiet) {
        if (seg) {
          log(`${algoLabel} 30초 세그먼트 생성 (블록 ${seg.m}, step ${seg.start}–${seg.start + seg.len}, seed=${seed}, temp=${temperature.toFixed(1)})`);
        } else {
          const bars = Math.round(overlap.T / BAR_STEPS);
          log(`${algoLabel} 전곡 생성 (T=${overlap.T}, ${bars}마디, seed=${seed}, temp=${temperature.toFixed(1)})`);
        }
      }
      const myToken = ++genToken;
      if (algo === 'algo2') await ensureAlgo2Loaded();

      const t0 = performance.now();
      let res;
      if (algo === 'algo2') {
        res = await runAlgo2Once({ overlap, temperature, seed });
      } else {
        res = runAlgo1Once({ overlap, instLen, temperature, seed });
      }
      if (myToken !== genToken) return null;   // 더 새로운 생성이 시작됨 — stale 폐기
      res.offset = offset;
      res.segment = seg ? { m: seg.m, start: seg.start, len: seg.len } : null;
      const dt = performance.now() - t0;
      if (!opts.quiet) log(`생성 완료 (${dt.toFixed(0)}ms, ${res.notes.length} notes)`, 'OK');

      playState.lastGenerated = res;
      $('btnDownloadMidi').disabled = false;
      const btnT = $('btnPlayInTonnetz');
      if (btnT) btnT.disabled = false;
      const btnP = $('btnPlayLocal');
      if (btnP) btnP.disabled = false;
      syncActionButtons();

      // 품질 맵 점 추가 (구조 보존 × 신선함)
      try { updateQualityMap(res, seg, { algo, algoLabel, seed }); } catch (e) { console.warn('quality map:', e); }

      const segLabel = seg ? `블록 ${seg.m}` : '전곡';
      setProgress(1, `생성 완료 (${segLabel}) · ${res.notes.length} notes · ♪ 듣기 또는 MIDI 저장`);
      return res;
    } catch (e) {
      log(`생성 실패: ${e.message}`, 'ERR');
      console.error(e);
      return null;
    }
  }

  function onClickGenerate() { return generateNow({}); }

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
      const segTag = cur.segment ? `m${cur.segment.m}` : 'full';
      const fname = `hibari_dash_seed${seed}_${segTag}.mid`;
      window.MidiIO.downloadBytes(bytes, fname);
      log(`MIDI 다운로드: ${fname} (${(bytes.length / 1024).toFixed(1)} KB)`, 'OK');
    } catch (e) {
      log(`MIDI 저장 실패: ${e.message}`, 'ERR');
    }
  }

  // ── Tonnetz Demo 연동 (시나리오 1: publish → 자동재생) ─────────────
  function onClickPlayInTonnetz() {
    if (!playState.lastGenerated) {
      log('재생할 생성 결과가 없습니다 (먼저 Generate)', 'ERR');
      return;
    }
    if (!window.TDAState || typeof window.TDAState.publishSequence !== 'function') {
      log('TDAState 모듈 미로드 (../../shared/state.js)', 'ERR');
      return;
    }
    try {
      const cur = playState.lastGenerated;
      window.TDAState.publishSequence({
        notes: cur.notes,
        bpm: playState.bpm,
        ticksPerEighth: 240,
        source: 'hibari_dashboard',
      });
      setWorkflowStage(3);
      try { sessionStorage.setItem('tda:workflowStage', '3'); } catch (e) {}
      log(`Tonnetz Demo 로 publish (${cur.notes.length} notes, bpm=${playState.bpm})`, 'OK');
      console.info('[hibari→tonnetz] publish:', { notes: cur.notes.length, bpm: playState.bpm });
      // 같은 탭 내비게이션 → sessionStorage 보존
      window.location.href = '../../tonnetz_demo/index.html?from=hibari&intent=autoplay';
    } catch (e) {
      log(`Tonnetz publish 실패: ${e.message}`, 'ERR');
      console.error(e);
    }
  }

  // ── 시나리오 8: 편집 시작 시 pending sequence 자동 소거 ────────────
  // 정책: 편집 상태 데이터는 재생 대기열로 유지하지 않음. publishSequence 후
  // hibari 로 돌아와 OM 을 수정하는 순간 stale 시퀀스를 즉시 clear.
  function clearPendingOnEdit() {
    try {
      if (window.TDAState && typeof window.TDAState.consumeSequence === 'function') {
        // peek + clear 의도로 consume 사용 (반환값 무시)
        const wasThere = window.TDAState.peekSequence?.();
        if (wasThere) {
          window.TDAState.consumeSequence();
          log('OM 편집 감지 → 이전 publish sequence clear', 'INFO');
          console.info('[hibari] scenario8: pending sequence cleared on edit', {
            source: wasThere.source, notes: wasThere.notes?.length
          });
        }
      }
    } catch (e) { /* noop */ }
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
          invalidateGeneratedOnEdit();
          updateEditMeta(ed);
          updateOODBanner(ed);
          saveEditState(ed);
          clearPendingOnEdit(); // 시나리오 8
          vaeResetBase();        // 수동 편집 → VAE 슬라이더 0% 끝점 재설정
          liveMaybeRegenerate(); // 라이브 모드: 편집 → 자동 재생성·재생
        },
      });
      updateEditMeta(UI.editEditor);
      updateOODBanner(UI.editEditor);

      // hover tooltip
      const tt = $('hoverTooltip');
      const wrap = $('editCanvas').parentElement;
      attachHoverTooltip(UI.editEditor, tt, wrap, data);

      // 변형 스택 복원: localStorage 에 stack 이 있으면 적용 → 편집 OM 자동 재계산
      const savedStack = loadStackState();
      if (savedStack && savedStack.length > 0) {
        UI.stack = savedStack;
        // id 충돌 방지: 다음 id 를 가장 큰 기존 id 보다 크게 설정
        let maxNum = 0;
        savedStack.forEach(s => {
          if (typeof s.id === 'string' && s.id.startsWith('s')) {
            const n = parseInt(s.id.slice(1), 10);
            if (Number.isFinite(n) && n > maxNum) maxNum = n;
          }
        });
        UI.stackNextId = maxNum + 1;
        log(`변형 스택 복원: ${savedStack.length}개 단계`);
      }
      renderStackList();

      // 알고리즘 라디오 ↔ 입력 모드 초기 동기화 (algo1=binary 기본)
      const initAlgo = document.querySelector('input[name="algo"]:checked')?.value || 'algo1';
      UI.stackMode = initAlgo === 'algo2' ? 'continuous' : 'binary';
      applyViewModeButtonDisabled();
      updateModeBadge();
      // algo 변경 시에도 disable 갱신 (Algo1↔Algo2 전환 시 continuous 버튼 차단/해제)
      document.querySelectorAll('input[name="algo"]').forEach(r => {
        r.addEventListener('change', applyViewModeButtonDisabled);
      });

      if (UI.stack.length > 0) recomputeStackToEditor();

      // 30초 세그먼트 — 저장된 선택 복구 → 셀렉트 채우기 → 캔버스 밴드 표시
      loadSegmentState();
      populateSegmentSelect();
      applySegmentToEditors();

      // 사이클 미리듣기 목록 + 시각화 초기 렌더 (c0 기본 표시)
      populateCycleList();
      populateNoteLookup();
      playState.selectedCycleIdx = 0;
      renderCycleViz(0, null);

      // ── 곡 전환 후 데이터 로드 완료 시 UI 갱신 ────────────────────────
      const song = currentSong();

      // 헤더 부제 동적화: 곡·차원·거리/모델 정보
      const subEl = document.querySelector('.app-header__sub');
      if (subEl) {
        if (song === 'solari') {
          subEl.textContent =
            `solari · T=${T}·K=${K}·N=${data.notesMeta.num_notes} · voice_leading · Transformer`;
        } else {
          subEl.textContent =
            `hibari · T=${T}·K=${K}·N=${data.notesMeta.num_notes} · DFT α=0.25 per-cycle τ · FC`;
        }
      }

      // Algorithm 2 라디오 라벨 동적화 (텍스트 노드만 교체)
      const algo2Labels = document.querySelectorAll('input[name="algo"][value="algo2"]');
      algo2Labels.forEach(radio => {
        const label = radio.closest('label');
        if (!label) return;
        // 텍스트 노드 찾아서 교체
        for (const node of label.childNodes) {
          if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
            node.textContent = song === 'solari'
              ? ' Algorithm 2 (Transformer)'
              : ' Algorithm 2 (FC)';
            break;
          }
        }
      });

      // VAE 패널 — hibari 전용 (60×14 학습; solari 60×25 비호환)
      // hidden 만으로 패널 전체가 DOM 에서 숨겨져 슬라이더 조작 불가.
      // <details> 는 disabled IDL 속성이 없으므로 hidden 토글로 충분.
      const vaeGroup = $('vaeGroup');
      if (vaeGroup) vaeGroup.hidden = (song === 'solari');

      // 곡 전환 토글 버튼 active 상태 동기화
      document.querySelectorAll('[data-song-toggle]').forEach(btn => {
        const target = btn.dataset.songToggle;
        btn.classList.toggle('is-active', target === song);
        btn.setAttribute('aria-pressed', String(target === song));
      });

      // 최초 로드 상태 메시지
      const metricHint = song === 'solari' ? 'voice_leading · Transformer' : 'DFT α=0.25 per-cycle τ';
      setStatus(
        `${song} · T=${T} · K=${K} · N=${data.notesMeta.num_notes} · ${metricHint}`,
        'ok'
      );
      log(`데이터 로드 완료 (곡: ${song}, manifest version ${data.manifest.version})`, 'OK');
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
