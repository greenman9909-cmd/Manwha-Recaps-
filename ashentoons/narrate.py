"""Turn a grounded source-panel script into a Kokoro-timed manifest.

Audio generation can be expensive. Hash-addressed, source-root-contained WAV
cache prevents recomputation of identical speech lines in later attempts.
All source images require independently supplied expected SHA-256 hashes.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import tempfile

from .core import _safe_source, audit_source_image, file_hash, validate
from .storyboard import audit_storyboard
from .tts import synthesize, VOICE
from .production import probe_audio

CACHE_REVISION = "kokoro82m-puck-en-v1"


def _safe_output_folder(root: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(p in ("", ".", "..") for p in pure.parts):
        return None
    try:
        base = root.resolve(strict=True)
        target = (base / Path(relative)).resolve()
        if not target.is_relative_to(base) or target == base:
            return None
        return target
    except (OSError, RuntimeError, ValueError):
        return None


def narrate_script(script: dict, source_root: Path, output_manifest: Path,
                   audio_subdirectory: str = "narration",
                   speed: float = 1.0) -> dict:
    """Synthesize line-by-line from authorized script; do not release automatically."""
    if not isinstance(script, dict) or script.get("source_authorized") is not True:
        return {"status": "FAIL", "errors": ["explicit source authorization declaration required"]}
    if script.get("subtitles") is not False or script.get("generated_visuals") is not False:
        return {"status": "FAIL", "errors": ["script must explicitly disable subtitles/generated visuals"]}
    if (type(speed) not in (float, int) or not math.isfinite(speed)
            or speed < 0.75 or speed > 1.25):
        return {"status": "FAIL", "errors": ["invalid voice speed"]}
    shots = script.get("clips")
    if not isinstance(shots, list) or not 1 <= len(shots) <= 2000:
        return {"status": "FAIL", "errors": ["1–2000 script clips required"]}
    evidence = audit_storyboard(script)
    if evidence["status"] != "PASS":
        return evidence
    audio_folder = _safe_output_folder(source_root, audio_subdirectory)
    if audio_folder is None:
        return {"status": "FAIL", "errors": ["unsafe narration output directory"]}
    if (not isinstance(output_manifest, Path)
            or output_manifest.suffix.lower() != ".json"
            or output_manifest.is_symlink() or output_manifest.exists()):
        return {"status": "FAIL", "errors": ["output manifest must be a new JSON file"]}
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            return {"status": "FAIL", "errors": [f"clip[{i}]: invalid object"]}
        if (not isinstance(shot.get("narration"), str) or not shot["narration"].strip()
                or len(shot["narration"]) > 1800):
            return {"status": "FAIL", "errors": [f"clip[{i}]: narration must be 1–1800 chars"]}
        audit = audit_source_image(source_root, shot.get("panel"), shot.get("panel_sha256"))
        if audit["status"] != "PASS":
            return {"status": "FAIL", "errors": [f"clip[{i}]: invalid panel source/hash"],
                    "detail": audit}
        motion = shot.get("motion", "static")
        if not isinstance(motion, str) or motion not in ("static", "zoom_in", "zoom_out"):
            return {"status": "FAIL", "errors": [f"clip[{i}]: invalid motion"]}
    try:
        audio_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return {"status": "FAIL", "errors": ["could not create narration directory"]}

    produced = []
    start = 0.0
    pipeline = None
    reused = 0
    for i, shot in enumerate(shots):
        text = shot["narration"].strip()
        digest = sha256(
            f"{CACHE_REVISION}|{speed}|{text}".encode("utf-8")).hexdigest()[:32]
        audio_file = audio_folder / f"line-{digest}.wav"
        probed = None
        if audio_file.is_file() and not audio_file.is_symlink():
            probed = probe_audio(audio_file)
        if not probed or probed.get("status") != "PASS":
            if pipeline is None:
                try:
                    from kokoro import KPipeline
                    pipeline = KPipeline(lang_code="a")
                except (ImportError, RuntimeError, OSError) as exc:
                    return {"status": "FAIL", "errors": ["Kokoro pipeline unavailable: " + str(exc)[:180]],
                            "completed_audio_lines": i}
            result = synthesize(text, audio_file, speed=speed, pipeline=pipeline)
            if result["status"] != "PASS":
                return {"status": "FAIL", "errors": [f"clip[{i}]: Kokoro synthesis failed"],
                        "detail": result, "completed_audio_lines": i}
            probed = probe_audio(audio_file)
            if probed["status"] != "PASS":
                return {"status": "FAIL", "errors": [f"clip[{i}]: narration WAV unreadable"]}
        else:
            reused += 1
        duration = round(probed["duration"], 3)
        if not 0.1 <= duration <= 30:
            return {"status": "FAIL", "errors": [f"clip[{i}]: clip exceeds 30 seconds"]}
        try:
            audio_relative = audio_file.resolve(strict=True).relative_to(source_root.resolve(strict=True)).as_posix()
            audio_sha = file_hash(audio_file)
        except (OSError, ValueError, RuntimeError):
            return {"status": "FAIL", "errors": [f"clip[{i}]: unsafe WAV output"]}
        produced.append({
            "panel": shot["panel"], "panel_sha256": shot["panel_sha256"],
            "audio": audio_relative, "audio_sha256": audio_sha,
            "speaker": "MC", "voice": VOICE,
            "event_id": shot["event_id"],
            "event_continuation": shot.get("event_continuation", False),
            "chapter": shot["chapter"], "narration": text,
            "panel_summary": shot["panel_summary"],
            "match_reason": shot["match_reason"],
            "narrative_role": shot["narrative_role"],
            "motion": shot.get("motion", "static"),
            "start": round(start, 3), "end": round(start + duration, 3),
        })
        start = round(start + duration, 3)
    manifest = {
        "source_authorized": True, "subtitles": False,
        "generated_visuals": False, "voices": {"MC": VOICE},
        "clips": produced,
    }
    checked = validate(manifest, source_root)
    if checked["status"] != "PASS":
        return {"status": "FAIL", "errors": checked["errors"]}
    if audit_storyboard(manifest)["status"] != "PASS":
        return {"status": "FAIL", "errors": ["generated storyboard did not validate"]}
    try:
        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            prefix=".ashentoons-manifest-", suffix=".json", dir=output_manifest.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(manifest, file, indent=2, ensure_ascii=False)
                file.write("\n")
            if output_manifest.exists():
                return {"status": "FAIL", "errors": ["manifest appeared during generation"]}
            os.replace(name, output_manifest)
        finally:
            Path(name).unlink(missing_ok=True)
    except OSError as exc:
        return {"status": "FAIL", "errors": ["failed to save manifest: " + str(exc)[:150]]}
    return {
        "status": "PASS", "path": str(output_manifest),
        "total_clips": len(produced), "total_duration": start,
        "audio_reused": reused, "ready_to_publish": False,
        "note": "Local narration and source hashes are not editorial or rights certification",
    }
