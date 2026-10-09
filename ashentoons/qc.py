"""Independently decode audio and video to detect technical corruption.

No automated decoder can prove correct character identity, fair use, permission
to publish, or alignment between narration and illustrated story events.
"""
from __future__ import annotations

import math
from pathlib import Path
import subprocess

from .media import probe_media


def decode_check(path: Path, expected_duration: float | None = None,
                 timeout: int = 1800) -> dict:
    """Decode *both* elementary streams, fail on errors, never modify video."""
    preflight = probe_media(path)
    if preflight.get("status") != "PASS":
        return {"status": "FAIL", "errors": ["stream preflight rejected media"],
                "detail": preflight}
    duration = preflight["duration"]
    if expected_duration is not None:
        if (type(expected_duration) not in (int, float)
                or not math.isfinite(expected_duration) or expected_duration <= 0):
            return {"status": "FAIL", "errors": ["invalid expected duration"]}
        if abs(duration - expected_duration) > max(0.6, expected_duration * 0.005):
            return {"status": "FAIL", "errors": ["duration mismatch"],
                    "actual": duration, "expected": expected_duration}
    if type(timeout) is not int or timeout < 1 or timeout > 14400:
        return {"status": "FAIL", "errors": ["invalid decode timeout"]}
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-xerror", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
             "-f", "null", "-"],
            capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "FAIL", "errors": [type(exc).__name__]}
    if proc.returncode:
        return {"status": "FAIL", "errors": ["audio/video decode failure"],
                "detail": proc.stderr.decode("utf-8", "replace")[-500:]}
    return {
        "status": "PASS", "duration": duration,
        "width": preflight["width"], "height": preflight["height"],
        "subtitles_streams_present": False,
        "burned_subtitles_verified_absent": False,
        "semantic_alignment_verified": False,
        "note": "Technical decode only; an actual visual/audio review is mandatory",
    }
