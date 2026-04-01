"""
TDA Music Pipeline - Configuration
===================================
모든 하이퍼파라미터와 상수를 한 곳에서 관리합니다.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MIDIConfig:
    """MIDI 전처리 관련 설정"""
    file_name: str = "Ryuichi_Sakamoto_-_hibari.mid"
    inst1_end_idx: int = 2006  # inst 1 끝 인덱스
    solo_bars: int = 59        # 솔로 구간 (8분음표 단위, 4마디 × 8 + 마지막 비트 보정 등)
    eighth_per_bar: int = 8    # 한 마디당 8분음표 수
    num_chords: int = 17       # 고유 화음 수
    num_notes: int = 23        # 고유 note (pitch, duration) 수


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
    # Algorithm 2 (Neural Network)
    epochs: int = 100
    lr: float = 0.001
    dropout: float = 0.3
    test_size: float = 0.3
    random_state: int = 1
    max_resample_attempts: int = 50  # 재샘플링 최대 시도 횟수


@dataclass
class PipelineConfig:
    """전체 파이프라인 설정"""
    midi: MIDIConfig = field(default_factory=MIDIConfig)
    homology: HomologyConfig = field(default_factory=HomologyConfig)
    overlap: OverlapConfig = field(default_factory=OverlapConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    output_dir: str = "./output"
    pickle_dir: str = "./pickle"
