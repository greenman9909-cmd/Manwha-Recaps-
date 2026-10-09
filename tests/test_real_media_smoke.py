"""Tiny *actual* FFmpeg smoke test: source panel + WAV => no-subtitle MP4.

No downloaded manhwa, copyrighted samples, external TTS or network required.
"""
import math
import shutil
import struct
import tempfile
import unittest
import wave
import zlib
from pathlib import Path

from ashentoons.assemble import assemble
from ashentoons.media import probe_media
from ashentoons.qc import decode_check
from ashentoons.render import render_clip


def png_chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)


def fixture_png(path):
    width, height = 64, 64
    row = b"\x00" + bytes([60, 85, 115]) * width
    data = row * height
    image = (b"\x89PNG\r\n\x1a\n"
             + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
             + png_chunk(b"IDAT", zlib.compress(data))
             + png_chunk(b"IEND", b""))
    path.write_bytes(image)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg and ffprobe not installed")
class RealMediaSmoke(unittest.TestCase):
    def test_render_assemble_and_full_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_png(root / "panel.png")
            with wave.open(str(root / "voice.wav"), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(24000)
                frames = b"".join(
                    struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / 24000)))
                    for i in range(24000)
                )
                out.writeframes(frames)
            one = root / "one.mp4"
            two = root / "two.mp4"
            for motion, output in (("static", one), ("zoom_in", two)):
                result = render_clip(root, "panel.png", "voice.wav",
                                     output, 1.0, 640, 360, motion=motion)
                self.assertEqual(result["status"], "PASS", result)
                self.assertEqual(decode_check(output, 1.0)["status"], "PASS")
            result = assemble([one, two], root / "part.mp4")
            self.assertEqual(result["status"], "PASS", result)
            final = probe_media(root / "part.mp4")
            self.assertEqual(final["status"], "PASS")
            self.assertGreater(final["duration"], 1.5)
            self.assertEqual(decode_check(root / "part.mp4", 2.0)["status"], "PASS")
