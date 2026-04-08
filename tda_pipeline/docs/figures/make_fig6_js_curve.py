"""
Figure 6 — 학습 epoch별 JS divergence 곡선.
FC / LSTM / Transformer 세 모델을 학습하면서 매 epoch 시점에
생성을 해서 JS divergence를 측정하여 플롯.
"""
import os, sys, pickle, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt

EPOCHS = 60  # 모델당 학습 epoch
EVAL_EVERY = 5  # eval interval (너무 잦으면 느림)

def main():
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

    # 1) 전처리 + Tonnetz overlap 로드
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
    print(f"T={T}  C={C}  N={N}")

    # 2) training data
    X, y = prepare_training_data(overlap_values, [inst1, inst2], notes_label, T, N)
    # split
    np.random.seed(0)
    idx = np.random.permutation(len(X))
    split = int(len(X) * 0.7)
    X_tr, y_tr = X[idx[:split]], y[idx[:split]]
    X_va, y_va = X[idx[split:]], y[idx[split:]]
    print(f"train={len(X_tr)}  val={len(X_va)}")

    original = [inst1, inst2]

    def train_and_track(model, model_type):
        """각 epoch 후 JS를 측정."""
        js_per_epoch = []
        def cb(epoch, total, train_l, val_l):
            if epoch % EVAL_EVERY == 0 or epoch == total - 1:
                # 생성 한 번
                gen = generate_from_model(
                    model, overlap_values, notes_label,
                    model_type=model_type, adaptive_threshold=True)
                metrics = evaluate_generation(gen, original, notes_label, name="")
                js_per_epoch.append((epoch, metrics['js_divergence']))
        train_model(
            model, X_tr, y_tr, X_va, y_va,
            epochs=EPOCHS, lr=0.001, batch_size=32,
            model_type=model_type, seq_len=T,
            epoch_callback=cb,
        )
        return js_per_epoch

    # 3) 세 모델 학습
    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    print("\n== FC ==")
    fc = MusicGeneratorFC(C, N, hidden_dim=128, dropout=0.3)
    fc_curve = train_and_track(fc, 'fc')

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    print("\n== LSTM ==")
    lstm = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
    lstm_curve = train_and_track(lstm, 'lstm')

    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    print("\n== Transformer ==")
    trans = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                      num_layers=2, dropout=0.1, max_len=T)
    trans_curve = train_and_track(trans, 'transformer')

    # 4) plot
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor('white')

    for name, curve, color in [
        ('FC', fc_curve, '#2980b9'),
        ('LSTM', lstm_curve, '#27ae60'),
        ('Transformer', trans_curve, '#e74c3c'),
    ]:
        if not curve:
            continue
        xs, ys = zip(*curve)
        ax.plot(xs, ys, marker='o', markersize=6, linewidth=2,
                label=name, color=color)

    ax.set_xlabel('Epoch', fontsize=11, color='#2c3e50')
    ax.set_ylabel('Pitch JS Divergence  (생성곡 vs 원곡)',
                  fontsize=11, color='#2c3e50')
    ax.set_title('Figure 6. 학습 epoch별 JS Divergence — FC / LSTM / Transformer\n'
                 '(Tonnetz 기반 overlap, 동일 초기 seed)',
                 fontsize=12, color='#2c3e50', pad=12)
    ax.axhline(y=np.log(2), color='#7f8c8d', linestyle=':',
               alpha=0.5, label='theoretical max = log 2')
    ax.legend(fontsize=10, frameon=True)
    ax.grid(alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig6_js_curve.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

    # save curves as JSON too
    import json
    curves = {
        'fc': fc_curve, 'lstm': lstm_curve, 'transformer': trans_curve,
        'epochs': EPOCHS, 'eval_every': EVAL_EVERY,
    }
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fig6_curves.json'), 'w') as f:
        json.dump(curves, f, indent=2)

if __name__ == '__main__':
    main()
