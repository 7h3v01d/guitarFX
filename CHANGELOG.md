# Changelog

## 2.1.1 — Stability: stop the cut-outs

### Fixed
- **Cutting in and out / crackle under load.** Several causes addressed:
  - The **3-band EQ now skips its filters when flat** (the default). It was
    running three IIR filters every block for no tonal change — needless CPU
    that could push the audio callback past its deadline and drop out.
  - On Windows the app now **prefers the WASAPI** audio host API instead of the
    default MME, which stutters badly on full-duplex. (The same physical device
    is listed once per host API; we now steer to the stable WASAPI copy.)
  - The audio callback is **wrapped in a failsafe**: a transient DSP error can
    no longer abort the stream (which showed up as a hard cut-out). On error it
    passes the dry signal through and counts it (`controller.get_proc_errors()`).
  - Stream open now **falls back through auto buffer size** and then 44100 Hz,
    so a fussy device still ends up with working audio.

### Notes
- If you were selecting an "MME"/"DirectSound" copy of the cable before, you'll
  now see the WASAPI one — pick that.
- Roadmap added (`ROADMAP.md`): **looper (live looping + overdubbing)** and a
  **metronome** are the next planned features.
- Tests: 30 passing (two new, revert-proven, for the EQ fast-path).

## 2.1.0 — Input level + anti-static audio fixes

### Fixed
- **Static / crackle:** the stream now opens with a safe 1024-frame buffer and
  `latency="high"` (was a very tight 256 / `"low"`), and it matches the audio
  device's **native sample rate** instead of forcing 44100 — a rate mismatch on
  USB cables (many are 48 kHz) was a prime cause of the crackle. Buffer under/
  overruns are now counted (`controller.get_xruns()`) instead of silently ignored.
- **Quiet input:** the **Input Gain** knob range went from 4× to **12×**, so a weak
  passive-pickup signal can be brought up to a usable level.

### Added
- A transparent **input soft-limiter**: above unity, big boosts round off smoothly
  toward the ceiling instead of slamming into a hard clip (which sounded like harsh
  static). Fully transparent below the knee, so normal levels are unaffected.
- `controller.set_buffer_size()` / `get_buffer_size()` / `get_xruns()` /
  `get_samplerate()` so a skin can expose a "stability vs latency" control and warn
  on dropouts.
- `EffectsChain.set_samplerate()` and `Tuner.set_samplerate()` — the DSP and tuner
  rebuild cleanly for whatever rate the device opens at.

### Notes
- If it's still quiet, the biggest single fix is usually the **Windows input-level
  slider** for the USB device — see README troubleshooting.
- Six new revert-proven tests (28 total, all passing).

## 2.0.0 — Stage makeover + tone/feature upgrades

### Added
- **New "Stage" skin** (now the default): a dark pedalboard with custom
  canvas-drawn **rotary knobs** (drag up/down to turn, scroll-wheel to nudge,
  double-click to reset), animated glowing **IN/OUT meters**, a live **tuner**
  strip with a moving cents needle, and one-tap **preset** buttons. All colours
  come from `skins/stage/theme.json` — re-theming is a one-line edit.
- **Cabinet simulation** (`Cabinet` knob): speaker-style high/low rolloff that
  tames fizzy distortion and warms up clean tones.
- **Chorus** (`Chorus` knob): modulated short delay for shimmer on clean sounds.
- **Reverb** (`Reverb` + `Rvb Size` knobs): Schroeder-style room ambience.
- **Tuner**: real-time pitch detection (autocorrelation) exposed via
  `controller.get_tuner()`. Fed automatically from the input while playing.
- **Presets**: six factory tones — Clean, Crunch, Lead, Surf, Ambient, Metal —
  plus **Save As…** to store your own (persisted to `~/.guitarfx/presets.json`).
  Available in every skin (Stage buttons; Classic/Neon dropdowns).
- **Test suite** (`tests/`, 22 tests): DSP, tuner, and preset logic, runnable
  headlessly with `pytest`. Run via `run-tests.bat`.
- Convenience launchers: `run-classic.bat`, `run-neon.bat`, `run-tests.bat`.

### Changed
- The parameter table moved to `core/params.py` (no audio-layer import) so
  skins/tests can introspect controls without the sounddevice dependency.
- Classic and Neon windows enlarged to fit the four new effect controls, and
  gained a preset picker.
- SPDX (Apache-2.0) headers added across the source.

### Unchanged / compatibility
- All three new effects default to **off**, so a freshly loaded chain sounds
  identical to before until you dial them in or pick a preset.
- The `core` → `skins` contract is untouched: existing skins keep working, and
  the new effects appeared in Classic/Neon automatically (they build controls
  from `controller.param_spec()`).
