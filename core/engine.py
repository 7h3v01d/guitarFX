# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Real-time full-duplex audio stream. Knows nothing about the GUI —
just pulls audio in, runs it through an EffectsChain, pushes audio out.
"""

import numpy as np
import sounddevice as sd

from .effects import EffectsChain

SAMPLE_RATE = 44100     # preferred rate; the device's native rate wins if it differs
BLOCK_SIZE = 1024       # bigger = more stable (fewer dropouts/static), a touch more latency
CHANNELS = 1            # guitar is mono


def device_samplerate(device_index, fallback=SAMPLE_RATE):
    """Best-guess native sample rate for a device. Matching it avoids the
    driver having to resample, which is a common source of crackle/static
    on cheap USB guitar cables (many are natively 48 kHz)."""
    try:
        info = sd.query_devices(device_index)
        sr = int(round(info.get("default_samplerate") or 0))
        return sr if sr > 0 else fallback
    except Exception:
        return fallback


class AudioEngine:
    def __init__(self, fx: EffectsChain):
        self.fx = fx
        self.metronome = None      # optional Metronome, mixed into the output
        self.stream = None
        self.blocksize = BLOCK_SIZE
        self.latency = "high"      # 'high' lets PortAudio pick a safe buffer
        self.samplerate = SAMPLE_RATE
        self.xruns = 0             # count of under/overruns since start (0 = clean)
        self.proc_errors = 0       # count of DSP callback errors (should stay 0)

    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            # Under/overruns surface here — the audible 'static'/crackle.
            # Count them so the UI can warn instead of silently glitching.
            self.xruns += 1
        try:
            x = indata[:, 0].astype(np.float32)
            y = self.fx.process(x)
            m = self.metronome
            if m is not None and m.enabled:
                y = y + m.render(len(y))
                np.clip(y, -1.0, 1.0, out=y)
            outdata[:, 0] = y
        except Exception:
            # A DSP error must NEVER abort the stream (that's a hard cut-out).
            # Fail safe: pass the dry input straight through and keep going.
            self.proc_errors += 1
            try:
                outdata[:, 0] = indata[:, 0]
            except Exception:
                outdata.fill(0)

    def _open(self, input_device, output_device, samplerate, blocksize, latency):
        return sd.Stream(
            samplerate=samplerate,
            blocksize=blocksize,
            dtype="float32",
            channels=CHANNELS,
            device=(input_device, output_device),
            callback=self._callback,
            latency=latency,
        )

    def start(self, input_device, output_device,
              samplerate=None, blocksize=None, latency=None):
        """Open the duplex stream as robustly as possible. Tries, in order:
          1. native device rate + requested block size
          2. native device rate + auto block size (host picks the safest)
          3. 44100 Hz + auto block size
        so we always end up with *some* working audio rather than an error."""
        self.stop()
        self.xruns = 0
        self.proc_errors = 0

        if blocksize is not None:
            self.blocksize = int(blocksize)
        if latency is not None:
            self.latency = latency
        if samplerate is None:
            samplerate = device_samplerate(input_device)

        attempts = [
            (samplerate, self.blocksize),
            (samplerate, 0),        # blocksize 0 -> PortAudio/host chooses optimal
            (SAMPLE_RATE, 0),
        ]
        last_err = None
        for sr, bs in attempts:
            try:
                self.stream = self._open(input_device, output_device,
                                         sr, bs, self.latency)
                self.stream.start()
                self.samplerate = int(sr)
                return self.samplerate
            except Exception as e:
                last_err = e
                self.stream = None
        raise last_err if last_err else RuntimeError("could not open audio stream")

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def is_running(self):
        return self.stream is not None and self.stream.active
