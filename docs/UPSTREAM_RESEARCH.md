# Upstream study — ideas selected for AshenToons

This comparison informs the architecture but is **not** a claim that the projects' code was transplanted or all features are implemented.

| Project | Relevant feature | AshenToons choice |
| --- | --- | --- |
| [lyndonkl/claude — visual-storytelling-design](https://github.com/lyndonkl/claude/blob/main/skills/visual-storytelling-design/SKILL.md) | Plan a narrative arc, context, insight, visual emphasis, honest framing | Require hook/setup/conflict/reveal/etc. shot roles, exact panel evidence, narrative review. Adapt principles to video, not data charts. |
| [meellm/MeManga](https://github.com/meellm/MeManga) | CLI and locally maintained manga assets; downloadable/exportable content | Operate on local authorized panels. No third-party manga scraping, rate-limit circumvention or redistribution implemented. |
| [Zulko/moviepy](https://github.com/Zulko/moviepy) | Programmatic declarative video editing in Python | Prefer deterministic FFmpeg subprocesses and stream-copy assembly for lower memory usage and portability. |
| [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Scene boundary detection in final videos | Possible independent scene-cut audit later; for this version use explicit shot times and independent FFmpeg full decode. |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | Automatic silence and pacing analysis | Check narrated WAV duration before encoding; silence trimming and pacing analysis remain future work. |

## Specific takeaways

- **Reliable source ≠ verified rights**: even a correct SHA-256 cannot prove that reuse has been authorized. Obtain proper rights and perform a human rights review.
- **Events first, pictures second**: each spoken event needs a source panel with a plain-language justification; otherwise a visually plausible but wrong panel can pass filename checks.
- **Small edits beat giant renders**: use 3–5-minute parts with source/audio hash-based cache keys. Verify each actual MP4 before moving forward.
- **No subtitles**: forbid subtitle streams and generated captions; a reviewer still checks for baked-in caption overlays. Original speech bubbles may remain part of the source artwork.
- **Edit metadata, not facts**: SEO drafts must cite provided story title/timeline only, be private by default, and never fabricate tags, chapters, or view counts.
- **No premature certification**: FFmpeg decode success is technical correctness, not semantic or editorial clearance.

No runtime dependency on any of these third-party repositories is introduced solely by this research.
