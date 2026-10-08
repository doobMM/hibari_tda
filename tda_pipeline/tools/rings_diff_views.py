"""
tools/rings_diff_views.py — 고리판에서 조작한 곡이 원본과 '어떻게' 달라졌나를 한 눈에 보이는 그림 후보 셋 (2026-10-08 사용자 요청).
  "조작을 함으로써 원본과 어떤 식으로 달라지는지를 한 눈에 표현할 그림 같은 게 있으면 좋을 것 같아. 예를 들면 곡의 모양이 어떻게 바뀌는 지"

같은 조작 하나(기본: 라를 감싼 원 90°)를 세 가지로 그린다 — 고르기 전 시안이다(짓지 않는다).
  A 곡의 모양   shape/ 의 접기(experiments/song_fold.py)를 그대로: 원본 몸을 먼저 접고, 바꾼 곡은 **원본 몸에서 이어 접는다**(따뜻한 시작 —
               동적 그래프 그리기의 '머릿속 지도 보존'). 그래서 움직인 곳 = 음악이 바뀐 곳. 대조: 원본을 원본 몸에서 다시 접은 이동량(바닥).
  B 모듈 꽃     오른손 한 모듈 32박을 한 바퀴로(각 = 박, 반지름 = 음높이). 회색 = 원본, 색 = 바뀐 음.
  C 곡 전체 지도 곡 전체(34모듈)를 한 줄에 한 모듈씩 쌓은 표. 칸 색 = 그 박에서 원본과 다른 음 수(두 손). 오른손은 세로줄, 왼손은 한 박씩 밀려 비스듬한 줄.
곡 = hibari MIDI 의 박·길이 그대로, 음높이만 판 상태대로 (experiments/run_rings_h1_probe.py 의 piece()).
    python tools/rings_diff_views.py [고리 번호] [사분]  → docs/figures/rings_diff_views.png
"""
import sys, os, io, contextlib
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
import run_rings_h1_probe as P
import song_fold as SF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'; plt.rcParams['axes.unicode_minus'] = False

RING, K = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 1)
NAME = {8: '미를 감싼 원', 7: '미·도 허리 원', 6: '도를 감싼 원', 2: '파를 감싼 원', 1: '파·라 허리 원', 0: '라를 감싼 원',
        5: '솔을 감싼 원', 4: '솔·시 허리 원', 3: '시를 감싼 원'}[RING]
ST = P.turn(P.IDENT, RING, K)
O1, O2 = P.piece(P.IDENT); E1, E2 = P.piece(ST)
SPB = 60 / 66                                              # 1박 = 2 스텝(8분음표)

def song(i1, i2):
    v = [np.array(sorted((s / 2, (e - s) / 2, p, s / 2 * SPB, (e - s) / 2 * SPB, 80) for s, p, e in inst), float) for inst in (i1, i2)]
    return {'slug': 'rings', 'title': '', 'composer': '', 'voices': v, 'beats': float(max(x[:, 0].max() for x in v)), 'seconds': 0.0}

def fold_from(W, unit, ban, X0, iters=1500):
    """song_fold.fold 와 같은 결합·힘, 단 초기 자리 = X0 (스펙트럴 초기화 대신). 끝에 X0 쪽으로 회전만 맞춘다(Procrustes)."""
    p = dict(SF.DEF); T = len(W)
    rec, rsim, best = SF.knn(W, p['k'], p['thr'], ban)
    E = [(np.arange(T - 1), np.arange(1, T), np.full(T - 1, unit), np.full(T - 1, p['chain'])),
         (np.arange(T - 2), np.arange(2, T), np.full(T - 2, 1.94 * unit), np.full(T - 2, p['bend']))]
    g = (rsim - p['thr']) / (1 - p['thr']); E.append((rec[:, 0], rec[:, 1], p['rho'] * (1 - rsim), 0.15 + 0.85 * g * g))
    ei = np.concatenate([e[0] for e in E]).astype(np.int64); ej = np.concatenate([e[1] for e in E]).astype(np.int64)
    rest = np.concatenate([e[2] for e in E]).astype(np.float64); stiff = np.concatenate([e[3] for e in E]).astype(np.float64)
    nbl = [set() for _ in range(T)]
    for i, j in zip(ei, ej): nbl[i].add(int(j)); nbl[j].add(int(i))
    nb = np.full((T, max(len(x) for x in nbl)), -1, np.int64)
    for i, x in enumerate(nbl): nb[i, :len(x)] = sorted(x)
    X = np.ascontiguousarray(X0.copy()); pre = np.ones(T); np.add.at(pre, ei, stiff); np.add.at(pre, ej, stiff)
    Rw = p['wall'] * (0.239 * T * unit * p['rep_r'] ** 2) ** (1 / 3)
    for it in range(iters):
        mv = SF._step(X, ei, ej, rest, stiff, nb, p['rep_r'], p['rep_k'], p['grav'], 0.6, 0.3 * max(0.25, 1 - it / 1500), pre, Rw)
        if it > 200 and mv < p['tol']: break
    X -= X.mean(0); U, _, Vt = np.linalg.svd(X.T @ X0); R = U @ Vt
    return X @ R

so, se = song(O1, O2), song(E1, E2)
Wo, ns, unit, tt, ban = SF.features(so); We, *_ = SF.features(se)
with contextlib.redirect_stdout(io.StringIO()):
    X0, info, _ = SF.fold(Wo, unit, ban)
Xc = fold_from(Wo, unit, ban, X0)                         # 대조: 원본을 원본 몸에서 다시
Xe = fold_from(We, unit, ban, X0)
dc = np.linalg.norm(Xc - X0, axis=1); de = np.linalg.norm(Xe - X0, axis=1)
print(f'A 접기: 노드 {len(X0)} · 이동 중앙값 대조 {np.median(dc):.3f} / 바꾼 곡 {np.median(de):.3f} · 95% {np.percentile(dc, 95):.3f} / {np.percentile(de, 95):.3f}')

# B: 오른손 모듈 32박 (원곡 박 정렬: 오른손 0 에서 32 주기)
def module(i1):
    m = {}
    for s, p, e in i1:
        if s < 32: m.setdefault(s, []).append((p, e - s))
    return m
MO, ME = module(O1), module(E1)
# C: 곡 전체 박마다 원본과 다른 음 수 (두 손)
Tn = max(e for s, p, e in O1 + O2)
def onsets(i1, i2):
    d = {}
    for h, inst in enumerate((i1, i2)):
        for s, p, e in inst: d.setdefault(s, []).append((h, p, e - s))
    return d
DO, DE = onsets(O1, O2), onsets(E1, E2)
diff = np.zeros(Tn)
for t in range(Tn):
    a, b = sorted(DO.get(t, [])), sorted(DE.get(t, [])); diff[t] = len(set(a) ^ set(b)) / 2
rows = int(np.ceil(Tn / 32)); C = np.full((rows, 32), np.nan)
for t in range(Tn): C[t // 32, t % 32] = diff[t]
print(f'B 바뀐 오른손 스텝 {sum(1 for t in range(32) if sorted(MO.get(t, [])) != sorted(ME.get(t, [])))}/32 · C 다른 음이 있는 박 {(diff > 0).sum()}/{Tn}')

# ── 그림 ──────────────────────────────────────────────────────────────────
INK, DIM, GRAY, TEAL, CORAL, BG = '#22302a', '#7d877f', '#c9c5b8', '#1D9E75', '#D85A30', '#f3f0e6'
fig = plt.figure(figsize=(15, 5.6), facecolor=BG)
fig.suptitle(f'같은 조작 하나 — {NAME} 90° — 를 세 가지로', color=INK, fontsize=14, y=0.98)

# A
axA = fig.add_axes([0.01, 0.08, 0.32, 0.8]); axA.set_facecolor(BG); axA.axis('off')
sc = max(np.abs(X0[:, :2]).max(), 1e-9)
axA.plot(X0[:, 0] / sc - 1.05, X0[:, 1] / sc, color=GRAY, lw=0.8)
lim = np.percentile(dc, 99) * 1.5
mov = np.clip((de - lim) / (np.percentile(de, 99) - lim + 1e-9), 0, 1)
for i in range(len(Xe) - 1):
    c = matplotlib.colors.to_rgb(TEAL) if mov[i] < 0.05 else tuple(np.array(matplotlib.colors.to_rgb(TEAL)) * (1 - mov[i]) + np.array(matplotlib.colors.to_rgb(CORAL)) * mov[i])
    axA.plot(Xe[i:i + 2, 0] / sc + 1.05, Xe[i:i + 2, 1] / sc, color=c, lw=0.6 + 1.4 * mov[i])
axA.text(-1.05, -1.25, '원본의 몸', ha='center', color=DIM, fontsize=10); axA.text(1.05, -1.25, '바꾼 곡의 몸 (주황 = 움직인 곳)', ha='center', color=DIM, fontsize=10)
axA.set_xlim(-2.2, 2.2); axA.set_ylim(-1.4, 1.2); axA.set_aspect('equal')
axA.set_title('A  곡의 모양 — 원본 몸에서 이어 접기', color=INK, fontsize=12, loc='left')

# B
axB = fig.add_axes([0.36, 0.08, 0.27, 0.8], projection='polar'); axB.set_facecolor(BG)
axB.set_theta_zero_location('N'); axB.set_theta_direction(-1); axB.set_yticks([]); axB.set_xticks([]); axB.spines['polar'].set_color(GRAY)
r = lambda p: (p - 46) / 40
for t in range(32):
    th = 2 * np.pi * t / 32; ch = sorted(MO.get(t, [])) != sorted(ME.get(t, []))
    if ch: axB.bar(th, 1.0, width=2 * np.pi / 32, bottom=0.05, color=CORAL, alpha=0.10, edgecolor='none')
    for p, d in MO.get(t, []): axB.scatter([th], [r(p)], s=22, color=GRAY, zorder=2)
    for p, d in ME.get(t, []):
        new = (p, d) not in MO.get(t, [])
        axB.scatter([th], [r(p)], s=30 if new else 10, color=CORAL if new else TEAL, zorder=3)
def top(m): return [r(max(p for p, d in m[t])) if t in m else 0.08 for t in range(32)] + [r(max(p for p, d in m[0]))]
ths = [2 * np.pi * t / 32 for t in range(33)]
axB.plot(ths, top(MO), color=GRAY, lw=1.2); axB.plot(ths, top(ME), color=TEAL, lw=1.4)
axB.set_ylim(0, 1.0)
axB.set_title('B  모듈 꽃 — 32박 한 바퀴, 바깥 = 높은 음', color=INK, fontsize=12, loc='left', pad=14)

# C
axC = fig.add_axes([0.67, 0.12, 0.31, 0.74]); axC.set_facecolor(BG)
cm = matplotlib.colors.LinearSegmentedColormap.from_list('d', ['#fbf9f2', '#f2c7a8', CORAL])
axC.imshow(C, aspect='auto', cmap=cm, vmin=0, vmax=max(1, np.nanmax(C)), interpolation='nearest')
axC.set_xlabel('모듈 안의 박 (0 → 31)', color=DIM, fontsize=10); axC.set_ylabel('모듈 (위 → 아래로 시간)', color=DIM, fontsize=10)
axC.tick_params(colors=DIM, labelsize=8)
for s in axC.spines.values(): s.set_color(GRAY)
axC.set_title('C  곡 전체 지도 — 진할수록 원본과 다른 음이 많다', color=INK, fontsize=12, loc='left')
out = os.path.join(ROOT, 'docs', 'figures', 'rings_diff_views.png')
fig.savefig(out, dpi=110, facecolor=BG); print('저장', out)
