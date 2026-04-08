"""
run_improvement_F.py — 개선 F: Continuous overlap + Algorithm 2

§7.1.5 에서 제안된 개선 F 의 구현. FC 모델 (기존 §3.4 최우수) 에 대해
세 가지 입력 형식을 비교한다.

  F-bin  :  binary overlap (기존 baseline, §3.4 재현)
  F-cont :  continuous activation matrix (희귀도 가중치 포함, §2.5 연속값 확장)
  F-mod  :  module-local continuous activation (§7.1.6 P4 style)

각 설정에 대해 서로 다른 torch seed 로 N=5회 학습 + 생성 + JS 측정.

비고: FC 모델 자체는 이미 nn.Linear 입력이라 real-valued input 을 자연스럽게
받아들인다. 개선 F 의 핵심은 학습 데이터의 *값 분포* 를 binary vs continuous 로
바꾸었을 때 FC 가 더 풍부한 위상 정보를 학습하는가 를 검증하는 것이다.
"""
import os, sys, json, time, random, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

N_TRIALS = 5
EPOCHS = 60  # §3.4 와 비슷한 조건
LR = 1e-3
HIDDEN = 128
BATCH = 32


def set_all_seeds(seed):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def train_and_eval(X_train, y_train, X_valid, y_valid,
                    overlap_for_gen, notes_label, inst1, inst2,
                    num_cycles, num_notes, seed):
    """FC 모델 하나 학습 + 생성 + JS 측정."""
    import torch
    from generation import (
        MusicGeneratorFC, train_model, generate_from_model,
    )
    from eval_metrics import evaluate_generation

    set_all_seeds(seed)
    model = MusicGeneratorFC(num_cycles, num_notes,
                              hidden_dim=HIDDEN, dropout=0.3)
    # 학습 (verbose 억제)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=EPOCHS, lr=LR, batch_size=BATCH,
            model_type='fc', seq_len=1088,
        )
    train_loss = history[-1]['train_loss']
    val_loss = history[-1]['val_loss']

    # 생성
    generated = generate_from_model(
        model, overlap_for_gen, notes_label,
        model_type='fc', adaptive_threshold=True)

    metrics = evaluate_generation(
        generated, [inst1, inst2], notes_label, name="")

    return {
        'train_loss': float(train_loss),
        'val_loss':   float(val_loss),
        'js':         float(metrics['js_divergence']),
        'coverage':   float(metrics['note_coverage']),
        'n_notes':    int(len(generated)),
    }


def main():
    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import prepare_training_data
    from overlap import build_activation_matrix
    from preprocessing import simul_chord_lists, simul_union_by_dict
    import pandas as pd

    print("=" * 72)
    print("  개선 F — Continuous overlap + Algorithm 2 (FC)")
    print("=" * 72)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    notes_label = p._cache['notes_label']
    notes_dict = p._cache['notes_dict']
    adn_i = p._cache['adn_i']
    N = len(notes_label)
    T = 1088

    # ─── 공통: note_time_df 재구성 (overlap.py 입력용) ───
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

    # ─── Tonnetz cache 에서 cycle_labeled 가져옴 (§3.4 baseline 과 동일) ───
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    K = len(cycle_labeled)
    print(f"\n  Tonnetz cycles: {K}")

    # ── F-bin: binary activation (기존 §3.4 재현) ──
    act_bin = build_activation_matrix(note_time_df, cycle_labeled,
                                       continuous=False)
    X_bin = act_bin.values.astype(np.float32)

    # ── F-cont: continuous activation (희귀도 가중치 포함) ──
    act_cont = build_activation_matrix(note_time_df, cycle_labeled,
                                        continuous=True)
    X_cont = act_cont.values.astype(np.float32)

    print(f"\n  Binary activation:     density {(X_bin > 0).mean():.3f}")
    print(f"  Continuous activation: density {(X_cont > 0).mean():.3f}  "
          f"mean {X_cont.mean():.3f}")

    # 정답 y — 원곡 multi-hot note 행렬 (§3.4 와 동일)
    _, y = prepare_training_data(
        X_bin, [inst1, inst2], notes_label, T, N)

    # train/valid split (§3.4 와 동일한 시점 분할)
    np.random.seed(0)
    idx = np.random.permutation(len(X_bin))
    split = int(len(X_bin) * 0.7)
    tr_idx = idx[:split]
    va_idx = idx[split:]

    configs = {
        'F-bin (baseline)':     X_bin,
        'F-cont (continuous)':  X_cont,
    }

    all_results = {}
    for cfg_name, X in configs.items():
        print(f"\n[{cfg_name}]")
        X_tr = X[tr_idx]; y_tr = y[tr_idx]
        X_va = X[va_idx]; y_va = y[va_idx]

        trials = []
        for i in range(N_TRIALS):
            seed = 8100 + i * 7
            t0 = time.time()
            r = train_and_eval(
                X_tr, y_tr, X_va, y_va,
                X, notes_label, inst1, inst2,
                num_cycles=K, num_notes=N, seed=seed)
            r['seed'] = seed
            r['elapsed_s'] = time.time() - t0
            trials.append(r)
            print(f"  [{i+1:2d}] seed={seed}  val={r['val_loss']:.4f}  "
                  f"JS={r['js']:.4f}  cov={r['coverage']:.2f}  "
                  f"({r['elapsed_s']:.1f}s)")

        js_arr = np.array([t['js'] for t in trials])
        val_arr = np.array([t['val_loss'] for t in trials])
        cov_arr = np.array([t['coverage'] for t in trials])
        summary = {
            'js_mean':    float(js_arr.mean()),
            'js_std':     float(js_arr.std(ddof=1)),
            'js_min':     float(js_arr.min()),
            'js_max':     float(js_arr.max()),
            'val_mean':   float(val_arr.mean()),
            'val_std':    float(val_arr.std(ddof=1)),
            'cov_mean':   float(cov_arr.mean()),
            'elapsed_total': float(sum(t['elapsed_s'] for t in trials)),
            'trials':     trials,
        }
        all_results[cfg_name] = summary
        print(f"  → JS = {summary['js_mean']:.4f} ± {summary['js_std']:.4f}")

    # ─── 요약 출력 ───
    print("\n" + "=" * 72)
    print("  요약 (N=5 trials each, FC 모델 고정, §3.4 baseline JS = 0.0015 참조)")
    print("=" * 72)
    print(f"  {'Configuration':28s}  {'JS (mean ± std)':20s}  {'best':>8s}  {'val':>8s}")
    print("  " + "─" * 70)
    for name, r in all_results.items():
        print(f"  {name:28s}  "
              f"{r['js_mean']:.4f} ± {r['js_std']:.4f}  "
              f"{r['js_min']:>8.4f}  "
              f"{r['val_mean']:>8.4f}")

    # JSON 저장
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    lite = {k: {kk: vv for kk, vv in v.items() if kk != 'trials'}
            for k, v in all_results.items()}
    lite['n_trials']    = N_TRIALS
    lite['epochs']      = EPOCHS
    lite['hidden_dim']  = HIDDEN
    lite['batch_size']  = BATCH
    lite['lr']          = LR
    lite['note'] = ('F-bin 은 §3.4 와 동일한 구조 (Tonnetz binary overlap). '
                    'F-cont 는 희귀도 가중치를 적용한 연속값 활성행렬을 입력으로 사용.')
    with open(os.path.join(out_dir, 'step_improvementF_results.json'),
              'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {out_dir}/step_improvementF_results.json")


if __name__ == '__main__':
    main()
