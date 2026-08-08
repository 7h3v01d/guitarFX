# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Tone presets.

A preset is just a dict of {param_key: value} plus an optional "bypass".
Factory presets are pure data below. User presets are persisted to a JSON
file in the user's home dir so they survive restarts.

This module never imports sounddevice or a GUI toolkit; apply_preset()
takes a plain setter callable, so it is fully testable headlessly and the
controller stays the only thing that knows about the DSP.
"""

import json
import os
from collections import OrderedDict

_USER_DIR = os.path.join(os.path.expanduser("~"), ".guitarfx")
_USER_PATH = os.path.join(_USER_DIR, "presets.json")


# Ordered so the UI shows them in a musical "clean -> dirty -> spacey" arc.
FACTORY_PRESETS = OrderedDict([
    ("Clean", {
        "input_gain": 1.0, "gate_threshold": 0.004, "drive": 0.0,
        "cab_amount": 0.15, "tone_low": 1.0, "tone_mid": 0.0, "tone_high": 2.0,
        "chorus_mix": 0.0, "delay_time": 0.30, "delay_feedback": 0.2,
        "delay_mix": 0.0, "reverb_mix": 0.15, "reverb_size": 0.4,
        "master_volume": 0.85, "bypass": False,
    }),
    ("Crunch", {
        "input_gain": 1.2, "gate_threshold": 0.008, "drive": 0.35,
        "cab_amount": 0.5, "tone_low": 1.0, "tone_mid": 2.0, "tone_high": 1.0,
        "chorus_mix": 0.0, "delay_time": 0.30, "delay_feedback": 0.25,
        "delay_mix": 0.0, "reverb_mix": 0.12, "reverb_size": 0.4,
        "master_volume": 0.8, "bypass": False,
    }),
    ("Lead", {
        "input_gain": 1.3, "gate_threshold": 0.01, "drive": 0.6,
        "cab_amount": 0.6, "tone_low": 0.0, "tone_mid": 4.0, "tone_high": 2.0,
        "chorus_mix": 0.0, "delay_time": 0.35, "delay_feedback": 0.3,
        "delay_mix": 0.25, "reverb_mix": 0.2, "reverb_size": 0.5,
        "master_volume": 0.8, "bypass": False,
    }),
    ("Surf", {
        "input_gain": 1.0, "gate_threshold": 0.004, "drive": 0.0,
        "cab_amount": 0.2, "tone_low": 0.0, "tone_mid": -1.0, "tone_high": 4.0,
        "chorus_mix": 0.1, "delay_time": 0.22, "delay_feedback": 0.35,
        "delay_mix": 0.45, "reverb_mix": 0.4, "reverb_size": 0.6,
        "master_volume": 0.85, "bypass": False,
    }),
    ("Ambient", {
        "input_gain": 1.0, "gate_threshold": 0.003, "drive": 0.0,
        "cab_amount": 0.2, "tone_low": 1.0, "tone_mid": 0.0, "tone_high": 1.0,
        "chorus_mix": 0.5, "delay_time": 0.5, "delay_feedback": 0.5,
        "delay_mix": 0.5, "reverb_mix": 0.7, "reverb_size": 0.9,
        "master_volume": 0.8, "bypass": False,
    }),
    ("Metal", {
        "input_gain": 1.4, "gate_threshold": 0.02, "drive": 0.85,
        "cab_amount": 0.7, "tone_low": 3.0, "tone_mid": -6.0, "tone_high": 3.0,
        "chorus_mix": 0.0, "delay_time": 0.3, "delay_feedback": 0.2,
        "delay_mix": 0.0, "reverb_mix": 0.1, "reverb_size": 0.3,
        "master_volume": 0.8, "bypass": False,
    }),
])


def apply_preset(preset: dict, set_param, set_bypass) -> None:
    """
    Apply a preset dict using the supplied callables.

    set_param(key, value) is expected to clamp out-of-range values itself
    (the controller's set_param does). "bypass" is routed to set_bypass.
    Unknown keys are ignored so an old preset file can't crash a new build.
    """
    for key, value in preset.items():
        if key == "bypass":
            set_bypass(bool(value))
        else:
            try:
                set_param(key, value)
            except KeyError:
                pass  # param no longer exists; skip quietly


def load_user_presets() -> "OrderedDict[str, dict]":
    try:
        with open(_USER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return OrderedDict(data)
    except (FileNotFoundError, ValueError, OSError):
        pass
    return OrderedDict()


def save_user_presets(presets: dict) -> None:
    os.makedirs(_USER_DIR, exist_ok=True)
    tmp = _USER_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2)
    os.replace(tmp, _USER_PATH)  # atomic-ish on same filesystem
