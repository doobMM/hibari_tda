// verify_life.mjs — 살아 있는 격자(3판) 검증 자료 (docs/tonnetz_lenia_spec.md §10.5, 실행 전에 적은 예측)
// 페이지와 같은 엔진(lenia/life-core.js)을 돌려 원자료를 남긴다. MI 판정은 experiments/run_life_mi.py 가 한다.
//   node tools/verify_life.mjs X1|X2|X3|X3b|X4 [seeds] [part]   → docs/step3_data/life_raw_<X>[_part].json
//   SEED0=7100 (환경 변수) 로 시드 묶음을 바꾼다 — 1회차 5100, 2회차 7100 (명세 §10.9). 1회차 원자료는 life_raw_r1*_*.json
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = globalThis;
require(path.join(ROOT, 'hibari_dashboard/public/js/generation-algo1.js'));
const T = require(path.join(ROOT, 'lenia/life-core.js'));
const D = JSON.parse(fs.readFileSync(path.join(ROOT, 'lenia/tonnetz.json'), 'utf8'));
const G = globalThis.GenerationAlgo1;
const EXP = process.argv[2], N = +(process.argv[3] || 20), SEED0 = +(process.env.SEED0 || 5100);
// CA 는 결정적이다 — 시드는 음 뽑기만 바꾼다. 그래서 시드 묶음을 바꿀 때 놓는 **각도**도 옮긴다(1회차 5100 은 0 이라 그대로 재현).
// 안 옮기면 2회차가 1회차·탐색(돌봄 재현·비옥도 탐색이 쓴 초기 조건)과 같은 궤적을 시험한다 — 명세 §10.9
const ANG0 = SEED0 === 5100 ? 0 : (SEED0 * 0.618) % 6.283;
// 3회차부터는 놓는 **자리**도 옮긴다 — 20점이 원을 채워 각도만으로는 독립 초기 조건이 안 된다(2.266 ≈ 5×1.7, §10.11)
const POS0 = SEED0 < 9000 ? [0, 0] : [(SEED0 * 0.3719) % T.W, (SEED0 * 0.2311) % T.H];
const sp = (x, y) => [((x + POS0[0]) % T.W + T.W) % T.W, ((y + POS0[1]) % T.H + T.H) % T.H];
// 회차별 엔진 값을 고정한다 — DEF 가 바뀌어도 1·2회차를 그대로 다시 돌릴 수 있게 (나머지는 세 회차 같다)
const ENG = SEED0 === 5100 ? { FLOCAL: false, FERT: 0.06, LURE: 0.35 } : SEED0 === 7100 ? { FLOCAL: true, FERT: 0.1, LURE: 0.30 } : {};
const HALF = process.env.HALF == null ? null : +process.env.HALF;   // 오래 걸리면 시드를 반씩 (HALF=0|1)
const skip = s => HALF != null && (s < N / 2) !== (HALF === 0);
const OUTP = process.env.OUTP || 'life_raw_';                      // 3회차: OUTP=life_raw_r3_
const PART = process.argv[4] == null ? null : +process.argv[4];   // 나눠 돌리기: X2 = rate 번호, X3 = 가중치(0/1), X3b = 팔(0 실제·1 섞음·2 끔), X4 = 돌봄(0/1)
const beat = L => { for (let k = 0; k < 4; k++) L.caStep(); return L.beat(); };
const wr = (v, P) => v - P * Math.round(v / P);
const out = { script: 'tools/verify_life.mjs ' + EXP, n_seeds: N, seed0: SEED0, ang0: ANG0, pos0: POS0, eng: ENG, generated_at: new Date().toISOString(), params: T.DEF, rows: [] };

if (EXP === 'X1') {                      // 몰기: 방향 4개 → 이동 방향
  const DIRS = [[1, 0], [0, 1], [-1, 0], [0, -1]];
  for (let d = 0; d < 4; d++) for (let s = 0; s < N; s++) { if (skip(s)) continue;
    const L = T.create(D, { seed: SEED0 + s, algo1: G, ...ENG }); L.spawn(0, ...sp(10, 6), (s * 2.39 + ANG0) % 6.283);
    for (let b = 0; b < 8; b++) beat(L);
    // 변위는 **박마다 증분을 더해** 잰다. 29박이면 ≈6.4 를 가는데 세로 둘레가 12 라, 끝점 둘만 가장 가까운 상으로 빼면
    // 반 바퀴(6)를 넘은 세로 이동이 거꾸로 읽힌다 (1회차 첫 실행의 버그 — life_raw_r1bug_X1.json, 명세 §10.7)
    L.setSteer(0, DIRS[d]); let prev = null, sx = 0, sy = 0, done = false, jumps = 0;
    for (let b = 0; b < 50; b++) { beat(L); const B = L.state.blobs[0][0]; if (!B) break;
      if (b > 20) { const ix = wr(B.x - prev[0], T.NX) * T.W / T.NX, iy = wr(B.y - prev[1], T.NY) * T.H / T.NY;
        if (Math.hypot(ix, iy) > 1) jumps++;              // 한 박에 1 넘게 뛰면 덩어리가 갈라져 다른 쪽을 잡은 것 (속도 ≈0.2/박)
        sx += ix; sy += iy; }
      if (b >= 20) prev = [B.x, B.y]; if (b === 49) done = true; }
    let ang = null;
    if (done) ang = Math.atan2(sy, sx) * 180 / Math.PI;
    const tgt = Math.atan2(DIRS[d][1], DIRS[d][0]) * 180 / Math.PI;
    out.rows.push({ dir: d, seed: s, angle: ang, err: ang == null ? null : ((ang - tgt + 540) % 360) - 180, alive: done, dist: Math.hypot(sx, sy), jumps });
  }
}
if (EXP === 'X2') {                      // rate → 찾은 고리 수 · 음높이
  const RATES = [0, 0.5, 1.0, 1.5];
  for (let r = 0; r < RATES.length; r++) { if (PART != null && r !== PART) continue; for (let s = 0; s < N; s++) { if (skip(s)) continue;
    // 같은 자리, 시드마다 다른 각도. ⚠ 1회차(life_raw_r1bad_X2_*.json)는 각도까지 고정이라 CA 가 결정적이어서
    // 20시드가 전부 같은 궤적이었고(유사반복), 사전등록(5분)과 달리 2분만 돌았다 — 명세 §10.7
    const L = T.create(D, { seed: SEED0 + 100 + s, algo1: G, RATE: RATES[r], ...ENG }); L.spawn(0, ...sp(7, 6), 0.3 + s * 0.9 + ANG0); L.spawn(1, ...sp(12, 5), 2.4 + s * 1.3 + ANG0);
    const foundK = new Set(); let ps = 0, pn = 0, pitches = {};
    for (let b = 0; b < 660; b++) {                         // 5분 (사전등록)
      const ev = beat(L); ev.found.forEach(([k]) => foundK.add(k));
      ev.voices.forEach(v => v.notes.forEach(q => { ps += q[0]; pn++; pitches[q[0]] = (pitches[q[0]] || 0) + 1; }));
    }
    out.rows.push({ rate: RATES[r], seed: s, found: foundK.size, meanPitch: pn ? ps / pn : null, notes: pn, pitches,
                    alive: [L.mass(0) > 15, L.mass(1) > 15] });
  } }
}
if (EXP === 'X3') {                      // intra·inter(실제) vs 섞은 가중치 → 지나간 칸의 음
  for (let w = 0; w < 2; w++) { if (PART != null && w !== PART) continue; for (let s = 0; s < N; s++) {
    const L = T.create(D, { seed: SEED0 + 200 + s, algo1: G, shuffleWeights: w === 1, ...ENG }); L.spawn(0, ...sp(9, 6), (s * 1.7 + ANG0) % 6.283);
    const pcMass = new Array(12).fill(0); let black = 0, tot = 0, pitchSum = 0, pitchW = 0;
    for (let b = 0; b < 264; b++) {
      beat(L);
      if (b % 4 === 0) { const A = L.state.A[0];
        for (let i = 0; i < A.length; i += 2) if (A[i] > 0.1) { const n = L.cell[i], pc = L.geo.nodes[n].pc, li = L.note[n];
          pcMass[pc] += A[i]; tot += A[i]; if (li < 0) black += A[i]; else { pitchSum += A[i] * L.labels[li].pitch; pitchW += A[i]; } } }
    }
    out.rows.push({ shuffled: w, seed: s, blackFrac: tot ? black / tot : null, meanPitch: pitchW ? pitchSum / pitchW : null,
                    pcMass: pcMass.map(x => +(x / (tot || 1)).toFixed(4)), alive: L.mass(0) > 15 });
  } }
}
if (EXP === 'X3b') {                     // 메커니즘: 칸을 옮길 때 hibari 의 전이(실제 intra_right)가 높은 이웃으로 가나 — 팔 실제/섞음/끔(비옥도 0)
  const WR = D.note_weights.intra_right, ARMS = ['real', 'shuf', 'off'];
  for (let a = 0; a < 3; a++) { if (PART != null && a !== PART) continue; for (let s = 0; s < N; s++) { if (skip(s)) continue;
    // 실제·섞음 팔의 비옥도는 2회차 값(국소 0.1)으로 못 박는다 — DEF 는 3회차부터 0 이다
    const opt = { seed: SEED0 + 200 + s, algo1: G, FLOCAL: true, FERT: a === 2 ? 0 : 0.1 }; if (a === 1) opt.shuffleWeights = true;
    const L = T.create(D, opt); L.spawn(0, ...sp(9, 6), (s * 1.7 + ANG0) % 6.283);
    const M = new Float32Array(L.geo.nodes.length), pcMass = new Array(12).fill(0);
    let prev = -1, sc = 0, n = 0, died = null, black = 0, tot = 0, pitchSum = 0, pitchW = 0;
    for (let b = 0; b < 264; b++) {                         // 2분 (X3 과 같다)
      beat(L); const A = L.state.A[0];
      M.fill(0); for (let i = 0; i < A.length; i++) if (A[i] > 0.1) M[L.cell[i]] += A[i];
      // 점수 = 옮겨 간 칸의 W(앞 음 → 새 음) − 앞 칸 6-이웃(음 있는 칸)의 평균 W.  0 = 무작위 이웃, 평가는 **실제** 가중치로
      let best = -1, bm = 0; for (let i = 0; i < M.length; i++) if (M[i] > bm && L.note[i] >= 0) { bm = M[i]; best = i; }
      if (best >= 0 && prev >= 0 && best !== prev && L.geo.nodes[prev].nb.includes(best)) {
        const vp = L.note[prev], nbs = L.geo.nodes[prev].nb.filter(j => L.note[j] >= 0);
        sc += WR[vp][L.note[best]] - nbs.reduce((t, j) => t + WR[vp][L.note[j]], 0) / nbs.length; n++; }
      if (best >= 0) prev = best;
      if (b % 4 === 0) for (let i = 0; i < A.length; i += 2) if (A[i] > 0.1) { const nd = L.cell[i], pc = L.geo.nodes[nd].pc, li = L.note[nd];
        pcMass[pc] += A[i]; tot += A[i]; if (li < 0) black += A[i]; else { pitchSum += A[i] * L.labels[li].pitch; pitchW += A[i]; } }
      if (L.mass(0) < 15) { died = b; break; }
    }
    out.rows.push({ arm: ARMS[a], armIdx: a, seed: s, score: n ? sc / n : null, moves: n, died, alive: died == null,
                    blackFrac: tot ? black / tot : null, meanPitch: pitchW ? pitchSum / pitchW : null, pcMass: pcMass.map(x => +(x / (tot || 1)).toFixed(4)) });
  } }
}
if (EXP === 'X4') {                      // 방치 vs 60초마다 몰기
  for (let c = 0; c < 2; c++) { if (PART != null && c !== PART) continue; for (let s = 0; s < N; s++) { if (skip(s)) continue;
    const L = T.create(D, { seed: SEED0 + 300 + s, algo1: G, ...ENG }); L.spawn(0, ...sp(10, 6), (s * 2.1 + ANG0) % 6.283);
    let died = null;
    for (let b = 0; b < 660; b++) {                          // 5분
      if (c === 1 && b % 132 === 0) { const a = s + b / 132 * 1.9; L.setSteer(0, [Math.cos(a), Math.sin(a)]); }
      if (c === 1 && b % 132 === 40) L.setSteer(0, null);   // 몰기는 18초만, 나머지는 놓아 둔다
      beat(L); if (L.mass(0) < 15) { died = b; break; }
    }
    out.rows.push({ care: c, seed: s, died, alive5min: died == null });
  } }
}
fs.writeFileSync(path.join(ROOT, `docs/step3_data/${OUTP}${EXP}${PART == null ? '' : '_' + PART}${HALF == null ? '' : 'h' + HALF}.json`), JSON.stringify(out));
console.log(EXP, 'rows', out.rows.length, '저장');
