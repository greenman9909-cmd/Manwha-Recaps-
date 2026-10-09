import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ashentoons.assemble import assemble

class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.a=self.root/'a.mp4'
        self.b=self.root/'b.mp4'
        self.a.write_bytes(b'a')
        self.b.write_bytes(b'b')
        self.out=self.root/'final.mp4'
    def tearDown(self): self.temp.cleanup()
    def test_no_clips(self):
        self.assertEqual(assemble([],self.out)['status'],'FAIL')
    def test_missing_clip(self):
        self.assertEqual(assemble([self.root/'missing.mp4'],self.out)['status'],'FAIL')
    def test_output_overwrites_input(self):
        self.assertEqual(assemble([self.a],self.a)['status'],'FAIL')
    def test_bad_extension(self):
        self.assertEqual(assemble([self.a],self.root/'run.sh')['status'],'FAIL')
    def test_probe_failure(self):
        with patch('ashentoons.assemble.probe_media',return_value={'status':'FAIL'}):
            self.assertEqual(assemble([self.a],self.out)['status'],'FAIL')
    def test_mismatched_dimensions(self):
        def probe(p):
            return {'status':'PASS','duration':3,'video_codec':'h264','audio_codec':'aac',
                    'width':1280 if p==self.a else 1920,'height':720}
        with patch('ashentoons.assemble.probe_media',side_effect=probe):
            self.assertEqual(assemble([self.a,self.b],self.out)['status'],'FAIL')
