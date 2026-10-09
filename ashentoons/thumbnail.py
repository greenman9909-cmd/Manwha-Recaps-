"""Create a lightweight 1280x720 JPG thumbnail from an authorized source panel.

Only crops/color grading existing pixels and places a human-written headline.
No AI-generated illustration, face replacement, or narration subtitles.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from .core import _safe_source, audit_source_image, file_hash


def make_thumbnail(root: Path, panel: str, expected_sha256: str,
                   output: Path, headline: str, focus_x: float = 0.5,
                   focus_y: float = 0.4) -> dict:
    if (not isinstance(headline, str) or not 4 <= len(headline.strip()) <= 60
            or any(ord(c) < 32 and c not in "\t" for c in headline)):
        return {"status": "FAIL", "errors": ["headline must be 4–60 printable characters"]}
    if (type(focus_x) not in (float, int) or type(focus_y) not in (float, int)
            or not 0 <= focus_x <= 1 or not 0 <= focus_y <= 1):
        return {"status": "FAIL", "errors": ["invalid crop focus coordinates"]}
    if not isinstance(output, Path) or output.suffix.lower() not in (".jpg", ".jpeg"):
        return {"status": "FAIL", "errors": ["output must be JPEG"]}
    if output.is_symlink() or output.exists():
        return {"status": "FAIL", "errors": ["output exists or is a symlink; choose a new thumbnail name"]}
    if audit_source_image(root, panel, expected_sha256)["status"] != "PASS":
        return {"status": "FAIL", "errors": ["panel source/hash invalid"]}
    source = _safe_source(root, panel)
    if source is None:
        return {"status": "FAIL", "errors": ["panel path unsafe"]}
    try:
        from PIL import Image, ImageOps, ImageDraw, ImageFont
    except ImportError:
        return {"status": "FAIL", "errors": ["Pillow missing: pip install -e '.[images]'"]}
    fd = None
    tmp = None
    try:
        Image.MAX_IMAGE_PIXELS = 80_000_000
        with Image.open(source) as raw:
            raw.load()
            canvas = ImageOps.fit(
                raw.convert("RGB"), (1280, 720),
                method=Image.Resampling.LANCZOS,
                centering=(focus_x, focus_y))
        # Slight bottom darkening ensures legible contrast without altering
        # identities or synthesizing any new subject matter.
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        overlay = ImageDraw.Draw(layer)
        for y in range(350, 720):
            opacity = int(190 * (y - 350) / 370)
            overlay.line((0, y, 1279, y), fill=(0, 0, 0, opacity))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), layer)
        draw = ImageDraw.Draw(canvas)

        def get_font(size):
            try:
                return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
            except OSError:
                return ImageFont.load_default(size=size)

        words = headline.upper().split()
        best = None
        for size in range(84, 35, -4):
            font = get_font(size)
            lines, line = [], ""
            for word in words:
                candidate = (line + " " + word).strip()
                if draw.textbbox((0, 0), candidate, font=font, stroke_width=5)[2] <= 1150:
                    line = candidate
                else:
                    if line:
                        lines.append(line)
                    line = word
            if line:
                lines.append(line)
            if len(lines) <= 2 and all(
                    draw.textbbox((0, 0), l, font=font, stroke_width=5)[2] <= 1150
                    for l in lines):
                best = (font, lines, size)
                break
        if best is None:
            return {"status": "FAIL", "errors": ["headline too long for 2 legible lines"]}
        font, lines, size = best
        start_y = 700 - len(lines) * (size + 14)
        for line_index, line in enumerate(lines):
            draw.text(
                (640, start_y + line_index * (size + 14)),
                line, anchor="mt", font=font,
                fill=(255, 255, 245, 255),
                stroke_width=6, stroke_fill=(14, 10, 9, 255),
            )
        brand = get_font(30)
        draw.text(
            (35, 28), "ASHENTOONS", font=brand, fill=(255, 255, 255, 255),
            stroke_width=3, stroke_fill=(0, 0, 0, 255))
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".ashentoons-thumb-", suffix=".jpg",
                                   dir=output.parent)
        os.close(fd)
        fd = None
        tmp = Path(name)
        canvas.convert("RGB").save(tmp, "JPEG", quality=88, optimize=True)
        if tmp.stat().st_size > 2_000_000:
            canvas.convert("RGB").save(tmp, "JPEG", quality=75, optimize=True)
        if tmp.stat().st_size > 2_000_000:
            return {"status": "FAIL", "errors": ["thumbnail exceeds 2 MB"]}
        if output.exists():
            return {"status": "FAIL", "errors": ["thumbnail output appeared while generating"]}
        os.replace(tmp, output)
        return {
            "status": "PASS", "output": str(output),
            "sha256": file_hash(output), "width": 1280, "height": 720,
            "note": "Thumbnail draft from supplied panel; framing/title and rights require user review",
        }
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return {"status": "FAIL", "errors": [type(exc).__name__ + ": " + str(exc)[:170]]}
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None:
            tmp.unlink(missing_ok=True)
