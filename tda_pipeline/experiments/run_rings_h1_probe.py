"""
run_rings_h1_probe.py — 고리판(sketch/rings.html)을 돌린 곡에 **연구의 H₁(정본 경로)** 을 그대로 걸면 무엇이 보이나.

질문 (2026-10-07 사용자): "지속 호몰로지나 그 외의 위상수학 개념이 어떻게 적용될 수 있을지 가능성을 탐색해줘".
고리판에서 위상은 지금 '겉면 = 공 · 원 = 고리' 뿐이다. 연구의 핵심(H₁ — 사용자 말 "H_1을 쓰는 걸 멈추지 않는 게 좋을 것 같긴 해")을
판에 붙이려면 먼저 **원 하나를 사분 돌린 곡의 H₁ 고리가 얼마나·어떻게 바뀌는지** 알아야 한다(사건으로 쓸 수 있나, 목표로 쓸 수 있나).

방법
  곡 = hibari MIDI 의 두 손 사건(시각·길이)을 **그대로** 두고 음높이만 판 상태대로 바꾼다:
       사건마다 그 박·그 음높이의 칸(sketch/cube-core.js 칸표, node 로 덤프)을 찾아 그 칸에 지금 앉은 점의 음높이로.
       → 다 맞춘 판 = 원곡 그대로 (정본과 비트 동일해야 한다: P0).
  H₁ = 정본 경로 그대로: setup_hibari 와 같은 전처리(단 compute_intra_weights 의 화음 수는 기본값 17 이 아니라 그 판의 화음 수 —
       판을 돌리면 화음 가짓수가 늘 수 있다. 다 맞춘 판에서는 17 그대로라 정본과 같다) → build_overlap_bundle('dft', α=0.25, ow=0.3, dw=1.0, use_decayed=False, threshold=0.35)
       (거리 함수·설정은 바꾸지 않는다 — 연구 결정은 사용자 몫). 고리는 (음높이, 길이) 집합으로 바꿔 판끼리 비교한다.
  판   ① 다 맞춤 ② 원 하나 사분 27가지(원 9 × k 1·2·3) ③ 무작위 걸음 2·3·5·10·30수 × 6 ④ 대조: 무작위 칸 12개를 마구 섞기 × 9,
       점 54개 전부 마구 섞기 × 6 (고리판으로 갈 수 있는 상태인지는 따지지 않는다 — 위상 대조용)

사전 예측 (돌리기 전에 적음, 2026-10-07)
  P0  다 맞춘 판 → K=14, 고리 14개가 정본과 (음높이·길이 집합으로) 같다.
  P1  원 하나 사분 27가지 중 20가지 이상이 고리 집합을 바꾼다(hibari 고리를 하나라도 잃거나 새 고리가 생김) — H₁ 이 한 수에 반응한다.
  P2  걸음이 길수록 hibari 고리가 덜 남는다: 남은 hibari 고리 수의 중앙값이 1수 > 3수 > 10수 > 30수 (단조), 30수는 54개 마구 섞기 중앙값 + 1 이하.
  P3  (탐색, 방향 불확실) 원 사분 한 번이 무작위 칸 12개 섞기보다 hibari 고리를 더 많이 남긴다(중앙값).
  P4  들리는 변화(오른손 모듈에서 바뀐 스텝 수)와 위상 변화(잃은 hibari 고리 수 + 새 고리 수)가 같은 쪽으로 간다: 스피어만 ρ > 0.3 (1·2·3·5수 판).

한계
  - 정본 PH 는 rate 0~1.5 를 0.01 씩 151번 돈다(판 하나 ~10초) — 브라우저에서 매 수마다 하려면 JS 로 옮겨야 한다(이 스크립트는 옮기지 않는다).
  - 곡은 원곡의 박 정렬(왼손이 33에서 들어옴)을 쓴다. 페이지의 엔진은 왼손을 0 부터 한 박 늦게 돌린다 — 판의 '곡' 과 이 '곡' 은 두 손 위상이 한 박 다르다.
  - 고리 비교는 (음높이, 길이) 집합이 같은가만 본다. 지속(막대 길이)·rate 구간은 비교하지 않는다.
  - 귀로 들리는가는 재지 않는다. '바뀐 스텝 수' 는 귀의 대리값일 뿐이다.

산출: docs/step3_data/rings_h1_probe.json
"""
import sys, os, io, json, time, random, subprocess, contextlib, datetime
from collections import Counter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    BASE = suite.setup_hibari()
from preprocessing import build_note_labels, group_notes_with_duration, build_chord_labels, chord_to_note_labels, prepare_lag_sequences
from weights import compute_intra_weights
from scipy.stats import spearmanr

PREDICTION = {
    'P0': '다 맞춘 판 → K=14, 고리 14개가 정본과 같다',
    'P1': '원 하나 사분 27가지 중 ≥20 이 고리 집합을 바꾼다',
    'P2': '남은 hibari 고리 중앙값 1수 > 3수 > 10수 > 30수, 30수 ≤ 54개 섞기 중앙값 + 1',
    'P3': '(탐색) 원 사분 한 번 > 무작위 칸 12개 섞기 (남은 hibari 고리 중앙값)',
    'P4': '바뀐 스텝 수 ↔ 위상 변화 스피어만 ρ > 0.3 (1·2·3·5수 판)',
}
CFG = dict(metric='dft', alpha=0.25, octave_weight=0.3, duration_weight=1.0, use_decayed=False, threshold=0.35)

# ── 고리판 칸표·회전 (페이지와 같은 엔진) ────────────────────────────────────
JS = r"""
const HS=require('./sketch/common.js'); globalThis.HS=HS; globalThis.HSCube=require('./sketch/cube-core.js');
const RG=require('./sketch/rings-core.js'); const H=HS.derive(require('./lenia/tonnetz.json')); const T=RG.create(H).table;
console.log(JSON.stringify({home:T.cell.map(c=>c.pitch), ev:T.cell.map(c=>c.ev.map(e=>e.step)), perm:RG.PERM, lmap:T.lmap}));
"""
TB = json.loads(subprocess.run(['node', '-e', JS], capture_output=True, text=True, check=True, cwd=ROOT).stdout)
HOME, EV, PERM = TB['home'], TB['ev'], TB['perm']
IDENT = list(range(54))

def turn(st, ring, k):
    P = PERM[ring]
    for _ in range(k % 4):
        o = list(st)
        for i in range(54): o[P[i]] = st[i]
        st = o
    return st

def cell_of(step, pitch):
    c = [i for i in range(54) if HOME[i] == pitch and step in EV[i]]
    assert len(c) == 1, (step, pitch, c)
    return c[0]

# 원곡 사건 → 칸 (오른손: 0 에서 32 주기 · 왼손: 32 에서 33 주기, 첫 칸이 쉼)
I1, I2 = BASE['inst1_real'], BASE['inst2_real']
C1 = [cell_of(s % 32, p) for s, p, e in I1]
C2 = []
for s, p, e in I2:
    l = (s - 32) % 33; assert l >= 1, s
    C2.append(cell_of(l - 1, p))

def piece(st):
    return ([(s, HOME[st[c]], e) for (s, p, e), c in zip(I1, C1)], [(s, HOME[st[c]], e) for (s, p, e), c in zip(I2, C2)])

def data_from(i1, i2):
    """setup_hibari 와 같은 전처리 (MIDI 읽기·손 나누기만 건너뛴다)."""
    notes_label, notes_counts = build_note_labels(i1[:59])
    chord_map_module, _ = build_chord_labels(group_notes_with_duration(i1[:59]))
    notes_dict = chord_to_note_labels(chord_map_module, notes_label); notes_dict['name'] = 'notes'
    m1, seq1 = build_chord_labels(group_notes_with_duration(i1))
    m2, seq2 = build_chord_labels(group_notes_with_duration(i2))
    inv = {v: k for k, v in chord_map_module.items()}
    for m in (m1, m2):                                          # 곡 전체의 화음 번호가 모듈의 화음 번호와 같은 화음인가
        for fs, lb in m.items(): assert inv.get(lb) == fs, '화음 번호가 모듈과 어긋난다'
    adn_i = prepare_lag_sequences(seq1, seq2, solo_timepoints=32, max_lag=4)
    nc = len(chord_map_module)                                  # setup_hibari 는 기본값 17(hibari 의 화음 수)을 쓴다 — 판에 따라 화음 수가 달라진다
    return {'notes_label': notes_label, 'notes_counts': notes_counts, 'notes_dict': notes_dict, 'adn_i': adn_i,
            'intra': compute_intra_weights(adn_i[1][0], num_chords=nc) + compute_intra_weights(adn_i[2][0], num_chords=nc),
            'num_notes': len(notes_label), 'num_chords': len(chord_map_module), 'inst1_real': i1, 'inst2_real': i2,
            'note_time_df': suite.build_note_time_df(notes_dict, adn_i, len(notes_label), suite.TOTAL_LENGTH), 'T': suite.TOTAL_LENGTH}

def cycles_of(st):
    i1, i2 = piece(st); d = data_from(i1, i2); suite.OVERLAP_CACHE.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        b = suite.build_overlap_bundle(d, **CFG)
    inv = {v - 1: k for k, v in d['notes_label'].items()}
    cyc = [frozenset(inv[i] for i in c) for c in b['cycle_labeled'].values()]
    mod = Counter(); ref = Counter()
    for s, p, e in i1:
        if s < 32: mod[(s, p, e - s)] += 1
    for s, p, e in I1:
        if s < 32: ref[(s, p, e - s)] += 1
    steps = sum(1 for t in range(32) if sorted(k for k in mod if k[0] == t) != sorted(k for k in ref if k[0] == t))
    return cyc, d['num_notes'], steps

HIB, HSET = None, None
def init(hib):
    global HIB, HSET
    HIB, HSET = hib, set(hib)

def jac(a, b): return len(a & b) / len(a | b)
def soft(S, pitch_only=False):
    """(사후 — 사전 예측에 없다) hibari 고리마다 이 판에서 가장 닮은 고리의 자카드 평균. 정확히 같은 고리만 세면 한 음만 바뀐 고리도 '잃음' 이 된다."""
    f = (lambda c: frozenset(p for p, d in c)) if pitch_only else (lambda c: c)
    T = [f(c) for c in S]
    return round(float(np.mean([max(jac(f(h), t) for t in T) if T else 0.0 for h in HIB])), 4)

def summary(st, tag, **kw):
    t1 = time.time(); cyc, nn, steps = cycles_of(st)
    S = set(cyc); kept = len(HSET & S); new = len(S - HSET)
    rec = {'tag': tag, 'K': len(cyc), 'notes': nn, 'kept': kept, 'lost': len(HSET) - kept, 'new': new,
           'jaccard': round(len(HSET & S) / max(1, len(HSET | S)), 4), 'steps_changed': steps,
           'moved_cells': sum(1 for i in range(54) if st[i] != i), 'soft_keep': soft(S), 'soft_keep_pitch': soft(S, True),
           'seconds': round(time.time() - t1, 1), **kw}
    rec['cycles'] = [sorted([list(x) for x in c]) for c in cyc]
    print(f"  {tag:14s} K={rec['K']:2d} 음{nn:2d} 남음{kept:2d} 잃음{rec['lost']:2d} 새{new:2d} 바뀐스텝{steps:2d} 칸{rec['moved_cells']:2d}"
          f" 닮음{rec['soft_keep']:.2f}/{rec['soft_keep_pitch']:.2f} {rec['seconds']}s", flush=True)
    return rec

def make_jobs():
    """판 목록 — 난수는 판을 만들 때만 쓰므로 순서대로 미리 만들어도 순차 실행과 같은 판이다 (run_rings_vineyard_probe.py 도 쓴다)."""
    jobs = [(IDENT, 'solved', {})]
    for ring in range(9):
        for k in (1, 2, 3):
            jobs.append((turn(IDENT, ring, k), f'single r{ring}k{k}', dict(group='single', ring=ring, k=k)))
    rng = random.Random(20261007)
    for L in (2, 3, 5, 10, 30):
        for sd in range(6):
            st, walk = IDENT, []
            for _ in range(L):
                r, k = rng.randrange(9), rng.choice((1, 2, 3)); st = turn(st, r, k); walk.append([r, k])
            jobs.append((st, f'walk{L} s{sd}', dict(group=f'walk{L}', walk=walk)))
    for sd in range(9):
        cells = rng.sample(range(54), 12); perm = cells[:]
        while any(a == b for a, b in zip(cells, perm)): rng.shuffle(perm)
        st = list(IDENT)
        for a, b in zip(cells, perm): st[a] = b
        jobs.append((st, f'rand12 s{sd}', dict(group='rand12')))
    for sd in range(6):
        st = list(IDENT); rng.shuffle(st)
        jobs.append((st, f'rand54 s{sd}', dict(group='rand54')))
    return jobs

def job(a): return summary(a[0], a[1], **a[2])

if __name__ == '__main__':
    from multiprocessing import Pool
    t0 = time.time()
    hib, n0, _ = cycles_of(IDENT); init(hib)
    suite.OVERLAP_CACHE.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        cb = suite.build_overlap_bundle(BASE, **CFG)
    inv0 = {v - 1: k for k, v in BASE['notes_label'].items()}
    CANON = [frozenset(inv0[i] for i in c) for c in cb['cycle_labeled'].values()]
    print(f'P0 다 맞춘 판 K={len(HIB)} 음 {n0} · 정본 K={len(CANON)} · 같은 고리 {len(HSET & set(CANON))} · {time.time() - t0:.1f}s', flush=True)

    jobs = make_jobs()
    with Pool(7, initializer=init, initargs=(HIB,)) as pool:
        rows = pool.map(job, jobs, chunksize=1)

    def med(g, key='kept'):
        v = [r[key] for r in rows if r.get('group') == g]; return float(np.median(v)) if v else None
    single = [r for r in rows if r.get('group') == 'single']
    changed = sum(1 for r in single if r['lost'] or r['new'])
    mk = {g: med(g) for g in ('single', 'walk2', 'walk3', 'walk5', 'walk10', 'walk30', 'rand12', 'rand54')}
    mono = mk['single'] > mk['walk3'] > mk['walk10'] > mk['walk30']
    pp = [r for r in rows if r.get('group') in ('single', 'walk2', 'walk3', 'walk5')]
    rho, pv = spearmanr([r['steps_changed'] for r in pp], [r['lost'] + r['new'] for r in pp])
    VERDICT = {
        'P0': {'pass': len(HIB) == 14 and HSET == set(CANON), 'K': len(HIB), 'same_as_canon': len(HSET & set(CANON))},
        'P1': {'pass': changed >= 20, 'changed': changed, 'of': len(single)},
        'P2': {'pass': bool(mono and mk['walk30'] <= mk['rand54'] + 1), 'medians_kept': mk},
        'P3': {'pass': mk['single'] > mk['rand12'], 'single': mk['single'], 'rand12': mk['rand12'], 'note': '탐색'},
        'P4': {'pass': bool(rho > 0.3), 'spearman_rho': round(float(rho), 4), 'p': float(pv), 'n': len(pp)},
    }
    for k, v in VERDICT.items(): print(k, 'PASS' if v['pass'] else 'FAIL', {a: b for a, b in v.items() if a != 'pass'})
    POSTHOC = {g: {'soft_keep': med(g, 'soft_keep'), 'soft_keep_pitch': med(g, 'soft_keep_pitch'), 'K': med(g, 'K'), 'new': med(g, 'new'),
                   'steps_changed': med(g, 'steps_changed')}
               for g in ('single', 'walk2', 'walk3', 'walk5', 'walk10', 'walk30', 'rand12', 'rand54')}
    print('사후(중앙값)', json.dumps(POSTHOC, ensure_ascii=False))
    out = {'script': 'experiments/run_rings_h1_probe.py', 'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
           'config': CFG, 'prediction': PREDICTION, 'verdict': VERDICT, 'posthoc_medians': POSTHOC,
           'hibari_cycles': [sorted([list(x) for x in c]) for c in HIB], 'rows': rows, 'seconds': round(time.time() - t0, 1)}
    dst = os.path.join(ROOT, 'docs', 'step3_data', 'rings_h1_probe.json')
    json.dump(out, open(dst, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('저장', dst, f'{time.time() - t0:.0f}s')
