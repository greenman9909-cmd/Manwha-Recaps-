# AshenToons Studio — v0.3 (local-first segment pipeline)

**A practical, fail-closed Python/FFmpeg toolkit for producing manhwa recap MP4s in short, reviewable parts.** Designed for GPT-6 planning and deterministic local execution. **No YouTube upload or autonomous editorial certification is claimed.**

## Implemented

- Source-only panel verification: paths stay inside `--source-root`, expected SHA-256, source signatures.
- Narration-first timing: **Kokoro-82M English Puck (`am_puck`)**, optional local TTS, SHA-addressed WAV reuse.
- Required panel-to-narration notes: chapter, event, panel summary, match reason, narrative role.
- **3–5 minute target parts** (240s target, 300s maximum; short final part allowed).
- FFmpeg static/slow-zoom source-panel MP4 renderer, hash-keyed clip cache, stream-copy part assembly.
- Independent ffprobe check and full FFmpeg decode of assembled video **and audio**.
- Frame-by-frame editorial review snapshots, editable human review checklist, fail-closed release controls.
- Truthful YouTube metadata drafts, default **private**; optional 1280×720 JPEG thumbnail generation from an authorized source image.
- **No added subtitles, no generated illustration assets, no automatic publication.**
- Non-destructive `workspace-init` to prepare `D:\AshenToons`; **no delete or disk format feature**.
- Python 3.10/3.12/3.13 CI including a real FFmpeg-generated media smoke test.

## What this intentionally cannot certify

Technical decoding does **not** verify that the spoken events match the artwork, that speech bubbles contain no text, that source reuse is licensed, or that a title/thumbnail is truthful. `certify` still **refuses release** until those independent checks are fully verified. The CLI does not post to YouTube. Only use assets that you have the right to use.

## Install

Prerequisites: Python 3.10+, **FFmpeg and ffprobe on PATH**. Windows PowerShell:

```powershell
python -m pip install -e .
ashentoons --help
ashentoons workspace-init "D:\AshenToons"
```

For optional **Kokoro-82M Puck** narration (may fetch model weights on first use):

```powershell
python -m pip install -e ".[tts,images]"
```

## Complete source → narration → parts → review workflow

1. Place authorized source panels in `D:\AshenToons\sources`. Create a script based on [examples/episode-script.sample.json](examples/episode-script.sample.json), using relative panel names like `sources/ch01-panel01.png`.
2. Hash each original panel with `ashentoons hash "D:\AshenToons\sources\ch01-panel01.png"` and paste the actual 64-character hash in the script. Script fields explicitly set `source_authorized: true` (this declaration is **not** license evidence), `subtitles: false`, `generated_visuals: false`.
3. Generate all WAV clips and an audio-timed manifest with one reused Kokoro instance:

```powershell
ashentoons narrate-script "D:\AshenToons\manifests\script01.json" --source-root "D:\AshenToons" --output-manifest "D:\AshenToons\manifests\episode01.json"
```

4. Review manifest and plan:

```powershell
ashentoons validate "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons"
ashentoons storyboard-audit "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons"
ashentoons plan-parts "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons"
```

5. Render no-subtitle MP4 parts to `exports\episode01\part-001.mp4`, etc. Corrupt or mismatched narration/panels block rendering.

```powershell
ashentoons render-parts "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons" --output-dir "D:\AshenToons\exports\episode01"
ashentoons qc-decode "D:\AshenToons\exports\episode01\part-001.mp4"
```

6. Extract actual video screenshots for the first part and create a blank independent human checklist. **Do not approve it without watching/listening to the MP4**.

```powershell
ashentoons review-frames "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons" --video "D:\AshenToons\exports\episode01\part-001.mp4" --part 1 --output-dir "D:\AshenToons\reviews\episode01-part01"
ashentoons review-template "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons" --output "D:\AshenToons\reviews\episode01-review.json"
ashentoons review-check "D:\AshenToons\reviews\episode01-review.json"
```

`review-check` fails until you fill **every** real shot/audio/continuity review. Even passing a review cannot override rights checks or automatically authorize public release.

7. Draft honest SEO fields for later manual review/upload:

```powershell
ashentoons seo-draft "D:\AshenToons\manifests\episode01.json" --source-root "D:\AshenToons" --series "Your Manhwa Title" --title "Your Accurate English Recap Title" --output "D:\AshenToons\manifests\youtube01.json"
```

Optional human-reviewed thumbnail draft (source artwork only, 1280x720, under 2 MB):
```powershell
ashentoons thumbnail "sources/ch01-panel01.png" --source-root "D:\\AshenToons" --sha256 ACTUAL_PANEL_SHA256 --headline "BACK FOR REVENGE!" --output "D:\\AshenToons\\thumbnails\\episode01.jpg"
```

8. Transfer each MP4 to your phone or attach it in ChatGPT for per-part review when the transfer interface supports that file size. **This repository itself does not send chat attachments or upload to YouTube.**

## Safety and disk space

`workspace-init` only creates these folders: `sources`, `narration`, `exports`, `cache`, `temp`, `reviews`, `thumbnails`, `manifests`. It never wipes D: or deletes existing files. Keep source images, TTS lines, final MP4s, manifests and approved thumbnails. Treat **only deliberate temporary/cache files** as candidates for later cleanup.

## Tests

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The real media smoke test requires FFmpeg. See [architecture](docs/ARCHITECTURE.md) and [related GitHub research](docs/UPSTREAM_RESEARCH.md).

## Limitations / roadmap

Automated scene meaning verification, speech transcription/alignment, expressive multi-scene editing, advanced thumbnail A/B experimentation, YouTube OAuth upload, real channel analytics, trending-title A/B research, and independent release certification are **not implemented**. GPT-6 can help write and review story plans, but it is not magically running inside this local package and cannot replace editorial approval.
