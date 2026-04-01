"""
run_comparison.py — K별 음악 생성 비교
=========================================

K=10, 17, 48(전체)으로 음악을 생성하여 비교합니다.
각 결과에 대해 preservation score, 생성 note 수, 고유 pitch 수를 출력합니다.
"""

import sys, os, time, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import TDAMusicPipeline, PipelineConfig


def run_for_k(base_pipeline, k_value, label):
    """주어진 K로 cycle selection + 음악 생성을 수행합니다.

    동작 흐름:
      1) base_pipeline의 캐시를 얕은 복사하여 독립 파이프라인 생성
      2) k_value개의 cycle 부분집합을 선택 (run_cycle_selection)
      3) 선택된 cycle로 Algorithm 1 음악 생성
      4) 생성된 note의 통계(고유 pitch 수 등)를 반환
    """
    # 원본 cache를 복사하여 독립적으로 실행
    # — 각 K 실험이 서로의 캐시를 오염시키지 않도록 분리
    p = copy.copy(base_pipeline)
    p._cache = dict(base_pipeline._cache)

    print(f"\n{'='*60}")
    print(f"  {label}: K={k_value}")
    print(f"{'='*60}")

    # K가 전체 cycle 수보다 작으면 부분집합 선택, 아니면 전체 사용
    if k_value is not None and k_value < len(base_pipeline._cache['cycle_labeled']):
        p.run_cycle_selection(k=k_value, verbose=False)
        sel = p._cache.get('selection_result')
        score = sel.final_score if sel else 1.0
    else:
        score = 1.0
        print(f"[Stage 3.5] 전체 cycle 사용 (K={len(base_pipeline._cache['cycle_labeled'])})")

    # 선택된 cycle 수에 맞춰 Algorithm 1으로 음악 생성
    n_cycles = len(p._cache['cycle_labeled'])
    generated = p.run_generation_algo1(
        verbose=False,
        file_suffix=f"_K{k_value if k_value else n_cycles}"
    )

    # 생성된 note에서 고유 pitch 집합 추출
    pitches = set()
    for start, pitch, end in generated:
        pitches.add(pitch)

    return {
        'k': k_value if k_value else n_cycles,
        'n_cycles': n_cycles,
        'score': score,
        'n_notes': len(generated),
        'n_pitches': len(pitches),
        'generated': generated
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  K별 음악 생성 비교")
    print("=" * 60)

    # ── 메인 흐름: 전처리 → 중첩행렬(pkl) → K별 생성 비교 ──

    config = PipelineConfig()
    pipeline = TDAMusicPipeline(config)

    # Stage 1: 전처리 — MIDI → 화음/note 레이블링
    print("\n[Stage 1] 전처리...")
    pipeline.run_preprocessing()

    # Stage 3: 중첩행렬 — 기존 pkl에서 cycle 정보 로드 후 overlap matrix 구축
    pkl_file = "h1_rBD_t_notes1_1e-4_0.0~1.5.pkl"
    print(f"\n[Stage 3] 중첩행렬 구축 (from pkl)...")
    pipeline.run_overlap_construction(from_pickle=pkl_file)

    total_cycles = len(pipeline._cache['cycle_labeled'])
    print(f"\n  전체 cycle 수: {total_cycles}")

    # K별 생성 — K=10, 17은 부분집합, None은 전체 cycle 사용
    k_values = [10, 17, None]  # None = 전체
    results = []

    for k in k_values:
        label = f"K={k}" if k else f"K={total_cycles} (전체)"
        r = run_for_k(pipeline, k, label)
        results.append(r)

    # 요약 테이블 출력 — K별 cycle 수, preservation score, 생성 note/pitch 수 비교
    print(f"\n{'='*60}")
    print(f"  요약")
    print(f"{'='*60}")
    print(f"\n  {'K':>4s} | {'Cycles':>6s} | {'Score':>6s} | {'Notes':>6s} | {'Pitches':>7s}")
    print(f"  {'----':>4s} | {'------':>6s} | {'------':>6s} | {'------':>6s} | {'-------':>7s}")
    for r in results:
        print(f"  {r['k']:4d} | {r['n_cycles']:6d} | {r['score']:6.4f} | {r['n_notes']:6d} | {r['n_pitches']:7d}")

    print(f"\n  출력 파일: {config.output_dir}/algo1_K*_*.musicxml")
    print(f"\n{'='*60}")
    print("  완료")
    print("=" * 60)
