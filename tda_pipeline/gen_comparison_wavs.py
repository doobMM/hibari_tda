"""
gen_comparison_wavs.py — 청취 비교 평가용 WAV 생성 (C 세션, 2026-04-16)
=========================================================================

생성 대상 (5개):
  1. output/hibari_complex_algo1_best.wav    — 실험 B (complex α=0.25) + Algo1 best JS
  2. output/hibari_complex_algo2_fc.wav      — 실험 B + Algo2 FC continuous
  3. output/hibari_timeflow_algo1_best.wav   — timeflow (α=0.5 cache) + per-cycle τ + Algo1 best JS
  4. output/hibari_timeflow_algo2_fc.wav     — timeflow + FC continuous
  5. output/hibari_original.wav              — 원곡 MIDI → WAV (렌더링만)

참조:
  - 실험 B 설정: run_complex_n20.py (B_BEST_TAUS, α=0.25, ow=0.0, dw=0.3, rc=0.1)
  - timeflow best_taus: docs/step3_data/percycle_tau_n20_results.json
  - WAV 렌더러: wav_renderer.py (페달+리버브 포함)

실행:
  cd tda_pipeline && python gen_comparison_wavs.py
"""

import os, sys, json, random, pickle, time
import numpy as np
import pandas as pd
warnings_imported = False
try:
    import warnings
    warnings.filterwarnings('ignore')
    warnings_imported = True
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from preprocessing import simul_chord_lists, simul_union_by_dict
from overlap import build_activation_matrix
from generation import (algorithm1_optimized, NodePool, CycleSetManager,
                         notes_to_xml, MusicGeneratorFC, prepare_training_data,
                         train_model, generate_from_model)
from eval_metrics import evaluate_generation
import pretty_midi
from wav_renderer import render_midi_to_wav, score_to_wav

# ─── 상수 ────────────────────────────────────────────────────────────────────

RATE_T      = 0.3
T_TOTAL     = 1088
ALGO1_MOD   = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
               4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]

# 실험 B best_taus (run_complex_n20.py에서 복사, 재탐색 금지)
B_BEST_TAUS = [0.3,0.1,0.5,0.6,0.5,0.4,0.1,0.4,0.35,0.6,
               0.7,0.1,0.6,0.5,0.3,0.6,0.7,0.1,0.1,0.1,
               0.1,0.5,0.3,0.1,0.1,0.7,0.6,0.6,0.4,0.1,
               0.7,0.1,0.7,0.35,0.1,0.35,0.3,0.1,0.6,0.1]

OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
HIBARI_MID  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'Ryuichi_Sakamoto_-_hibari.mid')


# ─── 공통 유틸 ───────────────────────────────────────────────────────────────

def build_note_time_df(p):
    adn_i      = p._cache['adn_i']
    notes_dict = p._cache['notes_dict']
    notes_label= p._cache['notes_label']
    chord_pairs= simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets  = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))
    ntd = np.zeros((T_TOTAL, len(nodes_list)), dtype=int)
    for t in range(min(T_TOTAL, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


def make_overlap_from_taus(cont_act, best_taus, K):
    """best_taus per-cycle τ → 이진 overlap 행렬."""
    ov = np.zeros_like(cont_act)
    for ci, tau in enumerate(best_taus[:K]):
        ov[:, ci] = (cont_act[:, ci] >= tau).astype(float)
    return ov


def run_algo1_best(shared, ov, cyc, n_trials=5, seed_base=42):
    """N=n_trials Algo1 실행, best JS trial의 gen 반환."""
    best_js  = float('inf')
    best_gen = None
    for i in range(n_trials):
        seed = seed_base + i
        random.seed(seed); np.random.seed(seed)
        pool    = NodePool(shared['notes_label'], shared['notes_counts'], num_modules=65)
        manager = CycleSetManager(cyc)
        gen = algorithm1_optimized(pool, list(ALGO1_MOD) * 34,  # ~1088 steps
                                   ov, manager, max_resample=50, verbose=False)
        if not gen:
            continue
        r = evaluate_generation(gen, [shared['inst1_real'], shared['inst2_real']],
                                 shared['notes_label'], name="")
        js = r['js_divergence']
        print(f"    seed={seed:3d}  JS={js:.4f}")
        if js < best_js:
            best_js  = js
            best_gen = gen
    print(f"  → Algo1 best JS = {best_js:.4f}")
    return best_gen, best_js


def run_algo2_fc(shared, cont_act, epochs=80):
    """FC 학습 + 생성, (gen, js, model) 반환."""
    try:
        import torch
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        print(f"  [SKIP] torch/sklearn 없음: {e}")
        return None, None, None

    N = len(shared['notes_label'])
    K = cont_act.shape[1]

    X, y = prepare_training_data(
        cont_act, [shared['inst1_real'], shared['inst2_real']],
        shared['notes_label'], T_TOTAL, N
    )
    X_tr, X_v, y_tr, y_v = train_test_split(X, y, test_size=0.2, random_state=42)

    import torch
    torch.manual_seed(42)
    model = MusicGeneratorFC(num_cycles=K, num_notes=N, hidden_dim=128, dropout=0.3)
    t0 = time.time()
    hist = train_model(model, X_tr, y_tr, X_v, y_v,
                       epochs=epochs, lr=0.001, batch_size=32,
                       model_type='fc', seq_len=T_TOTAL)
    tt = time.time() - t0
    vl = hist[-1]['val_loss'] if hist else None
    print(f"  Algo2 FC 학습: {tt:.1f}s  val_loss={vl:.4f}" if vl else f"  완료 {tt:.1f}s")

    # best of 3 trials
    best_js, best_gen = float('inf'), None
    for i in range(3):
        torch.manual_seed(i); random.seed(i); np.random.seed(i)
        gen = generate_from_model(model, cont_act, shared['notes_label'],
                                   model_type='fc', adaptive_threshold=True)
        if not gen:
            continue
        r = evaluate_generation(gen, [shared['inst1_real'], shared['inst2_real']],
                                  shared['notes_label'], name="")
        js = r['js_divergence']
        print(f"    trial {i}: JS={js:.4f}")
        if js < best_js:
            best_js, best_gen = js, gen
    print(f"  → Algo2 FC best JS = {best_js:.4f}")
    return best_gen, best_js, model


def gen_to_wav(gen, wav_path, mid_path, label, tempo_bpm=66):
    """생성 음표 리스트 → pretty_midi MIDI → WAV.

    music21은 10080 PPQN MIDI를 생성해 pretty_midi의 최대 틱 한계(1e7)를 초과함.
    pretty_midi (220 PPQN)로 직접 MIDI를 작성하여 우회.
    """
    if not gen:
        print(f"  [SKIP] {label}: gen 없음")
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 8th-note index → seconds
    sec_per_8th = 60.0 / tempo_bpm / 2.0   # at 66 BPM: 0.4545...s

    pm = pretty_midi.PrettyMIDI(initial_tempo=float(tempo_bpm))
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

    dur = render_midi_to_wav(mid_path, wav_path)
    print(f"  WAV: {wav_path}  ({dur:.1f}s)")
    return dur


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    # ══════════════════════════════════════════════════════════════════════════
    # 0. 원곡 WAV
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═"*60)
    print("  0. 원곡 hibari MIDI → WAV")
    print("═"*60)
    orig_wav = os.path.join(OUTPUT_DIR, 'hibari_original.wav')
    if os.path.exists(orig_wav):
        print(f"  이미 존재: {orig_wav}")
        results['original'] = {'wav': orig_wav}
    else:
        dur = render_midi_to_wav(HIBARI_MID, orig_wav)
        print(f"  완료: {orig_wav}  ({dur:.1f}s)")
        results['original'] = {'wav': orig_wav, 'duration_s': round(dur, 1)}

    # ══════════════════════════════════════════════════════════════════════════
    # 공통 전처리
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═"*60)
    print("  공통 전처리")
    print("═"*60)
    base_p = TDAMusicPipeline(PipelineConfig())
    base_p.run_preprocessing()
    preproc_cache = dict(base_p._cache)

    note_time_df = build_note_time_df(base_p)
    shared = {
        'notes_label':  base_p._cache['notes_label'],
        'notes_counts': base_p._cache['notes_counts'],
        'inst1_real':   base_p._cache['inst1_real'],
        'inst2_real':   base_p._cache['inst2_real'],
    }
    print(f"  notes={len(shared['notes_label'])}종")

    # ══════════════════════════════════════════════════════════════════════════
    # 1. Timeflow (α=0.5 cache) + per-cycle τ
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═"*60)
    print("  1. Timeflow 비교 기준 — per-cycle τ (JS≈0.0241)")
    print("    설정: α=0.5, ow=0.3 (metric_tonnetz.pkl), K=42")
    print("═"*60)

    # cycle_labeled 로드 (캐시)
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        tf_cache = pickle.load(f)
    cyc_tf = tf_cache['cycle_labeled']
    K_tf   = len(cyc_tf)
    print(f"  K={K_tf}")

    # percycle_tau_n20_results.json에서 best_taus 로드
    percycle_path = 'docs/step3_data/percycle_tau_n20_results.json'
    with open(percycle_path) as f:
        percycle_data = json.load(f)
    tf_best_taus = percycle_data['per_cycle_tau']['best_taus']
    tf_ref_js    = percycle_data['per_cycle_tau']['js_mean']
    print(f"  per-cycle τ 참조 JS: {tf_ref_js:.4f}")

    # continuous activation
    cont_tf = build_activation_matrix(note_time_df, cyc_tf, continuous=True).values.astype(np.float32)
    ov_tf   = make_overlap_from_taus(cont_tf, tf_best_taus, K_tf)

    # 1-A. Algo1
    print("\n  [1-A] Timeflow Algo1 N=5")
    gen_tf_a1, js_tf_a1 = run_algo1_best(shared, ov_tf, cyc_tf, n_trials=5, seed_base=100)
    wav_tf_a1 = os.path.join(OUTPUT_DIR, 'hibari_timeflow_algo1_best.wav')
    mid_tf_a1 = os.path.join(OUTPUT_DIR, 'hibari_timeflow_algo1_best.mid')
    dur_tf_a1 = gen_to_wav(gen_tf_a1, wav_tf_a1, mid_tf_a1, 'Timeflow Algo1')
    results['timeflow_algo1'] = {
        'js': round(js_tf_a1, 4), 'wav': wav_tf_a1,
        'ref_js_n20': tf_ref_js,
        'config': 'timeflow, α=0.5, ow=0.3, per-cycle τ',
    }

    # 1-B. Algo2 FC
    print("\n  [1-B] Timeflow Algo2 FC")
    gen_tf_a2, js_tf_a2, _ = run_algo2_fc(shared, cont_tf, epochs=80)
    wav_tf_a2 = os.path.join(OUTPUT_DIR, 'hibari_timeflow_algo2_fc.wav')
    mid_tf_a2 = os.path.join(OUTPUT_DIR, 'hibari_timeflow_algo2_fc.mid')
    dur_tf_a2 = gen_to_wav(gen_tf_a2, wav_tf_a2, mid_tf_a2, 'Timeflow Algo2 FC')
    results['timeflow_algo2_fc'] = {
        'js': round(js_tf_a2, 4) if js_tf_a2 else None, 'wav': wav_tf_a2,
        'ref_js': 0.0004,
        'config': 'timeflow, α=0.5, continuous FC',
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. Complex (실험 B) — α=0.25, ow=0.0, dw=0.3, rc=0.1
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═"*60)
    print("  2. 실험 B — complex (JS≈0.0183)")
    print("    설정: α=0.25, ow=0.0, dw=0.3, rc=0.1, rate_t=0.3")
    print("═"*60)

    cfg_b = PipelineConfig()
    cfg_b.metric.metric          = 'tonnetz'
    cfg_b.metric.alpha           = 0.25
    cfg_b.metric.octave_weight   = 0.0
    cfg_b.metric.duration_weight = 0.3

    pb = TDAMusicPipeline(cfg_b)
    pb._cache.update(preproc_cache)

    t0 = time.time()
    pb.run_homology_search(search_type='complex', dimension=1, rate_t=RATE_T, rate_s=0.1)
    pb.run_overlap_construction(persistence_key='h1_complex_lag1')
    ph_time = time.time() - t0

    cyc_b = pb._cache['cycle_labeled']
    K_b   = len(cyc_b)
    print(f"  PH 완료: K={K_b}  ({ph_time:.1f}s)")

    # B_BEST_TAUS 적용
    cont_b = build_activation_matrix(note_time_df, cyc_b, continuous=True).values.astype(np.float32)
    ov_b   = make_overlap_from_taus(cont_b, B_BEST_TAUS, K_b)

    # 2-A. Algo1
    print("\n  [2-A] Complex Algo1 N=5")
    gen_b_a1, js_b_a1 = run_algo1_best(shared, ov_b, cyc_b, n_trials=5, seed_base=200)
    wav_b_a1 = os.path.join(OUTPUT_DIR, 'hibari_complex_algo1_best.wav')
    mid_b_a1 = os.path.join(OUTPUT_DIR, 'hibari_complex_algo1_best.mid')
    dur_b_a1 = gen_to_wav(gen_b_a1, wav_b_a1, mid_b_a1, 'Complex Algo1')
    results['complex_algo1'] = {
        'js': round(js_b_a1, 4), 'wav': wav_b_a1,
        'ref_js_n20': 0.0183,
        'config': 'complex, α=0.25, ow=0.0, dw=0.3, rc=0.1, per-cycle τ (B_BEST_TAUS)',
    }

    # 2-B. Algo2 FC
    print("\n  [2-B] Complex Algo2 FC")
    gen_b_a2, js_b_a2, _ = run_algo2_fc(shared, cont_b, epochs=80)
    wav_b_a2 = os.path.join(OUTPUT_DIR, 'hibari_complex_algo2_fc.wav')
    mid_b_a2 = os.path.join(OUTPUT_DIR, 'hibari_complex_algo2_fc.mid')
    dur_b_a2 = gen_to_wav(gen_b_a2, wav_b_a2, mid_b_a2, 'Complex Algo2 FC')
    results['complex_algo2_fc'] = {
        'js': round(js_b_a2, 4) if js_b_a2 else None, 'wav': wav_b_a2,
        'ref_js': 0.0003,
        'config': 'complex, α=0.25, ow=0.0, dw=0.3, rc=0.1, continuous FC',
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 요약
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═"*60)
    print("  생성 완료 요약")
    print("═"*60)
    for tag, info in results.items():
        js_str  = f"JS={info['js']:.4f}" if info.get('js') else "JS=?"
        ref_str = f"(ref N=20: {info.get('ref_js_n20') or info.get('ref_js', '?')})"
        print(f"  {tag:25s}  {js_str}  {ref_str}")
        print(f"    → {info['wav']}")

    # 결과 JSON 저장
    out_json = os.path.join(OUTPUT_DIR, 'comparison_wav_results.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  결과 메타: {out_json}")
    print("\n[완료]")
    return results


if __name__ == '__main__':
    main()
