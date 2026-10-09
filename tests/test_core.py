import tempfile
import unittest
from pathlib import Path
from ashentoons.core import validate, certify, file_hash

class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'panel.png').write_bytes(b'authorized-fixture-panel')
        self.manifest = dict(source_authorized=True,subtitles=False,generated_visuals=False,voices={'MC':'voice-unique','NARRATOR':'voice-narrator'},clips=[dict(panel='panel.png',panel_sha256=file_hash(self.root/'panel.png'),speaker='MC',voice='voice-unique',event_id='evt-1',narration='An event happens.',start=0,end=3)])
    def tearDown(self): self.temp.cleanup()
    def test_valid_manifest(self): self.assertEqual(validate(self.manifest,self.root)['status'],'PASS')
    def test_swapped_voice(self):
        self.manifest['clips'][0]['voice']='voice-narrator'
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_voice_collision(self):
        self.manifest['voices']['NARRATOR']='voice-unique'
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_panel_tampering(self):
        (self.root/'panel.png').write_bytes(b'wrong panel')
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_path_traversal(self):
        self.manifest['clips'][0]['panel']='../secrets.txt'
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_missing_grounding(self):
        del self.manifest['clips'][0]['event_id']
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_subtitles_rejected(self):
        self.manifest['subtitles']=True
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_generated_visuals_rejected(self):
        self.manifest['generated_visuals']=True
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_overlap_rejected(self):
        self.manifest['clips'].append({**self.manifest['clips'][0],'start':2,'end':4})
        self.assertEqual(validate(self.manifest,self.root)['status'],'FAIL')
    def test_no_auto_certification(self):
        (self.root/'render.mp4').write_bytes(b'not-real-mp4')
        self.assertFalse(certify(self.manifest,self.root,self.root/'render.mp4')['release_allowed'])

if __name__ == '__main__': unittest.main()
