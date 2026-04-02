"""
topology.py — professor.py의 generateBarcode 최적화 래퍼
================================================================

두 가지 방향의 최적화를 제공합니다:
1. generate_barcode_numpy  : 기존 pHcol 알고리즘 + numpy 벡터화
2. generate_barcode_ripser : ripser(C++) + cycle representative 추출

둘 다 기존 generateBarcode와 동일한 출력 형식을 보장합니다:
    [dimension, [birth_time, death_time], generator_string]
"""

import numpy as np
import itertools as it
from collections import defaultdict
from typing import List, Tuple, Optional, Dict


# ═══════════════════════════════════════════════════════════════════════════
# 방향 1: Numpy 벡터화 버전
# ═══════════════════════════════════════════════════════════════════════════

def generate_barcode_numpy(mat: np.ndarray,
                           listOfDimension: list = [1],
                           exactStep: bool = True,
                           annotate: bool = True,
                           onlyFiniteInterval: bool = False,
                           birthDeathSimplex: bool = False,
                           sortDimension: bool = False) -> list:
    """
    기존 generateBarcode와 동일한 결과를 내는 numpy 최적화 버전.

    최적화 포인트:
    - filtration times: np.unique 벡터 연산
    - VR complex: 행렬 인덱싱으로 diameter 일괄 계산
    - pHcol: set 기반 column operation
    """
    n = len(mat)
    max_dim = max(listOfDimension)

    # ══════════════════════════════════════════════════════
    # 단계 1: Filtration times 추출 (벡터화)
    # ══════════════════════════════════════════════════════
    # 거리 행렬의 상삼각+대각선에서 고유한 양수 값들을 추출한다.
    # 이 값들이 simplex가 등장하는 시점(filtration value)이 된다.
    if exactStep:
        # 상삼각 + 대각선에서 고유값 추출 (기존 distancesOfMatrix)
        triu_idx = np.triu_indices(n)
        vals = mat[triu_idx]
        filt_times = np.unique(vals)
        filt_times = filt_times[filt_times > 0]  # 0은 자기 자신과의 거리이므로 제외
        filt_times = filt_times.tolist()
    else:
        raise NotImplementedError("exactStep=False는 미지원")

    if not filt_times:
        return []

    # ══════════════════════════════════════════════════════
    # 단계 2: Vietoris-Rips 복합체 구축 (벡터화)
    # ══════════════════════════════════════════════════════
    # 각 filtration time마다 해당 시점에 등장하는 simplex들을 수집한다.
    # simplex의 diameter = 구성 꼭짓점 쌍 중 최대 거리.
    # diameter가 t인 simplex는 시점 t에 등장한다.

    # 0-simplex(꼭짓점)는 항상 시점 0에 존재
    simplices_by_step: Dict[float, list] = {0: [(i,) for i in range(n)]}
    for t in filt_times:
        simplices_by_step.setdefault(t, [])

    # onlyFiniteInterval이면 필요한 차원만 계산하여 불필요한 조합 생성 방지
    if onlyFiniteInterval:
        dims_needed = set()
        for d in listOfDimension:
            dims_needed.add(d)       # cycle을 감지하려면 해당 차원 필요
            dims_needed.add(d + 1)   # cycle을 "죽이려면" 한 차원 높은 simplex 필요
        dims_needed = sorted(dims_needed)
    else:
        dims_needed = list(range(1, max_dim + 2))

    filt_arr = np.array(filt_times)

    for dim in dims_needed:
        k = dim + 1  # simplex의 꼭짓점 개수 (예: 1-simplex=edge → k=2)
        if k > n:
            continue

        if k == 2:
            # Edge(1-simplex): 가장 빈번하므로 행렬 인덱싱으로 벡터화
            # 상삼각의 모든 (i,j) 쌍이 edge 후보
            ii, jj = np.triu_indices(n, k=1)
            diameters = mat[ii, jj]  # edge의 diameter = 양 끝점 거리
            for idx in range(len(ii)):
                d = diameters[idx]
                if d <= 0:
                    continue
                simplices_by_step.setdefault(d, []).append((int(ii[idx]), int(jj[idx])))
        elif k == 3:
            # Triangle(2-simplex): 세 변의 최대 길이가 diameter
            combos = np.array(list(it.combinations(range(n), 3)))
            if len(combos) == 0:
                continue
            i0, i1, i2 = combos[:, 0], combos[:, 1], combos[:, 2]
            d01 = mat[i0, i1]  # 변 (0,1) 길이
            d02 = mat[i0, i2]  # 변 (0,2) 길이
            d12 = mat[i1, i2]  # 변 (1,2) 길이
            diameters = np.maximum(np.maximum(d01, d02), d12)  # 세 변 중 최대

            for idx in range(len(combos)):
                d = diameters[idx]
                if d <= 0:
                    continue
                simplices_by_step.setdefault(d, []).append(tuple(int(x) for x in combos[idx]))
        else:
            # 4-simplex 이상: 조합 수가 적으므로 itertools 사용
            for tup in it.combinations(range(n), k):
                d = max(mat[i, j] for (i, j) in it.combinations(tup, 2))
                if d <= 0:
                    continue
                simplices_by_step.setdefault(d, []).append(tup)

    # filtration 순서대로 정렬: 시점 0(꼭짓점) → 오름차순 filtration time
    ordered_steps = [0] + filt_times
    simplex_with_step = []
    for step in ordered_steps:
        slist = simplices_by_step.get(step, [])
        if slist:
            simplex_with_step.append((step, slist))

    # ══════════════════════════════════════════════════════
    # 단계 3: Column labels + Boundary matrix 구축
    # ══════════════════════════════════════════════════════
    # 각 simplex에 열 번호를 부여하고, 경계 연산자(boundary operator)를 구성한다.
    # boundary(σ) = σ의 (dim-1)차 면(face)들의 교대합(alternating sum).
    # 예: boundary(triangle ABC) = BC - AC + AB

    col_labels = []       # [(filtration_time, simplex_tuple), ...] — 열 번호 → simplex 매핑
    simplex_to_col = {}   # simplex_tuple → 열 번호 역매핑
    col_idx = 0

    for step, slist in simplex_with_step:
        for s in slist:
            col_labels.append((step, s))
            simplex_to_col[s] = col_idx
            col_idx += 1

    total_cols = len(col_labels)

    # Boundary matrix를 희소(sparse) 표현으로 구축
    # D_rows[col] = 해당 열의 비제로 행 인덱스 리스트
    # D_vals[col] = {행 인덱스: 계수(±1)} — 교대 부호
    # None = 영벡터 열 (birth 후보), _SKIP = 관심 차원 밖 (무시)
    _SKIP = "SKIP"
    dim_filter = set(listOfDimension) if onlyFiniteInterval else set(range(max_dim + 2))

    D_rows = [None] * total_cols
    D_vals = [None] * total_cols

    for c in range(total_cols):
        _, simplex = col_labels[c]
        sdim = len(simplex) - 2  # boundary의 homology 차원 (simplex 차원 - 1)
        if sdim not in dim_filter:
            D_rows[c] = _SKIP  # 관심 차원 밖이면 건너뜀
            D_vals[c] = _SKIP
            continue
        if len(simplex) <= 1:
            # 0-simplex(꼭짓점)는 경계가 없음 → 영벡터 → H0 birth 후보
            D_rows[c] = None
            D_vals[c] = None
            continue

        # 경계 연산자 계산: 각 면(face)에 교대 부호((-1)^e)를 부여
        rows = []
        vals = {}
        for e, face in enumerate(it.combinations(simplex, len(simplex) - 1)):
            if face in simplex_to_col:
                r = simplex_to_col[face]
                rows.append(r)
                vals[r] = (-1) ** (e + 1)  # 교대 부호: +1, -1, +1, ...

        if rows:
            D_rows[c] = rows
            D_vals[c] = vals
        else:
            D_rows[c] = None
            D_vals[c] = None

    # ══════════════════════════════════════════════════════
    # 단계 4: pHcol 알고리즘 (Persistent Homology Column 축소)
    # ══════════════════════════════════════════════════════
    # 경계 행렬을 열 단위로 축소(reduce)하여 persistent interval을 추출한다.
    # 핵심: 각 열의 "pivot" (최하단 비제로 원소)가 고유해질 때까지 열 덧셈 반복.
    # - pivot이 없는 열(영벡터) → homology class 탄생 (birth)
    # - pivot이 있는 열 → 해당 birth를 소멸시킴 (death)

    births = []           # birth 열 인덱스 목록
    finite_births = set() # death에 의해 소멸된 birth 열 인덱스 집합
    low_R = {}            # low_R[pivot_row] = 해당 pivot을 가진 열 인덱스
    low_R_val = {}        # low_R_val[pivot_row] = pivot 위치의 계수
    barcode = []

    col_simplex_list = [cl[1] for cl in col_labels]  # 열 번호 → simplex 빠른 조회용

    for e in range(total_cols):
        rows = D_rows[e]
        vals = D_vals[e]

        if rows is _SKIP:
            # 관심 차원 밖의 열은 건너뜀
            continue

        if rows is None:
            # 영벡터 열 → homology class 탄생 (birth)
            births.append(e)
            continue

        # 현재 열의 pivot (가장 큰 행 인덱스) 찾기
        pivot = max(rows)
        coeff = vals[pivot]

        # 열 축소(column reduction): 같은 pivot을 가진 기존 열이 있으면 빼서 제거
        while pivot in low_R:
            j = low_R[pivot]       # 같은 pivot을 가진 기존 열
            jc = low_R_val[pivot]  # 기존 열의 pivot 계수
            c = -coeff / jc        # pivot을 상쇄하기 위한 스칼라 배수

            j_rows = D_rows[j]
            j_vals = D_vals[j]

            # 희소 열 덧셈: D[e] += c * D[j] (pivot 상쇄 목적)
            new_vals = dict(vals)
            for r in j_rows:
                if r in new_vals:
                    nv = new_vals[r] + c * j_vals[r]
                    if nv == 0:
                        del new_vals[r]  # 상쇄되어 0이 되면 제거
                    else:
                        new_vals[r] = nv
                else:
                    new_vals[r] = c * j_vals[r]

            if not new_vals:
                # 열이 완전히 영벡터가 됨 → birth로 전환
                rows = None
                vals = None
                pivot = -1
                break

            # 새로운 pivot 계산 후 다시 검사
            rows = list(new_vals.keys())
            vals = new_vals
            pivot = max(rows)
            coeff = vals[pivot]

        # 축소된 열 저장
        D_rows[e] = rows
        D_vals[e] = vals

        if rows is None:
            # 축소 결과 영벡터 → birth
            births.append(e)
            continue

        # pivot이 남아있으면 → 이 열이 birth를 소멸시킴 (death)
        low_R[pivot] = e
        low_R_val[pivot] = coeff

        # Finite interval(유한 구간) 추출: [birth_time, death_time]
        finite_births.add(pivot)  # pivot 위치의 birth가 소멸됨을 기록
        step_e, simplex_e = col_labels[e]
        dim_e = len(simplex_e) - 2  # homology 차원 (death simplex 차원 - 1)

        if dim_e not in listOfDimension:
            continue

        birth_simplex = col_labels[pivot][1]
        birth_step = col_labels[pivot][0]
        death_step = step_e

        # 기존 코드의 두 가지 경우:
        # 1) birth simplex가 vertex → birth time = 0 (H0의 connected component)
        # 2) birth step != death step → 일반 finite interval
        if len(birth_simplex) == 1:
            # 꼭짓점에서 탄생 → birth time = 0
            if annotate:
                generator = _build_generator_string(rows, vals, col_simplex_list)
            else:
                generator = None
            if birthDeathSimplex:
                if annotate:
                    entry = [dim_e, [0, birth_simplex], col_labels[e], generator]
                else:
                    entry = [dim_e, [0, birth_simplex], col_labels[e]]
            else:
                if annotate:
                    entry = [dim_e, [0, death_step], generator]
                else:
                    entry = [dim_e, [0, death_step]]
            barcode.append(entry)
        elif birth_step != death_step:
            # 일반 경우: birth와 death의 filtration time이 다른 유한 구간
            if annotate:
                generator = _build_generator_string(rows, vals, col_simplex_list)
            else:
                generator = None
            if birthDeathSimplex:
                if annotate:
                    entry = [dim_e, col_labels[pivot], col_labels[e], generator]
                else:
                    entry = [dim_e, col_labels[pivot], col_labels[e]]
            else:
                if annotate:
                    entry = [dim_e, [birth_step, death_step], generator]
                else:
                    entry = [dim_e, [birth_step, death_step]]
            barcode.append(entry)

    # 무한 구간(Infinite intervals): death 없이 끝까지 살아남은 homology class
    if not onlyFiniteInterval:
        for b in births:
            if b in finite_births:
                continue  # 이미 소멸된 birth는 제외
            step_b, simplex_b = col_labels[b]
            dim_b = len(simplex_b) - 1  # birth simplex의 homology 차원
            if dim_b not in listOfDimension:
                continue
            if annotate:
                generator = str(simplex_b)
                if birthDeathSimplex:
                    entry = [dim_b, [step_b, simplex_b], "infty", generator]
                else:
                    entry = [dim_b, [step_b, "infty"], generator]
            else:
                if birthDeathSimplex:
                    entry = [dim_b, [step_b, simplex_b], "infty"]
                else:
                    entry = [dim_b, [step_b, "infty"]]
            barcode.append(entry)

    # 차원 기준 정렬 (요청 시)
    if sortDimension:
        barcode.sort(key=lambda x: x[0])

    return barcode


def _build_generator_string(rows: list, vals: dict,
                            col_simplex_list: list) -> str:
    """
    pHcol의 축소된 열(reduced column)로부터 generator 문자열을 생성한다.

    축소된 열의 비제로 원소들이 가리키는 simplex들의 선형결합이
    곧 해당 homology class의 대표 cycle(representative cycle)이다.
    부호를 반전(-1 곱)하여 기존 코드와 동일한 형식으로 출력한다.
    예: "(0, 1) + (1, 3) - (0, 3)" → 꼭짓점 0-1-3을 잇는 삼각형 cycle
    """
    parts = []
    for i, r in enumerate(rows):
        # 부호 반전: pHcol 축소 과정의 관례에 맞추기 위함
        sign = int(vals[r]) * -1
        simplex_str = str(col_simplex_list[r])
        if i == 0:
            # 첫 항: 양수면 부호 생략, 음수면 " - " 접두
            if sign == -1:
                parts.append(f" - {simplex_str}")
            else:
                parts.append(simplex_str)
        else:
            # 이후 항: " + " 또는 " - "로 연결
            if sign == -1:
                parts.append(f" - {simplex_str}")
            elif sign == 1:
                parts.append(f" + {simplex_str}")
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# 방향 2: ripser 기반 버전
# ═══════════════════════════════════════════════════════════════════════════

def _check_ripser():
    """ripser 설치 여부를 확인합니다."""
    try:
        import ripser  # noqa: F401
        return True
    except ImportError:
        return False


def _find_death_edge(mat: np.ndarray, death_val: float,
                     birth_val: float) -> Optional[Tuple[int, int]]:
    """
    death filtration value에서 추가되는 edge를 찾습니다.
    birth 이후에 등장하는 edge 중 filtration value == death인 것.
    """
    n = len(mat)
    candidates = []
    # 거리 행렬에서 death_val과 일치하는 모든 edge를 수집
    for i in range(n):
        for j in range(i + 1, n):
            if abs(mat[i, j] - death_val) < 1e-8:
                candidates.append((i, j))
    return candidates


def _find_shortest_path_bfs(adj: Dict[int, list], src: int,
                            dst: int) -> Optional[List[int]]:
    """BFS로 src → dst 최단 경로를 찾습니다."""
    if src == dst:
        return [src]
    visited = {src}
    queue = [(src, [src])]
    # 너비 우선 탐색: 최단 경로를 보장
    while queue:
        node, path = queue.pop(0)
        for neighbor in adj.get(node, []):
            if neighbor == dst:
                return path + [dst]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None


def _extract_cycle_representative(mat: np.ndarray, birth: float,
                                  death: float) -> Optional[List[Tuple[int, int]]]:
    """
    H1 cycle representative를 추출합니다.

    원리:
    - death_val에서 추가되는 edge (u, v)가 cycle을 "죽이는" edge
    - birth_val < filtration <= death_val인 graph에서
      u→v 최단경로를 찾으면 그것이 cycle representative
    """
    n = len(mat)

    # 1단계: cycle을 소멸시키는 death edge 후보 찾기
    # death 시점에 등장하는 edge가 기존 cycle을 채워서 소멸시킴
    death_edges = _find_death_edge(mat, death, birth)
    if not death_edges:
        return None

    # 2단계: death 직전까지의 그래프 구축 (filtration < death인 edge만 사용)
    # 이 그래프에서 death edge의 양 끝점 사이에 경로가 있으면
    # 그 경로 + death edge가 cycle을 이룸
    adj: Dict[int, list] = defaultdict(list)
    for i in range(n):
        for j in range(i + 1, n):
            if mat[i, j] < death - 1e-12:  # death 미만인 edge만 포함
                adj[i].append(j)
                adj[j].append(i)

    # 3단계: 각 death edge (u, v)에 대해 BFS로 u→v 경로 탐색
    # 경로가 존재하면 경로 + death edge = cycle representative
    for u, v in death_edges:
        path = _find_shortest_path_bfs(adj, u, v)
        if path and len(path) >= 2:
            # path = [u, ..., v] 형태의 경로
            # cycle = 경로의 edge들 + 닫는 edge (v→u)
            edges = []
            for k in range(len(path) - 1):
                a, b = path[k], path[k + 1]
                edges.append((min(a, b), max(a, b)))  # 정규화: 작은 번호 먼저
            edges.append((min(u, v), max(u, v)))  # cycle을 닫는 death edge
            return edges

    return None


def _edges_to_generator_string(edges: List[Tuple[int, int]]) -> str:
    """
    edge 리스트를 기존 generator 문자열 형식으로 변환한다.
    예: [(0,1), (1,3), (0,3)] → "(0, 1) + (1, 3) + (0, 3)"
    """
    parts = []
    for i, (a, b) in enumerate(edges):
        s = f"({a}, {b})"
        if i == 0:
            parts.append(s)
        else:
            parts.append(f" + {s}")
    return "".join(parts)


def generate_barcode_ripser(mat: np.ndarray,
                            listOfDimension: list = [1],
                            annotate: bool = True,
                            birthDeathSimplex: bool = False,
                            sortDimension: bool = False,
                            onlyFiniteInterval: bool = False,
                            **kwargs  # exactStep 등 numpy 버전 전용 인자 무시
                            ) -> list:
    """
    ripser(C++) 기반 persistent homology 계산.
    기존 generateBarcode와 호환되는 출력 형식을 제공합니다.

    주의: generator 추출은 BFS 기반 근사이므로,
    기존 pHcol과 정확히 같은 generator가 아닐 수 있으나
    동치인 cycle을 표현합니다.
    """
    try:
        from ripser import ripser
    except ImportError:
        raise ImportError(
            "ripser 패키지가 필요합니다: pip install ripser"
        )

    max_dim = max(listOfDimension)

    # ripser 실행: C++ 기반으로 매우 빠르지만 cycle representative를 직접 제공하지 않음
    result = ripser(mat, maxdim=max_dim, distance_matrix=True)
    diagrams = result['dgms']  # diagrams[dim] = Nx2 배열 (birth, death)

    barcode = []

    for dim in listOfDimension:
        if dim >= len(diagrams):
            continue
        dgm = diagrams[dim]

        for birth, death in dgm:
            # 무한 구간: death = inf → 영원히 살아남는 homology class
            if np.isinf(death):
                if onlyFiniteInterval:
                    continue
                if annotate:
                    entry = [dim, [float(birth), "infty"], ""]
                else:
                    entry = [dim, [float(birth), "infty"]]
                barcode.append(entry)
                continue

            # 유한 구간: cycle이 탄생(birth)했다가 소멸(death)하는 경우
            b_val = float(birth)
            d_val = float(death)

            if annotate and dim == 1:
                # H1 cycle의 경우: BFS로 cycle representative 추출 시도
                # ripser는 cycle 정보를 주지 않으므로 death edge + BFS로 근사
                edges = _extract_cycle_representative(mat, b_val, d_val)
                if edges:
                    gen_str = _edges_to_generator_string(edges)
                else:
                    gen_str = ""  # cycle 추출 실패 시 빈 문자열

                if birthDeathSimplex:
                    entry = [dim, [b_val, None], [d_val, None], gen_str]
                else:
                    entry = [dim, [b_val, d_val], gen_str]
            else:
                if birthDeathSimplex:
                    entry = [dim, [b_val, None], [d_val, None]]
                else:
                    entry = [dim, [b_val, d_val]]
            barcode.append(entry)

    if sortDimension:
        barcode.sort(key=lambda x: x[0])

    return barcode
