"""embed_hibari_midis.py

tda_pipeline/tonnetz_demo/js/preloaded_midi.js 에 hibari 파이프라인 7단계
(v0 원곡 + v1~v6 생성본) base64 인라인을 추가한다.

- 기존 공용도메인 3곡(bach/ravel/clair)은 보존
- 기존에 hibari_* 키가 있으면 전부 삭제 후 새로 추가 (idempotent)
"""

from __future__ import annotations
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tonnetz_demo" / "js" / "preloaded_midi.js"

# 7개 엔트리: (key, title, artist, year, source path relative to ROOT)
ENTRIES = [
    ("hibari_v0", "hibari (원곡)",        "Ryuichi Sakamoto", "2009",
     "Ryuichi_Sakamoto_-_hibari.mid"),
    ("hibari_v1", "v1 · Algo 1 · freq",   "TDA pipeline",     "2026",
     "output/hibari+/v1_algo1_frequency_binary.mid"),
    ("hibari_v2", "v2 · Algo 1 · DFT",    "TDA pipeline",     "2026",
     "output/hibari+/v2_algo1_dft_binary.mid"),
    ("hibari_v3", "v3 · Algo 1 · τ_c α=0.5", "TDA pipeline",  "2026",
     "output/hibari+/v3_algo1_dft_percycle_tau_alpha05.mid"),
    ("hibari_v4", "v4 · Algo 1 · τ_c α=0.25 ★", "TDA pipeline", "2026",
     "output/hibari+/v4_algo1_dft_percycle_alpha025.mid"),
    ("hibari_v5", "v5 · Algo 2 · FC-cont ★", "TDA pipeline",  "2026",
     "output/hibari+/v5_algo2_fc_cont_dft_alpha05.mid"),
    ("hibari_v6", "v6 · Block P3 (m=0)",  "TDA pipeline",     "2026",
     "output/hibari+/v6_block_p3_bestof10_m0.mid"),
]


def encode(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def format_entry(key: str, title: str, artist: str, year: str, b64: str) -> str:
    # 한 줄로 포맷 (기존 bach/ravel/clair 스타일 유지)
    title_esc = title.replace('"', '\\"')
    artist_esc = artist.replace('"', '\\"')
    return (
        f'  {key}: {{ title: "{title_esc}", artist: "{artist_esc}", '
        f'year: "{year}", b64: "{b64}" }},\n'
    )


def main() -> None:
    src = TARGET.read_text(encoding="utf-8")

    # 기존 hibari_* 엔트리 전부 제거 (멱등성 보장)
    src_clean = re.sub(
        r"^  hibari_[a-z0-9_]+: \{[^\n]*\n",
        "",
        src,
        flags=re.MULTILINE,
    )

    # 새 엔트리 생성
    new_lines = []
    for key, title, artist, year, rel in ENTRIES:
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(path)
        b64 = encode(path)
        new_lines.append(format_entry(key, title, artist, year, b64))
        print(f"{key:12s}  {path.stat().st_size:>7d} B → {len(b64):>8d} b64")

    # `};` 닫는 중괄호 앞에 삽입
    if "\n};" not in src_clean:
        raise RuntimeError("Could not find closing '};' in preloaded_midi.js")
    updated = src_clean.replace("\n};", "\n" + "".join(new_lines).rstrip() + "\n};")

    TARGET.write_text(updated, encoding="utf-8")
    print(f"\n✓ Wrote {TARGET}")
    print(f"  size: {len(src):,} → {len(updated):,} bytes  (+{len(updated)-len(src):,})")


if __name__ == "__main__":
    main()
