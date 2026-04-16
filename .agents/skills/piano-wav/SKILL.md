---
name: piano-wav
description: MusicXML 또는 MIDI 파일을 UprightPiano 사운드폰트로 렌더링하여 WAV 변환. "WAV로 바꿔줘", "piano로 들려줘", "렌더링해줘" 등의 요청에 자동 로드.
allowed-tools: Bash(python *) Glob Read
argument-hint: <file1.musicxml> [file2.mid] ...
---

## MusicXML / MIDI → Piano WAV 변환

### 렌더링 설정 (필수 — 사용자 피드백 반영)
- SoundFont: `C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2`
- Sample Rate: 44100
- **서스테인 페달**: 2음 이상 동시 활성 시 자동 ON (resolution=0.05s)
- **Reverb**: roomsize=0.6, damping=0.4, width=0.8, level=0.3
- **Chorus**: nr=3, level=0.4, speed=0.3, depth=8.0
- 2초 여운 추가 후 peak normalize (0.9)

### 실행 방법

**MusicXML → WAV** (gen_harmony_wav.py의 musicxml_to_piano_wav 함수 사용):
```bash
cd tda_pipeline && python -c "
import sys; sys.path.insert(0, '.')
from gen_harmony_wav import musicxml_to_piano_wav
xml = 'output/<파일명>.musicxml'
wav = 'output/<파일명>_piano.wav'
dur = musicxml_to_piano_wav(xml, wav)
print(f'완료: {wav} ({dur:.1f}s)')
"
```

**MIDI → WAV** (직접 FluidSynth 사용):
```bash
cd tda_pipeline && python -c "
import numpy as np, pretty_midi, fluidsynth, scipy.io.wavfile as wavfile
# ... (gen_tonnetz_vwide_wav.py 패턴 참조)
"
```

### 복수 파일 일괄 변환
파일 목록을 받으면 루프로 순차 변환. 각 파일당 약 30-60초 소요.

### 결과 보고
- 파일명, 길이(초), 경로 표시
- output/ 폴더에 저장
