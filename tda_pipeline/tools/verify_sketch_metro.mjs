// verify_sketch_metro.mjs — hibari 노선도 회색 시제품(sketch/metro-core.js)이 규칙 한 장대로 도는지. 소리 없음.
//   node tools/verify_sketch_metro.mjs       (실패가 있으면 종료 코드 1)
// 문턱은 돌리기 전에 적었다(2026-10-01). G2 의 "3배" 는 앞서 돌린 봇 시험(봇 6~11분 vs 방치 1~1.5분, 어려워짐 0.9)을 본 뒤 정했다 — 확증 아님.
// 그 뒤 한 판을 규칙의 3~6분에 맞추려 어려워짐을 0.8 로 올리자 G2 가 경계에서 실패했다(가장 짧은 시드 2.97배). 문턱은 그대로 둔다.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const M = require('../sketch/metro-core.js');
const SEEDS = [1, 2, 3, 4, 5, 6, 7, 8];
let bad = 0;
const line = (ok, n, m) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${n}  ${m}`); if (!ok) bad++; };
const med = a => [...a].sort((x, y) => x - y)[a.length >> 1];
const held = S => S.score + S.stations.reduce((a, s) => a + s.q.length, 0) + S.lines.reduce((a, L) => a + L.trains.reduce((b, t) => b + t.pax.length, 0), 0);

function bot(E) {                          // 단순한 사람: 새 역을 가장 가까운 노선 끝에 잇고, 안 되면 남은 노선으로 가장 가까운 역과 잇는다
  const S = E.state; let seen = 3; E.newLine([0, 1, 2]) || E.newLine([0, 1]) || E.newLine([0, 2]);
  return () => {
    if (S.gift) E.chooseGift(0);
    if (S.spare.trains) E.addTrain(S.lines.reduce((a, b) => a.trains.length <= b.trains.length ? a : b));
    if (S.spare.cars) E.addCar(S.lines[0]);
    while (seen < S.stations.length) { const id = seen++, st = S.stations[id]; let best = null;
      S.lines.forEach(L => { if (L.loop) return; [['tail', L.stations[L.stations.length - 1]], ['head', L.stations[0]]].forEach(([end, s]) => {
        const d = Math.hypot(S.stations[s].x - st.x, S.stations[s].y - st.y); if (!best || d < best.d) best = { L, end, d }; }); });
      if (!(best && E.extend(best.L, best.end, [id]))) { const near = S.stations.filter(s => s.id !== id).sort((a, b) => Math.hypot(a.x - st.x, a.y - st.y) - Math.hypot(b.x - st.x, b.y - st.y));
        for (const n of near) if (E.newLine([n.id, id])) break; } } };
}
function run(seed, play, limit = 1500) { const E = M.create({ seed }), S = E.state, act = play ? bot(E) : null; let leak = 0;
  if (!play) S.started = true;
  for (let t = 0; t < limit * 10 && !S.over; t++) { if (act) act(); else if (S.gift) E.chooseGift(0); E.step(0.1); if (held(S) !== S.spawned) leak++; }
  return { t: S.t, score: S.score, leak, week: S.week, stations: S.stations.length }; }

const idle = SEEDS.map(s => run(s, false)), play = SEEDS.map(s => run(s, true));
line(idle.every(r => r.t < 150), 'G1 지는 것이 있다', `손대지 않으면 ${Math.min(...idle.map(r => r.t)).toFixed(0)}~${Math.max(...idle.map(r => r.t)).toFixed(0)}초에 역이 넘친다 (문턱 < 150초)`);
line(play.every((r, i) => r.t > 3 * idle[i].t && r.score > 0), 'G2 하면 버틴다', `단순한 봇: ${Math.min(...play.map(r => r.t / 60)).toFixed(1)}~${Math.max(...play.map(r => r.t / 60)).toFixed(1)}분(중앙 ${(med(play.map(r => r.t)) / 60).toFixed(1)}분), 나른 승객 중앙 ${med(play.map(r => r.score))}명 · 같은 시드의 방치보다 3배 넘게 오래 (문턱) — 실제 배수 ${Math.min(...play.map((r, i) => r.t / idle[i].t)).toFixed(2)}~${Math.max(...play.map((r, i) => r.t / idle[i].t)).toFixed(2)}, 중앙 ${med(play.map((r, i) => r.t / idle[i].t)).toFixed(2)}`);
line([...idle, ...play].every(r => r.leak === 0), 'G3 승객이 사라지지 않는다', `매 0.1초 '생긴 승객 = 나른 + 역에서 기다림 + 열차 안' 이 어긋난 횟수 ${[...idle, ...play].reduce((a, r) => a + r.leak, 0)}`);
{ const E = M.create({ seed: 3 }), S = E.state; E.newLine([0, 1]); const tr = S.lines[0].trains[0], p0 = E.trainPos(tr); E.step(0.5); const p1 = E.trainPos(tr);
  line(S.started && Math.hypot(p1.x - p0.x, p1.y - p0.y) > 10, 'G4 그으면 곧바로 달린다', `노선을 긋고 0.5초 뒤 열차가 ${Math.hypot(p1.x - p0.x, p1.y - p0.y).toFixed(0)} 만큼 움직였다 (문턱 > 10) · 긋기 전에는 시간이 안 흐른다`); }
{ let refused = 0, used = 0, refund = 0, n = 0;
  for (const s of SEEDS) { const E = M.create({ seed: s }), S = E.state, ids = S.stations.map(x => x.id);
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) if (a !== b && E.crossings(ids[a], ids[b])) {
      n++; const keep = S.spare.bridges; S.spare.bridges = 0; if (!E.newLine([ids[a], ids[b]])) refused++; S.spare.bridges = keep;
      const L = E.newLine([ids[a], ids[b]]); if (L && S.spare.bridges === keep - 1) used++; if (L) { E.removeLine(L); if (S.spare.bridges === keep) refund++; } a = b = 3; } }
  line(n > 0 && refused === n && used === n && refund === n, 'G5 강을 건너면 다리가 든다', `강을 건너는 연결 ${n}가지: 다리 없으면 거절 ${refused} · 있으면 하나 씀 ${used} · 노선을 지우면 돌려받음 ${refund}`); }
{ const a = run(5, true, 400), b = run(5, true, 400); line(a.t === b.t && a.score === b.score, 'G6 같은 시드 = 같은 판', `시드 5 두 번: ${a.t.toFixed(1)}초 ${a.score}명 / ${b.t.toFixed(1)}초 ${b.score}명`); }
console.log(`     (서술) 봇이 끝난 주: ${play.map(r => r.week + 1).join(' · ')} · 그때 역 수: ${play.map(r => r.stations).join(' · ')}`);
console.log(bad ? `\n${bad}개 실패` : '\n전부 통과'); process.exit(bad ? 1 : 0);
