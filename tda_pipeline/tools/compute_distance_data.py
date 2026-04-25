"""
compute_distance_data.py — note 거리행렬 + cycle 구성 + tightness JSON 추출

거리: tonnetz, dft, voice_leading (pure musical metrics)
cycle: cache/metric_*.pkl 의 cycle_labeled

산출:
  docs/cycle_distance_data.json
    {
      "notes": [{label, pitch, dur, name}, ...],
      "metrics": {
        "tonnetz":      {"distance": [[...]], "cycles": [...], "stats": {...}},
        "dft":          {"distance": [[...]], "cycles": [...], "stats": {...}},
        "voice_leading":{"distance": [[...]], "cycles": [...], "stats": {...}}
      }
    }

cycle 항목:
  {id, indices, n_indices, pitches, n_pitches, mean_intra_dist, tightness}
    tightness = mean_intra_dist / mean_global_dist
      (1.0 ≈ 무작위, < 1.0 = 가까운 note 묶음, > 1.0 = 멀리 떨어진 묶음)
"""
# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import pickle, json
from pathlib import Path
import numpy as np
import pretty_midi as pm

from pipeline import TDAMusicPipeline
from config import PipelineConfig
from musical_metrics import compute_note_distance_matrix

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)


def main():
    # 1. notes_label
    cfg = PipelineConfig()
    pipe = TDAMusicPipeline(cfg)
    pipe.run_preprocessing()
    nl = pipe._cache["notes_label"]   # {(pitch, dur): label} (1-indexed)
    inv = sorted(nl.items(), key=lambda x: x[1])
    notes = [
        {
            "label": lbl,
            "pitch": pd[0],
            "dur": pd[1],
            "name": pm.note_number_to_name(pd[0]),
            "display": f"{pm.note_number_to_name(pd[0])}({pd[1]})",
        }
        for pd, lbl in inv
    ]
    N = len(notes)
    print(f"notes_label: {N}종")

    out = {"notes": notes, "metrics": {}}

    METRICS = {
        "tonnetz": {"octave_weight": 0.3, "duration_weight": 1.0},
        "dft": {"octave_weight": 0.3, "duration_weight": 1.0},
        "voice_leading": {"duration_weight": 1.0},
    }

    for metric, kwargs in METRICS.items():
        print(f"\n[{metric}] computing distance matrix...")
        D = compute_note_distance_matrix(nl, metric=metric, **kwargs)
        # D is N x N, label-order (1-indexed → row/col 0..N-1 = label 1..N)

        # Global stats
        iu = np.triu_indices(N, k=1)
        d_off = D[iu]
        mean_global = float(d_off.mean())
        max_d = float(d_off.max())
        min_d = float(d_off.min())
        print(f"  range [{min_d:.3f}, {max_d:.3f}], mean {mean_global:.3f}")

        # Cycles from cache (cache uses 0-indexed, so label = idx+1)
        with open(CACHE / f"metric_{metric}.pkl", "rb") as f:
            c = pickle.load(f)
        cycles_raw = c["cycle_labeled"]

        cycles_out = []
        for cid, idxs in cycles_raw.items():
            # idxs are 0-indexed positions matching D rows (= label - 1)
            idxs = list(idxs)
            if len(idxs) < 2:
                mean_intra = 0.0
                tightness = 0.0
            else:
                pairs = []
                for i in range(len(idxs)):
                    for j in range(i + 1, len(idxs)):
                        pairs.append(D[idxs[i], idxs[j]])
                mean_intra = float(np.mean(pairs))
                tightness = mean_intra / mean_global if mean_global > 0 else 0.0

            pitches = sorted({notes[i]["pitch"] for i in idxs})
            cycles_out.append({
                "id": int(cid),
                "indices": idxs,
                "n_indices": len(idxs),
                "labels": [i + 1 for i in idxs],
                "pitches": pitches,
                "pitch_names": [pm.note_number_to_name(p) for p in pitches],
                "n_pitches": len(pitches),
                "mean_intra_dist": round(mean_intra, 4),
                "tightness": round(tightness, 4),
            })

        # Sort cycles by tightness ascending (most cohesive first)
        cycles_sorted = sorted(cycles_out, key=lambda c: c["tightness"])
        tight_summary = {
            "min_tightness": min(c["tightness"] for c in cycles_out if c["tightness"] > 0),
            "max_tightness": max(c["tightness"] for c in cycles_out),
            "median_tightness": float(np.median([c["tightness"] for c in cycles_out if c["tightness"] > 0])),
            "n_cycles_below_1.0": sum(1 for c in cycles_out if 0 < c["tightness"] < 1.0),
            "n_cycles_above_1.0": sum(1 for c in cycles_out if c["tightness"] >= 1.0),
        }
        print(f"  cycles: {len(cycles_out)}, tightness range [{tight_summary['min_tightness']:.2f}, {tight_summary['max_tightness']:.2f}], median {tight_summary['median_tightness']:.2f}")
        print(f"    {tight_summary['n_cycles_below_1.0']} cycles tight (< 1.0)  /  {tight_summary['n_cycles_above_1.0']} loose (>= 1.0)")

        out["metrics"][metric] = {
            "distance": D.round(4).tolist(),
            "cycles": cycles_sorted,
            "stats": {
                "mean_global_dist": round(mean_global, 4),
                "min_dist": round(min_d, 4),
                "max_dist": round(max_d, 4),
                **tight_summary,
            },
        }

    out_path = DOCS / "cycle_distance_data.json"
    out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n[saved] {out_path.relative_to(ROOT)}  ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
