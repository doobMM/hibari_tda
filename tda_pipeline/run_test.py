"""
TDA Music Pipeline - Quick Start Test
=======================================
기존 pickle 파일을 활용하여 빠르게 음악을 생성해볼 수 있는 테스트 스크립트입니다.

사용법:
    python run_test.py

필요한 파일:
    - Ryuichi_Sakamoto_-_hibari.mid (같은 디렉토리)
    - pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl (기존 분석 결과, 선택사항)
    - professor.py (generateBarcode 함수, 새로 탐색할 경우 필요)
"""

import sys
import os
import time

# 현재 디렉토리를 path에 추가 (기존 professor.py 사용을 위해)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def step1_preprocessing():
    """Step 1: MIDI 파일 전처리"""
    print("=" * 60)
    print("STEP 1: MIDI 전처리")
    print("=" * 60)
    
    from preprocessing import (
        load_and_quantize, split_instruments,
        group_notes_with_duration, build_chord_labels, build_note_labels,
        chord_to_note_labels, find_flexible_pitches,
        simul_chord_lists, simul_union_by_dict
    )
    
    midi_file = "Ryuichi_Sakamoto_-_hibari.mid"
    if not os.path.exists(midi_file):
        print(f"  ⚠ '{midi_file}'을 찾을 수 없습니다.")
        print(f"  → MIDI 파일을 이 스크립트와 같은 디렉토리에 넣어주세요.")
        return None
    
    t0 = time.time()
    
    # 1-1. MIDI 로드 & 양자화
    adjusted_notes, tempo, boundaries = load_and_quantize(midi_file)
    print(f"  템포: {tempo} BPM")
    print(f"  총 음표 수: {len(adjusted_notes)}")
    print(f"  악기 경계: {boundaries}")
    
    # 1-2. 두 악기 분리
    inst1_notes, inst2_notes = split_instruments(adjusted_notes, boundaries[0])
    
    # 1-3. 솔로 구간 제거 (각 악기의 처음/끝 4마디)
    SOLO_NOTES = 59        # 4마디에 해당하는 음표(tuple) 수
    SOLO_TIMEPOINTS = 32   # 4마디에 해당하는 시점 수 (4마디 × 8 eighth notes)
    inst1_real = inst1_notes[:-SOLO_NOTES]  # inst 1: 1~132마디
    inst2_real = inst2_notes[SOLO_NOTES:]   # inst 2: 5~136마디
    
    print(f"  inst1_real: {len(inst1_real)}개 음표")
    print(f"  inst2_real: {len(inst2_real)}개 음표")
    
    # 1-4. 모듈(반복 단위) 분석
    module_notes = inst1_real[:SOLO_NOTES]
    notes_label, notes_counts = build_note_labels(module_notes)
    print(f"  고유 note (pitch, duration) 수: {len(notes_label)}")
    
    # 1-5. 화음 레이블링
    active_module = group_notes_with_duration(module_notes)
    chord_map, _ = build_chord_labels(active_module)
    notes_dict = chord_to_note_labels(chord_map, notes_label)
    notes_dict['name'] = 'notes'
    print(f"  고유 화음 수: {len(chord_map)}")
    
    # 1-6. 전체 시퀀스 화음 레이블링
    active1 = group_notes_with_duration(inst1_real)
    active2 = group_notes_with_duration(inst2_real)
    _, chord_seq1 = build_chord_labels(active1)
    _, chord_seq2 = build_chord_labels(active2)
    
    # 1-7. Flexible pitches (같은 pitch, 다른 duration)
    flex = find_flexible_pitches(notes_counts, notes_label)
    
    dt = time.time() - t0
    print(f"  전처리 완료: {dt:.2f}s\n")
    
    return {
        'inst1_real': inst1_real,
        'inst2_real': inst2_real,
        'notes_label': notes_label,
        'notes_counts': notes_counts,
        'notes_dict': notes_dict,
        'chord_seq1': chord_seq1,
        'chord_seq2': chord_seq2,
        'flexible_pitches': flex,
        'tempo': tempo,
        'solo_notes': SOLO_NOTES,           # 음표 수 (59)
        'solo_timepoints': SOLO_TIMEPOINTS, # 시점 수 (32)
    }


def step2_load_persistence(data):
    """Step 2: 기존 pickle에서 persistence 로드 (또는 새로 탐색)"""
    print("=" * 60)
    print("STEP 2: Persistent Homology 데이터 로드")
    print("=" * 60)
    
    from overlap import label_cycles_from_persistence, get_cycle_stats
    
    pkl_file = "pickle/h1_rBD_t_notes1_1e-4_0.0~1.5.pkl"
    
    if os.path.exists(pkl_file):
        print(f"  기존 pickle 파일 발견: {pkl_file}")
        import pandas as pd
        
        df = pd.read_pickle(pkl_file)
        persistence = {}
        for _, row in df.iterrows():
            key = row['cycle']
            val = (row['rate'], row['birth'], row['death'])
            persistence.setdefault(key, []).append(val)
        
        print(f"  {len(persistence)}개 사이클 로드됨")
    else:
        print(f"  ⚠ pickle 파일을 찾을 수 없습니다: {pkl_file}")
        print(f"  → 새로 Homology를 탐색합니다 (시간이 걸릴 수 있습니다)...")
        persistence = _search_new(data)
    
    # 사이클 레이블링
    cycle_labeled = label_cycles_from_persistence(persistence)
    
    # 통계
    length_stats, vertex_stats, missing = get_cycle_stats(
        cycle_labeled, data['notes_dict']
    )
    print(f"  사이클 수: {len(cycle_labeled)}")
    print(f"  길이별 분포: {length_stats[:5]}...")
    if missing:
        print(f"  사이클에 미포함 note: {missing}")
    
    print()
    return persistence, cycle_labeled


def _search_new(data):
    """pickle이 없을 때 새로 homology 탐색 (간소화 버전)"""
    try:
        from professor import generateBarcode
    except ImportError:
        print("  ⚠ professor.py를 찾을 수 없습니다!")
        print("  → 기존 WK14 폴더의 professor.py를 복사해 주세요.")
        sys.exit(1)
    
    from weights import compute_intra_weights, compute_inter_weights, compute_distance_matrix, compute_out_of_reach
    from overlap import group_rBD_by_homology
    from preprocessing import group_notes_with_duration, build_chord_labels
    
    print("  intra/inter weights 계산 중...")
    
    # 간이 lag 시퀀스 (lag=1만)
    # inst1: 5~132마디 (solo 제거 후)
    c1 = data['chord_seq1'][data['solo_timepoints']:]
    # inst2: 5~132마디
    c2_full = data['chord_seq2']
    c2 = [None] + c2_full[:-(data['solo_timepoints'])]
    
    # intra weights
    w1 = compute_intra_weights(data['chord_seq1'])
    w2 = compute_intra_weights([None] + c2_full)
    intra = w1 + w2
    
    # inter weight (lag=1)
    inter = compute_inter_weights(c1, c2, lag=1)
    oor = compute_out_of_reach(inter, power=-4)
    
    notes_dict = data['notes_dict']
    num_notes = len(data['notes_label'])
    
    # rate를 0.0001 간격으로 탐색 (0.0 ~ 1.5)
    profile = []
    step = 0.0001
    total_steps = int(1.5 / step)
    
    print(f"  {total_steps}개 rate 포인트를 탐색합니다...")
    
    for a in range(total_steps):
        rate = round(a * step, 4)
        if a % 100 == 0:
            print(f"    rate = {rate:.4f} ({a}/{total_steps})")
        
        timeflow_w = intra + rate * inter
        dist = compute_distance_matrix(timeflow_w, notes_dict, oor, num_notes=num_notes)
        
        bd = generateBarcode(
            mat=dist.values, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False
        )
        profile.append((rate, bd))
    
    persistence = group_rBD_by_homology(profile, dim=1)
    print(f"  탐색 완료: {len(persistence)}개 사이클 발견")
    
    return persistence


def step3_build_overlap(data, cycle_labeled):
    """Step 3: 중첩행렬 구축"""
    print("=" * 60)
    print("STEP 3: 중첩행렬(Overlap Matrix) 구축")
    print("=" * 60)
    
    import numpy as np
    import pandas as pd
    from preprocessing import simul_chord_lists, simul_union_by_dict
    from overlap import build_activation_matrix, build_overlap_matrix
    
    t0 = time.time()
    
    notes_dict = data['notes_dict']
    num_notes = len(data['notes_label'])
    TOTAL_LENGTH = 1088  # 136마디 × 8 eighth notes
    THRESHOLD = 0.35
    
    print(f"  threshold = {THRESHOLD}")
    
    # 전체 시퀀스에서 simul chord pairs 구축
    # inst1: 1~136마디 (뒤 4마디는 None)
    # inst2: 1~136마디 (앞 4마디는 None)
    sp = data['solo_timepoints']  # 32 (시점 수)
    cs1 = list(data['chord_seq1']) + [None] * sp
    cs2 = [None] * sp + [None] + list(data['chord_seq2'])
    
    # 길이 맞추기
    max_len = max(len(cs1), len(cs2))
    cs1.extend([None] * (max_len - len(cs1)))
    cs2.extend([None] * (max_len - len(cs2)))
    
    chord_pairs = simul_chord_lists(cs1[:TOTAL_LENGTH], cs2[:TOTAL_LENGTH])
    note_sets = simul_union_by_dict(chord_pairs, notes_dict)
    
    # Note-Time DataFrame
    nodes_list = list(range(1, num_notes + 1))
    note_time_data = []
    for ns in note_sets:
        row = [1 if col in ns else 0 for col in nodes_list]
        note_time_data.append(row)
    note_time_df = pd.DataFrame(note_time_data, columns=nodes_list)
    
    print(f"  Note-Time DataFrame: {note_time_df.shape}")
    
    # 활성화 행렬
    activation = build_activation_matrix(note_time_df, cycle_labeled)
    print(f"  Activation Matrix: {activation.shape}")
    
    # 중첩행렬
    overlap = build_overlap_matrix(
        activation, cycle_labeled,
        threshold=THRESHOLD,
        total_length=TOTAL_LENGTH
    )
    
    on_ratio = overlap.values.sum() / overlap.size
    dt = time.time() - t0
    print(f"  Overlap Matrix: {overlap.shape}")
    print(f"  ON ratio: {on_ratio:.4f} ({on_ratio*100:.2f}%)")
    print(f"  구축 완료: {dt:.2f}s\n")
    
    return overlap


def step4_generate_music(data, cycle_labeled, overlap):
    """Step 4: Algorithm 1로 음악 생성"""
    print("=" * 60)
    print("STEP 4: 음악 생성 (Algorithm 1)")
    print("=" * 60)
    
    from generation import NodePool, CycleSetManager, algorithm1_optimized, notes_to_xml
    import datetime
    
    t0 = time.time()
    
    notes_label = data['notes_label']
    notes_counts = data['notes_counts']
    
    # 화음 높이 시퀀스 (각 시점에서 몇 개의 음을 배치할지)
    # 원곡 모듈의 화음 높이를 33회 반복 (132마디 = 4마디 × 33)
    modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
    inst_chord_heights = modules * 33  # 32 × 33 = 1056 시점
    
    print(f"  생성할 시점 수: {len(inst_chord_heights)}")
    print(f"  사이클 수: {len(cycle_labeled)}")
    
    # 노드 풀 생성
    pool = NodePool(notes_label, notes_counts, num_modules=65)
    print(f"  노드 풀 크기: {pool.total_size}")
    
    # 사이클 집합 매니저 (교집합/합집합 캐싱)
    manager = CycleSetManager(cycle_labeled)
    
    # 생성 실행
    print(f"  음악 생성 중...")
    generated = algorithm1_optimized(
        pool, inst_chord_heights,
        overlap.values,
        manager,
        max_resample=50,
        verbose=True
    )
    
    # MusicXML로 출력
    output_dir = "./generated_output"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"hibari_tda_{timestamp}"
    
    notes_to_xml(
        [generated],
        tempo_bpm=int(data['tempo']),
        file_name=file_name,
        output_dir=output_dir
    )
    
    dt = time.time() - t0
    print(f"\n  생성 완료: {dt:.2f}s")
    print(f"  생성된 음표 수: {len(generated)}")
    print(f"  출력 파일: {output_dir}/{file_name}.musicxml")
    
    # MIDI로도 변환 시도
    try:
        from music21 import converter
        xml_path = os.path.join(output_dir, f"{file_name}.musicxml")
        score = converter.parse(xml_path)
        midi_path = os.path.join(output_dir, f"{file_name}.mid")
        score.write('midi', fp=midi_path)
        print(f"  MIDI 파일: {midi_path}")
    except Exception as e:
        print(f"  (MIDI 변환 건너뜀: {e})")
    
    return generated


def step5_visualize(overlap, cycle_labeled):
    """Step 5 (선택): 중첩행렬 시각화"""
    print("=" * 60)
    print("STEP 5: 중첩행렬 시각화")
    print("=" * 60)
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # GUI 없이 저장
        import matplotlib.pyplot as plt
        import seaborn as sns
        from matplotlib.colors import ListedColormap
        
        mat = overlap.values.T  # (cycles, time)
        
        fig, ax = plt.subplots(1, 1, figsize=(24, 15))
        sns.heatmap(
            mat,
            cmap=ListedColormap(['white', (0.2, 0.8, 0.8)]),
            yticklabels=[f'C{i+1}' for i in range(len(mat))],
            cbar=False, ax=ax
        )
        
        ax.set_title('Overlap Matrix - TDA Generated Music')
        ax.set_xlabel('Time (eighth note)')
        ax.set_ylabel('Cycle')
        
        # x축 레이블 간격 조정
        n = 15
        for i, label in enumerate(ax.xaxis.get_ticklabels()):
            if i % n != 0:
                label.set_visible(False)
        
        output_path = "./generated_output/overlap_matrix.png"
        plt.savefig(output_path, bbox_inches='tight', dpi=150)
        plt.close()
        print(f"  저장됨: {output_path}\n")
        
    except ImportError:
        print("  matplotlib/seaborn이 필요합니다.\n")


# ═══════════════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  TDA Music Pipeline - Hibari Test            ║")
    print("║  류이치 사카모토 'hibari' 위상 구조 음악 생성  ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    
    # Step 1: 전처리
    data = step1_preprocessing()
    if data is None:
        sys.exit(1)
    
    # Step 2: Persistence 로드
    persistence, cycle_labeled = step2_load_persistence(data)
    
    # Step 3: 중첩행렬 구축
    overlap = step3_build_overlap(data, cycle_labeled)
    
    # Step 4: 음악 생성
    generated = step4_generate_music(data, cycle_labeled, overlap)
    
    # Step 5: 시각화 (선택)
    step5_visualize(overlap, cycle_labeled)
    
    print("=" * 60)
    print("모든 단계 완료!")
    print("=" * 60)
    print()
    print("생성된 파일:")
    print("  ./generated_output/hibari_tda_*.musicxml  ← 악보")
    print("  ./generated_output/hibari_tda_*.mid       ← 재생용 MIDI")
    print("  ./generated_output/overlap_matrix.png     ← 중첩행렬 시각화")
    print()
    print("MusicXML 파일은 MuseScore(무료)로 열어서 재생할 수 있습니다:")
    print("  https://musescore.org/ko")
    print()
