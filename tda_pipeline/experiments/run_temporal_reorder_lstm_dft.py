"""
Task 39-4 — §6.4 LSTM 시간 재배치 실측 (DFT, gap=0)

요구 조건:
  - metric='dft', alpha=0.25, octave_weight=0.3, duration_weight=1.0
  - min_onset_gap=0, post_bugfix=True
  - 모델: LSTM (hidden=128, num_layers=2)
  - 조건 5종 × N=5

출력:
  docs/step3_data/temporal_reorder_lstm_dft_gap0.json
"""
from __future__ import annotations

import json
import os
import pickle
import random
import time
from typing import Any

import numpy as np
from sklearn.model_selection import train_test_split

try:
    import torch
except Exception:  # pragma: no cover - optional dependency guard
    torch = None

from config import PipelineConfig
from generation import (
    MusicGeneratorLSTM,
    generate_from_model,
    prepare_training_data,
    train_model,
)
from sequence_metrics import evaluate_sequence_metrics
from temporal_reorder import reorder_overlap_matrix
from utils.result_meta import build_result_header

import run_dft_gap0_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
OUT_PATH = os.path.join(STEP3_DIR, "temporal_reorder_lstm_dft_gap0.json")
SUMMARY_PATH = os.path.join(STEP3_DIR, "phase3_task39_4_lstm_summary.json")

# 우선 캐시 사용: Task 39 Wave2에서 생성한 alpha=0.25 전용 캐시
CACHE_PATH = os.path.join(
    BASE_DIR,
    "cache",
    "metric_dft_alpha0p25_ow0p3_dw1p0.pkl",
)

METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
POST_BUGFIX = True

N_REPEATS = 5
EPOCHS = 50
LR = 0.001
BATCH_SIZE = 32
SEED_BASE = 3900

CONDITIONS = (
    "baseline",
    "segment_shuffle_retrain_x",
    "block_permute32_retrain_x",
    "markov_tau1_retrain_x",
    "segment_shuffle_retrain_o",
)


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def ensure_dirs() -> None:
    os.makedirs(STEP3_DIR, exist_ok=True)


def metric_stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"mean": None, "std": None}
    return {
        "mean": round(float(arr.mean()), 6),
        "std": round(float(arr.std(ddof=1) if arr.size > 1 else 0.0), 6),
    }


def make_header() -> dict[str, Any]:
    cfg = PipelineConfig()
    cfg.metric.metric = METRIC
    cfg.metric.alpha = float(ALPHA)
    cfg.metric.octave_weight = float(OCTAVE_WEIGHT)
    cfg.metric.duration_weight = float(DURATION_WEIGHT)
    cfg.min_onset_gap = int(MIN_ONSET_GAP)
    cfg.post_bugfix = bool(POST_BUGFIX)
    return build_result_header(
        cfg,
        script_name=__file__,
        n_repeats=N_REPEATS,
        extra={
            "model": "lstm",
            "track": "hibari",
            "overlap_type": "continuous",
            "task": "T39-4",
        },
    )


def load_continuous_overlap(data: dict[str, Any]) -> tuple[np.ndarray, int]:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "rb") as f:
            cached = pickle.load(f)
        act_cont = cached.get("activation_continuous")
        cycle_labeled = cached.get("cycle_labeled")
        if act_cont is not None and cycle_labeled is not None:
            values = act_cont.values if hasattr(act_cont, "values") else act_cont
            return values.astype(np.float32), int(len(cycle_labeled))

    bundle = suite.build_overlap_bundle(
        data,
        METRIC,
        alpha=ALPHA,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=0.35,
    )
    cont = bundle["activation_continuous"].values.astype(np.float32)
    return cont, int(len(bundle["cycle_labeled"]))


def fit_lstm(
    *,
    x_input: np.ndarray,
    y_target: np.ndarray,
    num_notes: int,
    seq_len: int,
    seed: int,
) -> tuple[Any, float]:
    if torch is None:
        raise RuntimeError("torch가 설치되어 있지 않아 LSTM 실험을 수행할 수 없습니다.")

    set_all_seeds(seed)
    x_train, x_valid, y_train, y_valid = train_test_split(
        x_input, y_target, test_size=0.2, random_state=seed
    )

    model = MusicGeneratorLSTM(
        num_cycles=x_input.shape[1],
        num_notes=num_notes,
        hidden_dim=128,
        num_layers=2,
        dropout=0.3,
    )
    history = train_model(
        model,
        x_train,
        y_train,
        x_valid,
        y_valid,
        epochs=EPOCHS,
        lr=LR,
        batch_size=BATCH_SIZE,
        model_type="lstm",
        seq_len=seq_len,
    )
    return model, float(history[-1]["val_loss"])


def eval_lstm(
    *,
    model: Any,
    overlap_values: np.ndarray,
    notes_label: dict[tuple[int, int], int],
    original_notes: list[tuple[int, int, int]],
    name: str,
) -> dict[str, float]:
    generated = generate_from_model(
        model,
        overlap_values,
        notes_label,
        model_type="lstm",
        adaptive_threshold=True,
        min_onset_gap=MIN_ONSET_GAP,
    )
    if not generated:
        raise RuntimeError(f"{name}: 생성된 음표가 없습니다.")

    seq = evaluate_sequence_metrics(generated, original_notes, name=name)
    return {
        "pitch_js": float(seq["pitch_js"]),
        "transition_js": float(seq["transition_js"]),
        "dtw": float(seq["dtw"]),
        "n_notes": float(len(generated)),
    }


def summarize_conditions(raw: dict[str, list[dict[str, float]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cond in CONDITIONS:
        samples = raw[cond]
        out[cond] = {
            "pitch_js": metric_stats([s["pitch_js"] for s in samples]),
            "transition_js": metric_stats([s["transition_js"] for s in samples]),
            "dtw": metric_stats([s["dtw"] for s in samples]),
            "val_loss": metric_stats([s["val_loss"] for s in samples]),
            "n_notes": metric_stats([s["n_notes"] for s in samples]),
            "n_samples": len(samples),
        }
    return out


def main() -> None:
    ensure_dirs()
    print("=" * 80)
    print("Task 39-4 | LSTM temporal reorder 실측 (DFT continuous, gap=0)")
    print("=" * 80)
    t0 = time.time()

    data = suite.setup_hibari()
    cont_overlap, n_cycles = load_continuous_overlap(data)
    notes_label = data["notes_label"]
    total_length = int(data["T"])
    num_notes = len(notes_label)
    original_notes = data["inst1_real"] + data["inst2_real"]

    _, y_original = prepare_training_data(
        cont_overlap,
        [data["inst1_real"], data["inst2_real"]],
        notes_label,
        total_length,
        num_notes,
    )

    raw: dict[str, list[dict[str, float]]] = {k: [] for k in CONDITIONS}

    for i in range(N_REPEATS):
        rep_seed = SEED_BASE + i * 97
        print(f"\n[반복 {i + 1}/{N_REPEATS}] seed={rep_seed}")

        seg_overlap, _ = reorder_overlap_matrix(
            cont_overlap, strategy="segment_shuffle", seed=rep_seed + 11
        )
        block_overlap, _ = reorder_overlap_matrix(
            cont_overlap, strategy="block_permute", seed=rep_seed + 23, block_size=32
        )
        markov_overlap, _ = reorder_overlap_matrix(
            cont_overlap, strategy="markov_resample", seed=rep_seed + 37, temperature=1.0
        )

        # retrain X: baseline overlap으로 학습한 모델을 모든 재배치 입력에 적용
        model_x, val_x = fit_lstm(
            x_input=cont_overlap,
            y_target=y_original,
            num_notes=num_notes,
            seq_len=total_length,
            seed=rep_seed + 100,
        )

        for key, ov in (
            ("baseline", cont_overlap),
            ("segment_shuffle_retrain_x", seg_overlap.astype(np.float32)),
            ("block_permute32_retrain_x", block_overlap.astype(np.float32)),
            ("markov_tau1_retrain_x", markov_overlap.astype(np.float32)),
        ):
            ev = eval_lstm(
                model=model_x,
                overlap_values=ov,
                notes_label=notes_label,
                original_notes=original_notes,
                name=f"{key}_rep{i + 1}",
            )
            ev["val_loss"] = float(val_x)
            ev["seed"] = float(rep_seed)
            raw[key].append(ev)

        # retrain O: segment_shuffle overlap으로 학습 + 생성
        seg_overlap = seg_overlap.astype(np.float32)
        model_o, val_o = fit_lstm(
            x_input=seg_overlap,
            y_target=y_original,
            num_notes=num_notes,
            seq_len=total_length,
            seed=rep_seed + 200,
        )
        ev_o = eval_lstm(
            model=model_o,
            overlap_values=seg_overlap,
            notes_label=notes_label,
            original_notes=original_notes,
            name=f"segment_shuffle_retrain_o_rep{i + 1}",
        )
        ev_o["val_loss"] = float(val_o)
        ev_o["seed"] = float(rep_seed)
        raw["segment_shuffle_retrain_o"].append(ev_o)

        print(
            f"  baseline dtw={raw['baseline'][-1]['dtw']:.4f} | "
            f"segX={raw['segment_shuffle_retrain_x'][-1]['dtw']:.4f} | "
            f"blkX={raw['block_permute32_retrain_x'][-1]['dtw']:.4f} | "
            f"mkvX={raw['markov_tau1_retrain_x'][-1]['dtw']:.4f} | "
            f"segO={raw['segment_shuffle_retrain_o'][-1]['dtw']:.4f}"
        )

    conditions = summarize_conditions(raw)
    baseline_dtw = conditions["baseline"]["dtw"]["mean"]

    dtw_change_pct: dict[str, float] = {}
    for key in CONDITIONS:
        if key == "baseline":
            continue
        dtw_mean = conditions[key]["dtw"]["mean"]
        dtw_change_pct[key] = round(100.0 * (dtw_mean - baseline_dtw) / baseline_dtw, 4)

    max_abs_change = max(abs(v) for v in dtw_change_pct.values())
    reproduced = all(abs(v) <= 0.5 for v in dtw_change_pct.values())
    if reproduced:
        recommendation = "서술 유지"
    elif max_abs_change <= 1.0:
        recommendation = "수치 교체"
    else:
        recommendation = "전면 재작성"

    payload = {
        **make_header(),
        "conditions": conditions,
        "dtw_change_pct": dtw_change_pct,
        "verdict": {
            "threshold_0_5_pct_reproduced": reproduced,
            "max_dtw_change_pct": round(float(max_abs_change), 4),
            "recommendation": recommendation,
        },
        "elapsed_s": round(float(time.time() - t0), 1),
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    summary = {
        "output_json": os.path.relpath(OUT_PATH, BASE_DIR),
        "dtw_change_pct": dtw_change_pct,
        "reproduced_le_0_5pct": reproduced,
        "recommendation": recommendation,
        "elapsed_s": payload["elapsed_s"],
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n완료")
    print(f"  저장: {OUT_PATH}")
    print(f"  요약: {SUMMARY_PATH}")
    print(f"  verdict: {payload['verdict']}")


if __name__ == "__main__":
    main()

