"""
run_generalization.py — §7.2 다른 곡으로의 일반화

사카모토 류이치의 8곡에 같은 파이프라인을 적용하여 본 연구의 핵심 주장이
hibari-specific 인지 일반적 패턴인지 검증한다.

각 곡에 대해 수행:
  1. 전처리 + 자동 파라미터 감지
  2. Frequency 와 Tonnetz 두 거리 함수로 PH 수행 → cycle_labeled + overlap
  3. Algorithm 1을 N=10회 반복 → JS divergence 측정
  4. 두 거리 함수 간 JS 감소율 계산 (§3.1 hibari 에서 -47%)

결과: docs/step3_data/step72_generalization.json
"""
import os, sys, json, time, random, pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from config import PipelineConfig, MIDIConfig
from pipeline import TDAMusicPipeline
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation
from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_distance_matrix, compute_out_of_reach,
)
from overlap import (
    group_rBD_by_homology, label_cycles_from_persistence,
    build_activation_matrix, build_overlap_matrix,
)
from topology import generate_barcode_numpy
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict,
)
from collections import Counter


TRACKS = [
    ("hibari (baseline)", "Ryuichi_Sakamoto_-_hibari.mid"),
    ("aqua",              "aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid"),
    ("a flower is not a flower",
                          "a-flower-is-not-a-flower-ryuichi-sakamoto.mid"),
    ("bibo no aozora",    "bibo-no-aozora-solo-piano.mid"),
    ("energy flow",       "energy-flow-ryuichi-sakamoto.mid"),
    ("merry christmas Mr Lawrence",
                          "merry-christmas-mr-lawrence.mid"),
    ("solari",            "ryuichi-sakamoto-solari.mid"),
    ("the last emperor theme",
                          "the-last-emperor-theme-the-last-emperor-ryuichi-sakamoto.mid"),
    ("tong poo (solo)",   "tong-poo-solo-ver.mid"),
]

N_REPEATS = 10


def preprocess_unified(midi_file):
    """
    곡 하나를 통합 chord label 체계로 전처리한다.

    기존 pipeline.run_preprocessing() 는 notes_dict 를 첫 `solo_notes` 개
    note 만 보고 만들기 때문에, 다른 곡에서는 adn_i 의 chord label 과 label
    체계가 어긋난다. 본 함수는 두 악기의 전체 note 를 모두 보고 하나의 통합
    chord_map 을 구축하여 모든 것이 일관된 label 을 사용하도록 한다.

    Returns: dict with keys matching pipeline._cache entries
    """
    # 1) MIDI 로드 + 양자화
    adjusted, tempo, boundaries = load_and_quantize(midi_file, quantize_unit=None)
    if not boundaries:
        raise ValueError("no instrument boundary detected")
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    if not inst1 or not inst2:
        raise ValueError(f"empty instrument: inst1={len(inst1)} inst2={len(inst2)}")

    inst1_real = inst1  # solo removal 생략 (일반화를 위해)
    inst2_real = inst2

    # 2) group_notes_with_duration 을 전체 곡에 적용
    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)

    # 3) 통합 chord map: 두 악기의 frozenset 을 모두 모아 하나의 label 체계로
    unified_map = {}
    label_counter = 0

    def to_labeled_seq(active_dict):
        nonlocal label_counter
        seq = []
        for t in sorted(active_dict.keys()):
            ps = active_dict[t]
            if ps is None:
                seq.append(None); continue
            fs = frozenset(ps)
            if fs not in unified_map:
                unified_map[fs] = label_counter
                label_counter += 1
            seq.append(unified_map[fs])
        return seq

    chord_seq1 = to_labeled_seq(active1)
    chord_seq2 = to_labeled_seq(active2)

    # 4) note label 은 전체 note 기준으로 생성
    all_notes = inst1_real + inst2_real
    notes_label, notes_counts = build_note_labels(all_notes)
    N = len(notes_label)
    if N == 0:
        raise ValueError("empty notes_label")

    # 5) notes_dict: 통합 chord_map 을 note label 집합으로 변환
    notes_dict = chord_to_note_labels(unified_map, notes_label)
    notes_dict['name'] = 'notes'

    # 6) lag sequence — solo_timepoints 는 prepare_lag_sequences 내부에서
    # lag1 구간 시작점을 정하는 데 쓰이며, 0이면 lag1_2 가 빈 리스트가 된다.
    # hibari 의 32 가 기본값이지만 짧은 곡에서는 전체 길이 대비 너무 클 수
    # 있으므로 min(32, T//8) 로 안전 처리.
    sp = min(32, max(1, len(chord_seq1) // 8))
    adn_i = prepare_lag_sequences(chord_seq1, chord_seq2,
                                   solo_timepoints=sp, max_lag=4)

    # 7) total_length
    all_ends = [e for _, _, e in adjusted]
    T = max(all_ends) if all_ends else 0

    num_chords = label_counter

    return {
        'inst1_real': inst1_real,
        'inst2_real': inst2_real,
        'chord_seq1': chord_seq1,
        'chord_seq2': chord_seq2,
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'notes_dict': notes_dict,
        'unified_chord_map': unified_map,
        'adn_i': adn_i,
        'T': T,
        'N': N,
        'num_chords': num_chords,
        'tempo': tempo,
    }


def compute_overlap_for_metric(data, metric_name, alpha=0.5):
    """주어진 거리 함수로 PH → cycle_labeled + overlap 행렬."""
    notes_label = data['notes_label']
    notes_dict = data['notes_dict']
    adn_i = data['adn_i']
    N = data['N']
    T = data['T']
    nc = data['num_chords']

    if metric_name == 'frequency':
        m_dist = None
    else:
        m_dist = compute_note_distance_matrix(notes_label, metric=metric_name)

    w1 = compute_intra_weights(adn_i[1][0], num_chords=nc)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=nc)
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1],
                                  num_chords=nc, lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    # rate sweep (hibari 와 동일하게 0.01 간격)
    profile = []
    rate = 0.0
    while rate <= 1.5 + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(
            tw, notes_dict, oor, num_notes=N).values
        final = (compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)
                 if m_dist is not None else freq_dist)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd))
        rate += 0.01

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    if len(cycle_labeled) == 0:
        return None, None

    # activation + overlap
    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(ntd_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled,
                                   threshold=0.35, total_length=T)
    return cycle_labeled, overlap.values


def run_algo1(data, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    # chord height 는 hibari 와 동일한 패턴을 쓰되, 곡 길이에 맞춰 반복
    heights_pattern = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                       4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    T = len(overlap_values)
    n_rep = T // len(heights_pattern) + 1
    heights = (heights_pattern * n_rep)[:T]
    t0 = time.time()
    generated = algorithm1_optimized(
        pool, heights, overlap_values, manager,
        max_resample=50, verbose=False)
    return generated, time.time() - t0


def run_eval(data, generated):
    notes_label = data['notes_label']
    inst1 = data['inst1_real']
    inst2 = data['inst2_real']
    m = evaluate_generation(generated, [inst1, inst2], notes_label, name="")
    return {'js': float(m['js_divergence']),
            'cov': float(m['note_coverage']),
            'n_notes': int(len(generated))}


def process_track(display_name, midi_file):
    print(f"\n{'='*72}")
    print(f"  {display_name}  ({midi_file})")
    print('='*72)
    try:
        data = preprocess_unified(midi_file)
    except Exception as e:
        return {'error': f"preprocess failed: {type(e).__name__}: {e}"}

    T = data['T']
    N = data['N']
    nc = data['num_chords']
    print(f"  T={T}  N={N}  C={nc}  "
          f"inst1={len(data['inst1_real'])}  "
          f"inst2={len(data['inst2_real'])}")
    if N == 0 or nc == 0:
        return {'error': 'empty labels after preprocessing'}

    result = {
        'file': midi_file,
        'T': T, 'N': N, 'C': nc,
        'inst1_n': len(data['inst1_real']),
        'inst2_n': len(data['inst2_real']),
    }

    for metric in ['frequency', 'tonnetz']:
        print(f"\n  [{metric}]")
        try:
            cl, ov = compute_overlap_for_metric(data, metric)
        except Exception as e:
            print(f"    PH failed: {type(e).__name__}: {e}")
            result[metric] = {'error': str(e)}
            continue

        if cl is None or ov is None:
            print(f"    PH empty — no cycles found")
            result[metric] = {'n_cycles': 0, 'error': 'no cycles'}
            continue

        n_cycles = len(cl)
        print(f"    cycles = {n_cycles}, overlap {ov.shape}, "
              f"density {(ov > 0).mean():.3f}")

        trials = []
        for i in range(N_REPEATS):
            gen, el = run_algo1(data, ov, cl, seed=8500 + i)
            ev = run_eval(data, gen)
            ev['elapsed_ms'] = el * 1000
            trials.append(ev)
        js_arr = np.array([t['js'] for t in trials])
        cov_arr = np.array([t['cov'] for t in trials])
        result[metric] = {
            'n_cycles': n_cycles,
            'density': float((ov > 0).mean()),
            'js_mean': float(js_arr.mean()),
            'js_std':  float(js_arr.std(ddof=1)),
            'js_min':  float(js_arr.min()),
            'js_max':  float(js_arr.max()),
            'cov_mean': float(cov_arr.mean()),
            'avg_time_ms': float(np.mean([t['elapsed_ms'] for t in trials])),
        }
        print(f"    JS = {result[metric]['js_mean']:.4f} "
              f"± {result[metric]['js_std']:.4f}  "
              f"(best {result[metric]['js_min']:.4f})")

    # ── Tonnetz 개선율 계산 ──
    try:
        f = result['frequency']['js_mean']
        t = result['tonnetz']['js_mean']
        result['improvement_pct'] = float(100 * (f - t) / f)
        print(f"\n  → Tonnetz 개선율: {result['improvement_pct']:+.1f}%  "
              f"(hibari baseline: -47.2%)")
    except (KeyError, ZeroDivisionError):
        result['improvement_pct'] = None

    return result


def main():
    print("=" * 72)
    print("  §7.2 — 사카모토 9곡 일반화 실험")
    print("=" * 72)

    all_results = {}
    for name, mid in TRACKS:
        try:
            all_results[name] = process_track(name, mid)
        except Exception as e:
            print(f"  FAIL: {e}")
            all_results[name] = {'error': str(e)}

    # ── 최종 요약 ──
    print("\n\n" + "=" * 90)
    print("  요약")
    print("=" * 90)
    hdr = f"  {'곡':30s} {'T':>5s} {'N':>3s} {'C':>3s}  {'freq cyc':>8s}  {'ton cyc':>7s}  {'freq JS':>8s}  {'ton JS':>8s}  {'개선':>7s}"
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))
    for name, r in all_results.items():
        if 'error' in r:
            print(f"  {name:30s}  ERROR: {r['error'][:40]}")
            continue
        f_cyc = r.get('frequency', {}).get('n_cycles', 0)
        t_cyc = r.get('tonnetz', {}).get('n_cycles', 0)
        f_js  = r.get('frequency', {}).get('js_mean', float('nan'))
        t_js  = r.get('tonnetz', {}).get('js_mean', float('nan'))
        imp   = r.get('improvement_pct')
        imp_s = f"{imp:+.1f}%" if imp is not None else "—"
        print(f"  {name:30s}  {r['T']:>5d} {r['N']:>3d} {r['C']:>3d}  "
              f"{f_cyc:>8d}  {t_cyc:>7d}  "
              f"{f_js:>8.4f}  {t_js:>8.4f}  {imp_s:>7s}")

    # JSON 저장
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'step72_generalization.json'),
              'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {out_dir}/step72_generalization.json")


if __name__ == '__main__':
    main()
