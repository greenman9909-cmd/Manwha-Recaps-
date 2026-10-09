# AshenToons Studio — v0.5 (local-first segment pipeline)

**A practical, fail-closed Python/FFmpeg toolkit for producing manhwa recap MP4s in short, reviewable parts.** Designed for GPT-6 planning and deterministic local execution. **No public YouTube publishing or autonomous editorial certification is claimed.**

## Implemented

- **Native MeManga chapter import:** lossless local pages with natural numbered order, decoding verification, SHA-256 provenance, RTL/LTR page metadata and resumable multi-chapter batch import. This does not trigger a web download.
- Source-only panel verification: paths stay inside `--source-root`, expected SHA-256, source signatures.
- Narration-first timing: optional local **Kokoro-82M English character cast**, with stable per-speaker voice mapping, MC-led narration and voice-separated SHA-addressed WAV reuse. Old Puck-only scripts still work.
- Required panel-to-narration notes: chapter, event, panel summary, match reason, narrative role.
- **3–5 minute target parts** (240s target, 300s maximum; short final part allowed).
- FFmpeg static/slow-zoom source-panel MP4 renderer, hash-keyed clip cache, stream-copy part assembly.
- Independent ffprobe check and full FFmpeg decode of assembled video **and audio**.
- Frame-by-frame editorial review snapshots, editable human review checklist, fail-closed release controls.
- Truthful YouTube metadata drafts, default **private**; optional 1280×720 JPEG thumbnail generation from an authorized source image.
- Optional OAuth YouTube **private-only draft upload** with a receipt created before the API call, explicit consent, explicit audience declaration, and no automatic ambiguous retries.
- **No added subtitles, no generated illustration assets, no automatic publication.**
- Non-destructive `workspace-init` to prepare `D:\AshenToons`; **no delete or disk format feature**.
- Python 3.10/3.12/3.13 CI including a real FFmpeg-generated media smoke test.

## What this intentionally cannot certify

Technical decoding does **not** verify that the spoken events match the artwork, that speech bubbles contain no text, that source reuse is licensed, or that a title/thumbnail is truthful. `certify` still **refuses release** until those independent checks are fully verified. The optional `upload-private` command can upload a private draft with your Google OAuth approval, but it **cannot publish publicly**. Only use assets that you have the right to use.

## Install

Prerequisites: Python 3.10+, **FFmpeg and ffprobe on PATH**. Windows PowerShell:

```powershell
python -m pip install -e .
ashentoons --help
ashentoons workspace-init "D:\AshenToons"
```

For optional **Kokoro-82M English cast** narration (may fetch model weights on first use):

```powershell
python -m pip install -e ".[tts,images,youtube]"
```

## Fast local MeManga → AshenToons import (no manual file copying)

After MeManga has created a local chapter folder, use:

~~~powershell
ashentoons ingest-memanga "D:\AshenToons\temp\memanga-downloads\The Wrong Way to Use Healing Magic\Chapter 1" --source-root "D:\AshenToons" --series-id healing-magic --chapter 1 --reading-direction rtl
~~~

For a whole locally downloaded title's numbered chapter folders:

~~~powershell
ashentoons ingest-memanga-batch "D:\AshenToons\temp\memanga-downloads\The Wrong Way to Use Healing Magic" --source-root "D:\AshenToons" --series-id healing-magic --start-chapter 1 --end-chapter 12 --reading-direction rtl
~~~

The input folders must already exist. Image files are copied **without transcoding**, page hashes are verified, unchanged chapters are reused and nothing existing is overwritten. Chapter manifests are stored under `manifests/healing-magic`. A single project-level user authorization declaration is recorded with the imported material; a new permission prompt is not required for each chapter. RTL means panel/bubble reading order within each manga page, **not reversing the page sequence**. See the [MeManga integration guide](docs/MEMANGA_IMPORT.md).

Cast audition now supports `ashentoons tts-line "Dialogue" out.wav --voice am_fenrir` in addition to the multi-character storyboard registry.

## Complete source → narration → parts → review workflow

1. Place authorized source panels in `D:\AshenToons\sources`. Create a script based on [examples/episode-script.sample.json](examples/episode-script.sample.json), using relative panel names like `sources/ch01-panel01.png`.
   **Optional character cast:** put `"voices": {"MC":"am_fenrir", "Hero":"am_puck", "Rival":"am_michael"}` in the script, then `"speaker": "MC"` (or `"speaker": "Hero"`, etc.) on each relevant clip. The MC voice must differ from character voices. Legacy scripts default to `am_puck`. This routes distinct on-device voices but does **not** independently verify dialogue or emotion. See [storytelling and multi-voice workflow](docs/STORYTELLING_MULTIVOICE.md).

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

Optional **private-only** YouTube draft upload, after checking the real MP4, source rights, metadata and approved thumbnail. Supply your own Google Cloud OAuth Desktop App client JSON locally, not in GitHub or chat; the first upload opens a browser for consent. The platform's audience setting requires an explicit yes/no choice. The command cannot make the video public:

```powershell
ashentoons upload-private "D:\\AshenToons\\exports\\episode01\\part-001.mp4" --metadata "D:\\AshenToons\\manifests\\youtube01.json" --client-secrets "D:\\AshenToons\\.credentials\\oauth-client.json" --token-file "D:\\AshenToons\\.credentials\\youtube-token.json" --receipt "D:\\AshenToons\\manifests\\upload-receipt-part001.json" --made-for-kids no --confirm-private-upload
```

`--made-for-kids no` is **only an example**: choose the correct setting for the actual video. The uploader checks full audio/video decoding before posting, does not auto-retry an uncertain upload, and writes a receipt whose status may require inspecting YouTube Studio. OAuth/API quota and account verification requirements still apply.

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

Automated scene meaning verification, speech transcription/alignment, independently verified emotional acting, advanced thumbnail A/B experimentation, public YouTube publishing, real channel analytics, trending-title A/B research, and independent release certification are **not implemented**. GPT-6 can help write and review story plans, but it is not magically running inside this local package and cannot replace editorial approval.
