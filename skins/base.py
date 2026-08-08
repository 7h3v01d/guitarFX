# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
The contract every skin must satisfy.

A skin is a directory under skins/ containing:
  - __init__.py that sets SKIN = YourSkinClass and DISPLAY_NAME = "..."
  - skin.py (or however you like) with the actual UI code
  - any assets (theme.json, images, etc.) it wants

main.py discovers skins by scanning this package's subdirectories and
importing their __init__.py, so adding a new skin never requires
touching main.py or core/.
"""

from abc import ABC, abstractmethod
import importlib
import pkgutil

from core.controller import GuitarFXController


class FrontendSkin(ABC):
    """Subclass this and implement run() to create a new skin."""

    #: Shown in --list-skins and window titles. Override in subclasses.
    display_name: str = "Unnamed Skin"

    @abstractmethod
    def run(self, controller: GuitarFXController) -> None:
        """
        Build and launch the UI, blocking until the user closes it.

        Implementations should:
          - call controller.list_input_devices()/list_output_devices()
            to populate device pickers
          - call controller.start(in_idx, out_idx) / controller.stop()
          - read controller.param_spec() to know what controls to build,
            and call controller.get_param()/set_param() to wire them up
          - call controller.stop() on window close, so the audio stream
            doesn't keep running after the UI disappears
        """
        raise NotImplementedError


def discover_skins() -> "dict[str, type]":
    """
    Scan skins/* subpackages for a SKIN class + DISPLAY_NAME, returning
    {skin_id: SKIN_CLASS}. skin_id is the subpackage's folder name, which
    is what users pass to `--skin`.
    """
    import skins  # the skins package itself, to walk its subpackages

    found = {}
    for module_info in pkgutil.iter_modules(skins.__path__):
        name = module_info.name
        if name == "base":
            continue
        try:
            mod = importlib.import_module(f"skins.{name}")
        except Exception as e:
            print(f"[skins] failed to load skin '{name}': {e}")
            continue
        skin_cls = getattr(mod, "SKIN", None)
        if skin_cls is None:
            continue
        found[name] = skin_cls
    return found
