"""Upload safety tests: private-only, explicit consent and no duplicate retries."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ashentoons.youtube import validate_private_upload, upload_private_draft


class YoutubeDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(b"mock video fixture")
        self.secrets = self.root / "oauth-client.json"
        self.secrets.write_text("{}", encoding="utf-8")
        self.token = self.root / "token.json"
        self.receipt = self.root / "receipt.json"
        self.meta = {
            "title": "An Original English Manhwa Recap",
            "description": "Short original commentary about a story.",
            "tags": ["manhwa recap", "AshenToons"],
            "privacyStatus": "private",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def inputs(self, confirmed=True, privacy="private"):
        meta = dict(self.meta)
        meta["privacyStatus"] = privacy
        return validate_private_upload(self.video, meta, self.secrets, self.token,
                                       self.receipt, False, confirmed)

    def test_preflight_requires_explicit_consent_and_private_status(self):
        self.assertEqual(self.inputs(confirmed=False)["status"], "FAIL")
        self.assertEqual(self.inputs(privacy="public")["status"], "FAIL")
        self.assertEqual(self.inputs()["status"], "PASS")

    def test_existing_receipt_blocks_second_attempt(self):
        self.receipt.write_text('{"status":"UNCERTAIN"}', encoding="utf-8")
        result = self.inputs()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("receipt", str(result["errors"]))

    def test_decode_fails_before_any_api_or_receipt(self):
        with patch("ashentoons.youtube.decode_check",
                   return_value={"status": "FAIL", "errors": ["media corrupt"]}):
            result = upload_private_draft(self.video, self.meta, self.secrets,
                                          self.token, self.receipt, False, True)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(self.receipt.exists())

    def fake_google_modules(self, raise_on_chunk=False):
        modules = {}
        names = [
            "google", "google.oauth2", "google.oauth2.credentials",
            "google.auth", "google.auth.transport",
            "google.auth.transport.requests", "google_auth_oauthlib",
            "google_auth_oauthlib.flow", "googleapiclient",
            "googleapiclient.discovery", "googleapiclient.http",
        ]
        for name in names:
            modules[name] = types.ModuleType(name)
            modules[name].__path__ = []

        class Credentials:
            valid = True
            expired = False
            refresh_token = None
            def to_json(self):
                return '{"mock":"credential"}'
        class Flow:
            @classmethod
            def from_client_secrets_file(cls, _path, _scopes):
                return cls()
            def run_local_server(self, port=0):
                return Credentials()
        class Request:
            pass
        class MediaFileUpload:
            def __init__(self, *_args, **_kwargs):
                pass
        class MediaRequest:
            def next_chunk(self):
                if raise_on_chunk:
                    raise RuntimeError("uncertain network result")
                return None, {"id": "abcdefghijk"}
        class Video:
            def __init__(self):
                self.body = None
                self.calls = 0
            def insert(self, **kwargs):
                self.body = kwargs["body"]
                self.calls += 1
                return MediaRequest()
        video = Video()
        class YouTube:
            def videos(self):
                return video
        modules["google.oauth2.credentials"].Credentials = Credentials
        modules["google.auth.transport.requests"].Request = Request
        modules["google_auth_oauthlib.flow"].InstalledAppFlow = Flow
        modules["googleapiclient.discovery"].build = lambda *_a, **_k: YouTube()
        modules["googleapiclient.http"].MediaFileUpload = MediaFileUpload
        return modules, video

    def test_upload_one_private_draft_and_write_receipt(self):
        modules, video = self.fake_google_modules()
        with patch.dict("sys.modules", modules):
            with patch("ashentoons.youtube.decode_check", return_value={"status": "PASS"}):
                result = upload_private_draft(self.video, self.meta, self.secrets,
                                              self.token, self.receipt, False, True)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["privacyStatus"], "private")
        self.assertEqual(video.calls, 1)
        self.assertEqual(video.body["status"]["privacyStatus"], "private")
        self.assertFalse(video.body["status"]["selfDeclaredMadeForKids"])
        saved = json.loads(self.receipt.read_text("utf-8"))
        self.assertEqual(saved["video_id"], "abcdefghijk")
        self.assertEqual(saved["status"], "UPLOADED_PRIVATE")
        self.assertTrue(self.token.exists())

    def test_ambiguous_failure_never_retries(self):
        modules, video = self.fake_google_modules(raise_on_chunk=True)
        with patch.dict("sys.modules", modules):
            with patch("ashentoons.youtube.decode_check", return_value={"status": "PASS"}):
                result = upload_private_draft(self.video, self.meta, self.secrets,
                                              self.token, self.receipt, True, True)
                again = upload_private_draft(self.video, self.meta, self.secrets,
                                             self.token, self.receipt, True, True)
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(again["status"], "FAIL")
        self.assertEqual(video.calls, 1)
        self.assertEqual(json.loads(self.receipt.read_text("utf-8"))["status"], "UNCERTAIN")
