"""
gen_pipeline_progression_wavs.py
================================

hibari 파이프라인 분기별 성능 향상 WAV 생성.

출력: output/pipeline_progression/ (v0 ~ v6)

  v0. 원곡 (reuse from output/final/)
  v1. Algo1 + frequency + binary OM          baseline
  v2. Algo1 + DFT + binary OM                §4.1 거리 함수 효과
  v3. Algo1 + DFT + per-cycle τ (α=0.5)      §5.7 continuous + per-cycle τ (reuse)
  v4. Algo1 + DFT + per-cycle τ + α=0.25     §5.8.1 Phase 2 최저 (Algo1 best)
  v5. Algo2 FC-cont + DFT (α=0.5)            §5.8.2 absolute best (reuse)
  v6. §6 블록 단위 P3+best-of-10 (α=0.25)    §6.6 best global trial (m=0, seed 9309)

각 단계 Algo1 신규 생성분은 5 trial 중 JS 최저 seed 선택.
v6은 m=0, seed=9309, k=10 reproduce.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import pickle

# --- path_bootstrap ---
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "experiments"))
sys.path.insert(0, _HERE)
# --- end path_bootstrap ---

import pretty_midi
import scipy.io.wavfile as wavfile

try:
    import fluidsynth
except ImportError:
    fluidsynth = None

try:
    import torch
except ImportError:
    torch = None

from eval_metrics import evaluate_generation
from generation import (
    CycleSetManager,
    NodePool,
    algorithm1_optimized,
    notes_to_xml,
)
import run_dft_gap0_suite as suite
import run_phase3_task38a_dft_gap0 as task56

# suite/task56의 BASE_DIR은 experiments/로 잡혀있어 MIDI 경로 교정
_ROOT_MIDI = os.path.join(_ROOT, "Ryuichi_Sakamoto_-_hibari.mid")
suite.MIDI_FILE = _ROOT_MIDI
suite.BASE_DIR = _ROOT
suite.STEP3_DIR = os.path.join(_ROOT, "docs", "step3_data")
task56.BASE_DIR = _ROOT
task56.MIDI_FILE = _ROOT_MIDI

from gen_final_wavs import render_midi_to_wav_stereo as render_midi_to_wav

BASE_DIR = _ROOT
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUT_DIR = os.path.join(BASE_DIR, "output", "pipeline_progression")
FINAL_DIR = os.path.join(BASE_DIR, "output", "final")
HIBARI_MID = os.path.join(BASE_DIR, "Ryuichi_Sakamoto_-_hibari.mid")

TEMPO_BPM = 66
ALGO1_N_TRIALS = 5


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def ensure_out_dir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def write_pretty_midi(generated, mid_path, tempo_bpm=TEMPO_BPM) -> None:
    sec_per_8th = 60.0 / float(tempo_bpm) / 2.0
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(tempo_bpm))
    inst = pretty_midi.Instrument(program=0, name="Piano")
    for start_idx, pitch, end_idx in generated:
        inst.notes.append(pretty_midi.Note(
            velocity=80, pitch=int(pitch),
            start=float(start_idx) * sec_per_8th,
            end=float(end_idx) * sec_per_8th,
        ))
    pm.instruments.append(inst)
    pm.write(mid_path)


def save_as_wav(generated, stem) -> dict:
    """MusicXML 우선 → MIDI → WAV. 실패 시 pretty_midi fallback."""
    xml_path = os.path.join(OUT_DIR, f"{stem}.musicxml")
    mid_path = os.path.join(OUT_DIR, f"{stem}.mid")
    wav_path = os.path.join(OUT_DIR, f"{stem}.wav")

    render_mode = "musicxml_to_wav_stereo"
    fallback_reason = None

    try:
        score = notes_to_xml([generated], tempo_bpm=TEMPO_BPM,
                             file_name=stem, output_dir=OUT_DIR)
        if score is None:
            raise RuntimeError("notes_to_xml returned None")
        score.write("midi", fp=mid_path)
        duration = render_midi_to_wav(mid_path, wav_path)
    except Exception as e:
        fallback_reason = f"{type(e).__name__}: {e}"
        render_mode = "fallback_pretty_midi_to_wav_stereo"
        write_pretty_midi(generated, mid_path)
        duration = render_midi_to_wav(mid_path, wav_path)

    return {
        "xml": xml_path if render_mode == "musicxml_to_wav" else None,
        "mid": mid_path,
        "wav": wav_path,
        "duration_s": round(float(duration), 3),
        "render_mode": render_mode,
        "fallback_reason": fallback_reason,
    }


def make_percycle_overlap(cont_overlap, taus):
    k = cont_overlap.shape[1]
    if len(taus) < k:
        raise ValueError(f"tau 부족: {len(taus)} < {k}")
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus[:k]):
        out[:, ci] = (cont_overlap[:, ci] >= float(tau)).astype(np.float32)
    return out


def run_algo1_best(data, overlap_values, cycle_labeled, *, n_trials, seed_base):
    """n_trials 중 JS 최저 trial 선택."""
    best = {"seed": None, "js": float("inf"), "generated": None}
    for i in range(n_trials):
        seed = seed_base + i
        set_seeds(seed)
        pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        manager = CycleSetManager(cycle_labeled)
        generated = algorithm1_optimized(
            pool, suite.INST_CHORD_HEIGHTS, overlap_values, manager,
            max_resample=50, verbose=False, min_onset_gap=0,
        )
        metrics = evaluate_generation(
            generated,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"], name="",
        )
        js = float(metrics["js_divergence"])
        print(f"    seed={seed}  JS={js:.5f}  notes={len(generated)}")
        if js < best["js"]:
            best = {"seed": int(seed), "js": js, "generated": generated,
                    "n_notes": int(len(generated))}
    return best


def load_alpha025_cache():
    path = os.path.join(CACHE_DIR, "metric_dft_alpha0p25_ow0p3_dw1p0.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def setup_for_task56(data):
    """task56 script expects data to have chord_seq1/chord_seq2 etc."""
    from preprocessing import group_notes_with_duration, build_chord_labels, prepare_lag_sequences
    inst1 = data["inst1_real"]
    inst2 = data["inst2_real"]
    _, cs1 = build_chord_labels(group_notes_with_duration(inst1))
    _, cs2 = build_chord_labels(group_notes_with_duration(inst2))
    data["chord_seq1"] = cs1
    data["chord_seq2"] = cs2
    return data


def generate_v6_block(data):
    """§6 block-based best global trial: m=0, seed=9309, k=10."""
    data = setup_for_task56(data)
    cycle_local, proto, n_cyc = task56.compute_module_local_ph(data, start_module=0)
    if cycle_local is None or proto is None:
        raise RuntimeError("v6: P3 prototype 계산 실패 (m=0)")
    print(f"    K_local={n_cyc}, prototype density={float((proto>0).mean()):.3f}")

    mod, cov, best_j = task56.gen_with_best_of_k(
        data, proto, cycle_local, base_seed=9309, k=10
    )
    print(f"    best_j={best_j}, module_coverage={cov}/23")

    all_gen = task56.replicate_inst1(mod) + task56.replicate_inst2(mod)
    metrics = evaluate_generation(
        all_gen,
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"], name="",
    )
    return {
        "seed": 9309,
        "best_j": int(best_j),
        "js": float(metrics["js_divergence"]),
        "generated": all_gen,
        "module_coverage": int(cov),
        "n_notes": int(len(all_gen)),
    }


def copy_existing(src, dst):
    if os.path.exists(src):
        shutil.copy2(src, dst)
        return True
    return False


def main():
    os.chdir(BASE_DIR)
    ensure_out_dir()

    t_start = time.time()
    print("=" * 72)
    print("파이프라인 분기별 성능 향상 WAV 생성")
    print("=" * 72)

    data = suite.setup_hibari()
    entries: list[dict[str, Any]] = []

    # ---- v0: 원곡 (reuse) ----
    print("\n[v0] 원곡")
    src = os.path.join(FINAL_DIR, "hibari_original.wav")
    dst = os.path.join(OUT_DIR, "v0_hibari_original.wav")
    if copy_existing(src, dst):
        print(f"    reused: {dst}")
        entries.append({"stage": "v0", "file": "v0_hibari_original.wav",
                        "purpose": "원곡 비교 기준", "config": "original midi render",
                        "js_run": None, "reused_from": src})
    else:
        print("    [ERROR] final/hibari_original.wav 없음")

    # ---- v1: Algo1 + frequency + binary ----
    print("\n[v1] Algo1 + frequency + binary OM  (baseline)")
    freq_bundle = suite.build_overlap_bundle(
        data, "frequency", alpha=0.5,
        octave_weight=0.3, duration_weight=1.0,
    )
    v1_best = run_algo1_best(
        data,
        freq_bundle["overlap_binary"].values.astype(np.float32),
        freq_bundle["cycle_labeled"],
        n_trials=ALGO1_N_TRIALS, seed_base=1000,
    )
    v1_art = save_as_wav(v1_best["generated"], "v1_algo1_frequency_binary")
    entries.append({"stage": "v1", "file": "v1_algo1_frequency_binary.wav",
                    "purpose": "Baseline: frequency distance + binary OM",
                    "config": "metric=frequency, alpha=0.5, overlap=binary, gap=0",
                    "js_ref_paper": "0.0345 (§4.1)",
                    "js_run": round(v1_best["js"], 6),
                    "seed": v1_best["seed"],
                    "K": len(freq_bundle["cycle_labeled"]),
                    **v1_art})

    # ---- v2: Algo1 + DFT + binary ----
    print("\n[v2] Algo1 + DFT + binary OM  (+ distance function)")
    dft_bundle = suite.build_overlap_bundle(
        data, "dft", alpha=0.5,
        octave_weight=0.3, duration_weight=1.0,
    )
    v2_best = run_algo1_best(
        data,
        dft_bundle["overlap_binary"].values.astype(np.float32),
        dft_bundle["cycle_labeled"],
        n_trials=ALGO1_N_TRIALS, seed_base=2000,
    )
    v2_art = save_as_wav(v2_best["generated"], "v2_algo1_dft_binary")
    entries.append({"stage": "v2", "file": "v2_algo1_dft_binary.wav",
                    "purpose": "+DFT distance (§4.1)",
                    "config": "metric=dft, alpha=0.5, ow=0.3, dw=1.0, overlap=binary",
                    "js_ref_paper": "0.0213 (§4.1)",
                    "js_run": round(v2_best["js"], 6),
                    "seed": v2_best["seed"],
                    "K": len(dft_bundle["cycle_labeled"]),
                    **v2_art})

    # ---- v3: DFT + per-cycle τ (α=0.5) — reuse ----
    print("\n[v3] Algo1 + DFT + per-cycle τ (α=0.5)  (reuse from output/final/)")
    src3 = os.path.join(FINAL_DIR, "hibari_dft_gap0_algo1_final.wav")
    dst3 = os.path.join(OUT_DIR, "v3_algo1_dft_percycle_tau_alpha05.wav")
    if copy_existing(src3, dst3):
        for ext in [".mid", ".musicxml"]:
            src_ext = src3.replace(".wav", ext)
            dst_ext = dst3.replace(".wav", ext)
            copy_existing(src_ext, dst_ext)
        print(f"    reused: {dst3}")
        entries.append({"stage": "v3", "file": "v3_algo1_dft_percycle_tau_alpha05.wav",
                        "purpose": "+per-cycle τ continuous OM (§5.7)",
                        "config": "metric=dft, alpha=0.5, overlap=continuous->per-cycle tau",
                        "js_ref_paper": "0.01489 (§5.7)",
                        "js_run": 0.01437, "seed": 9004,
                        "reused_from": src3})
    else:
        print("    [ERROR] final/hibari_dft_gap0_algo1_final.wav 없음")

    # ---- v4: DFT + per-cycle τ + α=0.25 (best record) ----
    print("\n[v4] Algo1 + DFT + per-cycle τ + α=0.25  (Algo1 best record)")
    alpha25 = load_alpha025_cache()
    alpha25_taus_json = os.path.join(STEP3_DIR, "percycle_tau_dft_alpha025_results.json")
    with open(alpha25_taus_json, "r", encoding="utf-8") as f:
        a25 = json.load(f)
    taus_a25 = a25["percycle"]["tau_profile"]
    cont_a25 = alpha25["activation_continuous"].values.astype(np.float32)
    ov_a25_pc = make_percycle_overlap(cont_a25, taus_a25)
    v4_best = run_algo1_best(
        data, ov_a25_pc, alpha25["cycle_labeled"],
        n_trials=ALGO1_N_TRIALS, seed_base=7200,
    )
    v4_art = save_as_wav(v4_best["generated"], "v4_algo1_dft_percycle_alpha025")
    entries.append({"stage": "v4", "file": "v4_algo1_dft_percycle_alpha025.wav",
                    "purpose": "+α=0.25 Phase 2 최저 Algo1 (§5.8.1)",
                    "config": "metric=dft, alpha=0.25, K=14, overlap=continuous->per-cycle tau",
                    "js_ref_paper": "0.00902 ± 0.00170 (N=20)",
                    "js_run": round(v4_best["js"], 6),
                    "seed": v4_best["seed"],
                    "K": len(alpha25["cycle_labeled"]),
                    **v4_art})

    # ---- v5: Algo2 FC-cont — reuse ----
    print("\n[v5] Algo2 FC-cont DFT (α=0.5)  (absolute best, reuse)")
    src5 = os.path.join(FINAL_DIR, "hibari_dft_gap0_algo2_fc_cont_final.wav")
    dst5 = os.path.join(OUT_DIR, "v5_algo2_fc_cont_dft_alpha05.wav")
    if copy_existing(src5, dst5):
        for ext in [".mid", ".musicxml"]:
            copy_existing(src5.replace(".wav", ext), dst5.replace(".wav", ext))
        print(f"    reused: {dst5}")
        entries.append({"stage": "v5", "file": "v5_algo2_fc_cont_dft_alpha05.wav",
                        "purpose": "Algo2 FC-cont 본 연구 최저 (§5.8.2)",
                        "config": "FC, metric=dft, alpha=0.5, overlap=continuous",
                        "js_ref_paper": "0.00035 ± 0.00015 (N=10)",
                        "js_run": 0.00022, "seed": 6111,
                        "reused_from": src5})
    else:
        print("    [ERROR] final/hibari_dft_gap0_algo2_fc_cont_final.wav 없음")

    # ---- v6: §6 block-based (P3 + best-of-10, m=0, seed 9309) ----
    print("\n[v6] §6 블록 단위 P3 + best-of-10 (m=0, seed=9309, α=0.25)")
    v6 = generate_v6_block(data)
    v6_art = save_as_wav(v6["generated"], "v6_block_p3_bestof10_m0")
    entries.append({"stage": "v6", "file": "v6_block_p3_bestof10_m0.wav",
                    "purpose": "§6 블록 단위 best global trial (§6.6)",
                    "config": "metric=dft, alpha=0.25, block_len=32, m=0, P3 + best-of-10",
                    "js_ref_paper": "0.01479 (best global trial)",
                    "js_run": round(v6["js"], 6),
                    "seed": v6["seed"],
                    "best_j": v6["best_j"],
                    "module_coverage": f"{v6['module_coverage']}/23",
                    **v6_art})

    # ---- 메타데이터 기록 ----
    meta = {
        "generated_at": now_iso(),
        "elapsed_s": round(time.time() - t_start, 1),
        "out_dir": OUT_DIR,
        "rendering": "UprightPianoKW SF2 44.1kHz stereo, sustain+reverb+chorus",
        "entries": entries,
    }
    meta_path = os.path.join(OUT_DIR, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # README
    lines = ["# Pipeline Progression WAV — hibari",
             "",
             f"- 생성: {meta['generated_at']}",
             f"- 소요: {meta['elapsed_s']}s",
             f"- 렌더링: {meta['rendering']}",
             "",
             "| 단계 | 파일 | JS (논문) | JS (run) | 설정 |",
             "|---|---|---|---|---|"]
    for e in entries:
        lines.append(
            f"| {e['stage']} | `{e['file']}` | "
            f"{e.get('js_ref_paper', '-')} | {e.get('js_run', '-')} | "
            f"{e.get('config', '-')} |"
        )
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n" + "=" * 72)
    print(f"완료 — {OUT_DIR}")
    print(f"소요: {meta['elapsed_s']}s")
    print("=" * 72)


if __name__ == "__main__":
    main()
