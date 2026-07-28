"""Shared filesystem / fingerprint helpers for candidate isolation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Iterable


SKIP_NAMES = {
    ".git",
    ".harness",
    "runs",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "media",
    "partial_movie_files",
    "library",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    path = root / "harness.config.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_dotenv(root: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE). Does not override existing env."""
    root = root or project_root()
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def now_id(prefix: str = "run") -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES and not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") and name not in {".gitkeep"}:
                continue
            yield Path(dirpath) / name


def fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(iter_files(root), key=lambda p: str(p.relative_to(root))):
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for path in iter_files(src):
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


PRESERVE_ON_PROMOTE = {".git", "library"}


def promote(candidate: Path, workspace: Path, backup: Path | None = None) -> None:
    if backup is not None:
        if workspace.exists() and any(workspace.iterdir()):
            copy_tree(workspace, backup)
    # Replace workspace contents with candidate (keep workspace root + library archive)
    if workspace.exists():
        for child in list(workspace.iterdir()):
            if child.name in PRESERVE_ON_PROMOTE:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        workspace.mkdir(parents=True, exist_ok=True)
    for path in iter_files(candidate):
        rel = path.relative_to(candidate)
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
