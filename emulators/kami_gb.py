from util import *
from emulator import Emulator
from test import *
from PIL import Image
import os
import subprocess
import sys

class KamiGB(Emulator):
    def __init__(self):
        # DMG-only (CLAUDE.md "Out of scope (DMG-only): all CGB/SGB tests"); no extra features.
        super().__init__("kami-gb", "https://github.com/kami-gb/kami-gb", startup_time=1.0,
                         features=set(), supported_models={"DMG"})
    
    def setup(self):
        # __file__ is emulators/kami_gb.py; project root is 3 levels up (emulators → GBEmulatorShootout → test → root)
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        candidates = [
            os.path.join(root, "build", "msvc",  "bin", "Release", "kami-gb.exe"),
            os.path.join(root, "build", "clang", "bin", "Release", "kami-gb.exe"),
            os.path.join(root, "build", "msvc",  "bin", "Debug",   "kami-gb.exe"),
            os.path.join(root, "build", "clang", "bin", "Debug",   "kami-gb.exe"),
        ]
        self.__bin_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
        if not os.path.exists(self.__bin_path):
            raise FileNotFoundError("kami-gb binary not found; build the project first. Searched:\n" + "\n".join(candidates))

    def startProcess(self, rom, *, model, required_features):
        # kami-gb only supports DMG: skip CGB/SGB and unsupported-feature ROMs (they crash on load).
        # Returning None makes the base Emulator.run record no result instead of launching the exe.
        if not self.canRun(model=model, required_features=required_features):
            return None
        # We pass --no-throttle to run as fast as possible for the shootout, --mute to avoid audio
        # device conflicts or noise, and --no-save so no .sav sidecars are written next to test ROMs.
        cmd = [self.__bin_path, os.path.abspath(rom), "--turbo", "--mute", "--no-save"]
        if sys.platform == "win32":
            cmd.append("--square-corners")
        
        # GBEmulatorShootout might expect us to be in a specific CWD
        # but kami-gb seems to handle absolute paths fine.
        return subprocess.Popen(cmd)

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None
        if screenshot.size == (160, 144):
            return screenshot
        # BOX (area-average) over each integer-scale block: solid game-pixel blocks
        # produce the exact expected shade while single-pixel OpenGL edge artifacts
        # at quad boundaries are averaged away, keeping diffs well under 50.
        return screenshot.resize((160, 144), Image.BOX)
