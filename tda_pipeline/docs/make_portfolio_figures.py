"""포트폴리오 보고서 전용 추가 그림 생성"""

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from pathlib import Path

# ── 전역 스타일 설정 ─────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "Malgun Gothic",
    "axes.unicode_minus": False,
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

OUT = Path(r"C:\WK14\tda_pipeline\docs\figures")
OUT.mkdir(exist_ok=True)

# 색상 팔레트
C_MAIN   = "#1d3557"
C_ACC    = "#e63946"
C_BLUE   = "#457b9d"
C_LIGHT  = "#a8dadc"
C_BG     = "#f1faee"
C_GOLD   = "#d4a017"
PALETTE  = ["#457b9d", "#e63946", "#a8dadc", "#f4a261"]


# ═══════════════════════════════════════════════════════════════
# PF-1. 거리 함수 비교 막대그래프
# ═══════════════════════════════════════════════════════════════
def pf1_distance_comparison():
    metrics  = ["Frequency\n(빈도)", "DFT", "Tonnetz", "Voice-\nleading\n(성부진행)"]
    js_vals  = [0.0753, 0.0511, 0.0398, 0.0891]
    colors   = ["#adb5bd", "#6c757d", C_ACC, "#adb5bd"]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(metrics, js_vals, color=colors, edgecolor="white", linewidth=1.5, width=0.55)

    # 수치 표시
    for bar, v in zip(bars, js_vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.002,
                f"{v:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Tonnetz에 화살표 주석
    ax.annotate("−47%", xy=(2, 0.0398), xytext=(2.7, 0.065),
                fontsize=12, fontweight="bold", color=C_ACC,
                arrowprops=dict(arrowstyle="->", color=C_ACC, lw=2))

    ax.set_ylabel("JS Divergence (낮을수록 좋음)", fontsize=11)
    ax.set_ylim(0, 0.11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("거리 함수별 생성 품질 비교 (N=20)", fontsize=13, fontweight="bold", pad=12)

    fig.savefig(OUT / "pf1_distance_comparison.png")
    plt.close()
    print("  ✓ pf1_distance_comparison.png")


# ═══════════════════════════════════════════════════════════════
# PF-2. 누적 개선 과정 (waterfall)
# ═══════════════════════════════════════════════════════════════
def pf2_improvement_waterfall():
    stages = [
        "① 기준선\n(빈도거리)",
        "② Tonnetz\n교체",
        "③ 연속값\n중첩행렬",
        "④ 신경망 FC\n(이진 입력)",
        "⑤ 신경망 FC\n(연속값 입력)"
    ]
    js_vals = [0.0753, 0.0398, 0.0343, 0.0014, 0.0004]
    improvements = ["", "−47%", "−14%", "−96%", "−71%"]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#adb5bd", "#457b9d", "#457b9d", "#e63946", "#e63946"]
    bars = ax.bar(range(len(stages)), js_vals, color=colors,
                  edgecolor="white", linewidth=1.5, width=0.6)

    for i, (bar, v, imp) in enumerate(zip(bars, js_vals, improvements)):
        y = v + 0.003
        ax.text(bar.get_x() + bar.get_width()/2, y,
                f"{v:.4f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
        if imp:
            ax.text(bar.get_x() + bar.get_width()/2, y + 0.007,
                    imp, ha="center", va="bottom", fontsize=8, color=C_ACC, fontweight="bold")

    # 화살표로 흐름 표시
    for i in range(len(stages)-1):
        ax.annotate("", xy=(i+1, js_vals[i+1] + 0.001),
                    xytext=(i, js_vals[i] + 0.001),
                    arrowprops=dict(arrowstyle="->", color="#999999", lw=1.2))

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages, fontsize=8.5)
    ax.set_ylabel("JS Divergence", fontsize=11)
    ax.set_ylim(0, 0.095)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("단계별 누적 개선 과정", fontsize=13, fontweight="bold", pad=12)

    fig.savefig(OUT / "pf2_improvement_waterfall.png")
    plt.close()
    print("  ✓ pf2_improvement_waterfall.png")


# ═══════════════════════════════════════════════════════════════
# PF-3. 곡별 최적 거리 기준 비교
# ═══════════════════════════════════════════════════════════════
def pf3_cross_song():
    songs = ["hibari", "solari", "aqua", "Bach\nFugue", "Ravel\nPavane"]
    freq_js    = [0.0753, 0.0643, 0.1249, 0.0902, 0.0337]
    tonnetz_js = [0.0398, 0.0816, 0.0920, 0.0408, 0.0387]
    vl_js      = [0.0891, 0.0631, None,   0.1242, 0.0798]
    # None → NaN for plotting
    vl_js_plot = [v if v is not None else 0 for v in vl_js]
    vl_mask    = [v is not None for v in vl_js]

    x = np.arange(len(songs))
    w = 0.22

    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - w, freq_js, w, label="Frequency (빈도)", color="#adb5bd", edgecolor="white")
    b2 = ax.bar(x, tonnetz_js, w, label="Tonnetz", color=C_ACC, edgecolor="white")
    b3_vals = [v if m else 0 for v, m in zip(vl_js_plot, vl_mask)]
    b3 = ax.bar(x + w, b3_vals, w, label="Voice-leading (성부진행)", color=C_BLUE, edgecolor="white")

    # 최적 표시 (별)
    best_indices = [1, 2, 1, 1, 0]  # tonnetz, vl, tonnetz, tonnetz, freq
    best_vals    = [0.0398, 0.0631, 0.0920, 0.0408, 0.0337]
    best_x       = [x[0], x[1]+w, x[2], x[3], x[4]-w]
    for bx, bv in zip(best_x, best_vals):
        ax.text(bx, bv + 0.004, "★", ha="center", fontsize=14, color=C_GOLD)

    ax.set_xticks(x)
    ax.set_xticklabels(songs, fontsize=10)
    ax.set_ylabel("JS Divergence (낮을수록 좋음)", fontsize=11)
    ax.legend(fontsize=9, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, 0.15)
    ax.set_title("곡별 최적 거리 기준 — ★ 표시가 각 곡의 최적", fontsize=13, fontweight="bold", pad=12)

    fig.savefig(OUT / "pf3_cross_song.png")
    plt.close()
    print("  ✓ pf3_cross_song.png")


# ═══════════════════════════════════════════════════════════════
# PF-4. 옥타브 가중치 튜닝 곡선
# ═══════════════════════════════════════════════════════════════
def pf4_octave_tuning():
    ow  = [0.1, 0.3, 0.5, 0.7, 1.0]
    js  = [0.0516, 0.0479, 0.0590, 0.0720, 0.0719]
    cyc = [50, 47, 42, 38, 35]

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax2 = ax1.twinx()

    ln1 = ax1.plot(ow, js, "o-", color=C_ACC, linewidth=2.5, markersize=9, label="JS Divergence", zorder=5)
    ln2 = ax2.plot(ow, cyc, "s--", color=C_BLUE, linewidth=1.8, markersize=7, label="Cycle 수", zorder=3)

    # 최적점 강조
    ax1.scatter([0.3], [0.0479], s=200, facecolors="none", edgecolors=C_ACC, linewidths=2.5, zorder=6)
    ax1.annotate("최적: 0.3", xy=(0.3, 0.0479), xytext=(0.5, 0.044),
                fontsize=11, fontweight="bold", color=C_ACC,
                arrowprops=dict(arrowstyle="->", color=C_ACC, lw=1.5))

    ax1.set_xlabel("옥타브 가중치 (octave weight)", fontsize=11)
    ax1.set_ylabel("JS Divergence", fontsize=11, color=C_ACC)
    ax2.set_ylabel("발견된 Cycle 수", fontsize=11, color=C_BLUE)
    ax1.tick_params(axis="y", labelcolor=C_ACC)
    ax2.tick_params(axis="y", labelcolor=C_BLUE)

    lns = ln1 + ln2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, fontsize=9, loc="upper left")

    ax1.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax1.set_title("옥타브 가중치 튜닝 (N=10)", fontsize=13, fontweight="bold", pad=12)

    fig.savefig(OUT / "pf4_octave_tuning.png")
    plt.close()
    print("  ✓ pf4_octave_tuning.png")


# ═══════════════════════════════════════════════════════════════
# PF-5. 파이프라인 개념도 (코드블록 대체용, 한글 안전)
# ═══════════════════════════════════════════════════════════════
def pf5_pipeline_simple():
    """4단계 파이프라인을 깔끔한 도식으로"""
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.set_xlim(-0.5, 10)
    ax.set_ylim(-0.5, 3)
    ax.axis("off")

    boxes = [
        (0.3,  "1단계\n전처리",       "MIDI → 양자화\n두 악기 분리\n음 레이블링",  "#e8f0fe"),
        (2.8,  "2단계\n위상 분석",    "가중치 행렬\n→ 거리 행렬\n→ Barcode",       "#fff3cd"),
        (5.3,  "3단계\n중첩행렬",     "Cycle 활성화\n시간 × Cycle\n이진/연속값",   "#d4edda"),
        (7.8,  "4단계\n생성",         "Algorithm 1 (규칙)\nAlgorithm 2 (신경망)\n→ 새 곡",  "#f8d7da"),
    ]

    for x, title, desc, color in boxes:
        rect = mpl.patches.FancyBboxPatch(
            (x, 0.1), 2.0, 2.5, boxstyle="round,pad=0.12",
            facecolor=color, edgecolor="#555555", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x+1.0, 2.15, title, ha="center", va="center",
                fontsize=11, fontweight="bold", color=C_MAIN)
        ax.text(x+1.0, 1.0, desc, ha="center", va="center",
                fontsize=8.5, color="#333333", linespacing=1.5)

    # 화살표
    for x in [2.3, 4.8, 7.3]:
        ax.annotate("", xy=(x+0.5, 1.35), xytext=(x, 1.35),
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=2))

    ax.text(5.0, -0.3, "원곡 MIDI  ────────────────────────────────→  생성된 음악 (MusicXML / MIDI / WAV)",
            ha="center", fontsize=9, color="#888888", style="italic")

    fig.savefig(OUT / "pf5_pipeline_simple.png")
    plt.close()
    print("  ✓ pf5_pipeline_simple.png")


# ═══════════════════════════════════════════════════════════════
# PF-6. "곡의 성격이 도구를 결정한다" 요약 표 (그래픽)
# ═══════════════════════════════════════════════════════════════
def pf6_song_character_summary():
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)

    # 헤더
    headers = ["곡", "음 특성", "최적 거리", "최적 모델", "핵심 해석"]
    hx = [0.8, 2.3, 4.0, 5.6, 7.8]
    for x, h in zip(hx, headers):
        ax.text(x, 4.5, h, ha="center", va="center", fontsize=10,
                fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=C_MAIN, edgecolor="none"))

    rows = [
        ("hibari",      "7음 (장조)",  "Tonnetz",    "FC",          "공간적 배치"),
        ("solari",      "12음",        "Voice-lead", "Transformer", "선율적 진행"),
        ("Bach Fugue",  "12음",        "Tonnetz",    "—",           "숨은 화성 구조"),
        ("Ravel Pavane","12음 (N=49)", "Frequency",  "FC",          "풍부한 분포"),
    ]

    for i, row in enumerate(rows):
        y = 3.5 - i * 0.9
        bg = "#f7f9ff" if i % 2 == 0 else "white"
        rect = mpl.patches.Rectangle((0, y-0.35), 10, 0.7, facecolor=bg, edgecolor="#dddddd", linewidth=0.5)
        ax.add_patch(rect)
        for x, val in zip(hx, row):
            fw = "bold" if x == hx[0] else "normal"
            c = C_ACC if val in ("Tonnetz", "Voice-lead", "Frequency") else "#333333"
            ax.text(x, y, val, ha="center", va="center", fontsize=9, fontweight=fw, color=c)

    fig.savefig(OUT / "pf6_song_character.png")
    plt.close()
    print("  ✓ pf6_song_character.png")


if __name__ == "__main__":
    print("포트폴리오 그림 생성 중...")
    pf1_distance_comparison()
    pf2_improvement_waterfall()
    pf3_cross_song()
    pf4_octave_tuning()
    pf5_pipeline_simple()
    pf6_song_character_summary()
    print("완료.")
