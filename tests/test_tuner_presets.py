# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""Tuner + preset tests. No audio device or GUI required."""

import numpy as np
import pytest

from core.tuner import Tuner, freq_to_note, STANDARD_STRINGS
from core import presets as presets_mod
from core.params import PARAM_SPEC

SR = 44100


def _feed(tuner, freq, seconds=0.2, amp=0.4):
    n = int(SR * seconds)
    t = np.arange(n) / SR
    sig = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    for i in range(0, n, 256):
        tuner.push(sig[i:i + 256])


# ---- tuner ----------------------------------------------------------

def test_freq_to_note_a440_is_a4():
    note, cents = freq_to_note(440.0)
    assert note == "A4"
    assert abs(cents) < 0.5


def test_tuner_detects_concert_a():
    tuner = Tuner(SR)
    _feed(tuner, 440.0)
    r = tuner.estimate()
    assert r is not None
    assert r.note == "A4"
    assert abs(r.cents) < 5


def test_tuner_detects_low_e_string():
    tuner = Tuner(SR)
    _feed(tuner, 82.41)
    r = tuner.estimate()
    assert r is not None
    assert r.note == "E2"
    assert r.nearest_string == "E2"


def test_tuner_flags_slightly_sharp_note():
    tuner = Tuner(SR)
    _feed(tuner, 448.0)  # ~ +31 cents sharp of A4
    r = tuner.estimate()
    assert r is not None
    assert r.note == "A4"
    assert r.cents > 10


def test_tuner_returns_none_on_silence():
    tuner = Tuner(SR)
    tuner.push(np.zeros(4096, dtype=np.float32))
    assert tuner.estimate() is None


def test_all_standard_strings_are_recognised():
    for name, freq in STANDARD_STRINGS.items():
        tuner = Tuner(SR)
        _feed(tuner, freq)
        r = tuner.estimate()
        assert r is not None and r.note == name, f"{name} @ {freq}Hz -> {r}"


# ---- presets --------------------------------------------------------

def test_apply_preset_routes_params_and_bypass():
    written = {}
    bypass = {"v": None}
    preset = {"drive": 0.5, "reverb_mix": 0.3, "bypass": True}
    presets_mod.apply_preset(preset, lambda k, v: written.__setitem__(k, v),
                             lambda b: bypass.__setitem__("v", b))
    assert written == {"drive": 0.5, "reverb_mix": 0.3}
    assert bypass["v"] is True


def test_apply_preset_ignores_unknown_keys():
    written = {}
    presets_mod.apply_preset({"drive": 0.2, "not_a_real_param": 9},
                             lambda k, v: (_ for _ in ()).throw(KeyError(k))
                             if k == "not_a_real_param" else written.__setitem__(k, v),
                             lambda b: None)
    assert written == {"drive": 0.2}


def test_factory_presets_only_reference_valid_params():
    valid = set(PARAM_SPEC.keys()) | {"bypass"}
    for name, preset in presets_mod.FACTORY_PRESETS.items():
        unknown = set(preset) - valid
        assert not unknown, f"preset {name!r} has unknown keys: {unknown}"


def test_factory_preset_values_are_within_range():
    for name, preset in presets_mod.FACTORY_PRESETS.items():
        for key, spec in PARAM_SPEC.items():
            if key in preset:
                v = preset[key]
                assert spec.minimum <= v <= spec.maximum, \
                    f"{name}.{key}={v} out of [{spec.minimum},{spec.maximum}]"


def test_user_preset_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(presets_mod, "_USER_DIR", str(tmp_path))
    monkeypatch.setattr(presets_mod, "_USER_PATH", str(tmp_path / "presets.json"))
    data = {"MyTone": {"drive": 0.42, "bypass": False}}
    presets_mod.save_user_presets(data)
    assert presets_mod.load_user_presets() == data


def test_load_user_presets_tolerates_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(presets_mod, "_USER_PATH", str(tmp_path / "nope.json"))
    assert presets_mod.load_user_presets() == {}


# ---- tuner samplerate matching --------------------------------------

def test_tuner_tracks_samplerate_change():
    tuner = Tuner(44100)
    tuner.set_samplerate(48000)
    assert tuner.sr == 48000
    # Feed a 48 kHz A4 and confirm it's still read as A4 (revert-proven:
    # without updating sr the detected pitch would be off by 48000/44100).
    n = int(48000 * 0.2)
    t = np.arange(n) / 48000.0
    sig = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    for i in range(0, n, 256):
        tuner.push(sig[i:i + 256])
    r = tuner.estimate()
    assert r is not None
    assert r.note == "A4"
    assert abs(r.cents) < 8
