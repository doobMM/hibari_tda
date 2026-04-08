"""
Figure 2 (interactive supplementary) — hibari cycle 3D + click-to-play.

브라우저에서 cycle 선을 클릭하면 그 cycle의 note들이 Tone.js로 재생된다.
- 마우스 드래그: 자유 회전
- 우측 legend 클릭: cycle on/off
- cycle line 클릭: 해당 cycle의 note 시퀀스를 sine wave로 재생
- hover: 구성 note의 pitch name + duration 표시

오프라인 사용 시 인터넷 연결 필요 (plotly.js + Tone.js CDN).
"""
import os, sys, pickle, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def midi_to_name(midi_pitch):
    return f"{PITCH_NAMES[midi_pitch % 12]}{midi_pitch // 12 - 1}"

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    import plotly.graph_objects as go
    import plotly.colors as pc

    cache_path = os.path.join('cache', 'metric_tonnetz.pkl')
    with open(cache_path, 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']

    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    notes_label = p._cache['notes_label']  # (pitch, dur) → label
    label_to_note = {lbl: nd for nd, lbl in notes_label.items()}

    all_nodes = sorted({int(v) for verts in cycle_labeled.values()
                        if isinstance(verts, (list, tuple, set))
                        for v in verts})
    n = len(all_nodes)
    node_idx = {v: i for i, v in enumerate(all_nodes)}

    thetas = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xs = np.cos(thetas)
    ys = np.sin(thetas)

    def label_text(lbl):
        if lbl in label_to_note:
            pitch, dur = label_to_note[lbl]
            return f"label {lbl}: {midi_to_name(pitch)} (dur={dur})"
        return f"label {lbl}"

    fig = go.Figure()

    # base notes
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=np.zeros(n),
        mode='markers+text',
        text=[str(v) for v in all_nodes],
        textposition='top center',
        marker=dict(size=8, color='#7f8c8d',
                    line=dict(width=1, color='#2c3e50')),
        hovertext=[label_text(v) for v in all_nodes],
        hoverinfo='text',
        name='all notes',
        showlegend=False,
    ))

    cycles_to_show = list(cycle_labeled.items())[:20]
    cmap = pc.qualitative.Set3 + pc.qualitative.Pastel1

    z_offsets = np.linspace(-1.0, 1.0, len(cycles_to_show))

    # cycle 데이터를 JS에서도 사용할 수 있게 별도 저장
    cycles_audio_data = []  # 각 trace에 대응되는 [(pitch_midi, duration_8th), ...]

    # 첫 trace는 노드 trace이므로 인덱스 0이 노드, 1부터 cycle
    cycles_audio_data.append([])  # node trace (no audio)

    for ci, (cid, verts) in enumerate(cycles_to_show):
        if not isinstance(verts, (list, tuple, set)):
            continue
        verts_i = [int(v) for v in verts if int(v) in node_idx]
        if len(verts_i) < 3:
            continue

        z_off = z_offsets[ci]
        cx = [xs[node_idx[v]] for v in verts_i]
        cy = [ys[node_idx[v]] for v in verts_i]
        cz = [z_off] * len(verts_i)
        cx.append(cx[0]); cy.append(cy[0]); cz.append(cz[0])

        color = cmap[ci % len(cmap)]
        notes_in_cycle = []
        for v in verts_i:
            if v in label_to_note:
                pitch, dur = label_to_note[v]
                notes_in_cycle.append({'pitch': int(pitch),
                                       'dur': int(dur),
                                       'name': midi_to_name(pitch)})
        cycles_audio_data.append(notes_in_cycle)

        hover_lines = '<br>'.join(label_text(v) for v in verts_i)
        cycle_label = f'cycle {ci+1}: [{", ".join(str(v) for v in verts_i)}]'

        fig.add_trace(go.Scatter3d(
            x=cx, y=cy, z=cz,
            mode='lines+markers',
            line=dict(color=color, width=6),
            marker=dict(size=6, color=color,
                        line=dict(width=1, color='#2c3e50')),
            name=cycle_label,
            hovertext=[hover_lines] * len(cx),
            hoverinfo='text',
        ))

    fig.update_layout(
        title=dict(
            text='Figure 2 (interactive). hibari Cycles — Tonnetz, top 20<br>'
                 '<sub>드래그=회전 · legend 클릭=on/off · cycle 선 클릭=재생</sub>',
            x=0.5, xanchor='center', font=dict(size=15, color='#2c3e50'),
        ),
        scene=dict(
            xaxis_title='x', yaxis_title='y', zaxis_title='cycle index',
            aspectmode='cube',
            camera=dict(eye=dict(x=0.2, y=0.2, z=2.2)),
        ),
        width=1100, height=800,
        legend=dict(font=dict(size=9), x=1.02, y=0.5,
                    xanchor='left', yanchor='middle'),
        margin=dict(l=0, r=260, t=80, b=120),
    )

    # ── plotly_click → Tone.js audio playback ──
    plot_div_id = 'fig2_plot'
    cycles_json = json.dumps(cycles_audio_data)

    extra_html = f"""
<div id="audio_status" style="text-align:center; margin-top:10px;
    font-family:sans-serif; font-size:14px; color:#2c3e50;">
  <button id="audio_init_btn" style="padding:8px 16px; font-size:13px;
    background:#3498db; color:white; border:none; border-radius:4px;
    cursor:pointer;">🔊 오디오 켜기 (한 번 클릭 필요)</button>
  <span id="status_msg" style="margin-left:12px; color:#7f8c8d;"></span>
</div>
<script src="https://unpkg.com/tone@14.8.49/build/Tone.js"></script>
<script>
  const cyclesAudioData = {cycles_json};
  let synth = null;
  let audioReady = false;

  document.getElementById('audio_init_btn').addEventListener('click', async function() {{
    await Tone.start();
    synth = new Tone.PolySynth(Tone.Synth).toDestination();
    audioReady = true;
    document.getElementById('audio_init_btn').style.display = 'none';
    document.getElementById('status_msg').textContent
      = '✓ 오디오 준비 완료. cycle 선을 클릭해보세요.';
  }});

  function midiToFreq(midiPitch) {{
    return 440 * Math.pow(2, (midiPitch - 69) / 12);
  }}

  function playCycle(notes) {{
    if (!audioReady || !synth) {{
      document.getElementById('status_msg').textContent
        = '⚠ 먼저 위쪽 "오디오 켜기" 버튼을 클릭하세요.';
      return;
    }}
    const now = Tone.now();
    let t = now;
    const stepDur = 0.4; // each note 0.4s
    notes.forEach((nt, idx) => {{
      synth.triggerAttackRelease(midiToFreq(nt.pitch), stepDur * 0.9, t);
      t += stepDur;
    }});
    document.getElementById('status_msg').textContent
      = `▶ 재생 중: ${{notes.map(n => n.name).join(' → ')}}`;
  }}

  // plotly_click 이벤트 — DOMContentLoaded 후
  function attachClickHandler() {{
    const plotDiv = document.querySelector('.plotly-graph-div');
    if (!plotDiv) {{ setTimeout(attachClickHandler, 200); return; }}
    plotDiv.on('plotly_click', function(data) {{
      if (!data.points || !data.points.length) return;
      const pt = data.points[0];
      const traceIdx = pt.curveNumber;
      const cycleNotes = cyclesAudioData[traceIdx];
      if (cycleNotes && cycleNotes.length > 0) {{
        playCycle(cycleNotes);
      }}
    }});
  }}
  attachClickHandler();
</script>
"""

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig2_cycle3d_interactive.html')
    fig.write_html(out, include_plotlyjs='cdn', full_html=True,
                   post_script=None)

    # post_script가 head에 들어가면 안 되므로 직접 삽입
    with open(out, 'r', encoding='utf-8') as f:
        html = f.read()
    html = html.replace('</body>', extra_html + '\n</body>')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Saved: {out}")
    print(f"  cycles with audio data: {sum(1 for c in cycles_audio_data if c)}")

if __name__ == '__main__':
    main()
