"""
run_combined_AB.py — 방향 A + B 결합: note 재분배 + 시간 재배치 + continuous + Transformer

위상적 거리 구조 보존 + 화성적 조화 + 시간 순서 변화를 동시에 적용:
  - 방향 A: scale_major로 note 재분배 (화성 보존)
  - 방향 B: overlap matrix 시간축 재배치 (시간 구조 변화)
  - continuous overlap (풍부한 입력)
  - Transformer 학습/생성

비교 대상: 6가지 조합
  {original, scale_major} × {no_reorder, segment_shuffle, block_permute}

사용법:
  python run_combined_AB.py
"""
import os, sys, time, json, datetime, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from run_note_reassign_dl import remap_music_notes
from note_reassign import find_new_notes
from sequence_metrics import evaluate_sequence_metrics
from generation import notes_to_xml
from overlap import build_activation_matrix
from preprocessing import simul_chord_lists, simul_union_by_dict
from temporal_reorder import reorder_overlap_matrix

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED = 42
EPOCHS = 50
LR = 0.001
BATCH_SIZE = 32
N_CANDIDATES = 1000
PITCH_RANGE = (40, 88)


def build_continuous_overlap(data, cl):
    N = len(data['notes_label'])
    T = data['T']
    cp = simul_chord_lists(data['adn_i'][1][-1], data['adn_i'][2][-1])
    ns = simul_union_by_dict(cp, data['notes_dict'])
    nodes = list(range(1, N + 1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(ns))):
        if ns[t]:
            for n in ns[t]:
                if 1 <= n <= N:
                    ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)
    act_cont = build_activation_matrix(ntd_df, cl, continuous=True)
    return act_cont.values.astype(np.float32)


def run():
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model,
    )
    from sklearn.model_selection import train_test_split

    print("=" * 70)
    print("  방향 A+B 결합: note 재분배 + 시간 재배치 + continuous")
    print("=" * 70)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov_binary, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    # continuous overlap
    ov_cont = build_continuous_overlap(data, cl)
    print(f"  Continuous overlap: shape={ov_cont.shape}, mean={ov_cont.mean():.3f}")

    T = data['T']
    N = len(data['notes_label'])
    C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    # ── scale_major note 재분배 ──
    print(f"\n[scale_major] note 재분배...")
    reassign = find_new_notes(
        data['notes_label'], cl, seed=SEED,
        note_metric='tonnetz', cycle_metric='tonnetz',
        pitch_range=PITCH_RANGE, n_candidates=N_CANDIDATES,
        harmony_mode='scale', scale_type='major',
    )
    new_notes_label = reassign['new_notes_label']
    N_new = len(new_notes_label)
    print(f"  scale: {reassign.get('scale_root_name', '?')} major, N_new={N_new}")

    remapped = remap_music_notes(
        [data['inst1'], data['inst2']],
        data['notes_label'], new_notes_label
    )
    remapped_flat = remapped[0] + remapped[1]

    # ── 시간 재배치 전략 ──
    reorder_strategies = [
        ('none', None),
        ('segment_shuffle', {'strategy': 'segment_shuffle'}),
        ('block32', {'strategy': 'block_permute', 'block_size': 32}),
        ('block64', {'strategy': 'block_permute', 'block_size': 64}),
        ('markov_t1.0', {'strategy': 'markov_resample', 'temperature': 1.0}),
    ]

    # ── note 설정 ──
    note_configs = [
        ('orig', data['notes_label'], [data['inst1'], data['inst2']],
         N, original_notes),
        ('major', new_notes_label, remapped, N_new, remapped_flat),
    ]

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': EPOCHS,
        'scale_root': reassign.get('scale_root_name', ''),
        'experiments': {},
    }

    for note_name, nl, inst_pair, n_notes, ref_notes in note_configs:
        for reorder_name, reorder_kwargs in reorder_strategies:
            exp_name = f"{note_name}_{reorder_name}"

            # overlap 준비
            if reorder_kwargs is None:
                ov = ov_cont.copy()
                reorder_info = {'strategy': 'none'}
            else:
                ov, reorder_info = reorder_overlap_matrix(
                    ov_cont, seed=SEED, **reorder_kwargs
                )

            print(f"\n{'='*70}")
            print(f"  [{exp_name}] note={note_name}, reorder={reorder_name}")
            print(f"{'='*70}")
            if reorder_kwargs:
                print(f"  재배치 info: {reorder_info.get('strategy')}, "
                      f"n_segments={reorder_info.get('n_segments', reorder_info.get('n_blocks', ''))}")

            t1 = time.time()

            X, y = prepare_training_data(ov, inst_pair, nl, T, n_notes)
            X_tr, X_va, y_tr, y_va = train_test_split(
                X, y, test_size=0.2, random_state=SEED
            )

            model = MusicGeneratorTransformer(
                C, n_notes, d_model=128, nhead=4,
                num_layers=2, dropout=0.1, max_len=T
            )
            history = train_model(model, X_tr, y_tr, X_va, y_va,
                                  epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
                                  model_type='transformer', seq_len=T)
            val_loss = history[-1]['val_loss']

            gen = generate_from_model(model, ov, nl,
                                      model_type='transformer',
                                      adaptive_threshold=True)
            if not gen:
                print(f"  생성 실패")
                all_results['experiments'][exp_name] = {'error': 'no notes'}
                continue

            # MusicXML 출력
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            notes_to_xml([gen], tempo_bpm=66,
                         file_name=f"AB_{exp_name}_{ts}",
                         output_dir="./output")

            # 평가
            seq_orig = evaluate_sequence_metrics(gen, original_notes,
                                                 name=f"{exp_name}_vs_orig")
            seq_ref = evaluate_sequence_metrics(gen, ref_notes,
                                                name=f"{exp_name}_vs_ref")

            elapsed = time.time() - t1

            all_results['experiments'][exp_name] = {
                'val_loss': round(val_loss, 4),
                'n_notes': len(gen),
                'note_set': note_name,
                'reorder': reorder_name,
                'vs_original': {k: round(v, 6) for k, v in seq_orig.items()},
                'vs_ref': {k: round(v, 6) for k, v in seq_ref.items()},
                'elapsed_s': round(elapsed, 1),
            }

            vo = seq_orig
            vr = seq_ref
            print(f"  val_loss={val_loss:.4f}  notes={len(gen)}")
            print(f"  vs orig: pJS={vo['pitch_js']:.4f} DTW={vo['dtw']:.4f} tJS={vo['transition_js']:.4f}")
            print(f"  vs ref:  pJS={vr['pitch_js']:.4f} DTW={vr['dtw']:.4f} tJS={vr['transition_js']:.4f}")
            print(f"  소요: {elapsed:.1f}s")

    # ── 요약 ──
    elapsed_total = time.time() - t0

    print(f"\n{'='*110}")
    print(f"  요약: note × reorder (continuous Transformer)")
    print(f"{'='*110}")
    print(f"  {'실험':<25} {'vloss':>6} {'notes':>6} "
          f"{'pJS(orig)':>10} {'DTW(orig)':>10} {'tJS(orig)':>10} "
          f"{'pJS(ref)':>10} {'DTW(ref)':>10}")
    print(f"  {'─'*25} {'─'*6} {'─'*6} "
          f"{'─'*10} {'─'*10} {'─'*10} "
          f"{'─'*10} {'─'*10}")

    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<25} ERROR"); continue
        vo = r['vs_original']
        vr = r['vs_ref']
        print(f"  {name:<25} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
              f"{vo['pitch_js']:>10.4f} {vo['dtw']:>10.4f} {vo['transition_js']:>10.4f} "
              f"{vr['pitch_js']:>10.4f} {vr['dtw']:>10.4f}")

    # JSON
    out_path = os.path.join("docs", "step3_data", "combined_AB_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
    print(f"총 소요: {elapsed_total:.1f}s")


if __name__ == '__main__':
    run()
