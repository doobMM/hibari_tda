// tools/verify/xcheck_flight_vr.mjs — 검산: vrH1 을 ripser 와 대조 — 에이전트 판정기와 다른 시드·다른 모양으로.
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import os from 'os';
import { execFileSync } from 'child_process';
import fs from 'fs';
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL('../..', import.meta.url)).replace(/[\/]$/, '');
const F = require(ROOT + '/sketch/flight-core.js');
const dir = os.tmpdir() + '/';
const PY = fileURLToPath(new URL('./xcheck_ripser_h1.py', import.meta.url));
let seed = 987654321; const rnd = () => { seed = (seed * 1103515245 + 12345) >>> 0; return seed / 4294967296; };
const clouds = [];
for (let k = 0; k < 40; k++) {                       // 무작위 (점 수 6–41)
  const n = 6 + Math.floor(rnd() * 36), P = [];
  for (let i = 0; i < n; i++) P.push([rnd() * 2 - 1, rnd() * 2 - 1, rnd() * 2 - 1]);
  clouds.push(P);
}
for (let k = 0; k < 20; k++) {                       // 잡음 섞인 고리·8자·나선 (실제 날갯길에 가까운 것)
  const n = 16 + Math.floor(rnd() * 25), P = [], kind = k % 3;
  for (let i = 0; i < n; i++) { const t = 2 * Math.PI * i / n, e = () => (rnd() - 0.5) * 0.08;
    if (kind === 0) P.push([0.6 * Math.cos(t) + e(), 0.3 * Math.sin(2 * t) + e(), 0.6 * Math.sin(t) + e()]);
    else if (kind === 1) P.push([0.7 * Math.sin(t) + e(), e(), 0.35 * Math.sin(2 * t) + e()]);
    else P.push([0.5 * Math.cos(3 * t) + e(), t / 6 - 0.5 + e(), 0.5 * Math.sin(3 * t) + e()]); }
  clouds.push(P);
}
fs.writeFileSync(dir + 'vr_in.json', JSON.stringify(clouds));
execFileSync('python', [PY, dir + 'vr_in.json', dir + 'vr_out.json'], { stdio: 'inherit' });
const ref = JSON.parse(fs.readFileSync(dir + 'vr_out.json', 'utf8'));
let worst = 0, mism = 0, nb = 0;
clouds.forEach((P, k) => {
  const mine = F.vrH1(P).map(b => [b[0], b[1]]).filter(b => b[1] - b[0] > 1e-9).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const r = ref[k];
  if (mine.length !== r.length) { mism++; console.log('막대 수 다름', k, mine.length, r.length); return; }
  mine.forEach((b, i) => { worst = Math.max(worst, Math.abs(b[0] - r[i][0]), Math.abs(b[1] - r[i][1])); nb++; });
});
console.log((mism === 0 && worst < 1e-6 ? 'PASS' : 'FAIL') + ` vrH1 = ripser: 점구름 ${clouds.length}개, 막대 ${nb}개, 개수 다른 구름 ${mism}, 최대 차 ${worst.toExponential(2)}`);
// 정답이 알려진 모양
const circ = n => Array.from({ length: n }, (_, i) => [Math.cos(2 * Math.PI * i / n), Math.sin(2 * Math.PI * i / n), 0]);
const b20 = F.vrH1(circ(20));
console.log(`원 20점: 막대 ${b20.length}개, 탄생 ${b20[0] && b20[0][0].toFixed(6)} (기대 ${(2 * Math.sin(Math.PI / 20)).toFixed(6)}), 죽음 ${b20[0] && b20[0][1].toFixed(4)}`);
const line = Array.from({ length: 25 }, (_, i) => [i / 24, 0, 0]);
const back = line.concat(line.slice().reverse().map(p => [p[0], 0.02, 0]));   // 오고 가는 선분 (날갯짓 대조군과 같은 꼴)
console.log(`선분: ${F.vrH1(line).length}개 · 오고 가는 선분: 최대 지속 ${Math.max(0, ...F.vrH1(back).map(b => b[1] - b[0])).toFixed(4)}`);
