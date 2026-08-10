# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Tiny WAV I/O helpers built on the standard library (no extra dependencies).
Mono, 16-bit PCM — enough to save a loop to a file she can keep or share.
"""

import wave

import numpy as np


def write_wav_mono(path: str, samples: np.ndarray, samplerate: int) -> str:
    """Write a 1-D float32 array in [-1, 1] to a mono 16-bit PCM WAV file.
    Values are clipped to [-1, 1] before conversion. Returns the path."""
    data = np.asarray(samples, dtype=np.float32).ravel()
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")   # little-endian int16
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(samplerate))
        w.writeframes(pcm.tobytes())
    return path


def read_wav_mono(path: str):
    """Read a 16-bit PCM WAV back as (float32 array, samplerate). Mostly for
    tests / round-tripping. If stereo, returns the first channel."""
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    pcm = np.frombuffer(raw, dtype="<i2")
    if ch > 1:
        pcm = pcm[::ch]
    return (pcm.astype(np.float32) / 32767.0), sr
