"""Extract actual rendered frames for phone-friendly per-part editorial review.

The JPEGs and index JSON are review artifacts. They NEVER become subtitles
or imply panel/narration semantic correctness.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

from .media import probe_media
from .production import plan_parts
from .storyboard import audit_storyboard


def extract_review_frames(manifest: dict, source_root: Path,
                          part_video: Path, part_number: int,
                          output_dir: Path, target_seconds: float = 240,
                          max_seconds: float = 300) -> dict:
    plan = plan_parts(manifest, source_root, target_seconds, max_seconds)
    if plan["status"] != "PASS":
        return plan
    evidence = audit_storyboard(manifest)
    if evidence["status"] != "PASS":
        return evidence
    if type(part_number) is not int or not 1 <= part_number <= len(plan["parts"]):
        return {"status": "FAIL", "errors": ["part number out of range"]}
    if not isinstance(part_video, Path) or part_video.is_symlink():
        return {"status": "FAIL", "errors": ["invalid part video"]}
    meta = probe_media(part_video)
    if meta["status"] != "PASS":
        return {"status": "FAIL", "errors": ["part MP4 failed stream preflight"]}
    part = plan["parts"][part_number - 1]
    expected = sum(
        manifest["clips"][i]["end"] - manifest["clips"][i]["start"]
        for i in part["clip_indices"])
    if abs(meta["duration"] - expected) > max(0.6, expected * 0.005):
        return {"status": "FAIL", "errors": ["review video does not match planned part duration"]}
    if not isinstance(output_dir, Path) or output_dir.is_symlink():
        return {"status": "FAIL", "errors": ["unsafe review output directory"]}
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return {"status": "FAIL", "errors": ["review directory unavailable"]}
    screenshots = []
    cumulative = 0.0
    for clip_index in part["clip_indices"]:
        clip = manifest["clips"][clip_index]
        duration = clip["end"] - clip["start"]
        midpoint = cumulative + duration * 0.5
        cumulative += duration
        filename = f"shot-{clip_index:05d}.jpg"
        destination = output_dir / filename
        fd, name = tempfile.mkstemp(
            prefix=".ashentoons-frame-", suffix=".jpg", dir=output_dir)
        os.close(fd)
        tmp = Path(name)
        try:
            result = subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{midpoint:.3f}", "-i", str(part_video),
                 "-frames:v", "1", "-q:v", "3", "-y", str(tmp)],
                capture_output=True, timeout=90, check=False)
            if result.returncode or not tmp.is_file() or tmp.stat().st_size == 0:
                return {"status": "FAIL", "errors": [f"clip[{clip_index}]: frame extraction failed"],
                        "frames_extracted": len(screenshots)}
            os.replace(tmp, destination)
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "FAIL", "errors": [f"clip[{clip_index}]: extraction timed out/failed"]}
        finally:
            tmp.unlink(missing_ok=True)
        screenshots.append({
            "clip_index": clip_index, "image": filename,
            "panel": clip["panel"], "chapter": clip["chapter"],
            "narration": clip["narration"],
            "panel_summary": clip["panel_summary"],
            "match_reason": clip["match_reason"],
            "image_matches_narration": None,
        })
    index_path = output_dir / "review-index.json"
    if index_path.is_symlink():
        return {"status": "FAIL", "errors": ["review index cannot be a symlink"]}
    fd, name = tempfile.mkstemp(
        prefix=".ashentoons-review-", suffix=".json", dir=output_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({
                "status": "PENDING_HUMAN_REVIEW",
                "part": part_number, "part_video": str(part_video),
                "frames": screenshots, "approved_for_publication": False,
                "note": "Inspect JPEG frames against real narration and original panels",
            }, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(name, index_path)
    except OSError:
        return {"status": "FAIL", "errors": ["could not write frame index"]}
    finally:
        Path(name).unlink(missing_ok=True)
    return {"status": "PASS", "index": str(index_path),
            "frames_extracted": len(screenshots),
            "approved_for_publication": False}
