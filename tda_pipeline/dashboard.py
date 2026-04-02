"""
dashboard.py — TDA Music Pipeline 인터랙티브 대시보드
=====================================================

streamlit run dashboard.py

기능:
  - Algorithm 1/2 선택 + 하이퍼파라미터 조절
  - min_onset_gap 슬라이더
  - cycle subset K 선택
  - 인터랙티브 piano roll (hover → note 정보)
  - 생성된 음악 재생 (MIDI → WAV)
  - 원곡 vs 생성곡 비교
  - 평가 지표 실시간 표시
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import os, sys, time, tempfile, io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="TDA Music Pipeline",
    page_icon="🎵",
    layout="wide"
)


# ═══════════════════════════════════════════════════════════════════════════
# 캐싱: 데이터를 한 번만 로드
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def load_pipeline_data():
    """파이프라인 데이터를 로드하고 캐싱합니다."""
    import pandas as pd
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences,
        simul_chord_lists, simul_union_by_dict
    )
    from overlap import (
        label_cycles_from_persistence, build_activation_matrix,
        build_overlap_matrix
    )

    midi_file = os.path.join(os.path.dirname(__file__),
                             "Ryuichi_Sakamoto_-_hibari.mid")

    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    module_notes = inst1_real[:59]
    notes_label, notes_counts = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, cs1 = build_chord_labels(active1)
    _, cs2 = build_chord_labels(active2)
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    # Persistence from pkl
    pkl_path = os.path.join(os.path.dirname(__file__),
                            "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    df = pd.read_pickle(pkl_path)
    persistence = {}
    for _, row in df.iterrows():
        persistence.setdefault(row['cycle'], []).append(
            (row['rate'], row['birth'], row['death']))
    cycle_labeled = label_cycles_from_persistence(persistence)

    # Overlap matrix
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))
    T = 1088
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled, threshold=0.35, total_length=T)

    return {
        'overlap': overlap,
        'cycle_labeled': cycle_labeled,
        'notes_dict': notes_dict,
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'inst1_real': inst1_real,
        'inst2_real': inst2_real,
        'adn_i': adn_i,
        'T': T,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Piano Roll (Plotly)
# ═══════════════════════════════════════════════════════════════════════════

def make_piano_roll(notes, title="Piano Roll", color='#6c63ff', xlim=None):
    """인터랙티브 piano roll을 Plotly로 생성합니다."""
    fig = go.Figure()

    for start, pitch, end in notes:
        if xlim and (end < xlim[0] or start > xlim[1]):
            continue
        fig.add_shape(
            type="rect",
            x0=start, x1=end, y0=pitch - 0.4, y1=pitch + 0.4,
            fillcolor=color, line=dict(color='white', width=0.3),
            opacity=0.8,
        )
        # Hover용 투명 scatter
        fig.add_trace(go.Scatter(
            x=[(start + end) / 2], y=[pitch],
            mode='markers', marker=dict(size=1, opacity=0),
            hoverinfo='text',
            hovertext=f"pitch={pitch}, start={start}, dur={end-start}",
            showlegend=False
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Time (eighth notes)",
        yaxis_title="Pitch",
        plot_bgcolor='#1a1d28',
        paper_bgcolor='#0f1117',
        font=dict(color='#e0e0e0'),
        height=300,
        margin=dict(l=50, r=20, t=40, b=40),
        xaxis=dict(range=xlim, gridcolor='#2a2d3a'),
        yaxis=dict(gridcolor='#2a2d3a'),
    )
    return fig


def make_comparison_roll(orig_notes_list, gen_notes, xlim=None):
    """원곡 vs 생성곡 비교 piano roll."""
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Original", "Generated"],
                        vertical_spacing=0.08)

    colors_orig = ['#4ecdc4', '#ff6b6b']
    for inst_idx, inst_notes in enumerate(orig_notes_list):
        c = colors_orig[inst_idx % 2]
        for s, p, e in inst_notes:
            if xlim and (e < xlim[0] or s > xlim[1]):
                continue
            fig.add_shape(type="rect", row=1, col=1,
                          x0=s, x1=e, y0=p-0.4, y1=p+0.4,
                          fillcolor=c, line=dict(width=0.2, color='white'), opacity=0.7)
            fig.add_trace(go.Scatter(x=[(s+e)/2], y=[p], mode='markers',
                                     marker=dict(size=1, opacity=0),
                                     hovertext=f"p={p} t={s} d={e-s}",
                                     hoverinfo='text', showlegend=False), row=1, col=1)

    for s, p, e in gen_notes:
        if xlim and (e < xlim[0] or s > xlim[1]):
            continue
        fig.add_shape(type="rect", row=2, col=1,
                      x0=s, x1=e, y0=p-0.4, y1=p+0.4,
                      fillcolor='#6c63ff', line=dict(width=0.2, color='white'), opacity=0.7)
        fig.add_trace(go.Scatter(x=[(s+e)/2], y=[p], mode='markers',
                                 marker=dict(size=1, opacity=0),
                                 hovertext=f"p={p} t={s} d={e-s}",
                                 hoverinfo='text', showlegend=False), row=2, col=1)

    fig.update_layout(
        height=500, plot_bgcolor='#1a1d28', paper_bgcolor='#0f1117',
        font=dict(color='#e0e0e0'),
        margin=dict(l=50, r=20, t=40, b=40),
    )
    if xlim:
        fig.update_xaxes(range=xlim)
    fig.update_xaxes(gridcolor='#2a2d3a')
    fig.update_yaxes(gridcolor='#2a2d3a')
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# 음악 생성 함수
# ═══════════════════════════════════════════════════════════════════════════

def _rebuild_overlap_with_metric(data, metric_info):
    """musical metric을 적용하여 PH를 재탐색하고 새 overlap을 반환합니다."""
    from weights import (compute_intra_weights, compute_inter_weights,
                         compute_distance_matrix, compute_out_of_reach)
    from overlap import (group_rBD_by_homology, label_cycles_from_persistence,
                         build_activation_matrix, build_overlap_matrix)
    from topology import generate_barcode_numpy
    from musical_metrics import (compute_note_distance_matrix,
                                  compute_hybrid_distance,
                                  compute_multi_hybrid_distance)
    import pandas as pd

    adn_i = data['adn_i']
    notes_dict = data['notes_dict']
    notes_label = data['notes_label']
    N = len(notes_label)
    T = data['T']
    mi = metric_info

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    # 음악적 거리 사전 계산
    if mi['metric'] == 'hybrid':
        m_names = mi.get('hybrid_metrics', ['tonnetz'])
        m_weights = mi.get('hybrid_weights')
    else:
        m_names = [mi['metric']]
        alpha = mi.get('alpha', 0.5)
        m_weights = [alpha, 1.0 - alpha]

    # rate sweep (coarse: power=-2, step=0.01, 150 evaluations)
    profile = []
    step = 0.01
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values

        if mi['metric'] == 'hybrid':
            final = compute_multi_hybrid_distance(freq_dist, notes_label, m_names, m_weights)
        else:
            m_dist = compute_note_distance_matrix(notes_label, metric=mi['metric'])
            final = compute_hybrid_distance(freq_dist, m_dist, alpha=mi.get('alpha', 0.5))

        bd = generate_barcode_numpy(mat=final, listOfDimension=[1],
                                     exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd))
        rate += step

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)

    # Overlap matrix 재구축
    from preprocessing import simul_chord_lists, simul_union_by_dict
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled, threshold=0.35, total_length=T)

    return overlap, cycle_labeled


def generate_music(data, algorithm, k_cycles, min_gap, dl_model_type='fc',
                    progress_callback=None, metric_info=None):
    """파라미터에 따라 음악을 생성합니다."""
    from cycle_selector import CycleSubsetSelector
    from generation import (
        NodePool, CycleSetManager, algorithm1_optimized,
        build_orphan_supplement, notes_to_xml
    )

    _p = progress_callback
    mi = metric_info or {'metric': 'frequency'}
    metric_key = mi['metric']
    if metric_key == 'hybrid':
        metric_key = 'tonnetz'  # hybrid는 현재 tonnetz 캐시 사용

    # 캐시에서 로드 (즉시), 없으면 PH 재탐색 (느림)
    cache_path = os.path.join(os.path.dirname(__file__), "cache", f"metric_{metric_key}.pkl")
    if os.path.exists(cache_path):
        import pickle
        with open(cache_path, 'rb') as f:
            cached = pickle.load(f)
        overlap_df = cached['overlap']
        cycle_labeled = cached['cycle_labeled']
    else:
        if _p: _p.progress(5, text=f"캐시 없음 → PH 재탐색 중 (~10초)...")
        overlap_df, cycle_labeled = _rebuild_overlap_with_metric(data, mi)
    notes_label = data['notes_label']
    notes_counts = data['notes_counts']
    notes_dict = data['notes_dict']
    adn_i = data['adn_i']

    # Cycle selection
    if k_cycles < len(cycle_labeled):
        selector = CycleSubsetSelector(overlap_df.values, cycle_labeled)
        result = selector.select_with_coverage(notes_dict, k=k_cycles, verbose=False)
        items = list(cycle_labeled.items())
        sel_labeled = {i: items[idx][1] for i, idx in enumerate(result.selected_indices)}
        sel_overlap = overlap_df.values[:, result.selected_indices]
        score = result.final_score

        supplement = build_orphan_supplement(
            result.orphan_notes, result.orphan_chords, notes_dict,
            adn_i[1][-1], adn_i[2][-1], notes_label, 1088
        )
    else:
        sel_labeled = dict(cycle_labeled)
        sel_overlap = overlap_df.values
        score = 1.0
        supplement = None

    if algorithm == "Algorithm 1":
        if _p: _p.progress(30, text="Algorithm 1: 확률적 샘플링 중...")
        pool = NodePool(notes_label, notes_counts, num_modules=65)
        manager = CycleSetManager(sel_labeled)
        modules = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
                   4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3] * 33
        generated = algorithm1_optimized(
            pool, list(modules), sel_overlap, manager,
            orphan_supplement=supplement, min_onset_gap=min_gap
        )
        if _p: _p.progress(90, text="MusicXML 변환 중...")
    else:
        # Algorithm 2 (DL)
        from generation import (
            prepare_training_data, augment_training_data,
            MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer,
            train_model, generate_from_model
        )
        if _p: _p.progress(20, text="학습 데이터 준비 중...")
        T, C = sel_overlap.shape[0], sel_overlap.shape[1]
        N = len(notes_label)

        X, y = prepare_training_data(
            sel_overlap, [data['inst1_real'], data['inst2_real']],
            notes_label, T, N
        )
        if _p: _p.progress(30, text="Data augmentation (10x) 중...")
        X_aug, y_aug = augment_training_data(
            X, y, sel_overlap, sel_labeled,
            k_values=[10, 20], n_shifts=2, n_noise_copies=1
        )

        n = len(X_aug)
        idx = np.random.permutation(n)
        split = int(n * 0.7)

        if dl_model_type == 'FC':
            model = MusicGeneratorFC(C, N, hidden_dim=256, dropout=0.3)
        elif dl_model_type == 'LSTM':
            model = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.2)
        else:
            model = MusicGeneratorTransformer(C, N, d_model=64, nhead=4, num_layers=2, dropout=0.3)

        mtype = dl_model_type.lower()
        if _p: _p.progress(40, text=f"{dl_model_type} 모델 학습 중 (50 epochs)...")
        import io as _io, contextlib
        with contextlib.redirect_stdout(_io.StringIO()):
            train_model(model, X_aug[idx[:split]], y_aug[idx[:split]],
                        X_aug[idx[split:]], y_aug[idx[split:]],
                        epochs=50, lr=0.001, batch_size=64, model_type=mtype, seq_len=T)

        if _p: _p.progress(80, text="학습 완료! 음악 생성 중...")
        generated = generate_from_model(model, sel_overlap, notes_label,
                                         model_type=mtype, min_onset_gap=min_gap)
        if _p: _p.progress(90, text="MusicXML 변환 중...")

    return generated, score


def notes_to_midi_bytes(notes, tempo_bpm=66):
    """생성된 note를 MIDI 바이트로 변환합니다."""
    from generation import notes_to_xml
    import datetime

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"dashboard_{ts}"
    outdir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(outdir, exist_ok=True)

    notes_to_xml([notes], tempo_bpm=tempo_bpm, file_name=fname, output_dir=outdir)

    xml_path = os.path.join(outdir, f"{fname}.musicxml")
    midi_path = os.path.join(outdir, f"{fname}.mid")

    try:
        from music21 import converter
        score = converter.parse(xml_path)
        score.write('midi', fp=midi_path)
        with open(midi_path, 'rb') as f:
            return f.read(), midi_path
    except Exception:
        return None, xml_path


# ═══════════════════════════════════════════════════════════════════════════
# 메인 UI
# ═══════════════════════════════════════════════════════════════════════════

st.title("🎵 TDA Music Pipeline")
st.markdown("위상수학(Topology)으로 사카모토 류이치 'hibari'의 구조를 분석하고, 새 음악을 생성합니다.")

# 데이터 로드
with st.spinner("데이터 로드 중..."):
    data = load_pipeline_data()

total_cycles = len(data['cycle_labeled'])

# ── 사이드바: 파라미터 ──
st.sidebar.header("⚙️ Generation Parameters")

algorithm = st.sidebar.selectbox(
    "작곡 방식",
    ["Algorithm 1", "Algorithm 2 (DL)"],
    help="Algorithm 1: 규칙 기반 (빠름, 1~3초)\nAlgorithm 2: AI 학습 기반 (느림, 20~150초)"
)

if algorithm == "Algorithm 2 (DL)":
    dl_model = st.sidebar.selectbox("DL Model", ["FC", "LSTM", "Transformer"])
    # 모델별 설명 (비전공자용)
    model_descriptions = {
        "FC": "**FC**: 매 순간 독립적으로 '지금 어떤 음을 칠까?' 판단합니다. 앞뒤 흐름은 모르지만 가장 빠르고 안정적입니다.",
        "LSTM": "**LSTM**: 곡을 처음부터 순서대로 읽으면서 '직전에 높은 음을 쳤으니 다음은 낮은 음'처럼 흐름을 기억합니다. 학습이 느립니다.",
        "Transformer": "**Transformer**: 곡 전체를 한눈에 보고 '1마디와 10마디가 비슷한 패턴이니 비슷한 음을 쓰자'처럼 먼 거리의 관계도 파악합니다.",
    }
    st.sidebar.caption(model_descriptions[dl_model])
else:
    dl_model = "FC"

# 각 metric의 사전 계산된 cycle 수 (precompute_metrics.py 결과)
_metric_cycle_counts = {
    'frequency': 43, 'tonnetz': 46, 'voice_leading': 22, 'dft': 20
}

max_cycles = _metric_cycle_counts.get(selected_metric, total_cycles)
k_cycles = st.sidebar.slider(
    "사용할 구조 패턴 수",
    min_value=3, max_value=max_cycles, value=min(17, max_cycles), step=1,
    help=f"선택한 거리 방식으로 발견된 {max_cycles}개 패턴 중 몇 개를 사용할지."
)

min_gap = st.sidebar.slider(
    "음 사이 최소 간격",
    min_value=0, max_value=8, value=0, step=1,
    help="새 음이 시작되기까지의 최소 대기 시간. 0: 제한 없음(빽빽함), 3: 1.5박 쉬고 다음 음(여유로움)"
)

tempo = st.sidebar.slider("Tempo (BPM)", 40, 120, 66)

st.sidebar.markdown("---")
st.sidebar.header("🎼 거리 함수")

metric_choice = st.sidebar.selectbox(
    "음의 거리 측정 방식",
    ["빈도 (기존)", "Tonnetz (어울림)", "Voice-leading (높낮이)", "DFT (파동)"],
    help="음들 사이의 '가까움'을 어떻게 정의할지. 정의에 따라 발견되는 반복 구조가 달라집니다."
)

metric_descriptions = {
    "빈도 (기존)": "곡에서 연달아 자주 등장한 음끼리 가깝다고 봅니다. 곡의 통계에만 의존.",
    "Tonnetz (어울림)": "'도와 솔', '도와 미'처럼 함께 울리면 잘 어울리는 음끼리 가깝다고 봅니다. 피아노 건반 위의 화음 관계를 반영.",
    "Voice-leading (높낮이)": "피아노 건반에서 가까이 있는 음(예: 도→레)끼리 가깝다고 봅니다. 손가락을 적게 움직이는 자연스러운 진행.",
    "DFT (파동)": "소리의 파동(주파수) 패턴이 비슷한 음끼리 가깝다고 봅니다.",
}
st.sidebar.caption(metric_descriptions[metric_choice])

metric_map = {
    "빈도 (기존)": "frequency",
    "Tonnetz (어울림)": "tonnetz",
    "Voice-leading (높낮이)": "voice_leading",
    "DFT (파동)": "dft",
}
selected_metric = metric_map[metric_choice]

# 각 metric의 사전 계산된 cycle 수 표시
n_cyc = _metric_cycle_counts.get(selected_metric, '?')
st.sidebar.caption(f"이 방식으로 발견된 구조 패턴: **{n_cyc}개**")

st.sidebar.markdown("---")
view_range = st.sidebar.slider(
    "Piano Roll 표시 범위",
    min_value=0, max_value=1088, value=(0, 200), step=8,
    help="표시할 시간 범위 (eighth notes)"
)

# ── Algorithm 설명 ──
if algorithm == "Algorithm 1":
    st.sidebar.caption(
        "**Algorithm 1**: 원곡에서 추출한 뼈대 패턴을 보고, "
        "'지금 이 패턴이 활성화되어 있으니 이 음들 중에서 골라라'는 "
        "규칙으로 음을 랜덤 배치합니다. 빠르지만 앞뒤 흐름을 고려하지 않습니다."
    )

# ── 생성 버튼 ──
if st.sidebar.button("🎹 음악 생성", type="primary", use_container_width=True):
    progress = st.progress(0, text="준비 중...")

    t0 = time.time()

    metric_info = {'metric': selected_metric}

    progress.progress(10, text="Cycle 선택 중...")
    generated, score = generate_music(
        data, algorithm, k_cycles, min_gap, dl_model,
        progress_callback=progress, metric_info=metric_info
    )
    dt = time.time() - t0

    progress.progress(100, text=f"완료! ({dt:.1f}s)")

    st.session_state['generated'] = generated
    st.session_state['score'] = score
    st.session_state['gen_time'] = dt
    st.session_state['gen_params'] = {
        'algorithm': algorithm, 'k': k_cycles,
        'gap': min_gap, 'model': dl_model,
        'metric': metric_choice
    }

# ── 결과 표시 ──
if 'generated' in st.session_state:
    generated = st.session_state['generated']
    score = st.session_state['score']
    dt = st.session_state['gen_time']
    params = st.session_state['gen_params']

    # 지표
    from eval_metrics import evaluate_generation
    metrics = evaluate_generation(
        generated, [data['inst1_real'], data['inst2_real']],
        data['notes_label']
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Notes", f"{metrics['n_notes']:,}")
    col2.metric("Pitches", f"{metrics['pitch_count']}")
    col3.metric("Coverage", f"{metrics['note_coverage']:.0%}")
    col4.metric("JS Divergence", f"{metrics['js_divergence']:.4f}")
    col5.metric("Score", f"{score:.3f}")

    st.caption(f"{params['algorithm']} | K={params['k']} | gap={params['gap']} | {dt:.1f}s")

    # Piano Roll
    st.subheader("Piano Roll")
    xlim = list(view_range)

    fig = make_comparison_roll(
        [data['inst1_real'], data['inst2_real']],
        generated, xlim=xlim
    )
    st.plotly_chart(fig, use_container_width=True)

    # MIDI 다운로드
    st.subheader("Audio")
    midi_bytes, midi_path = notes_to_midi_bytes(generated, tempo)

    if midi_bytes:
        st.download_button(
            "⬇️ MIDI 다운로드",
            data=midi_bytes,
            file_name=os.path.basename(midi_path),
            mime="audio/midi"
        )
        st.info(f"저장됨: {midi_path}")
    else:
        st.warning(f"MusicXML 저장됨: {midi_path}")

else:
    # 초기 상태: 원곡만 표시
    st.info("👈 사이드바에서 파라미터를 설정하고 '음악 생성' 버튼을 누르세요.")

    st.subheader("원곡 Piano Roll")
    orig_flat = list(data['inst1_real']) + list(data['inst2_real'])
    fig = make_piano_roll(orig_flat, "hibari (Original)", '#4ecdc4',
                          xlim=list(view_range))
    st.plotly_chart(fig, use_container_width=True)
