"""Generate Algorithm 2 — Neural Sequence Model diagram (v5)."""
from PIL import Image, ImageDraw, ImageFont
import os, random

W, H = 1100, 620
img = Image.new('RGB', (W, H), '#FFFFFF')
draw = ImageDraw.Draw(img)

FD = r'C:\Users\82104\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\c7bf07f7-1002-4049-9e02-01ea99ddb5fe\246d5b4c-791e-4fbf-b7e9-43d2e2418f22\skills\canvas-design\canvas-fonts'
SYSF = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')

def _safe_font(font_name, size, *, mono=False, bold=False):
    candidates = [os.path.join(FD, font_name)]
    if mono:
        candidates += [os.path.join(SYSF, 'consola.ttf'), os.path.join(SYSF, 'cour.ttf')]
    elif bold:
        candidates += [os.path.join(SYSF, 'segoeuib.ttf'), os.path.join(SYSF, 'arialbd.ttf')]
    else:
        candidates += [os.path.join(SYSF, 'segoeui.ttf'), os.path.join(SYSF, 'arial.ttf')]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()

ft_title = _safe_font('InstrumentSans-Bold.ttf', 20, bold=True)
ft_sec = _safe_font('InstrumentSans-Bold.ttf', 14, bold=True)
ft_label = _safe_font('InstrumentSans-Regular.ttf', 12)
ft_sm = _safe_font('InstrumentSans-Regular.ttf', 10)
ft_rb = _safe_font('InstrumentSans-Bold.ttf', 11, bold=True)
ft_rule = _safe_font('InstrumentSans-Regular.ttf', 11)
ft_mono = _safe_font('GeistMono-Regular.ttf', 10, mono=True)
ft_mono_sm = _safe_font('GeistMono-Regular.ttf', 9, mono=True)
ft_tiny = _safe_font('GeistMono-Regular.ttf', 7, mono=True)
ft_or = _safe_font('InstrumentSans-Bold.ttf', 12, bold=True)

TEAL = '#1A9E96'; TEAL_D = '#0D6B65'; TEAL_L = '#D4F0ED'
GRAY = '#CCCCCC'; GRAY_T = '#666666'; DARK = '#1A1A1A'; BG = '#F7FAFA'
PURPLE = '#7B68AE'; PURPLE_L = '#E8E0F5'
WARM = '#E8A87C'; WARM_D = '#B07040'

draw.text((W//2, 24), 'Algorithm 2  \u2014  Neural Sequence Model', fill=DARK, font=ft_title, anchor='mt')
draw.line([(60, 50), (W-60, 50)], fill=GRAY, width=1)

# === INPUT ===
s1x, s1y, s1w, s1h = 20, 60, 175, 500
draw.rounded_rectangle([(s1x, s1y), (s1x+s1w, s1y+s1h)], radius=6, fill=BG, outline=GRAY)
draw.text((s1x+s1w//2, s1y+10), 'Input: O[t, :]', fill=DARK, font=ft_sec, anchor='mt')
draw.text((s1x+s1w//2, s1y+28), '(continuous overlap)', fill=GRAY_T, font=ft_sm, anchor='mt')

gx, gy = s1x+26, s1y+56
cw_, ch_ = 18, 15; rows_, cols_ = 24, 6
random.seed(123)
for r in range(rows_):
    for c in range(cols_):
        x0, y0 = gx + c*cw_, gy + r*ch_
        v = random.random()
        if v > 0.55:
            rc = int(255-v*(255-26)); gc = int(255-v*(255-158)); bc = int(255-v*(255-150))
            fill = f'#{rc:02x}{gc:02x}{bc:02x}'
        else: fill = '#FFFFFF'
        draw.rectangle([(x0+1,y0+1),(x0+cw_-1,y0+ch_-1)], fill=fill)
        draw.rectangle([(x0,y0),(x0+cw_,y0+ch_)], outline='#E8E8E8', width=1)
for c in range(cols_):
    draw.text((gx+c*cw_+cw_//2, gy-4), f'c{c+1}', fill=GRAY_T, font=ft_mono_sm, anchor='mb')
hy = gy + 6*ch_
draw.rectangle([(gx-2, hy-1), (gx+cols_*cw_+2, hy+ch_+1)], outline=TEAL_D, width=2)
draw.text((s1x+s1w//2, gy+rows_*ch_+8), 'Each row O[t,:]', fill=GRAY_T, font=ft_sm, anchor='mt')
draw.text((s1x+s1w//2, gy+rows_*ch_+20), '= K-dim vector', fill=GRAY_T, font=ft_sm, anchor='mt')
gly = gy+rows_*ch_+36; glw=80; glx=s1x+(s1w-glw)//2
for i in range(glw):
    v=i/glw; rc=int(255-v*(255-26)); gc=int(255-v*(255-158)); bc=int(255-v*(255-150))
    draw.line([(glx+i, gly), (glx+i, gly+8)], fill=f'#{rc:02x}{gc:02x}{bc:02x}')
draw.rectangle([(glx, gly), (glx+glw, gly+8)], outline=GRAY)
draw.text((glx, gly+12), '0', fill=GRAY_T, font=ft_mono_sm, anchor='lt')
draw.text((glx+glw, gly+12), '1', fill=GRAY_T, font=ft_mono_sm, anchor='rt')

# Arrow
arr_y = s1y+s1h//2
draw.line([(s1x+s1w+2, arr_y), (s1x+s1w+20, arr_y)], fill=TEAL, width=2)
draw.polygon([(s1x+s1w+20, arr_y), (s1x+s1w+14, arr_y-4), (s1x+s1w+14, arr_y+4)], fill=TEAL)

# === NN ===
nnx=s1x+s1w+22; nny=s1y; nnw=580; nnh=500
draw.rounded_rectangle([(nnx, nny), (nnx+nnw, nny+nnh)], radius=6, fill=BG, outline=GRAY)
draw.text((nnx+nnw//2, nny+10), 'Neural Network  (choose one)', fill=DARK, font=ft_sec, anchor='mt')

box_w=155; box_h=300; or_w=30
total_w=3*box_w+2*or_w; start_x=nnx+(nnw-total_w)//2; start_y=nny+60

models = [
    ('FC', TEAL, TEAL_D, TEAL_L, '2-layer, H=128', ['Timepoint-independent','(no time context)']),
    ('LSTM', PURPLE, PURPLE, PURPLE_L, '2-layer, H=128', ['Forward sequential','context']),
    ('Transformer', WARM_D, WARM_D, '#FFF0E5', '2L, 4-head, d=128', ['Self-attention','positional encoding']),
]
for i, (name, border, text_c, bg_c, spec, desc_lines) in enumerate(models):
    bx=start_x+i*(box_w+or_w); by_=start_y
    draw.rounded_rectangle([(bx, by_), (bx+box_w, by_+box_h)], radius=6, fill='#FFFFFF', outline=border, width=2)
    draw.rounded_rectangle([(bx+2, by_+2), (bx+box_w-2, by_+34)], radius=4, fill=bg_c)
    draw.text((bx+box_w//2, by_+17), name, fill=text_c, font=ft_sec, anchor='mm')
    draw.text((bx+box_w//2, by_+46), spec, fill=GRAY_T, font=ft_mono_sm, anchor='mt')
    base_vy = by_ + 65
    if name in ('FC', 'LSTM'):
        vy = base_vy + 14
    else:
        vy = base_vy + 18
    if name=='FC':
        layers=[4,5,4,3]
        for li,n in enumerate(layers):
            for ni in range(n):
                sp=(box_w-40)//max(n-1,1); cx=bx+20+ni*sp if n>1 else bx+box_w//2; cy=vy+li*42; r=6
                draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=TEAL_L, outline=TEAL)
                if li<len(layers)-1:
                    for nj in range(layers[li+1]):
                        sp2=(box_w-40)//max(layers[li+1]-1,1); cx2=bx+20+nj*sp2 if layers[li+1]>1 else bx+box_w//2; cy2=vy+(li+1)*42
                        draw.line([(cx,cy+r),(cx2,cy2-r)], fill='#DCDCDC', width=1)
    elif name=='LSTM':
        for ci in range(4):
            cx=bx+box_w//2; cy=vy+ci*42
            draw.rounded_rectangle([(cx-24,cy-11),(cx+24,cy+11)], radius=4, fill=PURPLE_L, outline=PURPLE)
            draw.text((cx,cy), f'h_{ci+1}', fill=PURPLE, font=ft_mono_sm, anchor='mm')
            if ci<3:
                draw.line([(cx,cy+11),(cx,cy+31)], fill=PURPLE, width=1)
                draw.polygon([(cx,cy+31),(cx-3,cy+26),(cx+3,cy+26)], fill=PURPLE)
    else:
        grid_n = 4
        step = 25
        grid_span = (grid_n - 1) * step
        gx0 = bx + (box_w - grid_span) // 2
        for ai in range(grid_n):
            for aj in range(grid_n):
                cx = gx0 + ai * step
                cy = vy + aj * step
                intensity = max(0, 200 - abs(ai - aj) * 60)
                r = 7
                fc = f'#{255-intensity:02x}{220-intensity//2:02x}{180-intensity//3:02x}'
                draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=fc, outline=WARM)
        draw.text((bx+box_w//2, vy+grid_span+18), 'attention weights', fill=GRAY_T, font=ft_mono_sm, anchor='mt')
    for di, line in enumerate(desc_lines):
        draw.text((bx+box_w//2, by_+box_h-30+di*13), line, fill=GRAY_T, font=ft_sm, anchor='mt')
    if i<2:
        draw.text((bx+box_w+or_w//2, by_+box_h//2), 'OR', fill=GRAY_T, font=ft_or, anchor='mm')

bot_y=start_y+box_h+14
draw.rounded_rectangle([(start_x, bot_y), (start_x+total_w, bot_y+26)], radius=4, fill=TEAL_L, outline=TEAL)
draw.text((start_x+total_w//2, bot_y+13), 'Sigmoid + Adaptive Threshold  -->  Multi-hot output y[t,:]', fill=TEAL_D, font=ft_rule, anchor='mm')
bot2_y=bot_y+32
draw.rounded_rectangle([(start_x+40, bot2_y), (start_x+total_w-40, bot2_y+22)], radius=3, fill='#FFF8F0', outline=WARM, width=1)
draw.text((start_x+total_w//2, bot2_y+11), 'Training: BCE Loss + Data Augmentation (circular shift, bit-flip)', fill=WARM_D, font=ft_sm, anchor='mm')

# Arrow to output
s3x=nnx+nnw+4
draw.line([(nnx+nnw, arr_y), (s3x+14, arr_y)], fill=TEAL, width=2)
draw.polygon([(s3x+14, arr_y), (s3x+8, arr_y-4), (s3x+8, arr_y+4)], fill=TEAL)

# === OUTPUT with actual hibari pitch labels ===
s3_left=s3x+16; s3w=W-s3_left-8
draw.rounded_rectangle([(s3_left, nny), (s3_left+s3w, nny+nnh)], radius=6, fill=BG, outline=GRAY)
draw.text((s3_left+s3w//2, nny+10), 'Output', fill=DARK, font=ft_sec, anchor='mt')

# Note labels with actual pitch in parentheses
vx=s3_left+4; vw=s3w-8; vy=nny+30
# Show a selection of 8 notes with real pitches
note_entries = [
    ('n1', 'E3'), ('n2', 'F3'), ('n7', 'C4'), ('n10', 'E4'),
    ('..', ''), ('n18', 'B4'), ('n22', 'G5'), ('n23', 'A5'),
]
bh = 15
for i, (nid, pitch) in enumerate(note_entries):
    y0 = vy + i*(bh+2)
    active = i in [0, 2, 5, 7]
    fill = TEAL if active else '#F0F0F0'
    draw.rounded_rectangle([(vx, y0), (vx+vw, y0+bh)], radius=2, fill=fill)
    tc = '#FFFFFF' if active else GRAY_T
    if pitch:
        draw.text((vx+vw//2, y0+bh//2), f'{nid} ({pitch})', fill=tc, font=ft_tiny, anchor='mm')
    else:
        draw.text((vx+vw//2, y0+bh//2), '..', fill=tc, font=ft_tiny, anchor='mm')

draw.text((s3_left+s3w//2, vy+len(note_entries)*(bh+2)+2), 'Multi-hot (N=23)', fill=GRAY_T, font=ft_sm, anchor='mt')

# Piano roll with matching pitches
pr_y = vy + len(note_entries)*(bh+2) + 18
pr_bottom = nny + nnh - 10
pr_h = pr_bottom - pr_y
pitches_pr = ['E3','G3','C4','E4','G4','B4','G5']
p_h = pr_h // len(pitches_pr)

pitch_lbl_w = 16
pr_ix = vx + pitch_lbl_w + 2
pr_iw = vw - pitch_lbl_w - 4

for i, p in enumerate(pitches_pr):
    py = pr_y + i*p_h
    draw.line([(pr_ix, py), (pr_ix+pr_iw, py)], fill='#E8E8E8', width=1)
    draw.text((vx+pitch_lbl_w-1, py+p_h//2), p, fill=GRAY_T, font=ft_tiny, anchor='rm')
draw.line([(pr_ix, pr_y+len(pitches_pr)*p_h), (pr_ix+pr_iw, pr_y+len(pitches_pr)*p_h)], fill='#E8E8E8', width=1)

random.seed(77)
ts=5; sw_=pr_iw/ts
for t in range(ts+1):
    draw.line([(pr_ix+t*sw_, pr_y), (pr_ix+t*sw_, pr_y+len(pitches_pr)*p_h)], fill='#EEEEEE', width=1)
for t in range(ts):
    for _ in range(random.randint(1,2)):
        p=random.randint(0, len(pitches_pr)-1)
        nx_=pr_ix+t*sw_+2; ny_=pr_y+(len(pitches_pr)-1-p)*p_h+2
        nw_=sw_-4; nh_=p_h-4
        if nw_>2 and nh_>2:
            draw.rounded_rectangle([(nx_,ny_),(nx_+nw_,ny_+nh_)], radius=2, fill=TEAL)

draw.text((W//2, H-8), 'FC: best for hibari (spatial)  |  Transformer: best for solari (melodic)', fill=GRAY_T, font=ft_label, anchor='mb')

img.save(r'C:\WK14\tda_pipeline\docs\figures\fig_algo2_neural.png', dpi=(150, 150))
print('Saved fig_algo2_neural.png')
