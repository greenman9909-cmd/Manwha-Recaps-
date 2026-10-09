"""Non-destructive workspace setup on a dedicated directory, e.g. D:\\AshenToons."""
from __future__ import annotations

from pathlib import Path

DIRECTORIES = (
    "sources", "narration", "exports", "cache",
    "temp", "reviews", "thumbnails", "manifests",
)


def initialize_workspace(root: Path) -> dict:
    if not isinstance(root, Path) or root.is_symlink():
        return {"status": "FAIL", "errors": ["workspace must be a directory, not a symlink"]}
    if root.parent == root or root == Path(".") or not root.name:
        return {"status": "FAIL", "errors": ["refusing to use a filesystem root as workspace"]}
    if root.exists() and not root.is_dir():
        return {"status": "FAIL", "errors": ["workspace path is a file"]}
    try:
        for name in DIRECTORIES:
            path = root / name
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                return {"status": "FAIL", "errors": [f"unsafe existing folder: {name}"]}
        root.mkdir(parents=True, exist_ok=True)
        for name in DIRECTORIES:
            (root / name).mkdir(exist_ok=True)
    except OSError as exc:
        return {"status": "FAIL", "errors": [f"cannot prepare workspace: {exc}"]}
    return {"status": "PASS", "workspace": str(root),
            "directories": list(DIRECTORIES), "files_deleted": 0,
            "note": "No existing files were modified or deleted"}
