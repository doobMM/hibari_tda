"""
tools/group_g_views.py — 손짓 g(왼손 시계 한 칸 늦춤) 하나가 그림에서 보이는가: 같은 순간을 세 가지 그림으로 그려 원곡 | g 뒤 를 나란히 놓는다.
(2026-10-28 사용자: 시연 영상 demo_g.mp4 는 "그림이 안 예쁨 · 바뀐 게 안 보임", 군 방향은 유지 → 영상을 다시 짓기 전에 그림 셋 먼저.)

자료: hibari 두 손 = 같은 낱말(모듈 59음), 오른손 32칸 · 왼손 33칸(33박째 시작). 창 = 8분 515박째부터 44박(영상과 같은 대목).
  원곡: 두 손 같은 박 같은 음 = U0 · g 뒤(창 전체에 왼손 한 칸 늦춤): U1. 그림마다 같은 음 = 붉은 인주(朱) 획.
그림 셋 (모두 납작붓 LC.brush, 종이 위 먹 + 인주):
  가 펼친 두 줄 — 위 오른손 · 아래 왼손 선율을 가로로 쓴 먹 줄, 같은 음이면 두 줄을 잇는 인주 세로획(연결선).
  나 한 고리 — 창을 고리 하나로, 오른손 획은 바깥 · 왼손 획은 안쪽으로. 같은 음이면 두 획이 고리를 꿰뚫는 한 획으로 이어진다.
  다 두 먹 한 줄 — 두 손의 맨 윗음 선율을 같은 띠에 겹쳐 쓴다(오른손 먹 · 왼손 옅은 먹). 같은 음 자리에서 두 줄이 한 획으로 만난다.
검증 (CLAUDE.md 「검증기를 짓는 두 규칙」):
  증상 오라클 — 최종 그림에서 원곡 | g 뒤 픽셀이 얼마나 다른가(달라진 픽셀 몫) · 인주 픽셀 몫이 줄어드는가.
  양성 대조 — 'g 를 무시한 판'(늦춤을 넣지 않음)을 같은 판정기에 넣어 달라짐 0 → FAIL 이 나야 한다.
산출: docs/figures/group_g_views.png · docs/step3_data/group_g_views.json
"""
import os, sys, json
import numpy as np
from scipy.ndimage import gaussian_filter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'tools')]
import group_grammar as GG
import logogram_cosiatec as LC

T0, STEPS = 515, 44
R16, L16 = GG.voices('Ryuichi_Sakamoto_-_hibari.mid')
MOD = sorted((s // 2, p) for (s, p), d in R16 if s < 64)
HAND = {'R': (32, 0), 'L': (33, 33)}

def notes(shiftL):
    out = {}
    for h, (P, t0) in HAND.items():
        sh = shiftL if h == 'L' else 0
        out[h] = [(k, p) for k in range(STEPS) for s, p in MOD if s == (T0 + k - t0 - sh) % P]
    return out

def phrases(ks):                                                         # 이어진 박끼리 묶기
    out = []
    for k in ks:
        if out and k - out[-1][-1] == 1: out[-1].append(k)
        else: out.append([k])
    return [r for r in out if len(r) > 1]
def chord(ns, k): return sum(1 for kk, p in ns if kk == k)

def tops(ns):                                                            # 박마다 맨 윗음 (선율)
    d = {}
    for k, p in ns: d[k] = max(d.get(k, 0), p)
    return d

LC.G, LC.L = 640, 1.0
def canvas(): return np.zeros((LC.G, LC.G))
def br(F, path, w, press=None):
    """LC.brush 에 획 길이에 맞는 도장 수를 준다 — 기본 최소 40개는 짧은 획에 먹을 쌓아 덩어리로 만든다."""
    p = np.asarray(path, float); ln = np.hypot(*np.diff(p, axis=0).T).sum()
    LC.brush(F, p, w, press=press, n=max(6, int(ln / 0.004)))
def finish(ink, seal, pale=None):
    """먹(검정) · 옅은 먹(회색) · 인주(朱)를 종이에 얹는다."""
    G = LC.G; yy, xx = np.mgrid[0:G, 0:G]; r = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
    paper = np.array([241, 237, 228]) / 255 * (1 - 0.06 * r[..., None] ** 2)
    m = lambda F: np.flipud(np.clip((gaussian_filter(F, 1.0) - 0.2) / 0.06, 0, 1))[..., None]
    out = paper
    if pale is not None: out = out * (1 - 0.75 * m(pale)) + np.array([120, 116, 110]) / 255 * 0.75 * m(pale)
    out = out * (1 - m(ink)) + np.array([16, 16, 18]) / 255 * m(ink)
    return out * (1 - m(seal)) + np.array([196, 52, 36]) / 255 * m(seal)

def view_a(N):                                                           # 가 펼친 두 줄
    ink, seal = canvas(), canvas(); X = lambda k: -0.88 + 1.76 * k / (STEPS - 1)
    same = set(N['R']) & set(N['L'])
    for h, base, sg in (('R', 0.32, 1), ('L', -0.32, -1)):
        tp = tops(N[h]); ks = sorted(tp)
        for run in phrases(ks):                                          # 이어진 박 = 한 획, 쉼에서 붓을 뗀다 · 화음이면 눌러 쓴다
            br(ink, [(X(k), base + sg * 0.012 * (tp[k] - 70)) for k in run], 0.016, press=[0.6 + 0.12 * chord(N[h], k) for k in run])
    for k, p in same: br(seal, [(X(k), 0.22), (X(k) + 0.008, 0.0), (X(k), -0.22)], 0.008)
    return finish(ink, seal)

def view_b(N):                                                           # 나 한 고리
    ink, seal = canvas(), canvas(); A = lambda k: np.pi / 2 - 2 * np.pi * k / STEPS; R0 = 0.55
    th = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi * 0.985, 600)
    br(ink, np.c_[R0 * np.cos(th), R0 * np.sin(th)], 0.02)
    same = set(N['R']) & set(N['L'])
    for h, sg in (('R', 1), ('L', -1)):
        for k, p in tops(N[h]).items():
            a = A(k); ln = 0.06 + 0.011 * (p - 64)
            pts = [((R0 + sg * (0.02 + ln * t)) * np.cos(a - 0.04 * t), (R0 + sg * (0.02 + ln * t)) * np.sin(a - 0.04 * t)) for t in np.linspace(0, 1, 6)]
            br(seal if (k, p) in same else ink, pts, 0.011)
    for k, p in same:                                                    # 같은 음 = 고리를 꿰뚫는 한 획
        a = A(k); br(seal, [((R0 - 0.05) * np.cos(a), (R0 - 0.05) * np.sin(a)), ((R0 + 0.05) * np.cos(a), (R0 + 0.05) * np.sin(a))], 0.012)
    return finish(ink, seal)

def view_c(N):                                                           # 다 두 먹 한 줄
    ink, pale, seal = canvas(), canvas(), canvas(); X = lambda k: -0.88 + 1.76 * k / (STEPS - 1); Y = lambda p: 0.02 * (p - 74)
    same = set(N['R']) & set(N['L'])
    for h, F, w in (('R', ink, 0.014), ('L', pale, 0.024)):
        tp = tops(N[h]); ks = sorted(tp)
        for run in phrases(ks): br(F, [(X(k), Y(tp[k])) for k in run], w, press=[0.6 + 0.12 * chord(N[h], k) for k in run])
    for k, p in same: LC.stamp(seal, X(k), Y(p), 0.012, 1.0)
    return finish(ink, seal, pale)

def oracle(a, b):
    """증상 오라클: 달라진 픽셀 몫 · 인주 픽셀 몫(앞, 뒤). 인주 = 붉고 초록이 낮은 픽셀."""
    diff = float((np.abs(a - b).max(axis=2) > 0.15).mean())
    red = lambda x: float(((x[..., 0] - x[..., 1]) > 0.35).mean())
    return diff, red(a), red(b)

if __name__ == '__main__':
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    N0, N1 = notes(0), notes(1); U0, U1 = len(set(N0['R']) & set(N0['L'])), len(set(N1['R']) & set(N1['L']))
    print(f'두 손 같은 음: 원곡 {U0} · g 뒤 {U1}')
    VIEWS = [('가 펼친 두 줄', view_a), ('나 한 고리', view_b), ('다 두 먹 한 줄', view_c)]
    fig = plt.figure(figsize=(12, 18), facecolor='#efebe3'); rec = {}
    for i, (name, f) in enumerate(VIEWS):
        a, b = f(N0), f(N1); diff, r0, r1 = oracle(a, b)
        dnull, _, _ = oracle(a, f(notes(0)))                              # 양성 대조: g 를 무시한 판
        ok = diff > 0.002 and r1 < r0 and dnull <= 0.002 / 10
        rec[name] = {'changed_px_frac': round(diff, 5), 'seal_px_frac_before_after': [round(r0, 5), round(r1, 5)], 'null_changed_px_frac': round(dnull, 6), 'pass': ok}
        print(f'{name}: 달라진 픽셀 {diff:.2%} · 인주 {r0:.3%} → {r1:.3%} · g 무시한 판 {dnull:.4%} → {"통과" if ok else "실패"}')
        for j, (img, lab) in enumerate(((a, f'원곡 · 같은 음 {U0}'), (b, f'g 뒤 · 같은 음 {U1}'))):
            ax = fig.add_axes([0.02 + j * 0.49, 0.67 - i * 0.325, 0.47, 0.30]); ax.imshow(img); ax.axis('off')
            ax.set_title(f'{name} — {lab}', fontsize=12, color='#222', loc='left')
    fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'group_g_views.png'), dpi=90, facecolor='#efebe3')
    json.dump({'script': 'tools/group_g_views.py', 'window': [T0, STEPS], 'unison': [U0, U1], 'views': rec}, open(os.path.join(ROOT, 'docs', 'step3_data', 'group_g_views.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
