#!/usr/bin/env bash
# Runs the skills/txtify-transcribe SKILL.md workflow, with the skill's own
# commands, against a real Txtify image and asserts on the actual output files.
#
#   IMAGE=txtify:e2e ./scripts/skill_e2e.sh                  # current tree (docker_e2e.sh builds it)
#   docker pull lkmeta/txtify:latest && IMAGE=lkmeta/txtify:latest ./scripts/skill_e2e.sh
#   IMAGE=lkmeta/txtify@sha256:<digest> ./scripts/skill_e2e.sh   # published image, by digest
#   PLATFORM=linux/amd64 IMAGE=... ./scripts/skill_e2e.sh    # other arch (emulated)
#   YT=1 ...                                                 # also run the YouTube legs
#
# The build is detected from /history (404 = v1.1, 200 = newer) and every
# version-dependent check must match it. lkmeta/* images must carry a registry
# digest: docker-compose tags local builds as lkmeta/txtify:latest too.
# Needs port 8011 free (the skill's default). Creates its own uniquely named
# container + volumes, refuses to reuse existing ones, and removes only those
# on exit. Ends with "PASS: skill E2E complete".
set -u
IMAGE="${IMAGE:?set IMAGE}"
PLATFORM="${PLATFORM:-}"
BASE=http://127.0.0.1:8011
RUN_ID="$(date +%s)_$$"
NAME=txtify_skill_e2e_$RUN_ID
VOL_OUT=txtify_skill_e2e_output_$RUN_ID
VOL_CACHE=txtify_skill_e2e_cache_$RUN_ID
FIX="$(cd "$(dirname "$0")/.." && pwd)/tests/fixtures/speech.mp3"
WORK=$(mktemp -d)
OUT="$WORK/out"; mkdir -p "$OUT"
trap 'rm -rf "$WORK"' EXIT


# Prints the Nth ```sh block under the SKILL.md heading that starts with $1.
SKILL_MD="$(cd "$(dirname "$0")/.." && pwd)/skills/txtify-transcribe/SKILL.md"
snippet() {
  awk -v h="$1" -v n="${2:-1}" '
    index($0, h) == 1 { on = 1; next }
    on && /^### / { exit }
    on && /^ *```sh$/ { c++; if (c == n) { grab = 1; next } }
    grab && /^ *```$/ { exit }
    grab { sub(/^  /, ""); print }' "$SKILL_MD"
}
# Runs a snippet the way a fresh agent shell would: plain sh, empty environment.
run_fresh() { env -i PATH="$PATH" HOME="$HOME" sh -c "$1"; }

PASSES=0
ok()   { PASSES=$((PASSES+1)); echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; exit 1; }
code_of() { tail -n1 <<<"$1" | sed 's/^HTTP //'; }
job_of()  { sed -n 's/.*"pid":\([0-9][0-9]*\).*/\1/p' <<<"$1"; }

# The skill's step 5 poll loop. Same logic; it prints only the final status
# (instead of every poll) and the sleep is configurable.
poll() {
  JOB=$1; case "$JOB" in ''|*[!0-9]*) echo "bad job id"; return 1 ;; esac
  fails=0
  for i in $(seq 1 180); do
    S=$(curl -s --max-time 10 "$BASE/status?pid=$JOB")
    if [ -z "$S" ]; then
      fails=$((fails+1)); [ "$fails" -ge 3 ] && { echo "Txtify stopped responding"; break; }
    else
      fails=0
      case "$S" in
        *'"progress":"100"'*|*'"phase":"Canceled"'*|*Error*|*'not found'*) break ;;
      esac
    fi
    sleep "${POLL_SLEEP:-10}"
  done
  echo "$S"
}

submit_file() {  # file model language [translation target]  (skill step 4)
  F=$1
  curl -s --max-time 1800 -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" \
    -F "media=@\"$F\"" \
    --form-string language="$3" --form-string model="$2" \
    --form-string translation="${4:-none}" --form-string language_translation="${5:-EN}"
}

echo "== image: $IMAGE ${PLATFORM:+($PLATFORM)}"
docker image inspect "$IMAGE" >/dev/null 2>&1 || fail "image not present locally (pull or build it first)"
DIGESTS=$(docker image inspect "$IMAGE" --format '{{join .RepoDigests " "}}')
echo "   id $(docker image inspect "$IMAGE" --format '{{.Id}} arch {{.Architecture}} created {{.Created}}') digests [$DIGESTS]"
case "$IMAGE" in lkmeta/*) [ -n "$DIGESTS" ] || fail "$IMAGE has no registry digest: it's a local build, not the published image" ;; esac
docker ps -a --format '{{.Names}}' | grep -qx $NAME && fail "container $NAME already exists"
for v in $VOL_OUT $VOL_CACHE; do
  docker volume inspect $v >/dev/null 2>&1 && fail "volume $v already exists; refusing to touch it"
done
docker volume create $VOL_OUT >/dev/null && docker volume create $VOL_CACHE >/dev/null || fail "volume create"
# From here on, everything removed on exit was created by this run.
trap 'docker rm -f $NAME >/dev/null 2>&1; docker volume rm $VOL_OUT $VOL_CACHE >/dev/null 2>&1; rm -rf "$WORK"' EXIT

echo "== Txtify / Docker not available"
curl -s --max-time 5 "$BASE/health" >/dev/null; rc=$?
[ "$rc" = 7 ] && ok "no instance: health check fails with curl exit 7" || fail "port 8011 busy or unexpected rc=$rc"
msg=$(DOCKER_HOST=unix:///nonexistent.sock docker info 2>&1)
grep -q 'Cannot connect to the Docker daemon' <<<"$msg" && ok "no daemon: 'Cannot connect to the Docker daemon'" || fail "docker-down message: $msg"

echo "== step 2: start (MAX_CONCURRENT_JOBS=1 and MAX_UPLOAD_SIZE_MB=1 to reach 429 / size limit)"
docker run -d --name $NAME ${PLATFORM:+--platform $PLATFORM} -p 127.0.0.1:8011:8011 \
  -e MAX_CONCURRENT_JOBS=1 -e MAX_UPLOAD_SIZE_MB=1 \
  -v $VOL_OUT:/app/output -v $VOL_CACHE:/root/.cache "$IMAGE" >/dev/null || fail "docker run"
[ "$(docker port $NAME)" = "8011/tcp -> 127.0.0.1:8011" ] && ok "bound to 127.0.0.1 only" || fail "binding: $(docker port $NAME)"

echo "== step 1: detect"
for i in $(seq 1 60); do curl -s --max-time 5 "$BASE/health" | grep -q '"status":"ok"' && break; sleep 3; done
[ "$(curl -s --max-time 5 "$BASE/health")" = '{"status":"ok"}' ] && ok "/health ok" || fail "/health"
curl -s --max-time 5 "$BASE/" | grep -o '<title>[^<]*</title>' | grep -q Txtify && ok "title says Txtify" || fail "title"
HIST=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/history")
case "$HIST" in 404) V=v1.1 ;; 200) V=newer ;; *) fail "/history -> $HIST" ;; esac
echo "   /history -> $HIST: testing as $V"
[ -z "${EXPECT:-}" ] || [ "$EXPECT" = "$V" ] || fail "expected $EXPECT, got $V"

echo "== fixtures (made with the container's ffmpeg)"
docker cp "$FIX" $NAME:/tmp/speech.mp3 >/dev/null
docker exec $NAME sh -c 'cd /tmp &&
  ffmpeg -y -loglevel error -f lavfi -i color=c=black:s=320x240:r=10 -i speech.mp3 -shortest -c:v mpeg4 -c:a aac "talk.mp4" &&
  ffmpeg -y -loglevel error -i speech.mp3 -c:a aac speech.mkv &&
  ffmpeg -y -loglevel error -f lavfi -i anoisesrc=d=15:r=44100 -c:a pcm_s16le big.wav' || fail "fixture generation"
docker cp $NAME:/tmp/talk.mp4 "$WORK/my talk; v2.mp4" >/dev/null
docker cp $NAME:/tmp/speech.mkv "$WORK/speech.mkv" >/dev/null
docker cp $NAME:/tmp/big.wav "$WORK/big.wav" >/dev/null
printf 'not media' > "$WORK/notes.txt"
ls -l "$WORK" | sed 's/^/   /'

echo "== step 4: input validation"
R=$(curl -s -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" --form-string 'youtube_url=https://example.com/x' -F language=en -F model=whisper_tiny -F translation=none -F language_translation=EN)
[ "$(code_of "$R")" = 400 ] && grep -q 'Invalid YouTube URL' <<<"$R" && ok "non-YouTube URL -> 400" || fail "$R"
printf 'https://www.youtube.com/watch?v=jNQXAC9IVRw' > "$WORK/url.txt"   # valid URL inside a file
R=$(curl -s -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" --form-string "youtube_url=@$WORK/url.txt" -F language=en -F model=whisper_tiny -F translation=none -F language_translation=EN)
[ "$(code_of "$R")" = 400 ] && grep -q 'Invalid YouTube URL' <<<"$R" && ok "--form-string sends '@file' as literal text (400); -F would have read the file" || fail "$R"
R=$(submit_file "$WORK/notes.txt" whisper_tiny en)
[ "$(code_of "$R")" = 400 ] && grep -q 'Invalid file type' <<<"$R" && ok "unsupported .txt upload -> 400" || fail "$R"
R=$(submit_file "$WORK/missing.mp3" whisper_tiny en 2>&1); rc=$?
[ "$rc" = 26 ] && ok "missing local file -> curl exit 26, nothing sent" || fail "rc=$rc $R"
R=$(curl -s -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" -F "media=@\"$FIX\"" -F language=en -F model=whisper_tiny)
[ "$(code_of "$R")" = 422 ] && ok "missing form fields -> 422" || fail "$R"
R=$(submit_file "$FIX" whisper_tiny en deepl XX)
[ "$(code_of "$R")" = 400 ] && grep -q "Translation to 'XX' is not supported" <<<"$R" && ok "bad DeepL target -> 400" || fail "$R"
R=$(submit_file "$WORK/big.wav" whisper_tiny en)
[ "$(code_of "$R")" = 400 ] && grep -q 'exceeds 1 MB limit' <<<"$R" && ok "upload over MAX_UPLOAD_SIZE_MB -> 400" || fail "$R"
R=$(curl -s -w '\nHTTP %{http_code}\n' "$BASE/status?pid=999999")
[ "$(code_of "$R")" = 404 ] && grep -q 'Transcription not found' <<<"$R" && ok "unknown job -> 404" || fail "$R"

echo "== audio: mp3, whisper_tiny, en"
R=$(submit_file "$FIX" whisper_tiny en); J=$(job_of "$R")
[ "$(code_of "$R")" = 200 ] && [ -n "$J" ] && ok "submitted, job $J" || fail "$R"
S=$(poll "$J"); echo "   $S"
grep -q '"phase":"Completed successfully!"' <<<"$S" && ok "completed" || fail "$S"
for f in txt srt vtt sbv pdf; do
  c=$(curl -s -o "$OUT/speech.$f" -w '%{http_code}' "$BASE/downloadPreview?pid=$J&format=$f"); echo "   $f -> HTTP $c"
  eval "C_$f=$c"
done
grep -qi 'quick brown fox jumps over the lazy dog' "$OUT/speech.txt" && ok "txt has the spoken words" || fail "txt: $(cat "$OUT/speech.txt")"
grep -q -- '-->' "$OUT/speech.txt" && ok "txt export carries timestamp blocks (documented quirk)" || fail "txt has no timestamps: update the skill"
head -1 "$OUT/speech.srt" | grep -q '^1' && grep -q '^00:00:00,[0-9]* --> 00:00:0' "$OUT/speech.srt" && grep -qi 'quick brown fox' "$OUT/speech.srt" && ok "srt valid + words" || fail "srt"
head -1 "$OUT/speech.vtt" | grep -q '^WEBVTT' && grep -q -- '-->' "$OUT/speech.vtt" && grep -qi 'quick brown fox' "$OUT/speech.vtt" && ok "vtt valid + words" || fail "vtt"
grep -Eq '^[0-9]+:[0-9]{2}:[0-9]{2}\.[0-9]{3},[0-9]+:[0-9]{2}:[0-9]{2}\.[0-9]{3}$' "$OUT/speech.sbv" && grep -qi 'quick brown fox' "$OUT/speech.sbv" && ok "sbv valid + words" || fail "sbv"
if [ "$V" = newer ]; then [ "$C_pdf" = 200 ] && head -c4 "$OUT/speech.pdf" | grep -q '%PDF' && ok "pdf via /downloadPreview (%PDF)" || fail "pdf $C_pdf"
else [ "$C_pdf" = 400 ] && ok "pdf via /downloadPreview -> 400 (v1.1; use the zip)" || fail "pdf code $C_pdf on v1.1"; rm -f "$OUT/speech.pdf"; fi

echo "== step 6: overwrite guard + zip"
printf 'keep me' > "$OUT/existing.srt"
if [ -e "$OUT/existing.srt" ]; then echo "   EXISTS: ask the user"; else curl -sf -o "$OUT/existing.srt" "$BASE/downloadPreview?pid=$J&format=srt"; fi
[ "$(cat "$OUT/existing.srt")" = 'keep me' ] && ok "existing file left untouched" || fail "overwrote existing file"
curl -sf -o "$OUT/speech.zip" "$BASE/download?pid=$J" || fail "zip download"
LIST=$(unzip -Z1 "$OUT/speech.zip" | sort | tr '\n' ' ')
[ "$LIST" = "en_transcription.srt final_transcription.pdf final_transcription.sbv final_transcription.srt final_transcription.txt final_transcription.vtt logs.txt transcription.txt " ] && ok "zip has the 8 documented files" || fail "zip: $LIST"
mkdir "$OUT/speech" && unzip -q -n "$OUT/speech.zip" -d "$OUT/speech" && ok "zip extracted into a new folder" || fail "unzip"
mkdir "$OUT/speech" 2>/dev/null && fail "mkdir should refuse an existing folder" || ok "second extract refused (folder exists)"
head -c4 "$OUT/speech/final_transcription.pdf" | grep -q '%PDF' && ok "zip pdf is a real PDF" || fail "zip pdf"
grep -qi 'quick brown fox' "$OUT/speech/transcription.txt" && ! grep -q -- '-->' "$OUT/speech/transcription.txt" && ok "zip transcription.txt is plain text" || fail "plain text"
R=$(curl -s -w '\nHTTP %{http_code}\n' "$BASE/downloadPreview?pid=$J&format=docx")
[ "$(code_of "$R")" = 400 ] && ok "unknown export format -> 400" || fail "$R"

echo "== SKILL.md snippets run in a fresh sh (no variables carried over)"
SNIP5=$(snippet "### 5." 1 | sed "s/^JOB=42;/JOB=$J;/; s/sleep 10/sleep 1/")
[ -n "$SNIP5" ] || fail "could not extract the step 5 snippet"
R=$(run_fresh "$SNIP5")
tail -n1 <<<"$R" | grep -q '"phase":"Completed successfully!"' && ok "step 5 poll snippet, verbatim, in fresh sh" || fail "step 5 snippet: $R"
FRESH="$OUT/fresh dir; v2"; mkdir -p "$FRESH"
SNIP6=$(snippet "### 6." 1 | sed "s/JOB=42/JOB=$J/; s|OUT='/approved/folder'|OUT='$FRESH'|")
run_fresh "$SNIP6" && grep -qi 'quick brown fox' "$FRESH/my-talk.srt" && ok "step 6 save snippet, verbatim, in fresh sh (folder has a space and ';')" || fail "step 6 snippet"
R=$(run_fresh "$SNIP6"); [ "$R" = "EXISTS: ask the user" ] && ok "step 6 snippet refuses to overwrite on a second run" || fail "overwrite: $R"
SNIPZ=$(snippet "### 6." 2 | sed "s/JOB=42/JOB=$J/; s|OUT='/approved/folder'|OUT='$FRESH'|")
run_fresh "$SNIPZ" >/dev/null && [ -s "$FRESH/my-talk/final_transcription.srt" ] && ok "zip snippet downloads + extracts into a new folder" || fail "zip snippet"
R=$(run_fresh "$SNIPZ" 2>&1); grep -q 'EXISTS: ask the user' <<<"$R" && ok "zip snippet refuses to overwrite on a second run" || fail "zip overwrite: $R"
# Dangling symlinks at the target name: refused, and nothing is written outside.
ln -s "$WORK/outside.srt" "$FRESH/evil.srt"; ln -s "$WORK/outside.zip" "$FRESH/evilz.zip"
SNIPL=$(snippet "### 6." 1 | sed "s/JOB=42/JOB=$J/; s|OUT='/approved/folder'|OUT='$FRESH'|; s/NAME=my-talk/NAME=evil/")
R=$(run_fresh "$SNIPL"); [ "$R" = "EXISTS: ask the user" ] && [ ! -e "$WORK/outside.srt" ] && ok "step 6 snippet treats a dangling symlink as taken" || fail "symlink: $R"
R=$(run_fresh "$(grep -v 'EXISTS: ask the user' <<<"$SNIPL")")
[ "$R" = "download failed or name taken" ] && [ ! -e "$WORK/outside.srt" ] && ok "even with that check removed, ln refuses the symlink (nothing written outside)" || fail "ln symlink: $R"
SNIPZL=$(snippet "### 6." 2 | sed "s/JOB=42/JOB=$J/; s|OUT='/approved/folder'|OUT='$FRESH'|; s/NAME=my-talk/NAME=evilz/")
R=$(run_fresh "$SNIPZL"); [ "$R" = "EXISTS: ask the user" ] && [ ! -e "$WORK/outside.zip" ] && ok "zip snippet treats a dangling symlink as taken" || fail "zip symlink: $R"
R=$(run_fresh "$(grep -v 'EXISTS: ask the user' <<<"$SNIPZL")")
[ "$R" = "download failed or name taken" ] && [ ! -e "$WORK/outside.zip" ] && [ ! -e "$FRESH/evilz" ] && ok "zip: even with that check removed, ln refuses the symlink" || fail "zip ln symlink: $R"
ls -A "$FRESH" | grep -q '^\.txtify-' && fail "temp files left behind: $(ls -A "$FRESH")" || ok "no temp files left in the output folder"
SNIPM=$(snippet "### 6." 1 | sed "s/JOB=42/JOB=$J/; s|OUT='/approved/folder'|OUT='$OUT/does-not-exist'|")
R=$(run_fresh "$SNIPM"); [ "$R" = "folder missing or not writable" ] && [ ! -e "$OUT/does-not-exist" ] && ok "step 6 snippet refuses a missing folder, writes nothing" || fail "missing folder: $R"

echo "== video: mp4 with a space and ';' in the name, whisper_base, auto"
R=$(submit_file "$WORK/my talk; v2.mp4" whisper_base auto); J2=$(job_of "$R")
[ "$(code_of "$R")" = 200 ] && ok "quoted path with ';' uploaded, job $J2" || fail "$R"
S=$(poll "$J2"); echo "   $S"
grep -q '"phase":"Completed successfully!"' <<<"$S" && ok "video completed" || fail "$S"
curl -sf -o "$OUT/talk.srt" "$BASE/downloadPreview?pid=$J2&format=srt"
grep -qi 'quick brown fox' "$OUT/talk.srt" && ok "video srt has the spoken words" || fail "$(cat "$OUT/talk.srt")"

echo "== mkv upload"
R=$(submit_file "$WORK/speech.mkv" whisper_tiny en); J3=$(job_of "$R")
if [ "$V" = v1.1 ]; then [ "$(code_of "$R")" = 400 ] && grep -q 'Invalid file type' <<<"$R" && ok "mkv rejected (v1.1)" || fail "$R"
else S=$(poll "$J3"); grep -q 'Completed successfully!' <<<"$S" && ok "mkv accepted and completed (newer build)" || fail "$S"; fi

echo "== unknown model name falls back silently"
R=$(submit_file "$FIX" whisper_bogus en); J4=$(job_of "$R")
S=$(poll "$J4"); echo "   $S"
grep -q 'Completed successfully!' <<<"$S" && ok "model=whisper_bogus still completes (silent fallback, documented)" || fail "$S"

echo "== failed transcription: unsupported spoken language"
R=$(submit_file "$FIX" whisper_tiny xx); J5=$(job_of "$R")
S=$(poll "$J5"); echo "   $S"
grep -q '"phase":"Error' <<<"$S" && ok "language=xx -> Error phase" || fail "$S"

echo "== busy (429), download before completion (404), cancel"
R=$(submit_file "$FIX" whisper_small en); J6=$(job_of "$R")
R2=$(submit_file "$FIX" whisper_tiny en)
[ "$(code_of "$R2")" = 429 ] && grep -q 'Server is busy' <<<"$R2" && ok "second job while one runs -> 429" || fail "$R2"
R=$(curl -s -w '\nHTTP %{http_code}\n' "$BASE/downloadPreview?pid=$J6&format=txt")
[ "$(code_of "$R")" = 404 ] && grep -q 'in progress or not found' <<<"$R" && ok "download before completion -> 404" || fail "$R"
curl -s -X POST "$BASE/cancel?pid=$J6" | grep -q 'canceled successfully' || fail "cancel"
S=$(poll "$J6"); echo "   $S"
grep -q '"phase":"Canceled"' <<<"$S" && ok "canceled job reports Canceled" || fail "$S"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/download?pid=$J6")" = 404 ] && ok "canceled job has nothing to download" || fail "cancel download"

echo "== translation without a DeepL key"
R=$(submit_file "$FIX" whisper_tiny en deepl DE); J7=$(job_of "$R")
S=$(poll "$J7"); echo "   $S"
grep -q '"phase":"Completed (translation failed)"' <<<"$S" && ok "honest 'Completed (translation failed)'" || fail "$S"
curl -sf "$BASE/downloadPreview?pid=$J7&format=txt" | grep -qi 'quick brown fox' && ok "original-language text kept" || fail "translation-failed text"

if [ "${YT:-0}" = 1 ]; then
  echo "== YouTube (19 s public video 'Me at the zoo')"
  R=$(curl -s --max-time 1800 -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" \
    --form-string 'youtube_url=https://www.youtube.com/watch?v=jNQXAC9IVRw' \
    -F language=en -F model=whisper_tiny -F translation=none -F language_translation=EN); J8=$(job_of "$R")
  [ "$(code_of "$R")" = 200 ] && ok "YouTube submitted, job $J8" || fail "$R"
  S=$(poll "$J8"); echo "   $S"
  curl -sf -o "$OUT/zoo.srt" "$BASE/downloadPreview?pid=$J8&format=srt"
  grep -qi 'elephant' "$OUT/zoo.srt" && ok "YouTube srt has the spoken words" || fail "$(cat "$OUT/zoo.srt")"
  if [ "$V" = v1.1 ]; then  # v1.1: limit is checked from metadata, before any download
    echo "== YouTube duration limit (15:05 video)"
    R=$(curl -s --max-time 120 -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" \
      --form-string 'youtube_url=https://www.youtube.com/watch?v=UF8uR6Z6KLc' \
      -F language=en -F model=whisper_tiny -F translation=none -F language_translation=EN)
    [ "$(code_of "$R")" = 400 ] && grep -q 'exceeds 15 minute limit' <<<"$R" && ok "over-15-min video -> 400 (v1.1 default limit)" || fail "$R"
  else
    echo "   skip duration-limit leg: newer builds default to no limit, it would download the full 15-min video"
  fi
fi

echo "== curl timeout on submit"
R=$(curl -s --max-time 1 -w '\nHTTP %{http_code}\n' -X POST "$BASE/transcribe" \
  -F "media=@\"$WORK/my talk; v2.mp4\"" -F language=en -F model=whisper_tiny -F translation=none -F language_translation=EN --limit-rate 1k 2>&1); rc=$?
[ "$rc" = 28 ] && ok "slow submit -> curl exit 28, no job id returned" || fail "rc=$rc $R"

echo "== Txtify goes away mid-poll"
docker stop $NAME >/dev/null
S=$(POLL_SLEEP=1 poll "$J"); [ "$S" = "Txtify stopped responding" ] || S=$(tail -n1 <<<"$S")
grep -q 'stopped responding' <<<"$S" && ok "poll loop stops after 3 failed checks" || fail "$S"

echo "== saved files"
ls -l "$OUT" | sed 's/^/   /'
echo "PASS: skill E2E complete ($PASSES checks) on $IMAGE [$V] ${PLATFORM:+($PLATFORM)}"
