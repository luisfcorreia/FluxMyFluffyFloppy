# PyFluff

A Python (tkinter, stdlib-only) replica of
[FluxMyFluffyFloppy](https://github.com/FrankieTheFluff/FluxMyFluffyFloppy)
— a Windows GUI for the
[Greaseweazle host tools](https://github.com/keirf/Greaseweazle) (`gw`).
The original Lazarus sources next to this folder are **not modified**;
this is a separate reimplementation in `./pyfluff`.

## Requirements

- Python 3.10+ with **tkinter** (ships with python.org Windows/macOS
  installers; on Linux: `apt install python3-tk` / `dnf install python3-tkinter`).
- No `pip` packages required for the app itself (`requirements.txt` is
  intentionally near-empty; `pyserial` is an optional nicety only).
- At runtime you need the Greaseweazle host tools (`gw.exe`/`gw`) and,
  optionally, a folder with `diskdefs_*.cfg` files — same as the original.

## Run

```bash
# Windows (uses bundled venv when present)
run.bat

# Any platform
python run.py                 # stores settings in ./pyfluff.ini
python run.py path\to.ini    # custom settings file

# With the bundled venv
.venv/bin/python run.py                       # POSIX
.venv\Scripts\python.exe run.py               # Windows
```

First start creates `~/.pyfluff/Templates` and `~/.pyfluff/Diskdefs`
(point the Options dialog at your real folders afterwards).

## Layout

```text
pyfluff/
  run.py / run.bat        launchers
  requirements.txt        stdlib-only declaration
  pyfluff.ini             created on first run (settings, git-ignored)
  .venv/                  bundled virtualenv (python -m venv, no packages)
  src/pyfluff/
    gwcmd.py              command-line builder (port of CMD_Generate),
                          filename builder (Create_Filename), T-track parser
    choices.py            image formats, internal format specs, SCP/HFE lists
    config_store.py       INI settings (same section/keys as original)
    templates.py          .inir/.iniw read/write templates + diskdefs scan
    runner.py             streaming gw subprocess + serial-port enumeration
    gui/app.py            main window: Read/Write/Convert/Tools/Settings
    gui/dialogs.py        Options, About, execution console w/ track grids
  tests/test_core.py      headless tests (no display needed): python -m unittest
```

## Coverage vs. the original

Read / Write / Convert / Tools (Erase, Seek, Clean, RPM) / Settings
(Delays, PIN get/set, Firmware update), `gw` path + Device/COM + Drive +
Hardware (Greaseweazle vs Adafruit RP2040 `--device` quirk) top bar,
`--time` / `--bt` flags, template New/Save/Delete (`.inir`/`.iniw` with
identical key names), diskdefs-folder format-spec loading, incremental
disk numbering with zero-padded `N_of_M` names and format-dependent
extensions (incl. SCP `::disktype=`, HFE `::bitrate/interface/...`, RAW
`00.0.raw`), log-parameter / log-output / combined logging, View-menu
"Show all arguments" toggle, Options/About dialogs, and the track-grid
console (`Txx.x` → side 0/1 grids, red `-` on "Giving up").

## Deliberate deviations

- Fixed the original's stray trailing `"` in the Bandwidth/Info/Reset/
  Delays-info one-shot commands (`... --device COM3"`).
- Write-template version stamp is `v4.00` (original saves stale `3.00`;
  the key is never validated on load).
- Process launch uses an argv list instead of `cmd /C <string>`, so paths
  with spaces work everywhere; the quoted string is still shown as the
  command-line preview.
- COM-port listing uses the Windows registry like the original, and
  `/dev/ttyUSB*|ACM*|S*` + `/dev/cu.*` globs on POSIX.
- Explorer/CMD-Dir buttons use the platform file manager
  (`os.startfile` / `open` / `xdg-open`).
