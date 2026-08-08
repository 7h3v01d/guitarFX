# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Neon skin: compact, dark, vertical-fader layout. Same controller API as
the classic skin, totally different look and widget arrangement — this
is the point of the skin system.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

from skins.base import FrontendSkin
from core.controller import GuitarFXController

_THEME_PATH = os.path.join(os.path.dirname(__file__), "theme.json")


def _load_theme():
    defaults = {
        "window_title": "Guitar FX — Neon",
        "window_size": "620x460",
        "bg": "#101014",
        "panel_bg": "#191922",
        "fg": "#e8e8f0",
        "accent": "#39ff88",
        "danger": "#ff4d6d",
        "muted": "#6a6a7a",
        "font_family": "Consolas",
        "font_size": 9,
    }
    try:
        with open(_THEME_PATH) as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass
    return defaults


class NeonSkin(FrontendSkin):
    display_name = "Neon"

    def run(self, controller: GuitarFXController) -> None:
        theme = _load_theme()
        app = _NeonApp(controller, theme)
        app.mainloop()


class _NeonApp(tk.Tk):
    def __init__(self, controller: GuitarFXController, theme: dict):
        super().__init__()
        self.controller = controller
        self.theme = theme

        self.title(theme["window_title"])
        self.geometry(theme["window_size"])
        self.configure(bg=theme["bg"])

        self._style = ttk.Style(self)
        self._configure_style()

        self._build_ui()
        self._refresh_devices()
        self._poll_meters()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self):
        t = self.theme
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass
        self._style.configure("Neon.TFrame", background=t["panel_bg"])
        self._style.configure("Neon.TLabel", background=t["panel_bg"],
                               foreground=t["fg"], font=(t["font_family"], t["font_size"]))
        self._style.configure("NeonValue.TLabel", background=t["panel_bg"],
                               foreground=t["accent"], font=(t["font_family"], t["font_size"], "bold"))
        self._style.configure("Neon.Horizontal.TProgressbar",
                               troughcolor=t["bg"], background=t["accent"])
        self._style.configure("Neon.Vertical.TScale", background=t["panel_bg"])

    # ---- UI ----
    def _build_ui(self):
        top = tk.Frame(self, bg=self.theme["bg"])
        top.pack(fill="x", padx=10, pady=8)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()

        tk.Label(top, text="IN", bg=self.theme["bg"], fg=self.theme["muted"],
                 font=(self.theme["font_family"], self.theme["font_size"])).grid(row=0, column=0, sticky="w")
        self.input_combo = ttk.Combobox(top, textvariable=self.input_var, state="readonly", width=28)
        self.input_combo.grid(row=0, column=1, padx=6)

        tk.Label(top, text="OUT", bg=self.theme["bg"], fg=self.theme["muted"],
                 font=(self.theme["font_family"], self.theme["font_size"])).grid(row=0, column=2, sticky="w")
        self.output_combo = ttk.Combobox(top, textvariable=self.output_var, state="readonly", width=28)
        self.output_combo.grid(row=0, column=3, padx=6)

        ttk.Button(top, text="\u21bb", width=3, command=self._refresh_devices).grid(row=0, column=4, padx=4)
        self.start_btn = tk.Button(top, text="\u25b6 START", command=self._toggle_stream,
                                    bg=self.theme["accent"], fg="#000000", relief="flat",
                                    font=(self.theme["font_family"], self.theme["font_size"], "bold"))
        self.start_btn.grid(row=0, column=5, padx=(10, 0))

        # meters
        meter_row = tk.Frame(self, bg=self.theme["bg"])
        meter_row.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(meter_row, text="IN", bg=self.theme["bg"], fg=self.theme["muted"]).pack(side="left")
        self.in_meter = ttk.Progressbar(meter_row, length=200, maximum=1.0,
                                         style="Neon.Horizontal.TProgressbar")
        self.in_meter.pack(side="left", padx=6)
        tk.Label(meter_row, text="OUT", bg=self.theme["bg"], fg=self.theme["muted"]).pack(side="left", padx=(16, 0))
        self.out_meter = ttk.Progressbar(meter_row, length=200, maximum=1.0,
                                          style="Neon.Horizontal.TProgressbar")
        self.out_meter.pack(side="left", padx=6)
        self.status_label = tk.Label(meter_row, text="STOPPED", bg=self.theme["bg"], fg=self.theme["danger"],
                                      font=(self.theme["font_family"], self.theme["font_size"], "bold"))
        self.status_label.pack(side="right")

        # vertical faders, one per param — the signature "neon" look
        rack = ttk.Frame(self, style="Neon.TFrame")
        rack.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._param_widgets = {}
        for col, (key, spec) in enumerate(self.controller.param_spec().items()):
            self._add_fader(rack, col, key, spec)

        bottom = tk.Frame(self, bg=self.theme["bg"])
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self.bypass_var = tk.BooleanVar(value=self.controller.get_bypass())
        tk.Checkbutton(bottom, text="BYPASS", variable=self.bypass_var,
                        command=lambda: self.controller.set_bypass(self.bypass_var.get()),
                        bg=self.theme["bg"], fg=self.theme["fg"], selectcolor=self.theme["panel_bg"],
                        activebackground=self.theme["bg"], activeforeground=self.theme["fg"]).pack(side="left")
        tk.Button(bottom, text="RESET", command=self._reset_defaults,
                  bg=self.theme["panel_bg"], fg=self.theme["fg"], relief="flat").pack(side="right")
        tk.Button(bottom, text="SAVE", command=self._save_preset,
                  bg=self.theme["panel_bg"], fg=self.theme["accent"], relief="flat").pack(side="right", padx=6)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(bottom, textvariable=self.preset_var, state="readonly",
                                          values=self.controller.list_presets(), width=12)
        self.preset_combo.pack(side="right", padx=6)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_preset())
        tk.Label(bottom, text="PRESET", bg=self.theme["bg"], fg=self.theme["muted"],
                 font=(self.theme["font_family"], self.theme["font_size"])).pack(side="right")

    def _add_fader(self, parent, col, key, spec):
        cell = ttk.Frame(parent, style="Neon.TFrame")
        cell.grid(row=0, column=col, padx=6, pady=6, sticky="ns")

        value_label = ttk.Label(cell, text=f"{self.controller.get_param(key):.2f}",
                                 style="NeonValue.TLabel")
        value_label.pack()

        var = tk.DoubleVar(value=self.controller.get_param(key))

        def _cb(val, key=key, value_label=value_label):
            v = float(val)
            self.controller.set_param(key, v)
            value_label.config(text=f"{v:.2f}")

        slider = ttk.Scale(cell, from_=spec.maximum, to=spec.minimum, orient="vertical",
                            variable=var, command=_cb, length=180, style="Neon.Vertical.TScale")
        slider.pack()

        label_text = spec.label.replace(" / ", "/\n").replace(" ", "\n")
        ttk.Label(cell, text=label_text, style="Neon.TLabel", justify="center").pack(pady=(4, 0))

        self._param_widgets[key] = (slider, value_label)

    # ---- devices ----
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
            match = next((f"{i}: {n}" for i, n in inputs if i == guess_in), None)
            if match:
                self.input_var.set(match)
        elif inputs:
            self.input_var.set(f"{inputs[0][0]}: {inputs[0][1]}")

        default_out = self.controller.default_output()
        if default_out is not None:
            match = next((f"{i}: {n}" for i, n in outputs if i == default_out), None)
            if match:
                self.output_var.set(match)
        elif outputs:
            self.output_var.set(f"{outputs[0][0]}: {outputs[0][1]}")

    def _selected_index(self, value):
        if not value:
            return None
        return int(value.split(":", 1)[0])

    def _toggle_stream(self):
        if self.controller.is_running():
            self.controller.stop()
            self.start_btn.config(text="\u25b6 START")
            self.status_label.config(text="STOPPED", fg=self.theme["danger"])
            return

        in_idx = self._selected_index(self.input_var.get())
        out_idx = self._selected_index(self.output_var.get())
        if in_idx is None or out_idx is None:
            messagebox.showwarning("Select devices", "Please choose an input and output device.")
            return
        try:
            self.controller.start(in_idx, out_idx)
        except Exception as e:
            messagebox.showerror("Could not start audio", str(e))
            return
        self.start_btn.config(text="\u25a0 STOP")
        self.status_label.config(text="LIVE", fg=self.theme["accent"])

    def _sync_controls(self):
        for key, (slider, value_label) in self._param_widgets.items():
            v = self.controller.get_param(key)
            slider.set(v)
            value_label.config(text=f"{v:.2f}")
        self.bypass_var.set(self.controller.get_bypass())

    def _apply_preset(self):
        name = self.preset_var.get()
        if name:
            self.controller.apply_preset(name)
            self._sync_controls()

    def _save_preset(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save preset", "Name this tone:", parent=self)
        if not name:
            return
        try:
            self.controller.save_preset(name)
        except ValueError as e:
            messagebox.showwarning("Save preset", str(e))
            return
        self.preset_combo["values"] = self.controller.list_presets()

    def _reset_defaults(self):
        self.controller.reset_to_defaults()
        self._sync_controls()

    def _poll_meters(self):
        in_peak, out_peak = self.controller.get_levels()
        self.in_meter["value"] = in_peak
        self.out_meter["value"] = out_peak
        self.after(60, self._poll_meters)

    def _on_close(self):
        self.controller.stop()
        self.destroy()
