# Maintenance plan (July 2026)

Codebase audit → fixes landed as a stack of 5 PRs. Merge in order; each PR's base is the previous branch, so GitHub retargets automatically as they merge.

| # | Branch | Issues addressed |
|---|--------|-----------------|
| 1 | `fix/health-hygiene-docs` | Real `/health` endpoint (docker healthcheck was false-passing via the catch-all), catch-all returns 404, contact email + Resend header moved to env/uuid, `.env.example` cleanup (drop unused `HUGGINGFACE_API_KEY`), gitignore media/transcripts, README truth pass (no "simulation"/"monitoring"), modern `TemplateResponse` signature |
| 2 | `fix/pdf-unicode` | PDF export corrupts non-Latin text (latin-1 + abandoned fpdf 1.7.2) → fpdf2 with bundled Unicode font |
| 3 | `fix/job-identity-sqlite` | Job-identity race ("latest row" lookups cross-wire concurrent jobs) → explicit job id through subprocess argv; SQLite WAL + per-operation connections; relative subprocess path (runs outside Docker); graceful DeepL line-count mismatch handling; dead conda block removed |
| 4 | `feat/upload-limits-streaming` | Limits 100MB/10min → 1000MB/15min, uploads streamed to disk (no more double full read into memory), user-facing copy updated (index + FAQ), accepted upload formats widened |
| 5 | `chore/deps-and-tests` | Dependency refresh — fixes all open Dependabot alerts (torch critical, yt-dlp, python-multipart highs; removes unused transformers/accelerate/srt/webvtt-py entirely), `whisper_large` → large-v3, first pytest suite (converters, clean_filename, job-id flow, `/health`, `/transcribe` validation) |

Verification: pytest suite in PR5, live uvicorn smoke tests per PR, and a full Docker build + end-to-end transcription (upload → status → preview → download, Greek PDF check, real YouTube download with new yt-dlp) on the integrated stack.
