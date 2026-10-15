"""INI settings — mirrors the keys used by the original (section
'FluxMyFluffyFloppy' in FluxMyFluffyFloppy.ini / pyfluff.ini)."""

from __future__ import annotations

import configparser
import os

SECTION = "FluxMyFluffyFloppy"

DEFAULTS: dict[str, str] = {
    "Version": "v0.1.0",
    "VersionINI": "10",
    "Height": "770",
    "Width": "935",
    "ShowArg": "True",
    "Greaseweazle": "",
    "SaveBoolGWDevCom": "False",
    "SaveGWDevice": "",
    "SaveBoolGWDrive": "False",
    "SaveGWDrive": "",
    "GWHW": "Greaseweazle",
    "CodepageCMD": "True",
    "Diskdefs": "",
    "FolderTemplates": "",
    "LastFolder_Read_Dest": "",
    "LastFolder_Write_Source": "",
    "LastFolder_Convert_Source": "",
    "LastFolder_Convert_Dest": "",
    "Time": "False",
    "Backtrace": "False",
}


class AppConfig:
    def __init__(self, path: str):
        self.path = path
        self._cp = configparser.ConfigParser()
        self._cp.optionxform = str  # keep key case like the Delphi TIniFile
        if os.path.exists(path):
            self._cp.read(path, encoding="utf-8")
        if SECTION not in self._cp:
            self._cp[SECTION] = {}
        for k, v in DEFAULTS.items():
            self._cp[SECTION].setdefault(k, v)

    # -- typed accessors -------------------------------------------------
    def get(self, key: str, default: str = "") -> str:
        return self._cp[SECTION].get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self._cp[SECTION].get(key)
        if val is None:
            return default
        return val.strip().lower() in ("1", "true", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._cp[SECTION].get(key, str(default)))
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: object) -> None:
        if isinstance(value, bool):
            value = "True" if value else "False"
        self._cp[SECTION][key] = str(value)

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            self._cp.write(fh)
