"""
JSON 메타데이터 누락 감사 스크립트 (Task 1-3).

tda_pipeline/docs/step3_data/ 전체를 스캔하여, 최상위 dict에
{metric, alpha, octave_weight, duration_weight, min_onset_gap}
필드가 누락된 JSON 목록을 출력.

중첩 dict까지는 한 단계만 검사 (예: config 블록, meta 블록이 최상위 값의 dict이면 그 안도 체크).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = ["metric", "alpha", "octave_weight", "duration_weight", "min_onset_gap"]


def gather_top_keys(obj: Any) -> set[str]:
    """최상위 키 + 1-depth 하위 dict 키까지 합쳐서 반환."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys.update(obj.keys())
        for v in obj.values():
            if isinstance(v, dict):
                keys.update(v.keys())
    return keys


def audit(json_dir: Path) -> list[dict]:
    rows = []
    for p in sorted(json_dir.glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            rows.append({"file": p.name, "error": str(e), "missing": list(REQUIRED_FIELDS)})
            continue
        keys = gather_top_keys(obj)
        missing = [k for k in REQUIRED_FIELDS if k not in keys]
        rows.append({"file": p.name, "missing": missing, "present": [k for k in REQUIRED_FIELDS if k in keys]})
    return rows


def main():
    json_dir = Path(__file__).resolve().parent.parent / "docs" / "step3_data"
    if not json_dir.exists():
        print(f"[ERR] {json_dir} not found")
        sys.exit(1)
    rows = audit(json_dir)

    total = len(rows)
    incomplete = [r for r in rows if r.get("missing")]
    complete = [r for r in rows if not r.get("missing")]

    print(f"=== JSON meta audit: {json_dir} ===")
    print(f"total files: {total}")
    print(f"  fully-tagged (all 5 fields): {len(complete)}")
    print(f"  incomplete: {len(incomplete)}")
    print()

    print("--- incomplete files (missing fields) ---")
    for r in incomplete:
        print(f"  {r['file']}")
        if 'error' in r:
            print(f"    ERROR: {r['error']}")
        else:
            print(f"    missing: {r['missing']}")
            print(f"    present: {r['present']}")

    print()
    print("--- fully-tagged files ---")
    for r in complete:
        print(f"  {r['file']}")


if __name__ == "__main__":
    main()
