"""
TDA Music Pipeline - Configuration
===================================
모든 하이퍼파라미터와 상수를 한 곳에서 관리합니다.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MIDIConfig:
    """MIDI 전처리 관련 설정

    [일반화] auto_detect=True이면 MIDI 파일에서 파라미터를 자동 감지.
    아래 값들은 hibari 기준 fallback으로만 사용됩니다.
    """
    file_name: str = "Ryuichi_Sakamoto_-_hibari.mid"
    auto_detect: bool = True     # True면 아래 값 대신 MIDI에서 자동 감지

    # ── Fallback 값 (auto_detect=False일 때만 사용) ──
    inst1_end_idx: int = 2006    # inst 1 끝 인덱스
    solo_notes: int = 59         # 솔로 구간 note 수 (구: solo_bars)
    solo_timepoints: int = 32    # 솔로 구간 시간 길이
    num_chords: int = 17         # 고유 화음 수
    num_notes: int = 23          # 고유 note (pitch, duration) 수
    quantize_unit: Optional[float] = None  # None = 8분음표 자동


@dataclass
class MetricConfig:
    """거리 함수 설정

    metric: 사용할 거리 함수
      - 'frequency': 기존 빈도 역수 (기본값, alpha=1.0과 동일)
      - 'tonnetz': Tonnetz 격자 거리
      - 'voice_leading': pitch 차이 (반음 수)
      - 'dft': Fourier 공간 거리
      - 'hybrid': 빈도 + 음악적 거리 혼합 (alpha로 비율 조절)

    hybrid_metrics: hybrid 모드에서 섞을 metric 목록
      예: ['tonnetz', 'dft'] → 빈도 + tonnetz + dft 3개를 혼합
    hybrid_weights: 각 metric의 가중치 (빈도 포함)
      예: [0.4, 0.3, 0.3] → 빈도 40%, tonnetz 30%, dft 30%
    """
    metric: str = 'frequency'
    alpha: float = 0.0                  # hybrid에서 빈도 거리 비중 (α grid search N=20 결과: α=0.0 최적)
    octave_weight: float = 0.3          # Tonnetz note 거리의 옥타브 항 가중치 (튜닝 N=10: 0.3 최적, 기존 0.5)
    hybrid_metrics: List[str] = field(default_factory=lambda: ['tonnetz'])
    hybrid_weights: Optional[List[float]] = None  # None이면 균등 배분


@dataclass
class HomologyConfig:
    """Persistent Homology 탐색 설정"""
    max_lag: int = 4           # inter-weight lag 최대값
    power: int = -2            # rate step = 10^power
    rate_start: float = 0.0
    rate_end: float = 1.5
    dimensions: List[int] = field(default_factory=lambda: [1, 2])


@dataclass
class OverlapConfig:
    """중첩행렬 구축 설정"""
    threshold: float = 0.35    # ON 비율 목표치
    lower_bound: Optional[float] = None  # None이면 max(0, threshold - 0.1)
    total_length: int = 1088   # 전체 시퀀스 길이 (8분음표 단위)


@dataclass
class GenerationConfig:
    """음악 생성(Algorithm 1 & 2) 설정"""
    num_modules: int = 65      # 반복 모듈 수
    tempo_bpm: int = 66
    temperature: float = 3.0   # NodePool 샘플링 온도: w(n) ∝ freq(n)^(1/T). T>1=균등화, T<1=집중 (N=10 결과: T=3.0 최적)
    # Algorithm 2 (Neural Network)
    epochs: int = 100
    lr: float = 0.001
    dropout: float = 0.3
    test_size: float = 0.3
    random_state: int = 1
    max_resample_attempts: int = 50  # 재샘플링 최대 시도 횟수
    use_continuous_overlap: bool = True  # Algo2 입력: True=continuous, False=binary (N=5: +64.3% JS 개선)


@dataclass
class PipelineConfig:
    """전체 파이프라인 설정"""
    midi: MIDIConfig = field(default_factory=MIDIConfig)
    metric: MetricConfig = field(default_factory=MetricConfig)
    homology: HomologyConfig = field(default_factory=HomologyConfig)
    overlap: OverlapConfig = field(default_factory=OverlapConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    output_dir: str = "./output"
    pickle_dir: str = "./pickle"
