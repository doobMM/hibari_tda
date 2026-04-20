// Web Audio engine — polyphonic sine + light FM, ADSR, master compressor.
// All modes share this. 30-sec session window + click-free note scheduling.

export class AudioEngine {
  constructor() {
    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = window.__ac || new AC();
    window.__ac = this.ctx;
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.0;
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -18;
    comp.ratio.value = 4;
    comp.attack.value = 0.005;
    comp.release.value = 0.2;
    this.master.connect(comp).connect(this.ctx.destination);
    this._fadeIn();
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
  // MIDI pitch → frequency
  _f(midi) { return 440 * Math.pow(2, (midi - 69) / 12); }
  // Trigger a note. midi in [21,108]. velocity [0,1]. dur seconds.
  note(midi, {velocity = 0.6, dur = 0.45, detune = 0} = {}) {
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const mod = this.ctx.createOscillator();
    const modGain = this.ctx.createGain();
    const g = this.ctx.createGain();
    osc.type = 'sine';
    mod.type = 'sine';
    const f = this._f(midi);
    osc.frequency.value = f;
    mod.frequency.value = f * 2.0;
    modGain.gain.value = f * 0.25;
    osc.detune.value = detune;
    mod.connect(modGain).connect(osc.frequency);
    // ADSR
    const peak = Math.max(0.05, velocity * 0.55);
    g.gain.setValueAtTime(0, now);
    g.gain.linearRampToValueAtTime(peak, now + 0.008);
    g.gain.exponentialRampToValueAtTime(peak * 0.6, now + 0.08);
    g.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(g).connect(this.master);
    osc.start(now);
    mod.start(now);
    osc.stop(now + dur + 0.05);
    mod.stop(now + dur + 0.05);
  }
  stopAll(fadeMs = 80) {
    const now = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(this.master.gain.value, now);
    this.master.gain.linearRampToValueAtTime(0, now + fadeMs / 1000);
    setTimeout(() => this._fadeIn(), fadeMs + 20);
  }
}
