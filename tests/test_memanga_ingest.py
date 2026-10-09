"""MeManga local-source handoff: page order, integrity and non-destructive import."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ashentoons.cli import main
from ashentoons.core import file_hash
from ashentoons.memanga_ingest import ingest_memanga_chapter


class MeMangaIngestTests(unittest.TestCase):
    def setUp(self):
        self.working = tempfile.TemporaryDirectory()
        self.base = Path(self.working.name)
        self.root = self.base / "AshenToons"
        self.root.mkdir()
        self.incoming = self.base / "MeManga Downloads" / "The Wrong Way to Use Healing Magic" / "Chapter 1"
        self.incoming.mkdir(parents=True)

    def tearDown(self):
        self.working.cleanup()

    def image(self, name, *, color="navy", size=(400, 600)):
        path = self.incoming / name
        Image.new("RGB", size, color).save(path)
        return path

    def ingest(self, *, chapter=1, series_id="healing-magic", direction="rtl"):
        return ingest_memanga_chapter(
            self.root, self.incoming, series_id, chapter, direction)

    def test_lossless_natural_page_order_and_rtl_metadata(self):
        source = [
            self.image("10.webp", color="green"),
            self.image("2.webp", color="red"),
            self.image("1.webp", color="blue"),
        ]
        before = {f.name: file_hash(f) for f in source}
        result = self.ingest()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["pages_imported"], 3)
        self.assertFalse(result["ready_to_publish"])
        self.assertFalse(result["reused"])
        ledger = json.loads(Path(result["source_manifest"]).read_text("utf-8"))
        self.assertEqual(ledger["reading_direction"], "rtl")
        self.assertEqual(ledger["page_sequence"], "natural filename order; do not reverse manga pages")
        self.assertEqual([p["original_filename"] for p in ledger["pages"]],
                         ["1.webp", "2.webp", "10.webp"])
        self.assertEqual([p["page_number"] for p in ledger["pages"]], [1, 2, 3])
        self.assertEqual(
            [p["panel"] for p in ledger["pages"]],
            ["sources/healing-magic/ch001/page-0001.webp",
             "sources/healing-magic/ch001/page-0002.webp",
             "sources/healing-magic/ch001/page-0003.webp"])
        self.assertEqual([p["sha256"] for p in ledger["pages"]],
                         [before["1.webp"], before["2.webp"], before["10.webp"]])
        self.assertTrue(ledger["source_authorized"])
        self.assertFalse(ledger["external_license_verified"])
        for file in source:
            self.assertEqual(file_hash(file), before[file.name], "MeManga originals must remain unchanged")

    def test_import_is_idempotent_with_exact_same_files(self):
        self.image("001.png")
        first = self.ingest()
        second = self.ingest()
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(second["status"], "PASS")
        self.assertTrue(second["reused"])
        self.assertEqual(second["pages_imported"], 1)

    def test_changes_to_originals_do_not_overwrite_imported_pages(self):
        page = self.image("001.png")
        first = self.ingest()
        self.assertEqual(first["status"], "PASS")
        saved = self.root / "sources/healing-magic/ch001/page-0001.png"
        old_hash = file_hash(saved)
        Image.new("RGB", (400, 600), "orange").save(page)
        second = self.ingest()
        self.assertEqual(second["status"], "FAIL", second)
        self.assertEqual(file_hash(saved), old_hash)

    def test_changed_saved_copy_is_detected_not_repaired_silently(self):
        self.image("001.png")
        result = self.ingest()
        self.assertEqual(result["status"], "PASS")
        output = self.root / "sources/healing-magic/ch001/page-0001.png"
        output.write_bytes(b"corrupt data")
        second = self.ingest()
        self.assertEqual(second["status"], "FAIL")
        self.assertEqual(output.read_bytes(), b"corrupt data")

    def test_fake_jpeg_rejected_before_copying_any_page(self):
        self.image("1.webp")
        (self.incoming / "2.jpg").write_bytes(b"not a genuine jpg")
        result = self.ingest()
        self.assertEqual(result["status"], "FAIL", result)
        self.assertFalse((self.root / "sources/healing-magic/ch001").exists())
        self.assertFalse((self.root / "manifests/healing-magic/chapter-001-source.json").exists())

    def test_no_images_rejected(self):
        (self.incoming / "metadata.json").write_text('{"title":"test"}')
        self.assertEqual(self.ingest()["status"], "FAIL")
        self.assertFalse((self.root / "sources").exists())

    def test_metadata_sidecars_ignored_not_copied(self):
        self.image("001.webp")
        (self.incoming / "cover.txt").write_text("Never copy unrelated files.")
        report = self.ingest()
        self.assertEqual(report["status"], "PASS")
        dest = Path(report["source_folder"])
        self.assertEqual([p.name for p in dest.iterdir()], ["page-0001.webp"])

    def test_invalid_series_slug_rejected(self):
        self.image("001.png")
        for series in ("../../private", "A B", ".repo", "", "a/b", "a\\b", "x" * 70):
            with self.subTest(series=series):
                self.assertEqual(self.ingest(series_id=series)["status"], "FAIL")
        self.assertFalse((self.root / "sources").exists())

    def test_invalid_chapter_numbers_rejected(self):
        self.image("001.jpg")
        for value in (0, -1, 100001, True, 3.1, "3"):
            with self.subTest(value=value):
                self.assertEqual(self.ingest(chapter=value)["status"], "FAIL")

    def test_reading_direction_does_not_reverse_page_order(self):
        self.image("010.jpg")
        self.image("001.jpg")
        result = self.ingest(direction="ltr")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["reading_direction"], "ltr")
        ledger = json.loads(Path(result["source_manifest"]).read_text("utf-8"))
        self.assertEqual([p["original_filename"] for p in ledger["pages"]],
                         ["001.jpg", "010.jpg"])

    def test_conflicting_existing_chapter_folder_left_untouched(self):
        self.image("001.png")
        dest = self.root / "sources/healing-magic/ch001"
        dest.mkdir(parents=True)
        (dest / "my-original.png").write_bytes(b"do not touch")
        report = self.ingest()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual((dest / "my-original.png").read_bytes(), b"do not touch")

    def test_same_source_inside_workspace_source_folder_rejected(self):
        dest = self.root / "sources/healing-magic/ch002"
        dest.mkdir(parents=True)
        Image.new("RGB", (400, 600), "red").save(dest / "0001.jpg")
        self.assertEqual(ingest_memanga_chapter(
            self.root, dest, "healing-magic", 1)["status"], "FAIL")

    def test_cli_import_generates_provenance(self):
        self.image("001.png")
        status = main(["ingest-memanga", str(self.incoming),
                       "--source-root", str(self.root),
                       "--series-id", "healing-magic",
                       "--chapter", "2", "--reading-direction", "rtl"])
        self.assertEqual(status, 0)
        self.assertTrue((self.root / "manifests/healing-magic/chapter-002-source.json").is_file())

    def test_malformed_input_not_a_directory_rejected(self):
        bad = self.base / "not-a-chapter"
        bad.write_text("bad")
        self.assertEqual(ingest_memanga_chapter(
            self.root, bad, "healing-magic", 1)["status"], "FAIL")

    def test_symlink_original_rejected_if_supported(self):
        file = self.image("001.png")
        linked = self.incoming / "002.png"
        try:
            linked.symlink_to(file)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks require additional Windows privileges")
        result = self.ingest()
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse((self.root / "sources").exists())


if __name__ == "__main__":
    unittest.main()
