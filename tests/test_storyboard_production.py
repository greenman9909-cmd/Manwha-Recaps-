"""Grounding, segmentation, audio-lock and review safety regression tests."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ashentoons.core import file_hash
from ashentoons.production import plan_parts, render_parts
from ashentoons.storyboard import audit_storyboard, review_template, check_review


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = self.root / "panel.png"
        self.panel.write_bytes(b"original-fixture")
        self.audio = self.root / "speech.wav"
        self.audio.write_bytes(b"audio-fixture")
        self.m = {
            "source_authorized": True, "subtitles": False,
            "generated_visuals": False, "voices": {"MC": "am_puck"},
            "clips": [],
        }
        for i in range(31):
            self.m["clips"].append({
                "panel": "panel.png",
                "panel_sha256": file_hash(self.panel),
                "audio": "speech.wav",
                "audio_sha256": file_hash(self.audio),
                "speaker": "MC", "voice": "am_puck",
                "event_id": f"event-{i}", "chapter": i // 7 + 1,
                "narration": f"Original scene event {i}",
                "panel_summary": f"Panel depicts the moment of scene {i}",
                "match_reason": f"Evidence for scene number {i} in panel",
                "narrative_role": "setup" if i else "hook",
                "start": float(i * 10), "end": float((i + 1) * 10),
            })

    def tearDown(self):
        self.tmp.cleanup()

    def test_plans_two_parts_at_300_second_cap(self):
        r = plan_parts(self.m, self.root)
        self.assertEqual(r["status"], "PASS", r)
        self.assertEqual(len(r["parts"]), 2)
        self.assertLessEqual(max(p["duration"] for p in r["parts"]), 300)
        self.assertEqual(sum(len(p["clip_indices"]) for p in r["parts"]), 31)
        self.assertFalse(r["subtitles"])

    def test_boundary_without_gap(self):
        r = plan_parts(self.m, self.root, 180, 240)
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["parts"][0]["end"], 210)

    def test_gap_rejected(self):
        self.m["clips"][10]["start"] += 0.6
        r = plan_parts(self.m, self.root)
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("gap", str(r["errors"]))

    def test_bad_duration_setting(self):
        for target, maximum in ((300, 120), (0, 240), (float("nan"), 240), (200, True)):
            self.assertEqual(plan_parts(self.m, self.root, target, maximum)["status"], "FAIL")

    def test_missing_story_evidence_rejected(self):
        self.m["clips"][0].pop("match_reason")
        self.assertEqual(audit_storyboard(self.m)["status"], "FAIL")
        with patch("ashentoons.production.probe_audio") as mock_audio:
            r = render_parts(self.m, self.root, self.root / "exports")
        self.assertEqual(r["status"], "FAIL")
        mock_audio.assert_not_called()

    def test_bad_role_rejected(self):
        self.m["clips"][0]["narrative_role"] = "made-up-role"
        self.assertEqual(audit_storyboard(self.m)["status"], "FAIL")

    def test_review_never_approves_by_itself(self):
        planned = plan_parts(self.m, self.root)
        sheet = review_template(self.m, planned)
        self.assertEqual(sheet["status"], "PENDING_HUMAN_REVIEW")
        self.assertIsNone(sheet["parts"][0]["shots"][0]["image_matches_narration"])
        self.assertFalse(sheet["approved_for_publication"])
        self.assertEqual(check_review(sheet)["status"], "FAIL")

    def test_matching_audio_hash_rejected_on_tampering(self):
        self.audio.write_bytes(b"mutated-audio")
        with patch("ashentoons.production.probe_audio") as probe:
            result = render_parts(self.m, self.root, self.root / "exports")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("SHA-256 mismatch", str(result["errors"]))
        probe.assert_not_called()

    def test_nonmatching_audio_duration_blocks_rendering(self):
        with patch("ashentoons.production.probe_audio", return_value={"status": "PASS", "duration": 3}):
            with patch("ashentoons.production.render_clip") as render:
                result = render_parts(self.m, self.root, self.root / "exports")
        self.assertEqual(result["status"], "FAIL")
        render.assert_not_called()

    def test_cached_render_and_full_part_decode(self):
        # Unit mocked renderer exercises control flow only; integration
        # coverage uses real FFmpeg in test_real_media_smoke.py.
        one = copy.deepcopy(self.m)
        one["clips"] = one["clips"][:2]
        def write_clip(root, panel, audio, output, duration, width, height, motion="static"):
            output.write_bytes(b"fixture")
            return {"status": "PASS"}
        def assemble(clips, output):
            output.write_bytes(b"part")
            return {"status": "PASS", "duration": 20, "sha256": "a" * 64}
        probe = {"status": "PASS", "duration": 10, "width": 1280, "height": 720}
        with patch("ashentoons.production.probe_audio", return_value={"status": "PASS", "duration": 10}), \\
             patch("ashentoons.production.render_clip", side_effect=write_clip) as render, \\
             patch("ashentoons.production.assemble", side_effect=assemble), \\
             patch("ashentoons.production.probe_media", return_value=probe), \\
             patch("ashentoons.production.decode_check", return_value={"status": "PASS"}) as decode:
            first = render_parts(one, self.root, self.root / "exports")
            self.assertEqual(first["status"], "PASS", first)
            self.assertEqual(render.call_count, 2)
            second = render_parts(one, self.root, self.root / "exports")
            self.assertEqual(second["status"], "PASS", second)
            self.assertEqual(second["clips_reused"], 2)
            self.assertEqual(render.call_count, 2)
            self.assertEqual(decode.call_count, 2)
            self.assertFalse(second["ready_to_publish"])
            one["clips"][0]["motion"] = "zoom_in"
            third = render_parts(one, self.root, self.root / "exports")
            self.assertEqual(third["status"], "PASS")
            self.assertEqual(render.call_count, 3)
