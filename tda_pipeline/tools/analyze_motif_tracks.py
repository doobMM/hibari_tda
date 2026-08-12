"""
tools/analyze_motif_tracks.py — 모티브 통제 트랙 12개의 음악적 분석

`experiments/motif_control.py` 가 만든
output/topo_diffusion/topo_motif{A,B,C,D}_{skeleton,v1,v2}.mid 12개를
원곡 Ryuichi_Sakamoto_-_hibari.mid 와 비교해 4개 항목(음역/화음/리듬/모티브간 차이)을
정량화한다. 위상(OM) 지표가 아니라 **음악 표면**(pretty_midi 로 읽은 실제 note)을 본다.

이 스크립트는 pretty_midi 로 MIDI 를 읽기만 한다 — 학습·추론·PH 계산 없음 (가벼움).

실행:
    python tools/analyze_motif_tracks.py

출력:
    docs/step3_data/motif_music_analysis.json   (전체 수치 원본)
    표준출력에 마크다운 표 (docs/motif_music_analysis.md 작성 시 그대로 대조용으로 사용)
"""

from __future__ import annotations

import json
import os
import warnings
from typing import Dict, List, Tuple

import numpy as np
import pretty_midi
from scipy import stats

warnings.filterwarnings("ignore", category=RuntimeWarning, module="pretty_midi")

TDA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIBARI_PATH = os.path.join(TDA_ROOT, "Ryuichi_Sakamoto_-_hibari.mid")
MOTIF_DIR = os.path.join(TDA_ROOT, "output", "topo_diffusion")
OUT_JSON = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_music_analysis.json")

BPM = 66
STEP_SEC = 60.0 / BPM / 2.0          # 8분음표 = 0.454545... s (motif_control.py SEC_PER_8TH 과 동일)
PLACEMENTS = [0, 32, 64, 96, 128, 160, 192, 224]   # experiments/motif_control.py
MOTIF_LEN = 8
SONG_T = 240

MOTIFS = ["A", "B", "C", "D"]
ROLES = ["skeleton", "v1", "v2"]
EPS = 1e-10


# ═══════════════════════════════════════════════════════════════════════════
# 0. 로딩
# ═══════════════════════════════════════════════════════════════════════════

def load_notes(path: str) -> Tuple[List[dict], float, int]:
    """모든 instrument 의 note 를 하나의 리스트로 합쳐 반환."""
    pm = pretty_midi.PrettyMIDI(path)
    notes = []
    for ii, inst in enumerate(pm.instruments):
        for n in inst.notes:
            notes.append({"pitch": int(n.pitch), "start": float(n.start),
                          "end": float(n.end), "velocity": int(n.velocity), "inst": ii})
    notes.sort(key=lambda d: d["start"])
    return notes, float(pm.get_end_time()), len(pm.instruments)


def step_index(t: float) -> int:
    return int(round(t / STEP_SEC))


def group_chords(notes: List[dict]) -> Dict[int, List[dict]]:
    """8분음표 스텝 grid 로 note 를 묶어 '동시에 울리는 화음'을 구성."""
    chords: Dict[int, List[dict]] = {}
    for n in notes:
        s = step_index(n["start"])
        chords.setdefault(s, []).append(n)
    return chords


# ═══════════════════════════════════════════════════════════════════════════
# 통계 유틸
# ═══════════════════════════════════════════════════════════════════════════

def js_divergence(counts_p: Dict, counts_q: Dict) -> float:
    """eval_metrics.pitch_distribution_similarity 와 동일한 정의
    (자연로그, eps=1e-10 스무딩, 대칭 JS)."""
    keys = sorted(set(counts_p) | set(counts_q))
    if not keys:
        return 0.0
    pt = sum(counts_p.values()) or 1
    qt = sum(counts_q.values()) or 1
    p = np.array([counts_p.get(k, 0) / pt + EPS for k in keys])
    q = np.array([counts_q.get(k, 0) / qt + EPS for k in keys])
    p /= p.sum()
    q /= q.sum()
    m = 0.5 * (p + q)
    return float(0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m)))


def bimodality_coefficient(x: np.ndarray) -> float:
    """Sarle's bimodality coefficient (population moments).
    BC > 5/9 (=0.5556, 균등분포 기준값) 이면 이봉(또는 다봉) 형태로 본다."""
    n = len(x)
    if n < 4:
        return float("nan")
    skew = float(stats.skew(x, bias=True))
    kurt = float(stats.kurtosis(x, fisher=True, bias=True))  # excess kurtosis
    return (skew ** 2 + 1.0) / (kurt + 3.0)


def largest_interior_gap(pitches: np.ndarray) -> dict:
    """IQR(25~75%) 내부에서 가장 큰 '빈 반음 구간'을 찾는다.
    두 성부가 음역으로 분리돼 있다면 중앙 부근에 뚜렷한 gap 이 남아야 한다."""
    q25, q50, q75 = np.percentile(pitches, [25, 50, 75])
    uniq = np.unique(pitches)
    best = {"gap_semitones": 0, "valley_pitch": float(q50),
            "low_edge": None, "high_edge": None}
    for i in range(len(uniq) - 1):
        lo, hi = int(uniq[i]), int(uniq[i + 1])
        mid = (lo + hi) / 2.0
        if q25 <= mid <= q75:
            gap = hi - lo
            if gap > best["gap_semitones"]:
                best = {"gap_semitones": int(gap), "valley_pitch": float(mid),
                        "low_edge": lo, "high_edge": hi}
    mass_below = float(np.mean(pitches <= best["valley_pitch"]))
    best["mass_below"] = mass_below
    best["mass_above"] = 1.0 - mass_below
    return best


def pitch_summary(notes: List[dict]) -> dict:
    p = np.array([n["pitch"] for n in notes])
    q0, q25, q50, q75, q100 = np.percentile(p, [0, 25, 50, 75, 100])
    gap = largest_interior_gap(p)
    bc = bimodality_coefficient(p)
    return {
        "n_notes": len(p), "min": int(q0), "p25": float(q25), "median": float(q50),
        "p75": float(q75), "max": int(q100), "iqr_semitones": float(q75 - q25),
        "range_semitones": int(q100 - q0),
        "bimodality_coefficient": bc,
        "gap": gap,
        "hist": {int(k): int(v) for k, v in
                 zip(*np.unique(p, return_counts=True))},
    }


def interval_class_hist(chords: Dict[int, List[dict]]) -> Tuple[Dict[int, int], dict]:
    ic_counts = {i: 0 for i in range(7)}
    chord_sizes = {}
    for step, ns in chords.items():
        pitches = [n["pitch"] for n in ns]
        chord_sizes[len(pitches)] = chord_sizes.get(len(pitches), 0) + 1
        for i in range(len(pitches)):
            for j in range(i + 1, len(pitches)):
                d = abs(pitches[i] - pitches[j]) % 12
                ic = min(d, 12 - d)
                ic_counts[ic] += 1
    return ic_counts, chord_sizes


def onset_density_curve(notes: List[dict], n_steps: int) -> np.ndarray:
    arr = np.zeros(n_steps, dtype=float)
    for n in notes:
        s = step_index(n["start"])
        if 0 <= s < n_steps:
            arr[s] += 1
    return arr


def autocorr(x: np.ndarray, lag: int) -> float:
    x = x - x.mean()
    denom = float(np.sum(x * x))
    if denom == 0 or lag >= len(x):
        return float("nan")
    num = float(np.sum(x[:-lag] * x[lag:]))
    return num / denom


def autocorr_full(x: np.ndarray, max_lag: int) -> np.ndarray:
    return np.array([autocorr(x, lag) for lag in range(1, max_lag + 1)])


def rank_of_lag(ac: np.ndarray, lag: int) -> int:
    """ac 배열(인덱스0=lag1)에서 주어진 lag 값의 내림차순 순위(1=최댓값)."""
    idx = lag - 1
    if idx < 0 or idx >= len(ac) or np.isnan(ac[idx]):
        return -1
    order = np.argsort(-ac)
    return int(np.where(order == idx)[0][0]) + 1


# ═══════════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════════

MASK_STEPS = set()
for _p in PLACEMENTS:
    MASK_STEPS.update(range(_p, _p + MOTIF_LEN))


def analyze_track(name: str, path: str, n_steps_for_autocorr: int) -> dict:
    notes, dur, n_inst = load_notes(path)
    chords = group_chords(notes)
    ic_counts, chord_sizes = interval_class_hist(chords)
    dens = onset_density_curve(notes, n_steps_for_autocorr)
    ac = autocorr_full(dens, min(80, n_steps_for_autocorr - 1))
    peak_lag = int(np.nanargmax(ac)) + 1  # ac[0] == lag 1
    rank32 = rank_of_lag(ac, 32) if n_steps_for_autocorr > 32 else -1

    in_mask_density = out_mask_density = None
    if n_steps_for_autocorr == SONG_T:
        in_idx = sorted(MASK_STEPS & set(range(n_steps_for_autocorr)))
        out_idx = sorted(set(range(n_steps_for_autocorr)) - MASK_STEPS)
        in_mask_density = float(dens[in_idx].mean()) if in_idx else None
        out_mask_density = float(dens[out_idx].mean()) if out_idx else None
    return {
        "name": name, "path": os.path.relpath(path, TDA_ROOT).replace("\\", "/"),
        "duration_sec": dur, "n_instruments": n_inst, "n_notes": len(notes),
        "pitch": pitch_summary(notes),
        "n_chords": len(chords),
        "chord_size_hist": {str(k): v for k, v in sorted(chord_sizes.items())},
        "mean_chord_size": float(np.mean([len(v) for v in chords.values()])) if chords else 0.0,
        "interval_class_hist": ic_counts,
        "density_curve": dens.tolist(),
        "autocorr_lag32": float(autocorr(dens, 32)) if n_steps_for_autocorr > 32 else None,
        "autocorr_lag32_rank": rank32,
        "autocorr_peak_lag": peak_lag,
        "autocorr_peak_value": float(ac[peak_lag - 1]),
        "density_mean": float(dens.mean()),
        "density_std": float(dens.std()),
        "density_mean_in_motif_window": in_mask_density,
        "density_mean_out_motif_window": out_mask_density,
    }


def main():
    results = {"config": {"bpm": BPM, "step_sec": STEP_SEC, "placements": PLACEMENTS,
                           "motif_len": MOTIF_LEN, "song_T": SONG_T},
               "tracks": {}}

    print("=" * 100)
    print("[0] 로딩")
    print("=" * 100)

    hibari = analyze_track("hibari", HIBARI_PATH, n_steps_for_autocorr=1088)
    results["tracks"]["hibari"] = hibari
    print(f"hibari: {hibari['n_notes']} notes, {hibari['n_instruments']} instruments, "
          f"{hibari['duration_sec']:.1f}s, pitch [{hibari['pitch']['min']}, {hibari['pitch']['max']}]")

    # 원곡 두 트랙이 진짜 별개 성부인지(음역이 다른지) 확인 — 전제 검증
    pm = pretty_midi.PrettyMIDI(HIBARI_PATH)
    if len(pm.instruments) == 2:
        p0 = np.array([n.pitch for n in pm.instruments[0].notes])
        p1 = np.array([n.pitch for n in pm.instruments[1].notes])
        results["hibari_raw_instrument_check"] = {
            "inst0_n": len(p0), "inst0_range": [int(p0.min()), int(p0.max())],
            "inst1_n": len(p1), "inst1_range": [int(p1.min()), int(p1.max())],
        }
        print(f"  raw inst0: n={len(p0)} range=[{p0.min()},{p0.max()}] / "
              f"inst1: n={len(p1)} range=[{p1.min()},{p1.max()}]")
        # 두 트랙이 내용까지 동일한지 (phase-shift 중복) 확인
        set0 = set((round(n.start, 3), n.pitch) for n in pm.instruments[0].notes)
        set1 = set((round(n.start, 3), n.pitch) for n in pm.instruments[1].notes)
        # inst1을 -1 step 만큼 되돌렸을 때 inst0과 얼마나 겹치는지
        shifted1 = set((round(s - STEP_SEC, 3), p) for (s, p) in set1)
        overlap_ratio = len(set0 & shifted1) / max(1, len(set0))
        results["hibari_raw_instrument_check"]["phase_shift_overlap_ratio"] = overlap_ratio
        print(f"  inst1을 -1 step 시프트 후 inst0과 겹침 비율: {overlap_ratio:.3f} "
              f"(1.0에 가까우면 두 트랙이 1스텝 위상차 복제)")

        # 단일 성부(inst0)만으로 화음 통계 — 생성 트랙(단일 트랙)과 공정 비교용
        notes0 = [{"pitch": int(n.pitch), "start": float(n.start), "end": float(n.end),
                   "velocity": int(n.velocity), "inst": 0} for n in pm.instruments[0].notes]
        chords0 = group_chords(notes0)
        ic0, sizes0 = interval_class_hist(chords0)
        mean_size0 = float(np.mean([len(v) for v in chords0.values()])) if chords0 else 0.0
        results["hibari_inst0_only"] = {
            "n_notes": len(notes0), "n_chords": len(chords0), "mean_chord_size": mean_size0,
            "chord_size_hist": {str(k): v for k, v in sorted(sizes0.items())},
            "interval_class_hist": ic0,
        }
        print(f"  hibari inst0 단독: n_chords={len(chords0)} mean_chord_size={mean_size0:.3f} "
              f"hist={ {k: v for k, v in sorted(sizes0.items())} }")

        # pitch-class 어휘 확인 (음역 gap이 진짜 성부분리인지, 그냥 빠진 음계음인지)
        allp = np.concatenate([p0, p1])
        pcs_used = sorted(set(int(p) % 12 for p in allp))
        results["hibari_pitch_classes_used"] = pcs_used
        print(f"  hibari가 쓰는 pitch class (0=C): {pcs_used}  (빠짐: {sorted(set(range(12)) - set(pcs_used))})")

    print()
    for m in MOTIFS:
        for r in ROLES:
            fname = f"topo_motif{m}_{r}.mid"
            fpath = os.path.join(MOTIF_DIR, fname)
            if not os.path.exists(fpath):
                print(f"  (없음, 건너뜀) {fname}")
                continue
            key = f"{m}_{r}"
            tr = analyze_track(key, fpath, n_steps_for_autocorr=SONG_T)
            results["tracks"][key] = tr
            print(f"{key}: {tr['n_notes']} notes, pitch[{tr['pitch']['min']},{tr['pitch']['max']}] "
                  f"median={tr['pitch']['median']:.0f} BC={tr['pitch']['bimodality_coefficient']:.3f} "
                  f"ac(lag32)={tr['autocorr_lag32']:.3f} ac_peak=lag{tr['autocorr_peak_lag']}"
                  f"({tr['autocorr_peak_value']:.3f})")

    # ── 표 1: 음역 구조 ──────────────────────────────────────────────
    print()
    print("=" * 100)
    print("[표 1] 음역 구조 (pitch)")
    print("=" * 100)
    header = f"{'track':16s} {'n':>5s} {'min':>4s} {'p25':>5s} {'med':>5s} {'p75':>5s} {'max':>4s} {'range':>6s} {'BC':>7s} {'gap':>4s} {'valley':>7s} {'mass<':>6s} {'mass>':>6s}"
    print(header)
    for key in ["hibari"] + [f"{m}_{r}" for m in MOTIFS for r in ROLES if f"{m}_{r}" in results["tracks"]]:
        t = results["tracks"][key]
        ps = t["pitch"]
        g = ps["gap"]
        print(f"{key:16s} {ps['n_notes']:5d} {ps['min']:4d} {ps['p25']:5.1f} {ps['median']:5.1f} "
              f"{ps['p75']:5.1f} {ps['max']:4d} {ps['range_semitones']:6d} "
              f"{ps['bimodality_coefficient']:7.3f} {g['gap_semitones']:4d} {g['valley_pitch']:7.1f} "
              f"{g['mass_below']:6.3f} {g['mass_above']:6.3f}")

    # ── 표 2: 화음 구조 ──────────────────────────────────────────────
    print()
    print("=" * 100)
    print("[표 2] 화음 구조 — 동시음 개수 분포 & 평균")
    print("=" * 100)
    for key in ["hibari"] + [f"{m}_{r}" for m in MOTIFS for r in ROLES if f"{m}_{r}" in results["tracks"]]:
        t = results["tracks"][key]
        print(f"{key:16s} n_chords={t['n_chords']:5d} mean_size={t['mean_chord_size']:.3f} "
              f"hist={t['chord_size_hist']}")

    print()
    print("[표 2b] Interval class 히스토그램 (%, IC0=유니즌/옥타브 ~ IC6=트라이톤)")
    ic_header = f"{'track':16s} " + " ".join(f"IC{i:>5d}" for i in range(7))
    print(ic_header)
    for key in ["hibari"] + [f"{m}_{r}" for m in MOTIFS for r in ROLES if f"{m}_{r}" in results["tracks"]]:
        t = results["tracks"][key]
        total = sum(t["interval_class_hist"].values()) or 1
        pcts = [100.0 * t["interval_class_hist"][i] / total for i in range(7)]
        print(f"{key:16s} " + " ".join(f"{p:7.2f}" for p in pcts))

    print()
    print("[표 2c] hibari 대비 — 생성 트랙 12개를 하나로 합친 interval-class 비율 (%p 차이 = 생성 - hibari)")
    hib_ic = results["tracks"]["hibari"]["interval_class_hist"]
    hib_total = sum(hib_ic.values())
    gen_ic_all = {i: 0 for i in range(7)}
    for m in MOTIFS:
        for r in ROLES:
            key = f"{m}_{r}"
            if key in results["tracks"]:
                for i in range(7):
                    gen_ic_all[i] += results["tracks"][key]["interval_class_hist"][i]
    gen_total = sum(gen_ic_all.values())
    print(f"{'IC':4s} {'hibari%':>9s} {'생성전체%':>10s} {'차이(%p)':>10s}")
    ic_compare = {}
    for i in range(7):
        hp = 100.0 * hib_ic[i] / hib_total
        gp = 100.0 * gen_ic_all[i] / gen_total
        ic_compare[str(i)] = {"hibari_pct": hp, "generated_pooled_pct": gp, "diff_pp": gp - hp}
        print(f"IC{i:<2d} {hp:9.2f} {gp:10.2f} {gp-hp:10.2f}")
    results["ic_hibari_vs_generated_pooled"] = ic_compare
    results["ic_js_hibari_vs_generated_pooled"] = js_divergence(hib_ic, gen_ic_all)
    print(f"JS(hibari, 생성전체 pooled interval-class) = {results['ic_js_hibari_vs_generated_pooled']:.5f}")

    hib_pitch_hist = results["tracks"]["hibari"]["pitch"]["hist"]
    gen_pitch_hist_all = {}
    for m in MOTIFS:
        for r in ROLES:
            key = f"{m}_{r}"
            if key in results["tracks"]:
                for k, v in results["tracks"][key]["pitch"]["hist"].items():
                    gen_pitch_hist_all[k] = gen_pitch_hist_all.get(k, 0) + v
    results["pitch_js_hibari_vs_generated_pooled"] = js_divergence(hib_pitch_hist, gen_pitch_hist_all)
    print(f"JS(hibari, 생성전체 pooled pitch) = {results['pitch_js_hibari_vs_generated_pooled']:.5f}")

    # 화음 크기(밀도) 비교: hibari 단일성부 대비 생성 12트랙
    hib1_mean = results["hibari_inst0_only"]["mean_chord_size"]
    gen_sizes = [results["tracks"][f"{m}_{r}"]["mean_chord_size"] for m in MOTIFS for r in ROLES
                 if f"{m}_{r}" in results["tracks"]]
    print(f"hibari(단일 성부) mean_chord_size={hib1_mean:.3f} vs 생성 12트랙 평균={np.mean(gen_sizes):.3f} "
          f"(범위 {min(gen_sizes):.3f}~{max(gen_sizes):.3f})")
    results["chord_size_hibari_inst0_vs_generated"] = {
        "hibari_inst0_mean": hib1_mean, "generated_mean": float(np.mean(gen_sizes)),
        "generated_min": float(min(gen_sizes)), "generated_max": float(max(gen_sizes)),
    }

    # ── 표 3: 리듬/밀도 (자기상관) ──────────────────────────────────
    print()
    print("=" * 100)
    print("[표 3] 리듬/밀도 — onset density 자기상관 (lag=32 이 모티브 배치 주기)")
    print("=" * 100)
    print(f"{'track':16s} {'density_mean':>12s} {'in_window':>10s} {'out_window':>11s} {'ratio':>7s} {'ac(lag32)':>10s} {'rank32':>7s} {'ac_peak_lag':>12s} {'ac_peak_val':>12s}")
    for key in [f"{m}_{r}" for m in MOTIFS for r in ROLES if f"{m}_{r}" in results["tracks"]]:
        t = results["tracks"][key]
        ratio = (t["density_mean_in_motif_window"] / t["density_mean_out_motif_window"]
                 if t["density_mean_out_motif_window"] else float("inf"))
        print(f"{key:16s} {t['density_mean']:12.4f} {t['density_mean_in_motif_window']:10.4f} "
              f"{t['density_mean_out_motif_window']:11.4f} {ratio:7.3f} "
              f"{t['autocorr_lag32']:10.4f} {t['autocorr_lag32_rank']:7d} "
              f"{t['autocorr_peak_lag']:12d} {t['autocorr_peak_value']:12.4f}")

    print()
    print("[표 3b] 역할별(뼈대/변주) ac(lag32) 및 in/out window 밀도비 평균 — 4개 모티브 평균")
    role_avg = {}
    for r in ROLES:
        vals = [results["tracks"][f"{m}_{r}"]["autocorr_lag32"] for m in MOTIFS
                 if f"{m}_{r}" in results["tracks"]]
        ranks = [results["tracks"][f"{m}_{r}"]["autocorr_lag32_rank"] for m in MOTIFS
                  if f"{m}_{r}" in results["tracks"]]
        n_top = sum(1 for m in MOTIFS if f"{m}_{r}" in results["tracks"]
                    and results["tracks"][f"{m}_{r}"]["autocorr_peak_lag"] % 32 == 0)
        ratios = [results["tracks"][f"{m}_{r}"]["density_mean_in_motif_window"] /
                  results["tracks"][f"{m}_{r}"]["density_mean_out_motif_window"]
                  for m in MOTIFS if f"{m}_{r}" in results["tracks"]]
        role_avg[r] = {"mean_ac_lag32": float(np.mean(vals)), "mean_rank32": float(np.mean(ranks)),
                       "n_tracks_with_32multiple_as_global_peak": n_top,
                       "mean_in_out_density_ratio": float(np.mean(ratios))}
        print(f"{r:10s} mean_ac(lag32)={np.mean(vals):.4f}  mean_rank(lag32)={np.mean(ranks):.2f}  "
              f"peak가 32의 배수인 트랙 수={n_top}/{len(vals)}  mean(in/out 밀도비)={np.mean(ratios):.3f}")
    results["role_level_autocorr_summary"] = role_avg

    # ── 표 4: 모티브간 차이 (pairwise JS) ────────────────────────────
    print()
    print("=" * 100)
    print("[표 4] 모티브간 차이 — 모티브별(v1+v2+skeleton 통합) pitch / interval-class JS divergence")
    print("=" * 100)
    pooled_pitch = {}
    pooled_ic = {}
    for m in MOTIFS:
        ph = {}
        ic = {i: 0 for i in range(7)}
        for r in ROLES:
            key = f"{m}_{r}"
            if key not in results["tracks"]:
                continue
            t = results["tracks"][key]
            for k, v in t["pitch"]["hist"].items():
                ph[k] = ph.get(k, 0) + v
            for i in range(7):
                ic[i] += t["interval_class_hist"][i]
        pooled_pitch[m] = ph
        pooled_ic[m] = ic

    pairwise = {}
    print(f"{'pair':10s} {'JS_pitch':>10s} {'JS_intervalclass':>18s}")
    for i in range(len(MOTIFS)):
        for j in range(i + 1, len(MOTIFS)):
            a, b = MOTIFS[i], MOTIFS[j]
            js_p = js_divergence(pooled_pitch[a], pooled_pitch[b])
            js_i = js_divergence(pooled_ic[a], pooled_ic[b])
            pairwise[f"{a}-{b}"] = {"js_pitch": js_p, "js_interval_class": js_i}
            print(f"{a}-{b:8s} {js_p:10.5f} {js_i:18.5f}")
    results["motif_pairwise_js"] = pairwise
    results["motif_pooled_pitch_hist"] = {m: pooled_pitch[m] for m in MOTIFS}
    results["motif_pooled_ic_hist"] = {m: pooled_ic[m] for m in MOTIFS}

    # 모티브별 요약 (중앙값·범위·BC)
    print()
    print("[표 4b] 모티브별 pooled pitch 요약")
    print(f"{'motif':8s} {'n':>5s} {'min':>4s} {'median':>7s} {'max':>4s} {'BC':>7s}")
    pooled_summary = {}
    for m in MOTIFS:
        arr = []
        for pitch, c in pooled_pitch[m].items():
            arr.extend([pitch] * c)
        arr = np.array(arr)
        bc = bimodality_coefficient(arr)
        pooled_summary[m] = {"n": len(arr), "min": int(arr.min()), "median": float(np.median(arr)),
                              "max": int(arr.max()), "bc": bc}
        print(f"{m:8s} {len(arr):5d} {int(arr.min()):4d} {float(np.median(arr)):7.1f} "
              f"{int(arr.max()):4d} {bc:7.3f}")
    results["motif_pooled_summary"] = pooled_summary

    print()
    print("[표 4c] 모티브별(3역할 평균) 화음 밀도 — mean_chord_size")
    motif_chord_avg = {}
    for m in MOTIFS:
        sizes = [results["tracks"][f"{m}_{r}"]["mean_chord_size"] for r in ROLES
                 if f"{m}_{r}" in results["tracks"]]
        motif_chord_avg[m] = float(np.mean(sizes))
        print(f"{m:8s} mean_chord_size(3역할 평균)={np.mean(sizes):.3f}  (역할별: {[round(s,3) for s in sizes]})")
    results["motif_mean_chord_size_avg"] = motif_chord_avg

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    # density_curve는 크므로 JSON에는 남기되 하나의 파일로 통합 저장
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print()
    print(f"저장: {OUT_JSON}")


if __name__ == "__main__":
    main()
