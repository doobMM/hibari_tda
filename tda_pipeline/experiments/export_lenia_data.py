"""
export_lenia_data.py — 단계 0: Lenia 상호작용 페이지용 정본 데이터 (docs/lenia_spec.md §4-0)

⛔ hibari_dashboard/data/ 의 고리·OM 을 쓰지 않는다 — use_decayed=True (정본 아님, CLAUDE.md T11).
   정본 = α=0.25, ow=0.3, dw=1.0, use_decayed=False, K=14. PH 를 여기서 다시 계산한다(캐시 불필요).

산출: tda_pipeline/lenia/hibari.json
  cycles     고리 14개, 0-indexed label_idx
  traversal  PH 원 변 목록에서 복원한 순회 순서 (호몰로지 대표 고리). 실패 시 null
  tau        헤드라인 JS=0.00902 의 고리별 τ_c (percycle_tau_dft_gap0_alpha_grid_results.json)
  rarity     1 / (그 음을 품은 고리 수)   — overlap.py:build_activation_matrix 와 같게
  rule       Lenia 규칙 상수 T · u_max 와 그 유도 (전반부 0~543 에서만 계산)
  layout     화면 좌표 23×2 + 후보 4종의 비교 지표 (아래 사전 기준으로 고른다)
  labels     label_idx · pitch · dur · count

검사 (실패하면 멈춘다)
  D1  고리 == mobile_tonnetz/data/om_bank.json banks[2] (α=0.25 정본) 고리
  D2  (연속 활성도 ≥ τ_c) 의 빈 행 == 0/1088  (CLAUDE.md 정본값)

화면 배치 — 사전 기준 (코드를 돌리기 전에 적었다)
  명세는 DFT-MDS 를 기본값으로 뒀으나 그 근거("위치 = 화성 거리")가 무너졌다:
  이 파이프라인의 DFT 항은 단일 음에서 항상 0 이라(musical_metrics._build_dft_cache),
  "DFT 음악거리" = 0.3·|옥타브 차| + |길이 차|/max 길이 이고 23개 음이 7개 점으로 겹친다.
  후보 4종을 같은 기준으로 비교해 고른다:
    L1 DFT 음악거리 MDS            (명세의 원래 기본값)
    L2 hybrid α=0.25 rate=1.0 MDS (PH 가 실제로 본 거리)
    L3 고리 공동소속 그래프 측지선 MDS
    L4 고리 변(순회 인접) 골격 그래프 측지선 MDS  (PH 가 찾은 1-골격 그 자체)
  각 거리를 두 방법으로 펼친다 — 고전 MDS / SMACOF(2D stress 직접 최소화). 8개 후보, 같은 기준.
  기준 (순서대로 비교, 앞이 같을 때만 다음으로):
    ① 겹친 쌍 수 (화면 폭의 2% 이내)       — 적을수록. 겹치면 탭이 모호하고 입자가 포개진다
    ② 고리 다각형의 자기 교차 수 (순회 순서) — 적을수록. 꼬이면 고리가 고리로 안 보인다
    ③ 고리 응집도 = 고리 내 평균 거리 / 전체 평균 거리 — 낮을수록
"""
import sys, os, io, json, contextlib, itertools, datetime
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments'), os.path.join(ROOT, 'hibari_dashboard', 'scripts')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
from add_cycle_traversal import parse_edges, traverse_cycle      # 순회 복원 로직 재사용

ALPHA, OW, DW = 0.25, 0.3, 1.0
N = data['num_notes']
out = {'source': f'α={ALPHA} ow={OW} dw={DW} use_decayed=False K=14 (정본). export_lenia_data.py',
       'generated_at': datetime.datetime.now().isoformat(timespec='seconds')}

# ── 번들 (정본 경로 그대로) ──────────────────────────────────────────
with contextlib.redirect_stdout(io.StringIO()):
    bundle = suite.build_overlap_bundle(data, 'dft', alpha=ALPHA, octave_weight=OW,
                                        duration_weight=DW, use_decayed=False, threshold=0.35)
labels_order = list(bundle['cycle_labeled'].keys())
CY = [sorted(set(bundle['cycle_labeled'][k])) for k in labels_order]
K = len(CY)
A = bundle['activation_continuous'][labels_order].values.astype(float)     # (1088, 14)
B = bundle['overlap_binary'][labels_order].values.astype(int)

ob = json.load(open('mobile_tonnetz/data/om_bank.json', encoding='utf8'))['banks'][2]['cycles']
D1 = sorted(map(tuple, CY)) == sorted(tuple(sorted(set(c))) for c in ob)
assert D1, 'D1 실패 — 고리가 om_bank(α=0.25 정본) 과 다르다. 설정을 확인하라.'
# om_bank 순서를 정본 순서로 쓴다 (echo.html·JS 쪽과 인덱스를 맞추기 위해)
order = [CY.index(sorted(set(c))) for c in ob]
CY = [CY[i] for i in order]; A = A[:, order]; B = B[:, order]

grid = json.load(open('docs/step3_data/percycle_tau_dft_gap0_alpha_grid_results.json', encoding='utf8'))
r025 = next(r for r in grid['results'] if abs(float(r['alpha']) - ALPHA) < 1e-9)
TAU_BUNDLE_ORDER = list(r025['tau_profile'])            # 번들(cycle_labeled) 순서
TAU = [TAU_BUNDLE_ORDER[i] for i in order]
D2 = int(((A >= np.array(TAU)).sum(1) == 0).sum())
assert D2 == 0, f'D2 실패 — 빈 행 {D2}/1088 (정본은 0). τ 순서나 설정이 어긋났다.'
out['checks'] = {'D1_cycles_match_om_bank': D1, 'D2_empty_rows_headline_om': D2,
                 'headline_js_mean_of_this_tau': r025['js_mean']}

cnt = {}
for c in CY:
    for v in c: cnt[v] = cnt.get(v, 0) + 1
RAR = {v: 1.0 / n for v, n in cnt.items()}
isolated = [i for i in range(N) if i not in cnt]

# ── 순회 순서: 정본 설정으로 모든 rate 의 바코드를 다시 모은다 ──────────
inter = suite.compute_inter_weights(data['adn_i'][1][1], data['adn_i'][2][1],
                                    num_chords=data['num_chords'], lag=1)
oor = suite.compute_out_of_reach(inter, power=-2)
MUS = np.asarray(suite.metric_distance_matrix(data['notes_label'], 'dft', OW, DW), float)
trav_by_vset, rate = {}, 0.0
while rate <= 1.5 + 1e-10:
    fd = suite.compute_distance_matrix(data['intra'] + round(rate, 2) * inter, data['notes_dict'],
                                       oor, num_notes=N).values
    bd = suite.generate_barcode_numpy(mat=suite.compute_hybrid_distance(fd, MUS, alpha=ALPHA),
                                      listOfDimension=[1], exactStep=True,
                                      birthDeathSimplex=False, sortDimension=False)
    for e in bd:
        if not isinstance(e, list) or len(e) < 3 or e[0] != 1: continue
        ed = parse_edges(str(e[2]).strip())
        vs = frozenset(v for x in ed for v in x)
        if ed and vs not in trav_by_vset:
            t = traverse_cycle(ed)
            if t is not None and set(t) == vs: trav_by_vset[vs] = t
    rate = round(rate + 0.01, 2)
TRAV = [trav_by_vset.get(frozenset(c)) for c in CY]
out['traversal_found'] = f'{sum(t is not None for t in TRAV)}/{K}'

# ── Lenia 규칙 상수 — 전반부(0~543)에서만 유도, 탐색 없음 ───────────────
H = 544
def runs(col):
    p = np.diff(np.concatenate(([0], col, [0])))
    return np.where(p == -1)[0] - np.where(p == 1)[0]
mins = [int(runs(B[:H, c]).min()) for c in range(K) if runs(B[:H, c]).size]
T_rule = int(round(2 * float(np.median(mins))))
pos = A[:H][A[:H] > 0]
u_max = round(float(np.quantile(pos, 0.95)), 3)
out['rule'] = {
    'T': T_rule, 'u_max_generation': u_max, 'u_max_original': 1.0, 'read_threshold': 0.5,
    'derivation': {
        'T': f'정본 이진 scale OM 의 고리별 최소 지속 길이(전반부 0~{H-1}) 중앙값 {float(np.median(mins))} × 2',
        'u_max_generation': f'원곡 양의 연속 활성도 95% 분위 (전반부 0~{H-1})',
        'exact_special_case': 'T=1, u_max=1 이면 OM = [U ≥ τ_c] = 헤드라인 OM (build_percycle_overlap 과 같이 >=)'}}

# ── 화면 배치 후보 4종 ─────────────────────────────────────────────
def cmds(D, k=2):
    D = (D + D.T) / 2; np.fill_diagonal(D, 0)
    J = np.eye(N) - 1 / N; Bm = -0.5 * J @ (D ** 2) @ J
    w, V = np.linalg.eigh(Bm); o = np.argsort(w)[::-1]
    return V[:, o[:k]] * np.sqrt(np.maximum(w[o[:k]], 0))
def geodesic(W):                         # W: 가중 인접 (0 = 간선 없음), Floyd–Warshall
    G = np.where(W > 0, W, np.inf); np.fill_diagonal(G, 0)
    for k in range(N): G = np.minimum(G, G[:, [k]] + G[[k], :])
    fin = G[np.isfinite(G)].max(); return np.where(np.isfinite(G), G, fin + 1)   # 고립 음은 가장자리
C = np.zeros((N, N))
for c in CY:
    for i, j in itertools.combinations(c, 2): C[i, j] += 1; C[j, i] += 1
S = np.zeros((N, N))
for t in TRAV:
    if t:
        for a, b in zip(t, t[1:] + t[:1]): S[a, b] = S[b, a] = 1
fd1 = suite.compute_distance_matrix(data['intra'] + 1.0 * inter, data['notes_dict'], oor, num_notes=N).values
DISTS = {'L1_dft': MUS,
         'L2_hybrid_r1': np.asarray(suite.compute_hybrid_distance(fd1, MUS, alpha=ALPHA), float),
         'L3_comembership_geodesic': geodesic(np.divide(1.0, C, out=np.zeros_like(C), where=C > 0)),
         'L4_cycle_skeleton_geodesic': geodesic(S)}

# 펼치는 방법 2종. 고전 MDS 는 이웃이 똑같은 음을 한 점으로 뭉갠다(첫 실행: L4 에서도 겹친 쌍 12).
# SMACOF 는 2D stress 를 직접 줄인다. ⚠ 시작점에서 이미 겹친 점은 Guttman 변환에서 서로 밀어내는 항이
# 0 이 되어 계속 붙어 있으므로, 시작점에만 화면 폭 0.1% 의 결정적 섭동(황금각 나선)을 준다.
from sklearn.manifold import smacof
def smacof2(D):
    D = (D + D.T) / 2; np.fill_diagonal(D, 0)
    X0 = cmds(D); span = max(np.ptp(X0, 0).max(), 1e-9)
    ang = np.arange(N) * np.pi * (3 - np.sqrt(5))
    X0 = X0 + 1e-3 * span * np.stack([np.cos(ang), np.sin(ang)], 1)
    X, st = smacof(D, n_components=2, init=X0, n_init=1, max_iter=5000, eps=1e-10, metric=True,
                   normalized_stress=False)
    return X
CAND = {}
for name, D in DISTS.items():
    CAND[name + '__cmds'] = cmds(D)
    CAND[name + '__smacof'] = smacof2(D)

def seg_cross(p1, p2, p3, p4):
    d = lambda a, b, c: (c[0]-a[0])*(b[1]-a[1]) - (c[1]-a[1])*(b[0]-a[0])
    d1, d2, d3, d4 = d(p3, p4, p1), d(p3, p4, p2), d(p1, p2, p3), d(p1, p2, p4)
    return (d1 * d2 < 0) and (d3 * d4 < 0)
def metrics(X):
    E = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1)); iu = np.triu_indices(N, 1); span = E[iu].max()
    stacked = int((E[iu] < 0.02 * span).sum())
    cross = 0
    for t in TRAV:
        if not t or len(t) < 4: continue
        P = [X[v] for v in t]; segs = list(zip(P, P[1:] + P[:1])); n = len(segs)
        for a in range(n):
            for b in range(a + 2, n):
                if a == 0 and b == n - 1: continue           # 이웃 변 제외
                cross += seg_cross(*segs[a], *segs[b])
    coh = float(np.mean([E[np.ix_(c, c)][np.triu_indices(len(c), 1)].mean() for c in CY]) / E[iu].mean())
    return {'stacked_pairs': stacked, 'self_crossings': int(cross), 'cohesion': round(coh, 4)}
LM = {k: metrics(X) for k, X in CAND.items()}
pick = min(LM, key=lambda k: (LM[k]['stacked_pairs'], LM[k]['self_crossings'], LM[k]['cohesion']))
X = CAND[pick].copy()
# 정규화는 **고리에 속한 음만으로** 잡는다. 고립 음은 측지선에서 모두에게 '가장 먼 거리' 를 받아
# SMACOF 가 멀리 밀어내고, 그걸 범위에 넣으면 본 지도가 한쪽 구석으로 쪼그라든다(첫 화면에서 확인).
conn = [i for i in range(N) if i not in isolated]
lo = X[conn].min(0); span = max(np.ptp(X[conn], 0).max(), 1e-9)
X = (X - lo) / span                                                             # 연결 음: 0~1, 비율 유지
X[conn] += (1 - np.ptp(X[conn], 0)) / 2                                         # 가운데 정렬
for k, i in enumerate(isolated):                                                # 고립 음 — 지도 바로 아래, 따로
    X[i] = [0.5 + (k - (len(isolated) - 1) / 2) * 0.08, 1.07]
out['layout'] = {'chosen': pick, 'criteria': '① 겹친 쌍 → ② 고리 자기교차 → ③ 응집도 (사전 기준)',
                 'candidates': LM, 'coords': [[round(float(a), 5), round(float(b), 5)] for a, b in X],
                 'note': '연결된 음만으로 0~1 정규화·가운데 정렬. 고립 음(어느 고리에도 없음)은 지도 아래 y=1.07 에 따로 둔다'}

meta = json.load(open('hibari_dashboard/data/notes_metadata.json', encoding='utf8'))
out.update({'K': K, 'N': N, 'cycles': CY, 'traversal': TRAV, 'tau': TAU,
            'rarity': {str(k): round(v, 6) for k, v in RAR.items()}, 'isolated_notes': isolated,
            'labels': [{k: e[k] for k in ('label_idx', 'pitch', 'dur', 'count')} for e in meta['labels']]})
os.makedirs('lenia', exist_ok=True)
json.dump(out, open('lenia/hibari.json', 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))

print(f"D1 고리 == om_bank     : {D1}")
print(f"D2 헤드라인 OM 빈 행    : {D2}/1088  (τ 의 js_mean {r025['js_mean']:.6f})")
print(f"순회 순서 복원          : {out['traversal_found']}")
print(f"고립 음 (고리 없음)      : {isolated}  → {[meta['labels'][i]['pitch'] for i in isolated]}")
print(f"규칙 T = {T_rule} (최소지속 중앙값 {float(np.median(mins))}×2) · u_max(생성) = {u_max}")
print(f"\n{'배치':30s} {'겹친쌍':>6s} {'자기교차':>8s} {'응집도':>7s}")
for k, m in LM.items():
    print(f"{k:40s} {m['stacked_pairs']:6d} {m['self_crossings']:8d} {m['cohesion']:7.3f}{'   ← 선택' if k == pick else ''}")
print(f"\n저장: lenia/hibari.json ({os.path.getsize('lenia/hibari.json')} bytes)")
