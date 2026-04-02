"""
cycle_selector.py — Cycle Subset 선택: 위상 구조 보존도 최적화
================================================================

48개 cycle 전체 대신, 원곡의 위상 구조를 가장 잘 보존하는
K개 cycle subset을 선택합니다.

보존도 = 3가지 지표의 가중 평균:
  1. Note Pool Jaccard (0.5) — 음악 생성에 직접 연관
  2. Overlap Pattern 상관 (0.3) — 시간 구조 보존
  3. Betti Curve 유사도 (0.2) — 위상 구조 보존

탐색: Greedy Forward Selection
  - S=∅ → 매 단계에서 가장 preservation이 높은 cycle 추가
  - 종료: 고정 크기 K 또는 보존도 임계값 도달
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass, field


@dataclass
class SelectionResult:
    """Greedy selection 결과."""
    selected_indices: List[int]          # 선택된 cycle column 인덱스
    selected_cycles: List[tuple]         # 선택된 cycle vertex tuple
    preservation_curve: List[float]      # 각 단계의 composite score
    component_curves: Dict[str, List[float]]  # 지표별 curve
    final_score: float


# ═══════════════════════════════════════════════════════════════════════════
# 보존도 지표
# ═══════════════════════════════════════════════════════════════════════════

class PreservationMetrics:
    """
    전체 overlap matrix 대비 subset의 보존도를 계산합니다.

    초기화 시 전체 overlap matrix에서 시점별 note pool 등을
    사전 계산하여 select 루프 내에서 빠르게 평가합니다.
    """

    def __init__(self, overlap_matrix: np.ndarray,
                 cycle_notes: Dict[int, Set[int]],
                 weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)):
        """
        Args:
            overlap_matrix: (T, C) 이진 행렬
            cycle_notes: {col_idx: set of note labels} 매핑
            weights: (jaccard, correlation, betti) 가중치
        """
        self.overlap = overlap_matrix  # (T, C)
        self.T, self.C = overlap_matrix.shape
        self.cycle_notes = cycle_notes
        self.w_jaccard, self.w_corr, self.w_betti = weights

        # ── 사전 계산: 전체 matrix 기준값 ──
        # 각 시점(t)에서 활성화된 cycle 수의 합 → temporal profile (Betti curve와 동일)
        self._full_temporal = overlap_matrix.sum(axis=1).astype(float)  # (T,)
        self._full_betti = self._full_temporal.copy()
        # Betti curve의 L2 노름 (나중에 정규화 거리 계산에 사용)
        self._full_betti_norm = np.linalg.norm(self._full_betti)

        # ── 시점별 전체 note pool 사전 계산 ──
        # 각 시점 t에서 활성화된 모든 cycle의 note를 합집합으로 모은 것
        # greedy 루프에서 Jaccard를 빠르게 계산하기 위해 미리 구해둠
        self._full_pools: List[Set[int]] = []
        # note pool이 비어있지 않은 시점만 기록 (Jaccard 계산 시 순회 대상)
        self._active_times: List[int] = []
        for t in range(self.T):
            pool = set()
            for c in range(self.C):
                if overlap_matrix[t, c]:
                    pool |= cycle_notes.get(c, set())
            self._full_pools.append(pool)
            if pool:
                self._active_times.append(t)

    def note_pool_jaccard(self, subset: List[int]) -> float:
        """
        시점별 note pool Jaccard 유사도의 평균.

        각 활성 시점 t에서:
          full_pool = 전체 cycle이 커버하는 note 집합
          sub_pool  = subset cycle이 커버하는 note 집합
          J(t) = |full_pool ∩ sub_pool| / |full_pool ∪ sub_pool|
        최종 반환값 = 모든 활성 시점의 J(t) 평균
        """
        if not self._active_times:
            return 1.0

        subset_set = set(subset)
        total_j = 0.0
        count = 0

        for t in self._active_times:
            full_pool = self._full_pools[t]
            if not full_pool:
                continue

            # subset에 속하면서 시점 t에서 활성화된 cycle들의 note 합집합
            sub_pool = set()
            for c in subset_set:
                if self.overlap[t, c]:
                    sub_pool |= self.cycle_notes.get(c, set())

            if not full_pool and not sub_pool:
                continue

            # Jaccard 계산: 교집합 크기 / 합집합 크기
            intersection = len(full_pool & sub_pool)
            union = len(full_pool | sub_pool)
            if union > 0:
                total_j += intersection / union
                count += 1

        return total_j / count if count > 0 else 0.0

    def overlap_correlation(self, subset: List[int]) -> float:
        """
        전체 vs subset의 temporal profile에 대한 Pearson 상관계수.

        temporal profile = 각 시점에서 활성화된 cycle 수의 시계열 벡터.
        전체 cycle의 profile과 subset의 profile 간 상관이 높을수록
        시간에 따른 위상 구조의 밀도 변화 패턴이 유사함을 의미.
        음수 상관은 0으로 클리핑 (역상관은 보존으로 간주하지 않음).
        """
        # subset에 해당하는 열만 추출하여 시점별 합산
        sub_temporal = self.overlap[:, subset].sum(axis=1).astype(float)

        full_std = self._full_temporal.std()
        sub_std = sub_temporal.std()

        # 둘 다 상수(분산=0)이면 완벽 일치, 한쪽만 상수이면 상관 없음
        if full_std < 1e-12 or sub_std < 1e-12:
            return 1.0 if full_std < 1e-12 and sub_std < 1e-12 else 0.0

        corr = np.corrcoef(self._full_temporal, sub_temporal)[0, 1]
        return max(0.0, corr)  # 음수 상관은 0으로

    def betti_curve_score(self, subset: List[int]) -> float:
        """
        Betti curve L2 유사도: 1 - (정규화된 L2 거리).

        Betti curve = 시점별 활성 cycle 수 (= temporal profile과 동일).
        subset은 cycle 수가 적으므로 값이 전체보다 작음 →
        전체 합 / subset 합 비율로 스케일링하여 크기를 맞춘 뒤,
        L2 거리를 전체 curve의 노름으로 나누어 0~1 범위로 정규화.
        score = 1 - (||full - scaled_sub|| / ||full||)
        score가 1에 가까울수록 curve의 형태(shape)가 유사.
        """
        if self._full_betti_norm < 1e-12:
            return 1.0

        sub_betti = self.overlap[:, subset].sum(axis=1).astype(float)
        # 전체 대비 비율 보정: subset은 cycle 수가 적으므로 스케일 조정
        if sub_betti.sum() > 0:
            scale = self._full_betti.sum() / sub_betti.sum()
            sub_betti_scaled = sub_betti * scale
        else:
            return 0.0

        dist = np.linalg.norm(self._full_betti - sub_betti_scaled)
        return max(0.0, 1.0 - dist / self._full_betti_norm)

    def composite_score(self, subset: List[int]) -> Tuple[float, Dict[str, float]]:
        """
        3가지 지표의 가중 평균으로 최종 보존도 점수를 산출.

        score = w_jaccard * J + w_corr * C + w_betti * B
        기본 가중치: (0.5, 0.3, 0.2)
        → note pool 유사도(음악적 내용)에 가장 큰 비중,
          시간 패턴 상관에 중간 비중, Betti curve 형태에 보조 비중.
        """
        j = self.note_pool_jaccard(subset)
        c = self.overlap_correlation(subset)
        b = self.betti_curve_score(subset)

        score = self.w_jaccard * j + self.w_corr * c + self.w_betti * b
        components = {'jaccard': j, 'correlation': c, 'betti': b}
        return score, components


# ═══════════════════════════════════════════════════════════════════════════
# Greedy Forward Selection
# ═══════════════════════════════════════════════════════════════════════════

class CycleSubsetSelector:
    """
    Greedy forward selection으로 최적 cycle subset을 찾습니다.
    """

    def __init__(self, overlap_matrix: np.ndarray,
                 cycle_labeled: dict,
                 weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)):
        """
        Args:
            overlap_matrix: (T, C) 이진 행렬
            cycle_labeled: {label: (v0, v1, ...)} cycle vertex 매핑
        """
        self.overlap = overlap_matrix
        self.cycle_labeled = cycle_labeled
        self.C = overlap_matrix.shape[1]

        # cycle column index → note set 매핑 (cycle 내 vertex 추출)
        cycle_notes = {}
        items = list(cycle_labeled.items()) if isinstance(cycle_labeled, dict) else list(enumerate(cycle_labeled))
        for c_idx, (label, cycle) in enumerate(items):
            # dim=2인 경우: frozenset of tuples → 모든 vertex(note)의 합집합
            if isinstance(cycle, frozenset):
                verts = set()
                for simplex in cycle:
                    if isinstance(simplex, tuple):
                        verts.update(simplex)
                    else:
                        verts.add(simplex)
                cycle_notes[c_idx] = verts
            else:
                cycle_notes[c_idx] = set(cycle)

        self.cycle_notes = cycle_notes
        self.metrics = PreservationMetrics(overlap_matrix, cycle_notes, weights)
        self._items = items

    def select_fixed_size(self, k: int, verbose: bool = True) -> SelectionResult:
        """정확히 K개 cycle을 greedy로 선택합니다."""
        k = min(k, self.C)
        return self._greedy_select(
            stop_fn=lambda selected, score: len(selected) >= k,
            verbose=verbose
        )

    def select_by_threshold(self, target: float = 0.9,
                            max_k: Optional[int] = None,
                            verbose: bool = True) -> SelectionResult:
        """보존도가 target에 도달할 때까지 cycle을 추가합니다."""
        if max_k is None:
            max_k = self.C
        return self._greedy_select(
            stop_fn=lambda selected, score: score >= target or len(selected) >= max_k,
            verbose=verbose
        )

    def _greedy_select(self, stop_fn, verbose: bool) -> SelectionResult:
        """
        Greedy forward selection 공통 로직.

        빈 집합에서 시작하여 매 단계마다:
          1. 아직 선택되지 않은 모든 cycle을 후보로 시도
          2. 각 후보를 현재 선택 집합에 추가했을 때의 composite score 계산
          3. 가장 높은 score를 주는 cycle을 선택 집합에 확정
          4. stop_fn 조건(크기 K 도달 또는 목표 score 달성)이면 종료
        이 방식은 최적해를 보장하지는 않지만 O(C^2) 평가로 실용적.
        """
        selected: List[int] = []
        remaining = set(range(self.C))
        preservation_curve: List[float] = []
        component_curves: Dict[str, List[float]] = {
            'jaccard': [], 'correlation': [], 'betti': []
        }

        step = 0
        while remaining:
            best_c = -1
            best_score = -1.0
            best_comp = {}

            # 남은 후보 중 추가 시 score가 최대인 cycle 탐색
            for c in remaining:
                candidate = selected + [c]
                score, comp = self.metrics.composite_score(candidate)
                if score > best_score:
                    best_score = score
                    best_c = c
                    best_comp = comp

            # 최선의 cycle을 선택 집합에 추가
            selected.append(best_c)
            remaining.remove(best_c)
            preservation_curve.append(best_score)
            for key in component_curves:
                component_curves[key].append(best_comp[key])

            step += 1
            if verbose and (step <= 10 or step % 5 == 0 or step == self.C):
                cycle_verts = self._items[best_c][1]
                print(f"    step {step:2d}: +cycle {best_c:2d} {cycle_verts}"
                      f"  score={best_score:.4f}"
                      f"  (J={best_comp['jaccard']:.3f}"
                      f" C={best_comp['correlation']:.3f}"
                      f" B={best_comp['betti']:.3f})")

            # 종료 조건 확인 (크기 K 도달 또는 목표 score 달성)
            if stop_fn(selected, best_score):
                break

        selected_cycles = [self._items[i][1] for i in selected]

        return SelectionResult(
            selected_indices=selected,
            selected_cycles=selected_cycles,
            preservation_curve=preservation_curve,
            component_curves=component_curves,
            final_score=preservation_curve[-1] if preservation_curve else 0.0
        )

    def select_with_coverage(self, notes_dict: dict,
                              target: float = 0.9,
                              k: Optional[int] = None,
                              verbose: bool = True) -> SelectionResult:
        """
        Note coverage를 분석한 후 보존도를 최적화합니다.

        2단계 분석:
          1) "고아 note" 식별 — 어떤 cycle에도 속하지 않는 note
             → cycle 선택으로는 해결 불가, 생성 시 chord 기반 보충 필요
          2) greedy selection 수행 후 커버리지 보고

        Args:
            notes_dict: {chord_idx: set of note labels} 화음→note 매핑
            target: 보존도 임계값
            k: 고정 크기 (None이면 target 사용)

        Returns:
            SelectionResult에 .orphan_notes, .orphan_chords, .coverage 추가
        """
        # ── 전체 note 집합 (1-indexed) ──
        all_notes = set()
        for key, val in notes_dict.items():
            if isinstance(key, int):
                all_notes |= val

        # ── cycle에 포함된 note (0-indexed vertex → 1-indexed) ──
        notes_in_any_cycle = set()
        for c_idx, verts in self.cycle_notes.items():
            notes_in_any_cycle |= {v + 1 for v in verts}

        orphan_notes = all_notes - notes_in_any_cycle

        # ── 고아 note가 속한 chord 식별 ──
        orphan_chords = {}
        for n in orphan_notes:
            chords = [key for key, val in notes_dict.items()
                      if isinstance(key, int) and n in val]
            orphan_chords[n] = chords

        if verbose:
            if orphan_notes:
                print(f"    [Coverage] 고아 note {len(orphan_notes)}개"
                      f" (어떤 cycle에도 미포함): {sorted(orphan_notes)}")
                for n, chords in sorted(orphan_chords.items()):
                    print(f"      note {n} -> chord {chords}")
            else:
                print(f"    [Coverage] 모든 note가 cycle에 포함됨")

        # ── greedy selection ──
        if k is not None:
            result = self.select_fixed_size(k, verbose=verbose)
        else:
            result = self.select_by_threshold(target, verbose=verbose)

        # ── 선택 후 커버리지 보고 ──
        covered = set()
        for idx in result.selected_indices:
            covered |= {v + 1 for v in self.cycle_notes[idx]}

        total_missing = all_notes - covered

        if verbose:
            print(f"    [Coverage] {len(covered)}/{len(all_notes)} notes 커버"
                  f" (구조적 고아 {len(orphan_notes)}개 포함하면"
                  f" 최대 {len(notes_in_any_cycle)}/{len(all_notes)})")

        # ── orphan 정보를 result에 첨부 ──
        result.orphan_notes = orphan_notes
        result.orphan_chords = orphan_chords
        result.coverage = len(covered) / len(all_notes) if all_notes else 1.0

        return result

    def rank_cycles(self) -> List[Tuple[int, float]]:
        """
        각 cycle을 단독으로 평가하여 순위를 매깁니다.

        cycle 하나만 선택했을 때의 composite score를 기준으로
        내림차순 정렬. 개별 cycle의 중요도를 파악하거나,
        greedy selection의 첫 단계 결과를 미리 확인할 때 유용.
        """
        scores = []
        for c in range(self.C):
            score, _ = self.metrics.composite_score([c])
            scores.append((c, score))
        scores.sort(key=lambda x: -x[1])
        return scores
