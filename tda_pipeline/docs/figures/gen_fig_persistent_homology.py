"""Generate educational Persistent Homology diagram for §2.3.
Top: 4 filtration stages with eps-balls.
Bottom-left: Persistence barcode (H0 + H1).
Bottom-right: Persistence diagram."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 800, 580
img = Image.new('RGBA', (W, H), (255, 255, 255, 255))
draw = ImageDraw.Draw(img)

FD = os.environ.get('CANVAS_FONTS_DIR', '')  # 재생성 시 Claude canvas-design 폰트 경로를 환경변수로 주입
ft_title = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 18)
ft_sec   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 13)
ft_label = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 11)
ft_sm    = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 9)
ft_mono  = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 10)
ft_mono_sm = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 9)
ft_eps   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 11)

TEAL = '#1A9E96'; TEAL_D = '#0D6B65'
GRAY = '#CCCCCC'; GRAY_T = '#666666'; DARK = '#1A1A1A'; BG = '#F7FAFA'
RED = '#CC3333'

draw.text((W//2, 14), 'Persistent Homology  —  Birth, Death & Barcode', fill=DARK, font=ft_title, anchor='mt')
draw.line([(50, 36), (W-50, 36)], fill=GRAY, width=1)

# === TOP: 4 filtration stages ===
PTS = [(50,5),(82,18),(97,50),(82,82),(50,95),(18,82),(3,50),(18,18)]
pw_t = 170; rh_t = 100; gap_t = 12
total_t = 4*pw_t + 3*gap_t; sx_t = (W-total_t)//2
top_y = 46

top_stages = [
    dict(r=0,  lbl='eps = 0',     info='8 H0, 0 H1'),
    dict(r=16, lbl='eps  small',  info='5 H0, 0 H1'),
    dict(r=25, lbl='eps  medium', info='1 H0, 1 H1'),
    dict(r=42, lbl='eps  large',  info='1 H0, 0 H1'),
]

for si, s in enumerate(top_stages):
    px = sx_t + si*(pw_t+gap_t)
    draw.rounded_rectangle([(px,top_y),(px+pw_t,top_y+rh_t)], radius=4, fill=BG)
    sc = 0.85
    ox = px + (pw_t - int(100*sc))//2; oy = top_y + (rh_t - int(100*sc))//2
    pts = [(int(ox+p[0]*sc), int(oy+p[1]*sc)) for p in PTS]
    if s['r'] > 0:
        er = int(s['r']*sc)
        layer = Image.new('RGBA',(W,H),(0,0,0,0))
        ld = ImageDraw.Draw(layer)
        for pt in pts:
            ld.ellipse([(pt[0]-er,pt[1]-er),(pt[0]+er,pt[1]+er)],
                       fill=(26,158,150,50))
        img = Image.alpha_composite(img, layer)
        draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(px,top_y),(px+pw_t,top_y+rh_t)], radius=4, outline=GRAY)
    for pt in pts:
        draw.ellipse([(pt[0]-3,pt[1]-3),(pt[0]+3,pt[1]+3)], fill=RED)
    draw.text((px+pw_t//2, top_y+rh_t+4), s['lbl'], fill=TEAL_D, font=ft_eps, anchor='mt')
    draw.text((px+pw_t//2, top_y+rh_t+17), s['info'], fill=GRAY_T, font=ft_sm, anchor='mt')

# Arrows between top panels
for si in range(3):
    ax = sx_t + (si+1)*(pw_t+gap_t) - gap_t//2
    draw.line([(ax-4,top_y+rh_t//2),(ax+3,top_y+rh_t//2)], fill=TEAL, width=2)
    draw.polygon([(ax+5,top_y+rh_t//2),(ax+1,top_y+rh_t//2-3),(ax+1,top_y+rh_t//2+3)], fill=TEAL)

# === SEPARATOR ===
sep_y = top_y + rh_t + 32
draw.line([(40,sep_y),(W-40,sep_y)], fill=GRAY, width=1)

# === BOTTOM LEFT: Persistence Barcode ===
bcx, bcy = 30, sep_y+8
bcw, bch = 400, 255
draw.rounded_rectangle([(bcx,bcy),(bcx+bcw,bcy+bch)], radius=5, fill=BG, outline=GRAY)
draw.text((bcx+bcw//2, bcy+10), 'Persistence Barcode', fill=DARK, font=ft_sec, anchor='mt')

bar_x = bcx + 65; bar_w = bcw - 80
bar_h = 13; bar_gap = 3

# H0 bars
h0_bars = [
    (0.0, 0.15), (0.0, 0.18), (0.0, 0.22),
    (0.0, 0.35), (0.0, 0.40),
    (0.0, 0.55), (0.0, 0.60),
    (0.0, 1.00),  # survivor (infinity)
]
h0_y = bcy + 28
draw.text((bar_x-8, h0_y+4), 'H0', fill=RED, font=ft_sec, anchor='rt')

for i, (b, d) in enumerate(h0_bars):
    y = h0_y + i*(bar_h+bar_gap)
    x1 = bar_x + int(b*bar_w)
    x2 = bar_x + int(d*bar_w)
    draw.rounded_rectangle([(x1,y),(x2,y+bar_h)], radius=2, fill=RED)
    # Birth dot (open)
    draw.ellipse([(x1-3,y+bar_h//2-3),(x1+3,y+bar_h//2+3)], fill='#FFF', outline=RED, width=2)
    # Death dot or arrow
    if d >= 1.0:
        draw.polygon([(x2,y+bar_h//2),(x2-5,y+1),(x2-5,y+bar_h-1)], fill=RED)
    else:
        draw.ellipse([(x2-3,y+bar_h//2-3),(x2+3,y+bar_h//2+3)], fill=RED)

# H1 bars
h1_bars = [
    (0.50, 0.85),
    (0.38, 0.48),
]
h1_y = h0_y + len(h0_bars)*(bar_h+bar_gap) + 10
draw.text((bar_x-8, h1_y+4), 'H1', fill=TEAL_D, font=ft_sec, anchor='rt')

for i, (b, d) in enumerate(h1_bars):
    y = h1_y + i*(bar_h+bar_gap)
    x1 = bar_x + int(b*bar_w)
    x2 = bar_x + int(d*bar_w)
    draw.rounded_rectangle([(x1,y),(x2,y+bar_h)], radius=2, fill=TEAL)
    draw.ellipse([(x1-3,y+bar_h//2-3),(x1+3,y+bar_h//2+3)], fill='#FFF', outline=TEAL, width=2)
    draw.ellipse([(x2-3,y+bar_h//2-3),(x2+3,y+bar_h//2+3)], fill=TEAL)

# eps axis
ax_y = h1_y + len(h1_bars)*(bar_h+bar_gap) + 10
draw.line([(bar_x,ax_y),(bar_x+bar_w,ax_y)], fill=GRAY_T, width=1)
for i in range(6):
    tx = bar_x + i*bar_w//5
    draw.line([(tx,ax_y-3),(tx,ax_y+3)], fill=GRAY_T, width=1)
    draw.text((tx,ax_y+6), f'{i*0.2:.1f}', fill=GRAY_T, font=ft_mono_sm, anchor='mt')
draw.text((bar_x+bar_w//2, ax_y+18), 'eps (distance threshold)', fill=GRAY_T, font=ft_sm, anchor='mt')

# Legend
ly = ax_y + 32
draw.ellipse([(bar_x,ly),(bar_x+8,ly+8)], fill='#FFF', outline=RED, width=2)
draw.text((bar_x+12,ly+4), 'birth', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.ellipse([(bar_x+50,ly),(bar_x+58,ly+8)], fill=RED)
draw.text((bar_x+62,ly+4), 'death', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.rounded_rectangle([(bar_x+105,ly-1),(bar_x+135,ly+9)], radius=2, fill=TEAL)
draw.text((bar_x+139,ly+4), 'persistence = death - birth', fill=GRAY_T, font=ft_sm, anchor='lm')

# === BOTTOM RIGHT: Persistence Diagram ===
pdx, pdy = 455, sep_y+8
pdw, pdh = 320, 255
draw.rounded_rectangle([(pdx,pdy),(pdx+pdw,pdy+pdh)], radius=5, fill=BG, outline=GRAY)
draw.text((pdx+pdw//2, pdy+10), 'Persistence Diagram', fill=DARK, font=ft_sec, anchor='mt')

ax_x = pdx + 55; ax_top = pdy + 35; ax_size = 170
ax_bot = ax_top + ax_size

draw.line([(ax_x,ax_bot),(ax_x+ax_size,ax_bot)], fill=GRAY_T, width=1)
draw.line([(ax_x,ax_bot),(ax_x,ax_top)], fill=GRAY_T, width=1)
draw.text((ax_x+ax_size//2, ax_bot+12), 'birth', fill=GRAY_T, font=ft_sm, anchor='mt')
draw.text((ax_x-12, ax_top+ax_size//2), 'death', fill=GRAY_T, font=ft_sm, anchor='mm')

# Ticks
for i in range(6):
    t = i*0.2
    tx = ax_x + int(t*ax_size)
    ty = ax_bot - int(t*ax_size)
    draw.line([(tx,ax_bot-2),(tx,ax_bot+2)], fill=GRAY_T, width=1)
    draw.line([(ax_x-2,ty),(ax_x+2,ty)], fill=GRAY_T, width=1)

# Diagonal (b = d)
draw.line([(ax_x,ax_bot),(ax_x+ax_size,ax_top)], fill='#E0E0E0', width=1)
draw.text((ax_x+ax_size-5, ax_top+8), 'b=d', fill='#CCCCCC', font=ft_mono_sm, anchor='rm')

# Plot H0 points (red)
for (b, d) in h0_bars:
    if d < 1.0:
        ppx = ax_x + int(b*ax_size)
        ppy = ax_bot - int(d*ax_size)
        draw.ellipse([(ppx-4,ppy-4),(ppx+4,ppy+4)], fill=RED, outline='#FFF', width=1)
    else:
        ppx = ax_x + int(b*ax_size)
        ppy = ax_top - 8
        draw.polygon([(ppx,ppy),(ppx-5,ppy+8),(ppx+5,ppy+8)], fill=RED)

# Plot H1 points (teal)
for (b, d) in h1_bars:
    ppx = ax_x + int(b*ax_size)
    ppy = ax_bot - int(d*ax_size)
    draw.ellipse([(ppx-5,ppy-5),(ppx+5,ppy+5)], fill=TEAL, outline='#FFF', width=1)

# Annotation: far from diagonal
ann_x = ax_x + ax_size + 8
draw.line([(ann_x, ax_top+30),(ann_x, ax_bot-30)], fill=TEAL, width=1)
draw.polygon([(ann_x, ax_top+30),(ann_x-3,ax_top+38),(ann_x+3,ax_top+38)], fill=TEAL)
draw.text((ann_x+6, (ax_top+ax_bot)//2), 'far from\ndiagonal\n= long\npersistence', fill=GRAY_T, font=ft_sm, anchor='lm')

# PD Legend
draw.ellipse([(pdx+15, pdy+pdh-28),(pdx+23, pdy+pdh-20)], fill=RED)
draw.text((pdx+27, pdy+pdh-24), 'H0', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.ellipse([(pdx+55, pdy+pdh-28),(pdx+63, pdy+pdh-20)], fill=TEAL)
draw.text((pdx+67, pdy+pdh-24), 'H1', fill=GRAY_T, font=ft_sm, anchor='lm')

# === MUSICAL INTERPRETATION ===
mx, my = 30, bcy+bch+12
mw, mh = W-60, 108
draw.rounded_rectangle([(mx,my),(mx+mw,my+mh)], radius=5, fill='#FFF', outline=TEAL, width=1)
draw.text((mx+mw//2, my+8), 'Musical Interpretation', fill=TEAL_D, font=ft_sec, anchor='mt')

interp = [
    ('birth b:',      'Feature first appears at distance eps = b'),
    ('death d:',      'Feature absorbed (filled in) at eps = d'),
    ('persistence:',  'd - b  (larger = more stable structure)'),
    ('long bar:',     'Robust structural motif of the piece'),
    ('short bar:',    'Transient / noise-like pattern'),
]
for i, (k, v) in enumerate(interp):
    iy = my + 26 + i*16
    draw.text((mx+14, iy), k, fill=TEAL_D, font=ft_mono_sm, anchor='lt')
    draw.text((mx+110, iy), v, fill=GRAY_T, font=ft_sm, anchor='lt')

img.convert('RGB').save(r'C:\WK14\tda_pipeline\docs\figures\fig_persistent_homology.png', dpi=(150,150))
print('Saved fig_persistent_homology.png')
