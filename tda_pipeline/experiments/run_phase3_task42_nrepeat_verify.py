"""
Phase 3 Task 42 runner
======================

Goal:
  - Re-verify T39-4/T39-5 with statistical repeats (N=5)
  - Keep existing JSON files intact
  - Write Task42 outputs to new *_n5 / split filenames

Outputs:
  - docs/step3_data/temporal_reorder_fc_dft_gap0_n5.json
  - docs/step3_data/harmony_fc_dft_gap0_n5.json
  - docs/step3_data/harmony_lstm_dft_gap0_n5.json
  - docs/step3_data/temporal_reorder_lstm_dft_gap0_dtwverify.json
  - docs/step3_data/temporal_reorder_lstm_dft_gap0_wave2.json (snapshot/split)
  - docs/step3_data/phase3_task42_nrepeat_verify_summary.json
"""

from __future__ import annotations

import json
import os
import time
import traceback
from collections import Counter
from typing import Any

import numpy as np

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

from config import PipelineConfig
from utils.result_meta import build_result_header

import run_phase3_task39_wave2 as wave2
import run_temporal_reorder_lstm_dft as t39_4_lstm_focus


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
SCRIPT_NAME = os.path.basename(__file__)

METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
POST_BUGFIX = True
N_REPEATS = 5

TEMPORAL_FC_OUT = "temporal_reorder_fc_dft_gap0_n5.json"
HARMONY_FC_OUT = "harmony_fc_dft_gap0_n5.json"
HARMONY_LSTM_OUT = "harmony_lstm_dft_gap0_n5.json"
LSTM_DTWVERIFY_OUT = "temporal_reorder_lstm_dft_gap0_dtwverify.json"
LSTM_WAVE2_OUT = "temporal_reorder_lstm_dft_gap0_wave2.json"
SUMMARY_OUT = "phase3_task42_nrepeat_verify_summary.json"

TARGET_JSONS = [
    "temporal_reorder_fc_dft_gap0.json",
    "temporal_reorder_lstm_dft_gap0.json",
    "harmony_fc_dft_gap0.json",
    "harmony_lstm_dft_gap0.json",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)


def path_in_step3(filename: str) -> str:
    return os.path.join(STEP3_DIR, filename)


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(payload: dict[str, Any], filename: str) -> str:
    ensure_dirs()
    out_path = path_in_step3(filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[saved] {out_path}")
    return out_path


def save_json_abs(payload: dict[str, Any], abs_path: str) -> str:
    ensure_dirs()
    with open(abs_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[saved] {abs_path}")
    return abs_path


def metric_stats(values: list[float], ndigits: int = 6) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"mean": None, "std": None, "values": []}
    return {
        "mean": round(float(arr.mean()), ndigits),
        "std": round(float(arr.std(ddof=1) if arr.size > 1 else 0.0), ndigits),
        "values": [round(float(v), ndigits) for v in arr.tolist()],
    }


def has_mean_std(node: Any) -> bool:
    if isinstance(node, dict):
        if "mean" in node and "std" in node:
            return True
        return any(has_mean_std(v) for v in node.values())
    if isinstance(node, list):
        return any(has_mean_std(v) for v in node)
    return False


def inspect_existing_json(filename: str) -> dict[str, Any]:
    path = path_in_step3(filename)
    info: dict[str, Any] = {
        "file": filename,
        "exists": os.path.exists(path),
        "n_repeats": None,
        "has_mean_std": False,
        "needs_rerun_n5": True,
        "experiments_keys": [],
    }
    if not info["exists"]:
        return info

    data = load_json(path)
    info["n_repeats"] = data.get("n_repeats")
    info["has_mean_std"] = has_mean_std(data)
    exp = data.get("experiments")
    if isinstance(exp, dict):
        info["experiments_keys"] = list(exp.keys())

    n_rep = info["n_repeats"] if isinstance(info["n_repeats"], int) else -1
    info["needs_rerun_n5"] = not (n_rep >= N_REPEATS and info["has_mean_std"])
    return info


def make_task42_header(*, task: str, model: str, overlap_type: str) -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = float(ALPHA)
    cfg.metric.octave_weight = float(OCTAVE_WEIGHT)
    cfg.metric.duration_weight = float(DURATION_WEIGHT)
    cfg.min_onset_gap = int(MIN_ONSET_GAP)
    cfg.post_bugfix = bool(POST_BUGFIX)
    return build_result_header(
        cfg,
        script_name=SCRIPT_NAME,
        n_repeats=N_REPEATS,
        extra={
            "task": task,
            "model": model,
            "overlap_type": overlap_type,
            "purpose": "n_repeat_verification_task42",
        },
    )


def summarize_temporal_condition(
    records: list[dict[str, Any]],
    *,
    reorder_info: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "n_samples": len(records),
        "reorder_info": reorder_info,
        "val_loss": metric_stats([r["val_loss"] for r in records]),
        "n_notes": metric_stats([r["n_notes"] for r in records]),
        "pitch_js": metric_stats([r["pitch_js"] for r in records]),
        "transition_js": metric_stats([r["transition_js"] for r in records]),
        "dtw": metric_stats([r["dtw"] for r in records]),
        "ncd": metric_stats([r["ncd"] for r in records]),
    }
    if errors:
        out["errors"] = errors
    return out


def summarize_harmony_condition(
    records: list[dict[str, Any]],
    *,
    errors: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {"n_samples": len(records)}
    out["val_loss"] = metric_stats([r["val_loss"] for r in records if "val_loss" in r])
    out["n_notes"] = metric_stats([r["n_notes"] for r in records if "n_notes" in r])

    vs_orig_keys = ("pitch_js", "transition_js", "dtw", "ncd")
    vs_ref_keys = ("pitch_js", "transition_js", "dtw", "ncd")
    out["vs_original"] = {
        k: metric_stats([r["vs_original"][k] for r in records if "vs_original" in r])
        for k in vs_orig_keys
    }
    out["vs_ref"] = {
        k: metric_stats([r["vs_ref"][k] for r in records if "vs_ref" in r]) for k in vs_ref_keys
    }

    note_dist_values = [r["note_dist_error"] for r in records if "note_dist_error" in r]
    cycle_dist_values = [r["cycle_dist_error"] for r in records if r.get("cycle_dist_error") is not None]
    npc_values = [r["n_pitch_classes"] for r in records if "n_pitch_classes" in r]

    if note_dist_values:
        out["note_dist_error"] = metric_stats(note_dist_values, ndigits=4)
    if cycle_dist_values:
        out["cycle_dist_error"] = metric_stats(cycle_dist_values, ndigits=4)
    else:
        out["cycle_dist_error"] = {"mean": None, "std": None, "values": []}
    if npc_values:
        out["n_pitch_classes"] = metric_stats(npc_values, ndigits=3)

    pitch_ranges = [tuple(r["pitch_range_used"]) for r in records if "pitch_range_used" in r]
    if pitch_ranges:
        range_counter = Counter(f"{a}-{b}" for (a, b) in pitch_ranges)
        out["pitch_range_counts"] = dict(range_counter)

    best_scales = [str(r["best_scale_match"]) for r in records if "best_scale_match" in r]
    if best_scales:
        out["best_scale_match_counts"] = dict(Counter(best_scales))

    if errors:
        out["errors"] = errors
    return out


def run_t42_4_lstm_split_and_dtwverify(precheck: dict[str, Any]) -> dict[str, Any]:
    print("\n" + "=" * 80)
    print("T42-4 | temporal_reorder_lstm_dft_gap0 overwrite split check")
    print("=" * 80)

    out_info: dict[str, Any] = {
        "wave2_snapshot_written": False,
        "dtwverify_rerun": False,
    }

    temporal_path = path_in_step3("temporal_reorder_lstm_dft_gap0.json")
    wave2_path = path_in_step3(LSTM_WAVE2_OUT)
    dtwverify_path = path_in_step3(LSTM_DTWVERIFY_OUT)

    if not os.path.exists(temporal_path):
        out_info["current_temporal_file"] = "missing"
    else:
        data = load_json(temporal_path)
        exp_keys = list(data.get("experiments", {}).keys()) if isinstance(data.get("experiments"), dict) else []
        is_wave2_layout = any(k.startswith("retrainX_") for k in exp_keys) and any(
            k.startswith("retrainO_") for k in exp_keys
        )
        out_info["current_temporal_is_wave2_layout"] = bool(is_wave2_layout)
        out_info["current_temporal_n_repeats"] = data.get("n_repeats")
        out_info["current_temporal_has_mean_std"] = has_mean_std(data)

        if is_wave2_layout:
            wave2_payload = dict(data)
            wave2_payload["task42_split_note"] = (
                "Copied from temporal_reorder_lstm_dft_gap0.json to preserve Wave2 payload."
            )
            wave2_payload["task42_split_date"] = now_iso()
            save_json_abs(wave2_payload, wave2_path)
            out_info["wave2_snapshot_written"] = True
            out_info["wave2_snapshot_path"] = wave2_path

    dtwverify_check = inspect_existing_json(LSTM_DTWVERIFY_OUT)
    need_dtwverify_rerun = dtwverify_check["needs_rerun_n5"]
    out_info["dtwverify_precheck"] = dtwverify_check

    if need_dtwverify_rerun:
        print("[T42-4] Running Task39-4 focused LSTM N=5 -> dtwverify split output")
        orig_out = t39_4_lstm_focus.OUT_PATH
        orig_summary = t39_4_lstm_focus.SUMMARY_PATH
        try:
            t39_4_lstm_focus.OUT_PATH = dtwverify_path
            t39_4_lstm_focus.SUMMARY_PATH = path_in_step3(
                "phase3_task42_4_lstm_dtwverify_summary.json"
            )
            t39_4_lstm_focus.main()
        finally:
            t39_4_lstm_focus.OUT_PATH = orig_out
            t39_4_lstm_focus.SUMMARY_PATH = orig_summary

        payload = load_json(dtwverify_path)
        payload["purpose"] = "n_repeat_verification_task42"
        payload["task42_split_note"] = "Task39-4 focused LSTM rerun output"
        save_json_abs(payload, dtwverify_path)
        out_info["dtwverify_rerun"] = True
    else:
        print("[T42-4] Existing dtwverify file already has N=5 + std. Skip rerun.")

    out_info["dtwverify_path"] = dtwverify_path
    out_info["dtwverify_postcheck"] = inspect_existing_json(LSTM_DTWVERIFY_OUT)
    return out_info


def run_t42_1_temporal_fc_n5(context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print("T42-1 | Temporal reorder FC N=5")
    print("=" * 80)

    cont_overlap = context["cont_overlap"]
    notes_label = context["notes_label"]
    y_original = context["y_original"]
    original_notes = context["original_notes"]
    total_length = int(context["total_length"])
    n_notes = int(context["n_notes"])
    n_cycles = int(context["n_cycles"])
    variants = wave2.build_reorder_variants(cont_overlap)

    raw: dict[str, list[dict[str, Any]]] = {k: [] for k in variants}
    errors: dict[str, list[str]] = {k: [] for k in variants}

    for rep in range(N_REPEATS):
        seed = 14200 + rep * 101
        print(f"[T42-1] repeat {rep + 1}/{N_REPEATS} seed={seed}")

        model, val_loss = wave2.fit_model(
            model_type="fc",
            x_input=cont_overlap,
            y_target=y_original,
            num_notes=n_notes,
            seq_len=total_length,
            seed=seed,
        )

        for label, item in variants.items():
            ev = wave2.eval_model_vs_original(
                model=model,
                model_type="fc",
                overlap_values=item["overlap"],
                notes_label=notes_label,
                original_notes=original_notes,
                name=f"t42_fc_{label}_rep{rep + 1}",
            )
            if "error" in ev:
                errors[label].append(str(ev["error"]))
                continue
            raw[label].append(
                {
                    "val_loss": float(val_loss),
                    "n_notes": float(ev["n_notes"]),
                    "pitch_js": float(ev["pitch_js"]),
                    "transition_js": float(ev["transition_js"]),
                    "dtw": float(ev["dtw"]),
                    "ncd": float(ev["ncd"]),
                }
            )

    experiments: dict[str, Any] = {}
    for label, rows in raw.items():
        experiments[label] = summarize_temporal_condition(
            rows,
            reorder_info=variants[label]["reorder_info"],
            errors=errors[label],
        )

    payload: dict[str, Any] = {
        **make_task42_header(task="T42-1", model="fc", overlap_type="continuous"),
        "track": "hibari",
        "metric": METRIC,
        "n_cycles": n_cycles,
        "T": total_length,
        "N": n_notes,
        "epochs": int(wave2.DL_EPOCHS),
        "experiments": experiments,
    }
    out_path = save_json(payload, TEMPORAL_FC_OUT)

    baseline = experiments["baseline"]["pitch_js"]["mean"]
    deltas = {}
    for key, value in experiments.items():
        if key == "baseline":
            continue
        mean_v = value["pitch_js"]["mean"]
        if baseline is None or mean_v is None or baseline == 0:
            continue
        deltas[key] = round(100.0 * (mean_v - baseline) / baseline, 4)

    info = {
        "output": out_path,
        "baseline_pitch_js_mean": baseline,
        "pitch_js_delta_pct_vs_baseline": deltas,
        "max_abs_pitch_js_delta_pct": max((abs(v) for v in deltas.values()), default=0.0),
    }
    return out_path, info


def run_harmony_n5(
    context: dict[str, Any],
    *,
    model_type: str,
    out_filename: str,
    task_label: str,
) -> tuple[str, dict[str, Any]]:
    print("\n" + "=" * 80)
    print(f"{task_label} | Harmony constraints {model_type.upper()} N=5")
    print("=" * 80)

    data = context["data"]
    cont_overlap = context["cont_overlap"]
    notes_label = context["notes_label"]
    y_original = context["y_original"]
    original_notes = context["original_notes"]
    total_length = int(context["total_length"])
    n_notes = int(context["n_notes"])
    n_cycles = int(context["n_cycles"])
    cycle_labeled = context["bundle"]["cycle_labeled"]

    conditions = ("original", "baseline", "scale_major", "scale_penta")
    raw: dict[str, list[dict[str, Any]]] = {k: [] for k in conditions}
    errors: dict[str, list[str]] = {k: [] for k in conditions}

    harmony_cfgs = [
        ("baseline", {"harmony_mode": None}),
        ("scale_major", {"harmony_mode": "scale", "scale_type": "major"}),
        ("scale_penta", {"harmony_mode": "scale", "scale_type": "pentatonic"}),
    ]

    offset = 0 if model_type == "fc" else 30000
    for rep in range(N_REPEATS):
        rep_seed = 22200 + offset + rep * 173
        print(f"[{task_label}] repeat {rep + 1}/{N_REPEATS} seed={rep_seed}")

        # original
        model_orig, val_orig = wave2.fit_model(
            model_type=model_type,
            x_input=cont_overlap,
            y_target=y_original,
            num_notes=n_notes,
            seq_len=total_length,
            seed=rep_seed,
        )
        ev_orig = wave2.eval_model_harmony(
            model=model_orig,
            model_type=model_type,
            overlap_values=cont_overlap,
            notes_label=notes_label,
            original_notes=original_notes,
            ref_notes=original_notes,
            name=f"t42_{model_type}_original_rep{rep + 1}",
        )
        if "error" in ev_orig:
            errors["original"].append(str(ev_orig["error"]))
        else:
            raw["original"].append(
                {
                    "val_loss": float(val_orig),
                    "n_notes": float(ev_orig["n_notes"]),
                    "vs_original": dict(ev_orig["vs_original"]),
                    "vs_ref": dict(ev_orig["vs_ref"]),
                }
            )

        # baseline / scale major / pentatonic
        for idx, (name, kwargs) in enumerate(harmony_cfgs):
            pitch_range = (40, 88)
            try:
                reassign = wave2.find_new_notes(
                    notes_label,
                    cycle_labeled,
                    seed=wave2.SEED_BASE,
                    note_metric="tonnetz",
                    pitch_range=pitch_range,
                    n_candidates=1000,
                    **kwargs,
                )
            except RuntimeError as e:
                msg = str(e).lower()
                if "has only" not in msg and "too narrow" not in msg:
                    raise
                pitch_range = (24, 108)
                reassign = wave2.find_new_notes(
                    notes_label,
                    cycle_labeled,
                    seed=wave2.SEED_BASE,
                    note_metric="tonnetz",
                    pitch_range=pitch_range,
                    n_candidates=1000,
                    **kwargs,
                )

            new_notes_label = reassign["new_notes_label"]
            remapped = wave2.remap_music_notes(
                [data["inst1_real"], data["inst2_real"]],
                notes_label,
                new_notes_label,
            )
            remapped_flat = remapped[0] + remapped[1]
            n_new = len(new_notes_label)
            x_new, y_new = wave2.prepare_training_data(
                cont_overlap, remapped, new_notes_label, total_length, n_new
            )

            model_new, val_new = wave2.fit_model(
                model_type=model_type,
                x_input=x_new,
                y_target=y_new,
                num_notes=n_new,
                seq_len=total_length,
                seed=rep_seed + 10 + idx,
            )
            ev = wave2.eval_model_harmony(
                model=model_new,
                model_type=model_type,
                overlap_values=cont_overlap,
                notes_label=new_notes_label,
                original_notes=original_notes,
                ref_notes=remapped_flat,
                name=f"t42_{model_type}_{name}_rep{rep + 1}",
            )
            if "error" in ev:
                errors[name].append(str(ev["error"]))
                continue

            harmony = wave2.analyze_harmony(
                notes_label, cycle_labeled, new_notes_label, reassign["new_notes"]
            )
            cycle_dist_error = reassign.get("cycle_dist_error")
            raw[name].append(
                {
                    "val_loss": float(val_new),
                    "n_notes": float(ev["n_notes"]),
                    "vs_original": dict(ev["vs_original"]),
                    "vs_ref": dict(ev["vs_ref"]),
                    "note_dist_error": float(reassign["note_dist_error"]),
                    "cycle_dist_error": (
                        float(cycle_dist_error) if cycle_dist_error is not None else None
                    ),
                    "pitch_range_used": [int(pitch_range[0]), int(pitch_range[1])],
                    "n_pitch_classes": int(harmony["n_pitch_classes"]),
                    "best_scale_match": harmony["best_scale_name"],
                }
            )

    experiments = {
        key: summarize_harmony_condition(raw[key], errors=errors[key]) for key in conditions
    }

    payload: dict[str, Any] = {
        **make_task42_header(task=task_label, model=model_type, overlap_type="continuous"),
        "track": "hibari",
        "metric": METRIC,
        "n_cycles": n_cycles,
        "T": total_length,
        "N": n_notes,
        "epochs": int(wave2.DL_EPOCHS),
        "experiments": experiments,
    }
    out_path = save_json(payload, out_filename)

    # Quick decision helper for session report: best by vs_original pitch_js mean
    pitch_by_cond: dict[str, float] = {}
    for cond in conditions:
        v = experiments[cond]["vs_original"]["pitch_js"]["mean"]
        if v is not None:
            pitch_by_cond[cond] = float(v)
    best_cond = None
    if pitch_by_cond:
        best_cond = min(pitch_by_cond.items(), key=lambda kv: kv[1])[0]

    info = {
        "output": out_path,
        "best_vs_original_pitch_js_condition": best_cond,
        "vs_original_pitch_js_mean": pitch_by_cond,
    }
    return out_path, info


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
            "n_repeats": N_REPEATS,
        },
        "precheck": {},
        "tasks": {},
        "outputs": {},
    }

    try:
        print("=" * 80)
        print("Task 42 N-repeat verification start")
        print("=" * 80)

        # Phase 1: precheck
        for name in TARGET_JSONS:
            summary["precheck"][name] = inspect_existing_json(name)
        print("[phase1] precheck complete")

        # T42-4: LSTM overwrite split + dtwverify
        t42_4_info = run_t42_4_lstm_split_and_dtwverify(summary["precheck"])
        summary["tasks"]["T42-4"] = t42_4_info
        summary["outputs"]["T42-4_dtwverify"] = t42_4_info.get("dtwverify_path")
        if t42_4_info.get("wave2_snapshot_path"):
            summary["outputs"]["T42-4_wave2_snapshot"] = t42_4_info.get("wave2_snapshot_path")

        need_t42_1 = summary["precheck"]["temporal_reorder_fc_dft_gap0.json"]["needs_rerun_n5"]
        need_t42_2 = summary["precheck"]["harmony_fc_dft_gap0.json"]["needs_rerun_n5"]
        need_t42_3 = summary["precheck"]["harmony_lstm_dft_gap0.json"]["needs_rerun_n5"]

        if need_t42_1 or need_t42_2 or need_t42_3:
            print("[phase3] building hibari context once")
            hibari_context = wave2.build_hibari_context()
            summary["hibari_context"] = {
                "n_cycles": int(hibari_context["n_cycles"]),
                "T": int(hibari_context["total_length"]),
                "N": int(hibari_context["n_notes"]),
                "ph_time_s": float(hibari_context["bundle"]["ph_time_s"]),
            }
        else:
            hibari_context = None

        # T42-1
        if need_t42_1 and hibari_context is not None:
            out_t42_1, info_t42_1 = run_t42_1_temporal_fc_n5(hibari_context)
            summary["tasks"]["T42-1"] = info_t42_1
            summary["outputs"]["T42-1_fc_temporal_n5"] = out_t42_1
        else:
            summary["tasks"]["T42-1"] = {"skipped": True, "reason": "already has N=5 + std"}

        # T42-2
        if need_t42_2 and hibari_context is not None:
            out_t42_2, info_t42_2 = run_harmony_n5(
                hibari_context,
                model_type="fc",
                out_filename=HARMONY_FC_OUT,
                task_label="T42-2",
            )
            summary["tasks"]["T42-2"] = info_t42_2
            summary["outputs"]["T42-2_fc_harmony_n5"] = out_t42_2
        else:
            summary["tasks"]["T42-2"] = {"skipped": True, "reason": "already has N=5 + std"}

        # T42-3
        if need_t42_3 and hibari_context is not None:
            out_t42_3, info_t42_3 = run_harmony_n5(
                hibari_context,
                model_type="lstm",
                out_filename=HARMONY_LSTM_OUT,
                task_label="T42-3",
            )
            summary["tasks"]["T42-3"] = info_t42_3
            summary["outputs"]["T42-3_lstm_harmony_n5"] = out_t42_3
        else:
            summary["tasks"]["T42-3"] = {"skipped": True, "reason": "already has N=5 + std"}

        # Direction check (expected unchanged)
        direction_check: dict[str, Any] = {}
        if "T42-1" in summary["tasks"] and "max_abs_pitch_js_delta_pct" in summary["tasks"]["T42-1"]:
            direction_check["t42_1_fc_temporal_independence_supported"] = (
                summary["tasks"]["T42-1"]["max_abs_pitch_js_delta_pct"] <= 5.0
            )
        if "T42-2" in summary["tasks"] and "best_vs_original_pitch_js_condition" in summary["tasks"]["T42-2"]:
            direction_check["t42_2_fc_harmony_best"] = summary["tasks"]["T42-2"][
                "best_vs_original_pitch_js_condition"
            ]
        if "T42-3" in summary["tasks"] and "best_vs_original_pitch_js_condition" in summary["tasks"]["T42-3"]:
            direction_check["t42_3_lstm_harmony_best"] = summary["tasks"]["T42-3"][
                "best_vs_original_pitch_js_condition"
            ]
        summary["direction_check"] = direction_check

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
        summary["elapsed_s"] = round(float(time.time() - t0), 2)
        out_summary = save_json(summary, SUMMARY_OUT)
        print("=" * 80)
        print(
            f"Task42 done. status={summary['status']}, elapsed={summary['elapsed_s']}s, "
            f"summary={out_summary}"
        )
        print("=" * 80)


if __name__ == "__main__":
    main()

