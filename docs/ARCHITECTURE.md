# AshenToons Studio architecture (v0.3)

## Boundaries

- **GPT-6**: plans narrative beats, investigates style, helps create original commentary and drafts source-to-panel match explanations. It does not assert semantic verification based on text alone.
- **Optional Kokoro-82M TTS**: one canonical `am_puck` English MC voice for narration; generate 0.1–30 second atomic WAV lines.
- **FFmpeg / ffprobe**: deterministic 24-fps render/assemble; source-only still panels, centered zoom effects, AAC audio; no subtitle streams added.
- **Independent reviewer**: compares actual rendered frames, original authorized source panels and narration, then checks the human review sheet.
- **YouTube**: metadata draft only; explicitly NO uploader in this version.

## File/data pipeline

```text
authorized JPG/PNG/WEBP + owner-provided SHA-256
             +
   source-grounded script JSON (event, chapter, panel_summary, match_reason)
             |
        storyboard audit
             |
   Kokoro-82M Puck once per batch -> SHA-addressed cached WAV clips
             |
   timed episode manifest (source hashes + narration audio hashes)
             |
       segment planner (target 240s, maximum 300s)
             |
 FFmpeg shot render (static/zoom-in/zoom-out, source-only)
             |
 stream-copy part-001.mp4 ... part-NNN.mp4
             |
 ffprobe metadata + full FFmpeg decode of audio and video
             |
 reviewer frame JPEGs + human review JSON (all fields initially pending)
             |
  truthful private YouTube metadata JSON + optional authorized-panel thumbnail draft
             |
        HUMAN release decision (no auto uploader)
```

## Expected script fields

Each clip needs a relative authorized `panel`, `panel_sha256` computed before editing, unique grounded `event_id`, `narration`, `chapter` integer, `panel_summary` of at least eight characters, `match_reason` of at least eight characters, `narrative_role` (`hook`, `setup`, `conflict`, `reveal`, `reaction`, `payoff`, `transition`, `cliffhanger`), and optional `motion` (`static`, `zoom_in`, `zoom_out`). The outer JSON explicitly specifies `source_authorized: true`, `subtitles: false`, `generated_visuals: false`.

An input manifest used for rendering includes `voices: {"MC":"am_puck"}`, each shot's `speaker: "MC"`, `voice: "am_puck"`, `audio`, `audio_sha256` and monotonic `start/end` seconds. `narrate-script` prepares those fields.

## Efficiency

- Stream SHA-256 rather than loading complete images into memory.
- Lazy-load Kokoro only if speech is missing; reuse one pipeline for all lines in the batch.
- Cache speech by normalized line text, voice, speed and cache revision; cache clips by panel/audio hashes, dimensions, motion and revision.
- For 8GB VRAM systems, avoid simultaneous heavy AI inference and rendering; CLI serializes the latter. FFmpeg encoding defaults to CPU `libx264` for portability; GPU-specific benchmarks/acceleration are future work.
- Target 240 seconds per reviewable part, never exceed 300 seconds except the single shot durations are already validated to <=30 seconds.
- Fail before rendering if a panel hash, narration hash, narration timing, storyboard description, or chapter is missing/invalid.
- After each part, decode **both streams completely**; separate human review always required.
- Do not auto-delete source assets, narration WAV, metadata, exports, or any unrelated D: files.

## Quality gates

1. `audit-source`: image signature + expected digest (does not prove image decodability or licensing).
2. `storyboard-audit`: grounded event notes exist; semantic truth **not verified**.
3. `validate`: safe paths, stable speaker/voice registry, unique events, non-overlap and source hashes.
4. `render-parts`: additionally checks WAV hashes, lengths, camera presets, part FFprobe and full decode.
5. `review-frames` / `review-template`: checks real MP4 frames and asks a human to confirm each shot and all audio/continuity/absence of burned subtitles.
6. `review-check`: fails until every field is confirmed; no automatic release permission.
7. `certify`: still **NOT_CERTIFIED** with `release_allowed=false`. This version has no auto publishing path.

## Remaining engineering work

Audio text-to-speech transcription cross-check; independently test panel/story meaning with actual visual context; robust published-video certification; YouTube OAuth upload with explicit user approval; browser/GitHub integration; dynamic expressive effects; advanced thumbnail testing; analytics-driven content research. These are not faked by changing flags.

## Upstream comparison

See [UPSTREAM_RESEARCH.md](UPSTREAM_RESEARCH.md). Design inspiration only; no third-party code copied.
