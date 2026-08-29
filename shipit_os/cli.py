#!/usr/bin/env python3
"""Shipit OS CLI — one command to ship any folder."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from . import __version__
from .detector import detect, DetectionResult
from .git_utils import (
    GitError,
    ensure_git_repo,
    ensure_remote,
    fix_sdcard_permissions,
    get_remote_url,
    is_git_repo,
    push,
    stage_and_commit,
)
from .workflow import write_workflow
from .buildozer_spec import ensure_buildozer_spec

console = Console()


# ── Cool terminal aesthetic ──────────────────────────────────────────────

def banner():
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]%echo%[/] [bold white]buildprocess[/] [bold green]shipit[/]\n"
            "[dim]One command → APK + PIP + Pages. No SDK. No NDK.[/]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()


def log(msg: str, style: str = ""):
    console.print(f"[bold cyan][*][/] {msg}", style=style)


def ok(msg: str):
    console.print(f"[bold green][✓][/] {msg}")


def warn(msg: str):
    console.print(f"[bold yellow][!][/] {msg}")


def err(msg: str):
    console.print(f"[bold red][✗][/] {msg}")


def die(msg: str, code: int = 1):
    err(msg)
    sys.exit(code)


# ── Core actions ─────────────────────────────────────────────────────────

def do_detect(cwd: Path, force_entry: Optional[str] = None) -> DetectionResult:
    log(f"Target: [bold]{cwd}[/]")
    log("Scanning...")
    result = detect(str(cwd), force_entry=force_entry)

    if result.entry_file:
        ok(f"Found entry: [bold]{result.entry_file}[/] → {result.entry_kind} (confidence {result.confidence:.0%})")
    else:
        warn("No clear entry point detected")
    for n in result.notes:
        console.print(f"    [dim]• {n}[/]")
    return result


def do_clean(cwd: Path):
    log("Cleaning local build artifacts...")
    removed = []
    for name in ("bin", "dist", ".buildozer", "build", "*.egg-info"):
        p = cwd / name
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
            removed.append(name)
    # Also clear egg-info globs
    for p in cwd.glob("*.egg-info"):
        shutil.rmtree(p, ignore_errors=True)
        removed.append(p.name)
    if removed:
        ok(f"Removed: {', '.join(removed)}")
    else:
        ok("Nothing to clean")


def do_status(cwd: Path):
    log("Checking repository status...")
    if not is_git_repo(cwd):
        warn("Not a git repository yet")
        return
    remote = get_remote_url(cwd)
    if remote:
        ok(f"Remote: {remote}")
        # Try to extract owner/repo for Actions URL
        if "github.com" in remote:
            parts = remote.rstrip("/").replace(".git", "").split("/")
            if len(parts) >= 2:
                owner, repo = parts[-2], parts[-1]
                ok(f"Actions: https://github.com/{owner}/{repo}/actions")
                ok(f"Releases: https://github.com/{owner}/{repo}/releases")
                ok(f"Pages:   https://{owner}.github.io/{repo}/")
    else:
        warn("No remote configured")


def prepare_and_push(
    cwd: Path,
    result: DetectionResult,
    targets: List[str],
    remote_url: Optional[str] = None,
) -> None:
    """Generate workflow, commit, and push."""
    fix_sdcard_permissions(cwd)

    log("Bypassing local SDK/NDK...")
    log("Generating buildozer.spec + cloud workflow...")

    # Only the two ship files: buildozer.spec + workflow yml (no main.py)
    if "apk" in targets or not targets:
        spec_path = ensure_buildozer_spec(cwd, entry_file=result.entry_file)
        ok(f"buildozer.spec: {spec_path.relative_to(cwd)}")

    wf_path = write_workflow(cwd, entry_file=result.entry_file)
    ok(f"Workflow written: {wf_path.relative_to(cwd)}")

    # Ensure git
    if not is_git_repo(cwd):
        log("No git repo — initializing...")
        ensure_git_repo(cwd)
        ok("git init done")

    if remote_url:
        ensure_remote(cwd, remote_url)
        ok(f"Remote set: {remote_url}")
    elif not get_remote_url(cwd):
        warn("No git remote found.")
        console.print(
            "\n[dim]Create a GitHub repo, then either:[/]\n"
            "  1. git remote add origin https://github.com/YOU/REPO.git\n"
            "  2. Re-run with: shipit shipit --remote https://github.com/YOU/REPO.git\n"
        )
        # Still commit locally so user can push later
        stage_and_commit(cwd, "shipit: add cloud build workflow")
        ok("Changes committed locally. Push when ready.")
        return

    # Commit
    committed = stage_and_commit(cwd, f"shipit: cloud build ({','.join(targets)})")
    if committed:
        ok("Committed workflow + project files")
    else:
        log("Nothing new to commit")

    # Push
    log("Uploading payload to cloud builder...")
    try:
        push(cwd)
        remote = get_remote_url(cwd) or remote_url or ""
        ok("Pushed to origin")
        if "github.com" in remote:
            parts = remote.rstrip("/").replace(".git", "").split("/")
            if len(parts) >= 2:
                owner, repo = parts[-2], parts[-1]
                ok(f"Build started: https://github.com/{owner}/{repo}/actions")
                console.print()
                console.print(
                    Panel.fit(
                        f"[bold green]Done.[/]\n"
                        f"APK → Releases\n"
                        f"Site → https://{owner}.github.io/{repo}/\n"
                        f"(Wheel → PyPI if PYPI_TOKEN secret is set)",
                        border_style="green",
                        title="Shipit",
                    )
                )
    except GitError as e:
        err(str(e))
        console.print(
            "\n[dim]Common fixes:[/]\n"
            "  • gh auth login   (or set up SSH / personal access token)\n"
            "  • Make sure the remote repo exists on GitHub\n"
        )
        raise


def cmd_shipit(args):
    cwd = Path(args.cwd or os.getcwd()).resolve()
    banner()

    targets = []
    if args.apk or args.all:
        targets.append("apk")
    if args.pip or args.all:
        targets.append("pip")
    if args.pages or args.all:
        targets.append("pages")
    if not targets:
        targets = ["apk", "pip", "pages"]  # default full ship

    result = do_detect(cwd, force_entry=args.entry)

    if args.dry_run:
        log("Dry-run — generate buildozer.spec + workflow, do not push")
        if "apk" in targets or args.all:
            spec = ensure_buildozer_spec(cwd, entry_file=result.entry_file)
            ok(f"Wrote {spec.relative_to(cwd)}")
        wf = write_workflow(cwd, entry_file=result.entry_file)
        ok(f"Wrote {wf.relative_to(cwd)} (dry-run)")
        return

    try:
        prepare_and_push(cwd, result, targets, remote_url=args.remote)
    except GitError:
        sys.exit(1)


def cmd_status(args):
    cwd = Path(args.cwd or os.getcwd()).resolve()
    banner()
    do_status(cwd)


def cmd_clean(args):
    cwd = Path(args.cwd or os.getcwd()).resolve()
    banner()
    do_clean(cwd)


def cmd_detect(args):
    cwd = Path(args.cwd or os.getcwd()).resolve()
    banner()
    do_detect(cwd, force_entry=args.entry)


# ── Argument parser ──────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipit",
        description="Shipit OS — one command to ship any folder to APK + PyPI + GitHub Pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  shipit                          # full ship (apk + pip + pages)
  shipit apk                      # APK only
  shipit pip                      # wheel only
  shipit pages                    # GitHub Pages only
  shipit --entry Euler.py         # force entry file
  shipit --remote https://github.com/you/repo.git
  shipit --dry-run                # generate workflow only
  shipit status
  shipit clean
  shipit detect
        """,
    )
    parser.add_argument("-V", "--version", action="version", version=f"shipit-os {__version__}")

    # Top-level options (work with bare `shipit` and are inherited by subcommands via parent)
    parser.add_argument("--entry", "-e", help="Force entry file (e.g. Euler.py)")
    parser.add_argument("--remote", "-r", help="Git remote URL (https://github.com/you/repo.git)")
    parser.add_argument("--cwd", help="Working directory (default: current)")
    parser.add_argument("--dry-run", action="store_true", help="Generate workflow only, do not push")

    sub = parser.add_subparsers(dest="command")

    # Shared parent for ship-style subcommands
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--entry", "-e", help="Force entry file (e.g. Euler.py)")
    parent.add_argument("--remote", "-r", help="Git remote URL")
    parent.add_argument("--cwd", help="Working directory")
    parent.add_argument("--dry-run", action="store_true", help="Generate workflow only")

    for name in ("shipit", "apk", "pip", "pages"):
        p = sub.add_parser(name, parents=[parent], help=f"Run {name} target(s)")
        p.set_defaults(func=cmd_shipit)
        if name == "apk":
            p.set_defaults(apk=True, pip=False, pages=False, all=False)
        elif name == "pip":
            p.set_defaults(apk=False, pip=True, pages=False, all=False)
        elif name == "pages":
            p.set_defaults(apk=False, pip=False, pages=True, all=False)
        else:
            p.set_defaults(apk=False, pip=False, pages=False, all=True)

    # status
    p_status = sub.add_parser("status", help="Check cloud build status / links")
    p_status.add_argument("--cwd", help="Working directory")
    p_status.set_defaults(func=cmd_status)

    # clean
    p_clean = sub.add_parser("clean", help="Clean local bin/ dist/ .buildozer")
    p_clean.add_argument("--cwd", help="Working directory")
    p_clean.set_defaults(func=cmd_clean)

    # detect
    p_detect = sub.add_parser("detect", help="Only scan and show detected entry point")
    p_detect.add_argument("--entry", "-e", help="Force entry file")
    p_detect.add_argument("--cwd", help="Working directory")
    p_detect.set_defaults(func=cmd_detect)

    return parser


def main(argv: Optional[List[str]] = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # Allow bare `shipit` / `shipit --dry-run` = full shipit
    if args.command is None:
        args.command = "shipit"
        args.func = cmd_shipit
        args.apk = False
        args.pip = False
        args.pages = False
        args.all = True

    # Normalise flags for subcommands that didn't set them
    for attr in ("apk", "pip", "pages", "all", "entry", "remote", "cwd", "dry_run"):
        if not hasattr(args, attr):
            setattr(args, attr, None if attr in ("entry", "remote", "cwd") else False)

    args.func(args)


if __name__ == "__main__":
    main()
