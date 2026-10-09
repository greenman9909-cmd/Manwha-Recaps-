"""CLI smoke tests for planning, review, drafts, and workspace creation."""
import json
import tempfile
import unittest
from pathlib import Path

from ashentoons.cli import main
from ashentoons.core import file_hash


class PipelineCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        panel = self.root / "panel.png"
        panel.write_bytes(b"panel-fixture")
        self.m = self.root / "manifest.json"
        clips = []
        for i in range(2):
            clips.append({
                "panel": "panel.png", "panel_sha256": file_hash(panel),
                "event_id": f"scene-{i}", "chapter": i + 1,
                "speaker": "MC", "voice": "am_puck",
                "narration": "An original narrative line to explain what happened.",
                "panel_summary": "A panel depicts a scene involving the main character.",
                "match_reason": "This is the visual moment referenced in this narration.",
                "narrative_role": "setup", "start": i * 20, "end": (i + 1) * 20,
            })
        self.m.write_text(json.dumps({
            "source_authorized": True, "subtitles": False,
            "generated_visuals": False,
            "voices": {"MC": "am_puck"}, "clips": clips,
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def args(self):
        return [str(self.m), "--source-root", str(self.root)]

    def test_plan_and_storyboard_cli(self):
        self.assertEqual(main(["plan-parts", *self.args()]), 0)
        self.assertEqual(main(["storyboard-audit", *self.args()]), 0)

    def test_review_template_is_pending(self):
        out = self.root / "review.json"
        self.assertEqual(main(["review-template", *self.args(), "--output", str(out)]), 0)
        data = json.loads(out.read_text("utf-8"))
        self.assertFalse(data["approved_for_publication"])
        self.assertEqual(main(["review-check", str(out)]), 2)

    def test_seo_draft_private(self):
        out = self.root / "youtube.json"
        cmd = ["seo-draft", *self.args(), "--series", "Original Series",
               "--title", "The Hero Changes Everything in this Original Story",
               "--output", str(out)]
        self.assertEqual(main(cmd), 0)
        data = json.loads(out.read_text("utf-8"))
        self.assertEqual(data["privacyStatus"], "private")
        self.assertFalse(data["release_authorized"])

    def test_workspace_never_deletes_source(self):
        folder = self.root / "drive" / "AshenToons"
        self.assertEqual(main(["workspace-init", str(folder)]), 0)
        keep = folder / "sources" / "original.png"
        keep.write_bytes(b"keep")
        self.assertEqual(main(["workspace-init", str(folder)]), 0)
        self.assertEqual(keep.read_bytes(), b"keep")

    def test_tts_invalid_speed_has_no_side_effects(self):
        out = self.root / "speech.wav"
        self.assertEqual(main(["tts-line", "Hello", str(out), "--speed", "100"]), 2)
        self.assertFalse(out.exists())
