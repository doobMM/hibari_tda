/* ============================================================================
 * verify_tonnetz_h0.mjs — duet.html 의 Tonnetz H0 계기가 맞게 계산하는지 검사
 *
 * `tools/verify_js_algo1.mjs` 와 같은 방침이다: **배포되는 그 코드를 그대로**
 * 꺼내 돌린다. 사본을 만들어 검사하면 사본만 맞는 상태가 생긴다.
 *
 * 검사 대상 — 고정 Tonnetz(12 음이름, 이웃 ±3 ±4 ±7) 위 위쪽 레벨집합 여과의 H0.
 * 이 계기는 **생성에 관여하지 않는다.** 생성은 H1 중첩행렬이 한다.
 *
 * 실행:  node tools/verify_tonnetz_h0.mjs      (실패하면 종료코드 1)
 * ========================================================================= */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(ROOT, 'duet.html'), 'utf8');

// 배포 파일에서 계기 코드만 잘라 온다 (사본을 만들지 않는다)
const a = html.indexOf('  var TZ_NB = ');
const b = html.indexOf('  function drawTZ(');
if (a < 0 || b < 0 || b <= a) {
  console.error('duet.html 에서 Tonnetz 블록을 찾지 못했다 — 표식이 바뀌었나?');
  process.exit(1);
}
const src = html.slice(a, b);
const { tzH0, TZ_PC, TZ_COLS, TZ_ROWS } = (0, eval)(
  `(function(){${src}; return {tzH0, TZ_PC, TZ_COLS, TZ_ROWS};})()`);

const w = pcs => { const v = new Float64Array(12); for (const p of pcs) v[((p % 12) + 12) % 12] += 1; return v; };
const b0 = pcs => tzH0(w(pcs)).beta0;

let fail = 0;
const eq = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(46)} got=${JSON.stringify(got)} want=${JSON.stringify(want)}`);
  if (!ok) fail++;
};

console.log('Tonnetz H0 — 연결성분');
eq('빈 집합', b0([]), 0);
eq('C 단독 {0}', b0([0]), 1);
eq('C장3화음 {C,E,G} — 서로 이웃', b0([0, 4, 7]), 1);
eq('C단3화음 {C,Eb,G}', b0([0, 3, 7]), 1);
eq('트라이톤 {C,F#} — 6은 이웃 아님', b0([0, 6]), 2);
eq('반음 {C,C#} — 1은 이웃 아님', b0([0, 1]), 2);
// ⚠ 5는 이웃이다(완전4도 = 5도의 자리바꿈). 처음에 3으로 기대했다가 틀렸다.
eq('{C,C#,F#} — C#-F# 는 5도로 이어진다', b0([0, 1, 6]), 2);
eq('다이아토닉 C장조 7음 — 5도 사슬로 하나', b0([0, 2, 4, 5, 7, 9, 11]), 1);
eq('온음음계 {0,2,4,6,8,10} — 전부 짝수, 3·5·7 이웃 없음', b0([0, 2, 4, 6, 8, 10]), 2);
eq('12음 전부 — 원환면은 연결', b0([...Array(12).keys()]), 1);

console.log('\nelder rule — 센 쪽이 산다');
{
  // C 3회 · E 1회. E 는 태어나자마자 C 에 흡수돼야 한다 (지속 0).
  const r = tzH0(w([0, 0, 0, 4]));
  const sorted = r.bars.slice().sort((p, q) => (q[0] - q[1]) - (p[0] - p[1]));
  eq('막대 2개', r.bars.length, 2);
  eq('오래 사는 막대 = C (birth 3 → death 0)', sorted[0], [3, 0]);
  eq('짧은 막대 = E (birth 1 → death 1, 지속 0)', sorted[1], [1, 1]);
  eq('beta0 = 1', r.beta0, 1);
}

console.log('\n격자 — 표시용 기준점을 옮겨도 12 음이름이 모두 나온다');
eq('칸 수', TZ_PC.length, TZ_COLS * TZ_ROWS);
eq('음이름 12개 전부 등장', new Set(TZ_PC).size, 12);
eq('아랫줄 = 다이아토닉 5도 사슬 F C G D A E B',
   TZ_PC.slice(0, TZ_COLS), [5, 0, 7, 2, 9, 4, 11]);

console.log(fail ? `\n${fail}건 실패` : '\n전부 통과');
process.exit(fail ? 1 : 0);
