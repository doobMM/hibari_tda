"""
dashboard_interactive.py — 중첩행렬 편집 + 즉시 음악 생성 대시보드
===================================================================

streamlit run dashboard_interactive.py

핵심:
  - 사전 학습된 모델 로드 (학습 0초)
  - 중첩행렬을 클릭으로 편집
  - 편집 즉시 음악 생성 (~1초)
  - Piano Roll로 원곡과 비교
  - MIDI 다운로드
"""

import streamlit as st
import numpy as np
import pickle, os, sys, time, datetime, io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="TDA Seed Editor", page_icon="🎹", layout="wide")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "models")


@st.cache_resource
def load_models_and_data():
    """사전 학습된 모델과 데이터를 로드합니다."""
    import torch
    from generation import MusicGeneratorFC, MusicGeneratorLSTM

    with open(os.path.join(CACHE_DIR, 'meta.pkl'), 'rb') as f:
        meta = pickle.load(f)

    C, N, T = meta['C'], meta['N'], meta['T']

    # FC 모델
    fc = MusicGeneratorFC(C, N, hidden_dim=256, dropout=0.3)
    fc_state = torch.load(os.path.join(CACHE_DIR, 'fc_best.pt'), weights_only=True)
    fc.load_state_dict(fc_state['model'])
    fc.eval()

    # LSTM 모델
    lstm = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.2)
    lstm_state = torch.load(os.path.join(CACHE_DIR, 'lstm_best.pt'), weights_only=True)
    lstm.load_state_dict(lstm_state['model'])
    lstm.eval()

    # 원본 overlap
    ov_bin = np.load(os.path.join(CACHE_DIR, 'overlap_binary.npy'))
    ov_cont = np.load(os.path.join(CACHE_DIR, 'overlap_continuous.npy'))

    # 원곡 note
    from preprocessing import (load_and_quantize, split_instruments)
    midi = os.path.join(os.path.dirname(__file__), "Ryuichi_Sakamoto_-_hibari.mid")
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

    return {
        'fc': fc, 'lstm': lstm, 'meta': meta,
        'ov_bin': ov_bin, 'ov_cont': ov_cont,
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
    }


def generate_from_overlap(data, overlap, model_name, gap):
    """편집된 overlap으로 즉시 음악 생성."""
    import torch
    from generation import notes_to_xml

    meta = data['meta']
    notes_label = meta['notes_label']
    label_to_note = {v - 1: k for k, v in notes_label.items()}

    if model_name == 'FC':
        model = data['fc']
        X = torch.from_numpy(overlap.astype(np.float32))
        with torch.no_grad():
            logits = model(X)
            probs = torch.sigmoid(logits)
    else:
        model = data['lstm']
        # 모듈 단위 생성
        module_size = 32
        T = overlap.shape[0]
        n_mod = T // module_size
        all_probs = []
        for m in range(n_mod):
            chunk = overlap[m*module_size:(m+1)*module_size]
            X = torch.from_numpy(chunk.astype(np.float32)).unsqueeze(0)
            with torch.no_grad():
                logits = model(X).squeeze(0)
                all_probs.append(torch.sigmoid(logits))
        probs = torch.cat(all_probs, dim=0)

    T_out, N_out = probs.shape
    target_on = 0.15
    k = max(1, int(T_out * N_out * target_on))
    topk_val = torch.topk(probs.flatten(), k).values[-1].item()
    threshold = max(topk_val, 0.1)

    notes = []
    last_onset = -gap
    for t in range(T_out):
        if gap > 0 and (t - last_onset) < gap:
            continue
        onset_here = False
        for n in range(N_out):
            if probs[t, n] >= threshold and n in label_to_note:
                pitch, dur = label_to_note[n]
                notes.append((t, pitch, t + dur))
                onset_here = True
        if onset_here:
            last_onset = t

    return notes


def make_overlap_heatmap(overlap, title="중첩행렬", module_size=32):
    """중첩행렬 히트맵."""
    fig = go.Figure(data=go.Heatmap(
        z=overlap.T, colorscale='Viridis',
        x=list(range(overlap.shape[0])),
        y=[f'C{i}' for i in range(overlap.shape[1])],
        hovertemplate='시점: %{x}<br>Cycle: %{y}<br>값: %{z:.2f}<extra></extra>'
    ))
    # 모듈 경계선
    for m in range(1, overlap.shape[0] // module_size):
        fig.add_vline(x=m * module_size - 0.5, line_dash="dot",
                      line_color="rgba(255,255,255,0.2)")
    fig.update_layout(
        title=title, height=250,
        plot_bgcolor='#1a1d28', paper_bgcolor='#0f1117',
        font=dict(color='#e0e0e0', size=10),
        margin=dict(l=40, r=20, t=35, b=30),
        xaxis=dict(title='시점 (eighth notes)', gridcolor='#2a2d3a'),
        yaxis=dict(title='Cycle', gridcolor='#2a2d3a'),
    )
    return fig


def make_piano_roll(notes, title, color='#6c63ff', xlim=None):
    """Piano roll."""
    fig = go.Figure()
    for s, p, e in notes:
        if xlim and (e < xlim[0] or s > xlim[1]):
            continue
        fig.add_shape(type="rect", x0=s, x1=e, y0=p-0.4, y1=p+0.4,
                      fillcolor=color, line=dict(color='white', width=0.2), opacity=0.7)
        fig.add_trace(go.Scatter(x=[(s+e)/2], y=[p], mode='markers',
                                 marker=dict(size=1, opacity=0),
                                 hovertext=f"pitch={p} t={s} dur={e-s}",
                                 hoverinfo='text', showlegend=False))
    fig.update_layout(
        title=title, height=220,
        plot_bgcolor='#1a1d28', paper_bgcolor='#0f1117',
        font=dict(color='#e0e0e0'), margin=dict(l=40, r=20, t=35, b=30),
        xaxis=dict(range=xlim, gridcolor='#2a2d3a'),
        yaxis=dict(title='Pitch', gridcolor='#2a2d3a'),
    )
    return fig


# ═══════════════════════════════════════════════════════════════
# 메인 UI
# ═══════════════════════════════════════════════════════════════

st.title("🎹 TDA Seed Editor")
st.markdown("중첩행렬을 편집하고 즉시 음악을 생성합니다.")

with st.spinner("모델 로드 중..."):
    data = load_models_and_data()

ov_bin = data['ov_bin']
ov_cont = data['ov_cont']
C = ov_bin.shape[1]
T = ov_bin.shape[0]

# ── 사이드바 ──
st.sidebar.header("⚙️ 설정")

model_choice = st.sidebar.selectbox(
    "생성 모델",
    ["FC (빠름, 안정적)", "LSTM (선율 패턴)"],
    help="FC: 매 순간 독립 판단. LSTM: 흐름을 기억하며 판단."
)
model_name = "FC" if "FC" in model_choice else "LSTM"

gap = st.sidebar.slider("음 사이 최소 간격", 0, 8, 3,
    help="0: 빽빽함, 3: 1.5박 간격 (여유로움)")

view_range = st.sidebar.slider("표시 범위", 0, T, (0, 256), step=32)

st.sidebar.markdown("---")
st.sidebar.header("🎨 중첩행렬 편집")

edit_mode = st.sidebar.radio(
    "편집 도구",
    ["모듈 ON/OFF", "Cycle ON/OFF", "랜덤 변형"],
    help="모듈: 4마디 단위 토글, Cycle: 특정 cycle 전체 토글"
)

# 편집 가능한 overlap을 session_state에 저장
if 'edited_overlap' not in st.session_state:
    st.session_state.edited_overlap = ov_bin.copy()

overlap = st.session_state.edited_overlap

# ── 편집 도구 ──
if edit_mode == "모듈 ON/OFF":
    module_idx = st.sidebar.number_input("모듈 번호 (0~33)", 0, 33, 0)
    cycle_idx = st.sidebar.number_input("Cycle 번호", 0, C-1, 0)
    col1, col2 = st.sidebar.columns(2)
    if col1.button("켜기 ■", use_container_width=True):
        s, e = module_idx * 32, (module_idx + 1) * 32
        overlap[s:e, cycle_idx] = 1.0
        st.session_state.edited_overlap = overlap
    if col2.button("끄기 □", use_container_width=True):
        s, e = module_idx * 32, (module_idx + 1) * 32
        overlap[s:e, cycle_idx] = 0.0
        st.session_state.edited_overlap = overlap

elif edit_mode == "Cycle ON/OFF":
    cycle_idx = st.sidebar.number_input("Cycle 번호", 0, C-1, 0)
    col1, col2 = st.sidebar.columns(2)
    if col1.button("전체 켜기", use_container_width=True):
        overlap[:, cycle_idx] = 1.0
        st.session_state.edited_overlap = overlap
    if col2.button("전체 끄기", use_container_width=True):
        overlap[:, cycle_idx] = 0.0
        st.session_state.edited_overlap = overlap

elif edit_mode == "랜덤 변형":
    noise_pct = st.sidebar.slider("변형 비율 (%)", 1, 30, 5)
    if st.sidebar.button("랜덤 변형 적용"):
        mask = np.random.random(overlap.shape) < (noise_pct / 100)
        overlap[mask] = 1.0 - overlap[mask]
        st.session_state.edited_overlap = overlap

if st.sidebar.button("원본으로 초기화"):
    st.session_state.edited_overlap = ov_bin.copy()
    overlap = st.session_state.edited_overlap

# ── 생성 ──
st.sidebar.markdown("---")
if st.sidebar.button("🎹 음악 생성", type="primary", use_container_width=True):
    t0 = time.time()
    generated = generate_from_overlap(data, overlap, model_name, gap)
    dt = time.time() - t0

    st.session_state.generated = generated
    st.session_state.gen_time = dt
    st.session_state.gen_model = model_name

# ── 메인 영역 ──
col_left, col_right = st.columns([3, 2])

with col_left:
    # 중첩행렬 히트맵
    st.subheader("중첩행렬")
    xlim = list(view_range)
    fig_ov = make_overlap_heatmap(overlap[xlim[0]:xlim[1]],
                                   title=f"중첩행렬 (시점 {xlim[0]}~{xlim[1]})")
    st.plotly_chart(fig_ov, use_container_width=True)

    # 원곡 piano roll
    orig_notes = list(data['inst1_real']) + list(data['inst2_real'])
    fig_orig = make_piano_roll(orig_notes, "원곡 (hibari)", '#4ecdc4', xlim)
    st.plotly_chart(fig_orig, use_container_width=True)

    # 생성곡 piano roll
    if 'generated' in st.session_state:
        gen = st.session_state.generated
        fig_gen = make_piano_roll(gen, f"생성곡 ({st.session_state.gen_model})",
                                  '#6c63ff', xlim)
        st.plotly_chart(fig_gen, use_container_width=True)

with col_right:
    st.subheader("상태")

    # 편집 통계
    on_ratio = overlap.sum() / overlap.size
    st.metric("중첩행렬 ON 비율", f"{on_ratio:.1%}")

    active_cycles = (overlap.sum(axis=0) > 0).sum()
    st.metric("활성 Cycle 수", f"{active_cycles}/{C}")

    diff = np.abs(overlap - ov_bin).sum()
    st.metric("원본 대비 변경량", f"{int(diff)} cells")

    if 'generated' in st.session_state:
        gen = st.session_state.generated
        st.markdown("---")
        st.subheader("생성 결과")
        st.metric("생성 시간", f"{st.session_state.gen_time:.1f}초")
        st.metric("생성 Notes", f"{len(gen)}")
        st.metric("고유 Pitch", f"{len(set(p for _,p,_ in gen))}")

        # MIDI 다운로드
        from generation import notes_to_xml
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"seed_edit_{ts}"
        outdir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(outdir, exist_ok=True)
        notes_to_xml([gen], tempo_bpm=66, file_name=fname, output_dir=outdir)

        xml_path = os.path.join(outdir, f"{fname}.musicxml")
        try:
            from music21 import converter
            midi_path = os.path.join(outdir, f"{fname}.mid")
            converter.parse(xml_path).write('midi', fp=midi_path)
            with open(midi_path, 'rb') as f:
                midi_bytes = f.read()
            st.download_button("⬇️ MIDI 다운로드", data=midi_bytes,
                              file_name=f"{fname}.mid", mime="audio/midi")
        except Exception as e:
            st.warning(f"MIDI 변환 실패: {e}")
