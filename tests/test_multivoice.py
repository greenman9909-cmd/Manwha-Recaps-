"""Multi-character Kokoro production checks without external model/network."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ashentoons.core import file_hash, validate
from ashentoons.narrate import narrate_script
from ashentoons.tts import synthesize, SUPPORTED_VOICES


class MultivoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = self.root / "original.png"
        self.panel.write_bytes(b"\x89PNG\r\n\x1a\n" + b"original image fixture")
        self.script = {
            "source_authorized": True,
            "subtitles": False,
            "generated_visuals": False,
            "voices": {"MC": "am_fenrir", "Lloyd": "am_puck", "Javier": "am_michael"},
            "clips": []
        }
        for i, speaker in enumerate(("MC", "Lloyd", "Javier", "MC")):
            self.script["clips"].append({
                "panel": "original.png",
                "panel_sha256": file_hash(self.panel),
                "chapter": 1,
                "speaker": speaker,
                "event_id": f"scene-{i}",
                "narration": "The engineer has an unexpected plan.",
                "panel_summary": "The panel features a character facing an unusual problem.",
                "match_reason": "An editor states this image is consistent with the event.",
                "narrative_role": "hook" if i == 0 else "reaction",
                "motion": "static",
            })

    def tearDown(self):
        self.tmp.cleanup()

    def test_cast_voice_registry_and_per_voice_cache(self):
        calls = []
        def synth(text, output, *, speed=1.0, pipeline=None, voice="am_puck"):
            calls.append((text, voice))
            output.write_bytes((text + voice).encode("utf-8"))
            return {"status": "PASS", "duration": 2}

        fake_kokoro = types.SimpleNamespace(KPipeline=lambda lang_code: object())
        with patch.dict("sys.modules", {"kokoro": fake_kokoro}):
            with patch("ashentoons.narrate.synthesize", side_effect=synth):
                with patch("ashentoons.narrate.probe_audio", return_value={
                        "status": "PASS", "duration": 2.0}):
                    response = narrate_script(
                        self.script, self.root, self.root / "episode.json")
                    self.assertEqual(response["status"], "PASS", response)
                    self.assertEqual(response["audio_reused"], 1)
                    self.assertEqual(len(calls), 3)
                    generated = json.loads(
                        (self.root / "episode.json").read_text(encoding="utf-8"))
                    self.assertEqual(generated["voices"], self.script["voices"])
                    self.assertEqual(
                        [s["voice"] for s in generated["clips"]],
                        ["am_fenrir", "am_puck", "am_michael", "am_fenrir"])
                    self.assertEqual(
                        [s["speaker"] for s in generated["clips"]],
                        ["MC", "Lloyd", "Javier", "MC"])
                    self.assertEqual(
                        len({s["audio"] for s in generated["clips"]}), 3)
                    self.assertEqual(validate(generated, self.root)["status"], "PASS")
                    self.assertFalse(response["ready_to_publish"])
                    again = narrate_script(
                        self.script, self.root, self.root / "episode-again.json")
                    self.assertEqual(again["status"], "PASS", again)
                    self.assertEqual(again["audio_reused"], 4)
                    self.assertEqual(len(calls), 3)

    def test_unauthorized_character_speaker_refused_without_side_effects(self):
        self.script["clips"][0]["speaker"] = "Impostor"
        report = narrate_script(self.script, self.root, self.root / "episode.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse((self.root / "narration").exists())

    def test_invalid_or_mismatched_voice_preflight_refused(self):
        self.script["voices"]["Javier"] = "am_madeup"
        self.assertEqual(narrate_script(
            self.script, self.root, self.root / "bad.json")["status"], "FAIL")
        self.script["voices"]["Javier"] = "am_michael"
        self.script["clips"][2]["voice"] = "af_sky"
        self.assertEqual(narrate_script(
            self.script, self.root, self.root / "bad.json")["status"], "FAIL")
        self.assertFalse((self.root / "narration").exists())

    def test_narrator_voice_collision_is_rejected(self):
        self.script["voices"]["Javier"] = "am_fenrir"
        result = narrate_script(self.script, self.root, self.root / "bad.json")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("narrator", " ".join(result["errors"]))
        self.assertFalse((self.root / "narration").exists())

    def test_tts_allowlist_rejects_unknown_voice_without_creating_file(self):
        self.assertIn("am_fenrir", SUPPORTED_VOICES)
        self.assertIn("af_bella", SUPPORTED_VOICES)
        file = self.root / "new.wav"
        self.assertEqual(synthesize("Hello", file, voice="custom_unknown")["status"], "FAIL")
        self.assertFalse(file.exists())

    def test_legacy_narrator_defaults_to_puck(self):
        del self.script["voices"]
        for item in self.script["clips"]:
            item.pop("speaker")
        self.script["clips"] = self.script["clips"][:1]
        def synth(text, output, speed=1.0, pipeline=None):
            output.write_bytes(b"legacy")
            return {"status": "PASS"}
        fake = types.SimpleNamespace(KPipeline=lambda lang_code: object())
        with patch.dict("sys.modules", {"kokoro": fake}):
            with patch("ashentoons.narrate.synthesize", side_effect=synth):
                with patch("ashentoons.narrate.probe_audio", return_value={
                        "status": "PASS", "duration": 2.0}):
                    result = narrate_script(self.script, self.root, self.root / "legacy.json")
        self.assertEqual(result["status"], "PASS", result)
        legacy = json.loads((self.root / "legacy.json").read_text("utf-8"))
        self.assertEqual(legacy["voices"], {"MC": "am_puck"})
