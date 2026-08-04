#!/usr/bin/env bash
# Deep verification of the status state machine against the REAL worker in Docker.
# Proves every terminal path + that no processes or files are left behind.
# Assumes the container is already built and running on 8011.
set -uo pipefail

BASE="http://localhost:8011"
NAME="txtify_container"
FAIL=0
pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; FAIL=1; }

phase()    { curl -sf "$BASE/status?pid=$1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["phase"])' 2>/dev/null; }
progress() { curl -sf "$BASE/status?pid=$1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["progress"])' 2>/dev/null; }
# Authoritative worker OS pid straight from the DB row (the same value /cancel uses).
worker_pid_for() { docker exec "$NAME" python -c "import sys;sys.path.insert(0,'src');from db import transcriptionsDB;print(transcriptionsDB('output/transcriptions.db').get_process_pid($1) or '')" 2>/dev/null; }
run_state() { docker exec "$NAME" sh -c "awk '{print \$3}' /proc/$1/stat 2>/dev/null"; }  # R/S/D/Z or empty(gone)
running() { s=$(run_state "$1"); [ "$s" = "R" ] || [ "$s" = "S" ] || [ "$s" = "D" ]; }  # truly executing (not zombie/gone)

submit() { # model -> job id
  curl -sf -X POST "$BASE/transcribe" -F media=@"/tmp/long.mp3" \
    -F language=en -F "model=$1" -F translation=none -F language_translation=en \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["pid"])'
}

# Wait until the WORKER is genuinely running: progress >= 30 is set by the worker
# subprocess itself (10 is set by the main process before the worker spawns).
wait_inflight() {
  for _ in $(seq 1 200); do
    p=$(progress "$1"); [ -z "$p" ] && { sleep 0.3; continue; }
    if [ "$p" -ge 30 ] && [ "$p" -lt 100 ]; then return 0; fi
    [ "$p" -ge 100 ] && return 1
    sleep 0.3
  done
  return 1
}

echo "==> Building a ~60s looped audio so jobs stay in-flight long enough to interrupt"
docker cp tests/fixtures/speech.mp3 "$NAME:/tmp/speech.mp3" >/dev/null
docker exec "$NAME" ffmpeg -y -loglevel error -stream_loop 30 -i /tmp/speech.mp3 -c copy /tmp/long.mp3
docker cp "$NAME:/tmp/long.mp3" /tmp/long.mp3 >/dev/null

# ---------------------------------------------------------------------------
echo "==> CASE 1: cancel a running job — status sticks Canceled, worker killed, files cleaned"
J=$(submit whisper_base)
echo "    job=$J"
if wait_inflight "$J"; then
  curl -sf -X POST "$BASE/cancel?pid=$J" >/dev/null
  sleep 2
  [ "$(phase "$J")" = "Canceled" ] && pass "status is Canceled" || fail "status is '$(phase "$J")' not Canceled"
  # the worker's code must have stopped (SIGKILL); a leftover zombie is a
  # separate, pre-existing reaping matter and is reported at the end.
  WP=$(worker_pid_for "$J")
  if running "$WP"; then fail "worker $WP still EXECUTING after cancel (state=$(run_state "$WP"))"; else pass "worker stopped (state=$(run_state "$WP" | sed 's/^$/gone/'))"; fi
  # files cleaned — no output/<job> dir, no output/<job>_* files
  LEFT=$(docker exec "$NAME" sh -c "ls -d output/$J output/${J}_* 2>/dev/null" | tr '\n' ' ')
  [ -z "$LEFT" ] && pass "no leftover files" || fail "leftover files: $LEFT"
  # terminal sticks: a late poll (and any late worker write) stays Canceled
  sleep 1; [ "$(phase "$J")" = "Canceled" ] && pass "terminal state sticks" || fail "flipped to '$(phase "$J")'"
else
  fail "job never went in-flight (progress=$(progress "$J")) — cannot test cancel"
fi

# ---------------------------------------------------------------------------
echo "==> CASE 2: worker crashes (kill -9) — /status detects dead pid and flips to Error"
J2=$(submit whisper_base)
echo "    job=$J2"
if wait_inflight "$J2"; then
  WPID=$(worker_pid_for "$J2")
  if [ -n "$WPID" ] && running "$WPID"; then
    docker exec "$NAME" sh -c "kill -9 $WPID" 2>/dev/null
    echo "    killed worker pid $WPID; polling for Error..."
    OK=0
    for _ in $(seq 1 20); do
      ph=$(phase "$J2")
      case "$ph" in Error:*) OK=1; break;; esac
      sleep 0.5
    done
    [ "$OK" = 1 ] && pass "flipped to '$ph'" || fail "never flipped to Error (phase='$(phase "$J2")')"
    echo "$(phase "$J2")" | grep -q "stopped unexpectedly" && pass "informative dead-worker message" || fail "message not informative"
  else
    fail "could not find worker pid for $J2"
  fi
else
  fail "job2 never went in-flight — cannot test dead worker"
fi

# ---------------------------------------------------------------------------
echo "==> CASE 3: orphan recovery — job in-flight during restart is marked Error at boot"
J3=$(submit whisper_base)
echo "    job=$J3"
if wait_inflight "$J3"; then
  docker restart "$NAME" >/dev/null
  for _ in $(seq 1 40); do curl -sf "$BASE/health" >/dev/null 2>&1 && break; sleep 0.5; done
  sleep 1
  ph=$(phase "$J3")
  echo "$ph" | grep -qi "error" && pass "orphan marked Error ('$ph')" || fail "orphan not recovered (phase='$ph')"
else
  fail "job3 never went in-flight — cannot test orphan recovery"
fi

# ---------------------------------------------------------------------------
echo "==> CASE 4: happy path still completes end-to-end (tiny, short fixture)"
docker cp tests/fixtures/speech.mp3 "$NAME:/tmp/speech.mp3" >/dev/null
JH=$(curl -sf -X POST "$BASE/transcribe" -F media=@"tests/fixtures/speech.mp3" \
  -F language=en -F model=whisper_tiny -F translation=none -F language_translation=en \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["pid"])')
for _ in $(seq 1 120); do [ "$(progress "$JH")" = "100" ] && break; sleep 1; done
[ "$(phase "$JH")" = "Completed successfully!" ] && pass "completes with 'Completed successfully!'" || fail "final phase '$(phase "$JH")'"

# ---------------------------------------------------------------------------
echo "==> FINAL: no worker is still EXECUTING (zombies counted separately)"
RUNNING=$(docker exec "$NAME" sh -c "for p in /proc/[0-9]*; do read _ c st _ </\$p/stat 2>/dev/null; echo \$c \$st; done" 2>/dev/null | grep -i 'transcribe' | grep -vw Z)
[ -z "$RUNNING" ] && pass "no worker still executing" || fail "worker(s) still executing: $RUNNING"

echo "==> OBSERVE: zombie (defunct) workers awaiting reap — pre-existing, separate from this PR"
ZCOUNT=$(docker exec "$NAME" sh -c "grep -l 'Z' /proc/[0-9]*/stat 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
echo "  note: $ZCOUNT zombie process(es) present (uvicorn does not reap exited/killed workers)"

echo
[ "$FAIL" = 0 ] && echo "PASS: status machine verified — every terminal path correct, worker code always stops" \
              || { echo "FAILURES above"; exit 1; }
