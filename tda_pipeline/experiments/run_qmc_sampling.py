"""
run_qmc_sampling.py — Algorithm 1 의 노드 추출을 저불일치(QMC) 로 바꾸면?

착상의 출처
──────────
`수리생물학/QMC.txt` (MATH 749 수업 메모) 에 적힌 사용자 본인의 구상:

    "제일 긴 대각선보다, 모듈 길이보다 크게? 그러면서도 coprime?"
    "lag를 규칙적으로 바꿔가며?"
    "lags로 했을 때 화음조합 등장 센스?"

이 프로젝트에도 **lag** 와 **module 길이** 가 이미 있으므로 어휘가 그대로 겹친다.

왜 통할 것 같은가 (사전 예측)
────────────────────────────
`NodePool.pool` 은 빈도만큼 **복제해 펼친 배열**이다(label 이 count 번 반복).
따라서 "풀에서 균일 추출" = "목표 분포에서 카테고리 추출" 이고,
N 개를 뽑을 때 경험분포의 오차는 다항추출 오차 **O(1/√N)** 이다.

여기서 균일난수 대신 **coprime lag 가산 순회**를 쓰면
    idx_{n+1} = (idx_n + lag) mod |pool|,   gcd(lag, |pool|) = 1
가 되어 **한 바퀴 도는 동안 모든 슬롯을 정확히 한 번씩** 방문한다.
즉 경험분포가 목표분포에 O(1/N) 로 붙는다 — 1차원 Kronecker(Weyl) 수열의 이산판이고,
lag 를 |pool|/φ (황금비) 근처로 잡으면 부분수열의 불일치도 최소가 된다.

**예측**: 음고 JS 의 평균과 **분산이 함께 줄어든다.**
(분산 감소가 특히 중요하다 — 현재 측정은 0.065 ± 0.024 로 상대오차 37% 다.)

무엇을 바꾸지 않는가
──────────────────
`generation.py` 는 건드리지 않는다. NodePool 을 상속해 `sample()` 만 갈아끼운다.
cycle 선택·onset 규칙 등 Algorithm 1 의 나머지 로직은 전부 그대로다.
따라서 차이가 나오면 **추출 방식 단독의 효과**다.

실행:  python experiments/run_qmc_sampling.py [--n-seeds 20]
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__))))
# --- end path_bootstrap ---

import argparse
import json
import math
import os
import pickle
import random
import time
from math import gcd
from typing import List, Tuple

import numpy as np

import run_dft_gap0_suite as suite
from eval_metrics import pitch_distribution_similarity
from generation import CycleSetManager, NodePool, algorithm1_optimized

from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, STEP3_DIR, TDA_ROOT,
    consonance_score, load_continuous_om,
)

PHI = (1.0 + 5 ** 0.5) / 2.0


def coprime_lag(n: int, ratio: float = 1.0 / PHI) -> int:
    """|pool| 과 서로소이면서 n·ratio 에 가장 가까운 lag. 황금비가 기본값."""
    if n <= 2:
        return 1
    target = max(1, int(round(n * ratio)))
    for d in range(0, n):
        for cand in (target - d, target + d):
            if 1 <= cand < n and gcd(cand, n) == 1:
                return cand
    return 1


class GoldenStream:
    """
    황금비 Kronecker(Weyl) 수열  u_n = frac(n·φ⁻¹).
    1차원에서 불일치가 최소인 고전적 저불일치 수열이고, **길이가 매번 달라지는 풀**에도
    그대로 쓸 수 있다 — u_n 을 [0,1) 로 두고 그때그때 len(pool) 을 곱하면 되기 때문이다.

    `QMC.txt` 의 "lag 를 규칙적으로 바꿔가며 / 반복횟수가 lag 와 coprime 인 …" 구상을
    풀 크기에 무관한 형태로 일반화한 것.
    """

    def __init__(self, seed: int = 0):
        self.alpha = 1.0 / PHI               # 0.6180339887…
        self.u = (seed * 0.7548776662) % 1.0  # 시작점만 seed 로 (또 다른 무리수)

    def next(self) -> float:
        self.u = (self.u + self.alpha) % 1.0
        return self.u

    def pick(self, seq):
        return seq[min(len(seq) - 1, int(self.next() * len(seq)))]


class QMCNodePool(NodePool):
    """
    coprime lag 가산 순회로 노드를 뽑는 NodePool.

    `NodePool.__init__` 이 풀을 seed 기반으로 셔플하므로, 시작점과 셔플이
    seed 마다 달라 **곡마다 다른 결과**가 나온다. 다만 한 곡 안에서는
    슬롯을 고르게 훑어 경험분포가 목표분포에 빨리 붙는다.
    """

    def __init__(self, *args, lag_ratio: float = 1.0 / PHI, **kwargs):
        super().__init__(*args, **kwargs)
        self.lag = coprime_lag(self.total_size, lag_ratio)
        self._i = random.randrange(self.total_size)   # 시작점만 난수

    def sample(self) -> int:
        self._i = (self._i + self.lag) % self.total_size
        return int(self.pool[self._i])


def _song_freq_weights(data, temperature):
    """0-indexed note label → 곡 내 등장빈도^(1/T).  label+1 이 notes_label 값이다."""
    inv = {lbl: note for note, lbl in data["notes_label"].items()}
    out = {}
    for lbl, note in inv.items():
        c = float(data["notes_counts"].get(note, 1))
        out[lbl - 1] = max(1e-6, c ** (1.0 / max(1e-6, temperature)))
    return out


def build_music(data, cycle_labeled, om_bin, seed, temperature, mode, lag_ratio):
    """
    mode: 'uniform'      — 원래 그대로
          'qmc_pool'     — NodePool.sample() 만 QMC (전체 결정의 약 19%)
          'qmc_full'     — + cycle 교집합 추출까지 QMC (나머지 81%)

    'qmc_full' 은 `generation.random.choice` 를 실험 동안만 갈아끼운다.
    generation.py 자체는 수정하지 않는다 — 실험이 끝나면 원래대로 되돌린다.
    """
    random.seed(seed)
    np.random.seed(seed)
    T = om_bin.shape[0]
    inst_len = (MODULES * (T // len(MODULES) + 2))[:T]

    use_pool_qmc = mode in ("qmc_pool", "qmc_full", "combined")
    # 'freq_intersect' — 교집합 추출에 **곡 내 등장빈도 + 온도**를 반영한다.
    # 현재 교집합 가중은 "활성 사이클 몇 개에 속하는가"뿐이고 NodePool 온도가 닿지 않는다.
    # 노트 결정의 81% 가 이 경로이므로, 튜닝된 T=3.0 이 사실상 19% 에만 걸려 있었다.
    cls = QMCNodePool if use_pool_qmc else NodePool
    kw = {"lag_ratio": lag_ratio} if use_pool_qmc else {}
    pool = cls(data["notes_label"], data["notes_counts"], num_modules=65,
               temperature=temperature, **kw)

    import generation as _gen
    saved = _gen.random.choice
    if mode == "qmc_full":
        stream = GoldenStream(seed)
        _gen.random.choice = lambda seq: stream.pick(seq)
    elif mode in ("freq_intersect", "combined"):
        w = _song_freq_weights(data, temperature)
        rnd = random.Random(seed ^ 0x5EED)

        def weighted(seq):
            ws = [w.get(int(z), 1.0) for z in seq]
            tot = sum(ws)
            if tot <= 0:
                return rnd.choice(seq)
            r = rnd.random() * tot
            acc = 0.0
            for z, wi in zip(seq, ws):
                acc += wi
                if r <= acc:
                    return z
            return seq[-1]
        _gen.random.choice = weighted
    try:
        gen = algorithm1_optimized(pool, list(inst_len), om_bin.astype(np.float32),
                                   CycleSetManager(cycle_labeled),
                                   max_resample=50, verbose=False, min_onset_gap=0)
    finally:
        _gen.random.choice = saved
    return gen, pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=20)
    ap.add_argument("--temperature", type=float, default=3.0)
    ap.add_argument("--window", type=int, default=240)
    args = ap.parse_args()

    os.chdir(TDA_ROOT)
    t0 = time.time()
    print("=" * 78)
    print("Algorithm 1 노드 추출: 균일난수 vs coprime-lag 저불일치(QMC)")
    print(f"  착상: 수리생물학/QMC.txt · T={args.window} · seed {args.n_seeds}개 · "
          f"온도 {args.temperature}")
    print("=" * 78)

    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]

    om = load_continuous_om()
    om_bin = (om[200:200 + args.window] >= REAL_TAU).astype(np.float32)

    seeds = [1000 + 37 * i for i in range(args.n_seeds)]
    results = {}
    for label in ("uniform", "qmc_pool", "qmc_full", "freq_intersect", "combined"):
        qmc = label in ("qmc_pool", "qmc_full", "combined")
        js, cons, nn = [], [], []
        lag = None
        for sd in seeds:
            gen, pool = build_music(data, cycle_labeled, om_bin, sd,
                                    args.temperature, label, 1.0 / PHI)
            if not gen:
                continue
            js.append(pitch_distribution_similarity(gen, orig_flat)["js_divergence"])
            cons.append(consonance_score(gen))
            nn.append(len(gen))
            if qmc and lag is None:
                lag = (pool.lag, pool.total_size)
        results[label] = {
            "pitch_js_mean": float(np.mean(js)), "pitch_js_std": float(np.std(js, ddof=1)),
            "consonance_mean": float(np.mean(cons)),
            "consonance_std": float(np.std(cons, ddof=1)),
            "n_notes_mean": float(np.mean(nn)), "n": len(js),
            "js_all": [float(v) for v in js],
        }
        if lag:
            results[label]["lag"] = lag[0]
            results[label]["pool_size"] = lag[1]
            results[label]["lag_over_pool"] = lag[0] / lag[1]
        r = results[label]
        print(f"\n[{label}]  음고 JS = {r['pitch_js_mean']:.5f} ± {r['pitch_js_std']:.5f}"
              f"   협화도 {r['consonance_mean']:.4f} ± {r['consonance_std']:.4f}"
              f"   음 {r['n_notes_mean']:.0f}개")
        if lag:
            print(f"          풀 크기 {lag[1]} · lag {lag[0]} "
                  f"(비 {lag[0]/lag[1]:.4f}, 황금비 역수 {1/PHI:.4f}) · "
                  f"gcd={gcd(lag[0], lag[1])}")

    # ── 판정 ──
    u, q = results["uniform"], results["qmc_full"]
    d_mean = (q["pitch_js_mean"] - u["pitch_js_mean"]) / u["pitch_js_mean"] * 100
    d_std = (q["pitch_js_std"] - u["pitch_js_std"]) / u["pitch_js_std"] * 100
    try:
        from scipy import stats
        t, p = stats.ttest_ind(u["js_all"], q["js_all"], equal_var=False)
        lev = stats.levene(u["js_all"], q["js_all"])
        sig = f"Welch t={t:.2f} p={p:.2e} · 분산동일성 Levene p={lev.pvalue:.2e}"
    except Exception as e:
        sig = f"(scipy 없음: {e})"

    print(f"\n{'─'*78}")
    print(f"평균 변화 {d_mean:+.1f}%   표준편차 변화 {d_std:+.1f}%")
    print(f"  {sig}")
    print("  예측 검증 — 저불일치 추출은 경험분포 오차를 O(1/√N)→O(1/N) 로 줄이므로")
    print("  **평균보다 분산이 먼저 줄어야** 한다.")

    results["comparison"] = {"delta_mean_pct": d_mean, "delta_std_pct": d_std,
                             "significance": sig}
    results["source_idea"] = "수리생물학/QMC.txt — coprime lag 가산 순회 (Weyl/Kronecker 이산판)"
    out = os.path.join(STEP3_DIR, "qmc_sampling_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
