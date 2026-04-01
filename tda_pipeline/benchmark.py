"""
TDA Music Pipeline - 벤치마크 (기존 vs 최적화)
================================================
기존 방식(WK14)과 새 파이프라인의 소요시간을 단계별로 비교합니다.

사용법:
    python benchmark.py

필요한 파일:
    - Ryuichi_Sakamoto_-_hibari.mid
    - professor.py
    - pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl
    
    # 기존 코드 (../에 WK14 폴더가 있어야 함)
    - ../process.py  또는  ../WK14/process.py
    - ../util.py     또는  ../WK14/util.py
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from collections import Counter

# 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# 기존 코드 경로 탐색
OLD_CODE_DIR = None
for candidate in [PARENT_DIR, os.path.join(PARENT_DIR, 'WK14')]:
    if os.path.exists(os.path.join(candidate, 'process.py')) and \
       os.path.exists(os.path.join(candidate, 'util.py')):
        OLD_CODE_DIR = candidate
        break


def format_time(seconds):
    if seconds < 0.001:
        return f"{seconds*1_000_000:.0f} μs"
    elif seconds < 1:
        return f"{seconds*1000:.2f} ms"
    else:
        return f"{seconds:.3f} s"


def benchmark_preprocessing():
    """전처리 단계 비교"""
    print("\n" + "─" * 60)
    print("벤치마크 1: 전처리 (MIDI → 화음 시퀀스 → note 레이블링)")
    print("─" * 60)

    midi_file = os.path.join(SCRIPT_DIR, "Ryuichi_Sakamoto_-_hibari.mid")
    if not os.path.exists(midi_file):
        print("  ⚠ MIDI 파일을 찾을 수 없습니다.")
        return None, None

    results = {}

    # ── 기존 방식 ──
    if OLD_CODE_DIR:
        sys.path.insert(0, OLD_CODE_DIR)
        try:
            # 기존 모듈 임포트 (캐시 방지를 위해 reload)
            import importlib
            if 'process' in sys.modules:
                importlib.reload(sys.modules['process'])
            if 'util' in sys.modules:
                importlib.reload(sys.modules['util'])

            from process import (adjust_to_eighth_note, label_active_chord_by_onset,
                                 get_ready_with_lags, group_notes_with_duration_,
                                 notes_label_n_counts, chord_label_dict,
                                 chord_label_to_note_labels)

            t0 = time.perf_counter()

            old_adjusted, old_tempo = adjust_to_eighth_note(midi_file)
            adn_1 = old_adjusted[:2006]
            adn_2 = old_adjusted[2006:]
            adn_1_real = adn_1[:-59]
            adn_2_real = adn_2[59:]
            adn_1_chord = label_active_chord_by_onset(adn_1_real)
            adn_2_chord = label_active_chord_by_onset(adn_2_real)
            adn_i_old = get_ready_with_lags(adn_1_chord, adn_2_chord)
            module_notes_old = adn_1_real[:59]
            active_module_old = group_notes_with_duration_(module_notes_old)
            notes_label_old, notes_counts_old = notes_label_n_counts(module_notes_old)
            chord_label_old = chord_label_dict(active_module_old)
            notes_dict_old = chord_label_to_note_labels(chord_label_old, notes_label_old)
            notes_dict_old['name'] = 'notes'

            t_old = time.perf_counter() - t0
            results['old'] = t_old
            print(f"  기존 방식: {format_time(t_old)}")

        except Exception as e:
            print(f"  기존 방식 실행 실패: {e}")
            results['old'] = None
        finally:
            sys.path.remove(OLD_CODE_DIR)
    else:
        print("  ⚠ 기존 코드(process.py, util.py)를 찾을 수 없습니다.")
        print(f"    탐색 경로: {PARENT_DIR}")
        results['old'] = None

    # ── 새 방식 ──
    from preprocessing import (load_and_quantize, split_instruments,
                                group_notes_with_duration, build_chord_labels,
                                build_note_labels, chord_to_note_labels)

    t0 = time.perf_counter()

    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]
    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, cs1 = build_chord_labels(active1)
    _, cs2 = build_chord_labels(active2)
    module_notes = inst1_real[:59]
    nl, nc = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    nd = chord_to_note_labels(cm, nl)
    nd['name'] = 'notes'

    t_new = time.perf_counter() - t0
    results['new'] = t_new
    print(f"  새 방식:   {format_time(t_new)}")

    if results['old'] and results['new']:
        ratio = results['old'] / results['new']
        print(f"  → {ratio:.1f}x {'빠름' if ratio > 1 else '느림'}")

    return results, {
        'inst1_real': inst1_real, 'inst2_real': inst2_real,
        'notes_label': nl, 'notes_counts': nc, 'notes_dict': nd,
        'chord_seq1': cs1, 'chord_seq2': cs2,
    }


def benchmark_refine_connectedness(data):
    """refine_connectedness 단계 비교 (가장 큰 병목)"""
    print("\n" + "─" * 60)
    print("벤치마크 2: refine_connectedness (화음→note 가중치 분해)")
    print("─" * 60)

    notes_dict = data['notes_dict']
    num_notes = len(data['notes_label'])
    results = {}

    # 테스트용 가중치 행렬 생성 (17×17)
    np.random.seed(42)
    test_weight = pd.DataFrame(
        np.random.randint(0, 100, (17, 17)),
        dtype=float
    )
    # 상삼각으로 변환
    for i in range(17):
        for j in range(i):
            test_weight.iloc[j, i] += test_weight.iloc[i, j]
            test_weight.iloc[i, j] = 0

    N_REPEAT = 20  # 반복 측정

    # ── 기존 방식 ──
    if OLD_CODE_DIR:
        sys.path.insert(0, OLD_CODE_DIR)
        try:
            import importlib
            if 'util' in sys.modules:
                importlib.reload(sys.modules['util'])
            from util import refine_connectedness as old_refine

            times = []
            for _ in range(N_REPEAT):
                w = test_weight.copy()
                t0 = time.perf_counter()
                old_refine(w, notes_dict, power=0)
                times.append(time.perf_counter() - t0)

            t_old = np.median(times)
            results['old'] = t_old
            print(f"  기존 방식 (중앙값, {N_REPEAT}회): {format_time(t_old)}")

        except Exception as e:
            print(f"  기존 방식 실행 실패: {e}")
            results['old'] = None
        finally:
            sys.path.remove(OLD_CODE_DIR)
    else:
        results['old'] = None

    # ── 새 방식 ──
    from weights import refine_connectedness_fast

    times = []
    for _ in range(N_REPEAT):
        w = test_weight.copy()
        t0 = time.perf_counter()
        refine_connectedness_fast(w, notes_dict, num_notes)
        times.append(time.perf_counter() - t0)

    t_new = np.median(times)
    results['new'] = t_new
    print(f"  새 방식   (중앙값, {N_REPEAT}회): {format_time(t_new)}")

    if results['old'] and results['new']:
        ratio = results['old'] / results['new']
        print(f"  → {ratio:.1f}x {'빠름' if ratio > 1 else '느림'}")

    return results


def benchmark_activation_matrix(data):
    """활성화 행렬 구축 비교"""
    print("\n" + "─" * 60)
    print("벤치마크 3: 활성화 행렬 구축 (get_scattered_cycles_df)")
    print("─" * 60)

    notes_dict = data['notes_dict']
    num_notes = len(data['notes_label'])
    results = {}

    # pickle에서 사이클 로드
    pkl_path = os.path.join(SCRIPT_DIR, "pickle", "h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    if not os.path.exists(pkl_path):
        print("  ⚠ pickle 파일을 찾을 수 없습니다.")
        return {}

    df = pd.read_pickle(pkl_path)
    persistence = {}
    for _, row in df.iterrows():
        persistence.setdefault(row['cycle'], []).append(
            (row['rate'], row['birth'], row['death'])
        )

    from overlap import label_cycles_from_persistence
    cycle_labeled = label_cycles_from_persistence(persistence)

    # Note-Time DataFrame 생성 (공통)
    from preprocessing import simul_chord_lists, simul_union_by_dict
    TOTAL_LENGTH = 1088

    cs1 = list(data['chord_seq1']) + [None] * 59
    cs2 = [None] * 59 + [None] + list(data['chord_seq2'])
    max_len = max(len(cs1), len(cs2))
    cs1.extend([None] * (max_len - len(cs1)))
    cs2.extend([None] * (max_len - len(cs2)))
    chord_pairs = simul_chord_lists(cs1[:TOTAL_LENGTH], cs2[:TOTAL_LENGTH])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    nodes_list = list(range(1, num_notes + 1))
    note_data = [[1 if col in ns else 0 for col in nodes_list] for ns in note_sets]
    note_time_df = pd.DataFrame(note_data, columns=nodes_list)

    N_REPEAT = 10

    # ── 기존 방식 ──
    if OLD_CODE_DIR:
        sys.path.insert(0, OLD_CODE_DIR)
        try:
            import importlib
            if 'util' in sys.modules:
                importlib.reload(sys.modules['util'])
            from util import get_scattered_cycles_df

            times = []
            for _ in range(N_REPEAT):
                t0 = time.perf_counter()
                get_scattered_cycles_df(note_time_df, cycle_labeled, binary=True)
                times.append(time.perf_counter() - t0)

            t_old = np.median(times)
            results['old'] = t_old
            print(f"  기존 방식 (중앙값, {N_REPEAT}회): {format_time(t_old)}")

        except Exception as e:
            print(f"  기존 방식 실행 실패: {e}")
            results['old'] = None
        finally:
            sys.path.remove(OLD_CODE_DIR)
    else:
        results['old'] = None

    # ── 새 방식 ──
    from overlap import build_activation_matrix

    times = []
    for _ in range(N_REPEAT):
        t0 = time.perf_counter()
        build_activation_matrix(note_time_df, cycle_labeled)
        times.append(time.perf_counter() - t0)

    t_new = np.median(times)
    results['new'] = t_new
    print(f"  새 방식   (중앙값, {N_REPEAT}회): {format_time(t_new)}")

    if results['old'] and results['new']:
        ratio = results['old'] / results['new']
        print(f"  → {ratio:.1f}x {'빠름' if ratio > 1 else '느림'}")

    return results


def benchmark_overlap_construction(data):
    """전체 중첩행렬 구축 비교 (Step 3 전체)"""
    print("\n" + "─" * 60)
    print("벤치마크 4: 중첩행렬 전체 구축 (evaluate_threshold)")
    print("─" * 60)

    notes_dict = data['notes_dict']
    num_notes = len(data['notes_label'])
    THRESHOLD = 0.35
    TOTAL_LENGTH = 1088
    results = {}

    # pickle 로드
    pkl_path = os.path.join(SCRIPT_DIR, "pickle", "h1_rBD_t_notes1_1e-4_0.0~1.5.pkl")
    if not os.path.exists(pkl_path):
        print("  ⚠ pickle 파일 없음")
        return {}

    df = pd.read_pickle(pkl_path)
    persistence = {}
    for _, row in df.iterrows():
        persistence.setdefault(row['cycle'], []).append(
            (row['rate'], row['birth'], row['death'])
        )

    from overlap import label_cycles_from_persistence
    cycle_labeled = label_cycles_from_persistence(persistence)

    # 공통 DataFrame
    from preprocessing import simul_chord_lists, simul_union_by_dict
    cs1 = list(data['chord_seq1']) + [None] * 59
    cs2 = [None] * 59 + [None] + list(data['chord_seq2'])
    max_len = max(len(cs1), len(cs2))
    cs1.extend([None] * (max_len - len(cs1)))
    cs2.extend([None] * (max_len - len(cs2)))
    chord_pairs = simul_chord_lists(cs1[:TOTAL_LENGTH], cs2[:TOTAL_LENGTH])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)

    nodes_list = list(range(1, num_notes + 1))
    note_data = [[1 if col in ns else 0 for col in nodes_list] for ns in note_sets]
    note_time_df = pd.DataFrame(note_data, columns=nodes_list)

    # ── 기존 방식 ──
    if OLD_CODE_DIR:
        sys.path.insert(0, OLD_CODE_DIR)
        try:
            import importlib
            for mod_name in ['util', 'process']:
                if mod_name in sys.modules:
                    importlib.reload(sys.modules[mod_name])
            from util import (get_scattered_cycles_df, get_cycles_scaled, 
                              construct_overlap_df, label_cycle)

            # 기존 label_cycle
            cl_old, _, _ = label_cycle(persistence, notes_dict, info=False, log=False)

            t0 = time.perf_counter()
            cw_old = get_scattered_cycles_df(note_time_df, cl_old, binary=True)
            fo_old = get_cycles_scaled(cw_old, cl_old, THRESHOLD, None)
            oc_old = construct_overlap_df(fo_old, length=TOTAL_LENGTH)
            t_old = time.perf_counter() - t0

            results['old'] = t_old
            results['old_shape'] = oc_old.shape
            results['old_on'] = oc_old.values.sum() / oc_old.size
            print(f"  기존 방식: {format_time(t_old)}  (shape={oc_old.shape}, ON={results['old_on']:.4f})")

        except Exception as e:
            print(f"  기존 방식 실행 실패: {e}")
            import traceback
            traceback.print_exc()
            results['old'] = None
        finally:
            sys.path.remove(OLD_CODE_DIR)
    else:
        results['old'] = None

    # ── 새 방식 ──
    from overlap import build_activation_matrix, build_overlap_matrix

    t0 = time.perf_counter()
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    overlap = build_overlap_matrix(activation, cycle_labeled,
                                    threshold=THRESHOLD, total_length=TOTAL_LENGTH)
    t_new = time.perf_counter() - t0

    results['new'] = t_new
    results['new_shape'] = overlap.shape
    results['new_on'] = overlap.values.sum() / overlap.size
    print(f"  새 방식:   {format_time(t_new)}  (shape={overlap.shape}, ON={results['new_on']:.4f})")

    if results['old'] and results['new']:
        ratio = results['old'] / results['new']
        print(f"  → {ratio:.1f}x {'빠름' if ratio > 1 else '느림'}")

    return results


def print_summary(all_results):
    """최종 요약"""
    print("\n" + "═" * 60)
    print("벤치마크 요약")
    print("═" * 60)
    print(f"  {'단계':<30} {'기존':>10} {'새 코드':>10} {'배율':>8}")
    print("  " + "─" * 58)

    for name, res in all_results.items():
        if res is None:
            continue
        old = res.get('old')
        new = res.get('new')
        old_str = format_time(old) if old else "N/A"
        new_str = format_time(new) if new else "N/A"
        ratio_str = f"{old/new:.1f}x" if (old and new) else "─"
        print(f"  {name:<30} {old_str:>10} {new_str:>10} {ratio_str:>8}")

    print()
    if OLD_CODE_DIR:
        print(f"  기존 코드 위치: {OLD_CODE_DIR}")
    else:
        print("  ⚠ 기존 코드를 찾지 못해 비교 불가")
        print(f"    → process.py, util.py를 상위 폴더({PARENT_DIR})에 두세요")
    print()


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  TDA Music Pipeline - 성능 벤치마크           ║")
    print("║  기존 코드(WK14) vs 최적화 파이프라인 비교     ║")
    print("╚══════════════════════════════════════════════╝")

    if OLD_CODE_DIR:
        print(f"\n  기존 코드 발견: {OLD_CODE_DIR}")
    else:
        print(f"\n  ⚠ 기존 코드(process.py, util.py)를 찾을 수 없습니다.")
        print(f"    → 상위 폴더({PARENT_DIR})에 복사하면 비교가 가능합니다.")
        print(f"    → 새 코드만 단독 측정합니다.\n")

    all_results = {}

    # 벤치마크 1: 전처리
    res1, data = benchmark_preprocessing()
    all_results['1. 전처리'] = res1

    if data is None:
        print("\n  MIDI 파일이 없어 벤치마크를 중단합니다.")
        sys.exit(1)

    # 벤치마크 2: refine_connectedness
    res2 = benchmark_refine_connectedness(data)
    all_results['2. refine_connectedness'] = res2

    # 벤치마크 3: 활성화 행렬
    res3 = benchmark_activation_matrix(data)
    all_results['3. 활성화 행렬'] = res3

    # 벤치마크 4: 중첩행렬 전체
    res4 = benchmark_overlap_construction(data)
    all_results['4. 중첩행렬 전체'] = res4

    # 요약
    print_summary(all_results)
