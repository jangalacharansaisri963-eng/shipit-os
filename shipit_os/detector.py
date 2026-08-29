"""Smart entry-point and project-type detection."""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DetectionResult:
    entry_file: Optional[str] = None
    entry_kind: str = "unknown"  # main | flask | fastapi | kivy | pygame | html | js | unknown
    project_type: str = "python"  # python | web | hybrid
    has_requirements: bool = False
    has_setup: bool = False
    has_pyproject: bool = False
    has_index_html: bool = False
    has_game_js: bool = False
    found_files: List[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


# Common entry-point patterns
MAIN_GUARD = re.compile(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]')
DEF_MAIN = re.compile(r'def\s+main\s*\(')
FLASK_APP = re.compile(r'\bapp\s*=\s*Flask\s*\(')
FASTAPI_APP = re.compile(r'\bapp\s*=\s*FastAPI\s*\(')
KIVY_APP = re.compile(r'class\s+\w+\s*\(\s*App\s*\)')
PYGAME = re.compile(r'import\s+pygame|from\s+pygame')


def _safe_read(path: Path, max_bytes: int = 200_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def _score_python_file(path: Path) -> tuple[float, str, List[str]]:
    """Return (score, kind, notes) for a .py file."""
    content = _safe_read(path)
    if not content.strip():
        return 0.0, "unknown", []

    score = 0.0
    kind = "unknown"
    notes: List[str] = []

    has_main_guard = bool(MAIN_GUARD.search(content))
    has_def_main = bool(DEF_MAIN.search(content))
    has_flask = bool(FLASK_APP.search(content))
    has_fastapi = bool(FASTAPI_APP.search(content))
    has_kivy = bool(KIVY_APP.search(content))
    has_pygame = bool(PYGAME.search(content))

    if has_main_guard:
        score += 0.45
        notes.append("found if __name__ == '__main__'")
    if has_def_main:
        score += 0.25
        notes.append("found def main()")
    if has_flask:
        score += 0.6
        kind = "flask"
        notes.append("Flask app detected")
    if has_fastapi:
        score += 0.6
        kind = "fastapi"
        notes.append("FastAPI app detected")
    if has_kivy:
        score += 0.55
        kind = "kivy"
        notes.append("Kivy App class detected")
    if has_pygame:
        score += 0.4
        if kind == "unknown":
            kind = "pygame"
        notes.append("pygame import detected")

    # Prefer well-known names
    name = path.name.lower()
    if name in ("main.py", "app.py", "run.py", "game.py", "start.py"):
        score += 0.3
        notes.append(f"preferred name: {path.name}")
    elif name.endswith(".py") and not name.startswith("_"):
        score += 0.05

    if kind == "unknown" and (has_main_guard or has_def_main):
        kind = "main"

    return min(score, 1.0), kind, notes


def detect(cwd: Optional[str] = None, force_entry: Optional[str] = None) -> DetectionResult:
    """
    Scan the current working directory (or given path) and detect the best entry point.
    """
    root = Path(cwd or os.getcwd()).resolve()
    result = DetectionResult()

    if not root.is_dir():
        result.notes.append(f"Not a directory: {root}")
        return result

    # Collect candidate files
    py_files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root))
            # Skip common junk
            if any(part.startswith(".") for part in p.parts):
                continue
            if any(skip in p.parts for skip in ("__pycache__", "venv", ".venv", "node_modules", "dist", "build", "bin")):
                continue
            result.found_files.append(rel)

            if p.suffix == ".py":
                py_files.append(p)
            elif p.name.lower() == "index.html":
                result.has_index_html = True
            elif p.name.lower() in ("game.js", "main.js", "app.js"):
                result.has_game_js = True

    # Requirements / packaging markers
    result.has_requirements = (root / "requirements.txt").exists()
    result.has_setup = (root / "setup.py").exists() or (root / "setup.cfg").exists()
    result.has_pyproject = (root / "pyproject.toml").exists()

    # Force entry if requested
    if force_entry:
        forced = root / force_entry
        if forced.exists():
            score, kind, notes = _score_python_file(forced)
            result.entry_file = force_entry
            result.entry_kind = kind if kind != "unknown" else "main"
            result.confidence = max(score, 0.9)
            result.notes.extend(notes)
            result.notes.append(f"forced entry: {force_entry}")
            result.project_type = "python"
            return result
        else:
            result.notes.append(f"Forced entry not found: {force_entry}")

    # Score all Python files
    best_score = 0.0
    best_file: Optional[Path] = None
    best_kind = "unknown"
    best_notes: List[str] = []

    for pf in py_files:
        score, kind, notes = _score_python_file(pf)
        if score > best_score:
            best_score = score
            best_file = pf
            best_kind = kind
            best_notes = notes

    if best_file and best_score >= 0.3:
        result.entry_file = str(best_file.relative_to(root))
        result.entry_kind = best_kind
        result.confidence = best_score
        result.notes.extend(best_notes)
        result.project_type = "python"
    elif result.has_index_html or result.has_game_js:
        result.project_type = "web"
        result.entry_kind = "html" if result.has_index_html else "js"
        result.confidence = 0.7
        result.notes.append("Web project detected (index.html / game.js)")
        if result.has_index_html:
            result.entry_file = "index.html"
    else:
        # Last resort: any .py that isn't a test
        candidates = [p for p in py_files if "test" not in p.name.lower()]
        if candidates:
            # Prefer shorter path / shallower
            candidates.sort(key=lambda p: (len(p.parts), p.name))
            result.entry_file = str(candidates[0].relative_to(root))
            result.entry_kind = "main"
            result.confidence = 0.25
            result.notes.append(f"fallback entry: {result.entry_file}")
            result.project_type = "python"
        else:
            result.notes.append("No clear entry point found")
            result.confidence = 0.0

    return result
