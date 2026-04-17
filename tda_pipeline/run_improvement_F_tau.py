"""
run_improvement_F_tau.py — §4.3a 세 번째 조건 추가: FC-cont-τ05

FC 모델에 대해 세 가지 입력 형식을 비교한다.

  FC-bin      :  binary overlap (기존 baseline, §3.4)
  FC-cont     :  continuous activation a_{c,t} ∈ [0,1] (희귀도 가중치 포함)
  FC-cont-τ05 :  continuous activation → τ=0.5 이진화
                  X[t,c] = 1 if a_{c,t} >= 0.5 else 0
                  ("절반 이상 가중 활성이 있어야 cycle 활성 판정")

이진화 기준의 차이:
  FC-bin:       cycle V(c)에 note가 한 개라도 활성 → 1
  FC-cont-τ05:  희귀도 가중 활성도 a_{c,t} >= 0.5 → 1
                (더 높은 기준 → 더 sparse한 행렬)

각 설정 N=5회 학습 + 생성 + JS 측정.
결과를 step_improvementF_tau_results.json에 저장.
"""
import os, sys, json, time, random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

N_TRIALS = 5
EPOCHS = 60
LR = 1e-3
HIDDEN = 128
BATCH = 32
TAU = 0.5


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
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=EPOCHS, lr=LR, batch_size=BATCH,
            model_type='fc', seq_len=1088,
        )
    train_loss = history[-1]['train_loss']
    val_loss = history[-1]['val_loss']

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
    import pickle
    import pandas as pd
    from pipeline import TDAMusicPipeline, PipelineConfig
    from generation import prepare_training_data
    from overlap import build_activation_matrix
    from preprocessing import simul_chord_lists, simul_union_by_dict

    print("=" * 72)
    print("  §4.3a FC 입력 3종 비교: bin / cont / cont-τ05")
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

    # ── note_time_df 재구성 (overlap.py 입력용) ──
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

    # ── Tonnetz 캐시에서 cycle_labeled 로드 ──
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    K = len(cycle_labeled)
    print(f"\n  Tonnetz cycles: {K}")

    # ── 세 가지 입력 행렬 생성 ──
    act_bin = build_activation_matrix(note_time_df, cycle_labeled, continuous=False)
    X_bin = act_bin.values.astype(np.float32)

    act_cont = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)
    X_cont = act_cont.values.astype(np.float32)

    X_tau = (X_cont >= TAU).astype(np.float32)   # FC-cont-τ05

    print(f"\n  FC-bin:       density {(X_bin > 0).mean():.4f}")
    print(f"  FC-cont:      density {(X_cont > 0).mean():.4f}  mean={X_cont.mean():.4f}")
    print(f"  FC-cont-τ05:  density {(X_tau > 0).mean():.4f}  "
          f"(τ={TAU}, 기준: a_{{c,t}} >= {TAU})")

    # ── 정답 y 생성 (FC-bin 기준으로 고정) ──
    _, y = prepare_training_data(X_bin, [inst1, inst2], notes_label, T, N)

    # ── train/valid split (기존 §3.4와 동일 seed) ──
    np.random.seed(0)
    idx = np.random.permutation(len(X_bin))
    split = int(len(X_bin) * 0.7)
    tr_idx = idx[:split]
    va_idx = idx[split:]

    configs = {
        'FC-bin (baseline)':  X_bin,
        'FC-cont':            X_cont,
        f'FC-cont-τ{int(TAU*100):02d}': X_tau,
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
            r['elapsed_s'] = round(time.time() - t0, 2)
            trials.append(r)
            print(f"  [{i+1:2d}] seed={seed}  val={r['val_loss']:.4f}  "
                  f"JS={r['js']:.4f}  cov={r['coverage']:.2f}  "
                  f"({r['elapsed_s']:.1f}s)")

        js_arr  = np.array([t['js'] for t in trials])
        val_arr = np.array([t['val_loss'] for t in trials])
        cov_arr = np.array([t['coverage'] for t in trials])
        summary = {
            'js_mean':       float(js_arr.mean()),
            'js_std':        float(js_arr.std(ddof=1)),
            'js_min':        float(js_arr.min()),
            'js_max':        float(js_arr.max()),
            'val_mean':      float(val_arr.mean()),
            'val_std':       float(val_arr.std(ddof=1)),
            'cov_mean':      float(cov_arr.mean()),
            'elapsed_total': float(sum(t['elapsed_s'] for t in trials)),
            'trials':        trials,
        }
        all_results[cfg_name] = summary
        print(f"  → JS = {summary['js_mean']:.4f} ± {summary['js_std']:.4f}  "
              f"best={summary['js_min']:.4f}  val={summary['val_mean']:.4f}")

    # ── 요약 테이블 ──
    print("\n" + "=" * 72)
    print(f"  §4.3a 결과 요약 (N={N_TRIALS} trials, FC 고정)")
    print("=" * 72)
    print(f"  {'설정':24s}  {'JS (mean±std)':22s}  {'best':>8s}  "
          f"{'val_loss':>9s}  {'coverage':>8s}")
    print("  " + "─" * 76)
    for name, r in all_results.items():
        print(f"  {name:24s}  "
              f"{r['js_mean']:.4f} ± {r['js_std']:.4f}       "
              f"{r['js_min']:>8.4f}  "
              f"{r['val_mean']:>9.4f}  "
              f"{r['cov_mean']:>8.4f}")

    # FC-cont 대비 FC-cont-τ05 변화율 출력
    tau_key = f'FC-cont-τ{int(TAU*100):02d}'
    cont_js = all_results['FC-cont']['js_mean']
    tau_js  = all_results[tau_key]['js_mean']
    delta_pct = (tau_js - cont_js) / cont_js * 100
    print(f"\n  FC-cont → {tau_key}: "
          f"{cont_js:.4f} → {tau_js:.4f}  "
          f"Δ={delta_pct:+.1f}%")

    bin_js = all_results['FC-bin (baseline)']['js_mean']
    delta_vs_bin = (tau_js - bin_js) / bin_js * 100
    print(f"  FC-bin  → {tau_key}: "
          f"{bin_js:.4f} → {tau_js:.4f}  "
          f"Δ={delta_vs_bin:+.1f}%")

    # ── JSON 저장 ──
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    lite = {k: {kk: vv for kk, vv in v.items() if kk != 'trials'}
            for k, v in all_results.items()}
    lite['n_trials']   = N_TRIALS
    lite['epochs']     = EPOCHS
    lite['hidden_dim'] = HIDDEN
    lite['batch_size'] = BATCH
    lite['lr']         = LR
    lite['tau']        = TAU
    lite['note'] = (
        f'FC-bin: cycle note 1개 이상 활성 → 1 (§3.4 기준). '
        f'FC-cont: 희귀도 가중 활성도 a_{{c,t}} ∈ [0,1] 직접 입력. '
        f'FC-cont-τ{int(TAU*100):02d}: a_{{c,t}} >= {TAU} 이진화 — '
        f'절반 이상 가중 활성이 있어야 cycle 활성 판정.'
    )
    out_path = os.path.join(out_dir, 'step_improvementF_tau_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {out_path}")


if __name__ == '__main__':
    main()
