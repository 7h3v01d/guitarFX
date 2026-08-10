# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""WAV I/O tests. Pure stdlib + numpy — no audio device required."""

import os
import numpy as np

from core.audio_io import write_wav_mono, read_wav_mono
from core.looper import Looper


def test_wav_roundtrip(tmp_path):
    sr = 48000
    sig = (0.5 * np.sin(np.linspace(0, 40, 4000))).astype(np.float32)
    p = os.path.join(tmp_path, "t.wav")
    write_wav_mono(p, sig, sr)
    back, sr2 = read_wav_mono(p)
    assert sr2 == sr
    assert len(back) == len(sig)
    # within 16-bit quantisation
    assert np.max(np.abs(back - sig)) < 1e-3


def test_wav_clips_out_of_range(tmp_path):
    p = os.path.join(tmp_path, "c.wav")
    write_wav_mono(p, np.array([5.0, -5.0, 0.0], dtype=np.float32), 44100)
    back, _ = read_wav_mono(p)
    assert back.max() <= 1.0 and back.min() >= -1.0


def test_render_mix_none_when_idle():
    lp = Looper(48000)
    assert lp.render_mix() is None


def test_render_mix_is_a_copy():
    lp = Looper(48000)
    lp.arm_record()
    lp.process(np.full(1000, 0.4, dtype=np.float32))
    lp.close_record()
    mix = lp.render_mix()
    assert mix is not None and len(mix) == 1000
    mix[:] = 999.0                      # mutating the copy...
    assert lp.render_mix().max() < 1.0  # ...must not touch the looper's buffer
