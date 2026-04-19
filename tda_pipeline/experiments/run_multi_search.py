"""
run_multi_search.py — 다중 search 조합으로 통합 seed 생성
============================================================

search_type(timeflow/simul/complex) × lag(1~4) × dim(1,2)의
모든 조합에서 cycle을 탐색하고, 통합하여 음악을 생성합니다.

dim=2는 계산이 무거우므로 coarse step(power=-1)을 사용합니다.
"""

import sys, os, time
import numpy as np
import pandas as pd
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from pipeline import TDAMusicPipeline, PipelineConfig
from overlap import (
    label_cycles_from_persistence, group_rBD_by_homology,
    build_activation_matrix, build_overlap_matrix
)
from preprocessing import simul_chord_lists, simul_union_by_dict
from cycle_selector import CycleSubsetSelector


def merge_persistence_dicts(*dicts):
    """여러 persistence dict를 하나로 합칩니다.

    각 dict는 {cycle_vertex_tuple: [(rate, birth, death), ...]} 형태.
    같은 cycle(동일 vertex tuple)이 여러 search에서 발견되면,
    해당 cycle의 rate/birth/death 리스트를 단순 연결(extend)하여 통합.
    → 서로 다른 search에서 찾은 고유 cycle들이 하나의 dict로 모임.
    """
    merged = {}
    for d in dicts:
        for cycle_key, rate_list in d.items():
            merged.setdefault(cycle_key, []).extend(rate_list)
    return merged


def run_search_batch(pipeline, configs, verbose=True):
    """여러 (search_type, lag, dim, power) 조합을 순차 실행합니다.

    동작 흐름:
      1) configs 리스트를 순회하며 각 조합으로 homology search 실행
      2) 각 search 결과(persistence dict)를 merge_persistence_dicts로 누적 통합
      3) 조합별 발견 cycle 수와 소요 시간을 summary에 기록
    반환: (통합 persistence dict, 조합별 요약 리스트)
    """
    all_persistence = {}
    results_summary = []

    for i, (stype, lag, dim, power) in enumerate(configs):
        label = f"{stype}/lag{lag}/dim{dim}"
        if verbose:
            print(f"\n  [{i+1}/{len(configs)}] {label} (power={power})")

        t0 = time.time()

        # 임시로 power 변경 후 search 실행, 완료 후 원복
        original_power = pipeline.config.homology.power
        pipeline.config.homology.power = power

        try:
            pipeline.run_homology_search(
                search_type=stype, lag=lag, dimension=dim
            )
        except Exception as e:
            print(f"    ✗ 실패: {e}")
            pipeline.config.homology.power = original_power
            continue

        pipeline.config.homology.power = original_power

        # 해당 조합의 persistence 결과를 캐시에서 가져와 통합
        key = f"h{dim}_{stype}_lag{lag}"
        persistence = pipeline._cache.get(key, {})
        n_cycles = len(persistence)
        dt = time.time() - t0

        all_persistence = merge_persistence_dicts(all_persistence, persistence)

        results_summary.append({
            'config': label,
            'cycles': n_cycles,
            'time': dt
        })

        if verbose:
            print(f"    → {n_cycles}개 cycle ({dt:.1f}s)")

    return all_persistence, results_summary


if __name__ == "__main__":
    print("=" * 60)
    print("  다중 Search 조합 통합 탐색")
    print("=" * 60)

    # ── 메인 흐름 ──
    # 전처리 → 12개 search 조합 실행 → cycle 통합 → 중첩행렬 → cycle 선택 → 음악 생성

    config = PipelineConfig()
    pipeline = TDAMusicPipeline(config)

    # Stage 1: 전처리 — MIDI → 화음/note 레이블링
    print("\n[Stage 1] 전처리...")
    pipeline.run_preprocessing()

    # ── 탐색 조합 정의 ──
    # (search_type, lag, dim, power) 형태의 튜플 리스트
    # - search_type: 거리 행렬 구축 방식 (timeflow/simul/complex)
    # - lag: 시간 지연 단위 (timeflow에서 1~4 사용)
    # - dim: homology 차원 (1=cycle, 2=void)
    # - power: rate 탐색 해상도 (step = 10^power, -2→0.01 세밀, -1→0.1 거친)
    search_configs = []

    # Timeflow: 시간 흐름 기반 거리, lag=1~4 각각에 대해 dim=1(세밀), dim=2(거친)
    for lag in [1, 2, 3, 4]:
        search_configs.append(('timeflow', lag, 1, -2))  # dim=1: step=0.01 (150 evaluations)
        search_configs.append(('timeflow', lag, 2, -1))  # dim=2: step=0.1 (15 evaluations, 계산 부하 절감)

    # Simul: 동시 발음 기반 거리, lag 무관하므로 lag=1 고정
    search_configs.append(('simul', 1, 1, -2))
    search_configs.append(('simul', 1, 2, -1))

    # Complex: timeflow+simul 복합 거리, dim=1만 (dim=2는 너무 오래 걸림)
    search_configs.append(('complex', 1, 1, -2))
    search_configs.append(('complex', 2, 1, -2))

    # 총 12개 조합: timeflow 8 + simul 2 + complex 2

    print(f"\n[Stage 2] {len(search_configs)}개 탐색 조합 실행")
    t_total = time.time()

    all_persistence, summary = run_search_batch(pipeline, search_configs)

    dt_total = time.time() - t_total

    # ── 요약 ──
    print(f"\n{'='*60}")
    print(f"  탐색 요약")
    print(f"{'='*60}")
    print(f"\n  {'Config':<25s} | {'Cycles':>6s} | {'Time':>6s}")
    print(f"  {'-'*25} | {'-'*6} | {'-'*6}")
    for r in summary:
        print(f"  {r['config']:<25s} | {r['cycles']:6d} | {r['time']:5.1f}s")

    print(f"\n  통합 고유 cycle: {len(all_persistence)}개")
    print(f"  총 탐색 시간: {dt_total:.0f}s ({dt_total/60:.1f}분)")

    # dim별 cycle 수 — vertex 개수로 H1(3+)과 H2(4+)를 구분
    dim1_cycles = {k for k in all_persistence.keys() if len(k) >= 3}
    dim2_cycles = {k for k in all_persistence.keys() if len(k) >= 4}
    print(f"  H1 cycle (len≥3): {len(dim1_cycles)}개")
    print(f"  H2 void (len≥4): {len(dim2_cycles)}개")

    # ── Stage 3: 통합 중첩행렬 ──
    print(f"\n{'='*60}")
    print(f"  통합 중첩행렬 구축")
    print(f"{'='*60}")

    # persistence dict에서 cycle별 정수 레이블 부여
    cycle_labeled_raw = label_cycles_from_persistence(all_persistence)

    # dim=2의 cycle은 frozenset(simplex들의 집합) 형태로 저장됨
    # → generation 코드가 tuple(vertex 인덱스)을 기대하므로 변환 필요
    # frozenset({(1,2), (2,3), (1,3)}) → tuple(sorted({1,2,3})) = (1,2,3)
    cycle_labeled = {}
    for label, cycle in cycle_labeled_raw.items():
        if isinstance(cycle, frozenset):
            # frozenset 내의 simplex들에서 vertex를 추출하여 정렬된 tuple로 변환
            verts = set()
            for simplex in cycle:
                if isinstance(simplex, tuple):
                    verts.update(simplex)
                else:
                    verts.add(simplex)
            cycle_labeled[label] = tuple(sorted(verts))
        else:
            cycle_labeled[label] = cycle

    print(f"  총 cycle: {len(cycle_labeled)}개")

    # Note-time 이진 행렬 구축 — 각 시점에서 어떤 note가 활성화되는지
    adn_i = pipeline._cache['adn_i']
    notes_dict = pipeline._cache['notes_dict']
    num_notes = pipeline.config.midi.num_notes

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    nodes_list = list(range(1, num_notes + 1))
    T = config.overlap.total_length
    note_time_data = np.zeros((T, len(nodes_list)), dtype=int)
    for t in range(min(T, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    note_time_data[t, nodes_list.index(n)] = 1
    note_time_df = pd.DataFrame(note_time_data, columns=nodes_list)

    # 활성화 행렬(cycle이 각 시점에서 활성인지) → 이진 중첩행렬
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(
        activation, cycle_labeled,
        threshold=config.overlap.threshold,
        total_length=T
    )

    print(f"  Overlap matrix: {overlap.shape}")
    on_ratio = overlap.values.sum() / overlap.size
    print(f"  ON ratio: {on_ratio:.4f}")

    # ── Cycle Selection — preservation score 기반으로 최적 K 결정 ──
    print(f"\n{'='*60}")
    print(f"  Cycle Subset 선택")
    print(f"{'='*60}")

    selector = CycleSubsetSelector(overlap.values, cycle_labeled)

    # 전체 cycle에 대한 preservation curve 계산
    result_full = selector.select_fixed_size(len(cycle_labeled), verbose=False)

    # preservation score가 90%에 도달하는 최소 K 탐색
    target_k = None
    for i, s in enumerate(result_full.preservation_curve):
        if s >= 0.90:
            target_k = i + 1
            break

    # 주요 K 지점에서의 metric 출력
    print(f"\n  K | Score  | Jaccard | Corr  | Betti")
    print(f"  --|--------|---------|-------|------")
    milestones = [1, 3, 5, 10, 15, 20, 30]
    milestones = [m for m in milestones if m <= len(cycle_labeled)]
    milestones.append(len(cycle_labeled))
    for k in milestones:
        idx = k - 1
        j = result_full.component_curves['jaccard'][idx]
        c = result_full.component_curves['correlation'][idx]
        b = result_full.component_curves['betti'][idx]
        s = result_full.preservation_curve[idx]
        marker = " ← 90%" if target_k and k == target_k else ""
        print(f"  {k:2d} | {s:.4f} | {j:.4f}  | {c:.4f} | {b:.4f}{marker}")

    if target_k:
        print(f"\n  90% 보존도 도달: K={target_k}")

    # ── 음악 생성 — target_k(부분집합)와 전체 cycle 두 가지로 생성 ──
    print(f"\n{'='*60}")
    print(f"  음악 생성")
    print(f"{'='*60}")

    # pipeline 캐시에 통합 cycle 정보 설정
    pipeline._cache['cycle_labeled'] = cycle_labeled
    pipeline._cache['overlap_matrix'] = overlap

    for k_val, label in [(target_k, f"K{target_k}_multi"), (None, f"K{len(cycle_labeled)}_multi")]:
        if k_val is not None:
            # 부분집합 선택 전에 전체 cycle로 캐시 복원
            pipeline._cache['cycle_labeled'] = cycle_labeled
            pipeline._cache['overlap_matrix'] = overlap
            pipeline.run_cycle_selection(k=k_val, verbose=False)

        generated = pipeline.run_generation_algo1(
            file_suffix=f"_{label}",
            verbose=False
        )
        pitches = set(p for _, p, _ in generated)
        print(f"  {label}: {len(generated)} notes, {len(pitches)} pitches")

        # 다음 생성을 위해 전체 cycle로 캐시 복원
        pipeline._cache['cycle_labeled'] = cycle_labeled
        pipeline._cache['overlap_matrix'] = overlap

    # MIDI 변환 — musicxml → mid
    print(f"\n  MIDI 변환 중...")
    try:
        from music21 import converter
        import glob
        for f in glob.glob('output/algo1_*_multi_*.musicxml'):
            score = converter.parse(f)
            midi_path = f.replace('.musicxml', '.mid')
            score.write('midi', fp=midi_path)
            print(f"    {os.path.basename(f)} → .mid")
    except Exception as e:
        print(f"    MIDI 변환 실패: {e}")

    print(f"\n{'='*60}")
    print("  완료")
    print(f"{'='*60}")
