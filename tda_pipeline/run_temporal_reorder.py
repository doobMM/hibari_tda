"""
run_temporal_reorder.py — 방향 B: 중첩행렬 시간 재배치 실험

hibari에 대해 3가지 재배치 전략을 적용하고,
기존(원본) 생성 결과와 비교하여 "느낌은 비슷하나 다른 선율"이 만들어지는지 평가.

평가 지표:
  - pitch JS   : 분포 유사도 (낮을수록 좋음)
  - DTW        : 선율 윤곽 차이 (적당히 달라야 함 ★)
  - transition JS: 진행 패턴 차이
  - NCD        : 구조적 닮음

사용법:
  python run_temporal_reorder.py
"""
import os, sys, time, json, random, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph, run_algo1
from temporal_reorder import reorder_overlap_matrix
from eval_metrics import evaluate_generation
from sequence_metrics import evaluate_sequence_metrics

# ── 설정 ────────────────────────────────────────────────────────────────

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
TRACK_NAME = "hibari"
METRIC = "tonnetz"          # hibari 최적 거리 함수
N_TRIALS = 5                # 전략당 생성 횟수
SEED_BASE = 42

STRATEGIES = [
    ('segment_shuffle', {}),
    ('block_permute',   {'block_size': 32}),
    ('block_permute',   {'block_size': 64}),
    ('markov_resample', {'temperature': 1.0}),
    ('markov_resample', {'temperature': 1.5}),
]


def run_experiment():
    print("=" * 64)
    print(f"  방향 B: 중첩행렬 시간 재배치 실험 — {TRACK_NAME}")
    print("=" * 64)

    # ── 1. 전처리 + PH ──
    t0 = time.time()
    data = preprocess(MIDI_FILE)
    print(f"\n[전처리] T={data['T']}  N={data['N']}  C={data['num_chords']}")

    cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
    if cl is None:
        print("ERROR: no cycles found")
        return
    print(f"[PH] {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

    # ── 2. Baseline (원본 중첩행렬) ──
    print(f"\n{'─'*64}")
    print(f"  [Baseline] 원본 중첩행렬 → Algo1 × {N_TRIALS}")
    print(f"{'─'*64}")

    original_notes = data['inst1'] + data['inst2']
    baseline_results = []

    for i in range(N_TRIALS):
        gen = run_algo1(data, ov, cl, seed=SEED_BASE + i)
        js_m = evaluate_generation(gen, [data['inst1'], data['inst2']],
                                   data['notes_label'], name="")
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

    # ── 3. 각 전략 실험 ──
    all_results = {
        'track': TRACK_NAME,
        'metric': METRIC,
        'n_cycles': n_cyc,
        'n_trials': N_TRIALS,
        'baseline': {
            'avg': {k: round(v, 6) for k, v in baseline_avg.items()},
            'std': {k: round(v, 6) for k, v in baseline_std.items()},
        },
        'strategies': {},
    }

    for strategy_name, kwargs in STRATEGIES:
        label = strategy_name
        if kwargs:
            label += "_" + "_".join(f"{k}{v}" for k, v in kwargs.items())

        print(f"\n{'─'*64}")
        print(f"  [{label}] 재배치 → Algo1 × {N_TRIALS}")
        print(f"{'─'*64}")

        strategy_results = []
        reorder_info = None

        for i in range(N_TRIALS):
            # 매 trial마다 다른 seed로 재배치
            reordered, info = reorder_overlap_matrix(
                ov, strategy=strategy_name, seed=SEED_BASE + i * 100, **kwargs
            )
            if reorder_info is None:
                reorder_info = info

            gen = run_algo1(data, reordered, cl, seed=SEED_BASE + i)
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

        # baseline 대비 변화율
        delta = {}
        for k in avg:
            if baseline_avg[k] > 0:
                delta[k] = round(100 * (avg[k] - baseline_avg[k]) / baseline_avg[k], 1)
            else:
                delta[k] = 0.0

        print(f"  pitch JS:      {avg['pitch_js']:.4f} ± {std['pitch_js']:.4f}  (Δ {delta['pitch_js']:+.1f}%)")
        print(f"  transition JS: {avg['transition_js']:.4f} ± {std['transition_js']:.4f}  (Δ {delta['transition_js']:+.1f}%)")
        print(f"  DTW:           {avg['dtw']:.4f} ± {std['dtw']:.4f}  (Δ {delta['dtw']:+.1f}%)")
        print(f"  NCD:           {avg['ncd']:.4f} ± {std['ncd']:.4f}  (Δ {delta['ncd']:+.1f}%)")

        # 핵심 판정: pitch JS 유지 + DTW 증가 = 성공
        pitch_ok = delta['pitch_js'] < 20  # pitch 분포 20% 이내
        dtw_diff = delta['dtw'] > 10       # DTW 10% 이상 변화
        verdict = "★ 유망" if (pitch_ok and dtw_diff) else "△ 보통" if pitch_ok else "✗ 분포 붕괴"
        print(f"  판정: {verdict}")

        all_results['strategies'][label] = {
            'avg': {k: round(v, 6) for k, v in avg.items()},
            'std': {k: round(v, 6) for k, v in std.items()},
            'delta_pct': delta,
            'verdict': verdict,
            'reorder_info': {k: v for k, v in reorder_info.items()
                            if k not in ('shuffle_order', 'orig_state_dist', 'new_state_dist')},
        }

    # ── 4. 결과 저장 ──
    elapsed = time.time() - t0
    all_results['elapsed_s'] = round(elapsed, 1)

    out_path = os.path.join("docs", "step3_data", "temporal_reorder_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n결과 저장: {out_path}")

    # ── 5. 요약 테이블 ──
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


if __name__ == '__main__':
    run_experiment()
