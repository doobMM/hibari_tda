"""
visualize_tonnetz.py — Tonnetz 격자 위 hibari 음들이 빛나는 애니메이션
========================================================================

생성:
  - tonnetz_static.png    : 정적 이미지 (한 장)
  - tonnetz_animation.gif : 시간에 따라 음들이 빛나는 애니메이션
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib.collections import PatchCollection
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Tonnetz 격자 좌표 ──
# Tonnetz는 장3도(가로)와 완전5도(대각선) 관계로 12음을 평면에 배치
# 좌표 변환: pitch class p → (x, y)
#   x축 = 완전5도 방향 (p mod 12 / 12 * fifth_step)
#   y축 = 장3도 방향
# 일반적인 평면 Tonnetz: (x, y) = (5도 방향, 3도 방향)

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def tonnetz_coords():
    """
    Tonnetz를 7행 x 13열 격자에 배치 (반복 구조).
    각 셀의 pitch class 결정:
      - 가로(x++): +7 mod 12 (완전5도)
      - 세로(y++): +4 mod 12 (장3도)
    """
    coords = {}  # pitch_class → list of (x, y)
    rows, cols = 5, 9
    for r in range(rows):
        for c in range(cols):
            # 행마다 1/2 칸 오프셋 (헥사그날 격자)
            x = c + (r % 2) * 0.5
            y = r * np.sqrt(3) / 2
            pc = (c * 7 + r * 4) % 12
            coords.setdefault(pc, []).append((x, y))
    return coords, rows, cols


def get_hibari_note_pitch_classes():
    """hibari에 사용된 23개 note의 pitch class를 반환."""
    from preprocessing import (load_and_quantize, split_instruments,
                                build_note_labels)
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, _, bounds = load_and_quantize(midi)
    inst1, _ = split_instruments(adj, bounds[0])
    inst1_real = inst1[:-59]
    notes_label, _ = build_note_labels(inst1_real[:59])

    # label → (pitch, dur), pitch class 추출
    label_pc = {}
    for (pitch, dur), label in notes_label.items():
        label_pc[label] = (pitch % 12, pitch, dur)
    return label_pc, inst1_real


def get_note_timeline():
    """각 시점에서 어떤 pitch class가 활성화되는지."""
    from preprocessing import (load_and_quantize, split_instruments,
                                build_note_labels)
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, _, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    all_notes = list(inst1_real) + list(inst2_real)
    T = max(e for _, _, e in all_notes)

    # 각 시점에서 활성 pitch class set
    active_per_time = [set() for _ in range(T + 1)]
    for s, p, e in all_notes:
        for t in range(s, min(e, T + 1)):
            active_per_time[t].add(p % 12)

    return active_per_time, T


def draw_static_tonnetz():
    """정적 Tonnetz: hibari에 등장하는 모든 pitch class를 빛나게 표시."""
    coords, rows, cols = tonnetz_coords()
    label_pc, _ = get_hibari_note_pitch_classes()
    used_pcs = set(pc for pc, _, _ in label_pc.values())

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#0f1117')
    ax.set_facecolor('#0f1117')

    # 격자선 그리기 (인접한 셀끼리 연결)
    all_positions = []
    for pc, positions in coords.items():
        for pos in positions:
            all_positions.append((pos, pc))

    # 인접 연결: 거리 < 1.5인 점들 연결
    for i, (p1, pc1) in enumerate(all_positions):
        for p2, pc2 in all_positions[i+1:]:
            d = np.hypot(p1[0]-p2[0], p1[1]-p2[1])
            if 0.4 < d < 1.2:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                        color='#2a2d3a', linewidth=0.8, zorder=1)

    # note 그리기
    for pc, positions in coords.items():
        for x, y in positions:
            is_used = pc in used_pcs
            if is_used:
                # 외곽 빛
                ax.add_patch(Circle((x, y), 0.35, color='#ffd93d',
                                     alpha=0.3, zorder=2))
                ax.add_patch(Circle((x, y), 0.28, color='#ffd93d',
                                     alpha=0.6, zorder=3))
                ax.add_patch(Circle((x, y), 0.22, color='#fff5cc', zorder=4))
                ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                        fontsize=11, fontweight='bold',
                        color='#0f1117', zorder=5)
            else:
                ax.add_patch(Circle((x, y), 0.22,
                                     color='#1a1d28', ec='#444', lw=1, zorder=4))
                ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                        fontsize=10, color='#888', zorder=5)

    ax.set_xlim(-0.5, cols + 0.5)
    ax.set_ylim(-0.3, rows * np.sqrt(3) / 2 + 0.3)
    ax.set_aspect('equal')
    ax.axis('off')

    title = 'Tonnetz Lattice with hibari Notes'
    subtitle = '(Bright = used in hibari, dark = absent)'
    ax.text(cols / 2, rows * np.sqrt(3) / 2 + 0.05, title,
            ha='center', fontsize=18, fontweight='bold', color='#e0e0e0')
    ax.text(cols / 2, -0.15, subtitle,
            ha='center', fontsize=11, color='#888')

    out = os.path.join(os.path.dirname(__file__), 'output', 'tonnetz_static.png')
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    print(f'정적 이미지: {out}')
    plt.close()
    return out


def animate_tonnetz(duration_sec=20, fps=15):
    """
    시간에 따라 hibari의 음들이 Tonnetz 위에서 빛나는 애니메이션.
    1088 시점의 음악을 duration_sec 안에 압축하여 표시.
    """
    coords, rows, cols = tonnetz_coords()
    active_per_time, T = get_note_timeline()

    print(f'  total time points: {T}')
    print(f'  animation: {duration_sec}s @ {fps} fps = {duration_sec*fps} frames')

    n_frames = duration_sec * fps
    # 각 frame이 몇 개 시점을 묶어서 표현할지
    time_per_frame = T / n_frames

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#0f1117')
    ax.set_facecolor('#0f1117')
    ax.set_xlim(-0.5, cols + 0.5)
    ax.set_ylim(-0.3, rows * np.sqrt(3) / 2 + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # 격자선
    all_positions = []
    for pc, positions in coords.items():
        for pos in positions:
            all_positions.append((pos, pc))
    for i, (p1, _) in enumerate(all_positions):
        for p2, _ in all_positions[i+1:]:
            d = np.hypot(p1[0]-p2[0], p1[1]-p2[1])
            if 0.4 < d < 1.2:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                        color='#2a2d3a', linewidth=0.6, zorder=1)

    # 모든 셀에 빈 원 (background)
    bg_circles = {}
    text_objs = {}
    glow_circles = {}
    inner_circles = {}
    for pc, positions in coords.items():
        for x, y in positions:
            bg = Circle((x, y), 0.22, color='#1a1d28',
                        ec='#444', lw=1, zorder=4)
            ax.add_patch(bg)

            glow_outer = Circle((x, y), 0.40, color='#ffd93d',
                                alpha=0, zorder=2)
            glow_inner = Circle((x, y), 0.30, color='#ffd93d',
                                alpha=0, zorder=3)
            inner = Circle((x, y), 0.22, color='#fff5cc',
                           alpha=0, zorder=4)
            ax.add_patch(glow_outer)
            ax.add_patch(glow_inner)
            ax.add_patch(inner)

            txt = ax.text(x, y, NOTE_NAMES[pc], ha='center', va='center',
                          fontsize=10, color='#888', zorder=5)

            key = (round(x, 2), round(y, 2))
            glow_circles[key] = glow_outer
            inner_circles.setdefault(key, []).append((glow_inner, inner, txt))

    # 제목 + 시간 표시
    ax.text(cols / 2, rows * np.sqrt(3) / 2 + 0.35,
            "hibari on Tonnetz Lattice", ha='center',
            fontsize=18, fontweight='bold', color='#e0e0e0')
    time_text = ax.text(cols / 2, -0.1, '', ha='center',
                         fontsize=11, color='#888')

    def init():
        return []

    def update(frame):
        # 이 frame의 시간 범위
        t_start = int(frame * time_per_frame)
        t_end = int((frame + 1) * time_per_frame)
        active_pcs = set()
        for t in range(t_start, min(t_end + 1, len(active_per_time))):
            active_pcs.update(active_per_time[t])

        # 모든 셀 어둡게
        for pc, positions in coords.items():
            for x, y in positions:
                key = (round(x, 2), round(y, 2))
                if key in glow_circles:
                    glow_circles[key].set_alpha(0)
                if key in inner_circles:
                    for gi, ic, tx in inner_circles[key]:
                        gi.set_alpha(0)
                        ic.set_alpha(0)
                        tx.set_color('#888')
                        tx.set_fontweight('normal')

        # 활성 pc만 빛나게
        for pc in active_pcs:
            if pc in coords:
                for x, y in coords[pc]:
                    key = (round(x, 2), round(y, 2))
                    if key in glow_circles:
                        glow_circles[key].set_alpha(0.4)
                    if key in inner_circles:
                        for gi, ic, tx in inner_circles[key]:
                            gi.set_alpha(0.7)
                            ic.set_alpha(1.0)
                            tx.set_color('#0f1117')
                            tx.set_fontweight('bold')

        time_text.set_text(f't = {t_start}/{T} eighth notes')
        return []

    anim = animation.FuncAnimation(fig, update, frames=n_frames,
                                    init_func=init, interval=1000/fps,
                                    blit=False)

    out = os.path.join(os.path.dirname(__file__), 'output', 'tonnetz_animation.gif')
    print(f'  rendering...')
    anim.save(out, writer='pillow', fps=fps,
              savefig_kwargs={'facecolor': '#0f1117'})
    print(f'애니메이션: {out}')
    plt.close()
    return out


if __name__ == "__main__":
    print("=" * 60)
    print("  Tonnetz 격자 시각화")
    print("=" * 60)

    print("\n[1] 정적 이미지 생성...")
    draw_static_tonnetz()

    print("\n[2] 애니메이션 생성 (20초)...")
    animate_tonnetz(duration_sec=20, fps=15)

    print("\n완료!")
