"""
TDA Music Pipeline - Main Orchestrator
========================================
전체 파이프라인을 하나의 흐름으로 실행합니다.

핵심 설계 원칙:
1. 중간 결과를 캐싱하여 반복 실행 시 재계산 방지
2. 각 단계를 독립적으로 실행 가능 (모듈러 설계)
3. 설정 변경이 영향을 미치는 하류 단계만 재실행
"""

import os
import pickle
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import Counter

from config import PipelineConfig
from preprocessing import (
    load_and_quantize, split_instruments,
    group_notes_with_duration, build_chord_labels, build_note_labels,
    chord_to_note_labels, prepare_lag_sequences,
    find_flexible_pitches, simul_chord_lists, simul_union_by_dict
)
from weights import (
    compute_intra_weights, compute_inter_weights,
    compute_distance_matrix, compute_out_of_reach,
    compute_simul_weights
)
from overlap import (
    label_cycles_from_persistence, get_cycle_stats,
    build_activation_matrix, build_overlap_matrix,
    group_rBD_by_homology, find_common_across_lags
)
from generation import (
    NodePool, CycleSetManager,
    algorithm1_optimized, notes_to_xml
)


class TDAMusicPipeline:
    """
    TDA 기반 음악 생성 파이프라인.
    
    Usage:
        config = PipelineConfig()
        pipeline = TDAMusicPipeline(config)
        pipeline.run_preprocessing()
        pipeline.run_homology_search()
        pipeline.run_overlap_construction()
        generated = pipeline.run_generation()
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._cache = {}  # 중간 결과 캐시
        
        # 디렉토리 생성
        os.makedirs(config.output_dir, exist_ok=True)
        os.makedirs(config.pickle_dir, exist_ok=True)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Stage 1: 전처리
    # ═══════════════════════════════════════════════════════════════════════
    
    def run_preprocessing(self, midi_file: Optional[str] = None):
        """MIDI → 화음 시퀀스 → note 레이블링"""
        t0 = time.time()
        
        fpath = midi_file or self.config.midi.file_name
        print(f"[Stage 1] 전처리 시작: {fpath}")
        
        # MIDI 로드 및 양자화
        adjusted_notes, tempo, boundaries = load_and_quantize(
            fpath, quantize_unit=self.config.midi.quantize_unit
        )
        self._cache['tempo'] = tempo

        # 자동 감지 모드: MIDI에서 파라미터 추출
        if self.config.midi.auto_detect:
            from preprocessing import analyze_midi
            detected = analyze_midi(fpath, self.config.midi.quantize_unit)
            # 자동 감지 가능한 값 업데이트
            self.config.midi.inst1_end_idx = detected['inst1_end_idx']
            self.config.midi.num_notes = detected['num_notes']
            self.config.midi.num_chords = detected['num_chords']
            self.config.overlap.total_length = detected['total_timepoints']
            # solo는 자동 감지가 어려우므로 감지값이 0이면 config fallback 유지
            if detected['solo_notes'] > 0:
                self.config.midi.solo_notes = detected['solo_notes']
                self.config.midi.solo_timepoints = detected['solo_timepoints']

        # 두 악기 분리
        inst1_notes, inst2_notes = split_instruments(
            adjusted_notes, boundaries[0]
        )

        # 솔로 구간 제거
        solo = self.config.midi.solo_notes
        inst1_real = inst1_notes[:-solo] if solo > 0 else inst1_notes
        inst2_real = inst2_notes[solo:] if solo > 0 else inst2_notes
        self._cache['inst1_real'] = inst1_real
        self._cache['inst2_real'] = inst2_real
        
        # 화음 레이블링
        active1 = group_notes_with_duration(inst1_real)
        active2 = group_notes_with_duration(inst2_real)
        
        chord_map1, chord_seq1 = build_chord_labels(active1)
        chord_map2, chord_seq2 = build_chord_labels(active2)
        self._cache['chord_seq1'] = chord_seq1
        self._cache['chord_seq2'] = chord_seq2
        
        # Note 레이블링 (모듈 단위)
        module_notes = inst1_real[:solo]
        notes_label, notes_counts = build_note_labels(module_notes)
        self._cache['notes_label'] = notes_label
        self._cache['notes_counts'] = notes_counts
        
        # 화음 → note 매핑 (notes_dict)
        module_active = group_notes_with_duration(module_notes)
        chord_map_module, _ = build_chord_labels(module_active)
        notes_dict = chord_to_note_labels(chord_map_module, notes_label)
        notes_dict['name'] = 'notes'
        self._cache['notes_dict'] = notes_dict
        
        # lag별 시퀀스 준비
        # solo_timepoints는 solo_notes와 다름 (시간 길이 vs note 수)
        solo_tp = self.config.midi.solo_timepoints
        adn_i = prepare_lag_sequences(
            chord_seq1, chord_seq2,
            solo_timepoints=solo_tp,
            max_lag=self.config.homology.max_lag
        )
        self._cache['adn_i'] = adn_i
        
        # Flexible pitches
        flex_pitches = find_flexible_pitches(notes_counts, notes_label)
        self._cache['flexible_pitches'] = flex_pitches
        
        dt = time.time() - t0
        print(f"[Stage 1] 전처리 완료 ({dt:.2f}s)")
        print(f"  - Notes: {len(notes_label)}종, Chords: {len(chord_map_module)}종")
        
        return self
    
    # ═══════════════════════════════════════════════════════════════════════
    # Stage 2: Persistent Homology 탐색
    # ═══════════════════════════════════════════════════════════════════════
    
    def run_homology_search(self, 
                            search_type: str = 'timeflow',
                            lag: int = 1,
                            dimension: int = 1,
                            rate_t: float = 0.3,
                            rate_s: float = 0.6):
        """
        Persistent homology를 탐색합니다.
        
        Args:
            search_type: 'timeflow' | 'simul' | 'complex'
            lag: inter-weight lag (timeflow/complex 전용)
            dimension: 호몰로지 차원 (1=cycle, 2=void)
            rate_t, rate_s: complex 모드에서의 비율
        """
        t0 = time.time()
        cfg = self.config.homology
        
        print(f"[Stage 2] Homology 탐색: type={search_type}, dim={dimension}, lag={lag}")
        
        adn_i = self._cache['adn_i']
        notes_dict = self._cache['notes_dict']
        
        # Barcode 생성: topology.py의 numpy 최적화 버전 (기존 대비 ~2.5x)
        from topology import generate_barcode_numpy as generateBarcode
        
        if search_type == 'timeflow':
            profile, oor = self._search_timeflow(
                adn_i, notes_dict, lag, dimension, cfg, generateBarcode
            )
        elif search_type == 'simul':
            profile, oor = self._search_simul(
                adn_i, notes_dict, dimension, cfg, generateBarcode
            )
        elif search_type == 'complex':
            profile, oor = self._search_complex(
                adn_i, notes_dict, lag, dimension, rate_t, rate_s, cfg, generateBarcode
            )
        else:
            raise ValueError(f"Unknown search_type: {search_type}")
        
        # rBD 그룹화
        persistence = group_rBD_by_homology(profile, dim=dimension)
        
        # 캐시 저장
        key = f"h{dimension}_{search_type}_lag{lag}"
        self._cache[key] = persistence
        self._cache[f"{key}_oor"] = oor
        
        dt = time.time() - t0
        print(f"[Stage 2] 완료 ({dt:.2f}s) - {len(persistence)}개 호몰로지 발견")
        
        return self
    
    def _search_timeflow(self, adn_i, notes_dict, lag, dim, cfg, generateBarcode):
        """Timeflow homology 탐색"""
        # Intra weights
        w1 = compute_intra_weights(adn_i[1][0])
        w2 = compute_intra_weights(adn_i[2][0])
        intra = w1 + w2
        
        # Inter weight
        inter = compute_inter_weights(adn_i[1][lag], adn_i[2][lag], lag=lag)
        oor = compute_out_of_reach(inter, power=cfg.power)
        
        step = 10 ** cfg.power
        profile = []
        
        for a in range(int(cfg.rate_start / step), int(cfg.rate_end / step)):
            rate = round(a * step, -cfg.power)
            
            timeflow_w = intra + rate * inter
            dist = compute_distance_matrix(
                timeflow_w, notes_dict, oor, 
                num_notes=self.config.midi.num_notes
            )
            
            bd = generateBarcode(
                mat=dist.values, listOfDimension=[dim],
                exactStep=True, birthDeathSimplex=False, sortDimension=False
            )
            profile.append((rate, bd))
        
        return profile, oor
    
    def _search_simul(self, adn_i, notes_dict, dim, cfg, generateBarcode):
        """Simul homology 탐색"""
        simul_intra, simul_inter = compute_simul_weights(
            adn_i[1][-1], adn_i[2][-1], notes_dict
        )
        
        step = 10 ** cfg.power
        temp = step * simul_inter
        oor = 1 + 2 / temp.values[temp.values != 0].min()
        
        profile = []
        for a in range(int(cfg.rate_start / step), int(cfg.rate_end / step)):
            rate = round(a * step, 4)
            
            w = simul_intra + rate * simul_inter
            dist = compute_distance_matrix(
                w, notes_dict, oor, 
                num_notes=self.config.midi.num_notes,
                refine=False
            )
            
            bd = generateBarcode(
                mat=dist.values, listOfDimension=[dim],
                exactStep=True, birthDeathSimplex=False, sortDimension=False
            )
            profile.append((rate, bd))
        
        return profile, oor
    
    def _search_complex(self, adn_i, notes_dict, lag, dim, rate_t, rate_s, cfg, generateBarcode):
        """Complex homology 탐색"""
        # Timeflow 부분
        w1 = compute_intra_weights(adn_i[1][0])
        w2 = compute_intra_weights(adn_i[2][0])
        intra = w1 + w2
        inter = compute_inter_weights(adn_i[1][lag], adn_i[2][lag], lag=lag)
        
        timeflow_w = intra + rate_t * inter
        # Refine만 수행 (거리 변환은 complex에서)
        from weights import to_upper_triangular, refine_connectedness_fast
        from weights import symmetrize_upper_to_full
        
        tf_upper = to_upper_triangular(timeflow_w)
        tf_refined = refine_connectedness_fast(
            tf_upper, notes_dict, self.config.midi.num_notes
        )
        tf_full = symmetrize_upper_to_full(tf_refined)
        
        # Simul 부분
        simul_intra, simul_inter = compute_simul_weights(
            adn_i[1][-1], adn_i[2][-1], notes_dict
        )
        simul_w = simul_intra + rate_s * simul_inter
        
        oor = compute_out_of_reach(simul_w, power=cfg.power)
        
        step = 10 ** cfg.power
        profile = []
        
        for a in range(int(cfg.rate_start / step), int(cfg.rate_end / step)):
            rate = round(a * step, -cfg.power)
            
            complex_w = tf_full + rate * simul_w
            from weights import weight_to_distance
            dist = weight_to_distance(complex_w, oor)
            dist = symmetrize_upper_to_full(dist)
            
            bd = generateBarcode(
                mat=dist.values, listOfDimension=[dim],
                exactStep=True, birthDeathSimplex=False, sortDimension=False
            )
            profile.append((rate, bd))
        
        return profile, oor
    
    # ═══════════════════════════════════════════════════════════════════════
    # Stage 3: 중첩행렬 구축
    # ═══════════════════════════════════════════════════════════════════════
    
    def run_overlap_construction(self, 
                                 persistence_key: Optional[str] = None,
                                 from_pickle: Optional[str] = None):
        """
        사이클 persistence 데이터로부터 중첩행렬을 구축합니다.
        
        Args:
            persistence_key: 캐시 키 (예: 'h1_timeflow_lag1')
            from_pickle: pickle 파일에서 로드할 경우 파일명
        """
        t0 = time.time()
        cfg = self.config.overlap
        
        print(f"[Stage 3] 중첩행렬 구축 (threshold={cfg.threshold})")
        
        # Persistence 데이터 로드
        if from_pickle:
            filepath = os.path.join(self.config.pickle_dir, from_pickle)
            persistence = self._load_persistence_from_pickle(filepath)
        elif persistence_key and persistence_key in self._cache:
            persistence = self._cache[persistence_key]
        else:
            raise ValueError("persistence 데이터를 지정해주세요.")
        
        # 사이클 레이블링
        cycle_labeled = label_cycles_from_persistence(persistence)
        self._cache['cycle_labeled'] = cycle_labeled
        
        # 통계
        length_stats, vertex_stats, missing = get_cycle_stats(
            cycle_labeled, self._cache['notes_dict']
        )
        print(f"  - {len(cycle_labeled)}개 사이클")
        if missing:
            print(f"  - 사이클에 미포함 note: {missing}")
        
        # Note-time 행렬 구축
        adn_i = self._cache['adn_i']
        notes_dict = self._cache['notes_dict']
        
        chord_pairs = simul_chord_lists(adn_i[1][-1], adn_i[2][-1])
        note_sets = simul_union_by_dict(chord_pairs, notes_dict)
        
        # DataFrame 구축
        nodes_list = list(range(1, self.config.midi.num_notes + 1))
        note_time_df = self._build_note_time_df(nodes_list, note_sets)
        self._cache['note_time_df'] = note_time_df
        
        # 활성화 행렬
        activation = build_activation_matrix(note_time_df, cycle_labeled)
        
        # 중첩행렬
        overlap = build_overlap_matrix(
            activation, cycle_labeled,
            threshold=cfg.threshold,
            lower_bound=cfg.lower_bound,
            total_length=cfg.total_length
        )
        self._cache['overlap_matrix'] = overlap
        
        dt = time.time() - t0
        on_ratio = overlap.values.sum() / overlap.size
        print(f"[Stage 3] 완료 ({dt:.2f}s) - ON ratio: {on_ratio:.4f}")
        
        return self
    
    def _build_note_time_df(self, nodes_list, note_sets):
        """note-time DataFrame 구축"""
        data = []
        for ns in note_sets:
            row = [1 if col in ns else 0 for col in nodes_list]
            data.append(row)
        return pd.DataFrame(data, columns=nodes_list)
    
    def _load_persistence_from_pickle(self, filepath):
        """pickle에서 persistence 로드"""
        df = pd.read_pickle(filepath)
        result = {}
        for _, row in df.iterrows():
            key = row['cycle']
            val = (row['rate'], row['birth'], row['death'])
            result.setdefault(key, []).append(val)
        return result
    
    # ═══════════════════════════════════════════════════════════════════════
    # Stage 3.5: Cycle Subset 선택 (선택적)
    # ═══════════════════════════════════════════════════════════════════════

    def run_cycle_selection(self, k: Optional[int] = None,
                            target: Optional[float] = None,
                            verbose: bool = True):
        """
        위상 구조 보존도 기반으로 최적 cycle subset을 선택합니다.
        Greedy forward selection으로 복합 보존도(Jaccard+Corr+Betti)가
        가장 높은 cycle을 하나씩 추가합니다.

        Args:
            k: 고정 크기 선택 (예: 10, 17)
            target: 보존도 임계값 (예: 0.90)
            둘 다 None이면 전체 cycle 사용 (no-op)
        """
        if k is None and target is None:
            print("[Stage 3.5] Cycle 선택 생략 (전체 사용)")
            return self

        t0 = time.time()
        from cycle_selector import CycleSubsetSelector

        overlap = self._cache['overlap_matrix']
        cycle_labeled = self._cache['cycle_labeled']

        print(f"[Stage 3.5] Cycle Subset 선택"
              f" ({'K=' + str(k) if k else 'target=' + str(target)})")

        selector = CycleSubsetSelector(overlap.values, cycle_labeled)

        if k is not None:
            result = selector.select_fixed_size(k, verbose=verbose)
        else:
            result = selector.select_by_threshold(target, verbose=verbose)

        # 원본을 별도 키로 보존 (나중에 복원 가능)
        self._cache['cycle_labeled_full'] = cycle_labeled
        self._cache['overlap_matrix_full'] = overlap
        self._cache['selection_result'] = result

        # 선택된 cycle만으로 새 cycle_labeled 구성 (0부터 재인덱싱)
        items = list(cycle_labeled.items())
        selected_labeled = {}
        for new_idx, orig_col_idx in enumerate(result.selected_indices):
            orig_label, cycle_tuple = items[orig_col_idx]
            selected_labeled[new_idx] = cycle_tuple

        # overlap matrix에서 선택된 컬럼만 추출
        selected_overlap = pd.DataFrame(
            overlap.values[:, result.selected_indices],
            columns=list(range(len(result.selected_indices)))
        )

        # cache 교체 → 이후 Stage 4가 subset 기반으로 동작
        self._cache['cycle_labeled'] = selected_labeled
        self._cache['overlap_matrix'] = selected_overlap

        dt = time.time() - t0
        print(f"[Stage 3.5] 완료 ({dt:.2f}s)"
              f" — {len(result.selected_indices)}/{len(items)} cycles"
              f", score={result.final_score:.4f}")

        return self

    # ═══════════════════════════════════════════════════════════════════════
    # Stage 4: 음악 생성
    # ═══════════════════════════════════════════════════════════════════════

    def run_generation_algo1(self,
                             inst_chord_heights: Optional[List[int]] = None,
                             verbose: bool = False,
                             file_suffix: str = "") -> List[Tuple[int, int, int]]:
        """
        Algorithm 1로 음악을 생성합니다.
        
        Args:
            inst_chord_heights: 각 시점별 화음 높이(음의 수) 리스트
                None이면 기본 패턴(modules × 33) 사용
            verbose: 디버그 출력
        """
        t0 = time.time()
        print("[Stage 4-A] Algorithm 1 음악 생성")
        
        notes_label = self._cache['notes_label']
        notes_counts = self._cache['notes_counts']
        cycle_labeled = self._cache['cycle_labeled']
        overlap = self._cache['overlap_matrix']
        
        # 화음 높이 시퀀스
        if inst_chord_heights is None:
            modules = [4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3, 3, 3,
                       4, 4, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 3, 3, 3]
            inst_chord_heights = modules * 33
        
        # 노드 풀 생성
        pool = NodePool(
            notes_label, notes_counts,
            num_modules=self.config.generation.num_modules
        )
        
        # 사이클 집합 매니저
        cycles_list = list(cycle_labeled.values())
        manager = CycleSetManager(cycle_labeled)
        
        # 생성
        generated = algorithm1_optimized(
            pool, inst_chord_heights,
            overlap.values,
            manager,
            max_resample=self.config.generation.max_resample_attempts,
            verbose=verbose
        )
        
        # XML 출력
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        notes_to_xml(
            [generated],
            tempo_bpm=self.config.generation.tempo_bpm,
            file_name=f"algo1{file_suffix}_{timestamp}",
            output_dir=self.config.output_dir
        )
        
        dt = time.time() - t0
        print(f"[Stage 4-A] 완료 ({dt:.2f}s) - {len(generated)}개 음표 생성")
        
        return generated
    
    def run_generation_algo2(self, 
                             batch_size: int = 32) -> Optional[object]:
        """
        Algorithm 2 (신경망)로 음악을 생성합니다.
        """
        try:
            from generation import (
                prepare_training_data, MusicGenerator, train_model
            )
            from sklearn.model_selection import train_test_split
        except ImportError as e:
            print(f"  ⚠ 필요한 라이브러리가 없습니다: {e}")
            return None
        
        t0 = time.time()
        cfg = self.config.generation
        print("[Stage 4-B] Algorithm 2 (신경망) 학습")
        
        overlap = self._cache['overlap_matrix']
        notes_label = self._cache['notes_label']
        inst1_real = self._cache['inst1_real']
        inst2_real = self._cache['inst2_real']
        
        n_notes = self.config.midi.num_notes
        seq_len = self.config.overlap.total_length
        
        # 학습 데이터 준비
        X, y = prepare_training_data(
            overlap.values,
            [inst1_real, inst2_real],
            notes_label,
            seq_len,
            n_notes
        )
        
        print(f"  X shape: {X.shape}, y shape: {y.shape}")
        
        # Train/Valid 분할
        X_train, X_valid, y_train, y_valid = train_test_split(
            X, y, test_size=cfg.test_size, random_state=cfg.random_state
        )
        
        # 모델 생성
        dim_input = X.shape[1]
        dim_output = y.shape[1] * n_notes
        dim_hidden = seq_len
        
        model = MusicGenerator(
            dim_input, dim_hidden, dim_output, n_notes,
            dropout=cfg.dropout
        )
        
        # 학습
        history = train_model(
            model, X_train, y_train, X_valid, y_valid,
            epochs=cfg.epochs, lr=cfg.lr, batch_size=batch_size
        )
        
        self._cache['model'] = model
        self._cache['training_history'] = history
        
        dt = time.time() - t0
        print(f"[Stage 4-B] 완료 ({dt:.2f}s)")
        
        return model
    
    # ═══════════════════════════════════════════════════════════════════════
    # 캐시 관리
    # ═══════════════════════════════════════════════════════════════════════
    
    def save_cache(self, filepath: str = "pipeline_cache.pkl"):
        """중간 결과를 pickle로 저장합니다."""
        path = os.path.join(self.config.output_dir, filepath)
        with open(path, 'wb') as f:
            pickle.dump(self._cache, f)
        print(f"캐시 저장: {path}")
    
    def load_cache(self, filepath: str = "pipeline_cache.pkl"):
        """저장된 중간 결과를 로드합니다."""
        path = os.path.join(self.config.output_dir, filepath)
        with open(path, 'rb') as f:
            self._cache = pickle.load(f)
        print(f"캐시 로드: {path}")
        return self
    
    @property
    def cache_keys(self):
        return list(self._cache.keys())


# ═══════════════════════════════════════════════════════════════════════════
# CLI 엔트리포인트
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = PipelineConfig()
    pipeline = TDAMusicPipeline(config)
    
    # 1) 전처리
    pipeline.run_preprocessing()
    
    # 2) Homology 탐색 (예: timeflow, lag=1, dim=1)
    pipeline.run_homology_search(
        search_type='timeflow', lag=1, dimension=1
    )
    
    # 3) 중첩행렬 구축
    pipeline.run_overlap_construction(
        persistence_key='h1_timeflow_lag1'
    )
    
    # 4) 음악 생성
    generated = pipeline.run_generation_algo1(verbose=True)
    
    print(f"\n생성 완료: {len(generated)}개 음표")
