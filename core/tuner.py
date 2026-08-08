# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Real-time guitar tuner.

The audio thread calls push() with each input block (cheap: just copies
into a ring buffer). The UI thread calls estimate() on a timer to get the
current pitch. Pitch is found by normalised autocorrelation over the most
recent window, which is robust and cheap enough for a live tuner.

estimate() returns a TunerReading (or None if the signal is too quiet /
no clear pitch). Nothing here touches sounddevice or any GUI toolkit, so
it is fully testable headlessly.
"""

import threading
from dataclasses import dataclass

import numpy as np

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Standard-tuning open strings (Hz), handy for a "nearest string" hint.
STANDARD_STRINGS = {
    "E2": 82.41, "A2": 110.00, "D3": 146.83,
    "G3": 196.00, "B3": 246.94, "E4": 329.63,
}


@dataclass(frozen=True)
class TunerReading:
    freq: float          # detected fundamental, Hz
    note: str            # e.g. "A4"
    cents: float         # deviation from that note, -50..+50
    nearest_string: str  # closest standard open string, e.g. "E2"


def freq_to_note(freq: float):
    """Return (note_name_with_octave, cents_off) for a frequency in Hz."""
    if freq <= 0:
        return "--", 0.0
    midi = 69 + 12 * np.log2(freq / 440.0)
    nearest = int(round(midi))
    cents = (midi - nearest) * 100.0
    name = _NOTE_NAMES[nearest % 12]
    octave = nearest // 12 - 1
    return f"{name}{octave}", float(cents)


def _nearest_string(freq: float) -> str:
    return min(STANDARD_STRINGS, key=lambda s: abs(STANDARD_STRINGS[s] - freq))


class Tuner:
    def __init__(self, samplerate: int, window: int = 4096,
                 fmin: float = 60.0, fmax: float = 1000.0,
                 rms_floor: float = 0.005):
        self.sr = samplerate
        self.window = window
        self.fmin = fmin
        self.fmax = fmax
        self.rms_floor = rms_floor
        self._buf = np.zeros(window, dtype=np.float32)
        self._lock = threading.Lock()

    def set_samplerate(self, samplerate: int) -> None:
        """Match the actual device rate so pitch readings stay accurate."""
        with self._lock:
            self.sr = int(samplerate)
            self._buf[:] = 0.0

    def push(self, block: np.ndarray) -> None:
        """Feed an input block. Cheap; safe to call from the audio thread."""
        block = np.asarray(block, dtype=np.float32).ravel()
        n = len(block)
        if n == 0:
            return
        with self._lock:
            if n >= self.window:
                self._buf[:] = block[-self.window:]
            else:
                self._buf[:-n] = self._buf[n:]
                self._buf[-n:] = block

    def estimate(self):
        """Return a TunerReading, or None if no confident pitch is present."""
        with self._lock:
            x = self._buf.copy()

        x = x - np.mean(x)
        rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
        if rms < self.rms_floor:
            return None

        # Normalised autocorrelation.
        corr = np.correlate(x, x, mode="full")[len(x) - 1:]
        if corr[0] <= 0:
            return None
        corr = corr / corr[0]

        lag_min = max(1, int(self.sr / self.fmax))
        lag_max = min(len(corr) - 1, int(self.sr / self.fmin))
        if lag_max <= lag_min:
            return None

        segment = corr[lag_min:lag_max]
        peak = int(np.argmax(segment)) + lag_min
        if corr[peak] < 0.5:  # weak periodicity -> not a confident note
            return None

        # Parabolic interpolation around the peak for sub-sample accuracy.
        if 1 <= peak < len(corr) - 1:
            a, b, c = corr[peak - 1], corr[peak], corr[peak + 1]
            denom = (a - 2 * b + c)
            shift = 0.5 * (a - c) / denom if denom != 0 else 0.0
            peak_f = peak + shift
        else:
            peak_f = float(peak)

        freq = self.sr / peak_f
        if not (self.fmin <= freq <= self.fmax):
            return None

        note, cents = freq_to_note(freq)
        return TunerReading(freq=freq, note=note, cents=cents,
                            nearest_string=_nearest_string(freq))
