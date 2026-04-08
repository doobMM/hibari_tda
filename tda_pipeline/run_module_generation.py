"""
run_module_generation.py — §7.1 모듈 단위 생성 + 구조적 재배치

전략:
 1. Algorithm 1로 단 하나의 32-timestep 모듈만 생성한다.
    (기존 전체 생성은 T=1088, 여기서는 T=32)
 2. 생성된 모듈을 hibari의 실제 구조대로 배치한다:
    - Inst 1 position: 33 copies at t = 0, 32, 64, ..., 1024
                       (no rests between copies — 전체 [0, 1056))
    - Inst 2 position: 32 copies at t = 33, 66, 99, ...
                       (initial 33-timestep silence + 1-timestep rest between each)
 3. 생성 결과를 원곡 hibari와 비교 (JS divergence, note count, pitch count).
 4. MusicXML 파일 저장.

실제로 관찰된 hibari 구조 (§5 Figure 7):
  inst1: rest 0개 across [0, 1056)
  inst2: 초기 rest 33개 + 각 모듈 경계마다 1 rest → 32번째 copy까지 [33, 1088)
"""
import os, sys, json, time, random, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig
from generation import algorithm1_optimized, NodePool, CycleSetManager, notes_to_xml
from eval_metrics import evaluate_generation

MODULE_LEN = 32       # 한 모듈 = 32 8분음표
N_INST1_COPIES = 33   # inst1: 33번 반복, 쉼 없음
N_INST2_COPIES = 32   # inst2: 32번 반복, 각 copy 사이에 1 timestep rest
INST2_OFFSET = 33     # inst2 initial silence
T_TOTAL = 1088

N_REPEATS = 10        # 모듈 생성 자체를 반복하여 통계


def generate_one_module(p, overlap_values_mod, cycle_labeled, seed):
    """모듈 1개 (T=32 timesteps) 의 note를 생성."""
    random.seed(seed); np.random.seed(seed)

    pool = NodePool(p._cache['notes_label'], p._cache['notes_counts'],
                    num_modules=65)
    manager = CycleSetManager(cycle_labeled)

    # 한 모듈의 chord height 패턴 (32개)
    # hibari는 첫 16은 '4,4,4,3,4,3,4,3,4,3,3,3,3,3,3,3',
    #          뒤 16은 '4,4,4,3,4,3,4,3,4,3,4,3,3,3,3,3'
    module_heights = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                      4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]

    t0 = time.time()
    generated = algorithm1_optimized(
        pool, list(module_heights),
        overlap_values_mod,
        manager,
        max_resample=50,
        verbose=False)
    elapsed = time.time() - t0

    return generated, elapsed


def replicate_inst1(module_notes, n_copies, module_len):
    """한 모듈의 note를 inst 1 position에 n번 복제 (쉼 없음).

    각 copy는 t = [m * module_len, (m+1) * module_len) 범위에 배치됨.
    module_notes의 절대 시점 s는 모듈 내 상대 시점으로 해석.
    """
    replicated = []
    for m in range(n_copies):
        offset = m * module_len
        for s, pitch, e in module_notes:
            new_s = s + offset
            new_e = e + offset
            # note가 copy 경계를 넘어가면 경계에서 잘라냄
            if new_e > offset + module_len:
                new_e = offset + module_len
            if new_s < offset + module_len and new_e > new_s:
                replicated.append((new_s, pitch, new_e))
    return replicated


def replicate_inst2(module_notes, n_copies, module_len, initial_offset, rest_gap=1):
    """한 모듈의 note를 inst 2 position에 배치.

    - 처음 initial_offset timesteps은 silence
    - 각 copy 사이에 rest_gap timesteps의 rest
    - k번째 copy는 t = [initial_offset + k*(module_len + rest_gap),
                         initial_offset + k*(module_len + rest_gap) + module_len) 범위
    """
    replicated = []
    period = module_len + rest_gap
    for m in range(n_copies):
        copy_start = initial_offset + m * period
        for s, pitch, e in module_notes:
            new_s = s + copy_start
            new_e = e + copy_start
            if new_e > copy_start + module_len:
                new_e = copy_start + module_len
            if new_s < copy_start + module_len and new_e > new_s:
                replicated.append((new_s, pitch, new_e))
    return replicated


def main():
    print("=" * 64)
    print("  §7.1 모듈 단위 생성 + 구조적 재배치")
    print("=" * 64)

    # ── 1) 전처리 및 Tonnetz overlap 로드 ──
    p = TDAMusicPipeline(PipelineConfig())
    p.run_preprocessing()
    inst1 = p._cache['inst1_real']
    inst2 = p._cache['inst2_real']
    notes_label = p._cache['notes_label']

    with open('cache/metric_tonnetz.pkl', 'rb') as f:
        cache = pickle.load(f)
    overlap_full = cache['overlap'].values  # (T=1088, K=46)
    cycle_labeled = cache['cycle_labeled']
    K = len(cycle_labeled)
    print(f"\n  Tonnetz: {K} cycles, overlap shape {overlap_full.shape}")

    # ── Prototype module overlap ──
    # 전략 비교 (run_module_generation_v2.py, N=10):
    #   P0 OR (99.9% 셀 활성) : JS 0.094 ± 0.028  — 사실상 random sampling에 가까움
    #   P1 mean → τ=0.5 (16%) : JS 0.113 ± 0.029  — §4.3a 의 최적 τ 와 일치
    #   P3 median module (38%): JS 0.106 ± 0.029  — 실제 한 모듈 선택
    #
    # 평균 JS는 세 전략이 비슷하지만, 전략별 의미가 다르다:
    #   OR은 "모든 cycle이 모든 시점에 활성" = 본질적으로 random sampling.
    #   P1은 "33개 모듈 중 절반 이상에서 활성인 cell만" = 선택적 prototype.
    # 본 스크립트는 P1 (mean → τ=0.5) 를 기본으로 채택한다 — §4.3a 의
    # 발견과 일치하며 density가 의미 있는 수준 (16%)이다.

    n_mod_full = N_INST1_COPIES  # = 33
    total_usable = n_mod_full * MODULE_LEN  # 33 * 32 = 1056
    if total_usable > overlap_full.shape[0]:
        total_usable = overlap_full.shape[0] // MODULE_LEN * MODULE_LEN
    usable = overlap_full[:total_usable].reshape(
        total_usable // MODULE_LEN, MODULE_LEN, K).astype(float)

    mean_activation = usable.mean(axis=0)  # (32, K) 각 셀의 33 모듈 평균
    overlap_mod = (mean_activation >= 0.5).astype(np.float32)
    print(f"  Prototype module overlap (mean → τ=0.5) shape: "
          f"{overlap_mod.shape}")
    print(f"  Density: naive first-32 = "
          f"{(overlap_full[:MODULE_LEN] > 0).mean():.3f},  "
          f"P1 selective = {(overlap_mod > 0).mean():.3f}")

    # 원곡 평가를 위한 기준: hibari 전체
    original = [inst1, inst2]

    # ── 2) 모듈 생성 + 복제 + 평가를 N_REPEATS 회 반복 ──
    print(f"\n  생성 반복 횟수: {N_REPEATS}")
    trials = []
    best_trial = None

    for i in range(N_REPEATS):
        # 2a) 모듈 1개 생성
        module_notes, elapsed = generate_one_module(
            p, overlap_mod, cycle_labeled, seed=7100 + i)
        module_len_actual = max((e for _, _, e in module_notes), default=0)

        # 2b) 재배치
        inst1_rep = replicate_inst1(module_notes, N_INST1_COPIES, MODULE_LEN)
        inst2_rep = replicate_inst2(module_notes, N_INST2_COPIES,
                                     MODULE_LEN, INST2_OFFSET, rest_gap=1)
        all_gen = inst1_rep + inst2_rep

        # 2c) 평가
        metrics = evaluate_generation(all_gen, original, notes_label, name="")

        trial = {
            'seed': 7100 + i,
            'module_note_count': len(module_notes),
            'inst1_rep_count': len(inst1_rep),
            'inst2_rep_count': len(inst2_rep),
            'total_notes': len(all_gen),
            'js_divergence': metrics['js_divergence'],
            'kl_divergence': metrics['kl_divergence'],
            'note_coverage': metrics['note_coverage'],
            'pitch_count': metrics['pitch_count'],
            'elapsed_s': elapsed,
            'generated': all_gen,
        }
        trials.append(trial)

        print(f"  [{i+1:2d}] module={len(module_notes):3d}  "
              f"total={len(all_gen):4d}  "
              f"JS={metrics['js_divergence']:.4f}  "
              f"cov={metrics['note_coverage']:.2f}  "
              f"({elapsed*1000:.1f}ms)")

        if best_trial is None or trial['js_divergence'] < best_trial['js_divergence']:
            best_trial = trial

    # ── 3) 통계 요약 ──
    def stat(key):
        arr = np.array([t[key] for t in trials])
        return {'mean': float(arr.mean()),
                'std':  float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
                'min':  float(arr.min()),
                'max':  float(arr.max())}

    summary = {
        'n_repeats': N_REPEATS,
        'method': '§7.1 module-level generation + structural rearrangement',
        'cycle_source': 'Tonnetz (full-song PH), sliced to first 32 rows',
        'module_len': MODULE_LEN,
        'n_inst1_copies': N_INST1_COPIES,
        'n_inst2_copies': N_INST2_COPIES,
        'inst2_initial_offset': INST2_OFFSET,
        'inst2_rest_gap': 1,
        'js_divergence':  stat('js_divergence'),
        'kl_divergence':  stat('kl_divergence'),
        'note_coverage':  stat('note_coverage'),
        'total_notes':    stat('total_notes'),
        'pitch_count':    stat('pitch_count'),
        'elapsed_s':      stat('elapsed_s'),
        'best_seed': best_trial['seed'],
        'best_js': best_trial['js_divergence'],
    }

    print("\n" + "=" * 64)
    print("  요약 통계")
    print("=" * 64)
    print(f"  JS div:         {summary['js_divergence']['mean']:.4f} "
          f"± {summary['js_divergence']['std']:.4f}   "
          f"(min {summary['js_divergence']['min']:.4f}, "
          f"max {summary['js_divergence']['max']:.4f})")
    print(f"  Note coverage:  {summary['note_coverage']['mean']:.3f} "
          f"± {summary['note_coverage']['std']:.3f}")
    print(f"  Total notes:    {summary['total_notes']['mean']:.0f} "
          f"± {summary['total_notes']['std']:.0f}")
    print(f"  Gen time:       {summary['elapsed_s']['mean']*1000:.2f} ms "
          f"per module")

    # 비교: §3 baseline
    print("\n  [비교] 전체 곡 생성 baseline (Step 3 Tonnetz, N=20):")
    print("    JS div: 0.0398 ± 0.0031")
    print(f"  § 7.1 module-level: {summary['js_divergence']['mean']:.4f} "
          f"± {summary['js_divergence']['std']:.4f}")

    # ── 4) JSON 저장 ──
    out_dir = os.path.join('docs', 'step3_data')
    os.makedirs(out_dir, exist_ok=True)
    # trial의 'generated'는 JSON에 넣지 않음 (너무 큼)
    trials_lite = [{k: v for k, v in t.items() if k != 'generated'}
                   for t in trials]
    results = {'summary': summary, 'trials': trials_lite}
    with open(os.path.join(out_dir, 'step71_module_results.json'),
              'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  저장: docs/step3_data/step71_module_results.json")

    # ── 5) 최우수 trial의 MusicXML 출력 ──
    os.makedirs('output', exist_ok=True)
    try:
        notes_to_xml([best_trial['generated']],
                     tempo_bpm=66,
                     file_name=f"step71_module_best_seed{best_trial['seed']}",
                     output_dir="./output")
        print(f"  MusicXML: output/step71_module_best_seed{best_trial['seed']}.musicxml")
    except Exception as e:
        print(f"  MusicXML 저장 실패: {e}")


if __name__ == '__main__':
    main()
