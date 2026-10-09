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
    if len(clips) > 10000:
        errors.append('clip count exceeds safety limit')
        clips = clips[:10000]
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
        elif type(clip.get('event_continuation', False)) is not bool:
            errors.append(f'{label}: event_continuation must be boolean')
        elif event in seen_events and clip.get('event_continuation') is not True:
            errors.append(f'{label}: duplicate event without continuation')
        elif event not in seen_events and clip.get('event_continuation') is True:
            errors.append(f'{label}: continuation references unseen event')
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


def audit_source_image(root: Path, relative: object, expected_sha256: object) -> dict:
    """Strict source preflight. Signature and hash do NOT prove image decodability or license."""
    errors: list[str] = []
    path = _safe_source(root, relative)
    if path is None:
        return {'status': 'FAIL', 'errors': ['unsafe or missing source']}
    if not isinstance(expected_sha256, str) or not _HASH.fullmatch(expected_sha256):
        errors.append('invalid expected SHA-256')
    suffix = path.suffix.lower()
    try:
        with path.open('rb') as stream:
            header = stream.read(16)
        recognized = (
            (suffix == '.png' and header.startswith(b'\x89PNG\r\n\x1a\n')) or
            (suffix in ('.jpg', '.jpeg') and header.startswith(b'\xff\xd8\xff')) or
            (suffix == '.webp' and header.startswith(b'RIFF') and header[8:12] == b'WEBP')
        )
        if not recognized:
            errors.append('unsupported or invalid image signature')
        if isinstance(expected_sha256, str) and _HASH.fullmatch(expected_sha256) and file_hash(path) != expected_sha256:
            errors.append('source hash mismatch')
    except OSError:
        errors.append('source could not be read')
    return {'status': 'FAIL' if errors else 'PASS', 'errors': errors,
            'note': 'Signature and hash only; decoding, semantic grounding and license proof not verified'}
