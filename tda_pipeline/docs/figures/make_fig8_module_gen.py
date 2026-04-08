"""
Figure 8 — §7.1 모듈 단위 생성 + 구조적 재배치 결과 시각화.

3 panels:
(a) Prototype module overlap (32 × 46, union over 33 modules) heatmap
(b) 최우수 trial에서 생성된 한 모듈 (32 timesteps)의 piano roll
(c) 재배치된 결과 — inst 1 (33 copies) + inst 2 (32 copies with 1-step rests)
"""
import os, sys, json, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

MODULE_LEN = 32
N_INST1 = 33
N_INST2 = 32
INST2_OFFSET = 33


def regenerate_best():
    """최우수 seed로 module을 재생성하여 결과를 얻는다."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    import random
    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import algorithm1_optimized, NodePool, CycleSetManager

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap_full = cache['overlap'].values
    cycle_labeled = cache['cycle_labeled']
    K = len(cycle_labeled)

    # union overlap
    usable = overlap_full[:N_INST1 * MODULE_LEN].reshape(N_INST1, MODULE_LEN, K)
    overlap_mod = usable.max(axis=0).astype(np.float32)

    # best seed 찾기
    json_path = os.path.join('docs', 'step3_data', 'step71_module_results.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    best_seed = results['summary']['best_seed']
    print(f"Using best seed: {best_seed}")

    # 모듈 재생성
    random.seed(best_seed); np.random.seed(best_seed)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    module_heights = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                      4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    module_notes = algorithm1_optimized(
        pool, module_heights, overlap_mod, manager,
        max_resample=50, verbose=False)

    return overlap_mod, module_notes, p._cache


def replicate_inst1(mod, n, ml):
    out = []
    for m in range(n):
        off = m * ml
        for s, p, e in mod:
            ns = s + off
            ne = min(e + off, off + ml)
            if ns < off + ml and ne > ns:
                out.append((ns, p, ne))
    return out


def replicate_inst2(mod, n, ml, init_off, rest_gap=1):
    out = []
    period = ml + rest_gap
    for m in range(n):
        cs = init_off + m * period
        for s, p, e in mod:
            ns = s + cs
            ne = min(e + cs, cs + ml)
            if ns < cs + ml and ne > ns:
                out.append((ns, p, ne))
    return out


def draw_pianoroll(ax, notes, t_start, t_end, pitch_range, color,
                   module_starts=None, rest_starts=None):
    # 모듈 배경
    if module_starts is not None:
        for ms in module_starts:
            if ms + MODULE_LEN < t_start or ms > t_end:
                continue
            rs = max(ms, t_start)
            re = min(ms + MODULE_LEN, t_end)
            shade = '#eaf7ec' if (ms // MODULE_LEN) % 2 == 0 else '#f3faf4'
            ax.add_patch(Rectangle((rs, pitch_range[0] - 1), re - rs,
                                   pitch_range[1] - pitch_range[0] + 2,
                                   facecolor=shade, edgecolor='none', zorder=0))

    # 쉼 흰색
    if rest_starts is not None:
        for rs, re in rest_starts:
            if re < t_start or rs > t_end:
                continue
            rsc = max(rs, t_start); rec = min(re, t_end)
            ax.add_patch(Rectangle((rsc, pitch_range[0] - 1), rec - rsc,
                                   pitch_range[1] - pitch_range[0] + 2,
                                   facecolor='white', edgecolor='#95a5a6',
                                   linewidth=0.5, linestyle=':', zorder=1))

    # 모듈 경계선
    if module_starts is not None:
        for ms in module_starts:
            if t_start <= ms <= t_end:
                ax.axvline(x=ms, color='#27ae60', linewidth=0.8,
                           alpha=0.55, zorder=2)

    # 노트
    for s, p, e in notes:
        if e < t_start or s > t_end:
            continue
        if pitch_range[0] <= p <= pitch_range[1]:
            sc = max(s, t_start); ec = min(e, t_end)
            w = max(0.6, ec - sc)
            ax.add_patch(Rectangle((sc, p - 0.42), w, 0.84,
                                   facecolor=color, edgecolor='#1a242f',
                                   linewidth=0.3, alpha=0.9, zorder=3))

    ax.set_xlim(t_start, t_end)
    ax.set_ylim(pitch_range[0] - 1, pitch_range[1] + 2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.15, linestyle=':')


def main():
    overlap_mod, module_notes, cache = regenerate_best()
    print(f"Module: {len(module_notes)} notes, pitch range "
          f"[{min(p for _, p, _ in module_notes)}, "
          f"{max(p for _, p, _ in module_notes)}]")

    inst1_rep = replicate_inst1(module_notes, N_INST1, MODULE_LEN)
    inst2_rep = replicate_inst2(module_notes, N_INST2, MODULE_LEN,
                                 INST2_OFFSET, rest_gap=1)
    print(f"Inst1 replicated: {len(inst1_rep)} notes")
    print(f"Inst2 replicated: {len(inst2_rep)} notes")

    # ── Figure ──
    fig = plt.figure(figsize=(14, 10))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(3, 1, height_ratios=[0.9, 1.0, 1.4], hspace=0.42)

    # (a) overlap heatmap
    ax_a = fig.add_subplot(gs[0])
    im = ax_a.imshow(overlap_mod.T, aspect='auto', cmap='Greens',
                     interpolation='nearest', origin='lower')
    ax_a.set_title(
        '(a) Prototype module overlap $O_{\\mathrm{proto}} \\in \\{0,1\\}^{32 \\times 46}$  '
        '— 33개 모듈 위치의 OR (union)로 구축',
        fontsize=11, color='#2c3e50', loc='left', pad=8)
    ax_a.set_xlabel('Timestep within module', fontsize=10, color='#2c3e50')
    ax_a.set_ylabel('Cycle index', fontsize=10, color='#2c3e50')
    plt.colorbar(im, ax=ax_a, shrink=0.8, pad=0.02)

    # (b) generated module piano roll
    ax_b = fig.add_subplot(gs[1])
    mod_pitch_range = (min(p for _, p, _ in module_notes) - 2,
                       max(p for _, p, _ in module_notes) + 2)
    draw_pianoroll(ax_b, module_notes, 0, MODULE_LEN, mod_pitch_range,
                   color='#8e44ad', module_starts=[0])
    ax_b.set_title(
        f'(b) Algorithm 1으로 생성된 단일 모듈 — {len(module_notes)}개 note, '
        f'약 $1$ ms 소요',
        fontsize=11, color='#2c3e50', loc='left', pad=8)
    ax_b.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_b.set_xlabel('Time (module-local)', fontsize=10, color='#2c3e50')

    # (c) full arrangement
    ax_c = fig.add_subplot(gs[2])
    full_pitch = (40, 85)
    # inst 1 module boundaries
    inst1_starts = [m * MODULE_LEN for m in range(N_INST1 + 1)]
    # inst 2 rests = gaps of 1 between copies
    inst2_rests = [(INST2_OFFSET + m * (MODULE_LEN + 1) + MODULE_LEN,
                    INST2_OFFSET + m * (MODULE_LEN + 1) + MODULE_LEN + 1)
                   for m in range(N_INST2)]
    # 초기 silence
    inst2_rests = [(0, INST2_OFFSET)] + inst2_rests
    # 일부 구간만 보여주기: [0, 400) 로 확대
    t_show_start, t_show_end = 0, 400
    # 먼저 inst 1 (파랑)
    draw_pianoroll(ax_c, inst1_rep, t_show_start, t_show_end, full_pitch,
                   color='#2980b9', module_starts=inst1_starts)
    # inst 2 (빨강) 를 겹쳐 그리기 (배경은 다시 그리지 않고 rest만)
    for rs, re in inst2_rests:
        if re < t_show_start or rs > t_show_end:
            continue
        rsc = max(rs, t_show_start); rec = min(re, t_show_end)
        ax_c.add_patch(Rectangle((rsc, full_pitch[0] - 1), rec - rsc,
                                  full_pitch[1] - full_pitch[0] + 2,
                                  facecolor='#fadbd8', edgecolor='none',
                                  alpha=0.5, zorder=1.5))
    for s, p, e in inst2_rep:
        if e < t_show_start or s > t_show_end:
            continue
        if full_pitch[0] <= p <= full_pitch[1]:
            sc = max(s, t_show_start); ec = min(e, t_show_end)
            w = max(0.6, ec - sc)
            ax_c.add_patch(Rectangle((sc, p - 0.42), w, 0.84,
                                      facecolor='#c0392b',
                                      edgecolor='#1a242f',
                                      linewidth=0.3, alpha=0.85, zorder=4))
    ax_c.set_title(
        f'(c) Hibari 구조에 따라 재배치 (처음 400 timesteps만 표시)  '
        '— 파랑 = Inst 1 (33 copies, 쉼 없음), '
        '빨강 = Inst 2 (32 copies, 각 사이 1-step 쉼, 옅은 빨강 띠)',
        fontsize=10.5, color='#2c3e50', loc='left', pad=8)
    ax_c.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_c.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    fig.suptitle(
        'Figure 8. §7.1 모듈 단위 생성 + 구조적 재배치 — '
        'Best trial ($\\mathrm{JS}\\approx 0.030$, baseline 0.0398 대비 24% 개선)',
        fontsize=13, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig8_module_gen.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
