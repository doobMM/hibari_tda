"""
run_module_generation_v2.py — §7.1 prototype 전략 비교 실험

이전 run_module_generation.py의 OR(union) 접근은 99.9% 셀을 활성화시켜
실제로 cycle 구조 정보를 거의 담지 못한다는 비판이 있었다.
본 스크립트는 4가지 대안을 구현하고 N=10 반복으로 JS divergence를 비교한다.

Prototype 전략:
  P0 (이전 baseline) : max(OR) over 33 modules              — 99.9% dense
  P1 : Mean activation → binarize at τ=0.5                   — moderately sparse
  P2 : Mean activation → continuous [0,1] 그대로 사용        — continuous
  P3 : Median-activity 모듈 하나 선택 (cycle 활성 수 기준)   — 실제 한 모듈
  P4 : Module-local PH — 첫 모듈에서 새로 homology 계산     — 가장 원칙적
  P5 : Global cycle activity vector (1-row) 를 32번 복제    — 시간 무시

각 전략에 대해 N=10회 독립 생성 + 구조적 재배치 + JS 측정.
"""
import os, sys, json, time, random, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager
from eval_metrics import evaluate_generation

MODULE_LEN = 32
N_INST1 = 33
N_INST2 = 32
INST2_OFFSET = 33
N_REPEATS = 10


def replicate_inst1(mod, n=N_INST1, ml=MODULE_LEN):
    out = []
    for m in range(n):
        off = m * ml
        for s, p, e in mod:
            ns = s + off
            ne = min(e + off, off + ml)
            if ns < off + ml and ne > ns:
                out.append((ns, p, ne))
    return out


def replicate_inst2(mod, n=N_INST2, ml=MODULE_LEN, init_off=INST2_OFFSET, gap=1):
    out = []
    period = ml + gap
    for m in range(n):
        cs = init_off + m * period
        for s, p, e in mod:
            ns = s + cs
            ne = min(e + cs, cs + ml)
            if ns < cs + ml and ne > ns:
                out.append((ns, p, ne))
    return out


def run_algo1(p, overlap_values, cycle_labeled, seed):
    random.seed(seed); np.random.seed(seed)
    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    heights = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    t0 = time.time()
    generated = algorithm1_optimized(
        pool, list(heights), overlap_values, manager,
        max_resample=50, verbose=False)
    return generated, time.time() - t0


def eval_trial(p, module_notes, elapsed):
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
        'module_n_notes': int(len(module_notes)),
        'elapsed_ms': elapsed * 1000,
    }


# ── Prototype 전략별 중첩행렬 생성 ────────────────────────────────────

def make_P0_or(overlap_full):
    """max over 33 modules."""
    usable = overlap_full[:N_INST1 * MODULE_LEN].reshape(
        N_INST1, MODULE_LEN, -1)
    return usable.max(axis=0).astype(np.float32)


def make_P1_mean_bin(overlap_full, tau=0.5):
    """mean → τ=0.5로 이진화."""
    usable = overlap_full[:N_INST1 * MODULE_LEN].reshape(
        N_INST1, MODULE_LEN, -1).astype(float)
    mean = usable.mean(axis=0)
    return (mean >= tau).astype(np.float32)


def make_P2_mean_cont(overlap_full):
    """mean → 연속값 그대로."""
    usable = overlap_full[:N_INST1 * MODULE_LEN].reshape(
        N_INST1, MODULE_LEN, -1).astype(float)
    return usable.mean(axis=0).astype(np.float32)


def make_P3_median_module(overlap_full):
    """33개 모듈 중 cycle 활성 수가 median인 모듈 선택."""
    usable = overlap_full[:N_INST1 * MODULE_LEN].reshape(
        N_INST1, MODULE_LEN, -1)
    counts = usable.sum(axis=(1, 2))  # 각 모듈의 총 활성 셀 수
    sorted_idx = np.argsort(counts)
    median_idx = sorted_idx[len(sorted_idx) // 2]
    print(f"    P3: module counts min={counts.min()}, median={counts[median_idx]}, "
          f"max={counts.max()}, chosen={median_idx}")
    return usable[median_idx].astype(np.float32)


def make_P4_module_local_ph(p):
    """첫 모듈의 활성 note만으로 새로 PH 계산.

    간단한 구현: 첫 MODULE_LEN timesteps의 note_time을 잘라서,
    그 부분에만 등장하는 note 간의 거리를 원본 거리 행렬에서
    추출한 뒤 generate_barcode_numpy 호출.
    """
    # 복잡하므로 본 스크립트에서는 구현하지 않고 None 반환
    return None


def make_P5_flat(overlap_full):
    """cycle별 전체 활성 비율을 32번 복제."""
    # 각 cycle이 전체 시간축에서 활성인 비율
    rates = overlap_full[:N_INST1 * MODULE_LEN].mean(axis=0)  # (K,)
    # 32행 모두 같은 값
    proto = np.tile(rates, (MODULE_LEN, 1)).astype(np.float32)
    # 이진화 (τ=0.5)
    return (proto >= 0.5).astype(np.float32)


# ── 메인 실험 ─────────────────────────────────────────────────────────

def density(arr):
    return float((arr > 0).mean())


def run_strategy(name, overlap_proto, p, cycle_labeled):
    print(f"\n  [{name}] density={density(overlap_proto):.3f}")
    trials = []
    for i in range(N_REPEATS):
        mod, el = run_algo1(p, overlap_proto, cycle_labeled, seed=7200 + i)
        tr = eval_trial(p, mod, el)
        trials.append(tr)
    js_arr = np.array([t['js'] for t in trials])
    cov_arr = np.array([t['coverage'] for t in trials])
    return {
        'density': density(overlap_proto),
        'js_mean': float(js_arr.mean()),
        'js_std':  float(js_arr.std(ddof=1)),
        'js_min':  float(js_arr.min()),
        'js_max':  float(js_arr.max()),
        'cov_mean': float(cov_arr.mean()),
        'trials': trials,
    }


def main():
    print("=" * 64)
    print("  §7.1 v2 — Prototype 전략 비교")
    print("=" * 64)

    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap_full = cache['overlap'].values
    cycle_labeled = cache['cycle_labeled']
    print(f"\n  Tonnetz: {len(cycle_labeled)} cycles, {overlap_full.shape}")

    protos = [
        ('P0 — OR over 33',          make_P0_or(overlap_full)),
        ('P1 — mean → τ=0.5',        make_P1_mean_bin(overlap_full, tau=0.5)),
        ('P2 — mean continuous',     make_P2_mean_cont(overlap_full)),
        ('P3 — median module',       make_P3_median_module(overlap_full)),
        ('P5 — flat cycle rate',     make_P5_flat(overlap_full)),
    ]

    results = {}
    for name, ov in protos:
        results[name] = run_strategy(name, ov, p, cycle_labeled)

    # 결과 요약
    print("\n" + "=" * 64)
    print("  요약 (N=10회 반복, baseline full-song Tonnetz JS = 0.0398)")
    print("=" * 64)
    header = f"  {'Strategy':28s} {'dens':>6s}  {'JS (mean±std)':>20s}  {'best':>8s}  {'cov':>6s}"
    print(header)
    print("  " + "─" * (len(header) - 2))
    for name, r in results.items():
        line = (f"  {name:28s} "
                f"{r['density']:>6.3f}  "
                f"{r['js_mean']:>.4f} ± {r['js_std']:>.4f}  "
                f"{r['js_min']:>8.4f}  "
                f"{r['cov_mean']:>6.3f}")
        print(line)

    # JSON 저장 (trials 제외 → 짧게)
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    lite = {k: {kk: vv for kk, vv in v.items() if kk != 'trials'}
            for k, v in results.items()}
    lite['n_repeats'] = N_REPEATS
    lite['baseline_full_song_tonnetz'] = {'js_mean': 0.0398, 'js_std': 0.0031}
    with open(os.path.join(out_dir, 'step71_prototype_comparison.json'),
              'w', encoding='utf-8') as f:
        json.dump(lite, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: {out_dir}/step71_prototype_comparison.json")


if __name__ == '__main__':
    main()
