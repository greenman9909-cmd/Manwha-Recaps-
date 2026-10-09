"""Fail-closed technical QC, local voice and SEO tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ashentoons.core import file_hash
from ashentoons.qc import decode_check
from ashentoons.seo import seo_draft
from ashentoons.tts import synthesize


class QcSeoTtsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = self.root / "panel.png"
        self.panel.write_bytes(b"panel")
        self.m = {
            "source_authorized": True, "subtitles": False,
            "generated_visuals": False, "voices": {"MC": "am_puck"},
            "clips": [
                {"panel": "panel.png", "panel_sha256": file_hash(self.panel),
                 "speaker": "MC", "voice": "am_puck",
                 "event_id": f"event-{i}", "narration": f"Chapter {i+1}",
                 "chapter": i+1, "start": i*20, "end": (i+1)*20}
                for i in range(3)
            ],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_technical_decode_success_not_semantic_certification(self):
        probe = {"status": "PASS", "duration": 60, "width": 1920,
                 "height": 1080}
        with patch("ashentoons.qc.probe_media", return_value=probe), \
             patch("subprocess.run", return_value=Mock(returncode=0, stderr=b"")) as run:
            result = decode_check(self.root / "video.mp4", expected_duration=60)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["semantic_alignment_verified"])
        self.assertFalse(result["burned_subtitles_verified_absent"])
        self.assertIn("-xerror", run.call_args.args[0])

    def test_reject_duration_mismatch_before_decode(self):
        with patch("ashentoons.qc.probe_media", return_value={
                "status": "PASS", "duration": 60, "width": 1280, "height": 720}), \
             patch("subprocess.run") as run:
            r = decode_check(self.root / "x.mp4", 75)
        self.assertEqual(r["status"], "FAIL")
        run.assert_not_called()

    def test_reject_corrupt_decode(self):
        with patch("ashentoons.qc.probe_media", return_value={
                "status": "PASS", "duration": 60, "width": 1280, "height": 720}), \
             patch("subprocess.run", return_value=Mock(returncode=1, stderr=b"damaged")):
            self.assertEqual(decode_check(self.root / "x.mp4")["status"], "FAIL")

    def test_seo_chapters_and_private_default(self):
        r = seo_draft(self.m, self.root, "Revenge Story", "He Lost Everything And Returned To Win")
        self.assertEqual(r["status"], "PASS", r)
        self.assertTrue(r["metadata"]["chapters_included"])
        self.assertIn("00:00", r["metadata"]["description"])
        self.assertIn("00:40", r["metadata"]["description"])
        self.assertEqual(r["metadata"]["privacyStatus"], "private")
        self.assertFalse(r["metadata"]["release_authorized"])
        self.assertFalse(r["metadata"]["captions"])

    def test_seo_cannot_claim_chapters_from_bad_timeline(self):
        self.m["clips"][1]["start"] = 5
        r = seo_draft(self.m, self.root, "Revenge Story", "He Lost Everything And Returned To Win")
        self.assertEqual(r["status"], "FAIL")

    def test_seo_rejects_long_title(self):
        r = seo_draft(self.m, self.root, "Revenge Story", "x" * 101)
        self.assertEqual(r["status"], "FAIL")

    def test_local_tts_safety_without_download(self):
        file = self.root / "speech.wav"
        self.assertEqual(synthesize("Hello", file, voice="am_other")["status"], "FAIL")
        self.assertEqual(synthesize("", file)["status"], "FAIL")
        self.assertEqual(synthesize("Hello", file, speed=float("nan"))["status"], "FAIL")
        self.assertEqual(synthesize("Hello", self.root / "speech.exe")["status"], "FAIL")
        self.assertFalse(file.exists())
