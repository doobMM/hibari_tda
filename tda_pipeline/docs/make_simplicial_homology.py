"""
Simplicial homology 직관 그림: cycle (1차원 구멍) + void (2차원 구멍).
- 좌측: 4점 사각형 = H1 generator (cycle)
- 우측: 4점 tetrahedron boundary = H2 generator (void)
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib as mpl

mpl.rcParams['font.family'] = 'serif'

fig = plt.figure(figsize=(11, 5))
fig.patch.set_facecolor('white')

# ── 좌측: 1차원 cycle (4점 사각형) ──
ax1 = fig.add_subplot(1, 2, 1)
ax1.set_facecolor('white')

# 4개 점 (사각형 모양)
square_pts = [(0.2, 0.2), (1.0, 0.2), (1.0, 1.0), (0.2, 1.0)]
# edge 그리기 (사각형 boundary)
for i in range(4):
    x1, y1 = square_pts[i]
    x2, y2 = square_pts[(i + 1) % 4]
    ax1.plot([x1, x2], [y1, y2], color='#0984e3', linewidth=3, zorder=2)

# 점
for x, y in square_pts:
    ax1.add_patch(Circle((x, y), 0.06, facecolor='#74b9ff',
                          edgecolor='#0984e3', linewidth=2, zorder=4))

# 내부가 비어있다는 표시
cx, cy = 0.6, 0.6
ax1.text(cx, cy, 'hole', ha='center', va='center',
         fontsize=12, color='#d63031', fontweight='bold',
         style='italic', zorder=3)

ax1.set_xlim(-0.1, 1.3)
ax1.set_ylim(-0.1, 1.4)
ax1.set_aspect('equal')
ax1.axis('off')
ax1.set_title('(a) 1D cycle: generator of $H_1$\n4 points forming a square boundary,\nno 2-simplex inside',
              fontsize=11, color='#2c3e50', pad=10)

# ── 우측: 2차원 void (4점 tetrahedron boundary) ──
ax2 = fig.add_subplot(1, 2, 2, projection='3d')
ax2.set_facecolor('white')

# tetrahedron의 4개 꼭짓점
tet_pts = np.array([
    [0.0, 0.0, 0.0],  # A
    [1.0, 0.0, 0.0],  # B
    [0.5, 0.85, 0.0], # C
    [0.5, 0.3, 0.85]  # D
])

# 4개의 삼각형 면 (boundary 면들)
faces = [
    [tet_pts[0], tet_pts[1], tet_pts[2]],  # ABC
    [tet_pts[0], tet_pts[1], tet_pts[3]],  # ABD
    [tet_pts[0], tet_pts[2], tet_pts[3]],  # ACD
    [tet_pts[1], tet_pts[2], tet_pts[3]],  # BCD
]
poly = Poly3DCollection(faces, facecolors='#74b9ff', alpha=0.25,
                         edgecolors='#0984e3', linewidths=2)
ax2.add_collection3d(poly)

# 꼭짓점 강조
ax2.scatter(tet_pts[:, 0], tet_pts[:, 1], tet_pts[:, 2],
            color='#0984e3', s=80, zorder=10)

# 내부가 비어있음 → 텍스트
ax2.text(0.5, 0.4, 0.35, 'void', ha='center', va='center',
         fontsize=11, color='#d63031', fontweight='bold', style='italic')

ax2.set_xlim(-0.1, 1.1)
ax2.set_ylim(-0.1, 1.0)
ax2.set_zlim(-0.1, 1.0)
ax2.set_axis_off()
ax2.view_init(elev=20, azim=45)
ax2.set_title('(b) 2D void: generator of $H_2$\n4 points forming a tetrahedron boundary,\nno 3-simplex inside',
              fontsize=11, color='#2c3e50', pad=10)

plt.tight_layout()
out = os.path.join(os.path.dirname(__file__), 'simplicial_homology.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Saved: {out}")
