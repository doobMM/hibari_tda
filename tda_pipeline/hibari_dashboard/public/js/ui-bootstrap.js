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
    if (editor.displayMode === 'continuous') {
      $('editMeta').textContent =
        `평균 활성도 ${pct}% · 변경 ${diff}셀 (>5%p, ${diffPct}%)`;
    } else {
      $('editMeta').textContent =
        `density ${pct}% · diff ${diff} (${diffPct}%)`;
    }
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
    const btnPlayTonnetz = $('btnPlayInTonnetz');
    if (btnPlayTonnetz) btnPlayTonnetz.addEventListener('click', onClickPlayInTonnetz);
  }

  // ── 변형 스택 (Q1) ────────────────────────────────────────────
  // 스택 상태: [{id, kind, params, enabled}, ...]
  // 첫 변형은 reference 입력 → 출력. 다음 변형은 이전 출력 → 다시 출력.
  // localStorage 에 stack 자체를 저장 (참조와 함께 deterministic 재생성 가능).

  const STACK_STORAGE_KEY = 'hibari_dashboard_stack_v1';

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
  async function runAlgo2Once({ overlap, temperature, seed }) {
    const res = await playState.fcGen.generate({
      overlap, seed, temperature, minOnsetGap: 0,
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
        res = await runAlgo2Once({ overlap: fullOverlap, temperature, seed });
      } else {
        res = runAlgo1Once({ overlap: fullOverlap, instLen: fullInstLen, temperature, seed });
      }
      res.offset = 0;
      const dt = performance.now() - t0;
      log(`생성 완료 (${dt.toFixed(0)}ms, ${res.notes.length} notes)`, 'OK');

      playState.lastGenerated = res;
      $('btnDownloadMidi').disabled = false;
      const btnT = $('btnPlayInTonnetz');
      if (btnT) btnT.disabled = false;
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
      log(`Tonnetz Demo 로 publish (${cur.notes.length} notes, bpm=${playState.bpm})`, 'OK');
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
          updateEditMeta(ed);
          updateOODBanner(ed);
          saveEditState(ed);
          clearPendingOnEdit(); // 시나리오 8
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

      // 사이클 미리듣기 목록 + 시각화 초기 렌더 (c0 기본 표시)
      populateCycleList();
      populateNoteLookup();
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
