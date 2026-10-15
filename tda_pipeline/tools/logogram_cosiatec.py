"""
tools/logogram_cosiatec.py — 곡을 '낱말(동기) + 옮김(군 원소)' 으로 나누고, 그 문법대로 원형문자를 쓴다 (2026-10-14 사용자: "응, 부탁할게. 방향 전환이구나!").
앞 대화: 원형문자는 "규칙이 있는지, 정합적인지, 상호작용을 용이하게 하는지" 가 중요 · aqua 등은 대칭 이외의 구조 · Group theory · 지도교수님의 modular operation.

분해 = COSIATEC 의 최소 구현 (Meredith 2002 · 2013; 파이썬 구현을 찾지 못해 직접):
  점 = (16분음표 시각, 음높이). 옮김 v 의 MTP = {p : p + v ∈ D}. 큰 MTP 몇 개를 낱말 후보로 → 낱말 P 의 옮김 집합 T = {u : P + u ⊆ D} (TEC).
  압축률 = 덮은 점 수 / (|P| + |T| − 1) 이 가장 큰 TEC 를 문장에 넣고 덮은 점을 지운 뒤 되풀이. 압축률 < 2 이거나 점이 다하면 멈춘다 → 남은 점 = 옮김으로 설명되지 않는 '새 낱말'.
  옮김 u = (Δ시각, Δ음높이) 는 군 Z × Z 의 원소다. Δ음높이 ≠ 0 이면 조옮김.

그림 규칙 (곡마다 같다 — 음악의 옮김 ↔ 그림의 움직임):
  곡 전체가 고리 한 바퀴(각 = 시각, 처음과 끝이 만난다). 낱말(동기)은 처음 나온 자리 안쪽에 **한 번만** 크게 쓴다(가로 = 시간, 세로 = 음높이).
  고리 위 눈금 = 그 낱말이 되돌아오는 자리(시간 옮김) · 눈금이 안팎으로 밀린 만큼 = 조옮김(반음 하나 = 0.012, 옥타브 = 0.144).
  큰 낱말 셋까지 먹 빛 하나씩(짙은 먹 · 갈색 · 푸른 먹). 옮김으로 설명되지 않는 음 = 고리 바깥 옅은 점.
  ⚠ 첫 그림(낱말이 나올 때마다 다 찍기)은 hibari 가 빗살, 다른 곡은 흩뿌림이라 읽히지 않았다.
대조: 시각은 그대로 두고 음높이만 섞은 곡을 같은 분해에 넣는다 — 그 덮음이 우연의 바닥이다. 낱말은 5음 이상만(4음 이하는 우연히 맞기 쉽다).
산출: docs/figures/logogram_cosiatec.png · docs/step3_data/logogram_cosiatec.json (낱말·옮김 목록)
한계: 탐색이다(우연 대조 없음). 반전(거울)·늘이기는 넣지 않았다. COSIATEC 은 모든 MTP 를 보지만 여기서는 후보를 '자주 나는 옮김 60 + (횟수 × 거리) 큰 옮김 60 + 가장 멀리 뛰는 옮김 120' 으로 줄였다
  (처음엔 멀리 뛰는 옮김을 빼서 hibari 첫 모듈 × 65 옮김을 놓쳤다).
"""
import os, json, warnings
import numpy as np, pretty_midi
from scipy.ndimage import gaussian_filter, map_coordinates
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
TONES = [(16, 18, 20), (110, 58, 34), (40, 70, 98)]
PX = 0.012                                                               # 반음 하나 = 반지름 0.012 (옥타브 = 0.144)
def draw(words, rest, Ttot):
    ang = lambda t: np.pi / 2 - 2 * np.pi * t / Ttot
    polar = lambda a, r: (r * np.cos(a), r * np.sin(a))
    layers = []
    base = np.zeros((G, G))
    for t, p in rest: stamp(base, *polar(ang(t), 1.02 + rng.normal(0, .01)), 0.006, 0.35)        # 옮김으로 설명되지 않는 음 = 옅은 점
    for k, w in enumerate(words[:3]):
        F = np.zeros((G, G)); P = np.array(w['P']); T = np.array(w['T']); t0 = P[:, 0].min()
        for ut, up in T:                                                 # 되돌아오는 자리 = 고리 위 눈금 (조옮김이면 안팎으로 밀림)
            a = ang(t0 + ut); r = 1.0 + 0.05 * k + PX * up
            line(F, polar(a, r - 0.035), polar(a, r + 0.035), 0.0055, 0.55)
        a0 = ang(t0 + T[:, 0].min()); Q = P - [t0, int(np.median(P[:, 1]))]  # 낱말 = 고리 안 세 자리(위·오른아래·왼아래)에 크게 한 번
        slot = np.pi / 2 - 2 * np.pi * k / 3
        span = max(Q[:, 0].max(), 1); sc_t = 0.42 / span; sc_p = 0.30 / max(np.ptp(Q[:, 1]), 6)
        cx, cy = polar(slot, 0.52); tx, ty, rx, ry = 1.0, 0.0, 0.0, 1.0           # 낱말은 똑바로 선다(가로 = 시간, 세로 = 음높이)
        pt = lambda q: (cx + (q[0] - span / 2) * sc_t * tx + q[1] * sc_p * rx, cy + (q[0] - span / 2) * sc_t * ty + q[1] * sc_p * ry)
        Qs = Q[np.lexsort((Q[:, 1], Q[:, 0]))]
        for q0, q1 in zip(Qs[:-1], Qs[1:]): line(F, pt(q0), pt(q1), 0.008 if q0[0] == q1[0] else 0.012, 0.6)
        for q in Qs: stamp(F, *pt(q), 0.02, 0.9)
        layers.append(F)
    yy, xx = np.mgrid[0:G, 0:G].astype(float); wx, wy = fbm() * 5, fbm() * 5
    warp = lambda A: map_coordinates(A, [yy + wy, xx + wx], order=1)
    r = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
    out = np.array([238, 236, 230]) / 255 * (1 - 0.10 * r[..., None] ** 2)
    halo = gaussian_filter(warp(sum(layers) + base), 14); halo /= halo.max() + 1e-9
    out = out * (1 - 0.28 * halo[..., None]) + np.array([140, 148, 154]) / 255 * (0.28 * halo[..., None])
    for F, col, a in [(base, (120, 126, 130), 0.6)] + [(layers[k], TONES[k], 0.95) for k in range(len(layers) - 1, -1, -1)]:
        core = np.clip(1 - np.exp(-1.8 * warp(F)), 0, 1)[..., None]; out = out * (1 - a * core) + np.array(col) / 255 * (a * core)
    return np.clip(out, 0, 1)

def kind(T):
    ps = {p for t, p in T}; return '시간 옮김만' if ps == {0} else '조옮김 ' + ' '.join(f'{p:+d}' for p in sorted(ps) if p)

import sys
DRAW_ONLY = '--draw' in sys.argv                                         # 분해는 8분 걸린다 — 그림만 고칠 땐 JSON 의 낱말을 쓴다
OLD = json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'logogram_cosiatec.json'), encoding='utf8')) if DRAW_ONLY else None
SONGS = [('Ryuichi_Sakamoto_-_hibari.mid', 'hibari'), ('aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid', 'aqua'), ('energy-flow-ryuichi-sakamoto.mid', 'energy flow')]
fig = plt.figure(figsize=(16, 7.4), facecolor='#eeece6'); rec = {}
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
    img = draw(words, rest, D[:, 0].max() + 1)
    ax = fig.add_axes([0.005 + k * 0.333, 0.2, 0.325, 0.76]); ax.imshow(img, origin='lower'); ax.axis('off')
    fig.text(0.02 + k * 0.333, 0.155, name, fontsize=14, color='#1d201e')
    lines = [f'낱말 {len(words)}개가 음의 {cov / len(D):.0%} 를 쓴다 (음높이 섞은 곡 {null:.0%})']
    for i, w in enumerate(words[:3]):
        lines.append(f'{"짙은 먹 · 갈색 · 푸른 먹".split(" · ")[i]}: {len(w["P"])}음 × {len(w["T"])}번 — {kind(w["T"])}')
    fig.text(0.02 + k * 0.333, 0.02, '\n'.join(lines), fontsize=9.5, color='#5d655f', va='bottom')
fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'logogram_cosiatec.png'), dpi=100, facecolor='#eeece6')
if not DRAW_ONLY: json.dump({'script': 'tools/logogram_cosiatec.py', 'unit': '16분음표', 'songs': rec}, open(os.path.join(ROOT, 'docs', 'step3_data', 'logogram_cosiatec.json'), 'w', encoding='utf8'), ensure_ascii=False)
print('저장 docs/figures/logogram_cosiatec.png · docs/step3_data/logogram_cosiatec.json')
