"""
방향 A: vl_wide (voice_leading, pitch 48-84) → Algo1 생성 → Piano WAV
"""
import os, sys, warnings, random
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from note_reassign import find_new_notes
from run_note_reassign import run_algo1_with_new_notes
from generation import notes_to_xml

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
METRIC = "tonnetz"
SEED = 42

print("[1/5] 전처리...")
data = preprocess(MIDI_FILE)
print(f"  T={data['T']}, N={data['N']}, C={data['num_chords']}")

print("[2/5] Persistent Homology...")
cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
print(f"  {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

print("[3/5] vl_wide 새 note 탐색...")
result = find_new_notes(
    data['notes_label'], cl,
    note_metric='voice_leading', cycle_metric='voice_leading',
    pitch_range=(48, 84), n_candidates=1000, seed=SEED
)
print(f"  note 거리 오차:  {result['note_dist_error']:.4f}")
print(f"  cycle 거리 오차: {result['cycle_dist_error']:.4f}")
print(f"  원곡 pitches: {[n[0] for n in result['orig_notes']]}")
print(f"  새   pitches: {[n[0] for n in result['new_notes']]}")

print("[4/5] Algo1 생성...")
gen = run_algo1_with_new_notes(data, ov, cl, result['new_notes_label'], seed=SEED)
print(f"  생성된 음표 수: {len(gen)}")

print("[5/5] MusicXML → MIDI → Piano WAV...")
out_dir = os.path.join("output", "note_reassign_vl_wide")
os.makedirs(out_dir, exist_ok=True)

score = notes_to_xml([gen], tempo_bpm=66,
                     file_name="vl_wide", output_dir=out_dir)

if score:
    mid_path = os.path.join(out_dir, "vl_wide.mid")
    wav_path = os.path.join(out_dir, "vl_wide_piano.wav")
    score.write('midi', fp=mid_path)
    print(f"  MIDI: {mid_path}")

    # pyfluidsynth + Upright Piano SF2 렌더링 (페달 시뮬레이션 + reverb)
    import fluidsynth
    import pretty_midi
    import scipy.io.wavfile as wavfile

    SF2 = 'C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2'
    SR = 44100

    pm = pretty_midi.PrettyMIDI(mid_path)
    fs = fluidsynth.Synth(samplerate=float(SR))

    # Reverb + Chorus
    fs.setting('synth.reverb.active', 1)
    fs.setting('synth.chorus.active', 1)
    fs.set_reverb(roomsize=0.6, damping=0.4, width=0.8, level=0.3)
    fs.set_chorus(nr=3, level=0.4, speed=0.3, depth=8.0, type=0)

    sfid = fs.sfload(SF2)
    fs.program_select(0, sfid, 0, 0)

    # 이벤트 수집 (note on/off + sustain pedal)
    events = []
    for inst in pm.instruments:
        for note in inst.notes:
            events.append(('on',  note.start, note.pitch, note.velocity))
            events.append(('off', note.end,   note.pitch, 0))

    # 서스테인 페달 시뮬레이션: note overlap 구간에 pedal on
    all_notes = sorted([(n.start, n.end) for inst in pm.instruments for n in inst.notes])
    pedal_on = set()
    resolution = 0.05  # 50ms 단위
    t = 0.0
    end_time = pm.get_end_time()
    while t < end_time:
        active = sum(1 for s, e in all_notes if s <= t < e)
        if active >= 2:
            if t not in pedal_on:
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
    print(f"  Piano WAV: {wav_path}")
    print(f"  길이: {len(audio_mono)/SR:.1f}s")

print("\n완료!")
