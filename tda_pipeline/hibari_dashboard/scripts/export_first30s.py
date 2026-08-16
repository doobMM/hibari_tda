"""
export_first30s.py — hibari 원곡 첫 30초 note export (Guided Tour 청취 비교용)
===========================================================================

배경:
Guided Tour(`tour.html`)의 미니 페인트 데모는 "활성 고리 → 구성음 화음"
단순 sonification이라 실제 원곡 멜로디가 아니다. 사용자가 "hibari 첫 30초
불러오기" 후 재생해도 원곡처럼 안 들린다는 불만이 있었다.

이 스크립트는 원곡 첫 30초(8분음표 단위, T<60)의 실제 note를 그대로 뽑아
`tour.html`에서 "🎧 원곡 30초 듣기" 버튼으로 재생할 수 있게 export한다.

주의:
- `experiments/run_dft_gap0_suite.py`의 setup_hibari()를 재사용.
- (2026-08-15) suite.BASE_DIR 이 정정되어 MIDI 경로 우회가 불필요해졌다
  override 필요 (export_hibari_data.py와 동일 패턴).
- inst1_real/inst2_real은 동일 절대 타임라인(8분음표 단위, bpm=60 가정)의
  (start, pitch, end) 튜플 리스트. inst2는 33-step 솔로 인트로 이후 시작.
"""

import os
import sys
import json
from pathlib import Path

# tda_pipeline 루트 + experiments/ 경로를 sys.path에 추가
HERE = Path(__file__).resolve().parent
TDA_ROOT = HERE.parent.parent   # tda_pipeline/
sys.path.insert(0, str(TDA_ROOT))
sys.path.insert(0, str(TDA_ROOT / 'experiments'))

import run_dft_gap0_suite as suite  # experiments/run_dft_gap0_suite.py

# `suite.MIDI_FILE` 몽키패치 제거 (2026-08-15, T14).
# BASE_DIR 근본 수정(739c389) 으로 suite 가 이미 루트를 가리킨다.

DASHBOARD_ROOT = HERE.parent                      # hibari_dashboard/
DATA_DIR = DASHBOARD_ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = DATA_DIR / 'original_first30s.json'

WINDOW_STEPS = 60  # 30초 @ bpm=60, 8분음표=0.5s → 60 step = 30s
BPM = 60


def main():
    os.chdir(TDA_ROOT)  # suite 내부 상대경로(cache 등)가 TDA_ROOT 기준

    data = suite.setup_hibari()
    combined = list(data['inst1_real']) + list(data['inst2_real'])

    notes = []
    for s, p, e in combined:
        if s >= WINDOW_STEPS:
            continue
        e_clamped = min(e, WINDOW_STEPS)
        if e_clamped <= s:
            continue
        notes.append((int(s), int(p), int(e_clamped)))

    notes.sort(key=lambda n: (n[0], n[1]))

    payload = {
        "bpm": BPM,
        "unit": "eighth_note",
        "T": WINDOW_STEPS,
        "notes": notes,
    }

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"[OK] {len(notes)} notes -> {OUT_PATH} ({size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
