"""Import MeManga's already-downloaded chapter pages without modifying originals.

The adapter deliberately consumes a LOCAL chapter directory; downloading is
MeManga's job. Natural page order is retained, with original bytes and hashes.
No website request, transcoding, reverse order or semantic-accuracy claim.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .core import file_hash

_SERIES = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_PAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_PAGES = 600
_MAX_IMAGE_SIZE = 50 * 1024 * 1024
_MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024


def _ordered_key(path: Path):
    """Sort 1, 2, 10 numerically; retain original filenames for traceability."""
    return tuple(
        (0, int(piece)) if piece.isdigit() else (1, piece.casefold())
        for piece in re.split(r"(\d+)", path.name)
    )


def _fail(reason: str) -> dict:
    return {
        "status": "FAIL",
        "errors": [reason],
        "ready_to_publish": False,
    }


def _verify_image(path: Path) -> tuple[int, int]:
    """Actually decode a page rather than trusting its extension or signature."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError("Pillow is required: pip install -e '.[images]'") from exc
    with Image.open(path) as image:
        width, height = image.size
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("unsupported source image encoding")
        if width < 150 or height < 150 or width * height > 60_000_000:
            raise ValueError("unsupported page size")
        image.load()
    return width, height


def _verify_existing(ledger: Path, pages: list[dict],
                     target_dir: Path, source_root: Path) -> dict:
    """A repeated import is allowed only when source and output match exactly."""
    try:
        with ledger.open("r", encoding="utf-8") as stream:
            record = json.load(stream)
    except (ValueError, OSError) as exc:
        return _fail("existing chapter report is unreadable: " + str(exc)[:140])
    found = record.get("pages") if isinstance(record, dict) else None
    if not isinstance(found, list) or len(found) != len(pages):
        return _fail("existing chapter has different number of pages")
    try:
        if record.get("series_id") != target_dir.parent.name:
            return _fail("existing chapter belongs to another series")
        for expected, saved in zip(pages, found):
            if not isinstance(saved, dict):
                return _fail("invalid saved page record")
            destination = target_dir / expected["stored_filename"]
            if (saved.get("page_number") != expected["page_number"]
                    or saved.get("original_filename") != expected["original_filename"]
                    or saved.get("sha256") != expected["sha256"]
                    or saved.get("panel") != destination.relative_to(source_root).as_posix()
                    or destination.is_symlink() or not destination.is_file()
                    or file_hash(destination) != expected["sha256"]):
                return _fail("existing chapter differs; refusing to replace original output")
    except (OSError, ValueError):
        return _fail("existing output could not be verified")
    return {
        "status": "PASS", "reused": True,
        "pages_imported": len(pages),
        "source_manifest": str(ledger),
        "source_folder": str(target_dir),
        "ready_to_publish": False,
        "note": "Hash-verified local pages; semantic story review still required",
    }


def ingest_memanga_chapter(source_root: Path, chapter_folder: Path,
                           series_id: str, chapter: int,
                           reading_direction: str = "rtl") -> dict:
    """Safely copy a locally downloaded MeManga chapter to AshenToons.

    Page numbers are ordered by source file names, not by inferred speech bubble
    direction. For Japanese manga the editorial reading direction is RTL, but
    pages themselves always remain in chapter order.
    """
    if (not isinstance(source_root, Path) or not isinstance(chapter_folder, Path)
            or not isinstance(series_id, str) or not _SERIES.fullmatch(series_id)
            or type(chapter) is not int or not 1 <= chapter <= 100000
            or reading_direction not in ("rtl", "ltr")):
        return _fail("invalid workspace, source path, series slug, chapter or reading direction")
    if source_root.is_symlink() or chapter_folder.is_symlink():
        return _fail("workspace/chapter symlinks are forbidden")
    try:
        root = source_root.resolve(strict=True)
        incoming = chapter_folder.resolve(strict=True)
        if (not root.is_dir() or root.parent == root
                or not incoming.is_dir() or incoming == root):
            return _fail("workspace and chapter folders must be existing directories")
        sources_root = root / "sources"
        manifest_root = root / "manifests"
        if sources_root.is_symlink() or manifest_root.is_symlink():
            return _fail("workspace source/manifest symlinks are forbidden")
        dest_dir = sources_root / series_id / f"ch{chapter:03d}"
        report_path = manifest_root / series_id / f"chapter-{chapter:03d}-source.json"
        if (incoming == dest_dir or incoming.is_relative_to(sources_root)
                or dest_dir.parent.is_symlink()
                or report_path.parent.is_symlink()):
            return _fail("input must not be inside the destination sources tree")
        image_files = []
        for item in incoming.iterdir():
            if item.is_symlink():
                return _fail("symlink source encountered")
            if item.is_file() and item.suffix.lower() in _PAGE_SUFFIXES:
                image_files.append(item)
        image_files.sort(key=_ordered_key)
        if not 1 <= len(image_files) <= _MAX_PAGES:
            return _fail("chapter must have between 1 and 600 page images")
        pages = []
        total_size = 0
        for number, image in enumerate(image_files, start=1):
            size = image.stat().st_size
            if size <= 0 or size > _MAX_IMAGE_SIZE:
                return _fail(f"page {number}: empty or oversized source image")
            total_size += size
            if total_size > _MAX_TOTAL_SIZE:
                return _fail("chapter exceeds 2 GiB image limit")
            try:
                width, height = _verify_image(image)
            except (OSError, ValueError, SyntaxError) as exc:
                return _fail(f"page {number}: cannot decode original image: {exc}")
            pages.append({
                "page_number": number,
                "original_filename": image.name,
                "stored_filename": f"page-{number:04d}{image.suffix.lower()}",
                "sha256": file_hash(image),
                "bytes": size,
                "width": width, "height": height,
            })
        if report_path.exists() or report_path.is_symlink():
            if report_path.is_symlink():
                return _fail("existing manifest symlink forbidden")
            return _verify_existing(report_path, pages, dest_dir, root)
        if dest_dir.exists() or dest_dir.is_symlink():
            return _fail("chapter output already exists without a matching import report")
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".chapter-import-", dir=dest_dir.parent))
        try:
            for page, original in zip(pages, image_files):
                candidate = stage_dir / page["stored_filename"]
                with original.open("rb") as infile, candidate.open("xb") as outfile:
                    shutil.copyfileobj(infile, outfile, length=1024 * 1024)
                if file_hash(candidate) != page["sha256"]:
                    return _fail("copied page hash mismatch")
                page["panel"] = (dest_dir / page["stored_filename"]).relative_to(root).as_posix()
            record = {
                "version": 1,
                "series_id": series_id,
                "chapter": chapter,
                "source_type": "local MeManga chapter export",
                "source_folder": str(incoming),
                "reading_direction": reading_direction,
                "page_sequence": "natural filename order; do not reverse manga pages",
                "source_authorized": True,
                "source_authorization_basis": "user-declared for this production",
                "external_license_verified": False,
                "subtitles": False, "generated_visuals": False,
                "editorial_review": "PENDING",
                "pages": pages,
            }
            if dest_dir.exists() or dest_dir.is_symlink():
                return _fail("output directory appeared while importing")
            stage_dir.rename(dest_dir)
            with report_path.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
        return {
            "status": "PASS", "reused": False,
            "pages_imported": len(pages),
            "source_manifest": str(report_path),
            "source_folder": str(dest_dir),
            "reading_direction": reading_direction,
            "ready_to_publish": False,
            "note": "Images imported, hashes and decoding checked; story/text alignment is pending review",
        }
    except (OSError, ValueError) as exc:
        return _fail("chapter import failed: " + str(exc)[:180])


def ingest_memanga_batch(source_root: Path, manga_folder: Path, series_id: str,
                         first_chapter: int, last_chapter: int,
                         reading_direction: str = "rtl") -> dict:
    """Import Chapter 1, Chapter 2, ... directories from one local MeManga title.

    Fail fast and report the exact missing chapter. Previously imported source
    folders remain intact; this is resumable without overwriting pages.
    """
    if (not isinstance(manga_folder, Path) or manga_folder.is_symlink()
            or not isinstance(series_id, str) or not _SERIES.fullmatch(series_id)
            or type(first_chapter) is not int or type(last_chapter) is not int
            or not 1 <= first_chapter <= last_chapter <= 100000
            or last_chapter - first_chapter >= 48
            or reading_direction not in ("rtl", "ltr")):
        return _fail("invalid MeManga batch parameters")
    try:
        if not manga_folder.is_dir() or manga_folder.is_symlink():
            return _fail("MeManga manga folder does not exist")
    except OSError as exc:
        return _fail("cannot read manga folder: " + str(exc)[:140])
    output = []
    for chapter in range(first_chapter, last_chapter + 1):
        input_dir = manga_folder / f"Chapter {chapter}"
        result = ingest_memanga_chapter(
            source_root, input_dir, series_id, chapter, reading_direction)
        output.append({"chapter": chapter, **result})
        if result["status"] != "PASS":
            return {
                "status": "FAIL",
                "errors": [f"chapter {chapter}: " + "; ".join(result.get("errors", []))],
                "completed_chapters": sum(x["status"] == "PASS" for x in output),
                "next_required_chapter": chapter,
                "chapters": output,
                "ready_to_publish": False,
            }
    return {
        "status": "PASS",
        "completed_chapters": len(output),
        "chapters_reused": sum(bool(x.get("reused")) for x in output),
        "pages_imported": sum(x["pages_imported"] for x in output),
        "chapters": output,
        "ready_to_publish": False,
        "note": "Local chapter pages imported; story review and render still pending",
    }
