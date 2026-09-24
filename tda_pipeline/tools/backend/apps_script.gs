/**
 * apps_script.gs — 참여 기록 서버 (Google Apps Script 웹 앱)
 *
 * 스프레드시트 하나에 이벤트를 한 줄씩 붙인다. 설정 절차: docs/backend_setup.md
 * 클라이언트: shared/remote.js
 *
 *   POST  body = JSON 배열 [{ id, kind, uid, t, data }, …]   → { ok: true, n }
 *   GET   ?kinds=sow,vote                                    → { ok: true, events }
 *
 * 신뢰 경계: 이 URL 은 누구나 부를 수 있다. 그래서
 *   · kind 는 KINDS 에 있는 것만, 크기는 MAX_DATA 자까지만 받는다
 *   · GET 은 PUBLIC 에 있는 kind 만 돌려준다 (echo 배치는 연구자만 시트에서 본다)
 *   · 이름·이메일·IP 는 받지도 적지도 않는다. uid 는 브라우저가 만든 난수다
 * ponytail: 스팸 방어는 크기 제한뿐이다. 누가 마음먹고 표를 쏟으면 막지 못한다.
 *   필요해지면 uid 당 하루 상한을 여기 doPost 에 넣는다.
 */
var KINDS = { sow: 1, vote: 1, legacy: 1, echo: 1 };
var PUBLIC = { sow: 1, vote: 1 };
var MAX_DATA = 8000, MAX_BATCH = 200;
var HEAD = ['server_time', 'kind', 'id', 'uid', 't', 'data'];

function sheet_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('events');
  if (!sh) {
    sh = SpreadsheetApp.getActiveSpreadsheet().insertSheet('events');
    sh.appendRow(HEAD);
  }
  return sh;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
                       .setMimeType(ContentService.MimeType.JSON);
}

function valid_(e) {
  return e && KINDS[e.kind] === 1
    && typeof e.id === 'string' && /^[a-z0-9]{6,24}$/.test(e.id)
    && typeof e.uid === 'string' && /^[a-z0-9]{6,24}$/.test(e.uid)
    && typeof e.t === 'number' && isFinite(e.t)
    && JSON.stringify(e.data || null).length <= MAX_DATA;
}

function doPost(req) {
  var evs;
  try { evs = JSON.parse(req.postData.contents); } catch (err) { return out_({ ok: false, error: 'json' }); }
  if (!Array.isArray(evs) || evs.length > MAX_BATCH) return out_({ ok: false, error: 'batch' });
  var rows = evs.filter(valid_).map(function (e) {
    return [new Date(), e.kind, e.id, e.uid, e.t, JSON.stringify(e.data || null)];
  });
  if (rows.length) {
    var lock = LockService.getScriptLock();
    lock.waitLock(10000);                        // 동시에 붙이면 줄이 겹친다
    try {
      var sh = sheet_();
      sh.getRange(sh.getLastRow() + 1, 1, rows.length, HEAD.length).setValues(rows);
    } finally { lock.releaseLock(); }
  }
  // 버린 이벤트가 있어도 ok — 클라이언트가 같은 불량 이벤트를 영원히 재전송하지 않게
  return out_({ ok: true, n: rows.length, dropped: evs.length - rows.length });
}

function doGet(req) {
  var want = String((req.parameter || {}).kinds || '').split(',')
               .filter(function (k) { return PUBLIC[k] === 1; });
  var sh = sheet_(), n = sh.getLastRow() - 1, events = [];
  if (want.length && n > 0) {
    sh.getRange(2, 1, n, HEAD.length).getValues().forEach(function (r) {
      if (want.indexOf(r[1]) < 0) return;
      var data = null;
      try { data = JSON.parse(r[5]); } catch (err) { return; }
      events.push({ id: r[2], kind: r[1], uid: r[3], t: Number(r[4]), data: data });
    });
  }
  return out_({ ok: true, events: events });
}
