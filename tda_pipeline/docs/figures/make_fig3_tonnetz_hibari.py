"""
Figure 3 — Tonnetz 격자 + hibari note 배치.
hibari에서 실제로 사용되는 7개 pitch class (C major scale)
를 Tonnetz 위에 강조 표시.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import matplotlib as mpl

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# hibari에서 실제로 사용되는 pitch classes (C major scale)
HIBARI_PCS = {0, 2, 4, 5, 7, 9, 11}

# pc별 빈도 (count * note 수)
HIBARI_COUNTS = {
    0: 2 + 1 + 6,    # C (label 7, 8, 19)
    2: 2 + 5,        # D (label 9, 20)
    4: 2 + 4 + 1 + 4,  # E (label 1, 10, 11, 21)
    5: 2 + 2 + 1 + 1,  # F (label 2, 12, 13, 14)
    7: 2 + 5 + 2,    # G (label 3, 15, 22)
    9: 2 + 1 + 4 + 1 + 2,  # A (label 4, 5, 16, 17, 23)
    11: 4 + 3,       # B (label 6, 18)
}

def main():
    rows, cols = 5, 8
    coords = []
    for r in range(rows):
        for c in range(cols):
            x = c + (r % 2) * 0.5
            y = r * np.sqrt(3) / 2
            pc = (c * 7 + r * 4) % 12
            coords.append((x, y, pc))

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor('white')

    # 격자선
    for i, (x1, y1, _) in enumerate(coords):
        for x2, y2, _ in coords[i+1:]:
            d = np.hypot(x1-x2, y1-y2)
            if 0.4 < d < 1.2:
                ax.plot([x1, x2], [y1, y2], color='#cccccc',
                        linewidth=0.8, zorder=1)

    # hibari에서 사용되는 note의 인접 관계를 강조
    hibari_positions = [(x, y, pc) for x, y, pc in coords if pc in HIBARI_PCS]
    for i, (x1, y1, pc1) in enumerate(hibari_positions):
        for x2, y2, pc2 in hibari_positions[i+1:]:
            d = np.hypot(x1-x2, y1-y2)
            if d < 1.15:
                ax.plot([x1, x2], [y1, y2], color='#e74c3c',
                        linewidth=2.2, zorder=2, alpha=0.8)

    # 각 pitch class의 노드
    max_cnt = max(HIBARI_COUNTS.values()) if HIBARI_COUNTS else 1
    for x, y, pc in coords:
        if pc in HIBARI_PCS:
            cnt = HIBARI_COUNTS.get(pc, 0)
            # 빈도에 따라 크기 조정 (0.22 ~ 0.40)
            radius = 0.22 + 0.18 * (cnt / max_cnt)
            # hibari 쓰이는 음은 진한 파랑
            face = '#3498db'
            edge = '#2471a3'
            linewidth = 2.0
        else:
            radius = 0.22
            face = '#ecf0f1'
            edge = '#b2bec3'
            linewidth = 1.0

        ax.add_patch(Circle((x, y), radius, facecolor=face,
                            edgecolor=edge, linewidth=linewidth, zorder=4))
        ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                fontsize=10, fontweight='bold',
                color='white' if pc in HIBARI_PCS else '#7f8c8d',
                zorder=5)

        # 빈도 숫자 표시 (hibari 음만)
        if pc in HIBARI_PCS and HIBARI_COUNTS.get(pc, 0) > 0:
            ax.text(x, y - radius - 0.13, str(HIBARI_COUNTS[pc]),
                    ha='center', va='top', fontsize=7,
                    color='#2c3e50', zorder=5)

    # 범례
    legend_elems = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#3498db',
                   markeredgecolor='#2471a3', markersize=13,
                   label='hibari 사용 음 (7 pcs)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#ecf0f1',
                   markeredgecolor='#b2bec3', markersize=13,
                   label='미사용 pc'),
        plt.Line2D([0], [0], color='#e74c3c', linewidth=2.2,
                   label='hibari 음 간 Tonnetz 인접'),
    ]
    ax.legend(handles=legend_elems, loc='upper right',
              fontsize=9, frameon=True, framealpha=0.92)

    # 제목
    ax.set_title('Figure 3. Tonnetz 격자에 배치된 hibari의 7개 pitch class (C major scale)\n'
                 '빨간 선 = Tonnetz 그래프 상의 직접 인접, 숫자 = 원곡 내 출현 횟수',
                 fontsize=11, color='#2c3e50', pad=12)

    ax.set_xlim(-0.6, cols + 0.5)
    ax.set_ylim(-0.8, rows * np.sqrt(3) / 2 + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig3_tonnetz_hibari.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
