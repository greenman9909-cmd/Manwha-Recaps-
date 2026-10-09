"""Offline batch TTS QA: cost gates, cast routing, idempotency, fallback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from ashentoons.voice_batch import batch_narrate_google
from ashentoons.core import file_hash


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.audio=self.root/"audio"
        self.manifest=self.root/"timings.json"
        self.script={"series":"Healing Magic",
                     "clips":[
                         {"speaker":"MC","event_id":"ch01-01","chapter":1,
                          "narration":"One unexpected twist."},
                         {"speaker":"Usato","event_id":"ch01-02","chapter":1,
                          "narration":"You cannot be serious."},
                         {"speaker":"Rose","event_id":"ch01-03","chapter":1,
                          "narration":"Then train harder."},
                     ]}
        self.calls=[]

    def tearDown(self):
        self.tmp.cleanup()

    def fake_voice(self,text,output,voice="Gacrux",model=None,style=None):
        self.calls.append((text,voice))
        output.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(output),"wb") as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
            f.writeframes(b"\x20\x15\x45\x08" * 6000)
        return {"status":"PASS","path":str(output),
                "voice":voice,"duration":1.0,"sha256":file_hash(output)}

    def test_api_charge_approval_required(self):
        result=batch_narrate_google(self.script,self.audio,self.manifest,
                                     synth=self.fake_voice)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(self.audio.exists())
        self.assertFalse(self.manifest.exists())

    def test_missing_key_fails_before_audio_without_fallback(self):
        with patch("ashentoons.voice_batch.credential_ready",return_value=False):
            result=batch_narrate_google(self.script,self.audio,self.manifest,
                                       approve_api_charges=True,synth=self.fake_voice)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(self.audio.exists())
        self.assertEqual(self.calls,[])

    def test_cast_and_cache_reuse_across_runs(self):
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            result=batch_narrate_google(self.script,self.audio,self.manifest,
                                       approve_api_charges=True,synth=self.fake_voice)
        self.assertEqual(result["status"],"PASS",result)
        self.assertEqual(result["new_api_requests"],3)
        self.assertEqual([x[1] for x in self.calls],["Gacrux","Puck","Kore"])
        report=json.loads(self.manifest.read_text("utf8"))
        self.assertEqual([x["speaker"] for x in report["clips"]],["MC","Usato","Rose"])
        self.assertEqual(report["status"],"READY_FOR_STORY_SCENE_REVIEW")
        self.assertFalse(report["release_approved"])
        self.assertTrue(all(x["requires_story_scene_review"] for x in report["clips"]))
        second=self.root/"timings-2.json"
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            again=batch_narrate_google(self.script,self.audio,second,
                                       approve_api_charges=True,synth=self.fake_voice)
        self.assertEqual(again["status"],"PASS",again)
        self.assertEqual(again["new_api_requests"],0)
        self.assertEqual(again["reused"],3)
        self.assertEqual(len(self.calls),3)

    def test_bounded_api_requests_and_resumable_progress(self):
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            first=batch_narrate_google(self.script,self.audio,self.manifest,
                                     approve_api_charges=True,max_new_requests=1,
                                     synth=self.fake_voice)
        self.assertEqual(first["status"],"PARTIAL",first)
        self.assertEqual(first["completed"],1)
        self.assertFalse(self.manifest.exists())
        self.assertEqual(len(list(self.audio.glob("gemini-*.wav"))),1)
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            resumed=batch_narrate_google(self.script,self.audio,self.manifest,
                                       approve_api_charges=True,max_new_requests=2,
                                       synth=self.fake_voice)
        self.assertEqual(resumed["status"],"PASS",resumed)
        self.assertEqual(resumed["reused"],1)
        self.assertEqual(resumed["new_api_requests"],2)

    def test_optional_kokoro_rescue_preserves_speaker(self):
        def fail_google(*args,**kwargs):
            return {"status":"FAIL","errors":["429"]}
        def local(text,path,voice="am_puck"):
            return self.fake_voice(text,path,voice=voice)
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            result=batch_narrate_google(self.script,self.audio,self.manifest,
                                      approve_api_charges=True,
                                      fallback_to_kokoro=True,
                                      synth=fail_google,local_synth=local)
        self.assertEqual(result["status"],"PASS",result)
        report=json.loads(self.manifest.read_text("utf8"))
        self.assertEqual([x["engine"] for x in report["clips"]],["kokoro"]*3)
        self.assertEqual([x["voice"] for x in report["clips"]],
                         ["am_fenrir","am_puck","af_bella"])

    def test_invalid_character_is_rejected_before_cost(self):
        self.script["clips"][0]["speaker"]="UnexpectedPerson"
        with patch("ashentoons.voice_batch.credential_ready",return_value=True):
            result=batch_narrate_google(self.script,self.audio,self.manifest,
                                      approve_api_charges=True,synth=self.fake_voice)
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(self.audio.exists())

if __name__=="__main__":unittest.main()
