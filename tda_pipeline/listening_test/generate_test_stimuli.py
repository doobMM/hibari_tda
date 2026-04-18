"""
Task 45 - Listening test stimuli builder.

목표
1) 청취 실험용 A~H 자극을 output/listening_test/stimuli/로 모읍니다.
2) 30~60초 클립(기본 45초)을 만들어 파일 길이를 통일합니다.
3) 모바일 우선 HTML 플레이어(index.html)와 메타데이터를 생성합니다.

주의
- D/E/F(major_block32 계열)는 워크스페이스에 원본 파일이 없을 수 있습니다.
- 없으면 "missing"으로 리포트하고, override 파일로 경로를 주입할 수 있습니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.io import wavfile


SCRIPT_DIR = Path(__file__).resolve().parent
TDA_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = TDA_DIR / "output" / "listening_test"
STIMULI_DIR = OUTPUT_DIR / "stimuli"

if str(TDA_DIR) not in sys.path:
    sys.path.insert(0, str(TDA_DIR))

from wav_renderer import render_midi_to_wav  # noqa: E402


@dataclass(frozen=True)
class StimulusSpec:
    code: str
    title: str
    condition: str
    purpose: str
    js_reference: str
    source_candidates: Tuple[str, ...]
    required: bool = True


REQUIRED_STIMULI: Tuple[StimulusSpec, ...] = (
    StimulusSpec(
        code="A",
        title="Original hibari",
        condition="원곡 기준",
        purpose="기준 청취 자극",
        js_reference="-",
        source_candidates=(
            "output/final/hibari_original.wav",
            "output/hibari_original.wav",
            "Ryuichi_Sakamoto_-_hibari.mid",
        ),
    ),
    StimulusSpec(
        code="B",
        title="Algo1 Best",
        condition="DFT + per-cycle tau + gap=0 (Algo1)",
        purpose="수치 최적 Algo1",
        js_reference="0.01489",
        source_candidates=(
            "output/final/hibari_dft_gap0_algo1_final.wav",
            "output/hibari_dft_gap0_algo1.wav",
            "output/final/hibari_dft_gap0_algo1_final.mid",
        ),
    ),
    StimulusSpec(
        code="C",
        title="Algo2 FC-cont Best",
        condition="DFT + FC continuous + gap=0 (Algo2)",
        purpose="수치 최적 Algo2",
        js_reference="0.00035",
        source_candidates=(
            "output/final/hibari_dft_gap0_algo2_fc_cont_final.wav",
            "output/final/hibari_dft_gap0_algo2_fc_cont_final.mid",
            "output/hibari_complex_algo2_fc.wav",
        ),
    ),
    StimulusSpec(
        code="D",
        title="Tonnetz Success Case",
        condition="major_block32 Tonnetz-Transformer",
        purpose="위상 보존 변주 성공 사례 검증",
        js_reference="0.096786",
        source_candidates=(
            "output/section66/major_block32_tonnetz_transformer.wav",
            "output/section66/major_block32_tonnetz_transformer.mid",
            "output/major_block32_tonnetz_transformer.wav",
            "output/major_block32_tonnetz_transformer.mid",
        ),
    ),
    StimulusSpec(
        code="E",
        title="DFT Switch Failure",
        condition="major_block32 DFT-Transformer",
        purpose="Tonnetz 대비 DFT 악화 체감 검증",
        js_reference="0.353591",
        source_candidates=(
            "output/section66/major_block32_dft_transformer.wav",
            "output/section66/major_block32_dft_transformer.mid",
            "output/major_block32_dft_transformer.wav",
            "output/major_block32_dft_transformer.mid",
        ),
    ),
    StimulusSpec(
        code="F",
        title="DFT-FC Variant",
        condition="major_block32 DFT-FC",
        purpose="DFT 변주에서 FC 대안 검증",
        js_reference="0.307744",
        source_candidates=(
            "output/section66/major_block32_dft_fc.wav",
            "output/section66/major_block32_dft_fc.mid",
            "output/major_block32_dft_fc.wav",
            "output/major_block32_dft_fc.mid",
        ),
    ),
    StimulusSpec(
        code="G",
        title="Legacy gap=3",
        condition="DFT + gap=3 (Algo1 legacy)",
        purpose="gap=0 롤백 타당성 검증",
        js_reference="-",
        source_candidates=(
            "output/final/hibari_dft_gap3_algo1_legacy.wav",
            "output/hibari_dft_gap3_algo1.wav",
            "output/final/hibari_dft_gap3_algo1_legacy.mid",
        ),
    ),
    StimulusSpec(
        code="H",
        title="Legacy Tonnetz Complex",
        condition="Tonnetz complex legacy",
        purpose="레거시 복원 서사 재검증",
        js_reference="0.0183",
        source_candidates=(
            "output/final/hibari_tonnetz_complex_legacy.wav",
            "output/hibari_complex_algo1_best.wav",
            "output/final/hibari_tonnetz_complex_legacy.mid",
        ),
    ),
)


OPTIONAL_STIMULI: Tuple[StimulusSpec, ...] = (
    StimulusSpec(
        code="I",
        title="Algo1 Baseline",
        condition="DFT baseline without per-cycle tau",
        purpose="per-cycle tau 효과 확인용",
        js_reference="-",
        source_candidates=(
            "output/hibari_timeflow_algo1_best.wav",
            "output/hibari_timeflow_algo1_best.mid",
        ),
        required=False,
    ),
    StimulusSpec(
        code="J",
        title="FC Binary",
        condition="FC with binary overlap",
        purpose="continuous 입력 이점 확인",
        js_reference="-",
        source_candidates=(
            "output/test_algo2_fc_direct.wav",
            "output/test_algo2_fc_direct.mid",
        ),
        required=False,
    ),
    StimulusSpec(
        code="K",
        title="Frequency Baseline",
        condition="frequency metric baseline",
        purpose="거리함수 대비 기준선",
        js_reference="-",
        source_candidates=(
            "output/section66/frequency_baseline.wav",
            "output/section66/frequency_baseline.mid",
        ),
        required=False,
    ),
    StimulusSpec(
        code="L",
        title="Continuous Direct",
        condition="continuous direct condition",
        purpose="연속값 직접 입력 조건 확인",
        js_reference="-",
        source_candidates=(
            "output/section66/continuous_direct.wav",
            "output/section66/continuous_direct.mid",
        ),
        required=False,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listening test stimuli builder")
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=45.0,
        help="클립 길이(초). --full 모드에서는 무시됩니다.",
    )
    parser.add_argument(
        "--start-sec",
        type=float,
        default=30.0,
        help="클립 시작 시간(초). 파일 길이가 짧으면 자동 보정됩니다.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="클립을 자르지 않고 원본 전체를 사용합니다.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="선택 자극(I~L)도 함께 시도합니다.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="필수 자극 누락 시 종료 코드 1로 실패 처리합니다.",
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=SCRIPT_DIR / "stimuli_overrides.json",
        help="자극 코드별 수동 경로 매핑 JSON 파일",
    )
    return parser.parse_args()


def load_overrides(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("override 파일은 {code: path} 형태의 JSON이어야 합니다.")
    normalized: Dict[str, str] = {}
    for k, v in payload.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        normalized[k.strip().upper()] = v.strip()
    return normalized


def resolve_source(spec: StimulusSpec, overrides: Dict[str, str]) -> Tuple[Optional[Path], str]:
    override_value = overrides.get(spec.code)
    if override_value:
        p = Path(override_value)
        if not p.is_absolute():
            p = TDA_DIR / override_value
        if p.exists():
            return p, "override"
        return None, f"override_missing:{p}"

    for rel in spec.source_candidates:
        p = TDA_DIR / rel
        if p.exists():
            return p, "candidate"
    return None, "not_found"


def read_wav_float(path: Path) -> Tuple[int, np.ndarray]:
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        arr = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        arr = data.astype(np.float32) / 2147483648.0
    elif np.issubdtype(data.dtype, np.floating):
        arr = data.astype(np.float32)
    else:
        raise ValueError(f"지원하지 않는 WAV dtype: {data.dtype}")
    return sr, arr


def write_wav_float(path: Path, sr: int, data: np.ndarray) -> None:
    clipped = np.clip(data, -1.0, 1.0)
    out = (clipped * 32767.0).astype(np.int16)
    wavfile.write(path, sr, out)


def clip_and_normalize_wav(
    in_wav: Path,
    out_wav: Path,
    *,
    full: bool,
    start_sec: float,
    duration_sec: float,
) -> Tuple[float, float]:
    sr, data = read_wav_float(in_wav)
    total_samples = data.shape[0]
    total_sec = total_samples / float(sr)

    if full:
        chunk = data
        used_start = 0.0
    else:
        length_samples = max(1, int(duration_sec * sr))
        start_samples = int(max(0.0, start_sec) * sr)
        if start_samples + length_samples > total_samples:
            start_samples = max(0, total_samples - length_samples)
        end_samples = min(total_samples, start_samples + length_samples)
        chunk = data[start_samples:end_samples]
        used_start = start_samples / float(sr)

    peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
    if peak > 0:
        chunk = chunk / peak * 0.92

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    write_wav_float(out_wav, sr, chunk)
    clip_sec = chunk.shape[0] / float(sr)
    return used_start, clip_sec


def render_midi_source(mid_path: Path, temp_wav: Path) -> None:
    temp_wav.parent.mkdir(parents=True, exist_ok=True)
    render_midi_to_wav(str(mid_path), str(temp_wav))


def human_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_output_name(code: str, title: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in title).strip("_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return f"{code}_{safe}.wav"


def write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def write_catalog_csv(rows: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "code",
        "status",
        "title",
        "condition",
        "purpose",
        "js_reference",
        "source",
        "source_resolution",
        "output_wav",
        "clip_start_sec",
        "clip_duration_sec",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})


def build_html(rows: List[dict], output_path: Path, clip_mode: str) -> None:
    available = [r for r in rows if r.get("status") == "ready"]
    missing = [r for r in rows if r.get("status") != "ready" and r.get("required", True)]

    card_html = []
    for row in available:
        rel_audio = Path(row["output_wav"]).relative_to(OUTPUT_DIR).as_posix()
        card_html.append(
            f"""
<article class="card">
  <h2>{row['code']}. {row['title']}</h2>
  <p class="meta">{row['condition']}</p>
  <p>{row['purpose']}</p>
  <audio controls preload="none" src="{rel_audio}"></audio>
  <p class="small">JS ref: {row['js_reference']} | clip: {row.get('clip_duration_sec', '-')}s</p>
</article>
""".strip()
        )

    missing_html = ""
    if missing:
        missing_lines = "\n".join(
            f"<li>{r['code']} - {r['title']} (원본 필요: {r.get('notes', 'missing')})</li>"
            for r in missing
        )
        missing_html = f"""
<section class="missing">
  <h2>누락된 필수 자극</h2>
  <ul>
    {missing_lines}
  </ul>
</section>
""".strip()

    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Listening Test Stimuli</title>
  <style>
    :root {{
      --bg: #f7f8f5;
      --card: #ffffff;
      --ink: #182126;
      --muted: #54606b;
      --line: #dce2e8;
      --accent: #0c6f60;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Pretendard", "Noto Sans KR", "Segoe UI", sans-serif;
      color: var(--ink);
      background: linear-gradient(170deg, #eef4f2 0%, var(--bg) 45%, #fff 100%);
      padding: 16px;
    }}
    .wrap {{
      max-width: 880px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 1.4rem;
      line-height: 1.3;
    }}
    .desc {{
      color: var(--muted);
      margin-bottom: 16px;
      font-size: 0.95rem;
    }}
    .grid {{
      display: grid;
      gap: 12px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 8px 24px rgba(13, 33, 45, 0.05);
    }}
    .card h2 {{
      margin: 0 0 6px;
      font-size: 1.05rem;
    }}
    .meta {{
      margin: 0 0 10px;
      color: var(--accent);
      font-weight: 600;
      font-size: 0.92rem;
    }}
    .small {{
      margin: 8px 0 0;
      font-size: 0.84rem;
      color: var(--muted);
    }}
    audio {{
      width: 100%;
      margin-top: 8px;
    }}
    .missing {{
      margin-top: 16px;
      background: #fff8f4;
      border: 1px solid #f2d1c2;
      border-radius: 12px;
      padding: 12px;
    }}
    .missing h2 {{
      margin: 0 0 6px;
      color: #8a3c20;
      font-size: 1rem;
    }}
    .missing ul {{
      margin: 0;
      padding-left: 18px;
    }}
    @media (min-width: 720px) {{
      .grid {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Task 45 Listening Test Set</h1>
    <p class="desc">모바일 우선 플레이어입니다. 파일 모드: {clip_mode}. 라벨(A~H)만 노출해 블라인드 청취를 지원합니다.</p>
    <section class="grid">
      {"".join(card_html)}
    </section>
    {missing_html}
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def build_stimuli(args: argparse.Namespace) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STIMULI_DIR.mkdir(parents=True, exist_ok=True)

    specs: List[StimulusSpec] = list(REQUIRED_STIMULI)
    if args.include_optional:
        specs.extend(OPTIONAL_STIMULI)

    overrides = load_overrides(args.overrides)
    rows: List[dict] = []
    missing_required = 0
    temp_dir = OUTPUT_DIR / "_tmp_render"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        source, resolution = resolve_source(spec, overrides)
        row = {
            "code": spec.code,
            "title": spec.title,
            "condition": spec.condition,
            "purpose": spec.purpose,
            "js_reference": spec.js_reference,
            "required": spec.required,
            "source_resolution": resolution,
            "source": str(source) if source else "",
            "status": "missing",
            "output_wav": "",
            "clip_start_sec": "",
            "clip_duration_sec": "",
            "notes": "",
        }

        if source is None:
            row["notes"] = "source_not_found"
            rows.append(row)
            if spec.required:
                missing_required += 1
            continue

        ext = source.suffix.lower()
        source_wav: Optional[Path] = None
        if ext == ".wav":
            source_wav = source
        elif ext in {".mid", ".midi"}:
            temp_wav = temp_dir / f"{spec.code}_render.wav"
            try:
                render_midi_source(source, temp_wav)
                source_wav = temp_wav
            except Exception as exc:  # pragma: no cover
                row["notes"] = f"midi_render_failed:{type(exc).__name__}:{exc}"
                rows.append(row)
                if spec.required:
                    missing_required += 1
                continue
        else:
            row["notes"] = f"unsupported_source_ext:{ext}"
            rows.append(row)
            if spec.required:
                missing_required += 1
            continue

        out_name = make_output_name(spec.code, spec.title)
        out_wav = STIMULI_DIR / out_name

        try:
            if args.full:
                shutil.copy2(source_wav, out_wav)
                _, arr = read_wav_float(out_wav)
                clip_duration = arr.shape[0] / 44100.0
                clip_start = 0.0
            else:
                clip_start, clip_duration = clip_and_normalize_wav(
                    source_wav,
                    out_wav,
                    full=False,
                    start_sec=args.start_sec,
                    duration_sec=args.duration_sec,
                )
            row["status"] = "ready"
            row["output_wav"] = str(out_wav)
            row["clip_start_sec"] = round(float(clip_start), 3)
            row["clip_duration_sec"] = round(float(clip_duration), 3)
        except Exception as exc:  # pragma: no cover
            row["notes"] = f"wav_prepare_failed:{type(exc).__name__}:{exc}"
            if spec.required:
                missing_required += 1

        rows.append(row)

    manifest = {
        "generated_at": human_now(),
        "project_root": str(TDA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "clip_mode": "full" if args.full else "clip",
        "clip_default": None
        if args.full
        else {"start_sec": args.start_sec, "duration_sec": args.duration_sec},
        "required_total": len(REQUIRED_STIMULI),
        "required_missing": missing_required,
        "rows": rows,
    }
    write_manifest(manifest, OUTPUT_DIR / "stimuli_manifest.json")
    write_catalog_csv(rows, OUTPUT_DIR / "stimuli_catalog.csv")
    build_html(rows, OUTPUT_DIR / "index.html", "full" if args.full else "clip")

    print("=" * 72)
    print("Listening test stimuli build complete")
    print("=" * 72)
    ready_count = sum(1 for r in rows if r["status"] == "ready")
    print(f"Ready stimuli: {ready_count}/{len(rows)}")
    print(f"Required missing: {missing_required}/{len(REQUIRED_STIMULI)}")
    print(f"Manifest: {OUTPUT_DIR / 'stimuli_manifest.json'}")
    print(f"Web player: {OUTPUT_DIR / 'index.html'}")

    if missing_required > 0 and args.strict:
        return 1
    return 0


def main() -> None:
    args = parse_args()
    code = build_stimuli(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
