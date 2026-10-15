"""Main window — port of TForm1 (unit1.pas + unit1.lfm).

Tabs: Read / Write / Convert / Tools / Settings, plus the Greaseweazle
top bar, live command-line preview and the Go button.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..choices import (
    HFE_BITRATE_OPTIONS,
    HFE_ENCODING_OPTIONS,
    HFE_INTERFACE_OPTIONS,
    HFE_VERSION_OPTIONS,
    IMAGE_FORMATS,
    INTERNAL_FORMATS,
    SCP_OPTIONS,
)
from ..config_store import AppConfig
from ..gwcmd import (
    build_clean,
    build_convert,
    build_delays,
    build_erase,
    build_pin,
    build_read,
    build_rpm,
    build_seek,
    build_simple,
    build_update,
    build_write,
    dircheck,
    read_preview,
)
from ..runner import list_serial_ports, open_in_file_manager
from ..templates import (
    list_templates,
    load_template,
    read_diskdefs_names,
    read_diskformats,
    save_read_template,
    save_write_template,
    template_path,
)
from .dialogs import AboutDialog, ConsoleWindow, OptionsDialog, open_url

GW_INFO = 'Requires "Greaseweazle v1.23+" (and optional "diskdefs_.cfg")'

DRIVES = ["", "0", "1", "2", "3", "A", "B"]
HARDWARE = ["Greaseweazle", "Adafruit RP2040"]
REVS = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
RETRIES = ["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
FAKE_INDEX = ["", "300rpm", "8000000scp"]
ADJUST_SPEED = ["", "300", "360"]
PLL_READ = ["", "period=5:phase=60", "period=5:phase=60:lowpass=2.5us"]
PLL_CONV = ["", "period=5:phase=60"]
DENSEL = ["", "H", "L"]
CYLS_RW = ["", "0-76", "0-79", "0-80", "0-81", "0-81/2", "0-82", "0-83",
           "0-39", "0-40", "0-41", "0-7,9-12"]
CYLS_W = ["", "0-76", "0-79", "0-80", "0-81", "0-81/2", "0-82", "0-83",
          "0-39", "0-40", "0-41", "0-42", "0-7,9-12"]
HEADS_RW = ["", "0-1", "0", "1"]
STEPS_R = ["", "1", "2", "3", "4", "1/2"]
STEPS_W = ["", "1", "1/2", "2"]
FLIPPY = ["", "h0.off=+8", "h1.off=-8"]
ERASE_CYLS = ["", "0-81", "0-80", "0-79", "0-41", "0-40", "0-39"]
ERASE_HEADS = ["", "0,1", "0", "1"]
PRECOMP = ["", "type=mfm:40=125"]
INDEX_MARKS = ["", "--hard-sectors"]
PIN_LEVELS = ["", "High (5v)", "Low (0v)"]
CLEAN_PASSES = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

DELAY_DEFAULTS = {"select": "10", "step": "5000", "settle": "15",
                  "motor": "750", "watchdog": "10000", "pre_write": "100",
                  "post_write": "1000", "index_mask": "200"}


class PyFluffApp(tk.Tk):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.title(f"PyFluff v{__version__}")
        try:
            self.geometry(f"{cfg.get_int('Width', 935)}x"
                          f"{cfg.get_int('Height', 770)}")
        except Exception:  # noqa: BLE001
            pass

        self._building = True
        self._vars: dict[str, tk.Variable] = {}
        self._combos: dict[str, ttk.Combobox] = {}
        self._last_argv: list[str] = []

        self._build_menu()
        self._build_topbar()
        self._build_tabs()
        self._build_cmdbar()
        self._building = False

        self._after_build_init()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # variable helpers
    # ------------------------------------------------------------------
    def S(self, name: str, default: str = "") -> tk.StringVar:  # noqa: N802
        var = tk.StringVar(self, value=default)
        self._vars[name] = var
        var.trace_add("write", lambda *_a: self._changed())
        return var

    def B(self, name: str, default: bool = False) -> tk.BooleanVar:  # noqa: N802
        var = tk.BooleanVar(self, value=default)
        self._vars[name] = var
        var.trace_add("write", lambda *_a: self._changed())
        return var

    def _changed(self) -> None:
        if self._building:
            return
        self._refresh_filenames()
        self._update_go_caption()
        self._refresh_cmd()

    # ------------------------------------------------------------------
    # widget helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row(parent: tk.Misc) -> ttk.Frame:
        frm = ttk.Frame(parent)
        frm.pack(fill="x", pady=1)
        return frm

    def _combo(self, parent: tk.Misc, label: str, name: str,
               values: list[str], default: str = "", width: int = 22,
               labelwidth: int = 16) -> ttk.Combobox:
        ttk.Label(parent, text=label, width=labelwidth).pack(side="left")
        var = self.S(name, default)
        cb = ttk.Combobox(parent, textvariable=var, values=values,
                          width=width)
        cb.pack(side="left", padx=(0, 8))
        self._combos[name] = cb
        return cb

    def _check(self, parent: tk.Misc, label: str,
               name: str) -> ttk.Checkbutton:
        var = self.B(name)
        return ttk.Checkbutton(parent, text=label, variable=var)

    def _entry(self, parent: tk.Misc, label: str, name: str,
               default: str = "", width: int = 24,
               labelwidth: int = 16) -> ttk.Entry:
        ttk.Label(parent, text=label, width=labelwidth).pack(side="left")
        var = self.S(name, default)
        ent = ttk.Entry(parent, textvariable=var, width=width)
        ent.pack(side="left", padx=(0, 8))
        return ent

    def _spin(self, parent: tk.Misc, label: str, name: str, default: int,
              width: int = 6, frm: int = 0, to: int = 99999,
              labelwidth: int = 16) -> tk.Spinbox:
        ttk.Label(parent, text=label, width=labelwidth).pack(side="left")
        var = tk.StringVar(self, value=str(default))
        self._vars[name] = var
        var.trace_add("write", lambda *_a: self._changed())
        sp = tk.Spinbox(parent, textvariable=var, from_=frm, to=to,
                        width=width)
        sp.pack(side="left", padx=(0, 8))
        return sp

    # ------------------------------------------------------------------
    # menu
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.var_show_all = tk.BooleanVar(
            value=self.cfg.get_bool("ShowArg", True))
        self.var_show_all.trace_add("write", lambda *_a: self._apply_view())

        m_file = tk.Menu(menubar, tearoff=False)
        m_file.add_command(label="Close", command=self._on_close)
        menubar.add_cascade(label="File", menu=m_file)

        m_view = tk.Menu(menubar, tearoff=False)
        m_view.add_checkbutton(label="Show all arguments",
                               variable=self.var_show_all)
        menubar.add_cascade(label="View", menu=m_view)

        menubar.add_command(label="Options...", command=self._open_options)

        m_help = tk.Menu(menubar, tearoff=False)
        m_help.add_command(label="About...", command=self._open_about)
        m_help.add_separator()
        m_help.add_command(
            label="FluxMyFluffyFloppy on GitHub",
            command=lambda: open_url(
                "https://github.com/FrankieTheFluff/FluxMyFluffyFloppy"))
        m_help.add_command(
            label="Greaseweazle: download host tools",
            command=lambda: open_url(
                "https://github.com/keirf/greaseweazle/wiki/Download-Host-Tools"))
        m_help.add_command(
            label="Greaseweazle: getting started",
            command=lambda: open_url(
                "https://github.com/keirf/greaseweazle/wiki/Getting-Started"))
        m_help.add_command(
            label="Greaseweazle website",
            command=lambda: open_url("https://github.com/keirf/Greaseweazle"))
        menubar.add_cascade(label="Help", menu=m_help)
        self.configure(menu=menubar)

    # ------------------------------------------------------------------
    # top bar (Greaseweazle device selection)
    # ------------------------------------------------------------------
    def _build_topbar(self) -> None:
        bar = ttk.LabelFrame(self, text="Greaseweazle", padding=6)
        bar.pack(fill="x", padx=6, pady=(6, 0))

        r1 = self._row(bar)
        ttk.Label(r1, text="Location:", width=10).pack(side="left")
        self.var_gw = self.S("gw", self.cfg.get("Greaseweazle"))
        ttk.Entry(r1, textvariable=self.var_gw, width=60).pack(
            side="left", fill="x", expand=True)
        ttk.Button(r1, text="Browse...",
                   command=self._browse_gw).pack(side="left", padx=4)

        r2 = self._row(bar)
        self._combo(r2, "Device/COM:", "device", [], width=14, labelwidth=12)
        ttk.Button(r2, text="?",
                   command=self._refresh_devices, width=3).pack(side="left")
        self._combo(r2, "Drive:", "drive", DRIVES, width=5, labelwidth=7)
        self._combo(r2, "Hardware:", "hardware", HARDWARE, "Greaseweazle",
                     width=16, labelwidth=10)
        ttk.Button(r2, text="CMD/Dir",
                   command=self._cmd_dir).pack(side="left", padx=2)
        ttk.Button(r2, text="Reset",
                   command=lambda: self._oneshot("reset", "Reset")
                   ).pack(side="left", padx=2)
        ttk.Button(r2, text="Info",
                   command=lambda: self._oneshot("info", "Info")
                   ).pack(side="left", padx=2)
        ttk.Button(r2, text="Bandwidth",
                   command=lambda: self._oneshot("bandwidth", "Bandwidth")
                   ).pack(side="left", padx=2)

        r3 = self._row(bar)
        self._check(r3, "--time (show elapsed time)",
                    "opt_time").pack(side="left")
        self._check(r3, "--bt (backtrace on error)",
                    "opt_bt").pack(side="left", padx=(12, 0))

    # ------------------------------------------------------------------
    # tabs
    # ------------------------------------------------------------------
    def _build_tabs(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tab_read = ttk.Frame(self.nb)
        self.tab_write = ttk.Frame(self.nb)
        self.tab_conv = ttk.Frame(self.nb)
        self.tab_tools = ttk.Frame(self.nb)
        self.tab_settings = ttk.Frame(self.nb)
        self.nb.add(self.tab_read, text="Read")
        self.nb.add(self.tab_write, text="Write")
        self.nb.add(self.tab_conv, text="Convert")
        self.nb.add(self.tab_tools, text="Tools")
        self.nb.add(self.tab_settings, text="Settings")
        self.nb.bind("<<NotebookTabChanged>>",
                     lambda _e: self._on_tab_changed())
        self._build_read_tab()
        self._build_write_tab()
        self._build_conv_tab()
        self._build_tools_tab()
        self._build_settings_tab()

    # -- Read ------------------------------------------------------------
    def _build_read_tab(self) -> None:
        t = self.tab_read
        tpl = ttk.LabelFrame(t, text="Template:", padding=6)
        tpl.pack(fill="x", padx=4, pady=4)
        r = self._row(tpl)
        self._combo(r, "Name:", "r_tpl", [], width=28, labelwidth=6)
        ttk.Button(r, text="New", command=self._read_new).pack(side="left",
                                                               padx=2)
        ttk.Button(r, text="Save",
                   command=self._read_save).pack(side="left", padx=2)
        ttk.Button(r, text="Delete",
                   command=self._read_delete).pack(side="left", padx=2)
        r2 = self._row(tpl)
        self._entry(r2, "Description:", "r_desc", width=60, labelwidth=12)

        self.gb_read_arg = ttk.LabelFrame(t, text="Arguments (All):",
                                          padding=6)
        self.gb_read_arg.pack(fill="x", padx=4, pady=4)
        a = self._row(self.gb_read_arg)
        self._combo(a, "Format spec. src:", "r_fmt_src", ["Internal"],
                     "Internal", width=18)
        self._combo(a, "Format spec.:", "r_fmt", INTERNAL_FORMATS, width=26,
                     labelwidth=12)
        self.pn_read_all = ttk.Frame(self.gb_read_arg)
        self.pn_read_all.pack(fill="x")
        a2 = self._row(self.pn_read_all)
        self._combo(a2, "Revs:", "r_revs", REVS, width=6)
        self._check(a2, "Raw", "r_raw").pack(side="left")
        self._combo(a2, "Fake-index:", "r_fake", FAKE_INDEX, width=12)
        self._check(a2, "Hard-sectors", "r_hard").pack(side="left")
        a3 = self._row(self.pn_read_all)
        self._combo(a3, "Adjust-speed:", "r_speed", ADJUST_SPEED, width=8,
                     labelwidth=13)
        self._combo(a3, "Retries:", "r_retries", RETRIES, width=6,
                     labelwidth=8)
        self._combo(a3, "Seek-retries:", "r_seek", RETRIES, width=6,
                     labelwidth=12)
        self._combo(a3, "PLL:", "r_pll", PLL_READ, width=28, labelwidth=5)
        self._combo(a3, "Densel:", "r_dd", DENSEL, width=5, labelwidth=7)
        a4 = self._row(self.pn_read_all)
        self._combo(a4, "Cylinders:", "r_cyls", CYLS_RW, width=12)
        self._combo(a4, "Heads:", "r_heads", HEADS_RW, width=8, labelwidth=7)
        self._combo(a4, "Steps:", "r_steps", STEPS_R, width=6, labelwidth=7)
        self._check(a4, "HSwap (side 1 as side 0)",
                    "r_hswap").pack(side="left")
        self._combo(a4, "Flippy:", "r_flippy", FLIPPY, width=12,
                     labelwidth=7)
        self._check(a4, "Reverse", "r_reverse").pack(side="left")

        dst = ttk.LabelFrame(t, text="Destination:", padding=6)
        dst.pack(fill="x", padx=4, pady=4)
        d = self._row(dst)
        ttk.Label(d, text="Directory:", width=12).pack(side="left")
        self.var_r_destdir = self.S(
            "r_destdir", self.cfg.get("LastFolder_Read_Dest"))
        ttk.Entry(d, textvariable=self.var_r_destdir,
                  width=52).pack(side="left", fill="x", expand=True)
        ttk.Button(d, text="Browse...",
                   command=lambda: self._browse_dir("r_destdir")
                   ).pack(side="left", padx=2)
        ttk.Button(d, text="Explorer",
                   command=lambda: open_in_file_manager(
                       self.var_r_destdir.get())).pack(side="left", padx=2)
        d2 = self._row(dst)
        self._entry(d2, "Filename:", "r_filename", width=30, labelwidth=12)
        ttk.Button(d2, text="Clear",
                   command=lambda: self._vars["r_filename"].set("")
                   ).pack(side="left", padx=2)
        d3 = self._row(dst)
        ttk.Label(d3, text="Disk-Nr.:", width=12).pack(side="left")
        self._spin(d3, "", "r_disk1", 0, width=5, labelwidth=1)
        self._entry(d3, "", "r_of", "_of_", width=6, labelwidth=1)
        self._spin(d3, "", "r_disk2", 0, width=5, labelwidth=1)
        self._spin(d3, "Digits:", "r_digits", 1, width=4, frm=1, to=5,
                   labelwidth=7)
        self._check(d3, "Incremental", "r_incr").pack(side="left")
        self._check(d3, "Do not overwrite (-n)",
                    "r_noover").pack(side="left", padx=(8, 0))
        d4 = self._row(dst)
        self._combo(d4, "Format:", "r_format", IMAGE_FORMATS, width=26,
                     labelwidth=12)
        self._combo(d4, "Option:", "r_opt", [""], width=26, labelwidth=8)
        d5 = self._row(dst)
        self._combo(d5, "Interface:", "r_hfe_int", HFE_INTERFACE_OPTIONS,
                     width=26, labelwidth=12)
        self._combo(d5, "Version:", "r_hfe_ver", HFE_VERSION_OPTIONS,
                     width=14, labelwidth=8)
        self._combo(d5, "Encoding:", "r_hfe_enc", HFE_ENCODING_OPTIONS,
                     width=22, labelwidth=9)
        d6 = self._row(dst)
        ttk.Label(d6, text="Preview:", width=12).pack(side="left")
        self.var_r_preview = self.S("r_preview")
        ttk.Entry(d6, textvariable=self.var_r_preview, width=60,
                  state="readonly").pack(side="left", fill="x", expand=True)
        log = self._row(dst)
        self._check(log, "Log parameter", "r_log_param").pack(side="left")
        self._check(log, "Log output (no live monitoring)",
                    "r_log_out").pack(side="left", padx=(8, 0))
        self._check(log, "Log parameter and output in one file",
                    "r_log_both").pack(side="left", padx=(8, 0))

    # -- Write -----------------------------------------------------------
    def _build_write_tab(self) -> None:
        t = self.tab_write
        tpl = ttk.LabelFrame(t, text="Template:", padding=6)
        tpl.pack(fill="x", padx=4, pady=4)
        r = self._row(tpl)
        self._combo(r, "Name:", "w_tpl", [], width=28, labelwidth=6)
        ttk.Button(r, text="New", command=self._write_new).pack(side="left",
                                                                padx=2)
        ttk.Button(r, text="Save",
                   command=self._write_save).pack(side="left", padx=2)
        ttk.Button(r, text="Delete",
                   command=self._write_delete).pack(side="left", padx=2)
        r2 = self._row(tpl)
        self._entry(r2, "Description:", "w_desc", width=60, labelwidth=12)

        self.gb_write_arg = ttk.LabelFrame(t, text="Arguments (All):",
                                           padding=6)
        self.gb_write_arg.pack(fill="x", padx=4, pady=4)
        a = self._row(self.gb_write_arg)
        self._combo(a, "Format spec. src:", "w_fmt_src", ["Internal"],
                     "Internal", width=18)
        self._combo(a, "Format spec.:", "w_fmt", INTERNAL_FORMATS, width=26,
                     labelwidth=12)
        self.pn_write_all = ttk.Frame(self.gb_write_arg)
        self.pn_write_all.pack(fill="x")
        a2 = self._row(self.pn_write_all)
        self._check(a2, "Pre-erase", "w_preerase").pack(side="left")
        self._check(a2, "Erase empty", "w_eraseempty").pack(side="left",
                                                            padx=(8, 0))
        self._combo(a2, "Fake-index:", "w_fake", FAKE_INDEX, width=12)
        self._check(a2, "Hard-sectors", "w_hard").pack(side="left")
        self._check(a2, "No verify", "w_noverify").pack(side="left",
                                                        padx=(8, 0))
        a3 = self._row(self.pn_write_all)
        self._combo(a3, "Retries:", "w_retries", RETRIES, width=6)
        self._combo(a3, "Precomp:", "w_precomp", PRECOMP, width=18,
                     labelwidth=9)
        self._combo(a3, "Densel:", "w_dd", DENSEL, width=5, labelwidth=7)
        self._check(a3, "TP43 Pin 2 (--gen-tg43)",
                    "w_tg43").pack(side="left", padx=(8, 0))
        a4 = self._row(self.pn_write_all)
        self._combo(a4, "Cylinders:", "w_cyls", CYLS_W, width=12)
        self._combo(a4, "Heads:", "w_heads", HEADS_RW, width=8, labelwidth=7)
        self._combo(a4, "Steps:", "w_steps", STEPS_W, width=6, labelwidth=7)
        self._check(a4, "HSwap (side 1 as side 0)",
                    "w_hswap").pack(side="left")
        self._combo(a4, "Flippy:", "w_flippy", FLIPPY, width=12,
                     labelwidth=7)
        self._check(a4, "Reverse", "w_reverse").pack(side="left")

        src = ttk.LabelFrame(t, text="Source file:", padding=6)
        src.pack(fill="x", padx=4, pady=4)
        s = self._row(src)
        self.var_w_source = self.S(
            "w_source", self.cfg.get("LastFolder_Write_Source"))
        ttk.Entry(s, textvariable=self.var_w_source, width=70).pack(
            side="left", fill="x", expand=True)
        ttk.Button(s, text="Browse...",
                   command=self._browse_w_source).pack(side="left", padx=4)

    # -- Convert ---------------------------------------------------------
    def _build_conv_tab(self) -> None:
        t = self.tab_conv
        src = ttk.LabelFrame(t, text="Source file:", padding=6)
        src.pack(fill="x", padx=4, pady=4)
        s = self._row(src)
        ttk.Label(s, text="Source file:", width=12).pack(side="left")
        self.var_c_source = self.S(
            "c_source", self.cfg.get("LastFolder_Convert_Source"))
        ttk.Entry(s, textvariable=self.var_c_source, width=60).pack(
            side="left", fill="x", expand=True)
        ttk.Button(s, text="Browse...",
                   command=self._browse_c_source).pack(side="left", padx=4)
        s2 = self._row(src)
        self._check(s2, "Use source directory as destination",
                    "c_src_dir").pack(side="left")
        self._check(s2, "Use source filename as destination",
                    "c_src_file").pack(side="left", padx=(12, 0))

        self.gb_conv_arg = ttk.LabelFrame(t, text="Arguments (All):",
                                          padding=6)
        self.gb_conv_arg.pack(fill="x", padx=4, pady=4)
        self.pn_conv_all = ttk.Frame(self.gb_conv_arg)
        self.pn_conv_all.pack(fill="x")
        a = self._row(self.pn_conv_all)
        self._combo(a, "Adjust-speed:", "c_speed", ADJUST_SPEED, width=8)
        self._combo(a, "PLL:", "c_pll", PLL_CONV, width=24, labelwidth=5)
        self._combo(a, "Index marks:", "c_index", INDEX_MARKS, width=16,
                     labelwidth=12)
        a2 = self._row(self.pn_conv_all)
        ttk.Label(a2, text="Trackset (--tracks):").pack(side="left")
        a3 = self._row(self.pn_conv_all)
        self._combo(a3, "Cylinders:", "c_cyls", CYLS_W, width=12)
        self._combo(a3, "Heads:", "c_heads", HEADS_RW, width=8, labelwidth=7)
        self._combo(a3, "Steps:", "c_steps", STEPS_W, width=6, labelwidth=7)
        self._check(a3, "HSwap", "c_hswap").pack(side="left")
        self._combo(a3, "Flippy:", "c_flippy", FLIPPY, width=12,
                     labelwidth=7)
        a4 = self._row(self.pn_conv_all)
        ttk.Label(a4, text="Out-trackset (--out-tracks):").pack(side="left")
        a5 = self._row(self.pn_conv_all)
        self._combo(a5, "Cylinders:", "c_ocyls", CYLS_W, width=12)
        self._combo(a5, "Heads:", "c_oheads", HEADS_RW, width=8,
                     labelwidth=7)
        self._combo(a5, "Steps:", "c_osteps", STEPS_W, width=6, labelwidth=7)
        self._check(a5, "HSwap", "c_ohswap").pack(side="left")
        self._combo(a5, "Flippy:", "c_oflippy", FLIPPY, width=12,
                     labelwidth=7)
        self._check(a5, "Reverse", "c_reverse").pack(side="left")
        a6 = self._row(self.gb_conv_arg)
        self._combo(a6, "Diskdefs:", "c_diskdefs", ["Internal"], "Internal",
                     width=18)
        self._combo(a6, "Format:", "c_fmt", INTERNAL_FORMATS, width=26,
                     labelwidth=8)

        dst = ttk.LabelFrame(t, text="Destination:", padding=6)
        dst.pack(fill="x", padx=4, pady=4)
        d = self._row(dst)
        ttk.Label(d, text="Directory:", width=12).pack(side="left")
        self.var_c_destdir = self.S(
            "c_destdir", self.cfg.get("LastFolder_Convert_Dest"))
        ttk.Entry(d, textvariable=self.var_c_destdir,
                  width=52).pack(side="left", fill="x", expand=True)
        ttk.Button(d, text="Browse...",
                   command=lambda: self._browse_dir("c_destdir")
                   ).pack(side="left", padx=2)
        ttk.Button(d, text="Explorer",
                   command=lambda: open_in_file_manager(
                       self.var_c_destdir.get())).pack(side="left", padx=2)
        d2 = self._row(dst)
        self._entry(d2, "Filename:", "c_filename", width=30, labelwidth=12)
        ttk.Button(d2, text="Clear", command=self._conv_clear).pack(
            side="left", padx=2)
        d3 = self._row(dst)
        ttk.Label(d3, text="Disk-Nr.:", width=12).pack(side="left")
        self._spin(d3, "", "c_disk1", 0, width=5, labelwidth=1)
        self._entry(d3, "", "c_of", "_of_", width=6, labelwidth=1)
        self._spin(d3, "", "c_disk2", 0, width=5, labelwidth=1)
        self._spin(d3, "Digits:", "c_digits", 1, width=4, frm=1, to=5,
                   labelwidth=7)
        self._check(d3, "Incremental", "c_incr").pack(side="left")
        self._check(d3, "Do not overwrite (-n)",
                    "c_noover").pack(side="left", padx=(8, 0))
        d4 = self._row(dst)
        self._combo(d4, "File format:", "c_format", IMAGE_FORMATS, width=26,
                     labelwidth=12)
        self._combo(d4, "Option:", "c_opt", [""], width=26, labelwidth=8)
        d5 = self._row(dst)
        self._combo(d5, "Interface:", "c_hfe_int", HFE_INTERFACE_OPTIONS,
                     width=26, labelwidth=12)
        self._combo(d5, "Version:", "c_hfe_ver", HFE_VERSION_OPTIONS,
                     width=14, labelwidth=8)
        self._combo(d5, "Encoding:", "c_hfe_enc", HFE_ENCODING_OPTIONS,
                     width=22, labelwidth=9)
        d6 = self._row(dst)
        ttk.Label(d6, text="Preview:", width=12).pack(side="left")
        self.var_c_preview = self.S("c_preview")
        ttk.Entry(d6, textvariable=self.var_c_preview, width=60,
                  state="readonly").pack(side="left", fill="x", expand=True)

    # -- Tools -----------------------------------------------------------
    def _build_tools_tab(self) -> None:
        t = self.tab_tools
        self.var_tool = self.S("tool", "erase")
        modes = ttk.Frame(t)
        modes.pack(fill="x", padx=4, pady=4)
        for value, text in (("erase", "Erase"), ("seek", "Seek"),
                            ("clean", "Clean"), ("rpm", "RPM")):
            ttk.Radiobutton(modes, text=text, value=value,
                            variable=self.var_tool).pack(side="left",
                                                         padx=8)

        g = ttk.LabelFrame(t, text="Erase:", padding=6)
        g.pack(fill="x", padx=4, pady=4)
        r = self._row(g)
        self._combo(r, "Cylinders:", "e_cyls", ERASE_CYLS, width=10)
        self._combo(r, "Heads:", "e_heads", ERASE_HEADS, width=8,
                     labelwidth=7)
        self._combo(r, "Steps:", "e_steps", STEPS_W, width=6, labelwidth=7)
        self._check(r, "HSwap", "e_hswap").pack(side="left")
        self._combo(r, "Flippy:", "e_flippy", FLIPPY, width=12,
                     labelwidth=7)
        r2 = self._row(g)
        self._combo(r2, "Revs:", "e_revs", REVS, width=6)
        self._check(r2, "--hfreq", "e_hfreq").pack(side="left", padx=(8, 0))
        self._combo(r2, "Fake-index:", "e_fake", FAKE_INDEX, width=12,
                     labelwidth=11)

        g2 = ttk.LabelFrame(t, text="Seek:", padding=6)
        g2.pack(fill="x", padx=4, pady=4)
        r3 = self._row(g2)
        self._spin(r3, "Track:", "s_track", 0, width=6, to=84)
        self._check(r3, "--force", "s_force").pack(side="left", padx=(8, 0))
        self._check(r3, "--motor-on", "s_motor").pack(side="left",
                                                      padx=(8, 0))

        g3 = ttk.LabelFrame(t, text="Clean:", padding=6)
        g3.pack(fill="x", padx=4, pady=4)
        r4 = self._row(g3)
        self._spin(r4, "Cylinders (--cyls):", "cl_cyls", 0, width=6, to=84,
                   labelwidth=20)
        self._combo(r4, "Linger (--linger):", "cl_linger", ["100"], "100",
                     width=8, labelwidth=18)
        self._combo(r4, "Passes (--passes):", "cl_passes", CLEAN_PASSES,
                     "1", width=6, labelwidth=18)

        g4 = ttk.LabelFrame(t, text="RPM:", padding=6)
        g4.pack(fill="x", padx=4, pady=4)
        r5 = self._row(g4)
        self._spin(r5, "Iterations (--nr):", "rpm_nr", 1, width=6, frm=1,
                   to=1000, labelwidth=20)

    # -- Settings --------------------------------------------------------
    def _build_settings_tab(self) -> None:
        t = self.tab_settings
        self.var_setting = self.S("setting", "delays")
        modes = ttk.Frame(t)
        modes.pack(fill="x", padx=4, pady=4)
        for value, text in (("delays", "Delays"), ("pin", "PIN"),
                            ("firmware", "Firmware")):
            ttk.Radiobutton(modes, text=text, value=value,
                            variable=self.var_setting).pack(side="left",
                                                            padx=8)

        g = ttk.LabelFrame(t, text="Delays:", padding=6)
        g.pack(fill="x", padx=4, pady=4)
        r = self._row(g)
        for key, lbl in (("select", "--select"), ("step", "--step"),
                         ("settle", "--settle"), ("motor", "--motor")):
            self._entry(r, lbl + ":", "d_" + key,
                        DELAY_DEFAULTS[key], width=8, labelwidth=10)
        r2 = self._row(g)
        self._entry(r2, "--watchdog:", "d_watchdog",
                    DELAY_DEFAULTS["watchdog"], width=8, labelwidth=12)
        self._entry(r2, "--pre-write:", "d_pre_write",
                    DELAY_DEFAULTS["pre_write"], width=8, labelwidth=12)
        self._entry(r2, "--post-write:", "d_post_write",
                    DELAY_DEFAULTS["post_write"], width=8, labelwidth=13)
        self._entry(r2, "--index-mask:", "d_index_mask",
                    DELAY_DEFAULTS["index_mask"], width=8, labelwidth=13)
        r3 = self._row(g)
        ttk.Button(r3, text="Defaults",
                   command=self._delays_default).pack(side="left", padx=2)
        ttk.Button(r3, text="Info delays",
                   command=self._delays_info).pack(side="left", padx=2)

        g2 = ttk.LabelFrame(t, text="PIN:", padding=6)
        g2.pack(fill="x", padx=4, pady=4)
        r4 = self._row(g2)
        self.var_pin_mode = self.S("pin_mode", "get")
        ttk.Radiobutton(r4, text="Get PIN", value="get",
                        variable=self.var_pin_mode).pack(side="left")
        ttk.Radiobutton(r4, text="Set PIN", value="set",
                        variable=self.var_pin_mode).pack(side="left",
                                                         padx=(8, 0))
        self._spin(r4, "Number:", "pin_num", 2, width=5, frm=0, to=34,
                   labelwidth=9)
        self._combo(r4, "Level:", "pin_level", PIN_LEVELS, width=12,
                     labelwidth=7)

        g3 = ttk.LabelFrame(t, text="Firmware:", padding=6)
        g3.pack(fill="x", padx=4, pady=4)
        r5 = self._row(g3)
        self.var_fw_mode = self.S("fw_mode", "online")
        ttk.Radiobutton(r5, text="Online", value="online",
                        variable=self.var_fw_mode).pack(side="left")
        ttk.Radiobutton(r5, text="File (--force)", value="file",
                        variable=self.var_fw_mode).pack(side="left",
                                                        padx=(8, 0))
        ttk.Radiobutton(r5, text="Tag (--tag)", value="tag",
                        variable=self.var_fw_mode).pack(side="left",
                                                        padx=(8, 0))
        self._check(r5, "--bootloader", "fw_boot").pack(side="left",
                                                        padx=(12, 0))
        r6 = self._row(g3)
        ttk.Label(r6, text="File:", width=6).pack(side="left")
        self.var_fw_file = self.S("fw_file")
        ttk.Entry(r6, textvariable=self.var_fw_file,
                  width=50).pack(side="left")
        ttk.Button(r6, text="Browse...",
                   command=self._browse_fw).pack(side="left", padx=4)
        r7 = self._row(g3)
        self._entry(r7, "Tag:", "fw_tag", width=30, labelwidth=6)

    # ------------------------------------------------------------------
    # command preview + Go
    # ------------------------------------------------------------------
    def _build_cmdbar(self) -> None:
        bar = ttk.LabelFrame(self, text="Commandline:", padding=6)
        bar.pack(fill="x", padx=6, pady=(0, 6))
        self.txt_cmd = tk.Text(bar, height=3, wrap="word")
        self.txt_cmd.pack(fill="x")
        row = ttk.Frame(bar)
        row.pack(fill="x", pady=(4, 0))
        self.btn_go = ttk.Button(row, text="Read", command=self._go)
        self.btn_go.pack(side="right")

    # ------------------------------------------------------------------
    # init after build
    # ------------------------------------------------------------------
    def _after_build_init(self) -> None:
        self._refresh_devices()
        self._vars["drive"].set(self.cfg.get("SaveGWDrive")
                                if self.cfg.get_bool("SaveBoolGWDrive")
                                else "")
        if self.cfg.get_bool("SaveBoolGWDevCom"):
            self._vars["device"].set(self.cfg.get("SaveGWDevice"))
        self._vars["hardware"].set(self.cfg.get("GWHW", "Greaseweazle"))
        self._vars["opt_time"].set(self.cfg.get_bool("Time"))
        self._vars["opt_bt"].set(self.cfg.get_bool("Backtrace"))
        # format-option lists depend on chosen image format
        self._vars["r_format"].trace_add(
            "write", lambda *_a: self._sync_format_options("r"))
        self._vars["c_format"].trace_add(
            "write", lambda *_a: self._sync_format_options("c"))
        self._refresh_diskdefs()
        self._refresh_read_templates()
        self._refresh_write_templates()
        self._apply_view()
        self._on_tab_changed()
        self._refresh_filenames()
        self._refresh_cmd()

    # ------------------------------------------------------------------
    # view toggle (View > Show all arguments)
    # ------------------------------------------------------------------
    def _apply_view(self) -> None:
        show = self.var_show_all.get()
        self.cfg.set("ShowArg", show)
        title = ("Arguments (All):" if show
                 else 'Arguments (Only "format spec"):')
        self.gb_read_arg.configure(text=title)
        self.gb_write_arg.configure(text=title)
        self.gb_conv_arg.configure(text=title)
        for frame in (self.pn_read_all, self.pn_write_all, self.pn_conv_all):
            if show:
                frame.pack(fill="x")
            else:
                frame.pack_forget()
        self._refresh_cmd()

    # ------------------------------------------------------------------
    # device / diskdefs / templates
    # ------------------------------------------------------------------
    def _refresh_devices(self) -> None:
        ports = list_serial_ports()
        cb = self._combos["device"]
        current = self._vars["device"].get()
        cb.configure(values=ports)
        if current not in ports:
            self._vars["device"].set("")

    def _diskdefs_cfg(self, src_name: str) -> str:
        folder = self.cfg.get("Diskdefs")
        if not folder or src_name in ("", "Internal"):
            return ""
        return os.path.join(folder, src_name + ".cfg")

    def _refresh_diskdefs(self) -> None:
        names = read_diskdefs_names(self.cfg.get("Diskdefs"))
        for key in ("r_fmt_src", "w_fmt_src", "c_diskdefs"):
            cb = self._combos[key]
            cur = self._vars[key].get() or "Internal"
            cb.configure(values=names)
            self._vars[key].set(cur if cur in names else "Internal")
        self._sync_format_specs()

    def _sync_format_specs(self) -> None:
        pairs = (("r_fmt_src", "r_fmt"), ("w_fmt_src", "w_fmt"),
                 ("c_diskdefs", "c_fmt"))
        for src_key, fmt_key in pairs:
            src = self._vars[src_key].get()
            cb = self._combos[fmt_key]
            if src and src != "Internal":
                cb.configure(values=read_diskformats(
                    self._diskdefs_cfg(src)))
            else:
                cb.configure(values=INTERNAL_FORMATS)

    def _refresh_read_templates(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        names = list_templates(folder, ".inir")
        cb = self._combos["r_tpl"]
        cb.configure(values=names)
        if names:
            self._vars["r_tpl"].set(names[0])
            self._read_load()
        else:
            self._read_new(silent=True)

    def _refresh_write_templates(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        names = list_templates(folder, ".iniw")
        cb = self._combos["w_tpl"]
        cb.configure(values=names)
        if names:
            self._vars["w_tpl"].set(names[0])
            self._write_load()
        else:
            self._write_new(silent=True)

    # ------------------------------------------------------------------
    # read templates
    # ------------------------------------------------------------------
    def _read_values(self) -> dict:
        v = self._vars
        g = v.get
        return {
            "Name": g("r_tpl").get(), "Description": g("r_desc").get(),
            "Diskdefs": g("r_fmt_src").get(), "FormatSpec": g("r_fmt").get(),
            "Revs": g("r_revs").get(), "Raw": g("r_raw").get(),
            "Fake-Index": g("r_fake").get(),
            "Hard-Sectors": g("r_hard").get(),
            "Adjust-Speed": g("r_speed").get(), "Retries": g("r_retries").get(),
            "Seek-Retries": g("r_seek").get(), "PLL": g("r_pll").get(),
            "DD": g("r_dd").get(), "Cylinders": g("r_cyls").get(),
            "Heads": g("r_heads").get(), "Steps": g("r_steps").get(),
            "HSwap": g("r_hswap").get(), "Flippy": g("r_flippy").get(),
            "FlippyReverse": g("r_reverse").get(),
            "DestDir": g("r_destdir").get(),
            "DestFilename": g("r_filename").get(),
            "DestIncr": g("r_incr").get(), "DestNoOver": g("r_noover").get(),
            "DestDisk1": g("r_disk1").get(), "DestDOfD": g("r_of").get(),
            "DestDisk2": g("r_disk2").get(), "DestDigits": g("r_digits").get(),
            "DestForm": g("r_format").get(), "DestFormOpt": g("r_opt").get(),
            "DestFormInt": g("r_hfe_int").get(),
            "DestFormVer": g("r_hfe_ver").get(),
            "DestFormEnc": g("r_hfe_enc").get(),
            "Log_Param": g("r_log_param").get(),
            "Log_Output": g("r_log_out").get(),
            "Log_InOneFile": g("r_log_both").get(),
        }

    def _read_apply(self, d: dict) -> None:
        self._building = True
        try:
            v = self._vars
            str_keys = {"Diskdefs": "r_fmt_src", "FormatSpec": "r_fmt",
                        "Revs": "r_revs", "Fake-Index": "r_fake",
                        "Adjust-Speed": "r_speed", "Retries": "r_retries",
                        "Seek-Retries": "r_seek", "PLL": "r_pll",
                        "DD": "r_dd", "Cylinders": "r_cyls",
                        "Heads": "r_heads", "Steps": "r_steps",
                        "Flippy": "r_flippy", "DestDir": "r_destdir",
                        "DestFilename": "r_filename", "DestDOfD": "r_of",
                        "DestForm": "r_format", "DestFormOpt": "r_opt",
                        "DestFormInt": "r_hfe_int", "DestFormVer": "r_hfe_ver",
                        "DestFormEnc": "r_hfe_enc"}
            bool_keys = {"Raw": "r_raw", "Hard-Sectors": "r_hard",
                         "HSwap": "r_hswap", "FlippyReverse": "r_reverse",
                         "DestIncr": "r_incr", "DestNoOver": "r_noover",
                         "Log_Param": "r_log_param",
                         "Log_Output": "r_log_out",
                         "Log_InOneFile": "r_log_both"}
            int_keys = {"DestDisk1": "r_disk1", "DestDisk2": "r_disk2",
                        "DestDigits": "r_digits"}
            for k, var in str_keys.items():
                if k in d:
                    v[var].set(str(d[k]))
            for k, var in bool_keys.items():
                if k in d:
                    v[var].set(bool(d[k]))
            for k, var in int_keys.items():
                if k in d:
                    v[var].set(str(d[k]))
            if "Description" in d:
                v["r_desc"].set(str(d["Description"]))
            self._sync_format_options("r")
        finally:
            self._building = False
        self._refresh_filenames()
        self._refresh_cmd()

    def _read_load(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        name = self._vars["r_tpl"].get()
        if not name or not folder:
            return
        path = template_path(folder, name, ".inir")
        if os.path.exists(path):
            self._read_apply(load_template(path))

    def _read_new(self, silent: bool = False) -> None:  # noqa: ARG002
        self._building = True
        try:
            for key, val in (("r_tpl", ""), ("r_desc", ""),
                             ("r_fmt_src", "Internal"), ("r_fmt", ""),
                             ("r_revs", ""), ("r_fake", ""),
                             ("r_speed", ""), ("r_retries", ""),
                             ("r_seek", ""), ("r_pll", ""), ("r_dd", ""),
                             ("r_cyls", ""), ("r_heads", ""),
                             ("r_steps", ""), ("r_flippy", ""),
                             ("r_destdir", ""), ("r_filename", ""),
                             ("r_of", "_of_"), ("r_format", ""),
                             ("r_opt", ""), ("r_hfe_int", ""),
                             ("r_hfe_ver", ""), ("r_hfe_enc", "")):
                self._vars[key].set(val)
            for key, val in (("r_raw", False), ("r_hard", False),
                             ("r_hswap", False), ("r_reverse", False),
                             ("r_incr", False), ("r_noover", False),
                             ("r_log_param", False), ("r_log_out", False),
                             ("r_log_both", False)):
                self._vars[key].set(val)
            for key, val in (("r_disk1", "0"), ("r_disk2", "0"),
                             ("r_digits", "1")):
                self._vars[key].set(val)
            self._combos["r_fmt"].configure(values=INTERNAL_FORMATS)
        finally:
            self._building = False
        self._refresh_filenames()
        self._refresh_cmd()

    def _read_save(self) -> None:
        name = self._vars["r_tpl"].get().strip()
        if not name:
            messagebox.showwarning("PyFluff", "Please define a template name!",
                                   parent=self)
            return
        folder = self.cfg.get("FolderTemplates")
        if not folder:
            messagebox.showwarning(
                "PyFluff",
                "No templates folder defined (see Options). "
                "Template is not saved.", parent=self)
            return
        if not os.path.isdir(folder):
            messagebox.showwarning(
                "PyFluff",
                "In options defined templates folder does not exist.\n"
                "Please redefine! Template is not saved.", parent=self)
            return
        values = self._read_values()
        values["Name"] = name
        save_read_template(template_path(folder, name, ".inir"), values)
        self._refresh_read_templates()
        self._vars["r_tpl"].set(name)
        self._read_load()

    def _read_delete(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        name = self._vars["r_tpl"].get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(
                "PyFluff",
                "In options defined templates folder does not exist!\n"
                "Cannot delete the selected template!", parent=self)
            return
        path = template_path(folder, name, ".inir")
        if os.path.exists(path) and messagebox.askyesno(
                "PyFluff",
                "Do you really want to delete the selected template?",
                parent=self):
            os.remove(path)
            self._refresh_read_templates()

    # ------------------------------------------------------------------
    # write templates
    # ------------------------------------------------------------------
    def _write_values(self) -> dict:
        v = self._vars
        g = v.get
        return {
            "Name": g("w_tpl").get(), "Description": g("w_desc").get(),
            "Diskdefs": g("w_fmt_src").get(), "FormatSpec": g("w_fmt").get(),
            "EraseEmpty": g("w_eraseempty").get(),
            "Fake-Index": g("w_fake").get(),
            "Hard-Sectors": g("w_hard").get(),
            "NoVerify": g("w_noverify").get(), "Retries": g("w_retries").get(),
            "Precomp": g("w_precomp").get(),
            "Pre-Erase": g("w_preerase").get(), "DD": g("w_dd").get(),
            "TP43Pin2": g("w_tg43").get(), "Cylinders": g("w_cyls").get(),
            "Heads": g("w_heads").get(), "Steps": g("w_steps").get(),
            "HSwap": g("w_hswap").get(), "Flippy": g("w_flippy").get(),
            "FlippyReverse": g("w_reverse").get(),
        }

    def _write_apply(self, d: dict) -> None:
        self._building = True
        try:
            v = self._vars
            str_keys = {"Diskdefs": "w_fmt_src", "FormatSpec": "w_fmt",
                        "Fake-Index": "w_fake", "Retries": "w_retries",
                        "Precomp": "w_precomp", "DD": "w_dd",
                        "Cylinders": "w_cyls", "Heads": "w_heads",
                        "Steps": "w_steps", "Flippy": "w_flippy"}
            bool_keys = {"EraseEmpty": "w_eraseempty",
                         "Hard-Sectors": "w_hard", "NoVerify": "w_noverify",
                         "Pre-Erase": "w_preerase", "TP43Pin2": "w_tg43",
                         "HSwap": "w_hswap", "FlippyReverse": "w_reverse"}
            for k, var in str_keys.items():
                if k in d:
                    v[var].set(str(d[k]))
            for k, var in bool_keys.items():
                if k in d:
                    v[var].set(bool(d[k]))
            if "Description" in d:
                v["w_desc"].set(str(d["Description"]))
        finally:
            self._building = False
        self._refresh_cmd()

    def _write_load(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        name = self._vars["w_tpl"].get()
        if not name or not folder:
            return
        path = template_path(folder, name, ".iniw")
        if os.path.exists(path):
            self._write_apply(load_template(path))

    def _write_new(self, silent: bool = False) -> None:  # noqa: ARG002
        self._building = True
        try:
            for key in ("w_tpl", "w_desc", "w_fmt", "w_fake", "w_retries",
                        "w_precomp", "w_dd", "w_cyls", "w_heads",
                        "w_steps", "w_flippy"):
                self._vars[key].set("")
            self._vars["w_fmt_src"].set("Internal")
            for key in ("w_eraseempty", "w_hard", "w_noverify",
                        "w_preerase", "w_tg43", "w_hswap", "w_reverse"):
                self._vars[key].set(False)
            self._combos["w_fmt"].configure(values=INTERNAL_FORMATS)
        finally:
            self._building = False
        self._refresh_cmd()

    def _write_save(self) -> None:
        name = self._vars["w_tpl"].get().strip()
        if not name:
            messagebox.showwarning("PyFluff", "Please define a template name!",
                                   parent=self)
            return
        folder = self.cfg.get("FolderTemplates")
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(
                "PyFluff",
                "In options defined templates folder does not exist.\n"
                "Please redefine! Template is not saved.", parent=self)
            return
        values = self._write_values()
        values["Name"] = name
        save_write_template(template_path(folder, name, ".iniw"), values)
        self._refresh_write_templates()
        self._vars["w_tpl"].set(name)
        self._write_load()

    def _write_delete(self) -> None:
        folder = self.cfg.get("FolderTemplates")
        name = self._vars["w_tpl"].get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(
                "PyFluff",
                "In options defined templates folder does not exist!\n"
                "Cannot delete the selected template!", parent=self)
            return
        path = template_path(folder, name, ".iniw")
        if os.path.exists(path) and messagebox.askyesno(
                "PyFluff",
                "Do you really want to delete the following template?",
                parent=self):
            os.remove(path)
            self._refresh_write_templates()

    # ------------------------------------------------------------------
    # format options (SCP disktype / HFE bitrate+interface+encoding)
    # ------------------------------------------------------------------
    def _sync_format_options(self, prefix: str) -> None:
        fmt = self._vars[f"{prefix}_format"].get()
        opt_cb = self._combos[f"{prefix}_opt"]
        if fmt == "SCP (SuperCardPro)":
            opt_cb.configure(values=SCP_OPTIONS)
            if not self._vars[f"{prefix}_opt"].get():
                self._vars[f"{prefix}_opt"].set("")
        elif fmt == "HFE (HxC Floppy Emulator)":
            opt_cb.configure(values=HFE_BITRATE_OPTIONS)
        else:
            opt_cb.configure(values=[""])

    # ------------------------------------------------------------------
    # filename previews (port of Create_Filename)
    # ------------------------------------------------------------------
    @staticmethod
    def _to_int(var: tk.Variable) -> int:
        try:
            return int(float(str(var.get() or 0)))
        except (ValueError, TypeError):
            return 0

    def _refresh_filenames(self) -> None:
        v = self._vars
        if v["r_filename"].get():
            v["r_preview"].set(read_preview(
                v["r_filename"].get(), self._to_int(v["r_disk1"]),
                v["r_of"].get() or "_of_", self._to_int(v["r_disk2"]),
                max(1, self._to_int(v["r_digits"]) or 1),
                v["r_format"].get(), v["r_opt"].get(),
                v["r_hfe_ver"].get(), v["r_hfe_int"].get(),
                v["r_hfe_enc"].get()))
        else:
            v["r_preview"].set("")
        # convert: optional "use source ..." shortcuts
        if v["c_src_dir"].get() and v["c_source"].get():
            v["c_destdir"].set(os.path.dirname(
                os.path.abspath(v["c_source"].get())))
        if v["c_src_file"].get() and v["c_source"].get():
            base = os.path.splitext(
                os.path.basename(v["c_source"].get()))[0]
            v["c_filename"].set(base)
        if v["c_filename"].get():
            v["c_preview"].set(read_preview(
                v["c_filename"].get(), self._to_int(v["c_disk1"]),
                v["c_of"].get() or "_of_", self._to_int(v["c_disk2"]),
                max(1, self._to_int(v["c_digits"]) or 1),
                v["c_format"].get(), v["c_opt"].get(),
                v["c_hfe_ver"].get(), v["c_hfe_int"].get(),
                v["c_hfe_enc"].get()))
        else:
            v["c_preview"].set("")

    # ------------------------------------------------------------------
    # command generation (port of CMD_Generate)
    # ------------------------------------------------------------------
    def _common(self) -> dict:
        v = self._vars
        return {"gw": v["gw"].get(), "device": v["device"].get(),
                "hardware": v["hardware"].get() or "Greaseweazle",
                "drive": v["drive"].get(),
                "backtrace": v["opt_bt"].get(), "timed": v["opt_time"].get(),
                "show_all": self.var_show_all.get()}

    def _current_cmd(self) -> tuple[str, list[str]]:
        c = self._common()
        v = self._vars
        page = self.nb.index(self.nb.select())
        if page == 0:
            return build_read(
                c["gw"], c["device"], c["hardware"], c["drive"],
                v["r_fmt_src"].get() or "Internal",
                self._diskdefs_cfg(v["r_fmt_src"].get()),
                v["r_fmt"].get(), c["show_all"],
                v["r_cyls"].get(), v["r_heads"].get(), v["r_steps"].get(),
                v["r_hswap"].get(), v["r_flippy"].get(),
                v["r_reverse"].get(), v["r_revs"].get(), v["r_raw"].get(),
                v["r_fake"].get(), v["r_hard"].get(), v["r_speed"].get(),
                v["r_retries"].get(), v["r_seek"].get(),
                v["r_noover"].get(), v["r_pll"].get(), v["r_dd"].get(),
                v["r_destdir"].get(), v["r_preview"].get(),
                c["backtrace"], c["timed"])
        if page == 1:
            return build_write(
                c["gw"], c["device"], c["drive"],
                v["w_fmt_src"].get() or "Internal",
                self._diskdefs_cfg(v["w_fmt_src"].get()),
                v["w_fmt"].get(), c["show_all"],
                v["w_cyls"].get(), v["w_heads"].get(), v["w_steps"].get(),
                v["w_hswap"].get(), v["w_flippy"].get(),
                v["w_reverse"].get(), v["w_preerase"].get(),
                v["w_eraseempty"].get(), v["w_fake"].get(),
                v["w_hard"].get(), v["w_noverify"].get(),
                v["w_retries"].get(), v["w_precomp"].get(),
                v["w_dd"].get(), v["w_tg43"].get(), v["w_source"].get(),
                c["backtrace"], c["timed"])
        if page == 2:
            return build_convert(
                c["gw"], v["c_diskdefs"].get() or "Internal",
                self._diskdefs_cfg(v["c_diskdefs"].get()),
                v["c_fmt"].get(), c["show_all"],
                v["c_cyls"].get(), v["c_heads"].get(), v["c_steps"].get(),
                v["c_hswap"].get(), v["c_flippy"].get(),
                v["c_ocyls"].get(), v["c_oheads"].get(),
                v["c_osteps"].get(), v["c_ohswap"].get(),
                v["c_oflippy"].get(), v["c_reverse"].get(),
                v["c_speed"].get(), v["c_noover"].get(), v["c_pll"].get(),
                v["c_index"].get(), v["c_source"].get(),
                v["c_destdir"].get(), v["c_preview"].get(),
                c["backtrace"], c["timed"])
        if page == 3:
            tool = v["tool"].get()
            if tool == "erase":
                return build_erase(
                    c["gw"], c["device"], c["drive"], v["e_cyls"].get(),
                    v["e_heads"].get(), v["e_steps"].get(),
                    v["e_hswap"].get(), v["e_flippy"].get(),
                    v["e_revs"].get(), v["e_hfreq"].get(),
                    v["e_fake"].get(), c["backtrace"], c["timed"])
            if tool == "seek":
                return build_seek(
                    c["gw"], c["device"], c["drive"],
                    str(self._to_int(v["s_track"])), v["s_force"].get(),
                    v["s_motor"].get(), c["backtrace"], c["timed"])
            if tool == "clean":
                return build_clean(
                    c["gw"], c["device"], c["drive"],
                    str(self._to_int(v["cl_cyls"])),
                    v["cl_linger"].get() or "100",
                    v["cl_passes"].get() or "1", c["backtrace"], c["timed"])
            return build_rpm(
                c["gw"], c["device"], c["drive"],
                str(self._to_int(v["rpm_nr"]) or 1), c["backtrace"],
                c["timed"])
        # settings
        setting = v["setting"].get()
        if setting == "delays":
            return build_delays(
                c["gw"], c["device"], v["d_select"].get(),
                v["d_step"].get(), v["d_settle"].get(), v["d_motor"].get(),
                v["d_watchdog"].get(), v["d_pre_write"].get(),
                v["d_post_write"].get(), v["d_index_mask"].get(),
                c["backtrace"], c["timed"])
        if setting == "pin":
            get = v["pin_mode"].get() != "set"
            return build_pin(
                c["gw"], c["device"], c["drive"], get,
                str(self._to_int(v["pin_num"])), v["pin_level"].get(),
                c["backtrace"], c["timed"])
        return build_update(
            c["gw"], c["device"], v["fw_boot"].get(),
            v["fw_mode"].get(), v["fw_file"].get(), v["fw_tag"].get(),
            c["backtrace"], c["timed"])

    def _refresh_cmd(self) -> None:
        if self._building:
            return
        display, argv = self._current_cmd()
        if not self._vars["gw"].get():
            display = "No Greaseweazle application defined!"
            argv = []
        elif not os.path.exists(self._vars["gw"].get()):
            display = "Greaseweazle application not found!"
            argv = []
        self._last_argv = argv
        self.txt_cmd.configure(state="normal")
        self.txt_cmd.delete("1.0", "end")
        self.txt_cmd.insert("1.0", display)
        self.txt_cmd.configure(state="disabled")

    def _on_tab_changed(self) -> None:
        self._update_go_caption()
        self._refresh_filenames()
        self._refresh_cmd()

    def _update_go_caption(self) -> None:
        try:
            page = self.nb.index(self.nb.select())
        except Exception:  # noqa: BLE001
            return
        v = self._vars
        captions = {0: "Read", 1: "Write", 2: "Convert"}
        if page in captions:
            self.btn_go.configure(text=captions[page])
        elif page == 3:
            self.btn_go.configure(text={"erase": "Erase", "seek": "Seek",
                                        "clean": "Clean",
                                        "rpm": "RPM"}.get(v["tool"].get(),
                                                           "Erase"))
        else:
            setting = v["setting"].get()
            if setting == "delays":
                self.btn_go.configure(text="Set delays")
            elif setting == "pin":
                self.btn_go.configure(
                    text="Get PIN" if v["pin_mode"].get() != "set"
                    else "Set PIN")
            else:
                self.btn_go.configure(text="Update")

    # ------------------------------------------------------------------
    # browse helpers
    # ------------------------------------------------------------------
    def _browse_gw(self) -> None:
        initial = os.path.dirname(self.var_gw.get() or "") or "."
        fn = filedialog.askopenfilename(
            title="Select gw executable", initialdir=initial,
            filetypes=[("gw executable", "gw.exe" if os.name == "nt"
                        else "gw*"), ("All files", "*.*")])
        if fn:
            self.var_gw.set(fn)

    def _browse_dir(self, varname: str) -> None:
        d = filedialog.askdirectory(
            initialdir=self._vars[varname].get() or ".")
        if d:
            self._vars[varname].set(d)

    def _browse_w_source(self) -> None:
        fn = filedialog.askopenfilename(
            title="Select source image",
            initialdir=self.cfg.get("LastFolder_Write_Source") or ".")
        if fn:
            self.var_w_source.set(fn)

    def _browse_c_source(self) -> None:
        fn = filedialog.askopenfilename(
            title="Select source image",
            initialdir=self.cfg.get("LastFolder_Convert_Source") or ".")
        if fn:
            self.var_c_source.set(fn)

    def _browse_fw(self) -> None:
        fn = filedialog.askopenfilename(title="Select firmware file")
        if fn:
            self.var_fw_file.set(fn)

    # ------------------------------------------------------------------
    # top-bar one-shots + misc buttons
    # ------------------------------------------------------------------
    def _gw_or_warn(self) -> str | None:
        gw = self.var_gw.get()
        if not gw:
            messagebox.showwarning(
                "PyFluff",
                "Please define location of Greaseweazle (gw)!",
                parent=self)
            return None
        if not os.path.exists(gw):
            messagebox.showwarning("PyFluff", "Greaseweazle (gw) not found!",
                                   parent=self)
            return None
        return gw

    def _oneshot(self, verb: str, title: str) -> None:
        gw = self._gw_or_warn()
        if not gw:
            return
        _display, argv = build_simple(
            gw, self._vars["device"].get(), verb,
            self._vars["opt_bt"].get(), self._vars["opt_time"].get())
        ConsoleWindow(self, f"Greaseweazle - {title}", argv)

    def _cmd_dir(self) -> None:
        gw = self.var_gw.get()
        open_in_file_manager(os.path.dirname(gw) if gw else ".")

    def _conv_clear(self) -> None:
        self._building = True
        try:
            for key, val in (("c_filename", ""), ("c_of", "_of_"),
                             ("c_format", ""), ("c_opt", ""),
                             ("c_hfe_ver", ""), ("c_hfe_int", ""),
                             ("c_hfe_enc", ""), ("c_fmt", "")):
                self._vars[key].set(val)
            for key, val in (("c_disk1", "0"), ("c_disk2", "0"),
                             ("c_digits", "1"), ("c_src_dir", False),
                             ("c_src_file", False), ("c_incr", False),
                             ("c_noover", False)):
                self._vars[key].set(val)
        finally:
            self._building = False
        self._refresh_filenames()
        self._refresh_cmd()

    def _delays_default(self) -> None:
        for key, val in (("d_select", "10"), ("d_step", "5000"),
                         ("d_settle", "15"), ("d_motor", "750"),
                         ("d_watchdog", "10000"), ("d_pre_write", "100"),
                         ("d_post_write", "1000"),
                         ("d_index_mask", "200")):
            self._vars[key].set(val)

    def _delays_info(self) -> None:
        gw = self._gw_or_warn()
        if not gw:
            return
        _display, argv = build_simple(gw, self._vars["device"].get(),
                                      "delays")
        ConsoleWindow(self, "Greaseweazle - Info Delays", argv)

    # ------------------------------------------------------------------
    # Go (port of btGoClick validation + launch)
    # ------------------------------------------------------------------
    def _go(self) -> None:
        gw = self._gw_or_warn()
        if not gw:
            return
        page = self.nb.index(self.nb.select())
        v = self._vars
        if page == 0 and not self._validate_read():
            return
        if page == 1 and not self._validate_write():
            return
        if page == 2 and not self._validate_convert():
            return
        display, argv = self._current_cmd()
        if not argv:
            return
        if page == 0:
            self._run_read(display, argv)
        elif page == 1:
            ConsoleWindow(self, "Greaseweazle - Write", argv, mode="W")
        elif page == 2:
            ConsoleWindow(self, "Greaseweazle - Convert", argv)
        else:
            ConsoleWindow(self, f"Greaseweazle - {self.btn_go.cget('text')}",
                          argv)

    def _validate_read(self) -> bool:
        v = self._vars
        if not v["r_destdir"].get():
            messagebox.showwarning("PyFluff",
                                   "Destination directory not defined!",
                                   parent=self)
            return False
        dest = dircheck(v["r_destdir"].get())
        if not os.path.isdir(dest):
            from .dialogs import ask_create_dir
            if ask_create_dir(self, dest):
                os.makedirs(dest, exist_ok=True)
            else:
                return False
        if not v["r_filename"].get():
            messagebox.showwarning("PyFluff",
                                   "Destination filename is not defined!",
                                   parent=self)
            return False
        if not v["r_format"].get():
            messagebox.showwarning("PyFluff",
                                   "Destination format setting is missing!",
                                   parent=self)
            return False
        if v["r_format"].get() in ("IMA (Disk Image)", "IMG (Disk Image)") \
                and not v["r_fmt"].get():
            messagebox.showwarning(
                "PyFluff",
                "Sector image requires a disk format to be specified!",
                parent=self)
            return False
        if v["r_format"].get() == "HFE (HxC Floppy Emulator)" \
                and not v["r_opt"].get():
            messagebox.showwarning(
                "PyFluff", "HFE: Requires bitrate to be specified "
                           "(eg. filename.hfe::bitrate=500)", parent=self)
            return False
        target = os.path.join(dest, v["r_preview"].get())
        if v["r_preview"].get() and os.path.exists(target):
            if not messagebox.askyesno(
                    "PyFluff",
                    "Destination file is already existing! Overwrite?",
                    parent=self):
                return False
        return True

    def _validate_write(self) -> bool:
        src = self.var_w_source.get()
        if not src:
            messagebox.showwarning("PyFluff", "No source file selected!",
                                   parent=self)
            return False
        if not os.path.exists(src):
            messagebox.showwarning("PyFluff", "Source file not found!",
                                   parent=self)
            return False
        return True

    def _validate_convert(self) -> bool:
        v = self._vars
        src = v["c_source"].get()
        if not src:
            messagebox.showwarning("PyFluff", "No source file selected!",
                                   parent=self)
            return False
        if not os.path.exists(src):
            messagebox.showwarning("PyFluff", "Source file not found!",
                                   parent=self)
            return False
        dest = dircheck(v["c_destdir"].get())
        if not os.path.isdir(dest):
            from .dialogs import ask_create_dir
            if ask_create_dir(self, dest):
                os.makedirs(dest, exist_ok=True)
            else:
                return False
        if not v["c_format"].get():
            messagebox.showwarning(
                "PyFluff", "Destination fileformat settings incomplete!",
                parent=self)
            return False
        if not v["c_preview"].get():
            messagebox.showwarning(
                "PyFluff", "Destination filename settings incomplete!",
                parent=self)
            return False
        return True

    def _run_read(self, display: str, argv: list[str]) -> None:  # noqa: ARG002
        v = self._vars
        dest = dircheck(v["r_destdir"].get())
        base = os.path.splitext(v["r_preview"].get())[0]
        log_path = None
        append = False
        if v["r_log_param"].get():
            param_path = os.path.join(dest, base + ".txt")
            with open(param_path, "w", encoding="utf-8") as fh:
                fh.write(f"Filename: {v['r_preview'].get()}\n")
                fh.write(f"Format Source: {v['r_fmt_src'].get()}\n")
                fh.write(f"Format Selected: {v['r_fmt'].get()}\n")
                fh.write(f"Revs: {v['r_revs'].get()}\n")
                fh.write(f"Raw: {'Yes' if v['r_raw'].get() else 'No'}\n")
                fh.write(f"Fake-Index: {v['r_fake'].get()}\n")
                fh.write(f"Adjust-Speed: {v['r_speed'].get()}\n")
                fh.write(f"Retries: {v['r_retries'].get()}\n")
                fh.write(f"Seek-Retries: {v['r_seek'].get()}\n")
                fh.write(f"Cylinders: {v['r_cyls'].get()}\n")
                fh.write(f"Heads: {v['r_heads'].get()}\n")
                fh.write(f"Steps: {v['r_steps'].get()}\n")
                fh.write(f"HSwap: "
                         f"{'Yes' if v['r_hswap'].get() else 'No'}\n")
                fh.write(f"Flippy: {v['r_flippy'].get()}\n")
                fh.write(f"PLL: {v['r_pll'].get()}\n\n")
        if v["r_log_out"].get():
            if v["r_log_both"].get():
                log_path = os.path.join(dest, base + ".txt")
                append = True
            else:
                log_path = os.path.join(dest, base + "_output.txt")
        ConsoleWindow(self, "Greaseweazle - Read", argv, mode="R",
                      log_path=log_path, append_log=append)
        if v["r_incr"].get():
            try:
                d1 = self._to_int(v["r_disk1"])
                d2 = self._to_int(v["r_disk2"])
                if d1 < d2:
                    v["r_disk1"].set(str(d1 + 1))
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # options / about / close
    # ------------------------------------------------------------------
    def _open_options(self) -> None:
        OptionsDialog(self, self.cfg, self._options_applied)

    def _options_applied(self) -> None:
        self._refresh_diskdefs()
        self._refresh_read_templates()
        self._refresh_write_templates()
        self._refresh_filenames()
        self._refresh_cmd()

    def _open_about(self) -> None:
        AboutDialog(self, GW_INFO)

    def _on_close(self) -> None:
        try:
            cfg = self.cfg
            cfg.set("Width", self.winfo_width())
            cfg.set("Height", self.winfo_height())
            cfg.set("ShowArg", self.var_show_all.get())
            cfg.set("Greaseweazle", self.var_gw.get())
            cfg.set("GWHW", self._vars["hardware"].get())
            cfg.set("Time", self._vars["opt_time"].get())
            cfg.set("Backtrace", self._vars["opt_bt"].get())
            cfg.set("LastFolder_Read_Dest", self.var_r_destdir.get())
            cfg.set("LastFolder_Write_Source",
                    os.path.dirname(self.var_w_source.get())
                    if os.path.isfile(self.var_w_source.get())
                    else self.var_w_source.get())
            cfg.set("LastFolder_Convert_Source",
                    os.path.dirname(self.var_c_source.get())
                    if os.path.isfile(self.var_c_source.get())
                    else self.var_c_source.get())
            cfg.set("LastFolder_Convert_Dest", self.var_c_destdir.get())
            if cfg.get_bool("SaveBoolGWDevCom"):
                cfg.set("SaveGWDevice", self._vars["device"].get())
            if cfg.get_bool("SaveBoolGWDrive"):
                cfg.set("SaveGWDrive", self._vars["drive"].get())
            cfg.save()
        finally:
            self.destroy()


def main() -> None:
    """Entry point: python run.py."""
    import sys
    base = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    ini_default = os.path.join(os.path.dirname(base), "pyfluff.ini")
    ini_path = sys.argv[1] if len(sys.argv) > 1 else ini_default
    from ..config_store import AppConfig as Cfg

    cfg = Cfg(ini_path)
    if not cfg.get("FolderTemplates"):
        home = os.path.join(os.path.expanduser("~"), ".pyfluff")
        cfg.set("FolderTemplates", os.path.join(home, "Templates"))
        cfg.set("Diskdefs", os.path.join(home, "Diskdefs"))
        cfg.save()
    os.makedirs(cfg.get("FolderTemplates"), exist_ok=True)
    os.makedirs(cfg.get("Diskdefs"), exist_ok=True)
    app = PyFluffApp(cfg)
    app.mainloop()
