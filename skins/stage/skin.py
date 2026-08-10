# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Stage skin: a dark "pedalboard" makeover.

Signature pieces:
  - Knob: a canvas-drawn rotary control. Drag up/down to turn, scroll to
    nudge, double-click to reset to default. Built generically off
    controller.param_spec(), so new params get a knob automatically.
  - Tuner strip: big note letter + a moving cents needle, green in tune.
  - Preset row: one tap for Clean/Crunch/Lead/Surf/Ambient/Metal + Save.
  - Glowing IN/OUT meters that animate live.

Everything visual is driven by theme.json, so re-theming (e.g. changing the
accent colour) is a one-line edit with no code changes.
"""

import json
import math
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from skins.base import FrontendSkin
from core.controller import GuitarFXController

_THEME_PATH = os.path.join(os.path.dirname(__file__), "theme.json")


def _load_theme():
    defaults = {
        "window_title": "Guitar FX — Stage",
        "window_size": "900x720",
        "bg": "#0d0f1a", "panel_bg": "#151827", "panel_edge": "#242a40",
        "fg": "#e8ecff", "muted": "#7a819e", "accent": "#00e0c6",
        "accent_glow": "#0a4f49", "hot": "#ff5c8a", "amber": "#ffb454",
        "good": "#4be08a", "danger": "#ff4d6d", "knob_face": "#0b0e18",
        "track": "#2a3150", "font_family": "Segoe UI", "mono_family": "Consolas",
        "font_size": 10,
    }
    try:
        with open(_THEME_PATH) as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass
    return defaults


# =====================================================================
# Reusable canvas widgets
# =====================================================================
class Knob(tk.Canvas):
    """Rotary knob. Drag vertically to turn, scroll to nudge, dbl-click resets."""

    SIZE = 88
    START_DEG = 135.0   # min position (screen coords: 0=E, 90=S, 180=W, 270=N)
    SWEEP_DEG = 270.0   # clockwise sweep to max

    def __init__(self, parent, spec, value, theme, on_change):
        super().__init__(parent, width=self.SIZE, height=self.SIZE + 34,
                         bg=theme["panel_bg"], highlightthickness=0)
        self.spec = spec
        self.theme = theme
        self.on_change = on_change
        self._value = float(value)
        self._drag_y = None

        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Double-Button-1>", self._reset)
        self.bind("<MouseWheel>", self._wheel)          # Windows / macOS
        self.bind("<Button-4>", lambda e: self._nudge(+1))  # Linux up
        self.bind("<Button-5>", lambda e: self._nudge(-1))  # Linux down
        self._draw()

    # ---- value <-> normalised position ----
    def _norm(self):
        lo, hi = self.spec.minimum, self.spec.maximum
        return 0.0 if hi == lo else (self._value - lo) / (hi - lo)

    def set_value(self, v):
        self._value = max(self.spec.minimum, min(self.spec.maximum, float(v)))
        self._draw()

    # ---- interaction ----
    def _press(self, event):
        self._drag_y = event.y

    def _drag(self, event):
        if self._drag_y is None:
            return
        dy = self._drag_y - event.y          # up = increase
        span = self.spec.maximum - self.spec.minimum
        self._value = max(self.spec.minimum,
                          min(self.spec.maximum, self._value + dy * span / 180.0))
        self._drag_y = event.y
        self._commit()

    def _wheel(self, event):
        self._nudge(1 if event.delta > 0 else -1)

    def _nudge(self, direction):
        span = self.spec.maximum - self.spec.minimum
        self._value = max(self.spec.minimum,
                          min(self.spec.maximum, self._value + direction * span / 50.0))
        self._commit()

    def _reset(self, _event):
        self._value = self.spec.default
        self._commit()

    def _commit(self):
        self._draw()
        self.on_change(self._value)

    # ---- drawing ----
    def _point(self, cx, cy, r, deg):
        rad = math.radians(deg)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    def _arc_points(self, cx, cy, r, deg0, deg1, steps=48):
        pts = []
        for i in range(steps + 1):
            d = deg0 + (deg1 - deg0) * i / steps
            pts.extend(self._point(cx, cy, r, d))
        return pts

    def _draw(self):
        t = self.theme
        self.delete("all")
        cx, cy, R = self.SIZE / 2, self.SIZE / 2, self.SIZE / 2 - 8

        # faint outer glow
        self.create_oval(cx - R - 4, cy - R - 4, cx + R + 4, cy + R + 4,
                         outline=t["accent_glow"], width=2)
        # body
        self.create_oval(cx - R, cy - R, cx + R, cy + R,
                         fill=t["knob_face"], outline=t["panel_edge"], width=2)
        # full track
        self.create_line(*self._arc_points(cx, cy, R - 4, self.START_DEG,
                                            self.START_DEG + self.SWEEP_DEG),
                         fill=t["track"], width=4, capstyle="round")
        # value arc
        end = self.START_DEG + self.SWEEP_DEG * self._norm()
        if end > self.START_DEG + 0.5:
            self.create_line(*self._arc_points(cx, cy, R - 4, self.START_DEG, end),
                             fill=t["accent"], width=4, capstyle="round")
        # pointer
        px, py = self._point(cx, cy, R - 10, end)
        ix, iy = self._point(cx, cy, R * 0.35, end)
        self.create_line(ix, iy, px, py, fill=t["fg"], width=3, capstyle="round")
        self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=t["accent"], outline="")

        # value text
        unit = self.spec.unit
        if self.spec.maximum <= 1.5 and self.spec.minimum >= 0:
            txt = f"{self._value:.2f}"
        else:
            txt = f"{self._value:+.1f}{unit}" if unit == "dB" else f"{self._value:.2f}{unit}"
        self.create_text(cx, cy + R + 10, text=self.spec.label,
                         fill=t["muted"], font=(t["font_family"], 8, "bold"))
        self.create_text(cx, cy + R + 24, text=txt,
                         fill=t["accent"], font=(t["mono_family"], 9, "bold"))


class Meter(tk.Canvas):
    """Horizontal glowing level meter with a clip zone."""

    def __init__(self, parent, theme, width=260, height=16):
        super().__init__(parent, width=width, height=height,
                         bg=theme["panel_bg"], highlightthickness=0)
        self.theme = theme
        self.w, self.h = width, height
        self._bg = self.create_rectangle(0, 0, width, height,
                                         fill=theme["knob_face"], outline=theme["panel_edge"])
        self._fill = self.create_rectangle(0, 0, 0, height, fill=theme["good"], outline="")

    def set_level(self, level):
        level = max(0.0, min(1.0, float(level)))
        self.coords(self._fill, 0, 0, self.w * level, self.h)
        if level > 0.92:
            color = self.theme["danger"]
        elif level > 0.7:
            color = self.theme["amber"]
        else:
            color = self.theme["good"]
        self.itemconfig(self._fill, fill=color)


class TunerDisplay(tk.Canvas):
    """Big note letter + a moving cents needle. Green when in tune."""

    def __init__(self, parent, theme, width=860, height=96):
        super().__init__(parent, width=width, height=height,
                         bg=theme["panel_bg"], highlightthickness=1,
                         highlightbackground=theme["panel_edge"])
        self.theme = theme
        self.w, self.h = width, height
        self._build()

    def _build(self):
        t = self.theme
        cx = self.w / 2
        base_y = self.h - 24
        # scale line + ticks
        self.create_line(60, base_y, self.w - 60, base_y, fill=t["track"], width=2)
        for cents in (-50, -25, 0, 25, 50):
            x = cx + (cents / 50.0) * (self.w / 2 - 70)
            h = 12 if cents == 0 else 7
            col = t["accent"] if cents == 0 else t["muted"]
            self.create_line(x, base_y - h, x, base_y + h, fill=col, width=2)
        self._note = self.create_text(cx, 34, text="--", fill=t["muted"],
                                      font=(t["mono_family"], 40, "bold"))
        self._hint = self.create_text(self.w - 90, 30, text="", fill=t["muted"],
                                      font=(t["font_family"], 10))
        self._needle = self.create_line(cx, base_y - 22, cx, base_y + 22,
                                        fill=t["muted"], width=4, capstyle="round")
        self._label = self.create_text(90, 30, text="TUNER", fill=t["muted"],
                                       font=(t["font_family"], 10, "bold"))

    def update_reading(self, reading):
        t = self.theme
        cx = self.w / 2
        base_y = self.h - 24
        if reading is None:
            self.itemconfig(self._note, text="--", fill=t["muted"])
            self.itemconfig(self._hint, text="")
            self.coords(self._needle, cx, base_y - 22, cx, base_y + 22)
            self.itemconfig(self._needle, fill=t["muted"])
            return
        in_tune = abs(reading.cents) < 5
        color = t["good"] if in_tune else (t["amber"] if abs(reading.cents) < 20 else t["hot"])
        self.itemconfig(self._note, text=reading.note, fill=color)
        arrow = "✓ in tune" if in_tune else ("♯ sharp — ease off" if reading.cents > 0
                                             else "♭ flat — tighten")
        self.itemconfig(self._hint, text=f"{reading.nearest_string} string\n{arrow}")
        x = cx + (max(-50, min(50, reading.cents)) / 50.0) * (self.w / 2 - 70)
        self.coords(self._needle, x, base_y - 22, x, base_y + 22)
        self.itemconfig(self._needle, fill=color)


# =====================================================================
# Skin
# =====================================================================
class StageSkin(FrontendSkin):
    display_name = "Stage"

    def run(self, controller: GuitarFXController) -> None:
        theme = _load_theme()
        app = _StageApp(controller, theme)
        app.mainloop()


class _StageApp(tk.Tk):
    def __init__(self, controller, theme):
        super().__init__()
        self.controller = controller
        self.theme = theme
        self.knobs = {}

        self.title(theme["window_title"])
        self.geometry(theme["window_size"])
        self.resizable(False, False)
        self.configure(bg=theme["bg"])
        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass
        self._style.configure("Stage.TCombobox", fieldbackground=theme["panel_bg"],
                              background=theme["panel_bg"])

        self._build_top()
        self._build_tuner()
        self._build_metronome()
        self._build_looper()
        self._build_presets()
        self._build_board()
        self._build_footer()

        self._refresh_devices()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- section builders ----
    def _panel(self, parent, **kw):
        return tk.Frame(parent, bg=self.theme["panel_bg"],
                        highlightbackground=self.theme["panel_edge"],
                        highlightthickness=1, **kw)

    def _build_top(self):
        t = self.theme
        top = self._panel(self)
        top.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(top, text="GUITAR  FX", bg=t["panel_bg"], fg=t["accent"],
                 font=(t["font_family"], 16, "bold")).pack(side="left", padx=(12, 4), pady=8)
        tk.Label(top, text="STAGE", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 16)).pack(side="left", pady=8)

        self.start_btn = tk.Button(top, text="▶  START", command=self._toggle_stream,
                                    bg=t["accent"], fg="#04231f", relief="flat",
                                    activebackground=t["good"], padx=18, pady=6,
                                    font=(t["font_family"], 12, "bold"))
        self.start_btn.pack(side="right", padx=12, pady=8)

        self.status_label = tk.Label(top, text="● STOPPED", bg=t["panel_bg"],
                                     fg=t["danger"], font=(t["font_family"], 10, "bold"))
        self.status_label.pack(side="right", padx=6)

        dev = tk.Frame(top, bg=t["panel_bg"])
        dev.pack(side="left", padx=20, pady=6)
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        tk.Label(dev, text="IN", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).grid(row=0, column=0, sticky="w")
        self.input_combo = ttk.Combobox(dev, textvariable=self.input_var,
                                        state="readonly", width=26, style="Stage.TCombobox")
        self.input_combo.grid(row=0, column=1, padx=6, pady=2)
        tk.Label(dev, text="OUT", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).grid(row=1, column=0, sticky="w")
        self.output_combo = ttk.Combobox(dev, textvariable=self.output_var,
                                         state="readonly", width=26, style="Stage.TCombobox")
        self.output_combo.grid(row=1, column=1, padx=6, pady=2)
        tk.Button(dev, text="⟳", command=self._refresh_devices, relief="flat",
                  bg=t["panel_edge"], fg=t["fg"], width=3).grid(row=0, column=2, rowspan=2, padx=6)

    def _build_tuner(self):
        wrap = tk.Frame(self, bg=self.theme["bg"])
        wrap.pack(fill="x", padx=12, pady=6)
        self.tuner_display = TunerDisplay(wrap, self.theme, width=876)
        self.tuner_display.pack(fill="x")

    def _build_metronome(self):
        t = self.theme
        bar = self._panel(self)
        bar.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(bar, text="METRO", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).pack(side="left", padx=(12, 8), pady=8)

        self.metro_btn = tk.Button(bar, text="OFF", width=5, command=self._toggle_metro,
                                   bg=t["panel_edge"], fg=t["fg"], relief="flat",
                                   activebackground=t["accent"], activeforeground="#04231f",
                                   font=(t["font_family"], 10, "bold"))
        self.metro_btn.pack(side="left", padx=4, pady=6)

        # Beat indicator: flashes accent on the downbeat, green on other beats.
        self.beat_dot = tk.Canvas(bar, width=26, height=26, bg=t["panel_bg"],
                                  highlightthickness=0)
        self._beat_oval = self.beat_dot.create_oval(5, 5, 21, 21,
                                                    fill=t["panel_edge"], outline=t["muted"])
        self.beat_dot.pack(side="left", padx=8)

        tk.Label(bar, text="BPM", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).pack(side="left", padx=(12, 4))
        self.bpm_var = tk.IntVar(value=int(round(self.controller.get_bpm())))
        self.bpm_spin = tk.Spinbox(bar, from_=30, to=300, width=5,
                                   textvariable=self.bpm_var, command=self._on_bpm,
                                   bg=t["panel_edge"], fg=t["fg"], relief="flat",
                                   justify="center", font=(t["font_family"], 11, "bold"))
        self.bpm_spin.pack(side="left", padx=4, pady=6)
        self.bpm_spin.bind("<Return>", lambda e: self._on_bpm())
        self.bpm_spin.bind("<FocusOut>", lambda e: self._on_bpm())

        tk.Button(bar, text="TAP", command=self._tap_tempo, width=5,
                  bg=t["panel_edge"], fg=t["accent"], relief="flat",
                  activebackground=t["accent"], activeforeground="#04231f",
                  font=(t["font_family"], 10, "bold")).pack(side="left", padx=8, pady=6)

        tk.Label(bar, text="BEATS/BAR", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).pack(side="left", padx=(12, 4))
        self.sig_var = tk.IntVar(value=self.controller.get_beats_per_bar())
        self.sig_spin = tk.Spinbox(bar, from_=1, to=12, width=3,
                                   textvariable=self.sig_var, command=self._on_sig,
                                   bg=t["panel_edge"], fg=t["fg"], relief="flat",
                                   justify="center", font=(t["font_family"], 11, "bold"))
        self.sig_spin.pack(side="left", padx=4, pady=6)

        self._last_beat_count = 0

    def _build_looper(self):
        t = self.theme
        bar = self._panel(self)
        bar.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(bar, text="LOOPER", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).pack(side="left", padx=(12, 8), pady=8)

        # progress ring with layer count in the middle
        self.loop_ring = tk.Canvas(bar, width=44, height=44, bg=t["panel_bg"],
                                   highlightthickness=0)
        self.loop_ring.create_oval(6, 6, 38, 38, outline=t["panel_edge"], width=4)
        self._loop_arc = self.loop_ring.create_arc(6, 6, 38, 38, start=90, extent=0,
                                                   style="arc", outline=t["accent"], width=4)
        self._loop_txt = self.loop_ring.create_text(22, 22, text="0",
                                                    fill=t["fg"],
                                                    font=(t["font_family"], 10, "bold"))
        self.loop_ring.pack(side="left", padx=8)

        self.loop_btn = tk.Button(bar, text="●  REC", width=9, command=self._loop_toggle,
                                  bg=t["danger"], fg="#2a0d0d", relief="flat",
                                  activebackground=t["accent"],
                                  font=(t["font_family"], 11, "bold"))
        self.loop_btn.pack(side="left", padx=4, pady=6)

        tk.Button(bar, text="■ Stop", command=self._loop_stop, relief="flat",
                  bg=t["panel_edge"], fg=t["fg"], activebackground=t["accent"],
                  font=(t["font_family"], 10, "bold")).pack(side="left", padx=4, pady=6)
        tk.Button(bar, text="↶ Undo", command=self._loop_undo, relief="flat",
                  bg=t["panel_edge"], fg=t["fg"], activebackground=t["accent"],
                  font=(t["font_family"], 10, "bold")).pack(side="left", padx=4, pady=6)
        tk.Button(bar, text="✕ Clear", command=self._loop_clear, relief="flat",
                  bg=t["panel_edge"], fg=t["danger"], activebackground=t["danger"],
                  font=(t["font_family"], 10, "bold")).pack(side="left", padx=4, pady=6)
        tk.Button(bar, text="⭳ WAV", command=self._loop_export, relief="flat",
                  bg=t["panel_edge"], fg=t["accent"], activebackground=t["accent"],
                  font=(t["font_family"], 10, "bold")).pack(side="left", padx=4, pady=6)
        self.rev_btn = tk.Button(bar, text="◀ REV", command=self._loop_reverse, relief="flat",
                                 bg=t["panel_edge"], fg=t["fg"], activebackground=t["accent"],
                                 font=(t["font_family"], 10, "bold"))
        self.rev_btn.pack(side="left", padx=4, pady=6)

        # loop level
        tk.Label(bar, text="LVL", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 8, "bold")).pack(side="left", padx=(12, 2))
        self.loop_vol = tk.Scale(bar, from_=0, to=100, orient="horizontal",
                                 showvalue=0, length=80, command=self._loop_volume,
                                 bg=t["panel_bg"], fg=t["fg"], troughcolor=t["panel_edge"],
                                 highlightthickness=0, relief="flat")
        self.loop_vol.set(int(self.controller.get_loop_volume() * 100))
        self.loop_vol.pack(side="left", padx=2, pady=6)

        self.loop_status = tk.Label(bar, text="empty", bg=t["panel_bg"], fg=t["muted"],
                                    font=(t["font_family"], 9, "bold"))
        self.loop_status.pack(side="left", padx=12)
        self._last_loop_state = None

    def _build_presets(self):
        t = self.theme
        self.preset_bar = self._panel(self)
        self.preset_bar.pack(fill="x", padx=12, pady=6)
        self._render_preset_buttons()

    def _render_preset_buttons(self):
        for child in self.preset_bar.winfo_children():
            child.destroy()
        t = self.theme
        tk.Label(self.preset_bar, text="PRESETS", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).pack(side="left", padx=(12, 8), pady=8)
        for name in self.controller.list_presets():
            tk.Button(self.preset_bar, text=name,
                      command=lambda n=name: self._apply_preset(n),
                      bg=t["panel_edge"], fg=t["fg"], relief="flat",
                      activebackground=t["accent"], activeforeground="#04231f",
                      padx=12, pady=4, font=(t["font_family"], 10, "bold")
                      ).pack(side="left", padx=4, pady=6)
        tk.Button(self.preset_bar, text="＋ Save", command=self._save_preset,
                  bg=t["panel_bg"], fg=t["accent"], relief="flat",
                  padx=12, pady=4, font=(t["font_family"], 10, "bold")
                  ).pack(side="right", padx=12, pady=6)

    def _build_board(self):
        t = self.theme
        board = self._panel(self)
        board.pack(fill="both", expand=True, padx=12, pady=6)
        grid = tk.Frame(board, bg=t["panel_bg"])
        grid.pack(padx=10, pady=10)

        per_row = 7
        for idx, (key, spec) in enumerate(self.controller.param_spec().items()):
            r, c = divmod(idx, per_row)
            knob = Knob(grid, spec, self.controller.get_param(key), t,
                        on_change=lambda v, k=key: self.controller.set_param(k, v))
            knob.grid(row=r, column=c, padx=6, pady=6)
            self.knobs[key] = knob

    def _build_footer(self):
        t = self.theme
        foot = self._panel(self)
        foot.pack(fill="x", padx=12, pady=(6, 12))

        self.bypass_var = tk.BooleanVar(value=self.controller.get_bypass())
        tk.Checkbutton(foot, text="BYPASS", variable=self.bypass_var,
                       command=lambda: self.controller.set_bypass(self.bypass_var.get()),
                       bg=t["panel_bg"], fg=t["fg"], selectcolor=t["knob_face"],
                       activebackground=t["panel_bg"], activeforeground=t["fg"],
                       font=(t["font_family"], 10, "bold")).pack(side="left", padx=12, pady=8)
        tk.Button(foot, text="RESET", command=self._reset,
                  bg=t["panel_edge"], fg=t["fg"], relief="flat", padx=12, pady=4
                  ).pack(side="left", padx=6, pady=8)

        meters = tk.Frame(foot, bg=t["panel_bg"])
        meters.pack(side="right", padx=12, pady=6)
        tk.Label(meters, text="IN", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).grid(row=0, column=0, padx=4)
        self.in_meter = Meter(meters, t)
        self.in_meter.grid(row=0, column=1, pady=2)
        tk.Label(meters, text="OUT", bg=t["panel_bg"], fg=t["muted"],
                 font=(t["font_family"], 9, "bold")).grid(row=1, column=0, padx=4)
        self.out_meter = Meter(meters, t)
        self.out_meter.grid(row=1, column=1, pady=2)

    # ---- actions ----
    def _apply_preset(self, name):
        self.controller.apply_preset(name)
        for key, knob in self.knobs.items():
            knob.set_value(self.controller.get_param(key))
        self.bypass_var.set(self.controller.get_bypass())

    def _save_preset(self):
        name = simpledialog.askstring("Save preset", "Name this tone:", parent=self)
        if not name:
            return
        try:
            self.controller.save_preset(name)
        except ValueError as e:
            messagebox.showwarning("Save preset", str(e))
            return
        self._render_preset_buttons()

    def _reset(self):
        self.controller.reset_to_defaults()
        for key, knob in self.knobs.items():
            knob.set_value(self.controller.get_param(key))
        self.bypass_var.set(False)

    # ---- metronome ----
    def _toggle_metro(self):
        t = self.theme
        on = not self.controller.is_metronome_enabled()
        self.controller.set_metronome_enabled(on)
        self.metro_btn.config(text="ON" if on else "OFF",
                              bg=t["accent"] if on else t["panel_edge"],
                              fg="#04231f" if on else t["fg"])

    def _on_bpm(self):
        try:
            self.controller.set_bpm(int(self.bpm_var.get()))
        except (tk.TclError, ValueError):
            pass

    def _on_sig(self):
        try:
            self.controller.set_beats_per_bar(int(self.sig_var.get()))
        except (tk.TclError, ValueError):
            pass

    def _tap_tempo(self):
        bpm = self.controller.tap_tempo()
        self.bpm_var.set(int(round(bpm)))

    # ---- looper ----
    _LOOP_BTN = {
        "idle": ("●  REC", "danger", "#2a0d0d"),
        "countin": ("…  WAIT", "panel_edge", None),
        "recording": ("■  SET", "accent", "#04231f"),
        "playing": ("＋  DUB", "good", "#04231f"),
        "overdubbing": ("■  DUB", "accent", "#04231f"),
        "stopped": ("▶  PLAY", "good", "#04231f"),
    }

    def _loop_toggle(self):
        self.controller.looper_toggle()
        self._refresh_loop(force=True)

    def _loop_stop(self):
        self.controller.looper_stop()
        self._refresh_loop(force=True)

    def _loop_undo(self):
        self.controller.looper_undo()
        self._refresh_loop(force=True)

    def _loop_clear(self):
        self.controller.looper_clear()
        self._refresh_loop(force=True)

    def _loop_reverse(self):
        self.controller.looper_reverse()
        t = self.theme
        on = self.controller.is_loop_reversed()
        self.rev_btn.config(text="▶ REV" if on else "◀ REV",
                            bg=t["accent"] if on else t["panel_edge"],
                            fg="#04231f" if on else t["fg"])
        self._refresh_loop(force=True)

    def _loop_volume(self, val):
        try:
            self.controller.set_loop_volume(int(val) / 100.0)
        except (tk.TclError, ValueError):
            pass

    def _loop_export(self):
        try:
            path = filedialog.asksaveasfilename(
                title="Save loop as WAV", defaultextension=".wav",
                filetypes=[("WAV audio", "*.wav")], parent=self)
        except Exception:
            path = None
        try:
            saved = self.controller.export_loop_wav(path if path else None)
        except ValueError as e:
            messagebox.showwarning("Export loop", str(e))
            return
        except Exception as e:
            messagebox.showerror("Export loop", f"Couldn't save the loop:\n{e}")
            return
        messagebox.showinfo("Loop saved", f"Saved to:\n{saved}")

    def _refresh_loop(self, force=False):
        t = self.theme
        st = self.controller.looper_state()
        name = st["state"]
        if force or name != self._last_loop_state:
            self._last_loop_state = name
            label, bg_key, fg = self._LOOP_BTN.get(name, ("●  REC", "danger", "#2a0d0d"))
            self.loop_btn.config(text=label, bg=t[bg_key],
                                 fg=fg if fg else t["fg"])
            layers = st["layers"]
            secs = st["length_seconds"]
            if name == "idle":
                self.loop_status.config(text="empty", fg=t["muted"])
            elif name in ("recording", "countin"):
                self.loop_status.config(
                    text="count-in…" if name == "countin" else "recording…",
                    fg=t["accent"])
            else:
                self.loop_status.config(
                    text=f"{layers} layer{'s' if layers != 1 else ''} · {secs:.1f}s",
                    fg=t["good"] if name != "stopped" else t["muted"])
            self.loop_ring.itemconfig(self._loop_txt, text=str(st["layers"]))
            # keep the REV button in sync (e.g. after Clear resets it)
            rev = self.controller.is_loop_reversed()
            self.rev_btn.config(text="▶ REV" if rev else "◀ REV",
                                bg=t["accent"] if rev else t["panel_edge"],
                                fg="#04231f" if rev else t["fg"])
        # progress ring updates every poll
        extent = -359.9 * st["position"] if st["has_loop"] else 0
        self.loop_ring.itemconfig(self._loop_arc, extent=extent)

    def _refresh_devices(self):
        try:
            inputs = self.controller.list_input_devices()
            outputs = self.controller.list_output_devices()
        except Exception as e:
            messagebox.showerror("Device error", str(e))
            return
        self.input_combo["values"] = [f"{i}: {name}" for i, name in inputs]
        self.output_combo["values"] = [f"{i}: {name}" for i, name in outputs]

        guess_in = self.controller.guess_guitar_input()
        if guess_in is not None:
            m = next((f"{i}: {n}" for i, n in inputs if i == guess_in), None)
            if m:
                self.input_var.set(m)
        elif inputs:
            self.input_var.set(f"{inputs[0][0]}: {inputs[0][1]}")

        default_out = self.controller.default_output()
        if default_out is not None:
            m = next((f"{i}: {n}" for i, n in outputs if i == default_out), None)
            if m:
                self.output_var.set(m)
        elif outputs:
            self.output_var.set(f"{outputs[0][0]}: {outputs[0][1]}")

    def _selected_index(self, value):
        return int(value.split(":", 1)[0]) if value else None

    def _toggle_stream(self):
        t = self.theme
        if self.controller.is_running():
            self.controller.stop()
            self.start_btn.config(text="▶  START")
            self.status_label.config(text="● STOPPED", fg=t["danger"])
            return
        in_idx = self._selected_index(self.input_var.get())
        out_idx = self._selected_index(self.output_var.get())
        if in_idx is None or out_idx is None:
            messagebox.showwarning("Select devices", "Please choose an input and output device.")
            return
        try:
            self.controller.start(in_idx, out_idx)
        except Exception as e:
            messagebox.showerror("Could not start audio",
                                 f"{e}\n\nTip: try a different output device, or a larger "
                                 f"BLOCK_SIZE in core/engine.py.")
            return
        self.start_btn.config(text="■  STOP")
        self.status_label.config(text="● LIVE", fg=t["good"])

    def _poll(self):
        in_peak, out_peak = self.controller.get_levels()
        self.in_meter.set_level(in_peak)
        self.out_meter.set_level(out_peak)
        if self.controller.is_running():
            self.tuner_display.update_reading(self.controller.get_tuner())
        else:
            self.tuner_display.update_reading(None)

        # Metronome beat flash: bright on a new beat (accent on the downbeat),
        # dim otherwise.
        count, cur = self.controller.metronome_beat_state()
        if count != self._last_beat_count:
            self._last_beat_count = count
            color = self.theme["accent"] if cur == 0 else self.theme["good"]
            self.beat_dot.itemconfig(self._beat_oval, fill=color)
        else:
            self.beat_dot.itemconfig(self._beat_oval, fill=self.theme["panel_edge"])

        # Looper transport / progress ring.
        self._refresh_loop()

        self.after(70, self._poll)

    def _on_close(self):
        self.controller.stop()
        self.destroy()
