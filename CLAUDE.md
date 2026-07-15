# Txtify — agent guide

FastAPI web app that transcribes/translates audio & video: YouTube URL or upload → Whisper via stable-ts → optional DeepL translation → export as txt/srt/vtt/sbv/pdf. Single Docker container on port 8011, Jinja2 templates + vanilla JS frontend, SQLite for job state. Live at txtify.lkmeta.com (deployed from Docker Hub `lkmeta/txtify`). The public marketing site lives in the separate `lkmeta/txtify-web` repo — never edit site content here.

## Architecture (read this before touching job flow)

- `src/main.py` — all HTTP endpoints. `POST /transcribe` inserts a DB row (the **job id**), then `handle_transcription` spawns a detached worker subprocess and stores its **OS pid** in the same row. The frontend polls `GET /status?pid=<job id>` — the query param is named `pid` for historical reasons but **it is the job id, not the OS pid**. Keep it that way; the OS pid (row column 12) is only for cancellation/kill.
- `src/utils.py` — media download/upload handling, worker spawn, format converters (srt/vtt/sbv/pdf). `MAX_UPLOAD_SIZE_MB` / `MAX_VIDEO_DURATION` live here — **when changing them, update the copy in `templates/index.html` and `templates/faq.html` too.**
- `src/transcribe_process.py` — worker entrypoint; receives the job id as `argv[1]`. Never look up "the latest row" — that reintroduces the concurrency race fixed in #15.
- `src/models.py` — stable-ts transcription + DeepL translation. DeepL may merge/split lines; `save_final_transcription` aligns best-effort and must never raise on count mismatch.
- `src/db.py` — per-operation SQLite connections with WAL (async handlers + worker subprocesses share the file). Don't add a module-level shared connection.
- Job outputs live in `output/<job id>/`; `output/` is gitignored and dockerignored — media, transcripts, and `.db` files must never be committed or baked into the image.

## Commands

```sh
pytest                      # 32+ unit/API tests; runs WITHOUT torch installed
                            # (tests/conftest.py stubs torch/stable_whisper)
./scripts/docker_e2e.sh     # full gate: docker build → boot → real transcription
                            # → preview/download checks. Ends with "PASS: docker E2E complete"
uvicorn main:app --port 8011   # run locally (from src/); ffmpeg required
```

For quick local work you don't need the ML stack: install `requirements-dev.txt` minus `torch`/`torchaudio`/`stable-ts` (see `.github/workflows/tests.yml` for the exact recipe). Anything touching the worker/transcription path must be verified with `scripts/docker_e2e.sh` — the unit tests stub the model.

## Invariants & known traps

- `torch` and `torchaudio` must be pinned to the **same version** — a mismatch crashes the worker at import (`_torchaudio.abi3.so`), silently: status just sticks at 10%.
- `stable-ts` must stay ≥ 2.19.1 so pip picks an `openai-whisper` that builds under modern setuptools.
- PDF export uses fpdf2 with the bundled `static/fonts/DejaVuSans.ttf` — never reintroduce latin-1 encoding (Greek/Cyrillic output is a core use case). `multi_cell` needs `new_x="LMARGIN", new_y="NEXT"`.
- `transformers`, `accelerate`, `srt`, `webvtt-py` were removed as unused — don't re-add without an actual import.
- Product name is **Txtify**, never "Textify".
- Worker failures are invisible in the server log (stdout/stderr piped and unread). Debug via `output/<job id>_logs.txt`, or run `python src/transcribe_process.py <job_id> <file> en whisper_tiny none en all` manually.

## Conventions

- Conventional-commit messages; no AI attribution lines. Branch from `main`; never push to `main` directly.
- PR bodies: Problem / Change / How it was verified (with real command output) / Deferred.
- Merging stacked PRs: `gh pr edit --base main` can **fail silently** (GraphQL error) — always re-check `baseRefName` before `gh pr merge`, or you'll merge into a stack branch.
- CI: `Tests` (pytest, every PR) and `Docker Image CI` (image build) must both be green before merge.
