"""
wav_renderer.py — FluidSynth 기반 피아노 WAV 렌더링 유틸리티

gen_*.py 5개 파일에서 공통으로 사용되던 ~60줄의 렌더링 코드를 추출.
서스테인 페달 시뮬레이션 + reverb/chorus 적용.
"""
import os
import numpy as np
import pretty_midi
import fluidsynth
import scipy.io.wavfile as wavfile

SF2_DEFAULT = 'C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2'
SR_DEFAULT = 44100


def render_midi_to_wav(mid_path: str, wav_path: str, *,
                       sf2_path: str = SF2_DEFAULT,
                       sample_rate: int = SR_DEFAULT,
                       pedal_threshold: int = 2,
                       reverb_tail: float = 2.0) -> float:
    """
    MIDI 파일을 Upright Piano WAV로 렌더링.

    Parameters
    ----------
    mid_path : MIDI 파일 경로
    wav_path : 출력 WAV 경로
    sf2_path : SoundFont 경로
    sample_rate : 샘플링 레이트 (기본 44100)
    pedal_threshold : 동시 발음 N개 이상이면 서스테인 페달 ON (기본 2)
    reverb_tail : 마지막 음 후 리버브 여운 초 (기본 2.0)

    Returns
    -------
    float : 렌더링된 오디오 길이 (초)
    """
    pm = pretty_midi.PrettyMIDI(mid_path)
    fs = fluidsynth.Synth(samplerate=float(sample_rate))

    fs.setting('synth.reverb.active', 1)
    fs.setting('synth.chorus.active', 1)
    fs.set_reverb(roomsize=0.6, damping=0.4, width=0.8, level=0.3)
    fs.set_chorus(nr=3, level=0.4, speed=0.3, depth=8.0, type=0)

    sfid = fs.sfload(sf2_path)
    fs.program_select(0, sfid, 0, 0)

    # 이벤트 수집 (note on/off)
    events = []
    for inst in pm.instruments:
        for note in inst.notes:
            events.append(('on',  note.start, note.pitch, note.velocity))
            events.append(('off', note.end,   note.pitch, 0))

    # 서스테인 페달 시뮬레이션: N개 이상 동시 발음 구간에 pedal on
    all_notes = sorted([(n.start, n.end)
                        for inst in pm.instruments for n in inst.notes])
    pedal_on = set()
    resolution = 0.05
    t = 0.0
    end_time = pm.get_end_time()
    while t < end_time:
        active = sum(1 for s, e in all_notes if s <= t < e)
        if active >= pedal_threshold:
            if round(t, 3) not in pedal_on:
                events.append(('pedal_on', t, 0, 0))
                pedal_on.add(round(t, 3))
        else:
            if pedal_on and any(round(t - resolution, 3) in pedal_on
                                for _ in [1]):
                events.append(('pedal_off', t, 0, 0))
        t += resolution

    events.sort(key=lambda x: x[1])

    # 렌더링
    audio_chunks = []
    current_time = 0.0
    for ev_type, ev_time, pitch, vel in events:
        dt = ev_time - current_time
        if dt > 0:
            n_samples = int(dt * sample_rate)
            if n_samples > 0:
                audio_chunks.append(np.array(fs.get_samples(n_samples)))
            current_time = ev_time

        if ev_type == 'on':
            fs.noteon(0, pitch, vel)
        elif ev_type == 'off':
            fs.noteoff(0, pitch)
        elif ev_type == 'pedal_on':
            fs.cc(0, 64, 127)
        elif ev_type == 'pedal_off':
            fs.cc(0, 64, 0)

    # 리버브 테일
    audio_chunks.append(np.array(
        fs.get_samples(int(reverb_tail * sample_rate))))
    fs.delete()

    audio = np.concatenate(audio_chunks)
    audio_mono = audio[::2] + audio[1::2]
    peak = np.max(np.abs(audio_mono))
    if peak > 0:
        audio_mono = audio_mono / peak * 0.9
    wavfile.write(wav_path, sample_rate,
                  (audio_mono * 32767).astype(np.int16))

    return len(audio_mono) / sample_rate


def score_to_wav(score, mid_path: str, wav_path: str, **kwargs) -> float:
    """
    music21 Score → MIDI 저장 → WAV 렌더링.

    Parameters
    ----------
    score : music21.stream.Score
    mid_path : 중간 MIDI 저장 경로
    wav_path : 출력 WAV 경로
    **kwargs : render_midi_to_wav에 전달할 추가 인자

    Returns
    -------
    float : 렌더링된 오디오 길이 (초)
    """
    score.write('midi', fp=mid_path)
    return render_midi_to_wav(mid_path, wav_path, **kwargs)


def musicxml_to_wav(xml_path: str, wav_path: str, *,
                    keep_midi: bool = False, **kwargs) -> float:
    """
    MusicXML → MIDI → WAV 변환.

    Parameters
    ----------
    xml_path : MusicXML 파일 경로
    wav_path : 출력 WAV 경로
    keep_midi : True면 중간 MIDI 파일 유지 (기본 삭제)
    **kwargs : render_midi_to_wav에 전달할 추가 인자

    Returns
    -------
    float : 렌더링된 오디오 길이 (초)
    """
    from music21 import converter
    mid_path = wav_path.replace('.wav', '.mid')
    score = converter.parse(xml_path)
    score.write('midi', fp=mid_path)
    duration = render_midi_to_wav(mid_path, wav_path, **kwargs)
    if not keep_midi and os.path.exists(mid_path):
        os.remove(mid_path)
    return duration
