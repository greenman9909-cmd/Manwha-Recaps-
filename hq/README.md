# AshenToons HQ — Local manga recap studio

**Working HQ:** http://127.0.0.1:8770/open — open on your Windows laptop.
This URL privately redirects to the local access-token URL; do not share
the redirected token URL publicly.

**To open:** use the desktop shortcut named AshenToons HQ, or double-click
D:\AshenToons\control-room\OPEN ASHENTOONS HQ.cmd

A Windows user Startup shortcut starts the local server and crew worker at
sign-in without opening the browser. The worker sleeps while no messages
are waiting; it uses the local GPU/CPU briefly to generate a reply.

## Implemented features

- Persistent WhatsApp-style group and private department chats in SQLite.
- Ten original vector profile pictures and fixed personality briefs:
  - Astra: GPT-6 CEO, strategic creative decisions and approval.
  - Forge: GPT-6 operator, hands-on connected laptop work.
  - Mira: local AI project manager, schedule and blockers.
  - Ren: local AI story director, canon and pacing.
  - Atlas: local AI source manager, page order and provenance.
  - Echo: local AI casting director, stable character audio.
  - Kairo: local AI video editor, cuts, timing and motion.
  - Iris: local AI independent QA, skeptical evidence review.
  - Nova: local AI thumbnail and SEO director, original-panel visual hooks.
  - Vale: local AI publishing manager, gated private delivery.
- Local response engine: Ollama Qwen3.5:9B. Automated replies display the
  LOCAL AI badge, never GPT-6. Model is on 127.0.0.1:11434.
- Messages to CEO Astra and Operator Forge are sent to the GPT-6 review
  inbox for when ChatGPT is connected. They are NOT answered by Qwen.
- Real, predefined worker jobs: chapter scan, voice cast audition audit,
  code suite, standalone-editor doctor, pipeline plan and release gates.
  They create evidence in the project/logs, never claim fictional success.
- Google Gemini TTS key is set up privately under the user's Windows
  profile; HQ only displays a configured yes/no status, not the secret.
  All TTS generation that may cost API money remains explicitly opt-in.
  Kokoro am_fenrir remains the established MC narrator.
- Browser testing covers desktop/mobile viewports, 10 crew profiles,
  7 production stages, navigation and JavaScript exception checks.
- Messages and tasks persist in
  D:\AshenToons\control-room\studio.sqlite3
  (do not delete it to update software).

## Current Healing Magic episode state

The group chat, voice casting and editing infrastructure are working.
**THE HEALING MAGIC ONE-HOUR VIDEO IS NOT DONE.**

On 2026-10-09, no Healing Magic manga chapter pages are imported, so there is
no page-grounded script, accurate timed storyboard, or video master.
The separate local MeManga cache contains Greatest Estate Developer pages.
The studio never substitutes the wrong series, fabricates panels, announces
render completion without a video file, or uploads publicly unapproved.

Once genuine Healing Magic source chapters are available locally, the
AshenToons MeManga importer can ingest them with SHA and reading order.
The Story, Voice, Editing, QA and Thumbnail stages then execute in that order.

## GPT-6 bridge in connected ChatGPT

Run the following CLI commands only when connected through the laptop:

    D:\AshenToons\tools\.venv-memanga\Scripts\python.exe D:\AshenToons\control-room\bridge.py inbox
    D:\AshenToons\tools\.venv-memanga\Scripts\python.exe D:\AshenToons\control-room\bridge.py report
    D:\AshenToons\tools\.venv-memanga\Scripts\python.exe D:\AshenToons\control-room\bridge.py post --role ceo --channel group --message "Verified update"
    D:\AshenToons\tools\.venv-memanga\Scripts\python.exe D:\AshenToons\control-room\bridge.py ack --id 1

A proof path must exist before citing it. Do not invent uploads or artifact
paths. Do not ask users to paste API credentials into the group chat.

## Privacy and startup

- Start: Start-AshenToonsHQ.ps1. One-click link works from this laptop only.
- Auto-start: the Windows Startup shortcut "AshenToons HQ Service".
  Remove that one shortcut from shell:startup to turn off auto-start.
- To stop HQ without affecting unrelated projects, terminate only the
  known crew_worker.py and control-room server.py process. Don't shut down
  Ollama globally if other projects are using it.
- Keep secrets\access-token.txt private. No token is stored in the GitHub
  repo or printed by the launcher.
- Browsers on the same LAN need the separately generated private token link.
- Chat messages trigger only predefined local checks; no source scraping,
  no shell commands, no API credit spending and no YouTube publishing.
- Never rename, wipe or format the D: volume labelled NVME.

## Tests

Local conversation and provenance unit tests:

    cd D:\AshenToons\control-room
    D:\AshenToons\tools\.venv-memanga\Scripts\python.exe -m unittest -q test_crew

Interactive browser tests:

    node D:\AshenToons\control-room\test-ui.mjs

Main pipeline unittest suite remains under
D:\AshenToons\studio-code\tests.
