"""
Two boys on bikes, coasting downhill, pedaling backward.
Sketch style matching the other illustrations.
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

np.random.seed(789)
OUT = r'C:\WK14\tda_pipeline\docs\figures'
os.makedirs(OUT, exist_ok=True)

BG   = '#F7F4ED'
INK  = '#1c1c1c'
SOFT = '#9a9a90'
HILL = '#E8E4DA'

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set(xlim=(0, 19.2), ylim=(0, 10.8))
ax.axis('off')

# ─── LANDSCAPE ───────────────────────────────────────────────

# Distant hills
bx = np.linspace(0, 19.2, 400)
by = 8.0 + 0.45*np.sin(bx*0.21) + 0.28*np.sin(bx*0.55+1.4) + 0.12*np.sin(bx*1.05+0.6)
ax.fill_between(bx, by, 10.8, color='#EDEADA', alpha=0.45, zorder=1)
ax.plot(bx, by, c=SOFT, lw=0.6, alpha=0.22, zorder=2)

# Main hill (gentle S-slope downhill right)
hx = np.linspace(0, 19.2, 600)
hy = 5.9 + 1.3*np.exp(-((hx-2.2)/3.2)**2) - 1.55*(hx/19.2) + 0.10*np.sin(hx*1.25)
hy += np.random.normal(0, 0.016, len(hx))
ax.fill_between(hx, 0, hy, color=HILL, alpha=0.88, zorder=3)
ax.plot(hx, hy, c=INK, lw=0.95, alpha=0.60, zorder=4)

def hill_at(x):
    return float(np.interp(x, hx, hy))

def slope_at(x, dx=0.9):
    return np.arctan2(hill_at(x+dx) - hill_at(x-dx), 2*dx)

# Grass ticks
np.random.seed(789)
for gx in np.linspace(0.4, 18.8, 42):
    gy = hill_at(gx)
    h  = np.random.uniform(0.07, 0.15)
    ax.plot([gx, gx + np.random.uniform(-0.04, 0.04)],
            [gy, gy+h], c=INK, lw=0.42, alpha=0.25, zorder=4)

# ─── BIKE + RIDER ────────────────────────────────────────────

def bike_rider(cx, scale=1.0, lw=1.4, zb=6):
    ang = slope_at(cx)
    r   = 0.58 * scale      # wheel radius
    wb  = 1.52 * scale      # wheelbase

    cos_a, sin_a = np.cos(ang), np.sin(ang)

    # Rear wheel world centre
    rw_wx = cx - wb/2 * cos_a
    rw_wy = hill_at(rw_wx) + r

    # Flat-frame rear wheel rotated
    rot_x = (-wb/2)*cos_a - r*sin_a
    rot_y = (-wb/2)*sin_a + r*cos_a
    tx = rw_wx - rot_x
    ty = rw_wy - rot_y

    def W(px, py):
        """Flat-frame point → world"""
        wx = px*cos_a - py*sin_a + tx
        wy = px*sin_a + py*cos_a + ty
        return wx, wy

    def J(xs, ys, s=0.015):
        return (np.asarray(xs, float) + np.random.normal(0, s, len(xs)),
                np.asarray(ys, float) + np.random.normal(0, s, len(ys)))

    def L(xs, ys, lw_=None, zo=None):
        ax.plot(*J(xs, ys), c=INK, lw=lw_ or lw,
                solid_capstyle='round', solid_joinstyle='round',
                zorder=zo or zb)

    # Key frame points in flat coords
    bb_fp  = (0.0,           r + 0.22)
    st_fp  = (-0.22*scale,   r + 0.22 + 0.78*scale)
    ht_fp  = (+0.52*scale,   r + 0.22 + 0.50*scale)
    rw_fp  = (-wb/2,         r)
    fw_fp  = (+wb/2,         r)

    bb  = W(*bb_fp)
    st  = W(*st_fp)
    ht  = W(*ht_fp)
    rw  = W(*rw_fp)
    fw  = W(*fw_fp)

    # ── Wheels
    for cx_w, cy_w in (rw, fw):
        ax.add_patch(plt.Circle((cx_w, cy_w), r, fill=False, ec=INK, lw=lw, zorder=zb))
        ax.plot(cx_w, cy_w, 'o', c=INK, ms=2.4, zorder=zb+1)

    # ── Frame
    L([rw[0],bb[0]], [rw[1],bb[1]])           # chain stay
    L([rw[0],st[0]], [rw[1],st[1]])           # seat stay
    L([bb[0],st[0]], [bb[1],st[1]])           # seat tube
    L([st[0],ht[0]], [st[1],ht[1]+0.06])      # top tube
    L([bb[0],ht[0]], [bb[1],ht[1]])           # down tube
    L([ht[0],fw[0]], [ht[1],fw[1]])           # fork

    # ── Seat
    sl = W(st_fp[0]-0.20*scale, st_fp[1]+0.09)
    sr = W(st_fp[0]+0.10*scale, st_fp[1]+0.09)
    L([sl[0],sr[0]], [sl[1],sr[1]], lw_=lw*2.0, zo=zb+1)

    # ── Handlebar
    hb_bot = W(ht_fp[0],          ht_fp[1]+0.12)
    hb_top = W(ht_fp[0]-0.05*scale, ht_fp[1]+0.40*scale)
    hb_l   = W(ht_fp[0]-0.28*scale, ht_fp[1]+0.40*scale)
    hb_r   = W(ht_fp[0]+0.06*scale, ht_fp[1]+0.40*scale)
    L([hb_bot[0],hb_top[0]], [hb_bot[1],hb_top[1]])
    L([hb_l[0],hb_r[0]], [hb_l[1],hb_r[1]], lw_=lw*1.6, zo=zb+1)

    # ── Pedals — backward rotation (~108° from forward-up direction)
    crank = 0.28 * scale
    a1 = ang + np.radians(108)    # back-up crank
    a2 = a1 + np.pi               # front-down crank

    p1 = (bb[0] + crank*np.cos(a1), bb[1] + crank*np.sin(a1))
    p2 = (bb[0] + crank*np.cos(a2), bb[1] + crank*np.sin(a2))

    L([bb[0],p1[0]], [bb[1],p1[1]])
    L([bb[0],p2[0]], [bb[1],p2[1]])
    for (px,py,pa) in (p1+(a1,), p2+(a2,)):
        pdx = 0.105*np.cos(pa+np.pi/2)
        pdy = 0.105*np.sin(pa+np.pi/2)
        L([px-pdx,px+pdx], [py-pdy,py+pdy], lw_=lw*0.88)

    # ── Rider
    hip = W(st_fp[0]+0.02*scale, st_fp[1]+0.30*scale)
    tor = W(st_fp[0]+0.50*scale, st_fp[1]+0.60*scale)
    hd  = W(st_fp[0]+0.62*scale, st_fp[1]+0.96*scale)

    # Head
    ax.add_patch(plt.Circle(hd, 0.21*scale, fill=False, ec=INK, lw=lw, zorder=zb+2))
    # Torso (thick stroke)
    L([hip[0],tor[0]], [hip[1],tor[1]], lw_=lw*3.8, zo=zb+1)
    # Arms to handlebar
    L([tor[0], hb_l[0]+0.10], [tor[1], hb_l[1]], lw_=lw*2.1, zo=zb+1)
    # Legs (bent at knee, feet on pedals)
    k1 = W(st_fp[0]-0.10*scale, st_fp[1]-0.36*scale)
    k2 = W(st_fp[0]+0.30*scale, st_fp[1]-0.40*scale)
    L([hip[0],k1[0],p1[0]], [hip[1],k1[1],p1[1]], lw_=lw*2.2, zo=zb+1)
    L([hip[0],k2[0],p2[0]], [hip[1],k2[1],p2[1]], lw_=lw*2.2, zo=zb+1)

# Boy behind (slightly left, lower z)
bike_rider(cx=7.0,  scale=0.87, lw=1.28, zb=5)
# Boy ahead  (further right and down the hill, higher z)
bike_rider(cx=12.2, scale=0.93, lw=1.42, zb=7)

fig.savefig(f'{OUT}/illustration_bikes.png', dpi=100, bbox_inches='tight',
            facecolor=BG, edgecolor='none', pad_inches=0.18)
plt.close(fig)
print("Bikes saved.")
