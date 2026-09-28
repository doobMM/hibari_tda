"""
run_lenia_rule.py — 단계 1b: Lenia 갱신 규칙 검증 (docs/lenia_spec.md §4-1, §5)

규칙 (탐색하는 매개변수 없음 — 값은 export_lenia_data.py 가 전반부에서 유도했다)
  U_c = 연속 활성도 (overlap.py 그대로)
  G_c = +1 if τ_c ≤ U_c ≤ u_max else −1          (Lenia 사각형 성장, 하한 = 헤드라인 τ_c)
  A_c ← clip(A_c + G_c / T, 0, 1),  OM_c = [A_c ≥ ½]

사전 예측 (명세 §5, 실행 전에 적었다)
  R0  T=1, u_max=1 → 헤드라인 OM 과 100% 일치. **구현 검사 — 실패하면 중단**
  R1  T=25 는 정본 ① 이진 scale OM 과의 일치율을 올린다 (후반부 544~1087 에서 판정)
  R2  T=25 에서 음높이 JS 는 거의 변하지 않는다 (N=20, 같은 시드, paired)
  R3  T=25 에서 시간 정렬 지표는 나빠진다

  ⚠ R3 수정 — 실행 전, 결과를 보기 전에 적는다.
     명세는 DTW 를 적었으나 sequence_metrics.dtw_pitch_distance 는 시간축을 휘어 정렬하고
     음의 순서만 본다. 관성이 만드는 지연을 흡수할 것으로 예상된다(= 둔감).
     그래서 DTW 는 등록대로 재되, **모듈(32스텝) 단위로 시간을 맞춘 음높이 JS** 를 추가한다.
     이것이 "언제" 를 보는 자다. 두 지표 모두 보고한다.

하네스 검증: T=1 (= 헤드라인 OM) 으로 헤드라인의 all_js 20개를 **비트 단위로** 재현한다.
  seed_base = 100000 + α 격자 인덱스 2 × 10000 + 5000 = 125000 (run_percycle_tau_dft_alpha_grid.py)
  그리고 이 스크립트의 생성 루프가 suite.run_algo1_trials 와 같은 값을 내는지도 확인한다.

산출: docs/step3_data/lenia_rule_results.json
      tools/verify/lenia_fixture.json   (JS 포트 대조용 — om_bank 순서)
"""
import sys, os, io, json, contextlib, datetime
import numpy as np
from scipy.stats import ttest_rel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
    bundle = suite.build_overlap_bundle(data, 'dft', alpha=0.25, octave_weight=0.3,
                                        duration_weight=1.0, use_decayed=False, threshold=0.35)
from sequence_metrics import dtw_pitch_distance
from eval_metrics import pitch_distribution_similarity

CL = bundle['cycle_labeled']; keys = list(CL.keys())
U = bundle['activation_continuous'][keys].values.astype(np.float64)       # (1088, 14) 번들 순서
B = bundle['overlap_binary'][keys].values.astype(np.int8)
grid = json.load(open('docs/step3_data/percycle_tau_dft_gap0_alpha_grid_results.json', encoding='utf8'))
r025 = next(r for r in grid['results'] if abs(float(r['alpha']) - 0.25) < 1e-9)
TAU = np.array(r025['tau_profile'], dtype=np.float64)                     # 번들 순서
rule = json.load(open('lenia/hibari.json', encoding='utf8'))['rule']
T_L, U_MAX = int(rule['T']), float(rule['u_max_generation'])
SEED_BASE, NREP, H = 125000, 20, 544


def lenia_om(Useq, tau, T, u_max):
    """Lenia 사각형 성장. 한 스텝씩 — A 가 경로에 의존하므로 통째로 계산할 수 없다."""
    A = np.zeros(Useq.shape[1]); out = np.zeros(Useq.shape, dtype=np.float32)
    for t in range(len(Useq)):
        g = np.where((Useq[t] >= tau) & (Useq[t] <= u_max), 1.0, -1.0)
        A = np.minimum(1.0, np.maximum(0.0, A + g / T))                   # JS 와 같은 연산 순서
        out[t] = (A >= 0.5)
    return out

res = {'script': 'experiments/run_lenia_rule.py',
       'run_at': datetime.datetime.now().isoformat(timespec='seconds'),
       'rule': {'T': T_L, 'u_max_generation': U_MAX, 'tau_profile_bundle_order': TAU.tolist()},
       'seed_base': SEED_BASE, 'n_repeats': NREP, 'half_split': H}

# ── R0 — 정확한 특수 경우 ────────────────────────────────────────────
HEAD = (U >= TAU).astype(np.float32)                                   # build_percycle_overlap 과 같다
OM1 = lenia_om(U, TAU, 1, 1.0)
r0 = float((OM1 == HEAD).mean())
res['R0'] = {'agreement': r0, 'empty_rows_headline': int((HEAD.sum(1) == 0).sum())}
print(f'R0  T=1,u_max=1 vs 헤드라인 OM 일치율 = {r0*100:.4f}%   (빈 행 {res["R0"]["empty_rows_headline"]}/1088)')
assert r0 == 1.0, 'R0 실패 — 규칙 구현이 정본과 어긋났다. 나머지를 돌리지 않는다.'

# ── 하네스 검증 — 헤드라인 all_js 비트 재현 ──────────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    js_suite = [t['js_divergence'] for t in suite.run_algo1_trials(
        data, HEAD, CL, n_repeats=NREP, seed_base=SEED_BASE, min_onset_gap=0)]
d_head = float(np.max(np.abs(np.array(js_suite) - np.array(r025['all_js']))))
res['harness'] = {'max_abs_diff_vs_recorded_all_js': d_head, 'recorded_mean': r025['js_mean'],
                  'reproduced_mean': float(np.mean(js_suite))}
print(f'하네스  헤드라인 all_js 20개 재현: 최대 차 {d_head:.2e}  (평균 {np.mean(js_suite):.6f} vs 기록 {r025["js_mean"]:.6f})')

# ── R1 — 정본 ① 이진 scale OM 과의 일치율 ─────────────────────────────
OM25 = lenia_om(U, TAU, T_L, 1.0)
OM25u = lenia_om(U, TAU, T_L, U_MAX)
def agree(X, rows): return float((X[rows] == B[rows]).mean())
second = slice(H, None)
res['R1'] = {name: {'agree_second_half': agree(X, second), 'agree_first_half': agree(X, slice(0, H)),
                    'active_per_row': float(X.sum(1).mean()), 'empty_rows': int((X.sum(1) == 0).sum()),
                    'on_fraction_max': float(X.mean(0).max())}
             for name, X in [('T1_headline', OM1), (f'T{T_L}', OM25), (f'T{T_L}_umax{U_MAX}', OM25u)]}
res['R1']['binary_scale_om'] = {'active_per_row': float(B.sum(1).mean()), 'empty_rows': int((B.sum(1) == 0).sum()),
                                'on_fraction_max': float(B.mean(0).max())}
for k, v in res['R1'].items():
    if 'agree_second_half' in v:
        print(f'R1  {k:22s} 후반부 일치율 {v["agree_second_half"]*100:5.1f}%  (전반부 {v["agree_first_half"]*100:5.1f}%) '
              f'행당 {v["active_per_row"]:.2f} 빈행 {v["empty_rows"]:4d} 켜진시간최대 {v["on_fraction_max"]:.3f}')

# ── R2 · R3 — 생성 (N=20, 같은 시드) ────────────────────────────────
orig = [data['inst1_real'], data['inst2_real']]
orig_flat = [n for inst in orig for n in inst]
def wjs(gen, W=32):                       # 모듈 단위로 시간을 맞춘 음높이 JS — "언제" 를 본다
    vals = []
    for w in range(0, 1088, W):
        g = [n for n in gen if w <= n[0] < w + W]; o = [n for n in orig_flat if w <= n[0] < w + W]
        if g and o: vals.append(pitch_distribution_similarity(g, o)['js_divergence'])
    return float(np.mean(vals)), len(vals)
def generate(OM, i):
    suite.set_all_seeds(SEED_BASE + i)
    pool = suite.NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    mgr = suite.CycleSetManager(CL)
    return suite.algorithm1_optimized(pool, suite.INST_CHORD_HEIGHTS, OM, mgr,
                                      max_resample=50, verbose=False, min_onset_gap=0)
arms = {'T1_headline': OM1, f'T{T_L}': OM25}
M = {a: {'js': [], 'wjs': [], 'dtw': [], 'n_notes': []} for a in arms}
for a, OM in arms.items():
    for i in range(NREP):
        with contextlib.redirect_stdout(io.StringIO()):
            gen = generate(OM, i)
            js = suite.evaluate_generation(gen, orig, data['notes_label'], name='')['js_divergence']
        M[a]['js'].append(float(js)); M[a]['wjs'].append(wjs(gen)[0])
        M[a]['dtw'].append(float(dtw_pitch_distance(gen, orig_flat))); M[a]['n_notes'].append(len(gen))
    print(f'    생성 {a:12s} 완료 (N={NREP})')
d_loop = float(np.max(np.abs(np.array(M['T1_headline']['js']) - np.array(js_suite))))
res['harness']['own_loop_vs_suite_max_abs_diff'] = d_loop
print(f'하네스  이 스크립트의 생성 루프 == suite.run_algo1_trials : 최대 차 {d_loop:.2e}')

def paired(a, b):
    a, b = np.array(a), np.array(b); t = ttest_rel(b, a)
    return {'mean_T1': float(a.mean()), 'sd_T1': float(a.std(ddof=1)), f'mean_T{T_L}': float(b.mean()),
            f'sd_T{T_L}': float(b.std(ddof=1)), 'delta_pct': float((b.mean() - a.mean()) / a.mean() * 100),
            'paired_t': float(t.statistic), 'p': float(t.pvalue),
            'dz': float((b - a).mean() / (b - a).std(ddof=1)) if (b - a).std(ddof=1) > 0 else 0.0}
res['R2_pitch_js'] = paired(M['T1_headline']['js'], M[f'T{T_L}']['js'])
res['R3_windowed_js_32'] = paired(M['T1_headline']['wjs'], M[f'T{T_L}']['wjs'])
res['R3_dtw_registered'] = paired(M['T1_headline']['dtw'], M[f'T{T_L}']['dtw'])
res['n_notes'] = paired(M['T1_headline']['n_notes'], M[f'T{T_L}']['n_notes'])
res['raw'] = M
for k in ('R2_pitch_js', 'R3_windowed_js_32', 'R3_dtw_registered', 'n_notes'):
    v = res[k]
    print(f'{k:20s} T=1 {v["mean_T1"]:.5f}±{v["sd_T1"]:.5f} → T={T_L} {v[f"mean_T{T_L}"]:.5f}±{v[f"sd_T{T_L}"]:.5f}  '
          f'{v["delta_pct"]:+6.1f}%  p={v["p"]:.2e}  dz={v["dz"]:+.2f}')

json.dump(res, open('docs/step3_data/lenia_rule_results.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

# ── JS 포트 대조용 고정 입력 — om_bank(=hibari.json) 순서, U 는 6자리로 반올림 ─────
ob = json.load(open('mobile_tonnetz/data/om_bank.json', encoding='utf8'))['banks'][2]['cycles']
cyc = [sorted(set(CL[k])) for k in keys]
order = [cyc.index(sorted(set(c))) for c in ob]
Ur = np.round(U[:, order], 6); Tr = TAU[order]
fx = {'note': 'Lenia 규칙 JS 포트 대조. U 는 6자리 반올림, 기대값은 반올림된 U 로 파이썬이 계산했다.',
      'tau': Tr.tolist(), 'U': Ur.round(6).tolist(),
      'cases': [{'T': T, 'u_max': u, 'om_bits': ''.join('1' if x else '0' for x in lenia_om(Ur, Tr, T, u).ravel())}
                for T, u in [(1, 1.0), (T_L, 1.0), (T_L, U_MAX)]]}
os.makedirs('tools/verify', exist_ok=True)
json.dump(fx, open('tools/verify/lenia_fixture.json', 'w', encoding='utf8'), separators=(',', ':'))
print('저장: docs/step3_data/lenia_rule_results.json · tools/verify/lenia_fixture.json')
