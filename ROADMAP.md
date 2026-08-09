# Guitar FX — Roadmap

Ideas and planned features, roughly in priority order. Nothing here is a
commitment to a date — it's a place to park where we're headed.

## Near-term (stability & quality of life)

- **Stability / latency control in the UI.** The engine already supports it
  (`controller.set_buffer_size()`, `get_xruns()`, native-rate matching, WASAPI
  device preference on Windows). Surface a small "Audio" panel: a buffer-size
  selector (Low-latency / Balanced / Stable), the live sample rate, and a
  dropout counter so a bad setup is visible instead of just sounding broken.
- **Per-device input trim memory.** Remember the last-used input/output device
  and Input Gain per device, so her cable is set up the way she left it.

## Planned features

### Looper (live looping + overdubbing)

The headline feature. Record a short phrase, loop it, then stack more parts on
top in real time — the core of building a song by yourself.

Terms we're building toward:
- **Looping** — capture a short audio segment and play it back on repeat to make
  a steady rhythmic/melodic foundation.
- **Layering** — add more parts (riffs, beats, harmonies) over the repeating
  main loop.
- **Live looping / overdubbing** — do all of that in real time, the way a
  hardware loop pedal or a DAW does.

Sketch of how it fits the current design:
- A new **Looper stage** at the end of the chain (post-FX, pre-master), or a
  dedicated `core/looper.py` the controller owns, fed the same processed block
  the engine already produces.
- Transport: **Record → Overdub → Play → Stop → Clear**, plus **Undo** of the
  last overdub layer (keep a small stack of layers so undo/redo is cheap).
- The first recorded pass sets the loop length; later passes are summed
  (layered) into the loop buffer and wrapped to that length.
- **Sync to the metronome** (below): quantise the loop length to a whole number
  of bars so layers stay locked instead of drifting.
- A **loop meter / progress ring** in the Stage skin so she can see where the
  loop is and punch in overdubs on the beat.
- Nice-to-haves: per-layer volume, feedback/decay (older layers fade),
  half/double-speed, reverse, export the loop to a `.wav`.

### Metronome

A companion to the looper and useful on its own for practice.

- **Tempo (BPM)** with **tap-tempo**, and a **time signature** (4/4, 3/4, 6/8…).
- Audible click (accent the downbeat, softer on other beats) mixed into the
  output; generated in the DSP layer so it's sample-accurate.
- **Visual beat indicator** in the skin (flash / bouncing dot).
- Optional **count-in** (one bar of clicks before looper recording starts).
- Shared clock so the **looper locks to the metronome** — the thing that makes
  layered parts actually line up.

## Ideas / maybe later

- Preset **A/B compare** and preset categories (clean / dirty / ambient).
- A **tuner-only** big view for quick tuning without the full board.
- Simple **drum-pattern** backing (a step of the metronome idea) to jam over.
- MIDI or footswitch control for hands-free looper punch-in.
- Recording the full session (not just the loop) to `.wav`.
