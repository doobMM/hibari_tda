"""
Generate three sketch-style illustrations for hibari video essay.
Saves to C:\WK14\tda_pipeline\docs\figures\
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

try:
    from scipy.interpolate import splprep, splev
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("scipy not available — using raw control points")

np.random.seed(42)
OUT = r'C:\WK14\tda_pipeline\docs\figures'
os.makedirs(OUT, exist_ok=True)

BG   = '#F7F4ED'
INK  = '#1c1c1c'
SOFT = '#9a9a90'

def jit(a, s=0.021):
    return np.asarray(a, float) + np.random.normal(0, s, len(a))

def spline(xs, ys, n=200):
    if HAS_SCIPY and len(xs) >= 4:
        tck, _ = splprep([xs, ys], s=0.04, k=min(3, len(xs)-1))
        return splev(np.linspace(0, 1, n), tck)
    return list(xs), list(ys)

# ─────────────────────────────────────────────────────────────
# IMAGE 1: OPEN PALM  (1080 × 1080)
# ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.set(xlim=(0,10), ylim=(0,10), aspect='equal'); ax.axis('off')

def draw_finger(cx, yb, w, h, lw=1.45):
    th = np.linspace(np.pi, 0, 50)
    xs = np.r_[cx-w/2, cx-w/2, cx + w/2*np.cos(th), cx+w/2, cx+w/2]
    ys = np.r_[yb,     yb+h,   (yb+h) + w/2*np.sin(th), yb+h, yb]
    ax.plot(jit(xs), jit(ys), c=INK, lw=lw,
            solid_capstyle='round', solid_joinstyle='round')

draw_finger(3.65, 4.15, 0.63, 2.72)   # index
draw_finger(4.60, 4.25, 0.64, 3.08)   # middle (tallest)
draw_finger(5.55, 4.15, 0.63, 2.78)   # ring
draw_finger(6.32, 3.92, 0.55, 2.08)   # pinky

# Thumb — draw upright then rotate +24° (lean left: right-hand, palm up)
tcx, tyb, tw, th = 2.92, 3.28, 0.54, 1.70
tth = np.linspace(np.pi, 0, 40)
txs = np.r_[tcx-tw/2, tcx-tw/2, tcx+tw/2*np.cos(tth), tcx+tw/2, tcx+tw/2]
tys = np.r_[tyb,       tyb+th,  (tyb+th)+tw/2*np.sin(tth), tyb+th, tyb]
ang = np.radians(24)
rx = tcx + (txs-tcx)*np.cos(ang) - (tys-tyb)*np.sin(ang)
ry = tyb + (txs-tcx)*np.sin(ang) + (tys-tyb)*np.cos(ang)
ax.plot(jit(rx), jit(ry), c=INK, lw=1.45, solid_capstyle='round')

# Palm left edge
xl, yl = spline([3.02, 2.55, 2.48, 2.78, 3.18, 3.58],
                [4.15, 3.42, 2.68, 2.08, 1.78, 1.58])
ax.plot(jit(xl), jit(yl), c=INK, lw=1.45, solid_capstyle='round')

# Palm right edge
xr, yr = spline([6.60, 7.08, 7.18, 6.92, 6.52, 5.92],
                [3.92, 3.28, 2.52, 1.88, 1.62, 1.52])
ax.plot(jit(xr), jit(yr), c=INK, lw=1.45, solid_capstyle='round')

# Wrist base
xw, yw = spline([3.58, 4.22, 5.12, 5.88, 5.92],
                [1.58, 1.40, 1.40, 1.45, 1.52])
ax.plot(jit(xw), jit(yw), c=INK, lw=1.45, solid_capstyle='round')

# Thumb webbing to index
xwb, ywb = spline([3.06, 3.18, 3.30], [3.78, 4.03, 4.15])
ax.plot(jit(xwb), jit(ywb), c=INK, lw=1.2)

# Inter-finger valleys
for x1, y1, x2, y2 in [(4.0,4.32,4.12,4.42),
                         (4.93,4.42,5.07,4.42),
                         (5.87,4.30,6.03,4.08)]:
    vx, vy = spline([x1, (x1+x2)/2, x2], [y1, min(y1,y2)-0.17, y2])
    ax.plot(jit(vx), jit(vy), c=INK, lw=1.0, alpha=0.72)

# Palm crease lines (light)
for x1, x2, yc, amp, alp in [(3.4, 6.5, 2.80, 0.20, 0.32),
                               (3.7, 6.1, 3.50, 0.13, 0.26)]:
    px = np.linspace(x1, x2, 80)
    py = yc + amp * np.sin((px - x1) / (x2 - x1) * np.pi)
    ax.plot(jit(px, 0.04), jit(py, 0.04), c=SOFT, lw=0.7, alpha=alp)

fig.savefig(f'{OUT}/illustration_hand.png', dpi=100, bbox_inches='tight',
            facecolor=BG, edgecolor='none', pad_inches=0.15)
plt.close(fig)
print("Hand saved.")

# ─────────────────────────────────────────────────────────────
# IMAGE 2: TWO CONVERGING WAVES  (1920 × 1080)
# ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.set(xlim=(0, 19.2), ylim=(0, 10.8)); ax.axis('off')

x = np.linspace(0.5, 18.7, 2000)
t = (x - x[0]) / (x[-1] - x[0])

c1 = 7.1 - 2.0 * t      # 7.1 → 5.1  (upper, converging down)
c2 = 3.7 + 2.0 * t      # 3.7 → 5.7  (lower, converging up)
A  = 1.2
freq = 4.2

y1 = c1 + A * np.sin(2 * np.pi * freq * t)
y1 += np.random.normal(0, 0.022, len(t))

wobble = (0.17 * np.sin(2*np.pi*7.1*t) + 0.09 * np.sin(2*np.pi*11.3*t))
y2 = c2 + A * np.sin(2*np.pi*freq*t + np.pi + 0.4) + wobble * np.sin(np.pi*t) * 0.8
y2 += np.random.normal(0, 0.028, len(t))

ax.plot(x, y1, c=INK, lw=1.95, alpha=0.92, solid_capstyle='round')
ax.plot(x, y2, c=INK, lw=1.10, alpha=0.86, solid_capstyle='round')

fig.savefig(f'{OUT}/illustration_waves.png', dpi=100, bbox_inches='tight',
            facecolor=BG, edgecolor='none', pad_inches=0.2)
plt.close(fig)
print("Waves saved.")

# ─────────────────────────────────────────────────────────────
# IMAGE 3: SIMPLEX PROGRESSION  (1920 × 1080)
# ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.set(xlim=(0, 19.2), ylim=(0, 10.8)); ax.axis('off')

CY = 5.4
DR = 0.19
SX = [2.4, 6.2, 10.6, 15.2]

def dot(x, y):
    ax.add_patch(plt.Circle((x, y), DR, color=INK, zorder=5))

def seg(x1, y1, x2, y2, lw=1.55, ls='-', al=1.0):
    ax.plot([x1, x2], [y1, y2], c=INK, lw=lw, ls=ls,
            alpha=al, solid_capstyle='round', zorder=4)

def arrow(x):
    ax.annotate('', xy=(x+0.68, CY), xytext=(x, CY),
                arrowprops=dict(arrowstyle='->', color=SOFT, lw=1.1, mutation_scale=14))

# 0-simplex: single point
dot(SX[0], CY)
arrow(SX[0] + 0.35)

# 1-simplex: edge
d = 0.88
seg(SX[1]-d, CY, SX[1]+d, CY)
dot(SX[1]-d, CY); dot(SX[1]+d, CY)
arrow(SX[1] + d + 0.12)

# 2-simplex: filled triangle
r3 = 1.12
pts = [(SX[2],          CY + r3),
       (SX[2] - r3*0.87, CY - r3*0.5),
       (SX[2] + r3*0.87, CY - r3*0.5)]
ax.add_patch(plt.Polygon(pts, closed=True, fc='#DDD9CE', ec=INK, lw=1.55, zorder=3))
for p in pts:
    dot(*p)
arrow(SX[2] + r3*0.87 + 0.12)

# 3-simplex: tetrahedron (oblique projection)
s4 = 1.38
v = np.array([[ 0.00,  0.00,  s4],      # apex
              [-s4*.88, -s4*.50,  0],   # front-left
              [ s4*.88, -s4*.50,  0],   # front-right
              [ 0.00,   s4*.85,  0]])   # back

px4 = SX[3] + v[:,0] - 0.32*v[:,1]
py4 = CY    + v[:,2] + 0.42*v[:,1]

for i, j in [(0,1),(0,2),(1,2),(0,3),(1,3)]:
    seg(px4[i], py4[i], px4[j], py4[j])
seg(px4[2], py4[2], px4[3], py4[3], lw=1.0, ls='--', al=0.45)  # hidden edge

for i in range(4):
    dot(px4[i], py4[i])

# faint music note below tetrahedron
try:
    ax.text(SX[3], CY - 2.9, '\u2669', fontsize=30, color=SOFT, alpha=0.28,
            ha='center', va='center')
except Exception:
    pass

fig.savefig(f'{OUT}/illustration_simplex.png', dpi=100, bbox_inches='tight',
            facecolor=BG, edgecolor='none', pad_inches=0.28)
plt.close(fig)
print("Simplex saved.")
print("\nAll three illustrations complete.")
