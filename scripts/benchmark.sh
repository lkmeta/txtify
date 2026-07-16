#!/usr/bin/env bash
# Benchmark every Whisper model (and the DeepL translation path) against the
# real Docker image, using the committed speech fixture. Prints a markdown
# table; run before releases and compare with BENCHMARK.md.
#
# Usage:
#   ./scripts/benchmark.sh                 # all five models
#   ./scripts/benchmark.sh whisper_tiny whisper_base
#   BENCH_YOUTUBE=1 ./scripts/benchmark.sh # also benchmark the YouTube path
#
# Notes:
# - Whisper models are cached in the named docker volume `txtify-bench-cache`,
#   so the first run per model includes the download; later runs measure
#   inference only.
# - The translation row needs DEEPL_API_KEY in .env (skipped otherwise).
set -uo pipefail

PORT="${BENCH_PORT:-8091}"
BASE="http://127.0.0.1:${PORT}"
IMAGE=txtify:bench
NAME=txtify_bench
FIXTURE=tests/fixtures/speech.mp3
EXPECT="quick brown fox"
REFERENCE="the quick brown fox jumps over the lazy dog welcome to txtify your transcription assistant"
if [ "$#" -gt 0 ]; then MODELS=("$@"); else
  MODELS=(whisper_tiny whisper_base whisper_small whisper_medium whisper_large)
fi
trap 'docker rm -f $NAME >/dev/null 2>&1 || true' EXIT

echo "==> Building image"
docker build -q -t $IMAGE . >/dev/null

echo "==> Starting container (model cache volume: txtify-bench-cache)"
docker rm -f $NAME >/dev/null 2>&1 || true
docker run -d --rm --name $NAME -p "${PORT}:8011" \
  --env-file .env -v txtify-bench-cache:/root/.cache $IMAGE >/dev/null
for _ in $(seq 1 30); do curl -sf "$BASE/health" >/dev/null && break; sleep 2; done

submit_and_wait() {  # args: extra curl -F options...; sets DUR and SRT
  local start end job progress
  start=$(date +%s)
  job=$(curl -sf -X POST "$BASE/transcribe" "$@" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["pid"])') || return 1
  for _ in $(seq 1 360); do   # up to 30 min (large on CPU is slow)
    progress=$(curl -sf "$BASE/status?pid=$job" | python3 -c 'import json,sys; print(json.load(sys.stdin)["progress"])' || echo "")
    [ "$progress" = "100" ] && break
    [ "$progress" = "0" ] && { echo "    job $job errored:" >&2; docker exec $NAME tail -5 "output/${job}_logs.txt" >&2 || true; return 1; }
    sleep 5
  done
  [ "$progress" = "100" ] || return 1
  end=$(date +%s)
  DUR=$((end - start))
  SRT=$(curl -sf "$BASE/preview?pid=$job" | python3 -c 'import json,sys; print(json.load(sys.stdin)["srt"])')
  curl -sf -X POST "$BASE/cleanup?pid=$job" >/dev/null || true
}

wer() {  # word error rate (%) of SRT $1's text lines vs $REFERENCE
  python3 - "$REFERENCE" "$1" <<'PY'
import re, sys
# keep only subtitle text lines (drop indices and timestamp lines)
text = " ".join(
    l for l in sys.argv[2].splitlines()
    if l.strip() and "-->" not in l and not l.strip().isdigit()
)
norm = lambda s: re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()
ref, hyp = norm(sys.argv[1]), norm(text)
d = list(range(len(hyp) + 1))
for i, r in enumerate(ref, 1):
    prev, d[0] = d[0], i
    for j, h in enumerate(hyp, 1):
        prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
print(f"{100 * d[len(hyp)] / max(1, len(ref)):.0f}%")
PY
}

ROWS=""
for model in "${MODELS[@]}"; do
  echo "==> $model"
  if submit_and_wait -F media=@"$FIXTURE" -F language=en -F "model=$model" \
       -F translation=none -F language_translation=en; then
    line=$(printf '%s\n' "$SRT" | sed -n 3p)
    if printf '%s' "$SRT" | tr '[:upper:]' '[:lower:]' | /usr/bin/grep -q "$EXPECT"; then ok="yes"; else ok="NO"; fi
    W=$(wer "$SRT")
    ROWS="$ROWS| $model | ${DUR}s | $ok | $W | $line |
"
  else
    ROWS="$ROWS| $model | FAILED | - | - | - |
"
  fi
done

if /usr/bin/grep -qE '^DEEPL_API_KEY=..' .env 2>/dev/null; then
  echo "==> translation (whisper_base, en -> el via DeepL)"
  if submit_and_wait -F media=@"$FIXTURE" -F language=en -F model=whisper_base \
       -F translation=deepl -F language_translation=EL; then
    line=$(printf '%s\n' "$SRT" | sed -n 3p)
    if printf '%s' "$SRT" | /usr/bin/grep -q '[α-ωΑ-Ω]'; then ok="yes"; else ok="NO"; fi
    ROWS="$ROWS| deepl en→el (base) | ${DUR}s | $ok | - | $line |
"
  else
    ROWS="$ROWS| deepl en→el (base) | FAILED | - | - | - |
"
  fi
else
  echo "==> translation skipped (no DEEPL_API_KEY in .env)"
fi

if [ "${BENCH_YOUTUBE:-0}" = "1" ]; then
  echo "==> youtube path (whisper_tiny, 19s video)"
  if submit_and_wait -F "youtube_url=https://www.youtube.com/watch?v=jNQXAC9IVRw" \
       -F language=en -F model=whisper_tiny -F translation=none -F language_translation=en; then
    line=$(printf '%s\n' "$SRT" | sed -n 3p)
    ROWS="$ROWS| youtube (tiny) | ${DUR}s | yes | - | $line |
"
  else
    ROWS="$ROWS| youtube (tiny) | FAILED | - | - | - |
"
  fi
fi

echo
echo "| run | wall time | text ok | WER | first transcribed line |"
echo "|-----|-----------|---------|-----|------------------------|"
printf '%s' "$ROWS"
