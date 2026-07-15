---
name: deps-bump
description: Safely update Txtify dependencies or resolve Dependabot alerts. Use when asked to bump packages, fix security alerts, or when a Dependabot PR appears.
---

# Dependency updates for Txtify

## Ground rules

1. **`torch` and `torchaudio` move together, same version.** A mismatch doesn't fail the build — it crashes the worker at import, and jobs just hang at 10%. This is the #1 trap.
2. **`stable-ts` ≥ 2.19.1** so pip resolves an `openai-whisper` that builds under modern setuptools (older ones import `pkg_resources` in setup.py and break the Docker build). Check stable-ts's `openai-whisper` constraint before bumping torch far ahead.
3. Before adding any package, and before "fixing" an alert on one: check it's actually imported — `grep -rn '<pkg>' src/`. Unused packages get deleted, not bumped (transformers/accelerate/srt/webvtt-py died this way).
4. `yt-dlp` rots fastest and breaks YouTube downloads silently. After bumping, verify with a **real download** (host venv is fine):
   ```python
   import yt_dlp
   opts = {"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}], "outtmpl": "yt_test.%(ext)s", "quiet": True}
   yt_dlp.YoutubeDL(opts).download(["https://www.youtube.com/watch?v=jNQXAC9IVRw"])  # 19s clip
   ```
5. Runtime deps go in `requirements.txt`; test-only deps (pytest, httpx, pypdf) in `requirements-dev.txt`. Don't ship test tooling in the image.

## Checking alerts

```sh
gh api repos/lkmeta/txtify/dependabot/alerts --paginate \
  --jq '.[] | select(.state=="open") | [.security_advisory.severity, .dependency.package.name, .security_vulnerability.vulnerable_version_range, (.security_vulnerability.first_patched_version.identifier // "none")] | @tsv'
```

Pick the newest version that is explicitly patched in the alert set rather than blindly taking latest — conservative for the ML stack, current for everything else. Alerts auto-resolve after GitHub rescans the updated manifest (minutes to hours); don't chase the counter.

## Verification (non-negotiable)

Any `requirements.txt` change requires the full Docker E2E — the unit tests stub the ML stack and will pass even when the worker can't import: run the `verify` skill, Tier 2 (`./scripts/docker_e2e.sh` → `PASS: docker E2E complete`).
