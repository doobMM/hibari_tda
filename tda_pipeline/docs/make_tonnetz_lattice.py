"""
Tonnetz 격자 다이어그램 생성 (index.html 캡처 스타일).
- 저채도 회색 톤
- 얇은 격자선 + 부드러운 노드
- 옅은 색 면 강조
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import matplotlib as mpl

mpl.rcParams['font.family'] = 'DejaVu Sans'

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _build_coords(rows: int, cols: int):
    coords = []
    by_rc = {}
    for r in range(rows):
        for c in range(cols):
            x = c + (r % 2) * 0.5
            y = r * np.sqrt(3) / 2
            pc = (c * 7 + r * 4) % 12
            coords.append((x, y, pc))
            by_rc[(r, c)] = (x, y, pc)
    return coords, by_rc


def make_lattice():
    rows, cols = 7, 9
    coords, by_rc = _build_coords(rows, cols)

    bg = '#e6e8e7'
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    # Neighbor edges
    for i, (x1, y1, _) in enumerate(coords):
        for x2, y2, _ in coords[i + 1:]:
            d = np.hypot(x1 - x2, y1 - y2)
            if 0.75 < d < 1.05:
                ax.plot([x1, x2], [y1, y2], color='#aeb2b0', linewidth=1.0, zorder=1)

    # Soft colored triangles similar to UI capture
    tri_specs = [
        ((1, 2), (1, 3), (2, 2), '#cbd5e4'),
        ((1, 4), (2, 4), (2, 5), '#d5e3d3'),
        ((2, 1), (3, 1), (2, 2), '#d2dfd2'),
        ((2, 3), (3, 3), (3, 4), '#d8d2e4'),
        ((3, 4), (3, 5), (4, 4), '#d8e3cf'),
        ((4, 2), (5, 2), (4, 3), '#d3dde4'),
        ((4, 5), (5, 5), (5, 6), '#d9d2e3'),
    ]
    for a, b, c, color in tri_specs:
        if a in by_rc and b in by_rc and c in by_rc:
            pts = [by_rc[a][:2], by_rc[b][:2], by_rc[c][:2]]
            ax.add_patch(Polygon(pts, closed=True, facecolor=color, edgecolor='none', alpha=0.42, zorder=2))

    # Nodes
    for x, y, pc in coords:
        ax.add_patch(Circle((x, y), 0.24, facecolor='#dfe2e1', edgecolor='#a9adab', linewidth=1.0, zorder=3))
        ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                fontsize=17, color='#9ea2a0', zorder=4)

    ax.set_xlim(-0.8, cols - 0.1 + 0.5)
    ax.set_ylim(-0.5, rows * np.sqrt(3) / 2 + 0.6)
    ax.set_aspect('equal')
    ax.axis('off')

    out_dir = os.path.dirname(__file__)
    out_main = os.path.join(out_dir, 'tonnetz_lattice.png')
    out_alt = os.path.join(out_dir, 'tonnetz_lattice_수정.png')
    for out in (out_main, out_alt):
        plt.savefig(out, dpi=220, bbox_inches='tight', facecolor=bg, pad_inches=0.08)
        print(f"Saved: {out}")
    plt.close()
    return out_main, out_alt


if __name__ == "__main__":
    make_lattice()
