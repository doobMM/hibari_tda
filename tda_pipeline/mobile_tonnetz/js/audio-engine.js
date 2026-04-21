// Web Audio engine — triangle oscillator + convolution reverb.
// Marimba/vibraphone-like timbre: clean attack, long natural decay.

export class AudioEngine {
  constructor() {
    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = window.__ac || new AC();
    window.__ac = this.ctx;

    // Dry chain: master → compressor → destination
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.0;
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -18;
    comp.ratio.value     = 4;
    comp.attack.value    = 0.005;
    comp.release.value   = 0.2;
    this.master.connect(comp);
    comp.connect(this.ctx.destination);

    // Wet chain: compressor → convolver → wet gain → destination
    const convolver = this.ctx.createConvolver();
    convolver.buffer = this._makeImpulse(1.4);
    const wetGain = this.ctx.createGain();
    wetGain.gain.value = 0.22;
    comp.connect(convolver);
    convolver.connect(wetGain);
    wetGain.connect(this.ctx.destination);

    this._fadeIn();
  }

  // Synthetic exponential-decay impulse response (small hall)
  _makeImpulse(duration) {
    const rate   = this.ctx.sampleRate;
    const length = Math.floor(rate * duration);
    const buf    = this.ctx.createBuffer(2, length, rate);
    for (let ch = 0; ch < 2; ch++) {
      const data = buf.getChannelData(ch);
      for (let i = 0; i < length; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, 1.8);
      }
    }
    return buf;
  }

  _fadeIn() {
    const now = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(this.master.gain.value, now);
    this.master.gain.linearRampToValueAtTime(0.8, now + 0.1);
  }

  async unlock() {
    if (this.ctx.state !== 'running') await this.ctx.resume();
  }

  // MIDI pitch → Hz
  _f(midi) { return 440 * Math.pow(2, (midi - 69) / 12); }

  // Trigger a note — marimba/vibraphone timbre.
  // Two slightly detuned triangle oscillators → warm, non-synthetic tone.
  note(midi, { velocity = 0.6, dur = 1.8, detune = 0 } = {}) {
    const now = this.ctx.currentTime;
    const f   = this._f(midi);

    const g   = this.ctx.createGain();
    const peak = Math.max(0.04, velocity * 0.5);

    // Piano-like ADSR: instant attack, fast decay, low sustain, fade out
    g.gain.setValueAtTime(0, now);
    g.gain.linearRampToValueAtTime(peak,        now + 0.005);  // attack 5ms
    g.gain.exponentialRampToValueAtTime(peak * 0.12, now + 0.35); // decay
    g.gain.exponentialRampToValueAtTime(0.001,  now + dur);    // release

    g.connect(this.master);

    // Two triangle oscillators, 5 cents apart — avoids "pure sine" flatness
    for (const offset of [0, 5]) {
      const osc = this.ctx.createOscillator();
      osc.type = 'triangle';
      osc.frequency.value = f;
      osc.detune.value = detune + offset;
      osc.connect(g);
      osc.start(now);
      osc.stop(now + dur + 0.05);
    }
  }

  stopAll(fadeMs = 80) {
    const now = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(this.master.gain.value, now);
    this.master.gain.linearRampToValueAtTime(0, now + fadeMs / 1000);
    setTimeout(() => this._fadeIn(), fadeMs + 20);
  }
}
