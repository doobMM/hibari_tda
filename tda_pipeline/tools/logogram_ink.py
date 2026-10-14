"""
tools/logogram_ink.py — 원형문자 × hibari 그림 셋을 다시 (2026-10-14 사용자: 첫 그림 셋이 "보기에 안 끌린다").
첫 판(tools/logogram_views.py)은 박마다 같은 촉수를 꽂아 톱니바퀴처럼 고르고, 맞히기는 색을 평평하게 칠했다.
영화의 원형문자는 안개 속에 번진 잉크 — 고리 자체가 출렁이고, 굵은 웅덩이와 튀는 획이 몇 군데에만 있다.

같은 hibari 자료를 덜 기계적으로 읽는다:
  고리의 출렁임 = 선율 높이(박마다의 윗음) · 굵기 = 울리는 음 수 · 웅덩이 = 길게 끄는 화음 · 튀는 획 = 선율의 꼭대기(81)
  곡 전체: 두 가닥(오른손·왼손)이 위상이 맞을 때(처음 = 끝, 반 모듈) 하나로 합쳐지고 1/4 모듈 어긋날 때 가장 벌어진다 · 튀는 획 = 두 손의 같은 음
  맞히기: 들려준 문장은 안개 속 그림자, 내가 쓴 획은 검은 잉크 — 맞은 박은 짙은 먹으로 스미고 틀린 박은 옅은 먹으로 남는다(색을 칠하지 않는다).
잉크 결: 방울을 찍은 밀도장 → 부드러운 잡음으로 비틀기(domain warp) → 결 · 번짐(안개) → 종이 위 먹색.
    python tools/logogram_ink.py  → docs/figures/logogram_ink.png
"""
import sys, os
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
import run_rings_h1_probe as P
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'

G, L = 820, 1.6
rng = np.random.default_rng(7)

def fbm(scales=((60, 1.0), (22, 0.5), (8, 0.25))):
    f = sum(a * gaussian_filter(rng.normal(size=(G, G)), s) * s for s, a in scales); return f / (np.abs(f).max() + 1e-9)

def stamp(D, x, y, s, w=1.0):
    i, j, r = (y + L) / (2 * L) * (G - 1), (x + L) / (2 * L) * (G - 1), max(s / (2 * L) * (G - 1), 0.7)
    R = int(3 * r) + 2; i0, i1, j0, j1 = max(0, int(i) - R), min(G, int(i) + R + 1), max(0, int(j) - R), min(G, int(j) + R + 1)
    if i0 >= i1 or j0 >= j1: return
    yy, xx = np.mgrid[i0:i1, j0:j1]; D[i0:i1, j0:j1] += w * np.exp(-((yy - i) ** 2 + (xx - j) ** 2) / (2 * r * r))

def ang(t, N, rot=0.0): return np.pi / 2 - 2 * np.pi * t / N + rot

def stroke(D, ts, rs, ws, N, w=0.6, rot=0.0):
    for t, r, s in zip(ts, rs, ws):
        a = ang(t, N, rot); stamp(D, r * np.cos(a), r * np.sin(a), s, w)

def flick(D, t, N, R, length, width, bend, rot=0.0, w=0.7, drops=3):
    """고리에서 튀어 나가는 획: 굽고 가늘어지며 끝에 방울."""
    a0 = ang(t, N, rot); last = None
    for s in np.linspace(0, 1, 70):
        a = a0 + bend * s ** 1.6; r = R + length * s
        x, y = r * np.cos(a), r * np.sin(a); stamp(D, x, y, width * (1 - s) ** 1.4 + 0.004, w); last = (x, y, a)
    for _ in range(drops):
        d = rng.uniform(0.04, 0.16); x, y, a = last; stamp(D, x + d * np.cos(a) + rng.normal(0, .03), y + d * np.sin(a) + rng.normal(0, .03), rng.uniform(.006, .016), 0.9)

def render(D, ghost=None, rust=None, seed_ink=(18, 20, 22)):
    """밀도장 → 비틀기 → 결 → 번짐 → RGB."""
    yy, xx = np.mgrid[0:G, 0:G].astype(float); k = 14.0
    wx, wy = fbm() * k, fbm() * k
    warp = lambda F: map_coordinates(F, [yy + wy, xx + wx], order=1, mode='nearest')
    Dw = warp(D); tex = fbm(((3, 1.0), (1.2, 0.6)))
    core = 1 / (1 + np.exp(-(Dw * (1 + 0.45 * tex) - 0.55) / 0.09))
    halo = gaussian_filter(Dw, 22); halo = halo / (halo.max() + 1e-9) * np.clip(0.55 + 0.6 * fbm(((30, 1.0), (10, 0.6))), 0, 1.2)
    r = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
    paper = np.stack([np.full((G, G), c) for c in (238, 236, 230)], -1) / 255 * (1 - 0.10 * r[..., None] ** 2)
    out = paper * (1 - 0.42 * np.clip(halo, 0, 1)[..., None]) + np.array([140, 148, 154]) / 255 * (0.42 * np.clip(halo, 0, 1)[..., None])
    if ghost is not None:                                                # 들려준 문장 = 안개 속 그림자
        Gw = warp(ghost); gh = gaussian_filter(Gw, 5); gh = np.clip(gh / (gh.max() + 1e-9) * 1.6, 0, 1) * (0.8 + 0.2 * fbm())
        out = out * (1 - 0.40 * gh[..., None]) + np.array([118, 126, 132]) / 255 * (0.40 * gh[..., None])
    ink = np.array(seed_ink) / 255
    out = out * (1 - core[..., None]) + ink * core[..., None]
    if rust is not None:
        Rw = np.clip(warp(rust), 0, 1); m = core * Rw
        out = out * (1 - 0.62 * m[..., None]) + np.array([128, 134, 138]) / 255 * (0.62 * m[..., None])   # 틀린 박 = 아직 스미지 않은 옅은 먹
    return np.clip(out, 0, 1)

O1, O2 = P.piece(P.IDENT)

def module_field(notes, N=32, upto=None, rot=0.0):
    """한 모듈: 출렁임 = 윗음, 굵기 = 울리는 음 수, 웅덩이 = 긴 화음, 튀는 획 = 선율 꼭대기."""
    dens, top = np.zeros(N), np.full(N, np.nan)
    for s, p, d in notes:
        for k in range(s, s + d): dens[k % N] += 1
        top[s] = p if np.isnan(top[s]) else max(top[s], p)
    idx = np.arange(N); ok = ~np.isnan(top); top = np.interp(idx, idx[ok], top[ok], period=N)
    dens, top = gaussian_filter1d(dens, 1.1, mode='wrap'), gaussian_filter1d(top, 1.4, mode='wrap')
    M = 2200; u = np.linspace(0, N, M, endpoint=False)
    if upto is not None: u = u[u < upto]
    rr = 1.0 + 0.11 * (np.interp(u, np.arange(N + 1), np.append(top, top[0])) - 72) / 9
    ww = 0.010 + 0.060 * (np.interp(u, np.arange(N + 1), np.append(dens, dens[0])) / 4) ** 2
    D = np.zeros((G, G)); stroke(D, u, rr + rng.normal(0, .004, len(u)), ww, N, 0.55, rot)
    for s, p, d in notes:
        if upto is not None and s >= upto: continue
        if d >= 5: stamp_pool(D, s + d / 2, N, rot)                     # 길게 끄는 화음 = 웅덩이
        if p >= 79: flick(D, s, N, 1.0 + 0.11 * (p - 72) / 9, 0.30 + 0.10 * (p - 79), 0.040, 0.35 if p == 81 else -0.25, rot)
    return D

def stamp_pool(D, t, N, rot):
    a = ang(t, N, rot)
    for _ in range(40):
        r = 1.0 + rng.normal(0, 0.07); da = rng.normal(0, 0.10)
        stamp(D, r * np.cos(a + da), r * np.sin(a + da), rng.uniform(0.02, 0.06), 0.33)
    for _ in range(3): flick(D, t + rng.normal(0, .4), N, 1.04, rng.uniform(.10, .22), .022, rng.uniform(-.5, .5), rot, .6, 2)

mod = [(s, p, e - s) for s, p, e in O1 if s < 32]
A = render(module_field(mod, rot=0.3))

# 곡 전체: 두 가닥이 위상이 맞을 때 합쳐지고 1/4 모듈 어긋날 때 벌어진다
N = 1089; dens = np.zeros((2, N)); on = {}
for h, inst in enumerate((O1, O2)):
    for s, p, e in inst: dens[h, s:e] += 1; on.setdefault((s, p), set()).add(h)
t = np.arange(N); drift = np.clip((t - 33) / 33 + 1, 0, 32)                 # 왼손이 늦은 박 수(모듈마다 +1)
sep = 0.11 * np.sin(np.pi * drift / 16) ** 2                              # 0 · 16 · 32 박 늦음에서 0 (구절 단위로 맞음)
DB = np.zeros((G, G)); M = 5200; u = np.linspace(0, N, M, endpoint=False)
for h, sg in ((0, -1), (1, 1)):
    d = gaussian_filter1d(dens[h], 6, mode='wrap')
    stroke(DB, u, 1.0 + sg * np.interp(u, t, sep) + rng.normal(0, .003, M), 0.008 + 0.018 * np.interp(u, t, d) / 4, N, 0.5, 0.0)
uni = sorted((s, p) for (s, p), hs in on.items() if len(hs) == 2)
for s, p in uni:
    bend = 0.5 * np.sign(np.sin(2 * np.pi * s / N)) * rng.uniform(0.3, 1.0)
    flick(DB, s, N, 1.0 + np.interp(s, t, sep), 0.05 + 0.012 * (p - 60) + rng.uniform(0, .05), 0.010, bend, w=0.5, drops=1)
B = render(DB)

# 맞히기: 그림자 = 들려준 문장(같은 재료의 변주), 검은 획 = 내가 쓴 곳(24박까지 hibari 대로) · 틀린 박은 옅은 먹
V1, _ = P.piece(P.turn(P.IDENT, 0, 1)); tgt = [(s, p, e - s) for s, p, e in V1 if s < 32]
ghost = module_field(tgt, rot=0.3); mine = module_field(mod, upto=24, rot=0.3)
by = lambda ns: {k: sorted((p, d) for s, p, d in ns if s == k) for k in range(32)}
bt, bm = by(tgt), by(mod); wrong = [k for k in range(24) if bt[k] != bm[k]]
yy, xx = np.mgrid[0:G, 0:G]; X = xx / (G - 1) * 2 * L - L; Y = yy / (G - 1) * 2 * L - L
tt = ((np.pi / 2 + 0.3 - np.arctan2(Y, X)) % (2 * np.pi)) / (2 * np.pi) * 32
rust = gaussian_filter(np.isin(np.floor(tt).astype(int), wrong).astype(float), 10)
C = render(mine, ghost=ghost, rust=rust)
print(f'두 손 같은 음 {len(uni)} · 맞히기 24박 중 틀린 박 {len(wrong)} {wrong}')

fig = plt.figure(figsize=(16, 6.1), facecolor='#eeece6')
for k, (img, ttl) in enumerate([(A, '가  쓰기 — hibari 한 모듈'), (B, '나  읽기 — hibari 곡 전체'), (C, '다  맞히기 — 들은 문장을 따라 쓰기')]):
    ax = fig.add_axes([0.005 + k * 0.333, 0.075, 0.325, 0.85]); ax.imshow(img, origin='lower'); ax.axis('off')
    fig.text(0.02 + k * 0.333, 0.03, ttl, fontsize=12.5, color='#2a2e2b')
out = os.path.join(ROOT, 'docs', 'figures', 'logogram_ink.png')
fig.savefig(out, dpi=100, facecolor='#eeece6'); print('저장', out)
