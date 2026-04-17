"""
gen_fig_vr_complex_v2.py
Publication-quality Vietoris-Rips filtration – matplotlib rewrite.
Output: fig_vr_complex_v2.png  (dpi=200)
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Polygon, FancyArrowPatch
import matplotlib.patheffects as pe

matplotlib.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 9,
    'figure.dpi': 200,
    'text.usetex': False,
})

# ── Palette ──────────────────────────────────────────────────────────────────
TEAL      = '#1A9E96'
TEAL_D    = '#0D6B65'
TEAL_L    = '#C8ECEB'
DARK      = '#1C1C1C'
GRAY      = '#777777'
GRAY_L    = '#BBBBBB'
PANEL_BG  = '#F5FAFA'
RED       = '#CC3333'
WHITE     = '#FFFFFF'

# ── 8-point octagon  (unit square [0,1]×[0,1], centred at 0.5,0.5) ─────────
R = 0.36                       # radius: points at 0.14 … 0.86 → fits nicely
cx, cy = 0.5, 0.50
angs = [np.pi/2 - k * 2*np.pi/8 for k in range(8)]
PTS  = np.array([[cx + R*np.cos(a), cy + R*np.sin(a)] for a in angs])

# Adjacent vertex distance = 2R·sin(π/8) ≈ 0.276
# Vertex-skip-1 distance  = 2R·sin(π/4) ≈ 0.509
ADJ_DIST  = 2 * R * np.sin(np.pi / 8)   # ≈ 0.276
SKIP1_DIST= 2 * R * np.sin(np.pi / 4)   # ≈ 0.509

# Ball radii per stage (data coords of each panel)
# Stage 1: just past half adjacent distance → touching, not huge
# Stage 2: same order of magnitude, slightly more overlap
# Stage 3: past half of skip-1 distance → diagonals covered
BALL_R = [0.0, ADJ_DIST*0.56, ADJ_DIST*0.72, SKIP1_DIST*0.56]

# ── Stage definitions ────────────────────────────────────────────────────────
EPS_LABELS = ['ε = 0', 'ε  small', 'ε  medium', 'ε  large']
DESCS = [
    '0-simplices\n(isolated vertices)',
    '1-simplices appear\n(nearby pairs connect)',
    'H₁ cycle born\n(closed loop, unfilled)',
    'H₁ cycle dies\n(triangles fill the loop)',
]

ALL_EDGES = [
    [],
    [(0,1),(6,7),(7,0),(3,4),(4,5)],
    [(i,(i+1)%8) for i in range(8)],
    [(i,(i+1)%8) for i in range(8)] + [(0,2),(0,6),(2,4),(4,6),(2,6)],
]
ALL_TRIS = [
    [], [], [],
    [(0,1,2),(0,2,6),(2,3,4),(2,4,6),(4,5,6),(0,6,7)],
]

# ── Figure / axes setup ──────────────────────────────────────────────────────
# Manual layout via fig.add_axes([left, bottom, width, height]) in figure coords.
# Gives exact pixel-level control.
FIG_W, FIG_H = 14, 7.5
fig = plt.figure(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(WHITE)

# Panel grid geometry (all in figure fraction)
LEFT0   = 0.075    # left edge of column 0
PCOL_W  = 0.188    # panel width
PCOL_G  = 0.032    # gap between columns
ROW_H   = 0.260    # panel height
ROW_TOP = 0.68     # top panel bottom edge (in figure fraction)
ROW_BOT = 0.32     # bottom panel bottom edge
# Row separation = ROW_TOP - (ROW_BOT + ROW_H) = 0.68 - 0.57 = 0.11

def col_left(c):
    return LEFT0 + c * (PCOL_W + PCOL_G)

# Build axes: axes_top[c], axes_bot[c]
axes_top = []
axes_bot = []
for c in range(4):
    xl = col_left(c)
    at = fig.add_axes([xl, ROW_TOP, PCOL_W, ROW_H])
    ab = fig.add_axes([xl, ROW_BOT, PCOL_W, ROW_H])
    axes_top.append(at)
    axes_bot.append(ab)

# ── Axes styling helper ───────────────────────────────────────────────────────
def prep_ax(ax, bg=PANEL_BG):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')
    # Rounded panel background
    bg_patch = FancyBboxPatch(
        (0.02, 0.02), 0.96, 0.96,
        boxstyle='round,pad=0.01',
        linewidth=0.9, edgecolor=GRAY_L,
        facecolor=bg,
        transform=ax.transAxes, clip_on=False, zorder=0
    )
    ax.add_patch(bg_patch)

# ── Draw ε-balls panel ────────────────────────────────────────────────────────
def draw_balls(ax, stage):
    prep_ax(ax)
    r = BALL_R[stage]
    if r > 0:
        for p in PTS:
            c = Circle(p, r, facecolor=TEAL_L, edgecolor='none',
                       alpha=0.40, zorder=2)
            ax.add_patch(c)
    for p in PTS:
        dot = Circle(p, 0.038, facecolor=RED, edgecolor=WHITE,
                     linewidth=0.9, zorder=10)
        ax.add_patch(dot)

# ── Draw simplicial complex panel ─────────────────────────────────────────────
LOOP_EDGES = set([(i,(i+1)%8) for i in range(8)] +
                 [((i+1)%8, i) for i in range(8)])

def draw_complex(ax, stage):
    prep_ax(ax, bg=WHITE)
    edges = ALL_EDGES[stage]
    tris  = ALL_TRIS[stage]

    # Triangles
    for tri in tris:
        poly = Polygon(PTS[[tri[0],tri[1],tri[2]]], closed=True,
                       facecolor=TEAL_L, edgecolor='none', alpha=0.70, zorder=2)
        ax.add_patch(poly)

    # Edges
    for e in edges:
        p0, p1 = PTS[e[0]], PTS[e[1]]
        is_loop = (stage == 2) and (e in LOOP_EDGES or (e[1],e[0]) in LOOP_EDGES)
        ax.plot([p0[0],p1[0]], [p0[1],p1[1]],
                color=(TEAL_D if is_loop else TEAL),
                linewidth=(2.6 if is_loop else 1.8),
                solid_capstyle='round', zorder=5)

    # Vertices
    for p in PTS:
        v = Circle(p, 0.042, facecolor=WHITE, edgecolor=TEAL_D,
                   linewidth=1.6, zorder=8)
        ax.add_patch(v)

# ── Populate ──────────────────────────────────────────────────────────────────
for c in range(4):
    draw_balls(axes_top[c], c)
    draw_complex(axes_bot[c], c)

# ── Stage ε labels (centred between rows) ────────────────────────────────────
# y position: in figure coords, midpoint of the gap between top and bot panels
gap_mid_fig = ROW_BOT + ROW_H + (ROW_TOP - (ROW_BOT + ROW_H)) / 2   # ≈ 0.625
for c in range(4):
    xc = col_left(c) + PCOL_W / 2
    fig.text(xc, gap_mid_fig, EPS_LABELS[c],
             ha='center', va='center',
             fontsize=11, fontweight='bold', color=TEAL_D)

# ── Descriptions below bottom panels ─────────────────────────────────────────
desc_y_fig = ROW_BOT - 0.030
for c in range(4):
    xc = col_left(c) + PCOL_W / 2
    fig.text(xc, desc_y_fig, DESCS[c],
             ha='center', va='top',
             fontsize=7.8, color=GRAY, linespacing=1.45)

# ── Row labels ───────────────────────────────────────────────────────────────
row_top_mid = ROW_TOP + ROW_H / 2
row_bot_mid = ROW_BOT + ROW_H / 2
fig.text(0.022, row_top_mid, 'ε-balls',
         ha='center', va='center', rotation=90,
         fontsize=10.5, fontstyle='italic', color=GRAY)
fig.text(0.022, row_bot_mid, 'Complex',
         ha='center', va='center', rotation=90,
         fontsize=10.5, fontstyle='italic', color=GRAY)

# ── Arrows between columns ────────────────────────────────────────────────────
# Place in figure coords at the midpoints of the horizontal gaps
for c in range(3):
    x_r = col_left(c) + PCOL_W + 0.004
    x_l = col_left(c+1) - 0.004
    for row_mid in [row_top_mid, row_bot_mid]:
        arr = FancyArrowPatch(
            (x_r, row_mid), (x_l, row_mid),
            transform=fig.transFigure,
            arrowstyle='->', color=TEAL,
            mutation_scale=13, linewidth=1.5, zorder=20,
        )
        fig.add_artist(arr)

# ── Overall title ─────────────────────────────────────────────────────────────
title_y = ROW_TOP + ROW_H + 0.09
fig.text(0.5, title_y + 0.03,
         'Vietoris-Rips Complex  —  Filtration by ε',
         ha='center', va='bottom',
         fontsize=15.5, fontweight='bold', color=DARK)
fig.text(0.5, title_y,
         'Building a simplicial complex as the proximity threshold ε grows',
         ha='center', va='bottom',
         fontsize=9, color=GRAY, style='italic')

# ── Filtration chain ──────────────────────────────────────────────────────────
chain_y  = desc_y_fig - 0.09   # in figure coords
chain_y2 = chain_y - 0.025

# Separator line
line_x0 = LEFT0;  line_x1 = col_left(3) + PCOL_W
fig.add_artist(matplotlib.lines.Line2D(
    [line_x0, line_x1], [chain_y + 0.018, chain_y + 0.018],
    transform=fig.transFigure,
    color=GRAY_L, linewidth=0.8, zorder=1
))

labels_K = ['K₀', 'K₁', 'K₂', 'K₃']
xs_K = [0.30, 0.40, 0.50, 0.60]   # figure x coords

for x, lab in zip(xs_K, labels_K):
    fig.text(x, chain_y, lab,
             ha='center', va='center',
             fontsize=12, fontweight='bold', color=TEAL_D)

# ⊆ arrows between Ks (arrow + underline)
for i in range(3):
    x0 = xs_K[i] + 0.028
    x1 = xs_K[i+1] - 0.028
    ay = chain_y - 0.002
    arr = FancyArrowPatch(
        (x0, ay), (x1, ay),
        transform=fig.transFigure,
        arrowstyle='->', color=TEAL,
        mutation_scale=11, linewidth=1.4, zorder=20,
    )
    fig.add_artist(arr)
    # underline (⊆ = ⊂ + bar)
    fig.add_artist(matplotlib.lines.Line2D(
        [x0, x1 - 0.004], [ay - 0.012, ay - 0.012],
        transform=fig.transFigure,
        color=TEAL, linewidth=1.1, zorder=20
    ))

fig.text(0.5, chain_y2,
         'Filtration: nested sequence of simplicial complexes as ε grows',
         ha='center', va='top',
         fontsize=8.5, color=GRAY, style='italic')

# ── Key insight box ───────────────────────────────────────────────────────────
box_y0  = 0.015
box_y1  = chain_y2 - 0.022
box_xm  = 0.5
box_w   = 0.56
box = FancyBboxPatch(
    (box_xm - box_w/2, box_y0),
    box_w,
    box_y1 - box_y0,
    boxstyle='round,pad=0.012',
    linewidth=1.3, edgecolor=TEAL,
    facecolor='#EDF9F8',
    transform=fig.transFigure,
    clip_on=False, zorder=1
)
fig.add_artist(box)

box_text_y = (box_y0 + box_y1) / 2
fig.text(box_xm, box_text_y + 0.013,
         'Key: cycles appear (H₁ born) and get filled (H₁ dies).',
         ha='center', va='center',
         fontsize=9, fontweight='bold', color=TEAL_D,
         transform=fig.transFigure, zorder=2)
fig.text(box_xm, box_text_y - 0.013,
         'Tracking birth/death across ε  →  Persistent Homology',
         ha='center', va='center',
         fontsize=8.5, color=DARK,
         transform=fig.transFigure, zorder=2)

# ── Save ─────────────────────────────────────────────────────────────────────
import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig_vr_complex_v2.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor=WHITE)
plt.close()
print(f'Saved: {out}')
