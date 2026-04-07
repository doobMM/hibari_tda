"""
Tonnetz 격자 설명용 다이어그램 생성.
- 가로 = 완전5도 (+7 semitones)
- 대각선 = 장3도 (+4) / 단3도 (+3)
- 삼각형 = major/minor triad
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, FancyArrowPatch
import matplotlib as mpl

mpl.rcParams['font.family'] = 'serif'

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def make_lattice():
    """5x9 정도 크기의 헥사고날 격자."""
    # 좌표 → pitch class
    # 가로 +1: +7 (5도), 세로 +1 (위쪽 대각선): +4 (장3도)
    # 짝수/홀수 행 오프셋으로 헥사고날 만듦
    rows, cols = 4, 7
    coords = []  # (x, y, pc)
    for r in range(rows):
        for c in range(cols):
            x = c + (r % 2) * 0.5
            y = r * np.sqrt(3) / 2
            pc = (c * 7 + r * 4) % 12
            coords.append((x, y, pc))

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # 격자선 (인접 점들 연결)
    for i, (x1, y1, pc1) in enumerate(coords):
        for x2, y2, pc2 in coords[i+1:]:
            d = np.hypot(x1-x2, y1-y2)
            if 0.4 < d < 1.2:
                ax.plot([x1, x2], [y1, y2], color='#bbbbbb',
                        linewidth=1.0, zorder=1)

    # 한 삼각형 강조 (C major triad: C, E, G)
    # C(0), E(4), G(7) 위치 찾기
    pcs_to_highlight = {0, 4, 7}
    triad_positions = {}
    for x, y, pc in coords:
        if pc in pcs_to_highlight and pc not in triad_positions:
            triad_positions[pc] = (x, y)
            if len(triad_positions) == 3:
                break
    if len(triad_positions) == 3:
        pts = [triad_positions[0], triad_positions[4], triad_positions[7]]
        # 가장 가까운 위치를 찾기 위해 모든 조합 검사
        # 단순히 가장 가까운 트리오 찾기
        best = None
        best_perim = float('inf')
        positions_by_pc = {pc: [] for pc in [0, 4, 7]}
        for x, y, pc in coords:
            if pc in positions_by_pc:
                positions_by_pc[pc].append((x, y))
        for c_pos in positions_by_pc[0]:
            for e_pos in positions_by_pc[4]:
                for g_pos in positions_by_pc[7]:
                    perim = (np.hypot(c_pos[0]-e_pos[0], c_pos[1]-e_pos[1]) +
                             np.hypot(e_pos[0]-g_pos[0], e_pos[1]-g_pos[1]) +
                             np.hypot(g_pos[0]-c_pos[0], g_pos[1]-c_pos[1]))
                    if perim < best_perim:
                        best_perim = perim
                        best = (c_pos, e_pos, g_pos)
        if best and best_perim < 4:
            tri = Polygon(best, facecolor='#ffeaa7', edgecolor='#fdcb6e',
                          linewidth=2, alpha=0.7, zorder=2)
            ax.add_patch(tri)
            # C major 라벨
            cx = sum(p[0] for p in best) / 3
            cy = sum(p[1] for p in best) / 3
            ax.text(cx, cy - 0.05, 'C major\ntriad', ha='center', va='center',
                    fontsize=8, color='#7a5a00', fontweight='bold', zorder=6)

    # 노드
    for x, y, pc in coords:
        ax.add_patch(Circle((x, y), 0.27, facecolor='#74b9ff',
                            edgecolor='#0984e3', linewidth=1.2, zorder=4))
        ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                fontsize=11, fontweight='bold', color='white', zorder=5)

    # 화살표: 5도/장3도/단3도 방향 표시
    # 임의의 기준점 C 찾기
    c_origin = None
    for x, y, pc in coords:
        if pc == 0 and 1 < x < 4 and 0.3 < y < 2.5:
            c_origin = (x, y)
            break

    if c_origin:
        # 5도: 가로 오른쪽 옆 G
        for x, y, pc in coords:
            if pc == 7 and abs(y - c_origin[1]) < 0.1 and x > c_origin[0] and x - c_origin[0] < 1.3:
                ax.annotate('', xy=(x, y), xytext=c_origin,
                            arrowprops=dict(arrowstyle='->', color='#e74c3c', lw=2))
                mx, my = (x + c_origin[0])/2, (y + c_origin[1])/2 + 0.18
                ax.text(mx, my, '+ Perfect 5th\n(+7 semitones)',
                        ha='center', fontsize=8, color='#e74c3c', fontweight='bold')
                break
        # 장3도: 위쪽 대각선 E
        for x, y, pc in coords:
            if pc == 4 and y > c_origin[1] + 0.3 and abs(x - c_origin[0] - 0.5) < 0.3:
                ax.annotate('', xy=(x, y), xytext=c_origin,
                            arrowprops=dict(arrowstyle='->', color='#27ae60', lw=2))
                mx, my = (x + c_origin[0])/2 - 0.6, (y + c_origin[1])/2
                ax.text(mx, my, '+ Major 3rd\n(+4)', ha='right', fontsize=8,
                        color='#27ae60', fontweight='bold')
                break
        # 단3도: 다른 대각선 방향 (Eb)
        for x, y, pc in coords:
            if pc == 3 and y > c_origin[1] + 0.3 and abs(x - c_origin[0] + 0.5) < 0.3:
                ax.annotate('', xy=(x, y), xytext=c_origin,
                            arrowprops=dict(arrowstyle='->', color='#8e44ad', lw=2))
                mx, my = (x + c_origin[0])/2 + 0.6, (y + c_origin[1])/2
                ax.text(mx, my, '+ Minor 3rd\n(+3)', ha='left', fontsize=8,
                        color='#8e44ad', fontweight='bold')
                break

    ax.set_xlim(-0.6, cols + 0.5)
    ax.set_ylim(-0.5, rows * np.sqrt(3) / 2 + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

    out = os.path.join(os.path.dirname(__file__), 'tonnetz_lattice.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")
    return out


if __name__ == "__main__":
    make_lattice()
