"""
Figure 2 (interactive, standalone) — hibari cycle 3D 시각화.
Plotly로 회전/클릭 가능한 HTML을 생성한다. 논문 본문에는 들어가지 않으며,
별도 supplementary material로 배포한다.

- 마우스 드래그로 회전 (3D)
- cycle을 클릭하면 그 cycle이 포함하는 note label들이 hover에 표시됨
- 상위 12개 cycle을 색상별로 구분
"""
import os, sys, pickle, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    import plotly.graph_objects as go

    cache_path = os.path.join('cache', 'metric_tonnetz.pkl')
    with open(cache_path, 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    print(f"Loaded {len(cycle_labeled)} cycles")

    # 모든 note label 수집
    all_nodes = set()
    for verts in cycle_labeled.values():
        if isinstance(verts, (list, tuple, set)):
            for v in verts:
                all_nodes.add(int(v))
    nodes_sorted = sorted(all_nodes)
    n = len(nodes_sorted)
    node_idx = {v: i for i, v in enumerate(nodes_sorted)}

    # 중앙 원 배치
    thetas = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xs = np.cos(thetas)
    ys = np.sin(thetas)
    zs = np.zeros(n)

    # 전처리로 note label → (pitch, duration) 정보
    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    notes_label = p._cache['notes_label']  # (pitch, dur) → label (1-indexed)
    label_to_note = {lbl: nd for nd, lbl in notes_label.items()}
    PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def label_to_text(lbl):
        if lbl in label_to_note:
            p, d = label_to_note[lbl]
            pn = PITCH_NAMES[p % 12]
            oct = p // 12 - 1
            return f"label {lbl}: {pn}{oct} (pitch={p}, dur={d})"
        return f"label {lbl}"

    # 기본 노드
    node_hover = [label_to_text(v) for v in nodes_sorted]
    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='markers+text',
        text=[str(v) for v in nodes_sorted],
        textposition='top center',
        marker=dict(size=8, color='#7f8c8d', line=dict(width=1, color='#2c3e50')),
        hovertext=node_hover,
        hoverinfo='text',
        name='all notes',
    ))

    # Cycle 표시 — 상위 20개
    cycles_to_show = list(cycle_labeled.items())[:20]
    import plotly.colors as pc
    cmap = pc.qualitative.Set3 + pc.qualitative.Pastel1

    z_offsets = np.linspace(-1.0, 1.0, len(cycles_to_show))

    for ci, (cycle_id, verts) in enumerate(cycles_to_show):
        if not isinstance(verts, (list, tuple, set)):
            continue
        verts_i = [int(v) for v in verts if int(v) in node_idx]
        if len(verts_i) < 3:
            continue

        z_off = z_offsets[ci]
        cx = [xs[node_idx[v]] for v in verts_i]
        cy = [ys[node_idx[v]] for v in verts_i]
        cz = [z_off] * len(verts_i)
        # 닫기
        cx.append(cx[0])
        cy.append(cy[0])
        cz.append(cz[0])

        color = cmap[ci % len(cmap)]
        cycle_text = ' → '.join(str(v) for v in verts_i)
        hover_notes = '<br>'.join(label_to_text(v) for v in verts_i)

        fig.add_trace(go.Scatter3d(
            x=cx, y=cy, z=cz,
            mode='lines+markers',
            line=dict(color=color, width=6),
            marker=dict(size=6, color=color, line=dict(width=1, color='#2c3e50')),
            name=f'cycle {ci+1}: [{cycle_text}]',
            hovertext=[hover_notes] * len(cx),
            hoverinfo='text',
            legendgroup=f'c{ci}',
        ))

    fig.update_layout(
        title=dict(
            text='Figure 2 (interactive). hibari Cycles — Tonnetz metric, top 20 cycles<br>'
                 '<sub>드래그로 회전 · 범례 클릭으로 cycle on/off · '
                 'hover로 구성 note 확인</sub>',
            x=0.5, xanchor='center', font=dict(size=16, color='#2c3e50'),
        ),
        scene=dict(
            xaxis_title='x', yaxis_title='y', zaxis_title='cycle index',
            aspectmode='cube',
            camera=dict(eye=dict(x=0.2, y=0.2, z=2.2)),  # 위에서 내려다보기
        ),
        width=1000, height=800,
        legend=dict(font=dict(size=9), x=1.02, y=0.5, xanchor='left', yanchor='middle'),
        margin=dict(l=0, r=250, t=80, b=0),
    )

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig2_cycle3d_interactive.html')
    fig.write_html(out, include_plotlyjs='cdn', full_html=True)
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
