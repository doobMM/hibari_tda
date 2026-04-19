"""
run_note_reassign_unified.py — 방향 A: 거리 보존 note 재분배 통합 러너

기존 5개 파일을 통합:
  run_note_reassign.py              → --mode algo1
  run_note_reassign_dl.py           → --mode dl
  run_note_reassign_harmony.py      → --mode harmony
  run_note_reassign_harmony_dl.py   → --mode harmony_dl
  run_note_reassign_wasserstein.py  → --mode wasserstein

사용법:
  python run_note_reassign_unified.py --mode algo1
  python run_note_reassign_unified.py --mode dl
  python run_note_reassign_unified.py --mode harmony
  python run_note_reassign_unified.py --mode consonance_grid
  python run_note_reassign_unified.py --mode harmony_dl
  python run_note_reassign_unified.py --mode wasserstein
"""
import os, sys, time, json, warnings, argparse
import numpy as np
import random
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from run_any_track import preprocess, compute_ph, run_algo1
from note_reassign import find_new_notes, SCALES
from generation import algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml
from sequence_metrics import evaluate_sequence_metrics

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"
SEED_BASE = 42


# ═══════════════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════════════

def run_algo1_with_new_notes(data, ov, cl, new_notes_label, seed):
    """새 notes_label로 Algorithm 1 실행."""
    random.seed(seed); np.random.seed(seed)
    new_counts = {nt: 10 for nt in new_notes_label.keys()}
    pool = NodePool(new_notes_label, new_counts, num_modules=65)
    mgr = CycleSetManager(cl)
    T = len(ov)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
          4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    h = (hp * (T//32+1))[:T]
    return algorithm1_optimized(pool, h, ov, mgr, max_resample=50)


def remap_music_notes(music_notes_list, orig_notes_label, new_notes_label):
    """원곡 음표를 새 note로 치환 (DL 학습용)."""
    orig_sorted = sorted(orig_notes_label.items(), key=lambda x: x[1])
    new_sorted = sorted(new_notes_label.items(), key=lambda x: x[1])
    label_to_new = {}
    for (orig_note, label), (new_note, _) in zip(orig_sorted, new_sorted):
        label_to_new[label] = new_note

    remapped_list = []
    for inst_notes in music_notes_list:
        remapped = []
        for start, pitch, end in inst_notes:
            duration = end - start
            key = (pitch, duration)
            if key in orig_notes_label:
                label = orig_notes_label[key]
                if label in label_to_new:
                    new_pitch, new_dur = label_to_new[label]
                    remapped.append((start, new_pitch, start + new_dur))
        remapped_list.append(remapped)
    return remapped_list


def analyze_harmony(notes_label, cycle_labeled, new_notes_label, new_notes):
    """새 note set의 화성 분석 (음계 적합도)."""
    new_pitches = [n[0] for n in new_notes]
    pcs = set(p % 12 for p in new_pitches)
    best_match, best_name = 0.0, ""
    for sname, spc in SCALES.items():
        for root in range(12):
            scale_pcs = set((pc + root) % 12 for pc in spc)
            match = len(pcs & scale_pcs) / len(pcs) if pcs else 0
            if match > best_match:
                best_match = match
                root_name = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][root]
                best_name = f"{root_name} {sname}"
    return {
        'best_scale_match': best_match, 'best_scale_name': best_name,
        'pitch_classes_used': sorted(list(pcs)), 'n_pitch_classes': len(pcs),
    }


def setup_pipeline():
    """전처리 + PH 계산, 공통 data dict 반환."""
    data = preprocess(MIDI_FILE)
    print(f"[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")
    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        raise RuntimeError("no cycles found")
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")
    return data, cl, ov, n_cyc


def save_result(data, filename):
    out_path = os.path.join("docs", "step3_data", filename)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")


# ═══════════════════════════════════════════════════════════════════════
# Mode: algo1 — 거리 보존 note 재분배 + Algorithm 1
# ═══════════════════════════════════════════════════════════════════════

def mode_algo1(args):
    print("=" * 64)
    print(f"  방향 A: 거리 보존 note 재분배 — {TRACK_NAME}")
    print("=" * 64)

    t0 = time.time()
    data, cl, ov, n_cyc = setup_pipeline()
    original_notes = data['inst1'] + data['inst2']
    n_trials = args.n_trials

    # Baseline
    bl_results = []
    for i in range(n_trials):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        bl_results.append(evaluate_sequence_metrics(gen, original_notes))
    bl_avg = {k: np.mean([r[k] for r in bl_results]) for k in bl_results[0]}
    print(f"\n[Baseline] pitch JS: {bl_avg['pitch_js']:.4f}")

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC, 'n_cycles': n_cyc,
        'N': data['N'],
        'baseline': {k: round(v, 6) for k, v in bl_avg.items()},
        'reassignments': {},
    }

    configs = [
        ('tonnetz_narrow', {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (55, 79), 'n_candidates': 1000}),
        ('tonnetz_wide',   {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (48, 84), 'n_candidates': 1000}),
        ('tonnetz_vwide',  {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                            'pitch_range': (40, 88), 'n_candidates': 1000}),
    ]

    for config_name, kwargs in configs:
        print(f"\n  [{config_name}] 새 note 탐색...")
        result = find_new_notes(data['notes_label'], cl, seed=SEED_BASE,
                                **kwargs)
        print(f"  note err: {result['note_dist_error']:.4f}  "
              f"cycle err: {result['cycle_dist_error']:.4f}")

        reassign_results = []
        for i in range(n_trials):
            gen = run_algo1_with_new_notes(
                data, ov, cl, result['new_notes_label'], seed=SEED_BASE + i)
            if gen:
                reassign_results.append(
                    evaluate_sequence_metrics(gen, original_notes))

        if reassign_results:
            avg = {k: np.mean([r[k] for r in reassign_results])
                   for k in reassign_results[0]}
            all_results['reassignments'][config_name] = {
                'note_dist_error': round(result['note_dist_error'], 4),
                'cycle_dist_error': round(result['cycle_dist_error'], 4),
                'avg_metrics': {k: round(v, 6) for k, v in avg.items()},
            }

    all_results['elapsed_s'] = round(time.time() - t0, 1)
    save_result(all_results, 'note_reassign_results.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: dl — note 재분배 + LSTM/Transformer
# ═══════════════════════════════════════════════════════════════════════

def mode_dl(args):
    import torch
    from generation import (prepare_training_data, MusicGeneratorLSTM,
                            MusicGeneratorTransformer, train_model,
                            generate_from_model)
    from sklearn.model_selection import train_test_split

    print("=" * 64)
    print(f"  방향 A + DL: 거리 보존 note 재분배 + LSTM/Transformer")
    print("=" * 64)

    t0 = time.time()
    data, cl, ov, n_cyc = setup_pipeline()
    T, N, C = data['T'], len(data['notes_label']), n_cyc
    original_notes = data['inst1'] + data['inst2']

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': 50, 'experiments': {},
    }

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N)
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_orig, y_orig, test_size=0.2, random_state=SEED_BASE)

    model_types = ['lstm', 'transformer']

    # Baseline
    for mt in model_types:
        print(f"\n  [baseline_{mt}]")
        if mt == 'lstm':
            model = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
        else:
            model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                              num_layers=2, dropout=0.1, max_len=T)
        history = train_model(model, X_tr, y_tr, X_va, y_va,
                              epochs=50, lr=0.001, batch_size=32,
                              model_type=mt, seq_len=T)
        gen = generate_from_model(model, ov, data['notes_label'],
                                  model_type=mt, adaptive_threshold=True)
        if gen:
            seq_m = evaluate_sequence_metrics(gen, original_notes)
            all_results['experiments'][f'baseline_{mt}'] = {
                'val_loss': round(history[-1]['val_loss'], 4),
                'n_notes': len(gen),
                **{k: round(v, 6) for k, v in seq_m.items()},
            }

    # Reassign configs
    configs = [
        ('tonnetz_wide',  {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                           'pitch_range': (48, 84), 'n_candidates': 1000}),
        ('tonnetz_vwide', {'note_metric': 'tonnetz', 'cycle_metric': 'tonnetz',
                           'pitch_range': (40, 88), 'n_candidates': 1000}),
    ]

    for cfg_name, cfg_kwargs in configs:
        reassign = find_new_notes(data['notes_label'], cl, seed=SEED_BASE,
                                  **cfg_kwargs)
        new_nl = reassign['new_notes_label']
        remapped = remap_music_notes(
            [data['inst1'], data['inst2']], data['notes_label'], new_nl)
        remapped_flat = remapped[0] + remapped[1]
        N_new = len(new_nl)
        X_new, y_new = prepare_training_data(ov, remapped, new_nl, T, N_new)
        X_tr_n, X_va_n, y_tr_n, y_va_n = train_test_split(
            X_new, y_new, test_size=0.2, random_state=SEED_BASE)

        for mt in model_types:
            label = f"{cfg_name}_{mt}"
            print(f"\n  [{label}]")
            if mt == 'lstm':
                model = MusicGeneratorLSTM(C, N_new, hidden_dim=128,
                                           num_layers=2, dropout=0.3)
            else:
                model = MusicGeneratorTransformer(C, N_new, d_model=128,
                                                  nhead=4, num_layers=2,
                                                  dropout=0.1, max_len=T)
            history = train_model(model, X_tr_n, y_tr_n, X_va_n, y_va_n,
                                  epochs=50, lr=0.001, batch_size=32,
                                  model_type=mt, seq_len=T)
            gen = generate_from_model(model, ov, new_nl,
                                      model_type=mt, adaptive_threshold=True)
            if not gen:
                all_results['experiments'][label] = {'error': 'no notes'}
                continue

            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            notes_to_xml([gen], tempo_bpm=66,
                         file_name=f"reassign_{label}_{ts}",
                         output_dir="./output")

            seq_m = evaluate_sequence_metrics(gen, original_notes)
            seq_m2 = evaluate_sequence_metrics(gen, remapped_flat)
            all_results['experiments'][label] = {
                'val_loss': round(history[-1]['val_loss'], 4),
                'n_notes': len(gen),
                'vs_original': {k: round(v, 6) for k, v in seq_m.items()},
                'vs_remapped': {k: round(v, 6) for k, v in seq_m2.items()},
            }

    all_results['elapsed_s'] = round(time.time() - t0, 1)
    save_result(all_results, 'note_reassign_dl_results.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: harmony — 화성 제약 비교
# ═══════════════════════════════════════════════════════════════════════

def mode_harmony(args):
    print("=" * 70)
    print("  방향 A: 화성 제약 비교 실험")
    print("=" * 70)

    t0 = time.time()
    data, cl, ov, n_cyc = setup_pipeline()

    experiments = [
        ('baseline',    None,        {}),
        ('scale_major', 'scale',     {'scale_type': 'major'}),
        ('scale_minor', 'scale',     {'scale_type': 'minor'}),
        ('scale_penta', 'scale',     {'scale_type': 'pentatonic'}),
        ('consonance',  'consonance',{'alpha_consonance': 0.3}),
        ('interval',    'interval',  {'alpha_interval': 0.3}),
        ('all_major',   'all',       {'scale_type': 'major',
                                      'alpha_consonance': 0.3,
                                      'alpha_interval': 0.3}),
        ('all_penta',   'all',       {'scale_type': 'pentatonic',
                                      'alpha_consonance': 0.3,
                                      'alpha_interval': 0.3}),
    ]

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC, 'n_cycles': n_cyc,
        'pitch_range': [40, 88], 'n_candidates': 1000, 'experiments': {},
    }

    for exp_name, harmony_mode, extra in experiments:
        print(f"\n  [{exp_name}] harmony_mode={harmony_mode}")
        try:
            result = find_new_notes(
                data['notes_label'], cl, seed=SEED_BASE,
                note_metric='tonnetz', cycle_metric='tonnetz',
                pitch_range=(48, 84), n_candidates=1000,
                harmony_mode=harmony_mode, **extra)
        except RuntimeError as e:
            all_results['experiments'][exp_name] = {'error': str(e)}
            continue

        harmony = analyze_harmony(data['notes_label'], cl,
                                  result['new_notes_label'], result['new_notes'])

        # Algo1 생성
        new_counts = {nt: 10 for nt in result['new_notes_label'].keys()}
        pool = NodePool(result['new_notes_label'], new_counts, num_modules=65)
        mgr = CycleSetManager(cl)
        T = len(ov)
        hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,
              4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
        h = (hp * (T//32+1))[:T]
        random.seed(SEED_BASE); np.random.seed(SEED_BASE)
        gen = algorithm1_optimized(pool, h, ov, mgr, max_resample=50)

        if gen:
            notes_to_xml([gen], tempo_bpm=66,
                         file_name=f"harmony_{exp_name}", output_dir="./output")

        all_results['experiments'][exp_name] = {
            'harmony_mode': harmony_mode,
            'note_dist_error': round(result['note_dist_error'], 4),
            'cycle_dist_error': round(result['cycle_dist_error'], 4),
            'consonance_score': round(result['consonance_score'], 4),
            'interval_error': round(result['interval_error'], 4),
            'n_generated': len(gen) if gen else 0,
            'new_pitches': [n[0] for n in result['new_notes']],
            **{f'harmony_{k}': v for k, v in harmony.items()},
        }

    all_results['elapsed_s'] = round(time.time() - t0, 1)
    save_result(all_results, 'note_reassign_harmony_results.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: consonance_grid — §5.5 consonance 단독 소규모 grid search
# ═══════════════════════════════════════════════════════════════════════

def mode_consonance_grid(args):
    print("=" * 74)
    print("  §5.5 consonance 단독 목적함수 grid search (3x3, Algo1 포함)")
    print("=" * 74)

    t0 = time.time()
    data, cl, ov, n_cyc = setup_pipeline()
    original_notes = data['inst1'] + data['inst2']
    n_trials = args.n_trials

    alpha_note_grid = [0.3, 0.5, 1.0]
    beta_diss_grid = [0.1, 0.3, 1.0]  # code: alpha_consonance
    pitch_range = (48, 84)
    rows = []

    for alpha_note in alpha_note_grid:
        for beta_diss in beta_diss_grid:
            print(f"\n  [alpha_note={alpha_note:.1f}, beta_diss={beta_diss:.1f}]")

            result = find_new_notes(
                data['notes_label'], cl, seed=SEED_BASE,
                note_metric='tonnetz',
                pitch_range=pitch_range, n_candidates=1000,
                harmony_mode='consonance',
                alpha_note=alpha_note,
                alpha_consonance=beta_diss,
            )

            harmony = analyze_harmony(
                data['notes_label'], cl,
                result['new_notes_label'], result['new_notes']
            )

            trial_metrics = []
            for i in range(n_trials):
                gen = run_algo1_with_new_notes(
                    data, ov, cl, result['new_notes_label'],
                    seed=SEED_BASE + i
                )
                if gen:
                    trial_metrics.append(
                        evaluate_sequence_metrics(gen, original_notes)
                    )

            if trial_metrics:
                js_vals = [m['pitch_js'] for m in trial_metrics]
                mean_js = float(np.mean(js_vals))
                std_js = float(np.std(js_vals))
            else:
                mean_js = None
                std_js = None

            row = {
                'alpha_note': alpha_note,
                'beta_diss': beta_diss,
                'pitch_range': [pitch_range[0], pitch_range[1]],
                'mean_js': round(mean_js, 6) if mean_js is not None else None,
                'std_js': round(std_js, 6) if std_js is not None else None,
                'mean_dist_err': round(float(result['note_dist_error']), 6),
                'mean_consonance': round(float(result['consonance_score']), 6),
                'mean_scale_match': round(float(harmony['best_scale_match']), 6),
            }
            rows.append(row)

            js_txt = f"{row['mean_js']:.4f}" if row['mean_js'] is not None else "NA"
            print(
                f"    JS={js_txt}±{row['std_js'] if row['std_js'] is not None else 'NA'}  "
                f"dist_err={row['mean_dist_err']:.4f}  "
                f"consonance={row['mean_consonance']:.4f}  "
                f"scale_match={row['mean_scale_match']:.3f}"
            )

    rows.sort(key=lambda r: (r['alpha_note'], r['beta_diss']))
    save_result(rows, 'consonance_grid_search_results.json')
    print(f"\n총 소요 시간: {time.time() - t0:.1f}s")


# ═══════════════════════════════════════════════════════════════════════
# Mode: harmony_dl — 화성 제약 + Transformer
# ═══════════════════════════════════════════════════════════════════════

def mode_harmony_dl(args):
    import torch
    from generation import (prepare_training_data, MusicGeneratorTransformer,
                            train_model, generate_from_model)
    from sklearn.model_selection import train_test_split

    print("=" * 70)
    print("  화성 제약 + Algorithm 2 (Transformer) 비교")
    print("=" * 70)

    t0 = time.time()
    data, cl, ov, n_cyc = setup_pipeline()
    T, N, C = data['T'], len(data['notes_label']), n_cyc
    original_notes = data['inst1'] + data['inst2']

    all_results = {
        'track': TRACK_NAME, 'metric': METRIC,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': 50, 'experiments': {},
    }

    # Original baseline
    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N)
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_orig, y_orig, test_size=0.2, random_state=SEED_BASE)

    model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                      num_layers=2, dropout=0.1, max_len=T)
    history = train_model(model, X_tr, y_tr, X_va, y_va,
                          epochs=50, lr=0.001, batch_size=32,
                          model_type='transformer', seq_len=T)
    gen = generate_from_model(model, ov, data['notes_label'],
                              model_type='transformer', adaptive_threshold=True)
    if gen:
        seq_m = evaluate_sequence_metrics(gen, original_notes)
        all_results['experiments']['original_transformer'] = {
            'val_loss': round(history[-1]['val_loss'], 4), 'n_notes': len(gen),
            **{k: round(v, 6) for k, v in seq_m.items()},
        }

    # Harmony configs
    harmony_configs = [
        ('baseline',    {'harmony_mode': None}),
        ('scale_major', {'harmony_mode': 'scale', 'scale_type': 'major'}),
        ('scale_penta', {'harmony_mode': 'scale', 'scale_type': 'pentatonic'}),
        ('all_penta',   {'harmony_mode': 'all', 'scale_type': 'pentatonic',
                         'alpha_consonance': 0.3, 'alpha_interval': 0.3}),
    ]

    for cfg_name, extra in harmony_configs:
        print(f"\n  [{cfg_name}]")
        reassign = find_new_notes(
            data['notes_label'], cl, seed=SEED_BASE,
            note_metric='tonnetz', cycle_metric='tonnetz',
            pitch_range=(40, 88), n_candidates=1000, **extra)
        new_nl = reassign['new_notes_label']

        remapped = remap_music_notes(
            [data['inst1'], data['inst2']], data['notes_label'], new_nl)
        remapped_flat = remapped[0] + remapped[1]
        N_new = len(new_nl)
        X_new, y_new = prepare_training_data(ov, remapped, new_nl, T, N_new)
        X_tr_n, X_va_n, y_tr_n, y_va_n = train_test_split(
            X_new, y_new, test_size=0.2, random_state=SEED_BASE)

        label = f"{cfg_name}_transformer"
        model = MusicGeneratorTransformer(C, N_new, d_model=128, nhead=4,
                                          num_layers=2, dropout=0.1, max_len=T)
        history = train_model(model, X_tr_n, y_tr_n, X_va_n, y_va_n,
                              epochs=50, lr=0.001, batch_size=32,
                              model_type='transformer', seq_len=T)
        gen = generate_from_model(model, ov, new_nl,
                                  model_type='transformer',
                                  adaptive_threshold=True)
        if not gen:
            all_results['experiments'][label] = {'error': 'no notes'}
            continue

        seq_orig = evaluate_sequence_metrics(gen, original_notes)
        seq_remap = evaluate_sequence_metrics(gen, remapped_flat)
        harmony = analyze_harmony(data['notes_label'], cl,
                                  new_nl, reassign['new_notes'])

        all_results['experiments'][label] = {
            'val_loss': round(history[-1]['val_loss'], 4),
            'n_notes': len(gen),
            'vs_original': {k: round(v, 6) for k, v in seq_orig.items()},
            'vs_remapped': {k: round(v, 6) for k, v in seq_remap.items()},
            'n_pitch_classes': harmony['n_pitch_classes'],
            'best_scale_match': harmony['best_scale_name'],
        }

    all_results['elapsed_s'] = round(time.time() - t0, 1)
    save_result(all_results, 'note_reassign_harmony_dl_results.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: wasserstein — Wasserstein distance 제약
# ═══════════════════════════════════════════════════════════════════════

def mode_wasserstein(args):
    print("=" * 64)
    print("  Wasserstein Distance 제약 Note 재분배 실험")
    print("=" * 64)

    data, cl, ov, n_cyc = setup_pipeline()
    original_notes = data['inst1'] + data['inst2']
    n_trials = args.n_trials

    # Baseline
    bl_results = []
    for i in range(n_trials):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        bl_results.append(evaluate_sequence_metrics(gen, original_notes))
    bl_avg = {k: np.mean([r[k] for r in bl_results]) for k in bl_results[0]}

    results = {
        'track': TRACK_NAME, 'metric': METRIC, 'n_cycles': n_cyc,
        'N': data['N'],
        'baseline': {k: round(v, 6) for k, v in bl_avg.items()},
        'experiments': {},
    }

    configs = [
        ('no_wasserstein',      {'alpha_wasserstein': 0.0, 'n_candidates': 1000}),
        ('wasserstein_0.3',     {'alpha_wasserstein': 0.3, 'n_candidates': 1000,
                                 'n_wasserstein_topk': 30}),
        ('wasserstein_0.5',     {'alpha_wasserstein': 0.5, 'n_candidates': 1000,
                                 'n_wasserstein_topk': 30}),
        ('wasserstein_1.0',     {'alpha_wasserstein': 1.0, 'n_candidates': 1000,
                                 'n_wasserstein_topk': 30}),
        ('scale_major_wass_0.5', {'alpha_wasserstein': 0.5, 'n_candidates': 1000,
                                  'n_wasserstein_topk': 30,
                                  'harmony_mode': 'scale', 'scale_type': 'major'}),
    ]

    for cfg_name, kwargs in configs:
        print(f"\n  [{cfg_name}]")
        t1 = time.time()
        result = find_new_notes(
            notes_label=data['notes_label'], cycle_labeled=cl,
            note_metric='tonnetz', cycle_metric='tonnetz',
            pitch_range=(40, 88), seed=SEED_BASE,
            alpha_note=0.5, alpha_cycle=0.5, **kwargs)
        elapsed = time.time() - t1

        trial_results = []
        for i in range(n_trials):
            gen = run_algo1_with_new_notes(
                data, ov, cl, result['new_notes_label'], SEED_BASE + i)
            trial_results.append(evaluate_sequence_metrics(gen, original_notes))
        avg = {k: round(np.mean([r[k] for r in trial_results]), 6)
               for k in trial_results[0]}

        results['experiments'][cfg_name] = {
            'note_dist_error': round(result['note_dist_error'], 4),
            'cycle_dist_error': round(result['cycle_dist_error'], 4),
            'wasserstein_dist': round(result.get('wasserstein_dist', 0.0), 4),
            'total_cost': round(result['total_cost'], 4),
            'new_pitches': [p for p, d in result['new_notes']],
            'avg_metrics': avg,
            'elapsed_s': round(elapsed, 1),
        }
        print(f"  pJS={avg.get('pitch_js', '?')}  ({elapsed:.1f}s)")

    save_result(results, 'note_reassign_wasserstein_results.json')


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="방향 A: note 재분배 통합 러너")
    parser.add_argument('--mode', required=True,
                        choices=['algo1', 'dl', 'harmony',
                                 'consonance_grid', 'harmony_dl', 'wasserstein'])
    parser.add_argument('--n-trials', dest='n_trials', type=int, default=5)
    args = parser.parse_args()

    dispatch = {
        'algo1': mode_algo1,
        'dl': mode_dl,
        'harmony': mode_harmony,
        'consonance_grid': mode_consonance_grid,
        'harmony_dl': mode_harmony_dl,
        'wasserstein': mode_wasserstein,
    }
    dispatch[args.mode](args)


if __name__ == '__main__':
    main()
