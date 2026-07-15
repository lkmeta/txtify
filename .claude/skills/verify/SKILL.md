---
name: verify
description: Verify a Txtify change end-to-end. Use before committing any nontrivial change, when asked to "verify", "test this", or "make sure nothing breaks", and always after touching the worker/transcription path, dependencies, or the Dockerfile.
---

# Verifying Txtify changes

Two tiers. Pick the cheapest one that actually exercises the change.

## Tier 1 — unit/API tests (seconds, no ML stack needed)

```sh
pytest -q
```

Covers: format converters (incl. PDF Unicode round-trip), filename/URL/upload validation, job-id DB flow, `/health`, `/transcribe` error paths, DeepL alignment edge cases. `tests/conftest.py` stubs `torch`/`stable_whisper` when absent, so a light venv is enough:

```sh
grep -v -E '^(torch|stable-ts)' requirements.txt > /tmp/reqs.txt
pip install -r /tmp/reqs.txt pytest httpx pypdf
```

Sufficient on its own only for changes fully covered by tests (converters, validation, endpoint logic).

## Tier 2 — Docker E2E (the real gate, ~5–10 min)

```sh
./scripts/docker_e2e.sh
```

Builds the image, boots a container, checks `/health` + all pages + 404s, uploads a generated clip, runs a **real whisper-tiny transcription** to 100%, validates preview in all four formats, downloads the zip and confirms the PDF is in it, and checks validation errors. Success is the literal line `PASS: docker E2E complete`.

**Mandatory** for changes to: `requirements.txt`, `Dockerfile`, `.dockerignore`, `src/transcribe_process.py`, `src/models.py`, the worker-spawn path in `src/utils.py`.

## Reading failures

- Status stuck at **10%** → worker crashed at import (classic cause: torch/torchaudio version mismatch). Reproduce inside the container:
  `docker exec <name> python /app/src/transcribe_process.py 99 output/<clip> en whisper_tiny none en all`
- Status stuck at **30%** for a long time → model download in progress; not a failure yet.
- Job errors mid-run → `docker exec <name> cat output/<job id>_logs.txt` (the server log won't show worker errors).
- The E2E script's container is removed on exit; to debug interactively, `docker run -d --rm --name txtify_dbg -p 8078:8011 txtify:e2e` and drive it with curl.

## What "verified" means in a PR body

Paste the actual output: the pytest summary line and/or the `PASS: docker E2E complete` line. A claim without output doesn't count.
