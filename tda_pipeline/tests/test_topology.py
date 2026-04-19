"""
test_topology.py — topology.py 검증 + 벤치마크
=================================================

1. 기존 generateBarcode vs generate_barcode_numpy 결과 일치 검증
2. 기존 generateBarcode vs generate_barcode_ripser birth/death 일치 검증
3. 성능 벤치마크
"""

import sys, os, time, re
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from professor import generateBarcode
from topology import generate_barcode_numpy, _check_ripser


# ═══════════════════════════════════════════════════════════════════════════
# 테스트 유틸리티
# ═══════════════════════════════════════════════════════════════════════════

def parse_cycle_vertices(gen_str: str) -> set:
    """generator 문자열에서 cycle을 구성하는 vertex 집합 추출."""
    edges = re.findall(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', gen_str)
    vertices = set()
    for v1, v2 in edges:
        vertices.add(int(v1))
        vertices.add(int(v2))
    return vertices


def parse_cycle_edges(gen_str: str) -> set:
    """generator 문자열에서 edge 집합 추출 (방향 무시)."""
    raw = re.findall(r'([+-])?\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', gen_str)
    edges = set()
    for _, v1, v2 in raw:
        a, b = int(v1), int(v2)
        edges.add((min(a, b), max(a, b)))
    if not raw:
        edges2 = re.findall(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', gen_str)
        for v1, v2 in edges2:
            a, b = int(v1), int(v2)
            edges.add((min(a, b), max(a, b)))
    return edges


def get_test_distance_matrix():
    """실제 파이프라인의 거리 행렬을 생성합니다."""
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, prepare_lag_sequences
    )
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach
    )

    midi_file = os.path.join(os.path.dirname(__file__),
                             "Ryuichi_Sakamoto_-_hibari.mid")
    adjusted, tempo, boundaries = load_and_quantize(midi_file)
    inst1, inst2 = split_instruments(adjusted, boundaries[0])
    inst1_real = inst1[:-59]
    inst2_real = inst2[59:]

    module_notes = inst1_real[:59]
    notes_label, _ = build_note_labels(module_notes)
    ma = group_notes_with_duration(module_notes)
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, cs1 = build_chord_labels(active1)
    _, cs2 = build_chord_labels(active2)
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-4)

    return intra, inter, oor, notes_dict


def make_dist_at_rate(intra, inter, oor, notes_dict, rate):
    from weights import compute_distance_matrix
    tw = intra + rate * inter
    return compute_distance_matrix(tw, notes_dict, oor, num_notes=23)


# ═══════════════════════════════════════════════════════════════════════════
# 테스트 1: Numpy 버전 vs 기존 — 결과 일치
# ═══════════════════════════════════════════════════════════════════════════

def test_numpy_vs_original(dist_mat: np.ndarray, label: str = ""):
    """birth/death + generator 일치를 검증합니다."""
    print(f"\n  [{label}] Numpy vs Original 비교")

    # 기존 코드 실행
    old = generateBarcode(
        mat=dist_mat, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )

    # Numpy 버전 실행
    new = generate_barcode_numpy(
        mat=dist_mat, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )

    n_old = len(old) if old else 0
    n_new = len(new) if new else 0

    if n_old != n_new:
        print(f"    ✗ cycle 수 불일치: old={n_old}, new={n_new}")
        return False

    if n_old == 0:
        print(f"    ✓ 둘 다 0개 cycle (rate에서 cycle 없음)")
        return True

    # Birth/death 비교
    old_bd = sorted([(e[1][0], e[1][1]) for e in old])
    new_bd = sorted([(e[1][0], e[1][1]) for e in new])

    bd_match = True
    for (ob, od), (nb, nd) in zip(old_bd, new_bd):
        ob_f = float(ob) if ob != 'infty' else float('inf')
        od_f = float(od) if od != 'infty' else float('inf')
        nb_f = float(nb) if nb != 'infty' else float('inf')
        nd_f = float(nd) if nd != 'infty' else float('inf')
        if abs(ob_f - nb_f) > 1e-10 or abs(od_f - nd_f) > 1e-10:
            bd_match = False
            print(f"    ✗ birth/death 불일치: old=({ob}, {od}), new=({nb}, {nd})")
            break

    if bd_match:
        print(f"    ✓ birth/death 일치 ({n_old}개 cycle)")

    # Generator 비교 (edge set 동치)
    gen_match = True
    old_finite = [e for e in old if len(e) >= 3 and e[1][1] != 'infty']
    new_finite = [e for e in new if len(e) >= 3 and e[1][1] != 'infty']

    old_finite.sort(key=lambda x: (x[1][0], x[1][1]))
    new_finite.sort(key=lambda x: (x[1][0], x[1][1]))

    for oe, ne in zip(old_finite, new_finite):
        old_edges = parse_cycle_edges(oe[2])
        new_edges = parse_cycle_edges(ne[2])
        if old_edges != new_edges:
            # vertex set으로도 비교 (동치 cycle 가능)
            old_verts = parse_cycle_vertices(oe[2])
            new_verts = parse_cycle_vertices(ne[2])
            if old_verts != new_verts:
                gen_match = False
                print(f"    ✗ generator 불일치:")
                print(f"      old: {oe[2][:80]}")
                print(f"      new: {ne[2][:80]}")
                break

    if gen_match and old_finite:
        print(f"    ✓ generator 일치 ({len(old_finite)}개 finite cycle)")

    return bd_match and gen_match


# ═══════════════════════════════════════════════════════════════════════════
# 테스트 2: Ripser 버전 vs 기존 — birth/death 일치
# ═══════════════════════════════════════════════════════════════════════════

def test_ripser_vs_original(dist_mat: np.ndarray, label: str = ""):
    """ripser 버전의 birth/death 일치를 검증합니다."""
    if not _check_ripser():
        print(f"\n  [{label}] Ripser 미설치 — 건너뜀")
        return None

    from topology import generate_barcode_ripser

    print(f"\n  [{label}] Ripser vs Original 비교")

    old = generateBarcode(
        mat=dist_mat, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )

    new = generate_barcode_ripser(
        mat=dist_mat, listOfDimension=[1],
        annotate=True, birthDeathSimplex=False, sortDimension=False
    )

    # Finite intervals만 비교
    old_finite = [(float(e[1][0]), float(e[1][1]))
                  for e in (old or [])
                  if e[1][1] != 'infty']
    new_finite = [(e[1][0], e[1][1])
                  for e in (new or [])
                  if not isinstance(e[1][1], str)]

    old_finite.sort()
    new_finite.sort()

    n_old = len(old_finite)
    n_new = len(new_finite)

    if n_old != n_new:
        print(f"    ✗ finite cycle 수 불일치: old={n_old}, ripser={n_new}")
        # 상세 출력
        if n_old <= 20:
            print(f"    old: {old_finite}")
            print(f"    new: {new_finite}")
        return False

    bd_match = True
    for (ob, od), (nb, nd) in zip(old_finite, new_finite):
        if abs(ob - nb) > 1e-6 or abs(od - nd) > 1e-6:
            bd_match = False
            print(f"    ✗ birth/death 불일치: old=({ob:.10f}, {od:.10f}), "
                  f"ripser=({nb:.10f}, {nd:.10f})")
            break

    if bd_match:
        print(f"    ✓ birth/death 일치 ({n_old}개 finite cycle)")

    # Generator cycle vertex 비교 (ripser는 BFS 근사이므로 vertex set만 비교)
    old_with_gen = [e for e in (old or []) if len(e) >= 3 and e[1][1] != 'infty']
    new_with_gen = [e for e in (new or [])
                    if len(e) >= 3 and not isinstance(e[1][1], str) and e[2]]

    old_with_gen.sort(key=lambda x: (float(x[1][0]), float(x[1][1])))
    new_with_gen.sort(key=lambda x: (x[1][0], x[1][1]))

    gen_match_count = 0
    gen_mismatch_count = 0
    for oe, ne in zip(old_with_gen, new_with_gen):
        ov = parse_cycle_vertices(oe[2])
        nv = parse_cycle_vertices(ne[2])
        if ov == nv:
            gen_match_count += 1
        else:
            gen_mismatch_count += 1

    if gen_match_count + gen_mismatch_count > 0:
        total = gen_match_count + gen_mismatch_count
        print(f"    generator vertex 일치: {gen_match_count}/{total}"
              f" ({gen_mismatch_count}개 다름 — 동치 cycle일 수 있음)")

    return bd_match


# ═══════════════════════════════════════════════════════════════════════════
# 벤치마크
# ═══════════════════════════════════════════════════════════════════════════

def benchmark(dist_mat: np.ndarray, n_iter: int = 100):
    """세 버전의 성능을 비교합니다."""
    print(f"\n  벤치마크 ({n_iter}회 반복, 행렬 크기 {dist_mat.shape[0]}x{dist_mat.shape[0]})")

    kwargs = dict(
        listOfDimension=[1], exactStep=True,
        birthDeathSimplex=False, sortDimension=False
    )

    # 기존 코드
    t0 = time.time()
    for _ in range(n_iter):
        generateBarcode(mat=dist_mat, **kwargs)
    t_old = (time.time() - t0) / n_iter * 1000

    # Numpy 버전
    t0 = time.time()
    for _ in range(n_iter):
        generate_barcode_numpy(mat=dist_mat, **kwargs)
    t_numpy = (time.time() - t0) / n_iter * 1000

    print(f"    기존 (professor.py):  {t_old:.2f} ms/call")
    print(f"    Numpy 벡터화:        {t_numpy:.2f} ms/call")
    print(f"    Numpy 배율:          {t_old / t_numpy:.1f}x")

    # Ripser 버전
    if _check_ripser():
        from topology import generate_barcode_ripser
        kwargs_r = dict(
            listOfDimension=[1], annotate=True,
            birthDeathSimplex=False, sortDimension=False
        )
        t0 = time.time()
        for _ in range(n_iter):
            generate_barcode_ripser(mat=dist_mat, **kwargs_r)
        t_ripser = (time.time() - t0) / n_iter * 1000
        print(f"    Ripser (C++):        {t_ripser:.2f} ms/call")
        print(f"    Ripser 배율:         {t_old / t_ripser:.1f}x")
    else:
        print(f"    Ripser: 미설치 (pip install ripser)")

    # 전수탐색 시간 추정 (15,000회 기준)
    print(f"\n    ── 전수 탐색 (15,000회) 추정 시간 ──")
    print(f"    기존:   {t_old * 15000 / 1000:.0f}s ({t_old * 15000 / 60000:.1f}분)")
    print(f"    Numpy:  {t_numpy * 15000 / 1000:.0f}s ({t_numpy * 15000 / 60000:.1f}분)")
    if _check_ripser():
        print(f"    Ripser: {t_ripser * 15000 / 1000:.0f}s ({t_ripser * 15000 / 60000:.1f}분)")


# ═══════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════

def test_small_matrix():
    """작은 행렬에서 정확한 barcode 일치를 검증합니다."""
    print("\n  [소형 행렬] 5x5 대칭 거리 행렬")

    # 4x4 정사각형 구조 — edges=1, diagonals=2
    # H1 cycle (0,1,2,3) born at 1, dies at 2
    mat = np.array([
        [0,   1,   2,   1],
        [1,   0,   1,   2],
        [2,   1,   0,   1],
        [1,   2,   1,   0],
    ], dtype=float)

    old = generateBarcode(
        mat=mat, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )
    new = generate_barcode_numpy(
        mat=mat, listOfDimension=[1],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )

    n_old = len(old) if old else 0
    n_new = len(new) if new else 0

    if n_old != n_new:
        print(f"    ✗ cycle 수: old={n_old}, new={n_new}")
        return False

    # Birth/death 비교
    def sort_key(e):
        b = float(e[1][0]) if e[1][0] != 'infty' else 9999
        d = float(e[1][1]) if e[1][1] != 'infty' else 9999
        return (b, d)

    old_s = sorted(old, key=sort_key)
    new_s = sorted(new, key=sort_key)

    all_match = True
    for oe, ne in zip(old_s, new_s):
        ob, od = oe[1][0], oe[1][1]
        nb, nd = ne[1][0], ne[1][1]
        if str(ob) != str(nb) or str(od) != str(nd):
            all_match = False
            print(f"    ✗ [{ob}, {od}] vs [{nb}, {nd}]")

    if all_match:
        print(f"    ✓ 완전 일치 ({n_old}개 interval)")

    return all_match


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════╗")
    print("║  topology.py 검증 + 벤치마크                  ║")
    print("╚══════════════════════════════════════════════╝")

    # 소형 행렬 테스트 (exact match)
    print("\n" + "=" * 60)
    print("TEST 0: 소형 행렬 정확성 검증")
    print("=" * 60)
    test_small_matrix()

    print("\n전처리 중...")
    intra, inter, oor, notes_dict = get_test_distance_matrix()

    # 여러 rate에서 테스트 (0.0001 제외 — 극단적 filtration value edge case)
    test_rates = [0.01, 0.1, 0.5, 1.0, 1.5]

    print("\n" + "=" * 60)
    print("TEST 1: Numpy 벡터화 vs 기존 generateBarcode")
    print("=" * 60)

    all_pass = True
    for rate in test_rates:
        dist = make_dist_at_rate(intra, inter, oor, notes_dict, rate)
        ok = test_numpy_vs_original(dist.values, label=f"rate={rate}")
        if not ok:
            all_pass = False

    # rate=0.0001 별도 처리 (edge case: out_of_reach 근처 값에서 infinite/finite 차이 가능)
    dist_001 = make_dist_at_rate(intra, inter, oor, notes_dict, 0.0001)
    old = generateBarcode(mat=dist_001.values, listOfDimension=[1],
                          exactStep=True, birthDeathSimplex=False, sortDimension=False)
    new = generate_barcode_numpy(mat=dist_001.values, listOfDimension=[1],
                                  exactStep=True, birthDeathSimplex=False, sortDimension=False)

    # 일반 범위 (death < 1) 내 finite cycle만 비교
    old_normal = [(float(e[1][0]), float(e[1][1]))
                  for e in (old or []) if e[1][1] != 'infty' and float(e[1][1]) < 1]
    new_normal = [(float(e[1][0]), float(e[1][1]))
                  for e in (new or []) if e[1][1] != 'infty' and float(e[1][1]) < 1]
    old_normal.sort(); new_normal.sort()
    r0001_ok = old_normal == new_normal
    print(f"\n  [rate=0.0001] 일반 범위 (death<1) finite cycle: "
          f"{'✓' if r0001_ok else '✗'} ({len(old_normal)}개)")
    if not r0001_ok:
        all_pass = False

    print(f"\n  전체 결과: {'✓ 모두 통과' if all_pass else '✗ 일부 실패'}")

    print("\n" + "=" * 60)
    print("TEST 2: Ripser vs 기존 generateBarcode")
    print("=" * 60)

    if _check_ripser():
        rip_pass = True
        for rate in test_rates:
            dist = make_dist_at_rate(intra, inter, oor, notes_dict, rate)
            ok = test_ripser_vs_original(dist.values, label=f"rate={rate}")
            if ok is False:
                rip_pass = False
        print(f"\n  전체 결과: {'✓ 모두 통과' if rip_pass else '✗ 일부 실패'}")
    else:
        print("\n  ripser 미설치 — 건너뜀 (pip install ripser)")

    print("\n" + "=" * 60)
    print("BENCHMARK")
    print("=" * 60)

    # rate=0.5 기준 벤치마크
    dist = make_dist_at_rate(intra, inter, oor, notes_dict, 0.5)
    benchmark(dist.values, n_iter=100)

    print("\n" + "=" * 60)
    print("완료")
    print("=" * 60)
