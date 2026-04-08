"""
Figure 4 — Persistence Barcode Diagram.
기존 pkl의 (cycle, birth, death) 기록으로 barcode 시각화.

개선사항:
- 7개의 "영속 cycle" (death = 10001)은 death를 rate 최대값 1.5로 capping
- 전체 48개 cycle 모두 표시
- lifespan 기준 내림차순 정렬 → 위쪽에 긴 cycle
- 영속 cycle은 우측에 화살표로 "→ ∞" 표시
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

RATE_MAX = 1.5  # 탐색 상한

def main():
    pkl_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'pickle', 'h1_rBD_t_notes1_1e-4_0.0~1.5.pkl'))
    df = pd.read_pickle(pkl_path)
    print(f"Loaded {len(df)} rows from {pkl_path}")

    # per cycle birth / death 집계
    rows = []
    for cycle_id, grp in df.groupby('cycle'):
        b = grp['birth'].min()
        d = grp['death'].max()
        rows.append({'cycle': cycle_id, 'birth': b, 'death': d})

    bars = pd.DataFrame(rows)
    # 10001 같은 infty placeholder를 RATE_MAX + 작은 여유로 clip
    EPS = 0.0
    bars['infinite'] = bars['death'] >= RATE_MAX * 2  # 영속 여부 플래그
    bars.loc[bars['infinite'], 'death'] = RATE_MAX + EPS
    bars['lifespan_vis'] = bars['death'] - bars['birth']

    # lifespan 기준 내림차순 정렬
    bars = bars.sort_values('lifespan_vis', ascending=False).reset_index(drop=True)
    n_bars = len(bars)
    print(f"Total cycles: {n_bars},  infinite: {bars['infinite'].sum()}")

    fig, ax = plt.subplots(figsize=(12, 9))
    fig.patch.set_facecolor('white')

    cmap_finite = plt.cm.viridis
    max_finite_life = bars[~bars['infinite']]['lifespan_vis'].max()

    for i, row in bars.iterrows():
        if row['infinite']:
            color = '#e74c3c'  # 빨강 — 영속 cycle
        else:
            t = row['lifespan_vis'] / max_finite_life if max_finite_life > 0 else 0
            color = cmap_finite(t)
        # y는 위에서부터(긴 cycle이 위)
        y = n_bars - 1 - i
        width = row['death'] - row['birth']
        ax.barh(y, width, left=row['birth'], height=0.72,
                color=color, edgecolor='#2c3e50', linewidth=0.4)
        # 영속 cycle 화살표
        if row['infinite']:
            ax.annotate('∞', xy=(RATE_MAX + 0.01, y), xytext=(RATE_MAX + 0.05, y),
                        ha='left', va='center', fontsize=12, color='#c0392b',
                        fontweight='bold')

    ax.set_xlabel('Rate parameter $r_t$  (filtration scale)',
                  fontsize=12, color='#2c3e50')
    ax.set_ylabel('Cycle index (sorted by lifespan, top = longest)',
                  fontsize=12, color='#2c3e50')
    ax.set_title('Figure 4. Persistence Barcode — hibari H$_1$ cycles (모든 48개)\n'
                 '빨강 = 탐색 구간 $[0, 1.5]$ 내에서 소멸하지 않은 영속 cycle\n'
                 'viridis = 유한 lifespan에 비례 (보라 → 노랑)',
                 fontsize=11, color='#2c3e50', pad=12)

    ax.set_xlim(-0.03, RATE_MAX + 0.2)
    ax.set_ylim(-0.8, n_bars - 0.2)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # 영속/유한 범례
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor='#e74c3c', edgecolor='#2c3e50',
              label=f'영속 cycle ({int(bars["infinite"].sum())}개)'),
        Patch(facecolor=cmap_finite(0.9), edgecolor='#2c3e50',
              label='유한 cycle (lifespan 긴 쪽)'),
        Patch(facecolor=cmap_finite(0.1), edgecolor='#2c3e50',
              label='유한 cycle (lifespan 짧은 쪽)'),
    ]
    ax.legend(handles=legend_elems, loc='lower right',
              fontsize=9, framealpha=0.95)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig4_barcode.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
