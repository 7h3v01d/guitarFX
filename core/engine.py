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
        self.stream = None
        self.blocksize = BLOCK_SIZE
        self.latency = "high"      # 'high' lets PortAudio pick a safe buffer
        self.samplerate = SAMPLE_RATE
        self.xruns = 0             # count of under/overruns since start (0 = clean)

    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            # Under/overruns show up here. They're the audible 'static'/crackle.
            # Count them so the UI can warn instead of silently glitching.
            self.xruns += 1
        x = indata[:, 0].astype(np.float32)
        y = self.fx.process(x)
        outdata[:, 0] = y

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
        """Open the duplex stream. If samplerate is None, use the input
        device's native rate (falling back to 44100). If that rate can't be
        opened, retry at 44100 so we always get *some* audio."""
        self.stop()
        self.xruns = 0

        if blocksize is not None:
            self.blocksize = int(blocksize)
        if latency is not None:
            self.latency = latency
        if samplerate is None:
            samplerate = device_samplerate(input_device)

        try:
            self.stream = self._open(input_device, output_device,
                                     samplerate, self.blocksize, self.latency)
            self.stream.start()
            self.samplerate = int(samplerate)
        except Exception:
            # Fall back to the classic 44.1k path.
            self.stream = self._open(input_device, output_device,
                                     SAMPLE_RATE, self.blocksize, self.latency)
            self.stream.start()
            self.samplerate = SAMPLE_RATE
        return self.samplerate

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
