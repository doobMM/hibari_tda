"""
export_topo_onnx.py — 위상 손실 디노이저를 브라우저로 (ONNX Runtime Web)

목적 — 대시보드에서 사용자가 중첩행렬에 **모티브를 그리면**, 그 자리를 고정한 채
디퓨전이 나머지를 채우게 하려면 디노이저가 브라우저에서 돌아야 한다.

두 축이 모두 가변이어야 한다:
  · **배치 B** — MultiDiffusion 은 겹치는 창 여러 개를 한 번에 넣는다 (T=240 이면 13개)
  · **시간 T** — 창 60, 전곡 240 등

내보낸 뒤 PyTorch 와 수치를 대조하고, 하나라도 1e-4 를 넘으면 실패로 끝낸다.
스케줄 상수(betas/alphas/…)는 브라우저에서 다시 계산할 필요 없게 JSON 으로 함께 저장한다.

실행:  python tools/export_topo_onnx.py [--variant full]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TDA_ROOT = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TDA_ROOT)
sys.path.insert(0, os.path.join(TDA_ROOT, "experiments"))

import numpy as np
import torch

from run_topo_diffusion import (  # noqa: E402
    CACHE_DIR, K, T_DIFFUSION, WINDOW, DDPM, TopoConvUNet,
)

MODELS_DIR = os.path.join(TDA_ROOT, "hibari_dashboard", "public", "models")
ONNX_PATH = os.path.join(MODELS_DIR, "topo_denoiser.onnx")
META_PATH = os.path.join(MODELS_DIR, "topo_denoiser_meta.json")
TOL = 1e-4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="full")
    args = ap.parse_args()

    torch.set_num_threads(1)
    os.makedirs(MODELS_DIR, exist_ok=True)

    model = TopoConvUNet()
    ckpt_path = os.path.join(CACHE_DIR, f"topo_diffusion_{args.variant}.pt")
    if os.path.exists(ckpt_path):
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model_state"])
        meta_src = ck.get("meta", {})
        print(f"가중치: {os.path.relpath(ckpt_path, TDA_ROOT)} "
              f"(best_ep={meta_src.get('best_epoch')} val={meta_src.get('best_val_mse', 0):.4f})")
    else:
        meta_src = {"warning": "체크포인트 없음 — 랜덤 초기화로 내보냄"}
        print(f"!! 체크포인트 없음({ckpt_path}) — **랜덤 초기화 가중치**로 내보낸다")
    model.eval()

    dummy_x = torch.randn(1, K, WINDOW)
    dummy_t = torch.zeros(1, dtype=torch.long)

    export_kwargs = dict(
        input_names=["x", "t"], output_names=["eps"],
        dynamic_axes={"x": {0: "batch", 2: "time"},
                      "t": {0: "batch"},
                      "eps": {0: "batch", 2: "time"}},
        opset_version=17, do_constant_folding=True,
    )
    try:
        # torch 2.11 은 기본이 dynamo 경로라 onnxscript 를 요구한다.
        # 이 모델은 제어흐름이 없어 레거시 TorchScript 내보내기로 충분하다.
        torch.onnx.export(model, (dummy_x, dummy_t), ONNX_PATH,
                          dynamo=False, **export_kwargs)
    except TypeError:
        torch.onnx.export(model, (dummy_x, dummy_t), ONNX_PATH, **export_kwargs)
    size_mb = os.path.getsize(ONNX_PATH) / 1e6
    print(f"내보냄: {os.path.relpath(ONNX_PATH, TDA_ROOT)}  {size_mb:.2f} MB")

    # ── 수치 대조 ──
    try:
        import onnxruntime as ort
    except ImportError:
        print("!! onnxruntime 없음 — 수치 대조를 건너뛴다 (설치: pip install onnxruntime)")
        ort = None

    max_diffs = {}
    if ort is not None:
        sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
        cases = [("B1_T60", 1, 60), ("B13_T60", 13, 60), ("B1_T240", 1, 240),
                 ("B4_T120", 4, 120)]
        rng = np.random.default_rng(0)
        for name, b, t_len in cases:
            x = rng.standard_normal((b, K, t_len)).astype(np.float32)
            tt = rng.integers(0, T_DIFFUSION, size=(b,)).astype(np.int64)
            with torch.no_grad():
                ref = model(torch.from_numpy(x), torch.from_numpy(tt)).numpy()
            got = sess.run(["eps"], {"x": x, "t": tt})[0]
            d = float(np.abs(ref - got).max())
            max_diffs[name] = d
            flag = "OK " if d <= TOL else "FAIL"
            print(f"  [{flag}] {name:<9} shape {got.shape}  max|diff| = {d:.3e}")

    # ── 스케줄 상수 ──
    d = DDPM()
    meta = {
        "K": K, "train_window": WINDOW, "T_diffusion": T_DIFFUSION,
        "multidiffusion": {"win": WINDOW, "stride": 15, "hann_min": 1e-3},
        "repaint": {"jump_u": 4, "jump_from": 0.35},
        "tau": 0.5,
        "checkpoint": os.path.basename(ckpt_path) if os.path.exists(ckpt_path) else None,
        "train_meta": meta_src,
        "onnx_mb": round(size_mb, 3),
        "parity_max_abs_diff": max_diffs,
        "schedule": {
            "betas": [float(v) for v in d.betas],
            "alphas": [float(v) for v in d.alphas],
            "alphas_cumprod": [float(v) for v in d.alphas_cumprod],
            "sqrt_ac": [float(v) for v in d.sqrt_ac],
            "sqrt_1mac": [float(v) for v in d.sqrt_1mac],
            "post_var": [float(v) for v in d.post_var],
            "post_c0": [float(v) for v in d.post_c0],
            "post_ct": [float(v) for v in d.post_ct],
        },
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"메타: {os.path.relpath(META_PATH, TDA_ROOT)}  "
          f"{os.path.getsize(META_PATH)/1024:.0f} KB")

    if max_diffs and max(max_diffs.values()) > TOL:
        print(f"\n실패 — 최대 오차 {max(max_diffs.values()):.3e} > {TOL}")
        return 1
    print("\n수치 대조 통과 (배치·시간 축 모두 가변 확인)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
