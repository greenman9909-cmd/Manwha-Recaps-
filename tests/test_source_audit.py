import tempfile
import unittest
from pathlib import Path
from ashentoons.core import audit_source_image, file_hash

class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def check(self, name, data):
        p = self.root / name
        p.write_bytes(data)
        return audit_source_image(self.root, name, file_hash(p))
    def test_valid_png_signature(self):
        self.assertEqual(self.check('a.png', b'\x89PNG\r\n\x1a\n' + b'0'*20)['status'], 'PASS')
    def test_fake_png(self):
        self.assertEqual(self.check('a.png', b'not an image')['status'], 'FAIL')
    def test_extension_mismatch(self):
        self.assertEqual(self.check('a.jpg', b'\x89PNG\r\n\x1a\n')['status'], 'FAIL')
    def test_empty(self):
        self.assertEqual(self.check('a.webp', b'')['status'], 'FAIL')
    def test_valid_jpeg_signature(self):
        self.assertEqual(self.check('a.jpeg', b'\xff\xd8\xff' + b'0'*20)['status'], 'PASS')
    def test_valid_webp_signature(self):
        self.assertEqual(self.check('a.webp', b'RIFF' + b'0000WEBP' + b'0'*20)['status'], 'PASS')
    def test_unsafe_path(self):
        self.assertEqual(audit_source_image(self.root, '../secret.png', '0'*64)['status'], 'FAIL')
    def test_wrong_hash(self):
        p = self.root / 'a.png'
        p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0'*20)
        self.assertEqual(audit_source_image(self.root, 'a.png', '0'*64)['status'], 'FAIL')
