# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Metronome: a sample-accurate click generator mixed into the output stream.

It renders short percussive clicks at a steady tempo, accenting the first beat
of each bar. It's driven block-by-block from the audio callback via render(),
so timing is sample-accurate and independent of GUI timers. Pure numpy — no
audio device or GUI needed, so it's fully unit-testable.

A shared clock like this is also what a looper will lock to, so loop layers
line up with the beat (see ROADMAP.md).
"""

import time

import numpy as np


class Metronome:
    def __init__(self, samplerate: int, bpm: float = 120.0,
                 beats_per_bar: int = 4, volume: float = 0.35):
        self.sr = int(samplerate)
        self._bpm = float(bpm)
        self.beats_per_bar = int(beats_per_bar)
        self.volume = float(volume)
        self.enabled = False
        self.count_in_bars = 0        # reserved for looper count-in

        # UI-facing, updated as beats fire (plain ints; safe to read from the
        # UI thread for a flash indicator).
        self.beat_count = 0           # total beats emitted since last reset
        self.current_beat = 0         # 0-based index of the last beat within its bar

        # tap-tempo state
        self._taps = []

        self._build_clicks()
        self.reset()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _build_clicks(self):
        """Pre-render the accent (downbeat) and normal click waveforms. The
        downbeat is both higher-pitched and louder so the '1' stands out."""
        self._click_accent = self._make_click(2000.0, dur=0.035)
        self._click_normal = (self._make_click(1200.0, dur=0.030) * 0.7).astype(np.float32)
        self._clicklen = max(len(self._click_accent), len(self._click_normal))
        self._tail = np.zeros(self._clicklen, dtype=np.float32)
        self._tail_len = 0

    def _make_click(self, freq, dur=0.035):
        n = max(1, int(self.sr * dur))
        t = np.arange(n) / self.sr
        env = np.exp(-t * 45.0)                     # fast percussive decay
        tone = np.sin(2 * np.pi * freq * t)
        return (tone * env).astype(np.float32)

    def _interval(self):
        """Samples between beats."""
        return self.sr * 60.0 / self._bpm

    def samples_per_beat(self) -> float:
        return self._interval()

    def samples_per_bar(self) -> float:
        return self._interval() * self.beats_per_bar

    def reset(self):
        """Restart the beat grid so the next render begins on a downbeat."""
        self._pos = 0.0
        self._next_beat = 0.0
        self._beat_idx = 0
        self._tail_len = 0
        self.beat_count = 0
        self.current_beat = 0

    def set_samplerate(self, samplerate: int):
        if int(samplerate) != self.sr:
            self.sr = int(samplerate)
            self._build_clicks()
            self.reset()

    def set_bpm(self, bpm: float):
        self._bpm = float(max(30.0, min(300.0, bpm)))
        self.reset()

    def get_bpm(self) -> float:
        return self._bpm

    def set_beats_per_bar(self, n: int):
        self.beats_per_bar = int(max(1, min(16, n)))
        self.reset()

    def set_enabled(self, on: bool):
        self.enabled = bool(on)
        if self.enabled:
            self.reset()          # start cleanly on a downbeat

    def tap(self, now: float = None) -> float:
        """Register a tap; once there are two or more, set BPM from the median
        interval. Returns the current BPM."""
        if now is None:
            now = time.monotonic()
        # forget taps older than 2s (a new tempo)
        self._taps = [t for t in self._taps if now - t < 2.0]
        self._taps.append(now)
        if len(self._taps) >= 2:
            gaps = np.diff(self._taps)
            bpm = 60.0 / float(np.median(gaps))
            self.set_bpm(bpm)
        return self._bpm

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    def _emit(self, out, offset, click):
        n = len(out)
        clen = len(click)
        if offset >= n:
            # entirely in the future — shouldn't happen, but guard anyway
            return
        end = offset + clen
        if end <= n:
            out[offset:end] += click
        else:
            fit = n - offset
            out[offset:] += click[:fit]
            rem = click[fit:]
            self._tail[:len(rem)] += rem
            self._tail_len = max(self._tail_len, len(rem))

    def render(self, n: int) -> np.ndarray:
        """Return n samples of click audio (float32) for the next block, and
        advance the clock. Returns silence (and does not advance) when off."""
        if not self.enabled or n <= 0:
            return np.zeros(max(0, n), dtype=np.float32)

        out = np.zeros(n, dtype=np.float32)

        # carry over any click that spilled past the previous block
        if self._tail_len > 0:
            k = min(self._tail_len, n)
            out[:k] += self._tail[:k]
            if self._tail_len > k:
                self._tail[:self._tail_len - k] = self._tail[k:self._tail_len]
            self._tail[max(0, self._tail_len - k):] = 0.0
            self._tail_len -= k

        interval = self._interval()
        window_end = self._pos + n
        while self._next_beat < window_end:
            offset = int(round(self._next_beat - self._pos))
            offset = max(0, min(offset, n - 1))
            in_bar = self._beat_idx % self.beats_per_bar
            click = self._click_accent if in_bar == 0 else self._click_normal
            self._emit(out, offset, click)
            self.current_beat = in_bar
            self.beat_count += 1
            self._beat_idx += 1
            self._next_beat += interval

        self._pos += n
        return (out * self.volume).astype(np.float32)
