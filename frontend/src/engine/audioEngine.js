// src/engine/audioEngine.js
class AudioEngine {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.beepGain = null;
    this.alarmGain = null;

    this.warningInterval = null;
    this.criticalInterval = null;

    this.warningActive = false;
    this.criticalActive = false;

    this.muted = false;
    this.initialized = false;
    this.beepBuffer = null;
    this.beepOffset = 0;
    this.beepDuration = 0.15;
  }

  init() {
    if (this.initialized) return;
    try {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = 1.0;
      this.masterGain.connect(this.ctx.destination);

      this.beepGain = this.ctx.createGain();
      this.beepGain.gain.value = 2.0; // Amplified
      this.beepGain.connect(this.masterGain);

      this.alarmGain = this.ctx.createGain();
      this.alarmGain.gain.value = 0.7;
      this.alarmGain.connect(this.masterGain);

      this.initialized = true;
      console.log("[AudioEngine] Initialized Web Audio API context");
      
      this.loadAudio();
    } catch (err) {
      console.warn("[AudioEngine] Web Audio API not supported", err);
    }
  }

  async loadAudio() {
    try {
      const response = await fetch('/ecg_beep.mp3');
      const arrayBuffer = await response.arrayBuffer();
      this.beepBuffer = await this.ctx.decodeAudioData(arrayBuffer);
      
      // Auto-detect the first beep offset by scanning for the first loud peak
      const data = this.beepBuffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) {
        if (Math.abs(data[i]) > 0.3) {
          this.beepOffset = i / this.beepBuffer.sampleRate;
          break;
        }
      }
      // Step back a few ms to catch the attack
      this.beepOffset = Math.max(0, this.beepOffset - 0.02);
      this.beepDuration = 0.15; // 150ms beep slice
    } catch (err) {
      console.warn("Could not load ECG beep audio", err);
    }
  }

  resume() {
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  }

  playTone(freq, durationMs, type = "sine", gainNode = this.beepGain) {
    if (!this.initialized || !this.ctx) return;
    this.resume();

    const osc = this.ctx.createOscillator();
    const env = this.ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

    env.gain.setValueAtTime(0, this.ctx.currentTime);
    env.gain.linearRampToValueAtTime(1, this.ctx.currentTime + 0.01);
    env.gain.setValueAtTime(1, this.ctx.currentTime + (durationMs / 1000) - 0.02);
    env.gain.linearRampToValueAtTime(0, this.ctx.currentTime + (durationMs / 1000));

    osc.connect(env);
    env.connect(gainNode);

    osc.start();
    osc.stop(this.ctx.currentTime + (durationMs / 1000) + 0.05);
  }

  beep() {
    if (!this.initialized || !this.ctx || !this.beepBuffer) return;
    this.resume();

    // Duck the beep volume if critical alarm is active
    this.beepGain.gain.value = this.criticalActive ? 0.3 : 2.0;
    
    const source = this.ctx.createBufferSource();
    source.buffer = this.beepBuffer;
    source.connect(this.beepGain);
    source.start(0, this.beepOffset, this.beepDuration);
  }

  playWarningPattern() {
    if (this.muted || !this.warningActive || this.criticalActive) return;
    let t = this.ctx.currentTime;
    // BEEP (180ms), Gap (180ms)
    for (let i = 0; i < 3; i++) {
      this.playToneAtTime(900, 0.180, t, this.alarmGain, "sine");
      t += 0.360; // 180 + 180 gap
    }
  }

  playCriticalPattern() {
    if (this.muted || !this.criticalActive) return;
    let t = this.ctx.currentTime;
    // Tone 1 (1200Hz, 120ms) -> Gap (100ms) -> Tone 2 (1500Hz, 120ms) -> Pause (400ms)
    this.playToneAtTime(1200, 0.120, t, this.alarmGain, "triangle");
    this.playToneAtTime(1500, 0.120, t + 0.220, this.alarmGain, "triangle");
  }

  playToneAtTime(freq, durationSec, startTime, gainNode, type = "sine") {
    if (!this.initialized || !this.ctx) return;
    this.resume();

    const osc = this.ctx.createOscillator();
    const env = this.ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);

    env.gain.setValueAtTime(0, startTime);
    env.gain.linearRampToValueAtTime(1, startTime + 0.01);
    env.gain.setValueAtTime(1, startTime + durationSec - 0.02);
    env.gain.linearRampToValueAtTime(0, startTime + durationSec);

    osc.connect(env);
    env.connect(gainNode);

    osc.start(startTime);
    osc.stop(startTime + durationSec + 0.05);
  }

  setWarning(active) {
    this.warningActive = active;
    if (active && !this.warningInterval && !this.criticalActive) {
      this.playWarningPattern();
      // Total warning pattern duration = (180+180)*3 - 180 + 1200 = 2100ms
      this.warningInterval = setInterval(() => this.playWarningPattern(), 2100);
    } else if (!active && this.warningInterval) {
      clearInterval(this.warningInterval);
      this.warningInterval = null;
    }
  }

  setCritical(active) {
    this.criticalActive = active;
    if (active && !this.criticalInterval) {
      this.playCriticalPattern();
      // Total critical pattern duration = 120+100+120+400 = 740ms
      this.criticalInterval = setInterval(() => this.playCriticalPattern(), 740);
      
      if (this.warningInterval) {
        clearInterval(this.warningInterval);
        this.warningInterval = null;
      }
    } else if (!active && this.criticalInterval) {
      clearInterval(this.criticalInterval);
      this.criticalInterval = null;
      if (this.warningActive) {
        this.setWarning(true);
      }
    }
  }

  muteAlarms(isMuted) {
    this.muted = isMuted;
  }
}

const audioEngine = new AudioEngine();
export default audioEngine;
