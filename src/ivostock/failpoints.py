"""Puntos de interrupción exclusivos de la campaña externa de recuperación."""

import os
import time
from pathlib import Path


def checkpoint(name):
    if os.getenv("IVO_FAILPOINT") == name:
        if os.getenv("IVO_FAILPOINT_MODE") == "exit":
            os._exit(86)
        Path(os.environ["IVO_FAILPOINT_MARKER"]).touch()
        while True:
            time.sleep(0.05)
