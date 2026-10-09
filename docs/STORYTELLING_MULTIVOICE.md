# AshenToons v0.4 story-direction and multi-character narration

This is an **adaptation** of the storytelling ideas in
[visual-storytelling-design](https://github.com/lyndonkl/claude/blob/main/skills/visual-storytelling-design/SKILL.md).
That skill was written for **data visualization**, not manhwa video or TTS.
We apply only its high-level narrative structure, progressive disclosure,
cognitive clarity and integrity principles to our own production pipeline.

## Source and rights gate

Before starting a new manga/manhwa: record the exact title, creator, authorized
panel-source location, permitted uses (including derived YouTube commentary and
thumbnail imagery), chapter range, and any attribution/credit obligations.
**Online availability, scanlation, or lack of a local translation license
does not make a work public domain.** Do not fetch, mirror, or publish a title
without the rights needed for this project. Do not put third-party artwork in
GitHub. Local paths and SHA-256 digests refer only to authorized assets.

## Episode management ledger (one per title)

Use an editable local JSON/script/worksheet with:
- Series ID, title, chapter range, status and permission evidence.
- Scene index: chapter, sequence position, event_id, characters present,
  original panel filename/hash, panel summary and speech-bubble intent.
- Editorial: hook, setup, obstacle, turning point, payoff, suspense beat,
  original commentary, voice line, designated speaker, voice identifier.
- Frame: crop rectangle, target aspect ratio, safe faces/text area,
  minimum readable font in original bubble, shot duration and camera motion.
- QA: audio transcript, exact spoken text, audio duration, original shot file,
  rendered midpoint screenshot, actual visible source text notes,
  continuity/synchronization acceptance and reviewer initials.
- Release: per-part reviewer approval, private preview, accurate chapters/SEO,
  thumbnail with real authorized art, final user approval.

No role label implies a human has actually checked anything. Reviews start
unapproved and remain so until the finished MP4 is inspected.

## Story director: engaging without losing the story

1. **Opening (0–30s):** Lead with a real visual contradiction, character
   challenge or surprising choice visible in the authorized source. Do not
   invent plot events for clickbait.
2. **Context:** Briefly establish the MC, motivations, objective and stakes.
3. **Problem / escalation:** Keep beats in canonical chronological order. Use
   one new reveal at a time; update viewer understanding before moving on.
4. **Reaction / payoff:** Insert occasional ORIGINAL, scene-grounded playful
   commentary, not copied phrases or another creator's specific script.
5. **Segment close:** Use real existing cliffhangers or a concise question
   supported by the actual chapter.

Alternate funny and serious beats; avoid generic filler. A 60-minute target
is a length constraint **after** faithful story coverage, never a reason to
repeat panels, artificially slow speech or fabricate events.

## Local multi-character voice casting

Add to a new *script input*:

```json
{
  "source_authorized": true,
  "subtitles": false,
  "generated_visuals": false,
  "voices": {
    "MC": "am_fenrir",
    "MainCharacter": "am_puck",
    "Rival": "am_michael",
    "Guardian": "af_bella"
  },
  "clips": [
    {
      "speaker": "MC",
      "panel": "sources/authorized/ch01/001.png",
      "panel_sha256": "ACTUAL_SHA256_TO_FILL",
      "event_id": "ch01-intro-001",
      "chapter": 1,
      "narration": "An ORIGINAL concise scene description.",
      "panel_summary": "An evidence-grounded description of the artwork.",
      "match_reason": "Explain which visible details support this line.",
      "narrative_role": "hook",
      "motion": "static"
    }
  ]
}
```

All names and hashes in the example are placeholders. Never set
`source_authorized: true` without actual permission. For a speaker other than
`MC`, write the dialogue line in that speaker's `narration` field; do not
voice the original story word-for-word. The speaker ID maps to one stable voice
through every chapter. The narrator voice must differ from character voices;
all Kokoro IDs must be from the built-in English allowlist.

Use the existing `ashentoons narrate-script` command, then `validate`,
`storyboard-audit`, `plan-parts`, `render-parts`, `qc-decode` and actual
review. The generated WAV cache key includes **voice + speed + text**, so
different characters speaking the same text do not share audio.

Kokoro does not reliably guarantee human-like emotions merely because a voice
sounds deep. Record real short samples, compare pronunciation and pacing,
revise punctuation in scripts, and get human approval. Do not claim a scene is
correct because FFmpeg decoded it.

## Panel-text / spoken-audio accuracy review

For every 3–5-minute part, the independent reviewer should:
1. Compare original panel to crop; confirm no important face/speech bubble is cut.
2. Listen to every character line and verify its speaker is correctly assigned.
3. Compare the *meaning* of visible dialogue with the spoken recap, paying
   attention to who speaks, the story's event order and chapter continuity.
4. Check each narration line begins while its corresponding panel is present.
5. Check no added burned subtitles, no off-story captions or fabricated panels.
6. Check shots vary for actual story reasons, not filler or dramatic jitter.
7. Stop and fix failing shots **before** concatenating the long film.

Machine validation can prove file hashes, track durations, speaker names,
voice-cache identities and decodable media. It cannot prove story truth or
visual-text meaning by itself, and must not label these as certified.

## Reusable multiple-series production

Keep each series isolated under `D:\\AshenToons\\projects\\series-id`
with its own rights ledger, authorized sources, manifests, voice registry,
WAV cache namespace, 3–5 minute review parts, final MP4, description,
thumbnail and QA record. Never rename, clean or format the NVME (D:) drive.
Never upload to the user's YouTube account unless explicitly authorized;
existing YouTube support is **private draft only**.
