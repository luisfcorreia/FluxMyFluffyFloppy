"""Options / About / execution-console dialogs (ports of unit3/unit2/unit4)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..gwcmd import parse_track_line
from ..runner import GwProcess


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 - best effort, like OpenURL
        pass


class OptionsDialog(tk.Toplevel):
    """Port of TFrmOptions: INI-backed gw/device/drive/folder settings."""

    def __init__(self, master: tk.Misc, cfg, on_ok):
        super().__init__(master)
        self.title("Options")
        self.resizable(False, False)
        self._cfg = cfg
        self._on_ok = on_ok

        self.var_save_dev = tk.BooleanVar(
            value=cfg.get_bool("SaveBoolGWDevCom"))
        self.var_save_drive = tk.BooleanVar(
            value=cfg.get_bool("SaveBoolGWDrive"))
        self.var_codepage = tk.BooleanVar(
            value=cfg.get_bool("CodepageCMD", True))
        self.var_diskdefs = tk.StringVar(value=cfg.get("Diskdefs"))
        self.var_templates = tk.StringVar(value=cfg.get("FolderTemplates"))

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Checkbutton(frm, text="Save Greaseweazle device/COM on exit",
                        variable=self.var_save_dev).pack(anchor="w")
        ttk.Checkbutton(frm, text="Save drive selection on exit",
                        variable=self.var_save_drive).pack(anchor="w")
        ttk.Checkbutton(frm, text="Use default system codepage for gw output",
                        variable=self.var_codepage).pack(anchor="w")

        loc = ttk.LabelFrame(frm, text="Locations", padding=8)
        loc.pack(fill="x", pady=8)
        ttk.Label(loc, text="Diskdefs (folder):").grid(row=0, column=0,
                                                       sticky="w")
        ttk.Entry(loc, textvariable=self.var_diskdefs,
                  width=48).grid(row=1, column=0, sticky="ew")
        ttk.Button(loc, text="Browse...",
                   command=self._browse_diskdefs).grid(row=1, column=1,
                                                      padx=(6, 0))
        ttk.Label(loc, text="Templates (folder):").grid(row=2, column=0,
                                                        sticky="w",
                                                        pady=(6, 0))
        ttk.Entry(loc, textvariable=self.var_templates,
                  width=48).grid(row=3, column=0, sticky="ew")
        ttk.Button(loc, text="Browse...",
                   command=self._browse_templates).grid(row=3, column=1,
                                                       padx=(6, 0))
        loc.columnconfigure(0, weight=1)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right")
        ttk.Button(btns, text="Cancel",
                   command=self.destroy).pack(side="right", padx=(0, 6))

        self.transient(master)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _browse_diskdefs(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_diskdefs.get() or ".")
        if d:
            self.var_diskdefs.set(d)

    def _browse_templates(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_templates.get()
                                    or ".")
        if d:
            self.var_templates.set(d)

    def _ok(self) -> None:
        self._cfg.set("SaveBoolGWDevCom", self.var_save_dev.get())
        self._cfg.set("SaveBoolGWDrive", self.var_save_drive.get())
        self._cfg.set("CodepageCMD", self.var_codepage.get())
        self._cfg.set("Diskdefs", self.var_diskdefs.get())
        self._cfg.set("FolderTemplates", self.var_templates.get())
        self._cfg.save()
        self.destroy()
        self._on_ok()


class AboutDialog(tk.Toplevel):
    """Port of TFrmAbout: version, credits, links."""

    def __init__(self, master: tk.Misc, gw_info: str):
        super().__init__(master)
        self.title("About")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="PyFluff",
                  font=("TkDefaultFont", 14, "bold")).pack()
        ttk.Label(frm, text=f"v{__version__} — a Python GUI for "
                            "Greaseweazle host tools").pack()
        ttk.Label(frm, text=gw_info).pack(pady=(0, 4))
        ttk.Label(frm, text="A Python replica of FluxMyFluffyFloppy "
                            "(c) 2021-2026 FrankieTheFluff, GPL-2.0").pack()
        ttk.Label(frm, text="Greaseweazle host tools (c) Keir Fraser").pack()

        def link(parent, text, url):
            lbl = ttk.Label(parent, text=text, foreground="blue",
                            cursor="hand2")
            lbl.pack()
            lbl.bind("<Button-1>", lambda _e: open_url(url))

        link(frm, "https://github.com/FrankieTheFluff/FluxMyFluffyFloppy",
             "https://github.com/FrankieTheFluff/FluxMyFluffyFloppy")
        link(frm, "https://github.com/keirf/Greaseweazle",
             "https://github.com/keirf/Greaseweazle")
        link(frm, "GNU General Public License v2.0",
             "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html")
        link(frm, "fluxmyfluffyfloppy@mail.de",
             "mailto:fluxmyfluffyfloppy@mail.de"
             "?subject=FluxMyFluffyFloppy&body=")

        ttk.Button(frm, text="OK", command=self.destroy).pack(pady=(10, 0))
        self.transient(master)
        self.grab_set()
        self.focus_set()


class ConsoleWindow(tk.Toplevel):
    """Port of TfrmGW: live gw output + side0/side1 track grids.

    mode 'R' fills grids on Read, 'W' on Write; other captions show the
    log only (like the original, where StrGrid_Fill exits early).
    """

    ROWS = 9
    COLS = 10

    def __init__(self, master: tk.Misc, title: str, argv: list[str],
                 mode: str | None = None, log_path: str | None = None,
                 append_log: bool = False):
        super().__init__(master)
        self.title(title)
        self._mode = mode
        self._proc = GwProcess(argv, log_path=log_path,
                               append_log=append_log)
        self._done = False

        top = ttk.Frame(self, padding=8)
        top.pack(fill="both", expand=True)

        self.memo = tk.Text(top, width=100, height=24, wrap="none")
        yscroll = ttk.Scrollbar(top, orient="vertical",
                                command=self.memo.yview)
        self.memo.configure(yscrollcommand=yscroll.set)
        self.memo.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        self._grids_frame = ttk.Frame(top)
        self._grids_frame.grid(row=0, column=2, sticky="n", padx=(8, 0))
        self._cells: dict[tuple[int, int, int], tk.Label] = {}
        if mode in ("R", "W"):
            for side in (0, 1):
                ttk.Label(self._grids_frame,
                          text=f"Side {side}").grid(row=side * 11, column=0,
                                                    columnspan=11)
                for c in range(self.COLS + 1):
                    hdr = tk.Label(self._grids_frame, text=str(c - 1) if c
                                   else "", width=3,
                                   relief="groove" if c else "flat")
                    hdr.grid(row=side * 11 + 1, column=c)
                    if c:
                        for r in range(1, self.ROWS + 1):
                            lab = tk.Label(self._grids_frame, text="-",
                                           width=3, relief="groove")
                            lab.grid(row=side * 11 + 1 + r, column=c)
                            self._cells[(side, c - 1, r - 1)] = lab
        else:
            ttk.Label(self._grids_frame, text="(no track grid\nfor this "
                                              "command)").pack()

        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)

        ttk.Button(self, text="Close",
                   command=self.destroy).pack(pady=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._append(f"$ {' '.join(argv)}\n")
        self._proc.start()
        self.after(100, self._pump)

    # -- output ----------------------------------------------------------
    def _append(self, text: str) -> None:
        self.memo.insert("end", text + ("" if text.endswith("\n") else "\n"))
        self.memo.see("end")

    def _pump(self) -> None:
        if not self.winfo_exists():
            return
        for line in self._proc.poll():
            if line == "__DONE__":
                self._done = True
                self._append(f"\n[exit code "
                             f"{self._proc.returncode}]")
            else:
                self._append(line)
                self._fill_grid(line)
        if not self._done:
            self.after(100, self._pump)

    def _fill_grid(self, line: str) -> None:
        if self._mode not in ("R", "W"):
            return
        parsed = parse_track_line(line)
        if parsed is None:
            return
        track, side, giving_up = parsed
        mark = "-" if giving_up else self._mode
        col, row = track % 10, track // 10
        if row >= self.ROWS:
            return
        key = (side, col, row)
        if key in self._cells:
            color = "red" if giving_up else "green"
            self._cells[key].configure(text=mark, foreground=color)

    def destroy(self) -> None:  # noqa: D102
        try:
            self._proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        super().destroy()


def ask_create_dir(parent: tk.Misc, path: str) -> bool:
    return messagebox.askyesno(
        "PyFluff",
        f"Destination directory not found:\n{path}\n\nCreate directory?",
        parent=parent)
