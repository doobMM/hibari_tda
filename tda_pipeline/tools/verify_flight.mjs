// tools/verify_flight.mjs — 날갯짓(sketch/flight-core.js · sketch/flight.html) 판정기.   node tools/verify_flight.mjs
//   (V1 은 python + ripser 0.6.14 를 부른다: tools/verify/flight_ripser_check.py. PYTHON 환경변수로 실행 파일을 바꿀 수 있다.)
//
// ── 예측 (2026-10-07, 이 판정기를 처음 돌리기 **전에** 적었다 — 나중에 고치지 않는다) ─────────────────────────────
//  V1  무작위 점구름 20개(3차원, 15–40점): vrH1 의 지속 > 1e-9 막대가 ripser 와 전부 같다. 거리를 양쪽 다 float32 로 쓰므로 |차| = 0 일 것(문턱 1e-9).
//  V2  원 20점 → 막대 1개, 탄생 = 2·sin(π/20) (float32 반올림 안: |차| < 1e-6) · 선분 20점 → 0개 · 떨어진 원 둘 → 2개 · 8자(한 점 공유) → 2개.
//  V3  바닥에서 박에 맞춰 누르고 12박 → 내리치기 칸 0,1,2,3,4,5 (높이 −1, −0.5, −1/6, 1/6, 1/2, 5/6) ·
//      이어 4박 떼면 칸 0, 칸 0 한가운데(−5/6)에서 0.05 안(해석식이라 거의 0) ·
//      목표 고정(빛 (−0.7, ·, 0) 이 +z 로 — 목표와 직각, 목표 (0.7, 0), 거리 1.4) → 3초 뒤 수평 거리 ≤ 0.7 (어림 0.5).
//  V4  두 구절 × 칸 k=0..5 열둘: 칸 k 한가운데에서 누름 → H.mod[0].steps[16·구절 + 2k] 화음, 다음 박 → steps[16·구절 + 2k + 1] 단음,
//      떼고 3박 → 내 음 0개. 구절 바꾸기: 1박 떼고 다시 누르면 같은 구절, 3박 떼면 바뀐다.
//  V5  예시 첫 32박 = 오른손 32스텝 (음높이 32/32).                                                  ⚠ 맹검 아님 — 설계 중 탐색에서 32/32 를 보았다
//  V6  예시 고리: 박 32 에 L=32·P=33 이 생기고, 박 33..191(159박) 동안 그 고리의 음 = 왼손 steps[b mod 33] (159/159). ⚠ 맹검 아님(탐색에서 159/159)
//  V7  내 바퀴 k=1..5(박 32k)마다, 고리 1 이 모듈 첫 화음 [미3 시3 레4 솔4] 을 내는 첫 박 − 32k = 2, 3, 4, 5, 6 (바퀴마다 +1).
//  V8  같은 직선을 오고 가는 비행(맨 위에서 누른 채, 16박 왕복, 80박): 되돌아옴 후보 ≥ 3, 고리 0, 후보 지속 최댓값 < θ(0.3) — 어림 < 0.1.
//  V9  목표 고정 + 계속 누름(맨 위에서 맴돌기) 110박: 생김 1번, 다시 그림 ≥ 2번(어림 5), L = 16 · P = 17.  ⚠ 맹검 아님(탐색에서 생김 1 + 다시 그림 5)
//  V10 (a) 예시 고리 1 의 무게중심 0.6 위에서 곧게 내리지르면 지남 1 · (b) 고리 바깥(모서리)에서 내리지르면 0 ·
//      (c) 손 떼고 고리 밖에 앉혀 두면 박 33 + 8·33 = 297 에 사라진다(296 엔 있다) · (d) 목표 넷을 차례로 맴돌면 생김 ≥ 4, 살아 있는 고리는 늘 ≤ 3, 끝에 3.
//  V11 박 사이(0.2박)에서 누르면 그 호출이 내리치기 화음(4음, now=true)을 곧바로 돌려준다.
//  V12 flight.html 스크립트 문법 OK · HS.audio.wake 는 unlock 안에 한 번 · unlock 은 제스처 처리기(onPointerDown·onKeyDown·onListen·onPlay·onClear)
//      안에서만 · 그 처리기들은 addEventListener / HS.keys 인자로만 쓰인다 · voice 는 sing 안에서만, sing 은 `if (!sound) return` 으로 시작 ·
//      ev.key 를 쓰지 않는다 · 첫 조작 전 글자(제목+힌트+태그) ≤ 20 · 단추 min-height 44px.
//  V13 (덧붙임 — 브라우저를 못 쓰므로) 가짜 DOM 에서 페이지를 ?silent 로 띄운다: 25초 예시 동안 소리 호출 0(자동 재생 없음)·예시 고리 생김 ·
//      캔버스 pointerdown 그 호출 안에서 호출 ≥ 3, 지연 ≤ 0.006초 · Space 도 같다 · 훅 advance/probe 가 돈다 · 예외 0.
//  V14 (덧붙임, 첫 실행 뒤 V1–V13 이 전부 PASS 인 것을 보고 나서 적었다 — 아래 둘은 새 항목이라 아직 돌리지 않았다)
//      가짜 DOM: → 를 1초 누르면 목표점이 ≥ 0.5 옮겨 가고 빛의 방향이 1초 안에 ≥ 0.3 rad 바뀐다 · 손가락(touch) 누름 → 목표가 바뀌고 hold,
//      곧바로 소리 ≥ 3 · '고리 지우기' → 고리 0 · '▶ 예시 듣기' → 모드 demo, 단추 '♪ 듣는 중'(눌리지 않음) · '직접 하기' → 모드 play.
//  V15 (덧붙임) 누른 판 / 안 누른 판: 같은 상태에서 한쪽만 한 번 누른다(2박 누르고 뗌). 그 뒤 16박 동안 두 판의 차이는
//      누른 그 두 박(화음 + 단음)뿐이고, 고리 소리는 박마다 같다(16/16).
//  V15′ (사후 — V15 가 FAIL(달라진 박 셋: 35·36·37)인 것을 보고 원인을 확인하려고 적었다. V15 는 그대로 둔다)
//      원인 가설: V15 는 다음 내리치기 박(37)의 바로 그 순간에 뗐고, 엔진은 그 순간 아직 누르고 있다고 보아 37 의 화음을 냈다.
//      예측: 1.5박 만에 떼면(37 전에) 달라진 박은 정확히 둘(35 화음 · 36 단음)이고 고리 소리는 16/16 같다.
//
// 판정 결과를 보고 엔진 상수를 바꾸면 그 사실과 전후 값을 보고에 적는다(조정한 자료로 시험한 것이 된다).
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const ROOT = new URL('..', import.meta.url);
const HS = require('../sketch/common.js'), F = require('../sketch/flight-core.js');
const D = JSON.parse(readFileSync(new URL('lenia/tonnetz.json', ROOT), 'utf8')), H = HS.derive(D), SEC = HS.SEC;
let bad = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) { bad++; process.exitCode = 1; } };
const pitches = ls => ls.map(li => H.notes[li].pitch).join(',');
const sortBars = b => [...b].sort((x, y) => x[0] - y[0] || x[1] - y[1]);
const fix = (v, n = 3) => (+v).toFixed(n);

/** 박 경계로 감는다 (그 박의 처리가 끝난 자리) */
function toBeat(E) { const b = E.state.beat + 1; E.advance(b * SEC - E.state.time); return b; }
/** n 박을 박마다 감으며 그 박에 나온 음·사건을 모은다 */
function beats(E, n, each) { for (let i = 0; i < n; i++) { E.advance(SEC); const o = E.drain(); if (each) each(E.state.beat, o); } }

// ── V1 VR H₁ = ripser ─────────────────────────────────────────────────────────────────────
{
  const r = HS.rng(20261007), clouds = [];
  for (let c = 0; c < 20; c++) { const n = 15 + Math.floor(r() * 26), P = []; for (let i = 0; i < n; i++) P.push([r() * 2 - 1, r() * 2 - 1, r() * 2 - 1]); clouds.push(P); }
  let out = null, err = '';
  try { out = JSON.parse(execFileSync(process.env.PYTHON || 'python', [fileURLToPath(new URL('tools/verify/flight_ripser_check.py', ROOT))], { input: JSON.stringify({ clouds }), maxBuffer: 1 << 26 }).toString()); }
  catch (e) { err = String(e.message || e).slice(0, 200); }
  if (!out) ok(false, `V1 ripser 를 부르지 못했다: ${err}`);
  else {
    let same = 0, nb = 0, maxd = 0;
    clouds.forEach((P, c) => { const a = sortBars(F.vrH1(P).filter(b => b[1] - b[0] > 1e-9)), b = sortBars(out.bars[c]); nb += b.length;
      if (a.length !== b.length) return; let m = 0; a.forEach((x, i) => { m = Math.max(m, Math.abs(x[0] - b[i][0]), Math.abs(x[1] - b[i][1])); });
      maxd = Math.max(maxd, m); if (m < 1e-9) same++; });
    ok(same === 20, `V1 VR H₁ = ripser ${out.ripser}: 점구름 ${same}/20 막대 전부 같음 (ripser 막대 ${nb}개, 최대 |차| ${maxd.toExponential(2)})`);
  }
}
// ── V2 답이 알려진 모양 ───────────────────────────────────────────────────────────────────
{
  const circ = (cx, cy, r, n, skip0) => { const P = []; for (let i = skip0 ? 1 : 0; i < n; i++) P.push([cx + r * Math.cos(2 * Math.PI * i / n), cy + r * Math.sin(2 * Math.PI * i / n), 0]); return P; };
  const c1 = F.vrH1(circ(0, 0, 1, 20)), want = 2 * Math.sin(Math.PI / 20);
  ok(c1.length === 1 && Math.abs(c1[0][0] - want) < 1e-6, `V2 원 20점 → 막대 ${c1.length}개, 탄생 ${c1[0] && fix(c1[0][0], 7)} (2·sin(π/20) = ${fix(want, 7)}), 죽음 ${c1[0] && fix(c1[0][1], 4)}`);
  const seg = []; for (let i = 0; i < 20; i++) seg.push([i / 19, 0, 0]);
  ok(F.vrH1(seg).length === 0, `V2 선분 20점 → 막대 ${F.vrH1(seg).length}개`);
  const two = F.vrH1([...circ(-3, 0, 1, 20), ...circ(3, 0, 1, 20)]);
  ok(two.length === 2, `V2 떨어진 원 둘 → 막대 ${two.length}개 (지속 ${two.map(b => fix(b[1] - b[0])).join(', ')})`);
  const eight = F.vrH1([...circ(-1, 0, 1, 20), ...circ(-1, 0, 1, 20).map(p => [-p[0], p[1], 0]).filter((p, i) => i > 0)]);
  // 8자: 왼쪽 원(가운데 −1)은 θ=0 에서 원점을 지난다. 오른쪽 원은 그 거울상 x → −x (가운데 +1) — 원점 하나를 함께 쓴다(중복점 제거)
  ok(eight.length === 2, `V2 8자 → 막대 ${eight.length}개 (지속 ${eight.map(b => fix(b[1] - b[0])).join(', ')})`);
}
// ── V3 물리 ──────────────────────────────────────────────────────────────────────────────
{
  const E = F.create(H); E.place({ x: 0, y: -1, z: 0, head: 0 }); E.target(0.5, 0); toBeat(E);
  const ks = [], ys = []; E.press(); ks.push(E.probe().band); ys.push(E.state.y);
  for (let i = 1; i <= 11; i++) { E.advance(SEC); E.drain(); if (i % 2 === 0) { ks.push(E.probe().band); ys.push(E.state.y); } }
  E.advance(SEC); E.drain();                                   // 박 12: 올리기 끝 = 맨 위
  ok(ks.join() === '0,1,2,3,4,5', `V3 바닥에서 12박 누름 → 내리치기 칸 ${ks.join(',')} · 높이 ${ys.map(y => fix(y)).join(', ')}`);
  const yTop = E.state.y; E.release(); E.advance(4 * SEC); E.drain();
  const y4 = E.state.y;
  ok(E.probe().band === 0 && Math.abs(y4 - E.mid(0)) < 0.05, `V3 맨 위(${fix(yTop)})에서 4박 뗌 → 높이 ${fix(y4, 4)} 칸 ${E.probe().band} (칸 0 한가운데 ${fix(E.mid(0), 4)}, 차 ${fix(Math.abs(y4 - E.mid(0)), 5)})`);
  const E2 = F.create(H); E2.place({ x: -0.7, y: 0, z: 0, head: Math.PI / 2 }); E2.target(0.7, 0); E2.press(); E2.advance(3); E2.drain();
  const d = Math.hypot(E2.state.x - 0.7, E2.state.z);
  ok(d <= 0.7, `V3 목표 고정(직각 출발, 거리 1.4) → 3초 뒤 수평 거리 ${fix(d)} (≤ 0.7)`);
}
// ── V4 음 고르기 ─────────────────────────────────────────────────────────────────────────
{
  let good = 0, msgs = [];
  for (let ph = 0; ph < 2; ph++) for (let k = 0; k < 6; k++) {
    const E = F.create(H); toBeat(E); E.place({ x: 0, y: E.mid(k), z: 0, head: 0 }); E.state.ph = ph;
    const down = E.press(), cOk = down.map(n => n.li).join() === H.mod[0].steps[16 * ph + 2 * k].join();
    E.advance(SEC); const up = E.drain().notes.filter(n => n.src === 'me'), sOk = up.map(n => n.li).join() === H.mod[0].steps[16 * ph + 2 * k + 1].join();
    E.release(); let quiet = 0; beats(E, 3, (b, o) => { quiet += o.notes.filter(n => n.src === 'me').length; });
    if (cOk && sOk && quiet === 0) good++; else msgs.push(`구절${ph + 1} 칸${k}: 화음 ${cOk} 단음 ${sOk} 활공음 ${quiet}`);
  }
  ok(good === 12, `V4 내리치기 = 그 칸 화음 · 올리기 = 같은 자리 단음 · 활공 = 무음: ${good}/12 ${msgs.join(' | ')}`);
  const E = F.create(H); toBeat(E); E.place({ x: 0, y: E.mid(2), z: 0, head: 0 });
  E.press(); const p0 = E.probe().phrase; beats(E, 4); E.release(); beats(E, 1); E.press(); const p1 = E.probe().phrase;
  beats(E, 2); E.release(); beats(E, 3); E.press(); const p2 = E.probe().phrase;
  ok(p0 === 0 && p1 === 0 && p2 === 1, `V4 구절 바꾸기: 처음 ${p0} → 1박 활공 뒤 ${p1}(같음) → 3박 활공 뒤 ${p2}(바뀜)`);
}
// ── V5–V7 예시 ───────────────────────────────────────────────────────────────────────────
function runDemo(nBeats) {
  const E = F.create(H); E.demo(true); const start = E.state.beat + 1, me = {}, ring = {}, ev = [];
  for (let i = 0; i < nBeats * 8; i++) { E.advance(SEC / 8); const o = E.drain();
    o.notes.forEach(n => { const b = Math.round(n.at / SEC) - start; if (n.src === 'me') (me[b] = me[b] || []).push(n.li); else if (n.src === 'ring') { const R = ring[n.ring] = ring[n.ring] || {}; (R[b] = R[b] || []).push(n.li); } });
    o.events.forEach(e => ev.push({ ...e, b: Math.round(e.at / SEC) - start })); }
  return { E, start, me, ring, ev };
}
{
  const { me, ring, ev } = runDemo(200);
  let a = 0; for (let b = 0; b < 32; b++) if (pitches(me[b] || []) === pitches(H.mod[0].steps[b])) a++;
  ok(a === 32, `V5 예시 첫 32박 = hibari 오른손 32스텝: ${a}/32`);
  const born = ev.filter(e => e.type === 'born'), b1 = born[0];
  ok(!!b1 && b1.b === 32 && b1.L === 32 && b1.P === 33, `V6 첫 고리: 박 ${b1 && b1.b} 에 L=${b1 && b1.L} · P=${b1 && b1.P} (지속 ${b1 && fix(b1.pers)})`);
  let s6 = 0, n6 = 0; const R1 = ring[b1 ? b1.ring : 1] || {};
  for (let b = 33; b < 192; b++) { n6++; if (pitches(R1[b] || []) === pitches(H.mod[1].steps[b % 33])) s6++; }
  ok(s6 === n6 && n6 >= 33, `V6 고리 1 의 되풀이 = hibari 왼손(앞에 쉼 한 칸, 33박): 박 33..191 ${s6}/${n6}`);
  const first = pitches(H.mod[0].steps[0]), offs = [];
  for (let k = 1; k <= 5; k++) { let b = 32 * k; while (b < 32 * k + 40 && pitches(R1[b] || []) !== first) b++; offs.push(b - 32 * k); }
  const steps = offs.slice(1).map((o, i) => o - offs[i]);
  ok(offs.join() === '2,3,4,5,6' && steps.every(s => s === 1), `V7 나(32박)와 고리(33박)의 어긋남: 바퀴 1..5 에 ${offs.join(',')} 박 (차 ${steps.join(',')})`);
  console.log(`     예시 사건(192박 한 주기): ${ev.filter(e => e.b < 193).map(e => e.type + '@' + e.b + (e.P ? '/P' + e.P : '')).join(' ')}`);
}
// ── V8 같은 길을 오고 가기 ────────────────────────────────────────────────────────────────
{
  const E = F.create(H); E.place({ x: -0.6, y: 0.9, z: 0, head: 0 }); E.press(); const t0 = E.state.time;
  E.pilot(t => { const u = (t - t0) / (16 * SEC), f = u - Math.floor(u); return { x: -0.6 + 1.2 * (f < 0.5 ? 2 * f : 2 - 2 * f), z: 0, head: f < 0.5 ? 0 : Math.PI }; });
  let mx = 0, born = 0, last = null;
  beats(E, 80, (b, o) => { born += o.events.filter(e => e.type === 'born').length; const lc = E.probe().lastCand; if (lc && lc !== last) { last = lc; mx = Math.max(mx, lc.pers); } });
  const cand = E.probe().cand;
  ok(cand >= 3 && born === 0 && E.probe().rings.length === 0 && mx < 0.3, `V8 같은 직선 왕복 80박: 후보 ${cand} · 고리 ${born} · 후보 지속 최댓값 ${fix(mx, 4)} (< θ 0.3)`);
}
// ── V9 같은 원을 여러 바퀴 ────────────────────────────────────────────────────────────────
{
  const E = F.create(H); E.place({ x: 0.2, y: -0.83, z: 0.5, head: 0 }); E.target(0, 0); E.press();
  let born = 0, redraw = 0; beats(E, 110, (b, o) => o.events.forEach(e => { if (e.type === 'born') born++; if (e.type === 'redraw') redraw++; }));
  const R = E.probe().rings;
  ok(born === 1 && redraw >= 2 && R.length === 1 && R[0].L === 16 && R[0].P === 17, `V9 목표 고정 맴돌기 110박: 생김 ${born} · 다시 그림 ${redraw} · 고리 ${R.length}개 L=${R[0] && R[0].L} P=${R[0] && R[0].P} 지속 ${R[0] && fix(R[0].pers)}`);
}
// ── V10 지남 · 수명 · 셋까지 ───────────────────────────────────────────────────────────────
function demoRing() { const E = F.create(H); E.demo(true); const start = E.state.beat + 1; E.advance((start + 33) * SEC - E.state.time); E.drain(); E.demo(false); return { E, start }; }
function dive(x, z) {
  const { E } = demoRing(), R = E.rings()[0], c = R.plane.c; E.place({ x, y: c[1] + 0.6, z, head: 0 }); const t0 = E.state.time;
  E.pilot(t => ({ x: x + 0.15 * (t - t0), z, head: 0 }));                      // 곧게: x 쪽으로 천천히 가며 떨어진다
  let pass = 0; beats(E, 8, (b, o) => { pass += o.events.filter(e => e.type === 'pass').length; });
  return { pass, c, n: R.plane.n, life: E.rings()[0] && E.rings()[0].life };
}
{
  const { E: E0 } = demoRing(), c = E0.rings()[0].plane.c;
  const inR = dive(c[0], c[2]), outR = dive(0.9, 0.9);
  ok(inR.pass === 1, `V10a 고리 1(무게중심 ${c.map(v => fix(v, 2))}, 법선 ${inR.n.map(v => fix(v, 2))}) 가운데로 곧게 내리지름 → 지남 ${inR.pass} (수명 8 → ${inR.life})`);
  ok(outR.pass === 0, `V10b 고리 바깥(0.9, 0.9)으로 내리지름 → 지남 ${outR.pass}`);
  const { E, start } = demoRing(); E.place({ x: 0.9, y: -1, z: 0.9, head: 0 }); let gone = -1, at296 = null;
  for (let b = 34; b <= 300; b++) { E.advance((start + b) * SEC - E.state.time); const o = E.drain(); if (b === 296) at296 = E.rings().length; if (gone < 0 && o.events.some(e => e.type === 'fade')) gone = b; }
  ok(gone === 297 && at296 === 1, `V10c 고리 1 을 그냥 두면 박 ${gone} 에 사라진다 (296 엔 ${at296}개) — 33 + 8·33 = 297`);
  const E4 = F.create(H); E4.place({ x: 0, y: 0.9, z: 0, head: 0 }); E4.press();
  let born4 = 0, maxAlive = 0, fades = 0;
  [[-0.25, -0.25], [0.25, -0.25], [0.25, 0.25], [-0.25, 0.25], [-0.25, -0.25]].forEach(t => { E4.target(t[0], t[1]);
    beats(E4, 48, (b, o) => { o.events.forEach(e => { if (e.type === 'born') born4++; if (e.type === 'fade') fades++; }); maxAlive = Math.max(maxAlive, E4.rings().length); }); });
  ok(born4 >= 4 && maxAlive <= 3 && E4.rings().length === 3, `V10d 목표 넷을 차례로 맴돎: 생김 ${born4} · 살아 있는 고리 최대 ${maxAlive} · 끝 ${E4.rings().length} · 사라짐 ${fades}`);
}
// ── V11 누르는 호출이 곧바로 ─────────────────────────────────────────────────────────────
{
  const E = F.create(H); E.place({ x: 0, y: -1, z: 0, head: 0 }); toBeat(E); E.advance(0.2 * SEC);
  const ns = E.press();
  ok(ns.length === 4 && ns.every(n => n.now) && pitches(ns.map(n => n.li)) === pitches(H.mod[0].steps[0]), `V11 박 사이에서 누름 → 그 호출이 ${ns.length}음 [${ns.map(n => n.name).join(' ')}] 을 now=${ns.every(n => n.now)} 로 돌려준다`);
}
// ── V12 페이지 코드 검사 ─────────────────────────────────────────────────────────────────
const HTML = readFileSync(new URL('sketch/flight.html', ROOT), 'utf8');
const INLINE = [...HTML.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
{
  let syn = true; INLINE.forEach(s => { try { new Function(s); } catch (e) { syn = false; console.log('     문법:', e.message); } });
  ok(syn && INLINE.length === 1, `V12 스크립트 문법 (인라인 ${INLINE.length}개)`);
  const src = INLINE[0] || '', s = strip(src), fs = funcs(s), at = (re) => [...s.matchAll(re)].map(m => m.index);
  const inner = i => { let best = null; fs.forEach(f => { if (f.name && f.a < i && i < f.b && (!best || f.b - f.a < best.b - best.a)) best = f; }); return best ? best.name : null; };
  const wakes = at(/HS\.audio\.wake\(/g), unl = at(/\bunlock\(/g).filter(i => !/function\s*$/.test(s.slice(Math.max(0, i - 12), i)));
  const G = ['onPointerDown', 'onKeyDown', 'onListen', 'onPlay', 'onClear'];
  const wakeOk = wakes.length === 1 && inner(wakes[0]) === 'unlock', unlOk = unl.length > 0 && unl.every(i => G.includes(inner(i)));
  const refsOk = G.every(g => at(new RegExp('\\b' + g + '\\b', 'g')).every(i => { const before = src.slice(Math.max(0, i - 40), i);
    return /function\s*$/.test(before) || /addEventListener\('(pointerdown|pointerup|click|keydown|touchend)',\s*$/.test(before) || /HS\.keys\(\s*$/.test(before); }));
  ok(wakeOk && unlOk && refsOk, `V12 wake 는 unlock 안에 ${wakes.length}번(${wakes.map(inner)}) · unlock 부르는 곳 ${unl.length}곳 = ${[...new Set(unl.map(inner))].join(',')} · 처리기는 듣기 인자로만 ${refsOk}`);
  const voices = at(/HS\.audio\.voice\(/g), singF = fs.find(f => f.name === 'sing');
  ok(voices.length > 0 && voices.every(i => inner(i) === 'sing') && !!singF && /^\{\s*if \(!sound\) return;/.test(s.slice(singF.a, singF.a + 30)), `V12 voice ${voices.length}곳 전부 sing 안 · sing 은 if (!sound) return 으로 시작`);
  ok(!/\b(ev|e|event)\.key\b/.test(s), 'V12 ev.key 를 쓰지 않는다(키는 HS.keys → ev.code)');
  const txt = t => (t || '').replace(/<[^>]+>/g, '').replace(/\s+/g, '');
  const h1 = txt((HTML.match(/<h1>([\s\S]*?)<\/h1>/) || [])[1]), hint = txt((HTML.match(/<span id="hint">([\s\S]*?)<\/span>/) || [])[1]), tag = txt((HTML.match(/<div id="tag">([\s\S]*?)<\/div>/) || [])[1]);
  ok((h1 + hint + tag).length <= 20, `V12 첫 조작 전 글자: "${h1}" + "${hint}" + "${tag}" = ${(h1 + hint + tag).length}자 (≤ 20, 공백 빼고)`);
  ok(/button\{[^}]*min-height:44px/.test(HTML), 'V12 단추 min-height 44px');
}
// ── V13 가짜 DOM 에서 페이지 띄우기 (?silent) ─────────────────────────────────────────────
{
  const P = await bootPage('?silent'), w = P.ctx;
  let exc = 0; const run = sec => { for (let i = 0; i < Math.round(sec * 60); i++) { try { P.tick(1000 / 60); } catch (e) { if (exc++ < 3) console.log('     예외:', e.stack.split('\n').slice(0, 3).join(' / ')); } } };
  run(25);
  const p0 = w.__sk.probe(), calls0 = w.HS.audio.calls.length, say = P.el('say').textContent;
  ok(p0.mode === 'demo' && calls0 === 0 && p0.rings.length >= 1 && /33박마다/.test(P.sayLog.join('|')), `V13 들어와 25초 예시: 모드 ${p0.mode} · 소리 호출 ${calls0} · 고리 ${p0.rings.length}개(P=${p0.rings.map(r => r.P)}) · 사건 글 "${P.sayLog.slice(0, 2).join(' / ')}"`);
  const before = w.HS.audio.calls.length;
  P.el('cv').fire('pointerdown', { button: 0, pointerId: 7, pointerType: 'mouse', clientX: 190, clientY: 300, preventDefault() {} });
  const now = w.HS.audio.calls.slice(before), p1 = w.__sk.probe();
  // 누름 처리 안에서 예시 고리들이 사라지며(사건 ④) 낮은 음을 박 격자에 예약하고(≈0.06초 앞), 내리치기 화음은 곧바로(0.005초) 울린다 — 곧바로 울린 것을 센다
  const fast = now.filter(c => c.delay <= 0.006);
  ok(fast.length >= 3 && p1.mode === 'play' && p1.sound, `V13 캔버스 누름 → 그 호출 안에서 곧바로(≤0.006초) 소리 ${fast.length}개 [${fast.map(c => HS.noteName(c.pitch)).join(' ')}] · 그 밖 ${now.length - fast.length}개(지연 ${now.filter(c => c.delay > 0.006).map(c => fix(c.delay, 3)).join(',')}초) · 모드 ${p1.mode}`);
  run(3); P.el('cv').fire('pointerup', { pointerId: 7, pointerType: 'mouse' }); run(2);
  const b2 = w.HS.audio.calls.length; P.win('keydown', { code: 'Space', preventDefault() {}, ctrlKey: false, metaKey: false, altKey: false }); const k1 = w.HS.audio.calls.length - b2;
  run(1.5); P.win('keyup', { code: 'Space' }); run(1);
  w.__sk.advance(10); const p2 = w.__sk.probe();
  ok(k1 >= 3 && exc === 0 && typeof p2.step === 'number' && p2.pos.length === 3, `V13 Space → 그 호출 안에서 소리 ${k1}개 · 훅 advance(10) 뒤 박 ${p2.step} · 예외 ${exc} · 그리기 호출 ${P.drawn()}`);
}
// ── V14 방향키 · 손가락 · 단추 (가짜 DOM) ───────────────────────────────────────────────
{
  const P = await bootPage('?silent'), w = P.ctx; let exc = 0;
  const run = sec => { for (let i = 0; i < Math.round(sec * 60); i++) { try { P.tick(1000 / 60); } catch (e) { if (exc++ < 3) console.log('     예외:', e.stack.split('\n').slice(0, 3).join(' / ')); } } };
  run(2); P.el('play').fire('click', {}); run(1);
  const E = w.__sk.engine(), t0 = [E.state.tx, E.state.tz], h0 = E.state.head;
  P.win('keydown', { code: 'ArrowRight', preventDefault() {}, ctrlKey: false, metaKey: false, altKey: false }); run(1); P.win('keyup', { code: 'ArrowRight' });
  const moved = Math.hypot(E.state.tx - t0[0], E.state.tz - t0[1]), turned = Math.abs(Math.atan2(Math.sin(E.state.head - h0), Math.cos(E.state.head - h0)));
  ok(moved >= 0.5 && turned >= 0.3, `V14 → 1초: 목표점 ${fix(moved)} 옮김 (≥ 0.5) · 빛의 방향 ${fix(turned)} rad 바뀜 (≥ 0.3)`);
  const tb = [E.state.tx, E.state.tz], c0 = w.HS.audio.calls.length;
  P.el('cv').fire('pointerdown', { button: 0, pointerId: 3, pointerType: 'touch', clientX: 80, clientY: 420, preventDefault() {} });
  const fastT = w.HS.audio.calls.slice(c0).filter(c => c.delay <= 0.006).length, tch = Math.hypot(E.state.tx - tb[0], E.state.tz - tb[1]), held = E.state.hold;
  run(1); P.el('cv').fire('pointerup', { pointerId: 3, pointerType: 'touch' }); run(0.5);
  ok(tch > 0.05 && held && fastT >= 3 && !E.state.hold, `V14 손가락 누름 → 목표 ${fix(tch)} 옮김 · 날갯짓 ${held} · 곧바로 소리 ${fastT} · 떼면 활공 ${!E.state.hold}`);
  run(1); P.el('clear').fire('click', {}); run(0.2); const r0 = E.rings().length;
  P.el('listen').fire('click', {}); run(0.5); const pd = w.__sk.probe(), L = P.el('listen'), Ld = L.disabled, Lt = L.textContent;
  P.el('play').fire('click', {}); run(0.5); const pp = w.__sk.probe();
  ok(r0 === 0 && pd.mode === 'demo' && Ld === true && /듣는 중/.test(Lt) && pp.mode === 'play' && exc === 0,
    `V14 단추: 고리 지우기 → ${r0}개 · 예시 듣기 → ${pd.mode} '${Lt}' 눌림막음 ${Ld} · 직접 하기 → ${pp.mode} · 예외 ${exc}`);
}
// ── V15 누른 판 / 안 누른 판 ─────────────────────────────────────────────────────────────
{
  const mk = () => { const { E } = demoRing(); E.place({ x: 0.5, y: 0.3, z: -0.4, head: 1 }); E.target(-0.3, 0.2); toBeat(E); E.drain(); return E; };
  const A = mk(), B = mk(), tA = {}, tB = {}, put = (T, n) => { const b = Math.round(n.at / SEC); (T[n.src + b] = T[n.src + b] || []).push(n.li); };
  const b0 = A.state.beat; A.press().forEach(n => put(tA, n));
  for (let i = 0; i < 16; i++) { if (i === 2) A.release(); [[A, tA], [B, tB]].forEach(([E, T]) => { E.advance(SEC); E.drain().notes.forEach(n => put(T, n)); }); }
  const keys = [...new Set([...Object.keys(tA), ...Object.keys(tB)])].filter(k => !k.startsWith('event')), diff = keys.filter(k => (tA[k] || []).join() !== (tB[k] || []).join());
  let ringSame = 0; for (let b = b0 + 1; b <= b0 + 16; b++) if ((tA['ring' + b] || []).join() === (tB['ring' + b] || []).join()) ringSame++;
  ok(diff.length === 2 && diff.every(k => k.startsWith('me')) && ringSame === 16, `V15 한 번 누름(2박) → 16박 동안 달라진 것: ${diff.join(', ')} (누른 박 ${b0}) · 고리 소리 같음 ${ringSame}/16`);
}
{ // V15′ 사후: 다음 내리치기 전에 뗀다
  const mk = () => { const { E } = demoRing(); E.place({ x: 0.5, y: 0.3, z: -0.4, head: 1 }); E.target(-0.3, 0.2); toBeat(E); E.drain(); return E; };
  const A = mk(), B = mk(), tA = {}, tB = {}, put = (T, n) => { const b = Math.round(n.at / SEC); (T[n.src + b] = T[n.src + b] || []).push(n.li); };
  const b0 = A.state.beat; A.press().forEach(n => put(tA, n));
  for (let h = 0; h < 32; h++) { if (h === 3) A.release(); [[A, tA], [B, tB]].forEach(([E, T]) => { E.advance(SEC / 2); E.drain().notes.forEach(n => put(T, n)); }); }
  const keys = [...new Set([...Object.keys(tA), ...Object.keys(tB)])].filter(k => !k.startsWith('event')), diff = keys.filter(k => (tA[k] || []).join() !== (tB[k] || []).join());
  let ringSame = 0; for (let b = b0 + 1; b <= b0 + 16; b++) if ((tA['ring' + b] || []).join() === (tB['ring' + b] || []).join()) ringSame++;
  ok(diff.length === 2 && diff.join() === `me${b0},me${b0 + 1}` && ringSame === 16, `V15′(사후) 1.5박 만에 뗌 → 달라진 것: ${diff.join(', ')} · 고리 소리 같음 ${ringSame}/16`);
}
console.log(bad ? `\n${bad}개 FAIL` : '\n전부 PASS');

// ── 도움: 문자열·주석을 같은 길이 공백으로 지운다(자리 보존) · 이름 있는 함수의 몸 범위 ──────────────────
function strip(src) { let o = '', i = 0;
  while (i < src.length) { const c = src[i], d = src[i + 1];
    if (c === '/' && d === '/') { while (i < src.length && src[i] !== '\n') { o += ' '; i++; } continue; }
    if (c === '/' && d === '*') { while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) { o += src[i] === '\n' ? '\n' : ' '; i++; } o += '  '; i += 2; continue; }
    if (c === "'" || c === '"' || c === '`') { o += c; i++; while (i < src.length && src[i] !== c) { if (src[i] === '\\') { o += '  '; i += 2; continue; } o += src[i] === '\n' ? '\n' : ' '; i++; } o += c; i++; continue; }
    o += c; i++; }
  return o; }
function funcs(s) { const out = [], re = /function\s*([A-Za-z_$][\w$]*)?\s*\(/g; let m;
  while ((m = re.exec(s))) { const j = s.indexOf('{', re.lastIndex); let dep = 0, k = j; for (; k < s.length; k++) { if (s[k] === '{') dep++; else if (s[k] === '}' && !--dep) break; } out.push({ name: m[1] || null, a: j, b: k }); }
  return out; }

/** 페이지(common.js + flight-core.js + 인라인 스크립트)를 vm 안의 가짜 DOM 에서 띄운다. 그리기 호출은 세기만 한다. */
async function bootPage(search) {
  const els = {}, winL = {}, rafs = [], ints = [], sayLog = []; let ms = 1000, drawn = 0;
  const ctx2d = new Proxy({}, { get(t, k) { if (k in t) return t[k]; if (k === 'createRadialGradient' || k === 'createLinearGradient') return () => ({ addColorStop() {} });
    if (k === 'measureText') return () => ({ width: 10 }); return typeof k === 'string' ? () => { drawn++; } : undefined; }, set(t, k, v) { t[k] = v; return true; } });
  function el(id) { if (els[id]) return els[id]; const ls = {}, cl = new Set();
    const e = els[id] = { id, hidden: false, disabled: false, innerHTML: '', className: '', style: {}, width: 0, height: 0, clientWidth: 375, clientHeight: 534,
      _t: '', get textContent() { return this._t; }, set textContent(v) { this._t = v; if (id === 'say' && v) sayLog.push(v); },
      classList: { add: c => cl.add(c), remove: c => cl.delete(c), contains: c => cl.has(c) },
      addEventListener(t, f) { (ls[t] = ls[t] || []).push(f); }, fire(t, ev) { (ls[t] || []).forEach(f => f(ev)); },
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 375, height: 534 }), setPointerCapture() {}, getContext: () => ctx2d };
    return e; }
  const ctx = { console, Math, JSON, Date, Promise, Object, Array, Number, String, Set, Map, Error, Proxy, Symbol, isFinite, parseFloat, parseInt,
    Uint8Array, Int32Array, Uint32Array, Float32Array, Float64Array, location: { search }, devicePixelRatio: 2,
    performance: { now: () => ms }, requestAnimationFrame: f => { rafs.push(f); return rafs.length; }, setInterval: f => { ints.push(f); return ints.length; }, setTimeout: f => f(),
    addEventListener: (t, f) => { (winL[t] = winL[t] || []).push(f); },
    fetch: () => Promise.resolve({ json: () => Promise.resolve(JSON.parse(JSON.stringify(D))) }),
    document: { querySelector: s => el(s.replace(/^#/, '')), hidden: false, addEventListener() {} } };
  ctx.window = ctx; ctx.globalThis = ctx; vm.createContext(ctx);
  vm.runInContext(readFileSync(new URL('sketch/common.js', ROOT), 'utf8'), ctx);
  vm.runInContext(readFileSync(new URL('sketch/flight-core.js', ROOT), 'utf8'), ctx);
  INLINE.forEach(s => vm.runInContext(s, ctx));
  for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r));
  return { ctx, el, sayLog, drawn: () => drawn, win: (t, ev) => (winL[t] || []).forEach(f => f(ev)),
    tick(dtMs) { ms += dtMs; ints.forEach(f => f()); const fs = rafs.splice(0); fs.forEach(f => f(ms)); } };
}
