"""
motif_control.py — 중심 모티브를 중첩행렬로 주면 음악이 통제된다

목표 (사용자 정의)
─────────────────
  "hibari 로부터 출발해서, **중심 모티브를 중첩행렬을 이용해 제공하면**
   출력되는 음악을 **통제**하는 경우"

즉 필요한 것은 무작위 생성이 아니라 **조건부 생성**이다.
그리고 디퓨전에서 조건부 생성은 **재학습이 필요 없다** — 학습된 무조건부 모델을
그대로 사전분포로 쓰고, 매 디노이징 스텝에서 아는 영역을 덮어쓰면 된다.
이것이 RePaint(CVPR 2022) 방식이며, `run_topo_diffusion.py` 가 학습한
위상 손실 디노이저를 그대로 악기로 바꾼다.

세 가지 통제 축
──────────────
  1. **모티브가 무엇인가**  — 다른 모티브 → 다른 음악
  2. **어디에 놓는가**      — 배치 위치가 곡의 형식을 만든다(론도처럼 반복)
  3. **얼마나 남기는가**    — 마스크가 넓을수록 통제가 강하고, 좁을수록 모델이 자유롭다

"중심 모티브"의 정의
───────────────────
곡 안에서 **가장 자주 되풀이되는 위상적 몸짓**. 길이 L 의 창 각각에 대해
곡의 다른 위치에서 같은 cycle 활성 패턴이 몇 번 재현되는지 세고, 가장 많이
재현되는 것을 고른다. hibari 의 phase-shifting 반복 구조와 직접 맞물린다.

RePaint 핵심
───────────
  x_{i-1} = mask ⊙ q(motif, i-1)  +  (1-mask) ⊙ p_θ(x_i)
아는 영역은 원본 모티브를 그 시점의 노이즈 수준으로 흐린 값으로 강제하고,
모르는 영역만 모델이 채운다. 저노이즈 구간에서는 **되돌림 재샘플링(jump)** 을
넣어 경계가 어색하지 않게 조화시킨다.

실행
────
  python experiments/motif_control.py                 # 모티브 추출 + 통제 검증 + 음악
  python experiments/motif_control.py --no-wav
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

from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, K, OUT_DIR, REAL_TAU, STEP3_DIR, TDA_ROOT, WINDOW,
    DDPM, TopoConvUNet, consonance_score, h0_runs_np, js_divergence_profiles,
    load_continuous_om, per_cycle_activation_profile, temporal_autocorr,
)
from make_topo_music import (
    SEC_PER_8TH, TEMPERATURES, generate_with_temperature, render_wav, write_midi,
)

MOTIF_LEN = 8              # 8 스텝 = 1 마디 (§2 정의)
N_MOTIFS = 3               # 추출할 중심 모티브 수
SONG_T = 240               # 약 1분 50초
# 모티브를 놓는 자리 — 되풀이가 형식을 만든다. 32스텝(=4마디)마다 = 시간의 26.7% 고정.
# hibari 자체가 phase-shifting 반복곡이므로 오스티나토식 배치가 양식적으로도 맞다.
PLACEMENTS = [0, 32, 64, 96, 128, 160, 192, 224]
PLACEMENTS_SPARSE = [0, 64, 128, 192]            # 통제 약한 대조 (13.3%)
N_VARIATIONS = 4           # 같은 모티브로 뽑는 변주 수
JUMP_U = 4                 # RePaint 되돌림 재샘플링 횟수 (저노이즈 구간)
JUMP_FROM = 0.35           # 마지막 35% 구간에서만 jump — 비용 대비 효과
N_CANDIDATES = 24


# ═══════════════════════════════════════════════════════════════════════════
# 1. 중심 모티브 추출
# ═══════════════════════════════════════════════════════════════════════════

def extract_central_motifs(om_bin: np.ndarray, L: int = MOTIF_LEN,
                           n: int = N_MOTIFS) -> List[dict]:
    """
    (T,K) 이진 OM 에서 '가장 자주 되풀이되는 길이 L 패치' n개.

    재현 횟수 = 다른 위치의 같은 길이 패치와 셀 일치율이 상위인 개수.
    서로 겹치거나 거의 같은 모티브는 제외해 n개가 실제로 다르게 나오게 한다.
    """
    T = om_bin.shape[0]
    patches = np.stack([om_bin[s:s + L].reshape(-1) for s in range(T - L + 1)])
    P = patches.shape[0]

    # 활성이 너무 적은 패치는 모티브로 의미 없음
    active_counts = patches.sum(axis=1)
    valid = active_counts >= max(3, int(0.08 * L * om_bin.shape[1]))

    scores = np.zeros(P)
    for i in range(P):
        if not valid[i]:
            continue
        agree = (patches == patches[i]).mean(axis=1)
        agree[max(0, i - L):i + L] = 0.0            # 자기 자신·인접 창 제외
        scores[i] = float((agree >= 0.90).sum())    # 90% 이상 일치 = 재현

    def cycle_set(s: int) -> set:
        p = om_bin[s:s + L]
        return {c for c in range(p.shape[1]) if p[:, c].any()}

    def jaccard(a: set, b: set) -> float:
        return len(a & b) / max(1, len(a | b))

    # greedy maximin — 되풀이 횟수가 높으면서 이미 고른 것과 **충분히 다른** 것만.
    # 이 조건이 없으면 t=952 / t=950 처럼 사실상 같은 모티브가 뽑혀
    # "다른 모티브 → 다른 음악" 검증 자체가 성립하지 않는다.
    order = np.argsort(-scores)
    chosen: List[dict] = []
    for i in order:
        if scores[i] <= 0:
            break
        cs = cycle_set(int(i))
        too_close = any(
            abs(int(i) - c["start"]) < 4 * L                       # 시간상 인접
            or (patches[i] == c["flat"]).mean() >= 0.80            # 패치가 거의 같음
            or jaccard(cs, c["cycles"]) >= 0.60                    # 쓰는 cycle 집합이 겹침
            for c in chosen)
        if too_close:
            continue
        chosen.append({"start": int(i), "score": float(scores[i]), "cycles": cs,
                       "flat": patches[i].copy(),
                       "patch": om_bin[i:i + L].copy()})
        if len(chosen) >= n:
            break
    return chosen


def synthetic_motif(cycles: List[int], L: int = MOTIF_LEN, k: int = K,
                    pattern: str = "sustain") -> np.ndarray:
    """
    hibari 밖에서 온 모티브. 원곡이 잘 쓰지 않는 cycle 조합을 일부러 넣어
    "낯선 모티브를 줘도 통제가 되는가"를 확인하는 대조군.
      sustain — 지정 cycle 이 창 내내 켜짐 (긴 지속음처럼)
      pulse   — 두 스텝마다 점멸 (맥박처럼)
    """
    p = np.zeros((L, k), dtype=np.float32)
    for c in cycles:
        if pattern == "pulse":
            p[::2, c] = 1.0
        else:
            p[:, c] = 1.0
    return p


def motif_signature(patch: np.ndarray) -> dict:
    """모티브를 사람이 읽을 수 있는 형태로."""
    active_cycles = [int(c) for c in range(patch.shape[1]) if patch[:, c].any()]
    return {"n_active_cells": int(patch.sum()),
            "active_cycles": active_cycles,
            "n_active_cycles": len(active_cycles),
            "density": float(patch.mean())}


# ═══════════════════════════════════════════════════════════════════════════
# 2. RePaint — 모티브 조건부 샘플링 (MultiDiffusion 융합 포함)
# ═══════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def _fused_eps(model, x: torch.Tensor, i: int, starts: List[int],
               wwin: torch.Tensor, win: int) -> torch.Tensor:
    """
    겹치는 창들의 ε 예측을 Hann 가중 평균 — 창 하나로 학습한 모델을 임의 길이에.
    창들을 **한 배치로 묶어** 한 번에 통과시킨다 (CPU에서 13회 순차 호출보다 훨씬 빠름).
    """
    crops = torch.cat([x[:, :, s:s + win] for s in starts], dim=0)      # (W,K,win)
    t = torch.full((len(starts),), i, dtype=torch.long)
    eps_w = model(crops, t) * wwin                                      # (W,K,win)

    eps_acc = torch.zeros_like(x)
    w_acc = torch.zeros_like(x)
    for j, s in enumerate(starts):
        eps_acc[0, :, s:s + win] += eps_w[j]
        w_acc[0, :, s:s + win] += wwin[0]
    return eps_acc / w_acc


@torch.no_grad()
def sample_with_motif(model: TopoConvUNet, ddpm: DDPM, total_T: int,
                      known01: np.ndarray, mask: np.ndarray, seed: int,
                      win: int = WINDOW, stride: int = 15,
                      jump_u: int = JUMP_U, jump_from: float = JUMP_FROM) -> np.ndarray:
    """
    known01 : (T,K) ∈[0,1] — 사용자가 준 중첩행렬 (마스크 밖 값은 무시된다)
    mask    : (T,K) ∈{0,1} — 1인 곳은 **그대로 유지**, 0인 곳만 모델이 채운다
    반환    : (T,K) ∈[0,1]
    """
    model.eval()
    g = torch.Generator().manual_seed(seed)

    known = torch.from_numpy(known01.T[None].astype(np.float32)) * 2.0 - 1.0   # (1,K,T)
    m = torch.from_numpy(mask.T[None].astype(np.float32))

    starts = list(range(0, total_T - win + 1, stride))
    if starts[-1] != total_T - win:
        starts.append(total_T - win)
    wwin = torch.hann_window(win, periodic=False).clamp_min(1e-3)[None, None, :]

    x = torch.randn((1, K, total_T), generator=g)
    jump_start = int(ddpm.T * jump_from)

    for i in reversed(range(ddpm.T)):
        u_reps = jump_u if i < jump_start else 1
        for u in range(u_reps):
            eps = _fused_eps(model, x, i, starts, wwin, win)
            x0 = ddpm.pred_x0(x, torch.tensor([i]), eps)      # [-1,1] 클리핑 포함
            mean = ddpm.post_c0[i] * x0 + ddpm.post_ct[i] * x
            x_unknown = (mean + torch.sqrt(ddpm.post_var[i]) * torch.randn(x.shape, generator=g)
                         if i > 0 else mean)

            # 아는 영역: 원본 모티브를 i-1 노이즈 수준으로 흐려 강제
            if i > 0:
                a = ddpm.sqrt_ac[i - 1]
                b = ddpm.sqrt_1mac[i - 1]
                x_known = a * known + b * torch.randn(x.shape, generator=g)
            else:
                x_known = known
            x = m * x_known + (1.0 - m) * x_unknown

            # 되돌림 — 경계를 조화시킨다 (마지막 반복 뒤엔 하지 않음)
            if u < u_reps - 1 and i > 0:
                x = (torch.sqrt(ddpm.alphas[i]) * x
                     + torch.sqrt(ddpm.betas[i]) * torch.randn(x.shape, generator=g))

    return torch.clamp((x + 1.0) / 2.0, 0, 1)[0].T.numpy().astype(np.float32)


def build_motif_canvas(patch: np.ndarray, total_T: int,
                       placements: List[int]) -> Tuple[np.ndarray, np.ndarray]:
    """모티브를 지정 위치들에 심은 (known, mask)."""
    L = patch.shape[0]
    known = np.zeros((total_T, patch.shape[1]), dtype=np.float32)
    mask = np.zeros_like(known)
    for p in placements:
        if p + L > total_T:
            continue
        known[p:p + L] = patch
        mask[p:p + L] = 1.0
    return known, mask


# ═══════════════════════════════════════════════════════════════════════════
# 3. 통제가 실제로 되는지 검증
# ═══════════════════════════════════════════════════════════════════════════

def motif_fidelity(generated01: np.ndarray, known: np.ndarray, mask: np.ndarray) -> float:
    """마스크 영역에서 모티브가 그대로 살아남았는가 (이진화 후 일치율)."""
    gb = (generated01 >= REAL_TAU).astype(np.float32)
    idx = mask > 0.5
    if idx.sum() == 0:
        return 1.0
    return float((gb[idx] == known[idx]).mean())


def pairwise_difference(oms: List[np.ndarray], mask: np.ndarray) -> float:
    """마스크 **밖** 영역에서 변주끼리 얼마나 다른가 (통제 ≠ 복제 확인)."""
    free = mask < 0.5
    if free.sum() == 0 or len(oms) < 2:
        return 0.0
    bs = [(o >= REAL_TAU).astype(np.float32)[free] for o in oms]
    return float(np.mean([np.mean(bs[i] != bs[j])
                          for i in range(len(bs)) for j in range(i + 1, len(bs))]))


# ═══════════════════════════════════════════════════════════════════════════
# 4. 음악화
# ═══════════════════════════════════════════════════════════════════════════

def best_music_for_om(om_bin: np.ndarray, data: dict, cycle_labeled: dict,
                      orig_flat, tag: str, n_cand: int = N_CANDIDATES) -> dict:
    """OM 하나 → 후보 n개 → JS 게이트 → 협화도 최대."""
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    cands = []
    for i in range(n_cand):
        seed = int(rng.integers(1000, 999999))
        temp = TEMPERATURES[i % len(TEMPERATURES)]
        gen = generate_with_temperature(data, cycle_labeled, om_bin, seed, temp)
        if not gen:
            continue
        cands.append({"seed": seed, "temperature": temp, "notes": gen,
                      "js": pitch_distribution_similarity(gen, orig_flat)["js_divergence"],
                      "consonance": consonance_score(gen)})
    if not cands:
        return {}
    med = float(np.median([c["js"] for c in cands]))
    passed = [c for c in cands if c["js"] <= med] or cands
    b = max(passed, key=lambda c: c["consonance"])
    pitches = [p for _, p, _ in b["notes"]]
    return {"seed": b["seed"], "temperature": b["temperature"], "js": b["js"],
            "consonance": b["consonance"], "n_notes": len(b["notes"]),
            "pitch_min": int(min(pitches)), "pitch_max": int(max(pitches)),
            "duration_sec": round(max(e for _, _, e in b["notes"]) * SEC_PER_8TH, 1),
            "notes": b["notes"]}


# ═══════════════════════════════════════════════════════════════════════════
# 5. 메인
# ═══════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wav", action="store_true")
    ap.add_argument("--variant", default="full")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    os.chdir(TDA_ROOT)
    os.makedirs(OUT_DIR, exist_ok=True)
    t_total = time.time()

    print("=" * 80)
    print("중심 모티브로 음악을 통제한다 — RePaint 조건부 샘플링")
    print("=" * 80)

    # ── 모티브 추출 ──
    om = load_continuous_om()
    om_bin = (om >= REAL_TAU).astype(np.float32)
    motifs = extract_central_motifs(om_bin)

    # hibari 가 잘 쓰지 않는 cycle 조합을 대조군으로 하나 추가한다 —
    # "낯선 모티브를 줘도 통제되는가"가 통제력의 진짜 시험이다.
    used = set().union(*[m["cycles"] for m in motifs]) if motifs else set()
    rare = [c for c in range(K) if c not in used][:3] or [0, 6, 9]
    motifs.append({"start": -1, "score": 0.0, "cycles": set(rare),
                   "flat": None, "patch": synthetic_motif(rare, pattern="pulse"),
                   "synthetic": True})

    print(f"\n[1/5] 중심 모티브 {len(motifs)}개 (길이 {MOTIF_LEN} 스텝 = 1 마디)")
    for i, mo in enumerate(motifs):
        sig = motif_signature(mo["patch"])
        origin = ("hibari 외부(대조군, 점멸)" if mo.get("synthetic")
                  else f"hibari t={mo['start']:4d} 재현 {mo['score']:.0f}회")
        print(f"  모티브 {chr(65+i)}: {origin}  "
              f"활성 {sig['n_active_cells']}셀  cycle {sig['active_cycles']}")

    # ── 모델 ──
    ckpt_path = os.path.join(CACHE_DIR, f"topo_diffusion_{args.variant}.pt")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model = TopoConvUNet()
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    ddpm = DDPM()
    print(f"\n[2/5] 디노이저 로드: {os.path.basename(ckpt_path)} "
          f"(best_ep={ckpt['meta'].get('best_epoch')} val={ckpt['meta'].get('best_val_mse',0):.4f})")

    # ── 조건부 샘플링 ──
    print(f"\n[3/5] 모티브 조건부 생성 — T={SONG_T}, 배치 {PLACEMENTS}, "
          f"모티브당 변주 {N_VARIATIONS}개")
    results: Dict[str, dict] = {}
    for i, mo in enumerate(motifs):
        name = chr(65 + i)
        known, mask = build_motif_canvas(mo["patch"], SONG_T, PLACEMENTS)
        oms, fids = [], []
        for v in range(N_VARIATIONS):
            t0 = time.time()
            out = sample_with_motif(model, ddpm, SONG_T, known, mask, seed=9000 + i * 31 + v)
            oms.append(out)
            fids.append(motif_fidelity(out, known, mask))
            print(f"  모티브 {name} 변주 {v+1}/{N_VARIATIONS}  "
                  f"모티브 보존 {fids[-1]*100:.1f}%  ({time.time()-t0:.1f}s)")
        diff = pairwise_difference(oms, mask)
        results[name] = {"motif": mo, "known": known, "mask": mask,
                         "oms": oms, "fidelity": float(np.mean(fids)),
                         "free_region_difference": diff}
        print(f"  → 모티브 {name}: 보존 {np.mean(fids)*100:.1f}%, "
              f"자유영역 변주간 차이 {diff*100:.1f}%")

    # ── 통제 검증 ──
    print("\n[4/5] 통제 검증")
    print(f"  {'모티브':<8} {'보존율':>8} {'변주간차이':>10} {'밀도/스텝':>10} "
          f"{'autocorr':>9} {'H0runs':>7}")
    control = {}
    for name, r in results.items():
        arr = np.stack([(o >= REAL_TAU).astype(np.float32) for o in r["oms"]])
        dens = float(arr.sum(axis=(1, 2)).mean() / SONG_T)
        ac = temporal_autocorr(arr)
        runs, runlen = h0_runs_np(arr)
        control[name] = {"fidelity": r["fidelity"],
                         "free_region_difference": r["free_region_difference"],
                         "density_per_step": dens, "temporal_autocorr": ac,
                         "h0_runs_per_cycle": runs, "mean_run_length": runlen,
                         "profile": [float(v) for v in per_cycle_activation_profile(arr)]}
        print(f"  {name:<8} {r['fidelity']*100:>7.1f}% {r['free_region_difference']*100:>9.1f}% "
              f"{dens:>10.2f} {ac:>9.4f} {runs:>7.2f}")

    # 서로 다른 모티브가 서로 다른 결과를 내는가
    names = list(control.keys())
    cross = {}
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            na, nb = names[a], names[b]
            cross[f"{na}-{nb}"] = js_divergence_profiles(
                np.array(control[na]["profile"]), np.array(control[nb]["profile"]))
    print("  모티브 간 cycle 프로파일 JS (클수록 통제가 결과를 갈랐다는 뜻):")
    for k, v in cross.items():
        print(f"    {k}: {v:.5f}")

    # 세 번째 통제 축 — 마스크를 얼마나 넓게 잡느냐 (통제 강도 노브)
    print("\n  통제 강도 노브: 고정 비율 ↔ 변주 자유도 (모티브 A 기준)")
    coverage = {}
    for label, pl in (("sparse_13pct", PLACEMENTS_SPARSE), ("dense_27pct", PLACEMENTS)):
        kn, mk = build_motif_canvas(motifs[0]["patch"], SONG_T, pl)
        outs = [sample_with_motif(model, ddpm, SONG_T, kn, mk, seed=7700 + j)
                for j in range(2)]
        coverage[label] = {
            "mask_fraction": float(mk.mean()),
            "fidelity": float(np.mean([motif_fidelity(o, kn, mk) for o in outs])),
            "free_region_difference": pairwise_difference(outs, mk),
        }
        c = coverage[label]
        print(f"    {label:<12} 고정 {c['mask_fraction']*100:4.1f}%  "
              f"보존 {c['fidelity']*100:5.1f}%  자유영역 차이 {c['free_region_difference']*100:5.1f}%")

    # ── 음악화 ──
    print("\n[5/5] 음악 생성 + 렌더링")
    data = suite.setup_hibari()
    orig_flat = list(data["inst1_real"]) + list(data["inst2_real"])
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cycle_labeled = pickle.load(f)["cycle_labeled"]

    manifest = []
    for name, r in results.items():
        # (a) 모티브만 — 자유영역을 비워 둔 뼈대. "이것이 모티브다"를 귀로 확인시킨다.
        # (b),(c) 같은 모티브에서 나온 변주 둘.
        renders = [("skeleton", r["known"] * r["mask"])] + \
                  [(f"v{v+1}", o) for v, o in enumerate(r["oms"][:2])]
        for label, o in renders:
            ob = (o >= REAL_TAU).astype(np.float32)
            tag = f"motif{name}_{label}"
            mus = best_music_for_om(ob, data, cycle_labeled, orig_flat, tag)
            if not mus:
                continue
            stem = f"topo_{tag}"
            mid = os.path.join(OUT_DIR, f"{stem}.mid")
            write_midi(mus["notes"], mid)
            entry = {"track": tag, "motif": name, "role": label,
                     "midi": f"{stem}.mid",
                     "om_bits": "".join("1" if q else "0" for q in ob.reshape(-1).astype(int)),
                     "om_T": SONG_T, "om_K": K,
                     "mask_bits": "".join("1" if q else "0"
                                          for q in r["mask"].reshape(-1).astype(int)),
                     **{k: q for k, q in mus.items() if k != "notes"},
                     "control": control[name]}
            if not args.no_wav:
                wav = os.path.join(OUT_DIR, f"{stem}.wav")
                try:
                    entry["wav_seconds"] = round(render_wav(mid, wav), 1)
                    entry["wav"] = f"{stem}.wav"
                except Exception as e:
                    entry["wav_error"] = f"{type(e).__name__}: {e}"
            manifest.append(entry)
            print(f"  {tag:<14} JS={mus['js']:.5f} 협화={mus['consonance']:.4f} "
                  f"{mus['n_notes']}음 {mus['duration_sec']}s")

    payload = {
        "experiment": "motif_control",
        "goal": "중심 모티브를 중첩행렬로 제공 → 출력 음악을 통제",
        "method": "RePaint 조건부 샘플링 (재학습 없음) + MultiDiffusion 창 융합",
        "config": {"motif_len": MOTIF_LEN, "song_T": SONG_T, "placements": PLACEMENTS,
                   "n_variations": N_VARIATIONS, "jump_u": JUMP_U,
                   "jump_from": JUMP_FROM, "variant": args.variant},
        "motifs": {chr(65 + i): {**motif_signature(m["patch"]),
                                 "source_t": m["start"], "recurrence": m["score"],
                                 "synthetic": bool(m.get("synthetic", False)),
                                 "bits": "".join("1" if q else "0"
                                                 for q in m["patch"].reshape(-1).astype(int))}
                   for i, m in enumerate(motifs)},
        "control": control,
        "cross_motif_profile_js": cross,
        "coverage_knob": coverage,
        "tracks": manifest,
        "total_seconds": time.time() - t_total,
    }
    out = os.path.join(STEP3_DIR, "motif_control_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*80}\n저장: {out}   ({time.time()-t_total:.1f}s)")


if __name__ == "__main__":
    main()
