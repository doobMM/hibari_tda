"""
run_module_generation_unified.py — §7.1 모듈 단위 생성 통합 실험 러너

기존 4개 파일을 통합:
  run_module_generation.py     → --mode baseline
  run_module_generation_v2.py  → --mode prototype_comparison
  run_module_generation_v3.py  → --mode improvements
  run_module_generation_v4.py  → --mode startmodule_study

사용법:
  python run_module_generation_unified.py --mode baseline
  python run_module_generation_unified.py --mode prototype_comparison
  python run_module_generation_unified.py --mode improvements
  python run_module_generation_unified.py --mode startmodule_study
"""
import os, sys, json, time, random, pickle, datetime, argparse
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml
from eval_metrics import evaluate_generation

# ═══════════════════════════════════════════════════════════════════════
# 공통 상수 + 헬퍼
# ═══════════════════════════════════════════════════════════════════════

MODULE_LEN = 32
N_INST1_COPIES = 33
N_INST2_COPIES = 32
INST2_INIT_OFFSET = 33
MODULE_HEIGHTS = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                  4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
COVERAGE_TARGET = 20


def replicate_inst1(mod):
    out = []
    for m in range(N_INST1_COPIES):
        off = m * MODULE_LEN
        for s, p, e in mod:
            ns = s + off
            ne = min(e + off, off + MODULE_LEN)
            if ns < off + MODULE_LEN and ne > ns:
                out.append((ns, p, ne))
    return out


def replicate_inst2(mod):
    out = []
    period = MODULE_LEN + 1
    for m in range(N_INST2_COPIES):
        cs = INST2_INIT_OFFSET + m * period
        for s, p, e in mod:
            ns = s + cs
            ne = min(e + cs, cs + MODULE_LEN)
            if ns < cs + MODULE_LEN and ne > ns:
                out.append((ns, p, ne))
    return out


def run_algo1_module(p, overlap_proto, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    return algorithm1_optimized(
        pool, list(MODULE_HEIGHTS), overlap_proto, manager,
        max_resample=50, verbose=False)


def module_coverage(module_notes, notes_label):
    used = set()
    for s, p, e in module_notes:
        key = (p, e - s)
        if key in notes_label:
            used.add(notes_label[key])
    return len(used)


def eval_full(p, module_notes, keep_gen=False):
    all_gen = replicate_inst1(module_notes) + replicate_inst2(module_notes)
    metrics = evaluate_generation(
        all_gen,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        p._cache['notes_label'], name="")
    result = {
        'js': float(metrics['js_divergence']),
        'coverage': float(metrics['note_coverage']),
        'n_notes': int(len(all_gen)),
        'mod_n_notes': int(len(module_notes)),
    }
    if keep_gen:
        result['all_gen'] = all_gen
    return result


def load_tonnetz_cache():
    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    return cache['overlap'].values, cache['cycle_labeled']


def save_json(data, filename):
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {path}")


# ═══════════════════════════════════════════════════════════════════════
# Prototype 전략 생성 함수
# ═══════════════════════════════════════════════════════════════════════

def make_P0_or(overlap_full):
    usable = overlap_full[:N_INST1_COPIES * MODULE_LEN].reshape(
        N_INST1_COPIES, MODULE_LEN, -1)
    return usable.max(axis=0).astype(np.float32)


def make_P1(overlap_full, tau=0.5):
    usable = overlap_full[:N_INST1_COPIES * MODULE_LEN].reshape(
        N_INST1_COPIES, MODULE_LEN, -1).astype(float)
    return (usable.mean(axis=0) >= tau).astype(np.float32)


def make_P2_cont(overlap_full):
    usable = overlap_full[:N_INST1_COPIES * MODULE_LEN].reshape(
        N_INST1_COPIES, MODULE_LEN, -1).astype(float)
    return usable.mean(axis=0).astype(np.float32)


def make_P3_median(overlap_full):
    usable = overlap_full[:N_INST1_COPIES * MODULE_LEN].reshape(
        N_INST1_COPIES, MODULE_LEN, -1)
    counts = usable.sum(axis=(1, 2))
    sorted_idx = np.argsort(counts)
    median_idx = sorted_idx[len(sorted_idx) // 2]
    print(f"    P3: counts min={counts.min()}, median={counts[median_idx]}, "
          f"max={counts.max()}, chosen module={median_idx}")
    return usable[median_idx].astype(np.float32)


def make_P5_flat(overlap_full):
    rates = overlap_full[:N_INST1_COPIES * MODULE_LEN].mean(axis=0)
    proto = np.tile(rates, (MODULE_LEN, 1)).astype(np.float32)
    return (proto >= 0.5).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════
# 개선 전략 (C, D, P4)
# ═══════════════════════════════════════════════════════════════════════

def gen_with_best_of_k(p, overlap_proto, cycle_labeled, base_seed, k=10):
    notes_label = p._cache['notes_label']
    candidates = []
    for j in range(k):
        mod = run_algo1_module(p, overlap_proto, cycle_labeled,
                               seed=base_seed * 1000 + j)
        cov = module_coverage(mod, notes_label)
        candidates.append((cov, j, mod))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    best_cov, best_j, best_mod = candidates[0]
    return best_mod, best_cov, best_j


def gen_with_coverage_constraint(p, overlap_proto, cycle_labeled,
                                 base_seed, target=COVERAGE_TARGET,
                                 max_attempts=30):
    notes_label = p._cache['notes_label']
    best_mod, best_cov = None, -1
    for j in range(max_attempts):
        mod = run_algo1_module(p, overlap_proto, cycle_labeled,
                               seed=base_seed * 1000 + j)
        cov = module_coverage(mod, notes_label)
        if cov > best_cov:
            best_cov = cov; best_mod = mod
        if cov >= target:
            return best_mod, best_cov, j + 1
    return best_mod, best_cov, max_attempts


def compute_module_local_ph(p, start_module=0, alpha=0.5):
    """Module-local PH 계산. start_module로 시작 위치 선택."""
    from preprocessing import group_notes_with_duration, build_chord_labels
    from weights import (compute_intra_weights, compute_inter_weights,
                         compute_distance_matrix, compute_out_of_reach)
    from overlap import (group_rBD_by_homology, label_cycles_from_persistence,
                         build_activation_matrix)
    from topology import generate_barcode_numpy
    from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance

    notes_label = p._cache['notes_label']
    notes_dict = p._cache['notes_dict']
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    N = len(notes_label)

    t1_lo = start_module * MODULE_LEN
    t1_hi = t1_lo + MODULE_LEN
    t2_lo = t1_lo + INST2_INIT_OFFSET
    t2_hi = min(t2_lo + MODULE_LEN, 1088)

    inst1_mod = [(s, pp, e) for (s, pp, e) in inst1 if t1_lo <= s < t1_hi]
    inst2_mod = [(s, pp, e) for (s, pp, e) in inst2 if t2_lo <= s < t2_hi]

    # v4: 전체 chord_seq 슬라이싱 (호환성 유지)
    if hasattr(p, '_cache') and 'chord_seq1' in p._cache:
        cs1 = p._cache['chord_seq1'][t1_lo:t1_hi]
        cs2 = p._cache['chord_seq2'][t2_lo:t2_hi]
    else:
        # v3 fallback: 모듈 내 chord seq 재계산
        active1 = group_notes_with_duration(inst1_mod)
        active2 = group_notes_with_duration(inst2_mod)
        _, cs1 = build_chord_labels(active1)
        _, cs2 = build_chord_labels(active2)

    n1 = sum(1 for c in cs1 if c is not None)
    n2 = sum(1 for c in cs2 if c is not None)
    if n1 < 2 or n2 < 2:
        return None, None, 0

    w1 = compute_intra_weights(cs1, num_chords=17)
    w2 = compute_intra_weights(cs2, num_chords=17)
    intra = w1 + w2

    L = min(len(cs1), len(cs2))
    if L > 1:
        inter = compute_inter_weights(cs1[:L], cs2[:L], num_chords=17, lag=1)
    else:
        inter = pd.DataFrame(np.zeros((17, 17), dtype=int))
    oor = compute_out_of_reach(inter, power=-2)
    m_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    profile = []
    for r in [0.0, 0.5, 1.0]:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd))

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled_local = label_cycles_from_persistence(persistence)
    n_cycles = len(cycle_labeled_local)
    if n_cycles == 0:
        return None, None, 0

    # 활성화 행렬
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((MODULE_LEN, N), dtype=int)
    for s, pp, e in inst1_mod + inst2_mod:
        d = e - s
        if (pp, d) in notes_label:
            lbl = notes_label[(pp, d)]
            if s >= t2_lo:
                t_start = s - t2_lo
            else:
                t_start = s - t1_lo
            t_end = min(t_start + d, MODULE_LEN)
            for t in range(max(0, t_start), max(0, t_end)):
                if 0 <= t < MODULE_LEN:
                    ntd[t, lbl - 1] = 1

    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled_local)
    overlap_proto = activation.values.astype(np.float32)
    return cycle_labeled_local, overlap_proto, n_cycles


# ═══════════════════════════════════════════════════════════════════════
# Mode: baseline (v1) — P1 prototype, N=10, JSON + best MusicXML
# ═══════════════════════════════════════════════════════════════════════

def mode_baseline(args):
    print("=" * 64)
    print("  §7.1 모듈 단위 생성 + 구조적 재배치 (baseline)")
    print("=" * 64)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    overlap_full, cycle_labeled = load_tonnetz_cache()
    K = len(cycle_labeled)
    print(f"\n  Tonnetz: {K} cycles, overlap shape {overlap_full.shape}")

    proto = make_P1(overlap_full)
    print(f"  P1 density: {(proto > 0).mean():.3f}")

    n_repeats = args.n_repeats
    trials = []
    best_trial = None

    for i in range(n_repeats):
        mod = run_algo1_module(p, proto, cycle_labeled, seed=7100 + i)
        t0 = time.time()
        ev = eval_full(p, mod, keep_gen=True)
        elapsed = time.time() - t0
        trial = {'seed': 7100 + i, **ev, 'elapsed_s': elapsed}
        trials.append(trial)
        print(f"  [{i+1:2d}] JS={ev['js']:.4f}  cov={ev['coverage']:.2f}  "
              f"notes={ev['n_notes']}")
        if best_trial is None or ev['js'] < best_trial['js']:
            best_trial = trial

    # 통계
    js_arr = np.array([t['js'] for t in trials])
    summary = {
        'n_repeats': n_repeats,
        'js_divergence': {'mean': float(js_arr.mean()),
                          'std': float(js_arr.std(ddof=1)),
                          'min': float(js_arr.min()),
                          'max': float(js_arr.max())},
        'best_seed': best_trial['seed'],
        'best_js': best_trial['js'],
    }
    print(f"\n  JS = {js_arr.mean():.4f} +/- {js_arr.std(ddof=1):.4f}")

    trials_lite = [{k: v for k, v in t.items() if k != 'all_gen'}
                   for t in trials]
    save_json({'summary': summary, 'trials': trials_lite},
              'step71_module_results.json')

    # Best MusicXML
    os.makedirs('output', exist_ok=True)
    notes_to_xml([best_trial['all_gen']], tempo_bpm=66,
                 file_name=f"step71_module_best_seed{best_trial['seed']}",
                 output_dir="./output")


# ═══════════════════════════════════════════════════════════════════════
# Mode: prototype_comparison (v2) — P0/P1/P2/P3/P5 비교
# ═══════════════════════════════════════════════════════════════════════

def mode_prototype_comparison(args):
    print("=" * 64)
    print("  §7.1 v2 — Prototype 전략 비교")
    print("=" * 64)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    overlap_full, cycle_labeled = load_tonnetz_cache()
    print(f"\n  Tonnetz: {len(cycle_labeled)} cycles, {overlap_full.shape}")

    n_repeats = args.n_repeats
    protos = [
        ('P0 — OR over 33',      make_P0_or(overlap_full)),
        ('P1 — mean → τ=0.5',    make_P1(overlap_full)),
        ('P2 — mean continuous',  make_P2_cont(overlap_full)),
        ('P3 — median module',    make_P3_median(overlap_full)),
        ('P5 — flat cycle rate',  make_P5_flat(overlap_full)),
    ]

    results = {}
    for name, ov_proto in protos:
        dens = float((ov_proto > 0).mean())
        print(f"\n  [{name}] density={dens:.3f}")
        trials = []
        for i in range(n_repeats):
            mod = run_algo1_module(p, ov_proto, cycle_labeled, seed=7200 + i)
            ev = eval_full(p, mod)
            trials.append(ev)
        js_arr = np.array([t['js'] for t in trials])
        results[name] = {
            'density': dens,
            'js_mean': float(js_arr.mean()),
            'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()),
            'js_max': float(js_arr.max()),
            'cov_mean': float(np.mean([t['coverage'] for t in trials])),
        }

    # 요약
    print(f"\n{'='*64}\n  요약 (N={n_repeats})\n{'='*64}")
    for name, r in results.items():
        print(f"  {name:28s} dens={r['density']:.3f}  "
              f"JS={r['js_mean']:.4f}±{r['js_std']:.4f}  "
              f"best={r['js_min']:.4f}  cov={r['cov_mean']:.3f}")

    results['n_repeats'] = n_repeats
    results['baseline_full_song_tonnetz'] = {'js_mean': 0.0398, 'js_std': 0.0031}
    save_json(results, 'step71_prototype_comparison.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: improvements (v3) — C / D / P4 / P4+C
# ═══════════════════════════════════════════════════════════════════════

def mode_improvements(args):
    print("=" * 64)
    print("  §7.1 v3 — 한계 해결: 개선 C / D / P4")
    print("=" * 64)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    overlap_full, cycle_labeled = load_tonnetz_cache()

    proto_P1 = make_P1(overlap_full)
    print(f"\n  Tonnetz: {len(cycle_labeled)} cycles")
    print(f"  P1 prototype density: {(proto_P1 > 0).mean():.3f}")

    base_seeds = list(range(7300, 7300 + args.n_repeats))
    results = {}

    def run_strategy(name, gen_fn):
        print(f"\n[{name}]")
        trials = []
        for i, seed in enumerate(base_seeds):
            t0 = time.time()
            result = gen_fn(seed)
            elapsed = time.time() - t0
            if result is None or result[0] is None:
                print(f"  [{i+1:2d}] FAIL"); continue
            mod, extra = result
            ev = eval_full(p, mod)
            ev.update({'elapsed_ms': elapsed * 1000, 'seed': seed, **extra})
            trials.append(ev)
            print(f"  [{i+1:2d}] JS={ev['js']:.4f}  cov={ev['coverage']:.2f}")
        js_arr = np.array([t['js'] for t in trials])
        return {
            'js_mean': float(js_arr.mean()), 'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()), 'js_max': float(js_arr.max()),
            'cov_mean': float(np.mean([t['coverage'] for t in trials])),
            'mod_cov_mean': float(np.mean([t.get('module_coverage', 0)
                                           for t in trials])),
        }

    # Baseline P1
    results['Baseline P1'] = run_strategy('Baseline P1', lambda s: (
        run_algo1_module(p, proto_P1, cycle_labeled, seed=s),
        {'module_coverage': module_coverage(
            run_algo1_module(p, proto_P1, cycle_labeled, seed=s),
            p._cache['notes_label'])}
    ))

    # C: best-of-k
    def gen_C(seed):
        mod, cov, best_j = gen_with_best_of_k(
            p, proto_P1, cycle_labeled, base_seed=seed, k=10)
        return mod, {'module_coverage': cov, 'best_j': best_j}
    results['C: best-of-10'] = run_strategy('C: best-of-k=10', gen_C)

    # D: coverage constraint
    def gen_D(seed):
        mod, cov, attempts = gen_with_coverage_constraint(
            p, proto_P1, cycle_labeled, base_seed=seed)
        return mod, {'module_coverage': cov, 'attempts': attempts}
    results['D: cov>=20/23'] = run_strategy('D: coverage >= 20/23', gen_D)

    # C+D
    def gen_CD(seed):
        nl = p._cache['notes_label']
        cands = []
        for j in range(10):
            mod = run_algo1_module(p, proto_P1, cycle_labeled, seed=seed * 1000 + j)
            cov = module_coverage(mod, nl)
            cands.append((cov, j, mod))
        cands.sort(key=lambda x: (-x[0], x[1]))
        return cands[0][2], {'module_coverage': cands[0][0],
                             'over_target': int(cands[0][0] >= COVERAGE_TARGET)}
    results['C+D combined'] = run_strategy('C+D combined', gen_CD)

    # P4: module-local PH
    print("\n  P4 module-local PH 계산 중...")
    cycle_local, proto_P4, n_cyc = compute_module_local_ph(p)
    if cycle_local is not None and proto_P4 is not None:
        print(f"  P4 prototype density: {(proto_P4 > 0).mean():.3f}")

        results['P4: module-local PH'] = run_strategy('P4: module-local PH',
            lambda s: (run_algo1_module(p, proto_P4, cycle_local, seed=s),
                       {'module_coverage': module_coverage(
                           run_algo1_module(p, proto_P4, cycle_local, seed=s),
                           p._cache['notes_label'])}))

        # P4+C
        def gen_P4C(seed):
            nl = p._cache['notes_label']
            cands = []
            for j in range(10):
                mod = run_algo1_module(p, proto_P4, cycle_local,
                                       seed=seed * 1000 + j)
                cov = module_coverage(mod, nl)
                cands.append((cov, j, mod))
            cands.sort(key=lambda x: (-x[0], x[1]))
            return cands[0][2], {'module_coverage': cands[0][0]}
        results['P4 + C (best-of-10)'] = run_strategy('P4+C', gen_P4C)

    # 요약
    print(f"\n{'='*70}\n  요약 (N={args.n_repeats})\n{'='*70}")
    for name, r in results.items():
        print(f"  {name:28s}  JS={r['js_mean']:.4f}±{r['js_std']:.4f}  "
              f"best={r['js_min']:.4f}  cov={r['cov_mean']:.3f}")

    lite = {k: v for k, v in results.items()}
    lite['n_repeats'] = args.n_repeats
    lite['baseline_full_song'] = {'js_mean': 0.0398, 'js_std': 0.0031}
    save_json(lite, 'step71_improvements.json')


# ═══════════════════════════════════════════════════════════════════════
# Mode: startmodule_study (v4) — P4 시작 모듈 스윕
# ═══════════════════════════════════════════════════════════════════════

def mode_startmodule_study(args):
    print("=" * 72)
    print("  §7.1 v4 — 시작 모듈 선택 정당성 검증")
    print("=" * 72)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    start_modules = [0, 4, 8, 12, 16, 20, 24, 28]
    base_seeds = list(range(9300, 9300 + args.n_repeats))
    k_best = 10

    results = {}
    best_global = {'js': 1.0, 'info': None, 'all_gen': None}

    for sm in start_modules:
        print(f"\n[start_module = {sm}]  t in [{sm*32}, {(sm+1)*32})")
        cycle_local, proto, n_cyc = compute_module_local_ph(p, start_module=sm)
        if cycle_local is None:
            print("  PH empty, skip"); continue
        print(f"  cycles: {n_cyc}, density: {(proto>0).mean():.3f}")

        trials_js, trials_cov = [], []
        for seed in base_seeds:
            nl = p._cache['notes_label']
            cands = []
            for j in range(k_best):
                mod = run_algo1_module(p, proto, cycle_local,
                                       seed=seed * 1000 + j)
                cov = module_coverage(mod, nl)
                cands.append((cov, j, mod))
            cands.sort(key=lambda x: (-x[0], x[1]))
            best_mod = cands[0][2]
            ev = eval_full(p, best_mod, keep_gen=True)
            trials_js.append(ev['js'])
            trials_cov.append(ev['coverage'])
            if ev['js'] < best_global['js']:
                best_global = {'js': ev['js'],
                               'info': {'start_module': sm, 'seed': seed,
                                        'n_notes': ev['n_notes']},
                               'all_gen': ev['all_gen']}

        js_arr = np.array(trials_js)
        results[f'start_{sm:02d}'] = {
            'start_module': sm, 'n_cycles': n_cyc,
            'prototype_density': float((proto > 0).mean()),
            'js_mean': float(js_arr.mean()),
            'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()),
            'js_max': float(js_arr.max()),
            'cov_mean': float(np.mean(trials_cov)),
        }
        print(f"  JS = {js_arr.mean():.4f} +/- {js_arr.std(ddof=1):.4f}")

    # 요약
    print(f"\n{'='*72}\n  요약 — P4+C across start modules\n{'='*72}")
    for _, r in results.items():
        print(f"  start={r['start_module']:>2d}  cyc={r['n_cycles']:>3d}  "
              f"JS={r['js_mean']:.4f}±{r['js_std']:.4f}  "
              f"best={r['js_min']:.4f}")

    all_js = [r['js_mean'] for r in results.values()]
    print(f"\n  Across-module mean JS: {np.mean(all_js):.4f}")
    print(f"  Best global: {best_global['info']}, JS={best_global['js']:.4f}")

    # Best MusicXML
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    info = best_global['info']
    fname = f"step71_v4_best_m{info['start_module']:02d}_s{info['seed']}_{ts}"
    os.makedirs('output', exist_ok=True)
    notes_to_xml([best_global['all_gen']], tempo_bpm=66,
                 file_name=fname, output_dir="./output")
    print(f"\n  MusicXML: output/{fname}.musicxml")

    save_json({
        'n_repeats': args.n_repeats, 'k_best': k_best,
        'start_modules': start_modules, 'results': results,
        'best_global': {'js': best_global['js'], 'info': best_global['info']},
    }, 'step71_startmodule_study.json')


# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="§7.1 모듈 단위 생성 통합 러너")
    parser.add_argument('--mode', required=True,
                        choices=['baseline', 'prototype_comparison',
                                 'improvements', 'startmodule_study'])
    parser.add_argument('--n-repeats', dest='n_repeats', type=int, default=10)
    args = parser.parse_args()

    dispatch = {
        'baseline': mode_baseline,
        'prototype_comparison': mode_prototype_comparison,
        'improvements': mode_improvements,
        'startmodule_study': mode_startmodule_study,
    }
    dispatch[args.mode](args)


if __name__ == '__main__':
    main()
