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
from ashentoons.core import file_hash
from ashentoons.production import render_parts


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
            manifest = {
                "source_authorized": True, "subtitles": False,
                "generated_visuals": False, "voices": {"MC": "am_puck"},
                "clips": [
                    {
                        "panel": "panel.png",
                        "panel_sha256": file_hash(root / "panel.png"),
                        "audio": "voice.wav",
                        "audio_sha256": file_hash(root / "voice.wav"),
                        "speaker": "MC", "voice": "am_puck",
                        "event_id": f"event-{i}", "chapter": i + 1,
                        "narration": "One original scene event.",
                        "panel_summary": "Original colored illustration of a scene.",
                        "match_reason": "This particular scene matches the spoken event.",
                        "narrative_role": "setup",
                        "start": i, "end": i + 1,
                    } for i in range(2)
                ],
            }
            first = render_parts(manifest, root, root / "exports",
                                 target_seconds=1, max_seconds=3,
                                 width=640, height=360)
            self.assertEqual(first["status"], "PASS", first)
            self.assertEqual(len(first["parts"]), 2)
            second = render_parts(manifest, root, root / "exports",
                                  target_seconds=1, max_seconds=3,
                                  width=640, height=360)
            self.assertEqual(second["status"], "PASS", second)
            self.assertEqual(second["parts_reused"], 2)
            manifest["clips"][0]["motion"] = "zoom_in"
            changed = render_parts(manifest, root, root / "exports",
                                   target_seconds=1, max_seconds=3,
                                   width=640, height=360)
            self.assertEqual(changed["status"], "FAIL")
            self.assertTrue((root / "exports" / "part-001.mp4").exists())
