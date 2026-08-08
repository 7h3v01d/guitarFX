# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Classic skin: a straightforward control-panel GUI. Device pickers on top,
level meters, then one slider per parameter (built generically from
controller.param_spec(), so new params show up automatically).
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
        "window_title": "Guitar FX",
        "window_size": "480x680",
        "bg": "#f0f0f0",
        "accent": "#2e6f40",
        "danger": "#b3261e",
        "font_family": "TkDefaultFont",
        "font_size": 10,
    }
    try:
        with open(_THEME_PATH) as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass
    return defaults


class ClassicSkin(FrontendSkin):
    display_name = "Classic"

    def run(self, controller: GuitarFXController) -> None:
        theme = _load_theme()
        app = _ClassicApp(controller, theme)
        app.mainloop()


class _ClassicApp(tk.Tk):
    def __init__(self, controller: GuitarFXController, theme: dict):
        super().__init__()
        self.controller = controller
        self.theme = theme

        self.title(theme["window_title"])
        self.geometry(theme["window_size"])
        self.resizable(False, False)
        self.configure(bg=theme["bg"])

        self._build_ui()
        self._refresh_devices()
        self._poll_meters()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI construction ----
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        dev_frame = ttk.LabelFrame(self, text="Audio Devices")
        dev_frame.pack(fill="x", **pad)

        ttk.Label(dev_frame, text="Input (your USB guitar cable):").grid(
            row=0, column=0, sticky="w", padx=6, pady=4)
        self.input_var = tk.StringVar()
        self.input_combo = ttk.Combobox(dev_frame, textvariable=self.input_var,
                                         state="readonly", width=45)
        self.input_combo.grid(row=1, column=0, padx=6, pady=2, sticky="w")

        ttk.Label(dev_frame, text="Output (speakers/headphones):").grid(
            row=2, column=0, sticky="w", padx=6, pady=4)
        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(dev_frame, textvariable=self.output_var,
                                          state="readonly", width=45)
        self.output_combo.grid(row=3, column=0, padx=6, pady=2, sticky="w")

        btn_frame = ttk.Frame(dev_frame)
        btn_frame.grid(row=4, column=0, pady=8, sticky="w")
        ttk.Button(btn_frame, text="Refresh Devices",
                   command=self._refresh_devices).pack(side="left", padx=(6, 6))
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self._toggle_stream)
        self.start_btn.pack(side="left")

        self.status_label = ttk.Label(dev_frame, text="Stopped", foreground=self.theme["danger"])
        self.status_label.grid(row=5, column=0, sticky="w", padx=6, pady=(0, 6))

        meter_frame = ttk.LabelFrame(self, text="Levels")
        meter_frame.pack(fill="x", **pad)
        ttk.Label(meter_frame, text="Input").grid(row=0, column=0, padx=6, sticky="w")
        self.in_meter = ttk.Progressbar(meter_frame, length=380, maximum=1.0)
        self.in_meter.grid(row=0, column=1, padx=6, pady=4)
        ttk.Label(meter_frame, text="Output").grid(row=1, column=0, padx=6, sticky="w")
        self.out_meter = ttk.Progressbar(meter_frame, length=380, maximum=1.0)
        self.out_meter.grid(row=1, column=1, padx=6, pady=4)

        preset_frame = ttk.LabelFrame(self, text="Presets")
        preset_frame.pack(fill="x", **pad)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(
            preset_frame, textvariable=self.preset_var, state="readonly",
            values=self.controller.list_presets(), width=20)
        self.preset_combo.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Button(preset_frame, text="Load", command=self._apply_preset).grid(
            row=0, column=1, padx=4)
        ttk.Button(preset_frame, text="Save As…", command=self._save_preset).grid(
            row=0, column=2, padx=4)

        # Effects controls — built generically from the param spec
        fx_frame = ttk.LabelFrame(self, text="Effects")
        fx_frame.pack(fill="both", expand=True, **pad)

        self._param_labels = {}
        row = 0
        for key, spec in self.controller.param_spec().items():
            self._add_slider(fx_frame, row, key, spec)
            row += 1

        self.bypass_var = tk.BooleanVar(value=self.controller.get_bypass())
        ttk.Checkbutton(
            fx_frame, text="Bypass (dry passthrough)", variable=self.bypass_var,
            command=lambda: self.controller.set_bypass(self.bypass_var.get())
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(10, 0))
        row += 1

        ttk.Button(fx_frame, text="Reset to Defaults",
                   command=self._reset_defaults).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(10, 0))

    def _add_slider(self, parent, row, key, spec):
        unit = f" ({spec.unit})" if spec.unit else ""
        ttk.Label(parent, text=spec.label + unit, width=18).grid(
            row=row, column=0, sticky="w", padx=6, pady=3)

        var = tk.DoubleVar(value=self.controller.get_param(key))
        value_label = ttk.Label(parent, text=f"{var.get():.2f}", width=6)

        def _cb(val, key=key, value_label=value_label):
            v = float(val)
            self.controller.set_param(key, v)
            value_label.config(text=f"{v:.2f}")

        slider = ttk.Scale(parent, from_=spec.minimum, to=spec.maximum,
                            orient="horizontal", variable=var, command=_cb, length=250)
        slider.grid(row=row, column=1, padx=6, pady=3)
        value_label.grid(row=row, column=2, padx=4)
        self._param_labels[key] = (slider, value_label)

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

    def _selected_index(self, value: str):
        if not value:
            return None
        return int(value.split(":", 1)[0])

    # ---- start/stop ----
    def _toggle_stream(self):
        if self.controller.is_running():
            self.controller.stop()
            self.start_btn.config(text="Start")
            self.status_label.config(text="Stopped", foreground=self.theme["danger"])
            return

        in_idx = self._selected_index(self.input_var.get())
        out_idx = self._selected_index(self.output_var.get())
        if in_idx is None or out_idx is None:
            messagebox.showwarning("Select devices", "Please choose an input and output device.")
            return
        try:
            self.controller.start(in_idx, out_idx)
        except Exception as e:
            messagebox.showerror(
                "Could not start audio",
                f"{e}\n\nTip: try a larger block size, or pick a different output device."
            )
            return
        self.start_btn.config(text="Stop")
        self.status_label.config(text="Running", foreground=self.theme["accent"])

    def _sync_controls(self):
        for key, (slider, value_label) in self._param_labels.items():
            v = self.controller.get_param(key)
            slider.set(v)
            value_label.config(text=f"{v:.2f}")
        self.bypass_var.set(self.controller.get_bypass())

    def _apply_preset(self):
        name = self.preset_var.get()
        if not name:
            return
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
