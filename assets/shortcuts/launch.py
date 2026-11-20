#!/usr/bin/env python3
"""Launch configured applications using argument arrays, without a shell."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    apps = json.loads((root / "apps.json").read_text())
    if len(sys.argv) != 2 or sys.argv[1] not in apps:
        raise SystemExit("Unknown shortcut target")
    name = sys.argv[1]
    args = apps[name]
    if name == "shortcuts":
        args = ["kdialog", "--title", "Keyboard shortcuts", "--textbox",
                str(root / "CHEATSHEET.txt"), "1000", "700"]
    elif name == "screenshot":
        pictures = Path.home() / "Pictures"
        if shutil.which("xdg-user-dir"):
            result = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True,
                                    text=True, timeout=5, check=True)
            if result.stdout.strip():
                pictures = Path(result.stdout.strip())
        folder = pictures / "Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        args = ["flameshot", "gui", "--path", str(folder), "--clipboard", "--accept-on-select"]
    if not args or not shutil.which(args[0]):
        raise SystemExit("Install the application for this shortcut first")
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
