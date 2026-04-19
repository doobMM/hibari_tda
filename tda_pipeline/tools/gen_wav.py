"""
gen_wav.py — 통합 WAV 생성 스크립트

기존 5개 파일을 통합:
  gen_exp3_wav.py          → --mode exp3
  gen_harmony_wav.py       → --mode harmony
  gen_reassign_transformer_wav.py → --mode reassign_batch
  gen_tonnetz_vwide_wav.py → --mode reassign --note-metric tonnetz --pitch-range 40 88
  gen_vl_wide_wav.py       → --mode reassign --note-metric voice_leading --pitch-range 48 84

사용법:
  python gen_wav.py --mode harmony
  python gen_wav.py --mode reassign --note-metric tonnetz --pitch-range 40 88
  python gen_wav.py --mode reassign_batch --glob "output/reassign_*.musicxml"
  python gen_wav.py --mode exp3 --strategy segment_shuffle
"""
import os, sys, glob, argparse, warnings
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wav_renderer import render_midi_to_wav, musicxml_to_wav, score_to_wav


# ═══════════════════════════════════════════════════════════════════════
# Mode: harmony — 기존 MusicXML 파일 → WAV 변환
# ═══════════════════════════════════════════════════════════════════════

def mode_harmony(args):
    """MusicXML 파일 목록을 Piano WAV로 변환."""
    targets = args.files or [
        'harmony_scale_penta.musicxml',
        'harmony_scale_major.musicxml',
        'harmony_dl_scale_major_20260410_191703.musicxml',
    ]
    out_dir = os.path.join(os.path.dirname(__file__), 'output')

    for fname in targets:
        xml_path = os.path.join(out_dir, fname)
        if not os.path.exists(xml_path):
            print(f"[SKIP] {fname} 없음")
            continue
        wav_name = fname.replace('.musicxml', '_piano.wav')
        wav_path = os.path.join(out_dir, wav_name)
        print(f"[변환] {fname} → {wav_name}")
        dur = musicxml_to_wav(xml_path, wav_path)
        print(f"  완료: {wav_path} ({dur:.1f}s)")

    print("\n모두 완료!")


# ═══════════════════════════════════════════════════════════════════════
# Mode: reassign_batch — glob 패턴으로 MusicXML 일괄 변환
# ═══════════════════════════════════════════════════════════════════════

def mode_reassign_batch(args):
    """glob 패턴으로 MusicXML 파일을 일괄 WAV 변환."""
    pattern = args.glob_pattern or "output/reassign_tonnetz_*_transformer_*.musicxml"
    files = sorted(glob.glob(pattern))
    print(f"변환 대상: {len(files)}개")

    from music21 import converter
    for xml_path in files:
        base = os.path.splitext(os.path.basename(xml_path))[0]
        mid_path = xml_path.replace('.musicxml', '.mid')
        wav_path = xml_path.replace('.musicxml', '_piano.wav')

        print(f"\n{'='*60}\n  {base}\n{'='*60}")
        print("  [1/2] MusicXML → MIDI...")
        score = converter.parse(xml_path)
        score.write('midi', fp=mid_path)

        print("  [2/2] MIDI → Piano WAV...")
        duration = render_midi_to_wav(mid_path, wav_path)
        print(f"    WAV: {wav_path} ({duration:.1f}s)")

    print("\n모두 완료!")


# ═══════════════════════════════════════════════════════════════════════
# Mode: reassign — note 재분배 → Algo1 생성 → WAV
# ═══════════════════════════════════════════════════════════════════════

def mode_reassign(args):
    """거리 보존 note 재분배 → Algorithm 1 생성 → WAV."""
    from run_any_track import preprocess, compute_ph
    from note_reassign import find_new_notes
    from run_note_reassign import run_algo1_with_new_notes
    from generation import notes_to_xml

    note_metric = args.note_metric
    pitch_lo, pitch_hi = args.pitch_range
    seed = args.seed
    label = f"{note_metric}_{pitch_lo}_{pitch_hi}"

    print(f"[1/5] 전처리...")
    data = preprocess(args.midi)
    print(f"  T={data['T']}, N={data['N']}, C={data['num_chords']}")

    print(f"[2/5] Persistent Homology...")
    cl, ov, n_cyc, ph_time = compute_ph(data, "tonnetz")
    print(f"  tonnetz: {n_cyc} cycles ({ph_time:.1f}s)")

    print(f"[3/5] {note_metric} 새 note 탐색 (pitch {pitch_lo}-{pitch_hi})...")
    result = find_new_notes(
        data['notes_label'], cl,
        note_metric=note_metric, cycle_metric=note_metric,
        pitch_range=(pitch_lo, pitch_hi), n_candidates=1000, seed=seed
    )
    print(f"  note 거리 오차:  {result['note_dist_error']:.4f}")
    print(f"  cycle 거리 오차: {result['cycle_dist_error']:.4f}")

    print(f"[4/5] Algo1 생성...")
    gen = run_algo1_with_new_notes(data, ov, cl,
                                   result['new_notes_label'], seed=seed)
    print(f"  생성된 음표 수: {len(gen)}")

    print(f"[5/5] MusicXML → MIDI → Piano WAV...")
    out_dir = os.path.join("output", f"note_reassign_{label}")
    os.makedirs(out_dir, exist_ok=True)

    score = notes_to_xml([gen], tempo_bpm=66,
                         file_name=label, output_dir=out_dir)
    if score:
        mid_path = os.path.join(out_dir, f"{label}.mid")
        wav_path = os.path.join(out_dir, f"{label}_piano.wav")
        dur = score_to_wav(score, mid_path, wav_path)
        print(f"  Piano WAV: {wav_path} ({dur:.1f}s)")

    print("\n완료!")


# ═══════════════════════════════════════════════════════════════════════
# Mode: exp3 — Transformer 학습 + 재배치 생성 → WAV
# ═══════════════════════════════════════════════════════════════════════

def mode_exp3(args):
    """시간 재배치 + Transformer 학습 → 생성 → WAV."""
    from run_any_track import preprocess, compute_ph
    from temporal_reorder import reorder_overlap_matrix
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model, notes_to_xml
    )
    from sklearn.model_selection import train_test_split
    import torch

    seed = args.seed
    strategy = args.strategy

    print("[1/5] 전처리...")
    data = preprocess(args.midi)
    T = data['T']; N = len(data['notes_label'])
    print(f"  T={T}, N={N}, C={data['num_chords']}")

    print("[2/5] Persistent Homology...")
    cl, ov, n_cyc, ph_time = compute_ph(data, "tonnetz")
    C = n_cyc
    print(f"  tonnetz: {n_cyc} cycles ({ph_time:.1f}s)")

    print(f"[3/5] {strategy} 재배치 + 학습 데이터 준비...")
    reordered, info = reorder_overlap_matrix(ov, strategy=strategy, seed=seed)

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N
    )
    X_reord = reordered.astype(np.float32)
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_reord, y_orig, test_size=0.2, random_state=seed)

    print("[4/5] Transformer 학습 (noPE + retrain)...")
    model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                      num_layers=2, dropout=0.1, max_len=T,
                                      use_pos_emb=False)
    history = train_model(
        model, X_tr, y_tr, X_va, y_va,
        epochs=args.epochs, lr=0.001, batch_size=32,
        model_type='transformer', seq_len=T
    )
    print(f"  val_loss: {history[-1]['val_loss']:.4f}")

    print("[5/5] 음악 생성 + WAV 변환...")
    gen = generate_from_model(
        model, reordered, data['notes_label'],
        model_type='transformer', adaptive_threshold=True
    )
    print(f"  생성된 음표 수: {len(gen)}")

    out_name = f"exp3_noPE_retrain_{strategy}"
    out_dir = os.path.join("output", out_name)
    os.makedirs(out_dir, exist_ok=True)

    score = notes_to_xml([gen], tempo_bpm=66,
                         file_name=out_name, output_dir=out_dir)
    if score:
        mid_path = os.path.join(out_dir, f"{out_name}.mid")
        wav_path = os.path.join(out_dir, f"{out_name}_piano.wav")
        dur = score_to_wav(score, mid_path, wav_path)
        print(f"  Piano WAV: {wav_path} ({dur:.1f}s)")

    print("\n완료!")


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="통합 WAV 생성 스크립트")
    parser.add_argument('--mode', required=True,
                        choices=['harmony', 'reassign_batch', 'reassign', 'exp3'])
    parser.add_argument('--midi', default="Ryuichi_Sakamoto_-_hibari.mid")
    parser.add_argument('--seed', type=int, default=42)

    # harmony
    parser.add_argument('--files', nargs='*', help="harmony 모드: MusicXML 파일 목록")

    # reassign_batch
    parser.add_argument('--glob-pattern', dest='glob_pattern',
                        help="reassign_batch 모드: glob 패턴")

    # reassign
    parser.add_argument('--note-metric', dest='note_metric', default='tonnetz',
                        choices=['tonnetz', 'voice_leading', 'frequency', 'dft'])
    parser.add_argument('--pitch-range', dest='pitch_range', nargs=2, type=int,
                        default=[40, 88], metavar=('LO', 'HI'))

    # exp3
    parser.add_argument('--strategy', default='segment_shuffle',
                        choices=['segment_shuffle', 'block_permute',
                                 'markov_resample'])
    parser.add_argument('--epochs', type=int, default=50)

    args = parser.parse_args()

    dispatch = {
        'harmony': mode_harmony,
        'reassign_batch': mode_reassign_batch,
        'reassign': mode_reassign,
        'exp3': mode_exp3,
    }
    dispatch[args.mode](args)


if __name__ == '__main__':
    main()
