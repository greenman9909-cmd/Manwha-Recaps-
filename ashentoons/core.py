"""Fail-closed, source-only manifest checks. No media certification is implied."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import math
import re

_HASH = re.compile(r'^[0-9a-f]{64}$')


def file_hash(path: Path) -> str:
    """Stream content rather than loading large panel assets into RAM."""
    digest = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_source(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        return None
    raw = Path(relative)
    if raw.is_absolute() or any(part in ('.', '..') for part in raw.parts):
        return None
    resolved_root = root.resolve()
    candidate = (resolved_root / raw).resolve()
    if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
        return None
    return candidate


def _time(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate(manifest: dict, root: Path) -> dict:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {'status': 'FAIL', 'errors': ['manifest must be an object'], 'clip_count': 0}
    if manifest.get('subtitles') is not False:
        errors.append('subtitles must be disabled')
    if manifest.get('generated_visuals') is not False:
        errors.append('generated visuals forbidden')
    if manifest.get('source_authorized') is not True:
        errors.append('source authorization required')
    voices = manifest.get('voices')
    if not isinstance(voices, dict) or not voices or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v
        for k, v in voices.items()
    ):
        errors.append('invalid voice registry')
        voices = {}
    mc = voices.get('MC')
    if not mc:
        errors.append('MC voice required')
    if mc and any(v == mc for k, v in voices.items() if k != 'MC'):
        errors.append('MC voice collision')
    clips = manifest.get('clips')
    if not isinstance(clips, list) or not clips:
        errors.append('clips must be a nonempty list')
        clips = []
    last_end = 0.0
    seen_events: set[str] = set()
    hash_cache: dict[Path, str] = {}
    for i, clip in enumerate(clips):
        label = f'clip[{i}]'
        if not isinstance(clip, dict):
            errors.append(f'{label}: invalid clip object')
            continue
        panel = _safe_source(root, clip.get('panel'))
        if panel is None:
            errors.append(f'{label}: missing/escaped/invalid source')
        else:
            expected = clip.get('panel_sha256')
            if not isinstance(expected, str) or not _HASH.fullmatch(expected):
                errors.append(f'{label}: invalid source hash')
            else:
                if panel not in hash_cache:
                    hash_cache[panel] = file_hash(panel)
                if hash_cache[panel] != expected:
                    errors.append(f'{label}: source hash mismatch')
        speaker = clip.get('speaker')
        if not isinstance(speaker, str) or speaker not in voices:
            errors.append(f'{label}: unknown speaker')
        if clip.get('voice') != voices.get(speaker) or not voices.get(speaker):
            errors.append(f'{label}: voice mismatch')
        event = clip.get('event_id')
        if not isinstance(event, str) or not event.strip():
            errors.append(f'{label}: missing grounded event')
        elif event in seen_events and not clip.get('event_continuation', False):
            errors.append(f'{label}: duplicate event without continuation')
        else:
            seen_events.add(event)
        if not isinstance(clip.get('narration'), str) or not clip['narration'].strip():
            errors.append(f'{label}: missing narration')
        start, end = clip.get('start'), clip.get('end')
        if not _time(start) or not _time(end) or start < 0 or end <= start:
            errors.append(f'{label}: invalid timing')
        elif start < last_end - 1e-6:
            errors.append(f'{label}: overlapping or out-of-order timing')
        else:
            last_end = end
    return {'status': 'FAIL' if errors else 'PASS', 'errors': errors, 'clip_count': len(clips)}


def certify(manifest: dict, root: Path, rendered: Path) -> dict:
    report = validate(manifest, root)
    if not rendered.is_file() or rendered.stat().st_size == 0:
        report['errors'].append('missing/empty render')
    else:
        report['render_sha256'] = file_hash(rendered)
    report['status'] = 'NOT_CERTIFIED'
    report['release_allowed'] = False
    report['missing_checks'] = ['decoded frame inspection', 'speech verification', 'semantic panel alignment', 'independent QC']
    return report
