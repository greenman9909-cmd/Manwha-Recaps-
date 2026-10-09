import copy
import math
import tempfile
import unittest
from pathlib import Path
from ashentoons.core import file_hash, validate

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'panel.png').write_bytes(b'fixture')
        self.m = {'subtitles':False,'generated_visuals':False,'source_authorized':True,
                  'voices':{'MC':'a','NARRATOR':'b'},'clips':[{'panel':'panel.png',
                  'panel_sha256':file_hash(self.root/'panel.png'),'speaker':'MC',
                  'voice':'a','event_id':'e1','narration':'Story.', 'start':0,'end':2}]}
    def tearDown(self): self.temp.cleanup()
    def fail_case(self, mutate):
        m=copy.deepcopy(self.m); mutate(m)
        self.assertEqual(validate(m,self.root)['status'],'FAIL')
    def test_bad_manifest_types(self):
        for v in (None,[], 'bad'):
            self.assertEqual(validate(v,self.root)['status'],'FAIL')
    def test_bad_voice_types(self):
        for v in (None,[],{'MC':[]},{'MC':'a','NARRATOR':'a'}):
            self.fail_case(lambda m: m.update(voices=v))
    def test_bad_clip_types(self):
        for v in (None,{},[None]):
            self.fail_case(lambda m: m.update(clips=v))
    def test_nan_inf_and_boolean_timing(self):
        for v in (math.nan,math.inf,-math.inf,True):
            self.fail_case(lambda m: m['clips'][0].update(end=v))
    def test_backslash_traversal(self):
        self.fail_case(lambda m: m['clips'][0].update(panel='..\\secret.png'))
    def test_absolute_path(self):
        self.fail_case(lambda m: m['clips'][0].update(panel=str(self.root/'panel.png')))
    def test_bad_hash(self):
        self.fail_case(lambda m: m['clips'][0].update(panel_sha256='not-a-hash'))
    def test_empty_narration(self):
        self.fail_case(lambda m: m['clips'][0].update(narration='  '))
    def test_duplicate_event(self):
        def mutate(m):
            second=copy.deepcopy(m['clips'][0]);second.update(start=2,end=4)
            m['clips'].append(second)
        self.fail_case(mutate)
    def test_duplicate_event_explicit_continuation(self):
        second=copy.deepcopy(self.m['clips'][0]);second.update(start=2,end=4,event_continuation=True)
        self.m['clips'].append(second)
        self.assertEqual(validate(self.m,self.root)['status'],'PASS')
    def test_symlink_escape(self):
        outside=Path(self.temp.name).parent/'ashentoons-outside-test.txt'
        try:
            outside.write_bytes(b'outside')
            (self.root/'escape.png').symlink_to(outside)
            self.fail_case(lambda m: m['clips'][0].update(panel='escape.png',panel_sha256=file_hash(outside)))
        finally:
            outside.unlink(missing_ok=True)
    def test_authorization_must_be_boolean_true(self):
        self.fail_case(lambda m: m.update(source_authorized='yes'))
