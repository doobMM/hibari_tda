"""
run_all_full.py — 전곡 전체 파이프라인 (감쇄 lag + Algo1 + Algo2 DL)

각 곡에 대해:
  1. PH (frequency / tonnetz / voice_leading) + Algorithm 1 (N=10)
  2. 최적 metric 의 overlap 으로 Algorithm 2 (FC / LSTM / Transformer, N=3 seeds)
     - binary input, continuous input 각각
  3. 결과를 JSON 에 저장 (곡 단위로 중간 저장 → 중단 시 복구 가능)

출력: docs/step3_data/all_tracks_full_results.json
"""
import os, sys, json, time, random, warnings, argparse
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, chord_to_note_labels,
    prepare_lag_sequences, simul_chord_lists, simul_union_by_dict,
)
from weights import (
    compute_intra_weights, compute_inter_weights_decayed,
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

# ─── 실험 파라미터 ──────────────────────────────────────────────────────────
N_ALGO1   = 10
N_DL      = 3      # DL: 학습 느리므로 3 seeds
ALPHA     = 0.5
RATE_STEP = 0.05
METRICS   = ['frequency', 'tonnetz', 'voice_leading']
DL_EPOCHS = 60
DL_HIDDEN = 128
DL_LR     = 1e-3
DL_BATCH  = 32

ALL_TRACKS = [
    ("a flower is not a flower", "a-flower-is-not-a-flower-ryuichi-sakamoto.mid"),
    ("bibo no aozora",           "bibo-no-aozora-solo-piano.mid"),
    ("energy flow",              "energy-flow-ryuichi-sakamoto.mid"),
    ("merry christmas",          "merry-christmas-mr-lawrence.mid"),
    ("the last emperor",         "the-last-emperor-theme-the-last-emperor-ryuichi-sakamoto.mid"),
    ("tong poo (solo)",          "tong-poo-solo-ver.mid"),
]

OUT_DIR  = 'docs/step3_data'
OUT_JSON = f'{OUT_DIR}/all_tracks_full_results.json'


# ─── 전처리 ─────────────────────────────────────────────────────────────────

def pitch_only_notes(notes):
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


# ─── PH + overlap ────────────────────────────────────────────────────────────

def compute_ph(data, metric):
    adn_i = data['adn_i']; nd = data['notes_dict']
    nl = data['notes_label']; N = data['N']; T = data['T']; nc = data['num_chords']

    m_dist = (None if metric == 'frequency'
              else compute_note_distance_matrix(nl, metric=metric))

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
        return None, None, None, 0, elapsed

    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    ns = simul_union_by_dict(cp, nd)
    nodes = list(range(1, N + 1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(ns))):
        if ns[t]:
            for n in ns[t]:
                if 1 <= n <= N: ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)

    act_bin  = build_activation_matrix(ntd_df, cl, continuous=False)
    act_cont = build_activation_matrix(ntd_df, cl, continuous=True)
    ov_bin   = build_overlap_matrix(act_bin,  cl, threshold=0.35, total_length=T)

    return cl, ov_bin.values, act_cont.values, len(cl), elapsed


# ─── Algorithm 1 ────────────────────────────────────────────────────────────

def run_algo1(data, ov, cl, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    mgr  = CycleSetManager(cl)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    T = len(ov); h = (hp * (T // 32 + 1))[:T]
    return algorithm1_optimized(pool, h, ov, mgr, max_resample=50)


# ─── Algorithm 2 (DL) ───────────────────────────────────────────────────────

def run_algo2(data, ov_bin, act_cont, cl):
    """FC / LSTM / Transformer × binary + continuous."""
    try:
        import torch
        from generation import (
            prepare_training_data, MusicGeneratorFC,
            MusicGeneratorLSTM, MusicGeneratorTransformer,
            train_model, generate_from_model,
        )
    except ImportError as e:
        return {'error': str(e)}

    import io, contextlib

    nl = data['notes_label']; N = data['N']; T = data['T']
    inst1 = data['inst1']; inst2 = data['inst2']

    X_bin  = ov_bin.astype(np.float32)
    X_cont = act_cont.astype(np.float32)
    K = X_bin.shape[1]

    _, y = prepare_training_data(X_bin, [inst1, inst2], nl, T, N)

    np.random.seed(0)
    idx  = np.random.permutation(len(X_bin))
    sp   = int(len(X_bin) * 0.7)
    tr_i, va_i = idx[:sp], idx[sp:]

    results = {}
    for inp_name, X in [('binary', X_bin), ('continuous', X_cont)]:
        Xtr, ytr = X[tr_i], y[tr_i]
        Xva, yva = X[va_i], y[va_i]
        res_inp = {}

        for mtype in ['fc', 'lstm', 'transformer']:
            trials = []
            for si in range(N_DL):
                seed = 8200 + si * 7
                random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)

                if mtype == 'fc':
                    model = MusicGeneratorFC(K, N, hidden_dim=DL_HIDDEN, dropout=0.3)
                elif mtype == 'lstm':
                    model = MusicGeneratorLSTM(K, N, hidden_dim=DL_HIDDEN,
                                               num_layers=2, dropout=0.3)
                else:
                    model = MusicGeneratorTransformer(K, N, d_model=DL_HIDDEN,
                                                      nhead=4, num_layers=2,
                                                      dropout=0.1, max_len=T)
                t0 = time.time()
                with contextlib.redirect_stdout(io.StringIO()):
                    hist = train_model(model, Xtr, ytr, Xva, yva,
                                      epochs=DL_EPOCHS, lr=DL_LR,
                                      batch_size=DL_BATCH, model_type=mtype, seq_len=T)
                val = hist[-1]['val_loss']
                gen = generate_from_model(model, X, nl,
                                          model_type=mtype, adaptive_threshold=True)
                if not gen:
                    print(f"      [{inp_name}] {mtype:12s} seed={seed}  "
                          f"EMPTY generation (JS=1.0)", flush=True)
                    trials.append({'seed': seed, 'val': float(val),
                                   'js': 1.0, 'cov': 0.0, 'elapsed_s': round(time.time()-t0,1)})
                    continue
                m   = evaluate_generation(gen, [inst1, inst2], nl, name="")
                elapsed = time.time() - t0
                trials.append({'seed': seed, 'val': float(val),
                               'js': float(m['js_divergence']),
                               'cov': float(m['note_coverage']),
                               'elapsed_s': round(elapsed, 1)})
                print(f"      [{inp_name}] {mtype:12s} seed={seed}  "
                      f"val={val:.4f}  JS={m['js_divergence']:.4f}  "
                      f"cov={m['note_coverage']:.2f}  ({elapsed:.0f}s)", flush=True)

            js_arr = np.array([t['js'] for t in trials])
            res_inp[mtype] = {
                'js_mean': round(float(js_arr.mean()), 4),
                'js_std':  round(float(js_arr.std(ddof=1)), 4),
                'js_min':  round(float(js_arr.min()), 4),
                'val_mean': round(float(np.mean([t['val'] for t in trials])), 4),
                'trials': trials,
            }
        results[inp_name] = res_inp
    return results


# ─── 한 곡 처리 ─────────────────────────────────────────────────────────────

def process_one(name, midi_file):
    print(f"\n{'='*68}")
    print(f"  {name}  ({midi_file})")
    print(f"{'='*68}")

    try:
        data = preprocess(midi_file)
    except Exception as e:
        print(f"  PREPROCESS FAIL: {e}")
        return {'error': str(e)}

    print(f"  T={data['T']}  N={data['N']}  C={data['num_chords']}")
    result = {'T': data['T'], 'N': data['N'], 'num_chords': data['num_chords'],
              'algo1': {}}

    best_js = 1.0; best_metric = None
    best_cl = None; best_ov_bin = None; best_act_cont = None

    # ── Algorithm 1 ──
    for metric in METRICS:
        print(f"\n  [Algo1/{metric}]", end=" ", flush=True)
        try:
            cl, ov_bin, act_cont, n_cyc, ph_time = compute_ph(data, metric)
        except Exception as e:
            print(f"FAIL: {e}")
            result['algo1'][metric] = {'error': str(e)}
            continue

        if cl is None:
            print("no cycles")
            result['algo1'][metric] = {'n_cycles': 0, 'error': 'no cycles'}
            continue

        print(f"{n_cyc} cycles, {ph_time:.1f}s", flush=True)

        trials = []
        for i in range(N_ALGO1):
            gen = run_algo1(data, ov_bin, cl, seed=9700 + i)
            m   = evaluate_generation(gen, [data['inst1'], data['inst2']],
                                      data['notes_label'], name="")
            trials.append(float(m['js_divergence']))

        js = np.array(trials)
        r = {'n_cycles': n_cyc, 'ph_time_s': round(ph_time, 1),
             'js_mean': round(float(js.mean()), 4),
             'js_std':  round(float(js.std(ddof=1)), 4),
             'js_min':  round(float(js.min()), 4)}
        result['algo1'][metric] = r
        print(f"    JS = {r['js_mean']:.4f} ± {r['js_std']:.4f}  (best {r['js_min']:.4f})")

        if r['js_mean'] < best_js:
            best_js     = r['js_mean']
            best_metric = metric
            best_cl     = cl
            best_ov_bin  = ov_bin
            best_act_cont = act_cont

    result['best_metric'] = best_metric
    result['best_js_algo1'] = round(best_js, 4)

    # tonnetz_improvement
    if 'frequency' in result['algo1'] and 'tonnetz' in result['algo1']:
        try:
            f = result['algo1']['frequency']['js_mean']
            t = result['algo1']['tonnetz']['js_mean']
            result['tonnetz_improvement'] = round(100 * (f - t) / f, 1)
        except (KeyError, ZeroDivisionError):
            pass

    # ── Algorithm 2 ──
    if best_cl is not None:
        print(f"\n  [Algo2/DL] best_metric={best_metric}, K={len(best_cl)}")
        try:
            dl_res = run_algo2(data, best_ov_bin, best_act_cont, best_cl)
            result['algo2'] = dl_res
        except Exception as e:
            print(f"  Algo2 FAIL: {e}")
            result['algo2'] = {'error': str(e)}

        # best DL 요약
        if 'algo2' in result and 'error' not in result['algo2']:
            best_dl_js = 1.0; best_dl_key = None
            for inp_name, inp_res in result['algo2'].items():
                for mtype, v in inp_res.items():
                    if isinstance(v, dict) and 'js_mean' in v:
                        if v['js_mean'] < best_dl_js:
                            best_dl_js  = v['js_mean']
                            best_dl_key = f"{inp_name}/{mtype}"
            result['best_dl'] = best_dl_key
            result['best_js_dl'] = round(best_dl_js, 4)
            print(f"  Best DL: {best_dl_key}  JS={best_dl_js:.4f}")
    else:
        print("  [Algo2] skip — no cycles found in any metric")

    return result


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('midi', nargs='?', default=None)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--resume', action='store_true',
                        help='기존 JSON 에서 이미 완료된 곡 skip')
    args = parser.parse_args()

    if args.all or args.midi is None:
        tracks = ALL_TRACKS
    else:
        name = os.path.splitext(os.path.basename(args.midi))[0]
        tracks = [(name, args.midi)]

    # resume: 기존 결과 로드
    all_results = {}
    if args.resume and os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            all_results = json.load(f)
        print(f"[resume] 기존 결과 {len(all_results)}곡 로드")

    for name, mid in tracks:
        if args.resume and name in all_results:
            print(f"  skip (already done): {name}")
            continue

        result = process_one(name, mid)
        all_results[name] = result

        # 곡 단위 중간 저장
        os.makedirs(OUT_DIR, exist_ok=True)
        _save(all_results)
        print(f"  [저장] {OUT_JSON}")

    # ── 최종 요약 ──
    _print_summary(all_results)


def _save(all_results):
    """trials 포함 전체 저장."""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)


def _print_summary(all_results):
    print("\n\n" + "=" * 100)
    print("  전체 요약")
    print("=" * 100)
    hdr = f"  {'곡':30s} {'N':>4s} {'freq':>8s} {'tonnetz':>8s} {'voice_l':>8s} {'best_A1':>12s} {'ton%':>6s} | {'best_DL':>22s} {'DL_JS':>7s}"
    print(hdr)
    print("  " + "─" * 98)

    for name, r in all_results.items():
        if 'error' in r:
            print(f"  {name:30s}  ERROR")
            continue

        def fmt_a1(m):
            v = r.get('algo1', {}).get(m, {})
            return f"{v['js_mean']:.4f}" if 'js_mean' in v else "—"

        imp = f"{r['tonnetz_improvement']:+.1f}%" if 'tonnetz_improvement' in r else "—"
        best_dl  = r.get('best_dl', '—')
        best_dlj = f"{r['best_js_dl']:.4f}" if 'best_js_dl' in r else "—"

        print(f"  {name:30s} {r['N']:>4d} "
              f"{fmt_a1('frequency'):>8s} {fmt_a1('tonnetz'):>8s} {fmt_a1('voice_leading'):>8s} "
              f"{r.get('best_metric','—'):>12s} {imp:>6s} | "
              f"{best_dl:>22s} {best_dlj:>7s}")

    # DL 상세
    print("\n  ── DL 상세 (binary / continuous × FC / LSTM / Transformer) ──")
    for name, r in all_results.items():
        if 'error' in r or 'algo2' not in r or 'error' in r.get('algo2', {}):
            continue
        print(f"\n  [{name}]")
        for inp_name, inp_res in r['algo2'].items():
            for mtype, v in inp_res.items():
                if isinstance(v, dict) and 'js_mean' in v:
                    print(f"    {inp_name:12s} {mtype:12s}: "
                          f"JS={v['js_mean']:.4f}±{v['js_std']:.4f}  "
                          f"best={v['js_min']:.4f}")

    print(f"\n  JSON: {OUT_JSON}")


if __name__ == '__main__':
    main()
