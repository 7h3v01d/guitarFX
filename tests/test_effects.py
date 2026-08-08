# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""DSP tests. Pure numpy/scipy — no audio device or GUI required."""

import numpy as np
import pytest

from core.effects import EffectsChain

SR = 44100
BLOCK = 256


def _sine(freq, n, sr=SR, amp=0.5):
    t = np.arange(n) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _run_blocks(fx, signal, block=BLOCK):
    out = []
    for i in range(0, len(signal) - block + 1, block):
        out.append(fx.process(signal[i:i + block]))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def _high_energy(sig, sr=SR, cutoff=5000.0):
    spec = np.abs(np.fft.rfft(sig))
    freqs = np.fft.rfftfreq(len(sig), 1 / sr)
    return float(np.sum(spec[freqs >= cutoff] ** 2))


def test_default_chain_is_finite_and_shaped():
    fx = EffectsChain(SR)
    x = _sine(220, BLOCK)
    y = fx.process(x)
    assert y.shape == x.shape
    assert y.dtype == np.float32
    assert np.all(np.isfinite(y))


def test_bypass_is_exact_passthrough():
    fx = EffectsChain(SR)
    fx.drive = 0.9
    fx.reverb_mix = 1.0
    fx.bypass = True
    x = _sine(440, BLOCK)
    assert np.array_equal(fx.process(x), x)


def test_new_effects_off_by_default():
    """With defaults, the three new stages must be no-ops (revert baseline)."""
    fx = EffectsChain(SR)
    assert fx.cab_amount == 0.0
    assert fx.chorus_mix == 0.0
    assert fx.reverb_mix == 0.0


def test_cabinet_sim_reduces_high_frequency_energy():
    """Revert-proven: if the cab were a no-op, high energy wouldn't drop."""
    sig = _sine(8000, SR)  # 1s of a bright tone above the cab cutoff

    bright = EffectsChain(SR)
    bright.cab_amount = 0.0
    e_bright = _high_energy(_run_blocks(bright, sig))

    dark = EffectsChain(SR)
    dark.cab_amount = 1.0
    e_dark = _high_energy(_run_blocks(dark, sig))

    assert e_dark < e_bright * 0.5


def test_reverb_adds_a_tail_after_input_stops():
    """Impulse then silence: with reverb on, later blocks carry energy."""
    fx = EffectsChain(SR)
    fx.reverb_mix = 1.0
    fx.reverb_size = 0.9

    impulse = np.zeros(BLOCK, dtype=np.float32)
    impulse[0] = 1.0
    fx.process(impulse)

    silence = np.zeros(BLOCK, dtype=np.float32)
    tail_energy = 0.0
    for _ in range(20):  # ~120 ms later
        tail_energy += float(np.sum(fx.process(silence) ** 2))
    assert tail_energy > 1e-6

    # Baseline (reverb off) leaves only a tiny EQ-filter ring; reverb must
    # produce a dramatically larger tail. Revert-proven: no reverb -> fails.
    fx2 = EffectsChain(SR)
    fx2.reverb_mix = 0.0
    fx2.process(impulse)
    off_tail = sum(float(np.sum(fx2.process(silence) ** 2)) for _ in range(20))
    assert tail_energy > off_tail * 100


def test_chorus_changes_signal_but_keeps_it_bounded():
    fx = EffectsChain(SR)
    fx.chorus_mix = 0.6
    sig = _sine(330, SR)
    wet = _run_blocks(fx, sig)

    dry = _run_blocks(EffectsChain(SR), sig)  # chorus off
    assert not np.allclose(wet, dry)
    assert np.all(np.isfinite(wet))
    assert np.max(np.abs(wet)) <= 1.0


def test_drive_adds_harmonic_content():
    clean = EffectsChain(SR)
    dirty = EffectsChain(SR)
    dirty.drive = 0.8
    sig = _sine(200, SR)
    assert _high_energy(_run_blocks(dirty, sig)) > _high_energy(_run_blocks(clean, sig))


def test_everything_maxed_stays_finite_and_clipped():
    fx = EffectsChain(SR)
    fx.input_gain = 4.0
    fx.drive = 1.0
    fx.cab_amount = 1.0
    fx.tone_low = fx.tone_mid = fx.tone_high = 12.0
    fx.chorus_mix = 1.0
    fx.delay_mix = 1.0
    fx.delay_feedback = 0.9
    fx.reverb_mix = 1.0
    fx.reverb_size = 1.0
    fx.master_volume = 1.5

    out = _run_blocks(fx, _sine(150, SR * 2))
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0 + 1e-6


def test_analysis_hook_receives_input():
    fx = EffectsChain(SR)
    seen = []
    fx.analysis_hook = lambda blk: seen.append(blk.copy())
    x = _sine(440, BLOCK)
    fx.process(x)
    assert len(seen) == 1
    assert np.array_equal(seen[0], x)


def test_analysis_hook_errors_never_break_audio():
    fx = EffectsChain(SR)
    fx.analysis_hook = lambda blk: (_ for _ in ()).throw(RuntimeError("boom"))
    y = fx.process(_sine(440, BLOCK))
    assert np.all(np.isfinite(y))


# ---- input boost + soft limiter -------------------------------------

def test_input_gain_boosts_quiet_signal():
    quiet = _sine(220, BLOCK, amp=0.05)
    low = EffectsChain(SR)
    high = EffectsChain(SR)
    high.input_gain = 8.0
    out_low = low.process(quiet.copy())
    out_high = high.process(quiet.copy())
    # Boosted output must be clearly louder (revert-proven: if input_gain were
    # ignored these would match).
    assert np.max(np.abs(out_high)) > 3 * np.max(np.abs(out_low))


def test_soft_limit_is_transparent_below_knee_and_bounded_above():
    # Identity for |y| <= 0.9 ...
    mild = np.linspace(-0.9, 0.9, 64).astype(np.float32)
    assert np.allclose(EffectsChain._soft_limit(mild), mild, atol=1e-6)
    # ... and never exceeds 1.0 no matter how hard it's pushed.
    hot = np.linspace(-50, 50, 512).astype(np.float32)
    limited = EffectsChain._soft_limit(hot)
    assert np.all(np.abs(limited) <= 1.0 + 1e-6)
    assert np.all(np.isfinite(limited))


def test_cranked_input_gain_stays_bounded_and_finite():
    fx = EffectsChain(SR)
    fx.input_gain = 12.0
    out = _run_blocks(fx, _sine(200, SR))
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0 + 1e-6


# ---- samplerate matching --------------------------------------------

def test_set_samplerate_rebuilds_rate_dependent_dsp():
    fx = EffectsChain(44100)
    combs_44 = list(fx._comb_delays)
    fx.set_samplerate(48000)
    assert fx.sr == 48000
    # Reverb comb delays scale with rate, so they must actually change
    # (revert-proven: a no-op set_samplerate would leave these identical).
    assert fx._comb_delays != combs_44
    # And the chain still runs cleanly at the new rate.
    out = _run_blocks(fx, _sine(220, 48000))
    assert np.all(np.isfinite(out))


def test_set_samplerate_same_rate_is_noop():
    fx = EffectsChain(44100)
    combs = list(fx._comb_delays)
    fx.set_samplerate(44100)
    assert fx._comb_delays == combs
