"""
Figure 4 — Persistence Barcode Diagram.
탐색 구간 [0, 1.5] 내에서 살아있는 cycle을 시각화.

개선사항 (v3):
- 탐색 상한 1.5를 넘어가는 모든 cycle (총 11개)을 일관되게 "탐색 범위 초과"로 처리
- 두 가지 색만 사용 (빨강 = 범위 초과, 파랑 = 범위 내 소멸) — viridis gradient 제거
- xlim을 1.5 + 작은 여유로 정확히 자름
- 범위 초과 cycle은 우측 끝에 ∞ 표기
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

RATE_MAX = 1.5

def main():
    pkl_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'pickle', 'h1_rBD_t_notes1_1e-4_0.0~1.5.pkl'))
    df = pd.read_pickle(pkl_path)
    print(f"Loaded {len(df)} rows")

    rows = []
    for cid, grp in df.groupby('cycle'):
        rows.append({'cycle': cid,
                     'birth': grp['birth'].min(),
                     'death': grp['death'].max()})
    bars = pd.DataFrame(rows)

    # 탐색 범위 [0, 1.5]를 넘어가는 cycle = beyond_range
    bars['beyond'] = bars['death'] > RATE_MAX
    # 시각화용 death (clip)
    bars['death_vis'] = bars['death'].clip(upper=RATE_MAX)
    bars['lifespan_vis'] = bars['death_vis'] - bars['birth']

    # lifespan_vis 내림차순 정렬: 위쪽 = 오래 살아남은
    bars = bars.sort_values(['beyond', 'lifespan_vis'],
                            ascending=[False, False]).reset_index(drop=True)
    n_bars = len(bars)
    n_beyond = int(bars['beyond'].sum())
    print(f"Total cycles: {n_bars},  beyond range: {n_beyond}")

    fig, ax = plt.subplots(figsize=(11, 9))
    fig.patch.set_facecolor('white')

    color_beyond = '#e74c3c'   # 빨강
    color_finite = '#3498db'   # 파랑

    for i, row in bars.iterrows():
        color = color_beyond if row['beyond'] else color_finite
        y = n_bars - 1 - i
        width = row['death_vis'] - row['birth']
        ax.barh(y, width, left=row['birth'], height=0.72,
                color=color, edgecolor='#2c3e50', linewidth=0.4)
        if row['beyond']:
            ax.annotate('∞', xy=(RATE_MAX + 0.005, y),
                        ha='left', va='center', fontsize=13,
                        color='#c0392b', fontweight='bold')

    # 두 그룹의 경계선 (시각적 구분)
    if n_beyond > 0 and n_beyond < n_bars:
        boundary_y = n_bars - n_beyond - 0.5
        ax.axhline(y=boundary_y, color='#7f8c8d',
                   linestyle=':', linewidth=1.0, alpha=0.5)
        ax.text(RATE_MAX + 0.05, boundary_y - 0.5, '↓ 탐색 범위 내 소멸',
                fontsize=8, color='#7f8c8d', va='top')
        ax.text(RATE_MAX + 0.05, boundary_y + 0.5, '↑ 탐색 범위 초과',
                fontsize=8, color='#7f8c8d', va='bottom')

    ax.set_xlabel('Rate parameter $r_t$  (filtration scale)',
                  fontsize=12, color='#2c3e50')
    ax.set_ylabel('Cycle index (sorted by lifespan)',
                  fontsize=12, color='#2c3e50')
    ax.set_title('Figure 4. Persistence Barcode — hibari $H_1$ cycles (전체 48개)\n'
                 f'빨강 = 탐색 범위 $[0, {RATE_MAX}]$를 넘어 살아남는 cycle ({n_beyond}개)\n'
                 f'파랑 = 범위 내에서 birth/death 모두 발생하는 유한 cycle ({n_bars - n_beyond}개)',
                 fontsize=11, color='#2c3e50', pad=12)

    ax.set_xlim(-0.03, RATE_MAX + 0.18)
    ax.set_ylim(-0.8, n_bars - 0.2)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=color_beyond, edgecolor='#2c3e50',
              label=f'탐색 범위 초과 ({n_beyond}개)'),
        Patch(facecolor=color_finite, edgecolor='#2c3e50',
              label=f'범위 내 유한 cycle ({n_bars - n_beyond}개)'),
    ]
    ax.legend(handles=legend_elems, loc='lower right',
              fontsize=10, framealpha=0.95)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig4_barcode.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
