"""
reassign_tonnetz_{wide,vwide}_transformer MusicXML → Upright Piano WAV
서스테인 페달 + reverb 적용
"""
import os, sys, glob, warnings
import numpy as np
warnings.filterwarnings('ignore')

import fluidsynth
import pretty_midi
import scipy.io.wavfile as wavfile
from music21 import converter

SF2 = 'C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2'
SR = 44100

files = sorted(glob.glob("output/reassign_tonnetz_*_transformer_*.musicxml"))
print(f"변환 대상: {len(files)}개")
for f in files:
    print(f"  {f}")


def render_piano_wav(mid_path, wav_path):
    """MIDI → Upright Piano WAV (서스테인 페달 + reverb + chorus)"""
    pm = pretty_midi.PrettyMIDI(mid_path)
    fs = fluidsynth.Synth(samplerate=float(SR))

    fs.setting('synth.reverb.active', 1)
    fs.setting('synth.chorus.active', 1)
    fs.set_reverb(roomsize=0.6, damping=0.4, width=0.8, level=0.3)
    fs.set_chorus(nr=3, level=0.4, speed=0.3, depth=8.0, type=0)

    sfid = fs.sfload(SF2)
    fs.program_select(0, sfid, 0, 0)

    # 이벤트 수집
    events = []
    for inst in pm.instruments:
        for note in inst.notes:
            events.append(('on',  note.start, note.pitch, note.velocity))
            events.append(('off', note.end,   note.pitch, 0))

    # 서스테인 페달 시뮬레이션: 2개 이상 동시 발음 구간에 pedal on
    all_notes = sorted([(n.start, n.end) for inst in pm.instruments for n in inst.notes])
    pedal_on = set()
    resolution = 0.05
    t = 0.0
    end_time = pm.get_end_time()
    while t < end_time:
        active = sum(1 for s, e in all_notes if s <= t < e)
        if active >= 2:
            if round(t, 3) not in pedal_on:
                events.append(('pedal_on', t, 0, 0))
                pedal_on.add(round(t, 3))
        else:
            if pedal_on and any(round(t - resolution, 3) in pedal_on for _ in [1]):
                events.append(('pedal_off', t, 0, 0))
        t += resolution

    events.sort(key=lambda x: x[1])

    # 렌더링
    audio_chunks = []
    current_time = 0.0

    for ev_type, ev_time, pitch, vel in events:
        dt = ev_time - current_time
        if dt > 0:
            n_samples = int(dt * SR)
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

    # 리버브 테일 2초
    audio_chunks.append(np.array(fs.get_samples(int(2.0 * SR))))
    fs.delete()

    audio = np.concatenate(audio_chunks)
    audio_mono = audio[::2] + audio[1::2]
    peak = np.max(np.abs(audio_mono))
    if peak > 0:
        audio_mono = audio_mono / peak * 0.9
    wavfile.write(wav_path, SR, (audio_mono * 32767).astype(np.int16))
    return len(audio_mono) / SR


for xml_path in files:
    base = os.path.splitext(os.path.basename(xml_path))[0]
    mid_path = xml_path.replace('.musicxml', '.mid')
    wav_path = xml_path.replace('.musicxml', '_piano.wav')

    print(f"\n{'='*60}")
    print(f"  {base}")
    print(f"{'='*60}")

    # MusicXML → MIDI
    print("  [1/2] MusicXML → MIDI...")
    score = converter.parse(xml_path)
    score.write('midi', fp=mid_path)
    print(f"    MIDI: {mid_path}")

    # MIDI → Piano WAV
    print("  [2/2] MIDI → Piano WAV (FluidSynth)...")
    duration = render_piano_wav(mid_path, wav_path)
    print(f"    WAV: {wav_path}")
    print(f"    길이: {duration:.1f}s")

print("\n모두 완료!")
