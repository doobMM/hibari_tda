"""
run_aesthetic_rerank.py
=======================

미적 re-ranking 실험:
  - 음악이론 기반 미적 점수 A(S) ∈ [0,1] 정의
  - Algorithm 1 후보 24개 생성 → JS(구조) vs A(미적) trade-off 측정
  - M=20 배치 반복 통계 (Wilcoxon p)

실행 방법:
    python experiments/run_aesthetic_rerank.py        (루트에서)
    python run_aesthetic_rerank.py                    (experiments/ 안에서)

출력:
    docs/step3_data/aesthetic_rerank_results.json
"""

from __future__ import annotations

import json
import os
import pickle
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import stats

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from generation import CycleSetManager, NodePool, algorithm1_optimized

# suite.MIDI_FILE 은 import 시점에 experiments/ 기준으로 잡히므로 실제 위치로 교체
# (export_hibari_data.py 와 동일 패턴)
suite.MIDI_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # tda_pipeline/
    "Ryuichi_Sakamoto_-_hibari.mid",
)

# ─────────────────────────────────────────────
# 실험 설정 (현재 최적)
# ─────────────────────────────────────────────
METRIC = "dft"
ALPHA = 0.25
OCTAVE_WEIGHT = 0.3
DURATION_WEIGHT = 1.0
MIN_ONSET_GAP = 0
TEMPERATURE = 3.0          # §7.7 best_temperature
TOTAL_LENGTH = 1088        # 136마디 × 8 eighth notes
MODULES = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
           4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
INST_CHORD_HEIGHTS = MODULES * 33  # 1056 시점

K_CANDIDATES = 24          # 배치당 후보 수
M_BATCHES = 20             # 반복 배치 수
CALIB_N = 20               # calibration 비교군 크기
TAU_CANDIDATES = [0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7]

# 미적 점수 가중치
W_C = 0.4   # 협화도
W_V = 0.4   # 성부진행 부드러움
W_L = 0.2   # 도약 절제
TAU_V = 4.0  # 성부진행 스케일 (semitone, 장3도 기준)
TAU_L = 7.0  # 도약 스케일 (semitone, 완전5도 기준)

# 협화 interval class: {0,3,4,5}
CONSONANT_ICS = {0, 3, 4, 5}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # experiments/
TDA_ROOT = os.path.dirname(BASE_DIR)                            # tda_pipeline/
STEP3_DIR = os.path.join(TDA_ROOT, "docs", "step3_data")
CACHE_DIR = os.path.join(TDA_ROOT, "cache")
CACHE_NAME = "metric_dft_alpha0p25_ow0p3_dw1p0.pkl"


# ─────────────────────────────────────────────
# 미적 점수 함수
# ─────────────────────────────────────────────

def consonance_score(notes: List[Tuple[int, int, int]]) -> float:
    """
    협화도 C(S) ∈ [0,1].

    각 시점 t에서 활성화된 pitch 집합 P_t를 구성.
    chord 크기 ≥ 2 인 시점에 대해 협화 쌍 비율 계산.
    chord가 하나도 없으면 1.0 반환 (페널티 없음).
    """
    # t → 활성 pitch set 구축
    time_to_pitches: Dict[int, List[int]] = defaultdict(list)
    for start, pitch, end in notes:
        for t in range(start, end):
            time_to_pitches[t].append(pitch)

    chord_ratios = []
    for pitches in time_to_pitches.values():
        if len(pitches) < 2:
            continue
        total_pairs = 0
        consonant_pairs = 0
        for i in range(len(pitches)):
            for j in range(i + 1, len(pitches)):
                ic = abs(pitches[i] - pitches[j]) % 12
                ic = min(ic, 12 - ic)  # interval class ∈ {0..6}
                total_pairs += 1
                if ic in CONSONANT_ICS:
                    consonant_pairs += 1
        chord_ratios.append(consonant_pairs / total_pairs)

    if not chord_ratios:
        return 1.0  # chord 없으면 페널티 없음
    return float(np.mean(chord_ratios))


def voice_leading_smoothness(notes: List[Tuple[int, int, int]]) -> float:
    """
    성부진행 부드러움 V(S) ∈ (0,1].

    onset 시점별 활성 pitch 집합을 시간순으로 정렬.
    연속 두 집합 (P_a → P_b)에 대해
    motion = mean over p ∈ P_b of min_{q ∈ P_a}|p - q|.
    V(S) = exp(-avg_motion / τ_v).
    onset이 1개 이하이면 1.0 반환.
    """
    # onset 시점별 활성 pitch 집합 (note의 start 시점 기준)
    onset_to_pitches: Dict[int, List[int]] = defaultdict(list)
    for start, pitch, end in notes:
        onset_to_pitches[start].append(pitch)

    onsets = sorted(onset_to_pitches.keys())
    if len(onsets) < 2:
        return 1.0

    motions = []
    for i in range(1, len(onsets)):
        P_a = onset_to_pitches[onsets[i - 1]]
        P_b = onset_to_pitches[onsets[i]]
        # P_b의 각 음에 대해 P_a에서 가장 가까운 음까지 거리
        per_voice = [min(abs(p - q) for q in P_a) for p in P_b]
        motions.append(float(np.mean(per_voice)))

    avg_motion = float(np.mean(motions))
    return float(np.exp(-avg_motion / TAU_V))


def leap_restraint(notes: List[Tuple[int, int, int]]) -> float:
    """
    도약 절제 L(S) ∈ (0,1].

    onset 시점별 평균 pitch 시퀀스 m_1..m_T.
    연속 |m_{i+1} - m_i| 의 평균 leap.
    L(S) = exp(-avg_leap / τ_l).
    onset이 1개 이하이면 1.0 반환.
    """
    onset_to_pitches: Dict[int, List[int]] = defaultdict(list)
    for start, pitch, end in notes:
        onset_to_pitches[start].append(pitch)

    onsets = sorted(onset_to_pitches.keys())
    if len(onsets) < 2:
        return 1.0

    mean_pitches = [float(np.mean(onset_to_pitches[t])) for t in onsets]
    leaps = [abs(mean_pitches[i + 1] - mean_pitches[i]) for i in range(len(mean_pitches) - 1)]
    avg_leap = float(np.mean(leaps))
    return float(np.exp(-avg_leap / TAU_L))


def aesthetic_score(notes: List[Tuple[int, int, int]]) -> Dict[str, float]:
    """
    미적 점수 A(S) ∈ [0,1] 및 세 성분.

    Args:
        notes: [(start, pitch, end), ...] 생성 또는 원곡 note 리스트

    Returns:
        {
            "C": 협화도,
            "V": 성부진행 부드러움,
            "L": 도약 절제,
            "A": 가중 합 (0.4·C + 0.4·V + 0.2·L)
        }
    """
    C = consonance_score(notes)
    V = voice_leading_smoothness(notes)
    L = leap_restraint(notes)
    A = W_C * C + W_V * V + W_L * L
    return {"C": C, "V": V, "L": L, "A": A}


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────

def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def bundle_is_valid(bundle: dict) -> bool:
    required = {"cycle_labeled", "overlap_binary", "activation_continuous"}
    if not required.issubset(bundle.keys()):
        return False
    k = len(bundle["cycle_labeled"])
    return k > 0


def load_or_build_bundle(data: dict) -> dict:
    cache_path = os.path.join(CACHE_DIR, CACHE_NAME)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        if bundle_is_valid(cached):
            print(f"[cache] loaded: {cache_path} (K={len(cached['cycle_labeled'])})")
            return cached

    print("[info] cache not found/invalid. building PH bundle (시간 소요)...")
    fresh = suite.build_overlap_bundle(
        data, METRIC,
        alpha=ALPHA,
        octave_weight=OCTAVE_WEIGHT,
        duration_weight=DURATION_WEIGHT,
        use_decayed=False,
        threshold=0.35,
    )
    bundle = {
        "metric": fresh["metric"],
        "alpha": float(fresh["alpha"]),
        "octave_weight": float(fresh["octave_weight"]),
        "duration_weight": float(fresh["duration_weight"]),
        "cycle_labeled": fresh["cycle_labeled"],
        "overlap_binary": fresh["overlap_binary"],
        "activation_continuous": fresh["activation_continuous"],
        "ph_time_s": float(fresh["ph_time_s"]),
    }
    with open(cache_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"[cache] saved: {cache_path}")
    return bundle


def build_percycle_overlap(cont_overlap: np.ndarray, taus: List[float]) -> np.ndarray:
    """per-cycle τ 적용 → 이진 overlap 행렬 반환."""
    out = np.zeros_like(cont_overlap, dtype=np.float32)
    for ci, tau in enumerate(taus):
        out[:, ci] = (cont_overlap[:, ci] >= tau).astype(np.float32)
    return out


def greedy_percycle_tau(
    data: dict,
    cont_overlap: np.ndarray,
    cycle_labeled: dict,
    greedy_n: int = 5,
    seed_base_greedy: int = 54000,
) -> List[float]:
    """
    1-pass greedy coordinate descent로 per-cycle τ 탐색.
    (run_percycle_tau_dft_alpha025.py 동일 로직 재사용)
    """
    k = cont_overlap.shape[1]
    taus = [0.35] * k

    for ci in range(k):
        best_tau = taus[ci]
        best_mean = float("inf")
        for tj, tau in enumerate(TAU_CANDIDATES):
            cand = list(taus)
            cand[ci] = tau
            ov = build_percycle_overlap(cont_overlap, cand)
            js_vals = []
            for rep in range(greedy_n):
                seed = seed_base_greedy + ci * 1000 + tj * 100 + rep
                set_all_seeds(seed)
                pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
                mgr = CycleSetManager(cycle_labeled)
                gen = algorithm1_optimized(
                    pool, list(INST_CHORD_HEIGHTS), ov, mgr,
                    max_resample=50, verbose=False, min_onset_gap=MIN_ONSET_GAP
                )
                orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
                js = pitch_distribution_similarity(gen, orig_flat)["js_divergence"]
                js_vals.append(js)
            m = float(np.mean(js_vals))
            if m < best_mean:
                best_mean = m
                best_tau = float(tau)
        taus[ci] = best_tau

    return taus


def generate_one(
    data: dict,
    overlap_values: np.ndarray,
    cycle_labeled: dict,
    seed: int,
) -> List[Tuple[int, int, int]]:
    """seed 고정 후 Algorithm 1 한 번 생성."""
    set_all_seeds(seed)
    pool = NodePool(data["notes_label"], data["notes_counts"], num_modules=65)
    mgr = CycleSetManager(cycle_labeled)
    return algorithm1_optimized(
        pool, list(INST_CHORD_HEIGHTS), overlap_values, mgr,
        max_resample=50, verbose=False, min_onset_gap=MIN_ONSET_GAP
    )


def compute_js(generated: List[Tuple[int, int, int]], orig_flat: List[Tuple[int, int, int]]) -> float:
    return pitch_distribution_similarity(generated, orig_flat)["js_divergence"]


# ─────────────────────────────────────────────
# Step 0 — Calibration
# ─────────────────────────────────────────────

def run_calibration(
    orig_notes: List[Tuple[int, int, int]],
    seed: int = 9999,
) -> Dict[str, Any]:
    """
    지표 타당성 검증:
    원곡 A_orig vs 셔플 A_shuffle vs 무작위 A_random.
    기대: A_orig > A_shuffle > A_random.
    """
    print("\n── Calibration ──")
    rng = np.random.default_rng(seed)

    # 원곡 A
    score_orig = aesthetic_score(orig_notes)
    A_orig = score_orig["A"]
    print(f"  A_orig   = {A_orig:.4f}  (C={score_orig['C']:.3f}, V={score_orig['V']:.3f}, L={score_orig['L']:.3f})")

    # (a) pitch 셔플 ×CALIB_N — 성분별(C/V/L/A) 분해 저장
    sh = {"A": [], "C": [], "V": [], "L": []}
    pitches_only = [p for _, p, _ in orig_notes]
    for i in range(CALIB_N):
        rng_i = np.random.default_rng(seed + i)
        shuffled_p = list(pitches_only)
        rng_i.shuffle(shuffled_p)
        shuffled_notes = [(s, sp, e) for (s, _, e), sp in zip(orig_notes, shuffled_p)]
        sc = aesthetic_score(shuffled_notes)
        for kk in sh:
            sh[kk].append(sc[kk])
    A_shuffle_mean = float(np.mean(sh["A"]))
    print(f"  A_shuffle = {A_shuffle_mean:.4f} ± {np.std(sh['A']):.4f} "
          f"(C={np.mean(sh['C']):.3f}, V={np.mean(sh['V']):.3f}, L={np.mean(sh['L']):.3f})")

    # (b) 균등 무작위 pitch [48~84] ×CALIB_N
    rd = {"A": [], "C": [], "V": [], "L": []}
    for i in range(CALIB_N):
        rng_i = np.random.default_rng(seed + 1000 + i)
        rand_notes = [(start, int(rng_i.integers(48, 85)), end) for start, _, end in orig_notes]
        sc = aesthetic_score(rand_notes)
        for kk in rd:
            rd[kk].append(sc[kk])
    A_random_mean = float(np.mean(rd["A"]))
    print(f"  A_random  = {A_random_mean:.4f} ± {np.std(rd['A']):.4f} "
          f"(C={np.mean(rd['C']):.3f}, V={np.mean(rd['V']):.3f}, L={np.mean(rd['L']):.3f})")

    order_ok = (A_orig > A_shuffle_mean) and (A_shuffle_mean > A_random_mean)
    print(f"  순서 A_orig > A_shuffle > A_random: {'✓ 성립' if order_ok else '✗ 불성립 — 지표 재설계 신호'}")

    # 성분별 타당성: orig > shuffle > random 순서가 성립하는 성분 식별
    comp_valid = {}
    for comp in ("C", "V", "L"):
        o = score_orig[comp]; s = float(np.mean(sh[comp])); r = float(np.mean(rd[comp]))
        ok = (o > s) and (s > r)
        comp_valid[comp] = {"orig": o, "shuffle": s, "random": r, "order_valid": ok}
        print(f"    [{comp}] orig={o:.3f} shuffle={s:.3f} random={r:.3f} → "
              f"{'✓' if ok else '✗'}")

    return {
        "A_orig": A_orig,
        "C_orig": score_orig["C"],
        "V_orig": score_orig["V"],
        "L_orig": score_orig["L"],
        "A_shuffle_mean": A_shuffle_mean,
        "A_shuffle_std": float(np.std(sh["A"])),
        "A_random_mean": A_random_mean,
        "A_random_std": float(np.std(rd["A"])),
        "order_valid": order_ok,
        "component_calibration": comp_valid,
    }


# ─────────────────────────────────────────────
# Step 1+2 — 단일 배치: 후보 24개 생성 + 선택
# ─────────────────────────────────────────────

def run_one_batch(
    data: dict,
    overlap_values: np.ndarray,
    cycle_labeled: dict,
    orig_flat: List[Tuple[int, int, int]],
    batch_idx: int,
) -> Dict[str, Any]:
    """
    배치 1개 실행.
    - K_CANDIDATES개 후보 생성 (seed = batch_idx * K_CANDIDATES + k)
    - 각 후보의 JS_i, A_i 계산
    - Baseline(JS 최소) vs 미적 제약 선택(JS ≤ min+ε에서 A 최대) 비교
    - Pearson r(JS, A)
    """
    seed_base = batch_idx * K_CANDIDATES

    candidates_js = []
    candidates_A = []
    candidates_C = []
    candidates_V = []
    candidates_L = []

    for k in range(K_CANDIDATES):
        gen = generate_one(data, overlap_values, cycle_labeled, seed=seed_base + k)
        js_val = compute_js(gen, orig_flat)
        aes = aesthetic_score(gen)
        candidates_js.append(js_val)
        candidates_A.append(aes["A"])
        candidates_C.append(aes["C"])
        candidates_V.append(aes["V"])
        candidates_L.append(aes["L"])

    js_arr = np.array(candidates_js)
    A_arr  = np.array(candidates_A)

    # Baseline: JS 최소 후보
    baseline_idx = int(np.argmin(js_arr))
    JS_base = float(js_arr[baseline_idx])
    A_base  = float(A_arr[baseline_idx])

    # 미적 제약 선택: JS ≤ min_JS + ε (ε = std), 그 중 A 최대
    eps = float(js_arr.std(ddof=1))
    threshold_js = float(js_arr.min()) + eps
    mask = js_arr <= threshold_js
    aes_idx = int(np.where(mask)[0][np.argmax(A_arr[mask])])
    JS_aes = float(js_arr[aes_idx])
    A_aes  = float(A_arr[aes_idx])

    # 협화도-only 선택 (calibration에서 C만 유효 → C 최대, 동일 JS 제약)
    C_arr = np.array(candidates_C)
    C_base = float(C_arr[baseline_idx])
    cons_idx = int(np.where(mask)[0][np.argmax(C_arr[mask])])
    JS_cons = float(js_arr[cons_idx])
    C_cons  = float(C_arr[cons_idx])

    # Pearson r(JS, A)
    if js_arr.std() > 0 and A_arr.std() > 0:
        r, p_pearson = stats.pearsonr(js_arr, A_arr)
    else:
        r, p_pearson = 0.0, 1.0

    return {
        "batch": batch_idx,
        "JS_base": JS_base,
        "A_base": A_base,
        "JS_aes": JS_aes,
        "A_aes": A_aes,
        "C_base": C_base,
        "JS_cons": JS_cons,
        "C_cons": C_cons,
        "pearson_r": float(r),
        "pearson_p": float(p_pearson),
        "js_min": float(js_arr.min()),
        "js_std_eps": float(eps),
        "n_eligible": int(mask.sum()),
        # 성분 평균 (해석용)
        "C_mean": float(np.mean(candidates_C)),
        "V_mean": float(np.mean(candidates_V)),
        "L_mean": float(np.mean(candidates_L)),
        "A_mean": float(np.mean(candidates_A)),
    }


# ─────────────────────────────────────────────
# Step 3 — M=20 배치 반복 통계
# ─────────────────────────────────────────────

def run_batches(
    data: dict,
    overlap_values: np.ndarray,
    cycle_labeled: dict,
    orig_flat: List[Tuple[int, int, int]],
) -> Dict[str, Any]:
    batch_results = []
    print(f"\n── Step 1~2: M={M_BATCHES} 배치 반복 ──")
    for b in range(M_BATCHES):
        t0 = time.time()
        res = run_one_batch(data, overlap_values, cycle_labeled, orig_flat, batch_idx=b)
        elapsed = time.time() - t0
        print(
            f"  [batch {b:02d}]"
            f"  JS_base={res['JS_base']:.5f} A_base={res['A_base']:.4f}"
            f" | JS_aes={res['JS_aes']:.5f} A_aes={res['A_aes']:.4f}"
            f" | r={res['pearson_r']:+.3f}"
            f"  ({elapsed:.1f}s)"
        )
        batch_results.append(res)

    # 집계
    JS_base_arr = np.array([r["JS_base"] for r in batch_results])
    A_base_arr  = np.array([r["A_base"]  for r in batch_results])
    JS_aes_arr  = np.array([r["JS_aes"]  for r in batch_results])
    A_aes_arr   = np.array([r["A_aes"]   for r in batch_results])
    r_arr       = np.array([r["pearson_r"] for r in batch_results])

    # 협화도-only 전략 집계
    C_base_arr = np.array([r["C_base"] for r in batch_results])
    C_cons_arr = np.array([r["C_cons"] for r in batch_results])
    JS_cons_arr = np.array([r["JS_cons"] for r in batch_results])

    # Wilcoxon signed-rank test (paired)
    wilcox_A = stats.wilcoxon(A_aes_arr, A_base_arr)
    wilcox_JS = stats.wilcoxon(JS_aes_arr, JS_base_arr)
    wilcox_C = stats.wilcoxon(C_cons_arr, C_base_arr)
    wilcox_JScons = stats.wilcoxon(JS_cons_arr, JS_base_arr)

    summary = {
        "C_base_mean": float(C_base_arr.mean()),
        "C_base_std":  float(C_base_arr.std(ddof=1)),
        "C_cons_mean": float(C_cons_arr.mean()),
        "C_cons_std":  float(C_cons_arr.std(ddof=1)),
        "delta_C_mean": float((C_cons_arr - C_base_arr).mean()),
        "JS_cons_mean": float(JS_cons_arr.mean()),
        "delta_JS_cons_mean": float((JS_cons_arr - JS_base_arr).mean()),
        "wilcoxon_C_p": float(wilcox_C.pvalue),
        "wilcoxon_JScons_p": float(wilcox_JScons.pvalue),
        "JS_base_mean": float(JS_base_arr.mean()),
        "JS_base_std":  float(JS_base_arr.std(ddof=1)),
        "A_base_mean":  float(A_base_arr.mean()),
        "A_base_std":   float(A_base_arr.std(ddof=1)),
        "JS_aes_mean":  float(JS_aes_arr.mean()),
        "JS_aes_std":   float(JS_aes_arr.std(ddof=1)),
        "A_aes_mean":   float(A_aes_arr.mean()),
        "A_aes_std":    float(A_aes_arr.std(ddof=1)),
        "delta_A_mean": float((A_aes_arr - A_base_arr).mean()),
        "delta_A_std":  float((A_aes_arr - A_base_arr).std(ddof=1)),
        "delta_JS_mean": float((JS_aes_arr - JS_base_arr).mean()),
        "delta_JS_std":  float((JS_aes_arr - JS_base_arr).std(ddof=1)),
        "wilcoxon_A_stat":  float(wilcox_A.statistic),
        "wilcoxon_A_p":     float(wilcox_A.pvalue),
        "wilcoxon_JS_stat": float(wilcox_JS.statistic),
        "wilcoxon_JS_p":    float(wilcox_JS.pvalue),
        "pearson_r_mean":   float(r_arr.mean()),
        "pearson_r_std":    float(r_arr.std(ddof=1)),
        "pearson_r_median": float(np.median(r_arr)),
        "M": M_BATCHES,
        "K": K_CANDIDATES,
    }
    return {"batches": batch_results, "summary": summary}


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main() -> None:
    os.chdir(TDA_ROOT)   # suite 내부 상대경로(MIDI/cache)가 tda_pipeline 기준
    os.makedirs(STEP3_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    print("=" * 72)
    print("미적 Re-ranking 실험")
    print("  metric=DFT, alpha=0.25, ow=0.3, dw=1.0, gap=0")
    print(f"  K_candidates={K_CANDIDATES}, M_batches={M_BATCHES}")
    print("=" * 72)

    # ── Hibari 데이터 로드 ──
    print("\n[1/4] hibari 데이터 로드...")
    t0 = time.time()
    data = suite.setup_hibari()
    print(f"  완료 ({time.time()-t0:.1f}s)")

    # 원곡 음표 (pitch_distribution_similarity 인자용)
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    print(f"  원곡 총 음표 수: {len(orig_flat)}")

    # ── PH bundle 로드 또는 빌드 ──
    print("\n[2/4] overlap bundle 로드...")
    bundle = load_or_build_bundle(data)
    cycle_labeled = bundle["cycle_labeled"]
    cont_overlap = bundle["activation_continuous"].values.astype(np.float32)
    K = len(cycle_labeled)
    print(f"  K={K} cycles")

    # per-cycle τ 계산 (greedy)
    print("\n[3/4] per-cycle tau greedy 탐색...")
    t0 = time.time()
    tau_profile = greedy_percycle_tau(
        data, cont_overlap, cycle_labeled, greedy_n=5, seed_base_greedy=54000
    )
    overlap_values = build_percycle_overlap(cont_overlap, tau_profile)
    print(f"  tau profile: {[round(t,2) for t in tau_profile]}")
    print(f"  greedy 완료 ({time.time()-t0:.1f}s)")

    # ── Step 0: Calibration ──
    print("\n[4/4] 실험 실행...")
    calib = run_calibration(orig_flat, seed=9999)

    # ── Step 1~3: M=20 배치 ──
    batch_data = run_batches(data, overlap_values, cycle_labeled, orig_flat)
    summary = batch_data["summary"]

    # ── 최종 요약 출력 ──
    print("\n" + "=" * 72)
    print("최종 요약")
    print("=" * 72)
    print(f"\n[Calibration]")
    print(f"  A_orig    = {calib['A_orig']:.4f}  "
          f"(C={calib['C_orig']:.3f}, V={calib['V_orig']:.3f}, L={calib['L_orig']:.3f})")
    print(f"  A_shuffle = {calib['A_shuffle_mean']:.4f} ± {calib['A_shuffle_std']:.4f}")
    print(f"  A_random  = {calib['A_random_mean']:.4f} ± {calib['A_random_std']:.4f}")
    print(f"  순서 성립: {calib['order_valid']}")

    print(f"\n[M={M_BATCHES} 배치 통계]")
    print(f"  JS:  baseline={summary['JS_base_mean']:.5f}±{summary['JS_base_std']:.5f}"
          f"  →  미적선택={summary['JS_aes_mean']:.5f}±{summary['JS_aes_std']:.5f}"
          f"  (Δ={summary['delta_JS_mean']:+.5f}, Wilcoxon p={summary['wilcoxon_JS_p']:.4f})")
    print(f"  A:   baseline={summary['A_base_mean']:.4f}±{summary['A_base_std']:.4f}"
          f"  →  미적선택={summary['A_aes_mean']:.4f}±{summary['A_aes_std']:.4f}"
          f"  (Δ={summary['delta_A_mean']:+.4f}, Wilcoxon p={summary['wilcoxon_A_p']:.4f})")
    print(f"  r(JS,A): mean={summary['pearson_r_mean']:+.3f}±{summary['pearson_r_std']:.3f}"
          f"  median={summary['pearson_r_median']:+.3f}")
    print(f"\n[협화도-only 재정렬 — C만 calibration 유효]")
    print(f"  C:   baseline={summary['C_base_mean']:.4f}±{summary['C_base_std']:.4f}"
          f"  →  C선택={summary['C_cons_mean']:.4f}±{summary['C_cons_std']:.4f}"
          f"  (Δ={summary['delta_C_mean']:+.4f}, Wilcoxon p={summary['wilcoxon_C_p']:.4f})")
    print(f"  JS 희생(C선택): {summary['delta_JS_cons_mean']:+.5f} (p={summary['wilcoxon_JScons_p']:.4f})")

    # 해석
    A_improved = summary["delta_A_mean"] > 0
    JS_sacrifice = summary["delta_JS_mean"]
    A_sig = summary["wilcoxon_A_p"] < 0.05
    JS_sig = summary["wilcoxon_JS_p"] < 0.05
    print(f"\n[해석]")
    if A_improved and A_sig:
        print(f"  미적 점수 개선: +{summary['delta_A_mean']:.4f} (유의, p={summary['wilcoxon_A_p']:.4f})")
    elif A_improved and not A_sig:
        print(f"  미적 점수 소폭 개선: +{summary['delta_A_mean']:.4f} (비유의, p={summary['wilcoxon_A_p']:.4f})")
    else:
        print(f"  미적 점수 개선 없음: {summary['delta_A_mean']:.4f}")

    if JS_sig:
        print(f"  JS 희생: {JS_sacrifice:+.5f} (유의, p={summary['wilcoxon_JS_p']:.4f})")
    else:
        print(f"  JS 희생 없음: {JS_sacrifice:+.5f} (비유의, p={summary['wilcoxon_JS_p']:.4f})")

    r_m = summary["pearson_r_mean"]
    if r_m > 0.2:
        print(f"  r(JS,A)={r_m:+.3f}: 구조↑ = 미적↑ (정렬 관계)")
    elif r_m < -0.2:
        print(f"  r(JS,A)={r_m:+.3f}: 구조↑ = 미적↓ (긴장 관계 — re-ranking 의미 있음)")
    else:
        print(f"  r(JS,A)={r_m:+.3f}: 구조-미적 상관 약함 (독립)")

    # ── JSON 저장 ──
    out = {
        "config": {
            "metric": METRIC,
            "alpha": ALPHA,
            "octave_weight": OCTAVE_WEIGHT,
            "duration_weight": DURATION_WEIGHT,
            "min_onset_gap": MIN_ONSET_GAP,
            "K_candidates": K_CANDIDATES,
            "M_batches": M_BATCHES,
            "K_cycles": K,
            "tau_profile": [float(t) for t in tau_profile],
            "aesthetic_weights": {"C": W_C, "V": W_V, "L": W_L},
            "tau_v": TAU_V,
            "tau_l": TAU_L,
        },
        "calibration": calib,
        "summary": summary,
        "batches": batch_data["batches"],
    }

    out_path = os.path.join(STEP3_DIR, "aesthetic_rerank_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n저장됨: {out_path}")


if __name__ == "__main__":
    main()
