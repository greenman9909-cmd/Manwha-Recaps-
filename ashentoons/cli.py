"""AshenToons CLI: source-locked, no-subtitle production, never auto-publish."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .core import validate, audit_source_image, certify, file_hash
from .media import probe_media
from .render import render_clip
from .assemble import assemble
from .production import plan_parts, render_parts
from .storyboard import audit_storyboard, review_template, check_review
from .qc import decode_check
from .seo import seo_draft
from .tts import synthesize
from .narrate import narrate_script
from .review_frames import extract_review_frames
from .workspace import initialize_workspace


def _load_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("JSON input missing or larger than 8 MiB")
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path: Path, report: dict) -> None:
    if path.suffix.lower() != ".json" or path.is_symlink():
        raise ValueError("output must be a non-symlink JSON path")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ashentoons-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ashentoons", description="Source-only manhwa recap production and fail-closed QC")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate episode source manifest")
    v.add_argument("manifest", type=Path)
    v.add_argument("--source-root", type=Path, required=True)

    a = sub.add_parser("audit-source", help="check image signature and SHA-256")
    a.add_argument("image", help="path relative to --source-root")
    a.add_argument("--source-root", type=Path, required=True)
    a.add_argument("--sha256", required=True)

    h = sub.add_parser("hash", help="stream SHA-256 for local file")
    h.add_argument("file", type=Path)

    c = sub.add_parser("certify", help="fail-closed release certification placeholder")
    c.add_argument("manifest", type=Path)
    c.add_argument("--source-root", type=Path, required=True)
    c.add_argument("--render", type=Path, required=True)

    p = sub.add_parser("probe", help="inspect media streams using ffprobe")
    p.add_argument("file", type=Path)

    q = sub.add_parser("qc-decode", help="fully decode audio + video, no editorial certification")
    q.add_argument("file", type=Path)
    q.add_argument("--duration", type=float, default=None)

    render = sub.add_parser("render-clip", help="render authorized panel + narration WAV")
    render.add_argument("panel")
    render.add_argument("audio")
    render.add_argument("output", type=Path)
    render.add_argument("--source-root", type=Path, required=True)
    render.add_argument("--duration", type=float, required=True)
    render.add_argument("--width", type=int, default=1280)
    render.add_argument("--height", type=int, default=720)
    render.add_argument("--motion", choices=("static", "zoom_in", "zoom_out"), default="static")

    episode = sub.add_parser("assemble", help="assemble compatible MP4 clips without re-encode")
    episode.add_argument("output", type=Path)
    episode.add_argument("clips", type=Path, nargs="+")

    for name, help_text in (
        ("plan-parts", "plan reviewable 3–5 minute parts"),
        ("render-parts", "validate storyboard/audio and render chapter-aware parts"),
        ("storyboard-audit", "require evidence for every panel/narration match"),
        ("review-template", "produce a human review sheet with zero auto-approvals"),
        ("seo-draft", "prepare truthful, private-by-default YouTube metadata"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("manifest", type=Path)
        command.add_argument("--source-root", type=Path, required=True)
        if name in ("plan-parts", "render-parts", "review-template"):
            command.add_argument("--target-seconds", type=float, default=240)
            command.add_argument("--max-seconds", type=float, default=300)
        if name == "render-parts":
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--width", type=int, default=1280)
            command.add_argument("--height", type=int, default=720)
        if name in ("review-template", "seo-draft"):
            command.add_argument("--output", type=Path, required=True)
        if name == "seo-draft":
            command.add_argument("--series", required=True)
            command.add_argument("--title", required=True)
            command.add_argument("--tag", dest="tags", action="append", default=None)

    review = sub.add_parser("review-check", help="validate completed human review sheet")
    review.add_argument("file", type=Path)

    tts = sub.add_parser("tts-line", help="optional local Kokoro-82M Puck English WAV")
    tts.add_argument("text")
    tts.add_argument("output", type=Path)
    tts.add_argument("--speed", type=float, default=1.0)

    script = sub.add_parser("narrate-script", help="generate WAV clips and timed manifest with Kokoro")
    script.add_argument("script", type=Path)
    script.add_argument("--source-root", type=Path, required=True)
    script.add_argument("--output-manifest", type=Path, required=True)
    script.add_argument("--audio-subdirectory", default="narration")
    script.add_argument("--speed", type=float, default=1.0)

    frames = sub.add_parser("review-frames", help="extract part MP4 frames for shot-by-shot review")
    frames.add_argument("manifest", type=Path)
    frames.add_argument("--source-root", type=Path, required=True)
    frames.add_argument("--video", type=Path, required=True)
    frames.add_argument("--part", type=int, required=True)
    frames.add_argument("--output-dir", type=Path, required=True)
    frames.add_argument("--target-seconds", type=float, default=240)
    frames.add_argument("--max-seconds", type=float, default=300)

    workspace = sub.add_parser("workspace-init", help="prepare an AshenToons folder without deleting files")
    workspace.add_argument("directory", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "hash":
            if not args.file.is_file():
                raise ValueError("missing input file")
            print(file_hash(args.file))
            return 0
        if args.command == "assemble":
            report = assemble(args.clips, args.output)
        elif args.command == "render-clip":
            report = render_clip(args.source_root, args.panel, args.audio,
                                 args.output, args.duration, args.width,
                                 args.height, motion=args.motion)
        elif args.command == "workspace-init":
            report = initialize_workspace(args.directory)
        elif args.command == "narrate-script":
            report = narrate_script(_load_json(args.script), args.source_root,
                                    args.output_manifest, args.audio_subdirectory,
                                    args.speed)
        elif args.command == "review-frames":
            report = extract_review_frames(
                _load_json(args.manifest), args.source_root, args.video,
                args.part, args.output_dir, args.target_seconds, args.max_seconds)
        elif args.command == "tts-line":
            report = synthesize(args.text, args.output, speed=args.speed)
        elif args.command == "probe":
            report = probe_media(args.file)
        elif args.command == "qc-decode":
            report = decode_check(args.file, args.duration)
        elif args.command == "audit-source":
            report = audit_source_image(args.source_root, args.image, args.sha256)
        elif args.command == "review-check":
            report = check_review(_load_json(args.file))
        else:
            manifest = _load_json(args.manifest)
            if args.command == "validate":
                report = validate(manifest, args.source_root)
            elif args.command == "certify":
                report = certify(manifest, args.source_root, args.render)
            elif args.command == "storyboard-audit":
                report = validate(manifest, args.source_root)
                if report["status"] == "PASS":
                    report = audit_storyboard(manifest)
            elif args.command == "seo-draft":
                report = seo_draft(manifest, args.source_root, args.series,
                                   args.title, args.tags)
                if report["status"] == "PASS":
                    _write_json(args.output, report["metadata"])
            else:
                plan = plan_parts(manifest, args.source_root,
                                  args.target_seconds, args.max_seconds)
                if args.command == "plan-parts":
                    report = plan
                elif args.command == "render-parts":
                    report = render_parts(manifest, args.source_root,
                                          args.output_dir, args.target_seconds,
                                          args.max_seconds, args.width,
                                          args.height)
                elif args.command == "review-template":
                    report = review_template(manifest, plan)
                    if report["status"] == "PENDING_HUMAN_REVIEW":
                        _write_json(args.output, report)
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        # Producing a pending review template is a successful export,
        # never a release certification.
        return 0 if report["status"] in ("PASS", "PENDING_HUMAN_REVIEW") else 2
    except (OSError, ValueError, UnicodeError, TypeError, KeyError,
            RecursionError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "errors": [str(exc)]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
