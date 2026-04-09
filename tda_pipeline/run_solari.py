"""
run_solari.py — Sakamoto "solari" 전체 파이프라인

hibari/aqua 와 동일한 workflow + 전체 조합 실험:
  - Musical metrics: frequency, tonnetz, voice_leading
  - Algorithm 1: 3 metrics × N=10 trials
  - Algorithm 2 (DL): FC / LSTM / Transformer × binary + continuous × N=3 seeds
  - 개선 F (continuous) 포함

tie 정규화 적용: N=34 (unique pitch)
"""
import os, sys, json, time, random, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from math import gcd
from functools import reduce
from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
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
from generation import (
    algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml,
)
from eval_metrics import evaluate_generation

MIDI_FILE = "ryuichi-sakamoto-solari.mid"
N_ALGO1 = 10
N_DL = 3          # DL 은 학습이 느리므로 3회
ALPHA = 0.5
RATE_STEP = 0.05
DL_EPOCHS = 60
DL_HIDDEN = 128
DL_LR = 1e-3
DL_BATCH = 32

# ─── 전처리 ──────────────────────────────────────────────────────────

def preprocess():
    print("=" * 68)
    print("  Preprocess solari")
    print("=" * 68)
    adj, tempo, bounds = load_and_quantize(MIDI_FILE)
    # solari 는 5 instruments → bounds 에서 첫 악기 경계만 사용
    inst1_raw, inst2_raw = split_instruments(adj, bounds[0])
    print(f"  tempo={tempo:.1f} BPM")
    print(f"  inst1 raw: {len(inst1_raw)}, inst2 raw: {len(inst2_raw)}")

    # tie 정규화
    durs1 = [e-s for s,_,e in inst1_raw if e>s]
    durs2 = [e-s for s,_,e in inst2_raw if e>s]
    g = reduce(gcd, durs1 + durs2) if (durs1+durs2) else 1
    inst1 = [(s, p, s+g) for s, p, e in inst1_raw]
    inst2 = [(s, p, s+g) for s, p, e in inst2_raw]
    print(f"  tie GCD={g}, unique (p,d) before={len(set((p,e-s) for s,p,e in inst1_raw+inst2_raw))}"
          f" → after={len(set((p,e-s) for s,p,e in inst1+inst2))}")

    # 통합 chord map
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

    sp = min(32, max(1, len(cs1)//8))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=sp, max_lag=4)
    T = max(e for _,_,e in adj) if adj else 0

    print(f"  N={N}, C={nc}, T={T}, sp={sp}")

    return {
        'inst1': inst1, 'inst2': inst2,
        'inst1_raw': inst1_raw, 'inst2_raw': inst2_raw,
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'N': N, 'num_chords': nc, 'T': T, 'tempo': tempo,
    }

# ─── PH + overlap ────────────────────────────────────────────────────

def compute_ph(data, metric, alpha=ALPHA):
    adn_i = data['adn_i']; nd = data['notes_dict']
    nl = data['notes_label']; N = data['N']; T = data['T']; nc = data['num_chords']

    m_dist = (None if metric == 'frequency'
              else compute_note_distance_matrix(nl, metric=metric))

    w1 = compute_intra_weights(adn_i[1][0], num_chords=nc)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=nc)
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], num_chords=nc, lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    profile = []; rate = 0.0; t0 = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        fd = compute_distance_matrix(tw, nd, oor, num_notes=N).values
        final = compute_hybrid_distance(fd, m_dist, alpha=alpha) if m_dist is not None else fd
        bd = generate_barcode_numpy(mat=final, listOfDimension=[1],
                                    exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd)); rate += RATE_STEP
    print(f"    PH sweep: {len(profile)} steps, {time.time()-t0:.1f}s", flush=True)

    persistence = group_rBD_by_homology(profile, dim=1)
    cl = label_cycles_from_persistence(persistence)
    if not cl: return None, None

    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    ns = simul_union_by_dict(cp, nd)
    nodes = list(range(1, N+1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(ns))):
        if ns[t]:
            for n in ns[t]:
                if n in nodes: ntd[t, nodes.index(n)] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)
    act = build_activation_matrix(ntd_df, cl)
    ov = build_overlap_matrix(act, cl, threshold=0.35, total_length=T)
    return cl, ov.values

# ─── Algorithm 1 ─────────────────────────────────────────────────────

def run_a1(data, ov, cl, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(data['notes_label'], data['notes_counts'], num_modules=65)
    mgr = CycleSetManager(cl)
    hp = [4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3,4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3]
    T = len(ov); h = (hp * (T//32+1))[:T]
    t0 = time.time()
    gen = algorithm1_optimized(pool, h, ov, mgr, max_resample=50)
    return gen, time.time()-t0

def ev(data, gen):
    m = evaluate_generation(gen, [data['inst1'], data['inst2']],
                            data['notes_label'], name="")
    return {'js': float(m['js_divergence']), 'cov': float(m['note_coverage']),
            'n': len(gen)}

# ─── Algorithm 2 (DL) ────────────────────────────────────────────────

def run_a2(data, ov_values, cl, metric_name, input_type='binary'):
    """FC / LSTM / Transformer 학습 + 생성."""
    try:
        import torch
        from generation import (
            prepare_training_data, MusicGeneratorFC, MusicGeneratorLSTM,
            MusicGeneratorTransformer, train_model, generate_from_model,
        )
    except ImportError as e:
        return {'error': str(e)}

    nl = data['notes_label']; N = data['N']; T = data['T']

    # continuous activation 만들기
    if input_type == 'continuous':
        cp = simul_chord_lists(data['adn_i'][1][-1], data['adn_i'][2][-1])
        ns = simul_union_by_dict(cp, data['notes_dict'])
        nodes = list(range(1, N+1))
        ntd = np.zeros((T, N), dtype=int)
        for t in range(min(T, len(ns))):
            if ns[t]:
                for n in ns[t]:
                    if n in nodes: ntd[t, nodes.index(n)] = 1
        ntd_df = pd.DataFrame(ntd, columns=nodes)
        act_cont = build_activation_matrix(ntd_df, cl, continuous=True)
        X = act_cont.values.astype(np.float32)
    else:
        X = ov_values.astype(np.float32)

    _, y = prepare_training_data(X, [data['inst1'], data['inst2']], nl, T, N)
    K = X.shape[1]

    np.random.seed(0)
    idx = np.random.permutation(len(X))
    sp = int(len(X)*0.7)
    Xtr, ytr = X[idx[:sp]], y[idx[:sp]]
    Xva, yva = X[idx[sp:]], y[idx[sp:]]

    results = {}
    for mtype in ['fc', 'lstm', 'transformer']:
        trials = []
        for si in range(N_DL):
            seed = 8200 + si * 7
            random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)

            if mtype == 'fc':
                model = MusicGeneratorFC(K, N, hidden_dim=DL_HIDDEN, dropout=0.3)
            elif mtype == 'lstm':
                model = MusicGeneratorLSTM(K, N, hidden_dim=DL_HIDDEN, num_layers=2, dropout=0.3)
            else:
                model = MusicGeneratorTransformer(K, N, d_model=DL_HIDDEN, nhead=4,
                                                   num_layers=2, dropout=0.1, max_len=T)

            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                hist = train_model(model, Xtr, ytr, Xva, yva,
                                   epochs=DL_EPOCHS, lr=DL_LR, batch_size=DL_BATCH,
                                   model_type=mtype, seq_len=T)
            val = hist[-1]['val_loss']
            gen = generate_from_model(model, X, nl, model_type=mtype, adaptive_threshold=True)
            m = evaluate_generation(gen, [data['inst1'], data['inst2']], nl, name="")
            trials.append({'seed': seed, 'val': float(val),
                           'js': float(m['js_divergence']),
                           'cov': float(m['note_coverage']), 'n': len(gen)})
            print(f"      {mtype:12s} seed={seed}  val={val:.4f}  "
                  f"JS={m['js_divergence']:.4f}  cov={m['note_coverage']:.2f}", flush=True)

        js_arr = np.array([t['js'] for t in trials])
        results[mtype] = {
            'js_mean': float(js_arr.mean()), 'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()), 'val_mean': float(np.mean([t['val'] for t in trials])),
        }
    return results

# ─── Main ─────────────────────────────────────────────────────────────

def main():
    data = preprocess()
    all_results = {'N': data['N'], 'T': data['T'], 'num_chords': data['num_chords'],
                   'tempo': data['tempo']}
    best = {'js': 1.0}

    # ── Algorithm 1: 3 metrics × N=10 ──
    print("\n" + "=" * 68)
    print("  Algorithm 1 — frequency / tonnetz / voice_leading")
    print("=" * 68)
    for metric in ['frequency', 'tonnetz', 'voice_leading']:
        print(f"\n  [{metric}]")
        try:
            cl, ov = compute_ph(data, metric)
        except Exception as e:
            print(f"    FAIL: {e}"); all_results[f'a1_{metric}'] = {'error': str(e)}; continue
        if cl is None:
            all_results[f'a1_{metric}'] = {'error': 'no cycles'}; continue
        n_cyc = len(cl)
        print(f"    cycles={n_cyc}, overlap {ov.shape}, density={(ov>0).mean():.3f}")

        trials = []
        for i in range(N_ALGO1):
            gen, el = run_a1(data, ov, cl, seed=9600+i)
            e = ev(data, gen)
            trials.append(e)
            if e['js'] < best['js']:
                best = {'js': e['js'], 'metric': metric, 'algo': 'a1',
                        'seed': 9600+i, 'gen': gen}
        js_arr = np.array([t['js'] for t in trials])
        r = {'n_cycles': n_cyc, 'density': float((ov>0).mean()),
             'js_mean': float(js_arr.mean()), 'js_std': float(js_arr.std(ddof=1)),
             'js_min': float(js_arr.min()), 'cov_mean': float(np.mean([t['cov'] for t in trials]))}
        all_results[f'a1_{metric}'] = r
        print(f"    → JS = {r['js_mean']:.4f} ± {r['js_std']:.4f}  (best {r['js_min']:.4f})")

        # 이 metric 의 overlap 을 DL 에서도 사용 → tonnetz 로 고정
        if metric == 'tonnetz':
            tonnetz_cl, tonnetz_ov = cl, ov

    # ── Algorithm 2 (DL): binary + continuous ──
    if 'tonnetz_cl' in dir() or 'tonnetz_cl' in locals():
        print("\n" + "=" * 68)
        print("  Algorithm 2 (DL) — Tonnetz overlap, FC / LSTM / Transformer")
        print("=" * 68)

        for inp in ['binary', 'continuous']:
            print(f"\n  [{inp} input]")
            r = run_a2(data, tonnetz_ov, tonnetz_cl, 'tonnetz', input_type=inp)
            if 'error' in r:
                all_results[f'a2_{inp}'] = r; continue
            all_results[f'a2_{inp}'] = r
            for mt, v in r.items():
                print(f"    {mt:12s}: JS = {v['js_mean']:.4f} ± {v['js_std']:.4f}  "
                      f"(best {v['js_min']:.4f})")

    # ── 요약 ──
    print("\n" + "=" * 68)
    print("  요약 — solari (N=34, T=224)")
    print("=" * 68)
    for k, v in all_results.items():
        if k in ('N','T','num_chords','tempo'): continue
        if isinstance(v, dict) and 'js_mean' in v:
            print(f"  {k:25s}: JS = {v['js_mean']:.4f} ± {v.get('js_std',0):.4f}")
        elif isinstance(v, dict):
            for mk, mv in v.items():
                if isinstance(mv, dict) and 'js_mean' in mv:
                    print(f"  {k:25s} {mk:12s}: JS = {mv['js_mean']:.4f} ± {mv.get('js_std',0):.4f}")

    # best trial 저장
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if best.get('gen'):
        fname = f"solari_best_{best['algo']}_{best['metric']}_s{best['seed']}_{ts}"
        notes_to_xml([best['gen']], tempo_bpm=int(round(data['tempo'])),
                     file_name=fname, output_dir="./output")
        print(f"\n  Best: output/{fname}.musicxml  (JS={best['js']:.4f})")

    # JSON
    od = 'docs/step3_data'; os.makedirs(od, exist_ok=True)
    lite = {k: (v if not isinstance(v, dict) or 'gen' not in v
                else {kk: vv for kk, vv in v.items() if kk != 'gen'})
            for k, v in all_results.items()}
    with open(f'{od}/solari_results.json', 'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {od}/solari_results.json")


if __name__ == '__main__':
    main()
