"""
Figure 6 — 학습 epoch별 JS divergence 곡선.
FC / LSTM / Transformer 세 모델을 학습하면서 매 epoch 시점에
생성을 해서 JS divergence를 측정하여 플롯.

데이터가 이미 fig6_curves.json에 있으면 재학습 없이 재렌더링만.
"""
import os, sys, json, pickle, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt

EPOCHS = 60
EVAL_EVERY = 5
CURVES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fig6_curves.json')


def train_all():
    """세 모델 학습 + JS 측정 (약 2-3분)."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    import torch
    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import (
        prepare_training_data, MusicGeneratorFC, MusicGeneratorLSTM,
        MusicGeneratorTransformer, train_model, generate_from_model
    )
    from eval_metrics import evaluate_generation

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    notes_label = p._cache['notes_label']

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap = cache['overlap']
    overlap_values = overlap.values.astype(np.float32)
    T, C = overlap_values.shape
    N = len(notes_label)

    X, y = prepare_training_data(overlap_values, [inst1, inst2], notes_label, T, N)
    np.random.seed(0)
    idx = np.random.permutation(len(X))
    split = int(len(X) * 0.7)
    X_tr, y_tr = X[idx[:split]], y[idx[:split]]
    X_va, y_va = X[idx[split:]], y[idx[split:]]

    original = [inst1, inst2]

    def train_and_track(model, model_type):
        pts = []
        def cb(epoch, total, tr_l, va_l):
            if epoch % EVAL_EVERY == 0 or epoch == total - 1:
                gen = generate_from_model(model, overlap_values, notes_label,
                                          model_type=model_type, adaptive_threshold=True)
                m = evaluate_generation(gen, original, notes_label, name="")
                pts.append((epoch, m['js_divergence']))
        train_model(model, X_tr, y_tr, X_va, y_va,
                    epochs=EPOCHS, lr=0.001, batch_size=32,
                    model_type=model_type, seq_len=T, epoch_callback=cb)
        return pts

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    fc = MusicGeneratorFC(C, N, hidden_dim=128, dropout=0.3)
    fc_curve = train_and_track(fc, 'fc')

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    lstm = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
    lstm_curve = train_and_track(lstm, 'lstm')

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    trans = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                      num_layers=2, dropout=0.1, max_len=T)
    trans_curve = train_and_track(trans, 'transformer')

    curves = {'fc': fc_curve, 'lstm': lstm_curve, 'transformer': trans_curve,
              'epochs': EPOCHS, 'eval_every': EVAL_EVERY}
    with open(CURVES_JSON, 'w') as f:
        json.dump(curves, f, indent=2)
    return curves


def render(curves):
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.patch.set_facecolor('white')

    for name, key, color, marker in [
        ('FC',          'fc',          '#2980b9', 'o'),
        ('LSTM',        'lstm',        '#27ae60', 's'),
        ('Transformer', 'transformer', '#e74c3c', '^'),
    ]:
        curve = curves.get(key, [])
        if not curve:
            continue
        xs, ys = zip(*curve)
        ax.plot(xs, ys, marker=marker, markersize=7, linewidth=2.2,
                label=name, color=color)

    # 이론적 최댓값 — 진하고 두꺼운 선
    ax.axhline(y=np.log(2), color='#2c3e50', linestyle='--',
               linewidth=2.0, alpha=0.85,
               label=r'이론적 최댓값  $\log 2 \approx 0.693$')

    ax.set_xlabel('Epoch', fontsize=12, color='#2c3e50')
    ax.set_ylabel('Pitch JS Divergence  (생성곡 vs 원곡)',
                  fontsize=12, color='#2c3e50')
    ax.set_title('Figure 6. 학습 epoch별 JS Divergence — FC / LSTM / Transformer\n'
                 '(Tonnetz 기반 overlap, 동일 초기 seed)',
                 fontsize=12.5, color='#2c3e50', pad=12)
    ax.legend(fontsize=10.5, frameon=True, framealpha=0.95, loc='upper right')
    ax.grid(alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(-0.02, 0.78)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig6_js_curve.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")


def main():
    if os.path.exists(CURVES_JSON):
        print(f"재사용: {CURVES_JSON}")
        with open(CURVES_JSON, 'r') as f:
            curves = json.load(f)
    else:
        print("학습 데이터가 없음 — 재학습 수행 (~2-3 min)")
        curves = train_all()
    render(curves)


if __name__ == '__main__':
    main()
