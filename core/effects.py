# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Stateful, real-time audio effects chain.

This module has zero knowledge of any GUI. It just turns one numpy
block of audio into another. Anything UI-related lives in skins/.

Signal chain:
    Input Gain -> Noise Gate -> Drive -> Cabinet Sim -> 3-Band EQ
               -> Chorus -> Delay -> Reverb -> Master Volume

Every effect added after the original release (cabinet sim, chorus,
reverb) defaults to "off", so a freshly constructed chain with default
parameters produces exactly the same output as the original chain did.
"""

import numpy as np
from scipy.signal import butter, lfilter


class EffectsChain:
    """Full guitar signal chain: pure DSP, one numpy block in -> one out."""

    def __init__(self, samplerate: int):
        self.sr = samplerate

        # --- controllable parameters (read/written from any frontend) ---
        self.input_gain = 1.0        # 0 - 12 (soft-limited above unity)
        self.gate_threshold = 0.0    # 0 - 0.1 (linear amplitude)
        self.drive = 0.0             # 0 - 1
        self.cab_amount = 0.0        # 0 - 1  (0 = bright/off, 1 = full speaker cab)
        self.tone_low = 0.0          # -12 - +12 dB
        self.tone_mid = 0.0
        self.tone_high = 0.0
        self.chorus_mix = 0.0        # 0 - 1
        self.delay_time = 0.30       # seconds
        self.delay_feedback = 0.25   # 0 - 0.9
        self.delay_mix = 0.0         # 0 - 1
        self.reverb_mix = 0.0        # 0 - 1
        self.reverb_size = 0.5       # 0 - 1  (tail length / room size)
        self.master_volume = 0.8     # 0 - 1.5
        self.bypass = False

        # Optional analysis tap: called with the raw input block (pre-FX)
        # before any processing. Used by the tuner. Must be cheap & is
        # invoked from the audio thread, so it should only copy/queue data.
        self.analysis_hook = None

        # for level meters
        self.last_input_peak = 0.0
        self.last_output_peak = 0.0

        # Build all samplerate-dependent DSP state (filters, buffers, delays).
        self._configure_samplerate(samplerate)

    def _configure_samplerate(self, samplerate: int):
        """(Re)build every filter/buffer whose design depends on the sample
        rate. Safe to call again at start() so the chain can match whatever
        rate the audio device actually opens at (e.g. a 48 kHz USB cable),
        which avoids the driver resampling and the glitching/static that
        comes with a rate mismatch. Parameter *values* are untouched."""
        self.sr = samplerate
        nyq = samplerate / 2

        # --- EQ filter design (fixed band edges, gain applied via mix) ---
        self._lo_b, self._lo_a = butter(2, 300 / nyq, btype="lowpass")
        self._mid_b, self._mid_a = butter(2, [300 / nyq, 3000 / nyq], btype="bandpass")
        self._hi_b, self._hi_a = butter(2, 3000 / nyq, btype="highpass")
        self._lo_zi = np.zeros(max(len(self._lo_a), len(self._lo_b)) - 1)
        self._mid_zi = np.zeros(max(len(self._mid_a), len(self._mid_b)) - 1)
        self._hi_zi = np.zeros(max(len(self._hi_a), len(self._hi_b)) - 1)

        # --- cabinet sim: high-cut ~4.5kHz + low-cut ~90Hz (speaker rolloff) ---
        self._cab_lp_b, self._cab_lp_a = butter(2, min(4500, nyq * 0.98) / nyq, btype="lowpass")
        self._cab_hp_b, self._cab_hp_a = butter(2, 90 / nyq, btype="highpass")
        self._cab_lp_zi = np.zeros(max(len(self._cab_lp_a), len(self._cab_lp_b)) - 1)
        self._cab_hp_zi = np.zeros(max(len(self._cab_hp_a), len(self._cab_hp_b)) - 1)

        # --- chorus: modulated short delay ---
        self._chorus_base = 0.020    # 20 ms base delay
        self._chorus_depth = 0.007   # +/- 7 ms sweep
        self._chorus_lfo_hz = 0.8
        self._chorus_phase = 0.0
        self._chorus_tailmax = int((self._chorus_base + self._chorus_depth) * samplerate) + 4
        self._chorus_tail = np.zeros(self._chorus_tailmax, dtype=np.float32)

        # --- delay line ---
        max_delay_seconds = 1.5
        self._delay_buf = np.zeros(int(samplerate * max_delay_seconds), dtype=np.float32)
        self._delay_pos = 0

        # --- reverb: 4 parallel feedback combs + 1 allpass (Schroeder-style) ---
        base_combs = [1116, 1188, 1277, 1356]   # Freeverb tunings @44.1k
        base_allpass = 225
        scale = samplerate / 44100.0
        self._comb_delays = [max(2, int(d * scale)) for d in base_combs]
        self._allpass_delay = max(2, int(base_allpass * scale))
        self._comb_zi = [np.zeros(d) for d in self._comb_delays]
        self._allpass_zi = np.zeros(self._allpass_delay)

    def set_samplerate(self, samplerate: int):
        """Public: switch the chain to a new sample rate, rebuilding all
        rate-dependent DSP. No-op if unchanged."""
        if int(samplerate) != int(self.sr):
            self._configure_samplerate(int(samplerate))

    def _db_to_gain(self, db):
        return 10 ** (db / 20.0)

    @staticmethod
    def _soft_limit(y):
        """Identity for |y| <= 0.9, then smoothly compresses toward +/-1.
        Lets a big Input Gain boost round off gracefully instead of slamming
        into a hard clip (which is what makes cranked gain sound like harsh
        digital static). C1-continuous at the 0.9 knee."""
        a = np.abs(y)
        over = a > 0.9
        if np.any(over):
            y = y.astype(np.float32, copy=True)
            excess = (a[over] - 0.9) / 0.1
            y[over] = np.sign(y[over]) * (0.9 + 0.1 * np.tanh(excess)).astype(np.float32)
        return y

    # ------------------------------------------------------------------
    # Individual effect stages (each returns a new/processed block)
    # ------------------------------------------------------------------
    def _apply_cab(self, y):
        """Speaker cabinet emulation: rolls off fizzy highs + boomy lows."""
        amt = self.cab_amount
        if amt <= 0:
            return y
        wet, self._cab_lp_zi = lfilter(self._cab_lp_b, self._cab_lp_a, y, zi=self._cab_lp_zi)
        wet, self._cab_hp_zi = lfilter(self._cab_hp_b, self._cab_hp_a, wet, zi=self._cab_hp_zi)
        return (y * (1 - amt) + wet * amt).astype(np.float32)

    def _apply_chorus(self, y):
        """Single-voice modulated delay for shimmer/thickness on clean tones."""
        mix = self.chorus_mix
        if mix <= 0:
            return y
        n = len(y)
        if n == 0:
            return y
        tail = self._chorus_tail
        ext = np.concatenate([tail, y]).astype(np.float32)
        offset = len(tail)

        w = 2 * np.pi * self._chorus_lfo_hz / self.sr
        phase = self._chorus_phase + w * np.arange(n)
        delay_s = self._chorus_base + self._chorus_depth * 0.5 * (1 + np.sin(phase))
        read = offset + np.arange(n) - delay_s * self.sr
        read = np.clip(read, 0, len(ext) - 1)
        wet = np.interp(read, np.arange(len(ext)), ext).astype(np.float32)

        self._chorus_phase = float((self._chorus_phase + w * n) % (2 * np.pi))
        self._chorus_tail = ext[-self._chorus_tailmax:].copy()
        return (y * (1 - mix) + wet * mix).astype(np.float32)

    def _apply_reverb(self, y):
        """Schroeder reverb: parallel feedback combs into a single allpass."""
        mix = self.reverb_mix
        if mix <= 0:
            return y
        g = 0.70 + 0.28 * float(np.clip(self.reverb_size, 0.0, 1.0))  # 0.70..0.98
        acc = np.zeros(len(y), dtype=np.float64)
        for idx, D in enumerate(self._comb_delays):
            a = np.zeros(D + 1)
            a[0] = 1.0
            a[D] = -g
            out, self._comb_zi[idx] = lfilter([1.0], a, y, zi=self._comb_zi[idx])
            acc += out
        acc /= len(self._comb_delays)

        # one allpass diffuser
        ag = 0.5
        D = self._allpass_delay
        b = np.zeros(D + 1); b[0] = -ag; b[D] = 1.0
        a = np.zeros(D + 1); a[0] = 1.0; a[D] = -ag
        wet, self._allpass_zi = lfilter(b, a, acc, zi=self._allpass_zi)

        wet = (wet * 0.35).astype(np.float32)
        return (y * (1 - mix) + wet * mix).astype(np.float32)

    # ------------------------------------------------------------------
    def process(self, x: np.ndarray) -> np.ndarray:
        """x: 1-D float32 array in [-1, 1]. Returns processed array, same shape."""
        if self.analysis_hook is not None:
            try:
                self.analysis_hook(x)
            except Exception:
                pass  # analysis must never break the audio callback

        self.last_input_peak = float(np.max(np.abs(x))) if len(x) else 0.0

        if self.bypass:
            self.last_output_peak = self.last_input_peak
            return x

        y = x * self.input_gain
        # Tame big boosts so they round off instead of hard-clipping to static.
        if self.input_gain > 1.0:
            y = self._soft_limit(y)

        # Noise gate: attenuate (not hard-mute) below threshold -> less clicky
        if self.gate_threshold > 0:
            mask = np.abs(y) < self.gate_threshold
            y = np.where(mask, y * 0.05, y)

        # Drive / soft-clip distortion
        if self.drive > 0:
            k = 1 + self.drive * 18
            tk = np.tanh(k)
            y = np.tanh(y * k) / tk if tk != 0 else y

        # Cabinet sim (tames harsh distortion; also nice on clean)
        y = self._apply_cab(y)

        # 3-band EQ (split, apply gain per band, sum)
        lo, self._lo_zi = lfilter(self._lo_b, self._lo_a, y, zi=self._lo_zi)
        mid, self._mid_zi = lfilter(self._mid_b, self._mid_a, y, zi=self._mid_zi)
        hi, self._hi_zi = lfilter(self._hi_b, self._hi_a, y, zi=self._hi_zi)
        y = (lo * self._db_to_gain(self.tone_low) +
             mid * self._db_to_gain(self.tone_mid) +
             hi * self._db_to_gain(self.tone_high))

        # Chorus
        y = self._apply_chorus(y)

        # Delay / echo
        if self.delay_mix > 0:
            n = len(y)
            buf = self._delay_buf
            buflen = len(buf)
            delay_samples = int(self.delay_time * self.sr)
            delay_samples = max(1, min(delay_samples, buflen - 1))

            out_wet = np.empty(n, dtype=np.float32)
            pos = self._delay_pos
            fb = self.delay_feedback
            for i in range(n):
                read_pos = (pos - delay_samples) % buflen
                delayed = buf[read_pos]
                out_wet[i] = delayed
                buf[pos] = y[i] + delayed * fb
                pos = (pos + 1) % buflen
            self._delay_pos = pos
            y = y * (1 - self.delay_mix) + out_wet * self.delay_mix

        # Reverb
        y = self._apply_reverb(y)

        y = y * self.master_volume
        y = np.clip(y, -1.0, 1.0)

        self.last_output_peak = float(np.max(np.abs(y))) if len(y) else 0.0
        return y.astype(np.float32)
