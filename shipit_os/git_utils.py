"""Git helpers: init, commit, remote, push. Safe for /sdcard/ and non-repo folders."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class GitError(Exception):
    pass


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Command failed: {' '.join(cmd)}\n{e.stderr or e.stdout}") from e
    except FileNotFoundError:
        raise GitError("git is not installed or not in PATH") from None


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def ensure_git_repo(path: Path) -> None:
    """Initialize a git repo if one does not exist."""
    if not is_git_repo(path):
        _run(["git", "init"], cwd=path)
        # Reasonable defaults for phone environments
        _run(["git", "config", "user.email", "shipit@localhost"], cwd=path, check=False)
        _run(["git", "config", "user.name", "Shipit OS"], cwd=path, check=False)


def get_remote_url(path: Path, name: str = "origin") -> Optional[str]:
    try:
        r = _run(["git", "remote", "get-url", name], cwd=path, check=False)
        if r.returncode == 0:
            return r.stdout.strip()
    except GitError:
        pass
    return None


def ensure_remote(path: Path, url: str, name: str = "origin") -> None:
    existing = get_remote_url(path, name)
    if existing:
        if existing != url:
            _run(["git", "remote", "set-url", name, url], cwd=path)
    else:
        _run(["git", "remote", "add", name, url], cwd=path)


def stage_and_commit(path: Path, message: str = "shipit: cloud build workflow") -> bool:
    """Stage all and commit. Returns True if a commit was made."""
    _run(["git", "add", "-A"], cwd=path)
    # Check if there is anything to commit
    status = _run(["git", "status", "--porcelain"], cwd=path, check=False)
    if not status.stdout.strip():
        return False
    _run(["git", "commit", "-m", message], cwd=path)
    return True


def current_branch(path: Path) -> str:
    r = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=False)
    if r.returncode == 0:
        return r.stdout.strip()
    return "main"


def push(path: Path, remote: str = "origin", branch: Optional[str] = None) -> None:
    br = branch or current_branch(path)
    # Set upstream on first push
    _run(["git", "push", "-u", remote, br], cwd=path)


def fix_sdcard_permissions(path: Path) -> None:
    """Best-effort permission fix for /sdcard/ style paths (Termux / Acode)."""
    try:
        # Make sure we can write .git and .github
        for d in [path / ".git", path / ".github"]:
            if d.exists():
                os.chmod(d, 0o755)
        # Try to make the directory itself writable
        os.chmod(path, 0o755)
    except Exception:
        pass  # Non-fatal on restricted filesystems
