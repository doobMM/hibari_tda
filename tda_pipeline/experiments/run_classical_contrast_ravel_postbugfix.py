"""
§5.2 Ravel Pavane 독립 재실험 (post-bugfix)

저장:
  docs/step3_data/classical_contrast_ravel_postbugfix_results.json
"""

from __future__ import annotations

import json
import os

from config import PipelineConfig
from run_any_track import ALPHA, METRICS, N_ALGO1, process_one
from utils.result_meta import build_result_header


TRACK_NAME = "ravel_pavane"
MIDI_FILE = "maurice-ravel-pavane-pour-une-infante-defunte-m-19.mid"
OUT_JSON = os.path.join(
    "docs", "step3_data", "classical_contrast_ravel_postbugfix_results.json"
)


def main() -> None:
    if not os.path.exists(MIDI_FILE):
        raise FileNotFoundError(f"MIDI 파일 없음: {MIDI_FILE}")

    result = process_one(TRACK_NAME, MIDI_FILE)

    cfg = PipelineConfig()
    cfg.metric.metric = "multi"
    cfg.metric.alpha = float(ALPHA)
    cfg.min_onset_gap = 0
    cfg.post_bugfix = True

    header = build_result_header(
        cfg,
        script_name=__file__,
        n_repeats=N_ALGO1,
        extra={
            "song": TRACK_NAME,
            "midi_file": MIDI_FILE,
            "metrics": METRICS,
            "runner": "run_any_track.process_one",
            "experiment": "section_5_2_classical_contrast_independent_rerun",
        },
    )

    payload = {
        **header,
        "result": result,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[saved] {OUT_JSON}")


if __name__ == "__main__":
    main()

