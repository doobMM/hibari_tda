"""
export_hibari_data.py — hibari 대시보드용 데이터 export
===========================================================

실험 B 최적 설정(complex α=0.25, ow=0.0, dw=0.3, r_c=0.1 + per-cycle τ_c)으로
다음 산출물을 `hibari_dashboard/data/` 하위로 export 한다:

1. overlap_matrix_reference.json     — 이진 overlap (per-cycle τ 적용)
2. overlap_matrix_continuous.json    — 연속값 activation (soft Algo2 입력)
3. notes_metadata.json               — notes_label 직렬화 + 빈도 분포
4. cycles_metadata.json              — 각 cycle 구성 note + persistence
5. original_midi.mid                 — hibari 원곡 복사

주의:
- 기존 tda_pipeline 모듈은 import만 함. 원본 수정 금지.
- 실험 B의 best_taus(K=40)는 complex_percycle_n20_results.json에서 가져옴.
- PH 계산 시간이 길 수 있음 (complex mode, 16 rate steps).
"""

import os
import sys
import json
import shutil
import pickle
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd

# tda_pipeline 루트 경로를 sys.path에 추가
HERE = Path(__file__).resolve().parent
TDA_ROOT = HERE.parent.parent   # tda_pipeline/
sys.path.insert(0, str(TDA_ROOT))

from pipeline import TDAMusicPipeline
from config import PipelineConfig
from overlap import build_activation_matrix, build_overlap_matrix_percycle
from preprocessing import simul_chord_lists, simul_union_by_dict


# ──────────────────────────────────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────────────────────────────────
DASHBOARD_ROOT = HERE.parent                      # hibari_dashboard/
DATA_DIR = DASHBOARD_ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

N20_RESULTS = TDA_ROOT / 'docs' / 'step3_data' / 'complex_percycle_n20_results.json'
MIDI_SRC = TDA_ROOT / 'Ryuichi_Sakamoto_-_hibari.mid'


# ──────────────────────────────────────────────────────────────────────────
# 실험 B 최적 설정
# ──────────────────────────────────────────────────────────────────────────
EXP_B_CONFIG = {
    'alpha': 0.25,
    'ow': 0.0,
    'dw': 0.3,
    'rc': 0.1,
    'rate_t': 0.3,
}
T_TOTAL = 1088


def load_best_taus():
    """실험 B의 best_taus를 N=20 결과 JSON에서 로드."""
    with open(N20_RESULTS, 'r', encoding='utf-8') as f:
        data = json.load(f)
    exp_B = data['results']['exp_B_extended']
    taus = exp_B['best_taus']
    K = exp_B['K']
    assert len(taus) == K, f"best_taus 길이({len(taus)}) != K({K})"
    return taus, K


def build_note_time_df(pipeline):
    """파이프라인 캐시에서 note-time 행렬 DataFrame 구축. (run_complex_percycle.py와 동일)"""
    adn_i = pipeline._cache['adn_i']
    notes_dict = pipeline._cache['notes_dict']
    notes_label = pipeline._cache['notes_label']

    chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    nodes_list = list(range(1, len(notes_label) + 1))

    ntd = np.zeros((T_TOTAL, len(nodes_list)), dtype=int)
    for t in range(min(T_TOTAL, len(note_sets))):
        if note_sets[t] is not None:
            for n in note_sets[t]:
                if n in nodes_list:
                    ntd[t, nodes_list.index(n)] = 1
    return pd.DataFrame(ntd, columns=nodes_list)


# ──────────────────────────────────────────────────────────────────────────
# Export 스텝
# ──────────────────────────────────────────────────────────────────────────

def export_overlap_matrices(pipeline, best_taus, K_expected):
    """실험 B 설정으로 PH + overlap 재계산 후 JSON export."""
    cfg = pipeline.config

    print("[PH] complex search 시작")
    pipeline.run_homology_search(
        search_type='complex', dimension=1,
        rate_t=EXP_B_CONFIG['rate_t'], rate_s=EXP_B_CONFIG['rc'],
    )
    pipeline.run_overlap_construction(persistence_key='h1_complex_lag1')

    cycle_labeled = pipeline._cache['cycle_labeled']
    K = len(cycle_labeled)
    print(f"[PH] 완료 — K={K} cycles")

    if K != K_expected:
        print(f"[경고] K 불일치: 재계산={K}, 기대(=N=20 실험)={K_expected}")
        # taus 길이 조정
        if K < len(best_taus):
            best_taus = best_taus[:K]
        else:
            best_taus = best_taus + [0.35] * (K - len(best_taus))

    # note-time DF → activation 구성
    note_time_df = build_note_time_df(pipeline)
    cont_act_df = build_activation_matrix(note_time_df, cycle_labeled, continuous=True)
    cont_act = cont_act_df.values.astype(np.float32)
    print(f"[activation] continuous range: [{cont_act.min():.3f}, {cont_act.max():.3f}]")

    # per-cycle τ 이진화
    binary_ov = np.zeros_like(cont_act, dtype=np.int32)
    for ci, tau in enumerate(best_taus):
        binary_ov[:, ci] = (cont_act[:, ci] >= tau).astype(np.int32)

    density = float(binary_ov.sum()) / binary_ov.size
    print(f"[overlap] 이진 density: {density:.4f}")

    # ── 이진 overlap 저장 ─────────────────────────────────────────────────
    # 공간 절약을 위해 값은 1차원 평탄화 + shape만 저장
    ref_payload = {
        'shape': [T_TOTAL, K],
        'T': T_TOTAL,
        'K': K,
        'density': round(density, 6),
        'best_taus': [round(float(t), 3) for t in best_taus],
        'exp_config': EXP_B_CONFIG,
        'description': (
            '실험 B (complex α=0.25 ow=0.0 dw=0.3 r_c=0.1) + greedy per-cycle τ 이진화. '
            'overlap[t*K + c] 로 접근. 1=활성, 0=비활성.'
        ),
        # 1D flatten (row-major): values[t*K + c]
        'values': binary_ov.astype(int).flatten().tolist(),
    }
    out1 = DATA_DIR / 'overlap_matrix_reference.json'
    with open(out1, 'w', encoding='utf-8') as f:
        json.dump(ref_payload, f, ensure_ascii=False)
    print(f"[save] {out1} ({out1.stat().st_size/1024:.1f} KB)")

    # ── 연속값 activation 저장 ────────────────────────────────────────────
    # 소수점 4자리로 반올림하여 용량 절약
    cont_rounded = np.round(cont_act, 4)
    cont_payload = {
        'shape': [T_TOTAL, K],
        'T': T_TOTAL,
        'K': K,
        'min': float(cont_act.min()),
        'max': float(cont_act.max()),
        'mean': float(cont_act.mean()),
        'exp_config': EXP_B_CONFIG,
        'description': (
            '연속 activation (rarity-weighted). soft Algo2 입력용. '
            '값 ∈ [0, 1]. values[t*K + c].'
        ),
        'values': cont_rounded.flatten().tolist(),
    }
    out2 = DATA_DIR / 'overlap_matrix_continuous.json'
    with open(out2, 'w', encoding='utf-8') as f:
        json.dump(cont_payload, f, ensure_ascii=False)
    print(f"[save] {out2} ({out2.stat().st_size/1024:.1f} KB)")

    return cycle_labeled, binary_ov, cont_act


def export_notes_metadata(pipeline):
    """notes_label, notes_counts 등 notes 관련 메타데이터 export."""
    notes_label = pipeline._cache['notes_label']           # {(pitch, dur): label (1-indexed)}
    notes_counts = pipeline._cache['notes_counts']         # Counter over (pitch, dur)

    # label → (pitch, dur) 역매핑
    # notes_label: {(pitch, dur): label(1-indexed)}
    # 저장 형식: label을 key로, pitch/dur/count 정보
    labels = []
    for (pitch, dur), lbl in sorted(notes_label.items(), key=lambda x: x[1]):
        labels.append({
            'label': int(lbl),              # 1-indexed
            'label_idx': int(lbl) - 1,      # 0-indexed (JS용)
            'pitch': int(pitch),            # MIDI pitch
            'dur': int(dur),                # 8분음표 단위
            'count': int(notes_counts.get((pitch, dur), 0)),
            'pc': int(pitch) % 12,          # pitch class
        })

    # 전체 분포 (temperature 스케일링 기초)
    total_count = sum(n['count'] for n in labels)

    payload = {
        'num_notes': len(labels),
        'total_count_per_module': total_count,
        'num_modules_reference': 65,
        'labels': labels,
        'description': (
            '각 note는 (pitch, dur) 튜플 고유. label 은 1-indexed. '
            'JS 포팅 시 label_idx (0-indexed) 사용 권장. '
            'count 는 한 모듈 내 빈도. 전곡 빈도는 count × num_modules_reference.'
        ),
    }

    out = DATA_DIR / 'notes_metadata.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[save] {out} (N={len(labels)})")
    return labels


def export_cycles_metadata(pipeline, cycle_labeled, best_taus):
    """각 cycle의 구성 note + persistence 정보 export."""
    # persistence는 pipeline._cache에 h1_complex_lag1 키로 저장된 dict
    persistence = pipeline._cache.get('h1_complex_lag1', {})

    cycles_info = []
    # cycle_labeled: {label_idx: cycle_key} — label_idx 는 내부 재인덱싱
    for c_idx, cycle_key in cycle_labeled.items():
        # vertex 추출
        if isinstance(cycle_key, frozenset):
            verts = set()
            for simplex in cycle_key:
                if isinstance(simplex, tuple):
                    verts.update(simplex)
                else:
                    verts.add(simplex)
        else:
            verts = set(cycle_key)

        # 0-indexed vertex → 1-indexed note label
        note_labels_1idx = sorted(int(v) + 1 for v in verts)

        # persistence 통계
        p_entries = persistence.get(cycle_key, [])
        # 각 entry: (rate, birth, death)
        lifespans = []
        for (rate, birth, death) in p_entries:
            if isinstance(death, (int, float)) and isinstance(birth, (int, float)):
                lifespans.append({
                    'rate': round(float(rate), 3),
                    'birth': round(float(birth), 6),
                    'death': round(float(death), 6),
                    'length': round(float(death) - float(birth), 6),
                })

        # tau 값
        tau = best_taus[c_idx] if c_idx < len(best_taus) else 0.35

        cycles_info.append({
            'cycle_idx': int(c_idx),
            'vertices_0idx': sorted(int(v) for v in verts),
            'note_labels_1idx': note_labels_1idx,
            'note_labels_0idx': [n - 1 for n in note_labels_1idx],
            'size': len(note_labels_1idx),
            'tau': float(tau),
            'persistence_entries': lifespans,
            'max_persistence': max((x['length'] for x in lifespans), default=0.0),
        })

    payload = {
        'num_cycles': len(cycles_info),
        'source': 'complex PH (α=0.25, ow=0.0, dw=0.3, r_c=0.1, rate_t=0.3)',
        'cycles': cycles_info,
        'description': (
            '각 cycle 은 note 정점들의 순환 구조. '
            'vertices_0idx 는 내부 행렬 접근용, note_labels_1idx 는 notes_metadata 의 label 과 매칭. '
            'tau 는 per-cycle 이진화 임계값.'
        ),
    }

    out = DATA_DIR / 'cycles_metadata.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[save] {out} (K={len(cycles_info)})")


def copy_original_midi():
    if not MIDI_SRC.exists():
        print(f"[경고] 원곡 MIDI 없음: {MIDI_SRC}")
        return
    dst = DATA_DIR / 'original_hibari.mid'
    shutil.copy2(MIDI_SRC, dst)
    print(f"[save] {dst} ({dst.stat().st_size/1024:.1f} KB)")


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────

def main():
    os.chdir(TDA_ROOT)   # pipeline 내부에서 상대경로 참조

    print("=" * 70)
    print("  hibari Dashboard 데이터 Export")
    print("  실험 B 설정: complex α=0.25 ow=0.0 dw=0.3 r_c=0.1 + per-cycle τ")
    print("=" * 70)

    # 1) best_taus 로드
    best_taus, K_expected = load_best_taus()
    print(f"\n[1] best_taus 로드: K={K_expected}")

    # 2) 파이프라인 설정 및 전처리
    cfg = PipelineConfig()
    cfg.midi.auto_detect = True
    cfg.metric.metric = 'tonnetz'
    cfg.metric.alpha = EXP_B_CONFIG['alpha']
    cfg.metric.octave_weight = EXP_B_CONFIG['ow']
    cfg.metric.duration_weight = EXP_B_CONFIG['dw']

    pipeline = TDAMusicPipeline(cfg)
    print("\n[2] 전처리 시작")
    pipeline.run_preprocessing()

    # 3) Overlap 계산 및 export
    print("\n[3] Overlap 재계산 및 export")
    cycle_labeled, bin_ov, cont_act = export_overlap_matrices(
        pipeline, best_taus, K_expected
    )

    # 4) Notes metadata
    print("\n[4] Notes metadata export")
    export_notes_metadata(pipeline)

    # 5) Cycles metadata
    print("\n[5] Cycles metadata export")
    export_cycles_metadata(pipeline, cycle_labeled, best_taus)

    # 6) 원곡 MIDI 복사
    print("\n[6] 원곡 MIDI 복사")
    copy_original_midi()

    # 7) 요약 manifest
    print("\n[7] manifest 저장")
    manifest = {
        'version': '1.0',
        'generated_at': pd.Timestamp.now().isoformat(),
        'exp_config': EXP_B_CONFIG,
        'shape': {'T': T_TOTAL, 'K': len(cycle_labeled)},
        'files': [
            'overlap_matrix_reference.json',
            'overlap_matrix_continuous.json',
            'notes_metadata.json',
            'cycles_metadata.json',
            'original_hibari.mid',
        ],
        'algo1_best_js': 0.0183,
        'algo2_best_js': 0.0003,
    }
    with open(DATA_DIR / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[save] {DATA_DIR / 'manifest.json'}")

    print("\n" + "=" * 70)
    print("  Export 완료")
    print(f"  출력 디렉토리: {DATA_DIR}")
    print("=" * 70)


if __name__ == '__main__':
    main()
