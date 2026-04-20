"""
export_hibari_data.py — hibari 대시보드용 데이터 export
===========================================================

현재 최적 설정(DFT hybrid α=0.25, w_o=0.3, w_d=1.0, timeflow + decayed lag 1~4,
per-cycle τ_c, K=14)으로 다음 산출물을 `hibari_dashboard/data/` 하위로 export 한다:

1. overlap_matrix_reference.json     — 이진 overlap (per-cycle τ 적용)
2. overlap_matrix_continuous.json    — 연속값 activation (soft Algo2 입력)
3. notes_metadata.json               — notes_label 직렬화 + 빈도 분포
4. cycles_metadata.json              — 각 cycle 구성 note + persistence
5. original_midi.mid                 — hibari 원곡 복사

주의:
- 기존 tda_pipeline 모듈은 import만 함. 원본 수정 금지.
- best_taus(K=14)는 percycle_tau_dft_gap0_alpha_grid_results.json에서
  results[alpha=0.25].tau_profile을 사용 (Algo1 JS=0.00902±0.00170, N=20).
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

# tda_pipeline 루트 + experiments/ 경로를 sys.path에 추가
HERE = Path(__file__).resolve().parent
TDA_ROOT = HERE.parent.parent   # tda_pipeline/
sys.path.insert(0, str(TDA_ROOT))
sys.path.insert(0, str(TDA_ROOT / 'experiments'))

# 실제 JSON(percycle_tau_dft_gap0_alpha_grid_results.json)을 만든 코드 경로와
# 동일하게 K=14 cycles를 복원하기 위해 `run_dft_gap0_suite`의 빌드 함수를 재사용.
import run_dft_gap0_suite as suite  # experiments/run_dft_gap0_suite.py

# suite.MIDI_FILE은 __file__ 기준으로 experiments/ 하위를 가리키므로 실제 MIDI 위치로 교체.
suite.MIDI_FILE = str(TDA_ROOT / 'Ryuichi_Sakamoto_-_hibari.mid')


# ──────────────────────────────────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────────────────────────────────
DASHBOARD_ROOT = HERE.parent                      # hibari_dashboard/
DATA_DIR = DASHBOARD_ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

TAUS_RESULTS = TDA_ROOT / 'docs' / 'step3_data' / 'percycle_tau_dft_gap0_alpha_grid_results.json'
MIDI_SRC = TDA_ROOT / 'Ryuichi_Sakamoto_-_hibari.mid'


# ──────────────────────────────────────────────────────────────────────────
# 현재 최적 설정 (DFT α=0.25 + per-cycle τ, K=14)
# ──────────────────────────────────────────────────────────────────────────
OPTIMAL_CONFIG = {
    'metric': 'dft',
    'alpha': 0.25,
    'w_o': 0.3,            # Tonnetz/DFT note 거리의 옥타브 항 가중치
    'w_d': 1.0,            # Tonnetz/DFT note 거리의 duration 항 가중치
    'search_type': 'timeflow',
    'lag_mode': 'decayed_1_to_4',
    'max_lag': 4,
    'min_onset_gap': 0,
    'temperature': 3.0,
}
T_TOTAL = 1088


def load_best_taus():
    """α=0.25 결과에서 per-cycle best tau_profile 로드 (K=14)."""
    with open(TAUS_RESULTS, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = data['results']
    r025 = next((r for r in results if abs(float(r['alpha']) - 0.25) < 1e-9), None)
    if r025 is None:
        raise RuntimeError(f"alpha=0.25 결과가 {TAUS_RESULTS} 에 없음")
    taus = list(r025['tau_profile'])
    K = int(r025['K'])
    assert len(taus) == K, f"tau_profile 길이({len(taus)}) != K({K})"
    return taus, K


# ──────────────────────────────────────────────────────────────────────────
# Export 스텝
# ──────────────────────────────────────────────────────────────────────────

def export_overlap_matrices(data, bundle, best_taus, K_expected):
    """suite.build_overlap_bundle 결과에 per-cycle τ 적용 후 JSON export."""
    cycle_labeled = bundle['cycle_labeled']
    K = len(cycle_labeled)
    print(f"[PH] 완료 — K={K} cycles (ph_time={bundle['ph_time_s']}s)")

    if K != K_expected:
        print(f"[경고] K 불일치: 재계산={K}, 기대(=α=0.25 α-grid)={K_expected}")
        if K < len(best_taus):
            best_taus = best_taus[:K]
        else:
            best_taus = best_taus + [0.35] * (K - len(best_taus))

    # suite는 이미 continuous activation을 번들에 담아둠
    cont_act = bundle['activation_continuous'].values.astype(np.float32)
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
        'optimal_config': OPTIMAL_CONFIG,
        'description': (
            '현재 최적 (DFT α=0.25 w_o=0.3 w_d=1.0 timeflow + decayed lag 1~4) '
            '+ greedy per-cycle τ 이진화 (K=14). '
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
        'optimal_config': OPTIMAL_CONFIG,
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


def export_notes_metadata(data):
    """notes_label, notes_counts 등 notes 관련 메타데이터 export."""
    notes_label = data['notes_label']           # {(pitch, dur): label (1-indexed)}
    notes_counts = data['notes_counts']         # Counter over (pitch, dur)

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


def export_cycles_metadata(cycle_labeled, best_taus):
    """각 cycle의 구성 note + persistence 정보 export.

    suite.build_overlap_bundle은 persistence를 번들에 노출하지 않아
    persistence_entries는 빈 리스트로 둔다 (대시보드 UI가 참고만 하며 없어도 동작).
    """
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

        # tau 값
        tau = best_taus[c_idx] if c_idx < len(best_taus) else 0.35

        cycles_info.append({
            'cycle_idx': int(c_idx),
            'vertices_0idx': sorted(int(v) for v in verts),
            'note_labels_1idx': note_labels_1idx,
            'note_labels_0idx': [n - 1 for n in note_labels_1idx],
            'size': len(note_labels_1idx),
            'tau': float(tau),
            'persistence_entries': [],
            'max_persistence': 0.0,
        })

    payload = {
        'num_cycles': len(cycles_info),
        'source': 'DFT timeflow PH (α=0.25, w_o=0.3, w_d=1.0) + decayed lag 1~4, K=14',
        'cycles': cycles_info,
        'description': (
            '각 cycle 은 note 정점들의 순환 구조. '
            'vertices_0idx 는 내부 행렬 접근용, note_labels_1idx 는 notes_metadata 의 label 과 매칭. '
            'tau 는 per-cycle 이진화 임계값 (greedy search, α=0.25 기준).'
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
    os.chdir(TDA_ROOT)   # suite 내부 상대경로(cache 등)가 TDA_ROOT 기준

    print("=" * 70)
    print("  hibari Dashboard 데이터 Export")
    print("  현재 최적: DFT α=0.25 w_o=0.3 w_d=1.0 + decayed lag 1~4 + per-cycle τ (K=14)")
    print("=" * 70)

    # 1) best_taus 로드
    best_taus, K_expected = load_best_taus()
    print(f"\n[1] best_taus 로드: K={K_expected} (source={TAUS_RESULTS.name})")

    # 2) hibari 전용 전처리 (JSON 생성 스크립트와 동일 경로)
    print("\n[2] suite.setup_hibari 전처리")
    data = suite.setup_hibari()

    # 3) build_overlap_bundle — DFT α=0.25 w_o=0.3 w_d=1.0 decayed lag
    print("\n[3] suite.build_overlap_bundle 실행")
    bundle = suite.build_overlap_bundle(
        data,
        metric=OPTIMAL_CONFIG['metric'],
        alpha=OPTIMAL_CONFIG['alpha'],
        octave_weight=OPTIMAL_CONFIG['w_o'],
        duration_weight=OPTIMAL_CONFIG['w_d'],
        use_decayed=True,
        threshold=0.35,
    )
    cycle_labeled, bin_ov, cont_act = export_overlap_matrices(
        data, bundle, best_taus, K_expected
    )

    # 4) Notes metadata
    print("\n[4] Notes metadata export")
    export_notes_metadata(data)

    # 5) Cycles metadata
    print("\n[5] Cycles metadata export")
    export_cycles_metadata(cycle_labeled, best_taus)

    # 6) 원곡 MIDI 복사
    print("\n[6] 원곡 MIDI 복사")
    copy_original_midi()

    # 7) 요약 manifest
    print("\n[7] manifest 저장")
    manifest = {
        'version': '2.0',
        'generated_at': pd.Timestamp.now().isoformat(),
        'optimal_config': OPTIMAL_CONFIG,
        'shape': {'T': T_TOTAL, 'K': len(cycle_labeled)},
        'files': [
            'overlap_matrix_reference.json',
            'overlap_matrix_continuous.json',
            'notes_metadata.json',
            'cycles_metadata.json',
            'original_hibari.mid',
        ],
        'algo1_best_js': 0.00902,
        'algo1_best_js_std': 0.00170,
        'algo2_best_js': 0.00035,
        'algo2_best_js_std': 0.00015,
        'source_json': TAUS_RESULTS.name,
        'notes': (
            'Algo1 기록은 α=0.25 per-cycle τ DFT (gap=0, N=20). '
            'Algo2 기록은 α=0.5 FC-cont (continuous 입력) N=10 기준 — '
            '대시보드 FC 모델은 binary 입력으로 학습되므로 이 수치는 참고값.'
        ),
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
