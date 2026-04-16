"""
run_temporal_reorder_unified.py — 방향 B: 중첩행렬 시간 재배치 통합 실험

기존 3개 파일을 통합:
  run_temporal_reorder.py       → --mode algo1
  run_temporal_reorder_dl.py    → --mode dl
  run_temporal_reorder_dl_v2.py → --mode dl_v2

사용법:
  python run_temporal_reorder_unified.py --mode algo1
  python run_temporal_reorder_unified.py --mode dl
  python run_temporal_reorder_unified.py --mode dl_v2
"""
import os, sys, time, json, random, warnings, argparse, pickle
import numpy as np
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from temporal_reorder import reorder_overlap_matrix
from sequence_metrics import evaluate_sequence_metrics


# ═══════════════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════════════

def setup_pipeline(midi_file, metric, from_cache=False):
    """전처리 + PH → 공통 데이터 반환.
    from_cache=True 이면 cache/metric_{metric}.pkl 에서 overlap/cycle_labeled 로드.
    """
    data = preprocess(midi_file)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    if from_cache:
        cache_path = os.path.join("cache", f"metric_{metric}.pkl")
        t0 = time.time()
        with open(cache_path, 'rb') as f:
            cached = pickle.load(f)
        cl = cached['cycle_labeled']
        ov_df = cached['overlap']
        ov = ov_df.values if hasattr(ov_df, 'values') else ov_df
        ph_time = time.time() - t0
        n_cyc = len(cl)
        print(f"[캐시 로드] {metric}: {n_cyc} cycles  (alpha={cached.get('alpha','?')})")
        return data, cl, ov, n_cyc, ph_time

    cl, ov, n_cyc, ph_time = compute_ph(data, metric)
    if cl is None:
        print("ERROR: no cycles found")
        return None, None, None, None, None
    print(f"[PH] {metric}: {n_cyc} cycles ({ph_time:.1f}s)")
    return data, cl, ov, n_cyc, ph_time


def compute_delta(avg, baseline_avg):
    """baseline 대비 변화율(%) 계산."""
    delta = {}
    for k in avg:
        if baseline_avg.get(k, 0) > 0:
            delta[k] = round(100 * (avg[k] - baseline_avg[k]) / baseline_avg[k], 1)
        else:
            delta[k] = 0.0
    return delta


def judge_verdict(delta):
    """pitch JS 유지 + DTW 변화 기준 판정."""
    pitch_ok = delta.get('pitch_js', 0) < 20
    dtw_diff = delta.get('dtw', 0) > 10
    if pitch_ok and dtw_diff:
        return "★ 유망"
    elif pitch_ok:
        return "△ 보통"
    return "✗ 분포 붕괴"


def make_label(strategy_name, kwargs):
    """전략 이름 + 파라미터 → 라벨 문자열."""
    label = strategy_name
    if kwargs:
        label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())
    return label


# ═══════════════════════════════════════════════════════════════════════
# Mode: algo1 — Algorithm 1 × 재배치 전략 비교
# ═══════════════════════════════════════════════════════════════════════

STRATEGIES_ALGO1 = [
    ('segment_shuffle', {}),
    ('block_permute',   {'block_size': 32}),
    ('block_permute',   {'block_size': 64}),
    ('markov_resample', {'temperature': 1.0}),
    ('markov_resample', {'temperature': 1.5}),
]


def mode_algo1(args):
    """Algorithm 1 기반 시간 재배치 실험."""
    from run_any_track import run_algo1
    from eval_metrics import evaluate_generation

    print("=" * 64)
    print(f"  방향 B: 중첩행렬 시간 재배치 실험 — {args.track}")
    print("=" * 64)

    t0 = time.time()
    data, cl, ov, n_cyc, _ = setup_pipeline(args.midi, args.metric, args.from_cache)
    if data is None:
        return

    original_notes = data['inst1'] + data['inst2']
    n_trials = args.n_trials

    # ── Baseline ──
    print(f"\n{'─'*64}")
    print(f"  [Baseline] 원본 중첩행렬 → Algo1 × {n_trials}")
    print(f"{'─'*64}")

    baseline_results = []
    for i in range(n_trials):
        gen = run_algo1(data, ov, cl, seed=args.seed + i)
        seq_m = evaluate_sequence_metrics(gen, original_notes)
        baseline_results.append({
            'pitch_js': seq_m['pitch_js'],
            'transition_js': seq_m['transition_js'],
            'dtw': seq_m['dtw'],
            'ncd': seq_m['ncd'],
        })

    baseline_avg = {k: np.mean([r[k] for r in baseline_results])
                    for k in baseline_results[0]}
    baseline_std = {k: np.std([r[k] for r in baseline_results], ddof=1)
                    for k in baseline_results[0]}

    print(f"  pitch JS:      {baseline_avg['pitch_js']:.4f} ± {baseline_std['pitch_js']:.4f}")
    print(f"  transition JS: {baseline_avg['transition_js']:.4f} ± {baseline_std['transition_js']:.4f}")
    print(f"  DTW:           {baseline_avg['dtw']:.4f} ± {baseline_std['dtw']:.4f}")
    print(f"  NCD:           {baseline_avg['ncd']:.4f} ± {baseline_std['ncd']:.4f}")

    # ── 각 전략 실험 ──
    all_results = {
        'track': args.track, 'metric': args.metric,
        'n_cycles': n_cyc, 'n_trials': n_trials,
        'baseline': {
            'avg': {k: round(v, 6) for k, v in baseline_avg.items()},
            'std': {k: round(v, 6) for k, v in baseline_std.items()},
        },
        'strategies': {},
    }

    for strategy_name, kwargs in STRATEGIES_ALGO1:
        label = make_label(strategy_name, kwargs)
        print(f"\n{'─'*64}")
        print(f"  [{label}] 재배치 → Algo1 × {n_trials}")
        print(f"{'─'*64}")

        strategy_results = []
        reorder_info = None
        for i in range(n_trials):
            reordered, info = reorder_overlap_matrix(
                ov, strategy=strategy_name, seed=args.seed + i * 100, **kwargs)
            if reorder_info is None:
                reorder_info = info

            gen = run_algo1(data, reordered, cl, seed=args.seed + i)
            seq_m = evaluate_sequence_metrics(gen, original_notes)
            strategy_results.append({
                'pitch_js': seq_m['pitch_js'],
                'transition_js': seq_m['transition_js'],
                'dtw': seq_m['dtw'],
                'ncd': seq_m['ncd'],
            })

        avg = {k: np.mean([r[k] for r in strategy_results])
               for k in strategy_results[0]}
        std = {k: np.std([r[k] for r in strategy_results], ddof=1)
               for k in strategy_results[0]}
        delta = compute_delta(avg, baseline_avg)
        verdict = judge_verdict(delta)

        print(f"  pitch JS:      {avg['pitch_js']:.4f} ± {std['pitch_js']:.4f}  (Δ {delta['pitch_js']:+.1f}%)")
        print(f"  transition JS: {avg['transition_js']:.4f} ± {std['transition_js']:.4f}  (Δ {delta['transition_js']:+.1f}%)")
        print(f"  DTW:           {avg['dtw']:.4f} ± {std['dtw']:.4f}  (Δ {delta['dtw']:+.1f}%)")
        print(f"  NCD:           {avg['ncd']:.4f} ± {std['ncd']:.4f}  (Δ {delta['ncd']:+.1f}%)")
        print(f"  판정: {verdict}")

        all_results['strategies'][label] = {
            'avg': {k: round(v, 6) for k, v in avg.items()},
            'std': {k: round(v, 6) for k, v in std.items()},
            'delta_pct': delta,
            'verdict': verdict,
            'reorder_info': {k: v for k, v in reorder_info.items()
                            if k not in ('shuffle_order', 'orig_state_dist', 'new_state_dist')},
        }

    # ── 결과 저장 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "temporal_reorder_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 요약 테이블 ──
    print(f"\n{'='*64}")
    print(f"  요약 (baseline 대비 변화율 %)")
    print(f"{'='*64}")
    print(f"  {'전략':<30} {'pitch JS':>10} {'DTW':>10} {'trans JS':>10} {'NCD':>10} {'판정':>8}")
    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
    print(f"  {'baseline':<30} {'0.0':>10} {'0.0':>10} {'0.0':>10} {'0.0':>10} {'(기준)':>8}")
    for label, r in all_results['strategies'].items():
        d = r['delta_pct']
        print(f"  {label:<30} {d['pitch_js']:>+9.1f}% {d['dtw']:>+9.1f}% "
              f"{d['transition_js']:>+9.1f}% {d['ncd']:>+9.1f}% {r['verdict']:>8}")
    print(f"\n총 소요: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════════════
# Mode: dl — LSTM/Transformer × 재배치 (원본 학습 → 재배치 생성)
# ═══════════════════════════════════════════════════════════════════════

STRATEGIES_DL = [
    ('baseline',         {}),
    ('segment_shuffle',  {}),
    ('block_permute',    {'block_size': 32}),
    ('block_permute',    {'block_size': 64}),
    ('markov_resample',  {'temperature': 1.0}),
    ('markov_resample',  {'temperature': 1.5}),
]


def mode_dl(args):
    """LSTM/Transformer 기반 시간 재배치 실험 (원본 학습 → 재배치 생성)."""
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorLSTM, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from sklearn.model_selection import train_test_split

    print("=" * 64)
    print(f"  방향 B + DL: 시간 재배치 × LSTM/Transformer — {args.track}")
    print("=" * 64)

    t0 = time.time()
    data, cl, ov, n_cyc, _ = setup_pipeline(args.midi, args.metric, args.from_cache)
    if data is None:
        return

    T = data['T']; N = len(data['notes_label']); C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N)
    print(f"[학습 데이터] X: {X_orig.shape}, y: {y_orig.shape}")

    all_results = {
        'track': args.track, 'metric': args.metric,
        'n_cycles': n_cyc, 'T': T, 'N': N,
        'epochs': args.epochs, 'models': {},
    }

    model_types = ['lstm', 'transformer']
    for model_type in model_types:
        print(f"\n{'='*64}")
        print(f"  모델: {model_type.upper()}")
        print(f"{'='*64}")

        # 원본 overlap으로 학습
        print(f"\n  [학습] 원본 overlap으로 {model_type} 학습 ({args.epochs} epochs)...")
        X_train, X_valid, y_train, y_valid = train_test_split(
            X_orig, y_orig, test_size=0.2, random_state=args.seed)

        if model_type == 'lstm':
            model = MusicGeneratorLSTM(C, N, hidden_dim=128, num_layers=2, dropout=0.3)
        else:
            model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                              num_layers=2, dropout=0.1, max_len=T)
        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=args.epochs, lr=0.001, batch_size=32,
            model_type=model_type, seq_len=T)
        val_loss = history[-1]['val_loss']
        print(f"  최종 val_loss: {val_loss:.4f}")

        model_results = {'val_loss': round(val_loss, 4), 'strategies': {}}

        for strategy_name, kwargs in STRATEGIES_DL:
            if strategy_name == 'baseline':
                label = 'baseline'
                gen_overlap = ov
            else:
                label = make_label(strategy_name, kwargs)
                reordered, _ = reorder_overlap_matrix(
                    ov, strategy=strategy_name, seed=args.seed, **kwargs)
                gen_overlap = reordered

            print(f"\n  {'─'*56}")
            print(f"  [{label}] → {model_type} 생성")
            print(f"  {'─'*56}")

            gen = generate_from_model(
                model, gen_overlap, data['notes_label'],
                model_type=model_type, adaptive_threshold=True, min_onset_gap=0)

            if not gen:
                print(f"    ⚠ 생성된 음표 없음")
                model_results['strategies'][label] = {'error': 'no notes generated'}
                continue

            seq_m = evaluate_sequence_metrics(gen, original_notes,
                                              name=f"{model_type}_{label}")
            model_results['strategies'][label] = {
                'n_notes': len(gen),
                'pitch_js': round(seq_m['pitch_js'], 6),
                'transition_js': round(seq_m['transition_js'], 6),
                'dtw': round(seq_m['dtw'], 6),
                'ncd': round(seq_m['ncd'], 6),
            }

        # baseline 대비 변화율
        bl = model_results['strategies'].get('baseline', {})
        if bl and 'error' not in bl:
            for label, r in model_results['strategies'].items():
                if label == 'baseline' or 'error' in r:
                    continue
                bl_avg = {k: bl[k] for k in ['pitch_js', 'transition_js', 'dtw', 'ncd']}
                r_avg = {k: r[k] for k in ['pitch_js', 'transition_js', 'dtw', 'ncd']}
                r['delta_pct'] = compute_delta(r_avg, bl_avg)
                r['verdict'] = judge_verdict(r['delta_pct'])

        all_results['models'][model_type] = model_results

    # ── 결과 저장 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = args.out if args.out else os.path.join("docs", "step3_data", "temporal_reorder_dl_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # 요약 테이블
    for model_type in model_types:
        mr = all_results['models'][model_type]
        print(f"\n{'='*64}")
        print(f"  {model_type.upper()} 요약 (val_loss: {mr['val_loss']:.4f})")
        print(f"{'='*64}")
        print(f"  {'전략':<35} {'notes':>6} {'pitch JS':>10} {'DTW':>10} {'trans JS':>10} {'NCD':>10} {'판정':>8}")
        print(f"  {'─'*35} {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
        for label, r in mr['strategies'].items():
            if 'error' in r:
                print(f"  {label:<35} {'ERROR':>6}")
                continue
            print(f"  {label:<35} {r['n_notes']:>6} {r['pitch_js']:>10.4f} {r['dtw']:>10.4f} "
                  f"{r['transition_js']:>10.4f} {r['ncd']:>10.4f} {r.get('verdict', '(기준)'):>8}")
    print(f"\n총 소요: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════════════
# Mode: dl_v2 — PE 제거 / 재배치 학습 / 조합 실험
# ═══════════════════════════════════════════════════════════════════════

STRATEGIES_V2 = [
    ('segment_shuffle',  {}),
    ('block_permute',    {'block_size': 32}),
    ('markov_resample',  {'temperature': 1.0}),
]


def _train_and_generate(model, model_type, X_train, y_train, X_valid, y_valid,
                        gen_overlap, notes_label, original_notes, T, label,
                        epochs, lr, batch_size):
    """모델 학습 → 생성 → 평가 헬퍼."""
    from generation import train_model, generate_from_model

    history = train_model(
        model, X_train, y_train, X_valid, y_valid,
        epochs=epochs, lr=lr, batch_size=batch_size,
        model_type=model_type, seq_len=T)
    val_loss = history[-1]['val_loss']

    gen = generate_from_model(
        model, gen_overlap, notes_label,
        model_type=model_type, adaptive_threshold=True)
    if not gen:
        return {'error': 'no notes', 'val_loss': round(val_loss, 4)}

    seq_m = evaluate_sequence_metrics(gen, original_notes, name=label)
    return {
        'val_loss': round(val_loss, 4),
        'n_notes': len(gen),
        'pitch_js': round(seq_m['pitch_js'], 6),
        'transition_js': round(seq_m['transition_js'], 6),
        'dtw': round(seq_m['dtw'], 6),
        'ncd': round(seq_m['ncd'], 6),
    }


def mode_dl_v2(args):
    """PE 제거 + 재배치 학습 확장 실험."""
    import torch
    from generation import (
        prepare_training_data, MusicGeneratorTransformer,
        train_model, generate_from_model
    )
    from sklearn.model_selection import train_test_split

    print("=" * 64)
    print(f"  방향 B 확장: PE 제거 + 재배치 학습 — {args.track}")
    print("=" * 64)

    t0 = time.time()
    data, cl, ov, n_cyc, _ = setup_pipeline(args.midi, args.metric, args.from_cache)
    if data is None:
        return

    T = data['T']; N = len(data['notes_label']); C = n_cyc
    original_notes = data['inst1'] + data['inst2']

    X_orig, y_orig = prepare_training_data(
        ov, [data['inst1'], data['inst2']], data['notes_label'], T, N)

    all_results = {
        'track': args.track, 'metric': args.metric,
        'n_cycles': n_cyc, 'T': T, 'N': N, 'epochs': args.epochs,
        'experiments': {},
    }

    X_tr, X_va, y_tr, y_va = train_test_split(
        X_orig, y_orig, test_size=0.2, random_state=args.seed)

    # ── 실험 0: Baseline (PE 있음, 원본 학습, 원본 생성) ──
    print(f"\n{'='*64}")
    print(f"  [실험 0] Baseline: PE 있음 + 원본 학습 + 원본 생성")
    print(f"{'='*64}")

    model_bl = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                         num_layers=2, dropout=0.1, max_len=T,
                                         use_pos_emb=True)
    bl_result = _train_and_generate(
        model_bl, 'transformer', X_tr, y_tr, X_va, y_va,
        ov, data['notes_label'], original_notes, T, "baseline",
        args.epochs, 0.001, 32)
    all_results['experiments']['baseline'] = bl_result
    print(f"  val_loss={bl_result['val_loss']}, pitch_js={bl_result.get('pitch_js','?')}, dtw={bl_result.get('dtw','?')}")

    # ── 실험 1: PE 제거 + 원본 학습 + 재배치 생성 ──
    print(f"\n{'='*64}")
    print(f"  [실험 1] PE 제거: 원본 학습 → 재배치 생성")
    print(f"{'='*64}")

    model_nope = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                           num_layers=2, dropout=0.1, max_len=T,
                                           use_pos_emb=False)
    print("  학습 (PE 제거)...")
    history_nope = train_model(
        model_nope, X_tr, y_tr, X_va, y_va,
        epochs=args.epochs, lr=0.001, batch_size=32,
        model_type='transformer', seq_len=T)
    nope_val = history_nope[-1]['val_loss']
    print(f"  val_loss: {nope_val:.4f}")

    # PE 제거 baseline (원본 overlap 생성)
    gen_bl = generate_from_model(
        model_nope, ov, data['notes_label'],
        model_type='transformer', adaptive_threshold=True)
    if gen_bl:
        seq_bl = evaluate_sequence_metrics(gen_bl, original_notes, name="noPE_baseline")
        all_results['experiments']['noPE_baseline'] = {
            'val_loss': round(nope_val, 4), 'n_notes': len(gen_bl),
            'pitch_js': round(seq_bl['pitch_js'], 6),
            'transition_js': round(seq_bl['transition_js'], 6),
            'dtw': round(seq_bl['dtw'], 6),
            'ncd': round(seq_bl['ncd'], 6),
        }

    # PE 제거 + 재배치 생성
    for strategy_name, kwargs in STRATEGIES_V2:
        label = f"noPE_{make_label(strategy_name, kwargs)}"
        reordered, _ = reorder_overlap_matrix(
            ov, strategy=strategy_name, seed=args.seed, **kwargs)
        gen = generate_from_model(
            model_nope, reordered, data['notes_label'],
            model_type='transformer', adaptive_threshold=True)
        if not gen:
            all_results['experiments'][label] = {'error': 'no notes'}
            continue
        seq_m = evaluate_sequence_metrics(gen, original_notes, name=label)
        all_results['experiments'][label] = {
            'n_notes': len(gen),
            'pitch_js': round(seq_m['pitch_js'], 6),
            'transition_js': round(seq_m['transition_js'], 6),
            'dtw': round(seq_m['dtw'], 6),
            'ncd': round(seq_m['ncd'], 6),
        }

    # ── 실험 2: PE 있음 + 재배치 학습 + 재배치 생성 ──
    print(f"\n{'='*64}")
    print(f"  [실험 2] 재배치 학습: 재배치 overlap으로 학습+생성")
    print(f"{'='*64}")

    for strategy_name, kwargs in STRATEGIES_V2:
        label = f"retrain_{make_label(strategy_name, kwargs)}"
        print(f"\n  [{label}]")
        reordered, _ = reorder_overlap_matrix(
            ov, strategy=strategy_name, seed=args.seed, **kwargs)

        X_reord = reordered.astype(np.float32)
        X_r_tr, X_r_va, y_r_tr, y_r_va = train_test_split(
            X_reord, y_orig, test_size=0.2, random_state=args.seed)

        model_rt = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                             num_layers=2, dropout=0.1, max_len=T,
                                             use_pos_emb=True)
        result = _train_and_generate(
            model_rt, 'transformer', X_r_tr, y_r_tr, X_r_va, y_r_va,
            reordered, data['notes_label'], original_notes, T, label,
            args.epochs, 0.001, 32)
        all_results['experiments'][label] = result
        print(f"  val_loss={result['val_loss']}, pitch_js={result.get('pitch_js','?')}, dtw={result.get('dtw','?')}")

    # ── 실험 3: PE 제거 + 재배치 학습 + 재배치 생성 ──
    print(f"\n{'='*64}")
    print(f"  [실험 3] PE 제거 + 재배치 학습 (조합)")
    print(f"{'='*64}")

    for strategy_name, kwargs in STRATEGIES_V2:
        label = f"noPE_retrain_{make_label(strategy_name, kwargs)}"
        print(f"\n  [{label}]")
        reordered, _ = reorder_overlap_matrix(
            ov, strategy=strategy_name, seed=args.seed, **kwargs)

        X_reord = reordered.astype(np.float32)
        X_r_tr, X_r_va, y_r_tr, y_r_va = train_test_split(
            X_reord, y_orig, test_size=0.2, random_state=args.seed)

        model_combo = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                                num_layers=2, dropout=0.1, max_len=T,
                                                use_pos_emb=False)
        result = _train_and_generate(
            model_combo, 'transformer', X_r_tr, y_r_tr, X_r_va, y_r_va,
            reordered, data['notes_label'], original_notes, T, label,
            args.epochs, 0.001, 32)
        all_results['experiments'][label] = result
        print(f"  val_loss={result['val_loss']}, pitch_js={result.get('pitch_js','?')}, dtw={result.get('dtw','?')}")

    # ── 결과 저장 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = args.out if args.out else os.path.join("docs", "step3_data", "temporal_reorder_dl_v2_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # 요약 테이블
    bl = all_results['experiments'].get('baseline', {})
    bl_dtw = bl.get('dtw', 0)
    print(f"\n{'='*64}")
    print(f"  전체 요약 — Transformer (baseline: pitch_js={bl.get('pitch_js','?')}, dtw={bl.get('dtw','?')})")
    print(f"{'='*64}")
    print(f"  {'실험':<45} {'vloss':>6} {'pJS':>8} {'DTW':>8} {'tJS':>8} {'NCD':>8} {'ΔDTW%':>8}")
    print(f"  {'─'*45} {'─'*6} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for name, r in all_results['experiments'].items():
        if 'error' in r:
            print(f"  {name:<45} ERROR")
            continue
        dtw_delta = (100 * (r['dtw'] - bl_dtw) / bl_dtw) if bl_dtw > 0 else 0
        vloss_str = f"{r['val_loss']:>6.3f}" if 'val_loss' in r else "     -"
        print(f"  {name:<45} {vloss_str} {r['pitch_js']:>8.4f} {r['dtw']:>8.4f} "
              f"{r['transition_js']:>8.4f} {r['ncd']:>8.4f} {dtw_delta:>+7.1f}%")
    print(f"\n총 소요: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="방향 B: 중첩행렬 시간 재배치 통합 실험")
    parser.add_argument('--mode', required=True,
                        choices=['algo1', 'dl', 'dl_v2'])
    parser.add_argument('--midi', default="Ryuichi_Sakamoto_-_hibari.mid")
    parser.add_argument('--track', default="hibari")
    parser.add_argument('--metric', default="tonnetz")
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--n-trials', dest='n_trials', type=int, default=5,
                        help="algo1 모드: 전략당 반복 횟수 (기본 5)")
    parser.add_argument('--epochs', type=int, default=50,
                        help="dl/dl_v2 모드: 학습 에포크 수 (기본 50)")
    parser.add_argument('--out', default=None,
                        help="결과 저장 경로 (기본값은 모드별 고정 경로)")
    parser.add_argument('--from-cache', action='store_true', dest='from_cache',
                        help="cache/metric_{metric}.pkl 에서 overlap/cycle_labeled 직접 로드")

    args = parser.parse_args()

    dispatch = {
        'algo1': mode_algo1,
        'dl': mode_dl,
        'dl_v2': mode_dl_v2,
    }
    dispatch[args.mode](args)


if __name__ == '__main__':
    main()
