#!/usr/bin/env python3
"""Launcher that activates the dedicated timesfm venv before running code.

This lets you use TimesFM from anywhere in the workspace without manually
activating `timesfm/venv`.

Examples:
    python run_timesfm.py timesfm_wrapper.cli forecast sample.csv --horizon 12
    python run_timesfm.py timesfm_wrapper.api  # runs uvicorn (not recommended from here)
    python run_timesfm.py my_script.py
"""

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
VENV = WORKSPACE / "timesfm" / "venv"
BIN = VENV / "bin"
PYTHON = BIN / "python"

if not PYTHON.exists():
    print(f"TimesFM venv not found at {VENV}. Run the install step first.", file=sys.stderr)
    sys.exit(1)

# Prepend venv to PATH and set interpreter env vars
env = os.environ.copy()
env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")
env["VIRTUAL_ENV"] = str(VENV)

args = sys.argv[1:]
if not args:
    print("Usage: python run_timesfm.py <module_or_script> [args...]", file=sys.stderr)
    sys.exit(1)

target = args[0]

if target.endswith(".py"):
    cmd = [str(PYTHON), target, *args[1:]]
elif "." in target:
    # module invocation, e.g. timesfm_wrapper.cli
    cmd = [str(PYTHON), "-m", target, *args[1:]]
else:
    cmd = [str(PYTHON), target, *args[1:]]

sys.exit(subprocess.call(cmd, env=env))
