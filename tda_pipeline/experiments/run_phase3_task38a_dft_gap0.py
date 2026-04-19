"""
Phase 3 Task 38a runner
=======================

Runs T38a-1 ~ T38a-6 in a single Python session with:
  - metric='dft'
  - alpha=0.25
  - octave_weight=0.3
  - duration_weight=1.0
  - min_onset_gap=0
  - post_bugfix=True

Outputs:
  - docs/step3_data/step71_prototype_om_dft_gap0.json
  - docs/step3_data/step71_prototype_comparison_dft_gap0.json
  - docs/step3_data/step71_module_results_dft_gap0.json
  - docs/step3_data/step71_improvements_dft_gap0.json
  - docs/step3_data/section77_experiments_dft_gap0.json
  - docs/step3_data/step_barcode_dft_gap0.json
  - docs/step3_data/phase3_task38a_dft_gap0_summary.json
"""

from __future__ import annotations

import json
import os
import pickle
import random
import time
import traceback
from typing import Any

import numpy as np
import pandas as pd
from persim import wasserstein as pers_wasserstein

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from config import PipelineConfig
from eval_metrics import evaluate_generation
from generation import CycleSetManager, NodePool, algorithm1_optimized
from musical_metrics import compute_hybrid_distance, compute_note_distance_matrix
from overlap import (
    build_activation_matrix,
    group_rBD_by_homology,
    label_cycles_from_persistence,
)
from preprocessing import build_chord_labels, chord_to_note_labels, group_notes_with_duration
from topology import generate_barcode_numpy
from utils.result_meta import build_result_header
from weights import (
    compute_distance_matrix,
    compute_inter_weights,
    compute_intra_weights,
    compute_out_of_reach,
)

import run_dft_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
SCRIPT_NAME = os.path.basename(__file__)

METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
POST_BUGFIX = True

REFERENCE_FULL_SONG_BASELINE_JS = 0.0213

MODULE_LEN = 32
N_INST1_COPIES = 33
N_INST2_COPIES = 32
INST2_INIT_OFFSET = 33
MODULE_HEIGHTS = [
    4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3,
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


def save_json(payload: dict[str, Any], filename: str) -> str:
    ensure_dirs()
    out_path = os.path.join(STEP3_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[saved] {out_path}")
    return out_path


def make_header(n_repeats: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = float(ALPHA)
    cfg.metric.octave_weight = float(OCTAVE_WEIGHT)
    cfg.metric.duration_weight = float(DURATION_WEIGHT)
    cfg.min_onset_gap = int(MIN_ONSET_GAP)
    cfg.post_bugfix = bool(POST_BUGFIX)
    return build_result_header(cfg, script_name=SCRIPT_NAME, n_repeats=n_repeats, extra=extra)


def to_np(mat: Any) -> np.ndarray:
    if hasattr(mat, "values"):
        return np.asarray(mat.values, dtype=np.float32)
    return np.asarray(mat, dtype=np.float32)


def setup_data() -> dict[str, Any]:
    data = suite.setup_hibari()
    _, chord_seq1 = build_chord_labels(group_notes_with_duration(data["inst1_real"]))
    _, chord_seq2 = build_chord_labels(group_notes_with_duration(data["inst2_real"]))
    data["chord_seq1"] = chord_seq1
    data["chord_seq2"] = chord_seq2
    return data


def check_primary_cache() -> dict[str, Any]:
    path = os.path.join(CACHE_DIR, "metric_dft.pkl")
    out: dict[str, Any] = {"path": path, "exists": os.path.exists(path)}
    if not out["exists"]:
        return out
    with open(path, "rb") as f:
        cached = pickle.load(f)
    out["alpha"] = float(cached.get("alpha", np.nan))
    out["K"] = int(len(cached.get("cycle_labeled", {})))
    out["overlap_shape"] = list(getattr(cached.get("overlap"), "shape", []))
    return out


def load_or_build_alpha_bundle(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cache_name = "metric_dft_alpha0p25_ow0p3_dw1p0.pkl"
    cache_path = os.path.join(CACHE_DIR, cache_name)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            bundle = pickle.load(f)
        return bundle, {"used_cache": True, "cache_path": cache_path}

    print("[info] alpha=0.25 overlap cache not found. Building PH bundle now...")
    t0 = time.time()
    fresh = suite.build_overlap_bundle(
        data,
        METRIC,
        alpha=ALPHA,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=0.35,
    )
    bundle = {
        "metric": fresh["metric"],
        "alpha": float(fresh["alpha"]),
        "octave_weight": float(fresh["octave_weight"]),
        "duration_weight": float(fresh["duration_weight"]),
        "cycle_labeled": fresh["cycle_labeled"],
        "overlap_binary": fresh["overlap_binary"],
        "activation_continuous": fresh["activation_continuous"],
        "ph_time_s": float(fresh["ph_time_s"]),
    }
    with open(cache_path, "wb") as f:
        pickle.dump(bundle, f)
    elapsed = time.time() - t0
    return bundle, {"used_cache": False, "cache_path": cache_path, "build_elapsed_s": round(elapsed, 2)}


def reshape_inst1_modules(overlap_full: np.ndarray) -> np.ndarray:
    needed = N_INST1_COPIES * MODULE_LEN
    if overlap_full.shape[0] < needed:
        raise ValueError(f"overlap rows ({overlap_full.shape[0]}) < required ({needed})")
    return overlap_full[:needed].reshape(N_INST1_COPIES, MODULE_LEN, overlap_full.shape[1])


def proto_p0_first_module_copy(usable: np.ndarray) -> np.ndarray:
    return usable[0].astype(np.float32)


def proto_p1_union_of_active(usable: np.ndarray) -> np.ndarray:
    return usable.max(axis=0).astype(np.float32)


def proto_p2_exclusive_to_module(usable: np.ndarray) -> np.ndarray:
    counts = usable.sum(axis=0)
    return (counts == 1).astype(np.float32)


def proto_p3_module_specific(usable: np.ndarray) -> tuple[np.ndarray, int, list[int]]:
    counts = usable.sum(axis=(1, 2))
    sorted_idx = np.argsort(counts)
    median_idx = int(sorted_idx[len(sorted_idx) // 2])
    return usable[median_idx].astype(np.float32), median_idx, [int(x) for x in counts]


def replicate_inst1(module_notes: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for m in range(N_INST1_COPIES):
        off = m * MODULE_LEN
        for s, p, e in module_notes:
            ns = s + off
            ne = min(e + off, off + MODULE_LEN)
            if ns < off + MODULE_LEN and ne > ns:
                out.append((ns, p, ne))
    return out


def replicate_inst2(module_notes: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    period = MODULE_LEN + 1
    for m in range(N_INST2_COPIES):
        start = INST2_INIT_OFFSET + m * period
        for s, p, e in module_notes:
            ns = s + start
            ne = min(e + start, start + MODULE_LEN)
            if ns < start + MODULE_LEN and ne > ns:
                out.append((ns, p, ne))
    return out


def module_coverage(module_notes: list[tuple[int, int, int]], notes_label: dict[tuple[int, int], int]) -> int:
    used = set()
    for s, p, e in module_notes:
        key = (p, e - s)
        if key in notes_label:
            used.add(notes_label[key])
    return len(used)


def run_algo1_module(
    data: dict[str, Any],
    overlap_proto: np.ndarray,
    cycle_labeled: dict[Any, Any],
    seed: int,
) -> list[tuple[int, int, int]]:
    random.seed(seed)
    np.random.seed(seed)
    pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
    manager = CycleSetManager(cycle_labeled)
    return algorithm1_optimized(
        pool,
        list(MODULE_HEIGHTS),
        overlap_proto,
        manager,
        max_resample=50,
        verbose=False,
        min_onset_gap=MIN_ONSET_GAP,
    )


def eval_full(
    data: dict[str, Any],
    module_notes: list[tuple[int, int, int]],
    keep_gen: bool = False,
) -> dict[str, Any]:
    all_gen = replicate_inst1(module_notes) + replicate_inst2(module_notes)
    metrics = evaluate_generation(
        all_gen,
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"],
        name="",
    )
    out: dict[str, Any] = {
        "js": float(metrics["js_divergence"]),
        "coverage": float(metrics["note_coverage"]),
        "n_notes": int(len(all_gen)),
        "mod_n_notes": int(len(module_notes)),
    }
    if keep_gen:
        out["all_gen"] = all_gen
    return out


def run_proto_trials(
    data: dict[str, Any],
    overlap_proto: np.ndarray,
    cycle_labeled: dict[Any, Any],
    n_repeats: int,
    seed_base: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    worst: dict[str, Any] | None = None
    for i in range(n_repeats):
        seed = seed_base + i
        mod = run_algo1_module(data, overlap_proto, cycle_labeled, seed=seed)
        ev = eval_full(data, mod, keep_gen=False)
        ev["seed"] = seed
        ev["module_coverage"] = int(module_coverage(mod, data["notes_label"]))
        trials.append(ev)
        if best is None or ev["js"] < best["js"]:
            best = dict(ev)
        if worst is None or ev["js"] > worst["js"]:
            worst = dict(ev)

    js_vals = np.array([t["js"] for t in trials], dtype=float)
    cov_vals = np.array([t["coverage"] for t in trials], dtype=float)
    summary = {
        "js_mean": float(js_vals.mean()),
        "js_std": float(js_vals.std(ddof=1) if len(js_vals) > 1 else 0.0),
        "js_min": float(js_vals.min()),
        "js_max": float(js_vals.max()),
        "cov_mean": float(cov_vals.mean()),
        "module_cov_mean": float(np.mean([t["module_coverage"] for t in trials])),
    }
    return trials, summary, best or {}, worst or {}


def gen_with_best_of_k(
    data: dict[str, Any],
    overlap_proto: np.ndarray,
    cycle_labeled: dict[Any, Any],
    base_seed: int,
    k: int,
) -> tuple[list[tuple[int, int, int]], int, int]:
    candidates: list[tuple[int, int, list[tuple[int, int, int]]]] = []
    for j in range(k):
        mod = run_algo1_module(data, overlap_proto, cycle_labeled, seed=base_seed * 1000 + j)
        cov = module_coverage(mod, data["notes_label"])
        candidates.append((cov, j, mod))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    best_cov, best_j, best_mod = candidates[0]
    return best_mod, int(best_cov), int(best_j)


def gen_with_cov_constraint(
    data: dict[str, Any],
    overlap_proto: np.ndarray,
    cycle_labeled: dict[Any, Any],
    base_seed: int,
    target: int = 20,
    max_attempts: int = 30,
) -> tuple[list[tuple[int, int, int]], int, int]:
    best_mod: list[tuple[int, int, int]] | None = None
    best_cov = -1
    for j in range(max_attempts):
        mod = run_algo1_module(data, overlap_proto, cycle_labeled, seed=base_seed * 1000 + j)
        cov = module_coverage(mod, data["notes_label"])
        if cov > best_cov:
            best_cov = cov
            best_mod = mod
        if cov >= target:
            return mod, int(cov), int(j + 1)
    if best_mod is None:
        return [], int(best_cov), int(max_attempts)
    return best_mod, int(best_cov), int(max_attempts)


def compute_module_local_ph(
    data: dict[str, Any],
    start_module: int,
    rates: tuple[float, ...] = (0.0, 0.5, 1.0),
) -> tuple[dict[Any, Any] | None, np.ndarray | None, int]:
    notes_label = data["notes_label"]
    notes_dict = data["notes_dict"]
    inst1 = data["inst1_real"]
    inst2 = data["inst2_real"]
    num_chords = data["num_chords"]
    n_notes = len(notes_label)

    # 2026-04-19 Task 56 Option B: 두 악기 동일 물리 시각 창 [32(m+1), 32(m+2))
    # 이유: 기존 t2_lo = t1_lo + 33은 index lag=1을 physical 34-step lag로 왜곡.
    # Option B는 seq_a/seq_b 동기(같은 물리 t 참조) → inter lag=1 = physical 1.
    window_lo = (start_module + 1) * MODULE_LEN
    window_hi = window_lo + MODULE_LEN
    if window_hi > data["T"]:
        return None, None, 0

    t1_lo = window_lo
    t1_hi = window_hi
    t2_lo = window_lo
    t2_hi = window_hi

    cs1 = data["chord_seq1"][window_lo:window_hi]
    cs2 = data["chord_seq2"][window_lo:window_hi]

    if sum(1 for c in cs1 if c is not None) < 2 or sum(1 for c in cs2 if c is not None) < 2:
        return None, None, 0

    w1 = compute_intra_weights(cs1, num_chords=num_chords)
    w2 = compute_intra_weights(cs2, num_chords=num_chords)
    intra = w1 + w2

    L = min(len(cs1), len(cs2))
    if L > 1:
        inter = compute_inter_weights(cs1[:L], cs2[:L], num_chords=num_chords, lag=1)
    else:
        inter = pd.DataFrame(np.zeros((num_chords, num_chords), dtype=float))

    if np.count_nonzero(inter.values) == 0:
        oor = 1e6
    else:
        oor = compute_out_of_reach(inter, power=-2)

    m_dist = compute_note_distance_matrix(
        notes_label,
        metric=METRIC,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
    )

    profile: list[tuple[float, Any]] = []
    for r in rates:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=n_notes).values
        final_dist = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final_dist,
            listOfDimension=[1],
            exactStep=True,
            birthDeathSimplex=False,
            sortDimension=False,
        )
        profile.append((float(r), bd))

    persistence = group_rBD_by_homology(profile, dim=1)
    cycle_local = label_cycles_from_persistence(persistence)
    n_cycles = len(cycle_local)
    if n_cycles == 0:
        return None, None, 0

    nodes_list = list(range(1, n_notes + 1))
    ntd = np.zeros((MODULE_LEN, n_notes), dtype=int)
    # Option B: 두 악기 동일 창이므로 window_lo 기준으로 일괄 변환
    inst1_mod = [(s, p, e) for (s, p, e) in inst1 if window_lo <= s < window_hi]
    inst2_mod = [(s, p, e) for (s, p, e) in inst2 if window_lo <= s < window_hi]
    for s, p, e in inst1_mod + inst2_mod:
        d = e - s
        key = (p, d)
        if key not in notes_label:
            continue
        lbl = notes_label[key]
        t_start = s - window_lo
        t_end = min(t_start + d, MODULE_LEN)
        for t in range(max(0, t_start), max(0, t_end)):
            if 0 <= t < MODULE_LEN:
                ntd[t, lbl - 1] = 1

    note_time_df = pd.DataFrame(ntd, columns=nodes_list)
    activation = build_activation_matrix(note_time_df, cycle_local, continuous=False)
    overlap_proto = to_np(activation).astype(np.float32)
    return cycle_local, overlap_proto, n_cycles


def dgm_from_bd(bd: list[Any]) -> np.ndarray:
    pairs: list[list[float]] = []
    for item in bd:
        bd_pair = item[1]
        if len(bd_pair) != 2:
            continue
        b, d = bd_pair
        if d == float("inf"):
            continue
        pairs.append([float(b), float(d)])
    if not pairs:
        return np.empty((0, 2), dtype=float)
    return np.asarray(pairs, dtype=float)


def safe_wasserstein(d1: np.ndarray, d2: np.ndarray) -> float:
    if len(d1) == 0 and len(d2) == 0:
        return 0.0
    return float(pers_wasserstein(d1, d2))


def compute_reference_diagrams(data: dict[str, Any], rates: tuple[float, ...]) -> dict[float, np.ndarray]:
    notes_label = data["notes_label"]
    notes_dict = data["notes_dict"]
    chord_seq1 = data["chord_seq1"]
    n_notes = len(notes_label)
    num_chords = data["num_chords"]
    cs1 = chord_seq1[:MODULE_LEN]

    intra = compute_intra_weights(cs1, num_chords=num_chords)
    inter = pd.DataFrame(np.zeros((num_chords, num_chords), dtype=float))
    if np.count_nonzero(intra.values) == 0:
        return {r: np.empty((0, 2), dtype=float) for r in rates}
    oor = compute_out_of_reach(intra, power=-2)

    m_dist = compute_note_distance_matrix(
        notes_label,
        metric=METRIC,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
    )

    diagrams: dict[float, np.ndarray] = {}
    for r in rates:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=n_notes).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final,
            listOfDimension=[1],
            exactStep=True,
            birthDeathSimplex=False,
            sortDimension=False,
        )
        diagrams[r] = dgm_from_bd(bd)
    return diagrams


def eval_barcode_module(
    module_notes: list[tuple[int, int, int]],
    notes_label: dict[tuple[int, int], int],
    ref_diagrams: dict[float, np.ndarray],
    rates: tuple[float, ...],
) -> dict[str, Any]:
    if not module_notes:
        w_by_rate = {float(r): safe_wasserstein(np.empty((0, 2), dtype=float), ref_diagrams[r]) for r in rates}
        return {
            "w_total": float(sum(w_by_rate.values())),
            "w_by_rate": w_by_rate,
            "n_cycles": 0,
            "n_chords": 0,
        }

    active = group_notes_with_duration(module_notes)
    chord_map, chord_seq = build_chord_labels(active)
    notes_dict_gen = chord_to_note_labels(chord_map, notes_label)
    notes_dict_gen["name"] = "notes"
    num_chords = max(1, len(chord_map))
    n_notes = len(notes_label)

    intra = compute_intra_weights(chord_seq, num_chords=num_chords)
    inter = pd.DataFrame(np.zeros((num_chords, num_chords), dtype=float))
    if np.count_nonzero(intra.values) == 0:
        w_by_rate = {float(r): safe_wasserstein(np.empty((0, 2), dtype=float), ref_diagrams[r]) for r in rates}
        return {
            "w_total": float(sum(w_by_rate.values())),
            "w_by_rate": w_by_rate,
            "n_cycles": 0,
            "n_chords": num_chords,
        }

    oor = compute_out_of_reach(intra, power=-2)
    m_dist = compute_note_distance_matrix(
        notes_label,
        metric=METRIC,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
    )

    w_by_rate: dict[float, float] = {}
    n_cycles_max = 0
    for r in rates:
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict_gen, oor, num_notes=n_notes).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=ALPHA)
        bd = generate_barcode_numpy(
            mat=final,
            listOfDimension=[1],
            exactStep=True,
            birthDeathSimplex=False,
            sortDimension=False,
        )
        dgm = dgm_from_bd(bd)
        n_cycles_max = max(n_cycles_max, len(dgm))
        w_by_rate[float(r)] = safe_wasserstein(dgm, ref_diagrams[r])

    return {
        "w_total": float(sum(w_by_rate.values())),
        "w_by_rate": w_by_rate,
        "n_cycles": int(n_cycles_max),
        "n_chords": int(num_chords),
    }


def task_1(
    bundle: dict[str, Any],
    cache_meta: dict[str, Any],
    primary_cache_meta: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    overlap_full = to_np(bundle["overlap_binary"])
    cont_full = to_np(bundle["activation_continuous"])
    cycle_labeled = bundle["cycle_labeled"]
    K = int(len(cycle_labeled))

    usable = reshape_inst1_modules(overlap_full)
    p0 = proto_p0_first_module_copy(usable)
    p1 = proto_p1_union_of_active(usable)
    p2 = proto_p2_exclusive_to_module(usable)
    p3, median_idx, counts = proto_p3_module_specific(usable)

    result = {
        **make_header(
            n_repeats=0,
            extra={
                "task": "T38a-1",
                "K": K,
                "cycle_count": K,
                "cache_used": bool(cache_meta.get("used_cache", False)),
            },
        ),
        "K": K,
        "cycle_count": K,
        "overlap_shape_binary": list(overlap_full.shape),
        "overlap_shape_continuous": list(cont_full.shape),
        "prototype_shape": list(p0.shape),
        "prototype_density": {
            "P0_first_module_copy": float((p0 > 0).mean()),
            "P1_union_of_active": float((p1 > 0).mean()),
            "P2_exclusive_to_module": float((p2 > 0).mean()),
            "P3_module_specific": float((p3 > 0).mean()),
        },
        "module_specific_meta": {
            "chosen_module_index": int(median_idx),
            "module_active_counts": counts,
        },
        "cache_meta": {
            "primary_metric_dft_cache": primary_cache_meta,
            "alpha025_cache": cache_meta,
        },
        "ph_time_s": float(bundle.get("ph_time_s", -1)),
    }
    out = save_json(result, "step71_prototype_om_dft_gap0.json")

    artifacts = {
        "cycle_labeled": cycle_labeled,
        "overlap_full": overlap_full,
        "cont_full": cont_full,
        "usable": usable,
        "prototypes": {
            "P0_first_module_copy": p0,
            "P1_union_of_active": p1,
            "P2_exclusive_to_module": p2,
            "P3_module_specific": p3,
        },
        "K": K,
    }
    print(f"[T38a-1] K={K}")
    return out, artifacts


def task_2(data: dict[str, Any], artifacts: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n_repeats = 10
    seed_base = 7200
    cycle_labeled = artifacts["cycle_labeled"]

    old_comp_path = os.path.join(STEP3_DIR, "step71_prototype_comparison.json")
    old_comp: dict[str, Any] = {}
    if os.path.exists(old_comp_path):
        with open(old_comp_path, "r", encoding="utf-8") as f:
            old_comp = json.load(f)

    old_map = {
        "P1_union_of_active": "P0 — OR over 33",
        "P3_module_specific": "P3 — median module",
    }

    strategies = [
        ("P0_first_module_copy", artifacts["prototypes"]["P0_first_module_copy"]),
        ("P1_union_of_active", artifacts["prototypes"]["P1_union_of_active"]),
        ("P2_exclusive_to_module", artifacts["prototypes"]["P2_exclusive_to_module"]),
        ("P3_module_specific", artifacts["prototypes"]["P3_module_specific"]),
    ]

    results: dict[str, Any] = {}
    best_name = None
    best_mean = float("inf")
    for idx, (name, proto) in enumerate(strategies):
        trials, summary, best_trial, worst_trial = run_proto_trials(
            data,
            proto,
            cycle_labeled,
            n_repeats=n_repeats,
            seed_base=seed_base + idx * 100,
        )
        mean_js = float(summary["js_mean"])
        ratio = float(mean_js / REFERENCE_FULL_SONG_BASELINE_JS)

        tonnetz_ref = None
        tonnetz_delta_pct = None
        mapped = old_map.get(name)
        if mapped and mapped in old_comp and isinstance(old_comp[mapped], dict):
            tonnetz_ref = float(old_comp[mapped].get("js_mean"))
            if tonnetz_ref and tonnetz_ref > 0:
                tonnetz_delta_pct = float(100.0 * (mean_js - tonnetz_ref) / tonnetz_ref)

        results[name] = {
            "density": float((proto > 0).mean()),
            "js_mean": mean_js,
            "js_std": float(summary["js_std"]),
            "js_min": float(summary["js_min"]),
            "js_max": float(summary["js_max"]),
            "cov_mean": float(summary["cov_mean"]),
            "module_cov_mean": float(summary["module_cov_mean"]),
            "ratio_vs_full_song_baseline_0_0213": ratio,
            "tonnetz_reference_js_mean": tonnetz_ref,
            "delta_pct_vs_tonnetz_reference": tonnetz_delta_pct,
            "best_trial": best_trial,
            "worst_trial": worst_trial,
            "trials": trials,
        }
        if mean_js < best_mean:
            best_mean = mean_js
            best_name = name
        print(f"[T38a-2] {name}: JS={mean_js:.4f} ± {summary['js_std']:.4f}")

    payload = {
        **make_header(
            n_repeats=n_repeats,
            extra={
                "task": "T38a-2",
                "K": int(artifacts["K"]),
                "cycle_count": int(artifacts["K"]),
            },
        ),
        "K": int(artifacts["K"]),
        "cycle_count": int(artifacts["K"]),
        "reference_full_song_baseline_js": REFERENCE_FULL_SONG_BASELINE_JS,
        "best_strategy_by_mean_js": best_name,
        "results": results,
    }
    out = save_json(payload, "step71_prototype_comparison_dft_gap0.json")
    return out, {"best_strategy": best_name, "best_mean_js": best_mean}


def task_3(data: dict[str, Any], artifacts: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n_repeats = 20
    cycle_labeled = artifacts["cycle_labeled"]
    proto = artifacts["prototypes"]["P0_first_module_copy"]
    trials, summary, best_trial, worst_trial = run_proto_trials(
        data,
        proto,
        cycle_labeled,
        n_repeats=n_repeats,
        seed_base=7100,
    )

    payload = {
        **make_header(
            n_repeats=n_repeats,
            extra={
                "task": "T38a-3",
                "prototype_strategy": "P0_first_module_copy",
                "K": int(artifacts["K"]),
                "cycle_count": int(artifacts["K"]),
            },
        ),
        "summary": {
            "n_repeats": n_repeats,
            "js_divergence": {
                "mean": float(summary["js_mean"]),
                "std": float(summary["js_std"]),
                "min": float(summary["js_min"]),
                "max": float(summary["js_max"]),
            },
            "coverage_mean": float(summary["cov_mean"]),
            "best_seed": int(best_trial["seed"]),
            "best_js": float(best_trial["js"]),
            "worst_seed": int(worst_trial["seed"]),
            "worst_js": float(worst_trial["js"]),
            "ratio_vs_full_song_baseline_0_0213": float(summary["js_mean"] / REFERENCE_FULL_SONG_BASELINE_JS),
        },
        "best_trial": best_trial,
        "worst_trial": worst_trial,
        "trials": trials,
    }
    out = save_json(payload, "step71_module_results_dft_gap0.json")
    print(
        "[T38a-3] "
        f"JS={summary['js_mean']:.4f} ± {summary['js_std']:.4f}, "
        f"best={best_trial['js']:.4f} (seed={best_trial['seed']})"
    )
    return out, {
        "mean_js": float(summary["js_mean"]),
        "std_js": float(summary["js_std"]),
        "best_js": float(best_trial["js"]),
        "best_seed": int(best_trial["seed"]),
    }


def run_strategy_with_seeds(
    name: str,
    seeds: list[int],
    generator_fn,
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for seed in seeds:
        generated = generator_fn(seed)
        ev = generated["eval"]
        trial = {
            "seed": int(seed),
            "js": float(ev["js"]),
            "coverage": float(ev["coverage"]),
            "n_notes": int(ev["n_notes"]),
            "mod_n_notes": int(ev["mod_n_notes"]),
            "module_coverage": int(generated["module_coverage"]),
            "meta": generated.get("meta", {}),
        }
        trials.append(trial)
        if best is None or trial["js"] < best["js"]:
            best = dict(trial)

    js = np.array([t["js"] for t in trials], dtype=float)
    cov = np.array([t["coverage"] for t in trials], dtype=float)
    summary = {
        "js_mean": float(js.mean()),
        "js_std": float(js.std(ddof=1) if len(js) > 1 else 0.0),
        "js_min": float(js.min()),
        "js_max": float(js.max()),
        "coverage_mean": float(cov.mean()),
        "module_cov_mean": float(np.mean([t["module_coverage"] for t in trials])),
        "best_trial": best,
        "trials": trials,
    }
    print(f"[T38a-4] {name}: JS={summary['js_mean']:.4f} ± {summary['js_std']:.4f}")
    return summary


def task_4(data: dict[str, Any], artifacts: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n_repeats = 10
    seeds = list(range(7300, 7300 + n_repeats))
    cycle_labeled = artifacts["cycle_labeled"]
    p0 = artifacts["prototypes"]["P0_first_module_copy"]

    cycle_local, p3_proto, p3_cycles = compute_module_local_ph(data, start_module=0)
    if cycle_local is None or p3_proto is None:
        raise RuntimeError("P3 module-local PH is empty at start_module=0; cannot run T38a-4")

    def gen_c(seed: int) -> dict[str, Any]:
        mod, cov, best_j = gen_with_best_of_k(data, p0, cycle_labeled, base_seed=seed, k=10)
        ev = eval_full(data, mod, keep_gen=False)
        return {"module_notes": mod, "module_coverage": cov, "eval": ev, "meta": {"best_j": best_j}}

    def gen_d(seed: int) -> dict[str, Any]:
        mod, cov, attempts = gen_with_cov_constraint(data, p0, cycle_labeled, base_seed=seed, target=20, max_attempts=30)
        ev = eval_full(data, mod, keep_gen=False)
        return {"module_notes": mod, "module_coverage": cov, "eval": ev, "meta": {"attempts": attempts}}

    def gen_p3(seed: int) -> dict[str, Any]:
        mod = run_algo1_module(data, p3_proto, cycle_local, seed=seed)
        cov = module_coverage(mod, data["notes_label"])
        ev = eval_full(data, mod, keep_gen=False)
        return {
            "module_notes": mod,
            "module_coverage": cov,
            "eval": ev,
            "meta": {"start_module": 0, "local_cycles": int(p3_cycles)},
        }

    def gen_p3c(seed: int) -> dict[str, Any]:
        mod, cov, best_j = gen_with_best_of_k(data, p3_proto, cycle_local, base_seed=seed, k=10)
        ev = eval_full(data, mod, keep_gen=False)
        return {
            "module_notes": mod,
            "module_coverage": cov,
            "eval": ev,
            "meta": {"best_j": best_j, "start_module": 0, "local_cycles": int(p3_cycles)},
        }

    results = {
        "C_best_of_10": run_strategy_with_seeds("C_best_of_10", seeds, gen_c),
        "D_cov_ge_20": run_strategy_with_seeds("D_cov_ge_20", seeds, gen_d),
        "P3_module_local": run_strategy_with_seeds("P3_module_local", seeds, gen_p3),
        "P3_plus_C_best_of_10": run_strategy_with_seeds("P3_plus_C_best_of_10", seeds, gen_p3c),
    }

    payload = {
        **make_header(
            n_repeats=n_repeats,
            extra={
                "task": "T38a-4",
                "K": int(artifacts["K"]),
                "cycle_count": int(artifacts["K"]),
            },
        ),
        "reference_full_song_baseline_js": REFERENCE_FULL_SONG_BASELINE_JS,
        "P3_meta": {
            "start_module": 0,
            "local_cycle_count": int(p3_cycles),
            "prototype_density": float((p3_proto > 0).mean()),
        },
        "results": results,
    }
    out = save_json(payload, "step71_improvements_dft_gap0.json")

    best_name = min(results.keys(), key=lambda k: results[k]["js_mean"])
    return out, {
        "best_strategy": best_name,
        "best_mean_js": float(results[best_name]["js_mean"]),
        "p3_cycle_count": int(p3_cycles),
        "p3_proto": p3_proto,
        "cycle_local": cycle_local,
    }


def task_5(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n_repeats = 10
    k_best = 10
    base_seeds = list(range(9300, 9300 + n_repeats))

    # 2026-04-19 Task 56 Option B: 두 악기 동일 창 [32(m+1), 32(m+2)) 정책.
    # T=1088, MODULE_LEN=32 → window_hi = 32(m+2) ≤ T → m ≤ 32.
    # 단 m=32일 때 창 [1056, 1088)은 inst1 없이 inst2만 → PH 불안정 → 제외.
    # m ∈ [0, 31] (32개) 사용. start_module=m 창은 inst1 module (m+1) 구간.
    start_modules = list(range(32))

    results: dict[str, Any] = {}
    best_global = {"js": float("inf"), "info": None}

    for sm in start_modules:
        cycle_local, proto, n_cyc = compute_module_local_ph(data, start_module=sm)
        if cycle_local is None or proto is None:
            continue

        js_vals: list[float] = []
        cov_vals: list[float] = []
        best_local = {"js": float("inf"), "seed": None, "module_coverage": None, "n_notes": None}
        for seed in base_seeds:
            mod, mod_cov, best_j = gen_with_best_of_k(data, proto, cycle_local, base_seed=seed, k=k_best)
            ev = eval_full(data, mod, keep_gen=False)
            js_vals.append(float(ev["js"]))
            cov_vals.append(float(ev["coverage"]))

            if ev["js"] < best_local["js"]:
                best_local = {
                    "js": float(ev["js"]),
                    "seed": int(seed),
                    "module_coverage": int(mod_cov),
                    "n_notes": int(ev["n_notes"]),
                    "best_j": int(best_j),
                }
            if ev["js"] < best_global["js"]:
                best_global = {
                    "js": float(ev["js"]),
                    "info": {
                        "start_module": int(sm),
                        "seed": int(seed),
                        "module_coverage": int(mod_cov),
                        "coverage": float(ev["coverage"]),
                        "n_notes": int(ev["n_notes"]),
                        "module_count": 65,
                        "used_note_count": int(mod_cov),
                        "best_j": int(best_j),
                    },
                }

        if not js_vals:
            continue
        js_arr = np.asarray(js_vals, dtype=float)
        cov_arr = np.asarray(cov_vals, dtype=float)
        results[f"start_{sm:02d}"] = {
            "start_module": int(sm),
            "n_cycles": int(n_cyc),
            "prototype_density": float((proto > 0).mean()),
            "js_mean": float(js_arr.mean()),
            "js_std": float(js_arr.std(ddof=1) if len(js_arr) > 1 else 0.0),
            "js_min": float(js_arr.min()),
            "js_max": float(js_arr.max()),
            "coverage_mean": float(cov_arr.mean()),
            "best_local_trial": best_local,
        }
        print(
            "[T38a-5] "
            f"start={sm:02d}, cycles={n_cyc:02d}, "
            f"JS={js_arr.mean():.4f} ± {js_arr.std(ddof=1) if len(js_arr) > 1 else 0.0:.4f}"
        )

    means = {k: v["js_mean"] for k, v in results.items()}
    first_key = "start_00"
    first_advantage = None
    first_rank = None
    if first_key in means and means:
        sorted_keys = sorted(means.keys(), key=lambda x: means[x])
        first_rank = int(sorted_keys.index(first_key) + 1)
        first_advantage = bool(first_rank == 1)

    payload = {
        **make_header(
            n_repeats=n_repeats,
            extra={
                "task": "T38a-5",
                "k_best": k_best,
                "start_module_basis": 32,
            },
        ),
        "study_scope": {
            "start_module_basis": 32,
            "reason": "Task 56 Option B: window [32(m+1), 32(m+2)), m in [0, 31] (32 modules; m=32 excluded — inst1 missing)",
            "start_modules": start_modules,
            "k_best": k_best,
            "n_repeats_per_start_module": n_repeats,
        },
        "best_temperature": 3.0,
        "results": results,
        "first_module_advantage": {
            "start_module_0_is_best_by_mean": first_advantage,
            "start_module_0_rank_by_mean_js": first_rank,
        },
        "best_global_trial": {
            "js": float(best_global["js"]),
            "info": best_global["info"],
        },
    }
    out = save_json(payload, "section77_experiments_dft_gap0.json")
    return out, {
        "best_global_js": float(best_global["js"]),
        "best_global_info": best_global["info"],
        "first_module_advantage": first_advantage,
        "first_module_rank": first_rank,
    }


def task_6(data: dict[str, Any], p3_artifacts: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n_repeats = 10
    k_best = 10
    seeds = list(range(9400, 9400 + n_repeats))
    rates = (0.0, 0.5, 1.0)

    cycle_local = p3_artifacts["cycle_local"]
    p3_proto = p3_artifacts["p3_proto"]
    if cycle_local is None or p3_proto is None:
        cycle_local, p3_proto, _ = compute_module_local_ph(data, start_module=0)
    if cycle_local is None or p3_proto is None:
        raise RuntimeError("Cannot run T38a-6 without P3 local cycle/prototype")

    ref_diagrams = compute_reference_diagrams(data, rates=rates)
    ref_sizes = {str(r): int(len(ref_diagrams[r])) for r in rates}

    rows: list[dict[str, Any]] = []
    best_trial = {"w_total": float("inf"), "seed": None}
    for seed in seeds:
        candidates: list[tuple[float, int, list[tuple[int, int, int]], dict[str, Any]]] = []
        for j in range(k_best):
            mod = run_algo1_module(data, p3_proto, cycle_local, seed=seed * 1000 + j)
            wb = eval_barcode_module(mod, data["notes_label"], ref_diagrams, rates=rates)
            candidates.append((wb["w_total"], j, mod, wb))
        candidates.sort(key=lambda x: x[0])
        best_w, best_j, best_mod, wb = candidates[0]
        ev = eval_full(data, best_mod, keep_gen=False)

        row = {
            "seed": int(seed),
            "best_j": int(best_j),
            "w_total": float(best_w),
            "w_by_rate": {str(k): float(v) for k, v in wb["w_by_rate"].items()},
            "js": float(ev["js"]),
            "coverage": float(ev["coverage"]),
            "n_notes": int(ev["n_notes"]),
            "module_coverage": int(module_coverage(best_mod, data["notes_label"])),
            "n_cycles": int(wb["n_cycles"]),
            "n_chords": int(wb["n_chords"]),
        }
        rows.append(row)
        if best_w < best_trial["w_total"]:
            best_trial = dict(row)

    w_arr = np.array([r["w_total"] for r in rows], dtype=float)
    js_arr = np.array([r["js"] for r in rows], dtype=float)
    if len(rows) > 1 and np.std(w_arr) > 0 and np.std(js_arr) > 0:
        corr = float(np.corrcoef(w_arr, js_arr)[0, 1])
    else:
        corr = 0.0

    payload = {
        **make_header(
            n_repeats=n_repeats,
            extra={
                "task": "T38a-6",
                "start_module": 0,
                "rates": list(rates),
                "k_best": k_best,
            },
        ),
        "description": "DFT alpha=0.25 Wasserstein barcode vs JS correlation",
        "ref_diagrams_size": ref_sizes,
        "results": rows,
        "summary": {
            "w_mean": float(w_arr.mean()),
            "w_std": float(w_arr.std(ddof=1) if len(w_arr) > 1 else 0.0),
            "w_min": float(w_arr.min()),
            "js_mean": float(js_arr.mean()),
            "js_std": float(js_arr.std(ddof=1) if len(js_arr) > 1 else 0.0),
            "js_min": float(js_arr.min()),
            "pearson_w_js": corr,
        },
        "best_trial": best_trial,
        "cautions_unchanged": [
            "Wasserstein and JS optimize different targets",
            "module-level barcode does not capture full-song instrument interaction",
            "chord support mismatch can distort distance interpretation",
            "rate-grid sensitivity remains",
        ],
    }
    out = save_json(payload, "step_barcode_dft_gap0.json")
    print(f"[T38a-6] Pearson(W, JS)={corr:.4f}")
    return out, {
        "pearson_w_js": corr,
        "w_mean": float(w_arr.mean()),
        "js_mean": float(js_arr.mean()),
    }


def main() -> None:
    ensure_dirs()
    t0 = time.time()
    summary: dict[str, Any] = {
        "script": SCRIPT_NAME,
        "date_start": now_iso(),
        "same_python_session": True,
        "status": "running",
        "config": {
            "metric": METRIC,
            "alpha": ALPHA,
            "octave_weight": OCTAVE_WEIGHT,
            "duration_weight": DURATION_WEIGHT,
            "min_onset_gap": MIN_ONSET_GAP,
            "post_bugfix": POST_BUGFIX,
        },
        "tasks": {},
        "outputs": {},
    }

    try:
        print("=" * 80)
        print("Task 38a Phase 3 start: DFT alpha=0.25")
        print("=" * 80)

        primary_cache_meta = check_primary_cache()
        summary["cache_check_metric_dft"] = primary_cache_meta

        data = setup_data()
        summary["setup"] = {
            "num_notes": int(len(data["notes_label"])),
            "num_chords": int(data["num_chords"]),
            "total_length": int(data["T"]),
        }

        bundle, cache_meta = load_or_build_alpha_bundle(data)
        summary["alpha025_bundle_cache"] = cache_meta

        path1, artifacts = task_1(bundle, cache_meta, primary_cache_meta)
        summary["outputs"]["T38a-1"] = path1
        summary["tasks"]["T38a-1"] = {"K": int(artifacts["K"])}

        path2, r2 = task_2(data, artifacts)
        summary["outputs"]["T38a-2"] = path2
        summary["tasks"]["T38a-2"] = r2

        path3, r3 = task_3(data, artifacts)
        summary["outputs"]["T38a-3"] = path3
        summary["tasks"]["T38a-3"] = r3

        path4, r4 = task_4(data, artifacts)
        summary["outputs"]["T38a-4"] = path4
        summary["tasks"]["T38a-4"] = {
            "best_strategy": r4["best_strategy"],
            "best_mean_js": r4["best_mean_js"],
            "p3_cycle_count": r4["p3_cycle_count"],
        }

        path5, r5 = task_5(data)
        summary["outputs"]["T38a-5"] = path5
        summary["tasks"]["T38a-5"] = r5

        path6, r6 = task_6(data, r4)
        summary["outputs"]["T38a-6"] = path6
        summary["tasks"]["T38a-6"] = r6

        summary["status"] = "completed"
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        print("[ERROR]", exc)
        print(traceback.format_exc())
    finally:
        summary["date_end"] = now_iso()
        summary["elapsed_s"] = round(time.time() - t0, 2)
        out_summary = save_json(summary, "phase3_task38a_dft_gap0_summary.json")
        print("=" * 80)
        print(f"Task 38a done. status={summary['status']}, elapsed={summary['elapsed_s']}s")
        print(f"summary: {out_summary}")
        print("=" * 80)


if __name__ == "__main__":
    main()
