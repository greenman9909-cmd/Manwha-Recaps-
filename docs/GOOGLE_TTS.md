# Google AI Studio TTS — optional AshenToons voice department (v0.6)

Status: **Ready to configure locally**. This does not change the trusted
MC narrator: **Kokoro \`am_fenrir\` remains the production default**.

## Private setup (Windows laptop only)

Double-click:

\`D:\AshenToons\control-room\Setup Google Voices.cmd\`

This launches a loopback-only page at \`http://127.0.0.1:8771/\`.
Paste the API key **on the laptop in that form**, never in ChatGPT, a
terminal command, a GitHub commit or the group chat. The key is validated
using a read-only Google models query and then stored in:

\`C:\Users\green\.flow-mcp\gemini-key\`

The key file is restricted to the user's Windows account via \`icacls\`.
This is the same key location understood by the optional
[GTAI-1/flow-mcp](https://github.com/GTAI-1/flow-mcp) package, so setting
up its Google voice engine later won't require a second key. Key setup
makes **no audio generation requests** and spends **no Flow credits**.

Key readiness (no secret output, no network):

~~~powershell
Set-Location "D:\AshenToons\studio-code"
& "D:\AshenToons\tools\.venv-memanga\Scripts\python.exe" -m ashentoons.cli google-voice-status
~~~

## Narration engine

Google Gemini 2.5 Flash Preview TTS is the conservative default model.
The newer 3.1 Flash TTS and 3.8 Flash-Lite TTS model IDs are optional;
actual model access and quota depend on Google's API project.

**Your Google AI Plus subscription and Flow credits do not automatically
include paid Gemini Developer API access.** Some models have free quota;
a key attached to a billed project can incur charges. The command
refuses requests until you explicitly add the approval flag.

~~~powershell
& "D:\AshenToons\tools\.venv-memanga\Scripts\python.exe" -m ashentoons.cli tts-google "A new chapter begins." "D:\AshenToons\projects\healing-magic-001\auditions\google-gacrux-test.wav" --voice Gacrux --confirm-possible-api-charges
~~~

Optional batch usage for **existing, verified story lines only**:

~~~powershell
& "C:\Users\green\Documents\Manhwa-Recap-Studio\.venv-kokoro\Scripts\python.exe" -m ashentoons.cli voice-batch-google "D:\AshenToons\projects\healing-magic-001\approved-lines.json" --output-dir "D:\AshenToons\projects\healing-magic-001\google-audio" --output-manifest "D:\AshenToons\projects\healing-magic-001\voice-report-01.json" --max-new-requests 12 --confirm-possible-api-charges --fallback-kokoro
~~~

**Do not invent \`approved-lines.json\`:** it is created later by the
story department from chapter panels. The JSON includes \`clips\` with
\`event_id\`, \`speaker\`, \`chapter\`, \`narration\` (≤400 characters) and
optional \`voice_style\`. The cast can be defined under \`google_voices\`
and optional \`voices\` for local Kokoro rescue.

Proposed audition casting:

| Character | Google voice | Existing Kokoro voice |
|---|---|---|
| MC narrator | Gacrux | am_fenrir (still default) |
| Usato | Puck | am_puck |
| Rose | Kore | af_bella |
| Suzune | Zephyr | af_heart |
| Kazuki | Charon | am_michael |

Google "Fenrir" and Kokoro "am_fenrir" are **different engines and
recordings**. Identical names don't imply the same narrator sound.

## Safe production behavior

- No Google API call occurs unless \`--confirm-possible-api-charges\` is
  provided, and one batch is limited to **12 new requests by default**.
  Manually increase only after checking Google quota/actual billing.
- Clips are 24kHz mono signed 16-bit WAVs and must pass sample-rate,
  decoding and duration checks (≤30 seconds per line).
- SHA-based caching includes model, voice, style and exact line text.
  Restarting a batch reuses validated audio instead of paying again.
- HTTP 429 and transient 5xx retry at most twice with backoff.
  Auth errors fail immediately; keys never appear in errors or logs.
- An explicit \`--fallback-kokoro\` permits local rescues if Google
  fails or is unconfigured; it uses the correct character voice.
- Source-panel matches, facial reactions, pacing, pronunciation,
  dialogues and final thumbnail **still require editorial review**.
- The generated voice manifest is **never a release certificate**.
  No automatic YouTube upload or generated manga artwork.

## Architecture

GPT-6 CEO & Operator in connected ChatGPT → AshenToons HQ
Voice Department (Echo) → Kokoro production / optional Google voice
→ WAV manifest with speaker, event, SHA, real duration
→ Story and Editing/QC departments → reviewed long-form video.

The entire workflow runs on the laptop; only an explicitly approved
Google voice request goes to the Google API. The local UI only captures
the API key over 127.0.0.1 and stops after successful configuration.
