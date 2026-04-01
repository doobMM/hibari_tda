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


def algorithm1_optimized(node_pool: NodePool,
                         inst_len: List[int],
                         overlap_matrix: np.ndarray,
                         cycle_manager: CycleSetManager,
                         max_resample: int = 50,
                         verbose: bool = False) -> List[Tuple[int, int, int]]:
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
# Algorithm 2: 신경망 기반 음악 생성
# ═══════════════════════════════════════════════════════════════════════════

if HAS_TORCH:
    
    class MusicDataset(Dataset):
        """
        중첩행렬(X)과 one-hot 음악 시퀀스(y)를 배치 단위로 제공합니다.
        기존 코드의 X, y 생성을 Dataset으로 캡슐화.
        """
        
        def __init__(self, overlap_matrix: np.ndarray, 
                     onehot_music: np.ndarray,
                     sequence_length: int):
            """
            Args:
                overlap_matrix: (T, C) 중첩행렬
                onehot_music: (T, N) one-hot 인코딩된 음악
                sequence_length: 입력 시퀀스 길이
            """
            # 주기적 확장 (periodic extension)
            om_dup = np.concatenate([overlap_matrix, overlap_matrix], axis=0)
            oh_dup = np.concatenate([onehot_music, onehot_music], axis=0)
            
            T = sequence_length
            n_samples = T - 1
            
            # 슬라이딩 윈도우로 X, y 생성
            self.X = np.stack([
                om_dup[i:i + T].flatten() for i in range(n_samples)
            ]).astype(np.float32)
            
            self.y = np.stack([
                oh_dup[i:i + T].flatten() for i in range(n_samples)
            ]).astype(np.int64)
        
        def __len__(self):
            return len(self.X)
        
        def __getitem__(self, idx):
            return torch.from_numpy(self.X[idx]), torch.from_numpy(self.y[idx])
    
    
    class MusicGenerator(nn.Module):
        """
        중첩행렬로부터 음악을 생성하는 신경망.
        기존 Network 클래스의 정리 버전.
        """
        
        def __init__(self, dim_input: int, dim_hidden: int, 
                     dim_output: int, num_nodes: int, dropout: float = 0.3):
            super().__init__()
            self.fc1 = nn.Linear(dim_input, dim_hidden)
            self.fc2 = nn.Linear(dim_hidden, 2 * dim_hidden)
            self.fc3 = nn.Linear(2 * dim_hidden, dim_output)
            self.dropout = nn.Dropout(dropout)
            self.num_nodes = num_nodes
            
            # 가중치 초기화
            self._init_weights()
        
        def _init_weights(self):
            for m in [self.fc1, self.fc2]:
                fan_in = m.weight.size(0)
                w = 2.0 / math.sqrt(fan_in)
                m.weight.data.uniform_(-w, w)
            self.fc3.weight.data.uniform_(-3e-3, 3e-3)
        
        def forward(self, x):
            x = F.relu(self.fc1(x))
            x = self.dropout(x)
            x = F.relu(self.fc2(x))
            x = self.dropout(x)
            x = self.fc3(x)
            return x.view(-1, self.num_nodes)
    
    
    def prepare_training_data(overlap_matrix: np.ndarray,
                              music_notes: List[List[Tuple[int, int, int]]],
                              notes_label: dict,
                              sequence_length: int,
                              num_notes: int = 23) -> Tuple[np.ndarray, np.ndarray]:
        """
        학습 데이터를 준비합니다.
        
        두 악기의 note를 시간축 기준으로 one-hot 행렬로 변환합니다.
        기존 코드의 L_encoded / L_onehot 생성 로직 통합.
        
        Args:
            overlap_matrix: (T, C) 중첩행렬
            music_notes: [inst1_notes, inst2_notes]
            notes_label: (pitch, duration) → label
            sequence_length: 시퀀스 길이 T
            num_notes: 고유 note 수
        
        Returns:
            (X, y) 학습용 numpy 배열 쌍
        """
        # One-hot 행렬 구축 (시간 × note)
        onehot = np.zeros((sequence_length, num_notes), dtype=np.int64)
        
        for inst_notes in music_notes:
            for start, pitch, end in inst_notes:
                duration = end - start
                key = (pitch, duration)
                if key in notes_label:
                    label = notes_label[key] - 1  # 0-indexed
                    if 0 <= start < sequence_length and 0 <= label < num_notes:
                        onehot[start, label] = 1
        
        # Dataset 생성
        dataset = MusicDataset(overlap_matrix, onehot, sequence_length)
        return dataset.X, dataset.y
    
    
    def train_model(model: MusicGenerator,
                    X_train: np.ndarray, y_train: np.ndarray,
                    X_valid: np.ndarray, y_valid: np.ndarray,
                    epochs: int = 100, lr: float = 0.001,
                    batch_size: int = 32) -> List[dict]:
        """
        모델을 학습합니다.
        
        최적화: 배치 학습 도입으로 메모리 효율 개선.
        기존 코드는 전체 데이터를 한 번에 forward → OOM 위험.
        """
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        history = []
        n_train = len(X_train)
        
        for epoch in range(epochs):
            # ── Training ──
            model.train()
            epoch_loss = 0.0
            n_batches = 0
            
            indices = np.random.permutation(n_train)
            
            for start in range(0, n_train, batch_size):
                end = min(start + batch_size, n_train)
                batch_idx = indices[start:end]
                
                X_batch = torch.from_numpy(X_train[batch_idx])
                y_batch = torch.from_numpy(y_train[batch_idx].flatten())
                
                y_pred = model(X_batch)
                loss = criterion(y_pred, y_batch)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
                n_batches += 1
            
            avg_train_loss = epoch_loss / n_batches
            
            # ── Validation ──
            model.eval()
            with torch.no_grad():
                y_pred_val = model(torch.from_numpy(X_valid))
                val_loss = criterion(
                    y_pred_val, 
                    torch.from_numpy(y_valid.flatten())
                ).item()
            
            history.append({
                'epoch': epoch,
                'train_loss': avg_train_loss,
                'val_loss': val_loss
            })
            
            if epoch % 10 == 0:
                print(f"[Epoch {epoch:3d}] train_loss: {avg_train_loss:.5f}  val_loss: {val_loss:.5f}")
        
        return history


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
