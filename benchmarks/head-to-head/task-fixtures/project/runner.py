"""Harmless local task oracles for measurement controls, never upstream code."""

import json
import os
import sys
from pathlib import Path

mode = sys.argv[1]
complete = True
if mode == "setup":
    Path("ready").touch()
elif mode == "test":
    complete = Path("ready").exists()
elif mode == "parameterized":
    complete = sys.argv[2:] == ["unit"]
elif mode == "component":
    complete = Path.cwd().name == "widget" and os.environ.get("DEMO_CONTEXT") == "widget"
elif mode == "compile":
    complete = False
elif mode not in {"build", "unit"}:
    raise ValueError(mode)
print(json.dumps({"mode": mode, "completed": complete}))
# Compilation succeeds, but does not complete the test task.
sys.exit(0 if complete or mode == "compile" else 1)
