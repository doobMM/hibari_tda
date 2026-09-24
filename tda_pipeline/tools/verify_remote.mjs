// verify_remote.mjs — 참여 백엔드 전 구간 확인 (shared/remote.js · arena · echo · apps_script.gs)
//   실행: 저장소 루트에서  node tda_pipeline/tools/verify_remote.mjs
//   apps_script.gs 를 **그대로** node 에서 돌리는 모의 서버(verify/remote_mock.mjs, Google 서비스만 스텁)를
//   다른 출처(8788)에 띄우고, 정적 서버(8787)의 실제 페이지를 Chromium 으로 누른다.
//   모의 서버는 OPTIONS 를 거절한다 — Apps Script 처럼 preflight 를 못 받는 조건을 재현한다.
//   ⚠ 실제 Google 서버의 302 리다이렉트는 재현하지 않는다. 실배포 후 한 번은 사람 눈으로 확인할 것.
import { spawn } from 'child_process';
import { createRequire } from 'module';
const kids = [spawn('node', ['tda_pipeline/tools/verify/remote_mock.mjs', 'tda_pipeline/tools/backend/apps_script.gs']),
              spawn('python3', ['-m', 'http.server', '8787'])];
process.on('exit', () => kids.forEach(k => k.kill()));
await new Promise(r => setTimeout(r, 1500));
const require = createRequire(process.env.PW_ROOT || '/opt/node22/lib/node_modules/');  // 전역 playwright
const { chromium } = require('playwright');
const B = 'http://localhost:8787/tda_pipeline/', M = 'http://localhost:8788/';
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) process.exitCode = 1; };
const rows = async () => (await (await fetch(M + 'rows')).json());
const br = await chromium.launch();
let errs = [];
async function page(ctx, url) {
  const p = await ctx.newPage(); p.on('pageerror', e => errs.push(url + ' ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(url + ' ' + m.text()); });
  await p.goto(B + url); await p.waitForTimeout(1500); return p;
}
const ls = (p, k) => p.evaluate(k => JSON.parse(localStorage.getItem(k)), k);

// ── 1. 로컬 폴백 + 예전 판 복구 ───────────────────────────────
const c1 = await br.newContext({ locale: 'en-US' });
let p = await page(c1, 'arena/');
const seedId = (await p.evaluate(() => __arena.state().pieces[0].id));
const mineId = 'p3_d1.00_t1.00_g1.00_a2_s424242';
await p.evaluate(([a, m]) => localStorage.setItem('arena.v1', JSON.stringify({
  votes: 20, mine: { [m]: 1 }, votedIds: { [a]: 1 },
  pieces: [{ id: a, elo: 1530, wins: 3, losses: 1, parent: null },
           { id: m, elo: 1490, wins: 0, losses: 2, parent: a }] })), [seedId, mineId]);
await p.reload(); await p.waitForTimeout(1500);
let out = await ls(p, 'remote.outbox');
ok(out.some(e => e.kind === 'legacy' && e.data.votes === 20), 'legacy 20표가 outbox 에 올라갈 준비');
ok(out.some(e => e.kind === 'sow' && e.data.id === mineId), '예전 판에서 심은 조각이 sow 로 되살아남');
ok(await p.evaluate(m => !!__arena.state().mine[m] && __arena.state().votes === 20, mineId), '개인 기록: 내 조각 + 20표 유지');
await p.reload(); await p.waitForTimeout(1200);
out = await ls(p, 'remote.outbox');
ok(out.filter(e => e.kind === 'legacy').length === 1, '다시 열어도 legacy 는 한 번만');
ok(await p.evaluate(() => __arena.seedVotes(5)) === 25, '로컬 모드에서 투표 5회 (시험 도우미)');
ok((await ls(p, 'remote.outbox')).filter(e => e.kind === 'vote').length === 5, 'vote 이벤트 5개 쌓임');
ok(/이 브라우저에만/.test(await p.textContent('#store')), '로컬 모드 안내 문구');

let e = await page(c1, 'echo.html');
ok(await e.textContent('#say') === 'Tap anywhere' && await e.title() === 'Echo', 'en 브라우저 → 영어');
await e.mouse.click(100, 100); await e.mouse.click(200, 300); await e.mouse.click(300, 200);
await e.waitForTimeout(500);
ok(/dots · \d+ rings/.test(await e.textContent('#cnt')), '카운터 영어: ' + await e.textContent('#cnt'));
await e.click('#clr');
out = await ls(e, 'remote.outbox');
const ev = out.filter(x => x.kind === 'echo');
ok(ev.length === 1 && ev[0].data.drops.length === 3 && ev[0].data.lang === 'en', 'echo 한 판 = 이벤트 1개, 점 3개');
const k = await page(c1, 'echo.html?lang=ko');
ok(await k.textContent('#say') === '아무 데나 누르세요' && await k.textContent('#clr') === '비우기', '?lang=ko 강제');

// ── 2. 서버 연결 — 쌓인 outbox 가 올라간다 ─────────────────────
await c1.addInitScript(u => { window.REMOTE_ENDPOINT = u; }, M + 'exec');
p = await page(c1, 'arena/');
await p.waitForTimeout(1500);
let r = await rows();
ok((await ls(p, 'remote.outbox')).length === 0, 'outbox 비워짐');
ok(r.rows.length - 1 === out.length, `시트에 ${r.rows.length - 1}줄 = 쌓였던 ${out.length}개`);
ok(r.preflights === 0, 'CORS preflight 0회 (Apps Script 호환)');
ok(/모두와 함께/.test(await p.textContent('#store')), '공유 모드 안내 문구');
ok(await p.evaluate(() => __arena.seedVotes(3)) === 'off', '공유 모드에서 가짜 표 도우미 차단');

// ── 3. 다른 사람(새 브라우저)이 같은 사다리를 본다 ───────────────
const c2 = await br.newContext({ locale: 'ko-KR' });
await c2.addInitScript(u => { window.REMOTE_ENDPOINT = u; }, M + 'exec');
const q = await page(c2, 'arena/');
await q.waitForTimeout(1500);
const s1 = await p.evaluate(() => __arena.state().pieces.map(x => x.id + ':' + x.elo + ':' + x.wins).sort().join());
const s2 = await q.evaluate(() => __arena.state().pieces.map(x => x.id + ':' + x.elo + ':' + x.wins).sort().join());
ok(s1 === s2, '두 브라우저의 사다리가 같다');
ok(await q.evaluate(m => __arena.state().pieces.some(x => x.id === m) && !__arena.state().mine[m], mineId),
   '남의 조각은 보이되 "내 것"이 아니다');
ok(await q.evaluate(() => __arena.state().votes) === 0, '새 사람의 개인 표 수 0');
const tot = await q.evaluate(() => __arena.state().pieces.reduce((a, x) => a + x.wins, 0));
ok(tot === 5, `재생된 승 합계 = vote 이벤트 5 (legacy 20 은 합계뿐이라 재생 불가): ${tot}`);
// 브라우저 2 가 실제 UI 로 투표 → 브라우저 1 이 사다리 탭에서 받음
await q.click('#enter'); await q.waitForTimeout(300);
const pairIds = await q.evaluate(() => { const b = document.querySelector('.pick[data-w="A"]'); b.click(); return 1; });
await q.waitForTimeout(800);
await p.click('#enter'); await p.click('.tabs button[data-p="ladder"]'); await p.waitForTimeout(1200);
const tot1 = await p.evaluate(() => __arena.state().pieces.reduce((a, x) => a + x.wins, 0));
ok(tot1 === 6, '브라우저 2 의 표가 브라우저 1 사다리에 반영: ' + tot1);

// ── 4. echo 배치는 공개 GET 으로 나가지 않는다 ─────────────────
const g = await (await fetch(M + 'exec?kinds=echo,legacy,vote')).json();
ok(g.events.every(x => x.kind === 'vote'), 'GET 은 PUBLIC(sow·vote) 만');
// ── 5. 서버 입력 검증 ─────────────────────────────────────────
const bad = await (await fetch(M + 'exec', { method: 'POST', body: JSON.stringify([
  { id: 'abcdef12', kind: 'hack', uid: 'u1234567', t: 1, data: {} },
  { id: '<script>', kind: 'vote', uid: 'u1234567', t: 1, data: {} },
  { id: 'abcdef13', kind: 'echo', uid: 'u1234567', t: 1, data: 'x'.repeat(9000) },
  { id: 'abcdef14', kind: 'vote', uid: 'u1234567', t: 1, data: { a: '"><img src=x onerror=alert(1)>', b: 'x', w: 'A' } }]) })).json();
ok(bad.n === 1 && bad.dropped === 3, '불량 3개 거부, 형식 맞는 1개만 저장');
await p.reload(); await p.waitForTimeout(1500);
ok(await p.evaluate(() => !document.querySelector('img[src="x"]') && __arena.state().pieces.every(x => /^p-?\d/.test(x.id))),
   '가짜 id 를 담은 표는 사다리에 들어오지 않는다 (클라이언트 검증)');
errs = errs.filter(x => !/404/.test(x));   // favicon.ico — 이 변경 전부터 있던 404
ok(errs.length === 0, '콘솔 에러 0 ' + errs.join(' | '));
await br.close();
process.exit(process.exitCode || 0);
