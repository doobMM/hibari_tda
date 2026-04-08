"""
Figure 4 — Persistence Barcode Diagram.
기존 pkl의 (cycle, birth, death) 기록으로 barcode 시각화.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def main():
    pkl_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'pickle', 'h1_rBD_t_notes1_1e-4_0.0~1.5.pkl'))
    df = pd.read_pickle(pkl_path)
    print(f"Loaded {len(df)} rows from {pkl_path}")
    print(df.head())

    # rate별로 각 cycle의 첫 birth, 마지막 death 집계
    rows = []
    for cycle_id, grp in df.groupby('cycle'):
        b = grp['birth'].min()
        d = grp['death'].max()
        rate_alive = grp['rate'].max()
        rows.append({'cycle': cycle_id, 'birth': b, 'death': d, 'lifespan': d - b})

    bars = pd.DataFrame(rows).sort_values('birth').reset_index(drop=True)
    n_bars = len(bars)
    print(f"Total cycles with persistence: {n_bars}")

    # 상위 30개만 (너무 많으면 난잡)
    display_n = min(30, n_bars)
    bars_show = bars.head(display_n)

    fig, ax = plt.subplots(figsize=(11, 7))
    fig.patch.set_facecolor('white')

    cmap = plt.cm.viridis
    for i, row in bars_show.iterrows():
        color = cmap(row['lifespan'] / bars_show['lifespan'].max())
        ax.barh(i, row['death'] - row['birth'], left=row['birth'],
                height=0.7, color=color, edgecolor='#2c3e50', linewidth=0.4)

    ax.set_xlabel('Rate parameter $r_t$  (filtration scale)',
                  fontsize=11, color='#2c3e50')
    ax.set_ylabel('Cycle index (sorted by birth time)',
                  fontsize=11, color='#2c3e50')
    ax.set_title('Figure 4. Persistence Barcode — hibari H$_1$ cycles\n'
                 '각 막대 = 한 cycle이 살아 있는 rate 구간 [birth, death]',
                 fontsize=12, color='#2c3e50', pad=12)

    ax.set_xlim(-0.02, max(0.5, bars_show['death'].max() * 1.05))
    ax.set_ylim(-0.8, display_n - 0.2)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # colorbar for lifespan
    sm = plt.cm.ScalarMappable(cmap=cmap,
        norm=plt.Normalize(vmin=bars_show['lifespan'].min(),
                           vmax=bars_show['lifespan'].max()))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('Lifespan  (death − birth)', fontsize=9, color='#2c3e50')

    # 오래 살아남은 cycle 표시
    long_lived = bars_show.nlargest(3, 'lifespan')
    for i, row in long_lived.iterrows():
        ax.text(row['death'] + 0.005, i, '★',
                va='center', fontsize=12, color='#e74c3c')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig4_barcode.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
