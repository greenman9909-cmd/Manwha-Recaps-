"""Kokoro batch building runs with a mocked model, no network/model download."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ashentoons.core import file_hash, validate
from ashentoons.narrate import narrate_script


class NarrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = self.root / "panel.png"
        self.panel.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        self.script = {
            "source_authorized": True, "subtitles": False,
            "generated_visuals": False, "clips": []
        }
        for i in range(2):
            self.script["clips"].append({
                "panel": "panel.png", "panel_sha256": file_hash(self.panel),
                "event_id": f"evt-{i}", "chapter": 1,
                "narration": "The hero returns to make an important choice.",
                "panel_summary": "Panel includes the entire group in a meeting.",
                "match_reason": "The described event visually takes place in this panel.",
                "narrative_role": "setup", "motion": "static"
            })

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_manifest_with_reused_wav(self):
        output = self.root / "episode.json"

        def synth(_text, dest, speed=1.0, pipeline=None):
            dest.write_bytes(b"fixture-wav")
            return {"status": "PASS", "duration": 2.0}
        fake_kokoro = types.SimpleNamespace(KPipeline=lambda lang_code: object())
        with patch.dict("sys.modules", {"kokoro": fake_kokoro}):
            with patch("ashentoons.narrate.synthesize", side_effect=synth) as run:
                with patch("ashentoons.narrate.probe_audio",
                           return_value={"status": "PASS", "duration": 2.0}):
                    first = narrate_script(self.script, self.root, output)
                    self.assertEqual(first["status"], "PASS", first)
                    self.assertEqual(first["audio_reused"], 1)
                    self.assertEqual(run.call_count, 1)
                    manifest = json.loads(output.read_text("utf-8"))
                    self.assertEqual(validate(manifest, self.root)["status"], "PASS")
                    self.assertEqual(manifest["voices"], {"MC": "am_puck"})
                    self.assertEqual(manifest["clips"][0]["start"], 0)
                    self.assertEqual(manifest["clips"][1]["end"], 4)
                    self.assertFalse(first["ready_to_publish"])
                    second = narrate_script(self.script, self.root, self.root / "again.json")
                    self.assertEqual(second["status"], "PASS", second)
                    self.assertEqual(second["audio_reused"], 2)
                    self.assertEqual(run.call_count, 1)

    def test_missing_authorization_does_not_generate(self):
        self.script["source_authorized"] = False
        self.assertEqual(narrate_script(self.script, self.root, self.root / "a.json")["status"], "FAIL")

    def test_unsafe_audio_directory_rejected(self):
        r = narrate_script(self.script, self.root, self.root / "a.json", "../elsewhere")
        self.assertEqual(r["status"], "FAIL")

    def test_existing_manifest_not_overwritten(self):
        dest = self.root / "episode.json"
        dest.write_text("important original", encoding="utf-8")
        r = narrate_script(self.script, self.root, dest)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(dest.read_text("utf-8"), "important original")

    def test_source_hash_tampering_blocks_tts(self):
        self.panel.write_bytes(b"altered")
        r = narrate_script(self.script, self.root, self.root / "a.json")
        self.assertEqual(r["status"], "FAIL")
        self.assertFalse((self.root / "narration").exists())

    def test_missing_panel_reason_blocks_tts(self):
        del self.script["clips"][0]["match_reason"]
        r = narrate_script(self.script, self.root, self.root / "a.json")
        self.assertEqual(r["status"], "FAIL")

    def test_nonstatic_motion_allowlist(self):
        self.script["clips"][0]["motion"] = "eval(x)"
        r = narrate_script(self.script, self.root, self.root / "a.json")
        self.assertEqual(r["status"], "FAIL")
