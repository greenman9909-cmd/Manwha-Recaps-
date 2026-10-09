"""Fail-closed episode assembly from already-rendered compatible MP4 clips."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from .media import probe_media
from .core import file_hash

def assemble(clips: list[Path], output: Path, timeout: int = 3600) -> dict:
    if not isinstance(clips, list) or not 1 <= len(clips) <= 2000:
        return {"status":"FAIL","errors":["requires 1–2000 clips"]}
    if output.suffix.lower() != ".mp4" or output.is_symlink():
        return {"status":"FAIL","errors":["unsafe output"]}
    if any(not isinstance(p, Path) or not p.is_file() or p.is_symlink() for p in clips):
        return {"status":"FAIL","errors":["missing or unsafe clip"]}
    resolved_output = output.resolve()
    if any(p.resolve() == resolved_output for p in clips):
        return {"status":"FAIL","errors":["output overlaps input"]}
    probes = [probe_media(p) for p in clips]
    if any(p["status"] != "PASS" for p in probes):
        return {"status":"FAIL","errors":["input media preflight failed"]}
    codecs = {(p["video_codec"], p["audio_codec"], p["width"], p["height"]) for p in probes}
    if len(codecs) != 1:
        return {"status":"FAIL","errors":["incompatible codecs"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".ashentoons-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    list_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".ffconcat",
                                         prefix=".ashentoons-", dir=output.parent,
                                         delete=False) as listing:
            list_path = Path(listing.name)
            listing.write("ffconcat version 1.0\n")
            for clip in clips:
                # ffconcat single-quote escape, with paths normalized to POSIX slashes.
                path = clip.resolve().as_posix().replace("'", "'\\''")
                listing.write(f"file '{path}'\n")
        command = ["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
                   "-safe","0","-f","concat","-i",str(list_path),
                   "-map","0:v:0","-map","0:a:0","-c","copy","-movflags","+faststart",str(temp)]
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        if result.returncode != 0:
            return {"status":"FAIL","errors":["concat failed"],"detail":result.stderr.decode("utf-8","replace")[-600:]}
        check = probe_media(temp)
        if check["status"] != "PASS":
            return {"status":"FAIL","errors":["assembled media failed preflight"]}
        expected = sum(p["duration"] for p in probes)
        if abs(check["duration"] - expected) > max(1.0, len(clips)*0.15):
            return {"status":"FAIL","errors":["assembled duration mismatch"]}
        os.replace(temp, output)
        return {"status":"PASS","path":str(output),"sha256":file_hash(output),
                "duration":check["duration"],
                "note":"Container metadata only; content/sync not certified"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status":"FAIL","errors":[type(exc).__name__]}
    finally:
        temp.unlink(missing_ok=True)
        if list_path is not None:
            list_path.unlink(missing_ok=True)
