"""
run_soft_activation_all_models.py — A-3 Soft activation 아키텍처 확장
======================================================================

FC에서 확인된 soft activation 효과(+64.3%)를 LSTM, Transformer에도 적용.

각 모델별 binary vs continuous overlap 입력 비교:
  - binary:     (cont_act >= 0.35).astype(float)  [현재]
  - continuous: cont_act (0~1 실수값)             [새로운]

기대 출력 형태:
{
  "FC":          {"binary": {...}, "continuous": {...}, "improvement_pct": ...},
  "LSTM":        {"binary": {...}, "continuous": {...}, "improvement_pct": ...},
  "Transformer": {"binary": {...}, "continuous": {...}, "improvement_pct": ...},
}

결과: docs/step3_data/soft_activation_all_models.json
"""

import sys, os, json, time, random, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict
)
from overlap import build_activation_matrix, build_overlap_matrix
from eval_metrics import evaluate_generation

N_TRIALS = 5   # 생성 평가 반복 (section77과 동일)
EPOCHS   = 80  # 학습 에포크 (section77과 동일)


# ─── 공통 setup ────────────────────────────────────────────────────────────────
def load_hibari_cache():
    from pipeline import TDAMusicPipeline, PipelineConfig
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    binary_overlap = cache['overlap'].values

    notes_label  = p._cache['notes_label']
    notes_counts = p._cache['notes_counts']
    adn_i        = p._cache['adn_i']
    T = 1088

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, p._cache['notes_dict'])
    nodes_list = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)

    return {
        'cycle_labeled': cycle_labeled,
        'binary_overlap': binary_overlap,
        'cont_activation': cont_act.values.astype(np.float32),
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'inst1_real': p._cache['inst1_real'],
        'inst2_real': p._cache['inst2_real'],
        'T': T,
    }


# ─── 모델별 실험 ──────────────────────────────────────────────────────────────
def run_model_experiment(data, model_name, model_class, model_kwargs,
                         model_type_str):
    """
    하나의 모델 아키텍처에 대해 binary vs continuous 비교.

    Args:
        model_name:     'FC' | 'LSTM' | 'Transformer'
        model_class:    MusicGeneratorFC | MusicGeneratorLSTM | MusicGeneratorTransformer
        model_kwargs:   생성자 인수 dict
        model_type_str: 'fc' | 'lstm' | 'transformer'
    """
    try:
        import torch
        from generation import (
            prepare_training_data, train_model, generate_from_model
        )
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        print(f"  [{model_name}] 의존성 오류: {e}")
        return {'error': str(e)}

    cycle_labeled = data['cycle_labeled']
    binary_ov = data['binary_overlap']
    cont_ov   = data['cont_activation']
    notes_label = data['notes_label']
    inst1_real  = data['inst1_real']
    inst2_real  = data['inst2_real']
    T = data['T']
    N = len(notes_label)
    K = binary_ov.shape[1]

    print(f"\n  {'─'*50}")
    print(f"  [{model_name}] K={K} cycles, N={N} notes")

    result = {}

    for mode, overlap_for_train in [('binary', binary_ov), ('continuous', cont_ov)]:
        print(f"\n  [{model_name}] {mode} 모드")
        print(f"    X range: [{overlap_for_train.min():.3f}, {overlap_for_train.max():.3f}]")

        X, y = prepare_training_data(
            overlap_for_train,
            [inst1_real, inst2_real],
            notes_label, T, N
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # 모델 생성
        torch.manual_seed(42)
        model = model_class(**model_kwargs)

        t0 = time.time()
        history = train_model(
            model, X_train, y_train, X_val, y_val,
            epochs=EPOCHS, lr=0.001, batch_size=32,
            model_type=model_type_str,
            seq_len=T,
        )
        train_time = time.time() - t0
        print(f"    학습 완료: {train_time:.1f}s")

        final_val_loss = history[-1]['val_loss'] if history else None

        # 생성 및 평가
        js_trials = []
        for i in range(N_TRIALS):
            torch.manual_seed(i); random.seed(i); np.random.seed(i)
            gen = generate_from_model(
                model, overlap_for_train, notes_label,
                model_type=model_type_str,
                adaptive_threshold=True
            )
            if not gen:
                js_trials.append(1.0)
                continue
            m = evaluate_generation(gen, [inst1_real, inst2_real], notes_label, name="")
            js_trials.append(m['js_divergence'])

        js_arr = np.array(js_trials)
        print(f"    JS = {js_arr.mean():.4f} ± {js_arr.std(ddof=1):.4f}  "
              f"(trials: {js_trials})")

        result[mode] = {
            'js_mean':       round(float(js_arr.mean()), 4),
            'js_std':        round(float(js_arr.std(ddof=1) if len(js_trials) > 1 else 0.0), 4),
            'val_loss':      round(float(final_val_loss), 4) if final_val_loss else None,
            'train_time_s':  round(train_time, 1),
            'n_trials':      len(js_trials),
        }

    if 'binary' in result and 'continuous' in result:
        b = result['binary']['js_mean']
        c = result['continuous']['js_mean']
        improvement = 100 * (b - c) / b if b > 0 else 0.0
        result['improvement_pct'] = round(improvement, 1)
        print(f"\n  [{model_name}] binary→continuous: {improvement:+.1f}%")

    return result


def main():
    print("=" * 65)
    print("  A-3 Soft activation 아키텍처 확장")
    print("  FC / LSTM / Transformer × binary vs continuous 비교")
    print(f"  N_TRIALS={N_TRIALS}, EPOCHS={EPOCHS}")
    print("=" * 65)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        import torch
        from generation import MusicGeneratorFC, MusicGeneratorLSTM, MusicGeneratorTransformer
    except ImportError as e:
        print(f"[오류] {e}")
        return

    print("\n[공통 데이터 로드]")
    data = load_hibari_cache()
    K = data['binary_overlap'].shape[1]
    N = len(data['notes_label'])
    print(f"  K={K} cycles, N={N} notes, T={data['T']}")
    print(f"  continuous 범위: [{data['cont_activation'].min():.3f}, {data['cont_activation'].max():.3f}]")

    all_results = {}

    # ── FC ──────────────────────────────────────────────────────────────────
    print("\n\n[1/3] FC (Fully Connected)")
    r_fc = run_model_experiment(
        data,
        model_name='FC',
        model_class=MusicGeneratorFC,
        model_kwargs={'num_cycles': K, 'num_notes': N, 'hidden_dim': 128, 'dropout': 0.3},
        model_type_str='fc',
    )
    all_results['FC'] = r_fc

    # ── LSTM ────────────────────────────────────────────────────────────────
    print("\n\n[2/3] LSTM")
    r_lstm = run_model_experiment(
        data,
        model_name='LSTM',
        model_class=MusicGeneratorLSTM,
        model_kwargs={'num_cycles': K, 'num_notes': N, 'hidden_dim': 128,
                      'num_layers': 2, 'dropout': 0.3},
        model_type_str='lstm',
    )
    all_results['LSTM'] = r_lstm

    # ── Transformer ─────────────────────────────────────────────────────────
    print("\n\n[3/3] Transformer (use_pos_emb=True)")
    r_tr = run_model_experiment(
        data,
        model_name='Transformer',
        model_class=MusicGeneratorTransformer,
        model_kwargs={'num_cycles': K, 'num_notes': N, 'd_model': 128, 'nhead': 4,
                      'num_layers': 2, 'dropout': 0.1, 'use_pos_emb': True},
        model_type_str='transformer',
    )
    all_results['Transformer'] = r_tr

    # ── 요약 ────────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 65)
    print("  [요약] 모델별 binary → continuous 개선")
    print("=" * 65)
    print(f"  {'모델':15s}  {'binary JS':>10s}  {'cont JS':>10s}  {'개선':>8s}")
    print("  " + "─" * 50)
    for model_name, r in all_results.items():
        if 'error' in r:
            print(f"  {model_name:15s}  오류: {r['error']}")
            continue
        b = r.get('binary', {}).get('js_mean', float('nan'))
        c = r.get('continuous', {}).get('js_mean', float('nan'))
        imp = r.get('improvement_pct', float('nan'))
        mark = " ★" if imp > 0 else ""
        print(f"  {model_name:15s}  {b:>10.4f}  {c:>10.4f}  {imp:>7.1f}%{mark}")

    # 결과 저장
    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/soft_activation_all_models.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")
    print("\n[완료]")


if __name__ == "__main__":
    main()
