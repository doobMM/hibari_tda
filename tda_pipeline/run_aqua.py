"""
run_aqua.py — Sakamoto "aqua" 에 hibari 파이프라인 적용

hibari 에 적용된 동일한 workflow 를 aqua 한 곡에 적용하는 전용 스크립트.
일반화를 통째로 하는 대신 aqua 만 집중하여 §3.1 의 주요 결과
(frequency vs tonnetz, JS divergence) 를 재현할 수 있는지 확인한다.

기본 설정:
  - Tonnetz (α=0.5) 와 frequency 두 거리 함수 비교
  - Algorithm 1 (확률적 샘플링), N=10 trials
  - chord-height 패턴은 hibari 와 동일 ([4,4,4,3,4,3,...] × n_rep)
"""
import os, sys, json, time, random, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing import (
    load_and_quantize, split_instruments,
    group_notes_with_duration, build_note_labels,
    chord_to_note_labels, prepare_lag_sequences,
    simul_chord_lists, simul_union_by_dict,
)
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
from generation import algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml
from eval_metrics import evaluate_generation

MIDI_FILE = "aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid"
N_REPEATS = 10
ALPHA = 0.5       # Tonnetz hybrid weight
RATE_STEP = 0.05  # rate sweep 간격 (hibari 0.01 보다 넓게 — N=51 이라 가속 필요)


def tie_normalize_notes(notes):
    """
    붙임줄(tie) 해석: 모든 note 의 duration 을 GCD 단위로 정규화.
    aqua 의 경우 GCD=1 이므로 (start, pitch, start+1) 로 변환.

    음악적 해석: dur > GCD 인 note 는 "최소 음가(GCD) 짜리 note 가
    붙임줄로 이어진 것"으로 간주. 위상 분석에서 note identity 는
    pitch 만으로 결정되며, duration 차이는 더 이상 다른 note 를
    만들지 않는다.

    효과: aqua 의 unique (pitch, dur) 쌍이 157 → 51 (unique pitch) 로 감소.
    """
    from math import gcd
    from functools import reduce
    durs = [e - s for s, _, e in notes if e > s]
    d = reduce(gcd, durs) if durs else 1
    return [(s, p, s + d) for s, p, e in notes], d


def preprocess_aqua():
    """
    aqua 전용 전처리.

    hibari 와 달리:
      - solo_notes 개념 없음 (두 악기 모두 t=0 에서 시작)
      - notes_label / notes_dict 를 전체 note 기반으로 만듦
      - 통합 chord label 체계 (두 악기를 하나의 chord_map 으로)
    """
    print("=" * 64)
    print("  Preprocess aqua")
    print("=" * 64)

    adj, tempo, boundaries = load_and_quantize(MIDI_FILE)
    inst1_raw, inst2_raw = split_instruments(adj, boundaries[0])
    print(f"  tempo = {tempo:.1f} BPM")
    print(f"  inst1 raw: {len(inst1_raw)} notes, pitch "
          f"[{min(p for _,p,_ in inst1_raw)}, {max(p for _,p,_ in inst1_raw)}]")
    print(f"  inst2 raw: {len(inst2_raw)} notes, pitch "
          f"[{min(p for _,p,_ in inst2_raw)}, {max(p for _,p,_ in inst2_raw)}]")

    # ── 붙임줄(tie) 해석: dur → GCD 단위 정규화 ──
    inst1_real, d1 = tie_normalize_notes(inst1_raw)
    inst2_real, d2 = tie_normalize_notes(inst2_raw)
    print(f"  tie normalization: GCD inst1={d1}, inst2={d2}")
    print(f"  unique (pitch,dur) 기존: {len(set((p,e-s) for s,p,e in inst1_raw+inst2_raw))}"
          f" → 정규화 후: {len(set((p,e-s) for s,p,e in inst1_real+inst2_real))}")

    # ── 통합 chord 라벨 체계 ──
    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)

    unified_map = {}
    counter = 0
    def label_seq(active):
        nonlocal counter
        out = []
        for t in sorted(active.keys()):
            ps = active[t]
            if ps is None:
                out.append(None); continue
            fs = frozenset(ps)
            if fs not in unified_map:
                unified_map[fs] = counter; counter += 1
            out.append(unified_map[fs])
        return out
    chord_seq1 = label_seq(active1)
    chord_seq2 = label_seq(active2)

    num_chords = counter
    print(f"  chord_seq1 len={len(chord_seq1)}, chord_seq2 len={len(chord_seq2)}")
    print(f"  unified chord labels: {num_chords}")

    # ── note label (전체 note 기반) ──
    all_notes = inst1_real + inst2_real
    notes_label, notes_counts = build_note_labels(all_notes)
    N = len(notes_label)
    print(f"  unique notes (N): {N}")

    # ── notes_dict (chord → note label 집합) ──
    notes_dict = chord_to_note_labels(unified_map, notes_label)
    notes_dict['name'] = 'notes'

    # ── lag sequence ──
    # solo_timepoints 는 짧은 곡에서 너무 크면 lag 시퀀스가 비게 되므로 조정
    sp = min(32, max(1, len(chord_seq1) // 8))
    adn_i = prepare_lag_sequences(chord_seq1, chord_seq2,
                                   solo_timepoints=sp, max_lag=4)

    # ── total timepoints ──
    all_ends = [e for _, _, e in adj]
    T = max(all_ends) if all_ends else 0
    print(f"  T = {T}, sp = {sp}")

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


def compute_overlap(data, metric_name, alpha=ALPHA):
    """주어진 거리 함수로 PH → cycle_labeled + overlap."""
    adn_i = data['adn_i']
    notes_dict = data['notes_dict']
    notes_label = data['notes_label']
    N = data['N']
    T = data['T']
    nc = data['num_chords']

    print(f"\n  [{metric_name}] computing PH...")
    m_dist = (None if metric_name == 'frequency'
              else compute_note_distance_matrix(notes_label, metric=metric_name))

    w1 = compute_intra_weights(adn_i[1][0], num_chords=nc)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=nc)
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1],
                                  num_chords=nc, lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    # Rate sweep 0 ~ 1.5, 간격 RATE_STEP
    profile = []
    rate = 0.0
    steps = 0
    total_steps = int(1.5 / RATE_STEP) + 1
    t_start = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(
            tw, notes_dict, oor, num_notes=N).values
        final = (compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)
                 if m_dist is not None else freq_dist)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd))
        rate += RATE_STEP
        steps += 1
        if steps % 5 == 0 or steps == total_steps:
            elapsed = time.time() - t_start
            print(f"    rate {r:.2f}  step {steps}/{total_steps}  "
                  f"elapsed {elapsed:.1f}s", flush=True)

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    print(f"    rate sweep: {steps} steps, cycles found: {len(cycle_labeled)}")
    if len(cycle_labeled) == 0:
        return None, None

    # Activation → overlap
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
    ov = overlap.values
    print(f"    overlap shape: {ov.shape}, density: {(ov > 0).mean():.3f}")
    return cycle_labeled, ov


def run_algo1(data, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
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


def eval_generated(data, generated):
    m = evaluate_generation(
        generated,
        [data['inst1_real'], data['inst2_real']],
        data['notes_label'], name="")
    return {
        'js': float(m['js_divergence']),
        'cov': float(m['note_coverage']),
        'n_notes': int(len(generated)),
    }


def main():
    data = preprocess_aqua()

    results = {}
    best_overall = {'js': 1.0, 'metric': None, 'seed': None, 'gen': None}

    for metric in ['frequency', 'tonnetz']:
        try:
            cl, ov = compute_overlap(data, metric, alpha=ALPHA)
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            results[metric] = {'error': str(e)}
            continue

        if cl is None or ov is None:
            results[metric] = {'error': 'no cycles found'}
            continue

        print(f"\n  Running {N_REPEATS} trials of Algorithm 1...")
        trials = []
        for i in range(N_REPEATS):
            seed = 9500 + i
            gen, el = run_algo1(data, ov, cl, seed)
            ev = eval_generated(data, gen)
            ev['seed'] = seed
            ev['elapsed_ms'] = el * 1000
            trials.append(ev)
            print(f"    [{i+1:2d}] seed={seed}  JS={ev['js']:.4f}  "
                  f"cov={ev['cov']:.2f}  notes={ev['n_notes']}  "
                  f"({ev['elapsed_ms']:.1f} ms)")
            if ev['js'] < best_overall['js']:
                best_overall = {
                    'js': ev['js'], 'metric': metric,
                    'seed': seed, 'gen': gen, 'cov': ev['cov'],
                    'n_notes': ev['n_notes'],
                }

        js_arr = np.array([t['js'] for t in trials])
        cov_arr = np.array([t['cov'] for t in trials])
        results[metric] = {
            'n_cycles': len(cl),
            'density': float((ov > 0).mean()),
            'js_mean': float(js_arr.mean()),
            'js_std':  float(js_arr.std(ddof=1)),
            'js_min':  float(js_arr.min()),
            'js_max':  float(js_arr.max()),
            'cov_mean': float(cov_arr.mean()),
            'trials': trials,
        }
        print(f"  → {metric}: JS = {results[metric]['js_mean']:.4f} "
              f"± {results[metric]['js_std']:.4f}  "
              f"(best {results[metric]['js_min']:.4f})")

    # ── 요약 ──
    print("\n" + "=" * 64)
    print("  요약 — aqua (hibari baseline: freq 0.0753, ton 0.0398, -47.2%)")
    print("=" * 64)
    for metric, r in results.items():
        if 'error' in r:
            print(f"  {metric:12s}: ERROR {r['error']}")
            continue
        print(f"  {metric:12s}: {r['n_cycles']:3d} cycles, "
              f"density {r['density']:.3f}, "
              f"JS = {r['js_mean']:.4f} ± {r['js_std']:.4f}  "
              f"(best {r['js_min']:.4f})")

    try:
        f = results['frequency']['js_mean']
        t = results['tonnetz']['js_mean']
        imp = 100 * (f - t) / f
        print(f"\n  Tonnetz improvement: {imp:+.1f}% (hibari baseline: -47.2%)")
    except (KeyError, ZeroDivisionError, TypeError):
        pass

    # ── Best trial 저장 ──
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if best_overall['gen'] is not None:
        fname = f"aqua_best_{best_overall['metric']}_s{best_overall['seed']}_{ts}"
        notes_to_xml([best_overall['gen']],
                     tempo_bpm=int(round(data['tempo'])),
                     file_name=fname, output_dir="./output")
        print(f"\n  Best trial saved: output/{fname}.musicxml")
        print(f"    JS = {best_overall['js']:.4f} "
              f"({best_overall['metric']}, seed {best_overall['seed']})")

    # ── JSON 저장 ──
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    lite = {k: ({kk: vv for kk, vv in v.items() if kk != 'trials'}
                if isinstance(v, dict) else v)
            for k, v in results.items()}
    lite['T'] = data['T']
    lite['N'] = data['N']
    lite['num_chords'] = data['num_chords']
    lite['inst1_n'] = len(data['inst1_real'])
    lite['inst2_n'] = len(data['inst2_real'])
    lite['n_repeats'] = N_REPEATS
    lite['best_overall'] = {k: v for k, v in best_overall.items() if k != 'gen'}
    with open(os.path.join(out_dir, 'aqua_results.json'),
              'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {out_dir}/aqua_results.json")


if __name__ == '__main__':
    main()
