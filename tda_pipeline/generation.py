"""
TDA Music Pipeline - Music Generation (최적화)
================================================
Algorithm 1 (확률적 샘플링)과 Algorithm 2 (신경망) 구현.

주요 최적화:
1. Algorithm 1:
   - node_pool을 numpy 배열로 관리하여 random.choice 가속
   - onset_checker를 set 기반으로 변경하여 O(1) 멤버십 검사
   - inst_len 동적 갱신 버그 수정 (range를 while로 교체)
   - max_resample_attempts 도입으로 무한 루프 방지
   - node_intersect/union을 캐싱하여 반복 계산 제거

2. Algorithm 2:
   - 두 악기의 indexed_music을 시간축 기준으로 정렬
   - 배치 학습 도입 (메모리 효율)
   - 모델 구조 간소화
"""

import numpy as np
import pandas as pd
import random
import math
import os
import datetime
from collections import Counter
from typing import Dict, List, Tuple, Optional, Set

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ═══════════════════════════════════════════════════════════════════════════
# Algorithm 1: 확률적 샘플링 기반 음악 생성
# ═══════════════════════════════════════════════════════════════════════════

class NodePool:
    """
    노드 풀 관리 클래스.
    기존 코드의 node_pool, node_freq, node_i를 캡슐화합니다.
    """
    
    def __init__(self, notes_label: dict, notes_counts: Counter, num_modules: int = 65):
        self.notes_label = notes_label
        self.label_to_note = {v: k for k, v in notes_label.items()}  # 역매핑
        
        # 전체 곡에서의 빈도 계산
        whole_counts = {k: v * num_modules for k, v in notes_counts.items()}
        
        # 빈도 기반 노드 풀 생성 (numpy 배열)
        pool_list = []
        for note, count in whole_counts.items():
            if note in notes_label:
                label = notes_label[note]
                pool_list.extend([label] * count)
        
        # 셔플
        random.shuffle(pool_list)
        self.pool = np.array(pool_list, dtype=int)
        self.total_size = len(self.pool)
    
    def sample(self) -> int:
        """풀에서 무작위 note label을 샘플링합니다."""
        return int(np.random.choice(self.pool))
    
    def label_to_note_info(self, label: int) -> Tuple[int, int]:
        """label → (pitch, duration) 변환"""
        # notes_label은 1-indexed이므로 label+1이 아닌 label 자체 사용
        # 기존 코드의 get_note_by_label과 동일
        for note, lbl in self.notes_label.items():
            if lbl == label + 1:  # 0-indexed label → 1-indexed notes_label
                return note
        return None


class CycleSetManager:
    """
    사이클 집합 연산을 캐싱하여 중복 계산을 제거합니다.
    """
    
    def __init__(self, cycle_labeled: dict):
        self.all_cycle_sets = [set(cycle) for cycle in cycle_labeled.values()]
        self._cache_intersect = {}
        self._cache_union = {}
    
    def get_intersect_nodes(self, active_mask: np.ndarray) -> Optional[tuple]:
        """
        활성화된 사이클들의 교집합에서 빈도 기반 샘플링 풀을 반환합니다.
        
        최적화: 캐시 키로 active_mask의 tuple 사용
        """
        key = tuple(active_mask.nonzero()[0])
        if not key:
            return None
        
        if key not in self._cache_intersect:
            # 활성 사이클의 모든 원소를 빈도 기반으로 수집
            freq = Counter()
            for idx in key:
                for elem in self.all_cycle_sets[idx]:
                    freq[elem] += 1
            
            # 빈도만큼 반복하여 튜플로
            result = []
            for elem, count in freq.items():
                result.extend([elem] * count)
            
            self._cache_intersect[key] = tuple(result) if result else None
        
        return self._cache_intersect[key]
    
    def get_union_nodes(self, active_mask: np.ndarray) -> Optional[set]:
        """활성화된 사이클들의 합집합을 반환합니다."""
        key = tuple(active_mask.nonzero()[0])
        if not key:
            return None
        
        if key not in self._cache_union:
            union = set()
            for idx in key:
                union |= self.all_cycle_sets[idx]
            self._cache_union[key] = union
        
        return self._cache_union[key]


def build_orphan_supplement(orphan_notes: Set[int],
                            orphan_chords: Dict[int, List[int]],
                            notes_dict: dict,
                            adn_whole_1: list,
                            adn_whole_2: list,
                            notes_label: dict,
                            total_length: int = 1088) -> Dict[int, List[int]]:
    """
    고아 note를 chord 활성화 시점에 보충하는 매핑을 생성합니다.

    cycle에 속하지 않는 note(고아)가 원곡에서 실제로 연주되는 시점을
    찾아서, 해당 시점의 sampling pool에 추가할 note label 목록을 반환.

    Args:
        orphan_notes: {5, 8, 22} 등 고아 note (1-indexed)
        orphan_chords: {note: [chord_indices]} 매핑
        notes_dict: {chord_idx: set of note labels}
        adn_whole_1, adn_whole_2: 악기별 전체 chord 시퀀스 (None 포함)
        notes_label: (pitch, dur) -> label dict
        total_length: 시간축 길이

    Returns:
        {t: [label1, label2, ...]} — 시점 t에서 보충할 note label 목록
    """
    # 고아 note가 속한 chord 인덱스 집합
    orphan_chord_set = set()
    for n, chords in orphan_chords.items():
        orphan_chord_set.update(chords)

    # label -> note_label (1-indexed) 역매핑
    # orphan note의 label 값 (0-indexed for node_pool)
    orphan_labels = {n - 1 for n in orphan_notes}  # 0-indexed

    supplement: Dict[int, List[int]] = {}

    for t in range(min(total_length, len(adn_whole_1), len(adn_whole_2))):
        c1 = adn_whole_1[t]
        c2 = adn_whole_2[t]
        labels_to_add = []

        for chord_idx in [c1, c2]:
            if chord_idx is None:
                continue
            if chord_idx in orphan_chord_set:
                # 이 chord에 속한 고아 note를 추가
                chord_notes = notes_dict.get(chord_idx, set())
                for n in chord_notes:
                    if n in orphan_notes:
                        labels_to_add.append(n - 1)  # 0-indexed label

        if labels_to_add:
            supplement[t] = labels_to_add

    return supplement


def algorithm1_optimized(node_pool: NodePool,
                         inst_len: List[int],
                         overlap_matrix: np.ndarray,
                         cycle_manager: CycleSetManager,
                         max_resample: int = 50,
                         verbose: bool = False,
                         orphan_supplement: Optional[Dict[int, List[int]]] = None
                         ) -> List[Tuple[int, int, int]]:
    """
    Algorithm 1의 최적화 버전.
    
    핵심 수정사항:
    1. inst_len 동적 갱신 시 range 대신 while 사용
    2. onset_checker를 set으로 변경 (O(1) 검색)
    3. 경계 조건 (n1[2] >= length) 일관적 처리
    4. max_resample로 무한 루프 방지
    
    Args:
        node_pool: NodePool 객체
        inst_len: 각 시점별 추출할 음의 개수 리스트 (복사본 사용 권장)
        overlap_matrix: (T, C) numpy 배열
        cycle_manager: CycleSetManager 객체
        max_resample: 재샘플링 최대 시도 횟수
        verbose: 디버그 출력 여부
    
    Returns:
        생성된 음표 리스트 [(start, pitch, end), ...]
    """
    length = len(inst_len)
    inst_len = list(inst_len)  # 방어적 복사
    
    generated = []
    onset_checker: Dict[int, Set[Tuple[int, int]]] = {i: set() for i in range(length)}
    resample_count = 0
    
    for j in range(length):
        # 이 시점에서 추출할 음의 수 (동적으로 줄어들 수 있음)
        num_to_sample = max(0, inst_len[j])

        # 고아 note 보충: 이 시점에 chord 기반으로 추가할 note가 있으면
        # 일정 확률로 고아 note를 먼저 배치
        if orphan_supplement and j in orphan_supplement and num_to_sample > 0:
            for orphan_label in orphan_supplement[j]:
                if num_to_sample <= 0:
                    break
                # 30% 확률로 고아 note 삽입 (너무 많으면 부자연스러움)
                if random.random() < 0.3:
                    note_tuple = node_pool.label_to_note_info(orphan_label)
                    if note_tuple:
                        pitch, duration = note_tuple
                        end = min(j + duration, length)
                        n1 = (j, pitch, end)
                        n2 = (pitch, end - j)
                        if n2 not in onset_checker[j]:
                            generated.append(n1)
                            onset_checker[j].add(n2)
                            for t in range(j + 1, min(end, length)):
                                inst_len[t] = max(0, inst_len[t] - 1)
                                onset_checker[t].add(n2)
                            num_to_sample -= 1

        for _ in range(num_to_sample):
            flag = overlap_matrix[j, :].sum()

            note_info = _sample_note_at_time(
                j, length, flag, overlap_matrix,
                node_pool, cycle_manager, onset_checker,
                max_resample, verbose
            )
            
            if note_info is None:
                resample_count += 1
                continue
            
            n1, n2 = note_info
            generated.append(n1)
            onset_checker[j].add(n2)
            
            # 활성화 구간에서 inst_len 감소
            for t in range(j + 1, min(n1[2], length)):
                inst_len[t] = max(0, inst_len[t] - 1)
                onset_checker[t].add(n2)
    
    if verbose:
        print(f"총 {resample_count}번 재샘플링 실패")
    
    return generated


def _sample_note_at_time(j: int, length: int, flag: float,
                         overlap_matrix: np.ndarray,
                         node_pool: NodePool,
                         cycle_manager: CycleSetManager,
                         onset_checker: dict,
                         max_resample: int,
                         verbose: bool) -> Optional[Tuple[tuple, tuple]]:
    """
    단일 시점 j에서 하나의 note를 샘플링합니다.
    
    Returns:
        (n1, n2) where n1 = (onset, pitch, end), n2 = (pitch, duration)
        또는 실패 시 None
    """
    for attempt in range(max_resample):
        if flag == 0:
            # 사이클 활성화 없음 → 인접 시점의 union을 피해서 샘플링
            z = _sample_avoiding_neighbors(
                j, length, overlap_matrix, node_pool, cycle_manager
            )
        else:
            # 사이클 활성화 있음 → 교집합에서 샘플링
            intersect_pool = cycle_manager.get_intersect_nodes(overlap_matrix[j, :])
            if intersect_pool is None:
                z = node_pool.sample()
            else:
                z = random.choice(intersect_pool)
        
        note_tuple = node_pool.label_to_note_info(z)
        if note_tuple is None:
            continue
        
        pitch, duration = note_tuple
        n1 = (j, pitch, j + duration)
        n2 = (pitch, duration)
        
        # 유효성 검사
        if n1[2] > length:
            # 곡의 끝을 넘어감 → duration 조정 시도
            if j + 1 <= length:
                n1 = (j, pitch, length)
                n2 = (pitch, length - j)
            else:
                continue
        
        if n2 in onset_checker[j]:
            if verbose and attempt > 5:
                print(f"  시점 {j}: {n2} 이미 존재, 재샘플링 ({attempt+1}/{max_resample})")
            continue
        
        return n1, n2
    
    return None


def _sample_avoiding_neighbors(j: int, length: int,
                               overlap_matrix: np.ndarray,
                               node_pool: NodePool,
                               cycle_manager: CycleSetManager) -> int:
    """인접 시점의 활성 사이클 노드를 피해서 샘플링합니다."""
    avoid = set()
    
    if j > 0 and overlap_matrix[j - 1, :].sum() > 0:
        union_prev = cycle_manager.get_union_nodes(overlap_matrix[j - 1, :])
        if union_prev:
            avoid |= union_prev
    
    if j < length - 1 and overlap_matrix[j + 1, :].sum() > 0:
        union_next = cycle_manager.get_union_nodes(overlap_matrix[j + 1, :])
        if union_next:
            avoid |= union_next
    
    if not avoid:
        return node_pool.sample()
    
    # avoid에 없는 노드가 나올 때까지 샘플링 (최대 20회)
    for _ in range(20):
        z = node_pool.sample()
        if z not in avoid:
            return z
    
    return node_pool.sample()  # 포기하고 아무거나 반환


# ═══════════════════════════════════════════════════════════════════════════
# Algorithm 2: 신경망 기반 음악 생성 (수정판)
# ═══════════════════════════════════════════════════════════════════════════
#
# [수정] L_encoded(7670) vs L_onehot(1088) 불일치 해결
#   원인: 기존 코드가 sliding window로 y를 (T-1, T*N) 형태로 펼쳐서
#         시점과 note 차원이 혼합됨
#   수정: 시점 t의 overlap → 시점 t의 multi-hot note를 직접 매핑
#         X: (T, C), y: (T, N) — 동일한 시간축
#
# [추가] Baseline DL 모델
#   - MusicGeneratorFC: 기존 FC 구조 (수정판)
#   - MusicGeneratorLSTM: 시계열 패턴 학습
#   - MusicGeneratorTransformer: self-attention 기반

if HAS_TORCH:

    # ── 학습 데이터 준비 ──────────────────────────────────────────────────

    def build_onehot_matrix(music_notes: List[List[Tuple[int, int, int]]],
                            notes_label: dict,
                            sequence_length: int,
                            num_notes: int = 23) -> np.ndarray:
        """
        두 악기의 note를 시간축 기준으로 multi-hot 행렬로 변환합니다.
        각 시점 t에서 활성화된 note를 1로 표시.

        [수정] 기존 indexed_music의 두 악기 concat 문제 해결:
        두 악기를 별도 리스트로 받아 같은 시간축에 겹쳐 기록.

        Args:
            music_notes: [inst1_notes, inst2_notes], 각 note는 (start, pitch, end)
            notes_label: (pitch, duration) → label (1-indexed)
            sequence_length: 시간축 길이 T (= 1088)
            num_notes: 고유 note 수 (= 23)

        Returns:
            (T, N) multi-hot 행렬. onehot[t, n] = 1이면 시점 t에 note n이 활성.
        """
        onehot = np.zeros((sequence_length, num_notes), dtype=np.float32)

        for inst_notes in music_notes:
            for start, pitch, end in inst_notes:
                duration = end - start
                key = (pitch, duration)
                if key in notes_label:
                    label = notes_label[key] - 1  # 1-indexed → 0-indexed
                    if 0 <= start < sequence_length and 0 <= label < num_notes:
                        onehot[start, label] = 1.0

        return onehot

    def prepare_training_data(overlap_matrix: np.ndarray,
                              music_notes: List[List[Tuple[int, int, int]]],
                              notes_label: dict,
                              sequence_length: int,
                              num_notes: int = 23) -> Tuple[np.ndarray, np.ndarray]:
        """
        학습 데이터를 준비합니다.

        [수정] X와 y가 동일한 시간축을 공유:
          X[t] = overlap_matrix[t]  (C차원, 어떤 cycle이 활성인지)
          y[t] = onehot[t]         (N차원, 어떤 note가 활성인지)

        모델이 학습할 매핑: "시점 t의 위상 구조 → 시점 t의 음악"

        Returns:
            X: (T, C) float32, y: (T, N) float32
        """
        onehot = build_onehot_matrix(
            music_notes, notes_label, sequence_length, num_notes
        )

        X = overlap_matrix.astype(np.float32)  # (T, C)
        y = onehot                               # (T, N)

        return X, y

    # ── Data Augmentation ─────────────────────────────────────────────────

    def augment_training_data(X: np.ndarray, y: np.ndarray,
                              overlap_full: np.ndarray,
                              cycle_labeled: dict,
                              k_values: List[int] = [10, 15, 20, 30],
                              n_shifts: int = 3,
                              noise_prob: float = 0.03,
                              n_noise_copies: int = 2) -> Tuple[np.ndarray, np.ndarray]:
        """
        3가지 전략으로 학습 데이터를 증강합니다.

        1) Subset Augmentation:
           cycle_selector로 다양한 K값의 overlap을 생성.
           동일한 y(원곡)에 대해 다른 X(위상 구조)를 학습 →
           "불완전한 위상 정보에서도 원곡을 복원"하는 강건한 모델.

        2) Circular Shift:
           시작점을 랜덤 이동하여 시퀀스를 회전.
           [A B C D] → [C D A B]. 같은 패턴이지만 모델이
           다른 시퀀스로 인식 → 위치 편향 방지.

        3) Noise Injection:
           overlap에 소량의 bit flip을 추가.
           입력에 노이즈가 있어도 올바른 note를 예측하도록 학습 →
           overfitting 방지 + 정규화 효과.

        Args:
            X: (T, C) 원본 overlap (전체 cycle)
            y: (T, N) 원본 note multi-hot
            overlap_full: (T, C_full) cycle selection 이전의 전체 overlap
            cycle_labeled: 전체 cycle labeled dict
            k_values: subset augmentation에 사용할 K 리스트
            n_shifts: circular shift 횟수
            noise_prob: noise injection에서 bit flip 확률
            n_noise_copies: noise 복사본 수

        Returns:
            (X_aug, y_aug): 증강된 학습 데이터
        """
        from cycle_selector import CycleSubsetSelector

        T, C = X.shape
        N = y.shape[1]

        all_X = [X]     # 원본 포함
        all_y = [y]

        # ── 1) Subset Augmentation ──
        # 다양한 K값의 overlap matrix를 생성하여 같은 y에 매핑
        selector = CycleSubsetSelector(overlap_full, cycle_labeled)
        for k in k_values:
            if k >= overlap_full.shape[1]:
                continue
            result = selector.select_fixed_size(k, verbose=False)
            X_sub = overlap_full[:, result.selected_indices].astype(np.float32)
            # C가 다르므로 전체 C 크기로 zero-padding
            X_padded = np.zeros((T, C), dtype=np.float32)
            X_padded[:, :X_sub.shape[1]] = X_sub
            all_X.append(X_padded)
            all_y.append(y.copy())

        # ── 2) Circular Shift ──
        # 시작점을 랜덤으로 이동하여 시퀀스 회전
        for _ in range(n_shifts):
            shift = np.random.randint(1, T)
            X_shifted = np.roll(X, shift, axis=0)
            y_shifted = np.roll(y, shift, axis=0)
            all_X.append(X_shifted)
            all_y.append(y_shifted)

        # ── 3) Noise Injection ──
        # overlap에 소량의 bit flip 추가
        for _ in range(n_noise_copies):
            noise_mask = np.random.random(X.shape) < noise_prob
            X_noisy = X.copy()
            X_noisy[noise_mask] = 1.0 - X_noisy[noise_mask]  # 0→1 또는 1→0
            all_X.append(X_noisy.astype(np.float32))
            all_y.append(y.copy())

        X_aug = np.concatenate(all_X, axis=0)
        y_aug = np.concatenate(all_y, axis=0)

        return X_aug, y_aug

    # ── 모델 1: FC (기존 구조 수정판) ─────────────────────────────────────

    class MusicGeneratorFC(nn.Module):
        """
        Fully Connected 모델 (기존 MusicGenerator 수정판).
        시점별 독립 예측: overlap[t] → notes[t]

        입력: (batch, C)  — C = cycle 수
        출력: (batch, N)  — N = note 수 (multi-label sigmoid)
        """

        def __init__(self, num_cycles: int, num_notes: int,
                     hidden_dim: int = 128, dropout: float = 0.3):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(num_cycles, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, hidden_dim * 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim * 2, num_notes),
            )

        def forward(self, x):
            return self.net(x)  # (batch, N) — raw logits

    # ── 모델 2: LSTM ─────────────────────────────────────────────────────

    class MusicGeneratorLSTM(nn.Module):
        """
        LSTM 기반 시퀀스 모델.
        overlap 시퀀스의 시간적 패턴을 학습하여 note 시퀀스를 예측.

        입력: (batch, T, C)  — T 시점의 overlap 시퀀스
        출력: (batch, T, N)  — T 시점의 note 예측
        """

        def __init__(self, num_cycles: int, num_notes: int,
                     hidden_dim: int = 128, num_layers: int = 2,
                     dropout: float = 0.3):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=num_cycles,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.fc = nn.Linear(hidden_dim, num_notes)

        def forward(self, x):
            # x: (batch, T, C)
            out, _ = self.lstm(x)     # (batch, T, hidden)
            return self.fc(out)       # (batch, T, N)

    # ── 모델 3: Transformer ──────────────────────────────────────────────

    class MusicGeneratorTransformer(nn.Module):
        """
        Transformer 기반 시퀀스 모델.
        Self-attention으로 전체 시점 간 관계를 학습.

        입력: (batch, T, C)
        출력: (batch, T, N)
        """

        def __init__(self, num_cycles: int, num_notes: int,
                     d_model: int = 128, nhead: int = 4,
                     num_layers: int = 2, dropout: float = 0.1,
                     max_len: int = 1088):
            super().__init__()
            self.input_proj = nn.Linear(num_cycles, d_model)

            # 학습 가능한 positional encoding
            self.pos_emb = nn.Parameter(torch.randn(1, max_len, d_model) * 0.02)

            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead,
                dim_feedforward=d_model * 4,
                dropout=dropout, batch_first=True
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer, num_layers=num_layers
            )
            self.fc_out = nn.Linear(d_model, num_notes)

        def forward(self, x):
            # x: (batch, T, C)
            T = x.size(1)
            x = self.input_proj(x) + self.pos_emb[:, :T, :]  # (batch, T, d_model)
            x = self.transformer(x)                            # (batch, T, d_model)
            return self.fc_out(x)                              # (batch, T, N)

    # ── 학습 함수 ─────────────────────────────────────────────────────────

    def train_model(model: nn.Module,
                    X_train: np.ndarray, y_train: np.ndarray,
                    X_valid: np.ndarray, y_valid: np.ndarray,
                    epochs: int = 100, lr: float = 0.001,
                    batch_size: int = 32,
                    model_type: str = 'fc',
                    seq_len: int = 1088) -> List[dict]:
        """
        모델을 학습합니다.

        BCEWithLogitsLoss 사용 (multi-label 문제):
        각 시점에서 여러 note가 동시에 활성화될 수 있으므로
        CrossEntropy(단일 클래스) 대신 BCE(다중 레이블) 사용.

        Args:
            model_type: 'fc' | 'lstm' | 'transformer'
                fc: 시점별 독립 미니배치 학습
                lstm/transformer: seq_len 단위로 시퀀스를 잘라서 배치 학습
            seq_len: 시퀀스 모델에서 한 시퀀스의 길이 (기본 1088)
        """
        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

        is_seq = model_type in ('lstm', 'transformer')

        # 데이터를 텐서로 변환
        X_tr_all = torch.from_numpy(X_train)
        y_tr_all = torch.from_numpy(y_train)
        X_va_all = torch.from_numpy(X_valid)
        y_va_all = torch.from_numpy(y_valid)

        history = []

        for epoch in range(epochs):
            model.train()

            if is_seq:
                # 시퀀스 모델: seq_len 단위로 잘라서 배치 구성
                # augmented 데이터는 [seq1 | seq2 | ...] 형태로 concat되어 있음
                # → seq_len 단위로 잘라서 (n_seqs, seq_len, C) 배치 구성
                n_total = len(X_tr_all)
                n_seqs = n_total // seq_len
                if n_seqs == 0:
                    n_seqs = 1
                    actual_len = n_total
                else:
                    actual_len = seq_len

                X_seqs = X_tr_all[:n_seqs * actual_len].view(n_seqs, actual_len, -1)
                y_seqs = y_tr_all[:n_seqs * actual_len].view(n_seqs, actual_len, -1)

                # 배치 단위 학습
                seq_indices = torch.randperm(n_seqs)
                total_loss = 0.0
                n_batches = 0
                for s in range(0, n_seqs, max(1, batch_size // actual_len)):
                    e = min(s + max(1, batch_size // actual_len), n_seqs)
                    idx = seq_indices[s:e]
                    pred = model(X_seqs[idx])       # (batch, seq_len, N)
                    loss_b = criterion(pred, y_seqs[idx])
                    optimizer.zero_grad()
                    loss_b.backward()
                    optimizer.step()
                    total_loss += loss_b.item()
                    n_batches += 1
                avg_loss = total_loss / max(n_batches, 1)
            else:
                # FC 모델: 시점별 미니배치
                n = len(X_tr_all)
                indices = torch.randperm(n)
                total_loss = 0.0
                n_batches = 0
                for s in range(0, n, batch_size):
                    e = min(s + batch_size, n)
                    idx = indices[s:e]
                    pred = model(X_tr_all[idx])
                    loss_b = criterion(pred, y_tr_all[idx])
                    optimizer.zero_grad()
                    loss_b.backward()
                    optimizer.step()
                    total_loss += loss_b.item()
                    n_batches += 1
                avg_loss = total_loss / max(n_batches, 1)

            # ── Validation ──
            model.eval()
            with torch.no_grad():
                if is_seq:
                    n_va = len(X_va_all)
                    n_va_seqs = max(1, n_va // seq_len)
                    va_len = min(seq_len, n_va)
                    X_va_seq = X_va_all[:n_va_seqs * va_len].view(n_va_seqs, va_len, -1)
                    y_va_seq = y_va_all[:n_va_seqs * va_len].view(n_va_seqs, va_len, -1)
                    val_pred = model(X_va_seq)
                    val_loss = criterion(val_pred, y_va_seq).item()
                else:
                    val_pred = model(X_va_all)
                    val_loss = criterion(val_pred, y_va_all).item()

            history.append({
                'epoch': epoch,
                'train_loss': avg_loss,
                'val_loss': val_loss
            })

            if epoch % 20 == 0 or epoch == epochs - 1:
                print(f"  [Epoch {epoch:3d}] train={avg_loss:.5f}  val={val_loss:.5f}")

        return history

    # ── 생성 함수 ─────────────────────────────────────────────────────────

    def generate_from_model(model: nn.Module,
                            overlap_matrix: np.ndarray,
                            notes_label: dict,
                            model_type: str = 'fc',
                            threshold: float = 0.5,
                            adaptive_threshold: bool = True) -> List[Tuple[int, int, int]]:
        """
        학습된 모델로 음악을 생성합니다.

        모델이 각 시점에서 sigmoid > threshold인 note를 활성화로 판정.
        활성화된 note label → (pitch, duration) → (onset, pitch, onset+duration) 변환.

        adaptive_threshold=True이면 모델 출력의 분포를 보고
        threshold를 자동 조정합니다. LSTM처럼 sigmoid 값이
        전체적으로 낮은 모델에서 0개 생성을 방지.

        Args:
            threshold: sigmoid 임계값 (adaptive=False일 때 사용)
            adaptive_threshold: True면 y의 ON ratio에 맞춰 threshold 자동 결정

        Returns:
            [(start, pitch, end), ...] 음표 리스트
        """
        model.eval()
        # label → (pitch, duration) 역매핑
        label_to_note = {v - 1: k for k, v in notes_label.items()}  # 0-indexed

        X = torch.from_numpy(overlap_matrix.astype(np.float32))
        if model_type in ('lstm', 'transformer'):
            X = X.unsqueeze(0)  # (1, T, C)

        with torch.no_grad():
            logits = model(X)  # FC: (T, N), seq: (1, T, N)
            if model_type in ('lstm', 'transformer'):
                logits = logits.squeeze(0)  # (T, N)
            probs = torch.sigmoid(logits)   # (T, N)

        T_out, N_out = probs.shape

        # Adaptive threshold: 원곡의 ON ratio(~15%)에 맞춰 threshold 자동 결정
        # 상위 15%의 확률값을 기준점으로 사용
        if adaptive_threshold:
            target_on_ratio = 0.15  # 원곡의 대략적 ON ratio
            k = max(1, int(T_out * N_out * target_on_ratio))
            flat = probs.flatten()
            topk_val = torch.topk(flat, k).values[-1].item()
            threshold = max(topk_val, 0.1)  # 최소 0.1

        generated = []
        for t in range(T_out):
            for n in range(N_out):
                if probs[t, n] >= threshold:
                    if n in label_to_note:
                        pitch, duration = label_to_note[n]
                        generated.append((t, pitch, t + duration))

        return generated

    # ── 기존 호환용 별칭 ──────────────────────────────────────────────────

    # 기존 pipeline.py에서 참조하는 이름 유지
    MusicGenerator = MusicGeneratorFC


# ═══════════════════════════════════════════════════════════════════════════
# Music XML 출력
# ═══════════════════════════════════════════════════════════════════════════

def notes_to_xml(notes_list: List[List[Tuple[int, int, int]]],
                 tempo_bpm: int = 66,
                 file_name: str = "generated",
                 output_dir: str = "./output"):
    """
    생성된 음표를 MusicXML로 저장합니다.
    process.py의 notes_to_score_xml 간소화 버전.
    """
    try:
        from music21 import stream, note, tempo, chord, clef, meter, instrument
    except ImportError:
        print("music21이 설치되어 있지 않습니다.")
        return None
    
    s = stream.Score()
    
    for inst_idx, inst_notes in enumerate(notes_list):
        if not inst_notes:
            continue
        
        p = stream.Part()
        p.id = f"Instrument {inst_idx + 1}"
        p.insert(0, instrument.Instrument(instrumentNumber=inst_idx + 1))
        p.insert(0, meter.TimeSignature('4/4'))
        p.insert(0, clef.TrebleClef())
        p.insert(0, tempo.MetronomeMark(number=tempo_bpm))
        
        # 시작 시간별 그룹화
        by_start = {}
        for start, pitch, end in inst_notes:
            by_start.setdefault(start, []).append((pitch, end))
        
        start_offset = inst_notes[0][0] if inst_notes else 0
        max_end = max(e for _, _, e in inst_notes)
        
        for t in range(max_end):
            # 활성화 여부 확인
            is_active = any(s <= t < e for s, _, e in inst_notes)
            
            if not is_active:
                r = note.Rest()
                r.offset = float(t / 2) + start_offset
                r.quarterLength = 0.5
                p.append(r)
            elif t in by_start:
                pitches = by_start[t]
                if len(pitches) > 1:
                    # 화음
                    chord_notes = []
                    for pitch_val, end_val in pitches:
                        n = note.Note()
                        n.pitch.midi = pitch_val
                        n.quarterLength = float((end_val - t) / 2)
                        chord_notes.append(n)
                    c = chord.Chord(chord_notes)
                    c.offset = float(t / 2) + start_offset
                    p.append(c)
                else:
                    pitch_val, end_val = pitches[0]
                    n = note.Note()
                    n.pitch.midi = pitch_val
                    n.quarterLength = float((end_val - t) / 2)
                    n.offset = float(t / 2) + start_offset
                    p.append(n)
        
        s.append(p)
    
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f'{file_name}.musicxml')
    s.write('musicxml', fp=filepath)
    print(f"MusicXML 저장: {filepath}")
    return s
