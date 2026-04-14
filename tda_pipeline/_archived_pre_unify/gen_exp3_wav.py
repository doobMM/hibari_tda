"""
실험 3 (noPE + retrain + segment_shuffle) 음악 생성 → WAV 출력
"""
import os, sys, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_any_track import preprocess, compute_ph
from temporal_reorder import reorder_overlap_matrix
from generation import (
    prepare_training_data, MusicGeneratorTransformer,
    train_model, generate_from_model, notes_to_xml
)
from sklearn.model_selection import train_test_split

MIDI_FILE = "Ryuichi_Sakamoto_-_hibari.mid"
METRIC = "tonnetz"
SEED = 42
EPOCHS = 50
BATCH_SIZE = 32
LR = 0.001

print("[1/5] 전처리...")
data = preprocess(MIDI_FILE)
T = data['T']; N = len(data['notes_label'])
print(f"  T={T}, N={N}, C={data['num_chords']}")

print("[2/5] Persistent Homology...")
cl, ov, n_cyc, ph_time = compute_ph(data, METRIC)
C = n_cyc
print(f"  {METRIC}: {n_cyc} cycles ({ph_time:.1f}s)")

print("[3/5] segment_shuffle 재배치 + 학습 데이터 준비...")
reordered, info = reorder_overlap_matrix(ov, strategy='segment_shuffle', seed=SEED)

X_orig, y_orig = prepare_training_data(
    ov, [data['inst1'], data['inst2']], data['notes_label'], T, N
)
X_reord = reordered.astype(np.float32)
X_tr, X_va, y_tr, y_va = train_test_split(X_reord, y_orig, test_size=0.2, random_state=SEED)

print("[4/5] Transformer 학습 (noPE + retrain)...")
import torch
model = MusicGeneratorTransformer(C, N, d_model=128, nhead=4,
                                   num_layers=2, dropout=0.1, max_len=T,
                                   use_pos_emb=False)
history = train_model(
    model, X_tr, y_tr, X_va, y_va,
    epochs=EPOCHS, lr=LR, batch_size=BATCH_SIZE,
    model_type='transformer', seq_len=T
)
val_loss = history[-1]['val_loss']
print(f"  val_loss: {val_loss:.4f}")

print("[5/5] 음악 생성 + WAV 변환...")
gen = generate_from_model(
    model, reordered, data['notes_label'],
    model_type='transformer', adaptive_threshold=True
)
print(f"  생성된 음표 수: {len(gen)}")

# 두 악기로 분리 (간단히 전체를 하나의 악기로)
out_dir = os.path.join("output", "exp3_noPE_retrain_segment_shuffle")
os.makedirs(out_dir, exist_ok=True)

# MusicXML 저장
score = notes_to_xml([gen], tempo_bpm=66,
                     file_name="exp3_noPE_retrain_segment_shuffle",
                     output_dir=out_dir)

# WAV 변환 (FluidSynth + Upright Piano SF2, 서스테인 페달 + reverb)
if score:
    mid_path = os.path.join(out_dir, "exp3_noPE_retrain_segment_shuffle.mid")
    wav_path = os.path.join(out_dir, "exp3_noPE_retrain_segment_shuffle_piano.wav")

    score.write('midi', fp=mid_path)
    print(f"  MIDI 저장: {mid_path}")

    import fluidsynth
    import pretty_midi
    import scipy.io.wavfile as wavfile

    SF2 = 'C:/soundfonts/UprightPianoKW-SF2-20220221/UprightPianoKW-20220221.sf2'
    SR = 44100

    pm = pretty_midi.PrettyMIDI(mid_path)
    fs = fluidsynth.Synth(samplerate=float(SR))

    fs.setting('synth.reverb.active', 1)
    fs.setting('synth.chorus.active', 1)
    fs.set_reverb(roomsize=0.6, damping=0.4, width=0.8, level=0.3)
    fs.set_chorus(nr=3, level=0.4, speed=0.3, depth=8.0, type=0)

    sfid = fs.sfload(SF2)
    fs.program_select(0, sfid, 0, 0)

    events = []
    for inst in pm.instruments:
        for note in inst.notes:
            events.append(('on',  note.start, note.pitch, note.velocity))
            events.append(('off', note.end,   note.pitch, 0))

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
