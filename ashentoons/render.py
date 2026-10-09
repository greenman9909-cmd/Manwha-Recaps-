"""Deterministic CLI clip renderer for user-supplied authorized images and audio.

This module does not generate narration, verify rights, or certify semantics.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import tempfile
from .core import _safe_source, file_hash

def render_clip(root: Path, panel: str, audio: str, output: Path,
                duration: float, width: int = 1280, height: int = 720,
                timeout: int = 180) -> dict:
    """Render one image+audio clip atomically; reject unsafe paths and partial output."""
    if type(duration) not in (int, float) or not math.isfinite(duration) or not (0.1 <= duration <= 30):
        return {"status":"FAIL","errors":["duration outside 0.1–30 seconds"]}
    if type(width) is not int or type(height) is not int or width < 320 or height < 240 or width > 3840 or height > 2160 or width % 2 or height % 2:
        return {"status":"FAIL","errors":["invalid output dimensions"]}
    source = _safe_source(root, panel)
    narration = _safe_source(root, audio)
    if source is None or narration is None:
        return {"status":"FAIL","errors":["missing or unsafe panel/audio source"]}
    if source.suffix.lower() not in (".png",".jpg",".jpeg",".webp") or narration.suffix.lower() not in (".wav",".mp3",".m4a",".flac"):
        return {"status":"FAIL","errors":["unsupported source extension"]}
    if output.suffix.lower() != ".mp4" or output.is_symlink():
        return {"status":"FAIL","errors":["output must be a non-symlink MP4 path"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ashentoons-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    tmp = Path(name)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    command = ["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
               "-loop","1","-framerate","24","-i",str(source),"-i",str(narration),
               "-t",str(duration),"-vf",vf,"-r","24",
               "-c:v","libx264","-preset","veryfast","-crf","20",
               "-c:a","aac","-b:a","160k","-ar","48000",
               "-pix_fmt","yuv420p","-movflags","+faststart",str(tmp)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            return {"status":"FAIL","errors":["ffmpeg failed or produced empty output"],
                    "detail":result.stderr.decode("utf-8","replace")[-600:]}
        os.replace(tmp, output)
        return {"status":"PASS","path":str(output),"sha256":file_hash(output),
                "note":"Rendered only; synchronization and source licensing not certified"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status":"FAIL","errors":[type(exc).__name__]}
    finally:
        tmp.unlink(missing_ok=True)
