#!/usr/bin/env python3
"""PyFluff launcher: `python run.py [pyfluff.ini]`."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src"))

try:
    from pyfluff.gui.app import main  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name == "tkinter":
        sys.exit("PyFluff needs tkinter (standard library GUI).\n"
                 "Windows/macOS: included with python.org installers.\n"
                 "Debian/Ubuntu: sudo apt install python3-tk\n"
                 "Fedora: sudo dnf install python3-tkinter")
    raise

if __name__ == "__main__":
    main()
