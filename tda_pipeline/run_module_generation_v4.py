"""
run_module_generation_v4.py — P4 시작 모듈 선택 정당성 검증 + best MusicXML 출력

두 가지 목적:
 (A) P4 (module-local PH) 에서 "첫 모듈" 선택의 정당성:
     8개의 다른 시작 모듈 (0, 4, 8, 12, 16, 20, 24, 28) 각각에 대해
     module-local PH를 계산하고, 같은 seed 그룹에서 P4+C 성능을 측정한다.
     이를 통해 "어느 모듈로 시작해도 비슷한 결과를 내는가?" 또는
     "특정 모듈이 압도적으로 좋거나 나쁜가?" 를 확인.

 (B) Best trial MusicXML + piano WAV 저장:
     전체 실험에서 가장 낮은 JS 를 낸 trial의 MusicXML 생성 + WAV 변환.
"""
import os, sys, json, time, random, pickle, datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import (
    algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml,
)
from eval_metrics import evaluate_generation
from preprocessing import group_notes_with_duration, build_chord_labels
from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_distance_matrix, compute_out_of_reach,
)
from overlap import (
    group_rBD_by_homology, label_cycles_from_persistence,
    build_activation_matrix,
)
from topology import generate_barcode_numpy
from musical_metrics import (
    compute_note_distance_matrix, compute_hybrid_distance,
)

MODULE_LEN = 32
N_INST1_COPIES = 33
N_INST2_COPIES = 32
INST2_INIT_OFFSET = 33
N_REPEATS = 10
K_BEST = 10


# ─── replication helpers ──────────────────────────────────────────────

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


def module_coverage(module_notes, notes_label):
    used = set()
    for s, p, e in module_notes:
        key = (p, e - s)
        if key in notes_label:
            used.add(notes_label[key])
    return len(used)


def run_algo1_module(p, overlap_proto, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    heights = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    return algorithm1_optimized(
        pool, list(heights), overlap_proto, manager,
        max_resample=50, verbose=False)


def eval_full(p, module_notes):
    all_gen = replicate_inst1(module_notes) + replicate_inst2(module_notes)
    metrics = evaluate_generation(
        all_gen,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        p._cache['notes_label'], name="")
    return {
        'js': float(metrics['js_divergence']),
        'coverage': float(metrics['note_coverage']),
        'n_notes': int(len(all_gen)),
        'all_gen': all_gen,
    }


# ─── P4: module-local PH, 다양한 시작 모듈 지원 ───────────────────────

def compute_module_local_ph(p, start_module=0, alpha=0.5):
    """
    시작 모듈 인덱스 start_module 에 해당하는 구간의 chord transition
    만 사용하여 module-local PH를 계산.

    핵심 전략: build_chord_labels 를 재호출하지 않고, 전체 곡에서 이미
    계산된 chord_seq1 / chord_seq2 를 그대로 잘라 쓴다. 이렇게 하면
    notes_dict 와의 호환성이 유지된다 (chord label 체계가 동일).
    """
    notes_label = p._cache['notes_label']
    notes_dict = p._cache['notes_dict']
    chord_seq1_full = p._cache['chord_seq1']
    chord_seq2_full = p._cache['chord_seq2']
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    N = len(notes_label)

    t1_lo = start_module * MODULE_LEN
    t1_hi = t1_lo + MODULE_LEN
    t2_lo = t1_lo + INST2_INIT_OFFSET
    t2_hi = min(t2_lo + MODULE_LEN, len(chord_seq2_full))

    # 모듈 구간의 개별 note (activation matrix용)
    inst1_mod = [(s, pp, e) for (s, pp, e) in inst1 if t1_lo <= s < t1_hi]
    inst2_mod = [(s, pp, e) for (s, pp, e) in inst2 if t2_lo <= s < t2_hi]

    # 각 instrument 의 module 구간 chord sequence (weight 계산용)
    cs1 = chord_seq1_full[t1_lo:t1_hi]
    cs2 = chord_seq2_full[t2_lo:t2_hi]

    # None이 아닌 chord가 너무 적으면 PH 계산 불가
    n1_valid = sum(1 for c in cs1 if c is not None)
    n2_valid = sum(1 for c in cs2 if c is not None)
    if n1_valid < 2 or n2_valid < 2:
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

    # 활성화 행렬 — 모듈 한정 note_time matrix 에서
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((MODULE_LEN, N), dtype=int)
    for s, pp, e in inst1_mod + inst2_mod:
        d = e - s
        if (pp, d) in notes_label:
            lbl = notes_label[(pp, d)]
            # 모듈 상대 시점으로 변환
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


def p4_plus_c_one_trial(p, cycle_local, overlap_proto, base_seed, k=K_BEST):
    """P4 + C (best-of-k) 한 trial."""
    notes_label = p._cache['notes_label']
    candidates = []
    for j in range(k):
        mod = run_algo1_module(p, overlap_proto, cycle_local,
                               seed=base_seed * 1000 + j)
        cov = module_coverage(mod, notes_label)
        candidates.append((cov, j, mod))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    best_cov, best_j, best_mod = candidates[0]
    return best_mod, best_cov


def main():
    print("=" * 72)
    print("  §7.1 v4 — 시작 모듈 선택 정당성 검증 + best WAV 출력")
    print("=" * 72)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    start_modules = [0, 4, 8, 12, 16, 20, 24, 28]
    base_seeds = list(range(9300, 9310))

    results = {}
    best_global = {'js': 1.0, 'info': None, 'all_gen': None}

    for sm in start_modules:
        print(f"\n[start_module = {sm}]  t∈[{sm*32}, {(sm+1)*32})")
        cycle_local, proto, n_cyc = compute_module_local_ph(p, start_module=sm)
        if cycle_local is None:
            print("  PH empty, skip")
            continue
        print(f"  module-local cycles: {n_cyc}, prototype density: {(proto>0).mean():.3f}")

        trials_js = []
        trials_cov = []
        for seed in base_seeds:
            mod, mod_cov = p4_plus_c_one_trial(p, cycle_local, proto, seed)
            ev = eval_full(p, mod)
            trials_js.append(ev['js'])
            trials_cov.append(ev['coverage'])
            if ev['js'] < best_global['js']:
                best_global['js'] = ev['js']
                best_global['info'] = {
                    'start_module': sm, 'seed': seed,
                    'mod_coverage': mod_cov,
                    'total_coverage': ev['coverage'],
                    'n_notes': ev['n_notes'],
                }
                best_global['all_gen'] = ev['all_gen']

        js_arr = np.array(trials_js)
        cov_arr = np.array(trials_cov)
        res = {
            'start_module': sm,
            'n_cycles': n_cyc,
            'prototype_density': float((proto > 0).mean()),
            'js_mean': float(js_arr.mean()),
            'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()),
            'js_max': float(js_arr.max()),
            'cov_mean': float(cov_arr.mean()),
        }
        results[f'start_{sm:02d}'] = res
        print(f"  JS = {res['js_mean']:.4f} ± {res['js_std']:.4f}  "
              f"(min {res['js_min']:.4f}, max {res['js_max']:.4f}),  "
              f"cov {res['cov_mean']:.3f}")

    # ── 요약 ──
    print("\n" + "=" * 72)
    print("  요약 — P4+C across different start modules (N=10 each)")
    print("=" * 72)
    print(f"  {'start':>5s}  {'#cyc':>4s}  {'dens':>6s}  {'JS (mean ± std)':22s}  {'best':>7s}  {'cov':>5s}")
    print("  " + "─" * 65)
    for k, r in results.items():
        print(f"  {r['start_module']:>5d}  {r['n_cycles']:>4d}  "
              f"{r['prototype_density']:>6.3f}  "
              f"{r['js_mean']:.4f} ± {r['js_std']:.4f}       "
              f"{r['js_min']:>7.4f}  {r['cov_mean']:>5.3f}")

    # 전체 평균
    all_js = [r['js_mean'] for r in results.values()]
    print(f"\n  Across-module mean JS: {np.mean(all_js):.4f} ± {np.std(all_js, ddof=1):.4f}")
    print(f"  (개별 std 평균과 구분됨 — 이건 '시작 모듈에 따른 변동')")
    print(f"\n  Best global trial:")
    print(f"    {best_global['info']}")
    print(f"    JS = {best_global['js']:.4f}")

    # ── Best trial 을 MusicXML 로 저장 ──
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    info = best_global['info']
    fname = f"step71_v4_best_m{info['start_module']:02d}_s{info['seed']}_{ts}"
    notes_to_xml(
        [best_global['all_gen']],
        tempo_bpm=66,
        file_name=fname,
        output_dir="./output")
    print(f"\n  MusicXML: output/{fname}.musicxml")

    # JSON 저장
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    final = {
        'n_repeats': N_REPEATS,
        'k_best': K_BEST,
        'start_modules': start_modules,
        'results': results,
        'best_global': {
            'js': best_global['js'],
            'info': best_global['info'],
            'musicxml': f'output/{fname}.musicxml',
        },
    }
    with open(os.path.join(out_dir, 'step71_startmodule_study.json'),
              'w', encoding='utf-8') as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {out_dir}/step71_startmodule_study.json")
    return fname


if __name__ == '__main__':
    fname = main()
    print(f"\nDone. Best output base: {fname}")
