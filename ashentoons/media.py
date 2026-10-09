"""Bounded ffprobe inspection; not a semantic audiovisual certification."""
import json
import subprocess
from pathlib import Path

def probe_media(path: Path, timeout: float = 30) -> dict:
    if not isinstance(path, Path) or not path.is_file():
        return {"status": "FAIL", "errors": ["missing media"]}
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=index,codec_type,codec_name,width,height",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "FAIL", "errors": [type(exc).__name__]}
    if proc.returncode != 0:
        return {"status": "FAIL", "errors": ["ffprobe rejected media"]}
    try:
        data = json.loads(proc.stdout)
        streams = data["streams"]
        duration = float(data["format"]["duration"])
        if not (0 < duration < 86400):
            raise ValueError("invalid duration")
        video = [x for x in streams if x.get("codec_type") == "video"]
        audio = [x for x in streams if x.get("codec_type") == "audio"]
        subtitles = [x for x in streams if x.get("codec_type") == "subtitle"]
        if len(video) != 1 or len(audio) != 1 or subtitles:
            raise ValueError("expected one video, one audio, no subtitle streams")
        if int(video[0].get("width", 0)) < 16 or int(video[0].get("height", 0)) < 16:
            raise ValueError("invalid video dimensions")
        return {"status": "PASS", "duration": duration,
                "video_codec": video[0].get("codec_name"),
                "audio_codec": audio[0].get("codec_name"),
                "note": "Container/stream metadata only; decoded frames and sync not verified"}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {"status": "FAIL", "errors": ["malformed or unacceptable media metadata"]}
