"""Generate Binary vs Continuous overlap matrix comparison (v6).
Correct model: Binary is primary (at least one note in cycle active).
Continuous refines Binary: only cells with binary=1 can have continuous > 0.
Cells that are 0 in Binary are always 0 (white) in Continuous."""
from PIL import Image, ImageDraw, ImageFont
import os, random

W, H = 580, 620
img = Image.new('RGB', (W, H), '#FFFFFF')
draw = ImageDraw.Draw(img)

FD = r'C:\Users\82104\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\c7bf07f7-1002-4049-9e02-01ea99ddb5fe\246d5b4c-791e-4fbf-b7e9-43d2e2418f22\skills\canvas-design\canvas-fonts'
ft_title = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 17)
ft_sec   = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Bold.ttf'), 12)
ft_label = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 10)
ft_sm    = ImageFont.truetype(os.path.join(FD, 'InstrumentSans-Regular.ttf'), 9)
ft_mono  = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 8)
ft_mono2 = ImageFont.truetype(os.path.join(FD, 'GeistMono-Regular.ttf'), 9)

TEAL = '#1A9E96'; TEAL_D = '#0D6B65'; GRAY = '#CCCCCC'; GRAY_T = '#666666'
DARK = '#1A1A1A'; BG = '#F7FAFA'; WARM = '#E8A87C'; WARM_D = '#B07040'

def teal_gradient(v):
    if v < 0.01: return '#FFFFFF'
    rc = int(255 - v*(255-26)); gc = int(255 - v*(255-158)); bc = int(255 - v*(255-150))
    return f'#{rc:02x}{gc:02x}{bc:02x}'

# === DATA MODEL ===
random.seed(42)

NW = {1:0.15, 2:0.08, 3:0.12, 4:0.20, 5:0.10,
      6:0.18, 7:0.05, 8:0.14, 9:0.22, 10:0.09}

CYCLES = [
    [1,3,5],      [2,4,7,9],    [1,6,8],      [3,5,7,10],
    [2,4,6,8,9],  [1,3,9],      [5,6,7,10],   [2,8,9]
]

ACTIVE = []
for t in range(16):
    n_active = random.randint(3, 7)
    ACTIVE.append(set(random.sample(range(1, 11), n_active)))

# Binary: 1 if at least one note in cycle is active at time t (primary criterion)
bin_data = []
for t in range(16):
    row = []
    for c in range(8):
        ns = CYCLES[c]
        row.append(1 if any(n in ACTIVE[t] for n in ns) else 0)
    bin_data.append(row)

# Continuous: weighted ratio, but ONLY where binary=1 (else 0 = white)
cont_data = []
for t in range(16):
    row = []
    for c in range(8):
        if bin_data[t][c] == 1:
            ns = CYCLES[c]
            total = sum(NW[n] for n in ns)
            active = sum(NW[n] for n in ns if n in ACTIVE[t])
            row.append(round(active / total, 2))
        else:
            row.append(0.0)
    cont_data.append(row)

# Example: binary=1 cell with partial activation (0.2 <= cont <= 0.75)
ex_t, ex_c, ex_v = None, None, None
for t in range(16):
    for c in range(8):
        v = cont_data[t][c]
        if bin_data[t][c] == 1 and 0.2 <= v <= 0.75:
            ex_t, ex_c, ex_v = t, c, v
            break
    if ex_t is not None:
        break

# === DRAWING ===
draw.text((W//2, 14), 'Binary vs Continuous Overlap Matrix', fill=DARK, font=ft_title, anchor='mt')
draw.line([(40, 34), (W-40, 34)], fill=GRAY, width=1)

rows, cols = 16, 8
cw, ch = 20, 18

margin = 10; panel_pad = 15; time_label_w = 25
mat_w = cols * cw; mat_h = rows * ch
panel_w = panel_pad + time_label_w + mat_w + panel_pad

left_x = margin
left_r = left_x + panel_w
right_x = W - margin - panel_w
right_r = right_x + panel_w
top_y = 100

# --- LEFT PANEL: Binary ---
draw.rounded_rectangle([(left_x, top_y-56), (left_r, top_y+mat_h+36)],
                       radius=6, fill=BG, outline=GRAY)
left_mat_x = left_x + panel_pad + time_label_w
draw.text((left_mat_x+mat_w//2, top_y-44), 'Binary Overlap', fill=DARK, font=ft_sec, anchor='mt')
draw.text((left_mat_x+mat_w//2, top_y-28), 'O[t,c] = 1 if any n in V(c) active', fill=GRAY_T, font=ft_sm, anchor='mt')

for r in range(rows):
    for c in range(cols):
        x0 = left_mat_x + c*cw; y0 = top_y + r*ch
        fill = TEAL if bin_data[r][c] == 1 else '#FFFFFF'
        draw.rectangle([(x0+1,y0+1),(x0+cw-1,y0+ch-1)], fill=fill)
        draw.rectangle([(x0,y0),(x0+cw,y0+ch)], outline='#E0E0E0', width=1)

for c in range(cols):
    draw.text((left_mat_x+c*cw+cw//2, top_y-2), f'c{c+1}', fill=GRAY_T, font=ft_mono, anchor='mb')
for r in range(0, rows, 4):
    draw.text((left_mat_x-4, top_y+r*ch+ch//2), f't={r+1}', fill=GRAY_T, font=ft_mono, anchor='rm')

bly = top_y + mat_h + 6
draw.rectangle([(left_mat_x,bly),(left_mat_x+10,bly+10)], fill=TEAL, outline=GRAY)
draw.text((left_mat_x+14,bly+5), '1 (active)', fill=GRAY_T, font=ft_sm, anchor='lm')
draw.rectangle([(left_mat_x+80,bly),(left_mat_x+90,bly+10)], fill='#FFF', outline=GRAY)
draw.text((left_mat_x+94,bly+5), '0', fill=GRAY_T, font=ft_sm, anchor='lm')

# --- RIGHT PANEL: Continuous ---
draw.rounded_rectangle([(right_x, top_y-56), (right_r, top_y+mat_h+36)],
                       radius=6, fill=BG, outline=GRAY)
right_mat_x = right_x + panel_pad + time_label_w
draw.text((right_mat_x+mat_w//2, top_y-44), 'Continuous Overlap', fill=DARK, font=ft_sec, anchor='mt')
draw.text((right_mat_x+mat_w//2, top_y-28), 'a(c,t) = weighted ratio (0 if O=0)', fill=GRAY_T, font=ft_sm, anchor='mt')

for r in range(rows):
    for c in range(cols):
        x0 = right_mat_x + c*cw; y0 = top_y + r*ch
        fill = teal_gradient(cont_data[r][c])
        draw.rectangle([(x0+1,y0+1),(x0+cw-1,y0+ch-1)], fill=fill)
        draw.rectangle([(x0,y0),(x0+cw,y0+ch)], outline='#E0E0E0', width=1)

for c in range(cols):
    draw.text((right_mat_x+c*cw+cw//2, top_y-2), f'c{c+1}', fill=GRAY_T, font=ft_mono, anchor='mb')
for r in range(0, rows, 4):
    draw.text((right_mat_x-4, top_y+r*ch+ch//2), f't={r+1}', fill=GRAY_T, font=ft_mono, anchor='rm')

gly = top_y + mat_h + 6; glw = 100
glx = right_mat_x + (mat_w - glw)//2
for i in range(glw):
    draw.line([(glx+i,gly),(glx+i,gly+10)], fill=teal_gradient(i/glw))
draw.rectangle([(glx,gly),(glx+glw,gly+10)], outline=GRAY)
draw.text((glx,gly+13), '0.0', fill=GRAY_T, font=ft_mono, anchor='lt')
draw.text((glx+glw,gly+13), '1.0', fill=GRAY_T, font=ft_mono, anchor='rt')

# --- CENTER: refines arrow (binary → continuous) ---
mid_x = (left_r + right_x) // 2
mid_y = top_y + mat_h // 2
draw.text((mid_x, mid_y-28), 'vs', fill=GRAY_T, font=ft_sec, anchor='mm')
ahalf = min(25, (right_x - left_r - 20)//2)
# Single right-pointing arrow: binary is primary, continuous refines
draw.line([(mid_x-ahalf, mid_y-6),(mid_x+ahalf, mid_y-6)], fill=TEAL, width=2)
draw.polygon([(mid_x+ahalf, mid_y-6),(mid_x+ahalf-5, mid_y-10),(mid_x+ahalf-5, mid_y-2)], fill=TEAL)
draw.text((mid_x, mid_y+8),  'refines:', fill=GRAY_T, font=ft_sm, anchor='mt')
draw.text((mid_x, mid_y+20), 'same cells,', fill=TEAL_D, font=ft_mono, anchor='mt')
draw.text((mid_x, mid_y+32), '+ degree', fill=TEAL_D, font=ft_mono, anchor='mt')

# --- HIGHLIGHT EXAMPLE CELL ---
if ex_t is not None:
    for mx in [left_mat_x, right_mat_x]:
        x0 = mx + ex_c*cw; y0 = top_y + ex_t*ch
        draw.rectangle([(x0-1,y0-1),(x0+cw+1,y0+ch+1)], outline=WARM_D, width=2)

# === BOTTOM: Formula Section ===
bot_y = top_y + mat_h + 48
draw.rounded_rectangle([(margin+5, bot_y), (W-margin-5, bot_y+146)],
                       radius=5, fill='#FFFFFF', outline=TEAL, width=1)
draw.text((W//2, bot_y+8), 'Activation Model', fill=TEAL_D, font=ft_sec, anchor='mt')

draw.text((margin+22, bot_y+28),
          'Binary:     O[t,c] = 1 if exists n in V(c) s.t. n in At  (else 0)',
          fill=DARK, font=ft_mono2, anchor='lt')
draw.text((margin+22, bot_y+44),
          'Continuous: a(c,t) = ( sum w(n)*1[n in At] ) / ( sum w(n) ),  if O[t,c]=1',
          fill=DARK, font=ft_mono2, anchor='lt')
draw.text((margin+22, bot_y+56),
          '                   = 0                                          if O[t,c]=0',
          fill=GRAY_T, font=ft_mono2, anchor='lt')
draw.text((margin+22, bot_y+70),
          'w(n) = rarity weight     V(c) = notes of cycle c     At = active notes at t',
          fill=GRAY_T, font=ft_sm, anchor='lt')

if ex_t is not None:
    ns = CYCLES[ex_c]
    active_ns = [n for n in ns if n in ACTIVE[ex_t]]
    total_w = sum(NW[n] for n in ns)
    active_w = sum(NW[n] for n in active_ns)
    ns_str = ', '.join(f'n{n}' for n in ns)
    act_str = ', '.join(f'n{n}' for n in active_ns) if active_ns else 'none'
    aw_str = ' + '.join(f'{NW[n]:.2f}' for n in active_ns) if active_ns else '0'

    draw.line([(margin+22, bot_y+82), (W-margin-22, bot_y+82)], fill='#E8E8E8', width=1)
    draw.text((margin+22, bot_y+88),
              f'Example (highlighted):  c{ex_c+1} at t={ex_t+1}  — binary=1, partial activation',
              fill=WARM_D, font=ft_label, anchor='lt')
    draw.text((margin+22, bot_y+104),
              f'V(c{ex_c+1}) = {{{ns_str}}}     active: {{{act_str}}}',
              fill=GRAY_T, font=ft_sm, anchor='lt')
    draw.text((margin+22, bot_y+118),
              f'a(c{ex_c+1},{ex_t+1}) = ({aw_str}) / {total_w:.2f} = {ex_v:.2f}   [binary=1, continuous={ex_v:.2f}]',
              fill=DARK, font=ft_mono2, anchor='lt')

draw.text((W//2, bot_y+134),
          'tau=0.5 binarization of continuous overlap: JS -11.4% (Welch t=5.16, p < 0.001)',
          fill=GRAY_T, font=ft_sm, anchor='mt')

img.save(r'C:\WK14\tda_pipeline\docs\figures\fig_overlap_compare.png', dpi=(150, 150))
print(f'Saved. Canvas={W}x{H}')
if ex_t is not None:
    print(f'Example cell: c{ex_c+1} at t={ex_t+1}, a={ex_v:.2f}, binary={bin_data[ex_t][ex_c]}')
