"""결과 JSON 헤더 표준화 유틸 (Task 2-3).

모든 run_*.py 스크립트에서 생성하는 JSON의 최상위에 공통 필드를 주입하기 위한
헬퍼. post-bugfix(2026-04-15 이후) 결과의 조건을 메타로 함께 기록해서
논문 검수 시 "어떤 조건에서 나온 수치?"를 코드 역추적 없이 확인 가능하게 함.

사용 예:

    from utils.result_meta import build_result_header
    from config import PipelineConfig

    cfg = PipelineConfig()
    header = build_result_header(cfg, script_name=__file__, n_repeats=20,
                                  extra={"search_type": "timeflow"})
    results = {**header, "data": [...]}
    json.dump(results, open(out_path, "w"))

설계 원칙
- 기존 JSON에 **소급 적용 금지**. 이 유틸 도입 이후 생성분에만 주입.
- 최상위 dict에 평탄하게 병합 (중첩 X) — grep으로 조건 필터링이 쉽도록.
"""
from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path
from typing import Any, Optional


def _git_commit_sha(repo_root: Optional[Path] = None) -> str:
    """현재 HEAD의 짧은 SHA를 반환 (git 없으면 "unknown")."""
    cwd = str(repo_root) if repo_root else None
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def build_result_header(
    config,  # PipelineConfig 또는 MetricConfig; duck-typed
    *,
    script_name: str,
    n_repeats: int,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """실험 결과 JSON용 표준 헤더 dict를 반환.

    필수 5필드 (metric, alpha, octave_weight, duration_weight, min_onset_gap)
    + 메타 5필드 (n_repeats, date, script, post_bugfix, commit_sha).

    Args:
        config: `PipelineConfig` (권장) 혹은 `MetricConfig` 객체.
                MetricConfig만 넘기면 min_onset_gap, post_bugfix는 기본값.
        script_name: `__file__` 권장 — 경로는 basename만 저장.
        n_repeats: 재실험 횟수.
        extra: 스크립트 고유 필드 (예: {"search_type": "complex", "r_c": 0.1}).
               표준 필드와 키가 겹치면 덮어씀.

    Returns:
        최상위에 직접 병합 가능한 dict.
    """
    metric = getattr(config, "metric", config)
    # PipelineConfig: config.metric.metric, config.min_onset_gap, config.post_bugfix
    # MetricConfig:   config.metric (str), min_onset_gap 없음

    if hasattr(metric, "metric"):  # nested (PipelineConfig case)
        mcfg = metric
        min_onset_gap = getattr(config, "min_onset_gap", 0)
        post_bugfix = bool(getattr(config, "post_bugfix", True))
    else:  # MetricConfig 직접 전달
        mcfg = config
        min_onset_gap = 0
        post_bugfix = True

    header = {
        "metric": getattr(mcfg, "metric", "unknown"),
        "alpha": float(getattr(mcfg, "alpha", 0.0)),
        "octave_weight": float(getattr(mcfg, "octave_weight", 0.3)),
        "duration_weight": float(getattr(mcfg, "duration_weight", 0.3)),
        "min_onset_gap": int(min_onset_gap),
        "n_repeats": int(n_repeats),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "script": os.path.basename(str(script_name)),
        "post_bugfix": post_bugfix,
        "commit_sha": _git_commit_sha(),
    }

    if extra:
        header.update(extra)

    return header
