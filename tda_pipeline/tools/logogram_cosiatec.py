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
PX = 0.017                                                               # 반음 하나 = 반지름 0.017 — 낱말 안의 음높이와 조옮김이 같은 자(정합성)

def draw(words, rest, Ttot, notes_t, closed):
    """FlxB2/arrival_logograms 의 먹 결(겹친 열린 원호 · 디스크 덩이 · 굽는 촉수 → 두 번 흐림 → 문턱)에 우리 문법을 싣는다.
       고리 = 곡 전체(각 = 시각) · 원호 겹의 굵기 = 음 밀도 · 낱말이 되돌아올 때마다 같은 모양의 획(자리 = 시간 옮김, 안팎 = 조옮김).
       closed = 곡의 끝이 처음과 같은 위상이면 고리를 닫고, 아니면 이음매(처음 = 끝 자리)를 연다."""
    ang = lambda t: np.pi / 2 - 2 * np.pi * t / Ttot
    xy = lambda t, r: (r * np.cos(ang(t)), r * np.sin(ang(t)))
    F = np.zeros((G, G))
    dens = np.bincount(np.clip(notes_t, 0, Ttot - 1), minlength=Ttot).astype(float)
    dens = gaussian_filter(np.r_[dens, dens, dens], Ttot / 160)[Ttot:2 * Ttot]; dens /= dens.max() + 1e-9
    gap = 0.0 if closed else 0.035 * Ttot
    for c in range(5):                                                   # 겹친 열린 원호 (FlxB2 CircularStroke)
        cx, cy, rr = rng.normal(0, .012), rng.normal(0, .012), 1.0 + rng.normal(0, .01)
        t0 = gap * rng.uniform(.3, 1.0); t1 = Ttot - gap * rng.uniform(.3, 1.0) if gap else Ttot
        for u in np.linspace(t0, t1, 1600):
            x, y = xy(u, rr); stamp(F, x + cx, y + cy, (0.003 + 0.010 * dens[int(u) % Ttot]) * rng.uniform(.6, 1.4), 0.5)
    for t, p in rest: stamp(F, *xy(t, 1.0 + rng.normal(0, .02)), 0.004 * rng.uniform(.5, 1.5), 0.5)
    widths = [0.008, 0.007, 0.006]
    for k, w in enumerate(words[:3]):
        P = np.array(w['P']); P = P[np.lexsort((P[:, 1], P[:, 0]))]; base = int(np.median(P[:, 1]))
        side = 1 if k != 1 else -1
        for ut, up in w['T']:
            pts = [(t + ut, 1.0 + side * (0.04 + PX * (p - base + up))) for t, p in P]
            for (t0, r0), (t1, r1) in zip(pts[:-1], pts[1:]):
                if t1 - t0 > 16: continue
                for a in np.linspace(0, 1, 10): stamp(F, *xy(t0 + (t1 - t0) * a, r0 + (r1 - r0) * a), widths[k] * rng.uniform(.7, 1.3), 0.6)
            for _ in range(5):                                            # 뿌리 덩이 (FlxB2 disks)
                x, y = xy(pts[0][0] + rng.normal(0, Ttot / 900), 1.0 + rng.normal(0, .015)); stamp(F, x, y, rng.uniform(.004, .012), 0.6)
            if abs(up) >= 7:                                              # 크게 옮긴 되풀이 = 굽는 촉수 (FlxB2 Tendril, 무작위 걸음)
                x, y = xy(*pts[-1]); a = ang(pts[-1][0]) + (0 if side * up > 0 else np.pi); v = 0.0
                for s_ in range(40):
                    v = 0.9 * v + rng.uniform(-0.12, 0.12); a += v; x += 0.006 * np.cos(a); y += 0.006 * np.sin(a)
                    stamp(F, x, y, 0.005 * (1 - s_ / 45), 0.6)
    B = gaussian_filter(F, 1.6)                                          # 두 번 흐림 → 문턱 (FlxB2)
    core = np.clip((B - 0.18) / 0.06, 0, 1)
    yy, xx = np.mgrid[0:G, 0:G].astype(float)
    halo = gaussian_filter(B, 18); halo = np.clip(halo / (halo.max() + 1e-9) * (0.6 + 0.5 * fbm(((30, 1.0), (10, 0.6)))), 0, 1)
    r = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
    out = np.array([240, 238, 233]) / 255 * (1 - 0.08 * r[..., None] ** 2)
    out = out * (1 - 0.30 * halo[..., None]) + np.array([150, 156, 160]) / 255 * (0.30 * halo[..., None])
    return np.clip(out * (1 - core[..., None]) + np.array([14, 15, 17]) / 255 * core[..., None], 0, 1)

def unwrap(img, r0=0.62, r1=1.38, W=1400, H=150):
    """Wolfram unwrapping-01.nb 의 ImageTransformation[i, {ArcTan @@ #, Norm @ #} &] — 고리를 펴면 악보 띠(가로 = 시각, 세로 = 바깥쪽이 위)."""
    th = np.pi / 2 - 2 * np.pi * np.arange(W) / W; rr = np.linspace(r1, r0, H)
    X = rr[:, None] * np.cos(th)[None]; Y = rr[:, None] * np.sin(th)[None]
    j = (X + L) / (2 * L) * (G - 1); i = (Y + L) / (2 * L) * (G - 1)
    return np.stack([map_coordinates(img[..., c], [i, j], order=1) for c in range(3)], -1)

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
    img = draw(words, rest, Ttot, D[:, 0], closed); strip = unwrap(img)
    ax = fig.add_axes([0.005 + k * 0.333, 0.30, 0.325, 0.68]); ax.imshow(img, origin='lower'); ax.axis('off')
    ax2 = fig.add_axes([0.012 + k * 0.333, 0.205, 0.31, 0.07]); ax2.imshow(strip, aspect='auto'); ax2.axis('off')
    print(f'  고리 {"닫힘" if closed else "열림"}')
    fig.text(0.02 + k * 0.333, 0.155, name, fontsize=14, color='#1d201e')
    lines = [f'낱말 {len(words)}개가 음의 {cov / len(D):.0%} 를 쓴다 (음높이 섞은 곡 {null:.0%})']
    for i, w in enumerate(words[:3]):
        lines.append(f'{"바깥 획 · 안쪽 획 · 가는 획".split(" · ")[i]}: {len(w["P"])}음 × {len(w["T"])}번 — {kind(w["T"])}')
    fig.text(0.02 + k * 0.333, 0.02, '\n'.join(lines), fontsize=9.5, color='#5d655f', va='bottom')
fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'logogram_cosiatec.png'), dpi=100, facecolor='#eeece6')
if not DRAW_ONLY: json.dump({'script': 'tools/logogram_cosiatec.py', 'unit': '16분음표', 'songs': rec}, open(os.path.join(ROOT, 'docs', 'step3_data', 'logogram_cosiatec.json'), 'w', encoding='utf8'), ensure_ascii=False)
print('저장 docs/figures/logogram_cosiatec.png · docs/step3_data/logogram_cosiatec.json')
