"""1,000 deterministic mutation attacks against manifest acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path
from ashentoons.core import validate, file_hash

class ThousandAttacks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'panel.png').write_bytes(b'approved fixture')
        self.good = {
            'subtitles': False, 'generated_visuals': False, 'source_authorized': True,
            'voices': {'MC': 'exclusive-mc', 'NARRATOR': 'narrator'},
            'clips': [{'panel': 'panel.png', 'panel_sha256': file_hash(self.root / 'panel.png'),
                       'speaker': 'MC', 'voice': 'exclusive-mc', 'event_id': 'e1',
                       'narration': 'Source grounded narration', 'start': 0, 'end': 2}]}
    def tearDown(self):
        self.tmp.cleanup()

def attack(case, index):
    clip = case['clips'][0]
    if index == 0:
        clip['panel'] = '../' * (case['_variant'] + 1) + 'private.png'
    elif index == 1:
        clip['panel_sha256'] = f'{case["_variant"]:064x}'
    elif index == 2:
        clip['voice'] = f'swapped-{case["_variant"]}'
    elif index == 3:
        clip['speaker'] = f'impostor-{case["_variant"]}'
    elif index == 4:
        case['voices'][f'fake-{case["_variant"]}'] = 'exclusive-mc'
    elif index == 5:
        clip['start'] = -(case['_variant'] + 1)
    elif index == 6:
        clip['end'] = -(case['_variant'] + 1)
    elif index == 7:
        clip['narration'] = ' ' * (case['_variant'] + 1)
    elif index == 8:
        clip2 = copy.deepcopy(clip)
        clip2.update(start=2, end=4, event_continuation=f'yes-{case["_variant"]}')
        case['clips'].append(clip2)
    elif index == 9:
        clip['event_id'] = f'orphan-{case["_variant"]}'
        clip['event_continuation'] = True
    del case['_variant']

def build_test(family, variant):
    def test(self):
        manifest = copy.deepcopy(self.good)
        manifest['_variant'] = variant
        attack(manifest, family)
        report = validate(manifest, self.root)
        self.assertEqual(report['status'], 'FAIL', report)
        self.assertTrue(report['errors'])
    return test

for family in range(10):
    for variant in range(100):
        setattr(ThousandAttacks, f'test_attack_{family:02d}_{variant:03d}', build_test(family, variant))
