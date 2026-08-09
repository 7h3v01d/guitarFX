# Guitar FX

Turn your PC into a guitar amp/effects box using a USB guitar cable
(the kind with a 1/4" jack on one end and USB on the other — it's a
built-in audio interface).

## What it does

Guitar in → **Noise Gate → Drive → Cabinet Sim → 3-Band EQ → Chorus → Delay → Reverb → Master**
→ speakers/headphones, processed live in small chunks (~6 ms blocks) so it feels
responsive enough to play along to. There's a built-in **tuner** and one-tap
**tone presets**.

The frontend is **skinnable** — the audio engine doesn't know or care what UI is
driving it, so you can reskin the whole look without touching any DSP code. Three
skins ship out of the box:

- **Stage** (default) — a dark pedalboard with rotary knobs, a live tuner, preset
  buttons, and glowing meters.
- **Classic** — a straightforward control panel of sliders.
- **Neon** — a compact dark rack of vertical faders.

## 1. Install

```bash
pip install -r requirements.txt
```

On Windows, just run **`setup.bat`** (creates a `.venv` and installs everything).

**Linux only:** you also need the PortAudio system library and Tk:
```bash
sudo apt-get install libportaudio2 python3-tk
```
(Windows and macOS don't need this extra step.)

## 2. Plug in your cable

Plug the USB end into your computer, and the 1/4" end straight into your guitar's
output jack. Give it a few seconds — your OS should detect it as a new audio device
(often "USB Audio Device" or "USB PnP Sound Device").

## 3. Run it

```bash
python main.py                 # launches the Stage skin (default)
python main.py --skin classic  # sliders
python main.py --skin neon     # fader rack
python main.py --list-skins    # see what's available
```

On Windows: **`run.bat`** (Stage), `run-classic.bat`, or `run-neon.bat`.

- Pick your USB cable as the **Input** device (auto-detected if its name contains "USB").
- Pick your speakers or headphones as the **Output** device.
  **Use headphones if possible** — speakers + live guitar input can cause feedback loops.
- Click **START** and play.

## Controls

- **Input Gain** — boost a quiet pickup
- **Noise Gate** — cuts hiss/hum when you're not playing
- **Drive** — 0 = clean, higher = more overdrive/distortion
- **Cabinet** — speaker-cab emulation; smooths harsh, fizzy distortion (great past ~0.5 with Drive)
- **EQ Low / Mid / High** — shape your tone
- **Chorus** — shimmer/thickness, lovely on clean sounds
- **Delay Time / Feedback / Mix** — echo
- **Reverb / Rvb Size** — room ambience and how long the tail rings
- **Master** — final output level
- **Bypass** — instant clean passthrough for A/B comparison

### Presets

Six factory tones ship in: **Clean, Crunch, Lead, Surf, Ambient, Metal**. In Stage
they're buttons across the top; in Classic/Neon they're a dropdown. **Save As…**
stores your own tone to `~/.guitarfx/presets.json` so it survives restarts, and it
shows up alongside the factory ones everywhere.

### Tuner

While the stream is running, the Stage skin shows the note you're playing and how
many cents sharp/flat you are — green when you're in tune. It also names the nearest
standard-tuning open string (E A D G B E) as a hint.

### Metronome

The Stage skin has a **METRO** bar: toggle it **ON**, set the **BPM** (or hit
**TAP** a few times in rhythm to set the tempo by feel), and choose **BEATS/BAR**
(4 for most songs, 3 for a waltz). The dot flashes teal on the downbeat and green
on the other beats, and the click is mixed into your output so you can play along.
It's independent of the guitar tone — turning it on doesn't change your sound.

### Looper

Build a song by yourself: record a phrase, loop it, and stack more parts on top.
In the Stage skin's **LOOPER** bar the big button cycles through the workflow:

1. **●  REC** — press to start recording your first phrase (this is the base loop).
2. **■  SET** — press again to close the loop; it starts repeating immediately.
3. **＋  DUB** — press to overdub: play a new part on top; it's added as a layer.
4. **■  DUB** — press to punch out; the layer joins the loop. Repeat 3–4 to stack more.

**Stop** pauses playback (the loop is kept), **Undo** removes the most recent
layer, and **Clear** wipes the loop to start over. The ring shows the loop
position and the number in the middle is how many layers you've stacked.

**Tip:** turn the **metronome on first**. The looper then gives you a **one-bar
count-in** (four clicks) before it records, and snaps the loop to a whole number
of bars — so your layers and the click stay perfectly lined up.

## Make it yours (re-theming)

Every colour and font in the Stage skin lives in `skins/stage/theme.json`. Want it
purple instead of teal? Change `"accent"` and `"accent_glow"` and relaunch — no code
edits. Same idea for `skins/classic/theme.json` and `skins/neon/theme.json`.

## Architecture (for building your own skin)

```
core/                    the "brain" — never touched when reskinning
  params.py                PARAM_SPEC: the list of tweakable controls (pure data)
  effects.py               EffectsChain: pure DSP, one numpy block in -> one out
  tuner.py                 Tuner: autocorrelation pitch detection
  presets.py               factory presets + user-preset persistence
  engine.py                AudioEngine: owns the sounddevice stream
  controller.py            GuitarFXController: the ONLY thing a skin talks to

skins/                   the "face" — pluggable frontends
  base.py                   FrontendSkin ABC + skin auto-discovery
  stage/                    pedalboard GUI (knobs, tuner, presets) + theme.json
  classic/                  control-panel GUI + theme.json
  neon/                     dark fader-rack GUI + theme.json

main.py                  discovers skins under skins/, launches the one you pick
tests/                   headless DSP/tuner/preset tests (pytest)
```

**To create a new skin:**

1. Make a folder `skins/your_skin/`.
2. Write a class implementing `skins.base.FrontendSkin`, using only the controller:
   ```python
   from skins.base import FrontendSkin

   class YourSkin(FrontendSkin):
       display_name = "Your Skin"

       def run(self, controller):
           # controller.list_input_devices() / list_output_devices()
           # controller.start(in_idx, out_idx) / controller.stop()
           # controller.param_spec()  -> {key: ParamSpec(label, min, max, default, unit, group)}
           # controller.get_param(key) / set_param(key, value)
           # controller.list_presets() / apply_preset(name) / save_preset(name)
           # controller.get_tuner()   -> TunerReading(freq, note, cents, nearest_string) | None
           # controller.get_bypass()  / set_bypass(bool)
           # controller.get_levels()  -> (input_peak, output_peak)
           ...
   ```
3. In `skins/your_skin/__init__.py`: `SKIN = YourSkin` (and `DISPLAY_NAME = ...`).
4. `python main.py --list-skins` — it shows up with zero other changes.

Because every skin builds its controls by looping over `controller.param_spec()`,
adding a new effect parameter to `core/effects.py` + `core/params.py` makes it appear
in *every* skin automatically.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```
(or `run-tests.bat` on Windows). 22 tests cover the DSP chain, the tuner, and the
preset system — all headless, no audio hardware needed.

## Troubleshooting

- **Too quiet:** three levers, in order — (1) In Windows, open *Settings → System →
  Sound → your USB input device* and push its **input level to 100%** (enable any
  "boost" if offered); these cables ship quiet. (2) Turn the **Input Gain** knob up —
  it now boosts up to 12× and rounds off smoothly instead of distorting. (3) Nudge
  **Master** up. Watch the **IN meter** — if it barely moves, it's the OS level (1);
  if IN moves but OUT is quiet, it's Master (3).
- **Crackling / static / dropouts:** almost always the audio buffer being too tight
  for the machine. The app now defaults to a safe 1024-frame buffer at the device's
  native rate, which fixes most cases. If it still crackles, raise the buffer:
  `controller.set_buffer_size(2048)` (or 4096) before START — more stable, slightly
  more latency. The engine also counts glitches; `controller.get_xruns()` climbing
  while you play confirms it's an underrun.
- **Cuts in and out (Windows):** the app now prefers the **WASAPI** version of your
  devices, which is far more stable than MME for live guitar. If your device list
  shows more than one entry for the same hardware, pick the WASAPI one. Keep other
  audio apps (browsers, games) closed while playing — they can grab the device.
- **Static only when Input Gain is high:** you're amplifying the cable's own noise
  floor — back the gain off and raise the OS input level / Master instead.
- **No sound:** double-check you selected the *right* input device (not your laptop's
  built-in mic) and that the cable is fully seated in the guitar jack.
- **Feedback squeal:** you're playing through speakers near the pickup, or Input Gain /
  Master too high — use headphones or lower the gain.
- **Harsh, fizzy distortion:** turn the **Cabinet** knob up.
- **"Could not start audio":** try a different output device, or close other apps
  holding the audio device exclusively.

## Notes

- Mono in, mono out — fine for a single electric guitar.
- Delay is a simple feedback line; reverb is a Schroeder comb/allpass network — both
  chosen to sound good without heavy CPU cost.
