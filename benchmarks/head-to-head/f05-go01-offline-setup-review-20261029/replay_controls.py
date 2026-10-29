"""Replay copied synthetic controls with real subprocess/network entrypoints denied."""

from pathlib import Path
import runpy
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def denied(*args, **kwargs):
    raise AssertionError("Independent review forbids real subprocess/network actions")


subprocess.Popen = denied
socket.socket = denied
socket.create_connection = denied
sys.path.insert(0, str(HERE / "isolated-copy"))
runpy.run_path(str(HERE / "isolated-copy/controls.py"), run_name="__main__")
