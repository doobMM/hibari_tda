"""
tools/arrival_hibari.py — 영화 『컨택트(Arrival)』 원형문자 원본 먹으로 hibari 를 쓴다.
(2026-10-28 사용자: "여전히 그림이 별로야. 실제로 arrival 영화에 나온 것을 그대로 바탕으로 하면 안 돼?")

원본: WolframResearch/Arrival-Movie-Live-Coding 의 ScriptLogoJpegs 38장 (3300px, CC BY-NC 4.0 — 출처 표기·비상업).
      output/arrival/ScriptLogoJpegs 에 둔다(gitignore). 그림을 새로 그리지 않고 원본 먹 픽셀을 자르고 붙인다.
방법 (Wolfram 라이브 코딩의 unwrap 을 그대로):
  1 원 맞추기 — 먹 픽셀에 원을 맞춘다(대수 원 맞춤 → 반지름 ±12% 안의 먹만 다시 맞춤, 3번).
  2 펼치기 — 극좌표 띠(각 1440칸 × 반지름 0.5R~1.7R 320칸)로. 고리 = 띠의 가로줄 r ≈ R.
  3 조각 — 띠를 45칸(한 모듈 칸 = 1/32 바퀴) 조각으로, 15칸씩 밀며 자른다. 조각마다 바깥 먹(r > 1.08R)·안쪽 먹(r < 0.92R)·바깥 최대 길이.
  4 고르기 — hibari 한 칸(8분 박)의 음: 쉼 → 맨 고리, 단음 → 바깥 촉수(길이 ∝ 음높이), 화음 → 바깥 덩이 + 안쪽(베이스).
     **같은 음 묶음 = 같은 조각**(규칙·정합성: 같은 소리는 어디서나 같은 먹 모양). 다른 음 묶음끼리는 조각이 겹치지 않게.
  5 감기 — 고른 조각을 n칸(오른손 32 · 왼손 33)으로 늘이고 줄여 다시 원으로 감는다. 이음매는 4칸 겹쳐 섞는다.
산출: docs/figures/arrival_hibari.png (+ output/arrival/*.png 낱장)
"""
import os, sys, glob, json
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, gaussian_filter, zoom
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'tools')]
import group_grammar as GG

SRC = os.path.join(ROOT, 'output', 'arrival', 'ScriptLogoJpegs')
NA, NR, R0, R1 = 1440, 320, 0.5, 1.7                                     # 띠: 각 칸 · 반지름 칸 · 반지름 범위(R 단위)
DS = 3                                                                   # 3300 → 1100px 로 줄여 맞춘다(띠는 원본에서 뽑는다)

def ink_of(path):
    return 1 - np.asarray(Image.open(path).convert('L'), np.float32) / 255

def fit_circle(ink):
    s = ink[::DS, ::DS]; y, x = np.nonzero(s > 0.5); x = x * DS; y = y * DS
    keep = np.ones(len(x), bool)
    for _ in range(3):
        A = np.c_[2 * x[keep], 2 * y[keep], np.ones(keep.sum())]; b = x[keep] ** 2 + y[keep] ** 2
        cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]; R = np.sqrt(c + cx ** 2 + cy ** 2)
        keep = np.abs(np.hypot(x - cx, y - cy) - R) < 0.12 * R
    return cx, cy, R

def unwrap(ink, cx, cy, R):
    th = np.linspace(0, 2 * np.pi, NA, endpoint=False); rr = np.linspace(R0, R1, NR) * R
    T, Rr = np.meshgrid(th, rr)                                          # 행 = 반지름(안 → 밖), 열 = 각(12시부터 시계 방향)
    X = cx + Rr * np.sin(T); Y = cy - Rr * np.cos(T)
    return map_coordinates(ink, [Y, X], order=1, cval=0.0)

def rewrap(strip, size, Rpx):
    """띠 → 원. size 정사각 그림, 고리 반지름 Rpx."""
    c = (size - 1) / 2; yy, xx = np.mgrid[0:size, 0:size]
    r = np.hypot(xx - c, yy - c) / Rpx; th = np.mod(np.arctan2(xx - c, -(yy - c)), 2 * np.pi)
    ri = (r - R0) / (R1 - R0) * (NR - 1); ti = th / (2 * np.pi) * NA
    out = map_coordinates(np.c_[strip, strip[:, :1]], [ri, ti], order=1, cval=0.0)
    return np.where((r >= R0) & (r <= R1), out, 0)

RING = slice(int((0.92 - R0) / (R1 - R0) * NR), int((1.08 - R0) / (R1 - R0) * NR))
OUT = slice(RING.stop, NR); INN = slice(0, RING.start)

def feats(p, nb):
    """조각 p → 칸 nb 개의 바깥 길이(촉수가 닿은 가장 먼 반지름) · 바깥 먹 · 안쪽 먹 · 고리 이어짐 · 양 끝 깨끗함."""
    out, inn = p[OUT] > 0.5, p[INN] > 0.5; cols = np.array_split(np.arange(p.shape[1]), nb)
    ext = np.array([(np.nonzero(out[:, c].any(axis=1))[0].max() + 1) / out.shape[0] if out[:, c].any() else 0 for c in cols])
    mass = np.array([out[:, c].mean() for c in cols]); im = np.array([inn[:, c].mean() for c in cols])
    ring = (p[RING].max(axis=0) > 0.4).mean(); e = 20
    ends = out[:, :e].mean() + out[:, -e:].mean() + inn[:, :e].mean() + inn[:, -e:].mean()
    return ext, mass, im, ring, ends

def corr(a, b):
    a, b = a - a.mean(), b - b.mean(); d = np.sqrt((a * a).sum() * (b * b).sum()); return float((a * b).sum() / d) if d > 0 else 0.0

def best_arc(strips, L, melody, exclude=(), step=12):
    """길이 L 칸 원본 호 중 바깥 길이가 선율 윤곽(박 쌍마다 맨 윗음)을 가장 닮고, 고리가 이어지고, 양 끝이 깨끗한 것."""
    best = None; m = np.asarray(melody, float)
    for li, s in enumerate(strips):
        for a in range(0, NA, step):
            if any(li == x and abs(((a - y + NA // 2) % NA) - NA // 2) < L for x, y in exclude): continue
            p = s[:, np.arange(a, a + L) % NA]; ext, mass, im, ring, ends = feats(p, len(m))
            if ring < 0.9 or mass.mean() < 0.04: continue
            sc = corr(ext, m) + 0.3 * corr(mass, np.ones_like(m) + 0.0 * m) + 0.6 * ring - 3 * ends
            if best is None or sc > best[0]: best = (sc, li, a)
    return best

def plain_arc(strips, L, step=12):
    """쉼 = 깨끗한 맨 고리: 바깥·안쪽 먹이 가장 적고 고리가 끊기지 않는 호."""
    best = None
    for li, s in enumerate(strips):
        for a in range(0, NA, step):
            p = s[:, np.arange(a, a + L) % NA]; ring = (p[RING].max(axis=0) > 0.4).mean()
            if ring < 0.99: continue
            sc = p[OUT].mean() + p[INN].mean()
            if best is None or sc < best[0]: best = (sc, li, a)
    return best

def compose(strips, segs, rot=0.0):
    """segs = [(원본 번호, 시작 칸, 원본 길이, 놓을 시작 칸, 놓을 길이)] — 늘여 붙이고 이음매는 ov 칸 섞는다. rot = 칸 단위 돌림(군 원소)."""
    out = np.zeros((NR, NA)); wsum = np.zeros(NA); ov = 10
    for li, a, Ls, d0, Ld in segs:
        p = strips[li][:, np.arange(a - ov, a + Ls + ov) % NA]
        p = zoom(p, (1, (Ld + 2 * ov) / p.shape[1]), order=1)
        cols = np.arange(int(round(d0 + rot)) - ov, int(round(d0 + rot)) - ov + p.shape[1]) % NA
        k = np.arange(p.shape[1]); ramp = np.clip(np.minimum(k + 1, p.shape[1] - k) / (2 * ov), 0, 1)
        np.add.at(out, (slice(None), cols), p * ramp); np.add.at(wsum, cols, ramp)
    return out / np.maximum(wsum, 1e-6)

def module_segs(arcs, P):
    """한 모듈(P 칸) = 구절 1 (0~11) · 쉼 · 구절 2 (16~27) · 쉼 (P = 33 이면 마지막 쉼이 한 칸 길다)."""
    c = NA / P; (ph1, ph2a, ph2b, rest) = arcs
    L1, h = 540, 270
    return [(ph1[1], ph1[2], L1, 0, 12 * c),
            (rest[1], rest[2], 180, 12 * c, 4 * c),
            (ph1[1], ph1[2], h, 16 * c, 6 * c),                          # 구절 2 앞 6박 = 구절 1 앞 6박과 같은 소리 → 같은 먹
            (ph2b[1], ph2b[2], h, 22 * c, 6 * c),
            (rest[1], rest[2], 180, 28 * c, (P - 28) * c)]

def paper(ink, size):
    yy, xx = np.mgrid[0:size, 0:size]; r = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
    bg = np.array([243, 240, 233]) / 255 * (1 - 0.05 * r[..., None] ** 2)
    a = np.clip(ink, 0, 1)[..., None]
    return bg * (1 - a) + np.array([14, 14, 16]) / 255 * a

if __name__ == '__main__':
    fs = sorted(glob.glob(os.path.join(SRC, '*.jpg'))); strips = []
    for f in fs:
        ink = ink_of(f); strips.append(unwrap(ink, *fit_circle(ink)))
    R16, L16 = GG.voices('Ryuichi_Sakamoto_-_hibari.mid')
    by = {}
    for (s_, p), d in R16:
        if s_ < 64: by.setdefault(s_ // 2, []).append(p)
    assert all(not by.get(j) for j in (*range(12, 16), *range(28, 32)))
    mel = lambda j0: [max(by[j0 + 2 * q] + by[j0 + 2 * q + 1]) for q in range(6)]   # 박 쌍(화음 + 단음)마다 맨 윗음
    ph1 = best_arc(strips, 540, mel(0))
    ph2b = best_arc(strips, 270, mel(16)[3:], exclude=[(ph1[1], ph1[2] + 270)])
    rest = plain_arc(strips, 180)
    arcs = (ph1, None, ph2b, rest); print('구절 1', fs[ph1[1]].split(os.sep)[-1], ph1[2], '· 구절 2 뒤', fs[ph2b[1]].split(os.sep)[-1], ph2b[2], '· 쉼', fs[rest[1]].split(os.sep)[-1], rest[2])
    S = 900
    imgR = rewrap(compose(strips, module_segs(arcs, 32)), S, S * 0.30)
    imgL = rewrap(compose(strips, module_segs(arcs, 33)), S, S * 0.30)
    imgLg = rewrap(compose(strips, module_segs(arcs, 33), rot=NA / 33), S, S * 0.30)
    for name, im in (('R', imgR), ('L', imgL), ('Lg', imgLg)):
        Image.fromarray((paper(im, S) * 255).astype(np.uint8)).save(os.path.join(ROOT, 'output', 'arrival', f'hibari_{name}.png'))
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    fig, ax = plt.subplots(1, 3, figsize=(18, 6.6), facecolor='#f3f0e9')
    for a_, im, t in zip(ax, (imgR, imgL, imgLg), ('오른손 한 모듈 (32칸)', '왼손 한 모듈 (같은 낱말 + 쉼 한 칸 = 33칸)', '왼손 g — 한 칸 돌림')):
        a_.imshow(paper(im, S)); a_.axis('off'); a_.set_title(t, fontsize=13, color='#222')
    fig.text(0.5, 0.02, '먹: Arrival 원형문자 원본 (WolframResearch/Arrival-Movie-Live-Coding, CC BY-NC 4.0)', ha='center', fontsize=9, color='#777')
    fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'arrival_hibari.png'), dpi=80, facecolor='#f3f0e9')
    nm = lambda t: [os.path.basename(fs[t[1]]), int(t[2])]
    json.dump({'script': 'tools/arrival_hibari.py', 'source': 'WolframResearch/Arrival-Movie-Live-Coding ScriptLogoJpegs (CC BY-NC 4.0)',
               'phrase1': nm(ph1), 'phrase2_tail': nm(ph2b), 'rest': nm(rest), 'melody_pairs': [mel(0), mel(16)]},
              open(os.path.join(ROOT, 'docs', 'step3_data', 'arrival_hibari.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
