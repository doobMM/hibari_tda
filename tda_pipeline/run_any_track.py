"""
run_any_track.py — 임의의 MIDI 파일에 hibari 파이프라인 적용

사용법:
  python run_any_track.py <midi_file>
  python run_any_track.py --all   # 미리 정의된 전체 곡 리스트 순차 실행

전처리: pitch-only labeling (duration 무시, 기존 "tie 정규화")
거리 함수: frequency, tonnetz, voice_leading
Algorithm 1: 3 metrics × N=10 trials
"""
import os, sys, json, time, random, warnings, argparse
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict,
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
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

N_ALGO1 = 10
ALPHA = 0.5
RATE_STEP = 0.05
METRICS = ['frequency', 'tonnetz', 'voice_leading']

ALL_TRACKS = [
    ("a flower is not a flower", "a-flower-is-not-a-flower-ryuichi-sakamoto.mid"),
    ("bibo no aozora",           "bibo-no-aozora-solo-piano.mid"),
    ("energy flow",              "energy-flow-ryuichi-sakamoto.mid"),
    ("merry christmas",          "merry-christmas-mr-lawrence.mid"),
    ("the last emperor",         "the-last-emperor-theme-the-last-emperor-ryuichi-sakamoto.mid"),
    ("tong poo (solo)",          "tong-poo-solo-ver.mid"),
]


def pitch_only_notes(notes):
    """Pitch-only labeling: duration 을 모두 1 로 정규화."""
    return [(s, p, s + 1) for s, p, e in notes]


def preprocess(midi_file):
    adj, tempo, bounds = load_and_quantize(midi_file)
    inst1_raw, inst2_raw = split_instruments(adj, bounds[0])

    inst1 = pitch_only_notes(inst1_raw)
    inst2 = pitch_only_notes(inst2_raw)

    active1 = group_notes_with_duration(inst1)
    active2 = group_notes_with_duration(inst2)

    umap = {}; cnt = 0
    def label(active):
        nonlocal cnt
        out = []
        for t in sorted(active.keys()):
            ps = active[t]
            if ps is None: out.append(None); continue
            fs = frozenset(ps)
            if fs not in umap: umap[fs] = cnt; cnt += 1
            out.append(umap[fs])
        return out

    cs1 = label(active1); cs2 = label(active2)
    nc = cnt

    all_notes = inst1 + inst2
    notes_label, notes_counts = build_note_labels(all_notes)
    N = len(notes_label)
    notes_dict = chord_to_note_labels(umap, notes_label)
    notes_dict['name'] = 'notes'

    sp = min(32, max(1, len(cs1) // 8))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=sp, max_lag=4)
    T = max(e for _, _, e in adj) if adj else 0

    return {
        'inst1': inst1, 'inst2': inst2,
        'inst1_raw': inst1_raw, 'inst2_raw': inst2_raw,
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'N': N, 'num_chords': nc, 'T': T, 'tempo': tempo,
    }


def compute_ph(data, metric):
    adn_i = data['adn_i']; nd = data['notes_dict']
    nl = data['notes_label']; N = data['N']; T = data['T']; nc = data['num_chords']

    m_dist = (None if metric == 'frequency'
              else compute_note_distance_matrix(nl, metric=metric))

    from weights import compute_inter_weights_decayed

    inter = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=nc)
    w1 = compute_intra_weights(adn_i[1][0], num_chords=nc)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=nc)
    intra = w1 + w2
    oor = compute_out_of_reach(inter, power=-2)

    profile = []; rate = 0.0; t0 = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        fd = compute_distance_matrix(tw, nd, oor, num_notes=N).values
        final = compute_hybrid_distance(fd, m_dist, alpha=ALPHA) if m_dist is not None else fd
        bd = generate_barcode_numpy(mat=final, listOfDimension=[1],
                                    exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd)); rate += RATE_STEP

    persistence = group_rBD_by_homology(profile, dim=1)
    cl = label_cycles_from_persistence(persistence)
    elapsed = time.time() - t0
    if not cl:
        return None, None, 0, elapsed

    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    ns = simul_union_by_dict(cp, nd)
    nodes = list(range(1, N + 1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(ns))):
        if ns[t]:
            for n in ns[t]:
                if 1 <= n <= N: ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)
    act = build_activation_matrix(ntd_df, cl)
    ov = build_overlap_matrix(act, cl, threshold=0.35, total_length=T)
    return cl, ov.values, len(cl), elapsed


def run_algo1(data, ov, cl, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    mgr = CycleSetManager(cl)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    T = len(ov); h = (hp * (T//32+1))[:T]
    gen = algorithm1_optimized(pool, h, ov, mgr, max_resample=50)
    return gen


def process_one(name, midi_file):
    print(f"\n{'='*64}")
    print(f"  {name}  ({midi_file})")
    print(f"{'='*64}")

    try:
        data = preprocess(midi_file)
    except Exception as e:
        print(f"  PREPROCESS FAIL: {e}")
        return {'error': str(e)}

    print(f"  T={data['T']}  N={data['N']}  C={data['num_chords']}  "
          f"inst1={len(data['inst1'])}  inst2={len(data['inst2'])}")

    result = {'T': data['T'], 'N': data['N'], 'num_chords': data['num_chords'],
              'inst1_n': len(data['inst1']), 'inst2_n': len(data['inst2'])}

    for metric in METRICS:
        print(f"\n  [{metric}]", end=" ", flush=True)
        try:
            cl, ov, n_cyc, ph_time = compute_ph(data, metric)
        except Exception as e:
            print(f"FAIL: {e}")
            result[metric] = {'error': str(e)}
            continue

        if cl is None:
            print(f"no cycles")
            result[metric] = {'n_cycles': 0, 'error': 'no cycles'}
            continue

        print(f"{n_cyc} cycles, {ph_time:.1f}s", flush=True)

        trials = []
        for i in range(N_ALGO1):
            gen = run_algo1(data, ov, cl, seed=9700 + i)
            m = evaluate_generation(gen, [data['inst1'], data['inst2']],
                                    data['notes_label'], name="")
            trials.append(float(m['js_divergence']))

        js = np.array(trials)
        r = {'n_cycles': n_cyc, 'ph_time_s': round(ph_time, 1),
             'js_mean': round(float(js.mean()), 4),
             'js_std': round(float(js.std(ddof=1)), 4),
             'js_min': round(float(js.min()), 4)}
        result[metric] = r
        print(f"    JS = {r['js_mean']:.4f} ± {r['js_std']:.4f}  (best {r['js_min']:.4f})")

    # 최적 metric
    best_metric = None; best_js = 1.0
    for metric in METRICS:
        if metric in result and 'js_mean' in result[metric]:
            if result[metric]['js_mean'] < best_js:
                best_js = result[metric]['js_mean']
                best_metric = metric
    result['best_metric'] = best_metric
    result['best_js'] = best_js

    # Tonnetz 개선율
    if 'frequency' in result and 'tonnetz' in result:
        try:
            f = result['frequency']['js_mean']
            t = result['tonnetz']['js_mean']
            result['tonnetz_improvement'] = round(100 * (f - t) / f, 1)
        except (KeyError, ZeroDivisionError):
            pass

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('midi', nargs='?', default=None)
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()

    if args.all:
        tracks = ALL_TRACKS
    elif args.midi:
        name = os.path.splitext(os.path.basename(args.midi))[0]
        tracks = [(name, args.midi)]
    else:
        tracks = ALL_TRACKS

    all_results = {}
    for name, mid in tracks:
        all_results[name] = process_one(name, mid)

    # 요약
    print("\n\n" + "=" * 90)
    print("  최종 요약")
    print("=" * 90)
    print(f"  {'곡':30s} {'N':>4s} {'freq':>10s} {'tonnetz':>10s} {'voice_l':>10s} {'best':>12s} {'ton 개선':>8s}")
    print("  " + "─" * 88)

    # hibari / aqua / solari 참조값
    refs = [
        ("hibari (ref)", "—", "0.0753", "0.0398", "—", "tonnetz", "-47.2%"),
        ("aqua (ref)",   "51", "0.1249", "0.0920", "—", "tonnetz", "+26.3%"),
        ("solari (ref)", "34", "0.0643", "0.0816", "0.0631", "voice_l", "—"),
    ]
    for r in refs:
        print(f"  {r[0]:30s} {r[1]:>4s} {r[2]:>10s} {r[3]:>10s} {r[4]:>10s} {r[5]:>12s} {r[6]:>8s}")
    print("  " + "─" * 88)

    for name, r in all_results.items():
        if 'error' in r:
            print(f"  {name:30s}  ERROR: {r['error'][:40]}")
            continue
        def fmt(metric):
            if metric in r and 'js_mean' in r[metric]:
                return f"{r[metric]['js_mean']:.4f}"
            return "—"
        imp = f"{r.get('tonnetz_improvement', '—')}%" if 'tonnetz_improvement' in r else "—"
        print(f"  {name:30s} {r['N']:>4d} {fmt('frequency'):>10s} {fmt('tonnetz'):>10s} "
              f"{fmt('voice_leading'):>10s} {r.get('best_metric','—'):>12s} {imp:>8s}")

    # JSON 저장
    od = 'docs/step3_data'; os.makedirs(od, exist_ok=True)
    with open(f'{od}/all_tracks_results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {od}/all_tracks_results.json")


if __name__ == '__main__':
    main()
