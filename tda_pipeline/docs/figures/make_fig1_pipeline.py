"""
Figure 1 — 파이프라인 흐름도.
4-stage pipeline: Preprocessing → Homology → Overlap → Generation.

개선사항: 글자 키우고 공백 줄이기 + Stage 3에서 연속값 overlap도 언급.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib as mpl

mpl.rcParams['font.size'] = 11

def draw_box(ax, x, y, w, h, text, color, title=None):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.015,rounding_size=0.08",
                         facecolor=color, edgecolor='#2c3e50',
                         linewidth=1.6, zorder=2)
    ax.add_patch(box)
    if title:
        ax.text(x + w/2, y + h - 0.22, title, ha='center', va='top',
                fontsize=13, fontweight='bold', color='#2c3e50')
        ax.text(x + w/2, y + h/2 - 0.25, text, ha='center', va='center',
                fontsize=10.5, color='#34495e', linespacing=1.35)
    else:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=11, color='#2c3e50')

def draw_arrow(ax, x1, y1, x2, y2):
    arr = FancyArrowPatch((x1, y1), (x2, y2),
                          arrowstyle='-|>', mutation_scale=22,
                          color='#2c3e50', linewidth=2.0, zorder=1)
    ax.add_patch(arr)

def main():
    fig, ax = plt.subplots(figsize=(13, 5.2))
    fig.patch.set_facecolor('white')

    stages = [
        {'title': 'Stage 1', 'name': 'Preprocessing',
         'text': 'MIDI → 8분음표\n양자화 →\n두 악기 분리 →\nnote / chord\n레이블링',
         'color': '#fce4ec'},
        {'title': 'Stage 2', 'name': 'Persistent\nHomology',
         'text': '가중치 행렬 →\nrefine → 거리\n행렬 → Vietoris-\nRips → barcode',
         'color': '#e1f5fe'},
        {'title': 'Stage 3', 'name': 'Overlap Matrix',
         'text': 'cycle 활성화 판정\n→ scale 조정 →\n이진 중첩행렬\n$O \\in \\{0,1\\}^{T\\times K}$\n(연속값 변형 가능)',
         'color': '#e8f5e9'},
        {'title': 'Stage 4', 'name': 'Generation',
         'text': 'Algorithm 1\n(확률적 샘플링)\n또는\nAlgorithm 2\n(FC / LSTM /\nTransformer)',
         'color': '#fff3e0'},
    ]

    # 빡빡하게 — gap을 줄이고 box를 키움
    box_w, box_h = 2.75, 2.6
    gap = 0.35
    start_x = 0.25
    y0 = 1.15

    positions = []
    for i, s in enumerate(stages):
        x = start_x + i * (box_w + gap)
        draw_box(ax, x, y0, box_w, box_h, s['text'], s['color'], title=s['name'])
        ax.text(x + box_w/2, y0 + box_h + 0.12, s['title'],
                ha='center', fontsize=10.5, color='#7f8c8d', style='italic')
        positions.append((x, y0, box_w, box_h))

    # 화살표
    for i in range(len(stages) - 1):
        x1 = positions[i][0] + box_w
        x2 = positions[i+1][0]
        y = y0 + box_h/2
        draw_arrow(ax, x1 + 0.02, y, x2 - 0.02, y)

    # Input (위)
    input_x = positions[0][0] + box_w/2
    ax.text(input_x, y0 + box_h + 0.75,
            'Ryuichi Sakamoto — "hibari" (MIDI, $T=1088$ 8분음표 시점)',
            ha='center', fontsize=10.5, style='italic', color='#2c3e50')
    draw_arrow(ax, input_x, y0 + box_h + 0.55,
               input_x, y0 + box_h + 0.03)

    # Output (아래)
    out_x = positions[-1][0] + box_w/2
    ax.text(out_x, y0 - 0.55,
            '생성된 음악 (MusicXML / MIDI)',
            ha='center', fontsize=10.5, style='italic', color='#2c3e50')
    draw_arrow(ax, out_x, y0 - 0.03, out_x, y0 - 0.35)

    # Title
    ax.text(6.5, y0 + box_h + 1.2,
            'Figure 1.  TDA Music Pipeline: 4-Stage Flow',
            ha='center', fontsize=14, fontweight='bold', color='#2c3e50')

    ax.set_xlim(-0.1, 13.1)
    ax.set_ylim(-1.0, 5.6)
    ax.set_aspect('equal')
    ax.axis('off')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig1_pipeline.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
