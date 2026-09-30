"""
song_fold.py — 곡의 시간줄을 **닮은 대목끼리 닿게 접어** 3차원 몸 하나로 만든다.

무엇을 하나 (2026-09-30, 사용자 요청: "곡들의 본질을 포착해서 단일한 3차원 모양으로")
  곡 = 시간 순서의 한 줄(사슬). 두 시각의 **맥락**(그 앞뒤 4박에 울리는 음들)이 닮았으면 그 두 시각을 가까이 놓는다.
  되풀이가 많은 곡은 작게 말리고, 나아가기만 하는 곡은 길게 풀린다. 단백질이 아미노산 사슬을 접촉으로 접는 것과 같은 꼴이다
  (자기유사성 행렬 = 접촉 지도). 미분방정식이 아니라 스프링 풀기다.

모형 (길이 단위: 8분음표 = 1)
  노드   시각 하나(0.5박마다). 맥락 벡터 = 가운데가 무거운 4박 창 × [음높이 128 ⊕ 음이름 12], 시간으로 1 tatum 번짐, 곡 평균을 뺌, 정규화.
  사슬   (t, t+1) 쉬는 길이 = 노드 간격, 뻣뻣함 2.   굽힘 (t, t+2) 1.94×간격, 0.3.
  닮음   노드마다 가장 닮은 K=16 (창이 겹치는 이웃 제외), 닮음 ≥ 0.5 만. **목표 거리 = ρ·(1 − 닮음)**, ρ = 6.6.
  밀기   묶이지 않은 쌍이 2.0 안에 들면 민다(가닥 사이 틈).  약한 중력 + 부드러운 벽(꼬리가 몸을 감는다).
  풀기   스펙트럴 초기화(되풀이 + 사슬 그래프의 라플라시안) → 노드별 뻣뻣함으로 나눈 경사 하강.

⚠ 탐색적이다. 매개변수(ρ·문턱·밀기 반지름·번짐)는 13곡의 미리보기를 **눈으로 보고** 골랐다.
  견고성(시드·매개변수·시간 섞기 대조군)은 experiments/run_song_shape_checks.py 가 따로 잰다.
⚠ 정본 파이프라인(거리 함수·PH)과는 다른 대상이다 — 여기의 점은 **음이 아니라 시각**이고, 고리는 "되돌아옴" 이다.
"""
import os, warnings, colorsys
import numpy as np
warnings.filterwarnings('ignore')
import pretty_midi
from numba import njit, prange
from scipy.sparse import coo_matrix, identity
from scipy.sparse.linalg import eigsh
from scipy.ndimage import gaussian_filter1d

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS = [  # slug, MIDI, 제목, 작곡가
    ('hibari',  'Ryuichi_Sakamoto_-_hibari.mid',                                 'hibari',                          '사카모토 류이치'),
    ('aqua',    'aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid',                    'aqua',                            '사카모토 류이치'),
    ('solari',  'ryuichi-sakamoto-solari.mid',                                   'solari',                          '사카모토 류이치'),
    ('mcml',    'merry-christmas-mr-lawrence.mid',                               'Merry Christmas Mr. Lawrence',    '사카모토 류이치'),
    ('energy',  'energy-flow-ryuichi-sakamoto.mid',                              'energy flow',                     '사카모토 류이치'),
    ('bibo',    'bibo-no-aozora-solo-piano.mid',                                 'bibo no aozora',                  '사카모토 류이치'),
    ('flower',  'a-flower-is-not-a-flower-ryuichi-sakamoto.mid',                 'A Flower Is Not a Flower',        '사카모토 류이치'),
    ('emperor', 'the-last-emperor-theme-the-last-emperor-ryuichi-sakamoto.mid',  'The Last Emperor',                '사카모토 류이치'),
    ('tongpoo', 'tong-poo-solo-ver.mid',                                         'Tong Poo',                        '사카모토 류이치'),
    ('reich',   'steve-reich-piano-phase.mid',                                   'Piano Phase',                     '스티브 라이히'),
    ('bach',    'bach-toccata-and-fugue-in-d-minor-piano-solo.mid',              'Toccata and Fugue in D minor',    '바흐'),
    ('debussy', 'clair-de-lune-debussy.mid',                                     'Clair de Lune',                   '드뷔시'),
    ('ravel',   'maurice-ravel-pavane-pour-une-infante-defunte-m-19.mid',        'Pavane pour une infante défunte', '라벨'),
]
DEF = dict(Lbeats=4.0, blur=1.0, chroma_w=0.5, merged=True, k=16, thr=0.5, rho=6.6, bend=0.3, chain=2.0,
           rep_r=2.0, rep_k=0.5, grav=0.004, wall=1.15, iters=3000, tol=6e-4)


# ── 곡 읽기 ────────────────────────────────────────────────────────────────
def load(slug):
    """MIDI → 성부별 음표 배열 (박, 길이(박), 음높이, 초, 길이(초), 세기). 박 = 틱/해상도 — 템포 변화(루바토)와 무관한 악보 시간."""
    rec = next(s for s in SONGS if s[0] == slug)
    m = pretty_midi.PrettyMIDI(os.path.join(ROOT, rec[1])); res = m.resolution
    voices = []
    for inst in m.instruments:
        if inst.is_drum or not inst.notes: continue
        voices.append(np.array(sorted((m.time_to_tick(n.start) / res, (m.time_to_tick(n.end) - m.time_to_tick(n.start)) / res,
                                       n.pitch, n.start, n.end - n.start, n.velocity) for n in inst.notes), float))
    beats = max(v[:, 0].max() for v in voices)
    return {'slug': slug, 'title': rec[2], 'composer': rec[3], 'voices': voices, 'beats': float(beats), 'seconds': float(m.get_end_time()),
            'sec_at': lambda b: float(m.tick_to_time(int(round(b * res))))}


def tatum(song):
    """가장 흔한 onset 간격(박). 1/12 박 격자에 맞춘 뒤 최빈값 — 8분음표 곡은 0.5, 16분음표 곡은 0.25."""
    on = np.unique(np.round(np.concatenate([v[:, 0] for v in song['voices']]) * 12)) / 12
    ioi = np.round(np.diff(on) * 12).astype(int); ioi = ioi[ioi > 0]
    vals, cnt = np.unique(ioi, return_counts=True)
    return float(vals[np.argmax(cnt)] / 12)


def roll(song, tt):
    """(T, 성부, 128) onset 롤. 시각 = round(박 / tatum)."""
    T = int(np.ceil(song['beats'] / tt)) + 1
    R = np.zeros((T, len(song['voices']), 128), np.float32)
    for vi, v in enumerate(song['voices']):
        for b, d, p, *_ in v: R[min(T - 1, int(round(b / tt))), vi, int(p)] += 1
    return R


def context(R, L, blur=1.0, chroma_w=0.5):
    """맥락 벡터 (T, D). 시간으로 blur(tatum) 만큼 번지게 하고, 가운데가 무거운 길이 L(tatum) 창으로 자르고, 곡 평균을 빼고, 정규화한다.
    두 덩어리: 음높이(128·성부 수) 와 음이름(12·성부 수). 닮음 = (1−chroma_w)·음높이 닮음 + chroma_w·음이름 닮음."""
    T = R.shape[0]; X = R.reshape(T, -1)
    if blur > 0:
        r = int(np.ceil(3 * blur)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / blur) ** 2); k /= k.sum()
        X = np.apply_along_axis(lambda c: np.convolve(c, k, mode='same'), 0, X)
    C = X.reshape(T, -1, 128)
    chroma = np.stack([C[:, :, pc::12].sum(2) for pc in range(12)], 2).reshape(T, -1)
    h = int(L) // 2; taper = np.hanning(2 * h + 3)[1:-1]

    def win(M):
        P = np.pad(M, ((h, h), (0, 0)))
        W = np.stack([P[i:i + T] * taper[i] for i in range(2 * h + 1)], 1).reshape(T, -1)
        W = W - W.mean(0, keepdims=True)
        n = np.linalg.norm(W, axis=1, keepdims=True); n[n == 0] = 1
        return W / n
    return np.concatenate([np.sqrt(1 - chroma_w) * win(X), np.sqrt(chroma_w) * win(chroma)], 1).astype(np.float32)


def features(song, Lbeats=4.0, blur=1.0, chroma_w=0.5, merged=True, shuffle=None, **_):
    """곡 → (맥락 W, 노드 하나의 tatum 수 ns, 노드 간격 unit(8분음표 = 1), tatum, 창이 겹치는 노드 수 ban).
    merged: 성부를 합쳐 "들리는 대로" (False 면 누가 쳤는지 가린다).  shuffle: 대조군 — 시각을 뒤섞는다(음 재료는 같고 순서만 깨진다)."""
    tt = tatum(song); R = roll(song, tt)
    if shuffle is not None: R = R[np.random.default_rng(shuffle).permutation(len(R))]
    if merged: R = R.sum(1, keepdims=True)
    L = int(round(Lbeats / tt)); W = context(R, L, blur=blur, chroma_w=chroma_w)
    ns = max(1, int(round(0.5 / tt)))                       # 노드 = 0.5박 (tatum 이 1박인 곡은 1박)
    return W[::ns], ns, ns * tt * 2.0, tt, max(2, int(np.ceil(L / ns)))


def knn(W, k, thr, ban):
    """노드마다 가장 닮은 k 개 (|i−j| ≤ ban 제외, 닮음 ≥ thr). → 쌍 (n,2), 닮음 (n,), 노드별 최고 닮음 (T,)"""
    T = len(W); P = {}; best = np.zeros(T)
    for a in range(0, T, 512):
        S = W[a:a + 512] @ W.T
        for ii in range(S.shape[0]):
            i = a + ii; s = S[ii]; s[max(0, i - ban):i + ban + 1] = -1
            best[i] = s.max()
            for j in np.argpartition(-s, min(k, T - 1))[:k]:
                if s[j] >= thr:
                    key = (min(i, int(j)), max(i, int(j))); P[key] = max(P.get(key, 0.0), float(s[j]))
    return np.array(list(P.keys()), np.int64).reshape(-1, 2), np.array(list(P.values())), best


# ── 풀기 ───────────────────────────────────────────────────────────────────
@njit(parallel=True, fastmath=True, cache=True)
def _step(X, ei, ej, rest, stiff, nb, rep_r, rep_k, grav, lr, maxmove, pre, Rw):
    T = X.shape[0]; F = np.zeros((T, 3))
    for i in prange(T):
        rr = np.sqrt(X[i, 0] ** 2 + X[i, 1] ** 2 + X[i, 2] ** 2) + 1e-9
        gw = grav + (0.15 * (rr - Rw) / rr if rr > Rw else 0.0)
        fx = -gw * X[i, 0]; fy = -gw * X[i, 1]; fz = -gw * X[i, 2]
        for j in range(T):
            if i == j: continue
            dx = X[i, 0] - X[j, 0]; dy = X[i, 1] - X[j, 1]; dz = X[i, 2] - X[j, 2]
            r2 = dx * dx + dy * dy + dz * dz
            if r2 < rep_r * rep_r:
                skip = False
                for q in range(nb.shape[1]):
                    if nb[i, q] == j: skip = True; break
                    if nb[i, q] < 0: break
                if skip: continue
                r = np.sqrt(r2) + 1e-6; f = rep_k * (1.0 - r / rep_r)
                fx += f * dx / r; fy += f * dy / r; fz += f * dz / r
        F[i, 0] = fx; F[i, 1] = fy; F[i, 2] = fz
    for e in range(ei.shape[0]):
        i = ei[e]; j = ej[e]
        dx = X[j, 0] - X[i, 0]; dy = X[j, 1] - X[i, 1]; dz = X[j, 2] - X[i, 2]
        r = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-9
        f = stiff[e] * (r - rest[e])
        F[i, 0] += f * dx / r; F[i, 1] += f * dy / r; F[i, 2] += f * dz / r
        F[j, 0] -= f * dx / r; F[j, 1] -= f * dy / r; F[j, 2] -= f * dz / r
    mv = 0.0
    for i in range(T):
        li = lr / pre[i]
        m = np.sqrt(F[i, 0] ** 2 + F[i, 1] ** 2 + F[i, 2] ** 2) * li
        s = li if m <= maxmove else li * maxmove / m
        X[i, 0] += s * F[i, 0]; X[i, 1] += s * F[i, 1]; X[i, 2] += s * F[i, 2]
        mv += min(m, maxmove)
    return mv / T


def fold(W, unit, ban, seed=0, **kw):
    """맥락 W (T, D) → 접힌 자리 X (T, 3) 와 정보. seed > 0 이면 초기 자리에 잡음을 얹는다(견고성 검사용)."""
    p = dict(DEF); p.update(kw); T = len(W)
    rec, rsim, best = knn(W, p['k'], p['thr'], ban)
    E = [(np.arange(T - 1), np.arange(1, T), np.full(T - 1, unit), np.full(T - 1, p['chain']))]
    if p['bend'] > 0: E.append((np.arange(T - 2), np.arange(2, T), np.full(T - 2, 1.94 * unit), np.full(T - 2, p['bend'])))
    g = (rsim - p['thr']) / (1 - p['thr'])
    E.append((rec[:, 0], rec[:, 1], p['rho'] * (1 - rsim), 0.15 + 0.85 * g * g))
    ei = np.concatenate([e[0] for e in E]).astype(np.int64); ej = np.concatenate([e[1] for e in E]).astype(np.int64)
    rest = np.concatenate([e[2] for e in E]).astype(np.float64); stiff = np.concatenate([e[3] for e in E]).astype(np.float64)
    nbl = [set() for _ in range(T)]
    for i, j in zip(ei, ej): nbl[i].add(int(j)); nbl[j].add(int(i))
    nb = np.full((T, max(len(x) for x in nbl)), -1, np.int64)
    for i, x in enumerate(nbl): nb[i, :len(x)] = sorted(x)
    # 스펙트럴 초기화
    A = coo_matrix((np.concatenate([np.ones(T - 1), rsim]), (np.concatenate([np.arange(T - 1), rec[:, 0]]), np.concatenate([np.arange(1, T), rec[:, 1]]))), shape=(T, T)).tocsr()
    A = A + A.T; deg = np.asarray(A.sum(1)).ravel(); Dm = 1 / np.sqrt(deg)
    Ln = identity(T) - A.multiply(Dm[:, None]).multiply(Dm[None, :])
    w, v = eigsh(Ln.tocsc(), k=4, sigma=-1e-2, which='LM', v0=np.ones(T) / np.sqrt(T))
    X = v[:, np.argsort(w)[1:4]] * Dm[:, None]; X = (X - X.mean(0)) / (X.std(0) + 1e-12)
    X *= np.sign(X[np.argmax(np.abs(X), axis=0), np.arange(3)])
    X = np.ascontiguousarray(X * (T * unit) ** (1 / 3) * 1.2)
    if seed: X += np.random.default_rng(seed).normal(scale=0.5, size=X.shape)
    pre = np.ones(T); np.add.at(pre, ei, stiff); np.add.at(pre, ej, stiff)
    Rw = p['wall'] * (0.239 * T * unit * p['rep_r'] ** 2) ** (1 / 3)
    it = 0; mv = 1.0; ramp = 400
    while it < p['iters']:
        a = min(1.0, it / ramp)                              # 중력·밀기는 천천히 켠다
        mv = _step(X, ei, ej, rest, stiff, nb, p['rep_r'], p['rep_k'] * (0.2 + 0.8 * a), p['grav'] * a, 0.6,
                   0.3 * max(0.25, 1 - it / 1500), pre, Rw if it > 200 else 1e9)
        it += 1
        if it > ramp + 200 and mv < p['tol']: break
    X -= X.mean(0)
    # 주축 정렬: 가장 긴 쪽이 x, 그다음 y. 부호는 세제곱 평균(비대칭)으로 고정.
    ev, evec = np.linalg.eigh(np.cov(X.T)); X = X @ evec[:, ::-1]
    sg = np.sign((X ** 3).mean(0)); sg[sg == 0] = 1; X = X * sg
    d = np.linalg.norm(X[1:] - X[:-1], axis=1)
    info = {'T': int(T), 'unit': float(unit), 'n_bond': int(len(rec)), 'iters': int(it), 'move': float(mv),
            'rec80': float((best >= 0.8).mean()), 'rec95': float((best >= 0.95).mean()),
            'radius': float(np.sqrt((X ** 2).sum(1).mean())), 'extent': float(np.abs(X).max()),
            'chain_stretch_p95': float(np.percentile(d / unit, 95)), 'Rw': float(Rw)}
    return X, info, (rec, rsim, best)


# ── 색 ────────────────────────────────────────────────────────────────────
def colors(song, ns, T, tt, win_beats=4.0):
    """노드마다 색 (T, 3) 0..1. 색상 = 그 대목 음이름들의 5도권 위 무게중심 방향(레 쪽이 금빛), 채도 = 조성이 또렷한 정도, 밝기 = 음역(높을수록 밝다)."""
    R = roll(song, tt).sum(1)
    ch = np.stack([R[:, pc::12].sum(1) for pc in range(12)], 1)
    ch = gaussian_filter1d(ch, win_beats / tt / 2, axis=0, mode='nearest')
    pitch = (R * np.arange(128)).sum(1); cnt = R.sum(1)
    reg = gaussian_filter1d(pitch, win_beats / tt / 2, mode='nearest') / np.maximum(gaussian_filter1d(cnt, win_beats / tt / 2, mode='nearest'), 1e-6)
    ang = 2 * np.pi * (np.arange(12) * 7 % 12) / 12                     # 음이름 → 5도권 각
    z = (ch * np.exp(1j * ang)).sum(1) / np.maximum(ch.sum(1), 1e-6)
    hue = (np.angle(z) / (2 * np.pi) - 2 / 12 + 48 / 360) % 1           # 레(5도권 2번째) 방향 = 48° 금빛
    out = np.zeros((T, 3))
    for i in range(T):
        j = min(len(z) - 1, i * ns)
        out[i] = colorsys.hls_to_rgb(hue[j], float(np.clip(0.40 + (reg[j] - 48) / 36 * 0.22, 0.36, 0.66)), float(np.clip(0.30 + 0.75 * abs(z[j]), 0.30, 0.85)))
    return out


def run(slug, seed=0, shuffle=None, **kw):
    """곡 하나를 접는다 → (song, X, info, 부가). 부가 = (쌍, 닮음, 최고 닮음, ns, tt)"""
    song = load(slug); p = dict(DEF); p.update(kw)
    W, ns, unit, tt, ban = features(song, shuffle=shuffle, **p)
    X, info, (rec, rsim, best) = fold(W, unit, ban, seed=seed, **kw)
    info.update({'slug': slug, 'tatum': tt, 'node_tatums': ns, 'beats': song['beats'], 'seconds': song['seconds']})
    return song, X, info, (rec, rsim, best, ns, tt)
