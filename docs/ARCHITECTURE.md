# AshenToons architecture and execution order

**Current implementation: v0.2 validator only.** No working renderer, TTS, video QC, or publisher exists.

## Design target
GPT-6 plans, writes grounded scripts, resolves uncertainty; the laptop runs deterministic jobs. Use an immutable source manifest, canonical character and voice IDs, audio-first timing, source-panel-only FFmpeg editing, independent QC, and explicit authorized release.

## Build order
1. Import authorized panels and preserve SHA-256 provenance.
2. Ground each narrated event in a panel; lock character identity and voice casting.
3. Produce TTS, transcribe and align it independently.
4. Render 3–8s clips; assemble scenes, parts, episodes.
5. Inspect decoded media and semantics; inject defects to validate QC.
6. Add thumbnails, SEO, analytics, and authorized publishing.

## Laptop governor (target: 14900HX / 8 GB VRAM / 32 GB RAM)
Serialize heavy GPU inference and NVENC jobs; use bounded CPU workers and a memory budget. Preflight available disk space, persist checkpoints, use streaming hashes, and rerender only affected dependencies. Profile real hardware before setting permanent thresholds.

## Release invariant
No render can be approved by the current validator. A future release service must independently verify exact hashes, actual audio/video content, licensing, and explicit user authorization.
