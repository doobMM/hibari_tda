/* ============================================================================
 * remote.js — 참여 기록을 모두가 보는 곳에 남긴다 (없으면 이 브라우저에만)
 *
 * 백엔드 = Google Apps Script 웹 앱 + 스프레드시트 1장.
 *   서버 코드: tools/backend/apps_script.gs · 설정 절차: docs/backend_setup.md
 *   선택 근거(Firestore · Supabase · Cloudflare 비교)도 그 문서에 있다.
 *
 * ENDPOINT 가 비어 있으면 **로컬 폴백** — 모든 이벤트는 localStorage 에 쌓이고,
 * 나중에 ENDPOINT 를 채우면 쌓인 것이 그대로 올라간다(outbox). 잃는 표가 없다.
 *
 * 이벤트 = { id, kind, uid, t, data }
 *   uid 는 브라우저마다 한 번 만드는 난수다. 이름·이메일·IP 를 담지 않는다.
 *   "몇 명이 참여했나"만 셀 수 있으면 된다.
 *
 * 공개:
 *   Remote.send(kind, data)  → 이벤트 (즉시 로컬에 남고, 가능하면 올라간다)
 *   Remote.list(kinds)       → Promise<{ events, shared }>  서버 + 내 로그 합집합
 *   Remote.mine(kind)        → 내가 만든 이벤트
 *   Remote.shared            → ENDPOINT 가 설정됐나
 *   Remote.uid
 * ========================================================================== */
window.Remote = (function () {
  // ← Apps Script 배포 URL (https://script.google.com/macros/s/…/exec). 시험용으로
  //   페이지에서 window.REMOTE_ENDPOINT 를 먼저 정하면 그것을 쓴다.
  var ENDPOINT = window.REMOTE_ENDPOINT || '';

  var OUT = 'remote.outbox', LOG = 'remote.log', UID = 'remote.uid';
  function get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function rid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

  var uid = get(UID);
  if (typeof uid !== 'string') { uid = rid(); put(UID, uid); }

  var busy = false;
  /** outbox 를 올린다. 실패하면 남겨 두고 다음 기회에 다시 올린다. */
  function flush() {
    var q = get(OUT) || [];
    if (!ENDPOINT || busy || !q.length) return Promise.resolve(!q.length);
    busy = true;
    // text/plain = CORS "단순 요청" → preflight 없이 Apps Script 에 닿는다
    return fetch(ENDPOINT, { method: 'POST', body: JSON.stringify(q), keepalive: true,
                             headers: { 'Content-Type': 'text/plain;charset=utf-8' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.ok) throw new Error(j.error);
        put(OUT, (get(OUT) || []).slice(q.length));   // 올리는 사이 새로 쌓인 것은 남긴다
        return true;
      })
      .catch(function () { return false; })
      .then(function (ok) { busy = false; return ok; });
  }

  function send(kind, data) {
    var ev = { id: rid(), kind: kind, uid: uid, t: Date.now(), data: data };
    var log = get(LOG) || []; log.push(ev); put(LOG, log.slice(-2000));
    var q = get(OUT) || []; q.push(ev); put(OUT, q);
    flush();
    return ev;
  }

  function mine(kind) {
    return (get(LOG) || []).filter(function (e) { return !kind || e.kind === kind; });
  }

  /** 서버에서 kinds 를 받아 내 로그와 합친다(id 로 중복 제거). 서버가 안 되면 내 로그만. */
  function list(kinds) {
    var local = (get(LOG) || []).filter(function (e) { return kinds.indexOf(e.kind) >= 0; });
    if (!ENDPOINT) return Promise.resolve({ events: local, shared: false });
    return flush().then(function () {
      return fetch(ENDPOINT + '?kinds=' + encodeURIComponent(kinds.join(',')));
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) throw new Error(j.error);
      var seen = {}, all = [];
      j.events.concat(local).forEach(function (e) {
        if (e && typeof e.id === 'string' && !seen[e.id]) { seen[e.id] = 1; all.push(e); }
      });
      return { events: all, shared: true };
    }).catch(function () { return { events: local, shared: false }; });
  }

  addEventListener('pagehide', flush);
  return { send: send, list: list, mine: mine, flush: flush, uid: uid, shared: !!ENDPOINT };
})();
