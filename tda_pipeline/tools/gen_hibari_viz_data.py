"""
gen_hibari_viz_data.py — hibari TDA 시각화 데이터 재생성

hibari_barcode_data.js + hibari_overlap_data.js 를 재생성합니다.

버그 수정 (2026-04-15):
  - Cycle C 정의 오류: [2,6,9] (D-F♯-A) → [2,5,9] (D-F-A)
    hibari는 C장조 다이아토닉 {0,2,4,5,7,9,11} 사용 → F♯(6)이 존재하지 않음

사용법:
  cd C:\\WK14\\tda_pipeline
  python gen_hibari_viz_data.py

출력:
  tonnetz_demo/js/hibari_barcode_data.js
  tonnetz_demo/js/hibari_overlap_data.js
"""

import os, sys, json, re, pickle
import numpy as np
import pandas as pd

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
from overlap import (
    label_cycles_from_persistence,
    group_rBD_by_homology,
)


# ── 올바른 Demo Cycle 정의 ─────────────────────────────────────────────────
# hibari 음계: {C,D,E,F,G,A,B} = {0,2,4,5,7,9,11}  (C장조 다이아토닉)
# F♯(pc=6)은 hibari에 존재하지 않으므로 C는 D-F-A=[2,5,9]
DEMO_CYCLES = [
    {"name": "A", "label": "E-G-B",   "pcs": [4, 7, 11]},
    {"name": "B", "label": "C-E-G",   "pcs": [0, 4, 7]},
    {"name": "C", "label": "D-F-A",   "pcs": [2, 5, 9]},   # ← 수정: [2,6,9] → [2,5,9]
    {"name": "D", "label": "F-A-C-E", "pcs": [0, 4, 5, 9]},
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "tonnetz_demo", "js")
RATE_LIST = [round(r * 0.1, 1) for r in range(16)]   # 0.0 ~ 1.5
ALPHA = 0.5      # visualization용 hybrid 비율 (alpha=0 → Tonnetz만, rate 변화 없음)
OW    = 0.3      # octave_weight (최적값)


# ── generator 문자열 → vertex 집합 파싱 ────────────────────────────────────

def parse_vertices_from_generator(gen_str: str) -> set:
    """
    topology.py의 generator 문자열에서 모든 vertex 번호를 추출합니다.
    예: "(0, 1) + (1, 3) + (0, 3)" → {0, 1, 3}
    """
    vertices = set()
    nums = re.findall(r'\d+', gen_str)
    for n in nums:
        vertices.add(int(n))
    return vertices


def compute_cycle_strengths(barcode: list, idx_to_pc: dict) -> dict:
    """
    H₁ 바코드에서 각 데모 사이클(A/B/C/D)의 강도를 계산합니다.

    각 H₁ interval에 대해:
      1. cycle representative의 vertex 집합 추출
      2. vertex → pitch class 변환 (idx_to_pc)
      3. 데모 사이클과의 pitch class 교집합 계산
      4. 교집합 크기 ≥ 2 이면 (death - birth) 을 해당 사이클 강도에 누적

    Returns:
      {cycle_name: raw_strength_value}
    """
    strengths = {dc["name"]: 0.0 for dc in DEMO_CYCLES}
    cycle_pcs_sets = {dc["name"]: set(dc["pcs"]) for dc in DEMO_CYCLES}

    for entry in barcode:
        dim = entry[0]
        if dim != 1:
            continue
        interval = entry[1]
        birth = interval[0]
        death = interval[1]

        # 무한 구간 건너뜀
        if death == "infty" or not isinstance(death, (int, float)):
            continue
        if not isinstance(birth, (int, float)):
            continue

        persistence = float(death) - float(birth)
        if persistence <= 0:
            continue

        # generator 문자열
        gen_str = entry[2] if len(entry) > 2 else ""
        vertices = parse_vertices_from_generator(str(gen_str))

        # vertex → pitch class
        pcs_in_generator = {idx_to_pc.get(str(v), idx_to_pc.get(v)) for v in vertices}
        pcs_in_generator.discard(None)

        # 데모 사이클과 교집합 계산
        for dc in DEMO_CYCLES:
            overlap_count = len(pcs_in_generator & cycle_pcs_sets[dc["name"]])
            if overlap_count >= 2:
                strengths[dc["name"]] += persistence

    return strengths


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1] TDA 파이프라인 전처리...")
    config = PipelineConfig()
    config.midi.auto_detect = True
    p = TDAMusicPipeline(config)
    p.run_preprocessing()

    notes_label  = p._cache['notes_label']
    notes_dict   = p._cache['notes_dict']
    chord_seq1   = p._cache['chord_seq1']
    chord_seq2   = p._cache['chord_seq2']
    adn_i        = p._cache.get('adn_i')
    num_notes    = config.midi.num_notes
    num_chords   = config.midi.num_chords

    # idx_to_pc: note label(0-indexed int) → pitch class
    # notes_label = {(pitch, dur): 1-indexed label}
    sorted_notes = sorted(notes_label.items(), key=lambda x: x[1])
    idx_to_pc = {}
    for (pitch, dur), lbl in sorted_notes:
        idx_to_pc[str(lbl - 1)] = int(pitch) % 12

    print(f"  notes: {len(sorted_notes)}, chords: {num_chords}")
    print(f"  pitch classes: {sorted(set(idx_to_pc.values()))}")

    # Tonnetz 거리 행렬 (고정, rate와 무관)
    print("[2] Tonnetz 거리 행렬 계산...")
    m_dist = compute_note_distance_matrix(
        notes_label, metric='tonnetz', octave_weight=OW
    )
    print(f"  m_dist shape: {m_dist.shape}")

    # 가중치 행렬 계산 — 파이프라인(_search_timeflow)과 동일한 방식
    print("[3] 가중치 행렬 계산...")
    # intra: 두 악기의 intra weight 합산 (adn_i[inst][0] = lag-0 시퀀스)
    w1 = compute_intra_weights(adn_i[1][0], num_chords)
    w2 = compute_intra_weights(adn_i[2][0], num_chords)
    intra_w = w1 + w2
    # inter: 감쇄 가중 lag 1~4
    inter_w = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=num_chords)

    # out_of_reach (inter 기반)
    oor = compute_out_of_reach(inter_w)
    print(f"  oor = {oor:.6f}")

    # ── Rate별 바코드 계산 ──────────────────────────────────────────────
    print("[4] Rate별 persistent homology 계산 (16 rates)...")
    rate_data_list = []
    raw_strengths_all = {dc["name"]: [] for dc in DEMO_CYCLES}

    for rate in RATE_LIST:
        print(f"  rate={rate:.1f}", end="  ")

        # timeflow = intra + rate * inter
        combined = intra_w + rate * inter_w

        # frequency 기반 거리 행렬
        freq_dist = compute_distance_matrix(
            combined, notes_dict, oor, num_notes=num_notes
        )

        # hybrid: 50% freq + 50% Tonnetz (alpha=0.5 → rate 변화가 topology에 반영됨)
        hybrid = compute_hybrid_distance(freq_dist.values, m_dist, alpha=ALPHA)

        # Persistent Homology (H₁만)
        barcode = generate_barcode_numpy(
            hybrid,
            listOfDimension=[1],
            exactStep=True,
            annotate=True,
            onlyFiniteInterval=True,
        )

        # 유한 H₁ interval만 추출
        finite_h1 = []
        for entry in barcode:
            if entry[0] != 1:
                continue
            b, d = entry[1][0], entry[1][1]
            if d == "infty" or not isinstance(d, (int, float)):
                continue
            if not isinstance(b, (int, float)):
                continue
            finite_h1.append(entry)

        n_h1 = len(finite_h1)
        print(f"H₁={n_h1}", end="  ")

        # cycle strengths 계산
        raw_s = compute_cycle_strengths(finite_h1, idx_to_pc)
        for k, v in raw_s.items():
            raw_strengths_all[k].append(v)

        all_intervals = [
            {"birth": round(float(e[1][0]), 6),
             "death": round(float(e[1][1]), 6)}
            for e in finite_h1
        ]

        rate_data_list.append({
            "rate": rate,
            "n_h1": n_h1,
            "raw_strengths": {k: round(v, 6) for k, v in raw_s.items()},
            "all_intervals": all_intervals,
        })
        print()

    # 정규화: 각 cycle의 max raw strength로 나눔
    max_s = {}
    for dc in DEMO_CYCLES:
        vals = raw_strengths_all[dc["name"]]
        max_s[dc["name"]] = max(vals) if vals else 1.0

    print("\n  Max strengths:", {k: round(v, 6) for k, v in max_s.items()})

    # 정규화된 cycle_strengths 계산
    for rd in rate_data_list:
        cs = {}
        for dc in DEMO_CYCLES:
            raw = rd["raw_strengths"][dc["name"]]
            mx  = max_s[dc["name"]]
            cs[dc["name"]] = round(raw / mx, 6) if mx > 1e-10 else 0.0
        rd["cycle_strengths"] = cs

    # C=0 발생 위치 보고
    for rd in rate_data_list:
        if rd["cycle_strengths"].get("C", 1) == 0.0:
            print(f"  [INFO] C=0 at rate={rd['rate']:.1f}  "
                  f"(raw C={rd['raw_strengths'].get('C', 0):.6f})")

    # ── barcode 데이터 구조 조립 ───────────────────────────────────────
    barcode_data = {
        "idx_to_pc": idx_to_pc,
        "oor": oor,
        "demo_cycles": DEMO_CYCLES,
        "rate_data": [
            {
                "rate": rd["rate"],
                "n_h1": rd["n_h1"],
                "cycle_strengths": rd["cycle_strengths"],
                "all_intervals": rd["all_intervals"],
            }
            for rd in rate_data_list
        ]
    }

    # JS 파일 출력
    barcode_js = os.path.join(OUT_DIR, "hibari_barcode_data.js")
    with open(barcode_js, "w", encoding="utf-8") as f:
        f.write("window.HIBARI_BARCODE_DATA = ")
        f.write(json.dumps(barcode_data, ensure_ascii=False))
        f.write(";\n")
    print(f"\n[OK] {barcode_js}")

    print("\n완료. hibari_overlap_data.js는 기존 파일 유지 (재생성 불필요)")


if __name__ == "__main__":
    main()
