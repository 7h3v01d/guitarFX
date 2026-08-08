#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Leon Priest
"""
Guitar FX — turn your PC into a guitar amp/effects box.

    python main.py                 # launch with the default skin
    python main.py --skin neon     # launch with a specific skin
    python main.py --list-skins    # see what's available

Architecture:
    core/       DSP + audio I/O + GuitarFXController (the stable API)
    skins/      pluggable frontends; each is a folder with its own
                look/layout/toolkit usage, talking only to the controller

To add a new skin, create skins/<your_skin>/ with an __init__.py that
sets SKIN = YourSkinClass (implementing skins.base.FrontendSkin). No
other file in this project needs to change.
"""

import argparse
import sys

from core.controller import GuitarFXController
from skins.base import discover_skins

DEFAULT_SKIN = "stage"


def main():
    skins = discover_skins()
    if not skins:
        print("No skins found under skins/. Nothing to launch.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Guitar FX")
    parser.add_argument(
        "--skin", default=DEFAULT_SKIN,
        help=f"Which frontend skin to launch (default: {DEFAULT_SKIN})"
    )
    parser.add_argument(
        "--list-skins", action="store_true",
        help="List available skins and exit"
    )
    args = parser.parse_args()

    if args.list_skins:
        print("Available skins:")
        for skin_id, cls in skins.items():
            marker = " (default)" if skin_id == DEFAULT_SKIN else ""
            print(f"  {skin_id:<12} {cls.display_name}{marker}")
        return

    if args.skin not in skins:
        print(f"Unknown skin '{args.skin}'. Available: {', '.join(skins)}")
        sys.exit(1)

    controller = GuitarFXController()
    skin = skins[args.skin]()
    try:
        skin.run(controller)
    finally:
        # Always make sure the audio stream doesn't keep running after
        # the UI closes, no matter how the skin's mainloop exits.
        controller.stop()


if __name__ == "__main__":
    main()
