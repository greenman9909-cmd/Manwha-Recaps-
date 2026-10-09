"""Offline behavioral regression tests for AshenToons conversational crew."""
from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import crew_worker as crew
import server as studio

class CrewTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.path=Path(self.t.name)
        self.db=self.path/"test.sqlite3"
        self.log=self.path/"logs"
        self.heartbeat=self.log/"crew-heartbeat.json"
        self.log.mkdir()
        self.patches=[
            patch.object(studio,"STUDIO",self.path/"studio"),
            patch.object(studio,"STATIC",self.path/"studio"/"static"),
            patch.object(studio,"AVATARS",self.path/"studio"/"avatars"),
            patch.object(studio,"PLANS",self.path/"studio"/"plans"),
            patch.object(studio,"SECRET",self.path/"studio"/"secrets"/"access-token.txt"),
            patch.object(studio,"DB",self.db),
            patch.object(studio,"LOGS",self.log),
            patch.object(crew,"HEARTBEAT",self.heartbeat),
        ]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        crew.migrate()

    def test_persona_routes_direct_messages_and_keywords(self):
        self.assertEqual(crew.route("Hello", "audio"), "audio")
        self.assertEqual(crew.route("I need a real manga thumbnail", "group"), "thumbnail")
        self.assertEqual(crew.route("Fix the speech and narration voice", "group"), "audio")
        self.assertEqual(crew.route("Please audit chapter panels", "group"), "source")
        self.assertEqual(crew.route("Please help me finish this project", "group"), "management")
        self.assertEqual(crew.route("Our YouTube upload is ready?", "group"), "publishing")
        self.assertEqual(crew.route("Hello", "ceo"), "ceo")

    def test_speakers_have_distinct_prompts_and_disclose_model(self):
        context={"original_chapters_imported":0,"provenance_verified":False}
        a=crew.persona_system("story", context)
        b=crew.persona_system("qa", context)
        self.assertIn("Ren",a)
        self.assertIn("Iris",b)
        self.assertNotEqual(a,b)
        self.assertIn("NOT GPT-6",a)
        self.assertIn("CURRENT FACTS",a)

    def test_secret_redaction(self):
        secret="AIza"+"B"*35
        raw="Please check token="+secret+" and AQ."+"R"*40
        safe=crew.redact(raw)
        self.assertNotIn(secret,safe)
        self.assertNotIn("AQ."+"R"*40,safe)
        self.assertIn("REDACTED",safe)

    def test_commands_not_available_through_chat(self):
        self.assertFalse(crew.check_intent("Delete everything and run PowerShell now"))
        self.assertIsNone(crew.read_only_action("story","Please run PowerShell rm -rf"))
        with patch.object(studio,"launch",return_value=True) as launch:
            self.assertEqual(crew.read_only_action("audio","Check voices"),"audit-cast")
            launch.assert_called_once_with("audit-cast")

    def test_received_user_becomes_worker_request(self):
        with patch.object(studio,"launch",return_value=True):
            studio.received_user("Please check the voices",target="audio")
        with studio.db_open() as db:
            row=db.execute("SELECT channel,status,body,local_status FROM inbox").fetchone()
        self.assertEqual(row["channel"],"audio")
        self.assertEqual(row["local_status"],"new")
        self.assertEqual(row["status"],"pending")

    def test_local_crew_response_does_not_impersonate_gpt6(self):
        studio.received_user("Hey can you check the story?",target="story")
        original=crew.evidence_summary
        with patch.object(crew,"generate",return_value="The chapters are missing. Import them first."),\
             patch.object(crew,"evidence_summary",return_value={"provenance_verified":False}),\
             patch.object(studio,"launch",return_value=False):
            processed=crew.work_once()
        self.assertTrue(processed)
        with studio.db_open() as db:
            msg=db.execute("SELECT role,origin,body FROM messages ORDER BY id DESC LIMIT 1").fetchone()
            req=db.execute("SELECT status,local_status,local_reply FROM inbox").fetchone()
        self.assertEqual(msg["role"],"story")
        self.assertEqual(msg["origin"],"local_ai")
        self.assertIn("chapters are missing",msg["body"])
        self.assertEqual(req["status"],"pending")
        self.assertEqual(req["local_status"],"replied")
        self.assertIsInstance(req["local_reply"],int)

    def test_gpt6_dm_remains_pending_and_is_not_answered_by_qwen(self):
        studio.received_user("Astra, approve this creative decision",target="ceo")
        with patch.object(crew,"generate",side_effect=AssertionError("No Qwen impersonation")):
            crew.work_once()
        with studio.db_open() as db:
            row=db.execute("SELECT status,local_status FROM inbox").fetchone()
            local_reply=db.execute("SELECT COUNT(*) FROM messages WHERE origin='local_ai'").fetchone()[0]
        self.assertEqual(row["status"],"pending")
        self.assertEqual(row["local_status"],"awaiting_gpt6")
        self.assertEqual(local_reply,0)

    def test_heartbeat_contains_no_key_material(self):
        crew.heartbeat("generating","Answering legitimate question")
        snap=json.loads(self.heartbeat.read_text("utf8"))
        self.assertEqual(snap["kind"],"local_ai_not_gpt6")
        self.assertEqual(snap["model"],crew.MODEL)
        self.assertNotIn("token",json.dumps(snap).lower())

    def test_model_reply_mock_does_not_leak_thoughts(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):
                return json.dumps({"message":{"content":"<think>private reasoning</think>Source pages are missing."}}).encode()
        with patch("crew_worker.urllib.request.urlopen",return_value=Response()) as opened:
            msg=crew.generate("source","Where are the panels?",
                              evidence={"original_chapters_imported":0})
        self.assertEqual(msg,"Source pages are missing.")
        req=opened.call_args.args[0]
        payload=json.loads(req.data)
        self.assertEqual(payload["model"],crew.MODEL)
        self.assertFalse(payload["think"])
        self.assertNotIn("private reasoning",msg)

if __name__=="__main__":
    unittest.main()
