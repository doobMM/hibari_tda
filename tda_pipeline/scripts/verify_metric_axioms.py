"""
verify_metric_axioms.py
=======================
hibari의 23-note 공간에서 4개 거리 함수의 metric axiom을 수치 검증한다.

검증 대상:
1) frequency (adjacency inverse distance)
2) tonnetz
3) voice_leading
4) dft

출력:
- docs/step3_data/metric_axiom_verification.json
- 콘솔 요약 표
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import PipelineConfig
from pipeline import TDAMusicPipeline
from musical_metrics import compute_note_distance_matrix
from weights import compute_distance_matrix, compute_intra_weights, compute_out_of_reach


TOLERANCE = 1e-9
AXIOMS = [
    "nonnegativity",
    "identity_of_indiscernibles",
    "symmetry",
    "triangle_inequality",
]


def _note_as_list(label_to_note: Dict[int, Tuple[int, int]], label: int) -> list[int]:
    pitch, duration = label_to_note[label]
    return [int(pitch), int(duration)]


def _check_nonnegativity(
    dist: np.ndarray,
    label_to_note: Dict[int, Tuple[int, int]],
    tol: float,
) -> Dict[str, Any]:
    violations = np.argwhere(dist < -tol)
    count = int(violations.shape[0])
    if count == 0:
        return {"pass": True, "violations": 0, "worst_example": []}

    worst_idx = np.unravel_index(np.argmin(dist), dist.shape)
    i, j = int(worst_idx[0]), int(worst_idx[1])
    val = float(dist[i, j])
    worst = [
        i + 1,
        j + 1,
        _note_as_list(label_to_note, i + 1),
        _note_as_list(label_to_note, j + 1),
        val,
    ]
    return {"pass": False, "violations": count, "worst_example": worst}


def _check_identity_of_indiscernibles(
    dist: np.ndarray,
    label_to_note: Dict[int, Tuple[int, int]],
    tol: float,
) -> Dict[str, Any]:
    n = dist.shape[0]

    diag = np.diag(dist)
    diag_bad = np.where(np.abs(diag) > tol)[0]
    diag_count = int(diag_bad.size)

    offdiag = dist.copy()
    np.fill_diagonal(offdiag, np.inf)
    off_bad = np.argwhere(offdiag <= tol)
    off_count = int(off_bad.shape[0])

    count = diag_count + off_count
    if count == 0:
        return {"pass": True, "violations": 0, "worst_example": []}

    worst_diag_gap = -np.inf
    worst_diag_idx = -1
    if diag_count:
        bad_vals = np.abs(diag[diag_bad]) - tol
        rel = int(np.argmax(bad_vals))
        worst_diag_idx = int(diag_bad[rel])
        worst_diag_gap = float(bad_vals[rel])

    worst_off_gap = -np.inf
    worst_off_i = -1
    worst_off_j = -1
    if off_count:
        gaps = tol - offdiag[offdiag <= tol]
        rel = int(np.argmax(gaps))
        worst_off_i = int(off_bad[rel, 0])
        worst_off_j = int(off_bad[rel, 1])
        worst_off_gap = float(gaps[rel])

    if worst_diag_gap >= worst_off_gap:
        i = worst_diag_idx
        worst = [
            "diag_nonzero",
            i + 1,
            _note_as_list(label_to_note, i + 1),
            float(dist[i, i]),
        ]
    else:
        i, j = worst_off_i, worst_off_j
        worst = [
            "offdiag_nonpositive",
            i + 1,
            j + 1,
            _note_as_list(label_to_note, i + 1),
            _note_as_list(label_to_note, j + 1),
            float(dist[i, j]),
        ]

    return {"pass": False, "violations": count, "worst_example": worst}


def _check_symmetry(
    dist: np.ndarray,
    label_to_note: Dict[int, Tuple[int, int]],
    tol: float,
) -> Dict[str, Any]:
    n = dist.shape[0]
    diff = np.abs(dist - dist.T)
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    bad = np.argwhere((diff > tol) & mask)
    count = int(bad.shape[0])
    if count == 0:
        return {"pass": True, "violations": 0, "worst_example": []}

    upper_diff = np.where(mask, diff, -np.inf)
    i, j = np.unravel_index(np.argmax(upper_diff), upper_diff.shape)
    i, j = int(i), int(j)
    worst = [
        i + 1,
        j + 1,
        _note_as_list(label_to_note, i + 1),
        _note_as_list(label_to_note, j + 1),
        float(dist[i, j]),
        float(dist[j, i]),
        float(diff[i, j]),
    ]
    return {"pass": False, "violations": count, "worst_example": worst}


def _check_triangle_inequality(
    dist: np.ndarray,
    label_to_note: Dict[int, Tuple[int, int]],
    tol: float,
) -> Dict[str, Any]:
    n = dist.shape[0]
    count = 0
    worst_excess = -np.inf
    worst_i = -1
    worst_j = -1
    worst_k = -1

    for j in range(n):
        rhs = dist[:, [j]] + dist[[j], :]  # (i, k): d(i,j) + d(j,k)
        excess = dist - rhs                # (i, k): d(i,k) - (d(i,j)+d(j,k))
        bad = excess > tol
        bad_count = int(np.count_nonzero(bad))
        if bad_count:
            count += bad_count
            i, k = np.unravel_index(np.argmax(excess), excess.shape)
            cur = float(excess[i, k])
            if cur > worst_excess:
                worst_excess = cur
                worst_i = int(i)
                worst_j = int(j)
                worst_k = int(k)

    if count == 0:
        return {"pass": True, "violations": 0, "worst_example": []}

    lhs = float(dist[worst_i, worst_k])
    d_ij = float(dist[worst_i, worst_j])
    d_jk = float(dist[worst_j, worst_k])
    rhs = float(d_ij + d_jk)
    worst = [
        worst_i + 1,
        worst_j + 1,
        worst_k + 1,
        _note_as_list(label_to_note, worst_i + 1),
        _note_as_list(label_to_note, worst_j + 1),
        _note_as_list(label_to_note, worst_k + 1),
        lhs,
        rhs,
        float(lhs - rhs),
    ]
    return {"pass": False, "violations": int(count), "worst_example": worst}


def verify_metric_axioms(
    dist: np.ndarray,
    label_to_note: Dict[int, Tuple[int, int]],
    tol: float = TOLERANCE,
) -> Dict[str, Dict[str, Any]]:
    return {
        "nonnegativity": _check_nonnegativity(dist, label_to_note, tol),
        "identity_of_indiscernibles": _check_identity_of_indiscernibles(
            dist, label_to_note, tol
        ),
        "symmetry": _check_symmetry(dist, label_to_note, tol),
        "triangle_inequality": _check_triangle_inequality(dist, label_to_note, tol),
    }


def build_hibari_distance_matrices() -> Tuple[Dict[str, np.ndarray], Dict[int, Tuple[int, int]], PipelineConfig]:
    cfg = PipelineConfig()
    cfg.midi.file_name = "Ryuichi_Sakamoto_-_hibari.mid"

    pipeline = TDAMusicPipeline(cfg).run_preprocessing()
    cache = pipeline._cache

    notes_label: Dict[Tuple[int, int], int] = cache["notes_label"]
    notes_dict = cache["notes_dict"]
    adn_i = cache["adn_i"]

    # frequency distance: §2.4 정의의 1-step adjacency 기반 (양 악기 intra 전이 합)
    w1 = compute_intra_weights(adn_i[1][0], num_chords=cfg.midi.num_chords)
    w2 = compute_intra_weights(adn_i[2][0], num_chords=cfg.midi.num_chords)
    intra = w1 + w2
    oor = compute_out_of_reach(intra, power=cfg.homology.power)
    freq_matrix = compute_distance_matrix(
        intra,
        notes_dict,
        out_of_reach=oor,
        num_notes=cfg.midi.num_notes,
    ).values.astype(float)

    # musical metrics: §2.4 + 코드 기본 설정(config.py)
    tonnetz_matrix = compute_note_distance_matrix(
        notes_label,
        metric="tonnetz",
        octave_weight=cfg.metric.octave_weight,
        duration_weight=cfg.metric.duration_weight,
    )
    voice_leading_matrix = compute_note_distance_matrix(
        notes_label,
        metric="voice_leading",
        duration_weight=cfg.metric.duration_weight,
    )
    dft_matrix = compute_note_distance_matrix(
        notes_label,
        metric="dft",
        octave_weight=cfg.metric.octave_weight,
        duration_weight=cfg.metric.duration_weight,
    )

    label_to_note = {label: note for note, label in notes_label.items()}
    matrices = {
        "frequency": freq_matrix,
        "tonnetz": tonnetz_matrix.astype(float),
        "voice_leading": voice_leading_matrix.astype(float),
        "dft": dft_matrix.astype(float),
    }
    return matrices, label_to_note, cfg


def print_summary_table(results: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
    def cell(metric_name: str, axiom_name: str) -> str:
        r = results[metric_name][axiom_name]
        status = "PASS" if r["pass"] else "FAIL"
        return f"{status} ({r['violations']})"

    metrics = ["frequency", "tonnetz", "voice_leading", "dft"]

    print("\n=== Metric Axiom Verification (hibari, N=23, tol=1e-9) ===")
    print(
        f"{'metric':<15} {'nonnegativity':<18} {'identity':<18} "
        f"{'symmetry':<18} {'triangle':<18}"
    )
    print("-" * 90)
    for m in metrics:
        print(
            f"{m:<15} "
            f"{cell(m, 'nonnegativity'):<18} "
            f"{cell(m, 'identity_of_indiscernibles'):<18} "
            f"{cell(m, 'symmetry'):<18} "
            f"{cell(m, 'triangle_inequality'):<18}"
        )

    print("\n--- Worst Violation Samples (failed axioms only) ---")
    any_fail = False
    for m in metrics:
        for ax in AXIOMS:
            r = results[m][ax]
            if not r["pass"]:
                any_fail = True
                print(f"[{m} | {ax}] violations={r['violations']}")
                print(f"  worst_example={r['worst_example']}")
    if not any_fail:
        print("모든 metric/axiom이 통과했습니다.")


def main() -> None:
    matrices, label_to_note, _ = build_hibari_distance_matrices()

    results: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for metric_name, matrix in matrices.items():
        results[metric_name] = verify_metric_axioms(
            matrix, label_to_note, tol=TOLERANCE
        )

    out_path = PROJECT_ROOT / "docs" / "step3_data" / "metric_axiom_verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print_summary_table(results)
    print(f"\nSaved JSON: {out_path}")


if __name__ == "__main__":
    main()

