"""Headless tests for the toolkit-independent core (no tkinter needed)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from pyfluff import gwcmd
from pyfluff.choices import IMAGE_FORMATS, INTERNAL_FORMATS
from pyfluff.config_store import AppConfig
from pyfluff.templates import (
    list_templates,
    load_template,
    save_read_template,
    save_write_template,
)


class TestTrackset(unittest.TestCase):
    def test_full(self):
        self.assertEqual(
            gwcmd.trackset(" --tracks=", "0-81", "0-1", "1", True,
                           "h0.off=+8"),
            " --tracks=c=0-81:h=0-1:step=1:hswap:h0.off=+8")

    def test_minimal(self):
        self.assertEqual(gwcmd.trackset(" --tracks=", "0-40", "", "", False,
                                        ""), " --tracks=c=0-40")


class TestReadCmd(unittest.TestCase):
    def test_basic(self):
        display, argv = gwcmd.build_read(
            "gw.exe", "COM3", "Greaseweazle", "0", "Internal", "", "ibm.1440",
            True, dest_dir="/tmp", dest_preview="disk.adf")
        self.assertEqual(argv[:2], ["gw.exe", "read"])
        self.assertIn("--device=COM3", argv)
        self.assertIn("--drive=0", argv)
        self.assertIn("--format", argv)
        self.assertIn("ibm.1440", argv)
        self.assertTrue(argv[-1].endswith("disk.adf"))
        self.assertIn("read", display)

    def test_adafruit_device_quirk(self):
        _d, argv = gwcmd.build_read("gw", "COM6", "Adafruit RP2040", "",
                                    "Internal", "", "", False)
        self.assertIn("--device", argv)
        self.assertIn("COM6", argv)
        self.assertNotIn("--device=COM6", argv)

    def test_all_args(self):
        _d, argv = gwcmd.build_read(
            "gw", "", "Greaseweazle", "", "Internal", "", "", True,
            cyls="0-81", heads="0-1", steps="1", hswap=True,
            flippy="h0.off=+8", reverse=True, revs="3", raw=True,
            fake_index="300rpm", hard_sectors=True, adjust_speed="360",
            retries="2", seek_retries="1", no_overwrite=True,
            pll="period=5:phase=60", densel="H")
        for flag in ("--tracks=c=0-81:h=0-1:step=1:hswap:h0.off=+8",
                     "--reverse", "--revs=3", "--raw",
                     "--fake-index=300rpm", "--hard-sectors",
                     "--adjust-speed=360", "--retries=2",
                     "--seek-retries=1", "-n", "--pll",
                     "period=5:phase=60", "--densel", "H"):
            self.assertIn(flag, argv)

    def test_diskdefs(self):
        _d, argv = gwcmd.build_read("gw", "", "Greaseweazle", "", "diskdefs_x",
                                    "/dd/diskdefs_x.cfg", "ibm.720", True)
        self.assertIn("--diskdefs", argv)
        self.assertIn("/dd/diskdefs_x.cfg", argv)


class TestOtherCmds(unittest.TestCase):
    def test_write(self):
        _d, argv = gwcmd.build_write(
            "gw", "COM3", "1", "Internal", "", "", True, pre_erase=True,
            no_verify=True, retries="5", densel="L", gen_tg43=True,
            source_file="disk.adf")
        for flag in ("write", "--device=COM3", "--drive=1", "--pre-erase",
                     "--no-verify", "--retries=5", "--densel", "L",
                     "--gen-tg43", "disk.adf"):
            self.assertIn(flag, argv)

    def test_convert_out_tracks(self):
        _d, argv = gwcmd.build_convert(
            "gw", "Internal", "", "", True, out_cyls="0-79",
            out_heads="0-1", out_steps="1", out_flippy="h0.off=+8",
            reverse=True, index_marks="--hard-sectors",
            source_file="a.scp", dest_dir="/tmp", dest_preview="a.adf")
        self.assertIn("--out-tracks=c=0-79:h=0-1:step=1:h0.off=+8", argv)
        self.assertIn("--reverse", argv)
        self.assertIn("--hard-sectors", argv)

    def test_tools(self):
        _d, argv = gwcmd.build_erase("gw", "COM3", "0", cyls="0-81",
                                     heads="0,1", revs="2", hfreq=True)
        self.assertEqual(argv[:2], ["gw", "erase"])
        self.assertIn("--tracks=c=0-81:h=0,1", argv)
        self.assertIn("--hfreq", argv)
        _d, argv = gwcmd.build_seek("gw", "", "", "10", force=True,
                                    motor_on=True)
        self.assertEqual(argv[-3:], ["--force", "--motor-on", "10"])
        _d, argv = gwcmd.build_clean("gw", "", "", "40", "100", "3")
        self.assertIn("--cyls=40", argv)
        _d, argv = gwcmd.build_rpm("gw", "", "", "5")
        self.assertIn("--nr=5", argv)

    def test_settings(self):
        _d, argv = gwcmd.build_delays("gw", "COM3", select="10",
                                      watchdog="10000")
        self.assertIn("--select", argv)
        self.assertIn("--watchdog", argv)
        _d, argv = gwcmd.build_pin("gw", "", "", False, "2", "High (5v)")
        self.assertEqual(argv[-2:], ["2", "H"])
        _d, argv = gwcmd.build_pin("gw", "", "", True, "2", "")
        self.assertEqual(argv[1:3], ["pin", "get"])
        _d, argv = gwcmd.build_update("gw", "", False, "file", "fw.upd", "")
        self.assertIn("--force", argv)


class TestFilenames(unittest.TestCase):
    def test_zero_padding(self):
        self.assertEqual(
            gwcmd.numbered_name("disk", 1, "_of_", 0, 2), "disk01")
        self.assertEqual(
            gwcmd.numbered_name("disk", 3, "_of_", 12, 3), "disk003_of_012")

    def test_extensions(self):
        self.assertEqual(
            gwcmd.apply_extension("disk01", "ADF (AmigaDOS)"), "disk01.adf")
        self.assertEqual(
            gwcmd.apply_extension("d", "EDSK (EDSK, use: format=ibm.scan)"),
            "d.edsk")
        self.assertEqual(
            gwcmd.apply_extension("d", "SCP (SuperCardPro)",
                                  "::disktype=amiga"), "d.scp::disktype=amiga")
        self.assertEqual(
            gwcmd.apply_extension("d", "HFE (HxC Floppy Emulator)",
                                  "::bitrate=500", "::version=3",
                                  "::interface=IBMPC_HD",
                                  "::encoding=ISOIBM_MFM"),
            "d.hfe::bitrate=500::version=3::interface=IBMPC_HD"
            "::encoding=ISOIBM_MFM")
        self.assertEqual(gwcmd.apply_extension("d", "RAW (KryoFlux)"),
                         "d00.0.raw")


class TestTrackParser(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(gwcmd.parse_track_line("T1.0: some output"),
                         (1, 0, False))
        self.assertEqual(gwcmd.parse_track_line("T12.1: Giving up"),
                         (12, 1, True))
        self.assertIsNone(gwcmd.parse_track_line("Reading..."))
        self.assertIsNone(gwcmd.parse_track_line("T123.0: x"))


class TestConfigTemplates(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig(os.path.join(tmp, "pyfluff.ini"))
            cfg.set("Greaseweazle", "/opt/gw")
            cfg.set("ShowArg", True)
            cfg.save()
            cfg2 = AppConfig(os.path.join(tmp, "pyfluff.ini"))
            self.assertEqual(cfg2.get("Greaseweazle"), "/opt/gw")
            self.assertTrue(cfg2.get_bool("ShowArg"))

            save_read_template(os.path.join(tmp, "t.inir"),
                               {"Name": "t", "Description": "d",
                                "FormatSpec": "ibm.1440", "Raw": True,
                                "DestDisk1": 3, "PLL": "x"})
            d = load_template(os.path.join(tmp, "t.inir"))
            self.assertEqual(d["FormatSpec"], "ibm.1440")
            self.assertTrue(d["Raw"])
            self.assertEqual(d["DestDisk1"], 3)
            self.assertEqual(list_templates(tmp, ".inir"), ["t"])

            save_write_template(os.path.join(tmp, "w.iniw"),
                                {"Name": "w", "Pre-Erase": True,
                                 "DD": "H"})
            d = load_template(os.path.join(tmp, "w.iniw"))
            self.assertTrue(d["Pre-Erase"])
            self.assertEqual(d["DD"], "H")


class TestChoices(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(INTERNAL_FORMATS), 142)
        self.assertEqual(len(IMAGE_FORMATS), 41)


if __name__ == "__main__":
    unittest.main()
