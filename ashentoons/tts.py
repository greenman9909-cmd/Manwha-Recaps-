"""Optional on-device Kokoro-82M English narration adapter.

Install the optional 'tts' extra and obtain model assets through their
normal licensed distribution. No network request, download, or hidden
API credential is implemented here.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile

from .core import file_hash

VOICE = "am_puck"
# Fixed allowlist of official English Kokoro speaker IDs. The voice is
# selected by the script's stable character registry, never from a URL.
SUPPORTED_VOICES = frozenset({
    "am_puck", "am_fenrir", "am_michael", "am_adam", "am_onyx",
    "am_echo", "am_eric", "am_liam",
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "af_nova", "af_jessica", "af_river", "af_alloy",
})
SAMPLE_RATE = 24000


def synthesize(text: str, output: Path, voice: str = VOICE,
               speed: float = 1.0, pipeline=None) -> dict:
    """Generate one <=30-second WAV line atomically; keep heavy imports optional."""
    if (not isinstance(text, str) or not text.strip() or len(text) > 1800
            or "\x00" in text):
        return {"status": "FAIL", "errors": ["text must be 1–1800 characters"]}
    if not isinstance(voice, str) or voice not in SUPPORTED_VOICES:
        return {"status": "FAIL", "errors": ["voice must be an approved English Kokoro speaker ID"]}
    if (type(speed) not in (float, int) or not math.isfinite(speed)
            or not 0.75 <= speed <= 1.25):
        return {"status": "FAIL", "errors": ["invalid speech speed"]}
    if not isinstance(output, Path) or output.suffix.lower() != ".wav" or output.is_symlink() or output.exists():
        return {"status": "FAIL", "errors": ["output must be a new, non-symlink WAV"]}
    try:
        from kokoro import KPipeline
        import numpy as np
        import soundfile as sf
    except ImportError:
        return {"status": "FAIL", "errors": [
            "optional Kokoro dependencies missing: pip install -e '.[tts]'"]}
    temp = None
    try:
        chunks = []
        if pipeline is None:
            pipeline = KPipeline(lang_code="a")
        for _graphemes, _phonemes, audio in pipeline(text, voice=voice, speed=speed):
            chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not np.isfinite(chunk).all():
                raise ValueError("non-finite audio samples")
            chunks.append(chunk)
        if not chunks:
            return {"status": "FAIL", "errors": ["TTS generated no audio"]}
        samples = np.concatenate(chunks)
        seconds = len(samples) / SAMPLE_RATE
        if not 0.1 <= seconds <= 30:
            return {"status": "FAIL", "errors": [
                "TTS line exceeds 30 seconds; split into shorter narration clips"]}
        if np.max(np.abs(samples)) <= 0.000001:
            return {"status": "FAIL", "errors": ["TTS output is silent"]}
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".ashentoons-tts-", suffix=".wav",
                                   dir=output.parent)
        os.close(fd)
        temp = Path(name)
        sf.write(str(temp), samples, SAMPLE_RATE, subtype="PCM_16")
        if output.exists():
            return {"status": "FAIL", "errors": ["audio file appeared during generation; refusing overwrite"]}
        os.replace(temp, output)
        return {"status": "PASS", "path": str(output), "voice": voice,
                "duration": round(seconds, 3), "sha256": file_hash(output),
                "sample_rate": SAMPLE_RATE,
                "note": "TTS generated; does not certify pronunciation or narration accuracy"}
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        return {"status": "FAIL", "errors": [type(exc).__name__ + ": " + str(exc)[:200]]}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
