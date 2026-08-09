# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
GuitarFXController is the ONLY thing a skin is allowed to talk to.

Skins must never import EffectsChain or AudioEngine directly, and must
never reach into sounddevice themselves. That keeps the contract small
and stable, so a skin written today keeps working even if the DSP
internals change later.

Design notes for skin authors:
- PARAM_SPEC describes every tweakable parameter (label, range, default,
  unit) so a skin can build its controls generically (loop + build a
  slider/knob per entry) instead of hardcoding N widgets by name.
- get_param/set_param are the only way to read/write a parameter value;
  set_param clamps to the valid range so a skin can't send garbage into
  the audio callback.
- Presets: list_presets()/apply_preset()/save_preset()/delete_preset()
  give a skin one-tap tones without knowing which params exist.
- Tuner: get_tuner() returns the current pitch reading (or None). The
  tuner is fed automatically from the audio input while the stream runs.
- Level metering + "stream state changed" notifications are delivered
  via subscribe_state() / get_levels().
"""

from typing import Callable, Optional

from . import presets as presets_mod
from .effects import EffectsChain
from .engine import AudioEngine, SAMPLE_RATE
from .params import PARAM_SPEC, ParamSpec  # re-exported for skins that import them
from .tuner import Tuner

__all__ = ["GuitarFXController", "PARAM_SPEC", "ParamSpec"]


class GuitarFXController:
    """Stable facade over the DSP + audio engine, for skins to drive."""

    def __init__(self):
        self.fx = EffectsChain(SAMPLE_RATE)
        self.engine = AudioEngine(self.fx)
        self.tuner = Tuner(SAMPLE_RATE)
        # Feed the tuner straight from the pre-FX input block.
        self.fx.analysis_hook = self.tuner.push
        self._state_listeners = []
        self._last_error: Optional[str] = None
        self._user_presets = presets_mod.load_user_presets()
        # Audio buffer size (frames). Bigger = more stable / fewer dropouts,
        # a little more latency. Skins may offer this as a "stability" control.
        self._buffer_size = self.engine.blocksize

    # ---------------------------------------------------------------
    # Devices
    # ---------------------------------------------------------------
    def _preferred_hostapi(self):
        """On Windows, prefer the WASAPI host API — it's markedly more stable
        for full-duplex than the default MME (which stutters/cuts out). The
        same physical device is enumerated once per host API; steering to
        WASAPI avoids the glitchy duplicates. Returns a hostapi index or None."""
        import sys
        if not sys.platform.startswith("win"):
            return None
        try:
            import sounddevice as sd
            for i, ha in enumerate(sd.query_hostapis()):
                if "wasapi" in ha["name"].lower():
                    return i
        except Exception:
            pass
        return None

    def _devices(self, kind):
        """kind: 'in' or 'out'. Returns [(global_index, name), ...], filtered
        to the preferred host API when available, else all devices."""
        import sounddevice as sd
        chan = "max_input_channels" if kind == "in" else "max_output_channels"
        devs = list(enumerate(sd.query_devices()))
        pref = self._preferred_hostapi()
        if pref is not None:
            filtered = [(i, d) for i, d in devs
                        if d[chan] > 0 and d["hostapi"] == pref]
            if filtered:
                return [(i, d["name"]) for i, d in filtered]
        # Fallback: every device with the right channel direction.
        return [(i, d["name"]) for i, d in devs if d[chan] > 0]

    def list_input_devices(self):
        """Returns [(index, name), ...] for devices with input channels."""
        return self._devices("in")

    def list_output_devices(self):
        """Returns [(index, name), ...] for devices with output channels."""
        return self._devices("out")

    def guess_guitar_input(self):
        """Best-effort pick of a likely USB guitar interface, else first input."""
        inputs = self.list_input_devices()
        for i, name in inputs:
            if "usb" in name.lower():
                return i
        return inputs[0][0] if inputs else None

    def default_output(self):
        import sounddevice as sd
        outputs = self.list_output_devices()
        try:
            default_idx = sd.default.device[1]
        except Exception:
            default_idx = None
        if any(i == default_idx for i, _ in outputs):
            return default_idx
        return outputs[0][0] if outputs else None

    # ---------------------------------------------------------------
    # Stream lifecycle
    # ---------------------------------------------------------------
    def start(self, input_device: int, output_device: int):
        try:
            # Match the device's native rate (avoids resampling glitches), and
            # rebuild the DSP + tuner for whatever rate actually opens.
            from .engine import device_samplerate
            wanted = device_samplerate(input_device)
            self.fx.set_samplerate(wanted)
            self.tuner.set_samplerate(wanted)
            actual = self.engine.start(
                input_device, output_device,
                samplerate=wanted, blocksize=self._buffer_size,
            )
            if actual != wanted:
                # Fallback rate kicked in; keep DSP/tuner in sync with reality.
                self.fx.set_samplerate(actual)
                self.tuner.set_samplerate(actual)
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
            self.engine.stop()
            self._notify_state()
            raise
        self._notify_state()

    # ---------------------------------------------------------------
    # Audio quality / stability
    # ---------------------------------------------------------------
    def set_buffer_size(self, frames: int):
        """Set the audio block size. Larger (e.g. 2048) = fewer dropouts/
        static at the cost of a little latency. Takes effect on next start()."""
        self._buffer_size = max(64, int(frames))

    def get_buffer_size(self) -> int:
        return self._buffer_size

    def get_xruns(self) -> int:
        """Number of buffer under/overruns since the stream started. If this
        keeps climbing while playing, that's the audible static -> raise the
        buffer size."""
        return getattr(self.engine, "xruns", 0)

    def get_proc_errors(self) -> int:
        """Number of DSP callback errors since start (should stay 0). Non-zero
        means the failsafe dry-passthrough kicked in."""
        return getattr(self.engine, "proc_errors", 0)

    def get_samplerate(self) -> int:
        """The rate the stream actually opened at (may differ from 44100)."""
        return getattr(self.engine, "samplerate", SAMPLE_RATE)

    def stop(self):
        self.engine.stop()
        self._notify_state()

    def is_running(self) -> bool:
        return self.engine.is_running()

    def last_error(self) -> Optional[str]:
        return self._last_error

    def subscribe_state(self, callback: Callable[[bool], None]):
        """callback(is_running) fires whenever the stream starts/stops."""
        self._state_listeners.append(callback)

    def _notify_state(self):
        running = self.is_running()
        for cb in self._state_listeners:
            cb(running)

    # ---------------------------------------------------------------
    # Parameters (generic — skins should mostly drive UI off PARAM_SPEC)
    # ---------------------------------------------------------------
    def param_spec(self):
        return PARAM_SPEC

    def get_param(self, key: str) -> float:
        return getattr(self.fx, key)

    def set_param(self, key: str, value: float):
        spec = PARAM_SPEC[key]
        clamped = max(spec.minimum, min(spec.maximum, float(value)))
        setattr(self.fx, key, clamped)

    def get_bypass(self) -> bool:
        return self.fx.bypass

    def set_bypass(self, value: bool):
        self.fx.bypass = bool(value)

    def reset_to_defaults(self):
        for key, spec in PARAM_SPEC.items():
            self.set_param(key, spec.default)
        self.set_bypass(False)

    # ---------------------------------------------------------------
    # Presets
    # ---------------------------------------------------------------
    def list_presets(self):
        """Return preset names: factory presets first, then user presets."""
        names = list(presets_mod.FACTORY_PRESETS.keys())
        names += [n for n in self._user_presets if n not in presets_mod.FACTORY_PRESETS]
        return names

    def is_user_preset(self, name: str) -> bool:
        return name in self._user_presets and name not in presets_mod.FACTORY_PRESETS

    def apply_preset(self, name: str):
        preset = self._user_presets.get(name) or presets_mod.FACTORY_PRESETS.get(name)
        if preset is None:
            raise KeyError(f"Unknown preset: {name}")
        presets_mod.apply_preset(preset, self.set_param, self.set_bypass)

    def current_as_preset(self) -> dict:
        snap = {key: self.get_param(key) for key in PARAM_SPEC}
        snap["bypass"] = self.get_bypass()
        return snap

    def save_preset(self, name: str):
        """Save the current settings as a user preset (persisted to disk)."""
        name = name.strip()
        if not name:
            raise ValueError("Preset name cannot be empty")
        self._user_presets[name] = self.current_as_preset()
        presets_mod.save_user_presets(self._user_presets)

    def delete_preset(self, name: str):
        if name in self._user_presets:
            del self._user_presets[name]
            presets_mod.save_user_presets(self._user_presets)

    # ---------------------------------------------------------------
    # Tuner
    # ---------------------------------------------------------------
    def get_tuner(self):
        """Return the current TunerReading, or None if no clear pitch."""
        return self.tuner.estimate()

    # ---------------------------------------------------------------
    # Metering
    # ---------------------------------------------------------------
    def get_levels(self):
        """Returns (input_peak, output_peak), both in [0, 1]."""
        return self.fx.last_input_peak, self.fx.last_output_peak
