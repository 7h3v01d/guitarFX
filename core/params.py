# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
The parameter table: the single source of truth for what the DSP exposes.

Kept in its own module (no sounddevice / GUI imports) so skins, tests, and
tooling can introspect the controls without spinning up the audio engine.
Skins should build their controls by looping over PARAM_SPEC rather than
hardcoding widgets, so a new effect param shows up in every skin for free.
"""

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    key: str          # attribute name on EffectsChain
    label: str         # human-readable name for UI
    minimum: float
    maximum: float
    default: float
    unit: str = ""      # e.g. "dB", "s", "" for unitless
    group: str = ""     # optional UI grouping hint


# Ordered so skins that just iterate this dict get a sensible default layout.
PARAM_SPEC: "OrderedDict[str, ParamSpec]" = OrderedDict(
    (p.key, p) for p in [
        ParamSpec("input_gain", "Input Gain", 0.0, 12.0, 1.0, "x", "In"),
        ParamSpec("gate_threshold", "Noise Gate", 0.0, 0.1, 0.0, "", "In"),
        ParamSpec("drive", "Drive", 0.0, 1.0, 0.0, "", "Dirt"),
        ParamSpec("cab_amount", "Cabinet", 0.0, 1.0, 0.0, "", "Dirt"),
        ParamSpec("tone_low", "EQ Low", -12.0, 12.0, 0.0, "dB", "Tone"),
        ParamSpec("tone_mid", "EQ Mid", -12.0, 12.0, 0.0, "dB", "Tone"),
        ParamSpec("tone_high", "EQ High", -12.0, 12.0, 0.0, "dB", "Tone"),
        ParamSpec("chorus_mix", "Chorus", 0.0, 1.0, 0.0, "", "Mod"),
        ParamSpec("delay_time", "Delay Time", 0.05, 1.0, 0.30, "s", "Time"),
        ParamSpec("delay_feedback", "Delay Fbk", 0.0, 0.9, 0.25, "", "Time"),
        ParamSpec("delay_mix", "Delay Mix", 0.0, 1.0, 0.0, "", "Time"),
        ParamSpec("reverb_mix", "Reverb", 0.0, 1.0, 0.0, "", "Time"),
        ParamSpec("reverb_size", "Rvb Size", 0.0, 1.0, 0.5, "", "Time"),
        ParamSpec("master_volume", "Master", 0.0, 1.5, 0.8, "", "Out"),
    ]
)
