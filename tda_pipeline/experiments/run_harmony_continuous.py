"""
run_harmony_continuous.py — 화성 제약 + continuous overlap + Transformer

개선 F에서 continuous overlap이 binary보다 JS 2.3배 개선됨 (0.0014→0.0006).
이를 화성 제약 note 재분배에 결합:
  - binary vs continuous overlap × scale_major

사용법:
  python run_harmony_continuous.py
"""
import os, sys, time, json, datetime, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from run_note_reassign_dl import remap_music_notes
from note_reassign import find_new_notes, SCALES
from sequence_metrics import evaluate_sequence_metrics
from generation import notes_to_xml
from overlap import build_activation_matrix
from preprocessing import simul_chord_lists, simul_union_by_dict

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
    """continuous activation matrix 구축 (개선 F와 동일 방식)."""
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
    act_bin = build_activation_matrix(ntd_df, cl, continuous=False)
    return act_cont.values.astype(np.float32), act_bin.values.astype(np.float32)


def run():
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model,
    )
    from sklearn.model_selection import train_test_split

    print("=" * 70)
    print("  화성 제약 + continuous overlap + Transformer")
    print("=" * 70)

    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov_binary, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles"); return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    # continuous overlap 구축
    ov_cont, ov_bin_fresh = build_continuous_overlap(data, cl)
    print(f"  Binary density:     {(ov_bin_fresh > 0).mean():.3f}")
    print(f"  Continuous density: {(ov_cont > 0).mean():.3f}, mean={ov_cont.mean():.3f}")

    T = data['T']
    N = len(data['notes_label'])
    C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': EPOCHS, 'experiments': {},
    }

    # ── scale_major note 재분배 ──
    print(f"\n[scale_major] note 재분배...")
    reassign = find_new_notes(
        data['notes_label'], cl, seed=SEED,
        note_metric='tonnetz', cycle_metric='tonnetz',
        pitch_range=PITCH_RANGE, n_candidates=N_CANDIDATES,
        harmony_mode='scale', scale_type='major',
    )
    new_notes_label = reassign['new_notes_label']
    new_pitches = [n[0] for n in reassign['new_notes']]
    N_new = len(new_notes_label)

    print(f"  note 오차: {reassign['note_dist_error']:.4f}")
    print(f"  cycle 오차: {reassign['cycle_dist_error']:.4f}")
    print(f"  scale: {reassign.get('scale_root_name', '?')} major")
    print(f"  새 pitch: {new_pitches}")

    # 원곡 음표를 새 note로 치환
    remapped = remap_music_notes(
        [data['inst1'], data['inst2']],
        data['notes_label'], new_notes_label
    )
    remapped_flat = remapped[0] + remapped[1]
    print(f"  치환: inst1={len(remapped[0])}, inst2={len(remapped[1])}")

    # ── 4가지 조합: {원곡, reassign} × {binary, continuous} ──
    experiments = [
        ('orig_binary',    data['notes_label'], [data['inst1'], data['inst2']],
         ov_binary, N, original_notes, "원곡 note"),
        ('orig_continuous', data['notes_label'], [data['inst1'], data['inst2']],
         ov_cont, N, original_notes, "원곡 note"),
        ('major_binary',   new_notes_label, remapped,
         ov_binary, N_new, remapped_flat, "scale_major"),
        ('major_continuous', new_notes_label, remapped,
         ov_cont, N_new, remapped_flat, "scale_major"),
    ]

    for exp_name, nl, inst_pair, ov, n_notes, ref_notes, desc in experiments:
        print(f"\n{'='*70}")
        print(f"  [{exp_name}] {desc} + {'continuous' if 'cont' in exp_name else 'binary'}")
        print(f"{'='*70}")

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
                                  model_type='transformer', adaptive_threshold=True)
        if not gen:
            print(f"  생성 실패")
            all_results['experiments'][exp_name] = {'error': 'no notes'}
            continue

        print(f"  생성: {len(gen)}개 음표, val_loss={val_loss:.4f}")

        # MusicXML 출력
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        notes_to_xml([gen], tempo_bpm=66,
                     file_name=f"cont_{exp_name}_{ts}",
                     output_dir="./output")

        # 평가: vs 원곡 + vs 자기 참조
        seq_orig = evaluate_sequence_metrics(gen, original_notes, name=f"{exp_name}_vs_orig")
        seq_ref = evaluate_sequence_metrics(gen, ref_notes, name=f"{exp_name}_vs_ref")

        elapsed = time.time() - t1

        all_results['experiments'][exp_name] = {
            'val_loss': round(val_loss, 4),
            'n_notes': len(gen),
            'overlap_type': 'continuous' if 'cont' in exp_name else 'binary',
            'note_set': 'original' if 'orig' in exp_name else 'scale_major',
            'vs_original': {k: round(v, 6) for k, v in seq_orig.items()},
            'vs_ref': {k: round(v, 6) for k, v in seq_ref.items()},
            'elapsed_s': round(elapsed, 1),
        }

        print(f"  vs orig: pJS={seq_orig['pitch_js']:.4f} DTW={seq_orig['dtw']:.4f}")
        print(f"  vs ref:  pJS={seq_ref['pitch_js']:.4f} DTW={seq_ref['dtw']:.4f}")
        print(f"  소요: {elapsed:.1f}s")

    # ── 요약 ──
    elapsed_total = time.time() - t0

    print(f"\n{'='*100}")
    print(f"  요약: binary vs continuous × original vs scale_major")
    print(f"{'='*100}")
    print(f"  {'실험':<25} {'vloss':>6} {'notes':>6} {'pJS(orig)':>10} {'DTW(orig)':>10} {'pJS(ref)':>10} {'DTW(ref)':>10}")
    print(f"  {'─'*25} {'─'*6} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<25} ERROR"); continue
        vo = r['vs_original']
        vr = r['vs_ref']
        print(f"  {name:<25} {r['val_loss']:>6.3f} {r['n_notes']:>6} "
              f"{vo['pitch_js']:>10.4f} {vo['dtw']:>10.4f} "
              f"{vr['pitch_js']:>10.4f} {vr['dtw']:>10.4f}")

    # JSON 저장
    out_path = os.path.join("docs", "step3_data", "harmony_continuous_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")
    print(f"총 소요: {elapsed_total:.1f}s")


if __name__ == '__main__':
    run()
