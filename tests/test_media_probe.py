import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from ashentoons.media import probe_media

class ProbeTests(unittest.TestCase):
    def run_probe(self, payload, returncode=0):
        with patch("pathlib.Path.is_file", return_value=True), patch("subprocess.run", return_value=Mock(returncode=returncode,stdout=payload,stderr="")):
            return probe_media(Path("video.mp4"))
    def test_good(self):
        x='{"format":{"duration":"60"},"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080},{"codec_type":"audio","codec_name":"aac"}]}'
        self.assertEqual(self.run_probe(x)["status"],"PASS")
    def test_missing_audio(self):
        x='{"format":{"duration":"60"},"streams":[{"codec_type":"video","width":1920,"height":1080}]}'
        self.assertEqual(self.run_probe(x)["status"],"FAIL")
    def test_subtitles(self):
        x='{"format":{"duration":"60"},"streams":[{"codec_type":"video","width":1920,"height":1080},{"codec_type":"audio"},{"codec_type":"subtitle"}]}'
        self.assertEqual(self.run_probe(x)["status"],"FAIL")
    def test_corrupt_json(self):
        self.assertEqual(self.run_probe("{")["status"],"FAIL")
    def test_ffprobe_failure(self):
        self.assertEqual(self.run_probe("{}",1)["status"],"FAIL")
    def test_missing_file(self):
        self.assertEqual(probe_media(Path("does-not-exist-ashentoons.mp4"))["status"],"FAIL")
    def test_timeout(self):
        import subprocess
        with patch("pathlib.Path.is_file", return_value=True), patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe",1)):
            self.assertEqual(probe_media(Path("x.mp4"))["status"],"FAIL")
