# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Looper: live looping + overdubbing, locked to the metronome clock.

Model
-----
- The FIRST record pass sets the loop length. If a bar length is supplied
  (from the metronome), the length is quantised to a whole number of bars so
  overdubs and the click stay lined up.
- Later passes are OVERDUBS: the live input is summed into a new layer that
  wraps to the loop length. Committed layers are kept separately and also
  summed into a running mix (the playback), so a layer can be removed cleanly
  with undo.
- A COUNT-IN simply delays the start of capture by a given number of samples
  (one bar); the metronome provides the audible clicks during that time.

It's driven block-by-block from the audio callback via process(); it captures
the live post-FX signal and returns the loop playback to mix into the output.
Pure numpy — no audio device or GUI needed, so it's fully unit-testable.

States: idle -> [countin] -> recording -> playing <-> overdubbing, plus stopped.
"""

import numpy as np

IDLE = "idle"
COUNTIN = "countin"
RECORDING = "recording"
PLAYING = "playing"
OVERDUBBING = "overdubbing"
STOPPED = "stopped"


class Looper:
    def __init__(self, samplerate: int, max_seconds: float = 60.0, volume: float = 0.85):
        self.sr = int(samplerate)
        self.max_seconds = float(max_seconds)
        self.volume = float(volume)
        self.state = IDLE
        self.reversed = False

        self._length = 0
        self._pos = 0
        self._layers = []          # committed layers (each self._length long)
        self._mix = None           # sum of committed layers = playback source
        self._rec_layer = None     # overdub currently being recorded

        # first-pass capture
        self._cap = np.zeros(int(self.sr * self.max_seconds), dtype=np.float32)
        self._cap_len = 0
        self._quantize_spb = None  # samples per bar, or None for no quantise
        self._countin_remaining = 0

    # ------------------------------------------------------------------
    # Introspection (for the UI)
    # ------------------------------------------------------------------
    @property
    def layer_count(self) -> int:
        return len(self._layers)

    @property
    def length_seconds(self) -> float:
        return self._length / self.sr if self._length else 0.0

    def position_fraction(self) -> float:
        """0..1 progress through the loop (0 when there's no loop)."""
        if self._length <= 0:
            return 0.0
        return self._pos / self._length

    def has_loop(self) -> bool:
        return self._length > 0

    def render_mix(self):
        """Return a copy of the full mixed loop (sum of all committed layers)
        as a float32 array, or None if there's no loop yet. Safe to call from
        another thread — it snapshots the current mix reference and copies it."""
        mix = self._mix
        if self._length <= 0 or mix is None:
            return None
        return np.asarray(mix, dtype=np.float32).copy()

    def is_active(self) -> bool:
        return self.state != IDLE

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def set_samplerate(self, samplerate: int):
        if int(samplerate) != self.sr:
            self.sr = int(samplerate)
            self._cap = np.zeros(int(self.sr * self.max_seconds), dtype=np.float32)
            self.clear()

    def arm_record(self, samples_per_bar=None, count_in_samples: int = 0):
        """Begin a fresh recording (only from idle). Optionally quantise the
        loop length to whole bars, and/or delay capture by count_in_samples."""
        if self.state != IDLE:
            return
        self._quantize_spb = int(samples_per_bar) if samples_per_bar else None
        self._cap_len = 0
        if count_in_samples > 0:
            self._countin_remaining = int(count_in_samples)
            self.state = COUNTIN
        else:
            self._countin_remaining = 0
            self.state = RECORDING

    def close_record(self):
        """Finish the first pass and start looping."""
        if self.state not in (RECORDING, COUNTIN):
            return
        length = self._cap_len
        if length <= 0:
            self.clear()
            return
        if self._quantize_spb:
            bars = max(1, int(round(length / self._quantize_spb)))
            length = bars * self._quantize_spb
        base = np.zeros(length, dtype=np.float32)
        copy_n = min(self._cap_len, length)
        base[:copy_n] = self._cap[:copy_n]
        self._length = length
        self._layers = [base]
        self._mix = base.copy()
        self._pos = 0
        self.state = PLAYING

    def start_overdub(self):
        if self.state in (PLAYING, STOPPED) and self._length > 0:
            if self.state == STOPPED:
                self._pos = 0
            self._rec_layer = np.zeros(self._length, dtype=np.float32)
            self.state = OVERDUBBING

    def stop_overdub(self, commit: bool = True):
        if self.state != OVERDUBBING:
            return
        if commit and self._rec_layer is not None:
            self._layers.append(self._rec_layer)
            self._mix = self._mix + self._rec_layer
        self._rec_layer = None
        self.state = PLAYING

    def stop(self):
        """Stop playback/recording but keep the loop."""
        if self.state == OVERDUBBING:
            self.stop_overdub(commit=True)
        if self.state == RECORDING:
            self.close_record()
        if self.state == COUNTIN:
            self.clear()
            return
        if self.state in (PLAYING,):
            self.state = STOPPED

    def play(self):
        if self.state == STOPPED and self._length > 0:
            self._pos = 0
            self.state = PLAYING

    def clear(self):
        self.state = IDLE
        self.reversed = False
        self._length = 0
        self._pos = 0
        self._layers = []
        self._mix = None
        self._rec_layer = None
        self._cap_len = 0
        self._countin_remaining = 0
        self._quantize_spb = None

    def reverse(self):
        """Flip the loop so it plays backwards. Physically reverses every stored
        layer + the mix (and mirrors the play position), so overdub, undo and
        export all keep working normally afterwards. Only when a loop exists and
        we're not mid-record."""
        if self._length <= 0 or self.state not in (PLAYING, STOPPED):
            return
        self._mix = self._mix[::-1].copy()
        self._layers = [layer[::-1].copy() for layer in self._layers]
        self._pos = (self._length - self._pos) % self._length
        self.reversed = not self.reversed

    def undo(self):
        """Remove the most recent overdub layer (or cancel one in progress).
        The base layer is kept — use clear() to wipe the whole loop."""
        if self.state == OVERDUBBING:
            self._rec_layer = None
            self.state = PLAYING
            return
        if len(self._layers) > 1:
            last = self._layers.pop()
            self._mix = self._mix - last

    def toggle(self):
        """Single-button pedal cycle (no count-in/quantise; the controller has
        a smarter version that wires those in)."""
        if self.state == IDLE:
            self.arm_record()
        elif self.state == RECORDING:
            self.close_record()
        elif self.state == PLAYING:
            self.start_overdub()
        elif self.state == OVERDUBBING:
            self.stop_overdub()
        elif self.state == STOPPED:
            self.play()

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    def _capture(self, block):
        m = len(block)
        if m == 0:
            return
        end = self._cap_len + m
        if end > len(self._cap):
            m = len(self._cap) - self._cap_len
            block = block[:m]
            end = len(self._cap)
        self._cap[self._cap_len:end] = block
        self._cap_len = end
        if self._cap_len >= len(self._cap):
            self.close_record()      # hit the max loop length -> auto close

    def _read(self, n):
        L = self._length
        pos = self._pos
        if pos + n <= L:
            return self._mix[pos:pos + n].copy()
        first = L - pos
        return np.concatenate([self._mix[pos:], self._mix[:n - first]])

    def _write_overdub(self, x, n):
        L = self._length
        pos = self._pos
        if pos + n <= L:
            self._rec_layer[pos:pos + n] += x
        else:
            first = L - pos
            self._rec_layer[pos:] += x[:first]
            self._rec_layer[:n - first] += x[first:]

    def _advance(self, n):
        self._pos = (self._pos + n) % self._length

    def process(self, x: np.ndarray):
        """Feed the live (post-FX) block; capture if recording/overdubbing and
        return the loop playback block to mix into the output (or None)."""
        n = len(x)
        st = self.state
        if st == IDLE or n == 0:
            return None

        if st == COUNTIN:
            if self._countin_remaining >= n:
                self._countin_remaining -= n
                return None
            # count-in ends partway through this block; record the remainder
            start = self._countin_remaining
            self._countin_remaining = 0
            self.state = RECORDING
            self._capture(np.asarray(x[start:], dtype=np.float32))
            return None

        if st == RECORDING:
            self._capture(np.asarray(x, dtype=np.float32))
            return None

        if st == STOPPED:
            return None

        # PLAYING or OVERDUBBING
        out = self._read(n)
        if st == OVERDUBBING:
            self._write_overdub(np.asarray(x, dtype=np.float32), n)
        self._advance(n)
        return (out * self.volume).astype(np.float32)
