"""Generate educational VR Complex diagram for §2.1.
Two-row layout: top = ε-balls around points, bottom = abstract simplicial complex."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 800, 520
img = Image.new('RGBA', (W, H), (255, 255, 255, 255))
draw = ImageDraw.Draw(img)

FD = os.environ.get('CANVAS_FONTS_DIR', '')  # 재생성 시 Claude canvas-design 폰트 경로를 환경변수로 주입
ft_title = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 18)
ft_sec   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 13)
ft_label = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 11)
ft_sm    = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 9)
ft_mono  = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 10)
ft_eps   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 12)

TEAL = '#1A9E96'; TEAL_D = '#0D6B65'; TEAL_L = '#D4F0ED'
GRAY = '#CCCCCC'; GRAY_T = '#666666'; DARK = '#1A1A1A'; BG = '#F7FAFA'

draw.text((W//2, 14), 'Vietoris-Rips Complex  —  Filtration by eps', fill=DARK, font=ft_title, anchor='mt')
draw.line([(50, 36), (W-50, 36)], fill=GRAY, width=1)

# 8 base points on rough octagon (local coords 0-100)
PTS = [(50,5),(82,18),(97,50),(82,82),(50,95),(18,82),(3,50),(18,18)]

stages = [
    dict(r=0,  lbl='eps = 0',
         edges=[], tris=[],
         desc='0-simplices\n(isolated vertices)'),
    dict(r=18, lbl='eps  small',
         edges=[(0,1),(6,7),(7,0),(3,4),(4,5)], tris=[],
         desc='1-simplices appear\n(nearby pairs connect)'),
    dict(r=25, lbl='eps  medium',
         edges=[(i,(i+1)%8) for i in range(8)], tris=[],
         desc='H1 cycle born\n(closed loop, unfilled)'),
    dict(r=40, lbl='eps  large',
         edges=[(i,(i+1)%8) for i in range(8)]
               +[(0,2),(0,6),(2,4),(4,6),(2,6)],
         tris=[(0,1,2),(0,2,6),(2,3,4),(2,4,6),(4,5,6),(0,6,7)],
         desc='H1 cycle dies\n(triangles fill the loop)'),
]

pw, rh = 172, 145; gap = 14
total = 4*pw + 3*gap; sx = (W-total)//2
top_y = 48; lab_y = top_y+rh+2; bot_y = lab_y+22

draw.text((sx-4, top_y+rh//2), 'eps-balls', fill=GRAY_T, font=ft_sm, anchor='rm')
draw.text((sx-4, bot_y+rh//2), 'Complex', fill=GRAY_T, font=ft_sm, anchor='rm')

for si, s in enumerate(stages):
    px = sx + si*(pw+gap); pcx = px + pw//2

    # Top panel fill
    draw.rounded_rectangle([(px,top_y),(px+pw,top_y+rh)], radius=5, fill=BG)

    # Scale points into top panel
    sc = 1.32
    ox = px + (pw - int(100*sc))//2; oy = top_y + (rh - int(100*sc))//2
    ptsT = [(int(ox+p[0]*sc), int(oy+p[1]*sc)) for p in PTS]

    # Epsilon balls — per-ball layer for overlap darkening
    if s['r'] > 0:
        er = int(s['r']*sc)
        for pt in ptsT:
            bl = Image.new('RGBA',(W,H),(0,0,0,0))
            bd = ImageDraw.Draw(bl)
            bd.ellipse([(pt[0]-er,pt[1]-er),(pt[0]+er,pt[1]+er)],
                       fill=(26,158,150,45))
            img = Image.alpha_composite(img, bl)
        draw = ImageDraw.Draw(img)

    # Redraw top panel outline (over balls)
    draw.rounded_rectangle([(px,top_y),(px+pw,top_y+rh)], radius=5, outline=GRAY)

    # Data points (red)
    for pt in ptsT:
        draw.ellipse([(pt[0]-4,pt[1]-4),(pt[0]+4,pt[1]+4)], fill='#CC3333')

    # eps label
    draw.text((pcx, lab_y+8), s['lbl'], fill=TEAL_D, font=ft_eps, anchor='mt')

    # Bottom panel
    draw.rounded_rectangle([(px,bot_y),(px+pw,bot_y+rh)], radius=5, fill='#FFF', outline=GRAY)
    sc2 = 1.22
    ox2 = px + (pw-int(100*sc2))//2; oy2 = bot_y + (rh-int(100*sc2))//2
    ptsB = [(int(ox2+p[0]*sc2), int(oy2+p[1]*sc2)) for p in PTS]

    # Triangles
    for (i,j,k) in s['tris']:
        draw.polygon([ptsB[i],ptsB[j],ptsB[k]], fill=TEAL_L)
    # Edges — highlight cycle in stage 3
    ew = 3 if si == 2 else 2
    ec = TEAL_D if si == 2 else TEAL
    for (i,j) in s['edges']:
        draw.line([ptsB[i],ptsB[j]], fill=ec, width=ew)
    # Vertices
    for pt in ptsB:
        draw.ellipse([(pt[0]-5,pt[1]-5),(pt[0]+5,pt[1]+5)], fill='#FFF', outline=TEAL_D, width=2)

# Arrows between panels
for si in range(3):
    ax = sx + (si+1)*(pw+gap) - gap//2
    for ry in [top_y+rh//2, bot_y+rh//2]:
        draw.line([(ax-5,ry),(ax+3,ry)], fill=TEAL, width=2)
        draw.polygon([(ax+6,ry),(ax+1,ry-4),(ax+1,ry+4)], fill=TEAL)

# Descriptions
for si, s in enumerate(stages):
    px = sx + si*(pw+gap)
    for li, ln in enumerate(s['desc'].split('\n')):
        draw.text((px+pw//2, bot_y+rh+6+li*13), ln, fill=GRAY_T, font=ft_sm, anchor='mt')

# Filtration chain
fy = bot_y+rh+38
draw.line([(sx,fy),(sx+total,fy)], fill=GRAY, width=1)
cy = fy+14

# K0 ⊆ K1 ⊆ K2 ⊆ K3 — 폰트 대신 화살표를 직접 그려서 □ 문제 방지
k_labels = ['K0', 'K1', 'K2', 'K3']
k_xs = [W//2 - 90, W//2 - 30, W//2 + 30, W//2 + 90]
for kx, kl in zip(k_xs, k_labels):
    draw.text((kx, cy), kl, fill=TEAL_D, font=ft_label, anchor='mt')
for i in range(3):
    ax0 = k_xs[i] + 11;  ax1 = k_xs[i+1] - 11;  ay = cy + 7
    # 수평선 + 화살촉
    draw.line([(ax0, ay), (ax1-5, ay)], fill=TEAL, width=2)
    draw.polygon([(ax1, ay), (ax1-5, ay-3), (ax1-5, ay+3)], fill=TEAL)
    # 아랫선 (⊆ = ⊂ + 밑줄)
    draw.line([(ax0, ay+4), (ax1-5, ay+4)], fill=TEAL, width=1)

draw.text((W//2, cy+18), 'Filtration: nested sequence of simplicial complexes as eps grows',
          fill=GRAY_T, font=ft_label, anchor='mt')

# Key insight
ky = cy+38
draw.rounded_rectangle([(sx+30,ky),(sx+total-30,ky+40)], radius=5, fill='#FFF', outline=TEAL, width=1)
draw.text((W//2,ky+7), 'Key: cycles appear (H1 born) and get filled (H1 dies).',
          fill=DARK, font=ft_label, anchor='mt')
draw.text((W//2,ky+23), 'Tracking birth/death across eps  ->  Persistent Homology',
          fill=GRAY_T, font=ft_sm, anchor='mt')

img.convert('RGB').save(r'C:\WK14\tda_pipeline\docs\figures\fig_vr_complex.png', dpi=(150,150))
print('Saved fig_vr_complex.png')
