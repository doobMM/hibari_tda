"""
Figure 4 — Persistence Barcode Diagram (Tonnetz distance).

본 연구의 주 거리 함수는 Tonnetz이므로 barcode 역시 Tonnetz 기반으로 그린다.
기존 frequency-based pkl 대신, topology.generate_barcode_numpy 를 호출하여
Tonnetz hybrid distance로 rate 0~1.5 구간의 persistence를 직접 계산한다.

첫 실행 시 계산 결과를 fig4_tonnetz_persistence.pkl 에 캐시해두고,
이후 실행에서는 캐시만 로드한다 (계산에 2-3분 걸림).

Layout: 2 panels
 (a) 전체 48개 — 빨강 = 범위 초과, 파랑 = 범위 내 유한
 (b) 유한 37개만 zoom — lifespan 차이 식별
"""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RATE_MAX = 1.5
CACHE_PKL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'fig4_tonnetz_persistence.pkl')


def compute_tonnetz_persistence():
    """Tonnetz 거리로 rate 0~1.5 구간의 persistence를 계산하여
    (cycle, rate, birth, death) DataFrame으로 반환."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    os.chdir(root)
    sys.path.insert(0, root)

    from preprocessing import (
        load_and_quantize, split_instruments, build_note_labels,
        group_notes_with_duration, build_chord_labels, chord_to_note_labels,
        prepare_lag_sequences)
    from weights import (
        compute_intra_weights, compute_inter_weights,
        compute_distance_matrix, compute_out_of_reach)
    from overlap import group_rBD_by_homology
    from topology import generate_barcode_numpy
    from musical_metrics import compute_note_distance_matrix, compute_hybrid_distance

    print("Tonnetz persistence 재계산 시작 (약 2-3분)...")

    midi = 'Ryuichi_Sakamoto_-_hibari.mid'
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
    N = len(notes_label)

    w1 = compute_intra_weights(adn_i[1][0])
    w2 = compute_intra_weights(adn_i[2][0])
    intra = w1 + w2
    inter = compute_inter_weights(adn_i[1][1], adn_i[2][1], lag=1)
    oor = compute_out_of_reach(inter, power=-2)

    m_dist = compute_note_distance_matrix(notes_label, metric='tonnetz')

    rows = []
    rate = 0.0
    count = 0
    while rate <= RATE_MAX + 1e-10:
        r = round(rate, 2)
        tw = intra + r * inter
        freq_dist = compute_distance_matrix(tw, notes_dict, oor, num_notes=N).values
        final = compute_hybrid_distance(freq_dist, m_dist, alpha=0.5)
        bd = generate_barcode_numpy(
            mat=final, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False)
        # bd의 첫 dim=1 항목 추출
        profile_entry = (r, bd)
        persistence = group_rBD_by_homology([profile_entry], dim=1)
        for cycle_id, bd_list in persistence.items():
            for (rr, b, d) in bd_list:
                rows.append({'cycle': cycle_id, 'rate': rr,
                             'birth': b, 'death': d})
        count += 1
        if count % 30 == 0:
            print(f"  rate={r:.2f}  (누적 {len(rows)} rows)")
        rate += 0.01

    df = pd.DataFrame(rows)
    print(f"완료: {len(df)} rows, unique cycles: {df['cycle'].nunique()}")
    return df


def load_or_compute():
    if os.path.exists(CACHE_PKL):
        print(f"캐시 로드: {CACHE_PKL}")
        return pd.read_pickle(CACHE_PKL)
    df = compute_tonnetz_persistence()
    df.to_pickle(CACHE_PKL)
    print(f"캐시 저장: {CACHE_PKL}")
    return df


def main():
    df = load_or_compute()

    rows = []
    for cid, grp in df.groupby('cycle'):
        rows.append({'cycle': cid,
                     'birth': grp['birth'].min(),
                     'death': grp['death'].max()})
    bars = pd.DataFrame(rows)

    bars['beyond'] = bars['death'] > RATE_MAX
    bars['death_vis'] = bars['death'].clip(upper=RATE_MAX)
    bars['lifespan_vis'] = bars['death_vis'] - bars['birth']
    bars['true_lifespan'] = bars['death'] - bars['birth']

    bars = bars.sort_values(['beyond', 'lifespan_vis'],
                            ascending=[False, False]).reset_index(drop=True)
    n_bars = len(bars)
    n_beyond = int(bars['beyond'].sum())

    finite = bars[~bars['beyond']].reset_index(drop=True)
    n_finite = len(finite)
    finite_max_life = finite['true_lifespan'].max() if n_finite else 0
    finite_min_life = finite['true_lifespan'].min() if n_finite else 0
    print(f"Total {n_bars}, beyond {n_beyond}, finite {n_finite}")
    print(f"Finite lifespan range: {finite_min_life:.5f} – {finite_max_life:.5f}")

    fig = plt.figure(figsize=(13, 10))
    fig.patch.set_facecolor('white')
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.3], hspace=0.32)

    color_beyond = '#e74c3c'
    color_finite = '#3498db'

    # ─── Panel (a): full ───
    ax_a = fig.add_subplot(gs[0])
    for i, row in bars.iterrows():
        color = color_beyond if row['beyond'] else color_finite
        y = n_bars - 1 - i
        width = row['death_vis'] - row['birth']
        ax_a.barh(y, width, left=row['birth'], height=0.72,
                  color=color, edgecolor='#2c3e50', linewidth=0.4)
        if row['beyond']:
            ax_a.annotate('∞', xy=(RATE_MAX + 0.005, y),
                          ha='left', va='center', fontsize=12,
                          color='#c0392b', fontweight='bold')

    if 0 < n_beyond < n_bars:
        boundary_y = n_bars - n_beyond - 0.5
        ax_a.axhline(y=boundary_y, color='#7f8c8d',
                     linestyle=':', linewidth=1.0, alpha=0.6)

    ax_a.set_xlabel('Rate parameter $r_t$', fontsize=11, color='#2c3e50')
    ax_a.set_ylabel('Cycle index (lifespan ↓)', fontsize=11, color='#2c3e50')
    if n_beyond > 0:
        title_a = (f'(a) Tonnetz-based barcode — 전체 {n_bars}개 cycle. '
                   f'빨강 {n_beyond}개 = 탐색 범위 $[0, 1.5]$ 벗어남, '
                   f'파랑 {n_finite}개 = 범위 내 유한 cycle')
    else:
        title_a = (f'(a) Tonnetz-based barcode — 전체 {n_bars}개 cycle '
                   f'(모두 탐색 범위 $[0, 1.5]$ 내에서 유한, 파랑)')
    ax_a.set_title(title_a, fontsize=10.5, color='#2c3e50', loc='left', pad=8)
    ax_a.set_xlim(-0.03, RATE_MAX + 0.18)
    ax_a.set_ylim(-0.8, n_bars - 0.2)
    ax_a.grid(axis='x', alpha=0.3, linestyle='--')
    ax_a.spines['top'].set_visible(False)
    ax_a.spines['right'].set_visible(False)

    # ─── Panel (b): finite-only zoom ───
    ax_b = fig.add_subplot(gs[1])
    if n_finite > 0:
        fin_x_min = max(0, finite['birth'].min() - 0.001)
        fin_x_max = finite['death'].max() * 1.05
        finite_sorted = finite.sort_values('true_lifespan',
                                            ascending=False).reset_index(drop=True)
        cmap = plt.cm.viridis
        norms = ((finite_sorted['true_lifespan'] - finite_min_life) /
                 max(finite_max_life - finite_min_life, 1e-9))

        for i, row in finite_sorted.iterrows():
            y = n_finite - 1 - i
            color = cmap(0.2 + 0.7 * norms.iloc[i])
            ax_b.barh(y, row['death'] - row['birth'], left=row['birth'],
                      height=0.72, color=color, edgecolor='#2c3e50', linewidth=0.5)

        ax_b.set_xlim(fin_x_min, fin_x_max)
        ax_b.set_ylim(-0.8, n_finite - 0.2)
        ax_b.set_title(f'(b) 유한 {n_finite}개 cycle만 zoom — lifespan 범위 '
                       f'$[{finite_min_life:.4f}, {finite_max_life:.4f}]$, '
                       '색은 lifespan에 비례 (viridis)',
                       fontsize=10.5, color='#2c3e50', loc='left', pad=8)
    ax_b.set_xlabel('Rate parameter $r_t$  (zoom)', fontsize=11, color='#2c3e50')
    ax_b.set_ylabel('Cycle index (lifespan ↓)', fontsize=11, color='#2c3e50')
    ax_b.grid(axis='x', alpha=0.3, linestyle='--')
    ax_b.spines['top'].set_visible(False)
    ax_b.spines['right'].set_visible(False)

    fig.suptitle('Figure 4. Persistence Barcode — hibari $H_1$ cycles '
                 '(Tonnetz hybrid distance, $\\alpha=0.5$, timeflow weight)',
                 fontsize=13, color='#2c3e50', y=0.995, fontweight='bold')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fig4_barcode.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
