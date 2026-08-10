# Guitar FX — Roadmap

Ideas and planned features, roughly in priority order. Nothing here is a
commitment to a date — it's a place to park where we're headed.

## Shipped

- **Reverse + loop level** (v2.5.0) — flip the loop to play backwards (◀ REV),
  and a loop-volume slider in the LOOPER bar.
- **Export loop to WAV** (v2.4.0) — save the mixed loop (all layers) to a mono
  16-bit WAV via the LOOPER bar's **⭳ WAV** button; peak-protected, timestamped
  under `~/.guitarfx/loops/` by default.
- **Looper** (v2.3.0) — live looping with overdub/layering, locked to the
  metronome. First pass sets the loop (quantised to whole bars when the click is
  on); later passes stack layers; one-bar count-in; Stop / Play / Undo / Clear
  and a progress ring in the Stage skin.
- **Metronome** (v2.2.0) — sample-accurate click with tap-tempo, adjustable
  BPM and beats-per-bar, an accented downbeat, and a beat-flash indicator in the
  Stage skin. Built on a shared clock the looper locks to.

## Near-term (stability & quality of life)

- **Stability / latency control in the UI.** The engine already supports it
  (`controller.set_buffer_size()`, `get_xruns()`, native-rate matching, WASAPI
  device preference on Windows). Surface a small "Audio" panel: a buffer-size
  selector (Low-latency / Balanced / Stable), the live sample rate, and a
  dropout counter so a bad setup is visible instead of just sounding broken.
- **Per-device input trim memory.** Remember the last-used input/output device
  and Input Gain per device, so her cable is set up the way she left it.

## Planned features

### Looper — follow-ups

Shipped in v2.3.0 (record / overdub / layer / undo / clear, bar-quantised,
one-bar count-in, progress ring). Still on the wish list:
- **Half / double speed** on the loop (octave up/down).
- **Feedback/decay** so older layers fade over repeats (Frippertronics-style).
- **Per-layer volume** (needs a small per-layer UI).
- **Redo** (currently undo only), and multi-level undo of the base layer.

### Metronome

Shipped in v2.2.0 (see "Shipped" above). Remaining follow-ups: a **count-in**
(one bar of clicks before looper recording) — the `count_in_bars` hook already
exists — and letting the **looper lock to this clock** so layers stay in time.

## Ideas / maybe later

- Preset **A/B compare** and preset categories (clean / dirty / ambient).
- A **tuner-only** big view for quick tuning without the full board.
- Simple **drum-pattern** backing (a step of the metronome idea) to jam over.
- MIDI or footswitch control for hands-free looper punch-in.
- Recording the full session (not just the loop) to `.wav`.
