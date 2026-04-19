"""
run_module_barcode.py — 모듈 위상 거리(Wasserstein) 기반 생성 실험

§7.1 새 방향: "hibari와 같이 배치했을 때 같은 위상구조가 나오는 모듈"을 탐색.
기존 eval_full() (JS divergence) 대신 eval_barcode() (Wasserstein distance)를
best-of-k 선택 기준으로 사용.

Reference: hibari Module 0 (t∈[0,32), inst1 only) 의 persistence diagram
           rate = [0.0, 0.5, 1.0] 각각에서 계산 후 합산
Generated: Algorithm 1으로 생성된 모듈의 persistence diagram (동일 방식)
Metric   : Wasserstein distance (persim) — 합산 W_total = Σ_r W(dgm_gen[r], dgm_ref[r])

동시에 JS divergence도 측정하여 두 지표 간 상관관계를 분석한다.

주의사항 (논문 §7.2 포함 예정):
  (1) JS vs W dist: 두 목표는 상충 가능
      — JS는 note frequency 분포, W는 위상 구조를 측정.
        W가 낮아도 JS가 높을 수 있고, 반대도 마찬가지.
  (2) Module-level comparison의 한계
      — 단일 악기 모듈의 barcode를 비교하므로, full song 배치 후
        두 악기 상호작용에서 발생하는 위상 구조 변화가 반영되지 않음.
  (3) chord 공간 불일치 가능성
      — hibari reference는 전체 17 chord 공간, 생성 모듈은 그보다 적을 수 있음.
        이 경우 distance matrix의 지지(support)가 달라진다.
  (4) rate 선택과 결과 민감도
      — r=0.5를 대표값으로 쓰지만 full profile 비교와 결과가 다를 수 있음.
        본 실험은 r ∈ {0.0, 0.5, 1.0} 3점 합산으로 민감도를 완화한다.
"""
import os, sys, json, time, random, datetime
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
from preprocessing import (
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
)
from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_distance_matrix, compute_out_of_reach,
)
from overlap import (
    group_rBD_by_homology, label_cycles_from_persistence, build_activation_matrix,
)
from topology import generate_barcode_numpy
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
from persim import wasserstein as pers_wasserstein

from run_module_generation_v4 import (
    replicate_inst1, replicate_inst2,
    compute_module_local_ph, eval_full, run_algo1_module, module_coverage,
    MODULE_LEN, N_INST1_COPIES, N_INST2_COPIES, INST2_INIT_OFFSET,
    N_REPEATS, K_BEST,
)

# ─── 설정 ─────────────────────────────────────────────────────────────────────
ALPHA = 0.5          # tonnetz hybrid alpha
RATES = [0.0, 0.5, 1.0]  # barcode 비교에 쓸 rate 값들
START_MODULE = 0
BASE_SEEDS = list(range(9400, 9410))   # v4와 seed 공간 분리


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def dgm_from_bd(bd):
    """generate_barcode_numpy 반환 → numpy persistence diagram (finite pairs만)."""
    pairs = [[item[1][0], item[1][1]] for item in bd if item[1][1] != float('inf')]
    return np.array(pairs, dtype=float) if pairs else np.empty((0, 2), dtype=float)


def safe_wasserstein(dgm1, dgm2):
    """두 diagram 모두 비어있으면 0, 아니면 persim.wasserstein."""
    if len(dgm1) == 0 and len(dgm2) == 0:
        return 0.0
    return float(pers_wasserstein(dgm1, dgm2))


# ─── Reference barcode 계산 ───────────────────────────────────────────────────

def compute_ref_diagrams(p):
    """
    hibari Module 0 (inst1 only, t∈[0,32)) 의 persistence diagrams 계산.
    rate ∈ RATES 각각에서 diagram을 구한다.

    Notes:
    - inst1 only를 사용하는 이유: Module 0에서 inst2는 아직 시작되지 않음(t=33~).
      따라서 inter weight = 0, intra만으로 PH를 계산한다.
    - 이는 compute_module_local_ph(p, 0)의 reference와 동일한 데이터.
    """
    notes_label = p._cache['notes_label']
    notes_dict  = p._cache['notes_dict']
    chord_seq1  = p._cache['chord_seq1']
    N           = len(notes_label)
    num_chords  = p.config.midi.num_chords  # 17

    cs1 = chord_seq1[:MODULE_LEN]

    intra = compute_intra_weights(cs1, num_chords=num_chords)
    inter = pd.DataFrame(np.zeros((num_chords, num_chords), dtype=int))

    nz = intra.values[intra.values != 0]
    if len(nz) == 0:
        print("  [경고] hibari module 0 intra weight all-zero — reference diagram 비어있음")
        return {r: np.empty((0, 2)) for r in RATES}
    oor = 1 + 2 / (nz.min() * 1e-2)

    m_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    diagrams = {}
    for r in RATES:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        diagrams[r] = dgm_from_bd(bd)
        print(f"    ref r={r:.1f}: {len(diagrams[r])} finite cycles")
    return diagrams


# ─── Generated module barcode 계산 ────────────────────────────────────────────

def eval_barcode(module_notes, notes_label, ref_diagrams):
    """
    생성된 모듈 notes → Wasserstein distance vs hibari reference.

    Args:
        module_notes : [(start, pitch, end)] — 생성된 모듈 (0-indexed, 0..31)
        notes_label  : {(pitch, dur): int}
        ref_diagrams : {rate: np.array} — hibari module 0 reference

    Returns:
        dict {
            'w_total'    : float — Σ_r W(dgm_gen[r], dgm_ref[r]),
            'w_by_rate'  : {r: float},
            'n_cycles'   : int  — 생성 모듈의 최대 사이클 수 (rate별 max),
            'n_chords'   : int  — 생성 모듈의 고유 chord 수,
        }
    """
    if not module_notes:
        w_by_rate = {r: safe_wasserstein(np.empty((0, 2)), ref_diagrams[r]) for r in RATES}
        return {'w_total': sum(w_by_rate.values()), 'w_by_rate': w_by_rate,
                'n_cycles': 0, 'n_chords': 0}

    # chord sequence 구성
    active = group_notes_with_duration(module_notes)
    chord_map_gen, chord_seq_gen = build_chord_labels(active)
    notes_dict_gen = chord_to_note_labels(chord_map_gen, notes_label)
    notes_dict_gen['name'] = 'notes'

    num_chords_gen = len(chord_map_gen)
    N = len(notes_label)

    intra = compute_intra_weights(chord_seq_gen, num_chords=num_chords_gen)
    inter = pd.DataFrame(np.zeros((num_chords_gen, num_chords_gen), dtype=int))

    nz = intra.values[intra.values != 0]
    if len(nz) == 0:
        w_by_rate = {r: safe_wasserstein(np.empty((0, 2)), ref_diagrams[r]) for r in RATES}
        return {'w_total': sum(w_by_rate.values()), 'w_by_rate': w_by_rate,
                'n_cycles': 0, 'n_chords': num_chords_gen}
    oor = 1 + 2 / (nz.min() * 1e-2)

    m_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    w_by_rate = {}
    n_cycles_max = 0
    for r in RATES:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict_gen, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        dgm_gen = dgm_from_bd(bd)
        n_cycles_max = max(n_cycles_max, len(dgm_gen))
        w_by_rate[r] = safe_wasserstein(dgm_gen, ref_diagrams[r])

    return {
        'w_total'   : sum(w_by_rate.values()),
        'w_by_rate' : w_by_rate,
        'n_cycles'  : n_cycles_max,
        'n_chords'  : num_chords_gen,
    }


# ─── P4+C trial (Wasserstein 선택 기준) ──────────────────────────────────────

def p4c_trial_barcode(p, cycle_local, overlap_proto, base_seed, ref_diagrams, k=K_BEST):
    """
    best-of-k selection — 기준: Wasserstein distance (기존 v4의 coverage 기준 대체).

    각 candidate의 W_total과 JS divergence를 모두 측정한다.
    """
    notes_label = p._cache['notes_label']
    candidates = []
    for j in range(k):
        seed = base_seed * 1000 + j
        random.seed(seed); np.random.seed(seed)
        mod = run_algo1_module(p, overlap_proto, cycle_local, seed=seed)
        wb = eval_barcode(mod, notes_label, ref_diagrams)
        candidates.append((wb['w_total'], j, mod, wb))
    candidates.sort(key=lambda x: x[0])   # W 기준 오름차순
    best_w, best_j, best_mod, best_wb = candidates[0]
    return best_mod, best_wb


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("  run_module_barcode — Wasserstein 위상 거리 기반 모듈 생성")
    print("=" * 72)

    # ── 전처리 ──
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    notes_label = p._cache['notes_label']

    # ── Module 0 P4 cycle/overlap 계산 (Algorithm 1 입력용) ──
    print(f"\n[1] Module {START_MODULE} local PH 계산...")
    cycle_local, overlap_proto, n_cyc = compute_module_local_ph(p, start_module=START_MODULE)
    if cycle_local is None:
        print("  PH empty — 종료")
        return
    print(f"  module-local cycles: {n_cyc}, prototype density: {(overlap_proto > 0).mean():.3f}")

    # ── Reference barcode 계산 ──
    print(f"\n[2] Reference barcode 계산 (hibari module {START_MODULE}, inst1 only)...")
    ref_diagrams = compute_ref_diagrams(p)
    ref_sizes = {r: len(ref_diagrams[r]) for r in RATES}
    print(f"  reference cycles: {ref_sizes}")

    # ── 실험 루프 ──
    print(f"\n[3] 실험 루프 (N={len(BASE_SEEDS)} seeds × K={K_BEST} best-of-k)...")
    print(f"    {'seed':>6}  {'W_total':>8}  {'W@0.5':>7}  {'JS':>7}  {'cycles':>7}  {'chords':>7}")
    print(f"    {'-'*6}  {'-'*8}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")

    results = []
    best_global = {'w_total': float('inf'), 'js': None, 'seed': None, 'mod': None, 'wb': None}
    best_js_for_best_w = None  # best-W trial에서의 JS 값

    for seed in BASE_SEEDS:
        t0 = time.time()
        mod, wb = p4c_trial_barcode(p, cycle_local, overlap_proto, seed, ref_diagrams)

        # JS도 측정
        ev_js = eval_full(p, mod)
        js = ev_js['js']

        elapsed = time.time() - t0
        print(f"    {seed:>6}  {wb['w_total']:>8.4f}  {wb['w_by_rate'][0.5]:>7.4f}"
              f"  {js:>7.4f}  {wb['n_cycles']:>7d}  {wb['n_chords']:>7d}  ({elapsed:.1f}s)")

        results.append({
            'seed'    : seed,
            'w_total' : wb['w_total'],
            'w_by_rate': wb['w_by_rate'],
            'js'      : js,
            'n_cycles': wb['n_cycles'],
            'n_chords': wb['n_chords'],
            'coverage': ev_js['coverage'],
        })

        if wb['w_total'] < best_global['w_total']:
            best_global.update({'w_total': wb['w_total'], 'js': js,
                                 'seed': seed, 'mod': mod, 'wb': wb})

    # ── 통계 요약 ──
    w_arr = np.array([r['w_total'] for r in results])
    js_arr = np.array([r['js'] for r in results])
    corr = np.corrcoef(w_arr, js_arr)[0, 1]

    print(f"\n{'='*72}")
    print(f"  W_total : mean={w_arr.mean():.4f}  std={w_arr.std(ddof=1):.4f}"
          f"  min={w_arr.min():.4f}")
    print(f"  JS      : mean={js_arr.mean():.4f}  std={js_arr.std(ddof=1):.4f}"
          f"  min={js_arr.min():.4f}")
    print(f"  Pearson(W, JS) = {corr:.3f}")
    print(f"\n  Best trial (W 기준):")
    print(f"    seed={best_global['seed']}, W_total={best_global['w_total']:.4f}"
          f", JS={best_global['js']:.4f}")
    print(f"    ref cycle 수={ref_sizes}, gen cycle 수={best_global['wb']['n_cycles']}")

    # ── Best trial MusicXML 저장 ──
    if best_global['mod'] is not None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"step_barcode_best_s{best_global['seed']}_{ts}"
        all_gen = replicate_inst1(best_global['mod']) + replicate_inst2(best_global['mod'])
        notes_to_xml([all_gen], tempo_bpm=66, file_name=fname, output_dir="./output")
        print(f"\n  MusicXML: output/{fname}.musicxml")
    else:
        fname = None

    # ── JSON 저장 ──
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    output = {
        'description': 'Wasserstein 위상 거리 기반 모듈 생성 (run_module_barcode.py)',
        'config': {
            'start_module': START_MODULE,
            'alpha': ALPHA,
            'rates': RATES,
            'base_seeds': BASE_SEEDS,
            'k_best': K_BEST,
        },
        'ref_diagrams_size': {str(r): int(len(ref_diagrams[r])) for r in RATES},
        'results': [
            {**r, 'w_by_rate': {str(k): v for k, v in r['w_by_rate'].items()}}
            for r in results
        ],
        'summary': {
            'w_mean': float(w_arr.mean()),
            'w_std': float(w_arr.std(ddof=1)),
            'w_min': float(w_arr.min()),
            'js_mean': float(js_arr.mean()),
            'js_std': float(js_arr.std(ddof=1)),
            'js_min': float(js_arr.min()),
            'pearson_w_js': float(corr),
        },
        'best_trial': {
            'seed': best_global['seed'],
            'w_total': float(best_global['w_total']),
            'js': float(best_global['js']),
            'w_by_rate': {str(r): float(best_global['wb']['w_by_rate'][r]) for r in RATES},
            'musicxml': f"output/{fname}.musicxml" if fname else None,
        },
    }

    json_path = os.path.join(out_dir, 'step_barcode_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {json_path}")
    print(f"\nDone.")
    return output


if __name__ == '__main__':
    main()
