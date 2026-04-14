"""
run_module_generation_v3.py — §7.1 한계 해결을 위한 개선 C / D / P4 구현

이전 v2 실험에서 module-level randomness의 33× amplification 이 평균 JS 를
baseline 대비 약 2.8 배로 끌어올린다는 한계가 드러났다. 본 스크립트는 다음
세 가지 개선을 구현하고 baseline (P1) 대비 정량적으로 평가한다.

  C : best-of-k selection
      - k 개 candidate 모듈을 생성한 뒤 internal 품질 지표 (note coverage)
        가 가장 높은 것을 선택
      - 한 번의 random choice 에 대한 sensitivity 를 줄임

  D : note coverage hard constraint
      - 모듈 생성 후 coverage 가 threshold 미만이면 즉시 폐기 후 재생성
      - C 와 다른 점: C 는 k 개 다 만들고 하나 고름, D 는 첫 통과 모듈 사용

  P4 : module-local persistent homology
      - 첫 모듈 (32 timesteps) 의 chord transition 만으로 weight matrix 구축
      - 그 위에서 새로 PH 계산 → 모듈 자체에 내재된 cycle 발견
      - prototype overlap 자체가 필요 없음 (cycle_labeled 가 다름)

기본 비교 baseline:
  P1 (mean → τ=0.5)  :  v2 에서 채택된 selective prototype

각 설정 N=10 trials, JS / coverage / 생성 시간 측정.
결과: docs/step3_data/step71_improvements.json
"""
import os, sys, json, time, random, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation
from preprocessing import (
    group_notes_with_duration, build_chord_labels,
    chord_to_note_labels, prepare_lag_sequences,
)
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
COVERAGE_TARGET = 20  # D: at least 20/23 unique notes per module


# ─── 공통 helper ──────────────────────────────────────────────────────

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
    period = MODULE_LEN + 1  # 1-step rest gap
    for m in range(N_INST2_COPIES):
        cs = INST2_INIT_OFFSET + m * period
        for s, p, e in mod:
            ns = s + cs
            ne = min(e + cs, cs + MODULE_LEN)
            if ns < cs + MODULE_LEN and ne > ns:
                out.append((ns, p, ne))
    return out


def module_coverage(module_notes, notes_label):
    """Module 안에 등장한 unique (pitch, dur) label 수."""
    used = set()
    label_lookup = {(p, d): lbl for (p, d), lbl in notes_label.items()}
    for s, p, e in module_notes:
        d = e - s
        key = (p, d)
        if key in label_lookup:
            used.add(label_lookup[key])
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
    inst1_rep = replicate_inst1(module_notes)
    inst2_rep = replicate_inst2(module_notes)
    all_gen = inst1_rep + inst2_rep
    metrics = evaluate_generation(
        all_gen,
        [p._cache['inst1_real'], p._cache['inst2_real']],
        p._cache['notes_label'], name="")
    return {
        'js': float(metrics['js_divergence']),
        'coverage': float(metrics['note_coverage']),
        'n_notes': int(len(all_gen)),
        'mod_n_notes': int(len(module_notes)),
    }


# ─── P1 prototype (v2 채택안) ─────────────────────────────────────────

def make_P1(overlap_full):
    usable = overlap_full[:N_INST1_COPIES * MODULE_LEN].reshape(
        N_INST1_COPIES, MODULE_LEN, -1).astype(float)
    return (usable.mean(axis=0) >= 0.5).astype(np.float32)


# ─── 개선 C: best-of-k selection ─────────────────────────────────────

def gen_with_best_of_k(p, overlap_proto, cycle_labeled, base_seed, k=10):
    """k 개 candidate 모듈을 만들고, internal coverage 가 가장 높은 것 선택."""
    notes_label = p._cache['notes_label']
    candidates = []
    for j in range(k):
        mod = run_algo1_module(p, overlap_proto, cycle_labeled,
                               seed=base_seed * 1000 + j)
        cov = module_coverage(mod, notes_label)
        candidates.append((cov, j, mod))
    # 최고 coverage; tie-break: 가장 낮은 j (안정성)
    candidates.sort(key=lambda x: (-x[0], x[1]))
    best_cov, best_j, best_mod = candidates[0]
    return best_mod, best_cov, best_j


# ─── 개선 D: coverage hard constraint ────────────────────────────────

def gen_with_coverage_constraint(p, overlap_proto, cycle_labeled,
                                 base_seed, target=COVERAGE_TARGET,
                                 max_attempts=30):
    """Coverage >= target 인 첫 모듈을 사용. 못 찾으면 best 반환."""
    notes_label = p._cache['notes_label']
    best_mod = None
    best_cov = -1
    for j in range(max_attempts):
        mod = run_algo1_module(p, overlap_proto, cycle_labeled,
                               seed=base_seed * 1000 + j)
        cov = module_coverage(mod, notes_label)
        if cov > best_cov:
            best_cov = cov
            best_mod = mod
        if cov >= target:
            return best_mod, best_cov, j + 1
    return best_mod, best_cov, max_attempts


# ─── 개선 P4: module-local persistent homology ────────────────────────

def compute_module_local_ph(p, alpha=0.5, max_lag=4):
    """
    첫 모듈 (32 timesteps) 의 chord transition 데이터로
    persistent homology 를 새로 계산하여 module-local cycle_labeled 반환.

    구현 전략:
      1. inst1_real 에서 t ∈ [0, 32) 에 시작하는 note만 추출
      2. group_notes_with_duration → first-module chord seq
      3. compute_intra_weights 로 module-local intra weight matrix
      4. inter weight 도 inst2 의 첫 32 timesteps 로 동일 계산
      5. distance matrix → topology.generate_barcode_numpy
      6. cycle_labeled 변환

    반환: (cycle_labeled, overlap_proto)
        - cycle_labeled: module-local cycles
        - overlap_proto: 32 × len(cycle_labeled) 활성 행렬 (binary)
    """
    notes_label = p._cache['notes_label']
    notes_dict = p._cache['notes_dict']
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    N = len(notes_label)

    # 1) 첫 모듈에 시작하는 note만 추출
    inst1_mod = [(s, pp, e) for (s, pp, e) in inst1 if 0 <= s < MODULE_LEN]
    inst2_mod = [(s, pp, e) for (s, pp, e) in inst2
                 if INST2_INIT_OFFSET <= s < INST2_INIT_OFFSET + MODULE_LEN]
    print(f"    P4: inst1 module notes = {len(inst1_mod)}, "
          f"inst2 module notes = {len(inst2_mod)}")

    # 2) 모듈 내 chord seq
    active1 = group_notes_with_duration(inst1_mod)
    active2 = group_notes_with_duration(inst2_mod)
    cm1, cs1 = build_chord_labels(active1)
    cm2, cs2 = build_chord_labels(active2)

    # 3) intra weight (모듈 한정)
    w1 = compute_intra_weights(cs1, num_chords=17)
    w2 = compute_intra_weights(cs2, num_chords=17)
    intra = w1 + w2

    # 4) inter weight (모듈 한정, lag=1) — prepare_lag_sequences 우회
    # 두 sequence 길이를 같게 맞춘 뒤 직접 호출
    L = min(len(cs1), len(cs2))
    if L > 1:
        cs1_t = cs1[:L]
        cs2_t = cs2[:L]
        inter = compute_inter_weights(cs1_t, cs2_t, num_chords=17, lag=1)
    else:
        inter = pd.DataFrame(np.zeros((17, 17), dtype=int))
    oor = compute_out_of_reach(inter, power=-2)

    # 5) Tonnetz hybrid distance
    m_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    # 단일 rate 에서만 계산 (rate sweep 없이도 모듈 한 개 PH 는 의미 있음)
    rates_to_try = [0.0, 0.5, 1.0]
    profile = []
    for r in rates_to_try:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor,
                                            num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=alpha)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        profile.append((r, bd))

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled_local = label_cycles_from_persistence(persistence)
    print(f"    P4: module-local cycles found = {len(cycle_labeled_local)}")

    if len(cycle_labeled_local) == 0:
        return None, None

    # 6) 모듈 한정 활성화 행렬
    # inst1_mod + inst2_mod 의 union 을 32 timesteps 시간축에 매핑
    nodes_list = list(range(1, N + 1))
    ntd = np.zeros((MODULE_LEN, N), dtype=int)
    for s, pp, e in inst1_mod + inst2_mod:
        d = e - s
        if (pp, d) in notes_label:
            lbl = notes_label[(pp, d)]
            t_start = s if s < MODULE_LEN else (s - INST2_INIT_OFFSET)
            t_end = min(t_start + d, MODULE_LEN)
            for t in range(max(0, t_start), max(0, t_end)):
                if 0 <= t < MODULE_LEN:
                    ntd[t, lbl - 1] = 1

    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_labeled_local)

    # 단순 binary overlap (scale 조정 없이)
    overlap_proto = activation.values.astype(np.float32)
    return cycle_labeled_local, overlap_proto


# ─── 본 실험 ─────────────────────────────────────────────────────────

def run_strategy(name, base_seeds, gen_fn):
    """gen_fn(seed) -> (module_notes, extra_info_dict)"""
    print(f"\n[{name}]")
    trials = []
    for i, seed in enumerate(base_seeds):
        t0 = time.time()
        result = gen_fn(seed)
        elapsed = time.time() - t0
        if result is None or result[0] is None:
            print(f"  [{i+1:2d}] FAIL")
            continue
        mod, extra = result
        ev = eval_full(p_global, mod)
        ev.update({'elapsed_ms': elapsed * 1000, 'seed': seed, **extra})
        trials.append(ev)
        extra_str = ' '.join(f'{k}={v}' for k, v in extra.items() if k != 'best_j')
        print(f"  [{i+1:2d}] JS={ev['js']:.4f}  cov={ev['coverage']:.2f}  "
              f"mod_notes={ev['mod_n_notes']:3d}  {extra_str}  "
              f"({elapsed*1000:.1f} ms)")
    js_arr = np.array([t['js'] for t in trials])
    cov_arr = np.array([t['coverage'] for t in trials])
    mod_cov_arr = np.array([t.get('module_coverage', 0) for t in trials])
    return {
        'js_mean': float(js_arr.mean()),
        'js_std': float(js_arr.std(ddof=1)),
        'js_min': float(js_arr.min()),
        'js_max': float(js_arr.max()),
        'cov_mean': float(cov_arr.mean()),
        'mod_cov_mean': float(mod_cov_arr.mean()),
        'avg_elapsed_ms': float(np.mean([t['elapsed_ms'] for t in trials])),
        'trials': trials,
    }


def main():
    global p_global
    print("=" * 64)
    print("  §7.1 v3 — 한계 해결: 개선 C / D / P4")
    print("=" * 64)

    p_global = TDAMusicPipeline(PipelineConfig())
    p_global.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap_full = cache['overlap'].values
    cycle_labeled = cache['cycle_labeled']

    # P1 prototype (selective)
    proto_P1 = make_P1(overlap_full)
    print(f"\n  Tonnetz: {len(cycle_labeled)} cycles")
    print(f"  P1 prototype density: {(proto_P1 > 0).mean():.3f}")

    base_seeds = list(range(7300, 7310))
    results = {}

    # ── Baseline P1 (참조) ──
    def gen_P1(seed):
        mod = run_algo1_module(p_global, proto_P1, cycle_labeled, seed=seed)
        return mod, {'module_coverage': module_coverage(
            mod, p_global._cache['notes_label'])}
    results['Baseline P1'] = run_strategy('Baseline P1 (no improvement)',
                                          base_seeds, gen_P1)

    # ── 개선 C: best-of-k=10 ──
    def gen_C(seed):
        mod, cov, best_j = gen_with_best_of_k(
            p_global, proto_P1, cycle_labeled, base_seed=seed, k=10)
        return mod, {'module_coverage': cov, 'best_j': best_j}
    results['C: best-of-10'] = run_strategy(
        'C: best-of-k=10 (cov-maximizing)', base_seeds, gen_C)

    # ── 개선 D: coverage >= 20/23 ──
    def gen_D(seed):
        mod, cov, attempts = gen_with_coverage_constraint(
            p_global, proto_P1, cycle_labeled, base_seed=seed,
            target=COVERAGE_TARGET, max_attempts=30)
        return mod, {'module_coverage': cov, 'attempts': attempts}
    results['D: cov>=20/23'] = run_strategy(
        f'D: hard coverage constraint (>= {COVERAGE_TARGET}/23)',
        base_seeds, gen_D)

    # ── 개선 C + D 결합 ──
    def gen_CD(seed):
        # k=10 best 후 그 중 coverage 만족하는 첫 모듈
        notes_label = p_global._cache['notes_label']
        candidates = []
        for j in range(10):
            mod = run_algo1_module(p_global, proto_P1, cycle_labeled,
                                   seed=seed * 1000 + j)
            cov = module_coverage(mod, notes_label)
            candidates.append((cov, j, mod))
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_cov, best_j, best_mod = candidates[0]
        return best_mod, {'module_coverage': best_cov,
                          'over_target': int(best_cov >= COVERAGE_TARGET)}
    results['C+D combined'] = run_strategy(
        'C+D: best-of-10 with coverage report', base_seeds, gen_CD)

    # ── 개선 P4: module-local PH ──
    print("\n  P4 module-local PH 계산 중...")
    cycle_local, proto_P4 = compute_module_local_ph(p_global)
    if cycle_local is not None and proto_P4 is not None:
        print(f"  P4 prototype density: {(proto_P4 > 0).mean():.3f}")

        def gen_P4(seed):
            mod = run_algo1_module(p_global, proto_P4, cycle_local, seed=seed)
            return mod, {'module_coverage': module_coverage(
                mod, p_global._cache['notes_label'])}
        results['P4: module-local PH'] = run_strategy(
            'P4: module-local PH', base_seeds, gen_P4)

        # ── 최강 조합: P4 + C (module-local PH + best-of-10) ──
        def gen_P4C(seed):
            notes_label = p_global._cache['notes_label']
            candidates = []
            for j in range(10):
                mod = run_algo1_module(p_global, proto_P4, cycle_local,
                                       seed=seed * 1000 + j)
                cov = module_coverage(mod, notes_label)
                candidates.append((cov, j, mod))
            candidates.sort(key=lambda x: (-x[0], x[1]))
            best_cov, best_j, best_mod = candidates[0]
            return best_mod, {'module_coverage': best_cov}
        results['P4 + C (best-of-10)'] = run_strategy(
            'P4 + C: module-local PH with best-of-10',
            base_seeds, gen_P4C)
    else:
        print("  P4: 모듈 내 PH 결과가 비어 있음, 건너뜀")

    # ── 결과 요약 ──
    print("\n" + "=" * 70)
    print("  요약 (N=10, baseline full-song JS = 0.0398 ± 0.0031)")
    print("=" * 70)
    print(f"  {'Strategy':28s}  {'JS (mean ± std)':18s}  {'best':>7s}  {'cov':>5s}  {'time':>9s}")
    print("  " + "─" * 76)
    for name, r in results.items():
        print(f"  {name:28s}  "
              f"{r['js_mean']:.4f} ± {r['js_std']:.4f}  "
              f"{r['js_min']:>7.4f}  "
              f"{r['cov_mean']:>5.3f}  "
              f"{r['avg_elapsed_ms']:>6.1f} ms")

    # JSON 저장
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    lite = {k: {kk: vv for kk, vv in v.items() if kk != 'trials'}
            for k, v in results.items()}
    lite['n_repeats'] = N_REPEATS
    lite['baseline_full_song'] = {'js_mean': 0.0398, 'js_std': 0.0031}
    with open(os.path.join(out_dir, 'step71_improvements.json'),
              'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {out_dir}/step71_improvements.json")


if __name__ == '__main__':
    main()
