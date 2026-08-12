"""
recompute_free_region_js.py — 모티브 간 프로파일 JS 를 **자유영역만으로** 다시 잰다

왜 필요한가
──────────
`motif_control.py` 가 보고한 cross-motif profile JS 는 OM **전 영역**에서 계산됐다.
그런데 모티브는 시간의 26.7% 를 **직접 차지**한다. 서로 다른 모티브를 심으면
그 26.7% 만으로도 프로파일이 달라지므로, 전 영역 JS 는 "지시가 결과를 갈랐다"의
증거가 아니라 **"내가 넣은 것이 거기 있다"의 동어반복**을 상당 부분 포함한다.

진짜 질문은 "모델이 **채운 곳**이 모티브에 따라 달라지는가"이다.
그래서 마스크 **밖** 셀만으로 cycle 활성 프로파일을 다시 만들어 JS 를 잰다.

결과는 `docs/step3_data/motif_control_results.json` 의
`cross_motif_profile_js_free_region` 키로 되쓴다 (기존 키는 보존).

실행:  python tools/recompute_free_region_js.py
"""

from __future__ import annotations

import io
import json
import os

import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TDA_ROOT = os.path.dirname(TOOLS_DIR)
RESULTS = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")


def js_divergence(p, q, eps: float = 1e-10) -> float:
    p = np.asarray(p, dtype=np.float64) + eps
    q = np.asarray(q, dtype=np.float64) + eps
    p /= p.sum()
    q /= q.sum()
    m = 0.5 * (p + q)
    kl = lambda a, b: float(np.sum(a * np.log(a / b)))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def bits_to_bool(bits: str, T: int, K: int) -> np.ndarray:
    return (np.frombuffer(bits.encode("ascii"), dtype=np.uint8) == ord("1")).reshape(T, K)


def main() -> None:
    with io.open(RESULTS, encoding="utf-8") as f:
        data = json.load(f)

    # 렌더된 변주(v1/v2)만 om_bits 를 갖고 있다. 뼈대(skeleton)는 모티브 그 자체라 제외.
    by_motif = {}
    for t in data["tracks"]:
        if t.get("role") not in ("v1", "v2"):
            continue
        om = bits_to_bool(t["om_bits"], t["om_T"], t["om_K"])
        mk = bits_to_bool(t["mask_bits"], t["om_T"], t["om_K"])
        by_motif.setdefault(t["motif"], []).append((om, mk))

    prof_all, prof_free, n_free = {}, {}, {}
    for m, vs in by_motif.items():
        pa, pf = [], []
        for om, mk in vs:
            pa.append(om.mean(axis=0))
            free = ~mk
            pf.append(np.array([om[free[:, c], c].mean() if free[:, c].any() else 0.0
                                for c in range(om.shape[1])]))
            n_free[m] = int(free.sum())
        prof_all[m] = np.mean(pa, axis=0)
        prof_free[m] = np.mean(pf, axis=0)

    names = sorted(by_motif)
    all_js, free_js = {}, {}
    print(f"{'쌍':8s} {'전영역(기존)':>14s} {'자유영역만':>12s} {'배율':>7s}")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ja = js_divergence(prof_all[a], prof_all[b])
            jf = js_divergence(prof_free[a], prof_free[b])
            all_js[f"{a}-{b}"] = ja
            free_js[f"{a}-{b}"] = jf
            print(f"{a}-{b:6s} {ja:>14.5f} {jf:>12.5f} {jf/ja if ja else float('nan'):>6.2f}x")

    mx_a = max(all_js, key=all_js.get)
    mx_f = max(free_js, key=free_js.get)
    mn_f = min(free_js, key=free_js.get)
    print(f"\n최대 — 전영역 {mx_a} ({all_js[mx_a]:.5f}) / 자유영역 {mx_f} ({free_js[mx_f]:.5f})")
    print(f"최소 — 자유영역 {mn_f} ({free_js[mn_f]:.5f})")

    data["cross_motif_profile_js_free_region"] = free_js
    data["cross_motif_profile_js_recomputed_all_region"] = all_js
    data["free_region_note"] = (
        "cross_motif_profile_js(원본)는 OM 전 영역에서 계산돼 모티브가 직접 차지하는 "
        "26.7% 를 포함한다 — 그만큼 동어반복이 섞인다. free_region 판은 마스크 밖 셀만으로 "
        "다시 잰 것으로, '모델이 채운 곳이 모티브에 따라 달라지는가'에 답한다. "
        f"표본은 모티브당 렌더된 변주 {min(len(v) for v in by_motif.values())}개뿐이라 "
        "쌍마다 1개 비교에 해당한다 — 순위는 잠정으로 읽어야 한다."
    )
    with io.open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n기록: {os.path.relpath(RESULTS, TDA_ROOT)}")


if __name__ == "__main__":
    main()
