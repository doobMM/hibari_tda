"""rerender_motif_tracks.py — T12: 12 모티브 트랙의 **오디오만** 다시 만든다

왜 전체 재실행이 아닌가
───────────────────────
기존 `.ogg` 는 2026-08-12 산출로 `fcf929f`(NodePool 인덱스 수정) 이전이다.
이 OM 들은 zero-row 가 23~87% 라 풀 경로가 활짝 열려 있어 버그가 그대로 들어갔다.

그런데 버그는 **OM 생성**이 아니라 **OM 으로부터의 음 선택**에 있었다.
디퓨전이 만든 OM 자체는 멀쩡하다. 그래서 `motif_control.py` 를 통째로 다시 돌리지 않는다:

  · 전체 재실행하면 RePaint 샘플링이 다시 돌아 **OM 이 바뀐다**
  · 그 OM 들은 이미 렌더된 A/B 자극(`output/ab_check`, `output/ab_p4`)의 출처다
    — 바꾸면 무엇으로 무엇을 만들었는지 추적이 끊긴다
  · 디퓨전 재샘플링에 491초가 걸린다

→ **저장된 `om_bits` 를 복원해 음악만 다시 생성한다.** 수정된 코드 + `TEMPERATURES=[1.0]`.
  OM·마스크·control 지표는 그대로 두고 `best`(js·협화도·음 수 등)만 갱신한다.

실행:  python experiments/rerender_motif_tracks.py [--no-wav]
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import os
import pickle
import time

import numpy as np

import run_dft_gap0_suite as suite
from motif_control import best_music_for_om
from make_topo_music import TEMPERATURES, render_wav, write_midi
from run_topo_diffusion import CACHE_DIR, CACHE_NAME, OUT_DIR, STEP3_DIR, TDA_ROOT

MOTIF_JSON = os.path.join(STEP3_DIR, "motif_control_results.json")


def to_ogg(wav, ogg, q=4):
    import shutil, subprocess
    if not shutil.which("ffmpeg"):
        return False
    return subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
                           "-c:a", "libvorbis", "-q:a", str(q), ogg],
                          capture_output=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wav", action="store_true")
    args = ap.parse_args()
    os.chdir(TDA_ROOT)
    t0 = time.time()

    print("=" * 92)
    print(f"T12 — 모티브 트랙 오디오 재생성 (NodePool 수정 후, TEMPERATURES={TEMPERATURES})")
    print("=" * 92)

    payload = json.load(open(MOTIF_JSON, encoding="utf-8"))
    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]

    print(f"\n{'트랙':16} {'zero-row':>12} {'종전 JS':>9} {'신규 JS':>9} "
          f"{'종전 협화':>9} {'신규 협화':>9} {'음':>6}")
    changed = 0
    for e in payload["tracks"]:
        T, Kk = int(e["om_T"]), int(e["om_K"])
        ob = (np.frombuffer(e["om_bits"].encode("ascii"), dtype=np.uint8) == ord("1")
              ).reshape(T, Kk).astype(np.float32)
        zr = int((ob.sum(1) == 0).sum())

        old_js, old_cons = float(e["js"]), float(e["consonance"])
        mus = best_music_for_om(ob, data, cycle_labeled, orig_flat, e["track"])
        if not mus:
            print(f"  {e['track']:16} 생성 실패 — 건너뜀")
            continue

        stem = f"topo_{e['track']}"
        mid = os.path.join(OUT_DIR, f"{stem}.mid")
        write_midi(mus["notes"], mid)
        if not args.no_wav:
            wav = os.path.join(OUT_DIR, f"{stem}.wav")
            try:
                e["wav_seconds"] = round(render_wav(mid, wav), 1)
                to_ogg(wav, os.path.join(OUT_DIR, f"{stem}.ogg"))
                os.remove(wav)
            except Exception as ex:
                e["wav_error"] = f"{type(ex).__name__}: {ex}"

        # OM·마스크·control 은 건드리지 않는다. 생성 지표만 갱신.
        e.update({k: v for k, v in mus.items() if k != "notes"})
        e["zero_rows"] = zr
        e["pool_exposure"] = zr / T
        e["rerendered_2026_08_15"] = {
            "reason": "NodePool 인덱스 수정(fcf929f) + 온도 축 제거 후 오디오만 재생성",
            "previous": {"js": old_js, "consonance": old_cons},
        }
        changed += 1
        print(f"  {e['track']:16} {f'{zr}/{T} ({zr/T:.0%})':>12} {old_js:>9.5f} {mus['js']:>9.5f} "
              f"{old_cons:>9.4f} {mus['consonance']:>9.4f} {mus['n_notes']:>6}")

    payload["rerender_note"] = (
        "2026-08-15: NodePool 인덱스 수정(fcf929f) 이전에 만들어진 오디오를 재생성했다. "
        "OM·mask·control 지표는 원본 그대로이며 생성 결과(js·consonance·n_notes 등)만 갱신됐다. "
        "온도 축은 제거됐다(TEMPERATURES=[1.0]) — 종전 근거 §7.7.3 이 철회됐고 이 OM 들은 "
        "풀이 실제로 열려 T=1.0 이 우세하기 때문이다. "
        "⚠ 각 트랙의 js·consonance 는 게이트+랭킹 통과 후 값이라 낙관적으로 편향돼 있다.")
    payload["rerender_seconds"] = time.time() - t0
    with open(MOTIF_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    js_old = np.mean([e["rerendered_2026_08_15"]["previous"]["js"]
                      for e in payload["tracks"] if "rerendered_2026_08_15" in e])
    js_new = np.mean([e["js"] for e in payload["tracks"] if "rerendered_2026_08_15" in e])
    print(f"\n{'─'*92}")
    print(f"{changed}트랙 재생성 · 평균 JS {js_old:.5f} → {js_new:.5f} "
          f"({100*(js_new-js_old)/js_old:+.1f}%)")
    print(f"저장: {MOTIF_JSON}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
