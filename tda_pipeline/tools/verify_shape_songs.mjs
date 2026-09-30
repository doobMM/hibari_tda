// verify_shape_songs.mjs — 실제 13곡을 페이지와 **같은 경로**(index.html 의 strand → shape-core build)로 살을 입혀 본다.
//   ① 닫힌 면인가(열린 변 0) ② 조각 수 ③ 손잡이(구멍) 수를 굵기 σ 별로 — 굵게 하면 구멍이 메워진다. 어느 곡의 구멍이 오래 버티나.
//   node tools/verify_shape_songs.mjs   → docs/step3_data/song_shape_mesh.json
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SC = require(path.join(ROOT, 'shape', 'shape-core.js'));
// 페이지의 strand 함수를 글자 그대로 가져온다 (따로 베끼면 어긋난다)
const html = readFileSync(path.join(ROOT, 'shape', 'index.html'), 'utf8');
const src = html.slice(html.indexOf('  function strand(P, C, unit) {'), html.indexOf('  function flesh('));
const SUB = 3, MINDENS = +html.match(/MINDENS = ([\d.]+)/)[1], SIGMA = 0.5;     // 페이지의 기본 굵기 (?sigma= 가 없을 때)
const strand = new Function('SUB', 'MINDENS', src + '\nreturn strand;')(SUB, MINDENS);
const D = JSON.parse(readFileSync(path.join(ROOT, 'shape', 'data', 'shapes.json'), 'utf8')), out = { sigma_page: SIGMA, min_dens: MINDENS, songs: {} };
let fail = 0;
for (const g of D.songs) {
  const P = new Float32Array(g.T * 3), C = new Float32Array(g.T * 3); for (let i = 0; i < g.T * 3; i++) { P[i] = g.pos[i] * g.scale; C[i] = g.rgb[i] / 255; }
  const s = strand(P, C, g.unit), row = { T: g.T, rec80: g.rec80, genus_by_sigma: {} }; let line = '';
  for (const sg of [0.35, 0.5, 0.65, 0.8, 1.0]) {
    const m = SC.build(s.pos, s.col, { W: s.w, sigma: sg, iso: 0.5, maxGrid: 132 }), t = SC.topology(m);
    row.genus_by_sigma[sg] = t.genus; line += ` σ${sg}:${t.genus}`;
    if (sg === SIGMA) Object.assign(row, { V: t.V, F: t.F, components: t.components, boundaryEdges: t.boundaryEdges, nonManifoldEdges: t.nonManifoldEdges, ms: m.stats.ms, volume: +SC.measure(m).volume.toFixed(1) });
  }
  out.songs[g.slug] = row; const good = row.boundaryEdges === 0 && row.V > 0; if (!good) fail++;
  console.log(`${good ? 'PASS' : 'FAIL'}  ${g.slug.padEnd(8)} T=${String(g.T).padStart(4)} V=${row.V} 조각 ${row.components} 열린 변 ${row.boundaryEdges} 겹친 변 ${row.nonManifoldEdges} ${Math.round(row.ms)}ms 부피 ${row.volume} | 손잡이${line}`);
}
writeFileSync(path.join(ROOT, 'docs', 'step3_data', 'song_shape_mesh.json'), JSON.stringify(out, null, 1));
console.log(fail ? `\n실패 ${fail}건` : '\n전부 닫힌 면'); process.exit(fail ? 1 : 0);
