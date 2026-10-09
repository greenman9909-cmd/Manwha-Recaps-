# AshenToons Studio — Prototype v0.2

Source-only manhwa recap production **validator**, not a working video generator.

## What works
- SHA-256 streamed file verification, safe source-path resolution, fail-closed manifests
- MC voice exclusivity, speaker mapping, event and timeline validation
- Strict source-authorization and no-subtitles/no-generated-visuals rules
- Adversarial unit tests, CI matrix and packaging metadata
- Certification placeholder **always refuses release**

## Run
```bash
python -m unittest discover -s tests -v
```

## What is not built
Actual panel OCR, story memory, humor, multi-voice TTS, FFmpeg rendering, audiovisual semantic QC, thumbnails, SEO, or YouTube publishing. See [architecture roadmap](docs/ARCHITECTURE.md).

Use only panels you have permission to reuse. Do not publish without independent QC and explicit authorization.

## CLI usage

Install from the repository:
```bash
python -m pip install -e .
ashentoons --help
ashentoons hash projects/demo/source/panel.png
ashentoons audit-source panel.png --source-root projects/demo/source --sha256 EXPECTED_64_CHAR_SHA256
ashentoons validate projects/demo/episode.json --source-root projects/demo/source
ashentoons certify projects/demo/episode.json --source-root projects/demo/source --render projects/demo/final.mp4
```

Exit code **0** means the requested preflight passed; **2** means failure/error/not certified. The `certify` command intentionally always refuses release until independent audiovisual QC is implemented. No graphical interface or GPU is required for the validator. Source authorization must be genuine, not merely a manifest flag.
