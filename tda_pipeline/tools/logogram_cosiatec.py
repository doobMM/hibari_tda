"""
tools/logogram_cosiatec.py — 곡을 '낱말(동기) + 옮김(군 원소)' 으로 나누고, 그 문법대로 원형문자를 쓴다 (2026-10-14 사용자: "응, 부탁할게. 방향 전환이구나!").
앞 대화: 원형문자는 "규칙이 있는지, 정합적인지, 상호작용을 용이하게 하는지" 가 중요 · aqua 등은 대칭 이외의 구조 · Group theory · 지도교수님의 modular operation.

분해 = COSIATEC 의 최소 구현 (Meredith 2002 · 2013; 파이썬 구현을 찾지 못해 직접):
  점 = (16분음표 시각, 음높이). 옮김 v 의 MTP = {p : p + v ∈ D}. 큰 MTP 몇 개를 낱말 후보로 → 낱말 P 의 옮김 집합 T = {u : P + u ⊆ D} (TEC).
  압축률 = 덮은 점 수 / (|P| + |T| − 1) 이 가장 큰 TEC 를 문장에 넣고 덮은 점을 지운 뒤 되풀이. 압축률 < 2 이거나 점이 다하면 멈춘다 → 남은 점 = 옮김으로 설명되지 않는 '새 낱말'.
  옮김 u = (Δ시각, Δ음높이) 는 군 Z × Z 의 원소다. Δ음높이 ≠ 0 이면 조옮김.

그림 규칙 (곡마다 같다 — 음악의 옮김 ↔ 그림의 움직임):
  잉크 고리 하나 = 곡 전체(각 = 시각, 처음과 끝이 만난다). 고리 굵기 = 그때 울리는 음의 밀도.
  낱말이 되돌아올 때마다 **같은 모양의 획**이 고리에서 돋는다: 자리 = 시간 옮김, 안팎으로 밀린 거리 = 조옮김(낱말 안 음높이와 같은 자, 반음 = 0.017).
  큰 낱말 셋까지(바깥 획 · 안쪽 획 · 가는 획). 작은 낱말·남은 음은 고리의 결.
  먹 결은 FlxB2/arrival_logograms(MIT): 겹친 열린 원호 · 디스크 덩이 · 무작위로 굽는 촉수(크게 옮긴 되풀이에만) → 두 번 흐림 → 문턱.
  고리는 곡의 가장 큰 낱말이 조옮김 없이 끝까지 되돌아오면 닫고(hibari = Z32×Z33 이 한 바퀴 돌아 처음 위상으로), 아니면 이음매를 연다.
  아래 띠 = Wolfram unwrapping-01.nb 처럼 고리를 편 것 = 악보(가로 시각 · 위가 바깥). 띠를 옆으로 돌리기 = 시간 옮김(군의 작용).
  ⚠ 버린 그림 둘: 낱말을 나올 때마다 점으로 다 찍기(빗살·흩뿌림, 읽히지 않음) · 낱말을 가운데 한 번 + 고리 눈금(규칙은 읽히나 도식 — "이미지가 맘에 안 들어").
대조: 시각은 그대로 두고 음높이만 섞은 곡을 같은 분해에 넣는다 — 그 덮음이 우연의 바닥이다. 낱말은 5음 이상만(4음 이하는 우연히 맞기 쉽다).
산출: docs/figures/logogram_cosiatec.png · docs/step3_data/logogram_cosiatec.json (낱말·옮김 목록)
한계: 탐색이다(우연 대조 없음). 반전(거울)·늘이기는 넣지 않았다. COSIATEC 은 모든 MTP 를 보지만 여기서는 후보를 '자주 나는 옮김 60 + (횟수 × 거리) 큰 옮김 60 + 가장 멀리 뛰는 옮김 120' 으로 줄였다
  (처음엔 멀리 뛰는 옮김을 빼서 hibari 첫 모듈 × 65 옮김을 놓쳤다).
"""
import os, json, warnings
import numpy as np, pretty_midi
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = 1000                                                               # 점 (t, p) → t * ENC + p

def points(f):
    pm = pretty_midi.PrettyMIDI(os.path.join(ROOT, f)); q = pm.resolution / 4
    return np.array(sorted({(round(pm.time_to_tick(n.start) / q), n.pitch) for ins in pm.instruments if not ins.is_drum for n in ins.notes}))

def tec(P, Dk):
    """P 를 통째로 옮겨도 D 안에 있는 옮김 u 전부."""
    cand = Dk - (P[0, 0] * ENC + P[0, 1])
    for t, p in P[1:]:
        cand = cand[np.isin(cand + t * ENC + p, Dk)]
    return cand

def cosiatec(D, K=60, stop=2.0, minp=5):
    words, D = [], D.copy()
    while len(D) > 8:
        Dk = D[:, 0] * ENC + D[:, 1]
        dt, dp = D[None, :, 0] - D[:, None, 0], D[None, :, 1] - D[:, None, 1]
        m = (dt > 0) | ((dt == 0) & (dp > 0))
        v, c = np.unique(dt[m] * ENC + dp[m], return_counts=True)        # dp 범위 |dp| < 128 이라 ENC 로 겹치지 않는다
        best = None
        vt_all = np.floor((v + ENC // 2) / ENC)
        ok = np.where(c >= 4)[0]                                          # 후보: 자주 나는 옮김 K 개 + 멀리 가는 옮김 K 개(작은 낱말 × 많은 옮김)
        cand = np.unique(np.r_[np.argsort(-c)[:K], ok[np.argsort(-(c[ok] * vt_all[ok]))][:K],
                               ok[np.argsort(-vt_all[ok])][:2 * K]])     # 가장 멀리 뛰는 옮김 = 곡 앞머리만 남는 작은 낱말(많이 되풀이될수록 압축이 크다)
        for k in cand:
            vt = int(vt_all[k]); vp = int(v[k] - vt * ENC)
            P = D[np.isin(Dk + vt * ENC + vp, Dk)]                        # MTP(v)
            if len(P) < minp: continue                                    # 4음 이하 낱말은 우연히 맞기 쉽다 (아래 섞은 곡 대조)
            T = tec(P, Dk)
            cov = np.unique((P[:, 0] * ENC + P[:, 1])[:, None] + T[None, :])
            cr = len(cov) / (len(P) + len(T) - 1)
            if best is None or cr > best[0]: best = (cr, P, T, cov)
        if best is None or best[0] < stop: break
        cr, P, T, cov = best
        Tt = np.floor((T + ENC // 2) / ENC).astype(int); Tp = (T - Tt * ENC).astype(int)
        words.append({'P': P.tolist(), 'T': list(zip(Tt.tolist(), Tp.tolist())), 'cover': int(len(cov)), 'cr': round(float(cr), 2)})
        D = D[~np.isin(Dk, cov)]
    return words, D

# ── 그림: 낱말은 한 번 크게, 고리 위에는 되돌아오는 자리만 ─────────────────────────
G, L = 820, 1.6
rng = np.random.default_rng(11)
def fbm(sc=((60, 1.0), (22, 0.5), (8, 0.25))):
    f = sum(a * gaussian_filter(rng.normal(size=(G, G)), s) * s for s, a in sc); return f / (np.abs(f).max() + 1e-9)
def stamp(D, x, y, s, w):
    i, j, r = (y + L) / (2 * L) * (G - 1), (x + L) / (2 * L) * (G - 1), max(s / (2 * L) * (G - 1), 0.7)
    R = int(3 * r) + 2; i0, i1, j0, j1 = max(0, int(i) - R), min(G, int(i) + R + 1), max(0, int(j) - R), min(G, int(j) + R + 1)
    if i0 < i1 and j0 < j1:
        yy, xx = np.mgrid[i0:i1, j0:j1]; D[i0:i1, j0:j1] += w * np.exp(-((yy - i) ** 2 + (xx - j) ** 2) / (2 * r * r))
def line(F, a, b, s, w, n=None):
    n = n or max(4, int(np.hypot(b[0] - a[0], b[1] - a[1]) / 0.004))
    for u in np.linspace(0, 1, n): stamp(F, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, s, w)
PX = 0.017                                                               # 반음 하나 = 반지름 0.017 — 낱말 안의 음높이와 조옮김이 같은 자(정합성)

NIB = np.deg2rad(35)                                                     # 납작붓 각도: 이 방향으로 그으면 가장 가늘고, 직각이면 가장 굵다

def splat(F, x, y, wt):
    """점들을 격자에 쌍선형으로 뿌린다 (털 한 가닥의 먹)."""
    j = (np.asarray(x) + L) / (2 * L) * (G - 1); i = (np.asarray(y) + L) / (2 * L) * (G - 1)
    i0, j0 = np.floor(i).astype(int), np.floor(j).astype(int); di, dj = i - i0, j - j0
    for a, b, ww in ((0, 0, (1 - di) * (1 - dj)), (1, 0, di * (1 - dj)), (0, 1, (1 - di) * dj), (1, 1, di * dj)):
        ii, jj = i0 + a, j0 + b; ok = (ii >= 0) & (ii < G) & (jj >= 0) & (jj < G)
        np.add.at(F, (ii[ok], jj[ok]), (ww * wt)[ok])

def brush(F, path, wmax, wmin=None, press=None, dry=0.5, pool=True):
    """먹 붓획 = 털 여러 가닥. 굵기 = 방향(납작붓 각) × 누름 × press. 가닥마다 먹이 다르게 줄어 빠르고 가는 데서 비백이 난다."""
    path = np.asarray(path, float); wmin = 0.15 * wmax if wmin is None else wmin
    px = (G - 1) / (2 * L)
    seg = np.cumsum(np.r_[0, np.hypot(*np.diff(path, axis=0).T)]); n = max(30, int(seg[-1] * px / 0.5))
    u = np.linspace(0, seg[-1], n); sm = lambda v, s_=3: gaussian_filter1d(np.interp(u, seg, v), s_, mode='nearest')
    x, y = sm(path[:, 0]), sm(path[:, 1]); pr = sm(np.ones(len(path)) if press is None else np.asarray(press, float))
    dx, dy = np.gradient(x), np.gradient(y); d = np.arctan2(dy, dx); nrm = np.hypot(dx, dy) + 1e-12; nx, ny = -dy / nrm, dx / nrm
    a = np.linspace(0, 1, n)
    env = np.minimum(1, (a / 0.12) ** 0.5) * np.minimum(1, ((1 - a) / 0.35) ** 1.1)
    w = (wmin + (wmax - wmin) * np.abs(np.sin(d - NIB)) ** 0.9) * (0.2 + 0.8 * env) * pr
    thin = 1 - np.clip(w / wmax, 0, 1)
    B = max(8, int(2.2 * wmax * px))
    for b in range(B):
        o = (b / (B - 1)) * 2 - 1 + rng.normal(0, 0.04)
        rate = dry * rng.uniform(0.4, 1.6) * (0.6 + abs(o))              # 가장자리 털이 먼저 마른다
        load = 1.05 - rate * a ** 1.4 * (0.5 + thin) + 0.25 * gaussian_filter1d(rng.normal(size=n), 6)
        load = np.clip(load, 0, 1) * (rng.random(n) < np.clip(load * 1.6, 0, 1))  # 먹이 마르면 끊긴다 = 비백
        splat(F, x + o * w * nx, y + o * w * ny, load * 0.9)
    if pool:                                                             # 붓을 대는 자리에 먹이 고인다
        for _ in range(3): stamp(F, x[0] + rng.normal(0, w[2] * .3), y[0] + rng.normal(0, w[2] * .3), max(w[:8].max(), wmin) * 0.9, 1.6)

def flick(F, x0, y0, ang, length, w, bend):
    """삐침: 굽으며 빨리 빠지는 획 + 끝에서 튀는 먹 방울."""
    t = np.linspace(0, 1, 12); a = ang + bend * t ** 1.5
    pts = np.c_[x0 + np.cumsum(np.cos(a)) * length / 12, y0 + np.cumsum(np.sin(a)) * length / 12]
    brush(F, pts, w, w * 0.25, press=np.linspace(1.0, 0.35, 12), dry=1.1, pool=False)
    ex, ey = pts[-1]
    for _ in range(rng.integers(1, 4)):
        r_ = rng.uniform(0.02, 0.09); da = rng.normal(0, 0.35)
        stamp(F, ex + r_ * np.cos(a[-1] + da), ey + r_ * np.sin(a[-1] + da), rng.uniform(0.002, 0.007), 2.0)

def contour(P):
    """낱말의 선율 윤곽: 시각마다 가장 높은 음 → (0..1 시간, 반음)."""
    P = np.array(P); ts = np.unique(P[:, 0]); top = np.array([P[P[:, 0] == t, 1].max() for t in ts]); chord = np.array([(P[:, 0] == t).sum() for t in ts])
    x = (ts - ts.min()) / max(np.ptp(ts), 1); return x, top - top.mean(), chord

def glyph(F, P, ups, n, at, frame, size):
    """낱말 하나 = 먹 붓획 하나. 굵기 상한 = 되돌아온 횟수 · 점마다 무게 = 그 박의 화음 크기.
       곁획 = 조옮김마다 삐침 하나(위로 옮김 = 바깥, 아래 = 안쪽, 길이 ∝ 음정, 굽음은 획을 따라 흐르는 쪽)."""
    x, y, chord = contour(P); amp = size * 0.55 / max(np.ptp(y), 7)
    path = [frame(at + (xi - 0.5) * size, yi * amp) for xi, yi in zip(x, y)]
    w = min(0.017 + 0.0045 * np.log2(1 + n), 0.042)
    brush(F, path, w, press=0.75 + 0.12 * chord, dry=0.7)
    ds = sorted(set(ups) - {0})
    for k, d in enumerate(ds):
        sgn = 1 if d > 0 else -1; xs = at + ((k + 0.5) / len(ds) - 0.5) * size * 0.85
        x0, y0 = frame(xs, np.interp((xs - at) / size + 0.5, x, y) * amp)
        x1, y1 = frame(xs + 0.01, sgn * 1.0)
        ang = np.arctan2(y1 - y0, x1 - x0) + rng.normal(0, 0.25)
        flick(F, x0, y0, ang, 0.08 + 0.007 * abs(d), w * 0.9, sgn * rng.uniform(0.4, 1.0))

def draw(words, rest, Ttot, notes_t, closed):
    """원형문자 = 굵은 고리 하나 + 낱말 붓획 몇 개(큰 낱말부터 최대 5개, 처음 나온 자리에 한 번만).
       고리를 열고 닫기 = 가장 큰 낱말이 조옮김 없이 곡 끝까지 돌아오는가. 먹 결 = FlxB2(겹친 열린 원호 → 흐림 → 문턱)."""
    F = np.zeros((G, G)); R = 1.0
    dens = np.bincount(np.clip(notes_t, 0, Ttot - 1), minlength=Ttot).astype(float)
    dens = gaussian_filter(np.r_[dens, dens, dens], Ttot / 90)[Ttot:2 * Ttot]; dens = (dens - dens.min()) / (np.ptp(dens) + 1e-9)
    gapa = 0.0 if closed else 0.30                                      # 열린 곡은 이음매(처음 = 끝 자리)를 비운다
    th = np.linspace(np.pi / 2 - gapa / 2, np.pi / 2 - 2 * np.pi + gapa / 2, 2600)
    tt = (((np.pi / 2 - th) % (2 * np.pi)) / (2 * np.pi) * Ttot).astype(int) % Ttot
    ring = np.c_[R * np.cos(th), R * np.sin(th)]
    if closed: ring = np.r_[ring, ring[:40]]; tt = np.r_[tt, tt[:40]]  # 닫힌 고리는 이음매 없이 겹쳐 잇는다
    brush(F, ring, 0.058, 0.009, press=0.45 + 0.65 * dens[tt] ** 1.3, dry=0.45)
    tot = sum(w['cover'] for w in words); placed = []
    for w in words[:5]:
        P = np.array(w['P']); T = np.array(w['T']); t0 = P[:, 0].min() + T[:, 0].min()
        th = np.pi / 2 - 2 * np.pi * t0 / Ttot
        while any(abs(((th - q + np.pi) % (2 * np.pi)) - np.pi) < 0.75 for q in placed): th -= 0.25   # 획끼리 겹치지 않게
        placed.append(th)
        size = 0.35 + 0.55 * np.sqrt(w['cover'] / tot)
        tx, ty, rx, ry = np.sin(th), -np.cos(th), np.cos(th), np.sin(th)   # 고리 접선(시계 방향) · 바깥
        base = R + 0.07
        frame = lambda x, y, th=th: (base * np.cos(th) + x * np.sin(th) + (y + 0.0) * np.cos(th), base * np.sin(th) - x * np.cos(th) + y * np.sin(th))
        glyph(F, P, T[:, 1].tolist(), len(T), 0.0, frame, size)
    return ink(F)

def ink(F, paper=True):
    """먹: 농담(1 − e^−k·밀도) · 종이로 번진 가장자리 · 종이 결이 먹을 먹는 정도."""
    g = F.shape[0]; D = gaussian_filter(F, 0.7)
    fib = gaussian_filter(rng.normal(size=F.shape), 0.8); fib = 0.85 + 0.15 * fib / (np.abs(fib).max() + 1e-9)
    tone = 1 - np.exp(-1.9 * D * fib)
    bleed = gaussian_filter(D, 2.2) * (0.6 + 0.4 * gaussian_filter(rng.normal(size=F.shape), 3) / 0.2)
    bleed = np.clip(1 - np.exp(-0.5 * bleed), 0, 1) * 0.35
    t = np.clip(np.maximum(tone, bleed), 0, 1)[..., None]
    yy, xx = np.mgrid[0:g, 0:g].astype(float); r = np.hypot(xx - g / 2, yy - g / 2) / (g / 2)
    base = np.array([241, 238, 231]) / 255 * ((1 - 0.07 * r[..., None] ** 2) if paper else 1)
    inkc = np.array([16, 16, 18]) / 255; mid = np.array([92, 88, 84]) / 255       # 옅은 먹은 따뜻한 회색
    col = mid * (1 - t) + inkc * t
    return np.clip(base * (1 - t) + col * t, 0, 1)

def letters(words, H=150, W=1400):
    """낱자 표 (Wolfram sectionBreaking 처럼 원형문자의 조각을 떼어 세운 것): 낱말 붓획을 한 줄로."""
    global G, L
    G0, L0 = G, L; G, L = 260, 0.9; cells = []
    for w in words[:5]:
        F = np.zeros((G, G)); T = np.array(w['T'])
        glyph(F, w['P'], T[:, 1].tolist(), len(T), 0.0, lambda x, y: (x, y - 0.05), 0.95)
        cells.append(ink(F, paper=False)[::-1])
    G, L = G0, L0
    return cells

def kind(T):
    ps = {p for t, p in T}; return '시간 옮김만' if ps == {0} else '조옮김 ' + ' '.join(f'{p:+d}' for p in sorted(ps) if p)

import sys
DRAW_ONLY = '--draw' in sys.argv                                         # 분해는 8분 걸린다 — 그림만 고칠 땐 JSON 의 낱말을 쓴다
OLD = json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'logogram_cosiatec.json'), encoding='utf8')) if DRAW_ONLY else None
SONGS = [('Ryuichi_Sakamoto_-_hibari.mid', 'hibari'), ('aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid', 'aqua'), ('energy-flow-ryuichi-sakamoto.mid', 'energy flow')]
fig = plt.figure(figsize=(16, 8.6), facecolor='#eeece6'); rec = {}
for k, (f, name) in enumerate(SONGS):
    D = points(f)
    if DRAW_ONLY:
        old = OLD['songs'][name]; words = [{'P': w['pattern'], 'T': [tuple(x) for x in w['translators']], 'cover': w['cover'], 'cr': w['cr']} for w in old['words']]
        cov_k = set(); [cov_k.update((t + ut) * ENC + p + up for t, p in w['P'] for ut, up in w['T']) for w in words]
        rest = D[~np.isin(D[:, 0] * ENC + D[:, 1], list(cov_k))]; wn, null = [None] * old['null_words'], old['null_pitch_shuffle_covered_frac']
    else:
        words, rest = cosiatec(D)
    if not DRAW_ONLY:
        Dn = D.copy(); Dn[:, 1] = np.random.default_rng(0).permutation(Dn[:, 1])     # 대조: 같은 시각, 음높이만 섞은 곡
        wn, rn = cosiatec(Dn); null = 1 - len(rn) / len(Dn)
    cov = sum(w['cover'] for w in words)
    print(f'\n{name}: 점 {len(D)} · 낱말 {len(words)} 개가 {cov} 점({cov / len(D):.0%})을 덮는다 · 남은 점 {len(rest)}')
    for i, w in enumerate(words[:8]):
        print(f'  낱말 {i + 1}: 음 {len(w["P"])} × 옮김 {len(w["T"])} → {w["cover"]} 점, 압축 {w["cr"]} · {kind(w["T"])}')
    rec[name] = {'points': int(len(D)), 'covered': int(cov), 'rest': int(len(rest)), 'null_pitch_shuffle_covered_frac': round(null, 3), 'null_words': len(wn), 'words': [{'notes': len(w['P']), 'translators': w['T'], 'cover': w['cover'], 'cr': w['cr'], 'pattern': w['P']} for w in words]}
    Ttot = int(D[:, 0].max() + 1); big = words[0]
    closed = max(ut for ut, up in big['T']) + max(t for t, p in big['P']) - min(t for t, p in big['P']) >= Ttot - 16 and all(up == 0 for ut, up in big['T'])
    img = draw(words, rest, Ttot, D[:, 0], closed); cells = letters(words)
    ax = fig.add_axes([0.005 + k * 0.333, 0.30, 0.325, 0.68]); ax.imshow(img, origin='lower'); ax.axis('off')
    for c, (cell, w) in enumerate(zip(cells, words[:5])):
        axc = fig.add_axes([0.012 + k * 0.333 + c * 0.062, 0.12, 0.058, 0.13]); axc.imshow(cell); axc.axis('off')
        ups = sorted(set(u for t, u in w['T']) - {0})
        axc.set_title(f'×{len(w["T"])}' + (' ' + ' '.join(f'{u:+d}' for u in ups[:3]) if ups else ''), fontsize=7.5, color='#5d655f', pad=1)
    print(f'  고리 {"닫힘" if closed else "열림"}')
    fig.text(0.02 + k * 0.333, 0.275, name, fontsize=14, color='#1d201e')
    lines = [f'낱말 {len(words)}개가 음의 {cov / len(D):.0%} 를 쓴다 (음높이 섞은 곡 {null:.0%})']
    for i, w in enumerate(words[:3]):
        pass
    fig.text(0.02 + k * 0.333, 0.05, '\n'.join(lines), fontsize=9.5, color='#5d655f', va='bottom')
fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'logogram_cosiatec.png'), dpi=100, facecolor='#eeece6')
if not DRAW_ONLY: json.dump({'script': 'tools/logogram_cosiatec.py', 'unit': '16분음표', 'songs': rec}, open(os.path.join(ROOT, 'docs', 'step3_data', 'logogram_cosiatec.json'), 'w', encoding='utf8'), ensure_ascii=False)
print('저장 docs/figures/logogram_cosiatec.png · docs/step3_data/logogram_cosiatec.json')
