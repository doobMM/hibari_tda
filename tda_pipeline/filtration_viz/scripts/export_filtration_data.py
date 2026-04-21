"""
export_filtration_data.py — filtration_viz 전용 데이터 export
=================================================================

MIDI 진행에 맞춰 simplex가 나타났다 사라지는 시각화를 위한 정적 데이터를 만든다.

산출물(`filtration_viz/data/`):
  1. distance_hybrid_a025.json  — 23×23 hybrid 거리 행렬 (rate=1.0, α=0.25)
  2. points_2d.json             — 23×(x, y) MDS 2D 좌표 (정규화 [0,1])
  3. notes_active.json          — T×23 binary (note_time_df)
  4. cycles_simplicial.json     — cycles_metadata를 simplex 목록으로 변환
  5. manifest.json              — 경로 + 버전

재사용:
  - hibari_dashboard/data/ 의 notes_metadata / cycles_metadata / original_hibari.mid
    (복사하지 않고 상대경로로 참조만 할 수도 있지만, 자체 완결성을 위해 복사)
"""
import json
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.manifold import MDS

HERE = Path(__file__).resolve().parent
VIZ_ROOT = HERE.parent
DATA_DIR = VIZ_ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

TDA_ROOT = VIZ_ROOT.parent
sys.path.insert(0, str(TDA_ROOT))
sys.path.insert(0, str(TDA_ROOT / 'experiments'))

DASHBOARD_DATA = TDA_ROOT / 'hibari_dashboard' / 'data'

OPTIMAL_CONFIG = {
    'metric': 'dft',
    'alpha': 0.25,
    'w_o': 0.3,
    'w_d': 1.0,
    'use_decayed': True,
    'rate': 1.0,          # 거리 행렬 추출용 대표 rate
}


def build_distance_matrix():
    """현재 최적 설정으로 note-level 23×23 hybrid 거리 행렬 계산."""
    import run_dft_gap0_suite as suite
    from weights import (compute_distance_matrix, compute_inter_weights_decayed,
                         compute_out_of_reach)
    from musical_metrics import compute_hybrid_distance

    suite.MIDI_FILE = str(TDA_ROOT / 'Ryuichi_Sakamoto_-_hibari.mid')
    data = suite.setup_hibari()

    inter = compute_inter_weights_decayed(
        data['adn_i'], max_lag=4, num_chords=data['num_chords']
    )
    oor = compute_out_of_reach(inter, power=-2)
    musical_dist = suite.metric_distance_matrix(
        data['notes_label'],
        metric=OPTIMAL_CONFIG['metric'],
        octave_weight=OPTIMAL_CONFIG['w_o'],
        duration_weight=OPTIMAL_CONFIG['w_d'],
    )

    rate = OPTIMAL_CONFIG['rate']
    timeflow_w = data['intra'] + rate * inter
    freq_dist = compute_distance_matrix(
        timeflow_w, data['notes_dict'], oor, num_notes=data['num_notes']
    ).values
    final_dist = compute_hybrid_distance(
        freq_dist, musical_dist, alpha=OPTIMAL_CONFIG['alpha']
    )
    return data, final_dist.astype(float)


def export_distance(D):
    payload = {
        'N': int(D.shape[0]),
        'values': np.round(D, 5).flatten().tolist(),
        'min': float(D.min()),
        'max': float(D.max()),
        'optimal_config': OPTIMAL_CONFIG,
        'description': (
            'Hybrid DFT (α=0.25, w_o=0.3, w_d=1.0) + decayed lag 1~4, rate=1.0. '
            'Row-major 평탄화. values[i*N + j] = d(note_i, note_j). 23×23 대칭.'
        ),
    }
    out = DATA_DIR / 'distance_hybrid_a025.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[save] {out.name}  ({out.stat().st_size/1024:.1f} KB)')


def export_points(D):
    """MDS로 23점을 2D와 3D에 각각 투영 후 [-1, 1] 정규화 (3D는 [−1,1]³ 중심원점)."""
    def fit(ncomp):
        mds = MDS(
            n_components=ncomp, dissimilarity='precomputed',
            random_state=42, normalized_stress='auto', n_init=6,
        )
        P = mds.fit_transform(D)
        # 중앙화 + [−1, 1] 스케일
        P = P - P.mean(axis=0)
        s = np.max(np.abs(P))
        if s > 0:
            P = P / s
        P = 0.9 * P                                  # 약간의 여백
        return P, float(mds.stress_)

    P2, stress2 = fit(2)
    P3, stress3 = fit(3)

    payload = {
        'N': int(P2.shape[0]),
        'coords_2d': np.round(P2, 5).tolist(),       # [[x, y], ...]
        'coords_3d': np.round(P3, 5).tolist(),       # [[x, y, z], ...]
        'space': '[-1, 1]^D 중심원점',
        'stress_2d': stress2,
        'stress_3d': stress3,
        'description': (
            '23 note MDS 좌표. dissimilarity=hybrid DFT α=0.25 거리. '
            'coords_2d는 2D fallback, coords_3d는 3D 회전 뷰용.'
        ),
    }
    out = DATA_DIR / 'points_2d.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[save] {out.name}  stress 2D={stress2:.3f}, 3D={stress3:.3f}')


def export_notes_active(data):
    ntd: pd.DataFrame = data['note_time_df']     # T × 23
    arr = ntd.values.astype(np.int8)
    T, N = arr.shape
    payload = {
        'T': int(T),
        'N': int(N),
        # 메모리 절약: 각 시점을 23비트 integer로 packing할 수도 있으나
        # 23*1088=25024 바이트 정도라 평탄화로 충분
        'values': arr.flatten().tolist(),
        'description': (
            f'T={T} × N={N} binary. values[t*N + i] = 1 iff note_label(1-indexed i+1) 활성 at 8분음표 tick t.'
        ),
    }
    out = DATA_DIR / 'notes_active.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[save] {out.name}  T={T}, N={N}')
    return T, N


def export_cycles_simplicial():
    """
    hibari_dashboard/data/cycles_metadata.json을 simplex 형태로 재구성.

    각 cycle에서 {vertex 집합} → edges와 triangles을 명시적으로 열거해두면
    렌더러가 바로 그릴 수 있다. (cycle 폴리곤 경로는 PH 결과의
    cycle_key로부터만 정확히 알 수 있으므로 여기서는 vertex 집합만 제공)
    """
    src = DASHBOARD_DATA / 'cycles_metadata.json'
    with open(src, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    cycles_out = []
    for c in meta['cycles']:
        verts = c['vertices_0idx']
        # cycle의 전체 완전 그래프 edge/triangle 열거
        edges = [[verts[i], verts[j]] for i in range(len(verts))
                 for j in range(i + 1, len(verts))]
        cycles_out.append({
            'cycle_idx': c['cycle_idx'],
            'vertices_0idx': verts,
            'note_labels_1idx': c['note_labels_1idx'],
            'size': c['size'],
            'tau': c['tau'],
            'edges': edges,
        })

    payload = {
        'num_cycles': len(cycles_out),
        'source': meta.get('source', ''),
        'cycles': cycles_out,
        'description': (
            'cycle별 구성 정점 + 완전 그래프 edge 목록. '
            '렌더러는 cycle active 시 해당 edge들을 하이라이트.'
        ),
    }
    out = DATA_DIR / 'cycles_simplicial.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'[save] {out.name}  K={len(cycles_out)}')


def copy_auxiliary():
    """notes_metadata / MIDI 를 filtration_viz/data/ 로 복사."""
    for name in ['notes_metadata.json', 'original_hibari.mid']:
        src = DASHBOARD_DATA / name
        dst = DATA_DIR / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f'[copy] {name}  ({dst.stat().st_size/1024:.1f} KB)')
        else:
            print(f'[경고] 원본 없음: {src}')


def export_manifest(T, N):
    payload = {
        'version': '1.0',
        'optimal_config': OPTIMAL_CONFIG,
        'T': T,
        'N': N,
        'files': [
            'distance_hybrid_a025.json',
            'points_2d.json',
            'notes_active.json',
            'cycles_simplicial.json',
            'notes_metadata.json',
            'original_hibari.mid',
        ],
        'midi_total_eighth_notes': T,
        'notes': (
            'MIDI 재생 시간을 T개의 8분음표 구간으로 매핑. '
            '`t = floor(currentSec / (durationSec / T))` 로 현재 tick 계산. '
            'distance_hybrid_a025는 rate=1.0 스냅샷(representative).'
        ),
    }
    out = DATA_DIR / 'manifest.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'[save] {out.name}')


def main():
    import os
    os.chdir(TDA_ROOT)

    print('=' * 70)
    print('  filtration_viz 데이터 export')
    print('=' * 70)

    print('\n[1] distance matrix (hybrid α=0.25, rate=1.0)')
    data, D = build_distance_matrix()
    assert D.shape == (23, 23), f'unexpected shape {D.shape}'
    print(f'    D range [{D.min():.4f}, {D.max():.4f}]')

    print('\n[2] distance JSON export')
    export_distance(D)

    print('\n[3] MDS coordinates (2D + 3D)')
    export_points(D)

    print('\n[4] notes_active (T × 23)')
    T, N = export_notes_active(data)

    print('\n[5] cycles simplicial')
    export_cycles_simplicial()

    print('\n[6] 보조 파일 복사')
    copy_auxiliary()

    print('\n[7] manifest')
    export_manifest(T, N)

    print('\n' + '=' * 70)
    print(f'  완료 → {DATA_DIR}')
    print('=' * 70)


if __name__ == '__main__':
    main()
