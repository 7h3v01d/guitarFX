# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""Metronome tests. Pure numpy — no audio device or GUI required."""

import numpy as np

from core.metronome import Metronome

SR = 44100


def _render_seconds(m, seconds, block=1024):
    total = int(SR * seconds)
    out = []
    done = 0
    while done < total:
        n = min(block, total - done)
        out.append(m.render(n))
        done += n
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def _beat_starts(sig, thresh=0.05, refractory=None):
    """Onsets of clicks. A click is a decaying *sine*, so |sig| crosses the
    threshold many times within one click — after each detected onset we skip a
    refractory window so each click counts once."""
    if refractory is None:
        refractory = int(0.05 * SR)
    above = np.abs(sig) > thresh
    starts = []
    i, N = 0, len(sig)
    while i < N:
        if above[i]:
            starts.append(i)
            i += refractory
        else:
            i += 1
    return starts


def _count_beats(sig, **kw):
    return len(_beat_starts(sig, **kw))


def test_disabled_is_silent():
    m = Metronome(SR)  # enabled defaults False
    out = _render_seconds(m, 1.0)
    assert np.count_nonzero(out) == 0


def test_120bpm_gives_two_beats_per_second():
    m = Metronome(SR, bpm=120)
    m.set_enabled(True)
    out = _render_seconds(m, 1.0)
    assert _count_beats(out) in (2, 3)   # boundary beat at t=1.0 may or may not land


def test_60bpm_gives_one_beat_per_second():
    m = Metronome(SR, bpm=60)
    m.set_enabled(True)
    out = _render_seconds(m, 1.0)
    assert _count_beats(out) in (1, 2)


def test_beat_spacing_matches_bpm():
    m = Metronome(SR, bpm=100)
    m.set_enabled(True)
    out = _render_seconds(m, 3.0)
    starts = np.array(_beat_starts(out))
    gaps = np.diff(starts)
    expected = SR * 60 / 100          # 26460 samples
    assert np.all(np.abs(gaps - expected) < 0.02 * expected)


def test_downbeat_is_accented():
    m = Metronome(SR, bpm=120, beats_per_bar=4)
    m.set_enabled(True)
    out = _render_seconds(m, 2.0)
    starts = _beat_starts(out, thresh=0.02)

    def peak_at(s):
        return np.max(np.abs(out[s:s + int(0.04 * SR)]))

    assert peak_at(starts[0]) > peak_at(starts[1])


def test_render_is_continuous_across_block_sizes():
    a = Metronome(SR, bpm=137); a.set_enabled(True)
    b = Metronome(SR, bpm=137); b.set_enabled(True)
    out_small = _render_seconds(a, 2.0, block=133)     # awkward block size
    out_big = _render_seconds(b, 2.0, block=SR * 2)
    assert _count_beats(out_small) == _count_beats(out_big)


def test_tap_tempo_sets_bpm():
    m = Metronome(SR)
    t = 0.0
    for _ in range(4):
        m.tap(now=t)   # taps 0.5s apart -> 120 bpm
        t += 0.5
    assert abs(m.get_bpm() - 120.0) < 2.0


def test_set_samplerate_rebuilds_and_still_ticks():
    m = Metronome(44100, bpm=120)
    m.set_samplerate(48000)
    m.set_enabled(True)
    assert m.sr == 48000
    total = int(48000)
    out, done = [], 0
    while done < total:
        n = min(1024, total - done)
        out.append(m.render(n)); done += n
    assert np.count_nonzero(np.concatenate(out)) > 0


def test_bpm_is_clamped():
    m = Metronome(SR)
    m.set_bpm(5);     assert m.get_bpm() >= 30
    m.set_bpm(9999);  assert m.get_bpm() <= 300


def test_beat_counter_advances():
    m = Metronome(SR, bpm=120)
    m.set_enabled(True)
    _render_seconds(m, 1.05)
    assert m.beat_count >= 2
