#!/usr/bin/env python3
"""gen_code_map.py — TDA Pipeline 코드 맵 HTML 생성기 (depth ≤ 3)

AST로 함수 정의·호출 관계를 추출, git log로 최근 수정 뱃지,
외부 라이브러리는 회색 박스로 표시한 Mermaid flowchart HTML을 생성.

Usage (C:\\WK14 루트에서):
    python tda_pipeline/tools/gen_code_map.py pipeline
    python tda_pipeline/tools/gen_code_map.py generation
    python tda_pipeline/tools/gen_code_map.py overlap
"""
import ast
import subprocess
import sys
import re
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
TDA  = ROOT / "tda_pipeline"
DOCS = TDA / "docs"

MODULE_FILES = {
    "pipeline":        TDA / "pipeline.py",
    "generation":      TDA / "generation.py",
    "overlap":         TDA / "overlap.py",
    "preprocessing":   TDA / "preprocessing.py",
    "weights":         TDA / "weights.py",
    "topology":        TDA / "topology.py",
    "musical_metrics": TDA / "musical_metrics.py",
}

LOCAL_MODULES = set(MODULE_FILES.keys()) | {
    "config", "eval_metrics", "cycle_selector",
    "temporal_reorder", "sequence_metrics", "note_reassign",
}

EXTERN_ALIASES = {"np": "numpy", "pd": "pandas", "plt": "matplotlib"}
EXTERN_LIBS    = {"numpy", "pandas", "torch", "music21", "pretty_midi",
                  "sklearn", "scipy", "matplotlib", "pickle", "os"}

MODULE_COLORS = {
    "preprocessing":   "#3a86ff",
    "weights":         "#06d6a0",
    "overlap":         "#8338ec",
    "generation":      "#f4511e",
    "topology":        "#f7b731",
    "musical_metrics": "#e76f51",
    "cycle_selector":  "#9b5de5",
    "temporal_reorder":"#b5838d",
    "config":          "#adb5bd",
    "external":        "#6c757d",
    "pipeline":        "#4361ee",
}

# pipeline.py 특화: 함수 → (색상, stage_key)
# stage_key는 서브그래프 ID와 표시 라벨에 사용 — 반드시 고유해야 함
STAGE_MAP = {
    "__init__":                    ("#adb5bd", "초기화"),
    "run_preprocessing":           ("#4361ee", "Stage_1"),
    "run_homology_search":         ("#06d6a0", "Stage_2"),
    "_search_timeflow":            ("#06d6a0", "Stage_2sub"),
    "_search_simul":               ("#06d6a0", "Stage_2sub"),
    "_search_complex":             ("#06d6a0", "Stage_2sub"),
    "_apply_metric":               ("#06d6a0", "Stage_2sub"),
    "run_overlap_construction":    ("#8338ec", "Stage_3"),
    "_build_note_time_df":         ("#8338ec", "Stage_3sub"),
    "_load_persistence_from_pickle":("#8338ec","Stage_3sub"),
    "run_cycle_selection":         ("#9b5de5", "Stage_3_5"),
    "run_temporal_reorder":        ("#b5838d", "Stage_3_5"),
    "run_generation_algo1":        ("#f4511e", "Stage_4"),
    "run_generation_algo2":        ("#f4511e", "Stage_4"),
    "save_cache":                  ("#f7b731", "캐시"),
    "load_cache":                  ("#f7b731", "캐시"),
}

# stage_key → 표시 라벨 (한국어/영어 혼합)
STAGE_LABELS = {
    "초기화":    "초기화",
    "Stage_1":   "Stage 1 — 전처리",
    "Stage_2":   "Stage 2 — Homology 탐색",
    "Stage_2sub":"Stage 2 — 내부 탐색기",
    "Stage_3":   "Stage 3 — 중첩행렬",
    "Stage_3sub":"Stage 3 — 내부 헬퍼",
    "Stage_3_5": "Stage 3.5 — 선택적",
    "Stage_4":   "Stage 4 — 음악 생성",
    "캐시":      "캐시 관리",
}

# pipeline.py 특화: 함수 → 호출하는 외부 모듈 함수 목록 (depth 2)
PIPELINE_EDGES: dict[str, list[tuple[str, list[str]]]] = {
    "run_preprocessing": [
        ("preprocessing", ["load_and_quantize", "analyze_midi", "split_instruments",
                           "group_notes_with_duration", "build_chord_labels",
                           "build_note_labels", "chord_to_note_labels",
                           "prepare_lag_sequences", "find_flexible_pitches"]),
    ],
    "run_homology_search": [
        ("topology",        ["generateBarcode"]),
        ("musical_metrics", ["compute_note_distance_matrix", "compute_multi_hybrid_distance"]),
    ],
    "_search_timeflow": [
        ("weights", ["compute_intra_weights", "compute_inter_weights_decayed",
                     "compute_distance_matrix", "compute_out_of_reach"]),
        ("topology", ["generateBarcode"]),
    ],
    "_search_simul": [
        ("weights", ["compute_simul_weights", "compute_distance_matrix"]),
        ("topology", ["generateBarcode"]),
    ],
    "_search_complex": [
        ("weights", ["compute_intra_weights", "compute_inter_weights_decayed",
                     "compute_simul_weights", "to_upper_triangular",
                     "refine_connectedness_fast", "symmetrize_upper_to_full",
                     "weight_to_distance"]),
        ("topology", ["generateBarcode"]),
    ],
    "_apply_metric": [
        ("musical_metrics", ["compute_note_distance_matrix", "compute_hybrid_distance",
                              "compute_multi_hybrid_distance"]),
    ],
    "run_overlap_construction": [
        ("overlap", ["label_cycles_from_persistence", "get_cycle_stats",
                     "build_activation_matrix", "build_overlap_matrix",
                     "build_overlap_matrix_percycle"]),
        ("preprocessing", ["simul_chord_lists", "simul_union_by_dict"]),
    ],
    "run_cycle_selection": [
        ("cycle_selector", ["CycleSubsetSelector"]),
    ],
    "run_temporal_reorder": [
        ("temporal_reorder", ["reorder_overlap_matrix"]),
    ],
    "run_generation_algo1": [
        ("generation", ["NodePool", "CycleSetManager",
                        "algorithm1_optimized", "notes_to_xml"]),
    ],
    "run_generation_algo2": [
        ("generation", ["prepare_training_data", "MusicGenerator", "train_model"]),
        ("external",   ["sklearn"]),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. AST 파싱
# ─────────────────────────────────────────────────────────────────────────────

def parse_functions(filepath: Path) -> dict[str, dict]:
    """함수/메서드 이름 → {doc, lineno, end_lineno, class_name} 딕셔너리 반환."""
    src = filepath.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(filepath))
    result = {}

    def _process(node, class_name=None):
        doc = ast.get_docstring(node) or ""
        first_line = doc.split("\n")[0].strip() if doc else f"{node.name}()"
        first_line = first_line[:90]
        end = getattr(node, "end_lineno", node.lineno)
        key = node.name
        result[key] = {
            "doc":        first_line,
            "lineno":     node.lineno,
            "end_lineno": end,
            "class":      class_name,
            "qual":       f"{class_name}.{node.name}" if class_name else node.name,
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _process(item, node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _process(node)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. 최근 수정 감지 (git log)
# ─────────────────────────────────────────────────────────────────────────────

def get_recent_funcs(filepath: Path, funcs: dict[str, dict], days: int = 30) -> set[str]:
    """최근 N일 내 수정된 함수 이름 세트 반환."""
    try:
        result = subprocess.run(
            ["git", "log", f"--since={days} days ago",
             "--unified=0", "--pretty=format:", "--", str(filepath)],
            capture_output=True, text=True, cwd=ROOT, timeout=15
        )
        changed_lines: set[int] = set()
        for line in result.stdout.splitlines():
            m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2) or "1")
                changed_lines.update(range(start, start + max(count, 1)))

        recent = set()
        for name, info in funcs.items():
            if any(info["lineno"] <= ln <= info["end_lineno"] for ln in changed_lines):
                recent.add(name)
        return recent
    except Exception:
        return set()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mermaid 다이어그램 빌드
# ─────────────────────────────────────────────────────────────────────────────

def _safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


def build_mermaid_pipeline(funcs: dict[str, dict],
                           recent: set[str]) -> tuple[str, dict[str, str]]:
    """pipeline.py 전용 Mermaid 다이어그램 반환 (diagram_str, tooltips)."""
    lines = ["flowchart TD"]
    tooltips: dict[str, str] = {}

    # ── 파이프라인 중앙 블록 ──────────────────────────────────────────────────
    lines.append('    subgraph PIPE["🔵 pipeline.py — TDAMusicPipeline"]')
    lines.append("    direction TB")

    stage_groups: dict[str, list[str]] = defaultdict(list)
    for name, info in funcs.items():
        _, stage_key = STAGE_MAP.get(name, ("#868e96", "기타"))
        stage_groups[stage_key].append(name)

    stage_order = ["초기화", "Stage_1", "Stage_2", "Stage_2sub",
                   "Stage_3", "Stage_3sub", "Stage_3_5", "Stage_4", "캐시", "기타"]
    for stage_key in stage_order:
        if stage_key not in stage_groups:
            continue
        display_label = STAGE_LABELS.get(stage_key, stage_key.replace("_", " "))
        lines.append(f'        subgraph SG_{stage_key}["{display_label}"]')
        for name in stage_groups[stage_key]:
            nid = _safe(name)
            badge = " 🔴" if name in recent else ""
            lines.append(f'            {nid}["{name}{badge}"]')
            tooltips[name] = funcs[name]["doc"]
        lines.append("        end")
    lines.append("    end")
    lines.append("")

    # ── 외부 모듈 서브그래프 ──────────────────────────────────────────────────
    # 사용된 모듈 수집
    used_modules: dict[str, list[str]] = defaultdict(list)
    for caller, mod_calls in PIPELINE_EDGES.items():
        for (mod, fns) in mod_calls:
            for fn in fns:
                if fn not in used_modules[mod]:
                    used_modules[mod].append(fn)

    for mod, fns in used_modules.items():
        color = MODULE_COLORS.get(mod, "#868e96")
        sg_id = f"SG_{mod.upper()}"
        if mod == "external":
            lines.append('    subgraph SG_EXTERNAL["📦 External Libraries"]')
        else:
            lines.append(f'    subgraph {sg_id}["{mod}.py"]')
        for fn in fns:
            nid = _safe(f"{mod}_{fn}")
            lines.append(f'        {nid}["{fn}"]:::mod_{mod}')
            tooltips[fn] = fn
        lines.append("    end")
        lines.append("")

    # ── 내부 파이프라인 흐름 엣지 ────────────────────────────────────────────
    lines.append("    %% ── 파이프라인 흐름 ──")
    flow = [
        ("run_preprocessing",      "run_homology_search"),
        ("run_homology_search",    "run_overlap_construction"),
        ("run_overlap_construction","run_generation_algo1"),
        ("run_homology_search",    "_search_timeflow"),
        ("run_homology_search",    "_search_simul"),
        ("run_homology_search",    "_search_complex"),
        ("_search_timeflow",       "_apply_metric"),
        ("_search_simul",          "_apply_metric"),
        ("_search_complex",        "_apply_metric"),
        ("run_overlap_construction","_build_note_time_df"),
        ("run_overlap_construction","_load_persistence_from_pickle"),
    ]
    for src, dst in flow:
        lines.append(f"    {_safe(src)} --> {_safe(dst)}")
    lines.append("")

    # ── 외부 모듈 호출 엣지 ──────────────────────────────────────────────────
    lines.append("    %% ── 외부 모듈 호출 ──")
    for caller, mod_calls in PIPELINE_EDGES.items():
        caller_id = _safe(caller)
        for (mod, fns) in mod_calls:
            for fn in fns:
                callee_id = _safe(f"{mod}_{fn}")
                lines.append(f"    {caller_id} --> {callee_id}")
    lines.append("")

    # ── 스타일 ───────────────────────────────────────────────────────────────
    lines.append("    %% ── 스타일 ──")
    for name in funcs:
        nid = _safe(name)
        color, _ = STAGE_MAP.get(name, ("#868e96", ""))
        stroke = "#555"
        txt_color = "#fff" if name in recent else "#111"
        if name in recent:
            lines.append(f"    style {nid} fill:#e63946,stroke:#c1121f,color:#fff")
        else:
            lines.append(f"    style {nid} fill:{color},stroke:{stroke},color:{txt_color}")

    for mod, color in MODULE_COLORS.items():
        lines.append(f"    classDef mod_{mod} fill:{color},stroke:{color},color:#fff,font-size:11px")

    return "\n".join(lines), tooltips


def build_mermaid_generic(module_name: str, filepath: Path,
                          funcs: dict[str, dict],
                          recent: set[str]) -> tuple[str, dict[str, str]]:
    """일반 모듈용 Mermaid 다이어그램 (AST 기반)."""
    src = filepath.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # import 매핑
    import_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_map[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                import_map[alias.asname or alias.name] = mod

    lines = [f'flowchart TD']
    tooltips: dict[str, str] = {}

    color = MODULE_COLORS.get(module_name, "#4361ee")
    lines.append(f'    subgraph MAIN["{module_name}.py"]')
    for name, info in funcs.items():
        nid = _safe(name)
        badge = " 🔴" if name in recent else ""
        lines.append(f'        {nid}["{name}{badge}"]')
        tooltips[name] = info["doc"]
        if name in recent:
            lines.append(f"        style {nid} fill:#e63946,stroke:#c1121f,color:#fff")
        else:
            lines.append(f"        style {nid} fill:{color},stroke:#555,color:#fff")
    lines.append("    end")

    return "\n".join(lines), tooltips


# ─────────────────────────────────────────────────────────────────────────────
# 4. HTML 렌더링
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code Map — {module}.py</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3; font-family: system-ui, -apple-system, sans-serif; }}
  header {{ background: #161b22; border-bottom: 1px solid #30363d;
            padding: 14px 24px; display: flex; align-items: baseline; gap: 16px; }}
  h1 {{ font-size: 18px; font-weight: 600; }}
  .meta {{ color: #8b949e; font-size: 13px; }}
  .legend {{
    display: flex; flex-wrap: wrap; gap: 10px;
    padding: 10px 24px; background: #161b22;
    border-bottom: 1px solid #30363d; font-size: 12px;
  }}
  .leg {{ display: flex; align-items: center; gap: 6px; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }}
  .container {{ padding: 24px; overflow: auto; }}
  .mermaid-wrap {{
    background: #ffffff; border-radius: 10px; padding: 24px;
    overflow: auto; max-width: 100%;
    box-shadow: 0 2px 12px rgba(0,0,0,.4);
  }}
  #tooltip {{
    position: fixed; display: none; z-index: 9999;
    background: rgba(0,0,0,.85); color: #fff;
    padding: 7px 12px; border-radius: 6px;
    font-size: 13px; max-width: 340px;
    pointer-events: none; white-space: pre-wrap;
    box-shadow: 0 2px 8px rgba(0,0,0,.5);
  }}
  footer {{ color: #6e7681; font-size: 11px; padding: 12px 24px; text-align: center; }}
</style>
</head>
<body>
<header>
  <h1>📊 Code Map — {module}.py</h1>
  <span class="meta">생성: {timestamp} · depth ≤ 3 · 🔴 = 최근 30일 수정</span>
</header>
<div class="legend">
  <span class="leg"><span class="dot" style="background:#e63946"></span> 최근 수정 (🔴)</span>
  {legend_items}
  <span class="leg"><span class="dot" style="background:#6c757d"></span> External Lib</span>
</div>
<div class="container">
  <div class="mermaid-wrap">
    <pre class="mermaid">
{mermaid_code}
    </pre>
  </div>
</div>
<div id="tooltip"></div>
<footer>TDA Music Pipeline · gen_code_map.py · {module}.py</footer>

<script>
const TOOLTIPS = {tooltips_json};

mermaid.initialize({{
  startOnLoad: true,
  theme: 'default',
  flowchart: {{ htmlLabels: true, curve: 'basis', padding: 20 }},
}});

const tipEl = document.getElementById('tooltip');

function addTooltips(svg) {{
  svg.querySelectorAll('.node').forEach(node => {{
    // text content of the node label
    const rawText = (node.querySelector('foreignObject div, text') ||
                     node.querySelector('[class*="label"]') || node)
                    .textContent || '';
    const name = rawText.replace(/🔴/g, '').replace(/\s+/g,' ').trim();
    const tip = TOOLTIPS[name];
    if (!tip) return;
    node.style.cursor = 'help';
    node.addEventListener('mouseenter', e => {{
      tipEl.textContent = name + '\n' + tip;
      tipEl.style.display = 'block';
    }});
    node.addEventListener('mousemove', e => {{
      tipEl.style.left = (e.clientX + 16) + 'px';
      tipEl.style.top  = (e.clientY + 12) + 'px';
    }});
    node.addEventListener('mouseleave', () => {{ tipEl.style.display = 'none'; }});
  }});
}}

(function waitForMermaid(tries) {{
  const svg = document.querySelector('.mermaid svg');
  if (svg) {{ addTooltips(svg); return; }}
  if (tries > 0) setTimeout(() => waitForMermaid(tries - 1), 400);
}})(15);
</script>
</body>
</html>
"""


def render_html(module: str, mermaid_code: str, tooltips: dict[str, str]) -> str:
    legend_items = ""
    for mod, color in MODULE_COLORS.items():
        if mod in ("pipeline", "external"):
            continue
        legend_items += f'<span class="leg"><span class="dot" style="background:{color}"></span> {mod}.py</span>\n  '

    return HTML_TEMPLATE.format(
        module       = module,
        timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M"),
        mermaid_code = mermaid_code,
        tooltips_json= json.dumps(tooltips, ensure_ascii=False),
        legend_items = legend_items.strip(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. 진입점
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python gen_code_map.py <module_name>")
        print("  Modules: " + ", ".join(MODULE_FILES.keys()))
        sys.exit(1)

    module = sys.argv[1].lower().replace(".py", "")
    if module not in MODULE_FILES:
        print(f"Error: '{module}' not in known modules: {list(MODULE_FILES.keys())}")
        sys.exit(1)

    filepath = MODULE_FILES[module]
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        sys.exit(1)

    print(f"[1/4] AST 파싱: {filepath.name}")
    funcs = parse_functions(filepath)
    print(f"      → {len(funcs)}개 함수 발견")

    print("[2/4] git log 최근 수정 감지 (30일)")
    recent = get_recent_funcs(filepath, funcs)
    print(f"      → 최근 수정: {recent or '없음'}")

    print("[3/4] Mermaid 다이어그램 생성")
    if module == "pipeline":
        mermaid_code, tooltips = build_mermaid_pipeline(funcs, recent)
    else:
        mermaid_code, tooltips = build_mermaid_generic(module, filepath, funcs, recent)

    print("[4/4] HTML 렌더링 → docs/")
    html = render_html(module, mermaid_code, tooltips)
    out  = DOCS / f"code_map_{module}.html"
    out.write_text(html, encoding="utf-8")
    print(f"\n✅ 완료: {out}")
    print(f"   브라우저에서 열기: file:///{out.as_posix()}")


if __name__ == "__main__":
    main()
