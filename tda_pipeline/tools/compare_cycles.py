"""
compare_cycles.py — DFT vs Tonnetz cycle 구성 비교

각 거리 함수의 PH cycle 이 어떤 note 들로 구성되는지 비교한다.
- cache/metric_tonnetz.pkl, cache/metric_dft.pkl 의 cycle_labeled 로드
- preprocessing 에서 notes_label (label → (pitch, dur)) 복원
- 각 cycle 을 pitch 집합으로 변환
- DFT cycle 별로 가장 유사한 Tonnetz cycle (Jaccard) 표시

출력:
  1) 콘솔에 요약 표
  2) docs/cycle_compare.md 마크다운 (전체 cycle 목록)
  3) docs/cycle_compare.json (raw data)
"""
# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import pickle, json
from pathlib import Path
import pretty_midi as pm

from pipeline import TDAMusicPipeline
from config import PipelineConfig

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DOCS = ROOT / "docs"


def midi_name(p: int) -> str:
    return pm.note_number_to_name(p)


def load(metric: str) -> dict:
    with open(CACHE / f"metric_{metric}.pkl", "rb") as f:
        return pickle.load(f)


def build_inv_label() -> dict[int, tuple[int, int]]:
    """label (1-indexed) → (pitch, dur)"""
    cfg = PipelineConfig()
    pipe = TDAMusicPipeline(cfg)
    pipe.run_preprocessing()
    nl = pipe._cache["notes_label"]
    return {v: k for k, v in nl.items()}


def cycle_to_pitches(cycle: tuple[int, ...], inv_label: dict) -> list[int]:
    """cycle indices (0-indexed) → 정렬된 unique pitch 리스트"""
    pitches = set()
    for idx in cycle:
        label = idx + 1  # 0-base index → 1-base label
        if label in inv_label:
            pitches.add(inv_label[label][0])
    return sorted(pitches)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def main():
    print("=" * 70)
    print("DFT vs Tonnetz cycle 비교 (hibari)")
    print("=" * 70)

    inv_label = build_inv_label()
    print(f"\nnotes_label: 총 {len(inv_label)}종 (label 1 ~ {max(inv_label)})")

    # Note inventory
    print("\n[Note inventory]")
    print(f"{'label':>5}  {'pitch':>5}  {'dur':>3}  name")
    for lbl in sorted(inv_label):
        p, d = inv_label[lbl]
        print(f"{lbl:>5}  {p:>5}  {d:>3}  {midi_name(p)}")

    # Load
    t = load("tonnetz")
    d = load("dft")
    print(f"\n[Cycle counts]  Tonnetz={len(t['cycle_labeled'])}  DFT={len(d['cycle_labeled'])}")

    # Convert cycles → pitch sets
    tonnetz_cycles = []
    for cid, idxs in t["cycle_labeled"].items():
        pitches = cycle_to_pitches(idxs, inv_label)
        tonnetz_cycles.append({
            "cycle_id": cid,
            "indices": list(idxs),
            "n_indices": len(idxs),
            "pitches": pitches,
            "pitch_names": [midi_name(p) for p in pitches],
            "n_pitches": len(pitches),
        })
    dft_cycles = []
    for cid, idxs in d["cycle_labeled"].items():
        pitches = cycle_to_pitches(idxs, inv_label)
        dft_cycles.append({
            "cycle_id": cid,
            "indices": list(idxs),
            "n_indices": len(idxs),
            "pitches": pitches,
            "pitch_names": [midi_name(p) for p in pitches],
            "n_pitches": len(pitches),
        })

    # Per-DFT-cycle: nearest Tonnetz cycle by Jaccard on pitch sets
    print("\n[DFT cycle → 가장 유사한 Tonnetz cycle (Jaccard pitch overlap)]")
    print(f"{'DFT':>4}  {'#p':>3}  pitches              {'best Tn':>7}  J     공통 pitches")
    for dc in dft_cycles:
        d_set = set(dc["pitches"])
        best_j = -1.0
        best_tc = None
        for tc in tonnetz_cycles:
            j = jaccard(d_set, set(tc["pitches"]))
            if j > best_j:
                best_j = j
                best_tc = tc
        common = sorted(d_set & set(best_tc["pitches"]))
        common_names = [midi_name(p) for p in common]
        print(f"{dc['cycle_id']:>4}  {dc['n_pitches']:>3}  {','.join(dc['pitch_names']):<20}  "
              f"{best_tc['cycle_id']:>7}  {best_j:.2f}  {','.join(common_names)}")

    # Summary stats
    print("\n[Summary]")
    print(f"  Tonnetz cycle 평균 길이 (indices): {sum(c['n_indices'] for c in tonnetz_cycles)/len(tonnetz_cycles):.2f}")
    print(f"  DFT     cycle 평균 길이 (indices): {sum(c['n_indices'] for c in dft_cycles)/len(dft_cycles):.2f}")
    print(f"  Tonnetz cycle 평균 unique pitch:   {sum(c['n_pitches'] for c in tonnetz_cycles)/len(tonnetz_cycles):.2f}")
    print(f"  DFT     cycle 평균 unique pitch:   {sum(c['n_pitches'] for c in dft_cycles)/len(dft_cycles):.2f}")

    # 어떤 note 가 cycle 에 자주 등장하는가
    from collections import Counter
    t_pitch_freq = Counter(p for c in tonnetz_cycles for p in c["pitches"])
    d_pitch_freq = Counter(p for c in dft_cycles for p in c["pitches"])
    all_pitches = sorted(set(t_pitch_freq) | set(d_pitch_freq))
    print(f"\n[Pitch 별 cycle 등장 횟수]")
    print(f"{'pitch':>5}  {'name':>4}  {'Tn(/47)':>8}  {'DFT(/17)':>9}")
    for p in all_pitches:
        print(f"{p:>5}  {midi_name(p):>4}  {t_pitch_freq[p]:>8}  {d_pitch_freq[p]:>9}")

    # Save JSON + Markdown
    DOCS.mkdir(exist_ok=True)
    out_json = {
        "notes_label": {str(lbl): {"pitch": p, "dur": d, "name": midi_name(p)} for lbl, (p, d) in inv_label.items()},
        "tonnetz_cycles": tonnetz_cycles,
        "dft_cycles": dft_cycles,
        "tonnetz_pitch_freq": dict(t_pitch_freq),
        "dft_pitch_freq": dict(d_pitch_freq),
    }
    (DOCS / "cycle_compare.json").write_text(json.dumps(out_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[saved] docs/cycle_compare.json")

    # Markdown
    md = ["# DFT vs Tonnetz cycle 비교 (hibari)\n",
          f"생성: `tools/compare_cycles.py`  |  notes 23종, Tonnetz {len(tonnetz_cycles)} cycles, DFT {len(dft_cycles)} cycles\n"]
    md.append("## Note inventory\n")
    md.append("| label | pitch | dur | name |\n|---|---|---|---|")
    for lbl in sorted(inv_label):
        p, dur = inv_label[lbl]
        md.append(f"| {lbl} | {p} | {dur} | {midi_name(p)} |")
    md.append("\n## Tonnetz cycles (47개)\n")
    md.append("| id | #idx | #pitch | pitch names |\n|---|---|---|---|")
    for c in tonnetz_cycles:
        md.append(f"| {c['cycle_id']} | {c['n_indices']} | {c['n_pitches']} | {', '.join(c['pitch_names'])} |")
    md.append("\n## DFT cycles (17개)\n")
    md.append("| id | #idx | #pitch | pitch names |\n|---|---|---|---|")
    for c in dft_cycles:
        md.append(f"| {c['cycle_id']} | {c['n_indices']} | {c['n_pitches']} | {', '.join(c['pitch_names'])} |")
    md.append("\n## DFT cycle ↔ 가장 유사한 Tonnetz cycle\n")
    md.append("| DFT id | DFT pitches | best Tn id | Jaccard | 공통 pitches |\n|---|---|---|---|---|")
    for dc in dft_cycles:
        d_set = set(dc["pitches"])
        best_j, best_tc = -1, None
        for tc in tonnetz_cycles:
            j = jaccard(d_set, set(tc["pitches"]))
            if j > best_j:
                best_j, best_tc = j, tc
        common = sorted(d_set & set(best_tc["pitches"]))
        md.append(f"| {dc['cycle_id']} | {', '.join(dc['pitch_names'])} | {best_tc['cycle_id']} | {best_j:.2f} | {', '.join(midi_name(p) for p in common)} |")
    (DOCS / "cycle_compare.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[saved] docs/cycle_compare.md")


if __name__ == "__main__":
    main()
