"""Truthful, offline YouTube metadata draft from supplied episode facts.

Does not upload, infer licensing, scrape competitors, or fabricate chapters.
"""
from __future__ import annotations

from .core import validate


def _timestamp(value: float) -> str:
    seconds = max(0, int(value))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return (f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if hours else f"{minutes:02d}:{seconds:02d}")


def seo_draft(manifest: dict, root, series: str, title: str,
              tags: list[str] | None = None) -> dict:
    checked = validate(manifest, root)
    if checked["status"] != "PASS":
        return {"status": "FAIL", "errors": checked["errors"]}
    if not isinstance(series, str) or not 2 <= len(series.strip()) <= 120:
        return {"status": "FAIL", "errors": ["series name must be 2–120 characters"]}
    if not isinstance(title, str) or not 10 <= len(title.strip()) <= 100:
        return {"status": "FAIL", "errors": ["YouTube title must be 10–100 characters"]}
    if tags is None:
        tags = ["manhwa recap", "English manhwa recap", series.strip(),
                "AshenToons"]
    if (not isinstance(tags, list) or len(tags) > 30
            or any(not isinstance(t, str) or not t.strip() or len(t) > 80 for t in tags)
            or sum(len(t) for t in tags) > 450):
        return {"status": "FAIL", "errors": ["invalid video tags"]}
    # Only report chapter markers supported by the supplied timeline.
    first_by_chapter = {}
    for clip in manifest["clips"]:
        chapter = clip.get("chapter")
        if type(chapter) is int and chapter > 0 and chapter not in first_by_chapter:
            first_by_chapter[chapter] = clip["start"]
    chapters = sorted(first_by_chapter.items(), key=lambda x: x[1])
    # YouTube chapters need >=3 entries, first at zero, each >=10 seconds.
    chapter_lines = []
    if (len(chapters) >= 3 and chapters[0][1] <= 0.5
            and all(b[1] - a[1] >= 10 for a, b in zip(chapters, chapters[1:]))
            and manifest["clips"][-1]["end"] - chapters[-1][1] >= 10):
        chapter_lines = [f"{_timestamp(t)} — Chapter {c}" for c, t in chapters]
    description = [
        f"{series.strip()} — English manhwa recap with original commentary.",
        "",
        "Scenes use supplied source panels; verify reuse permissions before publication.",
        "Edited in short parts by AshenToons. No added subtitles.",
    ]
    if chapter_lines:
        description += ["", "CHAPTERS", *chapter_lines]
    description += ["", "What was the biggest twist? Share your thoughts.",
                    "", "#ManhwaRecap #AshenToons"]
    metadata = {
        "title": title.strip(), "description": "\n".join(description),
        "tags": list(dict.fromkeys(t.strip() for t in tags)),
        "categoryId": "24", "privacyStatus": "private",
        "captions": False,
        "manual_upload_required": True,
        "release_authorized": False,
        "chapters_included": bool(chapter_lines),
        "series": series.strip(),
        "note": "Draft only. Verify factual claims, rights, content and platform settings before publication.",
    }
    return {"status": "PASS", "metadata": metadata}
