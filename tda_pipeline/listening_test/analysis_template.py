"""
Task 45 - Listening test analysis template.

입력:
- response bundle JSON (response_schema.json 구조)

출력:
- analysis_report.md
- mos_summary.csv
- group_mannwhitney.csv
- pairwise_wilcoxon.csv
- js_similarity_spearman.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, Iterable, List, Optional, Tuple

from scipy.stats import mannwhitneyu, spearmanr, wilcoxon


JS_REFERENCE = {
    "B": 0.01489,
    "C": 0.00035,
    "D": 0.096786,
    "E": 0.353591,
    "F": 0.307744,
    "H": 0.0183,
}

CORE_PAIRS = ("B_vs_C", "D_vs_E", "B_vs_G")
METRICS = ("similarity", "naturalness", "preference")


@dataclass
class RatingRow:
    participant_id: str
    listener_group: str
    stimulus_code: str
    similarity: int
    naturalness: int
    preference: int


@dataclass
class PairChoice:
    participant_id: str
    listener_group: str
    pair_id: str
    left: str
    right: str
    preferred: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listening test statistics template")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="응답 JSON 파일 경로 (response_schema.json 구조)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output/listening_test/analysis"),
        help="분석 결과 출력 폴더",
    )
    return parser.parse_args()


def _safe_mean(values: List[float]) -> Optional[float]:
    return None if not values else float(mean(values))


def _safe_std(values: List[float]) -> Optional[float]:
    if len(values) <= 1:
        return 0.0 if values else None
    return float(stdev(values))


def load_bundle(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or "responses" not in payload:
        raise ValueError("입력 JSON은 { ..., 'responses': [...] } 구조여야 합니다.")
    if not isinstance(payload["responses"], list):
        raise ValueError("'responses'는 배열이어야 합니다.")
    return payload


def extract_rows(bundle: dict) -> Tuple[List[RatingRow], List[PairChoice]]:
    ratings: List[RatingRow] = []
    pairs: List[PairChoice] = []

    for resp in bundle.get("responses", []):
        if not resp.get("consent", False):
            continue
        pid = str(resp.get("participant_id", "")).strip()
        grp = str(resp.get("listener_group", "unknown")).strip().lower()
        for item in resp.get("stimuli_ratings", []):
            ratings.append(
                RatingRow(
                    participant_id=pid,
                    listener_group=grp,
                    stimulus_code=str(item.get("stimulus_code", "")).strip().upper(),
                    similarity=int(item.get("similarity", 0)),
                    naturalness=int(item.get("naturalness", 0)),
                    preference=int(item.get("preference", 0)),
                )
            )
        for item in resp.get("pairwise_choices", []):
            pairs.append(
                PairChoice(
                    participant_id=pid,
                    listener_group=grp,
                    pair_id=str(item.get("pair_id", "")).strip(),
                    left=str(item.get("left", "")).strip().upper(),
                    right=str(item.get("right", "")).strip().upper(),
                    preferred=str(item.get("preferred", "")).strip().upper(),
                )
            )
    return ratings, pairs


def summarize_mos(rows: List[RatingRow]) -> List[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r.stimulus_code, "all")].append(r)
        groups[(r.stimulus_code, r.listener_group)].append(r)

    out: List[dict] = []
    for (stimulus, group), items in sorted(groups.items()):
        sim = [x.similarity for x in items]
        nat = [x.naturalness for x in items]
        pref = [x.preference for x in items]
        out.append(
            {
                "stimulus_code": stimulus,
                "listener_group": group,
                "n": len(items),
                "similarity_mean": _safe_mean(sim),
                "similarity_std": _safe_std(sim),
                "naturalness_mean": _safe_mean(nat),
                "naturalness_std": _safe_std(nat),
                "preference_mean": _safe_mean(pref),
                "preference_std": _safe_std(pref),
            }
        )
    return out


def compute_spearman_js_similarity(mos_rows: List[dict]) -> dict:
    xs: List[float] = []
    ys: List[float] = []
    for row in mos_rows:
        code = row["stimulus_code"]
        if row["listener_group"] != "all":
            continue
        if code not in JS_REFERENCE:
            continue
        sim = row.get("similarity_mean")
        if sim is None:
            continue
        xs.append(JS_REFERENCE[code])
        ys.append(float(sim))

    if len(xs) < 3:
        return {
            "n": len(xs),
            "rho": None,
            "p_value": None,
            "note": "유효 표본 부족 (최소 3개 자극 필요)",
        }
    rho, pval = spearmanr(xs, ys)
    return {"n": len(xs), "rho": float(rho), "p_value": float(pval)}


def run_mann_whitney(rows: List[RatingRow]) -> List[dict]:
    by_stimulus = defaultdict(lambda: {"expert": [], "general": []})
    for r in rows:
        if r.listener_group not in ("expert", "general"):
            continue
        by_stimulus[r.stimulus_code][r.listener_group].append(r.similarity)

    results: List[dict] = []
    for code in sorted(by_stimulus.keys()):
        expert = by_stimulus[code]["expert"]
        general = by_stimulus[code]["general"]
        row = {
            "stimulus_code": code,
            "n_expert": len(expert),
            "n_general": len(general),
            "u_stat": None,
            "p_value": None,
        }
        if len(expert) >= 3 and len(general) >= 3:
            u, p = mannwhitneyu(expert, general, alternative="two-sided")
            row["u_stat"] = float(u)
            row["p_value"] = float(p)
        results.append(row)
    return results


def run_wilcoxon_pairs(choices: List[PairChoice]) -> List[dict]:
    bucket = defaultdict(list)
    for c in choices:
        bucket[c.pair_id].append(c)

    results: List[dict] = []
    for pair_id, items in sorted(bucket.items()):
        if pair_id not in CORE_PAIRS:
            continue
        encoded: List[float] = []
        left, right = None, None
        for item in items:
            left = item.left
            right = item.right
            if item.preferred == item.right:
                encoded.append(1.0)
            elif item.preferred == item.left:
                encoded.append(0.0)
        centered = [x - 0.5 for x in encoded if x in (0.0, 1.0)]
        row = {
            "pair_id": pair_id,
            "left": left,
            "right": right,
            "n": len(centered),
            "w_stat": None,
            "p_value": None,
            "right_preferred_ratio": _safe_mean(encoded),
        }
        # zeros are dropped by wilcoxon by default; min 6 gives slightly stable estimate
        non_zero = [x for x in centered if x != 0]
        if len(non_zero) >= 6:
            w, p = wilcoxon(centered, zero_method="wilcox", alternative="two-sided")
            row["w_stat"] = float(w)
            row["p_value"] = float(p)
        results.append(row)
    return results


def save_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def format_float(value: Optional[float], ndigits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{ndigits}f}"


def write_report(
    out_path: Path,
    *,
    bundle: dict,
    n_participants: int,
    n_rating_rows: int,
    mos_rows: List[dict],
    spearman_row: dict,
    mann_rows: List[dict],
    wilcoxon_rows: List[dict],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mos_all = [r for r in mos_rows if r["listener_group"] == "all"]
    lines: List[str] = []
    lines.append("# Listening Test Analysis Report")
    lines.append("")
    lines.append(f"- study_id: `{bundle.get('study_id', '-')}`")
    lines.append(f"- created_at: `{bundle.get('created_at', '-')}`")
    lines.append(f"- participants(consented): **{n_participants}**")
    lines.append(f"- rating rows: **{n_rating_rows}**")
    lines.append("")
    lines.append("## 1) MOS 요약 (전체)")
    lines.append("")
    lines.append("| Stimulus | n | Similarity | Naturalness | Preference |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in sorted(mos_all, key=lambda x: x["stimulus_code"]):
        lines.append(
            "| {s} | {n} | {sim} ± {sim_sd} | {nat} ± {nat_sd} | {pref} ± {pref_sd} |".format(
                s=row["stimulus_code"],
                n=row["n"],
                sim=format_float(row["similarity_mean"]),
                sim_sd=format_float(row["similarity_std"]),
                nat=format_float(row["naturalness_mean"]),
                nat_sd=format_float(row["naturalness_std"]),
                pref=format_float(row["preference_mean"]),
                pref_sd=format_float(row["preference_std"]),
            )
        )
    lines.append("")
    lines.append("## 2) JS vs Similarity 상관 (Spearman)")
    lines.append("")
    lines.append(
        f"- n={spearman_row.get('n')} | rho={format_float(spearman_row.get('rho'))} | p={format_float(spearman_row.get('p_value'))}"
    )
    if spearman_row.get("note"):
        lines.append(f"- note: {spearman_row['note']}")
    lines.append("")
    lines.append("## 3) 그룹 차이 (Mann-Whitney U, Similarity)")
    lines.append("")
    lines.append("| Stimulus | n_expert | n_general | U | p |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in mann_rows:
        lines.append(
            f"| {row['stimulus_code']} | {row['n_expert']} | {row['n_general']} | {format_float(row['u_stat'])} | {format_float(row['p_value'])} |"
        )
    lines.append("")
    lines.append("## 4) 쌍 비교 (Wilcoxon)")
    lines.append("")
    lines.append("| Pair | n | Right-preferred ratio | W | p |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in wilcoxon_rows:
        lines.append(
            f"| {row['pair_id']} ({row['left']} vs {row['right']}) | {row['n']} | {format_float(row['right_preferred_ratio'])} | {format_float(row['w_stat'])} | {format_float(row['p_value'])} |"
        )
    lines.append("")
    lines.append("## 5) 메모")
    lines.append("")
    lines.append("- 이 템플릿은 파일럿/본실험 모두 같은 포맷으로 재사용 가능합니다.")
    lines.append("- 자유서술(comment)은 별도 thematic coding 테이블로 후속 정리하세요.")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    bundle = load_bundle(args.input)
    rating_rows, pair_rows = extract_rows(bundle)

    participants = {r.participant_id for r in rating_rows}
    mos_rows = summarize_mos(rating_rows)
    spearman_row = compute_spearman_js_similarity(mos_rows)
    mann_rows = run_mann_whitney(rating_rows)
    wilcoxon_rows = run_wilcoxon_pairs(pair_rows)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    save_csv(out_dir / "mos_summary.csv", mos_rows)
    save_csv(out_dir / "group_mannwhitney.csv", mann_rows)
    save_csv(out_dir / "pairwise_wilcoxon.csv", wilcoxon_rows)

    with (out_dir / "js_similarity_spearman.json").open("w", encoding="utf-8") as f:
        json.dump(spearman_row, f, indent=2, ensure_ascii=False)

    write_report(
        out_dir / "analysis_report.md",
        bundle=bundle,
        n_participants=len(participants),
        n_rating_rows=len(rating_rows),
        mos_rows=mos_rows,
        spearman_row=spearman_row,
        mann_rows=mann_rows,
        wilcoxon_rows=wilcoxon_rows,
    )

    print("=" * 72)
    print("Listening test analysis finished")
    print("=" * 72)
    print(f"participants: {len(participants)}")
    print(f"rating rows: {len(rating_rows)}")
    print(f"output dir: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
