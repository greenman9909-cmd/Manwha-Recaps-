"""Audio-first, source-only production in independently reviewable MP4 parts.

This is a deterministic production runner, NOT a semantic review or publication
service. Rights and narration/panel correspondence require independent evidence.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from .assemble import assemble
from .core import _safe_source, file_hash, validate
from .media import probe_media
from .render import render_clip

RENDER_REVISION = "ashentoons-static-panel-v1"


def plan_parts(manifest: dict, root: Path, target_seconds: float = 240,
               max_seconds: float = 300) -> dict:
    """Group timeline clips into <= max_seconds parts without splitting a clip.

    Prefer an existing chapter boundary after target_seconds. The final part
    can be shorter. Gaps > 0.25s are refused to avoid silent missing story.
    """
    report = validate(manifest, root)
    if report["status"] != "PASS":
        return {"status": "FAIL", "errors": report["errors"], "parts": []}
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in
           (target_seconds, max_seconds)) or not (1 <= target_seconds <= max_seconds <= 600):
        return {"status": "FAIL", "errors": ["invalid part duration limits"], "parts": []}
    clips = manifest["clips"]
    previous_end = 0.0
    for i, clip in enumerate(clips):
        seconds = clip["end"] - clip["start"]
        if not 0.1 <= seconds <= 30:
            return {"status": "FAIL", "errors": [f"clip[{i}]: duration must be 0.1–30s"], "parts": []}
        if clip["start"] - previous_end > 0.25:
            return {"status": "FAIL", "errors": [f"clip[{i}]: unexplained timeline gap"], "parts": []}
        previous_end = clip["end"]
    if clips[0]["start"] > 0.25:
        return {"status": "FAIL", "errors": ["timeline must start near zero"], "parts": []}

    groups: list[list[int]] = []
    group: list[int] = []
    for index, clip in enumerate(clips):
        if group:
            first = clips[group[0]]
            elapsed = clip["end"] - first["start"]
            prior_elapsed = clips[group[-1]]["end"] - first["start"]
            changed_chapter = (
                clip.get("chapter") is not None
                and first.get("chapter") is not None
                and clip["chapter"] != clips[group[-1]].get("chapter")
            )
            if elapsed > max_seconds + 1e-6 or (prior_elapsed >= target_seconds and changed_chapter):
                groups.append(group)
                group = []
        group.append(index)
    if group:
        groups.append(group)
    if len(groups) > 2000:
        return {"status": "FAIL", "errors": ["too many parts"], "parts": []}
    parts = [{
        "part": part_id,
        "start": clips[group[0]]["start"],
        "end": clips[group[-1]]["end"],
        "duration": round(clips[group[-1]]["end"] - clips[group[0]]["start"], 3),
        "clip_indices": group,
    } for part_id, group in enumerate(groups, 1)]
    return {"status": "PASS", "parts": parts, "total_clips": len(clips),
            "estimated_duration": clips[-1]["end"], "subtitles": False,
            "note": "Planning only; no automatic claim of panel/narration alignment"}


def probe_audio(path: Path, timeout: int = 30) -> dict:
    """Check real audio duration (not merely a file extension)."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode:
            return {"status": "FAIL", "errors": ["ffprobe rejected narration audio"]}
        seconds = float(json.loads(proc.stdout)["format"]["duration"])
        if not math.isfinite(seconds) or seconds <= 0 or seconds > 30.75:
            raise ValueError("invalid audio duration")
        return {"status": "PASS", "duration": seconds}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError, OverflowError):
        return {"status": "FAIL", "errors": ["unreadable narration audio duration"]}


def _preflight_audio(manifest: dict, root: Path) -> dict:
    errors = []
    durations = []
    for i, clip in enumerate(manifest["clips"]):
        name, expected = clip.get("audio"), clip.get("audio_sha256")
        path = _safe_source(root, name)
        if path is None or path.suffix.lower() not in (".wav", ".mp3", ".m4a", ".flac"):
            errors.append(f"clip[{i}]: missing/unsafe narration audio")
            continue
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            errors.append(f"clip[{i}]: invalid narration SHA-256")
            continue
        try:
            if file_hash(path) != expected:
                errors.append(f"clip[{i}]: narration SHA-256 mismatch")
                continue
        except OSError:
            errors.append(f"clip[{i}]: unreadable narration audio")
            continue
        result = probe_audio(path)
        if result["status"] != "PASS":
            errors.append(f"clip[{i}]: narration audio failed ffprobe")
            continue
        desired = clip["end"] - clip["start"]
        if abs(result["duration"] - desired) > 0.75:
            errors.append(f"clip[{i}]: narration length differs from shot by >0.75s")
        durations.append(result["duration"])
    return {"status": "FAIL" if errors else "PASS", "errors": errors,
            "audio_durations": durations}


def render_parts(manifest: dict, source_root: Path, output_dir: Path,
                 target_seconds: float = 240, max_seconds: float = 300,
                 width: int = 1280, height: int = 720) -> dict:
    """Render only validated local assets, reuse hash-keyed clips, assemble parts.

    Entire manifest and all audio are preflighted before any rendering. A PASS
    is a *technical production result*; no public release permission follows.
    """
    plan = plan_parts(manifest, source_root, target_seconds, max_seconds)
    if plan["status"] != "PASS":
        return plan
    if type(width) is not int or type(height) is not int or not (
            320 <= width <= 3840 and 240 <= height <= 2160 and width % 2 == height % 2 == 0):
        return {"status": "FAIL", "errors": ["invalid output dimensions"]}
    audio_check = _preflight_audio(manifest, source_root)
    if audio_check["status"] != "PASS":
        return audio_check
    if output_dir.is_symlink():
        return {"status": "FAIL", "errors": ["output directory cannot be a symlink"]}
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        clip_dir = output_dir / "clips"
        clip_dir.mkdir(exist_ok=True)
    except OSError:
        return {"status": "FAIL", "errors": ["unable to create output directory"]}
    reports = []
    cache_hits = 0
    for part in plan["parts"]:
        rendered = []
        for index in part["clip_indices"]:
            shot = manifest["clips"][index]
            duration = shot["end"] - shot["start"]
            key_values = [RENDER_REVISION, shot["panel_sha256"],
                          shot["audio_sha256"], f"{duration:.6f}", str(width), str(height)]
            cache_key = sha256("|".join(key_values).encode("utf-8")).hexdigest()[:20]
            clip_path = clip_dir / f"shot-{index:05d}-{cache_key}.mp4"
            cached = False
            if clip_path.is_file() and not clip_path.is_symlink():
                info = probe_media(clip_path)
                cached = (info["status"] == "PASS" and info["width"] == width
                          and info["height"] == height and abs(info["duration"] - duration) <= 0.35)
            if not cached:
                result = render_clip(source_root, shot["panel"], shot["audio"],
                                     clip_path, duration, width, height)
                if result["status"] != "PASS":
                    return {"status": "FAIL", "errors": [f"clip[{index}]: render failed"],
                            "detail": result, "completed_parts": reports}
                info = probe_media(clip_path)
                if (info["status"] != "PASS" or info["width"] != width
                        or info["height"] != height or abs(info["duration"] - duration) > 0.35):
                    return {"status": "FAIL", "errors": [f"clip[{index}]: render output failed probe"],
                            "completed_parts": reports}
            else:
                cache_hits += 1
            rendered.append(clip_path)
        destination = output_dir / f"part-{part['part']:03d}.mp4"
        result = assemble(rendered, destination)
        if result["status"] != "PASS":
            return {"status": "FAIL", "errors": [f"part {part['part']}: assembly failed"],
                    "detail": result, "completed_parts": reports}
        reports.append({"part": part["part"], "path": str(destination),
                        "duration": result["duration"], "sha256": result["sha256"],
                        "clip_indices": part["clip_indices"]})
    return {"status": "PASS", "parts": reports, "clips_reused": cache_hits,
            "subtitles": False, "ready_to_publish": False,
            "requires_independent_semantic_review": True,
            "note": "Rendering is not evidence that spoken events match the panels"}
