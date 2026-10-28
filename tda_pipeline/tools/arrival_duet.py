"""
tools/arrival_duet.py — 두 손을 한 원형문자에 겹치고 손짓 g 를 건다 (원본 Arrival 먹, tools/arrival_hibari.py 가 고른 호 그대로).
(2026-10-28 사용자: "응, 두 손 겹쳐서 g 걸어 보여줘")

겹치는 규칙: 두 고리를 같은 반지름에 겹치고, 각 손이 **지금 읽는 칸**이 12시 바늘에 오게 돌린다(오른손 32칸 · 왼손 33칸).
  오른손 = 짙은 먹, 왼손 = 따뜻한 옅은 먹. 두 손의 같은 먹이 같은 자리에 오면 한 획으로 겹쳐 보인다.
순간: 8분 530박째 — 오른손 18칸(구절 2 의 3박째) · 왼손 2칸(구절 1 의 3박째). 반 모듈 어긋난 대목이고,
  구절 2 앞 6박 = 구절 1 앞 6박(같은 소리 → 같은 먹)이라 바늘 둘레에서 두 손의 먹이 포개진다(곡에서 같은 음이 가장 몰리는 곳).
g = 왼손 시계 한 칸 늦춤(왼손 고리를 1/33 바퀴 돌림) · g⁻¹ = 되돌림.
검증(CLAUDE.md 「검증기를 짓는 두 규칙」): 증상 오라클 = 최종 그림에서 달라진 픽셀 몫 · 두 먹 포갬 몫(Σmin / Σmax, 바늘 둘레 ±60°) ·
  양성 대조 = g 를 무시한 판은 달라짐 0, g·g⁻¹ 판은 원곡과 같아야 한다.
산출: docs/figures/arrival_duet.png · docs/step3_data/arrival_duet.json
"""
import os, sys, glob, json
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'tools')]
import arrival_hibari as AH

T, S = 530, 900
J = json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'arrival_hibari.json'), encoding='utf8'))
fs = sorted(glob.glob(os.path.join(AH.SRC, '*.jpg'))); names = [os.path.basename(f) for f in fs]
strips = [AH.unwrap(ink, *AH.fit_circle(ink)) for ink in map(AH.ink_of, fs)]
arc = lambda k: (0, names.index(J[k][0]), J[k][1])
ARCS = (arc('phrase1'), None, arc('phrase2_tail'), arc('rest'))

def ring(P, cell):
    """P 칸 고리를 칸 cell 의 가운데가 12시에 오게 돌려 감는다."""
    return np.clip(AH.rewrap(AH.compose(strips, AH.module_segs(ARCS, P), rot=-(cell + 0.5) * AH.NA / P), S, S * 0.30), 0, 1)

def duet(lag):
    cR, cL = T % 32, (T - 33 - lag) % 33
    return ring(32, cR), ring(33, cL), (cR, cL)

def paint(aR, aL):
    """두 손이 포갠 먹 = 검정 · 오른손만 = 푸른 먹 · 왼손만 = 따뜻한 먹. 포개지면 한 글자, 어긋나면 두 색 테가 갈라진다."""
    yy, xx = np.mgrid[0:S, 0:S]; r = np.hypot(xx - S / 2, yy - S / 2) / (S / 2)
    out = np.array([243, 240, 233]) / 255 * (1 - 0.05 * r[..., None] ** 2)
    both = np.minimum(aR, aL); onlyR, onlyL = aR - both, aL - both
    for a, col in ((onlyL, (168, 118, 82)), (onlyR, (58, 74, 96)), (both, (12, 12, 14))):
        out = out * (1 - a[..., None]) + np.array(col) / 255 * a[..., None]
    n0, n1 = int(S / 2 - S * 0.30 * 1.62), int(S / 2 - S * 0.30 * 1.52)
    out[n0:n1, S // 2 - 2:S // 2 + 2] = np.array([180, 50, 34]) / 255                                 # 12시 바늘
    return out

def overlap(aR, aL):
    yy, xx = np.mgrid[0:S, 0:S]; th = np.arctan2(xx - S / 2, -(yy - S / 2)); m = np.abs(th) < np.pi / 3
    return float(np.minimum(aR, aL)[m].sum() / max(np.maximum(aR, aL)[m].sum(), 1e-9))

if __name__ == '__main__':
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    panels = [('원곡', 0), ('g — 왼손 한 칸 늦춤', 1), ('g 의 역원 — 되돌림', 0)]
    imgs, rec = [], []
    for name, lag in panels:
        aR, aL, cells = duet(lag); img = paint(aR, aL); imgs.append(img)
        rec.append({'panel': name, 'cells_RL': cells, 'overlap_near_needle': round(overlap(aR, aL), 4)})
    nul = paint(*duet(0)[:2])                                            # 양성 대조: g 를 무시한 판
    diff = lambda a, b: float((np.abs(a - b).max(axis=2) > 0.15).mean())
    ora = {'changed_px_g': round(diff(imgs[0], imgs[1]), 4), 'changed_px_g_inverse_vs_original': round(diff(imgs[0], imgs[2]), 6),
           'changed_px_null': round(diff(imgs[0], nul), 6)}
    ora['pass'] = ora['changed_px_g'] > 0.005 and ora['changed_px_null'] == 0 and ora['changed_px_g_inverse_vs_original'] == 0 and rec[1]['overlap_near_needle'] < rec[0]['overlap_near_needle']
    print(rec, ora)
    fig, ax = plt.subplots(2, 3, figsize=(18, 12.6), facecolor='#f3f0e9', gridspec_kw={'height_ratios': [1, 0.62]})
    z0, z1, w0 = int(S * 0.02), int(S * 0.36), int(S * 0.22)             # 아래 줄 = 바늘 둘레 확대
    for k, (img, (name, lag), r) in enumerate(zip(imgs, panels, rec)):
        ax[0, k].imshow(img); ax[0, k].axis('off'); ax[0, k].set_title(f'{name}   (바늘 둘레 두 먹 포갬 {r["overlap_near_needle"]:.0%})', fontsize=13, color='#222')
        ax[1, k].imshow(img[z0:z1, w0:S - w0]); ax[1, k].axis('off')
    fig.text(0.5, 0.035, '검정 = 두 손 먹이 포갬 · 푸른 먹 = 오른손만(32칸) · 갈색 먹 = 왼손만(33칸) · 붉은 바늘 = 지금 읽는 칸 · 8분 530박째', ha='center', fontsize=11, color='#444')
    fig.text(0.5, 0.01, '먹: Arrival 원형문자 원본 (WolframResearch/Arrival-Movie-Live-Coding, CC BY-NC 4.0)', ha='center', fontsize=9, color='#777')
    fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'arrival_duet.png'), dpi=80, facecolor='#f3f0e9')
    json.dump({'script': 'tools/arrival_duet.py', 'moment_8th': T, 'panels': rec, 'oracle': ora},
              open(os.path.join(ROOT, 'docs', 'step3_data', 'arrival_duet.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
