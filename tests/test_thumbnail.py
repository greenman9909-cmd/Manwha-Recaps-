"""Actual 1280x720 source-based thumbnails, no generated artwork or upload."""
import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from ashentoons.core import file_hash
from ashentoons.thumbnail import make_thumbnail


def chunk(name, data):
    return (struct.pack(">I", len(data)) + name + data
            + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff))


def valid_png(path):
    row = b"\x00" + bytes([80, 100, 140]) * 64
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * 64))
        + chunk(b"IEND", b""))


@unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow optional extra not installed")
class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = self.root / "authorized.png"
        valid_png(self.panel)
        self.out = self.root / "thumb.jpg"

    def tearDown(self):
        self.tmp.cleanup()

    def test_thumbnail_is_valid_youtube_sized_jpeg(self):
        from PIL import Image
        result = make_thumbnail(self.root, "authorized.png", file_hash(self.panel),
                                self.out, "HE CAME BACK!")
        self.assertEqual(result["status"], "PASS", result)
        self.assertLessEqual(self.out.stat().st_size, 2_000_000)
        with Image.open(self.out) as img:
            self.assertEqual(img.size, (1280, 720))
            self.assertEqual(img.format, "JPEG")

    def test_refuses_overwrite_and_hash_mismatch(self):
        result = make_thumbnail(self.root, "authorized.png", "0" * 64,
                                self.out, "THE BIG RETURN")
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(self.out.exists())
        self.out.write_bytes(b"approved thumbnail - do not overwrite")
        result = make_thumbnail(self.root, "authorized.png", file_hash(self.panel),
                                self.out, "THE BIG RETURN")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.out.read_bytes(), b"approved thumbnail - do not overwrite")

    def test_rejects_scriptlike_or_bad_headline(self):
        self.assertEqual(make_thumbnail(
            self.root, "../private.png", file_hash(self.panel),
            self.out, "GOOD TITLE")["status"], "FAIL")
        self.assertEqual(make_thumbnail(
            self.root, "authorized.png", file_hash(self.panel),
            self.out, "\x00bad")["status"], "FAIL")
