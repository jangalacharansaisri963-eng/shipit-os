"""Generate a working buildozer.spec for the detected project."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "", name.lower())
    return s[:40] or "shipitapp"


def generate_buildozer_spec(
    root: Path,
    entry_file: Optional[str] = None,
    title: Optional[str] = None,
    package_name: Optional[str] = None,
    domain: str = "org.shipit",
    requirements: Optional[str] = None,
) -> str:
    """Return content of a minimal but working buildozer.spec."""
    folder = root.resolve()
    pkg = package_name or _slug(folder.name)
    app_title = title or folder.name.replace("_", " ").replace("-", " ").title() or "Shipit App"
    entry = entry_file or "main.py"

    reqs = requirements or "python3,kivy"

    req_txt = folder / "requirements.txt"
    if req_txt.exists() and not requirements:
        try:
            lines = [
                ln.strip().split("==")[0].split(">=")[0].split("<=")[0].strip()
                for ln in req_txt.read_text(encoding="utf-8", errors="ignore").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            extra = []
            for p in lines:
                pl = p.lower()
                if pl in ("kivy", "python3"):
                    continue
                if pl in ("pillow", "pil"):
                    extra.append("pillow")
                elif pl == "requests":
                    extra.append("requests")
                elif pl == "numpy":
                    extra.append("numpy")
                elif pl == "pygame":
                    extra.append("pygame")
            if extra:
                reqs = "python3,kivy," + ",".join(dict.fromkeys(extra))
        except Exception:
            pass

    include_exts = "py,png,jpg,jpeg,kv,atlas,ttf,txt,json,html,js,css,mp3,wav,ogg,gif,xml"

    # If entry is not main.py, tell user in comments; Buildozer still expects main.py
    # by convention — user owns their entry layout.
    entry_note = f"# Detected entry: {entry}"
    if entry != "main.py":
        entry_note += (
            "\n# Buildozer looks for main.py by default. "
            "Rename your entry to main.py or adjust source.dir / your app layout."
        )

    spec = f"""# Shipit OS generated buildozer.spec
# Edit title / package.name / requirements as needed, then re-run shipit.

[app]

# (str) Title of your application
title = {app_title}

# (str) Package name
package.name = {pkg}

# (str) Package domain (needed for android/ios packaging)
package.domain = {domain}

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.include_exts = {include_exts}

# (list) Source files to exclude
source.exclude_exts = spec,pyc,pyo

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, venv, .venv, .git, .github, dist, build, __pycache__

# (str) Application versioning
version = 0.1.0

# (list) Application requirements (comma separated)
requirements = {reqs}

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#------------------------------------------------------------------------------
# Android specific
#------------------------------------------------------------------------------

android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.logcat_filters = *:S python:D

{entry_note}

#------------------------------------------------------------------------------
# Buildozer settings
#------------------------------------------------------------------------------

[buildozer]

log_level = 2
warn_on_root = 0
"""
    return spec


def ensure_buildozer_spec(
    root: Path,
    entry_file: Optional[str] = None,
    force: bool = False,
) -> Path:
    """
    Write buildozer.spec if missing (or if force=True).
    Does NOT create main.py — only the two ship files: buildozer.spec + workflow.
    """
    root = root.resolve()
    spec_path = root / "buildozer.spec"

    if spec_path.exists() and not force:
        return spec_path

    content = generate_buildozer_spec(root, entry_file=entry_file)
    spec_path.write_text(content, encoding="utf-8")
    return spec_path
