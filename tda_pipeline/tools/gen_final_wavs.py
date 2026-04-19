"""
gen_final_wavs.py
=================

세션 C 최종 WAV 5종 생성 스크립트.

출력:
  - output/final/hibari_dft_gap0_algo1_final.wav
  - output/final/hibari_dft_gap0_algo2_fc_cont_final.wav
  - output/final/hibari_original.wav
  - output/final/hibari_dft_gap3_algo1_legacy.wav
  - output/final/hibari_tonnetz_complex_legacy.wav
  - output/final/README.md

요구 고정:
  - SoundFont: UprightPianoKW
  - 44.1kHz, 16-bit, stereo
  - sustain + reverb + chorus
"""

from __future__ import annotations

import json
import os
import random
import traceback
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
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

from sklearn.model_selection import train_test_split

from config import PipelineConfig
from eval_metrics import evaluate_generation
from generation import (
    CycleSetManager,
    MusicGeneratorFC,
    NodePool,
    algorithm1_optimized,
    generate_from_model,
    notes_to_xml,
    prepare_training_data,
    train_model,
)
from overlap import build_activation_matrix
from pipeline import TDAMusicPipeline

import run_dft_gap0_suite as suite


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STEP3_DIR = os.path.join(BASE_DIR, "docs", "step3_data")
FINAL_DIR = os.path.join(BASE_DIR, "output", "final")
HIBARI_MID = os.path.join(BASE_DIR, "Ryuichi_Sakamoto_-_hibari.mid")

SF2_PATH = "C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2"
SAMPLE_RATE = 44100
TEMPO_BPM = 66
REVERB_TAIL = 2.0
DEFAULT_ALPHA = 0.5
DEFAULT_OW = 0.3
DEFAULT_DW = 1.0

# legacy Tonnetz complex (실험 B)
LEGACY_COMPLEX_ALPHA = 0.25
LEGACY_COMPLEX_OW = 0.0
LEGACY_COMPLEX_DW = 0.3
LEGACY_COMPLEX_RC = 0.1
LEGACY_COMPLEX_RATE_T = 0.3


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def load_json(name: str) -> dict:
    path = os.path.join(STEP3_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs() -> None:
    os.makedirs(FINAL_DIR, exist_ok=True)


def make_percycle_overlap(cont_overlap: np.ndarray, taus: List[float]) -> np.ndarray:
    k = cont_overlap.shape[1]
    if len(taus) < k:
        raise ValueError(f"tau 길이 부족: len(taus)={len(taus)}, K={k}")
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus[:k]):
        out[:, ci] = (cont_overlap[:, ci] >= float(tau)).astype(np.float32)
    return out


def render_midi_to_wav_stereo(
    mid_path: str,
    wav_path: str,
    *,
    sf2_path: str = SF2_PATH,
    sample_rate: int = SAMPLE_RATE,
    pedal_threshold: int = 2,
    reverb_tail: float = REVERB_TAIL,
) -> float:
    """
    MIDI -> WAV (stereo, int16).
    wav_renderer.py와 동일한 이펙트/페달 정책을 유지하되 stereo로 저장.
    """
    if fluidsynth is None:
        raise RuntimeError("fluidsynth가 설치되지 않아 WAV 렌더링을 수행할 수 없습니다.")
    if not os.path.exists(sf2_path):
        raise FileNotFoundError(f"SoundFont가 없습니다: {sf2_path}")

    pm = pretty_midi.PrettyMIDI(mid_path)
    fs = fluidsynth.Synth(samplerate=float(sample_rate))

    fs.setting("synth.reverb.active", 1)
    fs.setting("synth.chorus.active", 1)
    fs.set_reverb(roomsize=0.6, damping=0.4, width=0.8, level=0.3)
    fs.set_chorus(nr=3, level=0.4, speed=0.3, depth=8.0, type=0)

    sfid = fs.sfload(sf2_path)
    fs.program_select(0, sfid, 0, 0)

    events = []
    for inst in pm.instruments:
        for n in inst.notes:
            events.append(("on", n.start, n.pitch, n.velocity))
            events.append(("off", n.end, n.pitch, 0))

    # pedal: 동시 발음 2개 이상 구간 ON
    all_notes = sorted((n.start, n.end) for inst in pm.instruments for n in inst.notes)
    pedal_on = set()
    resolution = 0.05
    t = 0.0
    end_time = pm.get_end_time()
    while t < end_time:
        active = sum(1 for s, e in all_notes if s <= t < e)
        if active >= pedal_threshold:
            key = round(t, 3)
            if key not in pedal_on:
                events.append(("pedal_on", t, 0, 0))
                pedal_on.add(key)
        else:
            prev_key = round(t - resolution, 3)
            if prev_key in pedal_on:
                events.append(("pedal_off", t, 0, 0))
        t += resolution

    events.sort(key=lambda x: x[1])

    chunks = []
    current_time = 0.0
    for ev_type, ev_time, pitch, vel in events:
        dt = ev_time - current_time
        if dt > 0:
            n_samples = int(dt * sample_rate)
            if n_samples > 0:
                chunks.append(np.array(fs.get_samples(n_samples), dtype=np.float32))
            current_time = ev_time

        if ev_type == "on":
            fs.noteon(0, int(pitch), int(vel))
        elif ev_type == "off":
            fs.noteoff(0, int(pitch))
        elif ev_type == "pedal_on":
            fs.cc(0, 64, 127)
        elif ev_type == "pedal_off":
            fs.cc(0, 64, 0)

    chunks.append(np.array(fs.get_samples(int(reverb_tail * sample_rate)), dtype=np.float32))
    fs.delete()

    audio = np.concatenate(chunks) if chunks else np.zeros(2, dtype=np.float32)
    if audio.size % 2 != 0:
        audio = audio[:-1]
    stereo = audio.reshape(-1, 2)

    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if peak > 0:
        stereo = stereo / peak * 0.9

    wavfile.write(wav_path, sample_rate, (stereo * 32767).astype(np.int16))
    return float(stereo.shape[0] / sample_rate)


def write_pretty_midi(generated: List[Tuple[int, int, int]], mid_path: str, tempo_bpm: int = TEMPO_BPM) -> None:
    sec_per_8th = 60.0 / float(tempo_bpm) / 2.0
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(tempo_bpm))
    inst = pretty_midi.Instrument(program=0, name="Piano")
    for start_idx, pitch, end_idx in generated:
        inst.notes.append(
            pretty_midi.Note(
                velocity=80,
                pitch=int(pitch),
                start=float(start_idx) * sec_per_8th,
                end=float(end_idx) * sec_per_8th,
            )
        )
    pm.instruments.append(inst)
    pm.write(mid_path)


def generated_to_xml_mid_wav(
    generated: List[Tuple[int, int, int]],
    stem: str,
    *,
    tempo_bpm: int = TEMPO_BPM,
) -> dict:
    xml_path = os.path.join(FINAL_DIR, f"{stem}.musicxml")
    mid_path = os.path.join(FINAL_DIR, f"{stem}.mid")
    wav_path = os.path.join(FINAL_DIR, f"{stem}.wav")

    score = notes_to_xml([generated], tempo_bpm=tempo_bpm, file_name=stem, output_dir=FINAL_DIR)
    if score is None:
        raise RuntimeError("MusicXML 저장 실패: music21 확인 필요")

    render_mode = "musicxml_to_wav_stereo"
    fallback_reason = None
    try:
        score.write("midi", fp=mid_path)
        duration = render_midi_to_wav_stereo(mid_path, wav_path)
    except Exception as e:
        fallback_reason = f"{type(e).__name__}: {e}"
        render_mode = "fallback_pretty_midi_to_wav_stereo"
        write_pretty_midi(generated, mid_path, tempo_bpm=tempo_bpm)
        duration = render_midi_to_wav_stereo(mid_path, wav_path)

    return {
        "xml": xml_path,
        "mid": mid_path,
        "wav": wav_path,
        "duration_s": round(float(duration), 3),
        "render_mode": render_mode,
        "fallback_reason": fallback_reason,
    }


def run_algo1_best(
    data: dict,
    overlap_values: np.ndarray,
    cycle_labeled: Dict,
    *,
    n_trials: int,
    seed_base: int,
    min_onset_gap: int,
) -> dict:
    trials = []
    best = {
        "seed": None,
        "js": float("inf"),
        "generated": None,
        "n_notes": 0,
    }

    for i in range(n_trials):
        seed = seed_base + i
        set_all_seeds(seed)
        pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
        manager = CycleSetManager(cycle_labeled)
        generated = algorithm1_optimized(
            pool,
            suite.INST_CHORD_HEIGHTS,
            overlap_values,
            manager,
            max_resample=50,
            verbose=False,
            min_onset_gap=min_onset_gap,
        )
        metrics = evaluate_generation(
            generated,
            [data["inst1_real"], data["inst2_real"]],
            data["notes_label"],
            name="",
        )
        js = float(metrics["js_divergence"])
        trials.append(
            {
                "seed": int(seed),
                "js": js,
                "n_notes": int(len(generated)),
            }
        )
        print(f"  seed={seed}  JS={js:.6f}  notes={len(generated)}")
        if js < best["js"]:
            best = {
                "seed": int(seed),
                "js": js,
                "generated": generated,
                "n_notes": int(len(generated)),
            }

    if best["generated"] is None:
        raise RuntimeError("Algo1 생성 실패: 유효 trial이 없습니다.")

    return {"best": best, "trials": trials}


def run_fc_cont_best(data: dict, cont_overlap: np.ndarray, seed: int) -> dict:
    if torch is None:
        raise RuntimeError("torch가 설치되지 않아 Algo2 FC를 실행할 수 없습니다.")

    n_notes = len(data["notes_label"])
    num_cycles = cont_overlap.shape[1]
    X, y = prepare_training_data(
        cont_overlap,
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"],
        data["T"],
        n_notes,
    )
    X_tr, X_va, y_tr, y_va = train_test_split(X, y, test_size=0.2, random_state=42)

    set_all_seeds(seed)
    model = MusicGeneratorFC(
        num_cycles=num_cycles,
        num_notes=n_notes,
        hidden_dim=128,
        dropout=0.3,
    )
    history = train_model(
        model,
        X_tr,
        y_tr,
        X_va,
        y_va,
        epochs=200,
        lr=0.001,
        batch_size=32,
        model_type="fc",
        seq_len=data["T"],
    )
    generated = generate_from_model(
        model,
        cont_overlap,
        data["notes_label"],
        model_type="fc",
        adaptive_threshold=True,
        min_onset_gap=0,
    )
    metrics = evaluate_generation(
        generated,
        [data["inst1_real"], data["inst2_real"]],
        data["notes_label"],
        name="",
    )
    return {
        "seed": int(seed),
        "js": float(metrics["js_divergence"]),
        "n_notes": int(len(generated)),
        "val_loss_last": float(history[-1]["val_loss"]) if history else None,
        "generated": generated,
    }


def build_legacy_complex_overlap() -> Tuple[np.ndarray, Dict]:
    cfg = PipelineConfig()
    cfg.metric.metric = "tonnetz"
    cfg.metric.alpha = float(LEGACY_COMPLEX_ALPHA)
    cfg.metric.octave_weight = float(LEGACY_COMPLEX_OW)
    cfg.metric.duration_weight = float(LEGACY_COMPLEX_DW)
    cfg.min_onset_gap = 0

    p = TDAMusicPipeline(cfg)
    p.run_preprocessing()
    p.run_homology_search(
        search_type="complex",
        lag=1,
        dimension=1,
        rate_t=LEGACY_COMPLEX_RATE_T,
        rate_s=LEGACY_COMPLEX_RC,
    )
    p.run_overlap_construction(persistence_key="h1_complex_lag1")

    cycle_labeled = p._cache["cycle_labeled"]
    note_time_df = p._cache["note_time_df"]
    cont_act = build_activation_matrix(note_time_df, cycle_labeled, continuous=True).values.astype(np.float32)

    complex_json = load_json("complex_percycle_n20_results.json")
    taus = complex_json["results"]["exp_B_extended"]["best_taus"]
    overlap = make_percycle_overlap(cont_act, taus)
    return overlap, cycle_labeled


def render_original_wav() -> dict:
    wav_path = os.path.join(FINAL_DIR, "hibari_original.wav")
    duration = render_midi_to_wav_stereo(HIBARI_MID, wav_path)
    return {
        "wav": wav_path,
        "duration_s": round(float(duration), 3),
        "render_mode": "midi_to_wav_stereo",
    }


def write_readme(meta: dict) -> str:
    out_path = os.path.join(FINAL_DIR, "README.md")
    lines = []
    lines.append("# Session C Final WAV Metadata")
    lines.append("")
    lines.append(f"- 생성 시각: {meta.get('generated_at')}")
    lines.append("- 출력 폴더: `tda_pipeline/output/final/`")
    lines.append("- 렌더링: UprightPiano SF2, 44.1kHz, 16-bit stereo, sustain+reverb+chorus")
    lines.append("")

    entries = meta.get("entries", [])
    for i, e in enumerate(entries, start=1):
        lines.append(f"## {i}. {e['file']}")
        lines.append(f"- 목적: {e.get('purpose', '-')}")
        lines.append(f"- JS (ref): {e.get('js_ref', '-')}")
        lines.append(f"- JS (run): {e.get('js_run', '-')}")
        lines.append(f"- seed: {e.get('seed', '-')}")
        lines.append(f"- min_onset_gap: {e.get('min_onset_gap', '-')}")
        lines.append(f"- 설정: {e.get('config', '-')}")
        lines.append(f"- render_mode: {e.get('render_mode', '-')}")
        if e.get("fallback_reason"):
            lines.append(f"- fallback_reason: {e['fallback_reason']}")
        lines.append(f"- duration_s: {e.get('duration_s', '-')}")
        lines.append(f"- musicxml: {e.get('xml', '-')}")
        lines.append(f"- midi: {e.get('mid', '-')}")
        lines.append(f"- wav: {e.get('wav', '-')}")
        lines.append(f"- generated_at: {e.get('generated_at', '-')}")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


def main() -> None:
    os.chdir(BASE_DIR)
    ensure_dirs()
    print("=" * 72)
    print("Session C Final WAV 생성 시작")
    print("=" * 72)

    percycle = load_json("percycle_tau_dft_gap0_results.json")
    soft = load_json("soft_activation_dft_gap0_results.json")

    data = suite.setup_hibari()

    # DFT overlap bundle (gap0 기준)
    dft_bundle = suite.build_overlap_bundle(
        data,
        "dft",
        alpha=DEFAULT_ALPHA,
        octave_weight=DEFAULT_OW,
        duration_weight=DEFAULT_DW,
        use_decayed=False,
    )
    cycle_dft = dft_bundle["cycle_labeled"]
    ov_dft_binary = dft_bundle["overlap_binary"].values.astype(np.float32)
    ov_dft_cont = dft_bundle["activation_continuous"].values.astype(np.float32)
    ov_dft_percycle = make_percycle_overlap(ov_dft_cont, percycle["per_cycle_tau"]["best_taus"])

    entries = []

    # 1) gap0 dft algo1 final
    print("\n[1/5] DFT gap0 Algo1 final")
    a1_gap0 = run_algo1_best(
        data,
        ov_dft_percycle,
        cycle_dft,
        n_trials=5,
        seed_base=9000,
        min_onset_gap=0,
    )
    art_gap0 = generated_to_xml_mid_wav(
        a1_gap0["best"]["generated"],
        "hibari_dft_gap0_algo1_final",
        tempo_bpm=TEMPO_BPM,
    )
    entries.append(
        {
            "file": "hibari_dft_gap0_algo1_final.wav",
            "purpose": "DFT + gap0 + per-cycle tau (Algo1)",
            "js_ref": f"{percycle['per_cycle_tau']['js_divergence']['mean']:.8f}",
            "js_run": f"{a1_gap0['best']['js']:.8f}",
            "seed": a1_gap0["best"]["seed"],
            "min_onset_gap": 0,
            "config": "metric=dft, alpha=0.5, ow=0.3, dw=1.0, overlap=continuous->per-cycle tau",
            "generated_at": now_iso(),
            **art_gap0,
        }
    )

    # 2) gap0 dft algo2 fc continuous final
    print("\n[2/5] DFT gap0 Algo2 FC continuous final")
    fc_trials = soft["models"]["FC"]["continuous"]["trials"]
    best_fc_trial = min(fc_trials, key=lambda t: float(t["js"]))
    fc_seed = int(best_fc_trial["seed"])
    fc_res = run_fc_cont_best(data, ov_dft_cont, seed=fc_seed)
    art_fc = generated_to_xml_mid_wav(
        fc_res["generated"],
        "hibari_dft_gap0_algo2_fc_cont_final",
        tempo_bpm=TEMPO_BPM,
    )
    entries.append(
        {
            "file": "hibari_dft_gap0_algo2_fc_cont_final.wav",
            "purpose": "DFT + gap0 + FC continuous (Algo2)",
            "js_ref": f"{soft['models']['FC']['continuous']['js_mean']:.8f}",
            "js_run": f"{fc_res['js']:.8f}",
            "seed": fc_seed,
            "min_onset_gap": 0,
            "config": "metric=dft, alpha=0.5, ow=0.3, dw=1.0, FC(hidden=128,dropout=0.3,epochs=200)",
            "generated_at": now_iso(),
            **art_fc,
        }
    )

    # 3) original
    print("\n[3/5] Original hibari")
    art_orig = render_original_wav()
    entries.append(
        {
            "file": "hibari_original.wav",
            "purpose": "원곡 비교 기준",
            "js_ref": "-",
            "js_run": "-",
            "seed": "-",
            "min_onset_gap": "-",
            "config": "original midi render",
            "generated_at": now_iso(),
            "xml": "-",
            "mid": HIBARI_MID,
            **art_orig,
            "fallback_reason": None,
        }
    )

    # 4) gap3 legacy algo1
    print("\n[4/5] DFT gap3 legacy Algo1")
    a1_gap3 = run_algo1_best(
        data,
        ov_dft_binary,
        cycle_dft,
        n_trials=5,
        seed_base=9100,
        min_onset_gap=3,
    )
    art_gap3 = generated_to_xml_mid_wav(
        a1_gap3["best"]["generated"],
        "hibari_dft_gap3_algo1_legacy",
        tempo_bpm=TEMPO_BPM,
    )
    entries.append(
        {
            "file": "hibari_dft_gap3_algo1_legacy.wav",
            "purpose": "gap=3 레거시 비교",
            "js_ref": "-",
            "js_run": f"{a1_gap3['best']['js']:.8f}",
            "seed": a1_gap3["best"]["seed"],
            "min_onset_gap": 3,
            "config": "metric=dft, alpha=0.5, ow=0.3, dw=1.0, overlap=binary",
            "generated_at": now_iso(),
            **art_gap3,
        }
    )

    # 5) tonnetz complex legacy algo1
    print("\n[5/5] Tonnetz complex legacy Algo1")
    ov_complex, cycle_complex = build_legacy_complex_overlap()
    a1_complex = run_algo1_best(
        data,
        ov_complex,
        cycle_complex,
        n_trials=5,
        seed_base=9200,
        min_onset_gap=0,
    )
    art_complex = generated_to_xml_mid_wav(
        a1_complex["best"]["generated"],
        "hibari_tonnetz_complex_legacy",
        tempo_bpm=TEMPO_BPM,
    )
    entries.append(
        {
            "file": "hibari_tonnetz_complex_legacy.wav",
            "purpose": "Tonnetz complex 레거시 비교",
            "js_ref": "0.0183 (complex_percycle_n20 exp_B_extended)",
            "js_run": f"{a1_complex['best']['js']:.8f}",
            "seed": a1_complex["best"]["seed"],
            "min_onset_gap": 0,
            "config": "metric=tonnetz, alpha=0.25, ow=0.0, dw=0.3, complex(rc=0.1), per-cycle tau",
            "generated_at": now_iso(),
            **art_complex,
        }
    )

    meta = {
        "generated_at": now_iso(),
        "entries": entries,
    }
    meta_json = os.path.join(FINAL_DIR, "final_wav_metadata.json")
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    readme = write_readme(meta)

    print("\n" + "=" * 72)
    print("완료")
    print("=" * 72)
    for e in entries:
        print(f"- {e['wav']}  (JS_run={e['js_run']})")
    print(f"- metadata: {meta_json}")
    print(f"- README: {readme}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n[ERROR]", exc)
        traceback.print_exc()
        raise
