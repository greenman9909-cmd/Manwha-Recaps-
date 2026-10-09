"""Per-shot snapshots are external review artifacts, never burned subtitles."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ashentoons.core import file_hash
from ashentoons.review_frames import extract_review_frames


class ReviewFramesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "panel.png").write_bytes(b"panel")
        self.manifest = {
            "source_authorized": True, "subtitles": False,
            "generated_visuals": False, "voices": {"MC": "am_puck"},
            "clips": [{
                "panel": "panel.png",
                "panel_sha256": file_hash(self.root / "panel.png"),
                "event_id": "event-1", "chapter": 1,
                "narration": "The hero discovers a secret.",
                "speaker": "MC", "voice": "am_puck",
                "panel_summary": "The character finds the hidden document.",
                "match_reason": "This is the panel where the discovery occurs.",
                "narrative_role": "reveal", "start": 0, "end": 10,
            }],
        }
        self.video = self.root / "part-001.mp4"
        self.video.write_bytes(b"fixture")

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_frames(self):
        def fake_run(command, **kwargs):
            Path(command[-1]).write_bytes(b"jpeg-image")
            return Mock(returncode=0)
        with patch("ashentoons.review_frames.probe_media",
                   return_value={"status": "PASS", "duration": 10}):
            with patch("subprocess.run", side_effect=fake_run):
                r = extract_review_frames(self.manifest, self.root, self.video,
                                          1, self.root / "review")
        self.assertEqual(r["status"], "PASS", r)
        self.assertEqual(r["frames_extracted"], 1)
        data = json.loads(Path(r["index"]).read_text("utf-8"))
        self.assertIsNone(data["frames"][0]["image_matches_narration"])
        self.assertFalse(data["approved_for_publication"])
        self.assertTrue((self.root / "review" / "shot-00000.jpg").is_file())

    def test_out_of_range_part_blocked(self):
        r = extract_review_frames(self.manifest, self.root, self.video, 2,
                                  self.root / "review")
        self.assertEqual(r["status"], "FAIL")

    def test_failure_to_get_actual_frame(self):
        with patch("ashentoons.review_frames.probe_media",
                   return_value={"status": "PASS", "duration": 10}):
            with patch("subprocess.run", return_value=Mock(returncode=1)):
                r = extract_review_frames(self.manifest, self.root, self.video, 1,
                                          self.root / "review")
        self.assertEqual(r["status"], "FAIL")
        self.assertFalse((self.root / "review" / "review-index.json").exists())
