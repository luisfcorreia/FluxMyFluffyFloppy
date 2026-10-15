"""gw.exe execution — streaming subprocess runner (replaces unit4 TConsoleProc).

Runs the argv list (no shell), merges stderr into stdout like the gw console
output, tees to an optional log file, and reports each line via callback.
Track progress lines (Txx.x) are parsed by the GUI for the side grids.
"""

from __future__ import annotations

import locale
import os
import queue
import subprocess
import threading
from collections.abc import Callable


class GwProcess:
    def __init__(self, argv: list[str],
                 on_line: Callable[[str], None] | None = None,
                 log_path: str | None = None,
                 append_log: bool = False,
                 encoding: str | None = None):
        self.argv = argv
        self.on_line = on_line
        self.log_path = log_path
        self.append_log = append_log
        self.encoding = encoding or locale.getpreferredencoding(False)
        self._proc: subprocess.Popen | None = None
        self._queue: queue.Queue[str | None] = queue.Queue()
        self.returncode: int | None = None

    # -- control ---------------------------------------------------------
    def start(self) -> None:
        log_fh = None
        if self.log_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_path)),
                        exist_ok=True)
            log_fh = open(self.log_path, "a" if self.append_log else "w",
                          encoding=self.encoding, errors="replace")

        def pump() -> None:
            try:
                self._proc = subprocess.Popen(
                    self.argv, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True,
                    encoding=self.encoding, errors="replace",
                    creationflags=(0x08000000 if os.name == "nt"
                                   else 0),  # CREATE_NO_WINDOW
                )
            except OSError as exc:
                self._queue.put(f"[pyfluff] failed to start: {exc}")
                self._queue.put(None)
                if log_fh:
                    log_fh.close()
                return
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                text = line.rstrip("\r\n")
                if log_fh:
                    log_fh.write(text + "\n")
                self._queue.put(text)
            self._proc.wait()
            self.returncode = self._proc.returncode
            if log_fh:
                log_fh.close()
            self._queue.put(None)

        threading.Thread(target=pump, daemon=True).start()

    def poll(self) -> list[str]:
        """Drain newly arrived lines (call from the Tk event loop)."""
        lines = []
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    lines.append("__DONE__")
                    break
                lines.append(item)
        except queue.Empty:
            pass
        return lines

    def terminate(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass


def list_serial_ports() -> list[str]:
    """COM/serial ports — Windows registry like the original, glob elsewhere."""
    if os.name == "nt":
        try:
            import winreg
            ports = []
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
                i = 0
                while True:
                    try:
                        _, value, _ = winreg.EnumValue(key, i)
                        ports.append(str(value))
                        i += 1
                    except OSError:
                        break
            return sorted(ports)
        except OSError:
            return []
    import glob
    found = []
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*",
                    "/dev/ttyAMA*", "/dev/cu.*"):
        found.extend(glob.glob(pattern))
    return sorted(found)


def open_in_file_manager(path: str) -> None:
    """Cross-platform equivalent of the Explorer / CMD-Dir buttons."""
    import subprocess as sp
    import sys
    target = path if os.path.isdir(path) else os.path.dirname(path) or "."
    try:
        if sys.platform.startswith("win"):
            os.startfile(target)  # noqa: S606
        elif sys.platform == "darwin":
            sp.Popen(["open", target])
        else:
            sp.Popen(["xdg-open", target])
    except OSError:
        pass
