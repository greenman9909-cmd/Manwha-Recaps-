# MeManga → AshenToons chapter import (v0.5)

**Goal:** import manga pages without manual copying, preserve the exact order
of the source pages and prepare them for AshenToons storyboard review.

[MeManga](https://github.com/meellm/MeManga) is an optional open-source
downloader. This adapter imports a chapter from an EXISTING local MeManga
export directory; it makes no network requests, and does not attempt
to bypass security or access controls.

## Local setup

For The Wrong Way to Use Healing Magic, keep the series ID as healing-magic.
The user's project-level authorization declaration is included in the source
ledger; importing further pages does not require asking the same question
again. This is a project declaration, not an independent legal certification.

In PowerShell, from the studio code directory:

~~~powershell
Set-Location "D:\AshenToons\studio-code"
python -m pip install -e ".[images]"
python -m ashentoons.cli ingest-memanga "D:\AshenToons\temp\memanga-downloads\The Wrong Way to Use Healing Magic\Chapter 1" --source-root "D:\AshenToons" --series-id healing-magic --chapter 1 --reading-direction rtl
~~~

Use the actual downloaded chapter path. The command does **not** fetch pages
when the input directory is missing. For webtoons use reading direction ltr.

**Important:** RTL describes the order of panels/bubbles *within* Japanese
manga pages; whole pages must remain in the numbered chapter order
(1, 2, 10), and are **never reversed**.

## Result

~~~text
D:\AshenToons\
  sources\
    healing-magic\
      ch001\
        page-0001.webp
        page-0002.webp
        ...
  manifests\
    healing-magic\
      chapter-001-source.json
~~~

The source ledger includes original filename, page sequence, final filename,
SHA-256, byte length, decoded width/height, reading direction and an
unapproved editorial review status.

Source pages are copied **byte for byte**. The downloader originals remain
unchanged. The importer validates image decoding before copying and rejects
missing/corrupt files. Re-running the same chapter is safe: matching source
and output hashes are verified, and the chapter is reused. Mismatched inputs,
existing unrelated outputs, and symlink pages are rejected, never overwritten.

## Five-voice casting example

The studio CLI can audition individual local Kokoro voices:

~~~powershell
python -m ashentoons.cli tts-line "The healer's training was just getting started." "D:\AshenToons\narration\healing-audition-fenrir.wav" --voice am_fenrir --speed 1.02
~~~

A story script can define the MC as am_fenrir, Usato as am_puck, Rose as
af_bella, Suzune as af_heart and Kazuki as am_michael. Every clip then selects
the corresponding speaker; the stable voice/text/speed cache prevents
cross-character audio reuse. For the exact JSON schema see
[STORYTELLING_MULTIVOICE.md](STORYTELLING_MULTIVOICE.md).

## Required quality control

1. Independently review the manga's page and speech-bubble reading order.
2. Keep original speech/faces/context readable when cutting vertical pages.
3. Map each ORIGINAL recap line to the correct real story event and speaker.
4. Synthesize stable voices and validate the exact timed scene manifest.
5. Render 3–5 minute parts, watch and listen, correct errors.
6. Assemble longer episodes only after each part passes editorial review.
7. Create the source-panel thumbnail and accurate title/SEO after the edit.

**Import success does not mean a 60-minute video is finished.**
Full FFmpeg decoding cannot independently certify scene/dialogue alignment.
This command never publishes, alters original files or renames the NVME drive.

## Troubleshooting

- No input pages: check the correct MeManga chapter folder; never substitute
  another title.
- No Pillow: install the optional images package as shown above.
- Image corrupt: redownload or repair the original using authorized methods.
- Existing chapter differs: inspect the ledger; never delete earlier work
  or silently replace it.
