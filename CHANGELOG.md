# Changelog

# Changelog

## 2.5.0 — Loop reverse + level

### Added
- **Reverse (◀ REV):** flip the loop so it plays backwards. Implemented as a
  physical flip of every stored layer, so overdub, undo and WAV export all keep
  working normally afterwards — reverse again to flip back.
- **Loop level (LVL):** a slider in the LOOPER bar to set how loud the loop sits
  under your live playing.
- Controller API: `looper_reverse`, `is_loop_reversed` (loop volume via the
  existing `set_loop_volume` / `get_loop_volume`).

### Notes
- Tests: 60 passing (five new — reverse plays backwards, double-reverse restores,
  reverse keeps undo working, reverse is a safe no-op with no loop, and loop
  volume scales playback).

## 2.4.0 — Export loop to WAV

### Added
- **Save your loop.** The LOOPER bar has a new **⭳ WAV** button that writes the
  current loop — all layers mixed down — to a mono 16-bit PCM WAV file. Pick a
  location, or it saves a timestamped file under `~/.guitarfx/loops/`.
  - Peak-protected: layered overdubs that sum past full scale are scaled down so
    the file doesn't clip.
  - Uses the stream's actual sample rate, so pitch/length are correct.
  - Built on the standard library (`core/audio_io.py`) — no new dependencies.
- Controller API: `export_loop_wav(path=None)`; looper gained `render_mix()`
  (a safe copy of the mixed loop).

### Notes
- Tests: 55 passing (four new — WAV round-trip, out-of-range clipping, and that
  `render_mix` returns a copy rather than the live buffer).

## 2.3.0 — Looper (live looping + overdubbing)

### Added
- **Looper** (`core/looper.py`) — record a phrase, loop it, and stack layers on
  top in real time:
  - **Record → Set → Overdub → Punch-out** cycle on one button, plus **Stop**,
    **Play**, **Undo** (removes the last layer), and **Clear**.
  - **Locked to the metronome:** when the click is on, recording gets a **one-bar
    count-in** and the loop length is **quantised to whole bars**, so layers and
    the beat stay lined up. With the metronome off, it free-runs at whatever
    length you record.
  - Records the **post-FX** signal (loops include your tone), and mixes loop
    playback in **before** the click so the metronome never gets baked into a loop.
  - Efficient layer model with a running mix, so **undo** is clean and cheap.
  - Rebuilds on device sample-rate change; fails safe (a glitch can't abort audio).
- **Stage skin LOOPER bar:** cycling transport button, Stop / Undo / Clear, a
  **progress ring** with a live layer count, and a state readout.
- Controller API for skins: `looper_toggle`, `looper_stop`, `looper_play`,
  `looper_undo`, `looper_clear`, `looper_state`, `set_loop_volume` /
  `get_loop_volume`.

### Notes
- Loop length caps at 60 seconds (auto-closes if you run over).
- Follow-ups parked in ROADMAP.md: per-layer volume, feedback/decay, half/double
  speed, reverse, and export-loop-to-WAV.
- Tests: 51 passing (eleven new for the looper — record/playback, overdub
  summing, undo, bar-quantise, count-in, wrap-around, block-size independence).
- As with the metronome, the looper *logic* is fully unit-tested and every UI
  wire was statically verified, but the Stage bar itself renders first on your
  machine — send a traceback if anything's off.

## 2.2.0 — Metronome

### Added
- **Metronome** — a sample-accurate click generator (`core/metronome.py`) mixed
  into the output stream:
  - Adjustable **BPM** (30–300) and **beats per bar**, with an **accented
    downbeat** (louder + higher pitch).
  - **Tap-tempo** — tap the button in time and it sets the BPM from your taps.
  - A **beat-flash** indicator in the Stage skin (teal downbeat / green off-beats)
    and a **METRO** control bar (on/off, BPM, tap, beats-per-bar).
  - Timed off the audio clock (not a GUI timer), so it stays in time regardless
    of UI load, and it rebuilds cleanly when the device sample rate changes.
  - Defaults to **off**, and it's an independent reference tone — enabling it
    doesn't colour the guitar sound.
- Controller API for skins: `set_metronome_enabled` / `is_metronome_enabled`,
  `set_bpm` / `get_bpm`, `set_beats_per_bar` / `get_beats_per_bar`,
  `set_metronome_volume` / `get_metronome_volume`, `tap_tempo`,
  `metronome_beat_state`.

### Notes
- This is the shared clock the planned **looper** will lock to (see ROADMAP.md).
- Tests: 40 passing (ten new for the metronome — timing, tap-tempo, accent,
  block-boundary continuity, samplerate change).
- The Stage window grew slightly to fit the metronome bar. The metronome UI is
  the one piece I couldn't render-test in my environment (no Tk there), though
  its logic is fully tested and every control wire was statically verified — so
  if anything looks off on first launch, send the traceback.

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
