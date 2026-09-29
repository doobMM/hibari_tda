"""
run_cycle_markov.py — 고리-Markov 연쇄를 Algorithm 1 에 접목한다 (docs/tonnetz_lenia_spec.md §5 R1~R4)

무엇을 바꾸나
  Algorithm 1 은 활성 고리들의 풀(공유 가중 합집합)에서 음을 **균등하게** 뽑는다 (generation.py:367).
  고리-Markov 는 그 한 줄만 바꾼다: 직전에 뽑힌 음 v 에서, 활성 고리 k 의 **향을 준 순회**에서
  v 다음 음 succ_k(v) 들 가운데 하나를 뽑는다 (여러 활성 고리가 같은 다음 음을 주면 그만큼 겹쳐 담는다 —
  풀의 공유 가중과 같은 규칙). 후보가 없거나 전부 막히면 원래 풀 추출로 돌아간다.
  = Kalpazidou 순환 표현: 전이 P(v→u) ∝ Σ_{k 활성} [v→u ∈ C_k]. 정상 흐름이 고리 순환들의 합이다.

팔 (같은 시드 20개, 짝지은 비교)
  algo1        generation.algorithm1_optimized 그대로 (정본 경로)
  copy_off     이 파일의 사본, Markov 끔 → algo1 과 **비트 동일해야 한다** (하네스 검사 H1)
  markov       향 = 곡의 시간 방향 (export_tonnetz_lenia_data.py 와 같은 투표)
  reverse      향 뒤집기                                   (R4)
  shuffled     같은 고리 집합, 순회 순서만 무작위 (시드마다) — 메커니즘 뺀 대조군 (R3)

OM 두 개
  tonnetz  Tonnetz α=0.5 K=41, 연속 활성도 ≥ 0.35 이진 (lenia/tonnetz.json 의 순회 = 페이지와 같은 것)
  dft      정본 DFT α=0.25 K=14, per-cycle τ (헤드라인 JS=0.00902 의 OM). 순회 = lenia/hibari.json

지표
  js            음높이 분포 JS (eval_metrics — 헤드라인과 같은 정의)
  h_int_js      **수평 음정 JS** — 이웃한 두 onset 시각 사이 모든 음 쌍 (p→q) 의 음정 q−p 분포. 한 onset 안의
                순서와 무관하다
  v_ic_js       **수직 음정류 JS** — 한 onset 안 음 쌍의 음정류(0~6) 분포
  transition_js eval_metrics.transition_matrix_similarity 그대로 (참고용). ⚠ 한 onset 안 음의 **순서**에
                의존한다 — 원곡은 MIDI 기록 순서, 생성은 추출 순서라 둘 다 음악적 뜻이 없다. 판정에 쓰지 않는다

PREDICTION (실행 전, spec §5 그대로)
  R1  markov 는 h_int_js 를 algo1 대비 10% 이상 낮춘다 (tonnetz OM)
  R2  js 는 algo1 대비 ±30% 안
  R3  shuffled 는 R1 이득의 절반 이상을 잃는다
  R4  reverse 는 markov 와 h_int_js 5% 안 (시간 방향 효과는 작다 — 불확실)

산출: docs/step3_data/cycle_markov_results.json
"""
import sys, os, io, json, random, contextlib, datetime
from collections import Counter, defaultdict
import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
import generation as gen
from generation import NodePool, CycleSetManager, algorithm1_optimized
from eval_metrics import evaluate_generation, transition_matrix_similarity

N_SEEDS, SEED0 = 20, 20260929
ORIG = list(data['inst1_real']) + list(data['inst2_real'])
N = data['num_notes']
LAB = sorted(((v - 1, k[0], k[1]) for k, v in data['notes_label'].items()))
PD2L = {(p, d): i for i, p, d in LAB}

# ── 곡의 시간 방향 (export_tonnetz_lenia_data.py 와 같은 투표) ─────────────
PAIRS = Counter()
for inst in (data['inst1_real'], data['inst2_real']):
    by = defaultdict(list)
    for s, p, e in inst:
        li = PD2L.get((p, e - s))
        if li is not None: by[s].append(li)
    ev = sorted(by.items())
    for (_, a), (_, b) in zip(ev, ev[1:]):
        for x in a:
            for y in b: PAIRS[(x, y)] += 1

def orient(t):
    fw = sum(PAIRS[(t[i], t[(i + 1) % len(t)])] for i in range(len(t)))
    bw = sum(PAIRS[(t[(i + 1) % len(t)], t[i])] for i in range(len(t)))
    return t if fw >= bw else [t[0]] + t[1:][::-1]

def succ_of(loops):
    out = []
    for o in loops:
        d = {}
        if o:
            for i, v in enumerate(o): d[v] = o[(i + 1) % len(o)]
        out.append(d)
    return out

# ── OM 두 개 ───────────────────────────────────────────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    bt = suite.build_overlap_bundle(data, 'tonnetz', alpha=0.5, octave_weight=0.3, duration_weight=1.0,
                                    use_decayed=False, threshold=0.35)
    bd = suite.build_overlap_bundle(data, 'dft', alpha=0.25, octave_weight=0.3, duration_weight=1.0,
                                    use_decayed=False, threshold=0.35)
TJ = json.load(open('lenia/tonnetz.json', encoding='utf8'))
kt = list(bt['cycle_labeled'].keys())
assert [sorted(set(bt['cycle_labeled'][k])) for k in kt] == TJ['cycles'], '페이지 데이터와 고리가 다르다'
OM_T = (bt['activation_continuous'][kt].values >= 0.35).astype(int)
LOOPS_T = [l['order'] for l in TJ['loops']]

kd = list(bd['cycle_labeled'].keys())
grid = json.load(open('docs/step3_data/percycle_tau_dft_gap0_alpha_grid_results.json', encoding='utf8'))
r025 = next(r for r in grid['results'] if abs(float(r['alpha']) - 0.25) < 1e-9)
OM_D = (bd['activation_continuous'][kd].values >= np.array(r025['tau_profile'])).astype(int)
HJ = json.load(open('lenia/hibari.json', encoding='utf8'))
trav_by_set = {frozenset(t): t for t in HJ['traversal'] if t}
LOOPS_D = [orient(list(trav_by_set[frozenset(bd['cycle_labeled'][k])])) for k in kd]
CL_T = {i: tuple(bt['cycle_labeled'][k]) for i, k in enumerate(kt)}
CL_D = {i: tuple(bd['cycle_labeled'][k]) for i, k in enumerate(kd)}

# ── 사본 Algorithm 1 — 음을 고르는 한 곳만 바꾼다 ─────────────────────
def sample_at(j, length, flag, om, pool, mgr, checker, max_resample, succ, prev):
    cand = None
    if succ is not None and prev is not None and flag > 0:
        cand = [succ[k][prev] for k in np.nonzero(om[j, :])[0] if prev in succ[k]]
    for attempt in range(max_resample):
        if cand:                                   # 고리-Markov 걸음
            z = random.choice(cand)
        elif flag == 0:
            z = gen._sample_avoiding_neighbors(j, length, om, pool, mgr)
        else:
            ip = mgr.get_intersect_nodes(om[j, :])
            z = pool.sample() if ip is None else random.choice(ip)
        tup = pool.label_to_note_info(z)
        if tup is None:
            if cand: cand = [c for c in cand if c != z]
            continue
        p, d = tup
        n1, n2 = (j, p, j + d), (p, d)
        if n1[2] > length:
            if j + 1 <= length: n1, n2 = (j, p, length), (p, length - j)
            else: continue
        if n2 in checker[j]:
            if cand: cand = [c for c in cand if c != z]
            continue
        return n1, n2, z
    return None

def algo1_copy(pool, inst_len, om, mgr, succ=None, max_resample=50, head_only=False):
    """head_only=True: onset 의 **첫 음만** 고리를 걷고(직전 onset 의 첫 음에서), 나머지는 원래 풀 추출.
    = 페이지(종달새와 문어)의 설계 — 선율 한 음은 고리-Markov, 화음은 Algorithm 1. ⚠ 사후 팔(아래 참고)."""
    length = len(inst_len); inst_len = list(inst_len)
    out, checker, prev = [], {i: set() for i in range(length)}, None
    for j in range(length):
        for s in range(max(0, inst_len[j])):
            use = succ if (not head_only or s == 0) else None
            info = sample_at(j, length, om[j, :].sum(), om, pool, mgr, checker, max_resample, use, prev)
            if info is None: continue
            n1, n2, z = info
            out.append(n1); checker[j].add(n2)
            if not head_only or s == 0: prev = z
            for t in range(j + 1, min(n1[2], length)):
                inst_len[t] = max(0, inst_len[t] - 1); checker[t].add(n2)
    return out

# ── 지표 ───────────────────────────────────────────────────────────────
def jsd(a, b):
    keys = sorted(set(a) | set(b)); eps = 1e-10
    p = np.array([a.get(k, 0) for k in keys], float); q = np.array([b.get(k, 0) for k in keys], float)
    p = p / p.sum() + eps; q = q / q.sum() + eps; p /= p.sum(); q /= q.sum(); m = (p + q) / 2
    return float(0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m)))

def intervals(notes):
    by = defaultdict(list)
    for s, p, e in notes: by[s].append(p)
    ts = sorted(by); h, v = Counter(), Counter()
    for a, b in zip(ts, ts[1:]):
        for p in by[a]:
            for q in by[b]: h[q - p] += 1
    for t in ts:
        ps = by[t]
        for i in range(len(ps)):
            for k in range(i + 1, len(ps)):
                ic = abs(ps[i] - ps[k]) % 12; v[min(ic, 12 - ic)] += 1
    return h, v
H0, V0 = intervals(ORIG)

def score(notes):
    ev = evaluate_generation(notes, [data['inst1_real'], data['inst2_real']], data['notes_label'], name='')
    h, v = intervals(notes)
    return {'js': ev['js_divergence'], 'h_int_js': jsd(H0, h), 'v_ic_js': jsd(V0, v) if v else None,
            'same_pc_pairs': v[0] / max(1, sum(v.values())),
            'transition_js': transition_matrix_similarity(notes, ORIG)['transition_js'], 'n_notes': len(notes)}

# ── 실행 ───────────────────────────────────────────────────────────────
def run(om, cl, loops):
    arms = {a: [] for a in ('algo1', 'copy_off', 'markov', 'reverse', 'shuffled', 'head', 'head_shuffled')}
    ident = 0
    fwd, rev = succ_of(loops), succ_of([[o[0]] + o[1:][::-1] if o else None for o in loops])
    for i in range(N_SEEDS):
        seed = SEED0 + i
        def fresh():
            suite.set_all_seeds(seed)
            return NodePool(data['notes_label'], data['notes_counts'], num_modules=65), CycleSetManager(cl)
        p, m = fresh(); a = algorithm1_optimized(p, suite.INST_CHORD_HEIGHTS, om, m, max_resample=50,
                                                 verbose=False, min_onset_gap=0)
        p, m = fresh(); c = algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, None)
        ident += int(a == c)
        arms['algo1'].append(score(a)); arms['copy_off'].append(score(c))
        p, m = fresh(); arms['markov'].append(score(algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, fwd)))
        p, m = fresh(); arms['reverse'].append(score(algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, rev)))
        rng = random.Random(seed * 7 + 1)
        shuf = [rng.sample(o, len(o)) if o else None for o in loops]
        p, m = fresh(); arms['shuffled'].append(score(algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, succ_of(shuf))))
        # ⚠ 사후 팔 (1차 결과를 본 뒤 추가, 2026-09-29): 'markov' 가 한 onset 안에서 고리를 이어 걸어 같은 음이름을
        #   쌓는다(v_ic +650%)는 진단 뒤, **페이지가 실제로 쓰는 방식**(첫 음만 걷기)을 잰다. 확증이 아니라 탐색이다.
        p, m = fresh(); arms['head'].append(score(algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, fwd, head_only=True)))
        p, m = fresh(); arms['head_shuffled'].append(score(algo1_copy(p, suite.INST_CHORD_HEIGHTS, om, m, succ_of(shuf),
                                                                    head_only=True)))
    return arms, ident

def summarize(arms):
    out = {}
    for a, rows in arms.items():
        out[a] = {k: {'mean': float(np.mean([r[k] for r in rows])), 'std': float(np.std([r[k] for r in rows], ddof=1))}
                  for k in rows[0] if rows[0][k] is not None}
    def paired(x, y, k):
        u = np.array([r[k] for r in arms[x]]); v = np.array([r[k] for r in arms[y]])
        return {'delta_pct': float((u.mean() - v.mean()) / v.mean() * 100),
                'wilcoxon_p': float(stats.wilcoxon(u, v).pvalue) if np.any(u != v) else 1.0,
                'paired_t_p': float(stats.ttest_rel(u, v).pvalue) if np.any(u != v) else 1.0}
    tests = {f'{x}_vs_{y}:{k}': paired(x, y, k)
             for x, y in [('markov', 'algo1'), ('shuffled', 'algo1'), ('reverse', 'markov'), ('shuffled', 'markov'),
                          ('head', 'algo1'), ('head_shuffled', 'head')]
             for k in ('js', 'h_int_js', 'v_ic_js', 'transition_js', 'same_pc_pairs')}
    return out, tests

_h, _v = H0, V0
result = {'script': 'experiments/run_cycle_markov.py', 'original_same_pc_pairs': _v[0] / sum(_v.values()),
          'posthoc_arms': ['head', 'head_shuffled'], 'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
          'n_seeds': N_SEEDS, 'seed0': SEED0,
          'prediction': {'R1': 'markov h_int_js <= 0.9 x algo1 (tonnetz OM)', 'R2': '|markov js / algo1 js - 1| <= 0.30',
                         'R3': 'shuffled loses >= half of R1 gain', 'R4': '|reverse / markov - 1| <= 0.05 on h_int_js'}}
for name, om, cl, loops in [('tonnetz', OM_T, CL_T, LOOPS_T), ('dft', OM_D, CL_D, LOOPS_D)]:
    arms, ident = run(om, cl, loops)
    summ, tests = summarize(arms)
    result[name] = {'K': len(cl), 'om_zero_rows': int((om.sum(1) == 0).sum()), 'H1_copy_identical': f'{ident}/{N_SEEDS}',
                    'summary': summ, 'tests': tests, 'per_seed': arms}
    print(f'\n== {name} K={len(cl)}  zero rows {result[name]["om_zero_rows"]}  H1 사본 동일 {ident}/{N_SEEDS}')
    for a in arms:
        s = summ[a]
        print(f'  {a:9s} js {s["js"]["mean"]:.5f}±{s["js"]["std"]:.5f}  h_int {s["h_int_js"]["mean"]:.5f}  '
              f'v_ic {s["v_ic_js"]["mean"]:.5f}  samePC {s["same_pc_pairs"]["mean"]:.3f}  '
              f'trans {s["transition_js"]["mean"]:.4f}  n {s["n_notes"]["mean"]:.0f}')
    for k, t in tests.items():
        if k.split(':')[1] in ('js', 'h_int_js', 'v_ic_js'):
            print(f'  {k:32s} {t["delta_pct"]:+7.1f}%  wilcoxon p={t["wilcoxon_p"]:.2g}')

json.dump(result, open('docs/step3_data/cycle_markov_results.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('\n저장 docs/step3_data/cycle_markov_results.json')
