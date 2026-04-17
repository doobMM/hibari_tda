"""
gen_hibari_viz_dft.py — DFT metric 기반 tonnetz_demo 데이터 생성

DFT metric 캐시(cache/metric_dft.pkl)로부터 top-10 cycle overlap 데이터를
tonnetz_demo/js/hibari_overlap_dft_data.js 로 내보냅니다.
barcode 애니메이션용 hibari_barcode_dft_data.js도 생성합니다.

사용법:
  cd C:\\WK14\\tda_pipeline
  python gen_hibari_viz_dft.py
"""
import os, sys, json, re, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline
from config import PipelineConfig
from weights import (
    compute_intra_weights,
    compute_inter_weights_decayed,
    compute_distance_matrix,
    compute_out_of_reach,
)
from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance
from topology import generate_barcode_numpy

OUT_DIR = os.path.join(os.path.dirname(__file__), "tonnetz_demo", "js")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "cache", "metric_dft.pkl")
RATE_LIST = [round(r * 0.1, 1) for r in range(16)]
OW = 0.3
TOP_K = 10   # 시각화에 표시할 상위 cycle 수
BLOCK_SIZE = 4  # 시간 다운샘플링 블록 크기

# DFT 기반 DEMO_CYCLES — hybari가 주로 사용하는 diatonic note 집합
# DFT metric이 파악하는 주요 구조는 pitch class set의 Fourier magnitude로 구분됨
# tonnetz 상에서 triad 연관성이 있는 cycle pcs를 사용
DFT_DEMO_CYCLES = [
    {"name": "A", "label": "E-G-B",   "pcs": [4, 7, 11]},
    {"name": "B", "label": "C-E-G",   "pcs": [0, 4, 7]},
    {"name": "C", "label": "D-F-A",   "pcs": [2, 5, 9]},
    {"name": "D", "label": "F-A-C-E", "pcs": [0, 4, 5, 9]},
]


def parse_vertices_from_generator(gen_str: str) -> set:
    vertices = set()
    for n in re.findall(r'\d+', str(gen_str)):
        vertices.add(int(n))
    return vertices


def compute_cycle_strengths_dft(barcode, idx_to_pc):
    strengths = {dc["name"]: 0.0 for dc in DFT_DEMO_CYCLES}
    cycle_pcs_sets = {dc["name"]: set(dc["pcs"]) for dc in DFT_DEMO_CYCLES}
    for entry in barcode:
        if entry[0] != 1:
            continue
        b, d = entry[1][0], entry[1][1]
        if d == "infty" or not isinstance(d, (int, float)):
            continue
        if not isinstance(b, (int, float)):
            continue
        persistence = float(d) - float(b)
        if persistence <= 0:
            continue
        gen_str = entry[2] if len(entry) > 2 else ""
        vertices = parse_vertices_from_generator(gen_str)
        pcs = {idx_to_pc.get(str(v), idx_to_pc.get(v)) for v in vertices}
        pcs.discard(None)
        for dc in DFT_DEMO_CYCLES:
            if len(pcs & cycle_pcs_sets[dc["name"]]) >= 2:
                strengths[dc["name"]] += persistence
    return strengths


def generate_overlap_js(ov_df, cycle_labeled, idx_to_pc):
    """DFT overlap matrix → JS 파일 생성."""
    density = ov_df.mean(axis=0)
    top_k_cols = density.nlargest(TOP_K).index.tolist()

    # 각 cycle의 pitch classes 구성
    cycle_pcs = {}
    for col in top_k_cols:
        note_indices = cycle_labeled.get(col, ())
        pcs = sorted(set(idx_to_pc.get(ni, idx_to_pc.get(str(ni))) for ni in note_indices) - {None})
        cycle_pcs[str(col)] = pcs

    # 시간 다운샘플링 (block_size=4)
    T = len(ov_df)
    T_down = T // BLOCK_SIZE
    sub = ov_df[top_k_cols].values  # (T, K)
    matrix = []
    for b in range(T_down):
        block = sub[b*BLOCK_SIZE:(b+1)*BLOCK_SIZE, :]
        row = [int(block[:, c].max()) for c in range(len(top_k_cols))]
        matrix.append(row)

    data = {
        "cycle_ids": [int(c) for c in top_k_cols],
        "cycle_pcs": cycle_pcs,
        "T_total": T,
        "T_down": T_down,
        "block_size": BLOCK_SIZE,
        "matrix": matrix,
        "metric": "dft",
    }
    out_path = os.path.join(OUT_DIR, "hibari_overlap_dft_data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.HIBARI_OVERLAP_DFT_DATA = ")
        f.write(json.dumps(data))
        f.write(";\n")
    print(f"[OK] {out_path}")
    print(f"  top-{TOP_K} cycles: {[int(c) for c in top_k_cols]}")
    print(f"  cycle pcs: {cycle_pcs}")
    return data


def generate_barcode_js(p, notes_label, notes_dict, adn_i, config, idx_to_pc):
    """DFT 기반 rate별 barcode 데이터 생성."""
    num_notes = config.midi.num_notes
    num_chords = config.midi.num_chords

    print("[2] DFT 거리 행렬 계산...")
    m_dist = compute_note_distance_matrix(notes_label, metric='dft', octave_weight=OW)

    print("[3] 가중치 행렬 계산...")
    w1 = compute_intra_weights(adn_i[1][0], num_chords)
    w2 = compute_intra_weights(adn_i[2][0], num_chords)
    intra_w = w1 + w2
    inter_w = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=num_chords)
    oor = compute_out_of_reach(inter_w)

    print("[4] Rate별 PH 계산 (16 rates)...")
    rate_data_list = []
    raw_strengths_all = {dc["name"]: [] for dc in DFT_DEMO_CYCLES}

    for rate in RATE_LIST:
        print(f"  rate={rate:.1f}", end="  ")
        combined = intra_w + rate * inter_w
        freq_dist = compute_distance_matrix(combined, notes_dict, oor, num_notes=num_notes)
        # DFT hybrid: alpha=0.5 → 50% freq + 50% DFT
        hybrid = compute_hybrid_distance(freq_dist.values, m_dist, alpha=0.5)
        barcode = generate_barcode_numpy(
            hybrid, listOfDimension=[1], exactStep=True,
            annotate=True, onlyFiniteInterval=True,
        )
        finite_h1 = [e for e in barcode
                     if e[0]==1 and isinstance(e[1][0],(int,float))
                     and isinstance(e[1][1],(int,float)) and e[1][1]!="infty"]
        n_h1 = len(finite_h1)
        print(f"H₁={n_h1}", end="  ")
        raw_s = compute_cycle_strengths_dft(finite_h1, idx_to_pc)
        for k, v in raw_s.items():
            raw_strengths_all[k].append(v)
        all_intervals = [
            {"birth": round(float(e[1][0]),6), "death": round(float(e[1][1]),6)}
            for e in finite_h1
        ]
        rate_data_list.append({
            "rate": rate, "n_h1": n_h1,
            "raw_strengths": {k: round(v,6) for k,v in raw_s.items()},
            "all_intervals": all_intervals,
        })
        print()

    max_s = {dc["name"]: max(raw_strengths_all[dc["name"]] or [1.0]) for dc in DFT_DEMO_CYCLES}
    for rd in rate_data_list:
        rd["cycle_strengths"] = {
            dc["name"]: round(rd["raw_strengths"][dc["name"]] / max(max_s[dc["name"]], 1e-10), 6)
            for dc in DFT_DEMO_CYCLES
        }

    barcode_data = {
        "idx_to_pc": idx_to_pc,
        "oor": oor,
        "demo_cycles": DFT_DEMO_CYCLES,
        "rate_data": [
            {"rate": rd["rate"], "n_h1": rd["n_h1"],
             "cycle_strengths": rd["cycle_strengths"],
             "all_intervals": rd["all_intervals"]}
            for rd in rate_data_list
        ],
        "metric": "dft",
    }
    out_path = os.path.join(OUT_DIR, "hibari_barcode_dft_data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.HIBARI_BARCODE_DFT_DATA = ")
        f.write(json.dumps(barcode_data, ensure_ascii=False))
        f.write(";\n")
    print(f"\n[OK] {out_path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[0] DFT 캐시 로드...")
    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    ov_df = cache["overlap"]         # (1088, 17) binary OM
    cycle_labeled = cache["cycle_labeled"]  # {col_idx: (note_indices,...)}
    print(f"  overlap shape: {ov_df.shape}, cycles: {len(cycle_labeled)}")

    print("[1] 전처리...")
    config = PipelineConfig()
    config.midi.auto_detect = True
    p = TDAMusicPipeline(config)
    p.run_preprocessing()

    notes_label = p._cache["notes_label"]
    notes_dict  = p._cache["notes_dict"]
    adn_i       = p._cache.get("adn_i")

    sorted_notes = sorted(notes_label.items(), key=lambda x: x[1])
    idx_to_pc = {}
    for (pitch, dur), lbl in sorted_notes:
        idx_to_pc[str(lbl - 1)] = int(pitch) % 12
        idx_to_pc[lbl - 1] = int(pitch) % 12  # int key도 등록

    # cycle_labeled의 key가 0-based column index인지 확인
    # overlap df columns = 0~16 (0-based cycle indices)
    print("[A] Overlap JS 생성...")
    generate_overlap_js(ov_df, cycle_labeled, idx_to_pc)

    print("[B] Barcode JS 생성 (약 5-10분 소요)...")
    generate_barcode_js(p, notes_label, notes_dict, adn_i, config, idx_to_pc)

    print("\n완료. tonnetz_demo에서 'DFT' 버튼으로 전환 가능합니다.")


if __name__ == "__main__":
    main()
