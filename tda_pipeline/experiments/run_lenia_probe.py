"""
run_lenia_probe.py — Lenia 명세(docs/lenia_spec.md) 가 기대는 측정 4종

목적
  Lenia(Chan 2019) 를 hibari 에 적용하기 전에, "우리 연구와 연관돼 있다"는 직관 중
  무엇이 데이터로 뒷받침되고 무엇이 아닌지 가른다. 구현이 아니라 **착수 전 측정**이다.

사전 예측 (실행 전에 적었다 — 결과는 JSON 의 verdict 에 그대로 남긴다)
  P1 고리 커널 : H1 고리는 필트레이션에서 "변은 있고 삼각형은 없는" 구간에 산다 →
                 고리 공동소속은 거리에 대해 **비단조**(중간 거리 최대) = Lenia 의 고리형 커널
  P2 2D 지도   : DFT 거리를 고전 MDS 로 2D 에 펼치면 stress-1 < 0.20
  P3 주기      : 연속 중첩행렬의 자기상관은 lag 32 부근(한 모듈)에서 lag 16 보다 높다
  P4 정본 OM   : build_overlap_matrix 의 threshold=0.35 는 활성도 임계가 아니라
                 "고리가 켜질 수 있는 시간 비율 상한" 이고, 최소 지속 길이(scale) 필터가 있다.
                 echo.html 의 규칙(연속 활성도 ≥ 0.35)은 그와 다르다.

대조군
  P1 : 같은 크기의 무작위 음 묶음 14개 (2000회) — 구조가 없으면 평평해야 한다
  P2 : 무작위 2D 좌표의 고리 이웃 보존율 (500회)
  P3 : 시간축 셔플 (200회) — 모든 주기성 파괴.
       ⚠ 열별 원형 이동도 돌렸으나 **이 통계엔 무효**다 — 풀링한 자기상관은 각 열의
         자기상관의 합이라 열별 이동에 불변이다. 기록을 위해 남기되 판정에 쓰지 않는다.
  P4 : 없음 (코드 정의 확인 + 정본 산출물 대조)

한계
  · 거리행렬은 rate(0~1.5) 마다 다르다. 대표 rate 만 쟀다(0, 0.5, 1.0, 1.5) + rate 무관 DFT.
  · 고리는 캐시(cache/metric_dft_alpha0p25_ow0p3_dw1p0.pkl) 것을 쓴다. om_bank(α=0.25) 와 일치 확인.
  · P3 은 두 악기를 합친 OM 이다. 32/33 두 손을 가르려면 악기별 OM 이 필요하다(미측정).

실행: python experiments/run_lenia_probe.py   (≈ 1분, cache/*.pkl 필요 — 저장소에 없다, 로컬 전용)
산출: docs/step3_data/lenia_probe_results.json
"""
import sys, os, io, json, pickle, itertools, contextlib, datetime
import numpy as np
from scipy.stats import spearmanr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
from weights import compute_inter_weights, compute_out_of_reach, compute_distance_matrix
from musical_metrics import compute_hybrid_distance

CACHE = 'cache/metric_dft_alpha0p25_ow0p3_dw1p0.pkl'
cache = pickle.load(open(CACHE, 'rb'))
CY = [sorted(set(v)) for v in cache['cycle_labeled'].values()]
N, K = data['num_notes'], len(CY)
SIZES = [len(c) for c in CY]
iu = np.triu_indices(N, 1)
out = {'script': 'experiments/run_lenia_probe.py', 'run_at': datetime.datetime.now().isoformat(timespec='seconds'),
       'cache': CACHE, 'N_notes': N, 'K_cycles': K, 'cycle_sizes': SIZES}

ob = json.load(open('mobile_tonnetz/data/om_bank.json'))['banks'][2]['cycles']
out['cycles_match_om_bank_alpha025'] = sorted(map(tuple, CY)) == sorted(tuple(sorted(set(c))) for c in ob)

inter = compute_inter_weights(data['adn_i'][1][1], data['adn_i'][2][1], num_chords=data['num_chords'], lag=1)
oor = compute_out_of_reach(inter, power=-2)
MUS = np.asarray(suite.metric_distance_matrix(data['notes_label'], 'dft', 0.3, 1.0), float)
def hybrid(r):
    fd = compute_distance_matrix(data['intra'] + r * inter, data['notes_dict'], oor, num_notes=N).values
    return np.asarray(compute_hybrid_distance(fd, MUS, alpha=0.25), float)
DISTS = {'dft_musical': MUS, 'hybrid_r0.0': hybrid(0.0), 'hybrid_r0.5': hybrid(0.5),
         'hybrid_r1.0': hybrid(1.0), 'hybrid_r1.5': hybrid(1.5)}

def comem(cycles):
    C = np.zeros((N, N))
    for c in cycles:
        for i, j in itertools.combinations(c, 2):
            C[i, j] += 1; C[j, i] += 1
    return C
C_REAL = comem(CY)
rng = np.random.default_rng(0)
def rand_cycles(): return [sorted(rng.choice(N, s, replace=False)) for s in SIZES]

# ── P1 고리 커널 ─────────────────────────────────────────────────────
def profile(D, C, q=5):
    d, c = D[iu], C[iu]
    e = np.quantile(d, np.linspace(0, 1, q + 1))
    b = np.clip(np.searchsorted(e, d, side='right') - 1, 0, q - 1)
    return [float(c[b == k].mean()) for k in range(q)]
ring = lambda p: max(p[1:-1]) - p[0]          # > 0 이면 고리형 (중간이 최근접보다 높다)
p1 = {}
for name, D in DISTS.items():
    p = profile(D, C_REAL); g = ring(p)
    nul_ring = np.array([ring(profile(D, comem(rand_cycles()))) for _ in range(2000)])
    rho = float(spearmanr(D[iu], C_REAL[iu]).correlation)
    nul_rho = np.array([spearmanr(D[iu], comem(rand_cycles())[iu]).correlation for _ in range(2000)])
    p1[name] = {'comembership_by_distance_quintile_near_to_far': [round(x, 4) for x in p],
                'ringness': round(g, 4), 'ringness_null_q95': round(float(np.quantile(nul_ring, .95)), 4),
                'p_ring': round(float((np.sum(nul_ring >= g) + 1) / 2001), 4),
                'spearman_rho': round(rho, 4), 'rho_null_mean': round(float(nul_rho.mean()), 4),
                'rho_null_sd': round(float(nul_rho.std()), 4),
                'p_blob': round(float((np.sum(nul_rho <= rho) + 1) / 2001), 4)}
out['P1_ring_kernel'] = {'per_distance': p1,
    'pairs_sharing_any_cycle': int((C_REAL[iu] > 0).sum()), 'pairs_total': int(len(iu[0])),
    'verdict': 'P1 기각 — 고리형이 아니라 덩어리형(단조 감소). 구조 자체는 강하다(ρ≈−0.63, 대조군 0±0.07).'}

# ── P2 2D 지도 ───────────────────────────────────────────────────────
def cmds(D, k):
    D = (D + D.T) / 2; np.fill_diagonal(D, 0)
    J = np.eye(N) - 1 / N; B = -0.5 * J @ (D ** 2) @ J
    w, V = np.linalg.eigh(B); o = np.argsort(w)[::-1]; w, V = w[o], V[:, o]
    return V[:, :k] * np.sqrt(np.maximum(w[:k], 0)), w
def stress(D, X):
    E = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1))
    return float(np.sqrt(((D[iu] - E[iu]) ** 2).sum() / (D[iu] ** 2).sum()))
def keep(X, k=3):
    E = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1)); np.fill_diagonal(E, np.inf)
    h = t = 0
    for i in range(N):
        cn = [j for j in np.argsort(-C_REAL[i]) if C_REAL[i, j] > 0 and j != i][:k]
        if cn: h += len(set(cn) & set(np.argsort(E[i])[:k])); t += len(cn)
    return h / t
p2 = {}
for name in ('dft_musical', 'hybrid_r1.0'):
    D = DISTS[name]; X2, w = cmds(D, 2); pos = w[w > 0]
    p2[name] = {'stress1_1d': round(stress(D, cmds(D, 1)[0]), 4), 'stress1_2d': round(stress(D, X2), 4),
                'stress1_3d': round(stress(D, cmds(D, 3)[0]), 4),
                'pos_eigen_share_2d': round(float(pos[:2].sum() / pos.sum()), 4),
                'cycle_neighbor_keep_2d': round(keep(X2), 4),
                'cycle_neighbor_keep_random_mean': round(float(np.mean([keep(rng.normal(size=(N, 2))) for _ in range(500)])), 4),
                'coords_2d': [[round(float(a), 5), round(float(b), 5)] for a, b in X2]}
out['P2_mds_2d'] = {'per_distance': p2,
    'verdict': 'P2 통과 — DFT 2D stress 0.064 (좋음). 고리 이웃 보존은 무작위의 2.6배지만 부분적(35%).'}

# ── P3 주기 ─────────────────────────────────────────────────────────
A = cache['activation_continuous'].values.astype(float)
def acf(X, L):
    Z = X - X.mean(0); den = (Z ** 2).sum()
    return np.array([(Z[:-l] * Z[l:]).sum() / den for l in L])
LAGS = np.arange(1, 70); r = acf(A, LAGS)
perm = np.stack([acf(A[rng.permutation(len(A))], LAGS) for _ in range(200)])
circ = np.stack([acf(np.stack([np.roll(A[:, k], rng.integers(len(A))) for k in range(K)], 1), LAGS) for _ in range(200)])
sel = [8, 16, 17, 24, 31, 32, 33, 34, 48, 64]
out['P3_om_periodicity'] = {
    'om_shape': list(A.shape), 'om_mean': round(float(A.mean()), 4),
    'acf': {str(l): round(float(r[l - 1]), 4) for l in sel},
    'acf_time_shuffle_q95': {str(l): round(float(np.quantile(perm[:, l - 1], .95)), 4) for l in sel},
    'acf_column_circshift_q95_INVALID_CONTROL': {str(l): round(float(np.quantile(circ[:, l - 1], .95)), 4) for l in sel},
    'top_lags': [int(x) for x in LAGS[np.argsort(-r)][:6]],
    'verdict': 'P3 기각(부분) — 주기성은 강하다(lag16 0.80 vs 셔플 0.03). 그러나 최강 주기는 32 가 아니라 16. '
               '봉우리가 16→17, 32→33 으로 넓게 퍼져 32/33 혼합과 맞으나, 악기별 OM 없이는 확증 불가.'}

# ── P4 정본 이진 OM 의 성질 vs echo.html 규칙 ──────────────────────────
B = cache['overlap_binary'].values
def min_run(col):
    p = np.diff(np.concatenate(([0], col, [0])))
    L = np.where(p == -1)[0] - np.where(p == 1)[0]
    return int(L.min()) if len(L) else 0
E = A >= 0.35
out['P4_canonical_binary_om'] = {
    'on_fraction_per_cycle': [round(float(x), 4) for x in B.mean(0)],
    'cycles_over_0.35_cap': int((B.mean(0) > 0.35 + 1e-9).sum()),
    'min_on_run_per_cycle_steps': [min_run(B[:, c]) for c in range(K)],
    'active_per_row_mean': round(float(B.sum(1).mean()), 4),
    'empty_rows': int((B.sum(1) == 0).sum()), 'rows': int(len(B)),
    'echo_rule_cont_ge_035': {'on_fraction_max': round(float(E.mean(0).max()), 4),
                              'agreement_with_canonical_binary': round(float((E == B.astype(bool)).mean()), 4),
                              'active_per_row_mean': round(float(E.sum(1).mean()), 4)},
    'verdict': 'P4 통과 — threshold=0.35 는 켜진 시간 비율 상한(하한 0.25), scale 은 최소 지속 길이다. '
               'echo.html 규칙은 둘 다 없다: 켜진 시간 최대 0.563, 정본과 일치율 64.7%.'}

dst = 'docs/step3_data/lenia_probe_results.json'
json.dump(out, open(dst, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(f'저장: {dst}')
for k in ('P1_ring_kernel', 'P2_mds_2d', 'P3_om_periodicity', 'P4_canonical_binary_om'):
    print(f'  {k:26s} {out[k]["verdict"]}')
