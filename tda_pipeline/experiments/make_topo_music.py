"""
make_topo_music.py — 위상 손실 디퓨전이 만든 OM 으로 실제 감상용 음악 생산

`run_topo_diffusion.py` 가 학습한 디노이저에서 중첩행렬(OM)을 뽑고,
Algorithm 1 로 음악을 생성한 뒤, **들을 수 있는 WAV** 까지 만든다.

생산 트랙
─────────
  A. REAL_30    — 원곡 OM 창(30초). 기준선: "지금까지 있던 것"
  B. CONV_30    — 1D-conv 디노이저, 위상 손실 없음. 아키텍처 효과만
  C. FULL_30    — 위상 손실 + 밀도 손실. 이번 접목의 결과
  D. FULL_LONG  — MultiDiffusion 으로 이어붙인 T=240(약 1분 50초) ★ 본편
  E. REAL_LONG  — 원곡 OM 같은 길이. D 와 직접 A/B

후보 선별 (2단)
──────────────
  1차 구조 게이트 : pitch JS 하위 절반만 통과 (원곡과의 음고분포 충실도)
  2차 미적 랭킹   : 협화도 최대. 협화도는 미적 지표 3종 중 유일하게
                    calibration 을 통과한 성분이다
                    (`project_aesthetic_rerank_negative_0613` — V·L 은 hibari
                     의 2성부 음역 분리를 오히려 페널티했다).

실행
────
  python experiments/make_topo_music.py
  python experiments/make_topo_music.py --no-wav      # MIDI 까지만
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
_rp_sys.path.insert(0, _rp_os.path.join(
    _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))), "tools"))
# --- end path_bootstrap ---

import argparse
import json
import os
import pickle
import time
from typing import Dict, List, Tuple

import numpy as np
import torch

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity

from run_topo_diffusion import (  # noqa: E402
    CACHE_DIR, CACHE_NAME, K, LONG_T, MODULES, OUT_DIR, REAL_TAU, STEP3_DIR,
    TDA_ROOT, WINDOW, DDPM, TopoConvUNet, consonance_score,
    density_match_binarize, generate_from_om, h0_runs_np,
    js_divergence_profiles, load_continuous_om, per_cycle_activation_profile,
    sample, sample_multidiffusion, sliding_windows_ct, temporal_autocorr,
)

TEMPO_BPM = 66
SEC_PER_8TH = 60.0 / TEMPO_BPM / 2.0        # 0.4545 s → T=60 ≈ 27s, T=240 ≈ 109s
N_CANDIDATES = 40                            # 트랙당 Algorithm 1 시드 수
N_OM_POOL = 24                               # 트랙당 후보 OM 개수
SAMPLE_SEED = 20260807


# ═══════════════════════════════════════════════════════════════════════════
# 모델 로드
# ═══════════════════════════════════════════════════════════════════════════

def load_model(variant: str) -> Tuple[TopoConvUNet, DDPM, dict]:
    path = os.path.join(CACHE_DIR, f"topo_diffusion_{variant}.pt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"모델 없음: {path} — run_topo_diffusion.py 를 먼저 실행")
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model = TopoConvUNet()
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, DDPM(), ckpt.get("meta", {})


# ═══════════════════════════════════════════════════════════════════════════
# OM 소스
# ═══════════════════════════════════════════════════════════════════════════

def build_om_sources(no_long: bool = False) -> Dict[str, np.ndarray]:
    """트랙명 → 이진 OM 후보 배열 (n, T, K)."""
    om = load_continuous_om()
    X = sliding_windows_ct(om, WINDOW, 2).transpose(0, 2, 1)      # (n,T,K)
    rng = np.random.default_rng(2026)

    src: Dict[str, np.ndarray] = {}

    # A. 원곡 OM 창
    idx = rng.choice(X.shape[0], size=N_OM_POOL, replace=False)
    src["REAL_30"] = (X[idx] >= REAL_TAU).astype(np.float32)

    # B/C. 디퓨전 30초 — 학습 데이터와 동일한 자(τ=0.5)로 이진화한다.
    # 밀도 일치 이진화는 연속 평균(0.264)을 그대로 켜므로 REAL(τ=0.5, 139셀)과
    # 애초에 비교가 안 된다 (eval_topo_diffusion.py 상단 주석 참조).
    for track, variant in (("CONV_30", "conv"), ("FULL_30", "full")):
        model, ddpm, _ = load_model(variant)
        s = sample(model, ddpm, N_OM_POOL, SAMPLE_SEED)
        src[track] = (s >= REAL_TAU).astype(np.float32)
        print(f"  [{track}] 샘플 {N_OM_POOL}개 생성 (연속 평균 {s.mean():.3f})")

    if no_long:
        return src

    # D. MultiDiffusion 장형
    model, ddpm, _ = load_model("full")
    longs = []
    n_long = 6
    for i in range(n_long):
        t0 = time.time()
        lo = sample_multidiffusion(model, ddpm, LONG_T, SAMPLE_SEED + i * 17)
        longs.append(lo)
        print(f"  [FULL_LONG] {i+1}/{n_long} MultiDiffusion T={LONG_T} ({time.time()-t0:.1f}s)")
    src["FULL_LONG"] = (np.stack(longs) >= REAL_TAU).astype(np.float32)

    # E. 원곡 OM 동일 길이
    starts = rng.choice(om.shape[0] - LONG_T, size=n_long, replace=False)
    src["REAL_LONG"] = np.stack([(om[s:s + LONG_T] >= REAL_TAU).astype(np.float32)
                                 for s in starts])
    return src


# ═══════════════════════════════════════════════════════════════════════════
# 후보 생성 + 2단 선별
# ═══════════════════════════════════════════════════════════════════════════

def generate_with_temperature(data, cycle_labeled, om_bin, seed, temperature):
    """NodePool 온도만 바꾼 Algorithm 1. T>1 은 희귀 note 쪽으로 균등화한다."""
    import random
    from generation import CycleSetManager, NodePool, algorithm1_optimized
    T = om_bin.shape[0]
    inst_len = (MODULES * (T // len(MODULES) + 2))[:T]
    random.seed(seed)
    np.random.seed(seed)
    pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65,
                    temperature=temperature)
    return algorithm1_optimized(pool, list(inst_len), om_bin.astype(np.float32),
                                CycleSetManager(cycle_labeled),
                                max_resample=50, verbose=False, min_onset_gap=0)


# 후보 공간을 온도 축으로 넓힌다. 1.0=원래 빈도, 3.0=§7.7.3 JS 최적.
# 어느 쪽이 더 "듣기 좋은지"는 협화도 랭킹이 고르게 한다.
TEMPERATURES = [1.0, 2.0, 3.0, 4.0]


def produce_track(track: str, om_pool: np.ndarray, data: dict, cycle_labeled: dict,
                  orig_flat: List[Tuple[int, int, int]], n_cand: int = N_CANDIDATES) -> dict:
    rng = np.random.default_rng(abs(hash(track)) % (2 ** 31))
    cands = []
    for i in range(n_cand):
        oi = int(rng.integers(0, om_pool.shape[0]))
        seed = 40000 + i * 7 + (abs(hash(track)) % 1000)
        temp = TEMPERATURES[i % len(TEMPERATURES)]
        gen = generate_with_temperature(data, cycle_labeled, om_pool[oi], seed, temp)
        if not gen:
            continue
        js = pitch_distribution_similarity(gen, orig_flat)["js_divergence"]
        cands.append({"om_idx": oi, "seed": seed, "temperature": temp, "js": js,
                      "consonance": consonance_score(gen),
                      "n_notes": len(gen), "notes": gen})
    if not cands:
        return {"track": track, "error": "후보 0개"}

    # 1차 구조 게이트 → 2차 협화도 랭킹
    js_med = float(np.median([c["js"] for c in cands]))
    passed = [c for c in cands if c["js"] <= js_med] or cands
    best = max(passed, key=lambda c: c["consonance"])

    pitches = [p for _, p, _ in best["notes"]]
    om_best = om_pool[best["om_idx"]]
    return {
        "track": track,
        # 들판 그림용 — 이 곡을 만든 바로 그 중첩행렬 (t-major 0/1 문자열)
        "om_bits": "".join("1" if v else "0" for v in om_best.reshape(-1).astype(int)),
        "om_T": int(om_best.shape[0]),
        "om_K": int(om_best.shape[1]),
        "n_candidates": len(cands),
        "js_gate_median": js_med,
        "n_passed_gate": len(passed),
        "best": {"om_idx": best["om_idx"], "seed": best["seed"],
                 "temperature": best["temperature"],
                 "js": best["js"], "consonance": best["consonance"],
                 "n_notes": best["n_notes"],
                 "pitch_min": int(min(pitches)), "pitch_max": int(max(pitches)),
                 "duration_sec": round(max(e for _, _, e in best["notes"]) * SEC_PER_8TH, 1)},
        "pool_stats": {
            "js_mean": float(np.mean([c["js"] for c in cands])),
            "js_std": float(np.std([c["js"] for c in cands], ddof=1)),
            "consonance_mean": float(np.mean([c["consonance"] for c in cands])),
            "consonance_std": float(np.std([c["consonance"] for c in cands], ddof=1)),
            "consonance_best": float(best["consonance"]),
        },
        "notes": best["notes"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 렌더링
# ═══════════════════════════════════════════════════════════════════════════

def write_midi(notes: List[Tuple[int, int, int]], path: str, *, shape_velocity: bool = True) -> None:
    """
    MIDI 기록. shape_velocity 는 **연주 레이어**이지 알고리즘의 일부가 아니다 —
    음고·리듬은 그대로 두고 세기만 손댄다. 근거는 hibari 의 2성부 음역 분리:
    아래 성부는 울림(페달)로 받치고 위 성부를 앞으로 낸다. 또 같은 순간에 음이
    많이 몰리면 전체를 살짝 눌러 탁해지지 않게 한다.
    """
    import pretty_midi
    from collections import Counter
    onset_count = Counter(s for s, _, _ in notes)

    pm = pretty_midi.PrettyMIDI(initial_tempo=float(TEMPO_BPM))
    inst = pretty_midi.Instrument(program=0, name="Piano")
    for s, p, e in notes:
        if shape_velocity:
            v = 72
            if p >= 72:
                v += 9                       # 선율 성부는 앞으로
            elif p < 55:
                v -= 7                       # 저역은 울림으로 받친다
            v -= 3 * max(0, onset_count[s] - 3)   # 몰릴수록 눌러 탁함 방지
            v = int(max(38, min(104, v)))
        else:
            v = 80
        inst.notes.append(pretty_midi.Note(velocity=v, pitch=int(p),
                                           start=float(s) * SEC_PER_8TH,
                                           end=float(e) * SEC_PER_8TH))
    pm.instruments.append(inst)
    pm.write(path)


def render_wav(mid_path: str, wav_path: str) -> float:
    from wav_renderer import render_midi_to_wav
    return render_midi_to_wav(mid_path, wav_path)


# ═══════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wav", action="store_true")
    ap.add_argument("--no-long", action="store_true")
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    os.makedirs(OUT_DIR, exist_ok=True)
    t_total = time.time()

    print("=" * 76)
    print("위상 손실 디퓨전 → 감상용 음악 생산")
    print("=" * 76)

    print("\n[1/4] OM 소스 준비...")
    sources = build_om_sources(no_long=args.no_long)

    # OM 구조 요약 (원곡 대비)
    real_prof = per_cycle_activation_profile(sources["REAL_30"])
    print("\n  OM 구조 요약")
    print(f"  {'track':<11} {'density/step':>12} {'autocorr':>9} {'H0runs':>7} {'runlen':>7} {'JSprof':>8}")
    om_stats = {}
    for name, pool in sources.items():
        dens = float(pool.sum(axis=(1, 2)).mean() / pool.shape[1])
        ac = temporal_autocorr(pool)
        runs, runlen = h0_runs_np(pool)
        jsp = js_divergence_profiles(per_cycle_activation_profile(pool), real_prof)
        om_stats[name] = {"density_per_step": dens, "temporal_autocorr": ac,
                          "h0_runs_per_cycle": runs, "mean_run_length": runlen,
                          "js_vs_real_profile": jsp, "T": int(pool.shape[1])}
        print(f"  {name:<11} {dens:>12.2f} {ac:>9.4f} {runs:>7.2f} {runlen:>7.2f} {jsp:>8.5f}")

    print("\n[2/4] hibari 파이프라인 로드...")
    t0 = time.time()
    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]
    print(f"  완료 ({time.time()-t0:.1f}s) K={len(cycle_labeled)}")

    print(f"\n[3/4] 트랙별 후보 {N_CANDIDATES}개 생성 + 2단 선별...")
    tracks = {}
    for name, pool in sources.items():
        t0 = time.time()
        r = produce_track(name, pool, data, cycle_labeled, orig_flat)
        tracks[name] = r
        b = r["best"]
        ps = r["pool_stats"]
        print(f"  [{name:<11}] JS={b['js']:.5f} (pool {ps['js_mean']:.5f}±{ps['js_std']:.5f})"
              f"  협화={b['consonance']:.4f} (pool {ps['consonance_mean']:.4f})"
              f"  {b['n_notes']}음 {b['duration_sec']}s  [{b['pitch_min']}-{b['pitch_max']}]"
              f"  ({time.time()-t0:.1f}s)")

    print("\n[4/4] MIDI / WAV 렌더링...")
    manifest = []
    for name, r in tracks.items():
        stem = f"topo_{name.lower()}"
        mid = os.path.join(OUT_DIR, f"{stem}.mid")
        write_midi(r["notes"], mid)
        entry = {"track": name, "midi": os.path.relpath(mid, TDA_ROOT).replace("\\", "/"),
                 **{k: v for k, v in r["best"].items()},
                 "om_bits": r["om_bits"], "om_T": r["om_T"], "om_K": r["om_K"],
                 "om_stats": om_stats[name], "pool_stats": r["pool_stats"]}
        if not args.no_wav:
            wav = os.path.join(OUT_DIR, f"{stem}.wav")
            try:
                dur = render_wav(mid, wav)
                entry["wav"] = os.path.relpath(wav, TDA_ROOT).replace("\\", "/")
                entry["wav_seconds"] = round(dur, 1)
                mb = os.path.getsize(wav) / 1e6
                print(f"  {name:<11} → {stem}.wav  {dur:.1f}s  {mb:.1f}MB")
            except Exception as e:
                entry["wav_error"] = f"{type(e).__name__}: {e}"
                print(f"  {name:<11} → WAV 실패: {e}")
        manifest.append(entry)

    out = os.path.join(STEP3_DIR, "topo_music_manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"experiment": "topo_music", "tempo_bpm": TEMPO_BPM,
                   "sec_per_8th": SEC_PER_8TH, "n_candidates": N_CANDIDATES,
                   "selection": "1차 pitch-JS 중앙값 게이트 → 2차 협화도 최대",
                   "tracks": manifest}, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*76}\n매니페스트: {out}")
    print(f"출력 폴더: {OUT_DIR}   (총 {time.time()-t_total:.1f}s)")


if __name__ == "__main__":
    main()
