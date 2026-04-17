"""Generate Algorithm 1 — Topological Sampling diagram."""
from PIL import Image, ImageDraw, ImageFont
import os, random

# Canvas
W, H = 1200, 700
img = Image.new('RGB', (W, H), '#FFFFFF')
draw = ImageDraw.Draw(img)

# Fonts
FD = r'C:\Users\82104\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\c7bf07f7-1002-4049-9e02-01ea99ddb5fe\246d5b4c-791e-4fbf-b7e9-43d2e2418f22\skills\canvas-design\canvas-fonts'
ft_title = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 22)
ft_sec = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 15)
ft_label = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 12)
ft_sm = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 10)
ft_rule = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 11)
ft_rb = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 11)
ft_mono = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 10)
ft_mono_sm = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 9)

# Colors
TEAL = '#1A9E96'
TEAL_L = '#B2E0DD'
TEAL_D = '#0D6B65'
GRAY = '#CCCCCC'
GRAY_T = '#666666'
DARK = '#1A1A1A'
BG = '#F7FAFA'
WARM = '#E8A87C'
WARM_D = '#B07040'

# Title
draw.text((W//2, 28), 'Algorithm 1  \u2014  Topological Sampling', fill=DARK, font=ft_title, anchor='mt')
draw.line([(80, 55), (W-80, 55)], fill=GRAY, width=1)

# === SECTION 1: OVERLAP MATRIX ===
s1x, s1y, s1w, s1h = 40, 80, 300, 540
draw.rounded_rectangle([(s1x, s1y), (s1x+s1w, s1y+s1h)], radius=6, fill=BG, outline=GRAY)
draw.text((s1x+s1w//2, s1y+16), 'Overlap Matrix  O[t, c]', fill=DARK, font=ft_sec, anchor='mt')

gx, gy = s1x+55, s1y+50
cw, ch = 34, 34
rows, cols = 12, 6
clabels = ['c1','c2','c3','c4','c5','c6']

pattern = [
    [1,0,1,0,0,1],
    [1,1,1,0,0,1],
    [0,1,0,0,1,0],
    [0,1,0,1,1,0],
    [1,0,0,1,0,0],
    [1,0,1,1,0,0],
    [0,0,1,0,0,1],
    [0,0,0,0,0,1],
    [1,1,0,0,1,0],
    [1,1,0,1,1,0],
    [0,0,1,1,0,1],
    [0,0,1,0,0,1],
]

for r in range(rows):
    for c in range(cols):
        x0 = gx + c*cw
        y0 = gy + r*ch
        x1, y1 = x0+cw, y0+ch
        fill = TEAL if pattern[r][c] else '#FFFFFF'
        draw.rectangle([(x0+1,y0+1),(x1-1,y1-1)], fill=fill)
        draw.rectangle([(x0,y0),(x1,y1)], outline=GRAY, width=1)

for c in range(cols):
    draw.text((gx+c*cw+cw//2, gy-10), clabels[c], fill=GRAY_T, font=ft_sm, anchor='mb')
for r in range(rows):
    draw.text((gx-8, gy+r*ch+ch//2), f't={r+1}', fill=GRAY_T, font=ft_mono_sm, anchor='rm')

draw.text((gx+cols*cw//2, gy-24), 'cycles', fill=GRAY_T, font=ft_sm, anchor='mb')
for i, ch_ in enumerate('time'):
    draw.text((gx-38, gy+rows*ch//2-20+i*14), ch_, fill=GRAY_T, font=ft_sm, anchor='mm')

# Highlight row 2 (intersection example) and row 8 (no-active example)
hy1 = gy + 1*ch
draw.rectangle([(gx-2, hy1-1), (gx+cols*cw+2, hy1+ch+1)], outline=WARM, width=2)
hy2 = gy + 7*ch
draw.rectangle([(gx-2, hy2-1), (gx+cols*cw+2, hy2+ch+1)], outline=TEAL_D, width=2)

# Legend
ly = gy + rows*ch + 20
draw.rectangle([(s1x+20, ly), (s1x+34, ly+14)], fill=TEAL, outline=GRAY)
draw.text((s1x+40, ly+7), 'Active (1)', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.rectangle([(s1x+130, ly), (s1x+144, ly+14)], fill='#FFFFFF', outline=GRAY)
draw.text((s1x+150, ly+7), 'Inactive (0)', fill=GRAY_T, font=ft_sm, anchor='lm')

# === SECTION 2: SAMPLING RULES ===
s2x, s2y, s2w, s2h = 390, 80, 420, 540
draw.rounded_rectangle([(s2x, s2y), (s2x+s2w, s2y+s2h)], radius=6, fill=BG, outline=GRAY)
draw.text((s2x+s2w//2, s2y+16), 'Sampling Rules', fill=DARK, font=ft_sec, anchor='mt')

# Arrow sec1 -> sec2
ay = s1y + s1h//2
draw.line([(s1x+s1w+2, ay), (s2x-2, ay)], fill=TEAL, width=2)
draw.polygon([(s2x-2, ay), (s2x-12, ay-6), (s2x-12, ay+6)], fill=TEAL)

# Diamond: check active
dcx, dcy = s2x+s2w//2, s2y+80
dr = 26
draw.polygon([(dcx, dcy-dr), (dcx+dr*2, dcy), (dcx, dcy+dr), (dcx-dr*2, dcy)],
             outline=TEAL_D, width=2, fill='#FFFFFF')
draw.text((dcx, dcy-3), 'Sum O[t,c]', fill=DARK, font=ft_mono, anchor='mm')
draw.text((dcx, dcy+10), '> 0 ?', fill=DARK, font=ft_mono, anchor='mm')

# Layout: Rule boxes tightly connected to diamond
r1w, r1h = 175, 70
r3w, r3h = 160, 70
# YES (Rule 1) — positioned directly below-left of diamond
yx = s2x+30
yy = dcy+dr+18  # tight gap from diamond bottom
# NO (Rule 3) — positioned directly below-right of diamond
nx = s2x+s2w-r3w-30
ny = dcy+dr+18

# === YES branch: diamond bottom-left edge → Rule 1 top-center ===
# Diamond bottom-left edge midpoint: between bottom (dcx, dcy+dr) and left (dcx-2*dr, dcy)
dia_bl_x = dcx - dr  # midpoint x
dia_bl_y = dcy + dr//2  # midpoint y
r1_top_cx = yx + r1w//2
# Draw line with arrowhead
draw.line([(dia_bl_x, dia_bl_y), (r1_top_cx, yy)], fill=TEAL, width=2)
draw.polygon([(r1_top_cx, yy), (r1_top_cx-4, yy-7), (r1_top_cx+4, yy-7)], fill=TEAL)
draw.text((dia_bl_x-12, dia_bl_y+2), 'YES', fill=TEAL_D, font=ft_rb, anchor='rm')

# Rule 1 box
draw.rounded_rectangle([(yx, yy), (yx+r1w, yy+r1h)], radius=4, fill='#FFFFFF', outline=TEAL, width=2)
draw.text((yx+r1w//2, yy+12), 'Rule 1', fill=TEAL_D, font=ft_rb, anchor='mt')
draw.text((yx+r1w//2, yy+30), 'Sample from', fill=DARK, font=ft_rule, anchor='mt')
draw.text((yx+r1w//2, yy+48), 'Intersection V(c)', fill=TEAL_D, font=ft_label, anchor='mt')

# === NO branch: diamond bottom-right edge → Rule 3 top-center ===
dia_br_x = dcx + dr
dia_br_y = dcy + dr//2
r3_top_cx = nx + r3w//2
draw.line([(dia_br_x, dia_br_y), (r3_top_cx, ny)], fill=GRAY_T, width=2)
draw.polygon([(r3_top_cx, ny), (r3_top_cx-4, ny-7), (r3_top_cx+4, ny-7)], fill=GRAY_T)
draw.text((dia_br_x+12, dia_br_y+2), 'NO', fill=GRAY_T, font=ft_rb, anchor='lm')

# Rule 3 box
draw.rounded_rectangle([(nx, ny), (nx+r3w, ny+r3h)], radius=4, fill='#FFFFFF', outline=GRAY_T, width=2)
draw.text((nx+r3w//2, ny+12), 'Rule 3', fill=GRAY_T, font=ft_rb, anchor='mt')
draw.text((nx+r3w//2, ny+30), 'Sample from', fill=DARK, font=ft_rule, anchor='mt')
draw.text((nx+r3w//2, ny+48), 'P \\ A(t)', fill=GRAY_T, font=ft_sec, anchor='mt')

# === Sub-diamond: empty? (connected from Rule 1 bottom) ===
sdcx = yx+r1w//2
sdy = yy+r1h+32
sr = 20
draw.line([(sdcx, yy+r1h), (sdcx, sdy-sr)], fill=TEAL, width=1)
draw.polygon([(sdcx, sdy-sr), (sdcx+sr*2, sdy), (sdcx, sdy+sr), (sdcx-sr*2, sdy)],
             outline=GRAY_T, width=1, fill='#FFFFFF')
draw.text((sdcx, sdy), 'Empty?', fill=DARK, font=ft_mono, anchor='mm')

# === Rule 2 (fallback) — connected from sub-diamond ===
r2y = sdy+sr+20
draw.line([(sdcx, sdy+sr), (sdcx, r2y)], fill=GRAY_T, width=1)
draw.polygon([(sdcx, r2y), (sdcx-3, r2y-5), (sdcx+3, r2y-5)], fill=GRAY_T)
draw.text((sdcx+5, sdy+sr+4), 'YES', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.rounded_rectangle([(yx, r2y), (yx+r1w, r2y+r1h)], radius=4, fill='#FFFFFF', outline=WARM, width=2)
draw.text((yx+r1w//2, r2y+12), 'Rule 2 (fallback)', fill=WARM_D, font=ft_rb, anchor='mt')
draw.text((yx+r1w//2, r2y+30), 'Sample from', fill=DARK, font=ft_rule, anchor='mt')
draw.text((yx+r1w//2, r2y+48), 'Union V(c)', fill=WARM_D, font=ft_label, anchor='mt')

# === Collision avoidance note ===
coly = r2y+r1h+20
draw.rounded_rectangle([(s2x+25, coly), (s2x+s2w-25, coly+32)], radius=3, fill='#FFF8F0', outline=WARM, width=1)
draw.text((s2x+s2w//2, coly+9), 'Collision avoidance: up to R = 50 resamples', fill=WARM_D, font=ft_rule, anchor='mt')

# === Output arrow ===
outy = coly+48
draw.line([(s2x+s2w//2, coly+32), (s2x+s2w//2, outy)], fill=TEAL, width=2)
draw.polygon([(s2x+s2w//2, outy+6), (s2x+s2w//2-5, outy), (s2x+s2w//2+5, outy)], fill=TEAL)
draw.text((s2x+s2w//2, outy+12), "n'[t]", fill=TEAL_D, font=ft_sec, anchor='mt')

# === SECTION 3: GENERATED SEQUENCE ===
s3x, s3y, s3w, s3h = 860, 80, 300, 540
draw.rounded_rectangle([(s3x, s3y), (s3x+s3w, s3y+s3h)], radius=6, fill=BG, outline=GRAY)
draw.text((s3x+s3w//2, s3y+16), 'Generated Sequence', fill=DARK, font=ft_sec, anchor='mt')

# Arrow sec2 -> sec3
draw.line([(s2x+s2w+2, ay), (s3x-2, ay)], fill=TEAL, width=2)
draw.polygon([(s3x-2, ay), (s3x-12, ay-6), (s3x-12, ay+6)], fill=TEAL)

# Piano roll
prx, pry = s3x+35, s3y+50
prw, prh = s3w-70, 420
pitches = ['C4','D4','E4','F4','G4','A4','B4','C5','D5','E5']
ph = prh // len(pitches)

for i, p in enumerate(pitches):
    py_ = pry + i*ph
    draw.line([(prx, py_), (prx+prw, py_)], fill='#E8E8E8', width=1)
    draw.text((prx-5, py_+ph//2), p, fill=GRAY_T, font=ft_mono_sm, anchor='rm')
draw.line([(prx, pry+len(pitches)*ph), (prx+prw, pry+len(pitches)*ph)], fill='#E8E8E8', width=1)

ts = 12
sw = prw / ts
for t in range(ts+1):
    tx = prx + t*sw
    draw.line([(tx, pry), (tx, pry+prh)], fill='#EEEEEE', width=1)
    if t < ts:
        draw.text((tx+sw//2, pry+prh+8), f't={t+1}', fill=GRAY_T, font=ft_mono_sm, anchor='mt')

notes_gen = [
    (0,7,2),(0,2,1),(1,5,2),(1,8,1),(2,3,1),(3,6,2),(3,1,1),
    (5,4,2),(5,9,1),(6,2,1),(7,0,2),(8,5,3),(8,7,1),(9,3,2),
    (10,8,2),(11,1,1),(11,6,1),
]
ncols = [TEAL, TEAL_D, '#2DB5AD', '#17847E', '#0D6B65', '#25A89F']
for (t, p, dur) in notes_gen:
    nx_ = prx + t*sw + 2
    ny_ = pry + (len(pitches)-1-p)*ph + 3
    nw_ = dur*sw - 4
    nh_ = ph - 6
    color = ncols[hash((t,p)) % len(ncols)]
    draw.rounded_rectangle([(nx_, ny_), (nx_+nw_, ny_+nh_)], radius=3, fill=color)

draw.text((prx+prw//2, pry+prh+22), 'time', fill=GRAY_T, font=ft_sm, anchor='mt')
draw.text((s3x+s3w//2, s3y+s3h-25), "n' = (n'_1, n'_2, ..., n'_T)", fill=GRAY_T, font=ft_mono, anchor='mt')

# Save
out = r'C:\WK14\tda_pipeline\docs\figures\fig_algo1_sampling.png'
img.save(out, dpi=(150, 150))
print(f'Saved: {out}')
print(f'Size: {img.size}')
