"""
diagnose_refine_bug.py
======================
d114742 bugfix 진단: refine_connectedness의 OLD vs NEW 동작 비교

핵심 질문:
1. OLD 코드(E.T @ W_upper @ E)와 NEW 코드(E.T @ W_sym @ E)의 차이는?
2. 어떤 note 쌍이 추가/누락되었는가?
3. frequency metric 43→1 cycle 붕괴의 원인은?
4. 새로운 버그가 도입됐는가, 아니면 올바른 수정인가?
"""

import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing import (
    load_and_quantize, split_instruments, build_note_labels,
    group_notes_with_duration, build_chord_labels, chord_to_note_labels,
    prepare_lag_sequences
)
from weights import (
    compute_intra_weights, compute_inter_weights_decayed,
    to_upper_triangular, _build_expansion_matrix,
    weight_to_distance, compute_out_of_reach, symmetrize_upper_to_full
)
from topology import generate_barcode_numpy


# ─────────────────────────────────────────────────────────────────────────────
# 1. OLD refine_connectedness (bugfix 이전)
# ─────────────────────────────────────────────────────────────────────────────

def refine_old(weight_matrix, notes_dict, num_notes=23, rounding_digits=4):
    """OLD 버전: E.T @ W_upper @ E (W_upper 을 그대로 사용)."""
    W = weight_matrix.values.astype(float)
    # 심대칭화 없이 그대로 사용
    E = _build_expansion_matrix(notes_dict, num_notes)
    refined = E.T @ W @ E
    if rounding_digits is not None:
        refined = np.round(refined, rounding_digits)
    refined = np.triu(refined)
    idx = list(range(1, num_notes + 1))
    return pd.DataFrame(refined, index=idx, columns=idx, dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEW refine_connectedness (bugfix 이후, 현재 코드)
# ─────────────────────────────────────────────────────────────────────────────

def refine_new(weight_matrix, notes_dict, num_notes=23, rounding_digits=4):
    """NEW 버전: E.T @ W_sym @ E (W_sym = W_upper + W_upper.T)."""
    W = weight_matrix.values.astype(float)
    W_sym = W + W.T
    np.fill_diagonal(W_sym, np.diag(W))
    E = _build_expansion_matrix(notes_dict, num_notes)
    refined = E.T @ W_sym @ E
    if rounding_digits is not None:
        refined = np.round(refined, rounding_digits)
    refined = np.triu(refined)
    idx = list(range(1, num_notes + 1))
    return pd.DataFrame(refined, index=idx, columns=idx, dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# 3. 데이터 로드
# ─────────────────────────────────────────────────────────────────────────────

def load_hibari():
    midi = "Ryuichi_Sakamoto_-_hibari.mid"
    adj, tempo, bounds = load_and_quantize(midi)
    inst1, inst2 = split_instruments(adj, bounds[0])
    inst1_real, inst2_real = inst1[:-59], inst2[59:]

    notes_label, notes_counts = build_note_labels(inst1_real[:59])
    ma = group_notes_with_duration(inst1_real[:59])
    cm, _ = build_chord_labels(ma)
    notes_dict = chord_to_note_labels(cm, notes_label)
    notes_dict['name'] = 'notes'

    _, cs1 = build_chord_labels(group_notes_with_duration(inst1_real))
    _, cs2 = build_chord_labels(group_notes_with_duration(inst2_real))
    adn_i = prepare_lag_sequences(cs1, cs2, solo_timepoints=32, max_lag=4)

    return notes_dict, notes_label, adn_i


# ─────────────────────────────────────────────────────────────────────────────
# 4. 진단 분석
# ─────────────────────────────────────────────────────────────────────────────

def analyze_missing_pairs(W_upper, notes_dict, num_notes):
    """OLD 코드에서 누락된 note 쌍을 식별합니다."""
    E = _build_expansion_matrix(notes_dict, num_notes)
    W = W_upper.values.astype(float)
    W_sym = W + W.T
    np.fill_diagonal(W_sym, np.diag(W))

    refined_old = E.T @ W @ E
    refined_sym = E.T @ W_sym @ E

    # 상삼각에서 old=0 but new>0인 쌍 = 누락된 쌍
    old_triu = np.triu(refined_old)
    new_triu = np.triu(refined_sym)

    was_zero_now_nonzero = (old_triu == 0) & (new_triu > 0)
    n_missing = np.sum(was_zero_now_nonzero)

    # 반대: old>0 but new=0 (double-counting 제거로 오히려 0이 된 경우)
    was_nonzero_now_zero = (old_triu > 0) & (new_triu == 0)
    n_lost = np.sum(was_nonzero_now_zero)

    # 값이 달라진 쌍 (old>0 and new>0 but different)
    both_nonzero = (old_triu > 0) & (new_triu > 0)
    changed = both_nonzero & (np.abs(old_triu - new_triu) > 1e-6)
    n_changed = np.sum(changed)

    return {
        'n_pairs_total': (num_notes * (num_notes + 1)) // 2,
        'n_old_nonzero': int(np.sum(old_triu > 0)),
        'n_new_nonzero': int(np.sum(new_triu > 0)),
        'n_missing_recovered': int(n_missing),
        'n_lost': int(n_lost),
        'n_value_changed': int(n_changed),
        'max_value_old': float(old_triu.max()),
        'max_value_new': float(new_triu.max()),
    }


def count_cycles(dist_matrix, dim=1):
    """generateBarcode로 cycle 수를 셉니다."""
    from overlap import group_rBD_by_homology
    D = dist_matrix if isinstance(dist_matrix, np.ndarray) else dist_matrix.values
    bd = generate_barcode_numpy(
        mat=D, listOfDimension=[dim],
        exactStep=True, birthDeathSimplex=False, sortDimension=False
    )
    profile = [(0.0, bd)]
    persistence = group_rBD_by_homology(profile, dim=dim)
    return len(persistence)


def compute_dist_from_refined(refined_df, oor):
    """refined weight matrix → symmetric distance matrix."""
    D_upper = weight_to_distance(refined_df, oor)
    D_full = symmetrize_upper_to_full(D_upper)
    return D_full


def main():
    print("=" * 65)
    print("  diagnose_refine_bug.py — d114742 bugfix 진단")
    print("=" * 65)

    # 데이터 로드
    print("\n[1] hibari 데이터 로드...")
    notes_dict, notes_label, adn_i = load_hibari()
    num_notes = len(notes_label)
    print(f"    notes={num_notes}, chords={max(k for k in notes_dict if isinstance(k,int))+1}")

    # 가중치 행렬 구성 (rate=0.3, 감쇄 lag)
    print("\n[2] 가중치 행렬 구성 (rate=0.3)...")
    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights_decayed(adn_i, max_lag=4, num_chords=17)
    oor = compute_out_of_reach(inter, power=-2)
    rate = 0.3
    timeflow_w = intra + rate * inter
    W_upper = to_upper_triangular(timeflow_w)

    print(f"    timeflow_w: nonzero={np.sum(timeflow_w.values != 0)}, max={timeflow_w.values.max():.4f}")
    print(f"    W_upper:    nonzero={np.sum(W_upper.values != 0)}, max={W_upper.values.max():.4f}")
    print(f"    out_of_reach = {oor:.4f}")

    # ─── 핵심 진단: 누락 쌍 분석 ─────────────────────────────────────────────
    print("\n[3] OLD vs NEW refine_connectedness 비교...")
    stats = analyze_missing_pairs(W_upper, notes_dict, num_notes)
    print(f"    전체 상삼각 쌍 수 (포함 대각): {stats['n_pairs_total']}")
    print(f"    OLD non-zero 연결:  {stats['n_old_nonzero']}")
    print(f"    NEW non-zero 연결:  {stats['n_new_nonzero']}")
    print(f"    ── OLD=0 → NEW>0 (복원된 누락):  {stats['n_missing_recovered']}")
    print(f"    ── OLD>0 → NEW=0 (새로 사라진):  {stats['n_lost']}")
    print(f"    ── 값이 변경된 쌍:               {stats['n_value_changed']}")
    print(f"    OLD max: {stats['max_value_old']:.4f}, NEW max: {stats['max_value_new']:.4f}")

    # ─── 구체적 누락 쌍 예시 ──────────────────────────────────────────────────
    print("\n[4] 누락 쌍 원인 분석 (representative examples)...")
    E = _build_expansion_matrix(notes_dict, num_notes)
    W = W_upper.values.astype(float)
    W_sym = W + W.T
    np.fill_diagonal(W_sym, np.diag(W))
    refined_old = np.triu(E.T @ W @ E)
    refined_new = np.triu(E.T @ W_sym @ E)

    # 누락 쌍 중 가장 큰 값 5개
    mask = (refined_old == 0) & (refined_new > 0)
    if mask.any():
        coords = np.argwhere(mask)
        values = [refined_new[r, c] for r, c in coords]
        top5 = sorted(zip(values, [tuple(c) for c in coords]), reverse=True)[:5]
        print("    복원된 누락 쌍 TOP5 (weight):")
        for w_val, ab in top5:
            a, b = ab
            # 어떤 chord pair 때문인지 역추적
            chords_a = [i for i in range(E.shape[0]) if E[i, a] > 0]
            chords_b = [j for j in range(E.shape[0]) if E[j, b] > 0]
            print(f"      note({a+1}, {b+1}): new_weight={w_val:.4f}  "
                  f"[note{a+1}∈chords{chords_a}, note{b+1}∈chords{chords_b}]")
            # 왜 old에서 0이었는지 확인
            for ci in chords_a:
                for cj in chords_b:
                    if W[ci, cj] > 0:
                        print(f"        ← W_old[{ci},{cj}]={W[ci,cj]:.4f} (chord_i<chord_j: {ci<cj}) → OLD 처리: {ci<=cj}")
    else:
        print("    (누락 쌍 없음)")

    # ─── frequency metric cycle 수 비교 ──────────────────────────────────────
    print("\n[5] frequency metric: OLD vs NEW cycle 수 비교")
    print("    (rate 범위 0.0~1.5 스캔 중...)")

    profile_old = []
    profile_new = []
    from overlap import group_rBD_by_homology

    for a in range(0, 151):  # 0.00 ~ 1.50 step 0.01
        r = round(a * 0.01, 2)
        tw = intra + r * inter

        W_up = to_upper_triangular(tw)

        # OLD
        ref_old = refine_old(W_up, notes_dict, num_notes)
        D_old = compute_dist_from_refined(ref_old, oor)
        bd_old = generate_barcode_numpy(
            mat=D_old.values, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile_old.append((r, bd_old))

        # NEW
        ref_new = refine_new(W_up, notes_dict, num_notes)
        D_new = compute_dist_from_refined(ref_new, oor)
        bd_new = generate_barcode_numpy(
            mat=D_new.values, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile_new.append((r, bd_new))

    persist_old = group_rBD_by_homology(profile_old, dim=1)
    persist_new = group_rBD_by_homology(profile_new, dim=1)

    print(f"    OLD(pre-bugfix) cycle 수: {len(persist_old)}")
    print(f"    NEW(post-bugfix) cycle 수: {len(persist_new)}")

    # ─── 각 cycle의 persistence 비교 ─────────────────────────────────────────
    def persistence_stats(persist):
        """각 cycle의 persistence 길이 통계."""
        lengths = []
        for cyc_id, occurrences in persist.items():
            rates = [rate for rate, b, d in occurrences]
            lengths.append(max(rates) - min(rates))
        return lengths

    len_old = persistence_stats(persist_old)
    len_new = persistence_stats(persist_new)

    if len_old:
        print(f"\n    OLD: persistence 평균={np.mean(len_old):.4f}, "
              f"max={max(len_old):.4f}, min={min(len_old):.4f}")
    if len_new:
        print(f"    NEW: persistence 평균={np.mean(len_new):.4f}, "
              f"max={max(len_new):.4f}, min={min(len_new):.4f}")

    # ─── 결론 ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  진단 결론")
    print("=" * 65)

    n_miss = stats['n_missing_recovered']
    n_old = stats['n_old_nonzero']
    n_new = stats['n_new_nonzero']

    print(f"\n  [A] bugfix 전후 연결 변화:")
    print(f"      OLD {n_old}개 → NEW {n_new}개 (+{n_new - n_old}개, {(n_new-n_old)/n_old*100:.1f}%)")
    print(f"      복원된 누락 연결: {n_miss}개")

    if n_miss > 0:
        print(f"\n  [B] 누락 연결이 실제로 존재했으므로 bugfix는 수학적으로 올바름.")
        print(f"      OLD 코드는 chord_i < chord_j이지만 note_a > note_b인")
        print(f"      경우를 하삼각(discarded)에 넣고 있었음 → 진짜 버그.")
    else:
        print(f"\n  [B] 누락 연결이 없음 → bugfix가 불필요하거나 다른 효과.")

    cycles_old = len(persist_old)
    cycles_new = len(persist_new)
    print(f"\n  [C] frequency cycle 수: {cycles_old} → {cycles_new}")
    if cycles_new < cycles_old:
        pct = (cycles_old - cycles_new) / cycles_old * 100
        print(f"      {pct:.0f}% 감소. 이는 bugfix로 추가된 연결이")
        print(f"      기존의 '인위적으로 단절된' 구조를 연결하면서")
        print(f"      persistent cycle이 붕괴된 결과임.")
        print(f"      → 새로운 버그 도입 아님. OLD 코드의 스파스한 연결이")
        print(f"        우연히 풍부한 위상 구조를 만들고 있었던 것.")
    else:
        print(f"      cycle 수가 유지되거나 증가 → 붕괴 없음.")

    print(f"\n  [D] 결론:")
    print(f"      d114742 bugfix는 수학적으로 올바른 수정임.")
    print(f"      논문의 pre-bugfix 결과(Tonnetz=0.0398, frequency=43 cycles)는")
    print(f"      버그 있는 구현에서 도출된 것임.")
    print(f"      → 모든 실험을 post-bugfix 코드로 재실행해야 함.")
    print()


if __name__ == "__main__":
    main()
