"""
Figure 5 — Piano roll 비교: 원곡 hibari vs Tonnetz-기반 생성곡.
원곡은 MIDI에서, 생성곡은 fresh Algorithm 1 실행으로.
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pickle

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def draw_pianoroll(ax, notes, title, color, T=1088, pitch_range=(40, 90)):
    """notes: list of (start, pitch, end)"""
    for (s, p, e) in notes:
        if pitch_range[0] <= p <= pitch_range[1]:
            w = max(1, e - s)
            ax.add_patch(Rectangle((s, p - 0.4), w, 0.8,
                                   facecolor=color, edgecolor='none',
                                   alpha=0.85))
    ax.set_xlim(0, T)
    ax.set_ylim(pitch_range[0] - 1, pitch_range[1] + 1)
    ax.set_ylabel('MIDI Pitch', fontsize=9, color='#2c3e50')
    ax.set_title(title, fontsize=11, color='#2c3e50', loc='left', pad=6)
    ax.grid(axis='y', alpha=0.2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

def main():
    # chdir to tda_pipeline root so hibari.mid is found
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import algorithm1_optimized, NodePool, CycleSetManager

    # 전처리
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']

    # Tonnetz 캐시 로드
    with open(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                           'cache', 'metric_tonnetz.pkl')), 'rb') as f:
        cache = pickle.load(f)
    overlap_df = cache['overlap']
    cycle_labeled = cache['cycle_labeled']
    overlap_values = overlap_df.values if hasattr(overlap_df, 'values') else overlap_df

    # 생성 한 번
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

    # Figure: 3 rows — orig inst1, orig inst2, generated
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    fig.patch.set_facecolor('white')

    draw_pianoroll(axes[0], inst1,
                   '(a) 원곡 — 악기 1 (Inst 1)',
                   color='#2980b9')
    draw_pianoroll(axes[1], inst2,
                   '(b) 원곡 — 악기 2 (Inst 2)',
                   color='#27ae60')
    draw_pianoroll(axes[2], generated,
                   '(c) 생성곡 — Algorithm 1 + Tonnetz (K=46, seed=42)',
                   color='#e74c3c')
    axes[2].set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    fig.suptitle('Figure 5. Piano Roll 비교 — 원곡 vs Tonnetz 기반 Algorithm 1 생성곡',
                 fontsize=13, color='#2c3e50', y=0.995)

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig5_pianoroll.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
