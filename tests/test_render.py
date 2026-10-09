import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from ashentoons.render import render_clip

class RenderClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'panel.png').write_bytes(b'panel')
        (self.root/'speech.wav').write_bytes(b'audio')
        self.out=self.root/'out.mp4'
    def tearDown(self): self.tmp.cleanup()
    def run_render(self, **kwargs):
        return render_clip(self.root,'panel.png','speech.wav',self.out,4,**kwargs)
    def test_reject_bad_duration(self):
        for value in (-1,0,float('nan'),float('inf'),100,True):
            self.assertEqual(render_clip(self.root,'panel.png','speech.wav',self.out,value)['status'],'FAIL')
    def test_reject_bad_dimensions(self):
        for dims in ((321,720),(1280,719),(100,720),(9999,720),(True,720)):
            self.assertEqual(self.run_render(width=dims[0],height=dims[1])['status'],'FAIL')
    def test_reject_unsafe_panel(self):
        self.assertEqual(render_clip(self.root,'../secret.png','speech.wav',self.out,4)['status'],'FAIL')
    def test_reject_unsafe_audio(self):
        self.assertEqual(render_clip(self.root,'panel.png','../secret.wav',self.out,4)['status'],'FAIL')
    def test_reject_non_mp4(self):
        self.assertEqual(render_clip(self.root,'panel.png','speech.wav',self.root/'out.sh',4)['status'],'FAIL')
    def test_ffmpeg_failure_does_not_publish(self):
        with patch('subprocess.run',return_value=Mock(returncode=1,stderr=b'bad')):
            self.assertEqual(self.run_render()['status'],'FAIL')
            self.assertFalse(self.out.exists())
    def test_timeout_does_not_publish(self):
        import subprocess
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('ffmpeg',1)):
            self.assertEqual(self.run_render()['status'],'FAIL')
            self.assertFalse(self.out.exists())
    def test_success_atomic(self):
        def fake_run(command, **kwargs):
            Path(command[-1]).write_bytes(b'fixture mp4')
            return Mock(returncode=0,stderr=b'')
        with patch('subprocess.run',side_effect=fake_run):
            self.assertEqual(self.run_render()['status'],'PASS')
            self.assertTrue(self.out.exists())
