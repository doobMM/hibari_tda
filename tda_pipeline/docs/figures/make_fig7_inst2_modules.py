"""
Figure 7 — Inst 2 score with module structure highlighted.

- 위쪽: 전체 곡(inst2)의 piano roll, 32 timesteps마다 모듈 경계 표시
  - 모듈 영역은 옅은 초록 배경
  - 쉼표(silence) 구간은 흰색
- 아래쪽: 한 모듈(예: 모듈 5, t∈[160, 192))을 확대하여 구체적 음 배치 표시
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

MODULE_LEN = 32  # 한 모듈 = 32 8분음표 (4박 × 8 = 32 8th notes per 4 bars)
N_MODULES = 33   # 총 33개 모듈


def find_silence_intervals(notes, t_max, pitch_range):
    """notes에서 음이 하나도 없는 timestep 구간들을 반환."""
    active = np.zeros(t_max + 1, dtype=bool)
    for s, p, e in notes:
        if pitch_range[0] <= p <= pitch_range[1]:
            active[s:min(e, t_max)] = True
    intervals = []
    in_rest = False
    rest_start = 0
    for t in range(t_max):
        if not active[t] and not in_rest:
            in_rest = True
            rest_start = t
        elif active[t] and in_rest:
            in_rest = False
            intervals.append((rest_start, t))
    if in_rest:
        intervals.append((rest_start, t_max))
    return intervals


def draw_pianoroll(ax, notes, t_start, t_end, pitch_range,
                   note_color='#2c3e50', show_modules=True,
                   show_rests=True):
    """piano roll + 모듈 배경 + 쉼표 배경."""
    # 모듈 배경 (옅은 초록)
    if show_modules:
        for m in range(N_MODULES + 1):
            ms = m * MODULE_LEN
            me = ms + MODULE_LEN
            if me <= t_start or ms >= t_end:
                continue
            rs = max(ms, t_start)
            re = min(me, t_end)
            # 짝수/홀수 모듈을 약간 다른 진하기로
            shade = '#dff5e1' if m % 2 == 0 else '#e8f8eb'
            ax.add_patch(Rectangle(
                (rs, pitch_range[0] - 1), re - rs,
                pitch_range[1] - pitch_range[0] + 2,
                facecolor=shade, edgecolor='none', zorder=0))

    # 쉼표 (흰색 박스 — 모듈 배경 위에 덮어쓰기)
    if show_rests:
        rests = find_silence_intervals(notes, t_end + 1, pitch_range)
        for rs, re in rests:
            if re < t_start or rs > t_end:
                continue
            rs_c = max(rs, t_start)
            re_c = min(re, t_end)
            if re_c <= rs_c:
                continue
            ax.add_patch(Rectangle(
                (rs_c, pitch_range[0] - 1), re_c - rs_c,
                pitch_range[1] - pitch_range[0] + 2,
                facecolor='white', edgecolor='none', zorder=1))

    # 모듈 경계선 (진한 초록)
    if show_modules:
        for m in range(N_MODULES + 1):
            mt = m * MODULE_LEN
            if t_start <= mt <= t_end:
                ax.axvline(x=mt, color='#27ae60', linewidth=1.0,
                           alpha=0.55, zorder=2)
                # 모듈 번호
                if t_end - t_start < 200:
                    ax.text(mt + 1, pitch_range[1] + 1.5,
                            f'M{m+1}', fontsize=8, color='#27ae60',
                            fontweight='bold')

    # 노트
    for s, p, e in notes:
        if e < t_start or s > t_end:
            continue
        if pitch_range[0] <= p <= pitch_range[1]:
            sc = max(s, t_start)
            ec = min(e, t_end)
            w = max(0.8, ec - sc)
            ax.add_patch(Rectangle(
                (sc, p - 0.42), w, 0.84,
                facecolor=note_color, edgecolor='#1a242f',
                linewidth=0.4, alpha=0.92, zorder=3))

    ax.set_xlim(t_start, t_end)
    ax.set_ylim(pitch_range[0] - 1, pitch_range[1] + 2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.15, linestyle=':')


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    inst2 = p._cache['inst2_real']
    print(f"inst2 length: {len(inst2)}")

    # inst2의 시작/끝 timepoint
    starts = [s for s, _, _ in inst2]
    ends = [e for _, _, e in inst2]
    pitches = [pp for _, pp, _ in inst2]
    print(f"  time range: {min(starts)} – {max(ends)}")
    print(f"  pitch range: {min(pitches)} – {max(pitches)}")

    pitch_range = (40, 90)
    t_start_full = 0
    t_end_full = N_MODULES * MODULE_LEN  # 1056

    fig = plt.figure(figsize=(14, 8.5))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.4], hspace=0.32)

    # ── (a) 전체 곡 ──
    ax_top = fig.add_subplot(gs[0])
    draw_pianoroll(ax_top, inst2, t_start_full, t_end_full, pitch_range,
                   note_color='#2c3e50',
                   show_modules=True, show_rests=True)
    ax_top.set_title(
        '(a) Inst 2 전체 — 33 modules × 32 timesteps = 1,056 timepoints',
        fontsize=11.5, color='#2c3e50', loc='left', pad=8)
    ax_top.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_top.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    # 모듈 번호 (전체 뷰는 너무 빽빽하므로 5개마다)
    for m in range(0, N_MODULES + 1, 5):
        mt = m * MODULE_LEN
        ax_top.text(mt + 2, pitch_range[1] + 1, f'M{m+1}',
                    fontsize=7.5, color='#27ae60', fontweight='bold')

    # ── (b) 모듈 5 확대 (t ∈ [128, 192)) ──
    ax_bot = fig.add_subplot(gs[1])
    zoom_start = 4 * MODULE_LEN   # 128
    zoom_end = 6 * MODULE_LEN     # 192 (2 modules)
    # zoom area의 pitch range를 데이터에 맞춰 좁힘
    z_pitches = [pp for s, pp, e in inst2
                 if not (e < zoom_start or s > zoom_end)]
    if z_pitches:
        z_lo = min(z_pitches) - 2
        z_hi = max(z_pitches) + 2
    else:
        z_lo, z_hi = pitch_range
    draw_pianoroll(ax_bot, inst2, zoom_start, zoom_end, (z_lo, z_hi),
                   note_color='#c0392b',
                   show_modules=True, show_rests=True)
    ax_bot.set_title(
        f'(b) 확대: Modules 5–6 (t ∈ [{zoom_start}, {zoom_end})) — '
        '초록 배경 = 모듈 영역, 흰색 = 쉼표, 빨강 = 음표',
        fontsize=11.5, color='#2c3e50', loc='left', pad=8)
    ax_bot.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_bot.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    # 전체 figure 제목
    fig.suptitle(
        'Figure 7. Inst 2의 모듈 구조와 쉼표 시각화',
        fontsize=14, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig7_inst2_modules.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
