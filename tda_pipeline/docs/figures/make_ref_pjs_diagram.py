"""
vs ref pJS 개념 도식 — v7

  단일 호(arc)로 각 쌍을 연결하고, 레이블은 호 중간 텍스트로만 표시:
  · 원곡 note 17개 ──(파란 점선 호)──→ 생성곡   │ 호 중간: "vs 원곡 pJS"
  · 새 note 집합   ──(주황 점선 호)──→ 생성곡   │ 호 중간: "vs ref pJS"
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

W, H = 15, 9.5          # 데이터 좌표 공간 (박스 위치 계산용, 유지)
fig, ax = plt.subplots(figsize=(12.5, 7.2))
ax.set_xlim(-0.3, 12.8)    # 오른쪽 공백 제거
ax.set_ylim(2.1, 9.5)      # 하단 공백 제거
ax.axis('off')
fig.patch.set_facecolor('white')

C_ORIG  = '#2980B9'
C_PROC  = '#5D6D7E'
C_REF   = '#E67E22'
C_GEN   = '#27AE60'
C_TITLE = '#1C2833'

def rbox(x, y, w, h, color):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0.12",
                       facecolor=color, edgecolor='white',
                       linewidth=1.8, zorder=3, alpha=0.93)
    ax.add_patch(p)

def label(x, y, text, fs=12, color='white', bold=False):
    ax.text(x, y, text, fontsize=fs, color=color,
            fontweight='bold' if bold else 'normal',
            va='center', ha='center', zorder=4)

def arrow_h(x1, y, x2, color='#566573', lw=2):
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                mutation_scale=18), zorder=5)

def arrow_v(x, y1, y2, color='#566573', lw=2):
    ax.annotate('', xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                mutation_scale=18), zorder=5)

def arrow_dashed(x1, y1, x2, y2, color, rad=0.0, lw=2.0):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                linestyle='dashed', mutation_scale=18,
                                connectionstyle=f'arc3,rad={rad}'), zorder=5)

# ── 좌표 설정 ────────────────────────────────────────────────────
BW, BH = 2.7, 1.05

TY  = 7.8
TX1, TX2, TX3 = 0.5, 3.7, 6.9
MX  = TX3
MY3 = 6.2
MY2 = 4.5
MY1 = 2.8

# ── 상단 3개 박스 ────────────────────────────────────────────────
rbox(TX1, TY, BW, BH, C_ORIG)
label(TX1+BW/2, TY+BH*0.65, '원곡 note 17개', fs=13, bold=True)
label(TX1+BW/2, TY+BH*0.28, '(hibari)', fs=10.5, color='#D6EAF8')

rbox(TX2, TY, BW, BH, C_PROC)
label(TX2+BW/2, TY+BH*0.65, 'note_reassign', fs=13, bold=True)
label(TX2+BW/2, TY+BH*0.28, '(전략 A / B)', fs=10.5, color='#D5D8DC')

rbox(TX3, TY, BW, BH, C_REF)
label(TX3+BW/2, TY+BH*0.65, '새 note 집합', fs=13, bold=True)
label(TX3+BW/2, TY+BH*0.28, 'ref 분포', fs=10.5, color='#FDEBD0')

# ── 중앙 3개 박스 ────────────────────────────────────────────────
rbox(MX, MY3, BW, BH, C_PROC)
label(MX+BW/2, MY3+BH*0.65, 'Overlap matrix', fs=13, bold=True)
label(MX+BW/2, MY3+BH*0.28, '재구성', fs=10.5, color='#D5D8DC')

rbox(MX, MY2, BW, BH, C_PROC)
label(MX+BW/2, MY2+BH*0.65, 'DL 재학습', fs=13, bold=True)
label(MX+BW/2, MY2+BH*0.28, '(LSTM / Transformer)', fs=10.5, color='#D5D8DC')

rbox(MX, MY1, BW, BH, C_GEN)
label(MX+BW/2, MY1+BH/2, '생성곡', fs=15, bold=True)

# ── 수평 화살표 (상단 행) ────────────────────────────────────────
arrow_h(TX1+BW, TY+BH/2, TX2)
arrow_h(TX2+BW, TY+BH/2, TX3)

# ── 수직 화살표 (중앙 열) ────────────────────────────────────────
arrow_v(MX+BW/2, TY,   MY3+BH)
arrow_v(MX+BW/2, MY3,  MY2+BH)
arrow_v(MX+BW/2, MY2,  MY1+BH)

# ── 파란 점선 호: 원곡 → 생성곡 (왼쪽 공간 통과, rad=0 직선 대각) ──
# 시작: 원곡 박스 하단 중앙 (1.85, 7.8)
# 끝:   생성곡 박스 왼쪽 중앙 (6.9, 3.325)
arrow_dashed(TX1+BW/2, TY,
             MX, MY1+BH/2,
             color=C_ORIG, rad=0.0)

# 레이블: 직선 중간점 근처 (약 3.9, 5.7)
ax.text(3.7, 5.9, 'vs 원곡 pJS',
        fontsize=12.5, color=C_ORIG, fontweight='bold',
        va='center', ha='center', zorder=8,
        bbox=dict(facecolor='white', edgecolor='none', alpha=0.85, pad=2))

# ── 주황 점선 호: 새 note 집합 → 생성곡 (오른쪽으로 우회) ─────────
# 시작: 새 note 집합 박스 오른쪽 중앙 (9.6, 8.325)
# 끝:   생성곡 박스 오른쪽 중앙 (9.6, 3.325)
# rad=-0.7: 오른쪽(동쪽)으로 볼록하게 휨
arrow_dashed(TX3+BW, TY+BH/2,
             MX+BW, MY1+BH/2,
             color=C_REF, rad=-0.7)

# 레이블: 호의 오른쪽 정점 근처 (약 11.3, 5.8)
ax.text(11.4, 5.8, 'vs ref pJS',
        fontsize=12.5, color=C_REF, fontweight='bold',
        va='center', ha='center', zorder=8,
        bbox=dict(facecolor='white', edgecolor='none', alpha=0.85, pad=2))

# ── 제목 ────────────────────────────────────────────────────────
ax.text(6.25, 9.1,
        'Algorithm 2 (DL) 평가 지표 — vs 원곡 pJS  vs.  vs ref pJS',
        ha='center', va='center', fontsize=13.5,
        fontweight='bold', color=C_TITLE)

plt.tight_layout(pad=0.4)
out = 'C:/WK14/tda_pipeline/docs/figures/fig_ref_pjs_diagram.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
print(f'저장: {out}')
