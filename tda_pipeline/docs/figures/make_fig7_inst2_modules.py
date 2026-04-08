"""
Figure 7 — 두 악기의 활성/쉼 패턴 비교 (모듈 반복).

목적: "같은 모듈 구조가 반복되지만, inst 1은 모듈들 사이에 쉼이 거의 없는 반면
      inst 2는 모듈 내/사이에 쉼이 있다"는 것을 강조.

개별 note는 표시하지 않는다. 대신:
- (a) Inst 1 — 한 구간의 activity band (활성=진한 색, 쉼=흰색)
- (b) Inst 2 — 같은 구간의 activity band
  → 두 band를 위아래로 놓고 보면 inst 1의 band는 (거의) 빈칸 없이 이어지고,
    inst 2의 band는 모듈 안에서 일정 간격으로 흰색 공백이 나타난다.
- (c) Inst 2 한 모듈 확대 — 개별 note를 piano roll로 보여주면서
      그 안의 쉼 구조를 자세히.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

MODULE_LEN = 32
N_MODULES = 33
N_SHOW_MODULES = 5  # (a), (b)에서 보여줄 모듈 개수
SHOW_START_MODULE = 4  # 시작 모듈 (0-based)


def compute_active_mask(notes, t_max):
    """시점별 활성/비활성 boolean 배열."""
    active = np.zeros(t_max + 1, dtype=bool)
    for s, _, e in notes:
        active[s:min(e, t_max + 1)] = True
    return active


def draw_activity_band(ax, active_mask, t_start, t_end, color, label):
    """한 악기의 활성도를 얇은 띠 형태로 표시. 활성=진한 색, 쉼=흰색."""
    # 모듈 배경
    for m in range(N_MODULES + 1):
        ms = m * MODULE_LEN
        me = ms + MODULE_LEN
        if me <= t_start or ms >= t_end:
            continue
        rs = max(ms, t_start)
        re = min(me, t_end)
        shade = '#eaf7ec' if m % 2 == 0 else '#f3faf4'
        ax.add_patch(Rectangle((rs, 0), re - rs, 1,
                               facecolor=shade, edgecolor='none', zorder=0))

    # active 구간 찾기 (연속 True 구간)
    in_active = False
    seg_start = 0
    for t in range(t_start, min(t_end, len(active_mask))):
        if active_mask[t] and not in_active:
            in_active = True
            seg_start = t
        elif not active_mask[t] and in_active:
            in_active = False
            ax.add_patch(Rectangle(
                (seg_start, 0.15), t - seg_start, 0.7,
                facecolor=color, edgecolor='#2c3e50',
                linewidth=0.3, zorder=2))
    if in_active:
        t_final = min(t_end, len(active_mask))
        ax.add_patch(Rectangle(
            (seg_start, 0.15), t_final - seg_start, 0.7,
            facecolor=color, edgecolor='#2c3e50',
            linewidth=0.3, zorder=2))

    # 모듈 경계
    for m in range(N_MODULES + 1):
        mt = m * MODULE_LEN
        if t_start <= mt <= t_end:
            ax.axvline(x=mt, color='#27ae60', linewidth=1.4,
                       alpha=0.75, zorder=3)
            module_num = m + 1
            ax.text(mt + MODULE_LEN / 2, 1.08, f'Module {module_num}',
                    fontsize=9.5, color='#27ae60', ha='center',
                    fontweight='bold')

    ax.set_xlim(t_start, t_end)
    ax.set_ylim(-0.05, 1.25)
    ax.set_yticks([])
    ax.set_ylabel(label, fontsize=11, color='#2c3e50',
                  rotation=0, ha='right', va='center', labelpad=15)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)


def draw_inst2_zoom(ax, inst2, t_start, t_end):
    """한 모듈 안 inst 2의 note 구조를 piano roll로 표시."""
    # 모듈 배경
    for m in range(N_MODULES + 1):
        ms = m * MODULE_LEN
        me = ms + MODULE_LEN
        if me <= t_start or ms >= t_end:
            continue
        rs = max(ms, t_start)
        re = min(me, t_end)
        shade = '#eaf7ec' if m % 2 == 0 else '#f3faf4'
        ax.add_patch(Rectangle((rs, 0), re - rs, 100,
                               facecolor=shade, edgecolor='none', zorder=0))

    # pitch range 데이터 기반
    zoom_notes = [(s, p, e) for s, p, e in inst2
                  if not (e < t_start or s > t_end)]
    if zoom_notes:
        z_lo = min(p for _, p, _ in zoom_notes) - 2
        z_hi = max(p for _, p, _ in zoom_notes) + 2
    else:
        z_lo, z_hi = 50, 85

    # 쉼표 구간 흰색 강조
    active = compute_active_mask(inst2, t_end + 1)
    in_rest = False
    rs0 = 0
    for t in range(t_start, t_end):
        if not active[t] and not in_rest:
            in_rest = True
            rs0 = t
        elif active[t] and in_rest:
            in_rest = False
            ax.add_patch(Rectangle((rs0, z_lo - 1), t - rs0,
                                   z_hi - z_lo + 2,
                                   facecolor='white', edgecolor='#95a5a6',
                                   linewidth=0.7, linestyle='--', zorder=1))
            # "REST" 라벨
            ax.text((rs0 + t) / 2, (z_lo + z_hi) / 2, 'REST',
                    ha='center', va='center', fontsize=11,
                    color='#7f8c8d', fontweight='bold',
                    style='italic', zorder=4)
    if in_rest:
        ax.add_patch(Rectangle((rs0, z_lo - 1), t_end - rs0,
                               z_hi - z_lo + 2,
                               facecolor='white', edgecolor='#95a5a6',
                               linewidth=0.7, linestyle='--', zorder=1))
        ax.text((rs0 + t_end) / 2, (z_lo + z_hi) / 2, 'REST',
                ha='center', va='center', fontsize=11,
                color='#7f8c8d', fontweight='bold',
                style='italic', zorder=4)

    # 모듈 경계
    for m in range(N_MODULES + 1):
        mt = m * MODULE_LEN
        if t_start <= mt <= t_end:
            ax.axvline(x=mt, color='#27ae60', linewidth=1.4,
                       alpha=0.75, zorder=3)

    # 노트
    for s, p, e in zoom_notes:
        sc = max(s, t_start)
        ec = min(e, t_end)
        w = max(0.8, ec - sc)
        ax.add_patch(Rectangle(
            (sc, p - 0.42), w, 0.84,
            facecolor='#c0392b', edgecolor='#1a242f',
            linewidth=0.4, alpha=0.92, zorder=5))

    ax.set_xlim(t_start, t_end)
    ax.set_ylim(z_lo - 1, z_hi + 1)
    ax.set_ylabel('MIDI Pitch', fontsize=10, color='#2c3e50')
    ax.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')
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

    T_max = N_MODULES * MODULE_LEN + MODULE_LEN
    active1 = compute_active_mask(inst1, T_max)
    active2 = compute_active_mask(inst2, T_max)
    print(f"inst1 active rate: {active1.mean():.3f}")
    print(f"inst2 active rate: {active2.mean():.3f}")
    print(f"inst1 rest count: {(~active1[:N_MODULES*MODULE_LEN]).sum()}")
    print(f"inst2 rest count: {(~active2[:N_MODULES*MODULE_LEN]).sum()}")

    # (a), (b)에서 보여줄 시간 구간: Modules 5-9 (5개 모듈)
    t_start_show = SHOW_START_MODULE * MODULE_LEN  # 128
    t_end_show = (SHOW_START_MODULE + N_SHOW_MODULES) * MODULE_LEN  # 288

    # (c) zoom: Module 5 한 개만 (t=128~160)
    zoom_start = SHOW_START_MODULE * MODULE_LEN
    zoom_end = (SHOW_START_MODULE + 1) * MODULE_LEN

    fig = plt.figure(figsize=(13, 8.5))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(3, 1, height_ratios=[0.55, 0.55, 1.5],
                          hspace=0.45)

    ax_a = fig.add_subplot(gs[0])
    draw_activity_band(ax_a, active1, t_start_show, t_end_show,
                       color='#2980b9', label='Inst 1\n')
    ax_a.set_title(
        f'(a) Inst 1 — {N_SHOW_MODULES}개 모듈 ($t \\in [{t_start_show}, {t_end_show})$)  '
        '연속된 활성. 모듈 사이에 쉼이 거의 없음',
        fontsize=11, color='#2c3e50', loc='left', pad=10)

    ax_b = fig.add_subplot(gs[1], sharex=ax_a)
    draw_activity_band(ax_b, active2, t_start_show, t_end_show,
                       color='#c0392b', label='Inst 2\n')
    ax_b.set_title(
        '(b) Inst 2 — 같은 구간. 각 모듈마다 시작 부분에 일정한 길이의 쉼',
        fontsize=11, color='#2c3e50', loc='left', pad=10)
    ax_b.set_xlabel('Time (8분음표 단위)', fontsize=10, color='#2c3e50')

    ax_c = fig.add_subplot(gs[2])
    draw_inst2_zoom(ax_c, inst2, zoom_start, zoom_end)
    ax_c.set_title(
        f'(c) Inst 2 한 모듈 확대 (Module {SHOW_START_MODULE+1}, '
        f'$t \\in [{zoom_start}, {zoom_end})$)  '
        '— 쉼 구간 흰색 박스로 강조, note는 빨강',
        fontsize=11, color='#2c3e50', loc='left', pad=10)

    fig.suptitle(
        'Figure 7. 두 악기의 모듈 반복 — Inst 1은 연속, Inst 2는 모듈마다 쉼',
        fontsize=14, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig7_inst2_modules.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
