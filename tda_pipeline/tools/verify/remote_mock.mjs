// remote_mock.mjs — apps_script.gs 를 실제로 돌리는 모의 서버 (Google 서비스만 스텁)
// 사용: node remote_mock.mjs <apps_script.gs>   · GET /rows 로 시트 내용을 본다
import http from 'http'; import fs from 'fs'; import vm from 'vm';
const rows = [];
const sheet = { appendRow: r => rows.push(r), getLastRow: () => rows.length,
  getRange: (r0, c0, n, m) => ({
    setValues: v => { v.forEach((row, i) => rows[r0 - 1 + i] = row); },
    getValues: () => rows.slice(r0 - 1, r0 - 1 + n) }) };
let made = false;
const ctx = {
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: () => made ? sheet : null,
                                                  insertSheet: () => { made = true; return sheet; } }) },
  ContentService: { MimeType: { JSON: 'json' }, createTextOutput: s => ({ s, setMimeType() { return this; } }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  JSON, Array, Date, String, Number, isFinite,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);
let preflights = 0;
http.createServer((q, s) => {
  if (q.method === 'OPTIONS') { preflights++; s.writeHead(405); return s.end(); } // Apps Script 는 preflight 를 못 받는다
  const u = new URL(q.url, 'http://x');
  if (u.pathname === '/rows') { s.writeHead(200, {'Content-Type':'application/json'});
    return s.end(JSON.stringify({ rows, preflights })); }
  let body = ''; q.on('data', c => body += c); q.on('end', () => {
    const out = q.method === 'POST' ? ctx.doPost({ postData: { contents: body } })
                                    : ctx.doGet({ parameter: Object.fromEntries(u.searchParams) });
    s.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    s.end(out.s);
  });
}).listen(8788, () => console.log('mock on 8788'));
