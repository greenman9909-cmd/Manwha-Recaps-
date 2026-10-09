import json
import tempfile
import unittest
from pathlib import Path
from ashentoons.cli import main
from ashentoons.core import file_hash

class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.panel = self.root / "panel.png"
        self.panel.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture")
        self.manifest = self.root / "episode.json"
        self.manifest.write_text(json.dumps({
            "subtitles":False,"generated_visuals":False,"source_authorized":True,
            "voices":{"MC":"exclusive"},
            "clips":[{"panel":"panel.png","panel_sha256":file_hash(self.panel),
                      "speaker":"MC","voice":"exclusive","event_id":"event",
                      "narration":"Narration","start":0,"end":2}]
        }))
    def tearDown(self): self.temp.cleanup()
    def test_valid_manifest(self):
        self.assertEqual(main(["validate",str(self.manifest),"--source-root",str(self.root)]),0)
    def test_source_audit(self):
        self.assertEqual(main(["audit-source","panel.png","--source-root",str(self.root),"--sha256",file_hash(self.panel)]),0)
    def test_missing_file(self):
        self.assertEqual(main(["validate",str(self.root/"missing.json"),"--source-root",str(self.root)]),2)
    def test_certification_refused(self):
        self.assertEqual(main(["certify",str(self.manifest),"--source-root",str(self.root),"--render",str(self.root/"missing.mp4")]),2)
    def test_bad_json(self):
        self.manifest.write_text("{not-json")
        self.assertEqual(main(["validate",str(self.manifest),"--source-root",str(self.root)]),2)
    def test_oversized_manifest(self):
        self.manifest.write_bytes(b" " * (8*1024*1024+1))
        self.assertEqual(main(["validate",str(self.manifest),"--source-root",str(self.root)]),2)
