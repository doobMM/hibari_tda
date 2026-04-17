"""Generate educational Simplicial Homology diagram for §2.2.
Three panels with epsilon balls: H0 (components), H1 (loop), H2 (cavity)."""
from PIL import Image, ImageDraw, ImageFont
import os, math

W, H = 720, 430
img = Image.new('RGBA', (W, H), (255, 255, 255, 255))
draw = ImageDraw.Draw(img)

FD = r'C:\Users\82104\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\c7bf07f7-1002-4049-9e02-01ea99ddb5fe\246d5b4c-791e-4fbf-b7e9-43d2e2418f22\skills\canvas-design\canvas-fonts'
ft_title = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 18)
ft_sec   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 13)
ft_label = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 11)
ft_sm    = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 9)
ft_mono  = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 10)
ft_mono_sm = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 9)

TEAL = '#1A9E96'; TEAL_D = '#0D6B65'; TEAL_L = '#D4F0ED'
GRAY = '#CCCCCC'; GRAY_T = '#666666'; DARK = '#1A1A1A'; BG = '#F7FAFA'
WARM = '#E8A87C'; WARM_D = '#B07040'
PURPLE = '#7B68AE'

draw.text((W//2, 14), 'Simplicial Homology  —  Cycles and Boundaries', fill=DARK, font=ft_title, anchor='mt')
draw.line([(40, 36), (W-40, 36)], fill=GRAY, width=1)

pw, ph = 210, 210; gap = 18
total = 3*pw + 2*gap; sx = (W-total)//2; sy = 52

panels = [
    ('H0: Connected Components', 'beta_0 = 2', TEAL),
    ('H1: 1-Cycle (Loop)',       'beta_1 = 1', PURPLE),
    ('H2: 2-Void (Cavity)',      'beta_2 = 1', WARM_D),
]

for pi, (title, betti, color) in enumerate(panels):
    px = sx + pi*(pw+gap); py = sy
    draw.rounded_rectangle([(px,py),(px+pw,py+ph)], radius=5, fill=BG)
    cx, cy = px+pw//2, py+ph//2+5

    if pi == 0:  # H0: two clusters with epsilon balls
        c1 = [(cx-55,cy-25),(cx-30,cy-35),(cx-35,cy+5)]
        c2 = [(cx+30,cy-15),(cx+55,cy-5)]
        er = 28
        for pt in c1+c2:
            bl = Image.new('RGBA',(W,H),(0,0,0,0))
            bd = ImageDraw.Draw(bl)
            bd.ellipse([(pt[0]-er,pt[1]-er),(pt[0]+er,pt[1]+er)],
                       fill=(26,158,150,40))
            img = Image.alpha_composite(img, bl)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([(px,py),(px+pw,py+ph)], radius=5, outline=GRAY)
        for i in range(len(c1)):
            for j in range(i+1,len(c1)):
                draw.line([c1[i],c1[j]], fill=TEAL, width=2)
        draw.line([c2[0],c2[1]], fill=TEAL, width=2)
        for p in c1+c2:
            draw.ellipse([(p[0]-5,p[1]-5),(p[0]+5,p[1]+5)], fill='#FFF', outline=TEAL_D, width=2)
        draw.text((cx-40, cy+30), 'group 1', fill=GRAY_T, font=ft_sm, anchor='mt')
        draw.text((cx+42, cy+15), 'group 2', fill=GRAY_T, font=ft_sm, anchor='mt')

    elif pi == 1:  # H1: hexagonal ring with epsilon balls
        hr = 42
        hex_pts = [(int(cx+hr*math.cos(math.pi/2+i*math.pi/3)),
                     int(cy+hr*math.sin(math.pi/2+i*math.pi/3))) for i in range(6)]
        ber = 26
        for pt in hex_pts:
            bl = Image.new('RGBA',(W,H),(0,0,0,0))
            bd = ImageDraw.Draw(bl)
            bd.ellipse([(pt[0]-ber,pt[1]-ber),(pt[0]+ber,pt[1]+ber)],
                       fill=(123,104,174,40))
            img = Image.alpha_composite(img, bl)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([(px,py),(px+pw,py+ph)], radius=5, outline=GRAY)
        for i in range(6):
            draw.line([hex_pts[i],hex_pts[(i+1)%6]], fill=PURPLE, width=3)
        for p in hex_pts:
            draw.ellipse([(p[0]-5,p[1]-5),(p[0]+5,p[1]+5)], fill='#FFF', outline=PURPLE, width=2)
        draw.text((cx, cy), 'hole', fill=PURPLE, font=ft_label, anchor='mm')
        draw.text((cx, cy+hr+22), 'no 2-simplex inside', fill=GRAY_T, font=ft_sm, anchor='mt')
        draw.text((cx, cy+hr+34), '-> cycle survives', fill=GRAY_T, font=ft_sm, anchor='mt')

    else:  # H2: tetrahedron
        draw.rounded_rectangle([(px,py),(px+pw,py+ph)], radius=5, outline=GRAY)
        top = (cx,cy-45); bl_ = (cx-40,cy+25); br_ = (cx+40,cy+25); back = (cx,cy-5)
        draw.polygon([top,bl_,back], fill='#FFF0E5', outline=WARM, width=1)
        draw.polygon([top,br_,back], fill='#FFF0E5', outline=WARM, width=1)
        draw.polygon([bl_,br_,back], fill='#FFF0E5', outline=WARM, width=1)
        draw.polygon([top,bl_,br_], outline=WARM_D, width=2)
        for p1,p2 in [(top,bl_),(top,br_),(bl_,br_),(top,back),(bl_,back),(br_,back)]:
            draw.line([p1,p2], fill=WARM_D, width=2)
        for p in [top,bl_,br_,back]:
            draw.ellipse([(p[0]-5,p[1]-5),(p[0]+5,p[1]+5)], fill='#FFF', outline=WARM_D, width=2)
        draw.text((cx, cy+44), '4 faces enclose', fill=GRAY_T, font=ft_sm, anchor='mt')
        draw.text((cx, cy+56), 'empty cavity inside', fill=GRAY_T, font=ft_sm, anchor='mt')

    # Title and betti — drawn AFTER balls
    draw.text((px+pw//2, py+10), title, fill=color, font=ft_sec, anchor='mt')
    draw.text((px+pw//2, py+ph-12), betti, fill=color, font=ft_mono, anchor='mb')

# Boundary operator box
by_ = sy+ph+18; bx = sx+10
draw.rounded_rectangle([(bx,by_),(bx+total-20,by_+100)], radius=5, fill='#FFF', outline=TEAL, width=1)
draw.text((bx+12,by_+14), 'Computing H1:', fill=TEAL_D, font=ft_sec, anchor='lt')
draw.text((bx+12,by_+34), 'H1(K) = ker(d1) / im(d2)', fill=DARK, font=ft_mono, anchor='lt')
draw.text((bx+240,by_+34), 'closed loops  /  filled triangles', fill=GRAY_T, font=ft_sm, anchor='lt')
draw.text((bx+12,by_+54), 'ker(d1): edge chains that form closed loops', fill=GRAY_T, font=ft_label, anchor='lt')
draw.text((bx+12,by_+70), 'im(d2):  loops that are boundaries of triangles ("filled in")', fill=GRAY_T, font=ft_label, anchor='lt')
draw.text((bx+12,by_+86), 'beta_1 = dim(ker) - dim(im) = number of independent cycles', fill=TEAL_D, font=ft_mono_sm, anchor='lt')

img.convert('RGB').save(r'C:\WK14\tda_pipeline\docs\figures\fig_simplicial_homology.png', dpi=(150,150))
print('Saved fig_simplicial_homology.png')
