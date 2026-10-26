# Publishing the Txtify skill on Agensi

How to list `skills/txtify-transcribe` on [Agensi](https://www.agensi.io), the SKILL.md marketplace, as a **free** skill. The goal is distribution: people looking for a transcription skill find Txtify and end up on GitHub.

Agensi's own docs, checked 2026-10-26: [quickstart](https://www.agensi.io/docs/creator-quickstart), [packaging](https://www.agensi.io/docs/packaging), [submit](https://www.agensi.io/docs/submit-on-the-website), [review](https://www.agensi.io/docs/review-and-approval), [FAQ](https://www.agensi.io/docs/creator-faq). If a field below doesn't match the form anymore, the form wins.

## What the skill is

- **Name:** `txtify-transcribe` (the listing name has to be unique on Agensi, max 60 characters)
- **Files:** `SKILL.md` + `references/options.md` (language and DeepL code tables). No scripts.
- **What it does:** finds or starts a local Txtify on `127.0.0.1:8011`, submits a local file or one YouTube URL, polls until it's done, and saves txt/srt/vtt/sbv (and pdf) into a folder the user picks. It uses the same HTTP endpoints Txtify's own web page calls.
- **Works against:** the published `lkmeta/txtify:latest` (v1.1, 2026-07-19) and current `main`. Differences are written into the skill: on v1.1, pdf is only in the zip, `mkv`/`avi` are rejected, and uploads are capped at 1000 MB and YouTube videos at 15 minutes by default.
- **Not supported, and the skill says so:** diarization, live/mic transcription, playlists, batch folders, a stable public API.
- **Who it's for:** people who want transcripts or subtitles without a cloud service and are fine running one Docker container. Typical users are creators, podcasters, researchers and anyone already self-hosting Txtify.
- **Prerequisites:** Docker (Docker Desktop on macOS/Windows), ~2-3 GB of disk for the image plus model weights, `curl`, and enough RAM for the model (about 10 GB for `whisper_large`, much less for the rest). A DeepL API key only for translation.
- **Agents:** any agent that loads SKILL.md files and can run shell commands: Claude Code, Codex CLI, Cursor, Gemini CLI and the rest Agensi supports. The commands are POSIX `sh` (macOS, Linux, WSL or Git Bash on Windows). An agent without a terminal gets the browser walkthrough instead. No agent has run the skill end to end yet. The scripts below run its commands directly, so try it in your own agent once it's live (see "After it goes live").

## How it was tested

- `scripts/skill_e2e.sh` runs the skill's commands against a real image and checks the files' contents, not just the status codes. It detects the build (v1.1 or newer) and requires that build's behavior. The step 5 and 6 snippets are pulled straight out of SKILL.md and run in a fresh `sh` with an empty environment, like an agent shell.
  - **Inputs:** mp3 audio, an mp4 video with a space and `;` in its name, mkv, and a YouTube video (`YT=1`)
  - **Outputs:** all five formats, the zip, and the overwrite guards
  - **Failures:** 400, 404, 422 and 429, missing file, unknown model, bad language (ends as `Error`), cancel, missing DeepL key, curl timeout, Txtify stopping mid-poll, and the `docker` client's error when no daemon is reachable
  - **Not covered:** the 500 response, an actual DeepL translation (needs a key) and YouTube's bot-check block (can't be triggered on purpose)
- `tests/test_skill.py` (runs in CI) fails when the app's models, formats, upload types, status strings or language lists drift away from what the skill says.

```sh
./scripts/docker_e2e.sh                        # builds the tree as txtify:e2e
IMAGE=txtify:e2e YT=1 ./scripts/skill_e2e.sh   # current code
docker pull lkmeta/txtify:latest && IMAGE=lkmeta/txtify:latest YT=1 ./scripts/skill_e2e.sh   # what users pull
```

## Build the ZIP

From the repo root:

```sh
rm -f dist/txtify-transcribe.zip && mkdir -p dist
(cd skills/txtify-transcribe && zip -r -X ../../dist/txtify-transcribe.zip SKILL.md references)
unzip -l dist/txtify-transcribe.zip   # expect SKILL.md at the top + references/options.md
```

`*.zip` is gitignored, so the archive never gets committed. Agensi blocks re-uploading an identical ZIP, so bump `version:` in the frontmatter whenever you resubmit.

## Listing content (copy into the form)

**Name**

```
Txtify Transcribe
```

**Summary** (max 300 characters)

```
Turn audio, video or a YouTube link into a transcript or subtitles (txt, srt, vtt, sbv, pdf) with your own self-hosted Txtify. Whisper runs on your machine in Docker, so your files don't go to a cloud transcription service.
```

**Description** (markdown)

```markdown
Your agent transcribes media with [Txtify](https://github.com/lkmeta/txtify), a free, open-source (Apache-2.0) Whisper app you run yourself in Docker.

Give it a file path or a YouTube link. It checks whether Txtify is already running on `localhost:8011`, offers to start it if not (and asks first, since that's a 2-3 GB image), uploads to your local instance, waits for the job and saves the transcript or subtitles in the folder you pick.

**What you get**
- txt, srt, vtt and sbv files, plus pdf (pdf comes from the zip on the current Docker image)
- five Whisper models, from `tiny` (fast) to `large` (most accurate, needs ~10 GB RAM)
- 72 spoken languages or auto-detect
- optional translation to 34 languages through DeepL, with your own API key

**How it treats your data**
- Whisper runs locally. Your media goes to your own container and nowhere else
- it asks before pulling images, starting containers, uploading a file or overwriting an output
- the container is bound to `127.0.0.1` only, because Txtify has no login
- YouTube jobs download from YouTube. Translation sends transcript text to DeepL. Both only happen when you choose them

**What it doesn't do**
No speaker labels, no live or mic transcription, no playlists. Txtify has no versioned public API: the skill uses the endpoints Txtify's own web page uses, and if they change it falls back to guiding you through the browser.

Built by the Txtify maintainer. Issues and stars welcome on [GitHub](https://github.com/lkmeta/txtify).
```

**See it in action** (real output from a test run on 2026-10-26: published v1.1 image, arm64, digest `sha256:d10a74ce…`, `whisper_tiny`)

```
Request:
"Transcribe https://www.youtube.com/watch?v=jNQXAC9IVRw to English subtitles and save them in ~/Videos/subs."

What the agent did:
1. Checked http://127.0.0.1:8011/health → {"status":"ok"}, page title "Txtify".
2. Confirmed the URL, model (whisper_tiny), language (en) and save folder with the user.
3. POST /transcribe → {"message":"Transcription started successfully.","pid":4}
4. Polled /status until:
   {"progress":"100","phase":"Completed successfully!","model":"whisper_tiny","language":"en","translation":"none","time_taken":"7.48"}
5. Checked ~/Videos/subs/me-at-the-zoo.srt didn't exist yet, then saved it.

Result (me-at-the-zoo.srt):
1
00:00:00,920 --> 00:00:05,700
Alright so here we are one of the elephant's cool thing

2
00:00:05,700 --> 00:00:10,290
for these guys it's that they have really really long

3
00:00:12,200 --> 00:00:18,380
and that's cool and that's pretty much all it is to say
```

(The folder and file name are examples. The JSON responses and the subtitle text are copied from the real run. `tiny` misses a word or two. That's the trade-off for 7 seconds. Use `base` or bigger when accuracy matters.)

**Compatibility note**

```
Needs an agent with terminal access (curl), Docker, and ~2-3 GB of disk for the Txtify image, plus the Whisper model weights (tiny ~75 MB, large ~3 GB). Tested with Txtify v1.1 (lkmeta/txtify:latest, arm64 and amd64) and the current main branch. Without terminal access, the skill walks you through Txtify's web page instead.
```

**Docs link**

```
https://github.com/lkmeta/txtify
```

**Limitations and FAQ**

```markdown
**Does my audio leave my machine?** Not for transcription. It goes to your own Txtify container. YouTube jobs download the video from YouTube, and DeepL translation (off by default) sends the transcript text to DeepL.

**Can I use txtify.lkmeta.com instead?** That's the project website and a live demo of how Txtify works. For private transcription it tells you to self-host, and the skill never uploads your files there.

**How long does it take?** On CPU, a short clip takes seconds with `tiny`/`base`. Long recordings with `medium`/`large` can take longer than the recording itself. The skill waits up to 30 minutes, then asks before waiting longer.

**Why is my .txt full of timestamps?** Txtify's txt export keeps the timestamp blocks. Ask for plain text and the skill strips them (for untranslated jobs it can also use the raw `transcription.txt`).

**Speaker labels, live transcription, playlists?** Not supported by Txtify today.
```

**Logo:** `static/txtify_logo.png` (500×500, square).

**Categories** (up to 3, the first decides the listing page):
1. Image & Video
2. Writing & Content
3. Productivity

(Translation & Localization fits too, but translation is an optional extra here, so it would oversell it as a first or second pick.)

**Tags:** transcription, subtitles, whisper, speech-to-text, self-hosted, docker, youtube, privacy, srt, captions

**Use cases:**
- transcribe a podcast, interview or lecture recording
- make .srt / .vtt subtitles for a video
- get a YouTube transcript without a cloud service
- translate a transcript with your own DeepL key

**Permissions:** the form detects these from the ZIP. Make sure it shows:
- tools: terminal / shell (`curl`, `docker`)
- files: reads the media file the user names, writes to the folder the user approves
- network: `127.0.0.1:8011` (local Txtify); Docker Hub for the image pull; from inside the container, the Whisper weights download, YouTube (URL jobs only) and DeepL (translation only)
- services: Docker. A DeepL API key only if translation is used

**Pricing:** Free.

## Step by step on agensi.io

1. **Account.** Sign up at agensi.io. No payout setup is needed for a free skill.
2. **Creator Mode.** Dashboard → Settings → turn on Creator Mode.
3. **Profile.** Fill in name, bio, avatar and a link (use `https://github.com/lkmeta/txtify`). Pick a handle (3-40 characters). Your storefront becomes `agensi.io/creators/<handle>`, and the handle can only change once every 30 days.
4. **Submit.** Go to `agensi.io/dashboard/submit` (Creator Dashboard → "Submit a Skill").
5. **Upload** `dist/txtify-transcribe.zip`. The form reads `name`, `description`, `summary`, `version`, `tags`, `keywords`, `use_cases` and `docs_url` from the frontmatter.
6. **Fill the fields** from the "Listing content" section above: Name, Summary, Description, Logo, See it in action, Compatibility note, Docs link, Limitations and FAQ. The AI helper can pre-fill empty fields, but replace its text with the copy above so nothing gets overclaimed.
7. **Categories, tags, use cases** as listed above.
8. **Permissions.** Compare what the form detected with the list above. If network or files are missing, add them rather than leaving the listing quieter than the skill.
9. **Pricing.** Choose Free. Don't set a price. Paid listings have a $1 minimum and need Stripe or Zoneless.
10. **Preview** desktop and mobile, then submit. The form auto-saves drafts.

## Review and the security scan

Every upload goes through an 8-check automated scan, an AI review and a human check. Expect a few hours, up to 48.

Expected scan result for this ZIP: **warnings, no failures.** `curl` and file writes are flagged as warnings by design (−5 each from 100). There's no `sudo`, `base64`, `curl | sh`, `shell=True`, environment-variable reading, secrets, or code that reads local data and sends it anywhere remote. The only upload goes to `127.0.0.1`, and the user has to confirm it first. If the "Network access" check fails anyway, it's the local upload: reply in the review notes that the target is the user's own localhost container, and point to step 4 of the SKILL.md.

Status shows in the dashboard as **Pending → Live**, **Rejected** (with reasons by email and in the dashboard) or **Paused**. To fix a rejection: change the files, bump `version:`, rebuild the ZIP and click **Resubmit**. An identical ZIP is refused.

## After it goes live

1. Open your public listing from the dashboard, and check it in a private window (logged out) to confirm it's visible.
2. Load it into your own agent through the Agensi MCP. Loading your own skill is free and doesn't count as a use.
3. Run the request from "See it in action" against a fresh `docker run`. Check that it asks before pulling and uploading, saves to the folder you gave it, and refuses to overwrite an existing file without asking.
4. Optionally link the listing from the README once it's live.

## Updating when Txtify changes

Update the skill whenever something it depends on changes: `/transcribe` form fields, `/status` JSON or status strings (`src/status.py`), export formats, models (`src/models.py`), language lists, default limits, or the Docker run command. `tests/test_skill.py` catches most of these in CI. For a Docker Hub release, also drop the "v1.1 only" notes once `latest` includes the newer behavior.

1. Edit `skills/txtify-transcribe/SKILL.md` (and regenerate `references/options.md` if the language lists changed).
2. Bump `version:` in the frontmatter.
3. Run `scripts/skill_e2e.sh` against the image users actually pull (`docker pull lkmeta/txtify:latest` first: docker-compose tags local builds with the same name, and the script refuses a `lkmeta/*` image without a registry digest), and against `txtify:e2e` for the current code.
4. Rebuild the ZIP and upload it as an update from the dashboard. Updates with no failed checks and an AI approval can go live automatically.
