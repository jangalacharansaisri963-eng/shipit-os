# Shipit OS

**One command to ship ANY folder → APK + PyPI + GitHub Pages.**  
No SDK. No NDK. No setup.

Built for people who code on their phone in **Acode / Termux / /sdcard/** and just want to ship.

```bash
pip install shipit-os
cd /sdcard/Download/MyGame
shipit
```

## What it does

```
%echo% buildprocess shipit
[*] Target: /sdcard/AcodeProjects/RetroGame
[*] Scanning...
[✓] Found entry: game.py → main (confidence 85%)
[*] Bypassing local SDK/NDK...
[*] Uploading payload to cloud builder...
[✓] Build started: github.com/you/RetroGame/actions
[✓] Done. APK → Releases | Site → you.github.io/RetroGame
```

1. **Smart auto-detect** – finds `if __name__ == "__main__"`, `def main()`, Flask/FastAPI, Kivy, pygame, `index.html`, etc. No forced `main.py`.
2. **Works anywhere** – uses `os.getcwd()`, auto `git init`, handles `/sdcard/` permissions.
3. **Zero heavy tooling on device** – local CLI is tiny. GitHub Actions (with Buildozer) does the APK build.
4. **Three outputs in ~5–15 min**:
   - `bin/*.apk` → GitHub Releases
   - `dist/*.whl` → PyPI (if you set `PYPI_TOKEN` secret)
   - Live site → `username.github.io/repo`

## Install

```bash
pip install shipit-os
```

## Commands

| Command | Meaning |
|---------|---------|
| `shipit` | Full ship (APK + wheel + Pages) |
| `shipit apk` | APK only |
| `shipit pip` | Wheel only |
| `shipit pages` | GitHub Pages only |
| `shipit status` | Show Actions / Releases / Pages links |
| `shipit clean` | Remove local `bin/`, `dist/`, `.buildozer` |
| `shipit detect` | Only scan & print entry point |
| `shipit --entry Euler.py` | Force a specific entry file |
| `shipit --remote https://github.com/you/repo.git` | Set remote in one go |
| `shipit --dry-run` | Generate workflow, don’t push |

## First-time setup (once per machine)

1. Install Git + GitHub CLI (or configure SSH / PAT).
2. Create an empty GitHub repo (or let Shipit push to an existing remote).
3. (Optional) Add repository secret `PYPI_TOKEN` for automatic PyPI upload.
4. (Optional) Enable GitHub Pages in repo settings → Source: GitHub Actions.

Then from any project folder:

```bash
shipit
```

## How the cloud build works

Shipit writes `.github/workflows/ship.yml` and pushes it. The workflow:

- Builds a wheel (if packaging metadata exists)
- Runs **Buildozer** on Ubuntu to produce an Android APK
- Deploys a simple (or your existing) site to GitHub Pages
- Uploads the APK as a GitHub Release asset

You never install the Android SDK/NDK on your phone.

## Project detection

Shipit looks for (in order of preference):

- Files containing `if __name__ == "__main__"` + `def main()`
- Flask / FastAPI / Kivy / pygame apps
- Well-known names: `main.py`, `app.py`, `game.py`, `run.py`
- `index.html` / `game.js` for pure web projects

Override any time with `--entry`.

## Limitations (v0.1)

- APK builds currently assume a Kivy-friendly layout (or you supply your own `buildozer.spec`). Pure console scripts will need a thin Kivy/Android entry later.
- First Buildozer run on GitHub Actions can take 10–20 minutes (cached afterwards).
- PyPI publish requires you to set the `PYPI_TOKEN` secret.
- You still need a GitHub account and a repo.

## License

MIT
