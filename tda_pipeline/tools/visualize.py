"""
visualize.py — 음악 시각화 (Piano Roll)
========================================

생성된 음악을 piano roll로 시각화합니다.
원곡과 생성곡을 나란히 비교할 수 있습니다.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Tuple, Optional
import os


def plot_piano_roll(notes: List[Tuple[int, int, int]],
                    title: str = "Piano Roll",
                    figsize: Tuple[int, int] = (20, 6),
                    color: str = '#6c63ff',
                    alpha: float = 0.8,
                    save_path: Optional[str] = None,
                    xlim: Optional[Tuple[int, int]] = None,
                    show: bool = True) -> plt.Figure:
    """
    단일 piano roll을 그립니다.

    Args:
        notes: [(start, pitch, end), ...] 음표 리스트
        title: 제목
        xlim: 시간축 범위 (None이면 전체)
    """
    fig, ax = plt.subplots(figsize=figsize)

    pitches = sorted(set(p for _, p, _ in notes))
    pitch_to_y = {p: i for i, p in enumerate(pitches)}

    for start, pitch, end in notes:
        if xlim and (end < xlim[0] or start > xlim[1]):
            continue
        y = pitch_to_y[pitch]
        rect = patches.Rectangle(
            (start, y - 0.4), end - start, 0.8,
            facecolor=color, edgecolor='white', linewidth=0.3, alpha=alpha
        )
        ax.add_patch(rect)

    ax.set_xlim(xlim or (0, max(e for _, _, e in notes) + 1))
    ax.set_ylim(-0.5, len(pitches) - 0.5)
    ax.set_yticks(range(len(pitches)))
    ax.set_yticklabels([str(p) for p in pitches], fontsize=8)
    ax.set_xlabel('Time (eighth notes)', fontsize=10)
    ax.set_ylabel('Pitch', fontsize=10)
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.set_facecolor('#1a1d28')
    fig.patch.set_facecolor('#0f1117')
    ax.tick_params(colors='#8892a0')
    ax.xaxis.label.set_color('#8892a0')
    ax.yaxis.label.set_color('#8892a0')
    ax.title.set_color('#e0e0e0')
    for spine in ax.spines.values():
        spine.set_color('#2a2d3a')

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        print(f"  저장: {save_path}")
    if show:
        plt.show()
    return fig


def plot_comparison(original_notes: List[List[Tuple[int, int, int]]],
                    generated_notes: List[Tuple[int, int, int]],
                    title: str = "원곡 vs 생성곡",
                    figsize: Tuple[int, int] = (20, 10),
                    xlim: Optional[Tuple[int, int]] = None,
                    save_path: Optional[str] = None,
                    show: bool = True) -> plt.Figure:
    """
    원곡과 생성곡의 piano roll을 위아래로 비교합니다.

    Args:
        original_notes: [inst1_notes, inst2_notes]
        generated_notes: [(start, pitch, end), ...]
    """
    # 원곡 통합
    orig_flat = []
    for inst in original_notes:
        orig_flat.extend(inst)

    # 공통 pitch 범위
    all_pitches = sorted(set(
        [p for _, p, _ in orig_flat] + [p for _, p, _ in generated_notes]
    ))
    pitch_to_y = {p: i for i, p in enumerate(all_pitches)}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    fig.patch.set_facecolor('#0f1117')

    colors_orig = ['#4ecdc4', '#ff6b6b']  # inst1=teal, inst2=red
    names = ['원곡 (inst1 + inst2)', '생성곡']

    # 원곡
    for inst_idx, inst_notes in enumerate(original_notes):
        c = colors_orig[inst_idx % len(colors_orig)]
        for start, pitch, end in inst_notes:
            if xlim and (end < xlim[0] or start > xlim[1]):
                continue
            y = pitch_to_y[pitch]
            rect = patches.Rectangle(
                (start, y - 0.4), end - start, 0.8,
                facecolor=c, edgecolor='white', linewidth=0.2, alpha=0.7
            )
            ax1.add_patch(rect)

    # 생성곡
    for start, pitch, end in generated_notes:
        if xlim and (end < xlim[0] or start > xlim[1]):
            continue
        y = pitch_to_y[pitch]
        rect = patches.Rectangle(
            (start, y - 0.4), end - start, 0.8,
            facecolor='#6c63ff', edgecolor='white', linewidth=0.2, alpha=0.7
        )
        ax2.add_patch(rect)

    for ax, name in zip([ax1, ax2], names):
        ax.set_xlim(xlim or (0, max(
            max((e for _, _, e in orig_flat), default=0),
            max((e for _, _, e in generated_notes), default=0)
        ) + 1))
        ax.set_ylim(-0.5, len(all_pitches) - 0.5)
        ax.set_yticks(range(len(all_pitches)))
        ax.set_yticklabels([str(p) for p in all_pitches], fontsize=7)
        ax.set_ylabel(name, fontsize=10, color='#e0e0e0')
        ax.set_facecolor('#1a1d28')
        ax.tick_params(colors='#8892a0')
        for spine in ax.spines.values():
            spine.set_color('#2a2d3a')

    ax2.set_xlabel('Time (eighth notes)', fontsize=10, color='#8892a0')
    fig.suptitle(title, fontsize=14, fontweight='bold', color='#e0e0e0')

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        print(f"  저장: {save_path}")
    if show:
        plt.show()
    return fig
