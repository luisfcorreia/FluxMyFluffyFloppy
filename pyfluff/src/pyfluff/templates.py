"""Read (.inir) / Write (.iniw) template files.

Key names mirror the original exactly (including 'Fake-Index',
'Seek-Retries', 'Pre-Erase', 'TP43Pin2', ...).  ConfigParser lowercases
keys by default, so optionxform is disabled to match TIniFile behaviour.
"""

from __future__ import annotations

import configparser
import os

READ_SECTION = "FluxMyFluffyFloppy-Read-Template"
WRITE_SECTION = "FluxMyFluffyFloppy-Write-Template"
SETTINGS = "Settings"

READ_VERSION = "v5.00"
WRITE_VERSION = "v4.00"  # original saves stale '3.00'; version key is unchecked

READ_FIELDS = [
    "Diskdefs", "FormatSpec", "Revs", "Fake-Index", "Adjust-Speed",
    "Retries", "Seek-Retries", "PLL", "DD", "Cylinders", "Heads",
    "Steps", "Flippy", "DestDir", "DestFilename", "DestDOfD",
    "DestForm", "DestFormOpt", "DestFormInt", "DestFormVer",
    "DestFormEnc",
]
READ_BOOL_FIELDS = [
    "Raw", "Hard-Sectors", "HSwap", "FlippyReverse", "DestIncr",
    "DestNoOver", "Log_Param", "Log_Output", "Log_InOneFile",
]
READ_INT_FIELDS = ["DestDisk1", "DestDisk2", "DestDigits"]

WRITE_FIELDS = [
    "Diskdefs", "FormatSpec", "Fake-Index", "Retries", "Precomp", "DD",
    "Cylinders", "Heads", "Steps", "Flippy",
]
WRITE_BOOL_FIELDS = [
    "EraseEmpty", "Hard-Sectors", "NoVerify", "Pre-Erase", "TP43Pin2",
    "HSwap", "FlippyReverse",
]


def _ini() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp.optionxform = str
    return cp


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def list_templates(folder: str, ext: str) -> list[str]:
    if not folder or not os.path.isdir(folder):
        return []
    names = []
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(ext.lower()):
            names.append(fn[: -len(ext)])
    return names


def template_path(folder: str, name: str, ext: str) -> str:
    return os.path.join(folder, name + ext)


def load_template(path: str) -> dict[str, object]:
    cp = _ini()
    cp.read(path, encoding="utf-8")
    data: dict[str, object] = {}
    for section in cp.sections():
        for k, v in cp[section].items():
            data[f"{section}\x00{k}"] = v
    # flattened convenience view: header + settings
    flat: dict[str, object] = {}
    for section in (READ_SECTION, WRITE_SECTION):
        if section in cp:
            for k in ("Version", "Name", "Description"):
                if k in cp[section]:
                    flat[k] = cp[section][k]
    if SETTINGS in cp:
        for k, v in cp[SETTINGS].items():
            flat[k] = v
    # coerce known bools/ints
    for k in READ_BOOL_FIELDS + WRITE_BOOL_FIELDS:
        if k in flat and isinstance(flat[k], str):
            flat[k] = _parse_bool(flat[k])
    for k in READ_INT_FIELDS:
        if k in flat:
            try:
                flat[k] = int(str(flat[k]))
            except ValueError:
                flat[k] = 0
    return flat


def save_read_template(path: str, values: dict[str, object]) -> None:
    cp = _ini()
    cp[READ_SECTION] = {
        "Version": READ_VERSION,
        "Name": str(values.get("Name", "")),
        "Description": str(values.get("Description", "")),
    }
    settings: dict[str, str] = {}
    for k in READ_FIELDS:
        settings[k] = str(values.get(k, ""))
    for k in READ_BOOL_FIELDS:
        v = values.get(k, False)
        settings[k] = "1" if v in (True, 1, "1", "True") else "0"
    for k in READ_INT_FIELDS:
        settings[k] = str(values.get(k, 0))
    cp[SETTINGS] = settings
    with open(path, "w", encoding="utf-8") as fh:
        cp.write(fh)


def save_write_template(path: str, values: dict[str, object]) -> None:
    cp = _ini()
    cp[WRITE_SECTION] = {
        "Version": WRITE_VERSION,
        "Name": str(values.get("Name", "")),
        "Description": str(values.get("Description", "")),
    }
    settings: dict[str, str] = {}
    for k in WRITE_FIELDS:
        settings[k] = str(values.get(k, ""))
    for k in WRITE_BOOL_FIELDS:
        v = values.get(k, False)
        settings[k] = "1" if v in (True, 1, "True") else "0"
    cp[SETTINGS] = settings
    with open(path, "w", encoding="utf-8") as fh:
        cp.write(fh)


def read_diskdefs_names(folder: str) -> list[str]:
    """Names for the format-source dropdowns: 'Internal' + *.cfg stems
    (excluding plain diskdefs), mirroring Refresh_Diskdefs_DropDown."""
    names = ["Internal"]
    if folder and os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith(".cfg"):
                stem = fn[:-4]
                if stem != "diskdefs" and stem not in names:
                    names.append(stem)
    return names


def read_diskformats(cfg_path: str) -> list[str]:
    """Parse 'disk <name>' lines from a diskdefs .cfg file."""
    formats = [""]
    try:
        with open(cfg_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("disk "):
                    formats.append(line[5:].strip())
    except OSError:
        return [""]
    return formats
