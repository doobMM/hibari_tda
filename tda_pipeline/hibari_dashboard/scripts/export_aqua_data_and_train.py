"""
export_aqua_data_and_train.py — aqua 대시보드 데이터 + Transformer 모델 생성
==================================================================================

hibari 외에 aqua 곡을 대시보드에서 사용할 수 있도록
(1) data_aqua/ 하위 JSON 5종 + MIDI 복사
(2) public/models/transformer_aqua.onnx + transformer_aqua_meta.json
을 생성한다.

연구 근거:
  - aqua는 chromatic(12 PC), tonnetz 거리 + Transformer 모델이 최적.
  - CLAUDE.md §핵심 발견 — 곡의 성격이 최적 도구를 결정한다 참조.

출력 스키마:
  data_aqua/ — export_hibari_data.py와 동일한 JSON 필드 구조
  models/ — train_fc_and_export.py의 meta 스키마 + model_type:'transformer' 추가

주의:
  - 기존 tda_pipeline/ 모듈은 import만. 수정 금지.
  - 웹 자산(js/html/css), data/(hibari), 기존 모델 파일 수정 금지.
  - os.chdir(TDA_ROOT) 로 cache 등 상대경로 맞춤.
"""

import os
import sys
import json
import shutil
import time
import warnings
from pathlib import Path
from math import gcd
from functools import reduce
from collections import Counter

import copy
import re
from collections import defaultdict

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

warnings.filterwarnings('ignore')

# ─── 경로 설정 ──────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent          # scripts/
DASH_ROOT = HERE.parent                          # hibari_dashboard/
TDA_ROOT = DASH_ROOT.parent                      # tda_pipeline/
DATA_SOL = DASH_ROOT / 'data_aqua'
MODELS_DIR = DASH_ROOT / 'public' / 'models'

DATA_SOL.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# tda_pipeline을 sys.path에 추가 (import용)
sys.path.insert(0, str(TDA_ROOT))
sys.path.insert(0, str(TDA_ROOT / 'experiments'))

MIDI_SRC = TDA_ROOT / 'aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid'

# ─── 전처리 설정 (run_aqua.py와 동일 파라미터) ──────────────────────────

ALPHA = 0.5           # hybrid α (솔라리 기본값)
RATE_STEP = 0.05      # PH rate sweep 간격
THRESHOLD = 0.35      # overlap 이진화 임계값

OPTIMAL_CONFIG = {
    'metric': 'tonnetz',
    'alpha': ALPHA,
    'search_type': 'timeflow',
    'lag_mode': 'lag_1',
    'max_lag': 1,
    'min_onset_gap': 0,
    'threshold': THRESHOLD,
    'description': 'aqua 최적: tonnetz 거리 (chromatic 12 PC, 선율적 진행)',
}

# ─── 전처리 (run_aqua.preprocess 에서 발췌) ────────────────────────────────

def preprocess(midi_path: str):
    """aqua MIDI → notes_label, notes_counts, adn_i, N, T, num_chords 반환."""
    from preprocessing import (
        load_and_quantize, split_instruments, build_note_labels,
        group_notes_with_duration, build_chord_labels, chord_to_note_labels,
        prepare_lag_sequences, simul_chord_lists, simul_union_by_dict,
    )

    print("  load_and_quantize...")
    adj, tempo, bounds = load_and_quantize(midi_path)
    inst1_raw, inst2_raw = split_instruments(adj, bounds[0])
    print(f"  tempo={tempo:.1f} BPM, inst1={len(inst1_raw)}, inst2={len(inst2_raw)}")

    # tie 정규화 (run_aqua.py와 동일)
    durs1 = [e - s for s, _, e in inst1_raw if e > s]
    durs2 = [e - s for s, _, e in inst2_raw if e > s]
    g = reduce(gcd, durs1 + durs2) if (durs1 + durs2) else 1
    inst1 = [(s, p, s + g) for s, p, e in inst1_raw]
    inst2 = [(s, p, s + g) for s, p, e in inst2_raw]
    print(f"  tie GCD={g}")

    # 통합 chord map (run_aqua.py와 동일)
    active1 = group_notes_with_duration(inst1)
    active2 = group_notes_with_duration(inst2)
    umap = {}
    cnt = 0

    def label(active):
        nonlocal cnt
        out = []
        for t in sorted(active.keys()):
            ps = active[t]
            if ps is None:
                out.append(None)
                continue
            fs = frozenset(ps)
            if fs not in umap:
                umap[fs] = cnt
                cnt += 1
            out.append(umap[fs])
        return out

    cs1 = label(active1)
    cs2 = label(active2)
    nc = cnt

    all_notes = inst1 + inst2
    notes_label, notes_counts = build_note_labels(all_notes)
    N = len(notes_label)
    notes_dict = chord_to_note_labels(umap, notes_label)
    notes_dict['name'] = 'notes'

    sp = min(32, max(1, len(cs1) // 8))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=sp, max_lag=4)
    T = max(e for _, _, e in adj) if adj else 0

    print(f"  N={N}, num_chords={nc}, T={T}, sp={sp}")

    return {
        'inst1': inst1, 'inst2': inst2,
        'inst1_raw': inst1_raw, 'inst2_raw': inst2_raw,
        'notes_label': notes_label, 'notes_counts': notes_counts,
        'notes_dict': notes_dict, 'adn_i': adn_i,
        'N': N, 'num_chords': nc, 'T': T, 'tempo': tempo,
    }


# ─── PH + overlap 계산 (run_aqua.compute_ph에서 발췌, tonnetz 고정) ─

def compute_overlap(data):
    """tonnetz 거리로 PH 계산 → (cycle_labeled, binary_ov, cont_act) 반환."""
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach,
    )
    from overlap import (
        group_rBD_by_homology, label_cycles_from_persistence,
        build_activation_matrix, build_overlap_matrix,
    )
    from topology import generate_barcode_numpy
    from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
    from preprocessing import simul_chord_lists, simul_union_by_dict

    adn_i = data['adn_i']
    nd = data['notes_dict']
    nl = data['notes_label']
    N = data['N']
    T = data['T']
    nc = data['num_chords']
    metric = 'tonnetz'

    print(f"  [tonnetz] note 거리 행렬 계산...")
    m_dist = compute_note_distance_matrix(nl, metric=metric)

    w1 = compute_intra_weights(adn_i[1][0], num_chords=nc)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=nc)
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], num_chords=nc, lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    print(f"  PH rate sweep 시작 (0.0 → 1.5, step={RATE_STEP})...")
    profile = []
    rate = 0.0
    t0 = time.time()
    while rate <= 1.5 + 1e-10:
        r = round(rate, 3)
        tw = intra + r * inter
        fd = compute_distance_matrix(tw, nd, oor, num_notes=N).values
        final = compute_hybrid_distance(fd, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((r, bd))
        rate += RATE_STEP
    print(f"  PH sweep: {len(profile)} steps, {time.time() - t0:.1f}s", flush=True)

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_labeled = label_cycles_from_persistence(persistence)
    if not cycle_labeled:
        raise RuntimeError("cycle_labeled 가 비어 있음 — PH 결과 없음")

    K = len(cycle_labeled)
    print(f"  K={K} cycles 발견")

    # activation matrix 구성 (run_aqua.py 방식)
    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    ns = simul_union_by_dict(cp, nd)
    nodes = list(range(1, N + 1))
    ntd = np.zeros((T, N), dtype=int)
    for t in range(min(T, len(ns))):
        if ns[t]:
            for n in ns[t]:
                if 1 <= n <= N:
                    ntd[t, n - 1] = 1
    ntd_df = pd.DataFrame(ntd, columns=nodes)

    # 이진 overlap (threshold=0.35)
    act_bin = build_activation_matrix(ntd_df, cycle_labeled)
    ov_df = build_overlap_matrix(act_bin, cycle_labeled, threshold=THRESHOLD, total_length=T)
    binary_ov = ov_df.values  # (T, K)

    # 연속 activation
    act_cont = build_activation_matrix(ntd_df, cycle_labeled, continuous=True)
    cont_act = act_cont.values.astype(np.float32)  # (T, K)

    print(f"  overlap shape={binary_ov.shape}, density={(binary_ov > 0).mean():.3f}")
    print(f"  continuous range=[{cont_act.min():.3f}, {cont_act.max():.3f}]")

    return cycle_labeled, binary_ov, cont_act, profile


# ─── JSON Export ─────────────────────────────────────────────────────────────

def export_overlap_matrices(T, K, binary_ov, cont_act):
    """이진 + 연속 overlap JSON 저장."""
    density = float(binary_ov.astype(bool).sum()) / binary_ov.size

    # 이진 overlap
    ref_payload = {
        'shape': [T, K],
        'T': T,
        'K': K,
        'density': round(density, 6),
        'optimal_config': OPTIMAL_CONFIG,
        'description': (
            'aqua tonnetz PH (α=0.5, timeflow, threshold=0.35) 이진 overlap. '
            'overlap[t*K + c] 로 접근. 1=활성, 0=비활성.'
        ),
        'values': binary_ov.astype(int).flatten().tolist(),
    }
    out1 = DATA_SOL / 'overlap_matrix_reference.json'
    with open(out1, 'w', encoding='utf-8') as f:
        json.dump(ref_payload, f, ensure_ascii=False)
    print(f"[save] {out1} ({out1.stat().st_size / 1024:.1f} KB)")

    # 연속 activation
    cont_rounded = np.round(cont_act, 4)
    cont_payload = {
        'shape': [T, K],
        'T': T,
        'K': K,
        'min': float(cont_act.min()),
        'max': float(cont_act.max()),
        'mean': float(cont_act.mean()),
        'optimal_config': OPTIMAL_CONFIG,
        'description': (
            '연속 activation. soft Algo2 입력용. '
            '값 ∈ [0, 1]. values[t*K + c].'
        ),
        'values': cont_rounded.flatten().tolist(),
    }
    out2 = DATA_SOL / 'overlap_matrix_continuous.json'
    with open(out2, 'w', encoding='utf-8') as f:
        json.dump(cont_payload, f, ensure_ascii=False)
    print(f"[save] {out2} ({out2.stat().st_size / 1024:.1f} KB)")


def export_notes_metadata(data):
    """notes_label, notes_counts → notes_metadata.json 저장."""
    notes_label = data['notes_label']
    notes_counts = data['notes_counts']

    labels = []
    for (pitch, dur), lbl in sorted(notes_label.items(), key=lambda x: x[1]):
        labels.append({
            'label': int(lbl),
            'label_idx': int(lbl) - 1,
            'pitch': int(pitch),
            'dur': int(dur),
            'count': int(notes_counts.get((pitch, dur), 0)),
            'pc': int(pitch) % 12,
        })

    total_count = sum(n['count'] for n in labels)
    payload = {
        'num_notes': len(labels),
        'total_count_per_module': total_count,
        'num_modules_reference': 65,
        'labels': labels,
        'description': (
            'aqua note 메타데이터. '
            '각 note는 (pitch, dur) 튜플 고유. label은 1-indexed. '
            'JS 포팅 시 label_idx (0-indexed) 사용 권장. '
            'count는 한 모듈 내 빈도.'
        ),
    }

    out = DATA_SOL / 'notes_metadata.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[save] {out} (N={len(labels)})")
    return labels


# ─── Traversal 헬퍼 (add_cycle_traversal.py와 동일 로직, aqua 경로 대응) ──

def _parse_edges(edges_str: str):
    """edges_str → 정규화된 edge 집합 (min,max 튜플)."""
    edges_raw = re.findall(r'([+-])?\s*\(\s*(\d+)\s*,\s*(\d+)\)', edges_str)
    edges = set()
    for _sign, v1, v2 in edges_raw:
        a, b = int(v1), int(v2)
        edges.add((min(a, b), max(a, b)))
    return edges


def _traverse_cycle(edges):
    """Edge 집합 → 연결된 순서 vertex 리스트. 단순 cycle만 지원, 그 외엔 None."""
    if not edges:
        return None
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    for v, nbrs in adj.items():
        if len(nbrs) != 2:
            return None
    start = min(adj.keys())
    traversal = [start]
    prev = None
    current = start
    visited = {start}
    while True:
        next_v = None
        for n in adj[current]:
            if n == prev:
                continue
            if n == start and len(traversal) >= 3:
                return traversal
            if n not in visited:
                next_v = n
                break
        if next_v is None:
            return None
        traversal.append(next_v)
        visited.add(next_v)
        prev = current
        current = next_v


def _extract_traversal_from_ph(profile_bd, verts_0idx: set):
    """PH barcode 전체를 순회하여 verts_0idx 집합과 매칭되는 traversal을 찾는다.

    profile_bd: [(rate, bd_list), ...] — compute_overlap 내부의 profile 배열.
    가중치 행렬에서 직접 edge 목록을 추출 불가한 경우 note_labels 정렬 순서로 fallback.
    """
    target = frozenset(int(v) for v in verts_0idx)
    for _r, bd in profile_bd:
        for entry in bd:
            if not isinstance(entry, list) or len(entry) < 3:
                continue
            if entry[0] != 1:
                continue
            edges_str = str(entry[2]).strip()
            edges = _parse_edges(edges_str)
            if not edges:
                continue
            vset = frozenset(v for e in edges for v in e)
            if vset == target:
                trav = _traverse_cycle(edges)
                if trav is not None and set(trav) == set(target):
                    return trav
    return None


def export_cycles_metadata(cycle_labeled, profile_bd=None):
    """cycle_labeled → cycles_metadata.json 저장.

    profile_bd: compute_overlap에서 수집한 (rate, bd) 리스트.
    None이면 traversal을 note_labels 정렬 순서로 fallback.
    """
    # tau는 threshold=0.35 균일 적용 (per-cycle τ 미적용)
    cycles_info = []
    matched_trav = 0
    for c_idx, cycle_key in cycle_labeled.items():
        if isinstance(cycle_key, frozenset):
            verts = set()
            for simplex in cycle_key:
                if isinstance(simplex, tuple):
                    verts.update(simplex)
                else:
                    verts.add(simplex)
        else:
            verts = set(cycle_key)

        note_labels_1idx = sorted(int(v) + 1 for v in verts)
        verts_0idx_sorted = sorted(int(v) for v in verts)

        # traversal 추출
        if profile_bd is not None:
            trav = _extract_traversal_from_ph(profile_bd, verts)
        else:
            trav = None

        if trav is not None:
            traversal_0idx = trav
            traversal_1idx = [v + 1 for v in trav]
            matched_trav += 1
        else:
            # fallback: 정렬 순서
            traversal_0idx = verts_0idx_sorted
            traversal_1idx = [v + 1 for v in verts_0idx_sorted]

        cycles_info.append({
            'cycle_idx': int(c_idx),
            'vertices_0idx': verts_0idx_sorted,
            'note_labels_1idx': note_labels_1idx,
            'note_labels_0idx': [n - 1 for n in note_labels_1idx],
            'size': len(note_labels_1idx),
            'tau': float(THRESHOLD),
            'traversal_0idx': traversal_0idx,
            'traversal_1idx': traversal_1idx,
            'persistence_entries': [],
            'max_persistence': 0.0,
        })

    print(f"  traversal 추출: {matched_trav}/{len(cycles_info)} cycles (나머지는 정렬 순서 fallback)")

    payload = {
        'num_cycles': len(cycles_info),
        'source': f'tonnetz timeflow PH (α={ALPHA}, threshold={THRESHOLD})',
        'cycles': cycles_info,
        'description': (
            '각 cycle은 note 정점들의 순환 구조. '
            'vertices_0idx는 내부 행렬 접근용, note_labels_1idx는 notes_metadata의 label과 매칭. '
            f'tau는 균일 이진화 임계값 ({THRESHOLD}). '
            'traversal_0idx/traversal_1idx는 cycle edge를 따라 연결된 재생 순서 '
            '(단순 cycle 가정; 미발견 시 정렬 순서 fallback).'
        ),
    }

    out = DATA_SOL / 'cycles_metadata.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[save] {out} (K={len(cycles_info)})")


def copy_midi(src: Path):
    """원곡 MIDI 복사."""
    if not src.exists():
        print(f"[경고] 원곡 MIDI 없음: {src}")
        return
    dst = DATA_SOL / 'original_aqua.mid'
    shutil.copy2(src, dst)
    print(f"[save] {dst} ({dst.stat().st_size / 1024:.1f} KB)")


def export_manifest(T, K, N):
    """manifest.json 저장."""
    manifest = {
        'version': '2.0',
        'song': 'aqua',
        'generated_at': pd.Timestamp.now().isoformat(),
        'optimal_config': OPTIMAL_CONFIG,
        'shape': {'T': T, 'K': K},
        'files': [
            'overlap_matrix_reference.json',
            'overlap_matrix_continuous.json',
            'notes_metadata.json',
            'cycles_metadata.json',
            'original_aqua.mid',
        ],
        'notes': (
            'aqua 최적 설정: tonnetz 거리 + Transformer 모델. '
            f'N={N} notes (tie 정규화), K={K} cycles, T={T} time steps. '
            'Algo2 모델: transformer_aqua.onnx (public/models/).'
        ),
    }

    out = DATA_SOL / 'manifest.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[save] {out}")


# ─── 동적 T 지원 커스텀 Transformer ─────────────────────────────────────────
#
# nn.TransformerEncoderLayer 는 TorchScript ONNX export 시 T를 고정으로 trace.
# (PyTorch 2.11 + onnxruntime 1.20 환경에서 재현 확인)
# dynamo=True 는 onnxscript 의존이라 미설치 환경에서 사용 불가.
# 따라서: 동일 계산을 수동 구현하여 Reshape 노드가 T를 상수로 굽지 않게 함.
# 가중치 구조가 generation.py MusicGeneratorTransformer와 다르므로,
# 학습도 이 클래스를 직접 사용한다 (generation.py 수정 없이).

class _MultiHeadSelfAttn(nn.Module):
    """동적 T ONNX export 가능한 self-attention."""

    def __init__(self, d_model: int, nhead: int, dropout: float = 0.1):
        super().__init__()
        self.nhead = nhead
        self.head_dim = d_model // nhead
        self.qkv = nn.Linear(d_model, d_model * 3, bias=True)
        self.out_proj = nn.Linear(d_model, d_model, bias=True)
        self.attn_drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        H, hd = self.nhead, self.head_dim
        # (B, T, 3*D) → (B, T, 3, H, hd) → (3, B, H, T, hd)
        qkv = self.qkv(x).reshape(B, T, 3, H, hd).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]         # 각 (B, H, T, hd)
        scale = float(hd) ** -0.5
        attn = torch.matmul(q, k.transpose(-2, -1)) * scale  # (B, H, T, T)
        attn = torch.softmax(attn, dim=-1)
        attn = self.attn_drop(attn)
        out = torch.matmul(attn, v)                # (B, H, T, hd)
        out = out.transpose(1, 2).contiguous().reshape(B, T, D)
        return self.out_proj(out)


class _TransformerBlock(nn.Module):
    """Pre-LN Transformer block (ONNX 동적 T 호환)."""

    def __init__(self, d_model: int, nhead: int, ff_dim: int, dropout: float = 0.1):
        super().__init__()
        self.attn = _MultiHeadSelfAttn(d_model, nhead, dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, ff_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(ff_dim, d_model), nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class DynTransformerModel(nn.Module):
    """
    동적 시퀀스 길이 지원 Transformer.

    입력: (batch, T, K)  — T가 ONNX dynamic axis로 노출됨
    출력: (batch, T, N)

    generation.py MusicGeneratorTransformer와 동일한 역할이지만
    nn.TransformerEncoderLayer 대신 수동 구현을 사용하여
    torch.onnx.export(dynamo=False) + onnxruntime에서 임의 T를 처리한다.
    """

    def __init__(self, num_cycles: int, num_notes: int,
                 d_model: int = 128, nhead: int = 4,
                 num_layers: int = 2, dropout: float = 0.1,
                 max_len: int = 256):
        super().__init__()
        self.input_proj = nn.Linear(num_cycles, d_model)
        self.pos_emb = nn.Parameter(torch.randn(1, max_len, d_model) * 0.02)
        self.layers = nn.ModuleList([
            _TransformerBlock(d_model, nhead, d_model * 4, dropout)
            for _ in range(num_layers)
        ])
        self.fc_out = nn.Linear(d_model, num_notes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.size(1)
        x = self.input_proj(x)
        x = x + self.pos_emb[:, :T, :]
        for layer in self.layers:
            x = layer(x)
        return self.fc_out(x)


# ─── Transformer 모델 학습 ────────────────────────────────────────────────────

def build_onehot_y(data, T, N):
    """원곡 note onset multi-hot (T, N) 행렬 구성."""
    from preprocessing import simul_chord_lists, simul_union_by_dict

    adn_i = data['adn_i']
    nd = data['notes_dict']
    nl = data['notes_label']

    cp = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    ns = simul_union_by_dict(cp, nd)

    # label → (pitch, dur) 역매핑
    label_to_pd = {v: k for k, v in nl.items()}

    prev_active = set()
    onehot = np.zeros((T, N), dtype=np.float32)

    for t in range(min(T, len(ns))):
        curr = set(ns[t]) if ns[t] else set()
        new_onsets = curr - prev_active
        for lbl in new_onsets:
            if lbl not in label_to_pd:
                continue
            pitch, dur = label_to_pd[lbl]
            key = (pitch, dur)
            if key in nl:
                label_idx = nl[key] - 1  # 0-indexed
                if 0 <= t < T and 0 <= label_idx < N:
                    onehot[t, label_idx] = 1.0
        prev_active = curr

    return onehot


def augment(X: np.ndarray, y: np.ndarray,
            n_shifts: int = 4, noise_prob: float = 0.03,
            n_noise: int = 3, rng=None):
    """circular shift + noise injection 증강 (train_fc_and_export.py 방식)."""
    if rng is None:
        rng = np.random.default_rng(0)
    T = X.shape[0]
    all_X = [X]
    all_y = [y]

    for _ in range(n_shifts):
        s = int(rng.integers(1, T))
        all_X.append(np.roll(X, s, axis=0))
        all_y.append(np.roll(y, s, axis=0))

    for _ in range(n_noise):
        mask = rng.random(X.shape) < noise_prob
        Xn = X.copy()
        Xn[mask] = 1.0 - Xn[mask]
        all_X.append(Xn.astype(np.float32))
        all_y.append(y.copy())

    return np.concatenate(all_X, axis=0), np.concatenate(all_y, axis=0)


def train_transformer(X_aug: np.ndarray, y_aug: np.ndarray,
                      K: int, N: int, T_orig: int,
                      d_model: int = 128, nhead: int = 4,
                      num_layers: int = 2, dropout: float = 0.1,
                      epochs: int = 100, lr: float = 1e-3, batch_size: int = 32,
                      seed: int = 42):
    """
    DynTransformerModel 학습.

    DynTransformerModel을 사용하는 이유:
      - nn.TransformerEncoderLayer 기반 MusicGeneratorTransformer는
        TorchScript ONNX export 시 T를 고정으로 trace하여,
        export 시와 다른 T로 inference 시 Reshape 에러 발생.
      - DynTransformerModel은 수동 구현으로 동적 T 지원.
      - 학습 루프는 직접 구현 (generation.train_model과 동일 방식).

    X_aug: (T_aug, K), y_aug: (T_aug, N) — 증강 후 행 concat.
    시퀀스 모델이므로 (seq, T_orig, K) 형태로 배치 구성.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    # max_len: T_orig 이상, T=60 윈도우도 처리 가능
    max_len = max(T_orig, 256)

    model = DynTransformerModel(
        num_cycles=K,
        num_notes=N,
        d_model=d_model,
        nhead=nhead,
        num_layers=num_layers,
        dropout=dropout,
        max_len=max_len,
    )

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # 7:3 train/val 분할 (행 단위)
    n_total = X_aug.shape[0]
    perm = np.random.RandomState(seed).permutation(n_total)
    Xp = X_aug[perm]
    yp = y_aug[perm]
    sp = int(n_total * 0.7)
    X_tr_np = Xp[:sp]
    y_tr_np = yp[:sp]
    X_va_np = Xp[sp:]
    y_va_np = yp[sp:]

    print(f"  학습 행 수: X_tr={X_tr_np.shape}, X_va={X_va_np.shape}")

    # 시퀀스 단위 배치 구성 (generation.train_model 방식과 동일)
    # X_aug는 [seq1 | seq2 | ...] concat 형태 → T_orig 단위로 자름
    seq_len = T_orig

    def make_seqs(X_np, y_np):
        n = len(X_np)
        n_seqs = max(1, n // seq_len)
        actual = min(seq_len, n)
        Xs = torch.from_numpy(X_np[:n_seqs * actual]).view(n_seqs, actual, K)
        ys = torch.from_numpy(y_np[:n_seqs * actual]).view(n_seqs, actual, N)
        return Xs, ys

    X_tr, y_tr = make_seqs(X_tr_np, y_tr_np)
    X_va, y_va = make_seqs(X_va_np, y_va_np)
    print(f"  시퀀스 배치: X_tr={tuple(X_tr.shape)}, X_va={tuple(X_va.shape)}")

    history = []
    best_val_loss = float('inf')
    best_state = None
    best_epoch = 0

    for ep in range(epochs):
        model.train()
        perm_seq = torch.randperm(X_tr.shape[0])
        total_loss, nb = 0.0, 0
        bs = max(1, batch_size // seq_len)
        for s in range(0, X_tr.shape[0], bs):
            e = min(s + bs, X_tr.shape[0])
            idx = perm_seq[s:e]
            pred = model(X_tr[idx])   # (batch, seq_len, N)
            loss = criterion(pred, y_tr[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            nb += 1
        tr_loss = total_loss / max(nb, 1)

        model.eval()
        with torch.no_grad():
            val_pred = model(X_va)
            val_loss = criterion(val_pred, y_va).item()

        # best-checkpoint 추적
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = ep
            best_state = copy.deepcopy(model.state_dict())

        history.append({'epoch': ep, 'train_loss': tr_loss, 'val_loss': val_loss})
        if ep % 20 == 0 or ep == epochs - 1:
            print(f"  [Epoch {ep:3d}] train={tr_loss:.5f}  val={val_loss:.5f}  (best_val={best_val_loss:.5f} @ ep{best_epoch})")

    print(f"  best checkpoint: epoch={best_epoch}, val_loss={best_val_loss:.5f}")
    # best 가중치 복원
    model.load_state_dict(best_state)

    return model, history, max_len, best_epoch, best_val_loss


def export_transformer_onnx(model, K: int, N: int, T_orig: int, out_path: Path):
    """
    DynTransformerModel → ONNX export.

    입력: 'overlap' [batch, T, K]  (T=동적축)
    출력: 'logits'  [batch, T, N]

    DynTransformerModel은 수동 self-attention 구현으로 동적 T 지원.
    더미 입력 T=60으로 export (대시보드 30초 세그먼트 기준).
    opset 17 → 16 → 18 → 14 순서로 fallback.
    """
    model.eval()
    # 더미 입력 T=60 (대시보드 세그먼트 기준, T_orig=224와 독립적)
    dummy = torch.randn(1, 60, K)

    for opset in [17, 16, 18, 14]:
        try:
            print(f"  ONNX export 시도 (opset={opset}, dynamo=False)...")
            try:
                torch.onnx.export(
                    model, dummy, str(out_path),
                    input_names=['overlap'],
                    output_names=['logits'],
                    dynamic_axes={
                        'overlap': {0: 'B', 1: 'T'},
                        'logits':  {0: 'B', 1: 'T'},
                    },
                    opset_version=opset,
                    dynamo=False,
                )
            except TypeError:
                # 구형 torch — dynamo 파라미터 없음
                torch.onnx.export(
                    model, dummy, str(out_path),
                    input_names=['overlap'],
                    output_names=['logits'],
                    dynamic_axes={
                        'overlap': {0: 'B', 1: 'T'},
                        'logits':  {0: 'B', 1: 'T'},
                    },
                    opset_version=opset,
                )
            print(f"  [onnx] opset={opset} export 성공: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
            return opset
        except Exception as e:
            print(f"  [경고] opset={opset} 실패: {type(e).__name__}: {e}")
            if out_path.exists():
                out_path.unlink()

    raise RuntimeError(
        "ONNX export 실패 — opset 17/16/18/14 모두 실패. "
        "torch.onnx.export 에러를 확인하여 수동 수정 필요."
    )


def verify_onnx(model, onnx_path: Path, K: int, N: int, T_dummy: int = 60):
    """
    onnxruntime으로 (1, T_dummy, K) 더미 입력 → (1, T_dummy, N) 출력 검증.
    torch vs ort 최대 오차 확인.
    """
    try:
        import onnxruntime as ort
    except ImportError:
        print("  [경고] onnxruntime 미설치 — 검증 생략")
        return None, None

    model.eval()
    dummy = torch.randn(1, T_dummy, K)

    with torch.no_grad():
        torch_out = model(dummy).numpy()  # (1, T_dummy, N)

    sess = ort.InferenceSession(str(onnx_path))
    ort_out = sess.run(['logits'], {'overlap': dummy.numpy()})[0]  # (1, T_dummy, N)

    err = float(np.abs(torch_out - ort_out).max())
    print(f"  torch vs ort 최대 오차 (T={T_dummy}): {err:.6e}")
    if err > 1e-3:
        print("  [경고] 오차 > 1e-3 — ONNX 변환 결과 확인 필요")
    else:
        print("  [OK] 오차 < 1e-3")

    # 출력 shape 확인
    print(f"  ORT 출력 shape: {ort_out.shape}")
    assert ort_out.shape == (1, T_dummy, N), \
        f"출력 shape 불일치: {ort_out.shape} != (1, {T_dummy}, {N})"
    return err, ort_out.shape


def save_transformer_meta(K: int, N: int, max_len: int,
                          notes_label: dict, history: list,
                          opset: int, out_path: Path,
                          best_epoch: int = None, best_val_loss: float = None):
    """transformer_aqua_meta.json 저장 (train_fc_and_export.py meta 스키마 + model_type)."""
    # label_to_note 매핑 (train_fc_and_export.py save_meta 동일 구조)
    label_to_pd = {v - 1: k for k, v in notes_label.items()}
    labels_sorted = []
    for li in sorted(label_to_pd.keys()):
        pitch, dur = label_to_pd[li]
        labels_sorted.append({
            'label_idx': li,
            'label': li + 1,
            'pitch': int(pitch),
            'dur': int(dur),
        })

    meta = {
        'version': '2.0',
        'model_type': 'transformer',
        'song': 'aqua',
        'architecture': (
            f'DynTransformerModel '
            f'(input_proj {K}→128, pos_emb max_len={max_len}, '
            f'2×TransformerBlock nhead=4 d_model=128 ff=512, fc_out 128→{N}). '
            f'동적 T ONNX 지원 (수동 self-attention 구현).'
        ),
        'num_cycles': K,
        'num_notes': N,
        'max_len': max_len,
        'onnx_opset': opset,
        'input': {
            'name': 'overlap',
            'shape': ['B', 'T', K],
            'dtype': 'float32',
            'description': 'Overlap row — 이진 또는 연속값. (batch, T, K).',
        },
        'output': {
            'name': 'logits',
            'shape': ['B', 'T', N],
            'dtype': 'float32',
            'description': 'Raw logits. sigmoid(logits) → multi-label 확률.',
        },
        'label_to_note': labels_sorted,
        'threshold': {
            'default': 0.5,
            'adaptive_target_on_ratio': 0.15,
            'min_threshold': 0.1,
            'description': 'adaptive=true 시 전체 확률의 top 15%를 임계값으로.',
        },
        'training': {
            'epochs': len(history),
            'final_train_loss': round(history[-1]['train_loss'], 5) if history else None,
            'final_val_loss': round(history[-1]['val_loss'], 5) if history else None,
            'best_epoch': int(best_epoch) if best_epoch is not None else None,
            'best_val_loss': round(float(best_val_loss), 5) if best_val_loss is not None else None,
            'augmentation': 'circular shift × 4 + noise(p=0.03) × 3',
            'loss': 'BCEWithLogitsLoss',
            'optimizer': 'Adam (lr=1e-3)',
        },
        'optimal_config': OPTIMAL_CONFIG,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[meta] 저장: {out_path}")


# ─── 메인 ──────────────────────────────────────────────────────────────────

def main():
    # cache 등 상대경로를 TDA_ROOT 기준으로 맞춤 (export_hibari_data.py 패턴)
    os.chdir(TDA_ROOT)

    print("=" * 70)
    print("  aqua 대시보드 데이터 Export + Transformer 학습")
    print("  최적 설정: tonnetz 거리 + Transformer (chromatic, 선율)")
    print("=" * 70)

    # ── 1. 전처리 ──────────────────────────────────────────────────────────
    print("\n[1] 전처리")
    data = preprocess(str(MIDI_SRC))
    N = data['N']
    T = data['T']
    notes_label = data['notes_label']
    print(f"  완료: N={N}, T={T}")

    # ── 2. PH + overlap ───────────────────────────────────────────────────
    print("\n[2] Persistent Homology + overlap 계산 (tonnetz)")
    cycle_labeled, binary_ov, cont_act, profile_bd = compute_overlap(data)
    K = binary_ov.shape[1]
    print(f"  K={K}, binary shape={binary_ov.shape}, cont shape={cont_act.shape}")

    # ── 3. data_aqua/ JSON export ───────────────────────────────────────
    print("\n[3] data_aqua/ JSON 저장")
    export_overlap_matrices(T, K, binary_ov, cont_act)
    export_notes_metadata(data)
    export_cycles_metadata(cycle_labeled, profile_bd=profile_bd)
    copy_midi(MIDI_SRC)
    export_manifest(T, K, N)

    # values 길이 검증
    ref_path = DATA_SOL / 'overlap_matrix_reference.json'
    with open(ref_path, 'r', encoding='utf-8') as f:
        _ref = json.load(f)
    assert len(_ref['values']) == T * K, \
        f"values 길이 불일치: {len(_ref['values'])} != {T * K}"
    print(f"  [검증] values 길이 T*K={T*K} — OK")

    # ── 4. Transformer 학습 데이터 구성 ──────────────────────────────────
    print("\n[4] Transformer 학습 데이터 구성")
    X_raw = binary_ov.astype(np.float32)   # (T, K)
    y_raw = build_onehot_y(data, T, N)     # (T, N)
    total_onsets = int(y_raw.sum())
    print(f"  X: {X_raw.shape}, density={X_raw.mean():.4f}")
    print(f"  y: {y_raw.shape}, 총 onset 수={total_onsets}")

    # 증강
    rng = np.random.default_rng(42)
    X_aug, y_aug = augment(X_raw, y_raw, rng=rng)
    print(f"  증강 후: X_aug={X_aug.shape}, y_aug={y_aug.shape}")

    # ── 5. Transformer 학습 ───────────────────────────────────────────────
    print("\n[5] Transformer 학습 (epochs=100, best-checkpoint export)")
    model, history, max_len, best_epoch, best_val_loss = train_transformer(
        X_aug, y_aug, K=K, N=N, T_orig=T,
        d_model=128, nhead=4, num_layers=2, dropout=0.1,
        epochs=100, lr=1e-3, batch_size=32, seed=42,
    )
    print(f"  학습 완료 — best_epoch={best_epoch}, best_val_loss={best_val_loss:.5f}")
    print(f"  (최종 epoch val_loss={history[-1]['val_loss']:.5f} — export 대상은 best checkpoint)")

    # ── 6. ONNX export (best-checkpoint 가중치 이미 load됨) ───────────────
    print("\n[6] ONNX Export (best-checkpoint 가중치)")
    onnx_path = MODELS_DIR / 'transformer_aqua.onnx'
    opset = export_transformer_onnx(model, K=K, N=N, T_orig=T, out_path=onnx_path)

    # ── 7. ONNX 검증 (T=60 및 T=224) ─────────────────────────────────────
    print("\n[7] ONNX 검증 (T=60 더미 입력)")
    err60, out_shape60 = verify_onnx(model, onnx_path, K=K, N=N, T_dummy=60)
    print("\n[7b] ONNX 검증 (T=224 더미 입력)")
    err224, out_shape224 = verify_onnx(model, onnx_path, K=K, N=N, T_dummy=224)
    err = err60  # 대표 오차 (T=60)

    # ── 8. 메타데이터 저장 ────────────────────────────────────────────────
    print("\n[8] 메타데이터 저장")
    meta_path = MODELS_DIR / 'transformer_aqua_meta.json'
    save_transformer_meta(K, N, max_len, notes_label, history, opset, meta_path,
                          best_epoch=best_epoch, best_val_loss=best_val_loss)

    # ── 최종 요약 ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  완료 — 생성된 파일 목록")
    print("=" * 70)
    for p in sorted(DATA_SOL.iterdir()):
        sz = p.stat().st_size
        print(f"  data_aqua/{p.name:45s} {sz/1024:8.1f} KB")
    for p in [onnx_path, meta_path]:
        if p.exists():
            sz = p.stat().st_size
            print(f"  public/models/{p.name:42s} {sz/1024:8.1f} KB")

    print()
    print(f"  N={N}, K={K}, T={T}, max_len={max_len}")
    print(f"  ONNX opset={opset}, torch-ort 최대 오차 T=60:{err60:.2e}  T=224:{err224:.2e}" if err is not None else "  ONNX 검증 생략")
    print(f"  학습 best: epoch={best_epoch}, val_loss={best_val_loss:.5f} (최종 epoch val={history[-1]['val_loss']:.5f})")
    print()
    print("  [다음 단계] UI 곡 전환 배선 정보:")
    print(f"    data_aqua 경로: hibari_dashboard/data_aqua/")
    print(f"    모델 경로: public/models/transformer_aqua.onnx")
    print(f"    메타 경로: public/models/transformer_aqua_meta.json")
    print(f"    T={T}, K={K}, N={N}")
    print(f"    ONNX 입력: 'overlap' [B, T, K], 출력: 'logits' [B, T, N]")
    print("=" * 70)


if __name__ == '__main__':
    main()
