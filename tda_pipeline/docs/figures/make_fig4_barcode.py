"""
Figure 4 — Persistence Barcode Diagram (frequency distance).

데이터 출처: pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl
이 pkl은 h1 차원, timeflow 가중치, frequency 거리(metric 표시 없음 = default),
tolerance 1e-4, rate 범위 [0, 1.5]로 계산된 결과이다. Tonnetz 등 다른
거리 함수의 barcode는 별도로 계산되어 cache/metric_*.pkl에 들어 있다.

개선사항 (v4):
- 두 panel:
  (a) 전체 barcode (48개) — 11개의 영속 cycle을 한눈에
  (b) 유한 37개 cycle만 zoom — 짧은 lifespan 차이 식별 가능
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd

RATE_MAX = 1.5

def main():
    pkl_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'pickle', 'h1_rBD_t_notes1_1e-4_0.0~1.5.pkl'))
    df = pd.read_pickle(pkl_path)

    rows = []
    for cid, grp in df.groupby('cycle'):
        rows.append({'cycle': cid,
                     'birth': grp['birth'].min(),
                     'death': grp['death'].max()})
    bars = pd.DataFrame(rows)

    bars['beyond'] = bars['death'] > RATE_MAX
    bars['death_vis'] = bars['death'].clip(upper=RATE_MAX)
    bars['lifespan_vis'] = bars['death_vis'] - bars['birth']
    bars['true_lifespan'] = bars['death'] - bars['birth']

    bars = bars.sort_values(['beyond', 'lifespan_vis'],
                            ascending=[False, False]).reset_index(drop=True)
    n_bars = len(bars)
    n_beyond = int(bars['beyond'].sum())

    finite = bars[~bars['beyond']].reset_index(drop=True)
    n_finite = len(finite)
    finite_max_life = finite['true_lifespan'].max()
    finite_min_life = finite['true_lifespan'].min()
    print(f"Total {n_bars}, beyond {n_beyond}, finite {n_finite}")
    print(f"Finite lifespan range: {finite_min_life:.5f} – {finite_max_life:.5f}")

    fig = plt.figure(figsize=(13, 10))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.3], hspace=0.32)

    color_beyond = '#e74c3c'
    color_finite = '#3498db'

    # ─── Panel (a): full barcode ───
    ax_a = fig.add_subplot(gs[0])
    for i, row in bars.iterrows():
        color = color_beyond if row['beyond'] else color_finite
        y = n_bars - 1 - i
        width = row['death_vis'] - row['birth']
        ax_a.barh(y, width, left=row['birth'], height=0.72,
                  color=color, edgecolor='#2c3e50', linewidth=0.4)
        if row['beyond']:
            ax_a.annotate('∞', xy=(RATE_MAX + 0.005, y),
                          ha='left', va='center', fontsize=12,
                          color='#c0392b', fontweight='bold')

    if 0 < n_beyond < n_bars:
        boundary_y = n_bars - n_beyond - 0.5
        ax_a.axhline(y=boundary_y, color='#7f8c8d',
                     linestyle=':', linewidth=1.0, alpha=0.6)

    ax_a.set_xlabel('Rate parameter $r_t$', fontsize=11, color='#2c3e50')
    ax_a.set_ylabel('Cycle index (lifespan ↓)', fontsize=11, color='#2c3e50')
    ax_a.set_title('(a) 전체 48개 cycle — 빨강 11개는 탐색 범위 $[0, 1.5]$를 벗어남,'
                   ' 파랑 37개는 범위 내 유한 cycle (대부분 매우 짧아 거의 점처럼 보임)',
                   fontsize=11, color='#2c3e50', loc='left', pad=8)
    ax_a.set_xlim(-0.03, RATE_MAX + 0.18)
    ax_a.set_ylim(-0.8, n_bars - 0.2)
    ax_a.grid(axis='x', alpha=0.3, linestyle='--')
    ax_a.spines['top'].set_visible(False)
    ax_a.spines['right'].set_visible(False)

    # ─── Panel (b): finite-only zoom ───
    ax_b = fig.add_subplot(gs[1])

    # x축을 finite cycle의 실제 lifespan 범위에 맞춰 zoom
    fin_x_min = max(0, finite['birth'].min() - 0.001)
    fin_x_max = finite['death'].max() * 1.05
    print(f"Zoom x range: [{fin_x_min:.5f}, {fin_x_max:.5f}]")

    finite_sorted = finite.sort_values('true_lifespan',
                                        ascending=False).reset_index(drop=True)
    # 색을 lifespan에 비례시켜 viridis 사용 (여기서는 cycle 간 차이가 보이므로 OK)
    cmap = plt.cm.viridis
    norms = (finite_sorted['true_lifespan'] - finite_min_life) / max(
        finite_max_life - finite_min_life, 1e-9)

    for i, row in finite_sorted.iterrows():
        y = n_finite - 1 - i
        color = cmap(0.2 + 0.7 * norms.iloc[i])  # 0.2~0.9 range
        ax_b.barh(y, row['death'] - row['birth'], left=row['birth'],
                  height=0.72, color=color, edgecolor='#2c3e50', linewidth=0.5)
        # cycle id 일부 표시 (lifespan 긴 상위 5개만)
        if i < 5:
            ax_b.text(row['death'] + 0.0003, y, str(row['cycle'])[:30] + '..',
                      va='center', fontsize=7, color='#555')

    ax_b.set_xlabel('Rate parameter $r_t$  (zoom)', fontsize=11, color='#2c3e50')
    ax_b.set_ylabel('Cycle index (lifespan ↓)', fontsize=11, color='#2c3e50')
    ax_b.set_title(f'(b) 유한 37개 cycle만 zoom — lifespan 범위 '
                   f'$[{finite_min_life:.4f}, {finite_max_life:.4f}]$, '
                   '색은 lifespan에 비례 (viridis)',
                   fontsize=11, color='#2c3e50', loc='left', pad=8)
    ax_b.set_xlim(fin_x_min, fin_x_max)
    ax_b.set_ylim(-0.8, n_finite - 0.2)
    ax_b.grid(axis='x', alpha=0.3, linestyle='--')
    ax_b.spines['top'].set_visible(False)
    ax_b.spines['right'].set_visible(False)

    fig.suptitle('Figure 4. Persistence Barcode — hibari $H_1$ cycles\n'
                 '(frequency distance, timeflow weight, $r_t \\in [0, 1.5]$)',
                 fontsize=13, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig4_barcode.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
