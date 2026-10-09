"""CLI entry point for AshenToons source preflight (not video certification)."""
import argparse
import json
import sys
from pathlib import Path
from .core import validate, audit_source_image, certify, file_hash
from .media import probe_media
from .render import render_clip
from .assemble import assemble

def main(argv=None):
    parser = argparse.ArgumentParser(prog="ashentoons", description="Fail-closed manhwa source preflight")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="validate an episode manifest")
    v.add_argument("manifest", type=Path)
    v.add_argument("--source-root", type=Path, required=True)
    a = sub.add_parser("audit-source", help="check image signature and SHA-256")
    a.add_argument("image", help="path relative to --source-root")
    a.add_argument("--source-root", type=Path, required=True)
    a.add_argument("--sha256", required=True)
    h = sub.add_parser("hash", help="stream SHA-256 for a local file")
    h.add_argument("file", type=Path)
    c = sub.add_parser("certify", help="fail-closed media certification placeholder")
    c.add_argument("manifest", type=Path)
    c.add_argument("--source-root", type=Path, required=True)
    c.add_argument("--render", type=Path, required=True)
    p = sub.add_parser("probe", help="inspect rendered media streams with ffprobe")
    p.add_argument("file", type=Path)
    render = sub.add_parser("render-clip", help="render authorized panel + existing narration audio")
    render.add_argument("panel")
    render.add_argument("audio")
    render.add_argument("output", type=Path)
    render.add_argument("--source-root", type=Path, required=True)
    render.add_argument("--duration", type=float, required=True)
    render.add_argument("--width", type=int, default=1280)
    render.add_argument("--height", type=int, default=720)
    episode = sub.add_parser("assemble", help="assemble pre-rendered MP4 clips using stream copy")
    episode.add_argument("output", type=Path)
    episode.add_argument("clips", type=Path, nargs="+")
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
            report = render_clip(args.source_root, args.panel, args.audio, args.output,
                                 args.duration, args.width, args.height)
        elif args.command == "probe":
            report = probe_media(args.file)
        elif args.command == "audit-source":
            report = audit_source_image(args.source_root, args.image, args.sha256)
        else:
            if not args.manifest.is_file() or args.manifest.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("manifest missing or larger than 8 MiB")
            with args.manifest.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
            report = (validate(manifest, args.source_root) if args.command == "validate"
                      else certify(manifest, args.source_root, args.render))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 2
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(json.dumps({"status": "ERROR", "errors": [str(exc)]}), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
