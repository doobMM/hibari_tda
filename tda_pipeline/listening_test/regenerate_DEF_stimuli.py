"""
Task 45-B: regenerate D/E/F listening stimuli.

생성 대상
- D: Tonnetz + Transformer + major_block32 (scale_major, continuous)
- E: DFT + Transformer + major_block32 (scale_major, continuous)
- F: DFT + FC + major_block32 (scale_major, continuous)

출력
- output/listening_test/stimulus_D_tonnetz_transformer.(mid|wav)
- output/listening_test/stimulus_E_dft_transformer.(mid|wav)
- output/listening_test/stimulus_F_dft_fc.(mid|wav)
- output/listening_test/def_regen_metadata.json
- listening_test/stimuli_overrides.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from sklearn.model_selection import train_test_split

try:
    import torch
except Exception:
    torch = None

BASE_DIR = Path(__file__).resolve().parent.parent
for _p in (BASE_DIR, BASE_DIR / "tools", BASE_DIR / "experiments"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from generation import (
    MusicGeneratorFC,
    MusicGeneratorTransformer,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from gen_final_wavs import render_midi_to_wav_stereo, write_pretty_midi
from note_reassign import find_new_notes
from run_note_reassign_unified import analyze_harmony, remap_music_notes
from sequence_metrics import evaluate_sequence_metrics
from temporal_reorder import reorder_overlap_matrix
from wav_renderer import render_midi_to_wav

import run_dft_gap0_suite as suite


LISTENING_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output" / "listening_test"
METADATA_PATH = OUT_DIR / "def_regen_metadata.json"
OVERRIDES_PATH = LISTENING_DIR / "stimuli_overrides.json"
DEFAULT_TEMPO_BPM = 66


@dataclass(frozen=True)
class Condition:
    code: str
    metric: str
    alpha: float
    octave_weight: float
    duration_weight: float
    model_type: str
    stem: str
    reference_vs_ref_pjs: float
    trial_seeds: tuple[int, ...]
    note_metric: str
    note_variant: str = "scale_major"


CONDITIONS: tuple[Condition, ...] = (
    Condition(
        code="D",
        metric="tonnetz",
        alpha=0.5,
        octave_weight=0.3,
        duration_weight=1.0,
        model_type="transformer",
        stem="stimulus_D_tonnetz_transformer",
        reference_vs_ref_pjs=0.003446,
        trial_seeds=(7401, 7402, 7403),
        note_metric="tonnetz",
    ),
    Condition(
        code="E",
        metric="dft",
        alpha=0.25,
        octave_weight=0.3,
        duration_weight=1.0,
        model_type="transformer",
        stem="stimulus_E_dft_transformer",
        reference_vs_ref_pjs=0.079844,
        trial_seeds=(7501, 7502, 7503),
        note_metric="dft",
    ),
    Condition(
        code="F",
        metric="dft",
        alpha=0.25,
        octave_weight=0.3,
        duration_weight=1.0,
        model_type="fc",
        stem="stimulus_F_dft_fc",
        reference_vs_ref_pjs=0.041159,
        trial_seeds=(7601, 7602, 7603),
        note_metric="dft",
    ),
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def ensure_out_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_model(cond: Condition, num_cycles: int, num_notes: int, seq_len: int):
    if cond.model_type == "transformer":
        return MusicGeneratorTransformer(
            num_cycles=num_cycles,
            num_notes=num_notes,
            d_model=128,
            nhead=4,
            num_layers=2,
            dropout=0.3,
            max_len=seq_len,
            use_pos_emb=True,
        )
    if cond.model_type == "fc":
        return MusicGeneratorFC(
            num_cycles=num_cycles,
            num_notes=num_notes,
            hidden_dim=128,
            dropout=0.3,
        )
    raise ValueError(f"unsupported model_type: {cond.model_type}")


def train_epochs(cond: Condition) -> int:
    return 50 if cond.model_type == "transformer" else 200


def make_reassigned_target(
    cond: Condition,
    notes_label: dict[tuple[int, int], int],
    cycle_labeled: dict[Any, Any],
    original_pair: list[list[tuple[int, int, int]]],
    seed: int,
) -> dict[str, Any]:
    kwargs = {
        "harmony_mode": "scale",
        "scale_type": "major",
        "pitch_range": (40, 88),
    }
    try:
        reassigned = find_new_notes(
            notes_label,
            cycle_labeled,
            note_metric=cond.note_metric,
            n_candidates=1000,
            seed=seed + 17,
            **kwargs,
        )
        used_pitch_range = (40, 88)
    except RuntimeError:
        reassigned = find_new_notes(
            notes_label,
            cycle_labeled,
            note_metric=cond.note_metric,
            n_candidates=1000,
            seed=seed + 17,
            harmony_mode="scale",
            scale_type="major",
            pitch_range=(24, 108),
        )
        used_pitch_range = (24, 108)

    new_notes_label = reassigned["new_notes_label"]
    remapped_pair = remap_music_notes(original_pair, notes_label, new_notes_label)
    remapped_flat = remapped_pair[0] + remapped_pair[1]
    harmony = analyze_harmony(notes_label, cycle_labeled, new_notes_label, reassigned["new_notes"])

    return {
        "new_notes_label": new_notes_label,
        "remapped_pair": remapped_pair,
        "remapped_flat": remapped_flat,
        "reassigned": reassigned,
        "harmony": harmony,
        "pitch_range_used": used_pitch_range,
    }


def run_one_trial(
    cond: Condition,
    *,
    seed: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    set_all_seeds(seed)

    bundle = suite.build_overlap_bundle(
        data,
        cond.metric,
        alpha=cond.alpha,
        octave_weight=cond.octave_weight,
        duration_weight=cond.duration_weight,
        use_decayed=False,
        threshold=0.35,
    )
    cycle_labeled = bundle["cycle_labeled"]
    ov_cont = bundle["activation_continuous"].values.astype(np.float32)

    original_pair = [data["inst1_real"], data["inst2_real"]]
    original_flat = data["inst1_real"] + data["inst2_real"]
    notes_label = data["notes_label"]

    note_target = make_reassigned_target(
        cond,
        notes_label=notes_label,
        cycle_labeled=cycle_labeled,
        original_pair=original_pair,
        seed=seed,
    )
    new_notes_label = note_target["new_notes_label"]
    remapped_pair = note_target["remapped_pair"]
    remapped_flat = note_target["remapped_flat"]

    ov_major_block32, reorder_info = reorder_overlap_matrix(
        ov_cont,
        strategy="block_permute",
        block_size=32,
        seed=seed + 23,
    )
    ov_major_block32 = ov_major_block32.astype(np.float32)

    num_notes = len(new_notes_label)
    seq_len = int(data["T"])
    x, y = prepare_training_data(
        ov_major_block32,
        remapped_pair,
        new_notes_label,
        seq_len,
        num_notes,
    )
    x_train, x_val, y_train, y_val = train_test_split(x, y, test_size=0.2, random_state=seed)

    model = build_model(cond, num_cycles=ov_major_block32.shape[1], num_notes=num_notes, seq_len=seq_len)
    history = train_model(
        model,
        x_train,
        y_train,
        x_val,
        y_val,
        epochs=train_epochs(cond),
        lr=0.001,
        batch_size=32,
        model_type=cond.model_type,
        seq_len=seq_len,
    )

    generated = generate_from_model(
        model,
        ov_major_block32,
        new_notes_label,
        model_type=cond.model_type,
        adaptive_threshold=True,
        min_onset_gap=0,
    )
    if not generated:
        raise RuntimeError(f"{cond.code}: generated sequence is empty")

    seq_vs_orig = evaluate_sequence_metrics(generated, original_flat, name=f"{cond.code}_vs_orig")
    seq_vs_ref = evaluate_sequence_metrics(generated, remapped_flat, name=f"{cond.code}_vs_ref")

    return {
        "seed": int(seed),
        "val_loss": float(history[-1]["val_loss"]) if history else None,
        "generated": generated,
        "n_notes_generated": int(len(generated)),
        "metrics": {
            "vs_orig_pitch_js": float(seq_vs_orig["pitch_js"]),
            "vs_orig_transition_js": float(seq_vs_orig["transition_js"]),
            "vs_orig_dtw": float(seq_vs_orig["dtw"]),
            "vs_ref_pitch_js": float(seq_vs_ref["pitch_js"]),
            "vs_ref_transition_js": float(seq_vs_ref["transition_js"]),
            "vs_ref_dtw": float(seq_vs_ref["dtw"]),
        },
        "reorder_info": reorder_info,
        "harmony": {
            "best_scale_match": note_target["harmony"]["best_scale_name"],
            "n_pitch_classes": int(note_target["harmony"]["n_pitch_classes"]),
        },
        "reassign_meta": {
            "note_dist_error": float(note_target["reassigned"]["note_dist_error"]),
            "cycle_dist_error": (
                float(note_target["reassigned"]["cycle_dist_error"])
                if note_target["reassigned"].get("cycle_dist_error") is not None
                else None
            ),
            "pitch_range_used": list(note_target["pitch_range_used"]),
            "note_variant": cond.note_variant,
        },
    }


def render_generated(generated: List[tuple[int, int, int]], stem: str) -> dict[str, Any]:
    mid_path = OUT_DIR / f"{stem}.mid"
    wav_path = OUT_DIR / f"{stem}.wav"

    write_pretty_midi(generated, str(mid_path), tempo_bpm=DEFAULT_TEMPO_BPM)
    render_mode = "stereo"
    fallback_reason = None
    try:
        duration_s = render_midi_to_wav_stereo(str(mid_path), str(wav_path))
    except Exception as exc:
        fallback_reason = f"{type(exc).__name__}: {exc}"
        render_mode = "mono_fallback"
        duration_s = render_midi_to_wav(str(mid_path), str(wav_path))

    return {
        "mid": str(mid_path),
        "wav": str(wav_path),
        "duration_s": float(duration_s),
        "render_mode": render_mode,
        "fallback_reason": fallback_reason,
    }


def pick_best_trial(rows: List[dict[str, Any]]) -> dict[str, Any]:
    return min(rows, key=lambda r: r["metrics"]["vs_ref_pitch_js"])


def relative_to_base(path_str: str) -> str:
    p = Path(path_str)
    return p.relative_to(BASE_DIR).as_posix()


def update_overrides(items: List[dict[str, Any]]) -> str:
    if OVERRIDES_PATH.exists():
        with OVERRIDES_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    for item in items:
        payload[item["code"]] = relative_to_base(item["artifacts"]["wav"])

    with OVERRIDES_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return str(OVERRIDES_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate D/E/F listening stimuli")
    parser.add_argument(
        "--condition",
        choices=["D", "E", "F", "all"],
        default="all",
        help="특정 조건만 생성하려면 D/E/F를 지정합니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 D/E/F 재학습을 진행할 수 없습니다.")

    ensure_out_dir()
    os.chdir(BASE_DIR)

    print("=" * 80)
    print("Task 45-B D/E/F regeneration start")
    print("=" * 80)

    data = suite.setup_hibari()

    selected = [c for c in CONDITIONS if args.condition in ("all", c.code)]
    outputs: List[dict[str, Any]] = []

    for cond in selected:
        print("\n" + "-" * 80)
        print(f"[{cond.code}] {cond.stem}")
        print(
            f"metric={cond.metric} alpha={cond.alpha} ow={cond.octave_weight} "
            f"dw={cond.duration_weight} model={cond.model_type}"
        )
        print("-" * 80)

        trials: List[dict[str, Any]] = []
        for seed in cond.trial_seeds:
            try:
                row = run_one_trial(cond, seed=seed, data=data)
                trials.append(row)
                print(
                    f"  seed={seed} vs_ref_pjs={row['metrics']['vs_ref_pitch_js']:.6f} "
                    f"vs_orig_pjs={row['metrics']['vs_orig_pitch_js']:.6f} "
                    f"dtw={row['metrics']['vs_orig_dtw']:.6f}"
                )
                # prompt 요구 N=1 trial, 성공 즉시 종료
                break
            except Exception as exc:
                print(f"  [retry] seed={seed} -> {type(exc).__name__}: {exc}")

        if not trials:
            raise RuntimeError(f"{cond.code}: 모든 trial seed 실패")

        best = pick_best_trial(trials)
        artifacts = render_generated(best["generated"], cond.stem)
        print(
            f"  [saved] {artifacts['wav']} "
            f"(render={artifacts['render_mode']}, {artifacts['duration_s']:.1f}s)"
        )

        outputs.append(
            {
                "code": cond.code,
                "stem": cond.stem,
                "metric": cond.metric,
                "alpha": cond.alpha,
                "octave_weight": cond.octave_weight,
                "duration_weight": cond.duration_weight,
                "model_type": cond.model_type,
                "reference_vs_ref_pjs": cond.reference_vs_ref_pjs,
                "post_bugfix_reproduction": True,
                "selected_trial": {
                    "seed": best["seed"],
                    "val_loss": best["val_loss"],
                    "metrics": best["metrics"],
                    "harmony": best["harmony"],
                    "reassign_meta": best["reassign_meta"],
                    "reorder_info": best["reorder_info"],
                    "n_notes_generated": best["n_notes_generated"],
                },
                "trial_count_attempted": len(trials),
                "artifacts": artifacts,
                "generated_at": now_iso(),
            }
        )

    override_path = update_overrides(outputs)
    payload = {
        "generated_at": now_iso(),
        "script": "listening_test/regenerate_DEF_stimuli.py",
        "outputs": outputs,
        "overrides_path": override_path,
    }
    with METADATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("Task 45-B completed")
    print("=" * 80)
    print(f"metadata: {METADATA_PATH}")
    print(f"overrides: {override_path}")
    for item in outputs:
        m = item["selected_trial"]["metrics"]
        print(
            f"- {item['code']} | seed={item['selected_trial']['seed']} "
            f"vs_ref_pjs={m['vs_ref_pitch_js']:.6f} "
            f"vs_orig_pjs={m['vs_orig_pitch_js']:.6f} "
            f"wav={item['artifacts']['wav']}"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n[ERROR]", exc)
        traceback.print_exc()
        raise
