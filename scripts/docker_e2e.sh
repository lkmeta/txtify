#!/usr/bin/env bash
# End-to-end smoke test against the real Docker image.
# Builds the image, boots a container, uploads a generated audio clip,
# polls /status until the transcription completes, and checks every export.
#
# Usage: ./scripts/docker_e2e.sh [port]
#   IMAGE=lkmeta/txtify:latest ./scripts/docker_e2e.sh   # test a published
#   image instead of building from the working tree (used by the scheduled
#   published-image check so a broken push gets caught, not discovered).
set -euo pipefail

PORT="${1:-8077}"
IMAGE="${IMAGE:-}"
NAME=txtify_e2e
BASE="http://127.0.0.1:${PORT}"
WORKDIR="$(mktemp -d)"
trap 'docker rm -f $NAME >/dev/null 2>&1 || true; rm -rf "$WORKDIR"' EXIT

if [ -z "$IMAGE" ]; then
  IMAGE=txtify:e2e
  echo "==> Building image"
  docker build -q -t $IMAGE .
else
  echo "==> Testing published image: $IMAGE"
  docker pull -q "$IMAGE"
fi

echo "==> Starting container"
docker run -d --rm --name $NAME -p "${PORT}:8011" $IMAGE >/dev/null

echo "==> Waiting for /health"
for _ in $(seq 1 30); do
  curl -sf "$BASE/health" >/dev/null && break
  sleep 2
done
curl -sf "$BASE/health" | grep -q '"ok"' || { echo "FAIL: /health"; exit 1; }

echo "==> Static pages"
for p in / /faq /contact; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$p")
  [ "$code" = "200" ] || { echo "FAIL: $p returned $code"; exit 1; }
done
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/nope")
[ "$code" = "404" ] || { echo "FAIL: unknown route returned $code"; exit 1; }

echo "==> Submitting transcription of real speech fixture (whisper tiny)"
JOB=$(curl -sf -X POST "$BASE/transcribe" \
  -F media=@"tests/fixtures/speech.mp3" -F language=en -F model=whisper_tiny \
  -F translation=none -F language_translation=en | python3 -c 'import json,sys; print(json.load(sys.stdin)["pid"])')
echo "    job id: $JOB"

echo "==> Polling /status (model download + transcription can take a few minutes)"
for _ in $(seq 1 120); do
  PROGRESS=$(curl -sf "$BASE/status?pid=$JOB" | python3 -c 'import json,sys; print(json.load(sys.stdin)["progress"])')
  echo "    progress: $PROGRESS"
  [ "$PROGRESS" = "100" ] && break
  [ "$PROGRESS" = "0" ] && { echo "FAIL: job errored"; docker exec $NAME cat "output/${JOB}_logs.txt" 2>/dev/null | tail -20; exit 1; }
  sleep 5
done
[ "$PROGRESS" = "100" ] || { echo "FAIL: timed out"; exit 1; }

echo "==> Preview + downloads"
# The fixture says "the quick brown fox ..." — assert real words came out.
curl -sf "$BASE/preview?pid=$JOB" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert all(k in d for k in ("txt", "srt", "vtt", "sbv")), d.keys()
srt = d["srt"]
assert "quick brown fox" in srt.lower(), "transcription wrong: %r" % srt
print("    transcribed:", srt.splitlines()[2])
'
curl -sf -o "$WORKDIR/result.zip" "$BASE/download?pid=$JOB"
LISTING=$(unzip -l "$WORKDIR/result.zip")
echo "$LISTING"
case "$LISTING" in
  *final_transcription.pdf*) ;;
  *) echo "FAIL: pdf missing from zip"; exit 1 ;;
esac

echo "==> MKV upload (video container path — converted to mp3 by ffmpeg in-app)"
docker cp tests/fixtures/speech.mp3 "$NAME:/tmp/speech.mp3" >/dev/null
docker exec $NAME ffmpeg -y -loglevel error -i /tmp/speech.mp3 -c:a aac /tmp/speech.mkv
docker cp "$NAME:/tmp/speech.mkv" "$WORKDIR/speech.mkv" >/dev/null
MKVJOB=$(curl -sf -X POST "$BASE/transcribe" \
  -F media=@"$WORKDIR/speech.mkv" -F language=en -F model=whisper_tiny \
  -F translation=none -F language_translation=en | python3 -c 'import json,sys; print(json.load(sys.stdin)["pid"])')
for _ in $(seq 1 60); do
  P=$(curl -sf "$BASE/status?pid=$MKVJOB" | python3 -c 'import json,sys; print(json.load(sys.stdin)["progress"])')
  [ "$P" = "100" ] && break
  [ "$P" = "0" ] && { echo "FAIL: mkv job errored"; exit 1; }
  sleep 5
done
[ "$P" = "100" ] || { echo "FAIL: mkv timed out"; exit 1; }
curl -sf "$BASE/preview?pid=$MKVJOB" | python3 -c '
import json, sys
assert "quick brown fox" in json.load(sys.stdin)["txt"].lower(), "mkv transcription wrong"
print("    mkv transcribed correctly")
'

echo "==> Translation path (no DeepL key in this container -> honest failure status)"
TJOB=$(curl -sf -X POST "$BASE/transcribe" \
  -F media=@"tests/fixtures/speech.mp3" -F language=en -F model=whisper_tiny \
  -F translation=deepl -F language_translation=EL | python3 -c 'import json,sys; print(json.load(sys.stdin)["pid"])')
for _ in $(seq 1 60); do
  TPHASE=$(curl -sf "$BASE/status?pid=$TJOB" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["progress"], d["phase"])')
  case "$TPHASE" in "100 "*) break ;; "0 "*) break ;; esac
  sleep 5
done
echo "    final: $TPHASE"
case "$TPHASE" in
  "100 Completed (translation failed)") ;;  # keyless container: exports ship untranslated, status is honest
  "100 Completed successfully!") ;;         # container has a working key (local runs)
  *) echo "FAIL: translation job ended as '$TPHASE'"; exit 1 ;;
esac

echo "==> Validation errors"
echo x > "$WORKDIR/bad.exe"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/transcribe" \
  -F media=@"$WORKDIR/bad.exe" -F language=en -F model=whisper_tiny \
  -F translation=none -F language_translation=en)
[ "$code" = "400" ] || { echo "FAIL: bad extension returned $code"; exit 1; }

echo "PASS: docker E2E complete"
