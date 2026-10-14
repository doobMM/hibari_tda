"""
tools/logogram_views.py — 영화 『컨택트(Arrival)』의 원형문자에 hibari 를 얹으면 어떤 모양인가: 고르기 전 그림 셋 (2026-10-14 사용자).
  "영화 contact에 나온 원형문자에 우리 연구를 적용할 수 있을까?"

원형문자의 형식: 잉크 고리 하나 = 문장 하나, 처음도 끝도 없이 한 번에 쓴다. 뜻은 고리의 굵기·덩이·촉수(바깥으로 뻗은 획)에 있다.
hibari 의 형식: 32박 모듈 하나가 돌고, 왼손이 33박이라 한 모듈에 한 박씩 밀린다 — 곡 전체가 한 바퀴 밀린 뒤 끝난다.

읽는 규칙 (세 그림 공통): 각 = 박(시계 방향, 위에서 시작) · 고리 굵기 = 그 박에 울리고 있는 음 수 ·
바깥 촉수 = 선율·윗음(길수록 높다) · 안쪽 덩이 = 베이스(클수록 길다).
  가 쓰기    hibari 오른손 한 모듈 = 원형문자 하나. 종달새는 32박, 문어는 33박마다 같은 글자를 돈다.
  나 읽기    hibari 곡 전체(1089박) = 원형문자 하나. 안쪽 가닥 = 오른손, 바깥 가닥 = 왼손, 촉수 = 두 손이 같은 박에 같은 음(176번).
  다 맞히기  들려준 문장(같은 재료로 만든 변주)을 귀로 듣고 같게 쓴다 — 맞은 박 초록, 틀린 박 주황, 아직 안 쓴 곳은 열려 있다.
곡 = hibari MIDI 의 박·길이·음높이 그대로 (experiments/run_rings_h1_probe.py 의 piece()). 변주는 같은 모듈의 음 자리만 바꾼 것.
    python tools/logogram_views.py  → docs/figures/logogram_views.png
"""
import sys, os
import numpy as np
from scipy.ndimage import gaussian_filter1d
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
import run_rings_h1_probe as P
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'; plt.rcParams['axes.unicode_minus'] = False

G, L = 640, 1.75
rng = np.random.default_rng(20261014)
PAPER, INK = np.array([239, 236, 228]) / 255, np.array([28, 31, 28]) / 255
GREEN, CORAL, GOLD = np.array([47, 107, 79]) / 255, np.array([216, 90, 48]) / 255, np.array([201, 138, 18]) / 255

def stamp(D, x, y, s, w=1.0):
    """잉크 한 방울: (x, y) 에 반지름 s 의 가우스."""
    i, j, r = (y + L) / (2 * L) * (G - 1), (x + L) / (2 * L) * (G - 1), max(s / (2 * L) * (G - 1), 0.6)
    R = int(3 * r) + 2; i0, i1, j0, j1 = max(0, int(i) - R), min(G, int(i) + R + 1), max(0, int(j) - R), min(G, int(j) + R + 1)
    if i0 >= i1 or j0 >= j1: return
    yy, xx = np.mgrid[i0:i1, j0:j1]; D[i0:i1, j0:j1] += w * np.exp(-((yy - i) ** 2 + (xx - j) ** 2) / (2 * r * r))

def ang(t, N): return np.pi / 2 - 2 * np.pi * t / N                     # 위에서 시작, 시계 방향
def wobble(n, amp=0.018):
    th = np.linspace(0, 2 * np.pi, n, endpoint=False); ph = rng.uniform(0, 2 * np.pi, 4)
    return amp * sum(np.sin(k * th + ph[k - 2]) / k for k in range(2, 6))

def ring(D, prof, N, R=1.0, base=0.010, gain=0.034, M=1500, gap=None):
    """굵기 prof(박) 의 잉크 고리. gap = 그리지 않을 박 구간(아직 안 쓴 곳)."""
    u = np.linspace(0, N, M, endpoint=False); th = np.interp(u, np.arange(N + 1), np.append(prof, prof[0])); wb = wobble(M)
    for k in range(M):
        if gap is not None and gap[0] <= u[k] < gap[1]: continue
        a, r = ang(u[k], N), R + wb[k]
        stamp(D, r * np.cos(a), r * np.sin(a), base + gain * th[k], 0.55)
        if rng.random() < 0.35:                                          # 번진 연기
            o = rng.normal(0, 0.03 + 0.04 * th[k]); stamp(D, (r + o) * np.cos(a), (r + o) * np.sin(a), 0.012 + 0.02 * rng.random(), 0.12)

def tendril(D, t, N, length, R=1.0, w0=0.022, curl=None, inward=False):
    curl = rng.uniform(-0.18, 0.18) if curl is None else curl
    for s in np.linspace(0, 1, 46):
        a = ang(t, N) + curl * s * s; r = R + (-1 if inward else 1) * length * s
        stamp(D, r * np.cos(a), r * np.sin(a), w0 * (1 - s) ** 1.2 + 0.003, 0.6)

def blob(D, t, N, size, R=1.0):
    a = ang(t, N); r = R - 0.06 - 0.5 * size
    for _ in range(6): stamp(D, r * np.cos(a) + rng.normal(0, size * 0.25), r * np.sin(a) + rng.normal(0, size * 0.25), size * 0.55, 0.5)

def module_marks(D, notes, N, gap=None):
    """notes = [(박, 음높이, 길이)] → 고리 굵기 + 촉수 + 덩이."""
    prof = np.zeros(N)
    for s, p, d in notes:
        for k in range(s, s + d): prof[k % N] += 1
    ring(D, gaussian_filter1d(prof / 4, 0.7, mode='wrap'), N, gap=gap)
    byt = {}
    for s, p, d in notes: byt.setdefault(s, []).append((p, d))
    for s, ns in byt.items():
        if gap is not None and gap[0] <= s < gap[1]: continue
        ns.sort(); top = [x for x in ns if x[0] >= 67]
        for k, (p, d) in enumerate(top): tendril(D, s + 0.25 * k, N, 0.10 + 0.032 * (p - 64), curl=0.06 * (k - 0.5))
        if len(ns) >= 3: blob(D, s, N, 0.025 + 0.012 * ns[0][1])          # 화음의 베이스

def shade(D, gain=1.6):
    I = 1 - np.exp(-gain * D)
    return PAPER[None, None] * (1 - I[..., None]) + INK[None, None] * I[..., None], I

def tint(img, mask, col, a=0.55):
    return img * (1 - a * mask[..., None]) + col[None, None] * (a * mask[..., None])

def sector(N, t0, t1, R0=0.78, R1=1.5):
    yy, xx = np.mgrid[0:G, 0:G]; x = xx / (G - 1) * 2 * L - L; y = yy / (G - 1) * 2 * L - L
    r = np.hypot(x, y); t = ((np.pi / 2 - np.arctan2(y, x)) % (2 * np.pi)) / (2 * np.pi) * N
    return ((t >= t0) & (t < t1) & (r > R0) & (r < R1)).astype(float)

O1, O2 = P.piece(P.IDENT)
mod = [(s, p, e - s) for s, p, e in O1 if s < 32]

# 가 쓰기 — 오른손 한 모듈
DA = np.zeros((G, G)); module_marks(DA, mod, 32); A, _ = shade(DA)

# 나 읽기 — 곡 전체, 두 가닥
N = 1089; prof = np.zeros((2, N)); on = {}
for h, inst in enumerate((O1, O2)):
    for s, p, e in inst: prof[h, s:e] += 1; on.setdefault((s, p), set()).add(h)
DB = np.zeros((G, G))
for h, R in ((0, 0.93), (1, 1.07)): ring(DB, gaussian_filter1d(prof[h] / 4, 3, mode='wrap'), N, R=R, base=0.006, gain=0.022, M=2600)
uni = sorted((s, p) for (s, p), hs in on.items() if len(hs) == 2)
for s, p in uni: tendril(DB, s, N, 0.06 + 0.018 * (p - 60), R=1.07, w0=0.010)
B, _ = shade(DB)

# 다 맞히기 — 들려준 문장 = 같은 재료의 변주, 나는 hibari 대로 24박까지 썼다
V1, _ = P.piece(P.turn(P.IDENT, 0, 1)); tgt = [(s, p, e - s) for s, p, e in V1 if s < 32]
by = lambda ns: {t: sorted((p, d) for s, p, d in ns if s == t) for t in range(32)}
bt, bm = by(tgt), by(mod); WRIT = 24
same = [t for t in range(WRIT) if bt[t] == bm[t]]; diff = [t for t in range(WRIT) if bt[t] != bm[t]]
DC = np.zeros((G, G)); module_marks(DC, mod, 32, gap=(WRIT, 32)); C, IC = shade(DC)
mg, mc = np.zeros((G, G)), np.zeros((G, G))
for t in same: mg = np.maximum(mg, sector(32, t, t + 1))
for t in diff: mc = np.maximum(mc, sector(32, t, t + 1))
C = tint(C, mg * np.clip(IC * 1.6, 0, 1), GREEN, 0.85); C = tint(C, mc * np.clip(IC * 1.6, 0, 1), CORAL, 0.9)
print(f'가 모듈 음 {len(mod)} · 나 두 손이 같은 박 같은 음 {len(uni)}번 · 다 쓴 박 {WRIT}: 맞음 {len(same)} · 틀림 {len(diff)} (틀린 박 {diff})')
half = sum(1 for s, p in uni if 33 + 15 * 33 <= s < 33 + 16 * 33)
print(f'   반 모듈(16박) 어긋난 모듈에서 같은 음 {half}번')

# ── 그림 ──────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(15.5, 6.2), facecolor=PAPER)
fig.suptitle('원형문자 × hibari — 세 가지 쓰임 (고르기 전 그림, 잉크는 전부 hibari 자료)', fontsize=14, color=INK, y=0.985)
for k, (img, ttl, sub) in enumerate([
        (A, '가  쓰기 — 한 모듈이 글자 하나', '종달새는 32박, 문어는 33박마다 같은 글자를 돈다\n촉수를 당기면 그 음이 오르고, 잉크를 굵히면 화음이 두꺼워진다'),
        (B, '나  읽기 — 곡 전체가 글자 하나', f'안쪽 가닥 오른손 · 바깥 가닥 왼손 · 촉수 = 두 손이 같은 음({len(uni)}번)\n처음과 끝이 맞닿는다 — 왼손이 한 모듈 다 밀리면 곡이 끝난다'),
        (C, '다  맞히기 — 들은 문장을 같게 쓰기', f'문장은 보이지 않고 들리기만 한다 · 맞은 박 초록 · 틀린 박 주황\n고리가 닫히고 다 초록이면 "통했다"')]):
    ax = fig.add_axes([0.01 + k * 0.33, 0.13, 0.31, 0.76]); ax.imshow(img, origin='lower', extent=[-L, L, -L, L]); ax.axis('off')
    ax.set_title(ttl, fontsize=12.5, color=INK, loc='left')
    fig.text(0.02 + k * 0.33, 0.035, sub, fontsize=10, color='#5d655f', va='bottom')
    if k == 0:
        for t, col, nm in ((5, GOLD, '종달새'), (4, CORAL, '문어')):
            a = ang(t, 32); r = 1.55 if nm == '종달새' else 1.42; ax.scatter([r * np.cos(a)], [r * np.sin(a)], s=60, color=col, zorder=3)
            ax.text(r * np.cos(a) + 0.08, r * np.sin(a), nm, color=col, fontsize=10, va='center')
    if k == 1:
        ax.annotate('처음 = 끝', (0, 1.12), (0.35, 1.55), color='#5d655f', fontsize=10, arrowprops=dict(arrowstyle='-', color='#9aa29b'))
        ax.annotate(f'반 모듈 어긋날 때 가장 많이 만난다 ({half}번)', (0, -1.25), (-1.6, -1.68), color='#5d655f', fontsize=10, arrowprops=dict(arrowstyle='-', color='#9aa29b'))
out = os.path.join(ROOT, 'docs', 'figures', 'logogram_views.png')
fig.savefig(out, dpi=105, facecolor=PAPER); print('저장', out)
