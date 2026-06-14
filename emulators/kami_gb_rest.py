from util import *
from emulator import Emulator, TestResult
from test import *
from PIL import Image
import os
import subprocess
import sys
import requests
import io
import time

class KamiGBRest(Emulator):
    def __init__(self, port=8080):
        super().__init__("kami-gb-rest", "https://github.com/kami-gb/kami-gb", startup_time=0.5)
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}/api/v1"
        self.__bin_path = None

    def setup(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        candidates = [
            os.path.join(root, "build", "msvc",  "bin", "Release", "kami-gb.exe"),
            os.path.join(root, "build", "clang", "bin", "Release", "kami-gb.exe"),
            os.path.join(root, "build", "msvc",  "bin", "Debug",   "kami-gb.exe"),
            os.path.join(root, "build", "clang", "bin", "Debug",   "kami-gb.exe"),
        ]
        self.__bin_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
        if not os.path.exists(self.__bin_path):
            raise FileNotFoundError("kami-gb binary not found; build the project first.")

    def startProcess(self, rom, *, model, required_features):
        # We use --rest-api=PORT and --turbo to run fast.
        # We also use --mute to avoid audio device conflicts.
        # --headless avoids opening windows during parallel testing.
        cmd = [
            self.__bin_path, 
            os.path.abspath(rom), 
            "--turbo", 
            "--mute", 
            "--headless",
            f"--rest-api={self.port}"
        ]
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def isWindowOpen(self):
        # Instead of checking for a window, we check if the API is responsive
        try:
            r = requests.get(f"{self.base_url}/ping", timeout=0.1)
            return r.status_code == 200
        except:
            return False

    def getScreenshot(self):
        try:
            r = requests.get(f"{self.base_url}/frame?format=png", timeout=0.5)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content))
        except:
            pass
        return None

    def run(self, test):
        print(f"Running {test} on {self.name} (port {self.port})")

        sav_file = os.path.splitext(test.rom)[0] + ".sav"
        if os.path.exists(sav_file):
            os.unlink(sav_file)

        p = self.startProcess(test.rom, model=test.model, required_features=test.required_features)
        if p is None:
            return None

        # Wait for API to be ready
        start_wait = time.monotonic()
        while not self.isWindowOpen():
            if time.monotonic() - start_wait > 10.0:
                self.endProcess(p)
                raise TimeoutError("API did not become ready in 10 seconds")
            time.sleep(0.1)
            if not self.isProcessAlive(p):
                raise RuntimeError("Process died before API ready")

        process_create_time = time.monotonic() - start_wait
        
        # Give it a bit more time for the cartridge to actually start if needed
        # but --turbo helps.
        
        start_time = time.monotonic()
        result = None
        screenshot = None
        
        # Timeout based on test runtime
        timeout = (test.runtime / self.speed) + self.startup_time + 5.0
        
        while time.monotonic() - start_time < timeout:
            time.sleep(0.1)
            screenshot = self.getScreenshot()
            if screenshot is not None:
                result = test.checkResult(screenshot)
                if result is not None:
                    break
            if not self.isProcessAlive(p):
                break
        
        self.endProcess(p)
        if result is None:
            result = test.getDefaultResult()
            
        return TestResult(
            result=result, 
            screenshot=imageToBase64(screenshot) if screenshot else "", 
            startuptime=process_create_time, 
            runtime=time.monotonic()-start_time
        )

    def __repr__(self):
        return f"{self.name}:{self.port}"
