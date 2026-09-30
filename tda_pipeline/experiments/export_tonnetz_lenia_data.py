"""
export_tonnetz_lenia_data.py — 종달새와 문어 (docs/tonnetz_lenia_spec.md) 의 데이터

⛔ cache/metric_tonnetz.pkl 을 쓰지 않는다 — K=47, 설정이 다르다. 정본 경로(build_overlap_bundle,
   use_decayed=False, ow=0.3, dw=1.0) 에서 Tonnetz α=0.5 로 다시 계산한다 → K=41.

산출: tda_pipeline/lenia/tonnetz.json
  labels      23 음 — label_idx · pitch · dur · count · pc
  cycles      Tonnetz 고리 41개 (0-indexed label_idx, 정렬)
  loops       고리마다 향을 준 순회 순서 · 복원 방식(ph | lattice | none) · 향 투표(순/역) · 가중 w
  hands       두 손의 리듬 고리 (첫 온전한 모듈의 onset 수) 와 처음 8모듈의 onset (시각, 음높이들)
  checks      K · 순회 복원 수 · 걸음 국소성 (spec §2.2) · 두 손 무늬 동일성 (spec §2.1)

순회 순서
  ph       PH 원 변 목록에서 복원 (export_lenia_data.py 와 같은 방법, 모든 rate 의 바코드)
  lattice  복원 실패 고리 — **격자 국소 걸음(음이름 Tonnetz 거리 ≤ 1)만으로** 해밀턴 순환을 찾는다.
           여럿이면 Tonnetz 음악거리 합이 가장 작은 것. 부분집합 DP (고리 크기 ≤ 15).
  none     그런 순환이 없다 → Markov 에서 뺀다 (Algorithm 1 의 고리 집합에는 남는다)

향 (곡의 시간 방향)
  손마다 이웃한 두 onset 시각의 모든 음 쌍 (a → b) 을 센다. 순회의 순방향 변이면 +1, 역방향이면 −1.
  합 ≥ 0 이면 순회 순서 그대로, 아니면 뒤집는다. 투표 수를 그대로 남긴다(얼마나 확실한지 보이게).

가중 w_k = 원곡에서 고리 k 의 평균 연속 활성도 (정본 경로의 activation_continuous).
"""
import sys, os, io, json, contextlib, datetime
from collections import Counter, defaultdict
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments'), os.path.join(ROOT, 'hibari_dashboard', 'scripts')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
from add_cycle_traversal import parse_edges, traverse_cycle

METRIC, ALPHA, OW, DW = 'tonnetz', 0.5, 0.3, 1.0
N = data['num_notes']
LAB = sorted(((v - 1, k[0], k[1]) for k, v in data['notes_label'].items()))   # (label_idx, pitch, dur)
assert [l[0] for l in LAB] == list(range(N))
PITCH = [l[1] for l in LAB]; DUR = [l[2] for l in LAB]
PD2L = {(p, d): i for i, p, d in LAB}
COUNT = data['notes_counts']

def pc_step(a, b):
    """두 음(label) 의 음높이 류가 Tonnetz 에서 몇 걸음인가 — 0 같은 류, 1 이웃(±3 ±4 ±7), 2 그 밖."""
    d = (PITCH[b] - PITCH[a]) % 12
    return 0 if d == 0 else (1 if d in (3, 4, 5, 7, 8, 9) else 2)

# ── 번들 (정본 경로, Tonnetz) ─────────────────────────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    bundle = suite.build_overlap_bundle(data, METRIC, alpha=ALPHA, octave_weight=OW, duration_weight=DW,
                                        use_decayed=False, threshold=0.35)
keys = list(bundle['cycle_labeled'].keys())
CY = [sorted(set(bundle['cycle_labeled'][k])) for k in keys]
K = len(CY)
ACT = bundle['activation_continuous'][keys].values.astype(float)       # (1088, K)
W = ACT.mean(0)

# ── 순회 순서 1: PH 원 변 목록 ────────────────────────────────────────
inter = suite.compute_inter_weights(data['adn_i'][1][1], data['adn_i'][2][1], num_chords=data['num_chords'], lag=1)
oor = suite.compute_out_of_reach(inter, power=-2)
MUS = np.asarray(suite.metric_distance_matrix(data['notes_label'], METRIC, OW, DW), float)
# 정본 번들과 **같은 루프**(rate += 0.01, r = round(rate, 2))로 rate 마다 바코드를 모은다.
# 이 profile 하나로 ① 순회 순서 ② 고리마다 살아 있는 rate 구간(vine) ③ rate 격자 위 거리 행렬을 뽑는다.
from overlap import group_rBD_by_homology, label_cycles_from_persistence
trav, profile, DGRID, rate = {}, [], {}, 0.0
while rate <= 1.5 + 1e-10:
    r = round(rate, 2)
    fd = suite.compute_distance_matrix(data['intra'] + r * inter, data['notes_dict'], oor, num_notes=N).values
    hd = suite.compute_hybrid_distance(fd, MUS, alpha=ALPHA)
    if abs(r * 10 - round(r * 10)) < 1e-9: DGRID[f'{r:.1f}'] = np.round(np.asarray(hd, float), 4).tolist()
    bd = suite.generate_barcode_numpy(mat=hd, listOfDimension=[1],
                                      exactStep=True, birthDeathSimplex=False, sortDimension=False)
    profile.append((r, bd))
    rate += 0.01
    for e in bd:
        if not isinstance(e, list) or len(e) < 3 or e[0] != 1: continue
        ed = parse_edges(str(e[2]).strip()); vs = frozenset(v for x in ed for v in x)
        if ed and vs not in trav:
            t = traverse_cycle(ed)
            if t is not None and set(t) == vs: trav[vs] = t

# ── 음 단위 intra(손별)·inter 가중치 — 사용자의 설계 그대로, 역수(거리) 변환 전 단계 ───────────
# weights.compute_intra_weights(한 손의 화음 전이, lag 1) · compute_inter_weights(두 손, lag 1, 양방향)
# → refine_connectedness_fast(화음 → 음) → 대칭 전체 행렬 → 최댓값 1 로 정규화. 3판 비옥도(성장 가산)가 쓴다.
from weights import compute_intra_weights, refine_connectedness_fast, to_upper_triangular
def note_w(Wc):
    up = refine_connectedness_fast(to_upper_triangular(Wc), data['notes_dict'], N).values.astype(float)
    full = np.triu(up) + np.triu(up, 1).T
    return (full / full.max()).round(4).tolist() if full.max() > 0 else full.tolist()
W_INTRA_R = note_w(compute_intra_weights(data['adn_i'][1][0], num_chords=data['num_chords']))
W_INTRA_L = note_w(compute_intra_weights(data['adn_i'][2][0], num_chords=data['num_chords']))
W_INTER = note_w(inter)

# ── vine: 고리마다 H₁ 생성원으로 나타나는 rate 들 (group_rBD_by_homology = 정본 번들이 쓰는 그 함수) ──
PERS = group_rBD_by_homology(profile, dim=1)
lab2 = label_cycles_from_persistence(PERS)
assert [sorted(set(lab2[i])) for i in range(len(lab2))] == CY, '정본 번들과 고리 순서·집합이 다르다'
def intervals(rs):
    rs = sorted(set(round(x, 2) for x in rs)); out = []
    for x in rs:
        if out and abs(x - out[-1][1] - 0.01) < 1e-6: out[-1][1] = x
        else: out.append([x, x])
    return out
VINES = []
for i in range(len(lab2)):
    rec = PERS[lab2[i]]
    VINES.append({'rates': intervals([r for r, b, d in rec]), 'n_rates': len(set(round(r, 2) for r, b, d in rec)),
                  'birth_death': [[round(r, 2), float(b), float(d)] for r, b, d in rec][:200]})

# ── 순회 순서 2: 격자 국소 해밀턴 순환 (부분집합 DP) ────────────────────
def lattice_loop(vs):
    vs = list(vs); m = len(vs)
    ok = [[pc_step(vs[i], vs[j]) <= 1 and i != j for j in range(m)] for i in range(m)]
    INF = float('inf'); FULL = 1 << m
    dp = [[INF] * m for _ in range(FULL)]; par = [[-1] * m for _ in range(FULL)]
    dp[1][0] = 0.0
    for S in range(FULL):
        if not S & 1: continue
        for j in range(m):
            c = dp[S][j]
            if c == INF: continue
            for k in range(m):
                if S >> k & 1 or not ok[j][k]: continue
                T = S | 1 << k; v = c + MUS[vs[j], vs[k]]
                if v < dp[T][k]: dp[T][k] = v; par[T][k] = j
    best, last = INF, -1
    for j in range(1, m):
        if ok[j][0] and dp[FULL - 1][j] + MUS[vs[j], vs[0]] < best:
            best, last = dp[FULL - 1][j] + MUS[vs[j], vs[0]], j
    if last < 0: return None
    order, S, j = [], FULL - 1, last
    while j != -1:
        order.append(vs[j]); pj = par[S][j]; S ^= 1 << j; j = pj
    return order[::-1]

# ── 곡의 시간 방향: 손마다 이웃한 두 onset 시각의 음 쌍 ─────────────────
def onsets(inst):
    by = defaultdict(list)
    for s, p, e in inst:
        li = PD2L.get((p, e - s))
        if li is not None: by[s].append(li)
    return sorted(by.items())
PAIRS = Counter()
for inst in (data['inst1_real'], data['inst2_real']):
    ev = onsets(inst)
    for (t0, a), (t1, b) in zip(ev, ev[1:]):
        for x in a:
            for y in b: PAIRS[(x, y)] += 1

loops, steps = [], Counter()
for k, c in enumerate(CY):
    t = trav.get(frozenset(c)); how = 'ph'
    if t is None:
        t = lattice_loop(c); how = 'lattice' if t is not None else 'none'
    if t is None:
        loops.append({'order': None, 'how': how, 'votes': [0, 0], 'w': round(float(W[k]), 6)}); continue
    fw = sum(PAIRS[(t[i], t[(i + 1) % len(t)])] for i in range(len(t)))
    bw = sum(PAIRS[(t[(i + 1) % len(t)], t[i])] for i in range(len(t)))
    if bw > fw: t = [t[0]] + t[1:][::-1]; fw, bw = bw, fw      # 투표는 최종 향 기준 [맞음, 어긋남]
    for i in range(len(t)):
        steps[(how, pc_step(t[i], t[(i + 1) % len(t)]))] += 1
    loops.append({'order': [int(v) for v in t], 'how': how, 'votes': [fw, bw], 'w': round(float(W[k]), 6)})

# ── 두 손의 리듬 고리 ──────────────────────────────────────────────────
def counts(inst):
    c = Counter(s for s, p, e in inst); T = max(c) + 1
    return [c.get(t, 0) for t in range(T)]
c1, c2 = counts(data['inst1_real']), counts(data['inst2_real'])
first2 = next(t for t, v in enumerate(c2) if v)                 # 왼손이 처음 우는 시각 (33)
ring1 = c1[0:32]
ring2 = c2[first2 - 1:first2 - 1 + 33] if c2[first2 - 1] == 0 else c2[first2:first2 + 33]
# 두 손 무늬 동일성: 왼손 고리에서 쉼 한 칸을 빼면 오른손 고리와 같은가 (spec §2.1)
same = any(ring2[:i] + ring2[i + 1:] == ring1 for i in range(33) if ring2[i] == 0)
# 오른손 34모듈이 첫 모듈과 같은 비율 / 왼손은 33 주기로 같은 비율
rep1 = np.mean([c1[m * 32:(m + 1) * 32] == ring1 for m in range(len(c1) // 32)])
off2 = first2 - 1 if c2[first2 - 1] == 0 else first2
rep2 = np.mean([c2[off2 + m * 33: off2 + (m + 1) * 33] == ring2 for m in range((len(c2) - off2) // 33)])

def early(inst, t0, n_mod, per):
    by = defaultdict(list)
    for s, p, e in inst:
        if t0 <= s < t0 + n_mod * per: by[s - t0].append(p)
    return [[int(t), sorted(ps)] for t, ps in sorted(by.items())]

out = {
    'source': f'{METRIC} α={ALPHA} ow={OW} dw={DW} use_decayed=False threshold=0.35 — export_tonnetz_lenia_data.py',
    'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
    'labels': [{'li': i, 'pitch': p, 'dur': d, 'count': int(COUNT.get((p, d), 0)) if isinstance(COUNT, dict) else None,
                'pc': p % 12} for i, p, d in LAB],
    'cycles': [[int(v) for v in c] for c in CY],
    'loops': loops,
    'hands': {
        'lark':    {'hand': 1, 'period': 32, 'ring': ring1, 'early': early(data['inst1_real'], 0, 8, 32)},
        'octopus': {'hand': 2, 'period': 33, 'ring': ring2, 'early': early(data['inst2_real'], off2, 8, 33)},
    },
    # 원곡 두 손의 음높이 빈도 — 검증 V6 이 eval_metrics 와 같은 정의로 JS 를 잰다
    'note_weights': {'intra_right': W_INTRA_R, 'intra_left': W_INTRA_L, 'inter': W_INTER,
                     'note': '음 단위 가중치(정규화). timeflow = intra(w1+w2) + rate × inter 의 재료. 3판 비옥도용'},
    'vines': VINES,                     # 고리 i 가 살아 있는 rate 구간들 (0~1.5, 0.01 간격)
    'dist_grid': DGRID,                 # rate 0.0~1.5 (0.1 간격) 의 23×23 음 거리 = PH 가 실제로 보는 행렬 (intra + rate·inter, Tonnetz α=0.5)
    'orig_pitch_counts': {str(k): v for k, v in sorted(Counter(p for s, p, e in list(data['inst1_real']) + list(data['inst2_real'])).items())},
    'checks': {
        'K': K,
        'loops_by_method': dict(Counter(l['how'] for l in loops)),
        'loop_steps_pc_distance': {f'{h}:{d}': n for (h, d), n in sorted(steps.items())},
        'loop_steps_local_fraction': round(sum(n for (h, d), n in steps.items() if d <= 1) / max(1, sum(steps.values())), 4),
        'orientation_votes_total': [sum(l['votes'][0] for l in loops), sum(l['votes'][1] for l in loops)],
        'orientation_ties': sum(1 for l in loops if l['order'] and l['votes'][0] == l['votes'][1]),
        'hand_patterns_same_but_one_rest': bool(same),
        'hand1_modules_equal_first': round(float(rep1), 4),
        'hand2_modules_equal_first_period33': round(float(rep2), 4),
        'om_mean_activation': round(float(ACT.mean()), 4),
    },
}
if not isinstance(COUNT, dict):
    cnt = Counter()
    for inst in (data['inst1_real'][:59],):
        for s, p, e in inst: cnt[(p, e - s)] += 1
    for l in out['labels']: l['count'] = int(cnt.get((l['pitch'], l['dur']), 0))

dst = os.path.join(ROOT, 'lenia', 'tonnetz.json')
json.dump(out, open(dst, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
print('저장', dst, os.path.getsize(dst), 'bytes')
for k, v in out['checks'].items(): print(f'  {k:38s} {v}')
print('  ring lark   ', ring1)
print('  ring octopus', ring2)
