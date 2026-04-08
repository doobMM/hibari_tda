"""
Figure 1 — 파이프라인 흐름도.
4-stage pipeline: Preprocessing → Homology → Overlap → Generation.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib as mpl

mpl.rcParams['font.size'] = 10

def draw_box(ax, x, y, w, h, text, color, title=None):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.02,rounding_size=0.1",
                         facecolor=color, edgecolor='#2c3e50',
                         linewidth=1.5, zorder=2)
    ax.add_patch(box)
    if title:
        ax.text(x + w/2, y + h - 0.18, title, ha='center', va='top',
                fontsize=11, fontweight='bold', color='#2c3e50')
        ax.text(x + w/2, y + h/2 - 0.15, text, ha='center', va='center',
                fontsize=8.5, color='#34495e')
    else:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=9, color='#2c3e50')

def draw_arrow(ax, x1, y1, x2, y2, label=None):
    arr = FancyArrowPatch((x1, y1), (x2, y2),
                          arrowstyle='-|>', mutation_scale=16,
                          color='#2c3e50', linewidth=1.5, zorder=1)
    ax.add_patch(arr)
    if label:
        mx, my = (x1 + x2)/2, (y1 + y2)/2
        ax.text(mx + 0.05, my, label, ha='left', va='center',
                fontsize=8, color='#555', style='italic')

def main():
    fig, ax = plt.subplots(figsize=(13, 6.5))
    fig.patch.set_facecolor('white')

    # 4 stages horizontally
    stages = [
        {'title': 'Stage 1', 'name': 'Preprocessing',
         'text': 'MIDI → 8분음표\n양자화 →\n두 악기 분리 →\nnote/chord\n레이블링',
         'color': '#fce4ec'},
        {'title': 'Stage 2', 'name': 'Persistent\nHomology',
         'text': '가중치 행렬 →\nrefine → 거리\n행렬 → Vietoris-\nRips → barcode',
         'color': '#e1f5fe'},
        {'title': 'Stage 3', 'name': 'Overlap Matrix',
         'text': 'cycle 활성화\n판정 → scale\n조정 → 이진\n중첩행렬 O',
         'color': '#e8f5e9'},
        {'title': 'Stage 4', 'name': 'Generation',
         'text': 'Algorithm 1\n(sampling)\nor\nAlgorithm 2\n(neural net)',
         'color': '#fff3e0'},
    ]

    box_w, box_h = 2.6, 2.8
    gap = 0.7
    start_x = 0.3
    y0 = 2.2

    positions = []
    for i, s in enumerate(stages):
        x = start_x + i * (box_w + gap)
        draw_box(ax, x, y0, box_w, box_h, s['text'], s['color'], title=s['name'])
        ax.text(x + box_w/2, y0 + box_h + 0.2, s['title'],
                ha='center', fontsize=9, color='#7f8c8d', style='italic')
        positions.append((x, y0, box_w, box_h))

    # Arrows between stages
    for i in range(len(stages) - 1):
        x1 = positions[i][0] + box_w
        x2 = positions[i+1][0]
        y = y0 + box_h/2
        draw_arrow(ax, x1 + 0.05, y, x2 - 0.05, y)

    # Inputs (top) and outputs (bottom)
    # Input: MIDI file
    ax.text(positions[0][0] + box_w/2, y0 + box_h + 0.9,
            'Ryuichi Sakamoto — "hibari"\n(MIDI, 8분음표 단위 T=1088)',
            ha='center', fontsize=9, style='italic', color='#2c3e50')
    draw_arrow(ax, positions[0][0] + box_w/2, y0 + box_h + 0.6,
               positions[0][0] + box_w/2, y0 + box_h + 0.05)

    # Output: MusicXML
    ax.text(positions[-1][0] + box_w/2, y0 - 0.55,
            '생성된 음악 (MusicXML / MIDI)',
            ha='center', fontsize=9, style='italic', color='#2c3e50')
    draw_arrow(ax, positions[-1][0] + box_w/2, y0 - 0.05,
               positions[-1][0] + box_w/2, y0 - 0.35)

    # Key data flow labels below arrows
    data_labels = [
        ('(N=23 notes,\n C=17 chords)', positions[0][0] + box_w + gap/2, y0 - 0.5),
        ('(barcode,\n cycle set)',      positions[1][0] + box_w + gap/2, y0 - 0.5),
        ('(O ∈ R^{T×K})',                positions[2][0] + box_w + gap/2, y0 - 0.5),
    ]
    for txt, lx, ly in data_labels:
        ax.text(lx, ly, txt, ha='center', va='top',
                fontsize=7.5, color='#666', style='italic')

    # Title
    ax.text(6.5, y0 + box_h + 1.6,
            'Figure 1.  TDA Music Pipeline: 4-Stage Flow',
            ha='center', fontsize=13, fontweight='bold', color='#2c3e50')

    ax.set_xlim(-0.3, 13.5)
    ax.set_ylim(-0.2, 6.5)
    ax.set_aspect('equal')
    ax.axis('off')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig1_pipeline.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
