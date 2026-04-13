"""
note_reassign.py — 방향 A: 거리 보존 note 재분배

중첩행렬(시간 구조)은 보존하고, 각 cycle에 새로운 note를 분배.
새 note 집합은 원곡의 note-note 및 cycle-cycle 거리 관계를
(up to permutation) 근사적으로 보존해야 한다.

알고리즘:
  1. 원곡의 note-note 거리행렬 D_orig (N×N) 계산
  2. 원곡의 cycle-cycle 거리행렬 C_orig (K×K) 계산 (voice_leading)
  3. 후보 pitch pool에서 새 note 집합 탐색 (최적화)
  4. cycle에 새 note 분배 (cycle 거리 보존, up to permutation)
  5. 새 notes_label 반환 → 기존 overlap matrix + 생성 알고리즘 사용

화성 제약 옵션 (harmony_mode):
  - None: 기존 방식 (chromatic, 거리만 보존)
  - 'scale': 후보 pitch를 특정 음계로 제한
  - 'consonance': cycle 내 불협화도 패널티 추가
  - 'interval': 원곡 cycle 내 interval structure 보존
  - 'wasserstein': Persistence Diagram 간 Wasserstein distance 제약
"""
import numpy as np
from typing import Dict, Tuple, List, Optional
from itertools import permutations


# ═══════════════════════════════════════════════════════════════════════════
# 0. Wasserstein distance between persistence diagrams
# ═══════════════════════════════════════════════════════════════════════════

def _extract_h1_pairs(barcode: list) -> np.ndarray:
    """barcode에서 H1 (birth, death) 쌍 추출. infinity는 제외."""
    pairs = []
    for entry in barcode:
        if entry[0] == 1:  # dimension 1
            bd = entry[1]
            b = bd[0] if isinstance(bd, (list, tuple)) else bd
            d = bd[1] if isinstance(bd, (list, tuple)) else None
            if d is not None and d != 'infty' and d != float('inf'):
                pairs.append([float(b), float(d)])
    return np.array(pairs) if pairs else np.empty((0, 2))


def wasserstein_distance_pd(dgm1: np.ndarray, dgm2: np.ndarray, p: int = 2) -> float:
    """
    두 persistence diagram 간 p-Wasserstein distance.

    각 점을 상대 diagram의 점 또는 대각선(diagonal)에 매칭.
    대각선 투영: (b,d) → ((b+d)/2, (b+d)/2), 비용 = (d-b)/2 * sqrt(2).

    Args:
        dgm1, dgm2: (n, 2) 형태의 (birth, death) 배열
        p: Wasserstein 차수 (기본 2)
    Returns:
        Wasserstein distance (float)
    """
    from scipy.optimize import linear_sum_assignment

    n1 = len(dgm1)
    n2 = len(dgm2)

    if n1 == 0 and n2 == 0:
        return 0.0

    # 비용 행렬: (n1 + n2) × (n1 + n2)
    # 왼쪽 n1: dgm1 점, 오른쪽 n2: dgm2 점
    # 상단 n1: dgm1을 dgm2 점 또는 대각선에 매칭
    # 하단 n2: dgm2를 dgm1 점 또는 대각선에 매칭
    N = n1 + n2
    cost = np.zeros((N, N))

    # dgm1[i] ↔ dgm2[j] 매칭 비용
    for i in range(n1):
        for j in range(n2):
            diff = dgm1[i] - dgm2[j]
            cost[i, j] = np.sum(np.abs(diff) ** p) ** (1.0 / p)

    # dgm1[i] → 대각선 (자기 자신 삭제) 비용
    for i in range(n1):
        diag_cost = (dgm1[i, 1] - dgm1[i, 0]) / np.sqrt(2)
        for j in range(n2, N):
            cost[i, j] = abs(diag_cost)

    # dgm2[j] → 대각선 (자기 자신 삭제) 비용
    for j in range(n2):
        diag_cost = (dgm2[j, 1] - dgm2[j, 0]) / np.sqrt(2)
        for i in range(n1, N):
            cost[i, j] = abs(diag_cost)

    # 대각선 ↔ 대각선: 비용 0
    # (이미 0으로 초기화됨)

    row_ind, col_ind = linear_sum_assignment(cost)
    return float(np.sum(cost[row_ind, col_ind]))


def compute_ph_wasserstein(D_matrix: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    거리행렬로부터 H1 persistence diagram을 계산하고
    (birth-death pairs, total_persistence)를 반환.

    topology.generate_barcode_numpy 대신 Ripser를 사용하여 빠르게 계산.
    """
    try:
        from ripser import ripser
        result = ripser(D_matrix, maxdim=1, distance_matrix=True)
        dgm = result['dgms'][1]  # H1 diagram
        # inf 제거
        mask = np.isfinite(dgm[:, 1])
        dgm = dgm[mask]
        total_pers = float(np.sum(dgm[:, 1] - dgm[:, 0])) if len(dgm) > 0 else 0.0
        return dgm, total_pers
    except ImportError:
        # Ripser 미설치 시 topology.py fallback
        from topology import generate_barcode_numpy
        barcode = generate_barcode_numpy(D_matrix, listOfDimension=[1])
        dgm = _extract_h1_pairs(barcode)
        total_pers = float(np.sum(dgm[:, 1] - dgm[:, 0])) if len(dgm) > 0 else 0.0
        return dgm, total_pers


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cycle-cycle 거리 계산
# ═══════════════════════════════════════════════════════════════════════════

def optimal_matching_set_distance(set_a: List[int], set_b: List[int],
                                   note_dist_fn=None) -> float:
    """
    두 pitch 집합 간의 최소 매칭 거리 (Hungarian algorithm).

    각 음을 1:1 대응시켜 총 거리가 최소인 매칭을 찾는다.
    집합 크기가 다르면, 작은 쪽을 큰 쪽의 부분집합에 매칭.
    """
    from scipy.optimize import linear_sum_assignment

    a = sorted(set_a)
    b = sorted(set_b)
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return 0.0

    if note_dist_fn is None:
        note_dist_fn = lambda x, y: abs(x - y)

    # cost matrix (|a| × |b|)
    cost = np.zeros((len(a), len(b)))
    for i in range(len(a)):
        for j in range(len(b)):
            cost[i, j] = note_dist_fn(a[i], b[j])

    row_ind, col_ind = linear_sum_assignment(cost)
    total = sum(cost[r, c] for r, c in zip(row_ind, col_ind))
    return total / len(a)


# voice_leading 호환용 별칭
def voice_leading_set_distance(set_a: List[int], set_b: List[int]) -> float:
    return optimal_matching_set_distance(set_a, set_b, lambda x, y: abs(x - y))


def tonnetz_set_distance(set_a: List[int], set_b: List[int]) -> float:
    """
    두 pitch 집합 간의 Tonnetz 최소 매칭 거리.

    각 음을 1:1 대응시키되, 쌍별 거리를 Tonnetz로 측정.
    translation-invariant가 아니므로 transposition이 최적해가 아님.
    """
    from musical_metrics import tonnetz_distance
    return optimal_matching_set_distance(
        set_a, set_b,
        lambda x, y: tonnetz_distance(x % 12, y % 12)
    )


def dft_set_distance(set_a: List[int], set_b: List[int]) -> float:
    """
    두 pitch class 집합 간의 DFT 거리.

    각 집합을 12차원 indicator → DFT → L2 거리.
    pitch class set 비교에 자연스럽게 확장됨.
    """
    def set_to_dft(pitches):
        indicator = np.zeros(12)
        for p in pitches:
            indicator[p % 12] = 1.0
        fft = np.fft.fft(indicator)
        return np.abs(fft[1:7])  # 1~6번 계수

    f_a = set_to_dft(set_a)
    f_b = set_to_dft(set_b)
    return float(np.linalg.norm(f_a - f_b))


def compute_cycle_distance_matrix(cycle_labeled: dict,
                                  notes_label: dict,
                                  metric: str = 'voice_leading'
                                  ) -> np.ndarray:
    """
    cycle-cycle 거리행렬 (K×K) 계산.

    Args:
        cycle_labeled: {label: (note_indices...)} — cycle 구성 note 인덱스 (1-indexed)
        notes_label: {(pitch, dur): label} — note 정보
        metric: 'voice_leading' | 'dft'

    Returns:
        (K, K) 대칭 거리 행렬
    """
    # label → pitch 역매핑
    label_to_pitch = {v: k[0] for k, v in notes_label.items()}

    cycles = list(cycle_labeled.values())
    K = len(cycles)

    # 각 cycle의 pitch 집합
    cycle_pitches = []
    for cycle_notes in cycles:
        pitches = [label_to_pitch[n] for n in cycle_notes if n in label_to_pitch]
        cycle_pitches.append(pitches)

    if metric == 'voice_leading':
        dist_fn = voice_leading_set_distance
    elif metric == 'tonnetz':
        dist_fn = tonnetz_set_distance
    elif metric == 'dft':
        dist_fn = dft_set_distance
    else:
        raise ValueError(f"Unknown cycle metric: {metric}")

    C = np.zeros((K, K))
    for i in range(K):
        for j in range(i + 1, K):
            d = dist_fn(cycle_pitches[i], cycle_pitches[j])
            C[i, j] = d
            C[j, i] = d

    return C


# ═══════════════════════════════════════════════════════════════════════════
# 2. 새 note 집합 탐색 (최적화)
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# 2a. 화성 제약 — Scale 정의 + Consonance + Interval preservation
# ═══════════════════════════════════════════════════════════════════════════

# 음계 정의: pitch class 집합 (C=0)
SCALES = {
    'major':       [0, 2, 4, 5, 7, 9, 11],       # Ionian
    'minor':       [0, 2, 3, 5, 7, 8, 10],       # Natural minor
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'pentatonic':  [0, 2, 4, 7, 9],              # Major pentatonic
    'minor_penta': [0, 3, 5, 7, 10],             # Minor pentatonic
    'dorian':      [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':  [0, 2, 4, 5, 7, 9, 10],
    'whole_tone':  [0, 2, 4, 6, 8, 10],
}

# Interval class의 consonance 점수 (0=완전협화, 높을수록 불협화)
# 전통 화성학 기반
INTERVAL_DISSONANCE = {
    0: 0.0,   # unison
    1: 1.0,   # minor 2nd (가장 불협화)
    2: 0.8,   # major 2nd
    3: 0.3,   # minor 3rd (협화)
    4: 0.3,   # major 3rd (협화)
    5: 0.1,   # perfect 4th (협화)
    6: 0.9,   # tritone (불협화)
    7: 0.0,   # perfect 5th (가장 협화)
    8: 0.3,   # minor 6th
    9: 0.3,   # major 6th
    10: 0.8,  # minor 7th
    11: 1.0,  # major 7th (불협화)
}


def _get_scale_pitches(pitch_range: Tuple[int, int],
                       scale_type: str = 'major',
                       root: int = 0) -> List[int]:
    """주어진 음계와 root에 해당하는 pitch 목록 (MIDI range 내)."""
    pcs = [(pc + root) % 12 for pc in SCALES[scale_type]]
    pitches = []
    for p in range(pitch_range[0], pitch_range[1] + 1):
        if p % 12 in pcs:
            pitches.append(p)
    return pitches


def _cycle_dissonance(pitches: List[int]) -> float:
    """
    cycle 내 모든 음 쌍의 평균 불협화도.
    0에 가까울수록 조화로움.
    """
    if len(pitches) < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(len(pitches)):
        for j in range(i + 1, len(pitches)):
            ic = abs(pitches[i] - pitches[j]) % 12
            total += INTERVAL_DISSONANCE.get(ic, 0.5)
            count += 1
    return total / count


def _total_dissonance(new_pitches: List[int],
                      cycle_compositions: List[List[int]]) -> float:
    """모든 cycle의 평균 불협화도."""
    if not cycle_compositions:
        return 0.0
    total = 0.0
    for idxs in cycle_compositions:
        cp = [new_pitches[i] for i in idxs]
        total += _cycle_dissonance(cp)
    return total / len(cycle_compositions)


def _cycle_interval_vector(pitches: List[int]) -> List[int]:
    """
    cycle 내 음들의 interval class vector (ic 0~6 빈도).
    화성학에서 '집합'의 지문 역할.
    """
    vec = [0] * 7  # ic 0~6
    for i in range(len(pitches)):
        for j in range(i + 1, len(pitches)):
            ic = abs(pitches[i] - pitches[j]) % 12
            if ic > 6:
                ic = 12 - ic
            vec[ic] += 1
    return vec


def _interval_structure_error(orig_pitches_per_cycle: List[List[int]],
                               new_pitches_per_cycle: List[List[int]]) -> float:
    """
    원곡과 새 곡의 각 cycle interval vector 간 차이.
    cycle 간 매칭은 동일 인덱스 기준 (이미 거리 보존으로 매칭됨).
    """
    if not orig_pitches_per_cycle:
        return 0.0

    total = 0.0
    for orig_cp, new_cp in zip(orig_pitches_per_cycle, new_pitches_per_cycle):
        v1 = np.array(_cycle_interval_vector(orig_cp), dtype=float)
        v2 = np.array(_cycle_interval_vector(new_cp), dtype=float)
        # 정규화 후 L1 거리
        s1, s2 = v1.sum(), v2.sum()
        if s1 > 0:
            v1 /= s1
        if s2 > 0:
            v2 /= s2
        total += float(np.sum(np.abs(v1 - v2)))
    return total / len(orig_pitches_per_cycle)


def _build_candidate_pool(pitch_range: Tuple[int, int] = (48, 84),
                          duration: int = 1) -> List[Tuple[int, int]]:
    """후보 note pool 생성 (chromatic scale, 주어진 옥타브 범위)."""
    return [(p, duration) for p in range(pitch_range[0], pitch_range[1] + 1)]


def _note_distance(n1: Tuple[int, int], n2: Tuple[int, int],
                   metric: str = 'voice_leading') -> float:
    """단일 note 쌍 거리."""
    from musical_metrics import tonnetz_note_distance, voice_leading_note_distance, dft_note_distance
    if metric == 'tonnetz':
        return tonnetz_note_distance(n1, n2)
    elif metric == 'voice_leading':
        return voice_leading_note_distance(n1, n2)
    elif metric == 'dft':
        return dft_note_distance(n1, n2)
    raise ValueError(f"Unknown metric: {metric}")


def _distance_matrix_for_notes(notes: List[Tuple[int, int]],
                                metric: str) -> np.ndarray:
    """note 리스트의 거리행렬 계산."""
    N = len(notes)
    D = np.zeros((N, N))
    for i in range(N):
        for j in range(i + 1, N):
            d = _note_distance(notes[i], notes[j], metric)
            D[i, j] = d
            D[j, i] = d
    return D


def _normalize_matrix(M: np.ndarray) -> np.ndarray:
    """거리행렬을 [0, 1]로 정규화."""
    mask = M > 0
    if not mask.any():
        return M.copy()
    vmin, vmax = M[mask].min(), M[mask].max()
    if vmax == vmin:
        return np.where(mask, 0.5, 0.0)
    R = np.zeros_like(M)
    R[mask] = (M[mask] - vmin) / (vmax - vmin)
    return R


def _matrix_distance_up_to_perm(A: np.ndarray, B: np.ndarray,
                                 max_perm_size: int = 8) -> Tuple[float, Optional[list]]:
    """
    두 거리행렬 간 최소 Frobenius 거리 (up to row/col permutation).

    행렬이 작으면(≤max_perm_size) 전수 탐색, 크면 sorted spectrum 비교.
    """
    N = len(A)
    A_n = _normalize_matrix(A)
    B_n = _normalize_matrix(B)

    if N <= max_perm_size:
        best_cost = float('inf')
        best_perm = None
        for perm in permutations(range(N)):
            B_perm = B_n[np.ix_(perm, perm)]
            cost = np.sum((A_n - B_perm) ** 2)
            if cost < best_cost:
                best_cost = cost
                best_perm = list(perm)
        return np.sqrt(best_cost), best_perm
    else:
        # 빠른 근사: 각 행의 정렬된 거리 프로파일을 비교
        # 행 프로파일을 정렬하면 permutation-invariant한 특성 벡터가 됨
        A_profiles = np.sort(A_n, axis=1)
        B_profiles = np.sort(B_n, axis=1)

        # 행 프로파일 간 매칭 (Hungarian)
        from scipy.optimize import linear_sum_assignment
        cost = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                cost[i, j] = np.sum((A_profiles[i] - B_profiles[j]) ** 2)
        row_ind, col_ind = linear_sum_assignment(cost)

        # 매칭된 프로파일 간 오차
        total_err = sum(cost[r, c] for r, c in zip(row_ind, col_ind))
        perm = [0] * N
        for r, c in zip(row_ind, col_ind):
            perm[c] = r
        return float(np.sqrt(total_err)), perm


def _precompute_tonnetz_table() -> np.ndarray:
    """12×12 Tonnetz 거리 테이블 (캐싱용)."""
    from musical_metrics import _build_tonnetz_distance_table
    return _build_tonnetz_distance_table()


def _fast_note_distance_matrix(pitches: List[int], metric: str,
                                tonnetz_table: Optional[np.ndarray] = None) -> np.ndarray:
    """note 리스트의 거리행렬을 빠르게 계산 (duration=1 가정)."""
    N = len(pitches)
    D = np.zeros((N, N))
    if metric == 'tonnetz':
        for i in range(N):
            for j in range(i + 1, N):
                pc_dist = int(tonnetz_table[pitches[i] % 12, pitches[j] % 12])
                oct_dist = abs(pitches[i] // 12 - pitches[j] // 12) * 0.5
                d = pc_dist + oct_dist
                D[i, j] = d
                D[j, i] = d
    elif metric == 'voice_leading':
        for i in range(N):
            for j in range(i + 1, N):
                d = abs(pitches[i] - pitches[j])
                D[i, j] = d
                D[j, i] = d
    elif metric == 'dft':
        from musical_metrics import pitch_class_dft
        dfts = [pitch_class_dft(p) for p in pitches]
        for i in range(N):
            for j in range(i + 1, N):
                d = float(np.linalg.norm(dfts[i] - dfts[j]))
                D[i, j] = d
                D[j, i] = d
    return D


def _fast_cycle_distance_matrix(cycle_pitches: List[List[int]], metric: str,
                                 tonnetz_table: Optional[np.ndarray] = None) -> np.ndarray:
    """cycle-cycle 거리행렬을 빠르게 계산 (최소 매칭)."""
    K = len(cycle_pitches)
    C = np.zeros((K, K))

    if metric == 'tonnetz':
        dist_fn = lambda x, y: int(tonnetz_table[x % 12, y % 12])
    elif metric == 'voice_leading':
        dist_fn = lambda x, y: abs(x - y)
    else:
        # dft는 set_distance 사용
        for i in range(K):
            for j in range(i + 1, K):
                d = dft_set_distance(cycle_pitches[i], cycle_pitches[j])
                C[i, j] = d
                C[j, i] = d
        return C

    for i in range(K):
        for j in range(i + 1, K):
            d = optimal_matching_set_distance(cycle_pitches[i], cycle_pitches[j], dist_fn)
            C[i, j] = d
            C[j, i] = d
    return C


def find_new_notes(notes_label: dict,
                   cycle_labeled: dict,
                   note_metric: str = 'voice_leading',
                   cycle_metric: str = 'voice_leading',
                   pitch_range: Tuple[int, int] = (48, 84),
                   n_candidates: int = 500,
                   alpha_note: float = 0.5,
                   alpha_cycle: float = 0.5,
                   seed: int = 42,
                   harmony_mode: Optional[str] = None,
                   scale_type: str = 'major',
                   scale_root: Optional[int] = None,
                   alpha_consonance: float = 0.0,
                   alpha_interval: float = 0.0,
                   alpha_wasserstein: float = 0.0,
                   n_wasserstein_topk: int = 20,
                   ) -> Dict:
    """
    원곡의 note-note / cycle-cycle 거리를 보존하는 새 note 집합을 찾는다.

    전략:
      1단계: 랜덤 후보 생성 → 거리행렬 비교 → 상위 후보 수집
      2단계 (alpha_wasserstein > 0): 상위 후보에 대해 PH → Wasserstein distance 계산

    Args:
        notes_label: 원곡의 {(pitch, dur): label}
        cycle_labeled: 원곡의 {label: (note_indices...)}
        note_metric: note-note 거리 메트릭
        cycle_metric: cycle-cycle 거리 메트릭
        pitch_range: 후보 pitch 범위 (MIDI number)
        n_candidates: 탐색할 랜덤 후보 수
        alpha_note: note 거리 보존 가중치
        alpha_cycle: cycle 거리 보존 가중치
        seed: 랜덤 시드
        harmony_mode: 화성 제약 모드
            None      — 기존 방식 (chromatic)
            'scale'   — 후보 pitch를 특정 음계로 제한
            'consonance' — cycle 내 불협화도 패널티 추가
            'interval'   — 원곡 cycle interval structure 보존
            'all'     — scale + consonance + interval 동시 적용
        scale_type: 음계 종류 ('major', 'minor', 'pentatonic', ...)
        scale_root: 음계 루트 (0=C, 2=D, ...). None이면 모든 root 중 최적 탐색
        alpha_consonance: consonance 패널티 가중치 (harmony_mode에 'consonance' 포함 시)
        alpha_interval: interval structure 보존 가중치 (harmony_mode에 'interval' 포함 시)

    Returns:
        dict with new_notes_label, errors, etc.
    """
    rng = np.random.RandomState(seed)

    # 화성 모드 파싱
    use_scale = harmony_mode in ('scale', 'all')
    use_consonance = harmony_mode in ('consonance', 'all')
    use_interval = harmony_mode in ('interval', 'all')

    # consonance/interval 가중치 기본값
    if use_consonance and alpha_consonance == 0.0:
        alpha_consonance = 0.3
    if use_interval and alpha_interval == 0.0:
        alpha_interval = 0.3

    # Tonnetz 테이블 미리 구축
    tonnetz_table = _precompute_tonnetz_table() if note_metric == 'tonnetz' or cycle_metric == 'tonnetz' else None

    # 원곡 정보 추출
    sorted_items = sorted(notes_label.items(), key=lambda x: x[1])
    orig_notes = [item[0] for item in sorted_items]
    orig_pitches = [n[0] for n in orig_notes]
    N = len(orig_notes)
    dur = orig_notes[0][1]

    # 원곡 거리행렬 (빠른 버전)
    D_orig = _fast_note_distance_matrix(orig_pitches, note_metric, tonnetz_table)
    D_orig_n = _normalize_matrix(D_orig)

    # cycle별 note 구성
    label_to_idx = {item[1]: i for i, item in enumerate(sorted_items)}
    cycle_compositions = []
    for cycle_notes in cycle_labeled.values():
        idxs = [label_to_idx[n] for n in cycle_notes if n in label_to_idx]
        cycle_compositions.append(idxs)
    K = len(cycle_compositions)

    # 원곡 cycle pitches → cycle 거리행렬
    orig_cycle_pitches = [[orig_pitches[i] for i in idxs] for idxs in cycle_compositions]
    C_orig = _fast_cycle_distance_matrix(orig_cycle_pitches, cycle_metric, tonnetz_table)

    # interval structure 보존용: 원곡 cycle interval vector
    orig_interval_vecs = None
    if use_interval:
        orig_interval_vecs = orig_cycle_pitches  # 비교용으로 보존

    # ── 후보 pitch pool 구성 ──
    if use_scale:
        # 모든 root를 시도하거나 특정 root 사용
        roots_to_try = [scale_root] if scale_root is not None else list(range(12))
        best_root = None
        best_root_pool = None
        best_root_size = 0

        for r in roots_to_try:
            pool = _get_scale_pitches(pitch_range, scale_type, r)
            if len(pool) >= N and len(pool) > best_root_size:
                best_root_size = len(pool)
                best_root = r
                best_root_pool = pool

        if best_root_pool is None or len(best_root_pool) < N:
            raise RuntimeError(
                f"Scale {scale_type} (root={scale_root}) in range {pitch_range} "
                f"has only {best_root_size} pitches, need {N}"
            )
        all_pitches = best_root_pool
        chosen_root = best_root
    else:
        all_pitches = list(range(pitch_range[0], pitch_range[1] + 1))
        chosen_root = None

    if N > len(all_pitches):
        raise RuntimeError(f"pitch range too narrow: need {N} but only {len(all_pitches)} available")

    use_wasserstein = alpha_wasserstein > 0

    # Wasserstein: 원곡 PH를 미리 계산
    dgm_orig = None
    if use_wasserstein:
        dgm_orig, _ = compute_ph_wasserstein(D_orig)
        print(f"  원곡 PH: {len(dgm_orig)} H1 cycles")

    # ── 1단계: note+cycle 기준 후보 수집 ──
    import heapq
    if use_wasserstein:
        topk_heap = []  # min-heap of (-cost, idx, result)
        topk_size = n_wasserstein_topk
    best_cost = float('inf')
    best_result = None

    for trial in range(n_candidates):
        chosen = rng.choice(all_pitches, size=N, replace=False)
        chosen.sort()
        new_pitches = [int(p) for p in chosen]

        # 새 note-note 거리행렬
        D_new = _fast_note_distance_matrix(new_pitches, note_metric, tonnetz_table)
        D_new_n = _normalize_matrix(D_new)
        note_error = float(np.sqrt(np.sum((D_orig_n - D_new_n) ** 2)))

        # early rejection
        cutoff = best_cost if not use_wasserstein else (
            -topk_heap[0][0] if len(topk_heap) >= topk_size else float('inf')
        )
        if alpha_note * note_error >= cutoff:
            continue

        # 새 cycle 거리행렬
        new_cycle_pitches = [[new_pitches[i] for i in idxs] for idxs in cycle_compositions]
        C_new = _fast_cycle_distance_matrix(new_cycle_pitches, cycle_metric, tonnetz_table)

        # cycle 거리 보존 (up to permutation)
        cycle_error, cycle_perm = _matrix_distance_up_to_perm(C_orig, C_new)

        total = alpha_note * note_error + alpha_cycle * cycle_error

        # ── 화성 제약 추가 비용 ──
        consonance_score = 0.0
        interval_error = 0.0

        if use_consonance:
            consonance_score = _total_dissonance(new_pitches, cycle_compositions)
            total += alpha_consonance * consonance_score

        if use_interval:
            interval_error = _interval_structure_error(
                orig_cycle_pitches, new_cycle_pitches
            )
            total += alpha_interval * interval_error

        candidate = {
            'new_notes': [(p, dur) for p in new_pitches],
            'note_error': note_error,
            'cycle_error': cycle_error,
            'consonance_score': consonance_score,
            'interval_error': interval_error,
            'total_cost': total,
            'cycle_perm': cycle_perm,
            'D_new': D_new,
            'C_new': C_new,
        }

        if use_wasserstein:
            # top-k heap 유지 (max-heap via negation)
            if len(topk_heap) < topk_size:
                heapq.heappush(topk_heap, (-total, trial, candidate))
            elif total < -topk_heap[0][0]:
                heapq.heapreplace(topk_heap, (-total, trial, candidate))
        else:
            if total < best_cost:
                best_cost = total
                best_result = candidate

    # ── 2단계: Wasserstein distance로 상위 후보 재평가 ──
    if use_wasserstein:
        print(f"  2단계: top-{len(topk_heap)} 후보에 Wasserstein distance 적용")
        best_cost = float('inf')
        best_result = None
        for neg_cost, trial_idx, cand in topk_heap:
            D_new = cand['D_new']
            dgm_new, _ = compute_ph_wasserstein(D_new)
            w_dist = wasserstein_distance_pd(dgm_orig, dgm_new)
            total_with_w = cand['total_cost'] + alpha_wasserstein * w_dist
            cand['wasserstein_dist'] = w_dist
            cand['total_cost_with_wasserstein'] = total_with_w
            if total_with_w < best_cost:
                best_cost = total_with_w
                best_result = cand
                best_result['total_cost'] = total_with_w
        print(f"  최종 선택: Wasserstein dist = {best_result.get('wasserstein_dist', 0):.4f}")

    if best_result is None:
        raise RuntimeError("No valid candidate found")

    # 결과 포맷팅
    new_notes = best_result['new_notes']
    new_notes_label = {note: (i + 1) for i, note in enumerate(new_notes)}

    # note 매핑: orig label → new label (같은 인덱스 위치)
    note_mapping = {}
    for i, (orig_note, orig_label) in enumerate(sorted_items):
        note_mapping[orig_label] = i + 1  # 동일 인덱스

    result = {
        'new_notes_label': new_notes_label,
        'note_mapping': note_mapping,
        'orig_notes': orig_notes,
        'new_notes': new_notes,
        'note_dist_error': best_result['note_error'],
        'cycle_dist_error': best_result['cycle_error'],
        'total_cost': best_result['total_cost'],
        'cycle_permutation': best_result['cycle_perm'],
        'D_orig': D_orig,
        'D_new': best_result['D_new'],
        'C_orig': C_orig,
        'C_new': best_result['C_new'],
        'harmony_mode': harmony_mode,
        'consonance_score': best_result['consonance_score'],
        'interval_error': best_result['interval_error'],
        'wasserstein_dist': best_result.get('wasserstein_dist', 0.0),
    }
    if use_scale:
        result['scale_type'] = scale_type
        result['scale_root'] = chosen_root
        result['scale_root_name'] = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][chosen_root]
        result['pool_size'] = len(all_pitches)

    return result
