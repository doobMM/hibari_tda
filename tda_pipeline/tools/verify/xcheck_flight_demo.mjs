// tools/verify/xcheck_flight_demo.mjs — 검산: 날갯짓 예시가 hibari 두 손을 박마다 그대로 내는가 — 엔진이 실제로 낸 음(drain) ↔ 원곡 자료(cube_ref 의 dataRight/dataLeft)
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dataRight, dataLeft } from './xcheck_cube_ref.mjs';
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL('../..', import.meta.url)).replace(/[\/]$/, '');
const HS = require(ROOT + '/sketch/common.js');
const F = require(ROOT + '/sketch/flight-core.js');
const H = HS.derive(require(ROOT + '/lenia/tonnetz.json'));
const E = F.create(H, {});
E.demo(true);
const SEC = F.SEC, byBeat = {};
let b0 = null;
for (let i = 0; i < 200 * 12; i++) {           // 200박을 1/12박씩
  E.advance(SEC / 12);
  const o = E.drain();
  o.notes.forEach(n => { const b = Math.round(n.at / SEC); (byBeat[b] = byBeat[b] || { me: [], ring: {}, ev: [] });
    if (n.src === 'me') byBeat[b].me.push(n.pitch); else if (n.src === 'ring') (byBeat[b].ring[n.ring] = byBeat[b].ring[n.ring] || []).push(n.pitch); else byBeat[b].ev.push(n.pitch); });
  o.events.forEach(e => { if (e.type === 'born') console.log('생김', 'at 박', Math.round(e.at / SEC), 'L', e.L, 'P', e.P, '지속', e.pers.toFixed(3)); });
}
const beats = Object.keys(byBeat).map(Number).sort((a, b) => a - b);
b0 = beats.find(b => byBeat[b].me.length);                 // 예시가 처음 소리 낸 박 = 모듈 스텝 0
const enc = a => a.slice().sort((x, y) => x - y).join(',');
const want = s => dataRight[s].map(x => x[0]);
const wantL = s => dataLeft[s].map(x => x[0]);
let okR = 0, nR = 0, firstR = null;
for (let q = 0; q < 128; q++) { const got = (byBeat[b0 + q] || { me: [] }).me; nR++; if (enc(got) === enc(want(q % 32))) okR++; else if (!firstR) firstR = { q, got: enc(got), want: enc(want(q % 32)) }; }
console.log(`예시 나(오른손) 첫 128박: hibari 오른손과 같은 박 ${okR}/${nR}`, firstR ? JSON.stringify(firstR) : '');
// 첫 고리 = 32박째에 생긴 고리 → 그다음 박부터 [쉼 + 구절] 33박 = hibari 왼손
const ringIds = new Set(); beats.forEach(b => Object.keys(byBeat[b].ring).forEach(id => ringIds.add(+id)));
const first = Math.min(...ringIds);
let okL = 0, nL = 0, firstL = null;
for (let q = 33; q < 128; q++) { const got = ((byBeat[b0 + q] || { ring: {} }).ring[first]) || []; nL++; if (enc(got) === enc(wantL(q % 33))) okL++; else if (!firstL) firstL = { q, got: enc(got), want: enc(wantL(q % 33)) }; }
console.log(`첫 고리 박 33..127: hibari 왼손(33박, 앞에 쉼)과 같은 박 ${okL}/${nL}`, firstL ? JSON.stringify(firstL) : '');
// 어긋남: 고리의 구절 첫 박(쉼 다음)이 내 모듈 첫 박보다 몇 박 늦나 — 바퀴마다 +1 이어야 한다
const lag = []; for (let lap = 1; lap <= 3; lap++) { const myStart = b0 + 32 * lap, ringStart = b0 + 33 + 33 * (lap - 1) + 1; lag.push(ringStart - myStart); }
console.log('바퀴별 어긋남(박)', lag.join(' → '));
