"""Explicit-consent YouTube *private draft* uploader (optional Google API extra).

Never makes a video public, never skips platform OAuth, never retries
uncertain API writes, and leaves an auditable receipt. No thumbnail or source
permission is implicitly granted by uploaded metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from .core import file_hash
from .qc import decode_check

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def validate_private_upload(video: Path, metadata: dict,
                            client_secrets: Path, token_file: Path,
                            receipt: Path, made_for_kids: bool,
                            confirmed: bool, thumbnail: Path | None = None) -> dict:
    errors = []
    if confirmed is not True:
        errors.append("explicit --confirm-private-upload is required")
    if type(made_for_kids) is not bool:
        errors.append("explicit yes/no made-for-kids declaration required")
    if not isinstance(video, Path) or video.suffix.lower() != ".mp4" or video.is_symlink() or not video.is_file():
        errors.append("video must be an existing non-symlink MP4")
    if not isinstance(metadata, dict):
        errors.append("metadata JSON object required")
        metadata = {}
    if metadata.get("privacyStatus") != "private":
        errors.append("only private YouTube uploads are allowed")
    title = metadata.get("title")
    description = metadata.get("description")
    tags = metadata.get("tags", [])
    if not isinstance(title, str) or not 10 <= len(title.strip()) <= 100:
        errors.append("YouTube title must be 10–100 characters")
    if not isinstance(description, str) or len(description) > 5000:
        errors.append("YouTube description invalid")
    if not isinstance(tags, list) or len(tags) > 30 or any(
            not isinstance(v, str) or not v.strip() or len(v) > 80 for v in tags):
        errors.append("invalid tags")
    if not isinstance(client_secrets, Path) or client_secrets.is_symlink() or not client_secrets.is_file():
        errors.append("OAuth client secret JSON missing/unsafe")
    if not isinstance(token_file, Path) or token_file.suffix.lower() != ".json" or token_file.is_symlink():
        errors.append("OAuth token output must be a non-symlink JSON path")
    if (not isinstance(receipt, Path) or receipt.suffix.lower() != ".json"
            or receipt.is_symlink() or receipt.exists()):
        errors.append("receipt must be a NEW, non-symlink JSON path to prevent duplicate uploads")
    if thumbnail is not None:
        if (not isinstance(thumbnail, Path) or thumbnail.suffix.lower() not in (".jpg", ".jpeg")
                or not thumbnail.is_file() or thumbnail.is_symlink()):
            errors.append("thumbnail must be an existing JPG file")
        elif thumbnail.stat().st_size > 2_000_000:
            errors.append("thumbnail exceeds 2 MB")
    if (isinstance(receipt, Path) and isinstance(video, Path)
            and receipt.resolve() == video.resolve()):
        errors.append("receipt must not overlap video")
    return {"status": "FAIL" if errors else "PASS", "errors": errors}


def _persist_token(token_file: Path, contents: str) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ashentoons-oauth-", suffix=".json",
                                 dir=token_file.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(contents, encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, token_file)
    finally:
        tmp.unlink(missing_ok=True)


def _write_receipt(path: Path, payload: dict, create: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if create:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return
    # Only the previously created receipt path may be updated.
    if not path.exists() or path.is_symlink():
        raise OSError("receipt vanished or became unsafe")
    fd, name = tempfile.mkstemp(prefix=".ashentoons-receipt-", suffix=".json",
                                 dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def upload_private_draft(video: Path, metadata: dict, client_secrets: Path,
                         token_file: Path, receipt: Path, made_for_kids: bool,
                         confirmed: bool = False,
                         thumbnail: Path | None = None) -> dict:
    """Upload one private draft after independent technical preflight and OAuth.

    A receipt is created BEFORE the upload request. If an exception occurs
    afterward, the upload state is UNCERTAIN: inspect YouTube Studio before
    considering a new upload. No automatic second attempt is made.
    """
    preflight = validate_private_upload(
        video, metadata, client_secrets, token_file, receipt,
        made_for_kids, confirmed, thumbnail)
    if preflight["status"] != "PASS":
        return preflight
    tested = decode_check(video)
    if tested["status"] != "PASS":
        return {"status": "FAIL", "errors": ["video failed complete audio/video decoding"],
                "detail": tested}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {"status": "FAIL", "errors": [
            "Google API extra missing: pip install -e '.[youtube]'"]}
    try:
        credentials = None
        if token_file.exists():
            credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
                credentials = flow.run_local_server(port=0)
            _persist_token(token_file, credentials.to_json())
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    except Exception:
        return {"status": "FAIL", "errors": ["OAuth failed; inspect client secrets and your browser authorization"]}

    upload_record = {
        "status": "UNCERTAIN", "video_sha256": file_hash(video),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_id": None, "privacyStatus": "private",
        "note": "Upload may have occurred. Check YouTube Studio before retrying.",
    }
    try:
        _write_receipt(receipt, upload_record, create=True)
    except OSError:
        return {"status": "FAIL", "errors": ["could not create single-upload receipt; upload not attempted"]}

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "tags": metadata.get("tags", []),
                    "categoryId": "24",
                },
                "status": {
                    "privacyStatus": "private",
                    "selfDeclaredMadeForKids": made_for_kids,
                },
            },
            media_body=MediaFileUpload(
                str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024,
                resumable=True),
        )
        result = None
        while result is None:
            _progress, result = request.next_chunk()
        video_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(video_id, str) or not _VIDEO_ID.fullmatch(video_id):
            raise ValueError("unexpected YouTube response")
        upload_record["video_id"] = video_id
        upload_record["status"] = "UPLOADED_PRIVATE"
        upload_record["url"] = "https://www.youtube.com/watch?v=" + video_id
        _write_receipt(receipt, upload_record)
        if thumbnail is not None:
            try:
                youtube.thumbnails().set(
                    videoId=video_id, media_body=str(thumbnail)).execute()
                upload_record["thumbnail_set"] = True
                _write_receipt(receipt, upload_record)
            except Exception:
                upload_record["status"] = "UPLOADED_PRIVATE_THUMBNAIL_PENDING"
                upload_record["thumbnail_set"] = False
                _write_receipt(receipt, upload_record)
                return {"status": "PARTIAL", "url": upload_record["url"],
                        "receipt": str(receipt), "privacyStatus": "private",
                        "errors": ["private upload succeeded, thumbnail requires manual retry"]}
        return {"status": "PASS", "url": upload_record["url"],
                "receipt": str(receipt), "privacyStatus": "private",
                "note": "Private draft only; no public release was made"}
    except Exception:
        # Never retry automatically: request may already have been accepted.
        try:
            _write_receipt(receipt, upload_record)
        except OSError:
            pass
        return {"status": "UNCERTAIN", "receipt": str(receipt),
                "errors": ["API upload result uncertain; inspect YouTube Studio before another attempt"]}
