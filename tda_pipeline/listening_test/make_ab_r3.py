"""make_ab_r3.py — 3라운드 청취: 한 번에 세 질문을 묻는다

왜 세 가지를 섞는가
───────────────────
청취 시간이 가장 희소한 자원이다. 그리고 **모든 쌍은 어차피
"지표가 귀를 맞추는가" 누적 표본에 들어간다** — 그러니 서로 다른 질문을
같은 프로토콜로 물으면 한 번에 세 가지가 진척된다.

  A족 (5쌍) 원곡 OM  vs  디퓨전 OM
      → 지난 두 라운드가 1:4 로 갈렸다. 누적으로 방향을 본다.
  B족 (5쌍) NodePool 수정 전  vs  수정 후
      → 오늘 하루의 정정 작업이 **귀에 들리는가**. JS 는 −44.5% 라고 했지만
        협화도는 12트랙 전부 떨어졌다. 지표가 답하지 못한 질문이다.
  C족 (5쌍) α=0 (위상 붕괴, K=1)  vs  α=0.25 (정본, K=14)
      → 미해결 관찰: 위상이 무너진 지점에서 협화도가 가장 높았다(0.7360 vs 0.6767).
        "구조가 협화도를 내주고 있나" 를 귀로 묻는다.

통제 (ab_p4 와 동일)
────────────────────
쌍 안에서 창·시드·instLen 을 공유하고 **한 가지만 다르게** 한다.
temperature=1.0. 창은 32스텝(약 14.5초) = 한 구조 주기.
A/B 배치는 시드로 섞고 정답표는 별도 JSON 에만 남긴다.

실행:  python listening_test/make_ab_r3.py [--shuffle-seed N]
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_ROOT = _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__)))
_rp_sys.path.insert(0, _ROOT)
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "experiments"))
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "tools"))
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.abspath(__file__)))
# --- end path_bootstrap ---

import argparse, json, os, pickle, random
import numpy as np

import generation as G
import run_dft_gap0_suite as suite
from run_topo_diffusion import CACHE_DIR, CACHE_NAME, REAL_TAU, TDA_ROOT, load_continuous_om
from make_topo_music import SEC_PER_8TH, render_wav, write_midi
from make_ab_check import bits, gen, to_ogg
from make_ab_p4 import PAGE
from run_t9_nodepool_recompute import OldPool

OUT = os.path.join(TDA_ROOT, "output", "ab_r3")
MOTIF_JSON = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")
VINE_JSON = os.path.join(TDA_ROOT, "docs", "step3_data", "alpha_vineyard.json")

T = 32
BASE = 192
TEMPERATURE = 1.0
# ab_p4 와 겹치지 않는 창을 쓴다 (거기서는 0·32·64·96·128·160 을 썼다)
WIN_A = [192, 224, 256, 288, 320]
WIN_B = [64, 96, 128, 160, 192]
WIN_C = [0, 64, 128, 192, 256]
TRACKS_A = ["motifB_v1", "motifC_v1", "motifC_v2", "motifD_v1", "motifD_v2"]
SEEDS_A = [6101, 6202, 6303, 6404, 6505]
SEEDS_B = [6606, 6707, 6808, 6909, 7010]
SEEDS_C = [7111, 7212, 7313, 7414, 7515]


def om_from_bits(e, off):
    Tt, Kk = int(e["om_T"]), int(e["om_K"])
    ob = (np.frombuffer(e["om_bits"].encode("ascii"), dtype=np.uint8) == ord("1")).reshape(Tt, Kk)
    return ob[off:off + T].astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffle-seed", type=int, default=20260831)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    data = suite.setup_hibari()
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    om_full = load_continuous_om()
    tr = {t["track"]: t for t in json.load(open(MOTIF_JSON, encoding="utf-8"))["tracks"]}
    V = json.load(open(VINE_JSON, encoding="utf-8"))
    fr = {round(f["alpha"], 2): f for f in V["frames"]}

    def real_om(off):
        return (om_full[off:off + T] >= REAL_TAU).astype(np.float32)

    def vine_om(alpha, off):
        f = fr[alpha]
        ob = (np.frombuffer(f["om_bits"].encode("ascii"), dtype=np.uint8) == ord("1")
              ).reshape(f["T"], f["K"])
        return ob[off:off + T].astype(np.float32), {str(i): v for i, v in enumerate(f["cycles"].values())}

    pairs = []
    # ── A족: 원곡 OM vs 디퓨전 OM ──
    for i, (w, tk, sd) in enumerate(zip(WIN_A, TRACKS_A, SEEDS_A)):
        r, d = real_om(w), om_from_bits(tr[tk], w % 200)
        pairs.append((f"R{i+1}", "A", sd,
                      ("원곡 OM", gen(data, cyc, r, sd, temperature=TEMPERATURE)),
                      (f"디퓨전 OM ({tk})", gen(data, cyc, d, sd, temperature=TEMPERATURE)),
                      {"real_zero": int((r.sum(1) == 0).sum()), "other_zero": int((d.sum(1) == 0).sum())}))
    # ── B족: NodePool 수정 전 vs 후 (같은 OM·시드) ──
    for i, (w, sd) in enumerate(zip(WIN_B, SEEDS_B)):
        o = real_om(BASE + w if BASE + w + T <= om_full.shape[0] else w)
        pairs.append((f"R{i+6}", "B", sd,
                      ("NodePool 수정 전 (1-indexed)", gen(data, cyc, o, sd, pool_cls=OldPool, temperature=TEMPERATURE)),
                      ("NodePool 수정 후 (0-indexed)", gen(data, cyc, o, sd, temperature=TEMPERATURE)),
                      {"real_zero": int((o.sum(1) == 0).sum()), "other_zero": int((o.sum(1) == 0).sum())}))
    # ── C족: 위상 붕괴 vs 정본 ──
    for i, (w, sd) in enumerate(zip(WIN_C, SEEDS_C)):
        o0, c0 = vine_om(0.0, w)
        o25, c25 = vine_om(0.25, w)
        pairs.append((f"R{i+11}", "C", sd,
                      ("α=0.00 위상 붕괴 (K=1)", gen(data, c0, o0, sd, temperature=TEMPERATURE)),
                      ("α=0.25 정본 (K=14)", gen(data, c25, o25, sd, temperature=TEMPERATURE)),
                      {"real_zero": int((o0.sum(1) == 0).sum()), "other_zero": int((o25.sum(1) == 0).sum())}))

    rng = random.Random(args.shuffle_seed)
    key, blocks = {}, []
    print(f"{'쌍':5} {'족':3} {'시드':>6} {'A 정체':30} {'zero-row':>12} {'음':>9}")
    for pid, fam, sd, c0, c1, meta in pairs:
        cands = [c0, c1]
        if rng.random() < 0.5:
            cands.reverse()
        key[pid] = {"A": cands[0][0], "B": cands[1][0], "family": fam, "seed": sd, **meta}
        for L, (name, notes) in zip("AB", cands):
            stem = f"{pid}{L}"
            mid = os.path.join(OUT, stem + ".mid")
            wav = os.path.join(OUT, stem + ".wav")
            write_midi(notes, mid); render_wav(mid, wav)
            to_ogg(wav, os.path.join(OUT, stem + ".ogg")); os.remove(wav)
        zr = "%d/%d" % (meta["real_zero"], meta["other_zero"])
        nn = "%d/%d" % (len(cands[0][1]), len(cands[1][1]))
        print(f"{pid:5} {fam:3} {sd:>6} {cands[0][0][:30]:30} {zr:>12} {nn:>9}")
        blocks.append(
            f'<div class="pair"><div class="pn">{pid} / {len(pairs)}</div>'
            f'<div class="pt">어느 쪽이 더 마음에 드나요?</div>'
            f'<div class="side"><label>A</label><audio controls preload="none" src="{pid}A.ogg"></audio></div>'
            f'<div class="side"><label>B</label><audio controls preload="none" src="{pid}B.ogg"></audio></div>'
            f'<div class="choices">'
            f'<button data-pair="{pid}" data-val="A">A</button>'
            f'<button data-pair="{pid}" data-val="B">B</button>'
            f'<button data-pair="{pid}" data-val="?">모르겠다</button></div>'
            f'<textarea data-pair="{pid}" placeholder="이유 한 줄 (선택)"></textarea></div>')

    page = (PAGE.replace("__PAIRS__", "\n".join(blocks))
                .replace("__N__", str(len(pairs)))
                .replace("AB-P4 ", "AB-R3 ")
                .replace("각 약 15초 · <b>5분이면 끝납니다</b>", "각 약 15초 · <b>10분쯤 걸립니다</b>"))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
    json.dump({"experiment": "R3 — 3족 15쌍", "n_pairs": len(pairs), "T_steps": T,
               "seconds_each": round(T * SEC_PER_8TH, 1), "temperature": TEMPERATURE,
               "shuffle_seed": args.shuffle_seed,
               "families": {"A": "원곡 OM vs 디퓨전 OM", "B": "NodePool 수정 전 vs 후",
                            "C": "α=0 위상붕괴 vs α=0.25 정본"},
               "key": key, "note": "이 파일을 먼저 열지 마세요 — 블라인드가 깨집니다."},
              open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n페이지: {os.path.join(OUT, 'index.html')}")


if __name__ == "__main__":
    main()
