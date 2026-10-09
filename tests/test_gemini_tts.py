"""No-network contract tests for Google AI Studio optional AshenToons narration."""
from __future__ import annotations
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import wave

from ashentoons.gemini_tts import (
    _pcm_from_response, credential_ready, GOOGLE_MODEL,
    DEFAULT_GOOGLE_CAST, DEFAULT_KOKORO_CAST, line_cache_path,
    probe_wave, save_key_securely, synthesize_google, validate_key,
)

FAKE_TEST_KEY = "AIza" + "F" * 34  # Format-valid mock key, never sent to Google.
SOUND = (b"\x12\x08" + b"\x25\x0c" + b"\x11\x09" + b"\x02\x06") * 700
PCM_JSON = {
    "candidates": [
        {"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000",
            "data": base64.b64encode(SOUND).decode("ascii"),
        }}]}}
    ]
}

class DummyResponse:
    status = 200
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        return json.dumps(self.payload).encode("utf-8")


class GoogleTTSContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.output = self.dir / "voice.wav"
    def tearDown(self):
        self.tmp.cleanup()

    def test_default_cast_distinct_and_fenrir_default_remains_kokoro(self):
        self.assertEqual(DEFAULT_KOKORO_CAST["MC"], "am_fenrir")
        self.assertEqual(DEFAULT_GOOGLE_CAST["MC"], "Gacrux")
        self.assertEqual(len(set(DEFAULT_GOOGLE_CAST.values())), 5)
        self.assertEqual(len(set(DEFAULT_KOKORO_CAST.values())), 5)

    def test_key_validation_does_not_generate_audio(self):
        requests = []
        def opener(req, timeout=12):
            requests.append(req)
            return DummyResponse({"models": [{"name": "models/gemini-2.5-flash-preview-tts"}]})
        ok, reason = validate_key(FAKE_TEST_KEY, opener=opener)
        self.assertTrue(ok, reason)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].method, "GET")
        self.assertNotIn(FAKE_TEST_KEY, requests[0].full_url)
        self.assertIn("/models?pageSize=1", requests[0].full_url)

    def test_invalid_key_rejected_without_network(self):
        attempts=[]
        ok,reason=validate_key("replace-me",opener=lambda *a,**kw:attempts.append(a))
        self.assertFalse(ok)
        self.assertEqual(attempts,[])

    def test_key_not_configured_no_network_call(self):
        with patch("ashentoons.gemini_tts._load_key",return_value=None):
            result=synthesize_google("Testing voice",self.output)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(self.output.exists())

    def test_true_google_response_becomes_valid_wav(self):
        sent=[]
        def opener(req,timeout=65):
            sent.append(req)
            return DummyResponse(PCM_JSON)
        result=synthesize_google("This engineer is absolutely cooked!",self.output,
                                 voice="Gacrux",api_key=FAKE_TEST_KEY,opener=opener)
        self.assertEqual(result["status"],"PASS",result)
        self.assertFalse(result["reused"])
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0].get_header("X-goog-api-key"),FAKE_TEST_KEY)
        self.assertNotIn(FAKE_TEST_KEY,sent[0].full_url)
        self.assertEqual(json.loads(sent[0].data)["generationConfig"]["speechConfig"]
                         ["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"],"Gacrux")
        self.assertEqual(probe_wave(self.output)["status"],"PASS")
        with wave.open(str(self.output),"rb") as f:
            self.assertEqual(f.getframerate(),24000)
            self.assertEqual(f.getnchannels(),1)
            self.assertEqual(f.getsampwidth(),2)

    def test_verified_cached_output_causes_no_second_api_request(self):
        def opener(req,timeout=65):
            return DummyResponse(PCM_JSON)
        first=synthesize_google("Test scene",self.output,api_key=FAKE_TEST_KEY,opener=opener)
        self.assertEqual(first["status"],"PASS")
        def fail(*a,**kw):
            raise AssertionError("A valid cached WAV must not make a network request")
        second=synthesize_google("Test scene",self.output,api_key=FAKE_TEST_KEY,opener=fail)
        self.assertEqual(second["status"],"PASS")
        self.assertTrue(second["reused"])

    def test_corrupt_existing_output_not_replaced(self):
        self.output.write_bytes(b"corrupt old file")
        result=synthesize_google("Testing",self.output,api_key=FAKE_TEST_KEY,
                                 opener=lambda *a,**kw:DummyResponse(PCM_JSON))
        self.assertEqual(result["status"],"FAIL")
        self.assertEqual(self.output.read_bytes(),b"corrupt old file")

    def test_http_429_retries_with_bound_then_success(self):
        attempts=[]
        def opener(req,timeout=65):
            attempts.append(1)
            if len(attempts)==1:
                raise urllib.error.HTTPError(req.full_url,429,"busy",{},None)
            return DummyResponse(PCM_JSON)
        pauses=[]
        result=synthesize_google("Try again",self.output,api_key=FAKE_TEST_KEY,
                                 opener=opener,sleep=pauses.append)
        self.assertEqual(result["status"],"PASS",result)
        self.assertEqual(len(attempts),2)
        self.assertEqual(len(pauses),1)

    def test_google_unauthorized_fail_fast_without_key_leak(self):
        calls=[]
        def opener(req,timeout=65):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url,403,"Forbidden",{},None)
        r=synthesize_google("Bad permission",self.output,
                            api_key=FAKE_TEST_KEY,opener=opener)
        self.assertEqual(r["status"],"FAIL")
        self.assertEqual(calls,[1])
        self.assertNotIn(FAKE_TEST_KEY,json.dumps(r))

    def test_missing_audio_response_rejected(self):
        result=synthesize_google("Test scene",self.output,
                                api_key=FAKE_TEST_KEY,
                                opener=lambda *a,**kw:DummyResponse({"candidates":[]}))
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(self.output.exists())

    def test_overlong_line_rejected_without_network(self):
        result=synthesize_google("X"*401,self.output,
                                api_key=FAKE_TEST_KEY,
                                opener=lambda *a,**kw:self.fail("Should not call"))
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(self.output.exists())

    def test_voice_and_model_allowlists(self):
        for voice,model in [("unknown",GOOGLE_MODEL),("Gacrux","unknown")]:
            result=synthesize_google("Test",self.output,voice=voice,model=model,
                                    api_key=FAKE_TEST_KEY)
            self.assertEqual(result["status"],"FAIL")

    def test_cache_is_derived_from_model_voice_style_and_line(self):
        a=line_cache_path(self.dir,"Hello","Gacrux","narrator")
        b=line_cache_path(self.dir,"Hello","Puck","narrator")
        c=line_cache_path(self.dir,"Hello","Gacrux","shouting")
        self.assertEqual(len({a.name,b.name,c.name}),3)

    def test_unsupported_sampling_rate_rejected(self):
        changed=json.loads(json.dumps(PCM_JSON))
        changed["candidates"][0]["content"]["parts"][0]["inlineData"]["mimeType"]="audio/L16;rate=16000"
        result=synthesize_google("Test",self.output,api_key=FAKE_TEST_KEY,
                                opener=lambda *a,**kw:DummyResponse(changed))
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(self.output.exists())


if __name__=="__main__":
    unittest.main()
