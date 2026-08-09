# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""Looper tests. Pure numpy — no audio device or GUI required."""

import numpy as np

from core.looper import Looper, IDLE, RECORDING, PLAYING, OVERDUBBING, STOPPED

SR = 48000


def _feed(lp, block):
    """Feed one block, return the playback (zeros if None)."""
    out = lp.process(block)
    return np.zeros(len(block), dtype=np.float32) if out is None else out


def _feed_many(lp, signal, block=1024):
    outs = []
    for i in range(0, len(signal), block):
        outs.append(_feed(lp, signal[i:i + block]))
    return np.concatenate(outs) if outs else np.zeros(0, dtype=np.float32)


def test_idle_is_silent_passthrough_none():
    lp = Looper(SR)
    assert lp.process(np.ones(512, dtype=np.float32)) is None
    assert lp.state == IDLE


def test_record_then_playback_repeats():
    lp = Looper(SR)
    lp.arm_record()
    assert lp.state == RECORDING
    phrase = np.linspace(0.1, 0.9, 4000).astype(np.float32)
    _feed_many(lp, phrase, block=512)
    lp.close_record()
    assert lp.state == PLAYING
    assert lp.has_loop()
    # Playback over 2 loop lengths should reproduce the phrase, twice.
    out = _feed_many(lp, np.zeros(len(phrase) * 2, dtype=np.float32), block=512)
    # allow for loop volume scaling
    expected = np.concatenate([phrase, phrase]) * lp.volume
    # lengths line up because no quantise was requested
    assert np.allclose(out[:len(expected)], expected, atol=1e-5)


def test_overdub_sums_layers():
    lp = Looper(SR)
    lp.arm_record()
    base_val, L = 0.2, 2400
    _feed(lp, np.full(L, base_val, dtype=np.float32))
    lp.close_record()
    # play exactly one loop so pos returns to 0
    _feed(lp, np.zeros(L, dtype=np.float32))
    lp.start_overdub()
    assert lp.state == OVERDUBBING
    over_val = 0.3
    _feed(lp, np.full(L, over_val, dtype=np.float32))
    lp.stop_overdub()
    assert lp.layer_count == 2
    out = _feed(lp, np.zeros(L, dtype=np.float32))
    # playback should now be (base + overdub) * volume  (revert-proven: without
    # summing it would still be just base)
    assert np.allclose(out, (base_val + over_val) * lp.volume, atol=1e-5)


def test_undo_removes_last_overdub():
    lp = Looper(SR)
    lp.arm_record()
    L = 1200
    _feed(lp, np.full(L, 0.2, dtype=np.float32))
    lp.close_record()
    for v in (0.1, 0.4):
        _feed(lp, np.zeros(L, dtype=np.float32))   # realign to loop top
        lp.start_overdub()
        _feed(lp, np.full(L, v, dtype=np.float32))
        lp.stop_overdub()
    assert lp.layer_count == 3
    lp.undo()
    assert lp.layer_count == 2
    out = _feed(lp, np.zeros(L, dtype=np.float32))
    assert np.allclose(out, (0.2 + 0.1) * lp.volume, atol=1e-5)


def test_quantise_to_whole_bars():
    lp = Looper(SR)
    spb = 1000
    lp.arm_record(samples_per_bar=spb)
    _feed_many(lp, np.ones(2300, dtype=np.float32), block=256)  # 2.3 bars
    lp.close_record()
    assert lp._length == 2000            # rounded to nearest whole bar (2)


def test_count_in_delays_capture():
    lp = Looper(SR)
    lp.arm_record(count_in_samples=500)
    assert lp.state == "countin"
    _feed(lp, np.ones(500, dtype=np.float32))   # exactly the count-in
    assert lp.state == "countin" or lp.state == RECORDING
    _feed(lp, np.full(1000, 0.5, dtype=np.float32))  # this should be captured
    lp.close_record()
    # captured length excludes the 500 count-in samples
    assert lp._length == 1000


def test_playback_wraps_across_boundary():
    lp = Looper(SR)
    lp.arm_record()
    L = 1000
    ramp = np.linspace(0, 1, L).astype(np.float32)
    _feed(lp, ramp)
    lp.close_record()
    # read in a block that straddles the loop end (700 + 700 > 1000)
    _feed(lp, np.zeros(700, dtype=np.float32))
    out = _feed(lp, np.zeros(700, dtype=np.float32))
    # second read starts at pos=700, wraps: [700..999] then [0..399]
    expected = np.concatenate([ramp[700:], ramp[:400]]) * lp.volume
    assert np.allclose(out, expected, atol=1e-5)


def test_clear_resets_to_idle():
    lp = Looper(SR)
    lp.arm_record()
    _feed(lp, np.ones(800, dtype=np.float32))
    lp.close_record()
    lp.clear()
    assert lp.state == IDLE
    assert not lp.has_loop()
    assert lp.process(np.ones(256, dtype=np.float32)) is None


def test_stop_then_play_keeps_loop():
    lp = Looper(SR)
    lp.arm_record()
    _feed(lp, np.full(1000, 0.3, dtype=np.float32))
    lp.close_record()
    lp.stop()
    assert lp.state == STOPPED
    assert _feed(lp, np.zeros(256, dtype=np.float32)).max() == 0.0  # silent
    lp.play()
    assert lp.state == PLAYING
    assert np.allclose(_feed(lp, np.zeros(256, dtype=np.float32)), 0.3 * lp.volume, atol=1e-5)


def test_blocksize_independent_recording():
    a = Looper(SR); a.arm_record()
    b = Looper(SR); b.arm_record()
    sig = np.sin(np.linspace(0, 20, 3000)).astype(np.float32)
    _feed_many(a, sig, block=64)
    _feed_many(b, sig, block=3000)
    a.close_record(); b.close_record()
    assert a._length == b._length
    assert np.allclose(a._mix, b._mix, atol=1e-6)


def test_toggle_cycles_states():
    lp = Looper(SR)
    lp.toggle(); assert lp.state == RECORDING
    _feed(lp, np.ones(500, dtype=np.float32))
    lp.toggle(); assert lp.state == PLAYING
    lp.toggle(); assert lp.state == OVERDUBBING
    lp.toggle(); assert lp.state == PLAYING
