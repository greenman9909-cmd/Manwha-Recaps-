import tempfile
import unittest
from pathlib import Path
from ashentoons.core import validate, file_hash, certify

class CrashResistance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'p.png').write_bytes(b'fixture')
        self.m = {'source_authorized': True, 'subtitles': False, 'generated_visuals': False,
                  'voices': {'MC': 'mc'}, 'clips': [{'panel':'p.png',
                  'panel_sha256':file_hash(self.root/'p.png'),'speaker':'MC','voice':'mc',
                  'event_id':'e','narration':'x','start':0,'end':1}]}
    def tearDown(self): self.tmp.cleanup()
    def test_unhashable_speaker_list(self):
        self.m['clips'][0]['speaker']=[]
        self.assertEqual(validate(self.m,self.root)['status'],'FAIL')
    def test_unhashable_speaker_dict(self):
        self.m['clips'][0]['speaker']={}
        self.assertEqual(validate(self.m,self.root)['status'],'FAIL')
    def test_unhashable_voice(self):
        self.m['clips'][0]['voice']=[]
        self.assertEqual(validate(self.m,self.root)['status'],'FAIL')
    def test_missing_root(self):
        self.assertEqual(validate(self.m,self.root/'does-not-exist')['status'],'FAIL')
    def test_certify_stays_closed(self):
        self.assertFalse(certify(self.m,self.root,self.root/'no-video.mp4')['release_allowed'])
