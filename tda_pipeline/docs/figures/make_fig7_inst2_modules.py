"""
Figure 7 — 두 악기의 모듈 구조 비교: inst 1과 inst 2의 쉼표 패턴 shift.

Layout (3 panels, all sharing the same time axis):
  (a) inst 1 전체 piano roll  — 모듈 배경 + 쉼표 흰색
  (b) inst 2 전체 piano roll  — 모듈 배경 + 쉼표 흰색
       → (a)와 (b)를 위아래로 나란히 보면 inst 2의 쉼표가 inst 1보다
         일정하게 오른쪽으로 shift되어 있음을 시각적으로 확인 가능
  (c) Modules 5–6 확대 — 두 악기를 같은 그래프에 색을 달리해 겹쳐 표시,
       모듈 안에서 쉼표가 어떻게 어긋나는지 자세히
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

MODULE_LEN = 32
N_MODULES = 33


def find_silence_intervals(notes, t_max, pitch_range):
    """음이 하나도 없는 timestep 구간들."""
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
                   show_rests=True, label_modules=False):
    # 모듈 배경
    if show_modules:
        for m in range(N_MODULES + 1):
            ms = m * MODULE_LEN
            me = ms + MODULE_LEN
            if me <= t_start or ms >= t_end:
                continue
            rs = max(ms, t_start)
            re = min(me, t_end)
            shade = '#dff5e1' if m % 2 == 0 else '#e8f8eb'
            ax.add_patch(Rectangle(
                (rs, pitch_range[0] - 1), re - rs,
                pitch_range[1] - pitch_range[0] + 2,
                facecolor=shade, edgecolor='none', zorder=0))

    # 쉼표 흰색
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

    # 모듈 경계선
    if show_modules:
        for m in range(N_MODULES + 1):
            mt = m * MODULE_LEN
            if t_start <= mt <= t_end:
                ax.axvline(x=mt, color='#27ae60', linewidth=0.9,
                           alpha=0.55, zorder=2)
                if label_modules:
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


def draw_overlay(ax, inst1, inst2, t_start, t_end, pitch_range):
    """모듈 5-6 zoom — 두 악기를 색을 달리해 같은 그래프에 표시."""
    # 모듈 배경
    for m in range(N_MODULES + 1):
        ms = m * MODULE_LEN
        me = ms + MODULE_LEN
        if me <= t_start or ms >= t_end:
            continue
        rs = max(ms, t_start)
        re = min(me, t_end)
        shade = '#dff5e1' if m % 2 == 0 else '#e8f8eb'
        ax.add_patch(Rectangle(
            (rs, pitch_range[0] - 1), re - rs,
            pitch_range[1] - pitch_range[0] + 2,
            facecolor=shade, edgecolor='none', zorder=0))

    # 두 악기의 쉼표를 따로 계산해서 이중 흰색 사용은 어렵기에,
    # 대신 두 악기 중 *둘 다* silent인 구간만 흰색으로
    active1 = np.zeros(t_end + 1, dtype=bool)
    active2 = np.zeros(t_end + 1, dtype=bool)
    for s, p, e in inst1:
        if pitch_range[0] <= p <= pitch_range[1]:
            active1[s:min(e, t_end + 1)] = True
    for s, p, e in inst2:
        if pitch_range[0] <= p <= pitch_range[1]:
            active2[s:min(e, t_end + 1)] = True
    both_silent = ~active1 & ~active2
    only2_silent = active1 & ~active2  # inst2만 쉼
    only1_silent = ~active1 & active2  # inst1만 쉼

    # 둘 다 쉼: 흰색
    in_rest = False
    rs0 = 0
    for t in range(t_start, t_end):
        if both_silent[t] and not in_rest:
            in_rest = True; rs0 = t
        elif (not both_silent[t]) and in_rest:
            in_rest = False
            ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t - rs0,
                                   pitch_range[1] - pitch_range[0] + 2,
                                   facecolor='white', edgecolor='none', zorder=1))
    if in_rest:
        ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t_end - rs0,
                               pitch_range[1] - pitch_range[0] + 2,
                               facecolor='white', edgecolor='none', zorder=1))

    # inst 1만 활성 (= inst 2 쉼) — 옅은 파랑 띠
    in_zone = False; rs0 = 0
    for t in range(t_start, t_end):
        if only2_silent[t] and not in_zone:
            in_zone = True; rs0 = t
        elif (not only2_silent[t]) and in_zone:
            in_zone = False
            ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t - rs0,
                                   pitch_range[1] - pitch_range[0] + 2,
                                   facecolor='#d6eaf8', edgecolor='none', zorder=1.2))
    if in_zone:
        ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t_end - rs0,
                               pitch_range[1] - pitch_range[0] + 2,
                               facecolor='#d6eaf8', edgecolor='none', zorder=1.2))

    # inst 2만 활성 (= inst 1 쉼) — 옅은 빨강 띠
    in_zone = False; rs0 = 0
    for t in range(t_start, t_end):
        if only1_silent[t] and not in_zone:
            in_zone = True; rs0 = t
        elif (not only1_silent[t]) and in_zone:
            in_zone = False
            ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t - rs0,
                                   pitch_range[1] - pitch_range[0] + 2,
                                   facecolor='#fadbd8', edgecolor='none', zorder=1.2))
    if in_zone:
        ax.add_patch(Rectangle((rs0, pitch_range[0] - 1), t_end - rs0,
                               pitch_range[1] - pitch_range[0] + 2,
                               facecolor='#fadbd8', edgecolor='none', zorder=1.2))

    # 모듈 경계선
    for m in range(N_MODULES + 1):
        mt = m * MODULE_LEN
        if t_start <= mt <= t_end:
            ax.axvline(x=mt, color='#27ae60', linewidth=1.2,
                       alpha=0.7, zorder=2)
            ax.text(mt + 1, pitch_range[1] + 1.3, f'M{m+1}',
                    fontsize=9, color='#27ae60', fontweight='bold')

    # 두 악기 노트
    for inst, color in [(inst1, '#2980b9'), (inst2, '#c0392b')]:
        for s, p, e in inst:
            if e < t_start or s > t_end:
                continue
            if pitch_range[0] <= p <= pitch_range[1]:
                sc = max(s, t_start); ec = min(e, t_end)
                w = max(0.8, ec - sc)
                ax.add_patch(Rectangle(
                    (sc, p - 0.42), w, 0.84,
                    facecolor=color, edgecolor='#1a242f',
                    linewidth=0.4, alpha=0.85, zorder=3))

    ax.set_xlim(t_start, t_end)
    ax.set_ylim(pitch_range[0] - 1, pitch_range[1] + 2.5)
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
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    print(f"inst1: {len(inst1)},  inst2: {len(inst2)}")
    print(f"  inst1 time: {min(s for s,_,_ in inst1)} – {max(e for _,_,e in inst1)}")
    print(f"  inst2 time: {min(s for s,_,_ in inst2)} – {max(e for _,_,e in inst2)}")

    pitch_range_full = (50, 85)
    t_start_full = 0
    t_end_full = N_MODULES * MODULE_LEN + 32  # 1056 + 여유

    fig = plt.figure(figsize=(14, 11))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.0, 1.4],
                          hspace=0.42)

    # ── (a) inst 1 ──
    ax_a = fig.add_subplot(gs[0])
    draw_pianoroll(ax_a, inst1, t_start_full, t_end_full, pitch_range_full,
                   note_color='#2980b9',
                   show_modules=True, show_rests=True)
    ax_a.set_title('(a) Inst 1 — 33 modules × 32 timesteps',
                   fontsize=11.5, color='#2c3e50', loc='left', pad=8)
    ax_a.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    # M1, M6, M11, ... 라벨
    for m in range(0, N_MODULES + 1, 5):
        mt = m * MODULE_LEN
        ax_a.text(mt + 1.5, pitch_range_full[1] + 0.8, f'M{m+1}',
                  fontsize=7.5, color='#27ae60', fontweight='bold')

    # ── (b) inst 2 ──
    ax_b = fig.add_subplot(gs[1], sharex=ax_a)
    draw_pianoroll(ax_b, inst2, t_start_full, t_end_full, pitch_range_full,
                   note_color='#c0392b',
                   show_modules=True, show_rests=True)
    ax_b.set_title('(b) Inst 2 — 같은 시간축. inst 1보다 약 33 timesteps 늦게 입장하며,'
                   ' 모듈마다 쉼표가 일정하게 오른쪽으로 shift됨',
                   fontsize=11.5, color='#2c3e50', loc='left', pad=8)
    ax_b.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_b.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')
    for m in range(0, N_MODULES + 1, 5):
        mt = m * MODULE_LEN
        ax_b.text(mt + 1.5, pitch_range_full[1] + 0.8, f'M{m+1}',
                  fontsize=7.5, color='#27ae60', fontweight='bold')

    # ── (c) Modules 5–6 확대, 두 악기 overlay ──
    ax_c = fig.add_subplot(gs[2])
    zoom_start = 4 * MODULE_LEN  # 128
    zoom_end = 6 * MODULE_LEN    # 192
    z_pitches = ([pp for s, pp, e in inst1
                  if not (e < zoom_start or s > zoom_end)] +
                 [pp for s, pp, e in inst2
                  if not (e < zoom_start or s > zoom_end)])
    z_lo = min(z_pitches) - 2 if z_pitches else pitch_range_full[0]
    z_hi = max(z_pitches) + 2 if z_pitches else pitch_range_full[1]
    draw_overlay(ax_c, inst1, inst2, zoom_start, zoom_end, (z_lo, z_hi))
    ax_c.set_title(f'(c) 확대: Modules 5–6 ($t \\in [{zoom_start}, {zoom_end})$) '
                   '— 파랑=Inst 1, 빨강=Inst 2.  '
                   '옅은 파랑 띠 = Inst 1만 활성 (Inst 2 쉼표),  '
                   '옅은 빨강 띠 = Inst 2만 활성 (Inst 1 쉼표)',
                   fontsize=11, color='#2c3e50', loc='left', pad=8)
    ax_c.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax_c.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    # 범례
    legend_elems = [
        Rectangle((0, 0), 1, 1, facecolor='#2980b9', edgecolor='#1a242f',
                  label='Inst 1 note'),
        Rectangle((0, 0), 1, 1, facecolor='#c0392b', edgecolor='#1a242f',
                  label='Inst 2 note'),
        Rectangle((0, 0), 1, 1, facecolor='#d6eaf8', edgecolor='none',
                  label='Inst 2 rest'),
        Rectangle((0, 0), 1, 1, facecolor='#fadbd8', edgecolor='none',
                  label='Inst 1 rest'),
        Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='#888',
                  label='둘 다 쉼'),
    ]
    ax_c.legend(handles=legend_elems, loc='upper right', fontsize=8,
                framealpha=0.95, ncol=5)

    fig.suptitle(
        'Figure 7. 두 악기의 모듈 구조 — 쉼표 패턴이 modular operation처럼 shift',
        fontsize=14, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig7_inst2_modules.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
