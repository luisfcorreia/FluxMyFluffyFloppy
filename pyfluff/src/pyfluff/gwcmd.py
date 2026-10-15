"""Command-line generation — faithful port of TForm1.CMD_Generate (unit1.pas).

Builds both a shell-quoted display string (shown in the GUI, like EdGWCMD)
and an argv list (used to launch gw safely, so paths with spaces work).
"""

from __future__ import annotations

import os
import shlex


def dircheck(path: str) -> str:
    """Ensure a trailing separator (port of DirCheck; uses os.sep)."""
    if not path:
        return ""
    return path if path.endswith((os.sep, "/", "\\")) else path + os.sep


def trackset(command: str, cyl: str, heads: str, steps: str,
             hswap: bool, flippy: str) -> str:
    """Port of Trackset(): e.g. ' --tracks=c=0-81:h=0-1:step=1:hswap:h0.off=+8'."""
    cmd = command + "c=" + cyl
    if heads:
        cmd += ":h=" + heads
    if steps:
        cmd += ":step=" + steps
    if hswap:
        cmd += ":hswap"
    if flippy:
        cmd += ":" + flippy
    return cmd


def _quote(argv: list[str]) -> str:
    """Display string with Windows-style double quotes around spaced args."""
    out = []
    for a in argv:
        if not a or any(c in a for c in " \t\""):
            out.append('"' + a.replace('"', '""') + '"')
        else:
            out.append(a)
    return " ".join(out)


def device_args(device: str, hardware: str = "Greaseweazle") -> list[str]:
    """Port of the --device quirk: Adafruit RP2040 uses '--device COMx'
    (space), plain Greaseweazle uses '--device=COMx'."""
    if not device:
        return []
    if hardware == "Adafruit RP2040":
        return ["--device", device]
    return ["--device=" + device]


def build_read(gw: str, device: str, hardware: str, drive: str,
               fmt_src: str, diskdefs_path: str, fmt: str, show_all: bool,
               cyls: str = "", heads: str = "", steps: str = "",
               hswap: bool = False, flippy: str = "",
               reverse: bool = False, revs: str = "", raw: bool = False,
               fake_index: str = "", hard_sectors: bool = False,
               adjust_speed: str = "", retries: str = "",
               seek_retries: str = "", no_overwrite: bool = False,
               pll: str = "", densel: str = "",
               dest_dir: str = "", dest_preview: str = "",
               backtrace: bool = False, timed: bool = False,
               ) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("read")
    argv += device_args(device, hardware)
    if drive:
        argv.append("--drive=" + drive)
    if fmt_src != "Internal":
        argv += ["--diskdefs", diskdefs_path]
        if fmt:
            argv += ["--format", fmt]
    elif fmt:
        argv += ["--format", fmt]
    if show_all:
        if cyls:
            argv.append(trackset(" --tracks=", cyls, heads, steps,
                                 hswap, flippy).strip())
            if flippy and reverse:
                argv.append("--reverse")
        if revs:
            argv.append("--revs=" + revs)
        if raw:
            argv.append("--raw")
        if fake_index:
            argv.append("--fake-index=" + fake_index)
        if hard_sectors:
            argv.append("--hard-sectors")
        if adjust_speed:
            argv.append("--adjust-speed=" + adjust_speed)
        if retries:
            argv.append("--retries=" + retries)
        if seek_retries:
            argv.append("--seek-retries=" + seek_retries)
        if no_overwrite:
            argv.append("-n")
        if pll:
            argv.append("--pll")
            argv.append(pll)
        if densel:
            argv.append("--densel")
            argv.append(densel)
    if dest_preview:
        argv.append(dircheck(dest_dir) + dest_preview)
    return _quote(argv), argv


def build_write(gw: str, device: str, drive: str,
                fmt_src: str, diskdefs_path: str, fmt: str, show_all: bool,
                cyls: str = "", heads: str = "", steps: str = "",
                hswap: bool = False, flippy: str = "",
                reverse: bool = False, pre_erase: bool = False,
                erase_empty: bool = False, fake_index: str = "",
                hard_sectors: bool = False, no_verify: bool = False,
                retries: str = "", precomp: str = "", densel: str = "",
                gen_tg43: bool = False, source_file: str = "",
                backtrace: bool = False, timed: bool = False,
                ) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("write")
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    if fmt_src != "Internal":
        argv += ["--diskdefs", diskdefs_path]
        if fmt:
            argv += ["--format", fmt]
    elif fmt:
        argv += ["--format", fmt]
    if show_all:
        if cyls:
            argv.append(trackset(" --tracks=", cyls, heads, steps,
                                 hswap, flippy).strip())
            if flippy and reverse:
                argv.append("--reverse")
        if pre_erase:
            argv.append("--pre-erase")
        if erase_empty:
            argv.append("--erase-empty")
        if fake_index:
            argv.append("--fake-index=" + fake_index)
        if hard_sectors:
            argv.append("--hard-sectors")
        if no_verify:
            argv.append("--no-verify")
        if retries:
            argv.append("--retries=" + retries)
        if precomp:
            argv.append("--precomp=" + precomp)
        if densel:
            argv.append("--densel")
            argv.append(densel)
        if gen_tg43:
            argv.append("--gen-tg43")
    if source_file:
        argv.append(source_file)
    return _quote(argv), argv


def build_convert(gw: str, diskdefs_name: str, diskdefs_path: str,
                  fmt: str, show_all: bool,
                  cyls: str = "", heads: str = "", steps: str = "",
                  hswap: bool = False, flippy: str = "",
                  out_cyls: str = "", out_heads: str = "",
                  out_steps: str = "", out_hswap: bool = False,
                  out_flippy: str = "", reverse: bool = False,
                  adjust_speed: str = "", no_overwrite: bool = False,
                  pll: str = "", index_marks: str = "",
                  source_file: str = "", dest_dir: str = "",
                  dest_preview: str = "",
                  backtrace: bool = False, timed: bool = False,
                  ) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("convert")
    if diskdefs_name != "Internal":
        argv += ["--diskdefs", diskdefs_path]
        if fmt:
            argv += ["--format", fmt]
    elif fmt:
        argv += ["--format", fmt]
    if show_all:
        if cyls:
            argv.append(trackset(" --tracks=", cyls, heads, steps,
                                 hswap, flippy).strip())
        if out_cyls:
            argv.append(trackset(" --out-tracks=", out_cyls, out_heads,
                                 out_steps, out_hswap, out_flippy).strip())
            if out_flippy and reverse:
                argv.append("--reverse")
        if adjust_speed:
            argv.append("--adjust-speed=" + adjust_speed)
        if no_overwrite:
            argv.append("-n")
        if pll:
            argv.append("--pll")
            argv.append(pll)
        if index_marks:
            argv.append(index_marks)
        if source_file:
            argv.append(source_file)
    if dest_preview:
        argv.append(dircheck(dest_dir) + dest_preview)
    return _quote(argv), argv


def build_erase(gw: str, device: str, drive: str, cyls: str = "",
                heads: str = "", steps: str = "", hswap: bool = False,
                flippy: str = "", revs: str = "", hfreq: bool = False,
                fake_index: str = "", backtrace: bool = False,
                timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("erase")
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    if revs:
        argv.append("--revs=" + revs)
    if cyls:
        argv.append(trackset(" --tracks=", cyls, heads, steps,
                             hswap, flippy).strip())
    if hfreq:
        argv.append("--hfreq")
    if fake_index:
        argv.append("--fake-index=" + fake_index)
    return _quote(argv), argv


def build_seek(gw: str, device: str, drive: str, track: str,
               force: bool = False, motor_on: bool = False,
               backtrace: bool = False,
               timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("seek")
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    if force:
        argv.append("--force")
    if motor_on:
        argv.append("--motor-on")
    argv.append(track or "0")
    return _quote(argv), argv


def build_clean(gw: str, device: str, drive: str, cyls: str,
                linger: str, passes: str, backtrace: bool = False,
                timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("clean")
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    argv.append("--cyls=" + (cyls or "0"))
    argv.append("--linger=" + (linger or "100"))
    argv.append("--passes=" + (passes or "1"))
    return _quote(argv), argv


def build_rpm(gw: str, device: str, drive: str, nr: str,
              backtrace: bool = False,
              timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("rpm")
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    argv.append("--nr=" + (nr or "1"))
    return _quote(argv), argv


def build_delays(gw: str, device: str, select: str = "", step: str = "",
                 settle: str = "", motor: str = "", watchdog: str = "",
                 pre_write: str = "", post_write: str = "",
                 index_mask: str = "", backtrace: bool = False,
                 timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("delays")
    if device:
        argv.append("--device=" + device)
    if select:
        argv += ["--select", select]
    if step:
        argv += ["--step", step]
    if settle:
        argv += ["--settle", settle]
    if motor:
        argv += ["--motor", motor]
    if watchdog:
        argv += ["--watchdog", watchdog]
    if pre_write:
        argv += ["--pre-write", pre_write]
    if post_write:
        argv += ["--post-write", post_write]
    if index_mask:
        argv += ["--index-mask", index_mask]
    return _quote(argv), argv


def build_pin(gw: str, device: str, drive: str, get: bool,
              pin_number: str = "", level: str = "",
              backtrace: bool = False,
              timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv += ["pin", "get" if get else "set"]
    if device:
        argv.append("--device=" + device)
    if drive:
        argv.append("--drive=" + drive)
    if pin_number:
        argv.append(pin_number)
    if not get and level:
        if level.startswith("Low"):
            argv.append("L")
        elif level.startswith("High"):
            argv.append("H")
    return _quote(argv), argv


def build_update(gw: str, device: str, bootloader: bool = False,
                 mode: str = "online", path: str = "", tag: str = "",
                 backtrace: bool = False,
                 timed: bool = False) -> tuple[str, list[str]]:
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append("update")
    if device:
        argv.append("--device=" + device)
    if bootloader:
        argv.append("--bootloader")
    if mode == "file" and path:
        argv += ["--force", path]
    elif mode == "tag" and tag:
        argv += ["--tag", tag]
    return _quote(argv), argv


def build_simple(gw: str, device: str, verb: str,
                 backtrace: bool = False,
                 timed: bool = False) -> tuple[str, list[str]]:
    """bandwidth / info / reset / delays-info one-shot commands."""
    argv = [gw]
    if backtrace:
        argv.append("--bt")
    if timed:
        argv.append("--time")
    argv.append(verb)
    argv += device_args(device)
    return _quote(argv), argv


# --------------------------------------------------------------------------
# Destination filename builder (port of TForm1.Create_Filename)
# --------------------------------------------------------------------------

def _numbered(base: str, num: int, digits: int) -> str:
    if num <= 0:
        return base
    return base + str(num).zfill(max(1, digits))


def numbered_name(base: str, disk1: int, of_text: str, disk2: int,
                  digits: int) -> str:
    """base + zero-padded disk1 [+ of_text + zero-padded disk2]."""
    name = _numbered(base, disk1, digits)
    if disk2 > 0:
        name += of_text + str(disk2).zfill(max(1, digits))
    return name


def apply_extension(stem: str, image_format: str, opt: str = "",
                    hfe_ver: str = "", hfe_int: str = "",
                    hfe_enc: str = "") -> str:
    """Port of the 'read/conv file extension' case blocks in Create_Filename."""
    t = (image_format or "").strip()
    if not t:
        return stem
    head3 = t[:3]
    if head3 == "EDS":
        return stem + "." + t[:4].strip().lower()
    if head3 == "HFE":
        return stem + ".hfe" + opt + hfe_ver + hfe_int + hfe_enc
    if head3 == "SCP":
        return stem + ".scp" + opt
    if head3 == "RAW":
        return stem + "00.0." + head3.lower()
    return stem + "." + head3.strip().lower()


def read_preview(base: str, disk1: int, of_text: str, disk2: int,
                 digits: int, image_format: str, opt: str = "",
                 hfe_ver: str = "", hfe_int: str = "",
                 hfe_enc: str = "") -> str:
    return apply_extension(numbered_name(base, disk1, of_text, disk2, digits),
                           image_format, opt, hfe_ver, hfe_int, hfe_enc)


# --------------------------------------------------------------------------
# Track-line parser (port of TfrmGW.StrGrid_Fill, unit4.pas)
# --------------------------------------------------------------------------

def parse_track_line(line: str) -> tuple[int, int, bool] | None:
    """Parse gw progress lines like 'T12.0: ...'.

    Returns (track, side, giving_up) or None if not a track line.
    Only 1- and 2-digit tracks are recognised, like the original.
    """
    s = line.lstrip()
    if not s.startswith("T"):
        return None
    dot = s.find(".")
    try:
        if dot == 2:
            track = int(s[1:2])
            side = int(s[3:4])
        elif dot == 3:
            track = int(s[1:3])
            side = int(s[4:5])
        else:
            return None
    except (ValueError, IndexError):
        return None
    if side not in (0, 1) or track < 0:
        return None
    return track, side, "Giving up" in s


def shell_split(display: str) -> list[str]:
    """Best-effort inverse of _quote for pasting a command back."""
    return shlex.split(display, posix=os.name != "nt")
