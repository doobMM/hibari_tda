"""
Figure 5 — Piano roll 비교: 원곡 hibari vs Tonnetz-기반 생성곡.
3개의 시간 구간(각 125 timesteps)을 나란히 표시하여 세부가 잘 보이게.
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pickle

def draw_pianoroll(ax, notes, color, t_start, t_end, pitch_range=(40, 90),
                   label=None):
    for (s, p, e) in notes:
        if e < t_start or s > t_end:
            continue
        if pitch_range[0] <= p <= pitch_range[1]:
            s_clip = max(s, t_start)
            e_clip = min(e, t_end)
            w = max(0.8, e_clip - s_clip)
            ax.add_patch(Rectangle((s_clip, p - 0.42), w, 0.84,
                                   facecolor=color, edgecolor='#2c3e50',
                                   linewidth=0.3, alpha=0.9))
    ax.set_xlim(t_start, t_end)
    ax.set_ylim(pitch_range[0] - 1, pitch_range[1] + 1)
    ax.grid(axis='y', alpha=0.2, linestyle='--')
    ax.grid(axis='x', alpha=0.15, linestyle=':')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if label:
        ax.set_ylabel(label, fontsize=9.5, color='#2c3e50')

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import algorithm1_optimized, NodePool, CycleSetManager

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap_df = cache['overlap']
    cycle_labeled = cache['cycle_labeled']
    overlap_values = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df

    random.seed(42); np.random.seed(42)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33
    generated = algorithm1_optimized(
        pool, inst_chord_heights, overlap_values, manager,
        max_resample=50, verbose=False)
    print(f"Generated: {len(generated)} notes")

    # 3개 구간을 뽑음: 시작/중반/후반 (각 125 steps)
    WIN = 125
    segments = [
        (0, WIN,         '1)  $t \\in [0, 125)$   — 곡의 시작'),
        (450, 450 + WIN, '2)  $t \\in [450, 575)$ — 곡의 중반'),
        (900, 900 + WIN, '3)  $t \\in [900, 1025)$ — 곡의 후반'),
    ]

    fig, axes = plt.subplots(3, 3, figsize=(14, 8), sharey=True)
    fig.patch.set_facecolor('white')

    row_configs = [
        (inst1,    '#2980b9', '(a) 원곡 — Inst 1'),
        (inst2,    '#27ae60', '(b) 원곡 — Inst 2'),
        (generated,'#e74c3c', '(c) 생성곡 — Algo 1 + Tonnetz'),
    ]

    for row, (notes, color, row_label) in enumerate(row_configs):
        for col, (t0, t1, seg_label) in enumerate(segments):
            ax = axes[row, col]
            draw_pianoroll(ax, notes, color, t0, t1)
            if col == 0:
                ax.set_ylabel(f'{row_label}\nMIDI Pitch',
                              fontsize=9.5, color='#2c3e50')
            if row == 0:
                ax.set_title(seg_label, fontsize=10.5, color='#2c3e50')
            if row == 2:
                ax.set_xlabel('Time (8분음표 단위)',
                              fontsize=9.5, color='#2c3e50')

    fig.suptitle('Figure 5. Piano Roll 비교 — 원곡 vs Tonnetz 기반 Algorithm 1 생성곡 '
                 '(3개 구간 × 125 timesteps)',
                 fontsize=13, color='#2c3e50', y=0.995)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig5_pianoroll.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
