"""
gen_summary3_figures.py — 연구요약_3장.md 용 비전공자 친화 그림 4종
===================================================================

1. summary3_cycle.png    — 음 조각들을 실로 잇다 보면 고리가 나타난다 (1장)
2. summary3_om.png       — 실제 hibari 중첩행렬 = 곡의 구조 설계도 (2장, 실데이터)
3. summary3_songs.png    — 3곡 비교: 고리 수·밀도 (3장, 발견 2)
4. summary3_knob.png     — 닮음의 손잡이: 방법 A vs B (3장, 발견 1)

팔레트: 괴물(2023) 그린 — #3a8f3d(풀잎) #6cc24a(새싹) #dba93f(햇살) #22331f(숲그늘)
실행: python docs/figures/gen_summary3_figures.py  (tda_pipeline 루트 기준)
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

import _fontsetup  # noqa: F401 — 한글 폰트 설정 (같은 폴더)

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
TDA = os.path.dirname(DOCS)

GRASS = '#3a8f3d'
SPROUT = '#6cc24a'
SUN = '#dba93f'
INK = '#22331f'
DIM = '#7a9070'
PAPER = '#f7faf1'

plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['savefig.facecolor'] = 'white'


# ── 1. 고리 발견 일러스트 ────────────────────────────────────────────────
def fig_cycle():
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.2))
    rng = np.random.default_rng(7)

    # 고리를 이룰 6점 + 바깥 3점 (모든 패널 동일 좌표)
    ang = np.linspace(0, 2 * np.pi, 7)[:-1] - np.pi / 2
    ring = np.c_[0.42 + 0.26 * np.cos(ang), 0.52 + 0.30 * np.sin(ang)]
    ring += rng.normal(0, 0.012, ring.shape)
    outs = np.array([[0.86, 0.72], [0.92, 0.42], [0.80, 0.18]])
    pts = np.vstack([ring, outs])

    titles = ['① 음 조각들 (23개 중 일부)',
              '② 가까운 것끼리 실로 잇는다',
              '③ 닫힌 길 = 고리(cycle) 발견!']

    for k, ax in enumerate(axes):
        ax.set_xlim(0, 1.05); ax.set_ylim(0, 1)
        ax.set_facecolor(PAPER)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color('#d7e3c8')
        ax.set_title(titles[k], fontsize=11, color=INK, pad=8)

        if k >= 1:  # 이웃 잇기 (고리 일부 + 바깥 점 한둘)
            for i in range(6):
                j = (i + 1) % 6
                n = 4 if k == 1 else 6          # ②에서는 아직 안 닫힘
                if i < n:
                    ax.plot(*zip(ring[i], ring[j]), color=SPROUT,
                            lw=2, alpha=0.85, zorder=1)
            ax.plot(*zip(outs[0], outs[1]), color=SPROUT, lw=1.4,
                    alpha=0.5, zorder=1)
        if k == 2:  # 닫힌 고리 강조
            loop = plt.Polygon(ring, closed=True, fill=True,
                               facecolor=SPROUT, alpha=0.18,
                               edgecolor=GRASS, lw=3, zorder=0)
            ax.add_patch(loop)
            ax.text(0.42, 0.52, '고리', ha='center', va='center',
                    fontsize=13, color=GRASS, fontweight='bold')

        ax.scatter(pts[:, 0], pts[:, 1], s=140, color=GRASS,
                   edgecolor='white', lw=1.5, zorder=3)
        # 음표 기호 살짝
        for (x, y) in pts:
            ax.text(x, y, '♪', ha='center', va='center',
                    fontsize=8, color='white', zorder=4)

    fig.tight_layout()
    out = os.path.join(HERE, 'summary3_cycle.png')
    fig.savefig(out, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('saved', out)


# ── 2. 실제 hibari 중첩행렬 (구조 설계도) ────────────────────────────────
def fig_om():
    ref_path = os.path.join(TDA, 'hibari_dashboard', 'data',
                            'overlap_matrix_reference.json')
    with open(ref_path, encoding='utf-8') as f:
        d = json.load(f)
    T, K = d['T'], d['K']
    om = np.array(d['values'], dtype=float).reshape(T, K).T   # (K, T)

    fig, ax = plt.subplots(figsize=(9.6, 2.6))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list('grass', ['#eef4e2', GRASS])
    ax.imshow(om, aspect='auto', cmap=cmap, interpolation='nearest')
    ax.set_xlabel('시간 →  (9분, 1,088칸)', fontsize=10, color=INK)
    ax.set_ylabel('고리 14개', fontsize=10, color=INK)
    ax.set_yticks([0, 13]); ax.set_yticklabels(['1번', '14번'], fontsize=8)
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_color('#b9cda3')
    ax.set_title('hibari의 구조 설계도 (중첩행렬) — 초록 칸 = 그 고리가 깨어 있는 순간',
                 fontsize=11, color=INK, pad=8)
    fig.tight_layout()
    out = os.path.join(HERE, 'summary3_om.png')
    fig.savefig(out, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('saved', out)


# ── 3. 3곡 비교 ──────────────────────────────────────────────────────────
def fig_songs():
    songs = ['hibari', 'solari', 'aqua']
    Ks = [14, 25, 82]
    dens = ['34%', '4.3%', '1.3%']
    scales = ['7음계 (단순)', '12음계', '12음계 (가장 풍부)']
    colors = [SPROUT, '#58a83c', GRASS]

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bars = ax.bar(songs, Ks, width=0.52, color=colors, zorder=3)
    for b, k, dn, sc in zip(bars, Ks, dens, scales):
        ax.text(b.get_x() + b.get_width() / 2, k + 2.5, f'고리 {k}개',
                ha='center', fontsize=11, color=INK, fontweight='bold')
        ax.text(b.get_x() + b.get_width() / 2, -9.5, f'밀도 {dn}\n{sc}',
                ha='center', va='top', fontsize=9, color=DIM)
    ax.set_ylim(0, 95)
    ax.set_yticks([])
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color('#b9cda3')
    ax.set_title('곡이 복잡해질수록 — 고리는 많아지고, 밀도는 성겨진다',
                 fontsize=12, color=INK, pad=10)
    ax.margins(y=0.12)
    fig.subplots_adjust(bottom=0.28)
    out = os.path.join(HERE, 'summary3_songs.png')
    fig.savefig(out, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('saved', out)


# ── 4. 닮음의 손잡이 ─────────────────────────────────────────────────────
def fig_knob():
    fig, ax = plt.subplots(figsize=(8.6, 2.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3)
    ax.axis('off')

    # 축
    ax.add_patch(FancyArrowPatch((0.6, 1.2), (9.4, 1.2),
                                 arrowstyle='<|-|>', mutation_scale=18,
                                 color='#b9cda3', lw=2.5))
    ax.text(0.6, 0.62, '원곡 복사\n(똑같음)', ha='left', fontsize=10, color=DIM)
    ax.text(9.4, 0.62, '완전히 새로움\n(구조도 사라짐)', ha='right',
            fontsize=10, color=DIM)

    # 방법 B — 원곡 매우 근접
    ax.scatter([1.7], [1.2], s=330, color=SUN, zorder=3,
               edgecolor='white', lw=2)
    ax.text(1.7, 1.78, '방법 B (신경망)\n차이 0.00035', ha='center',
            fontsize=9.5, color=INK)

    # 방법 A — 중간
    ax.scatter([4.1], [1.2], s=330, color=GRASS, zorder=3,
               edgecolor='white', lw=2)
    ax.text(4.1, 1.78, '방법 A (주사위)\n차이 0.009', ha='center',
            fontsize=9.5, color=INK)

    # 목표 영역
    ax.axvspan(3.0, 6.4, ymin=0.28, ymax=0.55, color=SPROUT, alpha=0.16)
    ax.text(5.2, 0.62, '목표 지대: "비슷한 느낌의 다른 공간"', ha='center',
            fontsize=10, color=GRASS, fontweight='bold')

    ax.set_title('닮음의 손잡이 — 두 방법은 손잡이의 다른 위치에 있다',
                 fontsize=12, color=INK, pad=6)
    fig.tight_layout()
    out = os.path.join(HERE, 'summary3_knob.png')
    fig.savefig(out, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('saved', out)


if __name__ == '__main__':
    fig_cycle()
    fig_om()
    fig_songs()
    fig_knob()
    print('완료 — 4개 그림 생성')
