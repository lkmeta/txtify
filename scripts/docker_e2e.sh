#!/usr/bin/env bash
# End-to-end smoke test against the real Docker image.
# Builds the image, boots a container, uploads a generated audio clip,
# polls /status until the transcription completes, and checks every export.
#
# Usage: ./scripts/docker_e2e.sh [port]
set -euo pipefail

PORT="${1:-8077}"
IMAGE=txtify:e2e
NAME=txtify_e2e
BASE="http://127.0.0.1:${PORT}"
WORKDIR="$(mktemp -d)"
trap 'docker rm -f $NAME >/dev/null 2>&1 || true; rm -rf "$WORKDIR"' EXIT

echo "==> Building image"
docker build -q -t $IMAGE .

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

echo "==> Generating 5s speech-like fixture"
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "sine=frequency=300:duration=5" "$WORKDIR/clip.mp3"

echo "==> Submitting transcription (whisper tiny)"
JOB=$(curl -sf -X POST "$BASE/transcribe" \
  -F media=@"$WORKDIR/clip.mp3" -F language=en -F model=whisper_tiny \
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
curl -sf "$BASE/preview?pid=$JOB" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all(k in d for k in ("txt","srt","vtt","sbv")), d.keys()'
curl -sf -o "$WORKDIR/result.zip" "$BASE/download?pid=$JOB"
LISTING=$(unzip -l "$WORKDIR/result.zip")
echo "$LISTING"
case "$LISTING" in
  *final_transcription.pdf*) ;;
  *) echo "FAIL: pdf missing from zip"; exit 1 ;;
esac

echo "==> Validation errors"
echo x > "$WORKDIR/bad.exe"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/transcribe" \
  -F media=@"$WORKDIR/bad.exe" -F language=en -F model=whisper_tiny \
  -F translation=none -F language_translation=en)
[ "$code" = "400" ] || { echo "FAIL: bad extension returned $code"; exit 1; }

echo "PASS: docker E2E complete"
