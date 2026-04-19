"""
gen_gap3_comparison.py — gap_min=0 vs gap_min=3 청취 비교 WAV 생성 (세션 C)
============================================================================

gap_min 설정이 음악적으로 올바른지 청각 평가하기 위한 비교 세트.

생성 파일 (output/ 폴더):
  1. hibari_dft_gap0_algo1.wav   — DFT, gap_min=0 (이전 설정)
  2. hibari_dft_gap3_algo1.wav   — DFT, gap_min=3 (새 설정, 1.5박 간격 제약)
  3. hibari_dft_gap3_transformer.wav — DFT, gap_min=3, Transformer Algo2
  4. hibari_original.wav          — 원곡 참조 (없으면 생성)

설정:
  - DFT cache: cache/metric_dft.pkl (사전 계산된 binary overlap + cycle_labeled)
  - w_o=0.3, w_d=1.0 (§4.1a/b 최적값)
  - Algo1: N=5 시도, best JS 선택
  - Transformer: N=1 (빠른 생성)

실행:
  cd C:\\WK14\\tda_pipeline
  python gen_gap3_comparison.py
"""

import os, sys, json, random, pickle, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings('ignore')

from pipeline import TDAMusicPipeline, PipelineConfig
from preprocessing import simul_chord_lists, simul_union_by_dict
from generation import (
    algorithm1_optimized, NodePool, CycleSetManager,
    generate_from_model, prepare_training_data, train_model,
    MusicGeneratorFC,
)
from eval_metrics import evaluate_generation
import pretty_midi

try:
    from wav_renderer import render_midi_to_wav
    HAS_WAV = True
except ImportError:
    HAS_WAV = False
    print("[WARNING] wav_renderer 없음 — MIDI만 저장됩니다.")

# ─── 상수 ────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(BASE_DIR, 'output')
CACHE_PATH  = os.path.join(BASE_DIR, 'cache', 'metric_dft.pkl')
HIBARI_MID  = os.path.join(BASE_DIR, 'Ryuichi_Sakamoto_-_hibari.mid')
T_TOTAL     = 1088
TEMPO_BPM   = 66
MODULES     = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
INST_CHORD_HEIGHTS = MODULES * 34   # ~1088 timestep

# ─── 유틸 ────────────────────────────────────────────────────────────────────

def build_note_time_df(p):
    adn_i       = p._cache['adn_i']
    notes_dict  = p._cache['notes_dict']
    notes_label = p._cache['notes_label']
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets   = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list  = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T_TOTAL, len(nodes_list)), dtype=int)
    for t in range(min(T_TOTAL, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


def gen_to_file(gen, wav_path, mid_path, label):
    """gen → pretty_midi MIDI → WAV.  music21의 PPQN 초과 문제를 우회."""
    if not gen:
        print(f"  [SKIP] {label}: gen 없음")
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sec_per_8th = 60.0 / TEMPO_BPM / 2.0

    pm = pretty_midi.PrettyMIDI(initial_tempo=float(TEMPO_BPM))
    inst = pretty_midi.Instrument(program=0, name='Piano')
    for (start_idx, pitch, end_idx) in gen:
        note = pretty_midi.Note(
            velocity=80,
            pitch=int(pitch),
            start=float(start_idx) * sec_per_8th,
            end=float(end_idx) * sec_per_8th,
        )
        inst.notes.append(note)
    pm.instruments.append(inst)
    pm.write(mid_path)
    print(f"  MIDI: {mid_path}")

    if HAS_WAV:
        dur = render_midi_to_wav(mid_path, wav_path)
        print(f"  WAV : {wav_path}  ({dur:.1f}s)")
        return dur
    return None


def run_algo1_best(shared, overlap_values, cycle_labeled,
                   n_trials=5, seed_base=42, min_onset_gap=3):
    """N=n_trials Algo1 실행, best JS trial 반환."""
    best_js, best_gen = float('inf'), None
    for i in range(n_trials):
        seed = seed_base + i
        random.seed(seed); np.random.seed(seed)
        pool    = NodePool(shared['notes_label'], shared['notes_counts'], num_modules=65)
        manager = CycleSetManager(cycle_labeled)
        gen = algorithm1_optimized(
            pool, INST_CHORD_HEIGHTS, overlap_values, manager,
            max_resample=50, verbose=False, min_onset_gap=min_onset_gap
        )
        if not gen:
            continue
        r = evaluate_generation(
            gen, [shared['inst1_real'], shared['inst2_real']],
            shared['notes_label'], name=""
        )
        js = r['js_divergence']
        print(f"    seed={seed:3d}  JS={js:.4f}  notes={len(gen)}")
        if js < best_js:
            best_js, best_gen = js, gen
    print(f"  → best JS = {best_js:.4f}")
    return best_gen, best_js


def run_transformer(shared, overlap_values, cycle_labeled,
                    note_time_df, seed=42, min_onset_gap=3):
    """Transformer 학습 + 생성."""
    try:
        import torch
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        print(f"  [SKIP] torch/sklearn 없음: {e}")
        return None, None

    notes_label = shared['notes_label']
    N = len(notes_label)
    K = overlap_values.shape[1]

    # Transformer용 binary overlap을 float32로
    ov_f = overlap_values.astype(np.float32)

    X, y = prepare_training_data(
        ov_f,
        [shared['inst1_real'], shared['inst2_real']],
        notes_label, T_TOTAL, N
    )
    X_tr, X_v, y_tr, y_v = train_test_split(X, y, test_size=0.2, random_state=seed)

    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)

    from generation import MusicGeneratorTransformer
    model = MusicGeneratorTransformer(
        num_cycles=K, num_notes=N,
        d_model=128, nhead=4, num_layers=2, dropout=0.3
    )

    t0 = time.time()
    hist = train_model(
        model, X_tr, y_tr, X_v, y_v,
        epochs=200, lr=0.001, batch_size=32,
        model_type='transformer', seq_len=T_TOTAL
    )
    tt = time.time() - t0
    vl = hist[-1]['val_loss'] if hist else None
    print(f"  Transformer 학습 {tt:.1f}s  val_loss={vl:.4f}" if vl else f"  완료 {tt:.1f}s")

    gen = generate_from_model(
        model, ov_f, notes_label,
        model_type='transformer', adaptive_threshold=True,
        min_onset_gap=min_onset_gap
    )
    if gen:
        r = evaluate_generation(
            gen, [shared['inst1_real'], shared['inst2_real']],
            notes_label, name=""
        )
        js = r['js_divergence']
        print(f"  → Transformer JS = {js:.4f}  notes={len(gen)}")
        return gen, js
    return None, None


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    os.chdir(BASE_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    print("\n" + "═"*60)
    print("  gap_min=0 vs gap_min=3 청취 비교 세트 생성")
    print("  설정: DFT binary overlap (cache/metric_dft.pkl)")
    print("═"*60)

    # ── 0. 원곡 WAV ──────────────────────────────────────────────────────────
    orig_wav = os.path.join(OUTPUT_DIR, 'hibari_original.wav')
    if os.path.exists(orig_wav):
        print(f"\n[0] 원곡 WAV 이미 존재: {orig_wav}")
    elif HAS_WAV and os.path.exists(HIBARI_MID):
        print("\n[0] 원곡 MIDI → WAV 렌더링...")
        dur = render_midi_to_wav(HIBARI_MID, orig_wav)
        print(f"  완료: {orig_wav}  ({dur:.1f}s)")
    results['original'] = {'wav': orig_wav}

    # ── 공통 전처리 ────────────────────────────────────────────────────────
    print("\n[전처리] Pipeline 초기화...")
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    note_time_df = build_note_time_df(p)
    shared = {
        'notes_label':  p._cache['notes_label'],
        'notes_counts': p._cache['notes_counts'],
        'inst1_real':   p._cache['inst1_real'],
        'inst2_real':   p._cache['inst2_real'],
    }
    print(f"  notes={len(shared['notes_label'])}종")

    # ── DFT 캐시 로드 ─────────────────────────────────────────────────────
    print(f"\n[캐시] DFT overlap 로드: {CACHE_PATH}")
    if not os.path.exists(CACHE_PATH):
        print("  [ERROR] cache/metric_dft.pkl 없음. run_dft_gap3_suite.py를 먼저 실행하세요.")
        return

    with open(CACHE_PATH, 'rb') as f:
        dft_cache = pickle.load(f)

    # overlap: DataFrame (T, K) or ndarray
    ov_df = dft_cache['overlap']
    cycle_labeled = dft_cache['cycle_labeled']

    if hasattr(ov_df, 'values'):
        overlap_values = ov_df.values.astype(np.float32)
    else:
        overlap_values = np.array(ov_df, dtype=np.float32)

    K = overlap_values.shape[1]
    print(f"  overlap shape: {overlap_values.shape}  K={K}")

    # ── 1. gap_min=0, DFT, Algo1 ─────────────────────────────────────────
    print("\n" + "═"*60)
    print("  [1] gap_min=0  DFT  Algo1  (N=5, best JS)")
    print("═"*60)
    gen_g0, js_g0 = run_algo1_best(
        shared, overlap_values, cycle_labeled,
        n_trials=5, seed_base=42, min_onset_gap=0
    )
    wav_g0 = os.path.join(OUTPUT_DIR, 'hibari_dft_gap0_algo1.wav')
    mid_g0 = os.path.join(OUTPUT_DIR, 'hibari_dft_gap0_algo1.mid')
    gen_to_file(gen_g0, wav_g0, mid_g0, 'DFT gap_min=0 Algo1')
    results['dft_gap0_algo1'] = {
        'js': round(js_g0, 4),
        'wav': wav_g0,
        'config': 'DFT, gap_min=0, Algorithm 1',
    }

    # ── 2. gap_min=3, DFT, Algo1 ─────────────────────────────────────────
    print("\n" + "═"*60)
    print("  [2] gap_min=3  DFT  Algo1  (N=5, best JS)  ← 새 설정")
    print("═"*60)
    gen_g3, js_g3 = run_algo1_best(
        shared, overlap_values, cycle_labeled,
        n_trials=5, seed_base=42, min_onset_gap=3
    )
    wav_g3 = os.path.join(OUTPUT_DIR, 'hibari_dft_gap3_algo1.wav')
    mid_g3 = os.path.join(OUTPUT_DIR, 'hibari_dft_gap3_algo1.mid')
    gen_to_file(gen_g3, wav_g3, mid_g3, 'DFT gap_min=3 Algo1')
    results['dft_gap3_algo1'] = {
        'js': round(js_g3, 4),
        'wav': wav_g3,
        'config': 'DFT, gap_min=3, Algorithm 1',
        'gap_min': 3,
    }

    # ── 3. gap_min=3, DFT, Transformer ───────────────────────────────────
    print("\n" + "═"*60)
    print("  [3] gap_min=3  DFT  Transformer Algo2  (N=5 학습, ~3분)")
    print("═"*60)
    gen_tr, js_tr = run_transformer(
        shared, overlap_values, cycle_labeled,
        note_time_df, seed=42, min_onset_gap=3
    )
    wav_tr = os.path.join(OUTPUT_DIR, 'hibari_dft_gap3_transformer.wav')
    mid_tr = os.path.join(OUTPUT_DIR, 'hibari_dft_gap3_transformer.mid')
    if gen_tr:
        gen_to_file(gen_tr, wav_tr, mid_tr, 'DFT gap_min=3 Transformer')
        results['dft_gap3_transformer'] = {
            'js': round(js_tr, 4) if js_tr else None,
            'wav': wav_tr,
            'config': 'DFT, gap_min=3, Transformer',
            'gap_min': 3,
        }

    # ── 요약 ──────────────────────────────────────────────────────────────
    print("\n" + "═"*60)
    print("  📋 생성 완료 요약")
    print("═"*60)
    for tag, info in results.items():
        js_str = f"JS={info['js']:.4f}" if info.get('js') else ""
        print(f"  {tag:35s}  {js_str}")
        print(f"    {info.get('wav', '—')}")
        if info.get('config'):
            print(f"    설정: {info['config']}")

    print(f"\n  🎧 청취 포인트:")
    print("  1. gap_min=0 vs gap_min=3: 음들의 밀집도, onset 간격감")
    print("  2. gap_min=3: 1.5박(8분음표 3개) 간격 제약 → 보다 '호흡이 있는' 느낌?")
    print("  3. Transformer: DL 기반 구조 학습 vs Algo1 확률 샘플링")

    # JSON 저장
    out_json = os.path.join(OUTPUT_DIR, 'gap3_comparison_results.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  결과 메타: {out_json}")
    print("\n[완료]")


if __name__ == '__main__':
    main()
